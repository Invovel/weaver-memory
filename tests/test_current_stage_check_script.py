import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "current_stage_check.py"
SPEC = importlib.util.spec_from_file_location("current_stage_check_script", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_parse_pytest_summary_handles_pass_and_fail_counts():
    summary = MODULE.parse_pytest_summary("1 failed, 269 passed in 154.64s")
    assert summary["failed"] == 1
    assert summary["passed"] == 269
    assert summary["ok"] is False

    passed = MODULE.parse_pytest_summary("270 passed in 120.00s")
    assert passed["failed"] == 0
    assert passed["passed"] == 270
    assert passed["ok"] is True


def test_extract_readme_benchmark_rows_reads_table():
    text = """
| Memory items | JSON size | Write throughput | Verified text search p95 |
| ---: | ---: | ---: | ---: |
| 100 | 75 KB | 266.08 items/s | 0.27 ms |
| 500 | 378 KB | 81.57 items/s | 1.46 ms |
"""
    rows = MODULE.extract_readme_benchmark_rows(text)
    assert rows[100]["json_size_kb"] == 75.0
    assert rows[500]["write_items_per_second"] == 81.57


def test_extract_readme_benchmark_rows_reads_chinese_header():
    text = """
| Memory items | JSON 大小 | 写入吞吐 | Verified text search p95 |
| ---: | ---: | ---: | ---: |
| 100 | 75 KB | 266.08 items/s | 0.27 ms |
"""
    rows = MODULE.extract_readme_benchmark_rows(text)
    assert rows[100]["verified_search_p95_ms"] == 0.27


def test_compare_readme_benchmark_claims_detects_drift():
    text = """
| Memory items | JSON size | Write throughput | Verified text search p95 |
| ---: | ---: | ---: | ---: |
| 100 | 75 KB | 266.08 items/s | 0.27 ms |
"""
    baseline = {
        "performance": [
            {
                "items": 100,
                "json_bytes": 91465,
                "write": {"items_per_second": 108.16},
                "verified_search": {"p95_ms": 1.82},
            }
        ]
    }
    differences = MODULE.compare_readme_benchmark_claims(text, baseline, source_name="README.md")
    fields = {item["field"] for item in differences}
    assert "json_size_kb" in fields
    assert "write_items_per_second" in fields
    assert "verified_search_p95_ms" in fields


def test_find_transient_root_entries_filters_expected_names(tmp_path):
    (tmp_path / ".memoryweaver-audit").mkdir()
    (tmp_path / ".tmp-layer3").mkdir()
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs").mkdir()
    found = [item.name for item in MODULE.find_transient_root_entries(tmp_path)]
    assert found == [".memoryweaver-audit", ".tmp-layer3"]
