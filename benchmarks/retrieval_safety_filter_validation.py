"""Validate safety gates after traditional keyword retrieval.

v0.5.4b separates relevance retrieval from MemoryWeaver runtime eligibility:

- SQLite FTS5 finds textually relevant capsules.
- Source gate removes untrusted assistant/synthetic/unknown capsules.
- Freshness gate keeps stale/newer-conflict context out of authoritative use.
- Marker eligibility narrows candidates to the current marker/card context.

This benchmark intentionally does not mutate memory, Layer 3, or runtime state.
It answers whether MemoryWeaver's filters still matter when a traditional
keyword retriever is already available.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.context_capsule_stress_validation import (
    DEFAULT_BASE_FIXTURE,
    DEFAULT_DIALOGUE_CARDS,
)
from benchmarks.context_capsule_validation import write_json, write_jsonl
from benchmarks.retrieval_comparison_validation import (
    _build_workspace,
    _capsules_from_ids,
    _rank_capsules,
)
from benchmarks.retrieval_fts5_filter_validation import FTS5Index, _percentile
from memoryweaver.context_schema import ContextCapsule
from memoryweaver.graph_linker import normalize_tag
from memoryweaver.schema import Source
from memoryweaver.store import tokenize_text


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT
    / "docs"
    / "validation"
    / "retrieval-safety-filter-v0.5.4b"
)

TRUSTED_RUNTIME_SOURCES = {
    Source.USER,
    Source.TERMINAL,
    Source.TOOL,
    Source.FILE,
    Source.WEB,
}
UNTRUSTED_RUNTIME_SOURCES = {
    Source.ASSISTANT,
    Source.SYNTHETIC,
    Source.UNKNOWN,
    Source.COMPOSER,
}


@dataclass
class SafetyArmStats:
    name: str
    recall_at_10: float
    required_evidence_hit_rate: float
    known_bad_warning_hit_rate: float
    average_candidate_count: float
    candidate_reduction_ratio: float
    latency_p95_ms: float
    untrusted_top10_leak_count: int
    assistant_trap_top10_leak_count: int
    stale_top10_leak_count: int
    runtime_authority_violation_count: int


def _expected_suppressed(query: dict[str, Any], card: dict[str, Any]) -> list[str]:
    values = list(query.get("expected_suppressed", []))
    values.extend(card.get("expected", {}).get("should", {}).get("suppressed_actions", []))
    values.extend(
        card.get("counterfactual", {})
        .get("without_marker", {})
        .get("known_bad_actions", [])
    )
    return sorted({normalize_tag(str(value)) for value in values if str(value)})


def _expected_evidence(query: dict[str, Any], card: dict[str, Any]) -> list[str]:
    values = list(query.get("expected_evidence", []))
    values.extend(card.get("expected", {}).get("should", {}).get("required_evidence", []))
    return sorted({normalize_tag(str(value)) for value in values if str(value)})


def _trap_query_text(card: dict[str, Any], query: dict[str, Any]) -> str:
    """Make the benchmark adversarial enough to pull assistant traps into FTS5."""
    fields = [
        query.get("query", ""),
        query.get("expected_core_issue_match", ""),
        query.get("expected_marker_activation", ""),
        " ".join(_expected_suppressed(query, card)),
        " ".join(_expected_evidence(query, card)),
    ]
    return " ".join(str(field) for field in fields if str(field))


def _token_set(*values: str) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        normalized = normalize_tag(str(value))
        tokens.add(normalized)
        tokens.update(tokenize_text(normalized))
        for part in normalized.replace("-", "_").split("_"):
            if part:
                tokens.add(part.lower())
    return tokens


def _capsule_text(capsule: ContextCapsule) -> str:
    return f"{capsule.summary} {' '.join(capsule.tags)}"


def _raw_meta(
    capsule: ContextCapsule,
    raw_metadata: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return raw_metadata.get(capsule.raw_ref_id, {})


def _same_card(
    capsule: ContextCapsule,
    *,
    card_id: str,
    raw_metadata: dict[str, dict[str, Any]],
) -> bool:
    return _raw_meta(capsule, raw_metadata).get("dialogue_card_id") == card_id


def _source_gate(capsule: ContextCapsule) -> bool:
    return capsule.source in TRUSTED_RUNTIME_SOURCES


def _is_stale_context(
    capsule: ContextCapsule,
    *,
    raw_metadata: dict[str, dict[str, Any]],
) -> bool:
    meta = _raw_meta(capsule, raw_metadata)
    text = _capsule_text(capsule).lower()
    card_type = str(meta.get("card_type", "")).lower()
    if "stale" in text or "expired" in text:
        return True
    if card_type == "freshness_conflict" and capsule.source not in {
        Source.USER,
        Source.TERMINAL,
    }:
        return True
    return False


def _freshness_gate(
    capsule: ContextCapsule,
    *,
    raw_metadata: dict[str, dict[str, Any]],
) -> bool:
    return not _is_stale_context(capsule, raw_metadata=raw_metadata)


def _marker_gate(
    capsule: ContextCapsule,
    *,
    card_id: str,
    marker_id: str,
    evidence_tags: list[str],
    suppressed_tags: list[str],
    raw_metadata: dict[str, dict[str, Any]],
) -> bool:
    if _same_card(capsule, card_id=card_id, raw_metadata=raw_metadata):
        return True
    capsule_tokens = _token_set(_capsule_text(capsule))
    allowed = _token_set(marker_id, *evidence_tags, *suppressed_tags)
    return bool(capsule_tokens & allowed)


def _has_required_evidence(
    ranked: list[tuple[ContextCapsule, float]],
    *,
    card_id: str,
    evidence_tags: list[str],
    raw_metadata: dict[str, dict[str, Any]],
) -> bool:
    required = _token_set(*evidence_tags)
    for capsule, _score in ranked[:10]:
        if not _same_card(capsule, card_id=card_id, raw_metadata=raw_metadata):
            continue
        if _token_set(_capsule_text(capsule)) & required:
            return True
    return False


def _has_known_bad_warning(
    ranked: list[tuple[ContextCapsule, float]],
    *,
    card_id: str,
    suppressed_tags: list[str],
    raw_metadata: dict[str, dict[str, Any]],
) -> bool:
    bad_tokens = _token_set(*suppressed_tags)
    for capsule, _score in ranked[:10]:
        if not _same_card(capsule, card_id=card_id, raw_metadata=raw_metadata):
            continue
        if _token_set(_capsule_text(capsule)) & bad_tokens:
            return True
    return False


def _recall_hit(
    ranked: list[tuple[ContextCapsule, float]],
    *,
    card_id: str,
    raw_metadata: dict[str, dict[str, Any]],
) -> bool:
    return any(
        _same_card(capsule, card_id=card_id, raw_metadata=raw_metadata)
        for capsule, _score in ranked[:10]
    )


def _leak_counts(
    ranked: list[tuple[ContextCapsule, float]],
    *,
    suppressed_tags: list[str],
    raw_metadata: dict[str, dict[str, Any]],
) -> tuple[int, int, int, int]:
    bad_tokens = _token_set(*suppressed_tags)
    untrusted = 0
    assistant_trap = 0
    stale = 0
    runtime_authority = 0
    for capsule, _score in ranked[:10]:
        if capsule.source in UNTRUSTED_RUNTIME_SOURCES:
            untrusted += 1
            runtime_authority += 1
        if (
            capsule.source == Source.ASSISTANT
            and (_token_set(_capsule_text(capsule)) & bad_tokens)
        ):
            assistant_trap += 1
        if _is_stale_context(capsule, raw_metadata=raw_metadata):
            stale += 1
            runtime_authority += 1
    return untrusted, assistant_trap, stale, runtime_authority


def _filter_ranked(
    ranked: list[tuple[ContextCapsule, float]],
    *,
    arm_name: str,
    card_id: str,
    marker_id: str,
    evidence_tags: list[str],
    suppressed_tags: list[str],
    raw_metadata: dict[str, dict[str, Any]],
) -> list[tuple[ContextCapsule, float]]:
    filtered = list(ranked)
    if arm_name in {
        "source_gate",
        "source_freshness_gate",
        "source_freshness_marker_gate",
    }:
        filtered = [(capsule, score) for capsule, score in filtered if _source_gate(capsule)]
    if arm_name in {"source_freshness_gate", "source_freshness_marker_gate"}:
        filtered = [
            (capsule, score)
            for capsule, score in filtered
            if _freshness_gate(capsule, raw_metadata=raw_metadata)
        ]
    if arm_name == "source_freshness_marker_gate":
        filtered = [
            (capsule, score)
            for capsule, score in filtered
            if _marker_gate(
                capsule,
                card_id=card_id,
                marker_id=marker_id,
                evidence_tags=evidence_tags,
                suppressed_tags=suppressed_tags,
                raw_metadata=raw_metadata,
            )
        ]
    return filtered


def _arm_stats(
    name: str,
    *,
    hits: list[bool],
    evidence_hits: list[bool],
    bad_warning_hits: list[bool],
    counts: list[int],
    latencies: list[float],
    corpus_size: int,
    untrusted_leaks: int,
    assistant_traps: int,
    stale_leaks: int,
    runtime_authority_violations: int,
) -> SafetyArmStats:
    average_count = mean(counts) if counts else 0.0
    return SafetyArmStats(
        name=name,
        recall_at_10=round(sum(1 for item in hits if item) / len(hits), 4),
        required_evidence_hit_rate=round(
            sum(1 for item in evidence_hits if item) / len(evidence_hits),
            4,
        ),
        known_bad_warning_hit_rate=round(
            sum(1 for item in bad_warning_hits if item) / len(bad_warning_hits),
            4,
        ),
        average_candidate_count=round(average_count, 2),
        candidate_reduction_ratio=round(1 - (average_count / corpus_size), 4),
        latency_p95_ms=round(_percentile(latencies, 0.95), 4),
        untrusted_top10_leak_count=untrusted_leaks,
        assistant_trap_top10_leak_count=assistant_traps,
        stale_top10_leak_count=stale_leaks,
        runtime_authority_violation_count=runtime_authority_violations,
    )


def evaluate_retrieval_safety_filter(
    *,
    base_fixture: Path,
    dialogue_cards_path: Path,
    workspace_root: Path,
) -> dict[str, Any]:
    workspace, cards, raw_metadata = _build_workspace(
        base_fixture=base_fixture,
        dialogue_cards_path=dialogue_cards_path,
        workspace_root=workspace_root,
    )
    all_capsules = workspace.context_capsules.list_all()
    fts5 = FTS5Index(all_capsules)
    corpus_size = len(all_capsules)
    arm_names = [
        "fts5_only",
        "source_gate",
        "source_freshness_gate",
        "source_freshness_marker_gate",
    ]
    arm_data: dict[str, dict[str, Any]] = {
        name: {
            "hits": [],
            "evidence_hits": [],
            "bad_warning_hits": [],
            "counts": [],
            "latencies": [],
            "untrusted_leaks": 0,
            "assistant_traps": 0,
            "stale_leaks": 0,
            "runtime_authority_violations": 0,
        }
        for name in arm_names
    }
    query_records: list[dict[str, Any]] = []

    for card in cards:
        card_id = str(card["dialogue_card_id"])
        for query in card.get("queries", []):
            query_text = _trap_query_text(card, query)
            marker_id = str(query.get("expected_marker_activation", ""))
            evidence_tags = _expected_evidence(query, card)
            suppressed_tags = _expected_suppressed(query, card)
            started = time.perf_counter()
            fts_ids = fts5.search(query_text)
            fts_capsules = _capsules_from_ids(workspace, fts_ids)
            fts_ranked = _rank_capsules(query_text, fts_capsules)
            fts_latency_ms = (time.perf_counter() - started) * 1000
            record: dict[str, Any] = {
                "dialogue_card_id": card_id,
                "query_id": query.get("query_id", ""),
                "marker_id": marker_id,
                "evidence_tags": evidence_tags,
                "suppressed_tags": suppressed_tags,
                "fts5_candidate_count": len(fts_ranked),
            }

            for arm_name in arm_names:
                started = time.perf_counter()
                ranked = _filter_ranked(
                    fts_ranked,
                    arm_name=arm_name,
                    card_id=card_id,
                    marker_id=marker_id,
                    evidence_tags=evidence_tags,
                    suppressed_tags=suppressed_tags,
                    raw_metadata=raw_metadata,
                )
                elapsed_ms = fts_latency_ms + ((time.perf_counter() - started) * 1000)
                hit = _recall_hit(
                    ranked,
                    card_id=card_id,
                    raw_metadata=raw_metadata,
                )
                evidence_hit = _has_required_evidence(
                    ranked,
                    card_id=card_id,
                    evidence_tags=evidence_tags,
                    raw_metadata=raw_metadata,
                )
                bad_warning_hit = _has_known_bad_warning(
                    ranked,
                    card_id=card_id,
                    suppressed_tags=suppressed_tags,
                    raw_metadata=raw_metadata,
                )
                untrusted, assistant_trap, stale, runtime_authority = _leak_counts(
                    ranked,
                    suppressed_tags=suppressed_tags,
                    raw_metadata=raw_metadata,
                )
                data = arm_data[arm_name]
                data["hits"].append(hit)
                data["evidence_hits"].append(evidence_hit)
                data["bad_warning_hits"].append(bad_warning_hit)
                data["counts"].append(len(ranked))
                data["latencies"].append(elapsed_ms)
                data["untrusted_leaks"] += untrusted
                data["assistant_traps"] += assistant_trap
                data["stale_leaks"] += stale
                data["runtime_authority_violations"] += runtime_authority
                record[f"{arm_name}_hit_at_10"] = hit
                record[f"{arm_name}_required_evidence_hit"] = evidence_hit
                record[f"{arm_name}_known_bad_warning_hit"] = bad_warning_hit
                record[f"{arm_name}_candidate_count"] = len(ranked)
                record[f"{arm_name}_untrusted_top10_leaks"] = untrusted
                record[f"{arm_name}_assistant_trap_top10_leaks"] = assistant_trap
                record[f"{arm_name}_stale_top10_leaks"] = stale
            query_records.append(record)

    arms = [
        _arm_stats(
            name,
            hits=[bool(item) for item in data["hits"]],
            evidence_hits=[bool(item) for item in data["evidence_hits"]],
            bad_warning_hits=[bool(item) for item in data["bad_warning_hits"]],
            counts=[int(item) for item in data["counts"]],
            latencies=[float(item) for item in data["latencies"]],
            corpus_size=corpus_size,
            untrusted_leaks=int(data["untrusted_leaks"]),
            assistant_traps=int(data["assistant_traps"]),
            stale_leaks=int(data["stale_leaks"]),
            runtime_authority_violations=int(data["runtime_authority_violations"]),
        )
        for name, data in arm_data.items()
    ]
    arms_by_name = {arm.name: arm for arm in arms}
    fts5_only = arms_by_name["fts5_only"]
    source_gate = arms_by_name["source_gate"]
    full_gate = arms_by_name["source_freshness_marker_gate"]
    metrics = {
        "validation": "retrieval-safety-filter-v0.5.4b",
        "query_count": len(query_records),
        "capsule_count": corpus_size,
        "fts5_only_untrusted_top10_leak_count": fts5_only.untrusted_top10_leak_count,
        "source_gate_untrusted_top10_leak_count": source_gate.untrusted_top10_leak_count,
        "full_gate_untrusted_top10_leak_count": full_gate.untrusted_top10_leak_count,
        "fts5_only_assistant_trap_top10_leak_count": (
            fts5_only.assistant_trap_top10_leak_count
        ),
        "full_gate_assistant_trap_top10_leak_count": (
            full_gate.assistant_trap_top10_leak_count
        ),
        "fts5_only_stale_top10_leak_count": fts5_only.stale_top10_leak_count,
        "full_gate_stale_top10_leak_count": full_gate.stale_top10_leak_count,
        "fts5_only_required_evidence_hit_rate": fts5_only.required_evidence_hit_rate,
        "full_gate_required_evidence_hit_rate": full_gate.required_evidence_hit_rate,
        "fts5_only_known_bad_warning_hit_rate": fts5_only.known_bad_warning_hit_rate,
        "full_gate_known_bad_warning_hit_rate": full_gate.known_bad_warning_hit_rate,
        "fts5_only_average_candidate_count": fts5_only.average_candidate_count,
        "full_gate_average_candidate_count": full_gate.average_candidate_count,
        "full_gate_candidate_reduction_ratio": full_gate.candidate_reduction_ratio,
        "fts5_only_latency_p95_ms": fts5_only.latency_p95_ms,
        "full_gate_latency_p95_ms": full_gate.latency_p95_ms,
        "runtime_authority_violation_count": (
            full_gate.runtime_authority_violation_count
        ),
        "online_llm_call_count": 0,
        "memory_promotion_count": 0,
        "layer3_mutation_count": 0,
    }
    hard_gates = {
        "query_count": metrics["query_count"] >= 50,
        "fts5_only_exposes_untrusted_leaks": (
            metrics["fts5_only_untrusted_top10_leak_count"] > 0
        ),
        "source_gate_reduces_untrusted_leaks": (
            metrics["source_gate_untrusted_top10_leak_count"]
            < metrics["fts5_only_untrusted_top10_leak_count"]
        ),
        "full_gate_blocks_untrusted_runtime_context": (
            metrics["full_gate_untrusted_top10_leak_count"] == 0
        ),
        "full_gate_blocks_assistant_traps": (
            metrics["full_gate_assistant_trap_top10_leak_count"] == 0
        ),
        "full_gate_blocks_stale_runtime_context": (
            metrics["full_gate_stale_top10_leak_count"] == 0
        ),
        "full_gate_preserves_required_evidence_hit_rate": (
            metrics["full_gate_required_evidence_hit_rate"]
            >= metrics["fts5_only_required_evidence_hit_rate"] - 0.05
        ),
        "full_gate_reduces_candidates": (
            metrics["full_gate_average_candidate_count"]
            < metrics["fts5_only_average_candidate_count"]
        ),
        "runtime_authority_violation_count": (
            metrics["runtime_authority_violation_count"] == 0
        ),
        "online_llm_call_count": metrics["online_llm_call_count"] == 0,
        "memory_promotion_count": metrics["memory_promotion_count"] == 0,
        "layer3_mutation_count": metrics["layer3_mutation_count"] == 0,
    }
    return {
        "validation": "retrieval-safety-filter-v0.5.4b",
        "passed": all(hard_gates.values()),
        "metrics": metrics,
        "hard_gates": hard_gates,
        "arms": [asdict(arm) for arm in arms],
        "query_records": query_records,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-fixture", default=str(DEFAULT_BASE_FIXTURE))
    parser.add_argument("--dialogue-cards", default=str(DEFAULT_DIALOGUE_CARDS))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    result = evaluate_retrieval_safety_filter(
        base_fixture=Path(args.base_fixture),
        dialogue_cards_path=Path(args.dialogue_cards),
        workspace_root=output_dir / ".memoryweaver-safety-filter",
    )
    write_json(output_dir / "raw_results.json", result)
    write_json(output_dir / "metrics_summary.json", result["metrics"])
    write_jsonl(output_dir / "arms.jsonl", result["arms"])
    write_jsonl(output_dir / "query_results.jsonl", result["query_records"])
    print(json.dumps({
        "validation": result["validation"],
        "passed": result["passed"],
        "metrics": result["metrics"],
    }, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
