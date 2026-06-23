from memoryweaver.harness import MemoryWeaverHarness
from memoryweaver.runtime.live_loop import LiveAction
from memoryweaver.store import MemoryWorkspace


def test_harness_orchestrates_conditioning_execution_and_outcome(tmp_path):
    workspace = MemoryWorkspace(tmp_path / ".memoryweaver")
    harness = MemoryWeaverHarness(workspace)

    interaction = harness.before_interaction(
        "Resolve Codex subscription load failure.",
        scope="project",
    )
    assert interaction.contract_version == "environment-contract-v1"
    assert interaction.workspace_validate["valid"] is True

    conditioning = harness.task_conditioning(
        "Codex subscription load failed after install",
        tags=["codex", "subscription"],
        arm="mw_marker",
        step=1,
    )
    assert conditioning.runtime_decision["marker_activated"] is True
    assert "Diagnostic Guidance" in conditioning.combined_context

    blocked = harness.before_execution(
        LiveAction(name="tool_call", target="reset_auth_files"),
        task_id="tau_harness",
        step=1,
    )
    assert blocked.decision.allowed is False
    assert blocked.decision.status.value == "needs_confirmation"

    allowed = harness.before_execution(
        LiveAction(name="check_evidence", target="selected_organization"),
        task_id="tau_harness",
        step=1,
    )
    assert allowed.decision.allowed is True

    feedback = harness.after_feedback(
        step=1,
        proposal=allowed.proposal,
        result={"status": "evidence_observed", "signal": "positive"},
        gate_status=allowed.decision.status.value,
    )
    assert feedback.trajectory.status.value == "continue"

    outcome = harness.after_task_outcome(
        task_id="tau_harness",
        step=1,
        action=LiveAction(name="check_evidence", target="selected_organization"),
        result={
            "status": "evidence_observed",
            "signal": "positive",
            "evidence": "selected organization resolved the failure",
        },
    )
    assert outcome.verified_write_count == 1
    assert workspace.memories.count() == 1
