"""Optional LLM provider and GraphProposal review tests."""

from memoryweaver.config import MemoryWeaverConfig, load_env_file
from memoryweaver.evidence import EvidenceStore
from memoryweaver.graph.budget import ProposalBudgetGate
from memoryweaver.graph.proposal import LLMGraphProposalService
from memoryweaver.graph.evidence_binder import GraphEvidenceBinder
from memoryweaver.graph.evidence_support import EvidenceSupport, EvidenceSupportCheck
from memoryweaver.evidence import EvidenceNode
from memoryweaver.graph.reviewer import GraphProposalReviewPolicy
from memoryweaver.graph.linker import ReviewedGraphLinker
from memoryweaver.graph_linker import tag_node_id
from memoryweaver.graph_schema import GraphProposal, GraphRelation
from memoryweaver.graph_store import GraphStore
from memoryweaver.providers.base import ProviderRequest, provider_from_config
from memoryweaver.providers.deepseek_provider import DeepSeekGraphProposalProvider


def test_env_example_defaults_keep_llm_graph_proposals_disabled():
    config = MemoryWeaverConfig.from_env(env={}, env_file=".env.example")
    assert config.enable_llm_graph_proposal is False
    assert config.graph_proposals_available() is False


def test_no_api_key_means_remote_provider_unavailable():
    config = MemoryWeaverConfig.from_env(env={
        "MEMORYWEAVER_ENABLE_LLM_GRAPH_PROPOSAL": "true",
        "MEMORYWEAVER_LLM_PROVIDER": "openai",
        "OPENAI_API_KEY": "",
    })
    provider = provider_from_config(config)
    assert provider.available() is False
    assert provider.propose_graph_links(ProviderRequest(tags=["a", "b"])) == []


def test_local_provider_outputs_only_graph_proposal():
    config = MemoryWeaverConfig.from_env(env={
        "MEMORYWEAVER_ENABLE_LLM_GRAPH_PROPOSAL": "true",
        "MEMORYWEAVER_LLM_PROVIDER": "local",
        "MEMORYWEAVER_LLM_PROPOSAL_CONFIDENCE_CAP": "0.6",
    })
    service = LLMGraphProposalService(config)
    proposals = service.propose(tags=[
        "codex_subscription_failed",
        "selected_organization",
    ])
    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.source == "llm"
    assert proposal.from_node == "codex_subscription_failed"
    assert proposal.to_node == "selected_organization"
    assert proposal.status == "pending"
    assert proposal.requires_review is True
    assert proposal.confidence <= 0.6


def test_deepseek_provider_parses_graph_proposals_without_writing_edges():
    config = MemoryWeaverConfig.from_env(env={
        "MEMORYWEAVER_ENABLE_LLM_GRAPH_PROPOSAL": "true",
        "MEMORYWEAVER_LLM_PROVIDER": "deepseek",
        "MEMORYWEAVER_LLM_MODEL": "deepseek-v4-pro",
        "DEEPSEEK_API_KEY": "test-key",
        "MEMORYWEAVER_LLM_PROPOSAL_CONFIDENCE_CAP": "0.6",
    })
    provider = DeepSeekGraphProposalProvider(config)

    def fake_post(payload):
        assert payload["model"] == "deepseek-v4-pro"
        return {
            "choices": [{
                "message": {
                    "content": (
                        '{"proposals":[{"from_tag":"codex_subscription_failed",'
                        '"to_tag":"selected_organization",'
                        '"relation":"related_to","reason":"same issue",'
                        '"confidence":0.91,"status":"pending",'
                        '"requires_review":true}]}'
                    )
                }
            }]
        }

    provider._post_json = fake_post
    proposals = provider.propose_graph_links(ProviderRequest(
        query="codex org problem",
        tags=["codex_subscription_failed", "selected_organization"],
    ))
    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.from_node == "codex_subscription_failed"
    assert proposal.to_node == "selected_organization"
    assert proposal.confidence == 0.6
    assert proposal.requires_review is True
    assert proposal.metadata["prompt_version"] == "graph_proposal_deepseek_v0.4.2"


