from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from automation import run_presignal_v21_r6_pack_e_acquisition_v1 as subject


def native_record(series: str, field: str, latest: float, prior: float) -> dict:
    start = "2026-07-16"
    end = "2026-07-23"
    request = subject.series_request(
        series=series,
        canonical_field=field,
        query_start=start,
        query_end=end,
        as_of_timestamp="2026-07-23T23:59:59Z",
        retrieval_timestamp="2026-07-24T09:00:00Z",
    )
    rows = [
        {"date": "2026-07-22", "value": prior},
        {"date": "2026-07-23", "value": latest},
    ]
    raw = {
        "source_id": subject.SOURCE,
        "query_identity": request["query_identity"],
        "query_symbol": request["query_symbol"],
        "bounded_start_date": start,
        "bounded_end_date": end,
        "rows": rows,
    }
    normalized = {
        "canonical_field": field,
        "selected_observation": rows[-1],
        "source_identity": request["source_identity"],
        "source_timestamp": "2026-07-23T00:00:00.000Z",
        "as_of_timestamp": "2026-07-23T23:59:59.000Z",
    }
    return {
        "object": "NATIVE_ACQUISITION_RECORD",
        "schema_version": "presignal.prospective_pack_e_acquisition.v1",
        "acquisition_record_id": f"NACQ_{series}",
        "episode_id": subject.EPISODE,
        "pack_a_identity": subject.PACK_A_ID,
        "request_identity": subject.TREASURY_REQUEST_ID,
        "forecast_cutoff_ts": subject.CUTOFF,
        "source_id": subject.SOURCE,
        "adapter_identity": subject.ADAPTER,
        "configuration_reference": subject.CONFIG_REF_VERBOSE,
        "credential_reference_type": subject.CREDENTIAL_TYPE,
        "source_identity": request["source_identity"],
        "source_url_or_key": request["source_url_or_key"],
        "source_type": subject.SOURCE_TYPE,
        "query_identity": request["query_identity"],
        "retrieval_timestamp": "2026-07-24T09:00:00Z",
        "acquisition_timestamp": "2026-07-24T09:00:00Z",
        "source_timestamp": "2026-07-23T00:00:00.000Z",
        "as_of_timestamp": "2026-07-23T23:59:59.000Z",
        "acquisition_method": "caller_controlled_existing_v2_fetch",
        "status": "SUPPLIED",
        "error_classification": "",
        "reason": "",
        "raw_acquired_content": subject.canonical(raw),
        "normalized_acquired_content": subject.canonical(normalized),
        "raw_checksum": subject.sha(raw),
        "normalized_checksum": subject.sha(normalized),
        "source_items": [{
            "canonical_field": field,
            "value": latest,
            "value_type": "percent",
            "source_id": subject.SOURCE,
            "source_name": subject.SOURCE_NAME,
            "source_identity": request["source_identity"],
            "source_timestamp": "2026-07-23T00:00:00.000Z",
            "as_of_timestamp": "2026-07-23T23:59:59.000Z",
            "acquisition_timestamp": "2026-07-24T09:00:00Z",
            "acquisition_method": "caller_controlled_existing_v2_fetch",
        }],
    }


