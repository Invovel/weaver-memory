"""Durable runtime primitives for gated tool execution.

The objects here are deliberately small. `ToolGateway` does not know how to run
shell commands by itself; callers must register explicit handlers. This keeps
the runtime path from silently gaining side effects while still producing hard
tool-result evidence for `HarnessRuntime`.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from memoryweaver.action_gate import (
    ActionGate,
    ActionGateDecision,
    ActionGateStatus,
    ActionProposal,
)
from memoryweaver.runtime.harness_runtime import HardEvidence, HardEvidenceType
from memoryweaver.store import SCHEMA_VERSION, atomic_write_json


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RuntimeEvent:
    event_id: str
    event_type: str
    thread_id: str = ""
    step: int = 0
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RuntimeEvent":
        return cls(**dict(data))


class EventJournal:
    """Append-only JSONL runtime journal."""

    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._events: list[RuntimeEvent] = []
        self._load()

    def append(
        self,
        event_type: str,
        *,
        thread_id: str = "",
        step: int = 0,
        payload: dict[str, Any] | None = None,
    ) -> RuntimeEvent:
        event = RuntimeEvent(
            event_id=f"evt_{len(self._events) + 1:08d}",
            event_type=event_type,
            thread_id=thread_id,
            step=step,
            payload=payload or {},
        )
        self._events.append(event)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        return event

    def list_events(self) -> list[RuntimeEvent]:
        return list(self._events)

    def events_for_thread(self, thread_id: str) -> list[RuntimeEvent]:
        return [event for event in self._events if event.thread_id == thread_id]

    def _load(self) -> None:
        if not self._path.exists():
            return
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                self._events.append(RuntimeEvent.from_dict(json.loads(line)))
            except json.JSONDecodeError:
                continue


@dataclass
class RuntimeCheckpoint:
    checkpoint_id: str
    thread_id: str
    step: int
    state: dict[str, Any] = field(default_factory=dict)
    last_event_id: str = ""
    created_at: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RuntimeCheckpoint":
        return cls(**dict(data))


class CheckpointStore:
    """JSON-backed checkpoint store keyed by thread id."""

    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._checkpoints: dict[str, list[RuntimeCheckpoint]] = {}
        self._load()

    def save(self, checkpoint: RuntimeCheckpoint) -> None:
        self._checkpoints.setdefault(checkpoint.thread_id, []).append(checkpoint)
        self._save()

    def latest(self, thread_id: str) -> RuntimeCheckpoint | None:
        items = self._checkpoints.get(thread_id, [])
        if not items:
            return None
        return items[-1]

    def list_for_thread(self, thread_id: str) -> list[RuntimeCheckpoint]:
        return list(self._checkpoints.get(thread_id, []))

    def _save(self) -> None:
        atomic_write_json(
            self._path,
            {
                "version": SCHEMA_VERSION,
                "checkpoints": {
                    thread_id: [item.to_dict() for item in items]
                    for thread_id, items in self._checkpoints.items()
                },
            },
        )

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            text = self._path.read_text(encoding="utf-8").strip()
            data = json.loads(text) if text else {}
        except (json.JSONDecodeError, FileNotFoundError):
            return
        checkpoints = data.get("checkpoints", {})
        if not isinstance(checkpoints, dict):
            return
        for thread_id, items in checkpoints.items():
            self._checkpoints[str(thread_id)] = [
                RuntimeCheckpoint.from_dict(item)
                for item in items
            ]


@dataclass
class ToolExecutionResult:
    proposal: ActionProposal
    gate_decision: ActionGateDecision
    executed: bool
    status: str
    signal: str = "neutral"
    evidence: str = ""
    output: dict[str, Any] = field(default_factory=dict)
    event_id: str = ""
    duplicate: bool = False
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal": self.proposal.to_dict(),
            "gate_decision": self.gate_decision.to_dict(),
            "executed": self.executed,
            "status": self.status,
            "signal": self.signal,
            "evidence": self.evidence,
            "output": dict(self.output),
            "event_id": self.event_id,
            "duplicate": self.duplicate,
            "error": self.error,
        }

    def to_hard_evidence(
        self,
        *,
        task_id: str = "",
        task_family: str = "",
    ) -> HardEvidence:
        known_bad_avoided = bool(self.output.get("known_bad_avoided", False))
        evidence_first = bool(self.output.get("evidence_first", False))
        false_trigger = bool(
            self.output.get(
                "false_trigger",
                self.status in {"failed_known_bad", "invalid_action"},
            )
        )
        return HardEvidence(
            evidence_type=HardEvidenceType.TOOL_RESULT,
            task_id=task_id,
            task_family=task_family,
            passed=self.status in {"passed", "evidence_observed", "ok"},
            source_ref=self.event_id,
            status=self.status,
            target=self.proposal.target,
            observed=self.evidence,
            known_bad_avoided=known_bad_avoided,
            evidence_first=evidence_first,
            false_trigger=false_trigger,
            metadata={
                "signal": self.signal,
                "executed": self.executed,
                "duplicate": self.duplicate,
            },
        )


ToolHandler = Callable[[ActionProposal], dict[str, Any]]


class ToolGateway:
    """Gate, execute registered handlers, journal results, and checkpoint state."""

    def __init__(
        self,
        action_gate: ActionGate,
        *,
        journal: EventJournal | None = None,
        checkpoints: CheckpointStore | None = None,
    ) -> None:
        self.action_gate = action_gate
        self.journal = journal
        self.checkpoints = checkpoints
        self._handlers: dict[str, ToolHandler] = {}
        self._executed_idempotency_keys = self._load_executed_idempotency_keys()

    def register(self, action_name: str, handler: ToolHandler) -> None:
        self._handlers[action_name] = handler

    def _load_executed_idempotency_keys(self) -> set[str]:
        if self.journal is None:
            return set()
        keys: set[str] = set()
        for event in self.journal.list_events():
            if event.event_type != "tool_result":
                continue
            payload = event.payload
            if not payload.get("executed"):
                continue
            proposal = payload.get("proposal", {})
            if not isinstance(proposal, dict):
                continue
            key = proposal.get("idempotency_key")
            if key:
                keys.add(str(key))
        return keys

    def execute(
        self,
        proposal: ActionProposal,
        *,
        thread_id: str,
        step: int,
    ) -> ToolExecutionResult:
        gate = self.action_gate.validate(proposal)
        if not gate.allowed:
            result = ToolExecutionResult(
                proposal=proposal,
                gate_decision=gate,
                executed=False,
                status="blocked_by_action_gate",
                signal="negative",
                evidence="; ".join(gate.reasons),
            )
            return self._record_result(result, thread_id=thread_id, step=step)

        if proposal.idempotency_key and proposal.idempotency_key in self._executed_idempotency_keys:
            result = ToolExecutionResult(
                proposal=proposal,
                gate_decision=gate,
                executed=False,
                status="duplicate_suppressed",
                signal="neutral",
                evidence=f"idempotency_key already executed: {proposal.idempotency_key}",
                duplicate=True,
            )
            return self._record_result(result, thread_id=thread_id, step=step)

        handler = self._handlers.get(proposal.action_name)
        if handler is None:
            result = ToolExecutionResult(
                proposal=proposal,
                gate_decision=gate,
                executed=False,
                status="missing_handler",
                signal="negative",
                evidence=f"no handler registered for {proposal.action_name}",
            )
            return self._record_result(result, thread_id=thread_id, step=step)

        try:
            output = handler(proposal)
            status = str(output.get("status", "ok"))
            signal = str(output.get("signal", "neutral"))
            evidence = str(output.get("evidence", ""))
            result = ToolExecutionResult(
                proposal=proposal,
                gate_decision=gate,
                executed=True,
                status=status,
                signal=signal,
                evidence=evidence,
                output=dict(output),
            )
            if proposal.idempotency_key:
                self._executed_idempotency_keys.add(proposal.idempotency_key)
            return self._record_result(result, thread_id=thread_id, step=step)
        except Exception as exc:
            result = ToolExecutionResult(
                proposal=proposal,
                gate_decision=gate,
                executed=False,
                status="handler_error",
                signal="negative",
                evidence=str(exc),
                error=str(exc),
            )
            return self._record_result(result, thread_id=thread_id, step=step)

    def _record_result(
        self,
        result: ToolExecutionResult,
        *,
        thread_id: str,
        step: int,
    ) -> ToolExecutionResult:
        event_id = ""
        if self.journal is not None:
            event = self.journal.append(
                "tool_result",
                thread_id=thread_id,
                step=step,
                payload=result.to_dict(),
            )
            event_id = event.event_id
            result.event_id = event_id
        if self.checkpoints is not None:
            self.checkpoints.save(
                RuntimeCheckpoint(
                    checkpoint_id=f"ckpt_{thread_id}_{step:04d}",
                    thread_id=thread_id,
                    step=step,
                    state={
                        "last_tool_status": result.status,
                        "last_tool_target": result.proposal.target,
                        "duplicate": result.duplicate,
                    },
                    last_event_id=event_id,
                )
            )
        return result
