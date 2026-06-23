from pathlib import Path

from benchmarks.controlled_active_guard_validation import (
    evaluate_controlled_active_guard,
    main,
)


def test_controlled_active_guard_only_allows_low_risk_hint(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    result = evaluate_controlled_active_guard(
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
    assert result["metrics"]["active_guard_applied_count"] == 1
    assert result["metrics"]["high_risk_blocked_count"] == 4
    assert result["metrics"]["route_hint_applied_count"] == 1
    assert result["metrics"]["required_evidence_plan_applied_count"] == 1
    assert result["metrics"]["tool_execution_count"] == 0
    assert result["metrics"]["actual_suppression_count"] == 0
    assert result["metrics"]["memory_promotion_count"] == 0
    assert result["metrics"]["layer3_mutation_count"] == 0
    assert result["metrics"]["online_llm_call_count"] == 0
    assert result["metrics"]["conflict_logged_count"] >= 1
    assert result["metrics"]["conflict_blocked_count"] >= 1

    active = [
        trace for trace in result["traces"]
        if trace["output_mode"] == "controlled_active_guard"
    ]
    assert len(active) == 1
    assert active[0]["marker_id"] == "retain_docker_warning_as_partial_evidence"
    assert active[0]["intervention_level"] == "L1_hint"
    assert active[0]["actual_route"] == "fast_verify"
    assert active[0]["actual_required_evidence"]
    assert active[0]["actual_suppressed_actions"] == []

    conflicted = [
        trace for trace in result["traces"]
        if trace["conflict_candidates"]
    ]
    assert conflicted
    assert "unresolved_marker_conflict" in conflicted[0]["block_reasons"]
    assert conflicted[0]["output_mode"] == "preview_only_blocked"


def test_controlled_active_guard_writes_outputs(tmp_path):
    exit_code = main(["--output-dir", str(tmp_path)])

    assert exit_code == 0
    assert (tmp_path / "raw_results.json").exists()
    assert (tmp_path / "metrics_summary.json").exists()
    assert (tmp_path / "guard_traces.jsonl").exists()
    assert len((tmp_path / "guard_traces.jsonl").read_text(encoding="utf-8").splitlines()) == 5
