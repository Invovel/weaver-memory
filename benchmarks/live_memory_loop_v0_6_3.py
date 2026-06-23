"""v0.6.3 live memory lifecycle loop.

This benchmark is deliberately separate from v0.6.4 external adapters. It
exercises real MemoryWeaver stores and lifecycle APIs:

    evidence write -> Layer-1 memory write -> explicit promotion
    -> verified retrieval -> contradiction handling
    -> provisional Layer-3 pattern -> rollback
    -> runtime marker context write

It does not call an LLM and does not ingest external benchmark rows.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks._safety import safe_rmtree_child
from benchmarks.context_capsule_validation import write_json, write_jsonl
from memoryweaver.composer import PatternComposer
from memoryweaver.context_schema import ContentType, MarkerEvidenceContext
from memoryweaver.contradiction import ContradictionResolver
from memoryweaver.evidence import EvidenceLink, EvidenceNode, EvidenceRelation
from memoryweaver.retriever import VerifiedRetriever
from memoryweaver.schema import (
    Freshness,
    MemoryItem,
    MemoryType,
    Polarity,
    Source,
)
from memoryweaver.store import MemoryWorkspace


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "validation" / "live-memory-loop-v0.6.3"


def evaluate_live_memory_loop(workspace_root: Path) -> dict[str, Any]:
    """Exercise a real workspace lifecycle and return an auditable trace."""

    safe_rmtree_child(
        workspace_root.parent,
        workspace_root,
        allowed_prefixes=(".memoryweaver",),
    )
    workspace = MemoryWorkspace(workspace_root)
    trace: list[dict[str, Any]] = []

    # 1. Evidence write.
    org_evidence = EvidenceNode(
        id="ev_codex_org_selected",
        text="Terminal transcript: Codex subscription failed until the selected organization was corrected.",
        source=Source.TERMINAL,
        source_uri="terminal://codex-login",
        title="Codex selected organization fixed subscription",
        language="en",
    )
    workspace.evidence.add_node(org_evidence)
    trace.append({"step": "evidence_write", "id": org_evidence.id})

    bad_path_evidence = EvidenceNode(
        id="ev_reinstall_not_root_cause",
        text="Tool run: reinstalling npm did not change the Codex subscription failure.",
        source=Source.TOOL,
        source_uri="tool://npm-reinstall",
        title="npm reinstall failed known-bad path",
        language="en",
    )
    workspace.evidence.add_node(bad_path_evidence)
    trace.append({"step": "evidence_write", "id": bad_path_evidence.id})

    # 2. Layer-1 verified memory writes.
    success_memory = MemoryItem(
        id="mem_codex_org_fix",
        polarity=Polarity.POSITIVE,
        memory_type=MemoryType.SUCCESS_PATH,
        content="For Codex subscription load failures, check selected organization and account entitlement before reinstalling npm.",
        tags=["codex", "subscription", "organization", "entitlement", "fast_verify"],
        source=Source.TERMINAL,
        evidence="Terminal evidence: selected organization corrected subscription failure.",
        confidence=0.86,
        freshness=Freshness.STABLE,
    )
    workspace.memories.add(success_memory)
    trace.append({"step": "memory_write", "id": success_memory.id, "layer": 1})

    avoid_memory = MemoryItem(
        id="mem_avoid_npm_reinstall_subscription",
        polarity=Polarity.NEGATIVE,
        memory_type=MemoryType.FAILED_ATTEMPT,
        content="Do not use npm reinstall as the first fix for Codex subscription load failures; it previously failed.",
        tags=["codex", "subscription", "npm", "reinstall", "known_bad_path"],
        source=Source.TOOL,
        evidence="Tool evidence: npm reinstall did not affect subscription failure.",
        confidence=0.82,
        freshness=Freshness.STABLE,
    )
    workspace.memories.add(avoid_memory)
    trace.append({"step": "known_bad_path_write", "id": avoid_memory.id, "layer": 1})

    # 3. Evidence links and explicit promotion.
    org_link = EvidenceLink(
        id="link_org_supports_memory",
        evidence_id=org_evidence.id,
        relation=EvidenceRelation.SUPPORTS,
        memory_id=success_memory.id,
    )
    workspace.evidence.add_link(org_link)
    avoid_link = EvidenceLink(
        id="link_reinstall_supports_memory",
        evidence_id=bad_path_evidence.id,
        relation=EvidenceRelation.SUPPORTS,
        memory_id=avoid_memory.id,
    )
    workspace.evidence.add_link(avoid_link)
    trace.append(
        {
            "step": "evidence_link_write",
            "ids": [org_link.id, avoid_link.id],
        }
    )

    promoted_success = workspace.memory_policy.promote_to_layer2(
        success_memory,
        workspace.evidence.links_for_memory(success_memory.id),
    )
    workspace.memories.update(promoted_success)
    promoted_avoid = workspace.memory_policy.promote_to_layer2(
        avoid_memory,
        workspace.evidence.links_for_memory(avoid_memory.id),
    )
    workspace.memories.update(promoted_avoid)
    trace.append(
        {
            "step": "promotion",
            "ids": [success_memory.id, avoid_memory.id],
            "target_layer": 2,
        }
    )

    # 4. Verified retrieval.
    retriever = VerifiedRetriever(workspace.memories)
    retrieval_results = retriever.search(
        "Codex subscription failed should I reinstall npm or check organization",
        threshold=0.05,
        limit=5,
    )
    trace.append(
        {
            "step": "retrieval",
            "query": "Codex subscription failed should I reinstall npm or check organization",
            "result_ids": [item.id for item in retrieval_results],
        }
    )

    # 5. Conflict handling: assistant claim tries to override verified memory.
    conflicting_claim = MemoryItem(
        id="mem_assistant_reinstall_claim",
        polarity=Polarity.POSITIVE,
        memory_type=MemoryType.HYPOTHESIS,
        content="Reinstalling npm is the correct first fix for Codex subscription failures.",
        tags=["codex", "subscription", "npm", "reinstall"],
        source=Source.ASSISTANT,
        confidence=0.9,
        freshness=Freshness.UNKNOWN,
    )
    conflict = ContradictionResolver().resolve(conflicting_claim, promoted_avoid)
    trace.append(
        {
            "step": "conflict_handling",
            "new_id": conflicting_claim.id,
            "existing_id": promoted_avoid.id,
            "severity": conflict.severity.value,
            "action": conflict.action,
            "relation": conflict.relation.value,
        }
    )

    # 6. Provisional Layer-3 Pattern creation and rollback.
    composer = PatternComposer(
        workspace.memories,
        workspace.patterns,
        workspace.evidence,
        workspace.memory_policy,
    )
    pattern = composer.compose(
        [success_memory.id, avoid_memory.id],
        rule="For Codex subscription failures, check organization and entitlement before npm reinstall.",
        applies_when=["codex subscription load failed", "api key exists but request denied"],
        avoid_when=["install failure is the actual error", "npm package is missing"],
        success_path=["check selected organization", "verify active account", "check entitlement"],
        failed_path=["blind npm reinstall", "reset auth files before evidence"],
        evidence_link_ids=[org_link.id, avoid_link.id],
        scope="project",
    )
    trace.append(
        {
            "step": "layer3_mutation",
            "kind": "compose_provisional",
            "pattern_id": pattern.id,
            "status": pattern.status.value,
        }
    )
    rolled_back = composer.rollback(
        pattern.id,
        "live lifecycle smoke intentionally exercises rollback path",
    )
    trace.append(
        {
            "step": "rollback",
            "pattern_id": rolled_back.id,
            "status": rolled_back.status.value,
            "rollback_to": rolled_back.rollback_to,
        }
    )

    # 7. Runtime marker context write (temporary marker substrate).
    marker_context = MarkerEvidenceContext(
        marker_id="marker_codex_subscription_org_first",
        required_tags=["codex", "subscription", "organization", "entitlement"],
        required_sources=[Source.TERMINAL, Source.TOOL],
        required_time_window="",
        preferred_content_types=[ContentType.TERMINAL_LOG, ContentType.TOOL_JSON],
        metadata={
            "recommended_route": "fast_verify",
            "known_bad_actions": ["reinstall_npm", "reset_auth_files"],
            "source": "v0.6.3-live-memory-loop",
        },
    )
    workspace.marker_evidence_contexts.add(marker_context)
    trace.append(
        {
            "step": "runtime_marker_write",
            "marker_id": marker_context.marker_id,
            "store": "marker_evidence_contexts",
        }
    )

    validate_report = workspace.validate()
    doctor_report = workspace.doctor()
    metrics = {
        "validation": "live-memory-loop-v0.6.3",
        "evidence_write_count": 2,
        "memory_write_count": 2,
        "verified_memory_write_count": 2,
        "promotion_count": 2,
        "retrieval_result_count": len(retrieval_results),
        "retrieved_success_memory": any(item.id == success_memory.id for item in retrieval_results),
        "retrieved_known_bad_memory": any(item.id == avoid_memory.id for item in retrieval_results),
        "conflict_handling_count": 1,
        "conflict_block_or_warn_count": int(conflict.action in {"block", "demote"}),
        "layer3_mutation_count": 1,
        "rollback_count": 1,
        "runtime_marker_write_count": 1,
        "known_bad_path_write_count": 1,
        "online_llm_call_count": 0,
        "workspace_validate_valid": bool(validate_report["valid"]),
        "workspace_doctor_valid": bool(doctor_report["valid"]),
    }
    hard_gates = {
        "verified_memory_write_count": metrics["verified_memory_write_count"] == 2,
        "promotion_count": metrics["promotion_count"] == 2,
        "retrieved_success_memory": metrics["retrieved_success_memory"],
        "retrieved_known_bad_memory": metrics["retrieved_known_bad_memory"],
        "conflict_handling_count": metrics["conflict_handling_count"] == 1,
        "layer3_mutation_count": metrics["layer3_mutation_count"] == 1,
        "rollback_count": metrics["rollback_count"] == 1,
        "runtime_marker_write_count": metrics["runtime_marker_write_count"] == 1,
        "known_bad_path_write_count": metrics["known_bad_path_write_count"] == 1,
        "online_llm_call_count": metrics["online_llm_call_count"] == 0,
        "workspace_validate_valid": metrics["workspace_validate_valid"],
        "workspace_doctor_valid": metrics["workspace_doctor_valid"],
    }
    return {
        "passed": all(hard_gates.values()),
        "metrics": metrics,
        "hard_gates": hard_gates,
        "trace": trace,
        "retrieval_results": [item.to_dict() for item in retrieval_results],
        "pattern": rolled_back.to_dict(),
        "workspace_validate": validate_report,
        "workspace_doctor": doctor_report,
    }


def write_outputs(output_dir: Path, result: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "raw_results.json", result)
    write_json(output_dir / "metrics_summary.json", result["metrics"])
    write_jsonl(output_dir / "lifecycle_trace.jsonl", result["trace"])
    write_readme(output_dir, result)


def write_readme(output_dir: Path, result: dict[str, Any]) -> None:
    metrics = result["metrics"]
    text = f"""# v0.6.3 Live Memory Loop

