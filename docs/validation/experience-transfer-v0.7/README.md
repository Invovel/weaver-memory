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
- Mode: deterministic local policy
- Families: 6
- Task runs: 72
- Provider:
- Model:
- Family limit: 0
- Target limit: 0

## Arm Metrics

| Arm | Tasks | Success | Avg Steps | Known Bad | Invalid Actions | Evidence First | Retrieval Before Critical | Token Avg | LLM Calls |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| no_memory | 15 | 1.0 | 2 | 15 | 0 | 0.0 | 0.0 | 59 | 0 |
| raw_rag_over_logs | 15 | 1.0 | 1.8 | 12 | 0 | 0.2 | 0.0 | 156.2 | 0 |
| mw_verified_memory | 15 | 1.0 | 1 | 0 | 0 | 1.0 | 1.0 | 93.6 | 0 |
| mw_verified_memory_marker | 15 | 1.0 | 1 | 0 | 0 | 1.0 | 1.0 | 150.4 | 0 |

## Marker-Only Boundary Metrics

This suite is reported separately and is not averaged into the main task
families.

| Arm | Tasks | Success | Avg Steps | Known Bad | Evidence First | Retrieval Before Critical | Marker Direct Change |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| no_memory | 3 | 1.0 | 2 | 3 | 0.0 | 0.0 | 0 |
| raw_rag_over_logs | 3 | 1.0 | 1 | 0 | 1.0 | 0.0 | 0 |
| mw_verified_memory | 3 | 1.0 | 2 | 3 | 0.0 | 0.0 | 0 |
| mw_verified_memory_marker | 3 | 1.0 | 1 | 0 | 1.0 | 0.0 | 3 |

## Probe Hygiene

- Main-suite valid decision-change rate for `mw_verified_memory`:
  1.0
- Main-suite invalid `no_memory` probes:
  0
- Marker-boundary valid decision-change rate for `mw_verified_memory_marker`:
  1.0

## Memory Use Diagnosis

- `mw_verified_memory` reason counts:
  {"marker_required": 3, "retrieval_hit": 15}
- `mw_verified_memory_marker` reason counts:
  {"marker_direct_guard": 3, "retrieval_hit": 15}

## Reliability

- pass@1: True
- pass^3: True
- Seeds: [7, 8, 9]

## Files

- `experience_families.jsonl`
- `task_runs.jsonl`
- `arm_metrics.json`
- `marker_only_arm_metrics.json`
- `decision_probe.jsonl`
- `probe_metrics.json`
- `memory_use_probe.jsonl`
- `memory_use_summary.json`
- `cost_metrics.json`
- `reliability.json`
- `raw_results.json`

## Interpretation

This is the structured deterministic Experience Transfer run. It compares source-learned verified experience against sibling target tasks across four arms.
