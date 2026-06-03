"""Base provider interfaces for GraphProposal generation only."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from memoryweaver.config import MemoryWeaverConfig
from memoryweaver.graph_schema import GraphProposal


@dataclass
class ProviderRequest:
    query: str = ""
    memories: list[dict] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


class LLMGraphProposalProvider(Protocol):
    """Providers may return GraphProposal objects, never graph edges."""

    config: MemoryWeaverConfig

    def available(self) -> bool:
        ...

    def propose_graph_links(self, request: ProviderRequest) -> list[GraphProposal]:
        ...


class DisabledProvider:
    """Provider used when config disables LLM graph proposals."""

    def __init__(self, config: MemoryWeaverConfig):
        self.config = config

    def available(self) -> bool:
        return False

    def propose_graph_links(self, request: ProviderRequest) -> list[GraphProposal]:
        return []


class BaseHTTPGraphProposalProvider:
    """Shared zero-dependency placeholder for remote providers.

    The SDK exposes provider configuration without forcing network access during
    tests. Concrete providers can later implement the HTTP call while preserving
    the same low-privilege GraphProposal contract.
    """

    provider_name = ""
    api_key_attr = ""

    def __init__(self, config: MemoryWeaverConfig):
        self.config = config

    def available(self) -> bool:
        return (
            self.config.enable_llm_graph_proposal
            and bool(getattr(self.config, self.api_key_attr, ""))
        )

    def propose_graph_links(self, request: ProviderRequest) -> list[GraphProposal]:
        if not self.available():
            return []
        raise NotImplementedError(
            f"{self.provider_name} HTTP graph proposal calls are not implemented yet"
        )


def provider_from_config(config: MemoryWeaverConfig):
    if not config.enable_llm_graph_proposal:
        return DisabledProvider(config)
    name = config.llm_provider.lower()
    if name == "local":
        from memoryweaver.providers.local_provider import LocalGraphProposalProvider

        return LocalGraphProposalProvider(config)
    if name == "openai":
        from memoryweaver.providers.openai_provider import OpenAIGraphProposalProvider

        return OpenAIGraphProposalProvider(config)
    if name == "anthropic":
        from memoryweaver.providers.anthropic_provider import AnthropicGraphProposalProvider

        return AnthropicGraphProposalProvider(config)
    if name == "deepseek":
        from memoryweaver.providers.deepseek_provider import DeepSeekGraphProposalProvider

        return DeepSeekGraphProposalProvider(config)
    if name == "qwen":
        from memoryweaver.providers.qwen_provider import QwenGraphProposalProvider

        return QwenGraphProposalProvider(config)
    return DisabledProvider(config)
