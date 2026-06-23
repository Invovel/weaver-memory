# Controlled Active Guard v0.5.2

## Purpose

This validation tests the first controlled runtime action boundary for
Runbook Markers.

It upgrades only one low-risk marker class from `active_preview` to a controlled
runtime plan mutation:

```text
L1_hint + full capsule evidence + raw refs
  -> actual route hint
  -> actual required-evidence plan
```

It does not allow tool execution, real action suppression, Layer-3 mutation,
memory promotion, or online LLM calls.

## Policy

```text
policy = controlled-active-guard-policy-v1
allowed_active_levels = ["L1_hint"]
requires_full_evidence_coverage = true
allows_route_hint = true
allows_required_evidence_plan = true
allows_tool_execution = false
allows_actual_suppression = false
allows_memory_promotion = false
allows_layer3_mutation = false
blocks_unresolved_conflicts = true
```

High-risk markers remain preview-only:

```text
L2_route -> blocked
L3_guard -> blocked
```

## Command

```powershell
python .\benchmarks\controlled_active_guard_validation.py `
  --output-dir .\docs\validation\controlled-active-guard-v0.5.2
```

## Results

```json
{
  "marker_count": 5,
  "active_guard_applied_count": 1,
  "preview_only_count": 4,
  "high_risk_blocked_count": 4,
  "active_guard_application_rate": 0.2,
  "tool_execution_count": 0,
  "actual_suppression_count": 0,
  "memory_promotion_count": 0,
  "layer3_mutation_count": 0,
  "online_llm_call_count": 0,
  "conflict_logged_count": 1,
  "conflict_blocked_count": 1,
  "required_evidence_plan_applied_count": 1,
  "route_hint_applied_count": 1
}
```

Generated artifacts:

```text
raw_results.json
metrics_summary.json
guard_traces.jsonl
```

## Conclusion

v0.5.2 now demonstrates a narrow active runtime boundary: one L1 hint can
change the runtime plan by adding a route hint and required evidence checks,
while L2/L3 markers remain blocked from active behavior.

It also records unresolved marker conflicts and blocks conflicted markers from
active behavior. In this fixture, the npm dependency card has an unresolved
`suppress_vs_suggest` conflict on `delete_lockfile`, so it remains
preview-only.

This is still not task-level success evidence. It only proves that controlled
runtime plan mutation can happen without crossing the trust boundary.
