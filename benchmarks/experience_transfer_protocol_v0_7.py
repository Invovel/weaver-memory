"""Run MemoryWeaver v0.7 Experience Transfer Protocol."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks._safety import safe_rmtree_child
from benchmarks.context_capsule_validation import write_json, write_jsonl
from memoryweaver.config import MemoryWeaverConfig
from memoryweaver.evaluation import (
    ExperienceFamily,
    ExperienceLLMAgentAdapter,
    ExperienceTransferProtocol,
    default_experience_families,
)
from memoryweaver.runtime import OpenAICompatibleAgent


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "validation" / "experience-transfer-v0.7"


def write_readme(output_dir: Path, result: dict) -> None:
    arm = result["arm_metrics"]
    marker_arm = result.get("marker_only_arm_metrics", {})
    probe_metrics = result.get("probe_metrics", {})
    memory_use_summary = result.get("memory_use_summary", {})
    reliability = result.get("reliability", {})
    config = result.get("run_config", {})
    mode = "live LLM" if config.get("llm") else "deterministic local policy"
    interpretation = (
        "This run uses a live LLM action selector with opaque action ids. It "
        "measures whether external context or MemoryWeaver retrieval can map "
        "those opaque actions to useful evidence before the agent exhausts its "
        "step budget."
        if config.get("llm")
        else "This is the structured deterministic Experience Transfer run. "
        "It compares source-learned verified experience against sibling target "
        "tasks across four arms."
    )
    text = f"""# v0.7 Experience Transfer Protocol

This validation measures experience reuse across sibling task families.

Protocol:

```text
source episode family -> sibling target task family
```

Arms:

- A. `no_memory`
- B. `raw_rag_over_logs`
- C. `mw_verified_memory`
- D. `mw_verified_memory_marker`

## Result

- Passed: {result['passed']}
- Mode: {mode}
- Families: {len(result['families'])}
- Task runs: {len(result['task_runs'])}
- Provider: {config.get('provider', '')}
- Model: {config.get('model', '')}
- Family limit: {config.get('family_limit', 0)}
- Target limit: {config.get('target_limit', 0)}

## Arm Metrics

| Arm | Tasks | Success | Avg Steps | Known Bad | Invalid Actions | Evidence First | Retrieval Before Critical | Token Avg | LLM Calls |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| no_memory | {arm['no_memory']['task_count']} | {arm['no_memory']['success_rate']} | {arm['no_memory']['average_steps_to_success']} | {arm['no_memory']['known_bad_action_attempts']} | {arm['no_memory']['invalid_action_count']} | {arm['no_memory']['required_evidence_first_hit_rate']} | {arm['no_memory']['retrieval_hit_before_critical_action_rate']} | {arm['no_memory']['average_token_estimate']} | {arm['no_memory']['online_llm_call_count']} |
| raw_rag_over_logs | {arm['raw_rag_over_logs']['task_count']} | {arm['raw_rag_over_logs']['success_rate']} | {arm['raw_rag_over_logs']['average_steps_to_success']} | {arm['raw_rag_over_logs']['known_bad_action_attempts']} | {arm['raw_rag_over_logs']['invalid_action_count']} | {arm['raw_rag_over_logs']['required_evidence_first_hit_rate']} | {arm['raw_rag_over_logs']['retrieval_hit_before_critical_action_rate']} | {arm['raw_rag_over_logs']['average_token_estimate']} | {arm['raw_rag_over_logs']['online_llm_call_count']} |
| mw_verified_memory | {arm['mw_verified_memory']['task_count']} | {arm['mw_verified_memory']['success_rate']} | {arm['mw_verified_memory']['average_steps_to_success']} | {arm['mw_verified_memory']['known_bad_action_attempts']} | {arm['mw_verified_memory']['invalid_action_count']} | {arm['mw_verified_memory']['required_evidence_first_hit_rate']} | {arm['mw_verified_memory']['retrieval_hit_before_critical_action_rate']} | {arm['mw_verified_memory']['average_token_estimate']} | {arm['mw_verified_memory']['online_llm_call_count']} |
| mw_verified_memory_marker | {arm['mw_verified_memory_marker']['task_count']} | {arm['mw_verified_memory_marker']['success_rate']} | {arm['mw_verified_memory_marker']['average_steps_to_success']} | {arm['mw_verified_memory_marker']['known_bad_action_attempts']} | {arm['mw_verified_memory_marker']['invalid_action_count']} | {arm['mw_verified_memory_marker']['required_evidence_first_hit_rate']} | {arm['mw_verified_memory_marker']['retrieval_hit_before_critical_action_rate']} | {arm['mw_verified_memory_marker']['average_token_estimate']} | {arm['mw_verified_memory_marker']['online_llm_call_count']} |

## Marker-Only Boundary Metrics

This suite is reported separately and is not averaged into the main task
families.

