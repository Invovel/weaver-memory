"""Offline batch runner for LLM GraphProposal review."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from memoryweaver.config import MemoryWeaverConfig
from memoryweaver.graph.budget import ProposalBudgetGate
from memoryweaver.graph.evidence_binder import GraphEvidenceBinder
from memoryweaver.graph.evidence_support import EvidenceSupportCheck
from memoryweaver.graph.linker import ReviewedGraphLinker
from memoryweaver.graph.proposal import LLMGraphProposalService
from memoryweaver.graph.reviewer import GraphProposalReviewPolicy
from memoryweaver.graph_schema import GraphProposal
from memoryweaver.store import MemoryWorkspace


@dataclass
class OfflineBatchResult:
    proposals: list[dict[str, Any]] = field(default_factory=list)
    reviewed: list[dict[str, Any]] = field(default_factory=list)
    budget_denials: list[str] = field(default_factory=list)
    online_llm_call_count: int = 0


class OfflineProposalBatchRunner:
    """Run LLM proposal generation only on the offline path."""

    def __init__(
        self,
        workspace: MemoryWorkspace,
        config: MemoryWeaverConfig,
        *,
        budget_gate: ProposalBudgetGate | None = None,
    ):
        self.workspace = workspace
        self.config = config
        self.budget_gate = budget_gate or ProposalBudgetGate()
        self.service = LLMGraphProposalService(config)
        self.binder = GraphEvidenceBinder(workspace.evidence)
        self.linker = ReviewedGraphLinker(
            workspace.graph,
            GraphProposalReviewPolicy(
                workspace.graph,
                evidence_check=EvidenceSupportCheck(workspace.evidence),
            ),
        )

    def run(
        self,
        records: list[dict[str, Any]],
        *,
        provider_wrong_link_rate: float = 0.0,
    ) -> OfflineBatchResult:
        result = OfflineBatchResult()
        proposal_count = 0
        for record in records:
            decision = self.budget_gate.allow_llm_proposal(
                path="offline",
                current_batch_proposals=proposal_count,
                provider_wrong_link_rate=provider_wrong_link_rate,
            )
            if not decision.allowed:
                result.budget_denials.extend(decision.reasons)
                break
            proposals = self.service.propose(
                query=str(record.get("query", "")),
                tags=list(record.get("tags", [])),
                memories=list(record.get("memories", [])),
                evidence=list(record.get("evidence", [])),
            )[:self.budget_gate.max_proposals_per_query]
            proposal_count += len(proposals)
            for proposal in proposals:
                proposal_record = {
                    "input_id": record.get("id", ""),
                    "query": record.get("query", ""),
                    "proposal": proposal.to_dict(),
                }
                result.proposals.append(proposal_record)
                result.reviewed.append(self.review_record(proposal_record))
        return result

    def review_record(self, record: dict[str, Any]) -> dict[str, Any]:
        proposal = GraphProposal.from_dict(record["proposal"])
        self.binder.bind(proposal, query=str(record.get("query", "")))
        review, edge_id = self.linker.review_and_apply(proposal)
        return {
            "input_id": record.get("input_id", ""),
            "query": record.get("query", ""),
            "proposal": proposal.to_dict(),
            "review": {
                "decision": review.decision,
                "reasons": review.reasons,
                "confidence": review.confidence,
                "requires_review": review.requires_review,
                "evidence_support": review.evidence_support,
            },
            "edge_id": edge_id,
        }
