# MemoryWeaver

**Feedback-Calibrated Memory Harness for Long-Lived AI Agents**

MemoryWeaver is an experimental memory harness for AI agents that turns conversations, terminal outputs, tool results, user corrections, and task outcomes into reusable long-term memory.

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

MemoryWeaver treats memory as an evolving feedback system.

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
Harness Pre-Tagging
        ↓
Layer 1: Candidate Memory
        ↓
Layer 2: Activated / Validated Memory
        ↓
Graph Linking / Pattern Composition
        ↓
Layer 3: Shared Pattern Memory
        ↓
Harness Policy Update
```

The system is designed as a feedback loop:

```text
Tag → Use → Feedback → Promote → Link → Abstract → Retag
```

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

### Layer 2: Activated Memory

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

### Layer 3: Shared Pattern Memory

Layer 3 stores reusable patterns, not just raw tags.

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

Layer 3 is shared by the harness and retrieval system.

It helps the agent decide:

* When to use fast mode
* When to use thinking mode
* Which memory to retrieve
* Which assumptions to avoid
* Which tool path to try first
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
* Learning which tags are useful for each LLM

The LLM reasons.
The tools act.
The memory stores.
The harness coordinates.

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

This allows agents to think deeply once, archive the result, and reuse validated patterns later.

---

## GBrain / Graph Memory Integration

MemoryWeaver is designed to work with graph-style memory systems.

Graph memory can:

* Link related tags
* Merge duplicate nodes
* Detect stale knowledge
* Connect people, projects, errors, tools, and outcomes
* Compose second-layer signals into third-layer patterns

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
  "source": "user | assistant | terminal | tool | file | web",
  "evidence": "...",
  "scope": "global | user | project | session | model",
  "model_fit": ["fast-chat", "reasoning-model", "coding-agent"],
  "confidence": 0.0,
  "heat": 0,
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
  "composed_from": [
    "mem_positive_1",
    "mem_negative_2",
    "mem_neutral_3",
    "mem_ambiguous_4"
  ],
  "rule": "If X and Y are true, prioritize Z and avoid A.",
  "applies_when": ["..."],
  "avoid_when": ["..."],
  "confidence": 0.82,
  "model_fit": ["coding-agent"],
  "promotion_reason": "Repeatedly helped solve similar tasks"
}
```

---

## Planned Components

```text
memoryweaver/
├── harness/
│   ├── event_detector.py
│   ├── feedback_classifier.py
│   ├── mode_router.py
│   └── memory_router.py
│
├── memory/
│   ├── schema.py
│   ├── store.py
│   ├── scorer.py
│   ├── promoter.py
│   └── decay.py
│
├── graph/
│   ├── linker.py
│   ├── composer.py
│   └── conflict_resolver.py
│
├── rag/
│   ├── embedder.py
│   ├── retriever.py
│   └── reranker.py
│
├── adapters/
│   ├── terminal.py
│   ├── mcp.py
│   ├── langgraph.py
│   ├── letta.py
│   └── mem0.py
│
├── examples/
│   ├── coding_agent_memory/
│   ├── terminal_feedback_loop/
│   └── fast_thinking_router/
│
└── tests/
```

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
* Add pattern promotion into Layer 3

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

MemoryWeaver is currently a concept-stage project.

The initial goal is to build a minimal local prototype for coding-agent workflows.

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
