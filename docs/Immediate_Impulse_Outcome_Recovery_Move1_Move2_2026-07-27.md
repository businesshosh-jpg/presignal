# Immediate Impulse Outcome Recovery R1

Date: Monday, July 27, 2026

## Scope

This note freezes:

1. a compact additive Immediate Impulse Outcome contract
2. a call-free audit of the existing historical USD/JPY acquisition path

It does not authorize:

- provider forecasts
- Round 1 forecast reruns
- modification of completed Round 1 evidence
- detector implementation
- Google workbook writes
- new external data-source integration

## Compact contract decision

The compact supplement contract is frozen as:

- contract id: `presignal_immediate_impulse_outcome_recovery_r1`
- schema version: `1.0.0`
- Outcome schema id: `presignal.immediate_impulse_outcome_recovery.r1`
- detector schema id: `presignal.immediate_impulse_detector_parameters.r1`

Maximum detection window is frozen at:

- `maximum_detection_window_seconds = 120`

The supplement is additive only. It does not replace the frozen
`presignal_event_path_contract_v1_1` records that power the completed
May-July 2024 Round 1 baseline.

## Existing Round 1 market-data route

The current historical Outcome path is local and repository-backed:

1. `automation/build_presignal_v21_episode_outcomes_v1_1.py`
   - calls `endpoint_request(...)`
   - which calls Apps Script function
   - `apiFetchGovernedHistoricalUsdJpyObservation`
2. `apps_script/historical_market_data_endpoint.js`
   - validates a UTC time request
   - tries providers in order:
     - `tiingo`
     - `eodhd`
     - `massive`
     - `twelvedata`
   - returns raw historical observations
3. `ObservationIndex` and `outcome_record(...)`
   - select anchor and horizon observations
   - build T+5 / T+15 / T+30 / T+60 Outcome fields
4. `prepare_presignal_v21_historical_baseline_prevalidation_v1_1.py`
   - converts legacy `2.1.0` Outcomes into `v1_1`
   - marks Immediate Impulse as `APPROXIMATION_ONLY`

## What supplied Round 1 one-minute data

Repository evidence from:

- `outputs/presignal_v21_pure_prediction_historical_baseline/PPHB-R1-PREVALIDATION-20260726T090136Z-254f4ac151673853e5c7/outcomes_v1_1/market_data_lineage.jsonl`

shows:

- selected provider for the validation sample: `tiingo`
- request window: whole UTC day
- returned observations: minute-aligned close prices
- stored selected observations:
  - anchor
  - `5m`
  - `15m`
  - `30m`
  - `60m`

The existing full Round 1 baseline used the same legacy line of minute-resolution
Outcome evidence converted into `v1_1`.

## Exact request parameters found in code

Apps Script request validation supports:

- `instrument = USD/JPY`
- `timezone = UTC`
- either:
  - `requested_timestamp`
  - or explicit `requested_window_start` / `requested_window_end`

Current provider-specific requests are hard-coded to one-minute granularity:

- `tiingo`
  - `resampleFreq=1min`
- `eodhd`
  - `interval=1m`
- `massive`
  - `/range/1/minute/`
- `twelvedata`
  - `interval=1min`

## Existing endpoint capability proven by repository evidence

The existing endpoint and acquisition route can currently prove:

- historical May-July 2024 coverage exists for one-minute observations
- UTC window requests are supported
- immutable raw observations can be persisted locally
- provider raw timestamps are preserved alongside normalized timestamps
- only OHLC-style observations are accepted
- `accepted_raw_price_field` is currently `close`

The current route does not prove:

- tick observations
- bid/ask quotes
- midpoint-native observations
- one-second bars
- five-second bars
- sub-minute pagination or retention behavior

## Timestamp and precision findings

### Endpoint level

`historical_market_data_endpoint.js`:

- normalizes provider timestamps to ISO UTC strings
- preserves `provider_returned_timestamp_raw`
- returns observation timestamps with millisecond string formatting

### Python acquisition level

`build_presignal_v21_episode_outcomes_v1_1.py`:

- rewrites accepted timestamps through `iso(...)`
- that helper strips microseconds
- current cache therefore preserves second precision, not sub-second precision

This is acceptable for one-minute Outcomes but is a real risk for any strict
Immediate Impulse implementation.

## Anchor and Outcome behavior today

The current Outcome builder uses:

- `latest_accepted(observations, release)` for the anchor
- this means nearest valid observation at or before `release_ts`
- not the preferred robust pre-release median midpoint

The current Immediate Impulse sidecar:

