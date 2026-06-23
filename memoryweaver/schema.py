"""MemoryItem schema and supporting types.

This is the foundational data model for MemoryWeaver. Every MemoryItem
enters the system in Layer 1 and can be explicitly promoted to Layer 2.
Canonical Layer-3 records are separate Pattern objects.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class Polarity(str, Enum):
    """The feedback polarity of a memory.

    POSITIVE  — useful, successful, or validated knowledge
    NEGATIVE  — failed attempts, wrong assumptions, rejected paths
    NEUTRAL   — stable facts or background context
    AMBIGUOUS — unverified hypotheses
    """

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    AMBIGUOUS = "ambiguous"


class Layer(int, Enum):
    """Which memory layer this item belongs to.

    Layer 1 — Candidate: raw, untested memory
    Layer 2 — Activated: retrieved, used, or confirmed memory
    Layer 3 — Pattern: composed, reusable diagnostic/decision pattern
    """

    CANDIDATE = 1
    ACTIVATED = 2
    PATTERN = 3


class Status(str, Enum):
    CANDIDATE = "candidate"
    ACTIVATED = "activated"
    PROMOTED = "promoted"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class PatternStatus(str, Enum):
    PROVISIONAL = "provisional"
    STABLE = "stable"
    CHALLENGED = "challenged"
    ROLLED_BACK = "rolled_back"
    ARCHIVED = "archived"


class MemoryType(str, Enum):
    FACT = "fact"
    CORRECTION = "correction"
    SUCCESS_PATH = "success_path"
    FAILED_ATTEMPT = "failed_attempt"
    PREFERENCE = "preference"
    HYPOTHESIS = "hypothesis"
    PATTERN = "pattern"
    AVOIDANCE_RULE = "avoidance_rule"


class Freshness(str, Enum):
    STABLE = "stable"
    VOLATILE = "volatile"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class Source(str, Enum):
    """Origin of a memory item and its initial trust boundary."""

    USER = "user"
    TERMINAL = "terminal"
    TOOL = "tool"
    WEB = "web"
    COMPOSER = "composer"
    ASSISTANT = "assistant"
    FILE = "file"
    SYNTHETIC = "synthetic"
    UNKNOWN = "unknown"


@dataclass
class MemoryItem:
    """A single memory entry in the MemoryWeaver system.

    Attributes:
        id: Unique identifier, auto-generated if not provided.
        layer: Current memory layer (1 or 2). Layer 3 is legacy-read-only.
        polarity: Feedback polarity classification.
        memory_type: The kind of memory (fact, correction, pattern, etc.).
        content: The actual memory text.
        tags: Searchable keyword tags.
        linked_tags: Tags linked from related memories.
        source: Where this memory came from (user, terminal, tool, etc.).
        evidence: Supporting evidence or context.
        scope: Visibility scope (global, user, project, session).
        model_fit: Which model types this memory is suited for.
        confidence: 0.0–1.0 confidence score.
        heat: How many times this memory has been accessed.
        use_count: How many times this memory contributed to an action.
        validation_count: How many outcome confirmations or corrections it received.
        success_score: Cumulative usefulness rating.
        correction_score: Cumulative correction/avoidance rating.
        freshness: Volatility classification.
        status: Lifecycle status.
        created_at: UTC timestamp of creation.
        updated_at: UTC timestamp of last update.
    """

    id: str = field(default_factory=lambda: f"mem_{uuid.uuid4().hex[:12]}")
    layer: Layer = Layer.CANDIDATE
    polarity: Polarity = Polarity.NEUTRAL
    memory_type: MemoryType = MemoryType.FACT
    content: str = ""
    tags: list[str] = field(default_factory=list)
    linked_tags: list[str] = field(default_factory=list)
    source: Source = Source.UNKNOWN
    evidence: str = ""
    scope: str = "project"
    model_fit: list[str] = field(default_factory=list)
    confidence: float = 0.0
    heat: int = 0
    use_count: int = 0
    validation_count: int = 0
    success_score: float = 0.0
    correction_score: float = 0.0
    freshness: Freshness = Freshness.UNKNOWN
    status: Status = Status.CANDIDATE
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    accessed_at: str = ""
    used_at: str = ""
    validated_at: str = ""
    legacy_pattern: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.source, Source):
            self.source = Source(self.source)

        if self.layer == Layer.PATTERN and not self.legacy_pattern:
            raise ValueError("Layer 3 records must be created through PatternComposer")

        if self.source in (Source.ASSISTANT, Source.SYNTHETIC):
            self.polarity = Polarity.AMBIGUOUS
            self.confidence = min(self.confidence, 0.3)

    def touch(self) -> None:
        """Backward-compatible alias for recording a real access."""
        self.record_access()

    def mark_updated(self) -> None:
        """Record a mutation without fabricating a usage signal."""
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def record_access(self) -> None:
        """Record retrieval or inspection of this memory."""
        self.accessed_at = datetime.now(timezone.utc).isoformat()
        self.heat += 1

    def record_use(self) -> None:
        """Record that this memory contributed to an action."""
        self.used_at = datetime.now(timezone.utc).isoformat()
        self.use_count += 1

    def record_validation(self) -> None:
        """Record an outcome confirmation or correction."""
        self.validated_at = datetime.now(timezone.utc).isoformat()
        self.validation_count += 1

    def promote(self, target_layer: Layer | None = None) -> None:
        """Promote a MemoryItem within its Layer-1/Layer-2 lifecycle."""
        if target_layer == Layer.PATTERN:
            raise ValueError("Layer 3 records must be created through PatternComposer")
        if self.layer == Layer.PATTERN:
            raise ValueError("legacy Layer-3 MemoryItem records are read-only")
        if target_layer is not None:
            self.layer = target_layer
        elif self.layer == Layer.CANDIDATE:
            self.layer = Layer.ACTIVATED
        self.status = Status.PROMOTED
        self.mark_updated()

    def deprecate(self) -> None:
        """Mark this memory as deprecated."""
        self.status = Status.DEPRECATED
        self.mark_updated()

    def archive(self) -> None:
        """Archive this memory (soft delete)."""
        self.status = Status.ARCHIVED
        self.mark_updated()

    def activate(self) -> None:
        """Move from candidate to activated."""
        if self.layer == Layer.CANDIDATE:
            self.layer = Layer.ACTIVATED
        self.status = Status.ACTIVATED
        self.mark_updated()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["layer"] = self.layer.value
        d["polarity"] = self.polarity.value
        d["memory_type"] = self.memory_type.value
        d["freshness"] = self.freshness.value
        d["status"] = self.status.value
        d["source"] = self.source.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MemoryItem:
        d = dict(d)  # shallow copy to avoid mutating the input
        if d.get("layer") == Layer.PATTERN.value:
            d["legacy_pattern"] = True
        if d.get("source", Source.UNKNOWN.value) in (
            Source.ASSISTANT.value,
            Source.SYNTHETIC.value,
        ):
            d["polarity"] = Polarity.AMBIGUOUS.value
            d["confidence"] = min(float(d.get("confidence", 0.0)), 0.3)
        d["layer"] = Layer(d["layer"])
        d["polarity"] = Polarity(d["polarity"])
        d["memory_type"] = MemoryType(d.get("memory_type", "fact"))
        d["freshness"] = Freshness(d.get("freshness", "unknown"))
        d["status"] = Status(d["status"])
        d["source"] = Source(d.get("source", Source.UNKNOWN.value))
        return cls(**d)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, s: str) -> MemoryItem:
        return cls.from_dict(json.loads(s))


@dataclass
class Pattern:
    """A Layer-3 composed pattern built from multiple MemoryItems.

    Patterns combine signals from different polarity zones
    (positive + negative + neutral + ambiguous) into reusable
    diagnostic or decision rules. In the current harness direction,
    Layer 3 acts as a path-promotion layer: verified experience is
    trialed, scored, promoted, challenged, or rolled back as a
    reusable execution path.
    """

    id: str = field(default_factory=lambda: f"pat_{uuid.uuid4().hex[:12]}")
    pattern_type: str = "diagnostic_rule"
    status: PatternStatus = PatternStatus.PROVISIONAL
    composed_from: list[str] = field(default_factory=list)
    rule: str = ""
    applies_when: list[str] = field(default_factory=list)
    avoid_when: list[str] = field(default_factory=list)
    success_path: list[str] = field(default_factory=list)
    failed_path: list[str] = field(default_factory=list)
    evidence_links: list[str] = field(default_factory=list)
    rollback_to: list[str] = field(default_factory=list)
    scope: str = "project"
    policy_version: str = "memory-policy-v1"
    freshness: Freshness = Freshness.UNKNOWN
    confidence: float = 0.0
    path_fitness_score: float = 0.0
    model_fit: list[str] = field(default_factory=list)
    promotion_reason: str = ""
    validation_task_runs: list[str] = field(default_factory=list)
    trial_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    false_trigger_count: int = 0
    known_bad_avoidance_count: int = 0
    evidence_first_count: int = 0
    average_step_delta: float = 0.0
    average_token_cost: float = 0.0
    supersedes_patterns: list[str] = field(default_factory=list)
    challenged_by: list[str] = field(default_factory=list)
    conflict_refs: list[str] = field(default_factory=list)
    rollback_reason: str = ""
    last_validated_at: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        d["freshness"] = self.freshness.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Pattern:
        d = dict(d)
        d["status"] = PatternStatus(d.get("status", "provisional"))
        d["freshness"] = Freshness(d.get("freshness", "unknown"))
        return cls(**d)

    def mark_updated(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()
