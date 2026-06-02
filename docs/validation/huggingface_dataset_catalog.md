# Hugging Face Dataset Catalog For MemoryWeaver Evaluation

## Purpose

This catalog records datasets discovered through the Hugging Face Hub on
2026-06-02. It separates datasets that can be adapted soon from datasets that
belong to later RAG and multilingual phases. No external dataset is vendored
into this repository by this document.

## Recommended Dataset Stack

| Priority | Dataset | Use | Integration level | License |
| --- | --- | --- | --- | --- |
| 1 | [xiaowu0162/longmemeval-cleaned](https://hf.co/datasets/xiaowu0162/longmemeval-cleaned) | Main long-term assistant-memory benchmark | Add adapter first | MIT |
| 2 | [Percena/locomo-mc10](https://hf.co/datasets/Percena/locomo-mc10) | Lightweight automated conversational-memory smoke test | Add adapter first | CC-BY-NC-4.0 |
| 3 | [miracl/miracl](https://hf.co/datasets/miracl/miracl) | Multilingual retrieval topics and qrels, including Chinese | Add in retrieval phase | Apache-2.0 |
| 4 | [miracl/miracl-corpus](https://hf.co/datasets/miracl/miracl-corpus) | MIRACL multilingual corpus | Add sampled Chinese subset first | Apache-2.0 |
| 5 | [BeIR/scifact](https://hf.co/datasets/BeIR/scifact) | Evidence retrieval and fact-checking retrieval | Add in RAG evidence phase | CC-BY-SA-4.0 |
| 6 | [miracl/hagrid](https://hf.co/datasets/miracl/hagrid) | Attributable generative retrieval and citation coverage | Add after evidence citations exist | Apache-2.0 |

## Selection Rationale

### Long-term memory

[xiaowu0162/longmemeval-cleaned](https://hf.co/datasets/xiaowu0162/longmemeval-cleaned)
replaces the deprecated original LongMemEval dataset and removes noisy history
sessions that interfere with answer correctness. It should be the main
longitudinal benchmark.

[Percena/locomo-mc10](https://hf.co/datasets/Percena/locomo-mc10) contains
`1,986` multiple-choice items derived from LoCoMo. Its ten-option format makes
it suitable for cheap, deterministic smoke tests before running more expensive
generative evaluation. It includes single-hop, multi-hop, temporal,
open-domain, and adversarial categories.

### Chinese and multilingual retrieval

[miracl/miracl](https://hf.co/datasets/miracl/miracl) supplies retrieval topics
and qrels across 18 languages, including Chinese. Pair it with
[miracl/miracl-corpus](https://hf.co/datasets/miracl/miracl-corpus). Start with
a pinned Chinese subset because the complete corpus is large.

### Evidence retrieval and attribution

[BeIR/scifact](https://hf.co/datasets/BeIR/scifact) is a small scientific
fact-checking retrieval benchmark. It is appropriate for Recall@k, MRR, and
nDCG tests once the RAG evidence layer exists.

[miracl/hagrid](https://hf.co/datasets/miracl/hagrid) adds manually labelled
relevant passages for attributable generative information seeking. Use it for
citation precision, citation recall, and unsupported-claim rate.

## Adapter Requirements

Every dataset adapter should write a manifest containing:

```text
dataset_id
hub_revision
downloaded_at_utc
license
split
language
sample_policy
row_count
content_hash
adapter_version
```

The processed artifact must be immutable. Imported memory should retain:

```text
source=file
dataset_id
record_id
split
language
provenance
adapter_version
content_hash
```

Assistant-generated transformations must be marked `source=synthetic` and
must not become verified facts.

## Suggested Rollout

1. Implement `longmemeval-cleaned` and `locomo-mc10` adapters.
2. Pin small development samples for fast CI.
3. Add full offline runs outside CI.
4. Add a Chinese MIRACL subset when tokenizer work begins.
5. Add SciFact and HAGRID when the evidence layer and citations exist.
6. Preserve raw manifests and processed hashes in every tagged evaluation.
