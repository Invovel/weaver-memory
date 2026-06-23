# PathoFlow Tool-Native Workflow Compare

This validation skips all LLM calls and uses PathoFlow's own non-LLM modules
to see what the repository can really do right now with tool-native flow logic.

## Result

- Planner probe count: 3
- Tool execution probe count: 6
- Previous offline replay runtime any-hit rate: 0.372
- Previous offline replay canonical any-hit rate: 0.5755

## What Was Actually Executed

- cpu_pseudo_detection_only: tool=5-pancreas-tumor-detection, mode=cpu_pseudo, success=True, file_count=3, state=completed
- demo_foreground_mask_only: tool=1-foreground-segmentation, mode=demo, success=True, file_count=1, state=completed
- demo_overlay_expected_gap: tool=59-generate-overlays, mode=demo, success=True, file_count=1, state=completed
- demo_nucleus_mask_only: tool=4-nucleus-segmentation-hovernet-pannuke, mode=demo, success=True, file_count=1, state=completed
- demo_macenko_expected_gap: tool=52-Global-Macenko, mode=demo, success=True, file_count=1, state=completed
- cpu_pseudo_breast_detection: tool=6-breast-tumor-detection, mode=cpu_pseudo, success=True, file_count=3, state=completed

## Multi-Step Attempt

- Attempt success: True
- Overlay preflight ready: True
- Overlay execution status: completed
- Overlay returned files: 1

## Multi-Step Chain Matrix

- chain_foreground_to_overlay: preflight=True, execution=completed, output_files=1
- chain_nucleus_to_overlay: preflight=True, execution=completed, output_files=1
- chain_detection_to_overlay: preflight=True, execution=completed, output_files=1
- chain_macenko_to_detection: preflight=unknown, execution=unknown, output_files=1

## Sequential Chain Execution

- tool_executor_foreground_overlay: success_count=2, failure_count=0, skipped_count=0
- tool_executor_nucleus_overlay: success_count=2, failure_count=0, skipped_count=0
- tool_executor_detection_overlay: success_count=2, failure_count=0, skipped_count=0
- tool_executor_macenko_detection: success_count=2, failure_count=0, skipped_count=0

## Current Executable Workflow Graph

```mermaid
flowchart LR
  A["H&E前景分割\n1-foreground-segmentation\nstatus: ok"]
  B["细胞核分割\n4-nucleus-segmentation-hovernet-pannuke\nstatus: ok"]
  C["CPU伪检测\n5/6 detection\nstatus: ok"]
  D["混叠预览\n59-generate-overlays\nstatus: ok"]
  E["染色归一化\n52-Global-Macenko\nstatus: ok"]
  A -->|foreground_mask| D
  B -->|nucleus_mask| D
  C -->|tumor_mask + report| D
  E -->|normalized_slide| C
```

## Planner Drift

- planner_qc_lung: query=`对肺癌NDPI批次进行信息汇总和质控，筛出不适合后续分析的低质量切片。` -> primary=`全景病理切片质量控制(GrandQC)` (wish_40_grandqc)
- planner_tme_lung: query=`对肺癌H&E切片进行TILs/免疫浸润/TME代理分析。` -> primary=`Foreground, Nucleus, Pathomics, and Survival Analysis` (workflow_foreground_nucleus_pathomics_survival)
- planner_ihc_lung: query=`对肺癌IHC切片进行阳性阴性细胞定量。` -> primary=`免疫组化阳性、阴性细胞检测分割(DeepLIIF)` (wish_41_deepliif)

## TME Audit

- `tme_reduced_execution_audit.json`
- `tme_reduced_execution_audit.md`

## DeepSeek Structured Output

- `deepseek_structured_output_audit.json`

Current conclusion for `deepseek-v4-pro`:

- transport/provider connectivity is normal
- strict JSON in `task_planning` is now materially fixed
- the previous structured-output failures were mainly caused by JSON truncation at `max_tokens=2048`, empty `content` with useful text in `reasoning_content`, and free-text numeric ranges being misread as tool IDs
- `general` intent still returns free text under the current PathoFlow framework contract, but it is now marked as `_free_text_response=true` instead of being surfaced as a fake `_parse_error`

