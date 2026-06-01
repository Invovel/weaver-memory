# MemoryWeaver

[English Version (英文版)](README.md) | [GitHub](https://github.com/Invovel/weaver-memory)

**面向长期 AI Agent 的反馈校准型记忆 Harness**

**LLM proposes. Harness judges.**

MemoryWeaver 是一个实验性的 Agent 记忆调度框架，用于把对话、终端输出、工具结果、用户纠正、任务结果转化为可复用的长期记忆。与传统 RAG 不同，MemoryWeaver 使用**来源门控极性**和**矛盾检测**来防止 LLM 编造的内容污染记忆库。

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

MemoryWeaver 把记忆看成一个持续演化的反馈系统。

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
Harness 预标记
        ↓
第一层：候选记忆
        ↓
第二层：激活 / 验证记忆
        ↓
图谱串联 / Pattern 组合
        ↓
第三层：公共 Pattern 记忆
        ↓
Harness 策略更新
```

完整闭环是：

```text
Tag → 使用 → 反馈 → 晋升 → 关联 → 抽象 → 重新标记
```

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

### 第二层：激活记忆

当某条记忆被调用、被用户反馈、被工具验证，或者参与过任务解决，它就可以进入第二层。

第二层开始做质量分区：

```text
positive   → 有用、成功、被确认
negative   → 失败路径、错误假设、被纠正
neutral    → 稳定背景、上下文事实
ambiguous  → 未验证假设、待确认信息
```

---

### 第三层：公共 Pattern 记忆

第三层不只是存 tag，而是存可复用的经验模式。

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

第三层会被 harness 和 RAG 系统共同使用，用于决定：

* 是否走 fast mode
* 是否走 thinking mode
* 应该检索哪些记忆
* 应该避免哪些假设
* 应该优先尝试哪个工具路径
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
* 学习哪些 tag 对某个 LLM 更有用

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
形成经验并归档
第二次相似问题快速复用
必要时轻量验证
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

## 建议 Pattern Schema

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
  "rule": "如果 X 和 Y 成立，则优先 Z，避免 A。",
  "applies_when": ["..."],
  "avoid_when": ["..."],
  "confidence": 0.82,
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

这是一张目标运行时架构图。当前 Sprint 0 原型已经实现本地记忆核心和第一批防污染
原语。RAG、GBrain、checkpoint 恢复、CLI job 隔离和 bad-case 闭环仍是后续目标，
详细设计位于 [`docs/`](docs/)。

---

## 当前模块结构

```text
memoryweaver/
├── memoryweaver/
│   ├── __init__.py
│   ├── schema.py          # MemoryItem, Pattern, 枚举类型
│   ├── store.py           # JSON 本地存储
│   ├── scorer.py          # 热度、置信度、晋升逻辑
│   ├── extractor.py       # EventDetector + 中英文 FeedbackClassifier
│   ├── router.py          # Fast / Thinking / Fast-Verify 模式路由
│   ├── retriever.py       # VerifiedRetriever 来源感知检索
│   └── contradiction.py   # ContradictionResolver (SILENT/WARN/BLOCK)
│
├── examples/
│   └── basic_memory_loop.py
│
├── benchmarks/
│   └── prototype_baseline.py
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
│   ├── bad_case_learning_loop.md
│   ├── agent_test_catalog.md
│   ├── testing_resilience_strategy.md
│   └── risk_assessment_and_benchmark.md
│
└── tests/
    ├── test_schema.py
    ├── test_contradiction.py
    └── test_retriever.py
```

---

## 设计文档

- [`docs/architecture.md`](docs/architecture.md) — 系统边界与设计原则
- [`docs/life_harness_notes.md`](docs/life_harness_notes.md) — LIFE-HARNESS 启发的生命周期 gate
- [`docs/rag_evidence_layer.md`](docs/rag_evidence_layer.md) — 高性能证据检索
- [`docs/gbrain_graph_memory.md`](docs/gbrain_graph_memory.md) — 图谱记忆、tag 与 memory lifecycle
- [`docs/react_agent_runtime.md`](docs/react_agent_runtime.md) — ReAct、会话衔接、缓存治理与容量规划
- [`docs/bad_case_learning_loop.md`](docs/bad_case_learning_loop.md) — bad-case 收集与递进优化
- [`docs/testing_resilience_strategy.md`](docs/testing_resilience_strategy.md) — 回归、崩溃、雪崩、压力、安全与 A/B 测试
- [`docs/risk_assessment_and_benchmark.md`](docs/risk_assessment_and_benchmark.md) — 当前风险与实测 baseline

---

## 原型 Benchmark

运行可复现的本地基线：

```powershell
python .\benchmarks\prototype_baseline.py
```

Windows 11、Python 3.14.0 下的实测结果：

| Memory items | JSON 大小 | 写入吞吐 | Verified text search p95 |
| ---: | ---: | ---: | ---: |
| 100 | 75 KB | 266.08 items/s | 0.27 ms |
| 500 | 378 KB | 81.57 items/s | 1.46 ms |
| 1,000 | 756 KB | 44.96 items/s | 2.91 ms |

JSON 原型适合验证语义与回归，不适合生产级持续摄入。当前每次写入都会整体重写
JSON 文件。

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

**Sprint 0 原型已完成。** 核心模块已实现，68 个测试全部通过：

- `schema.py` — MemoryItem dataclass（4 种极性、3 层、5 种状态）
- `store.py` — 原子写入 JSON 存储，支持 tag/polarity/layer 查询
- `scorer.py` — 热度/置信度评分和层级晋升规则
- `extractor.py` — 中英文反馈分类器 + 事件检测器
- `router.py` — Fast / Thinking / Fast-Verify 模式路由
- `retriever.py` — 来源感知的验证检索，带防污染过滤
- `contradiction.py` — 三级矛盾解决器（SILENT / WARN / BLOCK）

下一里程碑是 **Sprint 0.1 收口**。benchmark 当前记录了 6 个已知缺口：

1. `mw = memoryweaver.cli:main` 声明的 `cli.py` 不存在。
2. 普通 update 会错误增加 heat。
3. tag 检索可以绕过 assistant 来源门控。
4. assistant 记忆可以直接构造为 positive 和高 confidence。
5. `ModeRouter` 可以用未验证 assistant Pattern 触发 fast path。
6. whitespace tokenizer 无法召回重排后的中文短句。

下一步：先闭合信任边界，为这些 bad case 增加回归 fixture，再逐步实现 checkpoint
恢复、最小 GBrain 投影、bounded ReAct 和 RAG 证据层。

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
