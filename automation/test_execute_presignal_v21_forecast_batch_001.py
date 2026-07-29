from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from automation import execute_presignal_v21_forecast_batch_001 as batch001
from automation import google_clients


def valid_raw_output() -> dict[str, object]:
    return {
        "object": "FORECAST",
        "system_version": "presignal_v2.1",
        "schema_version": "2.1.1",
        "no_signal_flag": False,
        "no_signal_reason": None,
        "confidence": 0.68,
        "immediate_impulse_direction": "UP",
        "immediate_impulse_peak_pips_min": 4.0,
        "immediate_impulse_peak_pips_max": 9.0,
        "immediate_impulse_confidence": 0.62,
        "early_reaction_5m_direction": "UP",
        "expected_reversal_flag": True,
        "expected_reversal_horizon_min": 30,
        "expected_path_summary": "Initial upside reaction with later fade.",
        "information_used": ["frozen_pack_payload"],
        "missing_information": [],
        "invalidation_condition": "Macro surprise already priced before release.",
        "path": [
            {
                "horizon_min": 5,
                "expected_direction": "UP",
                "expected_pips_min": 2.0,
                "expected_pips_max": 8.0,
                "stage_confidence": 0.66,
                "continuation_probability": 0.60,
                "reversal_probability": 0.20,
                "stage_reason": "Fast upside impulse on release.",
                "invalidation_condition": "No upside move within first minute.",
            },
            {
                "horizon_min": 15,
                "expected_direction": "UP",
                "expected_pips_min": 3.0,
                "expected_pips_max": 10.0,
                "stage_confidence": 0.67,
                "continuation_probability": 0.58,
                "reversal_probability": 0.24,
                "stage_reason": "Primary fifteen-minute direction remains up.",
                "invalidation_condition": "Prompt reversal below pre-release midpoint.",
            },
            {
                "horizon_min": 30,
                "expected_direction": "FLAT",
                "expected_pips_min": 0.0,
                "expected_pips_max": 0.0,
                "stage_confidence": 0.55,
                "continuation_probability": 0.40,
                "reversal_probability": 0.42,
                "stage_reason": "Momentum fades into consolidation.",
                "invalidation_condition": "Fresh upside acceleration through highs.",
            },
            {
                "horizon_min": 60,
                "expected_direction": "DOWN",
                "expected_pips_min": 1.0,
                "expected_pips_max": 7.0,
                "stage_confidence": 0.51,
                "continuation_probability": 0.25,
                "reversal_probability": 0.61,
                "stage_reason": "Mean reversion dominates by the hour mark.",
                "invalidation_condition": "Persistent positive repricing after 30 minutes.",
            },
        ],
    }


