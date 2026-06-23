# Docs Guide

This folder is organized around the current active architecture, implementation
plan, and validation story.

## Start Here

- [architecture.md](./architecture.md) - current system boundary and what is or is not implemented
- [development_plan.md](./development_plan.md) - active stage, priorities, and sequencing
- [risk_assessment_and_benchmark.md](./risk_assessment_and_benchmark.md) - current risks, measured baseline, safety closure TODOs, and benchmark gates
- [life_harness_notes.md](./life_harness_notes.md) - lifecycle harness boundary and intervention points

## Active Design Docs

- [gbrain_graph_memory.md](./gbrain_graph_memory.md) - current GBrain boundary and deferred v0.8 direction
- [rag_evidence_layer.md](./rag_evidence_layer.md) - evidence-layer design boundary
- [react_agent_runtime.md](./react_agent_runtime.md) - runtime, checkpoint, and loop design
- [langgraph_trace_to_path.md](./langgraph_trace_to_path.md) - v0.8 direction for combining LangGraph substrate with evidence-gated trace-to-path promotion
- [reference_mapping.md](./reference_mapping.md) - external systems and papers mapped to the correct MemoryWeaver layer
- [related_work_positioning.md](./related_work_positioning.md) - paper-friendly comparison of adjacent systems and MemoryWeaver's added layer
- [claim_metric_mapping.md](./claim_metric_mapping.md) - claim to metric to benchmark to artifact mapping for the current stage
- [collaborative_specialist_routing.md](./collaborative_specialist_routing.md) - staged specialist routing plan
- [bad_case_learning_loop.md](./bad_case_learning_loop.md) - bad-case capture and regression direction
- [testing_resilience_strategy.md](./testing_resilience_strategy.md) - resilience and failure-mode test matrix
- [agent_test_catalog.md](./agent_test_catalog.md) - broader agent test inventory
- [open_source_strategy_options.md](./open_source_strategy_options.md) - external design ideas worth borrowing carefully

## Validation Artifacts

- [validation/](./validation/) - benchmark outputs, raw results, and reproducible validation batches
- [validation/harness-runtime-trace-loop/README.md](./validation/harness-runtime-trace-loop/README.md) - trace-seeded candidate-path runtime reuse and rollback loop
- [validation/harness-runtime-live-llm/README.md](./validation/harness-runtime-live-llm/README.md) - real `--llm` live-agent proposal bridge for runtime-path promotion
- [validation/harness-runtime-coding-debug/README.md](./validation/harness-runtime-coding-debug/README.md) - real pytest and diff evidence for coding-debug runtime path promotion
- [validation/claim-snapshot.md](./validation/claim-snapshot.md) - auto-generated current-stage claim summary from validation artifacts
- [validation/current-stage-check/README.md](./validation/current-stage-check/README.md) - fixed daily stage review workflow

## Archived Planning Docs

Historical plans, exploratory analyses, and superseded drafts now live under
[archive/](./archive/README.md). They remain useful for context, but they are
not the primary source of truth for the current v0.7 path-promotion stage.
