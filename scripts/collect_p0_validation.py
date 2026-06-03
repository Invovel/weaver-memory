"""Collect a reproducible P0 validation batch for MemoryWeaver.

The output keeps raw trial data alongside aggregate statistics so later
reports can be regenerated without rerunning the experiment.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmarks.prototype_baseline import benchmark_store, correctness_probes


def run(command: list[str]) -> dict[str, Any]:
    """Run a command from the repository root and retain its output."""
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def git_output(*args: str) -> str:
    """Return a best-effort Git value without making the batch fail."""
    result = run(["git", *args])
    if result["returncode"] != 0:
        return ""
    return result["stdout"].strip()


def aggregate_trials(trials: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate performance metrics across independent benchmark trials."""
    aggregates: list[dict[str, Any]] = []
    for item_index, item_result in enumerate(trials[0]["performance"]):
        aggregate: dict[str, Any] = {
            "items": item_result["items"],
            "json_bytes": item_result["json_bytes"],
            "metrics": {},
        }
        metric_paths = {
            "write_items_per_second": ("write", "items_per_second"),
            "reload_ms": ("reload_ms",),
            "find_by_tags_p95_ms": ("find_by_tags", "p95_ms"),
            "verified_search_by_tags_p95_ms": (
                "verified_search_by_tags",
                "p95_ms",
            ),
            "find_similar_p95_ms": ("find_similar", "p95_ms"),
            "verified_search_p95_ms": ("verified_search", "p95_ms"),
        }
        for metric_name, path in metric_paths.items():
            values: list[float] = []
            for trial in trials:
                value: Any = trial["performance"][item_index]
                for part in path:
                    value = value[part]
                values.append(float(value))
            aggregate["metrics"][metric_name] = {
                "mean": round(statistics.mean(values), 6),
                "stdev": round(statistics.stdev(values), 6)
                if len(values) > 1
                else 0.0,
                "min": round(min(values), 6),
                "max": round(max(values), 6),
                "samples": values,
            }
        aggregates.append(aggregate)
    return aggregates


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Where to write the JSON validation artifact.",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=5,
        help="Independent microbenchmark trials.",
    )
    parser.add_argument(
        "--items",
        nargs="+",
        type=int,
        default=[100, 500, 1000],
        help="Store sizes to benchmark.",
    )
    parser.add_argument(
        "--query-iterations",
        type=int,
        default=200,
        help="Iterations per query benchmark.",
    )
    args = parser.parse_args()

    pytest_result = run([sys.executable, "-m", "pytest", "-q"])
    trials: list[dict[str, Any]] = []
    for trial_index in range(args.trials):
        trials.append({
            "trial": trial_index + 1,
            "correctness_probes": correctness_probes(),
            "performance": [
                benchmark_store(item_count, args.query_iterations)
                for item_count in args.items
            ],
        })

    artifact = {
        "schema_version": "1.0",
        "experiment": "memoryweaver-sdk-v0.2.0-provisional-pattern-validation",
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python": platform.python_version(),
            "python_executable": sys.executable,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
            "git_head": git_output("rev-parse", "HEAD"),
            "git_status_short": git_output("status", "--short"),
        },
        "procedure": {
            "pytest": pytest_result["command"],
            "benchmark": {
                "trials": args.trials,
                "items": args.items,
                "query_iterations": args.query_iterations,
                "probes": [
                    "cli_import",
                    "source_gate",
                    "policy_gate",
                    "evidence_link",
                    "provisional_pattern",
                    "stable_pattern",
                    "chinese_lexical_recall",
                ],
            },
        },
        "pytest": pytest_result,
        "trials": trials,
        "aggregate": aggregate_trials(trials),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "output": str(args.output),
        "pytest_returncode": pytest_result["returncode"],
        "trials": args.trials,
        "items": args.items,
        "query_iterations": args.query_iterations,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