class ForecastBatch001Test(unittest.TestCase):
    def test_only_first_frozen_batch_is_authorized(self) -> None:
        bundle = batch001.verified_batch_bundle()
        self.assertEqual(bundle["user_batch_label"], "FORECAST_BATCH_001")
        self.assertEqual(bundle["frozen_batch_id"], "FCB_PACK_A_001")
        self.assertEqual(bundle["pack_type"], "PACK_A")
        self.assertEqual(len(bundle["bundles"]), 12)
        call_ids = [row["call"]["forecast_call_id"] for row in bundle["bundles"]]
        self.assertEqual(len(set(call_ids)), 12)
        self.assertTrue(all(row["call"]["batch_id"] == "FCB_PACK_A_001" for row in bundle["bundles"]))
        self.assertFalse(any(row["call"]["batch_id"] == "FCB_PACK_A_002" for row in bundle["bundles"]))

    def test_pack_and_prompt_fingerprints_resolve_for_batch_one(self) -> None:
        bundle = batch001.verified_batch_bundle()
        for row in bundle["bundles"]:
            call = row["call"]
            self.assertEqual(call["pack_row_fingerprint"], batch001.sha256_value(row["pack_row"]))
            self.assertEqual(
                row["prompt_fingerprint"]["prompt_text_fingerprint"],
                batch001.sha256_value(row["prompt_row"]["prompt_text"]),
            )
            self.assertEqual(
                row["prompt_fingerprint"]["prompt_context_fingerprint"],
                batch001.sha256_value(row["prompt_row"]["prompt_payload"]),
            )

    def test_leakage_audit_passes_for_real_batch_prompts(self) -> None:
        bundle = batch001.verified_batch_bundle()
        for row in bundle["bundles"]:
            audit = batch001.leakage_audit(
                row["prompt_row"]["prompt_text"],
                row["prompt_row"]["prompt_payload"],
                row["call"]["pack_type"],
            )
            self.assertTrue(audit["passed"], audit["violations"])

    def test_provider_authority_requires_exact_manifest_transport_match(self) -> None:
        bundle = batch001.verified_batch_bundle()
        call = bundle["bundles"][0]["call"]
        passed = batch001.provider_authority_result(
            call,
            {"actual_provider": call["provider"], "actual_model": call["model"]},
        )
        failed = batch001.provider_authority_result(
            call,
            {"actual_provider": "OpenAI", "actual_model": call["model"]},
        )
        self.assertTrue(passed["authority_passed"])
        self.assertFalse(failed["authority_passed"])

    def test_execute_batch_preserves_raw_output_and_validates_without_retry(self) -> None:
        calls_seen: list[str] = []

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

        def fake_dispatch(_service: object, _script_id: str, payload: dict[str, object]) -> dict[str, object]:
            calls_seen.append(str(payload["forecast_identity"]))
            return {
                "ok": True,
                "request": {"function": "apiCallAuthoritativeProviderJsonObject"},
                "classification": {"category": "READY"},
                "elapsed_ms": 10,
                "result": {
                    "status": "ok",
                    "actual_provider": payload["provider"],
                    "actual_model": payload["model"],
                    "raw_output": valid_raw_output(),
                    "prompt_tokens": 111,
                    "completion_tokens": 222,
                    "latency_ms": 333,
                    "completed_timestamp": "2026-07-29T12:35:00Z",
                },
            }

        with tempfile.TemporaryDirectory() as tmp:
            result = batch001.execute_batch(
                output_root=Path(tmp),
                fixed_timestamp="2026-07-29T12:34:56Z",
                enforce_head=False,
                auth_preflight=fake_preflight,
                dispatch=fake_dispatch,
            )
            run_dir = result["run_dir"]
            normalized = batch001.read_jsonl(run_dir / "normalized_forecast_results.jsonl")
            raw_transport = batch001.read_jsonl(run_dir / "raw_transport_results.jsonl")
            failed = batch001.read_jsonl(run_dir / "failed_call_ledger.jsonl")
            decision = batch001.read_json(run_dir / "batch_decision.json")
            self.assertEqual(len(calls_seen), 12)
            self.assertEqual(len(raw_transport), 12)
            self.assertEqual(len(normalized), 12)
            self.assertEqual(failed, [])
            self.assertEqual(decision["batch_status"], "FORECAST_BATCH_001_COMPLETE")
            self.assertEqual(decision["resume_decision"], "RESUME_PROTECTION_VALIDATED")

    def test_invalid_parse_stays_out_of_normalized_ledger(self) -> None:
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

        def fake_dispatch(_service: object, _script_id: str, payload: dict[str, object]) -> dict[str, object]:
            provider = payload["provider"]
            model = payload["model"]
            return {
                "ok": True,
                "request": {"function": "apiCallAuthoritativeProviderJsonObject"},
                "classification": {"category": "READY"},
                "elapsed_ms": 10,
                "result": {
                    "status": "ok",
                    "actual_provider": provider,
                    "actual_model": model,
                    "raw_output": "{not json}",
                    "prompt_tokens": 111,
                    "completion_tokens": 222,
                    "latency_ms": 333,
                    "completed_timestamp": "2026-07-29T12:35:00Z",
                },
            }

        with tempfile.TemporaryDirectory() as tmp:
            result = batch001.execute_batch(
                output_root=Path(tmp),
                fixed_timestamp="2026-07-29T12:34:56Z",
                enforce_head=False,
                auth_preflight=fake_preflight,
                dispatch=fake_dispatch,
            )
            run_dir = result["run_dir"]
            normalized = batch001.read_jsonl(run_dir / "normalized_forecast_results.jsonl")
            failed = batch001.read_jsonl(run_dir / "failed_call_ledger.jsonl")
            self.assertEqual(len(normalized), 0)
            self.assertEqual(len(failed), 12)
            self.assertTrue(all(row["terminal_state"] == "FAILED_PARSE" for row in failed))

    def test_default_script_service_factory_rebuilds_service_per_dispatch(self) -> None:
        fake_credentials = object()
        built_services: list[object] = []

        def fake_build(_creds: object, timeout_seconds: int) -> object:
            self.assertEqual(timeout_seconds, batch001.SCRIPT_HTTP_TIMEOUT_SECONDS)
            service = object()
            built_services.append(service)
            return service

        with mock.patch.object(batch001.google_clients, "load_credentials", return_value=fake_credentials), mock.patch.object(
            batch001.google_clients,
            "default_script_id",
            return_value="SCRIPT_ID",
        ), mock.patch.object(batch001.google_clients, "build_script_service", side_effect=fake_build):
            factory, script_id = batch001.build_default_script_service_factory()
            first = factory()
            second = factory()
        self.assertEqual(script_id, "SCRIPT_ID")
        self.assertEqual(len(built_services), 2)
        self.assertIs(first, built_services[0])
        self.assertIs(second, built_services[1])
        self.assertIsNot(first, second)

    def test_server_not_found_is_classified_as_confirmed_not_sent(self) -> None:
        exc = google_clients.ServerNotFoundError("Unable to find the server at script.googleapis.com")
        classified = google_clients.classify_google_exception(exc)
        self.assertEqual(classified["category"], "GOOGLE_API_CONNECTION_ERROR")
        self.assertEqual(classified["dispatch_certainty"], "CONFIRMED_NOT_SENT")


if __name__ == "__main__":
    unittest.main()
