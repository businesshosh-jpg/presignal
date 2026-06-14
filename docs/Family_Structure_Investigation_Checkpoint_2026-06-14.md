# Family Structure Investigation Checkpoint - 2026-06-14

## Decision

Status labels:

- `family_structure_investigation_v1_status = closed_diagnostic`
- `family_structure_reports_status = preserved_diagnostics`
- `batch_splitting_v1_status = not_approved`
- `broad_batch_splitting_status = rejected_or_frozen_for_now`
- `family_rule_v1_status = not_approved`
- `optional_next_track = narrow_family_combo_review`

Family Structure Investigation v1 produced useful diagnostics, but it does not approve broad live batch splitting or family-rule behavior.

## Diagnostic Chain

The investigation produced the following derived-only sheets:

- `Family_Structure_Report`
- `Batch_Splitting_Candidates`
- `Batch_Split_Counterfactuals`
- `Batch_Baseline_Coverage_Audit`
- `Batch_Split_Group_Counterfactuals`

All are preserved as decision-support diagnostics. None control prompts, scoring, batching, provider routing, calibration, or subscriber-facing behavior.

## Evidence Summary

`Family_Structure_Report` found a structural signal in mixed-family batches.

`Batch_Splitting_Candidates` narrowed the review to 20 high-priority diagnostic rows.

`Batch_Split_Counterfactuals` showed that the best-member proxy looked strong:

- `split_proxy_helped`: 20
- `strong_shadow_evidence`: 10
- `moderate_shadow_evidence`: 10

`Batch_Baseline_Coverage_Audit` showed the baseline data was available:

- `baseline_available`: 20
- `baseline_coverage_ok`

`Batch_Split_Group_Counterfactuals` tested true family-group proxies and produced mixed evidence:

- `family_group_helped`: 4
- `family_group_hurt_vs_best_member`: 16
- `strong_group_shadow_evidence`: 1
- `moderate_group_shadow_evidence`: 3
- `possible_proxy_damage`: 16

## Interpretation

The best-member proxy overstated the case for broad batch splitting.

The true family-group counterfactual suggests that family grouping can sometimes improve over the full batch baseline, but it often loses information versus the best-member proxy. That creates enough damage risk to reject or freeze broad `Batch Splitting v1` for now.

This is a useful outcome. The diagnostic layer prevented a premature behavior change.

## Decision Boundaries

Do not implement:

- live batch splitting
- broad `Batch Splitting v1`
- family-rule behavior changes
- prompt changes
- scoring changes
- market reaction logic changes
- provider weighting, routing, or calibration
- subscriber-facing behavior changes

Do not modify:

- `Event`
- `Predictions`
- existing scoring sheets except by their existing derived builders

## Optional Future Work

If this track continues, keep it narrow.

Possible future diagnostic-only work:

- review `housing+other`
- review `growth+other`
- review `labor+other`

These should be treated as narrow family-combo investigations, not as broad batch-splitting design.

Any future behavior design requires a separate explicit approval prompt and a new spec.

## Recommendation

Recommendation: preserve the current family-structure diagnostics and return to backtesting or another active roadmap track.

Broad batch splitting is not approved.
