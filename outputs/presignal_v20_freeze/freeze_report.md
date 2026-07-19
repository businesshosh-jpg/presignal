# PreSignal v2.0 Freeze

## Scope

This record freezes the completed PreSignal v2.0 Market Session experiment. It is preservation-only: no replay, repair, rescore, migration, workbook edit, Google Sheets write, provider invocation, or market-data acquisition was performed.

## What v2.0 tested

The frozen question was whether the shared request-driven Market-State Pack E improved Market Session forecasting performance compared with Pack A (no Market-State Pack). The primary forecast object was the **Market Session**. The independent scientific and primary outcome unit was also the **Market Session**, evaluated under the frozen session outcome, evaluation-window, direction, action-value, pairing, exclusion, and holdout rules.

## Authoritative result

The frozen holdout contained 65 Market Sessions and 186 exact Pack A/E pairs. The recovered population contained 249 candidate sessions, 239 replayed sessions, 195 usable sessions, 1,145 attached Predictions, and 562 exact Pack A/E provider-session pairs.

| Measure | Pack A | Pack E | E minus A |
| --- | ---: | ---: | ---: |
| Mean action value | -0.002564 | -0.010256 | -0.007692 |
| Direction accuracy | 49.45% | 48.39% | - |

The primary session-clustered 95% confidence interval for the action-value difference is `[-0.238526, 0.228205]`.

**Final decision: `INSUFFICIENT_EVIDENCE_OF_PACK_E_IMPROVEMENT`.**

The valid interpretation is: under the frozen v2.0 Market Session forecast and evaluation contract, there was insufficient evidence that Pack E improved forecasting performance over Pack A.

## Frozen Git identity

- Frozen commit: `fe6fbbe779c4d0808a3271c333e4b2f00f25016f`
- Annotated immutable tag: `presignal-v2.0-frozen`
- Tag target: `fe6fbbe779c4d0808a3271c333e4b2f00f25016f`
- Branch at freeze: `codex-simplified-authoritative-replay`
- Tag push: not performed

## Preserved scorer and contract

The exact frozen scorer and contract are addressable at the frozen commit:

- `automation/pack_ae_scoring_v1.py`
- `apps_script/market_scoring.js`
- `apps_script/evaluation_report.js`
- `automation/simplified_authoritative_replay_contract_v1.py`
- `docs/pack_ae_evaluation_contract_v1/evaluation_contract.json`
- `docs/pack_ae_evaluation_contract_v1/historical_split_manifest.json`
- `automation/test_pack_ae_scoring_v1.py`
- `automation/test_pack_ae_evaluation_contract_v1.py`

The checked frozen implementation files match commit `fe6fbbe779c4d0808a3271c333e4b2f00f25016f` with no working-tree diff.

## Pack A/E definitions

Pack identity, allowed information differences, provider/model equality, prompt equality, cutoff rules, source lineage, fingerprints, and experiment-arm semantics are preserved by:

- `automation/freeze_pack_ae_evaluation_contract_v1.py`
- `docs/pack_ae_evaluation_contract_v1/binding_manifest.json`
- `docs/pack_ae_evaluation_contract_v1/evaluation_contract.json`
- `docs/pack_ae_scoring_v1/scorer_binding.json`

No Pack B, C, or D definition was added or changed.

## Replay and result artifacts

The frozen replay package, raw/provider ledgers, accepted predictions, provenance checks, canonical outcomes, exact outcome attachment, evaluation readiness records, coverage audit, and confirmatory evaluation remain in `outputs/simplified_authoritative_replay/`. The authoritative scientific result is:

`outputs/simplified_authoritative_replay/evaluations/PRESIGNAL-V2-PACK-AE-CONFIRMATORY-HOLDOUT-EVALUATION-20260718T180602Z/scientific_result_summary.json`

Its recorded artifact fingerprint is `a95d0f78f7dbfdf7d544347ad70aa71581fa7eebf9e60bb996fe02eb15a9b17b`. The confirmatory artifact manifest’s three file hashes were independently verified in this task.

## Legacy workbooks

Legacy workbook evidence remains untouched. Existing repository configuration records the legacy main Sheet `1_gZGnd6h3VzdiBvGBHRSxn78KW8tsOi2UEc6Y_Sc23Q`, diagnostics Sheet `1jxcZotbzJKcAzrK0VhxetYX6hp5DPXCCIA0J6B6RUy0`, and archive Sheet `12hi1rugE_F-MhlupgmL13BIagerzA8CZkm1sk_nHPSg`. They were not contacted. No local workbook outside this repository was accessed.

## Limits of this result

This freeze does not repair or critique v2.0. Its conclusion is not evidence of equivalence, not a production claim, and not an Event-Path result. It neither proves nor disproves the v2.1 Event-Path hypothesis.

PreSignal v2.1 is a new Event-Path hypothesis built on this stable v2.0 foundation. It must define and freeze its own Episode, Prediction, Prediction Path, Outcome, and Evaluation contracts before any execution work begins.

## Validation

- Frozen commit and tag target: verified.
- Authoritative result and requested population/holdout figures: reconciled.
- Frozen scorer, contracts, Pack A/E definitions, replay package, and result files: located.
- Confirmatory artifact hash validation: passed.
- Preservation defects: none found.
- Provider calls, market-data calls, Apps Script calls, Google Sheets writes, and production-routing changes: zero.
