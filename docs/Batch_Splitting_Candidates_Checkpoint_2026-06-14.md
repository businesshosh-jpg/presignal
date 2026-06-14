# Batch Splitting Candidates Checkpoint - 2026-06-14

## Decision Status

Status labels:

- `family_structure_investigation_v1_status = active_diagnostic`
- `batch_splitting_candidates_v1_status = diagnostic_review_layer`
- `batch_splitting_v1_behavior_status = not_approved`
- `family_rule_v1_behavior_status = not_approved`
- `next_decision = review_high_priority_split_candidates`

`Batch_Splitting_Candidates` is a diagnostic ranking layer. It does not approve live batch splitting, family-rule behavior, prompt changes, scoring changes, routing, weighting, calibration, or subscriber-facing changes.

## Source Evidence

Current source layers:

- `Family_Structure_Report`
- `Batch_Splitting_Candidates`
- existing outcome/evaluation/attention reports used by `Family_Structure_Report`

Current build result:

- `Family_Structure_Report`: 1669 rows
- `Batch_Splitting_Candidates`: 275 rows
- `Batch_Splitting_Candidates` warnings: 0

Candidate priority distribution:

- `high_priority_diagnostic`: 20
- `medium_priority_diagnostic`: 146
- `low_priority_diagnostic`: 109

Top repeated candidate combos:

- `housing+other`
- `energy+positioning`
- `inflation+other`
- `labor+other`
- `growth+other`

## High-Priority Review

The 20 high-priority diagnostic rows all share the same split reason:

`mixed_family_batch|low_signal_family_present|best_member_outperformed_batch`

High-priority family-combo distribution:

- `housing+other`: 5
- `growth+other`: 5
- `labor+other`: 4
- `inflation+other`: 2
- `central_bank+energy`: 2
- `central_bank+housing`: 2

Month distribution:

- 2024-05: 5
- 2024-06: 1
- 2024-07: 2
- 2024-08: 2
- 2024-09: 2
- 2024-10: 3
- 2024-11: 3
- 2024-12: 2

Interpretation:

The high-priority rows are not random one-off failures. They cluster around repeated same-minute releases where a primary family is bundled with low-signal or `other` members, and the existing best-member comparison suggests the member-level signal may be cleaner than the batch aggregate.

The strongest near-term review targets are:

1. `growth+other`: durable goods / ISM / construction-spending style clusters.
2. `housing+other`: housing-price / housing-activity clusters mixed with inventories, current account, or press-conference style rows.
3. `labor+other`: claims or payroll clusters mixed with trade, productivity, corporate-profit, or inventory rows.

Secondary review targets:

- `inflation+other`
- `central_bank+energy`
- `central_bank+housing`

These secondary targets have fewer problematic rows and should not drive behavior design alone.

## Interpretation

The current evidence supports further diagnostic review of batch construction, especially mixed-family batches where a clear macro family is paired with low-signal or `other` members.

The strongest cases are not merely mixed-family batches. They are mixed-family batches where:

- a low-signal or `other` member is present
- best-member outcome appears stronger than the batch-level result
- the family combination recurs across multiple batches

This suggests the next bottleneck may be event structure or batch evaluation noise, not provider individuality or attention-factor routing.

## What This Does Not Prove

The checkpoint does not prove that live batch splitting would improve predictions.

It does not prove that current batch creation is wrong in all mixed-family cases.

It does not prove that every `family+other` batch should be split.

It does not authorize changing `Event`, `Predictions`, scoring, prompts, market reaction logic, or subscriber-facing behavior.

## Review Questions

Before any future `Batch Splitting v1` design, review the high-priority diagnostic rows and answer:

1. Are the high-priority candidates true structural problems or expected noisy batches?
2. Are `other`/low-signal members diluting batch anchors or evaluation targets?
3. Do `growth+other`, `housing+other`, `labor+other`, or `inflation+other` repeat enough to justify a future split design?
4. Would a family-split diagnostic comparison preserve the best-member signal better than the current aggregate?
5. Are some cases better solved by family classification cleanup rather than batch splitting?

