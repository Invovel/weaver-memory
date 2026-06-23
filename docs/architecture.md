# MemoryWeaver Architecture

## 文档状态

本文描述当前实现与后续目标架构。标记为“目标”的组件尚未落地，不应被
README 或调用方当作已有能力。

## 核心原则

**LLM proposes, Harness judges.**

- LLM 只能提出候选记忆、候选 Pattern、检索扩展词和行动建议。
- LLM 输出不能直接写入 verified memory。
- `assistant` 来源默认只能进入 `ambiguous`。
- HyDE 输出属于 `synthetic` 检索辅助文本，不是事实证据。
- negative memory 是 avoidance memory，不是应被丢弃的垃圾。
- Layer 3 存 Pattern，不直接存 raw chunk，且默认 `provisional`。
- Layer 3 的核心用途不是“再存一层记忆”，而是把 verified experience 晋升为可复用、
  可挑战、可回滚、可替换的 execution path。
- RAG 负责证据检索，GBrain 负责关系图谱。
- MemoryWeaver Harness 负责判断、调度、晋升、降权和防污染。
- Harness 还负责执行前动作校验和执行后轨迹调节。
- LLM 可以维护候选图谱、候选摘要和候选分支，但不能直接维护 verified memory
  或 stable Pattern。
- 更完整的 GBrain 前移、edge 分层和 runtime graph authority 是 v0.8 方向，
  不是当前 v0.7 原型的既有能力。

## 总体流程

```mermaid
flowchart LR
    U["User / Application"] --> EC["Environment Contract"]
    EC --> H["MemoryWeaver Harness"]
    H --> RT["Router + Skill Retrieval"]
    RT --> L["LLM"]
    RT --> M["Memory Store"]
    RT --> G["GBrain"]
    RT --> R["RAG Evidence Layer"]
    RT --> AG["ActionGate"]
    AG --> T["Tools"]
    T --> F["Tool Feedback"]
    F --> TR["TrajectoryRegulator"]
    TR --> H
    L --> P["Candidate proposals"]
    P --> H
    R --> E["Evidence with provenance"]
    E --> H
    G --> X["Related entities and patterns"]
    X --> H
    H --> J["Judge: accept / reject / quarantine / promote / demote"]
    J --> M
    J --> G
```

## 组件职责

| 组件 | 负责 | 不负责 |
| --- | --- | --- |
| Harness | 校验、调度、晋升、降权、防污染、冲突处置、动作校验、轨迹恢复 | 因为 LLM 输出流畅就直接信任 |
| LLM | 推理、候选记忆、候选 Pattern、查询扩展 | 直接写 verified memory |
| Memory Store | 保存记忆、生命周期、来源、效用信号 | 把编辑次数当成成功使用次数 |
| GBrain | 实体、记忆、Pattern、证据之间的关系 | 替代 RAG 证据检索 |
| RAG Evidence Layer | 清洗、分块、索引、召回、重排、引用 | 把 synthetic 文本晋升为事实 |
| Router | 在策略约束下选择 fast / thinking / fast+verify | 绕过 Harness 或 RetrievalPolicy |
| Environment Contract | 明确工具 schema、权限、source authority 与环境约束 | 允许模型自行发明规则 |
| ActionGate | 在执行前校验参数、权限、危险操作、幂等和确认要求 | 用第二个 LLM 替代确定性校验 |
| TrajectoryRegulator | 检测重复失败、停滞、预算耗尽和恢复条件 | 无限重试或偷偷执行高风险 fallback |
| Tool Feedback | 提供结构化、可验证的执行结果 | 未经 Harness 判断直接成为 verified memory |

## 当前实现

当前仓库已实现以 JSON 原型为基础的 runtime-memory 子集：

