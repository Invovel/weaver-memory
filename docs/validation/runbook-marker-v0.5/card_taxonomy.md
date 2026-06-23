# Runbook Marker v0.5 Card Taxonomy

## Tiers

- Tier 1 / golden: 5 fully annotated cards with events, expected trace behavior, counterfactual, and special safety cases.
- Tier 2 / typed: 15 typed cards with full expected marker/core issue fields and simplified counterfactual.
- Tier 3 / variation: 30 variation cards for trigger robustness, tag variation, and scope mismatch pressure.

## Card Types

- known_bad_path_suppression
- marker_conflict_shadow
- weak_signal_partial
- freshness_conflict
- ambiguous_evidence
- negative_avoidance
- route_hint
- evidence_requirement
- scope_mismatch
- overgeneralized_marker_rejection

## v0.5 Safety Boundary

All marker outputs are shadow recommendations. The actual runtime route remains `thinking`; no action is suppressed, no tool is executed, and no pattern is promoted automatically.
