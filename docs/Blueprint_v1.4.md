Blueprint ver.1.4 — Economic Event AI Prediction System (4th, Feb 2026)
Code-authoritative specification.

## 1) Purpose & Scope (Blueprint ver.1.4)

PreSignal ver.1.4 is a Google Sheets + Apps Script system that:

- Ingests upcoming macroeconomic events (currently via the FMP calendar fetcher), normalizes them, and upserts them into the Event sheet.
- Deterministically assigns identity + batching (event_id / batch_id / type) using the canonical batching rules implemented in the Apps Script codebase.
- Generates AI predictions for events into the Predictions sheet via a multi-provider runner (manual menu actions and a configurable window runner).
- Fetches released actual values for events and writes them back into the Event sheet (released_value / released_ts / provider metadata), using a deterministic hybrid resolver: direct FMP calendar resolution first, then selective SeriesMap fallback where needed.
- Computes a short-horizon USD/JPY “market reaction” move around release timestamps, logs the result, and writes best-effort evaluation fields back into matching Predictions rows.
- Builds derived evaluation/report tabs from scored Predictions rows for operator review and provider comparison.

Operationally, this blueprint documents only what is implemented in the uploaded Apps Script code. It does not assume any extra “evaluation/correction module” beyond what the code currently executes. Market reaction now performs a lightweight join back into Predictions for best-effort evaluation fields, and the evaluation builder now rewrites derived reporting tabs from those scored prediction rows. The system still does not build a separate scoring warehouse or autonomous leaderboard service.


## 2) Data Model & Tabs (Blueprint ver.1.4)

### Entities

#### EconomicEvent
A single macroeconomic release row stored in the Event sheet (canonical). The system expects, at minimum, that the Event sheet exists and contains recognizable headers for event metadata and timestamps. Ingestion via the FMP calendar module will enforce the Event header contract (below) by appending any missing columns to the end of the header row.

#### Prediction
A single AI output row stored in the Predictions sheet. Each row represents one provider run for one prediction target. The target may be a concrete Event row (`type = "single"` or `type = "member"`) or a batch-level release cluster identified by `event_id = batch_id` and `type = "batch"`. The prediction runner enforces the Predictions header contract (below) by appending any missing columns to the end of the header row before writing outputs.

#### LogRecord
A single append-only log row stored in the log sheet with structured JSON context. Logging is “best effort,” and relies on the log sheet already existing.

#### SeriesMap / SeriesMap Proposals / SeriesMap Suggestions
Mapping and triage entities used by the actuals fallback workflow:
SeriesMap: selective fallback mapping table used only when direct FMP actual resolution is weak or unavailable.
SeriesMap_Proposals: optional human triage queue (default mode is manual triage in code).
SeriesMap_Suggestions: generated review queue for possible fallback mappings; not every suggestion is expected to be promoted.
(These tables are part of the system’s operational data model even though they are not “event” or “prediction” rows.)

#### MarketReactionProviderRun
An append-only provider-level audit row stored in the optional `MR_ProviderRuns` sheet. Each row captures one market-reaction scoring result for one event and one market-data provider. This table is for provider comparison and debugging; the canonical final MR evaluation still lands on `Predictions`.

#### EvaluationRow / EvaluationSummary
Derived reporting entities stored in `Evaluation_Rows` and `Evaluation_Summary`. These are rebuilt from scored `Predictions` rows and exist for traceable analysis only; they do not replace `Event`, `Predictions`, or `MR_ProviderRuns` as canonical stores.

### Sheets (Tab Names)

The system is built around named sheets. Default names are defined in CFG and are treated as authoritative unless overridden in code at runtime.

#### Core sheets (expected to exist)
Event (CFG.SHEET_EVENT default: "Event")
Predictions (CFG.SHEET_PRED default: "Predictions")
log (CFG.SHEET_LOG default: "log")

#### SeriesMap workflow sheets (expected when using SeriesMap tools)
SeriesMap (CFG.SHEET_SERIESMAP default: "SeriesMap")
SeriesMap_Proposals (CFG.SHEET_SERIESMAP_PROPOSALS default: "SeriesMap_Proposals")
SeriesMap_Suggestions (CFG.SHEET_SERIESMAP_SUGGESTIONS default: "SeriesMap_Suggestions")

#### Optional market reaction audit sheet
MR_ProviderRuns

#### Optional derived evaluation/reporting sheets
Evaluation_Rows
Evaluation_Summary

#### Optional / legacy / compatibility
Config (optional): If present, the runner can read key-value configuration from it (best-effort; absence is allowed).
RawCalendar / RawCaldendar / Events (legacy variants): Some modules (notably market reaction routines) can fall back to these names when locating an event source sheet, but the canonical sheet is Event. In addition, _getRawSheet_() is a backward-compatible shim that returns the Event sheet (so any older calls to “Raw” will actually point at Event).

### Important: sheet creation behavior

The code frequently retrieves sheets by name but does not reliably auto-create missing tabs. If a required sheet is missing, behavior ranges from immediate explicit errors (e.g., “Missing required sheet: Event or log”) to downstream failures when writes occur. Practically: you must create the required tabs in the spreadsheet.

### Header Contracts (Case-Sensitive Labels as Written)

The system uses header-row lookup for writing/reading values. Header enforcement is implemented differently per sheet:

#### Event sheet headers (enforced by FMP ingestion when it runs)

When FMP ingestion/upsert runs, it enforces the following Event headers by appending any missing headers to the end of row 1:
object, country, indicator_name, genre, importance, type, event_id, batch_id, release_ts, source_cal, consensus_value, prev_revision, released_value, released_ts, source_provider, source_series_id, transform, release_status, notes

##### Notes:
If Event ingestion is never run, other modules may operate on whatever headers exist (and may fail if required headers are missing).
The codebase contains an earlier “sanity check” concept for core Event headers, but the effective implementation currently resolves Event by name and returns it without enforcing those minimum headers at sheet-open time.

#### Predictions sheet headers (enforced by prediction runner when it runs)

Before writing predictions, the runner enforces the following Predictions headers by appending any missing headers to the end of row 1:
object, run_id, prediction_id, schema_version, created_ts, event_id, batch_id, type, ai_name, ai_version, ai_model, model_version, consensus_value, prev_revision, source_cal, genre, importance, fx_pair, ai_forecast_value, qualitative_result, expected_move_dir, expected_move_pips_min, expected_move_pips_max, expected_holding_minutes, rationale_short, rationale, prompt_tokens, completion_tokens, latency_ms, raw_output, status, error_message, qualitative_only, released_value, forecast_error_abs, forecast_error_pct, forecast_dir_ok, eval_ts, eval_interval, start_ts, end_ts, start_price, end_price, realized_pips, dir_ok, band_ok, overall_ok, eval_note, indicator_name, country, release_ts, mr_window_min, mr_pred_dir, mr_pred_net_pips, mr_pred_strength, mr_pred_sustain_min, mr_real_dir, mr_strength_ok, mr_real_sustain_min, mr_sustain_error_min, mr_sustain_grade, mr_sustain_ok, mr_dir_ok, mr_real_max_up_pips, mr_real_max_down_pips, mr_final_provider, mr_compare_status, mr_compare_dir_agree, mr_compare_anchor_delta_min, mr_compare_pips_delta, mr_compare_confidence, mr_compare_note

#### MR_ProviderRuns audit headers

When market reaction scoring runs, the system may also append provider-level results to `MR_ProviderRuns`. The audit schema is append-only and includes:

score_run_ts, score_source, event_id, indicator_name, country, release_ts, provider, status, anchor_detected, anchor_phase, anchor_ts, start_ts, end_ts, start_price, end_price, realized_pips, real_dir, real_strength, realized_sustain_min, max_up_pips, max_down_pips, candle_count, provider_meta_json, compare_status, compare_confidence, error_note

#### Evaluation_Rows / Evaluation_Summary derived headers

When `Build Evaluation Sheets` runs, the system rewrites two derived reporting tabs from scored `Predictions` rows:

- `Evaluation_Rows`
- `Evaluation_Summary`

`Evaluation_Rows` includes trace and scored fields such as:

generated_ts, release_date, release_ts, event_id, batch_id, prediction_id, run_id, type, indicator_name, country, genre, importance, fx_pair, ai_name, ai_model, schema_version, status, qualitative_result, consensus_value, prev_revision, ai_forecast_value, released_value, mr_pred_dir, mr_pred_net_pips, mr_pred_strength, mr_pred_sustain_min, mr_real_dir, mr_real_strength, mr_real_sustain_min, mr_dir_ok, mr_strength_ok, mr_sustain_ok, overall_ok, realized_pips, mr_real_max_up_pips, mr_real_max_down_pips, mr_final_provider, mr_compare_status, mr_compare_note, eval_ts, trace_prediction_key

`Evaluation_Summary` includes grouped aggregates such as:

generated_ts, release_date, ai_name, scope, rows_scored, dir_ok_count, dir_ok_rate, strength_ok_count, strength_ok_rate, sustain_ok_count, sustain_ok_rate, overall_ok_count, overall_ok_rate, avg_realized_abs_pips, avg_pred_abs_pips

These sheets are rebuilt from scratch on each run and are derived reporting layers only.

#### log sheet headers (best-effort, non-reordering)

Logging uses a small shim that will:
If the log sheet has no headers, it writes the full header row once.
If headers exist, it will only fill blank header cells left-to-right up to the required length, without shifting or reordering.

##### Required log headers:
ts, level, message, context_json


## 3) Identity, Batching, and Synthetic Rows (Blueprint ver.1.4)

### 3.1 Canonical identity fields

Each Event row is identified and classified using three fields written to the Event sheet:

- event_id: deterministic ID for a single event row
- batch_id: deterministic ID shared by multiple events released at the same minute for the same country (or blank if not batched)
- type: classification of the row as either:
  - single (not batched)
  - member (part of a batch)

These three fields are treated as mandatory for downstream operations such as prediction runs (the runner will skip events missing event_id or type).

### 3.2 When and how identity is assigned

Identity assignment is performed by a post-pass batching step:

After events are upserted into Event, the system calls:

- applyBatchingForKeys_() (in runner_rules_patch.gs)

This post-pass reads all rows in the Event sheet (starting row 2), groups them deterministically, and then writes back event_id, batch_id, and type for each affected row.

If the Event sheet is missing any of these columns:
- country, indicator_name, release_ts, event_id, batch_id, type
the function throws an error and does not proceed.

Important behavior: this is not a “fill only if blank” patch—applyBatchingForKeys_() assigns values deterministically and writes them into the sheet body for each grouped row.

### 3.3 Batching key (grouping rule)

Batch grouping is computed using a minute-level key:

- country (uppercased)
- release_ts clamped to minute (UTC ISO string with seconds forced to :00Z)

Implementation detail made explicit:

If release_ts ends with :SSZ, the seconds are replaced with :00Z using:

- ts.replace(/:\d{2}Z$/, ':00Z')

Group key format (conceptual):

- COUNTRY|YYYY-MM-DDTHH:MM:00Z

If two or more events share the same (country, minuteUTC) they are treated as a batch.

### 3.4 Deterministic ID generation (event_id / batch_id)

The system generates IDs deterministically using a hash-based pseudo-UUID function:

- Hash core: FNV-1a 32-bit
- UUID-like string constructed from multiple hashes of the seed

#### batch_id

For each group:

- If the group has 2+ rows:
  - batch_id = uuidFrom("batch|" + groupKey)
- If the group has 1 row:
  - batch_id = "" (empty string)

#### event_id

For each row, regardless of batch size:

- event_id = uuidFrom("event|" + COUNTRY + "|" + minuteISO + "|" + indicator_name)

So two events at the same minute and country will:

- share the same batch_id (if 2+ rows exist in that group)
- always have distinct event_id values because indicator_name is part of the seed

### 3.5 type assignment (single vs member)

For each group:

- If the group has 2+ rows:
  - every row gets type = "member"
- If the group has 1 row:
  - the row gets type = "single"

No other type values are assigned in the Event sheet by batching logic.

### 3.6 Provider batch prediction rows in Predictions

When the prediction runner generates predictions for batched events, it contains explicit batch-level behavior:

If an event has:

- type === "member" and
- a non-empty batch_id

Then the runner groups all members sharing that batch_id, constructs a batch-level reference payload, and calls each enabled provider once for the combined release cluster.

These batch prediction rows have these key properties:

- event_id = the batch_id (note: not a concrete Event row ID)
- batch_id = the batch_id
- type = "batch"
- ai_name = provider name (for example `Gemini`, `OpenAI`, `Anthropic`)
- indicator_name = derived batch label (for example `Batch: CPI YoY | CPI MoM | ...`)

Each provider therefore produces its own batch prediction row, and those rows coexist with the member-level provider rows in the same Predictions table.


## 4) Event Ingestion & Upsert (Blueprint ver.1.4)

### 4.1 Source & responsibility

Event ingestion in ver.1.4 is implemented only via the FMP economic calendar pipeline in fmp_calendar.gs.

This pipeline is responsible for:

- Fetching upcoming events from FMP (/economic_calendar)
- Normalizing raw payload rows into the Event schema
- Upserting rows into the Event sheet using a deterministic fallback key
- Enforcing Event headers (append-only at end)
- Sorting the Event sheet by release_ts ascending after writes
- Deferring assignment of event_id, batch_id, type to the batching post-pass (applyBatchingForKeys_())

### 4.2 Authoritative entrypoint (menu)

The canonical UI entrypoint for ingestion is:

- Menu → PreSignal v1.4 → ① Events → “Fetch & Upsert (next 72h)”

This invokes menuUpsertNext72h_() (in Code.gs), which performs:

- runFmpUpcomingToEvent_(3)
- Hard-coded “next 72h” window implemented as 3 days ahead (UTC date range)
- Must bypass Config windowing (explicitly does not call resolveWindow_())
- applyBatchingForKeys_()
- Post-pass that fills event_id, batch_id, type deterministically (see Section 3)
- Logging + toast
- Writes a structured info log “Upsert (next 72h) finished” to log
- Displays a toast with fetched/appended/upserts and batching assigned count

Note: There is also a menuUpsertToEvent_() handler that uses a Config window and calls runFmpRangeToEvent_(). In the current code set, that range worker is present, but the “next 72h” path remains the canonical operator entrypoint.

### 4.3 Fetch logic (FMP)

The fetch worker is fmpFetchUpcoming(daysAhead):

API key source:

- CFG.FMP_API_KEY (preferred), else Script Property "FMP_API_KEY"

If missing, the function throws.

Base URL:

- CFG.FMP_BASE default: https://financialmodelingprep.com/api/v3

Date range:

- from = today (UTC)
- to = today + daysAhead (UTC)

Both formatted as YYYY-MM-DD using UTC getters.

Endpoint:

- GET {base}/economic_calendar?from=...&to=...&apikey=...

Optional server-side country filter:

- If CFG.FMP_COUNTRY is non-empty, it appends &country=... (best-effort; endpoint support may vary)

HTTP behavior:

- Non-200 response throws with the response code and body.

### 4.4 Normalization (raw → Event row)

Each raw object from FMP is normalized by normalizeFmpRow_(raw) into a schema object whose values are later written into the Event sheet.

Field mapping (effective behavior):

- object → "econ_event"
- indicator_name → first non-empty of:  
  indicator_name | title | event | name | category
- country → first non-empty of:  
  country | ccy | region, uppercased
- genre → first non-empty of:  
  genre | category | group
- importance → first non-empty of:  
  importance | impact | importanceText | importance_level

Consensus / previous:

- consensus_value pulls first non-empty from:  
  consensus_value | consensus | estimate | forecast | expected
- prev_revision pulls first non-empty from:  
  prev_revision | previous | previousValue | prev | prior | revised | revisedPrevious

