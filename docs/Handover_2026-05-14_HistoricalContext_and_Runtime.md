# Handover — 2026-05-14

This handover captures the latest state of the historical backfill, the runtime/network debugging, and the new `HistoricalContext` implementation work.

## 1. High-level status

We successfully resumed the historical backfill after a long block that initially looked like a Google/DNS issue, but turned out to be strongly affected by the Codex sandbox network path.

Key outcome:
- running `automation/run_pipeline.py` **outside the sandbox** is now the reliable execution path for live Google Sheets / Apps Script work
- once we switched to that path, blocked validations for late July completed successfully

We also implemented the first prediction-time history layer:
- `Feature Pack v1a`
- same-indicator historical memory only
- deterministic, compact, prompt-safe

## 2. Runtime / environment findings

### What happened

We spent significant time debugging repeated failures like:
- `Unable to find the server at sheets.googleapis.com`
- `Could not resolve host: oauth2.googleapis.com`
- `socket.gaierror: [Errno 8] nodename nor servname provided, or not known`

The sequence of findings was:

1. At first, failures looked like local Google/DNS/network problems.
2. We confirmed real macOS DNS weirdness at one point:
   - `scutil --dns` returned `No DNS configuration available`
   - `dns-sd -G v4v6 oauth2.googleapis.com` returned `Service Not Running`
   - `curl` could not resolve Google
3. After forcing DNS on the rebuilt Wi-Fi service:
   - `networksetup -getdnsservers "Wi-Fi"` returned:
     - `1.1.1.1`
     - `8.8.8.8`
   - `curl -I https://oauth2.googleapis.com` returned HTTP `404`
   - this was the desired success condition
4. Even after that, my in-tool Python/curl attempts were still failing.
5. We then confirmed the important distinction:
   - **outside the sandbox**, connectivity to Google was healthy
   - **inside the sandbox**, Google name resolution could still fail

### Final runtime conclusion

The reliable rule now is:

- for live pipeline runs against Google APIs, prefer **outside-sandbox execution**
- do **not** treat sandbox DNS failures as product-logic failures

### Code hardening added during this work

#### `automation/google_clients.py`

Added a temporary Google-host IPv4-only resolver wrapper:
- `FORCE_GOOGLE_API_IPV4`
- `_GoogleApiIPv4Only`

This was useful diagnostically, but it did **not** fully solve the issue by itself.

#### `automation/run_pipeline.py`

Added explicit runner error classification via:
- `_runner_error_metadata(exc)`

New artifact metadata can now mark:
- `google_dns_resolution_failure`
- `google_api_timeout`

This is helpful because infrastructure failures no longer look like prediction-logic bugs.

## 3. Historical backfill status

### Resolved late-July items

#### July 25 validation

Validated successfully outside sandbox.

Artifact:
- `/Users/junhoshino/projects/presignal/automation_runs/targeted_retest_20260513T153431Z.json`

Result:
- `pipeline_status = ok`
- `scenario_hits = 6`
- `scenario_misses = 0`

Meaning:
- the `jobless_claims + durable_goods` split is confirmed working

#### July 26 validation

Validated successfully outside sandbox.

Artifact:
- `/Users/junhoshino/projects/presignal/automation_runs/targeted_retest_20260513T154509Z.json`

Result:
- `pipeline_status = ok`
- `scenario_hits = 6`
- `scenario_misses = 0`

Meaning:
- the `headline_pce_yoy` promotion in `pce_income_spending` is confirmed working

### Subsequent day-runs

#### July 29, 2024

Artifact:
- `/Users/junhoshino/projects/presignal/automation_runs/day_run_20260513T160140Z.json`

Result:
- `pipeline_status = ok`
- `scenario_hits = 2`
- `scenario_misses = 0`
- small-output day
- `primary_lesson_category = provider_policy`
- `Gemini` needed more retries than `OpenAI` / `Anthropic`

No rule change needed.

#### July 30, 2024

Artifact:
- `/Users/junhoshino/projects/presignal/automation_runs/day_run_20260513T160934Z.json`

Result:
- `pipeline_status = ok`
- `scenario_hits = 9`
- `scenario_misses = 0`
- `primary_lesson_category = batch_splitting`

