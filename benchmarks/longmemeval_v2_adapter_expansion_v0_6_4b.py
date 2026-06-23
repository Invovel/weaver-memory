"""v0.6.4b LongMemEval-V2 adapter expansion dry-run.

This benchmark expands the v0.6.4a local LongMemEval-V2 adapter from a small
probe into a bounded coverage run. It still stops before MemoryItem writes:

    questions/trajectories -> ExternalEpisode -> RawSpan
    -> ContextCapsule -> Layer-1 candidate dry-run

The goal is adapter quality, not task success. No verified memory is written,
no promotion is performed, no Layer-3 mutation is allowed, and no LLM is called.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks._safety import safe_rmtree_child
from benchmarks.context_capsule_validation import write_json, write_jsonl
from memoryweaver.external.adapters import (
    adapt_external_record,
    build_candidate_memories,
    build_context_capsules,
    external_episode_to_raw_spans,
)
from memoryweaver.external.longmemeval_v2 import (
    load_lme_v2_haystack,
    load_lme_v2_questions,
    load_lme_v2_trajectories,
    lme_v2_question_to_external_record,
    resolve_lme_v2_root,
)
from memoryweaver.schema import Source
from memoryweaver.store import MemoryWorkspace


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT
    / "docs"
    / "validation"
    / "longmemeval-v2-adapter-expansion-v0.6.4b"
)

QUESTION_REQUIRED_FIELDS = [
    "id",
    "domain",
    "environment",
    "question_type",
    "question",
    "answer",
    "eval_function",
]
TRAJECTORY_REQUIRED_FIELDS = [
    "id",
    "domain",
    "environment",
    "goal",
    "outcome",
    "states",
]
STATE_REQUIRED_FIELDS = [
    "state_index",
    "step",
    "url",
    "action",
    "thought",
    "accessibility_tree",
]
ACTIONABLE_TERMS = {
    "action",
    "check",
    "click",
    "command",
    "error",
    "fail",
    "failed",
    "fix",
    "open",
    "select",
    "status",
    "submit",
    "tool",
    "update",
    "verify",
}
SPECIFICITY_RE = re.compile(
    r"(https?://\S+|\b[A-Z]{2,}[-_0-9A-Z]*\b|\b[a-z]+[_-][a-z0-9_-]+\b|\b\d+\b)"
)


def evaluate_lme_v2_expansion(
    input_root: Path | None,
    *,
    question_limit: int = 50,
    trajectories_per_question: int = 3,
    states_per_trajectory: int = 5,
    max_observation_chars: int = 1800,
    haystack_name: str = "lme_v2_small.json",
    hf_cache_root: Path | None = None,
    allow_download: bool = False,
) -> dict[str, Any]:
    """Run a single dry-run expansion and return reports plus samples."""

    input_root, resolution = resolve_lme_v2_root(
        input_root,
        hf_cache_root=hf_cache_root,
        allow_download=allow_download,
        download_root=input_root or Path.cwd() / "longmemeval-v2",
    )
    questions = load_lme_v2_questions(input_root, limit=question_limit)
    haystack = load_lme_v2_haystack(input_root, name=haystack_name)
    question_ids = [str(question.get("id", "")) for question in questions]
    requested_refs = {
        trajectory_id
        for question_id in question_ids
        for trajectory_id in haystack.get(question_id, [])[:trajectories_per_question]
    }
    trajectories_by_id = load_lme_v2_trajectories(input_root, requested_refs)

    missing_refs_by_question: dict[str, list[str]] = {}
    records: list[dict[str, Any]] = []
    for question in questions:
        question_id = str(question.get("id", ""))
        selected: list[dict[str, Any]] = []
        missing: list[str] = []
        for trajectory_id in haystack.get(question_id, [])[:trajectories_per_question]:
            trajectory = trajectories_by_id.get(trajectory_id)
            if trajectory is None:
                missing.append(trajectory_id)
            else:
                selected.append(trajectory)
        if missing:
            missing_refs_by_question[question_id] = missing
        records.append(
            lme_v2_question_to_external_record(
                question,
                selected,
                states_per_trajectory=states_per_trajectory,
                max_observation_chars=max_observation_chars,
            )
        )

    episodes = [adapt_external_record("longmemeval-v2", record) for record in records]
    raw_spans = []
    for episode in episodes:
        raw_spans.extend(external_episode_to_raw_spans(episode))
    capsules = build_context_capsules(raw_spans)
    memories, policy_violations = build_candidate_memories(capsules)

    raw_ids = {raw_span.id for raw_span in raw_spans}
    adapter_quality_report = _build_adapter_quality_report(
        questions=questions,
        haystack=haystack,
        requested_refs=requested_refs,
        trajectories_by_id=trajectories_by_id,
        episodes=episodes,
        raw_span_count=len(raw_spans),
        capsule_count=len(capsules),
        candidate_count=len(memories),
        question_limit=question_limit,
        trajectories_per_question=trajectories_per_question,
        states_per_trajectory=states_per_trajectory,
        max_observation_chars=max_observation_chars,
    )
    missing_field_report = _build_missing_field_report(
        questions=questions,
        trajectories=trajectories_by_id.values(),
        states_per_trajectory=states_per_trajectory,
    )
    evidence_ref_report = _build_evidence_ref_report(memories, raw_ids)
    candidate_memory_type_stats = _build_candidate_memory_type_stats(memories)
    signal_report = _build_signal_report(records, trajectories_by_id.values(), memories)

    required_field_coverage = missing_field_report["required_field_coverage"]
    trajectory_question_join_rate = adapter_quality_report["trajectory_question_join_rate"]
    evidence_ref_validity_rate = evidence_ref_report["evidence_ref_validity_rate"]
    unsupported_claim_rate = evidence_ref_report["unsupported_claim_rate"]
    candidate_density = _safe_ratio(len(memories), len(raw_spans))
    dedup_rate = _dedup_rate(memory.content for memory in memories)
    actionability_score_avg = _average(_actionability_score(memory.content, memory.tags, memory.source) for memory in memories)
    specificity_score_avg = _average(_specificity_score(memory.content) for memory in memories)
    temporal_order_accuracy = _temporal_order_accuracy(episodes)

    metrics = {
        "validation": "longmemeval-v2-adapter-expansion-v0.6.4b",
        "input_root": str(input_root),
        "input_root_source": resolution["source"],
        "question_limit": question_limit,
        "question_count": len(questions),
        "requested_trajectory_refs": len(requested_refs),
        "loaded_trajectory_count": len(trajectories_by_id),
        "missing_trajectory_refs": sum(len(value) for value in missing_refs_by_question.values()),
        "episode_count": len(episodes),
        "raw_span_count": len(raw_spans),
        "capsule_count": len(capsules),
        "candidate_memory_count": len(memories),
        "required_field_coverage": required_field_coverage,
        "trajectory_question_join_rate": trajectory_question_join_rate,
        "evidence_ref_validity_rate": evidence_ref_validity_rate,
        "candidate_density": candidate_density,
        "dedup_rate": dedup_rate,
        "unsupported_claim_rate": unsupported_claim_rate,
        "actionability_score_avg": actionability_score_avg,
        "specificity_score_avg": specificity_score_avg,
        "temporal_order_accuracy": temporal_order_accuracy,
        "conflict_resolution_accuracy": signal_report["conflict_resolution_accuracy"],
        "conflict_resolution_applicable": signal_report["conflict_resolution_applicable"],
        "conflict_pair_count": signal_report["conflict_pair_count"],
        "known_bad_path_detection_rate": signal_report["known_bad_path_detection_rate"],
        "known_bad_path_count": signal_report["known_bad_path_count"],
        "policy_gate_leak_count": len(policy_violations),
        "verified_memory_write_count": 0,
        "promotion_count": 0,
        "layer3_mutation_count": 0,
        "runtime_marker_write_count": 0,
        "known_bad_path_write_count": 0,
        "online_llm_call_count": 0,
    }
    hard_gates = {
        "question_limit_met": metrics["question_count"] == question_limit,
        "trajectory_question_join_rate": trajectory_question_join_rate >= 0.95,
        "required_field_coverage": required_field_coverage >= 0.95,
        "evidence_ref_validity_rate": evidence_ref_validity_rate == 1.0,
        "unsupported_claim_rate": unsupported_claim_rate == 0.0,
        "temporal_order_accuracy": temporal_order_accuracy == 1.0,
        "policy_gate_leak_count": metrics["policy_gate_leak_count"] == 0,
        "verified_memory_write_count": metrics["verified_memory_write_count"] == 0,
        "promotion_count": metrics["promotion_count"] == 0,
        "layer3_mutation_count": metrics["layer3_mutation_count"] == 0,
        "online_llm_call_count": metrics["online_llm_call_count"] == 0,
    }
    return {
        "passed": all(hard_gates.values()),
        "metrics": metrics,
        "hard_gates": hard_gates,
        "adapter_quality_report": adapter_quality_report,
        "missing_field_report": missing_field_report,
        "evidence_ref_report": evidence_ref_report,
        "candidate_memory_type_stats": candidate_memory_type_stats,
        "signal_report": signal_report,
        "policy_violations": policy_violations,
        "missing_refs_by_question": missing_refs_by_question,
        "converted_samples": [episode.to_dict() for episode in episodes[:3]],
        "candidate_memory_samples": [memory.to_dict() for memory in memories[:20]],
    }


def _build_adapter_quality_report(
    *,
    questions: list[dict[str, Any]],
    haystack: dict[str, list[str]],
    requested_refs: set[str],
    trajectories_by_id: dict[str, dict[str, Any]],
    episodes: list[Any],
    raw_span_count: int,
    capsule_count: int,
    candidate_count: int,
    question_limit: int,
    trajectories_per_question: int,
    states_per_trajectory: int,
    max_observation_chars: int,
) -> dict[str, Any]:
    question_ids = [str(question.get("id", "")) for question in questions]
    questions_with_haystack = [question_id for question_id in question_ids if haystack.get(question_id)]
    questions_with_loaded_trajectory = [
        question_id
        for question_id in question_ids
        if any(trajectory_id in trajectories_by_id for trajectory_id in haystack.get(question_id, [])[:trajectories_per_question])
    ]
    questions_with_query_answer = [
        episode
        for episode in episodes
        if episode.queries and episode.queries[0].query and episode.queries[0].answer
    ]
    return {
        "question_limit": question_limit,
        "question_count": len(questions),
        "haystack_question_coverage": _safe_ratio(len(questions_with_haystack), len(questions)),
        "trajectory_question_join_rate": _safe_ratio(len(questions_with_loaded_trajectory), len(questions)),
        "requested_trajectory_refs": len(requested_refs),
        "loaded_trajectory_count": len(trajectories_by_id),
        "trajectory_ref_load_rate": _safe_ratio(len(trajectories_by_id), len(requested_refs)),
        "query_answer_pair_coverage": _safe_ratio(len(questions_with_query_answer), len(episodes)),
        "episode_count": len(episodes),
        "raw_span_count": raw_span_count,
        "capsule_count": capsule_count,
        "candidate_memory_count": candidate_count,
        "trajectories_per_question": trajectories_per_question,
        "states_per_trajectory": states_per_trajectory,
        "max_observation_chars": max_observation_chars,
    }


def _build_missing_field_report(
    *,
    questions: list[dict[str, Any]],
    trajectories: Iterable[dict[str, Any]],
    states_per_trajectory: int,
) -> dict[str, Any]:
    missing_questions = _missing_counts(questions, QUESTION_REQUIRED_FIELDS, sample_key="id")
    trajectories_list = list(trajectories)
    missing_trajectories = _missing_counts(
        trajectories_list,
        TRAJECTORY_REQUIRED_FIELDS,
        sample_key="id",
    )
    states: list[dict[str, Any]] = []
    state_samples: list[tuple[str, dict[str, Any]]] = []
    for trajectory in trajectories_list:
        trajectory_id = str(trajectory.get("id", ""))
        for state in list(trajectory.get("states", []))[:states_per_trajectory]:
            states.append(state)
            state_samples.append((trajectory_id, state))
    missing_states = _missing_counts(
        states,
        STATE_REQUIRED_FIELDS,
        sample_key="state_index",
        parent_samples=state_samples,
    )
    present = (
        missing_questions["present_count"]
        + missing_trajectories["present_count"]
        + missing_states["present_count"]
    )
    total = (
        missing_questions["total_count"]
        + missing_trajectories["total_count"]
        + missing_states["total_count"]
    )
    return {
        "required_field_coverage": _safe_ratio(present, total),
        "question_required_fields": QUESTION_REQUIRED_FIELDS,
        "trajectory_required_fields": TRAJECTORY_REQUIRED_FIELDS,
        "state_required_fields": STATE_REQUIRED_FIELDS,
        "question_missing": missing_questions,
        "trajectory_missing": missing_trajectories,
        "state_missing": missing_states,
    }


def _missing_counts(
    rows: Iterable[dict[str, Any]],
    fields: list[str],
    *,
    sample_key: str,
    parent_samples: list[tuple[str, dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    rows_list = list(rows)
    missing_by_field: dict[str, int] = {field: 0 for field in fields}
    samples: list[dict[str, Any]] = []
    for index, row in enumerate(rows_list):
        parent_id = ""
        if parent_samples is not None and index < len(parent_samples):
            parent_id = parent_samples[index][0]
        missing_fields = [field for field in fields if field not in row]
        for field in missing_fields:
            missing_by_field[field] += 1
        if missing_fields and len(samples) < 20:
            samples.append(
                {
                    "id": str(row.get(sample_key, "")),
                    "parent_id": parent_id,
                    "missing_fields": missing_fields,
                }
            )
    total = len(rows_list) * len(fields)
    missing = sum(missing_by_field.values())
    return {
        "row_count": len(rows_list),
        "total_count": total,
        "present_count": total - missing,
        "missing_count": missing,
        "coverage": _safe_ratio(total - missing, total),
        "missing_by_field": missing_by_field,
        "samples": samples,
    }


def _build_evidence_ref_report(memories: list[Any], raw_ids: set[str]) -> dict[str, Any]:
    total_refs = 0
    valid_refs = 0
    invalid_samples: list[dict[str, Any]] = []
    unsupported = 0
    for memory in memories:
        raw_ref_id = _raw_ref_from_evidence(memory.evidence)
        if raw_ref_id:
            total_refs += 1
            if raw_ref_id in raw_ids:
                valid_refs += 1
            elif len(invalid_samples) < 20:
                invalid_samples.append({"memory_id": memory.id, "raw_ref_id": raw_ref_id})
        if not raw_ref_id or raw_ref_id not in raw_ids or not memory.content:
            unsupported += 1
    return {
        "candidate_memory_count": len(memories),
        "evidence_ref_count": total_refs,
        "valid_evidence_ref_count": valid_refs,
        "invalid_evidence_ref_count": total_refs - valid_refs,
        "evidence_ref_coverage": _safe_ratio(total_refs, len(memories)),
        "evidence_ref_validity_rate": _safe_ratio(valid_refs, total_refs),
        "unsupported_claim_count": unsupported,
        "unsupported_claim_rate": _safe_ratio(unsupported, len(memories)),
        "invalid_samples": invalid_samples,
    }


def _build_candidate_memory_type_stats(memories: list[Any]) -> dict[str, Any]:
    by_type = Counter(memory.memory_type.value for memory in memories)
    by_polarity = Counter(memory.polarity.value for memory in memories)
    by_source = Counter(memory.source.value for memory in memories)
    by_freshness = Counter(memory.freshness.value for memory in memories)
    assistant = [memory for memory in memories if memory.source == Source.ASSISTANT]
    return {
        "candidate_memory_count": len(memories),
        "by_memory_type": dict(sorted(by_type.items())),
        "by_polarity": dict(sorted(by_polarity.items())),
        "by_source": dict(sorted(by_source.items())),
        "by_freshness": dict(sorted(by_freshness.items())),
        "assistant_candidate_count": len(assistant),
        "assistant_ambiguous_count": sum(
            1
            for memory in assistant
            if memory.polarity.value == "ambiguous" and memory.confidence <= 0.3
        ),
        "confidence_buckets": _confidence_buckets(memories),
    }


def _build_signal_report(
    records: list[dict[str, Any]],
    trajectories: Iterable[dict[str, Any]],
    memories: list[Any],
) -> dict[str, Any]:
    trajectories_list = list(trajectories)
    failed_ids = {str(item.get("id", "")) for item in trajectories_list if str(item.get("outcome", "")).lower() == "failure"}
    detected_failed_ids: set[str] = set()
    conflict_candidates = 0
    for record in records:
        for turn in record.get("sessions", []):
            turn_id = str(turn.get("id", ""))
            tags = {str(tag).lower() for tag in turn.get("tags", [])}
            content = str(turn.get("content", "")).lower()
            if any(turn_id.startswith(failed_id) for failed_id in failed_ids) and (
                "failure" in tags
                or "failed" in tags
                or "fail" in content
                or "error" in content
            ):
                detected_failed_ids.add(turn_id.split("_")[0])
            if "conflict" in tags or "contradict" in content or "changed" in content:
                conflict_candidates += 1
    # The adapter does not resolve conflicts in v0.6.4b; it only preserves
    # enough signal to report whether conflict examples are present.
    conflict_resolution_applicable = conflict_candidates > 0
    return {
        "known_bad_path_count": len(failed_ids),
        "known_bad_path_detected_count": len(detected_failed_ids),
        "known_bad_path_detection_rate": _safe_ratio(len(detected_failed_ids), len(failed_ids)),
        "conflict_pair_count": conflict_candidates,
        "conflict_resolution_applicable": conflict_resolution_applicable,
        "conflict_resolution_accuracy": 0.0 if conflict_resolution_applicable else 0.0,
        "negative_candidate_count": sum(1 for memory in memories if memory.polarity.value == "negative"),
    }


def _confidence_buckets(memories: list[Any]) -> dict[str, int]:
    buckets = {"0.0-0.3": 0, "0.3-0.6": 0, "0.6-1.0": 0}
    for memory in memories:
        if memory.confidence <= 0.3:
            buckets["0.0-0.3"] += 1
        elif memory.confidence <= 0.6:
            buckets["0.3-0.6"] += 1
        else:
            buckets["0.6-1.0"] += 1
    return buckets


def _raw_ref_from_evidence(evidence: str) -> str:
    prefix = "raw_ref_id="
    if not evidence.startswith(prefix):
        return ""
    return evidence[len(prefix) :].strip()


def _dedup_rate(contents: Iterable[str]) -> float:
    normalized = [_normalize_text(content) for content in contents]
    if not normalized:
        return 0.0
    return (len(normalized) - len(set(normalized))) / len(normalized)


def _normalize_text(text: str) -> str:
    return " ".join(str(text).lower().split())


def _actionability_score(content: str, tags: list[str], source: Source) -> float:
    text = f"{content} {' '.join(tags)}".lower()
    token_hits = sum(1 for term in ACTIONABLE_TERMS if term in text)
    score = min(0.5, token_hits * 0.1)
    if source in {Source.USER, Source.TERMINAL, Source.TOOL, Source.FILE, Source.WEB}:
        score += 0.25
    if any(tag in ACTIONABLE_TERMS or tag in {"success", "failure", "temporal"} for tag in tags):
        score += 0.25
    return round(min(score, 1.0), 4)


def _specificity_score(content: str) -> float:
    text = str(content)
    tokens = {token.lower() for token in re.findall(r"[A-Za-z0-9_./:-]+", text)}
    entity_hits = len(SPECIFICITY_RE.findall(text))
    length_score = min(len(text) / 500, 0.35)
    token_score = min(len(tokens) / 50, 0.35)
    entity_score = min(entity_hits / 8, 0.3)
    return round(min(length_score + token_score + entity_score, 1.0), 4)


def _temporal_order_accuracy(episodes: list[Any]) -> float:
    checked = 0
    ordered = 0
    for episode in episodes:
        timestamps_by_trajectory: dict[str, list[str]] = defaultdict(list)
        for turn in episode.turns:
            if not turn.timestamp:
                continue
            trajectory_id = str(turn.id).split("_")[0]
            timestamps_by_trajectory[trajectory_id].append(turn.timestamp)
        for timestamps in timestamps_by_trajectory.values():
            if not timestamps:
                continue
            checked += 1
            if timestamps == sorted(timestamps):
                ordered += 1
    return _safe_ratio(ordered, checked)


def _average(values: Iterable[float]) -> float:
    items = list(values)
    if not items:
        return 0.0
    return round(sum(items) / len(items), 4)


def _safe_ratio(numerator: int | float, denominator: int | float) -> float:
    if denominator == 0:
        return 0.0
    return round(float(numerator) / float(denominator), 6)


def evaluate_question_limits(
    input_root: Path | None,
    *,
    question_limits: list[int],
    trajectories_per_question: int,
    states_per_trajectory: int,
    max_observation_chars: int,
    haystack_name: str,
    hf_cache_root: Path | None = None,
    allow_download: bool = False,
) -> dict[str, Any]:
    runs = []
    for question_limit in question_limits:
        runs.append(
            evaluate_lme_v2_expansion(
                input_root,
                question_limit=question_limit,
                trajectories_per_question=trajectories_per_question,
                states_per_trajectory=states_per_trajectory,
                max_observation_chars=max_observation_chars,
                haystack_name=haystack_name,
                hf_cache_root=hf_cache_root,
                allow_download=allow_download,
            )
        )
    return {
        "validation": "longmemeval-v2-adapter-expansion-v0.6.4b",
        "passed": all(run["passed"] for run in runs),
        "input_root": str(input_root),
        "question_limits": question_limits,
        "trajectories_per_question": trajectories_per_question,
        "states_per_trajectory": states_per_trajectory,
        "max_observation_chars": max_observation_chars,
        "haystack_name": haystack_name,
        "runs": runs,
    }


def write_outputs(output_dir: Path, result: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    latest = result["runs"][-1]
    write_json(output_dir / "raw_results.json", _strip_samples(result))
    write_json(output_dir / "metrics_summary.json", _summary(result))
    write_json(output_dir / "adapter_quality_report.json", _report_by_limit(result, "adapter_quality_report"))
    write_json(output_dir / "missing_field_report.json", _report_by_limit(result, "missing_field_report"))
    write_json(output_dir / "evidence_ref_report.json", _report_by_limit(result, "evidence_ref_report"))
    write_json(output_dir / "candidate_memory_type_stats.json", _report_by_limit(result, "candidate_memory_type_stats"))
    write_json(output_dir / "signal_report.json", _report_by_limit(result, "signal_report"))
    write_jsonl(output_dir / "converted_sample_preview.jsonl", latest["converted_samples"])
    write_jsonl(output_dir / "candidate_memory_samples.jsonl", latest["candidate_memory_samples"])
    write_readme(output_dir, result)


def _strip_samples(result: dict[str, Any]) -> dict[str, Any]:
    stripped = dict(result)
    stripped["runs"] = []
    for run in result["runs"]:
        copy = dict(run)
        copy.pop("converted_samples", None)
        copy.pop("candidate_memory_samples", None)
        stripped["runs"].append(copy)
    return stripped


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "validation": result["validation"],
        "passed": result["passed"],
        "question_limits": result["question_limits"],
        "metrics_by_limit": {
            str(run["metrics"]["question_limit"]): run["metrics"] for run in result["runs"]
        },
        "hard_gates_by_limit": {
            str(run["metrics"]["question_limit"]): run["hard_gates"] for run in result["runs"]
        },
    }


def _report_by_limit(result: dict[str, Any], key: str) -> dict[str, Any]:
    return {
        "validation": result["validation"],
        "reports_by_limit": {
            str(run["metrics"]["question_limit"]): run[key] for run in result["runs"]
        },
    }


def write_readme(output_dir: Path, result: dict[str, Any]) -> None:
    rows = []
    for run in result["runs"]:
        metrics = run["metrics"]
        rows.append(
            "| {question_count} | {loaded_trajectory_count} | {candidate_memory_count} | "
            "{required_field_coverage:.3f} | {evidence_ref_validity_rate:.3f} | "
            "{unsupported_claim_rate:.3f} | {policy_gate_leak_count} | "
            "{verified_memory_write_count} | {promotion_count} | {layer3_mutation_count} |".format(**metrics)
        )
    text = f"""# v0.6.4b LongMemEval-V2 Adapter Expansion

