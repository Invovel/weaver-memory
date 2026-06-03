"""DeepSeek provider placeholder for GraphProposal generation."""

from memoryweaver.providers.base import BaseHTTPGraphProposalProvider


class DeepSeekGraphProposalProvider(BaseHTTPGraphProposalProvider):
    provider_name = "deepseek"
    api_key_attr = "deepseek_api_key"
