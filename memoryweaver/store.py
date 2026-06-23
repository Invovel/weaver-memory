"""JSON-file-based memory store.

Provides CRUD operations and basic query-by-tag / query-by-polarity
on a local JSON file. Designed to be replaced by a vector DB in later
phases without changing the public API.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
import unicodedata
from pathlib import Path
from typing import Any, Optional

from memoryweaver.schema import MemoryItem, Layer, Polarity, Status
from memoryweaver.policy import MemoryPolicy, RetrievalPolicy

SCHEMA_VERSION = "0.2.0"


def atomic_write_json(path: str | Path, data: dict[str, Any]) -> None:
    """Write JSON atomically with a short Windows-friendly replace retry."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=target.parent,
        prefix="mw_",
        suffix=".tmp",
        text=True,
    )
    tmp = Path(tmp_name)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    _replace_with_retry(tmp, target)


def _replace_with_retry(
    source: Path,
    destination: Path,
    *,
    retries: int = 8,
    base_delay_seconds: float = 0.05,
) -> None:
    last_error: PermissionError | None = None
    for attempt in range(retries):
        try:
            os.replace(source, destination)
            return
        except PermissionError as error:
            last_error = error
            time.sleep(base_delay_seconds * (attempt + 1))
    if last_error is not None:
        raise last_error


def tokenize_text(text: str) -> set[str]:
    """Tokenize English identifiers and Chinese text without external deps."""
    normalized = unicodedata.normalize("NFKC", text).lower()
    tokens = set(re.findall(r"@?[a-z0-9][a-z0-9._/@+-]*", normalized))
    for segment in re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]+", normalized):
        if len(segment) == 1:
            tokens.add(segment)
        else:
            tokens.update(segment[index:index + 2] for index in range(len(segment) - 1))
    return tokens


