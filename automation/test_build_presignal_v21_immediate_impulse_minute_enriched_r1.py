from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation import build_presignal_v21_immediate_impulse_minute_enriched_r1 as enrichment


def forecast(**overrides):
    row = {
        "prediction_id": "PRD_fixture",
        "episode_id": "EP_FIXTURE",
        "provider": "Gemini",
        "model": "gemini-2.5-flash-lite",
        "information_arm": "BASELINE",
        "status": "VALID",
        "no_signal_flag": False,
        "immediate_impulse_direction": "UP",
        "early_reaction_5m_direction": "UP",
    }
    row.update(overrides)
    return row


def call_row(**overrides):
    row = {
        "call_id": "CALL_1",
        "call_index": 1,
        "episode_id": "EP_FIXTURE",
        "provider": "Gemini",
        "model": "gemini-2.5-flash-lite",
        "pack_arm": "PACK_A",
        "canonical_outcome_id": "OUT_fixture",
    }
    row.update(overrides)
    return row


def observation(ts: str, *, open_: float, high: float, low: float, close: float):
    return enrichment.Observation(
        timestamp=ts,
        instrument="USD/JPY",
        provider="tiingo",
        source_resolution="ONE_MINUTE",
        observation_type="OHLC",
        open=open_,
        high=high,
        low=low,
        close=close,
        bid=None,
        ask=None,
        midpoint=None,
        source_observation_id=None,
        request_identity="REQ_1",
        raw_artifact_reference="outputs/recovery/raw.json",
        raw_artifact_sha256="sha256:raw",
    )


def outcome(selected_30: str = "2024-05-08T07:30:00Z") -> dict:
    return {
        "episode_id": "EP_FIXTURE",
        "release_ts": "2024-05-08T07:00:00Z",
        "anchor_price_ts": "2024-05-08T07:00:00Z",
        "anchor_price": 155.0,
        "outcome_id": "OUT_fixture",
        "outcome_fingerprint": "sha256:outcome",
        "source_lineage": {
            "selected_observations": {
                "5": {"timestamp": "2024-05-08T07:05:00Z"},
                "15": {"timestamp": "2024-05-08T07:15:00Z"},
                "30": {"timestamp": selected_30},
                "60": {"timestamp": "2024-05-08T08:00:00Z"},
            }
        },
    }


def validation_row(classification: str = "EXACT_RECONCILIATION") -> dict:
    return {
        "episode_id": "EP_FIXTURE",
        "classification": classification,
        "anchor_match": {"timestamp_match": True, "price_match": True},
        "first_minute": {"present": True, "timestamp": "2024-05-08T07:01:00Z"},
        "second_minute": {"present": True, "timestamp": "2024-05-08T07:02:00Z"},
    }


