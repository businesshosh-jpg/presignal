# Automation Test Loop

This workflow replaces repeated interactive sheet-checking with a persistent local runner.

## One-time bootstrap

Run once to create or refresh `local/token.json` with both Sheets and Apps Script scopes:

```bash
python3 auth_sheets.py
```

After that, the runner should reuse the same token without prompting again.

## Runner modes

### `day-run`

Use this for untouched daily discovery runs.

`day-run` uses heavy-day auto handling by default:

- It reads the `Event` window before prediction.
- It marks a day as heavy when same-time clusters are large, mixed across several genres/families, or have high estimated provider-row load.
- Heavy days run predictions one release timestamp window at a time, then run actuals, market reaction, and evaluation once for the full day.
- Heavy-day release windows run provider-by-provider first, rather than waiting for all-provider calls to timeout.
- If a normal day-run hits a transport timeout, auto mode can retry predictions using the same release-window recovery path.

Controls:

```bash
--heavy-day-mode auto      # default: preflight and switch when heavy
--heavy-day-mode force     # always run prediction windows one release timestamp at a time
--heavy-day-mode recovery  # normal first, release-window recovery after timeout
--heavy-day-mode off       # old full-window prediction behavior
--skip-predictions         # run post-prediction phases without redoing predictions
```

Example:

```bash
python3 automation/run_pipeline.py \
  --mode day-run \
  --day 2024-05-13 \
  --tz UTC \
  --providers "Gemini,OpenAI,Anthropic"
```

Default behavior in `day-run`:

- predictions
- actuals fetch
- market reaction scoring
- evaluation rebuild

### `targeted-retest`

Use this after implementing a family rule change for a specific event or batch.

Example:

```bash
python3 automation/run_pipeline.py \
  --mode targeted-retest \
  --window-from-local "2024-05-03 23:45" \
  --window-to-local "2024-05-03 23:46" \
  --tz UTC \
  --providers "Gemini,OpenAI,Anthropic" \
  --run-market-reaction
```

### `review-summary`

Use this to summarize an existing artifact later without rerunning Apps Script:

```bash
python3 automation/run_pipeline.py \
  --mode review-summary \
  --artifact automation_runs/day_run_YYYYMMDDTHHMMSSZ.json
```

Or:

```bash
python3 automation/review_family_rules.py automation_runs/day_run_YYYYMMDDTHHMMSSZ.json
```

## Main runner

Example:

`automation/run_pipeline.py` supports all three modes above.

Behavior:

1. Updates `Config` sheet window values through the Sheets API.
2. Calls Apps Script remotely through `scripts.run`, using `apiRunPipelineWindow_`.
3. Reuses `local/token.json` instead of prompting again.
4. Saves a local JSON artifact in `automation_runs/` containing:
   - pipeline request/response
   - matching `Predictions` rows created during the run
   - matching `log` rows
   - recent `Evaluation_Scenario` rows
   - recent `Evaluation_BatchCompare` rows
   - a compact run summary for testing review

## Testing Framework

Each artifact summary now classifies the day into one or more lesson categories instead of only showing raw counts.

Main categories:

- `family_rule`
  - the watchlist missed the realized best member
- `confidence_risk`
  - batch-level confidence is too strong relative to member/scenario behavior
- `low_signal_suppression`
  - conservative low-signal handling worked and needs no new rule
- `batch_splitting`
  - same-time rows may be too mixed and should be split into cleaner families
- `provider_policy`
  - one provider was materially less stable or needed more retries
- `evaluation_coverage`
  - the day produced predictions but no scored evaluation rows in the tested window
- `automation_runtime`
  - the runner had to recover, checkpoint, or shrink chunk size during the run

Key summary fields:

- `lesson_categories`
- `primary_lesson_category`
- `learning_findings`
- `next_recommended_action`
- `provider_stats`

This turns each day-run into a structured review loop:

1. Did the day reveal a family-rule problem?
2. If not, did it reveal confidence, provider, coverage, or runtime issues?
3. If not, move to the next day.

## Remote Apps Script entrypoints

New API-safe wrappers:

- `apiRunPipelineWindow_(params)`
- `apiRunPredictionsWindow_(params)`
- `apiFetchActualsWindow_(params)`
- `apiScoreMarketReactionWindow_(params)`
- `apiBuildEvaluationSheets_()`

These wrappers avoid menu/UI flows and accept plain parameter objects only.

## Notes

- Prediction automation is run with `autoContinueEnabledOverride=false` inside the API wrapper, then looped locally until complete or `max_passes` is reached.
- Heavy days use a checkpoint-campaign style prediction loop:
  - one prediction chunk per remote call
  - local resume from checkpoint between calls
  - optional work-unit shrink and provider fallback on transport issues
  - automatic provider-first splitting for heavy-day release windows
- `FOMC Minutes`, speeches, auctions, and other low-signal families can now be tested end-to-end without Codex reading the sheet interactively each time.
- Suggested Family Rule Testing loop:
  1. `day-run` on the untouched day
  2. review summary / classify the lesson type
  3. implement a change only if the lesson actually calls for one
  4. `targeted-retest` on the affected event or batch when needed
