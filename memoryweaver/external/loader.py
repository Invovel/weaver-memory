"""Small JSON/JSONL loader helpers for external adapter experiments."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from memoryweaver.external.adapters import adapt_external_record
from memoryweaver.external.schema import ExternalEpisode


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def load_json(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [dict(item) for item in data]
    if isinstance(data, dict) and isinstance(data.get("records"), list):
        return [dict(item) for item in data["records"]]
    return [dict(data)]


def load_external_records(dataset_id: str, path: Path) -> list[ExternalEpisode]:
    records = load_jsonl(path) if path.suffix == ".jsonl" else load_json(path)
    return [adapt_external_record(dataset_id, record) for record in records]
