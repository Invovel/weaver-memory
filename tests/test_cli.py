"""CLI smoke chain for the standalone workspace."""

import json

import pytest

from memoryweaver.cli import main


def invoke(capsys, *args):
    assert main(list(args)) == 0
    return json.loads(capsys.readouterr().out)


def invoke_status(capsys, expected_code, *args):
    assert main(list(args)) == expected_code
    stdout = capsys.readouterr().out
    return json.loads(stdout) if stdout.strip() else None


def test_help_and_version_are_available():
    with pytest.raises(SystemExit) as help_exit:
        main(["--help"])
    assert help_exit.value.code == 0
    with pytest.raises(SystemExit) as version_exit:
        main(["--version"])
    assert version_exit.value.code == 0


def test_complete_memory_evidence_pattern_route_chain(tmp_path, capsys):
    root = str(tmp_path / ".memoryweaver")
    first = invoke(
        capsys,
        "memory", "add", "--root", root,
        "--content", "Codex CLI subscription load failed in WSL",
        "--source", "terminal",
        "--evidence", "captured output",
    )
    second = invoke(
        capsys,
        "memory", "add", "--root", root,
        "--content", "Check organization auth before reinstall",
        "--source", "terminal",
        "--evidence", "captured output",
    )
    invoke(capsys, "memory", "promote", "--root", root, first["id"])
    invoke(capsys, "memory", "promote", "--root", root, second["id"])

    node = invoke(
        capsys,
        "evidence", "add", "--root", root,
        "--text", "organization auth check resolved subscription failure",
        "--source", "terminal",
        "--uri", "term://run-1",
    )
    link = invoke(
        capsys,
        "evidence", "link", "--root", root,
        "--evidence-id", node["id"],
        "--memory-id", first["id"],
    )
    pattern = invoke(
        capsys,
        "pattern", "compose", "--root", root,
        "--memory-id", first["id"],
        "--memory-id", second["id"],
        "--evidence-link-id", link["id"],
        "--rule", "Codex CLI subscription load failed in WSL check organization auth",
        "--applies-when", "subscription fails after install",
        "--avoid-when", "reinstall first",
    )
    assert pattern["status"] == "provisional"

    for task_run in ("run-1", "run-2", "run-2"):
        invoke(
            capsys,
            "pattern", "validate", "--root", root,
            pattern["id"], "--task-run-id", task_run, "--success",
        )
    invoke(capsys, "pattern", "promote-stable", "--root", root, pattern["id"])

    route = invoke(
        capsys,
        "route", "--root", root,
        "--query", "Codex CLI subscription load failed in WSL check organization auth",
    )
    assert route["mode"] == "fast"
    assert pattern["id"] in route["matched_patterns"]
    assert invoke(capsys, "validate", "--root", root, "--json")["valid"] is True


def test_doctor_smoke(tmp_path, capsys):
    """mw doctor exits clean on an empty workspace."""
    root = str(tmp_path / ".memoryweaver")
    report = invoke(capsys, "doctor", "--root", root, "--json")
    assert report["valid"] is True
    assert "info" in report


def test_doctor_with_stale_pending(tmp_path, capsys):
    """mw doctor warns when pending proposals exceed their deadline."""
    from memoryweaver.graph_schema import GraphProposal, GraphRelation
    from memoryweaver.store import MemoryWorkspace

    root = str(tmp_path / ".memoryweaver")
    workspace = MemoryWorkspace(root)
    proposal = GraphProposal(
        proposal_type="link_tags",
        source="llm",
        relation=GraphRelation.RELATED_TO,
        from_tag="codex_subscription_failed",
        to_tag="selected_organization",
        status="pending",
        metadata={
            "pending_lifecycle": {
                "created_batch": 0,
                "review_deadline_batch": 1,
                "stale_after_batch": 3,
            },
            "current_batch": 4,
        },
    )
    workspace.graph.add_proposal(proposal)
    report = invoke(capsys, "doctor", "--root", root, "--json")
    assert any("stale pending proposal" in item for item in report["warnings"])


