#!/usr/bin/env python3
"""Tests for deterministic, local-only v2.1 Episode construction."""
from __future__ import annotations

import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation import build_presignal_v21_episodes as builder
from automation import presignal_v21_event_path_contract_v1 as contract


def row(**overrides):
    value = {"event_id":"evt-1", "batch_id":"", "country":"US", "indicator_name":"CPI", "release_ts":"2026-01-02T13:30:00Z", "source_cal":"FMP", "source_provider":"FMP", "source_series_id":"", "type":"single"}
    value.update(overrides)
    return value


class EpisodeBuilderTests(unittest.TestCase):
    def test_single_is_pending_deterministic_episode(self):
        episodes, dispositions = builder.build_population([row()])
        self.assertEqual(len(episodes), 1); self.assertEqual(episodes[0]["episode_id"][:9], "EP_EVENT_")
        self.assertEqual(episodes[0]["member_event_count"], 1); self.assertEqual(episodes[0]["selection_status"], "PENDING")
        self.assertEqual(list(episodes[0]), contract.EPISODE_FIELDS)
        self.assertEqual(dispositions[0]["disposition"], "CONSUMED")

    def test_batch_order_and_duplicate_event_collision_preserve_rows(self):
        values = [row(event_id="evt-b", batch_id="B", type="member", indicator_name="B"), row(event_id="evt-a", batch_id="B", type="member", indicator_name="A")]
        episodes, dispositions = builder.build_population(values)
        self.assertEqual(len(episodes), 1); self.assertEqual(episodes[0]["episode_id"][:9], "EP_BATCH_")
        reversed_episodes, _ = builder.build_population(list(reversed(values)))
        self.assertEqual(episodes[0]["member_event_ids"], reversed_episodes[0]["member_event_ids"]); self.assertEqual(len(dispositions), 2)
        collision = [row(event_id="shared", release_ts="2026-01-02T13:30:00Z"), row(event_id="shared", release_ts="2026-02-02T13:30:00Z", indicator_name="Payrolls")]
        _, collision_dispositions = builder.build_population(collision)
        self.assertEqual(sum(item["disposition"] == "CONSUMED" for item in collision_dispositions), 2)

    def test_duplicate_locator_and_episode_id_collision_are_fail_closed(self):
        _, duplicate_dispositions = builder.build_population([row(), row()])
        self.assertEqual([item["disposition"] for item in duplicate_dispositions], ["ERROR", "ERROR"])
        values = [row(event_id="first"), row(event_id="second", release_ts="2026-01-03T13:30:00Z")]
        with patch.object(builder.contract, "episode_id_for", return_value="EP_EVENT_COLLISION"):
            with self.assertRaises(builder.EpisodeBuildError): builder.build_population(values)

    def test_invalid_rows_and_batches_are_explicit(self):
        values = [row(event_id=""), row(release_ts="bad"), row(type="member", batch_id=""), row(event_id="a", batch_id="B", type="member"), row(event_id="b", batch_id="B", type="member", release_ts="2026-01-02T13:31:00Z")]
        episodes, dispositions = builder.build_population(values)
        self.assertEqual(episodes, []); self.assertEqual(len(dispositions), len(values))
        self.assertEqual({item["disposition"] for item in dispositions}, {"EXCLUDED"})

    def test_headers_reconciliation_and_population_determinism(self):
        with self.assertRaises(builder.EpisodeBuildError): builder.validate_event_headers(["event_id"])
        values = [row(event_id="one"), row(event_id="two", release_ts="2026-01-03T13:30:00Z")]
        left = builder.build_population(values); right = builder.build_population(list(reversed(values)))
        self.assertEqual(builder.fingerprint(builder.stable_population(*left)), builder.fingerprint(builder.stable_population(*right)))

    def test_source_workbook_is_unchanged_and_outputs_reconcile(self):
        before = hashlib.sha256(builder.SOURCE.read_bytes()).hexdigest(); headers, values = builder.xlsx_event_rows(builder.SOURCE)
        episodes, dispositions = builder.build_population(values)
        with tempfile.TemporaryDirectory() as temporary:
            manifest = builder.write_outputs(episodes, dispositions, before, Path(temporary))
            self.assertEqual(manifest["event_rows"], len(values)); self.assertEqual(manifest["consumed_rows"], sum(item["member_event_count"] for item in episodes))
        self.assertEqual(before, hashlib.sha256(builder.SOURCE.read_bytes()).hexdigest())


if __name__ == "__main__": unittest.main()
