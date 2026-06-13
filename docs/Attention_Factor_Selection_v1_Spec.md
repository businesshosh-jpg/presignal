# Attention Factor Selection v1 Spec

## Purpose

Attention Factor Selection v1 adds shadow-mode metadata only.

Each provider continues making predictions exactly as before, but may also return a compact structured list of 2-3 selected reasoning factors. These are structured explanation factors, not internal model attention.

This layer must not control, modify, override, or influence core prediction outputs or signal logic.

## Jan 31 2025 Checkpoint Status

Status labels:

- `attention_factor_v1_status = frozen_explainability`
- `attention_factor_v1_goal_1_status = successful_provider_individuality_layer`
- `attention_factor_v1_goal_2_status = not_approved_for_routing_or_weighting`
- `attention_phase_3a_v1_promotion_status = closed_frozen`
- `attention_phase_3b_status = not_approved`
- `next_active_track = family_rule_and_batch_splitting`
- `future_item = attention_factor_v2_causal_attention_experiment`

The Jan 31 2025 checkpoint closed the v1 promotion review. `Attention_Provider_Individuality` rebuilt with 1911 rows and showed primary attention-factor divergence in 1447 of 1676 comparable groups, a divergence rate of 0.8634. Providers often kept the same prediction direction while selecting different factors: 1136 same-direction/different-factor cases versus 210 same-direction/same-factor cases.

Goal 1 is considered successful enough to preserve Attention Factor Selection v1 as an explainability, provider-personality, future-learning, and non-control shadow metadata layer.

Observed provider habits at the checkpoint:

- Anthropic: `low_signal_event`, `hidden_detail_risk`, `missing_consensus`
- Gemini: `direct_fx_transmission`, `missing_consensus`, `low_signal_event`
- OpenAI: `importance`, `low_signal_event`, `missing_consensus`

Goal 2 did not clear the bar for Phase 3B. `Attention_Shadow_Summary` contained 173 `reject_or_monitor` rows and 103 `not_ready` rows, with 0 `watchlist_candidate` and 0 `strong_shadow_candidate` rows. Phase 3B is not approved, and routing, weighting, calibration, and behavior overrides are not supported by current v1 evidence.

## One-Shot v1 Causality Boundary

Attention Factor Selection v1 is one-shot: the provider receives one event or batch payload and returns one JSON response containing both prediction fields and `attention_factors`.

Implementation order:

`event payload -> one provider response -> prediction + attention_factors together`

Therefore, v1 proves provider-reported individuality and explanation diversity. It does not prove that selected attention factors causally steered prediction behavior. Do not claim that attention factors caused prediction differences in v1.

## Future v2 Roadmap Item

`Attention Factor v2 - Causal Attention Experiment` is a future experimental item only.

Purpose:

- test whether selecting attention factors before prediction changes prediction behavior
- compare a two-step causal-attention architecture against the current one-shot v1 baseline

Proposed future architecture:

1. provider chooses 2-3 attention factors only
2. provider generates prediction using those selected factors as primary reasoning anchors
3. compare outcomes and reasoning behavior against v1 one-shot baseline

Boundaries:

- future experiment only
- not production
- not subscriber-facing
- not a replacement for v1
- no Phase 3B implementation is approved by this roadmap item

The next active development recommendation is to investigate recurring `family_rule` and `batch_splitting` findings separately from Attention Factor v1 promotion.

## Next Track: Family Rule / Batch Splitting Investigation

The Jan 31 2025 checkpoint surfaced recurring `family_rule` and `batch_splitting` findings as the next active investigation candidate.

Purpose:

Determine whether recurring family-rule and batch-splitting patterns point to a stronger structural source of prediction error or evaluation noise than provider-level attention routing.

Why this matters:

Attention Factor v1 showed providers are not clones, but it did not produce control or routing evidence. Recurring `family_rule` and `batch_splitting` findings may indicate that the next bottleneck is event structure, family classification, batch construction, or comparison logic rather than provider individuality.

Scope:

- diagnostics, reporting, and design investigation only
- no live prediction behavior change yet
- no prompt change yet
- no scoring change yet
- no routing or provider weighting
- no Phase 3B promotion

Questions this track should answer:

1. Are certain event families being grouped, compared, or scored incorrectly?
2. Are same-minute batches mixing unrelated or weakly related events?
3. Does batch-level prediction lose signal compared with member-level prediction?
4. Are family rules needed before any provider weighting or routing can work?
5. Is `batch_splitting` a better accuracy-improvement path than Attention Factor routing?
6. Are `family_rule` findings pointing to deterministic system structure issues rather than AI-provider issues?

This is not an implementation approval. It is a roadmap/status direction for the next investigation track.

## Version Labeling

When enabled, this feature distinguishes the build from earlier `v1.4` behavior as:

- `v1.4-baseline`: no attention-factor shadow metadata
- `v1.4-attn-shadow`: attention-factor shadow metadata enabled

This is a comparison/audit label only. It does not imply a new major prediction-policy version.

For sheet data, `attention_schema_version` is the row-level era marker:

- blank `attention_schema_version`: pre-attention `v1.4-baseline` row
- `attention_schema_version = "1.0"`: `v1.4-attn-shadow` row