Both are parsed by _parseNumber_():

- removes %, whitespace, and commas
- returns Number or null → written as blank in the sheet if null

Timestamp parsing (scheduled release):

- release_ts is derived from first non-empty of:  
  release_ts | datetime | date | time

It is parsed by _parseReleaseTsUtcMinute_():

- accepts ISO strings, numeric strings, or epoch seconds/milliseconds
- rounds to nearest minute using Math.round(ms/60000)*60000
- outputs UTC ISO string with seconds forced to :00Z (e.g., 2026-02-10T12:30:00Z)
- invalid parse returns '' (blank)

Important: released fields are currently not populated by normalization  
Although the normalizer contains local variables for “released value / ts,” the returned object currently sets:

- released_value: ''
- released_ts: ''
- source_provider: ''
- source_series_id: ''
- transform: ''
- release_status: 'scheduled'
- notes: ''

So the ingestion pipeline treats FMP calendar rows as scheduled, and the actuals status/value lifecycle is handled later by the Actuals modules.

### 4.5 Local country filter (post-normalization)

After normalization, runFmpUpcomingToEvent_(daysAhead) applies a local filter:

- If CFG.COUNTRY_FILTER is a non-empty array, only rows whose normalized country (uppercased) is included are kept.

Default config sets COUNTRY_FILTER: ['US'].

This filter applies even if FMP server-side filtering is enabled.

### 4.6 Sorting behavior (in-memory and on-sheet)

Sorting is applied twice:

- In-memory sort before write  
  runFmpUpcomingToEvent_() sorts normalized rows by release_ts ascending (lexicographic on ISO string).
- Sheet sort after write  
  _upsertEventsToEvent_() attempts to sort the Event sheet range (rows 2..last) by the release_ts column ascending.

This is wrapped in try/catch and will not fail the run if sorting errors.

### 4.7 Upsert key & update semantics

Upsert is implemented by _upsertEventsToEvent_(normRows).

Fallback key (dedupe / match key):

- key = country + '|' + indicator_name + '|' + release_ts

Built from:

- existing Event rows (body) indexed by this key
- each normalized row generates the same key to match/update

Skip conditions (ingestion-level):

- If indicator_name is blank → skipped (counted)
- If release_ts is blank → skipped (counted)

Write semantics (critical):

For both appends and updates, the function constructs a full row array aligned to headers.

It explicitly sets:

- type = ''
- event_id = ''
- batch_id = ''

Therefore:

- Upsert updates will overwrite the entire row, and will blank out type/event_id/batch_id for any matched rows.  
- This is expected because the menu flow immediately runs applyBatchingForKeys_() afterward to repopulate those identity fields deterministically.

Numeric casting on write:

- consensus_value and prev_revision are written as Numbers if not blank.

### 4.8 Header enforcement policy (Event sheet)

getEventSheet() enforces the project policy: no auto-creation of tabs.

If the Event sheet does not exist, ingestion throws:

- Event sheet "Event" not found. Create it first.

If the Event sheet exists, ensureEventHeaders_(sh) ensures required headers exist:

- If row 1 is empty, it writes the full required header row once.
- Otherwise, it appends any missing required headers at the end of row 1.
- It does not reorder existing headers.

Excellent.  
Below is the fully rewritten Section 5) aligned with:

- Your existing architecture
- Strict JSON contract
- Deterministic identity rules
- And the new Feature Builder (deterministic context layer) we decided to introduce

This version preserves everything stable and only extends it cleanly.

## 5) Prediction Runner & Providers (Blueprint ver.1.4 — Revised with Feature Pack)

### 5.1 Purpose

The Prediction Runner generates one AI prediction row per (event_id × provider) and upserts it into the Predictions sheet.

Key architectural properties:

- Runs over Event rows within a configurable time window.
- Requires Event rows to already have event_id and type populated (batching/identity applied).
- Calls one or more AI providers (Gemini / OpenAI / Anthropic) depending on config and available API keys.
- Enforces strict JSON parsing.
- Writes error rows to Predictions if a provider call fails.
- Builds and attaches a deterministic feature_pack before calling any provider.
- Never mutates Event rows.

### 5.2 UI Entrypoints (Menu Functions)

From Menu → PreSignal v1.4 → ② Predictions:

- Run Predictions (All Providers) → runPredictionsAll_()
  - Window: 24h before now → 36h after now
  - Providers: CFG.PROVIDERS (filtered by available API keys)

- Run Predictions (Config Window) → runPredictionsWindow()
  - Dispatches to the dedicated prediction window path
  - Uses `PRED_WINDOW_*` keys when present
  - Falls back to shared `WINDOW_*` keys only if prediction-specific keys are absent

- Gemini (manual) → menuRunPredictionsGemini_()
  - Same window
  - Providers: ['Gemini']

- OpenAI (manual) → menuRunPredictionsOpenAI_()
  - Same window
  - Providers: ['OpenAI']

- Claude (manual) → menuRunPredictionsClaude_()
  - Same window
  - Providers: ['Anthropic']

### 5.3 Effective Prediction Window

The core runner computes:

- window_start_iso = now - windowMinBeforeMin
- window_end_iso   = now + windowMaxAfterMin

Defaults:

- 24*60 before
- 36*60 after

Optional Config override:

If:
- WINDOW_ENABLED truthy
- WINDOW_FROM_LOCAL and WINDOW_TO_LOCAL valid
- WINDOW_TZ set or defaults to script timezone

Then window is replaced with derived UTC ISO range.

If parsing fails → fallback to computed window (no failure).

### 5.4 Event Selection Rules (from Event sheet)

The runner scans Event rows (row 2 onward) and selects rows satisfying:

- object blank OR equals econ_event
- event_id exists and non-empty
- type exists and non-empty
- release_ts convertible to valid ISO
- release_ts ∈ [window_start_iso, window_end_iso]

Each selected event is normalized into a base runner payload:

- event_id
- batch_id
- type
- country
- indicator_name
- genre
- importance
- release_ts
- source_cal
- consensus_value
- prev_revision
- fx_pair

If fx_pair missing → defaults to CFG.DEFAULT_FX (USDJPY).

Selection statistics are logged:

- scanned
- skipped_bad_ts
- skipped_out_of_window
- skipped_missing_id_type
- selected

### 5.5 Qualitative-only Classification

Each event is classified as:

- numeric
- qualitative-only

Rules:

#### Explicit override (highest priority)

If event contains qualitative_only field → respected.

#### Genre match (case-insensitive)

speech, press_conference, statement, minutes, hearing, testimony

#### Indicator keyword match (word boundary)

Matches above keywords.

#### Auctions (conditional)

If auction-like AND both consensus and previous missing → qualitative-only.

#### GDPNow / nowcast exception

Explicitly treated as numeric.

If qualitative-only:

- ai_forecast_value MUST be null.

### 5.6 Feature Builder (Deterministic Context Layer) — NEW

Before any provider call, the runner computes a structured feature_pack.

#### Purpose

Prevent common-sense guessing and anchor predictions to current market conditions.

#### Inputs

- country
- indicator_name
- release_ts
- consensus_value
- prev_revision
- event_id

#### Data Sources

- FRED
- FMP
- internal surprise history
- optional price history

#### Rules

- Deterministic only (no AI computation allowed)
- No raw time-series tables
- Only aggregated statistics permitted
- Optional “as-of” mode: data must be ≤ release_ts
- Must be cached per (event_id)
- Must not modify Event sheet
- Must log feature_build_ms and feature_keys

#### Allowed Feature Types (governed)

- last_n_values (n ≤ 6)
- trend_3m / trend_6m
- surprise_std_12m
- avg_surprise_12m
- regime markers (≤ 5)
- related indicator deltas (≤ 5)

Forbidden:

- raw long histories
- look-ahead leakage
- LLM-derived features

The feature_pack is attached to the provider prompt.

#### Feature Pack v1 (Minimal Specification)

Purpose

Provide deterministic, compact, market-condition-oriented context to LLM before prediction.

Constraints

- Deterministic only (no AI computation)
- Computed from APIs or internal data
- No raw time-series tables
- Max 6 historical values
- Max 5 regime markers
- Max 5 related drivers
- Total serialized size target < 1,500 tokens
- No forward-looking data beyond release_ts

Required Blocks (v1 Minimal)

{
  "indicator_history": {
    "last_values": [],
    "trend_3m": 0,
    "trend_6m": 0,
    "surprise_std_12m": 0
  },
  "regime_context": {
    "policy_rate_level": 0,
    "policy_rate_direction_3m": "up|down|flat",
    "usd_trend_1m_pct": 0
  },
  "related_drivers": {
    "driver_1": 0,
    "driver_2": 0
  }
}

Versioning

Add:

- feature_pack_version in log context

If structure changes → increment version

### 5.7 Provider Resolution and API Keys

Providers enabled only if API key found.

Supported:

- Gemini
- OpenAI
- Anthropic (Claude alias)

Keys retrieved from:

- Script Properties
- User Properties
- Document Properties

Key names:

- Gemini: GEMINI_API_KEY, GOOGLE_API_KEY, GOOGLE_AI_STUDIO_API_KEY
- OpenAI: OPENAI_API_KEY
- Anthropic: ANTHROPIC_API_KEY

If no providers enabled:

- Return {status:'validation_error', message:'No providers enabled'}

### 5.8 Provider Call Mechanics (with Retries)

Wrapped in _withRetries_():

- Attempts: 4
- Exponential backoff (800ms base + jitter)
- Logs retry attempt

OpenAI

- response_format: { type: "json_object" }
- system + user (payload + feature_pack + contract)

Gemini

- response_mime_type = "application/json"
- Extract first JSON object
- Strip code fences

Anthropic

- system + one user message
- max_tokens: 2048

### 5.9 Strict JSON Contract

Provider must return:

{
  "object": "ai_prediction",
  "event_id": "...",
  "type": "...",
  ...
}

Rules:

- Strict JSON only
- No code fences
- Must include object, event_id, type
- event_id/type enforced to match Event row
- If array → first valid object selected
- If quoted JSON → inner JSON parsed

Additional requirement:

- rationale_short must reference or align with signals present in feature_pack.

Failure → error row written.

### 5.10 Normalization and Defaults

After parsing:

- event_id/type forced to Event values
- qualitative_only → ai_forecast_value = null
- qualitative_result defaults:
  - parsed valid OR inferred OR inline
- expected_move_dir defaults:
  - parsed OR derived OR flat
- Pips band defaults by importance
- holding minutes default = 60
- fallback direction rule:
  - flat if max ≤ 1, else up

### 5.11 Writing to Predictions

Each output row includes:

- run_id (UUID)
- prediction_id (UUID(event_id + "|" + ai_name))
- status

Upsert key:

- (event_id, ai_name)

Overwrite if exists, else append.

### 5.12 Provider Batch Rows

If:

- type == "member"
- batch_id non-empty

Runner groups all members for that batch_id and calls each enabled provider once for the combined release cluster.

For each enabled provider, runner upserts a batch row with:

- event_id = batch_id
- batch_id = batch_id
- type = "batch"
- ai_name = provider name
- indicator_name = derived batch label

Batch rows coexist with member rows and are normalized by the same prediction guardrails, with additional batch-specific sustain/horizon hygiene.

## 6) Actuals Fetching & Status Lifecycle (Blueprint ver.1.4)

### 6.1 Purpose

The Actuals Fetcher scans Event rows in a rolling time window, first attempts direct deterministic FMP calendar resolution for each eligible event, then consults SeriesMap only as a selective fallback, and writes resolved actuals back into the Event sheet:

- released_value
- released_ts
- source_provider
- source_series_id
- transform
- release_status

This module is implemented in actuals_fetcher.gs and is designed to be idempotent: repeated runs over the same time range should not corrupt state, and will only update rows when a new actual is found or a revision is detected.

### 6.2 Entrypoints (manual and automation)

#### Automation (installable trigger)

The system can run actuals fetches hourly via an installable trigger created from the menu:

- Menu → Automation → “Hourly actuals automation is ON” → menuStartActualsAutomation_()
  - Creates a trigger to run runFetchActualsHourly_() every hour at minute :10
  - De-duplicates existing triggers for the same handler

- Menu → Automation → “Hourly actuals automation is OFF” → menuStopActualsAutomation_()
  - Removes any triggers whose handler is runFetchActualsHourly_()

The hourly handler:

- runFetchActualsHourly_() → delegates to runFetchActualsWindow_() using defaults from ACTUALS_CFG:
  - LOOKBACK_MINUTES = 14 days
  - LOOKAHEAD_MINUTES = 60 minutes
  - MAX_ROWS_PER_RUN = 400

#### Manual runs

- Menu → Actuals → Manual fetch → menuActualsManualFetch_()
  - Default fallback: look back 24h, no lookahead, cap 2000
  - If resolveWindow_('actuals_manual') exists and returns an enabled window, it converts the window to “minutes back / minutes forward” relative to now and runs with those computed minutes.
  - Delegates to runFetchActualsWindow_(minsBack, minsFwd, cap)

Additional explicit manual tools:

- Actuals (past 24h) → menuRunActualsPast24h_() → runFetchActualsWindow_(24*60, 0, 1000)
- Actuals (past 7d) → menuRunActualsPast7d_() → runFetchActualsWindow_(7*24*60, 0, 2000)

### 6.3 Required sheets and “no auto-create” policy

The actuals runner requires both sheets to exist:

- Event (CFG.SHEET_EVENT or "Event")
- log (CFG.SHEET_LOG or "log")

If either is missing, the run throws:

- Missing required sheet: Event or log

The module does not create missing tabs.

### 6.4 Candidate selection (Event rows)

runFetchActualsWindow_(lookbackMinutes, lookaheadMinutes, rowCap):

- Loads all Event rows (row 2..last) into memory.
- Computes a time window:
  - lo = now - lookbackMinutes
  - hi = now + lookaheadMinutes

For each row, it determines:

- indicator_name
- release_status (prefers release_status; if missing, falls back to status)
- release_ts parsed into a Date (invalid dates are skipped)

It applies two major gates:

#### Gate A — skip qualitative events upfront

If _shouldSkipActuals_(indicator_name) returns true, the row is skipped and an info log is written:

- Actuals: skipped qualitative (includes event_id, indicator_name, country)

This gate is keyword/pattern based (speeches, minutes, testimony, etc.) and is independent of SeriesMap.

#### Gate B — time window + status rules

A row is selected as a candidate when:

If status is scheduled:

- release_ts ∈ [lo, hi] OR
- release_ts ∈ [lo, now] (“scheduled-but-past” catch-up)

If status is released or revised:

- release_ts >= lo (revision catch-up)

Finally, candidates are capped:

- If rowCap > 0, candidates are truncated to the first rowCap rows in scan order.

### 6.5 Hybrid resolution behavior (direct first, SeriesMap fallback)

For each candidate, the runner requires:

- event_id (non-empty)
- indicator_name (non-empty)
- release_ts (non-empty)

It first attempts the direct FMP calendar resolver. If that does not deterministically resolve an actual, it then tries to resolve a SeriesMap mapping using whichever resolver exists:

Preferred:

- resolveSeriesForEvent({country, indicator_name}, seriesMap)

Backward-compat:

- _resolveSeriesForEvent_(seriesMap, indicator_name, country)

If no map is found:

- logs warn: Actuals: No SeriesMap match (event_id, indicator_name, country)
- and (best-effort) calls appendSeriesMapSuggestion_(country, indicator_name) once per unique (country|indicator_name) per run.

If a map is found but indicates filtering:

- If map.provider === 'FILTER' or
- If map.notes matches /synthetic batch event/i  
  then the event is skipped with an info log:
  - Actuals: skipped by SeriesMap filter

### 6.6 Reference date heuristic (month-end)

Before fetching, the module computes a reference date used for FRED observation windows:

