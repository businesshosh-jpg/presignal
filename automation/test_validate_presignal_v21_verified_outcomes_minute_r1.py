from __future__ import annotations

import unittest

from automation import validate_presignal_v21_verified_outcomes_minute_r1 as validation


def point(provider: str, ts: str, price: float, anchor_ts: str = "2024-05-08T07:00:00Z"):
    return validation.VerifiedPoint(
        provider=provider,
        target="15m",
        timestamp=ts,
        price=price,
        direction=validation.direction_from_pips(validation.signed_pips(price, 155.00)),
        pips=validation.signed_pips(price, 155.00),
        anchor_timestamp=anchor_ts,
    )


def immediate_row(**overrides):
    row = {
        "episode_id": "EP1",
        "provider": "Gemini",
        "model": "gemini-2.5-flash-lite",
        "pack_arm": "PACK_A",
        "evaluation_status": "COMPLETED_DIRECTIONAL_FORECAST",
        "first_minute_direction_result": "CORRECT",
        "two_minute_direction_result": "INCORRECT",
        "sequence_unambiguous_direction_result": "CORRECT",
        "sequence_unambiguous": True,
        "verified_population_included": True,
        "verified_first_minute_quality_status": "MULTI_SOURCE_CONFIRMED",
        "verified_second_minute_quality_status": "MULTI_SOURCE_CONFIRMED",
        "no_signal_flag": False,
    }
    row.update(overrides)
    return row


def t15_row(**overrides):
    row = {
        "episode_id": "EP1",
        "provider": "Gemini",
        "model": "gemini-2.5-flash-lite",
        "information_arm": "BASELINE",
        "direction_15m_ok": True,
        "verified_population_included": True,
        "verified_target_quality_status": "MULTI_SOURCE_CONFIRMED",
    }
    row.update(overrides)
    return row


class VerifiedReleaseValidationTests(unittest.TestCase):
    def test_points_agree_boundary(self):
        left = point("tiingo", "2024-05-08T07:15:00Z", 155.03)
        right = point("eodhd", "2024-05-08T07:15:00Z", 155.01)
        self.assertTrue(validation.points_agree(left, right))
        far = point("eodhd", "2024-05-08T07:15:00Z", 155.07)
        self.assertFalse(validation.points_agree(left, far))

    def test_points_agree_rejects_anchor_delta_gt_60_seconds(self):
        left = point("tiingo", "2024-05-08T07:15:00Z", 155.03, "2024-05-08T07:00:00Z")
        right = point("eodhd", "2024-05-08T07:15:00Z", 155.03, "2024-05-08T07:01:01Z")
        self.assertFalse(validation.points_agree(left, right))

    def test_clustered_subset_finds_valid_pair(self):
        cluster = validation.clustered_subset([
            point("eodhd", "2024-05-08T07:15:00Z", 155.03),
            point("twelvedata", "2024-05-08T07:15:00Z", 155.02),
            point("massive", "2024-05-08T07:15:00Z", 154.90),
        ])
        self.assertEqual({row.provider for row in cluster}, {"eodhd", "twelvedata"})

    def test_classify_target_detects_no_consensus(self):
        primary = point("tiingo", "2024-05-08T07:15:00Z", 155.03)
        eodhd = point("eodhd", "2024-05-08T07:15:00Z", 154.90)
        twelve = point("twelvedata", "2024-05-08T07:15:00Z", 155.20)
        status, accepted, _, _, _ = validation.classify_target(primary, [eodhd, twelve])
        self.assertEqual(status, "SOURCE_DISAGREEMENT")
        self.assertIsNone(accepted)

    def test_t15_metric_recomputation(self):
        metrics = validation.t15_metric_recomputation([
            t15_row(direction_15m_ok=True),
            t15_row(provider="OpenAI", model="gpt-4o-mini-2024-07-18", information_arm="FULL_CONTEXT", direction_15m_ok=False),
        ])
        self.assertEqual(metrics["overall"]["numerator"], 1)
        self.assertEqual(metrics["overall"]["denominator"], 2)

    def test_immediate_metric_recomputation(self):
        metrics = validation.immediate_metric_recomputation([
            immediate_row(first_minute_direction_result="CORRECT", two_minute_direction_result="CORRECT"),
            immediate_row(provider="OpenAI", model="gpt-4o-mini-2024-07-18", pack_arm="PACK_E", first_minute_direction_result="INCORRECT", two_minute_direction_result="CORRECT", sequence_unambiguous_direction_result="INCORRECT"),
        ])
        self.assertEqual(metrics["overall_first_minute"]["numerator"], 1)
        self.assertEqual(metrics["overall_two_minute"]["numerator"], 2)

    def test_denominator_audit_explains_target_specific_exclusions(self):
        report = validation.denominator_audit(
            {
                "call_reconciliation": {"authorized_calls": 170},
                "forecast_arm_reconciliation": {"completed_directional_forecasts": 133, "valid_no_signals": 12, "schema_failures": 25},
            },
            [
                immediate_row(),
                immediate_row(prediction_id="PRD2", verified_first_minute_quality_status="SOURCE_DISAGREEMENT", verified_population_included=False),
            ],
            [
                t15_row(),
                t15_row(prediction_id="PRD2", direction_15m_ok=None, verified_population_included=False, verified_target_quality_status="SOURCE_DISAGREEMENT"),
            ],
        )
        self.assertEqual(report["total_forecast_arms"], 170)
        self.assertIn("t15_denominator_130", report["explanation"])

    def test_pair_classification_definitions(self):
        self.assertEqual(validation.pair_classification(False, True), "correction")
        self.assertEqual(validation.pair_classification(True, False), "degradation")

    def test_supersession_statement_requirements(self):
        report = validation.supersession_audit({
            "statement": "The prior Tiingo-only minute enrichment remains valid as a reproducible single-source baseline. It is superseded for final scientific Outcome reporting because its market observations were not independently verified. The original AI predictions remain valid and unchanged. The supersession applies only to accepted Outcome construction and evaluation."
        })
        self.assertEqual(report["result"], "PASS")

    def test_subminute_readiness_contract_preserved(self):
        report = validation.sub_minute_readiness_audit()
        self.assertTrue(report["checks"]["source_resolutions_present"])
        self.assertTrue(report["checks"]["observation_types_present"])

    def test_deterministic_fingerprint(self):
        payload = {"a": 1}
        self.assertEqual(validation.sha256_value(payload), validation.sha256_value(payload))


if __name__ == "__main__":
    unittest.main()
