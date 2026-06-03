# Attention Disagreement Summary v1 Spec

`Attention_Disagreement_Summary` is a rebuilt derived diagnostic sheet for summarizing `Attention_Disagreement_Review`.

It is Phase 2C analysis only. It must not control prompts, prediction logic, provider weighting, calibration, Market Reaction Memory, scoring, or signal generation.

## Purpose

The review sheet is case-level. This summary sheet converts those cases into compact patterns by:

- usefulness label
- winner provider
- outcome family
- family plus winner provider
- winner attention factor
- family plus winner attention factor
- disagreement kind

## Source

Primary source:

- `Attention_Disagreement_Review`

Do not read `Predictions` directly. Do not call AI providers.

## Sheet Rules

- Create `Attention_Disagreement_Summary` if missing.
- Preserve existing header order and append missing headers only.
- Clear and rebuild only the `Attention_Disagreement_Summary` body rows.
- Do not modify `Event`, `Predictions`, `Outcome_Ledger`, `Attention_Disagreement_Review`, existing Evaluation sheets, or existing summary sheets.
- Use header-based lookup.
- Missing optional fields must not crash the build.
- Include decision-support wording on every row.
- Do not use direct trading instruction language.

## Required Headers

generated_ts
summary_type
scope
scope_key
outcome_family
winner_provider
attention_factor
disagreement_kind
rows_total
useful_disagreement_count
possible_signal_count
no_clear_winner_count
unscored_or_thin_count
high_disagreement_count
avg_score_spread
avg_pips_spread
top_winner_provider
top_attention_factor
diagnostic_level
diagnostic_summary
recommended_next_step
decision_support_note

## Functions

- `getOrCreateAttentionDisagreementSummarySheet_()`
- `ensureAttentionDisagreementSummaryHeaders_()`
- `buildAttentionDisagreementSummary_()`
- `buildAttentionDisagreementSummaryRows_()`
- `apiBuildAttentionDisagreementSummary_()`

## Menu

Add:

`PreSignal v1.4 -> ⑤ Maintenance -> Build Attention Disagreement Summary`

## Acceptance Checks

1. `buildAttentionDisagreementSummary_()` runs without calling AI providers.
2. `Attention_Disagreement_Summary` is created or rebuilt.
3. Re-running does not duplicate rows.
4. Headers are append-only and not reordered.
5. `Attention_Disagreement_Review` is read only.
6. `Event`, `Predictions`, and `Outcome_Ledger` are unchanged.
7. All rows include `decision_support_note`.
8. No provider weighting, calibration, Market Reaction Memory, prompt control, or signal generation is implemented.
9. No direct trading instruction language is introduced.

## Decision-Support Wording

Use:

`Disagreement summary is diagnostic only; not trading advice.`
