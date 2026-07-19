#!/usr/bin/env python3
"""Tests for the fail-closed historical Attention preservation boundary."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
