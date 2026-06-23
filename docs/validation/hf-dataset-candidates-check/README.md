# Hugging Face Dataset Candidates Check

This validation checks MemoryWeaver's Hugging Face dataset candidate list.

passed = true
live_checked = true

## Metrics

- `dataset_count` = 9
- `primary_dataset_count` = 1
- `candidate_dataset_count` = 8
- `integrated_dataset_count` = 1
- `not_integrated_candidate_count` = 6
- `preview_adapter_validated_count` = 2
- `boundary_violation_count` = 0
- `live_checked_count` = 9
- `live_available_count` = 9
- `live_error_count` = 0
- `license_mismatch_count` = 0
- `size_mismatch_count` = 0

## Boundary

Only `xiaowu0162/longmemeval-v2` should be marked as integrated.
Candidate datasets may be `not_integrated` or `preview_adapter_validated`, but only LME-V2 is an integrated external path-promotion dataset.

## Files

- `metrics.json`
- `candidate_checks.jsonl`
- `live_metadata.json`
- `raw_results.json`