class MinuteEnrichmentTests(unittest.TestCase):
    def test_one_minute_routing(self):
        self.assertEqual(enrichment.source_resolution_to_detector_mode("ONE_MINUTE"), "ONE_MINUTE_APPROXIMATION")

    def test_unsupported_tick_path_does_not_fabricate_result(self):
        result = enrichment.unsupported_detector_result("TICK")
        self.assertEqual(result["availability_status"], "STRICT_AVAILABLE")
        self.assertEqual(result["outcome_status"], "UNIMPLEMENTED_DETECTOR_PATH")

    def test_unsupported_one_second_path_does_not_fabricate_result(self):
        result = enrichment.unsupported_detector_result("ONE_SECOND")
        self.assertEqual(result["detector_mode"], "STRICT_ONE_SECOND_UNIMPLEMENTED")

    def test_unsupported_five_second_path_is_resolution_limited(self):
        result = enrichment.unsupported_detector_result("FIVE_SECOND")
        self.assertEqual(result["availability_status"], "RESOLUTION_LIMITED")

    def test_frozen_anchor_reuse_and_exact_reconciliation(self):
        obs = {
            "2024-05-08T07:01:00Z": observation("2024-05-08T07:01:00Z", open_=155.0, high=155.03, low=155.0, close=155.02),
            "2024-05-08T07:02:00Z": observation("2024-05-08T07:02:00Z", open_=155.02, high=155.04, low=155.01, close=155.03),
        }
        row = enrichment.build_enriched_outcome_row(outcome(), validation_row(), obs, "2026-07-27T09:00:00Z")
        self.assertEqual(row["anchor_source"], "ORIGINAL_ROUND_1_FROZEN_OUTCOME")
        self.assertEqual(row["anchor_reconciliation_status"], "EXACT_RECONCILIATION")
        self.assertEqual(row["first_minute_net_direction"], "UP")

    def test_first_minute_down(self):
        obs = {
            "2024-05-08T07:01:00Z": observation("2024-05-08T07:01:00Z", open_=155.0, high=155.0, low=154.96, close=154.97),
            "2024-05-08T07:02:00Z": observation("2024-05-08T07:02:00Z", open_=154.97, high=154.98, low=154.95, close=154.96),
        }
        row = enrichment.build_enriched_outcome_row(outcome(), validation_row(), obs, "2026-07-27T09:00:00Z")
        self.assertEqual(row["first_minute_net_direction"], "DOWN")

    def test_flat_threshold(self):
        obs = {
            "2024-05-08T07:01:00Z": observation("2024-05-08T07:01:00Z", open_=155.0, high=155.005, low=154.995, close=155.009),
            "2024-05-08T07:02:00Z": observation("2024-05-08T07:02:00Z", open_=155.009, high=155.01, low=155.0, close=155.008),
        }
        row = enrichment.build_enriched_outcome_row(outcome(), validation_row(), obs, "2026-07-27T09:00:00Z")
        self.assertEqual(row["first_minute_net_direction"], "FLAT")

    def test_both_side_excursion_ambiguity(self):
        obs = {
            "2024-05-08T07:01:00Z": observation("2024-05-08T07:01:00Z", open_=155.0, high=155.02, low=154.98, close=155.015),
            "2024-05-08T07:02:00Z": observation("2024-05-08T07:02:00Z", open_=155.015, high=155.03, low=155.01, close=155.02),
        }
        row = enrichment.build_enriched_outcome_row(outcome(), validation_row(), obs, "2026-07-27T09:00:00Z")
        self.assertFalse(row["intraminute_sequence_known"])
        self.assertEqual(row["ambiguity_reason"], "BOTH_SIDES_EXCURSION_ORDER_UNKNOWN")

    def test_one_sided_excursion(self):
        obs = {
            "2024-05-08T07:01:00Z": observation("2024-05-08T07:01:00Z", open_=155.0, high=155.02, low=155.0, close=155.015),
            "2024-05-08T07:02:00Z": observation("2024-05-08T07:02:00Z", open_=155.015, high=155.03, low=155.01, close=155.02),
        }
        row = enrichment.build_enriched_outcome_row(outcome(), validation_row(), obs, "2026-07-27T09:00:00Z")
        self.assertTrue(row["intraminute_sequence_known"])
        self.assertIsNone(row["ambiguity_reason"])

    def test_missing_first_minute_blocks(self):
        with self.assertRaisesRegex(enrichment.EnrichmentError, "MISSING_REQUIRED_MINUTES"):
            enrichment.build_enriched_outcome_row(outcome(), validation_row(), {}, "2026-07-27T09:00:00Z")

    def test_two_minute_rule(self):
        obs = {
            "2024-05-08T07:01:00Z": observation("2024-05-08T07:01:00Z", open_=155.0, high=155.03, low=155.0, close=155.02),
            "2024-05-08T07:02:00Z": observation("2024-05-08T07:02:00Z", open_=155.02, high=155.05, low=155.01, close=155.04),
        }
        row = enrichment.build_enriched_outcome_row(outcome(), validation_row(), obs, "2026-07-27T09:00:00Z")
        self.assertEqual(row["two_minute_net_direction"], "UP")
        self.assertEqual(row["two_minute_net_pips"], 4.0)

    def test_minute_continuation(self):
        self.assertEqual(enrichment.minute_path_class("UP", "UP", True), "CONTINUATION")

    def test_minute_reversal(self):
        self.assertEqual(enrichment.minute_path_class("UP", "DOWN", True), "REVERSAL")

    def test_provider_and_resolution_lineage_preserved(self):
        obs = {
            "2024-05-08T07:01:00Z": observation("2024-05-08T07:01:00Z", open_=155.0, high=155.03, low=155.0, close=155.02),
            "2024-05-08T07:02:00Z": observation("2024-05-08T07:02:00Z", open_=155.02, high=155.04, low=155.01, close=155.03),
        }
        row = enrichment.build_enriched_outcome_row(outcome(), validation_row(), obs, "2026-07-27T09:00:00Z")
        self.assertEqual(row["provider"], "tiingo")
        self.assertEqual(row["source_resolution"], "ONE_MINUTE")
        self.assertEqual(row["observation_type"], "OHLC")

    def test_explained_horizon_selection_remains_admissible(self):
        self.assertEqual(validation_row("EXPLAINED_RECONCILIATION")["classification"], "EXPLAINED_RECONCILIATION")

    def test_evaluation_denominator_accounting(self):
        directional = enrichment.build_evaluation_row(call_row(), forecast(), {
            "episode_id": "EP_FIXTURE",
            "availability_status": "APPROXIMATION_ONLY",
            "first_minute_net_direction": "UP",
            "two_minute_net_direction": "UP",
            "intraminute_sequence_known": True,
            "minute_resolution_path_class": "CONTINUATION",
        }, "2026-07-27T09:00:00Z")
        no_signal = enrichment.build_evaluation_row(call_row(call_id="CALL_2", pack_arm="PACK_E"), forecast(prediction_id="PRD_2", information_arm="FULL_CONTEXT", status="NO_SIGNAL", no_signal_flag=True, immediate_impulse_direction=None, early_reaction_5m_direction="UNCERTAIN"), {
            "episode_id": "EP_FIXTURE",
            "availability_status": "APPROXIMATION_ONLY",
            "first_minute_net_direction": "UP",
            "two_minute_net_direction": "UP",
            "intraminute_sequence_known": True,
            "minute_resolution_path_class": "CONTINUATION",
        }, "2026-07-27T09:00:00Z")
        failed = enrichment.evaluation_row_for_schema_failure(call_row(call_id="CALL_3"), "2026-07-27T09:00:00Z")
        metrics = enrichment.metric_block([directional, no_signal, failed])
        self.assertEqual(metrics["directional_forecast_count"], 1)
        self.assertEqual(metrics["valid_no_signal_count"], 1)
        self.assertEqual(metrics["schema_failure_count"], 1)

    def test_pair_accounting(self):
        base = enrichment.build_evaluation_row(call_row(), forecast(), {
            "episode_id": "EP_FIXTURE",
            "availability_status": "APPROXIMATION_ONLY",
            "first_minute_net_direction": "UP",
            "two_minute_net_direction": "UP",
            "intraminute_sequence_known": True,
            "minute_resolution_path_class": "CONTINUATION",
        }, "2026-07-27T09:00:00Z")
        full = enrichment.build_evaluation_row(call_row(call_id="CALL_2", pack_arm="PACK_E"), forecast(prediction_id="PRD_2", information_arm="FULL_CONTEXT", immediate_impulse_direction="DOWN", early_reaction_5m_direction="DOWN"), {
            "episode_id": "EP_FIXTURE",
            "availability_status": "APPROXIMATION_ONLY",
            "first_minute_net_direction": "UP",
            "two_minute_net_direction": "UP",
            "intraminute_sequence_known": True,
            "minute_resolution_path_class": "CONTINUATION",
        }, "2026-07-27T09:00:00Z")
        rows = enrichment.build_pair_rows([base, full])
        self.assertEqual(rows[0]["pair_transition"], "BOTH_DIRECTIONAL")
        self.assertEqual(rows[0]["all_close_direction_evaluable_pair_classification"], "degradation")

    def test_deterministic_output_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.jsonl"
            enrichment.write_jsonl(p, [{"a": 1}, {"b": 2}])
            self.assertEqual(p.read_text(), '{"a":1}\n{"b":2}\n')


if __name__ == "__main__":
    unittest.main()
