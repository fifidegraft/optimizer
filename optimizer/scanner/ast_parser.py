"""Parses a single Python file's AST into FunctionNode objects.

Owned by Person 1 (Repository Intelligence). This module never touches
the filesystem beyond the one file it's given - ProjectScanner does the
directory walking.
"""
import ast
from typing import Dict, List

from optimizer.models.schemas import FunctionNode


class CallVisitor(ast.NodeVisitor):
    """Collects the names of things called inside a single function body."""

    def __init__(self):
        self.calls: List[str] = []

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name):
            self.calls.append(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            self.calls.append(node.func.attr)
        self.generic_visit(node)


class ASTParser(ast.NodeVisitor):
    """Walks one file's AST and indexes every function/method it defines.

    Class methods are qualified as Module.ClassName.method_name so they
    don't collide with a module-level function of the same name.
    """

    def __init__(self, file_path: str, module_prefix: str = ""):
        # file_path is the project-root-relative, POSIX-separated path
        # (e.g. "services/users.py") - stored as-is onto every FunctionNode.
        self.file_path = file_path
        self.module_prefix = module_prefix
        self.current_scope: List[str] = []
        self.functions: Dict[str, FunctionNode] = {}
        self.imports: Dict[str, str] = {}  # local alias -> fully qualified import path

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            name = alias.asname or alias.name
            self.imports[name] = alias.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        mod = node.module or ""
        for alias in node.names:
            name = alias.asname or alias.name
            self.imports[name] = f"{mod}.{alias.name}" if mod else alias.name
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        # Push the class name so methods get qualified as Module.Class.method
        # instead of colliding with module-level functions of the same name.
        self.current_scope.append(node.name)
        self.generic_visit(node)
        self.current_scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._record_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._record_function(node)

    def _record_function(self, node) -> None:
        scope_str = ".".join(self.current_scope + [node.name])
        qual_name = f"{self.module_prefix}.{scope_str}" if self.module_prefix else scope_str

        call_visitor = CallVisitor()
        call_visitor.visit(node)

        self.functions[qual_name] = FunctionNode(
            name=node.name,
            qualified_name=qual_name,
            file_path=str(self.file_path),
            line_start=node.lineno,
            line_end=getattr(node, "end_lineno", node.lineno),
            calls=call_visitor.calls,
        )

        # Recurse for nested/inner functions, qualified under this function's scope.
        self.current_scope.append(node.name)
        self.generic_visit(node)
        self.current_scope.pop()
