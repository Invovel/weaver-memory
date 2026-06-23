# LLM GraphProposal v0.4.2 Validation

This validation runs a real DeepSeek offline GraphProposal pressure test. DeepSeek never enters the online query path; it only produces offline proposals that pass through EvidenceSupportCheck and Harness review before accepted edges can affect online graph retrieval.

## Configuration

- Real provider: `deepseek`
- Real model: `deepseek-v4-pro`
- Local baseline provider: `local`
- Prompt version: `graph_proposal_deepseek_v0.4.2`
- Review policy version: `graph-proposal-review-v0.4.2`
- Dataset size: `40` memories, `5` evidence nodes, `4` queries
- Online LLM call count: `0`

## DeepSeek Proposal Metrics

- JSON parse success rate: `0.0`
- Proposal count: `0`
- Provider errors: `4`
  - q_subscription_cn: DeepSeek graph proposal request failed: HTTP Error 402: Payment Required
  - q_wsl_subscription: DeepSeek graph proposal request failed: HTTP Error 402: Payment Required
  - q_org_problem: DeepSeek graph proposal request failed: HTTP Error 402: Payment Required
  - q_api_key_but_codex_fails: DeepSeek graph proposal request failed: HTTP Error 402: Payment Required
- Accepted / pending / rejected / quarantined: `0` / `0` / `0` / `0`
- Accepted edge count: `0`
- Accepted wrong link rate: `0.0`
- Exact / partial / unsupported support rates: `0.0` / `0.0` / `0.0`
- Review cost per accepted edge: `0.0`

## v0.4 vs v0.4.2 Proposal-Level Comparison

| Metric | v0.4 | v0.4.2 | Target |
| --- | ---: | ---: | --- |
| proposals | 22 | 0 | <= 12 |
| accepted | 7 | 0 | > 0 |
| rejected | 0 | 0 | > 0 |
| accepted wrong link rate | n/a | 0.0 | 0 or close to 0 |
| online LLM calls | multiple / online path | 0 | 0 |

## v0.4 vs v0.4.2 Evidence Support Comparison

| Metric | v0.4 | v0.4.2 | Target |
| --- | ---: | ---: | --- |
| evidence coverage | 1.0 | 0.0 | <= 0.6 |
| supports_exact precision | n/a | 0.0 | >= 0.7 |
| supports_partial count | n/a | 0 | inspect |
| unsupported count | n/a | 0 | > 0 expected in noisy batch |

## Doctor Gate

- `mw doctor` valid: `True`
- doctor errors: `0`
- doctor warnings: `1`
- doctor info: `3`

## Success Criteria

- DeepSeek provider available: `False`
- accepted_edge_count > 0: `False`
- accepted_wrong_link_rate near 0: `True`
- Memory Recall@10 > no_graph: `False`
- online_llm_call_count = 0: `True`
- proposal budget respected: `True`
- supports_exact precision >= 0.7: `False`
- rejected > 0: `False`
- evidence coverage <= 0.6: `True`
- v0.4.2 pass: `False`

## Retrieval Comparison

| Arm | Tag Recall@k | Memory Recall@10 | Graph Expansion Precision | Candidate Reduction | Candidate Delta | Verified Text p95 ms | Online LLM Calls |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| no_graph | 1.0 | 0.5417 | 1.0 | 0.9125 | 0 | 0.7172 | 0 |
| manual_graph | 1.0 | 0.8334 | 1.0 | 0.8187 | 3.75 | 0.6455 | 0 |
| rule_graph | 1.0 | 0.8334 | 0.9167 | 0.8 | 4.5 | 0.7389 | 0 |
| local_offline_proposal_graph | 1.0 | 0.75 | 1.0 | 0.875 | 1.5 | 0.6213 | 0 |
| deepseek_offline_proposal_graph | 1.0 | 0.5417 | 1.0 | 0.9125 | 0 | 0.7226 | 0 |

## Interpretation

This is a retrieval/linking pressure validation, not a task-success experiment. v0.4.2 tests whether real offline LLM proposals can produce accepted edges without polluting the online path.

Layer 3 remains unchanged: provisional Patterns are limited to `fast_verify`, stable Patterns alone can route to `fast`, and evidence links do not auto-promote memory.

Pending proposals still require a lifecycle mechanism in a later release.

This run does not prove DeepSeek proposal utility because provider errors occurred before usable proposals were generated.

v0.5 should not start unless v0.4.2 passes: accepted edge count > 0, accepted wrong link rate near zero, and EvidenceSupportCheck exact-support precision passes manual audit.
