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
from memoryweaver.retriever import VerifiedRetriever
from memoryweaver.composer import PatternStore
from memoryweaver.policy import RetrievalPolicy
from memoryweaver.schema import Pattern, PatternStatus
from memoryweaver.store import token_jaccard


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
    matched_patterns: list[Pattern] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
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

    def __init__(
        self,
        store: MemoryStore,
        retriever: Optional[VerifiedRetriever] = None,
        pattern_store: Optional[PatternStore] = None,
        retrieval_policy: Optional[RetrievalPolicy] = None,
    ):
        self._store = store
        self._policy = retrieval_policy or RetrievalPolicy()
        self._retriever = retriever or VerifiedRetriever(store, self._policy)
        self._patterns = pattern_store

    def route(self, query: str, scope: str = "project") -> RouteDecision:
        """Analyze query against stored memory and return a mode decision."""
        similar = self._retriever.search(
            query,
            limit=max(self._store.count(), 10),
            threshold=self.VERIFY_THRESHOLD,
            scope=scope,
        )
        patterns = (
            self._patterns.search(
                query,
                scope=scope,
                limit=10,
                threshold=self.VERIFY_THRESHOLD,
            )
            if self._patterns
            else []
        )

        if not similar and not patterns:
            return RouteDecision(
                mode=InferenceMode.THINKING,
                reason="No similar prior memory found - first encounter.",
                matched_items=[],
                matched_patterns=[],
                confidence=0.9,
            )

        stable_patterns = [
            pattern for pattern in patterns
            if pattern.status == PatternStatus.STABLE
            and pattern.freshness != Freshness.EXPIRED
            and pattern.confidence >= 0.7
        ]

        memory_sim = max(
            (token_jaccard(query, item.content) for item in similar),
            default=0.0,
        )
        pattern_sim = max(
            (token_jaccard(query, pattern.rule) for pattern in patterns),
            default=0.0,
        )
        best_sim = max(memory_sim, pattern_sim)
        warnings = [
            f"legacy Layer-3 MemoryItem ignored for fast routing: {item.id}"
            for item in similar
            if item.layer == Layer.PATTERN or item.legacy_pattern
        ]

        # Fast route
        if pattern_sim >= self.FAST_THRESHOLD and stable_patterns:
            return RouteDecision(
                mode=InferenceMode.FAST,
                reason=f"High-confidence Layer-3 pattern matched (sim={best_sim:.2f}).",
                matched_items=similar[:5],
                matched_patterns=stable_patterns[:5],
                warnings=warnings,
                confidence=min(pattern_sim, 0.95),
            )

        # Fast + Verify route
        if best_sim >= self.VERIFY_THRESHOLD or patterns:
            ambiguous_count = sum(
                1 for m in similar if m.polarity.value == "ambiguous"
            )
            if ambiguous_count >= self.AMBIGUOUS_LIMIT:
                return RouteDecision(
                    mode=InferenceMode.FAST_VERIFY,
                    reason=(
                        f"Similar memories found (sim={best_sim:.2f}) "
                        f"but {ambiguous_count} ambiguous signals - verify recommended."
                    ),
                    matched_items=similar[:5],
                    matched_patterns=patterns[:5],
                    warnings=warnings,
                    confidence=0.6,
                )
            return RouteDecision(
                mode=InferenceMode.FAST_VERIFY,
                reason=(
                    f"Similar memories found (sim={best_sim:.2f}) "
                    "but no high-confidence Layer-3 pattern - verify recommended."
                ),
                matched_items=similar[:5],
                matched_patterns=patterns[:5],
                warnings=warnings,
                confidence=0.7,
            )

        # Default: think
        return RouteDecision(
            mode=InferenceMode.THINKING,
            reason=f"Similarity too low for fast path (best sim={best_sim:.2f}).",
            matched_items=similar[:5],
            matched_patterns=patterns[:5],
            warnings=warnings,
            confidence=0.8,
        )
