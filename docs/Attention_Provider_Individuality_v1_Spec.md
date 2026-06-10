# Attention Provider Individuality v1 Spec

## Purpose

`Attention_Provider_Individuality` is a rebuilt derived report for Attention Factor Selection v1.

Its purpose is to answer Goal 1 before Goal 2:

- Goal 1: Do providers choose different attention factors in a stable, recognizable way?
- Goal 2: Do those differences improve outcomes or justify routing, weighting, calibration, or behavior changes?

This report is for Goal 1 only. It measures provider individuality, explainability, and reasoning diversity. It must not infer forecast improvement or promote any candidate to routing/control behavior.

## Source Sheets

Preferred source:

- `Outcome_Ledger`

The report reads attention fields already passed through to `Outcome_Ledger`.

It does not call AI providers, create predictions, modify predictions, alter market-reaction scoring, or change existing Phase 3A rules.

## Output Sheet

Create or rebuild:

- `Attention_Provider_Individuality`

Rules:

- Create the sheet if missing.
- Preserve existing header order.
- Append missing headers only.
- Clear and rebuild only body rows.
- Missing optional fields should not crash the build.
- Warning rows may be emitted when useful fields are unavailable.

## Report Sections

The sheet uses `report_section` to distinguish row types.

### provider_factor_frequency

Counts provider attention-factor usage.

Key metrics:

- `provider`
- `attention_factor`
- `row_count`
- `share_within_provider`
- `overall_share`
- `rank_within_provider`

### provider_family_factor_matrix

Counts attention-factor usage by provider and family.

Key metrics:

- `provider`
- `event_family`
- `attention_factor`
- `row_count`
- `share_within_provider_family`
- `rank_within_provider_family`

### provider_divergence_summary

Measures whether comparable provider triplets selected the same or different primary attention factors.

Key metrics:

- `event_id`
- `batch_id`
- `event_family`
- `providers_present`
- `distinct_attention_factors_count`
- `all_same_factor`
- `partial_divergence`
- `full_divergence`
- `prediction_direction_diverged`
- `qualitative_result_diverged`

### convergence_vs_attention_divergence

Separates prediction convergence from attention-factor convergence.

Categories:

- same direction, different factors
- different direction, different factors
- same direction, same factor
- different direction, same factor

### provider_personality_summary

Summarizes provider habits without treating them as performance evidence.

Key metrics:

- `top_attention_factors`
- `top_family_attention_factors`
- `concentration_score`
- `individuality_label`

Labels may include:

- `diversified`
- `factor-concentrated`
- `family-sensitive`
- `indistinct`

### individuality_summary

Provides a global Goal 1 readout of attention-factor divergence.

### baseline_convergence_comparison

If a deterministic pre-attention baseline convergence table is not available, this section is skipped with a diagnostic row.

## Constraints

- Do not change provider prompts.
- Do not change prediction semantics.
- Do not change market reaction scoring.
- Do not change Phase 3A candidate or shadow rules.
- Do not modify `Event` or `Predictions`.
- Do not infer accuracy improvement from individuality rows.
- Do not create direct trading advice.
- Keep decision-support wording.

## Interpretation

This report can support statements like:

- "Providers show distinct factor-selection habits."
- "Providers often predict the same direction while selecting different reasoning factors."
- "One provider is more factor-concentrated while another is more diversified."

This report must not support statements like:

- "Provider X should be weighted more."
- "Factor Y improves accuracy."
- "This should be activated in live behavior."

Those belong to Phase 3A/3B performance evidence, not provider individuality evidence.

## Acceptance Checks

1. `buildAttentionProviderIndividuality_()` runs without calling AI providers.
2. `Attention_Provider_Individuality` is created or rebuilt.
3. Existing Phase 3A sheets still build as before.
4. `Event` is unchanged.
5. `Predictions` is unchanged.
6. `Outcome_Ledger` is read only.
7. Re-running the builder does not duplicate body rows.
8. Headers are append-only and not reordered.
9. Missing optional fields do not crash the build.
10. Output separates individuality evidence from performance evidence.
11. No provider weighting, calibration, routing, or behavior override is implemented.
12. No direct trading-advice language is introduced.

