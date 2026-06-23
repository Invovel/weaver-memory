import json

from memoryweaver.cli import main
from memoryweaver.integrations import MemoryWeaverModule
from memoryweaver.lifecycle import MemoryLifecycle
from memoryweaver.runtime import (
    MemoryWeaverLiveLoop,
    MockTauEnv,
    OpenAICompatibleAgent,
    RuleAgent,
)
from memoryweaver.schema import Layer
from memoryweaver.store import MemoryWorkspace


def _invoke(capsys, *args):
    assert main(list(args)) == 0
    return json.loads(capsys.readouterr().out)


def _write_jsonl(path, records):
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def _make_lme_v2_fixture(tmp_path):
    root = tmp_path / "longmemeval-v2"
    (root / "haystacks").mkdir(parents=True)
    _write_jsonl(
        root / "questions.jsonl",
        [
            {
                "id": "q001",
                "domain": "enterprise",
                "environment": "workarena",
                "question_type": "workflow-knowledge",
                "question": "Which evidence should be checked before closing?",
                "answer": "activity stream",
                "eval_function": "exact",
            }
        ],
    )
    _write_jsonl(
        root / "trajectories.jsonl",
        [
            {
                "id": "t001",
                "domain": "enterprise",
                "environment": "workarena",
                "goal": "Close the incident after checking the activity stream.",
                "outcome": "success",
                "start_url": "https://example.test",
                "states": [
                    {
                        "state_index": 0,
                        "step": 0,
                        "url": "https://example.test/incident",
                        "action": "click('Activity')",
                        "thought": "Inspect evidence before updating state.",
                        "accessibility_tree": "RootWebArea Incident Activity Stream",
                        "screenshot": "screenshots/t001/0.png",
                    }
                ],
            }
        ],
    )
    (root / "haystacks" / "lme_v2_small.json").write_text(
        json.dumps({"q001": ["t001"]}),
        encoding="utf-8",
    )
    return root


def test_memory_lifecycle_smoke_exercises_layer_gbrain_and_marker(tmp_path):
    workspace = MemoryWorkspace(tmp_path / ".memoryweaver")
    result = MemoryLifecycle(workspace).run_codex_subscription_smoke()

    assert result["passed"] is True
    assert result["metrics"]["verified_memory_write_count"] == 2
    assert result["metrics"]["promotion_count"] == 2
    assert result["metrics"]["layer3_mutation_count"] == 1
    assert result["metrics"]["runtime_marker_write_count"] == 1
    assert result["metrics"]["mind_map_node_count"] > 0
    assert all(item.layer == Layer.ACTIVATED for item in workspace.memories.list_all())
    assert workspace.marker_evidence_contexts.get("marker_codex_subscription_org_first") is not None
    assert any(node["layer"] == "layer_3" for node in result["mind_map"]["nodes"])


def test_lmev2_module_writes_context_without_verified_memory(tmp_path):
    root = _make_lme_v2_fixture(tmp_path)
    workspace = MemoryWorkspace(tmp_path / ".memoryweaver")
    module = MemoryWeaverModule(workspace)

    context = module.build_context_from_local_snapshot(
        root,
        question_index=0,
        trajectories_per_question=1,
        states_per_trajectory=1,
    )

    assert context.metrics["raw_span_count"] > 0
    assert context.metrics["capsule_count"] > 0
    assert context.metrics["verified_memory_write_count"] == 0
    assert context.metrics["promotion_count"] == 0
    assert workspace.memories.count() == 0
    assert len(workspace.raw_spans.list_all()) == context.metrics["raw_span_count"]
    assert len(workspace.context_capsules.list_all()) == context.metrics["capsule_count"]


def test_tau_style_live_loop_writes_memory_from_observations(tmp_path):
    workspace = MemoryWorkspace(tmp_path / ".memoryweaver")
    result = MemoryWeaverLiveLoop(workspace).run(
        task_id="tau_smoke",
        env=MockTauEnv(),
        agent=RuleAgent(),
        max_steps=4,
    )

    assert result.success is True
    assert result.verified_memory_write_count > 0
    assert result.promotion_count == result.verified_memory_write_count
    assert result.blocked_action_count == 0
    assert result.recovery_count == 0
    assert workspace.memories.count() == result.verified_memory_write_count


def test_tau_style_llm_loop_counts_llm_and_writes_memory(tmp_path, monkeypatch):
    workspace = MemoryWorkspace(tmp_path / ".memoryweaver")
    agent = OpenAICompatibleAgent(
        api_key="test-key",
        model="deepseek-chat",
        base_url="https://example.test/chat/completions",
        provider="deepseek",
    )

    def fake_post(system_prompt, user_message):
        agent.online_llm_call_count += 1
        return json.dumps(
            {
                "name": "check_evidence",
                "target": "selected_organization_and_entitlement",
                "reasoning": "mock LLM follows marker evidence.",
            }
        )

    monkeypatch.setattr(agent, "_post", fake_post)
    result = MemoryWeaverLiveLoop(workspace).run(
        task_id="tau_llm_smoke",
        env=MockTauEnv(),
        agent=agent,
        max_steps=4,
    )

    assert result.success is True
    assert result.online_llm_call_count == 1
    assert result.verified_memory_write_count == 1
    assert result.blocked_action_count == 0
    assert workspace.memories.count() == 1


def test_v0_7_cli_core_entries(tmp_path, capsys):
    root = str(tmp_path / ".memoryweaver")
    layer_result = _invoke(capsys, "layer", "smoke", "--root", root, "--json")
    assert layer_result["passed"] is True

    sync = _invoke(capsys, "gbrain", "sync", "--root", root, "--json")
    assert sync["graph_node_count"] > 0

    mindmap = _invoke(
        capsys,
        "gbrain", "mindmap", "--root", root, "--json",
        "--tag", "codex",
    )
    assert mindmap["nodes"]
    assert mindmap["core_node_ids"]

    root2 = str(tmp_path / ".memoryweaver-tau")
    tau = _invoke(capsys, "eval", "tau-smoke", "--root", root2, "--json")
    assert tau["success"] is True
    assert tau["verified_memory_write_count"] > 0
    assert "blocked_action_count" in tau

    manifest_path = tmp_path / "external.lock.json"
    manifest = _invoke(
        capsys,
        "external", "manifest", "--root", root,
        "--path", str(tmp_path),
        "--out", str(manifest_path),
        "--json",
    )
    assert manifest["entry_count"] == 1
    assert manifest_path.exists()
