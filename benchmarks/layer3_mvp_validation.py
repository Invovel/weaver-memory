"""Run the minimal Layer-3 candidate -> provisional -> trial -> stable validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks._safety import safe_rmtree_child
from benchmarks.context_capsule_validation import write_json, write_jsonl
from memoryweaver.evaluation import run_layer3_mvp


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "validation" / "layer3-mvp"


def run(output_dir: Path) -> dict[str, object]:
    workspace_root = output_dir / ".memoryweaver-layer3-mvp"
    safe_rmtree_child(
        output_dir,
        workspace_root,
        allowed_prefixes=(".memoryweaver-layer3-mvp",),
    )
    result = run_layer3_mvp(workspace_root).to_dict()
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "raw_results.json", result)
    write_json(output_dir / "metrics.json", result["metrics"])
    write_jsonl(output_dir / "task_runs.jsonl", result["task_runs"])
    write_jsonl(output_dir / "path_catalog.jsonl", result["path_catalog"])
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    result = run(args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
