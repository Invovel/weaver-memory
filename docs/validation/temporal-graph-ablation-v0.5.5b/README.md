# Temporal Graph Ablation v0.5.5b

This validation compares a static tag co-occurrence graph with MemoryWeaver's
temporal GBrain projection.

The test asks:

```text
Does temporal metadata improve runtime candidate safety compared with a static
tag graph, without changing Layer 3 lifecycle or granting runtime authority?
```

## Arms

```text
A. static_cooccurrence
   Rank all markers by lexical/tag co-occurrence. No validity window,
   freshness, drift, or challenged state is applied.

B. temporal_runtime
   Rank only temporal-runtime-eligible markers. Stale, challenged, expired, and
   valid_to-bounded markers are removed from runtime candidates and sent to the
   review queue.
```

## Results

```json
{
  "query_count": 50,
  "marker_count": 50,
  "runtime_eligible_query_count": 37,
  "review_only_query_count": 13,
  "static_recall_at_10": 1.0,
  "temporal_runtime_recall_at_10": 1.0,
  "static_average_candidate_count": 50,
  "temporal_average_candidate_count": 37,
  "static_stale_runtime_leak_count": 66,
  "temporal_stale_runtime_leak_count": 0,
  "static_challenged_runtime_leak_count": 66,
  "temporal_challenged_runtime_leak_count": 0,
  "temporal_review_capture_rate": 1.0,
  "runtime_authority_granted_count": 0,
  "memory_promotion_count": 0,
  "layer3_mutation_count": 0,
  "online_llm_call_count": 0
}
```

## Interpretation

The static graph has perfect marker recall, but it treats stale and challenged
markers as ordinary runtime candidates. In this fixture, static retrieval leaks
66 stale and 66 challenged top-10 runtime candidates.

The temporal graph keeps Recall@10 at 1.0 for runtime-eligible markers, removes
stale/challenged candidates from runtime, and captures all review-only markers
in the review queue.

This supports the design claim that GBrain should be temporal. The benefit is
not merely better matching; it is safer candidate routing:

```text
static graph       -> related marker
temporal GBrain    -> related marker + validity state + review boundary
```

## Non-Claims

This validation does not prove:

- task success improvement
- automatic marker repair
- automatic Layer-3 Pattern promotion
- production graph performance
- dense or hybrid retrieval quality

No runtime authority, memory promotion, Layer-3 mutation, or online LLM call
occurs in this test.
