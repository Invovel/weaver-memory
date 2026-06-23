# MemoryWeaver 完整路线计划

## 当前版本状态

```
v0.2.0 SDK foundation
   ↓
v0.4   DeepSeek online LLM GraphProposal（暴露 candidate-level pollution）
   ↓
v0.4.1 online/offline 拆分 + BudgetGate + EvidenceSupportCheck + ReviewPolicy 拒绝能力（136 tests）
   ↓
v0.4.2 真实 DeepSeek v4-pro 离线链路验证（8 proposals, accepted=0, wrong link rate=0, 142 tests）
   ↓
v0.4.3 mw doctor + proposal_eval recall fix（142 tests）
   ↓
v0.4.4 MemEvoBench-style synthetic dirty fixture trust-boundary validation（50 events, 16 queries, 146 tests）
```

**核心已完成验证：** online LLM call count = 0, accepted wrong link rate = 0, mw doctor valid = true, v0.4.4 synthetic dirty fixture pollution leaks `9 -> 0`, wrong promotions `37 -> 0`, contradiction false-accept `1.0 -> 0.0`, 146 tests passing.

**核心未证明：** LLM proposal 能为在线检索带来增量 recall（accepted edges = 0）；MemoryWeaver 是否比 `strict_verified_only` 更能保留 useful weak signals；是否提升端到端 Agent 任务成功率或优于 RAG over logs。

---

## 总体架构

```
MemoryWeaver Core      → memory / evidence / graph / policy / pattern
MemoryWeaver Runtime   → CLI / workspace / doctor / review / trace / decision-log / ledger / sentinel
MemoryWeaver Research  → benchmark / validation / paper metrics
```

核心原则（已升级）：
> LLM proposes only under budget; Harness judges and throttles.

LLM 不在在线路径运行。Harness 不仅裁决，还要限流。

---

## 三条并行线

### 线 A：EvidenceSupportCheck 校准（v0.4.2b）— 低优先级

**目标：** 在严格 gate 下产出 accepted edge > 0。

**当前阻塞根因：** 所有 proposal 都是 `supports_partial` + `candidate_only`，ReviewPolicy 对此只给 pending，不给 accept。

**最小改动：** 对 low-risk relation（related_to）+ supports_partial + confidence ≤ 0.3 的 proposal，允许标记为 `accepted_low_confidence` 进入图。该边在在线检索中权重极低（source=composer, confidence=0.3），不污染结果，但能产生可测量的 recall 增量。

**验证方式：** 用 v0.4.2 的同一批 `proposals_deepseek.jsonl` 重跑 review → eval。

**优先级原因：** 继续卡在 accepted=0 上性价比不高。只要 total safety 已证明（在线路径不调 LLM, wrong link rate=0），调参可放慢。

---

### 线 B：Trust-Boundary Validation（v0.4.4）— **已完成**

**阶段目标：** 在一个 MemEvoBench-style synthetic dirty fixture 中验证 source-gated policy、ContradictionResolver 和 VerifiedRetriever 的 trust-boundary 行为，而不是证明完整 Agent 性能。

**支持的 claim：** MemoryWeaver reduces polluted retrieval, wrong promotion, and contradiction false-accepts in a MemEvoBench-style synthetic dirty fixture, without reducing trusted Recall@10.

**中文 claim：** MemoryWeaver 在一个 MemEvoBench-style 合成污染 fixture 中减少了污染检索、错误晋升和冲突误接受，并且没有降低可信记忆召回。

**边界：** 这不是官方 MemEvoBench 分数，不是 end-to-end agent task success evaluation，不证明经验复用、路径复用、任务成功率提升或优于 RAG over logs。

#### 区域目的

| 区域 | 目的 | v0.4.4 结果 |
|---|---|---|
| Synthetic dirty fixture | 构造 adversarial injection、noisy tool outputs、biased feedback、freshness conflict、synthetic/ambiguous evidence 等污染情境 | 50 events、16 queries |
| Naive baseline | 证明 source gate 不是装饰；无门控时污染会进入晋升和检索 | leak `9`，wrong promotion `37`，false accept `1.0` |
| MemoryWeaver source gate | 验证来源门控、显式晋升、verified retrieval 和 contradiction block 的组合效果 | leak `0`，wrong promotion `0`，false accept `0.0` |
| Strict verified only | 给出保守上界，检查 MemoryWeaver 是否只是 strict filter | 当前与 MemoryWeaver recall 打平，触发 v0.4.5 差异化测试 |
| Dataset labeling | 防止把 synthetic fixture 写成官方 benchmark | 固定标注 `not official MemEvoBench score` |
| Reproducible artifacts | 保留 raw results、metrics、fixture、queries、completion status | `docs/validation/memevobench-style-v0.4.4/` |

