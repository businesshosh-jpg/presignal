Rule ver.1.3 — PreSignal Economic Event AI System (Oct 2025)
(Supersedes Rule ver.1.2)

1) Purpose & Scope (rule1.3.1)
Authoritative basis. This Rule Book documents only the behaviors implemented in the uploaded Apps Script .gs files and reconciled in Blueprint ver.1.3.1. Where legacy wording in rule1.3.docx conflicts with code or Blueprint ver.1.3.1, this document follows the Blueprint and code.
System scope. PreSignal ver.1.3.1 is a Google Sheets + Apps Script system that:
Ingests upcoming macroeconomic events from the FMP economic calendar and upserts them into the Event sheet.
Assigns deterministic identity and batching (event_id, batch_id, type) via a post-pass implemented in code.
Generates AI predictions into the Predictions sheet using enabled providers (Gemini/OpenAI/Anthropic), enforcing strict JSON contracts.
Fetches released actuals using SeriesMap resolution (FRED-first; limited FMP fallback) and updates the Event sheet lifecycle fields.
Computes a USD/JPY market reaction move around event timestamps and logs the result (no persistent scoring table in current code).
Explicit non-scope (not implemented). The following are not guaranteed or persisted by ver.1.3.1 code and therefore are out of scope for this Rule Book:
A closed-loop accuracy database (prediction vs actual vs market reaction).
Provider leaderboards or persistent scoring tables.
Market reaction for FX pairs other than USD/JPY.
Operational boundaries.
This Rule Book describes current behavior, not future intent.
Some modules are best-effort (e.g., logging), and some features depend on external functions not included in the uploaded files (notably the candle fetcher for market reaction).
Code-authoritative note. This section mirrors the implemented pipeline and explicitly excludes features that are not present or not persisted in code, per Blueprint ver.1.3.1.

2) Data Model & Tabs (rule1.3.1)
2.1 Canonical entities
EconomicEvent (Event sheet) A single macroeconomic release row. This is the canonical store for event metadata, scheduling, identity/batching fields, and actuals lifecycle fields.
Prediction (Predictions sheet) A single AI output row produced by the prediction runner. Each row represents one provider run for one event_id, or a synthetic batch summary row.
LogRecord (log sheet) An append-only operational log row with structured JSON context. Logging is best-effort and non-blocking.
SeriesMap workflow tables
SeriesMap: Authoritative mapping used by actuals fetching.
SeriesMap_Suggestions: Auto-/semi-generated candidate mappings for human triage.
SeriesMap_Proposals: Optional proposal workflow table (used by menu tools).

2.2 Sheet names (authoritative defaults)
The system resolves sheets by name. Defaults are defined in code and treated as authoritative unless overridden at runtime.
Core (must exist)
Event
Predictions
log
SeriesMap workflow (expected when using actuals/tools)
SeriesMap
SeriesMap_Suggestions
SeriesMap_Proposals
Legacy compatibility (read-only fallbacks in limited modules)
RawCalendar, RawCaldendar, Events Note: Backward-compat shims may resolve these to Event; the canonical sheet remains Event.
No auto-create policy
Core sheets are not reliably auto-created. Missing required sheets cause hard errors in control-plane paths.
Code-authoritative note. Sheet creation behavior varies by module; SeriesMap utilities may create SeriesMap_Suggestions, but core runners assume tabs already exist.

2.3 Header enforcement model
Headers are addressed by name, not position. When a module enforces headers, it appends missing headers to the right and never reorders existing columns.
Event headers are enforced by FMP ingestion.
Predictions headers are enforced by the prediction runner.
log headers are best-effort via the logging shim (fills blanks; no reorder).
If ingestion is never run, other modules may operate on existing headers and can fail if required headers are missing.

2.4 Event sheet header contract (enforced on ingestion)
When FMP ingestion runs, it ensures the following headers exist (append-only):

object, country, indicator_name, genre, importance,
type, event_id, batch_id, release_ts,
source_cal, consensus_value, prev_revision,
released_value, released_ts,
source_provider, source_series_id, transform,
release_status, notes
Semantics
object must be "econ_event" for Event rows.
type, event_id, batch_id are populated by the batching post-pass (not by ingestion).
release_status is initialized to "scheduled" by ingestion.

2.5 Predictions sheet header contract (enforced before writes)
Before writing predictions, the runner ensures these headers exist (append-only):

object, run_id, prediction_id, schema_version, created_ts,
event_id, batch_id, type,
ai_name, ai_version, ai_model, model_version,
consensus_value, prev_revision, source_cal, genre, importance, fx_pair,
ai_forecast_value, qualitative_result,
expected_move_dir, expected_move_pips_min, expected_move_pips_max,
expected_holding_minutes,
rationale_short, rationale,
prompt_tokens, completion_tokens, latency_ms,
raw_output, status, error_message, qualitative_only
Upsert identity
(event_id, ai_name) uniquely identifies a prediction row and is overwritten on re-run.

2.6 log sheet header contract
The logging shim expects:

ts, level, message, context_json
Logging is append-only, best-effort, and never blocks execution.

2.7 Required field presence by module (read requirements)
Batching post-pass requires: country, indicator_name, release_ts, event_id, batch_id, type headers to exist (throws if missing).
Prediction runner requires per-row event_id and type to be non-empty; release_ts must be parseable.
Actuals fetcher requires event_id, country, indicator_name, release_ts; reads/writes lifecycle fields.
Market reaction (past 24h) requires timestamp cells to be Date objects (strings are ignored in that path).
Code-authoritative note. These requirements reflect explicit checks and parsing behavior in the uploaded .gs files; they are not inferred guarantees.

3) Identity, Batching, and Synthetic Rows (rule1.3.1)
3.1 Canonical identity fields (Event sheet)
Each Event row is identified and classified using three fields stored on the Event sheet:
event_id: deterministic ID for a single event row
batch_id: deterministic ID shared by events released at the same minute for the same country (empty string when not batched)
type: classification of the Event row:
"single" (not batched)
"member" (part of a batch)
These fields are treated as mandatory for downstream operations (notably predictions). Events missing event_id or type are skipped by the prediction runner.
Code-authoritative note. This matches the runner’s selection gate: event_id and type must be present and non-empty to be eligible.

3.2 When identity is assigned (post-pass only)
Identity assignment is performed by a deterministic post-pass:
applyBatchingForKeys_() (implemented in runner_rules_patch.gs)
This runs after events are upserted into the Event sheet and writes event_id, batch_id, and type back into the Event rows.
Not “fill-only.” applyBatchingForKeys_() does not behave as “only fill blanks.” It deterministically assigns values and writes them into the sheet for the grouped rows.
Hard requirement (throws). If the Event sheet is missing any of these headers, the function throws and stops:
country, indicator_name, release_ts, event_id, batch_id, type
Code-authoritative note. This is an explicit header requirement in the batching function; it is not optional.

3.3 Grouping key (batch rule)
Batch grouping is computed at minute precision:
Country: uppercased
Release timestamp: clamped to minute, UTC ISO (...:00Z)
Implementation detail (clamp behavior): If release_ts ends with :SSZ, seconds are replaced with :00Z (truncate-to-minute, not “round to nearest minute”).
Conceptual group key:
COUNTRY|YYYY-MM-DDTHH:MM:00Z
Batch condition
If 2+ events share the same (COUNTRY, minuteUTC) → they are treated as a batch.

