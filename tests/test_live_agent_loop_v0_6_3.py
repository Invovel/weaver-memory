"""Tests for v0.6.3 live agent loop benchmark."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.live_agent_loop_v0_6_3 import (
    _build_memory_context,
    _build_marker_context,
    _build_system_prompt,
    _matches_known_bad,
    _matches_required_evidence,
    _parse_llm_action,
    evaluate_real_agent_loop,
)
from benchmarks.runbook_marker_trace_fixture import DialogueCard, load_dialogue_cards


# ---------------------------------------------------------------------------
# unit tests — no API calls needed
# ---------------------------------------------------------------------------


def test_parse_llm_action_valid_json():
    raw = '{"action": "tool_call", "target": "npm install", "reasoning": "try reinstall"}'
    result = _parse_llm_action(raw)
    assert result["action"] == "tool_call"
    assert result["target"] == "npm install"


def test_parse_llm_action_markdown_fence():
    raw = '```json\n{"action": "check_evidence", "target": "org list", "reasoning": "check org"}\n```'
    result = _parse_llm_action(raw)
    assert result["action"] == "check_evidence"


def test_parse_llm_action_invalid_json():
    raw = "I think we should check the organization first."
    result = _parse_llm_action(raw)
    assert result["action"] == "ask_user"


def test_parse_llm_action_resolve():
    raw = '{"action": "resolve", "target": "org mismatch fixed", "reasoning": "done"}'
    result = _parse_llm_action(raw)
    assert result["action"] == "resolve"


def test_matches_known_bad_reinstall_npm():
    assert _matches_known_bad("reinstall_npm") is True
    assert _matches_known_bad("npm install --force") is True


def test_matches_known_bad_safe_action():
    assert _matches_known_bad("check git status") is False
    assert _matches_known_bad("read config file") is False


def test_matches_required_evidence_org_check():
    assert _matches_required_evidence("check_selected_organization") is True
    assert _matches_required_evidence("check organization list") is True


def test_matches_required_evidence_generic():
    assert _matches_required_evidence("run arbitrary command") is False


def test_build_memory_context_no_memory():
    ctx = _build_memory_context("no_memory", None, [])
    assert ctx == ""


def test_build_memory_context_with_failures():
    events = [
        {
            "step": 1,
            "arm": "mw_memory",
            "action": "tool_call",
            "purpose": "reinstall npm",
            "tool_result": {"status": "failed_known_bad", "signal": "negative"},
        },
    ]
    ctx = _build_memory_context("mw_memory", None, events)
    assert "FAILED" in ctx
    assert "NEGATIVE" in ctx


def test_build_memory_context_with_evidence():
    events = [
        {
            "step": 1,
            "arm": "mw_memory",
            "action": "check_evidence",
            "purpose": "check organization",
            "tool_result": {"status": "evidence_observed", "signal": "positive"},
        },
    ]
    ctx = _build_memory_context("mw_memory", None, events)
    assert "OBSERVED" in ctx
    assert "POSITIVE" in ctx


def test_build_marker_context_no_marker_arm():
    ctx = _build_marker_context("mw_memory", None)
    assert ctx == ""


def test_build_marker_context_with_marker(card_codex_subscription):
    ctx = _build_marker_context("mw_memory_marker", card_codex_subscription)
    assert "KNOWN BAD PATHS" in ctx
    assert "RECOMMENDED EVIDENCE CHECKS" in ctx


def test_build_system_prompt_no_memory():
    prompt = _build_system_prompt("no_memory", "", "", None)
    assert "You are a coding assistant" in prompt
    assert "MemoryWeaver" not in prompt


def test_build_system_prompt_with_memory():
    prompt = _build_system_prompt("mw_memory", "PAST: reinstall npm FAILED", "", None)
    assert "MemoryWeaver" in prompt
    assert "reinstall npm FAILED" in prompt


def test_build_system_prompt_with_marker():
    prompt = _build_system_prompt(
        "mw_memory_marker", "", "KNOWN BAD PATHS: reinstall_npm", None,
    )
    assert "Runbook Marker" in prompt
    assert "KNOWN BAD PATHS" in prompt


# ---------------------------------------------------------------------------
# fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def card_codex_subscription() -> DialogueCard:
    cards = load_dialogue_cards()
    for card in cards:
        if "codex" in card.dialogue_card_id.lower() and "subscription" in card.dialogue_card_id.lower():
            return card
    # Fallback: first card
    return cards[0]


@pytest.fixture
def all_cards() -> list[DialogueCard]:
    return load_dialogue_cards()


# ---------------------------------------------------------------------------
# integration test — mock DeepSeek to avoid real API calls in CI
# ---------------------------------------------------------------------------


def _mock_deepseek_response(action: str, target: str) -> str:
    return json.dumps({"action": action, "target": target, "reasoning": "mock reasoning"})


def test_evaluate_real_agent_loop_with_mock_llm(all_cards, tmp_path):
    """Integration test using a mock LLM that always picks 'check_evidence'."""
    cards = all_cards[:2]  # only 2 cards for speed

    with patch(
        "benchmarks.live_agent_loop_v0_6_3._call_deepseek",
        return_value=_mock_deepseek_response("check_evidence", "check_selected_organization"),
    ):
        # Also patch _get_api_key to avoid env dependency
        with patch(
            "benchmarks.live_agent_loop_v0_6_3._get_api_key",
            return_value="mock-key",
        ):
            result = evaluate_real_agent_loop(cards, api_key="mock-key")

    assert result["task_count"] == 2
    assert result["task_run_count"] == 6  # 2 cards × 3 arms
    assert result["total_llm_calls"] > 0

    # With mock always returning check_evidence, all arms should succeed quickly.
    for arm_stats in result["arms"].values():
        assert arm_stats["average_steps_to_success"] <= 2
        assert arm_stats["evidence_observed_count"] >= 1


def test_evaluate_real_agent_loop_mock_bad_action(all_cards, tmp_path):
    """Mock LLM that picks a known-bad action, verifying it gets flagged."""
    cards = all_cards[:1]

    with patch(
        "benchmarks.live_agent_loop_v0_6_3._call_deepseek",
        return_value=_mock_deepseek_response("tool_call", "npm install --force"),
    ):
        with patch(
            "benchmarks.live_agent_loop_v0_6_3._get_api_key",
            return_value="mock-key",
        ):
            result = evaluate_real_agent_loop(cards, api_key="mock-key")

    no_mem = result["arms"]["no_memory"]
    assert no_mem["known_bad_action_attempts"] >= 1

    # mw_memory_marker should still catch it as known_bad via the tool runtime
    mw_marker = result["arms"]["mw_memory_marker"]
    assert mw_marker["known_bad_action_attempts"] >= 1


def test_real_agent_loop_three_arms_exist(all_cards, tmp_path):
    """Verify all three arms produce output with mock LLM."""
    cards = all_cards[:1]

    with patch(
        "benchmarks.live_agent_loop_v0_6_3._call_deepseek",
        side_effect=[
            _mock_deepseek_response("tool_call", "npm install --force"),     # no_memory step 1
            _mock_deepseek_response("tool_call", "npm install --force"),     # no_memory step 2
            _mock_deepseek_response("ask_user", "what should I try?"),       # no_memory step 3
            _mock_deepseek_response("check_evidence", "check organization"), # mw_memory step 1
            _mock_deepseek_response("resolve", "fixed"),                     # mw_memory step 2
            _mock_deepseek_response("check_evidence", "check organization"), # mw_marker step 1
            _mock_deepseek_response("resolve", "fixed"),                     # mw_marker step 2
        ],
    ):
        with patch(
            "benchmarks.live_agent_loop_v0_6_3._get_api_key",
            return_value="mock-key",
        ):
            result = evaluate_real_agent_loop(cards, api_key="mock-key")

    assert set(result["arms"].keys()) == {"no_memory", "mw_memory", "mw_memory_marker"}
    assert result["total_llm_calls"] == 7  # 3 + 2 + 2
