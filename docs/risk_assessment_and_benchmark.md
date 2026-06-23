# Current Risk Assessment And Prototype Benchmark

## 结论

当前最大的工程问题不是缺少更快的 retrieval，也不是继续放大 marker runtime
projection。P0 信任边界已经闭合并进入回归门禁，当前 worktree 也已经补上
contract / action / trajectory 的最小原型。现在最关键的开放问题是：

> **如何把 verified experience 稳定地晋升成“当前最新、最合适、最可靠”的 Layer-3 execution path，并在环境变化时替换旧路径。**

如果现在继续把精力主要放在 marker novelty、FTS5 candidate reduction 或更多
boundary-only 对比上，会偏离主贡献。当前最应该加深的是：path promotion、
path competition、stale path replacement、rollback 和 sibling-task reuse。

## 2026-06-02 P0 修复验证

P0 source gate、Router gate 与 heat 生命周期修复已经进入独立验证批次。完整方法、
原始数据、五次重复实验和限制说明见：

- [P0 Trust-Boundary Validation Report](./validation/p0-trust-boundary-2026-06-02/README.md)
- [Raw Results](./validation/p0-trust-boundary-2026-06-02/raw_results.json)
- [Control Plus N Models Protocol](./validation/llm-memory-experiment-protocol.md)
- [Hugging Face Dataset Catalog](./validation/huggingface_dataset_catalog.md)

当前仓库除了保留 P0 结果外，还新增一条更贴近主贡献的验证线：

- [Layer-3 Path Promotion v0.7](./validation/layer3-path-promotion-v0.7/README.md)
- [Harness Runtime Core](./validation/harness-runtime-core/README.md)

该验证已经覆盖：

- `stable_promotion_rate = 1.0`
- `latest_path_selection_accuracy = 1.0`
- `skill_path_selection_accuracy = 1.0`
- `harness_path_selection_accuracy = 1.0`
- `stale_path_suppression_rate = 1.0`
- `rollback_success_rate = 1.0`
- `false_stable_promotion_count = 0`
- `average_path_regret = 0`

`Harness Runtime Core` 是更小但更贴近 runtime path 本质的闭环。它把
`invalid_action` benchmark-debug 任务建成 50 个同类任务，比较：

- `no_memory`
- `naive_memory`
- `summary_memory`
- `retrieval_memory`
- `memoryweaver_harness_runtime`

当前 deterministic 结果：

- `memoryweaver_harness_runtime.invalid_action_rate = 0.0`
- `no_memory.invalid_action_rate = 1.0`
- `naive_memory.invalid_action_rate = 1.0`
- `summary_memory.invalid_action_rate = 0.68`
- `retrieval_memory.invalid_action_rate = 0.5`
- `memoryweaver_harness_runtime.memory_induced_regression_rate = 0.0`
- `memoryweaver_harness_runtime.promotion_precision = 1.0`
- `memoryweaver_harness_runtime.negative_memory_hit_rate = 1.0`
- `rollback_probe.rollback_frequency = 1.0`
- `memoryweaver_harness_runtime_recovery.success_rate = 1.0`

关键 aggregate 结果：

- `repeated_failure_rate_delta_vs_no_memory = -1.0`
- `invalid_action_rate_delta_vs_naive_memory = -1.0`
- `task_success_delta_vs_retrieval_memory = 0.5`
- `memory_induced_regression_delta_vs_naive_memory = -1.0`
- `promoted_after_task_index = 3`
- `rollback_recovery_success_rate = 1.0`
- `runtime_path_store_roundtrip = 1.0`
- `persistence_probe.journal_event_count = 3`
- `persistence_probe.checkpoint_count_for_first_task = 1`

该 benchmark 现在还写出 durable runtime artifacts：

- `events.jsonl`
- `checkpoints.json`
- `runtime_path_store.json`

其中前三条 promotion 支持证据包含由 `ToolGateway` 产生的 `tool_result` hard evidence，
不是只由 benchmark 脚本手工注入。

这个 benchmark 的研究问题是：

> Can evidence-gated path promotion reduce repeated agent failures without increasing memory-induced error propagation?

历史 SDK v0.2.0 correctness 新增验证覆盖：

- `memoryweaver.cli` 可导入并通过完整 smoke chain。
- 中文重排短句召回探针 `>= 1`。
- `assistant` / `synthetic` 写入降级和检索隔离。
- `EvidenceLink` dangling 与双 target 检查。
- provisional Pattern 最大只路由到 `fast_verify`。
- stable Pattern 才允许 `fast`。
- graph tag-linking 只影响候选召回，不影响最终裁决或 Layer 3 生命周期。

