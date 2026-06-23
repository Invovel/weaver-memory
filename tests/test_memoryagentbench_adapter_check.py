import json

from benchmarks.memoryagentbench_adapter_check import run
from memoryweaver.external.memoryagentbench import build_memoryagentbench_episodes


def _rows():
    return [
        {
            "_split": "Accurate_Retrieval",
            "_row_idx": 0,
            "context": "Document 1: Normandy is located in France.",
            "questions": json.dumps(["In what country is Normandy located?"]),
            "answers": json.dumps([["France"]]),
            "metadata": json.dumps({"qa_pair_ids": ["retrieval_q1"]}),
        },
        {
            "_split": "Test_Time_Learning",
            "_row_idx": 0,
            "context": "Previous event: user selected movie id 7008.",
            "questions": json.dumps(["What movie id did the user select after learning?"]),
            "answers": json.dumps([["7008"]]),
            "metadata": json.dumps({"qa_pair_ids": ["ttl_q1"], "previous_events": ["selected 7008"]}),
        },
        {
            "_split": "Long_Range_Understanding",
            "_row_idx": 0,
            "context": "A long story context with plot and characters.",
            "questions": json.dumps(["Write a summary of the story."]),
            "answers": json.dumps([["A short summary."]]),
            "metadata": json.dumps({"qa_pair_ids": ["long_q1"]}),
        },
        {
            "_split": "Conflict_Resolution",
            "_row_idx": 0,
            "context": "Fact 1: Apple CEO is Tim Cook. Fact 2: Apple CEO is wrong value.",
            "questions": json.dumps(["Resolve the conflict: who is Apple CEO?"]),
            "answers": json.dumps([["Tim Cook"]]),
            "metadata": json.dumps({"qa_pair_ids": ["conflict_q1"]}),
        },
    ]


def test_memoryagentbench_row_to_episode_parses_json_string_fields():
    episodes = build_memoryagentbench_episodes(_rows())

    assert len(episodes) == 4
    assert episodes[0].dataset_id == "memoryagentbench"
    assert episodes[0].source_repo == "ai-hyz/MemoryAgentBench"
    assert episodes[0].queries[0].query == "In what country is Normandy located?"
    assert episodes[0].queries[0].answer == "France"
    assert any("retrieval" in query.signal_types for episode in episodes for query in episode.queries)
    assert any("temporal" in query.signal_types for episode in episodes for query in episode.queries)
    assert any("conflict" in query.signal_types for episode in episodes for query in episode.queries)


def test_memoryagentbench_adapter_check_fixture_outputs_artifacts(tmp_path):
    input_path = tmp_path / "memoryagentbench_fixture.json"
    input_path.write_text(json.dumps(_rows()), encoding="utf-8")
    output_dir = tmp_path / "memoryagentbench"
    result = run(output_dir, input_path=input_path, sample_limit=4)

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
    assert metrics["split_count"] == 4
    assert metrics["query_answer_pair_coverage"] == 1
    assert metrics["policy_gate_leak_count"] == 0
    assert metrics["memory_promotion_count"] == 0
    assert metrics["layer3_mutation_count"] == 0
    assert metrics["retrieval_signal_count"] > 0
    assert metrics["temporal_signal_count"] > 0
    assert metrics["conflict_signal_count"] > 0
