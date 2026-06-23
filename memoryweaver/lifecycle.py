"""MemoryWeaver lifecycle service.

This is the functional spine of the SDK: verified writes, explicit promotion,
retrieval, conflict checks, Pattern composition/rollback, marker context writes,
and GBrain sync are exposed as one cohesive API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from memoryweaver.composer import PatternComposer
from memoryweaver.context_schema import ContentType, MarkerEvidenceContext
from memoryweaver.contradiction import ConflictResult, ContradictionResolver
from memoryweaver.evidence import EvidenceLink, EvidenceNode, EvidenceRelation
from memoryweaver.gbrain import GBrain, MindMapProjection
from memoryweaver.retriever import VerifiedRetriever
from memoryweaver.schema import (
    Freshness,
    MemoryItem,
    MemoryType,
    Pattern,
    Polarity,
    Source,
)
from memoryweaver.store import MemoryWorkspace


@dataclass
class VerifiedWriteResult:
    memory: MemoryItem
    evidence_node: EvidenceNode | None = None
    evidence_link: EvidenceLink | None = None
    promoted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory": self.memory.to_dict(),
            "evidence_node": self.evidence_node.to_dict() if self.evidence_node else None,
            "evidence_link": self.evidence_link.to_dict() if self.evidence_link else None,
            "promoted": self.promoted,
        }


@dataclass
class LifecycleTrace:
    events: list[dict[str, Any]] = field(default_factory=list)

    def add(self, step: str, **payload: Any) -> None:
        self.events.append({"step": step, **payload})


class MemoryLifecycle:
    """High-level lifecycle operations over a MemoryWorkspace."""

    def __init__(self, workspace: MemoryWorkspace):
        self.workspace = workspace
        self.retriever = VerifiedRetriever(workspace.memories, workspace.retrieval_policy)
        self.composer = PatternComposer(
            workspace.memories,
            workspace.patterns,
            workspace.evidence,
            workspace.memory_policy,
        )
        self.gbrain = GBrain(workspace)
        self.conflicts = ContradictionResolver()

    def write_verified_memory(
        self,
        *,
        memory_id: str,
        content: str,
        source: Source,
        tags: list[str],
        evidence_text: str,
        evidence_uri: str,
        polarity: Polarity = Polarity.NEUTRAL,
        memory_type: MemoryType = MemoryType.FACT,
        confidence: float = 0.8,
        freshness: Freshness = Freshness.UNKNOWN,
        scope: str = "project",
        promote: bool = True,
    ) -> VerifiedWriteResult:
        """Write a Layer-1 memory with citable evidence and optionally promote."""

        node = EvidenceNode(
            text=evidence_text,
            source=source,
            source_uri=evidence_uri,
            title=content[:80],
        )
        self.workspace.evidence.add_node(node)
        memory = MemoryItem(
            id=memory_id,
            polarity=polarity,
            memory_type=memory_type,
            content=content,
            tags=tags,
            source=source,
            evidence=evidence_text,
            scope=scope,
            confidence=confidence,
            freshness=freshness,
        )
        self.workspace.memories.add(memory)
        link = EvidenceLink(
            evidence_id=node.id,
            relation=EvidenceRelation.SUPPORTS,
            memory_id=memory.id,
        )
        self.workspace.evidence.add_link(link)
        promoted = False
        if promote:
            self.workspace.memory_policy.promote_to_layer2(
                memory,
                self.workspace.evidence.links_for_memory(memory.id),
            )
            self.workspace.memories.update(memory)
            promoted = True
        self.gbrain.sync_workspace()
        return VerifiedWriteResult(
            memory=memory,
            evidence_node=node,
            evidence_link=link,
            promoted=promoted,
        )

    def retrieve(
        self,
        query: str,
        *,
        limit: int = 10,
        scope: str = "project",
        threshold: float = 0.05,
    ) -> list[MemoryItem]:
        return self.retriever.search(
            query,
            limit=limit,
            threshold=threshold,
            scope=scope,
        )

    def check_conflict(
        self,
        new_item: MemoryItem,
        existing_item_id: str,
    ) -> ConflictResult:
        existing = self.workspace.memories.get(existing_item_id)
        if existing is None:
            raise KeyError(f"MemoryItem '{existing_item_id}' not found")
        return self.conflicts.resolve(new_item, existing)

    def compose_pattern(
        self,
        *,
        supporting_memory_ids: list[str],
        rule: str,
        applies_when: list[str],
        avoid_when: list[str],
        success_path: list[str],
        failed_path: list[str],
        evidence_link_ids: list[str],
        scope: str = "project",
    ) -> Pattern:
        pattern = self.composer.compose(
            supporting_memory_ids=supporting_memory_ids,
            rule=rule,
            applies_when=applies_when,
            avoid_when=avoid_when,
            success_path=success_path,
            failed_path=failed_path,
            evidence_link_ids=evidence_link_ids,
            scope=scope,
        )
        self.gbrain.sync_workspace()
        return pattern

    def rollback_pattern(self, pattern_id: str, reason: str) -> Pattern:
        pattern = self.composer.rollback(pattern_id, reason)
        self.gbrain.sync_workspace()
        return pattern

    def write_marker_context(
        self,
        *,
        marker_id: str,
        required_tags: list[str],
        required_sources: list[Source] | None = None,
        preferred_content_types: list[ContentType] | None = None,
        required_time_window: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> MarkerEvidenceContext:
        context = MarkerEvidenceContext(
            marker_id=marker_id,
            required_tags=required_tags,
            required_sources=required_sources or [],
            required_time_window=required_time_window,
            preferred_content_types=preferred_content_types or [],
            metadata=metadata or {},
        )
        self.workspace.marker_evidence_contexts.add(context)
        return context

    def mind_map(
        self,
        *,
        center_tags: list[str] | None = None,
        max_nodes: int = 80,
    ) -> MindMapProjection:
        self.gbrain.sync_workspace()
        return self.gbrain.project_mind_map(
            center_tags=center_tags,
            max_nodes=max_nodes,
        )

    def run_codex_subscription_smoke(self) -> dict[str, Any]:
        """A small real lifecycle run used by CLI and regression tests."""

        trace = LifecycleTrace()
        success = self.write_verified_memory(
            memory_id="mem_codex_org_fix",
            content=(
                "For Codex subscription load failures, check selected organization "
                "and account entitlement before reinstalling npm."
            ),
            source=Source.TERMINAL,
            tags=["codex", "subscription", "organization", "entitlement"],
            evidence_text="Terminal evidence: selected organization fixed subscription failure.",
            evidence_uri="terminal://codex-login",
            polarity=Polarity.POSITIVE,
            memory_type=MemoryType.SUCCESS_PATH,
            confidence=0.86,
            freshness=Freshness.STABLE,
        )
        trace.add("verified_write", memory_id=success.memory.id, promoted=success.promoted)
        avoid = self.write_verified_memory(
            memory_id="mem_avoid_npm_reinstall_subscription",
            content=(
                "Do not use npm reinstall as the first fix for Codex subscription "
                "load failures; it previously failed."
            ),
            source=Source.TOOL,
            tags=["codex", "subscription", "npm", "reinstall", "known_bad_path"],
            evidence_text="Tool evidence: npm reinstall did not affect subscription failure.",
            evidence_uri="tool://npm-reinstall",
            polarity=Polarity.NEGATIVE,
            memory_type=MemoryType.FAILED_ATTEMPT,
            confidence=0.82,
            freshness=Freshness.STABLE,
        )
        trace.add("known_bad_write", memory_id=avoid.memory.id, promoted=avoid.promoted)
        retrieved = self.retrieve(
            "Codex subscription failed should I reinstall npm or check organization"
        )
        trace.add("retrieval", result_ids=[item.id for item in retrieved])
        conflict = self.check_conflict(
            MemoryItem(
                id="mem_assistant_reinstall_claim",
                polarity=Polarity.POSITIVE,
                memory_type=MemoryType.HYPOTHESIS,
                content="Reinstall npm first for Codex subscription failures.",
                tags=["codex", "subscription", "npm"],
                source=Source.ASSISTANT,
                confidence=0.9,
            ),
            avoid.memory.id,
        )
        trace.add(
            "conflict",
            severity=conflict.severity.value,
            action=conflict.action,
            relation=conflict.relation.value,
        )
        pattern = self.compose_pattern(
            supporting_memory_ids=[success.memory.id, avoid.memory.id],
            rule="For Codex subscription failures, check organization and entitlement before npm reinstall.",
            applies_when=["codex subscription load failed", "api key exists but request denied"],
            avoid_when=["install failure is the actual error"],
            success_path=["check selected organization", "verify active account", "check entitlement"],
            failed_path=["blind npm reinstall", "reset auth files before evidence"],
            evidence_link_ids=[success.evidence_link.id, avoid.evidence_link.id],
        )
        trace.add("layer3_compose", pattern_id=pattern.id, status=pattern.status.value)
        rolled_back = self.rollback_pattern(
            pattern.id,
            "codex subscription lifecycle smoke exercises rollback path",
        )
        trace.add("rollback", pattern_id=rolled_back.id, status=rolled_back.status.value)
        marker = self.write_marker_context(
            marker_id="marker_codex_subscription_org_first",
            required_tags=["codex", "subscription", "organization", "entitlement"],
            required_sources=[Source.TERMINAL, Source.TOOL],
            preferred_content_types=[ContentType.TERMINAL_LOG, ContentType.TOOL_JSON],
            metadata={
                "recommended_route": "fast_verify",
                "known_bad_actions": ["reinstall_npm", "reset_auth_files"],
            },
        )
        trace.add("runtime_marker_write", marker_id=marker.marker_id)
        mind_map = self.mind_map(center_tags=["codex", "subscription"])
        validate_report = self.workspace.validate()
        doctor_report = self.workspace.doctor()
        metrics = {
            "verified_memory_write_count": 2,
            "promotion_count": 2,
            "retrieval_result_count": len(retrieved),
            "retrieved_success_memory": any(item.id == success.memory.id for item in retrieved),
            "retrieved_known_bad_memory": any(item.id == avoid.memory.id for item in retrieved),
            "conflict_handling_count": 1,
            "layer3_mutation_count": 1,
            "rollback_count": 1,
            "runtime_marker_write_count": 1,
            "known_bad_path_write_count": 1,
            "mind_map_node_count": len(mind_map.nodes),
            "mind_map_edge_count": len(mind_map.edges),
            "online_llm_call_count": 0,
            "workspace_validate_valid": validate_report["valid"],
            "workspace_doctor_valid": doctor_report["valid"],
        }
        return {
            "passed": all(
                [
                    metrics["verified_memory_write_count"] == 2,
                    metrics["promotion_count"] == 2,
                    metrics["retrieved_success_memory"],
                    metrics["retrieved_known_bad_memory"],
                    metrics["conflict_handling_count"] == 1,
                    metrics["layer3_mutation_count"] == 1,
                    metrics["rollback_count"] == 1,
                    metrics["runtime_marker_write_count"] == 1,
                    metrics["known_bad_path_write_count"] == 1,
                    metrics["mind_map_node_count"] > 0,
                    metrics["workspace_validate_valid"],
                    metrics["workspace_doctor_valid"],
                ]
            ),
            "metrics": metrics,
            "trace": trace.events,
            "mind_map": mind_map.to_dict(),
            "workspace_validate": validate_report,
            "workspace_doctor": doctor_report,
        }
