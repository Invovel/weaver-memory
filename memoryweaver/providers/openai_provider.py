"""OpenAI provider placeholder for GraphProposal generation."""

from memoryweaver.providers.base import BaseHTTPGraphProposalProvider


class OpenAIGraphProposalProvider(BaseHTTPGraphProposalProvider):
    provider_name = "openai"
    api_key_attr = "openai_api_key"