- ref = _refMonthEnd_(release_ts) if the function exists
- otherwise ref = new Date(release_ts)

This is intended to align monthly macro releases with an “end-of-month” observation window for series lookups.

### 6.7 Provider priority (within the SeriesMap fallback path)

Actual fetching is performed by _fetchActualFromProviders_(args).

Provider order is constructed as:

- The SeriesMap’s provider first (uppercased)
- Then ACTUALS_CFG.SOURCE_PRIORITY appended without duplicates  
  Default: ['FRED','FMP']

#### FRED adapter (primary)

- Requires Script Property: FRED_API_KEY (if missing, FRED returns null/skip)
- Fetches observations via _fredFetchObservations_(seriesId, refDate)
- Uses an ~18-month window ending at the end of the reference month
- Picks the latest observation inside the requested range
- Also builds an observations[] list suitable for transforms

Transform:

- If args.transform exists and _computeTransform_ exists, it computes the transformed value from observations[] (or a single-point fallback).

Success return shape:

- { hasActual:true, value, ts:<observation_date_iso>, provider:'FRED', series_id, transform }

#### FMP adapter (placeholder / limited)

FMP actuals are only attempted if:

- SeriesMap series_id matches: calendar:<Event Name>

It:

- Calls FMP /economic_calendar for a ±1 day window around refDate
- Finds a row where event matches the <Event Name> (case-insensitive exact match) and actual is non-empty
- Returns { hasActual:true, value:Number(actual), ts, provider:'FMP', series_id }

If the series_id does not match the required calendar: form, FMP returns {hasActual:false}.

### 6.8 Update semantics (what is written back to Event)

If _fetchActualFromProviders_() returns no actual:

- the row is not changed
- an info log is written: Actuals: fetch skipped with the reason/provider attempted

If an actual is found, the runner stages updates:

- released_value
  - Uses roundByUnit(res.value, map.unit_type, (map.transform||'level').toUpperCase()) if roundByUnit exists
  - Otherwise writes the numeric value as-is

- released_ts
  - Uses _parseReleaseTsUtcMinute_(res.ts) if available; otherwise preserves existing released_ts

- source_provider
  - res.provider || map.provider

- source_series_id
  - res.series_id || map.series_id

- transform
  - res.transform || map.transform

- release_status
  - Status transition logic (see 6.9)

All updates are applied in-memory first, then written back in one setValues() for the full Event range (rows 2..last).

### 6.9 Status lifecycle and revision detection

The module uses release_status (lowercased) as the canonical status field.

Status update rules:

- If current status is scheduled:
  - new status becomes released once an actual is found.

- If current status is released or revised:
  - the module compares the existing released_value with the newly fetched value.
  - If the value differs (comparison uses toFixed(10) normalization), status becomes revised.

Therefore:

- scheduled → released is triggered by the first successful actual fetch.
- released → revised is triggered only when the fetched value changes vs stored value.
- revised remains revised unless the value later matches exactly again (in which case it would stay revised because the code only promotes to revised, it does not downgrade).


## 7) SeriesMap: Structure, Resolution, and Suggestion Workflow (Blueprint ver.1.4)

### 7.1 Purpose

SeriesMap is the system’s mapping layer that connects an Event (country + indicator_name) to a provider series identifier and optional transform/precision policy. It is used primarily by Actuals Fetching to determine where to fetch released values and how to format them for storage.

This section documents only the behavior implemented in:

- series_map.gs
- seriesmap_fred_autosuggest.gs

### 7.2 Sheet: SeriesMap (authoritative mapping table)

#### Required table name

- Sheet name must be exactly: SeriesMap
- If the sheet does not exist:
  - loadSeriesMap() returns an empty array (silent)
  - resolveSeriesForEvent() will load and still resolve to null (no mapping)

#### Effective schema (columns used)

loadSeriesMap() reads headers by name (case-insensitive) and recognizes:

- country
- indicator_name_pattern
- provider
- series_id
- freq
- unit_type
- transform
- notes

Rows are skipped unless all of these are present on the row:

- country, indicator_name_pattern, provider

Important: Resolution will only return a match if the selected row has a non-empty series_id.

### 7.3 Pattern language and matching semantics

#### Country matching

- Exact match after normalization:
  - Event country is trimmed and uppercased
  - SeriesMap country is trimmed and uppercased
- If Event country is empty → resolver returns null

#### Indicator name normalization

Before matching, the resolver normalizes the event indicator name by removing a trailing parenthetical suffix, then lowercasing:

Examples of suffixes removed:

- "(Oct/04)", "(Jan)", "(Q1)", "(Dec preliminary)"

This is implemented by stripping the final (...) group at the end of the string.

#### Supported pattern types (indicator_name_pattern)

A SeriesMap row pattern can be:

- Regex literal  
  Format: /.../flags  
  If no i flag is included, i is automatically added.  
  Regex is applied to the normalized indicator string.

- Text pattern (substring match)  
  Any other value is treated as case-insensitive substring match against the normalized indicator string.

The resolver also normalizes patterns to remove invisible unicode spaces and strips a leading ' (Google Sheets “force text” apostrophe).

### 7.4 Match ranking (tie-break rules)

When multiple rows match the same event, the resolver selects the “best” one by score:

- Regex matches outrank text matches.
- Within the same kind, longer pattern length outranks shorter.

Scoring is effectively:

- Regex hit: 2000 + pattern.length
- Text hit: 1000 + pattern.length

### 7.5 Provider filtering and minimum completeness

- Rows where provider equals FILTER (case-insensitive) are never returned by the resolver.
- After choosing the best match, resolveSeriesForEvent() returns it only if:
  - provider is present and
  - series_id is present
- If series_id is missing, resolution returns null even if the pattern matched.

### 7.6 Rounding policy (used by Actuals write-back)

roundByUnit(value, unit_type, transform) standardizes rounding to a fixed decimal precision.

Core behavior:

- Non-numeric values → null
- Default precision → 2 decimals

Unit-driven precision:

- percent_1dp → 1
- percent_2dp → 2
- index_1dp → 1
- thousands_0dp / count_0dp → 0
- raw → 2

Transform-driven adjustment:

- If dp is still 2 and transform is mom or yoy (or contains pct) → dp becomes 1

### 7.7 Sheet: SeriesMap_Suggestions (self-healing queue)

#### Creation behavior

appendSeriesMapSuggestion_() ensures the suggestion sheet exists:

- If missing, it is auto-created via insertSheet('SeriesMap_Suggestions').

#### Base schema written on first creation

When created empty, it writes:

Base columns:

- country, indicator_name_pattern, provider, series_id, freq, unit_type, transform, seasonal_adjustment, precision_dp, lag_rule, notes, created_ts

Primary suggestion columns (appended on the right):

- cand_1_provider, cand_1_series_id, cand_1_title, cand_1_score, cand_1_freq

If the sheet already exists, _ensureSuggestionsSheet_() will append any missing required headers to the right (no reordering).

#### De-dupe policy for suggestions

appendSeriesMapSuggestion_() de-duplicates by:

- (country, indicator_name_pattern) where:
  - country is uppercased
  - indicator_name_pattern is the default pattern (see below)

If a suggestion already exists for that pair, it will not append a new row.

#### Default pattern rule

indicator_name_pattern defaults to the indicator name with the trailing date suffix stripped:

- buildDefaultPattern_(indicatorName) → stripDateSuffix_(indicatorName)

### 7.8 Fallback suggestion generation (current maintained workflow)

The active fallback-maintenance workflow is built around three sheets:

- FMP_EventCatalog: source list of candidate indicators
- FRED_Series_ID: local FRED candidate pool
- SeriesMap_Suggestions: human review queue

#### Step 1 — Build FRED Series Catalog

The catalog builder refreshes FRED_Series_ID.

Important current behavior:

- the catalog is filtered by default to US-relevant macro series
- foreign, state/local, and other noisy rows are reduced before they enter the candidate pool

This is intended to improve downstream suggestion quality, not to create canonical mappings by itself.

#### Step 2 — Rebuild Suggestions from FMP Catalog

rebuildSeriesMapSuggestionsFromFmpCatalog_():

- reads FMP_EventCatalog
- skips noisy source rows before matching, including:
  - impact == None
  - auction-like rows
  - CFTC-like rows
  - holiday-like rows
- ranks FRED candidates from FRED_Series_ID using deterministic title/domain/frequency/unit heuristics
- writes a review queue into SeriesMap_Suggestions

Current output policy:

- one primary candidate only (`cand_1_*`)
- a single suggested match in `suggested_*` when the system has a usable recommendation
- uncertain rows may be left without any suggested series
- `provider` and `series_id` remain blank in the base row until a human promotes the mapping

#### Step 3 — AI Review Suggestion Batch

reviewSeriesMapSuggestionsBatch_():

- scans SeriesMap_Suggestions for remaining `UNCERTAIN` rows
- processes them in bounded batches
- may choose one FRED match from the reviewed shortlist or decline to suggest anything
- writes review outcome into:
  - suggested_provider / suggested_series_id / suggested_title
  - suggested_confidence / suggested_reasoning
  - review_status / review_method

This batch design exists to stay within Apps Script execution limits.

#### Notes on legacy builders

Older windowed Event-row suggestion builders and FMP candidate slot augmentation still exist in parts of the codebase for compatibility, but they are no longer the primary maintained SeriesMap workflow.

### 7.10 Promoting suggestions into SeriesMap (human selection workflow)

promoteSelectedSeriesMapSuggestions_():

Requires:

- SeriesMap_Suggestions sheet exists
- SeriesMap sheet exists
- user has an active selection on SeriesMap_Suggestions

It reads selected rows and appends rows to SeriesMap.

#### Promotion constraints

A row is promotable only if:

- country, indicator_name_pattern, provider, series_id are all non-empty
- provider !== 'FILTER'

#### SeriesMap header enforcement during promotion

Promotion ensures SeriesMap has these headers (append missing at end, no reorder):

- country, indicator_name_pattern, provider, series_id, freq, unit_type, transform, notes

#### De-dupe policy for promotion

Before appending, it de-dupes against existing SeriesMap rows using the key:

- country | indicator_name_pattern | provider | series_id | transform

If an identical key already exists, the suggestion row is skipped.

### 7.11 FRED Auto-Suggest (legacy selected-row helper)

This is a separate, operator-driven helper in seriesmap_fred_autosuggest.gs.

#### What it does

- Operates only on selected rows in SeriesMap_Suggestions
- Queries the FRED “series search” endpoint
- Writes a primary candidate into cand_1_* plus classification metadata
- Current fallback workflow is centered on FMP catalog rebuild + optional AI review rather than multi-candidate selected-row autosuggest

#### Selection-only enforcement

menuSeriesMapAutoSuggestFRED_():

- Requires active sheet = SeriesMap_Suggestions
- Uses RangeList selection to build unique row numbers
- Ignores header row (row 1)

#### API key requirement

Requires Script Property:

- FRED_API_KEY  
  If missing, it logs an error and shows an alert.

#### Overwrite policy (important)

The menu runs with:

- forceOverwrite: true

Meaning:

- It clears cand_1_provider/series_id/title/score/freq first for each selected row
- Then writes fresh candidates based on the new search
- (So even if no candidates are found, cand_1 fields may become blank after the run.)

#### Output header enforcement

If the required output columns do not exist on SeriesMap_Suggestions, the tool appends them to the right (no reorder), then reloads the sheet data to align indices.



## 8) Actuals Backfill & Historical Update Mechanics (Blueprint ver.1.4)

### 8.1 Purpose

In addition to the rolling-window Actuals Harvester (Section 6), ver.1.4 contains a one-off, ignore-window backfill utility designed to:

- Fill missing released_value for historical Event rows (no time window)
- Skip rows already populated
- Route fetching via SeriesMap first, with a minimal “auto-map” fallback for a small set of common indicators

This backfill is implemented in actual_backfill.gs.

### 8.2 Entrypoint (menu maintenance wrapper)

Backfill is intended to be launched from the “maintenance” control plane in Code.gs:

- menuMaintenanceBackfillActuals_()

Verifies that fetchActualsIgnoreWindowOnce exists  
Logs “Maintenance: backfill missing actuals start”  
Calls fetchActualsIgnoreWindowOnce()

If fetchActualsIgnoreWindowOnce is missing, the wrapper throws:

- Missing function: fetchActualsIgnoreWindowOnce

This wrapper is control-plane only (logging + dispatch). All actual backfill behavior is in actual_backfill.gs.

### 8.3 Backfill scope and scan model (ignores time window)

fetchActualsIgnoreWindowOnce():

- Loads the entire Event sheet body (row 2..lastRow) into memory.
- Does not apply any “release_ts window” filtering.
- Processes rows sequentially and writes updates per-row using helper writers.

Required columns (must exist in Event headers):

- event_id, indicator_name, country, release_ts, release_status, released_value, type

If Event is empty (lastRow < 2), it logs and exits without changes.

### 8.4 Row-level eligibility rules (hard skips)

A row is skipped (no writes) if any of the following is true:

Missing minimum identifiers:

- event_id is blank OR indicator_name blank OR country blank OR release_ts blank

Already has an actual:

- released_value !== '' and released_value !== null

Current status is explicitly error:

- release_status === 'error' (case-insensitive compare is applied by lowercasing)

release_ts cannot be parsed into a valid Date

These skips are counted as skipped in the end summary log.

### 8.5 SeriesMap resolution order (and local auto-map fallback)

For eligible rows, the function attempts to resolve a mapping:

Primary:

- resolveSeriesForEvent(evObj, mapRows)

Uses loadSeriesMap() output loaded once at the beginning of the run.

Fallback:

- _autoMapIndicator(evObj)

A small built-in pattern list inside actual_backfill.gs that returns provider mappings for a limited set of indicators.

If neither yields a mapping:

- It logs:
  - Actuals(ignore window): No SeriesMap match

And moves to the next row (no writes).

Important: This backfill does not use SeriesMap_Suggestions or the autosuggest pipeline. It is strictly “resolve or skip,” with a minimal internal fallback.

### 8.6 Provider/type skip policy (explicit non-auto exclusions)

Even if a mapping exists, the backfill will force-skip and write a status when the mapping/provider is not meant to be auto-fetched, or the Event row is not an atomic event:

It computes:

- provider = (m.provider || '').toUpperCase()
- rowType = (Event.type || '').toLowerCase()

It then skips if:

- provider === 'MANUAL'
- provider === 'FILTER'
- rowType === 'batch'

When skipped by these conditions, it does write to the Event row:

- release_status: 'pending'
- notes: 'Manual/Filter/Batch: skipping'

And logs:

- Actuals(ignore window): skipped non-auto provider/type

This is a “soft skip”: it records a pending state rather than doing nothing.

### 8.7 Reference-period heuristic (for FRED alignment)

Backfill uses a reference-period helper:

- ref = getRefPeriodForEvent(evObj) (implemented in series_map.gs)

This produces:

- ref.refDate (UTC Date used to anchor the observation search window)
- ref.refKey (string YYYY-MM)

Rules (effective behavior):

- If indicator name contains a month in parentheses, the reference is that month-end.
- If indicator name contains a quarter in parentheses, the reference is quarter-end month-end.
- Otherwise, fallback is the last day of the month prior to release_ts.

This reference is used for the FRED observation window in _fredFetchObservation().

### 8.8 Provider routing implemented by backfill

Backfill supports only these providers:

#### A) FRED

Fetch path:

- _fredFetchObservation(seriesId, ref.refDate, m.transform)

Behavior:

- Requires Script Property FRED_API_KEY or it throws.
- Fetches fred/series/observations with a tight window:
  - observation_start = refDate - 15 days
  - observation_end = refDate + 15 days
- Uses FRED “units”:
  - MOM_PCT → pch
  - otherwise → lin
