# Immediate Impulse Outcome Recovery R1

## Scope

This compact contract is an additive supplement for bounded Immediate Impulse
Outcome recovery work after the completed PreSignal v2.1 Pure Prediction
Historical Baseline Round 1 run.

It does not replace:

- `presignal_event_path_contract_v1_1`
- the completed Round 1 forecast records
- the completed T+5 / T+15 / T+30 / T+60 Outcomes
- the completed T+15 primary evaluation

## Contract identity

- `contract_version = presignal_immediate_impulse_outcome_recovery_r1`
- `schema_version = 1.0.0`
- schema id:
  - `presignal.immediate_impulse_outcome_recovery.r1`
  - `presignal.immediate_impulse_detector_parameters.r1`

## Scientific hierarchy

- Primary endpoint remains `T+15 USD/JPY directional accuracy`
- Immediate Impulse is a secondary measurement only
- T+5 remains `EARLY_REACTION_5M`

## Measurement separation

The following must remain distinct:

1. Pre-release movement:
   - `T-10m` and `T-5m` through immediately before `T`
2. Event-impact anchor:
   - preferred `median valid midpoint` from `T-10s` through `T-2s`
   - fallback `last valid midpoint strictly before T`
3. Immediate Impulse:
   - first meaningful persistent movement detected only inside
     `T` through `T+120 seconds`

Pre-release movement must never be classified as Immediate Impulse.

## Preferred anchor

- `anchor_method = MEDIAN_VALID_MIDPOINT_T_MINUS_10S_TO_T_MINUS_2S`
- fallback `anchor_method = LAST_VALID_MIDPOINT_STRICTLY_BEFORE_T`
- `anchor_fallback_reason` must be blank for the preferred method
- `anchor_fallback_reason` must be nonblank for the fallback method

## Immediate Impulse definition

Immediate Impulse is not:

- `price(T+120s) - price(T)`

Immediate Impulse is:

- the first post-release directional movement that crosses a frozen
  meaningful-magnitude threshold and persists for a frozen minimum
  duration inside `T` through `T+120 seconds`

## Detector parameter names

The compact supplement records detector parameters without freezing the final
 numeric threshold values in this move.

Required parameter names:

- `minimum_move_pips`
- `minimum_persistence_seconds`
- `directional_retention_pips`
- `maximum_temporary_violations`
- `maximum_detection_window_seconds`

Frozen constant:

- `maximum_detection_window_seconds = 120`

## Outcome statuses

- `STRICT_AVAILABLE`
  - ordered sub-minute observations are sufficient for a duration-based detector
- `RESOLUTION_LIMITED`
  - observations exist but do not support the full strict detector without lossy assumptions
- `APPROXIMATION_ONLY`
  - only one-minute or similarly coarse observations are available
- `OUTCOME_UNAVAILABLE`
  - no valid recovery-quality observation set exists

## Direction values

- `UP`
- `DOWN`
- `FLAT`
- `UNAVAILABLE`

## Market-data resolution classes

- `TICK`
- `SECOND`
- `FIVE_SECOND`
- `ONE_MINUTE_OHLC`
- `OTHER_LIMITED`

## Required fields

- `episode_id`
- `forecast_id`
- `provider`
- `model`
- `pack_arm`
- `release_timestamp`
- `market_data_source`
- `market_data_resolution`
- `observation_start_timestamp`
- `observation_end_timestamp`
- `observation_count`
- `raw_observation_artifact_reference`
- `anchor_method`
- `anchor_fallback_reason`
- `anchor_timestamp`
- `anchor_price`
- `detector_parameters`
- `immediate_impulse_status`
- `immediate_impulse_direction`
- `immediate_impulse_start_timestamp`
- `immediate_impulse_threshold_cross_timestamp`
- `immediate_impulse_peak_timestamp`
- `immediate_impulse_peak_pips`
- `immediate_impulse_adverse_pips`
- `immediate_impulse_persistence_seconds`
- `immediate_impulse_reversed_by_120s`
- `net_move_at_120s_pips`
- `net_direction_at_120s`
- `contract_version`
- `schema_version`
- `evaluator_version`
- `generated_timestamp`

## Validation rules

- fail closed on missing or extra fields
- `anchor_timestamp` must be strictly before `release_timestamp`
- `immediate_impulse_*` timestamps must not precede `release_timestamp`
- `pack_arm` must be `BASELINE` or `FULL_CONTEXT`
- `maximum_detection_window_seconds` must equal `120`
- `STRICT_AVAILABLE` requires sub-minute resolution
- `APPROXIMATION_ONLY` is the expected status for `ONE_MINUTE_OHLC`
- `OUTCOME_UNAVAILABLE` requires:
  - `immediate_impulse_direction = UNAVAILABLE`
  - `net_direction_at_120s = UNAVAILABLE`
  - all detector-result fields null

## Failure-closed behavior

- no missing field may be defaulted silently
- no pre-release move may be reclassified as post-release Immediate Impulse
- no provider-owned Round 1 forecast field may be rewritten
- no original Round 1 Outcome or evaluation record may be mutated
- any future supplement must be additive and lineage-linked to the frozen Round 1 evidence
