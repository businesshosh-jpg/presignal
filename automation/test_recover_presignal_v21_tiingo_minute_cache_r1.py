from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from automation import recover_presignal_v21_tiingo_minute_cache_r1 as recovery


def outcome(episode_id: str = "EP_FIXTURE", release_ts: str = "2024-05-08T07:00:00Z") -> dict:
    return {
        "episode_id": episode_id,
        "release_ts": release_ts,
        "anchor_price_ts": release_ts,
        "anchor_price": 155.1,
        "price_5m": 155.2,
        "price_15m": 155.3,
        "price_30m": 155.4,
        "price_60m": 155.5,
        "source_lineage": {
            "selected_observations": {
                "5": {"timestamp": "2024-05-08T07:05:00Z"},
                "15": {"timestamp": "2024-05-08T07:15:00Z"},
                "30": {"timestamp": "2024-05-08T07:30:00Z"},
                "60": {"timestamp": "2024-05-08T08:00:00Z"},
            }
        },
    }


def observation(ts: str, close: float) -> dict:
    return {
        "provider": "tiingo",
        "instrument": "USD/JPY",
        "timestamp": ts,
        "source_resolution": "ONE_MINUTE",
        "observation_type": "OHLC",
        "open": close,
        "high": close,
        "low": close,
        "close": close,
        "bid": None,
        "ask": None,
        "midpoint": None,
        "accepted_raw_price_field": "close",
        "accepted_raw_price": close,
        "provider_returned_timestamp_raw": ts.replace("Z", ".000Z"),
        "source_observation_id": None,
        "request_identity": "REQ_1",
        "raw_artifact_reference": "raw.json",
        "raw_artifact_sha256": "abc",
        "retrieval_timestamp": "2026-07-27T00:00:00Z",
        "day": ts[:10],
        "position": 0,
    }


class RecoveryTests(unittest.TestCase):
    def test_day_request_id_matches_original_builder_shape(self) -> None:
        self.assertEqual(recovery.day_request_id("2024-05-08"), "MD_DAY_21eb9e211dd05fe44de7")

    def test_request_rows_group_by_utc_day(self) -> None:
        rows = recovery.request_rows_from_outcomes([
            outcome("EP_A", "2024-05-08T07:00:00Z"),
            outcome("EP_B", "2024-05-08T11:00:00Z"),
            outcome("EP_C", "2024-05-09T12:30:00Z"),
        ])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["day"], "2024-05-08")
        self.assertEqual(rows[0]["request_id"], "MD_DAY_21eb9e211dd05fe44de7")

    def test_normalize_response_preserves_ohlc_and_deduplicates_timestamp(self) -> None:
        day = {
            "day": "2024-05-08",
            "request_id": "REQ_1",
            "requested_window_start": "2024-05-08T00:00:00Z",
            "requested_window_end": "2024-05-08T23:59:00Z",
        }
        result = {
            "result": {
                "instrument": "USD/JPY",
                "selected_provider": "tiingo",
                "status": "SUCCESS",
                "returned_observation_count": 2,
                "provider_attempts": [{"provider": "tiingo", "status": "SUCCESS", "credential_property_name": "TIINGO_API_KEY", "credential_available": True}],
                "observations": [
                    {"returned_observation_timestamp": "2024-05-08T07:00:00.000Z", "provider_returned_timestamp_raw": "2024-05-08T07:00:00.000Z", "accepted_raw_price_field": "close", "accepted_raw_price": 155.1, "open": 155.0, "high": 155.2, "low": 154.9, "close": 155.1},
                    {"returned_observation_timestamp": "2024-05-08T07:00:00.000Z", "provider_returned_timestamp_raw": "2024-05-08T07:00:00.000Z", "accepted_raw_price_field": "close", "accepted_raw_price": 155.1, "open": 155.0, "high": 155.2, "low": 154.9, "close": 155.1},
                ],
            }
        }
        lineage, normalized = recovery.normalize_response(day, result, "2026-07-27T00:00:00Z", "raw.json", "sha")
        self.assertEqual(lineage["duplicate_timestamp_count"], 1)
        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized[0]["observation_type"], "OHLC")
        self.assertEqual(normalized[0]["source_resolution"], "ONE_MINUTE")
        self.assertEqual(normalized[0]["high"], 155.2)
        self.assertEqual(normalized[0]["timestamp"], "2024-05-08T07:00:00Z")

    def test_validation_requires_anchor_horizons_and_first_two_minutes(self) -> None:
        observations = [
            observation("2024-05-08T07:00:00Z", 155.1),
            observation("2024-05-08T07:01:00Z", 155.11),
            observation("2024-05-08T07:02:00Z", 155.12),
            observation("2024-05-08T07:05:00Z", 155.2),
            observation("2024-05-08T07:15:00Z", 155.3),
            observation("2024-05-08T07:30:00Z", 155.4),
            observation("2024-05-08T08:00:00Z", 155.5),
        ]
        rows, summary = recovery.validate_against_full_run([outcome()], observations)
        self.assertEqual(summary["anchor_exact"], 1)
        self.assertEqual(summary["first_minute_coverage"], 1)
        self.assertEqual(summary["second_minute_coverage"], 1)
        self.assertEqual(rows[0]["classification"], "EXACT_RECONCILIATION")

    def test_missing_second_minute_blocks_episode_admissibility(self) -> None:
        observations = [
            observation("2024-05-08T07:00:00Z", 155.1),
            observation("2024-05-08T07:01:00Z", 155.11),
            observation("2024-05-08T07:05:00Z", 155.2),
            observation("2024-05-08T07:15:00Z", 155.3),
            observation("2024-05-08T07:30:00Z", 155.4),
            observation("2024-05-08T08:00:00Z", 155.5),
        ]
        rows, summary = recovery.validate_against_full_run([outcome()], observations)
        self.assertEqual(summary["missing_count"], 1)
        self.assertEqual(rows[0]["classification"], "MISSING_OBSERVATIONS")

    def test_latest_available_minute_is_explained_reconciliation(self) -> None:
        explained = outcome()
        explained["source_lineage"]["selected_observations"]["30"]["timestamp"] = "2024-05-08T07:29:00Z"
        observations = [
            observation("2024-05-08T07:00:00Z", 155.1),
            observation("2024-05-08T07:01:00Z", 155.11),
            observation("2024-05-08T07:02:00Z", 155.12),
            observation("2024-05-08T07:05:00Z", 155.2),
            observation("2024-05-08T07:15:00Z", 155.3),
            observation("2024-05-08T07:29:00Z", 155.4),
            observation("2024-05-08T08:00:00Z", 155.5),
        ]
        rows, summary = recovery.validate_against_full_run([explained], observations)
        self.assertEqual(summary["mismatch_count"], 0)
        self.assertEqual(rows[0]["classification"], "EXPLAINED_RECONCILIATION")
        self.assertTrue(rows[0]["horizon_matches"][30]["explained_match"])

    def test_credential_route_check_never_exposes_secret_value(self) -> None:
        status = recovery.detect_credential_route()
        self.assertIsInstance(status.route_present, bool)
        self.assertFalse(hasattr(status, "token_value"))

    def test_recovery_writes_new_run_without_touching_source_run(self) -> None:
        run_id = recovery.recovery_run_id(datetime(2026, 7, 27, 0, 0, tzinfo=timezone.utc))
        self.assertTrue(run_id.startswith("PPHB-R1-TIINGO-MINUTE-CACHE-RECOVERY-"))
        self.assertNotIn(recovery.FULL_RUN_ID, run_id)


if __name__ == "__main__":
    unittest.main()
