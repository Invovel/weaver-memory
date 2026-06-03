"""Deterministic write, promotion, and retrieval policies."""

from __future__ import annotations

from typing import TYPE_CHECKING

from memoryweaver.schema import (
    Layer,
    MemoryItem,
    MemoryType,
    Pattern,
    PatternStatus,
    Polarity,
    Source,
    Status,
)

if TYPE_CHECKING:
    from memoryweaver.evidence import EvidenceLink


class MemoryPolicy:
    """Judge whether a candidate may be stored or promoted."""

    version = "memory-policy-v1"

    def normalize_candidate(self, item: MemoryItem) -> MemoryItem:
        if item.source in (Source.ASSISTANT, Source.SYNTHETIC):
            item.polarity = Polarity.AMBIGUOUS
            item.confidence = min(item.confidence, 0.3)
        return item

    def validate_write(self, item: MemoryItem, *, is_update: bool = False) -> None:
        self.normalize_candidate(item)
        if item.layer == Layer.PATTERN:
            raise ValueError("Layer 3 records must be created through PatternComposer")
        if not is_update and item.layer != Layer.CANDIDATE:
            raise ValueError("new MemoryItem records must start in Layer 1")

    def can_promote_to_layer2(
        self,
        item: MemoryItem,
        evidence_links: list[EvidenceLink],
    ) -> bool:
        if item.layer != Layer.CANDIDATE:
            return False
        if item.status in (Status.ARCHIVED, Status.DEPRECATED):
            return False
        if item.source == Source.USER:
            return (
                item.memory_type == MemoryType.PREFERENCE
                or item.validation_count > 0
                or bool(evidence_links)
            )
        if item.source in (Source.TERMINAL, Source.TOOL):
            return bool(item.evidence.strip()) or bool(evidence_links)
        if item.source in (Source.FILE, Source.WEB):
            return bool(evidence_links) and item.confidence > 0
        return False

    def promote_to_layer2(
        self,
        item: MemoryItem,
        evidence_links: list[EvidenceLink],
    ) -> MemoryItem:
        if not self.can_promote_to_layer2(item, evidence_links):
            raise ValueError(f"memory {item.id} does not satisfy Layer 2 policy")
        item.layer = Layer.ACTIVATED
        item.status = Status.ACTIVATED
        item.mark_updated()
        return item


class RetrievalPolicy:
    """Select memories and patterns that may enter query context."""

    version = "retrieval-policy-v1"
    SOURCE_WEIGHT: dict[Source, float] = {
        Source.USER: 1.0,
        Source.TERMINAL: 1.0,
        Source.TOOL: 0.9,
        Source.FILE: 0.6,
        Source.WEB: 0.6,
        Source.COMPOSER: 0.5,
        Source.ASSISTANT: 0.0,
        Source.SYNTHETIC: 0.0,
        Source.UNKNOWN: 0.0,
    }

    @staticmethod
    def _scope_matches(item_scope: str, query_scope: str) -> bool:
        return item_scope == "global" or item_scope == query_scope

    def should_include(
        self,
        item: MemoryItem,
        scope: str = "project",
        include_unverified: bool = False,
    ) -> bool:
        if item.status in (Status.ARCHIVED, Status.DEPRECATED):
            return False
        if not self._scope_matches(item.scope, scope):
            return False
        if item.source in (Source.USER, Source.TERMINAL, Source.TOOL):
            return True
        if item.source in (Source.FILE, Source.WEB):
            return item.confidence > 0
        if item.source == Source.ASSISTANT:
            return include_unverified and item.heat > 0
        return False

    def score(self, item: MemoryItem) -> float:
        return self.SOURCE_WEIGHT.get(item.source, 0.0) * item.confidence

    def should_include_pattern(self, pattern: Pattern, scope: str = "project") -> bool:
        return (
            pattern.status in (PatternStatus.PROVISIONAL, PatternStatus.STABLE)
            and pattern.freshness.value != "expired"
            and self._scope_matches(pattern.scope, scope)
        )
