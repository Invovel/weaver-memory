"""Minimal Layer-3 candidate -> provisional -> trial -> stable validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from memoryweaver.composer import PatternComposer
from memoryweaver.evidence import EvidenceLink, EvidenceNode
from memoryweaver.schema import Freshness, MemoryItem, PatternStatus
from memoryweaver.store import MemoryWorkspace


@dataclass
class Layer3MVPResult:
    passed: bool
    path_catalog: list[dict[str, Any]]
    task_runs: list[dict[str, Any]]
    metrics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_layer3_mvp(workspace_root: Path) -> Layer3MVPResult:
    workspace = MemoryWorkspace(workspace_root)
    composer = PatternComposer(
        workspace.memories,
        workspace.patterns,
        workspace.evidence,
        workspace.memory_policy,
    )
    success = _verified_memory(
        workspace,
        content="Checking selected_organization first resolved the recurring subscription entitlement issue.",
        tags=["codex", "subscription", "selected_organization"],
        evidence_uri="layer3://mvp/success",
    )
    failure = _verified_memory(
        workspace,
        content="Trying reinstall_npm first wasted steps and did not resolve the entitlement issue.",
        tags=["codex", "subscription", "reinstall_npm", "known_bad_path"],
        evidence_uri="layer3://mvp/failure",
    )
    pattern = composer.compose(
        supporting_memory_ids=[success["memory"].id, failure["memory"].id],
        rule="Check selected_organization before reinstall_npm for recurring Codex subscription entitlement issues",
        applies_when=["Codex subscription entitlement recurs"],
        avoid_when=["reinstall_npm first"],
        success_path=["selected_organization"],
        failed_path=["reinstall_npm"],
        evidence_link_ids=[success["link"].id, failure["link"].id],
        scope="project",
    )
    initial_status = pattern.status.value
    pattern.freshness = Freshness.STABLE
    workspace.patterns.update(pattern)

    challenged_pattern = composer.compose(
        supporting_memory_ids=[success["memory"].id, failure["memory"].id],
        rule="Always reinstall_npm first for recurring Codex subscription entitlement issues",
        applies_when=["Codex subscription entitlement recurs"],
        avoid_when=["selected_organization first"],
        success_path=["reinstall_npm"],
        failed_path=["selected_organization"],
        evidence_link_ids=[success["link"].id, failure["link"].id],
        scope="project",
    )
    challenged_pattern.freshness = Freshness.STABLE
    workspace.patterns.update(challenged_pattern)

    task_runs: list[dict[str, Any]] = []
    stable_trial_specs = [
        ("trial-1", True, 1, True, False, 1),
        ("trial-2", True, 1, True, False, 1),
        ("trial-3", True, 1, True, False, 1),
    ]
    for task_id, evidence_first, known_bad_avoided, successful, false_trigger, selected_cost in stable_trial_specs:
        updated = composer.record_path_trial(
            pattern.id,
            task_run_id=task_id,
            successful=successful,
            steps_saved=max(0, 4 - selected_cost),
            known_bad_avoided=known_bad_avoided,
            evidence_first=evidence_first,
            false_trigger=false_trigger,
            token_cost=0.0,
            conflict_ref=f"layer3_mvp:{task_id}" if false_trigger else "",
        )
        task_runs.append(
            {
                "task_id": task_id,
                "successful": successful,
                "known_bad_avoidance": known_bad_avoided,
                "evidence_first": evidence_first,
                "false_trigger": false_trigger,
                "selected_cost": selected_cost,
                "oracle_cost": 1,
                "path_regret": max(0, selected_cost - 1),
                "status_after_trial": updated.status.value,
            }
        )

    stable = composer.promote_stable(pattern.id)
    challenged = composer.record_path_trial(
        challenged_pattern.id,
        task_run_id="trial-4",
        successful=False,
        steps_saved=1,
        evidence_first=False,
        false_trigger=True,
        token_cost=0.0,
        conflict_ref="layer3_mvp:trial-4",
    )
    task_runs.append(
        {
            "task_id": "trial-4",
            "successful": False,
            "known_bad_avoidance": 0,
            "evidence_first": False,
            "false_trigger": True,
            "selected_cost": 3,
            "oracle_cost": 1,
            "path_regret": 2,
            "status_after_trial": challenged.status.value,
        }
    )
    path_catalog = [
        {
            "pattern_id": stable.id,
            "label": "stable_candidate",
            "initial_status": initial_status,
            "final_status": stable.status.value,
            "trial_count": stable.trial_count,
            "known_bad_avoidance_count": stable.known_bad_avoidance_count,
            "evidence_first_count": stable.evidence_first_count,
            "false_trigger_count": stable.false_trigger_count,
            "path_fitness_score": stable.path_fitness_score,
        },
        {
            "pattern_id": challenged.id,
            "label": "challenged_candidate",
            "initial_status": challenged_pattern.status.value,
            "final_status": challenged.status.value,
            "trial_count": challenged.trial_count,
            "known_bad_avoidance_count": challenged.known_bad_avoidance_count,
            "evidence_first_count": challenged.evidence_first_count,
            "false_trigger_count": challenged.false_trigger_count,
            "path_fitness_score": challenged.path_fitness_score,
        }
    ]
    avg_regret = round(sum(run["path_regret"] for run in task_runs) / len(task_runs), 4)
    metrics = {
        "candidate_to_provisional": initial_status == PatternStatus.PROVISIONAL.value,
        "stable_after_trials": stable.status == PatternStatus.STABLE,
        "challenged_on_conflict": challenged.status == PatternStatus.CHALLENGED,
        "known_bad_avoidance_count": stable.known_bad_avoidance_count,
        "evidence_first_count": stable.evidence_first_count,
        "false_trigger_count": challenged.false_trigger_count,
        "average_path_regret": avg_regret,
    }
    passed = (
        metrics["candidate_to_provisional"]
        and metrics["stable_after_trials"]
        and metrics["challenged_on_conflict"]
        and metrics["known_bad_avoidance_count"] == 3
        and metrics["evidence_first_count"] == 3
        and metrics["false_trigger_count"] == 1
        and metrics["average_path_regret"] == 0.5
    )
    return Layer3MVPResult(
        passed=passed,
        path_catalog=path_catalog,
        task_runs=task_runs,
        metrics=metrics,
    )


def _verified_memory(
    workspace: MemoryWorkspace,
    *,
    content: str,
    tags: list[str],
    evidence_uri: str,
) -> dict[str, Any]:
    item = MemoryItem(content=content, source="tool", tags=tags, evidence=content)
    workspace.memories.add(item)
    workspace.memory_policy.promote_to_layer2(item, [])
    workspace.memories.update(item)
    node = EvidenceNode(text=content, source="tool", source_uri=evidence_uri)
    workspace.evidence.add_node(node)
    link = EvidenceLink(evidence_id=node.id, memory_id=item.id)
    workspace.evidence.add_link(link)
    return {"memory": item, "node": node, "link": link}