#### Benchmark 后续优先级

| 优先级 | Benchmark | 测试重点 | 对应模块 |
|---|---|---|---|
| **1** | Official MemEvoBench data check | 确认官方数据是否公开、可下载、license 允许 | Adapter normalization |
| **2** | MEMTRACK | 跨平台状态追踪（Slack/Linear/Git, 噪声, 冲突, 交叉引用） | EventDetector, ContradictionResolver, VerifiedRetriever, Freshness |
| **3** | EvoMemBench | execution-oriented procedural memory | Layer 3 Pattern（v0.6 以后适用） |
| **4** | SMMBench | source-distributed multimodal memory | 暂缓 |

#### 已验证任务

**Task A：Contradiction Detection / False Accept Control**

输入：old memory + new event + source + timestamp。输出：SILENT / WARN / BLOCK。v0.4.4 重点看 contradiction false-accept rate：`1.0 -> 0.0`。

**Task B：Wrong Promotion Control**

输入：trusted user/terminal、assistant injection、noisy tool output、biased feedback、ambiguous evidence。输出：是否允许 Layer 2 promotion。v0.4.4 wrong promotions：`37 -> 0`。

**Task C：Verified Retrieval / Pollution Leak Control**

输入：query + memory pool（verified / assistant-only / synthetic / conflicting）。输出：top-k memory。v0.4.4 pollution retrieval leaks：`9 -> 0`，trusted Recall@10：`0.625 -> 0.8125`。

#### Baseline 设置

```
Baseline A：naive_no_gate
Baseline B：memoryweaver_source_gate
Baseline C：strict_verified_only
```

本阶段不包含 RAG over logs、不包含 No memory 任务执行、不包含 end-to-end agent task success。

#### 已产出指标

| 指标 | 含义 |
|---|---|
| Contradiction severity accuracy | SILENT/WARN/BLOCK 分类正确率 |
| BLOCK precision | 应拦截冲突中正确拦截的比例 |
| BLOCK recall | 应拦截冲突中实际拦截的比例 |
| Verified precision@k | 检索结果中 verified memory 占比 |
| Pollution rate@k | 检索结果中 unverified memory 占比 |
| Wrong promotion rate | 未验证被错误提升到 Layer 2 的比例 |
| Trusted Recall@10 | 可信 memory 是否仍能被召回 |

#### 论文 Claim

> We evaluate MemoryWeaver on a MemEvoBench-style synthetic dirty fixture with 50 events, 16 queries, and three baselines: naive_no_gate, memoryweaver_source_gate, and strict_verified_only. MemoryWeaver reduces pollution retrieval leaks from 9 to 0, wrong promotions from 37 to 0, and contradiction false-accept rate from 1.0 to 0.0, while improving trusted Recall@10 from 0.625 to 0.8125. This validation does not constitute an official MemEvoBench result or an end-to-end agent task success evaluation.

#### 执行顺序

```
Step 1：构造 built-in MemEvoBench-style synthetic dirty fixture（完成）
Step 2：实现 naive_no_gate / memoryweaver_source_gate / strict_verified_only 三组对照（完成）
Step 3：输出 raw_results.json + metrics.json + metrics_summary.json + completion_status.json + README.md（完成）
Step 4：明确 Dataset source / Official data status / non-official score 标签（完成）
Step 5：官方 MemEvoBench 数据确认与适配（后续，不属于 v0.4.4 完成条件）
```

### 线 B2：Strict-vs-MemoryWeaver Differentiation（v0.4.5）— **下一步**

**阶段目标：** 证明 MemoryWeaver 不是简单的 `strict_verified_only` 过滤器，而是在阻断污染的同时保留有价值的弱信号。

**corrected strict baseline：**

