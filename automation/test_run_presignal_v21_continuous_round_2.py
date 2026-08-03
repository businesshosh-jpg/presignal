#!/usr/bin/env python3
"""Focused local tests for the Round 2 continuous controller."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from automation import run_presignal_v21_continuous_round_2 as controller


NOW = datetime(2026, 8, 3, tzinfo=timezone.utc)


def row(event_id: str, release: str, *, marker: str = ""):
    return {"event_id": event_id, "batch_id": "", "country": "US", "indicator_name": "Test " + event_id + marker, "type": "single", "release_ts": release, "source_cal": "FMP", "source_provider": "FMP", "source_series_id": event_id, "release_status": "scheduled"}


def snapshot(rows):
    return {"snapshot_status": "AUTHORITATIVE_EVENT_SHEET_EXPORT", "source_authority": controller.SOURCE_AUTHORITY, "acquisition_lineage": {"canonical_steps": ["apiUpsertEventWindow_", "runFmpRangeToEvent_", "applyBatchingForKeys_", "event_sheet_export"]}, "event_rows": rows}


def prepared(cutoff: str):
    return {"forecast_cutoff_ts": cutoff, "prompt_fingerprints": {"A": "a", "E": "e"}, "pack_inputs": {"A": {"artifact_id": "PACK_A", "fingerprint": "sha256:a"}, "E": {"artifact_id": "PACK_E", "fingerprint": "sha256:e"}}}


class ContinuousRound2Tests(unittest.TestCase):
    def test_source_contract_is_canonical(self):
        contract = controller.source_contract()
        self.assertEqual(contract["source_authority"], controller.SOURCE_AUTHORITY)
        self.assertIn("apiUpsertEventWindow_", contract["refresh_entry_point"])

    def test_snapshot_rejects_historical_and_synthetic_rows(self):
        with self.assertRaisesRegex(controller.AdmissionError, "HISTORICAL"):
            controller.validate_snapshot(snapshot([row("E1", "2026-08-02T00:00:00Z")]), NOW)
        with self.assertRaisesRegex(controller.AdmissionError, "SYNTHETIC"):
            controller.validate_snapshot(snapshot([row("E1", "2026-08-04T00:00:00Z", marker=" synthetic")]), NOW)

    def test_snapshot_and_admission_are_deterministic(self):
        episodes = controller.validate_snapshot(snapshot([row("E2", "2026-08-05T00:00:00Z"), row("E1", "2026-08-04T00:00:00Z")]), NOW)
        prepared_rows = {episode["episode_id"]: prepared("2026-08-03T12:00:00Z") for episode in episodes}
        selected = controller.select_rolling_slice(episodes, prepared_rows, NOW)
        self.assertEqual([item["episode"]["release_ts"] for item in selected], ["2026-08-04T00:00:00Z", "2026-08-05T00:00:00Z"])
        calls = controller.forecast_inventory("R2S1", selected)
        self.assertEqual(len(calls), 12)
        self.assertEqual(len({call["call_id"] for call in calls}), 12)
        self.assertEqual({call["provider"] for call in calls}, {"Anthropic", "Gemini", "OpenAI"})

    def test_cutoff_and_maximum_are_enforced(self):
        episodes = controller.validate_snapshot(snapshot([row("E1", "2026-08-04T00:00:00Z")]), NOW)
        bad = {episodes[0]["episode_id"]: prepared("2026-08-04T00:00:00Z")}
        with self.assertRaisesRegex(controller.AdmissionError, "CUTOFF"):
            controller.select_rolling_slice(episodes, bad, NOW)
        with self.assertRaisesRegex(controller.AdmissionError, "SLICE_LIMIT"):
            controller.select_rolling_slice(episodes, {}, NOW, 49)

    def test_revision_and_non_scheduled_events_fail_closed(self):
        cancelled = row("E1", "2026-08-04T00:00:00Z")
        cancelled["release_status"] = "cancelled"
        with self.assertRaisesRegex(controller.AdmissionError, "NON_SCHEDULED"):
            controller.validate_snapshot(snapshot([cancelled]), NOW)

    def test_inventory_requires_unique_exact_call_identity(self):
        episodes = controller.validate_snapshot(snapshot([row("E1", "2026-08-04T00:00:00Z")]), NOW)
        prepared_rows = {episodes[0]["episode_id"]: prepared("2026-08-03T12:00:00Z")}
        selected = controller.select_rolling_slice(episodes, prepared_rows, NOW)
        with self.assertRaisesRegex(controller.AdmissionError, "DUPLICATE"):
            controller.forecast_inventory("R2S1", selected + selected)

    def test_call_freeze_requires_complete_immutable_pack_inputs(self):
        episodes = controller.validate_snapshot(snapshot([row("E1", "2026-08-04T00:00:00Z")]), NOW)
        incomplete = {episodes[0]["episode_id"]: {"forecast_cutoff_ts": "2026-08-03T12:00:00Z", "prompt_fingerprints": {"A": "a", "E": "e"}}}
        with self.assertRaisesRegex(controller.AdmissionError, "PACK_INPUTS_COMPLETE"):
            controller.select_rolling_slice(episodes, incomplete, NOW)

    def test_freeze_is_zero_access_and_no_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            result = controller.freeze(Path(directory) / "evidence")
            self.assertEqual(result["external_access"], 0)
            self.assertEqual(result["provider_calls"], 0)
            self.assertEqual(result["roster_decision"], "ROUND_2_DISPATCH_AUTHORIZATION_INPUTS_NOT_READY")


if __name__ == "__main__":
    unittest.main()
