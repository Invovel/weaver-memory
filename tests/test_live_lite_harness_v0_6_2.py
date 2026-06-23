from benchmarks.live_lite_harness_v0_6_2 import (
    evaluate_live_lite_harness,
    load_dialogue_cards,
    main,
)


def test_live_lite_harness_executes_mock_tools_safely():
    result = evaluate_live_lite_harness(load_dialogue_cards())

    assert result["passed"] is True
    metrics = result["metrics"]
    assert metrics["task_count"] >= 50
    assert metrics["task_run_count"] == metrics["task_count"] * 3
    assert metrics["decision_count"] == metrics["task_run_count"]
    assert metrics["hash_chain_valid"] is True
    assert metrics["mock_tool_execution_count"] > 0
    assert metrics["mw_steps_to_success_delta_vs_no_memory"] > 0
    assert metrics["mw_steps_to_success_delta_vs_rag"] > 0
    assert metrics["mw_known_bad_tool_failure_reduction_vs_no_memory"] > 0
    assert metrics["mw_known_bad_tool_failure_reduction_vs_rag"] > 0
    assert metrics["mw_required_evidence_first_hit_rate"] == 1.0
    assert metrics["mw_unsafe_mock_tool_execution_count"] == 0
    assert metrics["real_tool_execution_count"] == 0
    assert metrics["memory_promotion_count"] == 0
    assert metrics["layer3_mutation_count"] == 0
    assert metrics["online_llm_call_count"] == 0


def test_live_lite_harness_arm_results_are_ordered():
    result = evaluate_live_lite_harness(load_dialogue_cards())
    arms = {arm["arm"]: arm for arm in result["arms"]}

    assert arms["memoryweaver_runtime_marker"]["average_steps_to_success"] < (
        arms["rag_over_logs"]["average_steps_to_success"]
    )
    assert arms["rag_over_logs"]["average_steps_to_success"] < (
        arms["no_memory"]["average_steps_to_success"]
    )
    assert arms["no_memory"]["known_bad_tool_failures"] > (
        arms["rag_over_logs"]["known_bad_tool_failures"]
    )
    assert arms["rag_over_logs"]["known_bad_tool_failures"] > (
        arms["memoryweaver_runtime_marker"]["known_bad_tool_failures"]
    )
    assert arms["memoryweaver_runtime_marker"]["unsafe_mock_tool_execution_count"] == 0
    assert arms["memoryweaver_runtime_marker"]["evidence_observed_count"] > 0


def test_live_lite_harness_writes_outputs(tmp_path):
    exit_code = main(["--output-dir", str(tmp_path)])

    assert exit_code == 0
    assert (tmp_path / "raw_results.json").exists()
    assert (tmp_path / "metrics_summary.json").exists()
    assert (tmp_path / "arms.jsonl").exists()
    assert (tmp_path / "task_runs.jsonl").exists()
    assert (tmp_path / "decisions.jsonl").exists()
    assert len((tmp_path / "task_runs.jsonl").read_text(encoding="utf-8").splitlines()) == 150
    assert len((tmp_path / "decisions.jsonl").read_text(encoding="utf-8").splitlines()) == 150
