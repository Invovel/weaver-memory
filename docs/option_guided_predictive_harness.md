# Option-Guided Predictive Harness

MemoryWeaver absorbs two practical interaction patterns:

1. Option-guided interaction: present bounded choices before acting.
2. Predictive input compression: predict likely user intent continuations, keep
   matched predictions as routing hints, and discard unmatched predictions.

Both are candidate-generation mechanisms. Neither grants verified memory,
stable Layer-3 path status, or runtime authority.

## Public References

This module intentionally follows public patterns rather than private product
internals:

- `anthropics/claude-code`: public Claude Code repository and SDK-facing agent
  interface patterns: <https://github.com/anthropics/claude-code>
- Claude Agent SDK concepts: structured prompts, `AskUserQuestion`-style user
  choice, permissions, hooks, and auditable tool boundaries:
  <https://docs.anthropic.com/en/docs/claude-code/sdk> and
  <https://docs.anthropic.com/en/docs/claude-code/hooks>
- DeepSeek API context caching: prefix reuse / cache-hit intuition. MemoryWeaver
  adapts this as predictive context compression, not as factual memory:
  <https://api-docs.deepseek.com/guides/kv_cache>

The module does not copy proprietary Claude or DeepSeek implementation code.

## Principle

```text
LLM proposes options.
User selects or corrects.
Harness judges execution authority.
Tool feedback supplies hard evidence.
MemoryWeaver promotes only after evidence gates.
```

## Flow

```text
User input
-> intent prediction candidates
-> Harness filters impossible or unsafe candidates
-> option set
-> user selection
-> ActionProposal
-> ActionGate
-> tool result
-> evidence packet
-> promote / weaken / discard / rollback
```

## OptionCandidate

`OptionCandidate` follows the practical "give choices before acting" pattern.
It is useful when user intent is ambiguous, side effects are possible, or the
agent can reasonably offer multiple bounded routes.

Required boundary:

- An option is not verified memory.
- An option is not a stable Layer-3 path.
- A selected option still needs the normal Harness and ActionGate path.
- High-risk options require confirmation.

Implemented fields:

- `option_id`
- `intent_guess`
- `action_plan`
- `risk`
- `required_evidence`
- `confirmation_required`
- `action_name`
- `target`
- `arguments`
- `source_reference`

## PredictionCandidate

`PredictionCandidate` follows the predictive-completion pattern:

```text
predict likely continuation
-> compare with actual user continuation
-> keep matched prediction as route_hint
-> discard unmatched prediction
```

Required boundary:

- Predictions are synthetic.
- Unmatched predictions are discarded.
- Matched predictions may compress context or route options.
- Predictions never become verified memory by themselves.

Implemented fields:

- `prediction_id`
- `predicted_intent`
- `predicted_next_request`
- `confidence`
- `cache_prefix`
- `matched`
- `retained_as`
- `source_reference`

## Module API

`memoryweaver.option_harness` provides:

- `OptionGuidedPredictiveHarness`
- `OptionCandidate`
- `OptionSet`
- `UserSelection`
- `OptionHarnessDecision`
- `PredictionCandidate`
- `PredictionReconciliation`
- `OptionHarnessMetrics`
- `normalize_option_set`
- `retain_prediction_if_matched`
- `prediction_cache_hit`
- `common_prefix_unit`

The selected option is exported as an ActionProposal-shaped payload. That
payload is still only a proposal; `ActionGate` remains the execution authority.

## Metrics To Add Later

- `option_acceptance_rate`
- `wrong_action_rate`
- `prediction_hit_rate`
- `prediction_discard_rate`
- `compression_ratio`
- `promotion_without_evidence_count`

## Scope

This is an interaction and routing layer, not a new memory authority. It should
be integrated only after the existing evidence-gated path promotion chain
remains stable.
