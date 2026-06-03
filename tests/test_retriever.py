"""Tests for VerifiedRetriever."""

import os
import tempfile
from pathlib import Path

import pytest

from memoryweaver.schema import MemoryItem, Polarity, MemoryType, Status
from memoryweaver.store import MemoryStore
from memoryweaver.retriever import VerifiedRetriever


class TestVerifiedRetriever:
    @pytest.fixture
    def store(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(path)
        store = MemoryStore(path)

        store.add(MemoryItem(
            content="Codex subscription load failed in WSL",
            source="terminal",
            confidence=0.9,
            tags=["codex", "subscription", "wsl"],
        ))
        store.add(MemoryItem(
            content="User prefers npm over pnpm for package management",
            source="user",
            confidence=1.0,
            memory_type=MemoryType.PREFERENCE,
            tags=["preference", "npm", "pnpm"],
        ))
        store.add(MemoryItem(
            content="Codex might need Node version 22 to work properly",
            source="assistant",
            confidence=0.2,
            polarity=Polarity.AMBIGUOUS,
            tags=["codex", "node"],
        ))
        store.add(MemoryItem(
            content="npm install solved similar subscription issue in project X",
            source="web",
            confidence=0.5,
            tags=["npm", "subscription", "fix"],
        ))
        store.add(MemoryItem(
            content="If Codex installs but subscription fails, check auth first",
            source="composer",
            confidence=0.82,
            tags=["codex", "subscription", "pattern"],
        ))
        yield store
        Path(path).unlink(missing_ok=True)

    # ── Retrieval filtering ──────────────────────────────────────

    def test_excludes_assistant_by_default(self, store):
        retriever = VerifiedRetriever(store)
        results = retriever.search("Codex subscription load failed in WSL")
        contents = [r.content for r in results]
        # Assistant "might need Node 22" should be excluded
        assert "might need Node" not in contents[0] if contents else True
        # terminal-verified fact should appear
        assert any("subscription load failed" in c for c in contents)

    def test_includes_assistant_when_requested_and_heated(self, store):
        # Give the assistant memory some heat so it becomes includable
        for item in store.list_all():
            if item.source == "assistant":
                item.heat = 3
                store.update(item)

        retriever = VerifiedRetriever(store)
        results = retriever.search("Codex Node version WSL", include_unverified=True)
        contents = [r.content for r in results]
        assert any("might need Node" in c for c in contents)

    def test_still_excludes_zero_heat_assistant_even_when_requested(self, store):
        # All assistant items have heat=0 by default
        retriever = VerifiedRetriever(store)
        results = retriever.search("Codex Node version WSL", include_unverified=True)
        contents = [r.content for r in results]
        assert not any("might need Node" in c for c in contents)

    def test_terminal_and_user_always_included(self, store):
        retriever = VerifiedRetriever(store)
        results = retriever.search("npm pnpm package management preference")
        contents = [r.content for r in results]
        assert any("prefers npm" in c for c in contents)

    def test_composer_memory_is_not_returned_as_fact(self, store):
        retriever = VerifiedRetriever(store)
        results = retriever.search("Codex subscription auth check install fails")
        contents = [r.content for r in results]
        assert not any("check auth first" in c for c in contents)

    # ── Result ordering ──────────────────────────────────────────

    def test_user_sourced_ranked_highest(self, store):
        retriever = VerifiedRetriever(store)
        results = retriever.search("npm package management preference")
        if results:
            top_source = results[0].source
            assert top_source in ("user", "terminal")

    # ── Tag-based search ─────────────────────────────────────────

    def test_search_by_tags_respects_filtering(self, store):
        retriever = VerifiedRetriever(store)
        results = retriever.search_by_tags(["codex", "subscription"])
        contents = [r.content for r in results]
        # Terminal-verified fact should be included
        assert any("subscription load failed" in c for c in contents)
        # Composer output is only returned through canonical PatternStore routing.
        assert not any("check auth first" in c for c in contents)
        # Assistant claim matches "codex" but remains excluded by source gate.
        assert not any("might need Node" in c for c in contents)

    def test_search_by_tags_can_explicitly_include_heated_assistant(self, store):
        for item in store.list_all():
            if item.source == "assistant":
                item.heat = 3
                store.update(item)

        retriever = VerifiedRetriever(store)
        results = retriever.search_by_tags(
            ["node"],
            include_unverified=True,
        )

        assert any("might need Node" in r.content for r in results)

    def test_search_by_tags_excludes_inactive_memories(self, store):
        store.add(MemoryItem(
            content="Archived terminal memory",
            source="terminal",
            confidence=1.0,
            status=Status.ARCHIVED,
            tags=["inactive"],
        ))
        store.add(MemoryItem(
            content="Deprecated terminal memory",
            source="terminal",
            confidence=1.0,
            status=Status.DEPRECATED,
            tags=["inactive"],
        ))

        results = VerifiedRetriever(store).search_by_tags(["inactive"])

        assert results == []

    def test_synthetic_memory_never_enters_verified_results(self, store):
        store.add(MemoryItem(
            content="Synthetic HyDE answer",
            source="synthetic",
            confidence=1.0,
            heat=3,
            tags=["hyde"],
        ))

        results = VerifiedRetriever(store).search_by_tags(
            ["hyde"],
            include_unverified=True,
        )

        assert results == []

    # ── get_verified_context ─────────────────────────────────────

    def test_get_verified_context(self, store):
        retriever = VerifiedRetriever(store)
        ctx = retriever.get_verified_context("Codex subscription WSL auth")
        assert ctx
        assert "[terminal]" in ctx or "[user]" in ctx

    def test_get_verified_context_empty(self, store):
        retriever = VerifiedRetriever(store)
        ctx = retriever.get_verified_context("zzzz_nonexistent_topic_zzzz")
        assert ctx == ""

    # ── Edge cases ───────────────────────────────────────────────

    def test_unknown_source_is_never_returned_as_fact(self, store):
        store.add(MemoryItem(
            content="Something from unknown source with no evidence",
            source="unknown",
            confidence=0.0,
            tags=["unknown_tag"],
        ))
        store.add(MemoryItem(
            content="Another unknown source with some evidence and confidence",
            source="unknown",
            confidence=0.3,
            tags=["unknown_tag"],
        ))
        retriever = VerifiedRetriever(store)
        results = retriever.search("unknown source with evidence confidence")
        contents = [r.content for r in results]
        assert not any("with no evidence" in c for c in contents)
        assert not any("with some evidence" in c for c in contents)
