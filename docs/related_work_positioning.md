# Related Work Positioning

This note is a paper-friendly companion to
[reference_mapping.md](./reference_mapping.md).

Its purpose is to make the positioning concise:

- what existing systems already do well
- what MemoryWeaver does not claim
- what MemoryWeaver adds

## One-Sentence Positioning

> MemoryWeaver is an evidence-governed runtime path promotion layer that sits
> above an orchestration substrate and decides what verified experience may be
> promoted, reused, challenged, or revoked.

## Comparison Table

| Line of work | What it already provides | What it usually does not provide | MemoryWeaver addition |
| --- | --- | --- | --- |
| Exact answer cache | Near-zero lookup cost for repeated exact keys | Paraphrase transfer, evidence-version invalidation, challenge and rollback | Reusable path rather than stored answer, with explicit invalidation authority |
| Workflow / orchestration runtimes | Durable execution, checkpointing, interrupts, resume, thread state | Evidence-governed promotion, contradiction-aware reuse, memory-induced error control | Runtime-path governance above the substrate |
| Deterministic replay / trajectory skill engines | Successful-trajectory recording, replay templates, token and latency savings on repeated tasks | Evidence gate, negative memory, rollback authority, conflict-triggered revocation | Guarded promotion and replay of reusable runtime paths |
| Policy engines | Deterministic allow / deny rules, separation of decision and enforcement | Experience lifecycle, path quality, rollback based on empirical conflict | Evidence-linked authority for action and promotion |
| Tool-use safety benchmarks | Tool-risk scenarios, misuse detection, adversarial or unsafe action evaluation | Long-horizon promotion and reuse of corrected execution paths | Failure governance across repeated tasks |
| Reflection / verbal-memory agents | Iterative self-correction, reflection, episodic summaries | Hard-evidence promotion, provenance-gated reuse, rollback against contamination | External-evidence-first path promotion |
| Skill-library agents | Reusable procedures or skills discovered from prior success | Strong source gate, contradiction management, negative memory, revocation | Reusable runtime paths with challenge and rollback |
| Skill-document optimizers such as SkillOpt | Trajectory-driven edits to reusable skill text and validation-gated best-skill selection | Runtime authority, source-gated activation, stale-skill invalidation, rollback after deployment | Treat optimized skills as candidate procedures that still require Harness evidence gates |
| Coding-agent benchmarks | Hard signals such as test pass/fail and valid diffs | A mechanism for deciding when experience should become reusable policy | Promotion evidence and reuse governance |

## Positioning by Reference Family

### Answer cache

Strong at:

- exact-key lookup
- avoiding repeated generation for unchanged requests

MemoryWeaver does **not** compete on zero-cost exact cache hits.

MemoryWeaver adds:

- transfer of a retrieval path across semantic paraphrases
- evidence-version and scope checks before reuse
- invalidation, fallback, and rollback when the old path becomes stale

The controlled Retrieval Wear experiment makes the trade-off explicit:
ungoverned cache/path reuse can inspect fewer candidates, but both produce
stale reuse rate `1.0` after evidence drift. The MemoryWeaver arm keeps
evidence hit rate `1.0` and stale reuse rate `0.0` while inspecting `32.7%`
fewer candidates than repeated RAG.

### LangGraph / durable orchestration

Strong at:

- long-running execution
- checkpoint / resume
- human-in-the-loop interrupts
- graph-structured workflow control

MemoryWeaver does **not** compete here.

MemoryWeaver adds:

- hard-evidence promotion criteria
- contradiction-aware path challenge
- rollback against error propagation

### LOOP / trajectory replay engines

Strong at:

- recording successful first-run trajectories
- extracting reusable replay templates
- deterministic replay for recurring tasks

MemoryWeaver does **not** stop at replay.

MemoryWeaver adds:

- promotion only after evidence gating
- negative memory from failures
- guarded replay rather than blind replay
- rollback and revocation on conflict

### OPA / policy engines

Strong at:

- deterministic policy checks
- explicit authority boundaries
- enforcement decoupled from business logic

MemoryWeaver does **not** claim to replace policy engines.

MemoryWeaver adds:

- empirical experience quality control
- task-family-specific reusable path promotion
- revocation based on conflict and regression evidence

### Reflexion / reflective memory

Strong at:

- iterative improvement through reflection
- memory from prior failures or successes

MemoryWeaver differs in one central way:

- reflection is not promotion authority

MemoryWeaver adds:

- external evidence as the default promotion signal
- rollback when reused experience becomes unsafe

### Voyager / reusable skills

Strong at:

- collecting and reusing executable skills
- success-driven capability accumulation

MemoryWeaver adds:

- source gate
- contradiction handling
- negative memory
- rollback and revocation

### SkillOpt / skill-document optimization

Strong at:

- optimizing natural-language skill procedures from trajectories
- bounding edits to reusable skill text
- selecting deployable skill artifacts through validation

MemoryWeaver should not claim this as its primary contribution. A SkillOpt-style
procedure can be an excellent candidate input, but it is not runtime authority.

MemoryWeaver adds:

- scope and source checks before activation
- evidence-linked path promotion rather than text-quality promotion
- stale-procedure invalidation when evidence versions drift
- rollback and revocation after a deployed procedure causes conflicts or
  regressions

In short: SkillOpt trains "how to do it"; MemoryWeaver governs "when this
procedure may be trusted in the loop."

### SWE-bench / tau-bench style evaluation

Strong at:

- hard signals
- repeated-run reliability
- realistic task-family framing

MemoryWeaver uses these as evidence and evaluation structure, not as a
substitute for governance logic.

## What MemoryWeaver Does Not Claim

- It is not a generic long-term memory framework.
- It is not a generic RAG wrapper.
- It is not an orchestration runtime by itself.
- It is not a skill-document optimizer.
- It does not treat model confidence as default promotion evidence.
- It does not claim benchmark success alone is enough for safe reuse.

## What MemoryWeaver Claims

- Verified experience can be promoted into reusable runtime paths.
- Promotion should be evidence-gated rather than confidence-gated.
- Reuse should remain challengeable and revocable.
- Rollback is part of the core contribution, not a footnote.
- Optimized skills and generated procedures should remain candidates until
  Harness gates grant runtime authority.
- The main value is reducing repeated failure without increasing
  memory-induced error propagation.

## Canonical Summary

Use this concise formulation when needed:

> LangGraph runs the workflow; MemoryWeaver governs verified experience reuse.
