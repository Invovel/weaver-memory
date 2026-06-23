from pathlib import Path

from benchmarks.real_trajectory_experiment_v0_6 import (
    evaluate_real_trajectory_experiment,
    load_dialogue_cards,
    main,
)


def test_real_trajectory_experiment_reduces_bad_paths_and_steps():
    cards = load_dialogue_cards()
    result = evaluate_real_trajectory_experiment(cards)

    assert result["passed"] is True
    metrics = result["metrics"]
    assert metrics["task_count"] >= 50
    assert metrics["trajectory_count"] == metrics["task_count"] * 3
    assert metrics["arm_count"] == 3
    assert metrics["mw_steps_to_success_delta_vs_no_memory"] > 0
    assert metrics["mw_steps_to_success_delta_vs_rag"] > 0
    assert metrics["mw_known_bad_action_reduction_vs_no_memory"] > 0
    assert metrics["mw_known_bad_action_reduction_vs_rag"] > 0
    assert metrics["mw_required_evidence_first_hit_rate"] == 1.0
    assert metrics["mw_marker_activation_accuracy"] == 1.0
    assert metrics["runtime_authority_violation_count"] == 0
    assert metrics["online_llm_call_count"] == 0


def test_real_trajectory_experiment_arm_ordering():
    result = evaluate_real_trajectory_experiment(load_dialogue_cards())
    arms = {arm["arm"]: arm for arm in result["arms"]}

    assert set(arms) == {
        "no_memory",
        "rag_over_logs",
        "memoryweaver_runtime_marker",
    }
    assert arms["memoryweaver_runtime_marker"]["average_steps_to_success"] < (
        arms["rag_over_logs"]["average_steps_to_success"]
    )
    assert arms["rag_over_logs"]["average_steps_to_success"] < (
        arms["no_memory"]["average_steps_to_success"]
    )
    assert arms["memoryweaver_runtime_marker"]["known_bad_action_attempts"] == 0
    assert arms["rag_over_logs"]["known_bad_action_attempts"] > 0
    assert arms["no_memory"]["known_bad_action_attempts"] > (
        arms["rag_over_logs"]["known_bad_action_attempts"]
    )


def test_real_trajectory_experiment_writes_outputs(tmp_path):
    exit_code = main(["--output-dir", str(tmp_path)])

    assert exit_code == 0
    assert (tmp_path / "raw_results.json").exists()
    assert (tmp_path / "metrics_summary.json").exists()
    assert (tmp_path / "arms.jsonl").exists()
    assert (tmp_path / "task_runs.jsonl").exists()
    assert len((tmp_path / "task_runs.jsonl").read_text(encoding="utf-8").splitlines()) == 150
