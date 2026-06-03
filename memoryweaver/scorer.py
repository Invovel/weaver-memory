"""Memory scoring — heat, confidence, and promotion logic.

This module records lifecycle signals for Layer 1 and Layer 2 memories.
Layer 3 records are created only by PatternComposer.
"""

from __future__ import annotations

from memoryweaver.schema import MemoryItem, Layer, Status, Freshness, Polarity, MemoryType


class MemoryScorer:
    """Applies scoring rules and decides promotion / deprecation.

    Default thresholds (can be overridden):
        HEAT_PROMOTE       — heat >= this triggers layer review
        SUCCESS_BIAS       — success_score must exceed correction_score by this ratio
        CORRECTION_DEPRECATE — correction_score >= this triggers deprecation
    """

    HEAT_PROMOTE = 3
    SUCCESS_BIAS = 1.0  # success_score > correction_score
    CORRECTION_DEPRECATE = 2.0

    def __init__(
        self,
        heat_promote: int = 3,
        success_bias: float = 1.0,
        correction_deprecate: float = 2.0,
    ):
        self.HEAT_PROMOTE = heat_promote
        self.SUCCESS_BIAS = success_bias
        self.CORRECTION_DEPRECATE = correction_deprecate

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_access(self, item: MemoryItem) -> None:
        """Called every time a memory is retrieved."""
        item.record_access()

    def record_success(self, item: MemoryItem) -> None:
        """Called when a memory contributed to a successful outcome."""
        item.success_score += 1.0
        self._recalc_confidence(item)
        item.record_use()
        item.record_validation()

    def record_correction(self, item: MemoryItem) -> None:
        """Called when a memory led to a wrong outcome or user corrected it."""
        item.correction_score += 1.0
        self._recalc_confidence(item)
        item.record_use()
        item.record_validation()

    def evaluate(self, item: MemoryItem) -> Status:
        """Evaluate a memory and return its recommended status.

        This is the core decision function:
          - High corrections → deprecate (avoidance_rule)
          - Long unused → decay
          - Otherwise stay
        """
        # Deprecation check
        if item.correction_score >= self.CORRECTION_DEPRECATE:
            item.status = Status.DEPRECATED
            item.memory_type = MemoryType.AVOIDANCE_RULE
            return item.status

        # Freshness decay
        if item.heat == 0 and item.freshness == Freshness.UNKNOWN:
            item.freshness = Freshness.VOLATILE

        return item.status

    def recommend_layer(self, item: MemoryItem) -> Layer:
        """Return the recommended layer for this memory."""
        if (
            item.layer == Layer.ACTIVATED
            or item.heat >= 1
            or item.validation_count >= 1
        ):
            return Layer.ACTIVATED
        return Layer.CANDIDATE

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _recalc_confidence(self, item: MemoryItem) -> None:
        total = item.success_score + item.correction_score
        if total == 0:
            item.confidence = 0.0
        else:
            item.confidence = item.success_score / total
            item.confidence = round(item.confidence, 2)

    def recompute_all(self, items: list[MemoryItem]) -> None:
        """Batch-recompute confidence for a list of items."""
        for item in items:
            self._recalc_confidence(item)
            self.evaluate(item)