def test_context_cli_smoke_chain(tmp_path, capsys):
    root = str(tmp_path / ".memoryweaver")
    added = invoke(
        capsys,
        "context", "add", "--root", root,
        "--type", "terminal_log",
        "--source", "terminal",
        "--text", "$ codex status\nstderr: SUBSCRIPTION_LOAD_FAILED\nexit=1",
        "--timestamp", "2026-06-05T10:00:00Z",
        "--metadata-json", '{"command":"codex status","exit_code":1}',
    )
    capsule = added["capsule"]
    raw_span = added["raw_span"]
    assert capsule["raw_ref_id"] == raw_span["id"]
    assert capsule["source"] == "terminal"
    assert "subscription" in capsule["tags"]

    results = invoke(
        capsys,
        "context", "search", "--root", root,
        "--tag", "subscription",
        "--since", "2026-06-05T00:00:00Z",
        "--until", "2026-06-06T00:00:00Z",
    )
    assert [item["id"] for item in results] == [capsule["id"]]

    recovered = invoke(
        capsys,
        "context", "raw", "--root", root,
        raw_span["id"],
    )
    assert recovered["content"] == raw_span["content"]

    report = invoke(capsys, "context", "validate", "--root", root, "--json")
    assert report == {
        "valid": True,
        "raw_span_count": 1,
        "capsule_count": 1,
        "errors": [],
    }

    from memoryweaver.store import MemoryWorkspace

    assert MemoryWorkspace(root).memories.count() == 0


def test_graph_propose_review_eval_cli_chain(tmp_path, capsys):
    root = str(tmp_path / ".memoryweaver")
    input_path = tmp_path / "batch.jsonl"
    proposals_path = tmp_path / "proposals.jsonl"
    reviewed_path = tmp_path / "reviewed.jsonl"
    gold_path = tmp_path / "gold.jsonl"
    metrics_path = tmp_path / "metrics.json"

    invoke(
        capsys,
        "evidence", "add", "--root", root,
        "--text", "selected organization fixed codex subscription failed",
        "--source", "terminal",
        "--uri", "fixture://org",
    )
    input_path.write_text(
        json.dumps({
            "id": "q1",
            "query": "codex org problem",
            "tags": ["codex_subscription_failed", "selected_organization"],
        }) + "\n",
        encoding="utf-8",
    )
    gold_path.write_text(
        json.dumps({
            "from_tag": "codex_subscription_failed",
            "to_tag": "selected_organization",
            "relation": "related_to",
        }) + "\n",
        encoding="utf-8",
    )

    proposed = invoke(
        capsys,
        "graph", "propose", "--root", root,
        "--provider", "local",
        "--input", str(input_path),
        "--output", str(proposals_path),
    )
    assert proposed["proposal_count"] == 1
    reviewed = invoke(
        capsys,
        "graph", "review", "--root", root,
        "--input", str(proposals_path),
        "--output", str(reviewed_path),
        "--query", "codex org problem",
    )
    assert reviewed["reviewed_count"] == 1
    metrics = invoke(
        capsys,
        "graph", "eval", "--root", root,
        "--gold", str(gold_path),
        "--pred", str(reviewed_path),
        "--output", str(metrics_path),
    )
    assert metrics["proposal_count"] == 1
    assert metrics["matched_count"] == 1
    assert metrics_path.exists()


