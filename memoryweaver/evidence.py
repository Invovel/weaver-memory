"""Small, citable evidence records for the standalone MemoryWeaver SDK."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from memoryweaver.schema import Source
from memoryweaver.store import atomic_write_json

SCHEMA_VERSION = "0.2.0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EvidenceRelation(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    DERIVED_FROM = "derived_from"


@dataclass
class EvidenceNode:
    id: str = field(default_factory=lambda: f"ev_{uuid.uuid4().hex[:12]}")
    text: str = ""
    source: Source = Source.FILE
    source_uri: str = ""
    content_hash: str = ""
    document_id: str = ""
    document_version: str = ""
    title: str = ""
    language: str = "unknown"
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.source, Source):
            self.source = Source(self.source)
        if not self.content_hash:
            self.content_hash = hashlib.sha256(
                self.text.encode("utf-8")
            ).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["source"] = self.source.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> EvidenceNode:
        d = dict(d)
        d["source"] = Source(d.get("source", Source.FILE.value))
        return cls(**d)


@dataclass
class EvidenceLink:
    id: str = field(default_factory=lambda: f"link_{uuid.uuid4().hex[:12]}")
    evidence_id: str = ""
    relation: EvidenceRelation = EvidenceRelation.SUPPORTS
    memory_id: str = ""
    pattern_id: str = ""
    created_at: str = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if not isinstance(self.relation, EvidenceRelation):
            self.relation = EvidenceRelation(self.relation)
        if bool(self.memory_id) == bool(self.pattern_id):
            raise ValueError(
                "EvidenceLink must target exactly one memory_id or pattern_id"
            )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["relation"] = self.relation.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> EvidenceLink:
        d = dict(d)
        d["relation"] = EvidenceRelation(d["relation"])
        return cls(**d)


@dataclass
class EvidencePacket:
    query_id: str
    policy_version: str
    scope: str = "project"
    evidence_refs: list[str] = field(default_factory=list)
    memory_refs: list[str] = field(default_factory=list)
    pattern_refs: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    degraded_components: list[str] = field(default_factory=list)
    specialists: list[dict[str, Any]] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    recommended_mode: str = "thinking"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EvidenceStore:
    """Atomic JSON storage for evidence nodes and their memory links."""

    def __init__(self, nodes_path: str | Path, links_path: str | Path):
        self._nodes_path = Path(nodes_path)
        self._links_path = Path(links_path)
        self._nodes: dict[str, EvidenceNode] = {}
        self._links: dict[str, EvidenceLink] = {}
        self._load_nodes()
        self._load_links()

    def add_node(self, node: EvidenceNode) -> str:
        self._nodes[node.id] = node
        self._save_nodes()
        return node.id

    def get_node(self, id: str) -> Optional[EvidenceNode]:
        return self._nodes.get(id)

    def list_nodes(self) -> list[EvidenceNode]:
        return list(self._nodes.values())

    def add_link(self, link: EvidenceLink) -> str:
        self._links[link.id] = link
        self._save_links()
        return link.id

    def get_link(self, id: str) -> Optional[EvidenceLink]:
        return self._links.get(id)

    def list_links(self) -> list[EvidenceLink]:
        return list(self._links.values())

    def links_for_memory(self, memory_id: str) -> list[EvidenceLink]:
        return [link for link in self._links.values() if link.memory_id == memory_id]

    def links_for_pattern(self, pattern_id: str) -> list[EvidenceLink]:
        return [
            link for link in self._links.values() if link.pattern_id == pattern_id
        ]

    def validate_links(
        self,
        memory_ids: set[str],
        pattern_ids: set[str],
    ) -> list[str]:
        errors: list[str] = []
        for link in self._links.values():
            if link.evidence_id not in self._nodes:
                errors.append(f"dangling evidence node: {link.id}")
            if link.memory_id and link.memory_id not in memory_ids:
                errors.append(f"dangling memory target: {link.id}")
            if link.pattern_id and link.pattern_id not in pattern_ids:
                errors.append(f"dangling pattern target: {link.id}")
        return errors

    def _save_nodes(self) -> None:
        self._atomic_save(
            self._nodes_path,
            {"version": SCHEMA_VERSION, "nodes": [n.to_dict() for n in self._nodes.values()]},
        )

    def _save_links(self) -> None:
        self._atomic_save(
            self._links_path,
            {"version": SCHEMA_VERSION, "links": [l.to_dict() for l in self._links.values()]},
        )

    @staticmethod
    def _atomic_save(path: Path, data: dict[str, Any]) -> None:
        atomic_write_json(path, data)

    def _load_nodes(self) -> None:
        for raw in self._load_collection(self._nodes_path, "nodes"):
            node = EvidenceNode.from_dict(raw)
            self._nodes[node.id] = node

    def _load_links(self) -> None:
        for raw in self._load_collection(self._links_path, "links"):
            link = EvidenceLink.from_dict(raw)
            self._links[link.id] = link

    @staticmethod
    def _load_collection(path: Path, key: str) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        try:
            text = path.read_text(encoding="utf-8").strip()
            return json.loads(text).get(key, []) if text else []
        except (json.JSONDecodeError, FileNotFoundError):
            return []
