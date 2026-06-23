# MemoryWeaver Layer 3 完整设计与演进路线

## 概述

Layer 3 是 MemoryWeaver 从"记忆系统"升级为"Runtime Harness Memory"的关键层级。本文档整合了原始 README 设计、用户提出的 CoreIssueNode / HarnessMarker 循环机制、以及后续所有优化讨论，形成 Layer 3 的完整设计规范。

---

## 一、Layer 3 在 RAW 设计中的原始定位

### 1.1 Layer 3 是什么（来自 README 原文）

> Layer 3 stores canonical `Pattern` records, not Layer-3 `MemoryItem` copies and not raw RAG chunks. Layer 3 is provisional by default. A new Pattern must remain `provisional` until explicit validation promotes it to `stable`.

> A pattern may combine multiple memory signals: positive + negative + neutral + ambiguous.

> Layer 3 helps the agent decide: when to use fast mode, when to use thinking mode, which memory to retrieve, which assumptions to avoid, which tool path to try first, which model-specific memory format to use.

### 1.2 Layer 3 不是什么

```
Layer 3 ≠ 升级版的 MemoryItem（它是 structured rule，不是 raw memory）
Layer 3 ≠ 天然正确的权威层（provisional by default）
Layer 3 ≠ 可以自动生成（goes through PatternComposer，不能从 scorer 自动创建）
Layer 3 ≠ 可以在 retrieval 中充当 final answer（它帮助检索，不替代检索结果）
```

### 1.3 Layer 3 与 Layer 2 的本质区别

| | Layer 2 | Layer 3 |
|---|---|---|
| 粒度 | 单条 memory | 组合多条 memory 的 pattern/diagnostic rule |
| 形式 | "Codex subscription failed because org was wrong" | "If subscription failed and API key exists, check org before reinstalling" |
| 来源 | 直接来自 event | 来自 PatternComposer 组合 Layer 2 signals |
| 默认状态 | activated（使用过后即激活） | provisional（必须显式验证才 stable） |
| 路由作用 | 无（只作为检索候选项） | 有（影响 fast/thinking/fast_verify 选择） |
| 可用极性 | 单极性（positive/negative/neutral/ambiguous） | 多极性组合（positive + negative + neutral + ambiguous） |

---

## 二、Layer 3 循环机制的完整链路

### 2.1 原始构想（用户提出）

用户的核心洞察是：Layer 3 不应仅仅是 static pattern storage，而应该是一个循环——Pattern 在使用中不断被验证/挑战/拆分，最终收敛出 "某个问题最核心的根因" 并以安全的方式影响 runtime。

### 2.2 完整链路（整合所有优化后）

