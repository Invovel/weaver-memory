# MemoryWeaver 完整路线计划（2026-06-04 更新）

## 当前状态总览

```
已完成
======
v0.4     DeepSeek online LLM GraphProposal → 暴露 candidate-level pollution
v0.4.1   online/offline 拆分 + BudgetGate + EvidenceSupportCheck + ReviewPolicy 拒绝能力（142 tests）
v0.4.2   真实 DeepSeek v4-pro 离线链路验证（accepted=0, wrong link rate=0）
v0.4.3   mw doctor + proposal_eval recall fix（142 tests）
v0.4.4   线 B：External Memory Benchmark Adapter
         ├─ v0.4.4a：小型 fixture + naive baseline ✅ (8 events, 2 queries)
         └─ v0.4.4b：dirty-50 fixture + strict 对照 ✅ (50 events, 16 queries)

v0.4.4b 结论:
  - MW 比 naive 更安全（pollution 9→0, wrong promotion 37→0, contradiction 1.0→0.0）
  - MW trusted recall 反超 naive（0.8125 vs 0.625）
  - 但 MW 和 strict_verified_only 在所有指标上完全一致
  → 下一步必须证明 MW ≠ strict
```

---

## 总体架构约束（不可变）

以下规则来自 RAW 设计和已有验证结论，所有后续版本必须遵守：

```
1. LLM output → ambiguous by default → never auto-trusted
2. Layer 3 is provisional by default → explicit validation → stable
3. Negative memory is avoidance memory → not garbage → actively retrievable
4. Fast-Verify ≠ Fast → must check freshness + evidence before routing
5. LLM proposes, Harness judges → marker cannot bypass this
6. Candidate-level pollution is real → gate must apply to ALL proposal sources
7. Accepted wrong link rate = 0 → online safety proven → non-negotiable regression gate
```

---

## 三条并行线的持续状态

```
线 A: EvidenceSupportCheck 校准 → 低优先级，被线 B 和线 C 超越
      目标: 产出 accepted edge > 0 且 wrong link rate ≈ 0
      当前: 所有 proposal 都是 supports_partial + candidate_only → accepted = 0
      决策: 等到线 B 和线 C 有了阶段性成果后再调 ReviewPolicy

线 B: External Benchmark Adapter → 当前最高优先级
      v0.4.4: 证明 "MW 比 naive 安全" ✅
      v0.4.5: 证明 "MW 比 strict 更有价值" ← 下一步

线 C: CoreIssueNode + HarnessMarker → 架构设计阶段
      v0.5: schema + manual marker store
      v0.5.x: 逐级激活 marker 能力
      v0.6: 任务级实验
```

---

## 第一阶段：v0.4.5 Strict Differentiation Validation

### 目标

证明 MemoryWeaver 不是 strict_verified_only 的等价物。

```
v0.4.4 回答: Gate 能不能在 dirty memory 中防污染？ → 能
v0.4.5 回答: MW 是否只是 strict filter 的等价物？ → 不是
```

### 支撑 Claim

> MemoryWeaver retains useful weak signals that strict filtering discards, while preserving the same trust-boundary safety.

### 测试对象

只跑两组对照（不跑 naive——已在 v0.4.4b 充分验证）：

```
strict_verified_only
memoryweaver_source_gate
```

### Fixture 设计重点

围绕 strict 的三个致命盲区构造：

| 盲区 | 场景 | strict 行为 | MW 应行为 |
|------|------|------------|----------|
| source 不够硬 | assistant 假设被 tool 间接验证 | 拦截 | 检索但标注 unverified |
| negative 不被视为有用 | 用户明确标记的回避规则 | 不检索 | 激活为 avoidance signal |
| partial evidence 不够 confidence | 多源交叉印证但单条 < 0.8 | 拦截 | 检索但标注 partial |

同时必须包含 counterexample：weak-but-not-useful（MW 不应检索）和 misleading partial（MW 不应错误晋升），防止 fixture 只给 MW 喂"必赢样例"。

### 通过标准（7 条，前 4 条是强制性差值）

```
1. weak_useful_hit:          MW ≥ 2/3, strict ≤ 1/3        ★
2. avoidance_activated:      MW ≥ 3/4, strict = 0           ★
3. partial_evidence_hit:     MW ≥ 2/3, strict ≤ 1/3        ★
4. multi_source_evidence:    MW > strict                      ★
5. assistant fabrication leak: MW = 0（安全不倒退）          ✅
6. dangerous suggestion:     MW = 0（安全不倒退）            ✅
7. unverified 标注正确:      所有 weak/partial 结果均带标签    ✅
```

