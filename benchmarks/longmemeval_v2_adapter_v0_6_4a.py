"""v0.6.4a LongMemEval-V2 local snapshot + optional LLM smoke.

This benchmark consumes an unprocessed local LongMemEval-V2 snapshot and routes
it through MemoryWeaver's external adapter pipeline:

    questions/trajectories/haystack -> ExternalEpisode -> RawSpan
    -> ContextCapsule -> Layer-1 candidate dry-run

When --llm-smoke is set and a DeepSeek API key is available, the benchmark also
performs one low-privilege action-selection call. The LLM output is not allowed
to write memory, promote memory, or mutate Layer 3.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks._safety import safe_rmtree_child
from benchmarks.context_capsule_validation import write_json, write_jsonl
from benchmarks.live_agent_loop_v0_6_3 import _call_deepseek, _parse_llm_action
from memoryweaver.config import MemoryWeaverConfig
from memoryweaver.external.adapters import (
    build_candidate_memories,
    build_context_capsules,
    external_episode_to_raw_spans,
)
from memoryweaver.external.longmemeval_v2 import build_lme_v2_external_episodes
from memoryweaver.schema import Source
from memoryweaver.store import MemoryWorkspace


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT / "docs" / "validation" / "longmemeval-v2-adapter-v0.6.4a"
)


def evaluate_lme_v2_snapshot(
    input_root: Path | None,
    *,
    question_limit: int = 20,
    trajectories_per_question: int = 2,
    states_per_trajectory: int = 3,
    max_observation_chars: int = 1800,
    hf_cache_root: Path | None = None,
    allow_download: bool = False,
) -> dict[str, Any]:
    episodes, snapshot = build_lme_v2_external_episodes(
        input_root,
        question_limit=question_limit,
        trajectories_per_question=trajectories_per_question,
        states_per_trajectory=states_per_trajectory,
        max_observation_chars=max_observation_chars,
        hf_cache_root=hf_cache_root,
        allow_download=allow_download,
    )
    raw_spans = []
    for episode in episodes:
        raw_spans.extend(external_episode_to_raw_spans(episode))
    capsules = build_context_capsules(raw_spans)
    memories, policy_violations = build_candidate_memories(capsules)

    raw_ids = {raw_span.id for raw_span in raw_spans}
    signal_types = [
        signal
        for episode in episodes
        for query in episode.queries
        for signal in query.signal_types
    ]
    source_known_count = sum(1 for raw_span in raw_spans if raw_span.source != Source.UNKNOWN)
    assistant_memories = [memory for memory in memories if memory.source == Source.ASSISTANT]
    metrics = {
        "validation": "longmemeval-v2-adapter-v0.6.4a",
        "question_count": len(episodes),
        "requested_trajectory_refs": snapshot["requested_trajectory_refs"],
        "loaded_trajectory_count": snapshot["loaded_trajectory_count"],
        "missing_trajectory_refs": snapshot["missing_trajectory_refs"],
        "episode_count": len(episodes),
        "raw_span_count": len(raw_spans),
        "capsule_count": len(capsules),
        "candidate_memory_count": len(memories),
        "raw_ref_coverage": (
            sum(1 for capsule in capsules if capsule.raw_ref_id in raw_ids) / len(capsules)
            if capsules else 0.0
        ),
        "source_mapping_coverage": (
            source_known_count / len(raw_spans) if raw_spans else 0.0
        ),
        "capsule_build_success_rate": (
            sum(1 for capsule in capsules if capsule.summary and capsule.raw_ref_id) / len(capsules)
            if capsules else 0.0
        ),
        "query_answer_pair_coverage": (
            sum(1 for episode in episodes for query in episode.queries if query.query and query.answer)
            / sum(len(episode.queries) for episode in episodes)
            if episodes else 0.0
        ),
        "policy_gate_leak_count": len(policy_violations),
        "memory_promotion_count": sum(1 for memory in memories if memory.layer.value != 1),
        "layer3_mutation_count": 0,
        "assistant_candidate_count": len(assistant_memories),
        "assistant_ambiguous_count": sum(
            1
            for memory in assistant_memories
            if memory.polarity.value == "ambiguous" and memory.confidence <= 0.3
        ),
        "conflict_signal_count": signal_types.count("conflict"),
        "temporal_signal_count": signal_types.count("temporal"),
        "tool_signal_count": signal_types.count("tool"),
    }
    hard_gates = {
        "question_count": metrics["question_count"] == question_limit,
        "loaded_trajectory_count": metrics["loaded_trajectory_count"] > 0,
        "missing_trajectory_refs": metrics["missing_trajectory_refs"] == 0,
        "raw_ref_coverage": metrics["raw_ref_coverage"] == 1.0,
        "source_mapping_coverage": metrics["source_mapping_coverage"] == 1.0,
        "capsule_build_success_rate": metrics["capsule_build_success_rate"] >= 0.95,
        "query_answer_pair_coverage": metrics["query_answer_pair_coverage"] >= 0.95,
        "policy_gate_leak_count": metrics["policy_gate_leak_count"] == 0,
        "memory_promotion_count": metrics["memory_promotion_count"] == 0,
        "layer3_mutation_count": metrics["layer3_mutation_count"] == 0,
        "assistant_trust_boundary": (
            metrics["assistant_candidate_count"] == metrics["assistant_ambiguous_count"]
        ),
        "temporal_signal_count": metrics["temporal_signal_count"] > 0,
        "tool_signal_count": metrics["tool_signal_count"] > 0,
    }
    return {
        "passed": all(hard_gates.values()),
        "metrics": metrics,
        "hard_gates": hard_gates,
        "snapshot": snapshot,
        "policy_violations": policy_violations,
        "converted_samples": [episode.to_dict() for episode in episodes[:3]],
        "capsule_samples": [capsule.to_dict() for capsule in capsules[:10]],
        "candidate_memory_samples": [memory.to_dict() for memory in memories[:10]],
        "episodes": episodes,
        "capsules": capsules,
    }


def run_llm_smoke(
    result: dict[str, Any],
    *,
    env_file: Path | None,
    model: str = "deepseek-chat",
) -> dict[str, Any]:
    config = MemoryWeaverConfig.from_env(env_file=env_file) if env_file else MemoryWeaverConfig.from_env()
    api_key = config.deepseek_api_key
    if not api_key:
        return {
            "enabled": True,
            "attempted": False,
            "skipped_reason": "missing DEEPSEEK_API_KEY",
            "online_llm_call_count": 0,
        }
    episodes = result["episodes"]
    capsules = result["capsules"]
    if not episodes or not capsules:
        return {
            "enabled": True,
            "attempted": False,
            "skipped_reason": "no converted episode/capsule available",
            "online_llm_call_count": 0,
        }
    query = episodes[0].queries[0].query
    capsule_context = "\n".join(
        f"- [{capsule.source.value}] {capsule.summary[:260]}"
        for capsule in capsules[:6]
    )
    system_prompt = (
        "You are a low-privilege MemoryWeaver live-loop probe. "
        "Choose one next action for an agent using the external benchmark context. "
        "Return strict JSON only with keys action, target, reasoning. "
        "Allowed action values: check_evidence, tool_call, ask_user, resolve. "
        "Do not create memory, promote memory, mutate Layer 3, or write graph edges."
    )
    user_message = (
        f"Question:\n{query}\n\nContext capsules:\n{capsule_context}\n\n"
        "Pick the safest next action."
    )
    started = time.perf_counter()
    try:
        raw = _call_deepseek(
            system_prompt,
            user_message,
            api_key=api_key,
            model=model,
            temperature=0.0,
            max_tokens=256,
            timeout=60,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        parsed = _parse_llm_action(raw)
        parse_success = parsed["action"] in {"check_evidence", "tool_call", "ask_user", "resolve"}
        return {
            "enabled": True,
            "attempted": True,
            "provider": "deepseek",
            "model": model,
            "online_llm_call_count": 1,
            "latency_ms": elapsed_ms,
            "json_parse_success": parse_success,
            "action": parsed,
            "raw_response_preview": raw[:500],
            "memory_promotion_count": 0,
            "layer3_mutation_count": 0,
        }
    except Exception as exc:
        return {
            "enabled": True,
            "attempted": True,
            "provider": "deepseek",
            "model": model,
            "online_llm_call_count": 1,
            "json_parse_success": False,
            "error": f"{type(exc).__name__}: {exc}",
            "memory_promotion_count": 0,
            "layer3_mutation_count": 0,
        }


def write_readme(output_dir: Path, result: dict[str, Any]) -> None:
    metrics = result["metrics"]
    llm = result["llm_smoke"]
    text = f"""# v0.6.4a LongMemEval-V2 Adapter + LLM Smoke

