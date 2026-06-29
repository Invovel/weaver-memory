# Claim To Metric Mapping

This note connects the current MemoryWeaver claims to concrete metrics,
benchmarks, and validation artifacts.

The goal is simple: every major statement should point to a measurable signal
and an existing artifact.

## Core Principle

MemoryWeaver should not rely on vague benefit claims such as "better memory" or
"more context awareness." The current stage should only claim what is backed by:

- tool results
- test outcomes
- user correction
- diff validity
- benchmark deltas
- repeated validation
- conflict evidence
- rollback records

## Claim Mapping

| Claim | Metric | Benchmark / protocol | Artifact |
| --- | --- | --- | --- |
| MemoryWeaver reduces repeated agent failures | `repeated_failure_rate`, `repeated_failure_rate_delta_vs_no_memory` | `benchmarks/harness_runtime_core.py` | `docs/validation/harness-runtime-core/README.md`, `metrics.json`, `raw_results.json` |
| MemoryWeaver reduces invalid actions better than naive memory | `invalid_action_rate`, `invalid_action_rate_delta_vs_naive_memory` | `benchmarks/harness_runtime_core.py` | `docs/validation/harness-runtime-core/README.md`, `task_runs.jsonl` |
| Promotion is safer than naive memory reuse | `memory_induced_regression_rate`, `memory_induced_regression_delta_vs_naive_memory` | `benchmarks/harness_runtime_core.py` | `docs/validation/harness-runtime-core/README.md`, `raw_results.json` |
| Promotion is precise rather than noisy | `promotion_precision` | `benchmarks/harness_runtime_core.py` | `docs/validation/harness-runtime-core/README.md`, `metrics.json` |
| Negative memory is actually being reused | `negative_memory_hit_rate` | `benchmarks/harness_runtime_core.py` | `docs/validation/harness-runtime-core/README.md`, `task_runs.jsonl` |
| Rollback is functional, not decorative | `rollback_frequency`, `rollback_recovery_success_rate` | `benchmarks/harness_runtime_core.py` | `docs/validation/harness-runtime-core/README.md`, `raw_results.json` |
| Trace-derived candidate paths can be admitted and safely reused across sibling tasks | `candidate_registration_audited`, `rejected_evidence_audited_count`, `trace_store_roundtrip`, `runtime_path_store_roundtrip`, `repeated_failure_rate`, `negative_memory_hit_rate`, task-scoped replay journal / checkpoint counts | `benchmarks/harness_runtime_trace_loop.py` | `docs/validation/harness-runtime-trace-loop/README.md`, `metrics.json`, `raw_results.json` |
| Live-agent proposals can enter the same runtime-path evidence gate without promotion authority | `live_proposal_count`, `tool_result_count`, `canonicalized_bundle_count`, `tests_passed`, `file_diff_matches_expected`, `benchmark_delta`, `candidate_registration_audited`, `promotion_external_evidence_only`, `rollback_recorded` | `benchmarks/harness_runtime_live_llm.py --llm` | `docs/validation/harness-runtime-live-llm/README.md`, `reliability.json` |
| Coding-agent debug experience can be promoted from real test and diff evidence | `real_pytest_before_failed`, `real_pytest_after_passed`, `real_diff_matches_expected`, `candidate_registration_promotable`, `promotion_external_evidence_only`, `repeated_failure_rate_delta_vs_no_memory`, `memory_induced_regression_delta_vs_naive_memory`, `rollback_recorded` | `benchmarks/harness_runtime_coding_debug.py` | `docs/validation/harness-runtime-coding-debug/README.md`, `pytest_before.txt`, `pytest_after.txt`, `diff.patch`, `metrics.json` |
| Runtime path state survives persistence boundaries | `runtime_path_store_roundtrip`, journal count, checkpoint count | `benchmarks/harness_runtime_core.py` | `runtime_path_store.json`, `events.jsonl`, `checkpoints.json` |
| Verified experience transfers across sibling tasks | `average_steps_to_success`, `retrieval_hit_before_critical_action_rate`, `critical_action_changed_by_memory_rate` | `benchmarks/experience_transfer_protocol_v0_7.py` | `docs/validation/experience-transfer-v0.7/`, `arm_metrics.json`, `probe_metrics.json` |
| Experience transfer is reliable across repeated runs | `pass_at_1`, `pass_power_3`, mean / std summaries | `benchmarks/experience_transfer_protocol_v0_7.py` with reliability passes | `reliability.json`, `raw_results.json` |
| Trace-seeded runtime path reuse is reliable across repeated runs | `pass_at_1`, `pass_power_3`, mean / std summaries for repeated failure, invalid action, rollback, and negative memory hit rate | `benchmarks/harness_runtime_trace_loop.py` with reliability passes | `docs/validation/harness-runtime-trace-loop/reliability.json`, `raw_results.json` |
| Live LLM proposals remain under Harness authority | live `online_llm_call_count`, live `tool_result_count`, `canonicalized_bundle_count`, `tests_passed`, `file_diff_matches_expected`, `benchmark_delta`, `conflict_count`, `rollback_frequency`, `promotion_precision` | `benchmarks/harness_runtime_live_llm.py --llm` | `docs/validation/harness-runtime-live-llm/README.md`, `metrics.json`, `raw_results.json` |
| Live LLM path-promotion reliability holds across three runs | live `pass_at_1`, live `pass_power_3`, mean / std for invalid action, known bad, memory-induced regression, rollback, and promotion precision | `benchmarks/harness_runtime_live_llm.py --llm --reliability-passes 3` | `docs/validation/harness-runtime-live-llm/reliability.json` |
| v0.8 substrate is fully wired before optimization | `rag_evidence_hit_count`, `citation_coverage`, `gbrain_candidate_node_count`, `gbrain_candidate_edge_count`, `specialist_run_count`, `evidence_packet_ref_count`, `checkpoint_resume_success`, `pass_power_3` | `benchmarks/v08_integration_validation.py` | `docs/validation/v0.8-integration/README.md`, `metrics.json`, `evidence_packet.json`, `reliability.json` |
| v0.8 preserves Harness authority while adding RAG/GBrain/specialists | `verified_memory_write_count == 0`, `layer3_mutation_count == 0`, `promotion_without_hard_evidence_count == 0`, `gbrain_authority_granted == false`, `hyde_synthetic_not_promoted == true` | `benchmarks/v08_integration_validation.py` | `docs/validation/v0.8-integration/metrics.json`, `gbrain_search.json`, `gbrain_think.json` |
| Probe-based decision changes are not polluted by invalid actions | `probe_valid`, `decision_changed_valid_rate`, invalid probe count | `experience_transfer` probe path | `decision_probe.jsonl`, `probe_metrics.json` |
| Layer-3 path promotion supports stable selection and replacement | `stable_promotion_rate`, `latest_path_selection_accuracy`, `stale_path_suppression_rate`, `rollback_success_rate`, `average_path_regret` | `benchmarks/layer3_path_promotion_v0_7.py` | `docs/validation/layer3-path-promotion-v0.7/README.md` |
| Layer-3 path promotion improves end-to-end coding-debug execution paths | `best_path_selection_accuracy`, `path_regret_delta_vs_verified_memory`, `tests_passed`, `file_diff_matches_expected`, `memory_induced_regression_rate`, `rollback_success_rate`, `pass_power_3` | `benchmarks/layer3_path_promotion_e2e.py` | `docs/validation/layer3-path-promotion-e2e/README.md`, `metrics.json`, `artifact_manifest.json`, `claim_table.md`, `reliability.json` |
| Retrieval Wear differs from answer caching and blind path reuse | `semantic_transfer_rate`, `stale_path_reuse_rate`, `path_invalidation_rate`, `rollback_success_rate`, `total_candidates_inspected`, `pass_power_3` | `benchmarks/retrieval_wear_e2e.py` | `docs/validation/retrieval-wear-e2e/README.md`, `arm_metrics.json`, `task_runs.jsonl`, `claim_table.md`, `reliability.json` |
| Optimized skills or generated procedures are candidates, not runtime authority | `promotion_without_hard_evidence_count == 0`, `verified_memory_write_count == 0`, `layer3_mutation_count == 0`, candidate proposal records remain non-authoritative before Harness review | `benchmarks/v08_integration_validation.py`, LLM graph proposal validations | `docs/validation/v0.8-integration/metrics.json`, `docs/validation/llm-graph-proposal-v0.4.2/README.md` |
| Conflicted paths can be replaced by healthier runtime paths instead of only falling back | replacement-path selection after conflict, rollback avoidance on replacement path, stale-path suppression behavior | `HarnessRuntime` selection logic + runtime tests | `tests/test_harness_runtime.py` |

