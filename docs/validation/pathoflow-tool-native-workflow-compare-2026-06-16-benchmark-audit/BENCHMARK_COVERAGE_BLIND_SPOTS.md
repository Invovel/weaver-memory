# Benchmark Coverage Blind Spots

## Scope

This note audits what the current benchmark package still does **not** cover,
even after the benchmark false-failure / stale-report fixes.

Primary sources:

- `pathoflow-tool-native-workflow-compare-2026-06-16/workflow_contrast_report.json`
- `pathoflow-tool-native-workflow-compare-2026-06-16/planner_records.jsonl`
- `pathoflow-tool-native-workflow-compare-2026-06-16/tme_reduced_execution_audit.json`
- current benchmark scripts in `benchmarks/pathoflow_tool_native_workflow_compare.py`

## Main Finding

The current benchmark package is now cleaner, but it is still **coverage-thin**:

- it validates a few execution fragments well
- it validates planner routing for representative queries
- it validates one reduced TME chain with a patched executor audit
- it still does **not** exercise several high-frequency theoretical chains end to end

So the main remaining risk is no longer benchmark false failures in covered cases.
The main risk is **coverage blind spots**.

## Coverage Levels

### `execution_fragment_only`

These have some real/demo/cpu-pseudo execution evidence, but only as isolated fragments:

- `52-Global-Macenko -> 5-pancreas-tumor-detection`
  Offline edge count: `20`
  Note: validated as a fragment, not as part of a broader QC / metadata / downstream clinical chain.

- `1-foreground-segmentation -> 59-generate-overlays`
  Not a dominant offline edge by itself, but covered as a benchmark fragment.

- `4-nucleus-segmentation-hovernet-pannuke -> 59-generate-overlays`
  Covered only as a fragment.

- `5-pancreas-tumor-detection -> 59-generate-overlays`
  Covered only as a fragment.

### `planner_only`

These are represented in routing / selection logic, but not benchmarked through a real or demo execution chain:

- `29-Summarize-slide-info -> 40-GrandQC`
  Offline edge count: `1850`
  Blind spot: the benchmark proves planner preference for QC, but does not execute `29` or `40`.

- `40-GrandQC -> 1-foreground-segmentation`
  Offline edge count: `742`
  Blind spot: the benchmark executes `1`, but not the upstream `40`.

- `40-GrandQC -> 48-foreground-segmentation-beta -> 41-Deepliif`
  Offline chain count: `260`
  Blind spot: planner preference for IHC is covered, but the practical IHC chain is not benchmarked end to end.

- `40-GrandQC -> 61-hooknet-tls`
  Offline chain count: `76`
  Blind spot: planner semantics exist, but no execution evidence for TLS chain.

- `40-GrandQC -> 49-slide-embedding-all-methods`
  Offline edge count: `40`
  Blind spot: no embedding execution evidence in this benchmark.

### `patched_execution_only`

These have stronger orchestration evidence than planner-only cases, but the execution proof is still not “native real model execution”:

- `1-foreground-segmentation -> 53-hover-next-mp -> 77-Pathomics-pipeline-from-slides-nucleus`
  Offline dominant chain context:
  `29 -> 40 -> 1 -> 53 -> 77` count `700`
  Also `29 -> 40 -> 53 -> 77` count `200`

  Current evidence:
  - active preparer: yes
  - run_preparer: yes
  - executable_flow expansion: yes
  - API mock execute: yes
  - API execute-real: yes

  Blind spot:
  - the TME audit’s `execute-real` path is backed by a patched fake `wish_executor.execute_tool`
  - this proves multi-step orchestration and manifest handoff, but not actual native model execution for all steps

### `not_covered`

These show up in theoretical/high-frequency workflow evidence but have no meaningful execution benchmark in the current package:

- `29 -> 40 -> 3-tissue-segmentation -> 53 -> 77`
  Offline chain count: `110`
  Blind spot: `3-tissue-segmentation` is uncovered.

- `29 -> 40 -> 1 -> 53 -> 77 -> 67-GigaTIME`
  Offline chain count: `40`
  Blind spot: `67-GigaTIME` uncovered.

- `29 -> 40 -> 67-GigaTIME`
  Offline chain count: `30`
  Blind spot: direct GigaTIME path uncovered.

- `29 -> 40 -> 49-slide-embedding-all-methods -> 73-Infer-MIL-pipeline-for-slides`
  Offline chain count: `20`
  Blind spot: embedding + MIL inference uncovered.

- `54-kfb2svs -> 29-Summarize-slide-info`
  Offline chain count: `20`
  Blind spot: format conversion entry path uncovered.

- `31-Summarize-asap-xml-info -> 32-Transfer-asap-xml-to-tif`
  Offline edge count: `30`
  Blind spot: XML annotation utility chain uncovered.

- `32-Transfer-asap-xml-to-tif -> 34-Generate-classification-patches`
  Offline edge count: `20`
  Blind spot: downstream patch generation chain uncovered.

- `68-Train-segmentation-pipeline-from-slides-xml -> 70-Infer-segmentation-pipeline`
  Offline edge count: `20`
  Blind spot: train/infer segmentation path uncovered.

- `72-Train-MIL-pipeline-from-h5 -> 74-Infer-MIL-pipeline-for-h5`
  Offline edge count: `20`
  Blind spot: H5 MIL inference path uncovered in this benchmark, even though `74` has separate allowlist support in runtime code.

- `30-Get-slide-previews`
  Offline single-tool chain count: `20`
  Blind spot: no benchmark execution probe for previews.

## Highest-Priority Blind Spots

If we only add a few new benchmark families, these are the best next targets:

1. `29 -> 40 -> 1 -> 53 -> 77`
   Why: this is the dominant theoretical workflow family and still lacks native full-chain execution evidence.

2. `29 -> 40 -> 48 -> 41`
   Why: the IHC quantification family is the second major practical chain and currently has planner-only evidence.

3. `29 -> 40`
   Why: `29` and `40` are the most central upstream utility/QC pair in the theoretical graph, but neither is actually executed by this benchmark.

4. `29 -> 40 -> 3 -> 53 -> 77`
   Why: tissue-segmentation branch is a frequent variation of the dominant nucleus/pathomics workflow.

5. `29 -> 40 -> 49 -> 73`
   Why: embedding + MIL branch appears in the theoretical workflow but has zero execution coverage here.

## Practical Interpretation

Current benchmark confidence is strongest for:

- isolated demo / cpu-pseudo execution fragments
- overlay handoff contract fragments
- planner routing for QC / TME / IHC representative prompts
- reduced TME orchestration under patched execution audit

Current benchmark confidence is weak for:

- metadata/QC driven upstream chains
- IHC real execution chain
- tissue-segmentation branch
- MIL / embedding branch
- annotation/format-conversion utility chains
- native unpatched multi-step TME execution

## Bottom Line

The benchmark package is no longer mainly suffering from noisy false failures in
the covered cases.

The bigger remaining risk is that several **important workflow families are
still effectively unmeasured**.
