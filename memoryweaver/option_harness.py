"""Option-guided predictive Harness module.

This module absorbs two pragmatic interaction patterns:

- present bounded options before acting
- predict likely user continuations, keep matched hints, discard misses

The module is deliberately useful but non-authoritative. It can create option
sets, reconcile predictions, record a user selection, and emit an
ActionProposal-shaped payload. It cannot write verified memory, promote Layer-3
paths, or bypass ActionGate.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable, Sequence


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OptionRisk(str, Enum):
    """Risk label for a user-facing option candidate."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class OptionStatus(str, Enum):
    """Lifecycle status for a user-facing option."""

    PROPOSED = "proposed"
    SELECTED = "selected"
    REJECTED = "rejected"
    EXPIRED = "expired"


class PredictionStatus(str, Enum):
    """Retention status for a synthetic prediction."""

    PROPOSED = "proposed"
    MATCHED = "matched"
    DISCARDED = "discarded"


@dataclass(frozen=True)
class OptionCandidate:
    """A bounded user-facing action option.

    Option candidates follow the "present choices before acting" pattern, but
    remain proposals. A selected option must still pass the normal Harness and
    ActionGate path before it can execute or be promoted.
    """

    option_id: str
    intent_guess: str
    action_plan: tuple[str, ...]
    risk: OptionRisk = OptionRisk.LOW
    required_evidence: tuple[str, ...] = ()
    confirmation_required: bool = False
    fallback: str | None = None
    promotion_allowed: bool = False
    action_name: str = "ask_user"
    target: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    status: OptionStatus = OptionStatus.PROPOSED
    rationale: str = ""
    source_reference: str = "claude_agent_sdk_option_prompt"

    def __post_init__(self) -> None:
        if not isinstance(self.risk, OptionRisk):
            object.__setattr__(self, "risk", OptionRisk(self.risk))
        if not isinstance(self.status, OptionStatus):
            object.__setattr__(self, "status", OptionStatus(self.status))

    def to_action_proposal_payload(
        self,
        *,
        thread_id: str = "",
        step: int = 0,
        user_confirmation: bool = False,
    ) -> dict[str, Any]:
        """Return an ActionProposal-shaped dict without executing it."""

        idempotency_parts = [thread_id, str(step), self.option_id, self.action_name, self.target]
        idempotency_key = ":".join(part for part in idempotency_parts if part)
        return {
            "action_name": self.action_name,
            "target": self.target,
            "arguments": dict(self.arguments),
            "reasoning": self.rationale or self.intent_guess,
            "idempotency_key": idempotency_key,
            "user_confirmation": user_confirmation,
            "metadata": {
                "option_id": self.option_id,
                "option_risk": self.risk.value,
                "option_status": self.status.value,
                "promotion_allowed": False,
                "required_evidence": list(self.required_evidence),
            },
        }

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["risk"] = self.risk.value
        data["status"] = self.status.value
        data["promotion_allowed"] = False
        return data


@dataclass(frozen=True)
class PredictionCandidate:
    """A synthetic prediction of the user's likely next intent.

    A matched prediction can be retained only as a route hint or compression
    hint. It must not become verified memory without external evidence.
    """

    prediction_id: str
    predicted_intent: str
    predicted_next_request: str
    confidence: float
    matched: bool = False
    retained_as: str = "route_hint"
    verified_memory_allowed: bool = False
    status: PredictionStatus = PredictionStatus.PROPOSED
    cache_prefix: str = ""
    source_reference: str = "deepseek_context_cache"

    def __post_init__(self) -> None:
        if not isinstance(self.status, PredictionStatus):
            object.__setattr__(self, "status", PredictionStatus(self.status))
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("prediction confidence must be between 0.0 and 1.0")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["verified_memory_allowed"] = False
        return data


