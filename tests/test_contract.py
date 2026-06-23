from memoryweaver.contract import EnvironmentContract
from memoryweaver.schema import Source


def test_default_live_loop_contract_exposes_tools_and_source_authority():
    contract = EnvironmentContract.default_live_loop(max_steps=6, max_tool_calls=2)

    assert contract.tool("tool_call") is not None
    assert contract.tool("tool_call").idempotency_required is True
    assert contract.tool("check_evidence").required_args == ["target"]
    assert contract.resource_budget["steps"] == 6
    assert contract.resource_budget["tool_calls"] == 2

    assistant = contract.authority_for(Source.ASSISTANT)
    terminal = contract.authority_for(Source.TERMINAL)
    assert assistant is not None and assistant.may_become_verified is False
    assert terminal is not None and terminal.may_become_verified is True


def test_environment_contract_roundtrip_preserves_tool_contracts():
    contract = EnvironmentContract.default_live_loop()
    restored = EnvironmentContract.from_dict(contract.to_dict())

    assert restored.contract_id == contract.contract_id
    assert restored.tool("resolve").side_effect_level == "none"
    assert restored.authority_for(Source.SYNTHETIC).may_drive_runtime_context is False
