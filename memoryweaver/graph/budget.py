"""Budget gates for graph expansion and LLM GraphProposal generation."""

from __future__ import annotations

from dataclasses import dataclass, field

from memoryweaver.graph_schema import GraphRelation


@dataclass
class ProposalBudgetDecision:
    allowed: bool
    reasons: list[str] = field(default_factory=list)
    provider_override: str = ""


@dataclass
class ProposalBudgetGate:
    """Keep LLM proposal generation out of the online path."""

    max_batch_proposals: int = 24
    max_proposals_per_query: int = 6
    max_graph_hops: int = 1
    max_candidates_per_query: int = 50
    provider_wrong_link_threshold: float = 0.5
    allowed_relations: set[GraphRelation] = field(default_factory=lambda: {
        GraphRelation.RELATED_TO,
        GraphRelation.ALIAS_OF,
        GraphRelation.SAME_TOPIC_AS,
        GraphRelation.SAME_ISSUE_AS,
        GraphRelation.SUPPORTS,
        GraphRelation.LIMITS,
    })

    def allow_llm_proposal(
        self,
        *,
        path: str,
        current_batch_proposals: int = 0,
        provider_wrong_link_rate: float = 0.0,
    ) -> ProposalBudgetDecision:
        reasons: list[str] = []
        if path != "offline":
            reasons.append("online path never calls LLM GraphProposal")
        if current_batch_proposals >= self.max_batch_proposals:
            reasons.append("batch proposal budget exhausted")
        provider_override = ""
        if provider_wrong_link_rate > self.provider_wrong_link_threshold:
            reasons.append("provider wrong-link rate exceeds threshold")
            provider_override = "local"
        return ProposalBudgetDecision(
            allowed=not reasons,
            reasons=reasons,
            provider_override=provider_override,
        )

    def allow_relation(self, relation: GraphRelation) -> bool:
        return relation in self.allowed_relations
