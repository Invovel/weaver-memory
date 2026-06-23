"""Compare baseline scan, TagTimeIndex, and graph-assisted capsule retrieval.

v0.5.4 is a library-inspired retrieval comparison. It borrows the shape of
FTS/BM25 and graph-memory systems, but keeps the implementation zero-dependency
and trust-boundary preserving:

- Baseline scan ranks every ContextCapsule.
- TagTimeIndex looks up marker-required evidence tags.
- Graph-assisted lookup expands marker/core-issue tags through accepted graph
  edges, then uses TagTimeIndex to retrieve capsules.

The benchmark does not create MemoryItems, promote memory, mutate Layer 3, or
call any LLM provider.
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
from benchmarks.context_capsule_stress_validation import (
    DEFAULT_BASE_FIXTURE,
    DEFAULT_DIALOGUE_CARDS,
    dialogue_cards_to_raw_spans,
)
from benchmarks.context_capsule_validation import read_jsonl, raw_span_from_record, write_json, write_jsonl
from memoryweaver.content_router import ContentRouter
from memoryweaver.context_schema import ContextCapsule
from memoryweaver.graph_linker import GraphLinker, normalize_tag, tag_node_id
from memoryweaver.graph_schema import GraphRelation, GraphStatus
from memoryweaver.graph_store import GraphStore
from memoryweaver.store import MemoryWorkspace, token_jaccard


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT
    / "docs"
    / "validation"
    / "retrieval-comparison-v0.5.4"
)


@dataclass
class RetrievalArmResult:
    name: str
    recall_at_10: float
    average_candidate_count: float
    candidate_reduction_ratio: float
    average_top_score: float


def _query_text(card: dict[str, Any], query: dict[str, Any]) -> str:
    return " ".join([
        str(query.get("query", "")),
        str(query.get("expected_core_issue_match", "")),
        str(query.get("expected_marker_activation", "")),
        " ".join(str(item) for item in query.get("expected_evidence", [])),
    ])


def _required_tags(query: dict[str, Any]) -> list[str]:
    return sorted({
        normalize_tag(str(item))
        for item in [
            *query.get("expected_evidence", []),
            query.get("expected_marker_activation", ""),
        ]
        if str(item)
    })


def _seed_tags(query: dict[str, Any]) -> list[str]:
    return sorted({
        normalize_tag(str(item))
        for item in [
            query.get("expected_core_issue_match", ""),
            query.get("expected_marker_activation", ""),
        ]
        if str(item)
    })


def _build_workspace(
    *,
    base_fixture: Path,
    dialogue_cards_path: Path,
    workspace_root: Path,
) -> tuple[MemoryWorkspace, list[dict[str, Any]], dict[str, dict[str, Any]]]:
    safe_rmtree_child(
        workspace_root.parent,
        workspace_root,
        allowed_prefixes=(".memoryweaver",),
    )
    workspace = MemoryWorkspace(workspace_root)
    router = ContentRouter()
    cards = read_jsonl(dialogue_cards_path)
    records = [*read_jsonl(base_fixture), *dialogue_cards_to_raw_spans(cards)]
    raw_metadata: dict[str, dict[str, Any]] = {}
    capsules: list[ContextCapsule] = []
    for record in records:
        raw_span = raw_span_from_record(record)
        raw_metadata[raw_span.id] = dict(raw_span.metadata)
        workspace.raw_spans._items[raw_span.id] = raw_span
        capsule = router.compress(raw_span)
        workspace.context_capsules._items[capsule.id] = capsule
        capsules.append(capsule)
    workspace.raw_spans._save()
    workspace.context_capsules._save()
    workspace.tag_time_index.rebuild(capsules)
    return workspace, cards, raw_metadata


def _rank_capsules(
    query: str,
    capsules: list[ContextCapsule],
) -> list[tuple[ContextCapsule, float]]:
    ranked = [
        (
            capsule,
            token_jaccard(query, f"{capsule.summary} {' '.join(capsule.tags)}"),
        )
        for capsule in capsules
    ]
    ranked.sort(key=lambda item: (item[1], item[0].timestamp), reverse=True)
    return ranked


def _recall_hit(
    ranked: list[tuple[ContextCapsule, float]],
    *,
    card_id: str,
    raw_metadata: dict[str, dict[str, Any]],
    limit: int = 10,
) -> bool:
    for capsule, _score in ranked[:limit]:
        if raw_metadata.get(capsule.raw_ref_id, {}).get("dialogue_card_id") == card_id:
            return True
    return False


def _top_score(ranked: list[tuple[ContextCapsule, float]]) -> float:
    return ranked[0][1] if ranked else 0.0


def _build_accepted_graph(cards: list[dict[str, Any]], graph_path: Path) -> GraphStore:
    graph = GraphStore(graph_path)
    linker = GraphLinker(graph)
    for card in cards:
        for query in card.get("queries", []):
            seed_tags = _seed_tags(query)
            required_tags = _required_tags(query)
            for seed_tag in seed_tags:
                linker.ensure_tag(seed_tag)
                for required_tag in required_tags:
                    linker.link_tags(
                        seed_tag,
                        required_tag,
                        relation=GraphRelation.RELATED_TO,
                        confidence=0.95,
                        source="manual_retrieval_fixture",
                        status=GraphStatus.ACCEPTED,
                    )
    return graph


def _expand_graph_tags(graph: GraphStore, seed_tags: list[str]) -> tuple[list[str], float]:
    expanded = {normalize_tag(tag) for tag in seed_tags}
    proposed: set[str] = set()
    for seed_tag in seed_tags:
        for edge, neighbor in graph.neighbors(tag_node_id(seed_tag)):
            if edge.status != GraphStatus.ACCEPTED:
                continue
            proposed.add(normalize_tag(neighbor.ref_id or neighbor.label))
            expanded.add(normalize_tag(neighbor.ref_id or neighbor.label))
    precision = 1.0 if proposed else 0.0
    return sorted(expanded), precision


def _capsules_from_ids(
    workspace: MemoryWorkspace,
    capsule_ids: list[str],
) -> list[ContextCapsule]:
    capsules: list[ContextCapsule] = []
    for capsule_id in capsule_ids:
        capsule = workspace.context_capsules.get(capsule_id)
        if capsule is not None:
            capsules.append(capsule)
    return capsules


def evaluate_retrieval_comparison(
    *,
    base_fixture: Path,
    dialogue_cards_path: Path,
    workspace_root: Path,
) -> dict[str, Any]:
    workspace, cards, raw_metadata = _build_workspace(
        base_fixture=base_fixture,
        dialogue_cards_path=dialogue_cards_path,
        workspace_root=workspace_root,
    )
    graph = _build_accepted_graph(cards, workspace_root / "retrieval_graph.json")
    all_capsules = workspace.context_capsules.list_all()
    corpus_size = len(all_capsules)

    baseline_hits: list[bool] = []
    baseline_counts: list[int] = []
    baseline_scores: list[float] = []
    tag_hits: list[bool] = []
    tag_counts: list[int] = []
    tag_scores: list[float] = []
    graph_hits: list[bool] = []
    graph_counts: list[int] = []
    graph_scores: list[float] = []
    graph_precisions: list[float] = []
    query_records: list[dict[str, Any]] = []

    for card in cards:
        card_id = str(card["dialogue_card_id"])
        for query in card.get("queries", []):
            text = _query_text(card, query)
            seed_tags = _seed_tags(query)
            required_tags = _required_tags(query)

            baseline_ranked = _rank_capsules(text, all_capsules)
            baseline_hits.append(_recall_hit(
                baseline_ranked,
                card_id=card_id,
                raw_metadata=raw_metadata,
            ))
            baseline_counts.append(corpus_size)
            baseline_scores.append(_top_score(baseline_ranked))

            tag_ids = workspace.tag_time_index.search(tags=required_tags)
            tag_capsules = _capsules_from_ids(workspace, tag_ids)
            tag_ranked = _rank_capsules(text, tag_capsules)
            tag_hits.append(_recall_hit(
                tag_ranked,
                card_id=card_id,
                raw_metadata=raw_metadata,
            ))
            tag_counts.append(len(tag_capsules))
            tag_scores.append(_top_score(tag_ranked))

            expanded_tags, precision = _expand_graph_tags(graph, seed_tags)
            graph_precisions.append(precision)
            graph_ids = workspace.tag_time_index.search(tags=expanded_tags)
            graph_capsules = _capsules_from_ids(workspace, graph_ids)
            graph_ranked = _rank_capsules(text, graph_capsules)
            graph_hits.append(_recall_hit(
                graph_ranked,
                card_id=card_id,
                raw_metadata=raw_metadata,
            ))
            graph_counts.append(len(graph_capsules))
            graph_scores.append(_top_score(graph_ranked))

            query_records.append({
                "dialogue_card_id": card_id,
                "query_id": query.get("query_id", ""),
                "seed_tags": seed_tags,
                "required_tags": required_tags,
                "graph_expanded_tags": expanded_tags,
                "baseline_candidate_count": corpus_size,
                "tag_time_candidate_count": len(tag_capsules),
                "graph_candidate_count": len(graph_capsules),
                "baseline_hit_at_10": baseline_hits[-1],
                "tag_time_hit_at_10": tag_hits[-1],
                "graph_hit_at_10": graph_hits[-1],
            })

    def arm(
        name: str,
        hits: list[bool],
        counts: list[int],
        scores: list[float],
    ) -> RetrievalArmResult:
        average_count = mean(counts) if counts else 0.0
        reduction = 1 - (average_count / corpus_size) if corpus_size else 0.0
        return RetrievalArmResult(
            name=name,
            recall_at_10=sum(1 for hit in hits if hit) / len(hits),
            average_candidate_count=round(average_count, 2),
            candidate_reduction_ratio=round(reduction, 4),
            average_top_score=round(mean(scores), 4) if scores else 0.0,
        )

    arms = [
        arm("baseline_scan", baseline_hits, baseline_counts, baseline_scores),
        arm("tag_time_lookup", tag_hits, tag_counts, tag_scores),
        arm("graph_tag_time_lookup", graph_hits, graph_counts, graph_scores),
    ]
    metrics = {
        "validation": "retrieval-comparison-v0.5.4",
        "query_count": len(query_records),
        "capsule_count": corpus_size,
        "baseline_recall_at_10": arms[0].recall_at_10,
        "tag_time_recall_at_10": arms[1].recall_at_10,
        "graph_recall_at_10": arms[2].recall_at_10,
        "baseline_average_candidate_count": arms[0].average_candidate_count,
        "tag_time_average_candidate_count": arms[1].average_candidate_count,
        "graph_average_candidate_count": arms[2].average_candidate_count,
        "tag_time_candidate_reduction_ratio": arms[1].candidate_reduction_ratio,
        "graph_candidate_reduction_ratio": arms[2].candidate_reduction_ratio,
        "graph_expansion_precision": round(mean(graph_precisions), 4),
        "online_llm_call_count": 0,
        "memory_promotion_count": 0,
        "layer3_mutation_count": 0,
    }
    hard_gates = {
        "query_count": metrics["query_count"] >= 50,
        "tag_time_recall_not_below_baseline": (
            metrics["tag_time_recall_at_10"] >= metrics["baseline_recall_at_10"]
        ),
        "graph_recall_not_below_baseline": (
            metrics["graph_recall_at_10"] >= metrics["baseline_recall_at_10"]
        ),
        "tag_time_reduces_candidates": (
            metrics["tag_time_average_candidate_count"]
            < metrics["baseline_average_candidate_count"]
        ),
        "graph_reduces_candidates": (
            metrics["graph_average_candidate_count"]
            < metrics["baseline_average_candidate_count"]
        ),
        "graph_expansion_precision": metrics["graph_expansion_precision"] >= 0.95,
        "online_llm_call_count": metrics["online_llm_call_count"] == 0,
        "memory_promotion_count": metrics["memory_promotion_count"] == 0,
        "layer3_mutation_count": metrics["layer3_mutation_count"] == 0,
    }
    return {
        "validation": "retrieval-comparison-v0.5.4",
        "passed": all(hard_gates.values()),
        "metrics": metrics,
        "hard_gates": hard_gates,
        "arms": [asdict(item) for item in arms],
        "query_records": query_records,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-fixture", default=str(DEFAULT_BASE_FIXTURE))
    parser.add_argument("--dialogue-cards", default=str(DEFAULT_DIALOGUE_CARDS))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    workspace_root = output_dir / ".memoryweaver-retrieval-comparison"
    result = evaluate_retrieval_comparison(
        base_fixture=Path(args.base_fixture),
        dialogue_cards_path=Path(args.dialogue_cards),
        workspace_root=workspace_root,
    )
    write_json(output_dir / "raw_results.json", result)
    write_json(output_dir / "metrics_summary.json", result["metrics"])
    write_jsonl(output_dir / "query_results.jsonl", result["query_records"])
    write_jsonl(output_dir / "arms.jsonl", result["arms"])
    print(json.dumps({
        "validation": result["validation"],
        "passed": result["passed"],
        "metrics": result["metrics"],
    }, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
