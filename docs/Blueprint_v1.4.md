Blueprint ver.1.4 — Economic Event AI Prediction System (current operational state, Jun 2026)
Code-authoritative specification.

## 1) Purpose & Scope (Blueprint ver.1.4)

PreSignal ver.1.4 is a Google Sheets + Apps Script system that:

- Ingests upcoming macroeconomic events (currently via the FMP calendar fetcher), normalizes them, and upserts them into the Event sheet.
- Deterministically assigns identity + batching (event_id / batch_id / type) using the canonical batching rules implemented in the Apps Script codebase.
- Generates AI predictions for events into the Predictions sheet via a multi-provider runner (manual menu actions and a configurable window runner).
- Fetches released actual values for events and writes them back into the Event sheet (released_value / released_ts / provider metadata), using a deterministic hybrid resolver: direct FMP calendar resolution first, then selective SeriesMap fallback where needed.
- Computes a short-horizon USD/JPY “market reaction” move around release timestamps, logs the result, and writes best-effort evaluation fields back into matching Predictions rows.
- Builds derived evaluation/report tabs from scored Predictions rows for operator review and provider comparison.
- Builds a derived-only character diagnostics stack from existing predictions/outcomes, including residual, recurrence, economic-outcome-link, falsification, drift, and recurrence-to-economic-validation layers. These layers read from existing operational/derived sheets and do not modify prediction behavior, routing, weighting, calibration, or scoring.

Operationally, this blueprint documents only what is implemented in the uploaded Apps Script code. It does not assume any extra “evaluation/correction module” beyond what the code currently executes. Market reaction now performs a lightweight join back into Predictions for best-effort evaluation fields, and the evaluation builder now rewrites derived reporting tabs from those scored prediction rows. The system still does not build a separate scoring warehouse or autonomous leaderboard service.

### Version labeling note

For repo-level comparison and replay analysis, the `ver.1.4` line may be referenced with lightweight sub-labels:

- `v1.4-baseline`: pre-Attention Factor Selection v1 behavior
- `v1.4-attn-shadow`: same prediction/scoring behavior, with shadow-mode attention metadata collection enabled

This distinction is intended to separate metadata-era builds from earlier `v1.4` runs without implying a new major architecture or a new active prediction controller.

### June 2026 operational addendum

The current live codebase extends the original blueprint with deterministic feature-pack and market-context layers used for diagnostics and controlled replay:

- `HistoricalContext v1a` remains the baseline same-indicator history layer.
- `Feature Pack v2A` adds deterministic same-event context packs:
  - `surprise_pack`
  - `revision_pack`
  - `family_pack`
  - `signal_quality_pack`
- `Feature Pack v2B-Core` adds replay-safe market / rate context under `market_context_pack`.
- Market-context snapshots use data available at or before `release_ts`, explicitly sort returned rows before snapshot selection, and select the latest row `<= release_ts`.
- Validated sources currently in use are FRED (`FEDFUNDS`, `DFF`, `DGS2`, `DGS10`, `IRLTLT01JPM156N`), EODHD (`USDJPY.FOREX`, `GSPC.INDX`, `XAUUSD.FOREX`), and FMP (`DX-Y.NYB`, `CLUSD`).
- VIX, NDX, JP2Y, BOJ policy rate, and US-JP 2Y spread remain excluded until a separate exact-mapping repair task validates them.
- Controlled replay, context-consumption, and market-context sanity/validation tabs are diagnostics only. They do not authorize routing, weighting, calibration, or production-behavior changes.
- Live Google Sheets / Apps Script runs should prefer outside-sandbox execution. The Codex sandbox has shown intermittent name-resolution failures against `oauth2.googleapis.com` and `sheets.googleapis.com`; those failures are environment noise, not prediction-logic regressions.
- When surfaced by automation, network/name-resolution failures are classified separately (for example, `google_dns_resolution_failure`) so they can be distinguished from model, prompt, or family-rule failures.
- Character diagnostics are layered atop the same derived-only foundation. Current live tabs include:
  - `Character_Baseline_E`
  - `Provider_Character_Residuals`
  - `Provider_Character_Summary`
  - `Provider_Character_Family_Summary`
  - `Character_Disagreement_Report`
  - `Character_Recurrence_Validation`
  - `Character_Recurrence_Family_Validation`
  - `Character_Drift_Assessment`
  - Retired and intentionally removed legacy tabs from the old outcome / signal path: `Character_Outcome_Link`, `Character_Outcome_Summary`, `Character_Outcome_Family_Link`, `Character_Outcome_Provider_Controlled`, `Character_Outcome_Family_Controlled`, `Character_Outcome_Permutation_Test`, `Character_Outcome_Robust_Traits`, `Character_Good_Reasoning_Proxy_Test`, `Character_Outcome_Falsification_Report`, `Character_Outcome_Recurrence_Validation`, `Character_Outcome_Recurrence_Block_Detail`, `Character_Outcome_Recurrence_Interpretation`, `Character_Signal_Candidates`, `Character_Signal_Candidate_Summary`, `Character_Signal_Candidate_Family_Map`, `Character_Signal_Readiness_Report`, `Character_Signal_Shadow_Test`, `Character_Signal_Shadow_Family_Test`, `Character_Signal_Shadow_Summary`, and `Character_Signal_Shadow_Readiness`.
  - These are read-only diagnostics only; they do not authorize prompt changes, provider-role assignment, routing, weighting, or calibration.

### Jan 31 2025 Attention Factor checkpoint

Status labels:

- `attention_factor_v1_status = frozen_explainability`
- `attention_factor_v1_goal_1_status = successful_provider_individuality_layer`
- `attention_factor_v1_goal_2_status = not_approved_for_routing_or_weighting`
- `attention_phase_3a_v1_promotion_status = closed_frozen`
- `attention_phase_3b_status = not_approved`
- `next_active_track = feature_pack_v2b_replay_validation`
- `future_item = attention_factor_v2_causal_attention_experiment`

The Jan 31 2025 checkpoint preserves Attention Factor Selection v1 as an explainability/provider-individuality diagnostics layer. The checkpoint did not approve Phase 3B, provider routing, provider weighting, calibration, or behavior overrides.

Important implementation boundary: Attention Factor v1 is one-shot. Providers return prediction fields and `attention_factors` together in a single provider response. This establishes provider-reported individuality and explanation diversity, not proven causal attention steering.

Future roadmap item: `Attention Factor v2 - Causal Attention Experiment` may later test a two-step architecture where providers first choose 2-3 attention factors and then generate predictions using those selected factors as primary reasoning anchors. That future item is experimental only and is not production, subscriber-facing, or a replacement for v1.

The next active development recommendation is to validate `HistoricalContext v1a` / `Feature Pack v2A` on repeat-indicator slices, then extend cautiously to same-family memory only if the results remain stable and useful. Routing, weighting, calibration, and provider-prompt policy remain frozen pending clear evidence from feature-pack experiments.

#### Next Track: Family Rule / Batch Splitting Investigation

The next active track is validation of `HistoricalContext v1a` / `Feature Pack v2A` on repeat-indicator slices, with cautious same-family expansion only after those runs prove stable and useful. Recurring `family_rule` and `batch_splitting` findings remain diagnostics/reporting issues, not approved live behavior changes.

Questions this track should answer:

1. Are certain event families being grouped, compared, or scored incorrectly?
2. Are same-minute batches mixing unrelated or weakly related events?
3. Does batch-level prediction lose signal compared with member-level prediction?
4. Are family rules needed before any provider weighting or routing can work?
5. Is `batch_splitting` a better accuracy-improvement path than Attention Factor routing?
6. Are `family_rule` findings pointing to deterministic system structure issues rather than AI-provider issues?

