# External Reference Mapping

This note maps external systems and papers to the specific MemoryWeaver layers
they can inform.

The goal is not to relabel MemoryWeaver as another orchestration or memory
framework. The goal is to borrow the right substrate while keeping
MemoryWeaver's core claim clear:

> MemoryWeaver is an evidence-governed runtime path promotion layer.

## Core Boundary

- `LangGraph` can run workflows.
- `MemoryWeaver` decides what verified experience is safe to promote, reuse,
  challenge, or revoke.
- `HardEvidence` remains the promotion authority.
- `rollback` remains the anti-contamination mechanism.

## Reference Map

| Reference | Borrow | Do not borrow | MemoryWeaver layer |
| --- | --- | --- | --- |
| LangGraph | Durable execution, thread state, checkpoint, resume, interrupt, subgraph orchestration | Its runtime state or persistence as a substitute for verified memory or promotion policy | Execution substrate under `HarnessRuntime` |
| LOOP Skill Engine | First-run trajectory recording, template extraction, deterministic replay intuition | Treating successful replay alone as sufficient promotion authority | Trace-to-path and replay intuition under evidence gate |
| OPA / Rego | Deterministic policy boundary, separating decision from enforcement | Treating static policy as a replacement for experience promotion | `ActionGate`, source gate, authority policy |
| Temporal / Saga | Compensation, audit trail, replay, rollback-inspired workflow structure | Using workflow rollback as a substitute for evidence-driven path revocation | Durable recovery and rollback engineering |
| Voyager | Reusable executable skills and environment-validated reuse | Treating generated skills as trustworthy without source gate and contradiction handling | Runtime path / skill reuse intuition |
| SkillOpt | Trajectory-driven skill text optimization, bounded edits, validation-gated best-skill selection | Treating an optimized skill document as verified runtime authority | Candidate procedure generator feeding Harness-reviewed path promotion |
| Claude Code / Claude Agent SDK option prompts | Bounded option presentation before action, user selection as control signal, permissions and hooks as audit points | Letting selected options bypass ActionGate or evidence gates | Option-guided `ActionProposal` entrypoint |
| DeepSeek context caching / predictive input completion | Prefix reuse, cache-hit intuition, keep matched continuations and discard misses | Treating synthetic continuations as facts or verified memory | Predictive context compression and route hints only |
| CRITIC | Tool-interactive critique and external feedback as a stronger signal than self-confidence | Letting tool feedback bypass MemoryWeaver policy and provenance checks | Hard evidence and post-action validation |
| Reflexion | Failure-driven iteration and memory as a useful baseline or ablation | Using model-written reflection as the default promotion authority | Baseline / negative comparison arm |
| SWE-bench | Test-pass/fail, diff validity, regression surface for coding-agent tasks | Assuming benchmark success alone proves safe path promotion | Coding-agent hard evidence and task family design |
| tau-bench | `pass^k`, repeated validation, dynamic task reliability framing | Treating pass-rate alone as promotion precision | Reliability and repetition metrics |
| AgentDojo / ToolEmu | Tool-risk scenarios, action safety evaluation, adversarial tool-use framing | Replacing long-horizon promotion logic with one-step tool safety only | Tool-risk and runtime safety evaluation |

## Recommended Borrowing Strategy

### 1. Substrate

Use `LangGraph`-style orchestration ideas for:

- `thread_id`
- checkpoint / resume
- `interrupt`
- subgraph composition

Do not let the orchestration substrate define:

- verified memory
- promotion precision
- contradiction resolution
- rollback authority

### 2. Policy

Use `OPA`-style policy separation for:

- source authority
- high-risk action restrictions
- deterministic allow / block checks

Do not confuse static policy with:

- verified experience
- reusable execution path quality

### 3. Evidence

Use `CRITIC`, `SWE-bench`, and `tau-bench` style signals for:

- tool result evidence
- test result evidence
- diff validity
- benchmark delta
- repeated validation

Do not let model confidence, style, or verbal explanation count as default
promotion evidence.

### 4. Research Positioning

Use `Voyager` and `Reflexion` as contrast:

- `Voyager` shows reusable skill accumulation.
- `Reflexion` shows memory through linguistic reflection.
- `SkillOpt` shows that skill procedures themselves can be optimized from
  trajectories.
- Option-guided assistants show that user-facing choices can reduce ambiguous
  autonomy before action.
- Predictive completion shows that matched continuations can be used to reduce
  context noise.

MemoryWeaver's distinction is stricter:

- evidence-gated promotion
- contradiction-aware reuse
- negative memory
- rollback against contamination
- optimized procedures remain candidate inputs until Harness review grants
  runtime authority
- options and predictions remain candidate route signals until user feedback or
  hard evidence supports them

## Canonical Positioning

Use these sentences consistently:

- `MemoryWeaver is not a generic long-term memory framework.`
- `MemoryWeaver is an evidence-governed runtime path promotion layer built above an orchestration substrate such as LangGraph.`
- `Its purpose is to decide what verified experience may be promoted, reused, challenged, or revoked.`

Short version:

> LangGraph runs the workflow; MemoryWeaver governs verified experience reuse.

For a shorter paper-friendly comparison table, see
[related_work_positioning.md](./related_work_positioning.md).

For the preferred LangGraph + trace-to-path combination, see
[langgraph_trace_to_path.md](./langgraph_trace_to_path.md).
