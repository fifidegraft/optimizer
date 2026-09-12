"""
Optimization Agent package.
Responsible for packaging hotspot context, interacting with LLM providers,
and generating 2-3 structured candidate optimization patches.
"""

from .candidate_generator import CandidateGenerator
from .context_builder import ContextBuilder
from .llm_client import (
    BaseLLMClient,
    GeminiLLMClient,
    MockLLMClient,
    OpenAICompatibleLLMClient,
    get_llm_client,
)
from ..models.schemas import Hotspot, CandidatePatch
from typing import Dict, List, Optional, Union


def generate_candidates(
    hotspot: Union[Hotspot, Dict],
    file_contents: Optional[Dict[str, str]] = None,
    base_dir: str = ".",
    client: Optional[BaseLLMClient] = None
) -> List[CandidatePatch]:
    """
    Convenience functional entrypoint matching the integration contract in docs/project_brief.md §11.
    """
    generator = CandidateGenerator(client=client)
    return generator.generate(hotspot=hotspot, file_contents=file_contents, base_dir=base_dir)


__all__ = [
    "CandidateGenerator",
    "ContextBuilder",
    "BaseLLMClient",
    "GeminiLLMClient",
    "MockLLMClient",
    "OpenAICompatibleLLMClient",
    "get_llm_client",
    "generate_candidates"
]