| Arm | Tasks | Success | Avg Steps | Known Bad | Evidence First | Retrieval Before Critical | Marker Direct Change |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| no_memory | {marker_arm.get('no_memory', {}).get('task_count', 0)} | {marker_arm.get('no_memory', {}).get('success_rate', 0)} | {marker_arm.get('no_memory', {}).get('average_steps_to_success', 0)} | {marker_arm.get('no_memory', {}).get('known_bad_action_attempts', 0)} | {marker_arm.get('no_memory', {}).get('required_evidence_first_hit_rate', 0)} | {marker_arm.get('no_memory', {}).get('retrieval_hit_before_critical_action_rate', 0)} | {marker_arm.get('no_memory', {}).get('marker_direct_action_change_count', 0)} |
| raw_rag_over_logs | {marker_arm.get('raw_rag_over_logs', {}).get('task_count', 0)} | {marker_arm.get('raw_rag_over_logs', {}).get('success_rate', 0)} | {marker_arm.get('raw_rag_over_logs', {}).get('average_steps_to_success', 0)} | {marker_arm.get('raw_rag_over_logs', {}).get('known_bad_action_attempts', 0)} | {marker_arm.get('raw_rag_over_logs', {}).get('required_evidence_first_hit_rate', 0)} | {marker_arm.get('raw_rag_over_logs', {}).get('retrieval_hit_before_critical_action_rate', 0)} | {marker_arm.get('raw_rag_over_logs', {}).get('marker_direct_action_change_count', 0)} |
| mw_verified_memory | {marker_arm.get('mw_verified_memory', {}).get('task_count', 0)} | {marker_arm.get('mw_verified_memory', {}).get('success_rate', 0)} | {marker_arm.get('mw_verified_memory', {}).get('average_steps_to_success', 0)} | {marker_arm.get('mw_verified_memory', {}).get('known_bad_action_attempts', 0)} | {marker_arm.get('mw_verified_memory', {}).get('required_evidence_first_hit_rate', 0)} | {marker_arm.get('mw_verified_memory', {}).get('retrieval_hit_before_critical_action_rate', 0)} | {marker_arm.get('mw_verified_memory', {}).get('marker_direct_action_change_count', 0)} |
| mw_verified_memory_marker | {marker_arm.get('mw_verified_memory_marker', {}).get('task_count', 0)} | {marker_arm.get('mw_verified_memory_marker', {}).get('success_rate', 0)} | {marker_arm.get('mw_verified_memory_marker', {}).get('average_steps_to_success', 0)} | {marker_arm.get('mw_verified_memory_marker', {}).get('known_bad_action_attempts', 0)} | {marker_arm.get('mw_verified_memory_marker', {}).get('required_evidence_first_hit_rate', 0)} | {marker_arm.get('mw_verified_memory_marker', {}).get('retrieval_hit_before_critical_action_rate', 0)} | {marker_arm.get('mw_verified_memory_marker', {}).get('marker_direct_action_change_count', 0)} |

## Probe Hygiene

- Main-suite valid decision-change rate for `mw_verified_memory`:
  {probe_metrics.get('main_suite', {}).get('mw_verified_memory', {}).get('decision_changed_valid_rate', 0)}
- Main-suite invalid `no_memory` probes:
  {probe_metrics.get('main_suite', {}).get('no_memory', {}).get('invalid_probe_count', 0)}
- Marker-boundary valid decision-change rate for `mw_verified_memory_marker`:
  {probe_metrics.get('marker_only_boundary', {}).get('mw_verified_memory_marker', {}).get('decision_changed_valid_rate', 0)}

## Memory Use Diagnosis

- `mw_verified_memory` reason counts:
  {json.dumps(memory_use_summary.get('mw_verified_memory', {}).get('reason_counts', {}), ensure_ascii=False)}
- `mw_verified_memory_marker` reason counts:
  {json.dumps(memory_use_summary.get('mw_verified_memory_marker', {}).get('reason_counts', {}), ensure_ascii=False)}

## Reliability

- pass@1: {reliability.get('pass_at_1', result['passed'])}
- pass^3: {reliability.get('pass_power_3', result['passed'])}
- Seeds: {reliability.get('seeds', [])}

## Files

- `experience_families.jsonl`
- `task_runs.jsonl`
- `arm_metrics.json`
- `marker_only_arm_metrics.json`
- `decision_probe.jsonl`
- `probe_metrics.json`
- `memory_use_probe.jsonl`
- `memory_use_summary.json`
- `cost_metrics.json`
- `reliability.json`
- `raw_results.json`

## Interpretation

