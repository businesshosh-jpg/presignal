"""Focused offline proof that the R6 refresh sidecar reuses v2.1 Episode rules."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from automation import presignal_v21_prospective_episode_refresh_v1 as refresh
from automation import run_presignal_v21_prospective_episode_refresh_v1 as runner


def row(event_id, name, release, kind="single", batch=""):
    return {"source_row": event_id, "event_id": event_id, "batch_id": batch, "type": kind, "country": "US", "indicator_name": name, "release_ts": release, "source_cal": "FMP", "source_provider": "", "source_series_id": ""}


class EpisodeRefreshTests(unittest.TestCase):
    def test_bounded_normalization_and_determinism(self):
        source = [row("EV_A", "A", "2030-01-01T12:00:00Z"), row("EV_OLD", "old", "2029-12-31T12:00:00Z")]
        canonical, rejected = refresh.canonical_events(source, window_start_utc="2030-01-01T00:00:00Z", window_end_utc="2030-01-02T00:00:00Z")
        again, _ = refresh.canonical_events(list(reversed(source)), window_start_utc="2030-01-01T00:00:00Z", window_end_utc="2030-01-02T00:00:00Z")
        self.assertEqual(canonical, again)
        self.assertEqual(len(canonical), 1); self.assertEqual(rejected[0]["classification"], "OUTSIDE_REFRESH_WINDOW")

    def test_same_time_batch_grouping_and_primary_are_frozen(self):
        events, _ = refresh.canonical_events([row("EV_B", "B", "2030-01-01T12:00:00Z", "member", "BATCH"), row("EV_A", "A", "2030-01-01T12:00:00Z", "member", "BATCH")], window_start_utc="2030-01-01T00:00:00Z", window_end_utc="2030-01-02T00:00:00Z")
        built, _ = refresh.construct_episodes(events, as_of_utc="2030-01-01T11:00:00Z")
        self.assertEqual(len(built), 1); self.assertTrue(built[0]["same_time_cluster_flag"])
        self.assertEqual(built[0]["member_event_count"], 2); self.assertEqual(built[0]["forecast_cutoff_ts"], built[0]["release_ts"])
        self.assertEqual(built[0]["secondary_event_identities"], [next(item for item in built[0]["member_event_ids"] if item != built[0]["primary_event_id"])])

    def test_candidate_selection_never_invents_a_tie_break(self):
        episodes = [{"eligibility": "ELIGIBLE_UPCOMING", "episode_id": "EP_A"}, {"eligibility": "ELIGIBLE_UPCOMING", "episode_id": "EP_B"}]
        self.assertEqual(refresh.candidate_decision(episodes)["decision"], "PROSPECTIVE_EPISODE_REFRESH_COMPLETE_SELECTION_AMBIGUOUS")
        self.assertEqual(refresh.candidate_decision(episodes[:1])["decision"], "PROSPECTIVE_EPISODES_REFRESHED_NATIVE_ATTENTION_READY")

    def test_conflicting_duplicate_fails_closed(self):
        second = row("EV_A", "A", "2030-01-01T12:00:00Z"); second["source_row"] = "EV_A_SECOND"
        with self.assertRaisesRegex(refresh.EpisodeRefreshError, "DUPLICATE_CONFLICT"):
            refresh.canonical_events([row("EV_A", "A", "2030-01-01T12:00:00Z"), second], window_start_utc="2030-01-01T00:00:00Z", window_end_utc="2030-01-02T00:00:00Z")

    def test_live_refresh_report_keeps_google_scope_and_attention_budget_bounded(self):
        capture = json.loads((Path(__file__).resolve().parents[1] / "outputs/presignal_v21_designed_drift_r6_episode_refresh/R6-EPISODE-REFRESH-20260723-v1/captured_event_readback.json").read_text())
        value = runner.reports(capture)
        self.assertEqual(value["google_event_write_report.json"]["object"], "Event")
        self.assertEqual(value["google_event_write_report.json"]["write_conflicts"], 0)
        self.assertEqual(value["external_access_audit.json"]["gemini_attention_calls"], 0)
        self.assertEqual(value["external_access_audit.json"]["outcome_operations"], 0)
        self.assertEqual(value["final_episode_refresh_decision.json"]["attention_call_budget_remaining"], 1)
