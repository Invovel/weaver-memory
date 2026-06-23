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
- Mode: live LLM
- Families: 3
- Task runs: 15
- Provider: deepseek
- Model: deepseek-chat
- Family limit: 3
- Target limit: 1

## Arm Metrics

| Arm | Tasks | Success | Avg Steps | Known Bad | Invalid Actions | False Trigger | Spurious Retrieval | Evidence First | Retrieval Before Critical | Token Avg | LLM Calls |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fresh_no_memory | 3 | 0.0 | 6 | 0 | 18 | 0.0 | 0.0 | 0.0 | 0.0 | 183.6667 | 18 |
| random_experience_raw_logs | 3 | 0.0 | 6 | 0 | 18 | 0.0 | 0.0 | 0.0 | 0.0 | 672.3333 | 18 |
| random_experience_naive_memory | 3 | 0.0 | 6 | 5 | 13 | 1.0 | 1.0 | 0.0 | 0.0 | 535.6667 | 19 |
| mw_verified_experience | 3 | 1.0 | 1 | 0 | 0 | 0.0 | 0.0 | 1.0 | 1.0 | 95.3333 | 3 |
| mw_verified_experience_marker | 3 | 1.0 | 1 | 0 | 0 | 0.0 | 0.0 | 1.0 | 1.0 | 153 | 3 |

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
