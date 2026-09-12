"""Workload runner — execute benchmark/test commands and measure execution time."""

import subprocess
import time
from datetime import datetime, timezone
from typing import Optional


def run_workload(
    command: str,
    cwd: str = ".",
    timeout: int = 300,
    env: Optional[dict] = None,
) -> dict:
    """
    Run a single workload command and time its execution.

    This is the core measurement function. Both baseline profiling and candidate
    benchmarking use this to get accurate timing. Non-zero exit codes are returned
    as data, not raised as exceptions, so the caller (verifier) can handle failures
    gracefully.

    Args:
        command (str): Shell command to execute.
            Example: "python benchmark.py" or "pytest -q"
        cwd (str): Working directory to run from. Default: "."
        timeout (int): Maximum execution time in seconds. Default: 300 (5 minutes)
        env (dict, optional): Environment variables to pass to subprocess.
            If None, inherits parent's environment.

    Returns:
        dict: Result object with fields:
            - runtime_ms (float): Elapsed time in milliseconds
            - exit_code (int): Process exit code (0 = success, non-zero = failure)
            - command (str): The command that was run
            - output (str): Captured stdout + stderr combined
            - timestamp (str): ISO 8601 timestamp when run started

    Example:
        >>> result = run_workload("python benchmark.py", cwd="demo/")
        >>> print(result)
        {
            'runtime_ms': 425.7,
            'exit_code': 0,
            'command': 'python benchmark.py',
            'output': '...',
            'timestamp': '2026-09-12T14:22:33.123456Z'
        }

        >>> result = run_workload("exit 1")
        >>> result['exit_code']
        1
        >>> # No exception raised; caller decides what to do with exit code
    """
    start_time = time.time()
    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        elapsed_ms = (time.time() - start_time) * 1000

        return {
            "runtime_ms": elapsed_ms,
            "exit_code": result.returncode,
            "command": command,
            "output": result.stdout + result.stderr,
            "timestamp": timestamp,
        }

    except subprocess.TimeoutExpired as e:
        elapsed_ms = (time.time() - start_time) * 1000
        # Capture any partial output before timeout
        partial_output = ""
        if e.stdout:
            partial_output += e.stdout
        if e.stderr:
            partial_output += e.stderr

        return {
            "runtime_ms": elapsed_ms,
            "exit_code": -1,
            "command": command,
            "output": f"TIMEOUT: command exceeded {timeout} seconds\n{partial_output}",
            "timestamp": timestamp,
        }

    except FileNotFoundError as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return {
            "runtime_ms": elapsed_ms,
            "exit_code": -1,
            "command": command,
            "output": f"ERROR: command not found: {str(e)}",
            "timestamp": timestamp,
        }

    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return {
            "runtime_ms": elapsed_ms,
            "exit_code": -1,
            "command": command,
            "output": f"ERROR: {type(e).__name__}: {str(e)}",
            "timestamp": timestamp,
        }


def benchmark_workload(
    command: str,
    cwd: str = ".",
    iterations: int = 3,
    timeout: int = 300,
) -> dict:
    """
    Run a workload multiple times for stable benchmark results.

    Runs the command N times and computes mean and standard deviation.
    Useful for getting reliable measurements when workload has small variance.

    Args:
        command (str): Command to execute
        cwd (str): Working directory
        iterations (int): Number of times to run. Default: 3
        timeout (int): Per-run timeout in seconds

    Returns:
        dict: Benchmark result with fields:
            - runtime_ms (float): Mean execution time across all iterations
            - runtime_stddev (float): Standard deviation of runtimes
            - iterations (int): Number of successful iterations
            - exit_code (int): 0 if all succeeded, -1 if any failed
            - results (list): Individual runtime_ms for each iteration
            - output (str): Concatenated output from all runs
            - timestamp (str): When first run started

    Example:
        >>> result = benchmark_workload("python bench.py", iterations=5)
        >>> result['runtime_ms']  # Mean time
        425.3
        >>> result['runtime_stddev']  # Variation
        12.5
    """
    if iterations < 1:
        return {
            "runtime_ms": 0,
            "runtime_stddev": 0,
            "iterations": 0,
            "exit_code": -1,
            "results": [],
            "output": "ERROR: iterations must be >= 1",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    results_list = []
    outputs = []
    failed_count = 0

    for _ in range(iterations):
        result = run_workload(command, cwd=cwd, timeout=timeout)
        results_list.append(result["runtime_ms"])
        outputs.append(result["output"])

        if result["exit_code"] != 0:
            failed_count += 1

    # Compute statistics
    if results_list:
        mean_ms = sum(results_list) / len(results_list)

        # Compute standard deviation
        if len(results_list) > 1:
            variance = sum((x - mean_ms) ** 2 for x in results_list) / len(results_list)
            stddev_ms = variance ** 0.5
        else:
            stddev_ms = 0.0
    else:
        mean_ms = 0.0
        stddev_ms = 0.0

    exit_code = 0 if failed_count == 0 else -1

    return {
        "runtime_ms": mean_ms,
        "runtime_stddev": stddev_ms,
        "iterations": iterations,
        "successful_iterations": iterations - failed_count,
        "exit_code": exit_code,
        "results": results_list,
        "output": "\n---\n".join(outputs),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
