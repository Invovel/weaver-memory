"""Evidence-gated runtime paths for Layer-3 pattern reuse.

This module is the thin runtime bridge between a proposed agent action and a
Layer-3 Pattern. It deliberately treats model confidence as non-promoting
evidence: promotion and rollback are driven by external observations such as
tool results, tests, user corrections, diffs, benchmark deltas, conflicts, and
rollback records.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
from math import pow
from pathlib import Path
from typing import Any

from memoryweaver.action_gate import ActionGate, ActionGateDecision, ActionProposal
from memoryweaver.composer import PatternComposer
from memoryweaver.contract import EnvironmentContract
from memoryweaver.schema import Pattern, PatternStatus
from memoryweaver.store import SCHEMA_VERSION, atomic_write_json


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class HardEvidenceType(str, Enum):
    TOOL_RESULT = "tool_result"
    TEST_RESULT = "test_result"
    USER_CORRECTION = "user_correction"
    FILE_DIFF = "file_diff"
    BENCHMARK_SCORE = "benchmark_score"
    REPEAT_VALIDATION = "repeat_validation"
    COUNTEREXAMPLE = "counterexample"
    CONFLICT = "conflict"
    TIME_DECAY = "time_decay"
    ROLLBACK_RECORD = "rollback_record"
    MODEL_CONFIDENCE = "model_confidence"


NEGATIVE_EVIDENCE_TYPES = {
    HardEvidenceType.COUNTEREXAMPLE,
    HardEvidenceType.CONFLICT,
    HardEvidenceType.ROLLBACK_RECORD,
}


@dataclass
class HardEvidence:
    """External observation that may support, challenge, or roll back a path."""

    evidence_type: HardEvidenceType | str
    task_id: str = ""
    task_family: str = ""
    passed: bool = False
    source_ref: str = ""
    status: str = ""
    target: str = ""
    expected: str = ""
    observed: str = ""
    score_before: float | None = None
    score_after: float | None = None
    regression_rate: float = 0.0
    count: int = 1
    conflict_ref: str = ""
    rollback_ref: str = ""
    known_bad_avoided: bool = False
    evidence_first: bool = False
    false_trigger: bool = False
    created_at: str = field(default_factory=_utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_type, HardEvidenceType):
            self.evidence_type = HardEvidenceType(self.evidence_type)

    @property
    def is_external(self) -> bool:
        return self.evidence_type != HardEvidenceType.MODEL_CONFIDENCE

    @property
    def is_positive(self) -> bool:
        return (
            self.is_external
            and self.passed
            and self.evidence_type not in NEGATIVE_EVIDENCE_TYPES
            and not self.false_trigger
        )

    @property
    def benchmark_delta(self) -> float:
        if self.score_before is None or self.score_after is None:
            return 0.0
        return round(float(self.score_after) - float(self.score_before), 4)

    def decayed_weight(
        self,
        *,
        now: datetime | None = None,
        half_life_days: float = 30.0,
    ) -> float:
        if not self.is_positive:
            return 0.0
        if half_life_days <= 0:
            return float(max(self.count, 1))
        try:
            created = datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
        except ValueError:
            created = now or datetime.now(timezone.utc)
        reference = now or datetime.now(timezone.utc)
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        days = max((reference - created).total_seconds() / 86400, 0.0)
        return round(float(max(self.count, 1)) * pow(0.5, days / half_life_days), 4)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence_type"] = self.evidence_type.value
        data["benchmark_delta"] = self.benchmark_delta
        data["is_external"] = self.is_external
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HardEvidence":
        payload = dict(data)
        payload.pop("benchmark_delta", None)
        payload.pop("is_external", None)
        payload["evidence_type"] = HardEvidenceType(payload["evidence_type"])
        return cls(**payload)


@dataclass
class RuntimePathCondition:
    """When a runtime path is allowed to intervene."""

    task_tags: list[str] = field(default_factory=list)
    query_terms: list[str] = field(default_factory=list)
    failure_modes: list[str] = field(default_factory=list)
    required_state: dict[str, Any] = field(default_factory=dict)

    def matches(self, *, query: str, tags: list[str], state: dict[str, Any]) -> bool:
        tag_set = {tag.lower() for tag in tags}
        if self.task_tags and not set(tag.lower() for tag in self.task_tags).issubset(tag_set):
            return False

        query_lower = query.lower()
        if self.query_terms and not any(term.lower() in query_lower for term in self.query_terms):
            return False

        if self.failure_modes:
            failure_mode = str(state.get("failure_mode", "")).lower()
            allowed_modes = {mode.lower() for mode in self.failure_modes}
            if failure_mode not in allowed_modes:
                return False

        for key, expected in self.required_state.items():
            if state.get(key) != expected:
                return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RuntimePathCondition":
        return cls(**dict(data))


@dataclass
class RuntimePathValidationGate:
    """Hard-evidence requirements before a runtime path may be promoted."""

    required_evidence: list[HardEvidenceType | str] = field(default_factory=list)
    min_repeated_validations: int = 3
    min_benchmark_delta: float = 0.0
    max_counterexamples: int = 0
    max_conflicts: int = 0
    max_memory_induced_regression_rate: float = 0.0
    half_life_days: float = 30.0
    min_decayed_support: float = 1.0
    allow_model_confidence: bool = False

    def __post_init__(self) -> None:
        self.required_evidence = [
            item if isinstance(item, HardEvidenceType) else HardEvidenceType(item)
            for item in self.required_evidence
        ]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["required_evidence"] = [item.value for item in self.required_evidence]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RuntimePathValidationGate":
        payload = dict(data)
        payload["required_evidence"] = [
            HardEvidenceType(item) for item in payload.get("required_evidence", [])
        ]
        return cls(**payload)


@dataclass
class RuntimePathRollbackRule:
    """When the harness should withdraw a runtime path."""

    rollback_on_conflict: bool = True
    rollback_on_counterexamples: int = 1
    rollback_on_regression_rate: float = 0.0
    rollback_reason: str = "runtime path challenged by external evidence"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RuntimePathRollbackRule":
        return cls(**dict(data))


@dataclass
class RuntimePathSpec:
    """A reusable execution path, not a prompt fragment."""

    path_id: str
    name: str
    condition: RuntimePathCondition
    action_policy: list[ActionProposal] = field(default_factory=list)
    validation_gate: RuntimePathValidationGate = field(default_factory=RuntimePathValidationGate)
    fallback: ActionProposal | None = None
    rollback_rule: RuntimePathRollbackRule = field(default_factory=RuntimePathRollbackRule)
    pattern_id: str = ""
    blocked_targets: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path_id": self.path_id,
            "name": self.name,
            "condition": self.condition.to_dict(),
            "action_policy": [action.to_dict() for action in self.action_policy],
            "validation_gate": self.validation_gate.to_dict(),
            "fallback": self.fallback.to_dict() if self.fallback else None,
            "rollback_rule": self.rollback_rule.to_dict(),
            "pattern_id": self.pattern_id,
            "blocked_targets": list(self.blocked_targets),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RuntimePathSpec":
        payload = dict(data)
        payload["condition"] = RuntimePathCondition.from_dict(payload["condition"])
        payload["action_policy"] = [
            ActionProposal.from_dict(item)
            for item in payload.get("action_policy", [])
        ]
        payload["validation_gate"] = RuntimePathValidationGate.from_dict(
            payload.get("validation_gate", {})
        )
        fallback = payload.get("fallback")
        payload["fallback"] = ActionProposal.from_dict(fallback) if fallback else None
        payload["rollback_rule"] = RuntimePathRollbackRule.from_dict(
            payload.get("rollback_rule", {})
        )
        return cls(**payload)


@dataclass
class RuntimeTask:
    task_id: str
    query: str
    tags: list[str] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)
    task_family: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RuntimePathAssessment:
    path_id: str
    can_promote: bool
    should_rollback: bool
    reasons: list[str] = field(default_factory=list)
    hard_evidence_count: int = 0
    model_confidence_ignored_count: int = 0
    repeated_validation_count: int = 0
    counterexample_count: int = 0
    conflict_count: int = 0
    benchmark_delta: float = 0.0
    memory_induced_regression_rate: float = 0.0
    decayed_support: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RuntimePathDecision:
    task: RuntimeTask
    path_id: str
    condition_matched: bool
    proposed_action: ActionProposal
    selected_action: ActionProposal
    action_gate: ActionGateDecision
    assessment: RuntimePathAssessment
    fallback_used: bool = False
    rollback_recommended: bool = False
    ledger_index: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task.to_dict(),
            "path_id": self.path_id,
            "condition_matched": self.condition_matched,
            "proposed_action": self.proposed_action.to_dict(),
            "selected_action": self.selected_action.to_dict(),
            "action_gate": self.action_gate.to_dict(),
            "assessment": self.assessment.to_dict(),
            "fallback_used": self.fallback_used,
            "rollback_recommended": self.rollback_recommended,
            "ledger_index": self.ledger_index,
        }


@dataclass
class RuntimePathTrialResult:
    path_id: str
    pattern: Pattern | None
    assessment: RuntimePathAssessment
    promoted: bool = False
    rolled_back: bool = False
    mutation: str = "none"

    def to_dict(self) -> dict[str, Any]:
        return {
            "path_id": self.path_id,
            "pattern": self.pattern.to_dict() if self.pattern else None,
            "assessment": self.assessment.to_dict(),
            "promoted": self.promoted,
            "rolled_back": self.rolled_back,
            "mutation": self.mutation,
        }


@dataclass
class RuntimeCandidateRegistration:
    """Audit result for admitting a trace-derived candidate path."""

    path_id: str
    candidate_id: str
    trace_id: str
    assessment: RuntimePathAssessment
    initial_evidence_count: int = 0
    rejected_evidence_count: int = 0
    rejected_as_challenge: bool = False
    ledger_index: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "path_id": self.path_id,
            "candidate_id": self.candidate_id,
            "trace_id": self.trace_id,
            "assessment": self.assessment.to_dict(),
            "initial_evidence_count": self.initial_evidence_count,
            "rejected_evidence_count": self.rejected_evidence_count,
            "rejected_as_challenge": self.rejected_as_challenge,
            "ledger_index": self.ledger_index,
        }


@dataclass
class RuntimePathReplayResult:
    """Result of executing a runtime path under harness control."""

    task: RuntimeTask
    path_id: str
    matched: bool
    policy_completed: bool
    rollback_recommended: bool
    assessment_before: RuntimePathAssessment
    assessment_after: RuntimePathAssessment
    executed_actions: list[ActionProposal] = field(default_factory=list)
    skipped_targets: list[str] = field(default_factory=list)
    tool_results: list[Any] = field(default_factory=list)
    fallback_action: ActionProposal | None = None
    ledger_index: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task.to_dict(),
            "path_id": self.path_id,
            "matched": self.matched,
            "policy_completed": self.policy_completed,
            "rollback_recommended": self.rollback_recommended,
            "assessment_before": self.assessment_before.to_dict(),
            "assessment_after": self.assessment_after.to_dict(),
            "executed_actions": [item.to_dict() for item in self.executed_actions],
            "skipped_targets": list(self.skipped_targets),
            "tool_results": [
                item.to_dict() if hasattr(item, "to_dict") else dict(item)
                for item in self.tool_results
            ],
            "fallback_action": self.fallback_action.to_dict() if self.fallback_action else None,
            "ledger_index": self.ledger_index,
        }


class HarnessRuntime:
    """Runtime execution-path layer backed by hard evidence."""

    def __init__(
        self,
        paths: list[RuntimePathSpec] | None = None,
        *,
        action_gate: ActionGate | None = None,
        composer: PatternComposer | None = None,
        now: datetime | None = None,
    ) -> None:
        self.action_gate = action_gate or ActionGate(EnvironmentContract.default_live_loop())
        self.composer = composer
        self.now = now
        self._paths: dict[str, RuntimePathSpec] = {}
        self._evidence: dict[str, list[HardEvidence]] = {}
        self.ledger: list[dict[str, Any]] = []
        for path in paths or []:
            self.register_path(path)

    def register_path(self, path: RuntimePathSpec) -> None:
        self._paths[path.path_id] = path
        self._evidence.setdefault(path.path_id, [])

    def register_candidate(
        self,
        candidate: Any,
        *,
        record_initial_evidence: bool = True,
        challenge_with_rejected: bool = False,
    ) -> RuntimeCandidateRegistration:
        path = getattr(candidate, "path", None)
        if not isinstance(path, RuntimePathSpec):
            raise TypeError("candidate.path must be a RuntimePathSpec")

        self.register_path(path)
        positive_evidence = list(getattr(candidate, "evidence", []))
        rejected_evidence = list(getattr(candidate, "rejected_evidence", []))
        evidence_to_record: list[HardEvidence] = []
        if record_initial_evidence:
            evidence_to_record.extend(positive_evidence)
        if challenge_with_rejected:
            evidence_to_record.extend(rejected_evidence)
        if evidence_to_record:
            self.record_evidence(path.path_id, evidence_to_record)

        assessment = self.assess(path.path_id)
        ledger_index = self._record(
            "candidate_registered",
            path_id=path.path_id,
            candidate_id=str(getattr(candidate, "candidate_id", "")),
            trace_id=str(getattr(candidate, "trace_id", "")),
            assessment=assessment.to_dict(),
            initial_evidence_count=len(positive_evidence) if record_initial_evidence else 0,
            rejected_evidence_count=len(rejected_evidence),
            rejected_as_challenge=challenge_with_rejected,
            rejected_evidence=[item.to_dict() for item in rejected_evidence],
            metrics=dict(getattr(candidate, "metrics", {})),
            notes=list(getattr(candidate, "notes", [])),
        )
        return RuntimeCandidateRegistration(
            path_id=path.path_id,
            candidate_id=str(getattr(candidate, "candidate_id", "")),
            trace_id=str(getattr(candidate, "trace_id", "")),
            assessment=assessment,
            initial_evidence_count=len(positive_evidence) if record_initial_evidence else 0,
            rejected_evidence_count=len(rejected_evidence),
            rejected_as_challenge=challenge_with_rejected,
            ledger_index=ledger_index,
        )

    def evidence_for(self, path_id: str) -> list[HardEvidence]:
        return list(self._evidence.get(path_id, []))

    def record_evidence(self, path_id: str, evidence: HardEvidence | list[HardEvidence]) -> None:
        if path_id not in self._paths:
            raise KeyError(f"RuntimePath '{path_id}' not registered")
        items = evidence if isinstance(evidence, list) else [evidence]
        self._evidence.setdefault(path_id, []).extend(items)
        self._record("evidence", path_id=path_id, evidence=[item.to_dict() for item in items])

    def decide(
        self,
        task: RuntimeTask,
        proposed_action: ActionProposal,
        *,
        new_evidence: list[HardEvidence] | None = None,
    ) -> RuntimePathDecision:
        matched, assessment = self._best_match(task)
        if matched and new_evidence:
            self.record_evidence(matched.path_id, new_evidence)
            assessment = self.assess(matched.path_id)

        if matched is None or assessment is None:
            assessment = RuntimePathAssessment(
                path_id="",
                can_promote=False,
                should_rollback=False,
                reasons=["no runtime path matched"],
            )
            gate = self.action_gate.validate(proposed_action)
            ledger_index = self._record(
                "decision",
                path_id="",
                task=task.to_dict(),
                selected_action=proposed_action.to_dict(),
                action_gate=gate.to_dict(),
                assessment=assessment.to_dict(),
            )
            return RuntimePathDecision(
                task=task,
                path_id="",
                condition_matched=False,
                proposed_action=proposed_action,
                selected_action=proposed_action,
                action_gate=gate,
                assessment=assessment,
                ledger_index=ledger_index,
            )

        selected, fallback_used = self._select_action(
            matched,
            task,
            proposed_action,
            assessment,
        )
        gate = self.action_gate.validate(selected)
        if not gate.allowed and matched.fallback is not None:
            selected = matched.fallback
            fallback_used = True
            gate = self.action_gate.validate(selected)

        ledger_index = self._record(
            "decision",
            path_id=matched.path_id,
            task=task.to_dict(),
            selected_action=selected.to_dict(),
            proposed_action=proposed_action.to_dict(),
            action_gate=gate.to_dict(),
            assessment=assessment.to_dict(),
            fallback_used=fallback_used,
        )
        return RuntimePathDecision(
            task=task,
            path_id=matched.path_id,
            condition_matched=True,
            proposed_action=proposed_action,
            selected_action=selected,
            action_gate=gate,
            assessment=assessment,
            fallback_used=fallback_used,
            rollback_recommended=assessment.should_rollback,
            ledger_index=ledger_index,
        )

    def assess(self, path_id: str) -> RuntimePathAssessment:
        path = self._paths[path_id]
        evidence = self._evidence.get(path_id, [])
        hard = [item for item in evidence if item.is_external]
        model_confidence_ignored = sum(
            1 for item in evidence if item.evidence_type == HardEvidenceType.MODEL_CONFIDENCE
        )
        positive = [item for item in hard if item.is_positive]
        required_present = {
            item.evidence_type
            for item in positive
        }
        repeated_validation_count = sum(
            max(item.count, 1)
            for item in positive
            if item.evidence_type == HardEvidenceType.REPEAT_VALIDATION
        )
        counterexamples = sum(
            max(item.count, 1)
            for item in hard
            if item.evidence_type == HardEvidenceType.COUNTEREXAMPLE or item.false_trigger
        )
        conflicts = sum(
            max(item.count, 1)
            for item in hard
            if item.evidence_type == HardEvidenceType.CONFLICT or item.conflict_ref
        )
        benchmark_delta = max((item.benchmark_delta for item in hard), default=0.0)
        regression_rate = max((item.regression_rate for item in hard), default=0.0)
        decayed_support = round(
            sum(
                item.decayed_weight(
                    now=self.now,
                    half_life_days=path.validation_gate.half_life_days,
                )
                for item in positive
            ),
            4,
        )

        reasons: list[str] = []
        rollback_rule = path.rollback_rule
        should_rollback = False
        if rollback_rule.rollback_on_conflict and conflicts > 0:
            should_rollback = True
            reasons.append("conflict evidence present")
        if counterexamples >= rollback_rule.rollback_on_counterexamples:
            should_rollback = True
            reasons.append("counterexample threshold reached")
        if regression_rate > rollback_rule.rollback_on_regression_rate:
            should_rollback = True
            reasons.append("memory-induced regression threshold exceeded")

        gate = path.validation_gate
        missing = [
            item.value
            for item in gate.required_evidence
            if item not in required_present
        ]
        if missing:
            reasons.append(f"missing hard evidence: {', '.join(missing)}")
        if repeated_validation_count < gate.min_repeated_validations:
            reasons.append(
                "repeated validations below threshold: "
                f"{repeated_validation_count}/{gate.min_repeated_validations}"
            )
        if benchmark_delta < gate.min_benchmark_delta:
            reasons.append(
                f"benchmark delta {benchmark_delta:.4f} below {gate.min_benchmark_delta:.4f}"
            )
        if counterexamples > gate.max_counterexamples:
            reasons.append("too many counterexamples")
        if conflicts > gate.max_conflicts:
            reasons.append("too many conflicts")
        if regression_rate > gate.max_memory_induced_regression_rate:
            reasons.append("memory-induced regression rate too high")
        if decayed_support < gate.min_decayed_support:
            reasons.append(
                f"decayed support {decayed_support:.4f} below {gate.min_decayed_support:.4f}"
            )
        if model_confidence_ignored and not gate.allow_model_confidence:
            reasons.append("model confidence ignored for promotion")

        can_promote = (
            not should_rollback
            and not missing
            and repeated_validation_count >= gate.min_repeated_validations
            and benchmark_delta >= gate.min_benchmark_delta
            and counterexamples <= gate.max_counterexamples
            and conflicts <= gate.max_conflicts
            and regression_rate <= gate.max_memory_induced_regression_rate
            and decayed_support >= gate.min_decayed_support
        )
        return RuntimePathAssessment(
            path_id=path_id,
            can_promote=can_promote,
            should_rollback=should_rollback,
            reasons=reasons,
            hard_evidence_count=len(hard),
            model_confidence_ignored_count=model_confidence_ignored,
            repeated_validation_count=repeated_validation_count,
            counterexample_count=counterexamples,
            conflict_count=conflicts,
            benchmark_delta=benchmark_delta,
            memory_induced_regression_rate=regression_rate,
            decayed_support=decayed_support,
        )

    def record_trial(
        self,
        path_id: str,
        *,
        task_run_id: str,
        evidence: list[HardEvidence],
        selected_cost: int = 1,
        baseline_cost: int = 4,
        oracle_cost: int = 1,
    ) -> RuntimePathTrialResult:
        self.record_evidence(path_id, evidence)
        path = self._paths[path_id]
        assessment = self.assess(path_id)
        pattern: Pattern | None = None
        mutation = "none"

        if self.composer is None or not path.pattern_id:
            return RuntimePathTrialResult(
                path_id=path_id,
                pattern=None,
                assessment=assessment,
                mutation=mutation,
            )

        external = [item for item in evidence if item.is_external]
        if not external:
            self._record(
                "trial_skipped",
                path_id=path_id,
                task_run_id=task_run_id,
                reason="no external evidence",
                assessment=assessment.to_dict(),
            )
            return RuntimePathTrialResult(
                path_id=path_id,
                pattern=self.composer._get(path.pattern_id),
                assessment=assessment,
                mutation=mutation,
            )

        if assessment.should_rollback:
            pattern = self.composer.rollback(path.pattern_id, path.rollback_rule.rollback_reason)
            self._record(
                "rollback",
                path_id=path_id,
                pattern_id=pattern.id,
                task_run_id=task_run_id,
                reason=path.rollback_rule.rollback_reason,
                assessment=assessment.to_dict(),
            )
            return RuntimePathTrialResult(
                path_id=path_id,
                pattern=pattern,
                assessment=assessment,
                rolled_back=True,
                mutation="rollback",
            )

        positive_external = [item for item in external if item.is_positive]
        if not positive_external:
            pattern = self.composer.record_path_trial(
                path.pattern_id,
                task_run_id=task_run_id,
                successful=False,
                false_trigger=any(item.false_trigger for item in external),
                conflict_ref=_first_conflict_ref(external) or f"runtime:{task_run_id}",
            )
            mutation = "trial_failed"
        else:
            pattern = self.composer.record_path_trial(
                path.pattern_id,
                task_run_id=task_run_id,
                successful=True,
                steps_saved=max(0, baseline_cost - selected_cost),
                known_bad_avoided=int(any(item.known_bad_avoided for item in positive_external)),
                evidence_first=any(item.evidence_first for item in positive_external),
                false_trigger=any(item.false_trigger for item in external),
                scope_match=True,
                recency_score=max(0.0, min(assessment.decayed_support, 1.0)),
            )
            mutation = "trial_recorded"

        promoted = False
        if assessment.can_promote and pattern.status != PatternStatus.STABLE:
            try:
                pattern = self.composer.promote_stable(path.pattern_id)
                promoted = True
                mutation = "promoted_stable"
                self._record(
                    "promotion",
                    path_id=path_id,
                    pattern_id=pattern.id,
                    task_run_id=task_run_id,
                    assessment=assessment.to_dict(),
                )
            except ValueError as exc:
                self._record(
                    "promotion_blocked",
                    path_id=path_id,
                    pattern_id=path.pattern_id,
                    task_run_id=task_run_id,
                    reason=str(exc),
                    assessment=assessment.to_dict(),
                )

        return RuntimePathTrialResult(
            path_id=path_id,
            pattern=pattern,
            assessment=assessment,
            promoted=promoted,
            mutation=mutation,
        )

    def guarded_replay(
        self,
        task: RuntimeTask,
        proposed_action: ActionProposal,
        gateway: Any,
        *,
        thread_id: str,
        start_step: int = 1,
    ) -> RuntimePathReplayResult:
        matched, assessment_before = self._best_match(task)
        if matched is None or assessment_before is None:
            empty = RuntimePathAssessment(
                path_id="",
                can_promote=False,
                should_rollback=False,
                reasons=["no runtime path matched"],
            )
            ledger_index = self._record(
                "guarded_replay",
                path_id="",
                task=task.to_dict(),
                proposed_action=proposed_action.to_dict(),
                executed_actions=[],
                skipped_targets=[],
                assessment_before=empty.to_dict(),
                assessment_after=empty.to_dict(),
                matched=False,
            )
            return RuntimePathReplayResult(
                task=task,
                path_id="",
                matched=False,
                policy_completed=False,
                rollback_recommended=False,
                assessment_before=empty,
                assessment_after=empty,
                ledger_index=ledger_index,
            )

        if assessment_before.should_rollback:
            ledger_index = self._record(
                "guarded_replay",
                path_id=matched.path_id,
                task=task.to_dict(),
                proposed_action=proposed_action.to_dict(),
                executed_actions=[],
                skipped_targets=[],
                tool_results=[],
                assessment_before=assessment_before.to_dict(),
                assessment_after=assessment_before.to_dict(),
                policy_completed=False,
                rollback_recommended=True,
                fallback_action=matched.fallback.to_dict() if matched.fallback else None,
                matched=True,
            )
            return RuntimePathReplayResult(
                task=task,
                path_id=matched.path_id,
                matched=True,
                policy_completed=False,
                rollback_recommended=True,
                assessment_before=assessment_before,
                assessment_after=assessment_before,
                fallback_action=matched.fallback,
                ledger_index=ledger_index,
            )

        executed_actions: list[ActionProposal] = []
        skipped_targets: list[str] = []
        tool_results: list[Any] = []
        step = start_step

        for action in matched.action_policy:
            target = action.target.lower().replace(" ", "_")
            if target and self._task_has_satisfied_target(task, matched.path_id, target):
                skipped_targets.append(action.target)
                continue

            executable_action = action
            if not executable_action.idempotency_key:
                action_data = executable_action.to_dict()
                action_data["idempotency_key"] = (
                    f"{thread_id}:{step}:{executable_action.action_name}:{executable_action.target}"
                ).strip(":")
                executable_action = ActionProposal.from_dict(action_data)

            result = gateway.execute(executable_action, thread_id=thread_id, step=step)
            step += 1
            executed_actions.append(executable_action)
            tool_results.append(result)
            if hasattr(result, "to_hard_evidence"):
                evidence = result.to_hard_evidence(
                    task_id=task.task_id,
                    task_family=task.task_family,
                )
                self.record_evidence(matched.path_id, evidence)

            current_assessment = self.assess(matched.path_id)
            if current_assessment.should_rollback:
                break

        assessment_after = self.assess(matched.path_id)
        policy_completed = (
            not assessment_after.should_rollback
            and all(
                self._task_has_satisfied_target(
                    task,
                    matched.path_id,
                    action.target.lower().replace(" ", "_"),
                )
                for action in matched.action_policy
                if action.target
            )
        )
        fallback_action = matched.fallback if assessment_after.should_rollback else None
        ledger_index = self._record(
            "guarded_replay",
            path_id=matched.path_id,
            task=task.to_dict(),
            proposed_action=proposed_action.to_dict(),
            executed_actions=[item.to_dict() for item in executed_actions],
            skipped_targets=list(skipped_targets),
            tool_results=[
                item.to_dict() if hasattr(item, "to_dict") else dict(item)
                for item in tool_results
            ],
            assessment_before=assessment_before.to_dict(),
            assessment_after=assessment_after.to_dict(),
            policy_completed=policy_completed,
            rollback_recommended=assessment_after.should_rollback,
            fallback_action=fallback_action.to_dict() if fallback_action else None,
            matched=True,
        )
        return RuntimePathReplayResult(
            task=task,
            path_id=matched.path_id,
            matched=True,
            policy_completed=policy_completed,
            rollback_recommended=assessment_after.should_rollback,
            assessment_before=assessment_before,
            assessment_after=assessment_after,
            executed_actions=executed_actions,
            skipped_targets=skipped_targets,
            tool_results=tool_results,
            fallback_action=fallback_action,
            ledger_index=ledger_index,
        )

    def _best_match(
        self,
        task: RuntimeTask,
    ) -> tuple[RuntimePathSpec | None, RuntimePathAssessment | None]:
        matches: list[tuple[RuntimePathSpec, RuntimePathAssessment]] = []
        for path in self._paths.values():
            if path.condition.matches(query=task.query, tags=task.tags, state=task.state):
                matches.append((path, self.assess(path.path_id)))
        if not matches:
            return None, None
        matches.sort(
            key=lambda item: (
                1 if item[1].should_rollback else 0,
                1 if not item[1].can_promote else 0,
                -item[1].decayed_support,
                -item[1].repeated_validation_count,
                -item[1].benchmark_delta,
            )
        )
        return matches[0]

    def _select_action(
        self,
        path: RuntimePathSpec,
        task: RuntimeTask,
        proposed_action: ActionProposal,
        assessment: RuntimePathAssessment,
    ) -> tuple[ActionProposal, bool]:
        if assessment.should_rollback and path.fallback is not None:
            return path.fallback, True

        unmet = self._first_unmet_policy_action(path, task)
        proposed_target = proposed_action.target.lower().replace(" ", "_")
        blocked = {item.lower().replace(" ", "_") for item in path.blocked_targets}
        if proposed_target in blocked:
            if unmet is not None:
                return unmet, False
            if path.action_policy:
                return path.action_policy[0], False
            if path.fallback is not None:
                return path.fallback, True

        return unmet or proposed_action, False

    def _first_unmet_policy_action(
        self,
        path: RuntimePathSpec,
        task: RuntimeTask,
    ) -> ActionProposal | None:
        for action in path.action_policy:
            target = action.target.lower().replace(" ", "_")
            if target and not self._task_has_satisfied_target(task, path.path_id, target):
                return action
        return None

    def _task_has_satisfied_target(
        self,
        task: RuntimeTask,
        path_id: str,
        target: str,
    ) -> bool:
        normalized = target.lower().replace(" ", "_")
        for item in self._evidence.get(path_id, []):
            evidence_target = item.target.lower().replace(" ", "_")
            if evidence_target != normalized or not item.is_positive:
                continue
            if not item.task_id or item.task_id == task.task_id:
                return True
        return False

    def _record(self, event: str, **payload: Any) -> int:
        record = {
            "index": len(self.ledger) + 1,
            "event": event,
            "timestamp": _utc_now(),
            **payload,
        }
        self.ledger.append(record)
        return int(record["index"])


def _first_conflict_ref(evidence: list[HardEvidence]) -> str:
    for item in evidence:
        if item.conflict_ref:
            return item.conflict_ref
    return ""


class RuntimePathStore:
    """JSON-backed store for runtime paths, evidence, and audit ledger."""

    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._paths: dict[str, RuntimePathSpec] = {}
        self._evidence: dict[str, list[HardEvidence]] = {}
        self._ledger: list[dict[str, Any]] = []
        self._load()

    def save_runtime(self, runtime: HarnessRuntime) -> None:
        self._paths = dict(runtime._paths)
        self._evidence = {
            path_id: list(items)
            for path_id, items in runtime._evidence.items()
        }
        self._ledger = [dict(item) for item in runtime.ledger]
        self._save()

    def to_runtime(
        self,
        *,
        action_gate: ActionGate | None = None,
        composer: PatternComposer | None = None,
        now: datetime | None = None,
    ) -> HarnessRuntime:
        runtime = HarnessRuntime(
            list(self._paths.values()),
            action_gate=action_gate,
            composer=composer,
            now=now,
        )
        runtime._evidence = {
            path_id: list(items)
            for path_id, items in self._evidence.items()
        }
        runtime.ledger = [dict(item) for item in self._ledger]
        return runtime

    def add_path(self, path: RuntimePathSpec) -> None:
        self._paths[path.path_id] = path
        self._evidence.setdefault(path.path_id, [])
        self._save()

    def add_evidence(self, path_id: str, evidence: HardEvidence | list[HardEvidence]) -> None:
        if path_id not in self._paths:
            raise KeyError(f"RuntimePath '{path_id}' not registered")
        items = evidence if isinstance(evidence, list) else [evidence]
        self._evidence.setdefault(path_id, []).extend(items)
        self._save()

    def get_path(self, path_id: str) -> RuntimePathSpec | None:
        return self._paths.get(path_id)

    def list_paths(self) -> list[RuntimePathSpec]:
        return list(self._paths.values())

    def evidence_for(self, path_id: str) -> list[HardEvidence]:
        return list(self._evidence.get(path_id, []))

    @property
    def ledger(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._ledger]

    def _save(self) -> None:
        atomic_write_json(
            self._path,
            {
                "version": SCHEMA_VERSION,
                "runtime_paths": [path.to_dict() for path in self._paths.values()],
                "evidence": {
                    path_id: [item.to_dict() for item in items]
                    for path_id, items in self._evidence.items()
                },
                "ledger": [dict(item) for item in self._ledger],
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
        for raw in data.get("runtime_paths", []):
            path = RuntimePathSpec.from_dict(raw)
            self._paths[path.path_id] = path
        raw_evidence = data.get("evidence", {})
        if isinstance(raw_evidence, dict):
            for path_id, items in raw_evidence.items():
                self._evidence[str(path_id)] = [
                    HardEvidence.from_dict(item)
                    for item in items
                ]
        self._ledger = [dict(item) for item in data.get("ledger", [])]
