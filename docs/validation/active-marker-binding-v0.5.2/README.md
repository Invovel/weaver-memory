# Active Marker Binding v0.5.2

## Purpose

This validation bridges the v0.5 Runbook Marker trace fixture and the v0.5.3
ContextCapsule / TagTimeIndex substrate.

It answers a narrow question:

```text
Can a manually seeded HarnessMarker bind to compact RAW-context capsules and
recover supporting raw spans before runtime intervention is enabled?
```

It does not prove end-to-end task success, automatic marker emergence, or real
tool-loop step reduction.

## Boundary

The validation uses `binding_mode = active_preview`.

That means the marker actively resolves a `MarkerEvidenceContext` and binds
candidate capsules, but it still has no runtime authority:

```text
runtime_authority = false
applied_to_runtime = false
actual_route = thinking
actual_suppressed_actions = []
online_llm_call_count = 0
layer3_mutation_count = 0
memory_promotion_count = 0
```

So this stage proves evidence binding, not active execution.

## Inputs

```text
docs/validation/runbook-marker-v0.5/dialogue_cards.jsonl
docs/validation/runbook-marker-v0.5/markers.json
docs/validation/context-capsule-v0.5.3/raw_spans_fixture.jsonl
```

The benchmark uses the five golden marker cards:

```text
Codex subscription failed
npm install dependency conflict
Docker build warning partial signal
CI timeout freshness conflict
API key exists but request rejected
```

## Command

```powershell
python .\benchmarks\active_marker_binding_validation.py `
  --output-dir .\docs\validation\active-marker-binding-v0.5.2
```

## Results

```json
{
  "marker_count": 5,
  "active_preview_generated_count": 5,
  "marker_context_bound_count": 5,
  "marker_context_hit_rate": 1.0,
  "required_evidence_total": 15,
  "required_evidence_covered": 15,
  "required_evidence_coverage": 1.0,
  "raw_recovery_rate": 1.0,
  "runtime_mutation_count": 0,
  "layer3_mutation_count": 0,
  "memory_promotion_count": 0,
  "online_llm_call_count": 0
}
```

Generated artifacts:

```text
raw_results.json
metrics_summary.json
binding_traces.jsonl
```

## Conclusion

v0.5.2 validates the marker-to-context binding step: a Runbook Marker can
resolve compact capsule evidence and recover raw spans without calling an LLM,
mutating runtime behavior, promoting memory, or changing Layer 3 lifecycle.

The next stage can decide whether selected low-risk marker recommendations move
from `active_preview` to controlled runtime action.
