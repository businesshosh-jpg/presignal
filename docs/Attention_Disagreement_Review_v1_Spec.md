# Attention Disagreement Review v1 Spec

`Attention_Disagreement_Review` is a rebuilt derived diagnostic sheet for Phase 2C of Attention Factor Selection v1.

It reviews case-level provider disagreement during the attention-shadow era. It is observational only and must not control prompts, prediction logic, provider weighting, calibration, Market Reaction Memory, scoring, or signal generation.

## Purpose

The current attention diagnostics show high provider convergence. Provider character is easiest to study where providers disagree.

This sheet answers:

- Which provider predictions disagreed on direction, strength, or expected pips?
- Which provider performed best in those disagreement cases?
- Which attention factors were selected by each provider?
- Was the disagreement useful, possible signal, noisy, tied, or unscored?

## Source

Primary source:

- `Outcome_Ledger`

Do not read `Predictions` directly unless a future revision explicitly requires it.

## Sheet Rules

- Create `Attention_Disagreement_Review` if missing.
- Preserve existing header order and append missing headers only.
- Clear and rebuild only the `Attention_Disagreement_Review` body rows.
- Do not modify `Event`, `Predictions`, `Outcome_Ledger`, existing Evaluation sheets, or existing summary sheets.
- Use header-based lookup.
- Missing optional fields must not crash the build.
- Include decision-support wording on every row.
- Do not use direct trading instruction language.

## Inclusion Logic

Group attention-era rows by provider target:

- batch rows use `batch_id`
- non-batch rows use `event_id`
- fallback to `batch_id` or `release_ts` if needed

Create one review row for a target when at least two providers exist and at least one of these is true:

- providers disagree on `mr_pred_dir`
- providers disagree on `mr_pred_strength`
- `mr_pred_net_pips` spread is at least 5 pips

## Usefulness Labels

- `useful_disagreement`: scored case with one clear winner and score spread at least 2
- `possible_signal`: scored case with one clear winner and score spread at least 1
- `no_clear_winner`: scored case but winner is tied
- `noisy_or_small_gap`: scored case with weak separation
- `unscored_or_thin`: insufficient scored evidence

## Required Headers

generated_ts
review_type
target_key
release_date
release_ts
event_id
batch_id
type
outcome_family
indicator_name
country
provider_count
provider_names
direction_set
strength_set
pips_min
pips_max
pips_spread
realized_pips
mr_real_dir
winner_provider
winner_score
score_spread
disagreement_kind
disagreement_level
usefulness_label
provider_score_detail
provider_prediction_detail
provider_attention_detail
recommended_next_step
decision_support_note

## Functions

- `getOrCreateAttentionDisagreementReviewSheet_()`
- `ensureAttentionDisagreementReviewHeaders_()`
- `buildAttentionDisagreementReview_()`
- `buildAttentionDisagreementReviewRows_()`
- `apiBuildAttentionDisagreementReview_()`

## Menu

Add:

`PreSignal v1.4 -> ⑤ Maintenance -> Build Attention Disagreement Review`

## Acceptance Checks

1. `buildAttentionDisagreementReview_()` runs without calling AI providers.
2. `Attention_Disagreement_Review` is created or rebuilt.
3. Re-running does not duplicate rows.
4. Headers are append-only and not reordered.
5. `Outcome_Ledger` is read only.
6. `Event` and `Predictions` are unchanged.
7. All rows include `decision_support_note`.
8. No provider weighting, calibration, Market Reaction Memory, prompt control, or signal generation is implemented.
9. No direct trading instruction language is introduced.

## Decision-Support Wording

Use:

`Disagreement review is diagnostic only; not trading advice.`
