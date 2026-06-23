# v0.4.4a MemEvoBench-Style Fixture Smoke Test

This is a MemEvoBench-style synthetic fixture smoke test inspired by the benchmark setting. It is not an official MemEvoBench integration validation and does not run task-completion agents or LLM judges.

## Source

- Dataset source: `built-in-memevobench-style-fixture`
- Reference: MemEvoBench, `https://arxiv.org/abs/2604.15774`
- Official MemEvoBench data: `not integrated in this validation`
- Events: `8`
- Queries: `2`

## Naive Baseline Comparison

| Metric | naive_no_gate | memoryweaver_source_gate | Delta |
| --- | ---: | ---: | ---: |
| trusted Recall@10 | 1.0 | 1.0 | 0.0 |
| pollution retrieval leak count | 3 | 0 | 3 |
| wrong promotion count | 5 | 0 | 5 |
| contradiction false accept rate | 1.0 | 0.0 | 1.0 |

## Metrics

- promotion accuracy: `1.0`
- trusted promotion recall: `1.0`
- pollution promotion block rate: `1.0`
- untrusted retrieval block rate: `1.0`
- contradiction severity accuracy: `1.0`
- contradiction block rate: `1.0`
- official correct Recall@10: `0.0`
- official misleading leak rate: `0.0`
- Memory Recall@10: `1.0`
- pollution retrieval leak count: `0`

## Scope

Line B is independent of v0.4.2 accepted-edge results. This smoke test measures source gate, ContradictionResolver, and VerifiedRetriever behavior under adversarial injection, noisy tool output, and biased feedback.

This result proves pollution resistance on a small synthetic fixture. It does not prove task success improvement, long-term memory-use gains, reduced repeated errors, or superiority over RAG over logs.

v0.5 scaling should still wait on the graph accepted-edge decision, but this adapter can already provide external-benchmark-facing trust-boundary metrics for the paper.
