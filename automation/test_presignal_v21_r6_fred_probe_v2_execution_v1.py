from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation import run_presignal_v21_r6_fred_probe_v2_execution_v1 as subject


def prepared_auth() -> dict:
    return {
        "authorization_name": subject.AUTH_NAME,
        "authorization_fingerprint": subject.AUTH_FP,
        "authorization_valid": True,
        "authorization_activated": False,
        "episode_identity": subject.EPISODE,
        "pack_a_identity": subject.PACK_A,
        "pack_a_content_checksum": subject.PACK_A_CONTENT,
        "ksrc_fred_source_identity": subject.SOURCE,
        "prospective_fred_adapter_identity": subject.ADAPTER,
        "new_apps_script_deployment_identity_or_mode": subject.DEPLOYMENT_MODE,
        "deployed_source_fingerprint": subject.DEPLOYED_SOURCE_FP,
        "bounded_query_identity": subject.QUERY_IDENTITY,
        "call_budget": 1,
        "retry_budget": 0,
        "forecast_cutoff": subject.CUTOFF,
        "no_writer_contract": True,
        "consumed_v1_authorization_fingerprint": subject.V1_AUTH_FP,
    }


def selected_manifest() -> dict:
    return {
        "content_checksum": "sha256:episode-content",
        "provenance_checksum": "sha256:episode-provenance",
        "lineage_checksum": "sha256:episode-lineage",
    }


def minimum_required() -> dict:
    return {
        "required_fields": [
            {
                "capability_id": "TREASURY_2Y_10Y_PRESESSION_STATE",
                "classification": "REQUIRED",
                "field_binding": [
                    "US2Y_YIELD_LEVEL",
                    "US10Y_YIELD_LEVEL",
                    "US2Y_CHANGE_FROM_PRIOR_CLOSE",
                    "US10Y_CHANGE_FROM_PRIOR_CLOSE",
                    "US10Y_MINUS_US2Y_CURVE",
                ],
                "request_identity": subject.REQUEST_IDENTITY,
            }
        ],
        "optional_fields": ["DXY_PRESESSION_STATE", "USDJPY_PRESESSION_STATE"],
        "contextual_or_not_acquired": ["LABOR_MARKET_CONTEXT"],
    }


def source_bindings() -> dict:
    return {
        "candidate_source_bindings": {
            "KSRC_FRED": ["US2Y_YIELD_LEVEL", "US10Y_YIELD_LEVEL"],
            "KSRC_FMP": ["DXY_PRESESSION_STATE", "USDJPY_PRESESSION_STATE"],
        }
    }


def capability_inventory() -> dict:
    return {
        "capabilities": [
            {"source_identity": "KSRC_FMP", "runtime_readiness": "APPROVED_AND_RUNTIME_READY_FOR_ITS_DECLARED_FIELDS"},
            {"source_identity": "KSRC_FRED", "runtime_readiness": "APPROVED_BUT_CONFIGURATION_MISSING"},
        ]
    }


