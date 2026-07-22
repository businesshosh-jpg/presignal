# PreSignal v2.1 Roadmap Status

This is the active human-facing status record for PreSignal v2.1 development.
It aligns task labels with the authoritative v2.1 Development Plan.

## Authoritative Sequence

1. Step 1 - Freeze v2.0
2. Step 2 - Define the narrow v2.1 contract
3. Step 3 - Create the new workbook series
4. Step 4 - Build the Episode and Outcome layer
5. Step 5 - Reuse v2 Attention, Information Requests, and shared Pack infrastructure
6. Step 6 - Test one provider first
7. Step 7 - Add all providers
8. Step 8 - Run and analyze the historical shadow test
9. Step 9 - Decide promotion

## Current Status

| Label | Status | Completed or Next Work |
| --- | --- | --- |
| Step 1 | COMPLETE | Freeze v2.0 |
| Step 2 | COMPLETE | Define the narrow v2.1 contract |
| Step 3 | COMPLETE | Create the new workbook series |
| Step 4 | COMPLETE | Build the Episode and Outcome layer |
| Step 5 | COMPLETE | Reuse v2 Attention, Information Requests, and shared Pack infrastructure |
| Step 5-R1 | COMPLETE | Audit and preserve frozen historical Attention lineage |
| Step 5-R2 | COMPLETE | Recover authoritative Attention history and complete Step 5 |
| Step 6 | COMPLETE | Validate the one-provider Pack A versus Pack E Event-Path pipeline |
| Step 7 | COMPLETE | Add all providers and freeze the controlled batch pipeline |
| Step 8A | COMPLETE | Execute the controlled historical Pack A versus Pack E shadow batch |
| Step 8B | COMPLETE | Episode-cluster-aware analysis of the historical Pack A versus Pack E shadow test |
| Step 8-R1 | COMPLETE | Repair the prospective FLAT path-stage output instruction |
| Step 9 | COMPLETE | Promotion deferred; bounded prospective shadow replication authorized |

## Historical Label Compatibility

Historical task labels used "Step 6" for some batch preparation and execution
work. Under the authoritative v2.1 Development Plan, all-provider enablement
maps to Step 7 and controlled historical batch execution maps to Step 8A.

The completed episode-cluster-aware paired analysis was historically created
with `STEP7-*` artifact and decision identifiers. Under this roadmap, that work
is **Step 8B — Episode-Cluster-Aware Analysis of the Historical Pack A versus
Pack E Shadow Test**. Those historical identifiers are retained unchanged.

Historical output directories, run IDs, fingerprints, contracts, forecasts,
evaluations, and execution artifacts remain unchanged. This document is the
only current roadmap-label authority for future status and task titles.

## Current Gate

Step 9 is complete. The Event-Path architecture is valid for a bounded
Post-Step-9 Prospective Shadow Replication using the repaired prospective FLAT
contract, but main-path promotion is deferred: the frozen Step 8B historical
comparison remains indeterminate under Episode clustering and missingness.

Direct Session Forecasting remains active, shadow-only operation continues,
and v3.0 is not authorized. Historical internal names remain unchanged:
historical batch execution maps to Step 8A and paired historical analysis maps
to Step 8B under this authoritative roadmap.

## Post-Step-9 Preparation

The bounded prospective Event-Path shadow collection is prepared with the
frozen P12/P40/P60/P80 study boundaries and repaired prospective contract.
Provider execution has **not** started. P12 is **PAUSED_PENDING_HISTORICAL_VALIDATION**
with zero admitted Episodes and zero prospective provider or forecast calls.

## Step 8-R2 Historical Reconstruction

The homogeneous Step 8-R2 historical continuation is complete: 259 Episodes
were processed and 40 unique Episodes produced at least one complete paired
observation. Its final read-only interpretation is complete and classifies the
historical evidence as indeterminate under missingness sensitivity. This does
not reopen Step 9 or authorize prospective execution.

Step 8-R3 diagnosis is complete. It identified an invalid sampled cluster
sign-flip implementation, Anthropic Attention raw-JSON coverage failure, and
provider-specific output-contract rejections. P12 remains paused pending
targeted repair and fresh homogeneous historical verification.

