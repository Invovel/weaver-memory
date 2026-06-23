import json

from benchmarks.harness_runtime_trace_loop import run


def test_harness_runtime_trace_loop_benchmark_writes_outputs(tmp_path):
    output_dir = tmp_path / "harness-runtime-trace-loop"
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
    ]:
        assert (output_dir / name).exists()

    metrics_doc = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))
    metrics = metrics_doc["arms"]
    aggregate = metrics_doc["aggregate"]

    assert metrics["memoryweaver_trace_candidate_runtime"]["task_count"] == 50
    assert metrics["memoryweaver_trace_candidate_runtime"]["invalid_action_rate"] == 0
    assert metrics["memoryweaver_trace_candidate_runtime"]["negative_memory_hit_rate"] == 1
    assert metrics["naive_memory"]["memory_induced_regression_rate"] == 1
    assert metrics["rollback_probe"]["rollback_frequency"] == 1
    assert metrics["memoryweaver_trace_candidate_runtime_recovery"]["success_rate"] == 1
    assert metrics["replacement_probe"]["success_rate"] == 1
    assert aggregate["candidate_registration_promotable"] == 1
    assert aggregate["candidate_registration_audited"] == 1
    assert aggregate["rejected_evidence_audited_count"] == 1
    assert aggregate["replacement_path_selected"] == 1
    assert aggregate["trace_store_roundtrip"] == 1
    assert aggregate["runtime_path_store_roundtrip"] == 1
    assert result["persistence_probe"]["candidate_registration_event_present"] is True
    assert result["persistence_probe"]["registration_rejected_evidence_count"] == 1
    assert result["persistence_probe"]["registration_rejected_as_challenge"] is False
    assert result["persistence_probe"]["replacement_registration_event_present"] is True
    assert result["persistence_probe"]["restored_selected_action"]["target"] == "action_schema_v2"
    assert result["persistence_probe"]["restored_policy_completed"] is True
    assert result["persistence_probe"]["restored_rollback_recommended"] is False
    assert len(result["candidate"]["path"]["action_policy"]) == 3
    assert result["persistence_probe"]["seed_journal_event_count"] == 4
    assert result["persistence_probe"]["runtime_replay_journal_event_count"] == 150
    assert result["persistence_probe"]["checkpoint_count_for_seed_thread"] == 4
    assert result["persistence_probe"]["runtime_replay_checkpoint_count"] == 150


def test_harness_runtime_trace_loop_benchmark_is_repeatable(tmp_path):
    output_dir = tmp_path / "harness-runtime-trace-loop"

    first = run(output_dir)
    second = run(output_dir)

    assert first["passed"] is True
    assert second["passed"] is True
    assert second["aggregate_metrics"]["candidate_registration_audited"] == 1
    assert second["aggregate_metrics"]["replacement_registration_audited"] == 1
    assert second["aggregate_metrics"]["replacement_path_selected"] == 1
    assert second["aggregate_metrics"]["trace_store_roundtrip"] == 1
    assert second["aggregate_metrics"]["runtime_path_store_roundtrip"] == 1
    assert len(second["candidate"]["path"]["action_policy"]) == 3
    assert second["persistence_probe"]["seed_journal_event_count"] == 4
    assert second["persistence_probe"]["runtime_replay_journal_event_count"] == 150
    assert second["persistence_probe"]["checkpoint_count_for_seed_thread"] == 4
    assert second["persistence_probe"]["runtime_replay_checkpoint_count"] == 150


def test_harness_runtime_trace_loop_reliability_outputs_pass_power_3(tmp_path):
    output_dir = tmp_path / "harness-runtime-trace-loop-reliability"
    result = run(output_dir, reliability_passes=3, seed=11)

    assert result["passed"] is True
    assert (output_dir / "reliability.json").exists()
    reliability = json.loads((output_dir / "reliability.json").read_text(encoding="utf-8"))
    assert reliability["run_count"] == 3
    assert reliability["pass_at_1"] is True
    assert reliability["pass_power_3"] is True
    assert reliability["seeds"] == [11, 12, 13]
    assert "memoryweaver_trace_candidate_runtime" in reliability["by_arm"]
    assert (
        reliability["by_arm"]["memoryweaver_trace_candidate_runtime"]["success_rate_mean"]
        == 1.0
    )
    assert reliability["by_arm"]["replacement_probe"]["success_rate_mean"] == 1.0
