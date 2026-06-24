# Validation Guide

This folder contains reproducible benchmark outputs, raw results, and stage
artifacts. The most useful entry points are below.

## Current Active Validation Lines

- [current-stage-check/README.md](./current-stage-check/README.md) - fixed daily repo-stage check
- [paper-evidence-package/README.md](./paper-evidence-package/README.md) - paper-facing evidence package that maps claims to metrics, artifacts, and limitations
- [layer3-path-promotion-v0.7/README.md](./layer3-path-promotion-v0.7/README.md) - main deterministic Layer-3 path-promotion validation
- [layer3-path-promotion-e2e/README.md](./layer3-path-promotion-e2e/README.md) - paper-facing Layer-3 path-promotion E2E benchmark with real pytest/diff evidence and pass^3
- [layer3-path-promotion-lme-v2/README.md](./layer3-path-promotion-lme-v2/README.md) - real-snapshot LongMemEval-V2 path-promotion bridge
- [retrieval-wear-e2e/README.md](./retrieval-wear-e2e/README.md) - five-arm Retrieval Wear validation: cache, repeated RAG, ungoverned path reuse, and governed invalidation
- [lme-v2-storage-check/README.md](./lme-v2-storage-check/README.md) - machine-readable local LongMemEval-V2 root / Hugging Face cache inspection
- [hf-longmemeval-v2-cache-check.md](./hf-longmemeval-v2-cache-check.md) - local Hugging Face cache/root check for `xiaowu0162/longmemeval-v2`
- [hf-dataset-candidates.md](./hf-dataset-candidates.md) - Hugging Face dataset candidate status for future external benchmark expansion
- [hf-dataset-candidates-check/README.md](./hf-dataset-candidates-check/README.md) - live/static metadata check for Hugging Face dataset candidate boundaries
- [memoryagentbench-adapter-check/README.md](./memoryagentbench-adapter-check/README.md) - Hugging Face `ai-hyz/MemoryAgentBench` preview adapter dry-run
- [locomo-mc10-adapter-check/README.md](./locomo-mc10-adapter-check/README.md) - Hugging Face `Percena/locomo-mc10` preview adapter dry-run
- [experience-transfer-v0.7/README.md](./experience-transfer-v0.7/README.md) - verified-experience sibling-task reuse protocol
- [harness-runtime-trace-loop/README.md](./harness-runtime-trace-loop/README.md) - seed-trace to candidate-path to sibling-task runtime reuse loop
- [harness-runtime-trace-loop/reliability.json](./harness-runtime-trace-loop/reliability.json) - repeated-run reliability summary for the trace-seeded runtime loop
- [harness-runtime-live-llm/README.md](./harness-runtime-live-llm/README.md) - real `--llm` live-agent proposal bridge for runtime-path promotion
- [harness-runtime-live-llm/reliability.json](./harness-runtime-live-llm/reliability.json) - repeated-run reliability summary for the live LLM bridge
- [harness-runtime-coding-debug/README.md](./harness-runtime-coding-debug/README.md) - micro-repo coding-debug runtime path using real pytest and real diff evidence
- [v0.8-integration/README.md](./v0.8-integration/README.md) - complete v0.8 substrate validation: RAG evidence, GBrain candidate graph, specialist EvidencePacket, checkpoint/resume, and pass^3
- [random-experience-v0.7/README.md](./random-experience-v0.7/README.md) - random-experience accumulation protocol

## Supporting Safety / Runtime Lines

- [p0-trust-boundary-2026-06-02/README.md](./p0-trust-boundary-2026-06-02/README.md)
- [context-capsule-v0.5.3/README.md](./context-capsule-v0.5.3/README.md)
- [context-capsule-stress-v0.5.3x/README.md](./context-capsule-stress-v0.5.3x/README.md)
- [retrieval-comparison-v0.5.4/README.md](./retrieval-comparison-v0.5.4/README.md)
- [retrieval-fts5-filter-v0.5.4a/README.md](./retrieval-fts5-filter-v0.5.4a/README.md)
- [retrieval-safety-filter-v0.5.4b/README.md](./retrieval-safety-filter-v0.5.4b/README.md)
- [temporal-gbrain-drift-v0.5.5/README.md](./temporal-gbrain-drift-v0.5.5/README.md)
- [temporal-graph-ablation-v0.5.5b/README.md](./temporal-graph-ablation-v0.5.5b/README.md)
- [real-trajectory-experiment-v0.6/README.md](./real-trajectory-experiment-v0.6/README.md)
- [controlled-harness-run-v0.6.1/README.md](./controlled-harness-run-v0.6.1/README.md)
- [live-lite-harness-v0.6.2/README.md](./live-lite-harness-v0.6.2/README.md)

## Notes

- Many folders here are historical stage artifacts and remain useful as evidence.
- For the current repository story, start with the Layer-3 v0.7 lines and the current-stage check.
- Most folders include both `README.md` and machine-readable result files such as `metrics.json`, `raw_results.json`, or `task_runs.jsonl`.
