"""MemoryWeaver - Feedback-Calibrated Memory Harness for Long-Lived AI Agents."""

__version__ = "0.1.0"

from memoryweaver.schema import MemoryItem, Polarity, Layer, Status, MemoryType, Freshness, Source, Pattern
from memoryweaver.store import MemoryStore
from memoryweaver.scorer import MemoryScorer
from memoryweaver.extractor import EventDetector, Event, EventType, FeedbackClassifier
from memoryweaver.router import ModeRouter, InferenceMode, RouteDecision
from memoryweaver.retriever import VerifiedRetriever
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
    "MemoryType",
    "Freshness",
    "Source",
    # store & scoring
    "MemoryStore",
    "MemoryScorer",
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
    # contradiction
    "ContradictionResolver",
    "ConflictResult",
    "Severity",
    "Relation",
]
