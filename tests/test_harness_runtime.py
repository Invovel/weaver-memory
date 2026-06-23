from datetime import datetime, timezone

from memoryweaver import (
    ActionGateStatus,
    ActionProposal,
    ActionGate,
    EnvironmentContract,
    EventJournal,
    HardEvidence,
    HardEvidenceType,
    HarnessRuntime,
    RuntimePathCondition,
    RuntimePathRollbackRule,
    RuntimePathSpec,
    RuntimePathStore,
    RuntimePathValidationGate,
    RuntimeTask,
    ToolGateway,
)
from memoryweaver.composer import PatternComposer
from memoryweaver.evidence import EvidenceLink, EvidenceNode
from memoryweaver.schema import Freshness, MemoryItem, PatternStatus
from memoryweaver.store import MemoryWorkspace


def _runtime_path(pattern_id: str = "") -> RuntimePathSpec:
    return RuntimePathSpec(
        path_id="path_invalid_action_benchmark_debug",
        name="Benchmark invalid_action recovery path",
        condition=RuntimePathCondition(
            task_tags=["benchmark", "debug"],
            query_terms=["invalid_action"],
            failure_modes=["invalid_action"],
        ),
        action_policy=[
            ActionProposal(
                action_name="check_evidence",
                target="action_schema",
                arguments={"target": "action_schema"},
            ),
            ActionProposal(
                action_name="check_evidence",
                target="marker_only_boundary",
                arguments={"target": "marker_only_boundary"},
            ),
            ActionProposal(
                action_name="check_evidence",
                target="pass_power_3",
                arguments={"target": "pass_power_3"},
            ),
        ],
        validation_gate=RuntimePathValidationGate(
            required_evidence=[
                HardEvidenceType.TEST_RESULT,
                HardEvidenceType.FILE_DIFF,
                HardEvidenceType.BENCHMARK_SCORE,
                HardEvidenceType.REPEAT_VALIDATION,
            ],
            min_repeated_validations=3,
            min_benchmark_delta=0.01,
            max_counterexamples=0,
            max_conflicts=0,
            max_memory_induced_regression_rate=0.0,
            min_decayed_support=3.0,
        ),
        fallback=ActionProposal(
            action_name="ask_user",
            target="confirm_safe_debug_path",
            arguments={"target": "confirm_safe_debug_path"},
        ),
        rollback_rule=RuntimePathRollbackRule(
            rollback_on_conflict=True,
            rollback_on_counterexamples=1,
            rollback_on_regression_rate=0.0,
            rollback_reason="runtime path introduced regression evidence",
        ),
        pattern_id=pattern_id,
        blocked_targets=["__invalid_action__"],
    )


def _task() -> RuntimeTask:
    return RuntimeTask(
        task_id="bench-debug-1",
        task_family="benchmark_debug",
        query="benchmark debug hit invalid_action in experience transfer",
        tags=["benchmark", "debug"],
        state={"failure_mode": "invalid_action"},
    )


def _hard_positive_evidence(task_id: str) -> list[HardEvidence]:
    return [
        HardEvidence(
            evidence_type=HardEvidenceType.TEST_RESULT,
            task_id=task_id,
            passed=True,
            status="passed",
            target="pass_power_3",
        ),
        HardEvidence(
            evidence_type=HardEvidenceType.FILE_DIFF,
            task_id=task_id,
            passed=True,
            expected="split marker-only boundary",
            observed="marker-only boundary isolated",
            target="marker_only_boundary",
        ),
        HardEvidence(
            evidence_type=HardEvidenceType.BENCHMARK_SCORE,
            task_id=task_id,
            passed=True,
            score_before=0.72,
            score_after=0.86,
        ),
        HardEvidence(
            evidence_type=HardEvidenceType.REPEAT_VALIDATION,
            task_id=task_id,
            passed=True,
            count=1,
            known_bad_avoided=True,
            evidence_first=True,
            target="action_schema",
        ),
    ]


