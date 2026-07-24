import unittest

from automation import run_presignal_v21_new_r6_paired_forecast_execution_v1 as runner


def auth_fixture():
    return {
        "authorization_name": runner.AUTHORIZATION_NAME,
        "authorization_fingerprint": runner.AUTHORIZATION_FP,
        "route_b_freeze_fingerprint": runner.ROUTE_B_FP,
        "episode_identity": runner.EPISODE_ID,
        "episode_content_checksum": "sha256:episode",
        "episode_provenance_checksum": "sha256:episodeprov",
        "episode_lineage_checksum": "sha256:episodelineage",
        "attention_identity": runner.ATTENTION_ID,
        "attention_content_checksum": "sha256:attention",
        "attention_provenance_checksum": "sha256:attentionprov",
        "attention_lineage_checksum": "sha256:attentionlineage",
        "request_set_checksum": "sha256:reqset",
        "pack_a_identity": runner.PACK_A_ID,
        "pack_a_content_checksum": runner.PACK_A_CONTENT,
        "pack_a_provenance_checksum": "sha256:packaprov",
        "pack_a_lineage_checksum": "sha256:packalineage",
        "pack_e_identity": runner.PACK_E_ID,
        "pack_e_content_checksum": runner.PACK_E_CONTENT,
        "pack_e_provenance_checksum": "sha256:packeprov",
        "pack_e_lineage_checksum": "sha256:packelineage",
        "pack_separation_report_checksum": "sha256:sep",
        "provider": "Gemini",
        "model": "gemini-2.5-flash-lite",
        "forecast_schema": runner.prospective_flat.PROSPECTIVE_CONTRACT_VERSION,
        "primary_endpoint": "15-minute primary endpoint",
        "optional_sidecars": [5, 30, 60],
        "call_budget": 2,
        "pack_a_call_budget": 1,
        "pack_e_call_budget": 1,
        "retry_budget": 0,
        "forecast_cutoff": runner.CUTOFF,
    }


