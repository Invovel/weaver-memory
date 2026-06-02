# Agent Test Catalog

## 文档状态

本文是完整测试目录，用于记录需要覆盖的 Agent 能力。执行频率、发布门禁、故障
矩阵与测试记录模板见
[testing_resilience_strategy.md](./testing_resilience_strategy.md)。

## 1. 基础功能

| 测试 | 覆盖内容 |
| --- | --- |
| Smoke | 启动、输入、模型、输出、基础工具、超时 |
| Functional | 问答、总结、抽取、代码、报告、表格、任务执行 |
| Structured output | JSON、Markdown、schema、字段类型、异常格式 |
| Input boundary | 空输入、超长、重复、乱码、特殊符号、中英混合、损坏文件 |
| Schema / contract | Harness、RAG、GBrain、CLI、checkpoint 接口兼容 |

## 2. Agent 智能能力

| 测试 | 覆盖内容 |
| --- | --- |
| Multi-turn | 指代、话题恢复、任务切换、中途改需求 |
| Context consistency | 结论、引用、名词、目标一致性 |
| Planning | 拆分、依赖、顺序、动态调整、避免无意义步骤 |
| Task success | 完全成功、部分成功、失败、假成功、人工补救 |
| Long context | 长文档、多文件、历史压缩、截断与抗干扰 |
| Memory | 应记、不应记、删除、隔离、过期、冲突澄清 |
| Clarification | 合理追问、不过度追问、说明假设 |
| Instruction following | 格式、语言、长度、禁止事项、指令优先级 |
| Fast-path correctness | point get、Pattern、Fast + Verify、ReAct 升级路径 |
| Environment contract | 工具 schema、source authority、policy version、环境约束 |
| Action realization | `ActionProposal`、执行前参数、权限、风险和确认 |
| Trajectory regulation | 重复失败、停滞、预算、恢复和审计 |
| Specialist routing | L0 / L1 / L2 升级、降级、超时、冲突和 EvidencePacket |

## 3. RAG、图谱与事实性

| 测试 | 覆盖内容 |
| --- | --- |
| Retrieval | Recall、Precision、Top-k、延迟、版本与同义表达 |
| Faithfulness | 文档忠实性、资料不足、事实与推测区分 |
| Citation accuracy | 引用存在、结论支持、页码、段落、版本 |
| Hallucination | 不存在概念、不完整资料、冲突资料、精确数字诱导 |
| Conflicting evidence | 新旧版本、用户、工具、网页、论文冲突 |
| Freshness | 最新资料、历史资料、时间敏感查询与具体日期 |
| Graph point retrieval | memory ID、canonical tag、entity ID 精确查询 |
| Graph local search | 1-2 hop 扩展、关系类型、focal node |
| Graph temporal | `valid_from`、`valid_to`、`SUPERSEDES`、stale node |
| Graph global search | community summary、大范围分类与主题覆盖 |
| Graph projection | Layer 2 tag 投影、alias、幂等写入、provenance |
| Anti-pollution | assistant、synthetic、raw chunk 不可直入 verified memory |
| Chinese retrieval | 中文 tokenizer、中英混合、错误码、包名 |

## 4. 工具调用

| 测试 | 覆盖内容 |
| --- | --- |
| Tool selection | 该调用时调用，不该调用时不调用，工具选择正确 |
| Tool parameter | 参数字段、类型、日期、路径、关键词 |
| Tool interpretation | 空结果、错误、关键字段、多工具结果融合 |
| Tool failure recovery | 超时、限流、500、网络、权限、格式错误 |
| Multi-tool | 顺序、依赖传递、部分失败、避免循环 |
| Side-effect | 删除、写库、提交、发送、发布、付款前确认 |
| Idempotency | checkpoint 恢复后不重复执行副作用 |
| Sandbox | allowlist、工作目录、资源预算、超时和取消 |
| Action gate | 非法 schema、危险命令、未确认副作用、重复幂等键 |

## 5. 安全与对抗

| 测试 | 覆盖内容 |
| --- | --- |
| Safety boundary | 恶意代码、隐私、高风险医疗、法律、金融请求 |
| Prompt injection | 用户、网页、PDF、邮件、RAG chunk、tool output |
| Jailbreak | 角色扮演、编码混淆、多语言、伪造授权 |
| Authorization | tenant、project、user、thread、scope 隔离 |
| Privacy | PII、API key、token、密码、日志脱敏 |
| Data leakage | 系统提示、开发者指令、私有文件、跨会话泄漏 |
| Human confirmation | 高风险副作用前确认 |
| Adversarial | 嵌套指令、矛盾指令、伪造工具结果、超长输入 |
| Memory poisoning | 恶意 tag、entity、Pattern、community summary 污染 |

