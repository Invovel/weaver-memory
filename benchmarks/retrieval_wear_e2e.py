"""Retrieval Wear end-to-end benchmark.

The benchmark distinguishes static answer caching from reusable retrieval
paths. It reuses the existing dialogue-card/capsule fixture and evaluates three
rounds per task family:

1. first exploration;
2. semantic paraphrase;
3. evidence-version drift.

This is a controlled retrieval experiment. It measures actual candidate
inspection and wall-clock retrieval time, but it does not claim open-world RAG
quality or production latency.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean, pstdev
import sys
from time import perf_counter
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmarks._safety import safe_rmtree_child
from benchmarks.context_capsule_stress_validation import (
    DEFAULT_BASE_FIXTURE,
    DEFAULT_DIALOGUE_CARDS,
)
from benchmarks.context_capsule_validation import write_json, write_jsonl
from benchmarks.retrieval_comparison_validation import (
    _build_workspace,
    _capsules_from_ids,
    _query_text,
    _rank_capsules,
    _recall_hit,
    _required_tags,
)


DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "validation" / "retrieval-wear-e2e"
ARMS = (
    "no_memory",
    "answer_cache",
    "rag_only",
    "retrieval_path_memory",
    "memoryweaver",
)
GENERATED_ARTIFACTS = (
    "raw_results.json",
    "metrics.json",
    "arm_metrics.json",
    "task_runs.jsonl",
    "reliability.json",
    "claim_table.md",
    "README.md",
)


def _prepare_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in GENERATED_ARTIFACTS:
        artifact = output_dir / name
        if artifact.exists():
            artifact.unlink()
    for child in (".retrieval-wear-workspace", "reliability_runs"):
        safe_rmtree_child(
            output_dir,
            output_dir / child,
            allowed_prefixes=(".retrieval-wear-", "reliability_"),
        )


def _paraphrase(query: dict[str, Any]) -> str:
    core = str(query.get("expected_core_issue_match", "")).replace("_", " ")
    evidence = " ".join(
        str(item).replace("_", " ") for item in query.get("expected_evidence", [])
    )
    return f"Find current supporting evidence for {core}; verify {evidence}."


def _timed_full_scan(
    text: str,
    capsules: list[Any],
) -> tuple[list[tuple[Any, float]], float]:
    started = perf_counter()
    ranked = _rank_capsules(text, capsules)
    return ranked, (perf_counter() - started) * 1000


def _timed_path_lookup(
    workspace: Any,
    text: str,
    tags: list[str],
) -> tuple[list[tuple[Any, float]], float]:
    started = perf_counter()
    capsule_ids = workspace.tag_time_index.search(tags=tags)
    capsules = _capsules_from_ids(workspace, capsule_ids)
    ranked = _rank_capsules(text, capsules)
    return ranked, (perf_counter() - started) * 1000


def _round_record(
    *,
    arm: str,
    card_id: str,
    round_name: str,
    evidence_version: int,
    path_version: int | None,
    retrieval_mode: str,
    ranked: list[tuple[Any, float]],
    latency_ms: float,
    raw_metadata: dict[str, dict[str, Any]],
    cache_hit: bool = False,
    stale_reuse: bool = False,
    path_reused: bool = False,
    path_invalidated: bool = False,
    rollback_success: bool = False,
) -> dict[str, Any]:
    evidence_hit = (
        False
        if stale_reuse
        else _recall_hit(ranked, card_id=card_id, raw_metadata=raw_metadata)
    )
    return {
        "task_family": card_id,
        "arm": arm,
        "round": round_name,
        "evidence_version": evidence_version,
        "path_version": path_version,
        "retrieval_mode": retrieval_mode,
        "retrieval_call_count": 0 if cache_hit else 1,
        "candidate_count": 0 if cache_hit else len(ranked),
        "latency_ms": round(latency_ms, 6),
        "evidence_hit": evidence_hit,
        "cache_hit": cache_hit,
        "stale_reuse": stale_reuse,
        "path_reused": path_reused,
        "path_invalidated": path_invalidated,
        "rollback_success": rollback_success,
    }


def _evaluate_family(
    *,
    workspace: Any,
    card: dict[str, Any],
    all_capsules: list[Any],
    raw_metadata: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    query = card["queries"][0]
    card_id = str(card["dialogue_card_id"])
    original = _query_text(card, query)
    paraphrase = _paraphrase(query)
    tags = _required_tags(query)
    records: list[dict[str, Any]] = []

    for arm in ARMS:
        answer_cache: dict[str, int] = {}
        path_version: int | None = None

        ranked, latency = _timed_full_scan(original, all_capsules)
        answer_cache[original] = 1
        path_version = 1
        records.append(
            _round_record(
                arm=arm,
                card_id=card_id,
                round_name="initial",
                evidence_version=1,
                path_version=path_version,
                retrieval_mode="full_scan",
                ranked=ranked,
                latency_ms=latency,
                raw_metadata=raw_metadata,
            )
        )

        if arm in {"retrieval_path_memory", "memoryweaver"}:
            ranked, latency = _timed_path_lookup(workspace, paraphrase, tags)
            mode = "guarded_path_lookup" if arm == "memoryweaver" else "path_lookup"
            path_reused = True
        else:
            ranked, latency = _timed_full_scan(paraphrase, all_capsules)
            mode = "full_scan"
            path_reused = False
            if arm == "answer_cache":
                answer_cache[paraphrase] = 1
        records.append(
            _round_record(
                arm=arm,
                card_id=card_id,
                round_name="paraphrase",
                evidence_version=1,
                path_version=path_version,
                retrieval_mode=mode,
                ranked=ranked,
                latency_ms=latency,
                raw_metadata=raw_metadata,
                path_reused=path_reused,
            )
        )

        if arm == "answer_cache":
            cache_hit = original in answer_cache
            records.append(
                _round_record(
                    arm=arm,
                    card_id=card_id,
                    round_name="evidence_drift",
                    evidence_version=2,
                    path_version=1,
                    retrieval_mode="exact_answer_cache",
                    ranked=[],
                    latency_ms=0.0,
                    raw_metadata=raw_metadata,
                    cache_hit=cache_hit,
                    stale_reuse=cache_hit,
                )
            )
        elif arm == "retrieval_path_memory":
            ranked, latency = _timed_path_lookup(workspace, original, tags)
            records.append(
                _round_record(
                    arm=arm,
                    card_id=card_id,
                    round_name="evidence_drift",
                    evidence_version=2,
                    path_version=1,
                    retrieval_mode="blind_path_lookup",
                    ranked=ranked,
                    latency_ms=latency,
                    raw_metadata=raw_metadata,
                    stale_reuse=True,
                    path_reused=True,
                )
            )
        elif arm == "memoryweaver":
            path_invalidated = path_version != 2
            ranked, latency = _timed_full_scan(original, all_capsules)
            path_version = 2
            records.append(
                _round_record(
                    arm=arm,
                    card_id=card_id,
                    round_name="evidence_drift",
                    evidence_version=2,
                    path_version=path_version,
                    retrieval_mode="invalidated_then_full_scan",
                    ranked=ranked,
                    latency_ms=latency,
                    raw_metadata=raw_metadata,
                    path_invalidated=path_invalidated,
                    rollback_success=path_invalidated,
                )
            )
        else:
            ranked, latency = _timed_full_scan(original, all_capsules)
            records.append(
                _round_record(
                    arm=arm,
                    card_id=card_id,
                    round_name="evidence_drift",
                    evidence_version=2,
                    path_version=path_version,
                    retrieval_mode="full_scan",
                    ranked=ranked,
                    latency_ms=latency,
                    raw_metadata=raw_metadata,
                )
            )
    return records


def _rate(records: list[dict[str, Any]], key: str) -> float:
    return round(sum(1 for record in records if record[key]) / max(len(records), 1), 4)


def _arm_metrics(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    metrics: dict[str, dict[str, Any]] = {}
    for arm in ARMS:
        arm_records = [record for record in records if record["arm"] == arm]
        paraphrase_records = [
            record for record in arm_records if record["round"] == "paraphrase"
        ]
        drift_records = [
            record for record in arm_records if record["round"] == "evidence_drift"
        ]
        metrics[arm] = {
            "task_family_count": len({
                record["task_family"] for record in arm_records
            }),
            "round_count": len(arm_records),
            "evidence_hit_rate": _rate(arm_records, "evidence_hit"),
            "semantic_transfer_rate": _rate(paraphrase_records, "path_reused"),
            "stale_path_reuse_rate": _rate(drift_records, "stale_reuse"),
            "path_invalidation_rate": _rate(drift_records, "path_invalidated"),
            "rollback_success_rate": _rate(drift_records, "rollback_success"),
            "retrieval_call_count": sum(
                record["retrieval_call_count"] for record in arm_records
            ),
            "average_candidate_count": round(
                mean(record["candidate_count"] for record in arm_records), 4
            ),
            "total_candidates_inspected": sum(
                record["candidate_count"] for record in arm_records
            ),
            "average_retrieval_latency_ms": round(
                mean(record["latency_ms"] for record in arm_records), 6
            ),
        }
    return metrics


def _run_once(
    output_dir: Path,
    *,
    task_family_limit: int,
    base_fixture: Path,
    dialogue_cards_path: Path,
) -> dict[str, Any]:
    workspace, cards, raw_metadata = _build_workspace(
        base_fixture=base_fixture,
        dialogue_cards_path=dialogue_cards_path,
        workspace_root=output_dir / ".retrieval-wear-workspace",
    )
    selected_cards = cards[:task_family_limit]
    all_capsules = workspace.context_capsules.list_all()
    records = [
        record
        for card in selected_cards
        for record in _evaluate_family(
            workspace=workspace,
            card=card,
            all_capsules=all_capsules,
            raw_metadata=raw_metadata,
        )
    ]
    metrics = _arm_metrics(records)
    rag = metrics["rag_only"]
    cache = metrics["answer_cache"]
    path = metrics["retrieval_path_memory"]
    mw = metrics["memoryweaver"]
    passed = (
        len(selected_cards) == task_family_limit
        and mw["evidence_hit_rate"] == 1.0
        and mw["semantic_transfer_rate"] == 1.0
        and mw["stale_path_reuse_rate"] == 0.0
        and mw["rollback_success_rate"] == 1.0
        and cache["semantic_transfer_rate"] == 0.0
        and cache["stale_path_reuse_rate"] == 1.0
        and path["semantic_transfer_rate"] == 1.0
        and path["stale_path_reuse_rate"] == 1.0
        and mw["total_candidates_inspected"] < rag["total_candidates_inspected"]
    )
    result = {
        "passed": passed,
        "task_family_count": len(selected_cards),
        "capsule_count": len(all_capsules),
        "records": records,
        "arm_metrics": metrics,
    }
    safe_rmtree_child(
        output_dir,
        output_dir / ".retrieval-wear-workspace",
        allowed_prefixes=(".retrieval-wear-",),
    )
    return result


def _reliability(runs: list[dict[str, Any]]) -> dict[str, Any]:
    pass_values = [bool(run["passed"]) for run in runs]
    candidate_counts = [
        run["arm_metrics"]["memoryweaver"]["total_candidates_inspected"]
        for run in runs
    ]
    stale_rates = [
        run["arm_metrics"]["memoryweaver"]["stale_path_reuse_rate"]
        for run in runs
    ]
    return {
        "run_count": len(runs),
        "pass_at_1": pass_values[0] if pass_values else False,
        "pass_power_3": len(pass_values) >= 3 and all(pass_values[:3]),
        "memoryweaver_total_candidates_mean": round(mean(candidate_counts), 4),
        "memoryweaver_total_candidates_std": (
            round(pstdev(candidate_counts), 4) if len(candidate_counts) > 1 else 0.0
        ),
        "memoryweaver_stale_path_reuse_rate_mean": round(mean(stale_rates), 4),
    }


def _claim_table(result: dict[str, Any]) -> str:
    arms = result["arm_metrics"]
    mw = arms["memoryweaver"]
    rag = arms["rag_only"]
    return "\n".join(
        [
            "# Retrieval Wear Claim Table",
            "",
            "| Claim | Metric | Value | Artifact |",
            "| --- | --- | ---: | --- |",
            f"| Retrieval paths transfer across paraphrases | `semantic_transfer_rate` | {mw['semantic_transfer_rate']} | `task_runs.jsonl` |",
            f"| Governed paths avoid stale reuse after evidence drift | `stale_path_reuse_rate` | {mw['stale_path_reuse_rate']} | `task_runs.jsonl` |",
            f"| Evidence drift triggers successful invalidation and recovery | `rollback_success_rate` | {mw['rollback_success_rate']} | `task_runs.jsonl` |",
            f"| Retrieval Wear inspects fewer candidates than repeated RAG | `total_candidates_inspected_delta_vs_rag` | {mw['total_candidates_inspected'] - rag['total_candidates_inspected']} | `arm_metrics.json` |",
            f"| The controlled result repeats across three isolated runs | `pass_power_3` | {str(result['reliability']['pass_power_3']).lower()} | `reliability.json` |",
            "",
        ]
    )


def _readme(result: dict[str, Any]) -> str:
    lines = [
        "# Retrieval Wear End-to-End Benchmark",
        "",
        "Controlled evidence for loop-aware retrieval-path reuse.",
        "",
        f"- `passed` = {str(result['passed']).lower()}",
        f"- `pass^3` = {str(result['reliability']['pass_power_3']).lower()}",
        f"- `task_family_count` = {result['task_family_count']}",
        f"- `capsule_count` = {result['capsule_count']}",
        "",
        "## Arms",
        "",
        "| arm | evidence hit | semantic transfer | stale reuse | rollback | candidates inspected | retrieval calls |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm in ARMS:
        metric = result["arm_metrics"][arm]
        lines.append(
            f"| {arm} | {metric['evidence_hit_rate']} | "
            f"{metric['semantic_transfer_rate']} | {metric['stale_path_reuse_rate']} | "
            f"{metric['rollback_success_rate']} | "
            f"{metric['total_candidates_inspected']} | "
            f"{metric['retrieval_call_count']} |"
        )
    lines.extend(
        [
            "",
            "## Protocol",
            "",
            "Each task family runs three rounds: initial exploration, semantic paraphrase,",
            "and evidence-version drift. `answer_cache` uses exact query keys;",
            "`retrieval_path_memory` reuses a path without freshness authority;",
            "`memoryweaver` reuses the scoped path for paraphrases but invalidates it",
            "when the evidence version changes.",
            "",
            "## Claim Boundary",
            "",
            "This benchmark uses the repository's controlled 50-card / 341-capsule fixture.",
            "Candidate counts and retrieval latency come from executed local retrieval.",
            "Evidence-version drift is a controlled protocol signal, not a production",
            "document-index update. The result does not establish open-world RAG",
            "superiority, generation quality, or production latency.",
            "",
            "## Artifacts",
            "",
            "- `raw_results.json`",
            "- `metrics.json`",
            "- `arm_metrics.json`",
            "- `task_runs.jsonl`",
            "- `reliability.json`",
            "- `claim_table.md`",
            "",
        ]
    )
    return "\n".join(lines)


def run(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    task_family_limit: int = 50,
    reliability_passes: int = 3,
    base_fixture: Path = DEFAULT_BASE_FIXTURE,
    dialogue_cards_path: Path = DEFAULT_DIALOGUE_CARDS,
) -> dict[str, Any]:
    _prepare_output_dir(output_dir)
    primary = _run_once(
        output_dir,
        task_family_limit=task_family_limit,
        base_fixture=base_fixture,
        dialogue_cards_path=dialogue_cards_path,
    )
    reliability_runs = []
    for index in range(1, max(reliability_passes, 1) + 1):
        pass_dir = output_dir / "reliability_runs" / f"retrieval-wear-pass-{index:03d}"
        pass_dir.mkdir(parents=True, exist_ok=True)
        reliability_runs.append(
            _run_once(
                pass_dir,
                task_family_limit=task_family_limit,
                base_fixture=base_fixture,
                dialogue_cards_path=dialogue_cards_path,
            )
        )
    reliability = _reliability(reliability_runs)
    passed = primary["passed"] and reliability["pass_power_3"]
    result = {
        "passed": passed,
        "research_question": (
            "Can a governed retrieval path transfer across paraphrases, inspect fewer "
            "candidates than repeated RAG, and avoid stale reuse after evidence drift?"
        ),
        "task_family_count": primary["task_family_count"],
        "capsule_count": primary["capsule_count"],
        "arms": list(ARMS),
        "arm_metrics": primary["arm_metrics"],
        "reliability": reliability,
        "task_runs": primary["records"],
    }
    write_json(output_dir / "raw_results.json", result)
    write_json(output_dir / "metrics.json", {
        "research_question": result["research_question"],
        "task_family_count": result["task_family_count"],
        "capsule_count": result["capsule_count"],
        "reliability": reliability,
    })
    write_json(output_dir / "arm_metrics.json", result["arm_metrics"])
    write_jsonl(output_dir / "task_runs.jsonl", result["task_runs"])
    write_json(output_dir / "reliability.json", reliability)
    (output_dir / "claim_table.md").write_text(_claim_table(result), encoding="utf-8")
    (output_dir / "README.md").write_text(_readme(result), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--task-family-limit", type=int, default=50)
    parser.add_argument("--reliability-passes", type=int, default=3)
    args = parser.parse_args(argv)
    result = run(
        args.output_dir,
        task_family_limit=args.task_family_limit,
        reliability_passes=args.reliability_passes,
    )
    print(json.dumps({
        "passed": result["passed"],
        "arm_metrics": result["arm_metrics"],
        "reliability": result["reliability"],
    }, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
