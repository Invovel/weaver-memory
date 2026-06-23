from benchmarks.external_dataset_adapter_v0_6_4 import (
    FIXTURE_RECORDS,
    evaluate_external_fixture,
)
from memoryweaver.external.adapters import (
    adapt_external_record,
    build_candidate_memories,
    build_context_capsules,
    external_episode_to_raw_spans,
)
from memoryweaver.schema import Layer, Polarity, Source


def test_external_dataset_adapter_spike_passes():
    result = evaluate_external_fixture(FIXTURE_RECORDS)

    assert result["passed"] is True
    assert result["metrics"]["dataset_count"] == 3
    assert result["metrics"]["conversion_success_rate"] >= 0.95
    assert result["metrics"]["raw_ref_coverage"] == 1.0
    assert result["metrics"]["capsule_build_success_rate"] >= 0.95
    assert result["metrics"]["policy_gate_leak_count"] == 0
    assert result["metrics"]["conflict_signal_count"] > 0
    assert result["metrics"]["temporal_signal_count"] > 0


def test_assistant_external_turn_stays_ambiguous_candidate():
    episode = adapt_external_record(
        "locomo",
        {
            "id": "assistant_boundary",
            "conversation": [
                {
                    "speaker": "assistant",
                    "text": "The legacy key might be valid even after the user correction.",
                    "timestamp": "2026-04-02T12:01:00+00:00",
                }
            ],
            "query": "Can the legacy key be trusted?",
            "answer": "No",
        },
    )
    raw_spans = external_episode_to_raw_spans(episode)
    capsules = build_context_capsules(raw_spans)
    memories, violations = build_candidate_memories(capsules)

    assert violations == []
    assert memories[0].source == Source.ASSISTANT
    assert memories[0].layer == Layer.CANDIDATE
    assert memories[0].polarity == Polarity.AMBIGUOUS
    assert memories[0].confidence <= 0.3


def test_external_raw_span_preserves_source_and_raw_ref():
    episode = adapt_external_record(
        "memoryagentbench",
        FIXTURE_RECORDS["memoryagentbench"][0],
    )
    raw_spans = external_episode_to_raw_spans(episode)
    capsules = build_context_capsules(raw_spans)

    raw_ids = {raw_span.id for raw_span in raw_spans}
    assert raw_ids
    assert all(capsule.raw_ref_id in raw_ids for capsule in capsules)
    assert [capsule.source for capsule in capsules] == [
        raw_span.source for raw_span in raw_spans
    ]