This track is not an implemented behavior change. It does not approve prompt changes, scoring changes, live prediction behavior changes, provider routing, provider weighting, calibration, or Phase 3B promotion.


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
Evaluation_BatchCompare
Evaluation_Scenario
Prediction_Aggregates
Outcome_Ledger
Outcome_Summary_ProviderFamily
Outcome_Summary_Convergence
Outcome_Summary_Bucket
Outcome_Diagnostics
Character_Baseline_E
Provider_Character_Residuals
Provider_Character_Summary
Provider_Character_Family_Summary
Character_Disagreement_Report
Character_Recurrence_Validation
Character_Recurrence_Family_Validation
Character_Drift_Assessment
Retired legacy tabs from the old outcome / signal path are intentionally excluded and must not be recreated.
Attention_Factor_Summary
Provider_Character_Diagnostics
Attention_Provider_Individuality
Attention_Evidence_Report
Attention_Disagreement_Review
Attention_Disagreement_Summary
Attention_Phase3_Candidates
Attention_Shadow_Experiments
Attention_Shadow_Summary
Family_Structure_Report
Batch_Splitting_Candidates
Batch_Split_Counterfactuals
Batch_Baseline_Coverage_Audit
Batch_Split_Group_Counterfactuals
Inflation_NoSignal_Review

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
object, run_id, prediction_id, schema_version, created_ts, event_id, batch_id, type, ai_name, ai_version, ai_model, model_version, consensus_value, prev_revision, source_cal, genre, importance, fx_pair, ai_forecast_value, qualitative_result, expected_move_dir, expected_move_pips_min, expected_move_pips_max, expected_holding_minutes, rationale_short, rationale, prompt_tokens, completion_tokens, latency_ms, raw_output, status, error_message, qualitative_only, released_value, forecast_error_abs, forecast_error_pct, forecast_dir_ok, eval_ts, eval_interval, start_ts, end_ts, start_price, end_price, realized_pips, dir_ok, band_ok, overall_ok, eval_note, indicator_name, country, release_ts, mr_window_min, mr_pred_dir, mr_pred_net_pips, mr_pred_strength, mr_pred_sustain_min, mr_real_dir, mr_strength_ok, mr_real_sustain_min, mr_sustain_error_min, mr_sustain_grade, mr_sustain_ok, mr_dir_ok, mr_real_max_up_pips, mr_real_max_down_pips, mr_final_provider, mr_compare_status, mr_compare_dir_agree, mr_compare_anchor_delta_min, mr_compare_pips_delta, mr_compare_confidence, mr_compare_note, batch_anchor_mode, batch_anchor_confidence, batch_anchor_event_id, batch_anchor_indicator_name, batch_anchor_score, batch_anchor_margin, batch_anchor_runner_up_event_id, batch_anchor_runner_up_indicator_name, batch_anchor_reason, cache_creation_input_tokens, cache_read_input_tokens, pre_signal_mode, pre_risk_level, pre_volatility_level, watch_member_event_ids, watch_member_indicator_names, scenario_up_case, scenario_down_case, scenario_flat_case, scenario_confidence, scenario_plan_json

The `pre_*` / `scenario_*` columns are advisory pre-release planning fields. They sit alongside the existing directional prediction fields and do not change the legacy directional/pips summary math; scenario-watchlist coverage is reported separately in `Evaluation_Scenario`.

The planner also uses the same `pre_*` fields to surface recurring low-signal family handling without introducing new schema. Current code-level low-signal families include `cftc_positions`, `treasury_auctions`, `fed_speeches`, and `statement_report_text`; these families default toward conservative scenario framing and representative watchlists instead of high-confidence directional precision. The family detection is applied at row level as well as batch level so single/member speech and report-text rows inherit the same conservative handling.

Current live behavior also includes a deterministic confidence-calibration pass over the same pre-release planning fields. This does not add schema. Instead, it downgrades `scenario_confidence` when existing trace signals already imply weaker conviction, especially weak or unclear batch anchors, low `batch_anchor_confidence`, missing consensus, hidden-detail risk, and `HistoricalContext v1a` with `history_quality = partial` or `cold_start`. A narrow additional downgrade now applies to standalone `jobless_claims` member rows when same-indicator history is mixed or thin, or when the row is a supporting claims metric such as `continuing claims` or the `4-week average`.

#### MR_ProviderRuns audit headers

When market reaction scoring runs, the system may also append provider-level results to `MR_ProviderRuns`. The audit schema is append-only and includes:

score_run_ts, score_source, event_id, indicator_name, country, release_ts, provider, status, anchor_detected, anchor_phase, anchor_ts, start_ts, end_ts, start_price, end_price, realized_pips, real_dir, real_strength, realized_sustain_min, max_up_pips, max_down_pips, candle_count, provider_meta_json, compare_status, compare_confidence, error_note

#### Evaluation_Rows / Evaluation_Summary derived headers

When `Build Evaluation Sheets` runs, the system rewrites four derived reporting tabs from scored `Predictions` rows:

- `Evaluation_Rows`
- `Evaluation_Summary`
- `Evaluation_BatchCompare`
- `Evaluation_Scenario`

`Evaluation_Rows` includes trace and scored fields such as:

generated_ts, release_date, release_ts, event_id, batch_id, prediction_id, run_id, type, indicator_name, country, genre, importance, fx_pair, ai_name, ai_model, schema_version, status, qualitative_result, consensus_value, prev_revision, ai_forecast_value, released_value, mr_pred_dir, mr_pred_net_pips, mr_pred_strength, mr_pred_sustain_min, mr_real_dir, mr_real_strength, mr_real_sustain_min, mr_dir_ok, mr_strength_ok, mr_sustain_ok, overall_ok, realized_pips, mr_real_max_up_pips, mr_real_max_down_pips, mr_final_provider, eval_note, mr_compare_status, mr_compare_note, eval_ts, trace_prediction_key, batch_anchor_mode, batch_anchor_confidence, batch_anchor_event_id, batch_anchor_indicator_name, batch_anchor_score, batch_anchor_margin, batch_anchor_runner_up_event_id, batch_anchor_runner_up_indicator_name, batch_anchor_reason, pre_signal_mode, pre_risk_level, pre_volatility_level, watch_member_event_ids, watch_member_indicator_names, scenario_confidence

`Evaluation_Summary` includes grouped aggregates such as:

generated_ts, release_date, ai_name, scope, rows_scored, dir_ok_count, dir_ok_rate, strength_ok_count, strength_ok_rate, sustain_ok_count, sustain_ok_rate, overall_ok_count, overall_ok_rate, avg_realized_abs_pips, avg_pred_abs_pips

`Evaluation_BatchCompare` includes batch-vs-best-member comparison fields plus persisted batch-anchor selection trace fields, so operators can review whether the chosen anchor matched the strongest member-level outcome. For known same-minute mixed clusters, the best-member candidate pool is filtered to the release family first, preventing unrelated side rows such as CFTC/commodity positioning from winning a labor, ISM, or claims-family comparison.

`Evaluation_Scenario` includes scenario-watchlist coverage fields such as watch_member_event_ids, watch_member_indicator_names, best_member_event_id, best_member_rank_in_watchlist, watchlist_hit, and scenario_eval_result. It includes only scenario-mode batch predictions, excluding directional batches that merely carry anchor/context watch members. It grades whether the scenario map covered the same family-filtered best-scoring member without changing legacy directional/pips scoring.

For local automation, the project also exposes API-safe execution wrappers callable through the Apps Script Execution API: `apiRunPipelineWindow_`, `apiRunPredictionsWindow_`, `apiFetchActualsWindow_`, `apiScoreMarketReactionWindow_`, and `apiBuildEvaluationSheets_`. These wrappers accept plain parameter objects, avoid menu/UI flows, and support persistent-token external runners.

Additional public inspection/reporting wrappers now exposed are:

