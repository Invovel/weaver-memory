"""External benchmark adapter layer for MemoryWeaver."""

from memoryweaver.external.adapters import (
    adapt_external_record,
    build_candidate_memories,
    build_context_capsules,
    external_episode_to_raw_spans,
)
from memoryweaver.external.schema import ExternalEpisode, ExternalQuery, ExternalTurn
from memoryweaver.external.longmemeval_v2 import (
    build_lme_v2_external_episodes,
    build_lme_v2_external_records,
    default_lme_v2_root,
    download_lme_v2_snapshot,
    is_lme_v2_snapshot_root,
    resolve_lme_v2_root,
)

__all__ = [
    "ExternalEpisode",
    "ExternalQuery",
    "ExternalTurn",
    "adapt_external_record",
    "build_candidate_memories",
    "build_context_capsules",
    "external_episode_to_raw_spans",
    "build_lme_v2_external_episodes",
    "build_lme_v2_external_records",
    "default_lme_v2_root",
    "download_lme_v2_snapshot",
    "is_lme_v2_snapshot_root",
    "resolve_lme_v2_root",
]
