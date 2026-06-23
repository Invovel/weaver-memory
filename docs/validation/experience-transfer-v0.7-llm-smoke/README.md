# v0.7 Experience Transfer Protocol

This validation measures experience reuse across sibling task families.

Protocol:

```text
source episode family -> sibling target task family
```

Arms:

- A. `no_memory`
- B. `raw_rag_over_logs`
- C. `mw_verified_memory`
- D. `mw_verified_memory_marker`

## Result

- Passed: True
- Families: 1
- Task runs: 4

## Arm Metrics

| Arm | Tasks | Success | Avg Steps | Known Bad | Invalid Actions | Evidence First | Retrieval Before Critical | Token Avg |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| no_memory | 1 | 0.0 | 6 | 0 | 6 | 0.0 | 0.0 | 184 |
| raw_rag_over_logs | 1 | 1.0 | 1 | 0 | 0 | 1.0 | 0.0 | 89 |
| mw_verified_memory | 1 | 1.0 | 1 | 0 | 0 | 1.0 | 1.0 | 97 |
| mw_verified_memory_marker | 1 | 1.0 | 1 | 0 | 0 | 1.0 | 1.0 | 155 |

## Files

- `experience_families.jsonl`
- `task_runs.jsonl`
- `arm_metrics.json`
- `decision_probe.jsonl`
- `memory_use_probe.jsonl`
- `cost_metrics.json`
- `raw_results.json`

## Interpretation

This is the first structured Experience Transfer run. It is still local and
deterministic, but unlike v0.7 smoke tests it compares source-learned verified
experience against sibling target tasks across four arms.