3.4 Deterministic ID generation (event_id / batch_id)
IDs are generated deterministically via a hash-based UUID-like function:
batch_id
If a group has 2+ rows: batch_id = uuidFrom("batch|" + groupKey)
If a group has 1 row: batch_id = "" (empty string)
event_id
For each row, regardless of batch size: event_id = uuidFrom("event|" + COUNTRY + "|" + minuteISO + "|" + indicator_name)
Implication
Batched events share the same batch_id (within that minute+country), but each has a distinct event_id because indicator_name is in the seed.

3.5 type assignment (Event sheet)
For each (COUNTRY, minuteUTC) group:
group size == 1 → type = "single"
group size >= 2 → every row → type = "member"
No other type values are assigned in the Event sheet by batching logic.

3.6 Synthetic “batch summary” rows (Predictions sheet only)
When the prediction runner processes an Event row with:
type === "member" and
batch_id is non-empty
…it ensures a synthetic batch summary row exists in the Predictions sheet.
Synthetic batch row properties (as created by _ensureSyntheticBatchRow_()):
event_id = batch_id (note: this does not correspond to a real Event row)
type = "batch"
ai_name = "BatchSynth"
ai_model = "BatchAggregator"
qualitative_only = "true" (stored as a string)
expected_move_pips_min/max are set from CFG.PIPS_BY_IMPORTANCE based on the member event’s importance
The row is appended only if a matching row does not already exist (event_id == batch_id AND type == "batch")
Important scope rule
Synthetic “batch” rows are a Predictions-table artifact only.
The Event table uses only single and member.
Code-authoritative note. This behavior exists to make batched handling explicit in Predictions without calling an AI model for a non-event.

4) Event Ingestion & Upsert (rule1.3.1)
4.1 Source and responsibility (what ingestion does)
In ver.1.3.1, event ingestion is implemented only via the FMP economic calendar pipeline (fmp_calendar.gs). Its responsibilities are:
Fetch upcoming events from FMP (/economic_calendar)
Normalize raw payload rows into the Event schema
Upsert rows into the Event sheet using a deterministic match key
Enforce the Event header contract (append-only)
Sort the Event sheet by release_ts ascending (best-effort)
Defer event_id / batch_id / type to the batching post-pass
Code-authoritative note. No other calendar provider ingestion is implemented in the uploaded .gs files for v1.3.1.

4.2 Canonical entrypoint (menu)
The canonical user entrypoint is:
Menu → PreSignal v1.3 → ① Events → “Fetch & Upsert (next 72h)”
Handler behavior (effective path):
Calls runFmpUpcomingToEvent_(3) (3 days ahead; “next 72h” window)
Then calls applyBatchingForKeys_() to deterministically fill event_id/batch_id/type
Writes an info log and shows a toast summary (best-effort)
Known limitation (wiring / missing function) There is another handler path intended to use a configurable window (menuUpsertToEvent_() calling runFmpRangeToEvent_()), but runFmpRangeToEvent_() is not present in the uploaded code set. Therefore, only the “next 72h” path is reliably actionable as-is.

4.3 Fetch logic (FMP)
The fetch worker is fmpFetchUpcoming(daysAhead).
API key resolution
Uses CFG.FMP_API_KEY if non-empty
Else falls back to Script Property FMP_API_KEY
If neither exists → throws (ingestion stops)
Endpoint
Base: CFG.FMP_BASE (default https://financialmodelingprep.com/api/v3)
GET /economic_calendar?from=YYYY-MM-DD&to=YYYY-MM-DD&apikey=...
Date range
from = today (UTC)
to = today + daysAhead (UTC)
formatted as YYYY-MM-DD using UTC getters
Optional server-side filter
If CFG.FMP_COUNTRY is non-empty, it appends &country=... (best-effort; endpoint support may vary)
HTTP behavior
Non-200 response → throws with response code/body

4.4 Normalization (raw → Event row)
Each raw object is normalized by normalizeFmpRow_(raw).
Field mapping (first-non-empty selection)
object → "econ_event"
indicator_name ← indicator_name | title | event | name | category
country ← country | ccy | region (uppercased)
genre ← genre | category | group
importance ← importance | impact | importanceText | importance_level
Consensus / previous parsing
consensus_value ← consensus_value | consensus | estimate | forecast | expected
prev_revision ← prev_revision | previous | previousValue | prev | prior | revised | revisedPrevious
Both are parsed by _parseNumber_():
strips %, whitespace, commas
returns Number or null (written blank if null)
Timestamp parsing
release_ts ← release_ts | datetime | date | time
Parsed by _parseReleaseTsUtcMinute_():
accepts ISO strings, numeric strings, epoch seconds/milliseconds
rounds to nearest minute: Math.round(ms/60000)*60000
outputs UTC ISO with seconds forced to :00Z
invalid parse → '' (blank)
Released fields are not populated by ingestion Normalization currently sets:
released_value: ''
released_ts: ''
source_provider: ''
source_series_id: ''
transform: ''
release_status: 'scheduled'
notes: ''
Code-authoritative note. This establishes that ingestion produces “scheduled-only” rows; released/actual lifecycle is handled by the Actuals modules.

4.5 Local country filter (post-normalization)
After normalization, runFmpUpcomingToEvent_(daysAhead) applies a local filter:
If CFG.COUNTRY_FILTER is a non-empty array, only events whose normalized country is included are kept.
Default config is ['US'].
This applies even if server-side CFG.FMP_COUNTRY filtering is also used.

4.6 Sorting behavior
Sorting is applied twice:
In-memory: normalized rows are sorted by release_ts ascending (lexicographic ISO string compare).
On-sheet: _upsertEventsToEvent_() attempts to sort Event rows (2..last) by the release_ts column ascending. This is wrapped in try/catch and will not fail the run if sorting errors.

4.7 Upsert key and overwrite semantics (critical)
Upsert is implemented by _upsertEventsToEvent_(normRows).
Match key (dedupe/update key)
key = country + '|' + indicator_name + '|' + release_ts
Skip conditions
If indicator_name is blank → skipped
If release_ts is blank → skipped
Overwrite behavior (important) For both appends and updates, the function constructs a full row aligned to headers and explicitly sets:
type = ''
event_id = ''
batch_id = ''
Therefore:
Any matched-row update will blank out identity fields during upsert.
The canonical flow relies on immediately running applyBatchingForKeys_() afterward to repopulate identity deterministically.

4.8 Event header enforcement policy
getEventSheet() enforces a “no auto-create” policy:
If the Event sheet does not exist → throws (“Create it first.”)
If it exists, ensureEventHeaders_(sh) ensures required headers:
If row 1 is empty → writes the full required header row once
Otherwise → appends missing required headers to the end
Never reorders existing headers


5) Prediction Runner & Providers (rule1.3.1 — Revised)

5.1 Purpose (authoritative behavior)
The Prediction Runner generates one prediction row per (event_id × provider) and writes/upserts it into the Predictions sheet.
In ver.1.3.1 (revised), the runner operates under the following mandatory constraints:
Operates only over Event rows within a configured time window.
Requires Event identity to already exist (event_id and type must be non-empty).
Builds a deterministic feature_pack for each selected event before any provider call.
Enables providers only when their API keys are available at runtime.
Enforces strict JSON output parsing.
Writes structured error rows on failures.
Ensures a synthetic batch row exists in Predictions for batched events (see Section 3.6).
Never mutates Event rows.
Code-authoritative rule: No provider call may occur before feature_pack computation completes successfully.