def _prepared_pattern(tmp_path):
    workspace = MemoryWorkspace(tmp_path)
    memories = []
    for content in (
        "invalid_action came from action schema drift",
        "pass^3 and marker-only isolation reduced benchmark contamination",
    ):
        item = MemoryItem(content=content, source="terminal", evidence="test output")
        workspace.memories.add(item)
        workspace.memory_policy.promote_to_layer2(item, [])
        workspace.memories.update(item)
        memories.append(item)

    node = EvidenceNode(
        text="pytest and benchmark output validate action schema first",
        source="terminal",
        source_uri="pytest://harness-runtime",
    )
    workspace.evidence.add_node(node)
    link = EvidenceLink(evidence_id=node.id, memory_id=memories[0].id)
    workspace.evidence.add_link(link)
    composer = PatternComposer(
        workspace.memories,
        workspace.patterns,
        workspace.evidence,
        workspace.memory_policy,
    )
    pattern = composer.compose(
        supporting_memory_ids=[item.id for item in memories],
        rule="For benchmark debug invalid_action, check schema, isolate marker-only, then run pass^3",
        applies_when=["benchmark debug invalid_action"],
        avoid_when=["retry invalid action"],
        success_path=["action_schema", "marker_only_boundary", "pass_power_3"],
        failed_path=["__invalid_action__"],
        evidence_link_ids=[link.id],
        scope="project",
    )
    pattern.freshness = Freshness.STABLE
    workspace.patterns.update(pattern)
    return workspace, composer, pattern


def test_harness_runtime_uses_path_policy_before_invalid_action():
    runtime = HarnessRuntime(paths=[_runtime_path()])
    decision = runtime.decide(
        _task(),
        ActionProposal(
            action_name="tool_call",
            target="__invalid_action__",
            arguments={"target": "__invalid_action__"},
            idempotency_key="bench-debug-1:1:invalid",
        ),
    )

    assert decision.condition_matched is True
    assert decision.selected_action.action_name == "check_evidence"
    assert decision.selected_action.target == "action_schema"
    assert decision.action_gate.status == ActionGateStatus.ALLOW


def test_harness_runtime_ignores_model_confidence_for_promotion():
    runtime = HarnessRuntime(paths=[_runtime_path()])
    runtime.record_evidence(
        "path_invalid_action_benchmark_debug",
        HardEvidence(
            evidence_type=HardEvidenceType.MODEL_CONFIDENCE,
            task_id="bench-debug-1",
            passed=True,
            count=99,
            metadata={"confidence": 0.99},
        ),
    )

    assessment = runtime.assess("path_invalid_action_benchmark_debug")

    assert assessment.can_promote is False
    assert assessment.hard_evidence_count == 0
    assert assessment.model_confidence_ignored_count == 1
    assert "model confidence ignored for promotion" in assessment.reasons


def test_harness_runtime_promotes_pattern_from_hard_evidence(tmp_path):
    _, composer, pattern = _prepared_pattern(tmp_path)
    runtime = HarnessRuntime(
        paths=[_runtime_path(pattern.id)],
        composer=composer,
        now=datetime.now(timezone.utc),
    )

    result = None
    for index in range(1, 4):
        task_run_id = f"bench-debug-{index}"
        result = runtime.record_trial(
            "path_invalid_action_benchmark_debug",
            task_run_id=task_run_id,
            evidence=_hard_positive_evidence(task_run_id),
            selected_cost=1,
            baseline_cost=4,
        )

    assert result is not None
    assert result.promoted is True
    assert result.pattern is not None
    assert result.pattern.status == PatternStatus.STABLE
    assert result.assessment.can_promote is True
    assert result.assessment.repeated_validation_count == 3
    assert result.assessment.benchmark_delta == 0.14


def test_harness_runtime_rolls_back_on_conflict_evidence(tmp_path):
    _, composer, pattern = _prepared_pattern(tmp_path)
    runtime = HarnessRuntime(
        paths=[_runtime_path(pattern.id)],
        composer=composer,
    )

    result = runtime.record_trial(
        "path_invalid_action_benchmark_debug",
        task_run_id="bench-debug-conflict",
        evidence=[
            HardEvidence(
                evidence_type=HardEvidenceType.CONFLICT,
                task_id="bench-debug-conflict",
                passed=False,
                conflict_ref="conflict://new-schema-breaks-pass3",
                regression_rate=0.2,
            )
        ],
    )

    assert result.rolled_back is True
    assert result.pattern is not None
    assert result.pattern.status == PatternStatus.ROLLED_BACK
    assert result.assessment.should_rollback is True
    assert result.assessment.conflict_count == 1


