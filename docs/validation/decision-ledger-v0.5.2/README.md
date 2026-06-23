# Decision Ledger v0.5.2

## Purpose

This validation adds the audit substrate required before expanding marker
runtime authority further.

It records every route-plan decision as a hash-chained ledger row:

```text
marker decision
  -> policy version
  -> approval id, if any
  -> conflict refs, if any
  -> capsule refs
  -> raw refs
  -> zero side-effect counters
  -> sha256 record hash
```

## Command

```powershell
python .\benchmarks\decision_ledger_validation.py `
  --output-dir .\docs\validation\decision-ledger-v0.5.2
```

## Expected Gates

```json
{
  "decision_count": 5,
  "hash_chain_valid": true,
  "applied_plan_count": 2,
  "blocked_or_pending_count": 3,
  "approved_l2_decision_count": 1,
  "approved_l2_with_approval_id_count": 1,
  "blocked_with_reason_count": 3,
  "conflict_ref_count": 1,
  "raw_ref_attached_count": 5,
  "capsule_ref_attached_count": 5,
  "side_effect_total": 0
}
```

Generated artifacts:

```text
raw_results.json
metrics_summary.json
decisions.jsonl
```

## Conclusion

v0.5.2 now has a minimal approval / decision ledger. It does not grant new
runtime authority. It makes existing L1/L2 route-plan decisions auditable before
any later L3 guard or action-level authority is attempted.