```
┌─────────────────────────────────────────────────────────────────┐
│                     Layer 1: Candidate Memory                     │
│                                                                  │
│  Event → Harness Pre-Tagging → Layer 1 MemoryItem                │
│  source-gated, polarity-tagged                                   │
│  assistant → ambiguous only, confidence ≤ 0.3                   │
│  user/terminal/tool → polarity as observed                      │
│  status: candidate                                               │
│  不能直接进入检索（必须经过 source gate + policy check）           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     Layer 2: Activated Memory                     │
│                                                                  │
│  进入条件（任一满足）:                                            │
│    - 被检索并用于 task                                            │
│    - 被用户确认或纠正                                             │
│    - 被 terminal/tool 结果验证                                    │
│    - 有 evidence_link 支持                                       │
│                                                                  │
│  四极分区:                                                       │
│    positive  → 有用的成功信号                                     │
│    negative  → 失败路径 → avoidance memory，不删除               │
│    neutral   → 稳定的上下文/背景                                  │
│    ambiguous → 未验证的假设                                       │
│                                                                  │
│  生命周期信号:                                                    │
│    heat (使用频率), confidence, validation_count                 │
│    success_score, correction_score                               │
│    freshness (stable/volatile/expired/unknown)                   │
│                                                                  │
│  关键: 单条 memory 的价值有限                                     │
│  "Codex subscription failed" 只是一条记录                         │
│  "不要重装 npm" 只是一条 avoidance                                │
│  真正的 insight 来自多条 memory 的组合 → Layer 3                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                 GBrain: Graph Relation Layer                      │
│                                                                  │
│  GBrain 不是 memory store，是 relation engine:                    │
│    - 链接相关 tags（codex + subscription + organization）        │
│    - 合并重复节点（同一问题的不同表述）                            │
│    - 检测陈旧知识（freshness decay）                              │
│    - 连接 people, projects, errors, tools, outcomes              │
│    - 计算 relation density（某类节点之间的连接密度）             │
│                                                                  │
│  GBrain 为 CoreIssueNode 提供量化输入:                            │
│    - relation_density: 某 tag cluster 的连接密度                 │
│    - temporal_edge_count: 时间相关的边数                          │
│    - evidence_overlap: 多个 memory 指向同一 evidence              │
│    - failure_concentration: 多条 negative memory 指向同一根因     │
│                                                                  │
│  约束:                                                            │
│    - GBrain 维护 relation，不维护 verified memory                 │
│    - GBrain 的边可以被 challenge/reject                          │
│    - LLM 可以提议 candidate edge，Harness 审核                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     Layer 3: Pattern Layer                        │
│                                                                  │
│  PatternComposer 组合 multiple signals into diagnostic rules:    │
│                                                                  │
│  输入:                                                            │
│    - positive memory: 什么方法有效                                │
│    - negative memory: 什么方法无效/有害                           │
│    - neutral memory: 什么环境/上下文不变                          │
│    - ambiguous memory: 什么假设待验证                             │
│                                                                  │
│  输出:                                                            │
│    - rule: "If X and Y are true, prioritize Z and avoid A."      │
│    - applies_when / avoid_when                                   │
│    - confidence, freshness, model_fit                              │
│                                                                  │
│  状态转移（provisional 是默认，不是过渡）:                         │
│    provisional ──validation──→ stable                            │
│    provisional ──contradiction──→ challenged                     │
│    stable ──new evidence──→ challenged                           │
│    stable ──expired──→ archived                                  │
│    challenged ──evidence resolved──→ stable 或 archived           │
│                                                                  │
│  关键约束:                                                        │
│    - 不能从 scorer 自动创建                                       │
│    - 不能从 RAG retrieval 自动创建                                │
│    - PatternComposer 是唯一入口                                   │
│    - provisional Pattern 最多路由到 fast_verify                   │
│    - 只有 stable Pattern 才能路由到 fast                          │
│    - evidence links 不自动 promote Pattern                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│              CoreIssueNode: 经验收敛点                             │
│                                                                  │
│  定义: CoreIssueNode 是 "反复出现的一个核心问题" 的结构化表示。       │
│  它不是 memory，不是 pattern，而是一个 convergence marker——        │
│  它指出 "多个记忆和模式都在指向同一个根因"。                         │
│                                                                  │
│  产生条件（任一满足即可，不需要等 Layer 3 stable）:                  │
│    1. Layer 2 cluster: 同一类问题在 Layer 2 中反复出现 N 次        │
│    2. Layer 3 pattern: 一个 pattern 已经 capture 了该问题           │
│    3. GBrain relation_density: 某个 tag cluster 的连接密度超阈值   │
│    4. repeated_task_evidence: 多个 task 出现相同 failure pattern   │
│                                                                  │
│  为什么 CoreIssueNode 不能只从 Layer 3 产生:                        │
│    - Layer 3 pattern 可能还在 provisional，没到 stable             │
│    - 但问题已经出现了 5 次，每次都造成了同样的代价                  │
│    - 如果等 pattern stable 才产生 CoreIssueNode → 冷启动死锁       │
│    → CoreIssueNode 必须允许从 Layer 2 cluster + GBrain 直接产生    │
│                                                                  │
│  数据结构:                                                        │
│    id: str                    # unique identifier                 │
│    title: str                 # human-readable summary            │
│    scope: dict                # {project, environment, tool,      │
│                               #   platform, model}                │
│    applies_when: list[str]    # 什么条件下此问题是核心问题         │
│    does_not_apply_when: list[str]  # 排除条件                     │
│    supporting_memory_ids: list[str]    # Layer 2 memories         │
│    supporting_pattern_ids: list[str]   # Layer 3 patterns          │
│    supporting_evidence_ids: list[str]  # evidence nodes            │
│    contradicted_by: list[str]          # 与之冲突的 memory/evidence │
│    child_issue_ids: list[str]          # 拆分后的子问题            │
│    parent_issue_ids: list[str]         # 被合并到的父问题          │
│    confidence: float          # 这个问题确实是核心问题的置信度      │
│    stability: float           # 这个认识的稳定程度                 │
│    freshness: float           # 证据的新鲜度                       │
│    activation_count: int      # 被触发的次数                       │
│    success_count: int         # 识别准确次数                       │
│    failure_count: int         # 识别错误次数                       │
│    status: str                # candidate|active|stable|           │
│                               # challenged|split|archived          │
│                                                                  │
│  状态转移:                                                        │
│    candidate ──N activations + low conflict──→ active            │
│    active ──M successes──→ stable                                │
│    active ──user correction / new contradictory evidence──→ challenged │
│    challenged ──evidence resolved──→ stable 或 archived           │
│    any ──scope too broad──→ split（拆成多个子节点）               │
│    any ──drift detected──→ challenged                             │
│    any ──no activations for T time──→ archived                    │
│                                                                  │
│  关键约束:                                                        │
│    - CoreIssueNode 没有 runtime 权限                              │
│    - CoreIssueNode 不能直接 routing/guarding/blocking              │
│    - CoreIssueNode 是 HarnessMarker 的输入，不是替代               │
│    - scope 字段必须精确：WSL 下的经验不能迁移到 macOS              │
│    - 权重不能天然高于 Layer 2（参考下一节权重规则）                │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 权重规则：Layer 3 不天然高于 Layer 2

这是一个核心设计决策——来自对 RAW 原文中 "provisional by default" 的解读：

```
Layer 3 不是天然更真，而是更可复用。
它的优先级来自验证次数、适用范围、低冲突率和新鲜度，
而不是来自层级本身。
```

五维权重拆解：

| 权重 | 含义 | 来源 |
|---|---|---|
| reuse_weight | 可复用权重 | 被成功复用的次数 |
| verification_weight | 验证权重 | user/terminal 明确验证的次数 |
| freshness_weight | 时效权重 | evidence 的最后更新时间 |
| conflict_penalty | 冲突惩罚 | 与 verified memory 冲突的次数 |
| scope_match_weight | 适用范围匹配权重 | 当前 query scope 与 node scope 的重合度 |

相对优先级规则：

```
stable Layer 3 + fresh evidence      > activated Layer 2
provisional Layer 3                  ≈ activated Layer 2
challenged Layer 3                   < verified Layer 2
expired Layer 3                      < any Layer 2 with fresh evidence
```

反例说明为什么这条规则重要：

```
场景: 一周前的 Layer 3 pattern 说 "Codex subscription 失败时重装 npm 通常有效"
      但昨天用户纠正了，terminal 也验证了是该 org entitlement 的问题

