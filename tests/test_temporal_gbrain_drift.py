from pathlib import Path

from benchmarks.temporal_gbrain_drift_validation import (
    evaluate_temporal_drift,
    main,
)


def test_temporal_gbrain_drift_produces_review_only_marker_proposals(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    result = evaluate_temporal_drift(
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
    assert metrics["core_issue_count"] >= 50
    assert metrics["marker_count"] >= 50
    assert metrics["stale_marker_count"] > 0
    assert metrics["challenged_marker_count"] > 0
    assert metrics["supersedes_edge_count"] > 0
    assert metrics["challenged_by_edge_count"] > 0
    assert metrics["marker_proposal_count"] > 0
    assert metrics["runtime_authority_granted_count"] == 0
    assert metrics["memory_promotion_count"] == 0
    assert metrics["layer3_mutation_count"] == 0
    assert metrics["online_llm_call_count"] == 0
    assert all(proposal["requires_review"] for proposal in result["marker_proposals"])
    assert all(not proposal["runtime_authority"] for proposal in result["marker_proposals"])


def test_temporal_gbrain_drift_writes_outputs(tmp_path):
    exit_code = main(["--output-dir", str(tmp_path)])

    assert exit_code == 0
    assert (tmp_path / "raw_results.json").exists()
    assert (tmp_path / "metrics_summary.json").exists()
    assert (tmp_path / "marker_proposals.jsonl").exists()
    assert (tmp_path / "temporal_nodes.jsonl").exists()
    assert (tmp_path / "temporal_edges.jsonl").exists()
