import json

from benchmarks.harness_runtime_core import run


def test_harness_runtime_core_benchmark_writes_outputs(tmp_path):
    output_dir = tmp_path / "harness-runtime-core"
    result = run(output_dir)

    assert result["passed"] is True
    for name in [
        "raw_results.json",
        "task_runs.jsonl",
        "metrics.json",
        "README.md",
        "runtime_path_store.json",
        "events.jsonl",
        "checkpoints.json",
    ]:
        assert (output_dir / name).exists()

    metrics_doc = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))
    metrics = metrics_doc["arms"]
    aggregate = metrics_doc["aggregate"]
    assert metrics["memoryweaver_harness_runtime"]["task_count"] == 50
    assert metrics["memoryweaver_harness_runtime"]["invalid_action_rate"] == 0
    assert metrics["naive_memory"]["memory_induced_regression_rate"] == 1
    assert metrics["summary_memory"]["invalid_action_rate"] > 0
    assert metrics["rollback_probe"]["rollback_frequency"] == 1
    assert metrics["memoryweaver_harness_runtime_recovery"]["success_rate"] == 1
    assert aggregate["promotion_precision"] == 1
    assert aggregate["negative_memory_hit_rate"] == 1
    assert aggregate["task_success_delta_vs_retrieval_memory"] > 0
    assert aggregate["runtime_path_store_roundtrip"] == 1
    assert result["persistence_probe"]["restored_rollback_recommended"] is True
    assert result["persistence_probe"]["journal_event_count"] == 3
    assert result["persistence_probe"]["checkpoint_count_for_first_task"] == 1


def test_harness_runtime_core_benchmark_is_repeatable(tmp_path):
    output_dir = tmp_path / "harness-runtime-core"

    first = run(output_dir)
    second = run(output_dir)

    assert first["passed"] is True
    assert second["passed"] is True
    assert second["aggregate_metrics"]["runtime_path_store_roundtrip"] == 1
    assert second["persistence_probe"]["journal_event_count"] == 3
    assert second["persistence_probe"]["checkpoint_count_for_first_task"] == 1