def test_contract_action_and_trajectory_cli_chain(tmp_path, capsys):
    contract = invoke(
        capsys,
        "contract", "show", "--root", str(tmp_path / ".memoryweaver"),
        "--json",
        "--max-steps", "6",
        "--max-tool-calls", "2",
    )
    assert contract["resource_budget"]["steps"] == 6
    assert contract["tool_contracts"]["tool_call"]["idempotency_required"] is True

    blocked = invoke_status(
        capsys,
        1,
        "action", "validate", "--root", str(tmp_path / ".memoryweaver"),
        "--json",
        "--name", "tool_call",
        "--target", "reset_auth_files",
    )
    assert blocked["decision"]["status"] == "needs_confirmation"
    assert blocked["decision"]["allowed"] is False

    allowed = invoke(
        capsys,
        "action", "validate", "--root", str(tmp_path / ".memoryweaver"),
        "--json",
        "--name", "tool_call",
        "--target", "reset_auth_files",
        "--idempotency-key", "task:1:tool_call:reset_auth_files",
        "--confirm",
    )
    assert allowed["decision"]["status"] == "allow"
    assert allowed["decision"]["allowed"] is True

    events = json.dumps(
        [
            {
                "step": 1,
                "action_name": "tool_call",
                "target": "reinstall_npm",
                "result": {"status": "failed_known_bad", "signal": "negative"},
                "gate_status": "allow",
            },
            {
                "step": 2,
                "action_name": "tool_call",
                "target": "reinstall_npm",
                "result": {"status": "failed_known_bad", "signal": "negative"},
                "gate_status": "allow",
            },
        ]
    )
    trajectory = invoke(
        capsys,
        "trajectory", "evaluate", "--root", str(tmp_path / ".memoryweaver"),
        "--json",
        "--events-json", events,
    )
    assert trajectory["final_decision"]["status"] == "recover"
    assert trajectory["final_decision"]["repeated_failure"] is True


def test_skill_and_harness_cli_chain(tmp_path, capsys):
    root = str(tmp_path / ".memoryweaver")
    first = invoke(
        capsys,
        "memory", "add", "--root", root,
        "--content", "Check organization and entitlement before reinstalling npm",
        "--source", "terminal",
        "--tag", "codex",
        "--tag", "subscription",
        "--evidence", "terminal trace",
    )
    second = invoke(
        capsys,
        "memory", "add", "--root", root,
        "--content", "Blind npm reinstall did not resolve subscription failures",
        "--source", "tool",
        "--tag", "codex",
        "--tag", "subscription",
        "--tag", "reinstall",
        "--evidence", "tool trace",
    )
    invoke(capsys, "memory", "promote", "--root", root, first["id"])
    invoke(capsys, "memory", "promote", "--root", root, second["id"])

    node = invoke(
        capsys,
        "evidence", "add", "--root", root,
        "--text", "selected organization resolved the failure",
        "--source", "terminal",
        "--uri", "fixture://org",
    )
    link = invoke(
        capsys,
        "evidence", "link", "--root", root,
        "--evidence-id", node["id"],
        "--memory-id", first["id"],
    )
    pattern = invoke(
        capsys,
        "pattern", "compose", "--root", root,
        "--memory-id", first["id"],
        "--memory-id", second["id"],
        "--evidence-link-id", link["id"],
        "--rule", "For Codex subscription failures, check organization before reinstalling npm",
        "--applies-when", "subscription load failed",
        "--failed-path", "reinstall npm first",
    )
    for task_run in ("run-1", "run-2", "run-2"):
        invoke(
            capsys,
            "pattern", "validate", "--root", root,
            pattern["id"], "--task-run-id", task_run, "--success",
        )
    invoke(capsys, "pattern", "promote-stable", "--root", root, pattern["id"])

    skill = invoke(
        capsys,
        "skill", "retrieve", "--root", root,
        "--json",
        "--query", "Codex subscription failed should I reinstall npm first",
    )
    assert skill["skills"]
    assert skill["avoidance_memories"]
    assert skill["recommended_mode"] in {"fast", "fast_verify"}

    trace = invoke(
        capsys,
        "harness", "trace", "--root", root,
        "--json",
        "--query", "Codex subscription load failed after install",
        "--tag", "codex",
        "--tag", "subscription",
        "--action-name", "check_evidence",
        "--action-target", "selected_organization",
        "--result-json", '{"status":"evidence_observed","signal":"positive","evidence":"selected organization resolved the failure"}',
    )
    assert trace["task_conditioning"]["skill_result"]["skills"]
    assert trace["before_execution"]["decision"]["allowed"] is True
    assert trace["after_task_outcome"]["verified_write_count"] == 1