P0 / v0.2.0 这批结果适合作为论文中的 **System Correctness Validation** 或
**Trust-Boundary Validation**。它们不应该再承担主实验角色。主实验角色应转给
Layer-3 path promotion 及其 sibling-task reuse / stale-path replacement / rollback
验证线。

仍保留为后续工作的风险：

- checkpoint、图谱、RAG、production 级 durable `HarnessRuntime` 与长稳测试需要对应模块继续落地。

## 风险优先级

| 优先级 | 问题 | 为什么优先 | 先做什么 |
| --- | --- | --- | --- |
| Closed | P0 信任边界 | source、tag、Router、heat 已完成五轮验证 | 保持 regression gate |
| P1 | Layer-3 path promotion 仍是小型 deterministic fixture | 已有 stable / stale / rollback / best-path 证明，但 family 数量小、环境封闭、还没接真实长期轨迹 | path competition、freshness replacement、open-world replay |
| P1 | 仅有最小 Environment Contract / ActionGate 原型 | 已有默认合同与执行前 gate，但还缺持久化合同、确认审计、真实 ToolGateway 与恢复链 | `ToolContract`、`ActionProposal`、`ActionPolicy`、审计 |
| P1 | 仅有最小 TrajectoryRegulator 原型 | 已有循环/停滞/step budget gate，但还缺 token、wall-clock、checkpoint 与跨会话恢复 | loop、stagnation、budget、recovery |
| P1 | 缺少 checkpoint、Event Journal 和幂等恢复 | ReAct 与 CLI 崩溃后可能重复副作用 | 建设 durable runtime |
| P1 | 缺少实时监测与预警 | 不能及时发现污染、雪崩、成本飙升 | metrics、trace、alerts、runbook |
| Closed | 中文与混合语言 lexical baseline | whitespace-only 已替换，短中文重排与 package/error token 有回归 | 后续进入 dense retrieval |
| P2 | 缺少更大规模的 path evolution benchmark | 现在还不能证明路径晋升在更长轨迹、更多 family、更多环境变化下稳定 | larger replay suites、path regret curves、replacement tests |
| P2 | 缺少最小 GBrain | tag、关系、版本和 Pattern lineage 难组织 | `GraphProjector`、point get、1-hop expansion |
| P2 | 缺少快速 ReAct | 复杂任务不能稳定自动执行 | bounded loop、ToolGateway、job queue |
| P2 | 缺少 RAG Evidence Layer | 外部证据检索仍停留在设计 | cleaning、chunk、metadata、hybrid retrieval |
| P3 | 缺少离线维护面 | 无法大规模演进图谱和检索链 | DSL、offline eval、shadow、canary |

Collaborative Specialist Routing 的分层升级、降级和 benchmark 方案见
[collaborative_specialist_routing.md](./collaborative_specialist_routing.md)。

## 为什么图谱不是第一步

图谱会扩大传播范围。一个被错误晋升的 tag、edge 或 Pattern 可以影响更多查询。
因此推荐顺序：

```text
信任边界
  -> 回归与 benchmark
  -> contract、ActionGate、TrajectoryRegulator
  -> checkpoint、监测、预警
  -> 最小图谱点取
  -> bounded ReAct
  -> 大规模 RAG 与图谱维护
```

## 实时监测与预警

至少记录：

| 类别 | 指标 |
| --- | --- |
| 记忆正确性 | promotion rate、demotion rate、pollution rate、conflict rate |
| 检索质量 | Recall@k、citation coverage、zero-result rate、fast-path false-positive |
| 图谱质量 | candidate edge rate、alias merge rate、stale node rate、projection lag |
| ReAct | step count、loop abort、tool calls、checkpoint recovery、duplicate side effect |
| 性能 | p50、p95、p99、queue depth、timeout、cache hit、RSS、KV cache usage |
| 成本 | token、model calls、retry cost、RAG cost、CLI worker minutes |
| 安全 | prompt injection block、authorization deny、secret detection、tenant violation |

初始预警：

