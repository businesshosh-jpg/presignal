#!/usr/bin/env python3
"""Synthetic preregistration cases for v2.0 interaction outcome rule v0."""

from __future__ import annotations

import copy
import unittest
from datetime import datetime, timedelta, timezone

from automation.implement_phase9_v2_layered_prediction_evaluation_repair_v0 import _base_payload, _candles, _member
from automation.repair_phase9_v2_interaction_outcome_rule_v0 import _historical_interaction_status
from automation.v2_layered_prediction_evaluation_v0 import (
    FLAT_THRESHOLD_PIPS, INTERACTION_RULE_VERSION, classify_realized_interaction,
    construct_outcomes, evaluate_prediction, fingerprint, interaction_rule_fingerprint,
    interaction_rule_preregistration, normalize_session_members, parse_provider_prediction,
)


def _ts(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _cluster(cluster_id: str, release_minute: int, opening: float, closing: float, *, max_up: float | None = None, max_down: float | None = None):
    release = datetime(2031, 3, 1, 13, release_minute, tzinfo=timezone.utc)
    return {
        "outcome_id": "O_" + cluster_id, "outcome_level": "RELEASE_CLUSTER",
        "outcome_target_id": cluster_id, "outcome_status": "VALID",
        "outcome_window_start_ts": _ts(release), "outcome_window_end_ts": _ts(release + timedelta(minutes=5)),
        "opening_price_ts": _ts(release - timedelta(seconds=1)), "opening_price": opening,
        "closing_price_ts": _ts(release + timedelta(minutes=5)), "closing_price": closing,
        "max_up_pips": max_up if max_up is not None else max(0, round((closing - opening) / 0.01, 6)),
        "max_down_pips": max_down if max_down is not None else min(0, round((closing - opening) / 0.01, 6)),
        "outcome_fingerprint": fingerprint({"cluster": cluster_id, "opening": opening, "closing": closing}),
    }


def _session(opening: float = 150.0, closing: float = 150.0):
    return {
        "outcome_id": "O_SESSION", "outcome_level": "MARKET_SESSION", "outcome_target_id": "SESSION",
        "outcome_status": "VALID", "opening_price_ts": "2031-03-01T13:29:59Z", "opening_price": opening,
        "closing_price_ts": "2031-03-01T14:05:00Z", "closing_price": closing,
        "outcome_fingerprint": fingerprint({"session": True, "opening": opening, "closing": closing}),
    }


class InteractionRuleTest(unittest.TestCase):
    def classify(self, p0, p1, p2, p3, *, max_up=None, max_down=None):
        return classify_realized_interaction(
            _cluster("PRIMARY", 30, p0, p1),
            _cluster("SECONDARY", 59, p2, p3, max_up=max_up, max_down=max_down),
            _session(p0, p3),
        )

    def test_preregistration_fingerprint_is_stable_and_accuracy_blind(self):
        first = interaction_rule_preregistration("2031-01-01T00:00:00Z")
        second = interaction_rule_preregistration("2032-01-01T00:00:00Z")
        self.assertEqual(INTERACTION_RULE_VERSION, first["rule_version"])
        self.assertEqual(first["rule_fingerprint"], second["rule_fingerprint"])
        self.assertEqual(first["rule_fingerprint"], interaction_rule_fingerprint())
        self.assertTrue(first["prohibited_use_of_provider_accuracy"])
        self.assertTrue(first["provider_predictions_are_not_classifier_inputs"])

    def test_continuation(self):
        result = self.classify(150.00, 150.05, 150.05, 150.08)
        self.assertEqual("CONTINUATION", result["interaction_class"])
        self.assertEqual(5, result["primary_move_pips"])
        self.assertEqual(3, result["secondary_move_pips"])

    def test_small_same_direction_is_no_secondary_effect(self):
        result = self.classify(150.00, 150.05, 150.05, 150.06)
        self.assertEqual(FLAT_THRESHOLD_PIPS, result["secondary_abs_pips"])
        self.assertEqual("NO_MEANINGFUL_SECONDARY_EFFECT", result["interaction_class"])

    def test_partial_retrace(self):
        result = self.classify(150.00, 150.10, 150.10, 150.04)
        self.assertEqual("PARTIAL_RETRACE", result["interaction_class"])
        self.assertGreater(result["retrace_ratio"], 0)
        self.assertLess(result["retrace_ratio"], 1)

    def test_retrace_ratio_over_one_with_primary_net_is_residual(self):
        result = self.classify(150.00, 150.10, 150.20, 150.05)
        self.assertGreater(result["retrace_ratio"], 1)
        self.assertEqual("INDEPENDENT_VOLATILITY", result["interaction_class"])

    def test_exact_return_is_independent_volatility(self):
        result = self.classify(150.00, 150.10, 150.10, 150.00)
        self.assertEqual("INDEPENDENT_VOLATILITY", result["interaction_class"])
        self.assertEqual("SECONDARY_RETURNED_PRICE_TO_ORIGINAL_FLAT_BAND", result["classification_reason"])

    def test_full_reversal(self):
        result = self.classify(150.00, 150.10, 150.10, 149.95)
        self.assertEqual("FULL_REVERSAL", result["interaction_class"])
        self.assertLess(result["net_after_secondary_pips"], -FLAT_THRESHOLD_PIPS)

    def test_nonmeaningful_primary_is_independent_volatility(self):
        result = self.classify(150.00, 150.01, 150.01, 150.05)
        self.assertEqual("INDEPENDENT_VOLATILITY", result["interaction_class"])
        self.assertEqual("PRIMARY_MOVE_NOT_MEANINGFUL_SECONDARY_MOVE_MEANINGFUL", result["classification_reason"])

    def test_secondary_inside_flat_band_is_no_effect(self):
        result = self.classify(150.00, 150.05, 150.05, 150.055)
        self.assertEqual("NO_MEANINGFUL_SECONDARY_EFFECT", result["interaction_class"])

    def test_two_sided_flat_close_is_independent_volatility(self):
        result = self.classify(150.00, 150.05, 150.05, 150.055, max_up=6, max_down=-5)
        self.assertEqual("INDEPENDENT_VOLATILITY", result["interaction_class"])
        self.assertTrue(result["secondary_two_sided_excursion"])

    def test_missing_boundary_is_not_evaluable(self):
        primary = _cluster("PRIMARY", 30, 150.00, 150.05)
        primary["opening_price"] = ""
        result = classify_realized_interaction(primary, _cluster("SECONDARY", 59, 150.05, 150.08), _session(150, 150.08))
        self.assertEqual("NOT_EVALUABLE", result["interaction_class"])
        self.assertIn("INTERACTION_PRICE_MISSING", result["classification_reason"])

    def test_same_cluster_is_not_applicable(self):
        primary = _cluster("SAME", 30, 150.00, 150.05)
        secondary = copy.deepcopy(primary)
        result = classify_realized_interaction(primary, secondary, _session(150, 150.05))
        self.assertEqual("NOT_APPLICABLE", result["interaction_class"])
        self.assertEqual("NOT_APPLICABLE", result["evaluation_status"])

    def test_invalid_driver_order_fails_closed(self):
        primary = _cluster("PRIMARY", 59, 150.00, 150.05)
        secondary = _cluster("SECONDARY", 30, 150.05, 150.08)
        result = classify_realized_interaction(primary, secondary, _session(150, 150.08))
        self.assertEqual("NOT_EVALUABLE", result["interaction_class"])
        self.assertEqual("INVALID_DRIVER_ORDER_FOR_INTERACTION", result["classification_reason"])

    def test_boundary_timestamp_and_horizon_validation(self):
        primary = _cluster("PRIMARY", 30, 150.00, 150.05)
        primary["opening_price_ts"] = primary["outcome_window_start_ts"]
        result = classify_realized_interaction(primary, _cluster("SECONDARY", 59, 150.05, 150.08), _session(150, 150.08))
        self.assertEqual("NOT_EVALUABLE", result["interaction_class"])
        self.assertIn("OPENING_NOT_STRICTLY_PRE_RELEASE", result["classification_reason"])

    def test_multi_cluster_uses_selected_pair_only(self):
        ignored_first = _cluster("IGNORED_FIRST", 15, 150.00, 149.98)
        selected_primary = _cluster("SELECTED_PRIMARY", 30, 150.00, 150.05)
        ignored_middle = _cluster("IGNORED_MIDDLE", 45, 150.05, 150.02)
        selected_secondary = _cluster("SELECTED_SECONDARY", 59, 150.05, 150.08)
        result = classify_realized_interaction(selected_primary, selected_secondary, _session(150, 150.08))
        self.assertEqual("CONTINUATION", result["interaction_class"])
        self.assertNotIn(ignored_first["outcome_id"], {result["primary_outcome_id"], result["secondary_outcome_id"]})
        self.assertNotIn(ignored_middle["outcome_id"], {result["primary_outcome_id"], result["secondary_outcome_id"]})

    def test_between_release_behavior_is_separate(self):
        result = self.classify(150.00, 150.10, 150.06, 150.04)
        self.assertEqual("PARTIAL_RETRACE", result["between_release_behavior"])
        self.assertEqual("PARTIAL_RETRACE", result["secondary_release_interaction"])

    def test_layered_evaluation_linkage_and_session_preservation(self):
        session = {"session_id": "US|2031-04-01|CUSTOM_CONFIG_WINDOW", "session_date": "2031-04-01", "session_window_name": "CUSTOM_CONFIG_WINDOW", "fx_pair": "USDJPY"}
        members = [
            _member("evt-a", "CPI", "2031-04-01T13:30:00Z", "US|2031-04-01T13:30:00Z"),
            _member("evt-b", "ISM", "2031-04-01T15:00:00Z", "US|2031-04-01T15:00:00Z"),
        ]
        payload = _base_payload(session, members, "distinct")
        prediction, paths = parse_provider_prediction(
            payload, session=session, members=members, provider="P", model="M", pack_arm="A",
            pack_freeze_id="NO_PACK", pack_fingerprint="", forecast_run_id="R",
            forecast_created_ts="2031-03-31T00:00:00Z", forecast_cutoff_ts="2031-03-31T00:00:00Z",
            prompt_version="V", raw_output="fixture",
        )
        normalized = normalize_session_members(session["session_id"], members)
        outcomes = construct_outcomes(session=session, members=members, candles=_candles(normalized[0]["release_ts"], normalized[-1]["release_ts"]), generated_ts="2031-04-02T00:00:00Z")
        evaluations = evaluate_prediction(prediction, paths, outcomes, "2031-04-02T00:00:00Z")
        by_component = {}
        for row in evaluations:
            by_component.setdefault(row["evaluation_component"], []).append(row)
        self.assertEqual("CORRECT", by_component["PRIMARY_SECONDARY_INTERACTION"][0]["component_result"])
        self.assertIn(by_component["BETWEEN_RELEASE_BEHAVIOR"][0]["component_result"], {"CORRECT", "INCORRECT"})
        self.assertIn(by_component["PATH_DIRECTIONAL_SEQUENCE"][0]["component_result"], {"CORRECT", "INCORRECT"})
        self.assertIn(by_component["COMPLETE_PATH_STRICT"][0]["component_result"], {"CORRECT", "INCORRECT"})
        self.assertIn(by_component["SESSION_DIRECTION"][0]["component_result"], {"CORRECT", "INCORRECT"})
        self.assertEqual("NOT_YET_EVALUABLE", by_component["PRIMARY_DRIVER_CHOICE"][0]["component_result"])

    def test_historical_missing_and_unresolved_states_are_preserved(self):
        self.assertEqual("NOT_PREDICTED", _historical_interaction_status({"forecast_direction": "up"}))
        self.assertEqual("PARSE_UNRESOLVED", _historical_interaction_status({"primary_secondary_interaction": "CONTINUATION"}))
        self.assertEqual("EXPLICIT_INTERACTION_RECOVERABLE", _historical_interaction_status({
            "primary_secondary_interaction": "CONTINUATION",
            "primary_driver_release_cluster_id": "P", "secondary_driver_release_cluster_id": "S",
        }))


if __name__ == "__main__":
    unittest.main()
