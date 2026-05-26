# Outcome Diagnostics v1 Spec

## Purpose

Step 3 adds a derived diagnostic sheet named `Outcome_Diagnostics`.

`Outcome_Diagnostics` converts the Step 2 summary sheets into high-level audit conclusions about provider performance, provider convergence, family reliability, failure patterns, and readiness for future Attention Factor Selection work.

This is analysis-only and decision-support only. It is not trading advice.

## Source Sheets

- `Outcome_Summary_ProviderFamily`
- `Outcome_Summary_Convergence`
- `Outcome_Summary_Bucket`

Prefer these Step 2 summary sheets as the source layer.

## Diagnostic Types

`Outcome_Diagnostics` creates rows for:

1. `provider_family_strength`
2. `provider_family_weakness`
3. `convergence_risk`
4. `useful_disagreement`
5. `failure_pattern`
6. `unscored_data_quality`
7. `attention_factor_readiness`

## Required Headers

- `generated_ts`
- `diagnostic_type`
- `scope`
- `scope_key`
- `outcome_family`
- `ai_name`
- `metric_name`
- `metric_value`
- `metric_detail`
- `diagnostic_level`
- `diagnostic_summary`
- `recommended_next_step`
- `decision_support_note`

## Metric Definitions

### provider_family_strength

Source:
- `Outcome_Summary_ProviderFamily`

For each `outcome_family`:
- find the provider with the highest `overall_hit_rate`
- if `overall_hit_rate` is blank, use `avg_outcome_score`
- if `rows_scored < 5`, mark `diagnostic_level = low_confidence`
- otherwise:
  - `strong` if `overall_hit_rate >= 0.60`
  - `moderate` if `overall_hit_rate >= 0.45`
  - `weak` otherwise

### provider_family_weakness

Source:
- `Outcome_Summary_ProviderFamily`

For each `outcome_family + ai_name`:
- flag if `rows_scored >= 5` and `overall_hit_rate <= 0.25`
- also flag if `avg_outcome_score` is very low

### convergence_risk

Source:
- `Outcome_Summary_Convergence`

Aggregate by `outcome_family`:
- `total convergence rows`
- `high convergence rows`
- `high_convergence_rate = high / total`

Levels:
- `high` if `high_convergence_rate >= 0.70`
- `moderate` if `>= 0.40`
- `low` otherwise

### useful_disagreement

Source:
- `Outcome_Summary_Convergence`

Aggregate by `outcome_family`:
- count low-convergence rows
- count cases where `score_spread` is large
- useful disagreement exists when providers disagree and at least one provider performs meaningfully better

### failure_pattern

Source:
- `Outcome_Summary_Bucket`

For each `outcome_family + ai_name + type`:
- use `most_common_failure_type`
- include `direction_miss_count`, `strength_miss_count`, `sustain_miss_count`

### unscored_data_quality

Source:
- `Outcome_Summary_ProviderFamily`
- `Outcome_Summary_Bucket`

Flag families/providers or family/provider/type slices where unscored share is high.

Levels:
- `high` if `unscored_rate >= 0.50`
- `moderate` if `>= 0.25`
- `low` otherwise

### attention_factor_readiness

Source:
- all Step 2 summary sheets

Create one overall row:
- `scope = global`
- `scope_key = all`

Readiness is based on:
- `Outcome_Ledger`/Step 2 summaries existing
- enough scored rows existing
- convergence having been measured
- severe unscored data-quality not dominating all families

## Constraints

- Use Step 2 summary sheets only unless an exceptional fallback is required.
- Use header-based lookup.
- Create `Outcome_Diagnostics` if missing.
- If the sheet exists, preserve existing header order and append missing headers only.
- Clear and rebuild only `Outcome_Diagnostics` body rows.
- Do not reorder headers.
- Do not delete or change any other sheet.
- Missing optional fields should not crash the build.
- Do not call AI providers.
- Do not modify prediction logic.
- Do not modify `Event`.
- Do not modify `Predictions`.
- Do not modify `Outcome_Ledger`.
- Do not modify existing evaluation sheets.
- Do not implement Attention Factors here.
- Do not implement Market Reaction Memory here.
- Do not implement calibration here.
- Do not create direct trading signals.
- Preserve decision-support wording.
- Do not use buy/sell/trade-entry language.

## Acceptance Checks

1. `buildOutcomeDiagnostics_()` runs without calling AI providers.
2. `Outcome_Diagnostics` is created or rebuilt.
3. `Outcome_Ledger` is not modified.
4. `Outcome_Summary_*` sheets are not modified except read.
5. `Event` is unchanged.
6. `Predictions` is unchanged.
7. Existing evaluation sheets are unchanged.
8. Re-running `buildOutcomeDiagnostics_()` does not duplicate rows.
9. Headers are not reordered.
10. Missing optional fields do not crash the run.
11. All diagnostic rows include `decision_support_note`.
12. No buy/sell/trade-entry language is introduced.
13. `attention_factor_readiness` row is produced.

## Decision Support Wording

Every diagnostic row must carry:

`Diagnostic analysis only; not trading advice.`
