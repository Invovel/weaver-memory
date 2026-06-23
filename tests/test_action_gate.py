import pytest

from memoryweaver.action_gate import ActionGate, ActionGateStatus, ActionProposal
from memoryweaver.contract import EnvironmentContract


def _gate() -> ActionGate:
    return ActionGate(EnvironmentContract.default_live_loop())


def test_action_gate_blocks_unknown_tool():
    decision = _gate().validate(ActionProposal(action_name="shell_exec", target="rm -rf /"))

    assert decision.allowed is False
    assert decision.status == ActionGateStatus.BLOCK
    assert "allowlisted" in decision.reasons[0]


def test_action_gate_requires_confirmation_for_high_risk_target():
    proposal = ActionProposal(
        action_name="tool_call",
        target="reset_auth_files",
        arguments={"target": "reset_auth_files"},
        idempotency_key="task:1:reset_auth_files",
    )

    first = _gate().validate(proposal)
    assert first.allowed is False
    assert first.status == ActionGateStatus.NEEDS_CONFIRMATION

    proposal.user_confirmation = True
    second = _gate().validate(proposal)
    assert second.allowed is True
    assert second.status == ActionGateStatus.ALLOW


def test_action_gate_requires_idempotency_for_side_effecting_tool_call():
    proposal = ActionProposal(
        action_name="tool_call",
        target="selected_organization",
        arguments={"target": "selected_organization"},
    )

    decision = _gate().validate(proposal)
    assert decision.allowed is False
    assert decision.status == ActionGateStatus.BLOCK
    assert "idempotency_key" in decision.reasons[0]


def test_action_gate_allows_low_risk_evidence_check():
    proposal = ActionProposal(
        action_name="check_evidence",
        target="selected_organization",
        arguments={"target": "selected_organization"},
    )

    decision = _gate().validate(proposal)
    assert decision.allowed is True
    assert decision.status == ActionGateStatus.ALLOW
    assert decision.risk == "low"


@pytest.mark.parametrize(
    "target",
    [
        "del build_artifact",
        "erase temp_file",
        "rmdir generated_dir",
        "Remove-Item .tmp -Recurse",
        "format disk",
        "iex downloaded_script",
        "chmod 777 secret",
        "chown user:group secret",
        "delete_file",
    ],
)
def test_action_gate_requires_confirmation_for_high_risk_command_tokens(target):
    proposal = ActionProposal(
        action_name="tool_call",
        target=target,
        arguments={"target": target},
        idempotency_key=f"task:1:{target}",
    )

    decision = _gate().validate(proposal)

    assert decision.allowed is False
    assert decision.status == ActionGateStatus.NEEDS_CONFIRMATION
    assert decision.risk == "high"


def test_action_gate_allows_workdir_inside_allowed_root(tmp_path):
    allowed_root = tmp_path / "workspace"
    nested = allowed_root / "nested"
    nested.mkdir(parents=True)
    contract = EnvironmentContract.default_live_loop()
    contract.allowed_workdirs = [str(allowed_root)]

    proposal = ActionProposal(
        action_name="check_evidence",
        target="selected_organization",
        arguments={"target": "selected_organization"},
        working_directory=str(nested),
    )

    decision = ActionGate(contract).validate(proposal)
    assert decision.allowed is True


def test_action_gate_rejects_workdir_with_only_matching_prefix(tmp_path):
    allowed_root = tmp_path / "workspace"
    sibling_with_prefix = tmp_path / "workspace_evil"
    allowed_root.mkdir()
    sibling_with_prefix.mkdir()
    contract = EnvironmentContract.default_live_loop()
    contract.allowed_workdirs = [str(allowed_root)]

    proposal = ActionProposal(
        action_name="check_evidence",
        target="selected_organization",
        arguments={"target": "selected_organization"},
        working_directory=str(sibling_with_prefix),
    )

    decision = ActionGate(contract).validate(proposal)
    assert decision.allowed is False
    assert decision.status == ActionGateStatus.BLOCK
    assert "working_directory" in decision.reasons[0]
