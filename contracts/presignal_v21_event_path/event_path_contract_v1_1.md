# PreSignal v2.1 Event-Path Contract v1.1

`presignal_event_path_contract_v1_1` freezes the v2.1 scientific data contract at schema version `2.1.1`. It inherits v2.0 provider/model lineage, cutoff, Pack identity, no-signal lineage, USD/JPY pip convention, UTC lineage, and the one-pip FLAT threshold. It changes the primary object from Market Session to Event Episode and the primary endpoint to `EPISODE_REACTION_DIRECTION_15M`.

## Scope

An Episode is one standalone scheduled catalyst or one coherent same-time release cluster. A Market Session is only a container and derived Session Map. It is not a v2.1 prediction target, Outcome, or primary endpoint.

`event_id` remains preserved source lineage. The committed Event population proves it is not globally unique, so contract consumption uses a deterministic immutable Event-row locator without changing Event IDs. Valid `batch_id` remains the inherited cluster identity. Unbatched same-minute rows are separate Episodes unless a valid same-minute batch binds them.

## Frozen Rules

- Information arms: `BASELINE` and `FULL_CONTEXT` only.
- Path horizons: 5, 15, 30, and 60 minutes, in that exact order.
- Immediate Impulse is a separate sidecar with a default maximum observation window of 120 seconds.
- FLAT: absolute USD/JPY move strictly below 1.00 pip.
- Outcome anchor: the latest accepted close at or before release, at most 60 seconds stale.
- Horizon price: accepted close at or before the exact UTC horizon, at most 60 seconds stale. Missing data fails closed as `UNAVAILABLE`.
- Pip calculation: `(horizon_price - anchor_price) / 0.01`, rounded to two decimals.
- Early Reaction at T+5 is preserved but no longer defines the strict initial move.
- Reversal: earliest later required horizon opposite to the first established non-FLAT direction.
- Intervening Episodes: flagged, not automatically excluded in v1.
- Valid no-signal: all four realized horizons are FLAT and maximum absolute excursion is below one pip.
- Atomicity: every normal Prediction has exactly four Path rows; valid no-signal and provider-error records have none.

## Immediate Impulse Clarification

- `early_reaction_5m_direction` is the explicit persisted `EARLY_REACTION_5M` forecast field for Contract v1.1.
- Immediate Impulse is forecast separately through `immediate_impulse_*`.
- Under the current governed historical USD/JPY path, ordered one-minute closes support `APPROXIMATION_ONLY`, not a strict tick-accurate first-move scorer.
- The primary endpoint remains `EPISODE_REACTION_DIRECTION_15M`.

The contract validator is deterministic and does not execute runtime behavior. The workbook reconciliation is deliberately advisory: any future sheet amendment must be reviewed separately.
