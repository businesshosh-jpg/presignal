# Simplified Authoritative Replay v1

The provider returns a reduced forecast object, not the internal native-v2 relational graph.

Provider-owned fields are `primary_driver_token`, optional `secondary_driver_token`, `final_usdjpy_direction`, `reaction_strength`, `confidence`, `primary_thesis`, optional `secondary_thesis`, and two to four plain-text `reasoning_steps`. The executor supplies and verifies the run/session/provider/model metadata and preserves the raw response before parsing.

Driver tokens are generated deterministically from frozen session-member IDs. The executor maps a selected token back to its canonical event ID; providers never emit event IDs, release-cluster IDs, path target types, or database foreign keys. A valid reduced forecast therefore supports the Pack A versus Pack E same-session comparison without requiring a complete normalized Prediction Path graph.

The detailed native-v2 Prediction Path remains deferred research work. Only deterministic canonical fields are derived in this replay; unavailable detailed Path fields remain unavailable rather than being inferred or repaired.
