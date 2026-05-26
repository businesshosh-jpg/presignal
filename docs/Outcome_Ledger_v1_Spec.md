# Outcome_Ledger v1 Spec

## Purpose

`Outcome_Ledger` is a rebuilt derived audit/reporting sheet for provider and family performance analysis.
It is built from existing `Predictions` rows.
It does not replace `Event`, `Predictions`, `Evaluation_Rows`, `Evaluation_Summary`, `Evaluation_Scenario`, `MR_ProviderRuns`, or `Prediction_Aggregates`.

In Phase 1, Outcome_Ledger is a rebuilt derived audit sheet. It is intentionally conservative and does not yet function as the final immutable learning warehouse. Future phases may introduce an append-only or versioned learning ledger after this derived view is validated.

Step 2 summary sheets are derived from `Outcome_Ledger` and do not change `Outcome_Ledger`'s Phase 1 derived-audit role.

## Constraints

- Do not modify `Event`.
- Do not modify `Predictions`.
- Do not modify `Evaluation_Rows`.
- Do not modify `Evaluation_Summary`.
- Do not modify `Evaluation_Scenario`.
- Do not modify `MR_ProviderRuns`.
- Do not modify `Prediction_Aggregates`.
- `Outcome_Ledger` is derived-only.
- It must not create direct trading signals.
- It must preserve decision-support wording.
- It must not use buy/sell/trade-entry language.
- It must use header-based lookup.
- It must not reorder existing headers in any existing sheet.
- It may create `Outcome_Ledger`.
- It may create `Outcome_Ledger` headers.
- If `Outcome_Ledger` already exists, preserve existing header order and append missing headers only.
- Rebuilding `Outcome_Ledger` may clear and rewrite only `Outcome_Ledger` body rows.

## Phase 1 Scope

Create a rebuilt derived sheet named `Outcome_Ledger`.

Rows are deduplicated from `Predictions` by:

1. `prediction_id`
2. fallback key: `event_id + ai_name`

When duplicates exist, retain the newest row using:

1. `created_ts`
2. then `eval_ts`

Write one row per deduped provider prediction.

## Required Headers

`Outcome_Ledger` v1 writes these logical headers:

- `created_ts`
- `ledger_built_ts`
- `event_id`
- `batch_id`
- `type`
- `prediction_id`
- `run_id`
- `release_date`
- `release_ts`
- `indicator_name`
- `country`
- `genre`
- `importance`
- `ai_name`
- `ai_model`
- `status`
- `qualitative_result`
- `mr_pred_dir`
- `mr_pred_net_pips`
- `mr_pred_strength`
- `mr_pred_sustain_min`
- `mr_real_dir`
- `mr_real_strength`
- `mr_real_sustain_min`
- `realized_pips`
- `mr_dir_ok`
- `mr_strength_ok`
- `mr_sustain_ok`
- `overall_ok`
- `outcome_family`
- `outcome_score`
- `outcome_bucket`
- `scored_flag`
- `prediction_bias`
- `confidence`
- `pre_signal_mode`
- `pre_risk_level`
- `pre_volatility_level`
- `batch_anchor_mode`
- `batch_anchor_confidence`
- `no_trade_advice_flag`

If the sheet already exists, existing header order is preserved and any missing headers are appended only.

## Field Mapping

Read values from `Predictions` headers with the same names where available. If a source header does not exist, write blank.

- `release_date`
  - derived from `release_ts` when possible
  - format `YYYY-MM-DD`

- `outcome_family`
  - derived from `indicator_name` using conservative broad families:
    - `inflation` for CPI, PCE, PPI, inflation
    - `labor` for NFP, payroll, unemployment, wages, jobless claims
    - `growth` for GDP, retail sales, durable goods, factory orders, PMI, ISM
    - `housing` for housing, mortgage, home sales, building permits
    - `energy` for crude, oil, gasoline, distillate, EIA, API
    - `central_bank` for Fed, FOMC, Powell, minutes, speech, testimony
    - `positioning` for CFTC, positioning
    - `other` for unmatched

- `scored_flag`
  - `true` only when realized market reaction exists
  - use `mr_real_dir` or `realized_pips` as evidence
  - if both are blank, `scored_flag = false`

- `outcome_score`
  - only compute for scored rows
  - score formula:
    - `+2` if `mr_dir_ok` is true
    - `+1` if `mr_strength_ok` is true
    - `+1` if `mr_sustain_ok` is true
    - `+2` if `overall_ok` is true
  - if unscored, `outcome_score` is blank

- `outcome_bucket`
  - `full_hit` when `overall_ok` is true
  - `partial_hit` when `outcome_score >= 3`
  - `weak_fit` when `outcome_score` is `1` or `2`
  - `miss` when `outcome_score` is `0`
  - `unscored` when `scored_flag` is false

- `prediction_bias`
  - derive from `mr_pred_dir`
  - `up => upside_bias`
  - `down => downside_bias`
  - `flat => flat_bias`
  - otherwise blank

- `confidence`
  - use `batch_anchor_confidence` if available
  - otherwise `scenario_confidence` if available
  - otherwise blank

- `no_trade_advice_flag`
  - always `true`

## Phase 1 Functions

- `getOrCreateOutcomeLedgerSheet_()`
- `ensureOutcomeLedgerHeaders_()`
- `buildOutcomeLedger_()`
- `deriveOutcomeFamily_(indicatorName, genre)`
- `computeOutcomeScore_(rowObject)`
- `computeOutcomeBucket_(score, overallOk, scoredFlag)`
- `apiBuildOutcomeLedger_()`

## Phase 1 Acceptance Checks

1. `Outcome_Ledger` can be created if missing.
2. Headers are created or appended without reordering.
3. Running `buildOutcomeLedger_()` twice does not create duplicate rows.
4. `Outcome_Ledger` body can be rebuilt safely.
5. `Event` is unchanged.
6. `Predictions` is unchanged.
7. Unscored rows get `outcome_bucket = unscored`.
8. `no_trade_advice_flag` is always `true`.
9. Existing v1.4 behavior is preserved.
