"""Policy and lexical baseline tests for SDK v0.2.0."""

import pytest

from memoryweaver.evidence import EvidenceLink
from memoryweaver.policy import MemoryPolicy, RetrievalPolicy
from memoryweaver.schema import (
    Freshness,
    Layer,
    MemoryItem,
    MemoryType,
    Pattern,
    PatternStatus,
    Polarity,
    Source,
    Status,
)
from memoryweaver.store import token_jaccard, tokenize_text


def link_for(item: MemoryItem) -> EvidenceLink:
    return EvidenceLink(evidence_id="ev_1", memory_id=item.id)


class TestMemoryPolicy:
    def test_assistant_and_synthetic_are_downgraded(self):
        policy = MemoryPolicy()
        for source in (Source.ASSISTANT, Source.SYNTHETIC):
            item = MemoryItem(source=source, confidence=1.0, polarity=Polarity.POSITIVE)
            normalized = policy.normalize_candidate(item)
            assert normalized.polarity == Polarity.AMBIGUOUS
            assert normalized.confidence == 0.3

    def test_user_preference_can_promote_without_link(self):
        item = MemoryItem(source="user", memory_type=MemoryType.PREFERENCE)
        promoted = MemoryPolicy().promote_to_layer2(item, [])
        assert promoted.layer == Layer.ACTIVATED
        assert promoted.status == Status.ACTIVATED

    def test_user_fact_requires_validation_or_link(self):
        policy = MemoryPolicy()
        item = MemoryItem(source="user")
        assert policy.can_promote_to_layer2(item, []) is False
        item.record_validation()
        assert policy.can_promote_to_layer2(item, []) is True

    def test_terminal_and_tool_require_saved_evidence_or_link(self):
        policy = MemoryPolicy()
        for source in (Source.TERMINAL, Source.TOOL):
            item = MemoryItem(source=source)
            assert policy.can_promote_to_layer2(item, []) is False
            item.evidence = "captured output"
            assert policy.can_promote_to_layer2(item, []) is True

    def test_file_and_web_require_link_and_confidence(self):
        policy = MemoryPolicy()
        for source in (Source.FILE, Source.WEB):
            item = MemoryItem(source=source, confidence=0.5)
            assert policy.can_promote_to_layer2(item, []) is False
            assert policy.can_promote_to_layer2(item, [link_for(item)]) is True

    @pytest.mark.parametrize(
        "source",
        [Source.ASSISTANT, Source.SYNTHETIC, Source.COMPOSER, Source.UNKNOWN],
    )
    def test_untrusted_sources_cannot_promote(self, source):
        item = MemoryItem(source=source, evidence="text", confidence=1.0)
        assert MemoryPolicy().can_promote_to_layer2(item, [link_for(item)]) is False


class TestRetrievalPolicy:
    def test_scope_and_inactive_status_are_filtered(self):
        policy = RetrievalPolicy()
        item = MemoryItem(source="terminal", scope="private")
        assert policy.should_include(item, scope="project") is False
        item.scope = "global"
        assert policy.should_include(item, scope="project") is True
        item.status = Status.ARCHIVED
        assert policy.should_include(item, scope="project") is False

    def test_assistant_requires_explicit_unverified_and_heat(self):
        item = MemoryItem(source="assistant", heat=1)
        policy = RetrievalPolicy()
        assert policy.should_include(item) is False
        assert policy.should_include(item, include_unverified=True) is True

    def test_synthetic_is_never_returned_as_fact(self):
        item = MemoryItem(source="synthetic", heat=10, confidence=1.0)
        assert RetrievalPolicy().should_include(item, include_unverified=True) is False

    def test_provisional_and_stable_patterns_are_retrievable(self):
        policy = RetrievalPolicy()
        provisional = Pattern(status=PatternStatus.PROVISIONAL)
        stable = Pattern(status=PatternStatus.STABLE)
        archived = Pattern(status=PatternStatus.ARCHIVED)
        expired = Pattern(freshness=Freshness.EXPIRED)
        assert policy.should_include_pattern(provisional) is True
        assert policy.should_include_pattern(stable) is True
        assert policy.should_include_pattern(archived) is False
        assert policy.should_include_pattern(expired) is False


class TestLexicalBaseline:
    def test_chinese_reordered_query_has_overlap(self):
        assert token_jaccard("检查组织选择解决订阅问题", "订阅问题检查组织选择") > 0

    def test_mixed_identifiers_preserve_package_and_error_code(self):
        tokens = tokenize_text("修复 @scope/pkg v1.2.3 ERR_401 组织选择")
        assert "@scope/pkg" in tokens
        assert "v1.2.3" in tokens
        assert "err_401" in tokens
        assert "组织" in tokens

    def test_english_similarity_does_not_regress(self):
        assert token_jaccard(
            "Codex CLI subscription load failed in WSL",
            "Codex CLI subscription error in WSL",
        ) >= 0.5
