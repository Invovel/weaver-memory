"""Validate Runbook Marker -> ContextCapsule binding.

This is the bridge between v0.5 Runbook Marker traces and v0.5.3
ContextCapsules. It validates that a manually curated marker can actively bind
to compact RAW-context capsules before runtime intervention is enabled.

The validation is deliberately authority-safe:
- no online LLM call
- no tool execution
- no Layer 3 mutation
- no MemoryItem promotion
- no actual route/action mutation while marker runtime_authority is false
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks._safety import safe_rmtree_child
from benchmarks.context_capsule_validation import read_jsonl, raw_span_from_record
from memoryweaver.content_router import ContentRouter
from memoryweaver.context_schema import ContentType, MarkerEvidenceContext
from memoryweaver.marker_context import capsules_for_marker_context
from memoryweaver.store import MemoryWorkspace, tokenize_text


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTEXT_FIXTURE = (
    REPO_ROOT
    / "docs"
    / "validation"
    / "context-capsule-v0.5.3"
    / "raw_spans_fixture.jsonl"
)
DEFAULT_MARKERS = (
    REPO_ROOT
    / "docs"
    / "validation"
    / "runbook-marker-v0.5"
    / "markers.json"
)
DEFAULT_CARDS = (
    REPO_ROOT
    / "docs"
    / "validation"
    / "runbook-marker-v0.5"
    / "dialogue_cards.jsonl"
)
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT
    / "docs"
    / "validation"
    / "active-marker-binding-v0.5.2"
)


GENERIC_EVIDENCE_WORDS = {
    "check",
    "verify",
    "confirm",
    "compare",
    "inspect",
    "identify",
    "recent",
    "before",
    "after",
    "status",
    "code",
}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_cards(path: Path) -> list[dict[str, Any]]:
    return read_jsonl(path)


def load_markers(path: Path) -> list[dict[str, Any]]:
    data = read_json(path)
    return list(data.get("markers", []))


def seed_workspace_with_context(records: list[dict[str, Any]], workspace: MemoryWorkspace) -> None:
    router = ContentRouter()
    for record in records:
        raw_span = raw_span_from_record(record)
        workspace.raw_spans.add(raw_span)
        capsule = router.compress(raw_span)
        workspace.context_capsules.add(capsule)
        workspace.tag_time_index.add(capsule)


def words_for_evidence(label: str) -> list[str]:
    words: set[str] = set()
    for token in re.split(r"[^A-Za-z0-9]+", label):
        if not token:
            continue
        for subtoken in tokenize_text(token):
            lowered = subtoken.lower()
            if lowered and lowered not in GENERIC_EVIDENCE_WORDS:
                words.add(lowered)
    return sorted(words)


def tags_for_marker(marker: dict[str, Any], card: dict[str, Any]) -> list[str]:
    tags: set[str] = set()
    tags.update(tokenize_text(str(marker.get("id", ""))))
    tags.update(tokenize_text(str(marker.get("core_issue_id", ""))))
    for evidence in marker.get("required_evidence", []):
        tags.update(words_for_evidence(str(evidence)))
    for query in card.get("queries", []):
        tags.update(tokenize_text(str(query.get("query", ""))))
    for event in card.get("events", []):
        tags.update(str(tag).lower() for tag in event.get("tags", []))
    return sorted(tag for tag in tags if tag)


def evidence_item_covered(evidence_label: str, capsule_tags: set[str], capsule_text: str) -> bool:
    words = words_for_evidence(evidence_label)
    if not words:
        return True
    text = capsule_text.lower()
    return any(word in capsule_tags or word in text for word in words)


def build_marker_context(marker: dict[str, Any], card: dict[str, Any]) -> MarkerEvidenceContext:
    return MarkerEvidenceContext(
        marker_id=str(marker["id"]),
        required_tags=tags_for_marker(marker, card),
        required_time_window="2026-06-05T00:00:00Z..2026-06-06T00:00:00Z",
        preferred_content_types=[
            ContentType.TERMINAL_LOG,
            ContentType.TOOL_JSON,
            ContentType.CONVERSATION_TURN,
            ContentType.CODE_PATCH,
            ContentType.TRACE_RECORD,
        ],
    )


def golden_cards_by_marker(cards: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for card in cards:
        if card.get("tier") != "golden":
            continue
        marker_id = (
            card.get("expected", {})
            .get("must", {})
            .get("marker_activation", "")
        )
        if marker_id:
            result[str(marker_id)] = card
    return result


def evaluate_binding(
    *,
    context_fixture: Path,
    markers_path: Path,
    cards_path: Path,
    workspace_root: Path,
    limit: int = 5,
) -> dict[str, Any]:
    safe_rmtree_child(
        workspace_root.parent,
        workspace_root,
        allowed_prefixes=(".memoryweaver",),
    )
    workspace = MemoryWorkspace(workspace_root)
    seed_workspace_with_context(read_jsonl(context_fixture), workspace)

    cards = load_cards(cards_path)
    marker_to_card = golden_cards_by_marker(cards)
    markers = [
        marker for marker in load_markers(markers_path)
        if marker.get("id") in marker_to_card
    ][:limit]

    traces: list[dict[str, Any]] = []
    bound_count = 0
    raw_recovery_hits = 0
    raw_recovery_total = 0
    required_evidence_total = 0
    required_evidence_covered = 0
    runtime_mutation_count = 0
    layer3_mutation_count = 0
    memory_promotion_count = 0

    for marker in markers:
        card = marker_to_card[str(marker["id"])]
        marker_context = build_marker_context(marker, card)
        workspace.marker_evidence_contexts.add(marker_context)
        capsules = capsules_for_marker_context(
            marker_context,
            workspace.context_capsules,
            workspace.tag_time_index,
            limit=25,
        )
        if capsules:
            bound_count += 1

        raw_refs: list[str] = []
        capsule_tags: set[str] = set()
        capsule_text_parts: list[str] = []
        for capsule in capsules:
            capsule_tags.update(tag.lower() for tag in capsule.tags)
            capsule_text_parts.append(capsule.summary)
            raw_recovery_total += 1
            raw_span = workspace.raw_spans.get(capsule.raw_ref_id)
            if raw_span is not None:
                raw_recovery_hits += 1
                raw_refs.append(raw_span.id)

        covered_evidence: list[str] = []
        missing_evidence: list[str] = []
        capsule_text = " ".join(capsule_text_parts)
        for evidence in marker.get("required_evidence", []):
            required_evidence_total += 1
            if evidence_item_covered(str(evidence), capsule_tags, capsule_text):
                required_evidence_covered += 1
                covered_evidence.append(str(evidence))
            else:
                missing_evidence.append(str(evidence))

        runtime_authority = bool(marker.get("runtime_authority", False))
        applied_to_runtime = False
        actual_route = "thinking"
        if applied_to_runtime:
            runtime_mutation_count += 1

        traces.append({
            "dialogue_card_id": card.get("dialogue_card_id", ""),
            "query": card.get("queries", [{}])[0].get("query", ""),
            "core_issue_id": marker.get("core_issue_id", ""),
            "marker_id": marker.get("id", ""),
            "binding_mode": "active_preview",
            "runtime_authority": runtime_authority,
            "applied_to_runtime": applied_to_runtime,
            "recommended_route": marker.get("recommended_route", "fast_verify"),
            "actual_route": actual_route,
            "required_evidence": marker.get("required_evidence", []),
            "covered_evidence": covered_evidence,
            "missing_evidence": missing_evidence,
            "suppressed_actions": marker.get("suppressed_actions", []),
            "actual_suppressed_actions": [],
            "marker_context": marker_context.to_dict(),
            "bound_capsule_ids": [capsule.id for capsule in capsules],
            "raw_refs": raw_refs,
            "online_llm_call_count": 0,
            "layer3_mutation_count": 0,
            "memory_promotion_count": 0,
        })

    total = len(traces)
    metrics = {
        "marker_count": total,
        "active_preview_generated_count": total,
        "marker_context_bound_count": bound_count,
        "marker_context_hit_rate": bound_count / total if total else 0.0,
        "required_evidence_total": required_evidence_total,
        "required_evidence_covered": required_evidence_covered,
        "required_evidence_coverage": (
            required_evidence_covered / required_evidence_total
            if required_evidence_total else 1.0
        ),
        "raw_recovery_rate": raw_recovery_hits / raw_recovery_total if raw_recovery_total else 1.0,
        "runtime_mutation_count": runtime_mutation_count,
        "layer3_mutation_count": layer3_mutation_count,
        "memory_promotion_count": memory_promotion_count,
        "online_llm_call_count": 0,
    }
    hard_gates = {
        "marker_context_hit_rate": metrics["marker_context_hit_rate"] == 1.0,
        "required_evidence_coverage": metrics["required_evidence_coverage"] >= 0.8,
        "raw_recovery_rate": metrics["raw_recovery_rate"] == 1.0,
        "runtime_mutation_count": metrics["runtime_mutation_count"] == 0,
        "layer3_mutation_count": metrics["layer3_mutation_count"] == 0,
        "memory_promotion_count": metrics["memory_promotion_count"] == 0,
        "online_llm_call_count": metrics["online_llm_call_count"] == 0,
    }
    return {
        "validation": "active-marker-binding-v0.5.2",
        "passed": bool(traces) and all(hard_gates.values()),
        "metrics": metrics,
        "hard_gates": hard_gates,
        "traces": traces,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context-fixture", default=str(DEFAULT_CONTEXT_FIXTURE))
    parser.add_argument("--markers", default=str(DEFAULT_MARKERS))
    parser.add_argument("--cards", default=str(DEFAULT_CARDS))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    result = evaluate_binding(
        context_fixture=Path(args.context_fixture),
        markers_path=Path(args.markers),
        cards_path=Path(args.cards),
        workspace_root=output_dir / ".memoryweaver-active-marker-binding",
        limit=args.limit,
    )
    write_json(output_dir / "raw_results.json", result)
    write_json(output_dir / "metrics_summary.json", result["metrics"])
    write_jsonl(output_dir / "binding_traces.jsonl", result["traces"])
    print(json.dumps({
        "validation": result["validation"],
        "passed": result["passed"],
        "metrics": result["metrics"],
    }, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
