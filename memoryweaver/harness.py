"""Lifecycle orchestration over the deterministic MemoryWeaver modules."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from memoryweaver.action_gate import ActionGate, ActionGateDecision, ActionProposal
from memoryweaver.contract import EnvironmentContract
from memoryweaver.lifecycle import MemoryLifecycle
from memoryweaver.runtime_authority import RuntimeMemoryAuthority, create_runtime_authority
from memoryweaver.schema import Freshness, MemoryType, Polarity, Source
from memoryweaver.skill import SkillRetrievalResult, SkillRetriever
from memoryweaver.store import MemoryWorkspace
from memoryweaver.trajectory import TrajectoryDecision, TrajectoryRegulator


@dataclass
class InteractionStage:
    query: str
    scope: str
    contract_id: str
    contract_version: str
    workspace_validate: dict[str, Any]
    workspace_doctor: dict[str, Any]
    source_authority: dict[str, dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConditioningStage:
    query: str
    tags: list[str]
    scope: str
    arm: str
    step: int
    skill_result: SkillRetrievalResult
    runtime_decision: dict[str, Any]
    runtime_context: str
    combined_context: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "tags": list(self.tags),
            "scope": self.scope,
            "arm": self.arm,
            "step": self.step,
            "skill_result": self.skill_result.to_dict(),
            "runtime_decision": dict(self.runtime_decision),
            "runtime_context": self.runtime_context,
            "combined_context": self.combined_context,
        }


@dataclass
class ExecutionStage:
    proposal: ActionProposal
    decision: ActionGateDecision

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal": self.proposal.to_dict(),
            "decision": self.decision.to_dict(),
        }


@dataclass
class FeedbackStage:
    trajectory: TrajectoryDecision
    history_size: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "trajectory": self.trajectory.to_dict(),
            "history_size": self.history_size,
        }


@dataclass
class OutcomeStage:
    recorded_memory_ids: list[str] = field(default_factory=list)
    verified_write_count: int = 0
    promotion_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MemoryWeaverHarness:
    """Explicit lifecycle harness over task conditioning and execution gates."""

    def __init__(
        self,
        workspace: MemoryWorkspace,
        *,
        environment_contract: EnvironmentContract | None = None,
        runtime_authority: RuntimeMemoryAuthority | None = None,
        action_gate: ActionGate | None = None,
        trajectory: TrajectoryRegulator | None = None,
        skill_retriever: SkillRetriever | None = None,
    ) -> None:
        self.workspace = workspace
        self.environment_contract = environment_contract or EnvironmentContract.default_live_loop()
        self.lifecycle = MemoryLifecycle(workspace)
        self.skill_retriever = skill_retriever or SkillRetriever(
            workspace.memories,
            workspace.patterns,
            retriever=self.lifecycle.retriever,
        )
        self.skill_retriever.set_composer(self.lifecycle.composer)
        self.runtime_authority = runtime_authority or create_runtime_authority(
            workspace.memories,
            markers=[
                {
                    "id": "marker_codex_subscription_org_first",
                    "marker_type": "guard",
                    "level": "L3_guard",
                    "trigger_tags": ["codex", "subscription"],
                    "trigger_query_patterns": ["subscription"],
                    "suppressed_actions": ["reinstall_npm", "reset_auth_files"],
                    "required_evidence": ["selected_organization", "entitlement"],
                    "recommended_route": "fast_verify",
                    "max_route": "fast_verify",
                    "status": "active",
                }
            ],
        )
        self.action_gate = action_gate or ActionGate(self.environment_contract)
        self.trajectory = trajectory or TrajectoryRegulator(
            max_steps=self.environment_contract.max_steps,
            max_tool_calls=self.environment_contract.max_tool_calls,
        )

    def before_interaction(self, query: str, *, scope: str = "project") -> InteractionStage:
        return InteractionStage(
            query=query,
            scope=scope,
            contract_id=self.environment_contract.contract_id,
            contract_version=self.environment_contract.version,
            workspace_validate=self.workspace.validate(),
            workspace_doctor=self.workspace.doctor(),
            source_authority={
                key: authority.to_dict()
                for key, authority in self.environment_contract.source_authority.items()
            },
        )

    def task_conditioning(
        self,
        query: str,
        *,
        tags: list[str] | None = None,
        scope: str = "project",
        arm: str = "mw_marker",
        step: int = 1,
    ) -> ConditioningStage:
        resolved_tags = tags or []
        skill_result = self.skill_retriever.retrieve(query, scope=scope)
        runtime_decision = self.runtime_authority.evaluate(
            query,
            resolved_tags,
            arm,
            step,
        )
        runtime_context = self.runtime_authority.build_context(runtime_decision)
        combined_context = "\n\n".join(
            part for part in [skill_result.render_context(), runtime_context] if part
        )
        return ConditioningStage(
            query=query,
            tags=resolved_tags,
            scope=scope,
            arm=arm,
            step=step,
            skill_result=skill_result,
            runtime_decision={
                "decision_id": runtime_decision.decision_id,
                "arm": runtime_decision.arm,
                "marker_activated": runtime_decision.marker_activated,
                "marker_id": runtime_decision.marker_id,
                "recommended_route": runtime_decision.recommended_route,
                "max_route": runtime_decision.max_route,
                "suppressed_actions": list(runtime_decision.suppressed_actions),
                "required_evidence": list(runtime_decision.required_evidence),
                "allowed_memory_ids": [memory.id for memory in runtime_decision.allowed_memories],
                "blocked_memory_ids": [memory.id for memory in runtime_decision.blocked_memories],
            },
            runtime_context=runtime_context,
            combined_context=combined_context,
        )

    def before_execution(
        self,
        action: Any,
        *,
        task_id: str,
        step: int,
        user_confirmation: bool = False,
        resource_budget: dict[str, int] | None = None,
    ) -> ExecutionStage:
        proposal = (
            action
            if isinstance(action, ActionProposal)
            else ActionProposal.from_live_action(
                action,
                thread_id=task_id,
                step=step,
                timeout_seconds=self.environment_contract.default_timeout_seconds,
                user_confirmation=user_confirmation,
                resource_budget=resource_budget
                or ({"tool_calls": 1} if getattr(action, "name", "") == "tool_call" else {}),
            )
        )
        return ExecutionStage(
            proposal=proposal,
            decision=self.action_gate.validate(proposal),
        )

    def after_feedback(
        self,
        *,
        step: int,
        proposal: ActionProposal,
        result: dict[str, Any],
        gate_status: str,
    ) -> FeedbackStage:
        decision = self.trajectory.observe(
            step=step,
            proposal=proposal,
            result=result,
            gate_status=gate_status,
        )
        return FeedbackStage(
            trajectory=decision,
            history_size=len(self.trajectory.history),
        )

    def after_task_outcome(
        self,
        *,
        task_id: str,
        step: int,
        action: Any,
        result: dict[str, Any],
    ) -> OutcomeStage:
        status = str(result.get("status", ""))
        signal = str(result.get("signal", "neutral"))
        if status not in {"failed_known_bad", "evidence_observed"}:
            return OutcomeStage()
        target = str(getattr(action, "target", ""))
        negative = status == "failed_known_bad" or signal == "negative"
        memory_id = f"mem_{task_id}_{step}_{status}"
        write = self.lifecycle.write_verified_memory(
            memory_id=memory_id,
            content=str(result.get("evidence", target)),
            source=Source.TOOL,
            tags=["codex", "subscription", target, status],
            evidence_text=str(result.get("evidence", "")),
            evidence_uri=f"harness://{task_id}/{step}",
            polarity=Polarity.NEGATIVE if negative else Polarity.POSITIVE,
            memory_type=MemoryType.FAILED_ATTEMPT if negative else MemoryType.SUCCESS_PATH,
            confidence=0.82,
            freshness=Freshness.STABLE,
            promote=True,
        )
        return OutcomeStage(
            recorded_memory_ids=[write.memory.id],
            verified_write_count=1,
            promotion_count=1 if write.promoted else 0,
        )
