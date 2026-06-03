# Task-Level Experiment Plan

## Purpose

SDK v0.2.0 proves that the trust boundary holds. The next experiment must test
whether MemoryWeaver improves real task execution.

Main question:

```text
Does MemoryWeaver v0.2.0 reduce repeated trial-and-error compared with
No Memory and RAG over logs?
```

## Arms

| Arm | Description |
| --- | --- |
| No memory | Agent receives only the current task and current project context. |
| RAG over logs | Agent retrieves prior raw logs or summaries, but no MemoryPolicy, Pattern lifecycle, or provenance gate. |
| MemoryWeaver v0.2.0 | Agent uses Layer 1/2 memory, EvidenceLink, provisional Pattern recall, and policy-gated routing. |

## Datasets

Start with 20-50 repeated project tasks before expanding:

- coding/debugging tasks
- CLI configuration failures
- dependency and environment errors
- repeated user preference or style corrections
- documentation or setup tasks with known wrong paths

## Data Files

```text
task_runs.jsonl
evaluation_metrics.json
case_studies.md
raw_events.jsonl
memory_items.jsonl
pattern_items.jsonl
evidence_links.jsonl
```

## Metrics

| Metric | Meaning |
| --- | --- |
| steps_to_success | Number of agent/tool/action steps before task completion. |
| repeated_error_count | Count of repeated failed paths already observed in prior runs. |
| path_reuse_rate | Fraction of useful previous paths reused correctly. |
| tool_error_rate | Failed tool calls divided by total tool calls. |
| memory_activation_accuracy | Whether retrieved memory/Pattern was relevant and safe. |
| user_correction_count | Number of user corrections needed after agent action. |
| time_to_success | Wall-clock time, secondary to step count. |

## Analysis

Report the task-level experiment separately from trust-boundary validation:

- Trust-boundary validation checks whether gates hold.
- Task-level validation checks whether memory improves outcomes.

The first publishable comparison should focus on repeated-error reduction and
steps-to-success, not on production-scale storage.
