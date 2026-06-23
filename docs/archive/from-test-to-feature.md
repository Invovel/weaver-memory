# 从测试到落地：MemoryWeaver 的功能优先路线

## 问题诊断

现在已经有 25 个 validation README、18 个 benchmark 脚本、8000+ 行 benchmark 代码。每一轮验证都在证明"某个组件能正常工作"。但还没有一个对外可见的功能闭环。

核心矛盾：**你一直在验证组件，不是在交付功能。**

验证型开发的特点：每做完一个版本，产出一个 README，里面是"Passed: True"和一组 metrics。下一个版本再做更精细的验证。这些 README 加起来是一条完整的论证链——但它们不是功能。外人 clone 项目后，能跑的是 `mw` CLI，能看到的是 `mw doctor` 和 `mw trace`。没人能跑一个真实的 agent loop 然后看到 MW 改变了 LLM 的行为。

## 落地方案：三周内交付三个功能线

不再按版本号渐进验证。三周分三条功能线并行推进。

---

## 功能线 1：外部数据一键导入（Week 1）

### 目标

用户执行一条命令，从 HuggingFace 下载数据集，自动转成 MemoryWeaver events，跑 source gate，输出报告。

### 不做的

- 不做 12 个质量指标（v0.6.4b 推迟）
- 不做 full benchmark 评估（v0.6.5 推迟）
- 不做跨数据集对齐（v0.6.4c 推迟）

### 具体交付

```bash
mw dataset import longmemeval-v2
  → 下载 xiaowu0162/longmemeval-cleaned
  → 筛选 coding/tool-use trajectory
  → 转成 RawSpan → ContextCapsule → MemoryItem
  → 输出: 导入了多少条 trajectory、多少条 candidate memory
  → 全部 Layer-1 dry-run，不写 memory

mw dataset import locomo
  → 同样流程，proof of concept 覆盖第二个数据集

mw dataset list
  → 显示已导入的数据集、trajectory 数量、license、导入时间
```

### 需要的代码变更

不是新 benchmark，是 CLI 功能扩展：

```
memoryweaver/
├── dataset/
│   ├── __init__.py
│   ├── adapters/
│   │   ├── longmemeval.py      # 80% 现有 adapter 逻辑移过来
│   │   ├── locomo.py           # 新的
│   │   └── base.py             # ExternalEpisode, ExternalTurn
│   ├── registry.py             # dataset_registry.json CRUD
│   └── importer.py             # download + convert + report
└── cli.py                      # 新增 mw dataset 子命令
```

### 通过标准

```
1. mw dataset import longmemeval-v2 成功，输出 trajectory 和 candidate 统计
2. mw dataset import locomo 成功（即使数据量更小）
3. mw dataset list 显示两个数据集
4. 全程 policy_gate_leak_count = 0
5. 全程无 memory promotion / Layer-3 mutation
```

---

## 功能线 2：Live Agent Loop 可演示（Week 2）

### 目标

用户执行一条命令，指定一个 5 条 trajectory 的 task set，DeepSeek 真实决策每一步，MW 三种策略（no memory / MW memory / MW+marker）对比。输出三列步数和坏动作。

### 不做的

- 不扩展到 50 条 trajectory
- 不做 full benchmark 指标
- 不做真实 tool 执行
- 不做 driver loop（由 MW 驱动 LLM，而不是 LLM 驱动 MW）

### 具体交付

```bash
mw agent run --dataset longmemeval-v2 --limit 5 --arms no_memory,mw_memory,mw_marker
  → 每张 trajectory 跑三轮
  → 每步 LLM 决策 → MockToolRuntime 执行 → LLM 看到结果 → 下一步
  → 输出: 三种 arm 的步数、LLM call 数、known_bad action 尝试数、evidence first hit rate
```

### 需要的代码变更

你已经写了 `benchmarks/live_agent_loop_v0_6_3.py`。把它升级为 CLI 驱动的功能模块，而非一次性 benchmark：

```
memoryweaver/
├── agent/
│   ├── __init__.py
│   ├── loop.py              # 从 live_agent_loop_v0_6_3.py 移过来的核心循环
│   ├── tool_runtime.py       # MockToolRuntime
│   └── llm_client.py         # _call_deepseek 独立出来
└── cli.py                    # 新增 mw agent 子命令
```

不在 benchmarks 目录下加新文件。benchmarks 目录里的旧文件保持原样，标注 superseded。

