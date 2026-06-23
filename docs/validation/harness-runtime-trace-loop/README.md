# Harness Runtime Trace Loop

Minimal same-family closed loop: seed trace -> candidate path -> runtime reuse -> challenge -> rollback recovery.

passed = true

| arm | success_rate | repeated_failure_rate | invalid_action_rate | memory_induced_regression_rate | negative_memory_hit_rate | rollback_frequency | promotion_precision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| no_memory | 0.0 | 1.0 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| naive_memory | 0.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 0.0 |
| retrieval_memory | 0.5 | 0.5 | 0.5 | 0.2 | 0.5 | 0.0 | 0.0 |
| memoryweaver_trace_candidate_runtime | 1.0 | 0.0 | 0.0 | 0.0 | 1.0 | 0.0 | 1.0 |
| rollback_probe | 1.0 | 0.0 | 0.0 | 0.0 | 1.0 | 1.0 | 0.0 |
| memoryweaver_trace_candidate_runtime_recovery | 1.0 | 0.0 | 0.0 | 0.0 | 1.0 | 1.0 | 0.0 |
| replacement_probe | 1.0 | 0.0 | 0.0 | 0.0 | 1.0 | 0.0 | 0.0 |

## Aggregate

- `same_family_task_count` = 50
- `repeated_failure_rate_delta_vs_no_memory` = -1.0
- `invalid_action_rate_delta_vs_naive_memory` = -1.0
- `task_success_delta_vs_retrieval_memory` = 0.5
- `memory_induced_regression_delta_vs_naive_memory` = -1.0
- `promotion_precision` = 1.0
- `negative_memory_hit_rate` = 1.0
- `candidate_registration_promotable` = 1.0
- `candidate_registration_audited` = 1.0
- `rejected_evidence_audited_count` = 1
- `replacement_path_selected` = 1.0
- `replacement_registration_audited` = 1.0
- `trace_store_roundtrip` = 1.0
- `runtime_path_store_roundtrip` = 1.0
- `rollback_recovery_success_rate` = 1.0

## Reliability

- pass@1: True
- pass^3: True
- Seeds: [0]

Research question: Can evidence-gated path promotion reduce repeated agent failures without increasing memory-induced error propagation?