New provider-error rows still write `attention_schema_version = "1.0"` with `attention_validity_flag = "error"` so failed calls are not mistaken for old baseline rows.

## Shadow-Mode Rule

Attention factors must not control or modify:

- `mr_pred_dir`
- `mr_pred_net_pips`
- `mr_pred_strength`
- `mr_pred_sustain_min`
- `expected_move_dir`
- `expected_move_pips_min`
- `expected_move_pips_max`
- `expected_holding_minutes`
- `qualitative_result`
- `pre_signal_mode`
- scenario fields
- provider weighting
- calibration
- signal generation

This implementation is metadata only.

## Allowed Factors v1

- `consensus_surprise`
- `importance`
- `direct_fx_transmission`
- `hidden_detail_risk`
- `batch_anchor`
- `offsetting_members`
- `low_signal_event`
- `market_whipsaw_risk`
- `missing_consensus`
- `provider_disagreement`

## Excluded For Now

Do not include:

- `same_indicator_history`
- `recent_family_reaction`
- `regime_context`

These remain out of scope until deterministic same-family memory / regime context exists.

## Provider JSON Contract

Providers may return:

```json
{
  "attention_factors": [
    {
      "factor": "consensus_surprise",
      "weight": 0.45,
      "reason": "Consensus and previous values are available, so surprise risk is central."
    },
    {
      "factor": "direct_fx_transmission",
      "weight": 0.35,
      "reason": "This release can directly affect USD rate expectations."
    }
  ],
  "attention_summary": "The prediction mainly depends on consensus surprise and direct USDJPY transmission."
}
```

Rules:

- choose 2-3 factors from the allowed list only
- use the same allowed list for all providers
- do not assign provider-specific roles
- do not invent hidden data
- do not claim access to information outside the payload
- keep reasons concise and payload-grounded
- weights should be numbers between `0` and `1`

## Non-Fatal Parsing Rule

Attention factor parsing must be non-fatal.

If `attention_factors` are missing, malformed, invalid, or partially invalid:

- the prediction still succeeds if the core prediction JSON is otherwise valid
- blank attention fields may be written
- `attention_validity_flag` and `attention_validation_note` describe the issue

## Validation Rules

Validation includes:

1. missing -> `attention_validity_flag = missing`
2. non-array shape -> `invalid_shape`
3. drop factors outside the allowed list
4. keep at most top 3 factors by weight
5. default equal weights if retained weights are missing/invalid
6. `partial` when fewer than 2 valid factors remain
7. `ok` when 2-3 valid factors remain
8. payload-grounded checks:
   - `missing_consensus` only when consensus is unavailable
   - `batch_anchor` only in batch/member contexts
   - `offsetting_members` only when multi-member context exists
   - `provider_disagreement` only when disagreement context exists

## Predictions Headers

Append-only additions to `Predictions`:

- `attention_schema_version`
- `attention_factor_1`
- `attention_factor_1_weight`
- `attention_factor_1_reason`
- `attention_factor_2`
- `attention_factor_2_weight`
- `attention_factor_2_reason`
- `attention_factor_3`
- `attention_factor_3_weight`
- `attention_factor_3_reason`
- `attention_summary`
- `attention_validity_flag`
- `attention_validation_note`

## Outcome_Ledger Pass-Through

If safe, `Outcome_Ledger` may pass through selected attention fields for analysis only:

- `attention_schema_version`
- `attention_factor_1`
- `attention_factor_1_weight`
- `attention_factor_2`
- `attention_factor_2_weight`
- `attention_factor_3`
- `attention_factor_3_weight`
- `attention_summary`
- `attention_validity_flag`

This pass-through must not alter scoring.

## Constraints

- do not implement calibration
- do not implement provider weighting
- do not implement Market Reaction Memory
- do not implement same-family historical context
- do not implement an active reasoning controller
- do not create direct trading signals
- preserve decision-support wording
- do not use direct action language

## What Is Not Implemented Yet

- no attention-driven prompt routing
- no provider weighting
- no calibration
- no same-family memory
- no regime context
- no active reasoning controller

## Phase 2 Derived Analysis Sheets

After enough attention-era rows are collected, the following derived sheets may be rebuilt from `Outcome_Ledger`:

- `Attention_Factor_Summary`: summarizes selected reasoning factors, factor combinations, factor ranks, and outcome context.
- `Provider_Character_Diagnostics`: summarizes provider style, provider attention patterns, convergence/tie patterns, and unique-win patterns.
- `Attention_Provider_Individuality`: separates provider individuality/explainability evidence from performance evidence before routing or weighting is considered.
- `Attention_Evidence_Report`: converts the Phase 2 derived sheets into compact evidence conclusions and Phase 3 readiness.

These sheets are observational only. They do not change prompts, predictions, scoring, provider weighting, calibration, or signal generation.

## Phase 3A Shadow Experiments

Phase 3A uses attention factors only for shadow counterfactual experiments. It does not activate provider weighting, calibration, or behavior overrides.

As of the Jan 31 2025 checkpoint, Phase 3A promotion-focused testing for v1 is closed/frozen. The Phase 3A sheets may continue to be rebuilt for diagnostics, but v1 is not being promoted to Phase 3B.

## Decision Support Wording

Attention factor metadata is explanatory analysis only and not trading advice.
