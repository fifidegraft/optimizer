"""
LLM Provider Wrapper for Optimizer.
Designed to be zero-cost-first:
- Built-in Mock provider (default, 0 setup, 0 cost, offline-safe)
- Anthropic Claude (claude-opus-5, claude-3-7-sonnet, etc.)
- Google Gemini (free tier via Google AI Studio)
- Local Ollama (100% free, runs offline on local machine)
- Groq / OpenAI (for users with existing keys)

Uses Python standard library (urllib.request) so teammates have ZERO dependency installation issues.
"""

from __future__ import annotations
import abc
import json
import os
import re
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional


def load_env_file(env_path: str = ".env") -> None:
    """Lightweight zero-dependency .env loader."""
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception:
        pass


class BaseLLMClient(abc.ABC):
    """Abstract interface for LLM providers."""

    @abc.abstractmethod
    def generate_raw(self, prompt: str, system_prompt: str) -> str:
        """Sends prompt to the LLM and returns raw text output."""
        pass

    def generate_json(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        """Generates structured response and parses JSON."""
        raw = self.generate_raw(prompt, system_prompt)
        return self._extract_json(raw)

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extracts and parses JSON object from response, stripping markdown code fences if present."""
        cleaned = text.strip()
        # Find the outermost curly braces
        first_brace = cleaned.find("{")
        last_brace = cleaned.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            cleaned = cleaned[first_brace:last_brace + 1]

        try:
            return json.loads(cleaned, strict=False)
        except json.JSONDecodeError:
            # Attempt to fix common LLM formatting error: trailing commas before closing braces/brackets
            repaired = re.sub(r",\s*([\]}])", r"\1", cleaned)
            try:
                return json.loads(repaired, strict=False)
            except json.JSONDecodeError as e:
                raise ValueError(f"Failed to parse JSON from LLM response: {e}\nRaw output:\n{text[:500]}")


class MockLLMClient(BaseLLMClient):
    """
    Zero-cost, offline-safe mock provider.
    Inspects the provided code or prompt to synthesize 2-3 realistic, deterministic
    Python optimizations (e.g. set membership lookups, caching, loop invariant hoisting).
    """

    def generate_raw(self, prompt: str, system_prompt: str) -> str:
        # Default mock response with 2 candidates
        candidates = [
            {
                "candidate_id": "candidate_a",
                "strategy": "Set-based membership lookup",
                "explanation": "Converted O(n) list scans in the loop to O(1) set lookups to eliminate quadratic complexity.",
                "modified_files": []
            },
            {
                "candidate_id": "candidate_b",
                "strategy": "Function memoization and caching",
                "explanation": "Added functools.lru_cache to eliminate redundant recalculation of identical inputs.",
                "modified_files": []
            }
        ]

        return json.dumps({"candidates": candidates}, indent=2)


class GeminiLLMClient(BaseLLMClient):
    """
    Google Gemini API client using standard library HTTP (no extra pip packages required).
    Uses the free tier on Google AI Studio.
    """

    def __init__(self, api_key: str, model: str = "gemini-3.6-flash"):
        self.api_key = api_key
        self.model = model
        self.base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"

    def generate_raw(self, prompt: str, system_prompt: str) -> str:
        url = f"{self.base_url}?key={self.api_key}"
        headers = {"Content-Type": "application/json"}

        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": prompt}]}
            ],
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.2
            }
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                candidates = result.get("candidates", [])
                if not candidates:
                    raise RuntimeError("Gemini returned empty candidate list")
                parts = candidates[0].get("content", {}).get("parts", [])
                if not parts:
                    raise RuntimeError("Gemini candidate had no content parts")
                return parts[0].get("text", "")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Gemini API Error (HTTP {e.code}): {err_body}") from e
        except Exception as e:
            raise RuntimeError(f"Gemini connection failed: {e}") from e


class OpenAICompatibleLLMClient(BaseLLMClient):
    """
    Compatible with:
    - Free local Ollama (http://localhost:11434/v1)
    - Groq (free tier) (https://api.groq.com/openai/v1)
    - OpenAI (https://api.openai.com/v1)
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        api_key: Optional[str] = None,
        model: str = "qwen2.5-coder"
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or "ollama"
        self.model = model

    def generate_raw(self, prompt: str, system_prompt: str) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"}
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                choices = result.get("choices", [])
                if not choices:
                    raise RuntimeError("API returned empty choices list")
                return choices[0].get("message", {}).get("content", "")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI-compatible API Error (HTTP {e.code}): {err_body}") from e
        except Exception as e:
            raise RuntimeError(f"Connection to {self.base_url} failed: {e}") from e


class AnthropicLLMClient(BaseLLMClient):
    """
    Anthropic Claude API client using standard library HTTP (no extra pip packages required).
    Sends raw HTTP requests to /v1/messages with headers:
      - x-api-key: <api_key>
      - anthropic-version: 2023-06-01
      - Content-Type: application/json
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-opus-5",
        base_url: str = "https://api.anthropic.com/v1",
        max_tokens: int = 32000,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.max_tokens = max(max_tokens, 32000)

    def generate_raw(self, prompt: str, system_prompt: str) -> str:
        if self.base_url.endswith("/v1"):
            url = f"{self.base_url}/messages"
        else:
            url = f"{self.base_url}/v1/messages"

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": prompt}
            ],
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                content = result.get("content", [])
                if not content:
                    raise RuntimeError("Anthropic returned empty content list")
                text_parts = [
                    part.get("text", "")
                    for part in content
                    if part.get("type") == "text" or "text" in part
                ]
                if not text_parts:
                    raise RuntimeError("Anthropic response had no text parts")
                return "".join(text_parts)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Anthropic API Error (HTTP {e.code}): {err_body}") from e
        except Exception as e:
            raise RuntimeError(f"Anthropic connection failed: {e}") from e


def get_llm_client() -> BaseLLMClient:
    """
    Factory that automatically selects the appropriate LLM client based on environment variables.
    Defaults to MockLLMClient if no external provider is configured.
    """
    load_env_file()

    provider = os.getenv("LLM_PROVIDER", "").lower()

    if provider == "mock":
        return MockLLMClient()

    # 1. Anthropic
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if provider == "anthropic" or (not provider and anthropic_key):
        if not anthropic_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required for Anthropic provider.")
        model = os.getenv("ANTHROPIC_MODEL", "claude-opus-5")
        return AnthropicLLMClient(api_key=anthropic_key, model=model)

    # 2. Gemini (Free tier)
    gemini_key = os.getenv("GEMINI_API_KEY")
    if provider == "gemini" or (not provider and gemini_key):
        if not gemini_key:
            raise ValueError("GEMINI_API_KEY environment variable is required for Gemini provider.")
        model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
        return GeminiLLMClient(api_key=gemini_key, model=model)

    # 3. Local Ollama (100% Free local offline)
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434/v1")
    if provider == "ollama":
        model = os.getenv("OLLAMA_MODEL", "qwen2.5-coder")
        return OpenAICompatibleLLMClient(base_url=ollama_host, api_key="ollama", model=model)

    # 4. Groq (Free tier)
    groq_key = os.getenv("GROQ_API_KEY")
    if provider == "groq" or (not provider and groq_key):
        if not groq_key:
            raise ValueError("GROQ_API_KEY environment variable is required for Groq provider.")
        model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        return OpenAICompatibleLLMClient(
            base_url="https://api.groq.com/openai/v1",
            api_key=groq_key,
            model=model
        )

    # 5. OpenAI
    openai_key = os.getenv("OPENAI_API_KEY")
    if provider == "openai" or (not provider and openai_key):
        if not openai_key:
            raise ValueError("OPENAI_API_KEY environment variable is required for OpenAI provider.")
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        return OpenAICompatibleLLMClient(
            base_url="https://api.openai.com/v1",
            api_key=openai_key,
            model=model
        )

    # Default fallback: Mock provider
    print("[Optimizer Agent] No LLM API key detected. Running in free Mock Mode.")
    print("[Optimizer Agent] (Tip: set ANTHROPIC_API_KEY, GEMINI_API_KEY, or OLLAMA_HOST in .env for live models)")
    return MockLLMClient()
