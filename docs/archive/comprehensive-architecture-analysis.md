# MemoryWeaver 完整架构分析：从原始设计到 Runtime Harness Memory 循环

## 概述

本文档综合分析 MemoryWeaver 从原始 README 设计原则到 Layer 3 / CoreIssueNode / HarnessMarker 循环机制的完整演进逻辑，包括冷启动路径、drift detection、冲突检测和外部参考项目的对应关系。

---

## 一、原始设计的锚点

MemoryWeaver 的 README 里有几条不可动摇的设计基线，所有后续扩展都必须从它们出发，而不是绕开它们。

### 1.1 三层记忆不是等级制，是信任阶梯

RAW README 里的三层定义：

```
Layer 1: Candidate Memory — "does not assume the memory is correct or reusable"
Layer 2: Activated Memory — "retrieved, used, confirmed, corrected, verified"
Layer 3: Provisional Pattern — "provisional by default, explicit validation → stable"
```

RAW 设计里隐含了一个约束：**Layer 3 不是"更正确的记忆"，而是"更结构化的可复用模式"**。READEME 里写得很清楚——Layer 3 Pattern 从 positive + negative + neutral + ambiguous 四种极性的信号中组成，它不是一个升级版的 MemoryItem，而是一个 diagnostic rule。

这就决定了后续 CoreIssueNode 的定义不能是 "Layer 3 父节点优于一切"，而必须是 "经验收敛点，权重来自验证次数、低冲突率、新鲜度和 scope 匹配，而非来自层级本身"。

### 1.2 四种极性中的 negative 是 avoidance memory，不是垃圾

RAW 原文：

> Negative memory is not deleted. It becomes avoidance memory.

这是 MemoryWeaver 区别于 naive memory 和 strict_verified_only 的核心差异化点。READEME 里 negative memory 的例子是 "the user corrected the assistant"、"a command failed"、"a previous assumption was misleading"——它们不是无用数据，而是可检索的避坑信号。

后续 HarnessMarker 的 `known_bad_path_suppression` 功能直接继承了这个设计。它不是新增的能力，而是把 RAW 里已经定义的 negative/avoidance 机制从 retrieval 层面推进到了 runtime intervention 层面。

### 1.3 核心原则：LLM proposes, Harness judges

RAW 原文里这句话出现多次。它不是 slogan，而是架构约束：

```
LLM reasoning → candidate proposals
Harness judging → policy gate → promotion/rejection
```

这个约束在 HarnessMarker 设计中被进一步强化为：

```
CoreIssueNode → candidate HarnessMarker → human/evidence review → active marker
HarnessMarker can route, warn, require evidence, suppress bad paths
HarnessMarker CANNOT execute tools, auto-promote memory, auto-stabilize Layer 3
```

如果不坚持这个约束，marker 就会退化成 "LLM 自动判断 → LLM 自动执行"，完全绕过了 Harness 的判断层。

### 1.4 Fast / Thinking / Fast-Verify 路由不是简单的速度选择

RAW 定义了三种路由模式的触发条件：

```
New / uncertain / high-risk → Thinking Mode
Similar / validated / low-risk → Fast Mode
Known but possibly outdated → Fast + Verify
```

关键在于第三档——Fast-Verify 不是 "半快半慢"，而是 "用已有 pattern 加速，但必须验证当前 evidence 是否还 fresh"。这是 HarnessMarker 的 `max_mode = fast_verify` 规则的直接前身。marker 不能直接放行到 `fast`，因为验证过的经验不代表当前场景不需要再验证。

### 1.5 "从 Ask→Retrieve→Answer 到 Act→Observe→Learn→Remember→Reuse→Improve"

RAW 的最终目标是让 agent 从被动检索变成主动学习和改进。这是后续 CoreIssueNode → HarnessMarker → TaskRun outcome → reinforce/weaken/challenge/split 闭环的源头。如果 MemoryWeaver 只能存和检索，它就只是一个加了 source gate 的 RAG。闭环才是差异化。

---

## 二、Layer 3 循环机制与原始设计的对应关系

### 2.1 用户提出的机制 vs RAW 基础

用户提出的机制可以总结为：

```
Layer 2 clusters + Layer 3 patterns + GBrain relation density
→ CoreIssueNode（经验收敛点）
→ HarnessMarker（runtime 中的安全干预接口）
→ TaskRun outcome → 反馈更新 CoreIssueNode / Layer 2 / Layer 3
```