- Picks the latest non-empty value, preferring observations on/after the ref date, else the closest prior.

Rounding:

- Writes released_value as:
  - roundByUnit(fred.value, m.unit_type, m.transform)

Sanity check (only one implemented):

- If m.transform === 'YOY_PCT' and value is outside [-10, 50], the row is set to error:
  - release_status: 'error'
  - notes: 'Value out of range: <value>'

Write-back on success (FRED):

- released_value: <rounded>
- released_ts: now().toISOString() (time of backfill fetch, not observation timestamp)
- source_provider: m.provider
- source_series_id: m.series_id
- transform: m.transform
- release_status: 'fetched'

Optional mirror:

- If ACTUALS_CFG.COPY_ACTUALS_TO_PREDICTIONS is truthy, it calls:
  - _copyActualsToPredictions(event_id, value)

(This flag is not defined in actuals_fetcher.gs’s ACTUALS_CFG; it may be absent in practice. If absent, this branch is effectively disabled.)

#### B) FMP_CAL

Fetch path:

- _fmpFetchCalendarWindow(from, to) then _fmpPickMatchForEvent(...)

Window:

Based on release_ts date (UTC day):

- from = release day - 3 days
- to = release day + 3 days

Hard filter:

- The fetched calendar is filtered to country === 'US' before matching.

Match requirements:

- Must find an event match for the given semantic series_id (e.g., CRUDE_STOCKS, CHICAGO_PMI, etc.)
- If match exists but actual is null/invalid → pending

Write-back on success (FMP_CAL):

- released_value: match.actual (no rounding function applied here)
- released_ts: new Date(match.date).toISOString() (or now if missing)
- source_provider: 'FMP_CAL'
- source_series_id: m.series_id (semantic key, not a FRED series)
- transform: m.transform || 'LEVEL'
- release_status: 'fetched'

#### C) Any other provider

If m.provider is not one of the above:

Writes:

- release_status: 'error'
- notes: 'Provider <provider> not implemented'

Logs a warning.

### 8.9 Status values used by backfill (note: differs from rolling harvester)

The backfill routine uses these status strings:

- pending — used when skipping MANUAL/FILTER/BATCH, or when no observation/match is yet available
- fetched — used when an actual was successfully written
- error — used when a provider fails, sanity check fails, or provider is not implemented

This status vocabulary is not the same as the rolling window harvester (Section 6), which primarily uses scheduled / released / revised. Backfill is therefore a “maintenance-mode” lifecycle that can coexist with the main lifecycle but does not align status naming automatically.

### 8.10 Logging and end-of-run summary

Backfill logs to log via appendLog():

Start:

- Actuals(ignore window): start

Per-row route logs:

- Fetch route (event_id, provider, series)

Per-row outcome logs:

- fetched / pending / error messages by route

End summary:

- Actuals(ignore window): end with { updated, skipped, errors }



## 9) Market Reaction Scoring (Blueprint ver.1.4) — REWRITTEN (code-authoritative)

### 9.1 Purpose and scope (what exists)

Market Reaction Scoring in ver.1.4 is implemented in market_scoring.gs. Its purpose is to compute a short-horizon USD/JPY move (in pips) around an event timestamp, log the computed move, and write best-effort evaluation fields back into matching Predictions rows.

What it does:

- Reads timestamps from the Event sheet (or common fallbacks, depending on the entrypoint)
- For each eligible timestamp, calls _computeUsdJpyMove_() to compute the move
- Applies best-effort evaluation updates to Predictions rows matched by `event_id`, and also to batch rows where `type = "batch"` and `event_id = batch_id`
- Emits the result via a logger hook (if present), and appends a summary log row at the end of the run

What it does not do in code:

- It does not build a separate warehouse-style reaction database or autonomous leaderboard service
- It does not persist raw candle arrays to sheets
- It does not write back to Event rows
- It does not support arbitrary FX pairs (USD/JPY only in this module)

### 9.2 Critical dependencies (must exist elsewhere for scoring to work)

market_scoring.gs calls two global symbols that are not defined in any of the uploaded .gs files:

- getFxCandlesForWindow_(pair, releaseTsUtc, preMin, postMin)
- log_ (used as log_ && log_(...))

Because these identifiers are referenced directly, if they are not provided by another file in your Apps Script project, this module will throw a ReferenceError when it reaches those lines.

Therefore:

- The Market Reaction module is not self-contained in the uploaded code set.
- It is effectively a scaffolding layer that requires an external candle-fetch provider and a logger function to be present in the project.

### 9.3 Core computation: _computeUsdJpyMove_()

Signature:

- _computeUsdJpyMove_(releaseTsUtc, preMin, postMin, horizonMin, meta)

Behavior:

Fetch candles:

- out = getFxCandlesForWindow_('USD/JPY', releaseTsUtc, preMin||30, postMin||120)

If out.candles is missing/empty:

- logs no_candles via log_ (if present)
- returns { status: 'no_candles' }

Find base candle (t0):

- t0 = releaseTsUtc.getTime()
- base = _nearestAtOrBefore_(out.candles, t0)

If missing: returns { status: 'no_base' }

Find horizon candle (t0 + horizon):

- horizonMs = t0 + (horizonMin||15)*60*1000
- h = _nearestAtOrBefore_(out.candles, horizonMs) || lastCandle

Compute move:

- p0 = base.close
- p1 = h.close
- diff = p1 - p0
- pips = round((diff * 100), 2)  
  (USD/JPY: 0.01 JPY = 1 pip → multiply by 100; rounded to 2 decimals)

Direction flag:

- dir = 1 if pips > 0
- dir = -1 if pips < 0
- dir = 0 if pips == 0

Attach metadata:

- merges meta fields into the result object (only if the key isn’t already present)

Emits:

- logs computed_move via log_ (if present)

Return object includes at minimum:

- status: 'ok'
- provider: out.provider
- t0_ts, tH_ts
- t0_price, tH_price
- horizon_min
- pips
- dir
- max_up_pips
- max_down_pips
- realized_sustain_min
- plus any supplied meta fields

Important retrieval detail:

- The scorer makes one candle-window request per event and then evaluates the returned 1-minute candle array in memory.
- It does not perform one provider request per minute.

### 9.4 Entry points exposed on the menu

The menu items for Market Reaction are defined in Code.gs → onOpen() under:

- ④ Market Reaction
- Score Market Reaction (past 24h) → scoreMarketReactionPast24h_()
- Score Market Reaction (Config Window) → scoreMarketReactionByConfigWindow_()
- Debug Timestamp Sample → debugEventTimestampSample_()

### 9.5 scoreMarketReactionPast24h_() (Event-only, Date-only)

This worker:

- Uses CFG.SHEET_EVENT (default 'Event')
- Reads all Event rows
- Chooses the timestamp column:
  - prefers released_ts
  - else uses release_ts
  - if neither exists → throws

Eligibility rules (strict):

- It only accepts rows where the timestamp cell is a Date object (ts instanceof Date)
- It only scores events with:
  - since <= ts <= now, where since = now - 24 hours

For each eligible row it calls:

- _computeUsdJpyMove_(ts, 30, 120, _getMarketReactionHorizonMin_(cfg), { event_id, row_index, source:'past24h' })

It also attempts to apply evaluation results to matching Predictions rows via `_applyEvaluationToPredictions_()`.

At end it attempts:

- appendLog(getSheet(CFG.SHEET_LOG), 'INFO', 'ScoreMarketReaction(past24h)', { checked_events: count })

### 9.6 scoreMarketReactionByConfigWindow_() (Config-windowed, flexible parsing)

This worker:

- Requires a Config sheet (throws if missing)
- Requires MR_WINDOW_ENABLED == 'TRUE' (string compare uppercased)
  - otherwise logs skipped and returns

Parses:

- MR_WINDOW_TZ
- MR_WINDOW_FROM_LOCAL
- MR_WINDOW_TO_LOCAL
- MR_ANCHOR_MIN_ABS_MOVE_PIPS (optional; defaults to 3 pips for anchor-detection thresholding)
- MR_ANCHOR_LOOKBACK_MIN (optional; defaults to 1 minute)
- MR_ANCHOR_LOOKAHEAD_MIN (optional; defaults to 5 minutes)

It converts them to UTC Dates with _parseLocalToUtc_():

- accepts Date cells, ISO strings, or strict YYYY-MM-DD HH:mm interpreted in MR_WINDOW_TZ

If parse fails:

- logs parse_error and throws

Event sheet resolution:

- _getEventSheet_() tries, in order:
  - CFG.SHEET_EVENT (if set)
  - Event, Events, RawCalendar, RawCaldendar

It requires a sheet with at least 1 row and 1 column

Timestamp extraction per row:

- _getEventReleaseTs_(row, idxMap, tz) tries many column name variants and fallback heuristics (ts/time-like columns), accepting Date objects or parseable strings.

Window filter:

- includes rows where fromUtc <= ts <= toUtc

Scoring call:

- _computeUsdJpyMove_(ts, 30, 120, _getMarketReactionHorizonMin_(cfg), { event_id, row_index, source:'config_window' })

Anchor-detection behavior inside `_computeUsdJpyMove_()`:

- compute baseline from the nearest candle close at or before `release_ts`
- search for a meaningful reaction candle inside:
  - `release_ts - MR_ANCHOR_LOOKBACK_MIN`
  - `release_ts + MR_ANCHOR_LOOKAHEAD_MIN`
- use `MR_ANCHOR_MIN_ABS_MOVE_PIPS` as the minimum absolute move threshold
- prefer the first post-release threshold-crossing candle
- fall back to a pre-release candidate only when no post-release candidate exists
- if no candidate exists, return a `flat` reaction with `pips = 0`
- classify realized direction as `flat` when `abs(pips) < MR_FLAT_MAX_ABS_PIPS` while preserving the raw measured pip value
- use the same flat threshold when comparing provider directions
- when `MR_SKIP_ALREADY_SCORED = TRUE`, skip Config-window events that already have market-reaction results in matching Predictions rows before fetching candles

For each successful reaction object, the scorer writes best-effort evaluation fields into matching Predictions rows, including batch rows whose `event_id` matches the source event's `batch_id`:

- legacy evaluation fields such as `realized_pips`, `dir_ok`, `band_ok`, `overall_ok`
- market-reaction prediction fields such as `mr_real_dir`, `mr_strength_ok`, `mr_real_sustain_min`, `mr_sustain_error_min`, `mr_sustain_grade`, `mr_sustain_ok`, `mr_real_max_up_pips`, `mr_real_max_down_pips`

Realized and default predicted strength are classified from absolute net pips as weak < 5, medium < 15, and strong >= 15.

Safety cap:

- breaks after 300 checked events (intended), but checked is never incremented, so the cap does not actually engage.

End-of-run log:

- appendLog(... 'ScoreMarketReaction(config)', { window_from_utc, window_to_utc, total_rows, parsed_ts_rows, rows_in_window, checked_events })

### 9.7 Sustain evaluation model

`realized_sustain_min` is computed from the fetched 1-minute candles after the event start.

Effective behavior:

- Determine the dominant initial direction from the larger absolute value of `max_up_pips` vs `max_down_pips` inside the configured reaction horizon
- Scan forward on 1-minute candle closes up to `max(horizon, 60)` minutes
- Treat sustain as directionally valid while the close remains at least 1 pip on the correct side of the start price
- Allow up to 2 consecutive violating closes before sustain ends
- Return the last valid minute as `realized_sustain_min`

This is a directional-validity measure, not a requirement to retain a fixed share of the initial spike.

Here, “event start” means the detected anchor when one exists; otherwise the scorer records a flat/no-reaction outcome and sustain remains `0`.

### 9.8 Debug tools

`debugMarketReactionCandlesForEvent_(eventId)`:

- resolves the Event row by `event_id`
- fetches the same candle window used by normal scoring
- returns and logs:
  - `start_point`
  - `end_point`
  - `horizon_min`
  - `pips`
  - `dir`
  - provider metadata

It is intended for event-specific candle verification without writing the full candle array to the sheet.

`debugEventTimestampSample_()`:

This function exists to inspect how timestamps are parsed across different column layouts and timezones. It does not score; it is a diagnostics helper to validate that event timestamps can be interpreted as UTC Dates.



## 10) Logging, Error Handling, and Operational Guarantees (Blueprint ver.1.4)

### 10.1 Logging architecture (two-layer design)

Logging is implemented as:

Low-level log writer (always-load shim) — 00_logging_shim.gs  
Provides:

- ensureHeaders(sheet, headers)  
  If header row is empty → writes full headers.  
  Otherwise → fills missing header cells left-to-right without shifting columns.

- appendLog(sheet, level, message, context)  
  Ensures headers (best effort).  
  Writes one row: [ts_iso, level, message, context_json]  

Context JSON is safe-stringified:

- truncates long strings (per-string cap)  
- prevents circular references  
- truncates total JSON string to a maximum size  

Module wrapper logger(s) — primarily in actuals_fetcher.gs  
Provides:

- _log_(logSheet, level, msg, ctx)  
  Preferred path: appendLog(logSheet, level, msg, ctx)  
  Fallback path: raw appendRow([ts, level, msg, JSON.stringify(ctx)])  
  Errors are swallowed (best effort).

Canonical log sheet headers (as written by code):

- ts, level, message, context_json

---

### 10.2 Log sheet creation policy (strict)

The system policy across control-plane runners is:

No sheet auto-creation for required operational sheets (Event / Predictions / log).  
Missing sheets generally cause a hard stop in high-level runners (throw Error).

However, this varies by module:

- Some modules explicitly check for missing sheets and throw (e.g., Event/log required checks).  
- Some modules attempt to “touch” the log sheet but do not create it (e.g., getSheet('log') in prediction_runner.gs returns null if missing, and logging then becomes a no-op).

Exception: SeriesMap workflow utilities may auto-create SeriesMap_Suggestions (this is not part of the core run-loop logging system).

---

### 10.3 Logging reliability (best-effort, may drop)

Because appendLog() requires the sheet object as its first argument:

- Calls like appendLog(getSheet(CFG.SHEET_LOG), 'INFO', ...) write correctly.  
- Calls like appendLog('info', 'message', ctx) do not write (the “sheet” is a string).  

In these cases, logging effectively becomes silent / dropped, because the shim catches errors and avoids throwing.

In ver.1.4 codebase, both styles exist:

- Market scoring and many wrappers pass a sheet correctly.  
- The prediction runner’s internal appendLog(...) calls often do not pass a sheet, which means those log lines are best-effort but commonly dropped.

Operational guarantee: logging never blocks execution, but also cannot be relied on as complete unless the calling site passes the log sheet explicitly.

---

### 10.4 Error handling philosophy (control-plane vs worker code)

The system uses two different error strategies:

#### A) Control-plane menu wrappers (user-facing)

Typical behavior:

- Wrap work in try/catch  
- On failure:  
  - show a popup via showErrorPopup_(title, msg) (UI alert; toast fallback)  
  - attempt to write an error log (best effort)  
  - rethrow (so the execution transcript reflects the failure)

Examples:

- menuUpsertNext72h_()  
- manual actuals menu handlers  
- maintenance actions (health check, backfills)

#### B) Worker functions (data-plane)

Typical behavior:

- Skip invalid rows quietly (especially when parsing timestamps)  
- Do not crash the whole run for one bad row  
- Use “best effort” logging for skip reasons  

Examples:

- event normalization skips missing indicator_name / release_ts  
- actuals window runner skips rows that fail parsing  
- market scoring skips events missing price data  

---

### 10.5 Retry behavior (AI providers only)

Only the AI provider calls in prediction_runner.gs implement automatic retries:

- _withRetries_(fn, meta)  
  - attempts: 4  
  - exponential backoff with jitter  
  - base sleep: 800ms  
  - logs a retry record (but those retry logs may be dropped if the caller doesn’t pass a log sheet)

