from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from automation import recover_presignal_v21_forecast_batch_003_governance as recovery
from automation.test_execute_presignal_v21_forecast_batch_001 import valid_raw_output


class GovernanceRecoveryBatch003Test(unittest.TestCase):
    def test_scope_is_four_ssl_unknown_and_one_parse_replacement(self) -> None:
        bundle = recovery.verified_scope_bundle()
        categories = recovery.category_map(bundle["selected"])
        self.assertEqual(len(bundle["selected"]), 5)
        self.assertEqual(sum(1 for row in categories.values() if row["attempt_category"] == "GOVERNANCE_AUTHORIZED_UNKNOWN_STATE_RECOVERY"), 4)
        self.assertEqual(sum(1 for row in categories.values() if row["attempt_category"] == "GOVERNANCE_AUTHORIZED_PROVIDER_SCHEMA_REPLACEMENT"), 1)
        self.assertEqual(set(categories), set(recovery.IN_SCOPE_CALL_IDS))

    def test_only_five_calls_are_selected_from_frozen_batch(self) -> None:
        bundle = recovery.verified_scope_bundle()
        selected_ids = [row["call"]["forecast_call_id"] for row in bundle["selected"]]
        all_ids = [row["call"]["forecast_call_id"] for row in bundle["bundle"]["bundles"]]
        self.assertEqual(len(selected_ids), 5)
        self.assertEqual(len(all_ids), 12)
        self.assertEqual(len(set(all_ids) - set(selected_ids)), 7)

    def test_dispatch_states_fail_closed_on_unknown_transport(self) -> None:
        rows = recovery.dispatch_states_from_result(
            "FCL_test",
            {"ok": False, "classification": {"category": "UNKNOWN_SHARED_TRANSPORT_ERROR", "dispatch_certainty": "UNKNOWN"}},
            None,
        )
        self.assertEqual(rows[0]["state"], "REQUEST_SEND_STARTED")
        self.assertEqual(rows[-1]["state"], "REMOTE_STATE_UNKNOWN")

    def test_dispatch_states_record_confirmed_execution_path(self) -> None:
        rows = recovery.dispatch_states_from_result(
            "FCL_test",
            {"ok": True, "classification": {"category": "READY", "dispatch_certainty": "CONFIRMED_RESPONSE"}},
            {"request_status": "attempted", "execution_id": "exec_1"},
        )
        states = [row["state"] for row in rows]
        self.assertIn("GOOGLE_REQUEST_ACCEPTED", states)
        self.assertIn("APPS_SCRIPT_EXECUTION_ID_RECEIVED", states)
        self.assertIn("PROVIDER_DISPATCH_CONFIRMED", states)

    def test_authoritative_selection_reasons_follow_recovery_type(self) -> None:
        ssl_call = {"forecast_call_id": recovery.SSL_UNKNOWN_CALL_IDS[0]}
        parse_call = {"forecast_call_id": recovery.PARSE_REPLACEMENT_CALL_ID}
        ssl = recovery.authoritative_selection_row(
            ssl_call,
            {"attempt_category": "GOVERNANCE_AUTHORIZED_UNKNOWN_STATE_RECOVERY", "original_attempt_reference": {"x": 1}},
            "SUCCEEDED_VALID",
            Path("/tmp/RUN"),
        )
        parse = recovery.authoritative_selection_row(
            parse_call,
            {"attempt_category": "GOVERNANCE_AUTHORIZED_PROVIDER_SCHEMA_REPLACEMENT", "original_attempt_reference": {"x": 1}},
            "SUCCEEDED_VALID",
            Path("/tmp/RUN"),
        )
        self.assertIn("FINAL_BOUNDED_SEARCH", ssl["authority_reason"])
        self.assertIn("NULL_CONFIDENCE", parse["authority_reason"])

    def test_execute_recovery_uses_one_transport_per_call_and_no_more(self) -> None:
        service_instances: list[object] = []
        closed_instances: list[object] = []
        dispatched_calls: list[str] = []

        def fake_build_isolated() -> tuple[object, str, dict[str, object]]:
            service = object()
            service_instances.append(service)
            return service, "SCRIPT_ID", {"service_object_id": id(service), "underlying_http_object_id": id(service) + 1}

        def fake_dispatch(service: object, _script_id: str, payload: dict[str, object]) -> dict[str, object]:
            self.assertIs(service, service_instances[len(dispatched_calls)])
            dispatched_calls.append(str(payload["forecast_identity"]))
            return {
                "ok": True,
                "request": {"function": "apiCallAuthoritativeProviderJsonObject"},
                "classification": {"category": "READY", "dispatch_certainty": "CONFIRMED_RESPONSE"},
                "result": {
                    "status": "ok",
                    "request_status": "attempted",
                    "response_status": "ok",
                    "terminal_status": "completed",
                    "actual_provider": payload["provider"],
                    "actual_model": payload["model"],
                    "raw_output": valid_raw_output(),
                    "provider_response_body": '{"ok": true}',
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "completed_timestamp": "2026-07-29T17:50:00Z",
                },
            }

        def fake_close(service: object) -> dict[str, object]:
            closed_instances.append(service)
            return {
                "service_object_id": id(service),
                "underlying_http_object_id": id(service) + 1,
                "closed_paths": ["service.close", "authorized_http.close", "underlying_http.close"],
                "close_errors": [],
            }

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            recovery,
            "git_branch",
            return_value="codex/immediate-impulse-outcome-recovery-r1",
        ), mock.patch.object(
            recovery,
            "git_head",
            return_value=recovery.EXPECTED_START_HEAD,
        ), mock.patch.object(
            recovery,
            "is_descendant_of",
            return_value=True,
        ), mock.patch.object(
            recovery.batch_exec,
            "verify_google_preflight",
            return_value={
                "read_only_preflight_result": "PASSED",
                "resource_identity_result": "PASSED",
                "google_writes": 0,
            },
        ), mock.patch.object(
            recovery,
            "build_isolated_script_service",
            side_effect=fake_build_isolated,
        ), mock.patch.object(
            recovery.batch_exec,
            "default_dispatch",
            side_effect=fake_dispatch,
        ), mock.patch.object(
            recovery.google_clients,
            "close_google_service",
            side_effect=fake_close,
        ):
            result = recovery.execute_recovery(output_root=Path(tmp), fixed_timestamp="2026-07-29T18:20:00Z", enforce_head=False)

        self.assertEqual(len(service_instances), 5)
        self.assertEqual(len(closed_instances), 5)
        self.assertEqual(result["reconciliation"]["attempted_new_calls"], 5)
        self.assertEqual(result["reconciliation"]["valid_new_results"], 5)
        self.assertEqual(result["decision"]["recovery_status"], "BATCH_003_GOVERNANCE_RECOVERY_COMPLETE")

    def test_provider_error_wrapper_guard_still_blocks_parsing(self) -> None:
        payload = {"status": "error", "response_status": "error", "provider_response_body": "", "raw_output": ""}
        self.assertTrue(recovery.batch_exec.provider_error_without_forecast_payload(payload))

    def test_in_scope_call_with_existing_valid_result_blocks_new_dispatch(self) -> None:
        target_call = recovery.SSL_UNKNOWN_CALL_IDS[0]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            existing_dir = out / "PPHB-R1-FORECAST-EXECUTION-BATCH-XYZ"
            existing_dir.mkdir(parents=True)
            (existing_dir / "normalized_forecast_results.jsonl").write_text(
                recovery.canonical_json({"forecast_call_id": target_call, "terminal_state": "SUCCEEDED_VALID"}) + "\n"
            )
            with mock.patch.object(recovery, "git_branch", return_value="codex/immediate-impulse-outcome-recovery-r1"), mock.patch.object(
                recovery, "git_head", return_value=recovery.EXPECTED_START_HEAD
            ), mock.patch.object(recovery, "is_descendant_of", return_value=True), mock.patch.object(
                recovery.batch_exec, "verify_google_preflight", return_value={"read_only_preflight_result": "PASSED", "resource_identity_result": "PASSED", "google_writes": 0}
            ):
                result = recovery.execute_recovery(output_root=out, fixed_timestamp="2026-07-29T18:21:00Z", enforce_head=False)
        self.assertEqual(result["decision"]["recovery_status"], "BATCH_003_GOVERNANCE_RECOVERY_BLOCKED")
        self.assertEqual(result["reconciliation"]["skipped_existing_authoritative_results"], 1)


if __name__ == "__main__":
    unittest.main()
