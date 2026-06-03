# Changelog

## Unreleased - Graph Tag-Linking Validation

- Added minimal graph schema/store/linker/retriever modules.
- Added candidate-only GraphProposal support.
- Added graph-assisted tag expansion and candidate memory narrowing.
- Added graph retrieval benchmark comparing baseline search, tag expansion, and graph candidate search.
- Added validation report under `docs/validation/graph-tag-linking-v0.3/`.
- Preserved Layer 3 lifecycle rules: provisional Patterns stay capped at `fast_verify`; only stable Patterns can route `fast`.

## v0.2.0 - Provisional Pattern Foundation

Validated on 2026-06-03 and tagged as
`sdk-v0.2.0-provisional-pattern-foundation`.

This release establishes the trust-boundary foundation for MemoryWeaver:

- Added `MemoryPolicy` and `RetrievalPolicy`.
- Added `EvidenceNode`, `EvidenceLink`, `EvidencePacket`, and `EvidenceStore`.
- Added `MemoryWorkspace` with directory-backed JSON stores.
- Added canonical `Pattern`, `PatternStore`, and `PatternComposer`.
- Added `memoryweaver.cli:main` with validate, memory, evidence, pattern, and route commands.
- Replaced whitespace-only text matching with a Chinese and mixed-language lexical baseline.
- Prevented new Layer-3 `MemoryItem` writes; legacy Layer-3 JSON remains readable with validation warnings.
- Restricted provisional Patterns to `fast_verify`; only stable, fresh, high-confidence Patterns can route `fast`.
- Kept `Scorer.evaluate()` limited to Layer 1 / Layer 2 lifecycle signals.

Validation:

- `python -m pytest -q`: `113 passed`
- CLI workspace smoke check: valid
- Five-trial local benchmark saved under `docs/validation/sdk-v0.2.0/`

Scope:

- This is a system correctness and trust-boundary validation release.
- It does not prove task success improvement, repeated error reduction, cross-model reuse, or long-term production stability.
- GBrain, graph expansion, full RAG runtime, embeddings, vector DB, HarnessRuntime, ActionGate, checkpointing, and real LLM providers remain deferred.

## Next

### v0.2.1 - Documentation And SDK Stability

- Keep raw validation data attached to the release.
- Clarify benchmark scope as correctness plus local prototype performance.
- Keep Layer 3 provisional policy documented as a hard rule.
- Preserve the P0 regression gate.

### v0.3.0 - Task-Level Experiments

- Add `task_runs.jsonl`, `evaluation_metrics.json`, and `case_studies.md`.
- Compare No Memory vs RAG over logs vs MemoryWeaver v0.2.0.
- Measure steps-to-success, repeated error reduction, path reuse rate, tool error rate, and memory activation accuracy.

### v0.4.0 - Indexed And Graph-Aware Runtime

- Add `ConflictDetector`, fuller `EvidencePacket`, SQLite/indexed backend, simple vector backend, and minimal GBrain projection.
- Keep the hard rule: LLMs may maintain candidate graph, candidate summaries, and candidate branches, but never verified memory or stable Patterns directly.