## Evidence Required Before Behavior Change

Future behavior change would require a separate spec and stronger evidence, such as:

- repeated high-priority candidates across future backtest blocks
- stable improvement in family-split diagnostic comparison
- no evidence that splitting damages coherent macro clusters
- clear identity semantics for synthetic split groups
- deterministic rebuild behavior and auditability
- explicit approval to alter batching behavior

## Current Recommendation

Recommendation: `review_high_priority_split_candidates`.

Do not implement live `Batch Splitting v1` yet.

High-priority review result: enough repeated structure exists to justify a shadow-only counterfactual report.

Next build recommendation:

`Batch_Split_Counterfactuals`

This should compare current batch-level results against hypothetical family-split groupings using existing scored data only. It must not alter live batching, `Event`, `Predictions`, scoring, prompts, market reaction logic, or subscriber-facing behavior.

Implementation boundary:

The v1 shadow counterfactual may use a best-member-derived split proxy where true family-split group outcomes are not available. Any such proxy must be labeled clearly and must not be described as a new prediction or proof that live splitting would improve results.

## Batch Split Counterfactuals v1 Result

`Batch_Split_Counterfactuals` was implemented as a shadow-only proxy report over the 20 high-priority `Batch_Splitting_Candidates` rows.

Build result:

- `Batch_Split_Counterfactuals`: 20 rows
- `activation_status = shadow_only`: 20 rows
- warnings: 0

Counterfactual labels:

- `split_proxy_helped`: 20
- `inconclusive_missing_baseline`: 0

Evidence labels:

- `strong_shadow_evidence`: 10
- `moderate_shadow_evidence`: 10

Interpretation:

The high-priority split-candidate structure is stronger than the first candidate review suggested. After mapping observed batch baselines directly from `Evaluation_BatchCompare`, all 20 high-priority rows show a positive best-member-derived split proxy versus current batch baseline.

This is still not approval for live batch splitting because the proxy uses best-member outcomes, not a true family-split prediction or evaluation path.

Updated recommendation:

`design_true_shadow_split_group_counterfactual`

The next diagnostic layer should test true shadow split groups, not live behavior. It should compare current batch outcomes against deterministic family-split groups using existing member rows and preserve all identity semantics.

## Batch Baseline Coverage Audit Result

`Batch_Baseline_Coverage_Audit` was implemented to check whether missing baselines were caused by source coverage gaps.

Build result:

- `Batch_Baseline_Coverage_Audit`: 21 rows
- batch audit rows: 20
- summary rows: 1
- warnings: 0

Coverage labels:

- `baseline_available`: 20

Summary label:

- `baseline_coverage_ok`

Interpretation:

The blocker is not missing scored batch baseline coverage. The earlier missing-baseline result was a derived-report mapping issue, repaired by reading observed batch baselines from `Evaluation_BatchCompare`.

## Batch Split Group Counterfactuals Result

`Batch_Split_Group_Counterfactuals` was implemented as the true shadow family-group counterfactual over existing scored member rows.

Build result:

- `Batch_Split_Group_Counterfactuals`: 20 rows
- warnings: 0
- `activation_status = shadow_only`: all rows

Counterfactual labels:

- `family_group_helped`: 4
- `family_group_hurt_vs_best_member`: 16

Evidence labels:

- `strong_group_shadow_evidence`: 1
- `moderate_group_shadow_evidence`: 3
- `possible_proxy_damage`: 16

Interpretation:

The earlier best-member proxy overstated the case for batch splitting. True family-group shadow evidence is mixed: family groups often improve over the full batch baseline, but usually underperform the best-member proxy. This means the current evidence does not justify live batch splitting.

Updated recommendation:

`do_not_promote_batch_splitting_yet`

Preserve these sheets as diagnostics. If development continues, the next question should be narrower: whether a small number of family-combo patterns such as `housing+other` or `growth+other` deserve a stricter design review, not broad batch splitting.
