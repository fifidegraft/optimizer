"""Profiling integration — run workloads under cProfile and identify hotspots."""

import cProfile
import pstats
import subprocess
import sys
import time
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional


def profile_workload(
    command: str,
    cwd: str = ".",
    timeout: int = 300,
    limit: int = 20,
) -> dict:
    """
    Run command under cProfile and rank the hottest project functions.

    Executes a command with cProfile instrumentation, identifies the hottest
    functions in the project code (excluding stdlib/site-packages), ranks them
    by impact (self_time * calls or similar scoring), and returns structured data.

    The CLI will use the scanner to fill in qualified_name, dependencies, and
    related_files. This function only needs to identify and rank hotspots by
    execution time.

    Args:
        command (str): Shell command to profile (e.g., "python benchmark.py")
        cwd (str): Working directory. Default: "."
        timeout (int): Maximum execution time in seconds. Default: 300
        limit (int): Maximum number of hotspots to return. Default: 20

    Returns:
        dict: Profiling result with fields:
            - exit_code (int): 0 if success, non-zero if command failed, -1 if system error
            - output (str): Captured stdout + stderr from the command
            - hotspots (list): Ranked list of hotspot dicts, best first. Each has:
                * function (str): Function name
                * file (str): Absolute file path (as cProfile reports it)
                * line (int): Line number where function defined
                * calls (int): Number of times called
                * self_time (float): Time in function only (seconds)
                * cumulative_time (float): Time in function + callees (seconds)
                * runtime_percent (float): Percentage of total runtime (0-100)

    Design notes:
        - Excludes stdlib and site-packages frames
        - Ranks by score (self_time * calls) to avoid cumulative_time bias
          (cumulative_time puts main() at top)
        - File paths are absolute (scanner normalizes them)
        - Never raises; returns exit_code -1 on system errors
        - cProfile overhead means timing differs from baseline (CLI measures
          baseline separately with benchmark_workload)

    Example:
        >>> result = profile_workload("python benchmark.py", cwd="demo/")
        >>> result["exit_code"]
        0
        >>> result["hotspots"][0]
        {
            'function': 'generate_feed',
            'file': '/path/to/services/recommendations.py',
            'line': 41,
            'calls': 10420,
            'self_time': 0.62,
            'cumulative_time': 1.82,
            'runtime_percent': 62.0
        }
    """
    try:
        # Try to inject cProfile using Python's -m cProfile flag
        # For "python script.py", transform to "python -m cProfile script.py"
        # For other commands, run with cProfile wrapper
        profile_command = _wrap_with_cprofile(command)

        # Run the command with cProfile
        result = subprocess.run(
            profile_command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout + result.stderr
        exit_code = result.returncode

    except subprocess.TimeoutExpired:
        return {
            "exit_code": -1,
            "output": f"TIMEOUT: command exceeded {timeout} seconds",
            "hotspots": [],
        }

    except Exception as e:
        return {
            "exit_code": -1,
            "output": f"ERROR: {type(e).__name__}: {str(e)}",
            "hotspots": [],
        }

    # If command failed, don't try to parse stats
    if exit_code != 0:
        return {
            "exit_code": exit_code,
            "output": output,
            "hotspots": [],
        }

    # Parse cProfile output from stdout
    try:
        hotspots = _parse_cprofile_output(output, limit=limit)
    except Exception as e:
        # If parsing fails, return empty hotspots but don't fail the whole result
        return {
            "exit_code": exit_code,
            "output": output,
            "hotspots": [],
        }

    return {
        "exit_code": exit_code,
        "output": output,
        "hotspots": hotspots,
    }


def _wrap_with_cprofile(command: str) -> str:
    """
    Wrap a shell command to run under cProfile.

    For Python file execution, injects -m cProfile.
    For inline code (-c), uses python's built-in profiling via -m pstats.
    For other commands, returns as-is (complex to profile subprocesses).

    Args:
        command: Original shell command

    Returns:
        Command with cProfile instrumentation (or original if can't wrap)
    """
    # Check if it's a Python command
    if command.startswith("python ") or command.startswith("python3 "):
        parts = command.split(None, 1)
        python_exe = parts[0]
        rest = parts[1] if len(parts) > 1 else ""

        # If it's a file (not -c), use -m cProfile
        if rest and not rest.startswith("-c"):
            return f"{python_exe} -m cProfile {rest}"
        elif rest and rest.startswith("-c"):
            # For -c, we still use python directly but parse the output
            # Note: -m cProfile doesn't support -c directly
            return command
        else:
            return command
    else:
        # For non-Python commands, return as-is
        return command


def _parse_cprofile_output(output: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Parse cProfile output and extract hotspots.

    Parses the text output from `python -m cProfile script.py` and extracts
    timing information for each function.

    Args:
        output: Combined stdout+stderr from cProfile run
        limit: Maximum number of hotspots to return

    Returns:
        List of hotspot dicts, ranked by impact (best first)
    """
    hotspots = []
    lines = output.split("\n")

    # cProfile output format (text mode, default):
    # ncalls  tottime  percall  cumtime  percall filename:lineno(function)
    # Example:
    # 100    0.050    0.000    0.150    0.001 /path/to/file.py:42(my_function)

    total_time = 0.0

    for line in lines:
        line = line.strip()

        # Skip empty lines and headers
        if not line or "ncalls" in line or "function calls" in line:
            continue

        # Try to parse as cProfile stat line
        parts = line.split()
        if len(parts) < 6:
            continue

        try:
            # Parse: ncalls tottime percall cumtime percall filename:lineno(function)
            ncalls_str = parts[0]
            tottime_str = parts[1]
            cumtime_str = parts[3]

            # Handle recursive calls (e.g., "100/50" for ncalls)
            if "/" in ncalls_str:
                ncalls_str = ncalls_str.split("/")[1]  # Take non-recursive part

            ncalls = int(ncalls_str)
            tottime = float(tottime_str)
            cumtime = float(cumtime_str)

            # Parse filename:lineno(function)
            # Last part is usually filename:lineno(function)
            func_info = parts[-1]

            if ":" not in func_info or "(" not in func_info:
                continue

            # Split on last colon
            file_part, rest = func_info.rsplit(":", 1)
            file_path = file_part

            # Extract line number and function name
            # Format: lineno(function)
            if "(" in rest and ")" in rest:
                line_part, func_part = rest.split("(", 1)
                func_name = func_part.rstrip(")")
                try:
                    line_no = int(line_part)
                except ValueError:
                    continue
            else:
                continue

            # Skip internal/stdlib
            if _should_skip_file(file_path):
                continue

            # Calculate metrics
            if ncalls > 0:
                score = tottime * ncalls  # Rank by self_time * calls
            else:
                score = tottime

            # Store total time for percentage calculation
            total_time = max(total_time, cumtime)

            hotspots.append({
                "function": func_name,
                "file": file_path,
                "line": line_no,
                "calls": ncalls,
                "self_time": tottime,
                "cumulative_time": cumtime,
                "runtime_percent": 0.0,  # Will calculate below
                "_score": score,
            })

        except (ValueError, IndexError):
            continue

    # Calculate runtime percentages and sort by score
    if total_time > 0:
        for hotspot in hotspots:
            hotspot["runtime_percent"] = (hotspot["cumulative_time"] / total_time) * 100

    hotspots.sort(key=lambda h: h["_score"], reverse=True)

    # Remove internal score field and limit results
    result = []
    for hotspot in hotspots[:limit]:
        del hotspot["_score"]
        result.append(hotspot)

    return result


def _extract_hotspots(stats: pstats.Stats, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Extract and rank hotspots from cProfile statistics.

    Filters out stdlib and site-packages, ranks by score (self_time * calls),
    and returns structured hotspot data.

    Args:
        stats: pstats.Stats object from cProfile
        limit: Maximum number of hotspots to return

    Returns:
        List of hotspot dicts, ranked by impact (best first)
    """
    hotspots = []
    total_time = stats.total_tt  # Total time spent in profiled code

    # Get all function stats
    for func_key, func_stats in stats.stats.items():
        file_path, line_number, func_name = func_key

        # Skip stdlib and site-packages
        if _should_skip_file(file_path):
            continue

        # Extract timing data
        # func_stats is: (primitives, non_primitives, total_time, cumulative_time, callers_dict)
        # We need: (calls, total_time, cumulative_time)
        primitives = func_stats[0]  # Direct calls (not recursive)
        total_func_time = func_stats[2]
        cumulative_func_time = func_stats[3]

        if total_time > 0:
            runtime_percent = (cumulative_func_time / total_time) * 100
        else:
            runtime_percent = 0.0

        # Score for ranking: self_time * calls
        # This identifies functions that both take time AND are called frequently
        score = total_func_time * primitives if primitives > 0 else total_func_time

        hotspots.append({
            "function": func_name,
            "file": file_path,
            "line": line_number,
            "calls": primitives,
            "self_time": total_func_time,
            "cumulative_time": cumulative_func_time,
            "runtime_percent": runtime_percent,
            "_score": score,  # Internal ranking field
        })

    # Sort by score (self_time * calls), descending
    hotspots.sort(key=lambda h: h["_score"], reverse=True)

    # Take top N and remove internal ranking field
    result = []
    for hotspot in hotspots[:limit]:
        del hotspot["_score"]
        result.append(hotspot)

    return result


def _should_skip_file(file_path: str) -> bool:
    """
    Determine if a file should be excluded from profiling results.

    Skips:
    - Python standard library files
    - site-packages and dist-packages
    - setuptools, pip, pytest, etc.
    - cProfile's own frames

    Args:
        file_path: Absolute path to a Python source file

    Returns:
        True if the file should be skipped, False otherwise
    """
    # Skip internal Python/cProfile files
    if "<" in file_path and ">" in file_path:
        # Internal frames like <frozen importlib>
        return True

    # Normalize path for comparison
    normalized = file_path.replace("\\", "/").lower()

    # Skip site-packages and dist-packages
    if "site-packages" in normalized or "dist-packages" in normalized:
        return True

    # Skip Python standard library
    # Check for common stdlib locations
    if "lib/python" in normalized or "lib64/python" in normalized:
        # But allow if it's in the project (not a system path)
        # This is a heuristic: if it's in /usr, /opt, or similar, skip it
        if any(prefix in normalized for prefix in ["/usr/", "/opt/", "/System/"]):
            return True

    # Skip setuptools, pip, pytest, and similar
    skip_patterns = [
        "setuptools",
        "pip",
        "pytest",
        "distutils",
        "importlib",
        "pkgutil",
        "threading",
        "subprocess",
    ]
    for pattern in skip_patterns:
        if f"/{pattern}" in normalized or f"\\{pattern}" in normalized:
            return True

    return False
