# PathoFlow Native Framework Issue List

This note focuses on problems in the original PathoFlow framework itself.
It intentionally excludes temporary compatibility shims that were only added
to validate external provider protocol behavior.

## Scope

- Included:
  - offline planner behavior
  - reviewed flow registry coverage
  - tool execution outputs
  - multi-step chaining / artifact handoff
  - output contract reliability
- Excluded:
  - third-party relay quirks beyond protocol compatibility
  - temporary `openai-compat-gpt-5.4` adapter details as product design

## Priority Order

1. Planner drift
2. Success-without-output execution gaps
3. Artifact contract mismatch between upstream/downstream tools
4. Registry coverage mismatch vs executable tools
5. LLM JSON contract instability

## Issue 1: Planner Drift

Severity: Critical

Evidence:
- [README.md](./README.md)
- [planner_records.jsonl](./planner_records.jsonl)
- [workflow_contrast_report.md](./workflow_contrast_report.md)

Observed behavior:
- `OfflineFlowPlanner` routes representative lung QC / TME / IHC queries to
  `wish_14_intrahepatic_cholangiocarcinoma_cancer_detection`.

Why this matters:
- The framework chooses the wrong disease/task family before execution even
  begins, so downstream tool success cannot rescue the workflow.

Recommended fix:
- Add hard disease/task constraints before ranking.
- Penalize cross-disease flows strongly.
- Separate QC / TME / IHC routing from generic cancer-detection scoring.

## Issue 2: Success With No Output Files

Severity: Critical

Evidence:
- [tool_execution_records.jsonl](./tool_execution_records.jsonl)
- [chain_matrix.json](./chain_matrix.json)
- [sequential_chains.json](./sequential_chains.json)

Observed behavior:
- `59-generate-overlays` returns `success=true` and `completed_no_output`.
- `52-Global-Macenko` returns `success=true` and `completed_no_output`.

Why this matters:
- The framework reports a nominally successful step while producing no usable
  artifact, so multi-step chains falsely look healthy.

Recommended fix:
- Treat zero-output result manifests as execution failures unless explicitly
  allowed by the tool contract.
- Backfill missing demo assets or generate minimal placeholder artifacts.

## Issue 3: Artifact Contract Mismatch

Severity: High

Evidence:
- [chain_matrix.json](./chain_matrix.json)

Observed behavior:
- Detection output mask is PNG-like, while overlay preflight requires
  `input_mask` to be `.tif/.tiff`.

Why this matters:
- Individually executable tools cannot be composed because the framework's
  contracts disagree on artifact format.

Recommended fix:
- Normalize mask artifact contracts across tools, or insert explicit format
  bridge steps recognized by the planner and preflight layer.

## Issue 4: Registry Coverage Mismatch

Severity: High

Evidence:
- [README.md](./README.md)
- `PathoFlow` reviewed flow registry inspection during benchmark runs

Observed behavior:
- Some executable tools, such as
  `4-nucleus-segmentation-hovernet-pannuke`, are not represented in the
  reviewed flow registry.

Why this matters:
- The planner and preparer cannot reason over all practically executable
  tools, so the planning layer and execution layer diverge.

Recommended fix:
- Add missing executable tools to reviewed flow registry YAML with IO schema,
  risk metadata, and adapter declarations.

## Issue 5: LLM Output Contract Instability

Severity: Medium

Evidence:
- [openai_compat_ask_result.json](./openai_compat_ask_result.json)
- [gpt54_responses_ask_result.json](./gpt54_responses_ask_result.json)

Observed behavior:
- After protocol compatibility is solved, live asks return useful text but not
  strict JSON; `PathoFlow` falls back to `_parse_error` and stores the answer
  in `reasoning`.

Why this matters:
- Structured UI panels and downstream automated evaluation remain unstable even
  when the model call succeeds.

Recommended fix:
- Tighten prompt contract wording.
- Harden JSON repair / extraction.
- Consider schema-aware response validation with retry.

## Bottom Line

The native PathoFlow framework's main problems are not protocol-level anymore.
The dominant blockers are planner drift, false-success zero-output tools, and
missing composability contracts between steps. Fixing those should come before
further provider or model experimentation.
