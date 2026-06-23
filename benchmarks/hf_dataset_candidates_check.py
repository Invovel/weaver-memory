"""Validate Hugging Face dataset candidate metadata and claim boundaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmarks.context_capsule_validation import write_json, write_jsonl


DEFAULT_CANDIDATES = REPO_ROOT / "docs" / "validation" / "hf-dataset-candidates.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "validation" / "hf-dataset-candidates-check"


def _records(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    primary = dict(catalog["primary_dataset"])
    primary["role"] = "primary"
    candidates = [dict(item, role="candidate") for item in catalog.get("candidates", [])]
    return [primary] + candidates


def _normalize(value: Any) -> str:
    if isinstance(value, list):
        return ",".join(sorted(str(item).lower() for item in value))
    return str(value or "").lower()


def _api_metadata(repo_id: str) -> dict[str, Any]:
    url = f"https://huggingface.co/api/datasets/{quote(repo_id, safe='/')}"
    request = Request(url, headers={"User-Agent": "MemoryWeaver-validation/0.1"})
    with urlopen(request, timeout=45) as response:
        data = json.load(response)
    tags = data.get("tags") or []
    card = data.get("cardData") or {}
    license_value = card.get("license") or next(
        (tag.split(":", 1)[1] for tag in tags if tag.startswith("license:")),
        "",
    )
    size_categories = card.get("size_categories") or [
        tag.split(":", 1)[1] for tag in tags if tag.startswith("size_categories:")
    ]
    return {
        "id": repo_id,
        "exists_on_hf": True,
        "downloads": data.get("downloads"),
        "likes": data.get("likes"),
        "created_at": data.get("createdAt"),
        "last_modified": data.get("lastModified"),
        "license": license_value,
        "size_categories": size_categories,
        "tags": tags,
        "url": f"https://hf.co/datasets/{repo_id}",
    }


def _should_compare_size(expected: str) -> bool:
    return bool(expected and ("<" in expected or expected.startswith("n<")))


def _evaluate_record(record: dict[str, Any], live: dict[str, Any] | None) -> dict[str, Any]:
    expected_license = _normalize(record.get("license"))
    live_license = _normalize(live.get("license")) if live else ""
    expected_size = str(record.get("size_category", ""))
    live_sizes = [_normalize(item) for item in (live or {}).get("size_categories", [])]
    license_matches = (
        live is None
        or not expected_license
        or expected_license in live_license
        or live_license in expected_license
    )
    size_matches = (
        live is None
        or not _should_compare_size(expected_size)
        or _normalize(expected_size) in live_sizes
    )
    return {
        "id": record["id"],
        "role": record["role"],
        "expected_status": record.get("memoryweaver_status", ""),
        "expected_license": record.get("license", ""),
        "expected_size_category": expected_size,
        "live_checked": live is not None,
        "live_exists_on_hf": bool(live and live.get("exists_on_hf")),
        "live_license": live.get("license", "") if live else "",
        "live_size_categories": live.get("size_categories", []) if live else [],
        "license_matches": license_matches,
        "size_matches": size_matches,
        "boundary_ok": (
            record["role"] == "primary"
            and record.get("memoryweaver_status") == "adapter_exists_local_snapshot_validated"
        )
        or (
            record["role"] == "candidate"
            and record.get("memoryweaver_status") in {"not_integrated", "preview_adapter_validated"}
        ),
    }


def _readme(result: dict[str, Any]) -> str:
    metrics = result["metrics"]
    lines = [
        "# Hugging Face Dataset Candidates Check",
        "",
        "This validation checks MemoryWeaver's Hugging Face dataset candidate list.",
        "",
        f"passed = {str(result['passed']).lower()}",
        f"live_checked = {str(result['live_checked']).lower()}",
        "",
        "## Metrics",
        "",
    ]
    for key, value in metrics.items():
        lines.append(f"- `{key}` = {value}")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "Only `xiaowu0162/longmemeval-v2` should be marked as integrated.",
            "Candidate datasets may be `not_integrated` or `preview_adapter_validated`, but only LME-V2 is an integrated external path-promotion dataset.",
            "",
            "## Files",
            "",
            "- `metrics.json`",
            "- `candidate_checks.jsonl`",
            "- `live_metadata.json`",
            "- `raw_results.json`",
            "",
        ]
    )
    return "\n".join(lines)


def run(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    catalog_path: Path = DEFAULT_CANDIDATES,
    live: bool = False,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    records = _records(catalog)
    live_metadata: dict[str, Any] = {}
    live_errors: dict[str, str] = {}
    if live:
        for record in records:
            try:
                live_metadata[record["id"]] = _api_metadata(record["id"])
            except Exception as exc:  # pragma: no cover - depends on network
                live_errors[record["id"]] = str(exc)

    checks = [
        _evaluate_record(record, live_metadata.get(record["id"]))
        for record in records
    ]
    metrics = {
        "dataset_count": len(records),
        "primary_dataset_count": sum(1 for item in checks if item["role"] == "primary"),
        "candidate_dataset_count": sum(1 for item in checks if item["role"] == "candidate"),
        "integrated_dataset_count": sum(
            1
            for item in checks
            if item["expected_status"] == "adapter_exists_local_snapshot_validated"
        ),
        "not_integrated_candidate_count": sum(
            1
            for item in checks
            if item["role"] == "candidate" and item["expected_status"] == "not_integrated"
        ),
        "preview_adapter_validated_count": sum(
            1
            for item in checks
            if item["role"] == "candidate" and item["expected_status"] == "preview_adapter_validated"
        ),
        "boundary_violation_count": sum(1 for item in checks if not item["boundary_ok"]),
        "live_checked_count": sum(1 for item in checks if item["live_checked"]),
        "live_available_count": sum(1 for item in checks if item["live_exists_on_hf"]),
        "live_error_count": len(live_errors),
        "license_mismatch_count": sum(
            1 for item in checks if item["live_checked"] and not item["license_matches"]
        ),
        "size_mismatch_count": sum(
            1 for item in checks if item["live_checked"] and not item["size_matches"]
        ),
    }
    passed = (
        metrics["dataset_count"] >= 1
        and metrics["primary_dataset_count"] == 1
        and metrics["integrated_dataset_count"] == 1
        and metrics["boundary_violation_count"] == 0
        and (
            not live
            or (
                metrics["live_checked_count"] == metrics["dataset_count"]
                and metrics["live_available_count"] == metrics["dataset_count"]
                and metrics["live_error_count"] == 0
                and metrics["license_mismatch_count"] == 0
                and metrics["size_mismatch_count"] == 0
            )
        )
    )
    result = {
        "passed": passed,
        "live_checked": live,
        "metrics": metrics,
        "checks": checks,
        "live_metadata": live_metadata,
        "live_errors": live_errors,
        "catalog_path": str(catalog_path),
    }
    write_json(output_dir / "metrics.json", metrics)
    write_json(output_dir / "live_metadata.json", live_metadata)
    write_json(output_dir / "raw_results.json", result)
    write_jsonl(output_dir / "candidate_checks.jsonl", checks)
    (output_dir / "README.md").write_text(_readme(result), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)
    result = run(args.output_dir, catalog_path=args.catalog, live=args.live)
    print(json.dumps({"passed": result["passed"], "metrics": result["metrics"]}, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