## Claim Groups

### 1. Promotion beats retrieval-only memory

Supported by:

- `invalid_action_rate`
- `task_success_delta_vs_retrieval_memory`
- `promotion_precision`

Current primary artifact:

- [harness-runtime-core](./validation/harness-runtime-core/README.md)

### 2. Promotion does not amplify contamination

Supported by:

- `memory_induced_regression_rate`
- `memory_induced_regression_delta_vs_naive_memory`
- probe-valid filtering and invalid-action exclusion

Current primary artifacts:

- [harness-runtime-core](./validation/harness-runtime-core/README.md)
- [harness-runtime-trace-loop](./validation/harness-runtime-trace-loop/README.md)
- [experience-transfer-v0.7](./validation/experience-transfer-v0.7/README.md)

### 3. Rollback restores stability after conflict

Supported by:

- `rollback_frequency`
- `rollback_recovery_success_rate`
- conflict-triggered fallback decisions

Current primary artifact:

- [harness-runtime-core](./validation/harness-runtime-core/README.md)
- [harness-runtime-trace-loop](./validation/harness-runtime-trace-loop/README.md)

### 4. Verified experience can become reusable runtime paths

Supported by:

- `stable_promotion_rate`
- `latest_path_selection_accuracy`
- `stale_path_suppression_rate`
- `average_path_regret`

