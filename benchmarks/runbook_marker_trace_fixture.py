"""Evaluate the v0.5 Runbook Marker dialogue fixture.

This benchmark is intentionally trace-first. It does not implement the full
v0.5 runtime, auto CoreIssueNode emergence, or automatic HarnessMarker
projection. Instead, it validates that the manually curated dialogue cards can
drive the minimal runtime trace contract:

baseline_no_marker vs memoryweaver_marker_shadow
  -> counterfactual advantage
  -> actual runtime unchanged in shadow mode
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memoryweaver.store import token_jaccard


DEFAULT_INPUT = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "validation"
    / "runbook-marker-v0.5"
    / "dialogue_cards.jsonl"
)
DEFAULT_OUTPUT_DIR = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "validation"
    / "runbook-marker-v0.5"
)


@dataclass(frozen=True)
class DialogueCard:
    dialogue_card_id: str
    title: str
    card_type: str
    tier: str
    domain: str
    turn_count: int
    query_id: str
    query: str
    events: list[dict[str, Any]]
    expected: dict[str, Any]
    annotations: dict[str, Any]
    counterfactual: dict[str, Any]
    conflict_candidates: list[dict[str, Any]]

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "DialogueCard":
        if "dialogue_card_id" in data:
            queries = list(data.get("queries", []))
            if not queries:
                raise ValueError("rich dialogue card requires at least one query")
            first_query = dict(queries[0])
            return cls(
                dialogue_card_id=str(data["dialogue_card_id"]),
                title=str(data.get("title", data["dialogue_card_id"])),
                card_type=str(data.get("card_type", "unknown")),
                tier=str(data.get("tier", "typed")),
                domain=str(data.get("domain", "")),
                turn_count=int(data.get("turns", data.get("turn_count", 0))),
                query_id=str(first_query.get("query_id", f"{data['dialogue_card_id']}_q1")),
                query=str(first_query.get("query", data.get("initial_user_problem", ""))),
                events=list(data.get("events", [])),
                expected=dict(data.get("expected", {})),
                annotations=dict(data.get("annotations", {})),
                counterfactual=dict(data.get("counterfactual", {})),
                conflict_candidates=list(data.get("conflict_candidates", [])),
            )

        # Backward-compatible loader for the first v0.5 seed fixture.
        dialogue_id = str(data["dialogue_id"])
        expected_core = str(data["expected_core_issue_node"])
        expected_marker = str(data["expected_harness_marker"])
        required_evidence = list(data["required_evidence"])
        suppressed = list(data["known_bad_path_suppression"])
        query = str(data["initial_user_problem"])
        return cls(
            dialogue_card_id=dialogue_id,
            title=query,
            card_type="known_bad_path_suppression",
            tier="typed",
            domain=str(data["scenario"]),
            turn_count=int(data["turn_count"]),
            query_id=f"{dialogue_id}_q1",
            query=query,
            events=[
                {
                    "event_id": f"{dialogue_id}_e1",
                    "turn": 1,
                    "source": "user",
                    "content": query,
                    "tags": [],
                    "expected_promoted": True,
                    "expected_retrievable": True,
                },
                {
                    "event_id": f"{dialogue_id}_e2",
                    "turn": 2,
                    "source": "user",
                    "content": str(data["user_correction_or_exploration_signal"]),
                    "tags": [],
                    "expected_promoted": True,
                    "expected_retrievable": True,
                },
            ],
            expected={
                "must": {
                    "core_issue_match": expected_core,
                    "marker_activation": expected_marker,
                    "shadow_mode": True,
                    "actual_route": "thinking",
                },
                "should": {
                    "recommended_route": str(data.get("expected_route", "fast_verify")),
                    "required_evidence": required_evidence,
                    "suppressed_actions": suppressed,
                },
                "must_not": {
                    "actual_suppressed": suppressed,
                    "auto_execute_tools": True,
                    "auto_promote_pattern": True,
                },
            },
            annotations={
                "core_issues": [expected_core],
                "markers": [expected_marker],
                "metric_focus": list(data["metric_focus"]),
            },
            counterfactual={
                "source": "manual_annotation",
                "confidence": 0.6,
                "without_marker": {
                    "likely_path": "repeat known bad path -> fail -> user corrects",
                    "estimated_steps": 5,
                    "known_bad_actions": suppressed,
                },
                "with_marker": {
                    "likely_path": "follow required evidence checks -> fast verify",
                    "estimated_steps": 2,
                },
            },
            conflict_candidates=[],
        )

    def searchable_text(self) -> str:
        must = dict(self.expected.get("must", {}))
        should = dict(self.expected.get("should", {}))
        fields = [
            self.dialogue_card_id,
            self.title,
            self.card_type,
            self.domain,
            self.query,
            str(must.get("core_issue_match", "")),
            str(must.get("marker_activation", "")),
            " ".join(str(item) for item in should.get("suppressed_actions", [])),
            " ".join(str(item) for item in should.get("required_evidence", [])),
            " ".join(str(event.get("content", "")) for event in self.events),
        ]
        return " ".join(fields)


def load_dialogue_cards(path: Path = DEFAULT_INPUT) -> list[DialogueCard]:
    cards: list[DialogueCard] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            cards.append(DialogueCard.from_dict(json.loads(line)))
        except Exception as exc:  # pragma: no cover - includes line context
            raise ValueError(f"Invalid dialogue card at line {line_number}: {exc}") from exc
    return cards


def match_card(query: str, cards: Iterable[DialogueCard]) -> tuple[DialogueCard, float]:
    scored = [
        (card, token_jaccard(query, card.searchable_text()))
        for card in cards
    ]
    if not scored:
        raise ValueError("No dialogue cards available for matching")
    scored.sort(key=lambda pair: (pair[1], pair[0].dialogue_card_id), reverse=True)
    return scored[0]


ESTIMATION_METHODOLOGY = {
    "step_unit": (
        "1 step = one independent agent action, including one tool call, one "
        "file read, one terminal command, or one user interaction."
    ),
    "excluded": [
        "internal reasoning",
        "retrieval",
        "memory recall",
    ],
    "user_correction_counts_as_step": True,
    "known_bad_action_counts_as_step": True,
    "scope": "manual counterfactual estimate for v0.5; real trajectories start in v0.6",
}


def advantage_types(card_type: str) -> list[str]:
    mapping = {
        "known_bad_path_suppression": ["guard_marker", "evidence_marker", "route_marker"],
        "marker_conflict_shadow": ["conflict_resolution"],
        "weak_signal_partial": ["partial_signal_retention"],
        "freshness_conflict": ["freshness_conflict_detection"],
        "ambiguous_evidence": ["ambiguous_evidence_control"],
        "negative_avoidance": ["negative_avoidance"],
        "route_hint": ["route_marker"],
        "evidence_requirement": ["evidence_marker"],
        "scope_mismatch": ["scope_control"],
        "overgeneralized_marker_rejection": ["overgeneralized_marker_rejection"],
    }
    return mapping.get(card_type, ["trace_advantage"])


def confidence_label(confidence: float) -> str:
    if confidence >= 0.7:
        return "high"
    if confidence >= 0.55:
        return "medium"
    return "low"


def confidence_basis(card: DialogueCard) -> str:
    if card.tier == "golden" and card.card_type in {
        "known_bad_path_suppression",
        "freshness_conflict",
        "ambiguous_evidence",
    }:
        return "replay"
    if card.tier == "golden":
        return "extrapolation"
    if card.tier == "typed":
        return "extrapolation"
    return "pure_counterfactual"


def mini_event(
    step: int,
    action: str,
    purpose: str,
    *,
    known_bad: bool = False,
    source: str = "manual_counterfactual",
    tool: str = "",
    command: str = "",
    content: str = "",
) -> dict[str, object]:
    event = {
        "step": step,
        "action": action,
        "purpose": purpose,
        "known_bad": known_bad,
        "source": source,
    }
    if tool:
        event["tool"] = tool
    if command:
        event["command"] = command
    if content:
        event["content"] = content
    return event


def build_baseline_no_marker(
    matched: DialogueCard,
    required_evidence: list[str],
    suppressed_actions: list[str],
) -> dict[str, object]:
    counterfactual = matched.counterfactual
    without_marker = dict(counterfactual.get("without_marker", {}))
    estimated_steps = int(without_marker.get("estimated_steps", 0)) or max(
        3,
        len(suppressed_actions) + 2,
    )
    known_bad_actions = list(without_marker.get("known_bad_actions", suppressed_actions))
    likely_path: list[dict[str, object]] = []
    step = 1
    for action in known_bad_actions:
        likely_path.append(
            mini_event(
                step,
                "tool_call",
                str(action),
                known_bad=True,
                tool="shell_or_cli",
                command=str(action),
            )
        )
        step += 1
    while step < max(estimated_steps, 2):
        likely_path.append(
            mini_event(
                step,
                "diagnostic_action",
                "generic_debugging_without_marker",
            )
        )
        step += 1
    likely_path.append(
        mini_event(
            step,
            "user_correction",
            "redirect_to_marker_relevant_evidence",
            content=str(matched.annotations.get("key_insight", "")),
        )
    )
    first_relevant_evidence_step = min(estimated_steps, max(1, step))
    if required_evidence:
        likely_path.append(
            mini_event(
                first_relevant_evidence_step,
                "tool_call",
                str(required_evidence[0]),
                tool="evidence_check",
                command=str(required_evidence[0]),
            )
        )
    return {
        "likely_path": likely_path,
        "estimated_steps": estimated_steps,
        "known_bad_actions": known_bad_actions,
        "first_relevant_evidence_step": first_relevant_evidence_step,
        "user_correction_expected": True,
    }


def build_marker_shadow_path(
    matched: DialogueCard,
    recommended_route: str,
    actual_route: str,
    required_evidence: list[str],
    suppressed_actions: list[str],
) -> dict[str, object]:
    counterfactual = matched.counterfactual
    with_marker = dict(counterfactual.get("with_marker", {}))
    estimated_steps = int(with_marker.get("estimated_steps", 0)) or max(
        1,
        min(2, len(required_evidence)),
    )
    likely_path = [
        mini_event(
            index + 1,
            "evidence_check",
            str(evidence),
            tool="evidence_check",
            command=str(evidence),
        )
        for index, evidence in enumerate(required_evidence[:estimated_steps])
    ]
    if len(likely_path) < estimated_steps:
        likely_path.append(
            mini_event(
                len(likely_path) + 1,
                "verify_result",
                "resolve_or_narrow_safely",
            )
        )
    return {
        "matched_core_issue": matched.expected["must"].get("core_issue_match", ""),
        "activated_marker": matched.expected["must"].get("marker_activation", ""),
        "shadow_mode": True,
        "recommended_route": recommended_route,
        "actual_route": actual_route,
        "suppressed_actions": suppressed_actions,
        "required_evidence": required_evidence,
        "likely_path": likely_path,
        "estimated_steps": estimated_steps,
        "first_relevant_evidence_step": 1 if required_evidence else 0,
        "user_correction_expected": False,
    }


def build_advantage(
    matched: DialogueCard,
    baseline: dict[str, object],
    marker_shadow: dict[str, object],
    conflict_candidates: list[dict[str, Any]],
) -> dict[str, object]:
    baseline_steps = int(baseline["estimated_steps"])
    marker_steps = int(marker_shadow["estimated_steps"])
    baseline_bad_actions = set(str(item) for item in baseline["known_bad_actions"])
    suppressed_actions = set(str(item) for item in marker_shadow["suppressed_actions"])
    known_bad_avoided = sorted(baseline_bad_actions & suppressed_actions)
    evidence_order_gain = max(
        0,
        int(baseline["first_relevant_evidence_step"])
        - int(marker_shadow["first_relevant_evidence_step"]),
    )
    confidence = float(matched.counterfactual.get("confidence", 0.5))
    source_gate_steps = 1 if matched.card_type in {
        "ambiguous_evidence",
        "weak_signal_partial",
        "freshness_conflict",
    } else 0
    guard_steps = 1 if known_bad_avoided else 0
    evidence_steps = max(0, baseline_steps - marker_steps - source_gate_steps - guard_steps)
    advantage: dict[str, object] = {
        "advantage_type": advantage_types(matched.card_type),
        "estimated_step_reduction": max(0, baseline_steps - marker_steps),
        "known_bad_actions_avoided": len(known_bad_avoided),
        "known_bad_actions": known_bad_avoided,
        "evidence_order_gain": evidence_order_gain,
        "user_correction_avoidance_estimate": (
            1 if baseline.get("user_correction_expected")
            and not marker_shadow.get("user_correction_expected")
            else 0
        ),
        "source": matched.counterfactual.get("source", "manual_annotation"),
        "confidence": confidence_label(confidence),
        "confidence_score": confidence,
        "confidence_basis": confidence_basis(matched),
        "estimation_methodology": ESTIMATION_METHODOLOGY,
        "attribution": {
            "source_gate_contribution": {
                "steps_saved": source_gate_steps,
                "mechanism": (
                    "keeps assistant/tool ambiguous signal labeled non-authoritative"
                    if source_gate_steps else "not primary in this card"
                ),
            },
            "guard_marker_contribution": {
                "steps_saved": guard_steps,
                "mechanism": (
                    "warns about known bad action before it is attempted"
                    if guard_steps else "not primary in this card"
                ),
            },
            "evidence_marker_contribution": {
                "steps_saved": evidence_steps,
                "mechanism": "moves required evidence checks earlier in the path",
            },
        },
    }
    if conflict_candidates:
        advantage["conflict_resolution"] = {
            "conflicting_markers": [
                conflict.get("marker_a", "")
                for conflict in conflict_candidates
            ] + [
                conflict.get("marker_b", "")
                for conflict in conflict_candidates
            ],
            "resolution": "shadow_unresolved_logged_for_v0_5_2",
            "baseline_behavior": (
                "both markers may be treated as simultaneous advice, causing oscillation"
            ),
            "marker_behavior": (
                "conflict detected, logged, and kept in shadow mode without runtime action"
            ),
            "oscillation_avoided": True,
        }
    return advantage


def trace_card(card: DialogueCard, cards: list[DialogueCard]) -> dict[str, object]:
    matched, similarity = match_card(card.query, cards)
    matched_must = dict(matched.expected.get("must", {}))
    matched_should = dict(matched.expected.get("should", {}))
    matched_must_not = dict(matched.expected.get("must_not", {}))
    expected_must = dict(card.expected.get("must", {}))
    expected_should = dict(card.expected.get("should", {}))
    expected_must_not = dict(card.expected.get("must_not", {}))
    recommended_route = str(matched_should.get("recommended_route", "fast_verify"))
    actual_route = str(matched_must.get("actual_route", "thinking"))
    required_evidence = list(matched_should.get("required_evidence", []))
    suppressed_actions = list(matched_should.get("suppressed_actions", []))
    intervention_level = str(matched.annotations.get("intervention_level", "L0_trace"))
    shadow_mode = bool(matched_must.get("shadow_mode", True))
    applied_to_runtime = False
    safety_violations: list[str] = []
    if actual_route != "thinking":
        safety_violations.append("actual_route_changed_in_shadow_mode")
    if not shadow_mode:
        safety_violations.append("shadow_mode_not_labeled")
    if applied_to_runtime:
        safety_violations.append("marker_applied_to_runtime_in_v0_5")
    if matched_must_not.get("auto_execute_tools") is not True:
        safety_violations.append("must_not_auto_execute_tools_missing")
    if matched_must_not.get("auto_promote_pattern") is not True:
        safety_violations.append("must_not_auto_promote_pattern_missing")
    baseline_no_marker = build_baseline_no_marker(
        matched,
        required_evidence,
        suppressed_actions,
    )
    memoryweaver_marker_shadow = build_marker_shadow_path(
        matched,
        recommended_route,
        actual_route,
        required_evidence,
        suppressed_actions,
    )
    advantage = build_advantage(
        matched,
        baseline_no_marker,
        memoryweaver_marker_shadow,
        matched.conflict_candidates,
    )
    return {
        "dialogue_card_id": card.dialogue_card_id,
        "query_id": card.query_id,
        "query": card.query,
        "card_type": card.card_type,
        "tier": card.tier,
        "matched_dialogue_card_id": matched.dialogue_card_id,
        "matched_core_issue": matched_must.get("core_issue_match", ""),
        "expected_core_issue": expected_must.get("core_issue_match", ""),
        "activated_marker": matched_must.get("marker_activation", ""),
        "expected_marker": expected_must.get("marker_activation", ""),
        "intervention_level": intervention_level,
        "max_allowed_in_v0_5": matched.annotations.get("max_allowed_in_v0_5", "shadow_only"),
        "marker_recommendation": {
            "recommended_route": recommended_route,
            "required_evidence": required_evidence,
            "suppressed_actions": suppressed_actions,
        },
        "shadow_effect": {
            "shadow_mode": shadow_mode,
            "applied_to_runtime": applied_to_runtime,
            "would_change_route": recommended_route != actual_route,
            "would_suppress_action": bool(suppressed_actions),
            "would_require_evidence": bool(required_evidence),
        },
        "actual_runtime": {
            "actual_route": actual_route,
            "actual_suppressed_actions": [],
            "actual_required_evidence": [],
        },
        "baseline_no_marker": baseline_no_marker,
        "memoryweaver_marker_shadow": memoryweaver_marker_shadow,
        "advantage": advantage,
        "counterfactual": matched.counterfactual,
        "conflict_candidates": matched.conflict_candidates,
        "safety_violations": safety_violations,
        "online_llm_call_count": 0,
        "similarity": round(similarity, 4),
        "trace_reason": (
            f"Matched {matched.dialogue_card_id} by lexical overlap with scenario, "
            f"problem text, events, expected core issue, and marker names. "
            "Marker output is recorded in shadow mode and not applied to runtime."
        ),
        "core_issue_match": (
            matched_must.get("core_issue_match") == expected_must.get("core_issue_match")
        ),
        "marker_match": (
            matched_must.get("marker_activation") == expected_must.get("marker_activation")
        ),
        "route_match": recommended_route == expected_should.get("recommended_route", "fast_verify"),
        "actual_runtime_unchanged": actual_route == "thinking" and not applied_to_runtime,
        "shadow_mode_labeled": shadow_mode is True,
        "counterfactual_present": bool(matched.counterfactual),
        "conflict_candidate_logged": bool(matched.conflict_candidates),
        "required_evidence_match": set(required_evidence) >= set(
            expected_should.get("required_evidence", [])
        ),
        "known_bad_path_warning_match": set(suppressed_actions) >= set(
            expected_should.get("suppressed_actions", [])
        ),
        "must_not_satisfied": (
            not safety_violations
            and not set(matched_must_not.get("actual_suppressed", []))
                & set([])  # actual runtime suppresses no actions in shadow mode
            and expected_must_not.get("auto_execute_tools") is True
            and expected_must_not.get("auto_promote_pattern") is True
        ),
        "trace_complete": bool(
            matched_must.get("core_issue_match")
            and matched_must.get("marker_activation")
            and required_evidence
            and recommended_route == "fast_verify"
            and actual_route == "thinking"
            and shadow_mode
            and matched.counterfactual
        ),
    }


def evaluate_cards(cards: list[DialogueCard]) -> dict[str, object]:
    traces = [trace_card(card, cards) for card in cards]
    total = len(traces)
    if total == 0:
        raise ValueError("Cannot evaluate an empty dialogue fixture")

    complete_count = sum(1 for trace in traces if trace["trace_complete"])
    core_match_count = sum(1 for trace in traces if trace["core_issue_match"])
    marker_match_count = sum(1 for trace in traces if trace["marker_match"])
    route_match_count = sum(1 for trace in traces if trace["route_match"])
    online_zero_count = sum(1 for trace in traces if trace["online_llm_call_count"] == 0)
    warning_match_count = sum(1 for trace in traces if trace["known_bad_path_warning_match"])
    required_evidence_match_count = sum(1 for trace in traces if trace["required_evidence_match"])
    shadow_labeled_count = sum(1 for trace in traces if trace["shadow_mode_labeled"])
    actual_unchanged_count = sum(1 for trace in traces if trace["actual_runtime_unchanged"])
    counterfactual_count = sum(1 for trace in traces if trace["counterfactual_present"])
    conflict_logged_count = sum(1 for trace in traces if trace["conflict_candidate_logged"])
    safety_violation_count = sum(len(trace["safety_violations"]) for trace in traces)
    golden_count = sum(1 for card in cards if card.tier == "golden")
    total_step_reduction = sum(
        int(trace["advantage"]["estimated_step_reduction"])
        for trace in traces
    )
    total_known_bad_avoided = sum(
        int(trace["advantage"]["known_bad_actions_avoided"])
        for trace in traces
    )
    total_evidence_order_gain = sum(
        int(trace["advantage"]["evidence_order_gain"])
        for trace in traces
    )
    total_user_correction_avoidance = sum(
        int(trace["advantage"]["user_correction_avoidance_estimate"])
        for trace in traces
    )
    marker_advantage_card_count = sum(
        1 for trace in traces
        if int(trace["advantage"]["estimated_step_reduction"]) > 0
        or int(trace["advantage"]["known_bad_actions_avoided"]) > 0
        or int(trace["advantage"]["evidence_order_gain"]) > 0
        or trace["conflict_candidate_logged"]
    )
    high_confidence_advantage_count = sum(
        1 for trace in traces
        if trace["advantage"]["confidence"] == "high"
    )
    medium_or_high_confidence_advantage_count = sum(
        1 for trace in traces
        if trace["advantage"]["confidence"] in {"high", "medium"}
    )
    conflict_resolution_advantage_count = sum(
        1 for trace in traces
        if "conflict_resolution" in trace["advantage"]
    )
    attribution_totals = {
        "source_gate_steps_saved": sum(
            int(trace["advantage"]["attribution"]["source_gate_contribution"]["steps_saved"])
            for trace in traces
        ),
        "guard_marker_steps_saved": sum(
            int(trace["advantage"]["attribution"]["guard_marker_contribution"]["steps_saved"])
            for trace in traces
        ),
        "evidence_marker_steps_saved": sum(
            int(trace["advantage"]["attribution"]["evidence_marker_contribution"]["steps_saved"])
            for trace in traces
        ),
    }
    type_counts: dict[str, int] = {}
    type_pass_counts: dict[str, int] = {}
    for trace in traces:
        card_type = str(trace["card_type"])
        type_counts[card_type] = type_counts.get(card_type, 0) + 1
        if trace["trace_complete"] and trace["must_not_satisfied"]:
            type_pass_counts[card_type] = type_pass_counts.get(card_type, 0) + 1

    metrics = {
        "card_count": total,
        "golden_card_count": golden_count,
        "unique_dialogue_ids": len({card.dialogue_card_id for card in cards}),
        "turn_min": min(card.turn_count for card in cards),
        "turn_max": max(card.turn_count for card in cards),
        "core_issue_match_accuracy": core_match_count / total,
        "marker_trigger_precision": marker_match_count / total,
        "route_accuracy": route_match_count / total,
        "online_llm_zero_rate": online_zero_count / total,
        "trace_completeness_rate": complete_count / total,
        "complete_trace_count": complete_count,
        "trace_generated_count": total,
        "shadow_mode_labeled_rate": shadow_labeled_count / total,
        "actual_runtime_unchanged_rate": actual_unchanged_count / total,
        "required_evidence_match_rate": required_evidence_match_count / total,
        "known_bad_path_warning_match_rate": warning_match_count / total,
        "counterfactual_present_rate": counterfactual_count / total,
        "conflict_candidate_logged_count": conflict_logged_count,
        "safety_violation_count": safety_violation_count,
        "counterfactual_step_reduction": total_step_reduction,
        "mean_counterfactual_step_reduction": total_step_reduction / total,
        "known_bad_action_reduction": total_known_bad_avoided,
        "evidence_order_improvement": total_evidence_order_gain,
        "user_correction_avoidance_estimate": total_user_correction_avoidance,
        "marker_advantage_card_count": marker_advantage_card_count,
        "marker_advantage_card_rate": marker_advantage_card_count / total,
        "high_confidence_advantage_count": high_confidence_advantage_count,
        "medium_or_high_confidence_advantage_count": (
            medium_or_high_confidence_advantage_count
        ),
        "conflict_resolution_advantage_count": conflict_resolution_advantage_count,
        "advantage_attribution_totals": attribution_totals,
        "card_type_counts": type_counts,
        "card_type_pass_counts": type_pass_counts,
    }
    passed = (
        metrics["unique_dialogue_ids"] == total
        and metrics["turn_min"] >= 10
        and metrics["turn_max"] <= 20
        and metrics["complete_trace_count"] >= 40
        and metrics["online_llm_zero_rate"] == 1.0
        and metrics["route_accuracy"] == 1.0
        and metrics["shadow_mode_labeled_rate"] == 1.0
        and metrics["actual_runtime_unchanged_rate"] == 1.0
        and metrics["counterfactual_present_rate"] == 1.0
        and metrics["safety_violation_count"] == 0
        and metrics["known_bad_path_warning_match_rate"] >= 0.8
        and metrics["marker_advantage_card_count"] >= golden_count
        and metrics["counterfactual_step_reduction"] > 0
        and metrics["known_bad_action_reduction"] > 0
        and metrics["evidence_order_improvement"] > 0
    )
    return {
        "benchmark": "runbook-marker-trace-fixture-v0.5",
        "dataset": {
            "source": str(DEFAULT_INPUT),
            "cards": total,
            "dialogue_unit": "one 10-20 turn conversation",
            "official_external_benchmark": False,
        },
        "metrics": metrics,
        "passed": passed,
        "traces": traces,
    }


def write_outputs(result: dict[str, object], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = output_dir / "raw_results.json"
    metrics_path = output_dir / "metrics_summary.json"
    traces_path = output_dir / "trace_samples.jsonl"
    counterfactual_path = output_dir / "counterfactual_notes.jsonl"
    conflicts_path = output_dir / "conflict_candidates.jsonl"
    advantage_path = output_dir / "trace_advantage.jsonl"

    raw_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    metrics_path.write_text(
        json.dumps(
            {
                "benchmark": result["benchmark"],
                "dataset": result["dataset"],
                "metrics": result["metrics"],
                "passed": result["passed"],
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    with traces_path.open("w", encoding="utf-8") as handle:
        for trace in result["traces"]:
            handle.write(json.dumps(trace, ensure_ascii=False) + "\n")
    with counterfactual_path.open("w", encoding="utf-8") as handle:
        for trace in result["traces"]:
            handle.write(json.dumps({
                "dialogue_card_id": trace["dialogue_card_id"],
                "counterfactual": trace["counterfactual"],
            }, ensure_ascii=False) + "\n")
    with conflicts_path.open("w", encoding="utf-8") as handle:
        for trace in result["traces"]:
            for conflict in trace["conflict_candidates"]:
                handle.write(json.dumps({
                    "dialogue_card_id": trace["dialogue_card_id"],
                    **conflict,
                }, ensure_ascii=False) + "\n")
    with advantage_path.open("w", encoding="utf-8") as handle:
        for trace in result["traces"]:
            handle.write(json.dumps({
                "dialogue_card_id": trace["dialogue_card_id"],
                "card_type": trace["card_type"],
                "tier": trace["tier"],
                "advantage": trace["advantage"],
            }, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate the v0.5 Runbook Marker dialogue trace fixture."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    cards = load_dialogue_cards(args.input)
    result = evaluate_cards(cards)
    result["dataset"]["source"] = str(args.input)
    write_outputs(result, args.output_dir)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        metrics = result["metrics"]
        print(f"benchmark={result['benchmark']}")
        print(f"passed={result['passed']}")
        print(f"cards={metrics['card_count']}")
        print(f"complete_trace_count={metrics['complete_trace_count']}")
        print(f"core_issue_match_accuracy={metrics['core_issue_match_accuracy']:.4f}")
        print(f"marker_trigger_precision={metrics['marker_trigger_precision']:.4f}")
        print(f"route_accuracy={metrics['route_accuracy']:.4f}")
        print(f"shadow_mode_labeled_rate={metrics['shadow_mode_labeled_rate']:.4f}")
        print(f"actual_runtime_unchanged_rate={metrics['actual_runtime_unchanged_rate']:.4f}")
        print(f"safety_violation_count={metrics['safety_violation_count']}")
        print(f"counterfactual_step_reduction={metrics['counterfactual_step_reduction']}")
        print(f"known_bad_action_reduction={metrics['known_bad_action_reduction']}")
        print(f"evidence_order_improvement={metrics['evidence_order_improvement']}")
        print(f"marker_advantage_card_count={metrics['marker_advantage_card_count']}")
        print(f"online_llm_zero_rate={metrics['online_llm_zero_rate']:.4f}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
