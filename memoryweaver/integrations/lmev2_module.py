"""MemoryWeaver module for LongMemEval-V2 style harnesses.

The module converts official LongMemEval-V2 question + history trajectory
records into MemoryWeaver RawSpan/ContextCapsule context. It can be used as a
backend inside an official harness without writing verified memory by default.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from memoryweaver.external.adapters import (
    adapt_external_record,
    build_candidate_memories,
    build_context_capsules,
    external_episode_to_raw_spans,
)
from memoryweaver.external.longmemeval_v2 import (
    lme_v2_question_to_external_record,
    load_lme_v2_haystack,
    load_lme_v2_questions,
    load_lme_v2_trajectories,
    resolve_lme_v2_root,
)
from memoryweaver.lifecycle import MemoryLifecycle
from memoryweaver.marker_context import capsules_for_marker_context
from memoryweaver.store import MemoryWorkspace


@dataclass
class MemoryWeaverContext:
    query: str
    evidence: list[dict[str, Any]] = field(default_factory=list)
    raw_refs: list[str] = field(default_factory=list)
    candidates: list[dict[str, Any]] = field(default_factory=list)
    markers: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "evidence": self.evidence,
            "raw_refs": self.raw_refs,
            "candidates": self.candidates,
            "markers": self.markers,
            "metrics": self.metrics,
        }


class MemoryWeaverModule:
    """LongMemEval-V2 context backend for MemoryWeaver."""

    def __init__(
        self,
        workspace: MemoryWorkspace,
        *,
        write_context: bool = True,
        write_memory: bool = False,
    ):
        self.workspace = workspace
        self.lifecycle = MemoryLifecycle(workspace)
        self.write_context = write_context
        self.write_memory = write_memory

    def build_context(
        self,
        question: dict[str, Any],
        history_trajectories: list[dict[str, Any]],
        *,
        states_per_trajectory: int = 5,
        max_observation_chars: int = 1800,
    ) -> MemoryWeaverContext:
        """Build MemoryWeaver context from one LME-V2 question and histories."""

        record = lme_v2_question_to_external_record(
            question,
            history_trajectories,
            states_per_trajectory=states_per_trajectory,
            max_observation_chars=max_observation_chars,
        )
        episode = adapt_external_record("longmemeval-v2", record)
        raw_spans = external_episode_to_raw_spans(episode)
        capsules = build_context_capsules(raw_spans)
        candidate_memories, policy_violations = build_candidate_memories(capsules)

        if self.write_context:
            for raw_span in raw_spans:
                self.workspace.raw_spans.add(raw_span)
            for capsule in capsules:
                self.workspace.context_capsules.add(capsule)
                self.workspace.tag_time_index.add(capsule)

        query_text = episode.queries[0].query if episode.queries else str(question.get("question", ""))
        retrieved = self.lifecycle.retrieve(query_text, threshold=0.05, limit=8)
        marker_contexts = self._marker_contexts_for_capsules()
        metrics = {
            "question_id": str(question.get("id", "")),
            "trajectory_count": len(history_trajectories),
            "raw_span_count": len(raw_spans),
            "capsule_count": len(capsules),
            "candidate_memory_count": len(candidate_memories),
            "retrieved_verified_memory_count": len(retrieved),
            "policy_gate_leak_count": len(policy_violations),
            "write_context": self.write_context,
            "write_memory": self.write_memory,
            "verified_memory_write_count": 0,
            "promotion_count": 0,
            "layer3_mutation_count": 0,
        }
        return MemoryWeaverContext(
            query=query_text,
            evidence=[
                {
                    "capsule_id": capsule.id,
                    "raw_ref_id": capsule.raw_ref_id,
                    "source": capsule.source.value,
                    "summary": capsule.summary,
                    "tags": capsule.tags,
                }
                for capsule in capsules[:20]
            ],
            raw_refs=[capsule.raw_ref_id for capsule in capsules],
            candidates=[memory.to_dict() for memory in candidate_memories[:20]],
            markers=marker_contexts,
            metrics=metrics,
        )

    def build_context_from_local_snapshot(
        self,
        root: Path | None = None,
        *,
        question_index: int = 0,
        trajectories_per_question: int = 5,
        states_per_trajectory: int = 5,
        haystack_name: str = "lme_v2_small.json",
        hf_cache_root: Path | None = None,
        allow_download: bool = False,
    ) -> MemoryWeaverContext:
        """Load one question from a local LME-V2 snapshot and build context."""

        resolved_root, _ = resolve_lme_v2_root(
            root,
            hf_cache_root=hf_cache_root,
            allow_download=allow_download,
            download_root=root,
        )
        questions = load_lme_v2_questions(resolved_root, limit=question_index + 1)
        if question_index >= len(questions):
            raise IndexError(f"question_index {question_index} out of range")
        question = questions[question_index]
        haystack = load_lme_v2_haystack(resolved_root, name=haystack_name)
        refs = haystack.get(str(question.get("id", "")), [])[:trajectories_per_question]
        trajectories = load_lme_v2_trajectories(resolved_root, set(refs))
        return self.build_context(
            question,
            [trajectories[ref] for ref in refs if ref in trajectories],
            states_per_trajectory=states_per_trajectory,
        )

    def _marker_contexts_for_capsules(self) -> list[dict[str, Any]]:
        markers: list[dict[str, Any]] = []
        for marker_context in self.workspace.marker_evidence_contexts.list_all():
            capsules = capsules_for_marker_context(
                marker_context,
                self.workspace.context_capsules,
                self.workspace.tag_time_index,
                limit=5,
            )
            if capsules:
                markers.append(
                    {
                        "marker_id": marker_context.marker_id,
                        "matched_capsule_ids": [capsule.id for capsule in capsules],
                        "required_tags": marker_context.required_tags,
                        "metadata": marker_context.metadata,
                    }
                )
        return markers