```text
source in {user, terminal}
and not explicitly_deprecated
```

不再要求 `expected_promoted = true`、external evidence、`confidence > 0.8` 或 positive polarity。这样 strict 可以公平保留用户纠正、terminal 观察和 negative avoidance 文本；MemoryWeaver 要证明的是额外理解 polarity、lifecycle、partial evidence、unverified labeling 和 fast_verify context。

**需要新增场景：**

1. assistant hypothesis 后续被 tool / user 部分验证；
2. ambiguous memory 被多次任务激活，但还没达到 full verified；
3. weak evidence + repeated successful use 进入 low-confidence activated memory；
4. 来自 user correction 的 negative memory 对避坑有用，但不是 terminal verified。

**指标：** weak_useful_hit@10, negative_avoidance_activation, known_bad_path_suppression, partial_evidence_hit@10, multi_source_evidence_count, strict_false_negative_count, unsafe_weak_trust_count, wrong_promotion_count, unverified_context_labeled_count。

**硬门槛：**

```text
weak_signal_recalled_count = weak_signal_labeled_unverified_count
weak_signal_mislabeled_trusted_count = 0
wrong_promotion_count = 0
```

**执行协议：** [`docs/validation/memevobench-style-v0.4.5/README.md`](../validation/memevobench-style-v0.4.5/README.md)

---

### 线 C：CoreIssueNode / HarnessMarker Runtime Loop（v0.5-v0.6）

v0.4.5 通过后，路线从“更大检索”转向“长期经验如何进入 runtime”。核心结构：

```text
Layer 2 Activated Memory
→ GBrain Relation Layer
→ Layer 3 Provisional Pattern
→ CoreIssueNode
→ MarkerProposal
→ ProjectionReview
→ HarnessMarker
→ Runtime Route / Guard / Evidence Check / Trace
→ TaskRun Feedback
→ reinforce / weaken / challenge / split / archive
```

#### v0.5：Schema + Manual Marker Store

**目标：** 定义 CoreIssueNode、HarnessMarker、MarkerProposal、ProjectionReview、MarkerActivationTrace，并用 50 条 10-20 轮多轮对话卡片驱动一个最小 `mw trace` demo，但不自动生成、不自动干预。

**测试入口：** [`docs/validation/v0.5-runbook-marker-dialogue-set.md`](../validation/v0.5-runbook-marker-dialogue-set.md)

**最小可展示闭环：**

```text
query
→ matched CoreIssueNode
→ activated HarnessMarker
→ suppressed known bad path
→ required evidence checks
→ route = fast_verify
→ trace saved
```

**允许：**

- manual core node
- manual marker
- trace
- hint
- shadow activation

**禁止：**

- 自动 guard
- 自动 block
- 自动 stable pattern
- 自动 fast
- 自动改 Layer 2

#### v0.5.1：Shadow Marker Activation

**目标：** marker 可以被 query 命中，但只记录，不改变行为。

**输出：**

- marker matched
- would_route_to
- would_require_evidence
- would_suppress_action
- trace only

**指标：** marker_trigger_precision, false_trigger_count, shadow_helpful_estimate, marker_noise_rate。

#### v0.5.2：Route / Guard Marker

**目标：** 让 marker 进入轻量 runtime 干预。

**允许：**

- L1 hint
- L2 route: `thinking -> fast_verify`
- L3 guard: suppress known bad path
- L4 require confirmation

**仍然禁止：**

- direct tool execution
- direct fast
- direct stable promotion

新增 MarkerConflictResolver、known_bad_path_suppression、required_evidence_check。

#### v0.5.5：Drift + CoreIssueNode Projection

**目标：** 从静态 memory 进入动态经验图谱。

加入 dynamic freshness、scope drift、environment drift、supersedes、split、merge、archive、CoreIssueNode -> MarkerProposal、ProjectionReview。

CoreIssueNode 是 experience convergence hypothesis，不是 truth authority；HarnessMarker 是 reviewed runtime projection，不是 action authority。

#### v0.6 任务级实验

**内容：**
- MemoryWeaver without marker vs MemoryWeaver with marker
- No memory vs RAG over logs vs MemoryWeaver 作为后续扩展
- 指标：steps-to-success, known_bad_path_attempts, evidence_check_order_accuracy, tool_error_rate, user_correction_count, marker_helpful_rate, marker_harm_rate

