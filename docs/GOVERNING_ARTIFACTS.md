# Governing Artifacts

This index is a compact pointer to current control boundaries. It does not replace the immutable evidence artifacts.

## FROZEN_EVIDENCE

| Artifact | Scope | Decision controlled | Modification |
|---|---|---|---|
| `PreSignal_v2.1_Development_Plan.pdf`, `PreSignal_v2.1_Full_Round_1_Completion_Proposal.pdf`, `v2.1_Immediate_Impulse_Outcome_Recovery_and_Minimal_Evaluation_Implementation_Proposal.pdf` | Governing proposals | Scientific boundary, completion criteria, and recovery scope | Prohibited |

## AUTHORITATIVE_CURRENT

| Artifact | Scope | Controls | Modification | Superseding artifact |
|---|---|---|---|---|
| `PPHB-R1-FORECAST-EXECUTION-PLAN-20260729T123101Z-14d356fb00c1` | Forecast population and ordering | 564 call identities, provider/model assignments, Pack membership, cutoffs, batch order | Prohibited | Future prompt migration revisions only for unexecuted calls |
| `PPHB-R1-FORECAST-FUTURE-NO-SIGNAL-PROMPT-MIGRATION-20260801T130644Z-2bcc88d1ba5e` | Unexecuted calls | Future prompt version, 45 revised batch manifests, 528 migrated call manifests, dispatch guard | Append-only | Future execution results |
| `automation/execute_presignal_v21_forecast_batch_001.py` | Forecast execution path | Manifest source guard, bounded batches, raw-before-parse, authority and contract checks | Controlled code changes only | None |

| Artifact | Scope | Decision controlled | Modification |
|---|---|---|---|
| `PPHB-R1-PACK-POPULATION-CONSTRUCTION-20260729T113217Z-88b9664e9bd2` | Pack A/E populations | Pack rows, payloads, source lineage | Prohibited |
| `PPHB-R1-FORECAST-EXECUTION-BATCH-001-20260729T125433Z-aed8c6eb2bf8` | Batch 001 | 12 authoritative forecasts | Prohibited |
| `PPHB-R1-FORECAST-GOVERNANCE-RECOVERY-BATCH-002-20260729T155711Z-d5eb5c6e23c3` and `PPHB-R1-FORECAST-PROVIDER-ERROR-REPLACEMENT-BATCH-002-2026-07-29T16:16:00Z-1e0d63b7c4c5` | Batch 002 | 12 authoritative forecasts | Prohibited |
| `PPHB-R1-FORECAST-EXECUTION-BATCH-003-20260729T163858Z-0da0530d54c3` plus accepted recovery/diagnosis boundaries | Batch 003 | 11 valid forecasts and one terminal schema failure | Prohibited |
| `PPHB-R1-FORECAST-BATCH-003-CLOSURE-AND-FUTURE-NO-SIGNAL-CLARIFICATION-20260801T103016Z-d79d82f56823` | Batch 003 closure | Terminal exception and future prompt rationale | Prohibited |
| `FCL_27720b8b23236b173b96fdee` terminal failure evidence in the accepted Batch 003 closure artifacts | Batch 003 exception | Terminal provider-schema failure; excluded from evaluation | Prohibited |
| `PPHB-R1-FORECAST-EXECUTION-BATCH-E003-20260802T063000Z-835fb6815b1b` | Pack E Batch 003 | 12 authoritative forecasts | Prohibited |
| `PPHB-R1-FORECAST-EXECUTION-BATCH-E004-20260802T064500Z-52aeb71b27a4` plus `PPHB-R1-PACK-E-BATCH-004-DUPLICATE-DISPATCH-RECONCILIATION-20260802T090000Z` | Pack E Batch 004 | 12 authoritative forecasts selected by earliest invocation/journal lineage; 10 duplicate dispatches remain non-authoritative | Prohibited |
| `PPHB-R1-FORECAST-EXECUTION-BATCH-E005-20260802T100000Z-dc63e52db568` plus `PPHB-R1-PACK-E-BATCH-005-COMPLETION-20260802T100000Z` | Pack E Batch 005 | 12 authoritative forecasts; exclusive lease and per-call reservations passed | Prohibited |
| `PPHB-R1-FORECAST-EXECUTION-BATCH-E006-20260802T110000Z-400d053f8fb9` plus `PPHB-R1-PACK-E-BATCH-006-COMPLETION-20260802T110000Z` | Pack E Batch 006 | 12 authoritative forecasts; exclusive lease and per-call reservations passed | Prohibited |
| `PPHB-R1-FORECAST-EXECUTION-BATCH-E007-20260802T120000Z-d209ab2c1065` plus `PPHB-R1-PACK-E-BATCH-007-COMPLETION-20260802T120000Z` | Pack E Batch 007 | 12 authoritative forecasts; exclusive lease and per-call reservations passed | Prohibited |
| `PPHB-R1-FORECAST-EXECUTION-BATCH-E008-20260802T130000Z-df09b65502c3` plus `PPHB-R1-PACK-E-BATCH-008-COMPLETION-20260802T130000Z` | Pack E Batch 008 | 12 authoritative forecasts; exclusive lease and per-call reservations passed | Prohibited |

## AUTHORITATIVE_CURRENT: PROMPT MANIFEST BOUNDARY

| Artifact group | Scope | Decision controlled | Modification | Superseding artifact |
|---|---|---|---|---|
| Original forecast-plan prompt payload/fingerprint manifests | Completed calls and original unexecuted revisions | Historical prompt lineage and completed-call evidence | Prohibited; original unexecuted revisions are dispatch-prohibited | Migrated prompt manifests for future calls |
| Migrated prompt manifests in `PPHB-R1-FORECAST-FUTURE-NO-SIGNAL-PROMPT-MIGRATION-20260801T130644Z-2bcc88d1ba5e` | `FCB_PACK_A_004`–`FCB_PACK_A_024` and `FCB_PACK_E_001`–`FCB_PACK_E_024` | Future prompt version and dispatch source | Append-only | Future execution result runs |

## INTERMEDIATE_RECOVERY

Transport repair, unknown-state resolution, final existence verification, provider-authority reconciliation, and Batch 003 diagnosis/recovery runs remain available for audit. Future execution should use the accepted closure and migration boundaries rather than reopening every intermediate run.

## DIAGNOSTIC_ONLY

Existing attention, population, lineage, and reconciliation audits that are not listed above remain diagnostic evidence. They may explain prior decisions but do not supersede the accepted current boundary.

## SUPERSEDED_REPORT

Earlier planning, execution, blocker, and recovery summaries are retained in place and are superseded only where the accepted current artifacts above explicitly establish a later boundary. No evidence is moved, renamed, or deleted.