这个链路和 RAW 中的反馈循环完全对应：

```
RAW: Tag → Use → Feedback → Promote → Link → Abstract → Retag
新链路: Memory → Retrieve → TaskRun → Evidence → CoreIssueNode → Marker → Retag/Reinforce
```

区别在于新链路引入了两个中间概念（CoreIssueNode 和 HarnessMarker），使得 "Abstract" 这个原本模糊的步骤有了明确的代理。

### 2.2 Layer 3 在循环中的正确位置

RAW 里 Layer 3 的作用是：

> "helps the agent decide when to use fast mode, when to use thinking mode, which memory to retrieve, which assumptions to avoid, which tool path to try first"

新链路没有推翻这个定义，而是把它精确化了：

| RAW 原文 | 新链路中的对应 | 实现方式 |
|---------|-------------|---------|
| when to use fast mode | Route Marker | max_mode = fast_verify |
| which assumptions to avoid | Guard Marker | known_bad_path_suppression |
| which tool path to try first | Evidence Marker | required_evidence checklist |
| which memory to retrieve | CoreIssueNode → GBrain projection | relation density → candidate narrowing |

Layer 3 本身不直接做这些事，而是通过 CoreIssueNode 和 HarnessMarker 来代理。这符合 RAW 的约束——"provisional by default, explicit validation promotes to stable"。

### 2.3 为什么 CoreIssueNode 不能只来自 Layer 3

如果 CoreIssueNode 只能从 Layer 3 产生，就会出现时序死锁：

```
问题出现了 5 次
→ Layer 2 积累了 5 条相关 memory
→ 但 Layer 3 Pattern 还没稳定（validation_count 不够、evidence 不够新鲜）
→ CoreIssueNode 无法产生
→ 没有 marker
→ 第 6 次继续踩坑
```

所以 CoreIssueNode 的 emergence 条件必须放宽为：

```
Layer 2 cluster（同一类问题反复出现）
+ Layer 3 provisional pattern（即使未 stable）
+ GBrain relation density（相关节点密度达到阈值）
+ repeated task evidence（同类 task 多次出现相同模式）
→ candidate CoreIssueNode
```

这和 RAW 里的 Layer 3 composition 逻辑一致——Pattern 本来就是从 positive + negative + neutral + ambiguous 四极信号组合出来的，CoreIssueNode 只是多了一条 "可以从 Layer 2 cluster 直接聚合" 的 shortcut。

### 2.4 Layer 3 权重不能天然高于 Layer 2

RAW 里没有任何地方说 Layer 3 > Layer 2 > Layer 1。三层是不同质的东西：

```
Layer 1: 原始 candidate，未经验证
Layer 2: 被使用/验证过的单条记忆
Layer 3: 多条记忆组合成的可复用规则
```

Layer 3 Pattern 比单条 Layer 2 memory 更 "结构化"，但不一定更 "正确"。所以正确的权重逻辑是：

```
stable Layer 3 + fresh evidence > activated Layer 2
provisional Layer 3 ≈ activated Layer 2
challenged Layer 3 < verified Layer 2
```

这防止了早期错误 Pattern 被放上高层后压制新证据——这正是 RAW 设计里 "provisional by default" 的意图。

---

## 三、HarnessMarker 与 RAW 设计原则的对应

### 3.1 每条权限规则都有 RAW 出处

| HarnessMarker 权限规则 | RAW 依据 |
|----------------------|---------|
| CANNOT execute tools | "LLM proposes, Harness judges" — marker 是 Harness 的一部分，不是 LLM，不能执行 |
| CANNOT auto-promote memory | "Pattern creation goes through PatternComposer" — 不能绕过 |
| CANNOT auto-stabilize Layer 3 | "provisional until explicit validation promotes to stable" |
| CANNOT bypass user/terminal evidence | "source-gated polarity" — 没有 source 豁免 |
| CANNOT trigger fast unless linked stable pattern passes policy | "stable Patterns alone can route to fast" — 从 v0.2.0 以来的硬规则 |
| CAN route (L2_route) | "helps the agent decide when to use fast mode" — Layer 3 的既定职责 |
| CAN warn (L1_hint) | "which assumptions to avoid" |
| CAN require verification (L3_guard) | "do not prioritize npm reinstall. Check authentication first" — Layer 3 pattern 示例 |
| CAN suppress known bad paths | "negative memory is not deleted. It becomes avoidance memory" |

