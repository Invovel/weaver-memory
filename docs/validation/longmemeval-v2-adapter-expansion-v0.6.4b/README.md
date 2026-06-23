# v0.6.4b LongMemEval-V2 Adapter Expansion

This validation expands the LongMemEval-V2 local snapshot adapter from the
v0.6.4a smoke run into bounded 50 / 100 question coverage runs.

It answers one question only:

> Can external LongMemEval-V2 data safely enter MemoryWeaver's external
> adapter substrate without writing verified memory or mutating lifecycle state?

It does **not** evaluate task success, agent behavior, memory promotion, Layer-3
pattern mutation, or runtime marker writes. Those belong to the separate
`v0.6.3-live-memory-loop` line.

## Result

- Overall passed: True
- Input root: `None`
- Question limits: [50, 100]
- Trajectories per question: 3
- States per trajectory: 5
- Online LLM calls: 0

| Questions | Loaded Traj. | Candidates | Field Cov. | Evidence Ref Valid | Unsupported | Gate Leaks | Verified Writes | Promotions | L3 Mutations |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 50 | 3 | 1900 | 1.000 | 1.000 | 0.000 | 0 | 0 | 0 | 0 |
| 100 | 3 | 3800 | 1.000 | 1.000 | 0.000 | 0 | 0 | 0 | 0 |

## Reports

- `adapter_quality_report.json`: join rate, haystack coverage, conversion volume.
- `missing_field_report.json`: missing raw question / trajectory / state fields.
- `evidence_ref_report.json`: raw evidence reference coverage and validity.
- `candidate_memory_type_stats.json`: candidate source, polarity, type, freshness counts.
- `signal_report.json`: known-bad path and conflict-signal preservation.

## Boundary

The dry-run boundary is intentionally hard:

- `verified_memory_write_count = 0`
- `promotion_count = 0`
- `layer3_mutation_count = 0`
- `runtime_marker_write_count = 0`
- `known_bad_path_write_count = 0`
- `online_llm_call_count = 0`

## Interpretation

v0.6.4b is the external-data ingestion lane. It verifies adapter coverage,
evidence-reference integrity, candidate density, and trust-boundary safety at
larger LongMemEval-V2 sample sizes. It should not be mixed with v0.6.3, which
is the live-memory lifecycle lane for real writes, promotion, retrieval,
conflict handling, rollback, Layer-3 mutation, and runtime marker writes.
