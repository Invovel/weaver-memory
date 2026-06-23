from pathlib import Path

from benchmarks.l2_route_approval_validation import (
    evaluate_l2_route_approval,
    main,
)


def test_l2_route_requires_explicit_approval(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    result = evaluate_l2_route_approval(
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
        conflicts_path=(
            repo_root
            / "docs"
            / "validation"
            / "runbook-marker-v0.5"
            / "conflict_candidates.jsonl"
        ),
        approvals_path=(
            repo_root
            / "docs"
            / "validation"
            / "l2-route-approval-v0.5.2"
            / "route_approvals.jsonl"
        ),
        workspace_root=tmp_path / ".memoryweaver",
    )

    assert result["passed"] is True
    assert result["metrics"]["l1_active_count"] == 1
    assert result["metrics"]["l2_marker_count"] == 2
    assert result["metrics"]["l2_approved_count"] == 1
    assert result["metrics"]["l2_pending_count"] == 1
    assert result["metrics"]["l2_applied_count"] == 1
    assert result["metrics"]["l3_blocked_count"] == 2
    assert result["metrics"]["conflict_blocked_count"] >= 1
    assert result["metrics"]["tool_execution_count"] == 0
    assert result["metrics"]["actual_suppression_count"] == 0
    assert result["metrics"]["memory_promotion_count"] == 0
    assert result["metrics"]["layer3_mutation_count"] == 0
    assert result["metrics"]["online_llm_call_count"] == 0

    approved = [
        trace for trace in result["traces"]
        if trace["output_mode"] == "approved_l2_route_plan"
    ]
    assert len(approved) == 1
    assert approved[0]["marker_id"] == "do_not_treat_key_existence_as_positive_auth"
    assert approved[0]["approval"]["decision"] == "approved"
    assert approved[0]["actual_route"] == "fast_verify"
    assert approved[0]["actual_required_evidence"]
    assert approved[0]["actual_suppressed_actions"] == []

    pending = [
        trace for trace in result["traces"]
        if trace["output_mode"] == "l2_route_pending_approval"
    ]
    assert len(pending) == 1
    assert pending[0]["marker_id"] == "require_recent_ci_log_before_timeout_update"
    assert "missing_l2_route_approval" in pending[0]["block_reasons"]


def test_l2_route_approval_writes_outputs(tmp_path):
    exit_code = main(["--output-dir", str(tmp_path)])

    assert exit_code == 0
    assert (tmp_path / "raw_results.json").exists()
    assert (tmp_path / "metrics_summary.json").exists()
    assert (tmp_path / "route_traces.jsonl").exists()
    assert len((tmp_path / "route_traces.jsonl").read_text(encoding="utf-8").splitlines()) == 5
