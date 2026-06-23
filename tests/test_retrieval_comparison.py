from pathlib import Path

from benchmarks.retrieval_comparison_validation import (
    evaluate_retrieval_comparison,
    main,
)


def test_retrieval_comparison_reduces_candidates_without_llm_or_mutation(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    result = evaluate_retrieval_comparison(
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
    assert metrics["query_count"] >= 50
    assert metrics["capsule_count"] >= 340
    assert metrics["tag_time_recall_at_10"] >= metrics["baseline_recall_at_10"]
    assert metrics["graph_recall_at_10"] >= metrics["baseline_recall_at_10"]
    assert (
        metrics["tag_time_average_candidate_count"]
        < metrics["baseline_average_candidate_count"]
    )
    assert (
        metrics["graph_average_candidate_count"]
        < metrics["baseline_average_candidate_count"]
    )
    assert metrics["graph_expansion_precision"] >= 0.95
    assert metrics["online_llm_call_count"] == 0
    assert metrics["memory_promotion_count"] == 0
    assert metrics["layer3_mutation_count"] == 0


def test_retrieval_comparison_writes_outputs(tmp_path):
    exit_code = main(["--output-dir", str(tmp_path)])

    assert exit_code == 0
    assert (tmp_path / "raw_results.json").exists()
    assert (tmp_path / "metrics_summary.json").exists()
    assert (tmp_path / "query_results.jsonl").exists()
    assert (tmp_path / "arms.jsonl").exists()