- `debugHistoricalContextForEvent(eventId)`
- `buildPredictionAggregateForEvent(eventId)`
- `buildPredictionAggregatesSheet()`

Weak-anchor families may also define structural watch profiles rather than forcing a default winner. In the current design, this includes monthly labor, ISM services, and jobless-claims clusters, where the system preserves a ranked watchlist of the most decision-relevant members instead of overcommitting to one ambiguous release row.

These sheets are rebuilt from scratch on each run and are derived reporting layers only. `Evaluation_Summary` excludes rows that were not truly scored, including `market_closed` and other unavailable-data cases, while `Evaluation_Rows` retains those rows for traceability.

#### Prediction_Aggregates derived headers

When `buildPredictionAggregatesSheet()` runs, the system also rewrites `Prediction_Aggregates` from existing `Predictions` rows.

Headers:

generated_ts, event_id, batch_id, type, country, indicator_name, release_ts, provider_count, economic_aggregate_bias, economic_agreement_level, market_aggregate_bias, market_agreement_level, market_disagreement_level, up_count, down_count, flat_count, uncertain_count, whipsaw_risk, volatility_risk, aggregate_confidence, summary_note, no_trade_advice_flag

This sheet is derived-only and not canonical. Implementation details:

- rows are grouped by `event_id`
- provider rows are deduplicated by canonical prediction identity `(event_id, ai_name)`; `prediction_id` remains trace metadata only
- the newest row by `created_ts` is retained
- non-`ok` rows count as `uncertain`
- `summary_note` remains responsibility-safe reporting text
- `no_trade_advice_flag` remains `TRUE`

#### Outcome_Ledger derived headers

When `buildOutcomeLedgerSheet()` runs, the system rewrites `Outcome_Ledger` from deduped `Predictions` rows.

In Phase 1, `Outcome_Ledger` is a rebuilt derived audit sheet. It is intentionally conservative and does not yet function as the final immutable learning warehouse. Future phases may introduce an append-only or versioned learning ledger after this derived view is validated.

Headers:

generated_ts, release_date, release_ts, event_id, batch_id, prediction_id, run_id, type, outcome_family, indicator_name, country, genre, importance, ai_name, ai_model, status, qualitative_result, mr_pred_dir, mr_pred_net_pips, mr_pred_strength, mr_pred_sustain_min, mr_real_dir, mr_real_strength, mr_real_sustain_min, realized_pips, mr_dir_ok, mr_strength_ok, mr_sustain_ok, overall_ok, outcome_score, outcome_bucket, scored_flag, prediction_bias, confidence, pre_signal_mode, pre_risk_level, pre_volatility_level, batch_anchor_mode, batch_anchor_confidence, trace_prediction_key, eval_ts, eval_note, no_trade_advice_flag

This sheet is derived-only and not canonical. Implementation details:

- rows are deduplicated by canonical prediction identity `(event_id, ai_name)`; `prediction_id` remains trace metadata only
- the newest row by `created_ts`, then `eval_ts`, is retained
- `outcome_score` and `outcome_bucket` are deterministic reporting labels
- missing `Outcome_Ledger` headers are appended, and existing `Outcome_Ledger` headers are not reordered
- `no_trade_advice_flag` remains `TRUE`

#### Outcome and attention derived reporting headers

The system also supports rebuilt derived reporting tabs for outcome and attention-era review:

- `Outcome_Summary_ProviderFamily`
- `Outcome_Summary_Convergence`
- `Outcome_Summary_Bucket`
- `Outcome_Diagnostics`
- `Character_Baseline_E`
- `Provider_Character_Residuals`
- `Provider_Character_Summary`
- `Provider_Character_Family_Summary`
- `Character_Disagreement_Report`
- `Character_Recurrence_Validation`
- `Character_Recurrence_Family_Validation`
- `Character_Drift_Assessment`
- Retired and intentionally removed legacy tabs from the old outcome / signal path: `Character_Outcome_Link`, `Character_Outcome_Summary`, `Character_Outcome_Family_Link`, `Character_Outcome_Provider_Controlled`, `Character_Outcome_Family_Controlled`, `Character_Outcome_Permutation_Test`, `Character_Outcome_Robust_Traits`, `Character_Good_Reasoning_Proxy_Test`, `Character_Outcome_Falsification_Report`, `Character_Outcome_Recurrence_Validation`, `Character_Outcome_Recurrence_Block_Detail`, `Character_Outcome_Recurrence_Interpretation`, `Character_Signal_Candidates`, `Character_Signal_Candidate_Summary`, `Character_Signal_Candidate_Family_Map`, `Character_Signal_Readiness_Report`, `Character_Signal_Shadow_Test`, `Character_Signal_Shadow_Family_Test`, `Character_Signal_Shadow_Summary`, and `Character_Signal_Shadow_Readiness`.
- `Attention_Factor_Summary`
- `Provider_Character_Diagnostics`
- `Attention_Provider_Individuality`
- `Attention_Evidence_Report`
- `Attention_Disagreement_Review`
- `Attention_Disagreement_Summary`
- `Attention_Phase3_Candidates`
- `Attention_Shadow_Experiments`
- `Attention_Shadow_Summary`
- `Family_Structure_Report`
- `Batch_Splitting_Candidates`
- `Batch_Split_Counterfactuals`
- `Batch_Baseline_Coverage_Audit`
- `Batch_Split_Group_Counterfactuals`
- `Inflation_NoSignal_Review`

These sheets are read-only over their source layers and rewrite only their own body rows. Missing headers are appended, existing header order is preserved, and the builders do not modify `Event`, `Predictions`, `Outcome_Ledger`, `MR_ProviderRuns`, or evaluation sheets.

`Attention_Factor_Summary`, `Provider_Character_Diagnostics`, `Attention_Provider_Individuality`, `Attention_Evidence_Report`, `Attention_Disagreement_Review`, and `Attention_Disagreement_Summary` are Phase 2 shadow-mode analysis layers. `Attention_Provider_Individuality` specifically separates provider individuality/explainability evidence from performance evidence. As of the Jan 31 2025 checkpoint, Attention Factor v1 is frozen as an explainability/provider-individuality layer. `Attention_Phase3_Candidates` is a conservative bridge layer for Phase 3 design review, and `Attention_Shadow_Experiments` and `Attention_Shadow_Summary` are Phase 3A counterfactual reporting layers, but Phase 3A v1 promotion is closed/frozen and Phase 3B is not approved. These sheets expose selected reasoning-factor evidence, provider-character evidence, case-level disagreement evidence, candidate-only experiment slices, and shadow experiment outcomes for review only. They do not control prompts, provider roles, provider weighting, calibration, Market Reaction Memory, scoring, or signal generation. V1 attention factors are returned in the same provider response as prediction fields and must not be described as proven causal controls.

`Character_Baseline_E`, `Provider_Character_Residuals`, `Provider_Character_Summary`, `Provider_Character_Family_Summary`, and `Character_Disagreement_Report` are the Character Residual Architecture v1 diagnostics layers. They construct a deterministic baseline from existing event fields and context, then record provider residual behavior relative to that baseline without changing prediction semantics or provider prompts. The retired `Character_Outcome_*`, `Character_Signal_*`, and `Character_Signal_Shadow_*` tabs are historical only and must not be recreated.

Provider Character v1 is completed and frozen. Its validated evidence base includes Character Residual, Character Recurrence, Provider Individuality, Economic Outcome Link, and Economic Falsification. The older market-reaction outcome, reliability outcome, and calibration-candidate branches remain retired. Provider Character v2 is now the active Direct Expression Research Branch, which uses compact free-form provider expressions instead of predefined labels because the label taxonomy may be compressing or obscuring useful provider reasoning patterns. Its active methodology roadmap is:

