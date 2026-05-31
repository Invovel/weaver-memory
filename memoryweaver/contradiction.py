"""Contradiction detection and resolution.

When new memories conflict with existing verified knowledge, the
ContradictionResolver decides whether to silently record the conflict,
warn the agent, or block execution entirely until the user resolves it.

This module implements the three-tier severity model discussed in the
MemoryWeaver design:

  L1 (SILENT) — both claims are unverified → record, don't interrupt
  L2 (WARN)   — unverified vs possibly-stale verified → note, proceed cautiously
  L3 (BLOCK)  — verified fact or user preference contradicted → stop, ask user
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from memoryweaver.schema import MemoryItem, Polarity, MemoryType, Freshness


class Severity(str, Enum):
    """How the resolver should handle a contradiction.

    SILENT — Record the conflict internally, do not interrupt the agent.
    WARN   — Downgrade confidence on the new claim and surface a caveat.
    BLOCK  — Stop execution immediately. The agent must ask the user
             before proceeding. This is the safety default for verified
             knowledge being overturned.
    """

    SILENT = "silent"
    WARN = "warn"
    BLOCK = "block"


class Relation(str, Enum):
    """The relationship between two conflicting memory items."""

    CONTRADICTS = "contradicts"            # Direct conflict
    SUPERSEDES = "supersedes"              # New evidence replaces old
    MUTUALLY_AMBIGUOUS = "mutually_ambiguous"  # Both unverified, both kept
    ENVIRONMENT_CHANGE = "environment_change"  # Both may be true at different times


@dataclass
class ConflictResult:
    """The outcome of a contradiction check."""

    severity: Severity
    reason: str
    action: str = "accept"  # accept | demote | block
    demote_confidence_to: float = 0.0
    relation: Relation = Relation.CONTRADICTS
    conflicting_id: str = ""


class ContradictionResolver:
    """Decide what to do when a new memory conflicts with stored knowledge.

    Core rules (ordered by priority — first match wins):

    1. Both unverified (assistant/assistant or ambiguous/ambiguous)
       → SILENT, keep both, mark as mutually_ambiguous.

    2. New claim contradicts a user-stated PREFERENCE that is STABLE
       → BLOCK. Preferences are sacred.

    3. New claim contradicts a terminal-verified fact with high confidence
       and STABLE freshness → BLOCK. Verified > unverified.

    4. New claim contradicts old verified knowledge that may be stale
       (VOLATILE or UNKNOWN freshness) → WARN. Proceed with annotation.

    5. New claim contradicts moderate-confidence verified knowledge
       → WARN. Err on the side of caution.

    Usage:
        resolver = ContradictionResolver()
        result = resolver.resolve(new_memory, existing_memory)
        if result.severity == Severity.BLOCK:
            ask_user_for_clarification(result.reason)
    """

    # Confidence threshold above which a verified memory is considered
    # strong enough to BLOCK on contradiction.
    STRONG_CONFIDENCE = 0.8

    # Confidence gap: if existing.confidence exceeds new.confidence by
    # this margin, the existing source is considered dominant.
    DOMINANCE_GAP = 0.3

    def resolve(
        self,
        new_item: MemoryItem,
        existing: MemoryItem,
    ) -> ConflictResult:
        """Compare a new memory against an existing one and return a decision.

        Args:
            new_item: The incoming (possibly contradictory) memory.
            existing: The already-stored memory it conflicts with.

        Returns:
            A ConflictResult with severity and recommended action.
        """
        # ── Rule 1: Both unverified ──────────────────────────────
        if self._both_unverified(new_item, existing):
            return ConflictResult(
                severity=Severity.SILENT,
                reason=(
                    "Two unverified claims disagree — "
                    "both retained pending user or terminal verification."
                ),
                action="accept",
                relation=Relation.MUTUALLY_AMBIGUOUS,
                conflicting_id=existing.id,
            )

        # ── Rule 2: User preference is sacred ────────────────────
        if self._is_user_preference(existing):
            return ConflictResult(
                severity=Severity.BLOCK,
                reason=(
                    f"New claim contradicts user-stated preference: "
                    f"'{self._truncate(existing.content)}'. "
                    f"Cannot override without explicit user confirmation."
                ),
                action="block",
                relation=Relation.CONTRADICTS,
                conflicting_id=existing.id,
            )

        # ── Rule 3: Strong verified fact ─────────────────────────
        if self._is_strong_verified(existing):
            return ConflictResult(
                severity=Severity.BLOCK,
                reason=(
                    f"New claim contradicts terminal-verified memory "
                    f"(confidence={existing.confidence}): "
                    f"'{self._truncate(existing.content)}'. "
                    f"Ask user whether the environment or requirement has changed."
                ),
                action="block",
                relation=Relation.CONTRADICTS,
                conflicting_id=existing.id,
            )

        # ── Rule 4: Verified but possibly stale ──────────────────
        if self._is_verified_but_stale(existing):
            return ConflictResult(
                severity=Severity.WARN,
                reason=(
                    f"New claim conflicts with possibly-outdated memory "
                    f"(freshness={existing.freshness.value}): "
                    f"'{self._truncate(existing.content)}'. "
                    f"Proceeding with reduced confidence. "
                    f"Recommend confirming with user."
                ),
                action="demote",
                demote_confidence_to=0.1,
                relation=Relation.ENVIRONMENT_CHANGE,
                conflicting_id=existing.id,
            )

        # ── Rule 5: Verified but moderate confidence ─────────────
        if self._is_verified_moderate(existing):
            return ConflictResult(
                severity=Severity.WARN,
                reason=(
                    f"Unverified claim conflicts with verified memory "
                    f"(confidence={existing.confidence}): "
                    f"'{self._truncate(existing.content)}'. "
                    f"Recommend confirming with user before acting."
                ),
                action="demote",
                demote_confidence_to=0.2,
                relation=Relation.CONTRADICTS,
                conflicting_id=existing.id,
            )

        # ── Fallback: warn ───────────────────────────────────────
        return ConflictResult(
            severity=Severity.WARN,
            reason=(
                "Memory conflict detected — "
                "recommend user verification before proceeding."
            ),
            action="demote",
            demote_confidence_to=0.3,
            relation=Relation.CONTRADICTS,
            conflicting_id=existing.id,
        )

    # ------------------------------------------------------------------
    # Severity conveniences
    # ------------------------------------------------------------------

    def needs_user_input(self, result: ConflictResult) -> bool:
        """True if this conflict MUST be resolved by the user."""
        return result.severity == Severity.BLOCK

    def should_warn(self, result: ConflictResult) -> bool:
        """True if the agent should surface a caveat to the user."""
        return result.severity in (Severity.WARN, Severity.BLOCK)

    # ------------------------------------------------------------------
    # Internal classification helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _both_unverified(new_item: MemoryItem, existing: MemoryItem) -> bool:
        """True if both memories lack external verification."""
        # assistant vs assistant
        if new_item.source == "assistant" and existing.source == "assistant":
            return True
        # Both are ambiguous hypotheses
        if (new_item.polarity == Polarity.AMBIGUOUS
                and existing.polarity == Polarity.AMBIGUOUS):
            return True
        # New is assistant, existing is composer (both unverified)
        if new_item.source == "assistant" and existing.source == "composer":
            return True
        return False

    @staticmethod
    def _is_user_preference(item: MemoryItem) -> bool:
        """True if item is a user-stated preference that hasn't expired."""
        return (
            item.source == "user"
            and item.memory_type == MemoryType.PREFERENCE
            and item.freshness != Freshness.EXPIRED
        )

    def _is_strong_verified(self, item: MemoryItem) -> bool:
        """True if item is externally verified, high confidence, and stable."""
        return (
            item.source in ("terminal", "user", "tool")
            and item.confidence >= self.STRONG_CONFIDENCE
            and item.freshness == Freshness.STABLE
        )

    def _is_verified_but_stale(self, item: MemoryItem) -> bool:
        """True if item was verified but may be outdated."""
        return (
            item.source in ("terminal", "user", "tool")
            and item.freshness in (Freshness.VOLATILE, Freshness.UNKNOWN)
        )

    def _is_verified_moderate(self, item: MemoryItem) -> bool:
        """True if item is verified but confidence is below the BLOCK threshold."""
        return (
            item.source in ("terminal", "user", "tool")
            and item.confidence < self.STRONG_CONFIDENCE
            and item.freshness != Freshness.EXPIRED
        )

    @staticmethod
    def _truncate(text: str, length: int = 80) -> str:
        if len(text) <= length:
            return text
        return text[:length] + "..."
