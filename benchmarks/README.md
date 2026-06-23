# Benchmark Guide

This folder mixes a few current primary entry points with many historical
validation scripts. Use this index to avoid guessing.

## Primary Current Entry Points

- [prototype_baseline.py](./prototype_baseline.py) - local prototype correctness probes and microbenchmark
- [layer3_path_promotion_v0_7.py](./layer3_path_promotion_v0_7.py) - main deterministic Layer-3 path-promotion validation
- [layer3_path_promotion_e2e.py](./layer3_path_promotion_e2e.py) - paper-facing Layer-3 path-promotion E2E benchmark with real pytest/diff evidence
- [layer3_path_promotion_lme_v2.py](./layer3_path_promotion_lme_v2.py) - real-snapshot LongMemEval-V2 path-promotion bridge
- [lme_v2_storage_check.py](./lme_v2_storage_check.py) - local LongMemEval-V2 root/Hugging Face cache inspection
- [hf_dataset_candidates_check.py](./hf_dataset_candidates_check.py) - Hugging Face dataset candidate metadata and integration-boundary check
- [memoryagentbench_adapter_check.py](./memoryagentbench_adapter_check.py) - MemoryAgentBench Hugging Face preview adapter dry-run
- [locomo_mc10_adapter_check.py](./locomo_mc10_adapter_check.py) - LoCoMo-MC10 Hugging Face preview adapter dry-run
- [experience_transfer_protocol_v0_7.py](./experience_transfer_protocol_v0_7.py) - sibling-task verified-experience reuse protocol
- [random_experience_accumulation_v0_7.py](./random_experience_accumulation_v0_7.py) - random-experience accumulation protocol

## Runtime / Harness Validation

- `real_trajectory_experiment_v0_6.py`
- `controlled_harness_run_v0_6_1.py`
- `live_lite_harness_v0_6_2.py`
- `live_memory_loop_v0_6_3.py`
- `live_agent_loop_v0_6_3.py`

## Retrieval / Context / Marker Validation

- `context_capsule_validation.py`
- `context_capsule_stress_validation.py`
- `retrieval_comparison_validation.py`
- `retrieval_fts5_filter_validation.py`
- `retrieval_safety_filter_validation.py`
- `runbook_marker_trace_fixture.py`
- `active_marker_binding_validation.py`
- `controlled_active_guard_validation.py`
- `l2_route_approval_validation.py`
- `decision_ledger_validation.py`

## Graph / GBrain / External Dataset Validation

- `llm_graph_proposal_validation.py`
- `temporal_gbrain_drift_validation.py`
- `temporal_graph_ablation_validation.py`
- `external_dataset_adapter_v0_6_4.py`
- `longmemeval_v2_adapter_v0_6_4a.py`
- `longmemeval_v2_adapter_expansion_v0_6_4b.py`
- `memevobench_adapter.py`

## Note

Most scripts here write their reproducible outputs under `docs/validation/`.
If you are unsure what to run today, prefer `scripts/current_stage_check.py`
first and then pick a primary current entry point from the list above.
