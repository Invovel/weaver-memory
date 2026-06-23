"""LoCoMo-MC10 Hugging Face adapter helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from memoryweaver.context_schema import ContentType
from memoryweaver.external.schema import ExternalEpisode, ExternalQuery, ExternalTurn
from memoryweaver.schema import Source


DATASET_REPO_ID = "Percena/locomo-mc10"
DEFAULT_CONFIG = "default"
DEFAULT_SPLIT = "train"
DATASET_VIEWER_BASE = "https://datasets-server.huggingface.co"


def fetch_locomo_mc10_preview(
    *,
    config: str = DEFAULT_CONFIG,
    split: str = DEFAULT_SPLIT,
    sample_limit: int = 5,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fetch a small read-only preview from Hugging Face Dataset Viewer."""

    params = urlencode({"dataset": DATASET_REPO_ID, "config": config, "split": split})
    request = Request(
        f"{DATASET_VIEWER_BASE}/first-rows?{params}",
        headers={"User-Agent": "MemoryWeaver-validation/0.1"},
    )
    with urlopen(request, timeout=45) as response:
        payload = json.load(response)
    rows = [item["row"] for item in payload.get("rows", [])[:sample_limit]]
    metadata = {
        "dataset": payload.get("dataset", DATASET_REPO_ID),
        "config": payload.get("config", config),
        "split": payload.get("split", split),
        "feature_names": [feature.get("name", "") for feature in payload.get("features", [])],
        "preview_row_count": len(payload.get("rows", [])),
        "sample_limit": sample_limit,
    }
    return rows, metadata


def load_locomo_mc10_rows(path: Path, *, sample_limit: int | None = None) -> list[dict[str, Any]]:
    """Load rows from a JSON/JSONL fixture or exported preview."""

    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        payload = json.loads(text)
        if isinstance(payload, list):
            rows = payload
        elif "rows" in payload:
            rows = [item.get("row", item) for item in payload["rows"]]
        else:
            rows = [payload]
    return rows[:sample_limit] if sample_limit is not None else rows


def locomo_mc10_row_to_episode(row: dict[str, Any], *, split: str = DEFAULT_SPLIT) -> ExternalEpisode:
    """Convert one LoCoMo-MC10 row into a MemoryWeaver ExternalEpisode."""

    episode_id = str(row.get("question_id") or row.get("id") or "locomo_mc10_row")
    turns: list[ExternalTurn] = []
    session_ids = list(row.get("haystack_session_ids") or [])
    summaries = list(row.get("haystack_session_summaries") or [])
    datetimes = list(row.get("haystack_session_datetimes") or [])
    sessions = list(row.get("haystack_sessions") or [])

    for session_index, summary in enumerate(summaries, start=1):
        session_id = _session_id(session_ids, session_index)
        turns.append(
            ExternalTurn(
                id=f"{session_id}_summary",
                role="dataset_summary",
                content=str(summary),
                source=Source.FILE,
                content_type=ContentType.TEXT,
                timestamp=_session_timestamp(datetimes, session_index),
                tags=_tags("locomo-mc10", session_id, "summary", row.get("question_type", "")),
                metadata={
                    "external_dataset_id": "locomo-mc10",
                    "session_id": session_id,
                    "summary_index": session_index,
                },
            )
        )

    for session_index, session_turns in enumerate(sessions, start=1):
        session_id = _session_id(session_ids, session_index)
        if not isinstance(session_turns, list):
            continue
        for turn_index, raw_turn in enumerate(session_turns, start=1):
            if not isinstance(raw_turn, dict):
                continue
            role = str(raw_turn.get("role", "user"))
            content = str(raw_turn.get("content", raw_turn.get("text", "")))
            turns.append(
                ExternalTurn(
                    id=f"{session_id}_turn_{turn_index:03d}",
                    role=role,
                    content=content,
                    source=_source_from_role(role),
                    content_type=ContentType.CONVERSATION_TURN,
                    timestamp=_session_timestamp(datetimes, session_index),
                    tags=_tags("locomo-mc10", session_id, role, row.get("question_type", "")),
                    metadata={
                        "external_dataset_id": "locomo-mc10",
                        "session_id": session_id,
                        "turn_index": turn_index,
                    },
                )
            )

    question = str(row.get("question", ""))
    answer = str(row.get("answer", ""))
    choices = [str(item) for item in row.get("choices", [])]
    query = ExternalQuery(
        id=str(row.get("question_id", "q001")),
        query=question,
        answer=answer,
        tags=_tags("locomo-mc10", row.get("question_type", ""), question, answer),
        expected_evidence_tags=_tags(answer, row.get("question_type", ""))[:4],
        signal_types=_signal_types(question, answer, row.get("question_type", "")),
        metadata={
            "external_dataset_id": "locomo-mc10",
            "correct_choice_index": row.get("correct_choice_index"),
            "num_choices": row.get("num_choices"),
            "choices": choices,
            "num_sessions": row.get("num_sessions"),
        },
    )
    return ExternalEpisode(
        dataset_id="locomo-mc10",
        source_repo=DATASET_REPO_ID,
        split=split,
        episode_id=episode_id,
        turns=turns,
        queries=[query],
        metadata={
            "question_type": row.get("question_type", ""),
            "external_schema_version": "locomo-mc10-preview-v0.9",
            "num_choices": row.get("num_choices"),
            "num_sessions": row.get("num_sessions"),
        },
    )


def build_locomo_mc10_episodes(
    rows: list[dict[str, Any]],
    *,
    split: str = DEFAULT_SPLIT,
) -> list[ExternalEpisode]:
    return [locomo_mc10_row_to_episode(row, split=split) for row in rows]


def _source_from_role(role: str) -> Source:
    lowered = role.lower()
    if lowered in {"user", "human", "speaker_1", "speaker1"}:
        return Source.USER
    if lowered in {"assistant", "agent", "speaker_2", "speaker2"}:
        return Source.ASSISTANT
    return Source.UNKNOWN


def _session_id(session_ids: list[Any], index: int) -> str:
    if index - 1 < len(session_ids):
        return str(session_ids[index - 1])
    return f"session_{index}"


def _session_timestamp(datetimes: list[Any], index: int) -> str:
    if index - 1 < len(datetimes):
        value = str(datetimes[index - 1])
        if value:
            return value
    return f"2026-01-01T00:{index:02d}:00+00:00"


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
    if any(token in text for token in ["when", "date", "before", "after", "time", "temporal"]):
        signals.add("temporal")
    if any(token in text for token in ["multi", "hop", "adversarial"]):
        signals.add("multi_hop")
    if any(token in text for token in ["not", "wrong", "changed", "conflict"]):
        signals.add("conflict")
    return sorted(signals)
