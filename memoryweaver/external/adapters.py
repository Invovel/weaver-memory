"""Adapters from external memory benchmarks into MemoryWeaver primitives."""

from __future__ import annotations

import json
import re
from typing import Any, Iterable

from memoryweaver.content_router import ContentRouter
from memoryweaver.context_schema import ContentType, ContextCapsule, RawSpan
from memoryweaver.external.schema import ExternalEpisode, ExternalQuery, ExternalTurn
from memoryweaver.policy import MemoryPolicy
from memoryweaver.schema import (
    Freshness,
    Layer,
    MemoryItem,
    MemoryType,
    Polarity,
    Source,
    Status,
)
from memoryweaver.store import tokenize_text


DATASET_REPOS = {
    "memoryagentbench": "ai-hyz/MemoryAgentBench",
    "longmemeval": "mteb/LongMemEval",
    "longmemeval-v2": "xiaowu0162/longmemeval-v2",
    "locomo": "mteb/LoCoMo",
}


def adapt_external_record(dataset_id: str, record: dict[str, Any]) -> ExternalEpisode:
    """Convert a broad external row shape into a canonical episode.

    The mapping is deliberately permissive: the v0.6.4 milestone is a dry-run
    adapter spike, not a full reproduction of each benchmark runtime.
    """

    normalized_id = _normalize_dataset_id(dataset_id)
    if normalized_id == "memoryagentbench":
        return _adapt_memoryagentbench(record)
    if normalized_id == "longmemeval-v2":
        return _adapt_longmemeval_v2(record)
    if normalized_id == "longmemeval":
        return _adapt_longmemeval(record)
    if normalized_id == "locomo":
        return _adapt_locomo(record)
    raise ValueError(f"unsupported external dataset: {dataset_id}")


def external_episode_to_raw_spans(episode: ExternalEpisode) -> list[RawSpan]:
    raw_spans: list[RawSpan] = []
    for turn in episode.turns:
        raw_spans.append(
            RawSpan(
                id=f"raw_{episode.dataset_id}_{episode.episode_id}_{turn.id}",
                content=turn.content,
                content_type=turn.content_type,
                source=turn.source,
                timestamp=turn.timestamp,
                metadata={
                    "dataset_id": episode.dataset_id,
                    "source_repo": episode.source_repo,
                    "split": episode.split,
                    "episode_id": episode.episode_id,
                    "turn_id": turn.id,
                    "role": turn.role,
                    "tags": turn.tags,
                    **turn.metadata,
                },
            )
        )
    return raw_spans


def build_context_capsules(raw_spans: Iterable[RawSpan]) -> list[ContextCapsule]:
    router = ContentRouter()
    return [router.compress(raw_span) for raw_span in raw_spans]


def build_candidate_memories(
    capsules: Iterable[ContextCapsule],
    *,
    policy: MemoryPolicy | None = None,
) -> tuple[list[MemoryItem], list[dict[str, Any]]]:
    """Dry-run Layer-1 candidates from capsules and report policy violations."""

    memory_policy = policy or MemoryPolicy()
    memories: list[MemoryItem] = []
    violations: list[dict[str, Any]] = []
    for capsule in capsules:
        item = MemoryItem(
            id=f"mem_ext_{capsule.id.removeprefix('cap_')}",
            layer=Layer.CANDIDATE,
            polarity=_polarity_from_capsule(capsule),
            memory_type=_memory_type_from_capsule(capsule),
            content=capsule.summary,
            tags=sorted(set(capsule.tags)),
            source=capsule.source,
            evidence=f"raw_ref_id={capsule.raw_ref_id}",
            scope="external_benchmark",
            confidence=_initial_confidence(capsule.source),
            freshness=_freshness_from_tags(capsule.tags),
            status=Status.CANDIDATE,
        )
        try:
            memory_policy.validate_write(item)
        except ValueError as exc:
            violations.append({"capsule_id": capsule.id, "error": str(exc)})
        raw_source = capsule.metadata.get("raw_source")
        if raw_source and raw_source != item.source.value:
            violations.append(
                {
                    "capsule_id": capsule.id,
                    "error": "candidate source differs from raw source",
                }
            )
        if item.source in (Source.ASSISTANT, Source.SYNTHETIC):
            if item.polarity != Polarity.AMBIGUOUS or item.confidence > 0.3:
                violations.append(
                    {
                        "capsule_id": capsule.id,
                        "error": "untrusted candidate bypassed policy",
                    }
                )
        if item.layer != Layer.CANDIDATE:
            violations.append(
                {
                    "capsule_id": capsule.id,
                    "error": "external adapter created non-candidate memory",
                }
            )
        memories.append(item)
    return memories, violations


