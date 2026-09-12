"""Repository-wide scanning and hotspot context building.

Owned by Person 1 (Repository Intelligence). This is the module Person 2
(profiler) and Person 3 (agent) both import.

Path contract (agreed with the team): every file_path this module hands
out - on FunctionNode, on CodeContext, in related_files - is relative to
the project root, using POSIX separators ("services/users.py"), never
absolute. That's the shape everyone else writes/backs up files by.
"""
import ast
from collections import deque
from pathlib import Path
from typing import Dict, List, Optional, Set

from optimizer.models.schemas import CodeContext, FunctionNode
from optimizer.scanner.ast_parser import ASTParser

DEFAULT_IGNORE_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules",
    "build", "dist", ".pytest_cache", ".mypy_cache",
    ".optimizer",  # verifier's backup/.py copies live under <project>/.optimizer/backups/
}


class ProjectScanner:
    def __init__(self, root_dir: str, ignore_dirs: Optional[Set[str]] = None):
        self.root_dir = Path(root_dir).resolve()
        self.ignore_dirs = ignore_dirs or set(DEFAULT_IGNORE_DIRS)

        self.functions: Dict[str, FunctionNode] = {}      # qualified_name -> node
        self._by_name: Dict[str, List[str]] = {}           # bare name -> [qualified_names]
        self.file_imports: Dict[str, Dict[str, str]] = {}  # rel_path (posix) -> {alias: import path}
        self.errors: List[str] = []

    def scan(self) -> "ProjectScanner":
        """Discovers and parses every .py file under root_dir. Returns self for chaining."""
        for abs_path in sorted(self.root_dir.rglob("*.py")):
            if any(part in self.ignore_dirs for part in abs_path.parts):
                continue

            rel_path = abs_path.relative_to(self.root_dir)
            rel_posix = rel_path.as_posix()
            module_name = ".".join(rel_path.with_suffix("").parts)

            try:
                content = abs_path.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=rel_posix)
            except (SyntaxError, UnicodeDecodeError) as exc:
                self.errors.append(f"{rel_posix}: {exc}")
                continue

            # ASTParser stores whatever file_path string it's given directly onto
            # each FunctionNode, so we hand it the relative posix path, not abs_path.
            parser = ASTParser(rel_posix, module_prefix=module_name)
            parser.visit(tree)

            self.functions.update(parser.functions)
            self.file_imports[rel_posix] = parser.imports

            for qual_name, node in parser.functions.items():
                self._by_name.setdefault(node.name, []).append(qual_name)

        return self

    def summary(self) -> Dict[str, int]:
        files = {node.file_path for node in self.functions.values()}
        return {"files": len(files), "functions": len(self.functions)}

    def find_function(self, name_or_qualified: str) -> Optional[FunctionNode]:
        """Look up a function by exact qualified name, bare name, or suffix match."""
        if name_or_qualified in self.functions:
            return self.functions[name_or_qualified]

        candidates = self._by_name.get(name_or_qualified)
        if candidates:
            return self.functions[candidates[0]]

        for qual_name, node in self.functions.items():
            if qual_name.endswith(f".{name_or_qualified}") or node.name == name_or_qualified:
                return node

        return None

    def _to_relative_posix(self, file_path: str) -> str:
        """Normalizes any path we're handed (absolute, relative, Windows-style
        from a teammate's machine, whatever) into our root-relative posix form."""
        p = Path(file_path)
        if p.is_absolute():
            try:
                return p.resolve().relative_to(self.root_dir).as_posix()
            except ValueError:
                return p.as_posix()  # outside root_dir; return as-is rather than guess
        return p.as_posix()

    def find_function_by_location(self, file_path: str, line_number: int) -> Optional[FunctionNode]:
        """Resolve a function from (filename, lineno) - the shape cProfile/pstats reports.
        Accepts either an absolute path (what cProfile usually gives you) or a
        relative one; normalizes to our root-relative convention either way."""
        target = self._to_relative_posix(file_path)
        for node in self.functions.values():
            if node.file_path == target and node.line_start <= line_number <= node.line_end:
                return node
        return None

    def _resolve_call(self, caller: FunctionNode, called_name: str) -> List[FunctionNode]:
        """Turn a bare call name into candidate FunctionNodes.

        Prefers a match in a different file than the caller, since same-file
        calls are usually less interesting for cross-file hotspot tracing and
        duplicate names (e.g. two get() helpers) are more likely module-local.
        """
        candidates = [self.functions[q] for q in self._by_name.get(called_name, [])]
        if not candidates:
            return []
        cross_file = [c for c in candidates if c.file_path != caller.file_path]
        return cross_file or candidates

    def get_code_context(
        self,
        qualified_function_name: str,
        padding_lines: int = 3,
        max_related_files: int = 3,
        max_depth: int = 3,
    ) -> CodeContext:
        """Builds the context package handed to Person 3's LLM prompt.

        Walks the hotspot's call chain breadth-first (not just its direct
        calls) so multi-hop patterns like
            recommendations.generate_feed() -> users.get_user() -> database.find_user()
        surface even though generate_feed only calls get_user directly.
        Stops once max_related_files distinct files have been touched, per
        the brief's "1-3 related files" scope rule.

        related_files is ordered with the hotspot's own file first, then
        related files in the order they were discovered.
        """
        target_node = self.find_function(qualified_function_name)
        if not target_node:
            raise ValueError(f"Function '{qualified_function_name}' not found in AST index.")

        related_files: List[str] = [target_node.file_path]
        seen_files: Set[str] = {target_node.file_path}
        related_snippets: Dict[str, str] = {}
        dependencies: List[str] = []

        visited = {target_node.qualified_name}
        queue = deque([(target_node, 0)])

        while queue and len(seen_files) < max_related_files:
            current, depth = queue.popleft()
            if depth >= max_depth:
                continue

            for call_name in current.calls:
                if len(seen_files) >= max_related_files:
                    break

                matches = self._resolve_call(current, call_name)
                if not matches:
                    continue
                match = matches[0]  # one resolved hop per call name keeps the walk narrow

                if match.qualified_name in visited:
                    continue
                visited.add(match.qualified_name)
                dependencies.append(match.qualified_name)

                if match.file_path not in seen_files:
                    if len(seen_files) >= max_related_files:
                        continue
                    seen_files.add(match.file_path)
                    related_files.append(match.file_path)

                related_snippets[match.qualified_name] = self._read_snippet(match)
                queue.append((match, depth + 1))

        return CodeContext(
            hotspot_function=target_node.qualified_name,
            file_path=target_node.file_path,
            line_start=target_node.line_start,
            line_end=target_node.line_end,
            code_snippet=self._read_snippet(target_node, padding_lines),
            dependencies=dependencies or target_node.calls,
            related_files=related_files,
            related_code_snippets=related_snippets,
        )

    def _read_snippet(self, node: FunctionNode, padding_lines: int = 0) -> str:
        # node.file_path is root-relative; resolve against root_dir to actually read it.
        abs_path = self.root_dir / node.file_path
        lines = abs_path.read_text(encoding="utf-8").splitlines()
        start = max(0, node.line_start - 1 - padding_lines)
        end = min(len(lines), node.line_end + padding_lines)
        return "\n".join(lines[start:end])
