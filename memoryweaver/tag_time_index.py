"""Tag/time index for ContextCapsule lookup."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from memoryweaver.context_schema import ContextCapsule, ContentType, Source
from memoryweaver.store import SCHEMA_VERSION, atomic_write_json


class TagTimeIndex:
    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._tag_index: dict[str, set[str]] = defaultdict(set)
        self._time_index: dict[str, set[str]] = defaultdict(set)
        self._capsule_meta: dict[str, dict[str, Any]] = {}
        self._load()

    def add(self, capsule: ContextCapsule) -> None:
        for tag in capsule.tags:
            self._tag_index[tag.lower()].add(capsule.id)
        bucket = time_bucket(capsule.timestamp)
        self._time_index[bucket].add(capsule.id)
        self._capsule_meta[capsule.id] = {
            "timestamp": capsule.timestamp,
            "time_bucket": bucket,
            "source": capsule.source.value,
            "content_type": capsule.content_type.value,
            "tags": list(capsule.tags),
        }
        self._save()

    def rebuild(self, capsules: list[ContextCapsule]) -> None:
        self._tag_index.clear()
        self._time_index.clear()
        self._capsule_meta.clear()
        for capsule in capsules:
            for tag in capsule.tags:
                self._tag_index[tag.lower()].add(capsule.id)
            bucket = time_bucket(capsule.timestamp)
            self._time_index[bucket].add(capsule.id)
            self._capsule_meta[capsule.id] = {
                "timestamp": capsule.timestamp,
                "time_bucket": bucket,
                "source": capsule.source.value,
                "content_type": capsule.content_type.value,
                "tags": list(capsule.tags),
            }
        self._save()

    def search(
        self,
        *,
        tags: list[str] | None = None,
        since: str = "",
        until: str = "",
        sources: list[Source] | None = None,
        content_types: list[ContentType] | None = None,
        match_all: bool = False,
    ) -> list[str]:
        candidates: set[str] | None = None
        if tags:
            for tag in tags:
                ids = set(self._tag_index.get(tag.lower(), set()))
                if candidates is None:
                    candidates = ids
                elif match_all:
                    candidates &= ids
                else:
                    candidates |= ids
        if candidates is None:
            candidates = set(self._capsule_meta)
        source_values = {source.value if isinstance(source, Source) else str(source) for source in (sources or [])}
        type_values = {
            content_type.value if isinstance(content_type, ContentType) else str(content_type)
            for content_type in (content_types or [])
        }
        results = []
        for capsule_id in candidates:
            meta = self._capsule_meta.get(capsule_id, {})
            timestamp = str(meta.get("timestamp", ""))
            if since and timestamp < since:
                continue
            if until and timestamp > until:
                continue
            if source_values and meta.get("source") not in source_values:
                continue
            if type_values and meta.get("content_type") not in type_values:
                continue
            results.append(capsule_id)
        results.sort(key=lambda capsule_id: self._capsule_meta[capsule_id]["timestamp"], reverse=True)
        return results

    def tag_recall(self, expected: dict[str, list[str]]) -> float:
        if not expected:
            return 1.0
        hits = 0
        total = 0
        for tag, capsule_ids in expected.items():
            indexed = self._tag_index.get(tag.lower(), set())
            for capsule_id in capsule_ids:
                total += 1
                if capsule_id in indexed:
                    hits += 1
        return hits / total if total else 1.0

    def _save(self) -> None:
        atomic_write_json(
            self._path,
            {
                "version": SCHEMA_VERSION,
                "tag_index": {key: sorted(value) for key, value in self._tag_index.items()},
                "time_index": {key: sorted(value) for key, value in self._time_index.items()},
                "capsule_meta": self._capsule_meta,
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
        self._tag_index = defaultdict(set, {
            key: set(value) for key, value in data.get("tag_index", {}).items()
        })
        self._time_index = defaultdict(set, {
            key: set(value) for key, value in data.get("time_index", {}).items()
        })
        self._capsule_meta = data.get("capsule_meta", {})


def time_bucket(timestamp: str) -> str:
    try:
        normalized = timestamp.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H")
    except ValueError:
        return timestamp[:13]
