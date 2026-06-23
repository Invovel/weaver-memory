from memoryweaver import (
    ActionGate,
    ActionProposal,
    EnvironmentContract,
    EventJournal,
    HardEvidenceType,
    HarnessRuntime,
    RuntimeTask,
    RuntimeTraceRecorder,
    RuntimeTraceStore,
    ToolGateway,
    extract_candidate_path_from_trace,
)


def test_runtime_trace_store_roundtrip(tmp_path):
    store = RuntimeTraceStore(tmp_path / "runtime_traces.jsonl")
    recorder = RuntimeTraceRecorder(
        trace_id="trace-1",
        task_id="task-1",
        task_type="benchmark_debug",
        user_goal="debug invalid action",
        initial_context={"family": "benchmark_debug"},
        thread_id="thread-1",
        store=store,
    )
    recorder.record_step(
        node_name="match_path",
        action_type="check_condition",
        observation={"matched": True},
        status="matched",
        latency_ms=5,
    )
    trace = recorder.finish(
        final_result={"selected_action": "check_evidence"},
        success=True,
    )

    reloaded = RuntimeTraceStore(tmp_path / "runtime_traces.jsonl")
    restored = reloaded.latest("task-1")

    assert trace.finished_at
    assert restored is not None
    assert restored.trace_id == "trace-1"
    assert restored.task_type == "benchmark_debug"
    assert restored.steps[0].node_name == "match_path"
    assert restored.final_result["selected_action"] == "check_evidence"
    assert restored.metrics["step_count"] == 1
    assert restored.metrics["total_latency_ms"] == 5
    assert restored.metrics["action_type_counts"]["check_condition"] == 1
    assert restored.metrics["status_counts"]["matched"] == 1


def test_runtime_trace_recorder_records_tool_gateway_result(tmp_path):
    journal = EventJournal(tmp_path / "events.jsonl")
    gateway = ToolGateway(
        ActionGate(EnvironmentContract.default_live_loop()),
        journal=journal,
    )
    gateway.register(
        "check_evidence",
        lambda proposal: {
            "status": "evidence_observed",
            "signal": "positive",
            "evidence": f"{proposal.target} verified",
            "known_bad_avoided": True,
        },
    )

    result = gateway.execute(
        ActionProposal(
            action_name="check_evidence",
            target="action_schema",
            arguments={"target": "action_schema"},
        ),
        thread_id="thread-trace",
        step=1,
    )

    recorder = RuntimeTraceRecorder(
        trace_id="trace-tool-1",
        task_id="task-tool-1",
        task_type="benchmark_debug",
    )
    step = recorder.record_tool_result(
        node_name="check_schema",
        result=result,
        thought_summary="verify schema before replay",
        latency_ms=12,
        token_cost=0,
    )
    trace = recorder.finish(success=True)

    assert step.action_type == "check_evidence"
    assert step.tool_name == "check_evidence"
    assert step.tool_args["target"] == "action_schema"
    assert step.observation["evidence"] == "action_schema verified"
    assert step.metadata["target"] == "action_schema"
    assert trace.steps[0].event_id == "evt_00000001"
    assert trace.metrics["step_count"] == 1
    assert trace.metrics["tool_action_count"] == 1
    assert trace.metrics["tool_result_count"] == 1
    assert trace.metrics["successful_tool_result_count"] == 1
    assert trace.metrics["failed_tool_result_count"] == 0
    assert trace.metrics["duplicate_tool_result_count"] == 0
    assert trace.metrics["event_linked_step_count"] == 1
    assert trace.metrics["total_latency_ms"] == 12
    assert trace.metrics["action_type_counts"]["check_evidence"] == 1
    assert trace.metrics["status_counts"]["evidence_observed"] == 1


def test_runtime_trace_recorder_step_ids_increment():
    recorder = RuntimeTraceRecorder(
        trace_id="trace-steps",
        task_id="task-steps",
    )

    first = recorder.record_step(
        node_name="match_path",
        action_type="check_condition",
        status="matched",
    )
    second = recorder.record_step(
        node_name="fallback",
        action_type="ask_user",
        status="queued",
    )

    assert first.step_id == "step_0001"
    assert second.step_id == "step_0002"


