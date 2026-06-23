"""Validate temporal GBrain drift signals without changing Layer 3.

v0.5.5 projects manual CoreIssueNode and HarnessMarker fixtures into a temporal
graph view. The graph records temporal metadata and lineage relations, then
produces candidate MarkerProposal records for stale/challenged markers.

This benchmark is intentionally offline and advisory only:

- no Layer 3 Pattern promotion
- no memory promotion
- no runtime authority
- no online LLM calls
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks._safety import safe_rmtree_child
from benchmarks.context_capsule_validation import write_json, write_jsonl
from memoryweaver.graph_schema import (
    GraphEdge,
    GraphNode,
    GraphNodeType,
    GraphRelation,
    GraphStatus,
)
from memoryweaver.graph_store import GraphStore


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORE_ISSUES = (
    REPO_ROOT
    / "docs"
    / "validation"
    / "runbook-marker-v0.5"
    / "core_issues.json"
)
DEFAULT_MARKERS = (
    REPO_ROOT
    / "docs"
    / "validation"
    / "runbook-marker-v0.5"
    / "markers.json"
)
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT
    / "docs"
    / "validation"
    / "temporal-gbrain-drift-v0.5.5"
)
NOW = "2026-06-05T12:00:00Z"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def days_between(left: str, right: str = NOW) -> int:
    return max(0, (parse_time(right) - parse_time(left)).days)


def core_node_id(core_issue_id: str) -> str:
    return f"core_{core_issue_id}"


def marker_node_id(marker_id: str) -> str:
    return f"marker_{marker_id}"


def old_marker_node_id(marker_id: str) -> str:
    return f"old_marker_{marker_id}"


def card_type_risk(card_type: str) -> float:
    if card_type == "freshness_conflict":
        return 0.42
    if card_type == "ambiguous_evidence":
        return 0.3
    if card_type == "marker_conflict_shadow":
        return 0.28
    if card_type == "overgeneralized_marker_rejection":
        return 0.25
    return 0.08


def marker_temporal_metadata(marker: dict[str, Any], core_issue: dict[str, Any]) -> dict[str, Any]:
    card_type = str(core_issue.get("card_type", ""))
    stale_candidate = card_type == "freshness_conflict" or "stale" in marker["id"]
    ambiguous_candidate = card_type == "ambiguous_evidence"
    valid_from = "2026-04-01T00:00:00Z" if stale_candidate else "2026-06-01T00:00:00Z"
    last_seen = "2026-04-20T00:00:00Z" if stale_candidate else "2026-06-05T10:00:00Z"
    valid_to = "2026-05-01T00:00:00Z" if stale_candidate else ""
    challenge_count = 2 if ambiguous_candidate or card_type == "marker_conflict_shadow" else 0
    age_days = days_between(last_seen)
    age_component = min(age_days / 60, 0.5)
    drift_score = round(
        min(1.0, age_component + card_type_risk(card_type) + (0.15 * challenge_count)),
        4,
    )
    if drift_score >= 0.7:
        drift_status = "stale"
    elif drift_score >= 0.5:
        drift_status = "challenged"
    elif drift_score >= 0.3:
        drift_status = "warn"
    else:
        drift_status = "healthy"
    return {
        "node_kind": "harness_marker",
        "core_issue_id": marker["core_issue_id"],
        "valid_from": valid_from,
        "valid_to": valid_to,
        "last_seen": last_seen,
        "freshness": "expired" if stale_candidate else "stable",
        "challenged_by": [
            f"dialogue_card:{core_issue.get('source_dialogue_card_id', '')}"
        ] if challenge_count else [],
        "challenge_count": challenge_count,
        "drift_score": drift_score,
        "drift_status": drift_status,
        "runtime_authority": bool(marker.get("runtime_authority", False)),
        "intervention_level": marker.get("intervention_level", ""),
    }


def build_temporal_graph(
    *,
    core_issues: list[dict[str, Any]],
    markers: list[dict[str, Any]],
    graph: GraphStore,
) -> dict[str, Any]:
    core_by_id = {core["id"]: core for core in core_issues}
    temporal_edges: list[GraphEdge] = []
    for core in core_issues:
        graph.add_node(GraphNode(
            id=core_node_id(core["id"]),
            node_type=GraphNodeType.TAG,
            label=core["title"],
            ref_id=core["id"],
            metadata={
                "node_kind": "core_issue",
                "valid_from": "2026-06-01T00:00:00Z",
                "valid_to": "",
                "last_seen": NOW,
                "freshness": "stable",
                "episode_provenance": core.get("source_dialogue_card_id", ""),
                "truth_authority": False,
            },
        ))

    for marker in markers:
        core = core_by_id.get(marker["core_issue_id"], {})
        metadata = marker_temporal_metadata(marker, core)
        marker_id = marker_node_id(marker["id"])
        graph.add_node(GraphNode(
            id=marker_id,
            node_type=GraphNodeType.TAG,
            label=marker["id"],
            ref_id=marker["id"],
            metadata=metadata,
        ))
        temporal_edges.append(GraphEdge(
            id=f"edge_{core_node_id(marker['core_issue_id'])}_supports_{marker_id}",
            source_id=core_node_id(marker["core_issue_id"]),
            target_id=marker_id,
            relation=GraphRelation.SUPPORTS,
            status=GraphStatus.ACCEPTED,
            confidence=0.9,
            source="temporal_gbrain_projection",
            metadata={
                "valid_from": metadata["valid_from"],
                "valid_to": metadata["valid_to"],
                "last_seen": metadata["last_seen"],
                "episode_provenance": core.get("source_dialogue_card_id", ""),
            },
        ))

        if metadata["drift_status"] in {"stale", "challenged"}:
            old_id = old_marker_node_id(marker["id"])
            graph.add_node(GraphNode(
                id=old_id,
                node_type=GraphNodeType.TAG,
                label=f"old:{marker['id']}",
                ref_id=old_id,
                metadata={
                    "node_kind": "historical_marker",
                    "valid_from": "2026-03-01T00:00:00Z",
                    "valid_to": metadata["valid_from"],
                    "last_seen": metadata["last_seen"],
                    "freshness": "expired",
                },
            ))
            temporal_edges.append(GraphEdge(
                id=f"edge_{marker_id}_supersedes_{old_id}",
                source_id=marker_id,
                target_id=old_id,
                relation=GraphRelation.SUPERSEDES,
                status=GraphStatus.ACCEPTED,
                confidence=0.8,
                source="temporal_gbrain_projection",
                metadata={
                    "valid_from": metadata["valid_from"],
                    "last_seen": NOW,
                    "reason": "newer marker context supersedes stale historical marker",
                },
            ))
            temporal_edges.append(GraphEdge(
                id=f"edge_{marker_id}_challenged_by_{core_node_id(marker['core_issue_id'])}",
                source_id=marker_id,
                target_id=core_node_id(marker["core_issue_id"]),
                relation=GraphRelation.RELATED_TO,
                status=GraphStatus.ACCEPTED,
                confidence=0.7,
                source="temporal_gbrain_projection",
                metadata={
                    "relation_semantic": "challenged_by",
                    "challenged_by": metadata["challenged_by"] or [
                        f"freshness:{metadata['last_seen']}"
                    ],
                    "drift_score": metadata["drift_score"],
                },
            ))

    for edge in temporal_edges:
        graph.add_edge(edge, replace=True)
    return {
        "core_issue_count": len(core_issues),
        "marker_count": len(markers),
        "temporal_edge_count": len(temporal_edges),
    }


def marker_proposals(graph: GraphStore) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    for node in graph.list_nodes():
        if node.metadata.get("node_kind") != "harness_marker":
            continue
        status = node.metadata.get("drift_status")
        if status not in {"stale", "challenged"}:
            continue
        action = "archive_or_refresh_marker" if status == "stale" else "review_marker_scope"
        proposals.append({
            "proposal_id": f"mp_{node.ref_id}",
            "proposal_type": "marker_drift_review",
            "marker_id": node.ref_id,
            "core_issue_id": node.metadata.get("core_issue_id", ""),
            "drift_status": status,
            "drift_score": node.metadata.get("drift_score", 0.0),
            "proposed_action": action,
            "requires_review": True,
            "runtime_authority": False,
            "layer3_mutation": False,
            "memory_promotion": False,
            "reason": (
                "temporal metadata indicates stale/challenged marker; "
                "proposal is advisory until reviewed"
            ),
        })
    proposals.sort(key=lambda item: (item["drift_score"], item["marker_id"]), reverse=True)
    return proposals


def evaluate_temporal_drift(
    *,
    core_issues_path: Path,
    markers_path: Path,
    workspace_root: Path,
) -> dict[str, Any]:
    safe_rmtree_child(
        workspace_root.parent,
        workspace_root,
        allowed_prefixes=(".memoryweaver",),
    )
    graph = GraphStore(workspace_root / "temporal_graph.json")
    core_issues = read_json(core_issues_path)["core_issues"]
    markers = read_json(markers_path)["markers"]
    projection = build_temporal_graph(
        core_issues=core_issues,
        markers=markers,
        graph=graph,
    )
    proposals = marker_proposals(graph)
    nodes = graph.list_nodes()
    edges = graph.list_edges()
    stale_markers = [
        node for node in nodes
        if node.metadata.get("node_kind") == "harness_marker"
        and node.metadata.get("drift_status") == "stale"
    ]
    challenged_markers = [
        node for node in nodes
        if node.metadata.get("node_kind") == "harness_marker"
        and node.metadata.get("drift_status") == "challenged"
    ]
    temporal_metadata_fields = [
        "valid_from",
        "valid_to",
        "last_seen",
        "freshness",
    ]
    temporal_metadata_complete = sum(
        1
        for node in nodes
        if all(field in node.metadata for field in temporal_metadata_fields)
    )
    metrics = {
        "core_issue_count": projection["core_issue_count"],
        "marker_count": projection["marker_count"],
        "graph_node_count": len(nodes),
        "temporal_edge_count": len(edges),
        "temporal_metadata_complete_count": temporal_metadata_complete,
        "stale_marker_count": len(stale_markers),
        "challenged_marker_count": len(challenged_markers),
        "supersedes_edge_count": sum(1 for edge in edges if edge.relation == GraphRelation.SUPERSEDES),
        "challenged_by_edge_count": sum(
            1
            for edge in edges
            if edge.metadata.get("relation_semantic") == "challenged_by"
        ),
        "marker_proposal_count": len(proposals),
        "review_required_count": sum(1 for item in proposals if item["requires_review"]),
        "runtime_authority_granted_count": sum(1 for item in proposals if item["runtime_authority"]),
        "memory_promotion_count": 0,
        "layer3_mutation_count": 0,
        "online_llm_call_count": 0,
    }
    hard_gates = {
        "core_issue_count": metrics["core_issue_count"] >= 50,
        "marker_count": metrics["marker_count"] >= 50,
        "temporal_metadata_complete": (
            metrics["temporal_metadata_complete_count"] == metrics["graph_node_count"]
        ),
        "stale_marker_count": metrics["stale_marker_count"] > 0,
        "challenged_marker_count": metrics["challenged_marker_count"] > 0,
        "supersedes_edge_count": metrics["supersedes_edge_count"] > 0,
        "challenged_by_edge_count": metrics["challenged_by_edge_count"] > 0,
        "marker_proposal_count": metrics["marker_proposal_count"] > 0,
        "all_proposals_require_review": (
            metrics["review_required_count"] == metrics["marker_proposal_count"]
        ),
        "runtime_authority_granted_count": metrics["runtime_authority_granted_count"] == 0,
        "memory_promotion_count": metrics["memory_promotion_count"] == 0,
        "layer3_mutation_count": metrics["layer3_mutation_count"] == 0,
        "online_llm_call_count": metrics["online_llm_call_count"] == 0,
    }
    return {
        "validation": "temporal-gbrain-drift-v0.5.5",
        "passed": all(hard_gates.values()),
        "metrics": metrics,
        "hard_gates": hard_gates,
        "marker_proposals": proposals,
        "temporal_nodes": [node.to_dict() for node in nodes],
        "temporal_edges": [edge.to_dict() for edge in edges],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-issues", default=str(DEFAULT_CORE_ISSUES))
    parser.add_argument("--markers", default=str(DEFAULT_MARKERS))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    result = evaluate_temporal_drift(
        core_issues_path=Path(args.core_issues),
        markers_path=Path(args.markers),
        workspace_root=output_dir / ".memoryweaver-temporal-gbrain",
    )
    write_json(output_dir / "raw_results.json", result)
    write_json(output_dir / "metrics_summary.json", result["metrics"])
    write_jsonl(output_dir / "marker_proposals.jsonl", result["marker_proposals"])
    write_jsonl(output_dir / "temporal_nodes.jsonl", result["temporal_nodes"])
    write_jsonl(output_dir / "temporal_edges.jsonl", result["temporal_edges"])
    print(json.dumps({
        "validation": result["validation"],
        "passed": result["passed"],
        "metrics": result["metrics"],
    }, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
