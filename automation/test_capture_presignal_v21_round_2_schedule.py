#!/usr/bin/env python3
"""Local-only tests for bounded Round 2 schedule refresh evidence."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automation import capture_presignal_v21_round_2_schedule as capture


class ScheduleRefreshTests(unittest.TestCase):
    def test_authorization_is_strictly_bounded(self):
        auth = capture.authorization()
        self.assertEqual(auth["ceilings"], {"fmp_api_requests": 1, "apps_script_invocations": 1, "event_sheet_upsert_operations": 1, "event_sheet_export_reads": 1, "retries": 0})
        self.assertEqual(auth["routes"]["apps_script_function"], "apiUpsertEventWindow")
        self.assertIn("provider dispatch", auth["not_authorized"])
        self.assertEqual(auth["attribution_control_version"], "presignal_r2_schedule_refresh_attribution_v1")

    def test_canonical_route_requires_attribution_fields(self):
        source = (capture.ROOT / "apps_script" / "automation_api.js").read_text()
        for field in ("operation_id", "authorization_id", "source_window_fingerprint", "pre_refresh_event_sheet_fingerprint", "post_refresh_event_sheet_fingerprint", "invocation_id"):
            self.assertIn(field, source)

    def test_freeze_and_resume_preserve_fingerprint(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "refresh"
            auth, evidence = capture.freeze(destination)
            self.assertEqual(evidence["apps_script_invocations"], 0)
            resumed, resumed_evidence = capture.freeze(destination)
            self.assertEqual(resumed["authorization_fingerprint"], auth["authorization_fingerprint"])
            self.assertEqual(resumed_evidence["remote_state"], "NOT_STARTED")

    def test_tampered_authorization_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "refresh"
            capture.freeze(destination)
            path = destination / "schedule_refresh_authorization.json"
            value = json.loads(path.read_text())
            value["ceilings"]["retries"] = 1
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(RuntimeError, "FINGERPRINT"):
                capture.freeze(destination)


if __name__ == "__main__":
    unittest.main()
