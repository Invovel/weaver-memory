# MemoryWeaver

[English Version (英文版)](README.md) | [GitHub](https://github.com/Invovel/weaver-memory)

**面向长期 AI Agent 的反馈校准型路径晋升 Harness**

**LLM proposes. Harness judges.**

**核心 claim：** Layer-3 path promotion 会把 verified experience 晋升为可复用的 execution path。

从更上位的角度，当前框架也可以表述为：
**受证据治理、感知循环过程的路径记忆框架**。Retrieval Wear 是它在检索循环中的
实例：系统可以跨语义改写复用已验证检索路径，但当 evidence version 改变时必须让
旧路径失效并重新检索。

当前 50 个任务族的受控 Retrieval Wear 实验已经把这种机制与答案缓存、盲目路径复用
区分开。相比每轮重新运行 RAG，MemoryWeaver 将候选检查量从 `51,150` 降至
`34,422`，减少约 `32.7%`，同时保持 evidence hit rate = `1.0`。在受控 evidence
drift 后，答案缓存和无门控路径复用的 stale reuse rate 都是 `1.0`；MemoryWeaver
保持 stale reuse rate = `0.0`、path invalidation rate = `1.0`、rollback recovery
= `1.0`，并通过三次独立运行。详见
[`docs/validation/retrieval-wear-e2e/README.md`](docs/validation/retrieval-wear-e2e/README.md)。

MemoryWeaver 是一个实验性的 runtime path-evolution harness，用于把对话、终端输出、工具结果、用户纠正、任务结果转化为 verified experience，再通过 Layer 3 晋升为可复用、可试用、可稳定、可挑战、可回滚、可替换的执行路径。

与传统 RAG 不同，MemoryWeaver 使用**来源门控极性**和**矛盾检测**来防止 LLM 编造的内容污染记忆库。但这些治理层本身不是终点；它们的意义在于让 Layer 3 能持续筛出“当前最新、最合适、最可靠的路径”。

它也不是答案缓存：

```text
答案缓存：精确问题 → 已存答案

MemoryWeaver：
任务循环 → 检索 / 执行路径 → 证据门控
        → 受控复用 → 失效 / 回滚
```

它不是普通 RAG。

普通 RAG 更像：

```text
用户提问 → 检索文档 → 生成回答
```

MemoryWeaver 更关注：

```text
执行任务 → 观察结果 → 接收反馈 → 归档经验 → 下次复用 → 持续优化
```

它的目标是让 Agent 不只是“会查资料”，而是能逐渐记住：

* 什么方案有效
* 什么方案失败
* 什么信息只是背景
* 什么假设还没有验证
* 哪些记忆应该晋升
* 哪些记忆应该降权
* 哪些节点已经过时
* 哪些 tag 对某个 LLM 更有用

---

## 为什么需要 MemoryWeaver？

大多数 RAG 系统把记忆当成静态知识库。

MemoryWeaver 把经验看成一个持续演化的路径系统。

它适合长期运行的 AI Agent，尤其适合记录：

* 项目环境
* 终端报错
* 成功修复路径
* 失败尝试
* 用户纠正
* 用户偏好
* 工具调用历史
* 模型适配记忆格式
* 已过时或错误的假设
* 可复用的诊断模式
* 可复用的执行路径

适用场景包括：

* Coding Agent
* Vibe Coding 工作流
* AI 开发助手
* 技术支持 Agent
* 企业内部知识 Agent
* 研究助手
* 长期个人 AI 助手

---

## 核心思想

MemoryWeaver 使用分层记忆架构。

```text
用户 / 工具 / 终端事件
        ↓
RAW Event / RawSpan
        ↓
ContextCapsule + TagTimeIndex（已验证 v0.5.3）
        ↓
Harness 预标记
        ↓
第一层：候选记忆
        ↓
第二层：Verified Experience
        ↓
路径候选池 + Pattern 组合
        ↓
第三层：provisional Execution Path
        ↓
Runtime Trial
        ↓
Stable Path / Challenged Path / Rollback / Archive
```

完整闭环是：

```text
Observe → Verify → Promote Path → Trial → Reuse / Rollback → Improve
```

---

## Layer-3 路径晋升

Layer 1 和 Layer 2 提供材料。

Layer 3 才是发动机。

MemoryWeaver 的关键问题不只是“某条 memory 能不能安全存下来”，而是：

> 多条 verified experience 能不能被晋升成下一个任务更好的执行路径？

Layer-3 生命周期是：

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

当前原型已经显式保存一批 Layer-3 路径信号：

* `success_path`
* `failed_path`
* `validation_task_runs`
* `path_fitness_score`
* `trial_count`
* `success_count`
* `failure_count`
* `false_trigger_count`

这也是 MemoryWeaver 和普通 memory layer、静态 skill 包、普通 graph 最本质的区别：

> 它不是为了记住更多事实，而是为了不断晋升出更好的路径。

---

## ContextCapsule / TagTimeIndex（已验证 v0.5.3）

MemoryWeaver 已吸收类似 `headroom` 的上下文压缩思想，但只把它作为
**RAW 到 Layer 1 之间的压缩入口**，不让它替代 memory、evidence 或 policy。

已验证的数据流是：

```text
RAW Event
  完整 terminal log / tool JSON / code patch / conversation turn
        ↓
ContentRouter
  按内容类型走规则式压缩
        ↓
ContextCapsule
  短摘要 + tags + timestamp + raw_ref_id
        ↓
Layer 1 Candidate Memory
  从 capsule summary + tags 生成，但仍受 source gate 控制
```

吸收四个设计：

| 设计 | MemoryWeaver 改造方式 |
| --- | --- |
| ContentRouter | 将 `terminal_log`、`tool_json`、`code_patch`、`conversation_turn`、`trace_record` 分流给不同规则压缩器。 |
| 可逆压缩 | 保存完整 `RawSpan`；每个 capsule 保留 `raw_ref_id`，需要时恢复完整证据。 |
| Tag-Time 双索引 | 维护 `tag -> capsule_ids` 与 `time_bucket -> capsule_ids`，减少全文扫描。 |
| MarkerEvidenceContext | 给 HarnessMarker 绑定 required tags、time window、sources 和 preferred content types。 |

本阶段不吸收三个设计：

| 暂缓设计 | 原因 |
| --- | --- |
| Cross-agent memory | 当前 MemoryWeaver 的 scope 与 source 边界很强，跨 agent 共享会模糊信任边界。 |
| 无信任边界的自动压缩 | 压缩必须继承 raw input 的 `source`、`timestamp` 和 trust status。 |
| Cache alignment | 多 agent cache coherence 暂不属于当前 runtime demo 范围。 |

强制安全规则：

```text
Context compression cannot increase trust.
ContextCapsule cannot promote memory.
Compressed summaries cannot replace raw evidence.
Raw evidence must remain recoverable via raw_ref_id.
Capsule source and timestamp inherit from RawSpan unchanged.
```

v0.5.3 验证指标：

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

也就是说：headroom-style compression 负责降低上下文成本；MemoryWeaver 仍然负责决定哪些上下文有资格影响 runtime。

---

## 记忆分层

### 第一层：候选记忆

Harness 先做轻量级预标记。

这一层存放的是“可能有价值”的记忆候选，不立即假设它们正确或可复用。

例如：

```text
positive?
negative?
neutral?
ambiguous?
```

第一层允许粗糙、重复和模糊。

---

### 第二层：Verified Experience

当某条记忆被调用、被用户反馈、被工具验证，或者参与过任务解决，它就可以进入第二层。

第二层开始做质量分区：

```text
positive   → 有用、成功、被确认
negative   → 失败路径、错误假设、被纠正
neutral    → 稳定背景、上下文事实
ambiguous  → 未验证假设、待确认信息
```

---

### 第三层：provisional Pattern

第三层保存 canonical `Pattern` 记录，不再复制成 Layer-3 `MemoryItem`，也不保存
RAG raw chunk。

Layer 3 是一个 **路径晋升层**。新 Pattern 默认以 provisional execution path 的形式
存在，随后会根据任务结果被试用、稳定、挑战、回滚或归档。

一个 Pattern 可以由多个分区组合而来：

```text
positive + negative + neutral + ambiguous
```

例如：

```text
如果用户在 WSL 中成功安装了 Codex CLI，
且 codex --version 可以正常返回，
但仍然出现 subscription load failed，
不要优先建议重新安装 npm 或 Codex，
应该优先检查登录状态、组织选择或订阅权限。
```

第三层会被 harness 和检索系统共同使用，但不能由 Scorer 自动创建，也不能因为 RAG
召回就自动晋升。Pattern 创建必须经过 `PatternComposer`，路径晋升也必须经过显式的
trial / promotion / rollback 逻辑。

它用于决定：

* 是否走 fast mode
* 是否走 thinking mode
* 应该检索哪些记忆
* 应该避免哪些假设
* 应该优先尝试哪个执行路径
* 当前模型更适合哪种记忆格式

---

## 记忆极性分区

MemoryWeaver 使用四种主要记忆极性。

### Positive Memory：好的记忆

有用、成功、被验证的知识。

例如：

* 某个命令成功了
* 某个修复方案解决了问题
* 用户确认答案正确
* 工具结果验证了假设

---

### Negative Memory：不好的记忆

失败尝试、错误假设、被否定路径。

例如：

* 用户纠正了模型
* 某个命令失败
* 某个方案没有解决问题
* 之前的判断方向误导了后续回答

Negative memory 不应该直接删除，而应该变成 **避坑记忆**。

---

### Neutral Memory：中立记忆

稳定事实或背景上下文。

例如：

* 用户使用 WSL
* 项目使用 pnpm
* 当前仓库是 Next.js 项目
* 用户喜欢分步骤解释

---

### Ambiguous Memory：模糊记忆

尚未被验证的假设。

例如：

* 问题可能和组织选择有关
* 某个包版本可能不兼容
* 某个工具可能需要额外认证

模糊记忆后续可以升级为 positive、negative，或者被降权归档。

---

## Harness 的角色

MemoryWeaver 把 harness 视为整个系统的控制层。

治理不是目的。

治理是为了让 Layer 3 能持续晋升出更好的执行路径。

Harness 负责：

* 捕捉值得记忆的事件
* 对用户和工具交互做预标记
* 判断反馈是正向、负向、中立还是模糊
* 记录成功路径和失败路径
* 给记忆打分
* 决定记忆进入哪一层
* 更新热度、置信度和时效性
* 晋升或废弃记忆
* 选择 fast mode 或 thinking mode
* 学习哪些路径对某个 LLM 或工作流更可复用

可以理解为：

```text
LLM 负责推理
Tools 负责执行
Memory 负责存储
Harness 负责监听、评价、调度和归档
```

MemoryWeaver 正在从记忆 Harness 扩展为生命周期感知的运行时 Harness：交互前校准
环境合同，任务阶段检索过程性技能，执行前校验动作，执行后调节退化轨迹。这个方向
参考了 [LIFE-HARNESS](https://arxiv.org/abs/2605.22166)，详细映射见
[`docs/life_harness_notes.md`](docs/life_harness_notes.md)。

---

## Fast Mode 与 Thinking Mode

MemoryWeaver 支持自适应推理路由。

```text
新问题 / 不确定 / 高风险
        → Thinking Mode

相似问题 / 已验证 / 低风险
        → Fast Mode

历史相似但可能过期
        → Fast + Verify
```

这样可以实现：

```text
第一次深度思考
形成 verified experience
晋升到 Layer 3 执行路径
第二次相似问题快速复用
必要时轻量验证或回滚
```

---

## GBrain / 图谱记忆集成

MemoryWeaver 适合和图谱式记忆系统结合。

图谱记忆可以：

* 连接相关 tag
* 合并重复节点
* 检测过时知识
* 连接人物、项目、错误、工具和结果
* 把第二层的分区信号组合成第三层 Pattern

例如：

```text
WSL
+ Codex CLI
+ npm 全局安装成功
+ subscription load failed
+ 用户已创建 OpenAI API key
```

可以被组合为：

```text
Codex CLI 认证 / 订阅诊断 Pattern
```

---

## 建议记忆 Schema

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

## 建议 Pattern Schema

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
  "rule": "如果 X 和 Y 成立，则优先 Z，避免 A。",
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
  "promotion_reason": "多次检索后帮助解决相似任务"
}
```

---

## 来源门控防污染

MemoryWeaver 使用三层防护来防止 LLM 编造的内容污染记忆库：

### 1. 来源门控极性

每条记忆都有 `source` 字段。Assistant 生成的内容**永远**归类为 `ambiguous`，从不自动信任：

| 来源 | 允许的极性 | 原因 |
|------|-----------|------|
| `user` | positive, negative, neutral, ambiguous | 直接人类反馈 |
| `terminal` | positive, negative, neutral | 客观命令结果 |
| `tool` | positive, negative, neutral | 工具输出可验证 |
| `assistant` | **仅 ambiguous** | LLM 输出默认不可信 |
| `composer` | neutral, ambiguous | Pattern 组合是推断性的 |

Ambiguous 记忆只能通过外部验证（用户确认或终端验证）升级为 `positive` 或 `negative`。

### 2. 矛盾检测

当新记忆与现有已验证知识冲突时，三级严重度决定响应方式：

```
L1 (SILENT) — 两个都未验证 → 记录，不打断
L2 (WARN)   — 未验证 vs 可能过期的已验证 → 标注，谨慎继续
L3 (BLOCK)  — 已验证事实或用户偏好被推翻 → 停止，必须询问用户
```

`ContradictionResolver`（`memoryweaver/contradiction.py`）用优先级规则链实现，用户偏好和终端验证事实拥有最高权威。

### 3. 已验证检索

`VerifiedRetriever`（`memoryweaver/retriever.py`）在检索时按来源可信度过滤：

- User 和 terminal 来源始终通过
- Web 和 composer 来源通过置信度检查后放行
- **Assistant 来源且 heat=0 的记忆完全排除**
- Assistant 来源但 heat>0 的记忆仅在显式请求时才包含

这防止了自噬循环：`LLM 编造 → 存为记忆 → 下次检索到 → 强化编造`。

### 架构图

![MemoryWeaver 运行时架构](docs/assets/memoryweaver-architecture.png)

这是一张当前运行时架构图。仓库现在已经包含本地记忆核心、防污染原语、可逆
ContextCapsule 压缩、Layer-3 path promotion、runtime marker authority、第一版
生命周期 gate（`EnvironmentContract`、`ActionGate`、`TrajectoryRegulator`），以及
v0.8 integrated substrate：RAG evidence、GBrain candidate graph、specialist
EvidencePacket routing 和 checkpoint/resume。生产级向量库、多跳图数据库、CLI job
隔离、更广泛 provider coverage 和大型外部 benchmark 优化属于 v0.9 工作，而不是
v0.8 继续搭建。

---

## 当前模块结构

```text
memoryweaver/
├── memoryweaver/
│   ├── __init__.py
│   ├── schema.py              # MemoryItem, Pattern, 枚举类型
│   ├── store.py               # JSON 本地存储 + MemoryWorkspace
│   ├── policy.py              # MemoryPolicy、RetrievalPolicy、ActionPolicy
│   ├── contract.py            # EnvironmentContract、ToolContract、SourceAuthority
│   ├── action_gate.py         # 结构化 ActionProposal + ActionGate
│   ├── trajectory.py          # 重复失败 / 停滞 / 预算调节器
│   ├── skill.py               # 基于 Layer-3 Pattern 的 procedural skill retrieval
│   ├── harness.py             # 条件化、执行前、反馈后、结果后的生命周期总入口
│   ├── scorer.py              # 热度、置信度、freshness 信号
│   ├── extractor.py           # EventDetector + 中英文 FeedbackClassifier
│   ├── retriever.py           # VerifiedRetriever 来源感知检索
│   ├── router.py              # Fast / Thinking / Fast-Verify 模式路由
│   ├── contradiction.py       # ContradictionResolver (SILENT/WARN/BLOCK)
│   ├── evidence.py            # EvidenceNode、EvidenceLink、EvidencePacket、EvidenceStore
│   ├── composer.py            # PatternStore + 显式 PatternComposer
│   ├── context_schema.py      # RawSpan、ContextCapsule、MarkerEvidenceContext
│   ├── context_store.py       # RAW/context 存储与 raw_ref 可逆恢复
│   ├── content_router.py      # RAW 到 capsule 的规则压缩
│   ├── tag_time_index.py      # capsule 的 tag/time 索引
│   ├── marker_context.py      # MarkerEvidenceContext 检索辅助
│   ├── graph_schema.py        # GraphNode、GraphEdge、GraphProposal
│   ├── graph_store.py         # 候选图谱持久化
│   ├── graph_linker.py        # tag / memory / evidence / pattern 关联
│   ├── graph_retriever.py     # 图辅助候选缩小
│   ├── gbrain.py              # 图同步 + mind-map 投影
│   ├── lifecycle.py           # verified write、Pattern compose/rollback、marker 写入
│   ├── runtime_authority.py   # marker 激活 + hash-chained runtime 裁决
│   ├── cli.py                 # `mw` CLI
│   ├── runtime/
│   │   └── live_loop.py       # 带 ActionGate + trajectory guard 的 tau-style live loop
│   ├── external/              # 外部数据 schema、adapter、manifest
│   ├── integrations/          # LongMemEval-V2 风格集成
│   ├── evaluation/            # v0.7 经验迁移 + Layer-3 路径晋升协议
│   ├── graph/                 # LLM GraphProposal 生成 / review 辅助
│   └── providers/             # proposal 生成 provider skeleton
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

## 设计文档

- [`docs/architecture.md`](docs/architecture.md) — 系统边界与设计原则
- [`docs/life_harness_notes.md`](docs/life_harness_notes.md) — LIFE-HARNESS 启发的生命周期 gate
- [`docs/rag_evidence_layer.md`](docs/rag_evidence_layer.md) — 高性能证据检索
- [`docs/gbrain_graph_memory.md`](docs/gbrain_graph_memory.md) — 图谱记忆、tag 与 memory lifecycle
- [`docs/react_agent_runtime.md`](docs/react_agent_runtime.md) — ReAct、会话衔接、缓存治理与容量规划
- [`docs/collaborative_specialist_routing.md`](docs/collaborative_specialist_routing.md) — GSCo 启发的分层 specialist 路由与 EvidencePacket 边界
- [`docs/open_source_strategy_options.md`](docs/open_source_strategy_options.md) — 扩展大型子系统前需要讨论的实现策略
- [`docs/bad_case_learning_loop.md`](docs/bad_case_learning_loop.md) — bad-case 收集与递进优化
- [`docs/testing_resilience_strategy.md`](docs/testing_resilience_strategy.md) — 回归、崩溃、雪崩、压力、安全与 A/B 测试
- [`docs/risk_assessment_and_benchmark.md`](docs/risk_assessment_and_benchmark.md) — 当前风险与实测 baseline

---

## 原型 Benchmark

运行可复现的本地基线：

```powershell
python .\benchmarks\prototype_baseline.py
```

最新 `current-stage-check` artifact 在 Windows 11、Python 3.14.0 下的实测结果：

| Memory items | JSON 大小 | 写入吞吐 | Verified text search p95 |
| ---: | ---: | ---: | ---: |
| 100 | 89.3 KB | 127.68 items/s | 1.52 ms |
| 500 | 447.3 KB | 56.91 items/s | 6.04 ms |
| 1,000 | 894.8 KB | 31.82 items/s | 13.20 ms |

JSON 原型适合验证语义与回归，不适合生产级持续摄入。当前每次写入都会整体重写
JSON 文件。

P0 信任边界修复已经完成五轮独立验证。详见
[`docs/validation/p0-trust-boundary-2026-06-02/README.md`](docs/validation/p0-trust-boundary-2026-06-02/README.md)。

---

## Roadmap

### Phase 0：概念原型

* 定义 memory schema
* 定义四种记忆分区
* 使用本地 JSON 存储
* 支持手动打标签
* 支持基础 tag / 文本检索

### Phase 1：Harness MVP

* 事件检测器
* 反馈分类器
* 记忆评分器
* 第一层到第二层晋升
* fast / thinking 模式路由
* 终端输出摄入

### Phase 2：RAG 集成

* 接入向量数据库
* 接入 embedding 检索
* 添加热度和衰减机制
* 添加置信度和时效性
* 添加记忆冲突检测

### Phase 3：图谱记忆

* 添加 graph linking
* 把 positive / negative / neutral / ambiguous 组合成 pattern
* 检测过时节点
* 将高价值 pattern 晋升到第三层

### Phase 4：Agent 集成

* 添加 LangGraph adapter
* 添加 MCP 接口
* 添加 coding-agent 示例
* 添加 terminal tool memory loop
* 添加 model-specific memory profile

### Phase 5：评估系统

* 评估记忆检索是否有用
* 统计重复错误是否减少
* 统计用户纠正率是否下降
* 统计任务解决率是否提高
* 对比启用记忆和禁用记忆的 Agent 表现

### v0.5.x Runtime-Memory Roadmap

当前研究分支采用更细的 runtime-memory 路线：

```text
v0.5   Runbook Marker Trace Advantage Validation
       手动 CoreIssueNode / HarnessMarker fixture、shadow trace、
       counterfactual advantage metrics

v0.5.2 Active Marker Binding Preview
       marker 绑定 MarkerEvidenceContext -> ContextCapsule -> RawSpan，
       但 runtime_authority 保持 false

v0.5.2 Controlled Active Guard
       一个低风险 L1_hint marker 可以写入 route/evidence plan，
       L2/L3 marker 仍保持 preview-only

v0.5.2 L2 Route Approval
       L2_route marker 必须有显式 approval，才可以写入 route/evidence plan

v0.5.2.x Active route / guard marker + MarkerConflictResolver
       marker 可以在 policy 下建议 route / guard / evidence check

v0.5.3 ContextCapsule + TagTimeIndex
       RAW/Event 压缩、RawSpan 恢复、tag-time capsule lookup、
       MarkerEvidenceContext 绑定

v0.5.5 Drift detection + CoreIssueNode -> MarkerProposal
       使用 TagTimeIndex 作为 time-aware evidence source

v0.6   Semi-real trajectory experiment
       将 v0.5 dialogue cards 转成 no_memory / rag_over_logs /
       memoryweaver_runtime_marker replay trajectories

v0.6.1 Controlled harness run
       增加 deterministic harness policy loop 和 hash-chained decisions；
       live agent run 后续再做

v0.6.2 Live-lite harness
       执行 deterministic in-memory mock tools 并记录 tool results；
       真实 shell/network/tool execution 仍保持关闭
```

### 具体参考库吸收计划

MemoryWeaver 当前不把外部项目直接作为依赖并入，而是把可用设计吸收到 MemoryWeaver 自己的可审计模块中，并保持原有 trust boundary 不变。

| 参考项目 | 吸收到 MemoryWeaver 的位置 | 具体改动 | 当前不吸收 |
| --- | --- | --- | --- |
| headroom | RAW/Evidence 压缩层 | `ContentRouter`、`ContextCapsule`、`RawSpan`、`TagTimeIndex`、`MarkerEvidenceContext` 放在 RAW event 和 Layer 1 之间；通过 `raw_ref_id` 保持可逆恢复。 | Cross-agent memory、cache alignment，以及任何会改变 trust 的压缩。 |
| Zep / Graphiti | Temporal GBrain 模型 | 后续 graph node/edge 增加 `valid_from`、`valid_to`、`last_seen`、`freshness`、`supersedes`、`challenged_by`、episode provenance。 | 自动维护真值图谱，或直接晋升 verified memory。 |
| Codebase-Memory | Coding-agent demo 场景 | 优先做 coding/debug/configuration cards：命令、文件、配置、报错、成功修复、失败路径、evidence-first checks。 | v0.5 不做完整 Tree-sitter 代码图谱或 MCP 集成。 |
| LongMemEval / AgentRunbook | Runbook 表达方式 | 把 `Layer 3 Pattern + HarnessMarker` 表达成 MemoryWeaver Runbook Marker：issue、gotcha、required evidence、avoid path、route recommendation。 | 在真实 trajectory 实验前，不声称端到端任务收益。 |
| harness-forge | Runtime 工程化模型 | 扩展 `mw doctor`、`mw trace`、decision log、review view、approval record、bundle、sentinel-style offline check。 | 不复用 GPL 代码，不做 auto-tuning，不自动跨项目激活 learned pattern。 |
| OpenDB / SQLite FTS5 | 后续索引层 | v0.5+ 可对比 JSON scan 与 FTS/BM25-style indexing 在更大 memory set 上的扩展性。 | 在语义 gate 稳定前，不替换当前 JSON 原型。 |

硬边界：

```text
外部项目可以启发 retrieval、graph、compression 和 runtime UX。
但不能削弱 source gate、evidence check、Layer 3 lifecycle、online/offline separation。
```

### 后续测试准备

下一阶段测试按小步验证推进，不一次性跳到大系统：

```text
v0.5.2 Decision Ledger
       为 marker route-plan decision 生成 hash-chained decision records，
       记录 policy version、approval id、conflict refs、capsule refs、
       raw refs，以及 zero side-effect counters

v0.5.3.x ContextCapsule stress set
       从 40 条 RawSpan fixture 扩展到 dialogue-derived raw spans，
       统计 compression ratio、tag recall、raw recovery、time filtering、
       trust-inheritance violations

v0.5.4 Library-inspired retrieval comparison
       对比 baseline scan、TagTimeIndex lookup 和 graph-assisted
       candidate narrowing

v0.5.4a SQLite FTS5 frontend filter comparison
       对比 SQLite FTS5 全量检索、MW tag/time -> FTS5、
       MW graph/tag/time -> FTS5

v0.5.4b Safety filter independence
       独立验证 source gate、freshness 和 marker eligibility 这些 safety gate，
       不把它们混进相关性排序指标里

v0.5.5 Temporal GBrain drift validation
       测试 valid_from/valid_to、supersedes、challenged_by、stale evidence、
       CoreIssueNode/MarkerProposal candidates，但不改变 Layer 3 晋升规则

v0.5.5b Temporal graph ablation
       对比 static tag co-occurrence graph 和 MW temporal graph

v0.5.6 Dense / hybrid comparison
       等 FTS5 与 safety gate 分别验证后，再引入 dense / hybrid retrieval

v0.6 Semi-real trajectory experiment
       将 10-20 轮 dialogue-card trajectories 按 no_memory、rag_over_logs、
       memoryweaver_runtime_marker 三组 replay；统计 steps-to-success、
       user corrections、tool calls、known bad actions 和 repeated-error reduction

v0.6.1 Controlled harness run
       将同样三组 arm 放进 deterministic harness policy loop，
       为每个 task/arm pair 记录一条 hash-chained decision

v0.6.2 Live-lite harness
       对 known-bad actions、generic debugging 和 required evidence checks
       执行 deterministic in-memory mock tools
```

当前最近的测试契约：

```text
1. Decision ledger 必须通过 hash-chain 校验。
2. L2 route plan 必须有显式 approval。
3. L3 guard marker 保持 preview/shadow，除非后续 policy 授权。
4. ContextCapsule 必须能通过 raw_ref_id 恢复 raw evidence。
5. Capsule compression 不能提高 trust，也不能晋升 memory。
6. Online path 不能调用 LLM GraphProposal。
```

---

## 应用场景

### Coding Agent Memory

记住项目命令、环境限制、失败修复路径和成功方案。

### 技术支持 Agent

把历史工单变成诊断 Pattern，把失败方案变成避坑规则。

### 研究助手

追踪假设、证据、反例和不断变化的结论。

### 个人长期 AI 助手

记住用户偏好、长期目标、项目上下文和表达风格。

### 多 Agent 记忆层

为不同 LLM 和工具提供共享的结构化记忆。

---

## 设计原则

1. 记忆必须有证据。
2. 负面记忆同样重要。
3. 模糊记忆不能当作真理。
4. 记忆必须支持衰减和过期。
5. 多次证明有用的记忆应该晋升。
6. 图谱关联比孤立 tag 更有价值。
7. Harness 应该从记忆反馈中学习。
8. 不同模型可能需要不同记忆格式。
9. 长期记忆应该可查看、可编辑、可删除。
10. Agent 应该记住结果，而不是只保存聊天文本。

---

## 当前状态

**当前仓库已经超出最初的 SDK v0.2.0 foundation。** 它仍然是零外部依赖的 JSON
原型，但当前工作树已经包含更完整的 runtime-memory 结构：

- `schema.py` - Layer 1/2 `MemoryItem` 与 canonical Layer 3 `Pattern`
- `store.py` - 原子 JSON store、`MemoryWorkspace`、中文/中英混合 lexical baseline
- `policy.py` - `MemoryPolicy`、`RetrievalPolicy` 与最小 `ActionPolicy`
- `contract.py` - 确定性 `EnvironmentContract`、`ToolContract`、`SourceAuthority`
- `action_gate.py` - 结构化 `ActionProposal` 与确定性 `ActionGate`
- `trajectory.py` - 重复失败、停滞、预算限制的最小 `TrajectoryRegulator`
- `skill.py` - 基于 Layer-3 Pattern 和 avoidance memory 的 procedural skill retrieval
- `harness.py` - 显式生命周期 harness，串联交互前、任务条件化、执行前 gate、
  反馈后 regulation、任务结果记录
- `evidence.py` - `EvidenceNode`、`EvidenceLink`、`EvidencePacket`、`EvidenceStore`
- `composer.py` - `PatternStore` 与显式 provisional `PatternComposer`
- `context_schema.py`、`context_store.py`、`content_router.py`、`tag_time_index.py` -
  可逆 RAW-to-capsule 压缩与 scoped capsule lookup
- `graph_schema.py`、`graph_store.py`、`graph_linker.py`、`graph_retriever.py` -
  最小候选图谱 / tag-linking，用于召回扩展和候选缩小
- `gbrain.py` - tags、memories、evidence、Pattern 的图同步与 mind-map 投影
- `config.py`、`providers/`、`graph/proposal.py`、`graph/reviewer.py` -
  可选低权限 LLM GraphProposal 生成与 Harness review
- `lifecycle.py` - verified write、Pattern compose/rollback、marker context 写入与 GBrain sync
- `runtime_authority.py` - runtime marker activation、source-gated memory context、
  hash-chained decision ledger
- `runtime/live_loop.py` - 带 runtime authority、ActionGate、trajectory regulation 的
  tau-style live loop
- `integrations/lmev2_module.py` - LongMemEval-V2 风格 context backend，默认不写 verified memory
- `external/longmemeval_v2.py` - LongMemEval-V2 snapshot resolver，支持自动发现
  `D:\benchmarks\longmemeval-v2`，回退 `D:\hf_cache`，并在缺失时可选通过 Hugging Face 下载
- `evaluation/experience_transfer.py` - 确定性的 v0.7 experience-transfer / random-experience protocol
- `evaluation/path_promotion.py` - 专门的 Layer-3 路径晋升协议，覆盖 stable-path promotion、
  stale-path suppression、rollback 与 best-path selection
- `cli.py` - `mw` CLI：validate、doctor、memory、evidence、pattern、route、graph、
  context、external、gbrain、skill、harness、contract、action、trajectory、layer、eval
- `scorer.py` - heat / confidence / freshness 信号，不再自动创建 Layer 3
- `retriever.py` - 策略过滤的 verified retrieval
- `router.py` - 支持 Pattern 的 Fast / Thinking / Fast-Verify 路由
- `extractor.py` - 中英文反馈分类器 + 事件检测器
- `contradiction.py` - 三级矛盾解决器（SILENT / WARN / BLOCK）

P0 批次已经关闭四项信任边界风险：编辑伪增 heat、tag gate 绕行、assistant
positive 写入和 Router fast-path 绕行。后续 runtime 增量继续加入 policy gate、
EvidenceLink 校验、中文召回探针、CLI smoke、provisional/stable Pattern 生命周期测试、
ContextCapsule 可逆恢复、marker-bound runtime guidance，以及最小的执行前 / 执行后
生命周期 gate。

验证范围：

- 当前原型主贡献方向：Layer-3 path promotion 已经能够把 verified experience
  晋升成显式可复用 execution path，用 `path_fitness_score` 给路径打分，通过多次
  task run trial 路径，并通过 `PatternComposer.select_best_path()`、
  `SkillRetriever`、`MemoryWeaverHarness` 以及 CLI 的 `pattern trial` /
  `pattern best-path` 流程来选择当前最优路径。
- 这条主 claim 的专门证据现在位于
  [`docs/validation/layer3-path-promotion-v0.7/README.md`](docs/validation/layer3-path-promotion-v0.7/README.md)，
  覆盖 stable-path promotion、latest-path selection、stale-path suppression、
  rollback success 和 zero path regret。
- 另外还增加了一条真实 snapshot 桥接路径：`mw eval path-promotion-lme-v2 --json`
  会先从 LongMemEval-V2 external episode 派生 path-promotion family，再运行同一套
  Layer-3 promotion / rollback 流程。当前机器上这条路已经可以直接跑在
  `D:\benchmarks\longmemeval-v2` 上；LongMemEval-V2 数据层也支持回退 `D:\hf_cache`
  或在缺失时可选下载 snapshot 布局。
- 在当前这个小型真实数据设置里，这条桥接线已经能从本地 snapshot 派生出 2 个 family，
  并保持 `stable_promotion_rate = 1.0`、`latest_path_selection_accuracy = 1.0`、
  `stale_path_suppression_rate = 1.0`、`average_path_regret = 0`。
- 在当前机器上，这条桥接线也已经可以稳定跑通 5 个真实 LongMemEval-V2 question 的
  小样本，得到 `real_snapshot_family_count = 5`、`latest_path_selection_accuracy = 1.0`、
  `average_path_regret = 0`。
- 同一条路径在当前机器上也已经顺利扩展到 20 和 50 个真实 LongMemEval-V2 question
  的小样本，同时保持 `stable_promotion_rate = 1.0`、
  `latest_path_selection_accuracy = 1.0`、`average_path_regret = 0`。
- 已证明：policy gate 不被基础路径绕过，provisional Pattern 不会过早 `fast`，
  evidence link 不会自动晋升 memory，中文 lexical retrieval 有基本命中，
  RAW context 可以通过 `raw_ref_id` 可逆恢复，runtime marker filters 在受控验证中
  可以把五类 leak 压到 0，live-loop smoke 能从 observation 写入 verified memory，
  同时不绕过 runtime safety boundary。
- 尚未证明：真实任务解决更快、重复错误减少、优于 RAG over logs、跨模型经验复用、
  长期真实项目稳定性。

安全边界结果、marker runtime projection、retrieval speed / candidate reduction
对比仍然重要，但它们更适合作为 supporting boundary evidence 或 appendix，而不是
论文主 claim。本项目当前主线应是 Layer-3 路径晋升。

当前 Layer-3 path-promotion 主验证可以直接运行：

```powershell
python .\benchmarks\layer3_path_promotion_v0_7.py
mw eval path-promotion --json
mw eval path-promotion-lme-v2 --json --question-limit 2 --trajectories-per-question 1 --states-per-trajectory 1
```

下一组论文主实验应继续沿着这条 Layer-3 主线外推：扩大 sibling-task family，
增加 path competition、stale-path replacement、环境变化下的 rollback，以及更开放的
任务轨迹。

对于 external benchmark context，`mw external lme-v2-context` 现在支持自动发现
`D:\benchmarks\longmemeval-v2`，并回退到 `D:\hf_cache` 中的 Hugging Face snapshot；
如果本地不存在，也可以选择自动下载所需的最小 snapshot 布局。

未来可以引入 LLM 维护 GBrain、思维导图和分支存储，但必须保留硬边界：LLM 可以维护
候选图谱、候选摘要、候选分支；不能直接维护 verified memory 或 stable Pattern。

下面这些验证更适合作为 supporting boundary evidence 或 appendix。它们对 trust 和
runtime safety 很重要，但已经不再是当前主 claim。

Graph tag-linking 验证记录见
[`docs/validation/graph-tag-linking-v0.3/README.md`](docs/validation/graph-tag-linking-v0.3/README.md)。
它说明一跳候选图谱可以改善 tag recall 并缩小候选扫描范围，但不证明任务成功率提升。

Runbook Marker v0.5 验证记录见
[`docs/validation/runbook-marker-v0.5/README.md`](docs/validation/runbook-marker-v0.5/README.md)。
它当前衡量的是人工标注的 counterfactual trace advantage，不是真实任务成功率提升。

Active Marker Binding v0.5.2 验证记录见
[`docs/validation/active-marker-binding-v0.5.2/README.md`](docs/validation/active-marker-binding-v0.5.2/README.md)。
它验证了五个 golden Runbook Marker 可以绑定 capsule evidence 并恢复 raw span，
同时不发生 runtime mutation、Layer-3 mutation、memory promotion、online LLM call
或 tool execution。

Controlled Active Guard v0.5.2 验证记录见
[`docs/validation/controlled-active-guard-v0.5.2/README.md`](docs/validation/controlled-active-guard-v0.5.2/README.md)。
它只允许一个低风险 `L1_hint` marker 写入 route hint 和 required evidence plan，
同时阻止 `L2_route` 与 `L3_guard` marker 进入 active runtime behavior。它也会记录
unresolved marker conflict，并阻止存在冲突的 marker 进入 active behavior。

L2 Route Approval v0.5.2 验证记录见
[`docs/validation/l2-route-approval-v0.5.2/README.md`](docs/validation/l2-route-approval-v0.5.2/README.md)。
它允许一个已批准的 `L2_route` marker 写入 route/evidence plan，同时让未批准的
L2 marker 保持 pending，并继续阻止 L3 guard marker。

Decision Ledger v0.5.2 验证记录见
[`docs/validation/decision-ledger-v0.5.2/README.md`](docs/validation/decision-ledger-v0.5.2/README.md)。
它将五条 route-plan decision 记录成 SHA-256 hash chain，并包含 policy version、
approval id、conflict refs、capsule refs、raw refs 和 zero side-effect counters。

ContextCapsule / TagTimeIndex v0.5.3 验证记录见
[`docs/validation/context-capsule-v0.5.3/README.md`](docs/validation/context-capsule-v0.5.3/README.md)。
它在 40 条 RawSpan fixture 上验证了 RAW-to-capsule compression、reversible raw
retrieval、tag-time lookup、CLI context smoke 和 MarkerEvidenceContext validation。

ContextCapsule Stress v0.5.3.x 验证记录见
[`docs/validation/context-capsule-stress-v0.5.3x/README.md`](docs/validation/context-capsule-stress-v0.5.3x/README.md)。
它在原 40 条 fixture 之外加入 50 张 dialogue cards 和 301 条 dialogue-derived
RawSpan，同时保持 raw recovery、tag recall、marker context hit rate 和 trust
inheritance gate 全部通过。

Retrieval Comparison v0.5.4 验证记录见
[`docs/validation/retrieval-comparison-v0.5.4/README.md`](docs/validation/retrieval-comparison-v0.5.4/README.md)。
它在 50 个 query 和 341 条 capsule 上对比 baseline capsule scan、TagTimeIndex
lookup、accepted graph + TagTimeIndex lookup。三组 Recall@10 都保持 1.0，
结构化检索把平均候选集从 341 缩小到 6.44，并且没有 online LLM call、memory
promotion 或 Layer-3 mutation。

SQLite FTS5 Frontend Filter v0.5.4a 验证记录见
[`docs/validation/retrieval-fts5-filter-v0.5.4a/README.md`](docs/validation/retrieval-fts5-filter-v0.5.4a/README.md)。
它对比 full SQLite FTS5、MW tag/time -> FTS5 和 MW graph/tag/time -> FTS5。
Recall@10 保持 1.0，平均候选集从 341 降到 6.44，p95 latency 从 11.5543 ms
降到约 2.02 ms，同时没有 online LLM call、memory promotion 或 Layer-3 mutation。

Temporal GBrain Drift v0.5.5 验证记录见
[`docs/validation/temporal-gbrain-drift-v0.5.5/README.md`](docs/validation/temporal-gbrain-drift-v0.5.5/README.md)。
它把 50 个 CoreIssueNode 和 50 个 HarnessMarker 投影到 temporal graph，记录
validity metadata、supersedes/challenged_by lineage，并生成 13 个 review-only
MarkerProposal candidate。它不会授予 runtime authority，也不会执行 memory
promotion 或 Layer-3 mutation。

Runtime Safety Gate Independence 由两个互补对比面共同验证：

#### 5.1 Relevance retrieval leaks

Retrieval Safety Filter v0.5.4b 验证记录见
[`docs/validation/retrieval-safety-filter-v0.5.4b/README.md`](docs/validation/retrieval-safety-filter-v0.5.4b/README.md)。
它在 50 个 dialogue-card query 和 341 条 capsule 上运行 adversarial FTS5 query。
FTS5-only top-10 结果里有 40 个 untrusted leak、35 个 assistant trap、27 个
stale runtime candidate；source/freshness/marker gates 将三者全部降为 0，
同时 required-evidence hit rate 和 known-bad-warning hit rate 都保持在 0.98。

#### 5.2 Static graph leaks

Temporal Graph Ablation v0.5.5b 验证记录见
[`docs/validation/temporal-graph-ablation-v0.5.5b/README.md`](docs/validation/temporal-graph-ablation-v0.5.5b/README.md)。
它对比 static tag co-occurrence 和 temporal GBrain runtime filtering。静态图
Recall@10 保持 1.0，但会泄漏 66 个 stale 和 66 个 challenged top-10 runtime
candidate；temporal runtime filtering 保持 eligible-marker Recall@10 = 1.0，
将 stale/challenged runtime leak 降为 0，并把全部 13 个 review-only marker
收进 review queue。

Neither relevance-based retrieval nor static graph structure is sufficient for
runtime memory safety. 换句话说，相关性检索和静态图谱都会召回“主题相关但没有
runtime 资格”的候选：它们可能 source 不可信、时间无效、被挑战过，或者不符合
marker eligibility。MemoryWeaver 的 source gate、temporal graph 和 marker
eligibility filter 组合起来，将五类 leak 全部降为 0，同时把 required-evidence
和 known-bad-warning hit rate 保持在 0.98 以上。这些验证都没有 online LLM call、
memory promotion、Layer-3 mutation 或 runtime-authority grant。

论文路线可以压缩成三条证据线：

```text
证据线 A: MW != strict filter        -> strict 会丢弃的有用弱信号，MW 能保留。
证据线 B: MW != relevance retrieval  -> BM25/FTS5 只管主题相关，MW 管 runtime 资格。
证据线 C: MW != static graph         -> static graph 负责连接，MW 追踪时效、挑战和替代。
v0.6 汇总: semi-real replay 已开始衡量步骤、纠错和 known-bad-path 尝试的减少；下一步才是 live harness runs。
```

最终 claim 不是简单的“MemoryWeaver 比 X 更好”，而是：strict filter、相关性检索、
静态图谱解决的是不同子问题，但它们都没有回答“这条经验有没有资格进入 runtime”。
这才是 MemoryWeaver 的论文贡献点。

Real Trajectory Experiment v0.6 验证记录见
[`docs/validation/real-trajectory-experiment-v0.6/README.md`](docs/validation/real-trajectory-experiment-v0.6/README.md)。
它将 50 个 dialogue-card task 按 `no_memory`、`rag_over_logs` 和
`memoryweaver_runtime_marker` 三组 replay。在这个 semi-real replay 中，
MemoryWeaver 相比 no-memory 平均少 3 步，相比 RAG 平均少 1 步；known-bad action
attempts 相比 no-memory 少 55，相比 RAG 少 50；required evidence first-hit rate
达到 1.0，并且没有 online LLM call 或 runtime-authority violation。它还不声称
live agent task success improvement。

Controlled Harness Run v0.6.1 验证记录见
[`docs/validation/controlled-harness-run-v0.6.1/README.md`](docs/validation/controlled-harness-run-v0.6.1/README.md)。
它将同样 50 个 task 放入 deterministic policy loop，并记录 150 条 hash-chained
decision。MemoryWeaver 保持 v0.6 的收益，同时增加 decision-level auditability：
相比 no-memory 少 3 步，相比 RAG 少 1 步；known-bad action attempts 相比 no-memory
少 55，相比 RAG 少 50；required evidence first-hit rate 为 1.0，并且所有
side-effect counters 都保持 0。它仍然不执行真实工具，也不声称 live agent success。

Live-Lite Harness v0.6.2 验证记录见
[`docs/validation/live-lite-harness-v0.6.2/README.md`](docs/validation/live-lite-harness-v0.6.2/README.md)。
它在同样 50 个 task 和三组 arm 上执行 500 次 deterministic in-memory mock tools。
known-bad mock tool 返回 `failed_known_bad`，required evidence tool 返回
`evidence_observed`。MemoryWeaver 相比 no-memory 减少 55 次 known-bad mock tool
failure，相比 RAG 减少 50 次；观察到 required evidence 100 次，MW arm 的 unsafe
mock tool execution 为 0，并且仍然没有 real tool execution、memory promotion、
Layer-3 mutation 或 online LLM call。

LLM GraphProposal 验证记录见
[`docs/validation/llm-graph-proposal-v0.4/README.md`](docs/validation/llm-graph-proposal-v0.4/README.md)。
API 框架默认关闭，只能生成 `GraphProposal`。必须经过 Harness review，才可能写入
candidate edge。

v0.8 搭建状态：integrated substrate 已完成，但还不是生产级规模优化。
[`docs/validation/v0.8-integration/README.md`](docs/validation/v0.8-integration/README.md)
记录了真实 artifact：RAG evidence refs、GBrain candidate graph、specialist
EvidencePacket、checkpoint/resume 和 pass^3 reliability，同时保持 direct verified
memory write、Layer-3 mutation 与 hard-evidence 外晋升都为 0。

推迟到 v0.9 的是：production vector DB / HNSW、多跳图谱优化、CLI job isolation、
更广泛 provider coverage、大型外部 benchmark、自动 PatternComposer 推理。这些是
建立在 v0.8 substrate 之上的优化和扩展，不再是 v0.8 缺失的搭建项。

---

## License

MIT

---

## 致谢

本项目受到以下方向启发：

* RAG
* 长期 Agent 记忆
* 反馈闭环
* 知识图谱
* 认知架构
* Vibe Coding Agent
* Memory-first Agent Framework

MemoryWeaver 不试图替代现有 Agent 框架。
它更适合作为 Agent Harness、Memory Store、Graph Layer 和 Retrieval Layer 之间的记忆调度层。
