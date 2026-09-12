"""A lightweight whole-project call graph, built from an already-scanned ProjectScanner.

Separate from get_code_context() (which is scoped to one hotspot's 1-3 files):
this gives a bird's-eye view of the whole repo, e.g. for a debug dump or a
"repo map" visualization if Person 4 wants one for the demo.
"""
from typing import Dict, List

from optimizer.scanner.project_scanner import ProjectScanner


def build_call_graph(scanner: ProjectScanner) -> Dict[str, List[str]]:
    """Returns {qualified_function_name: [qualified_names it calls]}.

    Calls that can't be resolved to a function we indexed (stdlib, third-party,
    dynamic dispatch, etc.) are silently dropped - this is a best-effort static
    graph, not a guarantee of completeness.
    """
    graph: Dict[str, List[str]] = {}
    for qual_name, node in scanner.functions.items():
        resolved: List[str] = []
        for call_name in node.calls:
            candidates = scanner._by_name.get(call_name)
            if candidates:
                resolved.append(candidates[0])
        graph[qual_name] = resolved
    return graph
