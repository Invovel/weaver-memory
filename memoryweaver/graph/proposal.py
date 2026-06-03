"""Service that asks providers for GraphProposal objects only."""

from __future__ import annotations

from memoryweaver.config import MemoryWeaverConfig
from memoryweaver.graph_schema import GraphProposal
from memoryweaver.providers.base import ProviderRequest, provider_from_config


class LLMGraphProposalService:
    """Generate candidate graph proposals without mutating graph or memory."""

    def __init__(self, config: MemoryWeaverConfig, provider=None):
        self.config = config
        self.provider = provider or provider_from_config(config)

    def enabled(self) -> bool:
        return self.config.enable_llm_graph_proposal and self.provider.available()

    def propose(
        self,
        *,
        query: str = "",
        memories: list[dict] | None = None,
        evidence: list[dict] | None = None,
        tags: list[str] | None = None,
    ) -> list[GraphProposal]:
        if not self.enabled():
            return []
        request = ProviderRequest(
            query=query,
            memories=memories or [],
            evidence=evidence or [],
            tags=tags or [],
        )
        proposals = self.provider.propose_graph_links(request)
        for proposal in proposals:
            proposal.source = "llm"
            proposal.confidence = min(
                proposal.confidence,
                self.config.llm_proposal_confidence_cap,
            )
            proposal.requires_review = True
            if proposal.status not in {"pending", "accepted", "rejected", "quarantined"}:
                proposal.status = "pending"
        return proposals
