# Family Structure Investigation v1 Spec

## Purpose

Family Structure Investigation v1 is the active post-Attention-v1 diagnostic track.

The investigation tests whether recurring `family_rule` and `batch_splitting` findings point to a stronger source of prediction error, evaluation noise, or hidden signal than provider-level attention routing.

This is a reporting and design-investigation layer only. It does not change prediction behavior.

## Background

The Jan 31 Attention Factor checkpoint closed Attention Factor Selection v1 as a successful explainability/provider-individuality layer:

- Provider individuality exists.
- Attention-factor divergence is stable enough for diagnostics.
- Attention Factor v1 does not prove causal attention steering because prediction and attention factors are returned in the same provider response.
- Phase 3B promotion was not approved because no `watchlist_candidate` or `strong_shadow_candidate` evidence emerged.

Why this matters: Attention Factor v1 showed providers are not clones, but it did not produce control/routing evidence. Recurring `family_rule` and `batch_splitting` findings may indicate the next bottleneck is event structure, family classification, or batch construction rather than provider individuality.

## New Derived Sheet

`Family_Structure_Report`

The sheet is rebuilt deterministically from existing source sheets. It may be created if missing, may append missing headers, and may rewrite only its own body rows.

## Source Sheets

Preferred source layers:

- `Outcome_Ledger`
- `Outcome_Summary_ProviderFamily`
- `Outcome_Summary_Convergence`
- `Outcome_Diagnostics`
- `Evaluation_BatchCompare`
- `Evaluation_Scenario`
- `Attention_Disagreement_Review`
- `Attention_Disagreement_Summary`
- `Attention_Phase3_Candidates`

Missing optional sheets or columns should produce warnings and blank fields rather than crash the report.

## Report Sections

`family_performance_summary` identifies families associated with stronger or weaker outcomes.

`batch_composition_summary` identifies mixed-family batches, low-signal family presence, and available anchor trace fields.

`batch_vs_member_outcome_comparison` compares current batch-level outcomes against best-member outcomes from existing evaluation data.

`family_mixing_risk_summary` groups repeated family combinations and highlights problematic mixed-family patterns.

`recurring_family_rule_findings` makes repeated family-rule evidence explicit and traceable.

`recurring_batch_splitting_findings` makes repeated batch-splitting evidence explicit and traceable.

`investigation_summary` provides top-level decision support for whether to investigate more, design a future Family Rule v1, design a future Batch Splitting v1, or conclude no structural signal yet.

## Recommendation Labels

- `investigate_more`
- `family_rule_candidate`
- `batch_splitting_candidate`
- `no_structural_signal_yet`

These labels are decision-support only. They do not approve implementation.

## Boundaries

Family Structure Investigation v1 must not:

- change provider prompts
- change prediction semantics
- change event batching behavior
- change family classification behavior
- change market reaction scoring
- change outcome scoring
- change provider weighting, routing, or calibration
- change subscriber-facing signals
- implement Phase 3B attention work

## Future Decision Gate

The report exists to decide whether future `Family Rule v1` or `Batch Splitting v1` work is justified.

Any future implementation must require a separate approval prompt and a new spec before changing live behavior.

## Acceptance Checks

- Existing Attention Factor reports still build unchanged.
- Existing Outcome/Evaluation reports still build unchanged.
- `Family_Structure_Report` builds successfully.
- Re-running the builder on the same source data produces deterministic rows, aside from `generated_ts`.
- Missing optional columns do not crash the report.
- No prediction prompt, scoring, batching, market reaction, provider weighting, routing, calibration, or subscriber-facing behavior changes are introduced.
- All wording remains decision support and not trading advice.
