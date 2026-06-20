# PreSignal Pre-Release Scenario Plan

## Why this exists

May 1 showed a real product lesson:

- the batch-anchor selector can be improved
- but some releases are still too ambiguous for a single honest pre-release direction call

The clearest example was the ISM manufacturing cluster on May 1, 2024.
Even after removing the weak/wrong PMI anchor, the batch still failed across providers because the model did not have the deciding release surprise yet.

That does **not** mean PreSignal should become a post-release product.
It means PreSignal should become better at the thing it can honestly do before release:

- identify danger
- identify what to watch
- describe what each major outcome would mean


## Product stance

PreSignal remains a **pre-release** tool.

It should do two different jobs depending on event clarity:

1. **Directional mode**
   Use the current output style when the setup is clear enough for one honest pre-release direction call.

2. **Scenario mode**
   Use a pre-release battle plan when the setup is ambiguous, qualitative, or highly dependent on hidden subcomponents.

Scenario mode is still prediction.
It predicts the important branches before release instead of pretending one branch is already known.


## Low-risk rollout

Do not remove the current prediction fields.
Do not replace the current `mr_pred_dir` pipeline.
Do not change the `(event_id, ai_name)` uniqueness rule.

Instead, append a small scenario layer to `Predictions`.

Suggested new append-only columns:

- `pre_signal_mode`
- `pre_risk_level`
- `pre_volatility_level`
- `watch_member_event_ids`
- `watch_member_indicator_names`
- `scenario_up_case`
- `scenario_down_case`
- `scenario_flat_case`
- `scenario_confidence`
- `scenario_plan_json`


## Meaning of each field

### `pre_signal_mode`

Allowed values:

- `directional`
- `scenario`

Use `directional` when one pre-release direction is honestly defensible.
Use `scenario` when the product should act like a watchlist and interpretation map.


### `pre_risk_level`

Allowed values:

- `low`
- `medium`
- `high`

This answers:
"How dangerous is it to assume the event will do nothing?"


### `pre_volatility_level`

Allowed values:

- `low`
- `medium`
- `high`

This answers:
"Even if direction is unclear, how likely is the event to create a meaningful move?"


### `watch_member_event_ids`

Pipe-delimited event ids for the most important members or sub-signals.

Example:

`e7f6-...|1bd4-...|389d-...`


### `watch_member_indicator_names`

Human-readable version of the watch list.

Example:

`ISM Manufacturing Employment | ISM Manufacturing Prices | ISM Manufacturing New Orders`


### `scenario_up_case`

Short pre-release description of what kind of release mix would support USDJPY up.

Example:

`Employment, prices, and new orders come in stronger than expected and reinforce a hawkish USD interpretation.`


### `scenario_down_case`

Short pre-release description of what kind of release mix would support USDJPY down.

Example:

`Employment and new orders disappoint, or the subcomponents signal softer growth / softer policy pressure than expected.`


### `scenario_flat_case`

Short pre-release description of what kind of release mix would keep the reaction muted.

Example:

`Mixed subcomponents, no single dominant surprise, or the deciding detail sits outside the payload.`


### `scenario_confidence`

Allowed values:

- `low`
- `medium`
- `high`

This is confidence in the **scenario map**, not confidence in one direction.


### `scenario_plan_json`

Machine-readable version for future scoring.

Suggested shape:

```json
{
  "mode": "scenario",
  "risk_level": "high",
  "volatility_level": "high",
  "watch_members": [
    {
      "event_id": "e7f6-...",
      "indicator_name": "ISM Manufacturing Employment",
      "priority": 1,
      "if_stronger_dir": "up",
      "if_weaker_dir": "down"
    },
    {
      "event_id": "1bd4-...",
      "indicator_name": "ISM Manufacturing Prices",
      "priority": 2,
      "if_stronger_dir": "up",
      "if_weaker_dir": "down"
    }
  ],
  "default_case": "flat",
  "note": "Direction depends on subcomponent surprise rather than headline PMI alone."
}
```


## When to use scenario mode

Scenario mode should be preferred when any of these are true:

- `batch_anchor_mode = no_clear_anchor`
- event is a high-importance qualitative release
- event is known to depend on hidden internals
- same-family subcomponents are competing for dominance
- missing consensus materially weakens honest direction confidence

Examples:

- ISM / PMI clusters
- FOMC plus related same-minute releases
- press conferences
- inflation or labor setups where the deciding detail is not in payload

For known same-family clusters, scenario watchlists should come from explicit release-family profiles rather than only from the generic anchor score. The first profile is `ism_services`, where the structural watch members are `Prices`, `New Orders`, `Business Activity`, and `Employment`; headline PMI remains context when those internals are present.


## What stays the same

The current fields remain valid:

- `qualitative_result`
- `expected_move_dir`
- `mr_pred_dir`
- `mr_pred_net_pips`
- `mr_pred_strength`
- `mr_pred_sustain_min`

For backward compatibility:

- `directional` rows continue to behave exactly like today
- `scenario` rows still fill existing prediction fields conservatively
- downstream scoring keeps working

This means we do **not** break existing menus, evaluation, or historical rows.


## How we score scenario mode

Do not score it only with:

- "Was the blind direction exactly right?"

That is too harsh for ambiguous events and pushes the system toward bluffing.

Add a second derived report later, for example:

- `Evaluation_Scenario`

Suggested scenario metrics:

- `watch_hit`
  Was the best member or actual dominant driver included in the watch list?

- `volatility_call_ok`
  If `pre_volatility_level = high`, did the event actually move meaningfully?

- `flat_case_ok`
  If the release was mixed / muted, did the scenario map explicitly cover that?

- `branch_coverage_ok`
  After actuals are known, did the realized stronger/weaker mix fit one of the pre-written cases?

- `scenario_overall_ok`
  Composite score using watch-hit, volatility-call, and branch-coverage.


## Why this is better than the current blind-direction-only approach

For events like May 1 ISM, the current system is forced into a bad choice:

- guess a direction it cannot honestly support
- or go flat and look weak when the event later explodes

Scenario mode gives a more useful pre-release answer:

- "This is dangerous"
- "These are the members that matter"
- "These are the branches that would imply up, down, or flat"

That is more useful to an operator than a fake single-arrow answer.


## Why this is better than a post-release rewrite

This plan does **not** turn PreSignal into an after-the-fact product.

Actuals are only used later for:

- evaluation
- training
- branch scoring

The user-facing output remains pre-release.


## Recommended implementation order

1. Add the scenario columns to `Predictions` as append-only fields.
2. Extend the prompt contract so the provider can return either:
   - `directional` output
   - or `scenario` output
3. Keep current normalization and guardrails for the legacy direction fields.
4. Fill the new scenario fields for high-ambiguity events first:
   - `batch_anchor_mode = no_clear_anchor`
   - qualitative high-importance events
5. Add a lightweight `Evaluation_Scenario` report after enough rows exist.


## Recommendation

The next product step should be:

**Make PreSignal better at pre-release scenario mapping, not louder at pretending certainty.**

That preserves the core product idea while making the difficult events more honest and more useful.
