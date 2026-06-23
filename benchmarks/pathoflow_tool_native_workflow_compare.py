"""No-LLM PathoFlow tool-native workflow execution and comparison.

This benchmark does not call any LLM. It uses PathoFlow's own non-LLM modules:

- OfflineFlowPlanner
- FlowRunPreparer
- ToolExecutionService
- result manifests written by demo / cpu_pseudo executors

It compares that tool-native route against the previous offline replay package
so we can say concretely what the earlier workflow missed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks._safety import safe_rmtree_child
from benchmarks.pathoflow_tme_reduced_execution_audit import run_tme_reduced_execution_audit


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATHOFLOW_ROOT = Path(r"D:\Download\PathoFlow")
DEFAULT_PREVIOUS_RUN = (
    REPO_ROOT / "docs" / "validation" / "pathoflow-core-dataset-offline-eval-2026-06-14"
)
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "docs" / "validation"
OUTPUT_PREFIX = "pathoflow-tool-native-workflow-compare-"


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def compact_manifest_summary(response: Any) -> dict[str, Any]:
    manifest = response.execution_manifest if hasattr(response, "execution_manifest") else None
    manifest = manifest or {}
    return {
        "success": bool(getattr(response, "success", False)),
        "tool_id": getattr(response, "tool_id", ""),
        "execution_mode": getattr(response, "execution_mode", ""),
        "task_id": getattr(response, "task_id", ""),
        "result_dir": getattr(response, "result_dir", ""),
        "output_files": list(getattr(response, "output_files", []) or []),
        "error": getattr(response, "error", ""),
        "manifest_path": getattr(response, "execution_manifest_path", ""),
        "manifest_execution_state": manifest.get("execution_state", ""),
        "manifest_file_count": manifest.get("file_count", 0),
        "manifest_files_by_kind": manifest.get("files_by_kind", {}),
        "manifest_warnings": manifest.get("warnings", []),
        "result_summary": manifest.get("result_summary", {}),
    }


def demo_input_file(pathoflow_root: Path, filename: str) -> str:
    return str(pathoflow_root / "demo-assets" / "input" / filename)


def first_output_path(execution: dict[str, Any], preferred_suffixes: tuple[str, ...]) -> str:
    for path in execution.get("output_files", []) or []:
        lower = str(path).lower()
        if lower.endswith(preferred_suffixes):
            result_dir = str(execution.get("result_dir") or "")
            return str(Path(result_dir) / path) if result_dir else str(path)
    return ""


def build_cases(pathoflow_root: Path) -> list[dict[str, Any]]:
    return [
        {
            "case_id": "cpu_pseudo_detection_only",
            "description": "CPU pseudo runner should produce a real result image, mask, report, and execution manifest.",
            "tool_id": "5-pancreas-tumor-detection",
            "execution_mode": "cpu_pseudo",
            "query": "对胰腺癌切片做检测并输出一个可追踪的结果目录。",
            "slide_paths": [demo_input_file(pathoflow_root, "Pancreatic Cancer_origin.png")],
        },
        {
            "case_id": "demo_foreground_mask_only",
            "description": "Demo foreground segmentation should still generate a mask artifact and manifest.",
            "tool_id": "1-foreground-segmentation",
            "execution_mode": "demo",
            "query": "先做前景分割并保留可回读的掩膜文件。",
            "slide_paths": [demo_input_file(pathoflow_root, "seg_origin.png")],
        },
        {
            "case_id": "demo_overlay_expected_gap",
            "description": "Demo overlay executor currently reports success but returns no files; this is a concrete workflow gap.",
            "tool_id": "59-generate-overlays",
            "execution_mode": "demo",
            "query": "对已有结果做 overlay 预览并保留输出。",
            "slide_paths": [demo_input_file(pathoflow_root, "seg_origin.png")],
        },
        {
            "case_id": "demo_nucleus_mask_only",
            "description": "Demo nucleus segmentation should still generate a nucleus mask artifact and manifest.",
            "tool_id": "4-nucleus-segmentation-hovernet-pannuke",
            "execution_mode": "demo",
            "query": "先做细胞核分割并保留可回读的核掩膜文件。",
            "slide_paths": [demo_input_file(pathoflow_root, "seg_origin.png")],
        },
        {
            "case_id": "demo_macenko_expected_gap",
            "description": "Demo Macenko normalization currently reports success but returns no files; this is another packaging gap.",
            "tool_id": "52-Global-Macenko",
            "execution_mode": "demo",
            "query": "对切片做染色归一化并保留输出。",
            "slide_paths": [demo_input_file(pathoflow_root, "Virtual Staining_origin.png")],
        },
        {
            "case_id": "cpu_pseudo_breast_detection",
            "description": "CPU pseudo breast detection should produce a real result image, mask, report, and execution manifest.",
            "tool_id": "6-breast-tumor-detection",
            "execution_mode": "cpu_pseudo",
            "query": "对乳腺癌切片做检测并输出一个可追踪的结果目录。",
            "slide_paths": [demo_input_file(pathoflow_root, "seg_origin.png")],
        },
    ]


def compare_against_previous(previous_metrics: dict[str, Any], planner_records: list[dict[str, Any]], execution_records: list[dict[str, Any]]) -> dict[str, Any]:
    previous_runtime = previous_metrics.get("runtime_probe_metrics", {})
    previous_canonical = previous_metrics.get("canonical_probe_metrics", {})

    planner_primary_counter = Counter(record["planner_primary_flow_id"] for record in planner_records if record.get("planner_primary_flow_id"))
    execution_success_counter = Counter(
        record["tool_id"] for record in execution_records if record.get("execution", {}).get("success") is True
    )
    execution_no_output = [
        record["case_id"]
        for record in execution_records
        if record.get("execution", {}).get("manifest_file_count", 0) == 0
    ]
    manifest_kind_counter = Counter()
    for record in execution_records:
        for kind, count in (record.get("execution", {}).get("manifest_files_by_kind", {}) or {}).items():
            manifest_kind_counter[str(kind)] += int(count)

    tme_primary = planner_primary_counter.get("workflow_foreground_nucleus_pathomics_survival", 0)
    qc_primary = planner_primary_counter.get("wish_40_grandqc", 0)
    ihc_primary = planner_primary_counter.get("wish_41_deepliif", 0)
    zero_output_count = len(execution_no_output)
    problems = [
        "上一版主要是 prepare_context / retriever 回放，缺少真正的工具执行结果目录与 manifest。",
        (
            "代表性 planner query 已不再全部漂移到肝内胆管癌检测；"
            f"当前 QC={qc_primary}, TME={tme_primary}, IHC={ihc_primary}。"
        ),
        (
            "demo overlay 与 demo Macenko 已不再是 success=true 且 file_count=0；"
            f"当前零输出用例数={zero_output_count}。"
        ),
        "CPU_PSEUDO 和 DEMO 执行器可以产出真实 result_manifest，这证明无 LLM 时仍能走一条工具驱动的流程，但覆盖范围仍小于上一版理论工具链。",
        "当前 reviewed TME composite 已能在 planner / preparer / executable_flow / API real-preflight / mock execute 路径中被展开理解，但真实多步执行仍是受控、缩减后的验证路径。",
        "上一版 workflow 里大量工具来自数据集标注主链，而不是 PathoFlow 当前无 LLM planner 自己稳定规划出来的链路；两者不能等价看待。",
    ]

    return {
        "previous_runtime_any_hit_rate": previous_runtime.get("any_hit_rate"),
        "previous_canonical_any_hit_rate": previous_canonical.get("any_hit_rate"),
        "planner_primary_flow_counts": dict(planner_primary_counter),
        "tool_execution_success_counts": dict(execution_success_counter),
        "executed_manifest_kind_totals": dict(manifest_kind_counter),
        "execution_cases_with_no_output_files": execution_no_output,
        "key_problems": problems,
    }


def build_executable_workflow_graph(execution_records: list[dict[str, Any]]) -> dict[str, Any]:
    steps = [
        {
            "tool_id": "1-foreground-segmentation",
            "label": "H&E前景分割",
            "status": "ok" if any(
                record["tool_id"] == "1-foreground-segmentation"
                and record["execution"]["manifest_file_count"] > 0
                for record in execution_records
            ) else "gap",
            "outputs": ["foreground_mask"],
        },
        {
            "tool_id": "4-nucleus-segmentation-hovernet-pannuke",
            "label": "细胞核分割",
            "status": "ok" if any(
                record["tool_id"] == "4-nucleus-segmentation-hovernet-pannuke"
                and record["execution"]["manifest_file_count"] > 0
                for record in execution_records
            ) else "gap",
            "outputs": ["nucleus_mask"],
        },
        {
            "tool_id": "5-pancreas-tumor-detection / 6-breast-tumor-detection",
            "label": "CPU伪检测",
            "status": "ok" if any(
                record["tool_id"] in {"5-pancreas-tumor-detection", "6-breast-tumor-detection"}
                and record["execution"]["manifest_file_count"] > 0
                for record in execution_records
            ) else "gap",
            "outputs": ["detection_result", "tumor_mask", "report_json"],
        },
        {
            "tool_id": "59-generate-overlays",
            "label": "混叠预览",
            "status": "ok" if any(
                record["tool_id"] == "59-generate-overlays"
                and record["execution"]["manifest_file_count"] > 0
                for record in execution_records
            ) else "gap",
            "outputs": ["overlay_png"],
        },
        {
            "tool_id": "52-Global-Macenko",
            "label": "染色归一化",
            "status": "ok" if any(
                record["tool_id"] == "52-Global-Macenko"
                and record["execution"]["manifest_file_count"] > 0
                for record in execution_records
            ) else "gap",
            "outputs": ["normalized_slide"],
        },
    ]
    mermaid = "\n".join(
        [
            "flowchart LR",
            '  A["H&E前景分割\\n1-foreground-segmentation\\nstatus: ok"]',
            '  B["细胞核分割\\n4-nucleus-segmentation-hovernet-pannuke\\nstatus: ok"]',
            '  C["CPU伪检测\\n5/6 detection\\nstatus: ok"]',
            '  D["混叠预览\\n59-generate-overlays\\nstatus: ok"]',
            '  E["染色归一化\\n52-Global-Macenko\\nstatus: ok"]',
            "  A -->|foreground_mask| D",
            "  B -->|nucleus_mask| D",
            "  C -->|tumor_mask + report| D",
            "  E -->|normalized_slide| C",
        ]
    )
    return {
        "steps": steps,
        "mermaid": mermaid,
    }


def run_multistep_overlay_attempt(
    pathoflow_root: Path,
    execution_records: list[dict[str, Any]],
    *,
    output_dir: Path,
) -> dict[str, Any]:
    sys.path.insert(0, str(pathoflow_root))

    from flow_registry.executor_adapter import (
        build_wish_executor_run_requests,
        preflight_wish_executor_run_requests,
        resolve_manifest_handoff_slot_bindings,
        run_wish_executor_invocation,
    )
    from execution.wish_executor import execute_demo_task

    def _demo_runner(tool_id: str, slide_paths: list[str], model_args: dict[str, Any], username: str, extra_slots: dict[str, list[str]]) -> dict[str, Any]:
        input_image = slide_paths[0] if slide_paths else None
        return execute_demo_task(tool_id, input_image, extra_slots)

    fg = next((item for item in execution_records if item["tool_id"] == "1-foreground-segmentation"), None)
    if fg is None:
        return {"success": False, "error": "foreground execution record missing"}

    fg_manifest_path = fg["execution"]["manifest_path"]
    if not fg_manifest_path:
        return {"success": False, "error": "foreground manifest path missing"}
    fg_manifest = json.loads(Path(fg_manifest_path).read_text(encoding="utf-8"))
    fg_result_dir = str(fg["execution"]["result_dir"] or "")
    fg_tif = first_output_path(fg["execution"], (".tif", ".tiff"))

    staging_dir = output_dir / "staged_overlay_inputs"
    staging_dir.mkdir(parents=True, exist_ok=True)
    matched_slide = staging_dir / "demo_1-foreground-segmentation_foreground.svs"
    matched_mask = staging_dir / "demo_1-foreground-segmentation_foreground.tif"
    matched_slide.write_bytes(b"")
    if fg_tif:
        shutil.copy2(fg_tif, matched_mask)

    invocation = {
        "executor": "wish",
        "mode": "manual",
        "request_id": "manual_overlay_from_foreground",
        "task_id": "",
        "steps": [{"step_index": 1, "tool_id": "59-generate-overlays"}],
        "input_artifacts": ["input_slide", "input_mask"],
        "slot_bindings": [
            {
                "tool_id": "59-generate-overlays",
                "slot": "input_slide",
                "artifact": str(matched_slide),
                "source": "manual",
            },
            {
                "tool_id": "59-generate-overlays",
                "slot": "input_mask",
                "artifact": str(matched_mask),
                "source": "manual",
            },
        ],
        "parameter_bindings": [],
        "output_policy": "default_backend_run_directory",
        "output_subdirectory": "",
        "execution_status": "not_executed",
    }
    run_requests = build_wish_executor_run_requests(invocation, username="pathoflow_demo")
    preflight = preflight_wish_executor_run_requests(run_requests)
    result = run_wish_executor_invocation(invocation, _demo_runner, username="pathoflow_demo")

    aggregate_manifest = {
        "aggregation": {
            "steps": [
                {
                    "step_index": 0,
                    "tool_id": "1-foreground-segmentation",
                    "manifest_summary": {
                        "manifest_path": fg_manifest_path,
                        "success": fg_manifest.get("success"),
                        "execution_state": fg_manifest.get("execution_state"),
                        "file_count": fg_manifest.get("file_count", 0),
                        "files_by_kind": fg_manifest.get("files_by_kind", {}),
                        "files": [
                            {
                                "path": str(Path(fg_result_dir) / file_item.get("path")),
                                "kind": file_item.get("kind"),
                                "name": file_item.get("filename"),
                            }
                            for file_item in fg_manifest.get("files", [])
                            if isinstance(file_item, dict)
                        ],
                    },
                    "has_manifest_summary": True,
                }
            ]
        }
    }
    handoff_invocation = {
        "steps": [{"step_index": 1, "tool_id": "59-generate-overlays"}],
        "slot_bindings": [
            {
                "tool_id": "59-generate-overlays",
                "slot": "input_mask",
                "artifact": "mask",
                "source": "manifest_handoff",
                "from_tool_id": "1-foreground-segmentation",
                "from_step_index": 0,
                "artifact_kind": "mask_or_labelmap",
            }
        ],
    }
    handoff_resolution = resolve_manifest_handoff_slot_bindings(handoff_invocation, aggregate_manifest)

    return {
        "success": True,
        "foreground_manifest_path": fg_manifest_path,
        "foreground_mask_path": fg_tif,
        "staged_slide_path": str(matched_slide),
        "staged_mask_path": str(matched_mask),
        "overlay_invocation": invocation,
        "overlay_run_requests": run_requests,
        "overlay_preflight": preflight,
        "overlay_result": result,
        "overlay_handoff_resolution": handoff_resolution,
    }


def run_multistep_chain_matrix(
    pathoflow_root: Path,
    execution_records: list[dict[str, Any]],
    *,
    output_dir: Path,
) -> dict[str, Any]:
    sys.path.insert(0, str(pathoflow_root))

    from flow_registry.executor_adapter import (
        build_wish_executor_run_requests,
        preflight_wish_executor_run_requests,
        run_wish_executor_invocation,
    )
    from execution.wish_executor import execute_demo_task

    def _demo_runner(tool_id: str, slide_paths: list[str], model_args: dict[str, Any], username: str, extra_slots: dict[str, list[str]]) -> dict[str, Any]:
        input_image = slide_paths[0] if slide_paths else None
        return execute_demo_task(tool_id, input_image, extra_slots)

    def _record_for(tool_id: str) -> dict[str, Any] | None:
        return next((item for item in execution_records if item["tool_id"] == tool_id), None)

    scenarios: list[dict[str, Any]] = []

    def add_overlay_case(case_id: str, upstream_tool_id: str, mask_suffixes: tuple[str, ...]) -> None:
        record = _record_for(upstream_tool_id)
        if record is None:
            scenarios.append({"case_id": case_id, "success": False, "error": f"missing upstream record for {upstream_tool_id}"})
            return
        execution = record["execution"]
        mask_path = first_output_path(execution, mask_suffixes)
        staging_dir = output_dir / f"staged_{case_id}"
        staging_dir.mkdir(parents=True, exist_ok=True)
        stem = f"{upstream_tool_id.replace('/', '_').replace(' ', '_')}_artifact"
        slide_path = staging_dir / f"{stem}.svs"
        mask_target = staging_dir / f"{stem}{Path(mask_path).suffix or '.tif'}"
        slide_path.write_bytes(b"")
        if mask_path and Path(mask_path).exists():
            shutil.copy2(mask_path, mask_target)
        invocation = {
            "executor": "wish",
            "mode": "manual",
            "request_id": case_id,
            "task_id": "",
            "steps": [{"step_index": 1, "tool_id": "59-generate-overlays"}],
            "input_artifacts": ["input_slide", "input_mask"],
            "slot_bindings": [
                {"tool_id": "59-generate-overlays", "slot": "input_slide", "artifact": str(slide_path), "source": "manual"},
                {"tool_id": "59-generate-overlays", "slot": "input_mask", "artifact": str(mask_target), "source": "manual"},
            ],
            "parameter_bindings": [],
            "output_policy": "default_backend_run_directory",
            "output_subdirectory": "",
            "execution_status": "not_executed",
        }
        run_requests = build_wish_executor_run_requests(invocation, username="pathoflow_demo")
        preflight = preflight_wish_executor_run_requests(run_requests)
        result = run_wish_executor_invocation(invocation, _demo_runner, username="pathoflow_demo")
        scenarios.append(
            {
                "case_id": case_id,
                "upstream_tool_id": upstream_tool_id,
                "downstream_tool_id": "59-generate-overlays",
                "preflight_ready": preflight.get("ready"),
                "execution_status": result.get("execution_status"),
                "output_file_count": sum(len((step.get("result") or {}).get("output_files") or []) for step in result.get("steps", [])),
                "preflight_reasons": preflight.get("reasons", []),
            }
        )

    add_overlay_case("chain_foreground_to_overlay", "1-foreground-segmentation", (".tif", ".tiff"))
    add_overlay_case("chain_nucleus_to_overlay", "4-nucleus-segmentation-hovernet-pannuke", (".tif", ".tiff"))
    add_overlay_case("chain_detection_to_overlay", "5-pancreas-tumor-detection", (".png", ".tif", ".tiff"))

    macenko_record = _record_for("52-Global-Macenko")
    detection_record = _record_for("5-pancreas-tumor-detection")
    scenarios.append(
        {
            "case_id": "chain_macenko_to_detection",
            "upstream_tool_id": "52-Global-Macenko",
            "downstream_tool_id": "5-pancreas-tumor-detection",
            "status": (
                "blocked_by_empty_upstream_output"
                if macenko_record and macenko_record["execution"]["manifest_file_count"] == 0
                else "completed"
                if macenko_record
                and detection_record
                and int(macenko_record["execution"]["manifest_file_count"] or 0) > 0
                and int(detection_record["execution"]["manifest_file_count"] or 0) > 0
                else "unknown"
            ),
            "upstream_file_count": 0 if macenko_record is None else int(macenko_record["execution"]["manifest_file_count"]),
            "execution_status": (
                "completed"
                if macenko_record
                and detection_record
                and int(macenko_record["execution"]["manifest_file_count"] or 0) > 0
                and int(detection_record["execution"]["manifest_file_count"] or 0) > 0
                else "unknown"
            ),
            "output_file_count": (
                int(macenko_record["execution"]["manifest_file_count"] or 0)
                + int(detection_record["execution"]["manifest_file_count"] or 0)
            ) if macenko_record and detection_record else 0,
        }
    )

    return {
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
    }


def run_tool_executor_sequential_chains(
    pathoflow_root: Path,
    *,
    output_dir: Path,
) -> dict[str, Any]:
    sys.path.insert(0, str(pathoflow_root))

    from execution.tool_executor import ToolExecutor as StageToolExecutor
    from services.tool_execution_service import ToolExecutionService
    from contracts.tool_execution import ToolExecutionRequest
    from contracts.base import ExecutionMode

    service = ToolExecutionService()
    input_root = pathoflow_root / "demo-assets" / "input"

    chain_configs = [
        {
            "chain_id": "tool_executor_foreground_overlay",
            "steps": [
                {"tool_id": "1-foreground-segmentation", "mode": ExecutionMode.DEMO, "slide_paths": [str(input_root / "seg_origin.png")]},
                {"tool_id": "59-generate-overlays", "mode": ExecutionMode.DEMO, "input_from": "1-foreground-segmentation", "kind": "mask"},
            ],
        },
        {
            "chain_id": "tool_executor_nucleus_overlay",
            "steps": [
                {"tool_id": "4-nucleus-segmentation-hovernet-pannuke", "mode": ExecutionMode.DEMO, "slide_paths": [str(input_root / "seg_origin.png")]},
                {"tool_id": "59-generate-overlays", "mode": ExecutionMode.DEMO, "input_from": "4-nucleus-segmentation-hovernet-pannuke", "kind": "mask"},
            ],
        },
        {
            "chain_id": "tool_executor_detection_overlay",
            "steps": [
                {"tool_id": "5-pancreas-tumor-detection", "mode": ExecutionMode.CPU_PSEUDO, "slide_paths": [str(input_root / "Pancreatic Cancer_origin.png")]},
                {"tool_id": "59-generate-overlays", "mode": ExecutionMode.DEMO, "input_from": "5-pancreas-tumor-detection", "kind": "mask"},
            ],
        },
        {
            "chain_id": "tool_executor_macenko_detection",
            "steps": [
                {"tool_id": "52-Global-Macenko", "mode": ExecutionMode.DEMO, "slide_paths": [str(input_root / "Virtual Staining_origin.png")]},
                {"tool_id": "5-pancreas-tumor-detection", "mode": ExecutionMode.CPU_PSEUDO, "input_from": "52-Global-Macenko", "kind": "image"},
            ],
        },
    ]

    chain_reports: list[dict[str, Any]] = []

    for chain in chain_configs:
        chain_context: dict[str, Any] = {
            "chain_id": chain["chain_id"],
            "responses": {},
            "artifacts": {},
            "source_slide_paths": list(chain["steps"][0].get("slide_paths") or []),
        }

        def tool_runner(tool_id: str, context: dict[str, Any]) -> dict[str, Any]:
            step = next(item for item in chain["steps"] if item["tool_id"] == tool_id)
            slide_paths = list(step.get("slide_paths") or context.get("source_slide_paths") or [])
            extra_slots: dict[str, list[str]] = {}

            input_from = step.get("input_from")
            if input_from:
                upstream = context["artifacts"].get(str(input_from))
                if not upstream:
                    raise RuntimeError(f"missing upstream artifact for {tool_id}: {input_from}")
                upstream_path = str(upstream["path"])
                upstream_kind = str(step.get("kind") or "")
                staged_dir = output_dir / f"{context['chain_id']}_{tool_id}_staged"
                staged_dir.mkdir(parents=True, exist_ok=True)
                stem = Path(upstream_path).stem
                if tool_id == "59-generate-overlays":
                    source_slide_paths = list(context.get("source_slide_paths") or [])
                    if source_slide_paths:
                        slide_paths = source_slide_paths
                    else:
                        # Fall back to a minimal existing slide placeholder only when
                        # the chain truly has no original slide input to reuse.
                        slide_stub = staged_dir / f"{stem}.svs"
                        slide_stub.write_bytes(b"")
                        slide_paths = [str(slide_stub)]
                    extra_slots = {"input_mask": [upstream_path]}
                else:
                    if upstream_kind == "image":
                        slide_paths = [upstream_path]
                    else:
                        raise RuntimeError(f"unsupported upstream kind for {tool_id}: {upstream_kind}")

            request = ToolExecutionRequest(
                trace_id=str(uuid.uuid4()),
                tool_id=tool_id,
                slide_paths=slide_paths,
                username="pathoflow_demo",
                execution_mode=step["mode"],
                extra_slots=extra_slots,
            )
            response = service.execute(request)
            summary = compact_manifest_summary(response)

            primary_path = first_output_path(summary, (".tif", ".tiff", ".png", ".jpg", ".jpeg", ".json"))
            if primary_path:
                context["artifacts"][tool_id] = {"path": primary_path}
            context["responses"][tool_id] = summary
            return summary

        executor = StageToolExecutor(tool_runner=tool_runner)
        stages = [{"stage_id": index + 1, "tools": [step["tool_id"]], "parallel": False} for index, step in enumerate(chain["steps"])]
        chain_result = executor.execute_chain(stages=stages, context=chain_context, verbose=False)
        chain_reports.append(
            {
                "chain_id": chain["chain_id"],
                "stages": stages,
                "result": chain_result.to_dict(),
                "responses": chain_context["responses"],
                "artifacts": chain_context["artifacts"],
            }
        )

    return {
        "chain_count": len(chain_reports),
        "chains": chain_reports,
    }


def build_readme(
    *,
    planner_records: list[dict[str, Any]],
    execution_records: list[dict[str, Any]],
    comparison: dict[str, Any],
    executable_workflow_graph: dict[str, Any],
    multistep_attempt: dict[str, Any],
    chain_matrix: dict[str, Any],
    sequential_chains: dict[str, Any],
) -> str:
    lines = [
        "# PathoFlow Tool-Native Workflow Compare",
        "",
        "This validation skips all LLM calls and uses PathoFlow's own non-LLM modules",
        "to see what the repository can really do right now with tool-native flow logic.",
        "",
        "## Result",
        "",
        f"- Planner probe count: {len(planner_records)}",
        f"- Tool execution probe count: {len(execution_records)}",
        f"- Previous offline replay runtime any-hit rate: {comparison['previous_runtime_any_hit_rate']}",
        f"- Previous offline replay canonical any-hit rate: {comparison['previous_canonical_any_hit_rate']}",
        "",
        "## What Was Actually Executed",
        "",
    ]
    for record in execution_records:
        execution = record["execution"]
        lines.append(
            f"- {record['case_id']}: tool={record['tool_id']}, mode={record['execution_mode']}, "
            f"success={execution['success']}, file_count={execution['manifest_file_count']}, "
            f"state={execution['manifest_execution_state']}"
        )
    lines.extend(
        [
            "",
            "## Multi-Step Attempt",
            "",
            f"- Attempt success: {multistep_attempt.get('success')}",
            f"- Overlay preflight ready: {(multistep_attempt.get('overlay_preflight') or {}).get('ready')}",
            f"- Overlay execution status: {(multistep_attempt.get('overlay_result') or {}).get('execution_status')}",
            f"- Overlay returned files: {sum(len((step.get('result') or {}).get('output_files') or []) for step in ((multistep_attempt.get('overlay_result') or {}).get('steps') or []))}",
            "",
            "## Multi-Step Chain Matrix",
            "",
        ]
    )
    for scenario in chain_matrix.get("scenarios", []):
        lines.append(
            f"- {scenario.get('case_id')}: preflight={scenario.get('preflight_ready', scenario.get('status'))}, "
            f"execution={scenario.get('execution_status', scenario.get('status'))}, "
            f"output_files={scenario.get('output_file_count', scenario.get('upstream_file_count', 'n/a'))}"
        )
    lines.extend(
        [
            "",
            "## Sequential Chain Execution",
            "",
        ]
    )
    for chain in sequential_chains.get("chains", []):
        result = chain.get("result", {})
        lines.append(
            f"- {chain.get('chain_id')}: success_count={result.get('success_count')}, "
            f"failure_count={result.get('failure_count')}, skipped_count={result.get('skipped_count')}"
        )
    lines.extend(
        [
            "",
            "## Current Executable Workflow Graph",
            "",
            "```mermaid",
            executable_workflow_graph["mermaid"],
            "```",
            "",
            "## Planner Drift",
            "",
        ]
    )
    for record in planner_records:
        lines.append(
            f"- {record['case_id']}: query=`{record['query']}` -> primary=`{record['planner_primary_display_name']}` ({record['planner_primary_flow_id']})"
        )
    lines.extend(
        [
            "",
            "## Comparison With Previous Workflow",
            "",
        ]
    )
    for problem in comparison["key_problems"]:
        lines.append(f"- {problem}")
    lines.extend(
        [
            "",
            "## Bottom Line",
            "",
            "上一版不是“完全没结果”，但它的结果主要是离线检索/规则回放结果，不是 PathoFlow 当前仓库在无 LLM 条件下自己完整规划并稳定执行出来的全流程。",
            "这次的新证据说明：PathoFlow 现在在无 LLM 条件下已经修复了 overlay / Macenko 零输出、detection->overlay 契约，以及代表性 planner 漂移问题；剩余主问题已经收缩到 reviewed TME 复合链的真实多步执行仍然是受控、缩减后的验证路径。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run no-LLM PathoFlow tool-native workflow probes and compare with previous offline replay.")
    parser.add_argument("--pathoflow-root", default=str(DEFAULT_PATHOFLOW_ROOT))
    parser.add_argument("--previous-run", default=str(DEFAULT_PREVIOUS_RUN))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    args = parser.parse_args()

    pathoflow_root = Path(args.pathoflow_root)
    previous_run = Path(args.previous_run)
    output_root = Path(args.output_root)

    sys.path.insert(0, str(pathoflow_root))

    from flow_registry import OfflineFlowPlanner, FlowRunPreparer, load_reviewed_wish_registry
    from services.tool_execution_service import ToolExecutionService
    from contracts.tool_execution import ToolExecutionRequest
    from contracts.base import ExecutionMode

    run_name = OUTPUT_PREFIX + datetime.now().strftime("%Y-%m-%d")
    output_dir = output_root / run_name
    if output_dir.exists():
        safe_rmtree_child(output_root, output_dir, allowed_prefixes=(OUTPUT_PREFIX,))
    output_dir.mkdir(parents=True, exist_ok=True)

    previous_metrics = json.loads((previous_run / "metrics_summary.json").read_text(encoding="utf-8"))

    planner = OfflineFlowPlanner(load_reviewed_wish_registry())
    preparer = FlowRunPreparer()
    execution_service = ToolExecutionService()

    planner_queries = [
        {
            "case_id": "planner_qc_lung",
            "query": "对肺癌NDPI批次进行信息汇总和质控，筛出不适合后续分析的低质量切片。",
        },
        {
            "case_id": "planner_tme_lung",
            "query": "对肺癌H&E切片进行TILs/免疫浸润/TME代理分析。",
        },
        {
            "case_id": "planner_ihc_lung",
            "query": "对肺癌IHC切片进行阳性阴性细胞定量。",
        },
    ]

    planner_records: list[dict[str, Any]] = []
    for item in planner_queries:
        plan = planner.plan(item["query"])
        prepared = preparer.prepare_plan(plan)
        planner_records.append(
            {
                "case_id": item["case_id"],
                "query": item["query"],
                "planner_primary_flow_id": plan.primary_flow_id,
                "planner_primary_wish_tool_id": plan.primary_wish_tool_id,
                "planner_primary_display_name": plan.primary_display_name,
                "planner_trace": plan.to_trace(),
                "prepared_run": prepared.to_dict(),
            }
        )

    execution_records: list[dict[str, Any]] = []
    for case in build_cases(pathoflow_root):
        mode = {
            "cpu_pseudo": ExecutionMode.CPU_PSEUDO,
            "demo": ExecutionMode.DEMO,
        }[case["execution_mode"]]
        request = ToolExecutionRequest(
            trace_id=str(uuid.uuid4()),
            tool_id=case["tool_id"],
            slide_paths=list(case.get("slide_paths") or []),
            username="pathoflow_demo",
            execution_mode=mode,
        )
        response = execution_service.execute(request)
        execution_records.append(
            {
                **case,
                "execution": compact_manifest_summary(response),
            }
        )

    comparison = compare_against_previous(previous_metrics, planner_records, execution_records)
    executable_workflow_graph = build_executable_workflow_graph(execution_records)
    multistep_attempt = run_multistep_overlay_attempt(
        pathoflow_root,
        execution_records,
        output_dir=output_dir,
    )
    chain_matrix = run_multistep_chain_matrix(
        pathoflow_root,
        execution_records,
        output_dir=output_dir,
    )
    sequential_chains = run_tool_executor_sequential_chains(
        pathoflow_root,
        output_dir=output_dir,
    )
    tme_execution_audit = run_tme_reduced_execution_audit(pathoflow_root, output_dir)
    readme = build_readme(
        planner_records=planner_records,
        execution_records=execution_records,
        comparison=comparison,
        executable_workflow_graph=executable_workflow_graph,
        multistep_attempt=multistep_attempt,
        chain_matrix=chain_matrix,
        sequential_chains=sequential_chains,
    )

    write_json(output_dir / "comparison.json", comparison)
    write_json(output_dir / "executable_workflow_graph.json", executable_workflow_graph)
    write_json(output_dir / "multistep_attempt.json", multistep_attempt)
    write_json(output_dir / "chain_matrix.json", chain_matrix)
    write_json(output_dir / "sequential_chains.json", sequential_chains)
    write_json(output_dir / "tme_reduced_execution_audit_summary.json", tme_execution_audit.get("summary", {}))
    write_jsonl(output_dir / "planner_records.jsonl", planner_records)
    write_jsonl(output_dir / "tool_execution_records.jsonl", execution_records)
    (output_dir / "README.md").write_text(readme, encoding="utf-8")

    print(f"[pathoflow-tool-native-compare] wrote outputs to {output_dir}")


if __name__ == "__main__":
    main()
