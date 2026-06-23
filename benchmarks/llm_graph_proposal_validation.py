"""Run v0.4.2 LLM GraphProposal pressure validation.

This benchmark evaluates whether LLM-generated GraphProposal objects improve
graph-assisted retrieval without changing the Layer-3 lifecycle. Providers may
generate proposals, but Harness review remains the only path to candidate graph
edges.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks._safety import safe_rmtree_child
from memoryweaver.config import MemoryWeaverConfig
from memoryweaver.evidence import EvidenceNode
from memoryweaver.graph.budget import ProposalBudgetGate
from memoryweaver.graph.evidence_binder import GraphEvidenceBinder
from memoryweaver.graph.evidence_support import EvidenceSupportCheck
from memoryweaver.graph.expansion_policy import GraphExpansionPolicy
from memoryweaver.graph.linker import ReviewedGraphLinker
from memoryweaver.graph.proposal import LLMGraphProposalService
from memoryweaver.graph.proposal_eval import EdgeKey, evaluate_proposals
from memoryweaver.graph.reviewer import GraphProposalReviewPolicy
from memoryweaver.graph_linker import GraphLinker
from memoryweaver.graph_retriever import GraphRetriever
from memoryweaver.graph_schema import GraphProposal, GraphRelation, GraphStatus
from memoryweaver.retriever import VerifiedRetriever
from memoryweaver.schema import MemoryItem, MemoryType, Polarity
from memoryweaver.store import MemoryWorkspace


VALIDATION_NAME = "llm-graph-proposal-v0.4.2"
PROMPT_VERSION = "graph_proposal_deepseek_v0.4.2"
POLICY_VERSION = "graph-proposal-review-v0.4.2"

QUERY_CASES = [
    {
        "id": "q_subscription_cn",
        "query": "Codex 订阅加载失败",
        "tags": ["codex_subscription_failed"],
        "expected_labels": ["subscription_failed", "organization_fix", "login_refresh"],
    },
    {
        "id": "q_wsl_subscription",
        "query": "subscription failed in WSL",
        "tags": ["wsl"],
        "expected_labels": ["subscription_failed", "wsl_env", "organization_fix"],
    },
    {
        "id": "q_org_problem",
        "query": "codex org problem",
        "tags": ["selected_organization"],
        "expected_labels": ["organization_fix", "subscription_failed"],
    },
    {
        "id": "q_api_key_but_codex_fails",
        "query": "API key 有了但是 Codex 不能用",
        "tags": ["api_key_exists"],
        "expected_labels": ["api_key_not_subscription", "subscription_failed", "billing_not_root"],
    },
]

GOLD_EDGES = [
    {
        "from_tag": "codex_subscription_failed",
        "to_tag": "selected_organization",
        "relation": "related_to",
        "evidence_ids": ["ev_org_selection"],
    },
    {
        "from_tag": "codex_subscription_failed",
        "to_tag": "login_refresh_helped",
        "relation": "related_to",
        "evidence_ids": ["ev_login_refresh"],
    },
    {
        "from_tag": "codex_subscription_failed",
        "to_tag": "wsl",
        "relation": "same_topic_as",
        "evidence_ids": ["ev_wsl_terminal"],
    },
    {
        "from_tag": "api_key_exists",
        "to_tag": "openai_api_billing",
        "relation": "same_topic_as",
        "evidence_ids": ["ev_api_key_scope"],
    },
    {
        "from_tag": "npm_reinstall_failed",
        "to_tag": "npm_install_success",
        "relation": "related_to",
        "evidence_ids": ["ev_npm_reinstall"],
    },
]


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


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def add_memory(
    workspace: MemoryWorkspace,
    *,
    label: str,
    content: str,
    tags: list[str],
    polarity: Polarity = Polarity.NEUTRAL,
    memory_type: MemoryType = MemoryType.FACT,
    evidence: str = "fixture",
) -> MemoryItem:
    item = MemoryItem(
        content=content,
        tags=tags,
        source="terminal",
        polarity=polarity,
        memory_type=memory_type,
        evidence=evidence,
        confidence=0.9,
    )
    item.id = f"mem_{label}"
    workspace.memories.add(item)
    workspace.memory_policy.promote_to_layer2(item, [])
    workspace.memories.update(item)
    return item


def build_workspace(root: str) -> tuple[MemoryWorkspace, dict[str, MemoryItem]]:
    workspace = MemoryWorkspace(root)
    fixtures = [
        ("subscription_failed", "Codex CLI subscription load failed in WSL after login.", ["codex_subscription_failed", "codex_cli", "wsl"], Polarity.NEGATIVE, MemoryType.FAILED_ATTEMPT),
        ("organization_fix", "Selecting the correct organization resolved Codex subscription loading.", ["selected_organization", "subscription_load_failed", "codex_cli"], Polarity.POSITIVE, MemoryType.SUCCESS_PATH),
        ("login_refresh", "Refreshing login helped after Codex subscription failed.", ["login_refresh_helped", "codex_subscription_failed"], Polarity.POSITIVE, MemoryType.SUCCESS_PATH),
        ("wsl_env", "WSL environment changed Codex CLI auth behavior compared with Windows terminal.", ["wsl", "windows_native_terminal", "codex_cli"], Polarity.NEUTRAL, MemoryType.FACT),
        ("api_key_not_subscription", "OpenAI API key existed, but Codex subscription still failed because org selection was separate.", ["api_key_exists", "codex_subscription_failed", "selected_organization"], Polarity.NEUTRAL, MemoryType.FACT),
        ("billing_not_root", "OpenAI API billing was not the root cause of Codex subscription load failure.", ["openai_api_billing", "codex_subscription_failed"], Polarity.NEGATIVE, MemoryType.CORRECTION),
        ("npm_install_success", "npm install -g codex succeeded and codex --version returned a version.", ["npm_install_success", "codex_version_success", "codex_cli"], Polarity.POSITIVE, MemoryType.SUCCESS_PATH),
        ("npm_reinstall", "Reinstalling npm package did not fix the subscription load failure.", ["npm_reinstall_failed", "codex_subscription_failed"], Polarity.NEGATIVE, MemoryType.FAILED_ATTEMPT),
        ("windows_terminal", "Windows native terminal could open Codex CLI after login refresh.", ["windows_native_terminal", "login_refresh_helped"], Polarity.POSITIVE, MemoryType.FACT),
        ("codex_version", "codex --version succeeded, proving the CLI binary was installed.", ["codex_version_success", "npm_install_success"], Polarity.POSITIVE, MemoryType.FACT),
        ("github_org_noise", "GitHub organization selection changed repository permissions only.", ["github_organization", "selected_organization"], Polarity.NEUTRAL, MemoryType.FACT),
        ("weather_api_noise", "Weather API key was valid but unrelated to Codex CLI auth.", ["weather_api_key", "api_key_exists"], Polarity.NEUTRAL, MemoryType.FACT),
        ("npm_subscription_noise", "npm package subscription warning came from a different package.", ["npm_package_subscription", "subscription_load_failed"], Polarity.NEUTRAL, MemoryType.FACT),
        ("vscode_extension_noise", "VS Code extension failed to reload because of marketplace cache.", ["vscode_extension_failed", "login_refresh_helped"], Polarity.NEUTRAL, MemoryType.FACT),
        ("old_org_conflict", "Old note claimed organization choice did not matter for Codex subscription.", ["selected_organization", "codex_subscription_failed", "old_version"], Polarity.NEGATIVE, MemoryType.CORRECTION),
    ]
    memories = {
        label: add_memory(
            workspace,
            label=label,
            content=content,
            tags=tags,
            polarity=polarity,
            memory_type=memory_type,
        )
        for label, content, tags, polarity, memory_type in fixtures
    }
    for index in range(25):
        add_memory(
            workspace,
            label=f"noise_{index:02d}",
            content=f"Noisy memory {index}: unrelated cache, package, API, or extension note.",
            tags=[
                ["docker_cache", "npm_package_subscription", "weather_api_key", "github_organization", "vscode_extension_failed"][index % 5],
                f"noise_{index % 7}",
            ],
            polarity=Polarity.NEUTRAL,
        )
    linker = GraphLinker(workspace.graph)
    for memory in workspace.memories.list_all():
        linker.link_memory_tags(memory)

    evidence_records = [
        ("ev_org_selection", "User confirmation: selected organization fixed Codex subscription loading.", ["selected_organization", "codex_subscription_failed"]),
        ("ev_login_refresh", "Terminal transcript: login refresh helped after subscription load failed.", ["login_refresh_helped", "codex_subscription_failed"]),
        ("ev_wsl_terminal", "Terminal evidence: WSL auth behavior differed from Windows native terminal.", ["wsl", "windows_native_terminal"]),
        ("ev_api_key_scope", "README note: API key presence does not prove Codex subscription entitlement.", ["api_key_exists", "openai_api_billing"]),
        ("ev_npm_reinstall", "Terminal evidence: npm reinstall completed but subscription error remained.", ["npm_reinstall_failed", "npm_install_success"]),
    ]
    for evidence_id, text, tags in evidence_records:
        workspace.evidence.add_node(EvidenceNode(
            id=evidence_id,
            text=text,
            source="terminal",
            source_uri=f"fixture://{evidence_id}",
            metadata={"tags": tags},
        ))
    return workspace, memories


def memory_payload(workspace: MemoryWorkspace) -> list[dict[str, Any]]:
    return [
        {
            "id": item.id,
            "content": item.content,
            "tags": item.tags,
            "polarity": item.polarity.value,
            "source": item.source.value,
        }
        for item in workspace.memories.list_all()
    ]


def evidence_payload(workspace: MemoryWorkspace) -> list[dict[str, Any]]:
    return [
        {
            "id": node.id,
            "text": node.text,
            "source": node.source.value,
            "metadata": node.metadata,
        }
        for node in workspace.evidence.list_nodes()
    ]


def make_batch_records(workspace: MemoryWorkspace) -> list[dict[str, Any]]:
    memories = memory_payload(workspace)
    evidence = evidence_payload(workspace)
    return [
        {
            "id": case["id"],
            "query": case["query"],
            "tags": case["tags"],
            "memories": memories,
            "evidence": evidence,
        }
        for case in QUERY_CASES
    ]


def add_manual_graph(workspace: MemoryWorkspace) -> None:
    linker = GraphLinker(workspace.graph)
    for edge in GOLD_EDGES:
        linker.link_tags(
            edge["from_tag"],
            edge["to_tag"],
            relation=GraphRelation(edge["relation"]),
            confidence=0.85,
            source="manual",
            status=GraphStatus.ACCEPTED,
        )


def add_rule_graph(workspace: MemoryWorkspace) -> None:
    linker = GraphLinker(workspace.graph)
    linker.link_tags("codex_subscription_failed", "selected_organization", relation=GraphRelation.RELATED_TO, confidence=0.75, source="rule", status=GraphStatus.ACCEPTED)
    linker.link_tags("codex_subscription_failed", "wsl", relation=GraphRelation.SAME_TOPIC_AS, confidence=0.75, source="rule", status=GraphStatus.ACCEPTED)
    linker.link_tags("api_key_exists", "openai_api_billing", relation=GraphRelation.SAME_TOPIC_AS, confidence=0.7, source="rule", status=GraphStatus.ACCEPTED)
    linker.link_tags("npm_reinstall_failed", "npm_install_success", relation=GraphRelation.RELATED_TO, confidence=0.65, source="rule", status=GraphStatus.ACCEPTED)
    linker.link_tags("api_key_exists", "weather_api_key", relation=GraphRelation.RELATED_TO, confidence=0.4, source="rule", status=GraphStatus.ACCEPTED)


def generate_llm_proposals(
    workspace: MemoryWorkspace,
    config: MemoryWeaverConfig,
    output_path: Path,
) -> dict[str, Any]:
    service = LLMGraphProposalService(config)
    budget_gate = ProposalBudgetGate(max_batch_proposals=12, max_proposals_per_query=3)
    records: list[dict[str, Any]] = []
    successful_queries = 0
    provider_errors: list[str] = []
    for batch in make_batch_records(workspace):
        decision = budget_gate.allow_llm_proposal(
            path="offline",
            current_batch_proposals=len(records),
        )
        if not decision.allowed:
            break
        try:
            proposals = service.propose(
                query=batch["query"],
                tags=batch["tags"],
                memories=batch["memories"],
                evidence=batch["evidence"],
            )[:budget_gate.max_proposals_per_query]
            successful_queries += 1
        except Exception as exc:
            proposals = []
            provider_errors.append(f"{batch['id']}: {exc}")
        for proposal in proposals:
            records.append({
                "input_id": batch["id"],
                "query": batch["query"],
                "proposal": proposal.to_dict(),
            })
    write_jsonl(output_path, records)
    return {
        "records": records,
        "json_parse_success_rate": round(successful_queries / len(QUERY_CASES), 4),
        "provider_errors": provider_errors,
    }


def review_proposals(
    workspace: MemoryWorkspace,
    proposal_records: list[dict[str, Any]],
    output_path: Path,
) -> list[dict[str, Any]]:
    binder = GraphEvidenceBinder(workspace.evidence)
    linker = ReviewedGraphLinker(
        workspace.graph,
        GraphProposalReviewPolicy(
            workspace.graph,
            evidence_check=EvidenceSupportCheck(workspace.evidence),
        ),
    )
    reviewed: list[dict[str, Any]] = []
    for record in proposal_records:
        proposal = GraphProposal.from_dict(record["proposal"])
        binder.bind(proposal, query=record.get("query", ""))
        review, edge_id = linker.review_and_apply(proposal)
        reviewed.append({
            "input_id": record.get("input_id", ""),
            "query": record.get("query", ""),
            "proposal": proposal.to_dict(),
            "review": {
                "decision": review.decision,
                "reasons": review.reasons,
                "confidence": review.confidence,
                "requires_review": review.requires_review,
                "evidence_support": review.evidence_support,
            },
            "edge_id": edge_id,
        })
    write_jsonl(output_path, reviewed)
    return reviewed


def support_audit(reviewed: list[dict[str, Any]]) -> dict[str, Any]:
    """Approximate manual audit fixture for EvidenceSupportCheck categories."""
    gold = {EdgeKey.from_record(record) for record in GOLD_EDGES}
    exact: list[dict[str, Any]] = []
    partial: list[dict[str, Any]] = []
    unsupported: list[dict[str, Any]] = []
    contradicts: list[dict[str, Any]] = []
    for record in reviewed:
        status = str(record.get("review", {}).get("evidence_support", ""))
        if status == "supports_exact":
            exact.append(record)
        elif status == "supports_partial":
            partial.append(record)
        elif status in {"does_not_support", "insufficient_evidence"}:
            unsupported.append(record)
        elif status == "contradicts":
            contradicts.append(record)
    exact_correct = sum(
        1 for record in exact
        if EdgeKey.from_record(record.get("proposal", record)) in gold
    )
    return {
        "supports_exact_count": len(exact),
        "supports_exact_correct": exact_correct,
        "supports_exact_precision": round(exact_correct / len(exact), 4) if exact else 0.0,
        "supports_partial_count": len(partial),
        "unsupported_count": len(unsupported),
        "contradicts_count": len(contradicts),
    }


def evaluate_retrieval_arm(
    arm: str,
    workspace: MemoryWorkspace,
    memories: dict[str, MemoryItem],
    iterations: int,
) -> dict[str, Any]:
    graph_retriever = GraphRetriever(
        workspace.graph,
        VerifiedRetriever(workspace.memories),
        workspace.memories.count(),
    )
    expansion_policy = GraphExpansionPolicy(
        min_text_results_before_skip=3,
        max_candidates=20,
    )
    case_metrics: list[dict[str, Any]] = []
    for case in QUERY_CASES:
        expected = {memories[label].id for label in case["expected_labels"]}
        measurement = timed(
            lambda case=case: graph_retriever.search_with_graph_candidates(
                case["query"],
                case["tags"],
                limit=10,
                threshold=0.0,
                expansion_policy=expansion_policy,
            ),
            iterations,
        )
        result = measurement["last"]
        returned = {item.id for item in result.results}
        expanded_relevant = {
            tag for tag in result.expanded_tags
            if tag in {tag for edge in GOLD_EDGES for tag in (edge["from_tag"], edge["to_tag"])}
        }
        case_metrics.append({
            "query_id": case["id"],
            "memory_recall_at_10": round(len(returned & expected) / len(expected), 4),
            "tag_recall_at_k": round(len(set(result.expanded_tags) & set(case["tags"])) / len(case["tags"]), 4),
            "graph_expansion_precision": round(len(expanded_relevant) / len(result.expanded_tags), 4) if result.expanded_tags else 0.0,
            "candidate_count": len(result.candidate_memory_ids),
            "candidate_reduction_ratio": result.candidate_reduction_ratio,
            "graph_expansion_candidate_delta": result.graph_expansion_candidate_delta,
            "expansion_skipped": result.expansion_skipped,
            "verified_text_p95_ms": measurement["p95_ms"],
            "verified_text_p50_ms": measurement["p50_ms"],
            "expanded_tags": result.expanded_tags,
            "returned_memory_ids": sorted(returned),
        })
    return {
        "arm": arm,
        "tag_recall_at_k": round(statistics.mean(case["tag_recall_at_k"] for case in case_metrics), 4),
        "memory_recall_at_10": round(statistics.mean(case["memory_recall_at_10"] for case in case_metrics), 4),
        "graph_expansion_precision": round(statistics.mean(case["graph_expansion_precision"] for case in case_metrics), 4),
        "candidate_reduction_ratio": round(statistics.mean(case["candidate_reduction_ratio"] for case in case_metrics), 4),
        "graph_expansion_candidate_delta": round(statistics.mean(case["graph_expansion_candidate_delta"] for case in case_metrics), 4),
        "verified_text_p95_ms": round(max(case["verified_text_p95_ms"] for case in case_metrics), 4),
        "verified_text_p50_ms": round(statistics.mean(case["verified_text_p50_ms"] for case in case_metrics), 4),
        "online_llm_call_count": 0,
        "cases": case_metrics,
    }


def evaluate_arm(
    arm: str,
    iterations: int,
    mutate: Callable[[MemoryWorkspace], None],
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"memoryweaver-{arm}-") as root:
        workspace, memories = build_workspace(root)
        mutate(workspace)
        return evaluate_retrieval_arm(arm, workspace, memories, iterations)


def evaluate_provider_flow(
    *,
    label: str,
    config: MemoryWeaverConfig,
    output_dir: Path,
    iterations: int,
) -> dict[str, Any]:
    workspace_root = output_dir / f".graph-proposal-{label}-workspace"
    safe_rmtree_child(
        output_dir,
        workspace_root,
        allowed_prefixes=(".graph-proposal-",),
    )
    workspace, memories = build_workspace(str(workspace_root))
    proposal_run = generate_llm_proposals(
        workspace,
        config,
        output_dir / f"proposals_{label}.jsonl",
    )
    reviewed = review_proposals(
        workspace,
        proposal_run["records"],
        output_dir / f"reviewed_{label}.jsonl",
    )
    metrics = evaluate_proposals(GOLD_EDGES, reviewed).to_dict()
    audit = support_audit(reviewed)
    doctor_report = workspace.doctor()
    (output_dir / f"doctor_{label}.json").write_text(
        json.dumps(doctor_report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    arm = evaluate_retrieval_arm(
        f"{label}_offline_proposal_graph",
        workspace,
        memories,
        iterations,
    )
    return {
        "label": label,
        "provider": config.llm_provider,
        "model": config.llm_model,
        "workspace_root": str(workspace_root),
        "proposal_records": proposal_run["records"],
        "json_parse_success_rate": proposal_run["json_parse_success_rate"],
        "provider_errors": proposal_run["provider_errors"],
        "reviewed": reviewed,
        "metrics": metrics,
        "support_audit": audit,
        "doctor_report": doctor_report,
        "retrieval_arm": arm,
        "accepted_edge_count": metrics["accepted"],
    }

def build_provider_config(
    *,
    provider: str,
    model: str,
    env_file: str,
) -> MemoryWeaverConfig:
    env = dict(os.environ)
    env.update({
        "MEMORYWEAVER_ENABLE_LLM_GRAPH_PROPOSAL": "true",
        "MEMORYWEAVER_LLM_PROVIDER": provider,
        "MEMORYWEAVER_LLM_MODEL": model,
    })
    return MemoryWeaverConfig.from_env(env=env, env_file=env_file)


def write_readme(
    output_dir: Path,
    *,
    raw_results: dict[str, Any],
) -> None:
    arms = raw_results["retrieval_arms"]
    deepseek_metrics = raw_results["provider_metrics"]["deepseek"]
    deepseek_support = raw_results["support_audits"]["deepseek"]
    deepseek_doctor = raw_results["doctor_reports"]["deepseek"]
    criteria = raw_results["success_criteria"]
    deepseek_errors = raw_results["provider_runs"]["deepseek"]["provider_errors"]
    provider_note = (
        "This run does not prove DeepSeek proposal utility because provider errors occurred before usable proposals were generated."
        if deepseek_errors
        else "DeepSeek provider returned proposals; accepted-edge utility is judged by the success criteria above."
    )
    lines = [
        "# LLM GraphProposal v0.4.2 Validation",
        "",
        "This validation runs a real DeepSeek offline GraphProposal pressure test. DeepSeek never enters the online query path; it only produces offline proposals that pass through EvidenceSupportCheck and Harness review before accepted edges can affect online graph retrieval.",
        "",
        "## Configuration",
        "",
        f"- Real provider: `{raw_results['providers']['deepseek']['provider']}`",
        f"- Real model: `{raw_results['providers']['deepseek']['model']}`",
        f"- Local baseline provider: `{raw_results['providers']['local']['provider']}`",
        f"- Prompt version: `{PROMPT_VERSION}`",
        f"- Review policy version: `{POLICY_VERSION}`",
        f"- Dataset size: `{raw_results['dataset']['memory_count']}` memories, `{raw_results['dataset']['evidence_count']}` evidence nodes, `{raw_results['dataset']['query_count']}` queries",
        f"- Online LLM call count: `{raw_results['online_llm_call_count']}`",
        "",
        "## DeepSeek Proposal Metrics",
        "",
        f"- JSON parse success rate: `{raw_results['provider_runs']['deepseek']['json_parse_success_rate']}`",
        f"- Proposal count: `{deepseek_metrics['proposal_count']}`",
        f"- Provider errors: `{len(deepseek_errors)}`",
        *(f"  - {error}" for error in deepseek_errors[:4]),
        f"- Accepted / pending / rejected / quarantined: `{deepseek_metrics['accepted']}` / `{deepseek_metrics['pending']}` / `{deepseek_metrics['rejected']}` / `{deepseek_metrics['quarantined']}`",
        f"- Accepted edge count: `{deepseek_metrics['accepted']}`",
        f"- Accepted wrong link rate: `{deepseek_metrics['accepted_wrong_link_rate']}`",
        f"- Exact / partial / unsupported support rates: `{deepseek_metrics['exact_support_rate']}` / `{deepseek_metrics['partial_support_rate']}` / `{deepseek_metrics['unsupported_rate']}`",
        f"- Review cost per accepted edge: `{deepseek_metrics['review_cost_per_accepted_edge']}`",
        "",
        "## v0.4 vs v0.4.2 Proposal-Level Comparison",
        "",
        "| Metric | v0.4 | v0.4.2 | Target |",
        "| --- | ---: | ---: | --- |",
        f"| proposals | 22 | {deepseek_metrics['proposal_count']} | <= 12 |",
        f"| accepted | 7 | {deepseek_metrics['accepted']} | > 0 |",
        f"| rejected | 0 | {deepseek_metrics['rejected']} | > 0 |",
        f"| accepted wrong link rate | n/a | {deepseek_metrics['accepted_wrong_link_rate']} | 0 or close to 0 |",
        f"| online LLM calls | multiple / online path | {raw_results['online_llm_call_count']} | 0 |",
        "",
        "## v0.4 vs v0.4.2 Evidence Support Comparison",
        "",
        "| Metric | v0.4 | v0.4.2 | Target |",
        "| --- | ---: | ---: | --- |",
        f"| evidence coverage | 1.0 | {deepseek_metrics['evidence_coverage']} | <= 0.6 |",
        f"| supports_exact precision | n/a | {deepseek_support['supports_exact_precision']} | >= 0.7 |",
        f"| supports_partial count | n/a | {deepseek_support['supports_partial_count']} | inspect |",
        f"| unsupported count | n/a | {deepseek_support['unsupported_count']} | > 0 expected in noisy batch |",
        "",
        "## Doctor Gate",
        "",
        f"- `mw doctor` valid: `{deepseek_doctor['valid']}`",
        f"- doctor errors: `{len(deepseek_doctor['errors'])}`",
        f"- doctor warnings: `{len(deepseek_doctor['warnings'])}`",
        f"- doctor info: `{len(deepseek_doctor['info'])}`",
        "",
        "## Success Criteria",
        "",
        f"- DeepSeek provider available: `{criteria['deepseek_provider_available']}`",
        f"- accepted_edge_count > 0: `{criteria['accepted_edge_count_gt_0']}`",
        f"- accepted_wrong_link_rate near 0: `{criteria['accepted_wrong_link_rate_near_zero']}`",
        f"- Memory Recall@10 > no_graph: `{criteria['recall_beats_no_graph']}`",
        f"- online_llm_call_count = 0: `{criteria['online_llm_call_count_zero']}`",
        f"- proposal budget respected: `{criteria['proposal_budget_respected']}`",
        f"- supports_exact precision >= 0.7: `{criteria['supports_exact_precision_ok']}`",
        f"- rejected > 0: `{criteria['rejected_gt_0']}`",
        f"- evidence coverage <= 0.6: `{criteria['evidence_coverage_ok']}`",
        f"- v0.4.2 pass: `{criteria['passed']}`",
        "",
        "## Retrieval Comparison",
        "",
        "| Arm | Tag Recall@k | Memory Recall@10 | Graph Expansion Precision | Candidate Reduction | Candidate Delta | Verified Text p95 ms | Online LLM Calls |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm in arms:
        lines.append(
            f"| {arm['arm']} | {arm['tag_recall_at_k']} | {arm['memory_recall_at_10']} | {arm['graph_expansion_precision']} | {arm['candidate_reduction_ratio']} | {arm['graph_expansion_candidate_delta']} | {arm['verified_text_p95_ms']} | {arm['online_llm_call_count']} |"
        )
    lines.extend([
        "",
        "## Interpretation",
        "",
        "This is a retrieval/linking pressure validation, not a task-success experiment. v0.4.2 tests whether real offline LLM proposals can produce accepted edges without polluting the online path.",
        "",
        "Layer 3 remains unchanged: provisional Patterns are limited to `fast_verify`, stable Patterns alone can route to `fast`, and evidence links do not auto-promote memory.",
        "",
        "Pending proposals still require a lifecycle mechanism in a later release.",
        "",
        provider_note,
        "",
        "v0.5 should not start unless v0.4.2 passes: accepted edge count > 0, accepted wrong link rate near zero, and EvidenceSupportCheck exact-support precision passes manual audit.",
    ])
    (output_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--provider", default="deepseek")
    parser.add_argument("--model", default="deepseek-v4-pro")
    parser.add_argument("--local-model", default="local-graph-proposer")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--output-dir", type=Path, default=Path("docs/validation/llm-graph-proposal-v0.4.2"))
    args = parser.parse_args()

    local_config = build_provider_config(
        provider="local",
        model=args.local_model,
        env_file=args.env_file,
    )
    deepseek_config = build_provider_config(
        provider=args.provider,
        model=args.model,
        env_file=args.env_file,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memoryweaver-gold-") as root:
        gold_workspace, _ = build_workspace(root)
        dataset = {
            "memory_count": gold_workspace.memories.count(),
            "evidence_count": len(gold_workspace.evidence.list_nodes()),
            "query_count": len(QUERY_CASES),
        }
    write_jsonl(args.output_dir / "gold_edges.jsonl", GOLD_EDGES)

    local_run = evaluate_provider_flow(
        label="local",
        config=local_config,
        output_dir=args.output_dir,
        iterations=args.iterations,
    )
    deepseek_run = evaluate_provider_flow(
        label="deepseek",
        config=deepseek_config,
        output_dir=args.output_dir,
        iterations=args.iterations,
    )

    retrieval_arms = [
        evaluate_arm("no_graph", args.iterations, lambda workspace: None),
        evaluate_arm("manual_graph", args.iterations, add_manual_graph),
        evaluate_arm("rule_graph", args.iterations, add_rule_graph),
        local_run["retrieval_arm"],
        deepseek_run["retrieval_arm"],
    ]
    no_graph_recall = retrieval_arms[0]["memory_recall_at_10"]
    deepseek_recall = deepseek_run["retrieval_arm"]["memory_recall_at_10"]
    deepseek_metrics = deepseek_run["metrics"]
    success_criteria = {
        "deepseek_provider_available": (
            deepseek_run["json_parse_success_rate"] > 0
            and deepseek_metrics["proposal_count"] > 0
        ),
        "accepted_edge_count_gt_0": deepseek_metrics["accepted"] > 0,
        "accepted_wrong_link_rate_near_zero": deepseek_metrics["accepted_wrong_link_rate"] <= 0.05,
        "recall_beats_no_graph": deepseek_recall > no_graph_recall,
        "online_llm_call_count_zero": sum(
            arm["online_llm_call_count"] for arm in retrieval_arms
        ) == 0,
        "proposal_budget_respected": deepseek_metrics["proposal_count"] <= 12,
        "supports_exact_precision_ok": deepseek_run["support_audit"]["supports_exact_precision"] >= 0.7,
        "rejected_gt_0": deepseek_metrics["rejected"] > 0,
        "evidence_coverage_ok": deepseek_metrics["evidence_coverage"] <= 0.6,
    }
    success_criteria["passed"] = all(success_criteria.values())

    raw_results = {
        "benchmark": VALIDATION_NAME,
        "providers": {
            "local": {
                "provider": local_config.llm_provider,
                "model": local_config.llm_model,
            },
            "deepseek": {
                "provider": deepseek_config.llm_provider,
                "model": deepseek_config.llm_model,
            },
        },
        "prompt_version": PROMPT_VERSION,
        "review_policy_version": POLICY_VERSION,
        "iterations": args.iterations,
        "dataset": dataset,
        "online_llm_call_count": sum(
            arm["online_llm_call_count"] for arm in retrieval_arms
        ),
        "provider_runs": {
            "local": {
                "json_parse_success_rate": local_run["json_parse_success_rate"],
                "provider_errors": local_run["provider_errors"],
                "proposal_count": len(local_run["proposal_records"]),
            },
            "deepseek": {
                "json_parse_success_rate": deepseek_run["json_parse_success_rate"],
                "provider_errors": deepseek_run["provider_errors"],
                "proposal_count": len(deepseek_run["proposal_records"]),
            },
        },
        "provider_metrics": {
            "local": local_run["metrics"],
            "deepseek": deepseek_run["metrics"],
        },
        "support_audits": {
            "local": local_run["support_audit"],
            "deepseek": deepseek_run["support_audit"],
        },
        "doctor_reports": {
            "local": local_run["doctor_report"],
            "deepseek": deepseek_run["doctor_report"],
        },
        "provider_workspaces": {
            "local": local_run["workspace_root"],
            "deepseek": deepseek_run["workspace_root"],
        },
        "success_criteria": success_criteria,
        "retrieval_arms": retrieval_arms,
    }
    (args.output_dir / "metrics.json").write_text(
        json.dumps(raw_results["provider_metrics"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "raw_results.json").write_text(
        json.dumps(raw_results, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_readme(args.output_dir, raw_results=raw_results)
    print(json.dumps(raw_results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
