# Benchmark Setup And Risks

## What This Benchmark Suite Is

The current PathoFlow validation bundle is not one single benchmark. It is a
small stack of scripts with different purposes:

1. `benchmarks/pathoflow_tool_native_workflow_compare.py`
   Purpose:
   - benchmark the current **no-LLM** PathoFlow tool-native route
   - compare it against the older offline replay package
   - produce execution fragments, planner traces, chain matrix, sequential chains,
     executable graph, and a summary README

2. `benchmarks/pathoflow_workflow_contrast_report.py`
   Purpose:
   - compare the **theoretical workflow graph** recovered from offline replay
     against the **actually executable workflow graph**
   - summarize breakpoints detected from benchmark artifacts

3. `benchmarks/pathoflow_tme_reduced_execution_audit.py`
   Purpose:
   - audit one specific reduced TME chain
   - test planner, active preparer, run_preparer, executable_flow,
     API prepare/preflight/mock execute, and API execute-real route

4. `benchmarks/pathoflow_env_override_probe.py`
   Purpose:
   - check live LLM backend routing and `.env` override effects
   - useful for provider/structured-output verification, but not part of no-LLM execution coverage

## Core Benchmark Settings

### 1. No-LLM tool-native compare

Source:
- `benchmarks/pathoflow_tool_native_workflow_compare.py`

Key settings:
- PathoFlow root default: `D:\\Download\\PathoFlow`
- previous offline package default:
  `docs/validation/pathoflow-core-dataset-offline-eval-2026-06-14`
- output directory pattern:
  `docs/validation/pathoflow-tool-native-workflow-compare-YYYY-MM-DD`
- existing same-day output directory is deleted and recreated

What it actually exercises:
- planner probes:
  - QC lung
  - TME lung
  - IHC lung
- direct execution probes:
  - `5-pancreas-tumor-detection` in `cpu_pseudo`
  - `1-foreground-segmentation` in `demo`
  - `59-generate-overlays` in `demo`
  - `4-nucleus-segmentation-hovernet-pannuke` in `demo`
  - `52-Global-Macenko` in `demo`
  - `6-breast-tumor-detection` in `cpu_pseudo`
- manual chain matrix probes:
  - foreground -> overlay
  - nucleus -> overlay
  - detection -> overlay
  - macenko -> detection
- sequential chain execution probes:
  - foreground -> overlay
  - nucleus -> overlay
  - detection -> overlay
  - macenko -> detection
- reduced TME audit:
  - imports `run_tme_reduced_execution_audit(...)`

Important implication:
- this benchmark covers only a **small execution subset**
- it is strong for fragment checks
- it is weak for broad workflow-family coverage

### 2. Contrast report

Source:
- `benchmarks/pathoflow_workflow_contrast_report.py`

Inputs:
- `workflow_graph.json` from offline replay
- `executable_workflow_graph.json` from tool-native compare
- `comparison.json`
- `chain_matrix.json`
- `sequential_chains.json`

Output:
- `workflow_contrast_report.json`
- `workflow_contrast_report.md`

Current behavior:
- breakpoint summary is derived from:
  - preflight contract mismatch
  - completed with zero output
  - empty upstream output
  - sequential chain failure
- interpretation section is now dynamic rather than hard-coded to stale old failures

### 3. TME reduced execution audit

Source:
- `benchmarks/pathoflow_tme_reduced_execution_audit.py`

What it covers:
- planner primary flow selection
- active preparer
- run_preparer
- executable_flow expansion
- API `/api/flow/prepare`
- API `/api/flow/real-preflight`
- API `/api/flow/execute`
- API `/api/flow/execute-real`

Very important setting:
- the audit patches `wish_executor.execute_tool`
- so `execute-real` in this audit validates **multi-step orchestration and manifest handoff**
- it does **not** prove native real model execution for all steps

## Confirmed Benchmark Problems Already Found

### A. Sequential overlay false failures

Old symptom:
- `tool_executor_foreground_overlay` and `tool_executor_nucleus_overlay`
  showed `success_count=1, failure_count=1`

