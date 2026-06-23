from memoryweaver import (
    ActionGate,
    ActionProposal,
    CheckpointStore,
    EnvironmentContract,
    EventJournal,
    HardEvidenceType,
    ToolExecutionResult,
    ToolGateway,
)


def _gateway(tmp_path):
    journal = EventJournal(tmp_path / "events.jsonl")
    checkpoints = CheckpointStore(tmp_path / "checkpoints.json")
    gateway = ToolGateway(
        ActionGate(EnvironmentContract.default_live_loop()),
        journal=journal,
        checkpoints=checkpoints,
    )
    return gateway, journal, checkpoints


def test_tool_gateway_records_allowed_tool_result_as_hard_evidence(tmp_path):
    gateway, journal, checkpoints = _gateway(tmp_path)
    gateway.register(
        "check_evidence",
        lambda proposal: {
            "status": "evidence_observed",
            "signal": "positive",
            "evidence": f"{proposal.target} passed",
            "known_bad_avoided": True,
            "evidence_first": True,
        },
    )

    result = gateway.execute(
        ActionProposal(
            action_name="check_evidence",
            target="action_schema",
            arguments={"target": "action_schema"},
        ),
        thread_id="thread-1",
        step=1,
    )
    evidence = result.to_hard_evidence(
        task_id="bench-debug-1",
        task_family="benchmark_debug",
    )

    assert result.executed is True
    assert result.event_id == "evt_00000001"
    assert evidence.evidence_type == HardEvidenceType.TOOL_RESULT
    assert evidence.passed is True
    assert evidence.evidence_first is True
    assert journal.list_events()[0].event_type == "tool_result"
    assert checkpoints.latest("thread-1").last_event_id == "evt_00000001"


def test_tool_result_does_not_infer_promotion_flags_from_action_name(tmp_path):
    gateway, _, _ = _gateway(tmp_path)
    gateway.register(
        "check_evidence",
        lambda proposal: {
            "status": "evidence_observed",
            "signal": "positive",
            "evidence": f"{proposal.target} passed",
        },
    )

    result = gateway.execute(
        ActionProposal(
            action_name="check_evidence",
            target="action_schema",
            arguments={"target": "action_schema"},
        ),
        thread_id="thread-no-flags",
        step=1,
    )
    evidence = result.to_hard_evidence(
        task_id="bench-debug-no-flags",
        task_family="benchmark_debug",
    )

    assert evidence.passed is True
    assert evidence.known_bad_avoided is False
    assert evidence.evidence_first is False


def test_tool_gateway_blocks_unknown_action_and_checkpoints(tmp_path):
    gateway, journal, checkpoints = _gateway(tmp_path)

    result = gateway.execute(
        ActionProposal(
            action_name="shell_exec",
            target="rm -rf /",
            arguments={"target": "rm -rf /"},
        ),
        thread_id="thread-2",
        step=1,
    )

    assert result.executed is False
    assert result.status == "blocked_by_action_gate"
    assert "allowlisted" in result.evidence
    assert journal.list_events()[0].payload["status"] == "blocked_by_action_gate"
    assert checkpoints.latest("thread-2").state["last_tool_status"] == "blocked_by_action_gate"


def test_tool_gateway_suppresses_duplicate_idempotency_key(tmp_path):
    gateway, journal, checkpoints = _gateway(tmp_path)
    calls = {"count": 0}

    def handler(proposal):
        calls["count"] += 1
        return {
            "status": "passed",
            "signal": "positive",
            "evidence": f"{proposal.target} executed",
        }

    gateway.register("tool_call", handler)
    proposal = ActionProposal(
        action_name="tool_call",
        target="safe_mock_tool",
        arguments={"target": "safe_mock_tool"},
        idempotency_key="thread-3:tool:safe_mock_tool",
    )

    first = gateway.execute(proposal, thread_id="thread-3", step=1)
    second = gateway.execute(proposal, thread_id="thread-3", step=2)

    assert first.executed is True
    assert second.executed is False
    assert second.duplicate is True
    assert second.status == "duplicate_suppressed"
    assert calls["count"] == 1
    assert len(journal.list_events()) == 2
    assert checkpoints.latest("thread-3").state["duplicate"] is True


def test_tool_gateway_suppresses_duplicate_idempotency_key_after_reload(tmp_path):
    gateway, _, _ = _gateway(tmp_path)
    calls = {"count": 0}

    def handler(proposal):
        calls["count"] += 1
        return {
            "status": "passed",
            "signal": "positive",
            "evidence": f"{proposal.target} executed",
        }

    proposal = ActionProposal(
        action_name="tool_call",
        target="safe_mock_tool",
        arguments={"target": "safe_mock_tool"},
        idempotency_key="thread-3-reload:tool:safe_mock_tool",
    )
    gateway.register("tool_call", handler)
    first = gateway.execute(proposal, thread_id="thread-3-reload", step=1)

    reloaded_gateway = ToolGateway(
        ActionGate(EnvironmentContract.default_live_loop()),
        journal=EventJournal(tmp_path / "events.jsonl"),
        checkpoints=CheckpointStore(tmp_path / "checkpoints.json"),
    )
    reloaded_gateway.register("tool_call", handler)
    second = reloaded_gateway.execute(proposal, thread_id="thread-3-reload", step=2)

    assert first.executed is True
    assert second.executed is False
    assert second.duplicate is True
    assert second.status == "duplicate_suppressed"
    assert calls["count"] == 1


def test_event_journal_and_checkpoint_store_reload(tmp_path):
    gateway, _, _ = _gateway(tmp_path)
    gateway.register(
        "check_evidence",
        lambda proposal: {
            "status": "passed",
            "signal": "positive",
            "evidence": "reloadable evidence",
        },
    )
    gateway.execute(
        ActionProposal(
            action_name="check_evidence",
            target="reload",
            arguments={"target": "reload"},
        ),
        thread_id="thread-4",
        step=1,
    )

    reloaded_journal = EventJournal(tmp_path / "events.jsonl")
    reloaded_checkpoints = CheckpointStore(tmp_path / "checkpoints.json")

    assert reloaded_journal.list_events()[0].event_id == "evt_00000001"
    assert reloaded_checkpoints.latest("thread-4").state["last_tool_status"] == "passed"