| 文件 | 当前能力 |
| --- | --- |
| `memoryweaver/schema.py` | Layer 1/2 `MemoryItem`、canonical `Pattern`、`Source` enum 与生命周期信号 |
| `memoryweaver/store.py` | JSON 持久化、`MemoryWorkspace`、CRUD、tag / polarity / layer / status 查询、中文与中英混合 lexical 相似度 |
| `memoryweaver/policy.py` | `MemoryPolicy`、`RetrievalPolicy`、最小 `ActionPolicy` |
| `memoryweaver/contract.py` | `EnvironmentContract`、`ToolContract`、`SourceAuthority` |
| `memoryweaver/action_gate.py` | 结构化 `ActionProposal` 与确定性 `ActionGate` |
| `memoryweaver/trajectory.py` | 最小 `TrajectoryRegulator`：重复失败、停滞、预算限制 |
| `memoryweaver/skill.py` | 基于 Layer 3 Pattern 与 avoidance memory 的 procedural skill retrieval |
| `memoryweaver/harness.py` | 显式 lifecycle orchestration：交互前、条件化、执行前、反馈后、结果后 |
| `memoryweaver/evidence.py` | `EvidenceNode`、`EvidenceLink`、`EvidencePacket` 与证据持久化 |
| `memoryweaver/composer.py` | `PatternStore` 与显式 provisional `PatternComposer` |
| `memoryweaver/context_schema.py`、`context_store.py`、`content_router.py`、`tag_time_index.py` | RAW-to-capsule 压缩、可逆 raw retrieval、tag/time lookup |
| `memoryweaver/graph_schema.py` | 最小 Graph node、edge、proposal schema |
| `memoryweaver/graph_store.py` | JSON-backed candidate graph store |
| `memoryweaver/graph_linker.py` | 手动 / 规则式 tag-memory-evidence-pattern 边建立 |
| `memoryweaver/graph_retriever.py` | 一跳 tag expansion 与 graph candidate narrowing |
| `memoryweaver/gbrain.py` | workspace graph sync 与 mind-map projection |
| `memoryweaver/config.py` | 可选 LLM graph proposal 配置，默认关闭 |
| `memoryweaver/providers/` | OpenAI / Anthropic / DeepSeek / Qwen / local provider skeletons |
| `memoryweaver/graph/` | `LLMGraphProposalService`、review policy、reviewed linker |
| `memoryweaver/lifecycle.py` | verified write、Pattern compose/rollback、marker context writes、GBrain sync |
| `memoryweaver/runtime_authority.py` | runtime marker activation、source-gated context、decision ledger |
| `memoryweaver/runtime/harness_runtime.py` | 最小 Evidence-Gated Runtime Path：condition、action policy、validation gate、fallback、rollback rule |
| `memoryweaver/runtime/live_loop.py` | tau-style live loop，串联 runtime authority、ActionGate、trajectory gate |
| `memoryweaver/integrations/`、`external/`、`evaluation/` | 外部数据 adapter、LME-V2 模块、v0.7 经验迁移协议、Layer-3 path-promotion 协议 |
| `memoryweaver/cli.py` | `mw validate`、`doctor`、memory、evidence、pattern、route、graph、context、external、gbrain、skill、harness、contract、action、trajectory、layer、eval |
| `memoryweaver/scorer.py` | access、use、validation、success、correction、confidence；不自动创建 Layer 3 |
| `memoryweaver/extractor.py` | 中英文规则式 feedback 分类与事件检测 |
| `memoryweaver/router.py` | 消费 policy-filtered memory 与 canonical Pattern 的 fast / thinking / fast+verify 路由 |
| `memoryweaver/retriever.py` | source-aware 文本与 tag 检索、status gate、synthetic 隔离 |
| `memoryweaver/contradiction.py` | 已知冲突对的 SILENT / WARN / BLOCK 处置 |

## 当前缺口

以下能力尚未落地：

- production 级 `HarnessRuntime` durable 端到端判断链。
- 自动发现冲突候选的 `ConflictDetector`。
- checkpoint、Event Journal、幂等恢复与 CLI job queue。
- 更完整的 `EnvironmentContract` / `ActionGate` / `TrajectoryRegulator`，包括用户确认、
  审计、恢复路径与 worker 隔离。
- 更完整的 `SkillRetriever` / `HarnessRuntime`，包括 checkpoint、context pack、
  event journal、真实 ToolGateway 和跨步骤状态恢复。
- production 级 GBrain 图谱存储与关系查询。
- 多跳图谱 expansion、alias merge、temporal graph 和 graph maintenance。
- RAG 证据层、向量数据库、Hybrid Retrieval 与 rerank。
- Layer 2 / Layer 3 层的完整 GBrain edge status（candidate / verified / runtime）
  与“early-link, late-authorize”激活顺序。

P0 source gate、tag gate、Router gate 与 heat 生命周期拆分已通过五轮验证，详见
[P0 trust-boundary report](./validation/p0-trust-boundary-2026-06-02/README.md)。

ReAct 在线循环、CLI job queue、会话 checkpoint、缓存治理和容量规划见
[react_agent_runtime.md](./react_agent_runtime.md)。

GBrain 图谱节点、Layer 2 tag 投影、短中长期 memory 映射和快速回退阶梯见
[gbrain_graph_memory.md](./gbrain_graph_memory.md)。

## v0.8 搭建状态

v0.8 integrated substrate 已经落地并有独立验证 artifact：

- RAG Evidence Layer：返回带 `source_uri`、`document_version`、`content_hash`
  的 citable evidence refs。
- GBrain v0.8：支持 candidate bundle ingestion、原始 `search`、合成 `think`
  和 mind-map projection。
