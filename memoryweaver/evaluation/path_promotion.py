"""Layer-3 Path Promotion validation protocol."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import re
from statistics import mean
from typing import Any

from memoryweaver.external.longmemeval_v2 import build_lme_v2_external_episodes
from memoryweaver.external.schema import ExternalEpisode
from memoryweaver.harness import MemoryWeaverHarness
from memoryweaver.lifecycle import MemoryLifecycle
from memoryweaver.schema import PatternStatus, Source
from memoryweaver.store import MemoryWorkspace


@dataclass
class PathPromotionTask:
    task_id: str
    query: str
    expected_best_label: str
    oracle_steps: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PathPromotionFamily:
    family_id: str
    title: str
    tags: list[str]
    required_evidence: str
    stale_action: str
    current_best_action: str
    overgeneralized_action: str
    historical_success: str
    current_success: str
    current_failure: str
    overgeneralized_failure: str
    target_tasks: list[PathPromotionTask] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PathPromotionResult:
    passed: bool
    families: list[dict[str, Any]]
    path_catalog: list[dict[str, Any]]
    task_runs: list[dict[str, Any]]
    metrics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LongMemEvalPathPromotionResult:
    passed: bool
    snapshot: dict[str, Any]
    families: list[dict[str, Any]]
    path_catalog: list[dict[str, Any]]
    task_runs: list[dict[str, Any]]
    metrics: dict[str, Any]
    derivation_samples: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PathPromotionProtocol:
    """Validate that verified experience promotes into reusable execution paths."""

    def __init__(
        self,
        *,
        workspace_root: Path,
        families: list[PathPromotionFamily] | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root)
        self.families = families or default_path_promotion_families()

    def run(self) -> PathPromotionResult:
        task_runs: list[dict[str, Any]] = []
        path_catalog: list[dict[str, Any]] = []
        for family in self.families:
            workspace = MemoryWorkspace(self.workspace_root / family.family_id)
            lifecycle = MemoryLifecycle(workspace)
            catalog = self._seed_family(lifecycle, family)
            path_catalog.extend(catalog)
            harness = MemoryWeaverHarness(workspace)
            current_best_id = next(
                item["pattern_id"]
                for item in catalog
                if item["label"] == "current_best"
            )
            stale_id = next(
                item["pattern_id"]
                for item in catalog
                if item["label"] == "stale_path"
            )
            rollback_id = next(
                item["pattern_id"]
                for item in catalog
                if item["label"] == "rollback_path"
            )
            selected_costs = {
                item["pattern_id"]: item["cost"]
                for item in catalog
            }
            for task in family.target_tasks:
                composer_paths = lifecycle.composer.select_best_path(
                    task.query,
                    scope="project",
                    limit=3,
                    threshold=0.05,
                )
                skill = harness.skill_retriever.retrieve(
                    task.query,
                    scope="project",
                    limit=3,
                    threshold=0.05,
                )
                conditioning = harness.task_conditioning(
                    task.query,
                    tags=family.tags,
                    scope="project",
                    arm="mw_memory",
                    step=1,
                )
                composer_top = composer_paths[0].id if composer_paths else ""
                skill_top = skill.skills[0].pattern_id if skill.skills else ""
                harness_top = (
                    conditioning.skill_result.skills[0].pattern_id
                    if conditioning.skill_result.skills
                    else ""
                )
                selected_cost = selected_costs.get(composer_top, task.oracle_steps)
                task_runs.append(
                    {
                        "family_id": family.family_id,
                        "task_id": task.task_id,
                        "query": task.query,
                        "expected_best_path_id": current_best_id,
                        "composer_selected_path_id": composer_top,
                        "skill_selected_path_id": skill_top,
                        "harness_selected_path_id": harness_top,
                        "latest_path_selected": composer_top == current_best_id,
                        "skill_best_path_selected": skill_top == current_best_id,
                        "harness_best_path_selected": harness_top == current_best_id,
                        "stale_path_suppressed": composer_top != stale_id,
                        "rollback_path_suppressed": composer_top != rollback_id,
                        "path_regret": max(0, selected_cost - task.oracle_steps),
                    }
                )
        metrics = self._metrics(task_runs, path_catalog)
        passed = (
            metrics["stable_promotion_rate"] == 1.0
            and metrics["latest_path_selection_accuracy"] == 1.0
            and metrics["skill_path_selection_accuracy"] == 1.0
            and metrics["harness_path_selection_accuracy"] == 1.0
            and metrics["stale_path_suppression_rate"] == 1.0
            and metrics["rollback_success_rate"] == 1.0
            and metrics["false_stable_promotion_count"] == 0
            and metrics["average_path_regret"] == 0.0
        )
        return PathPromotionResult(
            passed=passed,
            families=[family.to_dict() for family in self.families],
            path_catalog=path_catalog,
            task_runs=task_runs,
            metrics=metrics,
        )

    def _seed_family(
        self,
        lifecycle: MemoryLifecycle,
        family: PathPromotionFamily,
    ) -> list[dict[str, Any]]:
        prefix = family.family_id
        success = lifecycle.write_verified_memory(
            memory_id=f"mem_{prefix}_success",
            content=family.current_success,
            source=Source.TOOL,
            tags=family.tags + [family.required_evidence],
            evidence_text=family.current_success,
            evidence_uri=f"path://{prefix}/success",
            promote=True,
        )
        failure = lifecycle.write_verified_memory(
            memory_id=f"mem_{prefix}_failure",
            content=family.current_failure,
            source=Source.TOOL,
            tags=family.tags + [family.stale_action, "known_bad_path"],
            evidence_text=family.current_failure,
            evidence_uri=f"path://{prefix}/failure",
            promote=True,
        )
        history = lifecycle.write_verified_memory(
            memory_id=f"mem_{prefix}_history",
            content=family.historical_success,
            source=Source.FILE,
            tags=family.tags + [family.stale_action, "historical_path"],
            evidence_text=family.historical_success,
            evidence_uri=f"path://{prefix}/historical",
            promote=True,
        )
        general = lifecycle.write_verified_memory(
            memory_id=f"mem_{prefix}_general",
            content=family.overgeneralized_failure,
            source=Source.TOOL,
            tags=family.tags + [family.overgeneralized_action, "overgeneralized_path"],
            evidence_text=family.overgeneralized_failure,
            evidence_uri=f"path://{prefix}/overgeneralized",
            promote=True,
        )
        composer = lifecycle.composer
        old_path = composer.compose(
            supporting_memory_ids=[history.memory.id, failure.memory.id],
            rule=f"Try {family.stale_action} before checking {family.required_evidence}",
            applies_when=[f"{family.title} recurs"],
            avoid_when=[],
            success_path=[family.stale_action],
            failed_path=[family.required_evidence],
            evidence_link_ids=[history.evidence_link.id, failure.evidence_link.id],
            scope="project",
        )
        current_best = composer.compose(
            supporting_memory_ids=[success.memory.id, failure.memory.id],
            rule=f"Check {family.required_evidence} before trying {family.stale_action}",
            applies_when=[f"{family.title} recurs"],
            avoid_when=[family.stale_action],
            success_path=[family.required_evidence],
            failed_path=[family.stale_action],
            evidence_link_ids=[success.evidence_link.id, failure.evidence_link.id],
            scope="project",
        )
        rollback = composer.compose(
            supporting_memory_ids=[general.memory.id, failure.memory.id],
            rule=f"Always use {family.overgeneralized_action} for {family.title}",
            applies_when=[f"any {family.title} issue"],
            avoid_when=[family.required_evidence],
            success_path=[family.overgeneralized_action],
            failed_path=[family.required_evidence, family.stale_action],
            evidence_link_ids=[general.evidence_link.id, failure.evidence_link.id],
            scope="project",
        )

        for run_id in ("hist-1", "hist-2", "hist-3"):
            composer.record_path_trial(
                old_path.id,
                task_run_id=run_id,
                successful=True,
                steps_saved=1,
            )
        old_path.freshness = lifecycle.workspace.patterns.get(old_path.id).freshness
        lifecycle.workspace.patterns.update(old_path)
        composer.promote_stable(old_path.id)
        composer.record_path_trial(
            old_path.id,
            task_run_id="curr-1",
            successful=False,
            false_trigger=True,
            conflict_ref=f"{prefix}:stale_path",
        )
        composer.record_path_trial(
            old_path.id,
            task_run_id="curr-2",
            successful=False,
            false_trigger=True,
            conflict_ref=f"{prefix}:stale_path_repeat",
        )

        for run_id in ("run-1", "run-2", "run-3"):
            composer.record_path_trial(
                current_best.id,
                task_run_id=run_id,
                successful=True,
                steps_saved=2,
                known_bad_avoided=1,
                evidence_first=True,
            )
        stable_pattern = lifecycle.workspace.patterns.get(current_best.id)
        stable_pattern.freshness = stable_pattern.freshness or stable_pattern.freshness
        lifecycle.workspace.patterns.update(stable_pattern)
        composer.promote_stable(current_best.id)

        composer.record_validation(
            rollback.id,
            "rollback-1",
            False,
            conflict_ref=f"{prefix}:overgeneralized",
        )

        catalog = []
        for label, pattern_id, cost in (
            ("stale_path", old_path.id, 3),
            ("current_best", current_best.id, 1),
            ("rollback_path", rollback.id, 4),
        ):
            pattern = lifecycle.workspace.patterns.get(pattern_id)
            catalog.append(
                {
                    "family_id": family.family_id,
                    "label": label,
                    "pattern_id": pattern.id,
                    "status": pattern.status.value,
                    "path_fitness_score": pattern.path_fitness_score,
                    "confidence": pattern.confidence,
                    "cost": cost,
                    "rule": pattern.rule,
                }
            )
        return catalog

    @staticmethod
    def _metrics(task_runs: list[dict[str, Any]], path_catalog: list[dict[str, Any]]) -> dict[str, Any]:
        stable_candidates = [
            item for item in path_catalog
            if item["label"] == "current_best"
        ]
        return {
            "family_count": len({item["family_id"] for item in path_catalog}),
            "task_count": len(task_runs),
            "stable_promotion_rate": _avg(item["status"] == PatternStatus.STABLE.value for item in stable_candidates),
            "latest_path_selection_accuracy": _avg(run["latest_path_selected"] for run in task_runs),
            "skill_path_selection_accuracy": _avg(run["skill_best_path_selected"] for run in task_runs),
            "harness_path_selection_accuracy": _avg(run["harness_best_path_selected"] for run in task_runs),
            "stale_path_suppression_rate": _avg(run["stale_path_suppressed"] for run in task_runs),
            "rollback_success_rate": _avg(
                item["status"] in {PatternStatus.ROLLED_BACK.value, PatternStatus.CHALLENGED.value}
                for item in path_catalog
                if item["label"] == "rollback_path"
            ),
            "false_stable_promotion_count": sum(
                1
                for item in path_catalog
                if item["label"] in {"stale_path", "rollback_path"}
                and item["status"] == PatternStatus.STABLE.value
            ),
            "average_path_regret": round(mean(run["path_regret"] for run in task_runs), 4) if task_runs else 0.0,
        }


def default_path_promotion_families() -> list[PathPromotionFamily]:
    seeds = [
        (
            "codex_subscription_org",
            "Codex subscription entitlement",
            ["codex", "subscription", "auth"],
            "selected_organization",
            "reinstall_npm",
            "reset_auth_files",
        ),
        (
            "npm_registry_conflict",
            "npm registry dependency conflict",
            ["npm", "registry", "dependency"],
            "npm_registry",
            "delete_lockfile",
            "clear_global_cache",
        ),
        (
            "api_key_scope_denied",
            "API key scope denied",
            ["api_key", "scope", "denied"],
            "api_key_scope",
            "rotate_key_blindly",
            "reissue_all_credentials",
        ),
    ]
    families: list[PathPromotionFamily] = []
    for family_id, title, tags, evidence, stale_action, rollback_action in seeds:
        tasks = [
            PathPromotionTask(
                task_id=f"{family_id}_task_{index}",
                query=(
                    f"{title} sibling task {index}: should I check {evidence} before "
                    f"{stale_action}, or still try {stale_action} first? "
                    f"Do not overgeneralize to {rollback_action}."
                ),
                expected_best_label="current_best",
                oracle_steps=1,
            )
            for index in range(1, 4)
        ]
        families.append(
            PathPromotionFamily(
                family_id=family_id,
                title=title,
                tags=tags,
                required_evidence=evidence,
                stale_action=stale_action,
                current_best_action=evidence,
                overgeneralized_action=rollback_action,
                historical_success=f"Historical environment once recovered after {stale_action}.",
                current_success=f"Current environment succeeds after checking {evidence} first.",
                current_failure=f"Current environment fails when trying {stale_action} first.",
                overgeneralized_failure=f"{rollback_action} overgeneralizes and misses {evidence}.",
                target_tasks=tasks,
            )
        )
    return families


def _avg(values) -> float:
    items = [1.0 if value else 0.0 for value in values]
    return round(sum(items) / len(items), 4) if items else 0.0


def run_default_path_promotion(workspace_root: Path) -> PathPromotionResult:
    return PathPromotionProtocol(workspace_root=workspace_root).run()


class LongMemEvalPathPromotionProtocol:
    """Run the Layer-3 path-promotion flow over a real LongMemEval-V2 snapshot."""

    def __init__(
        self,
        *,
        workspace_root: Path,
        input_root: Path | None = None,
        question_limit: int = 5,
        trajectories_per_question: int = 1,
        states_per_trajectory: int = 2,
        max_observation_chars: int = 1800,
        haystack_name: str = "lme_v2_small.json",
        hf_cache_root: Path | None = None,
        allow_download: bool = False,
    ) -> None:
        self.workspace_root = Path(workspace_root)
        self.input_root = input_root
        self.question_limit = question_limit
        self.trajectories_per_question = trajectories_per_question
        self.states_per_trajectory = states_per_trajectory
        self.max_observation_chars = max_observation_chars
        self.haystack_name = haystack_name
        self.hf_cache_root = hf_cache_root
        self.allow_download = allow_download

    def run(self) -> LongMemEvalPathPromotionResult:
        episodes, snapshot = build_lme_v2_external_episodes(
            self.input_root,
            question_limit=self.question_limit,
            trajectories_per_question=self.trajectories_per_question,
            states_per_trajectory=self.states_per_trajectory,
            max_observation_chars=self.max_observation_chars,
            haystack_name=self.haystack_name,
            hf_cache_root=self.hf_cache_root,
            allow_download=self.allow_download,
        )
        families, derivation_samples = build_path_promotion_families_from_lme_v2(episodes)
        result = PathPromotionProtocol(
            workspace_root=self.workspace_root,
            families=families,
        ).run()
        metrics = dict(result.metrics)
        metrics["real_snapshot_family_count"] = len(families)
        metrics["resolved_root"] = snapshot.get("resolved_root", "")
        metrics["root_resolution_source"] = snapshot.get("root_resolution_source", "")
        return LongMemEvalPathPromotionResult(
            passed=result.passed,
            snapshot=snapshot,
            families=result.families,
            path_catalog=result.path_catalog,
            task_runs=result.task_runs,
            metrics=metrics,
            derivation_samples=derivation_samples,
        )


def build_path_promotion_families_from_lme_v2(
    episodes: list[ExternalEpisode],
) -> tuple[list[PathPromotionFamily], list[dict[str, Any]]]:
    families: list[PathPromotionFamily] = []
    derivation_samples: list[dict[str, Any]] = []
    for index, episode in enumerate(episodes, start=1):
        family, sample = _family_from_episode(episode, index=index)
        families.append(family)
        derivation_samples.append(sample)
    return families, derivation_samples


def run_lme_v2_path_promotion(
    workspace_root: Path,
    *,
    input_root: Path | None = None,
    question_limit: int = 5,
    trajectories_per_question: int = 1,
    states_per_trajectory: int = 2,
    max_observation_chars: int = 1800,
    haystack_name: str = "lme_v2_small.json",
    hf_cache_root: Path | None = None,
    allow_download: bool = False,
) -> LongMemEvalPathPromotionResult:
    return LongMemEvalPathPromotionProtocol(
        workspace_root=workspace_root,
        input_root=input_root,
        question_limit=question_limit,
        trajectories_per_question=trajectories_per_question,
        states_per_trajectory=states_per_trajectory,
        max_observation_chars=max_observation_chars,
        haystack_name=haystack_name,
        hf_cache_root=hf_cache_root,
        allow_download=allow_download,
    ).run()


GENERIC_TOKENS = {
    "a", "an", "and", "answer", "be", "boxed", "final", "for", "from", "i",
    "if", "in", "is", "it", "mark", "my", "of", "on", "or", "our", "should",
    "task", "the", "this", "to", "what", "when", "which", "with", "your",
    "longmemeval-v2", "enterprise", "workarena",
}


def _family_from_episode(
    episode: ExternalEpisode,
    *,
    index: int,
) -> tuple[PathPromotionFamily, dict[str, Any]]:
    query = episode.queries[0]
    title = _short_title(query.query, fallback=episode.metadata.get("question_type", "procedure"))
    stale_action = _derive_stale_action(episode)
    overgeneralized_action = _derive_overgeneralized_action(episode, stale_action)
    required_evidence = _derive_required_evidence(episode)
    tags = _derive_family_tags(episode, required_evidence, stale_action, overgeneralized_action)
    family_id = f"lmev2_{episode.episode_id}"
    tasks = [
        PathPromotionTask(
            task_id=f"{family_id}_task_{offset}",
            query=(
                f"{title} sibling task {offset}: should I check {required_evidence} before "
                f"{stale_action}, or still try {stale_action} first? Do not overgeneralize to "
                f"{overgeneralized_action}."
            ),
            expected_best_label="current_best",
            oracle_steps=1,
        )
        for offset in range(1, 4)
    ]
    family = PathPromotionFamily(
        family_id=family_id,
        title=title,
        tags=tags,
        required_evidence=required_evidence,
        stale_action=stale_action,
        current_best_action=required_evidence,
        overgeneralized_action=overgeneralized_action,
        historical_success=_historical_success(episode, stale_action),
        current_success=_current_success(episode, required_evidence),
        current_failure=_current_failure(episode, stale_action),
        overgeneralized_failure=f"{overgeneralized_action} overgeneralizes and misses {required_evidence}.",
        target_tasks=tasks,
    )
    return family, {
        "family_id": family_id,
        "episode_id": episode.episode_id,
        "question_type": episode.metadata.get("question_type", ""),
        "required_evidence": required_evidence,
        "stale_action": stale_action,
        "overgeneralized_action": overgeneralized_action,
        "tags": tags,
    }


def _derive_required_evidence(episode: ExternalEpisode) -> str:
    query = episode.queries[0]
    for candidate in [
        _normalize_phrase(query.answer, limit=4),
        _first_specific_token(query.expected_evidence_tags),
        _first_specific_token(query.tags),
        _first_web_keyword(episode),
    ]:
        if candidate:
            return candidate
    return "required_evidence"


def _derive_stale_action(episode: ExternalEpisode) -> str:
    for turn in episode.turns:
        if turn.source == Source.TOOL:
            parsed = _parse_tool_action(turn.content)
            if parsed:
                return parsed
    for turn in episode.turns:
        if turn.source == Source.ASSISTANT:
            guess = _extract_action_phrase(turn.content)
            if guess:
                return guess
    return "generic_tool_action"


def _derive_overgeneralized_action(episode: ExternalEpisode, stale_action: str) -> str:
    seen = {stale_action}
    for turn in episode.turns:
        if turn.source == Source.TOOL:
            parsed = _parse_tool_action(turn.content)
            if parsed and parsed not in seen:
                return parsed
            seen.add(parsed or "")
    for turn in episode.turns:
        if turn.source == Source.ASSISTANT:
            guess = _extract_action_phrase(turn.content)
            if guess and guess not in seen:
                return guess
    return "generic_overgeneralization"


def _derive_family_tags(
    episode: ExternalEpisode,
    required_evidence: str,
    stale_action: str,
    overgeneralized_action: str,
) -> list[str]:
    query = episode.queries[0]
    seed = [
        episode.metadata.get("question_type", ""),
        episode.metadata.get("domain", ""),
        episode.metadata.get("environment", ""),
        required_evidence,
        stale_action,
        overgeneralized_action,
    ]
    tags = [_normalize_phrase(value, limit=2) for value in seed if value]
    tags.extend(
        token for token in query.tags
        if token and token not in GENERIC_TOKENS
    )
    deduped: list[str] = []
    for tag in tags:
        if tag and tag not in deduped:
            deduped.append(tag)
        if len(deduped) >= 8:
            break
    return deduped or ["path_promotion"]


def _historical_success(episode: ExternalEpisode, stale_action: str) -> str:
    goal = next((turn.content for turn in episode.turns if turn.role == "user"), "")
    if goal:
        return f"Historical task context: {goal[:220]} | earlier path tried {stale_action}."
    return f"Historical environment once recovered after {stale_action}."


def _current_success(episode: ExternalEpisode, required_evidence: str) -> str:
    query = episode.queries[0]
    if query.answer:
        return (
            f"Current sibling task succeeds after checking {required_evidence} first. "
            f"Observed answer anchor: {query.answer[:220]}"
        )
    return f"Current sibling task succeeds after checking {required_evidence} first."


def _current_failure(episode: ExternalEpisode, stale_action: str) -> str:
    query = episode.queries[0]
    return (
        f"Current sibling task fails when trying {stale_action} first. "
        f"Task anchor: {query.query[:220]}"
    )


def _short_title(query: str, *, fallback: str) -> str:
    words = re.findall(r"[A-Za-z0-9_/-]+", query)
    filtered = [word for word in words if word.lower() not in GENERIC_TOKENS]
    title = " ".join(filtered[:6]).strip()
    return title or str(fallback or "path_promotion")


def _normalize_phrase(value: str, *, limit: int = 4) -> str:
    tokens = [
        token.lower()
        for token in re.findall(r"[A-Za-z0-9_/-]+", str(value))
        if token and token.lower() not in GENERIC_TOKENS
    ]
    return "_".join(tokens[:limit]).strip("_")


def _first_specific_token(values: list[str]) -> str:
    for value in values:
        normalized = _normalize_phrase(value, limit=2)
        if normalized:
            return normalized
    return ""


def _first_web_keyword(episode: ExternalEpisode) -> str:
    for turn in episode.turns:
        if turn.source == Source.WEB:
            normalized = _normalize_phrase(turn.content, limit=3)
            if normalized:
                return normalized
    return ""


def _parse_tool_action(content: str) -> str:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return ""
    action = str(payload.get("action", "")).strip()
    return _extract_action_phrase(action)


def _extract_action_phrase(text: str) -> str:
    normalized = _normalize_phrase(text, limit=3)
    return normalized
