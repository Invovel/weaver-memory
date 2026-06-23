# ContextCapsule / TagTimeIndex v0.5.3 Test Plan

## Purpose

This validation prepares the v0.5.3 RAW-to-capsule compression layer inspired by
headroom-style reversible context compression.

The goal is not to prove end-to-end task success. The goal is to verify that
MemoryWeaver can compress raw runtime context into short, tag-time indexed
capsules while preserving source-gated trust boundaries and reversible raw
evidence recovery.

## Architecture Position

ContextCapsule sits between RAW events and Layer 1 memory:

```text
RAW Event / RawSpan
  full terminal log, tool JSON, code patch, conversation turn, trace record
        ↓
ContentRouter
  rule-based content-type compression
        ↓
ContextCapsule
  summary + tags + timestamp + raw_ref_id
        ↓
Layer 1 Candidate Memory
  still source-gated and policy-controlled
```

It is not a memory layer and not an evidence replacement.

## Absorbed Design Ideas

| Source idea | MemoryWeaver adaptation |
| --- | --- |
| ContentRouter | Route content by type before compression. |
| CCR reversible compression | Keep RawSpan and require every capsule to point back through `raw_ref_id`. |
| Tag-Time index | Combine `tag -> capsule_ids` and `time_bucket -> capsule_ids`. |
| MarkerEvidenceContext | Let HarnessMarker request capsules by required tags, time window, source, and content type. |

## Deferred Ideas

| Deferred | Reason |
| --- | --- |
| Cross-agent memory | Violates current scope and source boundary assumptions. |
| ML/semantic compression | v0.5.3 must remain deterministic, inspectable, and zero-dependency. |
| Cache alignment | Multi-agent cache coherence is not needed before a later runtime demo. |

## Planned Files

```text
memoryweaver/
├── context_schema.py       # RawSpan, ContextCapsule, MarkerEvidenceContext
├── context_store.py        # RawSpanStore, ContextCapsuleStore
├── content_router.py       # rule-based compressors
├── tag_time_index.py       # tag/time lookup
└── marker_context.py       # marker -> capsule retrieval helper
```

Workspace files:

```text
.memoryweaver/
├── raw_spans.json
├── context_capsules.json
├── tag_time_index.json
└── marker_evidence_contexts.json
```

## Test Fixture Shape

The initial fixture should contain 30-50 raw spans:

| Content type | Count | Required behavior |
| --- | ---: | --- |
| `terminal_log` | 10 | Preserve command, exit code, stderr head/tail, timestamp. |
| `tool_json` | 10 | Preserve key paths, `status`, `error`, `id`, `code`, timestamp. |
| `conversation_turn` | 10 | Preserve speaker, intent, correction, decision, timestamp. |
| `code_patch` | 5 | Preserve file path, symbols, changed lines, timestamp. |
| `trace_record` | 5 | Preserve marker, route, required evidence, suppressed action. |

Each fixture row should include:

```json
{
  "raw_span_id": "raw_001",
  "content_type": "terminal_log",
  "source": "terminal",
  "timestamp": "2026-06-05T10:00:00Z",
  "content": "...full raw content...",
  "metadata": {
    "command": "codex --version",
    "exit_code": 0
  },
  "expected_capsule": {
    "required_tags": ["codex", "terminal"],
    "must_include": ["command", "exit=0"],
    "must_preserve_source": "terminal",
    "must_preserve_timestamp": true,
    "raw_retrievable": true
  }
}
```

## Required Metrics

```text
compression_ratio
tag_recall@k
raw_retrieval_success_rate
time_filter_accuracy
marker_context_hit_rate
trust_inheritance_violation_count
raw_ref_missing_count
capsule_promoted_memory_count
```

Completion target:

```text
raw_retrieval_success_rate = 1.0
trust_inheritance_violation_count = 0
raw_ref_missing_count = 0
capsule_promoted_memory_count = 0
marker_context_hit_rate >= 0.8
```