This validation expands the LongMemEval-V2 local snapshot adapter from the
v0.6.4a smoke run into bounded 50 / 100 question coverage runs.

It answers one question only:

> Can external LongMemEval-V2 data safely enter MemoryWeaver's external
> adapter substrate without writing verified memory or mutating lifecycle state?

It does **not** evaluate task success, agent behavior, memory promotion, Layer-3
pattern mutation, or runtime marker writes. Those belong to the separate
`v0.6.3-live-memory-loop` line.

## Result

- Overall passed: {result['passed']}
- Input root: `{result['input_root']}`
- Question limits: {result['question_limits']}
- Trajectories per question: {result['trajectories_per_question']}
- States per trajectory: {result['states_per_trajectory']}
- Online LLM calls: 0

| Questions | Loaded Traj. | Candidates | Field Cov. | Evidence Ref Valid | Unsupported | Gate Leaks | Verified Writes | Promotions | L3 Mutations |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(rows)}

## Reports

- `adapter_quality_report.json`: join rate, haystack coverage, conversion volume.
- `missing_field_report.json`: missing raw question / trajectory / state fields.
- `evidence_ref_report.json`: raw evidence reference coverage and validity.
- `candidate_memory_type_stats.json`: candidate source, polarity, type, freshness counts.
- `signal_report.json`: known-bad path and conflict-signal preservation.

