"""Validate hash-chained decision / approval ledger records.

The ledger is the audit substrate for runtime marker authority. It records why a
marker decision was applied or blocked, which policy was used, which approval or
conflict records mattered, and which side effects remained zero.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.l2_route_approval_validation import (
    DEFAULT_APPROVALS,
    DEFAULT_CARDS,
    DEFAULT_CONFLICTS,
    DEFAULT_CONTEXT_FIXTURE,
    DEFAULT_MARKERS,
    evaluate_l2_route_approval,
    write_json,
    write_jsonl,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT
    / "docs"
    / "validation"
    / "decision-ledger-v0.5.2"
)
ZERO_HASH = "0" * 64


def canonical_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def record_hash(record: dict[str, Any]) -> str:
    payload = dict(record)
    payload.pop("record_hash", None)
    return sha256_text(canonical_json(payload))


def build_decision_record(
    trace: dict[str, Any],
    *,
    sequence: int,
    previous_hash: str,
) -> dict[str, Any]:
    approval = dict(trace.get("approval", {}))
    conflicts = list(trace.get("conflict_candidates", []))
    output_mode = str(trace.get("output_mode", ""))
    record = {
        "decision_id": f"decision_{sequence:03d}_{trace['marker_id']}",
        "sequence": sequence,
        "previous_hash": previous_hash,
        "policy_version": "decision-ledger-policy-v1",
        "source_policy": trace.get("policy", ""),
        "dialogue_card_id": trace.get("dialogue_card_id", ""),
        "marker_id": trace.get("marker_id", ""),
        "intervention_level": trace.get("intervention_level", ""),
        "output_mode": output_mode,
        "decision": (
            "apply_plan"
            if output_mode in {"controlled_active_guard", "approved_l2_route_plan"}
            else "block_or_pending"
        ),
        "actual_route": trace.get("actual_route", "thinking"),
        "actual_required_evidence": trace.get("actual_required_evidence", []),
        "actual_suppressed_actions": trace.get("actual_suppressed_actions", []),
        "block_reasons": trace.get("block_reasons", []),
        "approval_id": approval.get("approval_id", ""),
        "approval_decision": approval.get("decision", ""),
        "conflict_refs": [
            {
                "conflict_type": conflict.get("conflict_type", ""),
                "action": conflict.get("action", ""),
                "status": conflict.get("status", ""),
            }
            for conflict in conflicts
        ],
        "bound_capsule_ids": trace.get("bound_capsule_ids", []),
        "raw_refs": trace.get("raw_refs", []),
        "side_effects": {
            "tool_execution_count": trace.get("tool_execution_count", 0),
            "actual_suppression_count": len(trace.get("actual_suppressed_actions", [])),
            "memory_promotion_count": trace.get("memory_promotion_count", 0),
            "layer3_mutation_count": trace.get("layer3_mutation_count", 0),
            "online_llm_call_count": trace.get("online_llm_call_count", 0),
        },
    }
    record["record_hash"] = record_hash(record)
    return record


def validate_hash_chain(records: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    previous = ZERO_HASH
    for index, record in enumerate(records, 1):
        if record.get("sequence") != index:
            errors.append(f"sequence mismatch at {index}")
        if record.get("previous_hash") != previous:
            errors.append(f"previous_hash mismatch at {index}")
        if record.get("record_hash") != record_hash(record):
            errors.append(f"record_hash mismatch at {index}")
        previous = str(record.get("record_hash", ""))
    return errors


def evaluate_decision_ledger(
    *,
    context_fixture: Path,
    markers_path: Path,
    cards_path: Path,
    conflicts_path: Path,
    approvals_path: Path,
    workspace_root: Path,
) -> dict[str, Any]:
    route_result = evaluate_l2_route_approval(
        context_fixture=context_fixture,
        markers_path=markers_path,
        cards_path=cards_path,
        conflicts_path=conflicts_path,
        approvals_path=approvals_path,
        workspace_root=workspace_root,
    )
    records: list[dict[str, Any]] = []
    previous_hash = ZERO_HASH
    for sequence, trace in enumerate(route_result["traces"], 1):
        record = build_decision_record(
            trace,
            sequence=sequence,
            previous_hash=previous_hash,
        )
        records.append(record)
        previous_hash = str(record["record_hash"])

    hash_errors = validate_hash_chain(records)
    applied = [record for record in records if record["decision"] == "apply_plan"]
    blocked = [record for record in records if record["decision"] == "block_or_pending"]
    side_effect_total = sum(
        sum(int(value) for value in record["side_effects"].values())
        for record in records
    )
    approved_l2 = [
        record
        for record in records
        if record["intervention_level"] == "L2_route"
        and record["decision"] == "apply_plan"
    ]
    metrics = {
        "decision_count": len(records),
        "hash_chain_valid": not hash_errors,
        "applied_plan_count": len(applied),
        "blocked_or_pending_count": len(blocked),
        "approved_l2_decision_count": len(approved_l2),
        "approved_l2_with_approval_id_count": sum(
            1 for record in approved_l2 if record["approval_id"]
        ),
        "blocked_with_reason_count": sum(1 for record in blocked if record["block_reasons"]),
        "conflict_ref_count": sum(len(record["conflict_refs"]) for record in records),
        "raw_ref_attached_count": sum(1 for record in records if record["raw_refs"]),
        "capsule_ref_attached_count": sum(
            1 for record in records if record["bound_capsule_ids"]
        ),
        "side_effect_total": side_effect_total,
    }
    hard_gates = {
        "decision_count": metrics["decision_count"] == 5,
        "hash_chain_valid": metrics["hash_chain_valid"] is True,
        "approved_l2_with_approval_id_count": (
            metrics["approved_l2_with_approval_id_count"] == 1
        ),
        "blocked_with_reason_count": metrics["blocked_with_reason_count"] >= 3,
        "conflict_ref_count": metrics["conflict_ref_count"] >= 1,
        "raw_ref_attached_count": metrics["raw_ref_attached_count"] == 5,
        "capsule_ref_attached_count": metrics["capsule_ref_attached_count"] == 5,
        "side_effect_total": metrics["side_effect_total"] == 0,
    }
    return {
        "validation": "decision-ledger-v0.5.2",
        "passed": all(hard_gates.values()),
        "policy": {
            "version": "decision-ledger-policy-v1",
            "hash_algorithm": "sha256",
            "hash_chain": True,
            "records_policy_version": True,
            "records_approval_id": True,
            "records_conflict_refs": True,
            "records_capsule_and_raw_refs": True,
            "records_zero_side_effects": True,
        },
        "metrics": metrics,
        "hard_gates": hard_gates,
        "hash_errors": hash_errors,
        "decisions": records,
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
    result = evaluate_decision_ledger(
        context_fixture=Path(args.context_fixture),
        markers_path=Path(args.markers),
        cards_path=Path(args.cards),
        conflicts_path=Path(args.conflicts),
        approvals_path=Path(args.approvals),
        workspace_root=output_dir / ".memoryweaver-decision-ledger",
    )
    write_json(output_dir / "raw_results.json", result)
    write_json(output_dir / "metrics_summary.json", result["metrics"])
    write_jsonl(output_dir / "decisions.jsonl", result["decisions"])
    print(json.dumps({
        "validation": result["validation"],
        "passed": result["passed"],
        "metrics": result["metrics"],
    }, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
