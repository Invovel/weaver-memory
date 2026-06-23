# Layer-3 Path Promotion End-to-End Benchmark

This is the paper-facing main experiment for MemoryWeaver's path-promotion claim.

passed = true
pass^3 = true

## Arms

| arm | tests_passed | diff_matches | best_path_selection | path_regret | known_bad_actions | regression_rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| no_memory | 0.0 | 0.0 | 0.0 | 3 | 3 | 0.0 |
| raw_rag_over_logs | 0.0 | 0.0 | 0.0 | 3 | 3 | 1.0 |
| retrieval_memory | 1.0 | 1.0 | 0.0 | 2 | 3 | 0.0 |
| mw_verified_memory | 1.0 | 1.0 | 0.0 | 1 | 0 | 0.0 |
| mw_layer3_path | 1.0 | 1.0 | 1.0 | 0 | 0 | 0.0 |

## Aggregate

- `path_regret_delta_vs_verified_memory` = -1
- `path_regret_delta_vs_retrieval_memory` = -2
- `known_bad_action_delta_vs_retrieval_memory` = -3
- `tests_passed` = 1.0
- `file_diff_matches_expected` = 1.0
- `memory_induced_regression_rate` = 0.0
- `rollback_success_rate` = 1.0

## Evidence Files

- `arm_metrics.json`
- `task_runs.jsonl`
- `artifact_manifest.json`
- `claim_table.md`
- `reliability.json`
- `evidence/*/pytest_before.txt`
- `evidence/*/pytest_after.txt`
- `evidence/*/diff.patch`
- `layer3_protocol/metrics.json`

The benchmark intentionally keeps RAG/GBrain/specialist substrate out of the critical path.
It tests whether verified experience becomes a better executable Layer-3 path.