def _adapt_memoryagentbench(record: dict[str, Any]) -> ExternalEpisode:
    episode_id = _record_id(record, "mab")
    return ExternalEpisode(
        dataset_id="memoryagentbench",
        source_repo=DATASET_REPOS["memoryagentbench"],
        split=str(record.get("split", "validation")),
        episode_id=episode_id,
        turns=_turns_from_record("memoryagentbench", episode_id, record),
        queries=_queries_from_record("memoryagentbench", episode_id, record),
        metadata={
            "task_type": record.get("task_type", record.get("category", "")),
            "external_schema_version": "adapter-v0.6.4",
        },
    )


def _adapt_longmemeval(record: dict[str, Any]) -> ExternalEpisode:
    episode_id = _record_id(record, "lme")
    return ExternalEpisode(
        dataset_id="longmemeval",
        source_repo=DATASET_REPOS["longmemeval"],
        split=str(record.get("split", "validation")),
        episode_id=episode_id,
        turns=_turns_from_record("longmemeval", episode_id, record),
        queries=_queries_from_record("longmemeval", episode_id, record),
        metadata={
            "question_type": record.get("question_type", record.get("category", "")),
            "external_schema_version": "adapter-v0.6.4",
        },
    )


def _adapt_longmemeval_v2(record: dict[str, Any]) -> ExternalEpisode:
    episode_id = _record_id(record, "lmev2")
    return ExternalEpisode(
        dataset_id="longmemeval-v2",
        source_repo=DATASET_REPOS["longmemeval-v2"],
        split=str(record.get("split", "local_probe")),
        episode_id=episode_id,
        turns=_turns_from_record("longmemeval-v2", episode_id, record),
        queries=_queries_from_record("longmemeval-v2", episode_id, record),
        metadata={
            "question_type": record.get("question_type", record.get("category", "")),
            "domain": record.get("domain", ""),
            "environment": record.get("environment", ""),
            "external_schema_version": "adapter-v0.6.4a",
        },
    )


def _adapt_locomo(record: dict[str, Any]) -> ExternalEpisode:
    episode_id = _record_id(record, "locomo")
    return ExternalEpisode(
        dataset_id="locomo",
        source_repo=DATASET_REPOS["locomo"],
        split=str(record.get("split", "validation")),
        episode_id=episode_id,
        turns=_turns_from_record("locomo", episode_id, record),
        queries=_queries_from_record("locomo", episode_id, record),
        metadata={
            "reasoning_type": record.get("reasoning_type", record.get("category", "")),
            "external_schema_version": "adapter-v0.6.4",
        },
    )


def _turns_from_record(
    dataset_id: str,
    episode_id: str,
    record: dict[str, Any],
) -> list[ExternalTurn]:
    raw_turns = _first_list(record, ["turns", "messages", "history", "conversation", "sessions"])
    if not raw_turns:
        context = record.get("context", record.get("memory", record.get("haystack", "")))
        raw_turns = [{"role": "user", "content": str(context)}] if context else []
    turns: list[ExternalTurn] = []
    for index, raw in enumerate(raw_turns, 1):
        payload = {"role": "user", "content": raw} if isinstance(raw, str) else dict(raw)
        role = str(payload.get("role", payload.get("speaker", payload.get("source", "user"))))
        content = str(payload.get("content", payload.get("text", payload.get("utterance", ""))))
        source = _source_from_role(role, payload)
        turns.append(
            ExternalTurn(
                id=str(payload.get("id", payload.get("turn_id", f"t{index:03d}"))),
                role=role,
                content=content,
                source=source,
                content_type=_content_type_from_payload(source, payload, content),
                timestamp=str(
                    payload.get(
                        "timestamp",
                        payload.get("time", f"2026-01-01T00:{index:02d}:00+00:00"),
                    )
                ),
                tags=_tags_from_values(dataset_id, role, content, payload.get("tags", [])),
                metadata={
                    "external_dataset_id": dataset_id,
                    "episode_id": episode_id,
                    "raw_role": role,
                },
            )
        )
    return turns


def _queries_from_record(
    dataset_id: str,
    episode_id: str,
    record: dict[str, Any],
) -> list[ExternalQuery]:
    raw_queries = _first_list(record, ["queries", "questions", "qa_pairs"])
    if not raw_queries:
        query_text = record.get("query", record.get("question", record.get("task", "")))
        if query_text:
            raw_queries = [
                {
                    "query": query_text,
                    "answer": record.get("answer", record.get("gold_answer", "")),
                    "id": record.get("query_id", record.get("qa_pair_id", "q001")),
                }
            ]
    queries: list[ExternalQuery] = []
    for index, raw in enumerate(raw_queries, 1):
        payload = dict(raw) if isinstance(raw, dict) else {"query": str(raw)}
        query_text = str(payload.get("query", payload.get("question", payload.get("input", ""))))
        answer = str(payload.get("answer", payload.get("gold_answer", payload.get("target", ""))))
        tags = _tags_from_values(dataset_id, query_text, answer, payload.get("tags", []))
        queries.append(
            ExternalQuery(
                id=str(payload.get("id", payload.get("query_id", f"q{index:03d}"))),
                query=query_text,
                answer=answer,
                tags=tags,
                expected_evidence_tags=list(payload.get("expected_evidence_tags", tags[:4])),
                signal_types=_signal_types(query_text, answer, tags, payload, record),
                metadata={
                    "external_dataset_id": dataset_id,
                    "episode_id": episode_id,
                    "raw_query_index": index,
                },
            )
        )
    return queries


