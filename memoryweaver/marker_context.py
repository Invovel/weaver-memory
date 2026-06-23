"""MarkerEvidenceContext helpers for ContextCapsule retrieval."""

from __future__ import annotations

from memoryweaver.context_schema import ContextCapsule, MarkerEvidenceContext
from memoryweaver.context_store import ContextCapsuleStore
from memoryweaver.tag_time_index import TagTimeIndex


def capsules_for_marker_context(
    marker_context: MarkerEvidenceContext,
    capsule_store: ContextCapsuleStore,
    index: TagTimeIndex,
    *,
    limit: int = 10,
) -> list[ContextCapsule]:
    since, until = _parse_window(marker_context.required_time_window)
    capsule_ids = index.search(
        tags=marker_context.required_tags,
        since=since,
        until=until,
        sources=marker_context.required_sources,
        content_types=marker_context.preferred_content_types,
    )
    capsules: list[ContextCapsule] = []
    for capsule_id in capsule_ids[:limit]:
        capsule = capsule_store.get(capsule_id)
        if capsule is not None:
            capsules.append(capsule)
    return capsules


def _parse_window(window: str) -> tuple[str, str]:
    # v0.5.3 benchmark uses explicit ISO windows; natural-language windows are
    # left to a later runtime layer.
    if not window:
        return "", ""
    if ".." in window:
        left, right = window.split("..", 1)
        return left.strip(), right.strip()
    return window.strip(), ""
