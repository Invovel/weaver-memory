# Real Trajectory Experiment v0.6

This is MemoryWeaver's first task-effect bridge after the v0.5 trace advantage
work.

It is **not yet a live agent benchmark**. The experiment replays the 50 curated
10-20 turn dialogue cards as semi-real task trajectories and compares three
arms:

```text
A. no_memory
   The agent has no prior memory and typically tries known bad actions before
   reaching the relevant evidence.

B. rag_over_logs
   The agent retrieves related logs, but relevance retrieval may still surface
   unsafe or misleading paths before the key evidence.

C. memoryweaver_runtime_marker
   The agent activates the expected Runbook Marker, checks required evidence
   first, and avoids known bad actions.
```

## Results

```json
{
  "trajectory_mode": "semi_real_dialogue_card_replay",
  "task_count": 50,
  "trajectory_count": 150,
  "arm_count": 3,
  "mw_steps_to_success_delta_vs_no_memory": 3,
  "mw_steps_to_success_delta_vs_rag": 1,
  "mw_known_bad_action_reduction_vs_no_memory": 55,
  "mw_known_bad_action_reduction_vs_rag": 50,
  "mw_tool_call_reduction_vs_no_memory": 3,
  "mw_user_correction_reduction_vs_no_memory": 50,
  "mw_required_evidence_first_hit_rate": 1.0,
  "rag_required_evidence_first_hit_rate": 0.0,
  "no_memory_required_evidence_first_hit_rate": 0.0,
  "mw_marker_activation_accuracy": 1.0,
  "runtime_authority_violation_count": 0,
  "online_llm_call_count": 0
}
```

## Arm Summary

See `arms.jsonl` for exact values. At a high level:

```text
no_memory                  -> longest path, most known-bad attempts, user correction expected
rag_over_logs              -> shorter than no_memory, but still tries one known-bad action
memoryweaver_runtime_marker -> shortest path, required evidence first, zero known-bad attempts
```

## Interpretation

v0.6 shifts the question from:

```text
Can MemoryWeaver produce a correct marker trace?
```

to:

```text
Does the marker trace correspond to fewer bad actions and faster evidence
access in a replayed task trajectory?
```

The answer is yes for this semi-real replay fixture. MemoryWeaver reduces
steps-to-success, known-bad action attempts, tool calls, and user corrections
relative to `no_memory`, and also reduces steps and known-bad action attempts
relative to `rag_over_logs`.

## Non-Claims

This validation does not prove:

- live agent task success improvement
- production runtime behavior
- generalization to external task benchmarks
- dense/hybrid retrieval superiority
- automatic Layer-3 Pattern improvement

It is a bridge between v0.5 manual counterfactual trace advantage and the later
live harness experiment. No online LLM calls, runtime-authority violations,
memory promotion, or Layer-3 mutation occur.

## Next Step

The next validation should replace replayed trajectories with actual harness
runs:

```text
no_memory vs rag_over_logs vs memoryweaver_runtime_marker
metrics: steps_to_success, bad_action_attempts, tool_calls, user_corrections,
         repeated_errors, required_evidence_first_hit
```