Provider failures do not stop the overall run:

- per-event/per-provider failures become error rows in Predictions (status + error_message + raw_output when available)  
- the runner continues to the next event/provider  

---

### 10.6 Hard-stop conditions (what will abort the run)

Runs will terminate immediately (throw) under these conditions:

- Required sheets do not exist in control-plane paths that explicitly check them (commonly Event/log).  
- Missing required columns for a function that explicitly enforces its header contract (e.g., batching post-pass requires: country, indicator_name, release_ts, event_id, batch_id, type).  
- Missing API keys when a provider is invoked and the worker treats it as required (e.g., FRED API key required for FRED fetch in certain paths).  

---

### 10.7 Non-blocking / skip conditions (what will not abort the run)

The following conditions usually do not abort a run:

- Individual rows with invalid timestamps (release_ts parse failures)  
- Events missing mapping (SeriesMap not found) during actuals fetch  
- Missing market price data for an event during market reaction scoring  
- Provider output that fails strict JSON parsing (prediction runner writes an error row and continues)  

---

### 10.8 User-visible feedback (UI notifications)

The system uses:

- Toast messages for success summaries (e.g., upsert summary).  
- Popup alerts for failures and some manual-run completion summaries via showErrorPopup_().  

If the execution context has no UI (e.g., trigger execution), showErrorPopup_() falls back to a toast where possible.

---

### 10.9 Operational guarantees (explicit)

Given the code behavior, ver.1.4 guarantees:

- No silent mutation of sheet schemas beyond “append missing headers” in targeted sheets that enforce headers (Event, Predictions, log, SeriesMap workflow sheets). No reordering is performed.  
- No single-row failure should abort multi-row worker loops for actuals scoring and market reaction (they skip and continue).  
- Logging is best-effort and non-blocking, and may be partially missing depending on call style.  
- Provider calls are retried, but provider failures do not stop the run; they are recorded as errors per event/provider.



## 11) Menus, Triggers, and Control-Plane Operations (Blueprint ver.1.4) — REWRITTEN (code-authoritative)

### 11.1 Menu installation (onOpen())

When the spreadsheet is opened in a UI context, onOpen() (in Code.gs) creates a custom menu:

PreSignal v1.4

This menu is the primary control plane for manual operations (ingestion, predictions, actuals, market reaction, maintenance).

---

### 11.2 Menu structure and handlers (exact wiring)

#### ① Events

This submenu contains both event ingestion and SeriesMap workflow actions:

- Fetch & Upsert (next 72h) → menuUpsertNext72h_()  
  Calls runFmpUpcomingToEvent_(3), then applyBatchingForKeys_(), then logs/toasts completion

- Fetch & Upsert (Config Window) → menuUpsertToEvent_()  
  Uses resolveWindow_('upsert_event') when enabled and falls back to upcoming 7d otherwise

- Build FRED Series Catalog → menuBuildFredSeriesCatalog_()

- Rebuild Suggestions from FMP Catalog → menuSeriesMapRebuildSuggestionsFromFmpCatalog_()

- AI Review Suggestion Batch → menuSeriesMapAiReviewBatch_()

- SeriesMap → Auto-suggest from FRED (Selected rows) → menuSeriesMapAutoSuggestFRED_()  
  Legacy selected-row helper; the primary fallback workflow is FMP catalog rebuild + optional AI review batch

- SeriesMap → Generate Proposals from Selected Suggestions → menuSeriesMapGenerateProposalsSelected_()  
  Requires active sheet = SeriesMap_Suggestions and rows selected  
  Delegates to _generateSeriesMapProposalsFromSuggestionRows_(...) (proposal generation pipeline)

- Promote Selected Suggestions → SeriesMap → menuSeriesMapPromoteSelected_()  
  Delegates to promoteSelectedSeriesMapSuggestions_() and logs + toast summary

---

#### ② Predictions

- Run Predictions (All Providers) → runPredictionsAll_()  
- Run Predictions (Config Window) → runPredictionsWindow()  
- Gemini (manual) → menuRunPredictionsGemini_()  
- OpenAI (manual) → menuRunPredictionsOpenAI_()  
- Claude (manual) → menuRunPredictionsClaude_()  

---

#### ③ Actuals

- Start Hourly Actuals Fetch → menuActualsStartHourly_()  
- Stop Hourly Actuals Fetch → menuActualsStopHourly_()  
- Fetch Actuals (Manual) → menuActualsManualFetch_()  

---

#### ④ Market Reaction

- Score Market Reaction (past 24h) → scoreMarketReactionPast24h_()  
- Score Market Reaction (Config Window) → scoreMarketReactionByConfigWindow_()  
- Build Evaluation Sheets → menuBuildEvaluationSheets_()  
- Debug Timestamp Sample → debugEventTimestampSample_()  

---

#### ⑤ Maintenance

- Backfill Missing Actuals → menuMaintenanceBackfillActuals_()  
  Calls fetchActualsIgnoreWindowOnce() (must exist, else throws)

- Backfill Market Reaction → menuMaintenanceBackfillMarketReaction_()  
  Calls scoreMarketReactionByConfigWindow_() (Config-window driven)

- Rebuild Logs / Diagnostics → menuMaintenanceDiagnostics_()  
  Non-destructive: logs a diagnostics report + UI alert

- System Health Check → menuMaintenanceHealthCheck_()  
  Checks required sheets exist + checks presence of key entrypoint functions + logs payload + UI alert

---

### 11.3 Trigger behavior (installable automation)

#### Hourly actuals trigger (as actually implemented)

menuActualsStartHourly_() creates an installable time-based trigger:

- Handler function: menuActualsManualFetch_()  
- Frequency: every 1 hour  
- De-duplication: before creating, it deletes any existing triggers whose handler is the same menuActualsManualFetch_()

menuActualsStopHourly_() removes triggers:

- Deletes all triggers whose handler is menuActualsManualFetch_()  
- Toasts how many were removed  

Important implication (code-authoritative):

The automation does not schedule runFetchActualsHourly_() (even though that function exists in actuals_fetcher.gs).

The scheduled automation path is:

trigger → menuActualsManualFetch_() → runFetchActualsWindow_(...).

---

### 11.4 Health check scope (what it validates)

menuMaintenanceHealthCheck_() checks:

Required sheets:

- Event  
- Predictions  
- log  

Function presence (symbol exists as function):

- menuUpsertToEvent_  
- menuPredAll_ (currently missing in uploaded code)  
- runPredictionsWindow  
- menuActualsStartHourly_  
- menuActualsManualFetch_  
- scoreMarketReactionPast24h_  
- scoreMarketReactionByConfigWindow_  

Key flags (presence only; does not reveal values):

- hasFmpKey → checks whether CFG.FMP_API_KEY is non-empty (does not check Script Properties)  
- hasAnyAiKey → uses _getKey_(...) if available to detect any AI key in Properties  

It logs a payload to the maintenance logger and shows an alert:

- “OK” if no missing sheets and no missing functions  
- otherwise “NOT OK” with missing lists  

---

### 11.5 “No auto-create” policy (control plane)

Menu actions generally assume required tabs exist. Where wrappers explicitly guard for existence, missing tabs cause a hard error. (SeriesMap_Suggestions is an exception created by SeriesMap utilities, not by core control-plane guards.)

---

### 11.6 Known wiring gaps (present in code as of ver.1.4)

These are not documentation issues—they are literal code-state issues:

- The menu item “Run Predictions (Config Window)” points to runPredictionsWindow(), which exists in the current code.  
- Health check also expects `menuPredAll_`, which is still missing in the uploaded .gs files.  

These mismatches mean:

The Predictions “Config Window” menu item is callable, but health check can still report “NOT OK” until `menuPredAll_` is implemented or removed from the checklist.



## 12) Configuration & Constants (Blueprint ver.1.4)

### 12.1 Authoritative configuration sources (precedence)

In ver.1.4, configuration values are pulled from three places. Precedence depends on the module:

#### Hard-coded CFG object in Code.gs
This is the global, baseline config for sheet names, FMP, and SeriesMap triage.

#### Module-local default CFG (Prediction Runner only) — prediction_runner.gs
prediction_runner.gs uses var CFG = (typeof CFG !== 'undefined') ? CFG : { ...defaults... } and then _ensureCfgDefaults_() to fill missing keys.  
This means Code.gs CFG is primary, and prediction-runner defaults fill any missing keys.

#### Spreadsheet tab: Config (key/value overrides) — Prediction Runner only
prediction_runner.gs reads Config!A:B and overrides selected keys (providers, window override, etc.).  
Other modules in this codebase do not use this Config sheet override path.

Supported prediction-specific keys include:

- PREDICTION_MODE = LIVE | BACKTEST
- BACKTRACK is accepted as an alias for BACKTEST
- In LIVE mode, rows with existing actuals markers on Event are skipped
- In BACKTEST mode, those rows remain eligible for selection
- PREDICTION_TEMPERATURE = numeric sampling control
- PREDICTION_SEED = integer seed for provider requests
- PRED_WINDOW_ENABLED / PRED_WINDOW_FROM_LOCAL / PRED_WINDOW_TO_LOCAL / PRED_WINDOW_TZ for prediction-only windowing
- Legacy shared `WINDOW_*` values are used only as fallback by the prediction runner

#### Apps Script Properties (API keys) — multiple modules
FMP: Script Properties FMP_API_KEY (fallback if CFG.FMP_API_KEY is empty)  
FRED: Script Properties FRED_API_KEY (required for FRED fetch paths)  
LLMs (prediction runner): Script/User/Document Properties are searched (in that order) for keys.

---

### 12.2 CFG in Code.gs (global baseline)

The following keys are defined in Code.gs and are authoritative defaults for ver.1.4:

#### Sheet names
CFG.SHEET_EVENT = 'Event'  
CFG.SHEET_PRED = 'Predictions'  
CFG.SHEET_LOG = 'log'  

#### FMP calendar ingestion
CFG.FMP_API_KEY = ''  
If blank, ingestion falls back to Script Property FMP_API_KEY  

CFG.FMP_BASE = 'https://financialmodelingprep.com/api/v3'  

#### Country scoping
CFG.FMP_COUNTRY = 'US'  
Used as an attempted server-side filter (&country=US) when calling FMP  

CFG.COUNTRY_FILTER = ['US']  
Always enforced locally after normalization; if present, only these countries are kept  

#### SeriesMap workflow sheet names
CFG.SHEET_SERIESMAP_SUGGESTIONS = 'SeriesMap_Suggestions'  
CFG.SHEET_SERIESMAP_PROPOSALS = 'SeriesMap_Proposals'  
CFG.SHEET_SERIESMAP = 'SeriesMap'  

#### SeriesMap triage controls (proposals generation)
CFG.SERIESMAP_TRIAGE_MODE = 'MANUAL'  
CFG.SERIESMAP_TRIAGE_OPENAI_MODEL = 'gpt-5.2' (declared “future” in code comments)  
CFG.SERIESMAP_TRIAGE_ALLOW_FALLBACK_MODELS = false  

---

### 12.3 Prediction Runner defaults (prediction_runner.gs)

The Prediction Runner defines additional keys (or default fills) used only by prediction generation:

#### Provider + model defaults
CFG.PROVIDERS = ['Gemini','OpenAI','Anthropic']  
CFG.GEMINI_MODEL = 'gemini-2.0-flash'  
CFG.OPENAI_MODEL = 'gpt-4o-mini'  
CFG.CLAUDE_MODEL = 'claude-3-5-sonnet-latest'  

#### Window defaults
CFG.WINDOW_MIN_BEFORE_MIN = 24*60  
CFG.WINDOW_MAX_AFTER_MIN = 36*60  

#### Other prediction defaults
CFG.DEFAULT_FX = 'USDJPY'  
CFG.DRY_RUN_PREDICT = false  
CFG.PIPS_BY_IMPORTANCE = { low:[3,10], medium:[8,25], high:[15,45], critical:[25,80] }  
CFG.SCHEMA_VERSION = '1.4'  
CFG.RULE_VERSION = '1.4'  

Note: These defaults only apply if CFG does not already define the key (or defines it as empty). In practice, Code.gs provides the base CFG, then the runner fills missing prediction-related keys.

---

### 12.4 Config sheet overrides (prediction runner only)

If a sheet named Config exists, the Prediction Runner reads it as:

Column A = key  
Column B = value  

Recognized override keys:

#### Provider selection
PROVIDERS  
Comma-separated list of: Gemini, OpenAI, Anthropic  
Alias: Claude is normalized to Anthropic  

#### FX pair
DEFAULT_FX  

#### Dry run
DRY_RUN_PREDICT (boolean-ish)  

#### Pips band overrides
PIPS_LOW_MIN, PIPS_LOW_MAX  
PIPS_MEDIUM_MIN, PIPS_MEDIUM_MAX  
PIPS_HIGH_MIN, PIPS_HIGH_MAX  
PIPS_CRITICAL_MIN, PIPS_CRITICAL_MAX  

#### Local window override (preferred when enabled)
WINDOW_ENABLED (true/false)  
WINDOW_FROM_LOCAL (e.g., YYYY-MM-DD HH:mm or a Date cell)  
WINDOW_TO_LOCAL  
WINDOW_TZ (IANA, e.g., Asia/Tokyo)  

If the local window override is enabled but parsing fails, it falls back to the normal rolling window.

---

### 12.5 API key resolution (authoritative)

#### FMP
Used by fmp_calendar.gs  

Resolution order:  
CFG.FMP_API_KEY (if non-empty)  
Script Property FMP_API_KEY  

If neither is present → ingestion throws.

#### FRED
Used by actuals modules and FRED autosuggest  

Requires Script Property:  
FRED_API_KEY  

If missing:  
autosuggest and FRED fetch paths error/return null (module-dependent)

#### Gemini
Key names tried:  
GEMINI_API_KEY, GOOGLE_API_KEY, GOOGLE_AI_STUDIO_API_KEY  

Property stores searched (in order):  
Script → User → Document  

#### OpenAI
Key name:  
OPENAI_API_KEY  

Property stores searched (in order):  
Script → User → Document  

#### Anthropic
Key name:  
ANTHROPIC_API_KEY  

Property stores searched (in order):  
Script → User → Document  

Providers without keys are treated as “not enabled.”

---

### 12.6 Actuals harvester constants (actuals_fetcher.gs)

Actuals uses a separate config object:

ACTUALS_CFG defaults:  
LOOKBACK_MINUTES = 14 * 24 * 60  
LOOKAHEAD_MINUTES = 60  
MAX_ROWS_PER_RUN = 400  
SOURCE_PRIORITY = ['FRED','FMP']  
DEFAULT_TZ = 'UTC'  
SERIESMAP_SHEET = 'SeriesMap'  

This config is not overridden by the Config sheet in the current code.

---

### 12.7 Market reaction scoring constants (market_scoring.gs)

Market reaction scoring does not use Config overrides in the current code. It uses hard-coded default parameters in the scorer entrypoints:

scoreMarketReactionPast24h_() calls _computeUsdJpyMove_(ts, 30, 120, 30, meta)  

pre-window = 30 min  
post-window = 120 min  
horizon = 30 min  

It computes the move using close-to-close difference at t0 and t0 + horizon.

---

### 12.8 Important correction note (discovered during code verification)

While preparing Section 12, I verified the actual .gs files directly and found that some behaviors in earlier accepted sections (notably Market Reaction and menu structure details) need to be realigned to the current code—for example, the market scorer uses a 30/120-minute candle window and a 30-minute horizon, not a 5/30-minute window.


## 13) System Execution Flow (End-to-End) (Blueprint ver.1.4)

### 13.1 Overview: canonical data flow

The system is designed to run in this order:

