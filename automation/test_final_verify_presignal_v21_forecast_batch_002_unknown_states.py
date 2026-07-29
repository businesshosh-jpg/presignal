from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from automation import final_verify_presignal_v21_forecast_batch_002_unknown_states as final_verify


class FinalForecastBatch002ExistenceVerificationTest(unittest.TestCase):
    def test_exactly_three_call_ids_are_audited(self) -> None:
        self.assertEqual(
            final_verify.UNKNOWN_CALL_IDS,
            [
                "FCL_befd6d6947490cc19f4754b9",
                "FCL_1ce38eb60f0865beca69bb31",
                "FCL_d72f741393a7643ea859edb8",
            ],
        )

    def test_call_search_tokens_include_exact_fingerprints(self) -> None:
        identity = {
            "forecast_call_id": "FCL_test",
            "forecast_identity": "STEP6_test",
            "prompt_text_fingerprint": "sha256:prompt",
            "prompt_context_fingerprint": "sha256:context",
            "pack_row_fingerprint": "sha256:pack",
            "pack_payload_input_fingerprint": "sha256:payload",
            "episode_id": "EP_test",
            "provider": "Gemini",
            "model": "gemini-2.5-flash-lite",
            "historical_cutoff": "2024-05-02T06:50:00Z",
        }
        tokens = final_verify.call_search_tokens(identity)
        self.assertIn("sha256:prompt", tokens)
        self.assertIn("sha256:context", tokens)
        self.assertIn("sha256:pack", tokens)
        self.assertIn("sha256:payload", tokens)

    def test_plausible_log_sheet_enumeration_is_read_only(self) -> None:
        titles = ["log", "Requests", "Main", "Provider_Result_Log", "Episodes"]
        plausible = final_verify.plausible_log_sheets(titles)
        self.assertEqual(plausible, ["log", "Requests", "Provider_Result_Log"])
        self.assertEqual(final_verify.safe_sheet_range("Provider Result Log"), "'Provider Result Log'!A:Z")

    def test_timestamp_only_matches_are_rejected(self) -> None:
        self.assertTrue(final_verify.reject_timestamp_only_candidate({"matched_fields": ["dispatch_timestamp_window"]}))
        self.assertFalse(final_verify.reject_timestamp_only_candidate({"matched_fields": ["dispatch_timestamp_window", "FCL_test"]}))

    def test_aggregate_provider_usage_cannot_establish_exact_result(self) -> None:
        self.assertFalse(final_verify.aggregate_provider_usage_is_exact_result({}))
        self.assertFalse(final_verify.aggregate_provider_usage_is_exact_result({"provider_request_id": "req_only"}))
        self.assertTrue(final_verify.aggregate_provider_usage_is_exact_result({"provider_request_id": "req", "forecast_call_id": "FCL_test"}))

    def test_apps_script_history_search_uses_read_only_process_routes_only(self) -> None:
        process_stub = mock.Mock()
        process_stub.listScriptProcesses.side_effect = RuntimeError("blocked")
        process_stub.list.side_effect = RuntimeError("blocked")
        script_service = mock.Mock()
        script_service.processes.return_value = process_stub
        identities = {
            call_id: {
                "forecast_call_id": call_id,
                "forecast_identity": f"STEP6_{index}",
                "prompt_text_fingerprint": f"sha256:p{index}",
                "prompt_context_fingerprint": f"sha256:c{index}",
                "pack_row_fingerprint": f"sha256:r{index}",
                "pack_payload_input_fingerprint": f"sha256:i{index}",
                "episode_id": f"EP_{index}",
                "provider": "Gemini",
                "model": "gemini-2.5-flash-lite",
                "historical_cutoff": "2024-05-02T06:50:00Z",
            }
            for index, call_id in enumerate(final_verify.UNKNOWN_CALL_IDS, start=1)
        }
        ledger, _matches = final_verify.apps_script_history_search(script_service, identities)
        self.assertEqual(process_stub.listScriptProcesses.call_count, 1)
        self.assertEqual(process_stub.list.call_count, 1)
        self.assertTrue(any(row["surface"] == "APPS_SCRIPT_EXECUTION_STATUS_API" for row in ledger))
        self.assertFalse(any("run(" in str(row) for row in ledger))

    def test_execute_verification_creates_call_free_append_only_run(self) -> None:
        fake_identities = {
            call_id: {
                "forecast_call_id": call_id,
                "forecast_identity": f"STEP6_{index}",
                "episode_id": f"EP_{index}",
                "provider": "Gemini",
                "model": "gemini-2.5-flash-lite",
                "prompt_text_fingerprint": f"sha256:p{index}",
                "prompt_context_fingerprint": f"sha256:c{index}",
                "pack_row_fingerprint": f"sha256:r{index}",
                "pack_payload_input_fingerprint": f"sha256:i{index}",
                "historical_cutoff": "2024-05-02T06:50:00Z",
            }
            for index, call_id in enumerate(final_verify.UNKNOWN_CALL_IDS, start=1)
        }
        fake_local_rows = [
            {
                "forecast_call_id": call_id,
                "call_started_journaled": True,
                "request_serialization_proven": True,
                "google_api_request_initiation": True,
                "local_response_retrieval_proven": True,
                "terminal_state_persisted": True,
                "bridge_invocation_proven": False,
                "provider_dispatch_proven": False,
                "transport_classification": {"dispatch_certainty": "UNKNOWN"},
            }
            for call_id in final_verify.UNKNOWN_CALL_IDS
        ]
        fake_sheet_ledger = [{"surface": "SHEET_TITLE_ENUMERATION", "sheet_titles": ["log"], "plausible_log_tabs": ["log"]}]
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(
                final_verify,
                "git_branch",
                return_value="codex/immediate-impulse-outcome-recovery-r1",
            ), mock.patch.object(
                final_verify,
                "git_head",
                return_value=final_verify.EXPECTED_HEAD,
            ), mock.patch.object(
                final_verify,
                "is_descendant_of",
                return_value=True,
            ), mock.patch.object(
                final_verify,
                "identity_inventory",
                return_value=fake_identities,
            ), mock.patch.object(
                final_verify.baseline,
                "failed_batch_rows",
                return_value={},
            ), mock.patch.object(
                final_verify.baseline,
                "local_lifecycle_rows",
                return_value=fake_local_rows,
            ), mock.patch.object(
                final_verify.google_clients,
                "load_credentials",
                return_value=object(),
            ), mock.patch.object(
                final_verify.google_clients,
                "build_sheets_service",
                return_value=object(),
            ), mock.patch.object(
                final_verify.google_clients,
                "build_script_service",
                return_value=object(),
            ), mock.patch.object(
                final_verify,
                "local_output_search",
                return_value=([{"surface": "LOCAL"}], []),
            ), mock.patch.object(
                final_verify,
                "orphan_search",
                return_value=([{"surface": "ORPHAN", "candidate_count": 0}], []),
            ), mock.patch.object(
                final_verify,
                "google_sheet_search",
                return_value=(fake_sheet_ledger, [], ["log"]),
            ), mock.patch.object(
                final_verify,
                "apps_script_history_search",
                return_value=([{"surface": "LIST_SCRIPT_PROCESSES", "status": "HTTP_ERROR"}], []),
            ), mock.patch.object(
                final_verify,
                "cloud_log_search",
                return_value=([{"surface": "CLOUD", "status": "NOT_ATTEMPTED"}], []),
            ), mock.patch.object(
                final_verify,
                "bridge_storage_search",
                return_value=([{"surface": "BRIDGE", "status": "NO_STORAGE"}], []),
            ), mock.patch.object(
                final_verify,
                "provider_metadata_search",
                return_value=([{"surface": "PROVIDER", "status": "UNAVAILABLE"}], []),
            ):
                result = final_verify.execute_verification(output_root=Path(tmp), fixed_timestamp="2026-07-29T16:20:00Z")
                summary_exists = (result["run_dir"] / "verification_summary.json").exists()
                decision_exists = (result["run_dir"] / "verification_decision.json").exists()

        self.assertEqual(result["decisions"]["verification_status"], "FINAL_EXISTENCE_VERIFICATION_COMPLETE")
        self.assertEqual(result["decisions"]["result_existence_decision"], "NO_RECOVERABLE_RESULTS_FOUND_AFTER_FINAL_BOUNDED_SEARCH")
        self.assertEqual(result["decisions"]["retry_governance_decision"], "READY_FOR_SINGLE_GOVERNANCE_AUTHORIZED_RECOVERY_ATTEMPT")
        self.assertEqual(result["recovered_results"], [])
        self.assertEqual(result["conflicts"], [])
        self.assertEqual(len(result["retry_rows"]), 3)
        self.assertTrue(all(row["recommendation"] == "GOVERNANCE_RETRY_REASONABLE_NO_RECOVERABLE_RESULT" for row in result["retry_rows"]))
        self.assertTrue(summary_exists)
        self.assertTrue(decision_exists)


if __name__ == "__main__":
    unittest.main()
