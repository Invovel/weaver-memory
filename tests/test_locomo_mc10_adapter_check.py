import json

from benchmarks.locomo_mc10_adapter_check import run
from memoryweaver.external.locomo_mc10 import build_locomo_mc10_episodes


def _row():
    return {
        "question_id": "conv-1_q0",
        "question": "When did Caroline go to the support group?",
        "question_type": "multi_hop",
        "answer": "7 May 2023",
        "correct_choice_index": 5,
        "num_choices": 10,
        "num_sessions": 2,
        "choices": [
            "20 May 2023",
            "10 May 2023",
            "6 May 2023",
            "8 May 2023",
            "9 May 2023",
            "7 May 2023",
            "12 June 2023",
            "15 May 2023",
            "14 May 2023",
            "7 April 2023",
        ],
        "haystack_session_ids": ["session_1", "session_2"],
        "haystack_session_summaries": [
            "Caroline attended an LGBTQ support group on 7 May 2023.",
            "Caroline later discussed adoption agencies.",
        ],
        "haystack_session_datetimes": ["2023-05-08T13:56:00", "2023-05-25T13:14:00"],
        "haystack_sessions": [
            [
                {"role": "user", "content": "I went to the support group on 7 May 2023."},
                {"role": "assistant", "content": "That date may be relevant later."},
            ],
            [
                {"role": "user", "content": "I am researching adoption agencies."},
                {"role": "assistant", "content": "Keep the support group date separate."},
            ],
        ],
    }


def test_locomo_mc10_row_to_episode_preserves_mc_metadata():
    episode = build_locomo_mc10_episodes([_row()])[0]

    assert episode.dataset_id == "locomo-mc10"
    assert episode.source_repo == "Percena/locomo-mc10"
    assert episode.queries[0].answer == "7 May 2023"
    assert episode.queries[0].metadata["num_choices"] == 10
    assert len(episode.queries[0].metadata["choices"]) == 10
    assert any(turn.source.value == "assistant" for turn in episode.turns)
    assert any(turn.source.value == "file" for turn in episode.turns)


def test_locomo_mc10_adapter_check_fixture_outputs_artifacts(tmp_path):
    input_path = tmp_path / "locomo_mc10_fixture.json"
    input_path.write_text(json.dumps([_row()]), encoding="utf-8")
    output_dir = tmp_path / "locomo-mc10"
    result = run(output_dir, input_path=input_path, sample_limit=1)

    assert result["passed"] is True
    for name in [
        "metrics.json",
        "raw_results.json",
        "converted_samples.jsonl",
        "capsule_samples.jsonl",
        "candidate_memory_samples.jsonl",
        "README.md",
    ]:
        assert (output_dir / name).exists()
    metrics = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["sample_count"] == 1
    assert metrics["choice_10_rate"] == 1
    assert metrics["query_answer_pair_coverage"] == 1
    assert metrics["policy_gate_leak_count"] == 0
    assert metrics["memory_promotion_count"] == 0
    assert metrics["layer3_mutation_count"] == 0
    assert metrics["assistant_candidate_count"] == metrics["assistant_ambiguous_count"]
