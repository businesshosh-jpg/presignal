from __future__ import annotations

import unittest

from automation import build_presignal_v21_verified_outcomes_minute_r1 as verified


def obs(provider: str, ts: str, close: float, *, high: float | None = None, low: float | None = None):
    return verified.ProviderObservation(
        provider=provider,
        day=ts[:10],
        timestamp=ts,
        timestamp_raw=ts,
        open=close,
        high=close if high is None else high,
        low=close if low is None else low,
        close=close,
        bid=None,
        ask=None,
        midpoint=None,
        accepted_comparison_field="close",
        accepted_comparison_value=close,
        source_resolution="ONE_MINUTE",
        observation_type="OHLC",
        instrument="USD/JPY",
        raw_artifact_reference="raw.json",
        raw_artifact_sha256="sha256:test",
        retrieval_timestamp="2026-07-27T00:00:00Z",
        request_identity="REQ",
    )


class VerifiedOutcomesMinuteBuildTest(unittest.TestCase):
    def test_request_day_manifest_is_deduplicated_and_fixed(self):
        rows = verified.request_day_manifest()
        self.assertEqual(len(rows), 7)
        self.assertEqual([row["day"] for row in rows], list(verified.UTC_DAYS))
        self.assertEqual(rows[0]["requested_window_start"], "2024-05-08T00:00:00Z")
        self.assertEqual(rows[-1]["requested_window_end"], "2024-05-20T23:59:00Z")

    def test_direction_from_pips_uses_flat_threshold(self):
        self.assertEqual(verified.direction_from_pips(0.5), "flat")
        self.assertEqual(verified.direction_from_pips(1.0), "up")
        self.assertEqual(verified.direction_from_pips(-1.0), "down")

    def test_points_agree_requires_same_direction_and_frozen_tolerances(self):
        anchor = obs("tiingo", "2024-05-08T07:00:00Z", 155.00)
        left_target = obs("tiingo", "2024-05-08T07:15:00Z", 155.04)
        right_target = obs("eodhd", "2024-05-08T07:15:00Z", 155.03)
        far_target = obs("twelvedata", "2024-05-08T07:15:00Z", 155.10)
        left = verified.build_verified_point("tiingo", "15m", left_target.timestamp, anchor, left_target)
        right = verified.build_verified_point("eodhd", "15m", right_target.timestamp, anchor, right_target)
        far = verified.build_verified_point("twelvedata", "15m", far_target.timestamp, anchor, far_target)
        self.assertTrue(verified.points_agree(left, right))
        self.assertFalse(verified.points_agree(left, far))

    def test_clustered_subset_detects_compare_provider_consensus(self):
        anchor = obs("tiingo", "2024-05-08T07:00:00Z", 155.00)
        p1 = verified.build_verified_point("eodhd", "15m", "2024-05-08T07:15:00Z", anchor, obs("eodhd", "2024-05-08T07:15:00Z", 155.06))
        p2 = verified.build_verified_point("twelvedata", "15m", "2024-05-08T07:15:00Z", anchor, obs("twelvedata", "2024-05-08T07:15:00Z", 155.07))
        p3 = verified.build_verified_point("massive", "15m", "2024-05-08T07:15:00Z", anchor, obs("massive", "2024-05-08T07:15:00Z", 154.90))
        cluster = verified.clustered_subset([p1, p2, p3])
        self.assertEqual({row.provider for row in cluster}, {"eodhd", "twelvedata"})

    def test_classify_target_returns_multi_source_confirmed_with_primary_confirmation(self):
        anchor = obs("tiingo", "2024-05-08T07:00:00Z", 155.00)
        primary = verified.build_verified_point("tiingo", "15m", "2024-05-08T07:15:00Z", anchor, obs("tiingo", "2024-05-08T07:15:00Z", 155.05))
        compare = verified.build_verified_point("eodhd", "15m", "2024-05-08T07:15:00Z", anchor, obs("eodhd", "2024-05-08T07:15:00Z", 155.04))
        quality, accepted, _, agreeing, outliers = verified.classify_target(primary, [compare])
        self.assertEqual(quality, "MULTI_SOURCE_CONFIRMED")
        self.assertEqual(accepted.provider, "tiingo")
        self.assertEqual(set(agreeing), {"tiingo", "eodhd"})
        self.assertEqual(outliers, [])

    def test_classify_target_overrides_primary_with_compare_cluster(self):
        anchor = obs("tiingo", "2024-05-08T07:00:00Z", 155.00)
        primary = verified.build_verified_point("tiingo", "15m", "2024-05-08T07:15:00Z", anchor, obs("tiingo", "2024-05-08T07:15:00Z", 155.20))
        eod = verified.build_verified_point("eodhd", "15m", "2024-05-08T07:15:00Z", anchor, obs("eodhd", "2024-05-08T07:15:00Z", 155.05))
        twelve = verified.build_verified_point("twelvedata", "15m", "2024-05-08T07:15:00Z", anchor, obs("twelvedata", "2024-05-08T07:15:00Z", 155.04))
        quality, accepted, _, agreeing, outliers = verified.classify_target(primary, [eod, twelve])
        self.assertEqual(quality, "MULTI_SOURCE_CONSENSUS")
        self.assertIn(accepted.provider, {"eodhd", "twelvedata"})
        self.assertEqual(set(agreeing), {"eodhd", "twelvedata"})
        self.assertIn("tiingo", outliers)

    def test_classify_target_handles_single_source_only(self):
        anchor = obs("tiingo", "2024-05-08T07:00:00Z", 155.00)
        primary = verified.build_verified_point("tiingo", "15m", "2024-05-08T07:15:00Z", anchor, obs("tiingo", "2024-05-08T07:15:00Z", 155.05))
        quality, accepted, _, _, _ = verified.classify_target(primary, [])
        self.assertEqual(quality, "SINGLE_SOURCE_ONLY")
        self.assertEqual(accepted.provider, "tiingo")

    def test_classify_target_handles_source_disagreement(self):
        anchor = obs("tiingo", "2024-05-08T07:00:00Z", 155.00)
        primary = verified.build_verified_point("tiingo", "15m", "2024-05-08T07:15:00Z", anchor, obs("tiingo", "2024-05-08T07:15:00Z", 155.05))
        eod = verified.build_verified_point("eodhd", "15m", "2024-05-08T07:15:00Z", anchor, obs("eodhd", "2024-05-08T07:15:00Z", 154.80))
        twelve = verified.build_verified_point("twelvedata", "15m", "2024-05-08T07:15:00Z", anchor, obs("twelvedata", "2024-05-08T07:15:00Z", 155.30))
        quality, accepted, _, _, _ = verified.classify_target(primary, [eod, twelve])
        self.assertEqual(quality, "SOURCE_DISAGREEMENT")
        self.assertIsNone(accepted)

    def test_build_verified_outcome_marks_intraminute_ambiguity(self):
        outcome = {
            "episode_id": "EP1",
            "release_ts": "2024-05-08T07:00:00Z",
            "outcome_id": "OUT1",
            "outcome_fingerprint": "sha256:out1",
        }
        cache = {
            "first_minute": {"timestamp": "2024-05-08T07:01:00Z"},
            "second_minute": {"timestamp": "2024-05-08T07:02:00Z"},
        }
        anchor_obs = obs("tiingo", "2024-05-08T07:00:00Z", 155.00)
        first_obs = obs("tiingo", "2024-05-08T07:01:00Z", 155.02, high=155.03, low=154.98)
        second_obs = obs("tiingo", "2024-05-08T07:02:00Z", 155.04, high=155.04, low=155.01)
        accepted = {
            "anchor": verified.build_verified_point("tiingo", "anchor", anchor_obs.timestamp, anchor_obs, anchor_obs),
            "first_minute": verified.build_verified_point("tiingo", "first_minute", first_obs.timestamp, anchor_obs, first_obs),
            "second_minute": verified.build_verified_point("tiingo", "second_minute", second_obs.timestamp, anchor_obs, second_obs),
            "5m": None, "15m": None, "30m": None, "60m": None,
        }
        verification_rows = [{"target": target, "quality_status": "MULTI_SOURCE_CONFIRMED"} for target in verified.TARGET_ORDER]
        row = verified.build_verified_outcome_row(outcome, cache, accepted, verification_rows, "2026-07-27T00:00:00Z")
        self.assertFalse(row["intraminute_sequence_known"])
        self.assertEqual(row["ambiguity_reason"], "BOTH_SIDES_EXCURSION_ORDER_UNKNOWN")

    def test_pair_classification_preserves_correction_definition(self):
        self.assertEqual(verified.pair_classification(False, True), "correction")
        self.assertEqual(verified.pair_classification(True, False), "degradation")
        self.assertEqual(verified.pair_classification(True, True), "both correct")


if __name__ == "__main__":
    unittest.main()
