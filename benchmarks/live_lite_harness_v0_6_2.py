"""v0.6.2 live-lite harness with deterministic mock tools.

v0.6.1 recorded controlled tool plans. v0.6.2 executes a tiny in-memory mock
tool runtime so task trajectories contain actual tool results:

- known-bad actions return failed_known_bad
- generic debugging returns no_signal
- required evidence checks return evidence_observed

No shell command, network call, LLM provider, memory promotion, or Layer-3
mutation is performed. This is the final local bridge before a real harness can
execute sandboxed tools.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.context_capsule_validation import write_json, write_jsonl
from benchmarks.real_trajectory_experiment_v0_6 import (
    DEFAULT_INPUT,
    _required_evidence,
    _suppressed_actions,
)
from benchmarks.runbook_marker_trace_fixture import DialogueCard, load_dialogue_cards


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT
    / "docs"
    / "validation"
    / "live-lite-harness-v0.6.2"
)
ZERO_HASH = "0" * 64


@dataclass
class LiveLiteArmStats:
    arm: str
    task_count: int
    success_rate: float
    average_steps_to_success: float
    average_mock_tool_calls: float
    known_bad_action_attempts: int
    known_bad_tool_failures: int
    known_bad_warning_count: int
    repeated_error_count: int
    user_correction_count: int
    required_evidence_first_hit_rate: float
    average_first_required_evidence_step: float
    evidence_observed_count: int
    decision_count: int
    hash_chain_valid: bool
    unsafe_mock_tool_execution_count: int
    real_tool_execution_count: int
    memory_promotion_count: int
    layer3_mutation_count: int
    online_llm_call_count: int


class MockToolRuntime:
    """Deterministic in-memory tool runner for v0.6.2."""

    def execute(
        self,
        *,
        name: str,
        known_bad: bool = False,
        required_evidence: bool = False,
    ) -> dict[str, Any]:
        if known_bad:
            status = "failed_known_bad"
            signal = "negative"
        elif required_evidence:
            status = "evidence_observed"
            signal = "positive"
        else:
            status = "no_signal"
            signal = "neutral"
        return {
            "tool_name": name,
            "mock": True,
            "status": status,
            "signal": signal,
            "real_execution": False,
        }


def _canonical_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash_record(record: dict[str, Any]) -> str:
    payload = dict(record)
    payload.pop("record_hash", None)
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _must(card: DialogueCard) -> dict[str, Any]:
    return dict(card.expected.get("must", {}))


def _decision(
    *,
    sequence: int,
    previous_hash: str,
    card: DialogueCard,
    arm: str,
    policy_action: str,
    route: str,
    marker_id: str = "",
    required_evidence: list[str] | None = None,
    known_bad_warnings: list[str] | None = None,
) -> dict[str, Any]:
    record = {
        "decision_id": f"live_lite_decision_{sequence:03d}_{arm}_{card.dialogue_card_id}",
        "sequence": sequence,
        "previous_hash": previous_hash,
        "policy_version": "live-lite-harness-policy-v1",
        "dialogue_card_id": card.dialogue_card_id,
        "query_id": card.query_id,
        "arm": arm,
        "policy_action": policy_action,
        "route": route,
        "marker_id": marker_id,
        "required_evidence": required_evidence or [],
        "known_bad_warnings": known_bad_warnings or [],
        "side_effects": {
            "real_tool_execution_count": 0,
            "memory_promotion_count": 0,
            "layer3_mutation_count": 0,
            "online_llm_call_count": 0,
        },
    }
    record["record_hash"] = _hash_record(record)
    return record


def _event(
    *,
    step: int,
    arm: str,
    action: str,
    purpose: str,
    tool_result: dict[str, Any] | None = None,
    known_bad: bool = False,
    known_bad_warning: bool = False,
    repeated_error: bool = False,
    user_correction: bool = False,
    required_evidence: bool = False,
    marker_activated: bool = False,
) -> dict[str, Any]:
    return {
        "step": step,
        "arm": arm,
        "action": action,
        "purpose": purpose,
        "tool_result": tool_result,
        "mock_tool_call": tool_result is not None,
        "known_bad": known_bad,
        "known_bad_warning": known_bad_warning,
        "repeated_error": repeated_error,
        "user_correction": user_correction,
        "required_evidence": required_evidence,
        "marker_activated": marker_activated,
    }


def _no_memory_run(
    card: DialogueCard,
    decision: dict[str, Any],
    runtime: MockToolRuntime,
) -> dict[str, Any]:
    suppressed = _suppressed_actions(card)
    evidence = _required_evidence(card)
    events: list[dict[str, Any]] = []
    step = 1
    for action in suppressed[:2]:
        events.append(_event(
            step=step,
            arm="no_memory",
            action="mock_tool",
            purpose=action,
            tool_result=runtime.execute(name=action, known_bad=True),
            known_bad=True,
            repeated_error=True,
        ))
        step += 1
    while step <= 4:
        events.append(_event(
            step=step,
            arm="no_memory",
            action="mock_tool",
            purpose="generic_debugging_without_memory",
            tool_result=runtime.execute(name="generic_debugging_without_memory"),
            repeated_error=step > 3,
        ))
        step += 1
    events.append(_event(
        step=5,
        arm="no_memory",
        action="user_correction",
        purpose=str(card.annotations.get("key_insight", "user correction")),
        user_correction=True,
    ))
    if evidence:
        events.append(_event(
            step=6,
            arm="no_memory",
            action="mock_tool",
            purpose=evidence[0],
            tool_result=runtime.execute(name=evidence[0], required_evidence=True),
            required_evidence=True,
        ))
    return _task_run(card, "no_memory", decision, events)


def _rag_run(
    card: DialogueCard,
    decision: dict[str, Any],
    runtime: MockToolRuntime,
) -> dict[str, Any]:
    suppressed = _suppressed_actions(card)
    evidence = _required_evidence(card)
    events: list[dict[str, Any]] = [
        _event(
            step=1,
            arm="rag_over_logs",
            action="retrieval",
            purpose="retrieve_related_logs",
        )
    ]
    step = 2
    if suppressed:
        events.append(_event(
            step=step,
            arm="rag_over_logs",
            action="mock_tool",
            purpose=suppressed[0],
            tool_result=runtime.execute(name=suppressed[0], known_bad=True),
            known_bad=True,
            repeated_error=True,
        ))
        step += 1
    if evidence:
        events.append(_event(
            step=step,
            arm="rag_over_logs",
            action="mock_tool",
            purpose=evidence[0],
            tool_result=runtime.execute(name=evidence[0], required_evidence=True),
            required_evidence=True,
        ))
        step += 1
    events.append(_event(
        step=step,
        arm="rag_over_logs",
        action="mock_tool",
        purpose="verify_after_log_recall",
        tool_result=runtime.execute(name="verify_after_log_recall"),
    ))
    return _task_run(card, "rag_over_logs", decision, events)


def _memoryweaver_run(
    card: DialogueCard,
    decision: dict[str, Any],
    runtime: MockToolRuntime,
) -> dict[str, Any]:
    evidence = _required_evidence(card)
    warnings = _suppressed_actions(card)
    marker = str(_must(card).get("marker_activation", ""))
    events: list[dict[str, Any]] = [
        _event(
            step=1,
            arm="memoryweaver_runtime_marker",
            action="marker_policy_decision",
            purpose=marker,
            marker_activated=True,
        )
    ]
    for warning in warnings[:2]:
        events.append(_event(
            step=1,
            arm="memoryweaver_runtime_marker",
            action="known_bad_warning",
            purpose=warning,
            known_bad_warning=True,
        ))
    for offset, evidence_item in enumerate(evidence[:2], start=2):
        events.append(_event(
            step=offset,
            arm="memoryweaver_runtime_marker",
            action="mock_tool",
            purpose=evidence_item,
            tool_result=runtime.execute(name=evidence_item, required_evidence=True),
            required_evidence=True,
        ))
    return _task_run(card, "memoryweaver_runtime_marker", decision, events)


def _task_run(
    card: DialogueCard,
    arm: str,
    decision: dict[str, Any],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    evidence_steps = [
        int(event["step"])
        for event in events
        if event.get("required_evidence")
    ]
    mock_tool_calls = [event for event in events if event.get("mock_tool_call")]
    known_bad_failures = [
        event for event in events
        if (event.get("tool_result") or {}).get("status") == "failed_known_bad"
    ]
    evidence_observed = [
        event for event in events
        if (event.get("tool_result") or {}).get("status") == "evidence_observed"
    ]
    return {
        "dialogue_card_id": card.dialogue_card_id,
        "query_id": card.query_id,
        "card_type": card.card_type,
        "arm": arm,
        "decision_id": decision["decision_id"],
        "policy_action": decision["policy_action"],
        "route": decision["route"],
        "success": bool(evidence_observed),
        "events": events,
        "steps_to_success": max(int(event["step"]) for event in events),
        "mock_tool_call_count": len(mock_tool_calls),
        "known_bad_action_attempts": sum(1 for event in events if event.get("known_bad")),
        "known_bad_tool_failures": len(known_bad_failures),
        "known_bad_warning_count": sum(1 for event in events if event.get("known_bad_warning")),
        "repeated_error_count": sum(1 for event in events if event.get("repeated_error")),
        "user_correction_count": sum(1 for event in events if event.get("user_correction")),
        "first_required_evidence_step": min(evidence_steps) if evidence_steps else 0,
        "required_evidence_first_hit": bool(evidence_steps and min(evidence_steps) <= 2),
        "evidence_observed_count": len(evidence_observed),
        "unsafe_mock_tool_execution_count": len(known_bad_failures),
        "real_tool_execution_count": 0,
        "memory_promotion_count": 0,
        "layer3_mutation_count": 0,
        "online_llm_call_count": 0,
    }


def build_live_lite_runs(cards: list[DialogueCard]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    runtime = MockToolRuntime()
    decisions: list[dict[str, Any]] = []
    task_runs: list[dict[str, Any]] = []
    previous_hash = ZERO_HASH
    sequence = 1
    for card in cards:
        evidence = _required_evidence(card)
        warnings = _suppressed_actions(card)
        marker_id = str(_must(card).get("marker_activation", ""))
        for arm in ["no_memory", "rag_over_logs", "memoryweaver_runtime_marker"]:
            if arm == "no_memory":
                decision = _decision(
                    sequence=sequence,
                    previous_hash=previous_hash,
                    card=card,
                    arm=arm,
                    policy_action="execute_uninformed_mock_plan",
                    route="thinking",
                )
                task_run = _no_memory_run(card, decision, runtime)
            elif arm == "rag_over_logs":
                decision = _decision(
                    sequence=sequence,
                    previous_hash=previous_hash,
                    card=card,
                    arm=arm,
                    policy_action="execute_rag_mock_plan",
                    route="thinking",
                    required_evidence=evidence[:1],
                )
                task_run = _rag_run(card, decision, runtime)
            else:
                decision = _decision(
                    sequence=sequence,
                    previous_hash=previous_hash,
                    card=card,
                    arm=arm,
                    policy_action="execute_marker_evidence_mock_plan",
                    route="fast_verify",
                    marker_id=marker_id,
                    required_evidence=evidence[:2],
                    known_bad_warnings=warnings,
                )
                task_run = _memoryweaver_run(card, decision, runtime)
            decisions.append(decision)
            task_runs.append(task_run)
            previous_hash = str(decision["record_hash"])
            sequence += 1
    return task_runs, decisions


def _validate_hash_chain(decisions: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    previous = ZERO_HASH
    for index, decision in enumerate(decisions, 1):
        if decision.get("sequence") != index:
            errors.append(f"sequence mismatch at {index}")
        if decision.get("previous_hash") != previous:
            errors.append(f"previous hash mismatch at {index}")
        if decision.get("record_hash") != _hash_record(decision):
            errors.append(f"record hash mismatch at {index}")
        previous = str(decision.get("record_hash", ""))
    return errors


def _arm_stats(arm: str, records: list[dict[str, Any]], decisions: list[dict[str, Any]]) -> LiveLiteArmStats:
    evidence_steps = [
        int(record["first_required_evidence_step"])
        for record in records
        if int(record["first_required_evidence_step"]) > 0
    ]
    arm_decisions = [decision for decision in decisions if decision["arm"] == arm]
    return LiveLiteArmStats(
        arm=arm,
        task_count=len(records),
        success_rate=round(sum(1 for record in records if record["success"]) / len(records), 4),
        average_steps_to_success=round(mean(int(record["steps_to_success"]) for record in records), 4),
        average_mock_tool_calls=round(mean(int(record["mock_tool_call_count"]) for record in records), 4),
        known_bad_action_attempts=sum(int(record["known_bad_action_attempts"]) for record in records),
        known_bad_tool_failures=sum(int(record["known_bad_tool_failures"]) for record in records),
        known_bad_warning_count=sum(int(record["known_bad_warning_count"]) for record in records),
        repeated_error_count=sum(int(record["repeated_error_count"]) for record in records),
        user_correction_count=sum(int(record["user_correction_count"]) for record in records),
        required_evidence_first_hit_rate=round(
            sum(1 for record in records if record["required_evidence_first_hit"]) / len(records),
            4,
        ),
        average_first_required_evidence_step=round(mean(evidence_steps), 4) if evidence_steps else 0.0,
        evidence_observed_count=sum(int(record["evidence_observed_count"]) for record in records),
        decision_count=len(arm_decisions),
        hash_chain_valid=True,
        unsafe_mock_tool_execution_count=sum(
            int(record["unsafe_mock_tool_execution_count"]) for record in records
        ),
        real_tool_execution_count=sum(int(record["real_tool_execution_count"]) for record in records),
        memory_promotion_count=sum(int(record["memory_promotion_count"]) for record in records),
        layer3_mutation_count=sum(int(record["layer3_mutation_count"]) for record in records),
        online_llm_call_count=sum(int(record["online_llm_call_count"]) for record in records),
    )


def evaluate_live_lite_harness(cards: list[DialogueCard]) -> dict[str, Any]:
    task_runs, decisions = build_live_lite_runs(cards)
    hash_errors = _validate_hash_chain(decisions)
    arms = [
        _arm_stats(
            arm,
            [record for record in task_runs if record["arm"] == arm],
            decisions,
        )
        for arm in ["no_memory", "rag_over_logs", "memoryweaver_runtime_marker"]
    ]
    for arm in arms:
        arm.hash_chain_valid = not hash_errors
    by_arm = {arm.arm: arm for arm in arms}
    no_memory = by_arm["no_memory"]
    rag = by_arm["rag_over_logs"]
    mw = by_arm["memoryweaver_runtime_marker"]
    metrics = {
        "validation": "live-lite-harness-v0.6.2",
        "task_count": len(cards),
        "task_run_count": len(task_runs),
        "decision_count": len(decisions),
        "hash_chain_valid": not hash_errors,
        "mw_steps_to_success_delta_vs_no_memory": round(no_memory.average_steps_to_success - mw.average_steps_to_success, 4),
        "mw_steps_to_success_delta_vs_rag": round(rag.average_steps_to_success - mw.average_steps_to_success, 4),
        "mw_known_bad_action_reduction_vs_no_memory": no_memory.known_bad_action_attempts - mw.known_bad_action_attempts,
        "mw_known_bad_action_reduction_vs_rag": rag.known_bad_action_attempts - mw.known_bad_action_attempts,
        "mw_known_bad_tool_failure_reduction_vs_no_memory": no_memory.known_bad_tool_failures - mw.known_bad_tool_failures,
        "mw_known_bad_tool_failure_reduction_vs_rag": rag.known_bad_tool_failures - mw.known_bad_tool_failures,
        "mw_required_evidence_first_hit_rate": mw.required_evidence_first_hit_rate,
        "mw_known_bad_warning_count": mw.known_bad_warning_count,
        "mw_evidence_observed_count": mw.evidence_observed_count,
        "mock_tool_execution_count": sum(arm.task_count * arm.average_mock_tool_calls for arm in arms),
        "mw_unsafe_mock_tool_execution_count": mw.unsafe_mock_tool_execution_count,
        "real_tool_execution_count": sum(arm.real_tool_execution_count for arm in arms),
        "memory_promotion_count": sum(arm.memory_promotion_count for arm in arms),
        "layer3_mutation_count": sum(arm.layer3_mutation_count for arm in arms),
        "online_llm_call_count": sum(arm.online_llm_call_count for arm in arms),
    }
    hard_gates = {
        "task_count": metrics["task_count"] >= 50,
        "task_run_count": metrics["task_run_count"] == metrics["task_count"] * 3,
        "decision_count": metrics["decision_count"] == metrics["task_run_count"],
        "hash_chain_valid": metrics["hash_chain_valid"],
        "mock_tool_execution_count": metrics["mock_tool_execution_count"] > 0,
        "mw_reduces_steps_vs_no_memory": metrics["mw_steps_to_success_delta_vs_no_memory"] > 0,
        "mw_reduces_steps_vs_rag": metrics["mw_steps_to_success_delta_vs_rag"] > 0,
        "mw_reduces_bad_tools_vs_no_memory": metrics["mw_known_bad_tool_failure_reduction_vs_no_memory"] > 0,
        "mw_reduces_bad_tools_vs_rag": metrics["mw_known_bad_tool_failure_reduction_vs_rag"] > 0,
        "mw_required_evidence_first_hit_rate": metrics["mw_required_evidence_first_hit_rate"] == 1.0,
        "mw_unsafe_mock_tool_execution_count": metrics["mw_unsafe_mock_tool_execution_count"] == 0,
        "real_tool_execution_count": metrics["real_tool_execution_count"] == 0,
        "memory_promotion_count": metrics["memory_promotion_count"] == 0,
        "layer3_mutation_count": metrics["layer3_mutation_count"] == 0,
        "online_llm_call_count": metrics["online_llm_call_count"] == 0,
    }
    return {
        "validation": "live-lite-harness-v0.6.2",
        "passed": all(hard_gates.values()),
        "policy": {
            "version": "live-lite-harness-policy-v1",
            "tool_runtime": "deterministic_in_memory_mock_tools",
            "allows_mock_tool_execution": True,
            "allows_real_tool_execution": False,
            "allows_memory_promotion": False,
            "allows_layer3_mutation": False,
            "allows_online_llm": False,
        },
        "metrics": metrics,
        "hard_gates": hard_gates,
        "hash_errors": hash_errors,
        "arms": [asdict(arm) for arm in arms],
        "task_runs": task_runs,
        "decisions": decisions,
    }


def write_outputs(result: dict[str, Any], output_dir: Path) -> None:
    write_json(output_dir / "raw_results.json", result)
    write_json(output_dir / "metrics_summary.json", result["metrics"])
    write_jsonl(output_dir / "arms.jsonl", result["arms"])
    write_jsonl(output_dir / "task_runs.jsonl", result["task_runs"])
    write_jsonl(output_dir / "decisions.jsonl", result["decisions"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dialogue-cards", default=str(DEFAULT_INPUT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args(argv)

    result = evaluate_live_lite_harness(load_dialogue_cards(Path(args.dialogue_cards)))
    write_outputs(result, Path(args.output_dir))
    print(json.dumps({
        "validation": result["validation"],
        "passed": result["passed"],
        "metrics": result["metrics"],
    }, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
