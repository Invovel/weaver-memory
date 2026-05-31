"""Event detector and feedback classifier.

Determines WHAT to tag (event detection) and HOW to tag it (polarity
classification). Uses rule-based keyword matching initially; designed
to be extended with LLM-based classification in later phases.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class EventType(str, Enum):
    """Broad category of a harness-observed event."""

    USER_CORRECTION = "user_correction"
    USER_CONFIRMATION = "user_confirmation"
    USER_PREFERENCE = "user_preference"
    TOOL_SUCCESS = "tool_success"
    TOOL_FAILURE = "tool_failure"
    ASSUMPTION_INVALIDATED = "assumption_invalidated"
    UNUSUAL_ENV = "unusual_env"
    REASONING_REVERSAL = "reasoning_reversal"
    ROUTINE_EXECUTION = "routine_execution"
    CHITCHAT = "chitchat"
    UNKNOWN = "unknown"


@dataclass
class Event:
    """A harness-observed event before memory extraction."""

    type: EventType
    text: str
    source: str = "unknown"
    metadata: dict = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# Keyword detection tables
# ---------------------------------------------------------------------------

# Positive feedback signals
_POSITIVE_ZH = [
    "对", "可以了", "解决了", "好的", "没问题", "就这样", "正确",
    "没问题了", "搞定了", "行了", "管用", "好使", "完美", "谢谢",
    "正是", "没错", "可以的", "成功了", "通过了",
]
_POSITIVE_EN = [
    "works", "fixed", "solved", "correct", "exactly", "perfect",
    "thanks", "that's it", "got it", "working now", "resolved",
    "that did it", "nice", "great", "awesome",
]

# Negative feedback signals
_NEGATIVE_ZH = [
    "不对", "还是报错", "不是这个", "错了", "没用", "不行",
    "没解决", "仍然失败", "还是一样", "不管用", "不好使",
    "没效果", "依旧报错", "依然失败", "不是我要的",
]
_NEGATIVE_EN = [
    "wrong", "doesn't work", "still fails", "not this", "incorrect",
    "didn't help", "didn't fix", "still broken", "no", "nope",
    "that's wrong", "not working", "error persists", "still error",
    "not what I meant",
]

# Ambiguous / uncertain signals
_AMBIGUOUS_ZH = [
    "可能", "不确定", "也许", "好像", "似乎", "大概", "或许",
    "不一定", "不太确定", "说不准",
]
_AMBIGUOUS_EN = [
    "maybe", "perhaps", "might", "could be", "not sure",
    "possibly", "uncertain", "probably", "seems like",
    "I think", "might be",
]


class FeedbackClassifier:
    """Rule-based classifier for user feedback polarity.

    Usage:
        fc = FeedbackClassifier()
        polarity, confidence = fc.classify("不对，还是报错")
        # -> (Polarity.NEGATIVE, 0.85)
    """

    def classify(self, text: str) -> tuple[str, float]:
        """Classify text and return (polarity, confidence).

        Returns:
            A (polarity_str, confidence) tuple.  Polarity is one of
            "positive", "negative", "ambiguous", or "neutral".
        """
        if not text or not text.strip():
            return ("neutral", 0.5)

        text_lower = text.lower().strip()
        scores: dict[str, float] = {
            "positive": 0.0,
            "negative": 0.0,
            "ambiguous": 0.0,
        }

        # Score each polarity zone
        scores["positive"] = self._match_score(text_lower, _POSITIVE_ZH, _POSITIVE_EN)
        scores["negative"] = self._match_score(text_lower, _NEGATIVE_ZH, _NEGATIVE_EN)
        scores["ambiguous"] = self._match_score(
            text_lower, _AMBIGUOUS_ZH, _AMBIGUOUS_EN
        )

        best = max(scores, key=scores.get)  # type: ignore[arg-type]
        best_score = scores[best]

        if best_score == 0.0:
            return ("neutral", 0.5)

        # Confidence: ratio of best score to sum of all scores
        total = sum(scores.values())
        confidence = round(best_score / total, 2) if total > 0 else 0.5
        confidence = min(confidence, 0.99)

        return (best, confidence)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _match_score(text: str, zh_list: list[str], en_list: list[str]) -> float:
        score = 0.0
        for kw in zh_list:
            if kw in text:
                score += 1.0
        for kw in en_list:
            # English keywords: use word-boundary match for short words
            if len(kw.split()) == 1 and len(kw) <= 5:
                if re.search(rf"\b{re.escape(kw)}\b", text):
                    score += 1.0
            else:
                if kw in text:
                    score += 1.0
        return score


class EventDetector:
    """Detects memory-worthy events from raw text.

    Applies the three-question rule:
      1. Will this help me avoid a wrong path next time?
      2. Will this mislead me if it goes stale?
      3. Is this a "result" or just "process"?

    MUST_TAG events are always captured.
    MAYBE_TAG events are captured only if non-obvious (not already stored).
    SKIP events are discarded.
    """

    MUST_TAG = {
        EventType.USER_CORRECTION,
        EventType.USER_CONFIRMATION,
        EventType.USER_PREFERENCE,
        EventType.TOOL_FAILURE,
        EventType.ASSUMPTION_INVALIDATED,
    }

    MAYBE_TAG = {
        EventType.TOOL_SUCCESS,
        EventType.UNUSUAL_ENV,
        EventType.REASONING_REVERSAL,
    }

    SKIP = {
        EventType.ROUTINE_EXECUTION,
        EventType.CHITCHAT,
    }

    def __init__(self, classifier: Optional[FeedbackClassifier] = None):
        self.classifier = classifier or FeedbackClassifier()

    def detect(self, text: str, source: str = "unknown") -> Optional[Event]:
        """Analyze text and return an Event if memory-worthy, else None."""
        event_type = self._classify_event(text)
        if event_type in self.SKIP:
            return None
        return Event(type=event_type, text=text, source=source)

    def should_tag(self, event: Event) -> bool:
        """Decide whether this event should become a memory."""
        if event.type in self.MUST_TAG:
            return True
        if event.type in self.SKIP:
            return False
        # MAYBE_TAG — caller should check store for duplicates
        return True

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _classify_event(self, text: str) -> EventType:
        text_lower = text.lower()

        # Check for corrections (strong signal — check first)
        if self._matches(text_lower, _NEGATIVE_ZH, _NEGATIVE_EN):
            return EventType.USER_CORRECTION
        if self._matches(text_lower, _POSITIVE_ZH, _POSITIVE_EN):
            return EventType.USER_CONFIRMATION

        # Check for ambiguous
        if self._matches(text_lower, _AMBIGUOUS_ZH, _AMBIGUOUS_EN):
            return EventType.REASONING_REVERSAL

        # Check for tool failure / success keywords
        if any(kw in text_lower for kw in ["error", "failed", "fail", "报错", "失败"]):
            return EventType.TOOL_FAILURE
        if any(kw in text_lower for kw in ["success", "成功", "passed", "通过"]):
            return EventType.TOOL_SUCCESS

        # Heuristic: short text with question mark → user preference
        if len(text) < 100 and "?" in text:
            return EventType.USER_PREFERENCE

        # Heuristic: unusual env keywords
        env_keywords = ["wsl", "docker", "windows", "macos", "linux"]
        if any(kw in text_lower for kw in env_keywords):
            return EventType.UNUSUAL_ENV

        return EventType.UNKNOWN

    @staticmethod
    def _matches(text: str, zh_list: list[str], en_list: list[str]) -> bool:
        for kw in zh_list:
            if kw in text:
                return True
        for kw in en_list:
            if len(kw.split()) == 1 and len(kw) <= 5:
                if re.search(rf"\b{re.escape(kw)}\b", text):
                    return True
            else:
                if kw in text:
                    return True
        return False
