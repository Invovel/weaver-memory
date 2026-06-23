"""v0.6.4 external dataset adapter spike.

This validation uses local mini-fixtures that mimic the field shapes of three
public external benchmarks:

- ai-hyz/MemoryAgentBench
- mteb/LongMemEval
- mteb/LoCoMo

It validates conversion into MemoryWeaver canonical external episodes, RawSpan,
ContextCapsule, and Layer-1 candidate dry-runs. It does not download data, call
LLMs, promote memory, or mutate Layer 3.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks._safety import safe_rmtree_child
from benchmarks.context_capsule_validation import write_json, write_jsonl
from memoryweaver.external.adapters import (
    adapt_external_record,
    build_candidate_memories,
    build_context_capsules,
    external_episode_to_raw_spans,
)
from memoryweaver.external.schema import ExternalEpisode
from memoryweaver.schema import Source
from memoryweaver.store import MemoryWorkspace


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT / "docs" / "validation" / "external-dataset-adapter-v0.6.4"
)
DATASET_LINKS = {
    "memoryagentbench": "https://huggingface.co/datasets/ai-hyz/MemoryAgentBench",
    "longmemeval": "https://huggingface.co/datasets/mteb/LongMemEval",
    "locomo": "https://huggingface.co/datasets/mteb/LoCoMo",
}


FIXTURE_RECORDS: dict[str, list[dict[str, Any]]] = {
    "memoryagentbench": [
        {
            "id": "mab_conflict_001",
            "split": "validation",
            "task_type": "conflict_resolution",
            "history": [
                {
                    "role": "user",
                    "content": (
                        "The deployment target changed from staging to production "
                        "after yesterday's correction."
                    ),
                    "timestamp": "2026-01-02T09:00:00+00:00",
                    "tags": ["deployment", "correction", "conflict"],
                },
                {
                    "role": "assistant",
                    "content": "Assume staging is still the safest target unless told otherwise.",
                    "timestamp": "2026-01-02T09:01:00+00:00",
                    "tags": ["deployment", "staging", "hypothesis"],
                },
                {
                    "role": "tool",
                    "content": (
                        '{"status": "ok", "key": "target", '
                        '"message": "production selected"}'
                    ),
                    "timestamp": "2026-01-02T09:03:00+00:00",
                    "tags": ["tool", "production"],
                },
            ],
            "question": "Which deployment target should be used now after the conflict?",
            "answer": "production",
        },
        {
            "id": "mab_ttl_001",
            "split": "validation",
            "task_type": "test_time_learning",
            "history": [
                {
                    "role": "user",
                    "content": (
                        "When npm auth fails with E401, refresh login before "
                        "reinstalling packages."
                    ),
                    "timestamp": "2026-01-03T10:00:00+00:00",
                    "tags": ["npm", "auth", "E401"],
                },
                {
                    "role": "terminal",
                    "content": "$ npm whoami\nerror E401 auth failed\nexit_code=1",
                    "timestamp": "2026-01-03T10:02:00+00:00",
                    "tags": ["terminal", "npm", "E401"],
                },
            ],
            "question": "What should be checked first for a recent npm E401 auth failure?",
            "answer": "refresh login",
        },
    ],
    "longmemeval": [
        {
            "id": "lme_temporal_001",
            "split": "validation",
            "question_type": "temporal",
            "sessions": [
                {
                    "role": "user",
                    "content": "Before March, CI usually finished in 4 minutes.",
                    "timestamp": "2026-03-01T08:00:00+00:00",
                    "tags": ["ci", "temporal", "old"],
                },
                {
                    "role": "tool",
                    "content": (
                        '{"status": "ok", "message": '
                        '"latest CI duration is 8 minutes"}'
                    ),
                    "timestamp": "2026-03-10T08:00:00+00:00",
                    "tags": ["ci", "latest", "duration"],
                },
            ],
            "query": "What is the latest CI duration?",
            "answer": "8 minutes",
        },
        {
            "id": "lme_preference_001",
            "split": "validation",
            "question_type": "preference",
            "sessions": [
                {
                    "role": "user",
                    "content": "For Python projects, prefer pytest -q for quick smoke validation.",
                    "timestamp": "2026-03-11T08:00:00+00:00",
                    "tags": ["python", "pytest", "preference"],
                }
            ],
            "query": "Which quick test command should be preferred?",
            "answer": "pytest -q",
        },
    ],
    "locomo": [
        {
            "id": "locomo_multi_hop_001",
            "split": "validation",
            "reasoning_type": "multi-hop temporal",
            "conversation": [
                {
                    "speaker": "user",
                    "text": "My travel plan changed after the hotel check-in moved to Friday.",
                    "timestamp": "2026-04-01T12:00:00+00:00",
                    "tags": ["travel", "changed", "friday"],
                },
                {
                    "speaker": "assistant",
                    "text": "The old Thursday check-in might still be useful.",
                    "timestamp": "2026-04-01T12:01:00+00:00",
                    "tags": ["travel", "old", "hypothesis"],
                },
            ],
            "queries": [
                {
                    "id": "locomo_q1",
                    "query": "Which hotel check-in day is current after the change?",
                    "answer": "Friday",
                    "tags": ["travel", "temporal", "changed"],
                }
            ],
        },
        {
            "id": "locomo_adversarial_001",
            "split": "validation",
            "reasoning_type": "adversarial",
            "conversation": [
                {
                    "speaker": "user",
                    "text": "Correction: do not use the legacy API key for billing requests.",
                    "timestamp": "2026-04-02T12:00:00+00:00",
                    "tags": ["api", "billing", "correction"],
                },
                {
                    "speaker": "assistant",
                    "text": "The legacy API key may still work for billing if it exists.",
                    "timestamp": "2026-04-02T12:01:00+00:00",
                    "tags": ["api", "billing", "legacy"],
                },
            ],
            "queries": [
                {
                    "id": "locomo_q2",
                    "query": "Should the legacy API key be used for billing requests?",
                    "answer": "No",
                    "tags": ["api", "billing", "conflict"],
                }
            ],
        },
    ],
}


def evaluate_external_fixture(records_by_dataset: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    episodes: list[ExternalEpisode] = []
    conversion_errors: list[dict[str, str]] = []
    for dataset_id, records in records_by_dataset.items():
        for index, record in enumerate(records):
            try:
                episodes.append(adapt_external_record(dataset_id, record))
            except (TypeError, ValueError) as exc:
                conversion_errors.append(
                    {"dataset_id": dataset_id, "index": str(index), "error": str(exc)}
                )

    raw_spans = []
    for episode in episodes:
        raw_spans.extend(external_episode_to_raw_spans(episode))
    capsules = build_context_capsules(raw_spans)
    memories, policy_violations = build_candidate_memories(capsules)

    source_known_count = sum(1 for raw_span in raw_spans if raw_span.source != Source.UNKNOWN)
    query_count = sum(len(episode.queries) for episode in episodes)
    answered_query_count = sum(
        1 for episode in episodes for query in episode.queries if query.query and query.answer
    )
    signal_types = [
        signal
        for episode in episodes
        for query in episode.queries
        for signal in query.signal_types
    ]
    raw_ids = {raw_span.id for raw_span in raw_spans}
    raw_ref_hits = sum(1 for capsule in capsules if capsule.raw_ref_id in raw_ids)
    source_inheritance_violations = sum(
        1
        for capsule in capsules
        if capsule.metadata.get("raw_source")
        and capsule.metadata.get("raw_source") != capsule.source.value
    )
    capsule_build_errors = sum(1 for capsule in capsules if not capsule.summary or not capsule.raw_ref_id)
    sample_count = sum(len(records) for records in records_by_dataset.values())

    metrics = {
        "dataset_count": len(records_by_dataset),
        "sample_count": sample_count,
        "episode_count": len(episodes),
        "conversion_success_rate": round(len(episodes) / sample_count, 4) if sample_count else 0.0,
        "raw_span_count": len(raw_spans),
        "capsule_count": len(capsules),
        "candidate_memory_count": len(memories),
        "raw_ref_coverage": round(raw_ref_hits / len(capsules), 4) if capsules else 0.0,
        "source_mapping_coverage": round(source_known_count / len(raw_spans), 4) if raw_spans else 0.0,
        "capsule_build_success_rate": round((len(capsules) - capsule_build_errors) / len(raw_spans), 4)
        if raw_spans
        else 0.0,
        "query_answer_pair_coverage": round(answered_query_count / query_count, 4) if query_count else 0.0,
        "conflict_signal_count": signal_types.count("conflict"),
        "temporal_signal_count": signal_types.count("temporal"),
        "tool_signal_count": signal_types.count("tool"),
        "policy_gate_leak_count": len(policy_violations),
        "source_inheritance_violation_count": source_inheritance_violations,
        "memory_promotion_count": sum(1 for item in memories if item.layer.value != 1),
        "layer3_mutation_count": 0,
        "online_llm_call_count": 0,
    }
    hard_gates = {
        "conversion_success_rate": metrics["conversion_success_rate"] >= 0.95,
        "raw_ref_coverage": metrics["raw_ref_coverage"] == 1.0,
        "capsule_build_success_rate": metrics["capsule_build_success_rate"] >= 0.95,
        "query_answer_pair_coverage": metrics["query_answer_pair_coverage"] >= 0.95,
        "policy_gate_leak_count": metrics["policy_gate_leak_count"] == 0,
        "source_inheritance_violation_count": metrics["source_inheritance_violation_count"] == 0,
        "conflict_signal_count": metrics["conflict_signal_count"] > 0,
        "temporal_signal_count": metrics["temporal_signal_count"] > 0,
        "memory_promotion_count": metrics["memory_promotion_count"] == 0,
        "layer3_mutation_count": metrics["layer3_mutation_count"] == 0,
        "online_llm_call_count": metrics["online_llm_call_count"] == 0,
    }
    return {
        "validation": "external-dataset-adapter-v0.6.4",
        "passed": all(hard_gates.values()) and not conversion_errors,
        "datasets": [
            {
                "dataset_id": dataset_id,
                "source": DATASET_LINKS[dataset_id],
                "fixture_records": len(records),
                "adapter_mode": "local_schema_fixture",
            }
            for dataset_id, records in records_by_dataset.items()
        ],
        "metrics": metrics,
        "hard_gates": hard_gates,
        "conversion_errors": conversion_errors,
        "policy_violations": policy_violations,
        "converted_samples": [episode.to_dict() for episode in episodes],
        "capsules": [capsule.to_dict() for capsule in capsules],
        "candidate_memories": [memory.to_dict() for memory in memories],
    }


def write_readme(output_dir: Path, result: dict[str, Any]) -> None:
    metrics = result["metrics"]
    text = f"""# v0.6.4 External Dataset Adapter Spike

