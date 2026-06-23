from pathlib import Path

from benchmarks.active_marker_binding_validation import evaluate_binding, main


def test_active_marker_binding_golden_cards_pass(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    result = evaluate_binding(
        context_fixture=(
            repo_root
            / "docs"
            / "validation"
            / "context-capsule-v0.5.3"
            / "raw_spans_fixture.jsonl"
        ),
        markers_path=(
            repo_root
            / "docs"
            / "validation"
            / "runbook-marker-v0.5"
            / "markers.json"
        ),
        cards_path=(
            repo_root
            / "docs"
            / "validation"
            / "runbook-marker-v0.5"
            / "dialogue_cards.jsonl"
        ),
        workspace_root=tmp_path / ".memoryweaver",
    )

    assert result["passed"] is True
    assert result["metrics"]["marker_count"] == 5
    assert result["metrics"]["marker_context_hit_rate"] == 1.0
    assert result["metrics"]["required_evidence_coverage"] == 1.0
    assert result["metrics"]["raw_recovery_rate"] == 1.0
    assert result["metrics"]["runtime_mutation_count"] == 0
    assert result["metrics"]["layer3_mutation_count"] == 0
    assert result["metrics"]["memory_promotion_count"] == 0
    assert result["metrics"]["online_llm_call_count"] == 0
    for trace in result["traces"]:
        assert trace["binding_mode"] == "active_preview"
        assert trace["runtime_authority"] is False
        assert trace["applied_to_runtime"] is False
        assert trace["actual_route"] == "thinking"
        assert trace["bound_capsule_ids"]
        assert trace["raw_refs"]


def test_active_marker_binding_writes_outputs(tmp_path):
    exit_code = main(["--output-dir", str(tmp_path)])

    assert exit_code == 0
    assert (tmp_path / "raw_results.json").exists()
    assert (tmp_path / "metrics_summary.json").exists()
    assert (tmp_path / "binding_traces.jsonl").exists()
    assert len((tmp_path / "binding_traces.jsonl").read_text(encoding="utf-8").splitlines()) == 5
