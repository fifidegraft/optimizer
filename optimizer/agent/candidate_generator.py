"""
Candidate generator module.
Coordinates LLM prompting, parses structured output, validates Python syntax,
and produces CandidatePatch objects ready for verification and benchmarking.
"""

from __future__ import annotations
import ast
import os
import re
import sys
from typing import Dict, List, Optional, Union

from ..models.schemas import CandidatePatch, Hotspot, ModifiedFile
from .context_builder import ContextBuilder, lookup_file_content, normalize_path
from .llm_client import BaseLLMClient, MockLLMClient, get_llm_client
from .prompts import SYSTEM_OPTIMIZER_PROMPT, format_user_prompt


class CandidateGenerator:
    """Generates and validates candidate optimization patches."""

    def __init__(self, client: Optional[BaseLLMClient] = None):
        self.client = client or get_llm_client()

    def generate(
        self,
        hotspot: Union[Hotspot, Dict],
        file_contents: Optional[Dict[str, str]] = None,
        base_dir: str = "."
    ) -> List[CandidatePatch]:
        """
        Main entrypoint: generates 2-3 candidate optimization patches for a given hotspot.
        """
        if isinstance(hotspot, dict):
            hotspot = Hotspot.from_dict(hotspot)

        # Handle MockLLMClient with synthesized candidates if mock client is active
        if isinstance(self.client, MockLLMClient):
            return self._generate_mock_candidates(hotspot, file_contents, base_dir)

        # Build prompt
        sections = ContextBuilder.build_prompt_sections(hotspot, file_contents, base_dir)
        user_prompt = format_user_prompt(
            hotspot_info=sections["hotspot_info"],
            profiler_metrics=sections["profiler_metrics"],
            context_code=sections["context_code"]
        )

        # Call LLM client
        try:
            response_json = self.client.generate_json(
                prompt=user_prompt,
                system_prompt=SYSTEM_OPTIMIZER_PROMPT
            )
        except Exception as e:
            print(f"[CandidateGenerator] LLM generation failed: {e}. Falling back to mock generator.", file=sys.stderr)
            return self._generate_mock_candidates(hotspot, file_contents, base_dir)

        raw_candidates = response_json.get("candidates", [])
        candidates: List[CandidatePatch] = []

        for raw in raw_candidates:
            cid = raw.get("candidate_id", f"candidate_{len(candidates) + 1}")
            strategy = raw.get("strategy", "Unknown Strategy")
            explanation = raw.get("explanation", "")
            edits_list = []
            candidate_valid = True

            # Support both Fifi's 'edits' and legacy 'modified_files'
            raw_edits = raw.get("edits") or raw.get("modified_files") or []

            for f in raw_edits:
                path = normalize_path(f.get("path", ""))
                # Support both Fifi's 'new_content' and legacy 'content'
                raw_content = f.get("new_content") or f.get("content") or ""

                # Clean markdown fences if model inadvertently wrapped code inside JSON string
                content = self._strip_fences(raw_content)

                # Validate syntax with ast.parse
                is_valid, err = self._validate_syntax(content)
                if not is_valid:
                    print(f"[CandidateGenerator] Warning: Syntax error in {cid} for {path}: {err}")
                    candidate_valid = False
                    break

                edits_list.append(ModifiedFile(path=path, new_content=content))

            # Reject candidate completely if any of its edited files has broken syntax (prevents broken partial patches)
            if candidate_valid and edits_list:
                candidates.append(CandidatePatch(
                    candidate_id=cid,
                    strategy=strategy,
                    explanation=explanation,
                    edits=edits_list
                ))

        # Fallback if no valid candidate was returned
        if not candidates:
            print("[CandidateGenerator] No valid candidates returned by LLM. Generating deterministic mock candidates.", file=sys.stderr)
            return self._generate_mock_candidates(hotspot, file_contents, base_dir)

        return candidates

    def _strip_fences(self, code: str) -> str:
        """Strips markdown code fences (e.g. ```python ... ```) if wrapped in string."""
        trimmed = code.strip()
        fence_match = re.match(r"^```(?:python)?\s*\n?(.*?)\n?```$", trimmed, re.DOTALL)
        if fence_match:
            return fence_match.group(1).strip()
        return code

    def _validate_syntax(self, code: str) -> tuple[bool, Optional[str]]:
        """Validates that code string is valid Python AST."""
        try:
            ast.parse(code)
            return True, None
        except SyntaxError as e:
            return False, str(e)

    def _generate_mock_candidates(
        self,
        hotspot: Hotspot,
        file_contents: Optional[Dict[str, str]],
        base_dir: str
    ) -> List[CandidatePatch]:
        """
        Produces realistic, syntactically valid mock candidates for testing and offline demos.
        If source code is available (in file_contents or on disk), performs algorithmic transformations.
        """
        source = ""
        if file_contents:
            source = lookup_file_content(hotspot.file, file_contents) or ""

        # If not in file_contents, attempt reading from disk
        if not source:
            disk_path = os.path.join(base_dir, hotspot.file)
            if os.path.exists(disk_path):
                try:
                    with open(disk_path, "r", encoding="utf-8") as f:
                        source = f.read()
                except Exception:
                    pass

        norm_file = normalize_path(hotspot.file)

        # Candidate A: Set-based lookup optimization
        cand_a_content = source
        explanation_a = "Replaced linear list scanning inside iteration with O(1) set lookup."
        if source and " in [" in source:
            cand_a_content = re.sub(r"in\s+(\[[^\]]+\])", r"in set(\1)", source)
            explanation_a = "Converted list membership check inside loop to set lookup."

        # Candidate B: Memoization / lru_cache
        cand_b_content = source
        explanation_b = "Added functools.lru_cache memoization to eliminate repeated calculations."
        if source and f"def {hotspot.function}" in source:
            if "import functools" not in source and "from functools" not in source:
                cand_b_content = "import functools\n\n" + source
            cand_b_content = cand_b_content.replace(
                f"def {hotspot.function}(",
                f"@functools.lru_cache(maxsize=1024)\ndef {hotspot.function}("
            )

        candidates = [
            CandidatePatch(
                candidate_id="candidate_a",
                strategy="Set-based Membership Lookup",
                explanation=explanation_a,
                edits=[ModifiedFile(path=norm_file, new_content=cand_a_content or "pass\n")]
            ),
            CandidatePatch(
                candidate_id="candidate_b",
                strategy="Function Result Memoization",
                explanation=explanation_b,
                edits=[ModifiedFile(path=norm_file, new_content=cand_b_content or "pass\n")]
            )
        ]

        return candidates