class PackEAcquisitionTests(unittest.TestCase):
    def test_cutoff_closed_behavior(self) -> None:
        self.assertFalse(subject.cutoff_open("2026-07-29T18:00:00Z"))
        self.assertFalse(subject.cutoff_open("2026-07-30T00:00:00Z"))

    def test_series_request_preserves_bounded_query(self) -> None:
        request = subject.series_request(
            series="DGS2",
            canonical_field="US2Y_YIELD_LEVEL",
            query_start="2026-07-16",
            query_end="2026-07-23",
            as_of_timestamp="2026-07-23T23:59:59Z",
            retrieval_timestamp="2026-07-24T09:00:00Z",
        )
        self.assertEqual(request["bounded_start_date"], "2026-07-16")
        self.assertEqual(request["bounded_end_date"], "2026-07-23")
        self.assertEqual(request["query_symbol"], "DGS2")

    def test_native_record_validation_and_temporal_validation(self) -> None:
        record = native_record("DGS2", "US2Y_YIELD_LEVEL", 4.37, 4.40)
        request = subject.series_request(
            series="DGS2",
            canonical_field="US2Y_YIELD_LEVEL",
            query_start="2026-07-16",
            query_end="2026-07-23",
            as_of_timestamp="2026-07-23T23:59:59Z",
            retrieval_timestamp="2026-07-24T09:00:00Z",
        )
        validation = subject.validate_native_record(record, request, expected_field="US2Y_YIELD_LEVEL", expected_series="DGS2")
        temporal = subject.temporal_validation(record, request)
        self.assertTrue(validation["schema_valid"])
        self.assertTrue(validation["provenance_valid"])
        self.assertTrue(validation["lineage_valid"])
        self.assertEqual(validation["writer_count"], 0)
        self.assertTrue(temporal["temporal_valid"])
        self.assertFalse(temporal["same_day_value_used"])

    def test_series_mismatch_rejected(self) -> None:
        record = native_record("DGS2", "US2Y_YIELD_LEVEL", 4.37, 4.40)
        request = subject.series_request(
            series="DGS10",
            canonical_field="US10Y_YIELD_LEVEL",
            query_start="2026-07-16",
            query_end="2026-07-23",
            as_of_timestamp="2026-07-23T23:59:59Z",
            retrieval_timestamp="2026-07-24T09:00:00Z",
        )
        validation = subject.validate_native_record(record, request, expected_field="US10Y_YIELD_LEVEL", expected_series="DGS10")
        self.assertFalse(validation["schema_valid"])

    def test_treasury_state_is_deterministic_and_uses_frozen_fields_only(self) -> None:
        dgs2 = native_record("DGS2", "US2Y_YIELD_LEVEL", 4.37, 4.40)
        dgs10 = native_record("DGS10", "US10Y_YIELD_LEVEL", 4.29, 4.31)
        first = subject.derive_treasury_state(dgs2, dgs10)
        second = subject.derive_treasury_state(dgs2, dgs10)
        self.assertEqual(first, second)
        self.assertEqual(
            sorted(first["derived_fields"].keys()),
            [
                "us10y_change_from_prior",
                "us10y_minus_us2y_curve",
                "us10y_yield_level",
                "us2y_change_from_prior",
                "us2y_yield_level",
            ],
        )
        self.assertEqual(first["derived_fields"]["us10y_minus_us2y_curve"], -0.08)

    def test_composite_record_is_deterministic(self) -> None:
        dgs2 = native_record("DGS2", "US2Y_YIELD_LEVEL", 4.37, 4.40)
        dgs10 = native_record("DGS10", "US10Y_YIELD_LEVEL", 4.29, 4.31)
        treasury = subject.derive_treasury_state(dgs2, dgs10)
        first = subject.treasury_state_to_composite_record(treasury, dgs2, dgs10, "2026-07-24T09:00:00Z")
        second = subject.treasury_state_to_composite_record(treasury, dgs2, dgs10, "2026-07-24T09:00:00Z")
        self.assertEqual(first, second)
        self.assertEqual(len(first["source_items"]), 5)
        self.assertEqual(first["source_items"][0]["canonical_field"], "US2Y_YIELD_LEVEL")

    def test_separation_report_uses_pack_builder_request_lineage(self) -> None:
        root = Path("/Users/junhoshino/projects/presignal-designed-drift-redesign")
        pack_a = json.loads((root / "outputs/presignal_v21_designed_drift_r6_pack_construction_fomc/R6-PACK-CONSTRUCTION-FOMC-20260724-v1/new_r6_pack_a.json").read_text())
        current_requests = json.loads((root / "outputs/presignal_v21_designed_drift_r6_information_request_priority_contract_repair/R6-INFORMATION-REQUEST-PRIORITY-CONTRACT-REPAIR-20260724-v1/new_r6_canonical_information_requests.json").read_text())["requests"]
        pack_e = json.loads((root / "outputs/presignal_v21_designed_drift_r6_pack_e_acquisition/R6-PACK-E-ACQUISITION-20260724-v1/new_r6_pack_e.json").read_text())
        pack_builder_requests = subject.adapt_requests_for_pack_builder(current_requests)
        bundle = {
            "request_fingerprint": subject.sha(pack_builder_requests),
            "authorized_source_environment_id": "R6_PACK_E_FRED_TREASURY_MINIMUM_V2",
        }
        composite = {
            "request_identity": subject.TREASURY_REQUEST_ID,
            "episode_id": subject.EPISODE,
            "pack_a_identity": subject.PACK_A_ID,
        }
        report = subject.separation_report(pack_a, pack_e, bundle, composite)
        self.assertTrue(report["request_lineage_valid"])
        self.assertTrue(report["separation_passed"])

    def test_coverage_report_treats_treasury_items_as_required_direct_support(self) -> None:
        root = Path("/Users/junhoshino/projects/presignal-designed-drift-redesign")
        pack_e = json.loads((root / "outputs/presignal_v21_designed_drift_r6_pack_e_acquisition/R6-PACK-E-ACQUISITION-20260724-v1/new_r6_pack_e.json").read_text())
        report = subject.coverage_report(pack_e)
        treasury_rows = [row for row in report["coverage"] if row["category"] == "treasury_yields"]
        self.assertEqual(len(treasury_rows), 1)
        self.assertEqual(treasury_rows[0]["coverage_status"], "DIRECT_SUPPORT")
        self.assertTrue(report["required_coverage_complete"])

    def test_transport_failure_classification(self) -> None:
        classification, counted = subject.classify_transport(None, {"ok": False})
        self.assertEqual(classification, "SOURCE_TRANSPORT_FAILED")
        self.assertTrue(counted)

    def test_source_content_not_found_is_failure_without_retry(self) -> None:
        record = {
            "status": "UNAVAILABLE",
            "error_classification": "SOURCE_CONTENT_NOT_FOUND",
        }
        classification, counted = subject.classify_transport(record, {"ok": True})
        self.assertEqual(classification, "SOURCE_CONTENT_NOT_FOUND")
        self.assertFalse(counted)

    def test_secret_safety_redaction(self) -> None:
        redacted = subject.redact({"api_key": "secret", "nested": {"authorization_header": "Bearer abc"}})
        self.assertEqual(redacted["api_key"], "REDACTED")
        self.assertEqual(redacted["nested"]["authorization_header"], "REDACTED")


if __name__ == "__main__":
    unittest.main()
