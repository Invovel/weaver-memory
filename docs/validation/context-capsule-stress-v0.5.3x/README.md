# ContextCapsule Stress v0.5.3.x

## Purpose

This validation extends the fixed ContextCapsule v0.5.3 fixture with
dialogue-derived raw spans from the Runbook Marker v0.5 golden cards.

It tests whether multi-turn user corrections, assistant hypotheses, tool
outputs, terminal observations, queries, and trace records can enter the
RAW-to-capsule layer without changing trust or losing reversible raw evidence.

## Command

```powershell
python .\benchmarks\context_capsule_stress_validation.py `
  --output-dir .\docs\validation\context-capsule-stress-v0.5.3x
```

## Gates

```text
raw_retrieval_success_rate = 1.0
trust_inheritance_violation_count = 0
raw_ref_missing_count = 0
capsule_promoted_memory_count = 0
dialogue_card_count >= 50
dialogue_raw_span_count >= 300
combined_raw_span_count >= 340
assistant_capsules_remain_assistant = true
```

## Observed Metrics

```json
{
  "raw_span_count": 341,
  "capsule_count": 341,
  "content_type_counts": {
    "terminal_log": 61,
    "tool_json": 13,
    "conversation_turn": 207,
    "code_patch": 5,
    "trace_record": 55
  },
  "tag_recall_at_k": 1.0,
  "raw_retrieval_success_rate": 1.0,
  "time_filter_accuracy": 1.0,
  "marker_context_hit_rate": 1.0,
  "trust_inheritance_violation_count": 0,
  "raw_ref_missing_count": 0,
  "capsule_promoted_memory_count": 0,
  "tag_miss_count": 0,
  "capsule_ref_error_count": 0,
  "card_count": 50,
  "dialogue_raw_span_count": 301,
  "combined_raw_span_count": 341,
  "assistant_capsule_count": 51
}
```

Note: `average_compression_ratio` is not a hard gate in this stress fixture
because many dialogue events are already short structured annotations. This
validation gates safety, indexing, and raw recovery; later trajectory runs
should measure real context-token reduction on full transcripts and logs.

## Generated Artifacts

```text
raw_results.json
metrics_summary.json
dialogue_raw_spans.jsonl
capsules.jsonl
marker_context_results.jsonl
```

## Interpretation

This is still a context-substrate validation, not a task-success benchmark.
It proves that dialogue-derived runtime traces can be compressed and indexed
without promoting memory, mutating Layer 3, or increasing assistant-sourced
trust.
