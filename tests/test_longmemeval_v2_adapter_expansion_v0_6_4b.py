import json

from benchmarks.longmemeval_v2_adapter_expansion_v0_6_4b import (
    evaluate_lme_v2_expansion,
    evaluate_question_limits,
)


def _write_jsonl(path, records):
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def _make_lme_v2_expansion_fixture(tmp_path):
    root = tmp_path / "longmemeval-v2"
    (root / "haystacks").mkdir(parents=True)
    _write_jsonl(
        root / "questions.jsonl",
        [
            {
                "id": "q001",
                "domain": "enterprise",
                "environment": "workarena",
                "question_type": "dynamic-environment",
                "question": "Which state is latest after checking evidence?",
                "answer": "Closed Complete",
                "eval_function": "exact",
            },
            {
                "id": "q002",
                "domain": "enterprise",
                "environment": "workarena",
                "question_type": "workflow-knowledge",
                "question": "Which action should be avoided?",
                "answer": "blind close",
                "eval_function": "exact",
            },
        ],
    )
    _write_jsonl(
        root / "trajectories.jsonl",
        [
            {
                "id": "t001",
                "domain": "enterprise",
                "environment": "workarena",
                "goal": "Close incident after checking the activity stream.",
                "outcome": "success",
                "start_url": "https://example.test/incident",
                "states": [
                    {
                        "state_index": 0,
                        "step": 0,
                        "url": "https://example.test/incident",
                        "action": None,
                        "thought": "I should inspect the activity stream first.",
                        "accessibility_tree": "RootWebArea Incident Activity Stream",
                        "screenshot": "screenshots/t001/0.png",
                    },
                    {
                        "state_index": 1,
                        "step": 1,
                        "url": "https://example.test/incident",
                        "action": "click('Update')",
                        "thought": "The evidence supports closing the incident.",
                        "accessibility_tree": "RootWebArea State Closed Complete",
                        "screenshot": "screenshots/t001/1.png",
                    },
                ],
            },
            {
                "id": "t002",
                "domain": "enterprise",
                "environment": "workarena",
                "goal": "Do not blindly close the incident without evidence.",
                "outcome": "failure",
                "start_url": "https://example.test/incident",
                "states": [
                    {
                        "state_index": 0,
                        "step": 0,
                        "url": "https://example.test/incident",
                        "action": "click('Close')",
                        "thought": "This may fail because evidence is missing.",
                        "accessibility_tree": "RootWebArea Error Missing activity evidence",
                        "screenshot": "screenshots/t002/0.png",
                    }
                ],
            },
        ],
    )
    (root / "haystacks" / "lme_v2_small.json").write_text(
        json.dumps({"q001": ["t001", "t002"], "q002": ["t002", "t001"]}),
        encoding="utf-8",
    )
    return root


def test_lme_v2_expansion_reports_adapter_quality(tmp_path):
    root = _make_lme_v2_expansion_fixture(tmp_path)
    result = evaluate_lme_v2_expansion(
        root,
        question_limit=2,
        trajectories_per_question=2,
        states_per_trajectory=2,
    )

    assert result["passed"] is True
    metrics = result["metrics"]
    assert metrics["required_field_coverage"] == 1.0
    assert metrics["trajectory_question_join_rate"] == 1.0
    assert metrics["evidence_ref_validity_rate"] == 1.0
    assert metrics["unsupported_claim_rate"] == 0.0
    assert metrics["policy_gate_leak_count"] == 0
    assert metrics["verified_memory_write_count"] == 0
    assert metrics["promotion_count"] == 0
    assert metrics["layer3_mutation_count"] == 0
    assert metrics["known_bad_path_count"] == 1
    assert metrics["known_bad_path_detection_rate"] == 1.0


def test_lme_v2_expansion_can_run_multiple_question_limits(tmp_path):
    root = _make_lme_v2_expansion_fixture(tmp_path)
    result = evaluate_question_limits(
        root,
        question_limits=[1, 2],
        trajectories_per_question=1,
        states_per_trajectory=1,
        max_observation_chars=400,
        haystack_name="lme_v2_small.json",
    )

    assert result["passed"] is True
    assert [run["metrics"]["question_limit"] for run in result["runs"]] == [1, 2]
    assert all(run["metrics"]["online_llm_call_count"] == 0 for run in result["runs"])
    assert all(run["metrics"]["verified_memory_write_count"] == 0 for run in result["runs"])