def test_deepseek_provider_preserves_evidence_grounded_confidence():
    config = MemoryWeaverConfig.from_env(env={
        "MEMORYWEAVER_ENABLE_LLM_GRAPH_PROPOSAL": "true",
        "MEMORYWEAVER_LLM_PROVIDER": "deepseek",
        "MEMORYWEAVER_LLM_MODEL": "deepseek-v4-pro",
        "DEEPSEEK_API_KEY": "test-key",
        "MEMORYWEAVER_LLM_PROPOSAL_CONFIDENCE_CAP": "0.6",
    })
    provider = DeepSeekGraphProposalProvider(config)

    def fake_post(_payload):
        return {
            "choices": [{
                "message": {
                    "content": (
                        '{"proposals":[{"from_tag":"codex_subscription_failed",'
                        '"to_tag":"selected_organization",'
                        '"relation":"related_to","reason":"evidence grounded",'
                        '"confidence":0.82,"evidence_ids":["ev_1"],'
                        '"risk":"low","requires_review":true}]}'
                    )
                }
            }]
        }

    provider._post_json = fake_post
    proposals = provider.propose_graph_links(ProviderRequest(tags=["a", "b"]))
    assert proposals[0].confidence == 0.82
    assert proposals[0].evidence_ids == ["ev_1"]


def test_reviewer_keeps_missing_evidence_pending(tmp_path):
    graph = GraphStore(tmp_path / "graph.json")
    proposal = GraphProposal(
        proposal_type="link_tags",
        source="llm",
        from_node="codex_subscription_failed",
        to_node="selected_organization",
        relation=GraphRelation.RELATED_TO,
        reason="Both appeared together.",
        confidence=0.9,
    )
    review = GraphProposalReviewPolicy(graph).review(proposal)
    assert review.decision == "pending"
    assert review.confidence == 0.6
    assert "missing evidence link" in review.reasons
    assert graph.list_edges() == []


def test_evidence_binder_marks_auto_bound_evidence_candidate(tmp_path):
    evidence = EvidenceStore(tmp_path / "nodes.json", tmp_path / "links.json")
    evidence.add_node(EvidenceNode(
        id="ev_org",
        text="selected organization fixed codex subscription failed",
        source="terminal",
        source_uri="fixture://org",
    ))
    proposal = GraphProposal(
        proposal_type="link_tags",
        source="llm",
        from_node="codex_subscription_failed",
        to_node="selected_organization",
        relation=GraphRelation.RELATED_TO,
        confidence=0.55,
    )
    bindings = GraphEvidenceBinder(evidence).bind(proposal)
    assert bindings[0].evidence_id == "ev_org"
    assert proposal.metadata["evidence_link_states"]["ev_org"] == "candidate_evidence_link"
    review = GraphProposalReviewPolicy(
        GraphStore(tmp_path / "graph.json"),
        evidence_check=EvidenceSupportCheck(evidence),
    ).review(proposal)
    assert review.decision == "accept"
    assert "candidate evidence passed exact support check" in review.reasons


