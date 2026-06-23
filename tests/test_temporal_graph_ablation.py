from pathlib import Path

from benchmarks.temporal_graph_ablation_validation import (
    evaluate_temporal_graph_ablation,
    main,
)


def test_temporal_graph_ablation_filters_review_only_markers(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    result = evaluate_temporal_graph_ablation(
        core_issues_path=(
            repo_root
            / "docs"
            / "validation"
            / "runbook-marker-v0.5"
            / "core_issues.json"
        ),
        markers_path=(
            repo_root
            / "docs"
            / "validation"
            / "runbook-marker-v0.5"
            / "markers.json"
        ),
        workspace_root=tmp_path / ".memoryweaver",
    )

    assert result["passed"] is True
    metrics = result["metrics"]
    assert metrics["query_count"] >= 50
    assert metrics["static_recall_at_10"] == 1.0
    assert metrics["temporal_runtime_recall_at_10"] >= 0.95
    assert (
        metrics["static_stale_runtime_leak_count"]
        + metrics["static_challenged_runtime_leak_count"]
    ) > 0
    assert metrics["temporal_stale_runtime_leak_count"] == 0
    assert metrics["temporal_challenged_runtime_leak_count"] == 0
    assert metrics["temporal_review_capture_rate"] == 1.0
    assert metrics["runtime_authority_granted_count"] == 0
    assert metrics["memory_promotion_count"] == 0
    assert metrics["layer3_mutation_count"] == 0
    assert metrics["online_llm_call_count"] == 0


def test_temporal_graph_ablation_writes_outputs(tmp_path):
    exit_code = main(["--output-dir", str(tmp_path)])

    assert exit_code == 0
    assert (tmp_path / "raw_results.json").exists()
    assert (tmp_path / "metrics_summary.json").exists()
    assert (tmp_path / "arms.jsonl").exists()
    assert (tmp_path / "query_results.jsonl").exists()
    assert (tmp_path / "review_queue.jsonl").exists()
