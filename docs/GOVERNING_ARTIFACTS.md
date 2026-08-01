# Governing Artifacts

This index is a compact pointer to current control boundaries. It does not replace the immutable evidence artifacts.

## AUTHORITATIVE_CURRENT

| Artifact | Scope | Controls | Modification | Superseding artifact |
|---|---|---|---|---|
| `PPHB-R1-FORECAST-EXECUTION-PLAN-20260729T123101Z-14d356fb00c1` | Forecast population and ordering | 564 call identities, provider/model assignments, Pack membership, cutoffs, batch order | Prohibited | Future prompt migration revisions only for unexecuted calls |
| `PPHB-R1-FORECAST-FUTURE-NO-SIGNAL-PROMPT-MIGRATION-20260801T130644Z-2bcc88d1ba5e` | Unexecuted calls | Future prompt version, 45 revised batch manifests, 528 migrated call manifests, dispatch guard | Append-only | Future execution results |
| `automation/execute_presignal_v21_forecast_batch_001.py` | Forecast execution path | Manifest source guard, bounded batches, raw-before-parse, authority and contract checks | Controlled code changes only | None |

## FROZEN_EVIDENCE

| Artifact | Scope | Decision controlled | Modification |
|---|---|---|---|
| `PPHB-R1-PACK-POPULATION-CONSTRUCTION-20260729T113217Z-88b9664e9bd2` | Pack A/E populations | Pack rows, payloads, source lineage | Prohibited |
| `PPHB-R1-FORECAST-EXECUTION-BATCH-001-20260729T125433Z-aed8c6eb2bf8` | Batch 001 | 12 authoritative forecasts | Prohibited |
| `PPHB-R1-FORECAST-GOVERNANCE-RECOVERY-BATCH-002-20260729T155711Z-d5eb5c6e23c3` and `PPHB-R1-FORECAST-PROVIDER-ERROR-REPLACEMENT-BATCH-002-2026-07-29T16:16:00Z-1e0d63b7c4c5` | Batch 002 | 12 authoritative forecasts | Prohibited |
| `PPHB-R1-FORECAST-EXECUTION-BATCH-003-20260729T163858Z-0da0530d54c3` plus accepted recovery/diagnosis boundaries | Batch 003 | 11 valid forecasts and one terminal schema failure | Prohibited |
| `PPHB-R1-FORECAST-BATCH-003-CLOSURE-AND-FUTURE-NO-SIGNAL-CLARIFICATION-20260801T103016Z-d79d82f56823` | Batch 003 closure | Terminal exception and future prompt rationale | Prohibited |

## INTERMEDIATE_RECOVERY

Transport repair, unknown-state resolution, final existence verification, provider-authority reconciliation, and Batch 003 diagnosis/recovery runs remain available for audit. Future execution should use the accepted closure and migration boundaries rather than reopening every intermediate run.

## DIAGNOSTIC_ONLY

Existing attention, population, lineage, and reconciliation audits that are not listed above remain diagnostic evidence. They may explain prior decisions but do not supersede the accepted current boundary.

## SUPERSEDED_REPORT

Earlier planning, execution, blocker, and recovery summaries are retained in place and are superseded only where the accepted current artifacts above explicitly establish a later boundary. No evidence is moved, renamed, or deleted.