def test_runtime_trace_recorder_tracks_duplicate_and_failed_tool_results(tmp_path):
    journal = EventJournal(tmp_path / "events.jsonl")
    gateway = ToolGateway(
        ActionGate(EnvironmentContract.default_live_loop()),
        journal=journal,
    )
    gateway.register(
        "tool_call",
        lambda proposal: {
            "status": "passed",
            "signal": "positive",
            "evidence": f"{proposal.target} executed",
        },
    )
    proposal = ActionProposal(
        action_name="tool_call",
        target="safe_mock_tool",
        arguments={"target": "safe_mock_tool"},
        idempotency_key="trace-dup:tool:safe_mock_tool",
    )

    first = gateway.execute(proposal, thread_id="trace-dup", step=1)
    second = gateway.execute(proposal, thread_id="trace-dup", step=2)

    recorder = RuntimeTraceRecorder(
        trace_id="trace-dup-1",
        task_id="task-dup-1",
    )
    recorder.record_tool_result(node_name="tool_exec", result=first, latency_ms=3)
    recorder.record_tool_result(node_name="tool_exec", result=second, latency_ms=4)
    trace = recorder.finish(success=False)

    assert trace.metrics["step_count"] == 2
    assert trace.metrics["tool_result_count"] == 2
    assert trace.metrics["successful_tool_result_count"] == 1
    assert trace.metrics["failed_tool_result_count"] == 1
    assert trace.metrics["duplicate_tool_result_count"] == 1
    assert trace.metrics["event_linked_step_count"] == 2
    assert trace.metrics["total_latency_ms"] == 7
    assert trace.metrics["status_counts"]["passed"] == 1
    assert trace.metrics["status_counts"]["duplicate_suppressed"] == 1


def test_trace_to_candidate_path_filters_invalid_action_and_syncs_hard_metrics(tmp_path):
    journal = EventJournal(tmp_path / "events.jsonl")
    gateway = ToolGateway(
        ActionGate(EnvironmentContract.default_live_loop()),
        journal=journal,
    )
    gateway.register(
        "check_evidence",
        lambda proposal: {
            "status": "evidence_observed",
            "signal": "positive",
            "evidence": f"{proposal.target} verified",
            "known_bad_avoided": proposal.target == "action_schema",
            "evidence_first": True,
        },
    )
    gateway.register(
        "tool_call",
        lambda proposal: {
            "status": "invalid_action",
            "signal": "negative",
            "evidence": "__invalid_action__ rejected",
            "false_trigger": True,
        },
    )

    invalid = gateway.execute(
        ActionProposal(
            action_name="tool_call",
            target="__invalid_action__",
            arguments={"target": "__invalid_action__"},
        ),
        thread_id="trace-candidate",
        step=1,
    )
    schema = gateway.execute(
        ActionProposal(
            action_name="check_evidence",
            target="action_schema",
            arguments={"target": "action_schema"},
        ),
        thread_id="trace-candidate",
        step=2,
    )

    recorder = RuntimeTraceRecorder(
        trace_id="trace-candidate-1",
        task_id="bench-debug-1",
        task_type="benchmark_debug",
        user_goal="debug invalid_action",
        initial_context={
            "tags": ["benchmark", "debug"],
            "failure_mode": "invalid_action",
        },
    )
    recorder.record_tool_result(node_name="bad_action", result=invalid, latency_ms=4)
    recorder.record_tool_result(node_name="check_schema", result=schema, latency_ms=8)
    trace = recorder.finish(
        success=True,
        metrics={
            "tests_passed": True,
            "file_diff_matches_expected": True,
            "score_before": 0.70,
            "score_after": 0.82,
            "repeat_validation_count": 3,
            "known_bad_avoided": True,
            "evidence_first": True,
        },
    )

    candidate = extract_candidate_path_from_trace(trace)
    evidence_types = {item.evidence_type for item in candidate.evidence}

    assert candidate.path.condition.task_tags == ["benchmark", "debug"]
    assert candidate.path.condition.failure_modes == ["invalid_action"]
    assert candidate.path.blocked_targets == ["__invalid_action__"]
    assert [action.target for action in candidate.path.action_policy] == ["action_schema"]
    assert candidate.rejected_evidence[0].target == "__invalid_action__"
    assert candidate.rejected_evidence[0].false_trigger is True
    assert HardEvidenceType.TOOL_RESULT in evidence_types
    assert HardEvidenceType.TEST_RESULT in evidence_types
    assert HardEvidenceType.FILE_DIFF in evidence_types
    assert HardEvidenceType.BENCHMARK_SCORE in evidence_types
    assert HardEvidenceType.REPEAT_VALIDATION in evidence_types
    assert candidate.metrics["tool_result_count"] == 2
    assert candidate.metrics["failed_tool_result_count"] == 1
    assert "bad actions were retained" in candidate.notes[0]

    runtime = HarnessRuntime(paths=[candidate.path])
    runtime.record_evidence(candidate.path.path_id, candidate.evidence)
    assessment = runtime.assess(candidate.path.path_id)
    assert assessment.can_promote is True
    assert assessment.repeated_validation_count == 3
    assert assessment.benchmark_delta == 0.12


