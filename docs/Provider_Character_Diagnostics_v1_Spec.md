# Provider Character Diagnostics v1 Spec

## Purpose

`Provider_Character_Diagnostics` is a rebuilt derived diagnostic sheet for analyzing provider differences, provider-style patterns, and winning-pattern differences during the Attention Factor Selection v1 shadow era.

It is observational only. It must not control prediction outputs, provider weighting, calibration, prompt routing, or signal generation.

`Attention_Evidence_Report` may read this sheet as a source for compact Phase 2B evidence conclusions.

## Source Sheet

- `Outcome_Ledger`

The sheet uses scored outcomes and attention pass-through metadata already present in `Outcome_Ledger`.

## Sheet Behavior

- Create `Provider_Character_Diagnostics` if missing.
- Preserve existing header order and append missing headers only.
- Clear and rebuild only the `Provider_Character_Diagnostics` body rows.
- Do not modify `Event`, `Predictions`, `Outcome_Ledger`, outcome summary sheets, or evaluation sheets.

## Required Headers

The sheet intentionally uses the same diagnostic shape as `Outcome_Diagnostics`:

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

## Diagnostic Types

- `provider_performance_profile`: provider-level outcome and style profile.
- `provider_family_profile`: provider + family outcome and style profile.
- `provider_attention_style`: top selected attention factors by provider.
- `unique_win_pattern`: cases where one provider uniquely outperformed peers.
- `tie_pattern`: global tie/convergence context.
- `convergence_character`: same-direction rate across complete provider groups.

## Metric Rules

- Provider performance uses `rows_scored`, `overall_ok`, `mr_dir_ok`, and `outcome_score`.
- Prediction style uses `mr_pred_dir` and `mr_pred_strength`.
- Attention style uses `attention_factor_1`, `attention_factor_2`, and `attention_factor_3`.
- Unique-win patterns compare providers within the same event or batch target and only count complete three-provider groups.
- Ties are preserved as a diagnostic signal, not treated as an error.

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

1. `buildProviderCharacterDiagnostics_()` runs without calling AI providers.
2. `Provider_Character_Diagnostics` is created or rebuilt.
3. Re-running the build does not duplicate rows.
4. Existing header order is preserved.
5. `Outcome_Ledger` is read-only.
6. `Event` and `Predictions` are unchanged.
7. Every row includes `decision_support_note`.
8. Provider character conclusions remain observational and do not apply weighting.
9. No direct trading advice language is introduced.

## Decision Support Wording

Every row should carry:

`Provider-character diagnostic only; not trading advice.`
