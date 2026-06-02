"""Tests for MemoryItem schema and MemoryStore."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from memoryweaver.schema import (
    MemoryItem,
    Pattern,
    Polarity,
    Layer,
    Status,
    MemoryType,
    Freshness,
    Source,
)
from memoryweaver.store import MemoryStore


class TestMemoryItem:
    def test_default_creation(self):
        item = MemoryItem()
        assert item.id.startswith("mem_")
        assert item.layer == Layer.CANDIDATE
        assert item.polarity == Polarity.NEUTRAL
        assert item.status == Status.CANDIDATE
        assert item.heat == 0
        assert item.confidence == 0.0

    def test_custom_creation(self):
        item = MemoryItem(
            polarity=Polarity.NEGATIVE,
            memory_type=MemoryType.FAILED_ATTEMPT,
            content="npm reinstall did not fix the issue",
            tags=["codex", "npm", "failed"],
            source="user",
        )
        assert item.polarity == Polarity.NEGATIVE
        assert item.memory_type == MemoryType.FAILED_ATTEMPT
        assert "codex" in item.tags

    def test_record_access_increments_heat(self):
        item = MemoryItem()
        assert item.heat == 0
        item.record_access()
        assert item.heat == 1
        item.record_access()
        assert item.heat == 2

    def test_mark_updated_does_not_increment_heat(self):
        item = MemoryItem()
        item.mark_updated()
        assert item.heat == 0

    def test_promote_to_next_layer(self):
        item = MemoryItem(layer=Layer.CANDIDATE)
        item.promote()
        assert item.layer == Layer.ACTIVATED
        assert item.status == Status.PROMOTED
        assert item.heat == 0

    def test_promote_to_specific_layer(self):
        item = MemoryItem()
        item.promote(Layer.PATTERN)
        assert item.layer == Layer.PATTERN

    def test_promote_does_not_exceed_layer_3(self):
        item = MemoryItem(layer=Layer.PATTERN)
        item.promote()
        assert item.layer == Layer.PATTERN  # no Layer 4

    def test_deprecate(self):
        item = MemoryItem()
        item.deprecate()
        assert item.status == Status.DEPRECATED
        assert item.heat == 0

    def test_archive(self):
        item = MemoryItem()
        item.archive()
        assert item.status == Status.ARCHIVED
        assert item.heat == 0

    def test_activate(self):
        item = MemoryItem(layer=Layer.CANDIDATE)
        item.activate()
        assert item.layer == Layer.ACTIVATED
        assert item.status == Status.ACTIVATED
        assert item.heat == 0

    def test_serialize_roundtrip(self):
        item = MemoryItem(
            polarity=Polarity.POSITIVE,
            memory_type=MemoryType.SUCCESS_PATH,
            content="检查组织选择后问题解决",
            tags=["codex", "fix"],
            source="user",
            heat=3,
            confidence=0.85,
        )
        d = item.to_dict()
        restored = MemoryItem.from_dict(d)
        assert restored.id == item.id
        assert restored.polarity == item.polarity
        assert restored.content == item.content
        assert restored.heat == item.heat
        assert restored.confidence == item.confidence

    def test_json_roundtrip(self):
        item = MemoryItem(content="test content", tags=["a", "b"])
        json_str = item.to_json()
        restored = MemoryItem.from_json(json_str)
        assert restored.content == "test content"
        assert restored.tags == ["a", "b"]

    def test_created_at_is_set(self):
        item = MemoryItem()
        assert item.created_at
        assert "T" in item.created_at  # ISO format

    def test_source_string_is_normalized_to_enum(self):
        item = MemoryItem(source="terminal")
        assert item.source == Source.TERMINAL

    def test_invalid_source_is_rejected(self):
        with pytest.raises(ValueError):
            MemoryItem(source="not-a-source")

    def test_assistant_source_is_downgraded(self):
        item = MemoryItem(
            source="assistant",
            polarity=Polarity.POSITIVE,
            confidence=1.0,
        )
        assert item.source == Source.ASSISTANT
        assert item.polarity == Polarity.AMBIGUOUS
        assert item.confidence == 0.3

    def test_synthetic_source_is_downgraded(self):
        item = MemoryItem(
            source="synthetic",
            polarity=Polarity.POSITIVE,
            confidence=1.0,
        )
        assert item.source == Source.SYNTHETIC
        assert item.polarity == Polarity.AMBIGUOUS
        assert item.confidence == 0.3

    def test_legacy_assistant_memory_is_downgraded_when_loaded(self):
        raw = MemoryItem().to_dict()
        raw.update({
            "source": "assistant",
            "polarity": "positive",
            "confidence": 0.95,
        })

        restored = MemoryItem.from_dict(raw)

        assert restored.source == Source.ASSISTANT
        assert restored.polarity == Polarity.AMBIGUOUS
        assert restored.confidence == 0.3


class TestPattern:
    def test_default_creation(self):
        p = Pattern()
        assert p.id.startswith("pat_")
        assert p.pattern_type == "diagnostic_rule"

    def test_with_composed_from(self):
        p = Pattern(
            composed_from=["mem_a", "mem_b", "mem_c"],
            rule="If X then Y, avoid Z.",
            confidence=0.9,
        )
        assert len(p.composed_from) == 3
        assert p.confidence == 0.9

    def test_serialize_roundtrip(self):
        p = Pattern(
            composed_from=["mem_1", "mem_2"],
            rule="test rule",
            confidence=0.75,
        )
        d = p.to_dict()
        restored = Pattern.from_dict(d)
        assert restored.id == p.id
        assert restored.rule == "test rule"
        assert restored.confidence == 0.75


class TestMemoryStore:
    @pytest.fixture
    def store(self):
        """Create a store backed by a temp file."""
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(path)  # remove empty file so _load won't see it
        yield MemoryStore(path)
        Path(path).unlink(missing_ok=True)

    def test_add_and_get(self, store):
        item = MemoryItem(content="test")
        store.add(item)
        retrieved = store.get(item.id)
        assert retrieved is not None
        assert retrieved.content == "test"

    def test_get_missing(self, store):
        assert store.get("nonexistent") is None

    def test_update(self, store):
        item = MemoryItem(content="original")
        store.add(item)
        item.content = "updated"
        store.update(item)
        assert store.get(item.id).content == "updated"
        assert item.heat == 0

    def test_update_missing_raises(self, store):
        item = MemoryItem(id="nonexistent", content="x")
        with pytest.raises(KeyError):
            store.update(item)

    def test_delete(self, store):
        item = MemoryItem()
        store.add(item)
        assert store.delete(item.id) is True
        assert store.get(item.id) is None

    def test_delete_missing(self, store):
        assert store.delete("nonexistent") is False

    def test_list_all(self, store):
        store.add(MemoryItem(content="a"))
        store.add(MemoryItem(content="b"))
        assert store.count() == 2
        assert len(store.list_all()) == 2

    def test_find_by_tags_any(self, store):
        store.add(MemoryItem(content="a", tags=["wsl", "codex"]))
        store.add(MemoryItem(content="b", tags=["docker", "python"]))
        store.add(MemoryItem(content="c", tags=["wsl", "python"]))

        results = store.find_by_tags(["wsl"])
        assert len(results) == 2  # a and c

        results = store.find_by_tags(["docker"])
        assert len(results) == 1

    def test_find_by_tags_match_all(self, store):
        store.add(MemoryItem(content="a", tags=["wsl", "codex"]))
        store.add(MemoryItem(content="b", tags=["wsl"]))

        results = store.find_by_tags(["wsl", "codex"], match_all=True)
        assert len(results) == 1

    def test_find_by_polarity(self, store):
        store.add(MemoryItem(polarity=Polarity.POSITIVE))
        store.add(MemoryItem(polarity=Polarity.NEGATIVE))
        store.add(MemoryItem(polarity=Polarity.POSITIVE))

        assert len(store.find_by_polarity(Polarity.POSITIVE)) == 2
        assert len(store.find_by_polarity(Polarity.NEGATIVE)) == 1
        assert len(store.find_by_polarity(Polarity.AMBIGUOUS)) == 0

    def test_find_by_layer(self, store):
        store.add(MemoryItem(layer=Layer.CANDIDATE))
        store.add(MemoryItem(layer=Layer.ACTIVATED))
        store.add(MemoryItem(layer=Layer.CANDIDATE))

        assert len(store.find_by_layer(Layer.CANDIDATE)) == 2
        assert len(store.find_by_layer(Layer.ACTIVATED)) == 1

    def test_find_similar(self, store):
        store.add(MemoryItem(content="Codex CLI subscription load failed in WSL"))
        store.add(MemoryItem(content="Docker build error on macOS"))
        store.add(MemoryItem(content="npm install permission denied"))

        results = store.find_similar("Codex CLI subscription error in WSL", threshold=0.5)
        assert len(results) >= 1
        # The Codex entry should be first
        assert "codex" in results[0].content.lower()

    def test_persistence_across_instances(self):
        """Verify memory survives store re-open."""
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(path)  # remove empty file

        # Write
        s1 = MemoryStore(path)
        s1.add(MemoryItem(content="persistent", tags=["test"]))
        assert s1.count() == 1

        # Read back
        s2 = MemoryStore(path)
        assert s2.count() == 1
        items = s2.find_by_tags(["test"])
        assert len(items) == 1
        assert items[0].content == "persistent"

        Path(path).unlink(missing_ok=True)


class TestScorer:
    from memoryweaver.scorer import MemoryScorer

    def test_record_access(self):
        from memoryweaver.scorer import MemoryScorer
        scorer = MemoryScorer()
        item = MemoryItem()
        scorer.record_access(item)
        assert item.heat == 1

    def test_record_success(self):
        from memoryweaver.scorer import MemoryScorer
        scorer = MemoryScorer()
        item = MemoryItem()
        scorer.record_success(item)
        assert item.success_score == 1.0
        assert item.confidence == 1.0  # 1 success / 0 corrections
        assert item.heat == 0
        assert item.use_count == 1
        assert item.validation_count == 1

    def test_record_correction(self):
        from memoryweaver.scorer import MemoryScorer
        scorer = MemoryScorer()
        item = MemoryItem()
        scorer.record_correction(item)
        assert item.correction_score == 1.0
        assert item.confidence == 0.0  # 0 successes / 1 correction
        assert item.heat == 0
        assert item.use_count == 1
        assert item.validation_count == 1

    def test_evaluate_promotes_on_heat_and_success(self):
        from memoryweaver.scorer import MemoryScorer
        scorer = MemoryScorer(heat_promote=3)
        item = MemoryItem(layer=Layer.ACTIVATED)
        item.heat = 3
        item.success_score = 3.0
        scorer.evaluate(item)
        assert item.status == Status.PROMOTED
        assert item.layer == Layer.PATTERN

    def test_evaluate_deprecates_on_correction(self):
        from memoryweaver.scorer import MemoryScorer
        scorer = MemoryScorer(correction_deprecate=2)
        item = MemoryItem()
        item.correction_score = 2.0
        scorer.evaluate(item)
        assert item.status == Status.DEPRECATED
        assert item.memory_type == MemoryType.AVOIDANCE_RULE


class TestFeedbackClassifier:
    from memoryweaver.extractor import FeedbackClassifier

    def test_positive_zh(self):
        from memoryweaver.extractor import FeedbackClassifier
        fc = FeedbackClassifier()
        polarity, conf = fc.classify("可以了，解决了")
        assert polarity == "positive"

    def test_negative_zh(self):
        from memoryweaver.extractor import FeedbackClassifier
        fc = FeedbackClassifier()
        polarity, conf = fc.classify("不对，还是报错")
        assert polarity == "negative"

    def test_ambiguous_zh(self):
        from memoryweaver.extractor import FeedbackClassifier
        fc = FeedbackClassifier()
        polarity, conf = fc.classify("可能和组织选择有关")
        assert polarity == "ambiguous"

    def test_neutral_fallback(self):
        from memoryweaver.extractor import FeedbackClassifier
        fc = FeedbackClassifier()
        polarity, conf = fc.classify("今天天气不错")
        assert polarity == "neutral"

    def test_positive_en(self):
        from memoryweaver.extractor import FeedbackClassifier
        fc = FeedbackClassifier()
        polarity, conf = fc.classify("That works perfectly, thanks!")
        assert polarity == "positive"

    def test_negative_en(self):
        from memoryweaver.extractor import FeedbackClassifier
        fc = FeedbackClassifier()
        polarity, conf = fc.classify("No, this is still broken")
        assert polarity == "negative"


class TestEventDetector:
    from memoryweaver.extractor import EventDetector, EventType

    def test_detect_correction(self):
        from memoryweaver.extractor import EventDetector, EventType
        detector = EventDetector()
        event = detector.detect("不对，这个方案没用")
        assert event is not None
        assert event.type == EventType.USER_CORRECTION

    def test_detect_confirmation(self):
        from memoryweaver.extractor import EventDetector, EventType
        detector = EventDetector()
        event = detector.detect("可以了！搞定了！")
        assert event is not None
        assert event.type == EventType.USER_CONFIRMATION

    def test_detect_ambiguous(self):
        from memoryweaver.extractor import EventDetector, EventType
        detector = EventDetector()
        event = detector.detect("不确定，也许是版本问题")
        assert event is not None
        assert event.type == EventType.REASONING_REVERSAL

    def test_should_tag_must_tag(self):
        from memoryweaver.extractor import EventDetector, EventType, Event
        detector = EventDetector()
        event = Event(type=EventType.USER_CORRECTION, text="不对")
        assert detector.should_tag(event) is True

    def test_should_tag_skip(self):
        from memoryweaver.extractor import EventDetector, EventType, Event
        detector = EventDetector()
        event = Event(type=EventType.CHITCHAT, text="你好")
        assert detector.should_tag(event) is False


class TestModeRouter:
    from memoryweaver.router import ModeRouter, InferenceMode

    def test_thinking_when_empty_store(self):
        from memoryweaver.router import ModeRouter, InferenceMode
        store = MemoryStore(":memory:")  # won't persist
        router = ModeRouter(store)
        decision = router.route("completely new topic")
        assert decision.mode == InferenceMode.THINKING

    def test_fast_verify_with_similar(self):
        from memoryweaver.router import ModeRouter, InferenceMode
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(path)

        store = MemoryStore(path)
        store.add(MemoryItem(
            content="Codex CLI subscription load failed in WSL",
            layer=Layer.ACTIVATED,
            tags=["codex", "wsl"],
            confidence=0.7,
            heat=2,
        ))
        router = ModeRouter(store)
        decision = router.route("Codex CLI subscription error in WSL")
        # Should at least find the similar memory
        assert decision.mode in (InferenceMode.FAST_VERIFY, InferenceMode.THINKING)
        assert len(decision.matched_items) > 0

        Path(path).unlink(missing_ok=True)

    def test_excludes_unverified_assistant_memory_from_routing(self):
        from memoryweaver.router import ModeRouter, InferenceMode
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(path)

        store = MemoryStore(path)
        store.add(MemoryItem(
            content="Codex CLI subscription load failed in WSL",
            source="assistant",
            polarity=Polarity.AMBIGUOUS,
            layer=Layer.PATTERN,
            confidence=0.3,
            freshness=Freshness.STABLE,
        ))

        decision = ModeRouter(store).route(
            "Codex CLI subscription load failed in WSL"
        )

        assert decision.mode == InferenceMode.THINKING
        assert decision.matched_items == []

        Path(path).unlink(missing_ok=True)

    def test_verified_pattern_can_still_route_fast(self):
        from memoryweaver.router import ModeRouter, InferenceMode
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(path)

        store = MemoryStore(path)
        store.add(MemoryItem(
            content="Codex CLI subscription load failed in WSL",
            source="terminal",
            layer=Layer.PATTERN,
            confidence=0.9,
            freshness=Freshness.STABLE,
        ))

        decision = ModeRouter(store).route(
            "Codex CLI subscription load failed in WSL"
        )

        assert decision.mode == InferenceMode.FAST

        Path(path).unlink(missing_ok=True)
