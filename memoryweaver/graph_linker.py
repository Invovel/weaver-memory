"""Manual and rule-based graph linking helpers."""

from __future__ import annotations

import re

from memoryweaver.evidence import EvidenceLink
from memoryweaver.graph_schema import (
    GraphEdge,
    GraphNode,
    GraphNodeType,
    GraphProposal,
    GraphRelation,
    GraphStatus,
)
from memoryweaver.graph_store import GraphStore
from memoryweaver.schema import MemoryItem, Pattern


def normalize_tag(tag: str) -> str:
    normalized = re.sub(r"[^a-z0-9\u3400-\u4dbf\u4e00-\u9fff]+", "_", tag.lower())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "untagged"


def tag_node_id(tag: str) -> str:
    return f"tag_{normalize_tag(tag)}"


class GraphLinker:
    """Create candidate graph nodes and edges without changing memory state."""

    def __init__(self, graph: GraphStore):
        self._graph = graph

    def ensure_tag(self, tag: str) -> str:
        node = GraphNode(
            id=tag_node_id(tag),
            node_type=GraphNodeType.TAG,
            label=normalize_tag(tag),
            ref_id=normalize_tag(tag),
        )
        return self._graph.add_node(node)

    def ensure_memory(self, memory: MemoryItem) -> str:
        return self._graph.add_node(
            GraphNode(
                id=f"memnode_{memory.id}",
                node_type=GraphNodeType.MEMORY,
                label=memory.content[:80],
                ref_id=memory.id,
                metadata={"source": memory.source.value, "layer": memory.layer.value},
            )
        )

    def ensure_evidence(self, evidence_id: str, label: str = "") -> str:
        return self._graph.add_node(
            GraphNode(
                id=f"evnode_{evidence_id}",
                node_type=GraphNodeType.EVIDENCE,
                label=label or evidence_id,
                ref_id=evidence_id,
            )
        )

    def ensure_pattern(self, pattern: Pattern) -> str:
        return self._graph.add_node(
            GraphNode(
                id=f"patnode_{pattern.id}",
                node_type=GraphNodeType.PATTERN,
                label=pattern.rule[:80],
                ref_id=pattern.id,
                metadata={"status": pattern.status.value},
            )
        )

    def link_memory_tags(self, memory: MemoryItem) -> list[str]:
        memory_node_id = self.ensure_memory(memory)
        edge_ids: list[str] = []
        for tag in memory.tags:
            tag_id = self.ensure_tag(tag)
            edge_ids.append(self.add_candidate_edge(
                source_id=memory_node_id,
                target_id=tag_id,
                relation=GraphRelation.RELATED_TO,
                confidence=1.0,
                source="rule",
                metadata={"tag": normalize_tag(tag)},
            ))
        return edge_ids

    def link_tags(
        self,
        left_tag: str,
        right_tag: str,
        relation: GraphRelation = GraphRelation.RELATED_TO,
        confidence: float = 0.7,
        source: str = "graph_proposal",
        status: GraphStatus = GraphStatus.CANDIDATE,
    ) -> str:
        return self.add_candidate_edge(
            source_id=self.ensure_tag(left_tag),
            target_id=self.ensure_tag(right_tag),
            relation=relation,
            confidence=confidence,
            source=source,
            status=status,
        )

    def link_evidence(
        self,
        link: EvidenceLink,
        *,
        evidence_label: str = "",
        confidence: float = 0.8,
    ) -> str:
        evidence_node_id = self.ensure_evidence(link.evidence_id, evidence_label)
        if link.memory_id:
            target_id = f"memnode_{link.memory_id}"
        elif link.pattern_id:
            target_id = f"patnode_{link.pattern_id}"
        else:
            raise ValueError("EvidenceLink has no graph target")
        return self.add_candidate_edge(
            source_id=evidence_node_id,
            target_id=target_id,
            relation=GraphRelation(link.relation.value),
            confidence=confidence,
            source="evidence_link",
            evidence_links=[link.id],
        )

    def link_pattern_lineage(self, pattern: Pattern) -> list[str]:
        pattern_node_id = self.ensure_pattern(pattern)
        edge_ids: list[str] = []
        for memory_id in pattern.composed_from:
            edge_ids.append(self.add_candidate_edge(
                source_id=pattern_node_id,
                target_id=f"memnode_{memory_id}",
                relation=GraphRelation.SUPPORTS,
                confidence=1.0,
                source="pattern_lineage",
                evidence_links=list(pattern.evidence_links),
            ))
        return edge_ids

    def add_candidate_edge(
        self,
        *,
        source_id: str,
        target_id: str,
        relation: GraphRelation,
        confidence: float,
        source: str = "graph_proposal",
        status: GraphStatus = GraphStatus.CANDIDATE,
        evidence_links: list[str] | None = None,
        metadata: dict | None = None,
    ) -> str:
        edge_id = f"edge_{source_id}_{relation.value}_{target_id}"
        edge = GraphEdge(
            id=edge_id,
            source_id=source_id,
            target_id=target_id,
            relation=relation,
            confidence=confidence,
            source=source,
            status=status,
            evidence_links=evidence_links or [],
            metadata=metadata or {},
        )
        existing = self._graph.get_edge(edge.id)
        if existing is None:
            return self._graph.add_edge(edge)
        existing.confidence = max(existing.confidence, edge.confidence)
        if existing.status == GraphStatus.CANDIDATE and edge.status != GraphStatus.CANDIDATE:
            existing.status = edge.status
        existing.evidence_links = sorted(set(existing.evidence_links + edge.evidence_links))
        existing.metadata.update(edge.metadata)
        self._graph.update_edge(existing)
        return existing.id

    def propose_link(
        self,
        *,
        from_text: str,
        to_text: str,
        relation: GraphRelation,
        reason: str,
        confidence: float,
        source: str = "llm",
        proposal_type: str = "link_tags",
    ) -> str:
        proposal = GraphProposal(
            proposal_type=proposal_type,
            source=source,
            from_text=from_text,
            to_text=to_text,
            relation=relation,
            reason=reason,
            confidence=confidence,
            decision="pending",
        )
        return self._graph.add_proposal(proposal)