def test_trace_to_candidate_path_keeps_multi_step_runtime_policy(tmp_path):
    journal = EventJournal(tmp_path / "events.jsonl")
    gateway = ToolGateway(
        ActionGate(EnvironmentContract.default_live_loop()),
        journal=journal,
    )
    gateway.register(
        "check_evidence",
        lambda proposal: {
            "status": "evidence_observed",
            "signal": "positive",
            "evidence": f"{proposal.target} verified",
            "known_bad_avoided": proposal.target == "action_schema",
            "evidence_first": proposal.target == "action_schema",
        },
    )
    recorder = RuntimeTraceRecorder(
        trace_id="trace-candidate-multi-1",
        task_id="bench-debug-multi-1",
        task_type="benchmark_debug",
        initial_context={
            "tags": ["benchmark", "debug"],
            "failure_mode": "invalid_action",
        },
    )
    recorder.record_tool_result(
        node_name="check_schema",
        result=gateway.execute(
            ActionProposal(
                action_name="check_evidence",
                target="action_schema",
                arguments={"target": "action_schema"},
            ),
            thread_id="trace-candidate-multi",
            step=1,
        ),
    )
    recorder.record_tool_result(
        node_name="isolate_marker_only",
        result=gateway.execute(
            ActionProposal(
                action_name="check_evidence",
                target="marker_only_boundary",
                arguments={"target": "marker_only_boundary"},
            ),
            thread_id="trace-candidate-multi",
            step=2,
        ),
    )
    recorder.record_tool_result(
        node_name="run_pass_power_3",
        result=gateway.execute(
            ActionProposal(
                action_name="check_evidence",
                target="pass_power_3",
                arguments={"target": "pass_power_3"},
            ),
            thread_id="trace-candidate-multi",
            step=3,
        ),
    )
    trace = recorder.finish(
        success=True,
        metrics={
            "tests_passed": True,
            "file_diff_matches_expected": True,
            "score_before": 0.72,
            "score_after": 0.88,
            "repeat_validation_count": 3,
            "known_bad_avoided": True,
            "evidence_first": True,
        },
    )

    candidate = extract_candidate_path_from_trace(trace)

    assert [action.target for action in candidate.path.action_policy] == [
        "action_schema",
        "marker_only_boundary",
        "pass_power_3",
    ]


def test_trace_to_candidate_path_emits_conflict_and_rollback_evidence():
    recorder = RuntimeTraceRecorder(
        trace_id="trace-conflict-1",
        task_id="bench-debug-conflict",
        task_type="benchmark_debug",
        initial_context={"failure_mode": "invalid_action"},
    )
    trace = recorder.finish(
        success=False,
        metrics={
            "conflict_count": 1,
            "conflict_ref": "conflict://schema-break",
            "rollback_count": 1,
            "rollback_ref": "rollback://path-invalid-action",
            "memory_induced_regression_rate": 0.2,
        },
    )

    candidate = extract_candidate_path_from_trace(trace)
    evidence_types = [item.evidence_type for item in candidate.evidence]

    assert HardEvidenceType.CONFLICT in evidence_types
    assert HardEvidenceType.ROLLBACK_RECORD in evidence_types

    runtime = HarnessRuntime(paths=[candidate.path])
    runtime.record_evidence(candidate.path.path_id, candidate.evidence)
    assessment = runtime.assess(candidate.path.path_id)

    assert assessment.should_rollback is True
    assert assessment.can_promote is False
    assert assessment.conflict_count == 1
    assert assessment.memory_induced_regression_rate == 0.2