5.2 UI entrypoints (menu-wired behavior)
Menu → PreSignal v1.3 → ② Predictions
Run Predictions (All Providers) → runPredictionsAll_()
Default rolling window: now − 24h → now + 36h
Providers: CFG.PROVIDERS filtered to only those with API keys present
Run Predictions (Config Window)
Menu references runPredictionsWindow, which does not exist in uploaded code. The implemented function is runPredictionsUsingWindow_() but is not wired.
Gemini (manual) → menuRunPredictionsGemini_()
Same default window
Providers: ['Gemini']
OpenAI (manual) → menuRunPredictionsOpenAI_()
Same default window
Providers: ['OpenAI']
Claude (manual) → menuRunPredictionsClaude_()
Same default window
Providers: ['Anthropic']
Code-authoritative note: Only “All Providers” and provider-specific manual runs are reliably callable via menu in current code state.

5.3 Prediction window (effective behavior)
Default rolling window:
window_start = now - windowMinBeforeMin
window_end   = now + windowMaxAfterMin
Typical defaults:
windowMinBeforeMin = 24 × 60
windowMaxAfterMin = 36 × 60
Config sheet override (runner-only)
If a sheet named Config exists and:
WINDOW_ENABLED is truthy
WINDOW_FROM_LOCAL and WINDOW_TO_LOCAL are valid
WINDOW_TZ is set (or defaults to script timezone)
Then the runner replaces the rolling window with the Config-derived UTC window.
If parsing fails: The runner falls back to the rolling window without failing.

5.4 Event selection rules (Event sheet → runner payload)
The runner scans Event rows (row 2 onward) and selects rows satisfying:
object blank OR equals econ_event (case-insensitive)
event_id exists and non-empty
type exists and non-empty
release_ts convertible to valid ISO
release_ts ∈ [window_start, window_end] inclusive
For selected events, it builds a base payload:
event_id
batch_id
type
country
indicator_name
genre
importance
release_ts
source_cal
consensus_value
prev_revision
fx_pair
If fx_pair is missing: Defaults to CFG.DEFAULT_FX (USDJPY).
Selection statistics are logged (best-effort):
scanned
skipped_bad_ts
skipped_out_of_window
skipped_missing_id_type
selected

5.5 Feature Pack (Deterministic Context Layer — Mandatory)
Before calling any provider, the runner MUST compute a structured feature_pack.
This is a hard architectural rule in ver.1.3.1.

5.5.1 Deterministic computation rule (hard rule)
feature_pack MUST be computed using deterministic system logic only.
LLMs MUST NOT compute trends, statistics, or derived metrics.
feature_pack MUST NOT be modified by any provider.
No provider call may occur before feature_pack is built.
Violation of this rule constitutes architectural breach.

5.5.2 Allowed feature types
feature_pack may include:
last_n_values (n ≤ 6)
trend_3m / trend_6m
surprise_std_12m
avg_surprise_12m
regime markers (≤ 5)
related indicator deltas (≤ 5)
Forbidden:
Raw long historical tables
Unbounded history
Look-ahead leakage
LLM-derived features

5.5.3 As-of integrity rule
If FEATURE_PACK_ASOF_LOCK is enabled:
No feature may use data later than release_ts.
Backtesting must respect timestamp integrity.
No forward contamination permitted.

5.5.4 Caching rule
feature_pack is computed once per event_id.
Multiple providers reuse the same feature_pack.
Recompute only when explicitly forced.

5.5.5 Versioning rule
feature_pack_version must be logged.
Any structural change requires version increment.
Historical backtests must log version used.

5.6 Qualitative-only classification
Before provider calls, each event is classified:
numeric
qualitative-only
If qualitative-only: ai_forecast_value MUST be null.
Classification rules:
Explicit override (highest priority)
If event contains qualitative_only, respect it.
Genre match (case-insensitive)
speech, press_conference, statement, minutes, hearing, testimony
Indicator keyword match (word boundary)
Auctions (conditional)
Only qualitative if both consensus and previous missing.
GDPNow / nowcast exception
Explicitly treated as numeric.

5.7 Provider enablement and API keys
Supported providers:
Gemini
OpenAI
Anthropic (Claude normalized to Anthropic)
Enablement rule: Provider is enabled only if API key found at runtime. Providers without keys are silently excluded.
Key lookup order:
Script Properties
User Properties
Document Properties
Key names:
Gemini: GEMINI_API_KEY, GOOGLE_API_KEY, GOOGLE_AI_STUDIO_API_KEY
OpenAI: OPENAI_API_KEY
Anthropic: ANTHROPIC_API_KEY
If no providers enabled: Runner returns validation_error: "No providers enabled".

5.8 Provider call mechanics and retries
All provider calls wrapped in _withRetries_():
Attempts: 4
Exponential backoff with jitter
Base sleep: 800ms
Retry logs best-effort
OpenAI:
Endpoint: /v1/chat/completions
response_format: { type: "json_object" }
Model: CFG.OPENAI_MODEL (default gpt-4o-mini)
Gemini:
Endpoint: v1beta/models/{model}:generateContent
response_mime_type = application/json
Defensive JSON extraction
Anthropic:
Endpoint: /v1/messages
Header: anthropic-version: 2023-06-01
Model: CFG.CLAUDE_MODEL

5.9 Strict JSON contract
Providers must return strict JSON only (no code fences).
Top-level object must include:
object == "ai_prediction"
event_id
type
Parse accommodations:
If quoted JSON → inner JSON parsed.
If top-level array → first usable object selected (prefer object == ai_prediction).
Additional rule (new in ver.1.3.1):
rationale_short must align with feature_pack signals.
Model must not contradict feature_pack statistics.
Model must not invent drivers outside feature_pack.
Failure to meet strict requirements → treated as error → error row written.

5.10 Normalization and defaults (post-parse)
After parsing, _normalizePrediction_():
Forces event_id and type to match Event row.
Provider cannot override identity.
If qualitative-only:
ai_forecast_value forced to null.
Defaults:
qualitative_result:
parsed if valid
else inferred from consensus vs previous
else inline
expected_move_dir:
parsed if valid
else derived from qualitative_result
else flat
Pips band defaults by importance:
low → [3,10]
medium → [8,25]
high → [15,45]
critical → [25,80]
Holding minutes:
Defaults to 60 if missing/invalid.
If direction still empty:
flat if expected_move_pips_max ≤ 1
else up

5.11 Writing to Predictions (upsert semantics)
Each prediction row includes:
run_id (derived from run start timestamp)
prediction_id (deterministic uuid(event_id + "|" + ai_name))
status
Upsert identity: (event_id, ai_name)
If match exists: Overwritten.
Else: Appended.
Telemetry note: Runner summary includes “duplicates” counter, but upsert does not emit duplicate in current code.

5.12 Synthetic batch rows (Predictions-only)
For Event rows where:
type == "member"
batch_id non-empty
Runner ensures synthetic batch row exists:
event_id = batch_id
type = "batch"
ai_name = "BatchSynth"
ai_model = "BatchAggregator"
qualitative_only = "true"
pips band derived from importance
Created only if not already present.
Important scope rule: Synthetic batch rows exist only in Predictions. Event sheet uses only single and member.

6) Actuals Fetching & Status Lifecycle (rule1.3.1)
6.1 Purpose (what actuals fetching does)
The Actuals Fetcher scans Event rows in a rolling time window, resolves a SeriesMap mapping for each eligible event, fetches the latest available observation (FRED-first; limited FMP fallback), optionally applies a transform, and writes results back into the Event sheet:
released_value
released_ts
source_provider
source_series_id
transform
release_status
This module is implemented in actuals_fetcher.gs and is designed to be idempotent at the sheet level: repeated runs over the same range should not corrupt state, and will update rows only when an actual is found or a revision is detected.
Code-authoritative note. This section documents the rolling-window harvester only. The ignore-window backfill (maintenance) has different status vocabulary and rules (covered later).

