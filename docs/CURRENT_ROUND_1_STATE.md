# Current Round 1 State

## Current authority

- Repository: `presignal-historical-baseline-r1`
- Branch: `codex/immediate-impulse-outcome-recovery-r1`
- Accepted HEAD: `b180cfde311a7a22dc49245a76e933e3191d5aa4` before prospective-stage reconciliation; this state update is append-only.
- Forecast contract: `presignal_event_path_contract_v1_1`
- Primary endpoint: `T+15`
- Secondary measurement: `Immediate Impulse`

## Completed stages

Attention population and consolidation, Pack lineage repair, Pack A/E construction, forecast planning, Forecast Batches 001–024, Pack A completion, Pack E Batches 001–002, Batch 003 closure, and the future-only NO_SIGNAL prompt migration are accepted.

## Current counts

- Frozen forecast-call identities: `564`
- Completed attempted calls: `564`
- Authoritative valid forecasts: `561`
- Terminal-invalid completed calls: `3`
- Unexecuted forecast calls: `0`
- Remote-state-unknown calls: `0`
- Unresolved authoritative identities: `0`
- Duplicate authoritative results: `0`
- Pack A: `282` frozen calls, `280` authoritative valid, `2` terminal-invalid
- Pack E: `282` frozen calls, `281` authoritative valid, `1` terminal-invalid
- Forecast population partition: every frozen call belongs to exactly one authoritative terminal category.
- Pack E Batch 004 duplicate dispatches: `10` preserved as non-authoritative evidence; one authoritative primary result is selected per call by earliest invocation and journal lineage.

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
- Batch 011: `PPHB-R1-FORECAST-EXECUTION-BATCH-011-20260802T013600Z-631806fd5a13`
- Batch 012: `PPHB-R1-FORECAST-EXECUTION-BATCH-012-20260802T015930Z-25a39df38d2a`
- Batch 013: `PPHB-R1-FORECAST-EXECUTION-BATCH-013-20260802T021128Z-0f9208a65341`
- Batch 014: `PPHB-R1-FORECAST-EXECUTION-BATCH-014-20260802T021408Z-07912d764a29`
- Batch 015: `PPHB-R1-FORECAST-EXECUTION-BATCH-015-20260802T022853Z-c001192e3bc5`
- Batch 016: `PPHB-R1-FORECAST-EXECUTION-BATCH-016-20260802T023211Z-2c80e4639857`
- Batch 017: `PPHB-R1-FORECAST-EXECUTION-BATCH-017-20260802T023936Z-9df19389ba37`
- Batch 018: `PPHB-R1-FORECAST-EXECUTION-BATCH-018-20260802T030159Z-af842700cdbb`
- Batch 019: `PPHB-R1-FORECAST-EXECUTION-BATCH-019-20260802T032048Z-c96db4e0af35`
- Batch 020: `PPHB-R1-FORECAST-EXECUTION-BATCH-020-20260802T032353Z-e3a0dc63fd8f`
- Batch 021: `PPHB-R1-FORECAST-EXECUTION-BATCH-021-20260802T034933Z-f8880ff5a60b`
- Batch 022: `PPHB-R1-FORECAST-EXECUTION-BATCH-022-20260802T035131Z-236d96079840`
- Round 1 count reconciliation: `PPHB-R1-FORECAST-COUNT-RECONCILIATION-ROUND-1-20260802T040030Z`
- Pack A completion: `PPHB-R1-PACK-A-COMPLETION-20260802T041525Z`
- Pack E Batch 001: `PPHB-R1-PACK-E-BATCH-001-COMPLETION-20260802T043229Z`
- Pack E Batch 002: `PPHB-R1-PACK-E-BATCH-002-COMPLETION-20260802T050414Z`
- Pack E Batch 003: `PPHB-R1-FORECAST-EXECUTION-BATCH-E003-20260802T063000Z-835fb6815b1b`
- Pack E Batch 004 primary execution: `PPHB-R1-FORECAST-EXECUTION-BATCH-E004-20260802T064500Z-52aeb71b27a4`
- Pack E Batch 004 duplicate-dispatch reconciliation: `PPHB-R1-PACK-E-BATCH-004-DUPLICATE-DISPATCH-RECONCILIATION-20260802T090000Z`
- Pack E Batch 005: `PPHB-R1-FORECAST-EXECUTION-BATCH-E005-20260802T100000Z-dc63e52db568`
- Pack E Batch 006: `PPHB-R1-FORECAST-EXECUTION-BATCH-E006-20260802T110000Z-400d053f8fb9`
- Pack E Batch 007: `PPHB-R1-FORECAST-EXECUTION-BATCH-E007-20260802T120000Z-d209ab2c1065`
- Pack E Batch 008: `PPHB-R1-FORECAST-EXECUTION-BATCH-E008-20260802T130000Z-df09b65502c3`
- Pack E Batch 009: `PPHB-R1-FORECAST-EXECUTION-BATCH-E009-20260802T140000Z-1e4a7d294347`
- Pack E Batch 010: `PPHB-R1-FORECAST-EXECUTION-BATCH-E010-20260802T150000Z-bc603415a4a9`
- Pack E Batch 011: `PPHB-R1-FORECAST-EXECUTION-BATCH-E011-20260802T160000Z-d6d2d156b163`
- Pack E Batch 012: `PPHB-R1-FORECAST-EXECUTION-BATCH-E012-20260802T170000Z-8b4849fc4dd0`
- Pack E Batch 013: `PPHB-R1-FORECAST-EXECUTION-BATCH-E013-20260802T180000Z-37fee9870723`
- Pack E Batch 014: `PPHB-R1-FORECAST-EXECUTION-BATCH-E014-20260802T190000Z-3832b3c57c2e`
- Pack E Batch 015: `PPHB-R1-FORECAST-EXECUTION-BATCH-E015-20260802T200000Z-608a594e1b8a`
- Pack E Batch 016: `PPHB-R1-FORECAST-EXECUTION-BATCH-E016-20260802T210000Z-6fed373a540e` plus `PPHB-R1-PACK-E-BATCH-016-COMPLETION-20260802T210000Z`
- Pack E Batch 017: `PPHB-R1-FORECAST-EXECUTION-BATCH-E017-20260802T220000Z-ff5bddb11f27` plus `PPHB-R1-PACK-E-BATCH-017-COMPLETION-20260802T220000Z`
- Pack E Batch 018: `PPHB-R1-FORECAST-EXECUTION-BATCH-E018-20260803T000000Z-2c26ea2c6c7a` plus `PPHB-R1-PACK-E-BATCH-018-COMPLETION-20260803T000000Z`
- Pack E Batch 019: `PPHB-R1-FORECAST-EXECUTION-BATCH-E019-20260803T010000Z-be38f0bf21d5` plus `PPHB-R1-PACK-E-BATCH-019-COMPLETION-20260803T010000Z`
- Pack E Batch 020: `PPHB-R1-FORECAST-EXECUTION-BATCH-E020-20260803T020000Z-33aed58c6dad` plus `PPHB-R1-PACK-E-BATCH-020-COMPLETION-20260803T020000Z`
- Pack E Batch 021: `PPHB-R1-FORECAST-EXECUTION-BATCH-E021-20260803T030000Z-effa2248ccfd` plus `PPHB-R1-PACK-E-BATCH-021-COMPLETION-20260803T030000Z`
- Pack E Batch 022: `PPHB-R1-FORECAST-EXECUTION-BATCH-E022-20260803T040000Z-e2f51b4a7768` plus `PPHB-R1-PACK-E-BATCH-022-COMPLETION-20260803T040000Z`
- Pack E Batch 023: `PPHB-R1-FORECAST-EXECUTION-BATCH-E023-20260803T050000Z-f4a1f6540e5a` plus `PPHB-R1-PACK-E-BATCH-023-COMPLETION-20260803T050000Z`
- Pack E Batch 024: `PPHB-R1-FORECAST-EXECUTION-BATCH-E024-20260803T060000Z-ee93fecddb2e` plus `PPHB-R1-PACK-E-BATCH-024-COMPLETION-20260803T060000Z`
- Full forecast execution completion: `PPHB-R1-FORECAST-FULL-EXECUTION-COMPLETION-20260803T060000Z`
- Pack A deterministic raw recovery: `PPHB-R1-PACK-A-DETERMINISTIC-RAW-RECOVERY-20260803T080000Z-9f2e4c7a1d66`
- Pack A deterministic raw recovery verification: `PPHB-R1-PACK-A-DETERMINISTIC-RAW-RECOVERY-VERIFICATION-20260803T111500Z-9f2e4c7a1d66` (`FCL_3d10ae8285471f4e3a980b79`; one schema-proven structural boundary restored, strict validation passed, no provider call; prior terminal evidence preserved)
- Outcome authorization preparation: `PPHB-R1-OUTCOME-AUTHORIZATION-PREPARATION-20260803T090000Z-18cddcdc5477`
- Outcome source preflight: `PPHB-R1-OUTCOME-COLLECTION-SLICE-001-20260803T000113Z-ceeaad9f41c8` (`OUTCOME_SOURCE_PREFLIGHT_PASSED`; collection blocked before external access by `GOOGLE_OAUTH_TOKEN_MISSING`)
- OAuth restoration and collection attempt: `PPHB-R1-OUTCOME-OAUTH-RESTORATION-SLICE-001-20260803T000800Z` (`GOOGLE_OAUTH_ROUTE_NOT_RESTORED`; preflight blocked before external access)
- OAuth route restored and Slice 001 collected: `PPHB-R1-OUTCOME-COLLECTION-SLICE-001-20260803T001512Z-ceeaad9f41c8` (`OUTCOME_SOURCE_PREFLIGHT_PASSED`; 12/12 candidate Outcomes valid, unattached and unevaluated)
- Slice 001 attachment and reconciliation: `PPHB-R1-OUTCOME-ATTACHMENT-SLICE-001-20260803T101500Z-5bbe84a70320` (`OUTCOME_SLICE_001_ATTACHED_AND_RECONCILED`; 12/12 candidates attached locally append-only; 44 valid forecasts covered across 12 complete Pack A/E pairs; evaluation remains unauthorized)
- Slice 001 minimal evaluation: `PPHB-R1-OUTCOME-EVALUATION-SLICE-001-20260803T103000Z-4f8c2b9a6d10` (`OUTCOME_SLICE_001_MINIMAL_EVALUATION_COMPLETE`; 44 valid forecasts evaluated locally; T+15 primary, Immediate Impulse strict score not applicable for APPROXIMATION_ONLY outcomes; no composite or broader matrix calculated)
- Bounded Outcome slice runner validation: `PPHB-R1-OUTCOME-SLICE-RUNNER-VALIDATION-20260803T110000Z-90765146ec19` (`OUTCOME_SLICE_RUNNER_IMPLEMENTATION_VALIDATED`; preflight-only default, explicit stage flags, authorization/ceiling/hash/lease/duplicate guards, and Slice 001 offline fixture compatibility passed; no Slice 002 authorization granted)
- Slice 002 manifest preparation: `PPHB-R1-OUTCOME-COLLECTION-MANIFEST-SLICE-002-20260803T121500Z-9c7adf4c2f2e` (`SLICE_002_OUTCOME_COLLECTION_MANIFEST_FROZEN`; 12 Episodes, 44 valid forecasts, 22 Pack A/E pairs; proposed collection authorization is not active)
- Authorized-slice controller validation: `PPHB-R1-OUTCOME-AUTHORIZED-SLICE-CONTROLLER-VALIDATION-20260803T125200Z-16e231a85457` plus end-to-end validation `PPHB-R1-OUTCOME-AUTHORIZED-SLICE-END-TO-END-VALIDATION-20260803T131000Z-16e231a85457` (`END_TO_END_AUTHORIZED_SLICE_MODE_IMPLEMENTED`; clean mocked progression passed; live Slice 002 remains stopped at `MANIFEST_ACCEPTED_END_TO_END_AUTHORIZATION_REQUIRED`; zero external access)
- Active Slice 002 end-to-end authorization: `PPHB-R1-OUTCOME-SLICE-002-END-TO-END-AUTHORIZATION-20260803T140000Z-e8e69ad49e46`, authorization `PPHB-R1-OUTCOME-SLICE-002-END-TO-END-AUTHORIZATION-20260803T140000Z`, fingerprint `sha256:acea3df8666d7d5dc6474bd7d0269a79e02e41d91ef4e449299833fe8fcf9da3`, bound to controller commit `856b562f6cead831ab838f48bca90284e3dd3cb7`
- Slice 002 collection: `PPHB-R1-OUTCOME-COLLECTION-SLICE-002-20260803T035402Z-5b2104c5270c` (`OUTCOME_COLLECTION_SLICE_002_COMPLETE`; 12/12 candidates valid; 3 Apps Script reads, 3 market-data attempts, 6 total external requests, 0 writes). The collection-to-attachment bridge is repaired and validated append-only.
- Slice 002 attachment: `PPHB-R1-OUTCOME-ATTACH-SLICE-002-20260803T044538Z-5b2104c5270c` (`OUTCOME_SLICE_002_ATTACHED_AND_RECONCILED`; 12/12 attached, 44 valid forecasts, 22 complete Pack A/E pairs, 0 writes). The controller completion-proof compatibility repair was accepted before evaluation.
- Slice 002 evaluation and completion: `PPHB-R1-OUTCOME-EVALUATE-SLICE-002-20260803T045628Z-5b2104c5270c` plus `slice_completion.json` (`AUTHORIZED_SLICE_002_END_TO_END_COMPLETE`; collection and attachment reused, 44 forecasts evaluated locally, six authorized metrics only, no external access).
- Next Slice 003 manifest preparation: `PPHB-R1-OUTCOME-COLLECTION-MANIFEST-SLICE-003-20260803T154000Z` (fingerprint recorded in the package; `NEXT_PROSPECTIVE_SLICE_MANIFEST_FROZEN`; 12 Episodes, 40 valid forecasts, 20 Pack A, 20 Pack E, 20 complete pairs; authorization inputs are proposed and inactive).
- Active Slice 003 end-to-end authorization: `PPHB-R1-OUTCOME-SLICE-003-END-TO-END-AUTHORIZATION-20260803T160000Z-42faad88745d71b047fb` (`SLICE_003_END_TO_END_AUTHORIZATION_FROZEN`; fingerprint `sha256:42faad88745d71b047fb1136b5f799b45501bed621874b85a894f6c2def36eb8`; authorized but not started).
- Slice 003 execution preflight: `PPHB-R1-OUTCOME-SLICE-003-END-TO-END-EXECUTION-BLOCKED-20260803T064300Z` (`AUTHORIZED_SLICE_003_GOVERNANCE_BLOCKED`; population spans 10 UTC release days while authorization permits 3 Apps Script reads; external requests 0).
- Slice 003 replacement authorization: `PPHB-R1-OUTCOME-SLICE-003-REPLACEMENT-END-TO-END-AUTHORIZATION-20260803T171000Z-27ebd3d15f91637f217a` (`SLICE_003_REPLACEMENT_END_TO_END_AUTHORIZATION_FROZEN`; fingerprint `sha256:27ebd3d15f91637f217a2621edecf48c32d61698587d3bf785b2ffdef743e49b`; corrected 10/12/22 ceilings; authorized but not started).
- Slice 003 replacement collection: `PPHB-R1-OUTCOME-COLLECTION-SLICE-003-20260803T071136Z-fc2fd1815bd5` (10 Apps Script reads, 12 market-data attempts, 22 total requests, 12 candidate records; two explicit unavailable-source Episodes; attachment and evaluation not started).
- Slice 003 replacement execution stop: `PPHB-R1-OUTCOME-SLICE-003-REPLACEMENT-END-TO-END-EXECUTION-BLOCKED-20260803T071500Z` (`AUTHORIZED_SLICE_003_GOVERNANCE_BLOCKED`; attachment blocked by two unavailable-source Outcomes; no retry authorized).
- Slice 003 unavailable-Outcome governance review: `PPHB-R1-SLICE-003-UNAVAILABLE-OUTCOME-GOVERNANCE-REVIEW-20260803T073000Z` recommends `AUTHORIZE_PAIRED_EXCLUSION_OF_TWO_UNAVAILABLE_EPISODES` and records `SLICE_003_RESUME_AUTHORIZATION_READY`. `EP_EVENT_4b80366594480b554889` is terminally unavailable under the exhausted canonical source route; `EP_EVENT_aa41226bcb8107901555` would require a separately authorized external recovery because its route failed before provider dispatch. No exclusion, attachment, evaluation, retry, or external request occurred in the review.
- Slice 003 paired-exclusion attachment authorization: `PPHB-R1-SLICE-003-PAIRED-EXCLUSION-ATTACHMENT-AUTHORIZATION-20260803T080000Z` is accepted and reconciled as `10/10` local attachments with zero external requests, writes, or retries.
- Slice 003 supplementary evaluation authorization: `PPHB-R1-SLICE-003-SUPPLEMENTARY-EVALUATION-AUTHORIZATION-20260803T081500Z`, fingerprint `sha256:1a04811ea2b95396242c37bda8b5430ad9e2b9bc5a9c4c33aa945fa238bd9b0d`, completed once for the revised 32-forecast population.
- Slice 003 completion: `PPHB-R1-OUTCOME-SLICE-003-COMPLETION-20260803T081500Z-1a04811ea2b95396242c` (`AUTHORIZED_SLICE_003_END_TO_END_COMPLETE`; 10 Outcomes, 32 forecasts, 16 Pack A, 16 Pack E, 16 complete pairs; no new external access or writes). The two unavailable Episodes and their eight paired forecast calls remain excluded under the accepted governance decision; prior blocked authorizations remain non-reusable.
- Slice 003 T+15 denominator reconciliation: `PPHB-R1-SLICE-003-T15-DENOMINATOR-RECONCILIATION-20260803T090000Z` (`SLICE_003_T15_DENOMINATORS_CONFIRMED`). Pack E call `FCL_cb40905e9d82b875db434ffd` is an explicit no-signal forecast for `EP_BATCH_e14769aca1aaacc9c230`; the governing rule excludes it from the Pack E directional denominator, leaving Pack E `7/15`. Pack A remains `5/16`; a direct paired T+15 comparison has 15 mutually scoreable pairs.
- Slice 004 manifest preparation: `PPHB-R1-OUTCOME-COLLECTION-MANIFEST-SLICE-004-20260803T090000Z-527470dac479af672166` (`NEXT_PROSPECTIVE_SLICE_MANIFEST_FROZEN`; fingerprint `sha256:527470dac479af672166e861dc39b33873264fc4fc734208cb370ccd2ce593a5`; 12 Episodes, 48 valid forecasts, 24 Pack A, 24 Pack E, 24 complete pairs, 8 UTC release days). Proposed authorization inputs are inactive.
- Slice 007 manifest and authorization: `PPHB-R1-OUTCOME-COLLECTION-MANIFEST-SLICE-007-20260803T140000Z` (fingerprint `sha256:0bf9c7477606ab6c51ec0d46397e30e6b83c7f6a3569b848650181c3d79659cc`) and `PPHB-R1-OUTCOME-SLICE-007-END-TO-END-AUTHORIZATION-20260803T150000Z` (fingerprint `sha256:c703e4cd2e9a2da744ef8a8447e8b92fad19e19e803ae95bdb73dba65081cc49`); corrected canonical source binding accepted after a mechanical top-level `source_authority` compatibility repair.
- Slice 007 completion: `PPHB-R1-OUTCOME-SLICE-007-COMPLETION-20260803T094017Z-0bf9c7477606` (`AUTHORIZED_SLICE_007_END_TO_END_COMPLETE`; 12 Outcomes, 42 valid forecasts, 21 Pack A, 21 Pack E, 21 complete pairs, 8 Apps Script reads, 8 market-data attempts, 16 total external requests, 0 writes, 0 retries, no unavailable or unresolved identities).
- Slice 008 manifest and authorization: `PPHB-R1-OUTCOME-COLLECTION-MANIFEST-SLICE-008-20260803T160000Z` (fingerprint `sha256:6c6c24320615ef6947412fa58c8a1628fa36a4634a8561e122dcb162981a8f90`) and `PPHB-R1-OUTCOME-SLICE-008-END-TO-END-AUTHORIZATION-20260803T170000Z` (fingerprint `sha256:0518c867118e707cacf5bf608faeebc3ca46241a8015d88d90f19cff4333523f`); 12 Episodes, 42 valid forecasts, 21 Pack A, 21 Pack E, 21 complete pairs, 6 UTC release days.
- Slice 008 completion: `PPHB-R1-OUTCOME-SLICE-008-COMPLETION-20260803T101556Z-6c6c24320615` (`AUTHORIZED_SLICE_008_END_TO_END_COMPLETE`; 12 Outcomes, 42 valid forecasts, 21 Pack A, 21 Pack E, 21 complete pairs, 6 Apps Script reads, 6 market-data attempts, 12 total external requests, 0 writes, 0 retries, no unavailable or unresolved identities).
- Slice 009 manifest and authorization: `PPHB-R1-OUTCOME-COLLECTION-MANIFEST-SLICE-009-20260803T180000Z` (fingerprint `sha256:1f8ae1ba9312ee2dd121b7d3fa68c4b20360720b71fce9364222af38aa3c6a26`) and `PPHB-R1-OUTCOME-SLICE-009-END-TO-END-AUTHORIZATION-20260803T190000Z` (fingerprint `sha256:fdf349b9984b88f20ddac84158b5120ddac814d6308fecf145acf6b7e567f674`); 12 Episodes, 42 valid forecasts, 21 Pack A, 21 Pack E, 21 complete pairs, 9 UTC release days.
- Slice 009 completion: `PPHB-R1-OUTCOME-SLICE-009-COMPLETION-20260803T103300Z-42826db48733c8ee9530` (`AUTHORIZED_SLICE_009_END_TO_END_COMPLETE`; four unavailable Episodes were symmetrically paired-excluded under the accepted rule; 8 Outcomes attached, 28 forecasts evaluated, 14 Pack A/E pairs, 18 collection requests, 0 new requests after collection, 0 writes, 0 retries).
- Slice 010 manifest and authorization: `PPHB-R1-OUTCOME-COLLECTION-MANIFEST-SLICE-010-20260803T200000Z` (fingerprint `sha256:ace0f9494fad1bb70c01254756de43cc514c8bed0a883530e6e4a2340f9b9a1a`) and `PPHB-R1-OUTCOME-SLICE-010-END-TO-END-AUTHORIZATION-20260803T210000Z` (fingerprint `sha256:38b6ef2c47ade753cfeb20b01b58fc36a3fa01ae8cb62d091663faa4cd69a430`); 12 Episodes, 52 valid forecasts, 26 Pack A, 26 Pack E, 26 complete pairs, 6 UTC release days.
- Slice 010 completion: `PPHB-R1-OUTCOME-SLICE-010-COMPLETION-20260803T104400Z-ace0f9494fad1bb70c01` (`AUTHORIZED_SLICE_010_END_TO_END_COMPLETE`; 12 Outcomes attached, 52 forecasts evaluated, 26 Pack A/E pairs, 12 external requests, 0 writes, 0 retries, no unavailable or unresolved identities).