Current primary artifact:

- [layer3-path-promotion-v0.7](./validation/layer3-path-promotion-v0.7/README.md)
- [layer3-path-promotion-e2e](./validation/layer3-path-promotion-e2e/README.md)
- [harness-runtime-trace-loop](./validation/harness-runtime-trace-loop/README.md)

## What Is Already Strong

- Repeated failure reduction in a deterministic runtime-path fixture
- Lower invalid-action rate than `no_memory`, `naive_memory`, `summary_memory`,
  and `retrieval_memory`
- Zero measured memory-induced regression in the current runtime-core fixture
- Functional rollback and rollback recovery path
- `pass^3` reliability artifact for the experience-transfer line
- Trace-seeded candidate registration with rejected-evidence audit and same-family replay
- Live LLM proposal bridge with `pass^3`, external evidence gating, bundle-target
  canonicalization audit, and rollback ledger
- Coding-debug micro-repo validation with real pytest failure, real patch diff,
  real pytest pass, and rollback ledger
- Layer-3 path-promotion E2E validation that compares `no_memory`,
  `raw_rag_over_logs`, `retrieval_memory`, `mw_verified_memory`, and
  `mw_layer3_path` with pass^3 pytest/diff evidence
- v0.8 integrated substrate validation with citable RAG refs, candidate GBrain
  graph, specialist EvidencePacket, checkpoint/resume, and pass^3 reliability

## What Still Needs Stronger Evidence

- More open-world task families beyond the current deterministic fixture
- More coding-agent style families beyond the current micro-repo pytest/diff loop
- More environmental change scenarios for stale-path replacement
- A broader claim bridge from deterministic fixture to longer-running agent use
- More external benchmark scale beyond the current v0.9 optimization and Layer-3
  E2E evidence chain

## Canonical Research Question

Use this question consistently:

> Can evidence-gated path promotion reduce repeated agent failures without
> increasing memory-induced error propagation?

## Canonical Experimental Summary

Use this concise summary when needed:

> MemoryWeaver should be evaluated not by how much it remembers, but by whether
> verified experience reduces repeated failure, avoids contamination, and can be
> rolled back when it becomes unsafe.
