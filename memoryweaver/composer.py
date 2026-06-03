"""Canonical provisional Layer-3 patterns and explicit composition."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from memoryweaver.evidence import EvidenceStore
from memoryweaver.policy import MemoryPolicy, RetrievalPolicy
from memoryweaver.schema import Freshness, Layer, Pattern, PatternStatus
from memoryweaver.store import MemoryStore, SCHEMA_VERSION, token_jaccard


class PatternStore:
    """Atomic JSON storage for canonical Layer-3 Pattern records."""

    def __init__(
        self,
        path: str | Path,
        policy: Optional[RetrievalPolicy] = None,
    ):
        self._path = Path(path)
        self._patterns: dict[str, Pattern] = {}
        self._policy = policy or RetrievalPolicy()
        self._load()

    def add(self, pattern: Pattern) -> str:
        self._patterns[pattern.id] = pattern
        self._save()
        return pattern.id

    def get(self, id: str) -> Optional[Pattern]:
        return self._patterns.get(id)

    def update(self, pattern: Pattern) -> None:
        if pattern.id not in self._patterns:
            raise KeyError(f"Pattern '{pattern.id}' not found")
        pattern.mark_updated()
        self._patterns[pattern.id] = pattern
        self._save()

    def list_all(self) -> list[Pattern]:
        return list(self._patterns.values())

    def search(
        self,
        query: str,
        scope: str = "project",
        limit: int = 10,
        threshold: float = 0.25,
    ) -> list[Pattern]:
        scored: list[tuple[float, Pattern]] = []
        for pattern in self._patterns.values():
            if not self._policy.should_include_pattern(pattern, scope):
                continue
            similarity = token_jaccard(query, pattern.rule)
            if similarity >= threshold:
                scored.append((similarity * pattern.confidence, pattern))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [pattern for _, pattern in scored[:limit]]

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "version": SCHEMA_VERSION,
                    "patterns": [p.to_dict() for p in self._patterns.values()],
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        os.replace(tmp, self._path)

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            text = self._path.read_text(encoding="utf-8").strip()
            data = json.loads(text) if text else {}
        except (json.JSONDecodeError, FileNotFoundError):
            return
        for raw in data.get("patterns", []):
            pattern = Pattern.from_dict(raw)
            self._patterns[pattern.id] = pattern


class PatternComposer:
    """Create and explicitly advance provisional Pattern records."""

    def __init__(
        self,
        memories: MemoryStore,
        patterns: PatternStore,
        evidence: EvidenceStore,
        policy: Optional[MemoryPolicy] = None,
    ):
        self._memories = memories
        self._patterns = patterns
        self._evidence = evidence
        self._policy = policy or MemoryPolicy()

    def compose(
        self,
        supporting_memory_ids: list[str],
        rule: str,
        applies_when: list[str],
        avoid_when: list[str],
        success_path: list[str],
        failed_path: list[str],
        evidence_link_ids: list[str],
        scope: str,
    ) -> Pattern:
        if not 2 <= len(supporting_memory_ids) <= 4:
            raise ValueError("PatternComposer requires 2-4 supporting memories")
        memories = [self._memories.get(id) for id in supporting_memory_ids]
        if any(memory is None for memory in memories):
            raise ValueError("all supporting memories must exist")
        if any(memory.layer != Layer.ACTIVATED for memory in memories if memory):
            raise ValueError("all supporting memories must be Layer 2")
        if any(memory.scope != scope for memory in memories if memory):
            raise ValueError("all supporting memories must share the Pattern scope")
        if not evidence_link_ids:
            raise ValueError("PatternComposer requires at least one EvidenceLink")
        links = [self._evidence.get_link(id) for id in evidence_link_ids]
        if any(link is None for link in links):
            raise ValueError("all EvidenceLinks must exist")
        if not any(link.memory_id in supporting_memory_ids for link in links if link):
            raise ValueError("at least one EvidenceLink must support an input memory")

        pattern = Pattern(
            composed_from=supporting_memory_ids,
            rule=rule,
            applies_when=applies_when,
            avoid_when=avoid_when,
            success_path=success_path,
            failed_path=failed_path,
            evidence_links=evidence_link_ids,
            rollback_to=list(supporting_memory_ids),
            scope=scope,
            policy_version=self._policy.version,
            freshness=Freshness.UNKNOWN,
            confidence=0.0,
        )
        self._patterns.add(pattern)
        return pattern

    def record_validation(
        self,
        pattern_id: str,
        task_run_id: str,
        successful: bool,
        conflict_ref: str = "",
    ) -> Pattern:
        pattern = self._get(pattern_id)
        if successful:
            pattern.validation_task_runs.append(task_run_id)
            pattern.confidence = round(
                len(pattern.validation_task_runs)
                / (len(pattern.validation_task_runs) + len(pattern.conflict_refs)),
                2,
            )
        else:
            pattern.conflict_refs.append(conflict_ref or f"task:{task_run_id}")
            pattern.status = PatternStatus.ROLLED_BACK
            pattern.rollback_reason = conflict_ref or f"failed validation: {task_run_id}"
        self._patterns.update(pattern)
        return pattern

    def promote_stable(self, pattern_id: str) -> Pattern:
        pattern = self._get(pattern_id)
        if len(pattern.validation_task_runs) < 3:
            raise ValueError("stable Pattern requires at least 3 successful validations")
        if len(set(pattern.validation_task_runs)) < 2:
            raise ValueError("stable Pattern requires at least 2 task runs")
        if not pattern.evidence_links:
            raise ValueError("stable Pattern requires evidence links")
        if pattern.conflict_refs:
            raise ValueError("stable Pattern cannot have unresolved conflicts")
        if pattern.freshness == Freshness.EXPIRED:
            raise ValueError("expired Pattern cannot become stable")
        if pattern.policy_version != self._policy.version:
            raise ValueError("Pattern policy version is stale")
        pattern.status = PatternStatus.STABLE
        self._patterns.update(pattern)
        return pattern

    def rollback(self, pattern_id: str, reason: str) -> Pattern:
        pattern = self._get(pattern_id)
        pattern.status = PatternStatus.ROLLED_BACK
        pattern.rollback_reason = reason
        pattern.rollback_to = list(pattern.composed_from)
        self._patterns.update(pattern)
        return pattern

    def archive(self, pattern_id: str) -> Pattern:
        pattern = self._get(pattern_id)
        pattern.status = PatternStatus.ARCHIVED
        self._patterns.update(pattern)
        return pattern

    def _get(self, pattern_id: str) -> Pattern:
        pattern = self._patterns.get(pattern_id)
        if pattern is None:
            raise KeyError(f"Pattern '{pattern_id}' not found")
        return pattern