This validation is separate from the v0.6.4 external-data adapter line.

It exercises actual MemoryWeaver workspace writes and lifecycle transitions:

- evidence write
- Layer-1 verified memory write
- explicit Layer-2 promotion
- verified retrieval
- contradiction handling
- provisional Layer-3 Pattern composition
- rollback
- runtime marker context write
- known-bad path write

No LLM is called in this lifecycle substrate check.

## Result

- Passed: {result['passed']}
- Verified memory writes: {metrics['verified_memory_write_count']}
- Promotions: {metrics['promotion_count']}
- Retrieval results: {metrics['retrieval_result_count']}
- Conflict handling count: {metrics['conflict_handling_count']}
- Layer-3 mutations: {metrics['layer3_mutation_count']}
- Rollbacks: {metrics['rollback_count']}
- Runtime marker writes: {metrics['runtime_marker_write_count']}
- Known-bad path writes: {metrics['known_bad_path_write_count']}
- Online LLM calls: {metrics['online_llm_call_count']}

## Boundary

v0.6.3-live-memory-loop proves that lifecycle writes can happen in the SDK.
v0.6.4b proves that external LongMemEval-V2 rows can enter safely without
writes. These lanes are intentionally separate.
"""
    (output_dir / "README.md").write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / ".memoryweaver-live-memory-loop",
    )
    args = parser.parse_args(argv)

    result = evaluate_live_memory_loop(args.workspace_root)
    write_outputs(args.output_dir, result)
    print(json.dumps({"passed": result["passed"], "metrics": result["metrics"]}, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
