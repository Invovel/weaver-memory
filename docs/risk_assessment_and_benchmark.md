# Current Risk Assessment And Prototype Benchmark

## 结论

当前最大的工程问题不是缺少完整图谱，也不是缺少更快的 ReAct。P0 信任边界已经
闭合并进入回归门禁，SDK v0.2.0 已补齐 CLI、Policy、Evidence 和 provisional
Pattern 基础。当前最大的开放问题是：

> **动作生命周期边界、可恢复运行链、GBrain 投影和完整 RAG pipeline 尚未落地。**

如果现在直接扩大图谱写入、加入自动 ReAct 或摄入大量 RAG 文档，Pattern、图谱
投影、工具动作和恢复路径仍缺少统一运行时策略。

## 2026-06-02 P0 修复验证

P0 source gate、Router gate 与 heat 生命周期修复已经进入独立验证批次。完整方法、
原始数据、五次重复实验和限制说明见：

- [P0 Trust-Boundary Validation Report](./validation/p0-trust-boundary-2026-06-02/README.md)
- [Raw Results](./validation/p0-trust-boundary-2026-06-02/raw_results.json)
- [Control Plus N Models Protocol](./validation/llm-memory-experiment-protocol.md)
- [Hugging Face Dataset Catalog](./validation/huggingface_dataset_catalog.md)

SDK v0.2.0 新增验证覆盖：

- `memoryweaver.cli` 可导入并通过完整 smoke chain。
- 中文重排短句召回探针 `>= 1`。
- `assistant` / `synthetic` 写入降级和检索隔离。
- `EvidenceLink` dangling 与双 target 检查。
- provisional Pattern 最大只路由到 `fast_verify`。
- stable Pattern 才允许 `fast`。
- graph tag-linking 只影响候选召回，不影响最终裁决或 Layer 3 生命周期。

这批结果适合作为论文中的 **System Correctness Validation** 或
**Trust-Boundary Validation**。它不适合作为主实验，因为它尚未证明任务成功率、
解决速度、重复错误率或跨模型复用能力的改善。

仍保留为后续工作的风险：

- checkpoint、图谱、RAG、ActionGate 与长稳测试需要对应模块落地后再执行。

## 风险优先级

| 优先级 | 问题 | 为什么优先 | 先做什么 |
| --- | --- | --- | --- |
| Closed | P0 信任边界 | source、tag、Router、heat 已完成五轮验证 | 保持 regression gate |
| P1 | 缺少 Environment Contract 与 ActionGate | 工具执行前没有统一 schema、权限、风险和确认边界 | `ToolContract`、`ActionProposal`、`ActionPolicy` |
| P1 | 缺少 TrajectoryRegulator | 重复失败、停滞和预算耗尽缺少确定性恢复 | loop、stagnation、budget、recovery |
| P1 | 缺少 checkpoint、Event Journal 和幂等恢复 | ReAct 与 CLI 崩溃后可能重复副作用 | 建设 durable runtime |
| P1 | 缺少实时监测与预警 | 不能及时发现污染、雪崩、成本飙升 | metrics、trace、alerts、runbook |
| Closed | 中文与混合语言 lexical baseline | whitespace-only 已替换，短中文重排与 package/error token 有回归 | 后续进入 dense retrieval |
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
