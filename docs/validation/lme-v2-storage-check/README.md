# LongMemEval-V2 Storage Check

This validation records where MemoryWeaver resolves `xiaowu0162/longmemeval-v2`
on the current machine.

## Result

- passed = true
- dataset_repo_id = `xiaowu0162/longmemeval-v2`
- hf_cache_root = `D:\hf_cache`
- dataset_cache_root_exists = `true`
- refs_main_exists = `true`
- refs_snapshot_complete = `false`
- complete_cache_snapshot_exists = `false`
- root_resolution_source = `benchmarks`
- resolved_root = `D:\benchmarks\longmemeval-v2`
- can_build_external_records = `true`

## Interpretation

`hf_cache_root` is a Hugging Face cache root. It is not necessarily a readable
dataset snapshot. A readable LongMemEval-V2 snapshot must contain:

```text
questions.jsonl
trajectories.jsonl
haystacks/lme_v2_small.json
```

If `root_resolution_source = benchmarks`, current evaluation reads from the
local benchmark snapshot while still keeping `hf_cache_root` available for
download/cache behavior.

## Files

- `storage_report.json`
- `metrics.json`
- `README.md`
