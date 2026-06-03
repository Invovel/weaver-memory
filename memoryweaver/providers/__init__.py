"""Optional LLM provider adapters for low-privilege GraphProposal generation."""

from memoryweaver.providers.base import LLMGraphProposalProvider, ProviderRequest
from memoryweaver.providers.local_provider import LocalGraphProposalProvider
from memoryweaver.providers.openai_provider import OpenAIGraphProposalProvider
from memoryweaver.providers.anthropic_provider import AnthropicGraphProposalProvider
from memoryweaver.providers.deepseek_provider import DeepSeekGraphProposalProvider
from memoryweaver.providers.qwen_provider import QwenGraphProposalProvider

__all__ = [
    "ProviderRequest",
    "LLMGraphProposalProvider",
    "LocalGraphProposalProvider",
    "OpenAIGraphProposalProvider",
    "AnthropicGraphProposalProvider",
    "DeepSeekGraphProposalProvider",
    "QwenGraphProposalProvider",
]
