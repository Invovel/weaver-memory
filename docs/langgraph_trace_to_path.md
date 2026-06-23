# LangGraph And Trace-To-Path

## Status

This document describes the preferred **v0.8 direction**. The minimal
trace-to-candidate-path primitive has landed; full LangGraph execution substrate
integration is still future work.

It explains how MemoryWeaver can borrow:

- `LangGraph` as an orchestration substrate
- `LOOP Skill Engine` style trace capture and replay intuition

without collapsing into a generic workflow runtime or a simple trajectory
recorder.

## Core Position

The recommended combination is:

```text
LangGraph substrate
  + trace capture
  + candidate path extraction
  + evidence gate
  + guarded replay
  + rollback / evolution
```

Short version:

> LangGraph runs the workflow. MemoryWeaver decides what verified experience may
> become a reusable runtime path.

## Why Not Just Use LOOP

`LOOP Skill Engine` is a strong reference for:

- recording a successful first-run trajectory
- extracting a reusable skill template
- replaying that template deterministically

Reference:

- [Good to Go: The LOOP Skill Engine](https://arxiv.org/abs/2605.14237)

That idea is close to MemoryWeaver, but not sufficient for this project.

MemoryWeaver must additionally answer:

- Which trajectories are trustworthy enough to reuse?
- Which failed trajectories should become negative memory?
- When should replay be blocked, downgraded, or challenged?
- How should conflict evidence trigger rollback or revocation?

So the target is not:

```text
record successful path -> replay it
```

The target is:

```text
record trajectory -> extract candidate path -> verify with evidence ->
promote conditionally -> reuse under guard -> rollback on conflict
```

## Layered Design

### 1. Trace Capture

Every run should produce a structured runtime trace rather than only a verbal
summary.

The trace should prioritize verifiable events:

- tool arguments
- tool outputs
- test results
- terminal errors
- user corrections
- file diffs
- benchmark deltas

This trace is a candidate-generation input, not verified memory by itself.

### 2. Candidate Path Extraction

A successful or partially successful trace can be converted into a
`CandidatePath`.

A failed trace can produce:

- negative memory
- avoid rules
- rollback triggers

This is the key upgrade from "memory item" to "runtime path."

### 3. Evidence Gate

Promotion must stay evidence-gated.

Typical promotion support:

- repeated successful validation
- tool-result evidence
- passing tests
- valid diffs
- improved benchmark score
- no open contradiction
- acceptable regression rate

Model confidence is not promotion authority.

### 4. Replay Modes

MemoryWeaver should not treat every reusable path as a blind deterministic
script.

Recommended modes:

| Mode | Purpose | Typical use |
| --- | --- | --- |
| `deterministic` | replay fixed tool sequence | periodic, stable workflows |
| `guarded` | replay with validation checkpoints | coding tasks, benchmark debug |
| `advisory` | path acts as policy guidance only | open-ended research or planning |

This is more expressive than a branch-free replay-only system.

### 5. Rollback And Evolution

If reuse begins to fail, MemoryWeaver should:

- challenge the path
- downgrade or quarantine it
- record conflict evidence
- route to fallback
- trigger rollback or re-learning

This is a core contribution, not a cleanup step.

## Why LangGraph Fits

LangGraph is a good substrate because it already provides:

- thread state
- checkpoint / resume
- interrupts
- graph-structured control flow
- durable execution patterns

MemoryWeaver should sit **above** that substrate.

LangGraph should not define:

- verified memory
- promotion precision
- contradiction handling
- rollback authority

## Mapping To MemoryWeaver

The preferred mapping is:

| Concern | LangGraph role | MemoryWeaver role |
| --- | --- | --- |
| Workflow execution | graph nodes, edges, thread state | n/a |
| Checkpoint / resume | substrate persistence | evidence-aware recovery policy |
| Human-in-the-loop | interrupt / resume | approval semantics, authority boundary |
| Trace capture | state snapshots, node outputs | evidence and trajectory recording |
| Candidate path extraction | optional node | path-specific extraction logic |
| Promotion | not defined by substrate | hard-evidence gate |
| Replay | graph execution path | deterministic / guarded / advisory semantics |
| Rollback | control-flow support | challenge, revocation, conflict response |

## Suggested v0.8 Shape

Preferred v0.8 path:

1. Keep current `HarnessRuntime` semantics.
2. Use `RuntimeTrace`, `RuntimeTraceRecorder`, and `RuntimeTraceStore` for
   structured run capture.
3. Use `extract_candidate_path_from_trace` / `trace_to_candidate_path` to turn a
   trace into `TracePathCandidate`.
4. Move the execution loop onto a LangGraph-style substrate.
5. Keep `HardEvidence`, `RuntimePathSpec`, `ActionGate`, and rollback policy in
   MemoryWeaver.

Current landed boundary:

- `RuntimeTraceRecorder` records tool results, statuses, latency, token cost,
  event ids, and synced trace metrics.
- `TracePathCandidate` contains a `RuntimePathSpec`, hard evidence, rejected bad
  evidence, and trace metrics.
- `extract_candidate_path_from_trace` filters invalid actions out of
  `action_policy`, keeps them as blocked targets / rejected evidence, and maps
  tests, diffs, benchmark deltas, repeated validation, conflicts, time decay,
  and rollback records into `HardEvidence`.
- `HarnessRuntime.register_candidate` admits a trace-derived candidate into the
  runtime registry, records initial hard evidence, audits rejected bad evidence,
  and can optionally treat rejected evidence as an explicit challenge.
- `HarnessRuntime.guarded_replay` executes path policy steps under tool-gateway
  control, records task-scoped tool evidence, and falls back when rollback is
  already recommended.
- Promotion is still performed by `HarnessRuntime.assess` / `record_trial`, not
  by the trace extractor.

Important safety boundary:

- Rejected bad evidence is audit material by default. It does not pollute the
  candidate's positive promotion assessment unless the caller explicitly passes
  `challenge_with_rejected=True`.

## Minimal Loop-Like Closure

The first useful closed loop is:

```text
run task
-> record trace
-> extract candidate path
-> attempt guarded replay on similar task
-> promote after repeated validated reuse
-> rollback or downgrade on conflict
```

This is the right bridge from today's runtime-path fixture toward a stronger
coding-agent benchmark line.

## Recommended First Task Domain

The best first domain remains:

- coding agent debugging
- benchmark agent failure governance
- terminal / tool-oriented tasks

because the evidence is naturally hard:

- exit codes
- pass / fail
- diff validity
- logs
- benchmark scores

## Canonical Summary

Use this wording consistently:

> LOOP focuses on recording and replaying successful trajectories. MemoryWeaver
> extends that idea with evidence-gated promotion, negative memory, guarded
> replay, contradiction handling, and rollback.
