"""Run Layer-3 Path Promotion over real LongMemEval-V2 snapshot data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks._safety import safe_rmtree_child
from benchmarks.context_capsule_validation import write_json, write_jsonl
from memoryweaver.evaluation import run_lme_v2_path_promotion


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "validation" / "layer3-path-promotion-lme-v2"


def write_readme(output_dir: Path, result: dict[str, object]) -> None:
    metrics = result["metrics"]
    snapshot = result["snapshot"]
    text = f"""# Layer-3 Path Promotion over LongMemEval-V2

This validation runs the Layer-3 path-promotion flow on a small real
LongMemEval-V2 snapshot subset.

## Result

- Passed: {result['passed']}
- Resolved root: {snapshot.get('resolved_root', '')}
- Root source: {snapshot.get('root_resolution_source', '')}
- Question count: {snapshot.get('question_count', 0)}
- Loaded trajectories: {snapshot.get('loaded_trajectory_count', 0)}
- Derived families: {metrics.get('real_snapshot_family_count', 0)}

## Metrics

| Metric | Value |
| --- | ---: |
| stable_promotion_rate | {metrics['stable_promotion_rate']} |
| latest_path_selection_accuracy | {metrics['latest_path_selection_accuracy']} |
| skill_path_selection_accuracy | {metrics['skill_path_selection_accuracy']} |
| harness_path_selection_accuracy | {metrics['harness_path_selection_accuracy']} |
| stale_path_suppression_rate | {metrics['stale_path_suppression_rate']} |
| rollback_success_rate | {metrics['rollback_success_rate']} |
| false_stable_promotion_count | {metrics['false_stable_promotion_count']} |
| average_path_regret | {metrics['average_path_regret']} |

## Files

- `raw_results.json`
- `snapshot.json`
- `families.jsonl`
- `path_catalog.jsonl`
- `task_runs.jsonl`
- `metrics.json`
- `derivation_samples.jsonl`

## Interpretation

This run is not a full open-world benchmark. It is the minimal real-data bridge:
LongMemEval-V2 snapshot -> derived path families -> Layer-3 promotion ->
best-path selection / stale-path suppression / rollback checks.
"""
    (output_dir / "README.md").write_text(text, encoding="utf-8")


def run(
    output_dir: Path,
    *,
    input_root: Path | None = None,
    question_limit: int = 5,
    trajectories_per_question: int = 1,
    states_per_trajectory: int = 2,
    max_observation_chars: int = 1800,
    haystack_name: str = "lme_v2_small.json",
    hf_cache_root: Path | None = None,
    allow_download: bool = False,
) -> dict[str, object]:
    workspace_root = output_dir / ".memoryweaver-lme-v2-path-promotion"
    safe_rmtree_child(
        output_dir,
        workspace_root,
        allowed_prefixes=(".memoryweaver-lme-v2-path-promotion",),
    )
    result = run_lme_v2_path_promotion(
        workspace_root,
        input_root=input_root,
        question_limit=question_limit,
        trajectories_per_question=trajectories_per_question,
        states_per_trajectory=states_per_trajectory,
        max_observation_chars=max_observation_chars,
        haystack_name=haystack_name,
        hf_cache_root=hf_cache_root,
        allow_download=allow_download,
    ).to_dict()
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "raw_results.json", result)
    write_json(output_dir / "snapshot.json", result["snapshot"])
    write_json(output_dir / "metrics.json", result["metrics"])
    write_jsonl(output_dir / "families.jsonl", result["families"])
    write_jsonl(output_dir / "path_catalog.jsonl", result["path_catalog"])
    write_jsonl(output_dir / "task_runs.jsonl", result["task_runs"])
    write_jsonl(output_dir / "derivation_samples.jsonl", result["derivation_samples"])
    write_readme(output_dir, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--input-root", type=Path, default=None)
    parser.add_argument("--question-limit", type=int, default=5)
    parser.add_argument("--trajectories-per-question", type=int, default=1)
    parser.add_argument("--states-per-trajectory", type=int, default=2)
    parser.add_argument("--max-observation-chars", type=int, default=1800)
    parser.add_argument("--haystack-name", default="lme_v2_small.json")
    parser.add_argument("--hf-cache-root", type=Path, default=None)
    parser.add_argument("--download-if-missing", action="store_true")
    args = parser.parse_args(argv)
    result = run(
        args.output_dir,
        input_root=args.input_root,
        question_limit=args.question_limit,
        trajectories_per_question=args.trajectories_per_question,
        states_per_trajectory=args.states_per_trajectory,
        max_observation_chars=args.max_observation_chars,
        haystack_name=args.haystack_name,
        hf_cache_root=args.hf_cache_root,
        allow_download=args.download_if_missing,
    )
    print(json.dumps({"passed": result["passed"], "metrics": result["metrics"]}, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