@dataclass(frozen=True)
class OptionSet:
    """A bounded set of user-facing options for one turn."""

    option_set_id: str
    user_query: str
    options: tuple[OptionCandidate, ...]
    predictions: tuple[PredictionCandidate, ...] = ()
    max_options: int = 4
    created_at: str = field(default_factory=_utc_now)
    source_references: tuple[str, ...] = (
        "anthropics/claude-code",
        "claude_agent_sdk_ask_user_permissions_hooks",
        "deepseek_context_caching_prefix_hit",
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "option_set_id": self.option_set_id,
            "user_query": self.user_query,
            "options": [option.to_dict() for option in self.options],
            "predictions": [prediction.to_dict() for prediction in self.predictions],
            "max_options": self.max_options,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class UserSelection:
    """User decision over an option set."""

    option_set_id: str
    selected_option_id: str
    user_text: str = ""
    confirmed: bool = False
    selected_at: str = field(default_factory=_utc_now)


@dataclass(frozen=True)
class PredictionReconciliation:
    """Matched and discarded prediction candidates."""

    retained: tuple[PredictionCandidate, ...]
    discarded: tuple[PredictionCandidate, ...]
    cache_hit_prefixes: tuple[str, ...] = ()

    @property
    def hit_rate(self) -> float:
        total = len(self.retained) + len(self.discarded)
        return len(self.retained) / total if total else 0.0

    @property
    def discard_rate(self) -> float:
        total = len(self.retained) + len(self.discarded)
        return len(self.discarded) / total if total else 0.0


@dataclass(frozen=True)
class OptionHarnessDecision:
    """Auditable result after a user selection."""

    option_set_id: str
    selected_option: OptionCandidate | None
    status: str
    reasons: tuple[str, ...] = ()
    action_proposal_payload: dict[str, Any] | None = None
    memory_authority_granted: bool = False
    layer3_authority_granted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "option_set_id": self.option_set_id,
            "selected_option": self.selected_option.to_dict() if self.selected_option else None,
            "status": self.status,
            "reasons": list(self.reasons),
            "action_proposal_payload": self.action_proposal_payload,
            "memory_authority_granted": False,
            "layer3_authority_granted": False,
        }