Ingest scheduled events → writes rows to Event  
Assign identity + batching → fills event_id / batch_id / type in Event  
Build/maintain SeriesMap (manual workflow) → prepares mapping for actuals  
Run predictions → writes rows to Predictions  
Fetch actuals → writes released_value / released_ts / release_status back to Event  
Compute market reaction (USD/JPY move) → logs computed pips moves  

Each step is independent and can be run manually. Some steps can be automated (hourly actuals trigger). Market reaction scoring is manual (or maintenance-triggered via config window).

---

### 13.2 Step 1 — Events ingestion (scheduled calendar → Event)

Trigger: Menu → ① Events → Fetch & Upsert (next 72h)  
Handler: menuUpsertNext72h_()

What it does:

Calls FMP economic calendar for the next 72 hours  
Normalizes raw rows into Event schema (scheduled-only)  
Upserts into Event using key: country|indicator_name|release_ts  
Sorts Event by release_ts (best effort)  
Clears event_id / batch_id / type during upsert (by design)  
Immediately runs batching to repopulate them  

Outputs:

Event rows updated/inserted  
log records (best effort)  
Toast summary  

---

### 13.3 Step 2 — Identity + batching (Event post-pass)

Trigger: Automatically performed at end of ingestion (Step 1)  
Worker: applyBatchingForKeys_()

What it does:

Groups events by (COUNTRY, minute(release_ts))  

For groups of size 1:  
type='single', batch_id=''  

For groups of size ≥2:  
all become type='member', share the same batch_id  

Assigns stable event_id per event using (country, minuteISO, indicator_name)  

Outputs:

Event updated with deterministic IDs and batch classification  

---

### 13.4 Step 3 — SeriesMap fallback maintenance (manual, selective)

Actuals fetching does not require universal SeriesMap coverage. The primary path is direct FMP calendar resolution. SeriesMap is maintained only for indicators where fallback coverage materially improves actuals reliability.

Canonical manual workflow:

Build/refresh FRED fallback pool  
Menu → ① Events → Build FRED Series Catalog

Rebuild fallback suggestions from the FMP catalog  
Menu → ① Events → Rebuild Suggestions from FMP Catalog

Review uncertain rows in batches (optional)  
Menu → ① Events → AI Review Suggestion Batch

Promote selected suggestions into SeriesMap  
Menu → ① Events → Promote Selected Suggestions → SeriesMap  
Handler: menuSeriesMapPromoteSelected_() → promoteSelectedSeriesMapSuggestions_()

Outputs:

SeriesMap_Suggestions updated/created as a review queue  
SeriesMap appended only with operator-approved fallback mappings  

---

### 13.5 Step 4 — Predictions generation (Event → Predictions)

Trigger: Menu → ② Predictions → Run Predictions (All Providers) or provider-specific manual runs  
Handler: runPredictionsAll_() (or menuRunPredictionsGemini_/OpenAI_/Claude_())

Preconditions:

Event rows must have non-empty event_id and type (Step 2)  
At least one provider must have a usable API key in Properties  
Predictions sheet must exist  

What it does:

Selects Event rows within a rolling window (default: -24h to +36h from now)  
Calls enabled providers and enforces strict JSON response contract  
Writes one row per (event_id × ai_name) into Predictions (upsert)  

For batched events (type='member' + batch_id):  
generates one provider batch prediction row per enabled provider in Predictions with event_id=batch_id and type='batch'  

Important wiring note (code-authoritative):

The menu item “Run Predictions (Config Window)” is wired to runPredictionsWindow(), which exists in the current code. Health-check output can still be partially stale because `menuPredAll_` remains absent.

Outputs:

Predictions updated/inserted rows  
log records are best-effort and may be partially dropped depending on call style  

---

### 13.6 Step 5 — Actuals fetching (SeriesMap → Event release fields)

There are two distinct actuals mechanisms:

#### A) Rolling-window actuals harvester (recommended operational path)

Trigger (manual): Menu → ③ Actuals → Fetch Actuals (Manual)  
Trigger (automation): Menu → ③ Actuals → Start Hourly Actuals Fetch  
(creates trigger that calls menuActualsManualFetch_() hourly)

Worker: runFetchActualsWindow_(...) in actuals_fetcher.gs

What it does:

Selects Event candidates within a time window and status logic  
Skips qualitative items (speech/minutes/testimony etc.)  
Attempts direct deterministic FMP calendar resolution first  
If direct resolution fails, resolves SeriesMap fallback mapping  
Fetches fallback actuals using provider priority (FRED-primary within fallback; FMP calendar lookup only when series_id is calendar:<...>)  
Writes back to Event:  
released_value, released_ts, source_provider, source_series_id, transform, release_status  

Uses a lifecycle: scheduled → released → revised (based on value change)  

#### B) Ignore-window backfill (maintenance-only, different status vocabulary)

Trigger: Menu → ⑤ Maintenance → Backfill Missing Actuals  
Worker: fetchActualsIgnoreWindowOnce() in actual_backfill.gs  

What it does:

Scans all Event rows without time windows  
Only fills missing released_value  
Uses SeriesMap + limited internal auto-map fallback  
Uses status values: pending / fetched / error (does not match rolling harvester’s lifecycle)  

---

### 13.7 Step 6 — Market reaction scoring (USD/JPY move)

Trigger (manual): Menu → ④ Market Reaction → Score Market Reaction (past 24h)  
Handler: scoreMarketReactionPast24h_()

Trigger (config window): Menu → ④ Market Reaction → Score Market Reaction (Config Window)  
Handler: scoreMarketReactionByConfigWindow_()

What it does:

Reads Event timestamps (prefers released_ts, else release_ts)  
For each eligible timestamp, calls _computeUsdJpyMove_(ts, pre=30, post=120, horizon=30, meta)  
Logs computed move; does not update sheets  

Critical dependency (code-authoritative):

Requires external function getFxCandlesForWindow_() to exist in the project (not present in uploaded code set). Without it, scoring will throw when invoked.

---

### 13.8 Minimal “successful run” checklist

A minimal, fully working end-to-end run (as code currently behaves) looks like:

Create required tabs: Event, Predictions, log, SeriesMap, SeriesMap_Suggestions  

Set Script Properties:  
FMP_API_KEY  
FRED_API_KEY (if you want actuals from FRED)  
at least one AI key (Gemini/OpenAI/Anthropic)  

Run:  
Events upsert (next 72h)  
(optional) SeriesMap suggestions + promote mappings  
Predictions (All Providers)  
Actuals manual fetch (or start hourly)  
Market reaction scoring (only if candle fetcher exists)



## 14) Data Contracts: Required Columns, Required Types, and Validation Rules (Blueprint ver.1.4)

### 14.1 Contract model (how the system reads/writes sheets)

Across the codebase, the contract model is:

Sheets are treated as header-addressed tables  
Column order is not fixed, but headers must exist for any fields the module uses  
When a module “enforces headers,” it does so by:  
writing a header row if empty, or  
appending missing required headers to the right  
it does not reorder existing columns  

All validation is runtime and “best effort.” If a required header is missing in a function that explicitly validates it, the function throws.

---

### 14.2 Event sheet contract (Event)

#### 14.2.1 Required headers (for core ingestion + downstream runs)

FMP ingestion enforces these headers (appending missing at end):

object, country, indicator_name, genre, importance, type, event_id, batch_id, release_ts, source_cal, consensus_value, prev_revision, released_value, released_ts, source_provider, source_series_id, transform, release_status, notes

#### 14.2.2 Required fields by module (read requirements)

A) Batching post-pass (applyBatchingForKeys_())  
Requires these headers to exist:

country  
indicator_name  
release_ts  
event_id  
batch_id  
type  

If any are missing, the function throws.

B) Prediction Runner (event selection)  
Requires these headers to exist to meaningfully run:

event_id (must be non-empty per row)  
type (must be non-empty per row)  
release_ts (must be parseable)  

It also reads (optional but used in prompts and output context):

batch_id, country, indicator_name, genre, importance, source_cal, consensus_value, prev_revision  

C) Actuals harvester (runFetchActualsWindow_())  
Reads:

event_id (required for logging and context)  
country, indicator_name (required for mapping)  
release_ts (required for window gating)  
release_status (preferred) or status (fallback)  
released_value (for revision detection)  

(writes) released_value, released_ts, source_provider, source_series_id, transform, release_status  

D) Market reaction scoring (scoreMarketReactionPast24h_())  
Requires at least one of:

released_ts (preferred) OR release_ts (fallback)  

Important type requirement (code-authoritative):

In scoreMarketReactionPast24h_(), timestamps are only accepted if the cell is a Date object (not a string).  
In scoreMarketReactionByConfigWindow_(), string timestamps can be parsed.

---

### 14.3 Predictions sheet contract (Predictions)

#### 14.3.1 Required headers (enforced by prediction runner)

The runner ensures these headers exist (append missing at end):

object, run_id, prediction_id, schema_version, created_ts, event_id, batch_id, type, ai_name, ai_version, ai_model, model_version, consensus_value, prev_revision, source_cal, genre, importance, fx_pair, ai_forecast_value, qualitative_result, expected_move_dir, expected_move_pips_min, expected_move_pips_max, expected_holding_minutes, rationale_short, rationale, prompt_tokens, completion_tokens, latency_ms, raw_output, status, error_message, qualitative_only  

#### 14.3.2 Required fields for upsert identity

The runner uses the upsert identity:

(event_id, ai_name)

So these fields must be present in headers for deterministic upserts:

event_id  
ai_name  

If either header is missing, the runner’s write path will misalign or fail.

#### 14.3.3 Required value types (effective)

created_ts: ISO string  
schema_version: string (default 1.4)  
event_id: string (UUID-like)  
type: one of:  
'single' | 'member' | 'batch'  
ai_name: string (e.g., Gemini, OpenAI, Anthropic)  
ai_forecast_value: numeric or blank (forced blank for qualitative-only)  
expected_move_pips_min/max: numeric  
expected_holding_minutes: integer-ish  
status: string (ok or error-status variants)  
raw_output: string (may contain raw provider response)  
qualitative_only: stored as a sheet-compatible boolean/string value depending on normalization; batch rows are provider rows and follow the same write path  

---

### 14.4 log sheet contract (log)

#### 14.4.1 Required headers

The logging shim expects:

ts, level, message, context_json  

#### 14.4.2 Field types

ts: ISO string timestamp  
level: 'info' | 'warn' | 'error' (case varies by caller)  
message: short string label  
context_json: JSON string (safe-stringified and truncated)  

---

### 14.5 SeriesMap contracts

#### 14.5.1 SeriesMap required headers (for resolution)

country  
indicator_name_pattern  
provider  
series_id  

Optional but used:

freq, unit_type, transform, notes  

If series_id is blank, resolution returns null even if the pattern matches.

#### 14.5.2 SeriesMap_Suggestions headers

The suggestion sheet is auto-created (if missing) and contains:

Base:

country, indicator_name_pattern, provider, series_id, freq, unit_type, transform, seasonal_adjustment, precision_dp, lag_rule, notes, created_ts  

Primary suggestion:

cand_1_provider, cand_1_series_id, cand_1_title, cand_1_score, cand_1_freq  

Append-only review metadata used by the FMP-catalog rebuild workflow:

indicator_name  
source_observations_count, source_unit, source_frequency, source_impact  
source_first_release_ts, source_last_release_ts  
source_avg_actual, source_avg_estimate  
suggested_provider, suggested_series_id, suggested_title  
suggested_confidence, suggested_reasoning  
review_status, review_method  
auto_classification, auto_notes, auto_run_ts  

The system appends missing headers; it does not reorder.

---

### 14.6 Strict JSON contract (AI output validation)

All AI providers are instructed to return strict JSON. The runner requires the parsed object to include:

object: "ai_prediction"  
event_id (must exist)  
type (must exist)  

Additionally, the runner validates that:

returned event_id/type match the Event row, and it overwrites them if needed.  

If parsing fails or required fields are missing:

The runner writes an error row with:

status indicating failure  
error_message  
raw_output captured if possible  


## 15) Provider Integrations: API Calls, Payloads, and Rate/Quota Behaviors (Blueprint ver.1.4)

### 15.1 Integration map (what external services are used for what)

The uploaded .gs code integrates the following external services:

FMP (Financial Modeling Prep)  
Economic calendar ingestion (Event population)  
Direct actual resolution first via FMP calendar matching; fallback actual resolution only when SeriesMap uses an explicit maintained mapping  

FRED (St. Louis Fed)  
Actuals source (primary)  
SeriesMap auto-suggest via series search API (operator workflow)  

LLM Providers (Predictions)  
Gemini (Google Generative Language API)  
OpenAI (Chat Completions API)  
Anthropic (Claude) (Messages API)  

---

### 15.2 Credentials (where keys are read from)

#### 15.2.1 Script Properties keys (explicitly required / referenced)

FRED  
FRED_API_KEY  
Used by:  
actuals_fetcher.gs (_fredFetchObservations_)  
seriesmap_fred_autosuggest.gs (FRED series search)  

FMP  
FMP_API_KEY  
Used by:  
actuals_fetcher.gs fallback adapter _fmpFetchActual_() when CFG.FMP_API_KEY is not set  

#### 15.2.2 Prediction provider keys (multi-property resolution)

The prediction runner resolves keys using _getKey_() across:

Script Properties  
User Properties  
Document Properties  

Key names:

Gemini  
GEMINI_API_KEY, GOOGLE_API_KEY, GOOGLE_AI_STUDIO_API_KEY (first found wins)  

OpenAI  
OPENAI_API_KEY  

Anthropic  
ANTHROPIC_API_KEY  

Important (code-authoritative):

Provider enablement is purely “key-present” based. If a provider’s key is missing, it is not enabled, even if listed in CFG.PROVIDERS.

---

### 15.3 FMP integration (calendar ingestion)

#### 15.3.1 Endpoint used

GET https://financialmodelingprep.com/api/v3/economic_calendar  

Query parameters:  
from=YYYY-MM-DD  
to=YYYY-MM-DD  
apikey=<FMP_API_KEY>  

#### 15.3.2 Data normalization behavior (calendar → Event row)

Implemented in normalizeFmpRow_():

object = "econ_event"  
country uppercased from country|ccy|region  
indicator_name from indicator_name|title|event|name|category  
consensus_value from consensus|estimate|forecast|expected (numeric-cleaned)  
prev_revision from previous|prev|prior|revisedPrevious… (numeric-cleaned)  
release_ts parsed and rounded to nearest minute UTC ISO  
source_cal = "FMP"  
release_status:  
default "scheduled" (the ingestion path does not set “released”)  
type/event_id/batch_id left blank and filled by post-pass batching logic  

#### 15.3.3 Upsert identity (Event ingestion)

Event upsert key (fallback identity) is:

country + '|' + indicator_name + '|' + release_ts  

As implemented in _upsertEventsToEvent_().

---

### 15.4 FRED integration (actuals)

#### 15.4.1 Endpoint used (observations)

GET https://api.stlouisfed.org/fred/series/observations  

Query parameters (as built in _fredFetchObservations_()):

series_id=<SERIES>  
api_key=<FRED_API_KEY>  
file_type=json  
observation_start=YYYY-MM-DD  
observation_end=YYYY-MM-DD  

Window logic:

The fetcher requests an 18-month lookback ending at the end of the reference month (refDate derived from event release time).

#### 15.4.2 Caching behavior (FRED observations)

CacheService.getScriptCache() is used with a key of:

fred:<seriesId>:<YYYY-MM>:<YYYY-MM>  

If cached, the fetcher returns cached observations without an HTTP call.

#### 15.4.3 How an “actual” is selected

Fetch returns an observations[] array.  
The code selects a “latest” observation within the request range using _pickLatestObservationInWindow_(...).  

The final numeric value is:

either the level (transform empty/level)  
or a transform computed by _computeTransform_(transform, observations).  

