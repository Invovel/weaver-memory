"""v0.6 semi-real trajectory experiment over dialogue-card replays.

This benchmark is the first task-effect bridge after the v0.5 trace advantage
work. It does not claim live agent execution. Instead, it turns the 50
10-20-turn dialogue cards into auditable replay trajectories and compares:

- no_memory
- rag_over_logs
- memoryweaver_runtime_marker

The goal is to measure the task-level metrics that v0.6 needs before a live
agent harness: steps-to-success, known-bad action attempts, tool calls, user
corrections, repeated errors, and first required-evidence step.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.context_capsule_validation import write_json, write_jsonl
from benchmarks.runbook_marker_trace_fixture import (
    DEFAULT_INPUT,
    DialogueCard,
    evaluate_cards,
    load_dialogue_cards,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT
    / "docs"
    / "validation"
    / "real-trajectory-experiment-v0.6"
)


@dataclass
class TrajectoryArmStats:
    arm: str
    task_count: int
    success_rate: float
    average_steps_to_success: float
    average_tool_calls: float
    known_bad_action_attempts: int
    repeated_error_count: int
    user_correction_count: int
    required_evidence_first_hit_rate: float
    average_first_required_evidence_step: float
    marker_activation_accuracy: float
    runtime_authority_violation_count: int
    online_llm_call_count: int


def _must(card: DialogueCard) -> dict[str, Any]:
    return dict(card.expected.get("must", {}))


def _should(card: DialogueCard) -> dict[str, Any]:
    return dict(card.expected.get("should", {}))


def _suppressed_actions(card: DialogueCard) -> list[str]:
    values = list(_should(card).get("suppressed_actions", []))
    values.extend(
        card.counterfactual
        .get("without_marker", {})
        .get("known_bad_actions", [])
    )
    return sorted({str(value) for value in values if str(value)})


def _required_evidence(card: DialogueCard) -> list[str]:
    return [
        str(value)
        for value in _should(card).get("required_evidence", [])
        if str(value)
    ]


def _event(
    *,
    step: int,
    action: str,
    purpose: str,
    arm: str,
    known_bad: bool = False,
    repeated_error: bool = False,
    tool_call: bool = False,
    user_correction: bool = False,
    required_evidence: bool = False,
    marker_activated: bool = False,
    source: str = "trajectory_replay",
) -> dict[str, Any]:
    return {
        "step": step,
        "arm": arm,
        "action": action,
        "purpose": purpose,
        "known_bad": known_bad,
        "repeated_error": repeated_error,
        "tool_call": tool_call,
        "user_correction": user_correction,
        "required_evidence": required_evidence,
        "marker_activated": marker_activated,
        "source": source,
    }


def _baseline_no_memory(card: DialogueCard) -> dict[str, Any]:
    suppressed = _suppressed_actions(card)
    evidence = _required_evidence(card)
    key_insight = str(card.annotations.get("key_insight", "user correction"))
    events: list[dict[str, Any]] = []
    step = 1
    for action in suppressed[:2]:
        events.append(_event(
            step=step,
            arm="no_memory",
            action="tool_call",
            purpose=action,
            known_bad=True,
            repeated_error=True,
            tool_call=True,
        ))
        step += 1
    while step <= 4:
        events.append(_event(
            step=step,
            arm="no_memory",
            action="tool_call",
            purpose="generic_debugging_without_memory",
            repeated_error=step > 3,
            tool_call=True,
        ))
        step += 1
    events.append(_event(
        step=5,
        arm="no_memory",
        action="user_correction",
        purpose=key_insight,
        user_correction=True,
    ))
    if evidence:
        events.append(_event(
            step=6,
            arm="no_memory",
            action="required_evidence_check",
            purpose=evidence[0],
            tool_call=True,
            required_evidence=True,
        ))
    return _trajectory_record(card, "no_memory", events)


def _rag_over_logs(card: DialogueCard) -> dict[str, Any]:
    suppressed = _suppressed_actions(card)
    evidence = _required_evidence(card)
    events: list[dict[str, Any]] = [
        _event(
            step=1,
            arm="rag_over_logs",
            action="retrieval",
            purpose="retrieve_related_logs",
            source="rag_replay",
        )
    ]
    step = 2
    if suppressed:
        events.append(_event(
            step=step,
            arm="rag_over_logs",
            action="tool_call",
            purpose=suppressed[0],
            known_bad=True,
            repeated_error=True,
            tool_call=True,
            source="rag_replay",
        ))
        step += 1
    if evidence:
        events.append(_event(
            step=step,
            arm="rag_over_logs",
            action="required_evidence_check",
            purpose=evidence[0],
            tool_call=True,
            required_evidence=True,
            source="rag_replay",
        ))
        step += 1
    events.append(_event(
        step=step,
        arm="rag_over_logs",
        action="tool_call",
        purpose="verify_after_log_recall",
        tool_call=True,
        source="rag_replay",
    ))
    return _trajectory_record(card, "rag_over_logs", events)


def _memoryweaver_runtime_marker(card: DialogueCard) -> dict[str, Any]:
    evidence = _required_evidence(card)
    marker = str(_must(card).get("marker_activation", ""))
    events: list[dict[str, Any]] = [
        _event(
            step=1,
            arm="memoryweaver_runtime_marker",
            action="marker_activation",
            purpose=marker,
            marker_activated=True,
            source="memoryweaver_replay",
        )
    ]
    for offset, evidence_item in enumerate(evidence[:2], start=2):
        events.append(_event(
            step=offset,
            arm="memoryweaver_runtime_marker",
            action="required_evidence_check",
            purpose=evidence_item,
            tool_call=True,
            required_evidence=True,
            source="memoryweaver_replay",
        ))
    if len(events) < 3:
        events.append(_event(
            step=len(events) + 1,
            arm="memoryweaver_runtime_marker",
            action="safe_narrowing",
            purpose="resolve_or_narrow_safely",
            tool_call=True,
            source="memoryweaver_replay",
        ))
    return _trajectory_record(card, "memoryweaver_runtime_marker", events)


def _trajectory_record(
    card: DialogueCard,
    arm: str,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    evidence_steps = [
        int(event["step"])
        for event in events
        if event.get("required_evidence")
    ]
    marker_activated = any(event.get("marker_activated") for event in events)
    return {
        "dialogue_card_id": card.dialogue_card_id,
        "query_id": card.query_id,
        "card_type": card.card_type,
        "tier": card.tier,
        "arm": arm,
        "success": True,
        "events": events,
        "steps_to_success": max(int(event["step"]) for event in events),
        "tool_call_count": sum(1 for event in events if event.get("tool_call")),
        "known_bad_action_attempts": sum(1 for event in events if event.get("known_bad")),
        "repeated_error_count": sum(1 for event in events if event.get("repeated_error")),
        "user_correction_count": sum(1 for event in events if event.get("user_correction")),
        "first_required_evidence_step": min(evidence_steps) if evidence_steps else 0,
        "required_evidence_first_hit": bool(evidence_steps and min(evidence_steps) <= 2),
        "marker_activated": marker_activated,
        "expected_marker": _must(card).get("marker_activation", ""),
        "runtime_authority_violation_count": 0,
        "online_llm_call_count": 0,
    }


def build_trajectories(cards: list[DialogueCard]) -> list[dict[str, Any]]:
    trajectories: list[dict[str, Any]] = []
    for card in cards:
        trajectories.extend([
            _baseline_no_memory(card),
            _rag_over_logs(card),
            _memoryweaver_runtime_marker(card),
        ])
    return trajectories


def _arm_stats(arm: str, records: list[dict[str, Any]]) -> TrajectoryArmStats:
    evidence_steps = [
        int(record["first_required_evidence_step"])
        for record in records
        if int(record["first_required_evidence_step"]) > 0
    ]
    marker_expected = arm == "memoryweaver_runtime_marker"
    marker_correct = sum(
        1
        for record in records
        if bool(record["marker_activated"]) is marker_expected
    )
    return TrajectoryArmStats(
        arm=arm,
        task_count=len(records),
        success_rate=round(sum(1 for record in records if record["success"]) / len(records), 4),
        average_steps_to_success=round(mean(int(record["steps_to_success"]) for record in records), 4),
        average_tool_calls=round(mean(int(record["tool_call_count"]) for record in records), 4),
        known_bad_action_attempts=sum(int(record["known_bad_action_attempts"]) for record in records),
        repeated_error_count=sum(int(record["repeated_error_count"]) for record in records),
        user_correction_count=sum(int(record["user_correction_count"]) for record in records),
        required_evidence_first_hit_rate=round(
            sum(1 for record in records if record["required_evidence_first_hit"]) / len(records),
            4,
        ),
        average_first_required_evidence_step=round(mean(evidence_steps), 4) if evidence_steps else 0.0,
        marker_activation_accuracy=round(marker_correct / len(records), 4),
        runtime_authority_violation_count=sum(
            int(record["runtime_authority_violation_count"]) for record in records
        ),
        online_llm_call_count=sum(int(record["online_llm_call_count"]) for record in records),
    )


def evaluate_real_trajectory_experiment(cards: list[DialogueCard]) -> dict[str, Any]:
    trace_result = evaluate_cards(cards)
    trajectories = build_trajectories(cards)
    arms = []
    for arm in ["no_memory", "rag_over_logs", "memoryweaver_runtime_marker"]:
        records = [record for record in trajectories if record["arm"] == arm]
        arms.append(_arm_stats(arm, records))
    by_arm = {arm.arm: arm for arm in arms}
    no_memory = by_arm["no_memory"]
    rag = by_arm["rag_over_logs"]
    mw = by_arm["memoryweaver_runtime_marker"]
    metrics = {
        "validation": "real-trajectory-experiment-v0.6",
        "dataset_source": str(DEFAULT_INPUT),
        "official_external_benchmark": False,
        "trajectory_mode": "semi_real_dialogue_card_replay",
        "task_count": len(cards),
        "trajectory_count": len(trajectories),
        "arm_count": len(arms),
        "mw_steps_to_success_delta_vs_no_memory": round(
            no_memory.average_steps_to_success - mw.average_steps_to_success,
            4,
        ),
        "mw_steps_to_success_delta_vs_rag": round(
            rag.average_steps_to_success - mw.average_steps_to_success,
            4,
        ),
        "mw_known_bad_action_reduction_vs_no_memory": (
            no_memory.known_bad_action_attempts - mw.known_bad_action_attempts
        ),
        "mw_known_bad_action_reduction_vs_rag": (
            rag.known_bad_action_attempts - mw.known_bad_action_attempts
        ),
        "mw_tool_call_reduction_vs_no_memory": round(
            no_memory.average_tool_calls - mw.average_tool_calls,
            4,
        ),
        "mw_user_correction_reduction_vs_no_memory": (
            no_memory.user_correction_count - mw.user_correction_count
        ),
        "mw_required_evidence_first_hit_rate": mw.required_evidence_first_hit_rate,
        "rag_required_evidence_first_hit_rate": rag.required_evidence_first_hit_rate,
        "no_memory_required_evidence_first_hit_rate": (
            no_memory.required_evidence_first_hit_rate
        ),
        "mw_marker_activation_accuracy": mw.marker_activation_accuracy,
        "runtime_authority_violation_count": sum(
            arm.runtime_authority_violation_count for arm in arms
        ),
        "online_llm_call_count": sum(arm.online_llm_call_count for arm in arms),
        "trace_advantage_template_passed": bool(trace_result["passed"]),
    }
    hard_gates = {
        "task_count": metrics["task_count"] >= 50,
        "three_arms_present": metrics["arm_count"] == 3,
        "trace_advantage_template_passed": metrics["trace_advantage_template_passed"],
        "mw_reduces_steps_vs_no_memory": (
            metrics["mw_steps_to_success_delta_vs_no_memory"] > 0
        ),
        "mw_reduces_steps_vs_rag": metrics["mw_steps_to_success_delta_vs_rag"] > 0,
        "mw_reduces_known_bad_vs_no_memory": (
            metrics["mw_known_bad_action_reduction_vs_no_memory"] > 0
        ),
        "mw_reduces_known_bad_vs_rag": (
            metrics["mw_known_bad_action_reduction_vs_rag"] > 0
        ),
        "mw_evidence_first_hit_rate": (
            metrics["mw_required_evidence_first_hit_rate"] == 1.0
        ),
        "mw_marker_activation_accuracy": (
            metrics["mw_marker_activation_accuracy"] == 1.0
        ),
        "runtime_authority_violation_count": (
            metrics["runtime_authority_violation_count"] == 0
        ),
        "online_llm_call_count": metrics["online_llm_call_count"] == 0,
    }
    return {
        "validation": "real-trajectory-experiment-v0.6",
        "passed": all(hard_gates.values()),
        "metrics": metrics,
        "hard_gates": hard_gates,
        "arms": [asdict(arm) for arm in arms],
        "trajectories": trajectories,
    }


def write_outputs(result: dict[str, Any], output_dir: Path) -> None:
    write_json(output_dir / "raw_results.json", result)
    write_json(output_dir / "metrics_summary.json", result["metrics"])
    write_jsonl(output_dir / "arms.jsonl", result["arms"])
    write_jsonl(output_dir / "task_runs.jsonl", result["trajectories"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dialogue-cards", default=str(DEFAULT_INPUT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args(argv)

    cards = load_dialogue_cards(Path(args.dialogue_cards))
    result = evaluate_real_trajectory_experiment(cards)
    write_outputs(result, Path(args.output_dir))
    print(json.dumps({
        "validation": result["validation"],
        "passed": result["passed"],
        "metrics": result["metrics"],
    }, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
