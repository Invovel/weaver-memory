"""MemoryItem schema and supporting types.

This is the foundational data model for MemoryWeaver. Every memory
enters the system as a MemoryItem and travels through Layer 1 → 2 → 3
based on feedback, scoring, and promotion rules.
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


@dataclass
class MemoryItem:
    """A single memory entry in the MemoryWeaver system.

    Attributes:
        id: Unique identifier, auto-generated if not provided.
        layer: Current memory layer (1, 2, or 3).
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
    source: str = "unknown"
    evidence: str = ""
    scope: str = "project"
    model_fit: list[str] = field(default_factory=list)
    confidence: float = 0.0
    heat: int = 0
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

    def touch(self) -> None:
        """Update the timestamp and increment heat."""
        self.updated_at = datetime.now(timezone.utc).isoformat()
        self.heat += 1

    def promote(self, target_layer: Layer | None = None) -> None:
        """Promote to the next layer (or a specific one)."""
        if target_layer is not None:
            self.layer = target_layer
        elif self.layer < Layer.PATTERN:
            self.layer = Layer(self.layer.value + 1)
        self.status = Status.PROMOTED
        self.touch()

    def deprecate(self) -> None:
        """Mark this memory as deprecated."""
        self.status = Status.DEPRECATED
        self.touch()

    def archive(self) -> None:
        """Archive this memory (soft delete)."""
        self.status = Status.ARCHIVED
        self.touch()

    def activate(self) -> None:
        """Move from candidate to activated."""
        if self.layer == Layer.CANDIDATE:
            self.layer = Layer.ACTIVATED
        self.status = Status.ACTIVATED
        self.touch()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["layer"] = self.layer.value
        d["polarity"] = self.polarity.value
        d["memory_type"] = self.memory_type.value
        d["freshness"] = self.freshness.value
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MemoryItem:
        d = dict(d)  # shallow copy to avoid mutating the input
        d["layer"] = Layer(d["layer"])
        d["polarity"] = Polarity(d["polarity"])
        d["memory_type"] = MemoryType(d.get("memory_type", "fact"))
        d["freshness"] = Freshness(d.get("freshness", "unknown"))
        d["status"] = Status(d["status"])
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
    diagnostic or decision rules.
    """

    id: str = field(default_factory=lambda: f"pat_{uuid.uuid4().hex[:12]}")
    pattern_type: str = "diagnostic_rule"
    composed_from: list[str] = field(default_factory=list)
    rule: str = ""
    applies_when: list[str] = field(default_factory=list)
    avoid_when: list[str] = field(default_factory=list)
    confidence: float = 0.0
    model_fit: list[str] = field(default_factory=list)
    promotion_reason: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Pattern:
        return cls(**d)