## Safety Invariants

These are hard gates:

```text
Context compression cannot increase trust.
ContextCapsule cannot promote memory.
Compressed summaries cannot replace raw evidence.
Raw evidence must remain recoverable via raw_ref_id.
Capsule source inherits from RawSpan.
Capsule timestamp inherits from RawSpan.
Assistant raw span compressed to capsule remains assistant-sourced.
```

## Commands

Full fixture validation:

```powershell
python .\benchmarks\context_capsule_validation.py `
  --fixture .\docs\validation\context-capsule-v0.5.3\raw_spans_fixture.jsonl `
  --output-dir .\docs\validation\context-capsule-v0.5.3
```

CLI smoke path:

```powershell
python -m memoryweaver.cli context add --type terminal_log --source terminal --text "..." --json
python -m memoryweaver.cli context search --tag codex --since 2026-06-01
python -m memoryweaver.cli context raw raw_001
python -m memoryweaver.cli context validate --root .memoryweaver-context-smoke --json
```

CLI status: implemented and covered by `tests/test_cli.py`.

## Relationship To v0.5 / v0.6

v0.5 proves marker counterfactual trace advantage.

v0.5.3 prepares the context substrate that lets active markers retrieve compact
evidence by tag/time before falling back to raw logs.

v0.6 should replace manual counterfactuals with real agent trajectories and use
ContextCapsule metrics to report context cost reduction.

## Full Fixture Validation Result

Status: full fixture validation complete.

Command:

```powershell
python .\benchmarks\context_capsule_validation.py `
  --fixture .\docs\validation\context-capsule-v0.5.3\raw_spans_fixture.jsonl `
  --output-dir .\docs\validation\context-capsule-v0.5.3 `
  --require-full-fixture
```

Observed metrics:

```json
{
  "raw_span_count": 40,
  "capsule_count": 40,
  "content_type_counts": {
    "terminal_log": 10,
    "tool_json": 10,
    "conversation_turn": 10,
    "code_patch": 5,
    "trace_record": 5
  },
  "tag_recall_at_k": 1.0,
  "raw_retrieval_success_rate": 1.0,
  "time_filter_accuracy": 1.0,
  "marker_context_hit_rate": 1.0,
  "trust_inheritance_violation_count": 0,
  "raw_ref_missing_count": 0,
  "capsule_promoted_memory_count": 0,
  "tag_miss_count": 0
}
```

Generated artifacts:

```text
raw_results.json
metrics_summary.json
capsules.jsonl
marker_context_results.jsonl
```

CLI smoke also writes an isolated local workspace:

```text
.memoryweaver-context-cli-smoke/
```

Scope note: this validation proves the deterministic RAW-to-capsule substrate
over the planned 10/10/10/5/5 content-type distribution. It still does not
prove task success, token reduction in a real agent loop, or active marker
intervention. Those remain v0.5.2/v0.6 responsibilities.

## Smoke Validation Result

Status: executable smoke validation complete.

Command:

```powershell
python .\benchmarks\context_capsule_validation.py `
  --fixture .\docs\validation\context-capsule-v0.5.3\raw_spans_fixture.example.jsonl `
  --output-dir .\docs\validation\context-capsule-v0.5.3
```

Observed metrics:

```json
{
  "raw_span_count": 3,
  "capsule_count": 3,
  "tag_recall_at_k": 1.0,
  "raw_retrieval_success_rate": 1.0,
  "time_filter_accuracy": 1.0,
  "marker_context_hit_rate": 1.0,
  "trust_inheritance_violation_count": 0,
  "raw_ref_missing_count": 0,
  "capsule_promoted_memory_count": 0
}
```

Scope note: this is a smoke validation over the seed fixture, not the full
30-50 RawSpan pressure fixture. It proves that the substrate is executable and
that the hard trust gates are wired. It is superseded by the full fixture
validation above.
