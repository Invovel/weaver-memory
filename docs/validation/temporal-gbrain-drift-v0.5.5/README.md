# Temporal GBrain Drift v0.5.5

## Purpose

This validation projects the v0.5 Runbook CoreIssueNode and HarnessMarker
fixtures into a lightweight temporal graph.

It validates the next Graphiti/Zep-inspired step:

```text
CoreIssueNode / HarnessMarker
  -> temporal metadata
  -> supersedes / challenged_by lineage
  -> candidate MarkerProposal
  -> review required
```

It does not change Layer 3, stabilize patterns, promote memory, grant runtime
authority, or call an LLM.

## Command

```powershell
python .\benchmarks\temporal_gbrain_drift_validation.py `
  --output-dir .\docs\validation\temporal-gbrain-drift-v0.5.5
```

## Gates

```text
core_issue_count >= 50
marker_count >= 50
all graph nodes have valid_from / valid_to / last_seen / freshness metadata
stale_marker_count > 0
challenged_marker_count > 0
supersedes_edge_count > 0
challenged_by_edge_count > 0
marker_proposal_count > 0
all proposals require review
runtime_authority_granted_count = 0
memory_promotion_count = 0
layer3_mutation_count = 0
online_llm_call_count = 0
```

## Observed Metrics

```json
{
  "core_issue_count": 50,
  "marker_count": 50,
  "graph_node_count": 113,
  "temporal_edge_count": 76,
  "temporal_metadata_complete_count": 113,
  "stale_marker_count": 6,
  "challenged_marker_count": 7,
  "supersedes_edge_count": 13,
  "challenged_by_edge_count": 13,
  "marker_proposal_count": 13,
  "review_required_count": 13,
  "runtime_authority_granted_count": 0,
  "memory_promotion_count": 0,
  "layer3_mutation_count": 0,
  "online_llm_call_count": 0
}
```

## Generated Artifacts

```text
raw_results.json
metrics_summary.json
marker_proposals.jsonl
temporal_nodes.jsonl
temporal_edges.jsonl
```

## Interpretation

This is a temporal graph substrate validation. It proves MemoryWeaver can detect
stale/challenged marker candidates and record lineage without letting the graph
become a truth maintainer or runtime authority.
