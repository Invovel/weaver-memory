# Open-Source Strategy Options

## Decision Boundary

This document collects implementation strategies for discussion. It does not
authorize adding graph memory, autonomous ReAct, or production RAG before the
current P0 and lifecycle gates are verified.

## Recommended Learning Path

| Area | Primary reference | Strategy to study | MemoryWeaver decision point |
| --- | --- | --- | --- |
| Temporal graph memory | [Graphiti](https://github.com/getzep/graphiti) | Incremental updates, temporal facts, episode lineage | Keep raw episodes separate from verified Pattern promotion |
| Graph RAG | [Microsoft GraphRAG](https://github.com/microsoft/graphrag) | Offline indexing, community summaries, local/global search | Decide whether community summaries belong in offline maintenance only |
| Durable agent runtime | [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | Threads, checkpoints, interrupts, resume | Reuse the checkpoint model before adding bounded ReAct |
| Lightweight ReAct | [smolagents](https://github.com/huggingface/smolagents) | Small tool loops, code agent and tool-calling agent boundaries | Keep Harness policy authoritative over model proposals |
| Model fallback | [LiteLLM Router](https://docs.litellm.ai/docs/routing) | Retries, fallbacks, cooldowns, routing | Separate LLM circuit breaking from retrieval and CLI breakers |
| Model abstraction | [Pydantic AI fallback models](https://ai.pydantic.dev/models/overview/#fallbackmodel) | Typed fallback model chains | Use for explicit fallback order and testable configuration |
| Coding-agent tool boundary | [SWE-agent](https://github.com/SWE-agent/SWE-agent) | Agent-computer interface and constrained tools | Shape `ToolContract` and `ActionGate` |
| Coding-agent runtime | [OpenHands](https://github.com/All-Hands-AI/OpenHands) | Runtime isolation and event-driven execution | Study CLI sandboxing, journal, and recovery |
| Sessions and tracing | [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) | Sessions, handoffs, guardrails, tracing | Keep observability explicit and versioned |
| Memory product shape | [Letta](https://github.com/letta-ai/letta) | Agent memory blocks and archival memory | Compare user-visible memory editing semantics |
| Memory extraction | [Mem0](https://github.com/mem0ai/mem0) | Memory extraction, update, delete, and graph memory options | Compare provenance and deduplication behavior |
| Graph pipeline | [Cognee](https://github.com/topoteretes/cognee) | Graph-oriented memory pipelines | Compare ingestion and compaction workflows |
| CLI graph memory | [GBrain](https://github.com/garrytan/gbrain) | Scoped retrieval, source-tier boosts, graph signals, synthesis separation | Strong candidate for the smallest graph adapter |

## Multiple Solution Options

### Option A: Conservative Harness First

```text
Source gate
-> lifecycle semantics
-> test and benchmark gate
-> ActionGate and TrajectoryRegulator
-> checkpoint runtime
-> minimal graph projection
```

Best when correctness and auditability matter more than feature speed.

### Option B: Minimal Graph Adapter After Gates

```text
Option A foundation
-> scoped point lookup
-> tag lookup
-> one-hop relation expansion
-> Pattern lineage
-> temporal edges
```

Study GBrain and Graphiti. Avoid automatic graph expansion into verified memory.

### Option C: RAG Evidence Layer Before Rich Graph

```text
Option A foundation
-> immutable dataset manifests
-> sparse and multilingual dense retrieval
-> reranking
-> citations
-> synthetic HyDE kept outside verified facts
```

Study MIRACL, SciFact, and HAGRID datasets before choosing a vector database.

### Option D: Durable Bounded ReAct

```text
Option A foundation
-> structured ActionProposal
-> ToolGateway
-> checkpoint and Event Journal
-> step, token, and wall-clock budgets
-> isolated fallback and circuit breakers
```

Study LangGraph, SWE-agent, OpenHands, smolagents, and LiteLLM. Do not let an
LLM bypass the Harness.

## Suggested Discussion Order

1. Approve the dataset stack and evaluation protocol.
2. Choose between minimal graph adapter and evidence-layer-first development.
3. Define the ActionGate contract before autonomous execution.
4. Add durable runtime and bounded ReAct only after recovery semantics exist.
5. Add richer graph maintenance, offline synthesis, and canary rollout last.