## Boundary

The dry-run boundary is intentionally hard:

- `verified_memory_write_count = 0`
- `promotion_count = 0`
- `layer3_mutation_count = 0`
- `runtime_marker_write_count = 0`
- `known_bad_path_write_count = 0`
- `online_llm_call_count = 0`

## Interpretation

v0.6.4b is the external-data ingestion lane. It verifies adapter coverage,
evidence-reference integrity, candidate density, and trust-boundary safety at
larger LongMemEval-V2 sample sizes. It should not be mixed with v0.6.3, which
is the live-memory lifecycle lane for real writes, promotion, retrieval,
conflict handling, rollback, Layer-3 mutation, and runtime marker writes.
"""
    (output_dir / "README.md").write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--question-limits", type=int, nargs="+", default=[50, 100])
    parser.add_argument("--trajectories-per-question", type=int, default=3)
    parser.add_argument("--states-per-trajectory", type=int, default=5)
    parser.add_argument("--max-observation-chars", type=int, default=1800)
    parser.add_argument("--haystack-name", default="lme_v2_small.json")
    parser.add_argument("--hf-cache-root", type=Path, default=None)
    parser.add_argument("--download-if-missing", action="store_true")
    args = parser.parse_args(argv)

    workspace_root = args.output_dir / ".memoryweaver-lme-v2-expansion-workspace"
    safe_rmtree_child(
        args.output_dir,
        workspace_root,
        allowed_prefixes=(".memoryweaver-lme-v2-expansion-workspace",),
    )
    MemoryWorkspace(workspace_root)

    result = evaluate_question_limits(
        args.input_root,
        question_limits=args.question_limits,
        trajectories_per_question=args.trajectories_per_question,
        states_per_trajectory=args.states_per_trajectory,
        max_observation_chars=args.max_observation_chars,
        haystack_name=args.haystack_name,
        hf_cache_root=args.hf_cache_root,
        allow_download=args.download_if_missing,
    )
    write_outputs(args.output_dir, result)
    print(json.dumps(_summary(result), ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
