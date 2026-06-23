# Layer-3 Path Promotion v0.7

This validation measures MemoryWeaver's main claim:

> Layer-3 path promotion turns verified experience into reusable execution paths.

## Result

- Passed: True
- Families: 3
- Task runs: 9

## Metrics

| Metric | Value |
| --- | ---: |
| stable_promotion_rate | 1.0 |
| latest_path_selection_accuracy | 1.0 |
| skill_path_selection_accuracy | 1.0 |
| harness_path_selection_accuracy | 1.0 |
| stale_path_suppression_rate | 1.0 |
| rollback_success_rate | 1.0 |
| false_stable_promotion_count | 0 |
| average_path_regret | 0 |

## Files

- `families.jsonl`
- `path_catalog.jsonl`
- `task_runs.jsonl`
- `metrics.json`
- `raw_results.json`

## Interpretation

This suite is not about retrieval speed, marker novelty, or proving that online
LLM calls stayed at zero. It is about whether verified experience can be
promoted into a better Layer-3 execution path, whether stale paths are
suppressed, and whether overgeneralized paths can be rolled back.
