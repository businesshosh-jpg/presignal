# Episode Exclusion Integrity Audit

## Decision

`TARGETED_EVENT_LINEAGE_REPAIR_REQUIRED`

The 48 stale-batch exclusions and 21 rows blocked by four raw Event-ID collisions are contract-valid today but scientifically unnecessary: existing immutable source fields resolve their identities deterministically. The final malformed timestamp row is scientifically justified as excluded because it is an exact duplicate of Excel row 2460 and consuming it would double-count a release.

## Row Count

The migration count of 4,316 includes header row 1. The builder correctly counts 4,315 non-empty Event data rows, Excel rows 2 through 4316.

## Audit Results

- Batch conflicts: 48 rows in 6 groups, all `STALE_BATCH_ID`.
- Duplicate-member exclusions: 21 rows in 2 batches; 4 raw IDs are `LEGITIMATE_DISTINCT_EVENT_WITH_COLLIDING_EVENT_ID` and the remaining 17 are batch members blocked by those collisions.
- Invalid timestamp: Excel row 4316 has literal `member` in `release_ts`; it otherwise exactly duplicates row 2460.

## Repair Scope

One narrow Event-lineage repair is required before attention selection: partition stale inherited batch identities using the existing country and UTC release minute, and rekey the four colliding raw Event IDs from existing immutable source lineage. Retain the malformed duplicate timestamp row as excluded (or quarantine it in the source lineage) rather than restoring and consuming it. No contract, Episode builder, provider, market-data, or production-routing change is recommended.
