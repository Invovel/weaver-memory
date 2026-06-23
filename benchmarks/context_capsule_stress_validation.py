"""Stress ContextCapsule with dialogue-derived RawSpans.

This validation extends the fixed v0.5.3 RawSpan fixture with v0.5 Runbook
dialogue cards. It verifies that multi-turn user corrections, assistant
hypotheses, tool/terminal observations, queries, and trace records can enter
the RAW-to-capsule layer without changing trust, losing raw recovery, or
creating memory/pattern side effects.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks._safety import safe_rmtree_child
from benchmarks.context_capsule_validation import (
    DEFAULT_OUTPUT_DIR as BASE_OUTPUT_DIR,
    evaluate_fixture,
    read_jsonl,
    write_json,
    write_jsonl,
)
from memoryweaver.context_schema import ContentType
from memoryweaver.schema import Source


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_FIXTURE = BASE_OUTPUT_DIR / "raw_spans_fixture.jsonl"
DEFAULT_DIALOGUE_CARDS = (
    REPO_ROOT
    / "docs"
    / "validation"
    / "runbook-marker-v0.5"
    / "dialogue_cards.jsonl"
)
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT
    / "docs"
    / "validation"
    / "context-capsule-stress-v0.5.3x"
)


def _source(value: str) -> Source:
    try:
        return Source(value)
    except ValueError:
        return Source.UNKNOWN


def _event_content_type(source: Source) -> ContentType:
    if source == Source.TERMINAL:
        return ContentType.TERMINAL_LOG
    if source == Source.TOOL:
        return ContentType.TOOL_JSON
    return ContentType.CONVERSATION_TURN


def _expected(tags: list[str], *must_include: str) -> dict[str, Any]:
    return {
        "required_tags": sorted({tag for tag in tags if tag}),
        "must_include": [item for item in must_include if item],
        "must_preserve_source": True,
        "must_preserve_timestamp": True,
        "raw_retrievable": True,
    }


def _timestamp(card_index: int, turn: int, offset: int = 0) -> str:
    minute = min(59, turn + offset)
    return f"2026-06-05T{10 + card_index:02d}:{minute:02d}:00Z"


def event_to_raw_span(card: dict[str, Any], event: dict[str, Any], card_index: int) -> dict[str, Any]:
    source = _source(str(event.get("source", Source.UNKNOWN.value)))
    tags = [str(tag) for tag in event.get("tags", [])]
    event_id = str(event["event_id"])
    turn = int(event.get("turn", 0))
    content_type = _event_content_type(source)
    text = str(event.get("content", ""))
    if content_type == ContentType.TOOL_JSON:
        content = json.dumps({
            "status": event.get("polarity", "ambiguous"),
            "id": event_id,
            "message": text,
            "code": "_".join(tags[:3]).upper(),
        }, ensure_ascii=False)
        must_include = event_id
    else:
        content = (
            f"dialogue_card={card['dialogue_card_id']} turn={turn} "
            f"tags={' '.join(tags)} text={text}"
        )
        must_include = "dialogue_card="
    return {
        "raw_span_id": f"stress_{event_id}",
        "content_type": content_type.value,
        "source": source.value,
        "timestamp": _timestamp(card_index, turn),
        "content": content,
        "metadata": {
            "dialogue_card_id": card["dialogue_card_id"],
            "event_id": event_id,
            "turn": turn,
            "speaker": source.value,
            "intent": event.get("polarity", "observation"),
            "original_tags": tags,
            "card_type": card.get("card_type", ""),
        },
        "expected_capsule": _expected(tags, must_include),
    }


def query_to_raw_span(card: dict[str, Any], query: dict[str, Any], card_index: int) -> dict[str, Any]:
    expected = query.get("expected_evidence", [])
    marker = str(query.get("expected_marker_activation", ""))
    tags = [
        *[str(tag) for tag in expected],
        str(query.get("expected_core_issue_match", "")),
        marker,
    ]
    query_id = str(query["query_id"])
    content = (
        f"dialogue_card={card['dialogue_card_id']} query_id={query_id} "
        f"expected_marker={marker} tags={' '.join(tags)} text={query.get('query', '')}"
    )
    return {
        "raw_span_id": f"stress_{query_id}",
        "content_type": ContentType.CONVERSATION_TURN.value,
        "source": Source.USER.value,
        "timestamp": _timestamp(card_index, int(query.get("turn", 0)), offset=1),
        "content": content,
        "metadata": {
            "dialogue_card_id": card["dialogue_card_id"],
            "query_id": query_id,
            "speaker": Source.USER.value,
            "intent": "query",
            "decision": marker,
        },
        "expected_capsule": _expected(tags, "expected_marker="),
    }


def trace_to_raw_span(card: dict[str, Any], query: dict[str, Any], card_index: int) -> dict[str, Any]:
    expected = card.get("expected", {})
    should = expected.get("should", {})
    must = expected.get("must", {})
    marker = str(query.get("expected_marker_activation", must.get("marker_activation", "")))
    trace = {
        "dialogue_card_id": card["dialogue_card_id"],
        "query_id": query["query_id"],
        "activated_marker": marker,
        "recommended_route": should.get("recommended_route", "fast_verify"),
        "required_evidence": should.get("required_evidence", []),
        "suppressed_actions": should.get("suppressed_actions", []),
        "shadow_mode": must.get("shadow_mode", True),
        "counterfactual": card.get("counterfactual", {}),
    }
    tags = [
        marker,
        "trace_record",
        *[str(item) for item in should.get("required_evidence", [])],
        *[str(item) for item in should.get("suppressed_actions", [])],
    ]
    return {
        "raw_span_id": f"stress_trace_{query['query_id']}",
        "content_type": ContentType.TRACE_RECORD.value,
        "source": Source.TOOL.value,
        "timestamp": _timestamp(card_index, int(query.get("turn", 0)), offset=2),
        "content": json.dumps(trace, ensure_ascii=False, sort_keys=True),
        "metadata": {
            "dialogue_card_id": card["dialogue_card_id"],
            "query_id": query["query_id"],
            "marker": marker,
            "card_type": card.get("card_type", ""),
        },
        "expected_capsule": _expected(tags, marker),
    }


def dialogue_cards_to_raw_spans(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for card_index, card in enumerate(cards):
        for event in card.get("events", []):
            records.append(event_to_raw_span(card, event, card_index))
        for query in card.get("queries", []):
            records.append(query_to_raw_span(card, query, card_index))
            records.append(trace_to_raw_span(card, query, card_index))
    return records


def evaluate_stress(
    *,
    base_fixture: Path,
    dialogue_cards_path: Path,
    workspace_root: Path,
) -> dict[str, Any]:
    base_records = read_jsonl(base_fixture)
    cards = read_jsonl(dialogue_cards_path)
    dialogue_records = dialogue_cards_to_raw_spans(cards)
    records = [*base_records, *dialogue_records]
    result = evaluate_fixture(
        records,
        workspace_root,
        require_full_fixture=True,
    )
    result["validation"] = "context-capsule-stress-v0.5.3x"
    result["dialogue_cards"] = {
        "source": str(dialogue_cards_path),
        "card_count": len(cards),
        "dialogue_raw_span_count": len(dialogue_records),
        "base_raw_span_count": len(base_records),
    }
    result["metrics"] = {
        **result["metrics"],
        "card_count": len(cards),
        "dialogue_raw_span_count": len(dialogue_records),
        "combined_raw_span_count": len(records),
        "assistant_capsule_count": sum(
            1 for capsule in result["capsules"] if capsule["source"] == Source.ASSISTANT.value
        ),
    }
    result["hard_gates"] = {
        **result["hard_gates"],
        "dialogue_card_count": len(cards) >= 50,
        "dialogue_raw_span_count": len(dialogue_records) >= 300,
        "combined_raw_span_count": len(records) >= 340,
        "assistant_capsules_remain_assistant": (
            result["metrics"]["assistant_capsule_count"] > 0
        ),
    }
    result["passed"] = (
        result["passed"]
        and all(result["hard_gates"].values())
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-fixture", default=str(DEFAULT_BASE_FIXTURE))
    parser.add_argument("--dialogue-cards", default=str(DEFAULT_DIALOGUE_CARDS))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    workspace_root = output_dir / ".memoryweaver-context-stress"
    safe_rmtree_child(
        output_dir,
        workspace_root,
        allowed_prefixes=(".memoryweaver-context-stress",),
    )
    result = evaluate_stress(
        base_fixture=Path(args.base_fixture),
        dialogue_cards_path=Path(args.dialogue_cards),
        workspace_root=workspace_root,
    )
    dialogue_records = dialogue_cards_to_raw_spans(read_jsonl(Path(args.dialogue_cards)))
    write_json(output_dir / "raw_results.json", result)
    write_json(output_dir / "metrics_summary.json", result["metrics"])
    write_jsonl(output_dir / "dialogue_raw_spans.jsonl", dialogue_records)
    write_jsonl(output_dir / "capsules.jsonl", result["capsules"])
    write_jsonl(output_dir / "marker_context_results.jsonl", result["marker_context_results"])
    print(json.dumps({
        "validation": result["validation"],
        "passed": result["passed"],
        "metrics": result["metrics"],
    }, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
