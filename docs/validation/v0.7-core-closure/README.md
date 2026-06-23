# v0.7 Core Closure

v0.7 changes the project direction from fragmented validation scripts to a
single functional MemoryWeaver core.

The implemented core surfaces are:

- `MemoryLifecycle`: verified memory write, evidence link, explicit Layer-2
  promotion, verified retrieval, conflict handling, provisional Layer-3
  Pattern composition, rollback, runtime marker context write, and GBrain sync.
- `GBrain`: advisory relation graph over tag / memory / evidence / pattern
  nodes, plus mind-map projection.
- `MemoryWeaverModule`: LongMemEval-V2 style context backend that converts
  external trajectories into RawSpan / ContextCapsule / candidate memory dry-run
  without verified memory writes by default.
- `MemoryWeaverLiveLoop`: tau-style per-step loop where an agent chooses actions
  from observation + MemoryWeaver runtime context, and environment observations
  can write verified memory.
- `mw` CLI entries: `external`, `gbrain`, `layer`, and `eval`.
- `external.lock.json`: reproducibility manifest for pinned local inputs.

## Smoke Results

### Layer / GBrain / Marker

Command:

```powershell
python -m memoryweaver.cli layer smoke --root docs\validation\v0.7-core-closure\.memoryweaver-layer --json
```

Result:

- passed: true
- verified memory writes: 2
- promotions: 2
- retrieval results: 2
- conflict handling count: 1
- Layer-3 mutation count: 1
- rollback count: 1
- runtime marker write count: 1
- known-bad path write count: 1
- mind-map nodes: 12
- mind-map edges: 13
- workspace validate: true
- workspace doctor: true

### Tau-Style Live Loop

Command:

```powershell
python -m memoryweaver.cli eval tau-smoke --root docs\validation\v0.7-core-closure\.memoryweaver-tau --json
```

Result:

- success: true
- step count: 1
- verified memory writes: 1
- promotions: 1
- online LLM calls: 0
- marker activated: true
- required evidence: selected organization + entitlement
- suppressed actions: reinstall npm + reset auth files

This is still a local mock environment, but the trajectory is not a prewritten
benchmark path: the agent policy chooses its action from runtime context.

### Tau-Style Live Loop With Real LLM

Command:

```powershell
python -m memoryweaver.cli eval tau-llm-smoke --root docs\validation\v0.7-core-closure\.memoryweaver-tau-llm --provider deepseek --model deepseek-chat --env-file .env --max-steps 5 --json
```

Result:

- success: true
- step count: 1
- online LLM calls: 1
- verified memory writes: 1
- promotions: 1
- selected action: `check_evidence`
- selected target: `selected_organization_and_entitlement`
- marker activated: true
- known-bad warnings present: reinstall npm + reset auth files

This is the first v0.7 smoke where action selection is performed by a real LLM
provider while MemoryWeaver handles runtime context and lifecycle writes.

### LongMemEval-V2 Context Backend

Command:

```powershell
python -m memoryweaver.cli external lme-v2-context --root docs\validation\v0.7-core-closure\.memoryweaver-lme --input-root D:\benchmarks\longmemeval-v2 --question-index 0 --trajectories-per-question 5 --states-per-trajectory 5 --json
```

Result:

- external question context produced
- RawSpan / ContextCapsule path used
- verified memory writes: 0
- promotions: 0
- Layer-3 mutations: 0

This confirms the v0.6.4 line remains the external-data ingestion lane, not the
memory-write lane.

### Mind Map

Command:

```powershell
python -m memoryweaver.cli gbrain mindmap --root docs\validation\v0.7-core-closure\.memoryweaver-layer --tag codex --tag subscription --json
```

Result:

- Layer-2 memory nodes present
- Evidence nodes present
- rolled-back Layer-3 Pattern node present
- tag nodes present
- lineage edges present

## Boundary

v0.7 does not claim official benchmark score parity yet. It implements the
functional substrate needed for those scores:

- external data can enter safely
- compressed context can be recovered through raw refs
- verified memory can be written and promoted
- unsafe assistant claims can be blocked by conflict policy
- Layer 3 remains PatternComposer controlled
- rollback is auditable
- GBrain and mind-map projection expose lineage
- runtime marker context can guide live-loop decisions

## Next Acceptance Target

The next step is not another small version. It is a single v0.7 hard-gate run
that combines:

- LongMemEval-V2 adapter coverage
- tau-style live-loop tasks
- memory lifecycle write / promote / rollback
- GBrain mind-map projection
- policy leak count
- evidence ref validity
- known-bad path detection

The critical gates remain:

- `evidence_ref_validity_rate >= 0.99`
- `unsupported_claim_rate <= 0.05`
- `policy_gate_leak_count = 0`
- `known_bad_path_detection_rate >= 0.70`
- `promotion_rollback_roundtrip_success_rate = 1.00`
