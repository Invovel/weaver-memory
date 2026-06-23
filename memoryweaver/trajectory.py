"""Deterministic trajectory regulation for repetition, stagnation, and budget."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from memoryweaver.action_gate import ActionProposal


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TrajectoryStatus(str, Enum):
    CONTINUE = "continue"
    RECOVER = "recover"
    HALT = "halt"


@dataclass
class TrajectoryRecord:
    step: int
    action_name: str
    target: str
    result_status: str
    signal: str
    gate_status: str
    timestamp: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TrajectoryDecision:
    status: TrajectoryStatus
    reasons: list[str] = field(default_factory=list)
    repeated_failure: bool = False
    stagnating: bool = False
    over_budget: bool = False
    recovery_action: str = ""
    recovery_target: str = ""
    checkpoint_recommended: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data


class TrajectoryRegulator:
    """Observe agent steps and decide whether to continue, recover, or halt."""

    def __init__(
        self,
        *,
        max_steps: int = 8,
        max_tool_calls: int = 4,
        repeated_failure_limit: int = 2,
        stagnation_window: int = 2,
    ) -> None:
        self.max_steps = max_steps
        self.max_tool_calls = max_tool_calls
        self.repeated_failure_limit = repeated_failure_limit
        self.stagnation_window = stagnation_window
        self.history: list[TrajectoryRecord] = []

    def observe(
        self,
        *,
        step: int,
        proposal: ActionProposal,
        result: dict[str, Any],
        gate_status: str,
    ) -> TrajectoryDecision:
        record = TrajectoryRecord(
            step=step,
            action_name=proposal.action_name,
            target=proposal.target,
            result_status=str(result.get("status", "")),
            signal=str(result.get("signal", "")),
            gate_status=gate_status,
        )
        self.history.append(record)
        return self.evaluate()

    def evaluate(self) -> TrajectoryDecision:
        if not self.history:
            return TrajectoryDecision(status=TrajectoryStatus.CONTINUE)

        last = self.history[-1]
        if len(self.history) >= self.max_steps:
            return TrajectoryDecision(
                status=TrajectoryStatus.HALT,
                reasons=[f"step budget exhausted at {len(self.history)}/{self.max_steps}"],
                over_budget=True,
                checkpoint_recommended=True,
            )

        tool_call_count = sum(
            1 for record in self.history if record.action_name == "tool_call"
        )
        if tool_call_count > self.max_tool_calls:
            return TrajectoryDecision(
                status=TrajectoryStatus.HALT,
                reasons=[
                    f"tool call budget exhausted at {tool_call_count}/{self.max_tool_calls}"
                ],
                over_budget=True,
                checkpoint_recommended=True,
            )

        if last.result_status == "blocked_by_action_gate":
            return TrajectoryDecision(
                status=TrajectoryStatus.RECOVER,
                reasons=["last action was blocked by ActionGate"],
                stagnating=True,
                recovery_action="ask_user",
                recovery_target="confirmation_or_safe_alternative",
                checkpoint_recommended=True,
            )

        if self._repeated_known_bad_failure():
            return TrajectoryDecision(
                status=TrajectoryStatus.RECOVER,
                reasons=["repeated known-bad failure detected"],
                repeated_failure=True,
                recovery_action="check_evidence",
                recovery_target="required_evidence",
                checkpoint_recommended=True,
            )

        if self._stagnating():
            return TrajectoryDecision(
                status=TrajectoryStatus.RECOVER,
                reasons=["trajectory is stagnating without new useful signal"],
                stagnating=True,
                recovery_action="ask_user",
                recovery_target="clarify_or_compact_context",
                checkpoint_recommended=True,
            )

        return TrajectoryDecision(status=TrajectoryStatus.CONTINUE)

    def _repeated_known_bad_failure(self) -> bool:
        if len(self.history) < self.repeated_failure_limit:
            return False
        recent = self.history[-self.repeated_failure_limit :]
        first = recent[0]
        return all(
            record.result_status == "failed_known_bad"
            and record.target == first.target
            for record in recent
        )

    def _stagnating(self) -> bool:
        if len(self.history) < self.stagnation_window:
            return False
        recent = self.history[-self.stagnation_window :]
        return all(
            record.result_status in {
                "no_signal",
                "needs_confirmation",
                "blocked_by_action_gate",
            }
            for record in recent
        )
