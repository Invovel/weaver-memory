from pathlib import Path

from benchmarks.retrieval_safety_filter_validation import (
    evaluate_retrieval_safety_filter,
    main,
)


def test_safety_filter_blocks_untrusted_runtime_context(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    result = evaluate_retrieval_safety_filter(
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
    assert metrics["fts5_only_untrusted_top10_leak_count"] > 0
    assert metrics["source_gate_untrusted_top10_leak_count"] < (
        metrics["fts5_only_untrusted_top10_leak_count"]
    )
    assert metrics["full_gate_untrusted_top10_leak_count"] == 0
    assert metrics["full_gate_assistant_trap_top10_leak_count"] == 0
    assert metrics["full_gate_stale_top10_leak_count"] == 0
    assert metrics["full_gate_required_evidence_hit_rate"] >= (
        metrics["fts5_only_required_evidence_hit_rate"] - 0.05
    )
    assert metrics["full_gate_average_candidate_count"] < (
        metrics["fts5_only_average_candidate_count"]
    )
    assert metrics["runtime_authority_violation_count"] == 0
    assert metrics["online_llm_call_count"] == 0
    assert metrics["memory_promotion_count"] == 0
    assert metrics["layer3_mutation_count"] == 0


def test_safety_filter_writes_outputs(tmp_path):
    exit_code = main(["--output-dir", str(tmp_path)])

    assert exit_code == 0
    assert (tmp_path / "raw_results.json").exists()
    assert (tmp_path / "metrics_summary.json").exists()
    assert (tmp_path / "arms.jsonl").exists()
    assert (tmp_path / "query_results.jsonl").exists()
