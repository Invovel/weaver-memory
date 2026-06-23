from pathlib import Path

from benchmarks.decision_ledger_validation import (
    evaluate_decision_ledger,
    main,
    validate_hash_chain,
)


def test_decision_ledger_hash_chain_and_audit_fields(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    result = evaluate_decision_ledger(
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
    assert result["metrics"]["decision_count"] == 5
    assert result["metrics"]["hash_chain_valid"] is True
    assert result["metrics"]["approved_l2_with_approval_id_count"] == 1
    assert result["metrics"]["conflict_ref_count"] >= 1
    assert result["metrics"]["side_effect_total"] == 0
    assert validate_hash_chain(result["decisions"]) == []
    for decision in result["decisions"]:
        assert decision["record_hash"]
        assert decision["policy_version"] == "decision-ledger-policy-v1"
        assert decision["bound_capsule_ids"]
        assert decision["raw_refs"]


def test_decision_ledger_writes_outputs(tmp_path):
    exit_code = main(["--output-dir", str(tmp_path)])

    assert exit_code == 0
    assert (tmp_path / "raw_results.json").exists()
    assert (tmp_path / "metrics_summary.json").exists()
    assert (tmp_path / "decisions.jsonl").exists()
    assert (
        len((tmp_path / "decisions.jsonl").read_text(encoding="utf-8").splitlines())
        == 5
    )
