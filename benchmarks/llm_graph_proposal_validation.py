"""Validate low-privilege LLM GraphProposal flow.

Compares manual graph, rule graph, and LLM-proposal graph. The LLM arm uses the
offline local provider so this benchmark never requires API keys or network.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memoryweaver.config import MemoryWeaverConfig
from memoryweaver.evidence import EvidenceLink, EvidenceNode
from memoryweaver.graph.linker import ReviewedGraphLinker
from memoryweaver.graph.proposal import LLMGraphProposalService
from memoryweaver.graph_linker import GraphLinker
from memoryweaver.graph_retriever import GraphRetriever
from memoryweaver.graph_schema import GraphRelation
from memoryweaver.retriever import VerifiedRetriever
from memoryweaver.schema import MemoryItem, MemoryType, Polarity
from memoryweaver.store import MemoryWorkspace


QUERY = "codex org problem"
SEED_TAGS = ["codex_subscription_failed"]


def timed(fn: Callable[[], object], iterations: int) -> dict[str, object]:
    samples: list[float] = []
    last = None
    for _ in range(iterations):
        started = time.perf_counter()
        last = fn()
        samples.append((time.perf_counter() - started) * 1000)
    return {
        "p95_ms": round(sorted(samples)[max(0, int(iterations * 0.95) - 1)], 4),
        "p50_ms": round(statistics.median(samples), 4),
        "last": last,
    }


def add_memory(workspace: MemoryWorkspace, content: str, tags: list[str]) -> MemoryItem:
    item = MemoryItem(
        content=content,
        tags=tags,
        source="terminal",
        polarity=Polarity.NEUTRAL,
        memory_type=MemoryType.FACT,
        evidence="fixture",
        confidence=0.9,
    )
    workspace.memories.add(item)
    workspace.memory_policy.promote_to_layer2(item, [])
    workspace.memories.update(item)
    return item


def build_workspace(root: str) -> tuple[MemoryWorkspace, dict[str, MemoryItem], str]:
    workspace = MemoryWorkspace(root)
    memories = {
        "subscription": add_memory(
            workspace,
            "Codex CLI subscription load failed in WSL",
            ["codex_subscription_failed", "codex_cli"],
        ),
        "organization": add_memory(
            workspace,
            "Selected organization fixed Codex subscription loading",
            ["selected_organization", "subscription_load_failed"],
        ),
    }
    for index in range(48):
        add_memory(
            workspace,
            f"Noise memory {index} about unrelated docker cache",
            [f"noise_{index % 8}", "docker"],
        )
    linker = GraphLinker(workspace.graph)
    for memory in workspace.memories.list_all():
        linker.link_memory_tags(memory)
    node = EvidenceNode(
        text="Organization selection fixed subscription load failed",
        source="user",
        source_uri="conversation://llm-graph-validation",
    )
    workspace.evidence.add_node(node)
    link = EvidenceLink(evidence_id=node.id, memory_id=memories["organization"].id)
    workspace.evidence.add_link(link)
    return workspace, memories, link.id


def add_manual_graph(workspace: MemoryWorkspace) -> None:
    GraphLinker(workspace.graph).link_tags(
        "codex_subscription_failed",
        "selected_organization",
        relation=GraphRelation.RELATED_TO,
        confidence=0.8,
        source="manual",
    )


def add_rule_graph(workspace: MemoryWorkspace) -> None:
    linker = GraphLinker(workspace.graph)
    linker.link_tags(
        "codex_subscription_failed",
        "selected_organization",
        relation=GraphRelation.SAME_ISSUE_AS,
        confidence=0.8,
        source="rule",
    )
    linker.link_tags(
        "selected_organization",
        "subscription_load_failed",
        relation=GraphRelation.RELATED_TO,
        confidence=0.8,
        source="rule",
    )


def add_llm_proposal_graph(workspace: MemoryWorkspace, evidence_link_id: str) -> dict[str, object]:
    config = MemoryWeaverConfig.from_env(env={
        "MEMORYWEAVER_ENABLE_LLM_GRAPH_PROPOSAL": "true",
        "MEMORYWEAVER_LLM_PROVIDER": "local",
        "MEMORYWEAVER_LLM_PROPOSAL_CONFIDENCE_CAP": "0.6",
    })
    proposals = LLMGraphProposalService(config).propose(
        query=QUERY,
        tags=["codex_subscription_failed", "selected_organization"],
    )
    accepted = 0
    wrong = 0
    linker = ReviewedGraphLinker(workspace.graph)
    for proposal in proposals:
        proposal.evidence_links.append(evidence_link_id)
        review, edge_id = linker.review_and_apply(proposal)
        if review.decision == "accept":
            accepted += 1
            if not edge_id:
                wrong += 1
        else:
            wrong += 1
    precision = accepted / len(proposals) if proposals else 0.0
    return {
        "proposal_count": len(proposals),
        "accepted": accepted,
        "proposal_precision": precision,
        "wrong_link_rate": wrong / len(proposals) if proposals else 0.0,
    }


def evaluate_arm(
    arm: str,
    mutate: Callable[[MemoryWorkspace, str], dict[str, object]],
    iterations: int,
) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix=f"memoryweaver-{arm}-") as root:
        workspace, memories, evidence_link_id = build_workspace(root)
        proposal_metrics = mutate(workspace, evidence_link_id)
        graph_retriever = GraphRetriever(
            workspace.graph,
            VerifiedRetriever(workspace.memories),
            workspace.memories.count(),
        )
        expected = {memories["subscription"].id, memories["organization"].id}
        measurement = timed(
            lambda: graph_retriever.search_with_graph_candidates(
                QUERY,
                SEED_TAGS,
                limit=10,
                threshold=0.0,
            ),
            iterations,
        )
        result = measurement["last"]
        returned = {item.id for item in result.results}
        recall = len(returned & expected) / len(expected)
        return {
            "arm": arm,
            "workspace_valid": workspace.validate()["valid"],
            "recall_at_10": recall,
            "candidate_count": len(result.candidate_memory_ids),
            "candidate_reduction_ratio": result.candidate_reduction_ratio,
            "p95_ms": measurement["p95_ms"],
            "p50_ms": measurement["p50_ms"],
            **proposal_metrics,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = {
        "benchmark": "llm-graph-proposal-v0.4",
        "iterations": args.iterations,
        "arms": [
            evaluate_arm("manual_graph", lambda workspace, _: (add_manual_graph(workspace) or {}), args.iterations),
            evaluate_arm("rule_graph", lambda workspace, _: (add_rule_graph(workspace) or {}), args.iterations),
            evaluate_arm("llm_proposal_graph", add_llm_proposal_graph, args.iterations),
        ],
    }
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
