"""Procedural skill retrieval over Layer-3 patterns and avoidance memory."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from memoryweaver.composer import PatternComposer, PatternStore
from memoryweaver.retriever import VerifiedRetriever
from memoryweaver.router import InferenceMode, ModeRouter
from memoryweaver.schema import MemoryItem, MemoryType, Pattern, PatternStatus, Polarity
from memoryweaver.store import MemoryStore, token_jaccard


@dataclass
class ProceduralSkill:
    """A reusable procedural view projected from a Pattern."""

    pattern_id: str
    rule: str
    status: str
    confidence: float
    path_fitness_score: float = 0.0
    applies_when: list[str] = field(default_factory=list)
    avoid_when: list[str] = field(default_factory=list)
    success_path: list[str] = field(default_factory=list)
    failed_path: list[str] = field(default_factory=list)
    evidence_links: list[str] = field(default_factory=list)
    supporting_memory_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_pattern(cls, pattern: Pattern) -> "ProceduralSkill":
        return cls(
            pattern_id=pattern.id,
            rule=pattern.rule,
            status=pattern.status.value,
            confidence=pattern.confidence,
            path_fitness_score=pattern.path_fitness_score,
            applies_when=list(pattern.applies_when),
            avoid_when=list(pattern.avoid_when),
            success_path=list(pattern.success_path),
            failed_path=list(pattern.failed_path),
            evidence_links=list(pattern.evidence_links),
            supporting_memory_ids=list(pattern.composed_from),
        )


@dataclass
class SkillRetrievalResult:
    """Result of task-conditioning skill retrieval."""

    query: str
    scope: str
    recommended_mode: str
    route_reason: str
    skills: list[ProceduralSkill] = field(default_factory=list)
    avoidance_memories: list[MemoryItem] = field(default_factory=list)
    supporting_memories: list[MemoryItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "scope": self.scope,
            "recommended_mode": self.recommended_mode,
            "route_reason": self.route_reason,
            "skills": [skill.to_dict() for skill in self.skills],
            "avoidance_memories": [memory.to_dict() for memory in self.avoidance_memories],
            "supporting_memories": [memory.to_dict() for memory in self.supporting_memories],
        }

    def render_context(self) -> str:
        parts: list[str] = []
        if self.skills:
            parts.append("## Procedural Skills")
            for index, skill in enumerate(self.skills, 1):
                parts.append(
                    f"{index}. [{skill.status}] {skill.rule} "
                    f"(confidence={skill.confidence:.2f}, path_fitness={skill.path_fitness_score:.2f})"
                )
                if skill.failed_path:
                    parts.append(
                        f"   Avoid: {', '.join(skill.failed_path[:3])}"
                    )
                elif skill.avoid_when:
                    parts.append(
                        f"   Avoid when: {', '.join(skill.avoid_when[:3])}"
                    )
        if self.avoidance_memories:
            parts.append("")
            parts.append("## Avoidance Memory")
            for index, memory in enumerate(self.avoidance_memories, 1):
                parts.append(
                    f"{index}. [{memory.source.value}] {memory.content}"
                )
        return "\n".join(parts).strip()


class SkillRetriever:
    """Retrieve procedural skills and avoidance memory for task conditioning."""

    def __init__(
        self,
        memories: MemoryStore,
        patterns: PatternStore,
        *,
        retriever: VerifiedRetriever | None = None,
        router: ModeRouter | None = None,
    ) -> None:
        self._memories = memories
        self._patterns = patterns
        self._retriever = retriever or VerifiedRetriever(memories)
        self._router = router or ModeRouter(
            memories,
            retriever=self._retriever,
            pattern_store=patterns,
        )
        self._composer: PatternComposer | None = None

    def set_composer(self, composer: PatternComposer) -> None:
        self._composer = composer

    def retrieve(
        self,
        query: str,
        *,
        scope: str = "project",
        limit: int = 5,
        threshold: float = 0.05,
    ) -> SkillRetrievalResult:
        patterns = self._select_patterns(
            query,
            scope=scope,
            limit=limit,
            threshold=threshold,
        )
        skills = [ProceduralSkill.from_pattern(pattern) for pattern in patterns[:limit]]
        memories = self._retriever.search(
            query,
            limit=max(limit * 2, 8),
            scope=scope,
            threshold=threshold,
        )
        for skill in skills:
            for memory_id in skill.supporting_memory_ids:
                memory = self._memories.get(memory_id)
                if memory is not None and memory not in memories:
                    memories.append(memory)
        failed_paths = [
            path
            for skill in skills
            for path in skill.failed_path
        ]
        avoid_phrases = [
            phrase
            for skill in skills
            for phrase in skill.avoid_when
        ]
        avoidance = [
            memory for memory in memories
            if self._is_avoidance_memory(
                memory,
                failed_paths=failed_paths,
                avoid_phrases=avoid_phrases,
            )
        ][:limit]
        support = [
            memory for memory in memories
            if memory not in avoidance
        ][:limit]
        route = self._router.route(query, scope=scope)
        recommended_mode = route.mode.value
        if skills and recommended_mode == InferenceMode.THINKING.value:
            recommended_mode = InferenceMode.FAST_VERIFY.value
        elif (
            recommended_mode == InferenceMode.FAST.value
            and not any(skill.status == PatternStatus.STABLE.value for skill in skills)
        ):
            recommended_mode = InferenceMode.FAST_VERIFY.value
        return SkillRetrievalResult(
            query=query,
            scope=scope,
            recommended_mode=recommended_mode,
            route_reason=route.reason,
            skills=skills,
            avoidance_memories=avoidance,
            supporting_memories=support,
        )

    def _select_patterns(
        self,
        query: str,
        *,
        scope: str,
        limit: int,
        threshold: float,
    ) -> list[Pattern]:
        if self._composer is not None:
            selected = self._composer.select_best_path(
                query,
                scope=scope,
                limit=limit,
                threshold=threshold,
            )
            if selected:
                return selected
        return self._patterns.search(
            query,
            scope=scope,
            limit=max(limit, 8),
            threshold=threshold,
        )

    @staticmethod
    def _is_avoidance_memory(
        memory: MemoryItem,
        *,
        failed_paths: list[str],
        avoid_phrases: list[str],
    ) -> bool:
        if memory.polarity == Polarity.NEGATIVE:
            return True
        if memory.memory_type in {MemoryType.FAILED_ATTEMPT, MemoryType.AVOIDANCE_RULE}:
            return True
        for phrase in failed_paths + avoid_phrases:
            if token_jaccard(memory.content, phrase) >= 0.1:
                return True
        return False
