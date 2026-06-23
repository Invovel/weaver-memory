"""Lifecycle metadata for pending GraphProposal records."""

from __future__ import annotations

from dataclasses import dataclass

from memoryweaver.graph_schema import GraphProposal


@dataclass
class PendingProposalLifecyclePolicy:
    """Annotate pending proposals without changing graph edges."""

    review_window_batches: int = 1
    stale_after_batches: int = 3

    def annotate(self, proposal: GraphProposal, *, current_batch: int = 0) -> dict:
        lifecycle = {
            "state": "pending_review",
            "created_batch": current_batch,
            "review_deadline_batch": current_batch + self.review_window_batches,
            "stale_after_batch": current_batch + self.stale_after_batches,
            "on_deadline": "human_or_rule_review",
            "on_stale": "archive_without_new_evidence",
        }
        proposal.metadata["pending_lifecycle"] = lifecycle
        return lifecycle
