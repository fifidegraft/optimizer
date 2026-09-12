"""Command line entry point.

    python -m optimizer run demo --workload "python scripts/performance_scenario.py" --test "pytest -q"
    python -m optimizer inspect demo
    python -m optimizer recover demo

Argument parsing, exit codes and the confirmation prompt live here; the loop
itself is in `optimizer.pipeline`.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path

from optimizer import pipeline
from optimizer.term import Console
from optimizer.verifier import recover_latest

EXIT_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="optimizer",
        description="Autonomous performance engineer for Python codebases. AI proposes. The runtime decides.",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("path", nargs="?", default=".", help="repository to optimize (default: .)")
        p.add_argument("--no-color", action="store_true", help="plain output (NO_COLOR=1 does the same)")
        p.add_argument("--json", action="store_true", help="machine-readable result on stdout, progress on stderr")
        p.add_argument("--timeout", type=int, default=300, metavar="SEC", help="per-command timeout (default 300)")

    run = sub.add_parser("run", help="profile, optimize, verify, apply")
    common(run)
    run.add_argument("--workload", required=True, metavar="CMD", help="command that exercises the app, e.g. 'python scripts/perf.py'")
    run.add_argument("--test", metavar="CMD", help="test command, e.g. 'pytest -q'; candidates that fail it are rejected")
    run.add_argument("--passes", type=int, default=1, metavar="N", help="bottlenecks to fix in sequence (default 1)")
    run.add_argument("--hotspot", action="append", default=[], metavar="NAME", help="target function; repeat for one per pass")
    run.add_argument("-y", "--yes", action="store_true", help="apply the winner without asking")
    run.add_argument("--min-improvement", type=float, default=0.05, metavar="FRAC", help="required speedup fraction (default 0.05)")
    run.add_argument("--iterations", type=int, default=1, metavar="N", help="workload runs per measurement (default 1)")

    inspect = sub.add_parser("inspect", help="analyze only: scan, profile, show hotspots")
    common(inspect)
    inspect.add_argument("--workload", metavar="CMD", help="command to profile (needs the profiler's ranking)")
    inspect.add_argument("--hotspot", action="append", default=[], metavar="NAME", help="show context for this function")

    recover = sub.add_parser("recover", help="restore the newest backup left by an interrupted run")
    common(recover)
    return parser


def _console(args: argparse.Namespace) -> Console:
    stream = sys.stderr if args.json else sys.stdout
    return Console(stream=stream, color=False if args.no_color else None)


def _confirm() -> bool:
    try:
        answer = input("Apply changes? [Y/n] ").strip().lower()
    except EOFError:
        return False
    return answer in ("", "y", "yes")


def _config(args: argparse.Namespace) -> pipeline.RunConfig:
    return pipeline.RunConfig(
        path=args.path,
        workload=getattr(args, "workload", None),
        test=getattr(args, "test", None),
        passes=getattr(args, "passes", 1),
        hotspots=tuple(getattr(args, "hotspot", [])),
        yes=getattr(args, "yes", False),
        min_improvement=getattr(args, "min_improvement", 0.05),
        timeout=args.timeout,
        iterations=getattr(args, "iterations", 1),
    )


def _emit_json(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, indent=2, default=str) + "\n")
    sys.stdout.flush()


def cmd_run(args: argparse.Namespace) -> int:
    console = _console(args)
    config = _config(args)
    if args.json:
        # Teammates' modules print progress to stdout; keep stdout clean for the payload.
        confirm = _decline_in_json
        with contextlib.redirect_stdout(sys.stderr):
            result = pipeline.run(config, console, confirm)
        _emit_json(result.to_json())
    else:
        result = pipeline.run(config, console, _confirm)
    return result.exit_code


def _decline_in_json() -> bool:
    sys.stderr.write("--json without --yes: not applying (pass --yes to apply).\n")
    return False


def cmd_inspect(args: argparse.Namespace) -> int:
    console = _console(args)
    config = _config(args)
    if args.json:
        with contextlib.redirect_stdout(sys.stderr):
            info = pipeline.inspect(config, console)
        _emit_json(info)
    else:
        info = pipeline.inspect(config, console)
    return info["exit_code"]


def cmd_recover(args: argparse.Namespace) -> int:
    console = _console(args)
    root = Path(args.path).resolve()
    if not root.is_dir():
        console.error(f"Not a directory: {args.path}")
        return pipeline.EXIT_FAILED
    snap = recover_latest(root)
    if snap is None:
        console.print("Nothing to recover: no backups found.")
        payload = {"restored": []}
    else:
        files = [f["path"] for f in snap["files"]]
        console.ok(f"Restored {len(files)} file(s) from backup {snap['id']}:")
        for f in files:
            console.print(f"- {f}")
        payload = {"restored": files, "backup": snap["id"]}
    if args.json:
        _emit_json(payload)
    return pipeline.EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = {"run": cmd_run, "inspect": cmd_inspect, "recover": cmd_recover}[args.command]
    try:
        return handler(args)
    except KeyboardInterrupt:
        sys.stderr.write("\nInterrupted. If a candidate was mid-trial, run `optimizer recover PATH`.\n")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