class NewR6PairedForecastExecutionTests(unittest.TestCase):
    def test_authorization_validation_passes_and_fingerprint_mismatch_blocks(self):
        auth = auth_fixture()
        episode = {"episode_identity": runner.EPISODE_ID, "content_checksum": "sha256:episode", "provenance_checksum": "sha256:episodeprov", "lineage_checksum": "sha256:episodelineage"}
        attention = {"attention_identity": runner.ATTENTION_ID, "content_checksum": "sha256:attention", "provenance_checksum": "sha256:attentionprov", "lineage_checksum": "sha256:attentionlineage"}
        pack_a = {"pack_identity": runner.PACK_A_ID, "content_checksum": runner.PACK_A_CONTENT, "provenance_checksum": "sha256:packaprov", "lineage_checksum": "sha256:packalineage", "request_set_checksum": "sha256:reqset"}
        pack_e = {"pack_id": runner.PACK_E_ID, "pack_fingerprint": runner.PACK_E_CONTENT, "provenance_checksum": "sha256:packeprov", "lineage_checksum": "sha256:packelineage"}
        separation = {"separation_passed": True}
        auth["pack_e_provenance_checksum"] = runner.PACK_E_PROVENANCE
        auth["pack_e_lineage_checksum"] = runner.PACK_E_LINEAGE
        auth["pack_separation_report_checksum"] = runner.sha(separation)
        result = runner.authorization_validation(auth, episode, attention, pack_a, pack_e, separation, {"requests": [1] * 10})
        self.assertTrue(result["authorization_valid"])
        auth["authorization_fingerprint"] = "sha256:wrong"
        blocked = runner.authorization_validation(auth, episode, attention, pack_a, pack_e, separation, {"requests": [1] * 10})
        self.assertFalse(blocked["authorization_valid"])

    def test_cutoff_open_and_closed_behavior(self):
        self.assertTrue(runner.cutoff_open("2026-07-24T00:00:00Z"))
        self.assertFalse(runner.cutoff_open("2026-07-29T18:00:00Z"))

    def test_unwrap_provider_output_and_optional_sidecars(self):
        raw = {
            "forecast": {
                "no_signal_flag": False,
                "confidence": 0.6,
                "expected_initial_direction": "UP",
                "expected_reversal_flag": False,
                "expected_reversal_horizon_min": None,
                "expected_path_summary": "path",
                "information_used": [],
                "missing_information": [],
                "invalidation_condition": "condition",
                "path": [{"horizon_min": 15, "expected_direction": "UP"}],
                "no_signal_reason": None,
            },
            "response_contract": {},
        }
        unwrapped = runner.unwrap_provider_output(raw)
        self.assertEqual(unwrapped["expected_initial_direction"], "UP")
        validated = runner.prospective_contract.validate_prospective_forecast(unwrapped, episode_id="EP", provider="Gemini", model="gemini-2.5-flash-lite", pack_arm="PACK_A", forecast_cutoff=runner.CUTOFF)
        self.assertTrue(validated["primary_forecast_valid"])
        self.assertFalse(validated["secondary_path_complete"])

    def test_missing_primary_direction_is_invalid_and_no_signal_not_primary(self):
        invalid = runner.prospective_contract.validate_prospective_forecast({"path": [{"horizon_min": 5, "expected_direction": "UP"}]}, episode_id="EP", provider="Gemini", model="gemini-2.5-flash-lite", pack_arm="PACK_A", forecast_cutoff=runner.CUTOFF)
        self.assertFalse(invalid["primary_forecast_valid"])
        self.assertEqual(invalid["forecast_state"], "INVALID")
        abstention = runner.prospective_contract.validate_prospective_forecast({"no_signal_flag": True}, episode_id="EP", provider="Gemini", model="gemini-2.5-flash-lite", pack_arm="PACK_A", forecast_cutoff=runner.CUTOFF)
        self.assertEqual(abstention["forecast_state"], "NO_SIGNAL")

    def test_payload_separation_and_identity_determinism(self):
        episode = {"country": "US", "release_timestamp": runner.RELEASE_TS, "forecast_cutoff": runner.CUTOFF, "primary_event_identity": runner.PRIMARY_EVENT_ID, "primary_event_name": runner.PRIMARY_EVENT_NAME}
        attention = {"provider_identity": "Gemini", "model_identity": "gemini-2.5-flash-lite", "selection_reason": "reason", "attention_identity": runner.ATTENTION_ID, "forecast_cutoff": runner.CUTOFF}
        pack_a = {"pack_identity": runner.PACK_A_ID, "schema_version": "a", "ordered_canonical_requests": [{"request_identity": "R1"}]}
        pack_e = {"pack_id": runner.PACK_E_ID, "pack_fingerprint": runner.PACK_E_CONTENT, "items": [{"item_key": "TREASURY_2Y_10Y_PRESESSION_STATE"}], "pack_e_version": "e"}
        row_a = runner.build_input_row(pack_arm="PACK_A", episode=episode, attention=attention, pack_a=pack_a, pack_e=pack_e)
        row_e = runner.build_input_row(pack_arm="PACK_E", episode=episode, attention=attention, pack_a=pack_a, pack_e=pack_e)
        req_a = runner.prospective_flat.prospective_request(row_a, run_id="RUN_A", contract_version=runner.prospective_flat.PROSPECTIVE_CONTRACT_VERSION)
        req_e = runner.prospective_flat.prospective_request(row_e, run_id="RUN_E", contract_version=runner.prospective_flat.PROSPECTIVE_CONTRACT_VERSION)
        self.assertNotIn(runner.PACK_E_ID, runner.canonical(req_a))
        self.assertNotIn("TREASURY_2Y_10Y_PRESESSION_STATE", runner.canonical(req_a))
        self.assertIn(runner.PACK_E_ID, runner.canonical(req_e))
        self.assertIn("TREASURY_2Y_10Y_PRESESSION_STATE", runner.canonical(req_e))

    def test_runtime_failure_becomes_incomplete_not_no_signal(self):
        self.assertEqual(runner.runtime_state({"status": "timeout"}), "TRANSPORT_FAILED")

    def test_pair_validation_and_outcome_auth_inactive(self):
        pack_a = {
            "forecast_identity": "A", "episode_identity": runner.EPISODE_ID, "provider_identity": "Gemini", "model_identity": "gemini-2.5-flash-lite",
            "forecast_cutoff": runner.CUTOFF, "schema_version": runner.prospective_flat.PROSPECTIVE_CONTRACT_VERSION,
            "pack_identity": runner.PACK_A_ID, "primary_15m_direction": "UP", "content_checksum": "sha256:a", "provenance_checksum": "sha256:ap", "lineage_checksum": "sha256:al",
        }
        pack_e = {
            "forecast_identity": "E", "episode_identity": runner.EPISODE_ID, "provider_identity": "Gemini", "model_identity": "gemini-2.5-flash-lite",
            "forecast_cutoff": runner.CUTOFF, "schema_version": runner.prospective_flat.PROSPECTIVE_CONTRACT_VERSION,
            "pack_identity": runner.PACK_E_ID, "primary_15m_direction": "DOWN", "content_checksum": "sha256:e", "provenance_checksum": "sha256:ep", "lineage_checksum": "sha256:el",
        }
        separation = {"separation_passed": True}
        pair = runner.pair_record(pack_a, pack_e)
        report = runner.pair_validation(pack_a, pack_e, separation)
        self.assertTrue(report["pack_identities_distinct"])
        self.assertFalse(report["pack_leakage_detected"])
        outcome = runner.outcome_authorization(pair, pack_a, pack_e, {"authorization_fingerprint": runner.AUTHORIZATION_FP}, {"content_checksum": "sha256:ep", "provenance_checksum": "sha256:epp", "lineage_checksum": "sha256:epl"})
        self.assertTrue(outcome["authorization_valid"])
        self.assertFalse(outcome["authorization_activated"])


if __name__ == "__main__":
    unittest.main()
