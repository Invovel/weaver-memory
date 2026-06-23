"""Audit the reduced TME execution path across PathoFlow planning and execution layers."""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_registry(pathoflow_root: Path):
    sys.path.insert(0, str(pathoflow_root))
    from flow_registry.registry import load_reviewed_wish_registry

    return load_reviewed_wish_registry()


def _planner_trace(pathoflow_root: Path, query: str) -> dict[str, Any]:
    sys.path.insert(0, str(pathoflow_root))
    from flow_registry import OfflineFlowPlanner

    registry = _load_registry(pathoflow_root)
    plan = OfflineFlowPlanner(registry).plan(query, top_k=5)
    return plan.to_trace()


def _active_preparer_trace(pathoflow_root: Path, query: str) -> dict[str, Any]:
    sys.path.insert(0, str(pathoflow_root))
    from flow_registry import FlowRunPreparer, OfflineFlowPlanner

    registry = _load_registry(pathoflow_root)
    prepared = FlowRunPreparer(registry, OfflineFlowPlanner(registry)).prepare_query(
        query,
        available_artifacts={"input_slide"},
    )
    return prepared.to_dict()


def _run_preparer_trace(pathoflow_root: Path, query: str) -> dict[str, Any]:
    sys.path.insert(0, str(pathoflow_root))
    from flow_registry.run_preparer.adapters import FlowRegistryAdapter
    from flow_registry.run_preparer.preparer import FlowRunPreparer

    registry = _load_registry(pathoflow_root)
    prepared = FlowRunPreparer(adapter=FlowRegistryAdapter(registry=registry)).prepare_query(
        query,
        available_artifacts=["input_slide"],
    )
    return prepared.to_dict()


def _executable_flow_trace(pathoflow_root: Path) -> dict[str, Any]:
    sys.path.insert(0, str(pathoflow_root))
    from flow_registry.executable_flow import expand_reviewed_composite_flow

    registry = _load_registry(pathoflow_root)
    return expand_reviewed_composite_flow(
        "workflow_foreground_nucleus_pathomics_survival",
        registry.flows,
    )


def _flow_prepare_api_traces(pathoflow_root: Path, output_dir: Path, query: str) -> dict[str, Any]:
    sys.path.insert(0, str(pathoflow_root))
    from flask import Flask
    from flow_registry.registry import load_reviewed_wish_registry
    from flow_registry.run_preparer import InMemoryApprovalTokenStore
    from flow_registry.run_preparer.adapters import FlowRegistryAdapter
    from flow_registry.run_preparer.preparer import FlowRunPreparer
    from flow_registry.run_preparer.real_execution import RealExecutionResult
    from flow_registry.run_preparer.wish_real_executor import WishRealExecutorAdapter
    from web.flow_prepare_api import register_flow_prepare_routes

    class FakeRealExecutor:
        def execute(self, prepared_run, request):
            return RealExecutionResult(
                status="real_submitted",
                execution_mode=request.execution_mode,
                run_hash=prepared_run.run_hash,
                primary_flow_id=prepared_run.primary_flow_id,
                dry_run=request.dry_run,
                audit=request.audit,
            )

    registry = load_reviewed_wish_registry()
    adapter = FlowRegistryAdapter(registry=registry)
    preparer = FlowRunPreparer(adapter=adapter)
    app = Flask(__name__)
    register_flow_prepare_routes(
        app,
        preparer=preparer,
        registry_adapter=adapter,
        token_store=InMemoryApprovalTokenStore(),
        real_executor=FakeRealExecutor(),
    )
    client = app.test_client()
    prepared_response = client.post(
        "/api/flow/prepare",
        json={
            "query": query,
            "available_artifacts": ["input_slide"],
            "user_id": "user_tme",
        },
    )
    prepared_payload = prepared_response.get_json()
    prepared = prepared_payload["data"] if prepared_payload and prepared_payload.get("success") else {}
    approval_response = client.post(
        "/api/flow/approval-intent",
        json={"user_id": "user_tme", "run_hash": prepared.get("run_hash", "")},
    )
    approval_payload = approval_response.get_json()
    token = ((approval_payload or {}).get("data") or {}).get("token", "")
    preflight_response = client.post(
        "/api/flow/real-preflight",
        json={
            "user_id": "user_tme",
            "run_hash": prepared.get("run_hash", ""),
            "wish_root": "/tmp",
            "pinglib_root": "/tmp",
            "output_dir": str(output_dir / "api_tme_preflight"),
            "gpu_policy": "cpu",
            "timeout_seconds": 60,
            "audit": {"minimal_sample": True, "sample_count": 1},
            "sample_inputs": {"input_slide": [__file__]},
        },
    )
    mock_execute_response = client.post(
        "/api/flow/execute",
        json={
            "user_id": "user_tme",
            "run_hash": prepared.get("run_hash", ""),
            "approval_token": token,
        },
    )

    slide = output_dir / "tme_case.svs"
    slide.write_text("slide", encoding="utf-8")

    with _patched_wish_executor(output_dir):
        app_real = Flask(__name__ + "_real")
        register_flow_prepare_routes(
            app_real,
            preparer=preparer,
            registry_adapter=adapter,
            token_store=InMemoryApprovalTokenStore(),
            real_executor=WishRealExecutorAdapter(exec_base=str(output_dir / "real_exec")),
        )
        client_real = app_real.test_client()
        prepared_real_response = client_real.post(
            "/api/flow/prepare",
            json={
                "query": query,
                "available_artifacts": ["input_slide"],
                "user_id": "user_tme",
            },
        )
        prepared_real_payload = prepared_real_response.get_json()
        prepared_real = prepared_real_payload["data"] if prepared_real_payload and prepared_real_payload.get("success") else {}
        approval_real_response = client_real.post(
            "/api/flow/approval-intent",
            json={"user_id": "user_tme", "run_hash": prepared_real.get("run_hash", "")},
        )
        approval_real_payload = approval_real_response.get_json()
        token_real = ((approval_real_payload or {}).get("data") or {}).get("token", "")
        execute_real_response = client_real.post(
            "/api/flow/execute-real",
            json={
                "user_id": "user_tme",
                "run_hash": prepared_real.get("run_hash", ""),
                "approval_token": token_real,
                "execution_mode": "real_run",
                "dry_run": False,
                "sample_inputs": {"input_slide": [str(slide)]},
                "output_dir": str(output_dir / "real_exec"),
                "audit": {"minimal_sample": True, "sample_count": 1},
            },
        )

    return {
        "prepare": {"status_code": prepared_response.status_code, "payload": prepared_payload},
        "approval": {"status_code": approval_response.status_code, "payload": approval_payload},
        "real_preflight": {"status_code": preflight_response.status_code, "payload": preflight_response.get_json()},
        "mock_execute": {"status_code": mock_execute_response.status_code, "payload": mock_execute_response.get_json()},
        "execute_real": {"status_code": execute_real_response.status_code, "payload": execute_real_response.get_json()},
    }


