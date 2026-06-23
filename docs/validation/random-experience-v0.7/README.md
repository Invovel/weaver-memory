# v0.7 Random Experience Accumulation Protocol

This validation measures whether random/noisy prior experience causes false
triggering compared with curated verified MemoryWeaver experience.

Protocol:

```text
random unrelated experience families -> relevant sibling target family
```

Arms:

- A. `fresh_no_memory`
- B. `random_experience_raw_logs`
- C. `random_experience_naive_memory`
- D. `mw_verified_experience`
- E. `mw_verified_experience_marker`

## Result

- Passed: True
- Mode: deterministic local policy
- Families: 6
- Task runs: 90
- Provider:
- Model:
- Family limit: 0
- Target limit: 0

## Arm Metrics

| Arm | Tasks | Success | Avg Steps | Known Bad | Invalid Actions | False Trigger | Spurious Retrieval | Evidence First | Retrieval Before Critical | Token Avg | LLM Calls |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fresh_no_memory | 18 | 1.0 | 2 | 18 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 59.3333 | 0 |
| random_experience_raw_logs | 18 | 1.0 | 2 | 18 | 0 | 1.0 | 1.0 | 0.0 | 0.0 | 223.5 | 0 |
| random_experience_naive_memory | 18 | 1.0 | 2 | 18 | 0 | 1.0 | 1.0 | 0.0 | 0.0 | 177.6667 | 0 |
| mw_verified_experience | 18 | 1.0 | 1 | 0 | 0 | 0.0 | 0.0 | 1.0 | 1.0 | 95 | 0 |
| mw_verified_experience_marker | 18 | 1.0 | 1 | 0 | 0 | 0.0 | 0.0 | 1.0 | 1.0 | 152.5 | 0 |

## Files

- `experience_families.jsonl`
- `task_runs.jsonl`
- `arm_metrics.json`
- `cost_metrics.json`
- `raw_results.json`

## Interpretation

This protocol is designed to expose when raw logs or naive memory convert
unrelated experience into current-task actions. MemoryWeaver should preserve
verified retrieval while keeping false-trigger and spurious-retrieval rates at
zero.
