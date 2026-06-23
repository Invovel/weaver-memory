# Claim Snapshot

Auto-generated current-stage summary for the main MemoryWeaver claims.

## Canonical Research Question

> Can evidence-gated path promotion reduce repeated agent failures without
> increasing memory-induced error propagation?

## Runtime Path Governance

| signal | current value | source |
| --- | ---: | --- |
| repeated_failure_rate_delta_vs_no_memory | -1.0 | `harness-runtime-core` |
| invalid_action_rate_delta_vs_naive_memory | -1.0 | `harness-runtime-core` |
| task_success_delta_vs_retrieval_memory | 0.5 | `harness-runtime-core` |
| memory_induced_regression_delta_vs_naive_memory | -1.0 | `harness-runtime-core` |
| promotion_precision | 1.0 | `harness-runtime-core` |
| rollback_recovery_success_rate | 1.0 | `harness-runtime-core` |
| runtime_path_store_roundtrip | 1.0 | `harness-runtime-core` |

## Runtime Arms

| arm | success_rate | invalid_action_rate | memory_induced_regression_rate | promotion_precision |
| --- | ---: | ---: | ---: | ---: |
| no_memory | 0.0 | 1.0 | 0.0 | 0.0 |
| naive_memory | 0.0 | 1.0 | 1.0 | 0.0 |
| summary_memory | 0.32 | 0.68 | 0.24 | 0.0 |
| retrieval_memory | 0.5 | 0.5 | 0.2 | 0.0 |
| memoryweaver_harness_runtime | 1.0 | 0.0 | 0.0 | 1.0 |

## Experience Transfer

| signal | current value | source |
| --- | ---: | --- |
| mw_verified_memory.average_steps_to_success | 1 | `experience-transfer-v0.7` |
| no_memory.average_steps_to_success | 2 | `experience-transfer-v0.7` |
| mw_verified_memory.retrieval_hit_before_critical_action_rate | 1.0 | `experience-transfer-v0.7` |
| mw_verified_memory_marker.known_bad_action_attempts | 0 | `experience-transfer-v0.7` |
| marker_only_boundary.marker_direct_action_change_count | 3 | `experience-transfer-v0.7` |
| probe.main_suite.mw_verified_memory.decision_changed_valid_rate | 1.0 | `experience-transfer-v0.7` |
| memory_use.mw_verified_memory.retrieval_miss_count | 0 | `experience-transfer-v0.7` |

## Reliability

| signal | current value | source |
| --- | ---: | --- |
| pass_at_1 | true | `experience-transfer-v0.7` |
| pass_power_3 | true | `experience-transfer-v0.7` |
| run_count | 3 | `experience-transfer-v0.7` |

## Live LLM Bridge

| signal | current value | source |
| --- | ---: | --- |
| live_llm_run_complete | 1.0 | `harness-runtime-live-llm` |
| online_llm_call_count | 3.0 | `harness-runtime-live-llm` |
| live.pass_at_1 | true | `harness-runtime-live-llm` |
| live.pass_power_3 | true | `harness-runtime-live-llm` |
| live.run_count | 3 | `harness-runtime-live-llm` |
| live.online_llm_call_count_mean | 3.0 | `harness-runtime-live-llm` |
| live.memory_induced_regression_rate | 0.0 | `harness-runtime-live-llm` |

## Coding Debug Hard Evidence

| signal | current value | source |
| --- | ---: | --- |
| real_pytest_before_failed | 1.0 | `harness-runtime-coding-debug` |
| real_pytest_after_passed | 1.0 | `harness-runtime-coding-debug` |
| real_diff_matches_expected | 1.0 | `harness-runtime-coding-debug` |
| coding_debug.memory_induced_regression_delta_vs_naive_memory | -1.0 | `harness-runtime-coding-debug` |
| coding_debug.rollback_recorded | 1.0 | `harness-runtime-coding-debug` |

## Layer-3 Path Promotion E2E

