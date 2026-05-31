"""Adaptive inference mode router.

Decides whether the next agent action should use fast mode,
thinking mode, or fast+verify based on existing memory patterns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from memoryweaver.schema import MemoryItem, Layer, Freshness
from memoryweaver.store import MemoryStore


class InferenceMode(str, Enum):
    """Recommended inference mode for the next agent step."""

    THINKING = "thinking"        # New / uncertain / high-risk
    FAST = "fast"                # Similar / validated / low-risk
    FAST_VERIFY = "fast_verify"  # Known but possibly outdated


@dataclass
class RouteDecision:
    """Result of mode router analysis."""

    mode: InferenceMode
    reason: str
    matched_items: list[MemoryItem] = field(default_factory=list)
    confidence: float = 0.0


class ModeRouter:
    """Routes agent queries to fast, thinking, or fast+verify mode.

    Decision logic (Phase 0: simplified thresholds):
      - sim >= 0.85 + Layer-3 pattern hit + not expired → fast
      - sim 0.5–0.85, or many ambiguous matches → fast + verify
      - otherwise → thinking

    Usage:
        router = ModeRouter(store)
        decision = router.route("Codex CLI subscription error in WSL")
        # -> RouteDecision(mode=FAST_VERIFY, ...)
    """

    FAST_THRESHOLD = 0.85
    VERIFY_THRESHOLD = 0.5
    AMBIGUOUS_LIMIT = 3

    def __init__(self, store: MemoryStore):
        self._store = store

    def route(self, query: str) -> RouteDecision:
        """Analyze query against stored memory and return a mode decision."""
        similar = self._store.find_similar(query, threshold=self.VERIFY_THRESHOLD)

        if not similar:
            return RouteDecision(
                mode=InferenceMode.THINKING,
                reason="No similar prior memory found — first encounter.",
                matched_items=[],
                confidence=0.9,
            )

        # Check for high-confidence Layer-3 pattern match
        high_match = [
            m for m in similar
            if m.layer == Layer.PATTERN
            and m.freshness != Freshness.EXPIRED
            and m.confidence >= 0.7
        ]

        # Compute best similarity (Jaccard from find_similar)
        query_words = set(query.lower().split())
        best_sim = 0.0
        for m in similar:
            item_words = set(m.content.lower().split())
            if item_words:
                sim = len(query_words & item_words) / len(query_words | item_words)
                best_sim = max(best_sim, sim)

        # Fast route
        if best_sim >= self.FAST_THRESHOLD and high_match:
            return RouteDecision(
                mode=InferenceMode.FAST,
                reason=f"High-confidence Layer-3 pattern matched (sim={best_sim:.2f}).",
                matched_items=high_match[:5],
                confidence=min(best_sim, 0.95),
            )

        # Fast + Verify route
        if best_sim >= self.VERIFY_THRESHOLD:
            ambiguous_count = sum(
                1 for m in similar if m.polarity.value == "ambiguous"
            )
            if ambiguous_count >= self.AMBIGUOUS_LIMIT:
                return RouteDecision(
                    mode=InferenceMode.FAST_VERIFY,
                    reason=(
                        f"Similar memories found (sim={best_sim:.2f}) "
                        f"but {ambiguous_count} ambiguous signals — verify recommended."
                    ),
                    matched_items=similar[:5],
                    confidence=0.6,
                )
            return RouteDecision(
                mode=InferenceMode.FAST_VERIFY,
                reason=(
                    f"Similar memories found (sim={best_sim:.2f}) "
                    "but no high-confidence Layer-3 pattern — verify recommended."
                ),
                matched_items=similar[:5],
                confidence=0.7,
            )

        # Default: think
        return RouteDecision(
            mode=InferenceMode.THINKING,
            reason=f"Similarity too low for fast path (best sim={best_sim:.2f}).",
            matched_items=similar[:5],
            confidence=0.8,
        )
