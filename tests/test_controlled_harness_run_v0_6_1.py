from benchmarks.controlled_harness_run_v0_6_1 import (
    evaluate_controlled_harness_run,
    load_dialogue_cards,
    main,
)


def test_controlled_harness_run_records_decisions_and_reduces_bad_paths():
    result = evaluate_controlled_harness_run(load_dialogue_cards())

    assert result["passed"] is True
    metrics = result["metrics"]
    assert metrics["task_count"] >= 50
    assert metrics["task_run_count"] == metrics["task_count"] * 3
    assert metrics["decision_count"] == metrics["task_run_count"]
    assert metrics["hash_chain_valid"] is True
    assert metrics["mw_steps_to_success_delta_vs_no_memory"] > 0
    assert metrics["mw_steps_to_success_delta_vs_rag"] > 0
    assert metrics["mw_known_bad_action_reduction_vs_no_memory"] > 0
    assert metrics["mw_known_bad_action_reduction_vs_rag"] > 0
    assert metrics["mw_required_evidence_first_hit_rate"] == 1.0
    assert metrics["mw_known_bad_warning_count"] > 0
    assert metrics["runtime_authority_violation_count"] == 0
    assert metrics["tool_execution_count"] == 0
    assert metrics["memory_promotion_count"] == 0
    assert metrics["layer3_mutation_count"] == 0
    assert metrics["online_llm_call_count"] == 0


def test_controlled_harness_run_arm_metrics_are_ordered():
    result = evaluate_controlled_harness_run(load_dialogue_cards())
    arms = {arm["arm"]: arm for arm in result["arms"]}

    assert arms["memoryweaver_runtime_marker"]["average_steps_to_success"] < (
        arms["rag_over_logs"]["average_steps_to_success"]
    )
    assert arms["rag_over_logs"]["average_steps_to_success"] < (
        arms["no_memory"]["average_steps_to_success"]
    )
    assert arms["memoryweaver_runtime_marker"]["known_bad_action_attempts"] == 0
    assert arms["memoryweaver_runtime_marker"]["known_bad_warning_count"] > 0
    assert arms["memoryweaver_runtime_marker"]["tool_execution_count"] == 0


def test_controlled_harness_run_writes_outputs(tmp_path):
    exit_code = main(["--output-dir", str(tmp_path)])

    assert exit_code == 0
    assert (tmp_path / "raw_results.json").exists()
    assert (tmp_path / "metrics_summary.json").exists()
    assert (tmp_path / "arms.jsonl").exists()
    assert (tmp_path / "task_runs.jsonl").exists()
    assert (tmp_path / "decisions.jsonl").exists()
    assert len((tmp_path / "task_runs.jsonl").read_text(encoding="utf-8").splitlines()) == 150
    assert len((tmp_path / "decisions.jsonl").read_text(encoding="utf-8").splitlines()) == 150