| signal | current value | source |
| --- | ---: | --- |
| layer3_e2e.path_regret_delta_vs_verified_memory | -1 | `layer3-path-promotion-e2e` |
| layer3_e2e.path_regret_delta_vs_retrieval_memory | -2 | `layer3-path-promotion-e2e` |
| layer3_e2e.known_bad_action_delta_vs_retrieval_memory | -3 | `layer3-path-promotion-e2e` |
| layer3_e2e.tests_passed | 1.0 | `layer3-path-promotion-e2e` |
| layer3_e2e.file_diff_matches_expected | 1.0 | `layer3-path-promotion-e2e` |
| layer3_e2e.best_path_selection_accuracy | 1.0 | `layer3-path-promotion-e2e` |
| layer3_e2e.latest_path_selection_accuracy | 1.0 | `layer3-path-promotion-e2e` |
| layer3_e2e.stale_path_suppression_rate | 1.0 | `layer3-path-promotion-e2e` |
| layer3_e2e.rollback_success_rate | 1.0 | `layer3-path-promotion-e2e` |
| layer3_e2e.memory_induced_regression_rate | 0.0 | `layer3-path-promotion-e2e` |
| layer3_e2e.pass_power_3 | true | `layer3-path-promotion-e2e` |
| layer3_e2e.tests_passed_pass_power_3 | true | `layer3-path-promotion-e2e` |
| layer3_e2e.diff_matches_expected_pass_power_3 | true | `layer3-path-promotion-e2e` |

## v0.8 Integrated Substrate

| signal | current value | source |
| --- | ---: | --- |
| rag_evidence_node_count | 3 | `v0.8-integration` |
| rag_evidence_hit_count | 3 | `v0.8-integration` |
| citation_coverage | 1.0 | `v0.8-integration` |
| hyde_synthetic_not_promoted | true | `v0.8-integration` |
| verified_memory_write_count | 0 | `v0.8-integration` |
| layer3_mutation_count | 0 | `v0.8-integration` |
| promotion_without_hard_evidence_count | 0 | `v0.8-integration` |
| gbrain_candidate_node_count | 2 | `v0.8-integration` |
| gbrain_candidate_edge_count | 1 | `v0.8-integration` |
| gbrain_authority_granted | false | `v0.8-integration` |
| specialist_run_count | 3 | `v0.8-integration` |
| evidence_packet_ref_count | 3 | `v0.8-integration` |
| checkpoint_resume_success | true | `v0.8-integration` |
| v0.8.pass_power_3 | true | `v0.8-integration` |
| v0.8.run_count | 3 | `v0.8-integration` |

## Claim Summary

- MemoryWeaver currently shows lower repeated failure and lower invalid-action rate than no-memory, naive-memory, summary-memory, and retrieval-memory baselines in the runtime-path fixture.
- The current runtime-path fixture shows zero measured memory-induced regression for `memoryweaver_harness_runtime` while `naive_memory` remains at `1.0`.
- The current validation line shows rollback and rollback recovery as functioning mechanisms rather than decorative hooks.
- The sibling-task experience-transfer line currently supports faster success and valid decision changes under verified-memory use.
- The live LLM bridge now has a real `--llm` pass^3 artifact with non-zero online LLM calls; it is no longer only a mock/smoke artifact.
- The coding-debug line provides hard evidence via real pytest failure, real patch diff, and real pytest pass artifacts.
- The Layer-3 E2E line is the current paper-facing main experiment: it compares no-memory, raw-log RAG, retrieval-memory, verified-memory, and Layer-3 path arms using real pytest/diff evidence and pass^3 reliability.
- The v0.8 integration line now validates RAG evidence, GBrain candidate graph, collaborative specialist routing, and checkpoint/resume as one substrate while preserving zero direct verified-memory or Layer-3 mutation.
- The strongest current evidence is still a controlled deterministic fixture plus sibling-task replay, not a broad open-world benchmark.
