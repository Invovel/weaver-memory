"""JSON-file-based memory store.

Provides CRUD operations and basic query-by-tag / query-by-polarity
on a local JSON file. Designed to be replaced by a vector DB in later
phases without changing the public API.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from memoryweaver.schema import MemoryItem, Layer, Polarity, Status


class MemoryStore:
    """Local JSON-backed store for MemoryItem objects.

    Usage:
        store = MemoryStore("memory.json")
        store.add(item)
        results = store.find_by_tags(["wsl", "codex"])
    """

    def __init__(self, path: str | Path = "memory.json"):
        self._path = Path(path)
        self._items: dict[str, MemoryItem] = {}
        if self._path.exists():
            self._load()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add(self, item: MemoryItem) -> str:
        """Insert a memory item. Returns its id."""
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
        query_words = set(content.lower().split())
        if not query_words:
            return []

        scored: list[tuple[float, MemoryItem]] = []
        for item in self._items.values():
            item_words = set(item.content.lower().split())
            if not item_words:
                continue
            overlap = len(query_words & item_words) / len(query_words | item_words)
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
            "version": "0.1.0",
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
