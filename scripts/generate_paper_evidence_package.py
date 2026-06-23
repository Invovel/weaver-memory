from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATION_ROOT = REPO_ROOT / "docs" / "validation"
DEFAULT_OUTPUT_DIR = VALIDATION_ROOT / "paper-evidence-package"


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str
    artifact: str


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _check(name: str, condition: bool, detail: str, artifact: str, *, warn: bool = False) -> Check:
    if condition:
        status = "pass"
    elif warn:
        status = "warn"
    else:
        status = "fail"
    return Check(name=name, status=status, detail=detail, artifact=artifact)


def _value(payload: dict[str, Any], *path: str) -> Any:
    current: Any = payload
    for key in path:
        current = current[key]
    return current


def build_package(validation_root: Path = VALIDATION_ROOT) -> dict[str, Any]:
    runtime_dir = validation_root / "harness-runtime-core"
    live_dir = validation_root / "harness-runtime-live-llm"
    coding_dir = validation_root / "harness-runtime-coding-debug"
    layer3_dir = validation_root / "layer3-path-promotion-e2e"
    v08_dir = validation_root / "v0.8-integration"
    transfer_dir = validation_root / "experience-transfer-v0.7"
    hf_dir = validation_root / "hf-dataset-candidates-check"
    lme_storage_dir = validation_root / "lme-v2-storage-check"
    locomo_dir = validation_root / "locomo-mc10-adapter-check"
    mab_dir = validation_root / "memoryagentbench-adapter-check"

    runtime = _read_json(runtime_dir / "metrics.json")
    live = _read_json(live_dir / "metrics.json")
    live_reliability = _read_json(live_dir / "reliability.json")
    coding = _read_json(coding_dir / "metrics.json")
    layer3 = _read_json(layer3_dir / "metrics.json")
    layer3_reliability = _read_json(layer3_dir / "reliability.json")
    layer3_manifest = _read_json(layer3_dir / "artifact_manifest.json")
    v08 = _read_json(v08_dir / "metrics.json")
    v08_reliability = _read_json(v08_dir / "reliability.json")
    transfer_reliability = _read_json(transfer_dir / "reliability.json")
    hf = _read_json(hf_dir / "metrics.json")
    lme_storage = _read_json(lme_storage_dir / "metrics.json")
    locomo = _read_json(locomo_dir / "metrics.json")
    mab = _read_json(mab_dir / "metrics.json")

    runtime_agg = runtime["aggregate"]
    runtime_arms = runtime["arms"]
    live_agg = live["aggregate"]
    coding_agg = coding["aggregate"]
    layer3_agg = layer3["aggregate"]
    layer3_arm = layer3["arms"]["mw_layer3_path"]

    layer3_evidence_files = []
    missing_layer3_evidence = 0
    for item in layer3_manifest:
        if item.get("arm") != "mw_layer3_path":
            continue
        for key in ["pytest_before", "pytest_after", "diff_patch"]:
            artifact = layer3_dir / item[key]
            layer3_evidence_files.append(_rel(artifact, validation_root))
            if not artifact.exists():
                missing_layer3_evidence += 1

    checks = [
        _check(
            "runtime core reduces repeated failure",
            runtime_agg["repeated_failure_rate_delta_vs_no_memory"] < 0,
            f"delta={runtime_agg['repeated_failure_rate_delta_vs_no_memory']}",
            "harness-runtime-core/metrics.json",
        ),
        _check(
            "runtime core blocks invalid action propagation",
            runtime_agg["invalid_action_rate_delta_vs_naive_memory"] < 0,
            f"delta={runtime_agg['invalid_action_rate_delta_vs_naive_memory']}",
            "harness-runtime-core/metrics.json",
        ),
        _check(
            "runtime core avoids memory-induced regression",
            runtime_agg["memory_induced_regression_delta_vs_naive_memory"] < 0,
            f"delta={runtime_agg['memory_induced_regression_delta_vs_naive_memory']}",
            "harness-runtime-core/metrics.json",
        ),
        _check(
            "live LLM bridge uses real online proposals",
            live_agg["live_llm_run_complete"] == 1.0 and live_agg["online_llm_call_count"] > 0,
            f"calls={live_agg['online_llm_call_count']}",
            "harness-runtime-live-llm/metrics.json",
        ),
        _check(
            "live LLM bridge is pass^3",
            live_reliability["run_count"] >= 3 and live_reliability["pass_power_3"] is True,
            f"run_count={live_reliability['run_count']}, pass_power_3={live_reliability['pass_power_3']}",
            "harness-runtime-live-llm/reliability.json",
        ),
        _check(
            "coding-debug has real pytest failure and pass",
            coding_agg["real_pytest_before_failed"] == 1.0 and coding_agg["real_pytest_after_passed"] == 1.0,
            "pytest_before_failed=1.0, pytest_after_passed=1.0",
            "harness-runtime-coding-debug/metrics.json",
        ),
        _check(
            "coding-debug has real expected diff",
            coding_agg["real_diff_matches_expected"] == 1.0
            and (coding_dir / "diff.patch").exists()
            and (coding_dir / "pytest_before.txt").exists()
            and (coding_dir / "pytest_after.txt").exists(),
            f"diff_matches={coding_agg['real_diff_matches_expected']}",
            "harness-runtime-coding-debug/diff.patch",
        ),
        _check(
            "Layer-3 E2E improves path regret",
            layer3_agg["path_regret_delta_vs_verified_memory"] < 0
            and layer3_agg["path_regret_delta_vs_retrieval_memory"] < 0,
            "deltas="
            f"{layer3_agg['path_regret_delta_vs_verified_memory']},"
            f"{layer3_agg['path_regret_delta_vs_retrieval_memory']}",
            "layer3-path-promotion-e2e/metrics.json",
        ),
        _check(
            "Layer-3 E2E keeps hard evidence true",
            layer3_agg["tests_passed"] == 1.0 and layer3_agg["file_diff_matches_expected"] == 1.0,
            f"tests={layer3_agg['tests_passed']}, diff={layer3_agg['file_diff_matches_expected']}",
            "layer3-path-promotion-e2e/metrics.json",
        ),
        _check(
            "Layer-3 E2E is pass^3",
            layer3_reliability["run_count"] >= 3
            and layer3_reliability["pass_power_3"] is True
            and layer3_reliability["tests_passed_pass_power_3"] is True
            and layer3_reliability["diff_matches_expected_pass_power_3"] is True,
            f"run_count={layer3_reliability['run_count']}",
            "layer3-path-promotion-e2e/reliability.json",
        ),
        _check(
            "Layer-3 E2E evidence files exist",
            missing_layer3_evidence == 0 and len(layer3_evidence_files) > 0,
            f"missing={missing_layer3_evidence}, file_refs={len(layer3_evidence_files)}",
            "layer3-path-promotion-e2e/artifact_manifest.json",
        ),
        _check(
            "v0.8 substrate preserves authority boundaries",
            v08["hyde_synthetic_not_promoted"] is True
            and v08["verified_memory_write_count"] == 0
            and v08["layer3_mutation_count"] == 0
            and v08["promotion_without_hard_evidence_count"] == 0
            and v08["gbrain_authority_granted"] is False,
            "synthetic/RAG/GBrain outputs remain non-authoritative",
            "v0.8-integration/metrics.json",
        ),
        _check(
            "v0.8 substrate is pass^3",
            v08_reliability["run_count"] >= 3 and v08_reliability["pass_power_3"] is True,
            f"run_count={v08_reliability['run_count']}",
            "v0.8-integration/reliability.json",
        ),
        _check(
            "external HF candidate boundary has no violations",
            hf["boundary_violation_count"] == 0 and hf["live_error_count"] == 0,
            f"live_checked={hf['live_checked_count']}, violations={hf['boundary_violation_count']}",
            "hf-dataset-candidates-check/metrics.json",
        ),
        _check(
            "LongMemEval-V2 can build records from local root",
            lme_storage["can_build_external_records"] is True,
            f"root={lme_storage['resolved_root']}",
            "lme-v2-storage-check/metrics.json",
        ),
        _check(
            "LoCoMo-MC10 preview adapter is boundary-safe",
            locomo["query_answer_pair_coverage"] == 1.0
            and locomo["policy_gate_leak_count"] == 0
            and locomo["memory_promotion_count"] == 0
            and locomo["layer3_mutation_count"] == 0,
            f"sample_count={locomo['sample_count']}, candidates={locomo['candidate_memory_count']}",
            "locomo-mc10-adapter-check/metrics.json",
        ),
        _check(
            "MemoryAgentBench preview adapter is boundary-safe",
            mab["query_answer_pair_coverage"] == 1.0
            and mab["policy_gate_leak_count"] == 0
            and mab["memory_promotion_count"] == 0
            and mab["layer3_mutation_count"] == 0,
            f"splits={mab['split_count']}, queries={mab['query_count']}",
            "memoryagentbench-adapter-check/metrics.json",
        ),
        _check(
            "experience-transfer reliability is pass^3",
            transfer_reliability["run_count"] >= 3 and transfer_reliability["pass_power_3"] is True,
            f"run_count={transfer_reliability['run_count']}, pass_power_3={transfer_reliability['pass_power_3']}",
            "experience-transfer-v0.7/reliability.json",
            warn=True,
        ),
    ]

    evidence_table = [
        {
            "paper_section": "3.1 Runtime Path Governance",
            "claim": "Evidence-gated runtime paths reduce repeated failures and invalid actions.",
            "primary_metrics": {
                "repeated_failure_rate_delta_vs_no_memory": runtime_agg["repeated_failure_rate_delta_vs_no_memory"],
                "invalid_action_rate_delta_vs_naive_memory": runtime_agg["invalid_action_rate_delta_vs_naive_memory"],
                "promotion_precision": runtime_agg["promotion_precision"],
            },
            "artifact": "harness-runtime-core/metrics.json",
            "evidence_level": "main",
        },
        {
            "paper_section": "3.2 Live LLM Bridge",
            "claim": "The proposal step can be driven by live LLM calls while Harness remains the authority.",
            "primary_metrics": {
                "online_llm_call_count": live_agg["online_llm_call_count"],
                "pass_power_3": live_reliability["pass_power_3"],
                "memory_induced_regression_rate": live_agg["memory_induced_regression_rate"],
            },
            "artifact": "harness-runtime-live-llm/",
            "evidence_level": "main",
        },
        {
            "paper_section": "3.3 Coding-Debug Hard Evidence",
            "claim": "Promotion can be gated by real pytest and real diff evidence.",
            "primary_metrics": {
                "real_pytest_before_failed": coding_agg["real_pytest_before_failed"],
                "real_pytest_after_passed": coding_agg["real_pytest_after_passed"],
                "real_diff_matches_expected": coding_agg["real_diff_matches_expected"],
            },
            "artifact": "harness-runtime-coding-debug/",
            "evidence_level": "main",
        },
        {
            "paper_section": "3.4 Layer-3 Path Promotion E2E",
            "claim": "Layer-3 path promotion improves reusable path selection over retrieval-only memory.",
            "primary_metrics": {
                "path_regret_delta_vs_retrieval_memory": layer3_agg["path_regret_delta_vs_retrieval_memory"],
                "known_bad_action_delta_vs_retrieval_memory": layer3_agg["known_bad_action_delta_vs_retrieval_memory"],
                "best_path_selection_accuracy": layer3_arm["best_path_selection_accuracy"],
                "pass_power_3": layer3_reliability["pass_power_3"],
            },
            "artifact": "layer3-path-promotion-e2e/",
            "evidence_level": "main",
        },
        {
            "paper_section": "3.5 v0.8 Substrate Boundary",
            "claim": "RAG, GBrain, specialists, and checkpoints can provide evidence without direct memory authority.",
            "primary_metrics": {
                "citation_coverage": v08["citation_coverage"],
                "gbrain_authority_granted": v08["gbrain_authority_granted"],
                "promotion_without_hard_evidence_count": v08["promotion_without_hard_evidence_count"],
                "pass_power_3": v08_reliability["pass_power_3"],
            },
            "artifact": "v0.8-integration/",
            "evidence_level": "supporting",
        },
        {
            "paper_section": "External Validity Appendix",
            "claim": "External HF datasets are cataloged and boundary-checked; only LME-V2 is currently integrated.",
            "primary_metrics": {
                "integrated_dataset_count": hf["integrated_dataset_count"],
                "preview_adapter_validated_count": hf["preview_adapter_validated_count"],
                "boundary_violation_count": hf["boundary_violation_count"],
            },
            "artifact": "hf-dataset-candidates-check/",
            "evidence_level": "boundary",
        },
    ]

    runtime_arms_comparison = [
        {
            "paper_label": "no_memory",
            "artifact_arm": "no_memory",
            "task_count": runtime_arms["no_memory"]["task_count"],
            "success_rate": runtime_arms["no_memory"]["success_rate"],
            "invalid_action_rate": runtime_arms["no_memory"]["invalid_action_rate"],
            "memory_induced_regression_rate": runtime_arms["no_memory"]["memory_induced_regression_rate"],
            "negative_memory_hit_rate": runtime_arms["no_memory"]["negative_memory_hit_rate"],
            "promotion_precision": runtime_arms["no_memory"]["promotion_precision"],
        },
        {
            "paper_label": "naive",
            "artifact_arm": "naive_memory",
            "task_count": runtime_arms["naive_memory"]["task_count"],
            "success_rate": runtime_arms["naive_memory"]["success_rate"],
            "invalid_action_rate": runtime_arms["naive_memory"]["invalid_action_rate"],
            "memory_induced_regression_rate": runtime_arms["naive_memory"]["memory_induced_regression_rate"],
            "negative_memory_hit_rate": runtime_arms["naive_memory"]["negative_memory_hit_rate"],
            "promotion_precision": runtime_arms["naive_memory"]["promotion_precision"],
        },
        {
            "paper_label": "summary",
            "artifact_arm": "summary_memory",
            "task_count": runtime_arms["summary_memory"]["task_count"],
            "success_rate": runtime_arms["summary_memory"]["success_rate"],
            "invalid_action_rate": runtime_arms["summary_memory"]["invalid_action_rate"],
            "memory_induced_regression_rate": runtime_arms["summary_memory"]["memory_induced_regression_rate"],
            "negative_memory_hit_rate": runtime_arms["summary_memory"]["negative_memory_hit_rate"],
            "promotion_precision": runtime_arms["summary_memory"]["promotion_precision"],
        },
        {
            "paper_label": "retrieval",
            "artifact_arm": "retrieval_memory",
            "task_count": runtime_arms["retrieval_memory"]["task_count"],
            "success_rate": runtime_arms["retrieval_memory"]["success_rate"],
            "invalid_action_rate": runtime_arms["retrieval_memory"]["invalid_action_rate"],
            "memory_induced_regression_rate": runtime_arms["retrieval_memory"]["memory_induced_regression_rate"],
            "negative_memory_hit_rate": runtime_arms["retrieval_memory"]["negative_memory_hit_rate"],
            "promotion_precision": runtime_arms["retrieval_memory"]["promotion_precision"],
        },
        {
            "paper_label": "MemoryWeaver",
            "artifact_arm": "memoryweaver_harness_runtime",
            "task_count": runtime_arms["memoryweaver_harness_runtime"]["task_count"],
            "success_rate": runtime_arms["memoryweaver_harness_runtime"]["success_rate"],
            "invalid_action_rate": runtime_arms["memoryweaver_harness_runtime"]["invalid_action_rate"],
            "memory_induced_regression_rate": runtime_arms["memoryweaver_harness_runtime"][
                "memory_induced_regression_rate"
            ],
            "negative_memory_hit_rate": runtime_arms["memoryweaver_harness_runtime"]["negative_memory_hit_rate"],
            "promotion_precision": runtime_arms["memoryweaver_harness_runtime"]["promotion_precision"],
        },
    ]

    non_claim_table = [
        {
            "dataset": "LoCoMo-MC10",
            "repo": locomo["source_repo"],
            "status": "adapter boundary only",
            "source_mode": locomo["source_mode"],
            "sample_count": locomo["sample_count"],
            "query_count": locomo["query_count"],
            "candidate_count": locomo["candidate_memory_count"],
            "boundary_guard": "no promotion, no Layer-3 mutation",
            "effectiveness_claim": "no",
            "artifact": "locomo-mc10-adapter-check/metrics.json",
        },
        {
            "dataset": "MemoryAgentBench",
            "repo": mab["source_repo"],
            "status": "adapter boundary only",
            "source_mode": mab["source_mode"],
            "sample_count": mab["sample_count"],
            "query_count": mab["query_count"],
            "candidate_count": mab["candidate_memory_count"],
            "boundary_guard": "no promotion, no Layer-3 mutation",
            "effectiveness_claim": "no",
            "artifact": "memoryagentbench-adapter-check/metrics.json",
        },
    ]

    artifact_mapping = [
        {
            "paper_claim": "Runtime path governance reduces repeated failures and invalid actions.",
            "pytest": "tests/test_harness_runtime_core_benchmark.py",
            "diff": "n/a",
            "json": "harness-runtime-core/metrics.json; harness-runtime-core/raw_results.json",
            "rollback_record": "harness-runtime-core/metrics.json::aggregate.rollback_recovery_success_rate",
        },
        {
            "paper_claim": "Live LLM proposals remain Harness-gated.",
            "pytest": "tests/test_harness_runtime_live_llm_benchmark.py",
            "diff": "n/a",
            "json": "harness-runtime-live-llm/metrics.json; harness-runtime-live-llm/reliability.json",
            "rollback_record": "harness-runtime-live-llm/metrics.json::aggregate.rollback_recorded",
        },
        {
            "paper_claim": "Coding-debug promotion uses real pytest and expected diff evidence.",
            "pytest": "tests/test_harness_runtime_coding_debug_benchmark.py",
            "diff": "harness-runtime-coding-debug/diff.patch",
            "json": "harness-runtime-coding-debug/metrics.json; harness-runtime-coding-debug/task_runs.jsonl",
            "rollback_record": "harness-runtime-coding-debug/metrics.json::aggregate.rollback_recorded",
        },
        {
            "paper_claim": "Layer-3 path promotion improves reusable path selection over retrieval-only memory.",
            "pytest": "tests/test_layer3_path_promotion_e2e.py",
            "diff": "layer3-path-promotion-e2e/artifact_manifest.json::mw_layer3_path.diff_patch",
            "json": "layer3-path-promotion-e2e/metrics.json; layer3-path-promotion-e2e/reliability.json",
            "rollback_record": "layer3-path-promotion-e2e/metrics.json::aggregate.rollback_success_rate",
        },
        {
            "paper_claim": "v0.8 substrate provides evidence without direct memory authority.",
            "pytest": "tests/test_v08_integration.py",
            "diff": "n/a",
            "json": "v0.8-integration/metrics.json; v0.8-integration/reliability.json",
            "rollback_record": "n/a; authority boundary checked by promotion_without_hard_evidence_count=0",
        },
        {
            "paper_claim": "External HF datasets are boundary-checked, not claimed as effectiveness evidence.",
            "pytest": "tests/test_hf_dataset_candidates_check.py; tests/test_locomo_mc10_adapter_check.py; tests/test_memoryagentbench_adapter_check.py",
            "diff": "n/a",
            "json": "hf-dataset-candidates-check/metrics.json; locomo-mc10-adapter-check/metrics.json; memoryagentbench-adapter-check/metrics.json",
            "rollback_record": "n/a; boundary checked by memory_promotion_count=0 and layer3_mutation_count=0",
        },
    ]

    open_issues = [
        {
            "issue": "LoCoMo-MC10 and MemoryAgentBench are preview adapters, not task-accuracy benchmarks.",
            "severity": "medium",
            "paper_handling": "Use only as external dataset boundary evidence, not as main effectiveness evidence.",
            "artifact": "locomo-mc10-adapter-check/, memoryagentbench-adapter-check/",
        },
        {
            "issue": "The current main experiment is a controlled deterministic coding-debug fixture.",
            "severity": "medium",
            "paper_handling": "State scope clearly and avoid broad open-world claims without a larger task suite.",
            "artifact": "layer3-path-promotion-e2e/",
        },
    ]
    if transfer_reliability["run_count"] < 3 or transfer_reliability["pass_power_3"] is not True:
        open_issues.insert(
            0,
            {
                "issue": "Experience-transfer reliability artifact is not a true three-run pass^3 artifact.",
                "severity": "medium",
                "paper_handling": "Do not use as a primary pass^3 claim until regenerated with three independent runs.",
                "artifact": "experience-transfer-v0.7/reliability.json",
            },
        )

    fail_count = sum(1 for item in checks if item.status == "fail")
    warn_count = sum(1 for item in checks if item.status == "warn")

    return {
        "passed": fail_count == 0,
        "summary": {
            "main_experiment_ready": fail_count == 0,
            "requirement_count": len(checks),
            "fail_count": fail_count,
            "warn_count": warn_count,
            "main_evidence_count": sum(1 for item in evidence_table if item["evidence_level"] == "main"),
            "supporting_evidence_count": sum(1 for item in evidence_table if item["evidence_level"] == "supporting"),
            "boundary_evidence_count": sum(1 for item in evidence_table if item["evidence_level"] == "boundary"),
        },
        "checks": [item.__dict__ for item in checks],
        "evidence_table": evidence_table,
        "runtime_arms_comparison": runtime_arms_comparison,
        "non_claim_table": non_claim_table,
        "artifact_mapping": artifact_mapping,
        "metrics": {
            "runtime": runtime_agg,
            "live_llm": {
                **live_agg,
                "run_count": live_reliability["run_count"],
                "pass_power_3": live_reliability["pass_power_3"],
            },
            "coding_debug": coding_agg,
            "layer3_e2e": {
                **layer3_agg,
                "best_path_selection_accuracy": layer3_arm["best_path_selection_accuracy"],
                "latest_path_selection_accuracy": layer3_arm["latest_path_selection_accuracy"],
                "stale_path_suppression_rate": layer3_arm["stale_path_suppression_rate"],
                "run_count": layer3_reliability["run_count"],
                "pass_power_3": layer3_reliability["pass_power_3"],
            },
            "v0_8_substrate": {
                **v08,
                "run_count": v08_reliability["run_count"],
                "pass_power_3": v08_reliability["pass_power_3"],
            },
            "external_datasets": {
                "hf_candidates": hf,
                "lme_v2_storage": lme_storage,
                "locomo_mc10": locomo,
                "memoryagentbench": mab,
            },
        },
        "open_issues": open_issues,
        "artifact_files": {
            "coding_debug": [
                "harness-runtime-coding-debug/pytest_before.txt",
                "harness-runtime-coding-debug/pytest_after.txt",
                "harness-runtime-coding-debug/diff.patch",
            ],
            "layer3_e2e": layer3_evidence_files,
        },
    }


