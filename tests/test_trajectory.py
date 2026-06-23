from memoryweaver.action_gate import ActionProposal
from memoryweaver.trajectory import TrajectoryRegulator, TrajectoryStatus


def test_repeated_known_bad_failure_triggers_recovery():
    regulator = TrajectoryRegulator(
        max_steps=6,
        max_tool_calls=4,
        repeated_failure_limit=2,
        stagnation_window=2,
    )
    proposal = ActionProposal(
        action_name="tool_call",
        target="reinstall_npm",
        idempotency_key="task:1:tool_call:reinstall_npm",
    )

    first = regulator.observe(
        step=1,
        proposal=proposal,
        result={"status": "failed_known_bad", "signal": "negative"},
        gate_status="allow",
    )
    assert first.status == TrajectoryStatus.CONTINUE

    second = regulator.observe(
        step=2,
        proposal=proposal,
        result={"status": "failed_known_bad", "signal": "negative"},
        gate_status="allow",
    )
    assert second.status == TrajectoryStatus.RECOVER
    assert second.repeated_failure is True
    assert second.recovery_action == "check_evidence"


def test_stagnation_and_budget_trigger_regulation():
    regulator = TrajectoryRegulator(
        max_steps=3,
        max_tool_calls=2,
        repeated_failure_limit=3,
        stagnation_window=2,
    )
    proposal = ActionProposal(
        action_name="check_evidence",
        target="ci_logs",
    )

    regulator.observe(
        step=1,
        proposal=proposal,
        result={"status": "no_signal", "signal": "neutral"},
        gate_status="allow",
    )
    recovery = regulator.observe(
        step=2,
        proposal=proposal,
        result={"status": "no_signal", "signal": "neutral"},
        gate_status="allow",
    )
    assert recovery.status == TrajectoryStatus.RECOVER
    assert recovery.stagnating is True

    halted = regulator.observe(
        step=3,
        proposal=proposal,
        result={"status": "no_signal", "signal": "neutral"},
        gate_status="allow",
    )
    assert halted.status == TrajectoryStatus.HALT
    assert halted.over_budget is True
