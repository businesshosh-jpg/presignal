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
