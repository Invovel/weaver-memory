import json

from benchmarks.experience_transfer_protocol_v0_7 import run
from memoryweaver.evaluation import ExperienceTransferProtocol


def test_experience_transfer_protocol_compares_four_arms(tmp_path):
    result = ExperienceTransferProtocol(
        workspace_root=tmp_path / ".memoryweaver-exp",
    ).run()

    assert result.passed is True
    metrics = result.arm_metrics
    assert set(metrics) == {
        "no_memory",
        "raw_rag_over_logs",
        "mw_verified_memory",
        "mw_verified_memory_marker",
    }
    assert metrics["no_memory"]["task_count"] == 15
    assert metrics["mw_verified_memory"]["task_count"] == 15
    assert result.marker_only_arm_metrics["no_memory"]["task_count"] == 3
    assert result.marker_only_arm_metrics["mw_verified_memory"]["task_count"] == 3
    assert (
        metrics["mw_verified_memory"]["average_steps_to_success"]
        < metrics["no_memory"]["average_steps_to_success"]
    )
    assert metrics["mw_verified_memory"]["retrieval_hit_before_critical_action_rate"] > 0.8
    assert metrics["mw_verified_memory_marker"]["known_bad_action_attempts"] == 0
    assert metrics["mw_verified_memory_marker"]["marker_direct_action_change_count"] == 0
    assert metrics["mw_verified_memory_marker"]["marker_added_value_count"] > 0
    assert result.marker_only_arm_metrics["mw_verified_memory"]["critical_action_changed_by_memory_rate"] == 0
    assert result.marker_only_arm_metrics["mw_verified_memory_marker"]["marker_direct_action_change_count"] > 0
    assert result.probe_metrics["main_suite"]["mw_verified_memory"]["decision_changed_valid_rate"] > 0
    assert result.memory_use_summary["mw_verified_memory"]["marker_required_count"] > 0
    assert result.memory_use_summary["mw_verified_memory"]["retrieval_miss_count"] == 0
    assert result.cost_metrics["mw_verified_memory"]["token_overhead_vs_no_memory"] > 0


def test_experience_transfer_outputs_required_files(tmp_path):
    output_dir = tmp_path / "experience-transfer"
    result = run(output_dir)

    assert result["passed"] is True
    for name in [
        "experience_families.jsonl",
        "task_runs.jsonl",
        "arm_metrics.json",
        "marker_only_arm_metrics.json",
        "decision_probe.jsonl",
        "probe_metrics.json",
        "memory_use_probe.jsonl",
        "memory_use_summary.json",
        "cost_metrics.json",
        "reliability.json",
        "raw_results.json",
        "README.md",
    ]:
        assert (output_dir / name).exists()
    task_runs = [
        json.loads(line)
        for line in (output_dir / "task_runs.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(task_runs) == 72
    assert any(run["critical_action_changed_by_memory"] for run in task_runs)
    assert any(run["marker_direct_action_change"] for run in task_runs)


def test_experience_transfer_probe_marks_invalid_llm_action_as_invalid(tmp_path):
    from memoryweaver.evaluation.experience_transfer import _decision_probe

    probe = _decision_probe(
        family=ExperienceTransferProtocol(
            workspace_root=tmp_path / ".memoryweaver-exp-probe"
        ).families[0],
        target=ExperienceTransferProtocol(
            workspace_root=tmp_path / ".memoryweaver-exp-probe-2"
        ).families[0].target_tasks[0],
        arm="no_memory",
        suite="main_suite",
        action_without_memory="reinstall_npm",
        action_with_context="__invalid_action__",
    )

    assert probe["decision_changed"] is True
    assert probe["probe_valid"] is False
    assert probe["decision_changed_valid"] is False


def test_experience_transfer_reliability_summary_outputs_pass_power_3(tmp_path):
    output_dir = tmp_path / "experience-transfer-reliability"
    result = run(output_dir, reliability_passes=3, seed=7)

    assert result["reliability"]["run_count"] == 3
    assert result["reliability"]["pass_at_1"] is True
    assert result["reliability"]["pass_power_3"] is True
    assert result["reliability"]["seeds"] == [7, 8, 9]
    assert "mw_verified_memory" in result["reliability"]["by_arm"]
