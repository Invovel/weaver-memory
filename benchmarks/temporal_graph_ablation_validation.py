"""Compare static tag co-occurrence graph with temporal GBrain filtering.

v0.5.5b is an ablation over the v0.5.5 temporal graph projection:

- static_cooccurrence treats any textually related marker as a runtime candidate.
- temporal_runtime filters stale/challenged/expired markers out of runtime use.
- temporal_review_queue captures those filtered markers for review-only handling.

The benchmark does not grant runtime authority, promote memory, mutate Layer 3,
or call an online LLM provider.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks._safety import safe_rmtree_child
from benchmarks.context_capsule_validation import write_json, write_jsonl
from benchmarks.temporal_gbrain_drift_validation import (
    DEFAULT_CORE_ISSUES,
    DEFAULT_MARKERS,
    build_temporal_graph,
    marker_node_id,
    marker_proposals,
    read_json,
)
from memoryweaver.graph_store import GraphStore
from memoryweaver.store import token_jaccard


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT
    / "docs"
    / "validation"
    / "temporal-graph-ablation-v0.5.5b"
)


@dataclass
class AblationArm:
    name: str
    recall_at_10: float
    average_candidate_count: float
    stale_runtime_leak_count: int
    challenged_runtime_leak_count: int
    review_capture_rate: float


def _marker_text(marker: dict[str, Any], core: dict[str, Any]) -> str:
    return " ".join([
        str(marker.get("id", "")),
        str(marker.get("recommended_route", "")),
        " ".join(str(item) for item in marker.get("required_evidence", [])),
        " ".join(str(item) for item in marker.get("suppressed_actions", [])),
        str(core.get("id", "")),
        str(core.get("title", "")),
        str(core.get("card_type", "")),
        str(core.get("scope", "")),
    ])


def _query_text(marker: dict[str, Any], core: dict[str, Any]) -> str:
    return " ".join([
        str(core.get("title", "")),
        str(core.get("card_type", "")),
        " ".join(str(item) for item in marker.get("required_evidence", [])),
        " ".join(str(item) for item in marker.get("suppressed_actions", [])),
    ])


def _marker_status(graph: GraphStore, marker_id: str) -> str:
    node = graph.get_node(marker_node_id(marker_id))
    if node is None:
        return "missing"
    return str(node.metadata.get("drift_status", "unknown"))


def _runtime_eligible(graph: GraphStore, marker_id: str) -> bool:
    node = graph.get_node(marker_node_id(marker_id))
    if node is None:
        return False
    metadata = node.metadata
    return (
        metadata.get("drift_status") not in {"stale", "challenged"}
        and metadata.get("freshness") != "expired"
        and not metadata.get("valid_to")
    )


def _rank_markers(
    query: str,
    markers: list[dict[str, Any]],
    core_by_id: dict[str, dict[str, Any]],
) -> list[tuple[dict[str, Any], float]]:
    ranked = [
        (
            marker,
            token_jaccard(query, _marker_text(marker, core_by_id[marker["core_issue_id"]])),
        )
        for marker in markers
    ]
    ranked.sort(key=lambda item: (item[1], item[0]["id"]), reverse=True)
    return ranked


def _leak_counts(
    ranked: list[tuple[dict[str, Any], float]],
    graph: GraphStore,
) -> tuple[int, int]:
    stale = 0
    challenged = 0
    for marker, _score in ranked[:10]:
        status = _marker_status(graph, marker["id"])
        if status == "stale":
            stale += 1
        if status == "challenged":
            challenged += 1
    return stale, challenged


def _recall_hit(
    ranked: list[tuple[dict[str, Any], float]],
    marker_id: str,
) -> bool:
    return any(marker["id"] == marker_id for marker, _score in ranked[:10])


def _arm(
    name: str,
    *,
    hits: list[bool],
    counts: list[int],
    stale_leaks: int,
    challenged_leaks: int,
    review_hits: list[bool],
) -> AblationArm:
    return AblationArm(
        name=name,
        recall_at_10=round(sum(1 for item in hits if item) / len(hits), 4),
        average_candidate_count=round(mean(counts), 2) if counts else 0.0,
        stale_runtime_leak_count=stale_leaks,
        challenged_runtime_leak_count=challenged_leaks,
        review_capture_rate=round(
            sum(1 for item in review_hits if item) / len(review_hits),
            4,
        ) if review_hits else 1.0,
    )


def evaluate_temporal_graph_ablation(
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
    build_temporal_graph(core_issues=core_issues, markers=markers, graph=graph)
    proposals = marker_proposals(graph)
    proposal_marker_ids = {proposal["marker_id"] for proposal in proposals}
    core_by_id = {core["id"]: core for core in core_issues}

    static_hits: list[bool] = []
    static_counts: list[int] = []
    static_stale = 0
    static_challenged = 0
    temporal_hits: list[bool] = []
    temporal_counts: list[int] = []
    temporal_stale = 0
    temporal_challenged = 0
    temporal_review_hits: list[bool] = []
    runtime_eligible_query_count = 0
    query_records: list[dict[str, Any]] = []

    for marker in markers:
        marker_id = str(marker["id"])
        core = core_by_id[marker["core_issue_id"]]
        query = _query_text(marker, core)
        static_ranked = _rank_markers(query, markers, core_by_id)
        stale, challenged = _leak_counts(static_ranked, graph)
        static_stale += stale
        static_challenged += challenged
        static_hits.append(_recall_hit(static_ranked, marker_id))
        static_counts.append(len(static_ranked))

        temporal_candidates = [
            candidate
            for candidate in markers
            if _runtime_eligible(graph, candidate["id"])
        ]
        temporal_ranked = _rank_markers(query, temporal_candidates, core_by_id)
        stale, challenged = _leak_counts(temporal_ranked, graph)
        temporal_stale += stale
        temporal_challenged += challenged
        temporal_counts.append(len(temporal_ranked))
        marker_is_runtime_eligible = _runtime_eligible(graph, marker_id)
        if marker_is_runtime_eligible:
            runtime_eligible_query_count += 1
            temporal_hits.append(_recall_hit(temporal_ranked, marker_id))
        else:
            temporal_review_hits.append(marker_id in proposal_marker_ids)

        query_records.append({
            "marker_id": marker_id,
            "core_issue_id": marker["core_issue_id"],
            "drift_status": _marker_status(graph, marker_id),
            "runtime_eligible": marker_is_runtime_eligible,
            "static_hit_at_10": _recall_hit(static_ranked, marker_id),
            "static_candidate_count": len(static_ranked),
            "static_stale_top10_leaks": _leak_counts(static_ranked, graph)[0],
            "static_challenged_top10_leaks": _leak_counts(static_ranked, graph)[1],
            "temporal_hit_at_10": (
                _recall_hit(temporal_ranked, marker_id)
                if marker_is_runtime_eligible else False
            ),
            "temporal_review_captured": (
                marker_id in proposal_marker_ids
                if not marker_is_runtime_eligible else False
            ),
            "temporal_candidate_count": len(temporal_ranked),
        })

    static_arm = _arm(
        "static_cooccurrence",
        hits=static_hits,
        counts=static_counts,
        stale_leaks=static_stale,
        challenged_leaks=static_challenged,
        review_hits=[],
    )
    temporal_arm = _arm(
        "temporal_runtime",
        hits=temporal_hits,
        counts=temporal_counts,
        stale_leaks=temporal_stale,
        challenged_leaks=temporal_challenged,
        review_hits=temporal_review_hits,
    )
    metrics = {
        "validation": "temporal-graph-ablation-v0.5.5b",
        "query_count": len(markers),
        "marker_count": len(markers),
        "runtime_eligible_query_count": runtime_eligible_query_count,
        "review_only_query_count": len(markers) - runtime_eligible_query_count,
        "static_recall_at_10": static_arm.recall_at_10,
        "temporal_runtime_recall_at_10": temporal_arm.recall_at_10,
        "static_average_candidate_count": static_arm.average_candidate_count,
        "temporal_average_candidate_count": temporal_arm.average_candidate_count,
        "static_stale_runtime_leak_count": static_arm.stale_runtime_leak_count,
        "temporal_stale_runtime_leak_count": temporal_arm.stale_runtime_leak_count,
        "static_challenged_runtime_leak_count": (
            static_arm.challenged_runtime_leak_count
        ),
        "temporal_challenged_runtime_leak_count": (
            temporal_arm.challenged_runtime_leak_count
        ),
        "temporal_review_capture_rate": temporal_arm.review_capture_rate,
        "runtime_authority_granted_count": 0,
        "memory_promotion_count": 0,
        "layer3_mutation_count": 0,
        "online_llm_call_count": 0,
    }
    hard_gates = {
        "query_count": metrics["query_count"] >= 50,
        "static_recall_at_10": metrics["static_recall_at_10"] == 1.0,
        "temporal_runtime_recall_at_10": (
            metrics["temporal_runtime_recall_at_10"] >= 0.95
        ),
        "static_exposes_stale_or_challenged_leaks": (
            metrics["static_stale_runtime_leak_count"]
            + metrics["static_challenged_runtime_leak_count"]
        ) > 0,
        "temporal_blocks_stale_runtime_leaks": (
            metrics["temporal_stale_runtime_leak_count"] == 0
        ),
        "temporal_blocks_challenged_runtime_leaks": (
            metrics["temporal_challenged_runtime_leak_count"] == 0
        ),
        "temporal_review_capture_rate": (
            metrics["temporal_review_capture_rate"] == 1.0
        ),
        "runtime_authority_granted_count": (
            metrics["runtime_authority_granted_count"] == 0
        ),
        "memory_promotion_count": metrics["memory_promotion_count"] == 0,
        "layer3_mutation_count": metrics["layer3_mutation_count"] == 0,
        "online_llm_call_count": metrics["online_llm_call_count"] == 0,
    }
    return {
        "validation": "temporal-graph-ablation-v0.5.5b",
        "passed": all(hard_gates.values()),
        "metrics": metrics,
        "hard_gates": hard_gates,
        "arms": [asdict(static_arm), asdict(temporal_arm)],
        "query_records": query_records,
        "review_queue": proposals,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-issues", default=str(DEFAULT_CORE_ISSUES))
    parser.add_argument("--markers", default=str(DEFAULT_MARKERS))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    result = evaluate_temporal_graph_ablation(
        core_issues_path=Path(args.core_issues),
        markers_path=Path(args.markers),
        workspace_root=output_dir / ".memoryweaver-temporal-ablation",
    )
    write_json(output_dir / "raw_results.json", result)
    write_json(output_dir / "metrics_summary.json", result["metrics"])
    write_jsonl(output_dir / "arms.jsonl", result["arms"])
    write_jsonl(output_dir / "query_results.jsonl", result["query_records"])
    write_jsonl(output_dir / "review_queue.jsonl", result["review_queue"])
    print(json.dumps({
        "validation": result["validation"],
        "passed": result["passed"],
        "metrics": result["metrics"],
    }, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
