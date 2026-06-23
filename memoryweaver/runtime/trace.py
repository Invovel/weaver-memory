"""Runtime trace primitives for trace-to-path evolution."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from memoryweaver.action_gate import ActionProposal
from memoryweaver.runtime.harness_runtime import (
    HardEvidence,
    HardEvidenceType,
    RuntimePathCondition,
    RuntimePathRollbackRule,
    RuntimePathSpec,
    RuntimePathValidationGate,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_metrics() -> dict[str, Any]:
    return {
        "step_count": 0,
        "tool_action_count": 0,
        "tool_result_count": 0,
        "successful_tool_result_count": 0,
        "failed_tool_result_count": 0,
        "duplicate_tool_result_count": 0,
        "error_step_count": 0,
        "event_linked_step_count": 0,
        "total_latency_ms": 0,
        "total_token_cost": 0,
        "action_type_counts": {},
        "status_counts": {},
    }


def _status_is_failure(status: str, error: str) -> bool:
    if error:
        return True
    return status in {
        "blocked_by_action_gate",
        "duplicate_suppressed",
        "failed",
        "failed_known_bad",
        "handler_error",
        "invalid_action",
        "missing_handler",
    }


def _slug(value: str, *, fallback: str) -> str:
    chars: list[str] = []
    for char in value.lower():
        if char.isalnum():
            chars.append(char)
        elif chars and chars[-1] != "_":
            chars.append("_")
    slug = "".join(chars).strip("_")
    return slug or fallback


def _coerce_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.replace(",", " ").split() if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _metric_value(trace: "RuntimeTrace", *keys: str, default: Any = None) -> Any:
    for source in (trace.metrics, trace.final_result, trace.initial_context):
        for key in keys:
            if key in source:
                return source[key]
    return default


def _as_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y", "passed", "pass", "ok"}:
            return True
        if lowered in {"0", "false", "no", "n", "failed", "fail"}:
            return False
    return bool(value)


def _as_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _target_from_step(step: "RuntimeTraceStep") -> str:
    return str(
        step.metadata.get("target")
        or step.tool_args.get("target")
        or step.tool_args.get("path")
        or step.tool_args.get("file")
        or step.tool_name
        or step.action_type
    )


def _observation_dict(step: "RuntimeTraceStep") -> dict[str, Any]:
    return dict(step.observation) if isinstance(step.observation, dict) else {}


def _is_invalid_target(target: str) -> bool:
    normalized = target.strip().lower()
    return normalized in {"__invalid_action__", "invalid_action", "invalid action"}


@dataclass
class RuntimeTraceStep:
    step_id: str
    node_name: str
    action_type: str
    tool_name: str = ""
    tool_args: dict[str, Any] = field(default_factory=dict)
    observation: Any = None
    status: str = ""
    thought_summary: str = ""
    error: str = ""
    latency_ms: int | None = None
    token_cost: int | None = None
    event_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RuntimeTraceStep":
        return cls(**dict(data))


@dataclass
class RuntimeTrace:
    trace_id: str
    task_id: str
    task_type: str = ""
    user_goal: str = ""
    initial_context: dict[str, Any] = field(default_factory=dict)
    steps: list[RuntimeTraceStep] = field(default_factory=list)
    final_result: dict[str, Any] = field(default_factory=dict)
    success: bool = False
    metrics: dict[str, Any] = field(default_factory=dict)
    thread_id: str = ""
    created_at: str = field(default_factory=_utc_now)
    finished_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["steps"] = [step.to_dict() for step in self.steps]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RuntimeTrace":
        payload = dict(data)
        payload["steps"] = [
            RuntimeTraceStep.from_dict(item)
            for item in payload.get("steps", [])
        ]
        return cls(**payload)


@dataclass
class TracePathCandidate:
    """Trace-derived candidate path plus the evidence used to assess it.

    `evidence` is the promotion/challenge evidence for the candidate path.
    `rejected_evidence` records observed bad actions that should be avoided but
    should not become positive support for the reusable path.
    """

    candidate_id: str
    trace_id: str
    path: RuntimePathSpec
    evidence: list[HardEvidence] = field(default_factory=list)
    rejected_evidence: list[HardEvidence] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "trace_id": self.trace_id,
            "path": self.path.to_dict(),
            "evidence": [item.to_dict() for item in self.evidence],
            "rejected_evidence": [item.to_dict() for item in self.rejected_evidence],
            "metrics": dict(self.metrics),
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TracePathCandidate":
        payload = dict(data)
        payload["path"] = RuntimePathSpec.from_dict(payload["path"])
        payload["evidence"] = [
            HardEvidence.from_dict(item)
            for item in payload.get("evidence", [])
        ]
        payload["rejected_evidence"] = [
            HardEvidence.from_dict(item)
            for item in payload.get("rejected_evidence", [])
        ]
        payload["metrics"] = dict(payload.get("metrics", {}))
        payload["notes"] = list(payload.get("notes", []))
        return cls(**payload)


class RuntimeTraceStore:
    """Append-only JSONL store for runtime traces."""

    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._traces: list[RuntimeTrace] = []
        self._load()

    def append(self, trace: RuntimeTrace) -> None:
        self._traces.append(trace)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(trace.to_dict(), ensure_ascii=False) + "\n")

    def list_traces(self) -> list[RuntimeTrace]:
        return list(self._traces)

    def traces_for_task(self, task_id: str) -> list[RuntimeTrace]:
        return [trace for trace in self._traces if trace.task_id == task_id]

    def latest(self, task_id: str) -> RuntimeTrace | None:
        matches = self.traces_for_task(task_id)
        if not matches:
            return None
        return matches[-1]

    def _load(self) -> None:
        if not self._path.exists():
            return
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                self._traces.append(RuntimeTrace.from_dict(json.loads(line)))
            except json.JSONDecodeError:
                continue


class RuntimeTraceRecorder:
    """Collect runtime steps and optionally persist completed traces."""

    def __init__(
        self,
        *,
        trace_id: str,
        task_id: str,
        task_type: str = "",
        user_goal: str = "",
        initial_context: dict[str, Any] | None = None,
        thread_id: str = "",
        store: RuntimeTraceStore | None = None,
    ) -> None:
        self._trace = RuntimeTrace(
            trace_id=trace_id,
            task_id=task_id,
            task_type=task_type,
            user_goal=user_goal,
            initial_context=dict(initial_context or {}),
            metrics=_default_metrics(),
            thread_id=thread_id,
        )
        self._store = store

    def record_step(
        self,
        *,
        node_name: str,
        action_type: str,
        tool_name: str = "",
        tool_args: dict[str, Any] | None = None,
        observation: Any = None,
        status: str = "",
        thought_summary: str = "",
        error: str = "",
        latency_ms: int | None = None,
        token_cost: int | None = None,
        event_id: str = "",
        metadata: dict[str, Any] | None = None,
        from_tool_result: bool = False,
    ) -> RuntimeTraceStep:
        step = RuntimeTraceStep(
            step_id=f"step_{len(self._trace.steps) + 1:04d}",
            node_name=node_name,
            action_type=action_type,
            tool_name=tool_name,
            tool_args=dict(tool_args or {}),
            observation=observation,
            status=status,
            thought_summary=thought_summary,
            error=error,
            latency_ms=latency_ms,
            token_cost=token_cost,
            event_id=event_id,
            metadata=dict(metadata or {}),
        )
        self._trace.steps.append(step)
        self._sync_metrics(step, from_tool_result=from_tool_result)
        return step

    def record_tool_result(
        self,
        *,
        node_name: str,
        result: Any,
        thought_summary: str = "",
        latency_ms: int | None = None,
        token_cost: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RuntimeTraceStep:
        observation = {
            "evidence": getattr(result, "evidence", ""),
            "output": dict(getattr(result, "output", {})),
            "duplicate": bool(getattr(result, "duplicate", False)),
        }
        error = str(getattr(result, "error", ""))
        if error:
            observation["error"] = error
        proposal = getattr(result, "proposal")
        merged_metadata = dict(metadata or {})
        if getattr(result, "event_id", ""):
            merged_metadata["event_id"] = getattr(result, "event_id")
        if getattr(proposal, "target", ""):
            merged_metadata["target"] = getattr(proposal, "target")
        return self.record_step(
            node_name=node_name,
            action_type=getattr(proposal, "action_name", ""),
            tool_name=getattr(proposal, "action_name", ""),
            tool_args=dict(getattr(proposal, "arguments", {})),
            observation=observation,
            status=str(getattr(result, "status", "")),
            thought_summary=thought_summary,
            error=error,
            latency_ms=latency_ms,
            token_cost=token_cost,
            event_id=str(getattr(result, "event_id", "")),
            metadata=merged_metadata,
            from_tool_result=True,
        )

    def _sync_metrics(
        self,
        step: RuntimeTraceStep,
        *,
        from_tool_result: bool,
    ) -> None:
        metrics = self._trace.metrics
        metrics["step_count"] += 1
        if step.tool_name:
            metrics["tool_action_count"] += 1
        if step.event_id:
            metrics["event_linked_step_count"] += 1
        if step.latency_ms is not None:
            metrics["total_latency_ms"] += step.latency_ms
        if step.token_cost is not None:
            metrics["total_token_cost"] += step.token_cost
        if step.error:
            metrics["error_step_count"] += 1

        action_counts = dict(metrics.get("action_type_counts", {}))
        action_counts[step.action_type] = action_counts.get(step.action_type, 0) + 1
        metrics["action_type_counts"] = action_counts

        status_counts = dict(metrics.get("status_counts", {}))
        if step.status:
            status_counts[step.status] = status_counts.get(step.status, 0) + 1
        metrics["status_counts"] = status_counts

        if from_tool_result:
            metrics["tool_result_count"] += 1
            if getattr(step.observation, "get", None) and step.observation.get("duplicate"):
                metrics["duplicate_tool_result_count"] += 1
            if _status_is_failure(step.status, step.error):
                metrics["failed_tool_result_count"] += 1
            else:
                metrics["successful_tool_result_count"] += 1

    def finish(
        self,
        *,
        final_result: dict[str, Any] | None = None,
        success: bool = False,
        metrics: dict[str, Any] | None = None,
    ) -> RuntimeTrace:
        self._trace.final_result = dict(final_result or {})
        self._trace.success = success
        merged_metrics = dict(self._trace.metrics)
        merged_metrics.update(metrics or {})
        self._trace.metrics = merged_metrics
        self._trace.finished_at = _utc_now()
        if self._store is not None:
            self._store.append(self._trace)
        return self._trace

    @property
    def trace(self) -> RuntimeTrace:
        return RuntimeTrace.from_dict(self._trace.to_dict())


def extract_candidate_path_from_trace(
    trace: RuntimeTrace,
    *,
    path_id: str = "",
    name: str = "",
    fallback: ActionProposal | None = None,
    validation_gate: RuntimePathValidationGate | None = None,
    rollback_rule: RuntimePathRollbackRule | None = None,
    blocked_targets: list[str] | None = None,
) -> TracePathCandidate:
    """Convert a runtime trace into a Layer-3 path candidate.

    The candidate is still untrusted. Promotion remains the job of
    `HarnessRuntime.assess` / `record_trial`, using the emitted hard evidence.
    """

    failure_modes = _infer_failure_modes(trace)
    task_tags = _infer_task_tags(trace)
    query_terms = failure_modes or task_tags[:2]
    policy, rejected, inferred_blocked = _extract_action_policy(trace)
    evidence = _extract_hard_evidence(trace, rejected_evidence=rejected)
    all_blocked = sorted({*inferred_blocked, *(blocked_targets or [])})

    path_slug = _slug(
        " ".join([trace.task_type, *failure_modes, trace.task_id]),
        fallback="runtime_trace_path",
    )
    candidate_path_id = path_id or f"path_{path_slug}"
    candidate_id = f"candidate_{_slug(trace.trace_id or trace.task_id, fallback=path_slug)}"
    fallback_action = fallback or ActionProposal(
        action_name="ask_user",
        target=f"confirm_{path_slug}_fallback",
        arguments={"target": f"confirm_{path_slug}_fallback"},
    )
    gate = validation_gate or _validation_gate_from_evidence(evidence, trace)
    rollback = rollback_rule or RuntimePathRollbackRule(
        rollback_on_conflict=True,
        rollback_on_counterexamples=1,
        rollback_on_regression_rate=0.0,
        rollback_reason="trace-derived runtime path challenged by external evidence",
    )

    path = RuntimePathSpec(
        path_id=candidate_path_id,
        name=name or f"Trace-derived path for {trace.task_type or trace.task_id}",
        condition=RuntimePathCondition(
            task_tags=task_tags,
            query_terms=query_terms,
            failure_modes=failure_modes,
        ),
        action_policy=policy,
        validation_gate=gate,
        fallback=fallback_action,
        rollback_rule=rollback,
        blocked_targets=all_blocked,
        metadata={
            "source_trace_id": trace.trace_id,
            "source_task_id": trace.task_id,
            "source_task_type": trace.task_type,
            "trace_success": trace.success,
            "rejected_evidence_count": len(rejected),
        },
    )

    notes: list[str] = []
    if not policy:
        notes.append("no reusable successful tool action found")
    if rejected:
        notes.append("bad actions were retained as rejected evidence and blocked targets")

    return TracePathCandidate(
        candidate_id=candidate_id,
        trace_id=trace.trace_id,
        path=path,
        evidence=evidence,
        rejected_evidence=rejected,
        metrics=dict(trace.metrics),
        notes=notes,
    )


def trace_to_candidate_path(
    trace: RuntimeTrace,
    **kwargs: Any,
) -> TracePathCandidate:
    """Compatibility alias for the trace-to-path direction in the docs."""

    return extract_candidate_path_from_trace(trace, **kwargs)


def _infer_task_tags(trace: RuntimeTrace) -> list[str]:
    tags = (
        _coerce_list(trace.initial_context.get("tags"))
        or _coerce_list(trace.initial_context.get("task_tags"))
        or _coerce_list(trace.initial_context.get("family"))
        or _coerce_list(trace.task_type.replace("_", " "))
    )
    seen: set[str] = set()
    unique: list[str] = []
    for tag in tags:
        lowered = tag.lower()
        if lowered not in seen:
            seen.add(lowered)
            unique.append(lowered)
    return unique


def _infer_failure_modes(trace: RuntimeTrace) -> list[str]:
    modes = set(_coerce_list(trace.initial_context.get("failure_mode")))
    modes.update(_coerce_list(trace.final_result.get("failure_mode")))
    status_counts = trace.metrics.get("status_counts", {})
    if isinstance(status_counts, dict) and status_counts.get("invalid_action"):
        modes.add("invalid_action")
    if _as_bool(_metric_value(trace, "invalid_action", "invalid_action_seen"), default=False):
        modes.add("invalid_action")
    for step in trace.steps:
        target = _target_from_step(step)
        if step.status == "invalid_action" or _is_invalid_target(target):
            modes.add("invalid_action")
    return sorted(_slug(mode, fallback="failure") for mode in modes if mode)


def _extract_action_policy(
    trace: RuntimeTrace,
) -> tuple[list[ActionProposal], list[HardEvidence], list[str]]:
    policy: list[ActionProposal] = []
    rejected_evidence: list[HardEvidence] = []
    blocked_targets: set[str] = set()
    seen_actions: set[tuple[str, str]] = set()

    for step in trace.steps:
        if not step.tool_name:
            continue
        target = _target_from_step(step)
        failed = _status_is_failure(step.status, step.error)
        invalid_target = _is_invalid_target(target)
        if failed or invalid_target:
            rejected_evidence.append(_tool_step_to_hard_evidence(step, passed=False))
            if target:
                blocked_targets.add(target)
            continue
        action_name = step.tool_name or step.action_type
        key = (action_name, target)
        if key in seen_actions:
            continue
        seen_actions.add(key)
        policy.append(
            ActionProposal(
                action_name=action_name,
                target=target,
                arguments=dict(step.tool_args),
                metadata={
                    "source_trace_id": trace.trace_id,
                    "source_step_id": step.step_id,
                    "source_node": step.node_name,
                },
            )
        )
    return policy, rejected_evidence, sorted(blocked_targets)


def _extract_hard_evidence(
    trace: RuntimeTrace,
    *,
    rejected_evidence: list[HardEvidence],
) -> list[HardEvidence]:
    evidence: list[HardEvidence] = []
    rejected_refs = {
        item.source_ref
        for item in rejected_evidence
        if item.source_ref
    }
    for step in trace.steps:
        if not step.tool_name:
            continue
        if step.event_id and step.event_id in rejected_refs:
            continue
        if _status_is_failure(step.status, step.error) or _is_invalid_target(_target_from_step(step)):
            continue
        evidence.append(_tool_step_to_hard_evidence(step, passed=True, trace=trace))

    test_passed = _metric_value(trace, "tests_passed", "test_passed", "pytest_passed")
    if test_passed is not None:
        evidence.append(
            HardEvidence(
                evidence_type=HardEvidenceType.TEST_RESULT,
                task_id=trace.task_id,
                task_family=trace.task_type,
                passed=_as_bool(test_passed),
                status="passed" if _as_bool(test_passed) else "failed",
                target=str(_metric_value(trace, "test_target", default="test_suite")),
                observed=str(_metric_value(trace, "test_output", default="")),
            )
        )

    diff_valid = _metric_value(
        trace,
        "file_diff_matches_expected",
        "diff_matches_expected",
        "file_diff_valid",
        "diff_valid",
    )
    if diff_valid is not None:
        evidence.append(
            HardEvidence(
                evidence_type=HardEvidenceType.FILE_DIFF,
                task_id=trace.task_id,
                task_family=trace.task_type,
                passed=_as_bool(diff_valid),
                target=str(_metric_value(trace, "diff_target", default="file_diff")),
                expected=str(_metric_value(trace, "diff_expected", default="")),
                observed=str(_metric_value(trace, "diff_observed", default="")),
            )
        )

    score_before = _metric_value(trace, "score_before", "benchmark_score_before")
    score_after = _metric_value(trace, "score_after", "benchmark_score_after")
    if score_before is not None and score_after is not None:
        before = _as_float(score_before)
        after = _as_float(score_after)
        evidence.append(
            HardEvidence(
                evidence_type=HardEvidenceType.BENCHMARK_SCORE,
                task_id=trace.task_id,
                task_family=trace.task_type,
                passed=after >= before,
                target=str(_metric_value(trace, "benchmark_name", default="benchmark")),
                score_before=before,
                score_after=after,
                regression_rate=_as_float(
                    _metric_value(
                        trace,
                        "memory_induced_regression_rate",
                        "regression_rate",
                    ),
                    default=0.0,
                ),
            )
        )

    repeated = _as_int(
        _metric_value(trace, "repeat_validation_count", "repeated_validation_count"),
        default=0,
    )
    if repeated > 0:
        evidence.append(
            HardEvidence(
                evidence_type=HardEvidenceType.REPEAT_VALIDATION,
                task_id=trace.task_id,
                task_family=trace.task_type,
                passed=True,
                count=repeated,
                target=str(_metric_value(trace, "repeat_validation_target", default="runtime_path")),
                known_bad_avoided=_as_bool(
                    _metric_value(trace, "known_bad_avoided", "known_bad_avoidance"),
                    default=False,
                ),
                evidence_first=_as_bool(
                    _metric_value(trace, "evidence_first"),
                    default=False,
                ),
            )
        )

    user_correction = _metric_value(trace, "user_correction_applied", "explicit_user_correction")
    if user_correction is not None:
        evidence.append(
            HardEvidence(
                evidence_type=HardEvidenceType.USER_CORRECTION,
                task_id=trace.task_id,
                task_family=trace.task_type,
                passed=_as_bool(user_correction),
                observed=str(_metric_value(trace, "user_correction", default="")),
            )
        )

    counterexamples = _as_int(
        _metric_value(trace, "counterexample_count", "counterexamples"),
        default=0,
    )
    if counterexamples > 0:
        evidence.append(
            HardEvidence(
                evidence_type=HardEvidenceType.COUNTEREXAMPLE,
                task_id=trace.task_id,
                task_family=trace.task_type,
                passed=False,
                count=counterexamples,
                target=str(_metric_value(trace, "counterexample_target", default="runtime_path")),
                observed=str(_metric_value(trace, "counterexample_observed", default="")),
            )
        )

    conflicts = _as_int(_metric_value(trace, "conflict_count", "conflicts"), default=0)
    conflict_ref = str(_metric_value(trace, "conflict_ref", default=""))
    if conflicts > 0 or conflict_ref:
        evidence.append(
            HardEvidence(
                evidence_type=HardEvidenceType.CONFLICT,
                task_id=trace.task_id,
                task_family=trace.task_type,
                passed=False,
                count=max(conflicts, 1),
                conflict_ref=conflict_ref,
                observed=str(_metric_value(trace, "conflict_observed", default="")),
            )
        )

    decay_weight = _metric_value(trace, "time_decay_weight", "decay_weight")
    if decay_weight is not None:
        evidence.append(
            HardEvidence(
                evidence_type=HardEvidenceType.TIME_DECAY,
                task_id=trace.task_id,
                task_family=trace.task_type,
                passed=True,
                observed=str(decay_weight),
                metadata={"decay_weight": _as_float(decay_weight)},
            )
        )

    rollback_count = _as_int(
        _metric_value(trace, "rollback_count", "rollback_frequency"),
        default=0,
    )
    rollback_ref = str(_metric_value(trace, "rollback_ref", default=""))
    if rollback_count > 0 or rollback_ref:
        evidence.append(
            HardEvidence(
                evidence_type=HardEvidenceType.ROLLBACK_RECORD,
                task_id=trace.task_id,
                task_family=trace.task_type,
                passed=False,
                count=max(rollback_count, 1),
                rollback_ref=rollback_ref,
                regression_rate=_as_float(
                    _metric_value(
                        trace,
                        "memory_induced_regression_rate",
                        "regression_rate",
                    ),
                    default=0.0,
                ),
            )
        )

    return evidence


def _tool_step_to_hard_evidence(
    step: RuntimeTraceStep,
    *,
    passed: bool,
    trace: RuntimeTrace | None = None,
) -> HardEvidence:
    observation = _observation_dict(step)
    output = dict(observation.get("output", {})) if isinstance(observation.get("output"), dict) else {}
    duplicate = _as_bool(observation.get("duplicate"), default=False)
    return HardEvidence(
        evidence_type=HardEvidenceType.TOOL_RESULT,
        task_id=trace.task_id if trace else "",
        task_family=trace.task_type if trace else "",
        passed=passed and not duplicate,
        source_ref=step.event_id,
        status=step.status,
        target=_target_from_step(step),
        observed=str(observation.get("evidence") or observation.get("error") or step.error or ""),
        known_bad_avoided=_as_bool(output.get("known_bad_avoided"), default=False),
        evidence_first=_as_bool(output.get("evidence_first"), default=False),
        false_trigger=_as_bool(
            output.get("false_trigger"),
            default=(
                step.status in {"failed_known_bad", "invalid_action"}
                or _is_invalid_target(_target_from_step(step))
            ),
        ),
        metadata={
            "step_id": step.step_id,
            "node_name": step.node_name,
            "action_type": step.action_type,
            "duplicate": duplicate,
        },
    )


def _validation_gate_from_evidence(
    evidence: list[HardEvidence],
    trace: RuntimeTrace,
) -> RuntimePathValidationGate:
    positive_types = []
    seen: set[HardEvidenceType] = set()
    for item in evidence:
        if item.is_positive and item.evidence_type not in seen:
            seen.add(item.evidence_type)
            positive_types.append(item.evidence_type)
    repeated = max(
        _as_int(_metric_value(trace, "repeat_validation_count", "repeated_validation_count")),
        3,
    )
    return RuntimePathValidationGate(
        required_evidence=positive_types,
        min_repeated_validations=repeated,
        min_benchmark_delta=0.0,
        max_counterexamples=0,
        max_conflicts=0,
        max_memory_induced_regression_rate=0.0,
        min_decayed_support=1.0,
        allow_model_confidence=False,
    )
