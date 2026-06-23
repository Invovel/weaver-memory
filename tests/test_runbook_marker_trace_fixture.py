import json
from pathlib import Path

from benchmarks.runbook_marker_trace_fixture import (
    evaluate_cards,
    load_dialogue_cards,
    main,
)
from benchmarks.memevobench_adapter import evaluate_runbook_trace


def test_runbook_marker_trace_fixture_contract():
    cards = load_dialogue_cards()
    result = evaluate_cards(cards)
    metrics = result["metrics"]

    assert result["benchmark"] == "runbook-marker-trace-fixture-v0.5"
    assert result["passed"] is True
    assert metrics["card_count"] == 50
    assert metrics["unique_dialogue_ids"] == 50
    assert metrics["turn_min"] >= 10
    assert metrics["turn_max"] <= 20
    assert metrics["complete_trace_count"] >= 40
    assert metrics["online_llm_zero_rate"] == 1.0
    assert metrics["route_accuracy"] == 1.0
    assert metrics["shadow_mode_labeled_rate"] == 1.0
    assert metrics["actual_runtime_unchanged_rate"] == 1.0
    assert metrics["counterfactual_present_rate"] == 1.0
    assert metrics["safety_violation_count"] == 0
    assert metrics["golden_card_count"] == 5
    assert metrics["conflict_candidate_logged_count"] >= 1
    assert metrics["known_bad_path_warning_match_rate"] >= 0.8
    assert metrics["counterfactual_step_reduction"] > 0
    assert metrics["known_bad_action_reduction"] > 0
    assert metrics["evidence_order_improvement"] > 0
    assert metrics["marker_advantage_card_count"] >= 5
    assert metrics["medium_or_high_confidence_advantage_count"] >= 5


def test_runbook_marker_trace_fixture_writes_outputs(tmp_path):
    exit_code = main(["--output-dir", str(tmp_path)])

    assert exit_code == 0
    assert (tmp_path / "raw_results.json").exists()
    assert (tmp_path / "metrics_summary.json").exists()
    assert (tmp_path / "trace_samples.jsonl").exists()
    assert (tmp_path / "counterfactual_notes.jsonl").exists()
    assert (tmp_path / "conflict_candidates.jsonl").exists()
    assert (tmp_path / "trace_advantage.jsonl").exists()
    assert len((tmp_path / "trace_samples.jsonl").read_text(encoding="utf-8").splitlines()) == 50


def test_runbook_marker_trace_fixture_loads_explicit_path():
    fixture = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "validation"
        / "runbook-marker-v0.5"
        / "dialogue_cards.jsonl"
    )
    cards = load_dialogue_cards(fixture)

    assert len(cards) == 50
    assert cards[0].expected["must"]["shadow_mode"] is True
    assert cards[0].expected["must"]["actual_route"] == "thinking"


def test_runbook_marker_golden_card_shadow_contract():
    cards = load_dialogue_cards()
    result = evaluate_cards(cards)
    traces = {
        trace["dialogue_card_id"]: trace
        for trace in result["traces"]
    }

    card_1 = traces["card_001_codex_subscription_failed"]
    assert "baseline_no_marker" in card_1
    assert "memoryweaver_marker_shadow" in card_1
    assert "advantage" in card_1
    assert card_1["shadow_effect"]["shadow_mode"] is True
    assert card_1["marker_recommendation"]["recommended_route"] == "fast_verify"
    assert card_1["actual_runtime"]["actual_route"] == "thinking"
    assert "reinstall_npm" in card_1["marker_recommendation"]["suppressed_actions"]
    assert card_1["counterfactual"]["source"] == "manual_annotation"
    assert card_1["advantage"]["estimated_step_reduction"] > 0
    assert card_1["advantage"]["confidence"] == "high"
    assert card_1["advantage"]["confidence_basis"] == "replay"
    assert card_1["advantage"]["attribution"]["guard_marker_contribution"]["steps_saved"] >= 1

    card_2 = traces["card_002_npm_install_dependency_conflict"]
    assert card_2["conflict_candidates"]
    assert card_2["conflict_candidates"][0]["status"] == "shadow_unresolved"
    assert "conflict_resolution" in card_2["advantage"]["advantage_type"]
    assert card_2["advantage"]["conflict_resolution"]["oscillation_avoided"] is True


def test_memevobench_adapter_runbook_trace_arm():
    fixture = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "validation"
        / "runbook-marker-v0.5"
        / "dialogue_cards.jsonl"
    )
    cards = [
        json.loads(line)
        for line in fixture.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    result = evaluate_runbook_trace(cards)

    assert result["benchmark"] == "runbook-marker-trace-fixture-v0.5"
    assert result["passed"] is True
    assert result["metrics"]["shadow_mode_labeled_rate"] == 1.0
    assert result["metrics"]["actual_runtime_unchanged_rate"] == 1.0
    assert result["metrics"]["counterfactual_step_reduction"] > 0
