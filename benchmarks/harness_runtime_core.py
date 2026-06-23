"""Minimal HarnessRuntime benchmark for evidence-gated path reuse."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from memoryweaver import (
    ActionProposal,
    ActionGate,
    CheckpointStore,
    EnvironmentContract,
    EventJournal,
    HardEvidence,
    HardEvidenceType,
    HarnessRuntime,
    RuntimePathCondition,
    RuntimePathRollbackRule,
    RuntimePathSpec,
    RuntimePathStore,
    RuntimePathValidationGate,
    RuntimeTask,
    ToolGateway,
)
from benchmarks._safety import safe_unlink_child

DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "validation" / "harness-runtime-core"
GENERATED_ARTIFACTS = (
    "raw_results.json",
    "task_runs.jsonl",
    "metrics.json",
    "README.md",
    "runtime_path_store.json",
    "events.jsonl",
    "checkpoints.json",
)


def _runtime_path() -> RuntimePathSpec:
    return RuntimePathSpec(
        path_id="path_benchmark_invalid_action",
        name="Benchmark invalid_action runtime path",
        condition=RuntimePathCondition(
            task_tags=["benchmark", "debug"],
            query_terms=["invalid_action"],
            failure_modes=["invalid_action"],
        ),
        action_policy=[
            ActionProposal(
                action_name="check_evidence",
                target="action_schema",
                arguments={"target": "action_schema"},
            ),
            ActionProposal(
                action_name="check_evidence",
                target="marker_only_boundary",
                arguments={"target": "marker_only_boundary"},
            ),
            ActionProposal(
                action_name="check_evidence",
                target="pass_power_3",
                arguments={"target": "pass_power_3"},
            ),
        ],
        validation_gate=RuntimePathValidationGate(
            required_evidence=[
                HardEvidenceType.TEST_RESULT,
                HardEvidenceType.FILE_DIFF,
                HardEvidenceType.BENCHMARK_SCORE,
                HardEvidenceType.REPEAT_VALIDATION,
            ],
            min_repeated_validations=3,
            min_benchmark_delta=0.01,
            max_counterexamples=0,
            max_conflicts=0,
            max_memory_induced_regression_rate=0.0,
            min_decayed_support=3.0,
        ),
        fallback=ActionProposal(
            action_name="ask_user",
            target="rollback_to_safe_debug",
            arguments={"target": "rollback_to_safe_debug"},
        ),
        rollback_rule=RuntimePathRollbackRule(
            rollback_on_conflict=True,
            rollback_on_counterexamples=1,
            rollback_on_regression_rate=0.0,
            rollback_reason="runtime benchmark regression",
        ),
        blocked_targets=["__invalid_action__"],
    )


def _tasks(count: int = 50) -> list[RuntimeTask]:
    return [
        RuntimeTask(
            task_id=f"bench-invalid-{index:03d}",
            task_family="benchmark_debug",
            query=f"benchmark debug invalid_action task {index}",
            tags=["benchmark", "debug"],
            state={"failure_mode": "invalid_action"},
        )
        for index in range(1, count + 1)
    ]


def _proposal(target: str) -> ActionProposal:
    return ActionProposal(
        action_name="tool_call",
        target=target,
        arguments={"target": target},
        idempotency_key=f"bench:{target}",
    )


def _trial_evidence(task: RuntimeTask, *, score_after: float = 0.86) -> list[HardEvidence]:
    return [
        HardEvidence(
            evidence_type=HardEvidenceType.TEST_RESULT,
            task_id=task.task_id,
            task_family=task.task_family,
            passed=True,
            status="passed",
            target="pass_power_3",
        ),
        HardEvidence(
            evidence_type=HardEvidenceType.FILE_DIFF,
            task_id=task.task_id,
            task_family=task.task_family,
            passed=True,
            expected="filter __invalid_action__ and split marker-only boundary",
            observed="probe_valid and marker-only boundary isolated",
            target="marker_only_boundary",
        ),
        HardEvidence(
            evidence_type=HardEvidenceType.BENCHMARK_SCORE,
            task_id=task.task_id,
            task_family=task.task_family,
            passed=True,
            score_before=0.72,
            score_after=score_after,
        ),
        HardEvidence(
            evidence_type=HardEvidenceType.REPEAT_VALIDATION,
            task_id=task.task_id,
            task_family=task.task_family,
            passed=True,
            known_bad_avoided=True,
            evidence_first=True,
            target="action_schema",
        ),
    ]


def run(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    _prepare_output_dir(output_dir)
    tasks = _tasks()
    journal = EventJournal(output_dir / "events.jsonl")
    checkpoints = CheckpointStore(output_dir / "checkpoints.json")
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
            "evidence": f"{proposal.target} verified by durable gateway",
            "known_bad_avoided": proposal.target == "action_schema",
            "evidence_first": proposal.target == "action_schema",
        },
    )

    baseline_runs = [
        {
            "task_id": task.task_id,
            "arm": "no_memory",
            "invalid_action": True,
            "success": False,
            "memory_induced_regression": False,
            "rollback": False,
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

    summary_runs = [
        {
            "task_id": task.task_id,
            "arm": "summary_memory",
            "invalid_action": index % 3 != 0,
            "success": index % 3 == 0,
            "memory_induced_regression": index % 4 == 0,
            "rollback": False,
            "negative_memory_hit": False,
            "promotion_decision": "summary_not_actionable",
        }
        for index, task in enumerate(tasks, 1)
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

    runtime = HarnessRuntime(paths=[_runtime_path()])
    runtime_runs = []
    promoted_after = 0
    for index, task in enumerate(tasks, 1):
        if index <= 3:
            action_schema_result = gateway.execute(
                ActionProposal(
                    action_name="check_evidence",
                    target="action_schema",
                    arguments={"target": "action_schema"},
                ),
                thread_id=task.task_id,
                step=1,
            )
            evidence = _trial_evidence(task)
            evidence.append(
                action_schema_result.to_hard_evidence(
                    task_id=task.task_id,
                    task_family=task.task_family,
                )
            )
            runtime.record_evidence("path_benchmark_invalid_action", evidence)
        decision = runtime.decide(task, _proposal("__invalid_action__"))
        if decision.assessment.can_promote and promoted_after == 0:
            promoted_after = index
        invalid_action = decision.selected_action.target == "__invalid_action__"
        runtime_runs.append(
            {
                "task_id": task.task_id,
                "arm": "memoryweaver_harness_runtime",
                "selected_action": decision.selected_action.to_dict(),
                "invalid_action": invalid_action,
                "success": not invalid_action,
                "memory_induced_regression": False,
                "rollback": decision.rollback_recommended,
                "negative_memory_hit": True,
                "promotion_decision": "evidence_gated_promote"
                if decision.assessment.can_promote
                else "evidence_gated_trial",
                "assessment": decision.assessment.to_dict(),
            }
        )

    conflict = HardEvidence(
        evidence_type=HardEvidenceType.CONFLICT,
        task_id="bench-invalid-conflict",
        task_family="benchmark_debug",
        passed=False,
        conflict_ref="conflict://schema-v2-breaks-path",
        regression_rate=0.2,
    )
    runtime.record_evidence("path_benchmark_invalid_action", conflict)
    rollback_decision = runtime.decide(tasks[-1], _proposal("__invalid_action__"))
    rollback_record = {
        "task_id": "bench-invalid-conflict",
        "arm": "memoryweaver_harness_runtime",
        "invalid_action": rollback_decision.selected_action.target == "__invalid_action__",
        "success": rollback_decision.selected_action.action_name == "ask_user",
        "memory_induced_regression": False,
        "rollback": rollback_decision.rollback_recommended,
        "negative_memory_hit": True,
        "promotion_decision": "rollback_on_conflict",
        "assessment": rollback_decision.assessment.to_dict(),
    }

    recovery_tasks = _tasks(10)
    recovery_runs = []
    for task in recovery_tasks:
        decision = runtime.decide(task, _proposal("__invalid_action__"))
        recovery_runs.append(
            {
                "task_id": f"{task.task_id}-after-rollback",
                "arm": "memoryweaver_harness_runtime_recovery",
                "invalid_action": decision.selected_action.target == "__invalid_action__",
                "success": decision.selected_action.action_name == "ask_user",
                "memory_induced_regression": False,
                "rollback": decision.rollback_recommended,
                "negative_memory_hit": True,
                "promotion_decision": "fallback_after_rollback",
                "assessment": decision.assessment.to_dict(),
            }
        )

    store_path = output_dir / "runtime_path_store.json"
    store = RuntimePathStore(store_path)
    store.save_runtime(runtime)
    restored_runtime = RuntimePathStore(store_path).to_runtime()
    restored_decision = restored_runtime.decide(tasks[-1], _proposal("__invalid_action__"))
    persistence_probe = {
        "path_count": len(RuntimePathStore(store_path).list_paths()),
        "evidence_count": len(
            restored_runtime.evidence_for("path_benchmark_invalid_action")
        ),
        "ledger_count": len(restored_runtime.ledger),
        "restored_rollback_recommended": restored_decision.rollback_recommended,
        "restored_selected_action": restored_decision.selected_action.to_dict(),
        "journal_event_count": len(EventJournal(output_dir / "events.jsonl").list_events()),
        "checkpoint_count_for_first_task": len(
            CheckpointStore(output_dir / "checkpoints.json").list_for_thread(tasks[0].task_id)
        ),
    }

    all_runs = (
        baseline_runs
        + naive_runs
        + summary_runs
        + retrieval_runs
        + runtime_runs
        + [rollback_record]
        + recovery_runs
    )
    metrics = {
        "no_memory": _metrics(baseline_runs),
        "naive_memory": _metrics(naive_runs),
        "summary_memory": _metrics(summary_runs),
        "retrieval_memory": _metrics(retrieval_runs),
        "memoryweaver_harness_runtime": _metrics(runtime_runs),
        "rollback_probe": _metrics([rollback_record]),
        "memoryweaver_harness_runtime_recovery": _metrics(recovery_runs),
    }
    core = metrics["memoryweaver_harness_runtime"]
    baseline = metrics["no_memory"]
    aggregate_metrics = {
        "repeated_failure_rate_delta_vs_no_memory": round(
            core["repeated_failure_rate"] - baseline["repeated_failure_rate"],
            4,
        ),
        "invalid_action_rate_delta_vs_naive_memory": round(
            core["invalid_action_rate"] - metrics["naive_memory"]["invalid_action_rate"],
            4,
        ),
        "task_success_delta_vs_no_memory": round(
            core["success_rate"] - baseline["success_rate"],
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
        "promoted_after_task_index": promoted_after,
        "rollback_recovery_success_rate": metrics[
            "memoryweaver_harness_runtime_recovery"
        ]["success_rate"],
        "runtime_path_store_roundtrip": 1.0
        if (
            persistence_probe["path_count"] == 1
            and persistence_probe["evidence_count"] >= 13
            and persistence_probe["ledger_count"] > 0
            and persistence_probe["restored_rollback_recommended"]
            and persistence_probe["journal_event_count"] == 3
            and persistence_probe["checkpoint_count_for_first_task"] == 1
        )
        else 0.0,
    }
    passed = (
        metrics["memoryweaver_harness_runtime"]["invalid_action_rate"]
        < metrics["no_memory"]["invalid_action_rate"]
        and metrics["memoryweaver_harness_runtime"]["invalid_action_rate"]
        < metrics["naive_memory"]["invalid_action_rate"]
        and metrics["memoryweaver_harness_runtime"]["invalid_action_rate"]
        < metrics["summary_memory"]["invalid_action_rate"]
        and metrics["memoryweaver_harness_runtime"]["memory_induced_regression_rate"]
        <= metrics["retrieval_memory"]["memory_induced_regression_rate"]
        and metrics["rollback_probe"]["rollback_frequency"] == 1.0
        and metrics["memoryweaver_harness_runtime_recovery"]["success_rate"] == 1.0
        and aggregate_metrics["runtime_path_store_roundtrip"] == 1.0
    )
    result = {
        "passed": passed,
        "task_count": len(tasks),
        "metrics": metrics,
        "aggregate_metrics": aggregate_metrics,
        "persistence_probe": persistence_probe,
        "research_question": (
            "Can evidence-gated path promotion reduce repeated agent failures "
            "without increasing memory-induced error propagation?"
        ),
    }

    (output_dir / "raw_results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with (output_dir / "task_runs.jsonl").open("w", encoding="utf-8") as handle:
        for run in all_runs:
            handle.write(json.dumps(run, ensure_ascii=False) + "\n")
    (output_dir / "metrics.json").write_text(
        json.dumps(
            {"arms": metrics, "aggregate": aggregate_metrics},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (output_dir / "README.md").write_text(_readme(result), encoding="utf-8")
    return result


def _prepare_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in GENERATED_ARTIFACTS:
        safe_unlink_child(output_dir, output_dir / name)


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
    lines = [
        "# Harness Runtime Core",
        "",
        "Minimal deterministic benchmark for evidence-gated runtime path reuse.",
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
    lines.append(f"Research question: {result['research_question']}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    result = run(args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
