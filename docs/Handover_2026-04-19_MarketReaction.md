# Handover Note — 2026-04-19

## Scope

This handover covers the recent Market Reaction and Predictions changes made during the current workstream.

Primary focus:

- Market Reaction scoring behavior
- Anchor-detection implementation
- Predictions sheet field layout and MR evaluation fields
- RuleBook / Blueprint alignment

## Current State

The latest live `Score Market Reaction` run appears healthier than the previous fixed-timestamp behavior.

Evidence from the live sheet/log:

- latest Market Reaction summary log observed at `2026-04-19T02:13:12Z`
- summary includes:
  - `horizon_min: 5`
  - `anchor_min_abs_move_pips: 3`
  - `anchor_lookback_min: 1`
  - `anchor_lookahead_min: 5`
- this indicates the live run is reading the new anchor-related config values

The run is no longer behaving like a pure `release_ts -> release_ts + horizon` measurement. It is now showing detected reaction starts in several rows.

Examples seen in live `Predictions` rows:

- event `2bcd-3969-54a1-7d75`
  - `start_ts = 2025-04-01T14:01:00.000Z`
  - `end_ts = 2025-04-01T14:06:00.000Z`
  - `start_price = 149.3`
  - `end_price = 149.19`
  - `realized_pips = -11`
- event `9184-63b4-0814-7ea4`
  - `start_ts = 2025-04-01T13:47:00.000Z`
  - `end_ts = 2025-04-01T13:52:00.000Z`
  - `realized_pips = 5`

This is consistent with anchor-based measurement rather than raw scheduled-timestamp measurement.

## Code Changes Made

### 1. `apps_script/market_scoring.js`

Implemented anchor-detection support and short-horizon MR scoring behavior.

Key changes:

- added config readers:
  - `MR_ANCHOR_MIN_ABS_MOVE_PIPS`
  - `MR_ANCHOR_LOOKBACK_MIN`
  - `MR_ANCHOR_LOOKAHEAD_MIN`
- added anchor-detection logic:
  - baseline uses nearest candle close at or before `release_ts`
  - detection window:
    - `release_ts - MR_ANCHOR_LOOKBACK_MIN`
    - `release_ts + MR_ANCHOR_LOOKAHEAD_MIN`
  - threshold:
    - `MR_ANCHOR_MIN_ABS_MOVE_PIPS`
  - prefers first qualifying post-release candidate
  - falls back to pre-release candidate if needed
- updated `_computeUsdJpyMove_()` to:
  - fetch one candle block
  - detect anchor
  - measure the MR horizon from anchor time when a meaningful move is found
  - return `flat` when no meaningful reaction is detected
- extended debug output to expose:
  - baseline point
  - anchor detection status
  - anchor phase
  - start point
  - end point
- retained existing logging

Also updated evaluation writing so the sheet stores:

- `mr_real_dir`
- `mr_real_strength`
- `mr_strength_ok`
- `mr_real_sustain_min`
- `mr_sustain_error_min`
- `mr_sustain_grade`
- `mr_sustain_ok`
- `mr_real_max_up_pips`
- `mr_real_max_down_pips`

### 2. `apps_script/prediction_runner.js`

Reworked the enforced `Predictions` header order to make the sheet easier for humans to read while preserving header-name-based writing behavior.

Important note:

- row writing is header-name driven, so reordering the columns did not require changing the row-object write logic

Also added `mr_real_strength` to the enforced schema.

### 3. Documentation

Updated:

- [RuleBook_v1.3.md](/Users/junhoshino/projects/presignal/docs/RuleBook_v1.3.md)
- [Blueprint_v1.3.md](/Users/junhoshino/projects/presignal/docs/Blueprint_v1.3.md)

These now document:

- the 5-minute MR window direction
- anchor settings
- anchor detection behavior
- MR evaluation fields in `Predictions`
- current code-authoritative behavior

## Sheet / Config Changes

The live sheet config now includes:

- `MR_ANCHOR_MIN_ABS_MOVE_PIPS = 3`
- `MR_ANCHOR_LOOKBACK_MIN = 1`
- `MR_ANCHOR_LOOKAHEAD_MIN = 5`

The live `Predictions` sheet column order was also reorganized into a more readable grouping.

## Known Limitations

### 1. Twelve Data coverage / credit limits

Some rows still end with:

- `eval_note = no_candles`

This is not a logic failure in Market Reaction itself. It is a data-availability or provider-credit issue.

Rows observed with this issue during checking included:

- `307d-7659-0211-d3a5`
- `9345-7a81-48f9-fead`

### 2. Event timestamp vs true market-impact timestamp

Even with anchor detection, the system still begins from the event's scheduled timestamp context.

This is better than the previous fixed start, but it does not fully solve the broader issue that:

- `release_ts` is sometimes not the exact first market-impact instant

The current anchor logic is a practical compromise:

- detect the first meaningful move near the release
- measure from that point if found
- otherwise classify the event as flat

### 3. `mr_strength_ok` semantics

