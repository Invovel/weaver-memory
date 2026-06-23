"""MemoryAgentBench Hugging Face preview adapter helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from memoryweaver.context_schema import ContentType
from memoryweaver.external.schema import ExternalEpisode, ExternalQuery, ExternalTurn
from memoryweaver.schema import Source


DATASET_REPO_ID = "ai-hyz/MemoryAgentBench"
DEFAULT_CONFIG = "default"
DEFAULT_SPLITS = (
    "Accurate_Retrieval",
    "Test_Time_Learning",
    "Long_Range_Understanding",
    "Conflict_Resolution",
)
DATASET_VIEWER_BASE = "https://datasets-server.huggingface.co"


def fetch_memoryagentbench_preview(
    *,
    splits: tuple[str, ...] = DEFAULT_SPLITS,
    config: str = DEFAULT_CONFIG,
    sample_limit_per_split: int = 1,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    split_metadata: list[dict[str, Any]] = []
    for split in splits:
        params = urlencode({"dataset": DATASET_REPO_ID, "config": config, "split": split})
        request = Request(
            f"{DATASET_VIEWER_BASE}/first-rows?{params}",
            headers={"User-Agent": "MemoryWeaver-validation/0.1"},
        )
        with urlopen(request, timeout=60) as response:
            payload = json.load(response)
        raw_rows = payload.get("rows", [])[:sample_limit_per_split]
        for item in raw_rows:
            row = dict(item.get("row", {}))
            row["_split"] = split
            row["_row_idx"] = item.get("row_idx")
            row["_truncated_cells"] = item.get("truncated_cells", [])
            rows.append(row)
        split_metadata.append(
            {
                "split": split,
                "feature_names": [feature.get("name", "") for feature in payload.get("features", [])],
                "preview_row_count": len(payload.get("rows", [])),
                "sampled_row_count": len(raw_rows),
            }
        )
    return rows, {
        "dataset": DATASET_REPO_ID,
        "config": config,
        "splits": list(splits),
        "sample_limit_per_split": sample_limit_per_split,
        "split_metadata": split_metadata,
    }


def load_memoryagentbench_rows(path: Path, *, sample_limit: int | None = None) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        payload = json.loads(text)
        rows = payload if isinstance(payload, list) else [payload]
    return rows[:sample_limit] if sample_limit is not None else rows


def memoryagentbench_row_to_episode(row: dict[str, Any]) -> ExternalEpisode:
    split = str(row.get("_split") or row.get("split") or "preview")
    row_idx = row.get("_row_idx", row.get("id", 0))
    episode_id = _safe_id(f"{split}_{row_idx}")
    context = _stringify(_maybe_json(row.get("context", "")))
    metadata = _metadata(row)
    questions = _as_list(_maybe_json(row.get("questions", [])))
    answers = _as_list(_maybe_json(row.get("answers", [])))
    qa_pair_ids = _as_list(metadata.get("qa_pair_ids", []))

    turns = [
        ExternalTurn(
            id="context",
            role="external_context",
            content=context,
            source=Source.FILE,
            content_type=ContentType.TEXT,
            timestamp="2026-01-01T00:00:00+00:00",
            tags=_tags("memoryagentbench", split, "context"),
            metadata={
                "external_dataset_id": "memoryagentbench",
                "split": split,
                "truncated_cells": row.get("_truncated_cells", []),
            },
        )
    ]
    for index, event in enumerate(_as_list(metadata.get("previous_events", [])), start=1):
        turns.append(
            ExternalTurn(
                id=f"previous_event_{index:03d}",
                role="previous_event",
                content=_stringify(event),
                source=Source.FILE,
                content_type=ContentType.TEXT,
                timestamp=f"2026-01-01T00:{index:02d}:00+00:00",
                tags=_tags("memoryagentbench", split, "previous_event"),
                metadata={"external_dataset_id": "memoryagentbench", "split": split},
            )
        )

    queries: list[ExternalQuery] = []
    for index, question in enumerate(questions, start=1):
        answer = answers[index - 1] if index - 1 < len(answers) else ""
        answer_text = _answer_text(answer)
        query_id = str(qa_pair_ids[index - 1]) if index - 1 < len(qa_pair_ids) else f"q{index:03d}"
        queries.append(
            ExternalQuery(
                id=_safe_id(query_id),
                query=str(question),
                answer=answer_text,
                tags=_tags("memoryagentbench", split, question, answer_text),
                expected_evidence_tags=_tags(answer_text, split)[:4],
                signal_types=_signal_types(split, question, answer_text, metadata),
                metadata={
                    "external_dataset_id": "memoryagentbench",
                    "split": split,
                    "raw_answer": answer,
                },
            )
        )

    return ExternalEpisode(
        dataset_id="memoryagentbench",
        source_repo=DATASET_REPO_ID,
        split=split,
        episode_id=episode_id,
        turns=turns,
        queries=queries,
        metadata={
            "external_schema_version": "memoryagentbench-preview-v0.9",
            "split": split,
            "truncated_cells": row.get("_truncated_cells", []),
        },
    )


def build_memoryagentbench_episodes(rows: list[dict[str, Any]]) -> list[ExternalEpisode]:
    return [memoryagentbench_row_to_episode(row) for row in rows]


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    raw = _maybe_json(row.get("metadata", {}))
    return raw if isinstance(raw, dict) else {}


def _maybe_json(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _answer_text(value: Any) -> str:
    if isinstance(value, list):
        return " | ".join(str(item) for item in value)
    return str(value)


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _tags(*values: Any) -> list[str]:
    tags: set[str] = set()
    for value in values:
        for token in str(value).replace("_", " ").replace("-", " ").split():
            cleaned = "".join(ch for ch in token.lower() if ch.isalnum())
            if cleaned:
                tags.add(cleaned)
    return sorted(tags)


def _signal_types(*values: Any) -> list[str]:
    text = " ".join(str(value).lower() for value in values)
    signals: set[str] = set()
    if any(token in text for token in ["conflict", "contradict", "wrong", "resolution"]):
        signals.add("conflict")
    if any(token in text for token in ["test_time", "learning", "previous", "long_range"]):
        signals.add("temporal")
    if any(token in text for token in ["retrieval", "accurate"]):
        signals.add("retrieval")
    return sorted(signals)


def _safe_id(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in str(value))
    return cleaned.strip("_") or "memoryagentbench_row"