def test_harness_runtime_registers_trace_candidate_without_polluting_with_rejected_evidence(tmp_path):
    journal = EventJournal(tmp_path / "events.jsonl")
    gateway = ToolGateway(
        ActionGate(EnvironmentContract.default_live_loop()),
        journal=journal,
    )
    gateway.register(
        "check_evidence",
        lambda proposal: {
            "status": "evidence_observed",
            "signal": "positive",
            "evidence": f"{proposal.target} verified",
            "known_bad_avoided": True,
            "evidence_first": True,
        },
    )

    schema = gateway.execute(
        ActionProposal(
            action_name="check_evidence",
            target="action_schema",
            arguments={"target": "action_schema"},
        ),
        thread_id="trace-register",
        step=1,
    )

    recorder = RuntimeTraceRecorder(
        trace_id="trace-register-1",
        task_id="bench-register-1",
        task_type="benchmark_debug",
        initial_context={
            "tags": ["benchmark", "debug"],
            "failure_mode": "invalid_action",
        },
    )
    recorder.record_step(
        node_name="bad_action",
        action_type="tool_call",
        tool_name="tool_call",
        tool_args={"target": "__invalid_action__"},
        status="blocked_by_action_gate",
        observation={"evidence": "__invalid_action__ blocked"},
    )
    recorder.record_tool_result(node_name="check_schema", result=schema)
    trace = recorder.finish(
        success=True,
        metrics={
            "tests_passed": True,
            "file_diff_matches_expected": True,
            "score_before": 0.7,
            "score_after": 0.9,
            "repeat_validation_count": 3,
            "known_bad_avoided": True,
            "evidence_first": True,
        },
    )
    candidate = extract_candidate_path_from_trace(trace)

    runtime = HarnessRuntime()
    registration = runtime.register_candidate(candidate)

    assert registration.initial_evidence_count == len(candidate.evidence)
    assert registration.rejected_evidence_count == 1
    assert registration.rejected_as_challenge is False
    assert registration.assessment.can_promote is True
    assert registration.assessment.counterexample_count == 0
    assert runtime.ledger[-1]["event"] == "candidate_registered"
    assert runtime.ledger[-1]["rejected_evidence_count"] == 1

    decision = runtime.decide(
        RuntimeTask(
            task_id="bench-register-replay",
            query="benchmark debug invalid_action",
            tags=["benchmark", "debug"],
            state={"failure_mode": "invalid_action"},
        ),
        ActionProposal(
            action_name="tool_call",
            target="__invalid_action__",
            arguments={"target": "__invalid_action__"},
        ),
    )

    assert decision.condition_matched is True
    assert decision.selected_action.target == "action_schema"
    assert decision.rollback_recommended is False


def test_harness_runtime_can_challenge_candidate_with_rejected_evidence(tmp_path):
    journal = EventJournal(tmp_path / "events.jsonl")
    gateway = ToolGateway(
        ActionGate(EnvironmentContract.default_live_loop()),
        journal=journal,
    )
    gateway.register(
        "check_evidence",
        lambda proposal: {
            "status": "evidence_observed",
            "signal": "positive",
            "evidence": f"{proposal.target} verified",
        },
    )
    schema = gateway.execute(
        ActionProposal(
            action_name="check_evidence",
            target="action_schema",
            arguments={"target": "action_schema"},
        ),
        thread_id="trace-register-challenge",
        step=1,
    )

    recorder = RuntimeTraceRecorder(
        trace_id="trace-register-challenge-1",
        task_id="bench-register-challenge-1",
        task_type="benchmark_debug",
        initial_context={"failure_mode": "invalid_action"},
    )
    recorder.record_step(
        node_name="bad_action",
        action_type="tool_call",
        tool_name="tool_call",
        tool_args={"target": "__invalid_action__"},
        status="invalid_action",
        observation={"evidence": "__invalid_action__ executed"},
    )
    recorder.record_tool_result(node_name="check_schema", result=schema)
    trace = recorder.finish(
        success=False,
        metrics={
            "tests_passed": True,
            "score_before": 0.7,
            "score_after": 0.8,
            "repeat_validation_count": 3,
        },
    )
    candidate = extract_candidate_path_from_trace(trace)

    runtime = HarnessRuntime()
    registration = runtime.register_candidate(
        candidate,
        challenge_with_rejected=True,
    )

    assert registration.rejected_as_challenge is True
    assert registration.assessment.should_rollback is True
    assert registration.assessment.can_promote is False
    assert registration.assessment.counterexample_count == 1
    assert runtime.ledger[-1]["rejected_as_challenge"] is True
