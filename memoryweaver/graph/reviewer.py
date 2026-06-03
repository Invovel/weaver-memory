"""Harness review policy for low-privilege GraphProposal objects."""

from __future__ import annotations

from dataclasses import dataclass, field

from memoryweaver.graph_linker import tag_node_id
from memoryweaver.graph_schema import GraphProposal, GraphRelation
from memoryweaver.graph_store import GraphStore
from memoryweaver.graph.evidence_support import (
    EvidenceSupport,
    EvidenceSupportCheck,
)
from memoryweaver.graph.relation_policy import RiskBasedRelationPolicy
from memoryweaver.store import token_jaccard


@dataclass
class GraphProposalReview:
    proposal_id: str
    decision: str
    reasons: list[str] = field(default_factory=list)
    confidence: float = 0.0
    requires_review: bool = True
    evidence_support: str = "insufficient_evidence"


class GraphProposalReviewPolicy:
    """Review LLM proposals before any candidate edge is written."""

    def __init__(
        self,
        graph: GraphStore,
        *,
        confidence_cap: float = 0.6,
        fanout_review_threshold: int = 8,
        evidence_check: EvidenceSupportCheck | None = None,
        relation_policy: RiskBasedRelationPolicy | None = None,
    ):
        self._graph = graph
        self.confidence_cap = max(0.0, min(confidence_cap, 1.0))
        self.fanout_review_threshold = fanout_review_threshold
        self.evidence_check = evidence_check or EvidenceSupportCheck()
        self.relation_policy = relation_policy or RiskBasedRelationPolicy()

    def review(self, proposal: GraphProposal) -> GraphProposalReview:
        reasons: list[str] = []
        evidence_links = list(dict.fromkeys(proposal.evidence_links + proposal.evidence_ids))
        support = self.evidence_check.check(proposal)
        proposal.metadata["evidence_support"] = support.to_dict()
        evidence_states = proposal.metadata.get("evidence_link_states", {})
        candidate_only_evidence = bool(evidence_links) and bool(evidence_states) and all(
            evidence_states.get(link_id) == "candidate_evidence_link"
            for link_id in evidence_links
            if evidence_states
        )
        verified_evidence = bool(evidence_links) and not candidate_only_evidence
        confidence = proposal.confidence
        if not verified_evidence:
            confidence = min(proposal.confidence, self.confidence_cap)

        if (
            proposal.source in {"assistant", "llm"}
            and not verified_evidence
            and proposal.confidence > self.confidence_cap
        ):
            reasons.append("confidence capped for assistant/llm proposal")

        if not evidence_links:
            reasons.append("missing evidence link")
        elif candidate_only_evidence:
            reasons.append("candidate evidence requires review")
        if support.status == EvidenceSupport.DOES_NOT_SUPPORT:
            reasons.append("evidence does not support relation")
            return GraphProposalReview(
                proposal_id=proposal.id,
                decision="reject",
                reasons=reasons,
                confidence=confidence,
                requires_review=True,
                evidence_support=support.status.value,
            )
        if support.status == EvidenceSupport.CONTRADICTS:
            reasons.append("evidence contradicts relation")
            return GraphProposalReview(
                proposal_id=proposal.id,
                decision="reject",
                reasons=reasons,
                confidence=confidence,
                requires_review=True,
                evidence_support=support.status.value,
            )
        if support.status == EvidenceSupport.SUPPORTS_PARTIAL:
            reasons.append("evidence supports relation only partially")

        if proposal.relation == GraphRelation.CONTRADICTS:
            reasons.append("conflicting relation rejected without terminal/user override")
            return GraphProposalReview(
                proposal_id=proposal.id,
                decision="reject",
                reasons=reasons,
                confidence=confidence,
                requires_review=True,
                evidence_support=support.status.value,
            )

        relation_risk = self.relation_policy.classify(proposal.relation)
        if not relation_risk.auto_accept_allowed:
            reasons.append("high-risk relation cannot be auto accepted")
            return GraphProposalReview(
                proposal_id=proposal.id,
                decision="quarantine",
                reasons=reasons,
                confidence=confidence,
                requires_review=True,
                evidence_support=support.status.value,
            )

        if relation_risk.requires_strong_evidence and support.status != EvidenceSupport.SUPPORTS_EXACT:
            reasons.append("relation requires exact evidence support")

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
                evidence_support=support.status.value,
            )

        lexical_similarity = token_jaccard(proposal.from_node, proposal.to_node)
        alias_auto_candidate = (
            proposal.relation == GraphRelation.ALIAS_OF
            and lexical_similarity >= 0.8
            and confidence <= self.confidence_cap
        )
        if alias_auto_candidate:
            return GraphProposalReview(
                proposal_id=proposal.id,
                decision="accept",
                reasons=reasons or ["alias/synonym high lexical match candidate"],
                confidence=confidence,
                requires_review=False,
                evidence_support=support.status.value,
            )

        low_risk_with_verified_evidence = (
            proposal.proposal_type in {"link_tags", "alias", "synonym"}
            and relation_risk.level == "low"
            and verified_evidence
            and support.status == EvidenceSupport.SUPPORTS_EXACT
        )
        if low_risk_with_verified_evidence:
            return GraphProposalReview(
                proposal_id=proposal.id,
                decision="accept",
                reasons=reasons or ["low-risk tag link with evidence"],
                confidence=confidence,
                requires_review=False,
                evidence_support=support.status.value,
            )

        return GraphProposalReview(
            proposal_id=proposal.id,
            decision="pending",
            reasons=reasons or ["requires harness review"],
            confidence=confidence,
            requires_review=True,
            evidence_support=support.status.value,
        )
