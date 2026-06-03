# SDK v0.2.0 Provisional Pattern Validation

## Summary

This batch validates the standalone JSON-backed SDK v0.2.0 foundation:

- `MemoryPolicy` and `RetrievalPolicy` source gates.
- CLI import and workspace validation.
- Explicit Layer 1 to Layer 2 promotion.
- Evidence node/link persistence and validation.
- Canonical provisional/stable Pattern routing.
- Chinese and mixed-language lexical retrieval baseline.
- P0 trust-boundary regression gate.

Raw data is stored in [`raw_results.json`](raw_results.json).

This is a **system correctness validation** and **trust-boundary validation**.
It is not the main task-performance experiment.

## What This Proves

- The implementation follows the source-gated design principles.
- Basic write, retrieval, routing, and validation paths do not bypass policy gates.
- Assistant and synthetic sources do not become trusted positive memory by default.
- Evidence links can support memory and Pattern records without automatically promoting them.
- Provisional and stable Layer-3 routing behaves as intended.
- Chinese and mixed-language lexical retrieval has a working baseline.
- CLI and workspace validation can run as smoke checks.

## What This Does Not Prove

- That an Agent solves real tasks faster.
- That repeated errors decrease in realistic task loops.
- That MemoryWeaver is better than RAG over logs.
- That memory can be reused across different LLMs.
- That the system is stable over long-running real projects.

Those claims require the next task-level experiment:

```text
No memory
vs RAG over logs
vs MemoryWeaver v0.2.0
```

with task metrics such as steps-to-success, repeated error count, path reuse
rate, tool error rate, and memory activation accuracy.

## Procedure

```powershell
python -m pytest -q
python .\scripts\collect_p0_validation.py `
  --output .\docs\validation\sdk-v0.2.0\raw_results.json `
  --trials 5 --items 100 500 1000 --query-iterations 200
python -m memoryweaver.cli validate --root .\.memoryweaver-sdk-smoke --json
```

## Correctness Probes

The five trials produced the same correctness result shape:

| Probe | Result |
| --- | --- |
| CLI module exists | `true` |
| Plain update heat | `0` |
| Lifecycle transition heat | `0` |
| Explicit access heat | `1` |
| Tag search returns unverified assistant | `false` |
| Assistant positive accepted | `false` |
| Assistant after write | `ambiguous`, confidence `0.3` |
| Unverified assistant route | `thinking` |
| Provisional Pattern route | `fast_verify` |
| Stable Pattern route | `fast` |
| Chinese reordered query match count | `1` |
| Workspace validate | `true` |

## Aggregate Performance

Mean values across five trials:

| Items | JSON bytes | Write items/s | Reload ms | Tag p95 ms | Verified tag p95 ms | Similar p95 ms | Verified text p95 ms |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 100 | 91,465 | 280.798 | 9.350 | 0.125 | 0.137 | 1.225 | 1.329 |
| 500 | 458,025 | 72.936 | 25.595 | 0.544 | 0.576 | 5.656 | 6.224 |
| 1,000 | 916,225 | 38.408 | 25.073 | 1.032 | 1.119 | 10.816 | 11.928 |

## Interpretation

The SDK v0.2.0 gates close the Sprint 0.1 surface:

- Layer 3 is provisional by default.
- `Scorer.evaluate()` does not create Layer 3.
- RAG-like evidence can be linked, but evidence links do not auto-promote memory.
- Provisional Patterns can be recalled, but the router caps them at `fast_verify`.
- Only stable, fresh, high-confidence Patterns can recommend `fast`.

This remains a local JSON prototype. The benchmark does not certify production
capacity, concurrency, crash recovery, GBrain graph expansion, vector search, or
full RAG runtime behavior.

SDK v0.2.0 is therefore sufficient for small-scale semantic validation and for
starting controlled task-level experiments, but it is not evidence of improved
task success rate yet.
