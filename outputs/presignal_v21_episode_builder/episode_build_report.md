# Episode Builder Report

- builder: `automation/build_presignal_v21_episodes.py`
- source_workbook: `presignal_main.xlsx`
- source_workbook_sha256: `5cf15d673079a6582655772ae5b69eb3bb56f0bb2f7172e26c8111a8ec6fb85f`
- event_rows: `4315`
- valid_source_rows: `4245`
- episodes: `1668`
- standalone_episodes: `931`
- batch_episodes: `737`
- consumed_rows: `4245`
- duplicate_event_id_values: `144`
- duplicate_event_id_row_excess: `148`
- duplicate_source_row_locators: `0`
- batch_membership_conflicts: `48`
- episode_id_collisions: `0`
- invalid_contract_rows: `0`
- unresolved_lineage_rows: `0`
- determinism: `{'repeated_run': 'PASS', 'input_order_shuffle': 'PASS', 'generated_timestamps_excluded_from_population_fingerprint': True}`
- event_row_locator_rule: `ER_ + SHA-256 canonical JSON of event_id, batch_id, country, indicator_name, UTC release_ts, source_cal, source_provider, source_series_id, type (first 20 hex characters)`
- member_ordering_rule: `release_ts, event_row_locator, indicator_name, event_id`
- episode_population_fingerprint: `sha256:f8d3bc72660ad9e0aaa6fb448508c3bc0e9ef08df83b907e00d6ecdc347d0a2d`
- contract_version: `presignal_event_path_contract_v1`
- schema_version: `2.1.0`

## Frozen Construction Rules

- `event_row_locator` is the frozen SHA-256 adapter over immutable Event lineage attributes; raw `event_id` is preserved but never used as a global key.
- `batch_id` is the only cluster identity. Unbatched singles remain standalone; same-minute singles are never merged.
- Members are ordered by release timestamp, locator, indicator name, then event ID. The first canonical member fills the validator-required primary fields as a structural anchor only; it is not attention or component ranking.
- `forecast_cutoff_ts` equals the Event release timestamp. This is the contract-safe upper availability boundary for an unselected Episode, not a provider forecast cutoff.
- Every generated Episode has `selection_status=PENDING`, `status=VALID`, and an empty `session_id`; no attention, session-map, outcome, or prediction field is derived.

## Dispositions

- CONSUMED: 4245
- EXCLUDED: 70

## Exclusions and Errors

- BATCH_RELEASE_MINUTE_CONFLICT: 48
- DUPLICATE_MEMBER_EVENT_ID: 21
- INVALID_RELEASE_TS: 1
