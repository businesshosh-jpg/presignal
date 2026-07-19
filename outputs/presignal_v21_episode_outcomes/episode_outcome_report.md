# Deterministic Episode and Outcome Layer

## Decision

`V2_1_DETERMINISTIC_EPISODE_AND_OUTCOME_LAYER_VALIDATED`

Roles use pre-release importance rank (`high > medium > low > unknown`) and canonical member order. USD/JPY observations come only from the approved read-only historical endpoint in UTC daily windows. Missing or stale required prices produce contract-valid `UNAVAILABLE` Outcomes; the availability ledger distinguishes `PARTIAL` coverage.

- Episodes: 1682
- Component roles: {'PRIMARY_COMPONENT': 1682, 'SECONDARY_COMPONENT': 820, 'SUPPORTING_COMPONENT': 1812}
- Outcome terminal dispositions: {'AVAILABLE': 1574, 'PARTIAL': 72, 'UNAVAILABLE': 36}
- Market-data daily calls in this build: 0
- Cached UTC days: 265
- Outcome population fingerprint: `sha256:8e8cfe4fdd8ecbbeb6e9ae2ca1e75c5e0e3466f95e0ed05e6abd9fac79f23f6a`
