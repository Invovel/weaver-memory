"""Bind candidate evidence references to GraphProposal objects.

This module deliberately does not create verified EvidenceLink records. It only
adds candidate evidence references that the Harness reviewer can inspect.
"""

from __future__ import annotations

from dataclasses import dataclass

from memoryweaver.evidence import EvidenceNode, EvidenceStore
from memoryweaver.graph_schema import GraphProposal
from memoryweaver.store import token_jaccard


@dataclass
class EvidenceBinding:
    proposal_id: str
    evidence_id: str
    score: float
    state: str = "candidate_evidence_link"


class GraphEvidenceBinder:
    """Attach likely evidence refs to proposals without verifying them."""

    def __init__(self, evidence: EvidenceStore):
        self.evidence = evidence

    def bind(
        self,
        proposal: GraphProposal,
        *,
        query: str = "",
        limit: int = 2,
        threshold: float = 0.05,
    ) -> list[EvidenceBinding]:
        existing = set(proposal.evidence_links + proposal.evidence_ids)
        bindings: list[EvidenceBinding] = []
        for evidence_id in existing:
            if self.evidence.get_node(evidence_id) is not None:
                bindings.append(EvidenceBinding(
                    proposal_id=proposal.id,
                    evidence_id=evidence_id,
                    score=1.0,
                    state="verified_evidence_link",
                ))

        if not bindings:
            scored = self._score_nodes(proposal, query)
            bindings.extend(
                EvidenceBinding(proposal.id, node.id, score)
                for score, node in scored[:limit]
                if score >= threshold
            )

        states = dict(proposal.metadata.get("evidence_link_states", {}))
        for binding in bindings:
            if binding.evidence_id not in proposal.evidence_links:
                proposal.evidence_links.append(binding.evidence_id)
            if binding.evidence_id not in proposal.evidence_ids:
                proposal.evidence_ids.append(binding.evidence_id)
            if binding.state != "verified_evidence_link":
                states[binding.evidence_id] = binding.state
        proposal.metadata["evidence_link_states"] = states
        proposal.metadata["evidence_binding"] = (
            "candidate_only"
            if states
            else "provided_or_verified"
        )
        return bindings

    def _score_nodes(
        self,
        proposal: GraphProposal,
        query: str,
    ) -> list[tuple[float, EvidenceNode]]:
        needle = " ".join([
            query,
            proposal.from_node,
            proposal.from_node.replace("_", " "),
            proposal.to_node,
            proposal.to_node.replace("_", " "),
            proposal.reason,
        ]).strip()
        scored: list[tuple[float, EvidenceNode]] = []
        for node in self.evidence.list_nodes():
            haystack = " ".join([
                node.id,
                node.title,
                node.text,
                node.source_uri,
                " ".join(str(value) for value in node.metadata.values()),
            ])
            score = token_jaccard(needle, haystack)
            if score > 0:
                scored.append((score, node))
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored
