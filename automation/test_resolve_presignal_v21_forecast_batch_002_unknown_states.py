from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from automation import resolve_presignal_v21_forecast_batch_002_unknown_states as resolver


class ForecastBatch002UnknownStateResolutionTest(unittest.TestCase):
    def test_only_three_unknown_calls_are_audited(self) -> None:
        self.assertEqual(len(resolver.UNKNOWN_CALL_IDS), 3)
        self.assertEqual(
            resolver.UNKNOWN_CALL_IDS,
            [
                "FCL_befd6d6947490cc19f4754b9",
                "FCL_1ce38eb60f0865beca69bb31",
                "FCL_d72f741393a7643ea859edb8",
            ],
        )
        self.assertTrue(set(resolver.UNKNOWN_CALL_IDS).isdisjoint(set(resolver.PROVEN_RETRY_SAFE_CALLS)))

    def test_classify_calls_keeps_unknown_state_calls_unresolved_without_exact_remote_match(self) -> None:
        identities = {
            call_id: {
                "forecast_call_id": call_id,
                "forecast_identity": f"STEP6_{index}",
                "episode_id": f"EP_{index}",
                "provider": "Gemini",
                "model": "gemini-2.5-flash-lite",
            }
            for index, call_id in enumerate(resolver.UNKNOWN_CALL_IDS, start=1)
        }
        local_rows = {
            call_id: {
                "transport_classification": {"category": "GOOGLE_API_TIMEOUT", "dispatch_certainty": "UNKNOWN"},
            }
            for call_id in resolver.UNKNOWN_CALL_IDS
        }

        unknown_inventory, retry_rows, recovered_rows, remote_terminal_failures, unresolved_rows = resolver.classify_calls(
            identities=identities,
            local_rows=local_rows,
            exact_matches=[],
        )

        self.assertEqual(len(unknown_inventory), 3)
        self.assertEqual(len(retry_rows), 3)
        self.assertEqual(len(unresolved_rows), 3)
        self.assertEqual(recovered_rows, [])
        self.assertEqual(remote_terminal_failures, [])
        self.assertTrue(all(row["classification"] == "REMOTE_EXECUTION_STATE_UNRESOLVED" for row in unknown_inventory))
        self.assertTrue(all(row["retry_safe"] is False for row in retry_rows))
        self.assertTrue(all(row["recommended_action"] == "MANUAL_GOVERNANCE_REVIEW_REQUIRED" for row in retry_rows))

    def test_repo_search_requires_exact_identifiers(self) -> None:
        identity = {
            "forecast_call_id": "FCL_test",
            "forecast_identity": "STEP6_test",
        }
        completed = mock.Mock(stdout="outputs/file.jsonl:1:FCL_test other text\n", returncode=0)
        with mock.patch.object(resolver.subprocess, "run", return_value=completed) as run_mock:
            result = resolver.repo_search(identity)
        self.assertEqual(result["status"], "MATCHES_FOUND")
        self.assertEqual(len(result["exact_hits"]), 1)
        self.assertIn("FCL_test", result["exact_hits"][0])
        args = run_mock.call_args.args[0]
        self.assertIn("FCL_test", args)
        self.assertIn("STEP6_test", args)

    def test_governance_options_cover_all_required_paths(self) -> None:
        rows = [{"forecast_call_id": "FCL_test"}]
        options = resolver.governance_options(rows)
        self.assertEqual({row["option_id"] for row in options}, {
            "OPTION_A_CONTINUE_HOLD",
            "OPTION_B_AUTHORIZE_RETRY_DESPITE_UNKNOWN_STATE",
            "OPTION_C_EXCLUDE_CALL",
        })

    def test_execute_resolution_creates_append_only_unresolved_audit_without_provider_calls(self) -> None:
        fake_identities = {
            call_id: {
                "forecast_call_id": call_id,
                "forecast_identity": f"STEP6_{index}",
                "episode_id": f"EP_{index}",
                "provider": "Gemini",
                "model": "gemini-2.5-flash-lite",
            }
            for index, call_id in enumerate(resolver.UNKNOWN_CALL_IDS, start=1)
        }
        fake_failed_rows = {
            "run_manifest": {
                "google_preflight": {
                    "resource_identity_result": {
                        "spreadsheet_id": "sheet123",
                        "script_id": "script123",
                    }
                }
            },
            "batch_call_manifest": [],
            "operation_journal": [],
            "raw_transport_results": [],
            "raw_provider_outputs": [],
            "failed_call_ledger": [],
        }
        fake_local_rows = [
            {
                "forecast_call_id": call_id,
                "transport_classification": {"category": "GOOGLE_API_TIMEOUT", "dispatch_certainty": "UNKNOWN"},
            }
            for call_id in resolver.UNKNOWN_CALL_IDS
        ]
        fake_log_rows = [{"source": "GOOGLE_SHEET_LOG_EXACT_SEARCH", "status": "NO_MATCH"}]
        fake_process_rows = [{"source": "LIST_SCRIPT_PROCESSES", "status": "HTTP_ERROR", "http_status": 403}]

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(
                resolver,
                "git_branch",
                return_value="codex/immediate-impulse-outcome-recovery-r1",
            ), mock.patch.object(
                resolver,
                "git_head",
                return_value=resolver.EXPECTED_HEAD,
            ), mock.patch.object(
                resolver,
                "is_descendant_of",
                return_value=True,
            ), mock.patch.object(
                resolver,
                "extract_call_identities",
                return_value=fake_identities,
            ), mock.patch.object(
                resolver,
                "failed_batch_rows",
                return_value=fake_failed_rows,
            ), mock.patch.object(
                resolver,
                "local_lifecycle_rows",
                return_value=fake_local_rows,
            ), mock.patch.object(
                resolver.google_clients,
                "load_credentials",
                return_value=object(),
            ), mock.patch.object(
                resolver.google_clients,
                "build_sheets_service",
                return_value=object(),
            ), mock.patch.object(
                resolver.google_clients,
                "build_script_service",
                return_value=object(),
            ), mock.patch.object(
                resolver,
                "sheet_log_search",
                return_value=(fake_log_rows, []),
            ), mock.patch.object(
                resolver,
                "process_api_search",
                return_value=(fake_process_rows, []),
            ), mock.patch.object(
                resolver,
                "repo_search",
                side_effect=lambda identity: {
                    "forecast_call_id": identity["forecast_call_id"],
                    "source": "LOCAL_REPO_EXACT_IDENTITY_SWEEP",
                    "status": "NO_MATCH",
                    "exact_hits": [],
                },
            ):
                result = resolver.execute_resolution(output_root=Path(tmp), fixed_timestamp="2026-07-29T16:00:00Z")
                inventory_exists = (result["run_dir"] / "unknown_call_inventory.jsonl").exists()
                retry_exists = (result["run_dir"] / "retry_eligibility_ledger.jsonl").exists()
                decision_exists = (result["run_dir"] / "resolution_decision.json").exists()

        self.assertEqual(result["decisions"]["unknown_state_resolution_status"], "UNKNOWN_CALL_STATES_UNRESOLVED")
        self.assertEqual(result["decisions"]["result_recovery_decision"], "REMOTE_RESULT_RECOVERY_NOT_PROVEN")
        self.assertEqual(result["decisions"]["retry_safety_decision"], "SOME_BATCH_002_CALLS_RETRY_SAFE")
        self.assertEqual(result["decisions"]["batch_002_next_decision"], "GOVERNANCE_REVIEW_REQUIRED")
        self.assertEqual(result["recovered_rows"], [])
        self.assertEqual(result["remote_terminal_failures"], [])
        self.assertEqual(len(result["unresolved_rows"]), 3)
        self.assertTrue(inventory_exists)
        self.assertTrue(retry_exists)
        self.assertTrue(decision_exists)


if __name__ == "__main__":
    unittest.main()