如果 Layer 3 天然优先 → 系统仍会推荐重装 npm（因为 pattern 仍在 Layer 3）
如果按权重规则 → 新的 verified Layer 2 memory 优先于过时的 Layer 3 pattern
```

---

## 三、HarnessMarker：从经验收敛到 Runtime 干预

### 3.1 定位

> CoreIssueNode 是经验收敛点，标志 "某个问题反复出现"。
> HarnessMarker 是经验进入 runtime 的安全接口，规定 "遇到此问题时应该如何调整行为"。

核心原则：

> Marker 是 runtime 里的红绿灯，不是司机。

### 3.2 HarnessMarker 的五个作用

**Route Marker**：当 query/task 命中核心问题节点时，Router 不直接从 `thinking` 开始，而是进入 `fast_verify`（仍不直接 `fast`，除非关联 stable pattern 且 evidence fresh）。

**Guard Marker**：如果 task 命中 known bad path（如 reinstall npm、git reset --hard、delete auth files、use --force），触发 known_bad_path_suppression + require_evidence_before_action + ask_user_confirmation。

**Evidence Marker**：自动要求某类 evidence（如 check selected organization、run codex --version、verify terminal output、inspect config file）。marker 不给答案，而是规定 "先验证什么"。

**Trace Marker**：在 mw trace 里记录：query matched core_issue_node → marker activated → avoided failed_path → required evidence check → route = fast_verify。对论文和调试有直接价值。

**Lifecycle Marker**：如果 marker 多次成功减少错误路径，强化对应 Pattern；如果失败或被用户纠正，challenge/rollback。

### 3.3 干预等级

HarnessMarker 不是 binary 的 on/off，而是六级干预：

| 等级 | 名称 | 行为 | 适用场景 |
|------|------|------|---------|
| L0 | trace | 只记录，不影响任何行为 | CoreIssueNode 刚形成，candidate marker |
| L1 | hint | 给 LLM 提醒（如 "注意：历史上此问题与 org 有关"），不改变 route | active marker，验证次数还不够 |
| L2 | route | 影响 thinking → fast_verify | verified marker，多次成功 |
| L3 | guard | 阻止或降级某些路径（suppress known bad path），并要求 evidence | verified marker，已知该路径会失败 |
| L4 | require_confirmation | 要求用户确认后才能继续 | 涉及高风险操作（如 delete auth files） |
| L5 | block | 硬阻断高风险动作 | 极其谨慎，必须 stable + high confidence + 风险明确 |

**升级规则**：marker 不能自动升级。升级条件：

```
L0 → L1: activation_count ≥ 3, failure_count = 0
L1 → L2: success_count ≥ 5, failure_count ≤ 1
L2 → L3: success_count ≥ 10, failure_count ≤ 1, verified evidence fresh
L3 → L4: marker_type = guard AND 涉及高风险操作
L4 → L5: 需人工 review，不可自动
```

**降级规则**：自动降级比自动升级更容易触发：

```
任何等级: drift_score > 阈值 → challenged
任何等级: failure_count 连续 2 次 → 降一级
任何等级: 用户纠正 → challenged
challenged: 新 evidence 确认问题解决 → archived
```

### 3.4 HarnessMarker 权限规则（硬约束，不可绕过）

```
HarnessMarker CAN:
  ✅ route（影响 thinking/fast_verify/fast 选择，最大 fast_verify）
  ✅ warn（给 LLM 提供 hint）
  ✅ require verification（规定必须先验证什么）
  ✅ suppress known bad paths（阻止已知失败路径）
  ✅ create trace entries（记录干预过程）

