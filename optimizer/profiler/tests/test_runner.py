"""Tests for the workload runner."""

import pytest
import time
from runner import run_workload, benchmark_workload


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
        result = run_workload("python -c \"import sys; sys.stderr.write('error msg')\"")

        assert result["exit_code"] == 0
        assert "error msg" in result["output"]

    def test_run_workload_timeout(self):
        """Test timeout handling."""
        result = run_workload("sleep 10", timeout=1)

        assert result["exit_code"] == -1
        assert "TIMEOUT" in result["output"]
        assert result["runtime_ms"] >= 1000  # Should be close to timeout

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
        # Should take at least 100ms, but not drastically more
        assert result["runtime_ms"] >= 100
        assert result["runtime_ms"] < 500  # Should be within reason

    def test_run_workload_preserves_environment(self):
        """Test that environment variables are passed through."""
        # Set a custom env var and check it's accessible
        result = run_workload(
            "python -c \"import os; print(os.getenv('TEST_VAR', 'not found'))\"",
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

    def test_benchmark_workload_mean_calculation(self):
        """Test that mean is calculated correctly."""
        # Use a command with known timing
        result = benchmark_workload("sleep 0.05", iterations=3)

        assert result["exit_code"] == 0
        # Mean should be around 50ms (each run is 50ms)
        assert result["runtime_ms"] >= 45
        assert result["runtime_ms"] < 200

    def test_benchmark_workload_single_iteration(self):
        """Test single iteration benchmark."""
        result = benchmark_workload("echo 'single'", iterations=1)

        assert result["iterations"] == 1
        assert result["successful_iterations"] == 1
        assert len(result["results"]) == 1
        assert result["runtime_stddev"] == 0  # No variance with 1 run

    def test_benchmark_workload_with_failures(self):
        """Test benchmark with some failed runs."""
        # Command that fails
        result = benchmark_workload("python -c \"import sys; sys.exit(1)\"", iterations=3)

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
        # Output should contain both runs
        assert result["output"].count("---") >= 1  # Separator between runs


class TestIntegrationWithVerifier:
    """Integration tests simulating verifier usage."""

    def test_baseline_and_candidate_timing(self):
        """Simulate verifier comparing baseline and candidate."""
        # Baseline run
        baseline = run_workload("python -c \"import time; time.sleep(0.05)\"")
        baseline_ms = baseline["runtime_ms"]

        # Candidate run (simulating optimized version - slightly faster)
        candidate = run_workload("python -c \"import time; time.sleep(0.04)\"")
        candidate_ms = candidate["runtime_ms"]

        if candidate["exit_code"] == 0 and baseline["exit_code"] == 0:
            speedup = baseline_ms / candidate_ms
            assert speedup > 1.0  # Candidate should be faster
            assert 0.8 < speedup < 1.3  # Reasonable speedup range for 5ms difference

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