@dataclass(frozen=True)
class OptionHarnessMetrics:
    """Compact metrics for option-guided predictive interaction."""

    option_count: int
    high_risk_option_count: int
    confirmation_required_count: int
    prediction_count: int
    prediction_retained_count: int
    prediction_discarded_count: int
    promotion_without_evidence_count: int = 0
    memory_authority_granted_count: int = 0
    layer3_authority_granted_count: int = 0

    @property
    def prediction_hit_rate(self) -> float:
        return (
            self.prediction_retained_count / self.prediction_count
            if self.prediction_count
            else 0.0
        )

    @property
    def prediction_discard_rate(self) -> float:
        return (
            self.prediction_discarded_count / self.prediction_count
            if self.prediction_count
            else 0.0
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["prediction_hit_rate"] = self.prediction_hit_rate
        data["prediction_discard_rate"] = self.prediction_discard_rate
        return data


def require_confirmation_for_high_risk(option: OptionCandidate) -> OptionCandidate:
    """Return an option that requires confirmation when risk is high."""

    if option.risk is not OptionRisk.HIGH or option.confirmation_required:
        return option
    return replace_option(
        option,
        confirmation_required=True,
        promotion_allowed=False,
    )


def replace_option(option: OptionCandidate, **changes: Any) -> OptionCandidate:
    """Small dataclass replacement helper that preserves authority boundaries."""

    payload = option.to_dict()
    payload.update(changes)
    payload["promotion_allowed"] = False
    payload["action_plan"] = tuple(payload.get("action_plan", ()))
    payload["required_evidence"] = tuple(payload.get("required_evidence", ()))
    return OptionCandidate(**payload)


def normalize_option_set(
    options: Iterable[OptionCandidate],
    *,
    max_options: int = 4,
) -> tuple[OptionCandidate, ...]:
    """Normalize an option set without granting promotion authority."""

    if max_options <= 0:
        raise ValueError("max_options must be positive")

    normalized: list[OptionCandidate] = []
    seen: set[str] = set()
    for option in options:
        if len(normalized) >= max_options:
            break
        if not option.option_id:
            raise ValueError("option_id is required")
        if option.option_id in seen:
            raise ValueError(f"duplicate option_id: {option.option_id}")
        if not option.action_plan:
            raise ValueError(f"option {option.option_id} must include at least one action step")
        seen.add(option.option_id)
        guarded = require_confirmation_for_high_risk(option)
        if guarded.promotion_allowed:
            guarded = replace_option(guarded, promotion_allowed=False)
        normalized.append(guarded)

    if not normalized:
        raise ValueError("at least one option is required")
    return tuple(normalized)


def retain_prediction_if_matched(
    prediction: PredictionCandidate,
    actual_text: str,
) -> PredictionCandidate | None:
    """Keep a prediction only when it matches the actual continuation.

    This follows DeepSeek-style context-cache semantics at the interaction
    layer: a prediction is retained if the actual continuation fully reuses a
    persisted prefix unit, or if the explicit predicted next request appears in
    the actual text.
    """

    expected = prediction.predicted_next_request.strip().lower()
    actual = actual_text.lower()
    cache_prefix = prediction.cache_prefix.strip().lower()
    prefix_hit = bool(cache_prefix and actual.startswith(cache_prefix))
    explicit_hit = bool(expected and expected in actual)
    if prefix_hit or explicit_hit:
        return PredictionCandidate(
            prediction_id=prediction.prediction_id,
            predicted_intent=prediction.predicted_intent,
            predicted_next_request=prediction.predicted_next_request,
            confidence=prediction.confidence,
            matched=True,
            retained_as="route_hint",
            verified_memory_allowed=False,
            status=PredictionStatus.MATCHED,
            cache_prefix=prediction.cache_prefix,
            source_reference=prediction.source_reference,
        )
    return None


def discard_prediction(prediction: PredictionCandidate) -> PredictionCandidate:
    """Mark a synthetic prediction as discarded without memory authority."""

    return PredictionCandidate(
        prediction_id=prediction.prediction_id,
        predicted_intent=prediction.predicted_intent,
        predicted_next_request=prediction.predicted_next_request,
        confidence=prediction.confidence,
        matched=False,
        retained_as="discarded",
        verified_memory_allowed=False,
        status=PredictionStatus.DISCARDED,
        cache_prefix=prediction.cache_prefix,
        source_reference=prediction.source_reference,
    )


def common_prefix_unit(first: str, second: str, *, min_chars: int = 8) -> str:
    """Return a reusable common prefix unit, or an empty string.

    This mirrors the useful part of context-cache behavior for MemoryWeaver:
    common prefixes can be retained as routing/compression hints, but not as
    facts or verified memory.
    """

    limit = min(len(first), len(second))
    idx = 0
    while idx < limit and first[idx].lower() == second[idx].lower():
        idx += 1
    prefix = first[:idx].strip()
    return prefix if len(prefix) >= min_chars else ""


def prediction_cache_hit(prediction: PredictionCandidate, actual_text: str) -> bool:
    """Return whether the actual text fully reuses a prediction cache prefix."""

    prefix = prediction.cache_prefix.strip().lower()
    return bool(prefix and actual_text.lower().startswith(prefix))


class OptionGuidedPredictiveHarness:
    """Full option-guided predictive interaction helper.

    This class is intentionally deterministic. It does not call an LLM. Upstream
    models may propose options or predictions, but this class bounds, filters,
    records, and exports them under Harness authority constraints.
    """

    def __init__(self, *, max_options: int = 4) -> None:
        if max_options <= 0:
            raise ValueError("max_options must be positive")
        self.max_options = max_options

    def default_options_for_query(self, user_query: str) -> tuple[OptionCandidate, ...]:
        """Create a conservative option set when no external options exist."""

        query = user_query.strip()
        return (
            OptionCandidate(
                option_id="inspect",
                intent_guess="Inspect context before changing anything",
                action_plan=("read relevant files", "summarize likely path"),
                risk=OptionRisk.LOW,
                required_evidence=("file_context",),
                action_name="ask_user",
                arguments={"query": query, "mode": "inspect"},
                rationale="Low-risk option for ambiguous requests.",
            ),
            OptionCandidate(
                option_id="plan",
                intent_guess="Produce a bounded implementation plan",
                action_plan=("identify files", "list tests", "wait for confirmation"),
                risk=OptionRisk.LOW,
                required_evidence=("plan_review",),
                action_name="ask_user",
                arguments={"query": query, "mode": "plan"},
                rationale="Clarifies next steps without side effects.",
            ),
            OptionCandidate(
                option_id="execute_guarded",
                intent_guess="Execute the likely low-risk path under gates",
                action_plan=("make minimal change", "run focused tests", "report diff"),
                risk=OptionRisk.MEDIUM,
                required_evidence=("git_diff", "focused_test_output"),
                action_name="tool_call",
                target="guarded_execution",
                arguments={"query": query},
                rationale="Useful when the user clearly asks to implement.",
            ),
        )

    def build_option_set(
        self,
        *,
        option_set_id: str,
        user_query: str,
        options: Sequence[OptionCandidate] | None = None,
        predictions: Sequence[PredictionCandidate] = (),
        actual_continuation: str = "",
    ) -> OptionSet:
        """Build a bounded option set with reconciled prediction hints."""

        source_options = tuple(options) if options is not None else self.default_options_for_query(user_query)
        normalized_options = normalize_option_set(source_options, max_options=self.max_options)
        reconciliation = self.reconcile_predictions(predictions, actual_continuation or user_query)
        return OptionSet(
            option_set_id=option_set_id,
            user_query=user_query,
            options=normalized_options,
            predictions=reconciliation.retained,
            max_options=self.max_options,
        )

    def reconcile_predictions(
        self,
        predictions: Sequence[PredictionCandidate],
        actual_text: str,
    ) -> PredictionReconciliation:
        """Retain matched predictions and discard all misses."""

        retained: list[PredictionCandidate] = []
        discarded: list[PredictionCandidate] = []
        cache_hits: list[str] = []
        seen: set[str] = set()
        for prediction in predictions:
            if not prediction.prediction_id:
                raise ValueError("prediction_id is required")
            if prediction.prediction_id in seen:
                raise ValueError(f"duplicate prediction_id: {prediction.prediction_id}")
            seen.add(prediction.prediction_id)
            matched = retain_prediction_if_matched(prediction, actual_text)
            if matched is None:
                discarded.append(discard_prediction(prediction))
            else:
                retained.append(matched)
                if prediction_cache_hit(prediction, actual_text):
                    cache_hits.append(prediction.cache_prefix)
        return PredictionReconciliation(
            retained=tuple(retained),
            discarded=tuple(discarded),
            cache_hit_prefixes=tuple(cache_hits),
        )

    def select_option(
        self,
        option_set: OptionSet,
        selection: UserSelection,
        *,
        thread_id: str = "",
        step: int = 0,
    ) -> OptionHarnessDecision:
        """Resolve a user selection into an ActionProposal-shaped payload."""

        if selection.option_set_id != option_set.option_set_id:
            return OptionHarnessDecision(
                option_set_id=option_set.option_set_id,
                selected_option=None,
                status="rejected",
                reasons=("selection option_set_id does not match option set",),
            )

        selected = next(
            (option for option in option_set.options if option.option_id == selection.selected_option_id),
            None,
        )
        if selected is None:
            return OptionHarnessDecision(
                option_set_id=option_set.option_set_id,
                selected_option=None,
                status="rejected",
                reasons=(f"unknown option_id: {selection.selected_option_id}",),
            )

        if selected.confirmation_required and not selection.confirmed:
            return OptionHarnessDecision(
                option_set_id=option_set.option_set_id,
                selected_option=selected,
                status="needs_confirmation",
                reasons=("selected option requires user confirmation",),
            )

        selected = replace_option(selected, status=OptionStatus.SELECTED)
        return OptionHarnessDecision(
            option_set_id=option_set.option_set_id,
            selected_option=selected,
            status="action_proposal_ready",
            reasons=("selected option converted to ActionProposal payload",),
            action_proposal_payload=selected.to_action_proposal_payload(
                thread_id=thread_id,
                step=step,
                user_confirmation=selection.confirmed,
            ),
            memory_authority_granted=False,
            layer3_authority_granted=False,
        )

    def metrics_for(
        self,
        option_set: OptionSet,
        reconciliation: PredictionReconciliation | None = None,
    ) -> OptionHarnessMetrics:
        """Produce compact safety metrics for an option-guided turn."""

        retained = len(option_set.predictions)
        discarded = len(reconciliation.discarded) if reconciliation is not None else 0
        prediction_count = retained + discarded
        return OptionHarnessMetrics(
            option_count=len(option_set.options),
            high_risk_option_count=sum(1 for option in option_set.options if option.risk is OptionRisk.HIGH),
            confirmation_required_count=sum(
                1 for option in option_set.options if option.confirmation_required
            ),
            prediction_count=prediction_count,
            prediction_retained_count=retained,
            prediction_discarded_count=discarded,
            promotion_without_evidence_count=0,
            memory_authority_granted_count=0,
            layer3_authority_granted_count=0,
        )
