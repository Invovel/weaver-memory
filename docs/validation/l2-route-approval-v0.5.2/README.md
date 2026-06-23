# L2 Route Approval v0.5.2

## Purpose

This validation tests the next runtime boundary after controlled L1 hints:
approval-gated `L2_route` activation.

It answers:

```text
Can MemoryWeaver allow an L2 route marker to write route/evidence plan only
when an explicit approval record exists?
```

## Policy

```text
policy = l2-route-approval-policy-v1
L1_hint = allowed with full evidence
L2_route = requires explicit approval
L3_guard = blocked

allowed effects:
  route_hint
  required_evidence_plan

denied effects:
  tool_execution
  actual_suppression
  memory_promotion
  layer3_mutation
  online_llm_call
```

Unresolved marker conflicts still block active behavior.

## Approval Fixture

The fixture contains one approval:

```text
do_not_treat_key_existence_as_positive_auth
```

The CI timeout L2 marker intentionally has no approval, so it remains pending.

## Command

```powershell
python .\benchmarks\l2_route_approval_validation.py `
  --output-dir .\docs\validation\l2-route-approval-v0.5.2
```

## Results

```json
{
  "marker_count": 5,
  "l1_active_count": 1,
  "l2_marker_count": 2,
  "l2_approved_count": 1,
  "l2_pending_count": 1,
  "l2_applied_count": 1,
  "l3_blocked_count": 2,
  "conflict_blocked_count": 1,
  "route_plan_applied_count": 2,
  "required_evidence_plan_applied_count": 2,
  "tool_execution_count": 0,
  "actual_suppression_count": 0,
  "memory_promotion_count": 0,
  "layer3_mutation_count": 0,
  "online_llm_call_count": 0
}
```

Generated artifacts:

```text
route_approvals.jsonl
raw_results.json
metrics_summary.json
route_traces.jsonl
```

## Conclusion

v0.5.2 can now distinguish three runtime marker states:

```text
L1_hint    -> controlled active route/evidence plan
L2_route   -> active only with explicit approval
L3_guard   -> preview-only / blocked
```

This is still not task success evidence. It proves the approval gate for route
planning, not autonomous execution.
