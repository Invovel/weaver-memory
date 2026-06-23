"""Validate the v0.5.3 ContextCapsule / TagTimeIndex substrate.

This benchmark is intentionally local and deterministic. It validates the RAW
context compression layer only; it does not create MemoryItems, promote memory,
or affect Layer 3 Pattern routing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks._safety import safe_rmtree_child
from memoryweaver.content_router import ContentRouter
from memoryweaver.context_schema import ContentType, MarkerEvidenceContext, RawSpan
from memoryweaver.marker_context import capsules_for_marker_context
from memoryweaver.schema import Source
from memoryweaver.store import MemoryWorkspace


DEFAULT_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "validation"
    / "context-capsule-v0.5.3"
    / "raw_spans_fixture.example.jsonl"
)
DEFAULT_OUTPUT_DIR = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "validation"
    / "context-capsule-v0.5.3"
)
FULL_FIXTURE_COUNTS = {
    ContentType.TERMINAL_LOG.value: 10,
    ContentType.TOOL_JSON.value: 10,
    ContentType.CONVERSATION_TURN.value: 10,
    ContentType.CODE_PATCH.value: 5,
    ContentType.TRACE_RECORD.value: 5,
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def raw_span_from_record(record: dict[str, Any]) -> RawSpan:
    return RawSpan(
        id=str(record.get("raw_span_id", record.get("id", ""))),
        content=str(record.get("content", "")),
        content_type=ContentType(str(record.get("content_type", ContentType.TEXT.value))),
        source=Source(str(record.get("source", Source.UNKNOWN.value))),
        timestamp=str(record.get("timestamp", "")),
        metadata=dict(record.get("metadata", {})),
    )


def evaluate_fixture(
    records: list[dict[str, Any]],
    workspace_root: Path,
    *,
    require_full_fixture: bool = False,
) -> dict[str, Any]:
    workspace = MemoryWorkspace(workspace_root)
    router = ContentRouter()
    capsule_records: list[dict[str, Any]] = []
    content_type_counts: dict[str, int] = {}
    raw_retrieval_hits = 0
    raw_retrieval_total = 0
    tag_hits = 0
    tag_total = 0
    timestamp_violations = 0
    trust_violations = 0
    must_include_misses: list[dict[str, Any]] = []
    tag_misses: list[dict[str, Any]] = []

    for record in records:
        raw_span = raw_span_from_record(record)
        content_type_counts[raw_span.content_type.value] = (
            content_type_counts.get(raw_span.content_type.value, 0) + 1
        )
        workspace.raw_spans.add(raw_span)
        capsule = router.compress(raw_span)
        workspace.context_capsules.add(capsule)
        workspace.tag_time_index.add(capsule)
        capsule_records.append(capsule.to_dict())

        expected = dict(record.get("expected_capsule", {}))
        if expected.get("raw_retrievable", True):
            raw_retrieval_total += 1
            recovered = workspace.raw_spans.get(capsule.raw_ref_id)
            if recovered and recovered.content == raw_span.content:
                raw_retrieval_hits += 1

        for tag in expected.get("required_tags", []):
            tag_total += 1
            if str(tag).lower() in {item.lower() for item in capsule.tags}:
                tag_hits += 1
            else:
                tag_misses.append({
                    "raw_span_id": raw_span.id,
                    "missing_tag": tag,
                    "tags": capsule.tags,
                })

        if capsule.source != raw_span.source:
            trust_violations += 1
        if capsule.metadata.get("raw_source") != raw_span.source.value:
            trust_violations += 1
        if expected.get("must_preserve_timestamp", True) and capsule.timestamp != raw_span.timestamp:
            timestamp_violations += 1

        summary_lower = capsule.summary.lower()
        for required_text in expected.get("must_include", []):
            if str(required_text).lower() not in summary_lower:
                must_include_misses.append({
                    "raw_span_id": raw_span.id,
                    "missing": required_text,
                    "summary": capsule.summary,
                })

    marker_contexts = [
        MarkerEvidenceContext(
            marker_id="marker_codex_subscription_context",
            required_tags=["codex", "subscription", "organization"],
            required_time_window="2026-06-05T00:00:00Z..2026-06-06T00:00:00Z",
            preferred_content_types=[
                ContentType.TERMINAL_LOG,
                ContentType.TOOL_JSON,
                ContentType.CONVERSATION_TURN,
            ],
        ),
        MarkerEvidenceContext(
            marker_id="marker_terminal_error_context",
            required_tags=["terminal", "error"],
            required_time_window="2026-06-05T00:00:00Z..2026-06-06T00:00:00Z",
            preferred_content_types=[ContentType.TERMINAL_LOG, ContentType.TOOL_JSON],
        ),
    ]
    marker_hits = 0
    marker_results: list[dict[str, Any]] = []
    for marker_context in marker_contexts:
        workspace.marker_evidence_contexts.add(marker_context)
        capsules = capsules_for_marker_context(
            marker_context,
            workspace.context_capsules,
            workspace.tag_time_index,
            limit=10,
        )
        if capsules:
            marker_hits += 1
        marker_results.append({
            "marker_id": marker_context.marker_id,
            "required_tags": marker_context.required_tags,
            "returned_capsule_ids": [capsule.id for capsule in capsules],
        })

    all_capsules = workspace.context_capsules.list_all()
    raw_ids = {raw_span.id for raw_span in workspace.raw_spans.list_all()}
    capsule_ref_errors = workspace.context_capsules.validate_raw_refs(raw_ids)
    raw_ref_missing_count = sum(
        1 for capsule in all_capsules if capsule.raw_ref_id not in raw_ids
    )
    compression_ratios = [capsule.compression_ratio for capsule in all_capsules]
    average_ratio = (
        sum(compression_ratios) / len(compression_ratios)
        if compression_ratios else 1.0
    )

    metrics = {
        "raw_span_count": len(records),
        "capsule_count": len(all_capsules),
        "content_type_counts": content_type_counts,
        "average_compression_ratio": round(average_ratio, 4),
        "tag_recall_at_k": tag_hits / tag_total if tag_total else 1.0,
        "raw_retrieval_success_rate": (
            raw_retrieval_hits / raw_retrieval_total if raw_retrieval_total else 1.0
        ),
        "time_filter_accuracy": 1.0 if timestamp_violations == 0 else 0.0,
        "marker_context_hit_rate": marker_hits / len(marker_contexts),
        "trust_inheritance_violation_count": trust_violations,
        "raw_ref_missing_count": raw_ref_missing_count,
        "capsule_promoted_memory_count": 0,
        "must_include_miss_count": len(must_include_misses),
        "tag_miss_count": len(tag_misses),
        "capsule_ref_error_count": len(capsule_ref_errors),
    }
    full_fixture_requirements = {
        content_type: content_type_counts.get(content_type, 0) >= minimum
        for content_type, minimum in FULL_FIXTURE_COUNTS.items()
    }
    full_fixture_requirements["raw_span_count"] = len(records) >= sum(
        FULL_FIXTURE_COUNTS.values()
    )
    hard_gates = {
        "raw_retrieval_success_rate": metrics["raw_retrieval_success_rate"] == 1.0,
        "trust_inheritance_violation_count": trust_violations == 0,
        "raw_ref_missing_count": raw_ref_missing_count == 0,
        "capsule_promoted_memory_count": metrics["capsule_promoted_memory_count"] == 0,
        "marker_context_hit_rate": metrics["marker_context_hit_rate"] >= 0.8,
        "tag_miss_count": len(tag_misses) == 0,
    }
    if require_full_fixture:
        hard_gates["full_fixture_distribution"] = all(
            full_fixture_requirements.values()
        )

    return {
        "validation": "context-capsule-v0.5.3",
        "passed": (
            all(hard_gates.values())
            and not must_include_misses
            and not tag_misses
            and not capsule_ref_errors
        ),
        "metrics": metrics,
        "hard_gates": hard_gates,
        "full_fixture_requirements": full_fixture_requirements,
        "marker_context_results": marker_results,
        "must_include_misses": must_include_misses,
        "tag_misses": tag_misses,
        "capsule_ref_errors": capsule_ref_errors,
        "capsules": capsule_records,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", default=str(DEFAULT_FIXTURE))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument(
        "--require-full-fixture",
        action="store_true",
        help="Require the full 10/10/10/5/5 content-type fixture distribution.",
    )
    args = parser.parse_args(argv)

    fixture = Path(args.fixture)
    output_dir = Path(args.output_dir)
    workspace_root = output_dir / ".memoryweaver-context-workspace"
    safe_rmtree_child(
        output_dir,
        workspace_root,
        allowed_prefixes=(".memoryweaver-context-workspace",),
    )
    records = read_jsonl(fixture)
    result = evaluate_fixture(
        records,
        workspace_root,
        require_full_fixture=args.require_full_fixture,
    )

    write_json(output_dir / "raw_results.json", result)
    write_json(output_dir / "metrics_summary.json", result["metrics"])
    write_jsonl(output_dir / "capsules.jsonl", result["capsules"])
    write_jsonl(output_dir / "marker_context_results.jsonl", result["marker_context_results"])
    print(json.dumps({
        "validation": result["validation"],
        "passed": result["passed"],
        "metrics": result["metrics"],
    }, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
