"""Focused no-network tests for the one-use FRED binding probe runner."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from automation import run_presignal_v21_r6_fred_binding_resolution_v1 as fred


def supplied_record(request: dict) -> dict:
    return {
        "object": "NATIVE_ACQUISITION_RECORD", "acquisition_record_id": "NACQ_FIXTURE",
        "episode_id": fred.EPISODE, "pack_a_identity": fred.PACK_A,
        "request_identity": request["request_identity"], "forecast_cutoff_ts": fred.CUTOFF,
        "source_id": fred.SOURCE, "adapter_identity": fred.ADAPTER,
        "configuration_reference": fred.CONFIG, "credential_reference_type": fred.CREDENTIAL_TYPE,
        "source_identity": request["source_identity"], "source_url_or_key": request["source_url_or_key"],
        "source_type": request["source_type"], "query_identity": request["query_identity"],
        "retrieval_timestamp": "2026-07-24T00:00:00Z", "acquisition_timestamp": "2026-07-24T00:00:00Z",
        "source_timestamp": "2024-07-24T00:00:00Z", "as_of_timestamp": "2024-07-24T23:59:59Z",
        "acquisition_method": "caller_controlled_existing_v2_fetch", "status": "SUPPLIED",
        "raw_checksum": "sha256:raw", "normalized_checksum": "sha256:normalized",
        "raw_acquired_content": "fixture", "normalized_acquired_content": "fixture",
        "source_items": [{"canonical_field": "US2Y_YIELD_LEVEL", "value": 4.5}],
    }


class FredBindingResolutionTests(unittest.TestCase):
    def test_frozen_reference_has_no_alias_and_probe_authorization_is_deterministic(self) -> None:
        request = fred.probe_request("2026-07-24T00:00:00Z")
        first, second = fred.authorization(request), fred.authorization(request)
        self.assertEqual(first["authorization_fingerprint"], second["authorization_fingerprint"])
        self.assertEqual(first["call_budget"], 1)
        self.assertEqual(first["retry_budget"], 0)
        self.assertEqual(fred.CONFIG, "Apps Script Script Property FRED_API_KEY")

    def test_native_record_validation_requires_expected_lineage_and_pre_cutoff_timestamps(self) -> None:
        request = fred.probe_request("2026-07-24T00:00:00Z")
        valid = fred.validate_native_record(supplied_record(request), request)
        self.assertTrue(valid["valid"])
        bad = supplied_record(request); bad["source_id"] = "KSRC_UNAPPROVED"
        self.assertFalse(fred.validate_native_record(bad, request)["valid"])

    def test_secret_redaction_keeps_nonsecret_authorization_state(self) -> None:
        redacted = fred.redact({"authorization_activated": True, "api_key": "secret", "access_token": "secret"})
        self.assertTrue(redacted["authorization_activated"])
        self.assertEqual(redacted["api_key"], "REDACTED")
        self.assertEqual(redacted["access_token"], "REDACTED")

    def test_cutoff_closed_performs_no_probe_or_pack_e_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            decision = fred.run(Path(directory), dispatch=True, at_utc="2026-07-29T18:00:00Z")
            self.assertEqual(decision, "NEW_R6_PACK_E_FRED_BINDING_BLOCKED_CUTOFF_CLOSED")
            audit = json.loads((Path(directory) / "external_access_audit.json").read_text())
            self.assertTrue(all(value == 0 for value in audit.values()))
            auth = json.loads((Path(directory) / "r6_pack_e_acquisition_authorization_preparation.json").read_text())
            self.assertEqual(auth["status"], "NOT_CREATED")

    def test_successful_probe_creates_only_inactive_minimum_environment_and_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as directory, \
             mock.patch.object(fred.google_clients, "load_credentials", return_value=object()), \
             mock.patch.object(fred.google_clients, "build_script_service", return_value=object()), \
             mock.patch.object(fred.google_clients, "default_script_id", return_value="script"), \
             mock.patch.object(fred.google_clients, "run_script_function_with_metadata") as run:
            request = fred.probe_request("2026-07-24T00:00:00Z")
            run.return_value = {"ok": True, "elapsed_ms": 1, "classification": {"category": "READY"}, "result": supplied_record(request)}
            decision = fred.run(Path(directory), dispatch=True, at_utc="2026-07-24T00:00:00Z")
            self.assertEqual(decision, "NEW_R6_PACK_E_FRED_BINDING_PROVEN_ACQUISITION_AUTHORIZATION_PREPARED")
            self.assertEqual(run.call_count, 1)
            environment = json.loads((Path(directory) / "r6_pack_e_source_environment.json").read_text())
            self.assertEqual(environment["approved_source_identities"], ["KSRC_FRED"])
            self.assertEqual(environment["retry_budget"], 0)
            authorization = json.loads((Path(directory) / "r6_pack_e_acquisition_authorization_preparation.json").read_text())
            self.assertFalse(authorization["authorization_activated"])
            self.assertEqual(authorization["pack_e_acquisition_calls"], 0)
            audit = json.loads((Path(directory) / "external_access_audit.json").read_text())
            self.assertEqual(audit["fred_calls"], 1)
            self.assertEqual(audit["pack_e_constructions"], 0)

    def test_failed_probe_never_activates_pack_e_authorization_or_retries(self) -> None:
        with tempfile.TemporaryDirectory() as directory, \
             mock.patch.object(fred.google_clients, "load_credentials", return_value=object()), \
             mock.patch.object(fred.google_clients, "build_script_service", return_value=object()), \
             mock.patch.object(fred.google_clients, "default_script_id", return_value="script"), \
             mock.patch.object(fred.google_clients, "run_script_function_with_metadata", return_value={"ok": False, "classification": {"category": "SOURCE_ACCESS_NOT_AUTHORIZED"}, "response": None}) as run:
            decision = fred.run(Path(directory), dispatch=True, at_utc="2026-07-24T00:00:00Z")
            self.assertEqual(decision, "NEW_R6_PACK_E_FRED_ACCESS_PROBE_FAILED")
            self.assertEqual(run.call_count, 1)
            authorization = json.loads((Path(directory) / "r6_pack_e_acquisition_authorization_preparation.json").read_text())
            self.assertEqual(authorization["status"], "NOT_CREATED")


if __name__ == "__main__":
    unittest.main()