HarnessMarker CANNOT:
  ❌ execute tools
  ❌ auto-promote memory
  ❌ auto-stabilize Layer 3
  ❌ bypass user/terminal evidence
  ❌ trigger fast（除非关联 stable pattern 且 policy 允许）
  ❌ make high-risk user decisions（这是 Harness L4 的职责，不是 marker 的）
```

### 3.5 数据结构

```python
@dataclass
class HarnessMarker:
    id: str
    marker_type: str         # route | guard | evidence | trace | lifecycle
    intervention_level: str  # L0_trace | L1_hint | L2_route | L3_guard |
                             # L4_require_confirmation | L5_block
    status: str              # candidate | active | verified | challenged |
                             # disabled | archived
    source_core_node_id: str
    linked_pattern_ids: list[str]
    linked_memory_ids: list[str]
    trigger_tags: list[str]           # 命中条件：tag 匹配
    trigger_query_patterns: list[str] # 命中条件：query 语义匹配
    guard_actions: list[str]          # suppress 哪些 action
    required_evidence: list[str]      # 必须先验证什么
    recommended_mode: str   # thinking | fast_verify
    max_mode: str            # 最高允许的 mode，通常 fast_verify
    drift_score: float       # 自动计算，检测 marker 是否已失效
    confidence: float
    activation_count: int
    success_count: int
    failure_count: int
    conflict_refs: list[str] # 冲突的其他 marker IDs
    policy_version: str
    created_at: str
    updated_at: str
```

### 3.6 例子：Codex Subscription 诊断

```
CoreIssueNode:
  title: "Codex subscription failure often from org entitlement mismatch"
  scope: {project: "weaver-memory", environment: "WSL", tool: "Codex CLI"}
  supporting_memory_ids: [mem_terminal_org_fix, mem_terminal_api_scope, ...]
  supporting_pattern_ids: [pattern_codex_subscription_diagnostic]
  confidence: 0.88
  status: stable