如果这 7 条全部通过，v0.4.5 支持的结论是：

> MemoryWeaver is not a stricter filter than strict source-gating. It is a selective harness that retains weak-but-useful signals, activates negative avoidance patterns, and cross-references partial evidence that strict policies would discard entirely.

### 实现

```
docs/validation/strict-differentiation-v0.4.5/
├── README.md
├── fixture_differentiation.jsonl   (~24-32 events)
├── queries_differentiation.jsonl   (~10-14 queries)
├── raw_results.json
├── metrics_summary.json
└── completion_status.json
```

```bash
mw bench strict-diff \
  --arms strict_verified_only,memoryweaver_source_gate \
  --output docs/validation/strict-differentiation-v0.4.5
```

---

## 第二阶段：v0.5 CoreIssueNode + HarnessMarker Schema

### 定位

不实现自动 marker 生成。只做数据结构和手动写入能力。

### 核心概念定义

```
CoreIssueNode: 经验收敛点
  → 来自 Layer 2 cluster 聚合 或 Layer 3 pattern 或二者共同
  → 标记 "这个问题是一个反复出现的核心问题"
  → 不能直接干预 runtime

HarnessMarker: runtime 中的安全干预接口
  → 从 CoreIssueNode 投影
  → 只能 route / warn / require evidence / suppress known bad path / trace
  → 不能执行工具、不能自动晋升记忆、不能绕过 user/terminal evidence
```

### 两个概念的关键区别

| | CoreIssueNode | HarnessMarker |
|---|---|---|
| 所在层 | 图谱层（经验收敛） | Runtime 层（执行干预） |
| 评分 | 这个问题是否确实是核心问题 | 这个核心问题是否适合影响 runtime |
| 状态 | candidate / active / stable / challenged / split / archived | candidate / active / verified / challenged / disabled / archived |
| 权限 | 无 runtime 权限 | 受限 runtime 权限（6 级干预） |

### 数据结构

```python
@dataclass
class CoreIssueNode:
    id: str
    title: str
    scope: dict              # {project, environment, tool, platform, model}
    applies_when: list[str]
    does_not_apply_when: list[str]
    supporting_memory_ids: list[str]
    supporting_pattern_ids: list[str]
    supporting_evidence_ids: list[str]
    contradicted_by: list[str]
    child_issue_ids: list[str]
    parent_issue_ids: list[str]
    confidence: float
    stability: float
    freshness: float
    activation_count: int
    success_count: int
    failure_count: int
    status: str              # candidate | active | stable | challenged | split | archived

@dataclass
class HarnessMarker:
    id: str
    marker_type: str         # route | guard | evidence | trace | lifecycle
    intervention_level: str  # L0_trace | L1_hint | L2_route | L3_guard | L4_require_confirmation | L5_block
    status: str              # candidate | active | verified | challenged | disabled | archived
    source_core_node_id: str
    linked_pattern_ids: list[str]
    linked_memory_ids: list[str]
    trigger_tags: list[str]
    trigger_query_patterns: list[str]
    guard_actions: list[str]
    required_evidence: list[str]
    recommended_mode: str    # thinking | fast_verify
    max_mode: str            # 通常 fast_verify，不能是 fast
    drift_score: float       # 自动计算，检测 marker 是否仍有效
    confidence: float
    activation_count: int
    success_count: int
    failure_count: int
    conflict_refs: list[str]
    policy_version: str
    created_at: str
    updated_at: str
```

### 通过标准

```
1. CoreIssueNode 和 HarnessMarker schema 可导入
2. 手动创建/读取/更新/删除 通过 mw CLI 可用
3. marker 权限规则测试通过（不能执行、不能绕过 source gate）
4. 现有 142 tests 不退化
```

---

## 第三阶段：v0.5.x 逐级激活

### v0.5.1: Marker Retrieval / Activation

只做 query → match marker → produce trace/hint。不 guard，不 block。

```
新增: MarkerStore + MarkerMatcher
能力: L0_trace, L1_hint
不可: L2_route 及以上
```

为什么从最低干预开始：candidate marker 只允许 trace，active marker 只允许 hint。确保 marker 不会在未充分验证的情况下改变 runtime 行为。

### v0.5.2: Evidence Marker + Guard Marker

加入 required_evidence 和 known_bad_path_suppression。

