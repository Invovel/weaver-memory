# v0.8 Integration Validation

This artifact validates the complete v0.8 build substrate:

- RAG evidence layer returns citable evidence refs.
- GBrain ingests candidate bundles and separates `search` from `think`.
- Collaborative specialists produce an `EvidencePacket`.
- Checkpoint/resume state round-trips through the durable runtime store.
- RAG/GBrain/specialist output does not directly write verified memory or Layer-3 patterns.

## Key Metrics

| metric | value |
| --- | --- |
| rag_evidence_node_count | 3 |
| rag_evidence_hit_count | 3 |
| citation_coverage | 1.0 |
| hyde_synthetic_not_promoted | True |
| verified_memory_write_count | 0 |
| layer3_mutation_count | 0 |
| promotion_without_hard_evidence_count | 0 |
| gbrain_candidate_node_count | 2 |
| gbrain_candidate_edge_count | 1 |
| gbrain_authority_granted | False |
| specialist_run_count | 3 |
| evidence_packet_ref_count | 3 |
| checkpoint_resume_success | True |

## Reliability

- run_count = 3
- pass_at_1 = True
- pass^3 = True
- seeds = [80, 81, 82]

## Claim Boundary

This validates the v0.8 system substrate. It does not claim open-world task
success superiority. v0.9 should optimize and expand benchmark coverage.