{interpretation}
"""
    (output_dir / "README.md").write_text(text, encoding="utf-8")


def run(
    output_dir: Path,
    *,
    llm: bool = False,
    provider: str = "deepseek",
    model: str = "deepseek-chat",
    base_url: str = "",
    env_file: Path | None = None,
    family_limit: int = 0,
    target_limit: int = 0,
    seed: int = 0,
    reliability_passes: int = 1,
) -> dict:
    agent_factory = None
    if llm:
        config = MemoryWeaverConfig.from_env(env_file=env_file)

        def agent_factory():
            return ExperienceLLMAgentAdapter(
                OpenAICompatibleAgent.from_config(
                    config,
                    provider=provider,
                    model=model,
                    base_url=base_url,
                )
            )

    families = _limited_families(
        family_limit=family_limit,
        target_limit=target_limit,
    )
    single_runs: list[dict] = []
    for offset in range(max(reliability_passes, 1)):
        run_seed = seed + offset
        workspace_root = output_dir / f".memoryweaver-experience-transfer-seed-{run_seed}"
        safe_rmtree_child(
            output_dir,
            workspace_root,
            allowed_prefixes=(".memoryweaver-experience-transfer-seed-",),
        )
        result = ExperienceTransferProtocol(
            workspace_root=workspace_root,
            families=families,
            agent_factory=agent_factory,
        ).run().to_dict()
        result["run_config"] = {
            "llm": llm,
            "provider": provider if llm else "",
            "model": model if llm else "",
            "base_url": base_url if llm else "",
            "family_limit": family_limit,
            "target_limit": target_limit,
            "seed": run_seed,
            "reliability_passes": reliability_passes,
        }
        single_runs.append(result)
    result = single_runs[0]
    result["reliability"] = _reliability_summary(single_runs)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "raw_results.json", result)
    write_jsonl(output_dir / "experience_families.jsonl", result["families"])
    write_jsonl(output_dir / "task_runs.jsonl", result["task_runs"])
    write_json(output_dir / "arm_metrics.json", result["arm_metrics"])
    write_json(output_dir / "marker_only_arm_metrics.json", result["marker_only_arm_metrics"])
    write_jsonl(output_dir / "decision_probe.jsonl", result["decision_probe"])
    write_json(output_dir / "probe_metrics.json", result["probe_metrics"])
    write_jsonl(output_dir / "memory_use_probe.jsonl", result["memory_use_probe"])
    write_json(output_dir / "memory_use_summary.json", result["memory_use_summary"])
    write_json(output_dir / "cost_metrics.json", result["cost_metrics"])
    write_json(output_dir / "reliability.json", result["reliability"])
    write_readme(output_dir, result)
    return result


def _limited_families(
    *,
    family_limit: int = 0,
    target_limit: int = 0,
) -> list[ExperienceFamily]:
    families = default_experience_families()
    if family_limit > 0:
        families = families[:family_limit]
    if target_limit > 0:
        limited: list[ExperienceFamily] = []
        for family in families:
            limited.append(
                ExperienceFamily(
                    family_id=family.family_id,
                    title=family.title,
                    source_success=family.source_success,
                    source_failure=family.source_failure,
                    tags=list(family.tags),
                    required_evidence=list(family.required_evidence),
                    known_bad_actions=list(family.known_bad_actions),
                    target_tasks=list(family.target_tasks[:target_limit]),
                )
            )
        families = limited
    return families


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--llm", action="store_true")
    parser.add_argument("--provider", default="deepseek")
    parser.add_argument("--model", default="deepseek-chat")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    parser.add_argument("--family-limit", type=int, default=0)
    parser.add_argument("--target-limit", type=int, default=0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--reliability-passes", type=int, default=1)
    args = parser.parse_args(argv)
    result = run(
        args.output_dir,
        llm=args.llm,
        provider=args.provider,
        model=args.model,
        base_url=args.base_url,
        env_file=args.env_file,
        family_limit=args.family_limit,
        target_limit=args.target_limit,
        seed=args.seed,
        reliability_passes=args.reliability_passes,
    )
    print(json.dumps({"passed": result["passed"], "arm_metrics": result["arm_metrics"]}, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


def _reliability_summary(results: list[dict]) -> dict:
    if not results:
        return {
            "run_count": 0,
            "pass_at_1": False,
            "pass_power_3": False,
            "seeds": [],
            "by_arm": {},
        }
    run_count = len(results)
    arms = list(results[0]["arm_metrics"])
    by_arm: dict[str, dict[str, float | int]] = {}
    for arm in arms:
        avg_steps = [float(result["arm_metrics"][arm]["average_steps_to_success"]) for result in results]
        known_bad = [float(result["arm_metrics"][arm]["known_bad_action_attempts"]) for result in results]
        success = [float(result["arm_metrics"][arm]["success_rate"]) for result in results]
        by_arm[arm] = {
            "pass_at_1": bool(results[0]["passed"]),
            "pass_power_3": all(bool(result["passed"]) for result in results),
            "success_rate_mean": _mean(success),
            "success_rate_std": _std(success),
            "average_steps_mean": _mean(avg_steps),
            "average_steps_std": _std(avg_steps),
            "known_bad_mean": _mean(known_bad),
            "known_bad_std": _std(known_bad),
        }
    return {
        "run_count": run_count,
        "pass_at_1": bool(results[0]["passed"]),
        "pass_power_3": all(bool(result["passed"]) for result in results),
        "seeds": [int(result.get("run_config", {}).get("seed", 0)) for result in results],
        "by_arm": by_arm,
    }


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def _std(values: list[float]) -> float:
    if not values:
        return 0.0
    avg = sum(values) / len(values)
    variance = sum((value - avg) ** 2 for value in values) / len(values)
    return round(variance ** 0.5, 4)


if __name__ == "__main__":
    raise SystemExit(main())
