"""Experience Transfer Protocol.

The protocol measures whether verified experience from a source episode family
changes behavior on sibling target tasks.

Arms:
  A. no_memory
  B. raw_rag_over_logs
  C. mw_verified_memory
  D. mw_verified_memory_marker

This module is intentionally small and deterministic so it can run in CI. The
agent policy is replaceable; later LLM runs can reuse the same family/arm
structure and output schema.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import mean
from typing import Any, Protocol

from memoryweaver.lifecycle import MemoryLifecycle
from memoryweaver.runtime import LiveAction, LiveObservation
from memoryweaver.runtime_authority import create_runtime_authority
from memoryweaver.schema import Freshness, MemoryType, Polarity, Source
from memoryweaver.store import MemoryWorkspace


ARMS = [
    "no_memory",
    "raw_rag_over_logs",
    "mw_verified_memory",
    "mw_verified_memory_marker",
]

RANDOM_EXPERIENCE_ARMS = [
    "fresh_no_memory",
    "random_experience_raw_logs",
    "random_experience_naive_memory",
    "mw_verified_experience",
    "mw_verified_experience_marker",
]


@dataclass
class ExperienceTargetTask:
    task_id: str
    query: str
    required_evidence: list[str]
    known_bad_actions: list[str]
    success_target: str
    similarity_bucket: str = "high"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExperienceFamily:
    family_id: str
    title: str
    source_success: str
    source_failure: str
    tags: list[str]
    required_evidence: list[str]
    known_bad_actions: list[str]
    target_tasks: list[ExperienceTargetTask] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExperienceTransferResult:
    passed: bool
    families: list[dict[str, Any]]
    task_runs: list[dict[str, Any]]
    arm_metrics: dict[str, Any]
    marker_only_arm_metrics: dict[str, Any]
    decision_probe: list[dict[str, Any]]
    probe_metrics: dict[str, Any]
    memory_use_probe: list[dict[str, Any]]
    memory_use_summary: dict[str, Any]
    cost_metrics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RandomExperienceAccumulationResult:
    passed: bool
    families: list[dict[str, Any]]
    task_runs: list[dict[str, Any]]
    arm_metrics: dict[str, Any]
    cost_metrics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TransferAgent:
    """Deterministic transfer agent with context-sensitive decisions."""

    def choose_action(
        self,
        *,
        step: int,
        query: str,
        memory_context: str,
        raw_context: str,
        previous_results: list[dict[str, Any]],
        required_evidence: list[str],
        known_bad_actions: list[str],
    ) -> LiveAction:
        context = f"{memory_context}\n{raw_context}".lower()
        previous = " ".join(str(item.get("status", "")) for item in previous_results).lower()
        if "selected organization" in context or "entitlement" in context or "organization" in context:
            return LiveAction(
                name="check_evidence",
                target=required_evidence[0],
                reasoning="Experience context points to required evidence.",
            )
        if "known bad paths" in context or "avoid" in context:
            return LiveAction(
                name="check_evidence",
                target=required_evidence[0],
                reasoning="Avoidance context suppresses known bad action.",
            )
        if "failed_known_bad" in previous and step >= 2:
            return LiveAction(
                name="check_evidence",
                target=required_evidence[0],
                reasoning="Tool failure forces fallback to evidence.",
            )
        if raw_context and step == 1:
            return LiveAction(
                name="tool_call",
                target=known_bad_actions[0],
                reasoning="Raw logs mention this attempted path without safety labels.",
            )
        if step == 1:
            return LiveAction(
                name="tool_call",
                target=known_bad_actions[0],
                reasoning="Fresh agent tries common fix first.",
            )
        if step == 2:
            return LiveAction(
                name="tool_call",
                target="generic_debugging",
                reasoning="Try broad debugging after first failure.",
            )
        return LiveAction(
            name="check_evidence",
            target=required_evidence[0],
            reasoning="Fallback to direct evidence check.",
        )


class TransferAgentProtocol(Protocol):
    online_llm_call_count: int

    def choose_action(
        self,
        *,
        step: int,
        query: str,
        memory_context: str,
        raw_context: str,
        previous_results: list[dict[str, Any]],
        required_evidence: list[str],
        known_bad_actions: list[str],
    ) -> LiveAction: ...


class ExperienceLLMAgentAdapter:
    """Adapter for LLM-like agents that choose from a text context."""

    def __init__(self, llm_agent: Any):
        self.llm_agent = llm_agent

    @property
    def online_llm_call_count(self) -> int:
        return int(getattr(self.llm_agent, "online_llm_call_count", 0))

    def choose_action(
        self,
        *,
        step: int,
        query: str,
        memory_context: str,
        raw_context: str,
        previous_results: list[dict[str, Any]],
        required_evidence: list[str],
        known_bad_actions: list[str],
    ) -> LiveAction:
        aliases = _action_aliases(required_evidence, known_bad_actions)
        state: dict[str, Any] = {
            "available_actions": list(aliases),
        }
        if memory_context:
            state["recommended_evidence"] = [_canonical_to_alias(item, aliases) for item in required_evidence]
            state["known_bad_actions"] = [_canonical_to_alias(item, aliases) for item in known_bad_actions]
        observation = LiveObservation(
            task_id="experience_transfer",
            goal=query,
            state=state,
            history=previous_results,
        )
        context_parts = [memory_context, raw_context]
        if memory_context:
            context_parts.append(f"Required evidence: {', '.join(required_evidence)}")
            context_parts.append(f"Known bad actions: {', '.join(known_bad_actions)}")
        context = "\n".join(part for part in context_parts if part)
        action = self.llm_agent.choose_action(observation, context, step=step)
        canonical_target = _resolve_llm_target(
            action.target,
            aliases,
            semantic_context=context,
        )
        return LiveAction(
            name=action.name,
            target=canonical_target,
            reasoning=action.reasoning,
        )


class FamilyEnv:
    """Small deterministic target task environment."""

    def __init__(self, target: ExperienceTargetTask):
        self.target = target
        self.observation = LiveObservation(
            task_id=target.task_id,
            goal=target.query,
            state={"resolved": False},
        )

    def reset(self) -> LiveObservation:
        self.observation = LiveObservation(
            task_id=self.target.task_id,
            goal=self.target.query,
            state={"resolved": False},
            history=[],
        )
        return self.observation

    def step(self, action: LiveAction) -> tuple[LiveObservation, dict[str, Any]]:
        target = action.target.lower()
        if target == "__invalid_action__":
            result = {
                "status": "invalid_action",
                "signal": "neutral",
                "evidence": f"{action.target} is not an executable action for {self.target.task_id}",
            }
        elif any(bad.lower() in target for bad in self.target.known_bad_actions):
            result = {
                "status": "failed_known_bad",
                "signal": "negative",
                "evidence": f"{action.target} did not resolve {self.target.task_id}",
            }
        elif any(required.lower() in target for required in self.target.required_evidence):
            self.observation.done = True
            self.observation.success = True
            self.observation.state["resolved"] = True
            result = {
                "status": "evidence_observed",
                "signal": "positive",
                "evidence": f"{action.target} resolved {self.target.task_id}",
            }
        else:
            result = {
                "status": "no_signal",
                "signal": "neutral",
                "evidence": f"{action.target} produced no useful signal",
            }
        self.observation.history.append({"action": action.to_dict(), "result": result})
        return self.observation, result


class ExperienceTransferProtocol:
    def __init__(
        self,
        *,
        workspace_root: Path,
        families: list[ExperienceFamily] | None = None,
        max_steps: int = 6,
        agent_factory: Any | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root)
        self.families = families or default_experience_families()
        self.max_steps = max_steps
        self.agent_factory = agent_factory or (lambda: TransferAgent())

    def run(self) -> ExperienceTransferResult:
        task_runs: list[dict[str, Any]] = []
        decision_probe: list[dict[str, Any]] = []
        memory_use_probe: list[dict[str, Any]] = []
        for family in self.families:
            for arm in ARMS:
                workspace = MemoryWorkspace(self.workspace_root / family.family_id / arm)
                lifecycle = MemoryLifecycle(workspace)
                if arm in {"mw_verified_memory", "mw_verified_memory_marker"}:
                    self._learn_source_episode(family, lifecycle)
                for target in family.target_tasks:
                    run = self._run_target(family, target, arm, workspace)
                    task_runs.append(run)
                    decision_probe.append(run["decision_probe"])
                    memory_use_probe.append(run["memory_use_probe"])
        main_runs = [run for run in task_runs if not run["marker_only_boundary"]]
        marker_only_runs = [run for run in task_runs if run["marker_only_boundary"]]
        arm_metrics = _arm_metrics(main_runs)
        marker_only_arm_metrics = _arm_metrics(marker_only_runs)
        probe_metrics = _probe_metrics(decision_probe)
        memory_use_summary = _memory_use_summary(memory_use_probe)
        cost_metrics = _cost_metrics(task_runs)
        main_suite_passed = (
            arm_metrics["mw_verified_memory"]["average_steps_to_success"]
            < arm_metrics["no_memory"]["average_steps_to_success"]
            and arm_metrics["mw_verified_memory_marker"]["known_bad_action_attempts"]
            <= arm_metrics["mw_verified_memory"]["known_bad_action_attempts"]
            and arm_metrics["mw_verified_memory"]["retrieval_hit_before_critical_action_rate"] > 0
        )
        marker_only_present = any(run["marker_only_boundary"] for run in task_runs)
        marker_only_boundary_passed = (
            not marker_only_present
            or (
                marker_only_arm_metrics["mw_verified_memory"]["critical_action_changed_by_memory_rate"] == 0
                and marker_only_arm_metrics["mw_verified_memory_marker"]["marker_direct_action_change_count"] > 0
                and marker_only_arm_metrics["mw_verified_memory_marker"]["known_bad_action_attempts"] == 0
            )
        )
        passed = main_suite_passed and marker_only_boundary_passed
        return ExperienceTransferResult(
            passed=passed,
            families=[family.to_dict() for family in self.families],
            task_runs=task_runs,
            arm_metrics=arm_metrics,
            marker_only_arm_metrics=marker_only_arm_metrics,
            decision_probe=decision_probe,
            probe_metrics=probe_metrics,
            memory_use_probe=memory_use_probe,
            memory_use_summary=memory_use_summary,
            cost_metrics=cost_metrics,
        )

    def _learn_source_episode(
        self,
        family: ExperienceFamily,
        lifecycle: MemoryLifecycle,
    ) -> None:
        lifecycle.write_verified_memory(
            memory_id=f"mem_{family.family_id}_success",
            content=family.source_success,
            source=Source.TOOL,
            tags=family.tags + family.required_evidence,
            evidence_text=family.source_success,
            evidence_uri=f"experience://{family.family_id}/source/success",
            polarity=Polarity.POSITIVE,
            memory_type=MemoryType.SUCCESS_PATH,
            confidence=0.86,
            freshness=Freshness.STABLE,
            promote=True,
        )
        lifecycle.write_verified_memory(
            memory_id=f"mem_{family.family_id}_failure",
            content=family.source_failure,
            source=Source.TOOL,
            tags=family.tags + family.known_bad_actions + ["known_bad_path"],
            evidence_text=family.source_failure,
            evidence_uri=f"experience://{family.family_id}/source/failure",
            polarity=Polarity.NEGATIVE,
            memory_type=MemoryType.FAILED_ATTEMPT,
            confidence=0.84,
            freshness=Freshness.STABLE,
            promote=True,
        )

    def _run_target(
        self,
        family: ExperienceFamily,
        target: ExperienceTargetTask,
        arm: str,
        workspace: MemoryWorkspace,
    ) -> dict[str, Any]:
        marker_only_boundary = family.family_id.startswith("marker_only_")
        suite = "marker_only_boundary" if marker_only_boundary else "main_suite"
        env = FamilyEnv(target)
        observation = env.reset()
        agent = self.agent_factory()
        authority = create_runtime_authority(
            workspace.memories,
            markers=[
                {
                    "id": f"marker_{family.family_id}",
                    "marker_type": "guard",
                    "level": "L3_guard",
                    "trigger_tags": family.tags,
                    "trigger_query_patterns": family.tags,
                    "suppressed_actions": family.known_bad_actions,
                    "required_evidence": family.required_evidence,
                    "recommended_route": "fast_verify",
                    "max_route": "fast_verify",
                    "status": "active",
                }
            ],
        )
        previous_results: list[dict[str, Any]] = []
        steps: list[dict[str, Any]] = []
        retrieval_hit_before_critical = False
        first_required_evidence_step = 0
        known_bad_attempts = 0
        invalid_action_count = 0
        tool_call_count = 0
        start_llm_calls = int(getattr(agent, "online_llm_call_count", 0))
        raw_context = self._raw_context(family) if arm == "raw_rag_over_logs" else ""
        for step in range(1, self.max_steps + 1):
            runtime_arm = {
                "no_memory": "no_memory",
                "raw_rag_over_logs": "no_memory",
                "mw_verified_memory": "mw_memory",
                "mw_verified_memory_marker": "mw_marker",
            }[arm]
            candidate_ids = None
            if arm in {"mw_verified_memory", "mw_verified_memory_marker"}:
                if marker_only_boundary:
                    candidate_ids = []
                else:
                    candidate_ids = [
                        item.id
                        for item in workspace.memories.find_by_tags(family.tags)
                    ]
            decision = authority.evaluate(
                target.query,
                tags=family.tags,
                arm=runtime_arm,
                step=step,
                candidate_ids=candidate_ids,
            )
            memory_context = authority.build_context(decision)
            if decision.allowed_memories and first_required_evidence_step == 0:
                retrieval_hit_before_critical = True
            action = agent.choose_action(
                step=step,
                query=target.query,
                memory_context=memory_context,
                raw_context=raw_context,
                previous_results=previous_results,
                required_evidence=target.required_evidence,
                known_bad_actions=target.known_bad_actions,
            )
            observation, result = env.step(action)
            previous_results.append(result)
            if action.name in {"tool_call", "check_evidence"}:
                tool_call_count += 1
            if result["status"] == "failed_known_bad":
                known_bad_attempts += 1
            if result["status"] == "invalid_action":
                invalid_action_count += 1
            if result["status"] == "evidence_observed" and not first_required_evidence_step:
                first_required_evidence_step = step
            steps.append(
                {
                    "step": step,
                    "memory_context": memory_context,
                    "raw_context": raw_context,
                    "decision": {
                        "marker_activated": decision.marker_activated,
                        "marker_id": decision.marker_id,
                        "allowed_memory_ids": [item.id for item in decision.allowed_memories],
                        "suppressed_actions": decision.suppressed_actions,
                        "required_evidence": decision.required_evidence,
                    },
                    "action": action.to_dict(),
                    "result": result,
                }
            )
            if observation.done:
                break
        critical_action_changed_by_memory = (
            arm in {"mw_verified_memory", "mw_verified_memory_marker"}
            and first_required_evidence_step == 1
        )
        marker_direct_action_change = (
            arm == "mw_verified_memory_marker"
            and steps
            and bool(steps[0]["decision"]["marker_activated"])
            and not steps[0]["decision"]["allowed_memory_ids"]
            and steps[0]["action"]["target"] != target.known_bad_actions[0]
        )
        marker_added_value = (
            arm == "mw_verified_memory_marker"
            and first_required_evidence_step == 1
        )
        decision_probe = _decision_probe(
            family=family,
            target=target,
            arm=arm,
            suite=suite,
            action_without_memory=target.known_bad_actions[0],
            action_with_context=steps[0]["action"]["target"] if steps else "",
        )
        memory_use_reason = _memory_use_reason(
            arm=arm,
            marker_only_boundary=marker_only_boundary,
            retrieval_hit_before_critical_action=retrieval_hit_before_critical,
            critical_action_changed_by_memory=critical_action_changed_by_memory,
            marker_direct_action_change=marker_direct_action_change,
        )
        memory_use_probe = {
            "family_id": family.family_id,
            "task_id": target.task_id,
            "arm": arm,
            "suite": suite,
            "marker_only_boundary": marker_only_boundary,
            "retrieval_hit_before_critical_action": retrieval_hit_before_critical,
            "critical_action_changed_by_memory": critical_action_changed_by_memory,
            "allowed_memory_ids_first_step": steps[0]["decision"]["allowed_memory_ids"] if steps else [],
            "memory_use_reason": memory_use_reason,
        }
        prompt_chars = sum(
            len(step["memory_context"]) + len(step["raw_context"]) + len(target.query)
            for step in steps
        )
        return {
            "family_id": family.family_id,
            "task_id": target.task_id,
            "arm": arm,
            "suite": suite,
            "marker_only_boundary": marker_only_boundary,
            "similarity_bucket": target.similarity_bucket,
            "success": observation.success,
            "steps_to_success": len(steps),
            "known_bad_action_attempts": known_bad_attempts,
            "invalid_action_count": invalid_action_count,
            "tool_call_count": tool_call_count,
            "first_required_evidence_step": first_required_evidence_step,
            "retrieval_hit_before_critical_action": retrieval_hit_before_critical,
            "critical_action_changed_by_memory": critical_action_changed_by_memory,
            "marker_direct_action_change": marker_direct_action_change,
            "marker_added_value": marker_added_value,
            "user_correction_count": 0,
            "verified_memory_write_count": 2 if arm in {"mw_verified_memory", "mw_verified_memory_marker"} else 0,
            "promotion_count": 2 if arm in {"mw_verified_memory", "mw_verified_memory_marker"} else 0,
            "rollback_count": 0,
            "online_llm_call_count": int(getattr(agent, "online_llm_call_count", 0)) - start_llm_calls,
            "prompt_char_count": prompt_chars,
            "token_estimate": max(1, prompt_chars // 4),
            "steps": steps,
            "decision_probe": decision_probe,
            "memory_use_probe": memory_use_probe,
        }

    @staticmethod
    def _raw_context(family: ExperienceFamily) -> str:
        return (
            f"Raw historical log: {family.source_failure}\n"
            f"Raw historical log: {family.source_success}\n"
            "No source gate, no polarity labels, no marker eligibility."
        )


def default_experience_families() -> list[ExperienceFamily]:
    seeds = [
        (
            "codex_subscription_org",
            "Codex subscription entitlement",
            ["codex", "subscription", "auth"],
            "selected_organization",
            "reinstall_npm",
        ),
        (
            "npm_registry_conflict",
            "npm registry dependency conflict",
            ["npm", "registry", "dependency"],
            "npm_registry",
            "delete_lockfile",
        ),
        (
            "docker_build_warning",
            "Docker build warning triage",
            ["docker", "build", "warning"],
            "docker_config",
            "docker_push_latest",
        ),
        (
            "ci_timeout_logs",
            "CI timeout diagnosis",
            ["ci", "timeout", "logs"],
            "ci_logs",
            "rerun_without_logs",
        ),
        (
            "api_key_scope_denied",
            "API key scope denied",
            ["api_key", "scope", "denied"],
            "api_key_scope",
            "rotate_key_blindly",
        ),
        (
            "marker_only_subscription_guard",
            "Marker-only subscription guard",
            ["marker_only", "subscription", "guard"],
            "organization_guardrail",
            "reset_auth_files",
        ),
    ]
    families: list[ExperienceFamily] = []
    for family_id, title, tags, evidence, bad in seeds:
        targets = [
            ExperienceTargetTask(
                task_id=f"{family_id}_target_{index}",
                query=f"{title} sibling task {index}: the issue recurred under different wording; choose the next diagnostic step.",
                required_evidence=[evidence],
                known_bad_actions=[bad],
                success_target=evidence,
                similarity_bucket="high" if index < 3 else "medium",
            )
            for index in range(1, 4)
        ]
        families.append(
            ExperienceFamily(
                family_id=family_id,
                title=title,
                source_success=f"Previous source episode succeeded after checking {evidence}.",
                source_failure=f"Previous source episode failed when trying {bad} first.",
                tags=tags,
                required_evidence=[evidence],
                known_bad_actions=[bad],
                target_tasks=targets,
            )
        )
    return families


class RandomExperienceAccumulationProtocol:
    """Measure false triggers from random/noisy prior experience.

    This protocol complements ExperienceTransferProtocol. It uses the same
    target families but replaces curated source experience with unrelated or
    misleading prior episodes for the raw/naive arms.
    """

    def __init__(
        self,
        *,
        workspace_root: Path,
        families: list[ExperienceFamily] | None = None,
        max_steps: int = 6,
        agent_factory: Any | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root)
        self.families = families or default_experience_families()
        self.max_steps = max_steps
        self.agent_factory = agent_factory or (lambda: TransferAgent())

    def run(self) -> RandomExperienceAccumulationResult:
        task_runs: list[dict[str, Any]] = []
        for family in self.families:
            for arm in RANDOM_EXPERIENCE_ARMS:
                workspace = MemoryWorkspace(self.workspace_root / family.family_id / arm)
                lifecycle = MemoryLifecycle(workspace)
                if arm in {"mw_verified_experience", "mw_verified_experience_marker"}:
                    ExperienceTransferProtocol._learn_source_episode(self, family, lifecycle)
                for target in family.target_tasks:
                    task_runs.append(self._run_target(family, target, arm, workspace))
        arm_metrics = _random_arm_metrics(task_runs)
        cost_metrics = _random_cost_metrics(task_runs)
        noisy_failure_or_trigger = any(
            arm_metrics[arm]["false_trigger_rate"] > 0
            or arm_metrics[arm]["success_rate"] < arm_metrics["mw_verified_experience"]["success_rate"]
            for arm in ("random_experience_raw_logs", "random_experience_naive_memory")
        )
        passed = (
            noisy_failure_or_trigger
            and arm_metrics["mw_verified_experience"]["success_rate"] > 0
            and arm_metrics["mw_verified_experience"]["false_trigger_rate"] == 0
            and arm_metrics["mw_verified_experience_marker"]["false_trigger_rate"] == 0
        )
        return RandomExperienceAccumulationResult(
            passed=passed,
            families=[family.to_dict() for family in self.families],
            task_runs=task_runs,
            arm_metrics=arm_metrics,
            cost_metrics=cost_metrics,
        )

    def _run_target(
        self,
        family: ExperienceFamily,
        target: ExperienceTargetTask,
        arm: str,
        workspace: MemoryWorkspace,
    ) -> dict[str, Any]:
        env = FamilyEnv(target)
        observation = env.reset()
        agent = self.agent_factory()
        authority = create_runtime_authority(
            workspace.memories,
            markers=[
                {
                    "id": f"marker_{family.family_id}",
                    "marker_type": "guard",
                    "level": "L3_guard",
                    "trigger_tags": family.tags,
                    "trigger_query_patterns": family.tags,
                    "suppressed_actions": family.known_bad_actions,
                    "required_evidence": family.required_evidence,
                    "recommended_route": "fast_verify",
                    "max_route": "fast_verify",
                    "status": "active",
                }
            ],
        )
        previous_results: list[dict[str, Any]] = []
        steps: list[dict[str, Any]] = []
        first_required_evidence_step = 0
        known_bad_attempts = 0
        invalid_action_count = 0
        tool_call_count = 0
        retrieval_hit_before_critical = False
        start_llm_calls = int(getattr(agent, "online_llm_call_count", 0))
        raw_context = self._random_raw_context(family) if arm == "random_experience_raw_logs" else ""
        if arm == "random_experience_naive_memory":
            raw_context = self._naive_memory_context(family)
        for step in range(1, self.max_steps + 1):
            runtime_arm = {
                "fresh_no_memory": "no_memory",
                "random_experience_raw_logs": "no_memory",
                "random_experience_naive_memory": "no_memory",
                "mw_verified_experience": "mw_memory",
                "mw_verified_experience_marker": "mw_marker",
            }[arm]
            candidate_ids = None
            if arm in {"mw_verified_experience", "mw_verified_experience_marker"}:
                candidate_ids = [
                    item.id
                    for item in workspace.memories.find_by_tags(family.tags)
                ]
            decision = authority.evaluate(
                target.query,
                tags=family.tags,
                arm=runtime_arm,
                step=step,
                candidate_ids=candidate_ids,
            )
            memory_context = authority.build_context(decision)
            if decision.allowed_memories and first_required_evidence_step == 0:
                retrieval_hit_before_critical = True
            action = agent.choose_action(
                step=step,
                query=target.query,
                memory_context=memory_context,
                raw_context=raw_context,
                previous_results=previous_results,
                required_evidence=target.required_evidence,
                known_bad_actions=target.known_bad_actions,
            )
            observation, result = env.step(action)
            previous_results.append(result)
            if action.name in {"tool_call", "check_evidence"}:
                tool_call_count += 1
            if result["status"] == "failed_known_bad":
                known_bad_attempts += 1
            if result["status"] == "invalid_action":
                invalid_action_count += 1
            if result["status"] == "evidence_observed" and not first_required_evidence_step:
                first_required_evidence_step = step
            steps.append(
                {
                    "step": step,
                    "memory_context": memory_context,
                    "raw_context": raw_context,
                    "action": action.to_dict(),
                    "result": result,
                    "decision": {
                        "marker_activated": decision.marker_activated,
                        "marker_id": decision.marker_id,
                        "allowed_memory_ids": [item.id for item in decision.allowed_memories],
                        "suppressed_actions": decision.suppressed_actions,
                        "required_evidence": decision.required_evidence,
                    },
                }
            )
            if observation.done:
                break
        prompt_chars = sum(
            len(step["memory_context"]) + len(step["raw_context"]) + len(target.query)
            for step in steps
        )
        return {
            "family_id": family.family_id,
            "task_id": target.task_id,
            "arm": arm,
            "success": observation.success,
            "steps_to_success": len(steps),
            "known_bad_action_attempts": known_bad_attempts,
            "invalid_action_count": invalid_action_count,
            "false_trigger": arm.startswith("random_experience") and known_bad_attempts > 0,
            "spurious_retrieval": arm.startswith("random_experience") and known_bad_attempts > 0,
            "irrelevant_memory_injection": arm == "random_experience_naive_memory" and known_bad_attempts > 0,
            "tool_call_count": tool_call_count,
            "first_required_evidence_step": first_required_evidence_step,
            "retrieval_hit_before_critical_action": retrieval_hit_before_critical,
            "verified_memory_write_count": 2 if arm in {"mw_verified_experience", "mw_verified_experience_marker"} else 0,
            "promotion_count": 2 if arm in {"mw_verified_experience", "mw_verified_experience_marker"} else 0,
            "online_llm_call_count": int(getattr(agent, "online_llm_call_count", 0)) - start_llm_calls,
            "prompt_char_count": prompt_chars,
            "token_estimate": max(1, prompt_chars // 4),
            "steps": steps,
        }

    @staticmethod
    def _random_raw_context(family: ExperienceFamily) -> str:
        bad = family.known_bad_actions[0]
        return (
            "Random prior experience logs from unrelated tasks:\n"
            f"- A different project appeared to succeed after trying {bad}.\n"
            f"- Another assistant suggested {bad} for a superficially similar issue.\n"
            "- No source gate, no scope check, no evidence validation.\n"
            "- These logs were not verified against the current task family."
        )

    @staticmethod
    def _naive_memory_context(family: ExperienceFamily) -> str:
        bad = family.known_bad_actions[0]
        return (
            "## Naive Memory Context\n"
            f"1. [assistant] Prior memory says {bad} resolved a similar issue.\n"
            f"2. [synthetic] Hypothesis: {bad} should be attempted first.\n"
            "No polarity gate, no evidence link, no runtime eligibility check."
        )


def _decision_probe(
    *,
    family: ExperienceFamily,
    target: ExperienceTargetTask,
    arm: str,
    suite: str,
    action_without_memory: str,
    action_with_context: str,
) -> dict[str, Any]:
    changed = action_without_memory != action_with_context
    probe_valid = bool(action_with_context) and action_with_context != "__invalid_action__"
    return {
        "family_id": family.family_id,
        "task_id": target.task_id,
        "arm": arm,
        "suite": suite,
        "probe_type": "context_action_change",
        "trap_observation": "POISON_RESULT_SENTINEL",
        "action_without_memory": action_without_memory,
        "action_with_context": action_with_context,
        "decision_changed": changed,
        "probe_valid": probe_valid,
        "decision_changed_valid": probe_valid and changed,
    }


def _memory_use_reason(
    *,
    arm: str,
    marker_only_boundary: bool,
    retrieval_hit_before_critical_action: bool,
    critical_action_changed_by_memory: bool,
    marker_direct_action_change: bool,
) -> str:
    if arm == "no_memory":
        return "no_memory_arm"
    if arm == "raw_rag_over_logs":
        if critical_action_changed_by_memory:
            return "raw_context_changed_action"
        return "raw_context_no_retrieval"
    if arm == "mw_verified_memory":
        if retrieval_hit_before_critical_action:
            return "retrieval_hit"
        if marker_only_boundary:
            return "marker_required"
        return "retrieval_miss"
    if arm == "mw_verified_memory_marker":
        if retrieval_hit_before_critical_action:
            return "retrieval_hit"
        if marker_direct_action_change:
            return "marker_direct_guard"
        return "retrieval_miss"
    return "unknown"


def _action_aliases(
    required_evidence: list[str],
    known_bad_actions: list[str],
) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for index, canonical in enumerate(known_bad_actions + required_evidence + ["generic_debugging"], start=1):
        aliases[f"action_{index}"] = canonical
    return aliases


def _canonical_to_alias(canonical: str, aliases: dict[str, str]) -> str:
    for alias, value in aliases.items():
        if value == canonical:
            return alias
    return canonical


def _resolve_llm_target(
    target: str,
    aliases: dict[str, str],
    *,
    semantic_context: str,
) -> str:
    normalized = target.strip()
    if normalized in aliases:
        return aliases[normalized]
    lowered = normalized.lower()
    semantic_lower = semantic_context.lower()
    for alias, canonical in aliases.items():
        if alias.lower() in lowered:
            return canonical
        if semantic_context and canonical.lower() in lowered and canonical.lower() in semantic_lower:
            return canonical
    return "__invalid_action__"


def _arm_metrics(task_runs: list[dict[str, Any]]) -> dict[str, Any]:
    by_arm: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run in task_runs:
        by_arm[run["arm"]].append(run)
    result: dict[str, Any] = {}
    for arm in ARMS:
        runs = by_arm.get(arm, [])
        result[arm] = {
            "task_count": len(runs),
            "success_rate": _avg(run["success"] for run in runs),
            "average_steps_to_success": round(mean(run["steps_to_success"] for run in runs), 4) if runs else 0.0,
            "known_bad_action_attempts": sum(run["known_bad_action_attempts"] for run in runs),
            "invalid_action_count": sum(run["invalid_action_count"] for run in runs),
            "average_tool_call_count": round(mean(run["tool_call_count"] for run in runs), 4) if runs else 0.0,
            "required_evidence_first_hit_rate": _avg(run["first_required_evidence_step"] == 1 for run in runs),
            "average_first_required_evidence_step": round(mean(run["first_required_evidence_step"] for run in runs), 4) if runs else 0.0,
            "retrieval_hit_before_critical_action_rate": _avg(run["retrieval_hit_before_critical_action"] for run in runs),
            "critical_action_changed_by_memory_rate": _avg(run["critical_action_changed_by_memory"] for run in runs),
            "marker_direct_action_change_count": sum(run["marker_direct_action_change"] for run in runs),
            "marker_added_value_count": sum(run["marker_added_value"] for run in runs),
            "average_token_estimate": round(mean(run["token_estimate"] for run in runs), 4) if runs else 0.0,
            "verified_memory_write_count": sum(run["verified_memory_write_count"] for run in runs),
            "promotion_count": sum(run["promotion_count"] for run in runs),
            "online_llm_call_count": sum(run["online_llm_call_count"] for run in runs),
        }
    return result


def _probe_metrics(decision_probe: list[dict[str, Any]]) -> dict[str, Any]:
    by_suite: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for probe in decision_probe:
        by_suite[str(probe.get("suite", "main_suite"))].append(probe)
    result: dict[str, Any] = {}
    for suite, probes in by_suite.items():
        by_arm: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for probe in probes:
            by_arm[str(probe["arm"])].append(probe)
        result[suite] = {}
        for arm in ARMS:
            arm_probes = by_arm.get(arm, [])
            result[suite][arm] = {
                "probe_count": len(arm_probes),
                "probe_valid_count": sum(bool(probe["probe_valid"]) for probe in arm_probes),
                "invalid_probe_count": sum(not bool(probe["probe_valid"]) for probe in arm_probes),
                "decision_changed_count": sum(bool(probe["decision_changed"]) for probe in arm_probes),
                "decision_changed_valid_count": sum(
                    bool(probe["decision_changed_valid"]) for probe in arm_probes
                ),
                "decision_changed_valid_rate": _avg(
                    bool(probe["decision_changed_valid"]) for probe in arm_probes
                ),
            }
    return result


def _memory_use_summary(memory_use_probe: list[dict[str, Any]]) -> dict[str, Any]:
    by_arm: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for probe in memory_use_probe:
        by_arm[str(probe["arm"])].append(probe)
    result: dict[str, Any] = {}
    for arm in ARMS:
        probes = by_arm.get(arm, [])
        reasons: dict[str, int] = defaultdict(int)
        for probe in probes:
            reasons[str(probe.get("memory_use_reason", "unknown"))] += 1
        result[arm] = {
            "probe_count": len(probes),
            "reason_counts": dict(sorted(reasons.items())),
            "marker_required_count": reasons.get("marker_required", 0),
            "retrieval_miss_count": reasons.get("retrieval_miss", 0),
            "retrieval_hit_count": reasons.get("retrieval_hit", 0),
        }
    return result


def _cost_metrics(task_runs: list[dict[str, Any]]) -> dict[str, Any]:
    by_arm: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run in task_runs:
        by_arm[run["arm"]].append(run)
    base = mean(run["token_estimate"] for run in by_arm["no_memory"]) if by_arm["no_memory"] else 0.0
    result = {}
    for arm, runs in by_arm.items():
        avg = mean(run["token_estimate"] for run in runs) if runs else 0.0
        success_count = sum(1 for run in runs if run["success"])
        result[arm] = {
            "average_token_estimate": round(avg, 4),
            "token_overhead_vs_no_memory": round(avg - base, 4),
            "token_per_successful_task": round(sum(run["token_estimate"] for run in runs) / success_count, 4) if success_count else 0.0,
            "llm_call_count": sum(run["online_llm_call_count"] for run in runs),
        }
    return result


def _random_arm_metrics(task_runs: list[dict[str, Any]]) -> dict[str, Any]:
    by_arm: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run in task_runs:
        by_arm[run["arm"]].append(run)
    result: dict[str, Any] = {}
    for arm in RANDOM_EXPERIENCE_ARMS:
        runs = by_arm.get(arm, [])
        result[arm] = {
            "task_count": len(runs),
            "success_rate": _avg(run["success"] for run in runs),
            "average_steps_to_success": round(mean(run["steps_to_success"] for run in runs), 4) if runs else 0.0,
            "known_bad_action_attempts": sum(run["known_bad_action_attempts"] for run in runs),
            "invalid_action_count": sum(run["invalid_action_count"] for run in runs),
            "false_trigger_rate": _avg(run["false_trigger"] for run in runs),
            "spurious_retrieval_rate": _avg(run["spurious_retrieval"] for run in runs),
            "irrelevant_memory_injection_rate": _avg(run["irrelevant_memory_injection"] for run in runs),
            "required_evidence_first_hit_rate": _avg(run["first_required_evidence_step"] == 1 for run in runs),
            "retrieval_hit_before_critical_action_rate": _avg(run["retrieval_hit_before_critical_action"] for run in runs),
            "average_token_estimate": round(mean(run["token_estimate"] for run in runs), 4) if runs else 0.0,
            "verified_memory_write_count": sum(run["verified_memory_write_count"] for run in runs),
            "promotion_count": sum(run["promotion_count"] for run in runs),
            "online_llm_call_count": sum(run["online_llm_call_count"] for run in runs),
        }
    return result


def _random_cost_metrics(task_runs: list[dict[str, Any]]) -> dict[str, Any]:
    by_arm: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run in task_runs:
        by_arm[run["arm"]].append(run)
    base = mean(run["token_estimate"] for run in by_arm["fresh_no_memory"]) if by_arm["fresh_no_memory"] else 0.0
    result = {}
    for arm, runs in by_arm.items():
        avg = mean(run["token_estimate"] for run in runs) if runs else 0.0
        success_count = sum(1 for run in runs if run["success"])
        result[arm] = {
            "average_token_estimate": round(avg, 4),
            "token_overhead_vs_fresh": round(avg - base, 4),
            "token_per_successful_task": round(sum(run["token_estimate"] for run in runs) / success_count, 4) if success_count else 0.0,
            "llm_call_count": sum(run["online_llm_call_count"] for run in runs),
        }
    return result


def _avg(values) -> float:
    items = [1.0 if value else 0.0 for value in values]
    return round(sum(items) / len(items), 4) if items else 0.0


def run_default_experience_transfer(workspace_root: Path) -> ExperienceTransferResult:
    return ExperienceTransferProtocol(workspace_root=workspace_root).run()


def run_default_random_experience_accumulation(workspace_root: Path) -> RandomExperienceAccumulationResult:
    return RandomExperienceAccumulationProtocol(workspace_root=workspace_root).run()
