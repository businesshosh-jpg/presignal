# Attention Factor Checkpoint - 2025-01-31

## Decision

Status labels:

- `attention_factor_v1_status = frozen_explainability`
- `attention_factor_v1_goal_1_status = successful_provider_individuality_layer`
- `attention_factor_v1_goal_2_status = not_approved_for_routing_or_weighting`
- `attention_phase_3a_v1_promotion_status = closed_frozen`
- `attention_phase_3b_status = not_approved`
- `next_active_track = family_rule_and_batch_splitting`
- `next_active_track_report = Family_Structure_Report`
- `future_item = attention_factor_v2_causal_attention_experiment`

Attention Factor Selection v1 is preserved as an explainability and provider-individuality diagnostics layer.

Do not promote v1 to Phase 3B. Do not activate provider routing, provider weighting, calibration, behavior overrides, or subscriber-facing changes from v1 attention evidence.

## Goal 1 Result

Provider individuality / explainability is confirmed enough to preserve Attention Factor Selection v1 as a successful diagnostics layer.

Checkpoint evidence:

- `Attention_Provider_Individuality`: 1911 rows
- primary attention-factor divergence: 1447 / 1676
- divergence rate: 0.8634
- same direction, different attention factors: 1136
- same direction, same factor: 210

Provider habits:

- Anthropic: `low_signal_event`, `hidden_detail_risk`, `missing_consensus`
- Gemini: `direct_fx_transmission`, `missing_consensus`, `low_signal_event`
- OpenAI: `importance`, `low_signal_event`, `missing_consensus`

Interpretation: providers report distinct, recognizable attention-factor habits even when prediction direction often converges.

## Goal 2 Result

Phase 3A did not clear promotion evidence.

Checkpoint evidence:

- `Attention_Shadow_Summary`: 173 `reject_or_monitor`
- `Attention_Shadow_Summary`: 103 `not_ready`
- 0 `watchlist_candidate`
- 0 `strong_shadow_candidate`

Interpretation: v1 attention evidence does not support Phase 3B, routing, weighting, calibration, or behavior-control behavior.

## Causality Boundary

Current Attention Factor v1 is one-shot:

`event payload -> one provider response -> prediction + attention_factors together`

This proves provider-reported individuality and explanation diversity. It does not prove causal attention steering. Do not claim that attention factors caused prediction differences in v1.

## Preserved v1 Role

Preserve Attention Factor v1 as:

- explainability layer
- provider personality diagnostics
- future learning/recalibration input
- non-control shadow metadata

The existing v1 reports remain derived-only read-only layers.

## Future Roadmap

`Attention Factor v2 - Causal Attention Experiment` is a future experimental item.

Purpose:

- test whether selecting attention factors before prediction changes prediction behavior
- compare against current one-shot v1 baseline

Proposed future architecture:

1. provider chooses 2-3 attention factors only
2. provider generates prediction using those selected factors as primary reasoning anchors
3. compare behavior and outcomes against v1

Boundary:

- future experiment only
- not production
- not subscriber-facing
- not replacing v1
- not Phase 3B approval

## Next Active Track

### Next Track: Family Rule / Batch Splitting Investigation

Redirect active development toward recurring findings:

- `family_rule`
- `batch_splitting`

Purpose:

Determine whether recurring `family_rule` and `batch_splitting` patterns point to a stronger structural source of prediction error or evaluation noise than provider-level attention routing.

Why this matters:

Attention Factor v1 showed providers are not clones, but it did not produce control or routing evidence. Recurring `family_rule` and `batch_splitting` findings may indicate that the next bottleneck is event structure, family classification, batch construction, or comparison logic rather than provider individuality.

Scope:

- diagnostics, reporting, and design investigation only
- no live prediction behavior change yet
- no prompt change yet
- no scoring change yet
- no routing or provider weighting
- no Phase 3B promotion

Questions to answer:

1. Are certain event families being grouped, compared, or scored incorrectly?
2. Are same-minute batches mixing unrelated or weakly related events?
3. Does batch-level prediction lose signal compared with member-level prediction?
4. Are family rules needed before any provider weighting or routing can work?
5. Is `batch_splitting` a better accuracy-improvement path than Attention Factor routing?
6. Are `family_rule` findings pointing to deterministic system structure issues rather than AI-provider issues?

This track is a candidate investigation, not an implemented behavior change.

Initial reporting layer:

- `Family_Structure_Report`

The report is a derived-only read-only investigation sheet. It summarizes family performance, batch composition, batch-vs-member comparison, family mixing risk, recurring `family_rule` findings, and recurring `batch_splitting` findings. It exists to decide whether future `Family Rule v1` or `Batch Splitting v1` work is justified, not to implement either behavior.

## Safety Constraints

- no prediction prompt changes
- no prediction semantic changes
- no scoring changes
- no provider weighting
- no calibration
- no market reaction logic changes
- no subscriber-facing behavior changes
- no direct trading advice