def test_evidence_support_distinguishes_exact_partial_and_unsupported(tmp_path):
    evidence = EvidenceStore(tmp_path / "nodes.json", tmp_path / "links.json")
    evidence.add_node(EvidenceNode(
        id="ev_exact",
        text="User confirmation: selected organization fixed codex subscription failed",
        source="terminal",
        source_uri="fixture://exact",
    ))
    evidence.add_node(EvidenceNode(
        id="ev_partial",
        text="subscription and organization appeared in troubleshooting notes",
        source="terminal",
        source_uri="fixture://partial",
    ))
    evidence.add_node(EvidenceNode(
        id="ev_noise",
        text="weather API key was valid",
        source="terminal",
        source_uri="fixture://noise",
    ))
    checker = EvidenceSupportCheck(evidence)
    exact = GraphProposal(
        proposal_type="link_tags",
        source="llm",
        from_node="codex_subscription_failed",
        to_node="selected_organization",
        relation=GraphRelation.RELATED_TO,
        evidence_links=["ev_exact"],
    )
    partial = GraphProposal(
        proposal_type="link_tags",
        source="llm",
        from_node="codex_subscription_failed",
        to_node="selected_organization",
        relation=GraphRelation.RELATED_TO,
        evidence_links=["ev_partial"],
    )
    unsupported = GraphProposal(
        proposal_type="link_tags",
        source="llm",
        from_node="codex_subscription_failed",
        to_node="selected_organization",
        relation=GraphRelation.RELATED_TO,
        evidence_links=["ev_noise"],
    )
    assert checker.check(exact).status == EvidenceSupport.SUPPORTS_EXACT
    assert checker.check(partial).status == EvidenceSupport.SUPPORTS_PARTIAL
    assert checker.check(unsupported).status == EvidenceSupport.DOES_NOT_SUPPORT


def test_evidence_support_does_not_treat_single_shared_token_as_exact(tmp_path):
    evidence = EvidenceStore(tmp_path / "nodes.json", tmp_path / "links.json")
    evidence.add_node(EvidenceNode(
        id="ev_org",
        text="selected organization fixed codex subscription failed",
        source="terminal",
        source_uri="fixture://org",
    ))
    proposal = GraphProposal(
        proposal_type="link_tags",
        source="llm",
        from_node="codex_subscription_failed",
        to_node="codex_cli",
        relation=GraphRelation.RELATED_TO,
        evidence_links=["ev_org"],
    )
    assert EvidenceSupportCheck(evidence).check(proposal).status != EvidenceSupport.SUPPORTS_EXACT


def test_reviewed_linker_writes_edge_only_after_accept(tmp_path):
    graph = GraphStore(tmp_path / "graph.json")
    proposal = GraphProposal(
        proposal_type="link_tags",
        source="llm",
        from_node="codex_subscription_failed",
        to_node="selected_organization",
        relation=GraphRelation.RELATED_TO,
        reason="Both appeared together.",
        confidence=0.54,
        evidence_links=["link_1"],
    )
    evidence = EvidenceStore(tmp_path / "nodes.json", tmp_path / "links.json")
    evidence.add_node(EvidenceNode(
        id="link_1",
        text="selected organization fixed codex subscription failed",
        source="terminal",
        source_uri="fixture://link_1",
    ))
    policy = GraphProposalReviewPolicy(
        graph,
        evidence_check=EvidenceSupportCheck(evidence),
    )
    review, edge_id = ReviewedGraphLinker(graph, policy).review_and_apply(proposal)
    assert review.decision == "accept"
    assert edge_id
    edge = graph.get_edge(edge_id)
    assert edge.source == "reviewed_graph_proposal"
    assert edge.source_id == tag_node_id("codex_subscription_failed")
    assert edge.target_id == tag_node_id("selected_organization")
    assert edge.evidence_links == ["link_1"]
    assert edge.status.value == "accepted"


def test_reviewer_quarantines_high_risk_relation_even_with_evidence(tmp_path):
    graph = GraphStore(tmp_path / "graph.json")
    proposal = GraphProposal(
        proposal_type="link_tags",
        source="llm",
        from_node="subscription_load_failed",
        to_node="selected_organization",
        relation=GraphRelation.CAUSED_BY,
        reason="Causality claim.",
        confidence=0.7,
        evidence_links=["link_1"],
    )
    review = GraphProposalReviewPolicy(graph).review(proposal)
    assert review.decision == "quarantine"
    assert "high-risk relation cannot be auto accepted" in review.reasons


