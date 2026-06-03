"""JSON-file-based memory store.

Provides CRUD operations and basic query-by-tag / query-by-polarity
on a local JSON file. Designed to be replaced by a vector DB in later
phases without changing the public API.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Optional

from memoryweaver.schema import MemoryItem, Layer, Polarity, Status
from memoryweaver.policy import MemoryPolicy, RetrievalPolicy

SCHEMA_VERSION = "0.2.0"


def tokenize_text(text: str) -> set[str]:
    """Tokenize English identifiers and Chinese text without external deps."""
    normalized = unicodedata.normalize("NFKC", text).lower()
    tokens = set(re.findall(r"@?[a-z0-9][a-z0-9._/@+-]*", normalized))
    for segment in re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]+", normalized):
        if len(segment) == 1:
            tokens.add(segment)
        else:
            tokens.update(segment[index:index + 2] for index in range(len(segment) - 1))
    return tokens


def token_jaccard(left: str, right: str) -> float:
    """Return token Jaccard similarity for English, Chinese, or mixed text."""
    left_tokens = tokenize_text(left)
    right_tokens = tokenize_text(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


class MemoryStore:
    """Local JSON-backed store for MemoryItem objects.

    Usage:
        store = MemoryStore("memory.json")
        store.add(item)
        results = store.find_by_tags(["wsl", "codex"])
    """

    def __init__(
        self,
        path: str | Path = "memory.json",
        policy: Optional[MemoryPolicy] = None,
    ):
        self._path = Path(path)
        self._items: dict[str, MemoryItem] = {}
        self._policy = policy or MemoryPolicy()
        if self._path.exists():
            self._load()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add(self, item: MemoryItem) -> str:
        """Insert a memory item. Returns its id."""
        self._policy.validate_write(item)
        self._items[item.id] = item
        self._save()
        return item.id

    def get(self, id: str) -> Optional[MemoryItem]:
        """Retrieve a single memory by id."""
        return self._items.get(id)

    def update(self, item: MemoryItem) -> None:
        """Update an existing memory item (matched by id)."""
        if item.id not in self._items:
            raise KeyError(f"MemoryItem '{item.id}' not found")
        self._policy.validate_write(item, is_update=True)
        item.mark_updated()
        self._items[item.id] = item
        self._save()

    def delete(self, id: str) -> bool:
        """Hard-delete a memory by id. Returns True if it existed."""
        if id in self._items:
            del self._items[id]
            self._save()
            return True
        return False

    def list_all(self) -> list[MemoryItem]:
        """Return every stored item."""
        return list(self._items.values())

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def find_by_tags(self, tags: list[str], match_all: bool = False) -> list[MemoryItem]:
        """Find memories whose tags overlap with *tags*.

        Args:
            tags: Tags to search for.
            match_all: If True, the memory must contain ALL given tags.
        """
        tag_set = set(t.lower() for t in tags)
        results = []
        for item in self._items.values():
            item_tags = set(t.lower() for t in item.tags)
            if match_all:
                if tag_set.issubset(item_tags):
                    results.append(item)
            else:
                if tag_set & item_tags:
                    results.append(item)
        return results

    def find_by_polarity(self, polarity: Polarity) -> list[MemoryItem]:
        """Return all memories with the given polarity."""
        return [i for i in self._items.values() if i.polarity == polarity]

    def find_by_layer(self, layer: Layer) -> list[MemoryItem]:
        """Return all memories at the given layer."""
        return [i for i in self._items.values() if i.layer == layer]

    def find_by_status(self, status: Status) -> list[MemoryItem]:
        """Return all memories with the given status."""
        return [i for i in self._items.values() if i.status == status]

    def find_similar(
        self, content: str, threshold: float = 0.7
    ) -> list[MemoryItem]:
        """Naive keyword-overlap similarity search.

        This is a placeholder for Phase 2 embedding-based retrieval.
        """
        if not tokenize_text(content):
            return []

        scored: list[tuple[float, MemoryItem]] = []
        for item in self._items.values():
            overlap = token_jaccard(content, item.content)
            if overlap >= threshold:
                scored.append((overlap, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored]

    def count(self) -> int:
        """Return the total number of stored items."""
        return len(self._items)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save(self) -> None:
        data = {
            "version": SCHEMA_VERSION,
            "items": [item.to_dict() for item in self._items.values()],
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self._path)  # atomic on same filesystem

    def _load(self) -> None:
        try:
            with open(self._path, encoding="utf-8") as f:
                text = f.read().strip()
            if not text:
                return
            data = json.loads(text)
        except (json.JSONDecodeError, FileNotFoundError):
            return
        for raw in data.get("items", []):
            item = MemoryItem.from_dict(raw)
            self._items[item.id] = item


class MemoryWorkspace:
    """Directory-backed coordination point for the standalone SDK."""

    def __init__(self, root: str | Path = ".memoryweaver"):
        from memoryweaver.composer import PatternStore
        from memoryweaver.evidence import EvidenceStore
        from memoryweaver.graph_store import GraphStore

        self.root = Path(root)
        self.memory_policy = MemoryPolicy()
        self.retrieval_policy = RetrievalPolicy()
        self.memories = MemoryStore(
            self.root / "memories.json",
            policy=self.memory_policy,
        )
        self.patterns = PatternStore(
            self.root / "patterns.json",
            policy=self.retrieval_policy,
        )
        self.evidence = EvidenceStore(
            self.root / "evidence_nodes.json",
            self.root / "evidence_links.json",
        )
        self.graph = GraphStore(self.root / "graph.json")

    def validate(self) -> dict[str, Any]:
        """Return structural errors and compatibility warnings."""
        errors: list[str] = []
        warnings: list[str] = []
        paths = [
            self.root / "memories.json",
            self.root / "patterns.json",
            self.root / "evidence_nodes.json",
            self.root / "evidence_links.json",
            self.root / "graph.json",
        ]
        for path in paths:
            if not path.exists():
                warnings.append(f"missing optional empty store: {path.name}")
                continue
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                errors.append(f"invalid JSON in {path.name}: {exc}")

        for item in self.memories.list_all():
            if item.legacy_pattern:
                warnings.append(f"legacy Layer-3 MemoryItem: {item.id}")
            if item.source.value in ("assistant", "synthetic") and (
                item.polarity.value != "ambiguous" or item.confidence > 0.3
            ):
                errors.append(f"polluting unverified memory: {item.id}")

        errors.extend(self.evidence.validate_links(
            {item.id for item in self.memories.list_all()},
            {pattern.id for pattern in self.patterns.list_all()},
        ))
        for pattern in self.patterns.list_all():
            if pattern.policy_version != self.memory_policy.version:
                warnings.append(f"stale pattern policy version: {pattern.id}")
        errors.extend(self.graph.validate_refs(
            memory_ids={item.id for item in self.memories.list_all()},
            evidence_ids={node.id for node in self.evidence.list_nodes()},
            pattern_ids={pattern.id for pattern in self.patterns.list_all()},
        ))

        if token_jaccard("检查组织选择解决订阅问题", "订阅问题检查组织选择") <= 0:
            errors.append("Chinese lexical retrieval probe failed")

        return {
            "valid": not errors,
            "schema_version": SCHEMA_VERSION,
            "memory_policy_version": self.memory_policy.version,
            "retrieval_policy_version": self.retrieval_policy.version,
            "errors": errors,
            "warnings": warnings,
        }