6.2 Entrypoints (manual and automation)
Automation (installable trigger via menu)
Menu → ③ Actuals → Start Hourly Actuals Fetch → menuActualsStartHourly_()
Menu → ③ Actuals → Stop Hourly Actuals Fetch → menuActualsStopHourly_()
Important code-authoritative behavior (trigger target): The installed hourly trigger runs menuActualsManualFetch_() (not runFetchActualsHourly_()), and is de-duplicated by deleting prior triggers with the same handler.
Manual runs
Menu → ③ Actuals → Fetch Actuals (Manual) → menuActualsManualFetch_()
Default fallback behavior: look back ~24h, no lookahead, cap ~2000
If resolveWindow_('actuals_manual') exists and returns an enabled window, it converts that window to a (minutes back / minutes forward) relative window and calls the window runner.
Additional explicit tools:
Actuals (past 24h) → menuRunActualsPast24h_() → runFetchActualsWindow_(24*60, 0, 1000)
Actuals (past 7d) → menuRunActualsPast7d_() → runFetchActualsWindow_(7*24*60, 0, 2000)

6.3 Required sheets and “no auto-create” policy
The rolling actuals runner requires both sheets to exist:
Event
log
If either is missing, it throws:
Missing required sheet: Event or log
The module does not auto-create missing core tabs.

6.4 Candidate selection (Event rows)
runFetchActualsWindow_(lookbackMinutes, lookaheadMinutes, rowCap):
Loads all Event rows (row 2..last) into memory.
Computes a time window:
lo = now - lookbackMinutes
hi = now + lookaheadMinutes
Per row it reads:
indicator_name
release_status (preferred), else status (fallback)
release_ts parsed as Date (invalid dates are skipped)
Gate A — skip qualitative events upfront If _shouldSkipActuals_(indicator_name) returns true, the row is skipped and an info log is written:
Actuals: skipped qualitative (includes event_id, indicator_name, country)
This is keyword/pattern based (e.g., speeches/minutes/testimony-like) and is independent of SeriesMap.
Gate B — time window + status rules A row becomes a candidate when:
If status is scheduled:
release_ts ∈ [lo, hi], OR
release_ts ∈ [lo, now] (“scheduled-but-past” catch-up)
If status is released or revised:
release_ts >= lo (revision catch-up)
Row cap
If rowCap > 0, candidates are truncated to the first rowCap rows in scan order.

6.5 SeriesMap resolution behavior (and suggestions)
For each candidate, the runner requires non-empty:
event_id
indicator_name
release_ts
It resolves mapping using whichever resolver exists:
Preferred:
resolveSeriesForEvent({country, indicator_name}, seriesMap)
Backward-compat:
_resolveSeriesForEvent_(seriesMap, indicator_name, country)
No mapping found
Logs warn: Actuals: No SeriesMap match
Best-effort: calls appendSeriesMapSuggestion_(country, indicator_name) once per unique (country|indicator_name) per run
Mapping-based filters If the resolved map indicates filtering, the event is skipped:
if map.provider === 'FILTER', OR
if map.notes matches /synthetic batch event/i
Log: Actuals: skipped by SeriesMap filter
Code-authoritative note. Rolling actuals can create suggestions during a run; this is an explicit behavior.

6.6 Reference date heuristic (month-end)
Before fetching, the module computes a reference date used for FRED observation windows:
If _refMonthEnd_(release_ts) exists → uses it
Else → uses new Date(release_ts)
This anchors the observation search window (especially for monthly series).

6.7 Provider priority (FRED-first; limited FMP fallback)
Actual fetching is performed by _fetchActualFromProviders_(args).
Provider order construction
Starts with the SeriesMap provider (uppercased)
Appends ACTUALS_CFG.SOURCE_PRIORITY without duplicates Default priority: ['FRED','FMP']
FRED adapter (primary)
Requires Script Property FRED_API_KEY (if missing, FRED returns null/skip in this path)
Fetches observations via _fredFetchObservations_(seriesId, refDate)
Uses ~18-month window ending at end-of-reference-month
Picks latest observation inside the window
Builds observations[] suitable for transforms
Transform
If args.transform exists and _computeTransform_() exists, computes transformed value from observations[] (or fallback).
Success return shape includes:
hasActual: true
value, ts, provider: 'FRED', series_id, transform
FMP adapter (limited calendar-only)
FMP actuals are attempted only when:
series_id matches: calendar:<Event Name>
Behavior:
Calls FMP /economic_calendar for ±1 day around refDate
Matches row where event equals <Event Name> (case-insensitive exact match) and actual is non-empty
If series_id is not calendar: form → FMP returns {hasActual:false}.
Code-authoritative note. Rolling actuals is effectively FRED-first; FMP is a narrow fallback.

6.8 Update semantics (what is written back to Event)
If no actual is found:
the row is not changed
an info log is written noting fetch skipped/reason/provider attempted
If an actual is found, the runner stages and writes:
released_value
Uses roundByUnit(res.value, map.unit_type, (map.transform||'level').toUpperCase()) if roundByUnit exists
Else writes numeric value as-is
released_ts
Uses _parseReleaseTsUtcMinute_(res.ts) if available; otherwise preserves existing released_ts
source_provider → res.provider || map.provider
source_series_id → res.series_id || map.series_id
transform → res.transform || map.transform
release_status → updated per lifecycle rules (next section)
Writes are applied in-memory, then committed back to the Event range in one setValues() call for rows 2..last.

6.9 Status lifecycle and revision detection (rolling harvester)
The rolling harvester uses release_status (lowercased) as the canonical status field.
Transition rules
If current status is scheduled:
first successful actual fetch → status becomes released
If current status is released or revised:
compare stored released_value vs newly fetched value
if different (comparison normalizes with toFixed(10)) → status becomes revised
No downgrade
Once set to revised, the code does not downgrade back to released automatically.
Code-authoritative note. This lifecycle is distinct from the maintenance backfill’s pending/fetched/error vocabulary, which is not reconciled automatically.

7) SeriesMap: Structure, Resolution, and Suggestion Workflow (rule1.3.1)
7.1 Purpose and responsibility
SeriesMap is the authoritative mapping layer for actuals. Actuals fetching does not infer series IDs from event text at runtime. It uses the SeriesMap sheet to resolve, per event, which upstream data series should be queried and how the fetched value should be interpreted/transformed.
Human responsibility (required). Maintaining accurate mappings in SeriesMap is a human triage responsibility. The system can generate suggestions and candidates, but it does not guarantee correctness without human promotion into SeriesMap.
Code-authoritative note. Actuals fetching will log “No SeriesMap match” and skip the event until a mapping exists.

7.2 SeriesMap sheet schema (required columns)
The resolver loads SeriesMap rows using the following columns (matched by header name; column order is not required, but headers must exist for reliable use):
country
indicator_name_pattern
provider
series_id
freq
unit_type
transform
notes
Required for resolution
country
indicator_name_pattern
provider
series_id
If any of these are missing or blank in a candidate row, it will not be usable for actuals.

