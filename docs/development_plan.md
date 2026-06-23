# MemoryWeaver Development Plan

## 当前判断

截至 2026-06-09，仓库已经超出最初的 SDK v0.2.0 provisional-pattern foundation。
当前 worktree 里，主线已经从“安全存记忆”推进到“Layer-3 path promotion”：

- 基础 schema、JSON store、scorer、extractor、router。
- `VerifiedRetriever`、`ContradictionResolver`、`MemoryPolicy`、`RetrievalPolicy`。
- `PatternStore`、`PatternComposer`、`record_path_trial()`、`select_best_path()`。
- `EnvironmentContract`、`ToolContract`、`SourceAuthority`。
- `ActionProposal`、`ActionGate`、`TrajectoryRegulator`。
- `ContextCapsule`、`RawSpan`、`TagTimeIndex`、`ContentRouter`。
- 最小 candidate graph / tag-linking 与 `GBrain` sync / projection。
- `SkillRetriever`、`MemoryWeaverHarness`、tau-style `live_loop`。
- `mw` CLI 已暴露 pattern trial / best-path、skill、harness、contract、action、trajectory、eval path-promotion。
- 专门的 Layer-3 path-promotion 协议、benchmark 与 validation artifact 已落地。
- 当前全量 `pytest` 为 340 passing tests。
- P0 source gate、tag gate、Router gate 与 heat 生命周期拆分已经完成五轮验证。

完整实验记录见
[P0 trust-boundary report](./validation/p0-trust-boundary-2026-06-02/README.md)。
当前最重要的判断不再是“继续补 marker 或 retrieval speed 对比”，而是：

> **继续把 verified experience 晋升成更好的 Layer-3 execution path，并证明这种路径晋升在 sibling tasks 上可复用、可替换、可回滚。**

当前结论边界：

- 当前仓库已经证明 Layer-3 path promotion 的最小闭环：stable promotion、best-path selection、
  stale-path suppression、rollback、zero path regret，并且已经有独立 benchmark /
  validation artifact。
- 当前 deterministic trace-loop 已经有 `pass^3` artifact；这不能替代 live LLM 路线的
  `pass^3`。
- 当前已有一次 live LLM bridge run 与 live `pass^3` artifact：真实模型只能提出动作或候选路径，
  Harness 记录 tool result、test result、diff validity、benchmark delta、conflict、rollback，
  再决定是否晋升。
- 当前仓库仍未证明真实开放环境中的长期任务成功率提升。
- 下一篇主实验应该围绕 Path Promotion，而不是 marker novelty 或 retrieval speed。
- LLM 可以维护候选图谱、候选摘要和候选分支；不能直接维护 verified memory 或
  stable Pattern。
- 当前 graph 仍不直接改变 Layer 3 生命周期；v0.8 已把 GBrain 升级为
  authority-limited candidate / search / think / mind-map substrate，但 Harness
  仍然保留晋升和回滚裁决权。
- API 的作用是低权限地产生候选图谱操作，真正变化必须通过 proposal acceptance、
  recall、candidate reduction 和 wrong link rate 体现。
- v0.8 已落地为 integrated substrate：RAG evidence layer、GBrain candidate graph、
  collaborative specialist EvidencePacket、checkpoint/resume substrate 与 pass^3
  validation 同时存在，且仍保持 `verified_memory_write_count = 0`、
  `layer3_mutation_count = 0`、`promotion_without_hard_evidence_count = 0`。
- 0.9 不再负责继续搭建这些基础件；实验冻结窗口内只继续运行已列入
  validation guide 的 sanity check、evidence reliability 与 claim mapping，不新增
  benchmark、adapter、agent loop、marker 类型、GBrain 功能或 LLM provider。

当前不实现的原因：

- Layer3 MVP、experience-transfer、live LLM、coding-debug 和 v0.8 integrated
  substrate 均已有可运行 validation line；剩余工作是把 artifact 口径继续收紧，
  而不是继续推迟 v0.8 搭建。
