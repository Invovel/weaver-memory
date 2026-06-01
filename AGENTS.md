# MemoryWeaver Agent Guide

## Project Positioning

MemoryWeaver is a feedback-calibrated lifecycle harness for long-lived AI
agents. It is not a generic RAG wrapper and it is not an LLM supervisor.

Core principle:

> **LLM proposes, Harness judges.**

## Non-Negotiable Rules

- LLM output must never become verified memory directly.
- `assistant` source defaults to `ambiguous`.
- HyDE output is `synthetic`; it is a retrieval aid, not factual memory.
- Negative memory is avoidance memory, not garbage.
- Layer 3 stores patterns and procedural skills, not raw RAG chunks.
- RAG retrieves evidence.
- GBrain organizes relationships.
- MemoryWeaver judges, routes, promotes, demotes, blocks, and recovers.
- High-risk side effects require explicit authorization and auditability.

## Lifecycle Intervention Points

MemoryWeaver should intervene at explicit lifecycle points:

| Stage | Target responsibility |
| --- | --- |
| Before interaction | Load `EnvironmentContract`, tool constraints, source authority, and retrieval policy |
| Task conditioning | Retrieve Layer 3 procedural skills, GBrain context, and RAG evidence |
| Before execution | Validate structured `ActionProposal` through `ActionGate` |
| After feedback | Detect repetition, stagnation, budget exhaustion, and recovery needs through `TrajectoryRegulator` |
| After task outcome | Record candidate memory, bad cases, utility, and regression fixtures |

Do not implement a single opaque LLM supervisor. Prefer deterministic gates and
small auditable policies. LLMs may propose contract updates, skills, root-cause
hypotheses, and recovery plans, but the Harness validates them.

## Harness Authority Levels

| Level | Authority | Examples |
| --- | --- | --- |
| L0 | Observe | Record events and tool feedback |
| L1 | Annotate | Attach source, freshness, risk, warning |
| L2 | Retrieve / Recommend | Supply evidence, graph context, and procedural skill |
| L3 | Validate / Block | Reject malformed, unauthorized, dangerous, or contradictory actions |
| L4 | Recover / Force Safe Path | Stop loops, compact context, require user confirmation, or route to a verified fallback |

The Harness may restrict an action. It must not silently make high-risk user
decisions.

## Current Prototype Boundary

The current Python package is a Sprint 0 prototype. It implements schema, JSON
storage, scoring, extraction, routing, verified retrieval primitives, and
contradiction resolution. It does not yet implement the complete lifecycle
harness.

Known P0 gaps are tracked in
[`docs/risk_assessment_and_benchmark.md`](docs/risk_assessment_and_benchmark.md).

## Development Order

1. Close existing source-gate, Router, heat, CLI, and Chinese retrieval gaps.
2. Add policy types and deterministic lifecycle contracts.
3. Add `ActionProposal`, `ActionGate`, and `TrajectoryRegulator`.
4. Add checkpoint recovery and bad-case regression fixtures.
5. Add minimal GBrain tag projection and point retrieval.
6. Add RAG evidence retrieval incrementally.
7. Add offline maintenance models only behind evaluation, shadow, canary, and rollback.

## Verification

Run:

```powershell
python -m pytest -q
python .\benchmarks\prototype_baseline.py
python .\scripts\generate_architecture_diagram.py
```

Do not claim a planned component exists until implementation and tests land.

## Design Documents

- [`docs/architecture.md`](docs/architecture.md)
- [`docs/life_harness_notes.md`](docs/life_harness_notes.md)
- [`docs/development_plan.md`](docs/development_plan.md)
- [`docs/risk_assessment_and_benchmark.md`](docs/risk_assessment_and_benchmark.md)
- [`docs/testing_resilience_strategy.md`](docs/testing_resilience_strategy.md)
