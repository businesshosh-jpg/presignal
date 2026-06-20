# Attention Phase3 Candidates Checkpoint (through 2024-12-06)

## Scope

This checkpoint freezes the current Phase 2C disagreement review state after the clean backtest block ending 2024-12-06.

Source rebuilds used:

- `Attention_Disagreement_Review`
- `Attention_Disagreement_Summary`
- `Attention_Phase3_Candidates`

These remain derived analysis layers only.

## Rebuild Snapshot

- `Attention_Disagreement_Review`: `180` rows
- `Attention_Disagreement_Summary`: `119` rows
- `Attention_Phase3_Candidates`: `73` rows

## Disagreement Review Snapshot

Case-level disagreement outcomes:

- `useful_disagreement`: `71`
- `possible_signal`: `6`
- `no_clear_winner`: `95`
- `unscored_or_thin`: `8`

Interpretation:

- useful disagreement exists and is repeatable
- ties still dominate overall
- disagreement evidence is informative, but not strong enough for live behavior control

## Candidate Sheet Snapshot

Candidate type counts:

- `family_winner_factor`: `48`
- `winner_factor`: `23`
- `family_winner`: `2`

Most repeated candidate slices:

- `other | OpenAI | consensus_surprise`: `12`
- `growth | Gemini | consensus_surprise`: `12`
- `other | Gemini | consensus_surprise`: `8`
- `energy | OpenAI | consensus_surprise`: `5`
- `labor | Gemini | consensus_surprise`: `5`
- `housing | Gemini | consensus_surprise`: `5`

Provider-level disagreement winner patterns still observed:

- `Gemini | consensus_surprise`: `40`
- `OpenAI | consensus_surprise`: `30`

## Current Reading

The candidate layer is doing the intended job:

- it filters to disagreement cases with repeated Phase 2C support
- it keeps the output explicitly candidate-only
- it does not activate weighting, calibration, output overrides, or provider-role control

The present evidence supports a later controlled shadow comparison design, but does not yet justify direct behavior change in the live prediction path.

## Next Planned Move

Keep the current behavior unchanged.

After the next clean backtest block:

1. rebuild the disagreement layers again
2. rebuild `Attention_Phase3_Candidates`
3. compare whether the same provider/family/factor slices persist
4. only then decide whether to draft a narrow Phase 3 shadow comparison design
