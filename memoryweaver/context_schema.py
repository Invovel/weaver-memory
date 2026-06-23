"""Context capsule schema for reversible RAW-context compression.

ContextCapsule sits before Layer 1. It is not memory, not evidence, and cannot
promote anything. It only provides compact, source-preserving context with a
raw_ref_id back to the full RawSpan.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from memoryweaver.schema import Source


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ContentType(str, Enum):
    TERMINAL_LOG = "terminal_log"
    TOOL_JSON = "tool_json"
    CONVERSATION_TURN = "conversation_turn"
    CODE_PATCH = "code_patch"
    TRACE_RECORD = "trace_record"
    TEXT = "text"


@dataclass
class RawSpan:
    id: str = field(default_factory=lambda: f"raw_{uuid.uuid4().hex[:12]}")
    content: str = ""
    content_type: ContentType = ContentType.TEXT
    source: Source = Source.UNKNOWN
    timestamp: str = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)
    content_hash: str = ""
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not isinstance(self.content_type, ContentType):
            self.content_type = ContentType(self.content_type)
        if not isinstance(self.source, Source):
            self.source = Source(self.source)
        if not self.content_hash:
            self.content_hash = hashlib.sha256(
                self.content.encode("utf-8")
            ).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["content_type"] = self.content_type.value
        data["source"] = self.source.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RawSpan":
        payload = dict(data)
        payload["content_type"] = ContentType(
            payload.get("content_type", ContentType.TEXT.value)
        )
        payload["source"] = Source(payload.get("source", Source.UNKNOWN.value))
        return cls(**payload)


@dataclass
class ContextCapsule:
    id: str = field(default_factory=lambda: f"cap_{uuid.uuid4().hex[:12]}")
    raw_ref_id: str = ""
    content_type: ContentType = ContentType.TEXT
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=utc_now)
    source: Source = Source.UNKNOWN
    compression_method: str = "rule_v1"
    compression_ratio: float = 1.0
    reversible: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not isinstance(self.content_type, ContentType):
            self.content_type = ContentType(self.content_type)
        if not isinstance(self.source, Source):
            self.source = Source(self.source)
        if not self.raw_ref_id:
            raise ValueError("ContextCapsule requires raw_ref_id")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["content_type"] = self.content_type.value
        data["source"] = self.source.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContextCapsule":
        payload = dict(data)
        payload["content_type"] = ContentType(
            payload.get("content_type", ContentType.TEXT.value)
        )
        payload["source"] = Source(payload.get("source", Source.UNKNOWN.value))
        return cls(**payload)


@dataclass
class MarkerEvidenceContext:
    marker_id: str
    required_tags: list[str] = field(default_factory=list)
    required_sources: list[Source] = field(default_factory=list)
    required_time_window: str = ""
    preferred_content_types: list[ContentType] = field(default_factory=list)
    fallback_raw_retrieval: bool = True
    created_at: str = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.required_sources = [
            source if isinstance(source, Source) else Source(source)
            for source in self.required_sources
        ]
        self.preferred_content_types = [
            content_type if isinstance(content_type, ContentType)
            else ContentType(content_type)
            for content_type in self.preferred_content_types
        ]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["required_sources"] = [source.value for source in self.required_sources]
        data["preferred_content_types"] = [
            content_type.value for content_type in self.preferred_content_types
        ]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MarkerEvidenceContext":
        payload = dict(data)
        payload["required_sources"] = [
            Source(source) for source in payload.get("required_sources", [])
        ]
        payload["preferred_content_types"] = [
            ContentType(content_type)
            for content_type in payload.get("preferred_content_types", [])
        ]
        return cls(**payload)
