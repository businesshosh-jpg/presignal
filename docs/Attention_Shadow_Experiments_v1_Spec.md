# Attention Shadow Experiments v1 Spec

## Purpose

`Attention_Shadow_Experiments` is a rebuilt derived reporting sheet for Phase 3A controlled shadow experiments.

Two weeks of attention-era backtesting is enough to begin counterfactual shadow review, but not enough to activate provider weighting, calibration, or behavior overrides. The sheet asks whether candidate provider/factor rules would have compared favorably against observed outcomes, without changing any prediction output.

This is post-hoc analysis only. It does not call AI providers, create predictions, alter provider output, change scoring, or affect subscriber-facing signals.

## Source Sheets

Preferred sources:

- `Outcome_Ledger`
- `Outcome_Summary_Convergence`
- `Outcome_Diagnostics`

`Predictions` should not be read unless attention fields are missing from `Outcome_Ledger`.

## Derived Sheets

### Attention_Shadow_Experiments

Creates one derived row per tested counterfactual rule instance.

Experiment types:

- `provider_factor_candidate`: tests whether a provider plus selected attention factor would compare favorably against a conservative observed baseline.
- `disagreement_provider_selector`: tests provider choice only in observed provider-disagreement cases.
- `low_signal_watchlist_shadow`: tests whether `low_signal_event` would have been useful as a watchlist-only tag.
- `hidden_detail_risk_confidence_shadow`: tests whether `hidden_detail_risk` may deserve future confidence reduction review.
- `convergence_no_weighting_shadow`: marks high-convergence cases where provider weighting would likely add fake precision.

### Attention_Shadow_Summary

Summarizes shadow experiment rows by:

- `experiment_name`
- `outcome_family`
- `candidate_provider`
- `candidate_factor`

This summary may label rows as `watchlist_candidate` or `strong_shadow_candidate`, but those labels are not live activation.

## Baseline Method

Current implementation uses:

`best_equal_provider_observed`

Within each event/batch group, this baseline compares against the best observed provider `outcome_score`. This is a conservative upper-bound comparator and not an active historical signal.

`provider_average` is not implemented in v1. It may be added later if useful for a less conservative comparison.

## Grouping Rules

Provider rows are grouped by:

- `batch_id` when `type = batch` and `batch_id` exists
- otherwise `event_id`

Within each group, the builder collects provider rows, outcome scores, outcome buckets, predicted directions, and attention factors.

Provider disagreement exists when at least two nonblank `mr_pred_dir` values differ, or when `Outcome_Summary_Convergence` reports low convergence.

High convergence is read from `Outcome_Summary_Convergence` when available, otherwise derived from matching predicted direction and strength.

## Activation Readiness

`Attention_Shadow_Summary` uses:

- `not_ready`: `rows_scored < 20`
- `watchlist_candidate`: `rows_scored >= 20`, `candidate_win_rate >= 0.55`, and `avg_candidate_delta > 0`
- `strong_shadow_candidate`: `rows_scored >= 40`, `candidate_win_rate >= 0.60`, and `avg_candidate_delta > 0.5`
- `reject_or_monitor`: `candidate_win_rate <= 0.45`
- `inconclusive`: all other cases

Even `strong_shadow_candidate` means continued future-block testing only. It does not permit active provider weighting, calibration, or behavior overrides.

## Constraints

- Do not modify `Event`.
- Do not modify `Predictions`.
- Do not modify `Outcome_Ledger`.
- Do not modify outcome summary sheets.
- Do not modify `Outcome_Diagnostics`.
- Do not call AI providers.
- Do not implement provider weighting.
- Do not implement calibration.
- Do not implement behavior overrides.
- Do not change prediction logic or provider outputs.
- Preserve decision-support wording.
- Do not introduce direct action language.

All rows must use:

`activation_status = shadow_only`

All experiment rows must use:

`decision_support_note = Shadow experiment only; not trading advice.`

All summary rows must use:

`decision_support_note = Shadow summary only; not trading advice.`

## Acceptance Checks

1. `buildAttentionShadowExperiments_()` runs without calling AI providers.
2. `Attention_Shadow_Experiments` is created or rebuilt.
3. `Attention_Shadow_Summary` is created or rebuilt.
4. `Event` is unchanged.
5. `Predictions` is unchanged.
6. `Outcome_Ledger` is read only.
7. Outcome summary sheets are read only.
8. `Outcome_Diagnostics` is read only.
9. Re-running the builder does not duplicate body rows.
10. Headers are not reordered.
11. Missing optional attention fields do not crash the run.
12. All experiment rows have `activation_status = shadow_only`.
13. No provider weighting is implemented.
14. No calibration is implemented.
15. No behavior override is implemented.
16. No direct action language is introduced.
17. Candidate readiness labels are reported only as future testing evidence.

## Entrypoints

- Menu: `PreSignal v1.4 -> ⑤ Maintenance -> Build Attention Shadow Experiments`
- API: `apiBuildAttentionShadowExperiments_()`