`Direct Expression Capture`
↓
`Same Path Validation`
↓
`Signal Synchrony`
↓
`Provider Slice Analysis`
↓
`Family Slice Analysis`
↓
`Event Class Analysis`
↓
`Conditional Predictive Value`
↓
`Calibration Research`
↓
`Production Learning`

Methodology Validation now groups the Direct Expression, Same Path, Signal Synchrony, Measurement Stability, and Reproducibility layers. Signal Synchrony v1 is active methodology validation and is not a prediction system.

`Character_Recurrence_Validation`, `Character_Recurrence_Family_Validation`, and `Character_Drift_Assessment` remain derived-only validation layers. They compare independent blocks, test recurrence, and measure drift. The retired `Character_Outcome_*`, `Character_Signal_*`, and `Character_Signal_Shadow_*` tabs are historical only and must not be recreated.

`Feature_Pack_Audit`, `Surprise_Pack_Coverage_Report`, `Market_Context_Provider_Repair_Report`, `Market_Context_Data_Sanity_Report`, `Market_Context_Source_Validation_Report`, `Feature_Pack_v2B_Core_Audit`, `Production_vs_V2B_Replay`, `V2B_Context_Utilization_Report`, `V2B_Prediction_Stability`, `Production_vs_V2B_Summary`, `Production_vs_V2B_Family_Summary`, `Production_vs_V2B_Provider_Summary`, and `V2B_Context_Consumption_Audit` are diagnostics layers for feature-pack and replay validation. They are read-only over their source layers, may be rebuilt deterministically, and must not change provider prompts, routing, weighting, calibration, scoring logic, or canonical prediction semantics.

`Family_Structure_Report` is the active post-Attention-v1 diagnostic layer for Family Structure Investigation v1. It is read-only over existing outcome, evaluation, and attention review sheets. It exists to decide whether future `Family Rule v1` or `Batch Splitting v1` work is justified by recurring structure evidence. It must not change prediction prompts, prediction semantics, batching rules, scoring, market reaction logic, provider weighting, calibration, routing, or subscriber-facing behavior.

`Economic_Value_Accuracy` is a derived-only diagnostic report that separates economic release prediction accuracy from market reaction prediction accuracy. It reads existing `Predictions` rows and matched `Event` actuals where available, scores economic-value direction conservatively, and compares that value-direction result against existing market-reaction grading. It does not modify prompts, providers, Predictions rows, Event rows, market-reaction scoring, evaluation scoring, Attention Factor logic, Family Structure logic, batching behavior, routing, weighting, calibration, or subscriber-facing behavior.

`Provider_Family_Economic_Accuracy` is a derived-only ranking/reporting layer over `Economic_Value_Accuracy`. It uses the existing `provider_family_summary` rows as its source of truth and highlights which provider-family slices may contain economic-value signal versus thin-sample noise. It does not create a second scoring path and does not change prompts, providers, Predictions rows, Event rows, market-reaction scoring, evaluation scoring, routing, weighting, calibration, or subscriber-facing behavior.

`Economic_To_Market_Translation_Errors` is a derived-only diagnostic layer over `Economic_Value_Accuracy` and `Provider_Family_Economic_Accuracy`. It isolates rows where economic value direction was correct but market direction was wrong, then groups them by provider, family, and failure mode so the team can inspect whether the miss came from opposite-direction logic, muted/flat market behavior, or strength/sustain mismatch. It does not change prompts, providers, Predictions rows, Event rows, market-reaction scoring, evaluation scoring, routing, weighting, calibration, or subscriber-facing behavior.

`Attention_Economic_Value_Report` is a derived-only diagnostic layer over existing `Economic_Value_Accuracy` case rows plus already-saved attention-factor labels from `Predictions`. It asks whether any attention-factor labels correlate with stronger or weaker economic-value accuracy globally, by provider, by family, or by provider-family slice. It is correlation-only: Attention Factor v1 factors are provider-reported metadata returned alongside predictions, and this report must not claim causality or change prompts, providers, Predictions rows, Event rows, scoring, routing, weighting, calibration, or subscriber-facing behavior.

`Attention_V3_Replay`, `Attention_V3_Replay_Evaluation`, and `Attention_V3_Replay_Reliability` are experimental, replay-only diagnostics for a narrow Attention-First plus Reflection test. They sample a small scored subset of historical event/provider rows, run an attention-selection step before prediction, then add a post-prediction reflection step. They must never overwrite `Predictions`, `Evaluation_*`, `Outcome_Ledger`, or existing Attention reports, and they must not be interpreted as production readiness, routing approval, weighting approval, calibration approval, or prompt-policy replacement.

Heavy diagnostics may write to an external derived-only workbook when `DIAGNOSTICS_SPREADSHEET_ID` is configured in the `Config` sheet or Script Properties. In that mode, the main workbook remains the canonical operational source of truth, and the diagnostics workbook is only an output target for large analytical reports. External diagnostics output must not imply live behavior changes or replace canonical operational sheets.

Workbook location is an infrastructure concern, not a builder concern. Derived report builders should resolve source sheets through a central sheet-location registry so migrated sheets can be read from `MAIN`, `DIAGNOSTICS`, `OVERVIEW`, or future archive workbooks without per-builder rewrites. `MAIN_SPREADSHEET_ID` may explicitly pin the canonical operational workbook for API execution contexts where `SpreadsheetApp.getActive()` is ambiguous. `DIAGNOSTICS_SPREADSHEET_ID` controls the diagnostics workbook; `OVERVIEW_SPREADSHEET_ID` controls the project-overview workbook (`project_overviews.xls`); both remain derived-only / governance-only and are not canonical operational sources of truth.

#### Project overview / governance workbook
`project_overviews.xls` is the governance and project-memory workbook. It stores project progression, status, roadmaps, research chronology, methodology corrections, and decision history.

Canonical tabs in the overview workbook:

- `Current_Roadmap`
- `Research_Journey`
- `PreSignal_Layer_Map`
- `Experiment_Register`
- `Interpretation_Corrections`
- `Decision_Log_v2`
- `Signal_Synchrony_v1`

Compatibility / derived governance helpers, if present, also resolve to the overview workbook:

- `Project_Status`
- `Decision_Log`

Migration governance and audit sheets, if present, also resolve to the overview workbook:

- `Workbook_Migration_Control`
- `Workbook_Migration_Log`
- `Workbook_Migration_Audit`
- `Workbook_Routing_Dependency_Audit`
- `Experiment_Lifecycle_Audit`
- `Experiment_Lifecycle_Summary`
- `Workbook_Migration_Phase2C_Report`
- `Workbook_Migration_Phase2E_Report`
- `Workbook_Migration_Post2F_Sanity_Audit`

`Workbook_Migration_Control` is the approval/control surface for sheet-migration batches, `Workbook_Migration_Log` is the append-only execution ledger, and the audit/lifecycle sheets are governance-only memory. They must not affect predictions, prompts, provider behavior, scoring, routing, weighting, calibration, or subscriber-facing behavior.

`Market_Sensitivity_Filter_Candidates` is a derived-only diagnostic layer over `Economic_To_Market_Translation_Errors` and `Provider_Family_Economic_Accuracy`. It ranks repeated flat-market translation failures into candidate low-confidence / no-signal filter rules so the team can inspect whether some families or indicators are being over-converted into directional market calls. It does not change prompts, providers, Predictions rows, Event rows, market-reaction scoring, evaluation scoring, routing, weighting, calibration, or subscriber-facing behavior.

`Market_Sensitivity_Filter_Summary` is a derived-only summary layer over `Market_Sensitivity_Filter_Candidates`. It rolls the atomized candidate rows up into decision-friendly family, provider-family, and family-importance summaries so the team can judge whether any future shadow no-signal counterfactual is justified. It does not change prompts, providers, Predictions rows, Event rows, market-reaction scoring, evaluation scoring, routing, weighting, calibration, or subscriber-facing behavior.

