# Controlled Harness Run v0.6.1

This validation moves one step beyond v0.6 semi-real replay.

v0.6 replay wrote comparable task trajectories. v0.6.1 adds a deterministic
harness policy loop and a hash-chained decision record for every task/arm pair.

It compares:

```text
A. no_memory
B. rag_over_logs
C. memoryweaver_runtime_marker
```

## Boundary

This is still a controlled local harness simulation. It does not execute real
tools and does not call an LLM.

Allowed marker effects:

```text
route_hint
required_evidence_plan
known_bad_warning
```

Disallowed side effects:

```text
tool_execution
actual_suppression
memory_promotion
Layer-3 mutation
online LLM call
```

## Results

```json
{
  "task_count": 50,
  "task_run_count": 150,
  "decision_count": 150,
  "hash_chain_valid": true,
  "mw_steps_to_success_delta_vs_no_memory": 3,
  "mw_steps_to_success_delta_vs_rag": 1,
  "mw_known_bad_action_reduction_vs_no_memory": 55,
  "mw_known_bad_action_reduction_vs_rag": 50,
  "mw_required_evidence_first_hit_rate": 1.0,
  "mw_known_bad_warning_count": 55,
  "runtime_authority_violation_count": 0,
  "tool_execution_count": 0,
  "memory_promotion_count": 0,
  "layer3_mutation_count": 0,
  "online_llm_call_count": 0
}
```

## Interpretation

The controlled harness policy loop preserves the v0.6 task-effect result while
adding auditability:

```text
no_memory                  -> no policy memory, bad paths attempted
rag_over_logs              -> relevant logs retrieved, one bad path still attempted
memoryweaver_runtime_marker -> marker decision, evidence-first plan, bad paths warned before attempt
```

MemoryWeaver reduces steps-to-success and known-bad action attempts relative to
both baselines. The run also records 150 hash-chained decisions, one for every
task/arm pair.

## Non-Claims

This validation does not prove live tool execution or real autonomous agent
success. It is the bridge from replayed trajectories to a future live harness.

No tool execution, actual action suppression, memory promotion, Layer-3
mutation, online LLM call, or runtime-authority violation occurs.

## Artifacts

```text
raw_results.json
metrics_summary.json
arms.jsonl
task_runs.jsonl
decisions.jsonl
```