- COLM 2026 截止前，优先级应是把 v0.7 的 path-promotion、safety、reliability 叙事
  与测试结果收口，而不是叠加一次 GBrain 激活顺序重构。
- “Early-link, late-authorize”已经以 authority-limited 的 v0.8 方式落地：GBrain
  可接收 candidate bundle，RAG 可返回 citable evidence，specialist 可输出
  EvidencePacket，但它们都不能直接写 verified memory 或 stable Pattern。

推荐中的 v0.8 运行时组合见 [langgraph_trace_to_path.md](./langgraph_trace_to_path.md)。

v0.8 集成验证见 [v0.8 Integration Validation](./validation/v0.8-integration/README.md)。

## v0.7 收口新增门槛

这两个门槛已经有最小 live bridge artifact，但仍不能外推到开放任务成功率：

1. **一次 live LLM run（已完成最小 bridge）**：在同一任务族上让真实 LLM 产生动作提案或候选路径，Harness
   只接受结构化 proposal，并记录外部证据。合格产物至少包括 `raw_results.json`、
   `task_runs.jsonl`、`decision_probe.jsonl` 或 runtime trace、tool result、测试 /
   diff / benchmark 证据、冲突证据与 rollback 记录。
2. **live LLM pass^3（已完成最小 bridge）**：固定 seed 或固定任务切片，重复运行 3 次，输出 `pass@1`、
   `pass^3`、关键指标均值 / 标准差，尤其是 `known_bad`、`invalid_action_rate`、
   `memory_induced_regression_rate`、`rollback_frequency` 和
   `promotion_precision`。

验收规则：

- 不能把 deterministic local policy 的 `pass^3` 当成 live LLM 可靠性证据。
- 不能把当前 live bridge 的 `pass^3` 外推成开放式长期任务成功率提升。
- live LLM 输出不能直接写入 verified memory 或 stable runtime path。
- promotion 依据必须来自工具返回、测试结果、用户显式纠错、diff 检查、benchmark
  score 改善、重复验证、反例、冲突、时间衰减和 rollback ledger。
- 如果 live run 引入 memory-induced regression，必须保留 rollback / demotion 记录，并在
  README 里明确写成失败或待修复结果。

## 开发规则

- 保留 **LLM proposes, Harness judges**。
- LLM 维护 GBrain、思维导图或分支存储时，只能产出 candidate structure。
- verified memory 和 stable Pattern 只能由 Harness policy 与验证结果显式产生。
- 每个步骤保持现有测试通过，并增加针对性回归测试。
- 优先小改，不在同一个提交中同时引入 enum、策略层、图谱和向量库。
- README 只声明已经落地且被测试覆盖的能力。

## 版本规划

### v0.2.1：稳定 SDK 与文档边界

目标是不扩展大系统，只稳定当前 SDK：

1. 把 validation 结果写进 README / docs。
2. 保留 `raw_results.json`。
3. 增加 changelog：v0.2.0 validated。
4. 明确 benchmark 是 correctness + local prototype benchmark，不是 production benchmark。
5. 把 Layer 3 provisional policy 写成硬规则。

### v0.3.0：Layer-3 Path Promotion 实验

目标是证明 verified experience 是否真的能晋升成更好的可复用执行路径。

新增数据资产：

```text
task_runs.jsonl
evaluation_metrics.json
case_studies.md
raw_events.jsonl
memory_items.jsonl
pattern_items.jsonl
evidence_links.jsonl
```

实验对照：

```text
no_path_promotion
retrieval_only
provisional_path
stable_path
```

核心指标：

- latest_path_selection_accuracy
- stale_path_suppression_rate
- rollback_success_rate
- false_stable_promotion_count
- average_path_regret
- sibling_task_path_reuse_rate

### v0.4.0：索引、冲突与最小图谱

再进入：

- `ConflictDetector`
- 更完整的 `EvidencePacket`
- SQLite / indexed backend
- simple vector backend
- minimal GBrain projection beyond the current candidate tag-linking layer

