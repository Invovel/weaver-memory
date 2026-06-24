# Retrieval Wear Claim Table

| Claim | Metric | Value | Artifact |
| --- | --- | ---: | --- |
| Retrieval paths transfer across paraphrases | `semantic_transfer_rate` | 1.0 | `task_runs.jsonl` |
| Governed paths avoid stale reuse after evidence drift | `stale_path_reuse_rate` | 0.0 | `task_runs.jsonl` |
| Evidence drift triggers successful invalidation and recovery | `rollback_success_rate` | 1.0 | `task_runs.jsonl` |
| Retrieval Wear inspects fewer candidates than repeated RAG | `total_candidates_inspected_delta_vs_rag` | -16728 | `arm_metrics.json` |
| The controlled result repeats across three isolated runs | `pass_power_3` | true | `reliability.json` |
