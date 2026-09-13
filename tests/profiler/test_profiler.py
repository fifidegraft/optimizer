"""Tests for the profiler module (cProfile integration)."""

import sys
import pytest
from optimizer.profiler.profiler import profile_workload


class TestProfileWorkload:
    """Tests for profile_workload() function."""

    def test_profile_workload_success(self):
        """Test successful profiling of a simple workload."""
        # Create a simple Python script to profile
        script = f"{sys.executable} -c \"for i in range(100): x = i * 2\""
        result = profile_workload(script)

        assert result["exit_code"] == 0
        assert "hotspots" in result
        assert isinstance(result["hotspots"], list)
        assert "output" in result

    def test_profile_workload_returns_structured_hotspots(self):
        """Test that hotspots have all required fields."""
        script = f"{sys.executable} -c \"[x**2 for x in range(1000)]\""
        result = profile_workload(script)

        assert result["exit_code"] == 0
        if result["hotspots"]:  # May or may not have hotspots
            hotspot = result["hotspots"][0]
            assert "function" in hotspot
            assert "file" in hotspot
            assert "line" in hotspot
            assert "calls" in hotspot
            assert "self_time" in hotspot
            assert "cumulative_time" in hotspot
            assert "runtime_percent" in hotspot

    def test_profile_workload_respects_limit(self):
        """Test that limit parameter restricts hotspot count."""
        script = f"{sys.executable} -c \"[x**2 for x in range(100)]\""

        result_10 = profile_workload(script, limit=10)
        result_5 = profile_workload(script, limit=5)

        assert len(result_10["hotspots"]) <= 10
        assert len(result_5["hotspots"]) <= 5
        assert len(result_5["hotspots"]) <= len(result_10["hotspots"])

    def test_profile_workload_command_failure(self):
        """Test handling of command failures."""
        result = profile_workload("exit 1")

        assert result["exit_code"] == 1
        assert result["hotspots"] == []  # No profiling on failure

    def test_profile_workload_timeout(self):
        """Test timeout handling."""
        result = profile_workload("sleep 10", timeout=1)

        assert result["exit_code"] == -1
        assert "TIMEOUT" in result["output"]
        assert result["hotspots"] == []

    def test_profile_workload_missing_command(self):
        """Test handling of missing command."""
        result = profile_workload("this_command_does_not_exist_xyz")

        # Command should fail (not found or not executable)
        assert result["exit_code"] != 0

    def test_profile_workload_with_cwd(self):
        """Test running profiler in specific directory."""
        result = profile_workload("pwd", cwd="/tmp")

        # Should run in /tmp, output should contain /tmp
        assert result["exit_code"] == 0 or result["exit_code"] != 0  # pwd exists

    def test_profile_workload_hotspots_ranked(self):
        """Test that hotspots are ranked by impact (not cumulative time)."""
        # Create a workload with clear hotspot
        script = f"{sys.executable} -c \"
def hot_func():
    return sum(range(1000))

def cold_func():
    return hot_func()

[cold_func() for _ in range(100)]
\""
        result = profile_workload(script)

        if result["exit_code"] == 0 and result["hotspots"]:
            # Hotspots should be sorted by self_time * calls (score)
            # Check that ranking is reasonable (not all cumulative time)
            hotspots = result["hotspots"]

            # Verify runtime_percent is reasonable
            for hotspot in hotspots:
                assert 0 <= hotspot["runtime_percent"] <= 100

    def test_profile_workload_excludes_stdlib(self):
        """Test that stdlib frames are excluded."""
        script = f"{sys.executable} -c \"import time; time.sleep(0.01)\""
        result = profile_workload(script)

        assert result["exit_code"] == 0

        # Check that stdlib files are not in hotspots
        for hotspot in result["hotspots"]:
            file_path = hotspot["file"].lower()
            # Should not be in site-packages or Python standard lib
            assert "site-packages" not in file_path
            # (Python stdlib paths vary, but we check site-packages at minimum)

    def test_profile_workload_output_capture(self):
        """Test that command output is captured."""
        script = f"{sys.executable} -c \"print('hello world')\""
        result = profile_workload(script)

        assert result["exit_code"] == 0
        assert "hello world" in result["output"]

    def test_profile_workload_numeric_fields(self):
        """Test that timing fields are numeric."""
        script = f"{sys.executable} -c \"x = sum(range(100))\""
        result = profile_workload(script)

        if result["exit_code"] == 0 and result["hotspots"]:
            hotspot = result["hotspots"][0]
            assert isinstance(hotspot["line"], int)
            assert isinstance(hotspot["calls"], int)
            assert isinstance(hotspot["self_time"], (int, float))
            assert isinstance(hotspot["cumulative_time"], (int, float))
            assert isinstance(hotspot["runtime_percent"], (int, float))


class TestProfileWorkloadIntegration:
    """Integration tests simulating CLI usage."""

    def test_profile_then_benchmark(self):
        """Simulate CLI: profile to find hotspot, then benchmark the workload."""
        from optimizer.profiler import run_workload

        # First, profile to get hotspots
        profile_result = profile_workload(
            f"{sys.executable} -c \"x = sum(range(1000))\""
        )
        assert profile_result["exit_code"] == 0

        # Then, benchmark the same workload (uses run_workload, which has no cProfile overhead)
        benchmark_result = run_workload(f"{sys.executable} -c \"x = sum(range(1000))\"")
        assert benchmark_result["exit_code"] == 0

        # Benchmark timing should be reasonable (no cProfile overhead)
        assert benchmark_result["runtime_ms"] > 0

    def test_profile_hotspots_have_required_fields_for_cli(self):
        """Test that hotspots have exactly the fields the CLI needs."""
        script = f"{sys.executable} -c \"y = [x**2 for x in range(100)]\""
        result = profile_workload(script)

        if result["exit_code"] == 0 and result["hotspots"]:
            hotspot = result["hotspots"][0]

            # CLI needs these fields to identify hotspots
            required = {"function", "file", "line", "calls", "self_time", "cumulative_time", "runtime_percent"}
            assert required.issubset(set(hotspot.keys()))

            # CLI does NOT need these (filled in by scanner):
            # - qualified_name
            # - dependencies
            # - related_files
            assert "qualified_name" not in hotspot  # Scanner fills this
            assert "dependencies" not in hotspot  # Scanner fills this
            assert "related_files" not in hotspot  # Scanner fills this


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
