# Retrieval Safety Filter v0.5.4b

This validation separates traditional relevance retrieval from MemoryWeaver
runtime eligibility.

The test asks:

```text
If SQLite FTS5 retrieves relevant but unsafe text, do MemoryWeaver safety gates
still prevent that text from becoming runtime-authoritative context?
```

It uses the same 50 dialogue-card queries and 341 ContextCapsules as the v0.5.4
retrieval validations. The query text is intentionally adversarial: it includes
the user query, expected marker, required evidence, and known bad actions so
that FTS5 can retrieve assistant traps and stale/noisy context.

## Arms

```text
A. fts5_only
   SQLite FTS5 over all capsules.

B. source_gate
   FTS5 results filtered by source trust.

C. source_freshness_gate
   Source gate plus stale/freshness-conflict filtering.

D. source_freshness_marker_gate
   Source + freshness + marker/card eligibility.
```

This is not a speed benchmark. v0.5.4a already measures FTS5 frontend candidate
reduction. v0.5.4b measures whether safety gates remain independent after a
traditional keyword retriever has already found textually relevant capsules.

## Results

```json
{
  "query_count": 50,
  "capsule_count": 341,
  "fts5_only_untrusted_top10_leak_count": 40,
  "source_gate_untrusted_top10_leak_count": 0,
  "full_gate_untrusted_top10_leak_count": 0,
  "fts5_only_assistant_trap_top10_leak_count": 35,
  "full_gate_assistant_trap_top10_leak_count": 0,
  "fts5_only_stale_top10_leak_count": 27,
  "full_gate_stale_top10_leak_count": 0,
  "fts5_only_required_evidence_hit_rate": 1.0,
  "full_gate_required_evidence_hit_rate": 0.98,
  "fts5_only_known_bad_warning_hit_rate": 1.0,
  "full_gate_known_bad_warning_hit_rate": 0.98,
  "fts5_only_average_candidate_count": 219.94,
  "full_gate_average_candidate_count": 153.3,
  "runtime_authority_violation_count": 0,
  "online_llm_call_count": 0,
  "memory_promotion_count": 0,
  "layer3_mutation_count": 0
}
```

## Interpretation

FTS5-only retrieval is correctly relevant but not runtime-safe. It returns
assistant traps, stale conflict candidates, and other untrusted capsules in the
top-10. After MemoryWeaver safety gates, untrusted top-10 leaks, assistant trap
leaks, stale runtime leaks, and runtime-authority violations are all zero.

The full gate keeps nearly all useful context:

```text
required evidence hit rate: 1.00 -> 0.98
known bad warning hit rate: 1.00 -> 0.98
```

The small drop is acceptable for this stage because v0.5.4b is validating a
conservative runtime boundary, not maximizing recall.

## Claim

MemoryWeaver can use traditional keyword retrieval as a frontend, but keyword
relevance is not sufficient for runtime authority. Source, freshness, and marker
eligibility gates are still required after FTS5/BM25-style retrieval.

## Non-Claims

This validation does not prove:

- end-to-end agent task success improvement
- superiority over RAG over logs in a live task loop
- dense retrieval performance
- production latency
- Layer-3 Pattern improvement

No online LLM calls, memory promotion, or Layer-3 mutation occur in this test.