The logic was adjusted so direction mismatch prevents `mr_strength_ok` from showing true.

Current intent:

- if direction is wrong, `mr_strength_ok` should not pass
- `mr_real_strength` remains available as a descriptive field

This makes the evaluation easier to interpret for users.

## Current Interpretation

The Market Reaction system is no longer trying to grade broad chart trend continuation.

It is now closer to the intended use:

- evaluate the chart's initial event reaction
- use a short horizon
- score directional reaction and size more cleanly

This is a better fit for economic-event behavior than the older 30-minute read.

## Recommended Next Steps

### Completed follow-up checkpoint — 2026-04-22

The follow-up provider-comparison work has been implemented and live-tested.

Key additions:

- the candle provider file is now `apps_script/fx_candle_provider.js`
- primary/fallback provider chain is:
  - `tiingo`
  - `twelvedata`
  - `massive`
- provider keys are read from Script Properties:
  - `TIINGO_API_KEY`
  - `TWELVEDATA_API_KEY`
  - `MASSIVE_API_KEY`
- provider-level scoring rows are appended to `MR_ProviderRuns`
- final canonical scoring remains on `Predictions`
- `MR_COMPARE_PROVIDER` and `MR_COMPARE_PROVIDER_2` allow comparison runs without widening `Predictions`
- comparison metadata is written to:
  - `mr_final_provider`
  - `mr_compare_status`
  - `mr_compare_dir_agree`
  - `mr_compare_anchor_delta_min`
  - `mr_compare_pips_delta`
  - `mr_compare_confidence`
  - `mr_compare_note`

The provider comparison model is intentionally not an average/blended score. It runs the same anchor/scoring rule against each provider, then selects a final provider result when the comparison providers agree and the primary appears to be an outlier.

Live validation examples:

- Construction Spending MoM, event `2bcd-3969-54a1-7d75`
  - `tiingo` showed about `-25.75` pips
  - `twelvedata` showed about `-11` pips
  - `massive` showed about `-11.3` pips
  - final result correctly switched to `twelvedata` with `compared_multi_override`
- Baker Hughes Oil Rig Count, event `2644-f174-87d4-e964`
  - tiny provider differences near zero are now treated as agreement after flat-threshold calibration
  - final confidence became `high`
- Monthly Budget Statement, event `092b-772f-5337-9d43`
  - realized move around `-12.15` pips now classifies as `medium`, not `strong`

Additional scoring controls added:

- `MR_FLAT_MAX_ABS_PIPS`
  - default `1`
  - moves below this absolute threshold are directionally treated as `flat`
  - raw realized pips are preserved
- `MR_SKIP_ALREADY_SCORED`
  - when `TRUE`, Config-window scoring skips event_ids that already have market-reaction results in `Predictions`
  - this protects provider API call limits during repeated tests

Strength threshold calibration was adjusted:

- `weak` below `5` absolute pips
- `medium` from `5` up to but not including `15` absolute pips
- `strong` at `15` absolute pips or more

Prediction sheet sorting was also adjusted so future prediction writes sort by:

- `release_ts`
- `event_id`
- `ai_name`

This preserves event grouping while avoiding the previous random-looking release timestamp order.

### Immediate

1. Continue checking a few more live-scored rows manually against chart screenshots.
2. Confirm whether the current anchor defaults are satisfactory:
   - threshold `3` pips
   - lookback `1`
   - lookahead `5`
3. Monitor how many rows still end as `no_candles` or provider-specific fetch errors.
4. Keep `MR_SKIP_ALREADY_SCORED = TRUE` for normal repeated operation, and temporarily set it to `FALSE` only for forced retests.

### If more refinement is needed

1. Review whether `MR_ANCHOR_LOOKAHEAD_MIN = 5` is wide enough for slower reactions.
2. Consider exposing more anchor details in logs if manual audit remains frequent.
3. If provider mismatch remains a recurring issue even after three-provider comparison, inspect `MR_ProviderRuns` first before changing the scoring rules.
4. Keep final MR evaluation on `Predictions`, but store provider-level scoring rows in `MR_ProviderRuns` so agreement/disagreement can be audited without widening `Predictions` excessively.

## Practical Summary For Next Session

If resuming this work later, the safest next assumption is:

- the live Market Reaction run is already using the new anchor-aware logic
- the live Market Reaction run should use three-provider comparison when configured
- the main remaining issue is not basic scoring flow anymore
- the main remaining risks are provider coverage, provider disagreement, and prediction interpretation quality

If debugging a specific event again, use the event-level MR debugger and compare:

- baseline point
- detected anchor point
- start point
- end point
- realized pips

That is now the clearest way to diagnose whether a disagreement comes from:

- timestamp interpretation
- anchor selection
- provider candle differences
- or missing candles

For repeated live-sheet testing:

- set `MR_SKIP_ALREADY_SCORED = FALSE` only while forcing a rescore
- run a very small Config-window target
- set `MR_SKIP_ALREADY_SCORED = TRUE` again immediately after the test