### 通过标准

```
1. mw agent run --limit 3 成功跑完 3 条 trajectory × 3 arms = 9 个 agent loop
2. 输出表格: arm / avg_steps / avg_llm_calls / known_bad_attempts / evidence_first_hit
3. MW marker arm 的 known_bad_attempts <= no_memory arm（不强制差值，只要求不更差）
4. 全程 online_llm_call_count > 0（真的调了 API）
5. 全程 real_tool_execution_count = 0
```

---

## 功能线 3：端到端 Trace 可见（Week 3）

### 目标

用户跑完 `mw agent run` 后，可以执行 `mw trace` 回看某条 trajectory 上 MW 每一步做了什么决策：哪条记忆被检索了、source gate 是否拦截了什么、marker 是否激活了、marker 的推荐和 LLM 的实际选择是否一致。

### 不做的

- 不做决策对比分析（v0.6.4b 的 12 个质量指标推迟）
- 不做已知坏路径检测率统计

### 具体交付

```bash
mw trace --trajectory-id <id>
  → Step 1: query matched → retrieved 3 candidate memories (1 blocked by source gate)
  → Step 2: marker activated "avoid_npm_reinstall" → suppressed action: reinstall npm
  → Step 3: LLM chose "check organization" (marker hint followed)
  → Step 4: evidence observed → resolved
  → Total: 4 steps, 0 known bad actions

mw trace --compare <id>
  → no_memory: 7 steps, 3 known bad, user corrected
  → mw_memory: 5 steps, 1 known bad
  → mw_marker: 4 steps, 0 known bad
```

### 需要的代码变更

在 v0.5 的 `mw trace` 基础设施上扩展。不需要新模块。

### 通过标准

```
1. mw trace --trajectory-id <id> 输出可读的步骤级决策日志
2. mw trace --compare <id> 输出三列对比
3. 每一步都标注 source（LLM 选择 / marker 推荐 / source gate 拦截）
```

---

## 三条线完成后的最终交付物

```
1. mw dataset import longmemeval-v2    → 外部数据一键导入
2. mw agent run --limit 5              → 真实 LLM agent 行为对比
3. mw trace --compare <id>             → 端到端决策追溯
```

这三个命令贯穿 MemoryWeaver 的完整功能路径：数据从哪里来 → agent 怎么用 → 每一步发生了什么。

## 哪些东西明确推迟

以下功能不做，等 v0.7 之后再考虑：

```
- 12 个质量指标（v0.6.4b 推迟）
- 跨数据集对齐（v0.6.4c 推迟）
- full benchmark 评估（v0.6.5 推迟）
- DatasetRegistry 完整化
- DataOrigin / ClaimLevel 枚举落地
- 完整 baseline 对比（Mem0、RAG、full-context）
- SWE-bench Lite
- LongMemEval 100 questions 全量
- 新 feature 不放在 benchmarks/ 目录下
```

这些不是不重要。它们是在核心功能闭环跑通之后，提升论文说服力的工作。但现在缺的是别人能跑的东西。

## 和之前路线的区别

| | 旧路线（v0.4.4 → v0.6.5） | 新路线（三周三条线） |
|---|---|---|
| 节奏 | 每个版本一个 README + metrics | 每条线一个 CLI 功能 |
| 验证对象 | 组件是否正确 | 用户能否跑通整个流程 |
| 外人视角 | 25 个 README 串起来的论证 | 3 个命令的可演示闭环 |
| v0.6.2/v0.6.3 | 硬编码轨迹/mock LLM benchmark | 升级为 mw agent run（保留 mock tools） |
| v0.6.4a | LongMemEval smoke spike | 升级为 mw dataset import |
| 新 benchmark | 继续在 benchmarks/ 加脚本 | 不再新增 benchmark，功能放入 memoryweaver/ |
| 论文 | 每一轮验证收集一张表 | 核心闭环跑通后集中写 |

## 最高优先级的三件事（本周）

```
1. mw dataset import longmemeval-v2 能跑
   → 把 v0.6.4a 的 adapter spike 从 benchmark 脚本升级为 CLI 功能

2. mw agent run --limit 3 能跑
   → 把 live_agent_loop_v0_6_3.py 从 benchmark 脚本升级为 CLI 功能
   → DeepSeek API key 已可用

3. mw trace --compare 能跑
   → 在 v0.5 的 trace 基础设施上扩展对比视图
```
