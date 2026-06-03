"""Canonical provisional Pattern lifecycle tests."""

import pytest

from memoryweaver.composer import PatternComposer
from memoryweaver.evidence import EvidenceLink, EvidenceNode
from memoryweaver.router import InferenceMode, ModeRouter
from memoryweaver.schema import Freshness, MemoryItem, PatternStatus
from memoryweaver.store import MemoryWorkspace


@pytest.fixture
def prepared(tmp_path):
    workspace = MemoryWorkspace(tmp_path)
    memories = []
    for content in (
        "Codex CLI subscription load failed in WSL",
        "Check organization auth state before reinstall",
    ):
        item = MemoryItem(content=content, source="terminal", evidence="captured output")
        workspace.memories.add(item)
        workspace.memory_policy.promote_to_layer2(item, [])
        workspace.memories.update(item)
        memories.append(item)

    node = EvidenceNode(
        text="subscription failure resolved after checking organization auth",
        source="terminal",
        source_uri="term://run-1",
    )
    workspace.evidence.add_node(node)
    link = EvidenceLink(evidence_id=node.id, memory_id=memories[0].id)
    workspace.evidence.add_link(link)
    composer = PatternComposer(
        workspace.memories,
        workspace.patterns,
        workspace.evidence,
        workspace.memory_policy,
    )
    return workspace, composer, memories, link


def compose(composer, memories, link):
    return composer.compose(
        supporting_memory_ids=[item.id for item in memories],
        rule="Codex CLI subscription load failed in WSL check organization auth",
        applies_when=["subscription fails after install"],
        avoid_when=["reinstall first"],
        success_path=["check organization auth"],
        failed_path=["reinstall npm"],
        evidence_link_ids=[link.id],
        scope="project",
    )


def test_compose_defaults_to_provisional(prepared):
    workspace, composer, memories, link = prepared
    pattern = compose(composer, memories, link)
    assert pattern.status == PatternStatus.PROVISIONAL
    assert pattern.rollback_to == [item.id for item in memories]
    assert workspace.patterns.get(pattern.id) is pattern


def test_compose_requires_two_to_four_layer2_memories(prepared):
    _, composer, memories, link = prepared
    with pytest.raises(ValueError, match="2-4"):
        composer.compose(
            [memories[0].id],
            "rule",
            [],
            [],
            [],
            [],
            [link.id],
            "project",
        )


def test_compose_rejects_scope_conflict(prepared):
    workspace, composer, memories, link = prepared
    memories[1].scope = "other"
    workspace.memories.update(memories[1])
    with pytest.raises(ValueError, match="scope"):
        compose(composer, memories, link)


def test_compose_requires_evidence(prepared):
    _, composer, memories, _ = prepared
    with pytest.raises(ValueError, match="EvidenceLink"):
        composer.compose(
            [item.id for item in memories],
            "rule",
            [],
            [],
            [],
            [],
            [],
            "project",
        )


def test_three_successes_across_two_runs_promote_stable(prepared):
    _, composer, memories, link = prepared
    pattern = compose(composer, memories, link)
    composer.record_validation(pattern.id, "run-1", True)
    composer.record_validation(pattern.id, "run-2", True)
    composer.record_validation(pattern.id, "run-2", True)
    stable = composer.promote_stable(pattern.id)
    assert stable.status == PatternStatus.STABLE
    assert stable.confidence == 1.0


def test_failed_validation_rolls_back_and_archive_is_explicit(prepared):
    _, composer, memories, link = prepared
    pattern = compose(composer, memories, link)
    rolled_back = composer.record_validation(pattern.id, "run-failed", False)
    assert rolled_back.status == PatternStatus.ROLLED_BACK
    assert rolled_back.rollback_to == [item.id for item in memories]
    assert composer.archive(pattern.id).status == PatternStatus.ARCHIVED


def test_router_caps_provisional_at_fast_verify(prepared):
    workspace, composer, memories, link = prepared
    pattern = compose(composer, memories, link)
    decision = ModeRouter(
        workspace.memories,
        pattern_store=workspace.patterns,
    ).route(pattern.rule)
    assert decision.mode == InferenceMode.FAST_VERIFY
    assert [item.id for item in decision.matched_patterns] == [pattern.id]


def test_router_allows_fresh_stable_pattern_fast(prepared):
    workspace, composer, memories, link = prepared
    pattern = compose(composer, memories, link)
    pattern.freshness = Freshness.STABLE
    composer.record_validation(pattern.id, "run-1", True)
    composer.record_validation(pattern.id, "run-2", True)
    composer.record_validation(pattern.id, "run-2", True)
    composer.promote_stable(pattern.id)
    decision = ModeRouter(
        workspace.memories,
        pattern_store=workspace.patterns,
    ).route(pattern.rule)
    assert decision.mode == InferenceMode.FAST
