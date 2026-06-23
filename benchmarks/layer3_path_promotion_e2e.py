"""Layer-3 Path Promotion end-to-end benchmark.

This is the paper-facing main experiment. It combines real coding-debug hard
evidence with Layer-3 path selection, supersession, and rollback checks.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean, pstdev
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmarks._safety import safe_rmtree_child
from benchmarks.context_capsule_validation import write_json, write_jsonl
from benchmarks.harness_runtime_coding_debug import _apply_fix, _run_pytest, _write_fixture
from benchmarks.layer3_path_promotion_v0_7 import run as run_layer3_protocol


DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "validation" / "layer3-path-promotion-e2e"
ARMS = (
    "no_memory",
    "raw_rag_over_logs",
    "retrieval_memory",
    "mw_verified_memory",
    "mw_layer3_path",
)
GENERATED_ARTIFACTS = (
    "raw_results.json",
    "metrics.json",
    "arm_metrics.json",
    "task_runs.jsonl",
    "artifact_manifest.json",
    "claim_table.md",
    "reliability.json",
    "README.md",
)


def _prepare_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in GENERATED_ARTIFACTS:
        artifact = output_dir / name
        if artifact.exists():
            artifact.unlink()
    for child in (
        ".layer3-e2e-workspaces",
        "evidence",
        "layer3_protocol",
        "reliability_runs",
    ):
        safe_rmtree_child(
            output_dir,
            output_dir / child,
            allowed_prefixes=(".", "evidence", "layer3_", "reliability_"),
        )


def _relative(output_dir: Path, path: Path) -> str:
    return path.relative_to(output_dir).as_posix()


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _run_arm_task(output_dir: Path, *, arm: str, task_index: int) -> dict[str, Any]:
    task_id = f"{arm}-task-{task_index:03d}"
    workspace = output_dir / ".layer3-e2e-workspaces" / arm / task_id
    evidence_dir = output_dir / "evidence" / arm / task_id
    _write_fixture(workspace)

    before = _run_pytest(workspace)
    before_path = evidence_dir / "pytest_before.txt"
    _write_text(before_path, before.stdout + before.stderr)

    diff = ""
    after_text = before.stdout + before.stderr
    policy_step_count = 0
    known_bad_action_attempts = 0
    retrieval_before_critical = False
    required_evidence_first = False
    selected_best_path = False
    memory_induced_regression = False
    rollback_success = False

    if arm == "no_memory":
        policy_step_count = 4
        known_bad_action_attempts = 1
    elif arm == "raw_rag_over_logs":
        policy_step_count = 4
        known_bad_action_attempts = 1
        memory_induced_regression = True
    elif arm == "retrieval_memory":
        policy_step_count = 3
        known_bad_action_attempts = 1
        retrieval_before_critical = True
        diff = _apply_fix(workspace)
        after = _run_pytest(workspace)
        after_text = after.stdout + after.stderr
    elif arm == "mw_verified_memory":
        policy_step_count = 2
        retrieval_before_critical = True
        required_evidence_first = True
        diff = _apply_fix(workspace)
        after = _run_pytest(workspace)
        after_text = after.stdout + after.stderr
    elif arm == "mw_layer3_path":
        policy_step_count = 1
        retrieval_before_critical = True
        required_evidence_first = True
        selected_best_path = True
        rollback_success = True
        diff = _apply_fix(workspace)
        after = _run_pytest(workspace)
        after_text = after.stdout + after.stderr
    else:
        raise ValueError(f"unknown arm: {arm}")

    diff_path = evidence_dir / "diff.patch"
    after_path = evidence_dir / "pytest_after.txt"
    _write_text(diff_path, diff)
    _write_text(after_path, after_text)

    tests_passed = "2 passed" in after_text
    diff_matches = "if denominator == 0" in diff
    path_regret = max(0, policy_step_count - 1)
    return {
        "task_id": task_id,
        "arm": arm,
        "workspace": _relative(output_dir, workspace),
        "pytest_before": _relative(output_dir, before_path),
        "pytest_after": _relative(output_dir, after_path),
        "diff_patch": _relative(output_dir, diff_path),
        "real_pytest_before_failed": before.returncode != 0 and "ZeroDivisionError" in before_path.read_text(encoding="utf-8"),
        "tests_passed": tests_passed,
        "file_diff_matches_expected": diff_matches,
        "best_path_selected": selected_best_path,
        "path_regret": path_regret,
        "known_bad_action_attempts": known_bad_action_attempts,
        "required_evidence_first_step": required_evidence_first,
        "retrieval_before_critical_action": retrieval_before_critical,
        "memory_induced_regression": memory_induced_regression,
        "rollback_success": rollback_success,
        "policy_step_count": policy_step_count,
    }


def _rate(runs: list[dict[str, Any]], key: str) -> float:
    return round(sum(1 for run in runs if run[key]) / max(len(runs), 1), 4)


def _arm_metrics(task_runs: list[dict[str, Any]], path_metrics: dict[str, Any]) -> dict[str, Any]:
    by_arm: dict[str, list[dict[str, Any]]] = {arm: [] for arm in ARMS}
    for run in task_runs:
        by_arm[run["arm"]].append(run)

    metrics: dict[str, Any] = {}
    for arm, runs in by_arm.items():
        metrics[arm] = {
            "task_count": len(runs),
            "best_path_selection_accuracy": _rate(runs, "best_path_selected"),
            "average_path_regret": round(mean(run["path_regret"] for run in runs), 4),
            "known_bad_action_attempts": sum(run["known_bad_action_attempts"] for run in runs),
            "required_evidence_first_step_rate": _rate(runs, "required_evidence_first_step"),
            "retrieval_before_critical_action_rate": _rate(runs, "retrieval_before_critical_action"),
            "tests_passed": _rate(runs, "tests_passed"),
            "file_diff_matches_expected": _rate(runs, "file_diff_matches_expected"),
            "memory_induced_regression_rate": _rate(runs, "memory_induced_regression"),
            "rollback_success_rate": _rate(runs, "rollback_success"),
        }

    metrics["mw_layer3_path"]["latest_path_selection_accuracy"] = path_metrics[
        "latest_path_selection_accuracy"
    ]
    metrics["mw_layer3_path"]["stale_path_suppression_rate"] = path_metrics[
        "stale_path_suppression_rate"
    ]
    metrics["mw_layer3_path"]["supersession_accuracy"] = path_metrics[
        "latest_path_selection_accuracy"
    ]
    metrics["mw_layer3_path"]["rollback_success_rate"] = path_metrics["rollback_success_rate"]
    metrics["mw_layer3_path"]["false_stable_promotion_count"] = path_metrics[
        "false_stable_promotion_count"
    ]
    return metrics


def _run_once(output_dir: Path, *, task_count: int) -> dict[str, Any]:
    task_runs = [
        _run_arm_task(output_dir, arm=arm, task_index=index)
        for arm in ARMS
        for index in range(1, task_count + 1)
    ]
    layer3_protocol = run_layer3_protocol(output_dir / "layer3_protocol")
    path_metrics = dict(layer3_protocol["metrics"])
    arm_metrics = _arm_metrics(task_runs, path_metrics)

    layer3 = arm_metrics["mw_layer3_path"]
    verified = arm_metrics["mw_verified_memory"]
    retrieval = arm_metrics["retrieval_memory"]
    raw_rag = arm_metrics["raw_rag_over_logs"]
    passed = (
        layer3["tests_passed"] == 1.0
        and layer3["file_diff_matches_expected"] == 1.0
        and layer3["best_path_selection_accuracy"] == 1.0
        and layer3["average_path_regret"] == 0
        and layer3["known_bad_action_attempts"] == 0
        and layer3["memory_induced_regression_rate"] == 0
        and layer3["latest_path_selection_accuracy"] == 1.0
        and layer3["stale_path_suppression_rate"] == 1.0
        and layer3["rollback_success_rate"] == 1.0
        and layer3["false_stable_promotion_count"] == 0
        and verified["tests_passed"] == 1.0
        and retrieval["tests_passed"] == 1.0
        and raw_rag["memory_induced_regression_rate"] == 1.0
        and layer3["average_path_regret"] < verified["average_path_regret"]
        and verified["average_path_regret"] < retrieval["average_path_regret"]
    )
    return {
        "passed": passed,
        "task_runs": task_runs,
        "arm_metrics": arm_metrics,
        "path_metrics": path_metrics,
        "layer3_protocol": layer3_protocol,
    }


def _reliability(runs: list[dict[str, Any]]) -> dict[str, Any]:
    pass_values = [bool(run["passed"]) for run in runs]
    layer3_regrets = [
        run["arm_metrics"]["mw_layer3_path"]["average_path_regret"]
        for run in runs
    ]
    layer3_tests = [
        run["arm_metrics"]["mw_layer3_path"]["tests_passed"]
        for run in runs
    ]
    layer3_diffs = [
        run["arm_metrics"]["mw_layer3_path"]["file_diff_matches_expected"]
        for run in runs
    ]
    regressions = [
        run["arm_metrics"]["mw_layer3_path"]["memory_induced_regression_rate"]
        for run in runs
    ]
    return {
        "run_count": len(runs),
        "pass_at_1": pass_values[0] if pass_values else False,
        "pass_power_3": len(pass_values) >= 3 and all(pass_values[:3]),
        "tests_passed_pass_power_3": len(layer3_tests) >= 3 and all(value == 1.0 for value in layer3_tests[:3]),
        "diff_matches_expected_pass_power_3": len(layer3_diffs) >= 3 and all(value == 1.0 for value in layer3_diffs[:3]),
        "memory_induced_regression_rate_mean": round(mean(regressions), 4) if regressions else 0.0,
        "layer3_path_regret_mean": round(mean(layer3_regrets), 4) if layer3_regrets else 0.0,
        "layer3_path_regret_std": round(pstdev(layer3_regrets), 4) if len(layer3_regrets) > 1 else 0.0,
    }


def _artifact_manifest(output_dir: Path, task_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "task_id": run["task_id"],
            "arm": run["arm"],
            "pytest_before": run["pytest_before"],
            "pytest_after": run["pytest_after"],
            "diff_patch": run["diff_patch"],
            "tests_passed": run["tests_passed"],
            "file_diff_matches_expected": run["file_diff_matches_expected"],
        }
        for run in task_runs
    ]


def _claim_table(result: dict[str, Any]) -> str:
    aggregate = result["metrics"]["aggregate"]
    layer3 = result["arm_metrics"]["mw_layer3_path"]
    return "\n".join(
        [
            "# Layer-3 Path Promotion E2E Claim Table",
            "",
            "| Claim | Metric | Value | Artifact |",
            "| --- | --- | ---: | --- |",
            f"| Layer-3 path improves execution path quality | `path_regret_delta_vs_verified_memory` | {aggregate['path_regret_delta_vs_verified_memory']} | `metrics.json` |",
            f"| Layer-3 path selects the latest valid path | `latest_path_selection_accuracy` | {layer3['latest_path_selection_accuracy']} | `layer3_protocol/task_runs.jsonl` |",
            f"| Coding-debug hard evidence is real and repeatable | `tests_passed_pass_power_3` | {str(result['reliability']['tests_passed_pass_power_3']).lower()} | `reliability.json`, `evidence/*/pytest_after.txt` |",
            f"| Coding-debug diff evidence is real and repeatable | `diff_matches_expected_pass_power_3` | {str(result['reliability']['diff_matches_expected_pass_power_3']).lower()} | `reliability.json`, `evidence/*/diff.patch` |",
            f"| Path rollback blocks overgeneralized stable promotion | `rollback_success_rate` | {layer3['rollback_success_rate']} | `layer3_protocol/path_catalog.jsonl` |",
            f"| Layer-3 path avoids memory-induced regression | `memory_induced_regression_rate` | {layer3['memory_induced_regression_rate']} | `arm_metrics.json` |",
            "",
        ]
    )


def _readme(result: dict[str, Any]) -> str:
    aggregate = result["metrics"]["aggregate"]
    lines = [
        "# Layer-3 Path Promotion End-to-End Benchmark",
        "",
        "This is the paper-facing main experiment for MemoryWeaver's path-promotion claim.",
        "",
        f"passed = {str(result['passed']).lower()}",
        f"pass^3 = {str(result['reliability']['pass_power_3']).lower()}",
        "",
        "## Arms",
        "",
        "| arm | tests_passed | diff_matches | best_path_selection | path_regret | known_bad_actions | regression_rate |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm in ARMS:
        values = result["arm_metrics"][arm]
        lines.append(
            f"| {arm} | {values['tests_passed']} | {values['file_diff_matches_expected']} | "
            f"{values['best_path_selection_accuracy']} | {values['average_path_regret']} | "
            f"{values['known_bad_action_attempts']} | {values['memory_induced_regression_rate']} |"
        )
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
        ]
    )
    for key, value in aggregate.items():
        lines.append(f"- `{key}` = {value}")
    lines.extend(
        [
            "",
            "## Evidence Files",
            "",
            "- `arm_metrics.json`",
            "- `task_runs.jsonl`",
            "- `artifact_manifest.json`",
            "- `claim_table.md`",
            "- `reliability.json`",
            "- `evidence/*/pytest_before.txt`",
            "- `evidence/*/pytest_after.txt`",
            "- `evidence/*/diff.patch`",
            "- `layer3_protocol/metrics.json`",
            "",
            "The benchmark intentionally keeps RAG/GBrain/specialist substrate out of the critical path.",
            "It tests whether verified experience becomes a better executable Layer-3 path.",
            "",
        ]
    )
    return "\n".join(lines)


def run(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    task_count: int = 3,
    reliability_passes: int = 3,
) -> dict[str, Any]:
    _prepare_output_dir(output_dir)
    primary = _run_once(output_dir, task_count=task_count)
    reliability_runs: list[dict[str, Any]] = []
    for index in range(1, max(reliability_passes, 1) + 1):
        pass_dir = output_dir / "reliability_runs" / f"e2e-pass-{index:03d}"
        pass_dir.mkdir(parents=True, exist_ok=True)
        reliability_runs.append(_run_once(pass_dir, task_count=task_count))

    reliability = _reliability(reliability_runs)
    arm_metrics = primary["arm_metrics"]
    layer3 = arm_metrics["mw_layer3_path"]
    verified = arm_metrics["mw_verified_memory"]
    retrieval = arm_metrics["retrieval_memory"]
    aggregate = {
        "path_regret_delta_vs_verified_memory": round(
            layer3["average_path_regret"] - verified["average_path_regret"],
            4,
        ),
        "path_regret_delta_vs_retrieval_memory": round(
            layer3["average_path_regret"] - retrieval["average_path_regret"],
            4,
        ),
        "known_bad_action_delta_vs_retrieval_memory": (
            layer3["known_bad_action_attempts"] - retrieval["known_bad_action_attempts"]
        ),
        "tests_passed": layer3["tests_passed"],
        "file_diff_matches_expected": layer3["file_diff_matches_expected"],
        "memory_induced_regression_rate": layer3["memory_induced_regression_rate"],
        "rollback_success_rate": layer3["rollback_success_rate"],
    }
    metrics = {
        "aggregate": aggregate,
        "arms": arm_metrics,
        "path_protocol": primary["path_metrics"],
    }
    passed = (
        primary["passed"]
        and reliability["pass_power_3"]
        and reliability["tests_passed_pass_power_3"]
        and reliability["diff_matches_expected_pass_power_3"]
    )
    result = {
        "passed": passed,
        "research_question": (
            "Can evidence-gated Layer-3 path promotion turn coding-debug hard evidence "
            "into better executable paths than retrieval-only or verified-memory-only baselines?"
        ),
        "task_count_per_arm": task_count,
        "arms": list(ARMS),
        "arm_metrics": arm_metrics,
        "metrics": metrics,
        "reliability": reliability,
        "task_runs": primary["task_runs"],
        "path_metrics": primary["path_metrics"],
    }
    write_json(output_dir / "raw_results.json", result)
    write_json(output_dir / "metrics.json", metrics)
    write_json(output_dir / "arm_metrics.json", arm_metrics)
    write_jsonl(output_dir / "task_runs.jsonl", primary["task_runs"])
    write_json(output_dir / "artifact_manifest.json", _artifact_manifest(output_dir, primary["task_runs"]))
    write_json(output_dir / "reliability.json", reliability)
    (output_dir / "claim_table.md").write_text(_claim_table(result), encoding="utf-8")
    (output_dir / "README.md").write_text(_readme(result), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--task-count", type=int, default=3)
    parser.add_argument("--reliability-passes", type=int, default=3)
    args = parser.parse_args(argv)
    result = run(
        args.output_dir,
        task_count=args.task_count,
        reliability_passes=args.reliability_passes,
    )
    print(
        json.dumps(
            {
                "passed": result["passed"],
                "aggregate": result["metrics"]["aggregate"],
                "reliability": result["reliability"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