def supplied_record() -> dict:
    raw = {
        "source_id": "KSRC_FRED",
        "query_identity": subject.QUERY_IDENTITY,
        "query_symbol": subject.SERIES,
        "bounded_start_date": subject.DATE_START,
        "bounded_end_date": subject.DATE_END,
        "rows": [
            {"date": "2024-07-22", "value": 4.6},
            {"date": "2024-07-23", "value": 4.7},
            {"date": "2024-07-24", "value": 4.8},
        ],
    }
    normalized = {
        "canonical_field": "US2Y_YIELD_LEVEL",
        "selected_observation": {"date": "2024-07-24", "value": 4.8},
        "source_identity": "fred:series:DGS2",
        "source_timestamp": "2024-07-24T00:00:00.000Z",
        "as_of_timestamp": "2024-07-24T23:59:59.000Z",
    }
    return {
        "object": "NATIVE_ACQUISITION_RECORD",
        "acquisition_record_id": "NACQ_probe",
        "schema_version": "presignal.prospective_pack_e_acquisition.v1",
        "episode_id": subject.EPISODE,
        "pack_a_identity": subject.PACK_A,
        "request_identity": subject.REQUEST_IDENTITY,
        "forecast_cutoff_ts": subject.CUTOFF,
        "source_id": subject.SOURCE,
        "adapter_identity": subject.ADAPTER,
        "configuration_reference": subject.CONFIG_REF_VERBOSE,
        "credential_reference_type": subject.CREDENTIAL_TYPE,
        "source_identity": "fred:series:DGS2",
        "source_url_or_key": "fred:series:DGS2",
        "source_type": "historical_series_observation",
        "query_identity": subject.QUERY_IDENTITY,
        "retrieval_timestamp": "2026-07-24T08:20:00Z",
        "acquisition_timestamp": "2026-07-24T08:20:00Z",
        "source_timestamp": "2024-07-24T00:00:00.000Z",
        "as_of_timestamp": "2024-07-24T23:59:59.000Z",
        "acquisition_method": "caller_controlled_existing_v2_fetch",
        "status": "SUPPLIED",
        "error_classification": "",
        "reason": "",
        "raw_acquired_content": json.dumps(raw, sort_keys=True, separators=(",", ":")),
        "normalized_acquired_content": json.dumps(normalized, sort_keys=True, separators=(",", ":")),
        "raw_checksum": "sha256:raw",
        "normalized_checksum": "sha256:norm",
        "source_items": [
            {
                "canonical_field": "US2Y_YIELD_LEVEL",
                "value": 4.8,
                "value_type": "percent",
                "source_id": subject.SOURCE,
                "source_name": "Federal Reserve Economic Data",
                "source_identity": "fred:series:DGS2",
                "source_timestamp": "2024-07-24T00:00:00.000Z",
                "as_of_timestamp": "2024-07-24T23:59:59.000Z",
                "acquisition_timestamp": "2026-07-24T08:20:00Z",
                "acquisition_method": "caller_controlled_existing_v2_fetch",
            }
        ],
    }


def unavailable_record(error_classification: str, reason: str) -> dict:
    return {
        "object": "NATIVE_ACQUISITION_RECORD",
        "acquisition_record_id": "NACQ_unavailable",
        "schema_version": "presignal.prospective_pack_e_acquisition.v1",
        "episode_id": subject.EPISODE,
        "pack_a_identity": subject.PACK_A,
        "request_identity": subject.REQUEST_IDENTITY,
        "forecast_cutoff_ts": subject.CUTOFF,
        "source_id": subject.SOURCE,
        "adapter_identity": subject.ADAPTER,
        "configuration_reference": subject.CONFIG_REF_VERBOSE,
        "credential_reference_type": subject.CREDENTIAL_TYPE,
        "source_identity": "fred:series:DGS2",
        "source_url_or_key": "fred:series:DGS2",
        "source_type": "historical_series_observation",
        "query_identity": subject.QUERY_IDENTITY,
        "retrieval_timestamp": "2026-07-24T08:20:00Z",
        "acquisition_timestamp": "2026-07-24T08:20:00Z",
        "status": "UNAVAILABLE",
        "error_classification": error_classification,
        "reason": reason,
        "raw_acquired_content": "",
        "normalized_acquired_content": "",
        "raw_checksum": "sha256:",
        "normalized_checksum": "sha256:",
        "source_items": [],
    }


def fake_read_json(path: Path):
    text = str(path)
    if text.endswith("fred_probe_v2_authorization_preparation.json"):
        return prepared_auth()
    if text.endswith("new_r6_selected_episode_manifest.json"):
        return selected_manifest()
    if text.endswith("pack_e_minimum_required_coverage.json"):
        return minimum_required()
    if text.endswith("pack_e_source_field_binding_report.json"):
        return source_bindings()
    if text.endswith("pack_e_runtime_ready_capability_inventory.json"):
        return capability_inventory()
    raise AssertionError(f"unexpected path {path}")


