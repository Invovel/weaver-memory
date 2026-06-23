# Hugging Face LongMemEval-V2 Cache Check

Date: 2026-06-12

## Result

The local LongMemEval-V2 evaluation path is usable on this machine.

```text
HF cache root: D:\hf_cache
Readable snapshot root: D:\benchmarks\longmemeval-v2
Dataset repo: xiaowu0162/longmemeval-v2
```

`D:\hf_cache` currently contains the Hugging Face repo reference under
`hub/datasets--xiaowu0162--longmemeval-v2/refs/main`, but it does not currently
contain a complete `snapshots/<revision>/` tree. The complete readable files are
under `D:\benchmarks\longmemeval-v2`.

## Verified Commands

```powershell
python benchmarks\longmemeval_v2_adapter_v0_6_4a.py `
  --output-dir docs\validation\longmemeval-v2-adapter-v0.6.4a-hf-cache-check `
  --hf-cache-root D:\hf_cache
```

Result:

```text
passed = true
question_count = 20
raw_span_count = 340
capsule_count = 340
assistant_candidate_count = 100
assistant_ambiguous_count = 100
memory_promotion_count = 0
layer3_mutation_count = 0
```

```powershell
python benchmarks\layer3_path_promotion_lme_v2.py `
  --output-dir docs\validation\layer3-path-promotion-lme-v2-hf-cache-check `
  --hf-cache-root D:\hf_cache `
  --question-limit 3 `
  --trajectories-per-question 1 `
  --states-per-trajectory 2
```

Result:

```text
passed = true
family_count = 3
task_count = 9
latest_path_selection_accuracy = 1.0
stale_path_suppression_rate = 1.0
rollback_success_rate = 1.0
root_resolution_source = benchmarks
resolved_root = D:\benchmarks\longmemeval-v2
```

## Interpretation

For current experiments, use `D:\benchmarks\longmemeval-v2` as `--input-root`
or rely on the resolver's benchmark-root default. Keep `D:\hf_cache` as
`--hf-cache-root` for download/cache behavior.

Do not claim that the benchmark read directly from a full HF cache snapshot
unless `D:\hf_cache\hub\datasets--xiaowu0162--longmemeval-v2\snapshots\<revision>`
contains the required files:

```text
questions.jsonl
trajectories.jsonl
haystacks/lme_v2_small.json
```
