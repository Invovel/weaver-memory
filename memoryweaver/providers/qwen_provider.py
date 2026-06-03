"""Qwen/DashScope provider placeholder for GraphProposal generation."""

from memoryweaver.providers.base import BaseHTTPGraphProposalProvider


class QwenGraphProposalProvider(BaseHTTPGraphProposalProvider):
    provider_name = "qwen"
    api_key_attr = "dashscope_api_key"
