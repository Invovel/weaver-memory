"""Run a reproducible current-stage check and tidy transient root workspaces.

This script keeps a fixed daily workflow in one place:

1. Optionally archive transient root-level workspaces.
2. Run the current regression and smoke checks.
3. Compare README benchmark claims with today's measured baseline.
4. Summarize today's TODO, the current implementation stage, and suggestions.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "docs" / "validation" / "current-stage-check"
TRANSIENT_PREFIXES = (".memoryweaver-", ".tmp-")
README_BENCHMARK_HEADERS = (
    "| Memory items | JSON size | Write throughput | Verified text search p95 |",
    "| Memory items | JSON 大小 | 写入吞吐 | Verified text search p95 |",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def run_command(command: list[str], *, timeout: int) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        elapsed = time.perf_counter() - started
        return {
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "timed_out": False,
            "duration_seconds": round(elapsed, 3),
        }
    except subprocess.TimeoutExpired as exc:
        elapsed = time.perf_counter() - started
        return {
            "command": command,
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "timed_out": True,
            "duration_seconds": round(elapsed, 3),
        }


def parse_json_output(result: dict[str, Any]) -> dict[str, Any] | None:
    stdout = str(result.get("stdout", "")).strip()
    if not stdout:
        return None
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return None


def parse_pytest_summary(output: str) -> dict[str, Any]:
    summary_line = ""
    for line in reversed(output.splitlines()):
        stripped = line.strip()
        if any(token in stripped for token in (" passed", " failed", " skipped", " xfailed", " xpassed")):
            summary_line = stripped
            break
    counts: dict[str, int] = {
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "xfailed": 0,
        "xpassed": 0,
        "errors": 0,
    }
    if summary_line:
        for number, label in re.findall(
            r"(\d+)\s+(passed|failed|skipped|xfailed|xpassed|error|errors)",
            summary_line,
        ):
            key = "errors" if label.startswith("error") else label
            counts[key] = int(number)
    counts["total"] = sum(counts.values())
    counts["summary_line"] = summary_line
    counts["ok"] = counts["failed"] == 0 and counts["errors"] == 0 and bool(summary_line)
    return counts


def extract_readme_benchmark_rows(readme_text: str) -> dict[int, dict[str, float]]:
    lines = readme_text.splitlines()
    header_index = -1
    for index, line in enumerate(lines):
        if line.strip() in README_BENCHMARK_HEADERS:
            header_index = index
            break
    if header_index < 0:
        return {}
    rows: dict[int, dict[str, float]] = {}
    for line in lines[header_index + 2 :]:
        stripped = line.strip()
        if not stripped.startswith("|"):
            break
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) != 4:
            continue
        items_text = cells[0].replace(",", "")
        if not items_text.isdigit():
            continue
        rows[int(items_text)] = {
            "json_size_kb": float(cells[1].replace("KB", "").strip()),
            "write_items_per_second": float(cells[2].replace("items/s", "").strip()),
            "verified_search_p95_ms": float(cells[3].replace("ms", "").strip()),
        }
    return rows


def compare_readme_benchmark_claims(
    readme_text: str,
    baseline_result: dict[str, Any],
    *,
    source_name: str,
) -> list[dict[str, Any]]:
    claimed_rows = extract_readme_benchmark_rows(readme_text)
    differences: list[dict[str, Any]] = []
    performance = baseline_result.get("performance", [])
    for row in performance:
        item_count = int(row["items"])
        claimed = claimed_rows.get(item_count)
        if claimed is None:
            differences.append(
                {
                    "source": source_name,
                    "items": item_count,
                    "field": "missing_row",
                    "claimed": None,
                    "actual": {
                        "json_size_kb": round(row["json_bytes"] / 1024, 1),
                        "write_items_per_second": row["write"]["items_per_second"],
                        "verified_search_p95_ms": row["verified_search"]["p95_ms"],
                    },
                }
            )
            continue
        actual = {
            "json_size_kb": round(row["json_bytes"] / 1024, 1),
            "write_items_per_second": round(float(row["write"]["items_per_second"]), 2),
            "verified_search_p95_ms": round(float(row["verified_search"]["p95_ms"]), 2),
        }
        tolerances = {
            "json_size_kb": 0.5,
            "write_items_per_second": 0.01,
            "verified_search_p95_ms": 0.01,
        }
        for field, actual_value in actual.items():
            claimed_value = round(float(claimed[field]), 2)
            if abs(actual_value - claimed_value) > tolerances[field]:
                differences.append(
                    {
                        "source": source_name,
                        "items": item_count,
                        "field": field,
                        "claimed": claimed_value,
                        "actual": actual_value,
                    }
                )
    return differences


def find_transient_root_entries(root: Path) -> list[Path]:
    found: list[Path] = []
    for entry in sorted(root.iterdir(), key=lambda item: item.name.lower()):
        if not entry.is_dir():
            continue
        if any(entry.name.startswith(prefix) for prefix in TRANSIENT_PREFIXES):
            found.append(entry)
    return found


def archive_transient_root_entries(root: Path, archive_root: Path) -> dict[str, Any]:
    candidates = find_transient_root_entries(root)
    if not candidates:
        return {"archive_dir": "", "moved": []}
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = archive_root / f"root-archive-{stamp}"
    destination.mkdir(parents=True, exist_ok=True)
    moved: list[str] = []
    for candidate in candidates:
        target = destination / candidate.name
        shutil.move(str(candidate), str(target))
        moved.append(candidate.name)
    return {"archive_dir": str(destination.relative_to(root)), "moved": moved}


def collect_today_todo() -> list[dict[str, str]]:
    return [
        {
            "title": "保持全量回归门禁为绿色",
            "source": "docs/risk_assessment_and_benchmark.md",
            "detail": "P0 信任边界已闭合，当前优先级是持续保持 regression gate，而不是重新打开边界面。",
        },
        {
            "title": "继续收口 v0.7 的 path-promotion 主线",
            "source": "docs/development_plan.md",
            "detail": "主叙事应继续集中在 path promotion、path competition、stale replacement、rollback、sibling-task reuse。",
        },
        {
            "title": "保持 v0.8 integrated substrate artifact 可复现",
            "source": "docs/development_plan.md",
            "detail": "v0.8 已完成 RAG evidence、GBrain candidate graph、specialist EvidencePacket 与 checkpoint/resume 搭建，当前重点是保持 pass^3 artifact 和 claim mapping 一致。",
        },
        {
            "title": "进入 v0.9 优化阶段",
            "source": "docs/development_plan.md",
            "detail": "0.9 不再负责基础搭建，重点转向外部 benchmark、压力/雪崩测试、provider fallback、向量库/HNSW 与多跳图谱优化。",
        },
    ]


def collect_doc_differences(pytest_summary: dict[str, Any]) -> list[dict[str, Any]]:
    differences: list[dict[str, Any]] = []
    plan_text = _read_text(ROOT / "docs" / "development_plan.md")
    match = re.search(r"当前全量 `pytest` 为 (\d+) passing tests。", plan_text)
    if match:
        claimed = int(match.group(1))
        actual = int(pytest_summary.get("passed", 0))
        failed = int(pytest_summary.get("failed", 0))
        if claimed != actual or failed > 0:
            differences.append(
                {
                    "source": "docs/development_plan.md",
                    "field": "pytest_count_claim",
                    "claimed": claimed,
                    "actual_passed": actual,
                    "actual_failed": failed,
                    "summary_line": pytest_summary.get("summary_line", ""),
                }
            )
    return differences


def derive_current_stage(
    *,
    pytest_summary: dict[str, Any],
    layer_smoke: dict[str, Any] | None,
    tau_smoke: dict[str, Any] | None,
    path_metrics: dict[str, Any] | None,
    lme_metrics: dict[str, Any] | None,
    e2e_metrics: dict[str, Any] | None,
    e2e_reliability: dict[str, Any] | None,
    v08_metrics: dict[str, Any] | None,
    v08_reliability: dict[str, Any] | None,
) -> dict[str, Any]:
    layer_ok = bool(layer_smoke and layer_smoke.get("passed"))
    tau_ok = bool(tau_smoke and tau_smoke.get("success"))
    path_ok = bool(path_metrics and path_metrics.get("stable_promotion_rate") == 1.0)
    lme_ok = bool(lme_metrics and lme_metrics.get("latest_path_selection_accuracy") == 1.0)
    e2e_ok = bool(
        e2e_metrics
        and e2e_reliability
        and e2e_metrics.get("aggregate", {}).get("tests_passed") == 1.0
        and e2e_metrics.get("aggregate", {}).get("file_diff_matches_expected") == 1.0
        and e2e_metrics.get("aggregate", {}).get("memory_induced_regression_rate") == 0
        and e2e_metrics.get("arms", {}).get("mw_layer3_path", {}).get("average_path_regret") == 0
        and e2e_reliability.get("pass_power_3") is True
        and e2e_reliability.get("tests_passed_pass_power_3") is True
        and e2e_reliability.get("diff_matches_expected_pass_power_3") is True
    )
    v08_ok = bool(
        v08_metrics
        and v08_reliability
        and v08_metrics.get("citation_coverage") == 1.0
        and v08_metrics.get("verified_memory_write_count") == 0
        and v08_metrics.get("layer3_mutation_count") == 0
        and v08_metrics.get("checkpoint_resume_success") is True
        and v08_reliability.get("pass_power_3") is True
    )
    if layer_ok and tau_ok and path_ok and v08_ok and e2e_ok:
        label = "v0.9 论文主实验证据收拢阶段"
        summary = (
            "当前实现已经把 Layer-3 path-promotion 从底座验证推进到论文主实验："
            "E2E benchmark 比较 no_memory、raw_rag_over_logs、retrieval_memory、"
            "mw_verified_memory 与 mw_layer3_path，并具备真实 pytest/diff 与 pass^3 证据。"
        )
    elif layer_ok and tau_ok and path_ok and v08_ok:
        label = "v0.8 integrated substrate 完成，进入 v0.9 优化阶段"
        summary = (
            "当前实现已经具备 Layer-3 path-promotion、live/coding-debug evidence、"
            "RAG evidence、GBrain candidate graph、specialist EvidencePacket 与 "
            "checkpoint/resume。0.9 应聚焦优化和外部 benchmark，而不是继续搭建基础框架。"
        )
    elif layer_ok and tau_ok and path_ok:
        label = "v0.7 Layer-3 path-promotion 收口阶段"
        summary = (
            "当前实现已经超出 Sprint 0 / v0.2.0，主线是 Layer-3 path-promotion "
            "加最小 lifecycle gates，而不是继续堆新的 marker 或图谱重构。"
        )
    else:
        label = "原型能力整合阶段"
        summary = "当前检查没有完全对齐 v0.7 收口信号，优先修复回归或补齐 smoke 输出。"
    return {
        "label": label,
        "summary": summary,
        "signals": {
            "pytest_ok": pytest_summary.get("ok", False),
            "layer_smoke_ok": layer_ok,
            "tau_smoke_ok": tau_ok,
            "path_promotion_metrics_ok": path_ok,
            "lme_path_metrics_ok": lme_ok,
            "layer3_e2e_ok": e2e_ok,
            "v08_integrated_substrate_ok": v08_ok,
        },
    }


def build_suggestions(
    *,
    pytest_summary: dict[str, Any],
    readme_differences: list[dict[str, Any]],
    doc_differences: list[dict[str, Any]],
    tidy_result: dict[str, Any],
) -> list[str]:
    suggestions: list[str] = []
    if not pytest_summary.get("ok", False):
        suggestions.append("先把 `pytest` 回归修到全绿，再把阶段结论当作对外叙述依据。")
    if readme_differences:
        suggestions.append("README 的 benchmark 表已经和当前实测不一致，建议改为引用最新 artifact，或注明日期与环境。")
    if doc_differences:
        suggestions.append("`docs/development_plan.md` 里的固定 `pytest` 数量已经过期，建议改成最新结果或改成不写死总数。")
    suggestions.append("下一步应把 v0.9 聚焦到优化与外部 benchmark：LongMemEval-V2、Mem2ActBench、EvoMemBench、MemEvoBench、coding-debug 扩展、压力/雪崩测试和 provider fallback。")
    if tidy_result.get("moved"):
        suggestions.append("后续本地运行产物统一写入 `.workspace_runs/` 或 `docs/validation/<run>/`，不要再把 `.memoryweaver-*` / `.tmp-*` 散落在仓库根目录。")
    return suggestions


def build_markdown_report(report: dict[str, Any]) -> str:
    pytest_summary = report["checks"]["pytest"]["summary"]
    baseline = report["checks"]["prototype_baseline"]
    readme_differences = report["readme_differences"]
    doc_differences = report["doc_differences"]
    lines = [
        "# Current Stage Check",
        "",
        f"- Generated at: `{report['generated_at_utc']}`",
        f"- Passed: `{report['passed']}`",
        "",
        "## 今日 TODO",
        "",
    ]
    for item in report["today_todo"]:
        lines.append(f"- `{item['title']}`")
        lines.append(f"  Source: `{item['source']}`")
        lines.append(f"  Detail: {item['detail']}")
    lines.extend(
        [
            "",
            "## 当前阶段",
            "",
            f"- Stage: `{report['current_stage']['label']}`",
            f"- Summary: {report['current_stage']['summary']}",
            f"- Pytest: `{pytest_summary.get('summary_line', '')}`",
            f"- Layer smoke passed: `{report['checks']['layer_smoke'].get('passed', False)}`",
            f"- Tau smoke success: `{report['checks']['tau_smoke'].get('success', False)}`",
            "",
            "## README / Docs 偏差",
            "",
            f"- README benchmark differences: `{len(readme_differences)}`",
            f"- Docs claim differences: `{len(doc_differences)}`",
        ]
    )
    if baseline:
        lines.extend(
            [
                "",
                "## 今日基线摘录",
                "",
                f"- Python: `{baseline.get('python', '')}`",
                f"- Platform: `{baseline.get('platform', '')}`",
                f"- 100-item write throughput: `{baseline['performance'][0]['write']['items_per_second']}` items/s",
                f"- 100-item verified search p95: `{baseline['performance'][0]['verified_search']['p95_ms']}` ms",
            ]
        )
    if readme_differences:
        lines.extend(["", "### README Differences", ""])
        for diff in readme_differences:
            lines.append(
                f"- `{diff['source']}` item `{diff['items']}` field `{diff['field']}`: "
                f"claimed `{diff['claimed']}`, actual `{diff['actual']}`"
            )
    if doc_differences:
        lines.extend(["", "### Docs Differences", ""])
        for diff in doc_differences:
            lines.append(
                f"- `{diff['source']}` field `{diff['field']}`: claimed `{diff['claimed']}`, "
                f"actual passed `{diff['actual_passed']}`, actual failed `{diff['actual_failed']}`"
            )
    lines.extend(["", "## 建议", ""])
    for item in report["suggestions"]:
        lines.append(f"- {item}")
    tidy_result = report.get("tidy_root", {})
    if tidy_result.get("moved"):
        lines.extend(["", "## Root Cleanup", ""])
        lines.append(f"- Archive dir: `{tidy_result['archive_dir']}`")
        for name in tidy_result["moved"]:
            lines.append(f"- Moved: `{name}`")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--pytest-timeout", type=int, default=300)
    parser.add_argument("--baseline-timeout", type=int, default=180)
    parser.add_argument("--smoke-timeout", type=int, default=120)
    parser.add_argument("--tidy-root", action="store_true")
    args = parser.parse_args()

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    tidy_result = {"archive_dir": "", "moved": []}
    if args.tidy_root:
        tidy_result = archive_transient_root_entries(ROOT, ROOT / ".workspace_runs")

    layer_root = output_dir / ".memoryweaver-layer"
    tau_root = output_dir / ".memoryweaver-tau"

    pytest_result = run_command([sys.executable, "-m", "pytest", "-q"], timeout=args.pytest_timeout)
    _write_text(output_dir / "pytest.txt", pytest_result["stdout"] + pytest_result["stderr"])
    pytest_summary = parse_pytest_summary(pytest_result["stdout"] + "\n" + pytest_result["stderr"])

    baseline_result_raw = run_command(
        [sys.executable, str(ROOT / "benchmarks" / "prototype_baseline.py")],
        timeout=args.baseline_timeout,
    )
    baseline_result = parse_json_output(baseline_result_raw) or {}
    _write_json(output_dir / "prototype_baseline.json", baseline_result)

    layer_smoke_raw = run_command(
        [
            sys.executable,
            "-m",
            "memoryweaver.cli",
            "layer",
            "smoke",
            "--root",
            str(layer_root),
            "--json",
        ],
        timeout=args.smoke_timeout,
    )
    layer_smoke = parse_json_output(layer_smoke_raw) or {}
    _write_json(output_dir / "layer_smoke.json", layer_smoke)

    validate_raw = run_command(
        [
            sys.executable,
            "-m",
            "memoryweaver.cli",
            "validate",
            "--root",
            str(layer_root),
            "--json",
        ],
        timeout=args.smoke_timeout,
    )
    validate_layer = parse_json_output(validate_raw) or {}
    _write_json(output_dir / "validate_layer.json", validate_layer)

    doctor_raw = run_command(
        [
            sys.executable,
            "-m",
            "memoryweaver.cli",
            "doctor",
            "--root",
            str(layer_root),
            "--json",
        ],
        timeout=args.smoke_timeout,
    )
    doctor_layer = parse_json_output(doctor_raw) or {}
    _write_json(output_dir / "doctor_layer.json", doctor_layer)

    tau_smoke_raw = run_command(
        [
            sys.executable,
            "-m",
            "memoryweaver.cli",
            "eval",
            "tau-smoke",
            "--root",
            str(tau_root),
            "--json",
        ],
        timeout=args.smoke_timeout,
    )
    tau_smoke = parse_json_output(tau_smoke_raw) or {}
    _write_json(output_dir / "tau_smoke.json", tau_smoke)

    readme_differences: list[dict[str, Any]] = []
    if baseline_result:
        readme_differences.extend(
            compare_readme_benchmark_claims(
                _read_text(ROOT / "README.md"),
                baseline_result,
                source_name="README.md",
            )
        )
        readme_differences.extend(
            compare_readme_benchmark_claims(
                _read_text(ROOT / "README_ZH.md"),
                baseline_result,
                source_name="README_ZH.md",
            )
        )

    doc_differences = collect_doc_differences(pytest_summary)

    path_metrics = None
    path_metrics_path = ROOT / "docs" / "validation" / "layer3-path-promotion-v0.7" / "metrics.json"
    if path_metrics_path.exists():
        path_metrics = json.loads(_read_text(path_metrics_path))
    lme_metrics = None
    lme_metrics_path = ROOT / "docs" / "validation" / "layer3-path-promotion-lme-v2" / "metrics.json"
    if lme_metrics_path.exists():
        lme_metrics = json.loads(_read_text(lme_metrics_path))
    e2e_metrics = None
    e2e_metrics_path = ROOT / "docs" / "validation" / "layer3-path-promotion-e2e" / "metrics.json"
    if e2e_metrics_path.exists():
        e2e_metrics = json.loads(_read_text(e2e_metrics_path))
    e2e_reliability = None
    e2e_reliability_path = ROOT / "docs" / "validation" / "layer3-path-promotion-e2e" / "reliability.json"
    if e2e_reliability_path.exists():
        e2e_reliability = json.loads(_read_text(e2e_reliability_path))
    v08_metrics = None
    v08_metrics_path = ROOT / "docs" / "validation" / "v0.8-integration" / "metrics.json"
    if v08_metrics_path.exists():
        v08_metrics = json.loads(_read_text(v08_metrics_path))
    v08_reliability = None
    v08_reliability_path = ROOT / "docs" / "validation" / "v0.8-integration" / "reliability.json"
    if v08_reliability_path.exists():
        v08_reliability = json.loads(_read_text(v08_reliability_path))

    current_stage = derive_current_stage(
        pytest_summary=pytest_summary,
        layer_smoke=layer_smoke,
        tau_smoke=tau_smoke,
        path_metrics=path_metrics,
        lme_metrics=lme_metrics,
        e2e_metrics=e2e_metrics,
        e2e_reliability=e2e_reliability,
        v08_metrics=v08_metrics,
        v08_reliability=v08_reliability,
    )
    suggestions = build_suggestions(
        pytest_summary=pytest_summary,
        readme_differences=readme_differences,
        doc_differences=doc_differences,
        tidy_result=tidy_result,
    )
    passed = bool(
        pytest_summary.get("ok", False)
        and layer_smoke.get("passed") is True
        and validate_layer.get("valid") is True
        and doctor_layer.get("valid") is True
        and tau_smoke.get("success") is True
    )

    report = {
        "generated_at_utc": _utc_now(),
        "passed": passed,
        "today_todo": collect_today_todo(),
        "current_stage": current_stage,
        "checks": {
            "pytest": {
                "command": pytest_result["command"],
                "returncode": pytest_result["returncode"],
                "timed_out": pytest_result["timed_out"],
                "duration_seconds": pytest_result["duration_seconds"],
                "summary": pytest_summary,
            },
            "prototype_baseline": baseline_result,
            "layer_smoke": layer_smoke,
            "validate_layer": validate_layer,
            "doctor_layer": doctor_layer,
            "tau_smoke": tau_smoke,
        },
        "readme_differences": readme_differences,
        "doc_differences": doc_differences,
        "suggestions": suggestions,
        "tidy_root": tidy_result,
    }

    _write_json(output_dir / "report.json", report)
    _write_text(output_dir / "report.md", build_markdown_report(report))
    print(json.dumps({"output_dir": str(output_dir), "passed": passed}, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
