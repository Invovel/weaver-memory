"""Minimal GBrain/tag-linking tests."""

import pytest

from memoryweaver.composer import PatternComposer
from memoryweaver.evidence import EvidenceLink, EvidenceNode
from memoryweaver.graph_linker import GraphLinker, tag_node_id
from memoryweaver.graph_retriever import GraphRetriever
from memoryweaver.graph_schema import (
    GraphEdge,
    GraphNode,
    GraphNodeType,
    GraphProposal,
    GraphRelation,
)
from memoryweaver.graph_store import GraphStore
from memoryweaver.retriever import VerifiedRetriever
from memoryweaver.router import InferenceMode, ModeRouter
from memoryweaver.schema import MemoryItem, PatternStatus, Polarity
from memoryweaver.store import MemoryWorkspace


def test_graph_schema_roundtrip_and_proposal(tmp_path):
    store = GraphStore(tmp_path / "graph.json")
    node = GraphNode(
        id="tag_codex_subscription",
        node_type=GraphNodeType.TAG,
        label="codex_subscription",
        ref_id="codex_subscription",
    )
    edge = GraphEdge(
        id="edge_001",
        source_id=node.id,
        target_id="tag_selected_organization",
        relation=GraphRelation.RELATED_TO,
        confidence=0.7,
    )
    store.add_node(node)
    store.add_node(GraphNode(
        id="tag_selected_organization",
        node_type=GraphNodeType.TAG,
        label="selected_organization",
        ref_id="selected_organization",
    ))
    store.add_edge(edge)
    store.add_proposal(GraphProposal(
        proposal_type="link_tags",
        source="llm",
        from_text="codex subscription failed",
        to_text="selected organization",
        relation=GraphRelation.RELATED_TO,
        reason="Both appeared in prior failed subscription loading cases.",
        confidence=0.52,
    ))

    restored = GraphStore(tmp_path / "graph.json")
    assert restored.get_node(node.id).node_type == GraphNodeType.TAG
    assert restored.get_edge(edge.id).relation == GraphRelation.RELATED_TO
    assert restored.list_proposals()[0].decision == "pending"


def test_graph_store_reports_dangling_refs(tmp_path):
    store = GraphStore(tmp_path / "graph.json")
    store.add_node(GraphNode(
        id="memnode_missing",
        node_type=GraphNodeType.MEMORY,
        label="missing",
        ref_id="missing",
    ))
    assert "dangling graph memory node" in " ".join(store.validate_refs(
        memory_ids=set(),
        evidence_ids=set(),
        pattern_ids=set(),
    ))


@pytest.fixture
def graph_workspace(tmp_path):
    workspace = MemoryWorkspace(tmp_path)
    memories = []
    for content, tags in [
        (
            "Codex CLI subscription load failed in WSL",
            ["codex_subscription_failed", "wsl", "codex_cli"],
        ),
        (
            "Selected organization was wrong and caused subscription loading failure",
            ["selected_organization", "subscription_load_failed"],
        ),
        (
            "Reinstalling npm did not fix Codex subscription failure",
            ["npm_reinstall_failed", "subscription_load_failed"],
        ),
    ]:
        item = MemoryItem(
            content=content,
            tags=tags,
            source="terminal",
            evidence="captured terminal output",
            confidence=0.9,
        )
        workspace.memories.add(item)
        workspace.memory_policy.promote_to_layer2(item, [])
        workspace.memories.update(item)
        memories.append(item)

    assistant = MemoryItem(
        content="Assistant guessed that VPN was the root cause",
        tags=["codex_subscription_failed", "vpn_guess"],
        source="assistant",
        polarity=Polarity.AMBIGUOUS,
        confidence=1.0,
    )
    workspace.memories.add(assistant)

    linker = GraphLinker(workspace.graph)
    for memory in memories + [assistant]:
        linker.link_memory_tags(memory)
    linker.link_tags(
        "codex_subscription_failed",
        "selected_organization",
        GraphRelation.SAME_ISSUE_AS,
        confidence=0.8,
        source="rule",
    )
    linker.link_tags(
        "npm_reinstall_failed",
        "npm_root_cause",
        GraphRelation.CONTRADICTS,
        confidence=0.8,
        source="rule",
    )
    return workspace, memories, assistant


