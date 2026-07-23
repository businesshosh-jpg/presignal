"""Focused selection binding tests; no provider or Google dependency."""
from __future__ import annotations

import unittest
from automation import presignal_v21_r6_episode_selection_v1 as selection


def candidate(identifier="EP_ONE", cutoff="2030-01-01T12:00:00Z"):
    return {"episode_id": identifier, "primary_event_id": "EV_PRIMARY", "member_event_ids": ["EV_PRIMARY", "EV_SECONDARY"], "release_ts": "2030-01-01T12:01:00Z", "forecast_cutoff_ts": cutoff, "market_session_context": "SAME_TIME_RELEASE_CLUSTER", "schema_version": "2.1.0", "eligibility": "ELIGIBLE_UPCOMING"}


class EpisodeSelectionTests(unittest.TestCase):
    def test_inventory_requires_exactly_five_unique_valid_candidates(self):
        items = [candidate("EP_" + str(index)) for index in range(5)]
        inventory_checksum = selection.checksum(items)
        selection.validate_inventory(candidates=items, episode_checksum=inventory_checksum, expected_episode_checksum=inventory_checksum, readback_valid=True)
        with self.assertRaisesRegex(selection.EpisodeSelectionError, "COUNT_NOT_FIVE"): selection.validate_inventory(candidates=items[:4], episode_checksum=inventory_checksum, expected_episode_checksum=inventory_checksum, readback_valid=True)
        changed = [dict(item) for item in items]; changed[0]["primary_event_id"] = "EV_CHANGED"
        with self.assertRaisesRegex(selection.EpisodeSelectionError, "CANDIDATE_INVENTORY_CHECKSUM_MISMATCH"):
            selection.validate_inventory(candidates=changed, episode_checksum=inventory_checksum, expected_episode_checksum=inventory_checksum, readback_valid=True)

    def test_passed_or_unknown_candidate_cannot_bind(self):
        items = [candidate("EP_" + str(index)) for index in range(5)]
        with self.assertRaisesRegex(selection.EpisodeSelectionError, "IDENTITY_MISMATCH"):
            selection.bind_explicit_selection(candidates=items, candidate_number=1, selected_episode_id="UNKNOWN", authorization_time_utc="2030-01-01T11:00:00Z", refresh_commit="c", refresh_evidence_checksum="e", candidate_inventory_checksum="i")
        with self.assertRaisesRegex(selection.EpisodeSelectionError, "CUTOFF_PASSED"):
            selection.bind_explicit_selection(candidates=items, candidate_number=1, selected_episode_id="EP_0", authorization_time_utc="2030-01-01T12:00:00Z", refresh_commit="c", refresh_evidence_checksum="e", candidate_inventory_checksum="i")

    def test_explicit_valid_selection_is_one_run_and_deterministic(self):
        items = [candidate("EP_" + str(index)) for index in range(5)]
        first = selection.bind_explicit_selection(candidates=items, candidate_number=1, selected_episode_id="EP_0", authorization_time_utc="2030-01-01T11:00:00Z", refresh_commit="c", refresh_evidence_checksum="e", candidate_inventory_checksum="i")
        second = selection.bind_explicit_selection(candidates=items, candidate_number=1, selected_episode_id="EP_0", authorization_time_utc="2030-01-01T11:30:00Z", refresh_commit="c", refresh_evidence_checksum="e", candidate_inventory_checksum="i")
        self.assertEqual(first["manifest"]["selection_method"], selection.SELECTION_METHOD)
        self.assertTrue(first["manifest"]["one_run_only"]); self.assertTrue(first["manifest"]["fallback_episode_prohibited"])
        self.assertEqual(first["fingerprint"], second["fingerprint"])
        self.assertEqual(first["manifest"]["gemini"]["attention_call_budget"], 1)
        self.assertEqual(first["manifest"]["gemini"]["retry_count"], 0)
