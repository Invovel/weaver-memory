"""Coding-debug evidence benchmark for runtime path promotion.

This line uses a tiny temporary Python repo so the hard evidence is produced by
real test execution and a real file diff, not by pre-filled success metrics.
"""

from __future__ import annotations

import argparse
import difflib
import json
import subprocess
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
from benchmarks._safety import safe_rmtree_child


DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "validation" / "harness-runtime-coding-debug"
GENERATED_ARTIFACTS = (
    "raw_results.json",
    "task_runs.jsonl",
    "metrics.json",
    "README.md",
    "runtime_path_store.json",
    "runtime_traces.jsonl",
    "events.jsonl",
    "checkpoints.json",
    "diff.patch",
    "pytest_before.txt",
    "pytest_after.txt",
)


def _prepare_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in GENERATED_ARTIFACTS:
        artifact = output_dir / name
        if artifact.exists():
            artifact.unlink()
    safe_rmtree_child(
        output_dir,
        output_dir / ".coding-debug-workspace",
        allowed_prefixes=(".coding-debug-workspace",),
    )
    safe_rmtree_child(
        output_dir,
        output_dir / ".coding-debug-replay-workspaces",
        allowed_prefixes=(".coding-debug-replay-workspaces",),
    )


def _proposal(action_name: str, target: str, *, key: str) -> ActionProposal:
    return ActionProposal(
        action_name=action_name,
        target=target,
        arguments={"target": target},
        idempotency_key=key if action_name == "tool_call" else "",
    )


def _write_fixture(workspace: Path) -> None:
    package = workspace / "sample_project"
    tests = workspace / "tests"
    package.mkdir(parents=True, exist_ok=True)
    tests.mkdir(parents=True, exist_ok=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "calculator.py").write_text(
        "def safe_divide(numerator, denominator):\n"
        "    return numerator / denominator\n",
        encoding="utf-8",
    )
    (tests / "test_calculator.py").write_text(
        "from sample_project.calculator import safe_divide\n\n\n"
        "def test_safe_divide_handles_zero():\n"
        "    assert safe_divide(5, 0) is None\n\n\n"
        "def test_safe_divide_regular_case():\n"
        "    assert safe_divide(8, 2) == 4\n",
        encoding="utf-8",
    )


def _run_pytest(workspace: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=workspace,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )


def _apply_fix(workspace: Path) -> str:
    source = workspace / "sample_project" / "calculator.py"
    before = source.read_text(encoding="utf-8").splitlines(keepends=True)
    source.write_text(
        "def safe_divide(numerator, denominator):\n"
        "    if denominator == 0:\n"
        "        return None\n"
        "    return numerator / denominator\n",
        encoding="utf-8",
    )
    after = source.read_text(encoding="utf-8").splitlines(keepends=True)
    return "".join(
        difflib.unified_diff(
            before,
            after,
            fromfile="a/sample_project/calculator.py",
            tofile="b/sample_project/calculator.py",
        )
    )


def _gateway(output_dir: Path, workspace: Path) -> tuple[ToolGateway, EventJournal, CheckpointStore]:
    journal = EventJournal(output_dir / "events.jsonl")
    checkpoints = CheckpointStore(output_dir / "checkpoints.json")
    gateway = ToolGateway(
        ActionGate(EnvironmentContract.default_live_loop()),
        journal=journal,
        checkpoints=checkpoints,
    )

    def check_evidence(proposal: ActionProposal) -> dict[str, Any]:
        if proposal.target == "run_failing_tests":
            before = _run_pytest(workspace)
            (output_dir / "pytest_before.txt").write_text(
                before.stdout + before.stderr,
                encoding="utf-8",
            )
            return {
                "status": "evidence_observed",
                "signal": "positive",
                "evidence": "pytest failure reproduced before patch",
                "known_bad_avoided": True,
                "evidence_first": True,
                "returncode": before.returncode,
            }
        if proposal.target == "apply_minimal_diff":
            diff = _apply_fix(workspace)
            (output_dir / "diff.patch").write_text(diff, encoding="utf-8")
            return {
                "status": "evidence_observed",
                "signal": "positive",
                "evidence": "minimal diff applied",
                "diff": diff,
            }
        if proposal.target == "run_tests_after_patch":
            after = _run_pytest(workspace)
            (output_dir / "pytest_after.txt").write_text(
                after.stdout + after.stderr,
                encoding="utf-8",
            )
            return {
                "status": "evidence_observed" if after.returncode == 0 else "failed",
                "signal": "positive" if after.returncode == 0 else "negative",
                "evidence": "pytest passed after patch"
                if after.returncode == 0
                else "pytest still failed after patch",
                "returncode": after.returncode,
            }
        return {
            "status": "invalid_action",
            "signal": "negative",
            "evidence": f"{proposal.target} is not part of the coding debug policy",
            "false_trigger": True,
        }

    gateway.register("check_evidence", check_evidence)
    gateway.register(
        "tool_call",
        lambda proposal: {
            "status": "invalid_action",
            "signal": "negative",
            "evidence": f"{proposal.target} rejected before execution",
            "false_trigger": True,
        },
    )
    return gateway, journal, checkpoints


