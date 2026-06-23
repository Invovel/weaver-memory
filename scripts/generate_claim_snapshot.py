from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = REPO_ROOT / "docs"
HARNESS_RUNTIME_CORE_DIR = DOCS_ROOT / "validation" / "harness-runtime-core"
EXPERIENCE_TRANSFER_DIR = DOCS_ROOT / "validation" / "experience-transfer-v0.7"
HARNESS_RUNTIME_LIVE_LLM_DIR = DOCS_ROOT / "validation" / "harness-runtime-live-llm"
HARNESS_RUNTIME_CODING_DEBUG_DIR = DOCS_ROOT / "validation" / "harness-runtime-coding-debug"
LAYER3_E2E_DIR = DOCS_ROOT / "validation" / "layer3-path-promotion-e2e"
V08_INTEGRATION_DIR = DOCS_ROOT / "validation" / "v0.8-integration"
OUTPUT_PATH = DOCS_ROOT / "validation" / "claim-snapshot.md"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_snapshot() -> str:
    runtime_metrics = _read_json(HARNESS_RUNTIME_CORE_DIR / "metrics.json")
    runtime_raw = _read_json(HARNESS_RUNTIME_CORE_DIR / "raw_results.json")
    transfer_raw = _read_json(EXPERIENCE_TRANSFER_DIR / "raw_results.json")
    transfer_reliability = _read_json(EXPERIENCE_TRANSFER_DIR / "reliability.json")
    live_metrics = _read_json(HARNESS_RUNTIME_LIVE_LLM_DIR / "metrics.json")
    live_reliability = _read_json(HARNESS_RUNTIME_LIVE_LLM_DIR / "reliability.json")
    coding_metrics = _read_json(HARNESS_RUNTIME_CODING_DEBUG_DIR / "metrics.json")
    layer3_e2e_metrics = _read_json(LAYER3_E2E_DIR / "metrics.json")
    layer3_e2e_reliability = _read_json(LAYER3_E2E_DIR / "reliability.json")
    v08_metrics = _read_json(V08_INTEGRATION_DIR / "metrics.json")
    v08_reliability = _read_json(V08_INTEGRATION_DIR / "reliability.json")

    runtime_arms = runtime_metrics["arms"]
    runtime_aggregate = runtime_metrics["aggregate"]
    live_aggregate = live_metrics["aggregate"]
    live_reliability_aggregate = live_reliability["aggregate"]
    coding_aggregate = coding_metrics["aggregate"]
    layer3_e2e_aggregate = layer3_e2e_metrics["aggregate"]
    layer3_e2e_layer3 = layer3_e2e_metrics["arms"]["mw_layer3_path"]
    transfer_metrics = transfer_raw["arm_metrics"]
    transfer_marker = transfer_raw["marker_only_arm_metrics"]
    transfer_probe = transfer_raw["probe_metrics"]
    transfer_memory_use = transfer_raw["memory_use_summary"]

    lines = [
        "# Claim Snapshot",
        "",
        "Auto-generated current-stage summary for the main MemoryWeaver claims.",
        "",
        "## Canonical Research Question",
        "",
        "> Can evidence-gated path promotion reduce repeated agent failures without",
        "> increasing memory-induced error propagation?",
        "",
        "## Runtime Path Governance",
        "",
        "| signal | current value | source |",
        "| --- | ---: | --- |",
        f"| repeated_failure_rate_delta_vs_no_memory | {runtime_aggregate['repeated_failure_rate_delta_vs_no_memory']} | `harness-runtime-core` |",
        f"| invalid_action_rate_delta_vs_naive_memory | {runtime_aggregate['invalid_action_rate_delta_vs_naive_memory']} | `harness-runtime-core` |",
        f"| task_success_delta_vs_retrieval_memory | {runtime_aggregate['task_success_delta_vs_retrieval_memory']} | `harness-runtime-core` |",
        f"| memory_induced_regression_delta_vs_naive_memory | {runtime_aggregate['memory_induced_regression_delta_vs_naive_memory']} | `harness-runtime-core` |",
        f"| promotion_precision | {runtime_aggregate['promotion_precision']} | `harness-runtime-core` |",
        f"| rollback_recovery_success_rate | {runtime_aggregate['rollback_recovery_success_rate']} | `harness-runtime-core` |",
        f"| runtime_path_store_roundtrip | {runtime_aggregate['runtime_path_store_roundtrip']} | `harness-runtime-core` |",
        "",
        "## Runtime Arms",
        "",
        "| arm | success_rate | invalid_action_rate | memory_induced_regression_rate | promotion_precision |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]

    for arm in [
        "no_memory",
        "naive_memory",
        "summary_memory",
        "retrieval_memory",
        "memoryweaver_harness_runtime",
    ]:
        values = runtime_arms[arm]
        lines.append(
            f"| {arm} | {values['success_rate']} | {values['invalid_action_rate']} | "
            f"{values['memory_induced_regression_rate']} | {values['promotion_precision']} |"
        )

    lines.extend(
        [
            "",
            "## Experience Transfer",
            "",
            "| signal | current value | source |",
            "| --- | ---: | --- |",
            f"| mw_verified_memory.average_steps_to_success | {transfer_metrics['mw_verified_memory']['average_steps_to_success']} | `experience-transfer-v0.7` |",
            f"| no_memory.average_steps_to_success | {transfer_metrics['no_memory']['average_steps_to_success']} | `experience-transfer-v0.7` |",
            f"| mw_verified_memory.retrieval_hit_before_critical_action_rate | {transfer_metrics['mw_verified_memory']['retrieval_hit_before_critical_action_rate']} | `experience-transfer-v0.7` |",
            f"| mw_verified_memory_marker.known_bad_action_attempts | {transfer_metrics['mw_verified_memory_marker']['known_bad_action_attempts']} | `experience-transfer-v0.7` |",
            f"| marker_only_boundary.marker_direct_action_change_count | {transfer_marker['mw_verified_memory_marker']['marker_direct_action_change_count']} | `experience-transfer-v0.7` |",
            f"| probe.main_suite.mw_verified_memory.decision_changed_valid_rate | {transfer_probe['main_suite']['mw_verified_memory']['decision_changed_valid_rate']} | `experience-transfer-v0.7` |",
            f"| memory_use.mw_verified_memory.retrieval_miss_count | {transfer_memory_use['mw_verified_memory']['retrieval_miss_count']} | `experience-transfer-v0.7` |",
            "",
            "## Reliability",
            "",
            "| signal | current value | source |",
            "| --- | ---: | --- |",
            f"| pass_at_1 | {str(transfer_reliability['pass_at_1']).lower()} | `experience-transfer-v0.7` |",
            f"| pass_power_3 | {str(transfer_reliability['pass_power_3']).lower()} | `experience-transfer-v0.7` |",
            f"| run_count | {transfer_reliability['run_count']} | `experience-transfer-v0.7` |",
            "",
            "## Live LLM Bridge",
            "",
            "| signal | current value | source |",
            "| --- | ---: | --- |",
            f"| live_llm_run_complete | {live_aggregate['live_llm_run_complete']} | `harness-runtime-live-llm` |",
            f"| online_llm_call_count | {live_aggregate['online_llm_call_count']} | `harness-runtime-live-llm` |",
            f"| live.pass_at_1 | {str(live_reliability['pass_at_1']).lower()} | `harness-runtime-live-llm` |",
            f"| live.pass_power_3 | {str(live_reliability['pass_power_3']).lower()} | `harness-runtime-live-llm` |",
            f"| live.run_count | {live_reliability['run_count']} | `harness-runtime-live-llm` |",
            f"| live.online_llm_call_count_mean | {live_reliability_aggregate['online_llm_call_count_mean']} | `harness-runtime-live-llm` |",
            f"| live.memory_induced_regression_rate | {live_aggregate['memory_induced_regression_rate']} | `harness-runtime-live-llm` |",
            "",
            "## Coding Debug Hard Evidence",
            "",
            "| signal | current value | source |",
            "| --- | ---: | --- |",
            f"| real_pytest_before_failed | {coding_aggregate['real_pytest_before_failed']} | `harness-runtime-coding-debug` |",
            f"| real_pytest_after_passed | {coding_aggregate['real_pytest_after_passed']} | `harness-runtime-coding-debug` |",
            f"| real_diff_matches_expected | {coding_aggregate['real_diff_matches_expected']} | `harness-runtime-coding-debug` |",
            f"| coding_debug.memory_induced_regression_delta_vs_naive_memory | {coding_aggregate['memory_induced_regression_delta_vs_naive_memory']} | `harness-runtime-coding-debug` |",
            f"| coding_debug.rollback_recorded | {coding_aggregate['rollback_recorded']} | `harness-runtime-coding-debug` |",
            "",
            "## Layer-3 Path Promotion E2E",
            "",
            "| signal | current value | source |",
            "| --- | ---: | --- |",
            f"| layer3_e2e.path_regret_delta_vs_verified_memory | {layer3_e2e_aggregate['path_regret_delta_vs_verified_memory']} | `layer3-path-promotion-e2e` |",
            f"| layer3_e2e.path_regret_delta_vs_retrieval_memory | {layer3_e2e_aggregate['path_regret_delta_vs_retrieval_memory']} | `layer3-path-promotion-e2e` |",
            f"| layer3_e2e.known_bad_action_delta_vs_retrieval_memory | {layer3_e2e_aggregate['known_bad_action_delta_vs_retrieval_memory']} | `layer3-path-promotion-e2e` |",
            f"| layer3_e2e.tests_passed | {layer3_e2e_aggregate['tests_passed']} | `layer3-path-promotion-e2e` |",
            f"| layer3_e2e.file_diff_matches_expected | {layer3_e2e_aggregate['file_diff_matches_expected']} | `layer3-path-promotion-e2e` |",
            f"| layer3_e2e.best_path_selection_accuracy | {layer3_e2e_layer3['best_path_selection_accuracy']} | `layer3-path-promotion-e2e` |",
            f"| layer3_e2e.latest_path_selection_accuracy | {layer3_e2e_layer3['latest_path_selection_accuracy']} | `layer3-path-promotion-e2e` |",
            f"| layer3_e2e.stale_path_suppression_rate | {layer3_e2e_layer3['stale_path_suppression_rate']} | `layer3-path-promotion-e2e` |",
            f"| layer3_e2e.rollback_success_rate | {layer3_e2e_layer3['rollback_success_rate']} | `layer3-path-promotion-e2e` |",
            f"| layer3_e2e.memory_induced_regression_rate | {layer3_e2e_aggregate['memory_induced_regression_rate']} | `layer3-path-promotion-e2e` |",
            f"| layer3_e2e.pass_power_3 | {str(layer3_e2e_reliability['pass_power_3']).lower()} | `layer3-path-promotion-e2e` |",
            f"| layer3_e2e.tests_passed_pass_power_3 | {str(layer3_e2e_reliability['tests_passed_pass_power_3']).lower()} | `layer3-path-promotion-e2e` |",
            f"| layer3_e2e.diff_matches_expected_pass_power_3 | {str(layer3_e2e_reliability['diff_matches_expected_pass_power_3']).lower()} | `layer3-path-promotion-e2e` |",
            "",
            "## v0.8 Integrated Substrate",
            "",
            "| signal | current value | source |",
            "| --- | ---: | --- |",
            f"| rag_evidence_node_count | {v08_metrics['rag_evidence_node_count']} | `v0.8-integration` |",
            f"| rag_evidence_hit_count | {v08_metrics['rag_evidence_hit_count']} | `v0.8-integration` |",
            f"| citation_coverage | {v08_metrics['citation_coverage']} | `v0.8-integration` |",
            f"| hyde_synthetic_not_promoted | {str(v08_metrics['hyde_synthetic_not_promoted']).lower()} | `v0.8-integration` |",
            f"| verified_memory_write_count | {v08_metrics['verified_memory_write_count']} | `v0.8-integration` |",
            f"| layer3_mutation_count | {v08_metrics['layer3_mutation_count']} | `v0.8-integration` |",
            f"| promotion_without_hard_evidence_count | {v08_metrics['promotion_without_hard_evidence_count']} | `v0.8-integration` |",
            f"| gbrain_candidate_node_count | {v08_metrics['gbrain_candidate_node_count']} | `v0.8-integration` |",
            f"| gbrain_candidate_edge_count | {v08_metrics['gbrain_candidate_edge_count']} | `v0.8-integration` |",
            f"| gbrain_authority_granted | {str(v08_metrics['gbrain_authority_granted']).lower()} | `v0.8-integration` |",
            f"| specialist_run_count | {v08_metrics['specialist_run_count']} | `v0.8-integration` |",
            f"| evidence_packet_ref_count | {v08_metrics['evidence_packet_ref_count']} | `v0.8-integration` |",
            f"| checkpoint_resume_success | {str(v08_metrics['checkpoint_resume_success']).lower()} | `v0.8-integration` |",
            f"| v0.8.pass_power_3 | {str(v08_reliability['pass_power_3']).lower()} | `v0.8-integration` |",
            f"| v0.8.run_count | {v08_reliability['run_count']} | `v0.8-integration` |",
            "",
            "## Claim Summary",
            "",
            "- MemoryWeaver currently shows lower repeated failure and lower invalid-action rate than no-memory, naive-memory, summary-memory, and retrieval-memory baselines in the runtime-path fixture.",
            "- The current runtime-path fixture shows zero measured memory-induced regression for `memoryweaver_harness_runtime` while `naive_memory` remains at `1.0`.",
            "- The current validation line shows rollback and rollback recovery as functioning mechanisms rather than decorative hooks.",
            "- The sibling-task experience-transfer line currently supports faster success and valid decision changes under verified-memory use.",
            "- The live LLM bridge now has a real `--llm` pass^3 artifact with non-zero online LLM calls; it is no longer only a mock/smoke artifact.",
            "- The coding-debug line provides hard evidence via real pytest failure, real patch diff, and real pytest pass artifacts.",
            "- The Layer-3 E2E line is the current paper-facing main experiment: it compares no-memory, raw-log RAG, retrieval-memory, verified-memory, and Layer-3 path arms using real pytest/diff evidence and pass^3 reliability.",
            "- The v0.8 integration line now validates RAG evidence, GBrain candidate graph, collaborative specialist routing, and checkpoint/resume as one substrate while preserving zero direct verified-memory or Layer-3 mutation.",
            "- The strongest current evidence is still a controlled deterministic fixture plus sibling-task replay, not a broad open-world benchmark.",
            "",
        ]
    )

    return "\n".join(lines)


def main() -> int:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(build_snapshot(), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
