"""Run MemoryWeaver v0.7 Random Experience Accumulation Protocol."""

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
    RandomExperienceAccumulationProtocol,
    default_experience_families,
)
from memoryweaver.runtime import OpenAICompatibleAgent


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "validation" / "random-experience-v0.7"


def write_readme(output_dir: Path, result: dict) -> None:
    arm = result["arm_metrics"]
    config = result.get("run_config", {})
    mode = "live LLM" if config.get("llm") else "deterministic local policy"
    text = f"""# v0.7 Random Experience Accumulation Protocol

This validation measures whether random/noisy prior experience causes false
triggering compared with curated verified MemoryWeaver experience.

Protocol:

```text
random unrelated experience families -> relevant sibling target family
```

Arms:

- A. `fresh_no_memory`
- B. `random_experience_raw_logs`
- C. `random_experience_naive_memory`
- D. `mw_verified_experience`
- E. `mw_verified_experience_marker`

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

| Arm | Tasks | Success | Avg Steps | Known Bad | Invalid Actions | False Trigger | Spurious Retrieval | Evidence First | Retrieval Before Critical | Token Avg | LLM Calls |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fresh_no_memory | {arm['fresh_no_memory']['task_count']} | {arm['fresh_no_memory']['success_rate']} | {arm['fresh_no_memory']['average_steps_to_success']} | {arm['fresh_no_memory']['known_bad_action_attempts']} | {arm['fresh_no_memory']['invalid_action_count']} | {arm['fresh_no_memory']['false_trigger_rate']} | {arm['fresh_no_memory']['spurious_retrieval_rate']} | {arm['fresh_no_memory']['required_evidence_first_hit_rate']} | {arm['fresh_no_memory']['retrieval_hit_before_critical_action_rate']} | {arm['fresh_no_memory']['average_token_estimate']} | {arm['fresh_no_memory']['online_llm_call_count']} |
| random_experience_raw_logs | {arm['random_experience_raw_logs']['task_count']} | {arm['random_experience_raw_logs']['success_rate']} | {arm['random_experience_raw_logs']['average_steps_to_success']} | {arm['random_experience_raw_logs']['known_bad_action_attempts']} | {arm['random_experience_raw_logs']['invalid_action_count']} | {arm['random_experience_raw_logs']['false_trigger_rate']} | {arm['random_experience_raw_logs']['spurious_retrieval_rate']} | {arm['random_experience_raw_logs']['required_evidence_first_hit_rate']} | {arm['random_experience_raw_logs']['retrieval_hit_before_critical_action_rate']} | {arm['random_experience_raw_logs']['average_token_estimate']} | {arm['random_experience_raw_logs']['online_llm_call_count']} |
| random_experience_naive_memory | {arm['random_experience_naive_memory']['task_count']} | {arm['random_experience_naive_memory']['success_rate']} | {arm['random_experience_naive_memory']['average_steps_to_success']} | {arm['random_experience_naive_memory']['known_bad_action_attempts']} | {arm['random_experience_naive_memory']['invalid_action_count']} | {arm['random_experience_naive_memory']['false_trigger_rate']} | {arm['random_experience_naive_memory']['spurious_retrieval_rate']} | {arm['random_experience_naive_memory']['required_evidence_first_hit_rate']} | {arm['random_experience_naive_memory']['retrieval_hit_before_critical_action_rate']} | {arm['random_experience_naive_memory']['average_token_estimate']} | {arm['random_experience_naive_memory']['online_llm_call_count']} |
| mw_verified_experience | {arm['mw_verified_experience']['task_count']} | {arm['mw_verified_experience']['success_rate']} | {arm['mw_verified_experience']['average_steps_to_success']} | {arm['mw_verified_experience']['known_bad_action_attempts']} | {arm['mw_verified_experience']['invalid_action_count']} | {arm['mw_verified_experience']['false_trigger_rate']} | {arm['mw_verified_experience']['spurious_retrieval_rate']} | {arm['mw_verified_experience']['required_evidence_first_hit_rate']} | {arm['mw_verified_experience']['retrieval_hit_before_critical_action_rate']} | {arm['mw_verified_experience']['average_token_estimate']} | {arm['mw_verified_experience']['online_llm_call_count']} |
| mw_verified_experience_marker | {arm['mw_verified_experience_marker']['task_count']} | {arm['mw_verified_experience_marker']['success_rate']} | {arm['mw_verified_experience_marker']['average_steps_to_success']} | {arm['mw_verified_experience_marker']['known_bad_action_attempts']} | {arm['mw_verified_experience_marker']['invalid_action_count']} | {arm['mw_verified_experience_marker']['false_trigger_rate']} | {arm['mw_verified_experience_marker']['spurious_retrieval_rate']} | {arm['mw_verified_experience_marker']['required_evidence_first_hit_rate']} | {arm['mw_verified_experience_marker']['retrieval_hit_before_critical_action_rate']} | {arm['mw_verified_experience_marker']['average_token_estimate']} | {arm['mw_verified_experience_marker']['online_llm_call_count']} |

## Files

- `experience_families.jsonl`
- `task_runs.jsonl`
- `arm_metrics.json`
- `cost_metrics.json`
- `raw_results.json`

## Interpretation

This protocol is designed to expose when raw logs or naive memory convert
unrelated experience into current-task actions. MemoryWeaver should preserve
verified retrieval while keeping false-trigger and spurious-retrieval rates at
zero.
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
) -> dict:
    workspace_root = output_dir / ".memoryweaver-random-experience"
    safe_rmtree_child(
        output_dir,
        workspace_root,
        allowed_prefixes=(".memoryweaver-random-experience",),
    )
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

    result = RandomExperienceAccumulationProtocol(
        workspace_root=workspace_root,
        families=_limited_families(family_limit=family_limit, target_limit=target_limit),
        agent_factory=agent_factory,
    ).run().to_dict()
    result["run_config"] = {
        "llm": llm,
        "provider": provider if llm else "",
        "model": model if llm else "",
        "base_url": base_url if llm else "",
        "family_limit": family_limit,
        "target_limit": target_limit,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "raw_results.json", result)
    write_jsonl(output_dir / "experience_families.jsonl", result["families"])
    write_jsonl(output_dir / "task_runs.jsonl", result["task_runs"])
    write_json(output_dir / "arm_metrics.json", result["arm_metrics"])
    write_json(output_dir / "cost_metrics.json", result["cost_metrics"])
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
    )
    print(json.dumps({"passed": result["passed"], "arm_metrics": result["arm_metrics"]}, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
