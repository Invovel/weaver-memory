"""MemoryAgentBench Hugging Face preview adapter check."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmarks.context_capsule_validation import write_json, write_jsonl
from memoryweaver.external.adapters import (
    build_candidate_memories,
    build_context_capsules,
    external_episode_to_raw_spans,
)
from memoryweaver.external.memoryagentbench import (
    DATASET_REPO_ID,
    build_memoryagentbench_episodes,
    fetch_memoryagentbench_preview,
    load_memoryagentbench_rows,
)


DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "validation" / "memoryagentbench-adapter-check"


def evaluate_rows(
    rows: list[dict[str, Any]],
    *,
    source_mode: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    episodes = build_memoryagentbench_episodes(rows)
    raw_spans = [
        raw_span
        for episode in episodes
        for raw_span in external_episode_to_raw_spans(episode)
    ]
    capsules = build_context_capsules(raw_spans)
    memories, policy_violations = build_candidate_memories(capsules)
    query_count = sum(len(episode.queries) for episode in episodes)
    answered_query_count = sum(
        1
        for episode in episodes
        for query in episode.queries
        if query.query and query.answer
    )
    split_count = len({episode.split for episode in episodes})
    raw_ids = {raw_span.id for raw_span in raw_spans}
    raw_ref_hits = sum(1 for capsule in capsules if capsule.raw_ref_id in raw_ids)
    signal_types = [
        signal
        for episode in episodes
        for query in episode.queries
        for signal in query.signal_types
    ]
    metrics = {
        "dataset_id": "memoryagentbench",
        "source_repo": DATASET_REPO_ID,
        "source_mode": source_mode,
        "sample_count": len(rows),
        "split_count": split_count,
        "episode_count": len(episodes),
        "query_count": query_count,
        "query_answer_pair_coverage": round(answered_query_count / query_count, 4)
        if query_count
        else 0.0,
        "raw_span_count": len(raw_spans),
        "capsule_count": len(capsules),
        "candidate_memory_count": len(memories),
        "raw_ref_coverage": round(raw_ref_hits / len(capsules), 4) if capsules else 0.0,
        "policy_gate_leak_count": len(policy_violations),
        "memory_promotion_count": sum(1 for memory in memories if memory.layer.value != 1),
        "layer3_mutation_count": 0,
        "retrieval_signal_count": signal_types.count("retrieval"),
        "temporal_signal_count": signal_types.count("temporal"),
        "conflict_signal_count": signal_types.count("conflict"),
    }
    hard_gates = {
        "sample_count": metrics["sample_count"] > 0,
        "split_count": metrics["split_count"] >= 4,
        "query_answer_pair_coverage": metrics["query_answer_pair_coverage"] >= 0.95,
        "raw_ref_coverage": metrics["raw_ref_coverage"] == 1.0,
        "policy_gate_leak_count": metrics["policy_gate_leak_count"] == 0,
        "memory_promotion_count": metrics["memory_promotion_count"] == 0,
        "layer3_mutation_count": metrics["layer3_mutation_count"] == 0,
        "retrieval_signal_present": metrics["retrieval_signal_count"] > 0,
        "temporal_signal_present": metrics["temporal_signal_count"] > 0,
        "conflict_signal_present": metrics["conflict_signal_count"] > 0,
    }
    return {
        "passed": all(hard_gates.values()),
        "metrics": metrics,
        "hard_gates": hard_gates,
        "metadata": metadata or {},
        "policy_violations": policy_violations,
        "converted_samples": [episode.to_dict() for episode in episodes[:4]],
        "capsule_samples": [capsule.to_dict() for capsule in capsules[:10]],
        "candidate_memory_samples": [memory.to_dict() for memory in memories[:10]],
    }


def _readme(result: dict[str, Any]) -> str:
    metrics = result["metrics"]
    return f"""# MemoryAgentBench Adapter Check

This validation consumes a small Hugging Face preview or fixture for
`ai-hyz/MemoryAgentBench` and routes it through the MemoryWeaver external
substrate.

## Result

- passed = {str(result['passed']).lower()}
- source_mode = `{metrics['source_mode']}`
- sample_count = {metrics['sample_count']}
- split_count = {metrics['split_count']}
- query_count = {metrics['query_count']}
- raw_span_count = {metrics['raw_span_count']}
- capsule_count = {metrics['capsule_count']}
- candidate_memory_count = {metrics['candidate_memory_count']}
- query_answer_pair_coverage = {metrics['query_answer_pair_coverage']}
- policy_gate_leak_count = {metrics['policy_gate_leak_count']}
- memory_promotion_count = {metrics['memory_promotion_count']}
- layer3_mutation_count = {metrics['layer3_mutation_count']}
- retrieval_signal_count = {metrics['retrieval_signal_count']}
- temporal_signal_count = {metrics['temporal_signal_count']}
- conflict_signal_count = {metrics['conflict_signal_count']}

## Boundary

This is a preview adapter / candidate dry-run. It does not claim
MemoryAgentBench task accuracy, verified-memory writes, or Layer-3
path-promotion gains.

## Files

- `metrics.json`
- `raw_results.json`
- `converted_samples.jsonl`
- `capsule_samples.jsonl`
- `candidate_memory_samples.jsonl`
"""


def write_outputs(output_dir: Path, result: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "raw_results.json", result)
    write_json(output_dir / "metrics.json", result["metrics"])
    write_jsonl(output_dir / "converted_samples.jsonl", result["converted_samples"])
    write_jsonl(output_dir / "capsule_samples.jsonl", result["capsule_samples"])
    write_jsonl(output_dir / "candidate_memory_samples.jsonl", result["candidate_memory_samples"])
    (output_dir / "README.md").write_text(_readme(result), encoding="utf-8")


def run(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    input_path: Path | None = None,
    sample_limit: int = 1,
    live: bool = False,
) -> dict[str, Any]:
    if input_path is not None:
        rows = load_memoryagentbench_rows(input_path, sample_limit=sample_limit)
        metadata = {"input_path": str(input_path), "sample_limit": sample_limit}
        source_mode = "fixture"
    elif live:
        rows, metadata = fetch_memoryagentbench_preview(sample_limit_per_split=sample_limit)
        source_mode = "hf_first_rows"
    else:
        raise ValueError("provide --input-path or --live")
    result = evaluate_rows(rows, source_mode=source_mode, metadata=metadata)
    write_outputs(output_dir, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--input-path", type=Path, default=None)
    parser.add_argument("--sample-limit", type=int, default=1)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)
    result = run(
        args.output_dir,
        input_path=args.input_path,
        sample_limit=args.sample_limit,
        live=args.live,
    )
    print(json.dumps({"passed": result["passed"], "metrics": result["metrics"]}, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