## Prompt boundary

- Completed Batches 001–003: `presignal_event_path_contract_v1_1_single_pair_validation`, `sha256:1c74911301c3c7ddea3dc359044209bbd9685b33fcfa434b504753a77f200ab6`
- Unexecuted Batch A004 onward and all Pack E: `presignal_event_path_contract_v1_1_single_pair_validation_no_signal_confidence_explicit_v1`, `sha256:2515e6c09742e58507efe8d9196ba58473c01f2d5bb9e8b5405405088d323a77`
- Authorized addition: `Even when no_signal_flag is true, confidence must be a numeric value from 0 to 1 and must not be null.`
- Call identities and logical batch identities are preserved through versioned manifest revisions; original unexecuted prompt revisions are dispatch-prohibited.

## Known terminal exception

`FCL_27720b8b23236b173b96fdee` (Anthropic / `claude-haiku-4-5`) is closed as terminal provider schema noncompliance after two `confidence=null` responses. It is not authoritative and must not enter evaluation without exceptional new authorization.

`FCL_3d10ae8285471f4e3a980b79` (OpenAI / `gpt-4o-mini-2024-07-18`) is closed as a terminal parse failure in Batch 010 (`PROVIDER_OUTPUT_PATH_COUNT`). It is not authoritative and is not automatically retried.

