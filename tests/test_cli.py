"""CLI smoke chain for the standalone workspace."""

import json

import pytest

from memoryweaver.cli import main


def invoke(capsys, *args):
    assert main(list(args)) == 0
    return json.loads(capsys.readouterr().out)


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
