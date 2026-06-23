# Harness Runtime Live LLM

Live-agent bridge for evidence-gated runtime path promotion.

passed = true
mode = live_llm
live_llm_run_complete = true

| arm | success_rate | repeated_failure_rate | invalid_action_rate | known_bad_action_rate | memory_induced_regression_rate | rollback_frequency | promotion_precision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| memoryweaver_live_candidate_runtime | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 |
| rollback_probe | 1.0 | 0.0 | 0.0 | 1.0 | 0.0 | 1.0 | 0.0 |

## Aggregate

- `live_llm_run_complete` = 1.0
- `online_llm_call_count` = 3.0
- `live_proposal_count` = 3.0
- `tool_result_count` = 3.0
- `canonicalized_bundle_count` = 2.0
- `tests_passed` = 1.0
- `file_diff_matches_expected` = 1.0
- `benchmark_delta` = 0.16
- `candidate_registration_promotable` = 1.0
- `candidate_registration_audited` = 1.0
- `rejected_evidence_audited_count` = 0.0
- `promotion_external_evidence_only` = 1.0
- `trace_store_roundtrip` = 1.0
- `runtime_path_store_roundtrip` = 1.0
- `rollback_recorded` = 1.0
- `memory_induced_regression_rate` = 0.0

## Reliability

- pass@1: True
- live LLM pass^3: True
- Seeds: [21, 22, 23]

## Run Commands

- Mock bridge: `python benchmarks\harness_runtime_live_llm.py --reliability-passes 3 --seed 21`
- Real LLM gate: `python benchmarks\harness_runtime_live_llm.py --llm --provider deepseek --model deepseek-chat --reliability-passes 3 --seed 21`

## Boundary

- Mock mode validates the artifact contract and Harness authority path.
- Only `--llm` mode counts as the missing live LLM run.
- Mock bridge pass^3 cannot be cited as live LLM pass^3.
- Model output remains a proposal; promotion still requires external evidence.

Research question: Can evidence-gated path promotion reduce repeated agent failures without increasing memory-induced error propagation?
