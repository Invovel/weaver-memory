"""Atomic JSON-backed store for minimal graph tag-linking."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from memoryweaver.graph_schema import (
    GraphEdge,
    GraphNode,
    GraphNodeType,
    GraphProposal,
    GraphStatus,
)
from memoryweaver.store import SCHEMA_VERSION, atomic_write_json


class GraphStore:
    """Store candidate graph nodes, edges, and LLM proposals.

    The graph is advisory only. It can shrink retrieval candidates, but it does
    not promote memory, stabilize Patterns, delete records, or trigger fast mode.
    """

    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._nodes: dict[str, GraphNode] = {}
        self._edges: dict[str, GraphEdge] = {}
        self._proposals: dict[str, GraphProposal] = {}
        self._load()

    def add_node(self, node: GraphNode) -> str:
        existing = self._nodes.get(node.id)
        if existing:
            existing.label = node.label or existing.label
            existing.ref_id = node.ref_id or existing.ref_id
            existing.metadata.update(node.metadata)
            existing.mark_updated()
        else:
            self._nodes[node.id] = node
        self._save()
        return node.id

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        return self._nodes.get(node_id)

    def list_nodes(self, node_type: GraphNodeType | None = None) -> list[GraphNode]:
        if node_type is None:
            return list(self._nodes.values())
        return [node for node in self._nodes.values() if node.node_type == node_type]

    def add_edge(self, edge: GraphEdge, *, replace: bool = False) -> str:
        if edge.id in self._edges and not replace:
            raise ValueError(f"GraphEdge '{edge.id}' already exists")
        self._edges[edge.id] = edge
        self._save()
        return edge.id

    def update_edge(self, edge: GraphEdge) -> None:
        if edge.id not in self._edges:
            raise KeyError(f"GraphEdge '{edge.id}' not found")
        edge.mark_updated()
        self._edges[edge.id] = edge
        self._save()

    def get_edge(self, edge_id: str) -> Optional[GraphEdge]:
        return self._edges.get(edge_id)

    def list_edges(
        self,
        *,
        status: GraphStatus | None = None,
    ) -> list[GraphEdge]:
        if status is None:
            return list(self._edges.values())
        return [edge for edge in self._edges.values() if edge.status == status]

    def edges_for(self, node_id: str) -> list[GraphEdge]:
        return [
            edge for edge in self._edges.values()
            if edge.source_id == node_id or edge.target_id == node_id
        ]

    def neighbors(
        self,
        node_id: str,
        *,
        include_stale: bool = False,
    ) -> list[tuple[GraphEdge, GraphNode]]:
        results: list[tuple[GraphEdge, GraphNode]] = []
        for edge in self.edges_for(node_id):
            if edge.status in (GraphStatus.REJECTED, GraphStatus.STALE) and not include_stale:
                continue
            other_id = edge.target_id if edge.source_id == node_id else edge.source_id
            node = self._nodes.get(other_id)
            if node is not None:
                results.append((edge, node))
        return results

    def add_proposal(self, proposal: GraphProposal) -> str:
        self._proposals[proposal.id] = proposal
        self._save()
        return proposal.id

    def get_proposal(self, proposal_id: str) -> Optional[GraphProposal]:
        return self._proposals.get(proposal_id)

    def list_proposals(self) -> list[GraphProposal]:
        return list(self._proposals.values())

    def validate_refs(
        self,
        *,
        memory_ids: set[str],
        evidence_ids: set[str],
        pattern_ids: set[str],
    ) -> list[str]:
        errors: list[str] = []
        for node in self._nodes.values():
            if node.node_type == GraphNodeType.MEMORY and node.ref_id not in memory_ids:
                errors.append(f"dangling graph memory node: {node.id}")
            if node.node_type == GraphNodeType.EVIDENCE and node.ref_id not in evidence_ids:
                errors.append(f"dangling graph evidence node: {node.id}")
            if node.node_type == GraphNodeType.PATTERN and node.ref_id not in pattern_ids:
                errors.append(f"dangling graph pattern node: {node.id}")
        for edge in self._edges.values():
            if edge.source_id not in self._nodes:
                errors.append(f"dangling graph edge source: {edge.id}")
            if edge.target_id not in self._nodes:
                errors.append(f"dangling graph edge target: {edge.id}")
        return errors

    def _save(self) -> None:
        atomic_write_json(
            self._path,
            {
                "version": SCHEMA_VERSION,
                "nodes": [node.to_dict() for node in self._nodes.values()],
                "edges": [edge.to_dict() for edge in self._edges.values()],
                "proposals": [
                    proposal.to_dict() for proposal in self._proposals.values()
                ],
            },
        )

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            text = self._path.read_text(encoding="utf-8").strip()
            data = json.loads(text) if text else {}
        except (json.JSONDecodeError, FileNotFoundError):
            return
        for raw in data.get("nodes", []):
            node = GraphNode.from_dict(raw)
            self._nodes[node.id] = node
        for raw in data.get("edges", []):
            edge = GraphEdge.from_dict(raw)
            self._edges[edge.id] = edge
        for raw in data.get("proposals", []):
            proposal = GraphProposal.from_dict(raw)
            self._proposals[proposal.id] = proposal