`FCL_e07264654e9d3da6f63088a1` (OpenAI / `gpt-4o-mini-2024-07-18`) is closed as a terminal validation failure in Pack E Batch 012 (`PATH_NEUTRAL_PIP_RANGE`). It is not authoritative and is not automatically retried.

The append-only Pack A terminal-invalid recovery-feasibility review (`PPHB-R1-PACK-A-TERMINAL-INVALID-RECOVERY-FEASIBILITY-REVIEW-20260803T070000Z-385b501cd5dc`) identified `FCL_3d10ae8285471f4e3a980b79` as mechanically recoverable. The accepted no-provider-call recovery (`PPHB-R1-PACK-A-DETERMINISTIC-RAW-RECOVERY-20260803T080000Z-9f2e4c7a1d66`) selected it as authoritative without modifying the original terminal evidence. Remaining terminal-invalid calls are `FCL_27720b8b23236b173b96fdee`, `FCL_7f0463b134c67757968580e8`, and `FCL_e07264654e9d3da6f63088a1`.

## Active scientific boundary

Pack A and Pack E remain separate. Provider/model lineage remains frozen. No provider weighting, ranking, consensus, winner selection, Outcome attachment, accuracy calculation, market-data access, matrix update, or Google write is authorized by this state file.

## Outcome collection boundary

