import json

from benchmarks.layer3_path_promotion_lme_v2 import run
from memoryweaver.evaluation import (
    LongMemEvalPathPromotionProtocol,
    build_path_promotion_families_from_lme_v2,
)
from memoryweaver.external.longmemeval_v2 import build_lme_v2_external_episodes


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
                "question_type": "workflow-knowledge",
                "question": "Which evidence should be checked before closing?",
                "answer": "activity stream",
                "eval_function": "exact",
            },
            {
                "id": "q002",
                "domain": "enterprise",
                "environment": "workarena",
                "question_type": "dynamic-environment",
                "question": "What is the latest state after the tool action?",
                "answer": "closed complete",
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
                        "action": "click('Activity')",
                        "thought": "Inspect evidence before updating state.",
                        "accessibility_tree": "RootWebArea Incident Activity Stream",
                        "screenshot": "screenshots/t001/0.png",
                    },
                    {
                        "state_index": 1,
                        "step": 1,
                        "url": "https://example.test/incident",
                        "action": "click('Close')",
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


def test_build_path_promotion_families_from_lme_v2(tmp_path):
    root = _make_lme_v2_fixture(tmp_path)
    episodes, _ = build_lme_v2_external_episodes(
        root,
        question_limit=2,
        trajectories_per_question=1,
        states_per_trajectory=2,
    )
    families, derivation = build_path_promotion_families_from_lme_v2(episodes)

    assert len(families) == 2
    assert len(derivation) == 2
    assert all(family.required_evidence for family in families)
    assert all(family.stale_action for family in families)
    assert all(family.target_tasks for family in families)


def test_lme_v2_path_promotion_protocol_runs_on_fixture(tmp_path):
    root = _make_lme_v2_fixture(tmp_path)
    result = LongMemEvalPathPromotionProtocol(
        workspace_root=tmp_path / ".memoryweaver-lme-v2-path",
        input_root=root,
        question_limit=2,
        trajectories_per_question=1,
        states_per_trajectory=2,
    ).run()

    assert result.passed is True
    assert result.metrics["real_snapshot_family_count"] == 2
    assert result.metrics["latest_path_selection_accuracy"] == 1.0


def test_lme_v2_path_promotion_outputs_required_files(tmp_path):
    root = _make_lme_v2_fixture(tmp_path)
    output_dir = tmp_path / "layer3-path-promotion-lme-v2"
    result = run(
        output_dir,
        input_root=root,
        question_limit=2,
        trajectories_per_question=1,
        states_per_trajectory=2,
    )

    assert result["passed"] is True
    for name in [
        "raw_results.json",
        "snapshot.json",
        "families.jsonl",
        "path_catalog.jsonl",
        "task_runs.jsonl",
        "metrics.json",
        "derivation_samples.jsonl",
        "README.md",
    ]:
        assert (output_dir / name).exists()
