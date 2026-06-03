"""Command-line interface for the standalone MemoryWeaver SDK."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from memoryweaver import __version__
from memoryweaver.composer import PatternComposer
from memoryweaver.evidence import EvidenceLink, EvidenceNode
from memoryweaver.router import ModeRouter
from memoryweaver.schema import MemoryItem
from memoryweaver.store import MemoryWorkspace


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
    pattern_promote = _leaf(
        pattern_commands,
        "promote-stable",
        "Explicitly promote a Pattern to stable.",
    )
    pattern_promote.add_argument("pattern_id")
    pattern_rollback = _leaf(pattern_commands, "rollback", "Rollback a Pattern.")
    pattern_rollback.add_argument("pattern_id")
    pattern_rollback.add_argument("--reason", required=True)

    route = _leaf(commands, "route", "Route a query using memories and Patterns.")
    route.add_argument("--query", required=True)
    route.add_argument("--scope", default="project")
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


def dispatch(args: argparse.Namespace) -> int:
    workspace = MemoryWorkspace(args.root)
    json_output = args.json

    if args.command == "validate":
        report = workspace.validate()
        report["cli_import"] = True
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
        elif args.pattern_command == "promote-stable":
            _emit(composer.promote_stable(args.pattern_id).to_dict(), json_output)
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