def test_graph_tag_expansion_and_candidate_search(graph_workspace):
    workspace, memories, assistant = graph_workspace
    graph_retriever = GraphRetriever(
        workspace.graph,
        VerifiedRetriever(workspace.memories),
        workspace.memories.count(),
    )

    expanded = graph_retriever.expand_tags(["codex_subscription_failed"])
    assert "selected_organization" in expanded

    result = graph_retriever.search_with_graph_candidates(
        "codex org problem",
        ["codex_subscription_failed"],
        threshold=0.0,
    )
    result_ids = [item.id for item in result.results]
    assert memories[0].id in result.candidate_memory_ids
    assert memories[1].id in result.candidate_memory_ids
    assert assistant.id in result.candidate_memory_ids
    assert assistant.id not in result_ids
    assert result.candidate_reduction_ratio > 0


def test_evidence_and_pattern_lineage_are_graph_addressable(graph_workspace):
    workspace, memories, _ = graph_workspace
    linker = GraphLinker(workspace.graph)
    node = EvidenceNode(
        text="codex --version worked but subscription failed",
        source="terminal",
        source_uri="term://1",
    )
    workspace.evidence.add_node(node)
    evidence_link = EvidenceLink(evidence_id=node.id, memory_id=memories[0].id)
    workspace.evidence.add_link(evidence_link)
    linker.link_evidence(evidence_link, evidence_label=node.text)

    composer = PatternComposer(
        workspace.memories,
        workspace.patterns,
        workspace.evidence,
        workspace.memory_policy,
    )
    pattern = composer.compose(
        supporting_memory_ids=[memories[0].id, memories[1].id],
        rule="Codex subscription load failed check selected organization",
        applies_when=["subscription failed"],
        avoid_when=["reinstall npm first"],
        success_path=["check organization"],
        failed_path=["npm reinstall"],
        evidence_link_ids=[evidence_link.id],
        scope="project",
    )
    lineage_edges = linker.link_pattern_lineage(pattern)
    assert len(lineage_edges) == 2
    assert workspace.validate()["valid"] is True
    assert workspace.graph.get_node(f"patnode_{pattern.id}").ref_id == pattern.id


def test_graph_does_not_change_layer3_routing(graph_workspace):
    workspace, memories, _ = graph_workspace
    linker = GraphLinker(workspace.graph)
    node = EvidenceNode(
        text="organization issue was linked to subscription failure",
        source="terminal",
        source_uri="term://2",
    )
    workspace.evidence.add_node(node)
    evidence_link = EvidenceLink(evidence_id=node.id, memory_id=memories[0].id)
    workspace.evidence.add_link(evidence_link)
    composer = PatternComposer(
        workspace.memories,
        workspace.patterns,
        workspace.evidence,
        workspace.memory_policy,
    )
    pattern = composer.compose(
        supporting_memory_ids=[memories[0].id, memories[1].id],
        rule="Codex subscription load failed check selected organization",
        applies_when=["subscription failed"],
        avoid_when=["reinstall npm first"],
        success_path=["check organization"],
        failed_path=["npm reinstall"],
        evidence_link_ids=[evidence_link.id],
        scope="project",
    )
    linker.ensure_pattern(pattern)
    assert pattern.status == PatternStatus.PROVISIONAL
    decision = ModeRouter(
        workspace.memories,
        pattern_store=workspace.patterns,
    ).route("Codex subscription load failed check selected organization")
    assert decision.mode == InferenceMode.FAST_VERIFY


def test_tag_node_id_is_stable():
    assert tag_node_id("Codex subscription failed") == "tag_codex_subscription_failed"