## 6. 稳定性与恢复

| 测试 | 覆盖内容 |
| --- | --- |
| Crash | 空响应、网络断开、文件损坏、并发冲突、多轮中断 |
| Memory crash | OOM、KV cache 压力、context overflow、磁盘满 |
| Memory leak | 千轮对话、连续工具、RAG 查询、日志与缓存增长 |
| Avalanche | 缓存击穿、429、重试风暴、连接池满、队列积压 |
| Fault injection | 关闭服务、网络抖动、API 500、DB 超时、权限失效 |
| Timeout | 模型、工具、检索、解析、多步骤任务 |
| Retry | 次数上限、指数退避、可重试分类、副作用保护 |
| Concurrency | 多用户、多会话、结果错配、session 串线 |
| Checkpoint recovery | 恢复、重放、乐观锁、新会话 handoff |
| Disaster recovery | snapshot、restore、rollback、RPO、RTO |

## 7. 性能与成本

| 测试 | 覆盖内容 |
| --- | --- |
| Smoke performance | 最小流量下脚本与 baseline |
| Average-load | 典型日常流量 |
| Stress | 高于典型流量时的退化曲线 |
| Spike | 瞬时暴增与恢复 |
| Breakpoint | 持续增压直至失败边界 |
| Soak | 24 小时、7 天、泄漏、日志和延迟漂移 |
| Latency | 首 token、总响应、RAG、Graph、CLI、解析 |
| Throughput | RPS、任务数、文档 ingest、工具并发、队列速度 |
| Cost | token、工具、失败、重试、RAG、模型路由 |
| Token usage | 历史、证据、工具结果、压缩和预算 |
| Specialist cost | specialist 数量、升级率、每级 latency、fallback 与模型成本 |

## 8. 发布与效果

| 测试 | 覆盖内容 |
| --- | --- |
| Regression | Prompt、模型、工具、RAG、Graph、policy 变化 |
| Offline eval | 固定 golden dataset |
| Shadow | 真实流量旁路比较 |
| Canary | 1%、5%、10% 灰度与自动回滚 |
| A/B | Prompt、模型、RAG、记忆、安全策略对比 |
| Production monitoring | 成功率、延迟、成本、失败、安全和投诉 |
| Human eval | 正确、完整、有用、安全、事实性、意图满足 |
| LLM-as-Judge | 辅助评分；关键业务仍需人工抽检 |

## 9. 用户体验

| 测试 | 覆盖内容 |
| --- | --- |
| Readability | 清晰、结构、重点、术语、冗余 |
| Explainability | 依据、不确定性、引用、事实与推测 |
| Interaction UX | 响应、中断、追问、承接修改、失败说明 |
| Tone and style | 语言、品牌语气、专业性、用户群适配 |

## 10. 领域专项

| 测试 | 覆盖内容 |
| --- | --- |
| Medical | 避免直接诊断、紧急症状、可靠来源 |
| Legal | 地区差异、法条真实性、专业咨询提示 |
| Financial | 市场时效、风险提示、避免承诺收益 |
| Coding agent | 可运行、测试、安全、项目结构、无关改动 |
| Data analysis | 字段、统计、缺失值、异常值、可复现性 |
| Document agent | PDF、表格、图片、摘要、页码、版本差异 |

## 11. 本项目必须额外覆盖

通用 Agent 清单之外，MemoryWeaver 必须补充：

1. Harness source gate 与所有绕行路径。
2. Layer 1、Layer 2、Layer 3 晋升、降权和删除。
3. negative avoidance memory 的保留与召回。
4. HyDE `SYNTHETIC` provenance。
5. Layer 2 tag 到 GBrain 的可重建投影。
6. cache namespace、snapshot 与 policy version。
7. RAG、GBrain、LLM、CLI 独立熔断与降级。
8. 新会话 `ContextPack` 接续与旧 checkpoint 迁移。
9. memory pollution rate、fast-path false-positive rate。
10. 离线维护面生成的 Retrieval Plan DSL 发布门禁。
11. Collaborative specialist routing 的升级率、冲突率和错误晋升率。
