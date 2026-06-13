# Attention Provider Individuality v1 Spec

## Purpose

`Attention_Provider_Individuality` is a rebuilt derived report for Attention Factor Selection v1.

Its purpose is to answer Goal 1 before Goal 2:

- Goal 1: Do providers choose different attention factors in a stable, recognizable way?
- Goal 2: Do those differences improve outcomes or justify routing, weighting, calibration, or behavior changes?

This report is for Goal 1 only. It measures provider individuality, explainability, and reasoning diversity. It must not infer forecast improvement or promote any candidate to routing/control behavior.

## Jan 31 2025 Checkpoint Status

Status labels:

- `attention_provider_individuality_status = confirmed_explainability_layer`
- `attention_factor_v1_status = frozen_explainability`
- `attention_phase_3b_status = not_approved`

The Jan 31 2025 checkpoint confirmed Goal 1 for v1. The rebuilt report contained 1911 rows. Primary attention-factor divergence appeared in 1447 of 1676 comparable groups, a divergence rate of 0.8634.

Convergence and divergence split:

- same prediction direction, different attention factors: 1136
- same prediction direction, same attention factor: 210

Provider habits at checkpoint:

- Anthropic: `low_signal_event`, `hidden_detail_risk`, `missing_consensus`
- Gemini: `direct_fx_transmission`, `missing_consensus`, `low_signal_event`
- OpenAI: `importance`, `low_signal_event`, `missing_consensus`

Interpretation: provider individuality and explainability are confirmed enough to preserve Attention Factor Selection v1 as a diagnostics layer.

Boundary: v1 attention factors are returned in the same provider response as the prediction. This report measures provider-reported factor-selection patterns, not proven causal attention steering.

Goal 2 remains outside this report. At the same checkpoint, `Attention_Shadow_Summary` showed 173 `reject_or_monitor`, 103 `not_ready`, 0 `watchlist_candidate`, and 0 `strong_shadow_candidate` rows. Phase 3B is not approved from v1 evidence.

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
- "Attention factor X caused the prediction difference."

Those belong to Phase 3A/3B performance evidence, not provider individuality evidence.

As of the Jan 31 2025 checkpoint, the v1 provider individuality layer is preserved as derived-only read-only reporting. The next active development recommendation is to investigate recurring `family_rule` and `batch_splitting` findings separately from this report.

### Next Track: Family Rule / Batch Splitting Investigation

The next active track is not Attention Factor Phase 3B. It is a diagnostics/reporting/design investigation into recurring `family_rule` and `batch_splitting` findings.

Why this matters: Attention Factor v1 showed provider individuality, but it did not produce routing or weighting evidence. The recurring family and batch findings may indicate that event structure, family classification, batch construction, or comparison logic is a stronger bottleneck than provider individuality.

This track must not change prompts, scoring, live prediction behavior, routing, provider weighting, calibration, or subscriber-facing behavior without a separate implementation approval.

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
