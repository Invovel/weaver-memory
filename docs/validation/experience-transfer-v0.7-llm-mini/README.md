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
- Mode: live LLM
- Families: 5
- Task runs: 40
- Provider: deepseek
- Model: deepseek-chat
- Family limit: 5
- Target limit: 2

## Arm Metrics

| Arm | Tasks | Success | Avg Steps | Known Bad | Invalid Actions | Evidence First | Retrieval Before Critical | Token Avg | LLM Calls |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| no_memory | 10 | 0.0 | 6 | 0 | 60 | 0.0 | 0.0 | 177.8 | 65 |
| raw_rag_over_logs | 10 | 1.0 | 1 | 0 | 0 | 1.0 | 0.0 | 86.8 | 10 |
| mw_verified_memory | 10 | 1.0 | 1 | 0 | 0 | 1.0 | 1.0 | 93.6 | 10 |
| mw_verified_memory_marker | 10 | 1.0 | 1 | 0 | 0 | 1.0 | 1.0 | 150.4 | 12 |

## Files

- `experience_families.jsonl`
- `task_runs.jsonl`
- `arm_metrics.json`
- `decision_probe.jsonl`
- `memory_use_probe.jsonl`
- `cost_metrics.json`
- `raw_results.json`

## Interpretation

This run uses a live LLM action selector with opaque action ids. It measures whether external context or MemoryWeaver retrieval can map those opaque actions to useful evidence before the agent exhausts its step budget.