HarnessMarker (从 CoreIssueNode 投影):
  marker_type: guard
  intervention_level: L3_guard
  trigger_tags: [codex, subscription, failed]
  trigger_query_patterns: ["subscription failed", "codex not working"]
  guard_actions: [suppress_reinstall_npm, suppress_reset_auth]
  required_evidence: [check_selected_organization, verify_api_key_scope]
  recommended_mode: fast_verify
  max_mode: fast_verify
  drift_score: 0.12（低 → marker 仍然有效）

Runtime 行为:
  User: "Codex subscription failed again. Should I reinstall npm?"
  → marker activated: codex_subscription_org_mismatch
  → known bad path detected: reinstall_npm → suppressed
  → required verification: check selected organization
  → route: fast_verify
  → trace entry written
```

---

## 四、三个关键优化

### 4.1 优化 A：冷启动路径

**问题**：如果 CoreIssueNode 依赖"反复出现"才能 emergence，问题出现前几次时 marker 不存在 → 无法记录 → evidence 不积累 → 更难 emergence → 冷启动死锁。

**方案**：允许 candidate CoreIssueNode 从第一次 occurrence 就产生 L0_trace marker：

```
第 1 次 occurrence:
  → candidate CoreIssueNode（status=candidate, activation_count=1）
  → L0_trace marker（只记录，不干预）

第 2-3 次 occurrence:
  → activation_count 增加
  → trace 记录累积
  → evidence 累积

第 4 次 occurrence:
  → 如果 GBrain relation_density 或 Layer 2 cluster 密度达到阈值
  → CoreIssueNode status: candidate → active
  → marker: L0 → L1_hint

第 5+ 次 occurrence:
  → 如果多次验证有效
  → CoreIssueNode: active → stable
  → marker: L1 → L2_route → L3_guard（按升级规则）
```

关键约束：candidate CoreIssueNode 只能产生 L0_trace marker。不能干预行为。这确保了冷启动不会以安全为代价。

与 Layer 1 的对应关系（RAW 依据）：

```
Layer 1 candidate memory → "does not assume the memory is correct or reusable"
L0_trace marker → 同样的逻辑：被记录了，但还没被证明可复用
```

### 4.2 优化 B：Context Drift Detection

**问题**：marker 在 scope 字段匹配的情况下，可能因为环境中一个关键变量改变而失效。scope 匹配 ≠ marker 仍然有效。

**例子**：

```
2026-03: marker "subscription failed → check org" 非常准
2026-05: Codex 改了 billing 模型，org 不再是主因
scope 仍然匹配（WSL, Codex CLI, 同一项目）
但 marker 实际已经失效
```

**方案**：每次 marker 激活后自动计算 drift_score：

```python
drift_score = f(
    # 最近 N 次激活的成功率趋势（上升 → drift 高）
    success_rate_trend(N=5),

    # 关联 evidence 的新鲜度衰减（evidence 越旧 → drift 越高）
    evidence_age_decay(linked_evidence_ids),

    # 关联 Layer 2 memory 的更新时间分布（长期没有新 memory → drift 高）
    memory_update_recency(linked_memory_ids),

    # scope 内环境变量的变更记录（环境变化 → drift 高）
    scope_change_frequency(scope),
)
```

**自动响应**：

```
drift_score < 0.3: marker 健康，无动作
drift_score 0.3-0.5: marker 加 WARN 标记，但可正常用
drift_score 0.5-0.7: marker 自动降为 challenged，不等用户纠正
drift_score > 0.7: marker 自动 disabled，保留 trace 数据
```

与 freshness 字段的关系（RAW 依据）：

```
RAW freshness: stable | volatile | expired | unknown（静态标签）
drift_score: 动态计算，自动触发降级（从静态到动态的升级）
对应 RAW 原则: "Memory must decay or expire"
```

### 4.3 优化 C：Marker 冲突检测

**问题**：两个 guard marker 可能同时命中同一 query，但建议互斥。

**极端例子**：

```
marker_A (guard): suppress reinstall npm  ← 来自 subscription 场景
marker_B (guard): suppress skip reinstall  ← 来自另一个 dependency 场景

