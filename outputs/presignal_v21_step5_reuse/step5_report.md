# Step 5 v2 Information Infrastructure Reuse

Decision: `V2_1_STEP5_TARGETED_COMPATIBILITY_REPAIR_REQUIRED`

The adapter reads the verified frozen v2 package and never regenerates Attention, requests, acquisition, or Packs. Historical Pack A/E inputs require exact member-level Attention lineage. The package preserves requests and Packs but lacks an Attention Map export, so affected historical Episodes remain unavailable rather than inferred from request labels.

- Counts: `{'total_episodes': 1682, 'exact_parent_session_matches': 1316, 'attention_compatible_episodes': 0, 'information_request_compatible_episodes': 1316, 'pack_a_compatible_episodes': 1316, 'pack_e_compatible_episodes': 1316, 'fully_step_6_ready_episodes': 0}`
- Unavailable: `{'ATTENTION_MAP_MISSING': 1316, 'NO_EXACT_PARENT_SESSION': 366}`
