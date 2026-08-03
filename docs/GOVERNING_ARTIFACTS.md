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
| `PPHB-R1-FORECAST-EXECUTION-BATCH-E009-20260802T140000Z-1e4a7d294347` plus `PPHB-R1-PACK-E-BATCH-009-COMPLETION-20260802T140000Z` | Pack E Batch 009 | 12 authoritative forecasts; exclusive lease and per-call reservations passed | Prohibited |
| `PPHB-R1-FORECAST-EXECUTION-BATCH-E010-20260802T150000Z-bc603415a4a9` plus `PPHB-R1-PACK-E-BATCH-010-COMPLETION-20260802T150000Z` | Pack E Batch 010 | 12 authoritative forecasts; exclusive lease and per-call reservations passed | Prohibited |
| `PPHB-R1-FORECAST-EXECUTION-BATCH-E011-20260802T160000Z-d6d2d156b163` plus `PPHB-R1-PACK-E-BATCH-011-COMPLETION-20260802T160000Z` | Pack E Batch 011 | 12 authoritative forecasts; exclusive lease and per-call reservations passed | Prohibited |
| `PPHB-R1-FORECAST-EXECUTION-BATCH-E012-20260802T170000Z-8b4849fc4dd0` plus `PPHB-R1-PACK-E-BATCH-012-COMPLETION-20260802T170000Z` | Pack E Batch 012 | 11 authoritative forecasts; one terminal validation failure (`FCL_e07264654e9d3da6f63088a1`); exclusive lease and reservations passed | Prohibited |
| `PPHB-R1-FORECAST-EXECUTION-BATCH-E013-20260802T180000Z-37fee9870723` plus `PPHB-R1-PACK-E-BATCH-013-COMPLETION-20260802T180000Z` | Pack E Batch 013 | 12 authoritative forecasts; exclusive lease and per-call reservations passed | Prohibited |
| `PPHB-R1-FORECAST-EXECUTION-BATCH-E014-20260802T190000Z-3832b3c57c2e` plus `PPHB-R1-PACK-E-BATCH-014-COMPLETION-20260802T190000Z` | Pack E Batch 014 | 12 authoritative forecasts; no repeated `PATH_NEUTRAL_PIP_RANGE`; exclusive lease and per-call reservations passed | Prohibited |
| `PPHB-R1-FORECAST-EXECUTION-BATCH-E015-20260802T200000Z-608a594e1b8a` plus `PPHB-R1-PACK-E-BATCH-015-COMPLETION-20260802T200000Z` | Pack E Batch 015 | 12 authoritative forecasts; no repeated `PATH_NEUTRAL_PIP_RANGE`; exclusive lease and per-call reservations passed | Prohibited |
| `PPHB-R1-FORECAST-EXECUTION-BATCH-E016-20260802T210000Z-6fed373a540e` plus `PPHB-R1-PACK-E-BATCH-016-COMPLETION-20260802T210000Z` | Pack E Batch 016 | 12 authoritative forecasts; no repeated `PATH_NEUTRAL_PIP_RANGE`; exclusive lease and per-call reservations passed | Prohibited |
| `PPHB-R1-FORECAST-EXECUTION-BATCH-E017-20260802T220000Z-ff5bddb11f27` plus `PPHB-R1-PACK-E-BATCH-017-COMPLETION-20260802T220000Z` | Pack E Batch 017 | 12 authoritative forecasts; exclusive lease and per-call reservations passed | Prohibited |
| `PPHB-R1-FORECAST-EXECUTION-BATCH-E018-20260803T000000Z-2c26ea2c6c7a` plus `PPHB-R1-PACK-E-BATCH-018-COMPLETION-20260803T000000Z` | Pack E Batch 018 | 12 authoritative forecasts; exclusive lease and per-call reservations passed | Prohibited |
| `PPHB-R1-FORECAST-EXECUTION-BATCH-E019-20260803T010000Z-be38f0bf21d5` plus `PPHB-R1-PACK-E-BATCH-019-COMPLETION-20260803T010000Z` | Pack E Batch 019 | 12 authoritative forecasts; exclusive lease and per-call reservations passed | Prohibited |
| `PPHB-R1-FORECAST-EXECUTION-BATCH-E020-20260803T020000Z-33aed58c6dad` plus `PPHB-R1-PACK-E-BATCH-020-COMPLETION-20260803T020000Z` | Pack E Batch 020 | 12 authoritative forecasts; exclusive lease and per-call reservations passed | Prohibited |
| `PPHB-R1-FORECAST-EXECUTION-BATCH-E021-20260803T030000Z-effa2248ccfd` plus `PPHB-R1-PACK-E-BATCH-021-COMPLETION-20260803T030000Z` | Pack E Batch 021 | 12 authoritative forecasts; exclusive lease and per-call reservations passed | Prohibited |
| `PPHB-R1-FORECAST-EXECUTION-BATCH-E022-20260803T040000Z-e2f51b4a7768` plus `PPHB-R1-PACK-E-BATCH-022-COMPLETION-20260803T040000Z` | Pack E Batch 022 | 12 authoritative forecasts; exclusive lease and per-call reservations passed | Prohibited |
| `PPHB-R1-FORECAST-EXECUTION-BATCH-E023-20260803T050000Z-f4a1f6540e5a` plus `PPHB-R1-PACK-E-BATCH-023-COMPLETION-20260803T050000Z` | Pack E Batch 023 | 12 authoritative forecasts; exclusive lease and per-call reservations passed | Prohibited |
| `PPHB-R1-FORECAST-EXECUTION-BATCH-E024-20260803T060000Z-ee93fecddb2e` plus `PPHB-R1-PACK-E-BATCH-024-COMPLETION-20260803T060000Z` | Pack E Batch 024 | 6 authoritative forecasts; final Pack E batch; exclusive lease and per-call reservations passed | Prohibited |
| `PPHB-R1-FORECAST-FULL-EXECUTION-COMPLETION-20260803T060000Z` | Full Round 1 forecast execution | 560 authoritative valid forecasts, 4 terminal-invalid calls, 0 unexecuted, 0 unresolved | Prohibited |
| `PPHB-R1-PACK-A-DETERMINISTIC-RAW-RECOVERY-20260803T080000Z-9f2e4c7a1d66` | Pack A `FCL_3d10ae8285471f4e3a980b79` | One existing preserved provider payload recovered by deterministic structural boundary repair; 561 authoritative valid forecasts, 3 unrecovered terminal-invalid calls, 0 unexecuted | Append-only; original terminal evidence remains prohibited | Supersedes the recovered call's terminal-invalid status for current authoritative counting only |
| `PPHB-R1-OUTCOME-COLLECTION-SLICE-001-20260803T001512Z-ceeaad9f41c8` | First 12-Episode immutable Outcome source slice | 12 schema-valid candidate Outcomes, source request lineage and raw hashes; candidates remain unattached and unevaluated | Append-only | Future attachment/reconciliation artifact |
| `PPHB-R1-OUTCOME-ATTACHMENT-SLICE-001-20260803T101500Z-5bbe84a70320` | First 12-Episode Outcome attachment | 12 unchanged candidate-to-attachment links and coverage-only reconciliation for 44 valid forecasts across 12 complete Pack A/E pairs; evaluation remains unauthorized | Append-only | Future evaluation authorization artifact |
| `PPHB-R1-OUTCOME-EVALUATION-SLICE-001-20260803T103000Z-4f8c2b9a6d10` | Minimal evaluation of attached Slice 001 | 44 valid forecasts; Pack-specific T+15 primary, horizon, path, magnitude/pip, reversal, and descriptive paired metrics; Immediate Impulse strict score not applicable for `APPROXIMATION_ONLY`; no composite or broader matrix | Append-only | Future evaluation artifacts only |
| `automation/run_presignal_v21_outcome_slice.py` plus `PPHB-R1-OUTCOME-SLICE-RUNNER-VALIDATION-20260803T110000Z-90765146ec19` | Bounded single-slice Outcome runner | Explicit authorization, manifest/hash binding, stage flags, request ceilings, lease/reservation and duplicate guards; Slice 001 fixture validation; no automatic authorization or next-slice advancement | Controlled code changes; validation evidence append-only | Future bounded runner revisions only |

