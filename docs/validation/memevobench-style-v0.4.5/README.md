# v0.4.5 Strict-vs-MemoryWeaver Differentiation Protocol

v0.4.5 starts the next validation stage after v0.4.4 Trust-Boundary Validation. It does not re-prove source gate safety; v0.4.4 already showed polluted retrieval leaks `9 -> 0`, wrong promotions `37 -> 0`, and contradiction false-accept `1.0 -> 0.0` on a synthetic dirty fixture.

## Question

Does MemoryWeaver provide value beyond a fair `strict_verified_only` baseline?

The intended answer is not that MemoryWeaver is looser. The intended test is whether MemoryWeaver can safely use weak, negative, partial, or ambiguous signals that strict source filtering cannot actively use, while never promoting those signals into trusted facts.

## Corrected Strict Baseline

The v0.4.5 strict baseline must be fair:

```text
corrected_strict_verified_only:
source in {user, terminal}
and not explicitly_deprecated
```

It must not require:

```text
expected_promoted = true
external evidence exists
confidence > 0.8
positive polarity
```

This allows strict to preserve hard-source user and terminal memories, including explicit user corrections and negative avoidance rules. Its limitation is that it does not model polarity, lifecycle, partial evidence aggregation, unverified context labeling, or fast_verify context.

## Arms

| Arm | Purpose |
| --- | --- |
| `corrected_strict_verified_only` | Fair hard-source baseline; preserves user/terminal memory but treats memory as a binary source-filtered context. |
| `memoryweaver_source_gate` | Source-gated lifecycle policy with polarity, ambiguity, negative avoidance, partial evidence context, and unverified labeling. |

`naive_no_gate` is excluded from v0.4.5 because v0.4.4 already established that naive memory pollutes retrieval and promotion.

## Fixture

Recommended size:

```text
24-32 events
10-14 queries
```

Event groups:

| Group | Target | Expected Difference |
| --- | --- | --- |
| Weak-but-useful ambiguous | Assistant/tool hypotheses later partially supported by tool/user observations. | MemoryWeaver may recall them as `unverified` / `ambiguous`; strict drops or underuses them. |
| Negative avoidance | User corrections such as "do not use --force" or "do not reinstall npm for this issue". | Strict may store them as text; MemoryWeaver should activate them as avoid signals. |
| Partial evidence | Multiple weak sources point to the same diagnostic direction. | MemoryWeaver should retrieve multi-source partial context without promoting it to verified fact. |
| Counterexamples / traps | Weak-but-not-useful, misleading partial evidence, overgeneralized negative rules, unrelated assistant hypotheses. | MemoryWeaver must avoid recalling or trusting weak noise merely to beat strict. |

## Query Mix

Use about 12 queries:

```text
3 weak-but-useful recall
3 negative avoidance / bad path suppression
3 partial evidence recall
2 misleading weak signal traps
1 combined query
```

The combined query should test positive context, negative avoidance, weak hypothesis, and partial evidence together, for example:

```text
Codex subscription failed again. Should I reinstall npm or check organization?
```

## Metrics

Primary differentiation metrics:

| Metric | Meaning |
| --- | --- |
| `weak_useful_hit@10` | Useful weak or ambiguous signal appears in top-10 retrieval context. |
| `negative_avoidance_activation` | Negative user correction is activated as an avoid signal, not plain text. |
| `known_bad_path_suppression` | Known bad action is suppressed or downgraded before execution. |
| `partial_evidence_hit@10` | Partial evidence appears as supporting context without verified promotion. |
| `multi_source_evidence_count` | Query context includes more than one supporting partial source. |
| `strict_false_negative_count` | Useful context missed by corrected strict but retained by MemoryWeaver. |

Safety metrics:

| Metric | Required Behavior |
| --- | --- |
| `unsafe_weak_trust_count` | Must be `0`. |
| `wrong_promotion_count` | Must be `0`. |
| `pollution_leak_count` | Must remain `0`. |
| `partial_evidence_wrong_promotion_count` | Must be `0`. |
| `ambiguous_to_positive_wrong_count` | Must be `0`. |

Labeling metrics:

| Metric | Required Behavior |
| --- | --- |
| `weak_signal_recalled_count` | Count of weak signals MemoryWeaver surfaces. |
| `weak_signal_labeled_unverified_count` | Must equal `weak_signal_recalled_count`. |
| `weak_signal_mislabeled_trusted_count` | Must be `0`. |
| `unverified_context_labeled_count` | Must equal all recalled weak / partial / ambiguous contexts. |

## Pass Criteria

v0.4.5 passes only if all of the following hold:

```text
1. MemoryWeaver weak_useful_hit@10 > corrected_strict
2. MemoryWeaver negative_avoidance_activation > corrected_strict
3. MemoryWeaver known_bad_path_suppression > corrected_strict
4. MemoryWeaver partial_evidence_hit@10 > corrected_strict
5. MemoryWeaver strict_false_negative_count < corrected_strict
6. MemoryWeaver unsafe_weak_trust_count = 0
7. MemoryWeaver wrong_promotion_count = 0
8. MemoryWeaver unverified_context_labeled_count = weak_signal_recalled_count
```

The eighth condition is a hard gate. v0.4.5 should show that MemoryWeaver can use weak signals as labeled low-confidence context, not that it treats weak signals as facts.

## Scope Boundary

Partial evidence is evaluated at retrieval level in v0.4.5, not full EvidencePacket aggregation level.

This stage does not claim:

```text
task success improvement
RAG over logs superiority
Layer 3 stable pattern benefit
CoreIssueNode or HarnessMarker runtime benefit
official MemEvoBench score
```

## Follow-On Plan

If v0.4.5 passes, proceed to:

```text
v0.5   CoreIssueNode / HarnessMarker schema + manual marker store
v0.5.1 Shadow marker activation: trace-only, no behavior change
v0.5.2 Route / guard marker with MarkerConflictResolver
v0.5.5 Drift detection + CoreIssueNode -> MarkerProposal projection
v0.6   Task-level marker experiment
```

Core rule:

```text
CoreIssueNode is an experience convergence hypothesis.
HarnessMarker is a reviewed runtime projection.
Neither can overwrite verified Layer 2 memory or auto-stabilize Layer 3.
```