def token_jaccard(left: str, right: str) -> float:
    """Return token Jaccard similarity for English, Chinese, or mixed text."""
    left_tokens = tokenize_text(left)
    right_tokens = tokenize_text(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


class MemoryStore:
    """Local JSON-backed store for MemoryItem objects.

    Usage:
        store = MemoryStore("memory.json")
        store.add(item)
        results = store.find_by_tags(["wsl", "codex"])
    """

    def __init__(
        self,
        path: str | Path = "memory.json",
        policy: Optional[MemoryPolicy] = None,
    ):
        self._path = Path(path)
        self._items: dict[str, MemoryItem] = {}
        self._policy = policy or MemoryPolicy()
        if self._path.exists():
            self._load()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add(self, item: MemoryItem) -> str:
        """Insert a memory item. Returns its id."""
        self._policy.validate_write(item)
        self._items[item.id] = item
        self._save()
        return item.id

    def get(self, id: str) -> Optional[MemoryItem]:
        """Retrieve a single memory by id."""
        return self._items.get(id)

    def update(self, item: MemoryItem) -> None:
        """Update an existing memory item (matched by id)."""
        if item.id not in self._items:
            raise KeyError(f"MemoryItem '{item.id}' not found")
        self._policy.validate_write(item, is_update=True)
        item.mark_updated()
        self._items[item.id] = item
        self._save()

    def delete(self, id: str) -> bool:
        """Hard-delete a memory by id. Returns True if it existed."""
        if id in self._items:
            del self._items[id]
            self._save()
            return True
        return False

    def list_all(self) -> list[MemoryItem]:
        """Return every stored item."""
        return list(self._items.values())

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def find_by_tags(self, tags: list[str], match_all: bool = False) -> list[MemoryItem]:
        """Find memories whose tags overlap with *tags*.

        Args:
            tags: Tags to search for.
            match_all: If True, the memory must contain ALL given tags.
        """
        tag_set = set(t.lower() for t in tags)
        results = []
        for item in self._items.values():
            item_tags = set(t.lower() for t in item.tags)
            if match_all:
                if tag_set.issubset(item_tags):
                    results.append(item)
            else:
                if tag_set & item_tags:
                    results.append(item)
        return results

    def find_by_polarity(self, polarity: Polarity) -> list[MemoryItem]:
        """Return all memories with the given polarity."""
        return [i for i in self._items.values() if i.polarity == polarity]

    def find_by_layer(self, layer: Layer) -> list[MemoryItem]:
        """Return all memories at the given layer."""
        return [i for i in self._items.values() if i.layer == layer]

    def find_by_status(self, status: Status) -> list[MemoryItem]:
        """Return all memories with the given status."""
        return [i for i in self._items.values() if i.status == status]

    def find_similar(
        self, content: str, threshold: float = 0.7
    ) -> list[MemoryItem]:
        """Naive keyword-overlap similarity search.

        This is a placeholder for Phase 2 embedding-based retrieval.
        """
        if not tokenize_text(content):
            return []

        scored: list[tuple[float, MemoryItem]] = []
        for item in self._items.values():
            overlap = token_jaccard(content, item.content)
            if overlap >= threshold:
                scored.append((overlap, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored]

    def count(self) -> int:
        """Return the total number of stored items."""
        return len(self._items)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save(self) -> None:
        data = {
            "version": SCHEMA_VERSION,
            "items": [item.to_dict() for item in self._items.values()],
        }
        atomic_write_json(self._path, data)

    def _load(self) -> None:
        try:
            with open(self._path, encoding="utf-8") as f:
                text = f.read().strip()
            if not text:
                return
            data = json.loads(text)
        except (json.JSONDecodeError, FileNotFoundError):
            return
        for raw in data.get("items", []):
            item = MemoryItem.from_dict(raw)
            self._items[item.id] = item


class MemoryWorkspace:
    """Directory-backed coordination point for the standalone SDK."""

    def __init__(self, root: str | Path = ".memoryweaver"):
        from memoryweaver.composer import PatternStore
        from memoryweaver.context_store import (
            ContextCapsuleStore,
            MarkerEvidenceContextStore,
            RawSpanStore,
        )
        from memoryweaver.evidence import EvidenceStore
        from memoryweaver.graph_store import GraphStore
        from memoryweaver.tag_time_index import TagTimeIndex

        self.root = Path(root)
        self.memory_policy = MemoryPolicy()
        self.retrieval_policy = RetrievalPolicy()
        self.memories = MemoryStore(
            self.root / "memories.json",
            policy=self.memory_policy,
        )
        self.patterns = PatternStore(
            self.root / "patterns.json",
            policy=self.retrieval_policy,
        )
        self.evidence = EvidenceStore(
            self.root / "evidence_nodes.json",
            self.root / "evidence_links.json",
        )
        self.graph = GraphStore(self.root / "graph.json")
        self.raw_spans = RawSpanStore(self.root / "raw_spans.json")
        self.context_capsules = ContextCapsuleStore(
            self.root / "context_capsules.json"
        )
        self.marker_evidence_contexts = MarkerEvidenceContextStore(
            self.root / "marker_evidence_contexts.json"
        )
        self.tag_time_index = TagTimeIndex(self.root / "tag_time_index.json")

    def validate(self) -> dict[str, Any]:
        """Return structural errors and compatibility warnings."""
        errors: list[str] = []
        warnings: list[str] = []
        paths = [
            self.root / "memories.json",
            self.root / "patterns.json",
            self.root / "evidence_nodes.json",
            self.root / "evidence_links.json",
            self.root / "graph.json",
            self.root / "raw_spans.json",
            self.root / "context_capsules.json",
            self.root / "marker_evidence_contexts.json",
            self.root / "tag_time_index.json",
        ]
        for path in paths:
            if not path.exists():
                warnings.append(f"missing optional empty store: {path.name}")
                continue
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                errors.append(f"invalid JSON in {path.name}: {exc}")

        for item in self.memories.list_all():
            if item.legacy_pattern:
                warnings.append(f"legacy Layer-3 MemoryItem: {item.id}")
            if item.source.value in ("assistant", "synthetic") and (
                item.polarity.value != "ambiguous" or item.confidence > 0.3
            ):
                errors.append(f"polluting unverified memory: {item.id}")

        errors.extend(self.evidence.validate_links(
            {item.id for item in self.memories.list_all()},
            {pattern.id for pattern in self.patterns.list_all()},
        ))
        for pattern in self.patterns.list_all():
            if pattern.policy_version != self.memory_policy.version:
                warnings.append(f"stale pattern policy version: {pattern.id}")
        errors.extend(self.graph.validate_refs(
            memory_ids={item.id for item in self.memories.list_all()},
            evidence_ids={node.id for node in self.evidence.list_nodes()},
            pattern_ids={pattern.id for pattern in self.patterns.list_all()},
        ))
        errors.extend(self.context_capsules.validate_raw_refs(
            {raw_span.id for raw_span in self.raw_spans.list_all()}
        ))

        if token_jaccard("检查组织选择解决订阅问题", "订阅问题检查组织选择") <= 0:
            errors.append("Chinese lexical retrieval probe failed")

        return {
            "valid": not errors,
            "schema_version": SCHEMA_VERSION,
            "memory_policy_version": self.memory_policy.version,
            "retrieval_policy_version": self.retrieval_policy.version,
            "errors": errors,
            "warnings": warnings,
        }

    def doctor(self) -> dict[str, Any]:
        """Return operational health warnings for v0.4.3 runtime checks."""
        errors: list[str] = []
        warnings: list[str] = []
        info: list[str] = []

        store_paths = [
            self.root / "memories.json",
            self.root / "patterns.json",
            self.root / "evidence_nodes.json",
            self.root / "evidence_links.json",
            self.root / "graph.json",
            self.root / "raw_spans.json",
            self.root / "context_capsules.json",
            self.root / "marker_evidence_contexts.json",
            self.root / "tag_time_index.json",
        ]
        for path in store_paths:
            if not path.exists():
                info.append(f"missing empty store: {path.name}")

        memories = self.memories.list_all()
        total_memories = len(memories)
        inactive_count = sum(
            1 for item in memories
            if item.status in (Status.DEPRECATED, Status.ARCHIVED)
        )
        if total_memories and inactive_count / total_memories > 0.5:
            warnings.append(
                f"deprecated/archived memories exceed 50%: {inactive_count}/{total_memories}"
            )

        legacy_patterns = [item for item in memories if item.legacy_pattern]
        if legacy_patterns:
            warnings.append(f"legacy Layer-3 MemoryItem count: {len(legacy_patterns)}")

        patterns = self.patterns.list_all()
        for pattern in patterns:
            composer_like = (
                2 <= len(pattern.composed_from) <= 4
                and bool(pattern.evidence_links)
                and bool(pattern.rollback_to)
                and bool(pattern.policy_version)
            )
            if not composer_like:
                errors.append(
                    f"non PatternComposer-like Pattern invariant: {pattern.id}"
                )

        memory_ids = {item.id for item in memories}
        pattern_ids = {pattern.id for pattern in patterns}
        evidence_nodes = self.evidence.list_nodes()
        evidence_ids = {node.id for node in evidence_nodes}
        links = self.evidence.list_links()
        errors.extend(self.evidence.validate_links(memory_ids, pattern_ids))

        linked_evidence_ids = {link.evidence_id for link in links}
        orphan_evidence = [
            node.id for node in evidence_nodes
            if node.id not in linked_evidence_ids
        ]
        if orphan_evidence:
            warnings.append(f"orphan evidence node count: {len(orphan_evidence)}")

        errors.extend(self.graph.validate_refs(
            memory_ids=memory_ids,
            evidence_ids=evidence_ids,
            pattern_ids=pattern_ids,
        ))

        graph_nodes = self.graph.list_nodes()
        edges = self.graph.list_edges()
        proposals = self.graph.list_proposals()
        accepted_edges = [
            edge for edge in edges
            if edge.status.value in ("accepted", "verified")
        ]
        if (graph_nodes or edges or proposals) and not accepted_edges:
            info.append("graph store is non-empty but accepted edge count is 0")

        stale_pending = 0
        exact_candidate_only = 0
        provider_statuses: list[str] = []
        online_llm_call_count = 0
        accepted_wrong_link_rate = 0.0
        exact_human_checked = 0
        exact_human_failed = 0
        pending_count = 0

        for proposal in proposals:
            if proposal.status == "pending":
                pending_count += 1
            lifecycle = proposal.metadata.get("pending_lifecycle", {})
            if proposal.status == "pending" and lifecycle:
                created_batch = int(lifecycle.get("created_batch", 0))
                stale_after = int(lifecycle.get("stale_after_batch", 0))
                current_batch = int(proposal.metadata.get("current_batch", created_batch))
                if current_batch > stale_after:
                    stale_pending += 1

            support = str(proposal.metadata.get("evidence_support", ""))
            evidence_state = str(proposal.metadata.get("evidence_state", ""))
            if support == "supports_exact" and evidence_state == "candidate_only":
                exact_candidate_only += 1
            if support == "supports_exact" and "human_verified" in proposal.metadata:
                exact_human_checked += 1
                if not bool(proposal.metadata.get("human_verified")):
                    exact_human_failed += 1

            provider_status = str(proposal.metadata.get("provider_status", ""))
            if provider_status in {"cooldown", "degraded", "disabled"}:
                provider_statuses.append(provider_status)
            online_llm_call_count += int(proposal.metadata.get("online_llm_call_count", 0))
            accepted_wrong_link_rate = max(
                accepted_wrong_link_rate,
                float(proposal.metadata.get("accepted_wrong_link_rate", 0.0)),
            )

        for edge in accepted_edges:
            online_llm_call_count += int(edge.metadata.get("online_llm_call_count", 0))
            accepted_wrong_link_rate = max(
                accepted_wrong_link_rate,
                float(edge.metadata.get("accepted_wrong_link_rate", 0.0)),
            )
            if bool(edge.metadata.get("wrong_link", False)):
                accepted_wrong_link_rate = max(accepted_wrong_link_rate, 1.0)

        if online_llm_call_count > 0:
            errors.append(f"online_llm_call_count > 0: {online_llm_call_count}")
        if accepted_wrong_link_rate > 0:
            errors.append(f"accepted wrong link rate > 0: {accepted_wrong_link_rate}")
        if pending_count and stale_pending / pending_count > 0.5:
            warnings.append(
                "stale pending proposal ratio exceeds 50%: "
                f"{stale_pending}/{pending_count}; consider archive_without_new_evidence"
            )
        elif stale_pending:
            warnings.append(
                f"stale pending proposal count: {stale_pending}; consider archive_without_new_evidence"
            )
        if exact_candidate_only:
            warnings.append(
                "pending proposals with supports_exact but candidate-only evidence: "
                f"{exact_candidate_only}"
            )
        if provider_statuses:
            warnings.append(
                "provider status degraded: " + ", ".join(sorted(set(provider_statuses)))
            )
        if exact_human_checked and exact_human_failed / exact_human_checked > 0.3:
            warnings.append(
                "EvidenceSupportCheck supports_exact human failure rate > 0.3: "
                f"{exact_human_failed}/{exact_human_checked}"
            )

        raw_ids = {raw_span.id for raw_span in self.raw_spans.list_all()}
        capsule_errors = self.context_capsules.validate_raw_refs(raw_ids)
        errors.extend(capsule_errors)
        if self.raw_spans.list_all() and not self.context_capsules.list_all():
            warnings.append("raw spans exist but no context capsules are indexed")
        if self.context_capsules.list_all() and not self.marker_evidence_contexts.list_all():
            info.append("context capsules exist but no marker evidence contexts are configured")

        return {
            "valid": not errors,
            "schema_version": SCHEMA_VERSION,
            "memory_policy_version": self.memory_policy.version,
            "retrieval_policy_version": self.retrieval_policy.version,
            "errors": errors,
            "warnings": warnings,
            "info": info,
        }
