# PathoFlow Database-Driven Localization Notes

This note answers a narrower question: if we treat the available manifests,
chain records, and structured validation artifacts as the operational data
plane, what do they tell us about where PathoFlow breaks?

## Available Local Data Sources

In this local copy, there is no committed production runtime SQLite database
snapshot. However, we do have database-like evidence sources:

- `execution_manifest.json` files emitted by tool execution
- `tool_execution_records.jsonl`
- `chain_matrix.json`
- `sequential_chains.json`
- `planner_records.jsonl`
- `pathoflow_structured_outputs.jsonl`
- `case_records.jsonl`

These are sufficient to localize the current failures at the planner,
artifact-contract, and execution-output layers.

## What The Recorded Data Proves

### 1. Planner is choosing the wrong flow family

Source:
- [planner_records.jsonl](./planner_records.jsonl)

Observed:
- Representative lung QC / TME / IHC queries all map to
  `wish_14_intrahepatic_cholangiocarcinoma_cancer_detection`.

Localization:
- Failure is in the planner scoring/ranking layer, before execution.

### 2. Overlay tools reach execution but emit no artifacts

Sources:
- [tool_execution_records.jsonl](./tool_execution_records.jsonl)
- [sequential_chains.json](./sequential_chains.json)

Observed:
- `59-generate-overlays` reaches `success=true`
- manifest state is `completed_no_output`
- `file_count=0`

Localization:
- Failure is downstream of preflight and invocation construction.
- The tool runner or demo asset packaging is the likely fault domain.

### 3. Upstream/downstream artifact contracts are inconsistent

Source:
- [chain_matrix.json](./chain_matrix.json)

Observed:
- Detection-to-overlay chain is rejected because the produced mask is PNG-like
  while downstream overlay requires `.tif/.tiff`.

Localization:
- Failure is in declared artifact contract/schema alignment, not planning.

### 4. Some executable tools are not represented in reviewed flow registry

Sources:
- [README.md](./README.md)
- local benchmark inspection notes

Observed:
- `4-nucleus-segmentation-hovernet-pannuke` executes in demo mode
- but does not participate as a reviewed flow in the registry

Localization:
- Failure is in registry coverage and planner/executor parity.

### 5. LLM contract is weaker than transport compatibility

Sources:
- [openai_compat_ask_result.json](./openai_compat_ask_result.json)
- [gpt54_responses_ask_result.json](./gpt54_responses_ask_result.json)

Observed:
- live ask can return a useful answer
- but response is free-form text, not strict JSON

Localization:
- Failure is in output contract enforcement / parsing, not in provider
  connectivity anymore.

## Practical Reading Of The Current Data Plane

If we treat the manifests and JSONL reports as the "database", the failure
ordering is:

1. Planner rank chooses the wrong disease/tool family.
2. Even when the right tool is forced, some downstream tools report success
   with zero files.
3. Some cross-step edges fail schema/preflight before execution.
4. Live LLM output, when available, still fails the strict structured contract.

## Best Next Data To Collect

If a real runtime database becomes available later, the most valuable tables or
records to inspect are:

- scheduler job rows and events for real execution transitions
- auth/session archive records for real frontend ask/ask_stream traces
- persisted execution manifests across many tools, not only demo probes
- user feedback / low-score clusters tied to toolchain ids

But based on the current local artifact set, the framework root causes are
already sharply localized enough to prioritize fixes.