Framework flagged:
- possible mixed batch at `2024-07-30T13:00:00Z`
- `Housing` + `Other`

But there was no actual miss, so treat as review-only for now.

#### July 31, 2024

First run failed from runtime/infrastructure only:
- artifact: `/Users/junhoshino/projects/presignal/automation_runs/day_run_20260513T162312Z.json`
- status: `runner_error`
- error kind: `google_dns_resolution_failure`

Rerun succeeded outside sandbox:
- artifact: `/Users/junhoshino/projects/presignal/automation_runs/day_run_20260513T171811Z.json`

Result:
- `pipeline_status = ok`
- `scenario_hits = 9`
- `scenario_misses = 0`
- `primary_lesson_category = batch_splitting`

Framework flagged:
- possible mixed batch at `2024-07-31T12:30:00Z`
- `Fiscal/Markets` + `Labor`

Again: review candidate only, not a must-fix.

### Next untouched day

The next untouched weekday after the current backfill progress is:
- **August 1, 2024**

## 4. HistoricalContext implementation

### User goal

User wanted to know whether prediction is really using the growing historical dataset.

Conclusion:
- before this change, **not directly**
- past data was helping mostly through:
  - manual family-rule tuning
  - split rules
  - watchlist refinement
  - provider/runtime policy

It was **not** being injected into prediction-time prompts as compact memory.

### Implemented feature

Implemented:
- **Feature Pack v1a**
- same-indicator history only
- deterministic summary, not raw history dump

File changed:
- `/Users/junhoshino/projects/presignal/apps_script/prediction_runner.js`

### What it does

During event selection:
- `_attachHistoricalContextToEvents_(eventSheet, events);`

This builds a same-indicator history pack from prior `Event` rows using:
- last 3 prior releases of the same normalized indicator

It derives:
- `events_seen`
- `history_quality`
- `last_3_actuals`
- `last_3_consensus`
- `last_3_surprises`
- `surprise_bias`
- `surprise_pattern`
- `surprise_volatility`
- `consensus_accuracy_trend`

These are attached as:

```json
feature_pack: {
  "feature_pack_version": "v1_historical_event_memory",
  "historical_context": {
    "same_indicator": { ... }
  }
}
```

### Prompt integration

For single-event prompts:
- `feature_pack` is injected into the payload

For batch prompts:
- each member now includes:
  - `historical_context_same_indicator`
- anchor member also includes:
  - `historical_context_same_indicator`

Prompt instructions were updated to explicitly say:
- use historical context as compact background memory
- do **not** mechanically extrapolate from it
- reduce reliance when `history_quality` is `partial` or `cold_start`

### Scope limits

Implemented only:
- `v1a`
- same-indicator memory

Not implemented yet:
- same-family historical context
- market reaction memory
- any new sheet/header changes

### Validation status

Local syntax check:
- `node --check apps_script/prediction_runner.js` passed

But live behavior is **not yet validated**, because:
- the new Apps Script file still needs to be updated live
- then we need targeted runs to verify output changes

## 5. Recommended next steps

### Immediate next step

1. Update live Apps Script with:
- `/Users/junhoshino/projects/presignal/apps_script/prediction_runner.js`

### Then validate `HistoricalContext v1a`

Best validation path:

1. Choose a few repeat indicators with known history:
   - CPI / PCE
   - Jobless Claims
   - ISM / PMI
   - Housing or Labor depending on available windows
2. Run small targeted retests
3. Inspect whether:
   - prompts remain compact
   - output behavior changes sensibly
   - cold-start / partial-history behavior remains conservative

### Then resume day-by-day backfill

Continue from:
- **August 1, 2024**

### Suggested next conversation opener

Use something like:

> Update live `prediction_runner.js`, validate `HistoricalContext v1a` on a few targeted repeat indicators, then continue the backfill from August 1, 2024 using outside-sandbox runs.

## 6. Important operational reminder

For future live runs in this thread:
- prefer **outside-sandbox execution** for `automation/run_pipeline.py`
- otherwise Google Sheets / Apps Script connectivity can fail in misleading ways

That is now the single most important runtime lesson from this workstream.
