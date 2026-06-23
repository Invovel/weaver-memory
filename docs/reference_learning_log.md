# Reference Learning Log

Last updated: 2026-06-12

This log records how MemoryWeaver absorbs external references without losing its
own boundary:

> LLM proposes. Harness judges. Evidence promotes. Conflicts demote.

The goal is not to copy another agent-memory product. The goal is to turn outside
work into concrete MemoryWeaver design constraints, validation targets, and
version milestones.

## Non-Negotiable Design Rules

- LLM output is never verified memory by default.
- Assistant-authored memory defaults to ambiguous unless supported by external
  evidence.
- Specialists, routers, RAG, GBrain, and HyDE may produce candidates or evidence
  packets; none can directly write Layer 2 verified memory or Layer 3 stable
  paths.
- Negative memory is avoidance memory, not trash.
- Layer 3 stores reusable runtime patterns or paths, not raw chunks.
- RAG retrieves evidence; GBrain organizes relations; MemoryWeaver Harness
  decides promotion, demotion, rollback, and anti-pollution.
- Live LLM runs prove proposal integration only when tool feedback, tests, diffs,
  rollback records, and pass^k evidence are captured outside the model.

## Current Target

v0.7 should close as an evidence package, not as a feature expansion.

The immediate target is:

1. Keep the Experience Transfer Protocol split between `main_suite` and
   `marker_only_boundary`.
2. Make invalid probes explicit: `action_with_context == "__invalid_action__"`
   must not count as a valid decision-change benefit.
3. Split Layer-3 MVP into clean promotion and expected conflict rejection.
4. Produce SQ01-SQ05 reports for paper/demo inspection.
5. Run pass^3 with independent output directories.
6. Keep README, claim mapping, diagrams, and validation artifacts aligned.

## Reference Matrix

