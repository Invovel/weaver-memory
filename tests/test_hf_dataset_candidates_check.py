import json

from benchmarks.hf_dataset_candidates_check import run


def _catalog(path):
    payload = {
        "primary_dataset": {
            "id": "owner/primary",
            "url": "https://hf.co/datasets/owner/primary",
            "exists_on_hf": True,
            "license": "mit",
            "size_category": "n<1K",
            "memoryweaver_status": "adapter_exists_local_snapshot_validated",
        },
        "candidates": [
            {
                "id": "owner/candidate",
                "url": "https://hf.co/datasets/owner/candidate",
                "exists_on_hf": True,
                "license": "apache-2.0",
                "size_category": "1K<n<10K",
                "memoryweaver_status": "not_integrated",
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_hf_dataset_candidates_check_static_boundaries(tmp_path):
    output_dir = tmp_path / "hf-check"
    result = run(output_dir, catalog_path=_catalog(tmp_path / "catalog.json"), live=False)

    assert result["passed"] is True
    assert result["metrics"]["dataset_count"] == 2
    assert result["metrics"]["integrated_dataset_count"] == 1
    assert result["metrics"]["boundary_violation_count"] == 0
    for name in ["metrics.json", "candidate_checks.jsonl", "live_metadata.json", "raw_results.json", "README.md"]:
        assert (output_dir / name).exists()


def test_hf_dataset_candidates_check_rejects_integrated_candidate(tmp_path):
    catalog_path = _catalog(tmp_path / "catalog.json")
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    payload["candidates"][0]["memoryweaver_status"] = "adapter_exists_local_snapshot_validated"
    catalog_path.write_text(json.dumps(payload), encoding="utf-8")

    result = run(tmp_path / "hf-check", catalog_path=catalog_path, live=False)

    assert result["passed"] is False
    assert result["metrics"]["boundary_violation_count"] == 1


def test_hf_dataset_candidates_check_allows_preview_adapter_candidate(tmp_path):
    catalog_path = _catalog(tmp_path / "catalog.json")
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    payload["candidates"][0]["memoryweaver_status"] = "preview_adapter_validated"
    catalog_path.write_text(json.dumps(payload), encoding="utf-8")

    result = run(tmp_path / "hf-check", catalog_path=catalog_path, live=False)

    assert result["passed"] is True
    assert result["metrics"]["preview_adapter_validated_count"] == 1
    assert result["metrics"]["integrated_dataset_count"] == 1
