# Confirmatory Prospective Round 2 Protocol

Protocol ID: `PPHB-R2-CONFIRMATORY-PROSPECTIVE-PROTOCOL-20260804T080000Z`
Fingerprint: `sha256:d417e4c76d3d38d471dbc76cbf361be4a28dac1b615ecccdc8aa18c37262362f`

## Purpose

Round 2 is a prospective confirmatory comparison of Pack A, the baseline, and Pack E, the hypothesis-supported experimental arm. It tests a difference in T+15 directional accuracy while separately reporting forecast coverage and NO_SIGNAL behavior. It does not authorize Pack replacement, provider selection, a meta-forecast, a new Pack, or a trading decision.

Round 1 is preserved as May-July 2024 historical evidence: 46 both-correct pairs, 40 Pack-A-only-correct pairs, 54 Pack-E-only-correct pairs, 66 both-incorrect pairs, and exact two-sided McNemar p-value `0.179665`. Its conclusion remains `MODERATE_DESCRIPTIVE_EVIDENCE_WITHOUT_INFERENTIAL_SUPPORT`.

## Prospective Controls

Each future Episode must be uniquely eligible, bound to USD/JPY and an authoritative release timestamp, and frozen in a manifest before provider dispatch. `information_cutoff_ts <= prompt_freeze_ts < forecast_freeze_deadline_ts < release_ts`; Pack inputs, prompt fingerprints, provider/model allocation, forecast identities, and Outcome identities must be frozen before release and before any Outcome is available. Any uncertain identity, cutoff, release time, Pack lineage, source authority, or leakage condition stops the Slice.

The permitted provider/model routes are Anthropic / `claude-haiku-4-5`, Gemini / `gemini-2.5-flash-lite`, and OpenAI / `gpt-4o-mini-2024-07-18`. Each admitted Episode pre-enumerates one paired Pack A/E call for each route. Both arms share the Episode, provider/model, cutoff, release timestamp, measurement windows, and Outcome identity. Selection, substitution, reallocation, or replacement after outcomes are observed is prohibited.

## Endpoint And Inference

`T+15 directional accuracy` is the primary endpoint. UP, DOWN, and FLAT are scoreable only with a valid attached Outcome and canonical boolean T+15 result. NO_SIGNAL is neither correct nor incorrect and is excluded from directional denominators. Pack-specific denominators are reported separately; direct Pack comparison uses only matching same-Episode/provider/model pairs where both arms are scoreable against the same Outcome.

The confirmatory analysis is pre-specified as an exact two-sided McNemar binomial test at alpha `0.05`, using only discordant pairs and no continuity correction. Both-correct and both-incorrect pairs remain in the four-cell report but not the test statistic. No confidence interval is authorized because no canonical paired risk-difference interval method and confidence level are governed. No interim comparison, efficacy/futility analysis, provider-level inference, subgroup testing, composite score, or post-hoc threshold selection is authorized.

Directional coverage and NO_SIGNAL rate are reported separately by Pack, alongside total eligible Episodes, valid forecasts, valid attached Outcomes, conditional T+15 accuracy, common paired-scoreable count, and unavailable/paired-excluded counts. No coverage-adjusted score is introduced. Unavailable Outcomes retain source evidence and may be symmetrically paired-excluded only under the existing accepted rule; no Outcome may be imputed, interpolated, or substituted.

## Population And Cadence

This is a bounded scenario design, not a post-hoc power calculation or a promise of a future effect. The target is 120 eligible Episodes and 240 common paired-scoreable observations. Recruitment occurs in deterministic Slices of at most 48 Episodes. If the completed 120-Episode cohort has fewer than 240 common pairs, recruitment continues only in whole frozen Slices up to 144 eligible Episodes. A confirmatory test requires at least 200 common pairs; below that maximum-ceiling minimum, evidence is preserved and any extension requires a separate authorization.

The nonbinding operational scenarios use Round 1 availability and common-scoreability only for planning: 96 eligible Episodes maps to approximately 214 common pairs, 120 to approximately 267, and 144 to approximately 320. Round 1 effects and availability are not assumed to recur.

Each Slice uses the accepted cadence: one immutable manifest, one explicit end-to-end authorization, and one coherent session. Apps Script reads are capped at one per distinct UTC release day, market-data attempts at one per selected Episode, and the total ceiling is their exact sum. The defaults remain zero retries, zero Google writes, and no more local append-only attachments than selected eligible Episodes. The existing authorized-slice controller handles Outcome stages; this protocol creates no new forecast or Outcome workflow.

Immediate Impulse is secondary and is reported strictly only for `SUPPORTED` Outcomes. Magnitude/pip error, horizon accuracy, path accuracy, and reversal accuracy remain descriptive secondary metrics under the existing canonical evaluator. No composite score is authorized.

## Next Move

Prepare one separately authorized Round 2 execution envelope and its first prospective Slice manifest, with future Episode eligibility, pre-release cutoff verification, deterministic provider/model allocation, and manifest-derived ceilings. No forecast dispatch, Outcome collection, attachment, or evaluation is authorized by this protocol Move.
