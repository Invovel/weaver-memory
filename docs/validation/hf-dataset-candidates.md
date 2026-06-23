# Hugging Face Dataset Candidates

Date checked: 2026-06-12

Source: Hugging Face public dataset API and Hub search.

This note separates currently validated MemoryWeaver inputs from future
benchmark candidates. It should be used together with
[huggingface_dataset_catalog.md](./huggingface_dataset_catalog.md) and
[lme-v2-storage-check](./lme-v2-storage-check/README.md).

## Current Primary Dataset

| Dataset | Status | License | Size | Current MemoryWeaver status |
| --- | --- | --- | --- | --- |
| [xiaowu0162/longmemeval-v2](https://hf.co/datasets/xiaowu0162/longmemeval-v2) | Available on HF | Apache-2.0 | n<1K questions | Adapter exists; local snapshot validated through `D:\benchmarks\longmemeval-v2`; cache root checked at `D:\hf_cache` |

## Near-Term Candidates

| Dataset | Status | License | Size | Proposed use |
| --- | --- | --- | --- | --- |
| [ai-hyz/MemoryAgentBench](https://hf.co/datasets/ai-hyz/MemoryAgentBench) | Available on HF | MIT | n<1K | Preview adapter validated across four splits; no task-accuracy claim |
| [xiaowu0162/longmemeval-cleaned](https://hf.co/datasets/xiaowu0162/longmemeval-cleaned) | Available on HF | MIT | not tagged | Dialogue-style long-term memory baseline; not yet integrated |
| [Percena/locomo-mc10](https://hf.co/datasets/Percena/locomo-mc10) | Available on HF | CC-BY-NC-4.0 | 1K<n<10K | Preview adapter validated; no task-accuracy claim |
| [mteb/LoCoMo](https://hf.co/datasets/mteb/LoCoMo) | Available on HF | CC-BY-NC-4.0 | 10K<n<100K | Retrieval-style LoCoMo bridge; not yet integrated |

## Retrieval / Evidence Candidates

| Dataset | Status | License | Size | Proposed use |
| --- | --- | --- | --- | --- |
| [miracl/miracl](https://hf.co/datasets/miracl/miracl) | Available on HF | Apache-2.0 | topics/qrels | Chinese and multilingual retrieval topics |
| [miracl/miracl-corpus](https://hf.co/datasets/miracl/miracl-corpus) | Available on HF | Apache-2.0 | 10M<n<100M | Large multilingual retrieval corpus; sample Chinese subset first |
| [BeIR/scifact](https://hf.co/datasets/BeIR/scifact) | Available on HF | CC-BY-SA-4.0 | 1K<n<10K | RAG evidence retrieval and fact-checking retrieval |
| [miracl/hagrid](https://hf.co/datasets/miracl/hagrid) | Available on HF | Apache-2.0 | 1K<n<10K | Attribution and citation coverage after RAG evidence layer |

## Boundary Notes

- `xiaowu0162/longmemeval-v2` currently has the primary MemoryWeaver adapter and
  local validation artifacts for external path-promotion work.
- `Percena/locomo-mc10` now has a preview adapter validation artifact:
  [locomo-mc10-adapter-check](./locomo-mc10-adapter-check/README.md). This is
  not a task-accuracy, verified-memory, or Layer-3 path-promotion result.
- `ai-hyz/MemoryAgentBench` now has a preview adapter validation artifact:
  [memoryagentbench-adapter-check](./memoryagentbench-adapter-check/README.md).
  This is not a task-accuracy, verified-memory, or Layer-3 path-promotion
  result.
- `D:\hf_cache` is a cache root. The current full LME-V2 readable snapshot is
  `D:\benchmarks\longmemeval-v2`.
- The datasets above should not be described as current MemoryWeaver benchmark
  results until a dedicated adapter writes manifest, metrics, and validation
  artifacts.
- MemEvoBench, Mem2ActBench, and EvoMemBench remain reference lines unless a
  concrete official dataset/code path is integrated and labeled separately.