- assistant 或 `SYNTHETIC` 来源尝试进入 verified memory。
- tag 检索返回默认不可见来源。
- fast-path false-positive 突增。
- conflict rate、zero-result rate、retry rate 或 queue depth 突增。
- RSS、KV cache、磁盘、日志或 checkpoint 延迟持续升高。
- snapshot 切换后 retrieval quality 明显下降。
- tenant scope 不一致或 CLI 副作用重复。

## 测试体系遗漏补充

完整测试目录见 [agent_test_catalog.md](./agent_test_catalog.md)。附件中的 64 项清单
已经覆盖大部分通用 Agent 能力。本项目还要额外强调：

1. memory poisoning 与 source-gated anti-pollution。
2. GBrain 投影幂等、alias 环和 temporal edge。
3. RAG snapshot、GBrain snapshot、policy version 与 cache namespace 一致性。
4. checkpoint 恢复后 CLI 副作用不重复。
5. 离线维护模型生成 Retrieval Plan DSL 后的 shadow、canary 和 rollback。
6. fast-path false-positive 与错误晋升率，而不只看平均延迟。
7. 删除、保留期限、PII 和跨 tenant memory 擦除。
8. benchmark 可重复性：固定数据、环境、版本与结果记录。

## Prototype Benchmark

运行方式：

```powershell
python .\benchmarks\prototype_baseline.py
```

基线脚本覆盖：

- JSON-backed `MemoryStore.add()`。
- JSON store reload。
- `find_by_tags()`。
- `VerifiedRetriever.search_by_tags()`。
- `find_similar()`。
- `VerifiedRetriever.search()`。
- CLI、heat、tag gate、assistant polarity、EvidenceLink、Policy、provisional/stable Pattern、Router 绕行和中文召回探针。

注意：

- 这是本地原型 microbenchmark，不是生产容量认证。
- 当前 `MemoryStore.add()` 每次都会整体重写 JSON 文件，写入复杂度会随数据量明显
  变差。
- 图谱、RAG、CLI、checkpoint、并发、崩溃、雪崩与长稳 benchmark 需要在对应模块
  落地后增加。

### 2026-06-01 Local Baseline

环境：

```text
Python 3.14.0
Windows 11 10.0.26200
query iterations: 100
```

正确性探针：

| 探针 | 当前结果 | 目标 |
| --- | --- | --- |
| `memoryweaver.cli` 存在 | `false` | `true` |
| 普通 update 后 heat | `1` | `0` |
| tag search 返回未验证 assistant | `true` | `false` |
| assistant positive 可直接构造 | `true` | `false` |
| 未验证 assistant Pattern 触发 Router | `fast` | 不得进入 fast |
| 中文重排短句召回数 | `0` | `>= 1` |

性能结果：

| items | JSON 大小 | 写入 items/s | reload ms | tag p95 ms | verified text p95 ms |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 100 | 75,465 B | 266.08 | 11.65 | 0.18 | 0.27 |
| 500 | 378,025 B | 81.57 | 13.62 | 0.53 | 1.46 |
| 1,000 | 756,225 B | 44.96 | 117.32 | 1.09 | 2.91 |

解释：

- 读取路径在 1,000 条原型数据下仍然较快。
- 写入吞吐随条目数量明显下降，因为每次 `add()` 都整体重写 JSON 文件。
- 这份结果用于修复前后的对照，不应外推为生产容量。

## 下一组 Benchmark

| 阶段 | Benchmark |
| --- | --- |
| SDK v0.2.0 后 | 对比 source gate、Router、heat、Policy、EvidenceLink、Pattern 与中文召回前后结果 |
| v0.3.0 任务实验 | No Memory vs RAG over logs vs MemoryWeaver v0.2.0，比较 steps-to-success、repeated errors、path reuse、tool errors、memory activation accuracy |
| Graph tag-linking | tag expansion、graph candidate narrowing、Evidence/Pattern lineage、wrong/stale link rate |
| 最小 GBrain 后 | point get、tag lookup、1-hop expansion、projection throughput |
| RAG MVP 后 | ingest throughput、Recall@k、p95、HNSW、hybrid、rerank |
| ReAct MVP 后 | step latency、CLI queue、checkpoint、crash recovery、duplicate side effect |
| 生产候选后 | average-load、stress、spike、breakpoint、soak、snowball failure |

## 2026-06-11 Safety Closure Record

本轮目标不是新增 ReAct、GBrain 或 RAG 功能，而是把 benchmark 和 action gate 的安全债收口，降低论文复现与本地验证时的文件系统风险。

### 结论

