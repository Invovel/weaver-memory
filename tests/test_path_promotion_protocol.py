import json

from benchmarks.layer3_path_promotion_v0_7 import run
from memoryweaver.evaluation import PathPromotionProtocol


def test_path_promotion_protocol_promotes_and_selects_latest_paths(tmp_path):
    result = PathPromotionProtocol(
        workspace_root=tmp_path / ".memoryweaver-path-promotion",
    ).run()

    assert result.passed is True
    metrics = result.metrics
    assert metrics["stable_promotion_rate"] == 1.0
    assert metrics["latest_path_selection_accuracy"] == 1.0
    assert metrics["skill_path_selection_accuracy"] == 1.0
    assert metrics["harness_path_selection_accuracy"] == 1.0
    assert metrics["stale_path_suppression_rate"] == 1.0
    assert metrics["rollback_success_rate"] == 1.0
    assert metrics["false_stable_promotion_count"] == 0
    assert metrics["average_path_regret"] == 0.0


def test_path_promotion_outputs_required_files(tmp_path):
    output_dir = tmp_path / "path-promotion"
    result = run(output_dir)

    assert result["passed"] is True
    for name in [
        "families.jsonl",
        "path_catalog.jsonl",
        "task_runs.jsonl",
        "metrics.json",
        "raw_results.json",
        "README.md",
    ]:
        assert (output_dir / name).exists()
    path_catalog = [
        json.loads(line)
        for line in (output_dir / "path_catalog.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(item["label"] == "current_best" for item in path_catalog)
    assert any(item["status"] in {"challenged", "rolled_back"} for item in path_catalog)
