"""GBrain temporal graph and mind-map projection.

GBrain is MemoryWeaver's relation layer. It links tags, memories, evidence, and
patterns so retrieval can narrow candidates and runtime traces can show
lineage. It does not promote memory, stabilize Layer 3, or execute runtime
actions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from memoryweaver.graph_linker import GraphLinker, tag_node_id
from memoryweaver.graph_schema import (
    GraphEdge,
    GraphNode,
    GraphNodeType,
    GraphRelation,
    GraphStatus,
)
from memoryweaver.schema import MemoryItem, Pattern
from memoryweaver.store import MemoryWorkspace


@dataclass
class MindMapNode:
    id: str
    label: str
    node_type: str
    ref_id: str = ""
    layer: str = ""
    status: str = ""
    rank: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MindMapEdge:
    id: str
    source_id: str
    target_id: str
    relation: str
    status: str
    confidence: float
    temporal: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MindMapProjection:
    center_tags: list[str]
    nodes: list[MindMapNode]
    edges: list[MindMapEdge]
    core_node_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "center_tags": self.center_tags,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "core_node_ids": self.core_node_ids,
        }


class GBrain:
    """Workspace-level graph synchronizer and mind-map projector."""

    def __init__(self, workspace: MemoryWorkspace):
        self.workspace = workspace
        self.linker = GraphLinker(workspace.graph)

    def sync_workspace(self, *, accepted: bool = True) -> dict[str, Any]:
        """Sync current stores into graph nodes and lineage edges.

        The sync is idempotent and advisory. It records graph relationships but
        never changes memory layer, Pattern status, or evidence truth.
        """

        status = GraphStatus.ACCEPTED if accepted else GraphStatus.CANDIDATE
        edge_ids: list[str] = []
        for memory in self.workspace.memories.list_all():
            self.linker.ensure_memory(memory)
            edge_ids.extend(self._link_memory_tags(memory, status=status))
        for link in self.workspace.evidence.list_links():
            node = self.workspace.evidence.get_node(link.evidence_id)
            edge_ids.append(
                self.linker.link_evidence(
                    link,
                    evidence_label=node.title if node else link.evidence_id,
                    confidence=0.9,
                )
            )
            edge = self.workspace.graph.get_edge(edge_ids[-1])
            if edge is not None and edge.status != status:
                edge.status = status
                self.workspace.graph.update_edge(edge)
        for pattern in self.workspace.patterns.list_all():
            self.linker.ensure_pattern(pattern)
            edge_ids.extend(self._link_pattern_lineage(pattern, status=status))
        return {
            "memory_count": self.workspace.memories.count(),
            "evidence_node_count": len(self.workspace.evidence.list_nodes()),
            "evidence_link_count": len(self.workspace.evidence.list_links()),
            "pattern_count": len(self.workspace.patterns.list_all()),
            "graph_node_count": len(self.workspace.graph.list_nodes()),
            "graph_edge_count": len(self.workspace.graph.list_edges()),
            "synced_edge_count": len(edge_ids),
            "status": status.value,
        }

    def add_temporal_edge(
        self,
        source_id: str,
        target_id: str,
        relation: GraphRelation,
        *,
        valid_from: str = "",
        valid_to: str = "",
        challenged_by: list[str] | None = None,
        supersedes: list[str] | None = None,
        confidence: float = 0.7,
        status: GraphStatus = GraphStatus.ACCEPTED,
    ) -> str:
        """Add a temporal graph edge with validity metadata."""

        edge = GraphEdge(
            source_id=source_id,
            target_id=target_id,
            relation=relation,
            confidence=confidence,
            source="gbrain_temporal",
            status=status,
            metadata={
                "valid_from": valid_from,
                "valid_to": valid_to,
                "challenged_by": challenged_by or [],
                "supersedes": supersedes or [],
                "temporal": True,
            },
        )
        return self.workspace.graph.add_edge(edge)

    def project_mind_map(
        self,
        *,
        center_tags: list[str] | None = None,
        max_nodes: int = 80,
        include_candidate: bool = True,
    ) -> MindMapProjection:
        """Project the graph into a compact mind-map view."""

        center_tags = center_tags or []
        selected_node_ids = self._select_node_ids(center_tags, max_nodes=max_nodes)
        raw_nodes = [
            self.workspace.graph.get_node(node_id)
            for node_id in selected_node_ids
            if self.workspace.graph.get_node(node_id) is not None
        ]
        raw_edges: list[GraphEdge] = []
        for edge in self.workspace.graph.list_edges():
            if not include_candidate and edge.status == GraphStatus.CANDIDATE:
                continue
            if edge.status in (GraphStatus.REJECTED, GraphStatus.STALE):
                continue
            if edge.source_id in selected_node_ids and edge.target_id in selected_node_ids:
                raw_edges.append(edge)

        degree: dict[str, int] = {node.id: 0 for node in raw_nodes}
        for edge in raw_edges:
            degree[edge.source_id] = degree.get(edge.source_id, 0) + 1
            degree[edge.target_id] = degree.get(edge.target_id, 0) + 1

        nodes = [self._mind_node(node, degree.get(node.id, 0)) for node in raw_nodes]
        nodes.sort(key=lambda node: (node.rank, node.node_type, node.id), reverse=True)
        edges = [self._mind_edge(edge) for edge in raw_edges]
        core_node_ids = [node.id for node in nodes[: min(10, len(nodes))] if node.rank > 0]
        return MindMapProjection(
            center_tags=center_tags,
            nodes=nodes,
            edges=edges,
            core_node_ids=core_node_ids,
        )

    def _select_node_ids(self, center_tags: list[str], *, max_nodes: int) -> set[str]:
        if not center_tags:
            nodes = self.workspace.graph.list_nodes()
            ranked = sorted(
                nodes,
                key=lambda node: len(self.workspace.graph.edges_for(node.id)),
                reverse=True,
            )
            return {node.id for node in ranked[:max_nodes]}

        selected = {tag_node_id(tag) for tag in center_tags if self.workspace.graph.get_node(tag_node_id(tag))}
        frontier = set(selected)
        for _ in range(2):
            next_frontier: set[str] = set()
            for node_id in frontier:
                for edge, neighbor in self.workspace.graph.neighbors(node_id):
                    if edge.status in (GraphStatus.REJECTED, GraphStatus.STALE):
                        continue
                    if len(selected) >= max_nodes:
                        return selected
                    selected.add(neighbor.id)
                    next_frontier.add(neighbor.id)
            frontier = next_frontier
        return selected

    def _link_memory_tags(
        self,
        memory: MemoryItem,
        *,
        status: GraphStatus,
    ) -> list[str]:
        memory_node_id = self.linker.ensure_memory(memory)
        edge_ids: list[str] = []
        for tag in memory.tags:
            tag_id = self.linker.ensure_tag(tag)
            edge_ids.append(
                self.linker.add_candidate_edge(
                    source_id=memory_node_id,
                    target_id=tag_id,
                    relation=GraphRelation.RELATED_TO,
                    confidence=1.0,
                    source="gbrain_sync",
                    status=status,
                    metadata={
                        "layer": memory.layer.value,
                        "source": memory.source.value,
                        "freshness": memory.freshness.value,
                    },
                )
            )
        return edge_ids

    def _link_pattern_lineage(
        self,
        pattern: Pattern,
        *,
        status: GraphStatus,
    ) -> list[str]:
        pattern_node_id = self.linker.ensure_pattern(pattern)
        edge_ids: list[str] = []
        for memory_id in pattern.composed_from:
            edge_ids.append(
                self.linker.add_candidate_edge(
                    source_id=pattern_node_id,
                    target_id=f"memnode_{memory_id}",
                    relation=GraphRelation.SUPPORTS,
                    confidence=1.0,
                    source="gbrain_pattern_lineage",
                    status=status,
                    evidence_links=list(pattern.evidence_links),
                    metadata={
                        "pattern_status": pattern.status.value,
                        "rollback_to": list(pattern.rollback_to),
                    },
                )
            )
        return edge_ids

    def _mind_node(self, node: GraphNode, degree: int) -> MindMapNode:
        layer = ""
        status = ""
        rank_bonus = 0.0
        if node.node_type == GraphNodeType.MEMORY and node.ref_id:
            memory = self.workspace.memories.get(node.ref_id)
            if memory is not None:
                layer = f"layer_{memory.layer.value}"
                status = memory.status.value
                rank_bonus += 2.0 if memory.layer.value == 2 else 1.0
        elif node.node_type == GraphNodeType.PATTERN and node.ref_id:
            pattern = self.workspace.patterns.get(node.ref_id)
            if pattern is not None:
                layer = "layer_3"
                status = pattern.status.value
                rank_bonus += 3.0
        elif node.node_type == GraphNodeType.EVIDENCE:
            layer = "evidence"
            rank_bonus += 1.0
        elif node.node_type == GraphNodeType.TAG:
            layer = "tag"
        return MindMapNode(
            id=node.id,
            label=node.label,
            node_type=node.node_type.value,
            ref_id=node.ref_id,
            layer=layer,
            status=status,
            rank=round(degree + rank_bonus, 3),
            metadata=dict(node.metadata),
        )

    @staticmethod
    def _mind_edge(edge: GraphEdge) -> MindMapEdge:
        temporal = {
            key: edge.metadata.get(key)
            for key in ["valid_from", "valid_to", "challenged_by", "supersedes", "temporal"]
            if key in edge.metadata
        }
        return MindMapEdge(
            id=edge.id,
            source_id=edge.source_id,
            target_id=edge.target_id,
            relation=edge.relation.value,
            status=edge.status.value,
            confidence=edge.confidence,
            temporal=temporal,
        )
