# PreSignal v2.1 Event-Path Contract v1

`presignal_event_path_contract_v1` freezes the v2.1 scientific data contract at schema version `2.1.0`. It inherits v2.0 provider/model lineage, cutoff, Pack identity, no-signal lineage, USD/JPY pip convention, UTC lineage, and the one-pip FLAT threshold. It changes the primary object from Market Session to Event Episode and the primary endpoint to `EPISODE_REACTION_DIRECTION_15M`.

## Scope

An Episode is one standalone scheduled catalyst or one coherent same-time release cluster. A Market Session is only a container and derived Session Map. It is not a v2.1 prediction target, Outcome, or primary endpoint.

`event_id` remains preserved source lineage. The committed Event population proves it is not globally unique, so contract consumption uses a deterministic immutable Event-row locator without changing Event IDs. Valid `batch_id` remains the inherited cluster identity. Unbatched same-minute rows are separate Episodes unless a valid same-minute batch binds them.

## Frozen Rules

- Information arms: `BASELINE` and `FULL_CONTEXT` only.
- Path horizons: 5, 15, 30, and 60 minutes, in that exact order.
- FLAT: absolute USD/JPY move strictly below 1.00 pip.
- Outcome anchor: the latest accepted close at or before release, at most 60 seconds stale.
- Horizon price: accepted close at or before the exact UTC horizon, at most 60 seconds stale. Missing data fails closed as `UNAVAILABLE`.
- Pip calculation: `(horizon_price - anchor_price) / 0.01`, rounded to two decimals.
- Reversal: earliest later required horizon opposite to the first established non-FLAT direction.
- Intervening Episodes: flagged, not automatically excluded in v1.
- Valid no-signal: all four realized horizons are FLAT and maximum absolute excursion is below one pip.
- Atomicity: every normal Prediction has exactly four Path rows; valid no-signal and provider-error records have none.

The contract validator is deterministic and does not execute runtime behavior. The workbook reconciliation is deliberately advisory: any future sheet amendment must be reviewed separately.