Root cause:
- benchmark sequential chain used an empty fake `.svs` stub for overlay input
- that path construction was brittle

Fix:
- benchmark now reuses the original source slide path for overlay when available

Status:
- fixed in benchmark code

### B. `chain_macenko_to_detection` was under-reported as `unknown`

Old symptom:
- `chain_matrix.json` marked this branch as `unknown`

Root cause:
- the benchmark only distinguished:
  - `blocked_by_empty_upstream_output`
  - otherwise `unknown`
- it did not reflect already-available success evidence from the compare package

Fix:
- benchmark now marks it `completed` when both upstream Macenko and downstream detection have nonzero manifest outputs

Status:
- fixed in benchmark code

### C. Contrast report stale narrative

Old symptom:
- report still described already-fixed overlay / normalization / planner issues as current major breakpoints

Root cause:
- interpretation text was static

Fix:
- interpretation is now generated from current breakpoint counts

Status:
- fixed in benchmark code

## Still-Present Potential Risks / Caveats

These are the most important remaining benchmark caveats.

### 1. Detection -> overlay may still be a false positive

This is the biggest current benchmark caveat.

Why:
- `first_output_path(...)` returns the first output file matching suffix preference
- for `5-pancreas-tumor-detection`, output files are:
  - `detection_result.png`
  - `tumor_mask.png`
  - `report.json`
- the current detection -> overlay benchmark uses suffix preference:
  - `(".png", ".tif", ".tiff")`
- so the selected artifact can become `detection_result.png` instead of `tumor_mask.png`

Implication:
- the benchmark can report a successful `detection -> overlay` chain
- while actually feeding a rendered result image into `input_mask`
- that means this path may still be a **benchmark false positive**

Confidence:
- high risk
- not yet fixed in the benchmark code during this run

### 2. Planner coverage is stronger than execution coverage

Several workflow families are planner-tested but not execution-tested:

- `29 -> 40`
- `29 -> 40 -> 48 -> 41`
- `29 -> 40 -> 61`
- `29 -> 40 -> 49`

Implication:
- benchmark can overstate readiness if one reads planner correctness as execution readiness

### 3. TME execute-real evidence is patched, not native

The reduced TME audit is still valuable, but:
- it proves orchestration
- it proves handoff contract logic
- it does not fully prove native runtime behavior of all involved tools

Implication:
- `execute_real_status = real_completed` in the audit is not equivalent to full native production execution proof

### 4. Coverage bias toward demo / cpu-pseudo fragments

The executable graph is built mostly from:
- `demo`
- `cpu_pseudo`

Implication:
- benchmark is better at proving artifact/contract behavior than true model/runtime behavior

### 5. Utility-chain blind spots remain large

Uncovered or nearly uncovered families still include:
- `54 -> 29`
- `31 -> 32`
- `32 -> 34`
- `68 -> 70`
- `72 -> 74`
- `30` single-tool preview route

Implication:
- benchmark says little about annotation conversion, patch generation, training/inference bridge, or H5 MIL path

### 6. Real-preflight in TME audit intentionally uses degraded roots

In the TME audit:
- `wish_root` and `pinglib_root` are intentionally set to `/tmp`

Implication:
- `real_preflight_ready = false` there is not a product regression by itself
- it is partly an audit setting artifact

## Coverage Blind Spots

The most important remaining blind spots are documented separately:

- `BENCHMARK_COVERAGE_BLIND_SPOTS.md`

Priority families to add next:

1. `29 -> 40 -> 1 -> 53 -> 77`
2. `29 -> 40 -> 48 -> 41`
3. `29 -> 40`
4. `29 -> 40 -> 3 -> 53 -> 77`
5. `29 -> 40 -> 49 -> 73`

## Bottom Line

This benchmark suite is now much cleaner than before, but it still needs to be
read as:

- good at proving a few execution fragments
- good at exposing some contract problems
- good at validating representative planner routing
- not yet sufficient to claim broad workflow-family execution coverage

And one current benchmark path, `detection -> overlay`, still looks suspicious
enough that it should not be treated as strong positive evidence until the
artifact selection is tightened from `detection_result.png` to the actual mask output.
