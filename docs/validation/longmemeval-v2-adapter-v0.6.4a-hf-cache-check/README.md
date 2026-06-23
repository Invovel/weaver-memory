# v0.6.4a LongMemEval-V2 Adapter + LLM Smoke

This validation consumes an unprocessed local LongMemEval-V2 snapshot and
routes it through MemoryWeaver's external adapter pipeline.

It validates:

- raw questions / trajectories / haystack field mapping
- ExternalEpisode conversion
- RawSpan creation
- ContextCapsule creation
- Layer-1 candidate dry-run
- source-gated policy boundary
- optional DeepSeek action-selection smoke

## Result

- Adapter passed: True
- Overall passed: True
- Questions: 20
- Loaded trajectories: 2
- Raw spans: 340
- Capsules: 340
- Candidate memories: 340
- Raw ref coverage: 1.0
- Policy gate leak count: 0
- Assistant ambiguous count: 100 / 100
- Online LLM calls: 0
- LLM attempted: False
- LLM JSON parse success: False

## Boundaries

- LLM cannot write memory.
- LLM cannot promote memory.
- LLM cannot create stable pattern.
- LLM cannot write graph edges.
- External data remains Layer-1 candidate dry-run only.

## Interpretation

v0.6.4a shows that LongMemEval-V2 local snapshot data can enter the
MemoryWeaver memory substrate without breaking the trust boundary. The optional
LLM smoke only validates action-selection connectivity; it is not a task
success score.