def test_runtime_path_store_roundtrips_paths_evidence_and_ledger(tmp_path):
    store_path = tmp_path / "runtime_paths.json"
    runtime = HarnessRuntime(paths=[_runtime_path()])
    runtime.record_evidence(
        "path_invalid_action_benchmark_debug",
        _hard_positive_evidence("bench-debug-1"),
    )
    decision = runtime.decide(
        _task(),
        ActionProposal(
            action_name="tool_call",
            target="__invalid_action__",
            arguments={"target": "__invalid_action__"},
            idempotency_key="bench-debug-store:1:invalid",
        ),
    )
    assert decision.selected_action.target == "action_schema"

    store = RuntimePathStore(store_path)
    store.save_runtime(runtime)

    restored = RuntimePathStore(store_path).to_runtime()
    evidence = restored.evidence_for("path_invalid_action_benchmark_debug")
    assert len(evidence) == 4
    assert restored.ledger[0]["event"] == "evidence"
    assert restored.ledger[-1]["event"] == "decision"

    restored.record_evidence(
        "path_invalid_action_benchmark_debug",
        HardEvidence(
            evidence_type=HardEvidenceType.CONFLICT,
            task_id="bench-debug-conflict",
            passed=False,
            conflict_ref="conflict://persisted-schema-break",
            regression_rate=0.2,
        ),
    )
    rollback_decision = restored.decide(
        _task(),
        ActionProposal(
            action_name="tool_call",
            target="__invalid_action__",
            arguments={"target": "__invalid_action__"},
            idempotency_key="bench-debug-store:2:invalid",
        ),
    )
    assert rollback_decision.rollback_recommended is True
    assert rollback_decision.selected_action.action_name == "ask_user"


def test_guarded_replay_uses_task_scoped_evidence_and_executes_policy_steps(tmp_path):
    runtime = HarnessRuntime(paths=[_runtime_path()])
    runtime.record_evidence(
        "path_invalid_action_benchmark_debug",
        _hard_positive_evidence("seed-task"),
    )
    gateway = ToolGateway(
        ActionGate(EnvironmentContract.default_live_loop()),
        journal=EventJournal(tmp_path / "events.jsonl"),
    )
    gateway.register(
        "check_evidence",
        lambda proposal: {
            "status": "evidence_observed",
            "signal": "positive",
            "evidence": f"{proposal.target} replay verified",
            "known_bad_avoided": proposal.target == "action_schema",
            "evidence_first": proposal.target == "action_schema",
        },
    )
    task = RuntimeTask(
        task_id="bench-debug-replay-1",
        task_family="benchmark_debug",
        query="benchmark debug invalid_action replay task",
        tags=["benchmark", "debug"],
        state={"failure_mode": "invalid_action"},
    )

    replay = runtime.guarded_replay(
        task,
        ActionProposal(
            action_name="tool_call",
            target="__invalid_action__",
            arguments={"target": "__invalid_action__"},
            idempotency_key="bench-debug-replay-1:invalid",
        ),
        gateway,
        thread_id=task.task_id,
        start_step=1,
    )

    assert replay.matched is True
    assert replay.policy_completed is True
    assert replay.rollback_recommended is False
    assert [action.target for action in replay.executed_actions] == [
        "action_schema",
        "marker_only_boundary",
        "pass_power_3",
    ]
    assert replay.skipped_targets == []
    assert len(replay.tool_results) == 3


def test_harness_runtime_prefers_healthier_replacement_path_after_conflict():
    old_path = _runtime_path()
    old_path.path_id = "path_old_invalid_action"
    old_path.name = "Old invalid_action path"

    replacement = _runtime_path()
    replacement.path_id = "path_replacement_invalid_action"
    replacement.name = "Replacement invalid_action path"
    replacement.action_policy = [
        ActionProposal(
            action_name="check_evidence",
            target="action_schema_v2",
            arguments={"target": "action_schema_v2"},
        ),
        ActionProposal(
            action_name="check_evidence",
            target="marker_only_boundary_v2",
            arguments={"target": "marker_only_boundary_v2"},
        ),
        ActionProposal(
            action_name="check_evidence",
            target="pass_power_3_v2",
            arguments={"target": "pass_power_3_v2"},
        ),
    ]

    runtime = HarnessRuntime(paths=[old_path, replacement])
    for evidence in _hard_positive_evidence("old-seed"):
        runtime.record_evidence("path_old_invalid_action", evidence)
    for evidence in _hard_positive_evidence("replacement-seed"):
        runtime.record_evidence("path_replacement_invalid_action", evidence)

    runtime.record_evidence(
        "path_old_invalid_action",
        HardEvidence(
            evidence_type=HardEvidenceType.CONFLICT,
            task_id="old-conflict",
            passed=False,
            conflict_ref="conflict://old-path-stale",
            regression_rate=0.2,
        ),
    )

    decision = runtime.decide(
        _task(),
        ActionProposal(
            action_name="tool_call",
            target="__invalid_action__",
            arguments={"target": "__invalid_action__"},
            idempotency_key="replacement-choice:invalid",
        ),
    )

    assert decision.path_id == "path_replacement_invalid_action"
    assert decision.selected_action.target == "action_schema_v2"
    assert decision.rollback_recommended is False
