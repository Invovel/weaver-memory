"""Canonical provisional Layer-3 patterns and explicit composition."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from memoryweaver.evidence import EvidenceStore
from memoryweaver.policy import MemoryPolicy, RetrievalPolicy
from memoryweaver.schema import Freshness, Layer, Pattern, PatternStatus
from memoryweaver.store import (
    MemoryStore,
    SCHEMA_VERSION,
    atomic_write_json,
    token_jaccard,
)


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
                signal = max(
                    pattern.path_fitness_score,
                    pattern.confidence,
                    0.1 if pattern.status == PatternStatus.PROVISIONAL else 0.0,
                )
                scored.append((similarity * signal, pattern))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [pattern for _, pattern in scored[:limit]]

    def _save(self) -> None:
        atomic_write_json(
            self._path,
            {
                "version": SCHEMA_VERSION,
                "patterns": [p.to_dict() for p in self._patterns.values()],
            },
        )

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

    STABLE_PATH_FITNESS_THRESHOLD = 0.55

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
        if successful:
            return self.record_path_trial(
                pattern_id,
                task_run_id=task_run_id,
                successful=True,
                conflict_ref=conflict_ref,
                steps_saved=1,
                evidence_first=True,
            )
        pattern = self._get(pattern_id)
        pattern.trial_count += 1
        pattern.failure_count += 1
        pattern.conflict_refs.append(conflict_ref or f"task:{task_run_id}")
        pattern.status = PatternStatus.ROLLED_BACK
        pattern.rollback_reason = conflict_ref or f"failed validation: {task_run_id}"
        pattern.confidence = self._confidence(pattern)
        pattern.path_fitness_score = self._path_fitness(
            pattern,
            scope_match=True,
            recency_score=1.0,
        )
        self._patterns.update(pattern)
        return pattern

    def record_path_trial(
        self,
        pattern_id: str,
        *,
        task_run_id: str,
        successful: bool,
        steps_saved: int = 0,
        known_bad_avoided: int = 0,
        evidence_first: bool = False,
        false_trigger: bool = False,
        token_cost: float = 0.0,
        scope_match: bool = True,
        recency_score: float = 1.0,
        supersedes_pattern_ids: list[str] | None = None,
        conflict_ref: str = "",
    ) -> Pattern:
        pattern = self._get(pattern_id)
        pattern.trial_count += 1
        pattern.last_validated_at = pattern.updated_at
        if supersedes_pattern_ids:
            for pattern_id_ref in supersedes_pattern_ids:
                if pattern_id_ref not in pattern.supersedes_patterns:
                    pattern.supersedes_patterns.append(pattern_id_ref)
        pattern.average_step_delta = self._running_average(
            pattern.average_step_delta,
            pattern.trial_count,
            float(steps_saved),
        )
        pattern.average_token_cost = self._running_average(
            pattern.average_token_cost,
            pattern.trial_count,
            float(token_cost),
        )
        if known_bad_avoided > 0:
            pattern.known_bad_avoidance_count += int(known_bad_avoided)
        if evidence_first:
            pattern.evidence_first_count += 1
        if false_trigger:
            pattern.false_trigger_count += 1
        if successful:
            pattern.validation_task_runs.append(task_run_id)
            pattern.success_count += 1
        else:
            pattern.failure_count += 1
            pattern.conflict_refs.append(conflict_ref or f"task:{task_run_id}")
        if false_trigger and conflict_ref and conflict_ref not in pattern.challenged_by:
            pattern.challenged_by.append(conflict_ref)
        pattern.confidence = self._confidence(pattern)
        pattern.path_fitness_score = self._path_fitness(
            pattern,
            scope_match=scope_match,
            recency_score=recency_score,
        )
        if not successful and pattern.status == PatternStatus.STABLE:
            pattern.status = PatternStatus.CHALLENGED
            pattern.rollback_reason = conflict_ref or f"challenged by task: {task_run_id}"
        elif (
            pattern.false_trigger_count >= 2
            or pattern.failure_count > pattern.success_count
        ) and pattern.status in (PatternStatus.PROVISIONAL, PatternStatus.STABLE):
            pattern.status = PatternStatus.CHALLENGED
            pattern.rollback_reason = conflict_ref or "path challenged by repeated failures"
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
        if pattern.path_fitness_score < self.STABLE_PATH_FITNESS_THRESHOLD:
            raise ValueError(
                "stable Pattern requires sufficient path fitness "
                f"(>= {self.STABLE_PATH_FITNESS_THRESHOLD:.2f})"
            )
        pattern.status = PatternStatus.STABLE
        self._patterns.update(pattern)
        return pattern

    def select_best_path(
        self,
        query: str,
        *,
        scope: str = "project",
        limit: int = 3,
        threshold: float = 0.05,
    ) -> list[Pattern]:
        candidates = self._patterns.search(
            query,
            scope=scope,
            limit=max(limit * 3, 10),
            threshold=threshold,
        )
        ranked = [
            pattern for pattern in candidates
            if pattern.status not in {
                PatternStatus.ROLLED_BACK,
                PatternStatus.ARCHIVED,
                PatternStatus.CHALLENGED,
            }
        ]
        ranked.sort(
            key=lambda pattern: (
                pattern.path_fitness_score,
                pattern.confidence,
                token_jaccard(query, pattern.rule),
            ),
            reverse=True,
        )
        return ranked[:limit]

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

    @staticmethod
    def _running_average(current: float, count: int, value: float) -> float:
        if count <= 0:
            return value
        previous_total = current * (count - 1)
        return round((previous_total + value) / count, 4)

    @staticmethod
    def _confidence(pattern: Pattern) -> float:
        denominator = (
            pattern.success_count
            + pattern.failure_count
            + pattern.false_trigger_count
            + len(pattern.conflict_refs)
        )
        if denominator <= 0:
            return 0.0
        return round(pattern.success_count / denominator, 4)

    @staticmethod
    def _path_fitness(
        pattern: Pattern,
        *,
        scope_match: bool,
        recency_score: float,
    ) -> float:
        trial_count = max(pattern.trial_count, 1)
        success_rate = pattern.success_count / trial_count
        known_bad_gain = pattern.known_bad_avoidance_count / trial_count
        evidence_first_gain = pattern.evidence_first_count / trial_count
        repeatability = min(len(set(pattern.validation_task_runs)) / 3, 1.0)
        step_gain = max(pattern.average_step_delta, 0.0) / 5
        false_trigger_penalty = pattern.false_trigger_count / trial_count
        failure_penalty = pattern.failure_count / trial_count
        token_cost_penalty = min(pattern.average_token_cost / 2000, 1.0)
        score = (
            0.28 * success_rate
            + 0.18 * known_bad_gain
            + 0.14 * evidence_first_gain
            + 0.12 * repeatability
            + 0.12 * step_gain
            + 0.10 * max(min(recency_score, 1.0), 0.0)
            + 0.06 * (1.0 if scope_match else 0.0)
            - 0.10 * false_trigger_penalty
            - 0.08 * failure_penalty
            - 0.04 * token_cost_penalty
        )
        return round(max(0.0, min(score, 1.0)), 4)
