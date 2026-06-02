# Attention Block Stability v1 Spec

## Purpose

`Attention_Block_Stability` is a rebuilt derived diagnostic sheet for comparing attention-era backtest blocks.

It checks whether observed provider, family, attention-factor, score, hit-rate, and convergence patterns remain similar across blocks such as `Nov 1-10 2024`, `Nov 11-15 2024`, and later `Nov 18-22 2024`.

This sheet is analysis-only. It must not control prompts, prediction logic, provider weighting, calibration, Market Reaction Memory, or signal generation.

## Source Sheet

- `Outcome_Ledger`

Do not read `Predictions` directly. Do not call AI providers.

## Sheet Behavior

- Create `Attention_Block_Stability` if missing.
- Preserve existing header order and append missing headers only.
- Clear and rebuild only the `Attention_Block_Stability` body rows.
- Do not modify `Event`, `Predictions`, `Outcome_Ledger`, summary sheets, diagnostics sheets, or evaluation sheets.

## Block Definitions

- `nov_01_10_2024`: `2024-11-01` through `2024-11-10`
- `nov_11_15_2024`: `2024-11-11` through `2024-11-15`
- `nov_18_22_2024`: `2024-11-18` through `2024-11-22`

Blocks with no rows do not produce performance slices, but the readiness row indicates whether enough observed blocks exist.

## Required Headers

- `generated_ts`
- `diagnostic_type`
- `block_id`
- `block_label`
- `block_start_date`
- `block_end_date`
- `scope`
- `scope_key`
- `outcome_family`
- `ai_name`
- `attention_factor`
- `metric_name`
- `metric_value`
- `baseline_block_id`
- `baseline_value`
- `delta_vs_baseline`
- `rows_total`
- `rows_scored`
- `overall_hit_rate`
- `avg_outcome_score`
- `convergence_rate`
- `stability_level`
- `diagnostic_summary`
- `recommended_next_step`
- `decision_support_note`

## Diagnostic Types

- `block_overview`
- `provider_block_performance`
- `family_block_performance`
- `attention_factor_block_performance`
- `provider_factor_block_performance`
- `convergence_block_risk`
- `cross_block_stability`
- `readiness_next_block`

## Metric Rules

- Use only attention-era `Outcome_Ledger` rows where `attention_schema_version` is `1.0` or `1`.
- Group rows by release date into the defined blocks.
- Compute `rows_total`, `rows_scored`, `overall_hit_rate`, and `avg_outcome_score` for each slice.
- Compute convergence from provider rows sharing the same event or batch target inside each block.
- Treat a target as high convergence when provider `mr_pred_dir` and `mr_pred_strength` are identical.
- Compare later blocks against `nov_01_10_2024` using `avg_outcome_score_delta`.
- Mark low sample slices conservatively instead of treating them as stable evidence.

## Constraints

- Do not modify prediction behavior.
- Do not implement active attention routing.
- Do not implement provider weighting.
- Do not implement calibration.
- Do not implement Market Reaction Memory.
- Do not create direct signals.
- Preserve decision-support wording.
- Do not use direct action language.

## Acceptance Checks

1. `buildAttentionBlockStability_()` runs without calling AI providers.
2. `Attention_Block_Stability` is created or rebuilt.
3. Re-running the build does not duplicate rows.
4. Existing header order is preserved.
5. `Outcome_Ledger` is read-only.
6. `Event` and `Predictions` are unchanged.
7. Every row includes `decision_support_note`.
8. Cross-block rows compare later blocks to the baseline block.
9. Readiness stays `partial` until three observed blocks exist.
10. No direct action language is introduced.

## Decision Support Wording

Every row should carry:

`Block stability diagnostic only; not trading advice.`
