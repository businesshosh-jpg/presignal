# Attention Phase3 Experiment v1 Spec

## Purpose

`Attention_Phase3_Candidates` is a rebuilt derived analysis sheet that bridges Phase 2 disagreement evidence into a conservative Phase 3 design review.

It does not change prompts, predictions, provider weighting, calibration, Market Reaction Memory, scoring, or signal generation.

Its job is to list disagreement cases where repeated Phase 2C evidence suggests a future controlled experiment may be worth studying.

## Source Sheets

- `Attention_Disagreement_Review`
- `Attention_Disagreement_Summary`

Do not read `Predictions` directly. Do not call AI providers.

## Phase 3 Guardrails

- Keep Phase 3 conservative.
- Do not implement provider weighting.
- Do not implement calibration.
- Do not implement output overrides.
- Do not implement Market Reaction Memory.
- Do not implement provider-specific prompt roles.
- Do not create direct signals.
- Preserve decision-support wording.

## Sheet Behavior

- Create `Attention_Phase3_Candidates` if missing.
- Preserve existing header order and append missing headers only.
- Clear and rebuild only the `Attention_Phase3_Candidates` body rows.
- Do not modify `Event`, `Predictions`, `Outcome_Ledger`, evaluation sheets, or existing attention summary sheets.

## Selection Logic

Only emit candidate rows for disagreement review cases where:

- `usefulness_label` is `useful_disagreement` or `possible_signal`
- `winner_provider` is a single provider, not `tie`
- the case matches repeated disagreement evidence from `Attention_Disagreement_Summary`

Repeated evidence means:

- `summary_type` is one of:
  - `family_winner_factor`
  - `family_winner`
  - `winner_factor`
- `diagnostic_level = useful_pattern`
- `rows_total >= 5`
- `useful_disagreement_count + possible_signal_count >= 4`

Preference order when matching evidence:

1. `family_winner_factor`
2. `family_winner`
3. `winner_factor`

This layer is candidate-only. It does not activate Phase 3 behavior.

## Required Headers

- `generated_ts`
- `candidate_type`
- `candidate_key`
- `target_key`
- `release_date`
- `release_ts`
- `event_id`
- `batch_id`
- `type`
- `outcome_family`
- `indicator_name`
- `country`
- `winner_provider`
- `attention_factor`
- `disagreement_kind`
- `usefulness_label`
- `score_spread`
- `pips_spread`
- `evidence_rows`
- `useful_rows`
- `evidence_level`
- `candidate_summary`
- `future_experiment_hint`
- `status`
- `decision_support_note`

## Interpretation

Rows in this sheet mean:

- this disagreement case aligned with repeated useful Phase 2C evidence
- this slice may deserve inclusion in a future controlled shadow comparison
- this slice is not approved for live behavior control

## Acceptance Checks

1. `buildAttentionPhase3Candidates_()` runs without calling AI providers.
2. `Attention_Phase3_Candidates` is created or rebuilt.
3. Re-running the build does not duplicate rows.
4. Existing header order is preserved.
5. Source sheets are read-only.
6. `Event`, `Predictions`, and `Outcome_Ledger` are unchanged.
7. Every row includes `decision_support_note`.
8. The sheet remains candidate-only and does not implement behavior change.
9. No direct action language is introduced.

## Decision Support Wording

Every row should carry:

`Phase 3 candidate review only; not trading advice.`
