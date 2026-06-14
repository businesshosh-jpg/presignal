# Family Structure Investigation v1 Spec

## Purpose

Family Structure Investigation v1 is the active post-Attention-v1 diagnostic track.

Final checkpoint: see `docs/Family_Structure_Investigation_Checkpoint_2026-06-14.md`. The investigation is closed as diagnostics. Broad `Batch Splitting v1` is not approved and is rejected/frozen for now.

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

## Follow-On Diagnostic Sheet

`Batch_Splitting_Candidates`

This sheet is a derived ranking layer over `Family_Structure_Report`. It ranks candidate batches by:

- mixed-family status
- low-signal or `other` member presence
- best-member outperformance versus batch result
- repeated family-combo evidence
- diagnostic priority

It is still diagnostic-only. It does not split batches, change event construction, change prediction prompts, change scoring, or approve live `Batch Splitting v1`.

Checkpoint status: see `docs/Batch_Splitting_Candidates_Checkpoint_2026-06-14.md`. The high-priority review found enough repeated structure to justify a future shadow-only `Batch_Split_Counterfactuals` report; live `Batch Splitting v1` remains not approved.

## Shadow Counterfactual Sheet

`Batch_Split_Counterfactuals`

This sheet is a shadow-only layer over `Batch_Splitting_Candidates`. It compares observed batch-level results against a best-member-derived split proxy from existing scored rows.

Important limitation: the split proxy is not a new prediction and is not true live batch splitting. It is a diagnostic approximation for deciding whether a later, more rigorous family-split counterfactual is worth designing.

It must write `activation_status = shadow_only` and must not change `Event`, `Predictions`, batching behavior, prompts, scoring, market reaction logic, provider routing, or subscriber-facing behavior.

Corrected result: after mapping observed batch baselines from `Evaluation_BatchCompare`, `Batch_Split_Counterfactuals` found 20 `split_proxy_helped` rows across the 20 high-priority candidates. This supports a future true shadow split-group counterfactual, not live splitting.

## Baseline Coverage Audit Sheet

`Batch_Baseline_Coverage_Audit`

This sheet audits why high-priority split candidates lack usable current batch baselines. It reads `Batch_Split_Counterfactuals`, `Outcome_Ledger`, and `Evaluation_BatchCompare` only.

It should classify coverage gaps as:

- `baseline_available`
- `missing_ledger_batch_rows`
- `batch_rows_present_but_unscored`
- `missing_evaluation_batch_compare`
- `evaluation_batch_compare_unscored`
- `unknown_missing_baseline`

It is diagnostic-only and must not rebuild source sheets or change scoring.

Initial audit result: baseline coverage is available for all 20 high-priority counterfactual rows. The prior missing-baseline diagnosis was a derived-report mapping gap, not a source coverage gap.

## True Shadow Group Counterfactual Sheet

`Batch_Split_Group_Counterfactuals`

This sheet groups existing scored member rows by `outcome_family` for each high-priority split candidate and compares the strongest family-group proxy against:

- the observed batch baseline
- the best-member proxy

It is the final diagnostic layer before any `Batch Splitting v1 Design Spec` discussion. It must not create new predictions, alter live batches, alter `Event`, alter `Predictions`, change scoring, or change subscriber-facing behavior.

Initial result: 4 rows showed `family_group_helped`, while 16 rows showed `family_group_hurt_vs_best_member`. This does not justify live batch splitting. Preserve the layer as diagnostics and consider only narrow family-combo review if future evidence repeats.

Final recommendation: preserve all family-structure sheets as diagnostics and return to backtesting or another active roadmap track. Optional future work should be narrow combo-specific review only.

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
- `Batch_Splitting_Candidates` builds successfully when `Family_Structure_Report` exists.
- `Batch_Split_Counterfactuals` builds successfully when `Batch_Splitting_Candidates` exists.
- `Batch_Baseline_Coverage_Audit` builds successfully when `Batch_Split_Counterfactuals` exists.
- `Batch_Split_Group_Counterfactuals` builds successfully when `Batch_Split_Counterfactuals` and `Outcome_Ledger` exist.
- Re-running the builder on the same source data produces deterministic rows, aside from `generated_ts`.
- Missing optional columns do not crash the report.
- No prediction prompt, scoring, batching, market reaction, provider weighting, routing, calibration, or subscriber-facing behavior changes are introduced.
- All wording remains decision support and not trading advice.