The Step 8-R3 targeted repairs and call-free fresh-verification preparation
are complete. The fresh cohort remains unexecuted and is frozen for a separate
historical verification task; P12 remains paused.

## Step 8-R3-R4 Adapter Smoke

The manifest-bound R3 dispatcher is connected to the concrete Attention,
Information Request, Pack, forecast, Outcome, and evaluation components. One
bounded smoke Episode (`EP_BATCH_b5c0c544ec07bbf0b950`) was processed without
advancing the cohort. It made five historical provider calls and reached
durable terminal states without a duplicate call, cutoff violation, leakage,
model substitution, or production mutation. No forecast pair was eligible in
that Episode: Anthropic Attention was rejected for truncated raw JSON, while
Gemini and OpenAI Information Requests were rejected for invalid frozen-schema
enums. The smoke validates runtime dispatch and resume safety only; it does not
provide a forecast-quality result. P12 remains **PAUSED_PENDING_HISTORICAL_VALIDATION**.

## Step 8-R3-R5 Compatibility Result

The child compatibility contract was bound to one replacement smoke of the
same Episode. The live run confirmed that the new prompt rules reached the
providers, but it did not meet the zero-recurrence gate: Anthropic remained
truncated by the fixed generic bridge output limit, Gemini used Attention
labels in the Request `priority` field, and OpenAI emitted `other` for one
Request `affected_channel`. No second replacement smoke was run. The fresh
cohort remains blocked pending a single targeted provider-contract repair;
P12 remains **PAUSED_PENDING_HISTORICAL_VALIDATION**.

## Step 8-R3-R6 Compatibility Completion

The compat-r2 source repair is call-free validated and freezes an 8,192-token
Anthropic Attention bound, raw-response retention before Python parsing, strict
Request-priority separation, and the documented exact `other` to `unknown`
channel normalization. OAuth was restored and the runtime uses the Apps Script
Execution API against pushed project HEAD, so no `AKfy...` deployment update was
needed. The authorized one-Episode smoke ran once and resumed with zero calls.
It remains terminally incomplete: Gemini Pack E was rejected with
`PATH_PIPS_MIN` because the frozen negative-DOWN instruction conflicts with the
active absolute-pip validator; OpenAI emitted `information_category=unknown`;
and Anthropic's fenced JSON provider identity was rejected before normalization.
The fresh cohort remains blocked; P12 remains **PAUSED_PENDING_HISTORICAL_VALIDATION**.

## Step 8-R3-R7 Final Contract Repair

Compat-r3 aligns all provider-visible pip ranges with the unchanged
absolute-magnitude validator, normalizes only the exact R6 Anthropic
`presignal_v2` label, and maps only `information_category=unknown` to the
existing `other` category. One new smoke of the same Episode completed an
OpenAI Pack A/Pack E paired evaluation and resumed with zero calls. The R6
values did not recur. Anthropic emitted a new, unapproved identity label and
Gemini emitted the unapproved `housing_market_trend` category; both were
strictly preserved as coverage limitations rather than broadened silently.
P12 remains **PAUSED_PENDING_HISTORICAL_VALIDATION**.

## Step 8-R3-R8 Provider Coverage Repair

Compat-r4 transfers Anthropic provider/model ownership to the manifest-bound
runtime route and accepts only documented workflow identity labels as audit
metadata. It also freezes the one exact Request mapping
`housing_market_trend` to the existing `other` category. The bounded R8 smoke
confirmed both repaired blockers: Anthropic Attention accepted the emitted
`presignal_v2_shadow_research` workflow identity and Gemini's Request was
accepted. The smoke then stopped before forecasts on two separately recorded
failures: an Anthropic Request bridge payload serialization error and a Gemini
`attention_rank="L"` value that was not rejected before prompt construction.
No additional Episode was processed, no forecast call was made, and the fresh
cohort remains blocked. P12 remains **PAUSED_PENDING_HISTORICAL_VALIDATION**.

## Step 8-R3-R9 Provider-Scoped Execution Repair

Compat-r5 preserves an undecodable Anthropic Request HTTP body before strict
rejection and rejects nonnumeric Attention rank values before they can reach
Request or forecast construction. Provider paths are now recorded independently
and aggregate to an Episode terminal state only after all provider paths finish.
The one-Episode R9 smoke completed Pack A/Pack E paired evaluations for all
three providers, recorded one complete Episode, and resumed with zero calls.
No cohort Episode beyond the smoke was processed. P12 remains
**PAUSED_PENDING_HISTORICAL_VALIDATION**.

