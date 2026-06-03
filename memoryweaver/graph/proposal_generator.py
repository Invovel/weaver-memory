"""Batch GraphProposal generation entrypoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from memoryweaver.config import MemoryWeaverConfig
from memoryweaver.graph.proposal import LLMGraphProposalService
from memoryweaver.graph_schema import GraphProposal


@dataclass
class GraphProposalBatchResult:
    input_id: str
    query: str
    proposals: list[GraphProposal]

    def to_records(self) -> list[dict[str, Any]]:
        return [
            {
                "input_id": self.input_id,
                "query": self.query,
                "proposal": proposal.to_dict(),
            }
            for proposal in self.proposals
        ]


class BatchGraphProposalGenerator:
    """Generate GraphProposal objects from JSON-serializable batch records."""

    def __init__(
        self,
        config: MemoryWeaverConfig,
        service: LLMGraphProposalService | None = None,
    ):
        self.config = config
        self.service = service or LLMGraphProposalService(config)

    def generate_one(self, record: dict[str, Any]) -> GraphProposalBatchResult:
        query = str(record.get("query", ""))
        proposals = self.service.propose(
            query=query,
            tags=list(record.get("tags", [])),
            memories=list(record.get("memories", [])),
            evidence=list(record.get("evidence", [])),
        )
        return GraphProposalBatchResult(
            input_id=str(record.get("id") or record.get("input_id") or ""),
            query=query,
            proposals=proposals,
        )

    def generate(self, records: list[dict[str, Any]]) -> list[GraphProposalBatchResult]:
        return [self.generate_one(record) for record in records]