- Collaborative Specialist Routing：L0 tag/source/scope/time、L1 RAG/GBrain
  specialist 共同产出结构化 `EvidencePacket`。
- Checkpoint / resume：通过 durable runtime store 完成 checkpoint roundtrip。
- Authority boundary：RAG、GBrain、specialist、HyDE 均不能直接写 verified
  memory 或 stable Layer-3 Pattern。

对应验证见
[v0.8-integration/README.md](./validation/v0.8-integration/README.md)：
`rag_evidence_hit_count = 3`、`citation_coverage = 1.0`、
`gbrain_candidate_node_count = 2`、`gbrain_candidate_edge_count = 1`、
`specialist_run_count = 3`、`checkpoint_resume_success = true`、
`pass^3 = true`，并保持 `verified_memory_write_count = 0`、
`layer3_mutation_count = 0`、`promotion_without_hard_evidence_count = 0`。

因此 0.9 不再负责继续搭建基础框架。0.9 只负责 production-grade 优化、外部
benchmark 扩展、容量/压力/雪崩测试、provider fallback、向量库/HNSW 和多跳图谱
性能优化。

生命周期 Harness、权限等级和 LIFE-HARNESS 映射见
[life_harness_notes.md](./life_harness_notes.md)。

## 生命周期介入点

借鉴 LIFE-HARNESS，但不直接复制其 benchmark runtime。MemoryWeaver 的目标介入点：

| 阶段 | Harness 介入 |
| --- | --- |
| 交互前 | 加载环境合同、工具约束、来源权威和检索策略 |
| 任务条件化 | 检索 Layer 3 procedural skill、GBrain 上下文和 RAG evidence |
| 执行前 | `ActionGate` 校验结构、权限、风险、幂等和用户确认 |
| 执行后 | `TrajectoryRegulator` 检测重复失败、停滞、超时和预算耗尽 |
| 任务完成后 | 记录候选记忆、bad case、效用和回归 fixture |

优先使用确定性 gate。LLM 可提出候选规则、技能和恢复路径，但不能绕过 gate。

## HarnessRuntime 最小核心

当前 `memoryweaver/runtime/harness_runtime.py` 已落地最小 runtime path 结构。它不是
prompt snippet，也不是普通 memory retrieval，而是：

```text
condition -> action policy -> validation gate -> fallback -> rollback rule
```

promotion 输入优先使用硬证据：

- 工具返回结果。
- 测试是否通过。
- 用户显式纠错。
- 文件 diff 是否符合预期。
- benchmark score 是否改善。
- 同类任务重复验证次数。
- 反例数量。
- 冲突证据。
- 时间衰减。
- rollback 记录。

模型自信度只能作为候选说明，不计入默认 promotion。新验证线
`benchmarks/harness_runtime_core.py` 覆盖 50 个 `invalid_action` 同类任务，并比较
`no_memory`、`naive_memory`、`summary_memory`、`retrieval_memory` 与
`memoryweaver_harness_runtime`，同时包含冲突触发 rollback 与 rollback 后恢复任务。

当前还提供最小 `RuntimePathStore`，用于把 runtime path spec、硬证据和 ledger
持久化为 JSON，并在新 runtime 中恢复。它不是 production checkpoint / event journal，
但已经覆盖跨会话路径复用的最小状态边界。

更偏 v0.8 的推荐演化方向不是“继续堆 memory item”，而是：

```text
RuntimeTrace -> CandidatePath -> Evidence Gate -> Guarded Replay -> Rollback
```

也就是借鉴 LOOP/trajectory replay 的“记录与复放”直觉，但把真正的晋升权保留在
MemoryWeaver 的硬证据 gate 中；同时把 LangGraph 一类系统放在执行编排底座层，而不让
它替代 verified experience 的判断权。

可参考但不等价的现成基础：

- OPA/Rego 类 policy engine：适合借鉴“策略判断与业务代码分离”，但不处理经验晋升。
- Temporal saga / compensation：适合借鉴可审计 rollback 和补偿动作，但不处理 agent memory。
- LangGraph durable execution：适合借鉴 checkpoint、human-in-the-loop 和 time travel，
  但不定义 promotion precision。
- LOOP Skill Engine：适合借鉴首次成功轨迹记录、模板抽取和确定性复放直觉，但不能把
  “成功一次即可复放”当作晋升标准。
- SWE-bench：适合借鉴 test/pass/fail 作为 coding-agent 硬证据。
- AgentDojo、ToolEmu、tau-bench：适合借鉴 tool-use 风险、动态任务与安全评测。
- Voyager skill library：适合借鉴可复用 skill 经验，但 MemoryWeaver 需要额外的
  source gate、contradiction、negative memory 和 rollback。

