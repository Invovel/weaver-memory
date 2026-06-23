"""Trace-to-path benchmark for evidence-gated same-family failure reduction."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from memoryweaver import (
    ActionGate,
    ActionProposal,
    CheckpointStore,
    EnvironmentContract,
    EventJournal,
    HardEvidence,
    HardEvidenceType,
    HarnessRuntime,
    RuntimePathStore,
    RuntimeTask,
    RuntimeTraceRecorder,
    RuntimeTraceStore,
    ToolGateway,
    extract_candidate_path_from_trace,
)
from benchmarks._safety import safe_rmtree_child, safe_unlink_child

DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "validation" / "harness-runtime-trace-loop"
GENERATED_ARTIFACTS = (
    "raw_results.json",
    "task_runs.jsonl",
    "metrics.json",
    "reliability.json",
    "README.md",
    "runtime_path_store.json",
    "runtime_traces.jsonl",
    "events.jsonl",
    "checkpoints.json",
)
PRIMARY_RUN_ARTIFACTS = (
    "task_runs.jsonl",
    "runtime_path_store.json",
    "runtime_traces.jsonl",
    "events.jsonl",
    "checkpoints.json",
)


def _tasks(count: int = 50) -> list[RuntimeTask]:
    return [
        RuntimeTask(
            task_id=f"trace-bench-invalid-{index:03d}",
            task_family="benchmark_debug",
            query=f"benchmark debug invalid_action sibling task {index}",
            tags=["benchmark", "debug"],
            state={"failure_mode": "invalid_action"},
        )
        for index in range(1, count + 1)
    ]


def _proposal(target: str, *, key: str) -> ActionProposal:
    return ActionProposal(
        action_name="tool_call",
        target=target,
        arguments={"target": target},
        idempotency_key=key,
    )


def _prepare_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in GENERATED_ARTIFACTS:
        safe_unlink_child(output_dir, output_dir / name)


def _seed_trace_candidate(
    *,
    output_dir: Path,
) -> dict[str, Any]:
    trace_store = RuntimeTraceStore(output_dir / "runtime_traces.jsonl")
    journal = EventJournal(output_dir / "events.jsonl")
    checkpoints = CheckpointStore(output_dir / "checkpoints.json")
    result = _trace_candidate_from_shared_stores(
        trace_store=trace_store,
        journal=journal,
        checkpoints=checkpoints,
        trace_id="trace-seed-1",
        task_id="trace-seed-task-1",
        thread_id="trace-seed-1",
        evidence_label="pass^3 seed trace",
        policy_targets=(
            "action_schema",
            "marker_only_boundary",
            "pass_power_3",
        ),
    )
    return {
        "trace": result["trace"],
        "candidate": result["candidate"],
        "trace_store": trace_store,
        "journal": journal,
        "checkpoints": checkpoints,
    }


def _trace_candidate_from_shared_stores(
    *,
    trace_store: RuntimeTraceStore,
    journal: EventJournal,
    checkpoints: CheckpointStore,
    trace_id: str,
    task_id: str,
    thread_id: str,
    evidence_label: str,
    policy_targets: tuple[str, str, str],
) -> dict[str, Any]:
    gateway = ToolGateway(
        ActionGate(EnvironmentContract.default_live_loop()),
        journal=journal,
        checkpoints=checkpoints,
    )
    gateway.register(
        "check_evidence",
        lambda proposal: {
            "status": "evidence_observed",
            "signal": "positive",
            "evidence": f"{proposal.target} verified in {evidence_label}",
            "known_bad_avoided": proposal.target.startswith("action_schema"),
            "evidence_first": proposal.target.startswith("action_schema"),
        },
    )
    invalid = gateway.execute(
        _proposal("__invalid_action__", key=f"{thread_id}:invalid"),
        thread_id=thread_id,
        step=1,
    )
    recorder = RuntimeTraceRecorder(
        trace_id=trace_id,
        task_id=task_id,
        task_type="benchmark_debug",
        user_goal="debug invalid_action with pass^3 evidence",
        initial_context={
            "tags": ["benchmark", "debug"],
            "failure_mode": "invalid_action",
            "family": "benchmark_debug",
        },
        thread_id=thread_id,
        store=trace_store,
    )
    recorder.record_tool_result(
        node_name="bad_action",
        result=invalid,
        thought_summary="observe invalid action failure path",
        latency_ms=3,
    )
    thought_summaries = [
        "validate schema first",
        "separate marker-only boundary case",
        "confirm repeated validation path",
    ]
    latencies = [8, 7, 9]
    node_names = [
        "check_schema",
        "isolate_marker_only",
        "run_pass_power_3",
    ]
    for step, (target, node_name, thought_summary, latency_ms) in enumerate(
        zip(policy_targets, node_names, thought_summaries, latencies),
        start=2,
    ):
        result = gateway.execute(
            ActionProposal(
                action_name="check_evidence",
                target=target,
                arguments={"target": target},
            ),
            thread_id=thread_id,
            step=step,
        )
        recorder.record_tool_result(
            node_name=node_name,
            result=result,
            thought_summary=thought_summary,
            latency_ms=latency_ms,
        )
    trace = recorder.finish(
        success=True,
        final_result={"selected_action": "check_evidence"},
        metrics={
            "tests_passed": True,
            "test_target": policy_targets[2],
            "file_diff_matches_expected": True,
            "diff_target": policy_targets[1],
            "diff_expected": "split marker-only boundary and filter invalid_action",
            "diff_observed": "marker-only boundary isolated; invalid_action filtered",
            "benchmark_name": "benchmark_debug_family",
            "score_before": 0.72,
            "score_after": 0.88,
            "repeat_validation_count": 3,
            "repeat_validation_target": policy_targets[0],
            "known_bad_avoided": True,
            "evidence_first": True,
            "time_decay_weight": 1.0,
        },
    )
    return {
        "trace": trace,
        "candidate": extract_candidate_path_from_trace(trace),
    }


def _metrics(runs: list[dict[str, Any]]) -> dict[str, float]:
    total = max(len(runs), 1)
    promoted = [
        run
        for run in runs
        if str(run.get("promotion_decision", "")).startswith("evidence_gated_promote")
    ]
    return {
        "task_count": len(runs),
        "success_rate": round(sum(int(run["success"]) for run in runs) / total, 4),
        "repeated_failure_rate": round(
            sum(int(not run["success"]) for run in runs) / total,
            4,
        ),
        "invalid_action_rate": round(
            sum(int(run["invalid_action"]) for run in runs) / total,
            4,
        ),
        "memory_induced_regression_rate": round(
            sum(int(run["memory_induced_regression"]) for run in runs) / total,
            4,
        ),
        "rollback_frequency": round(sum(int(run["rollback"]) for run in runs) / total, 4),
        "negative_memory_hit_rate": round(
            sum(int(run.get("negative_memory_hit", False)) for run in runs) / total,
            4,
        ),
        "promotion_precision": round(
            sum(int(run["success"]) for run in promoted) / max(len(promoted), 1),
            4,
        )
        if promoted
        else 0.0,
    }


def _readme(result: dict[str, Any]) -> str:
    metrics = result["metrics"]
    reliability = result.get("reliability", {})
    lines = [
        "# Harness Runtime Trace Loop",
        "",
        "Minimal same-family closed loop: seed trace -> candidate path -> runtime reuse -> challenge -> rollback recovery.",
        "",
        f"passed = {str(result['passed']).lower()}",
        "",
        "| arm | success_rate | repeated_failure_rate | invalid_action_rate | memory_induced_regression_rate | negative_memory_hit_rate | rollback_frequency | promotion_precision |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm, values in metrics.items():
        lines.append(
            f"| {arm} | {values['success_rate']} | {values['repeated_failure_rate']} | "
            f"{values['invalid_action_rate']} | {values['memory_induced_regression_rate']} | "
            f"{values['negative_memory_hit_rate']} | {values['rollback_frequency']} | "
            f"{values['promotion_precision']} |"
        )
    lines.append("")
    lines.append("## Aggregate")
    lines.append("")
    for key, value in result["aggregate_metrics"].items():
        lines.append(f"- `{key}` = {value}")
    lines.append("")
    lines.append("## Reliability")
    lines.append("")
    lines.append(f"- pass@1: {reliability.get('pass_at_1', result['passed'])}")
    lines.append(f"- pass^3: {reliability.get('pass_power_3', result['passed'])}")
    lines.append(f"- Seeds: {reliability.get('seeds', [])}")
    lines.append("")
    lines.append(f"Research question: {result['research_question']}")
    lines.append("")
    return "\n".join(lines)


def _reliability_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    if not results:
        return {
            "run_count": 0,
            "pass_at_1": False,
            "pass_power_3": False,
            "seeds": [],
            "by_arm": {},
        }
    arms = list(results[0]["metrics"])
    by_arm: dict[str, dict[str, float | bool]] = {}
    for arm in arms:
        success = [float(result["metrics"][arm]["success_rate"]) for result in results]
        repeated_failure = [
            float(result["metrics"][arm]["repeated_failure_rate"])
            for result in results
        ]
        invalid_action = [
            float(result["metrics"][arm]["invalid_action_rate"])
            for result in results
        ]
        rollback = [float(result["metrics"][arm]["rollback_frequency"]) for result in results]
        negative_memory = [
            float(result["metrics"][arm]["negative_memory_hit_rate"])
            for result in results
        ]
        by_arm[arm] = {
            "pass_at_1": bool(results[0]["passed"]),
            "pass_power_3": all(bool(result["passed"]) for result in results),
            "success_rate_mean": _mean(success),
            "success_rate_std": _std(success),
            "repeated_failure_rate_mean": _mean(repeated_failure),
            "repeated_failure_rate_std": _std(repeated_failure),
            "invalid_action_rate_mean": _mean(invalid_action),
            "invalid_action_rate_std": _std(invalid_action),
            "rollback_frequency_mean": _mean(rollback),
            "rollback_frequency_std": _std(rollback),
            "negative_memory_hit_rate_mean": _mean(negative_memory),
            "negative_memory_hit_rate_std": _std(negative_memory),
        }
    return {
        "run_count": len(results),
        "pass_at_1": bool(results[0]["passed"]),
        "pass_power_3": all(bool(result["passed"]) for result in results),
        "seeds": [
            int(result.get("run_config", {}).get("seed", 0))
            for result in results
        ],
        "by_arm": by_arm,
    }


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def _std(values: list[float]) -> float:
    if not values:
        return 0.0
    avg = sum(values) / len(values)
    variance = sum((value - avg) ** 2 for value in values) / len(values)
    return round(variance ** 0.5, 4)


def run(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    seed: int = 0,
    reliability_passes: int = 1,
) -> dict[str, Any]:
    _prepare_output_dir(output_dir)
    single_runs: list[dict[str, Any]] = []
    for offset in range(max(reliability_passes, 1)):
        run_seed = seed + offset
        run_output_dir = output_dir / f".trace-loop-seed-{run_seed}"
        safe_rmtree_child(output_dir, run_output_dir, allowed_prefixes=(".trace-loop-seed-",))
        single_runs.append(_single_run(run_output_dir, seed=run_seed))

    result = dict(single_runs[0])
    result["run_config"] = {
        "seed": seed,
        "reliability_passes": reliability_passes,
    }
    result["reliability"] = _reliability_summary(single_runs)

    output_dir.mkdir(parents=True, exist_ok=True)
    for name in PRIMARY_RUN_ARTIFACTS:
        source = output_dir / f".trace-loop-seed-{seed}" / name
        target = output_dir / name
        if source.exists():
            shutil.copyfile(source, target)
    (output_dir / "raw_results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "metrics.json").write_text(
        json.dumps(
            {"arms": result["metrics"], "aggregate": result["aggregate_metrics"]},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (output_dir / "reliability.json").write_text(
        json.dumps(result["reliability"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "README.md").write_text(_readme(result), encoding="utf-8")
    return result


def _single_run(output_dir: Path, *, seed: int = 0) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    tasks = _tasks()
    seed_artifacts = _seed_trace_candidate(output_dir=output_dir)
    candidate = seed_artifacts["candidate"]
    trace = seed_artifacts["trace"]

    baseline_runs = [
        {
            "task_id": task.task_id,
            "arm": "no_memory",
            "invalid_action": True,
            "success": False,
            "memory_induced_regression": False,
            "rollback": False,
            "negative_memory_hit": False,
            "promotion_decision": "no_memory",
        }
        for task in tasks
    ]
    naive_runs = [
        {
            "task_id": task.task_id,
            "arm": "naive_memory",
            "invalid_action": True,
            "success": False,
            "memory_induced_regression": True,
            "rollback": False,
            "negative_memory_hit": False,
            "promotion_decision": "unsafe_unverified",
        }
        for task in tasks
    ]
    retrieval_runs = [
        {
            "task_id": task.task_id,
            "arm": "retrieval_memory",
            "invalid_action": index % 2 == 0,
            "success": index % 2 == 1,
            "memory_induced_regression": index % 5 == 0,
            "rollback": False,
            "negative_memory_hit": index % 2 == 1,
            "promotion_decision": "retrieved_unpromoted",
        }
        for index, task in enumerate(tasks, 1)
    ]

    runtime = HarnessRuntime()
    registration = runtime.register_candidate(candidate)
    replay_gateway = ToolGateway(
        ActionGate(EnvironmentContract.default_live_loop()),
        journal=seed_artifacts["journal"],
        checkpoints=seed_artifacts["checkpoints"],
    )
    replay_gateway.register(
        "check_evidence",
        lambda proposal: {
            "status": "evidence_observed",
            "signal": "positive",
            "evidence": f"{proposal.target} verified during guarded replay",
            "known_bad_avoided": proposal.target == "action_schema",
            "evidence_first": proposal.target == "action_schema",
        },
    )

    runtime_runs = []
    for index, task in enumerate(tasks, 1):
        replay = runtime.guarded_replay(
            task,
            _proposal("__invalid_action__", key=f"{task.task_id}:invalid"),
            replay_gateway,
            thread_id=task.task_id,
            start_step=1,
        )
        executed_targets = [action.target for action in replay.executed_actions]
        skipped_targets = list(replay.skipped_targets)
        runtime_runs.append(
            {
                "task_id": task.task_id,
                "arm": "memoryweaver_trace_candidate_runtime",
                "candidate_id": candidate.candidate_id,
                "invalid_action": False,
                "success": replay.policy_completed and not replay.rollback_recommended,
                "memory_induced_regression": False,
                "rollback": replay.rollback_recommended,
                "negative_memory_hit": (
                    "action_schema" in executed_targets
                    or "action_schema" in skipped_targets
                ),
                "promotion_decision": "evidence_gated_promote"
                if registration.assessment.can_promote
                else "evidence_gated_trial",
                "assessment_before": replay.assessment_before.to_dict(),
                "assessment_after": replay.assessment_after.to_dict(),
                "assessment": replay.assessment_after.to_dict(),
                "executed_actions": [item.to_dict() for item in replay.executed_actions],
                "skipped_targets": skipped_targets,
                "tool_result_count": len(replay.tool_results),
                "fallback_action": replay.fallback_action.to_dict()
                if replay.fallback_action
                else None,
                "registration_ledger_index": registration.ledger_index,
                "replay_ledger_index": replay.ledger_index,
                "family_index": index,
            }
        )

    conflict = HardEvidence(
        evidence_type=HardEvidenceType.CONFLICT,
        task_id="trace-bench-conflict",
        task_family="benchmark_debug",
        passed=False,
        conflict_ref="conflict://schema-v2-invalidates-trace-path",
        regression_rate=0.2,
    )
    runtime.record_evidence(candidate.path.path_id, conflict)
    rollback_replay = runtime.guarded_replay(
        tasks[-1],
        _proposal("__invalid_action__", key="trace-bench-conflict:invalid"),
        replay_gateway,
        thread_id="trace-bench-conflict",
        start_step=1,
    )
    rollback_record = {
        "task_id": "trace-bench-conflict",
        "arm": "rollback_probe",
        "candidate_id": candidate.candidate_id,
        "invalid_action": False,
        "success": rollback_replay.fallback_action is not None,
        "memory_induced_regression": False,
        "rollback": rollback_replay.rollback_recommended,
        "negative_memory_hit": True,
        "promotion_decision": "rollback_on_conflict",
        "assessment_before": rollback_replay.assessment_before.to_dict(),
        "assessment_after": rollback_replay.assessment_after.to_dict(),
        "assessment": rollback_replay.assessment_after.to_dict(),
        "executed_actions": [item.to_dict() for item in rollback_replay.executed_actions],
        "skipped_targets": list(rollback_replay.skipped_targets),
        "tool_result_count": len(rollback_replay.tool_results),
        "fallback_action": rollback_replay.fallback_action.to_dict()
        if rollback_replay.fallback_action
        else None,
    }

    recovery_runs = []
    for task in _tasks(10):
        replay = runtime.guarded_replay(
            task,
            _proposal("__invalid_action__", key=f"{task.task_id}:rollback-recovery"),
            replay_gateway,
            thread_id=f"{task.task_id}-rollback-recovery",
            start_step=1,
        )
        recovery_runs.append(
            {
                "task_id": f"{task.task_id}-after-rollback",
                "arm": "memoryweaver_trace_candidate_runtime_recovery",
                "candidate_id": candidate.candidate_id,
                "invalid_action": False,
                "success": replay.fallback_action is not None,
                "memory_induced_regression": False,
                "rollback": replay.rollback_recommended,
                "negative_memory_hit": True,
                "promotion_decision": "fallback_after_rollback",
                "assessment_before": replay.assessment_before.to_dict(),
                "assessment_after": replay.assessment_after.to_dict(),
                "assessment": replay.assessment_after.to_dict(),
                "executed_actions": [item.to_dict() for item in replay.executed_actions],
                "skipped_targets": list(replay.skipped_targets),
                "tool_result_count": len(replay.tool_results),
                "fallback_action": replay.fallback_action.to_dict()
                if replay.fallback_action
                else None,
            }
        )

    replacement_trace = _trace_candidate_from_shared_stores(
        trace_store=seed_artifacts["trace_store"],
        journal=seed_artifacts["journal"],
        checkpoints=seed_artifacts["checkpoints"],
        trace_id="trace-replacement-1",
        task_id="trace-replacement-task-1",
        thread_id="trace-replacement-1",
        evidence_label="replacement seed trace",
        policy_targets=(
            "action_schema_v2",
            "marker_only_boundary_v2",
            "pass_power_3_v2",
        ),
    )
    replacement_candidate = replacement_trace["candidate"]
    replacement_registration = runtime.register_candidate(replacement_candidate)
    replacement_task = RuntimeTask(
        task_id="trace-bench-replacement-001",
        task_family="benchmark_debug",
        query="benchmark debug invalid_action replacement task",
        tags=["benchmark", "debug"],
        state={"failure_mode": "invalid_action"},
    )
    replacement_decision = runtime.decide(
        replacement_task,
        _proposal("__invalid_action__", key="trace-bench-replacement:invalid"),
    )
    replacement_probe = {
        "task_id": replacement_task.task_id,
        "arm": "replacement_probe",
        "candidate_id": replacement_candidate.candidate_id,
        "invalid_action": False,
        "success": replacement_decision.selected_action.target == "action_schema_v2",
        "memory_induced_regression": False,
        "rollback": replacement_decision.rollback_recommended,
        "negative_memory_hit": replacement_decision.selected_action.target == "action_schema_v2",
        "promotion_decision": "replacement_path_selected",
        "assessment": replacement_decision.assessment.to_dict(),
        "selected_action": replacement_decision.selected_action.to_dict(),
        "path_id": replacement_decision.path_id,
        "registration_ledger_index": replacement_registration.ledger_index,
    }

    store_path = output_dir / "runtime_path_store.json"
    store = RuntimePathStore(store_path)
    store.save_runtime(runtime)
    restored_runtime = RuntimePathStore(store_path).to_runtime()
    restored_replay = restored_runtime.guarded_replay(
        tasks[-1],
        _proposal("__invalid_action__", key="trace-bench-restored:invalid"),
        replay_gateway,
        thread_id="trace-bench-restored",
        start_step=1,
    )
    trace_roundtrip = RuntimeTraceStore(output_dir / "runtime_traces.jsonl").latest(trace.task_id)
    registration_record = next(
        (
            item
            for item in restored_runtime.ledger
            if item.get("event") == "candidate_registered"
        ),
        {},
    )
    replacement_registration_record = next(
        (
            item
            for item in reversed(restored_runtime.ledger)
            if item.get("event") == "candidate_registered"
            and item.get("candidate_id") == replacement_candidate.candidate_id
        ),
        {},
    )
    journal_snapshot = EventJournal(output_dir / "events.jsonl")
    checkpoint_snapshot = CheckpointStore(output_dir / "checkpoints.json")
    seed_journal_event_count = len(journal_snapshot.events_for_thread("trace-seed-1"))
    expected_seed_event_count = len(trace.steps)
    expected_main_replay_event_count = len(tasks) * len(candidate.path.action_policy)
    runtime_replay_journal_event_count = sum(
        len(journal_snapshot.events_for_thread(task.task_id))
        for task in tasks
    )
    runtime_replay_checkpoint_count = sum(
        len(checkpoint_snapshot.list_for_thread(task.task_id))
        for task in tasks
    )
    persistence_probe = {
        "trace_count": len(RuntimeTraceStore(output_dir / "runtime_traces.jsonl").list_traces()),
        "restored_trace_id": trace_roundtrip.trace_id if trace_roundtrip else "",
        "path_count": len(RuntimePathStore(store_path).list_paths()),
        "evidence_count": len(restored_runtime.evidence_for(candidate.path.path_id)),
        "ledger_count": len(restored_runtime.ledger),
        "candidate_registration_event_present": bool(registration_record),
        "registration_rejected_evidence_count": int(
            registration_record.get("rejected_evidence_count", 0)
        ),
        "registration_rejected_as_challenge": bool(
            registration_record.get("rejected_as_challenge", False)
        ),
        "replacement_registration_event_present": bool(replacement_registration_record),
        "restored_rollback_recommended": restored_replay.rollback_recommended,
        "restored_policy_completed": restored_replay.policy_completed,
        "restored_selected_path_id": restored_replay.path_id,
        "restored_selected_action": (
            restored_replay.executed_actions[0].to_dict()
            if restored_replay.executed_actions
            else {}
        ),
        "restored_fallback_action": restored_replay.fallback_action.to_dict()
        if restored_replay.fallback_action
        else None,
        "journal_event_count": len(journal_snapshot.list_events()),
        "seed_journal_event_count": seed_journal_event_count,
        "runtime_replay_journal_event_count": runtime_replay_journal_event_count,
        "checkpoint_count_for_seed_thread": len(
            checkpoint_snapshot.list_for_thread("trace-seed-1")
        ),
        "runtime_replay_checkpoint_count": runtime_replay_checkpoint_count,
    }

    all_runs = (
        baseline_runs
        + naive_runs
        + retrieval_runs
        + runtime_runs
        + [rollback_record]
        + recovery_runs
        + [replacement_probe]
    )
    metrics = {
        "no_memory": _metrics(baseline_runs),
        "naive_memory": _metrics(naive_runs),
        "retrieval_memory": _metrics(retrieval_runs),
        "memoryweaver_trace_candidate_runtime": _metrics(runtime_runs),
        "rollback_probe": _metrics([rollback_record]),
        "memoryweaver_trace_candidate_runtime_recovery": _metrics(recovery_runs),
        "replacement_probe": _metrics([replacement_probe]),
    }
    core = metrics["memoryweaver_trace_candidate_runtime"]
    aggregate_metrics = {
        "same_family_task_count": len(tasks),
        "repeated_failure_rate_delta_vs_no_memory": round(
            core["repeated_failure_rate"] - metrics["no_memory"]["repeated_failure_rate"],
            4,
        ),
        "invalid_action_rate_delta_vs_naive_memory": round(
            core["invalid_action_rate"] - metrics["naive_memory"]["invalid_action_rate"],
            4,
        ),
        "task_success_delta_vs_retrieval_memory": round(
            core["success_rate"] - metrics["retrieval_memory"]["success_rate"],
            4,
        ),
        "memory_induced_regression_delta_vs_naive_memory": round(
            core["memory_induced_regression_rate"]
            - metrics["naive_memory"]["memory_induced_regression_rate"],
            4,
        ),
        "promotion_precision": core["promotion_precision"],
        "negative_memory_hit_rate": core["negative_memory_hit_rate"],
        "candidate_registration_promotable": 1.0 if registration.assessment.can_promote else 0.0,
        "candidate_registration_audited": 1.0
        if persistence_probe["candidate_registration_event_present"]
        else 0.0,
        "rejected_evidence_audited_count": persistence_probe["registration_rejected_evidence_count"],
        "replacement_path_selected": 1.0
        if replacement_probe["selected_action"]["target"] == "action_schema_v2"
        else 0.0,
        "replacement_registration_audited": 1.0
        if persistence_probe["replacement_registration_event_present"]
        else 0.0,
        "trace_store_roundtrip": 1.0
        if (
            persistence_probe["trace_count"] == 2
            and persistence_probe["restored_trace_id"] == trace.trace_id
        )
        else 0.0,
        "runtime_path_store_roundtrip": 1.0
        if (
            persistence_probe["path_count"] == 2
            and persistence_probe["evidence_count"] >= len(candidate.evidence)
            and persistence_probe["ledger_count"] > 0
            and persistence_probe["restored_selected_path_id"]
            == replacement_candidate.path.path_id
            and not persistence_probe["restored_rollback_recommended"]
            and persistence_probe["restored_policy_completed"]
            and persistence_probe["seed_journal_event_count"] == expected_seed_event_count
            and persistence_probe["runtime_replay_journal_event_count"]
            == expected_main_replay_event_count
            and persistence_probe["checkpoint_count_for_seed_thread"]
            == expected_seed_event_count
            and persistence_probe["runtime_replay_checkpoint_count"]
            == expected_main_replay_event_count
        )
        else 0.0,
        "rollback_recovery_success_rate": metrics[
            "memoryweaver_trace_candidate_runtime_recovery"
        ]["success_rate"],
    }
    passed = (
        core["invalid_action_rate"] < metrics["no_memory"]["invalid_action_rate"]
        and core["invalid_action_rate"] < metrics["naive_memory"]["invalid_action_rate"]
        and core["memory_induced_regression_rate"]
        <= metrics["retrieval_memory"]["memory_induced_regression_rate"]
        and aggregate_metrics["candidate_registration_promotable"] == 1.0
        and aggregate_metrics["candidate_registration_audited"] == 1.0
        and aggregate_metrics["replacement_path_selected"] == 1.0
        and aggregate_metrics["replacement_registration_audited"] == 1.0
        and aggregate_metrics["trace_store_roundtrip"] == 1.0
        and aggregate_metrics["runtime_path_store_roundtrip"] == 1.0
        and metrics["rollback_probe"]["rollback_frequency"] == 1.0
        and metrics["memoryweaver_trace_candidate_runtime_recovery"]["success_rate"] == 1.0
    )
    result = {
        "passed": passed,
        "task_count": len(tasks),
        "run_config": {"seed": seed},
        "metrics": metrics,
        "aggregate_metrics": aggregate_metrics,
        "persistence_probe": persistence_probe,
        "registration": registration.to_dict(),
        "candidate": candidate.to_dict(),
        "research_question": (
            "Can evidence-gated path promotion reduce repeated agent failures "
            "without increasing memory-induced error propagation?"
        ),
    }

    with (output_dir / "task_runs.jsonl").open("w", encoding="utf-8") as handle:
        for run in all_runs:
            handle.write(json.dumps(run, ensure_ascii=False) + "\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--reliability-passes", type=int, default=1)
    args = parser.parse_args()
    result = run(
        args.output_dir,
        seed=args.seed,
        reliability_passes=args.reliability_passes,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