query: "npm install 报错，怎么办？"
→ 两个 guard 同时命中
→ 不知道该 suppress 什么
→ 静默崩溃
```

**方案**：marker 激活时的冲突检测流程：

```
Step 1: 收集所有命中的 guard marker
Step 2: 比较 guard_actions 集合
  - 无交集：无冲突，正常激活
  - 有交集但不互斥：两者都激活，但都降一级（如 L3 → L2）
  - 互斥（如 A suppress X, B suppress not-X）：
    Step 3: 比较两个 marker 的 confidence
      - 如果差值 > 0.3：选择高 confidence 的，降级低 confidence 的
      - 如果差值 ≤ 0.3：两者都不执行 guard，降级为 L1_hint
Step 4: 记录 marker_conflict_event
  → 作为新的 Layer 2 evidence
  → 触发 CoreIssueNode split 候选审查
Step 5: 如果同一对 marker 冲突 ≥ 3 次
  → 触发自动 CoreIssueNode split（原节点过宽，需拆成两个更精确的子节点）
```

与 ContradictionResolver 的复用（RAW 依据）：

```
ContradictionResolver: SILENT / WARN / BLOCK（memory 层的冲突）
Marker 冲突检测: 同样的三级逻辑，应用在 marker 层

两个 candidate marker 冲突 → SILENT: 记录，降级为 hint
stable vs candidate 冲突 → WARN: 优先 stable，降级 candidate
两个 stable 且互斥 → BLOCK: 都不执行，要求人工 review
```

---

## 五、循环的闭合：从 Runtime 回到 Layer 2/3

### 5.1 反馈回路

HarnessMarker 激活后的 outcome 不是终点，而是新一轮循环的输入：

```
TaskRun Outcome → 记录在 marker activation trace 中
    ↓
Outcome Evaluation（每次 marker 激活必须做四种判断之一）:
    ├─ success → reinforce marker + linked pattern + linked memories
    ├─ failure → weaken marker, 检查 drift_score
    ├─ user correction → challenge marker + challenge linked pattern
    ├─ no effect → reduce confidence, 标记为待观察
    └─ marker conflict → split CoreIssueNode candidate
    ↓
Updated:
    Layer 2 memory: validation_count ± 1, success_score/correction_score 调整
    Layer 3 pattern: confidence 调整, freshness 更新
    CoreIssueNode: stability 调整, activation_count + 1
    HarnessMarker: status 可能改变, drift_score 重算
    GBrain: relation weight 调整
    ↓
Loop restarts with richer experience
```

### 5.2 防止 feedback loop 失控

这是整个机制中最重要的安全设计：

```
陷阱（必须防止）:
  越常用 → 越核心 → 越容易被用 → 越强化
  → marker 变成 self-reinforcing dogma

正确循环:
  越常用 → 越核心 → 但每次验证 freshness + drift + conflict
  → 可能被 reinforce / weaken / challenge / split
  → 不会被盲目强化