更完整的“外部系统 / 论文 -> 可借能力 -> 不该借的部分 -> MemoryWeaver 对应层”
见 [reference_mapping.md](./reference_mapping.md)。
LangGraph substrate 与 trace-to-path 结合方向见
[langgraph_trace_to_path.md](./langgraph_trace_to_path.md)。

因此 MemoryWeaver 的差异点不是“有记忆”，而是把硬证据治理、路径晋升、运行时复用和
回滚放在同一个可审计 harness 中。

## 记忆层

| 层级 | 用途 | 内容 |
| --- | --- | --- |
| Layer 1 | 候选记忆 | 用户、工具、终端、assistant 提出的待判断信息 |
| Layer 2 | 激活 / 验证记忆 | 经过外部证据或任务结果支持的可复用记忆 |
| Layer 3 | Pattern / Execution Path | 从多条记忆与证据组合出的可复用执行路径 |

raw chunk 属于 RAG Evidence Layer。Layer 3 只保存 Pattern，并通过 provenance
链接回 supporting memories 与证据。

当前 SDK 规则：

- 新 `MemoryItem` 只允许 Layer 1 / Layer 2。
- 旧 JSON 中的 Layer-3 `MemoryItem` 仅作为 legacy 读取，并在 validate 中警告。
- `PatternComposer` 是创建 Layer-3 Pattern 的唯一入口。
- Layer 3 is provisional by default.
- `stable` Pattern 必须显式验证，不后台晋升、不自动泛化。
- Layer 3 的晋升目标是“更好的路径”，而不是“更多的 Pattern 数量”。
- LLM 维护的 GBrain、思维导图或分支存储只能作为 candidate structure，由 Harness
  和 policy gate 判断后才能影响 verified memory 或 stable Pattern。

## 来源模型

目标实现应使用 `Source` enum，而不是裸字符串：

| Source | 默认处理 |
| --- | --- |
| `USER` | 候选输入，按策略判断是否可晋升 |
| `ASSISTANT` | 强制 `ambiguous`，不得自动 verified |
| `TERMINAL` | 可验证观察，保留执行上下文 |
| `TOOL` | 可验证观察，校验工具与参数 |
| `FILE` | 带路径、版本或 hash 的证据 |
| `WEB` | 带 URL、时间戳与版本的外部证据 |
| `COMPOSER` | 推断出的候选 Pattern |
| `SYNTHETIC` | HyDE 等合成文本，只用于检索 |

## 检索边界

所有公开检索入口都应进入统一的策略门：

```mermaid
flowchart LR
    Q["Query"] --> RP["RetrievalPolicy"]
    RP --> VR["VerifiedRetriever"]
    VR --> TS["Text similarity"]
    VR --> TG["Tag search"]
    VR --> GS["Graph expansion"]
    TS --> MG["Merge and deduplicate"]
    TG --> MG
    GS --> MG
    MG --> RR["Rerank"]
    RR --> C["Policy-filtered context"]
```

当前 `MemoryStore` 的原始查询可保留为内部能力，但 Router、示例和未来 Agent
adapter 不应直接调用它们。

## 生命周期信号

当前原型已经拆分：

- `updated_at`：内容或元数据发生变化。
- `accessed_at`：记忆被检索。
- `used_at`：记忆参与了行动。
- `validated_at`：结果被用户、工具或终端证据确认。
- `heat`：按策略统计检索或有效使用，不因普通编辑自动上升。

后续 Policy 层还应加入：

- `positive_utility`：使用后帮助成功的证据。
- `avoidance_utility`：阻止已知失败路径的价值。

`confidence` 表示可信度，不应把 positive utility 与 negative avoidance
压缩成一个互相抵消的比例。

## Collaborative Specialist Routing

后续 Router 应逐级调用 specialist，而不是一次拉起所有昂贵能力：

```mermaid
flowchart LR
    Q["Query"] --> L0["L0: tag / source / scope / freshness"]
    L0 --> EP["EvidencePacket"]
    EP --> R{"Need escalation?"}
    R -- "No" --> F["Fast or Fast + Verify"]
    R -- "Recall weak or conflict" --> L1["L1: RAG / GBrain / ConflictDetector"]
    L1 --> EP
    R -- "High risk or unresolved" --> L2["L2: high-end model maintenance"]
    L2 --> EP
    EP --> L["LLM proposes"]
    L --> H["Harness judges"]
```

该设计参考 [GSCo / MedDr](https://github.com/sunanhe/MedDr) 的
generalist-specialist collaboration，但 MemoryWeaver 的 specialist 输出只能进入
结构化 `EvidencePacket`。LLM 和 specialist 都不能直接写 verified memory。

完整设计、开源项目组合与 benchmark 指标见
[collaborative_specialist_routing.md](./collaborative_specialist_routing.md)。