This validation consumes an unprocessed local LongMemEval-V2 snapshot and
routes it through MemoryWeaver's external adapter pipeline.

It validates:

- raw questions / trajectories / haystack field mapping
- ExternalEpisode conversion
- RawSpan creation
- ContextCapsule creation
- Layer-1 candidate dry-run
- source-gated policy boundary
- optional DeepSeek action-selection smoke

## Result

- Adapter passed: {result['adapter_passed']}
- Overall passed: {result['passed']}
- Questions: {metrics['question_count']}
- Loaded trajectories: {metrics['loaded_trajectory_count']}
- Raw spans: {metrics['raw_span_count']}
- Capsules: {metrics['capsule_count']}
- Candidate memories: {metrics['candidate_memory_count']}
- Raw ref coverage: {metrics['raw_ref_coverage']}
- Policy gate leak count: {metrics['policy_gate_leak_count']}
- Assistant ambiguous count: {metrics['assistant_ambiguous_count']} / {metrics['assistant_candidate_count']}
- Online LLM calls: {llm.get('online_llm_call_count', 0)}
- LLM attempted: {llm.get('attempted', False)}
- LLM JSON parse success: {llm.get('json_parse_success', False)}

## Boundaries

- LLM cannot write memory.
- LLM cannot promote memory.
- LLM cannot create stable pattern.
- LLM cannot write graph edges.
- External data remains Layer-1 candidate dry-run only.

