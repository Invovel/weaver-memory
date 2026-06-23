# v0.6.4 External Dataset Adapter Spike

This validation checks whether external benchmark-shaped rows can enter the
MemoryWeaver data pipeline without bypassing the trust boundary.

Datasets represented by local schema fixtures:

- ai-hyz/MemoryAgentBench
- mteb/LongMemEval
- mteb/LoCoMo

This is not an official benchmark score. It is an adapter spike:
external row -> ExternalEpisode -> RawSpan -> ContextCapsule -> Layer-1
candidate dry-run -> policy gate dry-run.

## Result

- Passed: True
- Dataset count: 3
- Sample count: 6
- Conversion success rate: 1.0
- Raw ref coverage: 1.0
- Capsule build success rate: 1.0
- Policy gate leak count: 0
- Conflict signal count: 3
- Temporal signal count: 6

## Boundaries

- No online dataset download.
- No LLM call.
- No real tool execution.
- No verified memory write.
- No memory promotion.
- No Layer-3 mutation.

## Interpretation

v0.6.4 proves that the first external benchmark adapter path is structurally
viable. It does not prove task success, answer accuracy, or live agent
behavior. Those remain for v0.6.3 live loop and later external dataset
evaluation.
