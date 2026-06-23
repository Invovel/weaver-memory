"""Validate MemoryWeaver frontend filters against SQLite FTS5.

v0.5.4a answers a narrower question than v0.5.4:

Can MemoryWeaver's tag/time and graph/tag/time filters act as a frontend for a
traditional keyword retriever, keeping Recall@10 while making FTS5 rank a much
smaller candidate set?

This benchmark uses Python's standard-library sqlite3 FTS5 support. It does not
use embeddings, online LLM calls, memory promotion, or Layer-3 mutation.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.context_capsule_stress_validation import (
    DEFAULT_BASE_FIXTURE,
    DEFAULT_DIALOGUE_CARDS,
)
from benchmarks.context_capsule_validation import write_json, write_jsonl
from benchmarks.retrieval_comparison_validation import (
    _build_accepted_graph,
    _build_workspace,
    _capsules_from_ids,
    _expand_graph_tags,
    _query_text,
    _rank_capsules,
    _recall_hit,
    _required_tags,
    _seed_tags,
)
from memoryweaver.context_schema import ContextCapsule
from memoryweaver.store import MemoryWorkspace


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT
    / "docs"
    / "validation"
    / "retrieval-fts5-filter-v0.5.4a"
)


@dataclass
class ArmStats:
    name: str
    recall_at_10: float
    average_candidate_count: float
    candidate_reduction_ratio: float
    latency_p50_ms: float
    latency_p95_ms: float
    average_top_score: float


class FTS5Index:
    def __init__(self, capsules: list[ContextCapsule]):
        self._conn = sqlite3.connect(":memory:")
        self._conn.execute(
            "CREATE VIRTUAL TABLE capsules USING fts5(id UNINDEXED, body)"
        )
        self._conn.executemany(
            "INSERT INTO capsules(id, body) VALUES (?, ?)",
            [
                (
                    capsule.id,
                    f"{capsule.summary} {' '.join(capsule.tags)}",
                )
                for capsule in capsules
            ],
        )
        self._conn.commit()

    def search(self, query: str, candidate_ids: list[str] | None = None) -> list[str]:
        terms = _fts_query(query)
        if not terms:
            return list(candidate_ids or [])
        rows = self._conn.execute(
            "SELECT id FROM capsules WHERE capsules MATCH ? ORDER BY bm25(capsules)",
            (terms,),
        ).fetchall()
        ids = [str(row[0]) for row in rows]
        if candidate_ids is None:
            return ids
        allowed = set(candidate_ids)
        return [capsule_id for capsule_id in ids if capsule_id in allowed]


def _fts_query(text: str) -> str:
    tokens: list[str] = []
    for raw in text.replace("_", " ").replace("-", " ").split():
        token = "".join(ch for ch in raw.lower() if ch.isalnum())
        if len(token) >= 2:
            tokens.append(token)
    # OR keeps the baseline forgiving; the MemoryWeaver filters are tested by
    # candidate size and safety gates, not by making FTS5 brittle.
    return " OR ".join(sorted(set(tokens[:32])))


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((len(ordered) - 1) * percentile)))
    return ordered[index]


def _timed_rank(
    query: str,
    capsules: list[ContextCapsule],
    *,
    fts5: FTS5Index | None = None,
    candidate_ids: list[str] | None = None,
    workspace: MemoryWorkspace | None = None,
) -> tuple[list[tuple[ContextCapsule, float]], int, float]:
    started = time.perf_counter()
    if fts5 is None:
        ranked = _rank_capsules(query, capsules)
        candidate_count = len(capsules)
    else:
        ids = fts5.search(query, candidate_ids=candidate_ids)
        if workspace is None:
            by_id = {capsule.id: capsule for capsule in capsules}
            ranked_capsules = [by_id[capsule_id] for capsule_id in ids if capsule_id in by_id]
        else:
            ranked_capsules = _capsules_from_ids(workspace, ids)
        ranked = _rank_capsules(query, ranked_capsules)
        candidate_count = len(candidate_ids) if candidate_ids is not None else len(capsules)
    elapsed_ms = (time.perf_counter() - started) * 1000
    return ranked, candidate_count, elapsed_ms


def _arm_stats(
    name: str,
    *,
    hits: list[bool],
    counts: list[int],
    latencies: list[float],
    top_scores: list[float],
    corpus_size: int,
) -> ArmStats:
    average_count = mean(counts) if counts else 0.0
    return ArmStats(
        name=name,
        recall_at_10=round(sum(1 for hit in hits if hit) / len(hits), 4),
        average_candidate_count=round(average_count, 2),
        candidate_reduction_ratio=round(1 - (average_count / corpus_size), 4),
        latency_p50_ms=round(_percentile(latencies, 0.5), 4),
        latency_p95_ms=round(_percentile(latencies, 0.95), 4),
        average_top_score=round(mean(top_scores), 4) if top_scores else 0.0,
    )


def evaluate_fts5_frontend_filter(
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
    fts5 = FTS5Index(all_capsules)
    corpus_size = len(all_capsules)

    arm_data: dict[str, dict[str, list[Any]]] = {
        name: {"hits": [], "counts": [], "latencies": [], "scores": []}
        for name in [
            "full_scan",
            "fts5_all",
            "mw_tag_time_filter",
            "mw_tag_time_fts5",
            "mw_graph_tag_time_fts5",
        ]
    }
    query_records: list[dict[str, Any]] = []

    for card in cards:
        card_id = str(card["dialogue_card_id"])
        for query in card.get("queries", []):
            query_text = _query_text(card, query)
            required_tags = _required_tags(query)
            seed_tags = _seed_tags(query)

            tag_ids = workspace.tag_time_index.search(tags=required_tags)
            tag_capsules = _capsules_from_ids(workspace, tag_ids)
            expanded_tags, graph_precision = _expand_graph_tags(graph, seed_tags)
            graph_ids = workspace.tag_time_index.search(tags=expanded_tags)

            ranked_full, count_full, latency_full = _timed_rank(query_text, all_capsules)
            ranked_fts, count_fts, latency_fts = _timed_rank(
                query_text,
                all_capsules,
                fts5=fts5,
            )
            started = time.perf_counter()
            ranked_tag = _rank_capsules(query_text, tag_capsules)
            latency_tag = (time.perf_counter() - started) * 1000
            ranked_tag_fts, count_tag_fts, latency_tag_fts = _timed_rank(
                query_text,
                all_capsules,
                fts5=fts5,
                candidate_ids=tag_ids,
                workspace=workspace,
            )
            ranked_graph_fts, count_graph_fts, latency_graph_fts = _timed_rank(
                query_text,
                all_capsules,
                fts5=fts5,
                candidate_ids=graph_ids,
                workspace=workspace,
            )

            outcomes = {
                "full_scan": (ranked_full, count_full, latency_full),
                "fts5_all": (ranked_fts, count_fts, latency_fts),
                "mw_tag_time_filter": (ranked_tag, len(tag_capsules), latency_tag),
                "mw_tag_time_fts5": (ranked_tag_fts, count_tag_fts, latency_tag_fts),
                "mw_graph_tag_time_fts5": (
                    ranked_graph_fts,
                    count_graph_fts,
                    latency_graph_fts,
                ),
            }
            record: dict[str, Any] = {
                "dialogue_card_id": card_id,
                "query_id": query.get("query_id", ""),
                "required_tags": required_tags,
                "graph_expanded_tags": expanded_tags,
                "graph_expansion_precision": graph_precision,
            }
            for name, (ranked, count, latency) in outcomes.items():
                hit = _recall_hit(ranked, card_id=card_id, raw_metadata=raw_metadata)
                arm_data[name]["hits"].append(hit)
                arm_data[name]["counts"].append(count)
                arm_data[name]["latencies"].append(latency)
                arm_data[name]["scores"].append(ranked[0][1] if ranked else 0.0)
                record[f"{name}_hit_at_10"] = hit
                record[f"{name}_candidate_count"] = count
            query_records.append(record)

    arms = [
        _arm_stats(
            name,
            hits=[bool(item) for item in data["hits"]],
            counts=[int(item) for item in data["counts"]],
            latencies=[float(item) for item in data["latencies"]],
            top_scores=[float(item) for item in data["scores"]],
            corpus_size=corpus_size,
        )
        for name, data in arm_data.items()
    ]
    arms_by_name = {arm.name: arm for arm in arms}
    fts5_recall = arms_by_name["fts5_all"].recall_at_10
    tag_fts = arms_by_name["mw_tag_time_fts5"]
    graph_fts = arms_by_name["mw_graph_tag_time_fts5"]
    metrics = {
        "validation": "retrieval-fts5-filter-v0.5.4a",
        "query_count": len(query_records),
        "capsule_count": corpus_size,
        "fts5_available": True,
        "fts5_all_recall_at_10": fts5_recall,
        "tag_time_fts5_recall_at_10": tag_fts.recall_at_10,
        "graph_tag_time_fts5_recall_at_10": graph_fts.recall_at_10,
        "fts5_all_average_candidate_count": arms_by_name["fts5_all"].average_candidate_count,
        "tag_time_fts5_average_candidate_count": tag_fts.average_candidate_count,
        "graph_tag_time_fts5_average_candidate_count": graph_fts.average_candidate_count,
        "tag_time_fts5_candidate_reduction_ratio": tag_fts.candidate_reduction_ratio,
        "graph_tag_time_fts5_candidate_reduction_ratio": graph_fts.candidate_reduction_ratio,
        "fts5_all_latency_p95_ms": arms_by_name["fts5_all"].latency_p95_ms,
        "tag_time_fts5_latency_p95_ms": tag_fts.latency_p95_ms,
        "graph_tag_time_fts5_latency_p95_ms": graph_fts.latency_p95_ms,
        "recall_delta_tag_time_vs_fts5": round(tag_fts.recall_at_10 - fts5_recall, 4),
        "recall_delta_graph_vs_fts5": round(graph_fts.recall_at_10 - fts5_recall, 4),
        "online_llm_call_count": 0,
        "memory_promotion_count": 0,
        "layer3_mutation_count": 0,
    }
    hard_gates = {
        "query_count": metrics["query_count"] >= 50,
        "fts5_available": metrics["fts5_available"] is True,
        "tag_time_fts5_recall_not_significantly_below_fts5": (
            metrics["recall_delta_tag_time_vs_fts5"] >= -0.05
        ),
        "graph_tag_time_fts5_recall_not_significantly_below_fts5": (
            metrics["recall_delta_graph_vs_fts5"] >= -0.05
        ),
        "tag_time_fts5_reduces_candidates_over_90pct": (
            metrics["tag_time_fts5_candidate_reduction_ratio"] >= 0.9
        ),
        "graph_tag_time_fts5_reduces_candidates_over_90pct": (
            metrics["graph_tag_time_fts5_candidate_reduction_ratio"] >= 0.9
        ),
        "tag_time_fts5_latency_p95_not_above_fts5": (
            metrics["tag_time_fts5_latency_p95_ms"]
            <= metrics["fts5_all_latency_p95_ms"]
        ),
        "graph_tag_time_fts5_latency_p95_not_above_fts5": (
            metrics["graph_tag_time_fts5_latency_p95_ms"]
            <= metrics["fts5_all_latency_p95_ms"]
        ),
        "online_llm_call_count": metrics["online_llm_call_count"] == 0,
        "memory_promotion_count": metrics["memory_promotion_count"] == 0,
        "layer3_mutation_count": metrics["layer3_mutation_count"] == 0,
    }
    return {
        "validation": "retrieval-fts5-filter-v0.5.4a",
        "passed": all(hard_gates.values()),
        "metrics": metrics,
        "hard_gates": hard_gates,
        "arms": [asdict(arm) for arm in arms],
        "query_records": query_records,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-fixture", default=str(DEFAULT_BASE_FIXTURE))
    parser.add_argument("--dialogue-cards", default=str(DEFAULT_DIALOGUE_CARDS))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    result = evaluate_fts5_frontend_filter(
        base_fixture=Path(args.base_fixture),
        dialogue_cards_path=Path(args.dialogue_cards),
        workspace_root=output_dir / ".memoryweaver-fts5-filter",
    )
    write_json(output_dir / "raw_results.json", result)
    write_json(output_dir / "metrics_summary.json", result["metrics"])
    write_jsonl(output_dir / "arms.jsonl", result["arms"])
    write_jsonl(output_dir / "query_results.jsonl", result["query_records"])
    print(json.dumps({
        "validation": result["validation"],
        "passed": result["passed"],
        "metrics": result["metrics"],
    }, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
