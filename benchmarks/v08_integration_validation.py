"""Validate the complete v0.8 integration substrate.

This benchmark proves that RAG evidence, GBrain candidate graph, collaborative
specialist routing, and checkpoint/resume can run as one evidence-gated system.
It deliberately does not write verified memory or stable Layer-3 patterns.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmarks._safety import safe_rmtree_child
from benchmarks.context_capsule_validation import write_json, write_jsonl
from memoryweaver.v08_integration import run_v08_integration


DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "validation" / "v0.8-integration"


def run(
    output_dir: Path,
    *,
    reliability_passes: int = 3,
    seed: int = 80,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    primary_workspace = output_dir / ".memoryweaver-v08-primary"
    safe_rmtree_child(output_dir, primary_workspace, allowed_prefixes=(".memoryweaver-v08-primary",))
    primary = run_v08_integration(primary_workspace).to_dict()

    reliability_runs: list[dict[str, Any]] = []
    for offset in range(max(reliability_passes, 1)):
        pass_dir = output_dir / "reliability_runs" / f"v08-pass-{seed + offset:03d}"
        safe_rmtree_child(
            output_dir,
            pass_dir,
            allowed_prefixes=("v08-pass-",),
        )
        result = run_v08_integration(pass_dir).to_dict()
        reliability_runs.append(
            {
                "seed": seed + offset,
                "passed": result["passed"],
                "metrics": result["metrics"],
            }
        )

    reliability = _reliability(reliability_runs)
    result = {
        **primary,
        "reliability": reliability,
        "raw_reliability_runs": reliability_runs,
    }
    _write_artifacts(output_dir, result)
    return result


def _write_artifacts(output_dir: Path, result: dict[str, Any]) -> None:
    write_json(output_dir / "raw_results.json", result)
    write_json(output_dir / "metrics.json", result["metrics"])
    write_json(output_dir / "evidence_packet.json", result["evidence_packet"])
    write_json(output_dir / "gbrain_search.json", result["gbrain_search"])
    write_json(output_dir / "gbrain_think.json", result["gbrain_think"])
    write_json(output_dir / "mind_map.json", result["mind_map"])
    write_json(output_dir / "checkpoint_probe.json", result["checkpoint_probe"])
    write_json(output_dir / "reliability.json", result["reliability"])
    write_jsonl(output_dir / "specialist_runs.jsonl", result["specialist_runs"])
    write_jsonl(output_dir / "rag_hits.jsonl", result["rag_hits"])
    write_jsonl(output_dir / "raw_reliability_runs.jsonl", result["raw_reliability_runs"])
    (output_dir / "README.md").write_text(_readme(result), encoding="utf-8")


def _reliability(runs: list[dict[str, Any]]) -> dict[str, Any]:
    metric_keys = sorted(runs[0]["metrics"]) if runs else []
    aggregates: dict[str, float] = {}
    for key in metric_keys:
        values = [
            float(run["metrics"][key])
            for run in runs
            if isinstance(run["metrics"].get(key), (int, float, bool))
        ]
        if not values:
            continue
        aggregates[f"{key}_mean"] = round(mean(values), 4)
        aggregates[f"{key}_std"] = round(pstdev(values), 4) if len(values) > 1 else 0.0
    return {
        "run_count": len(runs),
        "pass_at_1": bool(runs and runs[0]["passed"]),
        "pass_power_3": all(run["passed"] for run in runs) and len(runs) >= 3,
        "seeds": [run["seed"] for run in runs],
        "aggregates": aggregates,
    }


def _readme(result: dict[str, Any]) -> str:
    metrics = result["metrics"]
    reliability = result["reliability"]
    return f"""# v0.8 Integration Validation

This artifact validates the complete v0.8 build substrate:

- RAG evidence layer returns citable evidence refs.
- GBrain ingests candidate bundles and separates `search` from `think`.
- Collaborative specialists produce an `EvidencePacket`.
- Checkpoint/resume state round-trips through the durable runtime store.
- RAG/GBrain/specialist output does not directly write verified memory or Layer-3 patterns.

## Key Metrics

| metric | value |
| --- | --- |
| rag_evidence_node_count | {metrics['rag_evidence_node_count']} |
| rag_evidence_hit_count | {metrics['rag_evidence_hit_count']} |
| citation_coverage | {metrics['citation_coverage']} |
| hyde_synthetic_not_promoted | {metrics['hyde_synthetic_not_promoted']} |
| verified_memory_write_count | {metrics['verified_memory_write_count']} |
| layer3_mutation_count | {metrics['layer3_mutation_count']} |
| promotion_without_hard_evidence_count | {metrics['promotion_without_hard_evidence_count']} |
| gbrain_candidate_node_count | {metrics['gbrain_candidate_node_count']} |
| gbrain_candidate_edge_count | {metrics['gbrain_candidate_edge_count']} |
| gbrain_authority_granted | {metrics['gbrain_authority_granted']} |
| specialist_run_count | {metrics['specialist_run_count']} |
| evidence_packet_ref_count | {metrics['evidence_packet_ref_count']} |
| checkpoint_resume_success | {metrics['checkpoint_resume_success']} |

## Reliability

- run_count = {reliability['run_count']}
- pass_at_1 = {reliability['pass_at_1']}
- pass^3 = {reliability['pass_power_3']}
- seeds = {reliability['seeds']}

## Claim Boundary

This validates the v0.8 system substrate. It does not claim open-world task
success superiority. v0.9 should optimize and expand benchmark coverage.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--reliability-passes", type=int, default=3)
    parser.add_argument("--seed", type=int, default=80)
    args = parser.parse_args(argv)
    result = run(
        args.output_dir,
        reliability_passes=args.reliability_passes,
        seed=args.seed,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] and result["reliability"]["pass_power_3"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
