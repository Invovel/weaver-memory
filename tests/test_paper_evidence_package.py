import json

from scripts.generate_paper_evidence_package import build_package, write_package


def test_paper_evidence_package_builds_main_claims_from_current_artifacts():
    package = build_package()

    assert package["passed"] is True
    assert package["summary"]["fail_count"] == 0
    assert package["summary"]["warn_count"] == 0
    assert package["summary"]["main_evidence_count"] == 4
    assert package["metrics"]["live_llm"]["pass_power_3"] is True
    assert package["metrics"]["live_llm"]["online_llm_call_count"] > 0
    assert package["metrics"]["coding_debug"]["real_pytest_before_failed"] == 1.0
    assert package["metrics"]["coding_debug"]["real_pytest_after_passed"] == 1.0
    assert package["metrics"]["coding_debug"]["real_diff_matches_expected"] == 1.0
    assert package["metrics"]["layer3_e2e"]["path_regret_delta_vs_retrieval_memory"] < 0
    assert package["metrics"]["layer3_e2e"]["pass_power_3"] is True
    assert package["metrics"]["external_datasets"]["hf_candidates"]["boundary_violation_count"] == 0
    assert [item["paper_label"] for item in package["runtime_arms_comparison"]] == [
        "no_memory",
        "naive",
        "summary",
        "retrieval",
        "MemoryWeaver",
    ]
    assert {item["dataset"] for item in package["non_claim_table"]} == {
        "LoCoMo-MC10",
        "MemoryAgentBench",
    }
    assert all(item["effectiveness_claim"] == "no" for item in package["non_claim_table"])
    assert any("diff.patch" in item["diff"] for item in package["artifact_mapping"])
    assert any("rollback" in item["rollback_record"] for item in package["artifact_mapping"])

    warning_names = {item["name"] for item in package["checks"] if item["status"] == "warn"}
    assert warning_names == set()


def test_paper_evidence_package_writes_expected_files(tmp_path):
    output_dir = tmp_path / "paper-evidence-package"
    package = write_package(output_dir)

    assert package["passed"] is True
    for name in [
        "metrics.json",
        "evidence_table.json",
        "runtime_arms_comparison.json",
        "non_claim_table.json",
        "artifact_mapping.json",
        "checks.json",
        "open_issues.json",
        "artifact_files.json",
        "README.md",
    ]:
        assert (output_dir / name).exists()

    metrics = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["passed"] is True
    assert metrics["summary"]["fail_count"] == 0

    readme = (output_dir / "README.md").read_text(encoding="utf-8")
    assert "Layer-3 Path Promotion E2E" in readme
    assert "Runtime Arms Comparison" in readme
    assert "Non-Claim External Adapter Boundary" in readme
    assert "Artifact Mapping" in readme
    assert "LoCoMo-MC10" in readme
    assert "MemoryAgentBench" in readme
    assert "Do Not Overclaim" in readme
