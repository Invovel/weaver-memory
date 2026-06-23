"""Check local/Hugging Face storage for LongMemEval-V2."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmarks.context_capsule_validation import write_json
from memoryweaver.external.longmemeval_v2 import (
    DEFAULT_HF_CACHE_ROOT,
    inspect_lme_v2_storage,
)


DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "validation" / "lme-v2-storage-check"


def _readme(report: dict[str, Any], passed: bool) -> str:
    return f"""# LongMemEval-V2 Storage Check

This validation records where MemoryWeaver resolves `xiaowu0162/longmemeval-v2`
on the current machine.

## Result

- passed = {str(passed).lower()}
- dataset_repo_id = `{report['dataset_repo_id']}`
- hf_cache_root = `{report['hf_cache_root']}`
- dataset_cache_root_exists = `{str(report['dataset_cache_root_exists']).lower()}`
- refs_main_exists = `{str(report['refs_main_exists']).lower()}`
- refs_snapshot_complete = `{str(report['refs_snapshot_complete']).lower()}`
- complete_cache_snapshot_exists = `{str(report['complete_cache_snapshot_exists']).lower()}`
- root_resolution_source = `{report['root_resolution_source']}`
- resolved_root = `{report['resolved_root']}`
- can_build_external_records = `{str(report['can_build_external_records']).lower()}`

## Interpretation

`hf_cache_root` is a Hugging Face cache root. It is not necessarily a readable
dataset snapshot. A readable LongMemEval-V2 snapshot must contain:

```text
questions.jsonl
trajectories.jsonl
haystacks/lme_v2_small.json
```

If `root_resolution_source = benchmarks`, current evaluation reads from the
local benchmark snapshot while still keeping `hf_cache_root` available for
download/cache behavior.

## Files

- `storage_report.json`
- `metrics.json`
- `README.md`
"""


def run(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    input_root: Path | None = None,
    hf_cache_root: Path | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = inspect_lme_v2_storage(
        input_root,
        hf_cache_root=hf_cache_root or DEFAULT_HF_CACHE_ROOT,
    )
    metrics = {
        "dataset_cache_root_exists": report["dataset_cache_root_exists"],
        "refs_main_exists": report["refs_main_exists"],
        "refs_snapshot_complete": report["refs_snapshot_complete"],
        "complete_cache_snapshot_exists": report["complete_cache_snapshot_exists"],
        "can_build_external_records": report["can_build_external_records"],
        "root_resolution_source": report["root_resolution_source"],
        "resolved_root": report["resolved_root"],
    }
    passed = bool(report["can_build_external_records"])
    result = {
        "passed": passed,
        "metrics": metrics,
        "storage_report": report,
    }
    write_json(output_dir / "storage_report.json", report)
    write_json(output_dir / "metrics.json", metrics)
    (output_dir / "README.md").write_text(_readme(report, passed), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--input-root", type=Path, default=None)
    parser.add_argument("--hf-cache-root", type=Path, default=DEFAULT_HF_CACHE_ROOT)
    args = parser.parse_args(argv)
    result = run(
        args.output_dir,
        input_root=args.input_root,
        hf_cache_root=args.hf_cache_root,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
