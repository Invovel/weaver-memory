import json

from benchmarks.harness_runtime_coding_debug import run


def test_harness_runtime_coding_debug_uses_real_pytest_and_diff(tmp_path):
    output_dir = tmp_path / "harness-runtime-coding-debug"
    result = run(output_dir)

    assert result["passed"] is True
    for name in [
        "raw_results.json",
        "task_runs.jsonl",
        "metrics.json",
        "README.md",
        "runtime_path_store.json",
        "runtime_traces.jsonl",
        "events.jsonl",
        "checkpoints.json",
        "pytest_before.txt",
        "pytest_after.txt",
        "diff.patch",
    ]:
        assert (output_dir / name).exists()

    assert "ZeroDivisionError" in (output_dir / "pytest_before.txt").read_text(encoding="utf-8")
    assert "2 passed" in (output_dir / "pytest_after.txt").read_text(encoding="utf-8")
    assert "if denominator == 0" in (output_dir / "diff.patch").read_text(encoding="utf-8")

    metrics_doc = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))
    aggregate = metrics_doc["aggregate"]
    runtime = metrics_doc["arms"]["memoryweaver_coding_debug_runtime"]

    assert runtime["success_rate"] == 1
    assert runtime["invalid_action_rate"] == 0
    assert runtime["memory_induced_regression_rate"] == 0
    assert aggregate["real_pytest_before_failed"] == 1
    assert aggregate["real_pytest_after_passed"] == 1
    assert aggregate["real_diff_matches_expected"] == 1
    assert aggregate["promotion_external_evidence_only"] == 1
    assert aggregate["rollback_recorded"] == 1

    evidence_types = {
        item["evidence_type"]
        for item in result["candidate"]["evidence"]
    }
    assert {
        "tool_result",
        "test_result",
        "file_diff",
        "benchmark_score",
        "repeat_validation",
        "time_decay",
    }.issubset(evidence_types)
