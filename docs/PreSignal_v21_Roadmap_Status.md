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
| Step 9 | NOT STARTED | Decide promotion |

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

Step 8B is complete. Step 9 remains not started; its promotion decision is
blocked pending the separately authorized prospective output-contract repair
identified by the frozen Step 8B analysis.
