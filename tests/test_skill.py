from memoryweaver.composer import PatternComposer
from memoryweaver.evidence import EvidenceLink, EvidenceNode
from memoryweaver.schema import (
    Freshness,
    Layer,
    MemoryItem,
    MemoryType,
    PatternStatus,
    Polarity,
    Source,
    Status,
)
from memoryweaver.skill import SkillRetriever
from memoryweaver.store import MemoryWorkspace


def _seed_skill_workspace(tmp_path):
    workspace = MemoryWorkspace(tmp_path / ".memoryweaver")
    success = MemoryItem(
        id="mem_success",
        polarity=Polarity.POSITIVE,
        memory_type=MemoryType.SUCCESS_PATH,
        content="Check organization and entitlement before reinstalling npm.",
        tags=["codex", "subscription", "organization", "entitlement"],
        source=Source.TERMINAL,
        evidence="verified terminal trace",
        confidence=0.86,
        freshness=Freshness.STABLE,
    )
    avoid = MemoryItem(
        id="mem_avoid",
        polarity=Polarity.NEGATIVE,
        memory_type=MemoryType.FAILED_ATTEMPT,
        content="Blind npm reinstall did not resolve Codex subscription failures.",
        tags=["codex", "subscription", "npm", "reinstall"],
        source=Source.TOOL,
        evidence="tool trace",
        confidence=0.82,
        freshness=Freshness.STABLE,
    )
    workspace.memories.add(success)
    workspace.memories.add(avoid)
    for item in (success, avoid):
        promoted = workspace.memory_policy.promote_to_layer2(item, [])
        workspace.memories.update(promoted)
    node = EvidenceNode(
        id="ev_org",
        text="selected organization fixed the failure",
        source=Source.TERMINAL,
        source_uri="fixture://org",
    )
    workspace.evidence.add_node(node)
    link = EvidenceLink(
        id="link_org",
        evidence_id=node.id,
        memory_id=success.id,
    )
    workspace.evidence.add_link(link)
    composer = PatternComposer(
        workspace.memories,
        workspace.patterns,
        workspace.evidence,
        workspace.memory_policy,
    )
    pattern = composer.compose(
        supporting_memory_ids=[success.id, avoid.id],
        rule="For Codex subscription failures, check organization and entitlement before npm reinstall.",
        applies_when=["subscription load failed"],
        avoid_when=["installation itself failed"],
        success_path=["check selected organization", "check entitlement"],
        failed_path=["reinstall npm first"],
        evidence_link_ids=[link.id],
        scope="project",
    )
    pattern.status = PatternStatus.STABLE
    pattern.confidence = 0.91
    workspace.patterns.update(pattern)
    return workspace


def test_skill_retriever_returns_pattern_and_avoidance_memory(tmp_path):
    workspace = _seed_skill_workspace(tmp_path)
    result = SkillRetriever(workspace.memories, workspace.patterns).retrieve(
        "Codex subscription failed should I reinstall npm first",
        scope="project",
    )

    assert result.skills
    assert result.skills[0].pattern_id
    assert result.avoidance_memories
    assert result.avoidance_memories[0].polarity == Polarity.NEGATIVE
    assert result.recommended_mode in {"fast", "fast_verify"}
    assert "Procedural Skills" in result.render_context()
