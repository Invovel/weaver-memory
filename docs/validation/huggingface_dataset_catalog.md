# Hugging Face Dataset Catalog For MemoryWeaver Evaluation

## Purpose

This catalog records datasets discovered through the Hugging Face Hub. It was
last refreshed on 2026-06-12 while validating the local LongMemEval-V2 cache.
It separates datasets that can be adapted soon from datasets that belong to
later RAG and multilingual phases. No external dataset is vendored into this
repository by this document.

## Local Cache Status

Current machine:

```text
HF cache root: D:\hf_cache
Resolved LongMemEval-V2 working snapshot: D:\benchmarks\longmemeval-v2
```

Important distinction:

- `D:\hf_cache` is the Hugging Face cache root.
- The current `xiaowu0162/longmemeval-v2` cache entry under
  `D:\hf_cache\hub\datasets--xiaowu0162--longmemeval-v2` contains `refs/main`
  but does not currently contain a full `snapshots/<revision>/...` tree.
- The complete readable snapshot is present at `D:\benchmarks\longmemeval-v2`
  and includes `questions.jsonl`, `trajectories.jsonl`, `haystacks/`,
  screenshots, `SCHEMA.md`, `DATA_CARD.md`, `LICENSE`, and checksum metadata.
- Existing MemoryWeaver resolvers correctly prefer the explicit/benchmark
  snapshot root first, then fall back to `D:\hf_cache` if a complete snapshot
  tree exists there.

Verified commands on 2026-06-12:

```powershell
python benchmarks\longmemeval_v2_adapter_v0_6_4a.py `
  --output-dir docs\validation\longmemeval-v2-adapter-v0.6.4a-hf-cache-check `
  --hf-cache-root D:\hf_cache

python benchmarks\layer3_path_promotion_lme_v2.py `
  --output-dir docs\validation\layer3-path-promotion-lme-v2-hf-cache-check `
  --hf-cache-root D:\hf_cache `
  --question-limit 3 `
  --trajectories-per-question 1 `
  --states-per-trajectory 2
```

Both commands passed. Their `root_resolution_source` was `benchmarks`, meaning
the run used `D:\benchmarks\longmemeval-v2` as the complete local snapshot while
keeping `D:\hf_cache` as the cache root.

Machine-readable storage check:

- [lme-v2-storage-check](./lme-v2-storage-check/README.md)
- [hf-dataset-candidates](./hf-dataset-candidates.md)
- [hf-dataset-candidates-check](./hf-dataset-candidates-check/README.md)
- [memoryagentbench-adapter-check](./memoryagentbench-adapter-check/README.md)

## Recommended Dataset Stack

| Priority | Dataset | Use | Integration level | License |
| --- | --- | --- | --- | --- |
| 1 | [xiaowu0162/longmemeval-v2](https://hf.co/datasets/xiaowu0162/longmemeval-v2) | Main agent long-term memory and environment-experience benchmark | Adapter exists; local snapshot validated | Apache-2.0 |
| 2 | [xiaowu0162/longmemeval-cleaned](https://hf.co/datasets/xiaowu0162/longmemeval-cleaned) | Long-term assistant-memory benchmark for dialogue-style memory | Add adapter after LME-V2 path experiments | MIT |
| 3 | [Percena/locomo-mc10](https://hf.co/datasets/Percena/locomo-mc10) | Lightweight automated conversational-memory smoke test | Preview adapter validated; no accuracy claim | CC-BY-NC-4.0 |
| 4 | [mteb/LoCoMo](https://hf.co/datasets/mteb/LoCoMo) | Retrieval-form LoCoMo bridge through MTEB formatting | Add in retrieval comparison phase | CC-BY-NC-4.0 |
| 5 | [miracl/miracl](https://hf.co/datasets/miracl/miracl) | Multilingual retrieval topics and qrels, including Chinese | Add in Chinese/multilingual retrieval phase | Apache-2.0 |
| 6 | [miracl/miracl-corpus](https://hf.co/datasets/miracl/miracl-corpus) | MIRACL multilingual corpus | Add sampled Chinese subset first | Apache-2.0 |
| 7 | [BeIR/scifact](https://hf.co/datasets/BeIR/scifact) | Evidence retrieval and fact-checking retrieval | Add in RAG evidence phase | CC-BY-SA-4.0 |
| 8 | [miracl/hagrid](https://hf.co/datasets/miracl/hagrid) | Attributable generative retrieval and citation coverage | Add after evidence citations exist | Apache-2.0 |
| 9 | [ai-hyz/MemoryAgentBench](https://hf.co/datasets/ai-hyz/MemoryAgentBench) | Incremental multi-turn agent-memory evaluation | Preview adapter validated; no accuracy claim | MIT |

## Selection Rationale

### Long-term memory

[xiaowu0162/longmemeval-v2](https://hf.co/datasets/xiaowu0162/longmemeval-v2)
is now the primary external benchmark candidate for MemoryWeaver because it
targets long-term memory in web and enterprise agents rather than only
dialogue recall. The local snapshot path currently used by benchmarks is
`D:\benchmarks\longmemeval-v2`; `D:\hf_cache` is the cache root used by
download/discovery.

[xiaowu0162/longmemeval-cleaned](https://hf.co/datasets/xiaowu0162/longmemeval-cleaned)
replaces the deprecated original LongMemEval dataset and removes noisy history
sessions that interfere with answer correctness. It should be the main
dialogue-memory benchmark after the LME-V2 path-promotion line.

[Percena/locomo-mc10](https://hf.co/datasets/Percena/locomo-mc10) contains
`1,986` multiple-choice items derived from LoCoMo. Its ten-option format makes
it suitable for cheap, deterministic smoke tests before running more expensive
generative evaluation. It includes single-hop, multi-hop, temporal,
open-domain, and adversarial categories.

Current MemoryWeaver status: preview adapter validation passed on a Hugging
Face `first-rows` sample:
[locomo-mc10-adapter-check](./locomo-mc10-adapter-check/README.md). This only
validates schema conversion, source policy, candidate-memory dry-run, and the
assistant ambiguous boundary. It does not measure LoCoMo-MC10 answer accuracy.

[mteb/LoCoMo](https://hf.co/datasets/mteb/LoCoMo) is useful when the target is
retrieval-style evaluation rather than MC answer selection.

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

### Benchmarks without confirmed Hugging Face dataset integration

The following are useful references, but should not be described as current
Hugging Face dataset integrations until a concrete dataset repo and adapter are
validated:

| Reference | Current status |
| --- | --- |
| Mem2ActBench | Paper reference for memory-to-action grounding; no validated local/HF adapter yet. |
| EvoMemBench | Paper/code reference for memory scope/content taxonomy; no validated local/HF adapter yet. |
| MemEvoBench | Current repo has a MemEvoBench-style synthetic dirty fixture, not an official dataset integration. |

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

1. Keep `xiaowu0162/longmemeval-v2` as the primary external path-promotion bridge.
2. Preserve the local root/cache distinction: `D:\benchmarks\longmemeval-v2`
   is the readable snapshot; `D:\hf_cache` is the cache root.
3. Implement `longmemeval-cleaned`, `locomo-mc10`, and `mteb/LoCoMo` adapters
   only after the Layer-3 E2E paper experiment is stable.
4. Pin small development samples for fast CI.
5. Add a Chinese MIRACL subset when tokenizer work begins.
6. Add SciFact and HAGRID when the evidence layer and citations exist.
7. Preserve raw manifests and processed hashes in every tagged evaluation.
