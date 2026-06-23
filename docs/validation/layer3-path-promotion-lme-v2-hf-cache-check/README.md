# Layer-3 Path Promotion over LongMemEval-V2

This validation runs the Layer-3 path-promotion flow on a small real
LongMemEval-V2 snapshot subset.

## Result

- Passed: True
- Resolved root: D:\benchmarks\longmemeval-v2
- Root source: benchmarks
- Question count: 3
- Loaded trajectories: 1
- Derived families: 3

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

- `raw_results.json`
- `snapshot.json`
- `families.jsonl`
- `path_catalog.jsonl`
- `task_runs.jsonl`
- `metrics.json`
- `derivation_samples.jsonl`

## Interpretation

This run is not a full open-world benchmark. It is the minimal real-data bridge:
LongMemEval-V2 snapshot -> derived path families -> Layer-3 promotion ->
best-path selection / stale-path suppression / rollback checks.
