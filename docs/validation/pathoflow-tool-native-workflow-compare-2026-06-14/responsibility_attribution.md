# PathoFlow Responsibility Attribution

This note classifies the observed failures by likely cause type:

- implementation defect
- unclear layer ownership / boundary design
- multi-agent collaboration issue
- skill invocation / specialist routing issue

The goal is to avoid blaming "multi-agent" by default when the evidence points
to ordinary single-system defects.

## Overall Judgment

Most currently observed PathoFlow failures are **not** caused by multi-agent
coordination. They are primarily:

1. single-component implementation defects
2. planner / execution / registry boundary misalignment
3. artifact contract inconsistency

Only a small portion of the problem space resembles skill-routing or
specialist-escalation design, and even there the current evidence still points
more strongly to planner/rule design than to multi-agent collaboration.

## Attribution Table

| Issue | Primary Cause | Why |
| --- | --- | --- |
| Planner drift to wrong disease flow | `implementation defect` + `unclear layer ownership` | The offline planner ranking is making obviously wrong single-planner decisions. No multi-agent chain is involved. |
| Overlay success with zero files | `implementation defect` | The tool executor reaches a success state but emits no output artifacts. This is a tool/demo implementation problem. |
| Macenko success with zero files | `implementation defect` | Same as overlay: false-success with empty artifact set. |
| Detection PNG cannot feed overlay TIFF contract | `unclear layer ownership / boundary design` | Upstream producer and downstream preflight contract disagree on artifact format. This is an interface contract alignment problem between components. |
| Executable tool absent from reviewed flow registry | `unclear layer ownership / boundary design` | Registry curation and execution coverage are maintained as separate surfaces without parity enforcement. |
| LLM returns free text instead of strict JSON | `implementation defect` | Prompt contract / parser / retry policy are insufficient; not a multi-agent issue. |
| Need for manual hard routing to correct planner | `skill invocation / routing design` (secondary) | This points to routing policy weakness, but still within a single planner/router layer rather than a true multi-agent coordination failure. |

## Why This Is Not Primarily A Multi-Agent Problem

Observed system state:

- `OfflineFlowPlanner` alone can already choose the wrong disease family.
- `59-generate-overlays` alone can already return success with zero files.
- `52-Global-Macenko` alone can already return success with zero files.
- `tool_executor` sequential chains fail or degrade even without any specialist
  orchestration.

Therefore:

- Adding more agents would not fix the current dominant blockers.
- Specialist routing would only amplify confusion if the planner/execution
  contracts remain inconsistent.

## Where Skill / Specialist Design Might Matter Later

The following areas could become multi-agent or skill problems in a later
runtime architecture, but are not yet the main blockers here:

1. deciding when to escalate from fast planner to evidence-heavy planner
2. deciding when to call paper/toolchain specialists
3. deciding how to reconcile graph evidence vs RAG evidence vs live execution

Those are future routing concerns. The current failures appear *before* that
kind of collaboration would provide value.

## Practical Interpretation

Current PathoFlow behaves less like a "multi-agent system failing to
collaborate" and more like a layered system whose components do not yet agree
on:

- what should be planned
- what can actually be executed
- what file formats are handed off
- what counts as success

So the right fix order is:

1. repair single-tool false-success behavior
2. align artifact contracts
3. align reviewed registry with executable tool inventory
4. harden planner routing constraints
5. only then revisit higher-level specialist / skill routing
