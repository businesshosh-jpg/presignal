from __future__ import annotations

import unittest
from datetime import datetime, timezone

from automation import freeze_presignal_v21_round_2_t_minus_15 as t15


class TMinus15Tests(unittest.TestCase):
    NOW = datetime(2026, 8, 3, 15, 30, 0, tzinfo=timezone.utc)

    def test_exact_subtraction_and_boundaries(self):
        self.assertEqual(t15.cutoff_for("2026-08-03T15:45:00Z"), "2026-08-03T15:30:00Z")
        self.assertEqual(t15.cutoff_for("2026-08-03T15:30:01+00:00"), "2026-08-03T15:15:01Z")
        self.assertTrue(t15.dispatch_allowed(self.NOW, "2026-08-03T15:30:01Z"))
        self.assertFalse(t15.dispatch_allowed(self.NOW, "2026-08-03T15:30:00Z"))
        self.assertFalse(t15.dispatch_allowed(self.NOW, "2026-08-03T15:29:59Z"))

    def test_timezone_normalization_and_ambiguity(self):
        self.assertEqual(t15.cutoff_for("2026-08-04T00:45:00+09:00"), "2026-08-03T15:30:00Z")
        with self.assertRaisesRegex(t15.TMinus15Error, "AMBIGUOUS_TIMEZONE"):
            t15.parse_utc("2026-08-04T00:45:00")

    def test_release_revision_and_status_stops(self):
        base = {"event_id": "E", "country": "US", "indicator_name": "X", "type": "single", "source_cal": "FMP", "release_status": "scheduled", "release_ts": "2026-08-03T18:00:00Z"}
        snap = datetime(2026, 8, 3, 15, 0, tzinfo=timezone.utc)
        self.assertEqual(t15.classify_event(base, now_utc=self.NOW, snapshot_export_utc=snap), "ELIGIBLE_PROSPECTIVE")
        revised = {**base, "release_status": "revised"}
        self.assertEqual(t15.classify_event(revised, now_utc=self.NOW, snapshot_export_utc=snap), "AUTHORITY_UNRESOLVED")
        cancelled = {**base, "release_status": "cancelled"}
        self.assertEqual(t15.classify_event(cancelled, now_utc=self.NOW, snapshot_export_utc=snap), "CANCELLED_OR_SUPERSEDED")

    def test_snapshot_population_and_authorization_are_exact_and_call_free(self):
        evidence = t15.freeze(output_dir=t15.ROOT / "outputs" / "_test_t15_evidence", now_utc=self.NOW)
        try:
            self.assertEqual(evidence["first_slice"]["episode_count"], 31)
            self.assertEqual(evidence["first_slice"]["forecast_call_count"], 186)
            self.assertEqual(evidence["first_slice"]["pack_a_count"], 93)
            self.assertEqual(evidence["first_slice"]["pack_e_count"], 93)
            self.assertEqual(evidence["dispatch_authorization"]["maximum_calls_per_provider"], {"Anthropic": 62, "Gemini": 62, "OpenAI": 62})
            self.assertEqual(evidence["activity"]["provider_calls"], 0)
        finally:
            import shutil
            shutil.rmtree(t15.ROOT / "outputs" / "_test_t15_evidence")


if __name__ == "__main__":
    unittest.main()