class FredProbeV2ExecutionTests(unittest.TestCase):
    def test_authorization_validation_accepts_exact_prepared_binding(self) -> None:
        validated = subject.authorization_validation(prepared_auth())
        self.assertTrue(validated["authorization_valid"])

    def test_authorization_mismatch_blocks_dispatch(self) -> None:
        bad = prepared_auth()
        bad["authorization_fingerprint"] = "sha256:wrong"
        with tempfile.TemporaryDirectory() as temporary, patch.object(subject, "read_json", side_effect=lambda path: bad):
            decision = subject.run(Path(temporary), dispatch=False, at_utc="2026-07-24T08:20:00Z")
        self.assertEqual(decision, "NEW_R6_PACK_E_FRED_PROBE_V2_BLOCKED_AUTHORIZATION_MISMATCH")

    def test_cutoff_closed_blocks_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, patch.object(subject, "read_json", side_effect=fake_read_json):
            decision = subject.run(Path(temporary), dispatch=False, at_utc="2026-07-29T18:00:00Z")
        self.assertEqual(decision, "NEW_R6_PACK_E_FRED_PROBE_V2_BLOCKED_CUTOFF_CLOSED")

    def test_missing_reference_classifies_as_binding_not_found(self) -> None:
        record = unavailable_record("SOURCE_CONTENT_NOT_FOUND", "NO_OBSERVATION_AT_OR_BEFORE_AS_OF")
        classification, decision, binding = subject.classify_probe(record, {"ok": True})
        self.assertEqual(classification, "FRED_CONFIGURATION_REFERENCE_MISSING")
        self.assertEqual(decision, "NEW_R6_PACK_E_FRED_BINDING_NOT_FOUND")
        self.assertFalse(binding["reference_found"])

    def test_access_denied_classifies_as_failed_probe(self) -> None:
        record = unavailable_record("SOURCE_ACCESS_NOT_AUTHORIZED", "FETCH_FAILED:FRED HTTP 401")
        classification, decision, binding = subject.classify_probe(record, {"ok": True})
        self.assertEqual(classification, "FRED_ACCESS_NOT_AUTHORIZED")
        self.assertEqual(decision, "NEW_R6_PACK_E_FRED_ACCESS_PROBE_V2_FAILED")
        self.assertTrue(binding["reference_found"])

    def test_native_record_validation_accepts_supplied_record(self) -> None:
        validation = subject.validate_native_record(supplied_record(), subject.request_payload("2026-07-24T08:20:00Z"))
        self.assertTrue(validation["schema_valid"])
        self.assertTrue(validation["provenance_valid"])
        self.assertTrue(validation["lineage_valid"])
        self.assertEqual(validation["writer_count"], 0)

    def test_temporal_validation_is_deterministic(self) -> None:
        validated = subject.temporal_validation(supplied_record(), subject.request_payload("2026-07-24T08:20:00Z"))
        self.assertTrue(validated["bounded_query_preserved"])
        self.assertTrue(validated["timestamps_parse_deterministically"])
        self.assertTrue(validated["latest_eligible_observation_selection_deterministic"])
        self.assertFalse(validated["post_query_observation_used"])

    def test_successful_probe_prepares_inactive_acquisition_authorization(self) -> None:
        metadata = {"ok": True, "classification": {"category": "READY"}, "result": supplied_record()}
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(subject, "read_json", side_effect=fake_read_json), \
             patch.object(subject.google_clients, "load_credentials", return_value="creds"), \
             patch.object(subject.google_clients, "build_script_service", return_value="service"), \
             patch.object(subject.google_clients, "default_script_id", return_value="script"), \
             patch.object(subject.google_clients, "run_script_function_with_metadata", return_value=metadata):
            decision = subject.run(Path(temporary), dispatch=True, at_utc="2026-07-24T08:20:00Z")
            self.assertEqual(decision, "NEW_R6_PACK_E_FRED_BINDING_PROVEN_ACQUISITION_AUTHORIZATION_PREPARED")
            audit = json.loads((Path(temporary) / "external_access_audit.json").read_text())
            self.assertEqual(audit["apps_script_executions"], 1)
            self.assertEqual(audit["fred_calls"], 1)
            auth = json.loads((Path(temporary) / "r6_pack_e_acquisition_authorization_preparation.json").read_text())
            self.assertTrue(auth["authorization_valid"])
            self.assertFalse(auth["authorization_activated"])
            self.assertEqual(auth["pack_e_acquisition_calls"], 0)

    def test_transport_failure_stops_without_environment(self) -> None:
        metadata = {"ok": False, "classification": {"category": "GOOGLE_API_CONNECTION_ERROR"}, "response": None}
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(subject, "read_json", side_effect=fake_read_json), \
             patch.object(subject.google_clients, "load_credentials", return_value="creds"), \
             patch.object(subject.google_clients, "build_script_service", return_value="service"), \
             patch.object(subject.google_clients, "default_script_id", return_value="script"), \
             patch.object(subject.google_clients, "run_script_function_with_metadata", return_value=metadata):
            decision = subject.run(Path(temporary), dispatch=True, at_utc="2026-07-24T08:20:00Z")
            self.assertEqual(decision, "NEW_R6_PACK_E_FRED_ACCESS_PROBE_V2_FAILED")
            env = json.loads((Path(temporary) / "r6_pack_e_source_environment.json").read_text())
            self.assertEqual(env["status"], "NOT_CREATED")


if __name__ == "__main__":
    unittest.main()