Slice 001 contains 12 immutable candidate Outcomes under `presignal_event_path_contract_v1_1` schema `2.1.1`. Source collection used 3 Apps Script reads and 3 Tiingo provider attempts. The accepted attachment run links all 12 candidates append-only with unchanged hashes and no external access. Coverage is 44 valid forecasts across 12 complete Pack A/E pairs; no evaluation was calculated.
The accepted minimal evaluation is limited to those 44 forecasts and attached Outcomes. It reports Pack-specific T+15, horizon, path, magnitude/pip, and reversal metrics plus descriptive Pack A/E differences. Immediate Impulse remains secondary and strict-scoring is not applicable because the slice is `APPROXIMATION_ONLY`; no composite score or statistical inference is authorized.

The bounded single-slice runner and authorized-slice controller are validated for future use. They require separate machine-readable authorization, exact manifest hash, explicit stage controls, and append-only stage evidence; stage-by-stage mode remains available and end-to-end mode advances only after accepted prior-stage completion. Slices 002 through 011 are complete under their frozen boundaries, and Slice 012 is complete under its expanded boundary. Slice 011 used 14 Apps Script reads and 14 provider attempts (28 total external requests), then applied one deterministic paired exclusion with zero new external access; 35 Outcomes were attached and 124 forecasts evaluated across 62 complete Pack A/E pairs. Slice 012 used 1 Apps Script read and 1 provider attempt (2 total external requests), attached 3 Outcomes, and evaluated 14 forecasts across 7 complete Pack A/E pairs. T+15 remains primary and Immediate Impulse remains secondary; no composite score or broader matrix was calculated. Current controller state: `AUTHORIZED_EXPANDED_SLICE_END_TO_END_COMPLETE`. Slice 012 completed without unavailable Outcomes or continuation authorization. A new prospective Slice requires a new frozen manifest and explicit authorization.

## Slice 012 Completion

- Manifest: `PPHB-R1-OUTCOME-COLLECTION-MANIFEST-SLICE-012-20260804T010000Z-2254278251fac1f625ab` (`sha256:2254278251fac1f625ab06948c2275b996f59727b93a6eb9ddddc68c116427d5`)
- Population: 3 Episodes; 14 valid forecasts; 7 Pack A; 7 Pack E; 7 complete pairs; 0 unpaired; 1 UTC release day.
- Ceilings: 1 Apps Script read; 3 market-data attempts; 4 total requests; 3 local attachments; 0 writes; 0 retries. Actual collection used 1 provider attempt and 2 total requests.
- Collection: `PPHB-R1-OUTCOME-COLLECTION-SLICE-012-20260803T112350Z-c68c116427d5`.
- Attachment: `PPHB-R1-OUTCOME-ATTACH-SLICE-012-20260803T112356Z-c68c116427d5` (3/3, zero duplicates or unattached eligible Outcomes).
- Evaluation: `PPHB-R1-OUTCOME-EVALUATE-SLICE-012-20260803T112356Z-c68c116427d5` (14 forecasts; six authorized metrics only; Immediate Impulse strict score not applicable).
- Completion: `PPHB-R1-OUTCOME-SLICE-012-COMPLETION-20260804T030000Z-b7526624ab98c1da4aff` (`AUTHORIZED_EXPANDED_SLICE_END_TO_END_COMPLETE`).
- Ledger: `PPHB-R1-COMPLETED-SLICE-LEDGER-RECONCILIATION-THROUGH-012-20260804T030000Z`.

## Slice 011 Completion