### v0.8：Integrated Substrate（已搭建）

目标不是重写成 orchestration framework，而是把 runtime path 主线与 RAG evidence、
GBrain candidate graph、specialist routing、checkpoint/resume 接成一个受 Harness
约束的完整 substrate：

```text
RAG Evidence -> GBrain Candidate Graph -> Specialist EvidencePacket
             -> LLM Proposal -> Harness Evidence Gate -> Runtime Path / Rollback
```

已完成的 v0.8 工作：

- `RAGEvidenceLayerV08`：确定性 evidence refs、chunk metadata、citation hash。
- `MemoryWeaverGBrainEngineV08`：candidate bundle ingestion、`search`、`think`、
  mind-map projection。
- `CollaborativeSpecialistRouterV08`：L0 / L1 specialists 产出 `EvidencePacket`。
- checkpoint/resume probe：durable runtime store roundtrip。
- benchmark：`benchmarks/v08_integration_validation.py`。
- artifact：`docs/validation/v0.8-integration/`，`pass^3 = true`。

明确边界：

- RAG、GBrain、specialist、HyDE 都不能直接写 verified memory 或 stable Pattern。
- v0.8 是完整搭建完成点；v0.9 只负责优化、外部 benchmark、容量/压力/雪崩测试和
  production-grade backend。

已先落地的 v0.4 前置边界：

- `.env.example`
- `MemoryWeaverConfig`
- provider skeletons：OpenAI、Anthropic、DeepSeek、Qwen、Local
- `LLMGraphProposalService`
- `GraphProposalReviewPolicy`
- `ReviewedGraphLinker`
- validation：manual graph vs rule graph vs llm proposal graph

## Sprint 0.1：修正原型边界

### Step 1：补齐 CLI 或移除入口声明（已完成）

涉及文件：

```text
pyproject.toml
memoryweaver/cli.py
tests/test_cli.py
```

原因：

`pyproject.toml` 当前声明 `mw = "memoryweaver.cli:main"`，但 `memoryweaver/cli.py`
不存在。SDK v0.2.0 已补齐可运行 CLI。

预期测试：

- `memoryweaver.cli:main` 可导入。
- `mw --help` 成功退出。

### Step 2：拆分 update 与 heat（已完成）

涉及文件：

```text
memoryweaver/schema.py
memoryweaver/store.py
memoryweaver/scorer.py
tests/test_schema.py
```

原因：

当前 `touch()` 同时更新 `updated_at` 和 heat，导致编辑、晋升、降权、归档都被算作
“使用记忆”。应拆分 `mark_updated()`、`record_access()` 和后续 validated use 信号。

预期测试：

- 普通 `store.update()` 不增加 heat。
- `record_access()` 增加 heat。
- promote / deprecate / archive 不伪造使用次数。

### Step 3：修复 tag 检索门控（已完成）

涉及文件：

```text
memoryweaver/retriever.py
tests/test_retriever.py
```

原因：

当前 `VerifiedRetriever.search_by_tags()` 只排序，不调用 source gate。assistant 来源
可以通过 tag 路径绕过 anti-pollution。

预期测试：

- 命中同一 tag 的零 heat assistant 记忆默认被排除。
- 显式 `include_unverified=True` 时仍只放行满足策略的候选。
- archived / deprecated 状态有明确策略。

### Step 4：让 Router 经过 verified retrieval（已完成）

涉及文件：

```text
memoryweaver/router.py
memoryweaver/retriever.py
tests/test_schema.py
tests/test_retriever.py
```

原因：

修复前 `ModeRouter` 直接调用 `MemoryStore.find_similar()`，未验证 assistant Pattern
可以触发 fast route。当前 Router 已改为使用策略过滤后的候选。

预期测试：

- 未验证 assistant 记忆不能触发 fast。
- verified Pattern 仍可触发 fast。

### Step 5：增加 Source enum 与写入约束（已完成）

涉及文件：

