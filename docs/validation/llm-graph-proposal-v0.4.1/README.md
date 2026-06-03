# LLM GraphProposal v0.4.1 Validation

This validation treats every LLM-compatible backend strictly as an offline **LLM GraphProposal Provider**. It does not run on the online query path, write verified memory, stable Patterns, RelationEdge records without Harness review, or routing decisions.

## Configuration

- Provider: `local`
- Model: `local-graph-proposer`
- Prompt version: `graph_proposal_deepseek_v0.4.1`
- Review policy version: `graph-proposal-review-v0.4.1`
- Dataset size: `40` memories, `5` evidence nodes, `4` queries
- Proposal count: `4`
- Offline proposal count: `4`
- Online LLM call count: `0`
- Accepted / pending / rejected / quarantined: `0` / `2` / `2` / `0`
- Pending / reject / human-review rates: `0.5` / `0.5` / `1.0`
- Wrong link rate: `0.75`
- Evidence coverage: `1.0`
- Exact / partial / unsupported evidence support rates: `0.5` / `0.0` / `0.5`
- Accepted wrong link rate: `0.0`
- Review cost per accepted edge: `0.0`
- Human review needed: `4`

## Retrieval Comparison

| Arm | Tag Recall@k | Memory Recall@10 | Graph Expansion Precision | Candidate Reduction | Candidate Delta | Verified Text p95 ms | Online LLM Calls |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| no_graph | 1.0 | 0.5417 | 1.0 | 0.9125 | 0 | 0.7284 | 0 |
| manual_graph | 1.0 | 0.8334 | 1.0 | 0.8187 | 3.75 | 0.7246 | 0 |
| rule_graph | 1.0 | 0.8334 | 0.9167 | 0.8 | 4.5 | 0.6129 | 0 |
| llm_offline_proposal_graph | 1.0 | 0.5417 | 1.0 | 0.9125 | 0 | 0.7991 | 0 |

## Interpretation

This is a retrieval/linking validation, not a task-success experiment. v0.4.1 explicitly separates offline LLM proposal generation from online accepted-edge retrieval.

Layer 3 remains unchanged: provisional Patterns are limited to `fast_verify`, stable Patterns alone can route to `fast`, and evidence links do not auto-promote memory.
