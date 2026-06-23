# MemoryWeaver

[中文版 (Chinese Version)](README_ZH.md) | [GitHub](https://github.com/Invovel/weaver-memory)

**Feedback-Calibrated Path Promotion Harness for Long-Lived AI Agents**

**LLM proposes. Harness judges.**

**Core claim:** Layer-3 path promotion turns verified experience into reusable execution paths.

MemoryWeaver is an experimental runtime path-evolution harness for AI agents. It turns conversations, terminal outputs, tool results, user corrections, and task outcomes into verified experience, then promotes that experience through Layer 3 into reusable execution paths that can be trialed, stabilized, challenged, rolled back, and replaced.

In the current direction, a Layer-3 runtime path is not a prompt fragment. It has the shape:

```text
condition -> action policy -> validation gate -> fallback -> rollback rule
```

Promotion is gated by external evidence: tool results, passing tests, explicit user corrections, expected file diffs, benchmark-score deltas, repeated sibling-task validation, counterexamples, conflicts, time decay, and rollback records. Model confidence is not promotion evidence by default.

Unlike traditional RAG systems, MemoryWeaver uses **source-gated polarity** and **contradiction detection** to prevent LLM fabrications from polluting the memory store. Those governance layers are not the end goal by themselves; they exist so Layer 3 can keep selecting the latest, most suitable, and most reliable path for the next task.

Unlike traditional RAG systems that only retrieve documents, MemoryWeaver focuses on **feedback-aware memory evolution**:

* What worked?
* What failed?
* What was neutral context?
* What is still uncertain?
* Which memory patterns should be promoted, deprecated, linked, or reused?
* Which tags are useful for a specific LLM or agent workflow?

The goal is to help AI agents move from:

```text
Ask → Retrieve → Answer
```

to:

```text
Act → Observe → Learn → Remember → Reuse → Improve
```

---

## Why MemoryWeaver?

Most RAG systems treat memory as static knowledge.

MemoryWeaver treats experience as a path-evolution system.

It is designed for long-running agents that need to remember:

* Project setup
* Terminal errors
* Successful fixes
* Failed attempts
* User corrections
* User preferences
* Tool usage history
* Model-specific memory formats
* Outdated or invalid assumptions
* Reusable diagnostic patterns
* Reusable execution paths

This is especially useful for:

* Coding agents
* Vibe coding workflows
* AI developer assistants
* Technical support agents
* Internal knowledge agents
* Research assistants
* Long-term personal AI assistants

---

## Core Idea

MemoryWeaver uses a layered memory architecture.

```text
User / Tool / Terminal Event
        ↓
RAW Event / RawSpan
        ↓
ContextCapsule + TagTimeIndex (validated v0.5.3)
        ↓
Harness Pre-Tagging
        ↓
Layer 1: Candidate Memory
        ↓
Layer 2: Verified Experience
        ↓
Path Candidate Pool + Pattern Composition
        ↓
Layer 3: Provisional Execution Path
        ↓
Runtime Trial
        ↓
Stable Path / Challenged Path / Rollback / Archive
```

The system is designed as a feedback loop:

```text
Observe → Verify → Promote Path → Trial → Reuse / Rollback → Improve
```

---

## Layer-3 Path Promotion

Layer 1 and Layer 2 provide material.

Layer 3 is the engine.

MemoryWeaver's key question is not only whether a memory item is safe to store.
It is whether multiple verified experiences can be promoted into a better
execution path for the next task.

The Layer-3 lifecycle is:

```text
Layer 2 Verified Experience
        ↓
Provisional Pattern / Path Candidate
        ↓
Runtime Trial
        ↓
Stable Path
   or Challenged / Rolled Back / Archived Path
```

The current prototype already stores explicit Layer-3 path signals such as:

* `success_path`
* `failed_path`
* `validation_task_runs`
* `path_fitness_score`
* `trial_count`
* `success_count`
* `failure_count`
* `false_trigger_count`

This is the main distinction from a generic memory layer, static skill pack, or
plain graph: MemoryWeaver is trying to evolve better paths, not just remember
more facts.

---

## ContextCapsule / TagTimeIndex (Validated v0.5.3)

MemoryWeaver absorbs the useful parts of context-compression systems such
as `headroom` as a **RAW-to-Layer-1 compression layer**, not as a replacement
for memory, evidence, or policy.

The validated flow is:

```text
RAW Event
  complete terminal log / tool JSON / code patch / conversation turn
        ↓
ContentRouter
  rule-based content-type compression
        ↓
ContextCapsule
  short summary + tags + timestamp + raw_ref_id
        ↓
Layer 1 Candidate Memory
  generated from capsule summary and tags, still source-gated
```

The four designs to absorb are:

| Design | MemoryWeaver adaptation |
| --- | --- |
| ContentRouter | Route `terminal_log`, `tool_json`, `code_patch`, `conversation_turn`, and `trace_record` to different rule-based compressors. |
| Reversible compression | Store full `RawSpan`; every capsule keeps `raw_ref_id` so raw evidence can be restored. |
| Tag-Time index | Maintain `tag -> capsule_ids` and `time_bucket -> capsule_ids` for fast scoped lookup. |
| MarkerEvidenceContext | Bind HarnessMarker to required tags, time windows, sources, and preferred content types. |

The three designs not absorbed at this stage are:

| Deferred design | Reason |
| --- | --- |
| Cross-agent memory | Current MemoryWeaver scope rules are project/session/source-sensitive; cross-agent sharing would blur trust boundaries. |
| Auto-compression without trust boundary | Compression must inherit `source`, `timestamp`, and trust status from raw input. |
| Cache alignment | Multi-agent cache coherence is out of scope until a later runtime/demo phase. |

Hard safety rules:

```text
Context compression cannot increase trust.
ContextCapsule cannot promote memory.
Compressed summaries cannot replace raw evidence.
Raw evidence must remain recoverable via raw_ref_id.
Capsule source and timestamp inherit from RawSpan unchanged.
```

The v0.5.3 validation measures:

```text
compression_ratio
tag_recall@k
raw_retrieval_success_rate
time_filter_accuracy
marker_context_hit_rate
trust_inheritance_violation_count = 0
raw_ref_missing_count = 0
capsule_promoted_memory_count = 0
```

This means: headroom-style compression reduces context cost; MemoryWeaver still
decides what context is allowed to matter.

---

## Memory Layers

### Layer 1: Candidate Memory

The harness performs initial lightweight tagging.

This layer stores raw memory candidates before they are proven useful.

Examples:

```text
positive?
negative?
neutral?
ambiguous?
```

At this stage, the system does not assume the memory is correct or reusable.

---

### Layer 2: Verified Experience

A memory enters Layer 2 when it has been:

* Retrieved
* Used in a response
* Connected to a task
* Confirmed or corrected by the user
* Verified by a tool or terminal result

Layer 2 separates memory into quality partitions:

```text
positive   → useful or successful signals
negative   → failed paths or wrong assumptions
neutral    → stable context or background facts
ambiguous  → unverified hypotheses
```

---

### Layer 3: Provisional Pattern

Layer 3 stores canonical `Pattern` records, not Layer-3 `MemoryItem`
copies and not raw RAG chunks.

Layer 3 is a **path-promotion layer**. A new Pattern starts as a provisional
execution path, is tested against task outcomes, and may later become
`stable`, `challenged`, `rolled_back`, or `archived`.

A pattern may combine multiple memory signals:

```text
positive + negative + neutral + ambiguous
```

Example:

```text
If Codex CLI is installed successfully in WSL,
but subscription loading still fails,
do not prioritize npm reinstall.
Check authentication, selected organization, or subscription state first.
```

Layer 3 is shared by the harness and retrieval system, but it cannot be
created by the scorer and it cannot be created automatically from RAG
retrieval. Pattern creation goes through `PatternComposer`, and path
promotion goes through explicit trial / promotion / rollback logic.

It helps the agent decide:

* When to use fast mode
* When to use thinking mode
* Which memory to retrieve
* Which assumptions to avoid
* Which execution path to try first
* Which model-specific memory format to use

---

## Memory Polarity

MemoryWeaver classifies memory into four major polarity zones.

### Positive Memory

Useful, successful, or validated knowledge.

Examples:

* A command worked
* A fix solved the issue
* The user confirmed the answer
* A tool result verified the assumption

### Negative Memory

Failed attempts, wrong assumptions, or rejected paths.

Examples:

* The user corrected the assistant
* A command failed
* A proposed fix did not work
* A previous assumption was misleading

Negative memory is not deleted. It becomes **avoidance memory**.

### Neutral Memory

Stable facts or background context.

Examples:

* User uses WSL
* Project uses pnpm
* Agent is working inside a Next.js repository
* User prefers step-by-step explanations

### Ambiguous Memory

Unverified hypotheses.

Examples:

* The issue may be caused by organization selection
* The package version might be incompatible
* The tool may require additional authentication

Ambiguous memory can later become positive, negative, or deprecated.

---

## Harness Role

MemoryWeaver treats the harness as the control layer.

Governance is not the final product.

Governance exists so Layer 3 can keep promoting better execution paths.

The harness is responsible for:

* Detecting memory-worthy events
* Pre-tagging user and tool interactions
* Classifying feedback
* Tracking successful and failed paths
* Scoring memory value
* Routing memory into layers
* Updating heat, confidence, and freshness
* Promoting or deprecating memory
* Selecting fast mode or thinking mode
* Learning which paths are reusable for each LLM or workflow

The LLM reasons.
The tools act.
The memory stores.
The harness coordinates.

MemoryWeaver is evolving from a memory harness into a lifecycle-aware runtime
harness: calibrate environment contracts before interaction, retrieve
procedural skills during task conditioning, validate actions before execution,
and regulate degraded trajectories after feedback. This direction is inspired
by [LIFE-HARNESS](https://arxiv.org/abs/2605.22166); see
[`docs/life_harness_notes.md`](docs/life_harness_notes.md).

---

## Fast Mode vs Thinking Mode

MemoryWeaver supports adaptive inference routing.

```text
New / uncertain / high-risk task
        → Thinking Mode

Similar / validated / low-risk task
        → Fast Mode

Known but possibly outdated task
        → Fast + Verify
```

This allows agents to think deeply once, promote the result into Layer 3, and
reuse the validated execution path later.

---

## GBrain / Graph Memory Integration

MemoryWeaver is designed to work with graph-style memory systems.

Graph memory can:

* Link related tags
* Merge duplicate nodes
* Detect stale knowledge
* Connect people, projects, errors, tools, and outcomes
* Compose second-layer signals into third-layer patterns

Current boundary:

- v0.8 now includes an authority-limited GBrain substrate:
  candidate-bundle ingestion, raw `search`, synthesized `think`, and mind-map
  projection.
- The v0.8 validation line proves candidate graph integration with RAG evidence,
  specialist EvidencePacket routing, and checkpoint/resume while keeping
  `gbrain_authority_granted = false`.
- GBrain remains advisory. It can narrow candidates and preserve relation
  lineage, but it cannot directly promote verified memory or stable Layer-3
  paths.

Example:

```text
WSL
+ Codex CLI
+ npm global install success
+ subscription load failed
+ user already has API key
```

can become:

```text
Codex CLI authentication/subscription diagnostic pattern
```

---

## Suggested Memory Schema

```json
{
  "id": "mem_xxx",
  "layer": 1,
  "polarity": "positive | negative | neutral | ambiguous",
  "memory_type": "fact | correction | success_path | failed_attempt | preference | hypothesis | pattern | avoidance_rule",
  "content": "...",
  "tags": ["..."],
  "linked_tags": ["..."],
  "source": "user | assistant | terminal | tool | file | web | composer | synthetic",
  "evidence": "...",
  "scope": "global | user | project | session | model",
  "model_fit": ["fast-chat", "reasoning-model", "coding-agent"],
  "confidence": 0.0,
  "heat": 0,
  "use_count": 0,
  "validation_count": 0,
  "success_score": 0.0,
  "correction_score": 0.0,
  "freshness": "stable | volatile | expired | unknown",
  "status": "candidate | activated | promoted | deprecated | archived"
}
```

---

## Example Pattern Schema

```json
{
  "id": "pattern_xxx",
  "layer": 3,
  "pattern_type": "diagnostic_rule",
  "status": "provisional | stable | challenged | rolled_back | archived",
  "composed_from": [
    "mem_positive_1",
    "mem_negative_2",
    "mem_neutral_3",
    "mem_ambiguous_4"
  ],
  "rule": "If X and Y are true, prioritize Z and avoid A.",
  "applies_when": ["..."],
  "avoid_when": ["..."],
  "success_path": ["..."],
  "failed_path": ["..."],
  "confidence": 0.82,
  "path_fitness_score": 0.76,
  "trial_count": 4,
  "success_count": 3,
  "failure_count": 1,
  "false_trigger_count": 0,
  "model_fit": ["coding-agent"],
  "promotion_reason": "Repeatedly helped solve similar tasks"
}
```

---

## Source-Gated Anti-Pollution

MemoryWeaver uses three layers of defense to prevent LLM fabrications from contaminating memory:

### 1. Source-Gated Polarity

Every memory has a `source` field. Assistant-generated content is **always** classified as `ambiguous` and never automatically trusted:

| Source | Allowed Polarity | Rationale |
|--------|-----------------|-----------|
| `user` | positive, negative, neutral, ambiguous | Direct human feedback |
| `terminal` | positive, negative, neutral | Objective command results |
| `tool` | positive, negative, neutral | Tool outputs are verifiable |
| `assistant` | **ambiguous only** | LLM output is unverified by default |
| `composer` | neutral, ambiguous | Pattern composition is inferred |

An ambiguous memory can only be upgraded to `positive` or `negative` through external verification (user confirmation or terminal validation).

### 2. Contradiction Detection

When a new memory conflicts with existing verified knowledge, a three-tier severity system determines the response:

```
L1 (SILENT) — both claims are unverified → record, don't interrupt
L2 (WARN)   — unverified vs possibly-stale verified → note, proceed cautiously
L3 (BLOCK)  — verified fact or user preference contradicted → stop, ask user
```

The `ContradictionResolver` (`memoryweaver/contradiction.py`) implements this with a priority rule chain that treats user preferences and terminal-verified facts as the highest authority.

### 3. Verified Retrieval

The `VerifiedRetriever` (`memoryweaver/retriever.py`) filters memories by source credibility during retrieval:

- User and terminal sources always pass through
- Web and composer sources pass with confidence check
- **Assistant-sourced memories with zero heat are excluded entirely**
- Assistant memories with heat > 0 can be included only when explicitly requested

This prevents the self-pollution loop: `LLM fabricates → stored as memory → retrieved next time → reinforces fabrication`.

### Architecture Diagram

![MemoryWeaver runtime architecture](docs/assets/memoryweaver-architecture.png)

This is the current runtime architecture. The repository now includes the local
memory core, anti-pollution primitives, reversible ContextCapsule compression,
Layer-3 path promotion, runtime marker authority, first-pass lifecycle gates
(`EnvironmentContract`, `ActionGate`, `TrajectoryRegulator`), and a v0.8
integrated substrate for RAG evidence, GBrain candidate graph, specialist
EvidencePacket routing, and checkpoint/resume. Production vector search,
multi-hop graph databases, CLI job isolation, broad provider coverage, and
large external benchmark optimization are v0.9 work rather than v0.8 setup.

---

## Current Structure

```text
memoryweaver/
├── memoryweaver/
│   ├── __init__.py
│   ├── schema.py              # MemoryItem, Pattern, enums
│   ├── store.py               # JSON-backed MemoryStore + MemoryWorkspace
│   ├── policy.py              # MemoryPolicy, RetrievalPolicy, ActionPolicy
│   ├── contract.py            # EnvironmentContract, ToolContract, SourceAuthority
│   ├── action_gate.py         # Structured ActionProposal + deterministic ActionGate
│   ├── trajectory.py          # TrajectoryRegulator for loops, stagnation, and budget
│   ├── skill.py               # Procedural skill retrieval over Layer-3 patterns
│   ├── harness.py             # Lifecycle orchestration across conditioning, action, and feedback
│   ├── scorer.py              # Heat, confidence, freshness signals
│   ├── extractor.py           # EventDetector + FeedbackClassifier (zh/en)
│   ├── retriever.py           # VerifiedRetriever with source-aware weighting
│   ├── router.py              # Fast / Thinking / Fast-Verify mode router
│   ├── contradiction.py       # ContradictionResolver (SILENT/WARN/BLOCK)
│   ├── evidence.py            # EvidenceNode, EvidenceLink, EvidencePacket, EvidenceStore
│   ├── composer.py            # PatternStore + explicit PatternComposer
│   ├── context_schema.py      # RawSpan, ContextCapsule, MarkerEvidenceContext
│   ├── context_store.py       # Raw/context stores with reversible raw refs
│   ├── content_router.py      # Rule-based RAW-to-capsule compression
│   ├── tag_time_index.py      # tag/time lookup for capsules
│   ├── marker_context.py      # MarkerEvidenceContext retrieval helpers
│   ├── graph_schema.py        # GraphNode, GraphEdge, GraphProposal
│   ├── graph_store.py         # Candidate graph persistence
│   ├── graph_linker.py        # Tag / memory / evidence / pattern linking
│   ├── graph_retriever.py     # Graph-assisted candidate narrowing
│   ├── gbrain.py              # Graph sync + mind-map projection
│   ├── lifecycle.py           # Verified writes, Pattern compose/rollback, marker writes
│   ├── runtime_authority.py   # Marker activation + hash-chained runtime decisions
│   ├── cli.py                 # `mw` CLI
│   ├── runtime/
│   │   └── live_loop.py       # Tau-style live loop with ActionGate + trajectory guard
│   ├── external/              # External dataset schemas, adapters, manifests
│   ├── integrations/          # LongMemEval-V2 style integration module
│   ├── evaluation/            # v0.7 experience-transfer + Layer-3 path-promotion protocols
│   ├── graph/                 # LLM GraphProposal generation/review helpers
│   └── providers/             # Optional provider skeletons for proposal generation
│
├── examples/
│   └── basic_memory_loop.py
│
├── benchmarks/
│   ├── prototype_baseline.py
│   ├── retrieval_*_validation.py
│   ├── live_*_v0_6_*.py
│   ├── external_dataset_adapter_v0_6_4.py
│   ├── layer3_path_promotion_v0_7.py
│   └── *_v0_7.py
│
├── scripts/
│   └── generate_architecture_diagram.py
│
├── docs/
│   ├── architecture.md
│   ├── life_harness_notes.md
│   ├── development_plan.md
│   ├── rag_evidence_layer.md
│   ├── gbrain_graph_memory.md
│   ├── react_agent_runtime.md
│   ├── collaborative_specialist_routing.md
│   ├── open_source_strategy_options.md
│   ├── bad_case_learning_loop.md
│   ├── agent_test_catalog.md
│   ├── testing_resilience_strategy.md
│   └── risk_assessment_and_benchmark.md
│
└── tests/
    ├── test_schema.py
    ├── test_retriever.py
    ├── test_composer.py
    ├── test_skill.py
    ├── test_harness.py
    ├── test_graph.py
    ├── test_context_capsule.py
    ├── test_runtime_authority.py
    ├── test_live_lite_harness_v0_6_2.py
    ├── test_path_promotion_protocol.py
    ├── test_v0_7_core.py
    └── ...
```

---

## Design Documents

- [`docs/architecture.md`](docs/architecture.md) — system boundaries and design principles
- [`docs/life_harness_notes.md`](docs/life_harness_notes.md) — lifecycle gates inspired by LIFE-HARNESS
- [`docs/rag_evidence_layer.md`](docs/rag_evidence_layer.md) — high-performance evidence retrieval
- [`docs/gbrain_graph_memory.md`](docs/gbrain_graph_memory.md) — graph memory, tags, and memory lifecycle
- [`docs/react_agent_runtime.md`](docs/react_agent_runtime.md) — ReAct runtime, session continuity, cache governance, and capacity planning
- [`docs/collaborative_specialist_routing.md`](docs/collaborative_specialist_routing.md) — GSCo-inspired staged specialist routing and EvidencePacket boundary
- [`docs/open_source_strategy_options.md`](docs/open_source_strategy_options.md) — implementation strategies to discuss before adding larger subsystems
- [`docs/bad_case_learning_loop.md`](docs/bad_case_learning_loop.md) — bad-case collection and progressive optimization
- [`docs/testing_resilience_strategy.md`](docs/testing_resilience_strategy.md) — regression, crash, avalanche, stress, security, and A/B testing
- [`docs/risk_assessment_and_benchmark.md`](docs/risk_assessment_and_benchmark.md) — current risks and measured prototype baseline

---

## Prototype Benchmark

Run the reproducible local baseline:

```powershell
python .\benchmarks\prototype_baseline.py
```

Latest `current-stage-check` artifact measured on Windows 11 with Python 3.14.0:

| Memory items | JSON size | Write throughput | Verified text search p95 |
| ---: | ---: | ---: | ---: |
| 100 | 89.3 KB | 127.68 items/s | 1.52 ms |
| 500 | 447.3 KB | 56.91 items/s | 6.04 ms |
| 1,000 | 894.8 KB | 31.82 items/s | 13.20 ms |

The JSON prototype is suitable for semantics and regression work, not
production-scale ingestion. Each write rewrites the JSON file.

The P0 trust-boundary fixes were validated across five independent trials.
See [`docs/validation/p0-trust-boundary-2026-06-02/README.md`](docs/validation/p0-trust-boundary-2026-06-02/README.md).

---

## Roadmap

### Phase 0: Concept Prototype

* Define memory schema
* Define polarity partitions
* Build local JSON-based memory store
* Implement manual memory tagging
* Build simple retrieval by tags and text

### Phase 1: Harness MVP

* Event detector
* Feedback classifier
* Memory scorer
* Layer 1 → Layer 2 promotion
* Fast / thinking mode router
* Terminal output ingestion

### Phase 2: RAG Integration

* Add vector database
* Add embedding-based retrieval
* Add memory heat and decay
* Add freshness and confidence scoring
* Add memory conflict detection

### Phase 3: Graph Memory

* Add graph linking
* Compose `positive + negative + neutral + ambiguous` into patterns
* Add stale node detection
* Add explicit Pattern validation and stable promotion

### Phase 4: Agent Integration

* Add LangGraph adapter
* Add MCP interface
* Add coding-agent example
* Add terminal tool memory loop
* Add model-specific memory profiles

### Phase 5: Evaluation

* Measure retrieval usefulness
* Track repeated error reduction
* Track user correction rate
* Track task resolution rate
* Compare memory-enabled vs memory-disabled agent runs

### v0.5.x Runtime-Memory Roadmap

The current research branch uses a more detailed runtime-memory sequence:

```text
v0.5   Runbook Marker Trace Advantage Validation
       manual CoreIssueNode / HarnessMarker fixtures, shadow traces,
       counterfactual advantage metrics

v0.5.2 Active Marker Binding Preview
       marker binds MarkerEvidenceContext -> ContextCapsule -> RawSpan,
       but runtime_authority remains false

v0.5.2 Controlled Active Guard
       one low-risk L1_hint marker may apply route/evidence plan,
       while L2/L3 remain preview-only

v0.5.2 L2 Route Approval
       L2_route markers require explicit approval before route/evidence plan
       can be applied

v0.5.2.x Active route / guard marker + MarkerConflictResolver
       marker can recommend route/guard/evidence checks under policy

v0.5.3 ContextCapsule + TagTimeIndex
       RAW/Event compression, RawSpan recovery, tag-time capsule lookup,
       MarkerEvidenceContext binding

v0.5.5 Drift detection + CoreIssueNode -> MarkerProposal
       uses TagTimeIndex as a time-aware evidence source

v0.6   Semi-real trajectory experiment
       turns v0.5 dialogue cards into no_memory / rag_over_logs /
       memoryweaver_runtime_marker replay trajectories

v0.6.1 Controlled harness run
       adds a deterministic harness policy loop and hash-chained decisions;
       live agent runs follow

v0.6.2 Live-lite harness
       executes deterministic in-memory mock tools and records tool results;
       real shell/network/tool execution remains disabled
```

### Concrete Library Absorption Plan

MemoryWeaver does not absorb external projects as dependencies at this stage.
It absorbs their useful design ideas into explicit, auditable MemoryWeaver modules while preserving the trust boundary.

| Reference | Absorbed into MemoryWeaver | Concrete modification | Not absorbed now |
| --- | --- | --- | --- |
| headroom | RAW/Evidence compression layer | `ContentRouter`, `ContextCapsule`, `RawSpan`, `TagTimeIndex`, and `MarkerEvidenceContext` sit between RAW events and Layer 1. Compression stays reversible through `raw_ref_id`. | Cross-agent memory, cache alignment, and any compression that changes trust. |
| Zep / Graphiti | Temporal GBrain model | Future graph nodes and edges should carry `valid_from`, `valid_to`, `last_seen`, `freshness`, `supersedes`, `challenged_by`, and episode provenance. | Automatic graph truth maintenance or direct promotion to verified memory. |
| Codebase-Memory | Coding-agent demo substrate | Prioritize coding/debug/configuration cards: commands, files, configs, errors, successful fixes, failed paths, and evidence-first checks. | Full Tree-sitter repository graph or MCP integration in v0.5. |
| LongMemEval / AgentRunbook | Runbook framing | Treat `Layer 3 Pattern + HarnessMarker` as a MemoryWeaver Runbook Marker: issue, gotcha, required evidence, avoided path, and route recommendation. | Claiming end-to-end task improvement before trajectory experiments. |
| harness-forge | Runtime operations model | Add/extend `mw doctor`, `mw trace`, decision logs, review views, approval records, bundles, and sentinel-style offline checks. | GPL code reuse, auto-tuning, or cross-project learned pattern activation. |
| OpenDB / SQLite FTS5 | Future index layer | v0.5+ may compare JSON scan against FTS/BM25-style indexing for larger memory sets. | Replacing the current JSON prototype before semantic gates are stable. |

Hard boundary:

```text
External libraries may inspire retrieval, graph, compression, and runtime UX.
They must not weaken source gates, evidence checks, Layer 3 lifecycle, or online/offline separation.
```

### Prepared Next Validations

The next tests are prepared as staged validations rather than one large system jump:

```text
v0.5.2 Decision Ledger
       hash-chained decision records for marker route-plan decisions,
       including policy version, approval id, conflict refs, capsule refs,
       raw refs, and zero side-effect counters

v0.5.3.x ContextCapsule stress set
       expand from 40 RawSpan fixtures to dialogue-derived raw spans,
       measure compression ratio, tag recall, raw recovery, time filtering,
       and trust-inheritance violations

v0.5.4 Library-inspired retrieval comparison
       compare baseline scan, TagTimeIndex lookup, and graph-assisted
       candidate narrowing

v0.5.4a SQLite FTS5 frontend filter comparison
       compare SQLite FTS5 all-corpus retrieval against MW tag/time -> FTS5
       and MW graph/tag/time -> FTS5

v0.5.4b Safety filter independence
       isolate source gate, freshness, and marker eligibility as safety gates
       after keyword/semantic relevance retrieval

v0.5.5 Temporal GBrain drift validation
       test valid_from/valid_to, supersedes, challenged_by, stale evidence,
       and CoreIssueNode/MarkerProposal candidates without changing Layer 3
       promotion rules

v0.5.5b Temporal graph ablation
       compare static tag co-occurrence graph against MW temporal graph

v0.5.6 Dense / hybrid comparison
       introduce dense and hybrid retrieval only after FTS5 and safety gates
       are independently validated

v0.6 Semi-real trajectory experiment
       replay 10-20 turn dialogue-card trajectories across no_memory,
       rag_over_logs, and memoryweaver_runtime_marker arms; track
       steps-to-success, user corrections, tool calls, known bad actions,
       and repeated-error reduction metrics

v0.6.1 Controlled harness run
       run the same three arms through a deterministic harness policy loop,
       recording one hash-chained decision per task/arm pair

v0.6.2 Live-lite harness
       execute deterministic in-memory mock tools for known-bad actions,
       generic debugging, and required evidence checks
```

The immediate testing contract is:

```text
1. Decision ledger must be hash-chain valid.
2. L2 route plans must require explicit approval.
3. L3 guard markers remain preview/shadow unless a later policy grants authority.
4. ContextCapsule must recover raw evidence by raw_ref_id.
5. Capsule compression cannot increase trust or promote memory.
6. Online path must not call LLM GraphProposal.
```

---

## Use Cases

### Coding Agent Memory

Remember project-specific commands, environment constraints, failed fixes, and successful solutions.

### Technical Support Agent

Turn solved tickets into diagnostic patterns and failed attempts into avoidance rules.

### Research Assistant

Track hypotheses, evidence, contradictions, and evolving conclusions.

### Personal AI Assistant

Remember user preferences, long-term goals, project context, and communication style.

### Multi-Agent Memory Layer

Provide shared, structured memory across different LLMs and tools.

---

## Design Principles

1. Memory should be evidence-backed.
2. Negative memory is useful.
3. Ambiguous memory should not be treated as truth.
4. Memory must decay or expire.
5. Repeated usefulness should promote memory.
6. Graph links are more powerful than isolated tags.
7. The harness should learn from memory feedback.
8. Different models may need different memory formats.
9. Long-term memory should be inspectable and editable.
10. Agents should remember outcomes, not just text.

---

## Status

**The repository has moved beyond the original SDK v0.2.0 foundation.** It is
still a zero-dependency JSON prototype, but the current worktree now includes a
broader validated runtime-memory stack:

- `schema.py` - `MemoryItem` for Layer 1/2 and canonical `Pattern` for Layer 3.
- `store.py` - atomic JSON stores, `MemoryWorkspace`, Chinese/mixed lexical baseline.
- `policy.py` - `MemoryPolicy`, `RetrievalPolicy`, and minimal `ActionPolicy`.
- `contract.py` - deterministic `EnvironmentContract`, `ToolContract`, and `SourceAuthority`.
- `action_gate.py` - structured `ActionProposal` plus deterministic `ActionGate`.
- `trajectory.py` - minimal `TrajectoryRegulator` for repetition, stagnation, and budget limits.
- `skill.py` - procedural skill retrieval over Layer-3 Patterns and avoidance memory.
- `harness.py` - explicit lifecycle harness across before-interaction, task conditioning,
  pre-execution gating, post-feedback regulation, and task-outcome recording.
- `evidence.py` - `EvidenceNode`, `EvidenceLink`, `EvidencePacket`, `EvidenceStore`.
- `composer.py` - `PatternStore` and explicit provisional `PatternComposer`.
- `context_schema.py`, `context_store.py`, `content_router.py`, `tag_time_index.py` -
  reversible RAW-to-capsule compression and scoped capsule lookup.
- `graph_schema.py`, `graph_store.py`, `graph_linker.py`, `graph_retriever.py` -
  minimal candidate graph/tag-linking for recall expansion and candidate narrowing.
- `gbrain.py` - workspace graph sync and mind-map projection over tags, memories,
  evidence, and Patterns.
- `config.py`, `providers/`, `graph/proposal.py`, `graph/reviewer.py` -
  optional low-privilege LLM GraphProposal generation and Harness review.
- `lifecycle.py` - verified writes, Pattern composition/rollback, marker context
  writes, and GBrain sync as one high-level service.
- `runtime_authority.py` - runtime marker activation, source-gated memory context,
  and hash-chained decision ledger.
- `runtime/live_loop.py` - tau-style live loop with runtime authority, ActionGate,
  and trajectory regulation.
- `integrations/lmev2_module.py` - LongMemEval-V2 style context backend that writes
  RawSpan/ContextCapsule without promoting verified memory by default.
- `external/longmemeval_v2.py` - LongMemEval-V2 snapshot resolver that can auto-detect
  `D:\benchmarks\longmemeval-v2`, fall back to `D:\hf_cache`, and optionally download
  the required snapshot layout via Hugging Face.
- `evaluation/experience_transfer.py` - deterministic v0.7 experience-transfer and
  random-experience protocols.
- `evaluation/path_promotion.py` - dedicated Layer-3 path-promotion protocol for
  stable-path promotion, stale-path suppression, rollback, and best-path selection.
- `cli.py` - `mw` CLI for validate, doctor, memory, evidence, pattern, route,
  graph, context, external, gbrain, skill, harness, contract, action, trajectory,
  layer, and eval.
- `scorer.py` - heat/confidence/freshness signals without automatic Layer 3 promotion.
- `retriever.py` - policy-filtered verified retrieval.
- `router.py` - Pattern-aware fast / thinking / fast-verify routing.
- `extractor.py` - bilingual feedback classifier and event detector.
- `contradiction.py` - three-tier contradiction resolver.

The P0 batch closed four trust-boundary risks: false heat from edits, tag-gate
bypass, assistant-positive writes, and Router fast-path bypass. Subsequent
runtime increments add policy gates, EvidenceLink validation, Chinese retrieval
probes, CLI smoke coverage, provisional/stable Pattern lifecycle tests,
ContextCapsule reversibility, marker-bound runtime guidance, and minimal
pre-execution / post-step lifecycle gates.

Validation scope:

- Main contribution in the current prototype direction: Layer-3 path promotion
  can turn verified experience into explicit reusable execution paths, score
  those paths with `path_fitness_score`, trial them across task runs, and rank
  the best current path through `PatternComposer.select_best_path()`,
  `SkillRetriever`, `MemoryWeaverHarness`, and the CLI `pattern trial` /
  `pattern best-path` flow.
- Dedicated evidence for that claim now lives in
  [`docs/validation/layer3-path-promotion-v0.7/README.md`](docs/validation/layer3-path-promotion-v0.7/README.md),
  including stable-path promotion, latest-path selection, stale-path suppression,
  rollback success, and zero path regret in the current deterministic fixture.
- A small real-snapshot bridge also now runs over LongMemEval-V2 data through
  `mw eval path-promotion-lme-v2 --json`, deriving path-promotion families from
  real external episodes before running the same Layer-3 promotion / rollback
  flow. On the current machine this path already runs over
  `D:\benchmarks\longmemeval-v2`, and the LongMemEval-V2 data layer can also
  fall back to `D:\hf_cache` or optionally download the required snapshot layout.
- In its current small real-data setting, that bridge already derives two
  families from the local snapshot and keeps `stable_promotion_rate = 1.0`,
  `latest_path_selection_accuracy = 1.0`, `stale_path_suppression_rate = 1.0`,
  and `average_path_regret = 0`.
- On the current machine, the same bridge also runs cleanly on a 5-question
  real LongMemEval-V2 subset with `real_snapshot_family_count = 5`,
  `latest_path_selection_accuracy = 1.0`, and `average_path_regret = 0`.
- It also scales cleanly to larger real subsets on the current machine: the
  same route has already been exercised at 20 and 50 real LongMemEval-V2
  questions while keeping `stable_promotion_rate = 1.0`,
  `latest_path_selection_accuracy = 1.0`, and `average_path_regret = 0`.
- Proven: policy gates hold, provisional Patterns do not route `fast`, evidence
  links do not auto-promote memory, Chinese lexical retrieval has a baseline,
  RAW context remains reversible via `raw_ref_id`, runtime marker filters can
  hold five leak categories at zero in controlled validations, and live-loop
  smokes can write verified memory from observations without bypassing the
  runtime safety boundary.
- Not proven yet: faster real task completion, repeated error reduction,
  superiority over RAG over logs, cross-model memory reuse, or long-term project
  stability.

The safety-boundary results, marker projections, and retrieval-speed / candidate
reduction comparisons remain important, but they are supporting boundary
evidence rather than the primary claim. They fit best as safety or appendix
material around the main Layer-3 path-promotion story.

Run the current Layer-3 path-promotion validation with:

```powershell
python .\benchmarks\layer3_path_promotion_v0_7.py
mw eval path-promotion --json
mw eval path-promotion-lme-v2 --json --question-limit 2 --trajectories-per-question 1 --states-per-trajectory 1
```

The next publishable experiment should expand this Layer-3 story outward:
larger sibling-task families, stronger path competition, stale-path replacement,
rollback under environment change, and eventually open-world task trajectories.

For external benchmark context, `mw external lme-v2-context` now supports
automatic LongMemEval-V2 root discovery from `D:\benchmarks\longmemeval-v2` and
fallback Hugging Face cache discovery under `D:\hf_cache`, with optional
download when the local snapshot is missing.

Future LLM-assisted maintenance must keep this hard boundary: LLMs may maintain
candidate graph nodes, candidate summaries, and candidate branches, but they
must not directly maintain verified memory or stable Patterns.

The validation items below are supporting boundary or appendix evidence. They
matter for trust and runtime safety, but they are no longer the primary claim.

Graph tag-linking validation is recorded in
[`docs/validation/graph-tag-linking-v0.3/README.md`](docs/validation/graph-tag-linking-v0.3/README.md).
It shows that a one-hop graph can improve tag recall and reduce candidate scan
size in a controlled fixture, but it does not prove task success improvement.

Runbook Marker v0.5 validation is recorded in
[`docs/validation/runbook-marker-v0.5/README.md`](docs/validation/runbook-marker-v0.5/README.md).
It currently measures manually annotated counterfactual trace advantage, not
real task success improvement.

Active Marker Binding v0.5.2 validation is recorded in
[`docs/validation/active-marker-binding-v0.5.2/README.md`](docs/validation/active-marker-binding-v0.5.2/README.md).
It verifies that five golden Runbook Markers can bind capsule evidence and
recover raw spans without runtime mutation, Layer-3 mutation, memory promotion,
online LLM calls, or tool execution.

Controlled Active Guard v0.5.2 validation is recorded in
[`docs/validation/controlled-active-guard-v0.5.2/README.md`](docs/validation/controlled-active-guard-v0.5.2/README.md).
It allows exactly one low-risk `L1_hint` marker to add a route hint and required
evidence plan, while blocking `L2_route` and `L3_guard` markers from active
runtime behavior. It also logs unresolved marker conflicts and blocks conflicted
markers from active behavior.

L2 Route Approval v0.5.2 validation is recorded in
[`docs/validation/l2-route-approval-v0.5.2/README.md`](docs/validation/l2-route-approval-v0.5.2/README.md).
It permits one approved `L2_route` marker to apply a route/evidence plan while
leaving an unapproved L2 marker pending and keeping L3 guard markers blocked.

Decision Ledger v0.5.2 validation is recorded in
[`docs/validation/decision-ledger-v0.5.2/README.md`](docs/validation/decision-ledger-v0.5.2/README.md).
It records five route-plan decisions as a SHA-256 hash chain with policy
version, approval id, conflict refs, capsule refs, raw refs, and zero side-effect
counters.

ContextCapsule / TagTimeIndex v0.5.3 validation is recorded in
[`docs/validation/context-capsule-v0.5.3/README.md`](docs/validation/context-capsule-v0.5.3/README.md).
It validates RAW-to-capsule compression, reversible raw retrieval, tag-time
lookup, CLI context smoke, and MarkerEvidenceContext validation over a 40-span
fixture.

ContextCapsule Stress v0.5.3.x validation is recorded in
[`docs/validation/context-capsule-stress-v0.5.3x/README.md`](docs/validation/context-capsule-stress-v0.5.3x/README.md).
It extends the 40-span fixture with 50 dialogue cards and 301 dialogue-derived
RawSpans, while keeping raw recovery, tag recall, marker context hit rate, and
trust inheritance gates clean.

Retrieval Comparison v0.5.4 validation is recorded in
[`docs/validation/retrieval-comparison-v0.5.4/README.md`](docs/validation/retrieval-comparison-v0.5.4/README.md).
It compares baseline capsule scan, TagTimeIndex lookup, and accepted-graph plus
TagTimeIndex lookup over 50 queries and 341 capsules. All three keep Recall@10
at 1.0, while structured retrieval reduces the average candidate set from 341
to 6.44 without online LLM calls, memory promotion, or Layer-3 mutation.

SQLite FTS5 Frontend Filter v0.5.4a validation is recorded in
[`docs/validation/retrieval-fts5-filter-v0.5.4a/README.md`](docs/validation/retrieval-fts5-filter-v0.5.4a/README.md).
It compares full SQLite FTS5 retrieval with MW tag/time -> FTS5 and MW
graph/tag/time -> FTS5. Recall@10 remains 1.0, average candidates drop from
341 to 6.44, and p95 latency drops from 11.5543 ms to about 2.02 ms, with no
online LLM calls, memory promotion, or Layer-3 mutation.

Temporal GBrain Drift v0.5.5 validation is recorded in
[`docs/validation/temporal-gbrain-drift-v0.5.5/README.md`](docs/validation/temporal-gbrain-drift-v0.5.5/README.md).
It projects 50 CoreIssueNodes and 50 HarnessMarkers into a temporal graph with
validity metadata, supersedes/challenged_by lineage, and 13 review-only
MarkerProposal candidates. It grants no runtime authority and performs no
memory promotion or Layer-3 mutation.

Runtime Safety Gate Independence is validated across two complementary surfaces:

#### 5.1 Relevance Retrieval Leaks

Retrieval Safety Filter v0.5.4b is recorded in
[`docs/validation/retrieval-safety-filter-v0.5.4b/README.md`](docs/validation/retrieval-safety-filter-v0.5.4b/README.md).
It runs adversarial FTS5 queries over 50 dialogue-card queries and 341 capsules.
FTS5-only top-10 results contain 40 untrusted leaks, 35 assistant traps, and 27
stale runtime candidates. Source/freshness/marker gates reduce all three to 0
while keeping required-evidence hit rate at 0.98 and known-bad-warning hit rate
at 0.98.

#### 5.2 Static Graph Leaks

Temporal Graph Ablation v0.5.5b is recorded in
[`docs/validation/temporal-graph-ablation-v0.5.5b/README.md`](docs/validation/temporal-graph-ablation-v0.5.5b/README.md).
It compares static tag co-occurrence against temporal GBrain runtime filtering.
Static retrieval keeps marker Recall@10 at 1.0 but leaks 66 stale and 66
challenged top-10 runtime candidates. Temporal runtime filtering keeps
eligible-marker Recall@10 at 1.0, reduces stale/challenged runtime leaks to 0,
and captures all 13 review-only markers.

Neither relevance-based retrieval nor static graph structure is sufficient for
runtime memory safety. Both leak candidates that are topically relevant but
temporally invalid, source-untrusted, or marker-ineligible. MemoryWeaver's
combined source gate, temporal graph, and marker eligibility filter reduces all
five leak categories to zero, while preserving required-evidence and
known-bad-warning hit rates above 0.98. These validations perform no online LLM
calls, memory promotion, Layer-3 mutation, or runtime-authority grant.

Paper framing:

```text
Evidence line A: MW != strict filter        -> strict discards useful weak signals; MW can retain them.
Evidence line B: MW != relevance retrieval  -> BM25/FTS5 ranks topical text; MW decides runtime eligibility.
Evidence line C: MW != static graph         -> static graphs connect related nodes; MW tracks validity/challenge/replacement.
v0.6 summary: semi-real replay now measures fewer steps, corrections, and known-bad-path attempts; live harness runs are next.
```

The claim is not simply "MemoryWeaver beats X." The claim is that strict
filters, relevance retrieval, and static graphs solve different subproblems,
while none of them decides whether an experience is qualified to enter runtime.

Real Trajectory Experiment v0.6 is recorded in
[`docs/validation/real-trajectory-experiment-v0.6/README.md`](docs/validation/real-trajectory-experiment-v0.6/README.md).
It replays 50 dialogue-card tasks across `no_memory`, `rag_over_logs`, and
`memoryweaver_runtime_marker`. In this semi-real replay, MemoryWeaver reduces
steps-to-success by 3 vs no-memory and 1 vs RAG, reduces known-bad action
attempts by 55 vs no-memory and 50 vs RAG, reaches required evidence first at
rate 1.0, and performs no online LLM calls or runtime-authority violations. It
does not yet claim live agent task success improvement.

Controlled Harness Run v0.6.1 is recorded in
[`docs/validation/controlled-harness-run-v0.6.1/README.md`](docs/validation/controlled-harness-run-v0.6.1/README.md).
It runs the same 50 tasks through a deterministic policy loop and records 150
hash-chained decisions. MemoryWeaver keeps the v0.6 gains while adding
decision-level auditability: steps-to-success are reduced by 3 vs no-memory and
1 vs RAG, known-bad action attempts are reduced by 55 vs no-memory and 50 vs
RAG, required evidence is reached first at rate 1.0, and all side-effect
counters remain zero. This still does not execute real tools or claim live agent
success.

Live-Lite Harness v0.6.2 is recorded in
[`docs/validation/live-lite-harness-v0.6.2/README.md`](docs/validation/live-lite-harness-v0.6.2/README.md).
It executes 500 deterministic in-memory mock tools across the same 50 tasks and
three arms. Known-bad mock tools return `failed_known_bad`, while required
evidence tools return `evidence_observed`. MemoryWeaver reduces known-bad mock
tool failures by 55 vs no-memory and 50 vs RAG, observes required evidence 100
times, keeps unsafe mock tool execution at 0 in the MW arm, and still performs
no real tool execution, memory promotion, Layer-3 mutation, or online LLM call.

LLM GraphProposal validation is recorded in
[`docs/validation/llm-graph-proposal-v0.4/README.md`](docs/validation/llm-graph-proposal-v0.4/README.md).
The API framework is disabled by default and only produces `GraphProposal`
objects. Harness review is required before any candidate edge is written.

v0.8 build status: complete substrate, not production-scale optimization. The
artifact in
[`docs/validation/v0.8-integration/README.md`](docs/validation/v0.8-integration/README.md)
shows RAG evidence refs, GBrain candidate graph, specialist EvidencePacket,
checkpoint/resume, and pass^3 reliability while keeping direct verified-memory
and Layer-3 mutation at zero.

Deferred to v0.9: production vector DB / HNSW, multi-hop graph optimization,
CLI job isolation, broad provider coverage, larger external benchmarks, and
automatic PatternComposer inference. These are optimization and scale work on
top of the v0.8 substrate, not missing v0.8 setup.

---

## License

MIT

---

## Acknowledgements

This project is inspired by ideas from:

* RAG systems
* Long-term agent memory
* Feedback loops
* Knowledge graphs
* Cognitive architectures
* Vibe coding agents
* Memory-first agent frameworks

MemoryWeaver is not intended to replace existing agent frameworks.
It is designed to sit between the agent harness, memory store, graph layer, and retrieval layer.
