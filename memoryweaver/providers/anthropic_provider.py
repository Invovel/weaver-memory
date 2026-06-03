"""Anthropic provider placeholder for GraphProposal generation."""

from memoryweaver.providers.base import BaseHTTPGraphProposalProvider


class AnthropicGraphProposalProvider(BaseHTTPGraphProposalProvider):
    provider_name = "anthropic"
    api_key_attr = "anthropic_api_key"
