# Graph Tag-Linking v0.3 Validation

## Summary

This validation checks whether a minimal GBrain / mind-map tag-linking layer can
improve candidate recall and candidate narrowing without changing Layer-3
lifecycle rules.

Raw data is stored in [`raw_results.json`](raw_results.json).

## Scope

Implemented graph objects:

- `TagNode`
- `MemoryNode`
- `EvidenceNode`
- `PatternNode`
- `RelationEdge`
- `GraphProposal`

Implemented edge relations:

- `supports`
- `contradicts`
- `related_to`
- `same_issue_as`
- `caused_by`
- `supersedes`

Explicitly not allowed in this phase:

- automatic stable Pattern creation
- automatic memory deletion
- automatic overwrite of verified memory
- automatic Layer-3 promotion
- automatic fast routing

The graph only affects candidate recall. Final filtering remains under
`RetrievalPolicy`, and Layer 3 still obeys:

```text
provisional Pattern -> fast_verify
stable Pattern -> fast
EvidenceLink does not auto-promote memory
Scorer does not create Layer 3
```

## Procedure

```powershell
python benchmarks\graph_retrieval_baseline.py `
  --iterations 100 `
  --filler-items 45 `
  --output docs\validation\graph-tag-linking-v0.3\raw_results.json
python -m pytest -q
```

## Fixture

The benchmark constructs 50 memories:

- 5 hand-labeled Codex CLI subscription memories.
- 45 unrelated filler memories.
- 119 graph edges.
- 1 LLM-style `GraphProposal` left as `pending`.
- Evidence linked to the organization-selection memory.

The controlled topic includes:

- Codex CLI subscription failed
- WSL environment
- npm install success / reinstall failed
- `codex --version` success
- organization selection
- API key exists
- login refresh helped

## Results

| Query | Tag Recall@5 | Baseline Tag Memory Recall@10 | Tag Expansion Recall@10 | Graph Candidate Recall@10 | Candidate Reduction | Baseline Text p95 ms | Graph Candidate p95 ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `Codex 订阅加载失败` | 1.00 | 0.50 | 1.00 | 1.00 | 0.90 | 0.576 | 0.149 |
| `subscription failed in WSL` | 1.00 | 0.50 | 1.00 | 1.00 | 0.94 | 0.459 | 0.063 |
| `codex org problem` | 1.00 | 0.50 | 1.00 | 1.00 | 0.92 | 0.664 | 0.123 |
| `API key 有了但是 Codex 不能用` | 1.00 | 0.50 | 1.00 | 1.00 | 0.94 | 0.942 | 0.098 |

Aggregate:

- Baseline tag memory recall@10: `0.50`
- Tag expansion memory recall@10: `1.00`
- Graph candidate memory recall@10: `1.00`
- Mean candidate reduction ratio: `0.925`
- Mean baseline text p95: `0.660 ms`
- Mean graph candidate p95: `0.106 ms`
- Evidence link accuracy: `1.00`
- Wrong link rate: `0.00`
- Stale link rate: `0.00`

## Interpretation

The graph layer improved recall for tag-based search while reducing the
candidate set before verified text reranking. In this controlled fixture, graph
candidate search reduced the candidate pool by about 92.5% while preserving
memory recall@10.

This supports the next hypothesis:

```text
GBrain can shift retrieval from full text scan toward structured candidate
recall + graph expansion + small verified rerank.
```

It does not prove real task success improvement. The next task-level experiment
still needs No Memory vs RAG over logs vs MemoryWeaver comparisons.

## Risk Notes

Graph expansion precision ranged from `0.40` to `0.67`, which is useful but not
clean enough for final decisions. This confirms the current hard boundary:

- Graph output may narrow or expand candidates.
- Graph output must not become final truth.
- LLM-generated graph changes must remain `GraphProposal` until accepted by a
  deterministic or human-reviewed gate.
