# Handover Note — 2026-04-22 Prediction Quality

## Scope

This handover prepares the next workstream after completing Market Reaction provider/scoring stabilization.

Primary focus for the next conversation:

- improve AI prediction quality
- reduce overreaction on low-importance or indirect indicators
- make market-reaction prediction fields more internally consistent
- use the now-stabilized Market Reaction scoring output as feedback

## Current Starting Point

Market Reaction scoring is stable enough to use as evaluation feedback.

Recent completed work:

- provider-level market reaction audit rows are written to `MR_ProviderRuns`
- final event-level market reaction evaluation remains on `Predictions`
- USD/JPY candle providers are:
  - `tiingo`
  - `twelvedata`
  - `massive`
- comparison metadata is written to `Predictions`:
  - `mr_final_provider`
  - `mr_compare_status`
  - `mr_compare_dir_agree`
  - `mr_compare_anchor_delta_min`
  - `mr_compare_pips_delta`
  - `mr_compare_confidence`
  - `mr_compare_note`
- provider comparison can override the primary provider when compare providers cluster and the primary appears to be an outlier
- `MR_FLAT_MAX_ABS_PIPS` prevents tiny moves around zero from being treated as directional disagreement
- realized/default strength now uses:
  - `weak` below `5` absolute pips
  - `medium` from `5` up to but not including `15` absolute pips
  - `strong` at `15` absolute pips or more
- `MR_SKIP_ALREADY_SCORED = TRUE` should be the normal operating setting to avoid repeated candle-provider calls

## Why Prediction Quality Is Next

The Market Reaction layer can now tell us whether a prediction was directionally and magnitude-wise plausible. The next bottleneck is no longer candle data plumbing; it is the quality and consistency of AI forecasts.

Several live test rows showed that providers can produce market-reaction predictions that are too dramatic, logically inconsistent, or loosely connected to the indicator.

Examples observed during testing:

- Low-importance energy/fiscal/auction events sometimes predicted medium or strong directional moves even when the event is usually indirect for USDJPY.
- Some predictions treated a value as "stronger" or "weaker" relative to the previous value instead of relative to consensus.
- Some rationales were internally contradictory, especially around fiscal deficit, auctions, oil/gas inventories, and balance-sheet events.
- When consensus was missing, some providers still created a precise directional surprise instead of using a more cautious flat/weak stance.
- The generated fields sometimes disagreed with the narrative, for example a "weak" textual explanation paired with larger pips or medium/strong strength.

## Candidate Improvement Areas

### 1. Prompt / contract refinement

Strengthen the prediction prompt so model outputs follow a more disciplined hierarchy:

- primary comparison should be forecast vs consensus
- previous revision should be context, not the main surprise baseline
- missing consensus should lower confidence and usually reduce pip magnitude
- low-importance events should usually stay weak unless there is a clear direct FX transmission
- indirect indicators should explain the transmission path before assigning directional pips

### 2. Post-processing guardrails

Consider deterministic normalization after provider JSON validation:

- cap `mr_pred_net_pips` by importance unless a clear override reason exists
- downgrade `mr_pred_strength` when pips and importance disagree
- force `flat` / `weak` when consensus is missing and the event is low importance
- ensure sign consistency between `mr_pred_dir` and `mr_pred_net_pips`
- ensure `expected_move_dir`, `mr_pred_dir`, and `qualitative_result` do not contradict each other

Any post-processing must preserve the strict JSON validation contract and must not rename global Apps Script functions.

### 3. Evaluation reporting

Now that `Predictions` contains final MR evaluation fields, add or improve analysis views before changing too much model behavior.

Useful slices:

- by `ai_name`
- by `importance`
- by `genre`
- by `mr_compare_confidence`
- by `mr_final_provider`
- by consensus availability
- by `forecast_dir_ok`, `mr_dir_ok`, `mr_strength_ok`, `overall_ok`

This could be done either as a new sheet/report tab or as an Apps Script summary function. Do not change existing sheet header order unless explicitly approved.

## Suggested First Step In Next Conversation

Start by auditing the existing prediction prompt and normalization flow in:

- `apps_script/prediction_runner.js`

Look specifically for:

- prompt text around market reaction prediction
- JSON schema / required fields
- `_normalizePrediction_()`
- `_mrStrengthFromPips_()`
- default pips bands by importance
- relationship between `expected_move_*` fields and `mr_pred_*` fields

Then decide whether the first implementation should be:

- prompt-only refinement
- deterministic post-processing guardrails
- prediction-quality report tab
- or a small combination of prompt refinement plus guardrails

Recommended sequence:

1. inspect the current prompt and normalization code
2. define concrete failure rules from the test examples
3. implement the smallest safe guardrails
4. run one small Config-window prediction test
5. score Market Reaction only after predictions are generated

## Operational Notes

Use `MR_SKIP_ALREADY_SCORED = TRUE` during normal operation.

Set `MR_SKIP_ALREADY_SCORED = FALSE` only when intentionally forcing a rescore of already processed events.

For prediction testing, prefer a very small Config window. This avoids spending unnecessary AI-provider calls and keeps comparison easier.

Prediction rows are upserted by `event_id + ai_name`, so rerunning predictions for the same events and providers will overwrite existing prediction rows.

Market Reaction scoring updates matching `Predictions` rows by `event_id`.

## Guardrails From AGENTS.md

The next workstream must continue to follow repository constraints:

- do not rename global Apps Script functions
- do not change sheet header order without explicit instruction
- do not remove logging mechanisms
- maintain strict JSON validation contract
- maintain `event_id + ai_name` uniqueness rule
- preserve backward compatibility unless explicitly approved

## Recommended Commit Boundary

Keep prediction-quality changes separate from Market Reaction provider/scoring changes.

The Market Reaction stabilization work was committed as:

`c4bbe95 Add multi-provider market reaction scoring`

The next commit should be scoped to prediction-quality behavior, prompt rules, reports, or guardrails.