### 3.2 干预等级不是新增功能，是 RAW 路由器的细化

RAW 里只有 thinking / fast / fast_verify 三档。HarnessMarker 的六级干预（L0_trace 到 L5_block）是对这三档路由器在"有经验积累"场景下的精细化：

```
RAW: thinking → fast_verify → fast
Marker: L0_trace → L1_hint → L2_route → L3_guard → L4_require_confirmation → L5_block
```

L0-L2 对应 RAW 的 "New/uncertain → Thinking → Fast-Verify" 路径。
L3-L5 对应 RAW 的 "check authentication, selected organization, or subscription state first"——即 Pattern 给出的 actionable advice。

关键约束：L4 和 L5 不是 marker 自己的决定，而是 Harness policy 在 marker 激活后的判断。marker 标记风险，Harness 决定干预强度。这保持了 "LLM proposes, Harness judges" 的架构一致性。

---

## 四、三个优化与 RAW 设计的衔接

### 4.1 冷启动路径

优化内容：candidate CoreIssueNode 可以产生 L0_trace marker，只记录不干预。

RAW 依据：Layer 1 Candidate Memory 的定义——"does not assume the memory is correct or reusable"。candidate marker 就是 runtime 中的 candidate memory：它被记录了，但还没被证明可复用。

版本对应：v0.5 手动 marker 阶段应包含 candidate marker 的写入能力，否则手动 marker 只能在"问题已充分验证"后才能建，失去了早期 trace 的价值。

与外部参考的对应：Graphiti 的 "episode lineage" 概念——每次 occurrence 都是一条 episode，多条 episode 组成 trajectory，trajectory 收敛后形成 fact。Cold start marker 就是这个过程中的 "episode 级别的 trace"，不急于收敛为 fact。

### 4.2 Context Drift Detection

优化内容：marker 的 drift_score 自动检测环境变化导致的经验失效。

RAW 依据：Freshness 字段的五种状态（stable / volatile / expired / unknown / stale）和 "Memory must decay or expire" 原则。Drift detection 是 freshness 从静态标签到动态计算的升级。

与外部参考的对应：Zep 的 temporal knowledge graph 跟踪 "facts that were true at time T but may not be true at time T+1"。Drift score 是对同一思想的轻量实现——不需要完整 temporal graph，只需要在 marker 激活时计算关联 evidence 的时间衰减。

版本对应：v0.5.5 引入 drift_score 计算，但此时因为 marker 激活数据还不够，只能设一个宽松阈值。到 v0.6 积累了更多激活数据后收紧。

### 4.3 Marker 冲突检测

优化内容：同一 query 命中多个 guard marker 且建议互斥时，降级为 hint + 记录 conflict event。

RAW 依据：ContradictionResolver 的三级响应（SILENT / WARN / BLOCK）。Marker 冲突本质上是 "两个高置信经验之间存在矛盾"——这和不一致 memory 之间的冲突是同一类问题，只是发生在 marker 层而非 memory 层。

这意味着 marker 冲突的 resolution 应该复用 ContradictionResolver 的逻辑：如果两个 marker 都是 active（相当于两个 SILENT 级冲突），则降级并记录；如果一个 stable 一个 candidate（相当于 WARN），则优先 stable；如果两个都是 stable 且均经过多次验证（相当于 BLOCK），则触发人工 review。

---

## 五、外部参考项目的体系化对应

### 5.1 每个参考项目对准 MW 的哪个位点

| 参考项目 | 对准位点 | 吸收方式 |
|---------|---------|---------|
| **Graphiti / Zep** | temporal knowledge graph → drift detection、freshness decay | 学其 episode→fact→expiration 模型，不引入完整 temporal graph |
| **GBrain** | source-tier boosts + scoped retrieval + synthesis separation | 已在 graph_schema/graph_store 中吸收了最小投影，后续 CoreIssueNode 的 GBrain relation density 指标依赖它 |
| **harness-forge** | runtime CLI / doctor / review / trace / decision-log / bundle | 学其工程化接口设计，不复制代码；mw doctor 已落地，mw trace 和 decision-log 规划中 |
| **LIFE-HARNESS** | lifecycle gates: calibrate→retrieve→validate→regulate | 已体现在 MW 的 Agent Guide 中四个干预点；HarnessMarker 是对 intervene 步骤的具体实现 |
| **GraphRAG** | offline indexing + community summaries → CoreIssueNode 的 offline emergence | CoreIssueNode 的 "从 Layer 2 cluster 聚合" 机制可以借鉴 community summarization 的离线批处理模式 |
| **MemEvoBench** | adversarial injection / noisy tool / biased feedback → source-gated anti-pollution | v0.4.4 已验证；v0.4.5 扩展为 strict differentiation |