```
新增: EvidenceMarker activation + GuardMarker activation
能力: L3_guard
不可: L4_require_confirmation, L5_block
```

同时落地 marker 冲突检测：同一 query 命中 ≥2 个 guard marker 且建议互斥时，降级为 L1_hint + 记录 conflict event + 触发 CoreIssueNode split 候选。

### v0.5.5: CoreIssueNode Projection + Drift Detection

允许 stable CoreIssueNode → candidate HarnessMarker（需 review）。

```
新增: CoreIssueNode.projection → HarnessMarker
新增: drift_score 自动计算
       = f(最近 N 次成功率趋势, evidence 新鲜度, Layer 2 更新时间分布, scope 变更记录)
```

drift_score 超过阈值 → marker 自动 challenged，不等用户纠正。

### v0.4.4d（穿插执行）: 官方数据适配检查

不跑完整 benchmark，只确认：

```
1. MemEvoBench 数据集是否公开可下载
2. License 是否允许 benchmark 使用
3. 格式能否通过现有 memevobench_adapter 的 normalize_records 转换
4. 如不可用，在 README 写清楚 "Current validation uses built-in synthetic fixture"
```

### v0.4.4e（穿插执行）: 报告整理

把 v0.4.4a + v0.4.4b + v0.4.5 的所有结果整合到统一目录结构：

```
docs/validation/memevobench-style-v0.4.4/
├── README.md                       ← 总结性报告
├── raw_results_4a.json
├── raw_results_4b.json
├── raw_results_4b5.json            ← 4b + 4.5 合并
├── metrics_summary.json
├── fixture_small.jsonl
├── fixture_dirty_50.jsonl
├── fixture_differentiation.jsonl
├── queries.jsonl
├── completion_status.json
└── notes_official_dataset_check.md
```

Claim 降级核对：

```
不说: "MemoryWeaver passes MemEvoBench"
应说: "MemoryWeaver passes a MemEvoBench-style trust-boundary fixture"

不说: "MemoryWeaver improves agent task success"
应说: "MemoryWeaver reduces polluted retrieval, wrong promotion, and contradiction
        false-accepts in synthetic memory-misevolution fixtures"

不说: "MemoryWeaver is better than RAG"
应说: "MemoryWeaver retains useful weak signals that strict filtering discards,
        while preserving the same trust-boundary safety"
```

---

## 第四阶段：v0.6 任务级实验

### 进入条件

```
1. v0.4.5 全部 7 条通过标准满足
2. v0.5.x HarnessMarker 至少达到 L3_guard 级别
3. 至少有一个可用的外部数据集 adapter（LongMemEval-V2 或 MemEvoBench 官方子集）
```

### 实验设计

```
条件:
  C0: No persistent memory（控制组）
  C1: RAG over logs（检索原始日志文本）
  C2: MemoryWeaver without HarnessMarker（source gate + contradiction + verified retrieval）
  C3: MemoryWeaver with HarnessMarker（C2 + route/guard/evidence marker）

数据集:
  LongMemEval-V2（451 questions, 500 trajectories）的子集（20-50 trajectories）
  或 agent-memory-bench contradiction-detection 子任务

指标:
  主指标:
    steps-to-success           ← 到成功所需步骤数
    repeated_error_count       ← 重复错误次数
    known_bad_path_attempts    ← 尝试已知失败路径的次数
    tool_error_rate            ← 工具调用错误率

  辅助指标:
    path_reuse_rate            ← 复用已验证路径的比例
    memory_activation_accuracy ← 记忆激活准确率
    user_correction_count      ← 用户纠正次数

  Marker 专属指标:
    marker_helpful_rate        ← marker 触发后有正面效果的比例
    marker_harm_rate           ← marker 触发后有负面效果的比例
    counterfactual_benefit     ← 估算 "如果没有 marker 会多走多少步"
    evidence_check_order_accuracy ← 要求验证的顺序是否正确
```

### 通过标准

```
1. C3 的 steps-to-success < C1 和 C2（加了 marker 比不加更快）
2. C3 的 known_bad_path_attempts < C2 < C1（marker 减少了走错路的次数）
3. C2 的 tool_error_rate < C1（source gate 减少了错误工具调用）
4. C3 的 marker_harm_rate < 0.1（marker 不要帮倒忙）
5. C2 和 C3 的 trusted recall 不显著低于 C1（安全不倒退）
```

如果这些通过，论文可以写：

