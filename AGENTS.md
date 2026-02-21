# PreSignal Agent Instructions

This repository is governed by:

- docs/RuleBook_v1.3.md
- docs/Blueprint_v1.3.md

## Hierarchy

If there is any conflict:
1. RuleBook_v1.3.md takes precedence.
2. Blueprint_v1.3.md defines architecture.
3. Code must not violate either.

## Hard Constraints

- Do not rename global Apps Script functions.
- Do not change sheet header order without explicit instruction.
- Do not remove logging mechanisms.
- Maintain strict JSON validation contract.
- Maintain event_id + ai_name uniqueness rule.
- Preserve backward compatibility unless explicitly approved.

If a requested change would violate any of the above, ask for clarification before proceeding.