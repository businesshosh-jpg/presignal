# Step 5 v2 Information Infrastructure Reuse

Decision: `V2_1_FROZEN_ATTENTION_EXPORT_AND_STEP5_VALIDATED`

The adapter never regenerates Attention, requests, acquisition, or Packs. Historical Pack A/E inputs require exact member-level Attention lineage. The adapter reads the verified frozen v2 package plus the explicitly supplied authoritative Attention export. Only original parsed records with exact session, Event, provider/model, raw-response, and cutoff lineage can select an Episode. Provider errors and omissions remain preserved but unavailable.

- Counts: `{'total_episodes': 1682, 'exact_parent_session_matches': 1316, 'attention_compatible_episodes': 48, 'information_request_compatible_episodes': 1316, 'pack_a_compatible_episodes': 1316, 'pack_e_compatible_episodes': 1316, 'fully_step_6_ready_episodes': 48}`
- Unavailable: `{'ATTENTION_LINEAGE_MISMATCH': 40, 'ATTENTION_MAP_MISSING': 1268, 'NO_EXACT_PARENT_SESSION': 366}`
