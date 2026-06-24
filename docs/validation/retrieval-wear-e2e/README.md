# Retrieval Wear End-to-End Benchmark

Controlled evidence for loop-aware retrieval-path reuse.

- `passed` = true
- `pass^3` = true
- `task_family_count` = 50
- `capsule_count` = 341

## Arms

| arm | evidence hit | semantic transfer | stale reuse | rollback | candidates inspected | retrieval calls |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| no_memory | 1.0 | 0.0 | 0.0 | 0.0 | 51150 | 150 |
| answer_cache | 0.6667 | 0.0 | 1.0 | 0.0 | 34100 | 100 |
| rag_only | 1.0 | 0.0 | 0.0 | 0.0 | 51150 | 150 |
| retrieval_path_memory | 0.6667 | 1.0 | 1.0 | 0.0 | 17694 | 150 |
| memoryweaver | 1.0 | 1.0 | 0.0 | 1.0 | 34422 | 150 |

## Protocol

Each task family runs three rounds: initial exploration, semantic paraphrase,
and evidence-version drift. `answer_cache` uses exact query keys;
`retrieval_path_memory` reuses a path without freshness authority;
`memoryweaver` reuses the scoped path for paraphrases but invalidates it
when the evidence version changes.

## Claim Boundary

This benchmark uses the repository's controlled 50-card / 341-capsule fixture.
Candidate counts and retrieval latency come from executed local retrieval.
Evidence-version drift is a controlled protocol signal, not a production
document-index update. The result does not establish open-world RAG
superiority, generation quality, or production latency.

## Artifacts

- `raw_results.json`
- `metrics.json`
- `arm_metrics.json`
- `task_runs.jsonl`
- `reliability.json`
- `claim_table.md`
