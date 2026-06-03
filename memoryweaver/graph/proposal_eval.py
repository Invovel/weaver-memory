"""Evaluation helpers for GraphProposal batch validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from memoryweaver.graph_linker import normalize_tag


UNDIRECTED_RELATIONS = {
    "related_to",
    "alias_of",
    "same_topic_as",
    "same_issue_as",
}


@dataclass(frozen=True)
class EdgeKey:
    left: str
    right: str
    relation: str

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "EdgeKey":
        relation = str(record.get("relation", "related_to"))
        left = normalize_tag(str(record.get("from_tag") or record.get("from_node") or ""))
        right = normalize_tag(str(record.get("to_tag") or record.get("to_node") or ""))
        if relation in UNDIRECTED_RELATIONS and right < left:
            left, right = right, left
        return cls(left, right, relation)


@dataclass
class ProposalEvalResult:
    gold_count: int
    proposal_count: int
    matched_count: int
    wrong_count: int
    precision: float
    recall: float
    wrong_link_rate: float
    accepted: int
    pending: int
    rejected: int
    quarantined: int
    human_review_needed: int
    pending_rate: float
    reject_rate: float
    human_review_needed_rate: float
    evidence_coverage: float
    exact_support_rate: float
    partial_support_rate: float
    unsupported_rate: float
    accepted_wrong_link_rate: float
    review_cost_per_accepted_edge: float
    matched_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gold_count": self.gold_count,
            "proposal_count": self.proposal_count,
            "matched_count": self.matched_count,
            "wrong_count": self.wrong_count,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "wrong_link_rate": round(self.wrong_link_rate, 4),
            "accepted": self.accepted,
            "pending": self.pending,
            "rejected": self.rejected,
            "quarantined": self.quarantined,
            "human_review_needed": self.human_review_needed,
            "pending_rate": round(self.pending_rate, 4),
            "reject_rate": round(self.reject_rate, 4),
            "human_review_needed_rate": round(self.human_review_needed_rate, 4),
            "evidence_coverage": round(self.evidence_coverage, 4),
            "exact_support_rate": round(self.exact_support_rate, 4),
            "partial_support_rate": round(self.partial_support_rate, 4),
            "unsupported_rate": round(self.unsupported_rate, 4),
            "accepted_wrong_link_rate": round(self.accepted_wrong_link_rate, 4),
            "review_cost_per_accepted_edge": round(self.review_cost_per_accepted_edge, 4),
            "matched_ids": self.matched_ids,
        }


def evaluate_proposals(
    gold_edges: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
) -> ProposalEvalResult:
    gold = {EdgeKey.from_record(record) for record in gold_edges}
    proposal_records = [_proposal_record(record) for record in predictions]
    predicted = [EdgeKey.from_record(record) for record in proposal_records]
    matched_indices = [
        index for index, key in enumerate(predicted)
        if key in gold
    ]
    proposal_count = len(predicted)
    matched_count = len(matched_indices)
    wrong_count = proposal_count - matched_count
    decisions = [
        str(record.get("review", {}).get("decision") or record.get("decision") or record.get("status", "pending"))
        for record in predictions
    ]
    evidence_count = sum(
        1 for record in proposal_records
        if record.get("evidence_links") or record.get("evidence_ids")
    )
    support_statuses = [
        str(record.get("review", {}).get("evidence_support", "insufficient_evidence"))
        for record in predictions
    ]
    accepted_wrong = 0
    accepted_count = 0
    for decision, key in zip(decisions, predicted):
        if decision in {"accept", "accepted"}:
            accepted_count += 1
            if key not in gold:
                accepted_wrong += 1
    review_needed = sum(
        1 for record in predictions
        if bool(record.get("review", {}).get("requires_review", record.get("requires_review", True)))
    )
    return ProposalEvalResult(
        gold_count=len(gold),
        proposal_count=proposal_count,
        matched_count=matched_count,
        wrong_count=wrong_count,
        precision=matched_count / proposal_count if proposal_count else 0.0,
        recall=matched_count / len(gold) if gold else 0.0,
        wrong_link_rate=wrong_count / proposal_count if proposal_count else 0.0,
        accepted=decisions.count("accept") + decisions.count("accepted"),
        pending=decisions.count("pending"),
        rejected=decisions.count("reject") + decisions.count("rejected"),
        quarantined=decisions.count("quarantine") + decisions.count("quarantined"),
        human_review_needed=review_needed,
        pending_rate=decisions.count("pending") / proposal_count if proposal_count else 0.0,
        reject_rate=(decisions.count("reject") + decisions.count("rejected")) / proposal_count if proposal_count else 0.0,
        human_review_needed_rate=review_needed / proposal_count if proposal_count else 0.0,
        evidence_coverage=evidence_count / proposal_count if proposal_count else 0.0,
        exact_support_rate=support_statuses.count("supports_exact") / proposal_count if proposal_count else 0.0,
        partial_support_rate=support_statuses.count("supports_partial") / proposal_count if proposal_count else 0.0,
        unsupported_rate=(
            support_statuses.count("does_not_support")
            + support_statuses.count("contradicts")
            + support_statuses.count("insufficient_evidence")
        ) / proposal_count if proposal_count else 0.0,
        accepted_wrong_link_rate=accepted_wrong / accepted_count if accepted_count else 0.0,
        review_cost_per_accepted_edge=review_needed / accepted_count if accepted_count else 0.0,
        matched_ids=[
            str(proposal_records[index].get("id", proposal_records[index].get("proposal_id", "")))
            for index in matched_indices
        ],
    )


def _proposal_record(record: dict[str, Any]) -> dict[str, Any]:
    if "proposal" in record and isinstance(record["proposal"], dict):
        merged = dict(record["proposal"])
        if "review" in record:
            merged["review"] = record["review"]
        return merged
    return record
