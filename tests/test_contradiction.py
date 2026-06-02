"""Tests for ContradictionResolver."""

import pytest

from memoryweaver.schema import (
    MemoryItem,
    Polarity,
    MemoryType,
    Freshness,
)
from memoryweaver.contradiction import (
    ContradictionResolver,
    Severity,
    Relation,
)


class TestContradictionResolver:
    def setup_method(self):
        self.resolver = ContradictionResolver()

    # ── Rule 1: Both unverified → SILENT ─────────────────────────

    def test_both_assistant_sources_silent(self):
        new = MemoryItem(
            source="assistant",
            polarity=Polarity.AMBIGUOUS,
            content="Use Node 22",
        )
        existing = MemoryItem(
            source="assistant",
            polarity=Polarity.AMBIGUOUS,
            content="Use Node 20",
        )
        result = self.resolver.resolve(new, existing)
        assert result.severity == Severity.SILENT
        assert result.relation == Relation.MUTUALLY_AMBIGUOUS

    def test_both_ambiguous_polarity_silent(self):
        new = MemoryItem(
            polarity=Polarity.AMBIGUOUS,
            source="assistant",
            content="Maybe Node 22",
        )
        existing = MemoryItem(
            polarity=Polarity.AMBIGUOUS,
            source="assistant",
            content="Maybe Node 20",
        )
        result = self.resolver.resolve(new, existing)
        assert result.severity == Severity.SILENT

    def test_assistant_vs_composer_silent(self):
        new = MemoryItem(
            source="assistant",
            polarity=Polarity.AMBIGUOUS,
            content="New claim",
        )
        existing = MemoryItem(source="composer", content="Old claim")
        result = self.resolver.resolve(new, existing)
        assert result.severity == Severity.SILENT

    # ── Rule 2: User preference → BLOCK ──────────────────────────

    def test_user_preference_block(self):
        new = MemoryItem(
            source="assistant",
            polarity=Polarity.AMBIGUOUS,
            content="Suggest pnpm",
        )
        existing = MemoryItem(
            source="user",
            memory_type=MemoryType.PREFERENCE,
            content="User prefers npm over pnpm",
            freshness=Freshness.STABLE,
        )
        result = self.resolver.resolve(new, existing)
        assert result.severity == Severity.BLOCK
        assert not self.resolver.needs_user_input(result) == False
        # needs_user_input should be True for BLOCK
        assert self.resolver.needs_user_input(result) is True

    def test_expired_preference_no_block(self):
        """Expired preferences should NOT block."""
        new = MemoryItem(
            source="assistant",
            polarity=Polarity.AMBIGUOUS,
            content="Suggest pnpm",
        )
        existing = MemoryItem(
            source="user",
            memory_type=MemoryType.PREFERENCE,
            content="User prefers npm",
            freshness=Freshness.EXPIRED,
        )
        result = self.resolver.resolve(new, existing)
        # Should fall through to WARN (not BLOCK) since freshness is EXPIRED
        assert result.severity != Severity.BLOCK

    # ── Rule 3: Strong terminal-verified → BLOCK ─────────────────

    def test_strong_terminal_verified_block(self):
        new = MemoryItem(
            source="assistant",
            polarity=Polarity.AMBIGUOUS,
            content="Codex needs Node 22",
        )
        existing = MemoryItem(
            source="terminal",
            content="Codex works with Node 20.11.0",
            confidence=0.9,
            freshness=Freshness.STABLE,
        )
        result = self.resolver.resolve(new, existing)
        assert result.severity == Severity.BLOCK

    def test_terminal_verified_not_strong_enough(self):
        """Confidence below STRONG_CONFIDENCE should fall through."""
        new = MemoryItem(
            source="assistant",
            polarity=Polarity.AMBIGUOUS,
            content="Codex needs Node 22",
        )
        existing = MemoryItem(
            source="terminal",
            content="Codex works with Node 20",
            confidence=0.7,
            freshness=Freshness.STABLE,
        )
        result = self.resolver.resolve(new, existing)
        # 0.7 < 0.8 so not strong → should be WARN
        assert result.severity == Severity.WARN

    # ── Rule 4: Verified but stale → WARN ────────────────────────

    def test_stale_terminal_warn(self):
        new = MemoryItem(
            source="assistant",
            polarity=Polarity.AMBIGUOUS,
            content="Codex needs Node 22",
        )
        existing = MemoryItem(
            source="terminal",
            content="Codex works with Node 20",
            confidence=0.9,
            freshness=Freshness.VOLATILE,
        )
        result = self.resolver.resolve(new, existing)
        assert result.severity == Severity.WARN
        assert result.action == "demote"

    # ── Rule 5: Moderate confidence verified → WARN ──────────────

    def test_moderate_user_verified_warn(self):
        new = MemoryItem(
            source="assistant",
            polarity=Polarity.AMBIGUOUS,
            content="WSL2 not needed",
        )
        existing = MemoryItem(
            source="user",
            content="User confirmed WSL2 is required",
            confidence=0.5,
            freshness=Freshness.STABLE,
        )
        result = self.resolver.resolve(new, existing)
        assert result.severity == Severity.WARN

    # ── Convenience methods ──────────────────────────────────────

    def test_should_warn(self):
        new = MemoryItem(
            source="assistant",
            polarity=Polarity.AMBIGUOUS,
            content="claim",
        )
        existing = MemoryItem(
            source="user",
            content="old claim",
            confidence=0.5,
            freshness=Freshness.STABLE,
        )
        result = self.resolver.resolve(new, existing)
        assert self.resolver.should_warn(result) is True

    def test_silent_should_not_warn(self):
        new = MemoryItem(
            source="assistant",
            polarity=Polarity.AMBIGUOUS,
            content="claim",
        )
        existing = MemoryItem(
            source="assistant",
            polarity=Polarity.AMBIGUOUS,
            content="old claim",
        )
        result = self.resolver.resolve(new, existing)
        assert self.resolver.should_warn(result) is False
        assert self.resolver.needs_user_input(result) is False

    # ── Edge cases ───────────────────────────────────────────────

    def test_fallback_warn_when_no_rule_matches(self):
        """Unverified but not matching any specific rule → fallback WARN."""
        new = MemoryItem(
            source="web",
            content="Web-sourced claim",
            confidence=0.3,
        )
        existing = MemoryItem(
            source="composer",
            content="Composer-generated pattern",
            confidence=0.4,
        )
        result = self.resolver.resolve(new, existing)
        # web is not in "both_unverified" check (only assistant/assistant or ambiguous/ambiguous)
        # composer is not "user", not "terminal" → falls to fallback
        assert result.severity == Severity.WARN
