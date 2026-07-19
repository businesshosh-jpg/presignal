#!/usr/bin/env python3
"""Tests for the narrow, audited v2.1 Event-lineage repair."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from automation import build_presignal_v21_episodes as builder
from automation import repair_presignal_v21_event_lineage as repair


def records(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines()]


class EventLineageRepairTests(unittest.TestCase):
    def build_preview(self):
        temporary = tempfile.TemporaryDirectory()
        directory = Path(temporary.name)
        manifest = repair.repair(destination=directory)
        return temporary, directory, manifest

    def test_legacy_batch_generator_matches_authoritative_v2_rule(self):
        self.assertEqual(repair.legacy_batch_id("US", "2024-05-01T07:30:00Z"), "7d66-5e2e-1fbe-c216")
        self.assertEqual(repair.legacy_uuid_from_string("event|US|2024-05-01T07:30Z|Crude Oil Imports"), "1e91-8d5d-6af5-b759")

    def test_audited_batch_partitions_and_id_rekeys_are_deterministic(self):
        temporary, directory, manifest = self.build_preview()
        try:
            batches = json.loads((directory / "batch_repartition_map.json").read_text())
            rekeys = json.loads((directory / "event_id_rekey_map.json").read_text())
            self.assertEqual(len(batches), 12)
            self.assertEqual(sum(item["original_batch_id"] != item["repaired_batch_id"] for item in batches), 6)
            self.assertEqual(len(rekeys), 4)
            self.assertEqual(len({item["new_event_id"] for item in rekeys}), 4)
            self.assertEqual(manifest["new_batch_ids_created"], 6)
            self.assertTrue(all(item["repaired_type"] == "member" for item in batches))
        finally:
            temporary.cleanup()

    def test_collateral_members_remain_active_and_invalid_duplicate_remains_excluded(self):
        temporary, directory, manifest = self.build_preview()
        try:
            duplicate_map = json.loads((directory / "duplicate_canonicalization_map.json").read_text())
            ledger = records(directory / "event_lineage_repair_ledger.jsonl")
            _, rows = builder.xlsx_event_rows(directory / "presignal_main_repaired_preview.xlsx")
            episodes, dispositions = builder.build_population(rows)
            self.assertEqual(len(duplicate_map), 17)
            self.assertTrue(all(item["action"] == "REMAIN_ACTIVE_UNCHANGED" for item in duplicate_map))
            self.assertEqual(Counter(item["disposition"] for item in dispositions), {"CONSUMED": 4314, "EXCLUDED": 1})
            self.assertEqual(Counter(item["reason"] for item in dispositions if item["disposition"] != "CONSUMED"), {"INVALID_RELEASE_TS": 1})
            invalid = next(item for item in ledger if item["repair_class"] == "INVALID_CORRUPT_DUPLICATE_UNCHANGED")
            self.assertEqual(invalid["episode_eligibility_after"], "EXCLUDED")
            self.assertEqual(len(episodes), 1682)
            self.assertEqual(manifest["episode_population_comparison"]["new"]["error_rows"], 0)
        finally:
            temporary.cleanup()

    def test_scope_audit_and_idempotency_are_strict(self):
        temporary, directory, manifest = self.build_preview()
        try:
            changes = json.loads((directory / "workbook_change_audit.json").read_text())
            self.assertEqual(changes["non_event_sheets_changed"], 0)
            self.assertEqual(changes["unaudited_event_rows_changed"], 0)
            self.assertEqual(changes["unaudited_event_ids_changed"], 0)
            self.assertEqual(changes["unaudited_batch_ids_changed"], 0)
            self.assertEqual(changes["event_columns_changed"], ["batch_id", "event_id"])
            self.assertEqual(manifest["determinism"], {"repeated_preview_bytes": "PASS", "input_order_shuffle": "PASS", "repair_idempotency": "PASS"})
        finally:
            temporary.cleanup()

    def test_unexpected_source_fingerprint_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "changed.xlsx"
            source.write_bytes(b"not the audited workbook")
            with self.assertRaisesRegex(repair.RepairError, "SOURCE_WORKBOOK_FINGERPRINT_MISMATCH"):
                repair.repair(source=source, destination=Path(temporary) / "output")

    def test_promoted_copy_is_only_allowed_after_valid_preview(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "presignal_main.xlsx"
            shutil.copyfile(repair.SOURCE, source)
            output = Path(temporary) / "output"
            with patch.object(repair.builder, "write_outputs"):
                manifest = repair.repair(source=source, destination=output, promote=True)
            self.assertEqual(repair.sha(source), manifest["repaired_workbook_sha256"])
            self.assertEqual(repair.sha(source), repair.sha(output / "presignal_main_repaired_preview.xlsx"))


if __name__ == "__main__":
    unittest.main()
