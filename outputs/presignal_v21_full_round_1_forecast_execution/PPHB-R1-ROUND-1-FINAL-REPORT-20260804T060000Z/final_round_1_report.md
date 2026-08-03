# PreSignal v2.1 Round 1 Final Report

## Executive Summary

Decision: `ROUND_1_FINAL_REPORT_COMPLETE`. Evidence strength: **moderate descriptive evidence**. The primary T+15 directional accuracy result favors Pack E descriptively, both on Pack-specific pooled denominators and on the common paired-scoreable population. This is not inferential evidence and does not prove superiority or support replacing Pack A.

## Study Population And Exclusions

The final aggregate binds eleven accepted Slice evaluation artifacts: 518 evaluated forecast records, 259 Pack A records, 259 Pack E records, and 259 complete Pack A/E pairs. It preserves ten paired-excluded unavailable Episodes, three authority/attention-lineage exclusions, and three terminal-invalid forecasts. No excluded, unresolved, or unevaluated record is included.

## T+15 Primary Result

| Pack | Numerator | Denominator | T+15 directional accuracy |
|---|---:|---:|---:|
| Pack A | 87 | 208 | 0.418269 |
| Pack E | 113 | 252 | 0.448413 |

The observed descriptive difference favors Pack E. Pack-specific denominators differ because valid no-signal forecasts are excluded from directional denominators, so this comparison alone combines directional accuracy with different coverage behavior.

## Common Paired-Scoreable Comparison

| Population | Pack A | Pack E | A-E |
|---|---:|---:|---:|
| 206 common paired T+15-scoreable observations | 86/206 (0.417476) | 100/206 (0.485437) | -0.067961 |

This is the appropriate descriptive comparison for the same scoreable Pack A/E observations. It retains the observed Pack E advantage, but no statistical significance, confidence interval, hypothesis test, or generalization was calculated.

## Immediate Impulse Status

Immediate Impulse directional accuracy is secondary and `NOT_APPLICABLE_STRICT` for both Packs. There were zero strictly `SUPPORTED` Outcomes; `APPROXIMATION_ONLY` records were not converted into strict scores.

## Supporting Metrics

| Metric | Pack A | Pack E | Descriptive pattern |
|---|---:|---:|---|
| Magnitude interval error | 8.052163 pips | 7.186706 pips | Lower for Pack E |
| T+5 horizon accuracy | 88/208 (0.423077) | 112/252 (0.444444) | Higher for Pack E |
| T+30 horizon accuracy | 68/208 (0.326923) | 84/252 (0.333333) | Higher for Pack E |
| T+60 horizon accuracy | 72/208 (0.346154) | 91/252 (0.361111) | Higher for Pack E |
| Path accuracy | 0.378606 | 0.396825 | Higher for Pack E |
| Reversal accuracy | 104/208 (0.500000) | 118/252 (0.468254) | Higher for Pack A |

The favorable Pack E pattern spans the primary endpoint, magnitude interval error, the reported horizon accuracies, and path accuracy. Reversal accuracy is an exception, so the results are not uniformly favorable to Pack E across every authorized metric.

## No-Signal And Coverage Interpretation

Pack A had 51 no-signal exclusions from directional denominators; Pack E had 7. Pack E therefore issued a directional forecast on more evaluated records, while Pack A was more selective. This affects Pack-specific denominator comparability: Pack E's pooled result may reflect greater directional willingness, better conditional directional accuracy, or both. The 206 common paired-scoreable observations remove the pair-level no-signal mismatch for the direct descriptive T+15 comparison, but they do not turn the result into inferential evidence. No coverage-adjusted score was calculated.

## Limitations And Scientific Conclusion

The evidence is moderate descriptive evidence, not inferential evidence. It does not establish statistical significance, causal mechanism, broader generalization, provider selection, meta-forecast performance, or a Pack-level winner. Immediate Impulse provides no strict secondary corroboration. The large no-signal imbalance and different Pack-specific denominators require the common paired-scoreable population for direct descriptive comparison.

Continue Pack E development as a hypothesis-supported arm and retain Pack A as the baseline comparator. Do not replace Pack A, change Pack definitions, or introduce provider selection from this result alone.

## Recommended Next Move

Prepare one narrowly scoped authorization for an inferential paired T+15 comparison on the frozen 206 common paired-scoreable observations. It should use only accepted aggregate rows, perform no external access, preserve Pack separation, state the exact test and assumptions before execution, and leave coverage analysis, provider decomposition, Immediate Impulse recovery, Pack redesign, and Round 2 outside scope.

## Prohibited Overinterpretations

Do not describe Pack E as established as superior, statistically significant, causal, or ready to replace Pack A. Do not select providers, create a meta-forecast, calculate a composite score, mine subgroups, or claim Immediate Impulse support.

## Artifact And Lineage References

- Aggregate authorization: `PPHB-R1-AGGREGATE-EVALUATION-AUTHORIZATION-20260804T050000Z`, `sha256:806ff5fb1d37c42209690fa601101d7590fb96a856bde491ba16285d284ba0d7`.
- Aggregate result: `PPHB-R1-ROUND-1-AGGREGATE-EVALUATION-RESULT-20260804T050000Z`.
- Stage completion: `PPHB-R1-PROSPECTIVE-OUTCOME-EVALUATION-STAGE-COMPLETION-20260804T040000Z`.
- Final report artifact: `PPHB-R1-ROUND-1-FINAL-REPORT-20260804T060000Z`.
