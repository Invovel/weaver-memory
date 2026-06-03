"""Minimal graph schema for candidate tag-linking and lineage."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class GraphNodeType(str, Enum):
    TAG = "tag"
    MEMORY = "memory"
    EVIDENCE = "evidence"
    PATTERN = "pattern"


class GraphRelation(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    RELATED_TO = "related_to"
    SAME_ISSUE_AS = "same_issue_as"
    CAUSED_BY = "caused_by"
    SUPERSEDES = "supersedes"


class GraphStatus(str, Enum):
    CANDIDATE = "candidate"
    VERIFIED = "verified"
    REJECTED = "rejected"
    STALE = "stale"


@dataclass
class GraphNode:
    id: str
    node_type: GraphNodeType
    label: str = ""
    ref_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if not isinstance(self.node_type, GraphNodeType):
            self.node_type = GraphNodeType(self.node_type)

    def mark_updated(self) -> None:
        self.updated_at = _utc_now()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["node_type"] = self.node_type.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphNode:
        data = dict(data)
        data["node_type"] = GraphNodeType(data["node_type"])
        return cls(**data)


@dataclass
class GraphEdge:
    source_id: str
    target_id: str
    relation: GraphRelation
    id: str = field(default_factory=lambda: f"edge_{uuid.uuid4().hex[:12]}")
    confidence: float = 0.0
    source: str = "graph_proposal"
    status: GraphStatus = GraphStatus.CANDIDATE
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    evidence_links: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.relation, GraphRelation):
            self.relation = GraphRelation(self.relation)
        if not isinstance(self.status, GraphStatus):
            self.status = GraphStatus(self.status)
        self.confidence = max(0.0, min(float(self.confidence), 1.0))

    def mark_updated(self) -> None:
        self.updated_at = _utc_now()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["relation"] = self.relation.value
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphEdge:
        data = dict(data)
        data["relation"] = GraphRelation(data["relation"])
        data["status"] = GraphStatus(data.get("status", "candidate"))
        return cls(**data)


@dataclass
class GraphProposal:
    proposal_type: str
    source: str
    from_text: str
    to_text: str
    relation: GraphRelation
    reason: str
    id: str = field(default_factory=lambda: f"gp_{uuid.uuid4().hex[:12]}")
    confidence: float = 0.0
    decision: str = "pending"
    created_at: str = field(default_factory=_utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.relation, GraphRelation):
            self.relation = GraphRelation(self.relation)
        self.confidence = max(0.0, min(float(self.confidence), 1.0))

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["relation"] = self.relation.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphProposal:
        data = dict(data)
        data["relation"] = GraphRelation(data["relation"])
        return cls(**data)
