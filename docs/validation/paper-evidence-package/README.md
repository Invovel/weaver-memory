# Paper Evidence Package

Auto-generated package for the current paper-facing MemoryWeaver evidence chain.
It separates main experimental claims from supporting substrate checks and external-dataset boundary evidence.

## Readiness

| signal | value |
| --- | ---: |
| passed | true |
| main_experiment_ready | true |
| requirement_count | 18 |
| fail_count | 0 |
| warn_count | 0 |
| main_evidence_count | 4 |

## Section Mapping

| section | evidence level | claim | artifact |
| --- | --- | --- | --- |
| 3.1 Runtime Path Governance | main | Evidence-gated runtime paths reduce repeated failures and invalid actions. | `harness-runtime-core/metrics.json` |
| 3.2 Live LLM Bridge | main | The proposal step can be driven by live LLM calls while Harness remains the authority. | `harness-runtime-live-llm/` |
| 3.3 Coding-Debug Hard Evidence | main | Promotion can be gated by real pytest and real diff evidence. | `harness-runtime-coding-debug/` |
| 3.4 Layer-3 Path Promotion E2E | main | Layer-3 path promotion improves reusable path selection over retrieval-only memory. | `layer3-path-promotion-e2e/` |
| 3.5 v0.8 Substrate Boundary | supporting | RAG, GBrain, specialists, and checkpoints can provide evidence without direct memory authority. | `v0.8-integration/` |
| External Validity Appendix | boundary | External HF datasets are cataloged and boundary-checked; only LME-V2 is currently integrated. | `hf-dataset-candidates-check/` |

## Main Numbers

| line | metric | value |
| --- | --- | ---: |
| Runtime | repeated_failure_rate_delta_vs_no_memory | -1.0 |
| Runtime | invalid_action_rate_delta_vs_naive_memory | -1.0 |
| Runtime | memory_induced_regression_delta_vs_naive_memory | -1.0 |
| Live LLM | online_llm_call_count | 3.0 |
| Live LLM | pass_power_3 | true |
| Coding Debug | real_pytest_before_failed | 1.0 |
| Coding Debug | real_pytest_after_passed | 1.0 |
| Coding Debug | real_diff_matches_expected | 1.0 |
| Layer-3 E2E | path_regret_delta_vs_retrieval_memory | -2 |
| Layer-3 E2E | known_bad_action_delta_vs_retrieval_memory | -3 |
| Layer-3 E2E | best_path_selection_accuracy | 1.0 |
| Layer-3 E2E | pass_power_3 | true |
| v0.8 substrate | promotion_without_hard_evidence_count | 0 |
| HF boundary | boundary_violation_count | 0 |

## Runtime Arms Comparison

| arm | tasks | success | invalid action | memory-induced regression | negative hit | promotion precision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| no_memory | 50 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 |
| naive | 50 | 0.0 | 1.0 | 1.0 | 0.0 | 0.0 |
| summary | 50 | 0.32 | 0.68 | 0.24 | 0.0 | 0.0 |
| retrieval | 50 | 0.5 | 0.5 | 0.2 | 0.5 | 0.0 |
| MemoryWeaver | 50 | 1.0 | 0.0 | 0.0 | 1.0 | 1.0 |

## Non-Claim External Adapter Boundary

| dataset | status | source mode | samples | queries | candidates | boundary guard | effectiveness claim | artifact |
| --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |
| LoCoMo-MC10 | adapter boundary only | hf_first_rows | 3 | 3 | 638 | no promotion, no Layer-3 mutation | no | `locomo-mc10-adapter-check/metrics.json` |
| MemoryAgentBench | adapter boundary only | hf_first_rows | 4 | 103 | 4 | no promotion, no Layer-3 mutation | no | `memoryagentbench-adapter-check/metrics.json` |

## Artifact Mapping