`Market_Sensitivity_NoSignal_Counterfactuals` is a derived-only shadow layer over `Market_Sensitivity_Filter_Summary` and `Economic_Value_Accuracy`. It tests whether suppressing directional market calls in candidate flat-market families would have avoided misses without throwing away too many correct calls. It does not change prompts, providers, Predictions rows, Event rows, market-reaction scoring, evaluation scoring, routing, weighting, calibration, or subscriber-facing behavior.

`Inflation_NoSignal_Review` is a derived-only review layer over `Market_Sensitivity_NoSignal_Counterfactuals` and `Economic_To_Market_Translation_Errors`. It narrows the shadow no-signal investigation to inflation slices and ranks them by misses avoided, correct calls lost, net benefit, and recurring translation-error shape. It does not activate no-signal behavior, confidence changes, prompt changes, routing, weighting, calibration, or subscriber-facing behavior.

`Project_Status` is the governance current-state sheet for major initiatives in `project_overviews.xls`. It records the current phase, status, confidence, evidence summary, decision summary, next action, review target, and staleness of active, monitoring, completed, frozen, rejected, and archived work. It is visibility and project-memory only and must not influence predictions, prompts, provider behavior, scoring, routing, weighting, calibration, learning, or subscriber-facing behavior.

`Decision_Log_v2` is the governance historical-memory sheet for major project decisions in `project_overviews.xls`. It records dated milestone decisions such as success, rejection, freezing, activation into monitoring, or roadmap direction changes. It is append-style historical memory implemented as a deterministic derived build and must not influence predictions, prompts, provider behavior, scoring, routing, weighting, calibration, learning, or subscriber-facing behavior. The legacy `Decision_Log` name is retained only for backward compatibility if older workbooks or scripts still reference it.

The functional roadmap and architecture compass are documented in `docs/PreSignal_Compass_v1.md`. That roadmap is descriptive only and exists to keep long-term architecture naming stable; it must not override the RuleBook, sheet schemas, or implementation constraints.

### Active fast rebuild path

`Build Active Decision Reports` / `apiBuildActiveDecisionReports()` is the current runtime-reduction rebuild path for active decision work. It rebuilds only:

- `Evaluation_Rows`, `Evaluation_Summary`, `Evaluation_BatchCompare`, `Evaluation_Scenario`
- `Outcome_Ledger`
- `Outcome_Summary_ProviderFamily`, `Outcome_Summary_Convergence`, `Outcome_Summary_Bucket`
- `Outcome_Diagnostics`
- `Economic_Value_Accuracy`
- `Provider_Family_Economic_Accuracy`
- `Economic_To_Market_Translation_Errors`
- `Market_Sensitivity_Filter_Candidates` as a dependency-only feeder layer
- `Market_Sensitivity_Filter_Summary`
- `Market_Sensitivity_NoSignal_Counterfactuals`
- `Inflation_NoSignal_Review`

This active fast rebuild path exists because the current decision stack is:

`economic-value -> provider-family economic accuracy -> translation-error -> market-sensitivity -> inflation no-signal`

Closed or frozen diagnostics remain preserved and manually rebuildable, but are not part of the active fast rebuild path. This includes Attention Phase 3A counterfactual reporting, Phase 3B promotion work, Family Structure Investigation, broad batch splitting diagnostics, and related archived counterfactual layers.

### Inflation no-signal checkpoint

Current status labels:

- `inflation_no_signal_v1_status = shadow_monitor_only`
- `inflation_no_signal_primary_slice = inflation_low_importance`
- `inflation_no_signal_secondary_slice = family_inflation`
- `inflation_no_signal_supporting_slices = Gemini_inflation, OpenAI_inflation`
- `inflation_no_signal_broad_market_sensitivity_status = not_approved`
- `inflation_no_signal_activation_status = not_approved`
- `central_bank_no_signal_status = not_approved`
- `next_decision = monitor_in_future_backtest_blocks`

Checkpoint reference: `docs/Inflation_NoSignal_Checkpoint_2026-06-14.md`

This checkpoint means the current inflation no-signal idea stays narrow and shadow-only. The leading slice is low-importance inflation. The family-wide inflation slice remains a monitor. Provider-specific inflation slices are supporting evidence, not primary control logic. Broad market-sensitivity no-signal behavior and central-bank no-signal behavior are not approved.

`Batch_Splitting_Candidates` is a derived diagnostic ranking layer over `Family_Structure_Report`. It ranks mixed-family, low-signal, and best-member-outperformed batch cases for review. It does not split batches, change event construction, change scoring, change prediction prompts, or approve live `Batch Splitting v1`.

As of the 2026-06-14 checkpoint, `Batch_Splitting_Candidates` is in `diagnostic_review_layer` status and live `Batch Splitting v1` is not approved. High-priority candidate review found enough repeated structure to justify a future shadow-only `Batch_Split_Counterfactuals` report, but not live behavior changes.

`Batch_Split_Counterfactuals` is a shadow-only counterfactual layer over `Batch_Splitting_Candidates`. It compares observed batch-level results against a best-member-derived split proxy from existing scored rows. It must label proxy-derived evidence clearly and must not create predictions, split live batches, alter `Event`, alter `Predictions`, change scoring, or change subscriber-facing behavior.

The corrected counterfactual result found `split_proxy_helped` across all 20 high-priority rows after mapping observed batch baselines from `Evaluation_BatchCompare`. This supports a future true shadow split-group counterfactual, not live batch splitting.

`Batch_Baseline_Coverage_Audit` is a derived diagnostic layer over `Batch_Split_Counterfactuals`, `Outcome_Ledger`, and `Evaluation_BatchCompare`. It audits why high-priority split candidates lack usable current batch baselines. It must not rebuild source reports, change scoring, change batch construction, or alter live behavior.

The initial coverage audit found `baseline_coverage_ok`; the earlier missing-baseline issue was a derived-report mapping gap, not missing source coverage.

`Batch_Split_Group_Counterfactuals` is a true shadow family-group counterfactual over existing scored member rows. It deterministically groups batch members by outcome family and compares the strongest family-group proxy against the observed batch baseline and best-member proxy. It must not create predictions, alter `Event`, alter `Predictions`, split live batches, change scoring, or change subscriber-facing behavior.

Initial group-counterfactual evidence is mixed and does not approve live batch splitting: 4 rows helped at the family-group level and 16 rows underperformed the best-member proxy. Further work, if any, should be narrow family-combo review rather than broad batch-splitting design.

As of the 2026-06-14 Family Structure Investigation checkpoint, Family Structure Investigation v1 is closed as diagnostics. Broad `Batch Splitting v1` is not approved and is rejected/frozen for now. The reports remain preserved diagnostics, and optional future work is limited to narrow family-combo review such as `housing+other`, `growth+other`, or `labor+other`.

Next Track: Family Rule / Batch Splitting Investigation. Attention Factor v1 showed providers are not clones, but it did not produce control/routing evidence. Recurring `family_rule` and `batch_splitting` findings may indicate the next bottleneck is event structure, family classification, or batch construction rather than provider individuality.

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

## 3A) Historical Context / Feature Pack

### 3A.1 Implemented scope

The current live runner includes a deterministic feature-pack stack attached before provider prompting.

Current baseline:

- same-indicator prior-release history only
- Event-sheet history only
- last 3 prior releases maximum
- no AI/provider call during construction
- no sheet schema expansion to persist the feature pack

Broader live stack:

- v2A same-event context packs are available as deterministic append-only context
- v2B-Core market context is available as replay-safe deterministic append-only context
- same-family memory lives in `family_pack`, not in the baseline same-indicator slice

Not implemented in this layer:

- autonomous trading advice
- routing, weighting, calibration, or provider-role changes

### 3A.2 Feature-pack contents

The baseline normalized shape remains:

