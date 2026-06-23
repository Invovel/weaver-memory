# v0.6.3 Live Memory Loop

This validation is separate from the v0.6.4 external-data adapter line.

It exercises actual MemoryWeaver workspace writes and lifecycle transitions:

- evidence write
- Layer-1 verified memory write
- explicit Layer-2 promotion
- verified retrieval
- contradiction handling
- provisional Layer-3 Pattern composition
- rollback
- runtime marker context write
- known-bad path write

No LLM is called in this lifecycle substrate check.

## Result

- Passed: True
- Verified memory writes: 2
- Promotions: 2
- Retrieval results: 2
- Conflict handling count: 1
- Layer-3 mutations: 1
- Rollbacks: 1
- Runtime marker writes: 1
- Known-bad path writes: 1
- Online LLM calls: 0

## Boundary

v0.6.3-live-memory-loop proves that lifecycle writes can happen in the SDK.
v0.6.4b proves that external LongMemEval-V2 rows can enter safely without
writes. These lanes are intentionally separate.
