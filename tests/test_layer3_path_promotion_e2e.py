import json

from benchmarks.layer3_path_promotion_e2e import ARMS, run


def test_layer3_path_promotion_e2e_outputs_paper_artifacts(tmp_path):
    output_dir = tmp_path / "layer3-path-promotion-e2e"
    result = run(output_dir, task_count=1, reliability_passes=3)

    assert result["passed"] is True
    for name in [
        "raw_results.json",
        "metrics.json",
        "arm_metrics.json",
        "task_runs.jsonl",
        "artifact_manifest.json",
        "claim_table.md",
        "reliability.json",
        "README.md",
    ]:
        assert (output_dir / name).exists()

    arm_metrics = json.loads((output_dir / "arm_metrics.json").read_text(encoding="utf-8"))
    assert set(arm_metrics) == set(ARMS)
    assert arm_metrics["mw_layer3_path"]["tests_passed"] == 1
    assert arm_metrics["mw_layer3_path"]["file_diff_matches_expected"] == 1
    assert arm_metrics["mw_layer3_path"]["best_path_selection_accuracy"] == 1
    assert arm_metrics["mw_layer3_path"]["average_path_regret"] == 0
    assert arm_metrics["mw_layer3_path"]["known_bad_action_attempts"] == 0
    assert arm_metrics["mw_layer3_path"]["rollback_success_rate"] == 1
    assert arm_metrics["mw_layer3_path"]["false_stable_promotion_count"] == 0
    assert arm_metrics["mw_verified_memory"]["average_path_regret"] > 0
    assert arm_metrics["retrieval_memory"]["average_path_regret"] > arm_metrics["mw_verified_memory"]["average_path_regret"]

    reliability = json.loads((output_dir / "reliability.json").read_text(encoding="utf-8"))
    assert reliability["run_count"] == 3
    assert reliability["pass_power_3"] is True
    assert reliability["tests_passed_pass_power_3"] is True
    assert reliability["diff_matches_expected_pass_power_3"] is True

    manifest = json.loads((output_dir / "artifact_manifest.json").read_text(encoding="utf-8"))
    layer3_artifacts = [item for item in manifest if item["arm"] == "mw_layer3_path"]
    assert layer3_artifacts
    for item in layer3_artifacts:
        assert "pytest_before.txt" in item["pytest_before"]
        assert "pytest_after.txt" in item["pytest_after"]
        assert "diff.patch" in item["diff_patch"]
        assert item["tests_passed"] is True
        assert item["file_diff_matches_expected"] is True
