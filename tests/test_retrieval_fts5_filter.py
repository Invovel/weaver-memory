from pathlib import Path

from benchmarks.retrieval_fts5_filter_validation import (
    evaluate_fts5_frontend_filter,
    main,
)


def test_fts5_frontend_filter_reduces_candidates_without_recall_loss(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    result = evaluate_fts5_frontend_filter(
        base_fixture=(
            repo_root
            / "docs"
            / "validation"
            / "context-capsule-v0.5.3"
            / "raw_spans_fixture.jsonl"
        ),
        dialogue_cards_path=(
            repo_root
            / "docs"
            / "validation"
            / "runbook-marker-v0.5"
            / "dialogue_cards.jsonl"
        ),
        workspace_root=tmp_path / ".memoryweaver",
    )

    assert result["passed"] is True
    metrics = result["metrics"]
    assert metrics["fts5_available"] is True
    assert metrics["query_count"] >= 50
    assert metrics["tag_time_fts5_recall_at_10"] >= metrics["fts5_all_recall_at_10"] - 0.05
    assert metrics["graph_tag_time_fts5_recall_at_10"] >= metrics["fts5_all_recall_at_10"] - 0.05
    assert metrics["tag_time_fts5_candidate_reduction_ratio"] >= 0.9
    assert metrics["graph_tag_time_fts5_candidate_reduction_ratio"] >= 0.9
    assert metrics["online_llm_call_count"] == 0
    assert metrics["memory_promotion_count"] == 0
    assert metrics["layer3_mutation_count"] == 0


def test_fts5_frontend_filter_writes_outputs(tmp_path):
    exit_code = main(["--output-dir", str(tmp_path)])

    assert exit_code == 0
    assert (tmp_path / "raw_results.json").exists()
    assert (tmp_path / "metrics_summary.json").exists()
    assert (tmp_path / "arms.jsonl").exists()
    assert (tmp_path / "query_results.jsonl").exists()