This validation checks whether external benchmark-shaped rows can enter the
MemoryWeaver data pipeline without bypassing the trust boundary.

Datasets represented by local schema fixtures:

- ai-hyz/MemoryAgentBench
- mteb/LongMemEval
- mteb/LoCoMo

This is not an official benchmark score. It is an adapter spike:
external row -> ExternalEpisode -> RawSpan -> ContextCapsule -> Layer-1
candidate dry-run -> policy gate dry-run.

## Result

- Passed: {result['passed']}
- Dataset count: {metrics['dataset_count']}
- Sample count: {metrics['sample_count']}
- Conversion success rate: {metrics['conversion_success_rate']}
- Raw ref coverage: {metrics['raw_ref_coverage']}
- Capsule build success rate: {metrics['capsule_build_success_rate']}
- Policy gate leak count: {metrics['policy_gate_leak_count']}
- Conflict signal count: {metrics['conflict_signal_count']}
- Temporal signal count: {metrics['temporal_signal_count']}

## Boundaries

- No online dataset download.
- No LLM call.
- No real tool execution.
- No verified memory write.
- No memory promotion.
- No Layer-3 mutation.

## Interpretation

v0.6.4 proves that the first external benchmark adapter path is structurally
viable. It does not prove task success, answer accuracy, or live agent
behavior. Those remain for v0.6.3 live loop and later external dataset
evaluation.
"""
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "README.md").write_text(text, encoding="utf-8")


def write_outputs(result: dict[str, Any], output_dir: Path) -> None:
    write_json(output_dir / "raw_results.json", result)
    write_json(output_dir / "metrics_summary.json", result["metrics"])
    write_json(
        output_dir / "adapter_manifest.json",
        {
            "validation": result["validation"],
            "adapter_mode": "local_schema_fixture",
            "datasets": result["datasets"],
            "hard_gates": result["hard_gates"],
        },
    )
    write_jsonl(output_dir / "converted_samples.jsonl", result["converted_samples"])
    write_jsonl(output_dir / "capsules.jsonl", result["capsules"])
    write_jsonl(output_dir / "candidate_memories.jsonl", result["candidate_memories"])
    write_readme(output_dir, result)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args(argv)
    output_dir = Path(args.output_dir)
    workspace_root = output_dir / ".memoryweaver-external-workspace"
    safe_rmtree_child(
        output_dir,
        workspace_root,
        allowed_prefixes=(".memoryweaver-external-workspace",),
    )
    MemoryWorkspace(workspace_root)
    result = evaluate_external_fixture(FIXTURE_RECORDS)
    write_outputs(result, output_dir)
    print(
        json.dumps(
            {
                "validation": result["validation"],
                "passed": result["passed"],
                "metrics": result["metrics"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
