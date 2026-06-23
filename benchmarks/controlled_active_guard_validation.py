"""Validate controlled low-risk active marker behavior.

This stage upgrades exactly one class of marker from active_preview to a
controlled runtime plan mutation:

- allowed: L1_hint with full capsule/raw evidence coverage
- allowed: route hint and required-evidence plan
- not allowed: tool execution, real action suppression, memory promotion,
  Layer-3 mutation, online LLM calls, or high-risk L2/L3 activation
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.active_marker_binding_validation import (
    DEFAULT_CARDS,
    DEFAULT_CONTEXT_FIXTURE,
    DEFAULT_MARKERS,
    evaluate_binding,
    read_json,
    write_json,
    write_jsonl,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT
    / "docs"
    / "validation"
    / "controlled-active-guard-v0.5.2"
)
DEFAULT_CONFLICTS = (
    REPO_ROOT
    / "docs"
    / "validation"
    / "runbook-marker-v0.5"
    / "conflict_candidates.jsonl"
)
ALLOWED_ACTIVE_LEVELS = {"L1_hint"}


def marker_index(markers_path: Path) -> dict[str, dict[str, Any]]:
    return {
        str(marker["id"]): marker
        for marker in read_json(markers_path).get("markers", [])
    }


def load_conflicts(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def conflicts_for_marker(
    marker_id: str,
    dialogue_card_id: str,
    conflicts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        conflict for conflict in conflicts
        if conflict.get("dialogue_card_id") == dialogue_card_id
        and marker_id in {conflict.get("marker_a"), conflict.get("marker_b")}
    ]


def can_apply_active_guard(
    trace: dict[str, Any],
    marker: dict[str, Any],
    conflicts: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    intervention_level = str(marker.get("intervention_level", ""))
    if intervention_level not in ALLOWED_ACTIVE_LEVELS:
        reasons.append(f"intervention_level_not_allowed:{intervention_level}")
    if trace.get("missing_evidence"):
        reasons.append("missing_required_evidence")
    if not trace.get("bound_capsule_ids"):
        reasons.append("no_bound_capsules")
    if not trace.get("raw_refs"):
        reasons.append("no_raw_refs")
    if bool(marker.get("runtime_authority", False)):
        reasons.append("marker_file_runtime_authority_must_remain_false")
    if conflicts:
        reasons.append("unresolved_marker_conflict")
    return not reasons, reasons


def evaluate_controlled_active_guard(
    *,
    context_fixture: Path,
    markers_path: Path,
    cards_path: Path,
    workspace_root: Path,
    conflicts_path: Path = DEFAULT_CONFLICTS,
) -> dict[str, Any]:
    binding = evaluate_binding(
        context_fixture=context_fixture,
        markers_path=markers_path,
        cards_path=cards_path,
        workspace_root=workspace_root,
        limit=5,
    )
    markers = marker_index(markers_path)
    conflicts = load_conflicts(conflicts_path)
    traces: list[dict[str, Any]] = []
    active_applied_count = 0
    preview_only_count = 0
    high_risk_blocked_count = 0
    tool_execution_count = 0
    actual_suppression_count = 0
    memory_promotion_count = 0
    layer3_mutation_count = 0
    online_llm_call_count = 0
    conflict_logged_count = 0
    conflict_blocked_count = 0

    for trace in binding["traces"]:
        marker = markers[str(trace["marker_id"])]
        marker_conflicts = conflicts_for_marker(
            str(trace["marker_id"]),
            str(trace["dialogue_card_id"]),
            conflicts,
        )
        if marker_conflicts:
            conflict_logged_count += 1
        can_apply, block_reasons = can_apply_active_guard(
            trace,
            marker,
            marker_conflicts,
        )
        intervention_level = str(marker.get("intervention_level", ""))
        if can_apply:
            active_applied_count += 1
            actual_route = str(trace.get("recommended_route", "fast_verify"))
            actual_required_evidence = list(trace.get("required_evidence", []))
            actual_guard_warnings = list(trace.get("suppressed_actions", []))
            mode = "controlled_active_guard"
        else:
            preview_only_count += 1
            if intervention_level not in ALLOWED_ACTIVE_LEVELS:
                high_risk_blocked_count += 1
            if marker_conflicts:
                conflict_blocked_count += 1
            actual_route = "thinking"
            actual_required_evidence = []
            actual_guard_warnings = []
            mode = "preview_only_blocked"

        controlled_trace = {
            "dialogue_card_id": trace["dialogue_card_id"],
            "marker_id": trace["marker_id"],
            "intervention_level": intervention_level,
            "policy": "controlled-active-guard-policy-v1",
            "input_binding_mode": trace["binding_mode"],
            "output_mode": mode,
            "can_apply_active_guard": can_apply,
            "block_reasons": block_reasons,
            "conflict_candidates": marker_conflicts,
            "recommended_route": trace["recommended_route"],
            "actual_route": actual_route,
            "required_evidence": trace["required_evidence"],
            "actual_required_evidence": actual_required_evidence,
            "guard_warning_actions": actual_guard_warnings,
            "actual_suppressed_actions": [],
            "bound_capsule_ids": trace["bound_capsule_ids"],
            "raw_refs": trace["raw_refs"],
            "tool_execution_count": 0,
            "memory_promotion_count": 0,
            "layer3_mutation_count": 0,
            "online_llm_call_count": 0,
        }
        traces.append(controlled_trace)

    total = len(traces)
    metrics = {
        "marker_count": total,
        "active_guard_applied_count": active_applied_count,
        "preview_only_count": preview_only_count,
        "high_risk_blocked_count": high_risk_blocked_count,
        "active_guard_application_rate": active_applied_count / total if total else 0.0,
        "tool_execution_count": tool_execution_count,
        "actual_suppression_count": actual_suppression_count,
        "memory_promotion_count": memory_promotion_count,
        "layer3_mutation_count": layer3_mutation_count,
        "online_llm_call_count": online_llm_call_count,
        "conflict_logged_count": conflict_logged_count,
        "conflict_blocked_count": conflict_blocked_count,
        "required_evidence_plan_applied_count": sum(
            1 for trace in traces if trace["actual_required_evidence"]
        ),
        "route_hint_applied_count": sum(
            1 for trace in traces if trace["actual_route"] == "fast_verify"
        ),
    }
    hard_gates = {
        "active_guard_applied_count": metrics["active_guard_applied_count"] == 1,
        "high_risk_blocked_count": metrics["high_risk_blocked_count"] == 4,
        "tool_execution_count": tool_execution_count == 0,
        "actual_suppression_count": actual_suppression_count == 0,
        "memory_promotion_count": memory_promotion_count == 0,
        "layer3_mutation_count": layer3_mutation_count == 0,
        "online_llm_call_count": online_llm_call_count == 0,
        "conflict_logged_count": metrics["conflict_logged_count"] >= 1,
        "conflict_blocked_count": metrics["conflict_blocked_count"] >= 1,
    }
    return {
        "validation": "controlled-active-guard-v0.5.2",
        "passed": bool(traces) and all(hard_gates.values()),
        "policy": {
            "version": "controlled-active-guard-policy-v1",
            "allowed_active_levels": sorted(ALLOWED_ACTIVE_LEVELS),
            "requires_full_evidence_coverage": True,
            "allows_route_hint": True,
            "allows_required_evidence_plan": True,
            "allows_tool_execution": False,
            "allows_actual_suppression": False,
            "allows_memory_promotion": False,
            "allows_layer3_mutation": False,
            "blocks_unresolved_conflicts": True,
        },
        "metrics": metrics,
        "hard_gates": hard_gates,
        "traces": traces,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context-fixture", default=str(DEFAULT_CONTEXT_FIXTURE))
    parser.add_argument("--markers", default=str(DEFAULT_MARKERS))
    parser.add_argument("--cards", default=str(DEFAULT_CARDS))
    parser.add_argument("--conflicts", default=str(DEFAULT_CONFLICTS))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    result = evaluate_controlled_active_guard(
        context_fixture=Path(args.context_fixture),
        markers_path=Path(args.markers),
        cards_path=Path(args.cards),
        conflicts_path=Path(args.conflicts),
        workspace_root=output_dir / ".memoryweaver-controlled-active-guard",
    )
    write_json(output_dir / "raw_results.json", result)
    write_json(output_dir / "metrics_summary.json", result["metrics"])
    write_jsonl(output_dir / "guard_traces.jsonl", result["traces"])
    print(json.dumps({
        "validation": result["validation"],
        "passed": result["passed"],
        "metrics": result["metrics"],
    }, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
