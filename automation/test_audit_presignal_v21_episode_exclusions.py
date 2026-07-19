#!/usr/bin/env python3
"""Tests for the read-only v2.1 Episode exclusion integrity audit."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from automation import audit_presignal_v21_episode_exclusions as audit
from automation import build_presignal_v21_episodes as builder


def records(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines()]


class EpisodeExclusionAuditTests(unittest.TestCase):
    def run_audit(self, directory: Path):
        return audit.audit(destination=directory)

    def test_row_count_and_full_exclusion_accounting(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            manifest = self.run_audit(directory)
            counts = manifest["row_count_reconciliation"]
            ledger = records(directory / "exclusion_decision_ledger.jsonl")

        self.assertEqual(counts["migration_count"], 4316)
        self.assertEqual(counts["builder_count"], 4315)
        self.assertEqual(counts["canonical_physical_data_row_count"], 4315)
        self.assertEqual(counts["affected_row_locator_or_excel_row"], "Excel header row 1")
        self.assertEqual(len(ledger), 70)
        self.assertEqual(Counter(item["original_exclusion_reason"] for item in ledger), {
            "BATCH_RELEASE_MINUTE_CONFLICT": 48,
            "DUPLICATE_MEMBER_EVENT_ID": 21,
            "INVALID_RELEASE_TS": 1,
        })

    def test_batch_and_duplicate_classifications(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.run_audit(directory)
            batches = records(directory / "batch_release_minute_conflicts.jsonl")
            duplicates = records(directory / "duplicate_member_event_id_cases.jsonl")

        self.assertEqual(len(batches), 48)
        self.assertEqual(len({item["batch_id"] for item in batches}), 6)
        self.assertEqual({item["audit_classification"] for item in batches}, {"STALE_BATCH_ID"})
        self.assertTrue(all(len(item["other_batch_member_release_minutes"]) == 2 for item in batches))
        self.assertEqual(len(duplicates), 21)
        self.assertEqual(Counter(item["audit_classification"] for item in duplicates), {
            "DUPLICATE_EVENT_INSIDE_ONE_BATCH": 17,
            "LEGITIMATE_DISTINCT_EVENT_WITH_COLLIDING_EVENT_ID": 4,
        })
        self.assertTrue(all(item["source_row_number"] > 1 for item in duplicates))

    def test_invalid_timestamp_is_exact_duplicate_that_stays_excluded(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            manifest = self.run_audit(directory)
            invalid = json.loads((directory / "invalid_release_ts_case.json").read_text())
            ledger = records(directory / "exclusion_decision_ledger.jsonl")

        row = next(item for item in ledger if item["original_exclusion_reason"] == "INVALID_RELEASE_TS")
        self.assertEqual(invalid["source_row_number"], 4316)
        self.assertEqual(invalid["raw_release_ts"], "member")
        self.assertEqual(invalid["matching_authoritative_row_numbers"], [2460])
        self.assertEqual(row["audit_classification"], "EXACT_DUPLICATE_OBSERVATION")
        self.assertTrue(row["scientific_exclusion_justified"])
        self.assertEqual(row["recommended_disposition"], "KEEP_EXCLUDED")
        self.assertEqual(manifest["recommended_dispositions"], {
            "ELIGIBLE_AFTER_TARGETED_REPAIR": 69,
            "KEEP_EXCLUDED": 1,
        })

    def test_source_lineage_reconstructs_and_audit_is_read_only(self):
        source_before = hashlib.sha256(audit.SOURCE.read_bytes()).hexdigest()
        episode_before = hashlib.sha256((audit.EPISODE_OUTPUT / "episode_rows.jsonl").read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            manifest = self.run_audit(directory)
            ledger = records(directory / "exclusion_decision_ledger.jsonl")

        workbook = audit.numbered_event_rows(audit.SOURCE)
        locators = {}
        for number, raw in workbook["rows"]:
            try:
                record = builder.source_record(raw)
                locators[builder.contract.event_record_locator(record)] = number
            except builder.EpisodeBuildError:
                pass
        consumed = {item["event_row_locator"] for item in records(audit.EPISODE_OUTPUT / "event_row_dispositions.jsonl") if item["disposition"] == "CONSUMED"}

        self.assertEqual(source_before, hashlib.sha256(audit.SOURCE.read_bytes()).hexdigest())
        self.assertEqual(episode_before, hashlib.sha256((audit.EPISODE_OUTPUT / "episode_rows.jsonl").read_bytes()).hexdigest())
        self.assertEqual(manifest["source_workbook_sha256_before"], manifest["source_workbook_sha256_after"])
        for item in ledger:
            if item["event_row_locator"]:
                self.assertIn(item["event_row_locator"], locators)
                self.assertNotIn(item["event_row_locator"], consumed)
        self.assertEqual(sum(item["event_row_locator"] is None for item in ledger), 1)

    def test_rerun_is_deterministic(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            left = Path(first)
            right = Path(second)
            self.assertEqual(self.run_audit(left), self.run_audit(right))
            for name in (
                "row_count_reconciliation.json",
                "batch_release_minute_conflicts.jsonl",
                "duplicate_member_event_id_cases.jsonl",
                "invalid_release_ts_case.json",
                "exclusion_decision_ledger.jsonl",
                "audit_manifest.json",
                "audit_report.md",
            ):
                self.assertEqual((left / name).read_bytes(), (right / name).read_bytes())


if __name__ == "__main__":
    unittest.main()