- scans observations inside `T` through `T+120s`
- sets `SUPPORTED` only if any timestamp is not minute aligned
- otherwise sets `APPROXIMATION_ONLY`
- uses the current anchor close
- does not implement a duration-based threshold detector

This confirms that the repository already distinguishes:

- approximation behavior
- strict behavior

but has not yet implemented the strict detector.

## Capability decision

Decision:

- `EXISTING_SOURCE_SUPPORTS_RESOLUTION_LIMITED_IMPULSE`

Evidence:

- the current deployed route and local builder are hard-coded to one-minute requests
- the accepted Round 1 evidence used only one-minute close-based observations
- the current route can request a narrow UTC window, so a future supplement can
  acquire `T-10m` through `T+120s`
- but the currently proven output remains coarse OHLC-style observations, not a
  strict sub-minute event stream

Important distinction:

- the repository does **not** prove that the upstream vendors cannot provide
  finer resolution
- it proves only that the current accepted endpoint and local implementation do
  not currently request or preserve such resolution

## Requested audit answers

1. Round 1 one-minute source:
   - local legacy Outcome lineage converted into `v1_1`
   - validation sample selected provider: `tiingo`
2. Exact request parameters:
   - UTC day windows in existing lineage
   - one-minute request parameters in the Apps Script endpoint
3. Minimum historical resolution supported by the current route:
   - one-minute OHLC
4. Tick / bid / ask / midpoint / one-second / five-second:
   - not proven by current route
5. Historical coverage for May 1 through July 31, 2024:
   - proven for one-minute observations
6. Timestamp precision returned:
   - endpoint returns normalized UTC timestamps with millisecond string format
   - local cache keeps second precision
7. Timestamp origin:
   - provider raw timestamp plus normalized UTC timestamp
8. Price types available:
   - OHLC values, accepted field currently `close`
9. Raw sub-minute persistence:
   - possible in principle as local immutable artifacts
   - not currently exercised by accepted code
10. Request `T-10m` through `T+120s`:
   - supported by endpoint request shape
11. Request-size / pagination / retention restrictions:
   - no pagination logic exists in the current endpoint
   - `massive` hard-codes `limit=50000`
   - sub-minute retention and entitlement limits remain unproven
12. Would finer resolution alter existing canonical T+5/T+15/T+30/T+60 Outcomes:
   - it should not if implemented as a separate supplement
13. Can Immediate Impulse be added as a separate supplement without modifying Round 1:
   - yes
14. Timestamp-alignment risks:
   - scheduled release timestamp vs actual release second remains unresolved
   - current baseline is anchored to scheduled release timestamps

## Exact files and functions to modify next move

Smallest likely touch set:

- `apps_script/historical_market_data_endpoint.js`
  - `apiFetchGovernedHistoricalUsdJpyObservation`
  - `_historicalUsdJpyProviderResponse_`
  - `_historicalUsdJpyParseProviderRows_`
- `automation/build_presignal_v21_episode_outcomes_v1_1.py`
  - `endpoint_request`
  - `acquire_daily_observations`
  - `ObservationIndex`
  - `immediate_impulse_sidecar`
  - `outcome_record`
- create a new additive supplement builder rather than rewriting frozen Outcome rows
- `automation/test_historical_market_data_endpoint_v1.py`
- new contract tests for the supplement detector and acquisition path

## Files and artifacts that must remain untouched

- completed Round 1 full run:
  - `outputs/presignal_v21_pure_prediction_historical_baseline/PPHB-R1-FULL-20260726T160036Z-ca5d238916f1/`
- matrix freeze:
  - `outputs/presignal_v21_pure_prediction_historical_baseline/PPHB-R1-FULL-MATRIX-FREEZE-20260726T150529Z-97fd30af6719/`
- prevalidation evidence:
  - `outputs/presignal_v21_pure_prediction_historical_baseline/PPHB-R1-PREVALIDATION-20260726T090136Z-254f4ac151673853e5c7/`
- all validation-run output directories under:
  - `outputs/presignal_v21_pure_prediction_historical_baseline/`
- frozen `v1` contract files
- completed Round 1 forecast, Outcome, evaluation, and pair-comparison rows

## Recommended next bounded move

Recommended next move:

- perform a bounded live capability probe against the existing endpoint using a
  tiny sample of one or two Episodes and a strict `T-10m` through `T+120s`
  window request
- confirm whether any provider can return sub-minute timestamps through the
  current authenticated route
- persist raw observations immutably without altering existing Round 1 evidence

## Readiness

- readiness status:
  - `READY_FOR_BOUNDED_LIVE_SOURCE_CAPABILITY_PROBE`
