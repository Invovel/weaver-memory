"""Canonical external benchmark records for MemoryWeaver v0.6.4.

The external layer sits before MemoryItem. External rows become
ExternalEpisode records, then RawSpan and ContextCapsule objects. They do not
write verified memory, promote memory, or mutate Layer 3.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from memoryweaver.context_schema import ContentType
from memoryweaver.schema import Source


@dataclass
class ExternalTurn:
    """One turn or observation from an external benchmark episode."""

    id: str
    role: str
    content: str
    source: Source = Source.UNKNOWN
    content_type: ContentType = ContentType.TEXT
    timestamp: str = ""
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.source, Source):
            self.source = Source(self.source)
        if not isinstance(self.content_type, ContentType):
            self.content_type = ContentType(self.content_type)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source"] = self.source.value
        data["content_type"] = self.content_type.value
        return data


@dataclass
class ExternalQuery:
    """Question, task, or final probe attached to an external episode."""

    id: str
    query: str
    answer: str = ""
    tags: list[str] = field(default_factory=list)
    expected_evidence_tags: list[str] = field(default_factory=list)
    signal_types: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExternalEpisode:
    """A normalized row from a benchmark dataset."""

    dataset_id: str
    source_repo: str
    split: str
    episode_id: str
    turns: list[ExternalTurn] = field(default_factory=list)
    queries: list[ExternalQuery] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["turns"] = [turn.to_dict() for turn in self.turns]
        data["queries"] = [query.to_dict() for query in self.queries]
        return data
