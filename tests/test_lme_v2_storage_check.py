import json

from benchmarks.lme_v2_storage_check import run
from tests.test_longmemeval_v2_adapter_v0_6_4a import _make_lme_v2_fixture


def test_lme_v2_storage_check_writes_report(tmp_path):
    snapshot = _make_lme_v2_fixture(tmp_path)
    output_dir = tmp_path / "storage-check"
    result = run(output_dir, input_root=snapshot, hf_cache_root=tmp_path / "hf_cache")

    assert result["passed"] is True
    for name in ["storage_report.json", "metrics.json", "README.md"]:
        assert (output_dir / name).exists()

    report = json.loads((output_dir / "storage_report.json").read_text(encoding="utf-8"))
    assert report["root_resolution_source"] == "explicit"
    assert report["resolved_root"] == str(snapshot)
    assert report["can_build_external_records"] is True
