# Event Lineage Repair and Episode Rebuild

## Decision

`V2_1_EVENT_LINEAGE_REPAIR_AND_EPISODE_REBUILD_VALIDATED`

The repair changes only audited Event cells: 48 stale inherited batch identities are repartitioned with the legacy country-plus-UTC-minute rule, and four raw Event-ID collisions receive deterministic SHA-256 lineage extensions. The 17 collateral batch members remain active because audit evidence shows they are unique catalysts, not duplicate physical observations. Excel row 4316 remains excluded as the corrupt duplicate of row 2460.

## Rebuild

- Old Episode population: 1668 Episodes, 4245 consumed rows, 70 exclusions.
- New Episode population: 1682 Episodes, 4314 consumed rows, 1 exclusion.
- Recovered memberships: 14 newly valid cluster Episodes.

No frozen contract, provider, market-data, Apps Script, Google Sheets, or production routing behavior changed.
