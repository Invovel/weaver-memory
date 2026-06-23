# MemoryAgentBench Adapter Check

This validation consumes a small Hugging Face preview or fixture for
`ai-hyz/MemoryAgentBench` and routes it through the MemoryWeaver external
substrate.

## Result

- passed = true
- source_mode = `hf_first_rows`
- sample_count = 4
- split_count = 4
- query_count = 103
- raw_span_count = 4
- capsule_count = 4
- candidate_memory_count = 4
- query_answer_pair_coverage = 1.0
- policy_gate_leak_count = 0
- memory_promotion_count = 0
- layer3_mutation_count = 0
- retrieval_signal_count = 1
- temporal_signal_count = 102
- conflict_signal_count = 100

## Boundary

This is a preview adapter / candidate dry-run. It does not claim
MemoryAgentBench task accuracy, verified-memory writes, or Layer-3
path-promotion gains.

## Files

- `metrics.json`
- `raw_results.json`
- `converted_samples.jsonl`
- `capsule_samples.jsonl`
- `candidate_memory_samples.jsonl`
