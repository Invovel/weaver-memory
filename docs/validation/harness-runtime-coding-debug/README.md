# Harness Runtime Coding Debug

Real micro-repo coding-debug evidence for runtime path promotion.

passed = true

| arm | success_rate | repeated_failure_rate | invalid_action_rate | memory_induced_regression_rate | rollback_frequency | promotion_precision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| no_memory | 0.0 | 1.0 | 1.0 | 0.0 | 0.0 | 0.0 |
| naive_memory | 0.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 |
| memoryweaver_coding_debug_runtime | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 |
| rollback_probe | 1.0 | 0.0 | 0.0 | 0.0 | 1.0 | 0.0 |

## Aggregate

- `real_pytest_before_failed` = 1.0
- `real_pytest_after_passed` = 1.0
- `real_diff_matches_expected` = 1.0
- `candidate_registration_promotable` = 1.0
- `promotion_external_evidence_only` = 1.0
- `repeated_failure_rate_delta_vs_no_memory` = -1.0
- `invalid_action_rate_delta_vs_naive_memory` = -1.0
- `memory_induced_regression_delta_vs_naive_memory` = -1.0
- `runtime_path_store_roundtrip` = 1.0
- `rollback_recorded` = 1.0

## Hard Evidence Files

- `pytest_before.txt`
- `pytest_after.txt`
- `diff.patch`

Research question: Can evidence-gated path promotion reduce repeated agent failures without increasing memory-induced error propagation?