7.3 Pattern semantics: indicator_name_pattern
indicator_name_pattern is a match pattern applied to a normalized version of the event’s indicator_name.
Event name normalization
The resolver strips a trailing date suffix from the event name (stripDateSuffix_()), then lowercases it.
Two pattern modes
Regex pattern A string of the form /.../flags is treated as a RegExp.
If flags omit i, the resolver adds i (case-insensitive) automatically.
Matching uses re.test(normalizedName).
Text pattern (default) Any non-regex string is treated as plain text.
Matching uses substring containment: normalizedName.indexOf(patternLower) >= 0.
Code-authoritative note. Regex is recognized purely by string form (leading / + trailing /flags). There is no separate “regex column.”

7.4 Resolution algorithm (best-match rule)
resolveSeriesForEvent(ev, seriesMap) chooses one best row:
Eligibility filters
row.country must exactly equal ev.country (uppercased).
Rows where provider == "FILTER" are ignored by the resolver.
Pattern must compile successfully.
Scoring (deterministic)
Regex match score: 2000 + pattern.length
Text match score: 1000 + pattern.length
Winner selection
Highest score wins (so regex beats text, and longer patterns win within the same kind).
If the winning row lacks provider or series_id, the resolver returns null.
Implication
If multiple patterns match, you should make the more specific one longer and/or regex-based to ensure it wins.

7.5 Provider and series_id meaning (actuals-facing)
provider identifies the upstream data adapter used by the actuals module. In ver.1.3.1 rolling actuals:
FRED is the primary supported provider.
FMP is supported only in a narrow “calendar lookup” form (see below).
FILTER is used to explicitly prevent actuals fetching for matched events (skip-by-map).
series_id is provider-specific:
For FRED: a FRED series ID string.
For FMP: only calendar:<Event Name> is actionable in current rolling actuals code.
FMP calendar-only limitation If provider == "FMP" but series_id does not start with calendar:, the rolling actuals fetcher will not be able to fetch an actual from FMP and will behave as “no actual found.”
Code-authoritative note. This limitation is implemented in the FMP adapter; it is not a documentation policy choice.

7.6 Transform and rounding (display semantics)
transform controls how an observation is interpreted when actuals are written back to Event:
If transform is blank, the system defaults to level in suggestion workflows.
If roundByUnit(value, unit_type, transform) exists, it is applied before writing released_value.
unit_type affects rounding precision heuristics (e.g., percent/index/count).
Important boundary
Transform computation depends on _computeTransform_() being present (from shared code). If that function is absent in the runtime, transforms may not be applied even if specified.

7.7 SeriesMap_Suggestions sheet (auto-created; triage workflow)
The system uses SeriesMap_Suggestions as a human triage queue for unmapped events.
Auto-create behavior If SeriesMap_Suggestions does not exist, the system creates it.
Header contract (created or enforced append-only) Base columns (12):
country
indicator_name_pattern
provider
series_id
freq
unit_type
transform
seasonal_adjustment
precision_dp
lag_rule
notes
created_ts
Candidate slots (15):
cand_1_provider, cand_1_series_id, cand_1_title, cand_1_score, cand_1_freq
cand_2_provider, cand_2_series_id, cand_2_title, cand_2_score, cand_2_freq
cand_3_provider, cand_3_series_id, cand_3_title, cand_3_score, cand_3_freq
Missing headers are appended to the right; existing columns are never reordered.

7.8 Suggestion generation and de-duplication
appendSeriesMapSuggestion_(country, indicatorName, releaseTs) appends a suggestion row when:
country and indicatorName are non-empty, and
a row with the same (country, indicator_name_pattern) does not already exist in SeriesMap_Suggestions.
Default pattern:
indicator_name_pattern = stripDateSuffix_(indicatorName)
Defaults applied to the suggestion row:
If freq is blank, it may default to IRREGULAR depending on policy.
unit_type defaults to raw
transform defaults to level
created_ts is set to “now ISO”
REVIEW tagging If policy requireNumericProvider is enabled and (provider, series_id) are missing, notes is appended with:
REVIEW: missing provider/series_id

7.9 Promotion into SeriesMap (manual selection workflow)
promoteSelectedSeriesMapSuggestions_() promotes the user’s selected rows from SeriesMap_Suggestions into SeriesMap.
Hard requirements
Must be run with an active selection on SeriesMap_Suggestions.
Selection must include at least one non-header row.
Suggestions sheet must contain: country, indicator_name_pattern, provider, series_id.
Promotion rules
Rows missing any required field are skipped.
Rows where provider == "FILTER" are skipped.
The function de-dupes against existing SeriesMap entries by key: country|pattern|provider|series_id|transform(lowercased)
SeriesMap required headers are ensured (appended if missing; never reordered).
Only the mapped fields are written into SeriesMap (country, pattern, provider, series_id, and optional freq/unit_type/transform/notes).
Code-authoritative note. Promotion is a copy operation; it does not delete suggestions. Keeping suggestions for audit/triage is expected behavior.

7.10 FRED auto-suggest (candidate population only)
The FRED autosuggest module (seriesmap_fred_autosuggest.gs) is designed to populate the cand_1..cand_3 slots on SeriesMap_Suggestions rows. It performs:
A FRED series search for each suggestion row
Ranking/classification of results
Writing top candidates into candidate slot columns
Important limitation This module does not automatically change provider/series_id in the base columns unless explicitly coded in its ranking/classification rules; candidates are primarily advisory.

8) Windowing, Timestamps, and Timezone Semantics (rule1.3.1)
8.1 Canonical timestamp field (release_ts)
The canonical schedule timestamp for an event is release_ts on the Event sheet.
Storage format (canonical expectation)
UTC ISO string with seconds forced to :00Z Example: 2026-01-31T13:30:00Z
Ingestion parsing behavior
FMP ingestion normalizes timestamps using _parseReleaseTsUtcMinute_():
Accepts ISO strings, numeric strings, epoch seconds, epoch milliseconds
Rounds to nearest minute (Math.round(ms/60000)*60000)
Emits UTC ISO with seconds forced to :00Z
Invalid parse → blank release_ts and the event row is skipped during upsert
Important distinction (round vs truncate)
Ingestion uses round-to-nearest-minute
Batching uses truncate-to-minute only when clamping an already-ISO timestamp that ends with :SSZ (sets SS → 00)
Code-authoritative note. These behaviors are implemented in separate modules and are intentionally documented as-is (they are not harmonized).

8.2 Time window comparisons (runner and actuals)
All runtime window comparisons are performed in UTC milliseconds after parsing timestamps.
Prediction window (default)
Default rolling window (menu runs):
now - 24h to now + 36h
Eligibility requires release_ts parseable and inside the window inclusive.
Actuals window (default)
Past 24h and past 7d menu tools use rolling lookback windows ending at “now”.
Eligibility depends on both time window and release_status rules (see Section 6.4–6.9).
Inclusive boundaries
Window membership checks are inclusive at both ends (>= lo and <= hi) in the prediction runner selection.

8.3 Local-time configuration window (Config sheet override)
The prediction runner can replace its default rolling window with a Config sheet window when enabled.
Config parsing behavior
If Config exists and windowing is enabled, it reads:
WINDOW_FROM_LOCAL
WINDOW_TO_LOCAL
WINDOW_TZ (IANA timezone string)
Converts the local datetime range into UTC milliseconds.
If parsing fails or required fields are missing → silently falls back to the rolling window.
Scope
This override is implemented for the prediction runner path only (it is not a global system-level timestamp override).
Code-authoritative note. The presence of a Config sheet does not change ingestion, batching, or actuals behavior unless those modules explicitly read Config (they do not in v1.3.1 uploads).