```

**关键的四种判断**（每次 marker 激活至少执行一种）：

| 判断 | 触发条件 | 效果 |
|------|---------|------|
| reinforce | marker 成功帮助 task | confidence +0.02, stability +0.01（increment 递减） |
| weaken | marker 无帮助或误导 | confidence -0.05（惩罚 > 奖励） |
| challenge | 用户纠正 / 新 evidence 冲突 / drift high | status → challenged, 不能自动恢复 |
| split | 原 CoreIssueNode 过宽，两个不同子问题被混在一起 | 拆成多个子节点，marker 重新投影 |

**Increment 递减机制**：

```
reinforce 第 1 次: confidence +0.05
reinforce 第 2-5 次: confidence +0.03
reinforce 第 6-10 次: confidence +0.02
reinforce 第 11+ 次: confidence +0.01
confidence_max = 0.95（永远不能到 1.0）
```

这确保了一个 marker 不会因为用了很多次就变成无可置疑的真理。

---

## 六、HarnessMarker 与 Layer 3 的版本路线

### 6.1 v0.5：CoreIssueNode + HarnessMarker Schema（数据层）

**目标**：只做数据结构定义和手动写入。不做自动生成。

**内容**：

```
- CoreIssueNode dataclass + store
- HarnessMarker dataclass + store
- MarkerStatus, InterventionLevel enums
- mw marker create --core-node-id <id> --type guard --level L0_trace
- mw marker list / show / update / disable / archive
- mw core-issue create / list / show / update
- 权限规则测试（marker CANNOT 的所有规则）
```

**通过标准**：

```
1. schema 可导入，所有字段可读写
2. CLI 手动 CRUD 可用
3. 权限规则全部通过测试
4. 现有 142 tests 不退化
```

### 6.2 v0.5.1：L0_trace + L1_hint 激活

**目标**：最小 marker 激活能力——只记录和提醒，不改变行为。

**内容**：

```
- MarkerMatcher: query → match trigger_tags + trigger_query_patterns → 收集命中 marker
- L0_trace: 匹配到 candidate marker → 只写入 trace，不干预
- L1_hint: 匹配到 active marker → 注入 LLM context（"注意：此问题历史上与 X 有关"）
- MarkerActivationTrace 记录
- 不可: L2_route 及以上
```

**为什么从最低干预开始**：确保 marker 不会在未充分验证的情况下改变 runtime 行为。L0 和 L1 是完全可逆的——关掉 marker 系统不影响任何功能。

### 6.3 v0.5.2：L3_guard + Marker 冲突检测

**目标**：加入 required_evidence 和 known_bad_path_suppression。

**内容**：

```
- Evidence Marker: required_evidence 在路由前注入验证步骤
- Guard Marker: known_bad_path_suppression（如 suppress reinstall_npm）
- Marker 冲突检测: 同 query 命中多个 guard marker → 冲突 resolution
- 冲突 event → Layer 2 evidence → CoreIssueNode split candidate
```

**不可**：L4_require_confirmation, L5_block。

**冲突检测通过标准**：

```
1. 两个 guard marker 冲突时，系统不静默崩溃
2. 冲突 event 被正确记录
3. 同一对 marker 冲突 ≥ 3 次 → CoreIssueNode split 候选被创建
```

### 6.4 v0.5.5：CoreIssueNode Projection + Drift Detection

**目标**：CoreIssueNode 自动投影为 HarnessMarker，以及 marker 自动老化。

**内容**：

```
- CoreIssueNode.stable → candidate HarnessMarker（需 review，不自动激活）
- drift_score 自动计算
- drift_score > 0.5 → marker auto-challenged
- drift_score > 0.7 → marker auto-disabled
- marker activation trace 用于 drift 计算
```

**冷启动路径落地**：

```
- candidate CoreIssueNode 可以从 Layer 2 cluster + GBrain density 自动产生
- 不要求 Layer 3 pattern 先存在
- candidate CoreIssueNode 只能产生 L0_trace marker
```

### 6.5 v0.6：任务级 Marker 实验

**目标**：证明 HarnessMarker 有可测量的 positive impact。

**四组对照**：

```
C0: No persistent memory（纯 LLM agent）
C1: RAG over logs（检索原始日志文本）
C2: MemoryWeaver without HarnessMarker（source gate + contradiction + verified retrieval）
C3: MemoryWeaver with HarnessMarker（C2 + route/guard/evidence marker）
```

**实验指标**：

| 指标 | 含义 | C3 理想值 |
|------|------|----------|
| steps-to-success | 到成功所需步骤数 | C3 < C2 < C1 |
| repeated_error_count | 重复同样错误的次数 | C3 < C2 < C1 |
| known_bad_path_attempts | 尝试已知失败路径的次数 | C3 < C2 |
| tool_error_rate | 工具调用错误率 | C3 < C2 < C1 |
| marker_helpful_rate | marker 触发后有正面效果的比例 | > 0.7 |
| marker_harm_rate | marker 触发后有负面效果的比例 | < 0.1 |
| evidence_check_order_accuracy | 要求验证的顺序是否正确 | > 0.8 |
| path_reuse_rate | 复用已验证路径的比例 | C3 > C2 > C1 |
| user_correction_count | 用户纠正次数 | C3 < C2 < C1 |

**通过标准**：

```
1. C3 steps-to-success < C2 < C1
2. C3 known_bad_path_attempts < C2 < C1
3. C3 marker_harm_rate < 0.1
4. C2 和 C3 的 trusted recall 不显著低于 C1
5. C3 marker_helpful_rate > 0.7
```

---

## 七、完整版本路线总览

```
当前 (2026-06)
├── v0.4.4a ✅ 小型 fixture + naive baseline（8 events, 2 queries）
├── v0.4.4b ✅ dirty-50 + strict 对照（50 events, 16 queries）
│    结论: MW 比 naive 安全，但和 strict 在所有指标上完全一致
│
├── v0.4.5 ← 当前：strict differentiation
│    证明 MW 不是 strict 的等价物
│    围绕 weak-but-useful / negative avoidance / partial evidence 三类场景
│    通过标准: 7 条（4 条强制性差值 + 3 条安全兜底）
│
├── v0.4.4d + v0.4.4e（穿插执行）
│    官方数据检查 + 报告整理 + claim 降级
│
2026-07/08
├── v0.5: CoreIssueNode + HarnessMarker schema
│    只做数据结构和手动写入
│
├── v0.5.1: L0_trace + L1_hint marker 激活
│    最小干预，可完全回退
│
├── v0.5.2: L3_guard + marker 冲突检测
│    known_bad_path_suppression + required_evidence
│
├── v0.5.5: CoreIssueNode projection + drift detection
│    自动投影 + 自动老化
│
2026-09/10
├── v0.6: 任务级实验
│    四组对照 + marker 有效性指标
│
2026-11+
├── v0.7: Alpha CLI + Bundle export/import
├── v0.8: 离线 Sentinel watcher
└── v0.9: 对外 Alpha Demo
```

---

## 八、论文写作时机与可用 Claim

### 第一版草稿时机：v0.4.5 通过后

此时可用的 claim：

```
1. Source-gated polarity prevents assistant fabrications from polluting verified memory
   (v0.4.4a+b: pollution 9→0, wrong promotion 37→0, contradiction 1.0→0.0)

