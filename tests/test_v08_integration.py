import json

from benchmarks.v08_integration_validation import run
from memoryweaver import run_v08_integration


def test_v08_integration_substrate_preserves_authority_boundary(tmp_path):
    result = run_v08_integration(tmp_path / ".memoryweaver-v08")

    assert result.passed is True
    metrics = result.metrics
    assert metrics["rag_evidence_hit_count"] >= 2
    assert metrics["citation_coverage"] == 1.0
    assert metrics["hyde_synthetic_not_promoted"] is True
    assert metrics["verified_memory_write_count"] == 0
    assert metrics["layer3_mutation_count"] == 0
    assert metrics["promotion_without_hard_evidence_count"] == 0
    assert metrics["gbrain_authority_granted"] is False
    assert metrics["specialist_run_count"] >= 3
    assert metrics["l0_run_count"] == 1
    assert metrics["l1_run_count"] >= 2
    assert metrics["checkpoint_resume_success"] is True


def test_v08_integration_benchmark_writes_reproducible_artifacts(tmp_path):
    output_dir = tmp_path / "v08-integration"
    result = run(output_dir, reliability_passes=3, seed=80)

    assert result["passed"] is True
    assert result["reliability"]["pass_power_3"] is True
    for name in [
        "raw_results.json",
        "metrics.json",
        "evidence_packet.json",
        "specialist_runs.jsonl",
        "rag_hits.jsonl",
        "gbrain_search.json",
        "gbrain_think.json",
        "mind_map.json",
        "checkpoint_probe.json",
        "reliability.json",
        "README.md",
    ]:
        assert (output_dir / name).exists()

    metrics = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["verified_memory_write_count"] == 0
    assert metrics["layer3_mutation_count"] == 0
    assert metrics["promotion_without_hard_evidence_count"] == 0
