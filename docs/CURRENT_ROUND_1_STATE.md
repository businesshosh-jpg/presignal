# Current Round 1 State

## Current authority

- Repository: `presignal-historical-baseline-r1`
- Branch: `codex/immediate-impulse-outcome-recovery-r1`
- Accepted execution HEAD for Batch 010: `940bb7d98d29af58f9221d7517a6984028a554b7`
- Forecast contract: `presignal_event_path_contract_v1_1`
- Primary endpoint: `T+15`
- Secondary measurement: `Immediate Impulse`

## Completed stages

Attention population and consolidation, Pack lineage repair, Pack A/E construction, forecast planning, Forecast Batches 001–010, Batch 003 closure, and the future-only NO_SIGNAL prompt migration are accepted.

## Current counts

- Frozen forecast-call identities: `564`
- Batch 001 authoritative valid: `12`
- Batch 002 authoritative valid: `12`
- Batch 003 authoritative valid: `11`
- Batch 003 terminal schema-invalid completed calls: `1`
- Batch 004 authoritative valid: `12`
- Batch 005 authoritative valid: `12`
- Batch 006 authoritative valid: `12`
- Batch 007 authoritative valid: `12`
- Batch 008 authoritative valid: `12`
- Batch 009 authoritative valid: `12`
- Batch 010 authoritative valid: `11`
- Batch 010 terminal parse-invalid completed calls: `1`
- Cumulative authoritative valid forecasts: `118`
- Unexecuted calls: `444`
- Remote-state-unknown calls: `0`

## Accepted authoritative runs

- Forecast plan: `PPHB-R1-FORECAST-EXECUTION-PLAN-20260729T123101Z-14d356fb00c1`
- Batch 003 closure and prompt clarification: `PPHB-R1-FORECAST-BATCH-003-CLOSURE-AND-FUTURE-NO-SIGNAL-CLARIFICATION-20260801T103016Z-d79d82f56823`
- Future prompt migration: `PPHB-R1-FORECAST-FUTURE-NO-SIGNAL-PROMPT-MIGRATION-20260801T130644Z-2bcc88d1ba5e`
- Batch 004: `PPHB-R1-FORECAST-EXECUTION-BATCH-004-20260801T141015Z-fb41ad870499`
- Batch 005: `PPHB-R1-FORECAST-EXECUTION-BATCH-005-20260801T144920Z-9e071fe86e0a`
- Batch 006: `PPHB-R1-FORECAST-EXECUTION-BATCH-006-20260801T152316Z-7bf4abe983dc`
- Batch 007: `PPHB-R1-FORECAST-EXECUTION-BATCH-007-20260801T154757Z-c8b6730975c1`
- Batch 008: `PPHB-R1-FORECAST-EXECUTION-BATCH-008-20260801T174224Z-118a5dce57f7`
- Batch 009: `PPHB-R1-FORECAST-EXECUTION-BATCH-009-20260801T183009Z-524657addc89`
- Batch 010: `PPHB-R1-FORECAST-EXECUTION-BATCH-010-20260801T190644Z-17f70b192668`

## Prompt boundary

- Completed Batches 001–003: `presignal_event_path_contract_v1_1_single_pair_validation`, `sha256:1c74911301c3c7ddea3dc359044209bbd9685b33fcfa434b504753a77f200ab6`
- Unexecuted Batch A004 onward and all Pack E: `presignal_event_path_contract_v1_1_single_pair_validation_no_signal_confidence_explicit_v1`, `sha256:2515e6c09742e58507efe8d9196ba58473c01f2d5bb9e8b5405405088d323a77`
- Authorized addition: `Even when no_signal_flag is true, confidence must be a numeric value from 0 to 1 and must not be null.`
- Call identities and logical batch identities are preserved through versioned manifest revisions; original unexecuted prompt revisions are dispatch-prohibited.

## Known terminal exception

`FCL_27720b8b23236b173b96fdee` (Anthropic / `claude-haiku-4-5`) is closed as terminal provider schema noncompliance after two `confidence=null` responses. It is not authoritative and must not enter evaluation without exceptional new authorization.

`FCL_3d10ae8285471f4e3a980b79` (OpenAI / `gpt-4o-mini-2024-07-18`) is closed as a terminal parse failure in Batch 010 (`PROVIDER_OUTPUT_PATH_COUNT`). It is not authoritative and is not automatically retried.

## Active scientific boundary

Pack A and Pack E remain separate. Provider/model lineage remains frozen. No provider weighting, ranking, consensus, winner selection, Outcome attachment, accuracy calculation, market-data access, matrix update, or Google write is authorized by this state file.

## Exact next Move

Execute migrated `FCB_PACK_A_011` only, using the accepted migration run as its manifest source. Do not execute Batch 012, Pack E, or any other call in that Move.

## Prohibited reopening

Do not reopen accepted Attention, Pack, planning, Batches 001–003, Batch 003 closure, or prompt-migration evidence without a concrete contradiction in named authoritative artifacts or a focused-test failure.
