# Runbook Marker v0.5 Trace Advantage Validation

This directory contains the machine-readable seed fixture derived from `../v0.5-runbook-marker-dialogue-set.md`.

## Files

- `dialogue_cards.jsonl`: 50 dialogue cards, one card per 10-20 turn conversation.
- `core_issues.json`: manually annotated CoreIssueNode seed records.
- `markers.json`: manually annotated HarnessMarker seed records.
- `raw_results.json`: latest trace-fixture benchmark output.
- `metrics_summary.json`: compact metrics for reporting.
- `trace_samples.jsonl`: one generated trace record per dialogue card.
- `counterfactual_notes.jsonl`: manual counterfactual annotations used by traces.
- `conflict_candidates.jsonl`: marker conflict candidates logged in shadow mode.
- `trace_advantage.jsonl`: per-card counterfactual advantage records.
- `card_taxonomy.md`: card tiers and type taxonomy.
- `notes.md`: annotation notes and design decisions.

Purpose: validate counterfactual trace advantage for the v0.5 `mw trace`
minimal demo.

Boundary: this is not an official external benchmark and not an end-to-end task
success score. v0.5 measures manually annotated counterfactual trace advantage,
not real task execution improvement.

Expected trace contract:

```text
query -> CoreIssueNode -> HarnessMarker
  -> [SHADOW] recommendation: required evidence / suppressed actions / fast_verify
  -> actual runtime: thinking
```

v0.5 markers are recommendations only. They can detect what should happen, but
they cannot change runtime behavior yet.

Each trace now has two tracks:

```text
baseline_no_marker
memoryweaver_marker_shadow
```

The `advantage` field compares these tracks and estimates:

- counterfactual step reduction
- known bad action reduction
- evidence order improvement
- user correction avoidance
- confidence and confidence basis
- source-gate vs guard-marker vs evidence-marker attribution

Run:

```powershell
python .\benchmarks\runbook_marker_trace_fixture.py --output-dir .\docs\validation\runbook-marker-v0.5
```

or through the unified adapter:

```powershell
python .\benchmarks\memevobench_adapter.py `
  --fixture runbook-dialogue `
  --output-dir .\docs\validation\runbook-marker-v0.5
```

Key metrics:

```text
shadow_mode_labeled_rate = 1.0
actual_runtime_unchanged_rate = 1.0
safety_violation_count = 0
counterfactual_present_rate = 1.0
counterfactual_step_reduction > 0
known_bad_action_reduction > 0
evidence_order_improvement > 0
```

Interpretation:

```text
Source gate prevents pollution.
Marker guides behavior.
v0.5 estimates their counterfactual advantage.
v0.6 must replace these estimates with real agent trajectories.
```