def render_readme(package: dict[str, Any]) -> str:
    checks = package["checks"]
    evidence_table = package["evidence_table"]
    runtime_arms_comparison = package["runtime_arms_comparison"]
    non_claim_table = package["non_claim_table"]
    artifact_mapping = package["artifact_mapping"]
    metrics = package["metrics"]
    summary = package["summary"]

    lines = [
        "# Paper Evidence Package",
        "",
        "Auto-generated package for the current paper-facing MemoryWeaver evidence chain.",
        "It separates main experimental claims from supporting substrate checks and external-dataset boundary evidence.",
        "",
        "## Readiness",
        "",
        "| signal | value |",
        "| --- | ---: |",
        f"| passed | {str(package['passed']).lower()} |",
        f"| main_experiment_ready | {str(summary['main_experiment_ready']).lower()} |",
        f"| requirement_count | {summary['requirement_count']} |",
        f"| fail_count | {summary['fail_count']} |",
        f"| warn_count | {summary['warn_count']} |",
        f"| main_evidence_count | {summary['main_evidence_count']} |",
        "",
        "## Section Mapping",
        "",
        "| section | evidence level | claim | artifact |",
        "| --- | --- | --- | --- |",
    ]
    for item in evidence_table:
        lines.append(
            f"| {item['paper_section']} | {item['evidence_level']} | {item['claim']} | `{item['artifact']}` |"
        )

    lines.extend(
        [
            "",
            "## Main Numbers",
            "",
            "| line | metric | value |",
            "| --- | --- | ---: |",
            f"| Runtime | repeated_failure_rate_delta_vs_no_memory | {metrics['runtime']['repeated_failure_rate_delta_vs_no_memory']} |",
            f"| Runtime | invalid_action_rate_delta_vs_naive_memory | {metrics['runtime']['invalid_action_rate_delta_vs_naive_memory']} |",
            f"| Runtime | memory_induced_regression_delta_vs_naive_memory | {metrics['runtime']['memory_induced_regression_delta_vs_naive_memory']} |",
            f"| Live LLM | online_llm_call_count | {metrics['live_llm']['online_llm_call_count']} |",
            f"| Live LLM | pass_power_3 | {str(metrics['live_llm']['pass_power_3']).lower()} |",
            f"| Coding Debug | real_pytest_before_failed | {metrics['coding_debug']['real_pytest_before_failed']} |",
            f"| Coding Debug | real_pytest_after_passed | {metrics['coding_debug']['real_pytest_after_passed']} |",
            f"| Coding Debug | real_diff_matches_expected | {metrics['coding_debug']['real_diff_matches_expected']} |",
            f"| Layer-3 E2E | path_regret_delta_vs_retrieval_memory | {metrics['layer3_e2e']['path_regret_delta_vs_retrieval_memory']} |",
            f"| Layer-3 E2E | known_bad_action_delta_vs_retrieval_memory | {metrics['layer3_e2e']['known_bad_action_delta_vs_retrieval_memory']} |",
            f"| Layer-3 E2E | best_path_selection_accuracy | {metrics['layer3_e2e']['best_path_selection_accuracy']} |",
            f"| Layer-3 E2E | pass_power_3 | {str(metrics['layer3_e2e']['pass_power_3']).lower()} |",
            f"| v0.8 substrate | promotion_without_hard_evidence_count | {metrics['v0_8_substrate']['promotion_without_hard_evidence_count']} |",
            f"| HF boundary | boundary_violation_count | {metrics['external_datasets']['hf_candidates']['boundary_violation_count']} |",
            "",
            "## Runtime Arms Comparison",
            "",
            "| arm | tasks | success | invalid action | memory-induced regression | negative hit | promotion precision |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for item in runtime_arms_comparison:
        lines.append(
            f"| {item['paper_label']} | {item['task_count']} | {item['success_rate']} | "
            f"{item['invalid_action_rate']} | {item['memory_induced_regression_rate']} | "
            f"{item['negative_memory_hit_rate']} | {item['promotion_precision']} |"
        )

    lines.extend(
        [
            "",
            "## Non-Claim External Adapter Boundary",
            "",
            "| dataset | status | source mode | samples | queries | candidates | boundary guard | effectiveness claim | artifact |",
            "| --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |",
        ]
    )
    for item in non_claim_table:
        lines.append(
            f"| {item['dataset']} | {item['status']} | {item['source_mode']} | {item['sample_count']} | "
            f"{item['query_count']} | {item['candidate_count']} | {item['boundary_guard']} | "
            f"{item['effectiveness_claim']} | `{item['artifact']}` |"
        )

    lines.extend(
        [
            "",
            "## Artifact Mapping",
            "",
            "| paper claim | pytest | diff evidence | JSON evidence | rollback / boundary record |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for item in artifact_mapping:
        lines.append(
            f"| {item['paper_claim']} | `{item['pytest']}` | `{item['diff']}` | "
            f"`{item['json']}` | `{item['rollback_record']}` |"
        )

    lines.extend(
        [
            "",
            "## Requirement Checks",
            "",
            "| status | requirement | detail | artifact |",
            "| --- | --- | --- | --- |",
        ]
    )
    for item in checks:
        lines.append(f"| {item['status']} | {item['name']} | {item['detail']} | `{item['artifact']}` |")

    lines.extend(
        [
            "",
            "## Do Not Overclaim",
            "",
            "- Treat the main claims below as scoped to the listed artifacts and fixtures.",
        ]
    )
    for item in package["open_issues"]:
        lines.append(f"- {item['issue']} {item['paper_handling']}")
    lines.extend(
        [
            "",
            "## Generated Files",
            "",
            "- `metrics.json`: compact machine-readable metrics for paper tables.",
            "- `evidence_table.json`: section-to-artifact claim mapping.",
            "- `open_issues.json`: limitations and paper-handling notes.",
            "- `README.md`: this human-readable summary.",
            "",
        ]
    )
    return "\n".join(lines)


def write_package(output_dir: Path, validation_root: Path = VALIDATION_ROOT) -> dict[str, Any]:
    package = build_package(validation_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metrics.json").write_text(
        json.dumps(
            {
                "passed": package["passed"],
                "summary": package["summary"],
                "metrics": package["metrics"],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "evidence_table.json").write_text(
        json.dumps(package["evidence_table"], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "runtime_arms_comparison.json").write_text(
        json.dumps(package["runtime_arms_comparison"], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "non_claim_table.json").write_text(
        json.dumps(package["non_claim_table"], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "artifact_mapping.json").write_text(
        json.dumps(package["artifact_mapping"], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "checks.json").write_text(
        json.dumps(package["checks"], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "open_issues.json").write_text(
        json.dumps(package["open_issues"], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "artifact_files.json").write_text(
        json.dumps(package["artifact_files"], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "README.md").write_text(render_readme(package), encoding="utf-8")
    return package


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the paper-facing evidence package.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--validation-root", type=Path, default=VALIDATION_ROOT)
    args = parser.parse_args()

    package = write_package(args.output_dir, args.validation_root)
    print(f"Wrote {args.output_dir}")
    print(json.dumps(package["summary"], indent=2, ensure_ascii=False))
    return 0 if package["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
