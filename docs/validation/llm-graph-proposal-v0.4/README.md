# LLM GraphProposal v0.4 Validation

This validation treats DeepSeek strictly as an **LLM GraphProposal Provider**. It does not write verified memory, stable Patterns, RelationEdge records without Harness review, or routing decisions.

## Configuration

- Provider: `deepseek`
- Model: `deepseek-v4-pro`
- Prompt version: `graph_proposal_deepseek_v0.4`
- Review policy version: `graph-proposal-review-v0.4`
- Dataset size: `40` memories, `5` evidence nodes, `4` queries
- Proposal count: `22`
- Accepted / pending / rejected / quarantined: `7` / `3` / `0` / `12`
- Pending / reject / human-review rates: `0.1364` / `0.0` / `0.6818`
- Wrong link rate: `0.9091`
- Evidence coverage: `1.0`
- Human review needed: `15`

## Retrieval Comparison

| Arm | Tag Recall@k | Memory Recall@10 | Graph Expansion Precision | Candidate Reduction | Verified Text p95 ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| no_graph | 1.0 | 0.5417 | 1.0 | 0.9125 | 0.0585 |
| manual_graph | 1.0 | 0.8334 | 1.0 | 0.8187 | 0.0993 |
| rule_graph | 1.0 | 0.8334 | 0.9167 | 0.8 | 0.1078 |
| deepseek_proposal_graph | 1.0 | 0.9167 | 0.9167 | 0.7812 | 0.1385 |

## Interpretation

This is a retrieval/linking validation, not a task-success experiment. A positive result means graph proposals can shrink or improve retrieval candidates under Harness review; it does not prove that MemoryWeaver improves end-to-end Agent success rate.

Layer 3 remains unchanged: provisional Patterns are limited to `fast_verify`, stable Patterns alone can route to `fast`, and evidence links do not auto-promote memory.