- Manifest: `PPHB-R1-OUTCOME-COLLECTION-MANIFEST-SLICE-011-20260803T220000Z-4aea7d52a95303768ec8` (`sha256:4aea7d52a95303768ec8a20faa76957d41d4a9a0ddd6a2d37fb0b56ebc7495bf`)
- Expanded population: 36 selected Episodes; 14 UTC release days; 130 valid forecasts before treatment; 65 Pack A, 65 Pack E, 65 pairs.
- Unavailable treatment: `EP_EVENT_ce560e1428b25b69fbb2` was terminally unavailable under the current source because of `MISSING_OR_STALE_PRICE_60M`; its six linked forecasts were excluded symmetrically under the accepted paired-exclusion rule.
- Revised population: 35 attached Episodes; 124 evaluated forecasts; 62 Pack A; 62 Pack E; 62 complete pairs; 0 unpaired.
- Collection: `PPHB-R1-OUTCOME-COLLECTION-SLICE-011-20260803T105829Z-b56ebc7495bf` (14 Apps Script reads, 14 market-data attempts, 28 total external requests, 0 writes, 0 retries).
- Attachment: `PPHB-R1-OUTCOME-ATTACH-SLICE-011-20260803T110347Z-b56ebc7495bf` (35 local append-only attachments, 0 duplicates, 0 unattached eligible Outcomes).
- Evaluation: `PPHB-R1-OUTCOME-EVALUATE-SLICE-011-20260803T110347Z-b56ebc7495bf` (124 forecasts; six authorized metrics only; Immediate Impulse strict score not applicable).
- Completion: `PPHB-R1-OUTCOME-SLICE-011-COMPLETION-20260803T111500Z-eef0a8b7d52e` (`AUTHORIZED_EXPANDED_SLICE_END_TO_END_COMPLETE`).
- Ledger: `PPHB-R1-COMPLETED-SLICE-LEDGER-RECONCILIATION-THROUGH-011-20260803T111500Z`; Slice 002 completion is bound to its accepted evaluation-stage `slice_completion.json`, and no duplicate Episode use or unresolved authoritative identity remains.

## Exact next Move

Prepare a separately authorized confirmatory prospective Round 2 protocol. It must preserve Pack A as the baseline, Pack E as the hypothesis-supported arm, T+15 as primary, and pre-register coverage/no-signal handling; do not replace a Pack, add provider selection, or execute Round 2 in the preparation Move.

## Prospective Outcome/Evaluation Stage Completion

- Decision: `PROSPECTIVE_OUTCOME_EVALUATION_STAGE_COMPLETE`.
- Reconciliation: `PPHB-R1-PROSPECTIVE-OUTCOME-EVALUATION-STAGE-COMPLETION-20260804T040000Z`.
- Episode partition: 151 total; 138 completed/evaluated; 10 paired-excluded unavailable; 3 excluded by accepted authority/attention-lineage conflict; 0 eligible; 0 unresolved.
- Forecast partition: 564 frozen identities; 561 authoritative valid; 3 terminal-invalid; 518 forecast records evaluated in accepted Slice evaluations; no unexecuted forecast identity.
- Outcome coverage: 138 Outcomes attached; unavailable and paired-excluded evidence preserved; no duplicate attachment or evaluation.
- Historical aggregate boundary: at prospective-stage completion, no pooled metric, significance test, matrix update, composite score, or broader conclusion had been calculated. Its prescribed aggregate authorization has since been completed below.

## Round 1 Aggregate Evaluation

- Decision: `ROUND_1_AGGREGATE_EVALUATION_COMPLETE`.
- Authorization: `PPHB-R1-AGGREGATE-EVALUATION-AUTHORIZATION-20260804T050000Z` (`sha256:806ff5fb1d37c42209690fa601101d7590fb96a856bde491ba16285d284ba0d7`), single-use and completed against the eleven accepted Slice evaluation artifacts.
- Result: `PPHB-R1-ROUND-1-AGGREGATE-EVALUATION-RESULT-20260804T050000Z`; 518 unique evaluated forecasts, 259 Pack A, 259 Pack E, and 259 complete Pack A/E pairs. No external access, Google operation, Outcome attachment, retry, or Outcome modification occurred.
- T+15 primary endpoint: Pack A `87/208` (`0.418269`); Pack E `113/252` (`0.448413`). Common paired-scoreable population: 206 pairs, Pack A `86/206` (`0.417476`) and Pack E `100/206` (`0.485437`), descriptive only.
- Immediate Impulse: `NOT_APPLICABLE_STRICT` for both Packs because no accepted aggregate record has a `SUPPORTED` strict Outcome. No-signal exclusions: Pack A 51; Pack E 7.
- Other pooled metrics and all identity/denominator proofs are append-only in the aggregate result. No composite score, statistical inference, confidence interval, provider selection, subgroup analysis, or post-hoc optimization was calculated.

## Round 1 Final Interpretation

- Decisions: `ROUND_1_SCIENTIFIC_INTERPRETATION_COMPLETE`; `ROUND_1_FINAL_REPORT_COMPLETE`.
- Evidence strength: `MODERATE_DESCRIPTIVE_EVIDENCE`. Pack E has the higher T+15 directional accuracy on both Pack-specific pooled denominators and the 206 common paired-scoreable observations; it also has lower magnitude interval error and higher reported horizon and path results, while Pack A has higher reversal accuracy.
- Coverage boundary: Pack A's 51 no-signal exclusions versus Pack E's 7 prevent the Pack-specific denominators from establishing a like-for-like direct comparison. The common paired-scoreable result is descriptive only and does not provide statistical significance or a superiority claim.
- Scientific conclusion: continue Pack E as a hypothesis-supported arm and retain Pack A as the baseline comparator. Do not replace Pack A, select providers, create a meta-forecast, revise Pack definitions, or begin Round 2 from Round 1 descriptive evidence alone.
- Final report: `PPHB-R1-ROUND-1-FINAL-REPORT-20260804T060000Z`; no external access, metric recalculation, new inference test, forecast/Outcome change, or Google operation occurred.

## Round 1 Paired T+15 Inference

- Decision: `ROUND_1_PAIRED_T15_INFERENCE_COMPLETE`.
- Authorization: `PPHB-R1-PAIRED-T15-INFERENCE-AUTHORIZATION-20260804T070000Z` (`sha256:5b9f977a9915d9ce9273e3fc89afc5b1e01894ea564134f1badd99c2703916e1`), local-only and completed once against the frozen 206 common paired-scoreable observations.
- Test: pre-specified exact two-sided McNemar test, null of equal discordant probabilities, alpha `0.05`, no continuity correction, and no confidence interval because a canonical paired-risk-difference interval method was not governed.
- Four-cell table: 46 both correct; 40 Pack A correct / Pack E incorrect; 54 Pack A incorrect / Pack E correct; 66 both incorrect. Paired risk difference A-E: `-0.067961`; exact p-value: `0.179665`.
- Evidence correction: `pair_population_proof_correction.json` append-only corrects a non-core excluded-record metadata literal from 112 to 106 (`518 - 412`); the frozen 206-pair inventory, four-cell table, effect estimate, and p-value are unchanged.
- Inference: the null is not rejected at the pre-specified threshold. The evidence is therefore `MODERATE_DESCRIPTIVE_EVIDENCE_WITHOUT_INFERENTIAL_SUPPORT`, not a superiority, replacement, provider-selection, or future-performance claim. Keep Pack E hypothesis-supported and Pack A as the baseline.
- No external access, metric-population change, Outcome/forecast mutation, confidence interval, provider inference, subgroup test, multiple-comparison adjustment, odds ratio, Bayesian analysis, power analysis, or composite score occurred.

## Prospective Round 2 Protocol

