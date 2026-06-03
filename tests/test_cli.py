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