- `feature_pack_version = "v2a_core_context"`
- `historical_context.same_indicator.events_seen`
- `historical_context.same_indicator.history_quality`
- `historical_context.same_indicator.last_3_actuals`
- `historical_context.same_indicator.last_3_consensus`
- `historical_context.same_indicator.last_3_surprises`
- `historical_context.same_indicator.surprise_bias`
- `historical_context.same_indicator.surprise_pattern`
- `historical_context.same_indicator.surprise_volatility`
- `historical_context.same_indicator.consensus_accuracy_trend`

Supported `history_quality` values are `full`, `partial`, and `cold_start`.

Supported `surprise_pattern` values are `persistent_positive`, `persistent_negative`, `mixed`, `flat`, and `unknown`.

#### v2A same-event context packs

The deterministic v2A context layer uses `feature_pack_version = "v2a_core_context"` and adds:

- `surprise_pack`
  - same-indicator surprise history
  - consensus availability rate
  - last 5 surprises
  - surprise bias / volatility
- `revision_pack`
  - revision event count
  - last 5 revision deltas
  - revision bias / volatility / frequency / risk
  - safe placeholder values when revision source data is insufficient
- `family_pack`
  - outcome family
  - family event count
  - family surprise bias / volatility
  - family forecastability proxy
  - family market-translation noise
- `signal_quality_pack`
  - signal quality score
  - reproducible reason codes such as `cold_start`, `partial_history`, `missing_consensus`, `high_surprise_volatility`, and `high_revision_risk`

#### v2B-Core market context

The deterministic market-context layer uses `feature_pack_version = "v2b_core_market_context"` and adds:

- `market_context_pack`
  - rates: `FEDFUNDS`, `DFF`, `DGS2`, `DGS10`
  - Japan 10Y: `IRLTLT01JPM156N`
  - FX / risk assets: `USDJPY`, `DXY`, `SPX`, `Gold`, `WTI`
  - snapshot timestamp and lookback windows
  - explicit missing-field reporting
  - provider source map

Market-context construction must:

- use only data at or before `release_ts`
- sort provider rows explicitly before selecting snapshots
- derive `24h` and `5d` changes deterministically from prior available observations
- exclude VIX, NDX, JP2Y, BOJ policy rate, and US-JP 2Y spread unless separately repaired and validated

### 3A.3 Prompt injection model

For single/member payloads, the feature pack is injected as a compact nested object:

- `feature_pack.historical_context.same_indicator`
- `feature_pack.surprise_pack`
- `feature_pack.revision_pack`
- `feature_pack.family_pack`
- `feature_pack.signal_quality_pack`
- `feature_pack.market_context_pack` when the market-context layer is enabled for the run path or replay path

For batch payloads, the feature pack remains compact and compatible through member-level `historical_context_same_indicator` views rather than raw historical tables, and the market context pack remains deterministic and replay-safe.

Historical context is supporting context only. It must not be treated as a mechanical forecast override, and `partial` / `cold_start` should reduce confidence.

The current live planner now makes that confidence reduction explicit through `scenario_confidence`. The calibration remains deterministic and schema-preserving: it uses already available signals such as `history_quality`, `batch_anchor_mode`, `batch_anchor_confidence`, consensus presence, and hidden-detail risk to lower conviction when the payload is structurally incomplete or ambiguous. Market context may be present in the prompt, but it must remain decision-support context only and not become a routing or weighting mechanism.

### 3A.4 Public inspection entrypoint

The project exposes:

- `debugHistoricalContextForEvent(eventId)`

This public wrapper computes and returns the feature pack for one Event row without provider calls and without mutating `Event` or `Predictions`.

### 3A.5 Current feature-pack stack

The live runner now builds a deterministic feature stack before provider prompting:

- `feature_pack_version = "v2a_core_context"` for the current same-event context layer
- `surprise_pack`: prior-event surprise history against consensus
- `revision_pack`: revision instability / risk placeholder when exact revision history is unavailable
- `family_pack`: deterministic family-level memory using existing family classification and outcome-ledger evidence
- `signal_quality_pack`: reproducible quality / forecastability proxy based on cold-start, history depth, consensus availability, surprise volatility, and revision risk
- `feature_pack_version = "v2b_core_market_context"` for the replay-safe market / rate context layer
- `market_context_pack`: FRED, EODHD, and FMP market context snapshots available at or before `release_ts`

Feature-pack rules:

- All fields must be deterministic, reproducible, timestamped where relevant, versioned, and rebuildable.
- No free-form qualitative narrative should be introduced into the feature pack itself.
- Market-context construction must not rely on post-release rows or AI-generated interpretations.
- The market layer must not use proxy symbols for VIX, NDX, JP2Y, BOJ policy rate, or US-JP 2Y spread.

## 3B) Aggregate Provider View

### 3B.1 Purpose

The project now exposes a deterministic aggregate layer over existing provider rows:

- `buildPredictionAggregateForEvent(eventId)`

This does not replace provider predictions. It summarizes agreement/disagreement for one `event_id`.

### 3B.2 Reporting posture

The aggregate layer is decision-support only. It should remain framed as an aggregate provider view with reaction bias, disagreement, whipsaw risk, and confidence rather than a final trading signal.


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
- Converts selected Events into resumable work units before provider execution.
- Can checkpoint partial progress and resume across multiple Apps Script executions.
- Can auto-schedule a one-off continuation trigger when a run ends partial.
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
- PRED_WINDOW_ENABLED truthy
- PRED_WINDOW_FROM_LOCAL and PRED_WINDOW_TO_LOCAL valid
- PRED_WINDOW_TZ set or defaults to script timezone

Then window is replaced with derived UTC ISO range.

Legacy fallback:

- Shared `WINDOW_ENABLED`, `WINDOW_FROM_LOCAL`, `WINDOW_TO_LOCAL`, `WINDOW_TZ` are only used if the dedicated `PRED_WINDOW_*` keys are absent.

If parsing fails or required local-window fields are missing:

- the runner throws an operator-visible validation error instead of silently reverting to the rolling window.

### 5.3A Resumable execution model

The prediction runner no longer assumes one execution can finish a large window.

Work-unit model:

- `single` Event rows become one work unit each
- `member` Event rows become one work unit each
- each provider batch aggregate row is emitted by a separate `batch` work unit after the final member of that batch

Runtime controls:

- `PRED_MAX_WORK_UNITS_PER_RUN` caps work units per execution
- the runner also enforces an internal max runtime budget and exits early before the Apps Script execution ceiling

Checkpointing:

- resume state is stored in Apps Script Script Properties
- property key: `PREDICTION_RESUME_CHECKPOINT_V1`
- stored fields include:
  - effective UTC prediction window
  - prediction mode
  - enabled providers and models
  - last completed work-unit key
  - resume request payload

Resume semantics:

- if the current run matches the saved checkpoint signature, `resumed_from_checkpoint = true` and execution starts at the next unfinished work unit
- if the window, provider set, or prediction mode changes, the checkpoint is ignored and execution starts from the beginning

Auto-continuation:

- partial runs may schedule a one-off time trigger for `runPredictionsResume_()`
- trigger creation is controlled by `PRED_AUTO_CONTINUE_ENABLED`
- delay is controlled by `PRED_AUTO_CONTINUE_DELAY_MIN`
- old continuation triggers are cleared at the start of a run to avoid duplicate chains
- full completion clears both checkpoint and continuation triggers

Run-summary semantics:

- `resume_active = true` means work still remains after the current pass
- `resumed_from_checkpoint = true` means this pass started from a previously saved checkpoint
- `Prediction run checkpoint summary` means the current pass intentionally handed off remaining work to auto-resume

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

### 5.6 Provider Prompt Construction

The current uploaded prediction runner does not compute or persist a separate deterministic `feature_pack`.

Instead, prompt construction is provider-agnostic at the payload level and provider-specific at the transport level:

