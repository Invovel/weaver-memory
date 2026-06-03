"""Risk-based relation policy for GraphProposal review."""

from __future__ import annotations

from dataclasses import dataclass

from memoryweaver.graph_schema import GraphRelation


@dataclass(frozen=True)
class RelationRisk:
    level: str
    requires_strong_evidence: bool
    auto_accept_allowed: bool


class RiskBasedRelationPolicy:
    """Classify graph relation risk before Harness review."""

    low_risk = {
        GraphRelation.RELATED_TO,
        GraphRelation.ALIAS_OF,
        GraphRelation.SAME_TOPIC_AS,
    }
    medium_risk = {
        GraphRelation.SAME_ISSUE_AS,
        GraphRelation.SUPPORTS,
        GraphRelation.LIMITS,
    }
    high_risk = {
        GraphRelation.CAUSED_BY,
        GraphRelation.CONTRADICTS,
        GraphRelation.SUPERSEDES,
        GraphRelation.RESOLVES,
    }

    def classify(self, relation: GraphRelation) -> RelationRisk:
        if relation in self.high_risk:
            return RelationRisk("high", requires_strong_evidence=True, auto_accept_allowed=False)
        if relation in self.medium_risk:
            return RelationRisk("medium", requires_strong_evidence=True, auto_accept_allowed=True)
        return RelationRisk("low", requires_strong_evidence=False, auto_accept_allowed=True)
