# Attention Evidence Report v1 Spec

## Purpose

`Attention_Evidence_Report` is a rebuilt derived evidence sheet for Phase 2B.

It converts `Attention_Factor_Summary` and `Provider_Character_Diagnostics` into compact conclusions about attention-factor strength, weak slices, factor combinations, provider character, disagreement usefulness, and readiness for later Phase 3 review.

This sheet is observational only. It must not control prompts, predictions, provider weighting, calibration, Market Reaction Memory, or signal generation.

## Source Sheets

- `Attention_Factor_Summary`
- `Provider_Character_Diagnostics`

Do not read `Predictions` directly. Do not call AI providers.

## Sheet Behavior

- Create `Attention_Evidence_Report` if missing.
- Preserve existing header order and append missing headers only.
- Clear and rebuild only the `Attention_Evidence_Report` body rows.
- Do not modify `Event`, `Predictions`, `Outcome_Ledger`, outcome summary sheets, diagnostics sheets, or evaluation sheets.

## Required Headers

- `generated_ts`
- `evidence_type`
- `scope`
- `scope_key`
- `outcome_family`
- `ai_name`
- `attention_factor`
- `factor_combo`
- `sample_size`
- `metric_name`
- `metric_value`
- `baseline_value`
- `lift_vs_baseline`
- `evidence_level`
- `evidence_summary`
- `recommended_next_step`
- `decision_support_note`

## Evidence Types

- `attention_coverage`
- `provider_baseline`
- `strong_factor_provider`
- `weak_factor_provider`
- `strong_factor_combo`
- `family_factor_strength`
- `family_factor_weakness`
- `provider_attention_style`
- `provider_unique_win`
- `tie_pattern`
- `convergence_character`
- `phase3_readiness`

## Metric Rules

- Use the `global` row from `Attention_Factor_Summary` as the attention-era baseline.
- Compare factor/provider/family slices to the global `avg_outcome_score` baseline.
- `lift_vs_baseline` is `metric_value - baseline_value`.
- Prefer larger sample sizes when ties occur.
- Treat small samples as low-confidence evidence.
- Phase 3 readiness is based on scored attention rows, mixed-direction targets, and unique-win count.

## Constraints

- Do not implement provider weighting.
- Do not implement calibration.
- Do not implement Market Reaction Memory.
- Do not modify prediction logic.
- Do not create direct signals.
- Preserve decision-support wording.
- Do not use direct action language.

## Acceptance Checks

1. `buildAttentionEvidenceReport_()` runs without calling AI providers.
2. `Attention_Evidence_Report` is created or rebuilt.
3. Re-running the build does not duplicate rows.
4. Existing header order is preserved.
5. Source sheets are read-only.
6. `Event`, `Predictions`, and `Outcome_Ledger` are unchanged.
7. Every row includes `decision_support_note`.
8. The report includes `phase3_readiness`.
9. No direct action language is introduced.

## Decision Support Wording

Every row should carry:

`Evidence report only; not trading advice.`
