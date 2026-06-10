# Attention Factor Selection v1 Spec

## Purpose

Attention Factor Selection v1 adds shadow-mode metadata only.

Each provider continues making predictions exactly as before, but may also return a compact structured list of 2-3 selected reasoning factors. These are structured explanation factors, not internal model attention.

This layer must not control, modify, override, or influence core prediction outputs or signal logic.

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

## Decision Support Wording

Attention factor metadata is explanatory analysis only and not trading advice.
