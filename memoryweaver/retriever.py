"""Source-aware verified retriever.

Implements retrieval filtering based on source credibility. The core
rule: assistant-generated content that has never been externally
verified is excluded from retrieval by default, preventing the
"self-pollution loop" where an LLM's fabricated answers become
retrievable "knowledge."
"""

from __future__ import annotations

from memoryweaver.schema import MemoryItem, Layer, Source, Status
from memoryweaver.store import MemoryStore


class VerifiedRetriever:
    """Retrieve memories with source-aware credibility weighting.

    SOURCE_WEIGHT maps each source to a retrieval multiplier:

        user      1.0 — direct human feedback, always trusted
        terminal  1.0 — command output, objective truth
        tool      0.9 — tool result, slightly below raw terminal
        web       0.6 — external source, unverified locally
        composer  0.5 — pattern composition, inferred
        assistant 0.0 — LLM output, excluded unless verified by use

    Usage:
        retriever = VerifiedRetriever(store)
        results = retriever.search("Codex subscription WSL")
        # Only verified or externally-grounded memories returned.
    """

    SOURCE_WEIGHT: dict[Source, float] = {
        Source.USER:      1.0,
        Source.TERMINAL:  1.0,
        Source.TOOL:      0.9,
        Source.WEB:       0.6,
        Source.COMPOSER:  0.5,
        Source.ASSISTANT: 0.0,
        Source.FILE:      0.6,
        Source.SYNTHETIC: 0.0,
        Source.UNKNOWN:   0.2,
    }

    # Minimum combined score (source_weight * confidence) to include.
    MIN_SCORE = 0.05

    def __init__(self, store: MemoryStore):
        self._store = store

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        limit: int = 10,
        include_unverified: bool = False,
        threshold: float = 0.25,
    ) -> list[MemoryItem]:
        """Search for memories relevant to *query*, filtered by credibility.

        Args:
            query: The search query (uses naive keyword overlap for now).
            limit: Maximum number of results to return.
            include_unverified: If True, include assistant-sourced memories
                with heat > 0 (they were used at least once). Still excludes
                zero-heat assistant memories to prevent virgin fabrications
                from polluting retrieval.

        Returns:
            Sorted list of MemoryItems, best (most credible) first.
        """
        candidates = self._store.find_similar(query, threshold=threshold)

        scored: list[tuple[float, MemoryItem]] = []
        for item in candidates:
            if not self._should_include(item, include_unverified):
                continue

            weight = self.SOURCE_WEIGHT.get(item.source, 0.2)
            # Layer bonus: Layer-3 patterns get a small boost
            layer_bonus = 1.1 if item.layer == Layer.PATTERN else 1.0
            combined = weight * item.confidence * layer_bonus

            # Items that passed _should_include with explicit user request
            # (e.g. heated assistant memories) bypass the minimum score gate.
            passed_gate = (
                combined >= self.MIN_SCORE
                or item.source in (Source.USER, Source.TERMINAL)
                or (
                    include_unverified
                    and item.source == Source.ASSISTANT
                    and item.heat > 0
                )
            )
            if passed_gate:
                scored.append((combined, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:limit]]

    def search_by_tags(
        self,
        tags: list[str],
        match_all: bool = False,
        include_unverified: bool = False,
    ) -> list[MemoryItem]:
        """Tag-based search with the same source filtering as search()."""
        candidates = self._store.find_by_tags(tags, match_all=match_all)
        verified = [
            item
            for item in candidates
            if self._should_include(item, include_unverified)
        ]
        return self._sort_by_credibility(verified)

    def get_verified_context(self, query: str) -> str:
        """Return a single formatted context string of the top verified memories.

        Suitable for injecting into an LLM system prompt.
        """
        results = self.search(query, limit=5)
        if not results:
            return ""

        lines = []
        for i, item in enumerate(results, 1):
            src_label = (
                f"[{item.source.value}]"
                if item.source != Source.ASSISTANT
                else "[unverified]"
            )
            lines.append(
                f"{i}. {src_label} {item.content} "
                f"(confidence={item.confidence}, heat={item.heat})"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _should_include(item: MemoryItem, include_unverified: bool) -> bool:
        """Decide whether a memory item should appear in retrieval results."""
        if item.status in (Status.ARCHIVED, Status.DEPRECATED):
            return False

        # Always include user and terminal sources
        if item.source in (Source.USER, Source.TERMINAL, Source.TOOL):
            return True

        # Always include composer-generated patterns with confidence > 0
        if item.source == Source.COMPOSER and item.confidence > 0:
            return True

        # Web sources: include if they have any confidence
        if item.source in (Source.WEB, Source.FILE) and item.confidence > 0:
            return True

        # Assistant sources: excluded by default
        if item.source == Source.ASSISTANT:
            if include_unverified and item.heat > 0:
                # Was retrieved and used at least once — might have implicit
                # verification through continued task success
                return True
            return False

        # HyDE and other generated evidence may help query expansion, but
        # synthetic text must not be retrieved as factual memory.
        if item.source == Source.SYNTHETIC:
            return False

        # Unknown sources: include only with confidence
        return item.confidence > 0

    def _sort_by_credibility(self, items: list[MemoryItem]) -> list[MemoryItem]:
        """Sort items by source_weight * confidence, descending."""
        scored = [
            (self.SOURCE_WEIGHT.get(item.source, 0.2) * item.confidence, item)
            for item in items
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored]
