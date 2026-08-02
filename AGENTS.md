# PreSignal Agent Instructions

This repository is governed by:

- docs/RuleBook_v1.4.md
- docs/Blueprint_v1.4.md

## Hierarchy

If there is any conflict:
1. RuleBook_v1.4.md takes precedence.
2. Blueprint_v1.4.md defines architecture.
3. Code must not violate either.

## Hard Constraints

- Do not rename global Apps Script functions.
- Do not change sheet header order without explicit instruction.
- Do not remove logging mechanisms.
- Use append-only header enforcement; never reorder existing sheet columns.
- Preserve event_id / batch_id / type identity semantics.
- Maintain strict JSON validation contract.
- Maintain event_id + ai_name uniqueness rule.
- Position outputs as decision support, not trading advice.
- Avoid guaranteed-profit language and direct buy/sell instructions.
- Preserve backward compatibility unless explicitly approved.

If a requested change would violate any of the above, ask for clarification before proceeding.

## v2.1 Round 1 Operating Rules

- Reuse the existing v2.1 pipeline and adapters. Do not create parallel systems without a demonstrated necessity.
- Treat `docs/CURRENT_ROUND_1_STATE.md` and `docs/GOVERNING_ARTIFACTS.md` as the compact starting context for each bounded Move.
- Never overwrite completed, frozen, or governing evidence. Create append-only evidence for every new Move.
- Keep `T+15` as the primary endpoint and Immediate Impulse as a secondary measurement.
- Keep Pack A and Pack E separate, including source lineage, prompt version, execution, and evaluation cohorts.
- Preserve provider, model, call, batch, prompt, Pack, cutoff, and resume-key lineage. Fail closed on identity, count, fingerprint, authority, lineage, or contract conflicts.
- Do not redesign Pack E during Round 1 completion.
- Do not add provider weighting, ranking, consensus, routing, or winner selection unless separately authorized.
- Do not access market data, attach Outcomes, calculate accuracy, or write to Google unless the active Move explicitly authorizes it.
- Do not conduct broad repository cleanup or reopen settled architecture without a concrete contradiction.
- Inspect only named files, artifacts, and direct dependencies. Expand inspection only for a concrete conflict, missing dependency, or focused-test failure, and report the expansion.
- Maintain strict JSON and provider-authority validation. Preserve raw output before parsing and fail closed on invalid response status or missing provider payload.
- Every forecast batch invocation must acquire the existing exclusive execution lease and durable per-call reservation before preflight, client construction, or provider dispatch. A post-dispatch interruption is remote-state-unknown and requires explicit governance before any resend.
- Use focused tests for each bounded change. Run `git diff --check` before commit.
- Commit only bounded implementation, tests, and minimal documentation. Do not commit credentials or generated evidence unless explicitly required by repository policy.
- Push the accepted commit to the requested branch and report repository, branch, start/final HEAD, artifacts, tests, commit, and push status.
- Prefer the lowest-cost reliable model: GPT-5.6 Luna for mechanical inspection/documentation, GPT-5.4 for normal implementation/tests, and higher reasoning only for unresolved cross-boundary conflicts.
