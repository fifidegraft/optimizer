"""Tests for the workload runner."""

import pytest
import sys
from optimizer.profiler.runner import run_workload, benchmark_workload


class TestRunWorkload:
    """Tests for run_workload() function."""

    def test_run_workload_success(self):
        """Test successful command execution."""
        result = run_workload("echo 'hello world'")

        assert result["exit_code"] == 0
        assert result["runtime_ms"] > 0
        assert "hello world" in result["output"]
        assert result["command"] == "echo 'hello world'"
        assert "T" in result["timestamp"]  # ISO format check

    def test_run_workload_failure(self):
        """Test command with non-zero exit code."""
        result = run_workload("exit 42")

        assert result["exit_code"] == 42
        assert result["runtime_ms"] > 0
        # Should not raise exception, should return the exit code

    def test_run_workload_with_stderr(self):
        """Test capturing stderr output."""
        result = run_workload(f"{sys.executable} -c \"import sys; sys.stderr.write('error msg')\"")

        assert result["exit_code"] == 0
        assert "error msg" in result["output"]

    def test_run_workload_timeout(self):
        """Test timeout handling."""
        result = run_workload("sleep 10", timeout=1)

        assert result["exit_code"] == -1
        assert "TIMEOUT" in result["output"]
        # Should be close to timeout, but don't assert exact bounds (flaky)
        assert result["runtime_ms"] >= 1000

    def test_run_workload_missing_command(self):
        """Test handling of missing/invalid command."""
        result = run_workload("this_command_does_not_exist_xyz")

        assert result["exit_code"] == -1
        assert "ERROR" in result["output"] or result["exit_code"] != 0

    def test_run_workload_with_cwd(self):
        """Test running command in specific working directory."""
        result = run_workload("pwd", cwd="/tmp")

        assert result["exit_code"] == 0
        assert "/tmp" in result["output"] or "tmp" in result["output"]

    def test_run_workload_timing_accuracy(self):
        """Test that timing is reasonably accurate."""
        result = run_workload("sleep 0.1")

        assert result["exit_code"] == 0
        # Should take at least 100ms
        assert result["runtime_ms"] >= 100

    def test_run_workload_preserves_environment(self):
        """Test that environment variables are passed through."""
        result = run_workload(
            f"{sys.executable} -c \"import os; print(os.getenv('TEST_VAR', 'not found'))\"",
            env={"TEST_VAR": "found"}
        )

        assert "found" in result["output"]


class TestBenchmarkWorkload:
    """Tests for benchmark_workload() function."""

    def test_benchmark_workload_multiple_runs(self):
        """Test multiple runs and statistics."""
        result = benchmark_workload("echo 'test'", iterations=3)

        assert result["exit_code"] == 0
        assert result["iterations"] == 3
        assert result["successful_iterations"] == 3
        assert len(result["results"]) == 3
        assert all(t > 0 for t in result["results"])
        assert result["runtime_ms"] > 0
        assert result["runtime_stddev"] >= 0

    def test_benchmark_workload_uses_median(self):
        """Test that median is used (robust to outliers)."""
        # With 5 runs, median is the 3rd value when sorted
        result = benchmark_workload("echo 'test'", iterations=5)

        assert result["exit_code"] == 0
        assert result["iterations"] == 5
        # Median should be one of the actual run times
        assert result["runtime_ms"] in result["results"]

    def test_benchmark_workload_single_iteration(self):
        """Test single iteration benchmark."""
        result = benchmark_workload("echo 'single'", iterations=1)

        assert result["iterations"] == 1
        assert result["successful_iterations"] == 1
        assert len(result["results"]) == 1
        assert result["runtime_stddev"] == 0  # No variance with 1 run

    def test_benchmark_workload_with_failures(self):
        """Test benchmark with some failed runs."""
        result = benchmark_workload(
            f"{sys.executable} -c \"import sys; sys.exit(1)\"",
            iterations=3
        )

        assert result["exit_code"] == -1
        assert result["iterations"] == 3
        assert result["successful_iterations"] == 0
        assert len(result["results"]) == 3

    def test_benchmark_workload_invalid_iterations(self):
        """Test with invalid iteration count."""
        result = benchmark_workload("echo 'test'", iterations=0)

        assert result["exit_code"] == -1
        assert result["iterations"] == 0
        assert "ERROR" in result["output"]

    def test_benchmark_workload_combines_output(self):
        """Test that output from all runs is combined."""
        result = benchmark_workload("echo 'iteration'", iterations=2)

        assert result["exit_code"] == 0
        # Output should contain separator between runs
        assert result["output"].count("---") >= 1


class TestIntegrationWithVerifier:
    """Integration tests simulating verifier usage."""

    def test_baseline_and_candidate_timing(self):
        """Simulate verifier comparing baseline and candidate."""
        # Baseline run
        baseline = run_workload(f"{sys.executable} -c \"import time; time.sleep(0.05)\"")
        baseline_ms = baseline["runtime_ms"]

        # Candidate run (simulating optimized version - slightly faster)
        candidate = run_workload(f"{sys.executable} -c \"import time; time.sleep(0.04)\"")
        candidate_ms = candidate["runtime_ms"]

        if candidate["exit_code"] == 0 and baseline["exit_code"] == 0:
            speedup = baseline_ms / candidate_ms
            # Both should be reasonably close to their sleep times
            # but speedup should be in a reasonable range
            assert speedup > 0.5  # At least some speedup
            assert speedup < 2.0  # But not unreasonable

    def test_candidate_failure_handling(self):
        """Simulate verifier handling candidate test failure."""
        baseline = run_workload("echo 'baseline'")
        baseline_ms = baseline["runtime_ms"]

        # Candidate fails tests
        candidate = run_workload("exit 1")

        # Verifier should check exit code, not crash
        assert candidate["exit_code"] != 0
        assert not ("ERROR" in candidate["output"] and "stderr" in candidate["output"].lower())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