- the runner builds a strict JSON payload from Event-row metadata
- the payload is paired with a compact instruction contract describing:
  - consensus vs previous-value discipline
  - direct vs indirect USDJPY transmission logic
  - hidden-detail conservatism
  - output-key requirements

For concrete event predictions, the payload includes:

- `schema_version`
- `object = "econ_event"`
- `country`
- `indicator_name`
- `genre`
- `importance`
- `release_ts`
- `consensus_value`
- `prev_revision`
- `fx_pair`
- policy and required-output blocks

For batch predictions, the payload includes:

- `object = "econ_event_batch"`
- `batch_id`
- `country`
- `release_ts`
- `member_count`
- `members[]` with compact member metadata
- `anchor_selection` with mode/confidence/score/margin/reason trace
- `anchor_member` only when the selector finds a clear usable anchor
- `supporting_members` for the remaining batch members
- batch-level policy and required-output blocks

If `anchor_selection.mode` is `weak_anchor` or `no_clear_anchor`, provider prompts and guardrails treat the batch as scenario/watchlist planning rather than forcing a dominant member. Weak anchors remain stored as trace metadata, but they are not passed as the default `anchor_member`; only `clear_anchor` may become the model's default market focus. Same-family release clusters with multiple plausible drivers, such as monthly labor or ISM PMI/subcomponent groups, remain scenario-oriented unless one member has a clear scoring margin.

Scenario watchlists can use release-family profiles instead of raw generic score order. The first implemented profile is `ism_services`: it treats `Prices`, `New Orders`, `Business Activity`, and `Employment` as the structural watch members, with headline PMI kept as context when those subcomponents exist. `monthly_labor` now also has a structural watch profile: headline NFP, unemployment rate, wages, manufacturing payrolls, and private payrolls are watched together when the anchor margin is weak. `jobless_claims` similarly watches initial claims, continuing claims, and the 4-week average as one family. `factory_orders` watches `Factory Orders ex Transportation`, headline `Factory Orders`, and `ex Defense` in that order so the core orders read is not lost inside the broader headline. `macro_inflation_retail` now watches core CPI, headline CPI, retail sales MoM, retail sales ex-autos / ex-gas-autos, retail sales YoY, and CPI s.a. so same-minute inflation-plus-retail pileups are represented as one macro watch object. `cftc_positions` now acts as a low-signal positions profile: it uses a small representative watchlist led by S&P 500, Nasdaq 100, gold, silver, and crude oil positioning, while forcing low risk / low volatility / low confidence because the cluster is indirect and noisy for USDJPY. `eia_petroleum` now treats distillate production, refinery activity, crude stocks, gasoline stocks, gasoline production, distillate stocks, and Cushing crude oil stocks as the structural watch members so large weekly petroleum batches do not overfocus on imports-only rows and can still catch storage-location stress when there is no clear anchor. `mba_mortgage` now watches purchase index, market index, refinance index, and the 30-year mortgage rate so mortgage-demand detail is not lost inside the broader weekly rate package.

Provider-specific extension:

- Anthropic attaches an additional large static reusable scaffold to the cached system block.
- That scaffold is not a canonical stored entity and does not create a separate feature warehouse.

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
- system + user (payload + contract)

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

- rationale_short must reference or align with signals actually present in the payload and instruction contract.

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

#### Config-window actuals run

- Menu → Actuals → Fetch Actuals (Config Window) → menuActualsConfigWindowFetch_()
  - Default fallback: look back 24h, no lookahead, cap 2000
  - If resolveWindow_('actuals_manual') exists and returns an enabled window, it delegates to runFetchActualsWindowBounds_(fromUtcIso, toUtcIso, cap) with exact Config-derived UTC bounds.
  - If no Config window is enabled, it delegates to runFetchActualsWindow_(24*60, 0, cap)

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

runFetchActualsWindowBounds_(windowStartIso, windowEndIso, rowCap):

- Uses the exact supplied UTC bounds.
- Does not widen historical Config windows to now.

For each row, it determines:

- indicator_name
- release_status (prefers release_status; if missing, falls back to status)
- release_ts parsed into a Date (invalid dates are skipped)

It applies two major gates:

#### Gate A — skip explicit text/non-fetchable events upfront

If _shouldSkipActuals_(indicator_name) returns true, the row is skipped and an info log is written:

- Actuals: skipped_by_rule (includes event_id, indicator_name, country, skip_reason)

This gate is keyword/pattern based for clearly text-like releases such as speeches, minutes, testimony, statements, press conferences, and WASDE-style report text. Auction rows and `CB Employment Trends Index` are no longer auto-skipped by name alone.

#### Gate B — time window + status rules

A row is selected as a candidate when:

If status is scheduled:

- release_ts in [lo, hi]

If status is released or revised:

- release_ts in [lo, hi]

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

### 9.2 Critical dependencies

Market Reaction scoring depends on:

- `fx_candle_provider.js` for `getFxCandlesForWindow_()` / `getFxCandlesForWindowByProvider_()`
- the shared logger hook `log_`

In the current repo, the candle-fetch layer is present and maintained. The supported USD/JPY provider roles are:

- `tiingo` — primary scorer
- `eodhd` — first verification provider
- `massive` — provider 3 fallback / arbitration provider
- `twelvedata` — provider 4 backup when provider 3 is unavailable

The scorer is no longer modeled as an unconditional “query all compare providers” workflow. It now uses staged arbitration:

1. fetch `tiingo`
2. fetch `eodhd`
3. stop if they agree closely enough
4. otherwise fetch provider 3
5. fetch provider 4 only if provider 3 is unavailable

Agreement tolerance is code-authoritatively:

- same direction
- anchor delta `<= 1` minute
- pip delta `<= 3`

### 9.3 Core computation: _computeUsdJpyMove_()

Signature:

- _computeUsdJpyMove_(releaseTsUtc, preMin, postMin, horizonMin, meta)

Behavior:

Fetch candles:

- out = getFxCandlesForWindow_('USD/JPY', releaseTsUtc, preMin||30, postMin||120)

If out.candles is missing/empty:

- logs `no_candles` or `market_closed` via `log_` (if present)
- returns `{ status: 'market_closed' }` when the timestamp falls in the normal FX weekend closure window
- otherwise returns `{ status: 'no_candles' }`

Find base candle (t0):

- t0 = releaseTsUtc.getTime()
- base = _nearestAtOrBefore_(out.candles, t0)

If missing:

- returns `{ status: 'market_closed' }` when the timestamp falls in the normal FX weekend closure window
- otherwise returns `{ status: 'no_base' }`

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

For each eligible row it now delegates to staged provider arbitration through:

- `_computeMarketReactionWithFallbacks_(...)`

which internally uses `_computeUsdJpyMove_(...)` for each consulted provider.

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

- `_computeMarketReactionWithFallbacks_(...)`

Internally this:

- scores with `MR_PRIMARY_PROVIDER` (default `tiingo`)
- verifies with `MR_COMPARE_PROVIDER` (intended `eodhd`)
- escalates to `MR_COMPARE_PROVIDER_2` only when the first pair disagree materially
- uses `MR_COMPARE_PROVIDER_3` only when provider 3 is unavailable

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
- Fetch Actuals (Config Window) → menuActualsConfigWindowFetch_()  

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

- Handler function: menuActualsConfigWindowFetch_()  
- Frequency: every 1 hour  
- De-duplication: before creating, it deletes any existing triggers whose handler is the same menuActualsConfigWindowFetch_(), and also removes legacy menuActualsManualFetch_() triggers

menuActualsStopHourly_() removes triggers:

- Deletes all triggers whose handler is menuActualsConfigWindowFetch_() or legacy menuActualsManualFetch_()  
- Toasts how many were removed  

Important implication (code-authoritative):

