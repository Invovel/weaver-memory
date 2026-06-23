from pathlib import Path

from benchmarks.context_capsule_validation import evaluate_fixture, read_jsonl
from memoryweaver.content_router import ContentRouter
from memoryweaver.context_schema import ContentType, MarkerEvidenceContext, RawSpan
from memoryweaver.marker_context import capsules_for_marker_context
from memoryweaver.schema import Source
from memoryweaver.store import MemoryWorkspace


def test_context_capsule_preserves_source_timestamp_and_raw_ref(tmp_path):
    workspace = MemoryWorkspace(tmp_path / ".memoryweaver")
    raw = RawSpan(
        id="raw_assistant_hypothesis",
        content="Maybe reinstall npm first for Codex subscription failure.",
        content_type=ContentType.CONVERSATION_TURN,
        source=Source.ASSISTANT,
        timestamp="2026-06-05T11:00:00Z",
        metadata={"speaker": "assistant", "intent": "hypothesis"},
    )
    workspace.raw_spans.add(raw)

    capsule = ContentRouter().compress(raw)
    workspace.context_capsules.add(capsule)
    workspace.tag_time_index.add(capsule)

    recovered = workspace.raw_spans.get(capsule.raw_ref_id)
    assert recovered is not None
    assert recovered.content == raw.content
    assert capsule.source == Source.ASSISTANT
    assert capsule.timestamp == raw.timestamp
    assert capsule.metadata["raw_source"] == Source.ASSISTANT.value
    assert workspace.context_capsules.validate_raw_refs({raw.id}) == []
    assert workspace.memories.count() == 0


def test_tag_time_index_and_marker_context_retrieve_capsules(tmp_path):
    workspace = MemoryWorkspace(tmp_path / ".memoryweaver")
    router = ContentRouter()
    raw_spans = [
        RawSpan(
            id="raw_terminal_codex",
            content="$ codex --version\n0.12.0\nexit=0",
            content_type=ContentType.TERMINAL_LOG,
            source=Source.TERMINAL,
            timestamp="2026-06-05T10:00:00Z",
            metadata={"command": "codex --version", "exit_code": 0},
        ),
        RawSpan(
            id="raw_tool_subscription",
            content='{"status":"error","code":"SUBSCRIPTION_LOAD_FAILED","id":"evt_001"}',
            content_type=ContentType.TOOL_JSON,
            source=Source.TOOL,
            timestamp="2026-06-05T10:02:00Z",
        ),
    ]
    for raw in raw_spans:
        workspace.raw_spans.add(raw)
        capsule = router.compress(raw)
        workspace.context_capsules.add(capsule)
        workspace.tag_time_index.add(capsule)

    subscription_ids = workspace.tag_time_index.search(
        tags=["subscription"],
        since="2026-06-05T00:00:00Z",
        until="2026-06-06T00:00:00Z",
    )
    assert subscription_ids

    marker_context = MarkerEvidenceContext(
        marker_id="marker_codex_subscription",
        required_tags=["codex", "subscription"],
        required_time_window="2026-06-05T00:00:00Z..2026-06-06T00:00:00Z",
        preferred_content_types=[ContentType.TERMINAL_LOG, ContentType.TOOL_JSON],
    )
    capsules = capsules_for_marker_context(
        marker_context,
        workspace.context_capsules,
        workspace.tag_time_index,
    )
    assert {capsule.raw_ref_id for capsule in capsules} == {
        "raw_terminal_codex",
        "raw_tool_subscription",
    }


def test_context_capsule_validation_fixture_passes(tmp_path):
    fixture = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "validation"
        / "context-capsule-v0.5.3"
        / "raw_spans_fixture.example.jsonl"
    )
    result = evaluate_fixture(read_jsonl(fixture), tmp_path / ".memoryweaver")

    assert result["passed"] is True
    assert result["metrics"]["raw_retrieval_success_rate"] == 1.0
    assert result["metrics"]["trust_inheritance_violation_count"] == 0
    assert result["metrics"]["raw_ref_missing_count"] == 0
    assert result["metrics"]["capsule_promoted_memory_count"] == 0
    assert result["metrics"]["marker_context_hit_rate"] >= 0.8


def test_context_capsule_full_fixture_distribution_passes(tmp_path):
    fixture = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "validation"
        / "context-capsule-v0.5.3"
        / "raw_spans_fixture.jsonl"
    )
    result = evaluate_fixture(
        read_jsonl(fixture),
        tmp_path / ".memoryweaver",
        require_full_fixture=True,
    )

    assert result["passed"] is True
    assert result["metrics"]["raw_span_count"] == 40
    assert result["metrics"]["capsule_count"] == 40
    assert result["metrics"]["content_type_counts"] == {
        "terminal_log": 10,
        "tool_json": 10,
        "conversation_turn": 10,
        "code_patch": 5,
        "trace_record": 5,
    }
    assert result["metrics"]["tag_recall_at_k"] == 1.0
    assert result["metrics"]["tag_miss_count"] == 0
    assert result["hard_gates"]["full_fixture_distribution"] is True
