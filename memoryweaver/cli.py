"""Command-line interface for the standalone MemoryWeaver SDK."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from memoryweaver import __version__
from memoryweaver.action_gate import ActionGate, ActionProposal
from memoryweaver.composer import PatternComposer
from memoryweaver.content_router import ContentRouter
from memoryweaver.contract import EnvironmentContract
from memoryweaver.context_schema import ContentType, RawSpan
from memoryweaver.evidence import EvidenceLink, EvidenceNode
from memoryweaver.harness import MemoryWeaverHarness
from memoryweaver.router import ModeRouter
from memoryweaver.schema import MemoryItem, Source
from memoryweaver.skill import SkillRetriever
from memoryweaver.store import MemoryWorkspace
from memoryweaver.trajectory import TrajectoryRegulator


def _add_common(parser: argparse.ArgumentParser, *, suppress_default: bool = False) -> None:
    default_root: Any = argparse.SUPPRESS if suppress_default else ".memoryweaver"
    default_json: Any = argparse.SUPPRESS if suppress_default else False
    parser.add_argument("--root", default=default_root, help="Workspace directory.")
    parser.add_argument(
        "--json",
        action="store_true",
        default=default_json,
        help="Emit machine-readable JSON.",
    )


def _leaf(subparsers: Any, name: str, help_text: str) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(name, help=help_text)
    _add_common(parser, suppress_default=True)
    return parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mw", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    _add_common(parser)
    commands = parser.add_subparsers(dest="command", required=True)

    _leaf(commands, "validate", "Validate workspace structure and policy gates.")
    _leaf(commands, "doctor", "Check workspace operational health.")

    memory = commands.add_parser("memory", help="Manage Layer 1 and Layer 2 memories.")
    memory_commands = memory.add_subparsers(dest="memory_command", required=True)
    memory_add = _leaf(memory_commands, "add", "Add a Layer 1 memory candidate.")
    memory_add.add_argument("--content", required=True)
    memory_add.add_argument("--source", required=True)
    memory_add.add_argument("--tag", action="append", default=[])
    memory_add.add_argument("--scope", default="project")
    memory_add.add_argument("--evidence", default="")
    _leaf(memory_commands, "list", "List memories.")
    memory_search = _leaf(memory_commands, "search", "Search verified memories.")
    memory_search_group = memory_search.add_mutually_exclusive_group(required=True)
    memory_search_group.add_argument("--query")
    memory_search_group.add_argument("--tag", action="append")
    memory_search.add_argument("--scope", default="project")
    memory_promote = _leaf(memory_commands, "promote", "Explicitly promote to Layer 2.")
    memory_promote.add_argument("memory_id")

    evidence = commands.add_parser("evidence", help="Manage citable evidence.")
    evidence_commands = evidence.add_subparsers(dest="evidence_command", required=True)
    evidence_add = _leaf(evidence_commands, "add", "Add an EvidenceNode.")
    evidence_add.add_argument("--text", required=True)
    evidence_add.add_argument("--source", required=True)
    evidence_add.add_argument("--uri", required=True)
    evidence_add.add_argument("--title", default="")
    evidence_add.add_argument("--language", default="unknown")
    _leaf(evidence_commands, "list", "List evidence nodes.")
    evidence_link = _leaf(evidence_commands, "link", "Link evidence to a memory or Pattern.")
    evidence_link.add_argument("--evidence-id", required=True)
    evidence_target = evidence_link.add_mutually_exclusive_group(required=True)
    evidence_target.add_argument("--memory-id")
    evidence_target.add_argument("--pattern-id")
    evidence_link.add_argument(
        "--relation",
        choices=["supports", "contradicts", "derived_from"],
        default="supports",
    )

    pattern = commands.add_parser("pattern", help="Manage canonical Layer-3 Patterns.")
    pattern_commands = pattern.add_subparsers(dest="pattern_command", required=True)
    pattern_compose = _leaf(pattern_commands, "compose", "Compose a provisional Pattern.")
    pattern_compose.add_argument("--memory-id", action="append", required=True)
    pattern_compose.add_argument("--evidence-link-id", action="append", required=True)
    pattern_compose.add_argument("--rule", required=True)
    pattern_compose.add_argument("--applies-when", action="append", default=[])
    pattern_compose.add_argument("--avoid-when", action="append", default=[])
    pattern_compose.add_argument("--success-path", action="append", default=[])
    pattern_compose.add_argument("--failed-path", action="append", default=[])
    pattern_compose.add_argument("--scope", default="project")
    _leaf(pattern_commands, "list", "List Patterns.")
    pattern_show = _leaf(pattern_commands, "show", "Show a Pattern.")
    pattern_show.add_argument("pattern_id")
    pattern_validate = _leaf(pattern_commands, "validate", "Record Pattern validation.")
    pattern_validate.add_argument("pattern_id")
    pattern_validate.add_argument("--task-run-id", required=True)
    pattern_outcome = pattern_validate.add_mutually_exclusive_group(required=True)
    pattern_outcome.add_argument("--success", action="store_true")
    pattern_outcome.add_argument("--failure", action="store_true")
    pattern_validate.add_argument("--conflict-ref", default="")
    pattern_trial = _leaf(
        pattern_commands,
        "trial",
        "Record a Layer-3 execution-path trial with utility metrics.",
    )
    pattern_trial.add_argument("pattern_id")
    pattern_trial.add_argument("--task-run-id", required=True)
    pattern_trial_outcome = pattern_trial.add_mutually_exclusive_group(required=True)
    pattern_trial_outcome.add_argument("--success", action="store_true")
    pattern_trial_outcome.add_argument("--failure", action="store_true")
    pattern_trial.add_argument("--steps-saved", type=int, default=0)
    pattern_trial.add_argument("--known-bad-avoided", type=int, default=0)
    pattern_trial.add_argument("--evidence-first", action="store_true")
    pattern_trial.add_argument("--false-trigger", action="store_true")
    pattern_trial.add_argument("--token-cost", type=float, default=0.0)
    pattern_trial.add_argument("--scope-mismatch", action="store_true")
    pattern_trial.add_argument("--recency-score", type=float, default=1.0)
    pattern_trial.add_argument("--conflict-ref", default="")
    pattern_promote = _leaf(
        pattern_commands,
        "promote-stable",
        "Explicitly promote a Pattern to stable.",
    )
    pattern_promote.add_argument("pattern_id")
    pattern_best_path = _leaf(
        pattern_commands,
        "best-path",
        "Rank the best promoted execution paths for a query.",
    )
    pattern_best_path.add_argument("--query", required=True)
    pattern_best_path.add_argument("--scope", default="project")
    pattern_best_path.add_argument("--limit", type=int, default=3)
    pattern_best_path.add_argument("--threshold", type=float, default=0.05)
    pattern_rollback = _leaf(pattern_commands, "rollback", "Rollback a Pattern.")
    pattern_rollback.add_argument("pattern_id")
    pattern_rollback.add_argument("--reason", required=True)

    route = _leaf(commands, "route", "Route a query using memories and Patterns.")
    route.add_argument("--query", required=True)
    route.add_argument("--scope", default="project")

    graph = commands.add_parser("graph", help="Manage low-privilege graph proposals.")
    graph_commands = graph.add_subparsers(dest="graph_command", required=True)
    graph_propose = _leaf(
        graph_commands,
        "propose",
        "Generate GraphProposal JSONL from a batch file.",
    )
    graph_propose.add_argument("--provider", default="local")
    graph_propose.add_argument("--model", default="")
    graph_propose.add_argument("--env-file", default=".env")
    graph_propose.add_argument("--input", required=True)
    graph_propose.add_argument("--output", required=True)
    graph_propose.add_argument("--path", choices=["offline", "online"], default="offline")
    graph_review = _leaf(
        graph_commands,
        "review",
        "Harness-review GraphProposal JSONL and write reviewed JSONL.",
    )
    graph_review.add_argument("--input", required=True)
    graph_review.add_argument("--output", required=True)
    graph_review.add_argument("--query", default="")
    graph_eval = _leaf(
        graph_commands,
        "eval",
        "Evaluate reviewed GraphProposal JSONL against gold edges.",
    )
    graph_eval.add_argument("--gold", required=True)
    graph_eval.add_argument("--pred", required=True)
    graph_eval.add_argument("--output", default="")

    context = commands.add_parser("context", help="Manage RAW context capsules.")
    context_commands = context.add_subparsers(dest="context_command", required=True)
    context_add = _leaf(context_commands, "add", "Add a RawSpan and ContextCapsule.")
    context_add.add_argument("--type", required=True, choices=[item.value for item in ContentType])
    context_add.add_argument("--source", required=True, choices=[item.value for item in Source])
    context_add.add_argument("--text", required=True)
    context_add.add_argument("--timestamp", default="")
    context_add.add_argument("--metadata-json", default="{}")
    context_search = _leaf(context_commands, "search", "Search ContextCapsules by tag/time.")
    context_search.add_argument("--tag", action="append", required=True)
    context_search.add_argument("--since", default="")
    context_search.add_argument("--until", default="")
    context_search.add_argument("--source", action="append", default=[])
    context_search.add_argument("--type", action="append", default=[])
    context_search.add_argument("--limit", type=int, default=20)
    context_raw = _leaf(context_commands, "raw", "Recover a RawSpan by raw_ref_id.")
    context_raw.add_argument("raw_span_id")
    _leaf(context_commands, "validate", "Validate ContextCapsule raw refs.")

    external = commands.add_parser("external", help="Import external benchmark context.")
    external_commands = external.add_subparsers(dest="external_command", required=True)
    lme_context = _leaf(
        external_commands,
        "lme-v2-context",
        "Build MemoryWeaver context from a local LongMemEval-V2 snapshot.",
    )
    lme_context.add_argument("--input-root", default="")
    lme_context.add_argument("--question-index", type=int, default=0)
    lme_context.add_argument("--trajectories-per-question", type=int, default=5)
    lme_context.add_argument("--states-per-trajectory", type=int, default=5)
    lme_context.add_argument("--no-write-context", action="store_true")
    lme_context.add_argument("--hf-cache-root", default="")
    lme_context.add_argument("--download-if-missing", action="store_true")
    manifest = _leaf(
        external_commands,
        "manifest",
        "Write a reproducibility manifest for repos or local snapshots.",
    )
    manifest.add_argument("--path", action="append", required=True)
    manifest.add_argument("--out", required=True)

    gbrain = commands.add_parser("gbrain", help="Sync and inspect GBrain/mind-map state.")
    gbrain_commands = gbrain.add_subparsers(dest="gbrain_command", required=True)
    _leaf(gbrain_commands, "sync", "Sync memories/evidence/patterns into GBrain.")
    mindmap = _leaf(gbrain_commands, "mindmap", "Project GBrain into a mind-map view.")
    mindmap.add_argument("--tag", action="append", default=[])
    mindmap.add_argument("--max-nodes", type=int, default=80)

    skill = commands.add_parser("skill", help="Retrieve procedural skills and avoidance memory.")
    skill_commands = skill.add_subparsers(dest="skill_command", required=True)
    skill_retrieve = _leaf(
        skill_commands,
        "retrieve",
        "Retrieve Layer-3 procedural skills and avoidance memory for a query.",
    )
    skill_retrieve.add_argument("--query", required=True)
    skill_retrieve.add_argument("--scope", default="project")
    skill_retrieve.add_argument("--limit", type=int, default=5)

    harness = commands.add_parser("harness", help="Inspect lifecycle harness stages.")
    harness_commands = harness.add_subparsers(dest="harness_command", required=True)
    harness_trace = _leaf(
        harness_commands,
        "trace",
        "Trace deterministic lifecycle stages for one query/action pair.",
    )
    harness_trace.add_argument("--query", required=True)
    harness_trace.add_argument("--tag", action="append", default=[])
    harness_trace.add_argument("--scope", default="project")
    harness_trace.add_argument("--arm", default="mw_marker")
    harness_trace.add_argument("--step", type=int, default=1)
    harness_trace.add_argument("--action-name", default="check_evidence")
    harness_trace.add_argument("--action-target", default="selected_organization")
    harness_trace.add_argument("--action-reasoning", default="")
    harness_trace.add_argument(
        "--result-json",
        default='{"status":"no_signal","signal":"neutral","evidence":""}',
    )

    contract = commands.add_parser("contract", help="Inspect EnvironmentContract state.")
    contract_commands = contract.add_subparsers(dest="contract_command", required=True)
    contract_show = _leaf(
        contract_commands,
        "show",
        "Show the default live-loop EnvironmentContract.",
    )
    contract_show.add_argument("--max-steps", type=int, default=8)
    contract_show.add_argument("--max-tool-calls", type=int, default=4)

    action = commands.add_parser("action", help="Validate structured ActionProposal objects.")
    action_commands = action.add_subparsers(dest="action_command", required=True)
    action_validate = _leaf(
        action_commands,
        "validate",
        "Validate an ActionProposal against the default EnvironmentContract.",
    )
    action_validate.add_argument("--name", required=True)
    action_validate.add_argument("--target", default="")
    action_validate.add_argument("--reasoning", default="")
    action_validate.add_argument("--timeout", type=int, default=30)
    action_validate.add_argument("--working-directory", default="")
    action_validate.add_argument("--idempotency-key", default="")
    action_validate.add_argument("--confirm", action="store_true")
    action_validate.add_argument("--budget-json", default="{}")

    trajectory = commands.add_parser("trajectory", help="Evaluate trajectory-regulation decisions.")
    trajectory_commands = trajectory.add_subparsers(dest="trajectory_command", required=True)
    trajectory_eval = _leaf(
        trajectory_commands,
        "evaluate",
        "Evaluate a sequence of action results with the default TrajectoryRegulator.",
    )
    trajectory_eval.add_argument("--events-json", required=True)
    trajectory_eval.add_argument("--max-steps", type=int, default=8)
    trajectory_eval.add_argument("--max-tool-calls", type=int, default=4)
    trajectory_eval.add_argument("--repeated-failure-limit", type=int, default=2)
    trajectory_eval.add_argument("--stagnation-window", type=int, default=2)

    layer = commands.add_parser("layer", help="Run Layer lifecycle operations.")
    layer_commands = layer.add_subparsers(dest="layer_command", required=True)
    _leaf(layer_commands, "smoke", "Run verified write/promote/retrieve/rollback smoke.")

    eval_cmd = commands.add_parser("eval", help="Run v0.7 validations and runtime smokes.")
    eval_commands = eval_cmd.add_subparsers(dest="eval_command", required=True)
    tau_smoke = _leaf(eval_commands, "tau-smoke", "Run tau-style live-loop smoke.")
    tau_smoke.add_argument("--task-id", default="tau_smoke_codex_subscription")
    tau_smoke.add_argument("--max-steps", type=int, default=5)
    tau_llm = _leaf(
        eval_commands,
        "tau-llm-smoke",
        "Run tau-style live-loop smoke with real LLM action selection.",
    )
    tau_llm.add_argument("--task-id", default="tau_llm_smoke_codex_subscription")
    tau_llm.add_argument("--max-steps", type=int, default=5)
    tau_llm.add_argument("--provider", default="deepseek")
    tau_llm.add_argument("--model", default="deepseek-chat")
    tau_llm.add_argument("--base-url", default="")
    tau_llm.add_argument("--env-file", default=".env")
    live_memory = _leaf(eval_commands, "live-memory-loop", "Run lifecycle smoke via eval.")
    live_memory.add_argument("--output", default="")
    path_promotion = _leaf(
        eval_commands,
        "path-promotion",
        "Run Layer-3 path-promotion validation.",
    )
    path_promotion.add_argument("--output", default="")
    lme_v2_path_promotion = _leaf(
        eval_commands,
        "path-promotion-lme-v2",
        "Run Layer-3 path-promotion on a real LongMemEval-V2 snapshot subset.",
    )
    lme_v2_path_promotion.add_argument("--output", default="")
    lme_v2_path_promotion.add_argument("--input-root", default="")
    lme_v2_path_promotion.add_argument("--question-limit", type=int, default=5)
    lme_v2_path_promotion.add_argument("--trajectories-per-question", type=int, default=1)
    lme_v2_path_promotion.add_argument("--states-per-trajectory", type=int, default=2)
    lme_v2_path_promotion.add_argument("--hf-cache-root", default="")
    lme_v2_path_promotion.add_argument("--download-if-missing", action="store_true")
    return parser


def _emit(payload: Any, json_output: bool) -> None:
    if json_output or isinstance(payload, (dict, list)):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(payload)


def _composer(workspace: MemoryWorkspace) -> PatternComposer:
    return PatternComposer(
        workspace.memories,
        workspace.patterns,
        workspace.evidence,
        workspace.memory_policy,
    )


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def _write_jsonl(path: str | Path, records: list[dict[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def dispatch(args: argparse.Namespace) -> int:
    workspace = MemoryWorkspace(args.root)
    json_output = args.json

    if args.command == "validate":
        report = workspace.validate()
        report["cli_import"] = True
        _emit(report, json_output)
        return 0 if report["valid"] else 1

    if args.command == "doctor":
        report = workspace.doctor()
        _emit(report, json_output)
        return 0 if report["valid"] else 1

    if args.command == "memory":
        if args.memory_command == "add":
            item = MemoryItem(
                content=args.content,
                source=args.source,
                tags=args.tag,
                scope=args.scope,
                evidence=args.evidence,
            )
            workspace.memories.add(item)
            _emit(item.to_dict(), json_output)
        elif args.memory_command == "list":
            _emit([item.to_dict() for item in workspace.memories.list_all()], json_output)
        elif args.memory_command == "search":
            from memoryweaver.retriever import VerifiedRetriever

            retriever = VerifiedRetriever(
                workspace.memories,
                workspace.retrieval_policy,
            )
            results = (
                retriever.search(args.query, scope=args.scope)
                if args.query
                else retriever.search_by_tags(args.tag, scope=args.scope)
            )
            _emit([item.to_dict() for item in results], json_output)
        elif args.memory_command == "promote":
            item = workspace.memories.get(args.memory_id)
            if item is None:
                raise KeyError(f"MemoryItem '{args.memory_id}' not found")
            links = workspace.evidence.links_for_memory(item.id)
            workspace.memory_policy.promote_to_layer2(item, links)
            workspace.memories.update(item)
            _emit(item.to_dict(), json_output)
        return 0

    if args.command == "evidence":
        if args.evidence_command == "add":
            node = EvidenceNode(
                text=args.text,
                source=args.source,
                source_uri=args.uri,
                title=args.title,
                language=args.language,
            )
            workspace.evidence.add_node(node)
            _emit(node.to_dict(), json_output)
        elif args.evidence_command == "list":
            _emit([node.to_dict() for node in workspace.evidence.list_nodes()], json_output)
        elif args.evidence_command == "link":
            link = EvidenceLink(
                evidence_id=args.evidence_id,
                relation=args.relation,
                memory_id=args.memory_id or "",
                pattern_id=args.pattern_id or "",
            )
            workspace.evidence.add_link(link)
            _emit(link.to_dict(), json_output)
        return 0

    if args.command == "pattern":
        composer = _composer(workspace)
        if args.pattern_command == "compose":
            pattern = composer.compose(
                supporting_memory_ids=args.memory_id,
                rule=args.rule,
                applies_when=args.applies_when,
                avoid_when=args.avoid_when,
                success_path=args.success_path,
                failed_path=args.failed_path,
                evidence_link_ids=args.evidence_link_id,
                scope=args.scope,
            )
            _emit(pattern.to_dict(), json_output)
        elif args.pattern_command == "list":
            _emit([p.to_dict() for p in workspace.patterns.list_all()], json_output)
        elif args.pattern_command == "show":
            pattern = workspace.patterns.get(args.pattern_id)
            if pattern is None:
                raise KeyError(f"Pattern '{args.pattern_id}' not found")
            _emit(pattern.to_dict(), json_output)
        elif args.pattern_command == "validate":
            pattern = composer.record_validation(
                args.pattern_id,
                args.task_run_id,
                args.success,
                args.conflict_ref,
            )
            _emit(pattern.to_dict(), json_output)
        elif args.pattern_command == "trial":
            pattern = composer.record_path_trial(
                args.pattern_id,
                task_run_id=args.task_run_id,
                successful=args.success,
                steps_saved=args.steps_saved,
                known_bad_avoided=args.known_bad_avoided,
                evidence_first=args.evidence_first,
                false_trigger=args.false_trigger,
                token_cost=args.token_cost,
                scope_match=not args.scope_mismatch,
                recency_score=args.recency_score,
                conflict_ref=args.conflict_ref,
            )
            _emit(pattern.to_dict(), json_output)
        elif args.pattern_command == "promote-stable":
            _emit(composer.promote_stable(args.pattern_id).to_dict(), json_output)
        elif args.pattern_command == "best-path":
            _emit(
                [
                    pattern.to_dict()
                    for pattern in composer.select_best_path(
                        args.query,
                        scope=args.scope,
                        limit=args.limit,
                        threshold=args.threshold,
                    )
                ],
                json_output,
            )
        elif args.pattern_command == "rollback":
            _emit(composer.rollback(args.pattern_id, args.reason).to_dict(), json_output)
        return 0

    if args.command == "route":
        decision = ModeRouter(
            workspace.memories,
            pattern_store=workspace.patterns,
            retrieval_policy=workspace.retrieval_policy,
        ).route(args.query, scope=args.scope)
        _emit({
            "mode": decision.mode.value,
            "reason": decision.reason,
            "confidence": decision.confidence,
            "matched_items": [item.id for item in decision.matched_items],
            "matched_patterns": [p.id for p in decision.matched_patterns],
            "warnings": decision.warnings,
        }, json_output)
        return 0

    if args.command == "graph":
        if args.graph_command == "propose":
            from memoryweaver.config import MemoryWeaverConfig
            from memoryweaver.graph.budget import ProposalBudgetGate
            from memoryweaver.graph.proposal_generator import BatchGraphProposalGenerator

            budget_decision = ProposalBudgetGate().allow_llm_proposal(path=args.path)
            if not budget_decision.allowed:
                raise ValueError("; ".join(budget_decision.reasons))
            env = dict(os.environ)
            env.update({
                "MEMORYWEAVER_ENABLE_LLM_GRAPH_PROPOSAL": "true",
                "MEMORYWEAVER_LLM_PROVIDER": args.provider,
            })
            if args.model:
                env["MEMORYWEAVER_LLM_MODEL"] = args.model
            config = MemoryWeaverConfig.from_env(env=env, env_file=args.env_file)
            generator = BatchGraphProposalGenerator(config)
            output_records: list[dict[str, Any]] = []
            for result in generator.generate(_read_jsonl(args.input)):
                output_records.extend(result.to_records())
            _write_jsonl(args.output, output_records)
            _emit({
                "provider": config.llm_provider,
                "model": config.llm_model,
                "proposal_count": len(output_records),
                "output": args.output,
            }, json_output)
        elif args.graph_command == "review":
            from memoryweaver.graph.evidence_binder import GraphEvidenceBinder
            from memoryweaver.graph.evidence_support import EvidenceSupportCheck
            from memoryweaver.graph.linker import ReviewedGraphLinker
            from memoryweaver.graph.reviewer import GraphProposalReviewPolicy
            from memoryweaver.graph_schema import GraphProposal

            binder = GraphEvidenceBinder(workspace.evidence)
            linker = ReviewedGraphLinker(
                workspace.graph,
                GraphProposalReviewPolicy(
                    workspace.graph,
                    evidence_check=EvidenceSupportCheck(workspace.evidence),
                ),
            )
            reviewed: list[dict[str, Any]] = []
            for record in _read_jsonl(args.input):
                proposal_data = record.get("proposal", record)
                proposal = GraphProposal.from_dict(proposal_data)
                binder.bind(proposal, query=args.query or str(record.get("query", "")))
                review, edge_id = linker.review_and_apply(proposal)
                reviewed.append({
                    "input_id": record.get("input_id", ""),
                    "query": record.get("query", args.query),
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
            _write_jsonl(args.output, reviewed)
            _emit({
                "reviewed_count": len(reviewed),
                "output": args.output,
            }, json_output)
        elif args.graph_command == "eval":
            from memoryweaver.graph.proposal_eval import evaluate_proposals

            metrics = evaluate_proposals(
                _read_jsonl(args.gold),
                _read_jsonl(args.pred),
            ).to_dict()
            if args.output:
                Path(args.output).parent.mkdir(parents=True, exist_ok=True)
                Path(args.output).write_text(
                    json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            _emit(metrics, json_output)
        return 0

    if args.command == "context":
        if args.context_command == "add":
            metadata = json.loads(args.metadata_json)
            raw_kwargs: dict[str, Any] = {
                "content": args.text,
                "content_type": args.type,
                "source": args.source,
                "metadata": metadata,
            }
            if args.timestamp:
                raw_kwargs["timestamp"] = args.timestamp
            raw_span = RawSpan(**raw_kwargs)
            workspace.raw_spans.add(raw_span)
            capsule = ContentRouter().compress(raw_span)
            workspace.context_capsules.add(capsule)
            workspace.tag_time_index.add(capsule)
            _emit({
                "raw_span": raw_span.to_dict(),
                "capsule": capsule.to_dict(),
            }, json_output)
        elif args.context_command == "search":
            capsule_ids = workspace.tag_time_index.search(
                tags=args.tag,
                since=args.since,
                until=args.until,
                sources=[Source(source) for source in args.source],
                content_types=[ContentType(content_type) for content_type in args.type],
            )
            capsules = [
                workspace.context_capsules.get(capsule_id)
                for capsule_id in capsule_ids[: args.limit]
            ]
            _emit([
                capsule.to_dict()
                for capsule in capsules
                if capsule is not None
            ], json_output)
        elif args.context_command == "raw":
            raw_span = workspace.raw_spans.get(args.raw_span_id)
            if raw_span is None:
                raise KeyError(f"RawSpan '{args.raw_span_id}' not found")
            _emit(raw_span.to_dict(), json_output)
        elif args.context_command == "validate":
            raw_ids = {raw_span.id for raw_span in workspace.raw_spans.list_all()}
            errors = workspace.context_capsules.validate_raw_refs(raw_ids)
            report = {
                "valid": not errors,
                "raw_span_count": len(raw_ids),
                "capsule_count": len(workspace.context_capsules.list_all()),
                "errors": errors,
            }
            _emit(report, json_output)
            return 0 if report["valid"] else 1
        return 0

    if args.command == "external":
        if args.external_command == "lme-v2-context":
            from memoryweaver.integrations import MemoryWeaverModule

            module = MemoryWeaverModule(
                workspace,
                write_context=not args.no_write_context,
                write_memory=False,
            )
            context = module.build_context_from_local_snapshot(
                Path(args.input_root) if args.input_root else None,
                question_index=args.question_index,
                trajectories_per_question=args.trajectories_per_question,
                states_per_trajectory=args.states_per_trajectory,
                hf_cache_root=Path(args.hf_cache_root) if args.hf_cache_root else None,
                allow_download=args.download_if_missing,
            )
            _emit(context.to_dict(), json_output)
        elif args.external_command == "manifest":
            from memoryweaver.external.manifest import write_manifest

            manifest = write_manifest(
                [Path(path) for path in args.path],
                Path(args.out),
            )
            _emit(
                {
                    "output": args.out,
                    "entry_count": len(manifest["entries"]),
                    "schema_version": manifest["schema_version"],
                },
                json_output,
            )
        return 0

    if args.command == "gbrain":
        from memoryweaver.gbrain import GBrain

        gbrain = GBrain(workspace)
        if args.gbrain_command == "sync":
            _emit(gbrain.sync_workspace(), json_output)
        elif args.gbrain_command == "mindmap":
            projection = gbrain.project_mind_map(
                center_tags=args.tag,
                max_nodes=args.max_nodes,
            )
            _emit(projection.to_dict(), json_output)
        return 0

    if args.command == "skill":
        if args.skill_command == "retrieve":
            retriever = SkillRetriever(
                workspace.memories,
                workspace.patterns,
            )
            retriever.set_composer(_composer(workspace))
            result = retriever.retrieve(
                args.query,
                scope=args.scope,
                limit=args.limit,
            )
            _emit(result.to_dict(), json_output)
        return 0

    if args.command == "harness":
        if args.harness_command == "trace":
            from memoryweaver.runtime import LiveAction

            harness = MemoryWeaverHarness(workspace)
            before = harness.before_interaction(args.query, scope=args.scope)
            conditioning = harness.task_conditioning(
                args.query,
                tags=args.tag,
                scope=args.scope,
                arm=args.arm,
                step=args.step,
            )
            action = LiveAction(
                name=args.action_name,
                target=args.action_target,
                reasoning=args.action_reasoning,
            )
            execution = harness.before_execution(
                action,
                task_id="cli_harness_trace",
                step=args.step,
            )
            result = json.loads(args.result_json)
            feedback = harness.after_feedback(
                step=args.step,
                proposal=execution.proposal,
                result=result,
                gate_status=execution.decision.status.value,
            )
            outcome = harness.after_task_outcome(
                task_id="cli_harness_trace",
                step=args.step,
                action=action,
                result=result,
            )
            _emit(
                {
                    "before_interaction": before.to_dict(),
                    "task_conditioning": conditioning.to_dict(),
                    "before_execution": execution.to_dict(),
                    "after_feedback": feedback.to_dict(),
                    "after_task_outcome": outcome.to_dict(),
                },
                json_output,
            )
            return 0 if execution.decision.allowed else 1
        return 0

    if args.command == "contract":
        if args.contract_command == "show":
            contract = EnvironmentContract.default_live_loop(
                max_steps=args.max_steps,
                max_tool_calls=args.max_tool_calls,
            )
            _emit(contract.to_dict(), json_output)
        return 0

    if args.command == "action":
        if args.action_command == "validate":
            proposal = ActionProposal(
                action_name=args.name,
                target=args.target,
                arguments={"target": args.target} if args.target else {},
                reasoning=args.reasoning,
                working_directory=args.working_directory,
                timeout_seconds=args.timeout,
                idempotency_key=args.idempotency_key,
                user_confirmation=args.confirm,
                resource_budget=json.loads(args.budget_json),
            )
            contract = EnvironmentContract.default_live_loop()
            decision = ActionGate(contract).validate(proposal)
            _emit(
                {
                    "proposal": proposal.to_dict(),
                    "contract_id": contract.contract_id,
                    "contract_version": contract.version,
                    "decision": decision.to_dict(),
                },
                json_output,
            )
            return 0 if decision.allowed else 1
        return 0

    if args.command == "trajectory":
        if args.trajectory_command == "evaluate":
            regulator = TrajectoryRegulator(
                max_steps=args.max_steps,
                max_tool_calls=args.max_tool_calls,
                repeated_failure_limit=args.repeated_failure_limit,
                stagnation_window=args.stagnation_window,
            )
            events = json.loads(args.events_json)
            decisions: list[dict[str, Any]] = []
            for index, event in enumerate(events, start=1):
                proposal = ActionProposal(
                    action_name=str(event.get("action_name", "")),
                    target=str(event.get("target", "")),
                    idempotency_key=str(
                        event.get(
                            "idempotency_key",
                            f"trajectory:{index}:{event.get('action_name', '')}:{event.get('target', '')}",
                        )
                    ),
                )
                decision = regulator.observe(
                    step=int(event.get("step", index)),
                    proposal=proposal,
                    result=dict(event.get("result", {})),
                    gate_status=str(event.get("gate_status", "allow")),
                )
                decisions.append(
                    {
                        "step": int(event.get("step", index)),
                        "proposal": proposal.to_dict(),
                        "decision": decision.to_dict(),
                    }
                )
            report = {
                "history": [record.to_dict() for record in regulator.history],
                "decisions": decisions,
                "final_decision": decisions[-1]["decision"] if decisions else {},
            }
            _emit(report, json_output)
            final_status = report["final_decision"].get("status", "continue")
            return 0 if final_status != "halt" else 1
        return 0

    if args.command == "layer":
        from memoryweaver.lifecycle import MemoryLifecycle

        if args.layer_command == "smoke":
            result = MemoryLifecycle(workspace).run_codex_subscription_smoke()
            _emit(result, json_output)
            return 0 if result["passed"] else 1
        return 0

    if args.command == "eval":
        if args.eval_command == "tau-smoke":
            from memoryweaver.runtime import MemoryWeaverLiveLoop, MockTauEnv, RuleAgent

            result = MemoryWeaverLiveLoop(workspace).run(
                task_id=args.task_id,
                env=MockTauEnv(),
                agent=RuleAgent(),
                max_steps=args.max_steps,
                arm="mw_marker",
            )
            _emit(result.to_dict(), json_output)
            return 0 if result.success and result.verified_memory_write_count > 0 else 1
        if args.eval_command == "tau-llm-smoke":
            from memoryweaver.config import MemoryWeaverConfig
            from memoryweaver.runtime import (
                MemoryWeaverLiveLoop,
                MockTauEnv,
                OpenAICompatibleAgent,
            )

            config = MemoryWeaverConfig.from_env(env_file=args.env_file)
            agent = OpenAICompatibleAgent.from_config(
                config,
                provider=args.provider,
                model=args.model,
                base_url=args.base_url,
            )
            result = MemoryWeaverLiveLoop(workspace).run(
                task_id=args.task_id,
                env=MockTauEnv(),
                agent=agent,
                max_steps=args.max_steps,
                arm="mw_marker",
            )
            _emit(result.to_dict(), json_output)
            return 0 if (
                result.success
                and result.verified_memory_write_count > 0
                and result.online_llm_call_count > 0
            ) else 1
        if args.eval_command == "live-memory-loop":
            from memoryweaver.lifecycle import MemoryLifecycle

            result = MemoryLifecycle(workspace).run_codex_subscription_smoke()
            if args.output:
                Path(args.output).parent.mkdir(parents=True, exist_ok=True)
                Path(args.output).write_text(
                    json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            _emit(result, json_output)
            return 0 if result["passed"] else 1
        if args.eval_command == "path-promotion":
            from benchmarks.layer3_path_promotion_v0_7 import run as run_path_promotion

            output_root = (
                Path(args.output)
                if args.output
                else (workspace.root / "layer3-path-promotion-eval")
            )
            result = run_path_promotion(output_root)
            _emit(result, json_output)
            return 0 if result["passed"] else 1
        if args.eval_command == "path-promotion-lme-v2":
            from benchmarks.layer3_path_promotion_lme_v2 import run as run_lme_v2_path_promotion

            output_root = (
                Path(args.output)
                if args.output
                else (workspace.root / "layer3-path-promotion-lme-v2-eval")
            )
            result = run_lme_v2_path_promotion(
                output_root,
                input_root=Path(args.input_root) if args.input_root else None,
                question_limit=args.question_limit,
                trajectories_per_question=args.trajectories_per_question,
                states_per_trajectory=args.states_per_trajectory,
                hf_cache_root=Path(args.hf_cache_root) if args.hf_cache_root else None,
                allow_download=args.download_if_missing,
            )
            _emit(result, json_output)
            return 0 if result["passed"] else 1
        return 0

    raise ValueError(f"unsupported command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return dispatch(args)
    except (KeyError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