The automation does not schedule runFetchActualsHourly_() (even though that function exists in actuals_fetcher.gs).

The scheduled automation path is:

trigger → menuActualsConfigWindowFetch_() → runFetchActualsWindowBounds_(...) when Config is enabled, otherwise runFetchActualsWindow_(...).

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

#### Spreadsheet tab: Config (key/value overrides)
Both `prediction_runner.gs` and `market_scoring.gs` read Config!A:B overrides.  
Prediction Runner uses it for provider and window controls; Market Reaction uses it for provider arbitration and reaction-window controls.

Supported prediction-specific keys include:

- PREDICTION_MODE = LIVE | BACKTEST
- BACKTRACK is accepted as an alias for BACKTEST
- In LIVE mode, rows with existing actuals markers on Event are skipped
- In BACKTEST mode, those rows remain eligible for selection
- PREDICTION_TEMPERATURE = numeric sampling control
- PREDICTION_SEED = integer seed for provider requests
- PRED_MAX_WORK_UNITS_PER_RUN = work-unit cap per execution
- PRED_RESUME_ENABLED = enables checkpoint-based resume
- PRED_AUTO_CONTINUE_ENABLED = enables one-off continuation trigger after partial runs
- PRED_AUTO_CONTINUE_DELAY_MIN = minutes before continuation trigger fires
- ANTHROPIC_PROMPT_CACHE_ENABLED = enables Anthropic prompt caching
- ANTHROPIC_PROMPT_CACHE_TTL = Anthropic cache TTL hint (`5m` default, `1h` optional)
- PRED_WINDOW_ENABLED / PRED_WINDOW_FROM_LOCAL / PRED_WINDOW_TO_LOCAL / PRED_WINDOW_TZ for prediction-only windowing
- Legacy shared `WINDOW_*` values are used only as fallback by the prediction runner

External automation runner controls:

- `--heavy-day-mode auto`: default; preflight Event clusters and switch heavy days into release-window prediction chunks
- `--heavy-day-mode force`: always use release-window prediction chunks for day-run predictions
- `--heavy-day-mode recovery`: try the normal window first, then use release-window recovery after transport timeout
- `--heavy-day-mode off`: preserve the old full-window prediction orchestration
- `--skip-predictions`: run post-prediction phases without repeating provider calls

These are local runner controls, not Apps Script sheet configuration keys.

Supported market-reaction keys include:

- `MR_PRIMARY_PROVIDER`
- `MR_COMPARE_PROVIDER`
- `MR_COMPARE_PROVIDER_2`
- `MR_COMPARE_PROVIDER_3`
- `MR_WINDOW_ENABLED`
- `MR_WINDOW_FROM_LOCAL`
- `MR_WINDOW_TO_LOCAL`
- `MR_WINDOW_TZ`
- `MR_HORIZON_MIN`
- `MR_ANCHOR_MIN_ABS_MOVE_PIPS`
- `MR_ANCHOR_LOOKBACK_MIN`
- `MR_ANCHOR_LOOKAHEAD_MIN`
- `MR_FLAT_MAX_ABS_PIPS`
- `MR_SKIP_ALREADY_SCORED`

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
CFG.GEMINI_MODEL = 'gemini-2.5-flash-lite'  
CFG.OPENAI_MODEL = 'gpt-4o-mini'  
CFG.CLAUDE_MODEL = 'claude-haiku-4-5'  

#### Window defaults
CFG.WINDOW_MIN_BEFORE_MIN = 24*60  
CFG.WINDOW_MAX_AFTER_MIN = 36*60  

#### Other prediction defaults
CFG.DEFAULT_FX = 'USDJPY'  
CFG.PRED_MAX_WORK_UNITS_PER_RUN = 12
CFG.PRED_RESUME_ENABLED = true
CFG.PRED_AUTO_CONTINUE_ENABLED = true
CFG.PRED_AUTO_CONTINUE_DELAY_MIN = 1
CFG.ANTHROPIC_PROMPT_CACHE_ENABLED = true
CFG.ANTHROPIC_PROMPT_CACHE_TTL = '5m'
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
PRED_WINDOW_ENABLED (true/false)  
PRED_WINDOW_FROM_LOCAL (e.g., YYYY-MM-DD HH:mm or a Date cell)  
PRED_WINDOW_TO_LOCAL  
PRED_WINDOW_TZ (IANA, e.g., Asia/Tokyo)  

Legacy fallback keys:

WINDOW_ENABLED  
WINDOW_FROM_LOCAL  
WINDOW_TO_LOCAL  
WINDOW_TZ  

If the local window override is enabled but parsing fails, the runner now throws an operator-visible validation error rather than silently falling back.

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

Trigger (config window): Menu → ③ Actuals → Fetch Actuals (Config Window)  
Trigger (automation): Menu → ③ Actuals → Start Hourly Actuals Fetch  
(creates trigger that calls menuActualsConfigWindowFetch_() hourly)

Worker: runFetchActualsWindowBounds_(...) for enabled Config windows, otherwise runFetchActualsWindow_(...) in actuals_fetcher.gs

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
Actuals Config Window fetch (or start hourly)  
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
system: [{ type:"text", text: <static reusable scaffold>, cache_control?: { type:"ephemeral", ttl? } }]  
messages: [{ role:"user", content:[{ type:"text", text: <event-specific JSON payload> }] }]  

Implementation note:

- Anthropic is the only provider path currently using provider-side prompt caching.
- The cached block contains the static system/instruction/scaffold text only.
- The event-specific JSON payload remains outside the cached block so reuse can occur across many events.

Usage capture:

usage.input_tokens  
usage.output_tokens  
usage.cache_creation_input_tokens  
usage.cache_read_input_tokens  

Prediction rows store provider cache counters in `cache_creation_input_tokens` and `cache_read_input_tokens` when the provider response exposes them. For Anthropic, non-zero `cache_read_input_tokens` indicates the reusable static block was read from provider-side prompt cache.

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

Config-window actuals uses resolveWindow_('actuals_manual') when enabled and executes with exact absolute bounds. Historical windows do not widen to "from Config start through now."

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
Menu → ③ Actuals → Fetch Actuals (Config Window)  

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

A time-based trigger that runs menuActualsConfigWindowFetch_() hourly.

To disable:

Menu → ③ Actuals → Stop Hourly Actuals Fetch  

Operational notes:

Trigger runs in non-UI context, so do not rely on popups.  
Verify by checking the log sheet for actuals run messages (best effort; may be incomplete).  
If SeriesMap is not maintained, the trigger can still resolve many rows through the direct FMP path; only fallback-only cases will remain unresolved due to “No SeriesMap match.”  

### 18.3A Local heavy-day day-run automation

The local Python runner supports adaptive day-run orchestration for historically heavy days. Before prediction, it can read the selected `Event` window and group events by release timestamp. A day is treated as heavy when same-time clusters are large, mixed across several genres/families, or have high estimated provider-row load.

When heavy-day mode is active, predictions are executed one release timestamp window at a time. Each release window runs providers one at a time first, using the existing prediction checkpoint/resume mechanism within that window. This is intended to avoid all-provider transport stalls while preserving the same provider prompts, strict JSON contract, `(event_id, ai_name)` upsert identity, batch/member semantics, and decision-support wording.

Operational note:
- Local runner default Apps Script HTTP timeout is `300` seconds.
- If an Apps Script prediction call times out locally, the runner may recheck `Predictions` coverage for that exact release window/provider set before treating the window as failed.
- Release clusters with `event_count >= 4` or `member_count >= 4` should start in provider-split-first mode to reduce combined-call stalls.

After prediction windows complete, the runner may run actuals, market reaction, and evaluation for the requested full day/window. If those post-prediction phases need to be retried, use `--skip-predictions` so provider predictions are not repeated.

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
menuActualsConfigWindowFetch_  
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
