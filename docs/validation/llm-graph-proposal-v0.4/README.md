# LLM GraphProposal v0.4 Validation

## Summary

This validation checks the optional API/provider framework for low-privilege
GraphProposal generation.

The API does not make verified decisions. It only adds a candidate relation
generator:

```text
Memory / Evidence / Query
  -> LLM Provider
  -> GraphProposal
  -> Harness Review
  -> accept / reject / quarantine
  -> candidate Graph Edge
```

Raw data is stored in [`raw_results.json`](raw_results.json).

## Configuration Gate

Default behavior is disabled:

```text
MEMORYWEAVER_ENABLE_LLM_GRAPH_PROPOSAL=false
```

With no API key, the SDK and tests still run. With an API key and the flag
enabled, providers may generate `GraphProposal` objects only. They must not
write graph edges, verified memory, or stable Patterns directly.

## Procedure

```powershell
python benchmarks\llm_graph_proposal_validation.py `
  --iterations 100 `
  --output docs\validation\llm-graph-proposal-v0.4\raw_results.json
python -m pytest -q
```

The benchmark uses the offline local provider, so no network or real API key is
required.

## Results

| Arm | Recall@10 | Candidate Reduction | p95 ms | Proposal Precision | Wrong Link Rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| manual graph | 1.00 | 0.96 | 0.059 | n/a | n/a |
| rule graph | 1.00 | 0.96 | 0.079 | n/a | n/a |
| llm proposal graph | 1.00 | 0.96 | 0.048 | 1.00 | 0.00 |

## Review Policy

The `GraphProposalReviewPolicy` enforces:

- assistant / LLM proposal confidence is capped at `0.6`
- missing evidence link remains `pending`
- conflicting relation is rejected
- low-risk tag/alias proposal with evidence can be accepted
- high fan-out proposal requires review / quarantine

## Interpretation

The provider framework is safe by default:

- no API key is required
- LLM proposal generation is disabled unless explicitly enabled
- provider output is limited to `GraphProposal`
- `ReviewedGraphLinker` is the only path from accepted proposal to candidate edge
- Layer 3 lifecycle remains unchanged

This benchmark does not prove real LLM proposal quality. It proves the SDK
boundary: API integration adds a candidate relation generator, not a final
memory or routing authority.
