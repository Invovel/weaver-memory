"""Run Layer-3 Path Promotion validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks._safety import safe_rmtree_child
from benchmarks.context_capsule_validation import write_json, write_jsonl
from memoryweaver.evaluation import PathPromotionProtocol, run_default_path_promotion


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "validation" / "layer3-path-promotion-v0.7"


def write_readme(output_dir: Path, result: dict[str, object]) -> None:
    metrics = result["metrics"]
    text = f"""# Layer-3 Path Promotion v0.7

This validation measures MemoryWeaver's main claim:

> Layer-3 path promotion turns verified experience into reusable execution paths.

## Result

- Passed: {result['passed']}
- Families: {len(result['families'])}
- Task runs: {len(result['task_runs'])}

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

- `families.jsonl`
- `path_catalog.jsonl`
- `task_runs.jsonl`
- `metrics.json`
- `raw_results.json`

## Interpretation

This suite is not about retrieval speed, marker novelty, or proving that online
LLM calls stayed at zero. It is about whether verified experience can be
promoted into a better Layer-3 execution path, whether stale paths are
suppressed, and whether overgeneralized paths can be rolled back.
"""
    (output_dir / "README.md").write_text(text, encoding="utf-8")


def run(output_dir: Path) -> dict[str, object]:
    workspace_root = output_dir / ".memoryweaver-path-promotion"
    safe_rmtree_child(output_dir, workspace_root, allowed_prefixes=(".memoryweaver-",))
    result = run_default_path_promotion(workspace_root).to_dict()
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "raw_results.json", result)
    write_jsonl(output_dir / "families.jsonl", result["families"])
    write_jsonl(output_dir / "path_catalog.jsonl", result["path_catalog"])
    write_jsonl(output_dir / "task_runs.jsonl", result["task_runs"])
    write_json(output_dir / "metrics.json", result["metrics"])
    write_readme(output_dir, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    result = run(args.output_dir)
    print(json.dumps({"passed": result["passed"], "metrics": result["metrics"]}, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