| paper claim | pytest | diff evidence | JSON evidence | rollback / boundary record |
| --- | --- | --- | --- | --- |
| Runtime path governance reduces repeated failures and invalid actions. | `tests/test_harness_runtime_core_benchmark.py` | `n/a` | `harness-runtime-core/metrics.json; harness-runtime-core/raw_results.json` | `harness-runtime-core/metrics.json::aggregate.rollback_recovery_success_rate` |
| Live LLM proposals remain Harness-gated. | `tests/test_harness_runtime_live_llm_benchmark.py` | `n/a` | `harness-runtime-live-llm/metrics.json; harness-runtime-live-llm/reliability.json` | `harness-runtime-live-llm/metrics.json::aggregate.rollback_recorded` |
| Coding-debug promotion uses real pytest and expected diff evidence. | `tests/test_harness_runtime_coding_debug_benchmark.py` | `harness-runtime-coding-debug/diff.patch` | `harness-runtime-coding-debug/metrics.json; harness-runtime-coding-debug/task_runs.jsonl` | `harness-runtime-coding-debug/metrics.json::aggregate.rollback_recorded` |
| Layer-3 path promotion improves reusable path selection over retrieval-only memory. | `tests/test_layer3_path_promotion_e2e.py` | `layer3-path-promotion-e2e/artifact_manifest.json::mw_layer3_path.diff_patch` | `layer3-path-promotion-e2e/metrics.json; layer3-path-promotion-e2e/reliability.json` | `layer3-path-promotion-e2e/metrics.json::aggregate.rollback_success_rate` |
| v0.8 substrate provides evidence without direct memory authority. | `tests/test_v08_integration.py` | `n/a` | `v0.8-integration/metrics.json; v0.8-integration/reliability.json` | `n/a; authority boundary checked by promotion_without_hard_evidence_count=0` |
| External HF datasets are boundary-checked, not claimed as effectiveness evidence. | `tests/test_hf_dataset_candidates_check.py; tests/test_locomo_mc10_adapter_check.py; tests/test_memoryagentbench_adapter_check.py` | `n/a` | `hf-dataset-candidates-check/metrics.json; locomo-mc10-adapter-check/metrics.json; memoryagentbench-adapter-check/metrics.json` | `n/a; boundary checked by memory_promotion_count=0 and layer3_mutation_count=0` |

## Requirement Checks

| status | requirement | detail | artifact |
| --- | --- | --- | --- |
| pass | runtime core reduces repeated failure | delta=-1.0 | `harness-runtime-core/metrics.json` |
| pass | runtime core blocks invalid action propagation | delta=-1.0 | `harness-runtime-core/metrics.json` |
| pass | runtime core avoids memory-induced regression | delta=-1.0 | `harness-runtime-core/metrics.json` |
| pass | live LLM bridge uses real online proposals | calls=3.0 | `harness-runtime-live-llm/metrics.json` |
| pass | live LLM bridge is pass^3 | run_count=3, pass_power_3=True | `harness-runtime-live-llm/reliability.json` |
| pass | coding-debug has real pytest failure and pass | pytest_before_failed=1.0, pytest_after_passed=1.0 | `harness-runtime-coding-debug/metrics.json` |
| pass | coding-debug has real expected diff | diff_matches=1.0 | `harness-runtime-coding-debug/diff.patch` |
| pass | Layer-3 E2E improves path regret | deltas=-1,-2 | `layer3-path-promotion-e2e/metrics.json` |
| pass | Layer-3 E2E keeps hard evidence true | tests=1.0, diff=1.0 | `layer3-path-promotion-e2e/metrics.json` |
| pass | Layer-3 E2E is pass^3 | run_count=3 | `layer3-path-promotion-e2e/reliability.json` |
| pass | Layer-3 E2E evidence files exist | missing=0, file_refs=9 | `layer3-path-promotion-e2e/artifact_manifest.json` |
| pass | v0.8 substrate preserves authority boundaries | synthetic/RAG/GBrain outputs remain non-authoritative | `v0.8-integration/metrics.json` |
| pass | v0.8 substrate is pass^3 | run_count=3 | `v0.8-integration/reliability.json` |
| pass | external HF candidate boundary has no violations | live_checked=9, violations=0 | `hf-dataset-candidates-check/metrics.json` |
| pass | LongMemEval-V2 can build records from local root | root=D:\benchmarks\longmemeval-v2 | `lme-v2-storage-check/metrics.json` |
| pass | LoCoMo-MC10 preview adapter is boundary-safe | sample_count=3, candidates=638 | `locomo-mc10-adapter-check/metrics.json` |
| pass | MemoryAgentBench preview adapter is boundary-safe | splits=4, queries=103 | `memoryagentbench-adapter-check/metrics.json` |
| pass | experience-transfer reliability is pass^3 | run_count=3, pass_power_3=True | `experience-transfer-v0.7/reliability.json` |

## Do Not Overclaim

- Treat the main claims below as scoped to the listed artifacts and fixtures.
- LoCoMo-MC10 and MemoryAgentBench are preview adapters, not task-accuracy benchmarks. Use only as external dataset boundary evidence, not as main effectiveness evidence.
- The current main experiment is a controlled deterministic coding-debug fixture. State scope clearly and avoid broad open-world claims without a larger task suite.

## Generated Files

- `metrics.json`: compact machine-readable metrics for paper tables.
- `evidence_table.json`: section-to-artifact claim mapping.
- `open_issues.json`: limitations and paper-handling notes.
- `README.md`: this human-readable summary.
