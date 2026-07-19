#!/usr/bin/env python3
"""Tests for the fail-closed historical Attention preservation boundary."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation import export_authoritative_v2_attention_map_v1 as attention


def record(**changes):
    base = {
        "source_object": "session_attention_map",
        "session_id": "US|2024-05-01|WINDOW",
        "provider": "OpenAI",
        "model": "gpt-4o-mini",
        "event_id": "EVT-1",
        "attention_label": "PRIMARY_DRIVER",
        "attention_run_id": "session_attention_v0_20240501T070000Z",
        "forecast_cutoff_ts": "2024-05-01T07:20:00Z",
        "raw_output": "{\\\"object\\\":\\\"session_attention_map\\\"}",
        "attention_rank": 1,
        "confidence": 0.8,
    }
    base.update(changes)
    return base


class AuthoritativeAttentionExportTests(unittest.TestCase):
    def test_dedicated_source_is_accepted_and_attention_like_metadata_is_rejected(self):
        attention.validate_attention_record(record())
        for source_object in ("attention_factor_v1", "prediction_rationale", "batch_anchor_metadata", "information_request", "outcome_importance"):
            with self.assertRaises(attention.PreservationError):
                attention.validate_attention_record(record(source_object=source_object))

    def test_lineage_schema_and_identity_are_fail_closed(self):
        with self.assertRaisesRegex(attention.PreservationError, "MISSING_REQUIRED_LINEAGE"):
            attention.validate_attention_record(record(model=""))
        with self.assertRaisesRegex(attention.PreservationError, "UNKNOWN_ATTENTION_LABEL"):
            attention.validate_attention_record(record(attention_label="TERTIARY_DRIVER"))
        with self.assertRaisesRegex(attention.PreservationError, "INVALID_ATTENTION_RANK"):
            attention.validate_attention_record(record(attention_rank=0))
        with self.assertRaisesRegex(attention.PreservationError, "INVALID_ATTENTION_CONFIDENCE"):
            attention.validate_attention_record(record(confidence=1.2))
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(attention.PreservationError, "DUPLICATE_ATTENTION_IDENTITY"):
                attention.export_records([record(), record()], Path(temp))

    def test_export_is_stable_and_preserves_provider_disagreement(self):
        records = [record(provider="Gemini", model="gemini", attention_label="WATCHLIST"), record(provider="OpenAI", model="gpt", attention_label="PRIMARY_DRIVER")]
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_manifest = attention.export_records(records, Path(first))
            second_manifest = attention.export_records(list(reversed(records)), Path(second))
            self.assertEqual(first_manifest["export_fingerprint"], second_manifest["export_fingerprint"])
            self.assertEqual((Path(first) / "authoritative_attention_map.jsonl").read_text(), (Path(second) / "authoritative_attention_map.jsonl").read_text())
            labels = [json.loads(line)["attention_label"] for line in (Path(first) / "authoritative_attention_map.jsonl").read_text().splitlines()]
            self.assertEqual(set(labels), {"WATCHLIST", "PRIMARY_DRIVER"})

    def test_actual_inventory_is_deterministic_and_has_no_authoritative_rows(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_decision = attention.run_inventory(Path(first))
            second_decision = attention.run_inventory(Path(second))
            self.assertEqual(first_decision, second_decision)
            self.assertEqual(first_decision["decision"], "V2_1_FROZEN_ATTENTION_LINEAGE_NOT_RECOVERABLE")
            self.assertFalse((Path(first) / "authoritative_attention_map.jsonl").exists())
            self.assertEqual((Path(first) / "attention_source_inventory.json").read_text(), (Path(second) / "attention_source_inventory.json").read_text())
            self.assertEqual(first_decision["external_calls"]["provider"], 0)

    def test_google_rows_are_normalized_and_source_identity_is_fixed(self):
        headers = sorted(attention.GOOGLE_REQUIRED_HEADERS)
        row = {header: "" for header in headers}
        row.update({
            "history_capture_ts": "2026-07-02T01:00:00Z", "replay_id": "replay-1",
            "source_sheet": "Session_Attention_Map", "source_row_hash": "hash-1", "capture_phase": "Phase 2",
            "capture_status": "CAPTURED", "generated_ts": "2026-07-02T01:00:00Z",
            "attention_run_id": "run-1", "session_id": "S-1", "provider": "OpenAI", "model": "gpt",
            "event_id": "E-1", "attention_label": "PRIMARY_DRIVER", "raw_output": "{}", "status": "parsed",
            "error_message": "", "source_session_sheet": "Market_Sessions", "source_member_sheet": "Market_Session_Members",
        })
        values = [headers, [row[header] for header in headers], [""] * len(headers)]
        actual_headers, normalized = attention.normalize_google_values(values)
        self.assertEqual(actual_headers, headers)
        self.assertEqual(normalized, [row])
        self.assertEqual(attention.google_content_fingerprint(headers, normalized), attention.google_content_fingerprint(headers, list(reversed(normalized))))
        self.assertEqual(attention.GOOGLE_SPREADSHEET_ID, "1jxcZotbzJKcAzrK0VhxetYX6hp5DPXCCIA0J6B6RUy0")
        self.assertEqual(attention.REQUESTED_GOOGLE_WORKSHEET_GID, 1865169058)
        self.assertEqual(attention.GOOGLE_WORKSHEET_GID, 1528972154)

    def test_google_statuses_raw_lineage_and_duplicates_are_fail_closed(self):
        state = {
            "sessions": {"S-1": {"forecast_cutoff": "2024-05-01T07:20:00Z"}},
            "members": {"S-1": {"E-1"}},
            "provider_models": {("OpenAI", "gpt")},
        }
        raw = json.dumps({"object": "session_attention_map", "session_id": "S-1", "attention_items": [{"event_id": "E-1", "attention_label": "SECONDARY_DRIVER"}]})
        row = {
            "source_sheet": "Session_Attention_Map", "capture_status": "CAPTURED", "status": "parsed",
            "source_row_hash": "hash-1", "session_id": "S-1", "event_id": "E-1", "provider": "OpenAI",
            "model": "gpt", "release_ts": "2024-05-01T07:30:00Z", "attention_label": "SECONDARY_DRIVER",
            "raw_output": raw, "attention_run_id": "run-1",
        }
        validated = attention.validate_google_history_row(row, state)
        self.assertEqual(validated["step5_lineage_status"], "VALID_FOR_STEP5")
        self.assertEqual(validated["forecast_cutoff_ts"], "2024-05-01T07:20:00Z")
        error = attention.validate_google_history_row({**row, "status": "provider_contract_error", "raw_output": "broken", "attention_label": "NO_SIGNAL"}, state)
        self.assertEqual(error["step5_lineage_status"], "PRESERVED_NOT_SELECTABLE")
        with self.assertRaisesRegex(attention.PreservationError, "CONFLICTING_ATTENTION_IDENTITY"):
            attention.deduplicate_google_records([validated, {**validated, "attention_reason": "conflict"}])

    def test_google_retrieval_is_read_only(self):
        class GetCall:
            def execute(self):
                return {"spreadsheetId": attention.GOOGLE_SPREADSHEET_ID, "sheets": [{"properties": {"title": attention.GOOGLE_WORKSHEET_NAME, "sheetId": attention.GOOGLE_WORKSHEET_GID}}]}
        class Sheets:
            def get(self, **_kwargs):
                return GetCall()
        class Service:
            def spreadsheets(self):
                return Sheets()
        headers = sorted(attention.GOOGLE_REQUIRED_HEADERS)
        row = {header: "x" for header in headers}
        with patch.object(attention, "get_sheet_values", return_value=[headers, [row[header] for header in headers]]):
            actual_headers, actual_rows, metadata = attention.retrieve_google_history(Service())
        self.assertEqual(actual_headers, headers)
        self.assertEqual(len(actual_rows), 1)
        self.assertEqual(metadata["spreadsheet_id"], attention.GOOGLE_SPREADSHEET_ID)
        self.assertNotIn("batch_update_values", Path(attention.__file__).read_text())


if __name__ == "__main__":
    unittest.main()
