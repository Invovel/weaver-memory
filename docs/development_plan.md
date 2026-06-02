# MemoryWeaver Development Plan

## 当前判断

截至 2026-06-02，仓库已有 Sprint 0 原型和经过验证的 P0 anti-pollution 增量：

- 基础 schema、JSON store、scorer、extractor、router。
- `VerifiedRetriever`。
- `ContradictionResolver`。
- 79 个 pytest 测试通过。
- P0 source gate、tag gate、Router gate 与 heat 生命周期拆分已经完成五轮验证。

完整实验记录见
[P0 trust-boundary report](./validation/p0-trust-boundary-2026-06-02/README.md)。
下一步先补 CLI 与中文 baseline，再进入 Policy、Pattern、Graph 和 RAG。

## 开发规则

- 保留 **LLM proposes, Harness judges**。
- 每个步骤保持现有测试通过，并增加针对性回归测试。
- 优先小改，不在同一个提交中同时引入 enum、策略层、图谱和向量库。
- README 只声明已经落地且被测试覆盖的能力。

## Sprint 0.1：修正原型边界

### Step 1：补齐 CLI 或移除入口声明

涉及文件：

```text
pyproject.toml
memoryweaver/cli.py
tests/test_cli.py
```

原因：

`pyproject.toml` 当前声明 `mw = "memoryweaver.cli:main"`，但 `memoryweaver/cli.py`
不存在。最小方案是补一个可运行的 CLI 骨架。

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

### Step 6：改善中文相似度 baseline

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
- 英文 baseline 不回退。

## Sprint 1：策略、Pattern 与冲突

### Step 7：引入 Policy

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

### Step 9：统一 Pattern 存储

新增文件：

```text
memoryweaver/composer.py
tests/test_composer.py
```

当前示例同时创建 `Pattern` 和 Layer-3 `MemoryItem`。应确定一个持久化模型，并由
`PatternComposer` 负责 provenance、supporting memory 和晋升条件。

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

## Sprint 2：GBrain 与 RAG

1. 按 [gbrain_graph_memory.md](./gbrain_graph_memory.md) 引入 GBrain adapter，
   保存实体、关系、Layer 2 tag 投影和 Pattern lineage。
2. 按 [rag_evidence_layer.md](./rag_evidence_layer.md) 实现证据层。
3. 接入 sparse + multilingual dense retrieval。
4. 数据规模需要时加入 HNSW。
5. 加入 Hybrid Retrieval、rerank 与严格标记为 `SYNTHETIC` 的 HyDE。

协作式 specialist 路由按
[collaborative_specialist_routing.md](./collaborative_specialist_routing.md)
逐级落地：先 L0 deterministic specialist，再 L1 RAG / GBrain，最后才允许 L2
高端模型参与离线维护。所有 specialist 输出先进入结构化 `EvidencePacket`。

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
