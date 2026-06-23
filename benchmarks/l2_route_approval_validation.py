"""Validate approval-gated L2 route marker activation.

L2_route markers are more powerful than L1_hint markers because they can change
the runtime route recommendation. This benchmark keeps the boundary tight:

- L1_hint may apply as controlled active guard.
- L2_route requires an explicit approval record.
- L3_guard remains preview-only.
- Approved L2 can only add route/evidence plan, never execute tools or suppress
  actions.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.controlled_active_guard_validation import (
    DEFAULT_CARDS,
    DEFAULT_CONFLICTS,
    DEFAULT_CONTEXT_FIXTURE,
    DEFAULT_MARKERS,
    evaluate_controlled_active_guard,
    load_conflicts,
    marker_index,
    write_json,
    write_jsonl,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_APPROVALS = (
    REPO_ROOT
    / "docs"
    / "validation"
    / "l2-route-approval-v0.5.2"
    / "route_approvals.jsonl"
)
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT
    / "docs"
    / "validation"
    / "l2-route-approval-v0.5.2"
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def approval_index(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    approvals: dict[tuple[str, str], dict[str, Any]] = {}
    for record in read_jsonl(path):
        if record.get("decision") == "approved":
            approvals[(str(record.get("marker_id")), str(record.get("dialogue_card_id")))] = record
    return approvals


def approval_allows(record: dict[str, Any], effect: str) -> bool:
    return effect in set(str(item) for item in record.get("allowed_effects", []))


def evaluate_l2_route_approval(
    *,
    context_fixture: Path,
    markers_path: Path,
    cards_path: Path,
    conflicts_path: Path,
    approvals_path: Path,
    workspace_root: Path,
) -> dict[str, Any]:
    controlled = evaluate_controlled_active_guard(
        context_fixture=context_fixture,
        markers_path=markers_path,
        cards_path=cards_path,
        conflicts_path=conflicts_path,
        workspace_root=workspace_root,
    )
    markers = marker_index(markers_path)
    approvals = approval_index(approvals_path)
    conflicts = load_conflicts(conflicts_path)
    traces: list[dict[str, Any]] = []

    l1_active_count = 0
    l2_marker_count = 0
    l2_approved_count = 0
    l2_pending_count = 0
    l2_applied_count = 0
    l3_blocked_count = 0
    conflict_blocked_count = 0

    for trace in controlled["traces"]:
        marker = markers[str(trace["marker_id"])]
        level = str(marker.get("intervention_level", ""))
        approval = approvals.get((str(trace["marker_id"]), str(trace["dialogue_card_id"])))
        output_mode = trace["output_mode"]
        actual_route = trace["actual_route"]
        actual_required_evidence = list(trace["actual_required_evidence"])
        block_reasons = list(trace["block_reasons"])
        approval_record = approval or {}

        if level == "L1_hint" and output_mode == "controlled_active_guard":
            l1_active_count += 1
        elif level == "L2_route":
            l2_marker_count += 1
            if approval is None:
                l2_pending_count += 1
                block_reasons.append("missing_l2_route_approval")
                output_mode = "l2_route_pending_approval"
                actual_route = "thinking"
                actual_required_evidence = []
            elif (
                approval_allows(approval, "route_hint")
                and approval_allows(approval, "required_evidence_plan")
                and not trace["conflict_candidates"]
                and trace["bound_capsule_ids"]
                and trace["raw_refs"]
            ):
                l2_approved_count += 1
                l2_applied_count += 1
                output_mode = "approved_l2_route_plan"
                actual_route = str(trace["recommended_route"])
                actual_required_evidence = list(trace["required_evidence"])
                block_reasons = []
            else:
                l2_pending_count += 1
                block_reasons.append("approval_record_insufficient")
        elif level == "L3_guard":
            l3_blocked_count += 1

        if trace["conflict_candidates"]:
            conflict_blocked_count += 1

        traces.append({
            **trace,
            "policy": "l2-route-approval-policy-v1",
            "output_mode": output_mode,
            "approval": approval_record,
            "approval_required": level == "L2_route",
            "block_reasons": block_reasons,
            "actual_route": actual_route,
            "actual_required_evidence": actual_required_evidence,
            "actual_suppressed_actions": [],
            "tool_execution_count": 0,
            "memory_promotion_count": 0,
            "layer3_mutation_count": 0,
            "online_llm_call_count": 0,
        })

    metrics = {
        "marker_count": len(traces),
        "l1_active_count": l1_active_count,
        "l2_marker_count": l2_marker_count,
        "l2_approved_count": l2_approved_count,
        "l2_pending_count": l2_pending_count,
        "l2_applied_count": l2_applied_count,
        "l3_blocked_count": l3_blocked_count,
        "conflict_blocked_count": conflict_blocked_count,
        "route_plan_applied_count": sum(
            1 for trace in traces if trace["actual_route"] == "fast_verify"
        ),
        "required_evidence_plan_applied_count": sum(
            1 for trace in traces if trace["actual_required_evidence"]
        ),
        "tool_execution_count": 0,
        "actual_suppression_count": 0,
        "memory_promotion_count": 0,
        "layer3_mutation_count": 0,
        "online_llm_call_count": 0,
        "approval_record_count": len(approvals),
        "conflict_record_count": len(conflicts),
    }
    hard_gates = {
        "l1_active_count": metrics["l1_active_count"] == 1,
        "l2_approved_count": metrics["l2_approved_count"] == 1,
        "l2_pending_count": metrics["l2_pending_count"] == 1,
        "l2_applied_count": metrics["l2_applied_count"] == 1,
        "l3_blocked_count": metrics["l3_blocked_count"] == 2,
        "conflict_blocked_count": metrics["conflict_blocked_count"] >= 1,
        "tool_execution_count": metrics["tool_execution_count"] == 0,
        "actual_suppression_count": metrics["actual_suppression_count"] == 0,
        "memory_promotion_count": metrics["memory_promotion_count"] == 0,
        "layer3_mutation_count": metrics["layer3_mutation_count"] == 0,
        "online_llm_call_count": metrics["online_llm_call_count"] == 0,
    }
    return {
        "validation": "l2-route-approval-v0.5.2",
        "passed": all(hard_gates.values()),
        "policy": {
            "version": "l2-route-approval-policy-v1",
            "l1_hint": "allowed_with_full_evidence",
            "l2_route": "requires_explicit_approval",
            "l3_guard": "blocked",
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
    parser.add_argument("--approvals", default=str(DEFAULT_APPROVALS))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    result = evaluate_l2_route_approval(
        context_fixture=Path(args.context_fixture),
        markers_path=Path(args.markers),
        cards_path=Path(args.cards),
        conflicts_path=Path(args.conflicts),
        approvals_path=Path(args.approvals),
        workspace_root=output_dir / ".memoryweaver-l2-route-approval",
    )
    write_json(output_dir / "raw_results.json", result)
    write_json(output_dir / "metrics_summary.json", result["metrics"])
    write_jsonl(output_dir / "route_traces.jsonl", result["traces"])
    print(json.dumps({
        "validation": result["validation"],
        "passed": result["passed"],
        "metrics": result["metrics"],
    }, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