- Decisions: `PROSPECTIVE_ROUND_2_PROTOCOL_FROZEN`; `PROSPECTIVE_ROUND_2_EXECUTION_PREPARATION_READY`.
- Protocol: `PPHB-R2-CONFIRMATORY-PROSPECTIVE-PROTOCOL-20260804T080000Z` (`sha256:d417e4c76d3d38d471dbc76cbf361be4a28dac1b615ecccdc8aa18c37262362f`), append-only and execution-prohibited in this Move.
- Purpose: a prospective confirmatory Pack A baseline versus Pack E experimental-arm comparison. T+15 directional accuracy remains primary; exact two-sided McNemar at alpha `0.05` is frozen for final common paired-scoreable observations. Immediate Impulse remains secondary and strictly scoreable only for `SUPPORTED` Outcomes. No confidence interval, composite score, provider-level inference, subgroup inference, interim analysis, Pack replacement, or provider selection is authorized.
- Coverage: report directional coverage and NO_SIGNAL rate separately by Pack. NO_SIGNAL is neither correct nor incorrect and is excluded from directional denominators; direct Pack comparison uses matching same-Episode/provider/model rows scoreable in both Packs against the same Outcome.
- Bounded design: target 120 eligible Episodes and 240 common paired-scoreable observations; maximum 144 eligible Episodes, minimum 200 common pairs for the confirmatory test, and no more than 48 Episodes per Slice. The Round 1-derived scenario table is operational planning only, not a power claim or expected effect guarantee.
- Provider/model control: freeze one Pack A/E pair for each admitted Episode on each accepted route: Anthropic / `claude-haiku-4-5`, Gemini / `gemini-2.5-flash-lite`, and OpenAI / `gpt-4o-mini-2024-07-18`. Reallocation, silent substitution, outcome-informed selection, and replacement require separate authorization.
- Local-only protocol Move: Round 2 execution, forecast dispatches, provider calls, Apps Script reads, market-data requests, Google reads/writes, Outcome collection/attachment, metrics, and retries were all `0`.

## Exact Next Move

Prepare one separately authorized Round 2 execution envelope and first prospective Slice manifest. It must freeze future Episode eligibility, pre-release cutoff and leakage checks, deterministic provider/model allocation, paired forecast identities, and manifest-derived request ceilings before any forecast dispatch.

## Round 2 Execution Envelope Preparation

- Envelope decision: `ROUND_2_EXECUTION_ENVELOPE_FROZEN`.
- Envelope: `PPHB-R2-EXECUTION-ENVELOPE-20260803T090000Z` (`sha256:3fe721eee816e48a5eca00c50cbcbc397bec6258d60bdfc7857e8169869efdd0`), inactive and not provider-call authority. It binds to protocol `PPHB-R2-CONFIRMATORY-PROSPECTIVE-PROTOCOL-20260804T080000Z` (`sha256:d417e4c76d3d38d471dbc76cbf361be4a28dac1b615ecccdc8aa18c37262362f`) and preserves the 144 maximum / 120 target / 240 target common-pair / 200 minimum / 48-per-Slice limits.
- First-Slice decision: `ROUND_2_FIRST_PROSPECTIVE_SLICE_MANIFEST_BLOCKED`; dispatch decision: `ROUND_2_FIRST_SLICE_DISPATCH_AUTHORIZATION_INPUTS_NOT_READY`.
- Blocker: `PROSPECTIVE_EPISODE_SOURCE_AUTHORITY_MISSING`. Repository evidence contains only completed May-July 2024 Round 1 Episodes and explicitly synthetic prospective dry-run fixtures with placeholder 2030 timestamps. No authoritative current prospective Episode registry or release schedule is available, so no Episode, call, prompt fingerprint, cutoff, or manifest identity was fabricated.
- Activity: provider calls `0`; Google/market-data access `0`; Outcome activity `0`; metric calculation `0`.

## Exact Round 2 Next Move

Establish or provide an authoritative current prospective Episode source and release schedule, then freeze the first Slice manifest and one explicit forecast-dispatch authorization. Execute that authorization only after local identity, Pack A/E pairing, prompt, cutoff, lease, reservation, and leakage validation passes.

## Continuous Round 2 Execution Controller

- Decisions: `ROUND_2_AUTHORITATIVE_EPISODE_SOURCE_ESTABLISHED`; `CONTINUOUS_ROUND_2_CONTROLLER_READY`; `ROUND_2_DISPATCH_AUTHORIZATION_INPUTS_NOT_READY`.
- Authoritative source contract: FMP Economic Calendar through the existing Apps Script `apiUpsertEventWindow_` route, canonical `normalizeFmpRow_` normalization, Event-sheet upsert/batching, and a captured append-only Event-sheet export. Generic web calendars, synthetic fixtures, dry-run records, released events, and historical Round 1 events are rejected.
- Controller: `automation/run_presignal_v21_continuous_round_2.py`. It validates only captured authoritative snapshots, freezes deterministic Episode admission and exact Pack A/E/provider call identities, and defines resumable stage handoffs to the canonical forecast and Outcome controllers. It never dispatches from a policy ceiling alone.
- Current roster status: no append-only current Event-sheet export exists locally. A full roster cannot be frozen, no first rolling Slice is selected, and no provider-call identity is fabricated. The prior 2030 prospective fixture remains non-authoritative.
- Activity in this Move: provider calls `0`; external access `0`; Google writes `0`; Outcome activity `0`; evaluation activity `0`; retries `0`.

## Exact Next Round 2 Move

Freeze a bounded schedule-refresh and Event-sheet-export authorization for the canonical FMP/Apps Script route, including exact external and Google-write ceilings. Capture and preserve the authoritative current schedule snapshot, then use the continuous controller to freeze a first rolling Slice and an exact provider-dispatch authorization before any provider call.

## Prohibited reopening

Do not reopen accepted Attention, Pack, planning, Batches 001–003, Batch 003 closure, or prompt-migration evidence without a concrete contradiction in named authoritative artifacts or a focused-test failure.

## Round 2 Schedule Refresh Attempt

- Refresh authorization: `PPHB-R2-SCHEDULE-REFRESH-AUTHORIZATION-20260803T141000Z`, fingerprint `sha256:59f21d0e18ca85fc3bc69e9871093ad9f03c1e422ec757d0307e8338c6b3c275`.
- Frozen window: `2026-08-03T00:00:00Z` through `2026-08-10T23:59:59Z`; ceilings were one FMP request, one Apps Script invocation, one Event-sheet upsert operation, one export read, and zero retries.
- Decision: `ROUND_2_CURRENT_EVENT_SNAPSHOT_BLOCKED`; `ROUND_2_FIRST_ROLLING_SLICE_MANIFEST_BLOCKED`; `ROUND_2_FIRST_SLICE_EXACT_DISPATCH_AUTHORIZATION_NOT_READY`.
- Execution stopped during Google client setup before Apps Script dispatch. Actuals: FMP requests `0`; Apps Script invocations `0`; Event-sheet writes `0`; export reads `0`; provider calls `0`; Outcome/evaluation activity `0`; remote state `CONFIRMED_NOT_DISPATCHED`.
- No current Event snapshot, Episode admission, Slice manifest, or provider-call identity was fabricated. The single-use refresh authorization is blocked and non-reusable pending a new explicit refresh authorization after the credential/client setup issue is resolved.

## Exact Next Round 2 Move

Resolve the Google client setup/credential transport blocker, then freeze a new bounded schedule-refresh authorization before attempting the canonical FMP/Apps Script refresh. Do not reuse the blocked authorization or prepare provider dispatch without a validated append-only Event snapshot.

## Round 2 Google Route Repair and Refresh Attempt

