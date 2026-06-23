# SQLite FTS5 Frontend Filter v0.5.4a

## Purpose

This validation compares MemoryWeaver frontend filters against a traditional
keyword retriever:

```text
A. full_scan
B. SQLite FTS5 over all capsules
C. MW tag/time filter
D. MW tag/time -> SQLite FTS5
E. MW graph/tag/time -> SQLite FTS5
```

The question is not whether MemoryWeaver replaces FTS5. The question is whether
MemoryWeaver can sit in front of FTS5 as a trust/time/marker-aware candidate
filter, keeping Recall@10 while making FTS5 rank far fewer candidates.

## Command

```powershell
python .\benchmarks\retrieval_fts5_filter_validation.py `
  --output-dir .\docs\validation\retrieval-fts5-filter-v0.5.4a
```

## Gates

```text
query_count >= 50
SQLite FTS5 available
MW tag/time -> FTS5 Recall@10 not more than 0.05 below FTS5 all
MW graph/tag/time -> FTS5 Recall@10 not more than 0.05 below FTS5 all
candidate reduction >= 90%
p95 latency not above FTS5 all
online_llm_call_count = 0
memory_promotion_count = 0
layer3_mutation_count = 0
```

## Observed Metrics

```json
{
  "query_count": 50,
  "capsule_count": 341,
  "fts5_available": true,
  "fts5_all_recall_at_10": 1.0,
  "tag_time_fts5_recall_at_10": 1.0,
  "graph_tag_time_fts5_recall_at_10": 1.0,
  "fts5_all_average_candidate_count": 341,
  "tag_time_fts5_average_candidate_count": 6.44,
  "graph_tag_time_fts5_average_candidate_count": 6.44,
  "tag_time_fts5_candidate_reduction_ratio": 0.9811,
  "graph_tag_time_fts5_candidate_reduction_ratio": 0.9811,
  "fts5_all_latency_p95_ms": 11.5543,
  "tag_time_fts5_latency_p95_ms": 2.0186,
  "graph_tag_time_fts5_latency_p95_ms": 1.557,
  "recall_delta_tag_time_vs_fts5": 0.0,
  "recall_delta_graph_vs_fts5": 0.0,
  "online_llm_call_count": 0,
  "memory_promotion_count": 0,
  "layer3_mutation_count": 0
}
```

## Generated Artifacts

```text
raw_results.json
metrics_summary.json
arms.jsonl
query_results.jsonl
```

## Interpretation

This is a frontend-filter validation. FTS5 remains the traditional keyword
retriever; MemoryWeaver filters the candidate set before ranking. It does not
prove superiority over dense retrieval, hybrid RAG, GraphRAG, or real agent
task success.