```text
memoryweaver/schema.py
memoryweaver/extractor.py
memoryweaver/retriever.py
memoryweaver/contradiction.py
tests/test_schema.py
tests/test_retriever.py
tests/test_contradiction.py
```

原因：

修复前 `source` 是裸字符串，且允许直接构造 `source="assistant"`、
`polarity=positive`、`confidence=1.0`。当前已增加 enum、assistant 默认
`ambiguous` 和 confidence 上限约束。

预期测试：

- 非法 source 被拒绝。
- assistant 默认强制 ambiguous。
- assistant 不可直接成为 verified memory。
- 为旧 JSON 数据提供清晰迁移行为。

### Step 6：改善中文相似度 baseline（已完成）

涉及文件：

```text
memoryweaver/store.py
memoryweaver/router.py
tests/test_schema.py
```

原因：

当前文本检索使用 whitespace `split()`，中文句子通常会被当成单个 token。Sprint 0
可先使用简单 tokenizer 或字符 n-gram；向量检索留给 RAG 阶段。

预期测试：

- 同义域中文短句可召回相关记忆。
- 中英混合 package、version、error code token 不回退。
- 英文 baseline 不回退。

## Sprint 1：策略、Pattern 与冲突

### Step 7：引入 Policy（已完成）

新增文件：

```text
memoryweaver/policy.py
tests/test_policy.py
```

包含：

- `MemoryPolicy`：写入、晋升、降权与来源约束。
- `RetrievalPolicy`：来源、状态、层级、confidence 和 synthetic 可见性。

### Step 8：拆分可信度与效用

涉及文件：

```text
memoryweaver/schema.py
memoryweaver/scorer.py
tests/test_schema.py
```

目标：

- `confidence` 表示可信程度。
- `positive_utility` 表示成功贡献。
- `avoidance_utility` 表示避坑价值。
- negative memory 不因 correction 多而自动成为低价值垃圾。

### Step 9：统一 Pattern 存储（已完成）

新增文件：

```text
memoryweaver/composer.py
tests/test_composer.py
```

当前示例已改为只创建 canonical `Pattern`。`PatternComposer` 负责 provenance、
supporting memory、EvidenceLink 和显式 stable 晋升条件。Layer 3 is provisional by default.

### Step 10：补 ConflictDetector

新增文件：

```text
memoryweaver/conflict_detector.py
tests/test_conflict_detector.py
```

当前 `ContradictionResolver` 只能处置一对已经知道互相冲突的记忆。`ConflictDetector`
负责发现冲突候选，再交给 resolver。

## Sprint 1.5：生命周期 Harness

参考 [life_harness_notes.md](./life_harness_notes.md)，先实现确定性 gate，不引入
单体式 LLM supervisor。

### Step 11：环境与工具合同

当前状态：

- 最小 `contract.py` / `tests/test_contract.py` 已落地。
- 当前实现提供默认 live-loop `EnvironmentContract`、`ToolContract`、`SourceAuthority`。
- 仍未覆盖：持久化合同注册表、跨环境版本迁移、assistant 提议的离线合同 review。

新增文件：

```text
memoryweaver/contract.py
tests/test_contract.py
```

包含：

- `EnvironmentContract`
- `ToolContract`
- `SourceAuthority`

预期测试：

- 非法工具、缺失参数和越权 scope 被拒绝。
- 合同版本可追溯。
- assistant 提议不能直接修改合同。

### Step 12：执行前 ActionGate

当前状态：

- 最小 `action_gate.py` / `tests/test_action_gate.py` 已落地。
- 当前实现提供结构化 `ActionProposal`、`ActionGate`、`ActionPolicy`，并接入 v0.7 live loop。
- 仍未覆盖：真实 ToolGateway、用户确认持久化、worker 级幂等恢复、审计 bundle。

新增文件：

```text
memoryweaver/action_gate.py
tests/test_action_gate.py
```

包含：

- 结构化 `ActionProposal`
- `ActionPolicy`
- 危险动作确认
- 幂等键要求