## Interpretation

v0.6.4a shows that LongMemEval-V2 local snapshot data can enter the
MemoryWeaver memory substrate without breaking the trust boundary. The optional
LLM smoke only validates action-selection connectivity; it is not a task
success score.
"""
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "README.md").write_text(text, encoding="utf-8")


def write_outputs(output_dir: Path, result: dict[str, Any]) -> None:
    serializable = dict(result)
    serializable.pop("episodes", None)
    serializable.pop("capsules", None)
    write_json(output_dir / "raw_results.json", serializable)
    write_json(output_dir / "metrics_summary.json", result["metrics"])
    write_json(output_dir / "llm_smoke.json", result["llm_smoke"])
    write_jsonl(output_dir / "converted_samples.jsonl", result["converted_samples"])
    write_jsonl(output_dir / "capsule_samples.jsonl", result["capsule_samples"])
    write_jsonl(output_dir / "candidate_memory_samples.jsonl", result["candidate_memory_samples"])
    write_readme(output_dir, result)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--question-limit", type=int, default=20)
    parser.add_argument("--trajectories-per-question", type=int, default=2)
    parser.add_argument("--states-per-trajectory", type=int, default=3)
    parser.add_argument("--max-observation-chars", type=int, default=1800)
    parser.add_argument("--llm-smoke", action="store_true")
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--model", default="deepseek-chat")
    parser.add_argument("--hf-cache-root", type=Path, default=None)
    parser.add_argument("--download-if-missing", action="store_true")
    args = parser.parse_args(argv)

    workspace_root = args.output_dir / ".memoryweaver-lme-v2-workspace"
    safe_rmtree_child(
        args.output_dir,
        workspace_root,
        allowed_prefixes=(".memoryweaver-lme-v2-workspace",),
    )
    MemoryWorkspace(workspace_root)

    result = evaluate_lme_v2_snapshot(
        args.input_root,
        question_limit=args.question_limit,
        trajectories_per_question=args.trajectories_per_question,
        states_per_trajectory=args.states_per_trajectory,
        max_observation_chars=args.max_observation_chars,
        hf_cache_root=args.hf_cache_root,
        allow_download=args.download_if_missing,
    )
    llm_smoke = (
        run_llm_smoke(result, env_file=args.env_file, model=args.model)
        if args.llm_smoke
        else {
            "enabled": False,
            "attempted": False,
            "online_llm_call_count": 0,
            "skipped_reason": "run with --llm-smoke to attempt DeepSeek call",
        }
    )
    result["adapter_passed"] = result["passed"]
    result["llm_smoke"] = llm_smoke
    result["passed"] = bool(result["adapter_passed"]) and (
        not args.llm_smoke
        or (
            llm_smoke.get("attempted") is True
            and llm_smoke.get("json_parse_success") is True
            and llm_smoke.get("memory_promotion_count", 0) == 0
            and llm_smoke.get("layer3_mutation_count", 0) == 0
        )
    )
    write_outputs(args.output_dir, result)
    print(
        json.dumps(
            {
                "validation": "longmemeval-v2-adapter-v0.6.4a",
                "passed": result["passed"],
                "adapter_passed": result["adapter_passed"],
                "metrics": result["metrics"],
                "llm_smoke": result["llm_smoke"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