- Google route decision: `ROUND_2_GOOGLE_ROUTE_RESTORED`. The accepted explicit credential path `/Users/junhoshino/projects/presignal/local/token.json` loaded successfully and the idempotent `presignalRuntimeHealthCheck` returned `READY` with confirmed response state.
- Mechanical repair: use `google_clients.close_google_service` (the previously called transport-close helper does not exist) and perform the authorized Event export through one direct Sheets read rather than the independently retrying helper.
- New authorization: `PPHB-R2-SCHEDULE-REFRESH-AUTHORIZATION-20260803T142000Z` (`sha256:2e4bd7300b5098515e25edefe75da10402d633c2ea53bc9e2206d35970a0962c`), independent of and not a reactivation of the prior blocked authorization.
- Refresh decision: `ROUND_2_CURRENT_EVENT_SNAPSHOT_BLOCKED`; `ROUND_2_FIRST_ROLLING_SLICE_MANIFEST_BLOCKED`; `ROUND_2_FIRST_SLICE_EXACT_DISPATCH_AUTHORIZATION_NOT_READY`.
- The one authorized `apiUpsertEventWindow` invocation was submitted but did not return before the bounded wait was interrupted. Apps Script invocations: `1`; FMP requests: `UNKNOWN_UP_TO_1`; Event-sheet writes: `UNKNOWN_UP_TO_1`; export reads: `0`; retries: `0`; provider calls, Outcome collection, and evaluation: `0`; remote state: `UNKNOWN_POST_DISPATCH`.
- No snapshot, admission, manifest, forecast-call inventory, or dispatch authorization was created. The new refresh authorization is blocked and non-reusable. No further Google inspection or retry is permitted without a new explicit reconciliation authorization.

## Exact Next Round 2 Move

Freeze a narrowly scoped remote-state reconciliation authorization for `PPHB-R2-SCHEDULE-REFRESH-AUTHORIZATION-20260803T142000Z`. It must determine whether the submitted refresh wrote to the Event sheet without dispatching a new FMP request; only after certain reconciliation may a fresh export/snapshot authorization be considered.

## Round 2 Schedule Refresh Remote-State Reconciliation

- Reconciliation authorization: `PPHB-R2-SCHEDULE-REFRESH-RECONCILIATION-AUTHORIZATION-20260803T143000Z` (`sha256:928ad5f1b8467105d1253c6600560a443222143fc8d626d5d8abec755c64287b`), read-only and bound to the ambiguous `PPHB-R2-SCHEDULE-REFRESH-AUTHORIZATION-20260803T142000Z` invocation.
- Decision: `SCHEDULE_REFRESH_REMOTE_STATE_UNRESOLVED`; therefore `ROUND_2_CURRENT_EVENT_SNAPSHOT_BLOCKED`, `ROUND_2_FIRST_ROLLING_SLICE_MANIFEST_BLOCKED`, and `ROUND_2_FIRST_SLICE_EXACT_DISPATCH_AUTHORIZATION_NOT_READY` remain in force.
- Actual new activity: FMP `0`; Apps Script refresh invocations `0`; Event-sheet writes `0`; diagnostic reads `1`; retries `0`; provider, Outcome, and evaluation activity `0`.
- Read proof: canonical Event schema valid (`22` headers, `4,534` rows), `97` FMP rows in the authorized window, and zero duplicate window keys. The sheet has no invocation ID, upsert timestamp, raw-response fingerprint, or pre-dispatch baseline binding; the rows therefore cannot be attributed to the submitted refresh rather than pre-existing data. No snapshot, admission, manifest, or dispatch authority was created.

## Exact Next Round 2 Move

Do not retry or export under the blocked refresh. A new explicit governance decision is required to resolve the ambiguous remote state, for example through an authoritative operation-log or source-lineage capability that can attribute the original invocation without a new FMP request.

## Round 2 Attribution-Hardened Refresh Attempt

- Hardening decision: `ROUND_2_SCHEDULE_REFRESH_ATTRIBUTION_HARDENED` locally. The canonical source code now requires operation ID, authorization ID, source-window fingerprint, server invocation ID, pre/post Event-sheet fingerprints, timestamps, counts, and terminal remote state. Event semantics are unchanged.
- New authorization: `PPHB-R2-SCHEDULE-REFRESH-AUTHORIZATION-20260803T144000Z` (`sha256:83d702d6dfe1cc28ea4bc7bbf912056a47d4b084a4d5fa524fde23595c928735`), exact ceilings `1/1/1/1/0` for FMP, Apps Script, upsert, export, retries.
- Refresh decision: `SCHEDULE_REFRESH_REMOTE_STATE_UNRESOLVED`. The remote response was `ok` and reported `fetched=97`, `appended=0`, `upserts=97`, `skipped=0`, but omitted all attribution fields. This proves the deployed Apps Script route was pre-hardening; the local attribution controls were not active remotely.
- Actuals: FMP `1`; Apps Script `1`; Event-sheet upsert operation `1`; export read `1`; retries `0`; provider calls `0`; Outcome/evaluation `0`. The Event export is preserved as `DIAGNOSTIC_ONLY_NOT_AUTHORITATIVE`; no Episode admission, Slice manifest, or provider-dispatch authorization was created.
- The earlier ambiguous refresh remains permanently `SCHEDULE_REFRESH_REMOTE_STATE_UNRESOLVED_NON_REUSABLE` and was not reopened. The new authorization is also non-reusable. No further refresh or retry is authorized.

## Exact Next Round 2 Move

Publish/activate the attribution-hardened Apps Script route under a separately authorized deployment change, then run a new one-call refresh authorization. The existing 144000Z Event export cannot be promoted without server-side attribution.

## Round 2 Hardened Deployment Attempt

- Decision: `ROUND_2_HARDENED_APPS_SCRIPT_DEPLOYMENT_BLOCKED`.
- Authorization: `PPHB-R2-SCHEDULE-ATTRIBUTION-DEPLOYMENT-AUTHORIZATION-20260803T150000Z` (`sha256:e0e6458043422251f47c08449104db2ef1b40374a40cb1a8da0874ad150b06c3`). The local source fingerprint is `sha256:5c9558f51b6ea7cca8f905b543ef3306d9e6a0acd9a5d07f2c33d7dc8acbf670`.
- Certain partial-operation boundary: one Apps Script source update and one version creation completed; zero deployment activations and zero schedule refresh operations occurred. The project returned five `EXECUTION_API` deployments, but accepted evidence supplied no exact deployment ID or deterministic selection rule. Activation therefore failed closed before live route verification.
- Preserved activity: FMP `0`; Apps Script refresh `0`; Event-sheet writes `0`; Event export reads `0`; provider, Outcome, and evaluation activity `0`; retries `0`; remote state `CONFIRMED_RESPONSE`.
- The deployment authorization is non-reusable after its partial operation. Both prior refresh authorizations remain permanently non-reusable and their evidence is unchanged. No authoritative Event snapshot, Round 2 Episode admission, Slice manifest, or provider-dispatch authorization exists.

## Exact Next Round 2 Move

Freeze a new deployment authorization that binds exactly one accepted `EXECUTION_API` deployment ID in project `1A-iJDmNb1RFSCGS9YIPJfboNCO3sGUS1OomKf4yyQhQceSJlgXqWdGA9`, activates the already-created hardened version after a deterministic selection proof, verifies the attribution contract, and only then separately authorizes one new attributed schedule refresh.

## Round 2 Authoritative Deployment Binding and Refresh Attempt