## Step 8-R3-R10 Run Ownership and Orphan Reconciliation

The final Compat-R5 run `STEP8-R3-FINAL-4a42aef` is formally abandoned with
no scientific evidence issued. Its Gemini Attention operation reached
`ATTENTION_SENT` without a durable response, provider request ID, transport
result, or authoritative non-dispatch proof. R10 adds an OS-backed exclusive
run lease, heartbeat, append-only operation journal, and fail-closed stale
lease handling: any unresolved sent operation blocks takeover and retry.
The abandoned Gemini provider/Episode operation is preserved as terminal
missing for a successor Compat-R5 cohort; it must never be sent again. P12
remains **PAUSED_PENDING_HISTORICAL_VALIDATION**.

## Step 8-R3 Final Gate Diagnosis

Read-only reconciliation found that the reported 229 FORECAST selections
included 37 rejected Attention payloads whose raw content contained
`PRIMARY_DRIVER`; the accepted-Attention denominator is 192, not 229. It also
found 83 provider/Episode identities with both forecast arms accepted but
`VALID` evaluations whose directional horizon fields were all null. Final
historical evidence remains unissued pending read-only accounting
reconstruction and a targeted evaluation/runtime integrity decision. P12
remains **PAUSED_PENDING_HISTORICAL_VALIDATION**.

## Step 8-R3 Final Evidence Reconstruction

Read-only reconstruction corrected the accepted-Attention FORECAST population
to 192 and reproduced the 52 directionally evaluable paired rows without
changing any source ledger. The 83 affected accepted-forecast identities are
valid `NO_SIGNAL` evaluator branches, not missing Outcomes: 64 have both arms
without a directional endpoint and 19 have one such arm. They cannot be added
to the frozen 15-minute directional estimand. The derived result remains
indeterminate: Pack A 15/52 and Pack E 14/52, with exact McNemar and
Episode-cluster p-values of 1.0. Shared OAuth/network bursts occurred before
provider-specific handling on the Google authentication and Apps Script
Execution API route. P12 remains **PAUSED_PENDING_HISTORICAL_VALIDATION**;
prospective activation requires a narrow shared-runtime reliability decision,
not another provider-compatibility phase or automatic historical retest.

## Step 8-R3 Final Reporting Repair

The final accounting now separates 192 accepted FORECAST identities into 52
directional paired observations, 83 valid pairs containing at least one
`NO_SIGNAL` output, and 57 true operational or contract incomplete pairs.
The prior generic 27.1% "paired completion" label is superseded: it is the
**Directional Pair Yield**, while the **Valid Terminal Pair Rate** is 70.3%.
The frozen 85% `paired_completion_target` does not specify which definition it
intended; the original runner implemented directional coverage, and both
reported interpretations remain below 85%. Historical evidence remains
indeterminate. P12 remains **PAUSED_PENDING_HISTORICAL_VALIDATION** pending a
narrow repair of the shared Google OAuth and Apps Script Execution API
reliability boundary.

## Shared Runtime Reliability Repair

The shared client now serializes Google token refresh with an OS-backed lock,
persists refreshed tokens atomically, preserves structured Google/App Script
transport classifications, and exposes a harmless Execution API health
function. The bounded verification found the current refresh token has been
expired or revoked (`invalid_grant`), so no health call or provider call was
sent. Reauthentication with `python3 auth_sheets.py` is required before the
idempotent Apps Script health check can establish Step 9 runtime readiness.
P12 remains **PAUSED_PENDING_HISTORICAL_VALIDATION**.

## Shared Runtime Reliability Verification R1

The bounded R1 verifier confirmed that `local/token.json` remains readable,
contains a refresh token, and lists the required scopes, but Google rejected
the refresh grant with `invalid_grant` before Apps Script dispatch. No
`presignalRuntimeHealthCheck` call, provider call, forecast call, or
prospective call was made. Step 9 readiness remains blocked pending a
successful replacement of the revoked refresh token; P12 remains
**PAUSED_PENDING_HISTORICAL_VALIDATION**.
