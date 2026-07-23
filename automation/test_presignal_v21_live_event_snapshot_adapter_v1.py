from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automation import presignal_v21_live_event_snapshot_adapter_v1 as adapter


def row(**overrides):
    value = {"event_id": "EV_A", "batch_id": "", "type": "single", "country": "US",
             "indicator_name": "Test", "release_ts": "2030-01-01T12:00:00Z", "source_cal": "FMP",
             "source_provider": "FMP", "source_series_id": "SERIES", "_row_number": "2"}
    value.update(overrides)
    return value


class LiveEventSnapshotAdapterTests(unittest.TestCase):
    def snapshot(self, rows):
        directory = tempfile.TemporaryDirectory(); self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "event_source_snapshot.json"
        return adapter.build_event_source_snapshot(event_rows=rows, source_identity={"workbook_id": "W", "sheet_name": "Event"}, read_timestamp="2030-01-01T11:00:00Z", output_path=path), path

    def test_preserves_constructor_fields_and_builds_unchanged_population(self):
        snapshot, _ = self.snapshot([row(), row(event_id="EV_B", batch_id="B", type="member", _row_number="3"), row(event_id="EV_C", batch_id="B", type="member", _row_number="4")])
        self.assertEqual(snapshot["included_row_count"], 3)
        rows = adapter.constructor_rows(snapshot)
        self.assertEqual(rows[0]["event_id"], "EV_A")
        self.assertEqual(rows[1]["batch_id"], "B")
        episodes, dispositions = adapter.build_population_from_snapshot(snapshot)
        self.assertEqual(len(episodes), 2)
        self.assertEqual(len(dispositions), 3)

    def test_invalid_rows_are_excluded_and_snapshot_is_immutable(self):
        snapshot, path = self.snapshot([row(), row(event_id="", _row_number="3")])
        self.assertEqual(snapshot["excluded_row_count"], 1)
        self.assertEqual(snapshot["rows"][0]["batch_id"], "")
        with self.assertRaisesRegex(adapter.LiveEventSnapshotError, "DUPLICATE_EVENT_SOURCE_SNAPSHOT"):
            adapter.build_event_source_snapshot(event_rows=[row()], source_identity={}, read_timestamp="2030-01-01T11:00:00Z", output_path=path)
        self.assertIn("snapshot_checksum", json.loads(path.read_text()))

    def test_member_and_single_batch_contract_is_preserved(self):
        snapshot, _ = self.snapshot([row(), row(event_id="EV_B", type="member", batch_id="")])
        self.assertEqual(snapshot["included_row_count"], 1)
        self.assertEqual(snapshot["excluded"][0]["reason"], "MEMBER_BATCH_ID_REQUIRED")


if __name__ == "__main__":
    unittest.main()
