# PreSignal v2.1 Frozen Batch Paired Analysis

## Scope
Read-only analysis of the frozen Step 6 batch. Rejected outputs remain excluded; no provider, market-data, Apps Script, workbook, or Google Sheets operation occurred.

## Primary Endpoint
Complete provider/Episode pairs: 14. Pack A correct: 6 (0.4286); Pack E correct: 4 (0.2857).
Paired risk difference (A - E): 0.1429; exact McNemar p=0.6250; conservative interval=[-0.33268285425419064, 0.5568797677577234].
Episode-cluster exact label-swap: 10 clusters, 1024 permutations, p=0.6250.

## Missingness
Pack A accepted 15/21; Pack E accepted 17/21; complete paired 14/21.

## Output Contract
Rejected responses: 10; frozen reasons: {'PATH_NEUTRAL_PIP_RANGE': 6, 'PATH_PIPS_MIN': 1, 'PREDICTION_REVERSAL_FLAG': 3}. Six repeated FLAT-stage pip-range violations are a prospective output-contract prevention candidate; all historical rejections remain excluded.

## Attention
Adequate: 14/14; extension candidates: 0.

## Decision
V2_1_STEP7_TARGETED_OUTPUT_CONTRACT_REPAIR_REQUIRED: The repeated mechanical output-contract violation materially reduced paired completion, while the observed arm difference remains uncertain under Episode clustering and missingness bounds.

No Pack-superiority claim is supported by this analysis.
