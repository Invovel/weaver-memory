import json

from benchmarks.random_experience_accumulation_v0_7 import run
from memoryweaver.evaluation import RandomExperienceAccumulationProtocol


def test_random_experience_accumulation_flags_false_triggers(tmp_path):
    result = RandomExperienceAccumulationProtocol(
        workspace_root=tmp_path / ".memoryweaver-random",
    ).run()

    assert result.passed is True
    metrics = result.arm_metrics
    assert set(metrics) == {
        "fresh_no_memory",
        "random_experience_raw_logs",
        "random_experience_naive_memory",
        "mw_verified_experience",
        "mw_verified_experience_marker",
    }
    assert metrics["random_experience_raw_logs"]["false_trigger_rate"] > 0
    assert metrics["random_experience_naive_memory"]["false_trigger_rate"] > 0
    assert metrics["mw_verified_experience"]["false_trigger_rate"] == 0
    assert metrics["mw_verified_experience"]["retrieval_hit_before_critical_action_rate"] > 0


def test_random_experience_outputs_required_files(tmp_path):
    output_dir = tmp_path / "random-experience"
    result = run(output_dir)

    assert result["passed"] is True
    for name in [
        "experience_families.jsonl",
        "task_runs.jsonl",
        "arm_metrics.json",
        "cost_metrics.json",
        "raw_results.json",
        "README.md",
    ]:
        assert (output_dir / name).exists()
    task_runs = [
        json.loads(line)
        for line in (output_dir / "task_runs.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(task_runs) == 90
    assert any(run["false_trigger"] for run in task_runs)
    assert any(run["irrelevant_memory_injection"] for run in task_runs)