Supported transforms in _computeTransform_():

level (default)  
mom / pct_change / pct_mom  
yoy / pct_yoy  
saar  
diff / delta / chg  

Unknown transforms fall back to level.

---

### 15.5 FMP integration (actuals fallback adapter)

This exists, but is explicitly a limited fallback.

#### 15.5.1 When FMP actuals fallback is attempted

In _fmpFetchActual_():

series_id must match the pattern:  
calendar:<Event Name>  

The adapter then calls the FMP calendar endpoint for a ±1 day window around the reference date and searches for:

exact case-insensitive match on row.event  
and a non-empty row.actual  

#### 15.5.2 Output shape

If found, it returns:

{ hasActual:true, value:Number(actual), ts:<iso or fallback>, provider:'FMP', series_id:<series_id> }  

If not found (or if parsing fails), it returns { hasActual:false }.

---

### 15.6 LLM integration (Predictions)

All LLM calls originate from prediction_runner.gs and are made through UrlFetchApp.fetch(...).

#### 15.6.1 Common prompt contract (all providers)

The runner constructs a strict JSON prompt object:

system: role instruction (“macroeconomic forecasting model”)  
user: JSON string containing the event context and required output schema  
instruction: explicitly requires strict JSON only and forbids units/symbols in numeric values  

Strict validation is enforced by _strictParsePredictionJson_():

Must be JSON  
Must be object (or array where the first valid object is extracted)  
Must contain:  
object == "ai_prediction"  
event_id  
type  

#### 15.6.2 OpenAI (Chat Completions)

Endpoint:

POST https://api.openai.com/v1/chat/completions  

Headers:

Authorization: Bearer <OPENAI_API_KEY>  

Body (core fields):

model: <CFG.OPENAI_MODEL>  
response_format: { type: "json_object" }  
messages: [{role:"system", ...}, {role:"user", ...}]  

Notes:

If HTTP 429 occurs, it is treated as quota and retried.  
If HTTP 5xx occurs, treated as provider error and retried.  
If non-2xx otherwise, throws with response content.  

Usage capture:

j.usage.prompt_tokens  
j.usage.completion_tokens  

#### 15.6.3 Gemini (Generative Language API)

Endpoint:

POST https://generativelanguage.googleapis.com/v1beta/models/<model>:generateContent?key=<GEMINI_API_KEY>  

Body (core fields):

contents: [{ role:"user", parts:[{text: ...}] }]  
generationConfig: { response_mime_type: "application/json" }  

Parsing behavior:

Strips code fences if present.  
Extracts the first {...} JSON object if extra text surrounds it.  
Validates using _strictParsePredictionJson_().  

Usage capture:

usageMetadata.promptTokenCount  
usageMetadata.candidatesTokenCount  

#### 15.6.4 Anthropic (Claude)

Endpoint:

POST https://api.anthropic.com/v1/messages  

Headers:

x-api-key: <ANTHROPIC_API_KEY>  
anthropic-version: 2023-06-01  

Body (core fields):

model: <CFG.CLAUDE_MODEL>  
max_tokens: 2048  
system: <prompt.system>  
messages: [{ role:"user", content: ... }]  

Usage capture:

usage.input_tokens  
usage.output_tokens  

---

### 15.7 Rate limiting, retries, and burst control

#### 15.7.1 Predictions retry policy (Gemini / OpenAI / Anthropic)

All provider calls are wrapped in _withRetries_():

Attempts: 4  
Backoff: exponential (2^i * baseMs) with jitter  
Base delay: 800ms  

Retries occur for:

quota errors (429 → quota_exceeded)  
provider errors (non-2xx, parsing failures, empty content)  

Each retry logs:

level: warn for quota, error otherwise  
includes: provider name, wait_ms, and error message  

#### 15.7.2 FRED auto-suggest throttling (SeriesMap tool)

seriesmap_fred_autosuggest.gs uses explicit throttling:

sleep per call: default 800ms  

burst control:

burstSize default 5  
burstSleepMs default 2500  

Additionally, it retries once with a “simplified query” if the first search returns no candidates.



## 16) Windowing, Timezones, and Timestamp Parsing (Blueprint ver.1.4)

### 16.1 Canonical timestamp representation

Across the system, timestamps are represented in one of two ways:

UTC ISO string (preferred for storage and comparisons)  
Format: YYYY-MM-DDTHH:MM:00Z  
Used heavily in:  
Event.release_ts (FMP ingestion output)  
Event.released_ts (actuals harvester writes)  
internal comparisons where string ordering is used  

Google Sheets Date object (cell type = Date/DateTime)  
Used by:  
market_scoring.gs (past-24h scorer requires Date objects)  
some user-entered timestamps in sheets  

Important: Some modules accept string timestamps and parse them; others require the cell to already be a Date object (see 16.5).

---

### 16.2 Minute normalization policy (Event ingestion + utilities)

#### 16.2.1 FMP ingestion: rounding to nearest minute

_parseReleaseTsUtcMinute_() (used by normalizeFmpRow_() and some writer utilities):

Parses input timestamps from:  
ISO strings  
numeric strings  
epoch seconds  
epoch milliseconds  

Converts to milliseconds and rounds to nearest minute:  
Math.round(ms/60000)*60000  

Outputs UTC ISO string with seconds fixed to :00Z  

This means event times may be rounded up or down by up to 30 seconds relative to the raw provider timestamp.

#### 16.2.2 Batching: clamping to minute (no rounding)

Batching uses a different rule than ingestion rounding:

applyBatchingForKeys_() clamps a UTC ISO string to :00Z by replacing the seconds:

ts.replace(/:\d{2}Z$/, ':00Z')  

This is a truncate-to-minute operation for any seconds, not a “nearest minute” rounding.

Operational consequence:

Ingestion typically outputs minute-zeroed timestamps already, but if a release_ts ever contains seconds, batching will truncate, not round.

---

### 16.3 Window model (where windowing exists)

Windowing exists in three separate places, implemented differently:

Prediction Runner windowing (prediction_runner.gs)

Default rolling window:  
start = now - CFG.WINDOW_MIN_BEFORE_MIN  
end = now + CFG.WINDOW_MAX_AFTER_MIN  

Optional override via Config sheet (`PRED_WINDOW_ENABLED`, `PRED_WINDOW_FROM_LOCAL`, `PRED_WINDOW_TO_LOCAL`, `PRED_WINDOW_TZ`), with legacy fallback to shared `WINDOW_*` keys if the dedicated prediction keys are absent.

Actuals harvester windowing (actuals_fetcher.gs)

Uses relative minutes:  
lookbackMinutes, lookaheadMinutes  

Manual fetch may attempt to use resolveWindow_('actuals_manual') if present, but still executes as a lookback/lookahead relative to “now.”

Market reaction (Config Window) (market_scoring.gs)

Requires Config sheet window keys and MR_WINDOW_ENABLED == TRUE  
Parses local window into UTC Dates and filters events by fromUtc <= ts <= toUtc.

Event ingestion (next 72h) does not use resolveWindow_(); it uses a fixed “days ahead” parameter.

---

### 16.4 Config-window parsing (local → UTC)

Config-window parsing behavior is used by:

Prediction Runner (when PRED_WINDOW_ENABLED, with fallback to WINDOW_*)  
Market reaction scorer (Config window)  

Parsing accepts:

Date cells (already a Date object)  
ISO-like strings  
strict string format: YYYY-MM-DD HH:mm  

Timezone handling:

PRED_WINDOW_TZ / MR_WINDOW_TZ are treated as the interpretation timezone for the local strings for their respective modules.  

If missing, callers default to either:  
script timezone, or  
'UTC' (market scoring config path defaults to UTC).  

The conversion yields:

fromUtc and toUtc as UTC Date objects  
fromUtcIso and toUtcIso used by some modules for comparisons/logging  

If parsing fails:

callers do not throw in all cases:  
market scoring logs parse_error and throws  
prediction runner falls back to the default rolling window  

---

### 16.5 Timestamp parsing differences by module (critical behavior)

#### 16.5.1 Predictions runner (Event.release_ts)

Accepts strings in release_ts  
Parses into Date  
Uses Date comparisons for windowing  

If release_ts is invalid:  
event is skipped as bad_ts  

#### 16.5.2 Actuals harvester (Event.release_ts)

Accepts string release_ts  
Parses into Date  
Uses Date comparisons for selection gates  

If invalid:  
row is skipped  

#### 16.5.3 Market reaction scoring — strict Date-object requirement in past24h

scoreMarketReactionPast24h_() only accepts rows where:  
timestamp cell ts instanceof Date  

If the Event timestamp is stored as a string (even a valid ISO string), it is ignored by this worker.  

scoreMarketReactionByConfigWindow_() is more flexible:  
it can parse strings and also accept Date objects.  

Operational consequence:

If you expect “past 24h” market scoring to work, the Event sheet must store release_ts / released_ts as actual Date objects (or you must use the Config-window scorer that parses strings).

---

### 16.6 Comparison semantics (string vs Date)

The codebase uses both approaches:

Some filters compare UTC ISO strings lexicographically:  
works correctly only when strings are normalized to the same format and timezone (...Z), which is the system’s intended representation.  

Other filters compare Date.getTime() numerically:  
robust to format differences, as long as parsing succeeds.  

This mixed approach is why minute-normalization and consistent timestamp format matters.

---

### 16.7 Best-practice operational rules (implied by code)

To ensure consistent behavior across modules:

Store scheduled timestamps in Event as:  
release_ts = UTC ISO string (...:00Z) from ingestion  

When writing actuals timestamps:  
allow actuals fetcher to write released_ts (it normalizes to minute ISO if available)  

For Market scoring:  
Prefer using Config-window scoring if your Event timestamps are strings.  
Use past-24h scoring only when timestamps are Date-typed cells.



## 17) Known Gaps, Broken Links, and Code-Authoritative Limitations (Blueprint ver.1.4)

This section enumerates limitations that are explicitly true in the uploaded .gs files. These are not “future ideas” or “possible enhancements”—they are current ver.1.4 realities.

### 17.1 Missing or externally-required functions (hard runtime dependencies)

#### 17.1.1 Market reaction depends on a missing candle fetcher

market_scoring.gs calls:

getFxCandlesForWindow_(pair, releaseTsUtc, preMin, postMin)

This function is not present in any uploaded .gs file.  
Therefore, Market Reaction scoring will throw at runtime unless your Apps Script project contains an additional file providing this function.

Also referenced (best-effort logging):

log_ (not defined in uploaded set)

---

### 17.2 Menu wiring that references non-existent functions (broken handlers)

#### 17.2.1 Predictions “Config Window” is now wired

onOpen() wires a menu item to:

runPredictionsWindow

This function exists in the current code and dispatches to the windowed predictions path.

#### 17.2.2 Health check expects functions that are missing

menuMaintenanceHealthCheck_() checks for these:

runPredictionsWindow  
menuPredAll_ (still missing in the current uploaded set)

Effect:

Health check may still report “NOT OK” because `menuPredAll_` remains missing, even though the Config Window prediction handler itself now exists.

---

### 17.3 Inconsistent / non-unified release status vocabulary

There are two separate “status” vocabularies across actuals modules:

Rolling actuals harvester (actuals_fetcher.gs):  
scheduled → released → revised  

Ignore-window backfill (actual_backfill.gs):  
pending / fetched / error  

These are not automatically reconciled.  
As a result, Event rows may carry “maintenance statuses” that do not align with the rolling harvester’s lifecycle semantics.

---

### 17.4 Logging is best-effort and may be dropped

While the logging shim is robust, logging call sites are inconsistent:

appendLog() requires a sheet object, not just (level, msg, ctx).

Many calls do pass getSheet(CFG.SHEET_LOG) correctly.

Some calls (notably in parts of the prediction runner) call appendLog() without a sheet, which causes those log writes to fail silently.

Effect:

The log sheet is useful, but not guaranteed complete.

---

### 17.5 Market reaction “past 24h” requires Date-typed timestamp cells

scoreMarketReactionPast24h_() only scores rows where the timestamp cell is a Date object (instanceof Date).

If Event timestamps are stored as ISO strings (common after ingestion), “past 24h” scoring will likely score zero rows, even though timestamps are valid.

Workaround (in code behavior):

Use scoreMarketReactionByConfigWindow_() which parses strings.

---

### 17.6 “Counters” that are defined but not incremented (telemetry inaccuracies)

There are places where summary counters exist but do not reflect reality due to missing increments:

market_scoring.gs:

checked_events is logged as 0 even when scoring events  
the intended “cap 300 checked” does not engage because checked is not incremented  

Effect:

Summary logs are not reliable as KPIs; only per-event logs (if any) reflect actual work.

---

### 17.7 Limited FMP “actuals” support (calendar-only mapping)

FMP actuals fallback in the rolling harvester is only attempted when:

series_id is of the form calendar:<event name>

There is no generalized FMP “series” API integration for actual values in the current code.

Effect:

In practice, the overall resolver is FMP-direct first. SeriesMap is a narrower maintained fallback layer, and within that fallback layer FRED remains the primary source.

---

### 17.8 No standalone scoring warehouse or autonomous leaderboard service

Despite system design intent, the uploaded .gs files still do not implement a separate scoring warehouse or autonomous leaderboard service:

No independent warehouse outside `Predictions`, `MR_ProviderRuns`, and the derived evaluation tabs  
No autonomous model leaderboard service  
No automatic recalibration loop based on realized outcomes  

However, the current code does implement:

Best-effort market-reaction grading written back into `Predictions`  
Provider-level audit in `MR_ProviderRuns`  
Derived reporting rebuilds in `Evaluation_Rows` and `Evaluation_Summary`  

Effect:

ver.1.4 is now a pipeline + scored prediction store + derived evaluation reporting system, but not a separate warehouse-style evaluation platform.


## 18) Operational Playbooks (Blueprint ver.1.4)

This section describes how to operate the system in practice, strictly reflecting what the uploaded code supports today.

### 18.1 First-time setup checklist (minimum required to run core loops)

#### A) Required sheets (create tabs exactly)

Create these tabs (exact names):

Event  
Predictions  
log  

Required for fallback-mapping workflow:

SeriesMap  
SeriesMap_Suggestions  

Optional but used by some flows:

Config  
SeriesMap_Proposals  

#### B) Required API keys (Script Properties)

Set these in Apps Script Script Properties:

FMP_API_KEY (required for event ingestion)  
FRED_API_KEY (required for FRED-backed fallback actuals and FRED catalog/suggestion tools)  

Set at least one LLM provider key (Script/User/Document Properties; Script is simplest):

GEMINI_API_KEY (or GOOGLE_API_KEY)  
and/or OPENAI_API_KEY  
and/or ANTHROPIC_API_KEY  

#### C) One-time verification run

Run once, manually:

Fetch & Upsert (next 72h)  
Confirms: FMP access + Event header enforcement + batching post-pass works  

Then optionally, if you want fallback mapping coverage:

Build FRED Series Catalog  
Rebuild Suggestions from FMP Catalog  

---

### 18.2 Daily “normal operations” runbook (manual, no automation)

A typical daily flow:

Events refresh  
Menu → ① Events → Fetch & Upsert (next 72h)  

SeriesMap fallback triage (only for indicators where direct FMP actuals look weak)  
Menu → ① Events → Build FRED Series Catalog  
Menu → ① Events → Rebuild Suggestions from FMP Catalog  
Menu → ① Events → AI Review Suggestion Batch (optional, repeat in batches)  
In SeriesMap_Suggestions, review suggested rows and promote only the fallback mappings you actually want to maintain  

Run predictions  
Menu → ② Predictions → Run Predictions (All Providers)  
Use “Run Predictions (Config Window)” when you intentionally want the prediction-only Config window path.  

