# LoCoMo-MC10 Adapter Check

This validation consumes a small Hugging Face preview or fixture for
`Percena/locomo-mc10` and routes it through the MemoryWeaver external substrate.

## Result

- passed = true
- source_mode = `hf_first_rows`
- sample_count = 3
- raw_span_count = 638
- capsule_count = 638
- candidate_memory_count = 638
- choice_10_rate = 1.0
- query_answer_pair_coverage = 1.0
- policy_gate_leak_count = 0
- memory_promotion_count = 0
- layer3_mutation_count = 0
- assistant ambiguous count = 208 / 208

## Boundary

This is an adapter/candidate dry-run only. It does not claim LoCoMo-MC10 task
accuracy, verified-memory writes, or Layer-3 path-promotion gains.

## Files

- `metrics.json`
- `raw_results.json`
- `converted_samples.jsonl`
- `capsule_samples.jsonl`
- `candidate_memory_samples.jsonl`
