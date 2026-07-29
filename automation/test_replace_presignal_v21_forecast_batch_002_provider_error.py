from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from automation import replace_presignal_v21_forecast_batch_002_provider_error as replacement
from automation.test_execute_presignal_v21_forecast_batch_001 import valid_raw_output


def success_transport() -> dict[str, object]:
    return {
        "status": "ok",
        "request_status": "attempted",
        "response_status": "ok",
        "terminal_status": "completed",
        "actual_provider": "Gemini",
        "actual_model": "gemini-2.5-flash-lite",
        "provider": "Gemini",
        "model": "gemini-2.5-flash-lite",
        "request_id": "req_ok",
        "provider_response_body": "{\"ok\":true}",
        "raw_response_blocks": None,
        "raw_output": valid_raw_output(),
        "completed_timestamp": "2026-07-29T16:20:00Z",
        "prompt_tokens": 10,
        "completion_tokens": 20,
    }


def provider_error_transport() -> dict[str, object]:
    return {
        "status": "error",
        "request_status": "attempted",
        "response_status": "error",
        "terminal_status": "error",
        "actual_provider": "",
        "actual_model": "",
        "provider": "Gemini",
        "model": "gemini-2.5-flash-lite",
        "requested_provider": "Gemini",
        "requested_model": "gemini-2.5-flash-lite",
        "request_id": None,
        "provider_response_body": "",
        "raw_response_blocks": None,
        "raw_output": "",
        "error": "provider_error: provider_error: Gemini 503",
        "completed_timestamp": "2026-07-29T16:20:00Z",
    }


