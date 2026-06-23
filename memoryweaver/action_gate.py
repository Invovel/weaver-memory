"""Structured action proposals and deterministic pre-execution validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from memoryweaver.contract import EnvironmentContract
from memoryweaver.policy import ActionPolicy
from memoryweaver.schema import Source


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ActionGateStatus(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    NEEDS_CONFIRMATION = "needs_confirmation"


@dataclass
class ActionProposal:
    """LLM-proposed structured action to be judged by the harness."""

    action_name: str
    target: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""
    working_directory: str = ""
    timeout_seconds: int = 30
    idempotency_key: str = ""
    user_confirmation: bool = False
    resource_budget: dict[str, int] = field(default_factory=dict)
    proposed_by: Source = Source.ASSISTANT
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if not isinstance(self.proposed_by, Source):
            self.proposed_by = Source(self.proposed_by)

    def normalized_arguments(self) -> dict[str, Any]:
        arguments = dict(self.arguments)
        if self.target and "target" not in arguments:
            arguments["target"] = self.target
        return arguments

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["proposed_by"] = self.proposed_by.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActionProposal":
        payload = dict(data)
        payload["proposed_by"] = Source(payload.get("proposed_by", Source.ASSISTANT.value))
        return cls(**payload)

    @classmethod
    def from_live_action(
        cls,
        action: Any,
        *,
        thread_id: str,
        step: int,
        timeout_seconds: int = 30,
        user_confirmation: bool = False,
        resource_budget: dict[str, int] | None = None,
    ) -> "ActionProposal":
        action_name = str(getattr(action, "name", getattr(action, "action_name", "")))
        target = str(getattr(action, "target", ""))
        arguments = {"target": target} if target else {}
        return cls(
            action_name=action_name,
            target=target,
            arguments=arguments,
            reasoning=str(getattr(action, "reasoning", "")),
            timeout_seconds=timeout_seconds,
            idempotency_key=f"{thread_id}:{step}:{action_name}:{target}".strip(":"),
            user_confirmation=user_confirmation,
            resource_budget=resource_budget or {},
        )


@dataclass
class ActionGateDecision:
    status: ActionGateStatus
    allowed: bool
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    risk: str = "unknown"
    tool_name: str = ""
    normalized_proposal: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data


class ActionGate:
    """Validate an ActionProposal against the environment contract."""

    def __init__(
        self,
        environment: EnvironmentContract,
        policy: ActionPolicy | None = None,
    ) -> None:
        self._environment = environment
        self._policy = policy or ActionPolicy()

    def validate(self, proposal: ActionProposal) -> ActionGateDecision:
        tool = self._environment.tool(proposal.action_name)
        normalized = proposal.to_dict()
        risk = "unknown"

        if tool is None or not tool.allowed:
            return ActionGateDecision(
                status=ActionGateStatus.BLOCK,
                allowed=False,
                reasons=[f"action '{proposal.action_name}' is not allowlisted by EnvironmentContract"],
                risk=risk,
                normalized_proposal=normalized,
            )

        arguments = proposal.normalized_arguments()
        missing = tool.validate_arguments(arguments)
        if missing:
            return ActionGateDecision(
                status=ActionGateStatus.BLOCK,
                allowed=False,
                reasons=[f"missing required argument(s): {', '.join(missing)}"],
                tool_name=tool.name,
                risk=risk,
                normalized_proposal=normalized,
            )

        risk = self._policy.classify_risk(proposal, tool)

        if proposal.timeout_seconds > tool.max_timeout_seconds:
            return ActionGateDecision(
                status=ActionGateStatus.BLOCK,
                allowed=False,
                reasons=[
                    f"timeout_seconds={proposal.timeout_seconds} exceeds tool contract limit "
                    f"{tool.max_timeout_seconds}"
                ],
                tool_name=tool.name,
                risk=risk,
                normalized_proposal=normalized,
            )

        if not self._working_directory_allowed(proposal):
            return ActionGateDecision(
                status=ActionGateStatus.BLOCK,
                allowed=False,
                reasons=[f"working_directory '{proposal.working_directory}' is not allowed"],
                tool_name=tool.name,
                risk=risk,
                normalized_proposal=normalized,
            )

        budget_violations = self._policy.budget_violations(
            proposal,
            self._environment,
            tool,
        )
        if budget_violations:
            return ActionGateDecision(
                status=ActionGateStatus.BLOCK,
                allowed=False,
                reasons=budget_violations,
                tool_name=tool.name,
                risk=risk,
                normalized_proposal=normalized,
            )

        if self._policy.confirmation_required(proposal, tool) and not proposal.user_confirmation:
            return ActionGateDecision(
                status=ActionGateStatus.NEEDS_CONFIRMATION,
                allowed=False,
                reasons=["explicit user confirmation is required for this action"],
                tool_name=tool.name,
                risk=risk,
                normalized_proposal=normalized,
            )

        if self._policy.idempotency_required(proposal, tool) and not proposal.idempotency_key:
            return ActionGateDecision(
                status=ActionGateStatus.BLOCK,
                allowed=False,
                reasons=["idempotency_key is required for this action"],
                tool_name=tool.name,
                risk=risk,
                normalized_proposal=normalized,
            )

        return ActionGateDecision(
            status=ActionGateStatus.ALLOW,
            allowed=True,
            tool_name=tool.name,
            risk=risk,
            normalized_proposal=normalized,
        )

    def _working_directory_allowed(self, proposal: ActionProposal) -> bool:
        if not proposal.working_directory:
            return True
        contract = self._environment.tool(proposal.action_name)
        if contract is None:
            return False
        allowed = contract.allowed_workdirs or self._environment.allowed_workdirs
        if not allowed:
            return True
        try:
            requested = Path(proposal.working_directory).resolve()
        except OSError:
            return False
        for path in allowed:
            try:
                allowed_path = Path(path).resolve()
                requested.relative_to(allowed_path)
                return True
            except (OSError, ValueError):
                continue
        return False