8.4 “Date object vs string” handling (Sheets nuance)
Some modules treat timestamp cells differently depending on whether the cell is stored as a Date object or as a string.
Market reaction (past 24h tool)
In market_scoring.gs, runMarketReactionPast24h_() filters rows using:
release_ts must be a Date object (instanceof Date)
If release_ts is stored as a string (even a valid ISO string), that event is ignored by this specific function.
Other modules
Ingestion and prediction selection parse strings into dates and do not require Date-typed cells.
Operational implication
If you intend to use the “past 24h market reaction” tool, ensure the release_ts column is being stored as a Date by Sheets (not just text).
Code-authoritative note. This is a concrete behavioral limitation of the current market reaction tool path.

8.5 Timestamp normalization for IDs and grouping
Both identity and batching depend on minute-level UTC alignment:
Batching group key uses release_ts clamped/truncated to ...:00Z.
event_id seeds include (country, minuteISO, indicator_name).
Consequence
A change of even one minute in release_ts will generate a different event_id/batch_id on the next batching pass.

9) Market Reaction Scoring (rule1.3.1)
9.1 Purpose and scope (what is and is not implemented)
The Market Reaction module measures post-event USD/JPY price movement around an event’s release time and records the result only via logs. There is no persistent scoring table in ver.1.3.1, and no automatic feedback loop into Predictions or Event rows.
In scope
Fetching short-horizon FX candles around release_ts
Computing direction and magnitude (pips)
Emitting a structured log entry per evaluated event
Out of scope (not implemented)
Persistent accuracy metrics (MAE, hit rate tables)
Provider/model comparison dashboards
Automatic recalibration of bands or models
Code-authoritative note. Any scoring metrics mentioned in legacy rule1.3 are informational only unless explicitly written to a sheet in code. In v1.3.1, they are not.

9.2 Entrypoints (manual tools only)
Implemented menu entrypoints in market_scoring.gs:
④ Market Reaction → Run (past 24h) → runMarketReactionPast24h_()
④ Market Reaction → Run (manual window) → runMarketReactionManual_()
There is no installable trigger for market reaction in the uploaded code.

9.3 Event eligibility rules (strict)
An Event row is eligible for market reaction evaluation only if all conditions hold:
release_ts cell is a Date object (not a string).
release_ts is within the evaluated window (past 24h or manual window).
country == "US" (hard-coded in current implementation).
fx_pair resolves to USDJPY (explicit or default).
type is "single" or "member" (synthetic batch rows are not evaluated).
Rows failing any condition are silently skipped (no error thrown).
Code-authoritative note. The Date-object requirement is a concrete gate in runMarketReactionPast24h_() and is not relaxed.

9.4 Candle data sources and priority
The module attempts to fetch FX candles in this order:
Alpha Vantage (primary)
Twelve Data (fallback)
If both fail or return insufficient data → the event is logged with a no_candles outcome.
External dependency limitation
API keys must be present in Script Properties.
Provider rate limits and outages are not retried beyond basic error handling.
Candle availability is not guaranteed around illiquid times.

9.5 Time anchors and windowing
For each eligible event:
t₀ (anchor) = release_ts
Candles are fetched for a fixed short horizon around t₀ (implementation-defined in code; not user-configurable via UI in v1.3.1).
The module derives:
An initial move shortly after t₀
A sustained move further out in the window
Exact candle counts and offsets are code-defined constants and should be treated as implementation details.

9.6 Price normalization and pips calculation
Price selection
If bid/ask are available → mid = (bid + ask) / 2
Else → uses close
Pips conversion
For USD/JPY, pip value is computed using the standard JPY convention (0.01).
Direction logic
Direction is determined by the sign of (price_after − price_at_t₀).
If both initial and sustained absolute moves are < 1 pip → direction is treated as flat.

9.7 Comparison to prediction (best-effort, non-persistent)
If a matching Prediction row exists for the same event_id:
The module compares:
expected_move_dir vs observed direction
Observed pips vs [expected_move_pips_min, expected_move_pips_max]
These comparisons are used only to enrich the log output. They do not update Prediction or Event rows.
If no Prediction row exists, market reaction is still computed and logged.

9.8 Logging output (only durable artifact)
For each evaluated event, the module writes a log entry including (best-effort):
event_id
release_ts
fx_pair
observed direction (up|down|flat)
observed pips (initial and sustained)
prediction comparison flags (when applicable)
status:
ok
no_candles
provider_error
Logs are appended via appendLog() and are the only persistent record of market reaction results in v1.3.1.
Code-authoritative note. Any downstream analytics must parse logs; there is no scoring table to query.


10) Logging, Status Codes, and Error Semantics (rule1.3.1)
10.1 Logging is best-effort (non-blocking)
All modules use a lightweight logging shim (00_logging_shim.gs) that attempts to append rows to the log sheet. Logging failures must not stop the main operation unless the caller explicitly throws for unrelated reasons.
Implications
A successful run may have missing log rows if the log sheet is unavailable or a write fails.
The system makes no guarantee of “exactly-once” logging.
Code-authoritative note. The shim is designed to reduce cascading failures (e.g., failing an ingestion run because logging failed).

10.2 Log sheet contract
The canonical log sheet is named: log
Expected headers (append-only; never reordered):
ts
level
message
context_json
If headers are missing, the logger may attempt to create/repair them, but this is not a hard guarantee in every call path.

10.3 Log levels (normalized)
Log levels used by the shim are normalized to uppercase strings:
INFO
WARN
ERROR
Call sites may pass lower/mixed case; normalization is applied in the shim.

10.4 Context payload rules (context_json)
context_json must be a JSON string representation of an object. When possible, log call sites include keys such as:
run_id
module
event_id
batch_id
type
country
indicator_name
release_ts
provider
status
error
Size/shape limitations
Context is not schema-enforced and may vary by module.
Some modules include raw_output or truncated error details; the system does not guarantee full retention of large payloads.

10.5 Prediction runner status semantics (Predictions sheet)
Each prediction write includes a status field:
ok Parsed JSON validated and normalized successfully.
error Any provider call failure, parse failure, or validation failure. In error rows:
raw_output contains the provider response body when available
error_message contains a short reason string
qualitative_only still reflects event classification when it could be determined
Hard validity gates A prediction row is treated as valid only if the parsed object includes:
event_id
type
If either is missing from provider output, the runner writes an error row for that provider/event.
Code-authoritative note. This strictness exists to prevent silent mismatches between AI outputs and event rows.

10.6 Event lifecycle status semantics (Event sheet)
The Event sheet uses release_status (preferred) as the canonical lifecycle field during rolling operation:
scheduled Default on ingestion; no released actual yet in Event.
released Set by the rolling actuals fetcher when an actual is found for a previously scheduled event.
revised Set when a subsequent actuals fetch returns a different value than stored released_value.
No guarantee of completeness
The system may miss a release if SeriesMap is missing or APIs fail.
“Scheduled” can remain indefinitely without manual intervention.

10.7 Maintenance/backfill status vocabulary (non-reconciled)
The maintenance backfill module (actual_backfill.gs) uses its own status vocabulary (e.g., pending, fetched, error) for its internal workflow and does not automatically reconcile those values into release_status.
Operational rule
Treat backfill status as tool-specific state, not the canonical lifecycle for the main pipeline.
Code-authoritative note. This prevents conflating two distinct workflows that share columns but do not share semantics.