---

## 开源参考项目

### benchmark 数据集

| 数据集 | 来源 | 用途 | 规模 |
|---|---|---|---|
| **MemEvoBench** | arXiv:2604.15774 | 记忆污染/误演化防御（线 B 第一优先） | adversarial injection / noisy tool / biased feedback |
| **MEMTRACK** | NeurIPS 2025 SEA Workshop | 跨平台状态追踪与冲突处理（线 B 第二优先） | Slack/Linear/Git 多平台 |
| **EvoMemBench** | arXiv:2605.18421 | execution-oriented memory（后续） | knowledge + execution tasks |
| **LongMemEval-V2** | 2026 | v0.6 任务级实验 | 451 问题，500 轨迹，115M tokens |
| **Mem2ActBench** | 2026 | v0.6 ActionGate + TrajectoryRegulator | 2,029 sessions, 400 tasks |

### 架构参考

| 项目 | 参考价值 | 许可证 |
|---|---|---|
| **OpenDB** | SQLite FTS5 零向量库，LongMemEval 93.6% | — |
| **agentmemory** | BM25+Vector+Graph 混合检索 + 4 层记忆固化 | — |
| **harness-forge** | runtime CLI / doctor / review / trace / ledger / sentinel / bundle — **只学设计不复制代码** | GPL-3.0 |

---

## harness-forge 学习要点

### 已吸收到路线中

1. `mw doctor` — workspace 健康检查（v0.4.3 已落地）
2. `mw review --json` — proposal/edge/pattern 审核状态（入 v0.5）
3. `.memoryweaver/` 双层可见性结构（入 v0.5）
4. `mw trace` — 检索决策路径（入 v0.5）
5. `mw decision-log` — 裁决记录（入 v0.5）
6. Approval ledger（入 v0.5）
7. `mw export/import` bundle（入 v0.5）
8. Sentinel watcher + cost ceiling + panic stop（入 v0.8）

### 不吸收

- auto-tuning 自动调参（系统刚暴露 candidate-level pollution，太早）
- learned patterns 跨项目自动生效（需要 scope check）
- GPL 代码（只学设计）

---

## 汇总路线图

```
已完成
======
v0.4     DeepSeek 在线 proposal 实验 → 暴露 candidate-level pollution
v0.4.1   在线/离线拆分 + BudgetGate + EvidenceSupportCheck + ReviewPolicy 拒绝能力
v0.4.2   真实 DeepSeek v4-pro 离线链路验证（accepted=0, safe）
v0.4.3   mw doctor + proposal_eval recall fix（142 tests）
v0.4.4   MemEvoBench-style synthetic dirty fixture Trust-Boundary Validation
         ├─ 50 events / 16 queries
         ├─ naive_no_gate / memoryweaver_source_gate / strict_verified_only
         ├─ pollution leaks 9 -> 0
         ├─ wrong promotions 37 -> 0
         └─ contradiction false-accept 1.0 -> 0.0

当前活跃
========
v0.4.5   Strict-vs-MemoryWeaver Differentiation
         ├─ assistant hypothesis + partial verification
         ├─ repeated ambiguous memory activation
         ├─ weak evidence + repeated successful use
         ├─ correction-derived negative avoidance memory
         └─ unverified context labeling as hard gate

v0.4.2b  线 A：EvidenceSupportCheck 校准（低优先级）
         └─ 调 ReviewPolicy 让 supports_partial + related_to 可 low-confidence accept

等待前置
========
v0.5     CoreIssueNode / HarnessMarker schema + manual marker store
         ├─ 50-dialogue Runbook Marker trace set
         ├─ mw trace minimal demo
         ├─ matched CoreIssueNode
         ├─ activated HarnessMarker
         └─ known bad path warning + required evidence checks
v0.5.1   Shadow marker activation（trace-only）
v0.5.2   Route / Guard marker + MarkerConflictResolver
v0.5.5   Drift detection + CoreIssueNode -> MarkerProposal projection
v0.6     Task-level marker experiment
v0.7     Alpha CLI + Bundle export/import
v0.8     离线 Sentinel watcher
```
