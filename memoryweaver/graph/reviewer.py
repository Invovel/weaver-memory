"""Harness review policy for low-privilege GraphProposal objects."""

from __future__ import annotations

from dataclasses import dataclass, field

from memoryweaver.graph_linker import tag_node_id
from memoryweaver.graph_schema import GraphProposal, GraphRelation
from memoryweaver.graph_store import GraphStore


@dataclass
class GraphProposalReview:
    proposal_id: str
    decision: str
    reasons: list[str] = field(default_factory=list)
    confidence: float = 0.0
    requires_review: bool = True


class GraphProposalReviewPolicy:
    """Review LLM proposals before any candidate edge is written."""

    def __init__(
        self,
        graph: GraphStore,
        *,
        confidence_cap: float = 0.6,
        fanout_review_threshold: int = 8,
    ):
        self._graph = graph
        self.confidence_cap = max(0.0, min(confidence_cap, 1.0))
        self.fanout_review_threshold = fanout_review_threshold

    def review(self, proposal: GraphProposal) -> GraphProposalReview:
        reasons: list[str] = []
        confidence = min(proposal.confidence, self.confidence_cap)

        if proposal.source in {"assistant", "llm"} and proposal.confidence > self.confidence_cap:
            reasons.append("confidence capped for assistant/llm proposal")

        if not proposal.evidence_links:
            reasons.append("missing evidence link")

        if proposal.relation == GraphRelation.CONTRADICTS:
            reasons.append("conflicting relation requires review")
            return GraphProposalReview(
                proposal_id=proposal.id,
                decision="reject",
                reasons=reasons,
                confidence=confidence,
                requires_review=True,
            )

        fanout = max(
            len(self._graph.edges_for(proposal.from_node)),
            len(self._graph.edges_for(tag_node_id(proposal.from_node))),
        )
        if fanout >= self.fanout_review_threshold:
            reasons.append("high fan-out edge requires review")
            return GraphProposalReview(
                proposal_id=proposal.id,
                decision="quarantine",
                reasons=reasons,
                confidence=confidence,
                requires_review=True,
            )

        low_risk = (
            proposal.proposal_type in {"link_tags", "alias", "synonym"}
            and proposal.relation in {
                GraphRelation.RELATED_TO,
                GraphRelation.SAME_ISSUE_AS,
            }
            and confidence <= self.confidence_cap
        )
        if low_risk and proposal.evidence_links:
            return GraphProposalReview(
                proposal_id=proposal.id,
                decision="accept",
                reasons=reasons or ["low-risk tag link with evidence"],
                confidence=confidence,
                requires_review=False,
            )

        return GraphProposalReview(
            proposal_id=proposal.id,
            decision="pending",
            reasons=reasons or ["requires harness review"],
            confidence=confidence,
            requires_review=True,
        )
