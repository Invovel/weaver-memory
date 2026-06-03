"""Source-aware verified retriever.

Implements retrieval filtering based on source credibility. The core
rule: assistant-generated content that has never been externally
verified is excluded from retrieval by default, preventing the
"self-pollution loop" where an LLM's fabricated answers become
retrievable "knowledge."
"""

from __future__ import annotations

from memoryweaver.policy import RetrievalPolicy
from memoryweaver.schema import MemoryItem, Source
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

    SOURCE_WEIGHT = RetrievalPolicy.SOURCE_WEIGHT

    # Minimum combined score (source_weight * confidence) to include.
    MIN_SCORE = 0.05

    def __init__(
        self,
        store: MemoryStore,
        policy: RetrievalPolicy | None = None,
    ):
        self._store = store
        self._policy = policy or RetrievalPolicy()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        limit: int = 10,
        include_unverified: bool = False,
        threshold: float = 0.25,
        scope: str = "project",
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
            if not self._policy.should_include(item, scope, include_unverified):
                continue

            combined = self._policy.score(item)

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
        scope: str = "project",
    ) -> list[MemoryItem]:
        """Tag-based search with the same source filtering as search()."""
        candidates = self._store.find_by_tags(tags, match_all=match_all)
        verified = [
            item
            for item in candidates
            if self._policy.should_include(item, scope, include_unverified)
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

    def _sort_by_credibility(self, items: list[MemoryItem]) -> list[MemoryItem]:
        """Sort items by source_weight * confidence, descending."""
        scored = [
            (self._policy.score(item), item)
            for item in items
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored]
