"""
Context builder for assembling hotspot code and dependencies into an LLM prompt.
"""

from __future__ import annotations
import os
from typing import Dict, List, Optional, Union
from ..models.schemas import Hotspot


def normalize_path(path: str) -> str:
    """Normalizes path separators to POSIX style and strips leading dots/slashes."""
    return path.replace("\\", "/").strip("./")


def lookup_file_content(path: str, file_contents: Dict[str, str]) -> Optional[str]:
    """Looks up file content in dict handling differences in path separators."""
    norm_target = normalize_path(path)
    for k, v in file_contents.items():
        if normalize_path(k) == norm_target:
            return v
    return None


class ContextBuilder:
    """Gathers and formats hotspot code and related files into context for the LLM."""

    @staticmethod
    def format_hotspot_info(hotspot: Hotspot) -> str:
        deps = ", ".join(hotspot.dependencies) if hotspot.dependencies else "None identified"
        related = ", ".join(hotspot.related_files) if hotspot.related_files else "None"
        return (
            f"- Function: {hotspot.function}\n"
            f"- Qualified Name: {hotspot.qualified_name}\n"
            f"- Primary File: {normalize_path(hotspot.file)} (Line {hotspot.line})\n"
            f"- Dependencies / Callees: {deps}\n"
            f"- Related Files: {related}"
        )

    @staticmethod
    def format_profiler_metrics(hotspot: Hotspot) -> str:
        return (
            f"- Total Invocations: {hotspot.calls:,} calls\n"
            f"- Self Time: {hotspot.self_time:.4f}s\n"
            f"- Cumulative Time: {hotspot.cumulative_time:.4f}s\n"
            f"- Total Runtime Contribution: {hotspot.runtime_percent:.1f}%"
        )

    @classmethod
    def format_source_context(
        cls,
        hotspot: Hotspot,
        file_contents: Optional[Dict[str, str]] = None,
        base_dir: str = "."
    ) -> str:
        """
        Extracts and formats source code for the hotspot file and related files.
        If file_contents dictionary is provided, uses it; otherwise reads from disk.
        Normalizes paths across Windows and POSIX systems.
        """
        files_to_include: List[str] = [hotspot.file]
        seen_normalized = {normalize_path(hotspot.file)}

        for rel_file in hotspot.related_files:
            norm_rel = normalize_path(rel_file)
            if norm_rel not in seen_normalized and len(files_to_include) < 3:
                files_to_include.append(rel_file)
                seen_normalized.add(norm_rel)

        blocks = []
        for rel_path in files_to_include:
            content = None
            if file_contents:
                content = lookup_file_content(rel_path, file_contents)

            if content is None:
                # Attempt to read from disk
                disk_path = os.path.join(base_dir, rel_path)
                if os.path.exists(disk_path):
                    try:
                        with open(disk_path, "r", encoding="utf-8") as f:
                            content = f.read()
                    except Exception as e:
                        content = f"# Could not read {rel_path}: {e}"

            if content is not None:
                display_path = normalize_path(rel_path)
                blocks.append(
                    f"#### FILE: `{display_path}`\n"
                    f"```python\n"
                    f"{content.strip()}\n"
                    f"```"
                )

        if not blocks:
            return "# No source code files could be loaded."

        return "\n\n".join(blocks)

    @classmethod
    def build_prompt_sections(
        cls,
        hotspot: Union[Hotspot, Dict],
        file_contents: Optional[Dict[str, str]] = None,
        base_dir: str = "."
    ) -> Dict[str, str]:
        """Returns the individual formatted sections for prompt formatting."""
        if isinstance(hotspot, dict):
            hotspot = Hotspot.from_dict(hotspot)

        return {
            "hotspot_info": cls.format_hotspot_info(hotspot),
            "profiler_metrics": cls.format_profiler_metrics(hotspot),
            "context_code": cls.format_source_context(hotspot, file_contents, base_dir)
        }