10.8 Failure modes (what stops the run)
Hard-stop errors (throw)
Missing required core sheets for a module (e.g., Event, log)
Missing required API keys in code paths that explicitly require them (e.g., FMP ingestion without an API key)
Missing required headers in batching (explicit throw)
Soft errors (logged, continue)
Provider call failures with retries exhausted
JSON parse/validation failures (prediction runner writes error rows and continues)
Sorting failures after upsert
Market reaction candle provider failures (logs outcome; continues)


11) Maintenance Tools: Backfill, Repairs, and Utilities (rule1.3.1)
11.1 One-off backfill: “ignore window” actuals fetch
The maintenance backfill tool is implemented in actual_backfill.gs:
fetchActualsIgnoreWindowOnce()
This is a one-time, full-sheet sweep intended to populate missing actuals without relying on rolling time windows.
Core behavior
Scans all Event rows (row 2..last) with no time-window restriction.
Uses SeriesMap resolution first; if no match, applies a limited _autoMapIndicator() fallback (see 11.4).
Writes results back to the Event sheet row-by-row via helper writers.
Hard prerequisites
Event sheet must exist.
log sheet must exist (getSheet(CFG.SHEET_LOG) is called and used).
The Event sheet must contain headers used by the tool (event_id, indicator_name, country, release_ts, release_status, released_value, type, notes) or the run may error or skip rows.
Code-authoritative note. Unlike the rolling actuals harvester, this tool does not attempt to create missing sheets and is intended as an operator-run maintenance action.

11.2 Backfill eligibility gates (row-level)
A row is eligible for backfill processing only if all of the following hold:
event_id, indicator_name, country, and release_ts are non-empty
released_value is empty (strict: '' or null are treated as empty; any other value means “already filled”)
release_status is not "error"
release_ts can be parsed into a valid Date (_safeDate(release_ts) must succeed)
Rows failing any gate are counted as skipped and are not modified.

11.3 Backfill “provider/type” skip rules
After SeriesMap resolution (or auto-map fallback), the tool explicitly skips rows when:
provider is MANUAL or FILTER, OR
Event type is "batch" (synthetic batch rows)
When skipped for these reasons, it writes:
release_status = "pending"
notes = "Manual/Filter/Batch: skipping"
…and logs an info message.
Important semantic warning
This "pending" value is maintenance-tool state, not the rolling lifecycle (scheduled/released/revised). It is not reconciled automatically.
Code-authoritative note. This behavior is implemented directly in fetchActualsIgnoreWindowOnce() and intentionally diverges from rolling lifecycle semantics.

11.4 Backfill provider routing (implemented providers only)
Backfill supports only:
FRED
FMP_CAL
Anything else is treated as not implemented:
writes release_status = "error"
notes contain Provider <X> not implemented
logs a warning
FRED route (maintenance-only implementation)
Fetches observations from FRED within a ±15 day window around the reference date.
Uses FRED units parameter only for a limited transform mapping:
MOM_PCT → units=pch
otherwise → units=lin
Chooses the latest valid observation; breaks early if it finds an observation on/after the ref date.
On success, it writes:
released_value (rounded via roundByUnit)
released_ts = now().toISOString()
source_provider = m.provider (typically FRED)
source_series_id = m.series_id
transform = m.transform
release_status = "fetched"
FMP_CAL route (calendar-key lookup)
Fetches FMP economic calendar for a ±3 day window around the event date.
Filters calendar results to country === 'US' (hard-coded).
Selects the matching event using _fmpPickMatchForEvent(...) against m.series_id (semantic key like CRUDE_STOCKS).
If no match or actual is not yet available:
writes release_status = "pending" with a reason in notes
On success, it writes:
released_value = match.actual
released_ts = match.date (or now)
source_provider = "FMP_CAL"
source_series_id = m.series_id
transform = m.transform || "LEVEL"
release_status = "fetched"
Code-authoritative note. This backfill path is not the same as rolling actuals FMP behavior (which is “calendar:<Event Name>” only). Backfill uses a distinct provider label FMP_CAL and semantic keys.

11.5 Backfill sanity checks (limited)
The backfill tool applies a narrow sanity check only for:
transform === "YOY_PCT"
If the fetched value is outside [-10, 50]:
writes release_status = "error"
notes Value out of range: <value>
logs an error
No other systematic range validation is implemented.

11.6 Optional copying actuals into Predictions (feature-flagged)
If ACTUALS_CFG.COPY_ACTUALS_TO_PREDICTIONS is truthy, then after a successful backfill fetch the tool calls:
_copyActualsToPredictions(event_id, value)
This is an optional side-effect and depends on:
the flag being enabled, and
_copyActualsToPredictions existing in the runtime environment.
This behavior is not guaranteed in deployments where that helper is missing.

11.7 Auto-mapping fallback (limited, maintenance-only)
If resolveSeriesForEvent(...) returns no match, backfill attempts _autoMapIndicator(ev).
This function contains a hard-coded set of name-pattern fallbacks, including:
A small FRED fallback (e.g., PCE Price Index (MoM) → PCEPI, MOM_PCT)
Several FMP_CAL semantic-key fallbacks (e.g., Chicago PMI, CB Consumer Confidence, API crude stocks, Michigan inflation expectations, Baker Hughes rigs, selected CFTC net positions, Michigan sentiment/expectations)
If _autoMapIndicator returns null, the row is not updated and the tool logs:
Actuals(ignore window): No SeriesMap match
Code-authoritative note. These fallbacks are intentionally narrow and do not replace SeriesMap triage as the canonical method.

11.8 Implementation caveat: duplicate helper definition
actual_backfill.gs currently contains two definitions of _fredFetchObservation(...). In Apps Script, the later definition overrides the earlier one at runtime.
Operationally, both definitions implement the same endpoint and selection behavior with minor differences in structure; the effective behavior is the second definition.
Code-authoritative note. This is documented as an implementation fact; it is not treated as a contract guarantee.


12) Operational Run Order & Minimal Operator Checklist (rule1.3.1)
12.1 Canonical run order (implemented dependencies)
Because ingestion blanks identity fields on upsert (Section 4.7), the operational order is:
Events: Fetch & Upsert (next 72h)
Populates/updates Event rows (scheduled-only)
Enforces Event headers
Blanks event_id/batch_id/type on upserted rows
Batching post-pass (applyBatchingForKeys_())
Deterministically repopulates event_id/batch_id/type
Required before predictions
Predictions: Run
Requires event_id and type to be non-empty
Writes/upserts into Predictions by (event_id, ai_name)
Ensures synthetic batch rows exist in Predictions for member events
Actuals: Rolling fetch (manual or hourly trigger)
Requires SeriesMap mapping
Writes released_value and updates release_status
Market Reaction: manual run (optional)
Logs market move around release time (best-effort)
Does not persist scoring tables
Code-authoritative note. The code does not automatically chain these steps end-to-end; it provides menu tools and a trigger for hourly actuals only.

12.2 Minimum sheet prerequisites (operator checklist)
Before running any menu tools, ensure these sheets exist:
Required for core pipeline
Event
Predictions
log
Required for actuals mapping workflow
SeriesMap
Optional / created on demand
SeriesMap_Suggestions (auto-created by suggestion/backfill tools)

12.3 Minimum key prerequisites
FMP ingestion
Script Property FMP_API_KEY (or CFG.FMP_API_KEY set in code)
Predictions
At least one provider key available (otherwise “No providers enabled”):
GEMINI_API_KEY / GOOGLE_API_KEY / GOOGLE_AI_STUDIO_API_KEY
OPENAI_API_KEY
ANTHROPIC_API_KEY
Rolling actuals
FRED_API_KEY (for primary path)
SeriesMap entries for events you care about
Market reaction
Candle provider keys (Alpha Vantage and/or Twelve Data) in Script Properties