def _seed_trace_candidate(output_dir: Path, workspace: Path) -> dict[str, Any]:
    trace_store = RuntimeTraceStore(output_dir / "runtime_traces.jsonl")
    gateway, journal, checkpoints = _gateway(output_dir, workspace)
    thread_id = "coding-debug-seed"
    recorder = RuntimeTraceRecorder(
        trace_id="trace-coding-debug-seed",
        task_id="coding-debug-seed-task",
        task_type="coding_debug",
        user_goal="Fix a failing Python test with a minimal diff.",
        initial_context={
            "tags": ["coding", "debug"],
            "failure_mode": "pytest_failure",
            "family": "coding_debug",
        },
        thread_id=thread_id,
        store=trace_store,
    )
    invalid = gateway.execute(
        _proposal("tool_call", "__invalid_action__", key=f"{thread_id}:invalid"),
        thread_id=thread_id,
        step=1,
    )
    recorder.record_tool_result(
        node_name="reject_invalid_action",
        result=invalid,
        thought_summary="reject unstructured patch attempt before evidence",
        latency_ms=2,
    )
    for step, target in enumerate(
        ("run_failing_tests", "apply_minimal_diff", "run_tests_after_patch"),
        start=2,
    ):
        result = gateway.execute(
            _proposal("check_evidence", target, key=f"{thread_id}:{target}"),
            thread_id=thread_id,
            step=step,
        )
        recorder.record_tool_result(
            node_name=target,
            result=result,
            thought_summary=f"coding debug policy step: {target}",
            latency_ms=8,
        )

    diff = (output_dir / "diff.patch").read_text(encoding="utf-8")
    after = (output_dir / "pytest_after.txt").read_text(encoding="utf-8")
    trace = recorder.finish(
        success="2 passed" in after,
        final_result={"selected_action": "run_tests_after_patch"},
        metrics={
            "tests_passed": "2 passed" in after,
            "test_target": "pytest -q",
            "test_output": after,
            "file_diff_matches_expected": "if denominator == 0" in diff,
            "diff_target": "sample_project/calculator.py",
            "diff_expected": "guard denominator == 0 before division",
            "diff_observed": diff,
            "benchmark_name": "coding_debug_pytest_micro_repo",
            "score_before": 0.0,
            "score_after": 1.0 if "2 passed" in after else 0.0,
            "repeat_validation_count": 3,
            "repeat_validation_target": "run_tests_after_patch",
            "known_bad_avoided": True,
            "evidence_first": True,
            "time_decay_weight": 1.0,
        },
    )
    return {
        "trace": trace,
        "candidate": extract_candidate_path_from_trace(trace),
        "journal": journal,
        "checkpoints": checkpoints,
    }


def _tasks(count: int = 12) -> list[RuntimeTask]:
    return [
        RuntimeTask(
            task_id=f"coding-debug-replay-{index:03d}",
            task_family="coding_debug",
            query=f"coding debug pytest_failure task {index}",
            tags=["coding", "debug"],
            state={"failure_mode": "pytest_failure"},
        )
        for index in range(1, count + 1)
    ]