def _normalize_dataset_id(dataset_id: str) -> str:
    lowered = dataset_id.lower().replace("_", "-")
    if "memoryagentbench" in lowered or "memory-agent" in lowered:
        return "memoryagentbench"
    if "longmemeval-v2" in lowered or "lme-v2" in lowered:
        return "longmemeval-v2"
    if "longmemeval" in lowered:
        return "longmemeval"
    if "locomo" in lowered:
        return "locomo"
    return lowered


def _record_id(record: dict[str, Any], prefix: str) -> str:
    for key in ["episode_id", "id", "uuid", "qa_pair_id", "question_id"]:
        if record.get(key):
            return _safe_id(str(record[key]))
    payload = json.dumps(record, sort_keys=True, default=str)
    return f"{prefix}_{abs(hash(payload)) % 100000:05d}"


def _first_list(record: dict[str, Any], keys: list[str]) -> list[Any]:
    for key in keys:
        value = record.get(key)
        if isinstance(value, list):
            return value
    return []


def _source_from_role(role: str, payload: dict[str, Any]) -> Source:
    explicit = str(payload.get("source", "")).lower()
    value = explicit or role.lower()
    if value in {"human", "user", "customer"}:
        return Source.USER
    if value in {"assistant", "agent", "model", "llm"}:
        return Source.ASSISTANT
    if value in {"tool", "tool_call", "observation", "api"}:
        return Source.TOOL
    if value in {"terminal", "shell", "console"}:
        return Source.TERMINAL
    if value in {"web", "browser"}:
        return Source.WEB
    if value in {"file", "repo"}:
        return Source.FILE
    return Source.UNKNOWN


def _content_type_from_payload(
    source: Source,
    payload: dict[str, Any],
    content: str,
) -> ContentType:
    explicit = payload.get("content_type")
    if explicit:
        return ContentType(str(explicit))
    if source == Source.TERMINAL:
        return ContentType.TERMINAL_LOG
    if source == Source.TOOL:
        return ContentType.TOOL_JSON if _looks_json(content) else ContentType.TRACE_RECORD
    return ContentType.CONVERSATION_TURN


def _looks_json(value: str) -> bool:
    stripped = value.strip()
    return stripped.startswith("{") and stripped.endswith("}")


def _tags_from_values(*values: Any) -> list[str]:
    tags: set[str] = set()
    for value in values:
        if isinstance(value, list):
            for item in value:
                tags.update(_tags_from_values(item))
            continue
        text = str(value)
        tags.update(tokenize_text(text))
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_/-]*", text):
            tags.add(token.lower().replace("_", "-"))
    return sorted(tag for tag in tags if tag)


def _signal_types(*values: Any) -> list[str]:
    text = " ".join(str(value).lower() for value in values)
    signals: set[str] = set()
    if any(
        token in text
        for token in ["conflict", "contradict", "correction", "wrong", "changed", "outdated"]
    ):
        signals.add("conflict")
    if any(
        token in text
        for token in ["temporal", "time", "timestamp", "previous", "recent", "latest", "before", "after"]
    ):
        signals.add("temporal")
    if any(token in text for token in ["tool", "terminal", "api", "command", "trace"]):
        signals.add("tool")
    return sorted(signals)


def _polarity_from_capsule(capsule: ContextCapsule) -> Polarity:
    tags = {tag.lower() for tag in capsule.tags}
    summary = capsule.summary.lower()
    if capsule.source in (Source.ASSISTANT, Source.SYNTHETIC):
        return Polarity.AMBIGUOUS
    if tags.intersection({"correction", "wrong", "failed", "error"}) or "failed" in summary:
        return Polarity.NEGATIVE
    if tags.intersection({"success", "resolved", "positive"}):
        return Polarity.POSITIVE
    return Polarity.NEUTRAL


def _memory_type_from_capsule(capsule: ContextCapsule) -> MemoryType:
    tags = {tag.lower() for tag in capsule.tags}
    if "correction" in tags:
        return MemoryType.CORRECTION
    if tags.intersection({"failed", "error"}):
        return MemoryType.FAILED_ATTEMPT
    return MemoryType.FACT


def _initial_confidence(source: Source) -> float:
    if source in (Source.USER, Source.TERMINAL):
        return 0.7
    if source == Source.TOOL:
        return 0.6
    if source in (Source.FILE, Source.WEB):
        return 0.5
    if source == Source.ASSISTANT:
        return 0.8
    return 0.0


def _freshness_from_tags(tags: list[str]) -> Freshness:
    lowered = {tag.lower() for tag in tags}
    if lowered.intersection({"latest", "recent", "changed", "temporal"}):
        return Freshness.VOLATILE
    return Freshness.UNKNOWN


def _safe_id(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")
    return safe or "external_episode"
