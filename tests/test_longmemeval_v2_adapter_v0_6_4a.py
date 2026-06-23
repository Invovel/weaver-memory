import json

from benchmarks.longmemeval_v2_adapter_v0_6_4a import evaluate_lme_v2_snapshot
from memoryweaver.external.longmemeval_v2 import (
    _snapshot_from_hf_cache,
    build_lme_v2_external_episodes,
    inspect_lme_v2_storage,
    resolve_lme_v2_root,
)


def _write_jsonl(path, records):
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def _make_lme_v2_fixture(tmp_path):
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
                "question": "What is the latest state after the tool action?",
                "answer": "Closed Complete",
                "eval_function": "exact",
            },
            {
                "id": "q002",
                "domain": "enterprise",
                "environment": "workarena",
                "question_type": "workflow-knowledge",
                "question": "Which evidence should be checked?",
                "answer": "activity stream",
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
                "goal": "Close the incident after checking the activity stream.",
                "outcome": "success",
                "start_url": "https://example.test",
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
            }
        ],
    )
    (root / "haystacks" / "lme_v2_small.json").write_text(
        json.dumps({"q001": ["t001"], "q002": ["t001"]}),
        encoding="utf-8",
    )
    return root


def test_lme_v2_external_episodes_from_snapshot(tmp_path):
    root = _make_lme_v2_fixture(tmp_path)
    episodes, metadata = build_lme_v2_external_episodes(
        root,
        question_limit=2,
        trajectories_per_question=1,
        states_per_trajectory=2,
    )

    assert metadata["question_count"] == 2
    assert metadata["loaded_trajectory_count"] == 1
    assert metadata["missing_trajectory_refs"] == 0
    assert len(episodes) == 2
    assert episodes[0].dataset_id == "longmemeval-v2"
    assert episodes[0].source_repo == "xiaowu0162/longmemeval-v2"
    assert episodes[0].queries[0].query
    assert any(turn.source.value == "assistant" for turn in episodes[0].turns)
    assert any(turn.source.value == "tool" for turn in episodes[0].turns)


def test_lme_v2_snapshot_adapter_gate_passes(tmp_path):
    root = _make_lme_v2_fixture(tmp_path)
    result = evaluate_lme_v2_snapshot(
        root,
        question_limit=2,
        trajectories_per_question=1,
        states_per_trajectory=2,
    )

    assert result["passed"] is True
    assert result["metrics"]["raw_ref_coverage"] == 1.0
    assert result["metrics"]["policy_gate_leak_count"] == 0
    assert result["metrics"]["memory_promotion_count"] == 0
    assert (
        result["metrics"]["assistant_candidate_count"]
        == result["metrics"]["assistant_ambiguous_count"]
    )


def test_snapshot_from_hf_cache_layout(tmp_path):
    hf_cache = tmp_path / "hf_cache"
    snapshot = (
        hf_cache
        / "hub"
        / "datasets--xiaowu0162--longmemeval-v2"
        / "snapshots"
        / "abc123"
    )
    fixture = _make_lme_v2_fixture(tmp_path)
    snapshot.mkdir(parents=True, exist_ok=True)
    (snapshot / "questions.jsonl").write_text(
        (fixture / "questions.jsonl").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (snapshot / "trajectories.jsonl").write_text(
        (fixture / "trajectories.jsonl").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (snapshot / "haystacks").mkdir(parents=True, exist_ok=True)
    (snapshot / "haystacks" / "lme_v2_small.json").write_text(
        (fixture / "haystacks" / "lme_v2_small.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    refs = (
        hf_cache
        / "hub"
        / "datasets--xiaowu0162--longmemeval-v2"
        / "refs"
    )
    refs.mkdir(parents=True, exist_ok=True)
    (refs / "main").write_text("abc123", encoding="utf-8")

    assert _snapshot_from_hf_cache(hf_cache) == snapshot


def test_lme_v2_storage_inspection_distinguishes_cache_root_from_snapshot(tmp_path):
    fixture = _make_lme_v2_fixture(tmp_path)
    hf_cache = tmp_path / "hf_cache"
    refs = (
        hf_cache
        / "hub"
        / "datasets--xiaowu0162--longmemeval-v2"
        / "refs"
    )
    refs.mkdir(parents=True, exist_ok=True)
    (refs / "main").write_text("abc123", encoding="utf-8")

    report = inspect_lme_v2_storage(fixture, hf_cache_root=hf_cache)

    assert report["dataset_cache_root_exists"] is True
    assert report["refs_main_exists"] is True
    assert report["refs_snapshot_complete"] is False
    assert report["complete_cache_snapshot_exists"] is False
    assert report["can_build_external_records"] is True
    assert report["root_resolution_source"] == "explicit"
    assert report["resolved_root"] == str(fixture)
