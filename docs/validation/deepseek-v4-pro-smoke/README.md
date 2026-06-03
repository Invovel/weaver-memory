# DeepSeek v4 Pro GraphProposal Smoke

## Purpose

This smoke test verifies that `.env` can enable the DeepSeek provider and that
`deepseek-v4-pro` is used only as a low-privilege `GraphProposal` generator.

No API key is recorded in this report.

## Required `.env`

```text
MEMORYWEAVER_LLM_PROVIDER=deepseek
MEMORYWEAVER_LLM_MODEL=deepseek-v4-pro
MEMORYWEAVER_ENABLE_LLM_GRAPH_PROPOSAL=true
DEEPSEEK_API_KEY=...
```

The default `.env.example` still keeps LLM graph proposal disabled.

## Smoke Result

The DeepSeek provider returned one proposal for:

```text
query: codex org problem
tags: codex_subscription_failed, selected_organization
```

Observed behavior:

- provider available: `true`
- model: `deepseek-v4-pro`
- proposal count: `1`
- proposal source: `llm`
- proposal status: `pending`
- requires review: `true`
- review decision without EvidenceLink: `pending`
- review reason: `missing evidence link`
- graph edge written: `false`

## Local vs DeepSeek Comparison

| Provider | Proposal Count | Example Reason | Confidence | Review Decision |
| --- | ---: | --- | ---: | --- |
| local | 1 | Local provider linked the first two supplied tags. | 0.52 | pending |
| deepseek-v4-pro | 1 | Both tags appear in related memories where selected organization resolved the subscription issue. | 0.00-0.60 observed | pending |

Interpretation:

- DeepSeek produced a more semantic explanation than the deterministic local provider.
- The provider output still did not bypass review.
- Missing evidence kept the proposal pending.
- The test supports the intended boundary: API integration adds a candidate
  relation generator, not graph authority.