### 5.2 不吸收的部分及原因

| 参考项目 | 不吸收的内容 | 原因 |
|---------|-----------|------|
| Graphiti | 完整 temporal graph DB | MW 不需要完整图数据库，CoreIssueNode 的 drift_score 用轻量计算即可 |
| harness-forge | auto-tuning、learned patterns 跨项目 | 当前系统刚暴露 candidate-level pollution，自动调参太早 |
| GraphRAG | 全量 community hierarchy | MW 的经验收敛不需要全量图谱层次，CoreIssueNode 的 scope 限制了传播范围 |
| Mem0 | memory extraction 的自动 update/delete | MW 的 update/delete 需要通过 Harness review，不能自动 |

---

## 六、综合循环的最终形态

### 6.1 完整循环链路（整合所有优化后）

```
┌─────────────────────────────────────────────────────────────────┐
│                     EXPERIENCE ACCUMULATION                      │
│                                                                  │
│  User / Tool / Terminal Event                                    │
│       ↓                                                         │
│  Layer 1: Candidate Memory (source-gated, polarity-tagged)       │
│       ↓                                                         │
│  Layer 2: Activated Memory (verified, used, corrected)           │
│       ↓                                                         │
│  GBrain clusters: relation density, tag co-occurrence,           │
│    temporal edge, evidence overlap                               │
│       ↓                                                         │
│  Layer 3: Provisional Pattern                                    │
│    (composed from positive + negative + neutral + ambiguous)     │
│       ↓                                                         │
│  CoreIssueNode (candidate)                                       │
│    ← from Layer 2 clusters OR Layer 3 patterns OR both           │
│    ← scope: project/env/tool/platform/model                      │
│    ← score: separate from HarnessMarker confidence               │
│       ↓                                                         │
│  CoreIssueNode (stable)                                          │
│    ← after N verifications, low conflict rate, fresh evidence    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     RUNTIME INTERVENTION                          │
│                                                                  │
│  HarnessMarker (candidate → L0_trace only)                       │
│       ↓ (manual review / evidence accumulation)                  │
│  HarnessMarker (active)                                          │
│    ├─ Route Marker → fast_verify (not fast)                      │
│    ├─ Guard Marker → known_bad_path_suppression                  │
│    ├─ Evidence Marker → required_evidence checklist              │
│    ├─ Trace Marker → mw trace entry                              │
│    └─ Lifecycle Marker → Pattern validation feedback             │
│       ↓                                                         │
│  Runtime Intervention:                                            │
│    L0_trace → record only                                        │
│    L1_hint → suggest to LLM, don't change route                  │
│    L2_route → thinking → fast_verify                             │
│    L3_guard → suppress known bad path + require evidence         │
│    L4_require_confirmation → ask user                            │
│    L5_block → hard stop (rare, must be stable + high confidence) │
│       ↓                                                         │
│  CONSTRAINTS (HARD):                                             │
│    CANNOT execute tools                                          │
│    CANNOT auto-promote memory                                    │
│    CANNOT auto-stabilize Layer 3                                 │
│    CANNOT bypass user/terminal evidence                          │
│    CANNOT trigger fast without stable pattern + policy pass      │
│       ↓                                                         │
│  SAFETY CHECKS (PER ACTIVATION):                                 │
│    → drift_score check (is the marker still valid?)             │
│    → conflict check (other markers contradict this one?)        │
│    → scope match check (env/tool/platform still same?)          │
│    → counterfactual baseline (what would happen without marker?) │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     FEEDBACK LOOP                                 │
│                                                                  │
│  TaskRun Outcome → recorded in trace                             │
│       ↓                                                         │
│  Outcome Evaluation:                                             │
│    ├─ success → reinforce marker + linked pattern               │
│    ├─ failure → weaken marker, check drift                      │
│    ├─ user correction → challenge marker                        │
│    ├─ no effect → reduce confidence                             │
│    └─ marker conflict detected → split CoreIssueNode            │
│       ↓                                                         │
│  Updated:                                                        │
│    Layer 2 memory validation_count / success_score               │
│    Layer 3 pattern confidence / freshness                        │
│    CoreIssueNode stability / activation_count                    │
│    HarnessMarker status (active/challenged/disabled/archived)    │
│    GBrain relation weight                                        │
│       ↓                                                         │
│  Loop restarts with richer experience                            │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 循环中的关键约束（防止 feedback loop 失控）

```
越常用 → 越核心 → 越容易被用 → 越强化  ← 这是陷阱
越常用 → 越核心 → 但每次验证 freshness + drift + conflict → 可能被 weaken/challenge/split ← 这是正确循环
```

每次循环都必须执行四种判断中的至少一种：

- **reinforce**: 本次 marker 成功 → 增强，但 increment 递减（防止无限强化）
- **weaken**: 本次没帮助 → 降低
- **challenge**: 用户纠正、新 evidence 冲突、环境变化 → 标记 challenged
- **split**: CoreIssueNode 过宽 → 拆成两个更精确的子节点

### 6.3 和 RAW 的最终对应

```
RAW 原文最后一段:

"The LLM reasons. The tools act. The memory stores. The harness coordinates."

新链路对此的精确化:

"The LLM reasons → candidate proposals
 The tools act → TaskRun evidence
 The memory stores → Layer 1/2/3 + GBrain
 The harness coordinates → CoreIssueNode → HarnessMarker → intervention + trace + feedback

 MemoryWeaver is evolving from a memory harness into a lifecycle-aware
 runtime harness."

新链路是这个 evolution 的具体实现路径。
```

---

## 七、待解决的问题（当前分析的边界）

1. **EvidenceSupportCheck 的 supports_exact 校准问题**（来自 v0.4.1）仍未解决——如果 evidence binding 不准，CoreIssueNode 的 emergence 将建立在不可靠的 evidence 关系上。

2. **Pending 队列无限增长**（来自 v0.4.1）——CoreIssueNode 和 marker 也有同样风险：candidate marker 如果永远不满足激活条件，应该自动 archive。

3. **Layer 3 的 PatternComposer 目前是手动触发**——CoreIssueNode 要从 Layer 2 cluster 自动产生，需要先解决 "什么是够密集的 cluster" 的判断标准。

4. **HarnessMarker 的 scope 继承自 CoreIssueNode**，但 CoreIssueNode 的 scope 目前只在设计文档中定义了字段，没有实现自动推断逻辑——如果 scope 完全手动填写，迁移性会很差。

5. **Counterfactual baseline 目前不可计算**——"如果没有 marker，系统会走什么路径" 在纯 retrieval 实验中无法回答，需要等到 v0.6 任务级实验有 agent trajectory 数据后才能计算。

---

## 八、结论

MemoryWeaver 从 RAW 设计到 Layer 3 / CoreIssueNode / HarnessMarker 循环机制，不是另起炉灶，而是把 RAW 里已经定义但尚未精确化的概念一层层展开：

- RAW 的 "Abstract" 变成了 CoreIssueNode
- RAW 的 "helps the agent decide" 变成了 Route/Guard/Evidence Marker
- RAW 的 "negative memory is avoidance memory" 变成了 Guard Marker 的 known_bad_path_suppression
- RAW 的 "Tag → Use → Feedback → Promote → Link → Abstract → Retag" 变成了完整的 experience accumulation → runtime intervention → feedback loop

三个优化（冷启动路径、drift detection、冲突检测）不是额外功能，而是对这个循环机制的三个必要条件：没有冷启动，循环无法开始；没有 drift detection，循环会建立在过时经验上；没有冲突检测，循环中的 marker 会互相矛盾。

外部参考项目（Graphiti、GBrain、harness-forge、LIFE-HARNESS、GraphRAG）提供的不是代码，而是验证过的设计模式——temporal edge、source-tier boost、runtime CLI、lifecycle gate、offline community summary——每个都对 MW 的特定位点提供了 "这个方向已经被验证可行" 的信号。
