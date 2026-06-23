import json

from benchmarks.harness_runtime_live_llm import run
from memoryweaver.runtime import LiveAction


class CountingLLMAgent:
    def __init__(self):
        self.online_llm_call_count = 0
        self._targets = [
            "__invalid_action__",
            "action_schema",
            "marker_only_boundary",
            "pass_power_3",
        ]

    def choose_action(self, observation, memory_context, *, step):
        self.online_llm_call_count += 1
        target = self._targets[min(step - 1, len(self._targets) - 1)]
        return LiveAction(
            name="tool_call" if target == "__invalid_action__" else "check_evidence",
            target=target,
            reasoning="counted fake LLM proposal",
        )


def test_harness_runtime_live_llm_mock_mode_writes_outputs(tmp_path):
    output_dir = tmp_path / "harness-runtime-live-llm"
    result = run(output_dir)

    assert result["passed"] is True
    assert result["run_config"]["mode"] == "mock_live_agent"
    assert result["aggregate_metrics"]["live_llm_run_complete"] == 0
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
    aggregate = metrics_doc["aggregate"]
    runtime = metrics_doc["arms"]["memoryweaver_live_candidate_runtime"]

    assert runtime["success_rate"] == 1
    assert runtime["invalid_action_rate"] == 0
    assert runtime["memory_induced_regression_rate"] == 0
    assert aggregate["candidate_registration_promotable"] == 1
    assert aggregate["candidate_registration_audited"] == 1
    assert aggregate["promotion_external_evidence_only"] == 1
    assert aggregate["rejected_evidence_audited_count"] == 1
    assert aggregate["rollback_recorded"] == 1
    assert aggregate["trace_store_roundtrip"] == 1
    assert aggregate["runtime_path_store_roundtrip"] == 1
    assert [item["target"] for item in result["candidate"]["path"]["action_policy"]] == [
        "action_schema",
        "marker_only_boundary",
        "pass_power_3",
    ]


def test_harness_runtime_live_llm_reliability_outputs_pass_power_3(tmp_path):
    output_dir = tmp_path / "harness-runtime-live-llm-reliability"
    result = run(output_dir, reliability_passes=3, seed=21)

    assert result["passed"] is True
    reliability = json.loads((output_dir / "reliability.json").read_text(encoding="utf-8"))
    assert reliability["run_count"] == 3
    assert reliability["pass_at_1"] is True
    assert reliability["pass_power_3"] is True
    assert reliability["seeds"] == [21, 22, 23]
    assert (
        reliability["by_arm"]["memoryweaver_live_candidate_runtime"]["success_rate_mean"]
        == 1.0
    )
    assert (
        reliability["by_arm"]["memoryweaver_live_candidate_runtime"][
            "memory_induced_regression_rate_mean"
        ]
        == 0.0
    )


def test_harness_runtime_live_llm_mode_requires_online_call_count(tmp_path):
    output_dir = tmp_path / "harness-runtime-live-llm-mode"
    result = run(
        output_dir,
        llm=True,
        agent_factory=CountingLLMAgent,
        reliability_passes=3,
        seed=31,
    )

    assert result["passed"] is True
    assert result["run_config"]["mode"] == "live_llm"
    assert result["aggregate_metrics"]["live_llm_run_complete"] == 1
    assert result["aggregate_metrics"]["online_llm_call_count"] > 0

    reliability = json.loads((output_dir / "reliability.json").read_text(encoding="utf-8"))
    assert reliability["run_count"] == 3
    assert reliability["pass_power_3"] is True
    assert reliability["aggregate"]["online_llm_call_count_mean"] > 0

    readme = (output_dir / "README.md").read_text(encoding="utf-8")
    assert "mode = live_llm" in readme
    assert "live_llm_run_complete = true" in readme
    assert "live LLM pass^3: True" in readme