- `ActionPolicy` 已扩展高风险动作识别：覆盖 `del`、`erase`、`rmdir`、`Remove-Item`、`format`、`iex`、`chmod`、`chown`，并解析 `target`、`arguments`、`reasoning` 中的命令 token。
- 高风险动作不会被静默执行，而是进入 confirmation / idempotency gate；低风险 `check_evidence` 仍保持低风险，不被误伤。
- benchmark 清理逻辑已集中到 `benchmarks/_safety.py::safe_rmtree_child`；直接 `shutil.rmtree(...)` 只允许存在于该 helper 内部。
- benchmark 临时 workspace 删除必须同时满足两个条件：目标路径位于父输出目录内，且目录名匹配明确的临时前缀。
- `harness_runtime_coding_debug.py` 的临时目录已从裸 `workspace` 迁到 `.coding-debug-workspace`，replay workspace 也迁到 `.coding-debug-replay-workspaces`。
- live LLM validation 已完成真实 `--llm` pass^3：`live_llm_run_complete = 1.0`，`online_llm_call_count = 3.0`，`pass_power_3 = true`，seeds = `[21, 22, 23]`。

### 已验证

```powershell
python -m pytest tests\test_action_gate.py tests\test_benchmark_safety.py -q
```

结果：

```text
20 passed
```

受 benchmark 清理迁移影响的测试子集：

```text
31 passed
```

计划内 benchmark smoke：

```powershell
python benchmarks\harness_runtime_core.py --output-dir docs\validation\harness-runtime-core
python benchmarks\harness_runtime_trace_loop.py --output-dir docs\validation\harness-runtime-trace-loop
python benchmarks\harness_runtime_live_llm.py --llm --provider deepseek --model deepseek-chat --output-dir docs\validation\harness-runtime-live-llm --reliability-passes 3 --seed 21
python benchmarks\harness_runtime_coding_debug.py --output-dir docs\validation\harness-runtime-coding-debug
```

结果：全部 passed。

全量回归：

```powershell
python -m pytest -q
```

结果：

```text
322 passed in 243.48s
```

静态检查：

```powershell
rg "shutil\.rmtree\(" benchmarks
```

结果：只剩 `benchmarks/_safety.py` 内部实现点。

### TODO

| 优先级 | TODO | 原因 | 预期验证 |
| --- | --- | --- | --- |
| P0 | 保持 live LLM artifact 的真实运行口径 | 当前 artifact 明确 `online_llm_call_count = 3.0` 且 `pass_power_3 = true` | grep validation README / claim mapping，确认 wording 为 real `--llm` pass^3 |
| P0 | coding-debug 增加跨独立运行 pass^3 `reliability.json` | 当前有真实 pytest/diff，但缺跨 run 可靠性证据 | `tests_passed_pass3 = true`、`diff_matches_expected_pass3 = true`、`pass3_std = 0` |
| P0 | 将 coding-debug 指标接入 `claim_metric_mapping.md` 和 `claim-snapshot.md` | 论文证据链需要 claim -> metric -> artifact 显式映射 | `rg "coding-debug|tests_passed|file_diff_matches_expected" docs` |
| P1 | 为 `ActionPolicy` 增加更多 shell 边界样本 | 当前 token gate 已覆盖核心危险词，但还不是完整 shell parser | Windows / POSIX 高风险命令参数化测试 |
| P1 | 给 benchmark workspace 前缀建立统一命名约定 | 当前前缀已安全，但分散在各 benchmark 中 | `rg "allowed_prefixes" benchmarks` 人工审查 |
| P1 | RuntimePath schema 对齐 live-LLM / trace-loop / coding-debug | 后续论文比较实验需要统一字段口径 | schema key set comparison test |
| P2 | 将安全收口纳入 current-stage-check | 避免后续新增 benchmark 再引入裸 `rmtree` | current-stage-check 检查 `shutil.rmtree` 只在 `_safety.py` |

### 当前边界

- 这是工程安全收口，不是生产沙箱认证。
- `safe_rmtree_child` 防止 benchmark 删除跑出 output subtree，但不替代 OS-level sandbox。
- `ActionPolicy` 是 deterministic gate，不是完整 shell 安全分析器。
- 当前最强论文证据来自 controlled fixture、trace-loop、real pytest/diff coding-debug、以及真实 live LLM pass^3。边界仍然是：它证明真实模型提案能进入 Harness evidence gate，不证明开放世界长期任务成功率。