预期测试：

- 高风险动作在未确认时 block。
- 已完成副作用不会重复执行。
- LLM 输出不能直接作为 Shell 命令运行。

### Step 13：执行后 TrajectoryRegulator

当前状态：

- 最小 `trajectory.py` / `tests/test_trajectory.py` 已落地。
- 当前实现提供重复失败、停滞、step/tool-call budget 与 recovery 建议，并接入 live loop。
- 仍未覆盖：token / wall-clock 预算、checkpoint 恢复、跨会话 trajectory compact。

新增文件：

```text
memoryweaver/trajectory.py
tests/test_trajectory.py
```

包含：

- 重复失败检测
- stagnation 检测
- step / token / wall-clock 预算
- recovery 建议与 safe-path 路由

预期测试：

- 相同失败动作达到阈值后停止循环。
- 超出预算时 checkpoint 并显式终止或转后台。
- recovery 可审计，不偷偷执行高风险动作。

## Sprint 2：GBrain 与 RAG（v0.8 已完成搭建，v0.9 优化）

v0.8 已完成最小可运行框架：

1. `RAGEvidenceLayerV08` 提供 citable evidence refs、chunk metadata、source URI、
   document version 和 content hash。
2. `MemoryWeaverGBrainEngineV08` 支持 candidate bundle ingestion、`search`、
   `think` 和 mind-map projection。
3. `CollaborativeSpecialistRouterV08` 将 L0 tag/source/scope/time 与 L1
   RAG/GBrain specialist 合并为结构化 `EvidencePacket`。
4. durable checkpoint/resume probe 已接入 v0.8 benchmark。
5. `docs/validation/v0.8-integration/` 记录 pass^3 artifact。

v0.9 的工作是优化和扩展，而不是继续搭建：

- 接入 sparse + multilingual dense retrieval 的 production backend。
- 数据规模需要时加入 HNSW。
- 加入 Hybrid Retrieval、rerank 和更完整的 HyDE 评估。
- 优化 multi-hop graph expansion、wrong-link rate、stale suppression。
- 扩大外部 benchmark、压力测试、雪崩测试和 provider fallback。

协作式 specialist 路由已经有最小实现；L2 高端模型维护、shadow、canary 与 rollback
属于 v0.9 优化阶段。所有 specialist 输出仍先进入结构化 `EvidencePacket`，不能直接
写 verified memory 或 stable Pattern。

## Sprint 3：ReAct 运行时

按 [react_agent_runtime.md](./react_agent_runtime.md) 分阶段实现：

1. 增加 checkpoint schema、Event Journal 和版本化 `ContextPack`。
2. 增加 bounded ReAct loop 与结构化 `ActionProposal`。
3. 通过 `ToolGateway` 和 job queue 隔离 CLI 执行。
4. 增加 RAG、GBrain、LLM、CLI 的独立熔断、指标和缓存 namespace。
5. 最后增加高端模型维护 Retrieval Plan DSL 的离线评估、shadow 和 canary 发布。

## 每一步完成标准

- 新增行为有回归测试。
- 全量 pytest 通过。
- README 与实际能力一致。
- Router 和 Agent adapter 不绕过策略层。
- synthetic、assistant 和 raw chunk 不会直接进入 verified memory。

测试分类、发布门禁、崩溃恢复、内存压力、雪崩、性能、安全、A/B 与灾备策略见
[testing_resilience_strategy.md](./testing_resilience_strategy.md)。

完整 Agent 测试目录见 [agent_test_catalog.md](./agent_test_catalog.md)。当前风险排序、
监测预警与原型 benchmark 见
[risk_assessment_and_benchmark.md](./risk_assessment_and_benchmark.md)。

失败样本归纳、回归固化和递进优化闭环见
[bad_case_learning_loop.md](./bad_case_learning_loop.md)。

生命周期 gate、权限等级和 LIFE-HARNESS 借鉴说明见
[life_harness_notes.md](./life_harness_notes.md)。
