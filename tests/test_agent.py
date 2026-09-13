"""
Unit tests for the Optimization Agent module and shared models.
Aligned with Fifi's Verifier integration contract.
"""

import ast
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from optimizer.models.schemas import Hotspot, CandidatePatch, ModifiedFile
from optimizer.agent.context_builder import ContextBuilder, normalize_path, lookup_file_content
from optimizer.agent.candidate_generator import CandidateGenerator
from optimizer.agent.llm_client import AnthropicLLMClient, BaseLLMClient, MockLLMClient, get_llm_client
from optimizer.agent import generate_candidates


class StubLLMClient(BaseLLMClient):
    """Stub LLM client returning predetermined structured JSON response."""

    def __init__(self, response_text: str):
        self.response_text = response_text

    def generate_raw(self, prompt: str, system_prompt: str) -> str:
        return self.response_text


class TestOptimizationAgent(unittest.TestCase):

    def setUp(self):
        self.sample_hotspot = Hotspot(
            function="calculate_totals",
            qualified_name="billing.services.calculate_totals",
            file="billing/services.py",
            line=42,
            calls=15000,
            self_time=0.85,
            cumulative_time=2.10,
            runtime_percent=55.4,
            dependencies=["billing.models.get_rate"],
            related_files=["billing/services.py", "billing/models.py"]
        )

        self.sample_source = (
            "def calculate_totals(items, discounts):\n"
            "    total = 0\n"
            "    for item in items:\n"
            "        if item.code in [d.code for d in discounts]:\n"
            "            total += item.price * 0.9\n"
            "        else:\n"
            "            total += item.price\n"
            "    return total\n"
        )

    def test_hotspot_model_serialization(self):
        """Verify Hotspot to_dict and from_dict work accurately."""
        d = self.sample_hotspot.to_dict()
        self.assertEqual(d["function"], "calculate_totals")
        self.assertEqual(d["calls"], 15000)

        restored = Hotspot.from_dict(d)
        self.assertEqual(restored.function, self.sample_hotspot.function)
        self.assertEqual(restored.runtime_percent, 55.4)

    def test_hotspot_handles_null_values_defensively(self):
        """Verify Hotspot.from_dict handles None/missing fields without TypeError."""
        raw = {"function": "test", "line": None, "calls": None, "self_time": None}
        hotspot = Hotspot.from_dict(raw)
        self.assertEqual(hotspot.line, 0)
        self.assertEqual(hotspot.calls, 0)
        self.assertEqual(hotspot.self_time, 0.0)

    def test_fifi_contract_serialization_and_aliases(self):
        """Verify CandidatePatch serializes to Fifi's exact contract with edits and new_content."""
        patch = CandidatePatch(
            candidate_id="candidate_a",
            strategy="batch user retrieval",
            explanation="Batching DB calls",
            edits=[ModifiedFile(path="services/users.py", new_content="def get_users(): pass\n")]
        )
        # Check Fifi's keys
        self.assertEqual(patch.edits[0].path, "services/users.py")
        self.assertEqual(patch.edits[0].new_content, "def get_users(): pass\n")
        # Check backward compatibility aliases
        self.assertEqual(patch.modified_files[0].content, "def get_users(): pass\n")
        self.assertEqual(patch.files_changed, ["services/users.py"])

        data = patch.to_dict()
        self.assertIn("edits", data)
        self.assertEqual(data["edits"][0]["new_content"], "def get_users(): pass\n")

        # Check deserialization from Fifi's JSON format
        restored = CandidatePatch.from_dict(data)
        self.assertEqual(restored.candidate_id, "candidate_a")
        self.assertEqual(restored.edits[0].path, "services/users.py")

    def test_fifi_verification_return_fields(self):
        """Verify CandidatePatch holds Fifi's return metrics cleanly."""
        fifi_result = {
            "candidate_id": "candidate_a",
            "strategy": "batch retrieval",
            "explanation": "faster",
            "edits": [{"path": "services/users.py", "new_content": "x = 1\n"}],
            "accepted": True,
            "rejection_reason": None,
            "tests": {"passed": 34, "total": 34},
            "benchmark": {"before_ms": 840, "after_ms": 191, "speedup": 4.4}
        }
        cand = CandidatePatch.from_dict(fifi_result)
        self.assertTrue(cand.accepted)
        self.assertIsNone(cand.rejection_reason)
        self.assertTrue(cand.tests_passed)
        self.assertEqual(cand.speedup, 4.4)

    def test_path_normalization_cross_platform(self):
        """Verify normalize_path and lookup_file_content work across Windows and POSIX."""
        self.assertEqual(normalize_path("billing\\services.py"), "billing/services.py")
        self.assertEqual(normalize_path("./services/users.py"), "services/users.py")

        mapping = {"billing/services.py": "content_a"}
        self.assertEqual(lookup_file_content("billing\\services.py", mapping), "content_a")
        self.assertEqual(lookup_file_content("./billing/services.py", mapping), "content_a")

    def test_context_builder_formatting_with_windows_paths(self):
        """Verify ContextBuilder handles Windows path separators seamlessly."""
        win_hotspot = Hotspot(
            function="calculate_totals",
            qualified_name="billing.services.calculate_totals",
            file="billing\\services.py",
            line=42,
            calls=15000,
            self_time=0.85,
            cumulative_time=2.10,
            runtime_percent=55.4,
            dependencies=[],
            related_files=["billing\\services.py"]
        )
        sections = ContextBuilder.build_prompt_sections(
            win_hotspot,
            file_contents={"billing/services.py": self.sample_source}
        )

        self.assertIn("calculate_totals", sections["hotspot_info"])
        self.assertIn("#### FILE: `billing/services.py`", sections["context_code"])

    def test_mock_candidate_generation(self):
        """Verify Mock mode generates valid Python code candidates with edits."""
        candidates = generate_candidates(
            hotspot=self.sample_hotspot,
            file_contents={"billing/services.py": self.sample_source},
            client=MockLLMClient()
        )

        self.assertGreaterEqual(len(candidates), 2)
        for cand in candidates:
            self.assertTrue(cand.candidate_id.startswith("candidate_"))
            self.assertTrue(len(cand.edits) > 0)
            for e in cand.edits:
                ast.parse(e.new_content)

    def test_mock_candidate_reads_from_disk_fallback(self):
        """Verify Mock mode reads from disk if file_contents is None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "test_file.py")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(self.sample_source)

            hotspot = Hotspot(
                function="calculate_totals",
                qualified_name="test_file.calculate_totals",
                file="test_file.py",
                line=1,
                calls=100,
                self_time=0.1,
                cumulative_time=0.2,
                runtime_percent=10.0
            )

            candidates = generate_candidates(
                hotspot=hotspot,
                file_contents=None,
                base_dir=tmpdir,
                client=MockLLMClient()
            )

            self.assertGreaterEqual(len(candidates), 2)
            self.assertIn("def calculate_totals", candidates[0].edits[0].new_content)

    def test_resilient_json_extraction_with_trailing_commas_and_fences(self):
        """Verify LLM parser recovers from trailing commas, code fences, and conversational text."""
        messy_response = (
            "Here is your optimization candidate:\n"
            "```json\n"
            "{\n"
            '  "candidates": [\n'
            "    {\n"
            '      "candidate_id": "candidate_a",\n'
            '      "strategy": "Optimized lookup",\n'
            '      "explanation": "Removed loop scan.",\n'
            '      "edits": [\n'
            "        {\n"
            '          "path": "billing/services.py",\n'
            '          "new_content": "def foo(): pass\\n",\n'
            "        },\n"
            "      ],\n"
            "    },\n"
            "  ],\n"
            "}\n"
            "```\n"
            "Let me know if you need anything else!"
        )
        client = StubLLMClient(messy_response)
        parsed = client.generate_json("prompt", "sys_prompt")
        self.assertIn("candidates", parsed)
        self.assertEqual(parsed["candidates"][0]["candidate_id"], "candidate_a")

    def test_stub_llm_generation_with_fifi_edits_format(self):
        """Verify LLM structured JSON response with edits and new_content is parsed cleanly."""
        stub_json = '''{
            "candidates": [
                {
                    "candidate_id": "candidate_a",
                    "strategy": "Precompute set outside loop",
                    "explanation": "Extracts discount codes into a set before iteration.",
                    "edits": [
                        {
                            "path": "billing/services.py",
                            "new_content": "def calculate_totals(items, discounts):\\n    codes = {d.code for d in discounts}\\n    return sum(item.price for item in items)\\n"
                        }
                    ]
                }
            ]
        }'''
        generator = CandidateGenerator(client=StubLLMClient(stub_json))
        candidates = generator.generate(
            hotspot=self.sample_hotspot,
            file_contents={"billing/services.py": self.sample_source}
        )

        self.assertEqual(len(candidates), 1)
        cand = candidates[0]
        self.assertEqual(cand.candidate_id, "candidate_a")
        self.assertEqual(cand.edits[0].path, "billing/services.py")
        self.assertIn("def calculate_totals", cand.edits[0].new_content)
        # Ensure parsed AST is valid
        tree = ast.parse(cand.edits[0].new_content)
        self.assertIsInstance(tree, ast.Module)

    def test_syntax_validation_rejects_corrupted_code(self):
        """Verify candidate generator filters out code with syntax errors."""
        corrupted_json = '''{
            "candidates": [
                {
                    "candidate_id": "candidate_broken",
                    "strategy": "Broken syntax",
                    "explanation": "This has a syntax error",
                    "edits": [
                        {
                            "path": "billing/services.py",
                            "new_content": "def broken_code(: invalid syntax"
                        }
                    ]
                }
            ]
        }'''
        generator = CandidateGenerator(client=StubLLMClient(corrupted_json))
        candidates = generator.generate(
            hotspot=self.sample_hotspot,
            file_contents={"billing/services.py": self.sample_source}
        )

        # Broken candidate should be rejected, falling back to valid mock candidates
        self.assertTrue(len(candidates) >= 1)
        for c in candidates:
            self.assertNotEqual(c.candidate_id, "candidate_broken")
            for e in c.edits:
                ast.parse(e.new_content)

    def test_anthropic_client_initialization(self):
        client = AnthropicLLMClient(api_key="test-key")
        self.assertEqual(client.model, "claude-opus-5")
        self.assertEqual(client.max_tokens, 32000)

        # max_tokens cannot be lower than 32000
        client2 = AnthropicLLMClient(api_key="test-key", model="claude-3-7-sonnet", max_tokens=1000)
        self.assertEqual(client2.max_tokens, 32000)

    @patch("urllib.request.urlopen")
    def test_anthropic_client_generate_raw_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "content": [
                {"type": "text", "text": "{\"candidates\": []}"}
            ]
        }).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        client = AnthropicLLMClient(api_key="sk-ant-test1234", model="claude-opus-5")
        output = client.generate_raw("test prompt", "test system")

        self.assertEqual(output, "{\"candidates\": []}")
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.full_url, "https://api.anthropic.com/v1/messages")
        self.assertEqual(req.headers["X-api-key"], "sk-ant-test1234")
        self.assertEqual(req.headers["Anthropic-version"], "2023-06-01")
        self.assertEqual(req.headers["Content-type"], "application/json")

        payload = json.loads(req.data.decode("utf-8"))
        self.assertEqual(payload["model"], "claude-opus-5")
        self.assertEqual(payload["max_tokens"], 32000)
        self.assertEqual(payload["system"], "test system")
        self.assertEqual(payload["messages"], [{"role": "user", "content": "test prompt"}])

    @patch("urllib.request.urlopen")
    def test_anthropic_client_http_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://api.anthropic.com/v1/messages",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=io.BytesIO(b'{"error": "invalid_api_key"}')
        )
        client = AnthropicLLMClient(api_key="bad-key")
        with self.assertRaises(RuntimeError) as ctx:
            client.generate_raw("prompt", "system")
        self.assertIn("Anthropic API Error (HTTP 401)", str(ctx.exception))

    @patch("optimizer.agent.llm_client.load_env_file")
    def test_get_llm_client_anthropic(self, _mock_env):
        with patch.dict(os.environ, {"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "test-key", "ANTHROPIC_MODEL": "claude-opus-5"}, clear=True):
            client = get_llm_client()
            self.assertIsInstance(client, AnthropicLLMClient)
            self.assertEqual(client.model, "claude-opus-5")

    @patch("optimizer.agent.llm_client.load_env_file")
    def test_get_llm_client_anthropic_auto_detect(self, _mock_env):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
            client = get_llm_client()
            self.assertIsInstance(client, AnthropicLLMClient)

    @patch("optimizer.agent.llm_client.load_env_file")
    def test_get_llm_client_anthropic_missing_key_raises(self, _mock_env):
        with patch.dict(os.environ, {"LLM_PROVIDER": "anthropic"}, clear=True):
            with self.assertRaises(ValueError) as ctx:
                get_llm_client()
            self.assertIn("ANTHROPIC_API_KEY environment variable is required", str(ctx.exception))

    def test_llm_failure_prints_to_stderr_before_fallback(self):
        """Verify that when LLM call throws, error is printed to stderr before falling back to mock."""
        class FailingLLMClient(BaseLLMClient):
            def generate_raw(self, prompt: str, system_prompt: str) -> str:
                raise RuntimeError("Anthropic rate limit exceeded (HTTP 429)")

        generator = CandidateGenerator(client=FailingLLMClient())
        captured_stderr = io.StringIO()
        with patch("sys.stderr", captured_stderr):
            candidates = generator.generate(
                hotspot=self.sample_hotspot,
                file_contents={"billing/services.py": self.sample_source}
            )

        err_output = captured_stderr.getvalue()
        self.assertIn("LLM generation failed: Anthropic rate limit exceeded (HTTP 429)", err_output)
        self.assertIn("Falling back to mock generator", err_output)
        self.assertGreaterEqual(len(candidates), 1)


if __name__ == "__main__":
    unittest.main()
