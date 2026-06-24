import json

from benchmarks.retrieval_wear_e2e import ARMS, run


def test_retrieval_wear_separates_cache_path_reuse_and_governed_rollback(tmp_path):
    output_dir = tmp_path / "retrieval-wear-e2e"
    result = run(output_dir, task_family_limit=5, reliability_passes=3)

    assert result["passed"] is True
    assert set(result["arm_metrics"]) == set(ARMS)

    cache = result["arm_metrics"]["answer_cache"]
    path = result["arm_metrics"]["retrieval_path_memory"]
    rag = result["arm_metrics"]["rag_only"]
    mw = result["arm_metrics"]["memoryweaver"]

    assert cache["semantic_transfer_rate"] == 0
    assert cache["stale_path_reuse_rate"] == 1
    assert path["semantic_transfer_rate"] == 1
    assert path["stale_path_reuse_rate"] == 1
    assert mw["evidence_hit_rate"] == 1
    assert mw["semantic_transfer_rate"] == 1
    assert mw["stale_path_reuse_rate"] == 0
    assert mw["path_invalidation_rate"] == 1
    assert mw["rollback_success_rate"] == 1
    assert mw["total_candidates_inspected"] < rag["total_candidates_inspected"]

    for name in [
        "raw_results.json",
        "metrics.json",
        "arm_metrics.json",
        "task_runs.jsonl",
        "reliability.json",
        "claim_table.md",
        "README.md",
    ]:
        assert (output_dir / name).exists()

    reliability = json.loads(
        (output_dir / "reliability.json").read_text(encoding="utf-8")
    )
    assert reliability["run_count"] == 3
    assert reliability["pass_power_3"] is True
    assert reliability["memoryweaver_stale_path_reuse_rate_mean"] == 0