Fetch actuals  
Menu → ③ Actuals → Fetch Actuals (Manual)  

(Optional) Market reaction  
If candle fetcher exists:  
Menu → ④ Market Reaction → Score Market Reaction (Config Window)  
(More robust if timestamps are strings.)  

(Optional) Rebuild evaluation reports  
Menu → ④ Market Reaction → Build Evaluation Sheets  
Rewrites `Evaluation_Rows` and `Evaluation_Summary` from current scored `Predictions` rows.

---

### 18.3 Automation runbook (hourly actuals)

To enable hourly actuals fetching:

Menu → ③ Actuals → Start Hourly Actuals Fetch  

What this actually installs (code-authoritative):

A time-based trigger that runs menuActualsManualFetch_() hourly.

To disable:

Menu → ③ Actuals → Stop Hourly Actuals Fetch  

Operational notes:

Trigger runs in non-UI context, so do not rely on popups.  
Verify by checking the log sheet for actuals run messages (best effort; may be incomplete).  
If SeriesMap is not maintained, the trigger can still resolve many rows through the direct FMP path; only fallback-only cases will remain unresolved due to “No SeriesMap match.”  

---

### 18.4 Handling “new indicator appears” (SeriesMap workflow playbook)

When Event ingestion introduces new indicators and direct FMP actuals look weak or inconsistent:

Build fallback inputs  
Build FRED Series Catalog  
Rebuild Suggestions from FMP Catalog  

Open SeriesMap_Suggestions  
Review rows with READY_FOR_HUMAN_CHECK first  
Run AI Review Suggestion Batch for more UNCERTAIN rows if desired  

For each row you want to maintain as fallback coverage:

Copy the suggested FRED match into:

provider (typically FRED)  
series_id (FRED series id)  

Optionally set transform (level/mom/yoy/diff) and unit_type  

Promote  

Select completed rows  
Promote Selected Suggestions → SeriesMap  

---

### 18.5 “Actuals not filling” troubleshooting

If actuals are not appearing in Event:

Check whether direct FMP resolution should have covered the row first  

Then check SeriesMap only for fallback-target indicators  

Confirm:

country matches (uppercase)  
indicator_name_pattern matches (regex or substring)  
provider is not FILTER  
series_id is non-empty  

Confirm FRED_API_KEY exists in Script Properties  

Confirm status/eligibility  

If indicator is speech/minutes/testimony-like, actuals will be skipped by keyword gate.  

Confirm release_ts parses and is within the run’s selection window.  

Confirm you are not expecting generalized FMP series-based fallback through SeriesMap  

Rolling actuals uses direct FMP calendar matching first. In the fallback map path, FMP only works when series_id is calendar:<event name>.  

---

### 18.6 “Predictions not writing” troubleshooting

Confirm at least one provider key exists  

If none, runner returns validation_error: No providers enabled  

Confirm Event rows have identity  

event_id and type must be populated (run batching post-pass)  

Confirm selection window  

Events outside [-24h, +36h] won’t be selected in default run  

Confirm strict JSON compliance  

Provider output failures will produce error rows with raw_output and error_message  

---

### 18.7 Market reaction scoring playbook (only if candle fetcher exists)

Precondition:

A function named getFxCandlesForWindow_() must exist somewhere in your project.

Preferred path (robust to string timestamps):

Use Config Window scorer:

Set WINDOW_ENABLED=TRUE  
Fill WINDOW_FROM_LOCAL, WINDOW_TO_LOCAL, WINDOW_TZ  

Run: Score Market Reaction (Config Window)  

Avoid relying on “past 24h” if timestamps are strings:

scoreMarketReactionPast24h_() requires Date-typed timestamp cells.  

---

### 18.8 Maintenance playbooks

#### A) Backfill missing actuals (ignore window)

Menu → ⑤ Maintenance → Backfill Missing Actuals  

Use when:

you have historical rows missing released_value  
you want a one-off fill attempt across all rows  

Be aware:

it uses pending/fetched/error statuses, which differ from rolling harvester lifecycle.  

#### B) Backfill market reaction (config window)

Menu → ⑤ Maintenance → Backfill Market Reaction  

This simply delegates to the config-window market scorer and depends on the candle fetcher.


## 19) Appendix: Function Index (Blueprint ver.1.4)

This appendix lists all named function ...() declarations found in the uploaded .gs files, grouped by file. (Helper functions referenced but not declared in the uploaded set are not listed here.)

### 19.1 00_logging_shim.gs

getSheet  
getHeaderNames  
ensureHeaders  
appendLog  
safeStringify  
replacer  

---

### 19.2 Code.gs

#### Menu / entrypoints

onOpen  
menuUpsertNext72h_  
menuUpsertToEvent_  
menuUpsertFmpUpcomingToEvent24h_  
menuUpsertFmpUpcomingToEvent7d_  
menuDumpLast3Months_  
menuRunActualsPast24h_  
menuRunActualsPast7d_  
menuStartActualsAutomation_  
menuStopActualsAutomation_  
menuActualsManualFetch_  
menuActualsStartHourly_  
menuActualsStopHourly_  
runPredictionsAll_  
menuPredDispatch_  
menuRunPredictionsGemini_  
menuRunPredictionsOpenAI_  
menuRunPredictionsClaude_  
menuSeriesMapBuildSuggestions_  
menuSeriesMapPromoteSelected_  
menuSeriesMapGenerateProposalsSelected_  
menuBuildSeriesMapFromLast31d_  
menuMaintenanceBackfillActuals_  
menuMaintenanceBackfillMarketReaction_  
menuMaintenanceDiagnostics_  
menuMaintenanceHealthCheck_  

#### Ingestion / event utilities

_menuRunWrapper_  
_guardCoreTabsExist_  
fetchEventsInDateRangeUtc_  
fetchEventsInLastMonths_  
fetchEventsLast3Months_  
fetchEventsInLastMonths_  
computeFixed3MonthWindowUtc_  
coerceIsoZ  
toIsoZ  
pick  
pickFirst  
_readEventAsObjects_  

#### Logging / UI

_logInfo_  
_logWarn_  
_logError_  
_toast_  
showErrorPopup_  
_maintenanceLog_  

#### Sheets helpers

_getEventSheet_ (declared more than once in file)  
_getRawSheet_  

#### SeriesMap proposal (triage) pipeline

doPost  
doGet  
_jsonOut_  
_readSelectedSuggestionRows_  
_headerMap_  
_rowToObj_  
_seriesMapKey_  
_manualProposalsFromSuggestions_  
_proposalHeaders_  
_upsertProposals_  
_generateSeriesMapProposalsCore_  
_buildGPT52SeriesMapTriagePrompt_  
_showSeriesMapTriagePackDialog_  
_escapeHtml_  
_buildSeriesMapProposalPrompt_  
_callOpenAI_GPT52_SeriesMapTriage_  
_callOpenAI_SeriesMap_  
_callGemini_SeriesMap_  
setH  

Note (code-authoritative):  
runFetchActualsWindow_() is also declared in Code.gs (and separately in actuals_fetcher.gs). If both are present in the project, the effective one is whichever is loaded last by Apps Script’s runtime.

---

### 19.3 runner_rules_patch.gs

applyBatchingForKeys_  
col  
_col_  
_hash_  
_uuidFrom_  
minuteKey  
_uuidFromString_  
seg  
_uuidv4_  
ensureBatchRowsInPredictions_  

---

### 19.4 prediction_runner.gs

#### Entrypoints

runPredictionsAll_  
runPredictionsUsingWindow_  
menuRunPredictionsGemini_  
menuRunPredictionsOpenAI_  
menuRunPredictionsClaude_  

#### Core runner

runPredictionsCore_  
_computeWindow_  
_selectEventsForWindow_  
_buildPredictionJsonPrompt_  
_strictParsePredictionJson_  
_normalizePrediction_  

#### Provider resolution + API calls

_resolveProviders_  
_callOpenAI_  
_callGemini_  
_callClaude_  

#### Parsing helpers

_stripCodeFences_  
_extractFirstJsonObject_  

#### Predictions sheet writer

_ensurePredHeaders_  
_getPredHeaderIndex_  
_buildPredictionRow_  
_buildErrorPredictionRow_  
_upsertPredictions_  
_rowObjToRow_  
_groupBatchEvents_  
_buildBatchReferenceEvent_  
_buildBatchPredictionJsonPrompt_  

#### Qualitative logic

_isQualitativeOnly_  
_inferQualFromConsensus_  
_dirFromQual_  
_inferGenreFromName_  
debugQualFor_  

#### Config + utilities

_ensureCfgDefaults_  
_applyConfigOverridesFromSheet_  
_maybeOverrideWindowFromConfig_  
_localToUtcIso_  
_tzOffsetAt_  
_normalizeProviderName_  
_numOrNull_  
_oneOf_  
_cell  
_cfgNumber_  
_cfgBoolean_  
_statusFromErr_  
_schemaErr_  
_providerErr_  
_quotaErr_  
_withRetries_  
_getKey_  
_toIsoOrNull_  

---

### 19.5 fmp_calendar.gs

getEventSheet  
ensureEventHeaders_  
_coalesce_  
_parseNumber_  
_parseReleaseTsUtcMinute_  
_pickFirst_  
_parseToUtcMinuteIso_  
normalizeFmpRow_  
_upsertEventsToEvent_  
fmpFetchUpcoming  
_yyyy_mm_dd_  
_getScriptProp_  
runFmpUpcomingToEvent_  

---

### 19.6 actuals_fetcher.gs

#### Entrypoints

runFetchActualsWindow_  
runFetchActualsHourly_  

#### Provider fetch

_fetchActualFromProviders_  
_fredFetchObservations_  
_fmpFetchActual_  

#### Transforms + selection

_computeTransform_  
_pickLatestObservationInWindow_  
_refMonthEnd_  
_shouldSkipActuals_  

#### SeriesMap + normalization

_loadSeriesMap_  
_resolveSeriesForEvent_  
_normalizeIndicatorKey_  
_normFreq_  
_normProvider_  
_normTransform_  
_normUnitAndPrecision_  
_normSeasonal_  

#### Sheet header helpers

_getHeaderNames_  
_buildHeaderIndex_  
H  

#### Date helpers

_ymd  
_ym_  

#### Logging

_log_  

---

### 19.7 actual_backfill.gs

fetchActualsIgnoreWindowOnce  
_fredFetchObservation (declared twice in file)  
_fmtDateISO  
addDays  
_autoMapIndicator  

---

### 19.8 series_map.gs

#### Core SeriesMap

loadSeriesMap  
resolveSeriesForEvent  
roundByUnit  

#### Suggestions workflow

_ensureSuggestionsSheet_  
appendSeriesMapSuggestion_  
promoteSelectedSeriesMapSuggestions_  
buildDefaultPattern_  
buildSeriesMapSuggestionsWindow_  
buildSeriesMapSuggestionsUsingWindow_  
buildSeriesMapSuggestionsLast31d_  
buildSeriesMapSuggestions3moFixed_  
buildSeriesMapSuggestionsLastYear_  
buildSeriesMapSuggestions31d_  
buildSeriesMapSuggestionsLast31d_ (naming overlap exists; treat as declared as-is)  

#### FMP calendar candidate augmentation

_fmpGetBaseAndKey_  
_fmpYmdUtc_  
_fmpFetchCalendarAround_  
_fmpSuggestCalendarCandidates_  
_augmentSuggestionWithFmp_  
_findNextCandSlot_  
_writeCand_  

#### Heuristics for suggestions

suggestFromName_  
_fillSeriesMapDefaults_  
_guessFreqFromName_  
_guessUnitAndTransform_  
_guessPrecisionDp_  

#### Reference-period utility

getRefPeriodForEvent  
_extractMonthFromName  
_extractQuarterFromName  
_inferYearFromRelease  

#### Pattern utilities

stripDateSuffix_  
escapeRegex_  
_normalizePatternText_  
_isRegexPattern_  
_compilePattern_  

#### Misc helpers

_loadSeriesMap_  
_nowIso_  
addHoursIso_  
_isoMinuteZ_  
col  
sugCol  
ensureMapHeader_  
mv  
_tok_  
_jaccard_  
_ym  

---

### 19.9 seriesmap_fred_autosuggest.gs

menuSeriesMapAutoSuggestFRED_  
runSeriesMapAutoSuggestFromFRED_  
_getCandSlotForWrite_  
_writeCandSlot_  
_fredSeriesSearch_  
_rankFredSeriesResults_  
_classifyFredCandidates_  
_buildNotes_  
_normalizeIndicatorForFREDQuery_  
_tokens_  
_tokenOverlap_  
_hdrIndex_  
_ensureHeaders_  
_indexMapFromHeaders_  
_queueWrite_  
_applyWrites_  

---

### 19.10 market_scoring.gs

_computeUsdJpyMove_  
_nearestAtOrBefore_  
scoreMarketReactionPast24h_  
_getEventSheet_  
_indexByHeaderInsensitive_  
_parseEventTsFlexible_  
scoreMarketReactionByConfigWindow_  
_readConfigMap_  
_parseLocalToUtc_  
_getEventReleaseTs_  
_coerceAnyToUtcDate_  
_coerceDateAndTimeToUtc_  
_localPartsToUtc_  
_validDate_  
debugEventTimestampSample_  



## 20) Version Notes, Superseded Sections, and Document Integrity (Blueprint ver.1.4)

### 20.1 Version label and authority statement

This document is Blueprint ver.1.4.  
Authoritative source of truth: the uploaded Apps Script .gs files.  
If any discrepancy exists between this Blueprint and the code, the code wins.

---

### 20.2 Superseded sections (explicit replacements inside ver.1.4)

The following sections were rewritten after direct code verification and must be treated as the canonical content for ver.1.4:

#### Section 9) Market Reaction Scoring → superseded by Section 9 (REWRITTEN, code-authoritative)

Reason: code uses _computeUsdJpyMove_() + requires external getFxCandlesForWindow_(); it now writes best-effort evaluation fields into Predictions and uses a configurable short reaction horizon.

#### Section 11) Menus, Triggers, and Control Plane → superseded by Section 11 (REWRITTEN, code-authoritative)

Reason: actual onOpen() wiring differs from legacy assumptions; includes Market Reaction tools and Maintenance entries.

All earlier versions of these sections should be discarded.

---

### 20.3 Known runtime blockers (must be resolved outside the Blueprint)

Some functionality is present in code but cannot run end-to-end without additional project components:

Market Reaction requires getFxCandlesForWindow_() (not included in uploaded code set).  
Without it, market scoring will throw at runtime.

Predictions health check still references `menuPredAll_`, which does not exist in the uploaded set.

These are “code-state facts” of ver.1.4 and not documentation issues.

---

### 20.4 Scope boundary of ver.1.4

Blueprint ver.1.4 documents only what is implemented now:

#### Included:

FMP calendar ingestion → Event  
Batching / identity fill  
Predictions runner (Gemini/OpenAI/Anthropic)  
Actuals fetching (direct FMP first, selective SeriesMap fallback)  
SeriesMap workflow (fallback suggestions + optional AI review + promotion)  
Market reaction scoring (USD/JPY move computation + logging scaffold)  
Maintenance backfill tools (actuals + market reaction)  
Logging shim and best-effort operational logs  

#### Explicitly not included (not implemented in uploaded code):

Closed-loop warehouse-style accuracy platform beyond `Predictions`, `MR_ProviderRuns`, and the derived evaluation sheets  
Provider leaderboards / dashboards as autonomous services  
Persistent raw candle tables written to sheets  

---

### 20.5 Final note: document consistency rule

This Blueprint is written “section-by-section,” but it is intended to be read as a single specification. Where multiple modules use different status vocabularies or timestamp parsing rules, those differences are documented as intentional behaviors of the code, not as inconsistencies to be smoothed over.
