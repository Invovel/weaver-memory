from pathlib import Path

from benchmarks.context_capsule_stress_validation import (
    dialogue_cards_to_raw_spans,
    evaluate_stress,
    main,
)
from benchmarks.context_capsule_validation import read_jsonl


def test_dialogue_cards_generate_context_raw_spans():
    repo_root = Path(__file__).resolve().parents[1]
    cards = read_jsonl(
        repo_root
        / "docs"
        / "validation"
        / "runbook-marker-v0.5"
        / "dialogue_cards.jsonl"
    )
    records = dialogue_cards_to_raw_spans(cards)

    assert len(cards) >= 50
    assert len(records) >= 300
    assert {record["content_type"] for record in records} >= {
        "conversation_turn",
        "terminal_log",
        "tool_json",
        "trace_record",
    }
    assert any(record["source"] == "assistant" for record in records)
    assert all(record["expected_capsule"]["raw_retrievable"] for record in records)


def test_context_capsule_stress_validation_passes(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    result = evaluate_stress(
        base_fixture=(
            repo_root
            / "docs"
            / "validation"
            / "context-capsule-v0.5.3"
            / "raw_spans_fixture.jsonl"
        ),
        dialogue_cards_path=(
            repo_root
            / "docs"
            / "validation"
            / "runbook-marker-v0.5"
            / "dialogue_cards.jsonl"
        ),
        workspace_root=tmp_path / ".memoryweaver",
    )

    assert result["passed"] is True
    assert result["metrics"]["card_count"] >= 50
    assert result["metrics"]["dialogue_raw_span_count"] >= 300
    assert result["metrics"]["combined_raw_span_count"] >= 340
    assert result["metrics"]["raw_retrieval_success_rate"] == 1.0
    assert result["metrics"]["trust_inheritance_violation_count"] == 0
    assert result["metrics"]["capsule_promoted_memory_count"] == 0
    assert result["metrics"]["assistant_capsule_count"] > 0
    assert result["hard_gates"]["assistant_capsules_remain_assistant"] is True


def test_context_capsule_stress_writes_outputs(tmp_path):
    exit_code = main(["--output-dir", str(tmp_path)])

    assert exit_code == 0
    assert (tmp_path / "raw_results.json").exists()
    assert (tmp_path / "metrics_summary.json").exists()
    assert (tmp_path / "dialogue_raw_spans.jsonl").exists()
    assert (tmp_path / "capsules.jsonl").exists()