These artifacts capture the strongest current evidence for the reduced TME
child chain across planner, active preparer, run_preparer, executable_flow,
API real-preflight, API mock execute, and API execute-real.

## Comparison With Previous Workflow

- 上一版主要是 prepare_context / retriever 回放，缺少真正的工具执行结果目录与 manifest。
- 代表性 planner query 已不再全部漂移到肝内胆管癌检测；当前 QC=1, TME=1, IHC=1。
- demo overlay 与 demo Macenko 已不再是 success=true 且 file_count=0；当前零输出用例数=0。
- CPU_PSEUDO 和 DEMO 执行器可以产出真实 result_manifest，这证明无 LLM 时仍能走一条工具驱动的流程，但覆盖范围仍小于上一版理论工具链。
- 当前 reviewed TME composite 已能在 planner / preparer / executable_flow / API real-preflight / mock execute 路径中被展开理解，但真实多步执行仍是受控、缩减后的验证路径。
- 上一版 workflow 里大量工具来自数据集标注主链，而不是 PathoFlow 当前无 LLM planner 自己稳定规划出来的链路；两者不能等价看待。

## Bottom Line

上一版不是“完全没结果”，但它的结果主要是离线检索/规则回放结果，不是 PathoFlow 当前仓库在无 LLM 条件下自己完整规划并稳定执行出来的全流程。
这次的新证据说明：PathoFlow 现在在无 LLM 条件下已经修复了 overlay / Macenko 零输出、detection->overlay 契约，以及代表性 planner 漂移问题；剩余主问题已经收缩到 reviewed TME 复合链的真实多步执行仍然是受控、缩减后的验证路径。

## Daily Report - 2026-06-15

### 今日完成

- 重新核对了 PathoFlow 在无 LLM 条件下的 tool-native workflow，对比前一版验证结果，确认 demo overlay 和 demo Macenko 已从 `file_count=0` 修复到 `file_count=1`。
- 复核了多步链矩阵，确认 `foreground -> overlay`、`nucleus -> overlay`、`detection -> overlay` 三条代表性链路已经能完成 preflight + execution。
- 复核了代表性 planner query 的漂移情况，当前肺癌场景下已经能分别命中 `GrandQC`、`workflow_foreground_nucleus_pathomics_survival`、`DeepLIIF`，不再全部漂移到肝内胆管癌检测。
- 补充了 reduced TME child chain 的执行审计，确认它已经贯通 `planner`、`active preparer`、`run_preparer`、`executable_flow`、`mock execute`、`execute-real` 这些关键验证点。
- 补充了 `deepseek-v4-pro` structured output 审计，收口了 task-planning 严格 JSON 路径的主要问题来源，并把“provider/transport 故障”和“framework contract 的 free-text intent”区分开。

### 今日证据

- `chain_matrix.json`
- `comparison.json`
- `multistep_attempt.json`
- `planner_records.jsonl`
- `tool_execution_records.jsonl`
- `tme_reduced_execution_audit.json`
- `tme_reduced_execution_audit.md`
- `deepseek_structured_output_audit.json`

### 当前风险

- `tme_reduced_execution_audit.md` 里 `real-preflight ready` 仍然是 `False`，说明 reviewed TME 复合链还不是一条完全自然闭环的 native multi-step chain。
- `chain_macenko_to_detection` 目前仍是 `unknown`，它更像“局部证据已改善”，还不是“端到端已稳定闭环”。
- `general` intent 现在已经不再被错误标成 `_parse_error`，但它仍然是 free-text contract，而不是 strict JSON contract。
- 当前最强证据仍然是“缩减后的可控验证路径”，不是 PathoFlow 当前 planner 自己在开放场景下稳定串出的完整病理工作流。

### 明日建议

- 优先把 reduced TME child chain 从“受控验证链”继续推进到 `real-preflight ready = True` 的更完整 native chain。
- 把 `planner 改善` 和 `真实多步执行闭环` 继续分开表述，避免 README 或对外结论过度前置。
- 保持 DeepSeek task-planning JSON 修复的回归测试，并继续扩展更多病理任务 probe，而不是只盯住单个 TME query。
