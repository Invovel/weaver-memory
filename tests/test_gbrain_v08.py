from memoryweaver import (
    GBrainCandidateBundle,
    GBrainCandidateEdge,
    GBrainCandidateNode,
    GBrainCitation,
    GBrainGap,
    GBrainMindMapDocument,
    GBrainScope,
    GBrainSearchHit,
    GBrainSearchResult,
    GBrainThinkResult,
    MemoryWeaverGBrainEngineV08,
    MemoryWorkspace,
)
from memoryweaver.gbrain_v08 import GBrainCandidateBundle
from memoryweaver.graph_schema import GraphNode, GraphNodeType


def test_gbrain_v08_contracts_roundtrip():
    scope = GBrainScope(brain_id="workspace", source_id="repo_a", owner_scope="project")
    bundle = GBrainCandidateBundle(
        scope=scope,
        nodes=[GBrainCandidateNode(node_id="n1", node_type="entity", label="Codex CLI")],
        edges=[GBrainCandidateEdge(source_id="n1", target_id="n2", relation="supports", confidence=0.7)],
        summaries=["Candidate graph summary"],
    )
    search = GBrainSearchResult(
        query="subscription failure",
        scope=scope,
        hits=[
            GBrainSearchHit(
                ref_id="mem_1",
                ref_type="memory",
                title="Check selected organization",
                score=0.91,
                graph_layer="verified",
                evidence=[GBrainCitation(ref_id="evi_1", ref_type="evidence")],
            )
        ],
    )
    think = GBrainThinkResult(
        query="what should I inspect first?",
        scope=scope,
        answer="Check selected organization first.",
        citations=[GBrainCitation(ref_id="mem_1", ref_type="memory", layer="layer_2")],
        gaps=[GBrainGap(kind="freshness", detail="Need a newer entitlement check.")],
    )
    mind_map = GBrainMindMapDocument(
        scope=scope,
        center_query="subscription failure",
        candidate_nodes=[{"id": "n1"}],
        verified_nodes=[{"id": "n2"}],
        runtime_nodes=[{"id": "n3"}],
    )

    assert bundle.to_dict()["scope"]["source_id"] == "repo_a"
    assert search.to_dict()["hits"][0]["graph_layer"] == "verified"
    assert think.to_dict()["gaps"][0]["kind"] == "freshness"
    assert mind_map.to_dict()["runtime_nodes"][0]["id"] == "n3"


def test_gbrain_v08_engine_ingests_candidates_without_authority(tmp_path):
    workspace = MemoryWorkspace(tmp_path / ".memoryweaver")
    engine = MemoryWeaverGBrainEngineV08(workspace)
    scope = GBrainScope(source_id="repo_a")
    result = engine.ingest_candidate_bundle(
        GBrainCandidateBundle(
            scope=scope,
            nodes=[
                GBrainCandidateNode(
                    node_id="activity_stream",
                    node_type="tag",
                    label="activity stream evidence",
                    source_refs=["ev_1"],
                )
            ],
            edges=[
                GBrainCandidateEdge(
                    source_id="activity_stream",
                    target_id="blind_close",
                    relation="limits",
                    confidence=0.7,
                    source_refs=["ev_1"],
                )
            ],
            proposed_by="llm",
            authority_granted=True,
        )
    )

    assert result["accepted_for_storage"] is True
    assert result["authority_granted"] is False
    assert workspace.memories.count() == 0
    assert len(workspace.patterns.list_all()) == 0
    search = engine.search("activity stream before blind close", scope=scope)
    assert search.hits
    assert search.hits[0].graph_layer == "candidate"


def test_gbrain_v08_candidate_bundle_cannot_overwrite_existing_graph_nodes(tmp_path):
    workspace = MemoryWorkspace(tmp_path / ".memoryweaver")
    workspace.graph.add_node(
        GraphNode(
            id="tag_activity_stream",
            node_type=GraphNodeType.TAG,
            label="verified activity stream",
            ref_id="activity_stream",
            metadata={"graph_layer": "verified", "authority_granted": True},
        )
    )
    engine = MemoryWeaverGBrainEngineV08(workspace)
    scope = GBrainScope(source_id="repo_a")

    result = engine.ingest_candidate_bundle(
        GBrainCandidateBundle(
            scope=scope,
            nodes=[
                GBrainCandidateNode(
                    node_id="tag_activity_stream",
                    node_type="tag",
                    label="llm candidate should not overwrite existing tag",
                    source_refs=["ev_1"],
                )
            ],
            proposed_by="llm",
            authority_granted=True,
        )
    )

    original = workspace.graph.get_node("tag_activity_stream")
    candidate = workspace.graph.get_node("v08_tag_tag_activity_stream")
    assert result["authority_granted"] is False
    assert original is not None
    assert original.label == "verified activity stream"
    assert original.metadata["graph_layer"] == "verified"
    assert original.metadata["authority_granted"] is True
    assert candidate is not None
    assert candidate.metadata["graph_layer"] == "candidate"
    assert candidate.metadata["authority_granted"] is False


def test_gbrain_v08_candidate_bundle_cannot_claim_v08_internal_node_ids(tmp_path):
    workspace = MemoryWorkspace(tmp_path / ".memoryweaver")
    workspace.graph.add_node(
        GraphNode(
            id="v08_tag_activity_stream",
            node_type=GraphNodeType.TAG,
            label="promoted activity stream",
            ref_id="activity_stream",
            metadata={"graph_layer": "verified", "authority_granted": True},
        )
    )
    engine = MemoryWeaverGBrainEngineV08(workspace)
    scope = GBrainScope(source_id="repo_a")

    result = engine.ingest_candidate_bundle(
        GBrainCandidateBundle(
            scope=scope,
            nodes=[
                GBrainCandidateNode(
                    node_id="v08_tag_activity_stream",
                    node_type="tag",
                    label="llm candidate should not claim internal id",
                    source_refs=["ev_1"],
                )
            ],
            proposed_by="llm",
            authority_granted=True,
        )
    )

    original = workspace.graph.get_node("v08_tag_activity_stream")
    candidate = workspace.graph.get_node("v08_tag_v08_tag_activity_stream")
    assert result["authority_granted"] is False
    assert original is not None
    assert original.label == "promoted activity stream"
    assert original.metadata["graph_layer"] == "verified"
    assert original.metadata["authority_granted"] is True
    assert candidate is not None
    assert candidate.metadata["graph_layer"] == "candidate"
    assert candidate.metadata["authority_granted"] is False
