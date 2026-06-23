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

### v0.5 Runbook Marker Dialogue Set

Before the full task-level benchmark, v0.5 should use a trace-first dialogue
fixture:

```text
docs/validation/v0.5-runbook-marker-dialogue-set.md
```

This fixture contains 50 multi-turn dialogue cards. Each card represents one
10-20 turn conversation with exploration, failed paths, user correction,
evidence checks, expected CoreIssueNode, expected HarnessMarker, and expected
`fast_verify` trace behavior.

This is not yet an end-to-end task success benchmark. It is the bridge test for
the minimal runtime loop:

```text
query
-> CoreIssueNode match
-> HarnessMarker activation
-> known bad path warning
-> required evidence checks
-> route = fast_verify
```

Use it to prove that reviewed experience can influence runtime trace behavior
without changing Layer 3 lifecycle rules or calling an LLM online.

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

For the v0.5 dialogue trace fixture, add:

| Metric | Meaning |
| --- | --- |
| marker_trigger_precision | Whether the expected HarnessMarker fired. |
| core_issue_match_accuracy | Whether the query matched the expected CoreIssueNode. |
| known_bad_path_suppression | Whether previously failed actions were warned or suppressed. |
| evidence_check_order_accuracy | Whether required evidence checks appeared in the expected order. |
| trace_completeness | Whether trace includes node, marker, reason, evidence, suppressed path, and route. |

## Analysis

Report the task-level experiment separately from trust-boundary validation:

- Trust-boundary validation checks whether gates hold.
- Task-level validation checks whether memory improves outcomes.

The first publishable comparison should focus on repeated-error reduction and
steps-to-success, not on production-scale storage.