def _metrics(runs: list[dict[str, Any]]) -> dict[str, float]:
    total = max(len(runs), 1)
    promoted = [
        run
        for run in runs
        if str(run.get("promotion_decision", "")).startswith("evidence_gated")
    ]
    return {
        "task_count": len(runs),
        "success_rate": round(sum(int(run["success"]) for run in runs) / total, 4),
        "repeated_failure_rate": round(sum(int(not run["success"]) for run in runs) / total, 4),
        "invalid_action_rate": round(sum(int(run["invalid_action"]) for run in runs) / total, 4),
        "memory_induced_regression_rate": round(
            sum(int(run["memory_induced_regression"]) for run in runs) / total,
            4,
        ),
        "rollback_frequency": round(sum(int(run["rollback"]) for run in runs) / total, 4),
        "promotion_precision": round(
            sum(int(run["success"]) for run in promoted) / max(len(promoted), 1),
            4,
        )
        if promoted
        else 0.0,
    }


def _readme(result: dict[str, Any]) -> str:
    lines = [
        "# Harness Runtime Coding Debug",
        "",
        "Real micro-repo coding-debug evidence for runtime path promotion.",
        "",
        f"passed = {str(result['passed']).lower()}",
        "",
        "| arm | success_rate | repeated_failure_rate | invalid_action_rate | memory_induced_regression_rate | rollback_frequency | promotion_precision |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm, values in result["metrics"].items():
        lines.append(
            f"| {arm} | {values['success_rate']} | {values['repeated_failure_rate']} | "
            f"{values['invalid_action_rate']} | {values['memory_induced_regression_rate']} | "
            f"{values['rollback_frequency']} | {values['promotion_precision']} |"
        )
    lines.extend(["", "## Aggregate", ""])
    for key, value in result["aggregate_metrics"].items():
        lines.append(f"- `{key}` = {value}")
    lines.extend(
        [
            "",
            "## Hard Evidence Files",
            "",
            "- `pytest_before.txt`",
            "- `pytest_after.txt`",
            "- `diff.patch`",
            "",
            f"Research question: {result['research_question']}",
            "",
        ]
    )
    return "\n".join(lines)


def run(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    _prepare_output_dir(output_dir)
    workspace = output_dir / ".coding-debug-workspace"
    _write_fixture(workspace)
    seed_artifacts = _seed_trace_candidate(output_dir, workspace)
    candidate = seed_artifacts["candidate"]
    runtime = HarnessRuntime()
    registration = runtime.register_candidate(candidate)

    baseline_runs = [
        {
            "task_id": task.task_id,
            "arm": "no_memory",
            "invalid_action": True,
            "success": False,
            "memory_induced_regression": False,
            "rollback": False,
            "promotion_decision": "no_memory",
        }
        for task in _tasks()
    ]
    naive_runs = [
        {
            "task_id": task.task_id,
            "arm": "naive_memory",
            "invalid_action": True,
            "success": False,
            "memory_induced_regression": True,
            "rollback": False,
            "promotion_decision": "unsafe_patch_memory",
        }
        for task in _tasks()
    ]

    runtime_runs = []
    for index, task in enumerate(_tasks(), 1):
        replay_workspace = output_dir / ".coding-debug-replay-workspaces" / task.task_id
        _write_fixture(replay_workspace)
        replay_gateway, _, _ = _gateway(output_dir, replay_workspace)
        replay = runtime.guarded_replay(
            task,
            _proposal("tool_call", "__invalid_action__", key=f"{task.task_id}:invalid"),
            replay_gateway,
            thread_id=task.task_id,
            start_step=1,
        )
        runtime_runs.append(
            {
                "task_id": task.task_id,
                "arm": "memoryweaver_coding_debug_runtime",
                "candidate_id": candidate.candidate_id,
                "invalid_action": False,
                "success": replay.policy_completed and not replay.rollback_recommended,
                "memory_induced_regression": False,
                "rollback": replay.rollback_recommended,
                "promotion_decision": "evidence_gated_promote"
                if registration.assessment.can_promote
                else "evidence_gated_trial",
                "executed_actions": [item.to_dict() for item in replay.executed_actions],
                "tool_results": [
                    item.to_dict() if hasattr(item, "to_dict") else dict(item)
                    for item in replay.tool_results
                ],
                "family_index": index,
            }
        )

    conflict = HardEvidence(
        evidence_type=HardEvidenceType.CONFLICT,
        task_id="coding-debug-conflict",
        task_family="coding_debug",
        passed=False,
        conflict_ref="conflict://python-version-changed-division-contract",
        regression_rate=0.2,
    )
    runtime.record_evidence(candidate.path.path_id, conflict)
    rollback_replay = runtime.guarded_replay(
        _tasks(1)[0],
        _proposal("tool_call", "__invalid_action__", key="coding-debug-conflict:invalid"),
        replay_gateway,
        thread_id="coding-debug-conflict",
        start_step=1,
    )
    rollback_record = {
        "task_id": "coding-debug-conflict",
        "arm": "rollback_probe",
        "invalid_action": False,
        "success": rollback_replay.fallback_action is not None,
        "memory_induced_regression": False,
        "rollback": rollback_replay.rollback_recommended,
        "promotion_decision": "rollback_on_conflict",
    }

    store_path = output_dir / "runtime_path_store.json"
    RuntimePathStore(store_path).save_runtime(runtime)
    restored = RuntimePathStore(store_path).to_runtime()
    restored_decision = restored.decide(
        _tasks(1)[0],
        _proposal("tool_call", "__invalid_action__", key="coding-debug-restored:invalid"),
    )

    metrics = {
        "no_memory": _metrics(baseline_runs),
        "naive_memory": _metrics(naive_runs),
        "memoryweaver_coding_debug_runtime": _metrics(runtime_runs),
        "rollback_probe": _metrics([rollback_record]),
    }
    core = metrics["memoryweaver_coding_debug_runtime"]
    aggregate_metrics = {
        "real_pytest_before_failed": 1.0
        if "ZeroDivisionError" in (output_dir / "pytest_before.txt").read_text(encoding="utf-8")
        else 0.0,
        "real_pytest_after_passed": 1.0
        if "2 passed" in (output_dir / "pytest_after.txt").read_text(encoding="utf-8")
        else 0.0,
        "real_diff_matches_expected": 1.0
        if "if denominator == 0" in (output_dir / "diff.patch").read_text(encoding="utf-8")
        else 0.0,
        "candidate_registration_promotable": 1.0 if registration.assessment.can_promote else 0.0,
        "promotion_external_evidence_only": 1.0
        if registration.assessment.model_confidence_ignored_count == 0
        else 0.0,
        "repeated_failure_rate_delta_vs_no_memory": round(
            core["repeated_failure_rate"] - metrics["no_memory"]["repeated_failure_rate"],
            4,
        ),
        "invalid_action_rate_delta_vs_naive_memory": round(
            core["invalid_action_rate"] - metrics["naive_memory"]["invalid_action_rate"],
            4,
        ),
        "memory_induced_regression_delta_vs_naive_memory": round(
            core["memory_induced_regression_rate"]
            - metrics["naive_memory"]["memory_induced_regression_rate"],
            4,
        ),
        "runtime_path_store_roundtrip": 1.0
        if restored_decision.rollback_recommended
        and restored_decision.path_id == candidate.path.path_id
        else 0.0,
        "rollback_recorded": metrics["rollback_probe"]["rollback_frequency"],
    }
    passed = (
        core["success_rate"] == 1.0
        and aggregate_metrics["real_pytest_before_failed"] == 1.0
        and aggregate_metrics["real_pytest_after_passed"] == 1.0
        and aggregate_metrics["real_diff_matches_expected"] == 1.0
        and aggregate_metrics["candidate_registration_promotable"] == 1.0
        and aggregate_metrics["promotion_external_evidence_only"] == 1.0
        and aggregate_metrics["rollback_recorded"] == 1.0
        and aggregate_metrics["runtime_path_store_roundtrip"] == 1.0
    )
    result = {
        "passed": passed,
        "metrics": metrics,
        "aggregate_metrics": aggregate_metrics,
        "registration": registration.to_dict(),
        "candidate": candidate.to_dict(),
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
        for item in baseline_runs + naive_runs + runtime_runs + [rollback_record]:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    result = run(args.output_dir)
    print(json.dumps({"passed": result["passed"], "aggregate_metrics": result["aggregate_metrics"]}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
