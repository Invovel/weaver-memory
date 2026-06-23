# Layer-3 Path Promotion E2E Claim Table

| Claim | Metric | Value | Artifact |
| --- | --- | ---: | --- |
| Layer-3 path improves execution path quality | `path_regret_delta_vs_verified_memory` | -1 | `metrics.json` |
| Layer-3 path selects the latest valid path | `latest_path_selection_accuracy` | 1.0 | `layer3_protocol/task_runs.jsonl` |
| Coding-debug hard evidence is real and repeatable | `tests_passed_pass_power_3` | true | `reliability.json`, `evidence/*/pytest_after.txt` |
| Coding-debug diff evidence is real and repeatable | `diff_matches_expected_pass_power_3` | true | `reliability.json`, `evidence/*/diff.patch` |
| Path rollback blocks overgeneralized stable promotion | `rollback_success_rate` | 1.0 | `layer3_protocol/path_catalog.jsonl` |
| Layer-3 path avoids memory-induced regression | `memory_induced_regression_rate` | 0.0 | `arm_metrics.json` |
