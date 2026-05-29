# Attention Factor Summary v1 Spec

## Purpose

`Attention_Factor_Summary` is a rebuilt derived audit sheet for Attention Factor Selection v1.

It summarizes which shadow-mode attention factors providers selected and how those selections relate to scored outcomes. It is analysis-only and must not control prediction outputs, provider weighting, calibration, or signal generation.

## Source Sheet

- `Outcome_Ledger`

Do not read `Predictions` directly unless a future approved phase explicitly requires it.

## Sheet Behavior

- Create `Attention_Factor_Summary` if missing.
- Preserve existing header order and append missing headers only.
- Clear and rebuild only the `Attention_Factor_Summary` body rows.
- Do not modify `Event`, `Predictions`, `Outcome_Ledger`, summary sheets, diagnostics sheets, or evaluation sheets.

## Required Headers

- `generated_ts`
- `summary_type`
- `scope`
- `scope_key`
- `outcome_family`
- `ai_name`
- `attention_factor`
- `attention_factor_rank`
- `factor_combo`
- `rows_total`
- `rows_scored`
- `full_hit_count`
- `partial_hit_count`
- `weak_fit_count`
- `miss_count`
- `overall_hit_count`
- `overall_hit_rate`
- `dir_hit_count`
- `dir_hit_rate`
- `avg_outcome_score`
- `attention_validity_ok_count`
- `attention_partial_count`
- `attention_missing_or_invalid_count`
- `diagnostic_note`
- `decision_support_note`

## Summary Types

- `global`: overall attention-era coverage and performance context.
- `provider`: provider-level outcome profile.
- `family`: family-level outcome profile.
- `factor_provider`: factor usage and outcomes by provider.
- `factor_family`: factor usage and outcomes by outcome family.
- `factor_provider_family`: factor usage by provider and family.
- `factor_combo`: sorted factor combinations selected together.
- `factor_rank`: factor usage by rank position 1, 2, or 3.

## Metric Rules

- Count rows from `Outcome_Ledger`.
- Use `scored_flag` to determine scored rows.
- Use `outcome_bucket`, `outcome_score`, `overall_ok`, and `mr_dir_ok` for derived rates.
- Count attention validity from `attention_validity_flag`.
- Treat missing or invalid attention metadata as audit coverage information, not as prediction failure.

## Constraints

- Do not call AI providers.
- Do not modify prediction logic.
- Do not implement provider weighting.
- Do not implement calibration.
- Do not implement Market Reaction Memory.
- Do not create direct trading signals.
- Preserve decision-support wording.
- Do not use direct action language.

## Acceptance Checks

1. `buildAttentionFactorSummary_()` runs without calling AI providers.
2. `Attention_Factor_Summary` is created or rebuilt.
3. Re-running the build does not duplicate rows.
4. Existing header order is preserved.
5. `Outcome_Ledger` is read-only.
6. `Event` and `Predictions` are unchanged.
7. Every row includes `decision_support_note`.
8. No direct trading advice language is introduced.

## Decision Support Wording

Every row should carry:

`Attention-factor analysis only; not trading advice.`