class ProviderErrorReplacementTests(unittest.TestCase):
    def test_only_target_call_is_in_scope(self) -> None:
        target = replacement.load_target_bundle()
        self.assertEqual(target["call"]["forecast_call_id"], replacement.CALL_ID)

    def test_original_failed_evidence_remains_immutable(self) -> None:
        original = replacement.load_original_failed_evidence()
        before = json.dumps(original["raw_transport"], sort_keys=True)
        replacement.original_attempt_reclassification(replacement.load_target_bundle()["call"], original)
        after = json.dumps(original["raw_transport"], sort_keys=True)
        self.assertEqual(before, after)

    def test_original_provider_authority_failure_is_reconciled_append_only(self) -> None:
        target = replacement.load_target_bundle()
        original = replacement.load_original_failed_evidence()
        result = replacement.original_attempt_reclassification(target["call"], original)
        self.assertEqual(result["classification_decision"], "ORIGINAL_ATTEMPT_RECLASSIFIED_AS_FAILED_PROVIDER")
        self.assertEqual(result["reconciled_scientific_state"], "FAILED_PROVIDER")

    def test_gemini_503_with_no_provider_body_is_failed_provider(self) -> None:
        call = {"provider": "Gemini", "model": "gemini-2.5-flash-lite"}
        self.assertTrue(replacement.provider_error_without_payload(call, provider_error_transport()))

    def test_provider_error_wrappers_cannot_pass_as_valid_forecasts(self) -> None:
        self.assertFalse(replacement.successful_forecast_payload(provider_error_transport()))

    def test_response_status_must_be_success_before_forecast_parsing(self) -> None:
        transport = success_transport()
        transport["response_status"] = "error"
        self.assertFalse(replacement.successful_forecast_payload(transport))

    def test_provider_response_body_must_exist_before_forecast_parsing(self) -> None:
        transport = success_transport()
        transport["provider_response_body"] = ""
        self.assertFalse(replacement.successful_forecast_payload(transport))

    def test_error_route_identity_does_not_fabricate_actual_provider_or_model(self) -> None:
        transport = provider_error_transport()
        self.assertEqual(transport["actual_provider"], "")
        self.assertEqual(transport["actual_model"], "")

    def test_requested_provider_and_model_are_preserved_separately(self) -> None:
        transport = provider_error_transport()
        self.assertEqual(transport["requested_provider"], "Gemini")
        self.assertEqual(transport["requested_model"], "gemini-2.5-flash-lite")

    def test_exactly_one_replacement_attempt_is_authorized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            replacement.write_json(
                run_dir / "governance_authorization.json",
                {"maximum_additional_provider_calls": 1, "maximum_dispatches_for_call_in_move": 1},
            )
            auth = json.loads((run_dir / "governance_authorization.json").read_text())
            self.assertEqual(auth["maximum_additional_provider_calls"], 1)
            self.assertEqual(auth["maximum_dispatches_for_call_in_move"], 1)

    def test_no_automatic_retry_is_possible(self) -> None:
        services: list[object] = []

        def fake_factory() -> object:
            svc = object()
            services.append(svc)
            return svc

        def fake_preflight() -> dict[str, object]:
            return {
                "token_path": "/Users/junhoshino/projects/presignal/local/token.json",
                "token_path_external": True,
                "authentication_method": "test",
                "scope_names": [],
                "scope_verification_result": "PASSED",
                "read_only_preflight_result": "PASSED",
                "resource_identity_result": "PASSED",
                "google_writes": 0,
            }

        def fake_dispatch(_service: object, _script_id: str, _payload: dict[str, object]) -> dict[str, object]:
            return {"ok": True, "request": {"function": replacement.batch_exec.step6.BRIDGE_FUNCTION}, "classification": {"category": "READY"}, "result": provider_error_transport()}

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(replacement, "git_branch", return_value="codex/immediate-impulse-outcome-recovery-r1"), mock.patch.object(
            replacement, "git_head", return_value=replacement.EXPECTED_START_HEAD
        ), mock.patch.object(replacement, "is_descendant_of", return_value=True), mock.patch.object(
            replacement.batch_exec, "build_default_script_service_factory", return_value=(fake_factory, replacement.batch_exec.EXPECTED_SCRIPT_ID)
        ):
            result = replacement.execute_replacement(output_root=Path(tmp), fixed_timestamp="2026-07-29T16:15:00Z", auth_preflight=fake_preflight, dispatch=fake_dispatch)
        self.assertEqual(result["summary"]["replacement_attempt_count"], 1)
        self.assertEqual(len(services), 1)
        self.assertEqual(result["terminal_state"], "FAILED_PROVIDER")

    def test_fresh_apps_script_client_is_used(self) -> None:
        services: list[object] = []

        def fake_factory() -> object:
            svc = object()
            services.append(svc)
            return svc

        def fake_preflight() -> dict[str, object]:
            return {
                "token_path": "/Users/junhoshino/projects/presignal/local/token.json",
                "token_path_external": True,
                "authentication_method": "test",
                "scope_names": [],
                "scope_verification_result": "PASSED",
                "read_only_preflight_result": "PASSED",
                "resource_identity_result": "PASSED",
                "google_writes": 0,
            }

        def fake_dispatch(_service: object, _script_id: str, _payload: dict[str, object]) -> dict[str, object]:
            return {"ok": True, "request": {"function": replacement.batch_exec.step6.BRIDGE_FUNCTION}, "classification": {"category": "READY"}, "result": success_transport()}

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(replacement, "git_branch", return_value="codex/immediate-impulse-outcome-recovery-r1"), mock.patch.object(
            replacement, "git_head", return_value=replacement.EXPECTED_START_HEAD
        ), mock.patch.object(replacement, "is_descendant_of", return_value=True), mock.patch.object(
            replacement.batch_exec, "build_default_script_service_factory", return_value=(fake_factory, replacement.batch_exec.EXPECTED_SCRIPT_ID)
        ):
            replacement.execute_replacement(output_root=Path(tmp), fixed_timestamp="2026-07-29T16:16:00Z", auth_preflight=fake_preflight, dispatch=fake_dispatch)
        self.assertEqual(len(services), 1)

    def test_provider_authority_requires_exact_transport_agreement(self) -> None:
        call = replacement.load_target_bundle()["call"]
        passed = replacement.batch_exec.provider_authority_result(call, {"actual_provider": "Gemini", "actual_model": "gemini-2.5-flash-lite"})
        failed = replacement.batch_exec.provider_authority_result(call, {"actual_provider": "Gemini", "actual_model": "gemini-2.5-flash"})
        self.assertTrue(passed["authority_passed"])
        self.assertFalse(failed["authority_passed"])

    def test_successful_replacement_creates_exactly_one_authoritative_result(self) -> None:
        services: list[object] = []

        def fake_factory() -> object:
            svc = object()
            services.append(svc)
            return svc

        def fake_preflight() -> dict[str, object]:
            return {
                "token_path": "/Users/junhoshino/projects/presignal/local/token.json",
                "token_path_external": True,
                "authentication_method": "test",
                "scope_names": [],
                "scope_verification_result": "PASSED",
                "read_only_preflight_result": "PASSED",
                "resource_identity_result": "PASSED",
                "google_writes": 0,
            }

        def fake_dispatch(_service: object, _script_id: str, _payload: dict[str, object]) -> dict[str, object]:
            return {"ok": True, "request": {"function": replacement.batch_exec.step6.BRIDGE_FUNCTION}, "classification": {"category": "READY"}, "result": success_transport()}

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(replacement, "git_branch", return_value="codex/immediate-impulse-outcome-recovery-r1"), mock.patch.object(
            replacement, "git_head", return_value=replacement.EXPECTED_START_HEAD
        ), mock.patch.object(replacement, "is_descendant_of", return_value=True), mock.patch.object(
            replacement.batch_exec, "build_default_script_service_factory", return_value=(fake_factory, replacement.batch_exec.EXPECTED_SCRIPT_ID)
        ):
            result = replacement.execute_replacement(output_root=Path(tmp), fixed_timestamp="2026-07-29T16:17:00Z", auth_preflight=fake_preflight, dispatch=fake_dispatch)
            selection = json.loads((result["run_dir"] / "authoritative_result_selection.json").read_text())
        self.assertEqual(selection["authoritative_result"], "REPLACEMENT_RESULT")
        self.assertEqual(result["summary"]["batch_002_authoritative_valid_results"], 12)

    def test_batch_002_requires_12_authoritative_results_for_completion(self) -> None:
        services: list[object] = []

        def fake_factory() -> object:
            svc = object()
            services.append(svc)
            return svc

        def fake_preflight() -> dict[str, object]:
            return {
                "token_path": "/Users/junhoshino/projects/presignal/local/token.json",
                "token_path_external": True,
                "authentication_method": "test",
                "scope_names": [],
                "scope_verification_result": "PASSED",
                "read_only_preflight_result": "PASSED",
                "resource_identity_result": "PASSED",
                "google_writes": 0,
            }

        def fake_dispatch(_service: object, _script_id: str, _payload: dict[str, object]) -> dict[str, object]:
            return {"ok": True, "request": {"function": replacement.batch_exec.step6.BRIDGE_FUNCTION}, "classification": {"category": "READY"}, "result": provider_error_transport()}

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(replacement, "git_branch", return_value="codex/immediate-impulse-outcome-recovery-r1"), mock.patch.object(
            replacement, "git_head", return_value=replacement.EXPECTED_START_HEAD
        ), mock.patch.object(replacement, "is_descendant_of", return_value=True), mock.patch.object(
            replacement.batch_exec, "build_default_script_service_factory", return_value=(fake_factory, replacement.batch_exec.EXPECTED_SCRIPT_ID)
        ):
            result = replacement.execute_replacement(output_root=Path(tmp), fixed_timestamp="2026-07-29T16:18:00Z", auth_preflight=fake_preflight, dispatch=fake_dispatch)
        self.assertEqual(result["summary"]["batch_002_decision"], "FORECAST_BATCH_002_REMAINS_INCOMPLETE")
        self.assertEqual(result["summary"]["batch_002_authoritative_valid_results"], 11)

    def test_no_batch_003_no_google_writes_and_prior_evidence_immutable(self) -> None:
        original_path = replacement.OUTPUT_ROOT / replacement.GOVERNANCE_RECOVERY_ID / "failed_call_ledger.jsonl"
        before = original_path.read_text()
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "x"
            run_dir.mkdir()
            replacement.write_json(run_dir / "run_manifest.json", {"google_writes_executed": 0, "no_batch_003_execution": True})
            manifest = json.loads((run_dir / "run_manifest.json").read_text())
        self.assertEqual(manifest["google_writes_executed"], 0)
        self.assertTrue(manifest["no_batch_003_execution"])
        self.assertEqual(original_path.read_text(), before)


if __name__ == "__main__":
    unittest.main()