def test_pattern_trial_and_best_path_cli_chain(tmp_path, capsys):
    root = str(tmp_path / ".memoryweaver")
    first = invoke(
        capsys,
        "memory", "add", "--root", root,
        "--content", "Check organization and entitlement before reinstalling npm",
        "--source", "terminal",
        "--evidence", "terminal trace",
    )
    second = invoke(
        capsys,
        "memory", "add", "--root", root,
        "--content", "Blind npm reinstall did not resolve subscription failures",
        "--source", "tool",
        "--evidence", "tool trace",
    )
    invoke(capsys, "memory", "promote", "--root", root, first["id"])
    invoke(capsys, "memory", "promote", "--root", root, second["id"])
    node = invoke(
        capsys,
        "evidence", "add", "--root", root,
        "--text", "selected organization resolved the failure",
        "--source", "terminal",
        "--uri", "fixture://org",
    )
    link = invoke(
        capsys,
        "evidence", "link", "--root", root,
        "--evidence-id", node["id"],
        "--memory-id", first["id"],
    )
    pattern = invoke(
        capsys,
        "pattern", "compose", "--root", root,
        "--memory-id", first["id"],
        "--memory-id", second["id"],
        "--evidence-link-id", link["id"],
        "--rule", "Check organization before reinstalling npm for Codex subscription failures",
        "--applies-when", "subscription load failed",
        "--failed-path", "reinstall npm first",
    )
    for task_run in ("run-1", "run-2", "run-3"):
        trial = invoke(
            capsys,
            "pattern", "trial", "--root", root,
            pattern["id"],
            "--task-run-id", task_run,
            "--success",
            "--steps-saved", "2",
            "--known-bad-avoided", "1",
            "--evidence-first",
        )
    assert trial["path_fitness_score"] >= 0.55

    stable = invoke(capsys, "pattern", "promote-stable", "--root", root, pattern["id"])
    assert stable["status"] == "stable"

    ranked = invoke(
        capsys,
        "pattern", "best-path", "--root", root,
        "--json",
        "--query", "Codex subscription failed should I reinstall npm first",
    )
    assert ranked
    assert ranked[0]["id"] == pattern["id"]
    assert ranked[0]["path_fitness_score"] >= 0.55


def test_eval_path_promotion_cli(tmp_path, capsys):
    root = str(tmp_path / ".memoryweaver")
    output = tmp_path / "path-promotion"
    result = invoke(
        capsys,
        "eval", "path-promotion", "--root", root,
        "--json",
        "--output", str(output),
    )
    assert result["passed"] is True
    assert result["metrics"]["latest_path_selection_accuracy"] == 1.0
    assert (output / "raw_results.json").exists()


def test_eval_path_promotion_lme_v2_cli(tmp_path, capsys):
    root = tmp_path / "longmemeval-v2"
    (root / "haystacks").mkdir(parents=True)
    root.joinpath("questions.jsonl").write_text(
        json.dumps(
            {
                "id": "q001",
                "domain": "enterprise",
                "environment": "workarena",
                "question_type": "workflow-knowledge",
                "question": "Which evidence should be checked before closing?",
                "answer": "activity stream",
                "eval_function": "exact",
            }
        ) + "\n",
        encoding="utf-8",
    )
    root.joinpath("trajectories.jsonl").write_text(
        json.dumps(
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
        ) + "\n",
        encoding="utf-8",
    )
    (root / "haystacks" / "lme_v2_small.json").write_text(
        json.dumps({"q001": ["t001"]}),
        encoding="utf-8",
    )
    output = tmp_path / "path-promotion-lme-v2"
    result = invoke(
        capsys,
        "eval", "path-promotion-lme-v2", "--root", str(tmp_path / ".memoryweaver"),
        "--json",
        "--input-root", str(root),
        "--question-limit", "1",
        "--trajectories-per-question", "1",
        "--states-per-trajectory", "1",
        "--output", str(output),
    )
    assert result["passed"] is True
    assert result["metrics"]["real_snapshot_family_count"] == 1
    assert (output / "raw_results.json").exists()
