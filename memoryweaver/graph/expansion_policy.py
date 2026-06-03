"""Online graph expansion policy."""

from __future__ import annotations

from dataclasses import dataclass

from memoryweaver.graph_schema import GraphStatus


@dataclass
class GraphExpansionPolicy:
    """Budget graph expansion so online search does not over-expand."""

    max_hops: int = 1
    min_text_results_before_skip: int = 3
    text_threshold: float = 0.25
    max_candidates: int = 50
    accepted_statuses: set[GraphStatus] | None = None

    def __post_init__(self) -> None:
        if self.accepted_statuses is None:
            self.accepted_statuses = {GraphStatus.ACCEPTED, GraphStatus.VERIFIED}

    def should_expand(self, text_result_count: int) -> bool:
        return text_result_count < self.min_text_results_before_skip
