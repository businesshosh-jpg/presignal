# Outcome Summaries v1 Spec

## Purpose

Step 2 adds derived summary views built only from `Outcome_Ledger`.

These summaries support provider-performance review, convergence auditing, and failure-pattern analysis.
They are decision-support analysis only and are not trading advice.

Step 3 diagnostics are derived from Step 2 summary sheets and do not modify `Outcome_Ledger` or prediction logic.

## Source Sheet

- `Outcome_Ledger` only

No AI providers are called.
No prediction logic is changed.
No source or evaluation sheets are modified.

## Summary Sheets Created

1. `Outcome_Summary_ProviderFamily`
2. `Outcome_Summary_Convergence`
3. `Outcome_Summary_Bucket`

## Grouping Rules

### Outcome_Summary_ProviderFamily

Group by:
- `outcome_family`
- `ai_name`

### Outcome_Summary_Convergence

Group by:
- `event_id` if `type` is `single` or `member`
- `batch_id` if `type` is `batch` and `batch_id` exists

The selected key is written to `group_key`.

### Outcome_Summary_Bucket

Group by:
- `outcome_family`
- `ai_name`
- `type`

## Metric Definitions

### Outcome_Summary_ProviderFamily

- `rows_total`: all rows in group
- `rows_scored`: rows where `scored_flag` is true
- `full_hit_count`: `outcome_bucket = full_hit`
- `partial_hit_count`: `outcome_bucket = partial_hit`
- `weak_fit_count`: `outcome_bucket = weak_fit`
- `miss_count`: `outcome_bucket = miss`
- `unscored_count`: `outcome_bucket = unscored` or `scored_flag = false`
- `avg_outcome_score`: average scored `outcome_score`
- `dir_hit_count`: `mr_dir_ok = true`
- `dir_hit_rate`: `dir_hit_count / rows_scored`
- `strength_hit_count`: `mr_strength_ok = true`
- `strength_hit_rate`: `strength_hit_count / rows_scored`
- `sustain_hit_count`: `mr_sustain_ok = true`
- `sustain_hit_rate`: `sustain_hit_count / rows_scored`
- `overall_hit_count`: `overall_ok = true`
- `overall_hit_rate`: `overall_hit_count / rows_scored`

If `rows_scored = 0`, scored rates are blank.

### Outcome_Summary_Convergence

- `provider_count`: unique `ai_name` count
- `provider_names`: comma-separated provider names
- `unique_pred_dirs`: unique nonblank `mr_pred_dir` count
- `dir_converged_flag`: true when `provider_count >= 2` and `unique_pred_dirs = 1`
- `avg_pred_net_pips`: average numeric `mr_pred_net_pips`
- `pred_pips_min`: minimum numeric `mr_pred_net_pips`
- `pred_pips_max`: maximum numeric `mr_pred_net_pips`
- `pred_pips_spread`: `pred_pips_max - pred_pips_min`
- `unique_pred_strengths`: unique nonblank `mr_pred_strength` count
- `strength_converged_flag`: true when `provider_count >= 2` and `unique_pred_strengths = 1`
- `outcome_buckets`: comma-separated unique `outcome_bucket` values
- `best_outcome_score`: max scored `outcome_score`
- `worst_outcome_score`: min scored `outcome_score`
- `score_spread`: `best_outcome_score - worst_outcome_score`

`convergence_level`:
- `high` when providers agree on direction and strength and `pred_pips_spread <= 3`
- `medium` when providers agree on direction but differ on strength or pips
- `low` when providers disagree on direction
- `insufficient_providers` when `provider_count < 2`
- `unknown` when there is not enough data

This sheet measures convergence only. It must not force or manufacture disagreement.

### Outcome_Summary_Bucket

- `rows_total`: all rows in group
- `rows_scored`: rows where `scored_flag` is true
- `full_hit_count`, `partial_hit_count`, `weak_fit_count`, `miss_count`, `unscored_count`: bucket counts
- bucket rates use `rows_total` as denominator
- `direction_miss_count`: scored rows where `mr_dir_ok` is not true
- `strength_miss_count`: scored rows where `mr_strength_ok` is not true
- `sustain_miss_count`: scored rows where `mr_sustain_ok` is not true
- `most_common_failure_type`: highest of `direction_miss`, `strength_miss`, `sustain_miss`
  - tie priority: `direction_miss > strength_miss > sustain_miss`
  - if `rows_scored = 0`, use `unscored_only`

## Constraints

- Use `Outcome_Ledger` only as the source table.
- Use header-based lookup.
- Create summary sheets if missing.
- If a summary sheet exists, preserve existing header order and append missing headers only.
- Clear and rebuild only summary-sheet body rows.
- Do not reorder headers.
- Do not delete or change any other sheet.
- Missing optional fields in `Outcome_Ledger` must not crash the build.
- Write blank or safe defaults when data is missing.
- Do not call AI providers.
- Do not implement attention factors here.
- Do not implement market reaction memory here.
- Do not implement calibration here.
- Do not create direct trading signals.
- Preserve decision-support wording.
- Do not use buy/sell/trade-entry language.

## Acceptance Checks

1. `buildOutcomeSummaries_()` runs without calling any AI provider.
2. `Outcome_Summary_ProviderFamily` is created or rebuilt.
3. `Outcome_Summary_Convergence` is created or rebuilt.
4. `Outcome_Summary_Bucket` is created or rebuilt.
5. `Outcome_Ledger` is not modified except being read.
6. `Event` is unchanged.
7. `Predictions` is unchanged.
8. Existing evaluation sheets are unchanged.
9. Re-running `buildOutcomeSummaries_()` does not duplicate body rows.
10. Headers are not reordered.
11. Missing optional fields in `Outcome_Ledger` do not crash the run.
12. All summary sheets include `decision_support_note`.
13. No buy/sell/trade-entry language is introduced.
