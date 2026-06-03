"""Evidence node, link, packet, and workspace validation tests."""

import hashlib

import pytest

from memoryweaver.evidence import (
    EvidenceLink,
    EvidenceNode,
    EvidencePacket,
    EvidenceStore,
)
from memoryweaver.schema import MemoryItem, Pattern
from memoryweaver.store import MemoryWorkspace


def test_evidence_node_hash_and_persistence(tmp_path):
    store = EvidenceStore(tmp_path / "nodes.json", tmp_path / "links.json")
    node = EvidenceNode(text="small citable excerpt", source="file", source_uri="doc.md")
    store.add_node(node)

    restored = EvidenceStore(tmp_path / "nodes.json", tmp_path / "links.json")
    assert restored.get_node(node.id).content_hash == hashlib.sha256(
        node.text.encode("utf-8")
    ).hexdigest()


def test_evidence_link_requires_exactly_one_target():
    with pytest.raises(ValueError, match="exactly one"):
        EvidenceLink(evidence_id="ev_1")
    with pytest.raises(ValueError, match="exactly one"):
        EvidenceLink(evidence_id="ev_1", memory_id="mem_1", pattern_id="pat_1")


def test_workspace_validate_reports_dangling_link(tmp_path):
    workspace = MemoryWorkspace(tmp_path)
    workspace.evidence.add_link(
        EvidenceLink(evidence_id="missing", memory_id="missing")
    )

    report = workspace.validate()
    assert report["valid"] is False
    assert "dangling evidence node" in " ".join(report["errors"])
    assert "dangling memory target" in " ".join(report["errors"])


def test_workspace_validate_accepts_node_then_link(tmp_path):
    workspace = MemoryWorkspace(tmp_path)
    memory = MemoryItem(source="terminal", evidence="captured terminal output")
    workspace.memories.add(memory)
    node = EvidenceNode(text="captured terminal output", source="terminal", source_uri="term://1")
    workspace.evidence.add_node(node)
    workspace.evidence.add_link(EvidenceLink(evidence_id=node.id, memory_id=memory.id))
    assert workspace.validate()["valid"] is True


def test_evidence_packet_is_transport_only():
    packet = EvidencePacket(
        query_id="query-1",
        policy_version="retrieval-policy-v1",
        evidence_refs=["ev_1"],
        memory_refs=["mem_1"],
        pattern_refs=["pat_1"],
        conflicts=["conflict-1"],
        degraded_components=["vector-db"],
        recommended_mode="fast_verify",
    )
    assert packet.to_dict()["recommended_mode"] == "fast_verify"


def test_evidence_link_can_target_pattern():
    link = EvidenceLink(evidence_id="ev_1", pattern_id=Pattern().id)
    assert link.pattern_id
    assert link.memory_id == ""