@contextmanager
def _patched_wish_executor(output_dir: Path):
    sys.path.insert(0, str(output_dir.parents[2] / "PathoFlow"))
    from execution import wish_executor

    original = wish_executor.execute_tool

    def fake_execute_tool(tool_id, slide_paths, model_args=None, username="pathoflow_demo", extra_slots=None):
        task_dir = output_dir / username / tool_id.replace("/", "_")
        task_dir.mkdir(parents=True, exist_ok=True)
        if tool_id == "1-foreground-segmentation":
            output_files = ["demo_1-foreground-segmentation_foreground.tif"]
            kind = "mask_or_labelmap"
        elif tool_id == "53-hover-next-mp":
            output_files = ["demo_53-hover-next-mp_nuclei_mask.tif"]
            kind = "mask_or_labelmap"
        elif tool_id == "77-Pathomics-pipeline-from-slides-nucleus":
            output_files = ["pathomics_features.pkl"]
            kind = "download"
        else:
            output_files = []
            kind = "download"
        for name in output_files:
            (task_dir / name).write_text("artifact", encoding="utf-8")
        return {
            "success": True,
            "task_id": tool_id.replace("/", "_"),
            "tool_id": tool_id,
            "result_dir": str(task_dir),
            "output_files": output_files,
            "execution_manifest": {
                "manifest_path": str(task_dir / "execution_manifest.json"),
                "success": True,
                "execution_state": "completed",
                "file_count": len(output_files),
                "files_by_kind": {kind: len(output_files)},
                "files": [{"path": name, "kind": kind, "filename": name} for name in output_files],
                "result_summary": {},
                "warnings": [],
            },
        }

    wish_executor.execute_tool = fake_execute_tool
    try:
        yield
    finally:
        wish_executor.execute_tool = original


def run_tme_reduced_execution_audit(pathoflow_root: Path, output_dir: Path) -> dict[str, Any]:
    query = "对肺癌H&E切片进行TILs/免疫浸润/TME代理分析。"
    planner_trace = _planner_trace(pathoflow_root, query)
    active_preparer = _active_preparer_trace(pathoflow_root, query)
    run_preparer = _run_preparer_trace(pathoflow_root, query)
    executable_flow = _executable_flow_trace(pathoflow_root)
    api_path = _flow_prepare_api_traces(pathoflow_root, output_dir, query)

    payload = {
        "generated_at": datetime.now().isoformat(),
        "query": query,
        "planner_trace": planner_trace,
        "active_preparer": active_preparer,
        "run_preparer": run_preparer,
        "executable_flow": executable_flow,
        "api_path": api_path,
        "summary": {
            "planner_primary_flow_id": planner_trace.get("primary", {}).get("flow_id"),
            "active_preparer_ready": active_preparer.get("ready"),
            "run_preparer_ready": run_preparer.get("ready"),
            "executable_flow_expanded": executable_flow.get("expanded"),
            "real_preflight_ready": ((api_path.get("real_preflight", {}).get("payload") or {}).get("data") or {}).get("ready"),
            "mock_execute_status": ((api_path.get("mock_execute", {}).get("payload") or {}).get("data") or {}).get("status"),
            "execute_real_status": ((api_path.get("execute_real", {}).get("payload") or {}).get("data") or {}).get("status"),
            "execute_real_step_count": ((api_path.get("execute_real", {}).get("payload") or {}).get("data") or {}).get("result", {}).get("step_count"),
        },
    }
    _write_json(output_dir / "tme_reduced_execution_audit.json", payload)
    lines = [
        "# TME Reduced Execution Audit",
        "",
        f"- Planner primary: `{payload['summary']['planner_primary_flow_id']}`",
        f"- Active preparer ready: `{payload['summary']['active_preparer_ready']}`",
        f"- run_preparer ready: `{payload['summary']['run_preparer_ready']}`",
        f"- executable_flow expanded: `{payload['summary']['executable_flow_expanded']}`",
        f"- real-preflight ready: `{payload['summary']['real_preflight_ready']}`",
        f"- mock execute status: `{payload['summary']['mock_execute_status']}`",
        f"- execute-real status: `{payload['summary']['execute_real_status']}`",
        "",
        "Reduced chain:",
    ]
    for flow_id in executable_flow.get("flow_ids", []):
        lines.append(f"- `{flow_id}`")
    (output_dir / "tme_reduced_execution_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload
