# Retrieval Comparison v0.5.4

## Purpose

This validation compares three zero-dependency retrieval paths over the
ContextCapsule stress corpus:

```text
A. baseline_scan
   rank every capsule by lexical similarity

B. tag_time_lookup
   use marker-required evidence tags through TagTimeIndex

C. graph_tag_time_lookup
   expand marker/core-issue tags through accepted graph edges, then use
   TagTimeIndex
```

It is inspired by graph-memory and FTS/BM25-style retrieval systems, but it does
not add embeddings, vector databases, external FTS services, or online LLM calls.

## Command

```powershell
python .\benchmarks\retrieval_comparison_validation.py `
  --output-dir .\docs\validation\retrieval-comparison-v0.5.4
```

## Gates

```text
query_count >= 50
tag_time_recall_at_10 >= baseline_recall_at_10
graph_recall_at_10 >= baseline_recall_at_10
tag_time_average_candidate_count < baseline_average_candidate_count
graph_average_candidate_count < baseline_average_candidate_count
graph_expansion_precision >= 0.95
online_llm_call_count = 0
memory_promotion_count = 0
layer3_mutation_count = 0
```

## Observed Metrics

```json
{
  "query_count": 50,
  "capsule_count": 341,
  "baseline_recall_at_10": 1.0,
  "tag_time_recall_at_10": 1.0,
  "graph_recall_at_10": 1.0,
  "baseline_average_candidate_count": 341,
  "tag_time_average_candidate_count": 6.44,
  "graph_average_candidate_count": 6.44,
  "tag_time_candidate_reduction_ratio": 0.9811,
  "graph_candidate_reduction_ratio": 0.9811,
  "graph_expansion_precision": 1.0,
  "online_llm_call_count": 0,
  "memory_promotion_count": 0,
  "layer3_mutation_count": 0
}
```

The candidate reduction is large because marker-required tags and accepted
graph edges narrow retrieval to a small evidence neighborhood before lexical
reranking. This is not an FTS/BM25 production benchmark; it is a local
retrieval-substrate comparison over the v0.5.3.x capsule stress corpus.

## Generated Artifacts

```text
raw_results.json
metrics_summary.json
query_results.jsonl
arms.jsonl
```

## Interpretation

This is a retrieval-substrate validation. It tests whether structured tag/time
and accepted graph edges can shrink candidate sets without hurting Recall@10.
It does not prove end-to-end task success, repeated-error reduction, or RAG over
logs superiority.