12.4 Common operator failure patterns (and code-accurate remedies)
Predictions run selects 0 events Likely cause: event_id/type missing due to upsert overwriting them. Remedy: run batching post-pass immediately after ingestion.
Actuals keeps logging “No SeriesMap match” Cause: missing mapping. Remedy: triage SeriesMap_Suggestions and promote entries into SeriesMap.
Market reaction finds no eligible events Cause: release_ts stored as text, not Date object. Remedy: ensure release_ts column is Date-typed for relevant rows (Sheets formatting/storage).
Hourly actuals trigger exists but no updates happen Causes: SeriesMap missing, FRED key missing, or events classified as qualitative and skipped. Remedy: check logs for skip reasons and mapping.


13) Guarantees, Non-Guarantees, and Explicit Limitations (rule1.3.1)
13.1 Guarantees (only what code enforces)
G1 — Deterministic identity assignment (given stable inputs) If Event rows have stable values for:
country, indicator_name, release_ts
…then applyBatchingForKeys_() will assign:
stable event_id values seeded from (country, minuteUTC, indicator_name)
stable batch_id values seeded from (country, minuteUTC) only for groups with 2+ events
Boundary
Any change in those input fields changes the IDs.
Code-authoritative note. IDs are hash-derived from these fields; this is explicit in batching code.

G2 — Predictions upsert uniqueness by (event_id, ai_name) For a given (event_id, ai_name), the Predictions sheet will contain at most one row written by the runner; re-runs overwrite the existing row.
Code-authoritative note. Upsert is keyed on these two fields.

G3 — Strict JSON validation for prediction payloads A provider response is treated as “valid” only if it can be parsed into a JSON object that includes event_id and type. Otherwise, an error row is written.
Code-authoritative note. This is enforced by the prediction runner to prevent silent mismatches.

G4 — Rolling actuals lifecycle monotonicity (no downgrade) Within the rolling actuals harvester, a row that becomes revised will not be automatically downgraded back to released.
Code-authoritative note. Only scheduled → released and released → revised transitions are implemented.

13.2 Non-guarantees (explicitly not promised by code)
NG1 — Completeness of event coverage The system does not guarantee that all relevant events appear in the Event sheet. It depends on FMP results and local filtering.
NG2 — Accuracy of SeriesMap suggestions Candidates and suggestions are advisory. The system does not guarantee that suggested series_id values are correct.
NG3 — Actuals availability Even with a correct SeriesMap, actuals can fail due to:
missing API keys
provider downtime/rate limits
release timing differences vs reference date windows
transforms requiring missing helpers
NG4 — Market reaction data availability and fidelity Market reaction depends on external candle APIs and may return:
no candles
incomplete candles near release time
timing misalignment vs the true release second (minute-level anchoring)
NG5 — Logging completeness Logs are best-effort and may be missing even when operations succeed.

13.3 Explicit limitations (must be acknowledged operationally)
L1 — Ingestion overwrites identity fields Event upsert explicitly writes event_id/batch_id/type as blanks; batching must be run after ingestion.
L2 — Rolling FMP actuals fallback is narrow Rolling actuals supports FMP only via series_id = calendar:<Event Name>. Other FMP forms are not fetched.
L3 — Backfill uses different provider labels and status vocabulary Backfill uses FMP_CAL and status values like pending/fetched/error, which are not reconciled into rolling lifecycle automatically.
L4 — Menu wiring gaps exist Some menu items reference non-existent functions (e.g., runPredictionsWindow, runFmpRangeToEvent_). Operator workflows should use the implemented entrypoints described in this Rule Book.

14) Appendix: Glossary & Field Semantics (rule1.3.1)
This appendix defines terms and fields as they are used in code, not aspirational meanings.

14.1 Core entities
Event (Economic Event) A scheduled macroeconomic release ingested from FMP and stored in the Event sheet. It is the canonical unit for identity, batching, prediction eligibility, and actuals lifecycle.
Prediction A single AI-generated output associated with one event_id and one provider (ai_name). Stored in the Predictions sheet and overwritten on re-runs for the same key.
Synthetic Batch Row A Predictions-only artifact representing a group of Events released at the same minute for the same country. It does not correspond to any Event row.

14.2 Identity & batching terms
event_id Deterministic identifier for a single Event row. Seeded from (country, release_ts@minuteUTC, indicator_name).
batch_id Deterministic identifier shared by 2+ Events that share (country, release_ts@minuteUTC). Empty string for non-batched events.
type (Event sheet)
single: the only event in its minute+country group
member: one of multiple events in its minute+country group
type (Predictions sheet)
single: prediction tied to a single Event
member: prediction tied to a member Event
batch: synthetic summary row (Predictions-only)

14.3 Time & window terms
release_ts Canonical scheduled release timestamp for an Event. Stored as UTC ISO YYYY-MM-DDTHH:MM:00Z (string) or as a Date object, depending on write path.
Window (prediction) A UTC time range used to select Events eligible for prediction runs. Default: now − 24h → now + 36h.
Window (actuals) A rolling UTC lookback window used to detect newly released or revised actuals.

14.4 Prediction fields
ai_name Logical provider name: Gemini, OpenAI, or Anthropic.
ai_model / ai_version Provider-specific model identifiers as recorded at runtime. Not used for routing.
ai_forecast_value Numeric forecast in indicator units. Must be blank (null) for qualitative-only events.
qualitative_only Boolean-like flag (true/false, stored as string) indicating that numeric forecasts are disallowed.
qualitative_result One of: stronger, weaker, inline. Represents direction relative to consensus/expectation, not FX direction.
expected_move_dir One of: up, down, flat. Represents expected FX direction for the configured fx_pair.
expected_move_pips_min / max Lower/upper bounds of expected FX move in pips.
prediction_id Deterministic UUID derived from (event_id | ai_name).

14.5 Actuals & lifecycle fields
released_value Numeric actual value written by actuals fetchers after rounding/transform (if applicable).
released_ts Timestamp at which the actual was observed or fetched. Not guaranteed to equal the true publication time.
release_status (rolling pipeline)
scheduled: no actual fetched yet
released: actual fetched
revised: actual value changed after initial fetch
release_status (backfill tool) May include pending, fetched, error. These are maintenance-tool states and not reconciled automatically.

14.6 SeriesMap terms
SeriesMap Authoritative mapping table defining how an Event’s indicator_name resolves to an upstream data series.
indicator_name_pattern Substring or regex pattern matched against normalized event names.
provider Upstream data source identifier (FRED, FMP, FILTER, etc.).
series_id Provider-specific identifier for the data series.
transform Optional transformation applied to observations (e.g., LEVEL, MOM_PCT, YOY_PCT), subject to helper availability.

14.7 Market reaction terms
Market reaction Observed USD/JPY price movement around an Event’s release time, computed from short-horizon FX candles.
Initial move / sustained move Implementation-defined measures of immediate vs later price response; used only for logging.
no_candles Outcome indicating that candle data could not be fetched or was insufficient.

14.8 Logging terms
log sheet Append-only operational log. Not a source of truth for system state.
context_json Free-form JSON payload attached to a log entry; schema is not enforced.

14.9 Operator**
A human user running menu actions, triaging SeriesMap, or performing maintenance/backfill tasks. Many guarantees depend on correct operator sequencing.