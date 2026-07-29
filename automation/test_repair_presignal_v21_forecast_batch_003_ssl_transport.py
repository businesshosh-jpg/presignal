from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from automation import repair_presignal_v21_forecast_batch_003_ssl_transport as repair


class RepairForecastBatch003SslTransportTest(unittest.TestCase):
    def test_exactly_four_ssl_transport_calls_are_in_scope(self) -> None:
        self.assertEqual(len(repair.TRANSPORT_FAILURE_IDS), 4)
        self.assertNotIn(repair.PARSE_FAILED_CALL_ID, repair.TRANSPORT_FAILURE_IDS)

    def test_parse_failed_call_governance_preserves_non_recoverable_result(self) -> None:
        governance = repair.build_parse_failed_call_governance(
            {
                "parse_failure_analysis": {
                    "provider_authority_passed": True,
                    "raw_provider_output_contains_forecast": True,
                }
            }
        )
        self.assertEqual(governance["forecast_call_id"], repair.PARSE_FAILED_CALL_ID)
        self.assertEqual(governance["retry_classification"], "RETRY_AUTHORIZABLE_PROVEN_NO_VALID_RESULT")
        self.assertFalse(governance["existing_result_recoverable"])

    def test_result_search_conclusion_keeps_unknown_state_governance_bound(self) -> None:
        batch_state = {
            "raw_transport": {
                call_id: {"provider": "Gemini", "model": "gemini-2.5-flash-lite"}
                for call_id in repair.TRANSPORT_FAILURE_IDS
            }
        }
        exact_matches, recovered, retry_rows = repair.result_search_conclusion(
            batch_state,
            {call_id: [] for call_id in repair.TRANSPORT_FAILURE_IDS},
            [],
        )
        self.assertEqual(len(exact_matches), 4)
        self.assertEqual(recovered, [])
        self.assertTrue(all(row["classification"] == "GOVERNANCE_RETRY_REASONABLE_NO_RECOVERABLE_RESULT" for row in retry_rows))

    def test_call_free_transport_verification_builds_and_disposes_per_attempt(self) -> None:
        services: list[object] = []
        closed: list[object] = []

        class FakeService:
            def __init__(self) -> None:
                self._http = object()

        def fake_build(_creds: object, _timeout: int) -> FakeService:
            service = FakeService()
            services.append(service)
            return service

        def fake_describe(service: object) -> dict[str, object]:
            return {
                "service_object_id": id(service),
                "authorized_http_object_id": id(service) + 1,
                "underlying_http_object_id": id(service) + 2,
                "connection_count": 0,
                "connection_keys": [],
            }

        def fake_close(service: object) -> dict[str, object]:
            closed.append(service)
            return {
                "service_object_id": id(service),
                "authorized_http_object_id": id(service) + 1,
                "underlying_http_object_id": id(service) + 2,
                "closed_paths": ["service.close"],
                "close_errors": [],
                "connection_count": 0,
                "connection_keys": [],
            }

        with mock.patch.object(repair.google_clients, "load_credentials", return_value=object()), mock.patch.object(
            repair.google_clients,
            "default_script_id",
            return_value="SCRIPT_ID",
        ), mock.patch.object(
            repair.google_clients,
            "build_script_service",
            side_effect=fake_build,
        ), mock.patch.object(
            repair.google_clients,
            "describe_google_service_transport",
            side_effect=fake_describe,
        ), mock.patch.object(
            repair.google_clients,
            "close_google_service",
            side_effect=fake_close,
        ), mock.patch.object(
            repair.google_clients,
            "run_script_function_with_metadata",
            return_value={
                "ok": True,
                "classification": {"category": "READY"},
                "elapsed_ms": 5,
                "response": {"response": {"result": {"status": "READY"}}},
                "result": {"status": "READY"},
            },
        ):
            rows = repair.verify_call_free_transport()

        self.assertEqual(len(rows), repair.DIAGNOSTIC_INVOCATION_COUNT)
        self.assertEqual(len(services), repair.DIAGNOSTIC_INVOCATION_COUNT)
        self.assertEqual(len(closed), repair.DIAGNOSTIC_INVOCATION_COUNT)
        self.assertEqual({id(service) for service in services}, {id(service) for service in closed})

    def test_execute_repair_remains_call_free_and_append_only(self) -> None:
        verification_rows = [
            {
                "attempt": index,
                "result_ok": True,
                "classification": {"category": "READY"},
                "transport_created": {"underlying_http_object_id": index},
                "transport_closed": {"underlying_http_object_id": index, "closed_paths": ["service.close"], "close_errors": []},
            }
            for index in range(1, repair.DIAGNOSTIC_INVOCATION_COUNT + 1)
        ]
        batch_state = {
            "raw_transport": {
                call_id: {
                    "forecast_call_id": call_id,
                    "provider": "Gemini",
                    "model": "gemini-2.5-flash-lite",
                    "episode_id": f"EP_{call_id}",
                    "dispatch_timestamp": "2026-07-29T16:39:58Z",
                    "prompt_fingerprint": "sha256:prompt",
                    "pack_row_fingerprint": "sha256:pack",
                    "transport_classification": {
                        "exception_type": "SSLEOFError",
                        "message": "EOF occurred in violation of protocol (_ssl.c:1129)",
                    },
                }
                for call_id in repair.TRANSPORT_FAILURE_IDS
            },
            "failed": {call_id: {"terminal_state": "FAILED_TRANSPORT"} for call_id in repair.TRANSPORT_FAILURE_IDS},
            "operation_journal": [],
            "normalized": {},
            "reconciliation": {},
            "summary": {},
            "decision": {},
            "run_dir": Path("/tmp/batch003"),
        }
        diagnosis_state = {
            "transport_failure_analysis": {
                call_id: {
                    "forecast_call_id": call_id,
                    "classification": "REMOTE_EXECUTION_STATE_UNKNOWN",
                    "dispatch_certainty": "UNKNOWN",
                    "exception_class": "SSLEOFError",
                    "full_exception_chain": [{"exception_type": "SSLEOFError"}],
                }
                for call_id in repair.TRANSPORT_FAILURE_IDS
            },
            "shared_failure_analysis": {"decision": "SHARED_TRANSPORT_DEFECT_CONFIRMED"},
            "retry_safety": {},
            "parse_failure_analysis": {
                "provider_authority_passed": True,
                "raw_provider_output_contains_forecast": True,
            },
            "run_dir": Path("/tmp/diag003"),
        }
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            repair,
            "git_branch",
            return_value="codex/immediate-impulse-outcome-recovery-r1",
        ), mock.patch.object(
            repair,
            "git_head",
            return_value=repair.EXPECTED_START_HEAD,
        ), mock.patch.object(
            repair,
            "is_descendant_of",
            return_value=True,
        ), mock.patch.object(
            repair,
            "load_batch_003_state",
            return_value=batch_state,
        ), mock.patch.object(
            repair,
            "load_batch_003_diagnosis_state",
            return_value=diagnosis_state,
        ), mock.patch.object(
            repair,
            "verify_call_free_transport",
            return_value=verification_rows,
        ), mock.patch.object(
            repair,
            "search_local_outputs",
            return_value=([], {call_id: [] for call_id in repair.TRANSPORT_FAILURE_IDS}),
        ), mock.patch.object(
            repair,
            "search_filesystem_orphans",
            return_value=[],
        ), mock.patch.object(
            repair,
            "search_google_sheet_logs",
            return_value=[],
        ), mock.patch.object(
            repair,
            "process_records_for_time_windows",
            return_value=[],
        ), mock.patch.object(
            repair,
            "search_bridge_side_storage",
            return_value=[],
        ), mock.patch.object(
            repair,
            "search_provider_metadata",
            return_value=[],
        ):
            result = repair.execute_repair(output_root=Path(tmp), fixed_timestamp="2026-07-29T18:00:00Z")

        self.assertEqual(result["repair_decision"], "SHARED_SSL_TRANSPORT_REPAIR_VALIDATED")
        self.assertEqual(result["verification_decision"], "CALL_FREE_TRANSPORT_VERIFICATION_PASSED")
        self.assertEqual(result["result_existence_decision"], "NO_RECOVERABLE_RESULTS_FOUND")
        self.assertEqual(result["governance_decision"], "READY_FOR_SINGLE_GOVERNANCE_AUTHORIZED_BATCH_003_RECOVERY")
        self.assertEqual(result["reconciliation"]["batch_003_authoritative_valid"], 7)
        self.assertEqual(result["reconciliation"]["batch_003_unresolved_calls"], 5)


if __name__ == "__main__":
    unittest.main()
