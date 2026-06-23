"""Atomic JSON stores for RawSpan, ContextCapsule, and marker contexts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from memoryweaver.context_schema import (
    ContextCapsule,
    MarkerEvidenceContext,
    RawSpan,
)
from memoryweaver.store import SCHEMA_VERSION, atomic_write_json


class RawSpanStore:
    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._items: dict[str, RawSpan] = {}
        self._load()

    def add(self, raw_span: RawSpan) -> str:
        self._items[raw_span.id] = raw_span
        self._save()
        return raw_span.id

    def get(self, raw_span_id: str) -> Optional[RawSpan]:
        return self._items.get(raw_span_id)

    def list_all(self) -> list[RawSpan]:
        return list(self._items.values())

    def _save(self) -> None:
        _atomic_save(
            self._path,
            {"version": SCHEMA_VERSION, "raw_spans": [item.to_dict() for item in self._items.values()]},
        )

    def _load(self) -> None:
        for raw in _load_collection(self._path, "raw_spans"):
            item = RawSpan.from_dict(raw)
            self._items[item.id] = item


class ContextCapsuleStore:
    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._items: dict[str, ContextCapsule] = {}
        self._load()

    def add(self, capsule: ContextCapsule) -> str:
        self._items[capsule.id] = capsule
        self._save()
        return capsule.id

    def get(self, capsule_id: str) -> Optional[ContextCapsule]:
        return self._items.get(capsule_id)

    def list_all(self) -> list[ContextCapsule]:
        return list(self._items.values())

    def validate_raw_refs(self, raw_ids: set[str]) -> list[str]:
        errors: list[str] = []
        for capsule in self._items.values():
            if capsule.raw_ref_id not in raw_ids:
                errors.append(f"missing raw_ref_id for capsule: {capsule.id}")
            if capsule.source.value != capsule.metadata.get("raw_source", capsule.source.value):
                errors.append(f"source inheritance violation: {capsule.id}")
        return errors

    def _save(self) -> None:
        _atomic_save(
            self._path,
            {"version": SCHEMA_VERSION, "context_capsules": [item.to_dict() for item in self._items.values()]},
        )

    def _load(self) -> None:
        for raw in _load_collection(self._path, "context_capsules"):
            item = ContextCapsule.from_dict(raw)
            self._items[item.id] = item


class MarkerEvidenceContextStore:
    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._items: dict[str, MarkerEvidenceContext] = {}
        self._load()

    def add(self, context: MarkerEvidenceContext) -> str:
        self._items[context.marker_id] = context
        self._save()
        return context.marker_id

    def get(self, marker_id: str) -> Optional[MarkerEvidenceContext]:
        return self._items.get(marker_id)

    def list_all(self) -> list[MarkerEvidenceContext]:
        return list(self._items.values())

    def _save(self) -> None:
        _atomic_save(
            self._path,
            {"version": SCHEMA_VERSION, "marker_evidence_contexts": [item.to_dict() for item in self._items.values()]},
        )

    def _load(self) -> None:
        for raw in _load_collection(self._path, "marker_evidence_contexts"):
            item = MarkerEvidenceContext.from_dict(raw)
            self._items[item.marker_id] = item


def _atomic_save(path: Path, data: dict[str, Any]) -> None:
    atomic_write_json(path, data)


def _load_collection(path: Path, key: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8").strip()
        return json.loads(text).get(key, []) if text else []
    except (json.JSONDecodeError, FileNotFoundError):
        return []
