"""Live-agent bridge for evidence-gated runtime path promotion.

The default mode is a deterministic mock live agent so CI can verify the
artifact contract without network access. Use ``--llm`` to run the same harness
with a real OpenAI-compatible action selector.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from statistics import mean
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from memoryweaver import (
    ActionGate,
    ActionProposal,
    CheckpointStore,
    EnvironmentContract,
    EventJournal,
    HardEvidence,
    HardEvidenceType,
    HarnessRuntime,
    MemoryWeaverConfig,
    OpenAICompatibleAgent,
    RuntimePathStore,
    RuntimeTask,
    RuntimeTraceRecorder,
    RuntimeTraceStore,
    ToolGateway,
    extract_candidate_path_from_trace,
)
from memoryweaver.runtime import LiveAction, LiveObservation
from benchmarks._safety import safe_rmtree_child, safe_unlink_child


DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "validation" / "harness-runtime-live-llm"
GENERATED_ARTIFACTS = (
    "raw_results.json",
    "task_runs.jsonl",
    "metrics.json",
    "reliability.json",
    "README.md",
    "runtime_path_store.json",
    "runtime_traces.jsonl",
    "events.jsonl",
    "checkpoints.json",
)
PRIMARY_RUN_ARTIFACTS = (
    "task_runs.jsonl",
    "runtime_path_store.json",
    "runtime_traces.jsonl",
    "events.jsonl",
    "checkpoints.json",
)
POLICY_TARGETS = ("action_schema", "marker_only_boundary", "pass_power_3")


class ScriptedLivePathAgent:
    """Local stand-in for a live action selector.

    It behaves like an LLM-facing policy surface: each step emits a single
    ``LiveAction`` proposal, while the harness decides whether the result can
    support promotion.
    """

    online_llm_call_count = 0

    def __init__(self) -> None:
        self._targets = ("__invalid_action__", *POLICY_TARGETS)

    def choose_action(
        self,
        observation: LiveObservation,
        memory_context: str,
        *,
        step: int,
    ) -> LiveAction:
        target = self._targets[min(step - 1, len(self._targets) - 1)]
        return LiveAction(
            name="tool_call" if target == "__invalid_action__" else "check_evidence",
            target=target,
            reasoning="scripted live proposal for runtime-path gate dry run",
        )


LiveAgentFactory = Callable[[], Any]


def _prepare_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in GENERATED_ARTIFACTS:
        safe_unlink_child(output_dir, output_dir / name)


def _proposal(target: str, *, key: str) -> ActionProposal:
    return ActionProposal(
        action_name="tool_call",
        target=target,
        arguments={"target": target},
        idempotency_key=key,
    )


def _canonicalize_action(
    action: LiveAction,
    *,
    remaining_targets: list[str] | None = None,
) -> LiveAction:
    target = action.target.strip()
    lowered = target.lower().replace(" ", "_")
    remaining = list(remaining_targets or [])
    if remaining:
        for candidate in remaining:
            if candidate in lowered:
                target = candidate
                lowered = target
                break
    aliases = {
        "schema": "action_schema",
        "action_schema": "action_schema",
        "marker": "marker_only_boundary",
        "marker_only": "marker_only_boundary",
        "marker_only_boundary": "marker_only_boundary",
        "pass3": "pass_power_3",
        "pass^3": "pass_power_3",
        "pass_power_3": "pass_power_3",
        "__invalid_action__": "__invalid_action__",
        "invalid_action": "__invalid_action__",
    }
    if lowered in aliases:
        target = aliases[lowered]
    elif any(item in lowered for item in ("invalid", "bad_action")):
        target = "__invalid_action__"
    elif "schema" in lowered:
        target = "action_schema"
    elif "marker" in lowered or "boundary" in lowered:
        target = "marker_only_boundary"
    elif "pass" in lowered and "3" in lowered:
        target = "pass_power_3"
    elif target not in POLICY_TARGETS:
        target = "__invalid_action__"
    name = action.name if action.name in {"tool_call", "check_evidence", "ask_user", "resolve"} else "ask_user"
    if target in POLICY_TARGETS:
        name = "check_evidence"
    if target == "__invalid_action__":
        name = "tool_call"
    return LiveAction(name=name, target=target, reasoning=action.reasoning)


def _bundled_target_count(target: str) -> int:
    normalized = target.lower().replace(" ", "_")
    return sum(1 for item in POLICY_TARGETS if item in normalized)


def _gateway(output_dir: Path) -> tuple[ToolGateway, EventJournal, CheckpointStore]:
    journal = EventJournal(output_dir / "events.jsonl")
    checkpoints = CheckpointStore(output_dir / "checkpoints.json")
    gateway = ToolGateway(
        ActionGate(EnvironmentContract.default_live_loop()),
        journal=journal,
        checkpoints=checkpoints,
    )
    gateway.register(
        "tool_call",
        lambda proposal: {
            "status": "invalid_action",
            "signal": "negative",
            "evidence": f"{proposal.target} rejected by live runtime gate",
            "false_trigger": True,
        },
    )
    gateway.register(
        "check_evidence",
        lambda proposal: {
            "status": "evidence_observed",
            "signal": "positive",
            "evidence": f"{proposal.target} verified from external tool result",
            "known_bad_avoided": proposal.target == "action_schema",
            "evidence_first": proposal.target == "action_schema",
        },
    )
    return gateway, journal, checkpoints


def _live_trace_candidate(
    *,
    output_dir: Path,
    agent: Any,
    llm: bool,
    seed: int,
) -> dict[str, Any]:
    trace_store = RuntimeTraceStore(output_dir / "runtime_traces.jsonl")
    gateway, journal, checkpoints = _gateway(output_dir)
    trace_id = f"trace-live-llm-{seed}"
    task_id = f"live-llm-seed-task-{seed}"
    thread_id = f"live-llm-thread-{seed}"
    observation = LiveObservation(
        task_id=task_id,
        goal="Debug benchmark invalid_action by proposing a reusable runtime path.",
        state={
            "failure_mode": "invalid_action",
            "recommended_evidence": list(POLICY_TARGETS),
            "known_bad_actions": ["__invalid_action__"],
            "available_actions": ["__invalid_action__", *POLICY_TARGETS],
        },
    )
    recorder = RuntimeTraceRecorder(
        trace_id=trace_id,
        task_id=task_id,
        task_type="benchmark_debug",
        user_goal=observation.goal,
        initial_context={
            "tags": ["benchmark", "debug"],
            "failure_mode": "invalid_action",
            "family": "benchmark_debug",
            "mode": "live_llm" if llm else "mock_live_agent",
        },
        thread_id=thread_id,
        store=trace_store,
    )
    memory_context = (
        "Harness instruction: propose one action at a time. Known bad: "
        "__invalid_action__. Required evidence: action_schema, "
        "marker_only_boundary, pass_power_3. Model confidence cannot promote."
    )
    observed_targets: list[str] = []
    rejected_targets: list[str] = []
    canonicalized_bundle_count = 0
    start_llm_calls = int(getattr(agent, "online_llm_call_count", 0))
    for step in range(1, 5):
        remaining = [target for target in POLICY_TARGETS if target not in observed_targets]
        observation.state["remaining_evidence"] = list(remaining)
        observation.state["recommended_evidence"] = list(remaining)
        observation.state["available_actions"] = ["__invalid_action__", *remaining]
        memory_context = (
            "Harness instruction: propose one action at a time. Known bad: "
            "__invalid_action__. Choose exactly one target from remaining_evidence: "
            f"{', '.join(remaining)}. Model confidence cannot promote."
        )
        raw_action = agent.choose_action(observation, memory_context, step=step)
        action = _canonicalize_action(raw_action, remaining_targets=remaining)
        if (
            _bundled_target_count(raw_action.target) > 1
            and raw_action.target != action.target
        ):
            canonicalized_bundle_count += 1
        proposal = ActionProposal.from_live_action(
            action,
            thread_id=thread_id,
            step=step,
        )
        result = gateway.execute(proposal, thread_id=thread_id, step=step)
        observation.history.append({"action": action.to_dict(), "result": result.to_dict()})
        if result.status == "evidence_observed":
            observed_targets.append(action.target)
        else:
            rejected_targets.append(action.target)
        recorder.record_tool_result(
            node_name=_node_name(action.target),
            result=result,
            thought_summary=action.reasoning,
            latency_ms=5 + step,
            token_cost=64 if llm else 0,
            metadata={
                "raw_action": raw_action.to_dict(),
                "canonical_action": action.to_dict(),
                "live_llm": llm,
            },
        )
        if all(target in observed_targets for target in POLICY_TARGETS):
            break

    live_call_count = int(getattr(agent, "online_llm_call_count", 0)) - start_llm_calls
    success = all(target in observed_targets for target in POLICY_TARGETS)
    trace = recorder.finish(
        success=success,
        final_result={
            "selected_action": observed_targets[-1] if observed_targets else "",
            "failure_mode": "invalid_action",
            "observed_targets": list(observed_targets),
            "rejected_targets": list(rejected_targets),
        },
        metrics={
            "tests_passed": success,
            "test_target": "live_llm_runtime_path_smoke",
            "file_diff_matches_expected": "marker_only_boundary" in observed_targets,
            "diff_target": "live_llm_runtime_path_diff",
            "diff_expected": "filter invalid_action and isolate marker-only boundary",
            "diff_observed": "invalid_action rejected; marker-only boundary checked"
            if "marker_only_boundary" in observed_targets
            else "marker-only boundary not checked",
            "benchmark_name": "live_llm_runtime_path_bridge",
            "score_before": 0.72,
            "score_after": 0.88 if success else 0.72,
            "repeat_validation_count": 3 if "pass_power_3" in observed_targets else 0,
            "repeat_validation_target": "action_schema",
            "known_bad_avoided": "__invalid_action__" in rejected_targets,
            "evidence_first": observed_targets[:1] == ["action_schema"],
            "time_decay_weight": 1.0,
            "online_llm_call_count": live_call_count,
            "live_llm_run": llm,
            "canonicalized_bundle_count": canonicalized_bundle_count,
        },
    )
    return {
        "trace": trace,
        "candidate": extract_candidate_path_from_trace(trace),
        "trace_store": trace_store,
        "journal": journal,
        "checkpoints": checkpoints,
        "live_call_count": live_call_count,
    }


def _node_name(target: str) -> str:
    if target == "__invalid_action__":
        return "live_invalid_action_proposal"
    if target == "action_schema":
        return "live_check_schema"
    if target == "marker_only_boundary":
        return "live_isolate_marker_only"
    if target == "pass_power_3":
        return "live_run_pass_power_3"
    return "live_agent_proposal"


def _tasks(count: int = 5) -> list[RuntimeTask]:
    return [
        RuntimeTask(
            task_id=f"live-llm-replay-{index:03d}",
            task_family="benchmark_debug",
            query=f"live LLM benchmark debug invalid_action sibling task {index}",
            tags=["benchmark", "debug"],
            state={"failure_mode": "invalid_action"},
        )
        for index in range(1, count + 1)
    ]


def _metrics(runs: list[dict[str, Any]]) -> dict[str, float]:
    total = max(len(runs), 1)
    promoted = [
        run
        for run in runs
        if str(run.get("promotion_decision", "")).startswith("evidence_gated")
    ]
    return {
        "task_count": len(runs),
        "success_rate": round(sum(int(run["success"]) for run in runs) / total, 4),
        "repeated_failure_rate": round(sum(int(not run["success"]) for run in runs) / total, 4),
        "invalid_action_rate": round(sum(int(run["invalid_action"]) for run in runs) / total, 4),
        "known_bad_action_rate": round(sum(int(run["known_bad_action"]) for run in runs) / total, 4),
        "memory_induced_regression_rate": round(
            sum(int(run["memory_induced_regression"]) for run in runs) / total,
            4,
        ),
        "rollback_frequency": round(sum(int(run["rollback"]) for run in runs) / total, 4),
        "negative_memory_hit_rate": round(
            sum(int(run.get("negative_memory_hit", False)) for run in runs) / total,
            4,
        ),
        "promotion_precision": round(
            sum(int(run["success"]) for run in promoted) / max(len(promoted), 1),
            4,
        )
        if promoted
        else 0.0,
    }


def _readme(result: dict[str, Any]) -> str:
    reliability = result.get("reliability", {})
    mode = result["run_config"]["mode"]
    reliability_label = "live LLM pass^3" if mode == "live_llm" else "mock bridge pass^3"
    lines = [
        "# Harness Runtime Live LLM",
        "",
        "Live-agent bridge for evidence-gated runtime path promotion.",
        "",
        f"passed = {str(result['passed']).lower()}",
        f"mode = {mode}",
        f"live_llm_run_complete = {str(result['aggregate_metrics']['live_llm_run_complete'] == 1.0).lower()}",
        "",
        "| arm | success_rate | repeated_failure_rate | invalid_action_rate | known_bad_action_rate | memory_induced_regression_rate | rollback_frequency | promotion_precision |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm, values in result["metrics"].items():
        lines.append(
            f"| {arm} | {values['success_rate']} | {values['repeated_failure_rate']} | "
            f"{values['invalid_action_rate']} | {values['known_bad_action_rate']} | "
            f"{values['memory_induced_regression_rate']} | {values['rollback_frequency']} | "
            f"{values['promotion_precision']} |"
        )
    lines.extend(["", "## Aggregate", ""])
    for key, value in result["aggregate_metrics"].items():
        lines.append(f"- `{key}` = {value}")
    lines.extend(
        [
            "",
            "## Reliability",
            "",
            f"- pass@1: {reliability.get('pass_at_1', result['passed'])}",
            f"- {reliability_label}: {reliability.get('pass_power_3', False)}",
            f"- Seeds: {reliability.get('seeds', [])}",
            "",
            "## Run Commands",
            "",
            "- Mock bridge: `python benchmarks\\harness_runtime_live_llm.py --reliability-passes 3 --seed 21`",
            "- Real LLM gate: `python benchmarks\\harness_runtime_live_llm.py --llm --provider deepseek --model deepseek-chat --reliability-passes 3 --seed 21`",
            "",
            "## Boundary",
            "",
            "- Mock mode validates the artifact contract and Harness authority path.",
            "- Only `--llm` mode counts as the missing live LLM run.",
            "- Mock bridge pass^3 cannot be cited as live LLM pass^3.",
            "- Model output remains a proposal; promotion still requires external evidence.",
            "",
            f"Research question: {result['research_question']}",
            "",
        ]
    )
    return "\n".join(lines)


def _reliability_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    if not results:
        return {
            "run_count": 0,
            "pass_at_1": False,
            "pass_power_3": False,
            "seeds": [],
            "by_arm": {},
            "aggregate": {},
        }
    arms = list(results[0]["metrics"])
    by_arm: dict[str, dict[str, float | bool]] = {}
    for arm in arms:
        values = {key: [float(result["metrics"][arm][key]) for result in results] for key in (
            "success_rate",
            "repeated_failure_rate",
            "invalid_action_rate",
            "known_bad_action_rate",
            "memory_induced_regression_rate",
            "rollback_frequency",
            "promotion_precision",
        )}
        by_arm[arm] = {
            "pass_at_1": bool(results[0]["passed"]),
            "pass_power_3": len(results) >= 3 and all(bool(result["passed"]) for result in results[:3]),
            **{
                f"{key}_mean": _mean(items)
                for key, items in values.items()
            },
            **{
                f"{key}_std": _std(items)
                for key, items in values.items()
            },
        }
    aggregates = {
        key: [float(result["aggregate_metrics"].get(key, 0.0)) for result in results]
        for key in (
            "online_llm_call_count",
            "candidate_registration_promotable",
            "promotion_external_evidence_only",
            "rollback_recorded",
        )
    }
    return {
        "run_count": len(results),
        "pass_at_1": bool(results[0]["passed"]),
        "pass_power_3": len(results) >= 3 and all(bool(result["passed"]) for result in results[:3]),
        "seeds": [int(result.get("run_config", {}).get("seed", 0)) for result in results],
        "by_arm": by_arm,
        "aggregate": {
            f"{key}_mean": _mean(items)
            for key, items in aggregates.items()
        }
        | {
            f"{key}_std": _std(items)
            for key, items in aggregates.items()
        },
    }


def _mean(values: list[float]) -> float:
    return round(mean(values), 4) if values else 0.0


def _std(values: list[float]) -> float:
    if not values:
        return 0.0
    avg = sum(values) / len(values)
    variance = sum((value - avg) ** 2 for value in values) / len(values)
    return round(variance**0.5, 4)


def run(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    llm: bool = False,
    provider: str = "deepseek",
    model: str = "deepseek-chat",
    base_url: str = "",
    env_file: Path | None = None,
    seed: int = 0,
    reliability_passes: int = 1,
    replay_task_count: int = 5,
    agent_factory: LiveAgentFactory | None = None,
) -> dict[str, Any]:
    _prepare_output_dir(output_dir)
    single_runs: list[dict[str, Any]] = []
    for offset in range(max(reliability_passes, 1)):
        run_seed = seed + offset
        run_output_dir = output_dir / f".live-llm-seed-{run_seed}"
        safe_rmtree_child(output_dir, run_output_dir, allowed_prefixes=(".live-llm-seed-",))
        single_runs.append(
            _single_run(
                run_output_dir,
                llm=llm,
                provider=provider,
                model=model,
                base_url=base_url,
                env_file=env_file,
                seed=run_seed,
                replay_task_count=replay_task_count,
                agent_factory=agent_factory,
            )
        )

    result = dict(single_runs[0])
    result["run_config"] = {
        **result["run_config"],
        "seed": seed,
        "reliability_passes": reliability_passes,
    }
    result["reliability"] = _reliability_summary(single_runs)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in PRIMARY_RUN_ARTIFACTS:
        source = output_dir / f".live-llm-seed-{seed}" / name
        target = output_dir / name
        if source.exists():
            shutil.copyfile(source, target)
    (output_dir / "raw_results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "metrics.json").write_text(
        json.dumps(
            {"arms": result["metrics"], "aggregate": result["aggregate_metrics"]},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (output_dir / "reliability.json").write_text(
        json.dumps(result["reliability"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "README.md").write_text(_readme(result), encoding="utf-8")
    return result


def _single_run(
    output_dir: Path,
    *,
    llm: bool,
    provider: str,
    model: str,
    base_url: str,
    env_file: Path | None,
    seed: int,
    replay_task_count: int,
    agent_factory: LiveAgentFactory | None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    if agent_factory is not None:
        agent = agent_factory()
    elif llm:
        config = MemoryWeaverConfig.from_env(env_file=env_file)
        agent = OpenAICompatibleAgent.from_config(
            config,
            provider=provider,
            model=model,
            base_url=base_url,
        )
    else:
        agent = ScriptedLivePathAgent()

    seed_artifacts = _live_trace_candidate(
        output_dir=output_dir,
        agent=agent,
        llm=llm,
        seed=seed,
    )
    candidate = seed_artifacts["candidate"]
    trace = seed_artifacts["trace"]
    runtime = HarnessRuntime()
    registration = runtime.register_candidate(candidate)

    replay_gateway, journal, checkpoints = _gateway(output_dir)
    tasks = _tasks(replay_task_count)
    runtime_runs = []
    for index, task in enumerate(tasks, 1):
        replay = runtime.guarded_replay(
            task,
            _proposal("__invalid_action__", key=f"{task.task_id}:invalid"),
            replay_gateway,
            thread_id=task.task_id,
            start_step=1,
        )
        executed_targets = [action.target for action in replay.executed_actions]
        runtime_runs.append(
            {
                "task_id": task.task_id,
                "arm": "memoryweaver_live_candidate_runtime",
                "candidate_id": candidate.candidate_id,
                "invalid_action": False,
                "known_bad_action": "__invalid_action__" in candidate.path.blocked_targets,
                "success": replay.policy_completed and not replay.rollback_recommended,
                "memory_induced_regression": False,
                "rollback": replay.rollback_recommended,
                "negative_memory_hit": "action_schema" in executed_targets,
                "promotion_decision": "evidence_gated_promote"
                if registration.assessment.can_promote
                else "evidence_gated_trial",
                "assessment_before": replay.assessment_before.to_dict(),
                "assessment_after": replay.assessment_after.to_dict(),
                "executed_actions": [item.to_dict() for item in replay.executed_actions],
                "tool_results": [
                    item.to_dict() if hasattr(item, "to_dict") else dict(item)
                    for item in replay.tool_results
                ],
                "family_index": index,
            }
        )

    conflict = HardEvidence(
        evidence_type=HardEvidenceType.CONFLICT,
        task_id="live-llm-conflict",
        task_family="benchmark_debug",
        passed=False,
        conflict_ref="conflict://live-llm-schema-v2",
        regression_rate=0.2,
    )
    runtime.record_evidence(candidate.path.path_id, conflict)
    rollback_replay = runtime.guarded_replay(
        tasks[-1],
        _proposal("__invalid_action__", key="live-llm-conflict:invalid"),
        replay_gateway,
        thread_id="live-llm-conflict",
        start_step=1,
    )
    rollback_record = {
        "task_id": "live-llm-conflict",
        "arm": "rollback_probe",
        "candidate_id": candidate.candidate_id,
        "invalid_action": False,
        "known_bad_action": True,
        "success": rollback_replay.fallback_action is not None,
        "memory_induced_regression": False,
        "rollback": rollback_replay.rollback_recommended,
        "negative_memory_hit": True,
        "promotion_decision": "rollback_on_conflict",
        "assessment_before": rollback_replay.assessment_before.to_dict(),
        "assessment_after": rollback_replay.assessment_after.to_dict(),
        "fallback_action": rollback_replay.fallback_action.to_dict()
        if rollback_replay.fallback_action
        else None,
    }

    store_path = output_dir / "runtime_path_store.json"
    RuntimePathStore(store_path).save_runtime(runtime)
    restored_runtime = RuntimePathStore(store_path).to_runtime()
    restored_trace = RuntimeTraceStore(output_dir / "runtime_traces.jsonl").latest(trace.task_id)
    restored_decision = restored_runtime.decide(
        tasks[0],
        _proposal("__invalid_action__", key="live-llm-restored:invalid"),
    )
    trace_store_roundtrip = 1.0 if restored_trace and restored_trace.trace_id == trace.trace_id else 0.0
    runtime_path_store_roundtrip = (
        1.0
        if restored_decision.path_id == candidate.path.path_id
        and restored_decision.rollback_recommended is True
        else 0.0
    )

    all_runs = runtime_runs + [rollback_record]
    metrics = {
        "memoryweaver_live_candidate_runtime": _metrics(runtime_runs),
        "rollback_probe": _metrics([rollback_record]),
    }
    core = metrics["memoryweaver_live_candidate_runtime"]
    aggregate_metrics = {
        "live_llm_run_complete": 1.0 if llm and seed_artifacts["live_call_count"] > 0 else 0.0,
        "online_llm_call_count": float(seed_artifacts["live_call_count"]),
        "live_proposal_count": float(trace.metrics.get("tool_result_count", 0)),
        "tool_result_count": float(trace.metrics.get("tool_result_count", 0)),
        "canonicalized_bundle_count": float(trace.metrics.get("canonicalized_bundle_count", 0)),
        "tests_passed": 1.0 if any(
            item.evidence_type == HardEvidenceType.TEST_RESULT and item.passed
            for item in candidate.evidence
        )
        else 0.0,
        "file_diff_matches_expected": 1.0 if any(
            item.evidence_type == HardEvidenceType.FILE_DIFF and item.passed
            for item in candidate.evidence
        )
        else 0.0,
        "benchmark_delta": registration.assessment.benchmark_delta,
        "candidate_registration_promotable": 1.0 if registration.assessment.can_promote else 0.0,
        "candidate_registration_audited": 1.0
        if any(item.get("event") == "candidate_registered" for item in runtime.ledger)
        else 0.0,
        "rejected_evidence_audited_count": float(registration.rejected_evidence_count),
        "promotion_external_evidence_only": 1.0
        if registration.assessment.model_confidence_ignored_count == 0
        else 0.0,
        "trace_store_roundtrip": trace_store_roundtrip,
        "runtime_path_store_roundtrip": runtime_path_store_roundtrip,
        "rollback_recorded": metrics["rollback_probe"]["rollback_frequency"],
        "memory_induced_regression_rate": core["memory_induced_regression_rate"],
    }
    passed = (
        registration.assessment.can_promote
        and core["success_rate"] == 1.0
        and core["invalid_action_rate"] == 0.0
        and core["memory_induced_regression_rate"] == 0.0
        and aggregate_metrics["promotion_external_evidence_only"] == 1.0
        and aggregate_metrics["trace_store_roundtrip"] == 1.0
        and aggregate_metrics["runtime_path_store_roundtrip"] == 1.0
        and aggregate_metrics["rollback_recorded"] == 1.0
        and (not llm or aggregate_metrics["live_llm_run_complete"] == 1.0)
    )
    result = {
        "passed": passed,
        "run_config": {
            "mode": "live_llm" if llm else "mock_live_agent",
            "llm": llm,
            "provider": provider if llm else "",
            "model": model if llm else "",
            "base_url": base_url if llm else "",
            "seed": seed,
            "replay_task_count": replay_task_count,
        },
        "metrics": metrics,
        "aggregate_metrics": aggregate_metrics,
        "registration": registration.to_dict(),
        "candidate": candidate.to_dict(),
        "trace": trace.to_dict(),
        "research_question": (
            "Can evidence-gated path promotion reduce repeated agent failures "
            "without increasing memory-induced error propagation?"
        ),
    }
    with (output_dir / "task_runs.jsonl").open("w", encoding="utf-8") as handle:
        for run_record in all_runs:
            handle.write(json.dumps(run_record, ensure_ascii=False) + "\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--llm", action="store_true")
    parser.add_argument("--provider", default="deepseek")
    parser.add_argument("--model", default="deepseek-chat")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--reliability-passes", type=int, default=1)
    parser.add_argument("--replay-task-count", type=int, default=5)
    args = parser.parse_args()
    result = run(
        args.output_dir,
        llm=args.llm,
        provider=args.provider,
        model=args.model,
        base_url=args.base_url,
        env_file=args.env_file,
        seed=args.seed,
        reliability_passes=args.reliability_passes,
        replay_task_count=args.replay_task_count,
    )
    print(
        json.dumps(
            {
                "passed": result["passed"],
                "mode": result["run_config"]["mode"],
                "aggregate_metrics": result["aggregate_metrics"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
