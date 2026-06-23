"""Evidence support checks for GraphProposal relations."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from memoryweaver.evidence import EvidenceNode, EvidenceStore
from memoryweaver.graph_schema import GraphProposal, GraphRelation
from memoryweaver.store import token_jaccard, tokenize_text


class EvidenceSupport(str, Enum):
    SUPPORTS_EXACT = "supports_exact"
    SUPPORTS_PARTIAL = "supports_partial"
    DOES_NOT_SUPPORT = "does_not_support"
    CONTRADICTS = "contradicts"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass
class EvidenceSupportResult:
    status: EvidenceSupport
    evidence_ids: list[str] = field(default_factory=list)
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "evidence_ids": self.evidence_ids,
            "score": round(self.score, 4),
            "reasons": self.reasons,
        }


class EvidenceSupportCheck:
    """Check whether evidence supports a proposed relation, not just exists."""

    exact_markers = {
        "fixed",
        "resolved",
        "helped",
        "proved",
        "confirmation",
        "succeeded",
        "worked",
        "解决",
        "修复",
        "证明",
    }
    contradiction_markers = {
        "not",
        "did not",
        "unrelated",
        "not the root cause",
        "does not",
        "不是",
        "无关",
        "未解决",
    }

    def __init__(self, evidence: EvidenceStore | None = None):
        self.evidence = evidence

    def check(self, proposal: GraphProposal) -> EvidenceSupportResult:
        evidence_ids = list(dict.fromkeys(proposal.evidence_links + proposal.evidence_ids))
        if not evidence_ids:
            return EvidenceSupportResult(
                EvidenceSupport.INSUFFICIENT_EVIDENCE,
                reasons=["missing evidence reference"],
            )
        if self.evidence is None:
            return EvidenceSupportResult(
                EvidenceSupport.SUPPORTS_PARTIAL,
                evidence_ids=evidence_ids,
                score=0.5,
                reasons=["evidence store unavailable; treating refs as partial"],
            )

        nodes = [
            node for evidence_id in evidence_ids
            if (node := self.evidence.get_node(evidence_id)) is not None
        ]
        if not nodes:
            return EvidenceSupportResult(
                EvidenceSupport.INSUFFICIENT_EVIDENCE,
                evidence_ids=evidence_ids,
                reasons=["evidence references do not resolve"],
            )
        best = max(self._score_node(proposal, node) for node in nodes)
        if proposal.relation == GraphRelation.CONTRADICTS:
            return EvidenceSupportResult(
                EvidenceSupport.CONTRADICTS,
                evidence_ids=evidence_ids,
                score=best,
                reasons=["proposal relation is contradicts"],
            )
        if best >= 0.8:
            return EvidenceSupportResult(
                EvidenceSupport.SUPPORTS_EXACT,
                evidence_ids=evidence_ids,
                score=best,
                reasons=["evidence explicitly supports relation"],
            )
        if best >= 0.35:
            return EvidenceSupportResult(
                EvidenceSupport.SUPPORTS_PARTIAL,
                evidence_ids=evidence_ids,
                score=best,
                reasons=["evidence overlaps but does not exactly support relation"],
            )
        if best > 0:
            return EvidenceSupportResult(
                EvidenceSupport.DOES_NOT_SUPPORT,
                evidence_ids=evidence_ids,
                score=best,
                reasons=["evidence is weak context, not relation support"],
            )
        return EvidenceSupportResult(
            EvidenceSupport.DOES_NOT_SUPPORT,
            evidence_ids=evidence_ids,
            reasons=["evidence does not mention both endpoints"],
        )

    def _score_node(self, proposal: GraphProposal, node: EvidenceNode) -> float:
        left = proposal.from_node.replace("_", " ")
        right = proposal.to_node.replace("_", " ")
        text = " ".join([
            node.text.lower(),
            node.title.lower(),
            " ".join(str(value).lower() for value in node.metadata.values()),
        ])
        left_coverage = self._endpoint_coverage(left, proposal.from_node, text)
        right_coverage = self._endpoint_coverage(right, proposal.to_node, text)
        min_coverage = min(left_coverage, right_coverage)
        if min_coverage <= 0:
            return token_jaccard(f"{left} {right}", text) * 0.5
        if min_coverage < 0.67:
            return 0.35
        text_tokens = tokenize_text(text)
        phrase_markers = self.contradiction_markers - {"not"}
        if "not" in text_tokens or any(marker in text for marker in phrase_markers):
            return 0.25
        endpoint_score = 0.55
        if any(marker in text for marker in self.exact_markers):
            endpoint_score += 0.35
        if tokenize_text(proposal.relation.value) & tokenize_text(text):
            endpoint_score += 0.1
        return min(endpoint_score, 1.0)

    @staticmethod
    def _endpoint_coverage(endpoint_text: str, endpoint_tag: str, text: str) -> float:
        if endpoint_tag in text:
            return 1.0
        endpoint_tokens = {
            token for token in tokenize_text(endpoint_text)
            if len(token) > 1
        }
        if not endpoint_tokens:
            return 0.0
        text_tokens = tokenize_text(text)
        return len(endpoint_tokens & text_tokens) / len(endpoint_tokens)
