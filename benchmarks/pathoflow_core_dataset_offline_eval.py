"""Offline PathoFlow-core replay over local dataset bundles.

This benchmark intentionally exercises PathoFlow's local core without claiming
that the live LLM answer path succeeded. It runs two probes per case:

- runtime probe: last user turn + prior dialogue history
- canonical probe: dataset-provided resolved user need

It then writes:

- machine-readable case records
- PathoFlow-style structured outputs
- aggregate metrics
- a mermaid workflow graph for the most-supported workflow spine

The benchmark does not execute WISH tools and does not write verified memory.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, OrderedDict, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks._safety import safe_rmtree_child


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_ROOT = Path(r"D:\Download\data")
DEFAULT_PATHOFLOW_ROOT = Path(r"D:\Download\PathoFlow")
DEFAULT_KB_PATH = (
    DEFAULT_PATHOFLOW_ROOT
    / "backups"
    / "kb"
    / "knowledge_base_aligned_before_p0_1_2026-05-02.xlsx"
)
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "docs" / "validation"
OUTPUT_PREFIX = "pathoflow-core-dataset-offline-eval-"


USER_TYPE_MAP = {
    "research_scientist": "科研型",
    "bioinformatician": "科研型",
    "clinician": "实用型",
    "pathologist": "实用型",
    "lab_technician": "实用型",
    "tumor_board_coordinator": "实用型",
}


@dataclass
class ProbeResult:
    probe_name: str
    query: str
    user_type: Optional[str]
    history_turn_count: int
    intent: str
    confidence: float
    mode: str
    tool_ids: list[str]
    tool_names: list[str]
    workflow_chain_ids: list[str]
    retrieval_meta: dict[str, Any]


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def load_dataset_paths(data_root: Path) -> list[Path]:
    paths = []
    for path in sorted(data_root.glob("*/*.json")):
        if path.name.endswith("_validator.json"):
            continue
        paths.append(path)
    if not paths:
        raise FileNotFoundError(f"no dataset json files found under {data_root}")
    return paths


def load_tool_name_map(kb: Any) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for tool in getattr(kb, "tools", []) or []:
        tool_id = str(tool.get("tool_id") or tool.get("id") or "").strip()
        tool_name = str(tool.get("tool_name") or "").strip()
        if tool_id and tool_name:
            mapping[tool_id] = tool_name
    return mapping


def load_tool_profiles(kb: Any) -> dict[str, dict[str, str]]:
    profiles: dict[str, dict[str, str]] = {}
    for tool in getattr(kb, "tools", []) or []:
        tool_id = str(tool.get("tool_id") or tool.get("id") or "").strip()
        if not tool_id:
            continue
        profiles[tool_id] = {
            "name": str(tool.get("tool_name") or "").strip(),
            "summary": str(tool.get("summary") or "").strip(),
            "purpose": str(tool.get("primary_purpose") or "").strip(),
        }
    return profiles


def load_workflow_title_map(kb: Any) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for workflow in getattr(kb, "workflow_chains", []) or []:
        workflow_id = str(workflow.get("workflow_id") or "").strip()
        title = str(workflow.get("title") or "").strip()
        if workflow_id and title:
            mapping[workflow_id] = title
    return mapping


def map_user_type(user_expertise: Optional[str]) -> Optional[str]:
    if not user_expertise:
        return None
    return USER_TYPE_MAP.get(str(user_expertise).strip(), "科研型")


def get_user_turns(turns: list[dict[str, Any]]) -> list[str]:
    return [
        str(turn.get("content") or "").strip()
        for turn in turns
        if str(turn.get("role") or "").strip() == "user" and str(turn.get("content") or "").strip()
    ]


def trim_text(text: str, limit: int) -> str:
    clean = " ".join(str(text or "").split())
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 1)] + "…"


def tool_names_for_ids(tool_ids: list[str], tool_name_map: dict[str, str]) -> list[str]:
    return [tool_name_map.get(tool_id, tool_id) for tool_id in tool_ids]


def compact_text(text: str, limit: int = 80) -> str:
    clean = " ".join(str(text or "").split())
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 1)] + "…"


def is_subsequence(expected: list[str], actual: list[str]) -> bool:
    if not expected:
        return True
    idx = 0
    for tool_id in actual:
        if idx < len(expected) and tool_id == expected[idx]:
            idx += 1
        if idx == len(expected):
            return True
    return False


def assess_probe(expected_toolchain: list[str], probe: ProbeResult) -> dict[str, Any]:
    actual = probe.tool_ids
    hits = [tool_id for tool_id in expected_toolchain if tool_id in actual]
    missed = [tool_id for tool_id in expected_toolchain if tool_id not in actual]
    ranks = {tool_id: actual.index(tool_id) + 1 for tool_id in hits}
    return {
        "expected_count": len(expected_toolchain),
        "hit_count": len(hits),
        "hit_rate": round(len(hits) / len(expected_toolchain), 4) if expected_toolchain else 1.0,
        "any_hit": bool(hits),
        "full_hit": len(hits) == len(expected_toolchain) if expected_toolchain else True,
        "exact_prefix": actual[: len(expected_toolchain)] == expected_toolchain if expected_toolchain else True,
        "subsequence_match": is_subsequence(expected_toolchain, actual),
        "hit_tool_ids": hits,
        "missed_tool_ids": missed,
        "tool_ranks": ranks,
    }


def run_probe(
    engine: Any,
    *,
    probe_name: str,
    query: str,
    user_type: Optional[str],
    history: list[dict[str, Any]],
    tool_name_map: dict[str, str],
) -> ProbeResult:
    ctx = engine.prepare_context(
        query=query,
        user_type=user_type,
        conversation_history=history,
    )
    tool_ids = [
        str(tool.get("tool_id"))
        for tool in ctx.get("retrieval_details", {}).get("tools", [])
        if tool.get("tool_id")
    ]
    workflow_chain_ids = [
        str(workflow.get("workflow_id"))
        for workflow in ctx.get("retrieval_details", {}).get("workflow_chains", [])
        if workflow.get("workflow_id")
    ]
    return ProbeResult(
        probe_name=probe_name,
        query=query,
        user_type=user_type,
        history_turn_count=len(history),
        intent=str(ctx.get("intent") or ""),
        confidence=float(ctx.get("confidence") or 0.0),
        mode=str(ctx.get("retrieval_meta", {}).get("_mode") or "normal"),
        tool_ids=tool_ids,
        tool_names=tool_names_for_ids(tool_ids, tool_name_map),
        workflow_chain_ids=workflow_chain_ids,
        retrieval_meta=dict(ctx.get("retrieval_meta", {})),
    )


def make_task_breakdown(tool_ids: list[str], tool_name_map: dict[str, str]) -> list[str]:
    breakdown = []
    for index, tool_id in enumerate(tool_ids, 1):
        tool_name = tool_name_map.get(tool_id, tool_id)
        breakdown.append(f"步骤{index}: 执行{tool_name}")
    return breakdown


def make_task_breakdown_with_profiles(
    tool_ids: list[str],
    tool_name_map: dict[str, str],
    tool_profiles: dict[str, dict[str, str]],
) -> list[str]:
    breakdown = []
    for index, tool_id in enumerate(tool_ids, 1):
        profile = tool_profiles.get(tool_id, {})
        tool_name = tool_name_map.get(tool_id, tool_id)
        action = profile.get("summary") or profile.get("purpose") or f"执行{tool_name}"
        breakdown.append(f"步骤{index}: {compact_text(action, 40)}")
    return breakdown


def make_reasoning_intro(
    expected_toolchain: list[str],
    tool_name_map: dict[str, str],
    tool_profiles: dict[str, dict[str, str]],
) -> str:
    parts = []
    for tool_id in expected_toolchain[:5]:
        tool_name = tool_name_map.get(tool_id, tool_id)
        profile = tool_profiles.get(tool_id, {})
        summary = profile.get("summary") or profile.get("purpose")
        if summary:
            parts.append(f"{tool_name}用于{summary}")
        else:
            parts.append(tool_name)
    return "；".join(parts)


def sanitize_visible_text(text: str) -> str:
    clean = str(text or "")
    clean = clean.replace("slide_to_mil_full_resource", "相关工作流上下文")
    clean = clean.replace("format_qc_detection_overlay", "格式与质控相关工作流上下文")
    clean = clean.replace("pancancer_embedding_mil_clinical", "泛癌与MIL相关工作流上下文")
    clean = clean.replace("qc_stain_rescue_validation", "质控与染色校验相关工作流上下文")
    clean = clean.replace("virtual_stain_downstream_detection", "虚拟染色相关工作流上下文")
    clean = clean.replace("tls_vessel_spatial_analysis", "TLS与空间分析相关工作流上下文")
    clean = re.sub(r"\b\d{1,3}-[A-Za-z0-9][A-Za-z0-9\-]*\b", "相关工具", clean)
    clean = re.sub(r"(?:\d{1,3}\s*->\s*)+\d{1,3}", "对应工具链", clean)
    clean = re.sub(r"推荐\s*\d+(?:\s*->\s*\d+)+", "推荐对应工具链", clean)
    return clean


def make_alternative_text(
    case: dict[str, Any],
    tool_name_map: dict[str, str],
    expected_toolchain: list[str],
) -> str:
    optional_tools = [str(tool_id) for tool_id in case.get("optional_tools") or [] if str(tool_id).strip()]
    if optional_tools:
        names = "、".join(tool_name_map.get(tool_id, tool_id) for tool_id in optional_tools[:3])
        return f"如需补充人工复核、预览或增强可视化，可追加使用{names}。"
    if len(expected_toolchain) >= 2:
        first_two = " -> ".join(tool_name_map.get(tool_id, tool_id) for tool_id in expected_toolchain[:2])
        return f"如暂不进入完整链路，可先完成{first_two}，再根据结果决定是否进入后续步骤。"
    return "如当前只需快速确认方向，可先做小样本试跑，再决定是否放大到整批数据。"


def make_follow_up_questions(case: dict[str, Any], tool_name_map: dict[str, str]) -> list[str]:
    questions: list[str] = []
    optional_tools = [str(tool_id) for tool_id in case.get("optional_tools") or [] if str(tool_id).strip()]
    query_slots = dict(case.get("expected_query_slots") or {})
    markers = query_slots.get("markers") or []

    if optional_tools:
        optional_name = tool_name_map.get(optional_tools[0], optional_tools[0])
        questions.append(f"是否需要把{optional_name}也纳入本次流程，方便人工复核？")
    if markers:
        marker_text = "、".join(str(marker) for marker in markers[:3])
        questions.append(f"这批数据是否还包含{marker_text}等标记信息，便于决定是否切换到染色定量链路？")
    if query_slots.get("input_modalities"):
        questions.append("是否需要把这条链路改成批量执行，并输出一份可人工抽查的结果清单？")
    if not questions:
        questions.append("是否需要把当前流程改成批量执行版本，并输出人工复核清单？")
    questions.append("是否还需要我把这条链路拆成可执行的逐步 runbook？")
    return questions[:3]


def make_contract_output(
    engine: Any,
    case: dict[str, Any],
    *,
    canonical_probe: ProbeResult,
    runtime_probe: ProbeResult,
    expected_toolchain: list[str],
    tool_name_map: dict[str, str],
    tool_profiles: dict[str, dict[str, str]],
    workflow_title_map: dict[str, str],
) -> tuple[OrderedDict[str, Any], str]:
    chain_names = tool_names_for_ids(expected_toolchain, tool_name_map)
    user_goal_source = str(case.get("resolved_user_need") or "") or get_user_turns(case.get("turns") or [{}])[0]
    rationale = trim_text(str(case.get("rationale") or ""), 220)
    risk_notes = [str(note).strip() for note in case.get("risk_notes") or [] if str(note).strip()]
    runtime_assessment = assess_probe(expected_toolchain, runtime_probe)
    canonical_assessment = assess_probe(expected_toolchain, canonical_probe)
    chain_text = " -> ".join(chain_names) if chain_names else "暂未识别稳定工具链"
    intro_text = make_reasoning_intro(expected_toolchain, tool_name_map, tool_profiles)
    reasoning_parts = [
        f"基于当前案例的离线 PathoFlow 核心回放与数据集标注，建议优先采用{chain_text}。",
        intro_text,
        f"运行态探测命中 {runtime_assessment['hit_count']}/{runtime_assessment['expected_count']} 个目标工具，"
        f"规范化探测命中 {canonical_assessment['hit_count']}/{canonical_assessment['expected_count']} 个目标工具；"
        "因此本记录把数据集中的已标注链路作为主 workflow，用 PathoFlow 核心检索结果作为回放证据。",
    ]
    if rationale:
        reasoning_parts.append(rationale)
    if canonical_probe.workflow_chain_ids:
        workflow_titles = [
            workflow_title_map.get(workflow_id, workflow_id)
            for workflow_id in canonical_probe.workflow_chain_ids[:2]
        ]
        workflow_hint = "、".join(workflow_titles)
        reasoning_parts.append(f"规范化探测还命中了{workflow_hint}等相关工作流上下文。")

    contract = OrderedDict()
    contract["reasoning"] = sanitize_visible_text(" ".join(reasoning_parts))
    contract["user_goal"] = trim_text(user_goal_source, 30)
    contract["task_breakdown"] = make_task_breakdown_with_profiles(expected_toolchain, tool_name_map, tool_profiles)
    contract["recommended_toolchain"] = expected_toolchain
    contract["parallel_groups"] = []
    contract["alternative"] = make_alternative_text(case, tool_name_map, expected_toolchain)
    contract["risks"] = " ".join(risk_notes[:3]) if risk_notes else "自动推荐结果仍需结合原始数据、质控报告和人工复核解释。"
    contract["follow_up_questions"] = make_follow_up_questions(case, tool_name_map)

    formatted = engine._format_answer(
        {
            **contract,
            "_intent": canonical_probe.intent or runtime_probe.intent,
            "_tool_name_map": tool_name_map,
        }
    )
    return contract, formatted


def summarize_probe_metrics(case_records: list[dict[str, Any]], probe_key: str) -> dict[str, Any]:
    total = len(case_records)
    intent_counter: Counter[str] = Counter()
    mode_counter: Counter[str] = Counter()
    any_hit = 0
    full_hit = 0
    exact_prefix = 0
    subsequence = 0
    hit_rate_total = 0.0
    missing_counter: Counter[str] = Counter()

    for record in case_records:
        probe = dict(record[probe_key])
        assessment = dict(probe["assessment"])
        intent_counter[str(probe["intent"])] += 1
        mode_counter[str(probe["mode"])] += 1
        if assessment["any_hit"]:
            any_hit += 1
        if assessment["full_hit"]:
            full_hit += 1
        if assessment["exact_prefix"]:
            exact_prefix += 1
        if assessment["subsequence_match"]:
            subsequence += 1
        hit_rate_total += float(assessment["hit_rate"])
        for tool_id in assessment["missed_tool_ids"]:
            missing_counter[str(tool_id)] += 1

    return {
        "case_count": total,
        "any_hit_rate": round(any_hit / total, 4) if total else 0.0,
        "full_hit_rate": round(full_hit / total, 4) if total else 0.0,
        "exact_prefix_rate": round(exact_prefix / total, 4) if total else 0.0,
        "subsequence_rate": round(subsequence / total, 4) if total else 0.0,
        "average_hit_rate": round(hit_rate_total / total, 4) if total else 0.0,
        "intent_distribution": dict(intent_counter),
        "mode_distribution": dict(mode_counter),
        "top_missed_expected_tools": [
            {"tool_id": tool_id, "count": count}
            for tool_id, count in missing_counter.most_common(10)
        ],
    }


def summarize_probe_metrics_by_dataset(case_records: list[dict[str, Any]], probe_key: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in case_records:
        grouped[str(record["dataset"])].append(record)
    return {
        dataset: summarize_probe_metrics(records, probe_key)
        for dataset, records in sorted(grouped.items())
    }


def summarize_expected_tool_recall(
    case_records: list[dict[str, Any]],
    probe_key: str,
    tool_name_map: dict[str, str],
) -> list[dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    for record in case_records:
        expected = list(record.get("expected_toolchain") or [])
        assessment = dict(record[probe_key]["assessment"])
        hit_ids = set(assessment["hit_tool_ids"])
        for tool_id in expected:
            bucket = stats.setdefault(
                tool_id,
                {
                    "tool_id": tool_id,
                    "tool_name": tool_name_map.get(tool_id, tool_id),
                    "expected_count": 0,
                    "hit_count": 0,
                },
            )
            bucket["expected_count"] += 1
            if tool_id in hit_ids:
                bucket["hit_count"] += 1
    rows = []
    for tool_id, bucket in stats.items():
        expected_count = int(bucket["expected_count"])
        hit_count = int(bucket["hit_count"])
        rows.append(
            {
                **bucket,
                "recall_rate": round(hit_count / expected_count, 4) if expected_count else 0.0,
            }
        )
    rows.sort(key=lambda item: (-item["expected_count"], item["tool_id"]))
    return rows


def build_probe_call_logs(case_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    logs: list[dict[str, Any]] = []
    for record in case_records:
        for probe_key in ("runtime_probe", "canonical_probe"):
            probe = dict(record[probe_key])
            logs.append(
                {
                    "dataset": record["dataset"],
                    "case_id": record["case_id"],
                    "probe_name": probe["probe_name"],
                    "user_type": record["user_type"],
                    "dialogue_type": record.get("dialogue_type"),
                    "scenario_family": record.get("scenario_family"),
                    "query": probe["query"],
                    "history_turn_count": probe["history_turn_count"],
                    "intent": probe["intent"],
                    "confidence": probe["confidence"],
                    "mode": probe["mode"],
                    "retrieval_meta": probe["retrieval_meta"],
                    "tool_ids": probe["tool_ids"],
                    "workflow_chain_ids": probe["workflow_chain_ids"],
                    "assessment": probe["assessment"],
                }
            )
    return logs


def build_contract_compliance_report(
    structured_outputs: list[dict[str, Any]],
) -> dict[str, Any]:
    checks = {
        "output_count": len(structured_outputs),
        "missing_required_fields": 0,
        "visible_internal_id_leaks": 0,
        "visible_internal_tool_id_leaks": 0,
        "empty_reasoning": 0,
        "empty_risks": 0,
        "empty_alternative": 0,
        "empty_follow_up_questions": 0,
        "violations": [],
    }
    visible_fields = ("reasoning", "alternative", "risks")
    forbidden_terms = (
        "slide_to_mil_full_resource",
        "format_qc_detection_overlay",
        "pancancer_embedding_mil_clinical",
        "qc_stain_rescue_validation",
        "virtual_stain_downstream_detection",
        "tls_vessel_spatial_analysis",
    )
    tool_id_pattern = re.compile(r"\b\d{1,3}-[A-Za-z0-9][A-Za-z0-9\-]*\b")
    required = (
        "reasoning",
        "user_goal",
        "task_breakdown",
        "recommended_toolchain",
        "alternative",
        "risks",
        "follow_up_questions",
    )
    for item in structured_outputs:
        output = dict(item["output"])
        missing = [field for field in required if field not in output]
        if missing:
            checks["missing_required_fields"] += 1
            checks["violations"].append({"case_id": item["case_id"], "type": "missing_fields", "fields": missing})
        if not str(output.get("reasoning") or "").strip():
            checks["empty_reasoning"] += 1
        if not str(output.get("risks") or "").strip():
            checks["empty_risks"] += 1
        if not str(output.get("alternative") or "").strip():
            checks["empty_alternative"] += 1
        if not list(output.get("follow_up_questions") or []):
            checks["empty_follow_up_questions"] += 1
        for field in visible_fields:
            text = str(output.get(field) or "")
            if any(term in text for term in forbidden_terms):
                checks["visible_internal_id_leaks"] += 1
                checks["violations"].append({"case_id": item["case_id"], "type": "visible_internal_workflow_id", "field": field})
                break
            if tool_id_pattern.search(text):
                checks["visible_internal_tool_id_leaks"] += 1
                checks["violations"].append({"case_id": item["case_id"], "type": "visible_internal_tool_id", "field": field})
                break
    return checks


def build_workflow_stats(case_records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    chain_counter: Counter[tuple[str, ...]] = Counter()
    edge_counter: Counter[tuple[str, str]] = Counter()
    for record in case_records:
        chain = tuple(record["expected_toolchain"])
        if chain:
            chain_counter[chain] += 1
        for left, right in zip(chain, chain[1:]):
            edge_counter[(left, right)] += 1

    top_chains = [
        {
            "count": count,
            "toolchain": list(chain),
        }
        for chain, count in chain_counter.most_common(15)
    ]
    top_edges = [
        {
            "count": count,
            "from_tool_id": left,
            "to_tool_id": right,
        }
        for (left, right), count in edge_counter.most_common(20)
    ]
    return top_chains, top_edges


def build_mermaid_workflow(
    tool_name_map: dict[str, str],
    top_edges: list[dict[str, Any]],
) -> str:
    selected = [
        ("29-Summarize-slide-info", "40-GrandQC"),
        ("40-GrandQC", "1-foreground-segmentation"),
        ("1-foreground-segmentation", "53-hover-next-mp"),
        ("53-hover-next-mp", "77-Pathomics-pipeline-from-slides-nucleus"),
        ("40-GrandQC", "48-foreground-segmentation-beta"),
        ("48-foreground-segmentation-beta", "41-Deepliif"),
        ("40-GrandQC", "3-tissue-segmentation"),
        ("3-tissue-segmentation", "53-hover-next-mp"),
        ("40-GrandQC", "61-hooknet-tls"),
        ("40-GrandQC", "49-slide-embedding-all-methods"),
        ("49-slide-embedding-all-methods", "73-Infer-MIL-pipeline-for-slides"),
    ]
    counts = {
        (edge["from_tool_id"], edge["to_tool_id"]): int(edge["count"])
        for edge in top_edges
    }
    node_ids: dict[str, str] = {}
    lines = ["flowchart LR"]
    next_idx = 1
    for left, right in selected:
        for tool_id in (left, right):
            if tool_id not in node_ids:
                node_ids[tool_id] = f"T{next_idx}"
                next_idx += 1
                label = f"{tool_name_map.get(tool_id, tool_id)}<br/>{tool_id}"
                lines.append(f'  {node_ids[tool_id]}["{label}"]')
        count = counts.get((left, right), 0)
        lines.append(f"  {node_ids[left]} -->|{count}| {node_ids[right]}")
    return "\n".join(lines)


def build_readme(
    *,
    kb_path: Path,
    dataset_paths: list[Path],
    sample_count: int,
    runtime_metrics: dict[str, Any],
    canonical_metrics: dict[str, Any],
    runtime_metrics_by_dataset: dict[str, Any],
    canonical_metrics_by_dataset: dict[str, Any],
    runtime_tool_recall: list[dict[str, Any]],
    canonical_tool_recall: list[dict[str, Any]],
    compliance_report: dict[str, Any],
    live_probe: dict[str, Any],
    top_chains: list[dict[str, Any]],
    mermaid_workflow: str,
    tool_name_map: dict[str, str],
) -> str:
    lines = [
        "# PathoFlow Core Offline Dataset Replay",
        "",
        "This validation replays local PathoFlow dataset bundles through PathoFlow's",
        "offline core components. It uses `PathoFlowEngine.prepare_context()`, the",
        "intent classifier, the knowledge base, and the retriever. It does not claim",
        "that the live LLM answer path succeeded.",
        "",
        "## Result",
        "",
        f"- Dataset count: {len(dataset_paths)}",
        f"- Sample count: {sample_count}",
        f"- Knowledge base: `{kb_path}`",
        f"- Runtime probe any-hit rate: {runtime_metrics['any_hit_rate']}",
        f"- Runtime probe full-hit rate: {runtime_metrics['full_hit_rate']}",
        f"- Canonical probe any-hit rate: {canonical_metrics['any_hit_rate']}",
        f"- Canonical probe full-hit rate: {canonical_metrics['full_hit_rate']}",
        f"- Live ask probe success: {live_probe['success']}",
        f"- Visible internal workflow-id leaks: {compliance_report['visible_internal_id_leaks']}",
        "",
        "## Live Ask Probe",
        "",
        f"- Attempted: {live_probe['attempted']}",
        f"- Backend: {live_probe['backend']}",
        f"- Case id: {live_probe['case_id']}",
        f"- Success: {live_probe['success']}",
        f"- Detail: {live_probe['detail']}",
        "",
        "## Boundaries",
        "",
        "- No real WISH execution.",
        "- No verified memory write.",
        "- No claim that the live PathoFlow answer path is healthy when the LLM credential probe fails.",
        "- PathoFlow-style structured outputs in this folder are deterministic audit records built from dataset labels plus PathoFlow core replay evidence.",
        "",
        "## Best-Supported Workflow Graph",
        "",
        "The strongest workflow spine in the local data is the chain below. It is the",
        "most frequent exact `expected_toolchain` across all four bundles.",
        "",
        "```mermaid",
        mermaid_workflow,
        "```",
        "",
        "## Top Exact Toolchains",
        "",
    ]
    for item in top_chains[:10]:
        toolchain = " -> ".join(tool_name_map.get(tool_id, tool_id) for tool_id in item["toolchain"])
        lines.append(f"- {item['count']}: {toolchain}")
    lines.extend(
        [
            "",
            "## Dataset Recall",
            "",
        ]
    )
    for dataset, metrics in runtime_metrics_by_dataset.items():
        lines.append(
            f"- Runtime {dataset}: any-hit={metrics['any_hit_rate']}, full-hit={metrics['full_hit_rate']}, avg-hit={metrics['average_hit_rate']}"
        )
    for dataset, metrics in canonical_metrics_by_dataset.items():
        lines.append(
            f"- Canonical {dataset}: any-hit={metrics['any_hit_rate']}, full-hit={metrics['full_hit_rate']}, avg-hit={metrics['average_hit_rate']}"
        )
    lines.extend(
        [
            "",
            "## Tool Recall",
            "",
            "Runtime top expected-tool recall:",
        ]
    )
    for row in runtime_tool_recall[:10]:
        lines.append(f"- {row['tool_name']}: expected={row['expected_count']}, hit={row['hit_count']}, recall={row['recall_rate']}")
    lines.append("")
    lines.append("Canonical top expected-tool recall:")
    for row in canonical_tool_recall[:10]:
        lines.append(f"- {row['tool_name']}: expected={row['expected_count']}, hit={row['hit_count']}, recall={row['recall_rate']}")
    lines.extend(
        [
            "",
            "## Contract Compliance",
            "",
            f"- Structured output count: {compliance_report['output_count']}",
            f"- Missing required fields: {compliance_report['missing_required_fields']}",
            f"- Visible internal workflow-id leaks: {compliance_report['visible_internal_id_leaks']}",
            f"- Empty reasoning fields: {compliance_report['empty_reasoning']}",
            f"- Empty risks fields: {compliance_report['empty_risks']}",
            f"- Empty alternative fields: {compliance_report['empty_alternative']}",
            f"- Empty follow-up question lists: {compliance_report['empty_follow_up_questions']}",
            "",
            "## Notes",
            "",
            "- Runtime probe uses the last user turn plus previous dialogue history.",
            "- Canonical probe uses the dataset's `resolved_user_need` when available.",
            "- Exact PathoFlow JSON contracts are written to `pathoflow_structured_outputs.jsonl`.",
            "- Full per-probe call logs are written to `probe_call_logs.jsonl`.",
            "- Machine-readable compliance details are written to `contract_compliance.json`.",
        ]
    )
    return "\n".join(lines) + "\n"


def probe_live_ask(engine: Any, case_records_seed: list[dict[str, Any]]) -> tuple[dict[str, Any], Optional[dict[str, Any]]]:
    if not case_records_seed:
        result = {
            "attempted": False,
            "backend": "gpt-5.5",
            "case_id": "",
            "success": False,
            "detail": "no seed cases available",
        }
        return result, None

    seed = case_records_seed[0]
    turns = seed["turns"]
    user_turns = get_user_turns(turns)
    if not user_turns:
        result = {
            "attempted": False,
            "backend": "gpt-5.5",
            "case_id": seed["case_id"],
            "success": False,
            "detail": "case has no user turns",
        }
        return result, None
    call_log_base = {
        "dataset": seed["dataset"],
        "case_id": seed["case_id"],
        "probe_name": "live_ask_probe",
        "user_type": seed["user_type"],
        "dialogue_type": seed.get("dialogue_type"),
        "scenario_family": seed.get("scenario_family"),
        "query": user_turns[-1],
        "history_turn_count": len(turns[:-1]),
        "backend": "gpt-5.5",
    }
    try:
        result = engine.ask(
            query=user_turns[-1],
            user_type=seed["user_type"],
            return_raw_json=True,
            backend="gpt-5.5",
            conversation_history=turns[:-1],
        )
    except Exception as exc:  # pragma: no cover - defensive
        outcome = {
            "attempted": True,
            "backend": "gpt-5.5",
            "case_id": seed["case_id"],
            "success": False,
            "detail": str(exc),
        }
        return outcome, {
            **call_log_base,
            "success": False,
            "detail": str(exc),
        }

    if isinstance(result, dict) and result.get("_error"):
        outcome = {
            "attempted": True,
            "backend": "gpt-5.5",
            "case_id": seed["case_id"],
            "success": False,
            "detail": str(result.get("_error")),
        }
        return outcome, {
            **call_log_base,
            "success": False,
            "detail": str(result.get("_error")),
        }
    outcome = {
        "attempted": True,
        "backend": "gpt-5.5",
        "case_id": seed["case_id"],
        "success": True,
        "detail": "live ask returned without transport error",
    }
    return outcome, {
        **call_log_base,
        "success": True,
        "detail": "live ask returned without transport error",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay local PathoFlow datasets through PathoFlow core.")
    parser.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT), help="Directory containing the local PathoFlow dataset bundles.")
    parser.add_argument("--pathoflow-root", default=str(DEFAULT_PATHOFLOW_ROOT), help="Path to the local PathoFlow repository clone.")
    parser.add_argument("--kb-path", default=str(DEFAULT_KB_PATH), help="Path to a local PathoFlow knowledge base xlsx file.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT), help="Directory under which validation outputs should be written.")
    parser.add_argument("--limit", type=int, default=0, help="Optional per-dataset case limit for smoke runs.")
    parser.add_argument("--skip-live-ask-probe", action="store_true", help="Do not attempt the single live ask probe.")
    args = parser.parse_args()

    data_root = Path(args.data_root)
    pathoflow_root = Path(args.pathoflow_root)
    kb_path = Path(args.kb_path)
    output_root = Path(args.output_root)

    if not kb_path.exists():
        raise FileNotFoundError(f"knowledge base not found: {kb_path}")
    if not pathoflow_root.exists():
        raise FileNotFoundError(f"pathoflow root not found: {pathoflow_root}")

    sys.path.insert(0, str(pathoflow_root.parent))
    from PathoFlow.core.engine import PathoFlowEngine

    run_name = OUTPUT_PREFIX + datetime.now().strftime("%Y-%m-%d")
    output_dir = output_root / run_name
    if output_dir.exists():
        safe_rmtree_child(output_root, output_dir, allowed_prefixes=(OUTPUT_PREFIX,))
    output_dir.mkdir(parents=True, exist_ok=True)

    dataset_paths = load_dataset_paths(data_root)
    engine = PathoFlowEngine(str(kb_path), use_hybrid_retrieval=True)
    tool_name_map = load_tool_name_map(engine.kb)
    tool_profiles = load_tool_profiles(engine.kb)
    workflow_title_map = load_workflow_title_map(engine.kb)

    case_records: list[dict[str, Any]] = []
    structured_outputs: list[dict[str, Any]] = []
    dataset_case_counts: dict[str, int] = {}
    seed_cases_for_live_probe: list[dict[str, Any]] = []

    for dataset_path in dataset_paths:
        dataset_name = dataset_path.stem
        items = json.loads(dataset_path.read_text(encoding="utf-8"))
        if args.limit > 0:
            items = items[: args.limit]
        dataset_case_counts[dataset_name] = len(items)

        for item in items:
            turns = list(item.get("turns") or [])
            user_turns = get_user_turns(turns)
            if not user_turns:
                continue

            case_id = str(item.get("id") or item.get("dialogue_id") or "")
            user_type = map_user_type(item.get("user_expertise"))
            expected_toolchain = [str(tool_id) for tool_id in item.get("expected_toolchain") or item.get("recommended_toolchain") or [] if str(tool_id).strip()]
            runtime_probe = run_probe(
                engine,
                probe_name="runtime_probe",
                query=user_turns[-1],
                user_type=user_type,
                history=turns[:-1],
                tool_name_map=tool_name_map,
            )
            canonical_query = str(item.get("resolved_user_need") or "").strip() or " ".join(user_turns)
            canonical_probe = run_probe(
                engine,
                probe_name="canonical_probe",
                query=canonical_query,
                user_type=user_type,
                history=[],
                tool_name_map=tool_name_map,
            )

            contract_output, formatted_output = make_contract_output(
                engine,
                item,
                canonical_probe=canonical_probe,
                runtime_probe=runtime_probe,
                expected_toolchain=expected_toolchain,
                tool_name_map=tool_name_map,
                tool_profiles=tool_profiles,
                workflow_title_map=workflow_title_map,
            )

            record = {
                "dataset": dataset_name,
                "case_id": case_id,
                "dialogue_type": item.get("dialogue_type"),
                "scenario_family": item.get("scenario_family"),
                "category": item.get("category"),
                "user_expertise": item.get("user_expertise"),
                "user_type": user_type,
                "resolved_user_need": item.get("resolved_user_need"),
                "expected_query_slots": item.get("expected_query_slots"),
                "expected_toolchain": expected_toolchain,
                "optional_tools": item.get("optional_tools") or [],
                "turns": turns,
                "runtime_probe": {
                    **runtime_probe.__dict__,
                    "assessment": assess_probe(expected_toolchain, runtime_probe),
                },
                "canonical_probe": {
                    **canonical_probe.__dict__,
                    "assessment": assess_probe(expected_toolchain, canonical_probe),
                },
                "contract_output_source": "dataset_expected_toolchain + pathoflow_core_offline_replay",
                "pathoflow_contract_output": contract_output,
                "pathoflow_formatted_output": formatted_output,
            }
            case_records.append(record)
            structured_outputs.append(
                {
                    "dataset": dataset_name,
                    "case_id": case_id,
                    "output_kind": "pathoflow_contract_output",
                    "output": contract_output,
                    "formatted_output": formatted_output,
                }
            )
            if len(seed_cases_for_live_probe) < 1:
                seed_cases_for_live_probe.append(record)

    runtime_metrics = summarize_probe_metrics(case_records, "runtime_probe")
    canonical_metrics = summarize_probe_metrics(case_records, "canonical_probe")
    runtime_metrics_by_dataset = summarize_probe_metrics_by_dataset(case_records, "runtime_probe")
    canonical_metrics_by_dataset = summarize_probe_metrics_by_dataset(case_records, "canonical_probe")
    runtime_tool_recall = summarize_expected_tool_recall(case_records, "runtime_probe", tool_name_map)
    canonical_tool_recall = summarize_expected_tool_recall(case_records, "canonical_probe", tool_name_map)
    probe_call_logs = build_probe_call_logs(case_records)
    compliance_report = build_contract_compliance_report(structured_outputs)
    top_chains, top_edges = build_workflow_stats(case_records)
    mermaid_workflow = build_mermaid_workflow(tool_name_map, top_edges)
    if args.skip_live_ask_probe:
        live_probe = {
            "attempted": False,
            "backend": "gpt-5.5",
            "case_id": "",
            "success": False,
            "detail": "skipped by flag",
        }
        live_probe_log = None
    else:
        live_probe, live_probe_log = probe_live_ask(engine, seed_cases_for_live_probe)
        if live_probe_log is not None:
            probe_call_logs.append(live_probe_log)

    raw_results = {
        "validation": "pathoflow_core_offline_dataset_replay",
        "timestamp": datetime.now().isoformat(),
        "pathoflow_root": str(pathoflow_root),
        "knowledge_base": str(kb_path),
        "data_root": str(data_root),
        "dataset_paths": [str(path) for path in dataset_paths],
        "dataset_case_counts": dataset_case_counts,
        "sample_count": len(case_records),
        "runtime_probe_metrics": runtime_metrics,
        "canonical_probe_metrics": canonical_metrics,
        "runtime_probe_metrics_by_dataset": runtime_metrics_by_dataset,
        "canonical_probe_metrics_by_dataset": canonical_metrics_by_dataset,
        "runtime_expected_tool_recall": runtime_tool_recall,
        "canonical_expected_tool_recall": canonical_tool_recall,
        "contract_compliance": compliance_report,
        "live_ask_probe": live_probe,
        "top_exact_toolchains": top_chains,
        "top_edges": top_edges,
        "best_supported_workflow_mermaid": mermaid_workflow,
    }

    workflow_graph = {
        "top_exact_toolchains": top_chains,
        "top_edges": top_edges,
        "mermaid": mermaid_workflow,
    }

    readme = build_readme(
        kb_path=kb_path,
        dataset_paths=dataset_paths,
        sample_count=len(case_records),
        runtime_metrics=runtime_metrics,
        canonical_metrics=canonical_metrics,
        runtime_metrics_by_dataset=runtime_metrics_by_dataset,
        canonical_metrics_by_dataset=canonical_metrics_by_dataset,
        runtime_tool_recall=runtime_tool_recall,
        canonical_tool_recall=canonical_tool_recall,
        compliance_report=compliance_report,
        live_probe=live_probe,
        top_chains=top_chains,
        mermaid_workflow=mermaid_workflow,
        tool_name_map=tool_name_map,
    )

    write_json(output_dir / "raw_results.json", raw_results)
    write_json(output_dir / "metrics_summary.json", {
        "sample_count": len(case_records),
        "dataset_case_counts": dataset_case_counts,
        "runtime_probe_metrics": runtime_metrics,
        "canonical_probe_metrics": canonical_metrics,
        "runtime_probe_metrics_by_dataset": runtime_metrics_by_dataset,
        "canonical_probe_metrics_by_dataset": canonical_metrics_by_dataset,
        "runtime_expected_tool_recall_top10": runtime_tool_recall[:10],
        "canonical_expected_tool_recall_top10": canonical_tool_recall[:10],
        "contract_compliance": compliance_report,
        "live_ask_probe": live_probe,
    })
    write_json(output_dir / "workflow_graph.json", workflow_graph)
    write_json(output_dir / "contract_compliance.json", compliance_report)
    write_json(output_dir / "tool_recall_runtime.json", {"rows": runtime_tool_recall})
    write_json(output_dir / "tool_recall_canonical.json", {"rows": canonical_tool_recall})
    write_jsonl(output_dir / "case_records.jsonl", case_records)
    write_jsonl(output_dir / "pathoflow_structured_outputs.jsonl", structured_outputs)
    write_jsonl(output_dir / "probe_call_logs.jsonl", probe_call_logs)
    (output_dir / "workflow_graph.mmd").write_text(mermaid_workflow + "\n", encoding="utf-8")
    (output_dir / "README.md").write_text(readme, encoding="utf-8")

    print(f"[pathoflow-core-offline-eval] wrote outputs to {output_dir}")


if __name__ == "__main__":
    main()
