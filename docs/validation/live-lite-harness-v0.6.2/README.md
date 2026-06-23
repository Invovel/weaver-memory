# Live-Lite Harness v0.6.2

v0.6.2 is the first MemoryWeaver trajectory validation that executes tools,
but the tools are deterministic in-memory mocks.

The mock runtime returns:

```text
known-bad action      -> failed_known_bad
generic debugging     -> no_signal
required evidence     -> evidence_observed
```

No shell command, network call, real tool, LLM provider, memory promotion, or
Layer-3 mutation is performed.

## Arms

```text
A. no_memory
B. rag_over_logs
C. memoryweaver_runtime_marker
```

## Results

```json
{
  "task_count": 50,
  "task_run_count": 150,
  "decision_count": 150,
  "hash_chain_valid": true,
  "mock_tool_execution_count": 500,
  "mw_steps_to_success_delta_vs_no_memory": 3,
  "mw_steps_to_success_delta_vs_rag": 1,
  "mw_known_bad_tool_failure_reduction_vs_no_memory": 55,
  "mw_known_bad_tool_failure_reduction_vs_rag": 50,
  "mw_required_evidence_first_hit_rate": 1.0,
  "mw_known_bad_warning_count": 55,
  "mw_evidence_observed_count": 100,
  "mw_unsafe_mock_tool_execution_count": 0,
  "real_tool_execution_count": 0,
  "memory_promotion_count": 0,
  "layer3_mutation_count": 0,
  "online_llm_call_count": 0
}
```

## Interpretation

Compared with v0.6.1, this run no longer records only tool plans. It executes
mock tools and records tool results inside each task trajectory.

The outcome preserves the same ordering:

```text
no_memory                  -> executes more known-bad mock tools
rag_over_logs              -> retrieves related logs but still executes one bad mock tool
memoryweaver_runtime_marker -> warns on known-bad paths and executes evidence tools first
```

This is still not live agent execution, but it is a stronger local harness
boundary than replay or plan-only simulation.

## Non-Claims

This validation does not prove:

- real shell/tool execution
- autonomous LLM agent behavior
- external benchmark performance
- production runtime safety

It proves that the MemoryWeaver marker arm can run through a deterministic tool
runtime, avoid unsafe mock tool execution, preserve decision auditability, and
observe required evidence first.

## Artifacts

```text
raw_results.json
metrics_summary.json
arms.jsonl
task_runs.jsonl
decisions.jsonl
```