- Deployment authority: `AUTHORITATIVE_EXECUTION_API_DEPLOYMENT_CONFIRMED`. The historically accepted Round 1 endpoint `AKfycbw-SXeE8pE85mISnpH_xygFLjgysQqGpzAmcj9h8P9kRg4LCq3iI7BnoB5hYL-x72xN` is the sole selection target, proven by accepted collection and attachment invocation lineage rather than version, description, recency, or list order.
- Binding authorization: `PPHB-R2-SCHEDULE-ATTRIBUTION-DEPLOYMENT-BINDING-AUTHORIZATION-20260804T000000Z` (`sha256:61a5dc5d1faceeb59cdd4b6de6d4d40d43b299cdd06444f48cbff7f173867f6b`). It updated only that deployment from version `82` to the previously created hardened version `83`; source fingerprint `sha256:5c9558f51b6ea7cca8f905b543ef3306d9e6a0acd9a5d07f2c33d7dc8acbf670`.
- Deployment result: `ROUND_2_HARDENED_APPS_SCRIPT_DEPLOYED`; remote state certain. The live read-only probe returned the required attribution schema. No unrelated Apps Script, Event-sheet, provider, Outcome, or evaluation operation occurred.
- New refresh authorization: `PPHB-R2-SCHEDULE-REFRESH-AUTHORIZATION-20260803T151000Z` (`sha256:771f69fbf645849603e37944aa82fcdfc5bc3db31b8b74c3a40810490946edb4`), one FMP request, one Apps Script invocation, one Event upsert operation, one export read, and zero retries.
- Refresh result: `SCHEDULE_REFRESH_REMOTE_STATE_UNRESOLVED`. Intent `R2SCHEDOP_b1aa318ac0a9fb92002b789b` was persisted before the sole invocation, but no attributable response or terminal record was persisted. Actuals are Apps Script `1`, FMP `UNKNOWN_UP_TO_1`, Event write `UNKNOWN_UP_TO_1`, export `0`, retries `0`; provider, Outcome, and evaluation activity `0`. The refresh authorization is blocked and non-reusable.
- No authoritative Event snapshot, Episode admission, Round 2 Slice manifest, forecast-call inventory, or provider-dispatch authorization was created.

## Exact Next Round 2 Move

Freeze a separate read-only reconciliation authorization for `R2SCHEDOP_b1aa318ac0a9fb92002b789b`. It must establish the invocation's remote state from attributable operation-journal or Apps Script evidence without a new FMP request or Event write; do not export, admit, or dispatch unless that state is certain.

## Round 2 Refresh Completion Correction

- Correction: `SCHEDULE_REFRESH_COMPLETED_CONFIRMED`. The same invocation completed after the initial local evidence read. Its attributable execution record binds operation `R2SCHEDOP_b1aa318ac0a9fb92002b789b`, invocation `eab72393-d5e7-4088-8d4a-3cc5b06152d6`, authorization `151000Z`, terminal status `COMPLETED`, and remote state `CERTAIN`.
- Counts: fetched `97`; appended `0`; upserts `97`; unchanged `0`; rejected/cancelled/superseded `0`; pre/post Event fingerprints both `sha256:aaea9d5ab06a73f04f72d689163b6b4bc8efbfbd418c8cb899f68beb194eac78`.
- Snapshot: `PPHB-R2-CURRENT-EVENT-SNAPSHOT-20260803T151000Z` (`sha256:afab082d51abdd725b7c1a802c3391673de91e65c2b964b5cd31a29f3475b6d9`) is authoritative. The earlier blocker is retained but superseded by append-only completion correction.
- Stop: `ROUND_2_PROSPECTIVE_PROMPT_AND_CUTOFF_BINDINGS_NOT_FROZEN`. No accepted Round 2 artifact binds exact Pack A and Pack E prompt fingerprints and per-Episode prospective forecast cutoffs. No Episode admission, Slice manifest, forecast-call inventory, or dispatch authorization was created.

## Round 2 Prompt and Cutoff Authority Review

- Decisions: `ROUND_2_PACK_PROMPT_AUTHORITY_BLOCKED`; `ROUND_2_PROSPECTIVE_CUTOFF_AUTHORITY_BLOCKED`; `ROUND_2_FIRST_ROLLING_SLICE_MANIFEST_BLOCKED`; `ROUND_2_FIRST_SLICE_EXACT_DISPATCH_AUTHORIZATION_NOT_READY`.
- The Round 2 protocol/envelope define Pack roles, provider routes, and a pre-release cutoff requirement, but do not select one prospective Pack A prompt, one prospective Pack E prompt, or one numeric cutoff offset. Historical Round 1 prompt variants cannot be promoted by inference.
- No provider, Google, market-data, Outcome, or evaluation activity occurred. No Event was admitted and no dispatch authorization was created.

## Exact Next Round 2 Move

Freeze explicit Round 2 Pack A and Pack E prompt artifacts with fingerprints/output contracts and one numeric prospective cutoff rule, then apply that new authority to the authoritative Event snapshot.

## Round 2 Prompt Authority Reconciliation

- `ROUND_2_PACK_PROMPT_AUTHORITY_FROZEN`: the accepted future-only migration provides one exact static instruction for both prospective Packs: `presignal_event_path_contract_v1_1_single_pair_validation_no_signal_confidence_explicit_v1` (`sha256:2515e6c09742e58507efe8d9196ba58473c01f2d5bb9e8b5405405088d323a77`). Pack A remains `BASELINE` and Pack E `FULL_CONTEXT` through the canonical, fingerprinted Pack-input construction; sharing the static instruction does not merge Pack lineage.
- `ROUND_2_PROSPECTIVE_CUTOFF_AUTHORITY_BLOCKED`: the protocol and envelope specify only `information_cutoff_ts <= prompt_freeze_ts < forecast_freeze_deadline_ts < release_ts`. They do not pre-specify a numeric offset, minimum lead time, clock source, dispatch-window start, or revised-release recalculation rule. Historical and fixture timestamps remain non-authoritative.
- No snapshot rows were classified or admitted; no Slice manifest, forecast-call inventory, or dispatch authorization exists. Provider, Google, market-data, Outcome, evaluation, and retry activity: `0`.

## Exact Next Round 2 Move

Freeze one explicit prospective cutoff policy with its numeric release-relative offset, clock authority, revised-release handling, and dispatch window; then apply it to the accepted Event snapshot together with the already frozen prompt authority.

## Round 2 T-15 Cutoff and First Slice Preparation

- Amendment `PPHB-R2-T-MINUS-15-CUTOFF-PROTOCOL-AMENDMENT-20260804T013000Z` is frozen with fingerprint `sha256:a4200c3e5704ea1ba172967847e71d664f63b75d64c013fe2fbaf78ee0290085`: `forecast_cutoff_utc = authoritative release_timestamp_utc - 15 minutes`, UTC comparison, one-second precision, strict pre-cutoff dispatch, zero retries, release-revision recalculation, and fail-closed ambiguity handling.
- The accepted Event snapshot was classified at recorded UTC `2026-08-03T15:35:13Z`: `4,268` historical; `174` authority-unresolved; `3` already released; `1` identity/instrument-invalid; `88` eligible prospective; `0` future-not-yet-admitted; `0` past-cutoff; `0` cancelled/superseded; `0` synthetic/dry-run.
- First Slice `PPHB-R2-FIRST-ROLLING-SLICE-001-20260804T013000Z` contains `31` Episodes and `186` exact calls: `93` Pack A, `93` Pack E, with `62` calls per fixed provider/model route. Manifest fingerprint: `sha256:4eba0d76f06bc29b3c6360acf1c0d18153c2a0d59ae40e02df995b1aa636342e`.
- Dispatch authorization `PPHB-R2-FIRST-ROLLING-SLICE-DISPATCH-AUTHORIZATION-20260804T013000Z` is frozen preparation-only with fingerprint `sha256:04bd63ca29550357bbf49161d862291fba7b4aafe4676e1342b1b9cec1c73692`; it is not active. Timing classification is `186 DISPATCH_DUE_NOW`, `0 FROZEN_NOT_YET_DISPATCHABLE`, `0 CUTOFF_PASSED_NOT_AUTHORIZED`. Provider, Google, market-data, Outcome, evaluation, and retry activity: `0`.

## Exact Next Round 2 Move

Activate the exact first-Slice provider-dispatch authorization and dispatch only the enumerated calls after an immediate T−15 cutoff recheck.
