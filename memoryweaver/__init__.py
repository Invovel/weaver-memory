"""MemoryWeaver - Feedback-Calibrated Memory Harness for Long-Lived AI Agents."""

__version__ = "0.2.0"

from memoryweaver.schema import (
    MemoryItem,
    Polarity,
    Layer,
    Status,
    PatternStatus,
    MemoryType,
    Freshness,
    Source,
    Pattern,
)
from memoryweaver.store import MemoryStore, MemoryWorkspace, tokenize_text, token_jaccard
from memoryweaver.scorer import MemoryScorer
from memoryweaver.extractor import EventDetector, Event, EventType, FeedbackClassifier
from memoryweaver.router import ModeRouter, InferenceMode, RouteDecision
from memoryweaver.retriever import VerifiedRetriever
from memoryweaver.policy import MemoryPolicy, RetrievalPolicy
from memoryweaver.evidence import EvidenceNode, EvidenceLink, EvidencePacket, EvidenceRelation, EvidenceStore
from memoryweaver.composer import PatternStore, PatternComposer
from memoryweaver.contradiction import (
    ContradictionResolver,
    ConflictResult,
    Severity,
    Relation,
)

__all__ = [
    # schema
    "MemoryItem",
    "Pattern",
    "Polarity",
    "Layer",
    "Status",
    "PatternStatus",
    "MemoryType",
    "Freshness",
    "Source",
    # store & scoring
    "MemoryStore",
    "MemoryWorkspace",
    "MemoryScorer",
    "tokenize_text",
    "token_jaccard",
    # extraction
    "EventDetector",
    "Event",
    "EventType",
    "FeedbackClassifier",
    # routing
    "ModeRouter",
    "InferenceMode",
    "RouteDecision",
    # retrieval
    "VerifiedRetriever",
    "MemoryPolicy",
    "RetrievalPolicy",
    "EvidenceNode",
    "EvidenceLink",
    "EvidencePacket",
    "EvidenceRelation",
    "EvidenceStore",
    "PatternStore",
    "PatternComposer",
    # contradiction
    "ContradictionResolver",
    "ConflictResult",
    "Severity",
    "Relation",
]
