from __future__ import annotations

import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

from automation import execute_presignal_v21_forecast_batch_003 as batch003
from automation.test_execute_presignal_v21_forecast_batch_001 import valid_raw_output


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


def success_dispatch(_service: object, _script_id: str, payload: dict[str, object]) -> dict[str, object]:
    return {
        "ok": True,
        "request": {"function": "apiCallAuthoritativeProviderJsonObject"},
        "classification": {"category": "READY"},
        "result": {
            "status": "ok",
            "response_status": "ok",
            "provider_response_body": "{\"ok\":true}",
            "actual_provider": payload["provider"],
            "actual_model": payload["model"],
            "provider": payload["provider"],
            "model": payload["model"],
            "request_id": f"req_{payload['forecast_identity']}",
            "raw_output": valid_raw_output(),
            "prompt_tokens": 111,
            "completion_tokens": 222,
            "completed_timestamp": "2026-07-29T16:40:00Z",
        },
    }


class ForecastBatch003Tests(unittest.TestCase):
    def test_only_batch_003_is_authorized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            preflight = batch003.verify_batch_003_preflight(output_root=Path(tmp))
            bundle = preflight["bundle"]
        self.assertEqual(bundle["user_batch_label"], "FORECAST_BATCH_003")
        self.assertEqual(bundle["frozen_batch_id"], "FCB_PACK_A_003")
        self.assertEqual(len(bundle["bundles"]), 12)
        self.assertEqual(len(set(preflight["authorized_call_ids"])), 12)

    def test_provider_composition_matches_frozen_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = batch003.verify_batch_003_preflight(output_root=Path(tmp))["bundle"]
        counts = Counter((row["call"]["provider"], row["call"]["model"]) for row in bundle["bundles"])
        self.assertEqual(counts[("Anthropic", "claude-haiku-4-5")], 5)
        self.assertEqual(counts[("Gemini", "gemini-2.5-flash-lite")], 4)
        self.assertEqual(counts[("OpenAI", "gpt-4o-mini-2024-07-18")], 3)

    def test_prior_batches_are_treated_as_closed(self) -> None:
        summary = batch003.verify_closed_priors()
        self.assertEqual(summary["batch_001_authoritative_valid_results"], 12)
        self.assertEqual(summary["batch_002_authoritative_valid_results"], 12)
        self.assertEqual(summary["cumulative_authoritative_valid_results_before_batch_003"], 24)

    def test_provider_error_wrappers_cannot_reach_parsing(self) -> None:
        self.assertTrue(
            batch003.batch_exec.provider_error_without_forecast_payload(
                {
                    "status": "ok",
                    "response_status": "error",
                    "provider_response_body": "",
                    "raw_output": "",
                }
            )
        )

    def test_execute_batch_003_uses_fresh_client_per_call(self) -> None:
        services: list[object] = []

        def fake_factory() -> object:
            svc = object()
            services.append(svc)
            return svc

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            batch003.batch_exec, "build_default_script_service_factory", return_value=(fake_factory, batch003.batch_exec.EXPECTED_SCRIPT_ID)
        ):
            result = batch003.execute_batch_003(
                output_root=Path(tmp),
                fixed_timestamp="2026-07-29T16:41:00Z",
                enforce_head=False,
                auth_preflight=fake_preflight,
                dispatch=success_dispatch,
                script_service_factory_override=(fake_factory, batch003.batch_exec.EXPECTED_SCRIPT_ID),
            )
        self.assertEqual(len(services), 12)
        self.assertEqual(result["decision"]["batch_status"], "FORECAST_BATCH_003_COMPLETE")

    def test_no_automatic_retries_and_no_double_dispatch(self) -> None:
        calls: list[str] = []

        def tracked_dispatch(_service: object, _script_id: str, payload: dict[str, object]) -> dict[str, object]:
            calls.append(str(payload["forecast_identity"]))
            return success_dispatch(_service, _script_id, payload)

        with tempfile.TemporaryDirectory() as tmp:
            result = batch003.execute_batch_003(
                output_root=Path(tmp),
                fixed_timestamp="2026-07-29T16:42:00Z",
                enforce_head=False,
                auth_preflight=fake_preflight,
                dispatch=tracked_dispatch,
            )
        self.assertEqual(len(calls), 12)
        self.assertEqual(len(set(calls)), 12)
        self.assertEqual(result["reconciliation"]["attempted_provider_calls"], 12)


if __name__ == "__main__":
    unittest.main()
