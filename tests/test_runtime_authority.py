"""Tests for RuntimeMemoryAuthority — the core runtime intervention layer."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memoryweaver.policy import MemoryPolicy, RetrievalPolicy
from memoryweaver.runtime_authority import (
    CoreIssueRecord,
    DecisionLedger,
    HarnessMarkerRecord,
    MarkerStore,
    RuntimeMemoryAuthority,
    RuntimePolicyDecision,
    create_runtime_authority,
)
from memoryweaver.schema import Freshness, Layer, MemoryItem, MemoryType, Polarity, Source, Status
from memoryweaver.store import MemoryStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def memory_store():
    store = MemoryStore()
    items = [
        MemoryItem(
            id="mem_org_fix",
            content="Codex subscription failure fixed by selecting correct organization.",
            tags=["codex", "subscription", "organization"],
            source=Source.TERMINAL,
            polarity=Polarity.POSITIVE,
            evidence="terminal confirmed org switch",
            confidence=0.95,
            freshness=Freshness.STABLE,
        ),
        MemoryItem(
            id="mem_assistant_bad",
            content="Always reinstall npm to fix subscription errors.",
            tags=["codex", "subscription", "npm"],
            source=Source.ASSISTANT,
            polarity=Polarity.AMBIGUOUS,
            confidence=0.3,
            freshness=Freshness.STABLE,
        ),
        MemoryItem(
            id="mem_avoid_force",
            content="Do NOT use npm install --force — it corrupts lockfile.",
            tags=["npm", "install", "avoid"],
            source=Source.USER,
            polarity=Polarity.NEGATIVE,
            memory_type=MemoryType.AVOIDANCE_RULE,
            confidence=0.9,
            freshness=Freshness.STABLE,
        ),
        MemoryItem(
            id="mem_docker_latest",
            content="Do NOT docker push latest in CI — overwrites production tag.",
            tags=["docker", "push", "avoid"],
            source=Source.USER,
            polarity=Polarity.NEGATIVE,
            memory_type=MemoryType.AVOIDANCE_RULE,
            confidence=0.9,
            freshness=Freshness.STABLE,
        ),
        MemoryItem(
            id="mem_tool_noise",
            content="Tool output claims API key presence proves subscription entitlement.",
            tags=["codex", "api_key"],
            source=Source.TOOL,
            polarity=Polarity.NEUTRAL,
            confidence=0.5,
            freshness=Freshness.STABLE,
        ),
    ]
    # Use a fresh in-memory store (no previous test leakage)
    for item in items:
        store.add(item)
    return store


@pytest.fixture
def seeded_marker_store():
    ms = MarkerStore()
    ms.add_issue(CoreIssueRecord(
        issue_id="ci_codex_org",
        title="Codex subscription failure often from org entitlement mismatch",
        scope={"project": "weaver-memory", "environment": "WSL", "tool": "Codex CLI"},
        trigger_tags=["codex", "subscription", "failed"],
        trigger_query_patterns=["subscription failed", "codex not working"],
        supporting_memory_ids=["mem_org_fix"],
        confidence=0.88,
        status="active",
    ))
    ms.add_marker(HarnessMarkerRecord(
        marker_id="hm_avoid_npm_subscription",
        source_issue_id="ci_codex_org",
        marker_type="guard",
        level="L3_guard",
        trigger_tags=["codex", "subscription"],
        trigger_query_patterns=["subscription failed", "reinstall", "npm"],
        suppressed_actions=["reinstall_npm", "npm_install_force", "reset_auth_files"],
        required_evidence=["check_selected_organization", "check_active_account"],
        recommended_route="fast_verify",
        max_route="fast_verify",
        status="active",
    ))
    return ms


@pytest.fixture
def runtime(memory_store, seeded_marker_store):
    return RuntimeMemoryAuthority(memory_store, marker_store=seeded_marker_store)


# ---------------------------------------------------------------------------
# MarkerStore
# ---------------------------------------------------------------------------


def test_marker_store_match_by_tags(seeded_marker_store):
    matched = seeded_marker_store.match(
        "Codex subscription failed again", ["codex", "subscription"]
    )
    assert len(matched) == 1
    assert matched[0].marker_id == "hm_avoid_npm_subscription"


def test_marker_store_match_by_query_pattern(seeded_marker_store):
    matched = seeded_marker_store.match(
        "Should I reinstall npm?", ["codex"]
    )
    assert len(matched) == 1


def test_marker_store_no_match(seeded_marker_store):
    matched = seeded_marker_store.match(
        "How do I configure ESLint?", ["eslint"]
    )
    assert len(matched) == 0


def test_marker_store_candidate_not_matched():
    ms = MarkerStore()
    ms.add_marker(HarnessMarkerRecord(
        marker_id="hm_candidate",
        source_issue_id="ci_x",
        marker_type="route",
        level="L0_trace",
        trigger_tags=["test"],
        trigger_query_patterns=["test"],
        suppressed_actions=[],
        required_evidence=[],
        recommended_route="thinking",
        max_route="fast_verify",
        status="candidate",
    ))
    matched = ms.match("test", ["test"])
    assert len(matched) == 0  # candidate markers don't match


# ---------------------------------------------------------------------------
# DecisionLedger
# ---------------------------------------------------------------------------


def test_ledger_hash_chain(runtime, memory_store):
    decision = runtime.evaluate("test", ["test"], "mw_memory", 1)
    assert len(runtime.ledger.decisions) == 1
    assert runtime.ledger.validate_chain() == []


def test_ledger_multiple_decisions_form_chain(runtime, memory_store):
    for i in range(5):
        runtime.evaluate(f"test {i}", ["test"], "mw_marker", i + 1)
    assert len(runtime.ledger.decisions) == 5
    assert runtime.ledger.validate_chain() == []


def test_ledger_tamper_detection(runtime, memory_store):
    runtime.evaluate("test", ["test"], "mw_memory", 1)
    # Tamper with a decision
    runtime.ledger._decisions[0]["marker_activated"] = True
    errors = runtime.ledger.validate_chain()
    assert len(errors) > 0


# ---------------------------------------------------------------------------
# RuntimeMemoryAuthority.evaluate
# ---------------------------------------------------------------------------


def test_no_memory_arm_returns_empty_context(runtime):
    decision = runtime.evaluate(
        "Codex subscription failed", ["codex"], "no_memory", 1
    )
    assert decision.arm == "no_memory"
    assert len(decision.allowed_memories) == 0
    assert len(decision.blocked_memories) == 0
    assert not decision.marker_activated


def test_mw_memory_arm_retrieves_verified_only(runtime):
    decision = runtime.evaluate(
        "Codex subscription failed", ["codex", "subscription"], "mw_memory", 1
    )
    # Should retrieve the terminal-verified org fix, block assistant injection
    allowed_ids = {m.id for m in decision.allowed_memories}
    blocked_ids = {m.id for m in decision.blocked_memories}

    assert "mem_org_fix" in allowed_ids
    assert "mem_assistant_bad" in blocked_ids


def test_mw_marker_arm_activates_marker(runtime):
    decision = runtime.evaluate(
        "Codex subscription failed again. Should I reinstall npm?",
        ["codex", "subscription"],
        "mw_marker",
        1,
    )
    assert decision.marker_activated
    assert decision.marker_id == "hm_avoid_npm_subscription"
    assert "reinstall_npm" in decision.suppressed_actions
    assert "check_selected_organization" in decision.required_evidence
    assert decision.recommended_route == "fast_verify"
    assert decision.max_route == "fast_verify"


def test_mw_marker_arm_no_match(runtime):
    decision = runtime.evaluate(
        "How do I configure ESLint?", ["eslint"], "mw_marker", 1
    )
    assert not decision.marker_activated


def test_safety_counters_always_zero(runtime):
    decision = runtime.evaluate("test", ["test"], "mw_marker", 1)
    assert decision.tool_execution_count == 0
    assert decision.memory_promotion_count == 0
    assert decision.layer3_mutation_count == 0
    assert decision.online_llm_call_count == 0


def test_negative_memory_retrieved_as_avoidance(runtime):
    decision = runtime.evaluate(
        "npm install --force is it safe?", ["npm", "install"], "mw_memory", 1
    )
    allowed_ids = {m.id for m in decision.allowed_memories}
    assert "mem_avoid_force" in allowed_ids


# ---------------------------------------------------------------------------
# RuntimeMemoryAuthority.build_context
# ---------------------------------------------------------------------------


def test_build_context_no_memory(runtime):
    decision = runtime.evaluate("test", ["test"], "no_memory", 1)
    ctx = runtime.build_context(decision)
    assert ctx == ""


def test_build_context_with_verified_memories(runtime):
    decision = runtime.evaluate(
        "Codex subscription", ["codex"], "mw_memory", 1
    )
    ctx = runtime.build_context(decision)
    assert "Relevant Past Experience" in ctx
    assert "org fix" in ctx
    assert "reinstall npm" not in ctx  # assistant injection blocked


def test_build_context_with_marker_guidance(runtime):
    decision = runtime.evaluate(
        "Codex subscription failed. Reinstall npm?",
        ["codex", "subscription"],
        "mw_marker",
        1,
    )
    ctx = runtime.build_context(decision)
    assert "Diagnostic Guidance" in ctx
    assert "KNOWN BAD PATHS" in ctx
    assert "reinstall_npm" in ctx
    assert "RECOMMENDED EVIDENCE" in ctx
    assert "check_selected_organization" in ctx
    assert "fast_verify" in ctx


def test_build_context_never_shows_blocked_memories(runtime):
    decision = runtime.evaluate(
        "Codex subscription", ["codex"], "mw_memory", 1
    )
    ctx = runtime.build_context(decision)
    assert "Always reinstall npm" not in ctx


# ---------------------------------------------------------------------------
# RuntimeMemoryAuthority.record_outcome
# ---------------------------------------------------------------------------


def test_record_outcome_known_bad_attempted(runtime):
    decision = runtime.evaluate(
        "Codex subscription failed. Reinstall npm?",
        ["codex", "subscription"],
        "mw_marker",
        1,
    )
    checks = runtime.record_outcome(decision, "tool_call", "reinstall npm")
    assert checks["known_bad_attempted"] is True


def test_record_outcome_known_bad_avoided(runtime):
    decision = runtime.evaluate(
        "Codex subscription failed. Reinstall npm?",
        ["codex", "subscription"],
        "mw_marker",
        1,
    )
    checks = runtime.record_outcome(decision, "check_evidence", "check_selected_organization")
    assert checks["known_bad_attempted"] is False
    assert checks["evidence_checked:check_selected_organization"] is True


def test_record_outcome_no_marker(runtime):
    decision = runtime.evaluate("test", ["test"], "mw_memory", 1)
    checks = runtime.record_outcome(decision, "tool_call", "anything")
    assert checks == {}  # No marker → no compliance checks


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def test_create_runtime_authority_with_seed_data(memory_store):
    core_issues = [{
        "id": "ci_test",
        "title": "Test issue",
        "scope": {},
        "trigger_tags": ["test"],
        "trigger_query_patterns": ["test"],
        "supporting_memory_ids": [],
        "confidence": 0.8,
        "status": "active",
    }]
    markers = [{
        "id": "hm_test",
        "source_issue_id": "ci_test",
        "marker_type": "guard",
        "level": "L3_guard",
        "trigger_tags": ["test"],
        "trigger_query_patterns": ["test"],
        "suppressed_actions": ["bad_action"],
        "required_evidence": ["check_something"],
        "recommended_route": "fast_verify",
        "max_route": "fast_verify",
        "status": "active",
    }]
    rt = create_runtime_authority(memory_store, core_issues=core_issues, markers=markers)
    decision = rt.evaluate("test", ["test"], "mw_marker", 1)
    assert decision.marker_activated
    assert "bad_action" in decision.suppressed_actions