def test_reviewer_downgrades_exact_resolves_to_related_edge(tmp_path):
    graph = GraphStore(tmp_path / "graph.json")
    evidence = EvidenceStore(tmp_path / "nodes.json", tmp_path / "links.json")
    evidence.add_node(EvidenceNode(
        id="ev_org",
        text="selected organization fixed codex subscription failed",
        source="terminal",
        source_uri="fixture://org",
    ))
    proposal = GraphProposal(
        proposal_type="link_tags",
        source="llm",
        from_node="selected_organization",
        to_node="codex_subscription_failed",
        relation=GraphRelation.RESOLVES,
        reason="Organization fixed subscription failure.",
        confidence=0.9,
        evidence_links=["ev_org"],
    )
    review, edge_id = ReviewedGraphLinker(
        graph,
        GraphProposalReviewPolicy(
            graph,
            evidence_check=EvidenceSupportCheck(evidence),
        ),
    ).review_and_apply(proposal)
    assert review.decision == "accept"
    edge = graph.get_edge(edge_id)
    assert edge.relation == GraphRelation.RELATED_TO
    assert proposal.metadata["original_relation"] == "resolves"


def test_reviewer_rejects_conflicting_relation(tmp_path):
    graph = GraphStore(tmp_path / "graph.json")
    proposal = GraphProposal(
        proposal_type="link_tags",
        source="llm",
        from_node="npm_reinstall_failed",
        to_node="npm_root_cause",
        relation=GraphRelation.CONTRADICTS,
        reason="Conflicting root cause claim.",
        confidence=0.5,
        evidence_links=["link_1"],
    )
    review, edge_id = ReviewedGraphLinker(graph).review_and_apply(proposal)
    assert review.decision == "reject"
    assert edge_id == ""
    assert graph.list_edges() == []


def test_pending_proposal_gets_lifecycle_metadata(tmp_path):
    graph = GraphStore(tmp_path / "graph.json")
    proposal = GraphProposal(
        proposal_type="link_tags",
        source="llm",
        from_node="codex_subscription_failed",
        to_node="selected_organization",
        relation=GraphRelation.RELATED_TO,
        reason="No evidence yet.",
        confidence=0.4,
    )
    review, edge_id = ReviewedGraphLinker(graph).review_and_apply(proposal)
    assert review.decision == "pending"
    assert edge_id == ""
    stored = graph.get_proposal(proposal.id)
    assert stored.metadata["pending_lifecycle"]["state"] == "pending_review"
    assert stored.metadata["pending_lifecycle"]["on_stale"] == "archive_without_new_evidence"


def test_reviewer_quarantines_high_fanout(tmp_path):
    graph = GraphStore(tmp_path / "graph.json")
    from memoryweaver.graph_linker import GraphLinker

    linker = GraphLinker(graph)
    for index in range(8):
        linker.link_tags(
            "codex_subscription_failed",
            f"neighbor_{index}",
            relation=GraphRelation.RELATED_TO,
            confidence=0.8,
            source="rule",
        )

    high_fanout = GraphProposal(
        proposal_type="link_tags",
        source="llm",
        from_node="codex_subscription_failed",
        to_node="too_many_neighbors",
        relation=GraphRelation.RELATED_TO,
        reason="fanout test",
        confidence=0.5,
        evidence_links=["link_1"],
    )
    review = GraphProposalReviewPolicy(graph).review(high_fanout)
    assert review.decision == "quarantine"
    assert "high fan-out edge requires review" in review.reasons


def test_load_env_file_does_not_mutate_environment(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("MEMORYWEAVER_ENABLE_LLM_GRAPH_PROPOSAL=true\n", encoding="utf-8")
    values = load_env_file(env_file)
    assert values["MEMORYWEAVER_ENABLE_LLM_GRAPH_PROPOSAL"] == "true"


def test_budget_gate_denies_online_llm_proposals():
    decision = ProposalBudgetGate().allow_llm_proposal(path="online")
    assert decision.allowed is False
    assert "online path never calls LLM GraphProposal" in decision.reasons
