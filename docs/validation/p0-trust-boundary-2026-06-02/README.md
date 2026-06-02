# P0 Trust-Boundary Validation Report

## Abstract

This batch validates the Sprint 0.1 P0 fixes for MemoryWeaver's trust boundary
and lifecycle signals. The experiment was run on 2026-06-02 with five
independent microbenchmark trials. Raw observations, environment metadata,
pytest output, and aggregate statistics are preserved in
[raw_results.json](./raw_results.json).

The tested P0 boundary is closed:

- assistant-authored memories are downgraded to ambiguous with confidence at
  most `0.3`;
- synthetic memories cannot enter verified retrieval;
- tag retrieval applies the same source gate as text retrieval;
- archived and deprecated memories are excluded from verified retrieval;
- Router decisions use verified candidates;
- ordinary edits and lifecycle transitions do not fabricate heat;
- explicit access still increases heat;
- verified terminal patterns can still trigger the fast route.

The batch does not claim that the whole prototype is complete. The missing CLI
module and weak Chinese reordered-query recall remain open work.

## Scope

### P0 hypotheses

| ID | Hypothesis | Acceptance criterion |
| --- | --- | --- |
| H1 | Ordinary edits do not fabricate usage | `plain_update_heat == 0` |
| H2 | Lifecycle transitions do not fabricate usage | `lifecycle_transition_heat == 0` |
| H3 | Explicit access remains measurable | `explicit_access_heat == 1` |
| H4 | Tag retrieval blocks unverified assistant memory | `tag_search_returns_unverified_assistant == false` |
| H5 | Assistant positive writes cannot become verified facts | `assistant_positive_is_accepted == false` |
| H6 | Router blocks unverified assistant patterns | route is `thinking` |
| H7 | Router preserves the verified fast path | verified terminal route is `fast` |

### Out-of-scope observations

| Observation | Result | Follow-up |
| --- | --- | --- |
| `memoryweaver.cli` exists | `false` | Add CLI skeleton in Sprint 0.1 |
| Reordered Chinese query recall | `0` matches | Add tokenizer or character n-gram baseline |

## Method

Run:

```powershell
python .\scripts\collect_p0_validation.py `
  --output .\docs\validation\p0-trust-boundary-2026-06-02\raw_results.json `
  --trials 5 `
  --items 100 500 1000 `
  --query-iterations 200
```

The collector:

1. runs the full pytest suite;
2. executes correctness probes once per trial;
3. benchmarks JSON-backed stores at `100`, `500`, and `1000` items;
4. records all raw trials;
5. calculates mean, sample standard deviation, minimum, and maximum.

## Environment

| Field | Value |
| --- | --- |
| Python | `3.14.0` |
| Platform | `Windows-11-10.0.26200-SP0` |
| Machine | `AMD64` |
| CPU | `Intel64 Family 6 Model 165 Stepping 2, GenuineIntel` |
| Logical CPUs | `16` |
| Base Git revision | `f8daf43f382740398c64089ac3902dc1ad3d744d` |

The raw artifact also records the dirty worktree at collection time so the
experiment can be traced to the exact uncommitted patch under evaluation.

## Correctness Results

All five trials produced the same probe results:

| Probe | Before fix | After fix | P0 status |
| --- | ---: | ---: | --- |
| Plain update heat | `1` | `0` | Closed |
| Lifecycle transition heat | Not measured | `0` | Closed |
| Explicit access heat | Not measured | `1` | Closed |
| Tag search returns unverified assistant | `true` | `false` | Closed |
| Assistant positive write accepted | `true` | `false` | Closed |
| Assistant positive write result | Verified-like positive | `ambiguous`, confidence `0.3` | Closed |
| Router route from unverified assistant Pattern | `fast` | `thinking` | Closed |
| Router route from verified terminal Pattern | Not measured | `fast` | Closed |

The regression suite passed:

```text
79 passed
```

## Performance Results

Values below are means across five independent trials. Parentheses contain the
sample standard deviation.

| Items | Write items/s | Reload ms | Tag p95 ms | Verified tag p95 ms | Similar p95 ms | Verified text p95 ms |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 100 | 296.26 (11.46) | 10.14 (1.16) | 0.109 (0.037) | 0.103 (0.021) | 0.216 (0.027) | 0.378 (0.088) |
| 500 | 78.20 (2.79) | 23.55 (18.25) | 0.567 (0.067) | 0.609 (0.074) | 1.177 (0.080) | 1.644 (0.103) |
| 1,000 | 40.93 (0.67) | 34.25 (17.38) | 1.057 (0.057) | 1.249 (0.284) | 2.500 (0.160) | 3.396 (0.396) |

Interpretation:

- the verified gates add measurable but small overhead at prototype scale;
- read latency remains low at `1,000` items;
- write throughput falls sharply with scale because each add rewrites the
  complete JSON file;
- reload measurements include visible trial-to-trial variance at `500` and
  `1,000` items; raw samples are retained rather than smoothed;
- this is a local microbenchmark, not a production capacity claim.

## Evidence Map

| Requirement | Evidence |
| --- | --- |
| Source enum and safe downgrade | `memoryweaver/schema.py`, schema regression tests |
| Synthetic exclusion | `memoryweaver/retriever.py`, retriever regression test |
| Tag gate | `memoryweaver/retriever.py`, retriever regression tests, raw probes |
| Router gate | `memoryweaver/router.py`, Router regression tests, raw probes |
| Heat separation | `memoryweaver/schema.py`, `memoryweaver/store.py`, `memoryweaver/scorer.py`, lifecycle tests |
| Repeatability | five identical correctness-probe trials in `raw_results.json` |

## Limitations

- No LLM inference is exercised by this P0 batch.
- No concurrency, crash recovery, or long-running soak test is included.
- The JSON store remains intentionally simple.
- CLI and Chinese recall are open follow-up items.
- Long-term model comparisons require the separate experiment protocol in
  [../llm-memory-experiment-protocol.md](../llm-memory-experiment-protocol.md).
