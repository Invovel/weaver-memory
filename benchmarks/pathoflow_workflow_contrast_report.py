"""Build a final contrast report for theoretical vs executable PathoFlow workflows."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VALIDATION_ROOT = REPO_ROOT / "docs" / "validation"
DEFAULT_OFFLINE_DIR = DEFAULT_VALIDATION_ROOT / "pathoflow-core-dataset-offline-eval-2026-06-14"
DEFAULT_TOOL_DIR = DEFAULT_VALIDATION_ROOT / "pathoflow-tool-native-workflow-compare-2026-06-14"


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def classify_breakpoints(chain_matrix: dict[str, Any], sequential_chains: dict[str, Any]) -> dict[str, Any]:
    categories = Counter()
    examples: list[dict[str, Any]] = []

    for scenario in chain_matrix.get("scenarios", []):
        case_id = str(scenario.get("case_id") or "")
        if scenario.get("preflight_ready") is False:
            categories["preflight_contract_mismatch"] += 1
            examples.append({"case_id": case_id, "category": "preflight_contract_mismatch", "detail": scenario.get("preflight_reasons", [])})
        elif scenario.get("execution_status") == "completed" and int(scenario.get("output_file_count") or 0) == 0:
            categories["completed_no_output"] += 1
            examples.append({"case_id": case_id, "category": "completed_no_output", "detail": "execution completed but wrote zero output files"})
        elif scenario.get("status") == "blocked_by_empty_upstream_output":
            categories["empty_upstream_output"] += 1
            examples.append({"case_id": case_id, "category": "empty_upstream_output", "detail": "upstream tool returned success with zero files"})

    for chain in sequential_chains.get("chains", []):
        chain_id = str(chain.get("chain_id") or "")
        result = chain.get("result", {})
        if int(result.get("failure_count") or 0) > 0:
            categories["sequential_chain_failure"] += 1
            examples.append({"case_id": chain_id, "category": "sequential_chain_failure", "detail": result})

    return {
        "counts": dict(categories),
        "examples": examples[:20],
    }


def build_readme(
    *,
    offline_workflow: dict[str, Any],
    tool_workflow: dict[str, Any],
    tool_compare: dict[str, Any],
    breakpoint_summary: dict[str, Any],
) -> str:
    top_theoretical = offline_workflow.get("top_exact_toolchains", [])[:5]
    actual_steps = tool_workflow.get("steps", [])
    breakpoint_counts = breakpoint_summary.get("counts", {})
    lines = [
        "# PathoFlow Workflow Contrast Report",
        "",
        "This report contrasts the theoretical workflow recovered from the offline",
        "PathoFlow replay package with the currently executable no-LLM workflow",
        "evidence from the tool-native package.",
        "",
        "## Theoretical Workflow",
        "",
        "Theoretical workflow is derived from the offline baseline's dominant exact",
        "`expected_toolchain` patterns.",
        "",
        "```mermaid",
        offline_workflow.get("mermaid", ""),
        "```",
        "",
    ]
    for row in top_theoretical:
        lines.append(f"- {row['count']}: {' -> '.join(row['toolchain'])}")
    lines.extend(
        [
            "",
            "## Actually Executable Workflow",
            "",
            "Executable workflow is limited to no-LLM demo / cpu_pseudo tools that",
            "currently return real manifests and files.",
            "",
            "```mermaid",
            tool_workflow.get("mermaid", ""),
            "```",
            "",
        ]
    )
    for step in actual_steps:
        lines.append(f"- {step['label']}: status={step['status']}, outputs={', '.join(step['outputs'])}")
    lines.extend(
        [
            "",
            "## Main Gaps",
            "",
            f"- Previous offline replay runtime any-hit rate: {tool_compare.get('previous_runtime_any_hit_rate')}",
            f"- Previous offline replay canonical any-hit rate: {tool_compare.get('previous_canonical_any_hit_rate')}",
            f"- Planner primary drift counts: {tool_compare.get('planner_primary_flow_counts')}",
            f"- Executed zero-output cases: {tool_compare.get('execution_cases_with_no_output_files')}",
            "",
            "## Breakpoint Summary",
            "",
        ]
    )
    for key, value in breakpoint_summary.get("counts", {}).items():
        lines.append(f"- {key}: {value}")

    interpretation_lines = [
        "- Theoretical PathoFlow workflow is much richer than the currently executable workflow.",
    ]
    if not breakpoint_counts:
        interpretation_lines.append(
            "- No concrete executable breakpoint remains in the currently covered benchmark cases; the main remaining limitation is workflow coverage rather than a reproduced contract failure."
        )
    else:
        if breakpoint_counts.get("preflight_contract_mismatch"):
            interpretation_lines.append(
                "- Some benchmarked chains still show real preflight contract mismatch between upstream and downstream tools."
            )
        if breakpoint_counts.get("completed_no_output"):
            interpretation_lines.append(
                "- Some benchmarked chains still complete while writing zero output files."
            )
        if breakpoint_counts.get("empty_upstream_output"):
            interpretation_lines.append(
                "- Some downstream chains are still blocked because an upstream step returns success with zero files."
            )
        if breakpoint_counts.get("sequential_chain_failure"):
            interpretation_lines.append(
                "- Some sequential benchmark chains still fail and should be checked against harness input construction before they are treated as product breakpoints."
            )
    interpretation_lines.append(
        "- The repository can execute some real no-LLM tool fragments, but it still cannot turn the richer recovered theoretical workflow into a broad stable multi-step closed loop."
    )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            *interpretation_lines,
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a contrast report for PathoFlow theoretical vs executable workflows.")
    parser.add_argument("--offline-dir", default=str(DEFAULT_OFFLINE_DIR))
    parser.add_argument("--tool-dir", default=str(DEFAULT_TOOL_DIR))
    args = parser.parse_args()

    offline_dir = Path(args.offline_dir)
    tool_dir = Path(args.tool_dir)

    offline_workflow = load_json(offline_dir / "workflow_graph.json")
    tool_workflow = load_json(tool_dir / "executable_workflow_graph.json")
    tool_compare = load_json(tool_dir / "comparison.json")
    chain_matrix = load_json(tool_dir / "chain_matrix.json")
    sequential_chains = load_json(tool_dir / "sequential_chains.json")

    breakpoint_summary = classify_breakpoints(chain_matrix, sequential_chains)
    readme = build_readme(
        offline_workflow=offline_workflow,
        tool_workflow=tool_workflow,
        tool_compare=tool_compare,
        breakpoint_summary=breakpoint_summary,
    )

    report = {
        "generated_at": datetime.now().isoformat(),
        "offline_workflow": offline_workflow,
        "tool_workflow": tool_workflow,
        "tool_compare": tool_compare,
        "breakpoint_summary": breakpoint_summary,
    }
    write_json(tool_dir / "workflow_contrast_report.json", report)
    (tool_dir / "workflow_contrast_report.md").write_text(readme, encoding="utf-8")

    print(f"[pathoflow-workflow-contrast] wrote report to {tool_dir}")


if __name__ == "__main__":
    main()
