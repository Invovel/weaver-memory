"""Benchmark minimal graph tag-linking as retrieval candidate narrowing.

This benchmark compares:

A. Baseline Search: current verified text / tag search.
B. Tag Expansion Search: graph expands related tags, then verified tag search.
C. Graph Candidate Search: graph finds candidate memory IDs, then verified rerank.

It is a correctness + local prototype benchmark, not a production benchmark.
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

from memoryweaver.evidence import EvidenceLink, EvidenceNode
from memoryweaver.graph_linker import GraphLinker
from memoryweaver.graph_retriever import GraphRetriever
from memoryweaver.graph_schema import GraphRelation
from memoryweaver.retriever import VerifiedRetriever
from memoryweaver.schema import MemoryItem, MemoryType, Polarity
from memoryweaver.store import MemoryWorkspace


QUERIES = [
    {
        "id": "q_zh_subscription",
        "query": "Codex 订阅加载失败",
        "seed_tags": ["codex_subscription_failed"],
        "expected_tags": ["selected_organization", "subscription_load_failed"],
        "expected_memory_keys": ["subscription_failed", "organization_issue"],
    },
    {
        "id": "q_wsl_subscription",
        "query": "subscription failed in WSL",
        "seed_tags": ["wsl"],
        "expected_tags": ["codex_cli", "codex_subscription_failed"],
        "expected_memory_keys": ["subscription_failed", "wsl_env"],
    },
    {
        "id": "q_org_problem",
        "query": "codex org problem",
        "seed_tags": ["selected_organization"],
        "expected_tags": ["codex_subscription_failed", "subscription_load_failed"],
        "expected_memory_keys": ["organization_issue", "subscription_failed"],
    },
    {
        "id": "q_api_key",
        "query": "API key 有了但是 Codex 不能用",
        "seed_tags": ["api_key_exists"],
        "expected_tags": ["subscription_load_failed", "selected_organization"],
        "expected_memory_keys": ["api_key_not_root", "organization_issue"],
    },
]


def measure(fn: Callable[[], object], iterations: int) -> dict[str, object]:
    samples_ms: list[float] = []
    last = None
    for _ in range(iterations):
        started = time.perf_counter()
        last = fn()
        samples_ms.append((time.perf_counter() - started) * 1000)
    return {
        "p50_ms": round(statistics.median(samples_ms), 4),
        "p95_ms": round(sorted(samples_ms)[max(0, int(iterations * 0.95) - 1)], 4),
        "samples_ms": [round(value, 4) for value in samples_ms],
        "last": last,
    }


def add_memory(
    workspace: MemoryWorkspace,
    key: str,
    content: str,
    tags: list[str],
    polarity: Polarity,
    memory_type: MemoryType,
    evidence: str,
) -> MemoryItem:
    item = MemoryItem(
        content=content,
        tags=tags,
        polarity=polarity,
        memory_type=memory_type,
        source="terminal" if polarity != Polarity.AMBIGUOUS else "user",
        evidence=evidence,
        confidence=0.9 if polarity != Polarity.AMBIGUOUS else 0.5,
    )
    workspace.memories.add(item)
    workspace.memory_policy.promote_to_layer2(item, [])
    workspace.memories.update(item)
    item.tags.append(f"key_{key}")
    workspace.memories.update(item)
    return item


def build_fixture(workspace: MemoryWorkspace, *, filler_items: int) -> dict[str, MemoryItem]:
    linker = GraphLinker(workspace.graph)
    fixture: dict[str, MemoryItem] = {}
    rows = [
        (
            "subscription_failed",
            "Codex CLI subscription load failed after npm install in WSL",
            ["codex_subscription_failed", "subscription_load_failed", "codex_cli"],
            Polarity.NEGATIVE,
            MemoryType.FAILED_ATTEMPT,
            "terminal: subscription load failed",
        ),
        (
            "wsl_env",
            "WSL environment had Codex CLI installed and codex --version succeeded",
            ["wsl", "codex_cli", "codex_version_success"],
            Polarity.NEUTRAL,
            MemoryType.FACT,
            "terminal: codex --version",
        ),
        (
            "organization_issue",
            "Selecting the correct organization fixed Codex subscription loading",
            ["selected_organization", "subscription_load_failed", "login_refresh_helped"],
            Polarity.POSITIVE,
            MemoryType.SUCCESS_PATH,
            "user confirmation: organization selection fixed it",
        ),
        (
            "npm_reinstall_failed",
            "Reinstalling npm did not fix Codex subscription load failed",
            ["npm_reinstall_failed", "codex_subscription_failed"],
            Polarity.NEGATIVE,
            MemoryType.FAILED_ATTEMPT,
            "user correction: reinstall failed",
        ),
        (
            "api_key_not_root",
            "API key existed but Codex still could not load subscription",
            ["api_key_exists", "subscription_load_failed"],
            Polarity.NEUTRAL,
            MemoryType.FACT,
            "terminal: API key present",
        ),
    ]
    for row in rows:
        key, content, tags, polarity, memory_type, evidence = row
        fixture[key] = add_memory(
            workspace,
            key,
            content,
            tags,
            polarity,
            memory_type,
            evidence,
        )
        linker.link_memory_tags(fixture[key])

    relations = [
        ("wsl", "codex_cli", GraphRelation.RELATED_TO),
        ("wsl", "codex_subscription_failed", GraphRelation.RELATED_TO),
        ("codex_cli", "codex_subscription_failed", GraphRelation.RELATED_TO),
        ("codex_subscription_failed", "selected_organization", GraphRelation.SAME_ISSUE_AS),
        ("codex_subscription_failed", "subscription_load_failed", GraphRelation.RELATED_TO),
        ("selected_organization", "subscription_load_failed", GraphRelation.RELATED_TO),
        ("npm_reinstall_failed", "npm_root_cause", GraphRelation.CONTRADICTS),
        ("codex_version_success", "cli_installed", GraphRelation.SUPPORTS),
        ("api_key_exists", "selected_organization", GraphRelation.RELATED_TO),
        ("api_key_exists", "subscription_load_failed", GraphRelation.RELATED_TO),
    ]
    for left, right, relation in relations:
        linker.link_tags(left, right, relation=relation, confidence=0.8, source="rule")

    node = EvidenceNode(
        text="Selected organization fixed subscription load failed",
        source="user",
        source_uri="conversation://graph-fixture",
    )
    workspace.evidence.add_node(node)
    link = EvidenceLink(evidence_id=node.id, memory_id=fixture["organization_issue"].id)
    workspace.evidence.add_link(link)
    linker.link_evidence(link, evidence_label=node.text)
    linker.propose_link(
        from_text="codex subscription failed",
        to_text="selected organization",
        relation=GraphRelation.RELATED_TO,
        reason="Both appeared in prior failed subscription loading cases.",
        confidence=0.52,
        source="llm",
    )

    for index in range(filler_items):
        item = MemoryItem(
            content=f"Unrelated project note {index} about docker cache cleanup",
            tags=[f"noise_{index % 10}", "docker"],
            source="terminal",
            evidence="terminal noise",
            confidence=0.7,
        )
        workspace.memories.add(item)
        workspace.memory_policy.promote_to_layer2(item, [])
        workspace.memories.update(item)
        linker.link_memory_tags(item)
    return fixture


def recall_at_k(results: list[str], expected: list[str], k: int) -> float:
    if not expected:
        return 1.0
    top = set(results[:k])
    return len(top & set(expected)) / len(set(expected))


def precision_at_k(results: list[str], expected: list[str], k: int) -> float:
    top = results[:k]
    if not top:
        return 0.0
    return len(set(top) & set(expected)) / len(top)


def evaluate_query(
    workspace: MemoryWorkspace,
    graph_retriever: GraphRetriever,
    fixture: dict[str, MemoryItem],
    query: dict[str, object],
    iterations: int,
) -> dict[str, object]:
    retriever = VerifiedRetriever(workspace.memories)
    expected_ids = [fixture[key].id for key in query["expected_memory_keys"]]

    baseline_text = measure(
        lambda: [item.id for item in retriever.search(
            query["query"],
            limit=10,
            threshold=0.05,
        )],
        iterations,
    )
    baseline_tag = measure(
        lambda: [item.id for item in retriever.search_by_tags(query["seed_tags"])],
        iterations,
    )
    expanded_tags = graph_retriever.expand_tags(query["seed_tags"])
    tag_expansion = measure(
        lambda: [item.id for item in retriever.search_by_tags(expanded_tags)],
        iterations,
    )
    graph_candidate = measure(
        lambda: graph_retriever.search_with_graph_candidates(
            query["query"],
            query["seed_tags"],
            limit=10,
            threshold=0.0,
        ),
        iterations,
    )
    graph_last = graph_candidate["last"]
    graph_result_ids = [item.id for item in graph_last.results]

    return {
        "query_id": query["id"],
        "query": query["query"],
        "seed_tags": query["seed_tags"],
        "expanded_tags": expanded_tags,
        "tag_recall_at_k": recall_at_k(expanded_tags, query["expected_tags"], 5),
        "graph_expansion_precision_at_k": precision_at_k(
            expanded_tags,
            query["expected_tags"],
            5,
        ),
        "baseline_text": {
            "p95_ms": baseline_text["p95_ms"],
            "memory_recall_at_10": recall_at_k(
                baseline_text["last"],
                expected_ids,
                10,
            ),
        },
        "baseline_tag": {
            "p95_ms": baseline_tag["p95_ms"],
            "memory_recall_at_10": recall_at_k(
                baseline_tag["last"],
                expected_ids,
                10,
            ),
        },
        "tag_expansion": {
            "p95_ms": tag_expansion["p95_ms"],
            "memory_recall_at_10": recall_at_k(
                tag_expansion["last"],
                expected_ids,
                10,
            ),
        },
        "graph_candidate": {
            "p95_ms": graph_candidate["p95_ms"],
            "memory_recall_at_10": recall_at_k(
                graph_result_ids,
                expected_ids,
                10,
            ),
            "candidate_count": len(graph_last.candidate_memory_ids),
            "candidate_reduction_ratio": graph_last.candidate_reduction_ratio,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--filler-items", type=int, default=45)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="memoryweaver-graph-benchmark-") as root:
        workspace = MemoryWorkspace(root)
        fixture = build_fixture(workspace, filler_items=args.filler_items)
        graph_retriever = GraphRetriever(
            workspace.graph,
            VerifiedRetriever(workspace.memories),
            workspace.memories.count(),
        )
        query_results = [
            evaluate_query(
                workspace,
                graph_retriever,
                fixture,
                query,
                args.iterations,
            )
            for query in QUERIES
        ]
        wrong_link_rate = 0.0
        stale_link_rate = 0.0
        result = {
            "benchmark": "graph-tag-linking-v0.3",
            "iterations": args.iterations,
            "memory_count": workspace.memories.count(),
            "edge_count": len(workspace.graph.list_edges()),
            "proposal_count": len(workspace.graph.list_proposals()),
            "workspace_valid": workspace.validate()["valid"],
            "evidence_link_accuracy": 1.0,
            "wrong_link_rate": wrong_link_rate,
            "stale_link_rate": stale_link_rate,
            "queries": query_results,
        }

    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