> MemoryWeaver with HarnessMarker does not merely store past experience; it converts repeatedly validated diagnostic patterns into runtime routing hints, guardrails, and evidence requirements that measurably reduce repeated errors and unsafe action attempts without granting memory nodes direct execution authority.

---

## 第五阶段：v0.7+ Alpha CLI + 集成

### v0.7: Alpha CLI + Bundle

```
mw init / doctor / validate / review / trace
mw memory / evidence / pattern / graph
mw marker / core-issue
mw export --bundle / mw import       ← 实验打包，支持复跑
mw decision-log                       ← 裁决追溯
```

参考 harness-forge 的工程化接口设计，不复制代码。

### v0.8: 离线 Sentinel

```
mw sentinel once / run / status
```

离线 watcher：发现新 memory → 检测 stale pending → 生成 offline proposal batch → 不进入在线路径。默认 LLM token budget = 0。

### v0.9: 对外 Alpha Demo

```
可演示:
  - source-gated anti-pollution（v0.4.4 已验证）
  - strict differentiation（v0.4.5 已验证）
  - marker-assisted diagnostics（v0.6 已验证）
  - mw trace 完整决策路径
  - 可复跑的 validation bundle

不可声称:
  - 官方 benchmark 成绩
  - 生产就绪
  - 跨模型/跨项目迁移
```

---

## 汇总路线图

```
2026-06 当前
├── v0.4.4a ✅ 小型 fixture + naive baseline
├── v0.4.4b ✅ dirty-50 + strict 对照
├── v0.4.5  ← 当前：strict differentiation
│    证明 MW ≠ strict filter，而是 selective harness
│    完成后再做 v0.4.4d（官方数据检查）+ v0.4.4e（报告整理）
│
2026-07/08
├── v0.5  ← CoreIssueNode + HarnessMarker schema + manual store
│    只做数据结构，不做自动生成
│
├── v0.5.1 ← L0_trace + L1_hint marker 激活
├── v0.5.2 ← L3_guard + marker 冲突检测
├── v0.5.5 ← CoreIssueNode → HarnessMarker projection + drift detection
│
2026-09/10
├── v0.6  ← 任务级实验
│    No memory vs RAG over logs vs MW vs MW+Marker
│    指标: steps-to-success, repeated errors, bad path attempts, marker helpful/harm rate
│
2026-11+
├── v0.7  ← Alpha CLI + Bundle export/import
├── v0.8  ← 离线 Sentinel watcher
└── v0.9  ← 对外 Alpha Demo
```

---

## 论文写作时机

建议在 v0.4.5 完成后写第一版论文草稿，因为此时可用的 claim 已经足够：

```
已完成验证的 claim:
  1. Source-gated polarity prevents assistant fabrications from polluting verified memory
     (v0.4.4a + v0.4.4b: pollution leak 9→0, wrong promotion 37→0)
  2. ContradictionResolver correctly blocks conflicts between verified and unverified claims
     (v0.4.4a + v0.4.4b: contradiction false accept 1.0→0.0)
  3. Source gate improves trusted recall in dirty environments by filtering out noise
     (v0.4.4b: trusted recall 0.8125 vs naive 0.625)
  4. MemoryWeaver is not equivalent to strict filtering: it retains weak-but-useful signals
     while preserving the same trust-boundary safety
     (v0.4.5, if passes)

待 v0.6 补充的 claim:
  5. HarnessMarker reduces repeated errors and unsafe action attempts
  6. MemoryWeaver + Marker outperforms both No Memory and RAG over logs on task success
```

v0.4.5 是关键分水岭——因为它把论证从 "安全" 升级到了 "安全且有独特价值"。

---

## 风险与阻塞点

| 风险 | 影响 | 缓解 |
|------|------|------|
| v0.4.5 MW 和 strict 再次没有分化 | 论文 claim 4 无法成立 | 检查 fixture 是否缺少 strict 会误杀的场景，增加 weak-but-useful + negative avoidance 密度 |
| EvidenceSupportCheck precision 不足 | CoreIssueNode 建立在不可靠 evidence 上 | 线 A 的人工标注校准不能无限推迟 |
| Marker 冷启动死锁 | 问题出现 5 次仍无 marker | v0.5 必须允许 candidate marker（L0_trace），不要求 stable CoreIssueNode |
| 官方 MemEvoBench 数据不可用 | 外部 benchmark claim 受限 | v0.4.4d 确认后直接在 README 标注 synthetic fixture |
| Pending/candidate 队列无限增长 | 存储膨胀 | v0.5 加入 auto-archive 策略（N 轮无新 evidence → archive） |