## AUTHORITATIVE_CURRENT: PROMPT MANIFEST BOUNDARY

| Artifact group | Scope | Decision controlled | Modification | Superseding artifact |
|---|---|---|---|---|
| Original forecast-plan prompt payload/fingerprint manifests | Completed calls and original unexecuted revisions | Historical prompt lineage and completed-call evidence | Prohibited; original unexecuted revisions are dispatch-prohibited | Migrated prompt manifests for future calls |
| Migrated prompt manifests in `PPHB-R1-FORECAST-FUTURE-NO-SIGNAL-PROMPT-MIGRATION-20260801T130644Z-2bcc88d1ba5e` | `FCB_PACK_A_004`–`FCB_PACK_A_024` and `FCB_PACK_E_001`–`FCB_PACK_E_024` | Future prompt version and dispatch source | Append-only | Future execution result runs |

## INTERMEDIATE_RECOVERY

Transport repair, unknown-state resolution, final existence verification, provider-authority reconciliation, and Batch 003 diagnosis/recovery runs remain available for audit. Future execution should use the accepted closure and migration boundaries rather than reopening every intermediate run.

## DIAGNOSTIC_ONLY

Existing attention, population, lineage, and reconciliation audits that are not listed above remain diagnostic evidence. They may explain prior decisions but do not supersede the accepted current boundary.

`PPHB-R1-PACK-A-TERMINAL-INVALID-RECOVERY-FEASIBILITY-REVIEW-20260803T070000Z-385b501cd5dc` is diagnostic-only append-only evidence for the three Pack A terminal-invalid calls. It does not alter terminal classifications, authoritative counts, or the full-execution completion boundary; it identifies one separately authorized mechanical-recovery candidate only.

## SUPERSEDED_REPORT

Earlier planning, execution, blocker, and recovery summaries are retained in place and are superseded only where the accepted current artifacts above explicitly establish a later boundary. No evidence is moved, renamed, or deleted.