2. Source gate improves trusted recall in dirty environments by filtering out noise
   (v0.4.4b: trusted recall 0.8125 vs naive 0.625)

3. MemoryWeaver is not equivalent to strict filtering:
   it retains weak-but-useful signals and activates negative avoidance patterns
   while preserving the same trust-boundary safety
   (v0.4.5, if passes)

建议章节: Trust-Boundary Validation
适合: ICML/NeurIPS/ACL workshop paper
不声称: official benchmark result, task success improvement
```

### 第二版补充时机：v0.6 通过后

此时追加的 claim：

```
4. HarnessMarker converts repeatedly validated diagnostic patterns into runtime
   routing hints, guardrails, and evidence requirements

5. MemoryWeaver + Marker reduces repeated errors and unsafe action attempts
   compared to both No Memory and RAG over logs

建议章节: Runtime Harness Memory Evaluation
适合: full conference paper
```

---

## 九、风险与阻塞点

| 风险 | 影响层 | 缓解 |
|------|--------|------|
| v0.4.5 MW 和 strict 再次零分化 | v0.4.5 | 检查 fixture 密度，确保 weak-but-useful + negative avoidance + partial evidence 场景充分 |
| EvidenceSupportCheck precision 不足 | v0.5+ | CoreIssueNode 建立在不可靠 evidence 上的风险；线 A 校准不能无限推迟 |
| Marker 冷启动死锁 | v0.5.1 | v0.5 必须允许 candidate CoreIssueNode + L0_trace marker |
| 官方 MemEvoBench 数据不可用 | v0.4.4d + 论文 | v0.4.4d 确认后在 README 明确标注 synthetic fixture |
| Pending/candidate 队列无限增长 | v0.5+ | v0.5 加入 auto-archive: N 轮无新 evidence → archive |
| Counterfactual baseline 不可计算 | v0.6 | 在纯 retrieval 实验中无法回答 "没有 marker 会走什么路径"，需等 v0.6 agent trajectory |
