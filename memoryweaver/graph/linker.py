"""Apply accepted GraphProposal objects as candidate graph edges."""

from __future__ import annotations

from memoryweaver.graph_linker import GraphLinker
from memoryweaver.graph_schema import GraphProposal
from memoryweaver.graph_store import GraphStore
from memoryweaver.graph.reviewer import GraphProposalReviewPolicy


class ReviewedGraphLinker:
    """Review proposals before writing candidate edges."""

    def __init__(self, graph: GraphStore, policy: GraphProposalReviewPolicy | None = None):
        self.graph = graph
        self.policy = policy or GraphProposalReviewPolicy(graph)
        self.linker = GraphLinker(graph)

    def review_and_apply(self, proposal: GraphProposal):
        review = self.policy.review(proposal)
        proposal.status = review.decision
        proposal.decision = review.decision
        proposal.confidence = review.confidence
        proposal.requires_review = review.requires_review
        self.graph.add_proposal(proposal)
        if review.decision != "accept":
            return review, ""

        edge_id = self.linker.link_tags(
            proposal.from_node,
            proposal.to_node,
            relation=proposal.relation,
            confidence=proposal.confidence,
            source="reviewed_graph_proposal",
        )
        edge = self.graph.get_edge(edge_id)
        if edge is not None:
            edge.evidence_links = sorted(set(edge.evidence_links + proposal.evidence_links))
            edge.metadata.update({
                "proposal_id": proposal.id,
                "review_decision": review.decision,
            })
            self.graph.update_edge(edge)
        return review, edge_id
