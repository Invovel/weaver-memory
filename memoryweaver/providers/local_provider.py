"""Local deterministic provider for tests and offline graph proposal demos."""

from __future__ import annotations

from memoryweaver.config import MemoryWeaverConfig
from memoryweaver.graph_schema import GraphProposal, GraphRelation
from memoryweaver.providers.base import ProviderRequest


class LocalGraphProposalProvider:
    """Generate low-confidence GraphProposal objects without network access."""

    def __init__(self, config: MemoryWeaverConfig):
        self.config = config

    def available(self) -> bool:
        return self.config.enable_llm_graph_proposal

    def propose_graph_links(self, request: ProviderRequest) -> list[GraphProposal]:
        if not self.available():
            return []
        tags = [tag for tag in request.tags if tag]
        if len(tags) >= 2:
            confidence = min(0.52, self.config.llm_proposal_confidence_cap)
            return [
                GraphProposal(
                    proposal_type="link_tags",
                    source="llm",
                    from_node=tags[0],
                    to_node=tags[1],
                    relation=GraphRelation.RELATED_TO,
                    reason="Local provider linked the first two supplied tags.",
                    confidence=confidence,
                    status="pending",
                    requires_review=True,
                )
            ]
        return []
