# v0.4.4 MemEvoBench-Style Trust-Boundary Validation

This is a MemEvoBench-style synthetic dirty fixture validation inspired by the benchmark setting. It is not an official MemEvoBench integration validation and does not run task-completion agents or LLM judges.

## Supported Claim

We evaluate MemoryWeaver on a MemEvoBench-style synthetic dirty fixture with 50 events, 16 queries, and three baselines: naive_no_gate, memoryweaver_source_gate, and strict_verified_only. MemoryWeaver reduces pollution retrieval leaks from 9 to 0, wrong promotions from 37 to 0, and contradiction false-accept rate from 1.0 to 0.0, while improving trusted Recall@10 from 0.625 to 0.8125. This validation does not constitute an official MemEvoBench result or an end-to-end agent task success evaluation.

中文：MemoryWeaver 在一个 MemEvoBench-style 合成污染 fixture 中减少了污染检索、错误晋升和冲突误接受，并且没有降低可信记忆召回。

This result is suitable for a paper subsection titled `Trust-Boundary Validation`. It is not evidence of experience reuse, path reuse, task success improvement, or superiority over RAG over logs.

## Source

- Dataset source: `built-in MemEvoBench-style synthetic fixture`
- Fixture identifier: `built-in-memevobench-style-dirty50-synthetic-fixture`
- Reference: MemEvoBench, `https://arxiv.org/abs/2604.15774`
- Official MemEvoBench data: `not integrated`
- This validation is not an official MemEvoBench score.
- Events: `50`
- Queries: `16`

## Naive Baseline Comparison

| Metric | naive_no_gate | memoryweaver_source_gate | strict_verified_only | Key Delta |
| --- | ---: | ---: | ---: | ---: |
| trusted Recall@10 | 0.625 | 0.8125 | 0.8125 | 0.1875 |
| pollution retrieval leak count | 9 | 0 | 0 | 9 |
| wrong promotion count | 37 | 0 | 0 | 37 |
| contradiction false accept rate | 1.0 | 0.0 | 0.0 | 1.0 |

## Metrics

- promotion accuracy: `1.0`
- trusted promotion recall: `1.0`
- pollution promotion block rate: `1.0`
- untrusted retrieval block rate: `1.0`
- contradiction severity accuracy: `1.0`
- contradiction block rate: `1.0`
- boundary case pass rate: `1.0`
- official correct Recall@10: `0.0`
- official misleading leak rate: `0.0`
- Memory Recall@10: `0.8125`
- pollution retrieval leak count: `0`

## Scope

Line B is independent of v0.4.2 accepted-edge results. This smoke test measures source gate, ContradictionResolver, and VerifiedRetriever behavior under adversarial injection, noisy tool output, and biased feedback.

This result supports a trust-boundary claim on a synthetic dirty memory-misevolution fixture. It does not prove task success improvement, long-term memory-use gains, reduced repeated errors, or superiority over RAG over logs.

Completion criteria checked here: naive baseline, dirty fixture size, >=10 queries, MemoryWeaver pollution/wrong-promotion/false-accept improvements over naive, trusted recall preservation, strict_verified_only comparison, explicit non-official dataset labeling, and reproducible raw JSON artifacts.

Next step: v0.4.5 should differentiate MemoryWeaver from strict_verified_only by testing useful weak signals that strict filtering drops but source-gated lifecycle policy can retain safely.
