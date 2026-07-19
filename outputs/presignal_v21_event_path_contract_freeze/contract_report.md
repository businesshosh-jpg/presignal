# PreSignal v2.1 Event-Path Contract Freeze

## Decision

`presignal_event_path_contract_v1` is frozen at schema version `2.1.0`. The primary object is a selected Event Episode or coherent same-time Release Cluster. The primary endpoint is `EPISODE_REACTION_DIRECTION_15M`.

This is a new Event-Path hypothesis. It does not reopen the frozen v2.0 conclusion, `INSUFFICIENT_EVIDENCE_OF_PACK_E_IMPROVEMENT`, which remains limited to the Market Session contract.

## Inheritance and Deliberate Changes

The contract inherits provider/model lineage, cutoff discipline, Pack identity, no-signal lineage, UTC time, provider-neutral Outcomes, the USD/JPY `0.01` pip denominator, and the v2.0 one-pip FLAT threshold.

It deliberately changes the primary unit from Market Session to Episode. Its Outcome anchor is the accepted price at the scheduled release, rather than v2.0's reaction-detected anchor. Each T+5/T+15/T+30/T+60 price must be at or before the exact UTC horizon and no more than 60 seconds stale; otherwise the Outcome is `UNAVAILABLE`.

## Episode Identity and Event Duplicates

The committed Event population has 4,315 rows, 144 duplicated `event_id` values, and 148 duplicate-row excess records. All 144 groups are identity collisions across immutable event attributes; none is an exact duplicate or repeated source snapshot.

`event_id` is therefore retained as source lineage, not used as a global primary key. Episode construction must consume Event rows through the frozen immutable `event_record_locator`. A valid inherited `batch_id` binds a same-minute cluster; distinct batches remain distinct Episodes, and unbatched same-minute singles remain separate Episodes.

This records a targeted discrepancy with the frozen v2.0 replay helper, which required unique `event_id` values in its replay member set. The v2.1 adapter is `MODIFIED_FROM_V2_0`; no Event row or identity is changed.

## Path, Outcome, and Evaluation

- Normal Predictions require exactly four ordered Path rows: 5, 15, 30, and 60 minutes.
- Valid `NO_SIGNAL` and `PROVIDER_ERROR` Predictions have zero Path rows; they are distinct states.
- FLAT means absolute realized pips strictly below 1.00.
- Reversal is the earliest later required horizon opposite to the first established non-FLAT direction.
- Intervening Episodes are flagged and remain eligible in v1; they are not automatically excluded.
- A no-signal is correct only when all four realized directions are FLAT and maximum absolute excursion is below one pip.
- The complete-path score is the unweighted mean of available directional correctness values. It is supporting only.

## Workbook Reconciliation

All fields in the frozen Episode (23), Prediction (35), Prediction Path (27), Outcome (35), and Evaluation (27) contracts match the committed `presignal_main.xlsx` headers exactly. No field rename or workbook amendment is required. Arrays and JSON values will be serialized canonically in cells and validated by the contract validator; the header-only workbook deliberately has no embedded runtime validation.

## Validation and Scope

The validator reconstructs deterministic IDs and SHA-256 fingerprints, rejects incomplete/duplicate/unordered paths, enforces A/E compatibility, validates outcome pips and reversal, and fails closed on unavailable states. The test suite passed all valid and negative fixtures.

No provider, market-data, Apps Script, Google Sheets, replay, scoring, workbook, or production operation occurred.
