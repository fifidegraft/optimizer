"""Quick manual check for the scanner module - not the real CLI (that's Person 4's).

Run from the repo root:
    python scripts/verify_scanner.py demo
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from optimizer.scanner.project_scanner import ProjectScanner  # noqa: E402


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "demo"
    scanner = ProjectScanner(root).scan()
    summary = scanner.summary()

    print("Optimizer\n")
    print("Scanning repository...")
    print(f"{summary['files']} Python files found")
    print(f"{summary['functions']} functions indexed\n")

    if scanner.errors:
        print("Files skipped (syntax errors):")
        for err in scanner.errors:
            print(f"  - {err}")
        print()

    target = sys.argv[2] if len(sys.argv) > 2 else None
    if target:
        ctx = scanner.get_code_context(target)
        print(f"Related execution path for {ctx.hotspot_function}:")
        print(f"  {ctx.hotspot_function}")
        for dep in ctx.dependencies:
            print(f"    -> {dep}")
        print(f"\nAffected files ({len(ctx.related_files)}):")
        for f in ctx.related_files:
            print(f"  - {f}")


if __name__ == "__main__":
    main()