| Reference | Type | Useful Lesson | MemoryWeaver Absorption | Version Target |
| --- | --- | --- | --- | --- |
| [LIFE-HARNESS](https://arxiv.org/abs/2605.22166) / [code](https://github.com/Tianshi-Xu/Life-Harness) | paper/project | Runtime harness can improve frozen agents by adapting contracts, skills, action realization, and trajectory regulation. | Keep MemoryWeaver centered on runtime path promotion rather than model training. Use four-stage evidence flow: contract -> path -> action -> trajectory. | v0.7 framing, v0.8 runtime substrate |
| [Harness Updating Is Not Harness Benefit](https://arxiv.org/abs/2605.30621) | paper | Updating a harness artifact and benefiting from it are different capabilities. | Benchmark both `harness_update_quality` and `harness_benefit_rate`. Do not cite a successful update as task benefit. | v0.8/v0.9 |
| [SafeHarness](https://arxiv.org/abs/2604.13630) | benchmark/framework | Harness is an attack surface; security needs lifecycle-level checks, rollback, and privilege separation. | Expand tests for unsafe behavior rate, attack success rate, rollback success, and tool privilege tightening. | v0.7.1 safety, v0.8 resilience |
| [MemEvoBench](https://arxiv.org/abs/2604.15774) | benchmark | Memory can mis-evolve through noisy tool output, biased feedback, and adversarial injection. | Add memory-misevolution stress cases: contaminated pools, biased feedback, false positives, correction tools, and rollback. | v0.8 benchmark track |
| [LongMemEval-V2](https://arxiv.org/abs/2605.12493) / [dataset](https://huggingface.co/datasets/xiaowu0162/longmemeval-v2) | benchmark | Long-term agent memory must answer environment-experience questions, not just retrieve chat history. | Keep LME-V2 adapter as evidence retrieval benchmark; measure accuracy, latency, and compact evidence quality. | v0.8/v0.9 |
| [Mem2ActBench](https://arxiv.org/abs/2601.19935) | benchmark | Memory must be proactively applied to tool actions and parameter grounding. | Add action-grounding tasks where memory changes tool choice or arguments under Harness gate. | v0.9 |
| [EvoMemBench](https://arxiv.org/abs/2605.18421) / [code](https://github.com/DSAIL-Memory/EvoMemBench) | benchmark | Memory should be evaluated across in-episode/cross-episode and knowledge/execution axes. | Use this taxonomy to separate RAG evidence, short-term trace, Layer 2 memory, and Layer 3 execution paths. | v0.8/v0.9 |
| [Zep / Graphiti](https://arxiv.org/html/2501.13956v1), [Graphiti](https://github.com/getzep/graphiti) | repo/system | Temporal knowledge graphs need provenance, time windows, supersession, and incremental updates. | GBrain should store temporal relation candidates and lineage. It must not directly promote raw chunks to Layer 3. | v0.8 |
| [Microsoft GraphRAG](https://github.com/microsoft/graphrag) | repo/system | Offline graph indexing and community summaries help broad evidence retrieval. | Use for RAG evidence layer inspiration, not as MemoryWeaver's promotion authority. | v0.8 evidence layer |
| [Cognee](https://github.com/topoteretes/cognee) | repo/system | Agent memory can combine vector retrieval, graph reasoning, and ontology-like structure. | Borrow ingestion/graph pipeline ideas; keep verified-memory policy separate. | v0.8/v0.9 |
| [MemCog](https://arxiv.org/html/2605.28046v1) | paper | Memory should be navigable and proactively explored, not only one-shot retrieval. | Add graph-guided memory exploration as candidate expansion. Harness still gates final use. | v0.9 |
| [CodeMem](https://arxiv.org/html/2512.15813v1), [AST-guided CodeMEM](https://arxiv.org/pdf/2601.02868) | paper/repo family | Procedural/code memory and AST-guided context retention help coding agents preserve useful repository context. | Keep coding-debug benchmark centered on real pytest, diff, and repo context evidence. Add AST-aware future retrieval only after v0.7 evidence closes. | v0.8/v0.9 |
| [HarnessForge](https://arxiv.org/abs/2606.01779) | paper/future | Harness-policy co-evolution separates external execution structure from internal reasoning behavior. | Treat as future research direction; do not co-evolve policy until Harness benefit metrics are stable. | post-v0.9 |
| [OpenAI Harness Engineering](https://openai.com/index/harness-engineering/) | engineering note | Repository-local docs, plans, traces, tests, and observability become the agent's system of record. | Keep MemoryWeaver claims in repo artifacts, not old chat context. Validation logs and docs must be mechanically checkable. | v0.7.1 docs, v0.8 operations |
| [EvolveMem](https://arxiv.org/abs/2605.13941) / [SimpleMem](https://github.com/aiming-lab/SimpleMem) | paper/future | Retrieval mechanisms themselves can evolve through diagnosis, guarded updates, and revert-on-regression. | Useful for later RetrievalPolicy evolution. Must require regression gates before any policy update is accepted. | post-v0.9 |
| [MemSkill](https://github.com/ViktorAxelsen/MemSkill) | paper/project | Memory skills can be learned, refined, and reused from task feedback. | Map to Layer-3 path pattern extraction, but skill reuse must remain evidence-gated. | v0.8/v0.9 |
| [GSCo / MedDr](https://github.com/sunanhe/MedDr) | paper/project | Generalist-specialist collaboration can stage low-cost specialists before expensive reasoning. | Use for Collaborative Specialist Routing: cheap tag/source/scope/time checks first; escalate only under conflict, sparse evidence, or high risk. | v0.8 |
| [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | docs/system | Checkpoints preserve thread-scoped state; stores preserve cross-thread memory. | Use checkpoint/thread/resume as substrate. Do not confuse checkpoint state with verified memory. | v0.8 |
| [smolagents](https://github.com/huggingface/smolagents) | repo/system | A small ReAct/tool loop can remain understandable and testable. | Keep ReAct fast path small; Harness owns final authorization and evidence capture. | v0.8 |
| [LlamaIndex ReAct workflow](https://developers.llamaindex.ai/python/examples/workflow/react_agent/) | docs/system | ReAct workflows can be stateful while still tool-driven. | Use as reference for quick action loops, not for promotion logic. | v0.8 |
| [LiteLLM Router](https://docs.litellm.ai/docs/routing), [Pydantic AI FallbackModel](https://pydantic.dev/docs/ai/api/models/fallback/) | docs/system | Retry, cooldown, fallback, and semantic failure routing reduce model outage brittleness. | Add model fallback as runtime reliability, not as evidence quality. | v0.8 resilience |
| [SWE-agent ACI](https://github.com/SWE-agent/SWE-agent/blob/main/docs/background/aci.md) | repo/paper | Agent-computer interface shape strongly affects coding-agent behavior. | Treat ActionGate/tools as ACI; evaluate with real tests and diffs. | v0.8 coding track |
| [OpenHands](https://github.com/OpenHands/openhands) | repo/system | Sandboxed agent runtime and SDK boundaries matter for reproducible coding workflows. | Borrow workspace isolation and runtime boundary ideas. | v0.8/v0.9 |
| [OpenAI Agents SDK tracing](https://openai.github.io/openai-agents-python/tracing/), [guardrails](https://openai.github.io/openai-agents-python/guardrails/) | docs/system | Tracing and guardrails should be first-class runtime artifacts. | Keep trace, guardrail result, and tool feedback as claim evidence. | v0.8 |
| [BrowserAct skills](https://github.com/browser-act/skills), [Skill Forge](https://github.com/browser-act/skills/blob/main/docs/skill-forge.md) | repo/skill | Repeated web/browser tasks can be forged into reusable skills after validation. | Use skill-forge style only after real execution evidence; do not turn exploration into stable memory directly. | v0.8/v0.9 |
| Codex `skill-creator` | local skill | Skills should use progressive disclosure and low-freedom scripts for fragile workflows. | Make MemoryWeaver runtime paths compact, scripted where deterministic, and backed by validation artifacts. | v0.7.1 docs, v0.8 |
| [dbskill](https://github.com/lifangbiz/dbskill), [dontbesilent dbskill](https://github.com/dontbesilent2025/dbskill) | repo/skill | Skill routers can separate entry routing from domain execution; write operations need permission and audit. | Borrow route-only entrypoint and audit log pattern for future specialist packs. | v0.8 |
| [claude-mem](https://docs.claude-mem.ai/installation) | plugin/system | Session continuity can be useful, but shadow memory writers can be expensive and unsafe if ungated. | Borrow continuity UX; reject direct shadow-writes into verified memory. | v0.8 |
| [Headroom](https://github.com/chopratejas/headroom) | repo/system | Compression should preserve a retrieval path; token savings alone are not correctness. | Use reversible compression for evidence packets and traces; never compress away provenance or conflict markers. | v0.8 |
| `yo-wiki-atom` / `yo-wiki-review` | unverified/user-provided reference | The useful idea is atomic wiki entries plus review gate. Public canonical source not verified yet. | Adopt as a design pattern only: atomic entries, review status, supersession, and source links. | v0.8 docs |
| Letta / Mem0 | product/system references | Long-lived agent memory products show UX demand for continuity. | Keep as comparison baselines, not architectural authority. | v0.9 related work |

## Optimization Directions

### P0: v0.7 Evidence Closure

The next code changes should be small and evidence-oriented:

- Tighten Experience Transfer assertions around `main_suite` and
  `marker_only_boundary`.
- Make `retrieval_hit_before_critical_action_rate == 1.0` explicit for
  `mw_verified_memory` in the main suite when the deterministic fixture supports
  it.
- Keep invalid probe filtering as a first-class metric:
  `decision_changed_valid_rate`, not raw `decision_changed`.
- Split Layer3 MVP into:
  - clean candidate -> provisional -> trial -> stable
  - challenged candidate -> expected `promote_stable` rejection
- Emit `sq_report.jsonl` with SQ01-SQ05:
  - SQ01 evidence nodes and links exist
  - SQ02 provisional pattern created
  - SQ03 trial evidence recorded
  - SQ04 clean stable promotion succeeds
  - SQ05 conflict stable promotion is blocked

### P1: v0.8 GBrain and RAG Evidence Layer

The v0.8 graph/RAG work should follow three separations:

- RAG produces evidence nodes, not verified memory.
- GBrain produces relation candidates, temporal lineage, and conflict expansion.
- Harness decides whether evidence supports promotion, challenge, rollback, or
  demotion.

Suggested v0.8 metrics:

- `evidence_recall_at_k`
- `wrong_link_rate`
- `stale_relation_suppression_rate`
- `conflict_expansion_recall`
- `citation_version_match_rate`
- `graph_candidate_reduction_ratio`
- `promotion_without_hard_evidence_count == 0`

### P2: v0.8 Runtime Resilience

Use LangGraph, SafeHarness, LiteLLM, Pydantic AI, and OpenAI Agents SDK as
resilience references:

- checkpoint / resume / interrupt
- retry / cooldown / fallback
- trace IDs and guardrail events
- privilege tiering for tools
- rollback after repeated anomaly

Suggested metrics:

- `resume_success_rate`
- `checkpoint_roundtrip_rate`
- `fallback_success_rate`
- `cooldown_recovery_rate`
- `unsafe_action_block_rate`
- `rollback_after_anomaly_rate`

### P3: v0.9 External Benchmark Expansion

After v0.7 evidence closure and v0.8 architecture separation, expand to:

- LongMemEval-V2 for environment-experience evidence retrieval.
- Mem2ActBench for proactive memory-to-action use.
- EvoMemBench for memory scope/content taxonomy.
- MemEvoBench for contaminated memory evolution and biased feedback.
- CodeMem-style coding tasks for AST/repository context and real test/diff
  evidence.

## Version Gate

Do not jump from v0.8 directly to 1.0.

Recommended path:

- `v0.7.1`: evidence closure, SQ report, pass^3 reproducibility, stale doc cleanup.
- `v0.8`: GBrain temporal candidate graph, RAG evidence layer, specialist routing,
  checkpoint/resume substrate.
- `v0.9`: external benchmark matrix, broader live LLM/coding-debug validation,
  memory-misevolution stress tests.
- `v1.0`: stable API, reproducible artifact package, public README claims backed
  by artifact paths, and no undocumented benchmark entrypoint confusion.

## Explicit Non-Goals

- Do not let high-end LLMs directly maintain verified memory.
- Do not make GBrain the promotion authority.
- Do not treat live LLM pass^3 as open-world task success.
- Do not count harness updates as benefit without downstream task evidence.
- Do not store raw chunks as Layer-3 patterns.
- Do not make compression or summarization destroy provenance.
- Do not use specialist output as fact memory without hard evidence.

## Next Patch Checklist

When implementation resumes, apply this sequence:

1. Patch Layer3 MVP SQ01-SQ05 reporting and expected conflict rejection.
2. Tighten Experience Transfer deterministic assertions where current artifacts
   support exact values.
3. Regenerate Layer3 MVP and Experience Transfer validation artifacts with
   pass^3 independent directories.
4. Update `docs/development_plan.md` lines that still say Layer3 MVP or
   Experience Transfer are unfinished if the new evidence passes.
5. Update README claim language only after artifacts exist.
