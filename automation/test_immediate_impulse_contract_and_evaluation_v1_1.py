#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from automation import build_presignal_v21_episode_outcomes_v1_1 as outcomes
from automation import presignal_v21_event_path_contract_v1_1 as contract
from automation import run_presignal_v21_single_event_path_pair_v1_1 as step6
from automation.test_run_presignal_v21_single_event_path_pair_v1_1 import input_row, response


EXAMPLES = Path(__file__).resolve().parents[1] / "contracts" / "presignal_v21_event_path" / "examples"


def load(name):
    return json.loads((EXAMPLES / name).read_text())


def observation(ts: str, close: float, provider: str = "FIXTURE") -> dict:
    return {
        "timestamp": ts,
        "close": close,
        "provider": provider,
        "request_id": "REQ_1",
        "provider_returned_timestamp_raw": ts,
        "accepted_raw_price_field": "close",
    }


def request_lineage(day: str) -> dict:
    return {
        day: {
            "request_id": "REQ_1",
            "day": day,
            "window_start": day + "T00:00:00Z",
            "window_end": day + "T23:59:00Z",
            "status": "SUCCESS",
            "selected_provider": "FIXTURE",
            "returned_observation_count": 8,
            "provider_attempts": [],
            "transport_error": "",
        }
    }


class ImmediateImpulseTests(unittest.TestCase):
    def build_outcome(self, prices: list[tuple[str, float]]):
        episode = {"episode_id": "EP_FIXTURE", "session_id": "SES_FIXTURE", "release_ts": "2026-01-02T13:30:00Z"}
        rows = [observation(ts, close) for ts, close in prices]
        record, disposition = outcomes.outcome_record(episode, outcomes.ObservationIndex(rows), request_lineage("2026-01-02"), False, "2026-01-02T14:31:00Z")
        self.assertEqual(disposition, "AVAILABLE")
        contract.validate_outcome(record)
        return record

    def build_prediction(self, direction: str = "UP", episode_id: str = "EP_FIXTURE"):
        row = input_row(arm="PACK_A", members=1, episode_id=episode_id)
        payload = copy.deepcopy(response())
        payload["immediate_impulse_direction"] = direction
        payload["early_reaction_5m_direction"] = direction
        payload["path"][0]["expected_direction"] = direction
        return step6.response_to_contract(payload, row, run_id="RUN_FIXTURE", created_ts="2026-01-02T13:28:00Z", raw_output=payload, bridge_result={"prompt_tokens": 1, "completion_tokens": 2, "latency_ms": 3})

    def test_case_1_sustained_upward_impulse(self):
        outcome = self.build_outcome([
            ("2026-01-02T13:30:00Z", 150.00),
            ("2026-01-02T13:31:00Z", 150.03),
            ("2026-01-02T13:32:00Z", 150.05),
            ("2026-01-02T13:35:00Z", 150.04),
            ("2026-01-02T13:45:00Z", 150.06),
            ("2026-01-02T14:00:00Z", 150.02),
            ("2026-01-02T14:30:00Z", 149.98),
        ])
        self.assertEqual(outcome["immediate_impulse_outcome_state"], "APPROXIMATION_ONLY")
        self.assertEqual(outcome["confirmed_initial_direction"], "UP")
        self.assertFalse(outcome["false_initial_excursion_flag"])
        prediction, paths = self.build_prediction("UP")
        evaluation = step6.evaluate(prediction, paths, outcome, generated_ts="2026-01-02T14:32:00Z")
        self.assertTrue(evaluation["direction_5m_ok"])
        self.assertTrue(evaluation["initial_impulse_sustained_to_t5"])
        self.assertFalse(evaluation["initial_impulse_faded_by_t5"])
        self.assertFalse(evaluation["initial_impulse_reversed_by_t5"])

    def test_case_2_false_upward_excursion_followed_by_confirmed_decline(self):
        outcome = self.build_outcome([
            ("2026-01-02T13:30:00Z", 150.00),
            ("2026-01-02T13:31:00Z", 150.03),
            ("2026-01-02T13:32:00Z", 149.96),
            ("2026-01-02T13:35:00Z", 149.95),
            ("2026-01-02T13:45:00Z", 149.94),
            ("2026-01-02T14:00:00Z", 149.93),
            ("2026-01-02T14:30:00Z", 149.92),
        ])
        self.assertTrue(outcome["false_initial_excursion_flag"])
        self.assertEqual(outcome["false_initial_excursion_direction"], "UP")
        self.assertEqual(outcome["confirmed_initial_direction"], "DOWN")

    def test_case_3_initial_rise_fades_to_near_flat_by_t5(self):
        outcome = self.build_outcome([
            ("2026-01-02T13:30:00Z", 150.00),
            ("2026-01-02T13:31:00Z", 150.03),
            ("2026-01-02T13:32:00Z", 150.05),
            ("2026-01-02T13:35:00Z", 150.004),
            ("2026-01-02T13:45:00Z", 150.03),
            ("2026-01-02T14:00:00Z", 150.02),
            ("2026-01-02T14:30:00Z", 150.01),
        ])
        prediction, paths = self.build_prediction("UP")
        evaluation = step6.evaluate(prediction, paths, outcome, generated_ts="2026-01-02T14:32:00Z")
        self.assertEqual(outcome["confirmed_initial_direction"], "UP")
        self.assertTrue(evaluation["initial_impulse_faded_by_t5"])

    def test_case_4_initial_direction_reverses_before_t5(self):
        outcome = self.build_outcome([
            ("2026-01-02T13:30:00Z", 150.00),
            ("2026-01-02T13:31:00Z", 150.03),
            ("2026-01-02T13:32:00Z", 150.05),
            ("2026-01-02T13:35:00Z", 149.95),
            ("2026-01-02T13:45:00Z", 149.94),
            ("2026-01-02T14:00:00Z", 149.93),
            ("2026-01-02T14:30:00Z", 149.92),
        ])
        prediction, paths = self.build_prediction("UP")
        evaluation = step6.evaluate(prediction, paths, outcome, generated_ts="2026-01-02T14:32:00Z")
        self.assertTrue(evaluation["initial_impulse_reversed_by_t5"])

    def test_case_5_insufficient_five_minute_market_data_marks_immediate_impulse_unavailable(self):
        outcome = self.build_outcome([
            ("2026-01-02T13:30:00Z", 150.00),
            ("2026-01-02T13:35:00Z", 150.03),
            ("2026-01-02T13:45:00Z", 150.05),
            ("2026-01-02T14:00:00Z", 149.98),
            ("2026-01-02T14:30:00Z", 149.96),
        ])
        self.assertEqual(outcome["immediate_impulse_outcome_state"], "UNAVAILABLE_UNSUPPORTED_RESOLUTION")

    def test_case_6_one_minute_data_is_approximation_only(self):
        outcome = self.build_outcome([
            ("2026-01-02T13:30:00Z", 150.00),
            ("2026-01-02T13:31:00Z", 149.97),
            ("2026-01-02T13:32:00Z", 149.95),
            ("2026-01-02T13:35:00Z", 149.94),
            ("2026-01-02T13:45:00Z", 149.93),
            ("2026-01-02T14:00:00Z", 149.92),
            ("2026-01-02T14:30:00Z", 149.91),
        ])
        self.assertEqual(outcome["immediate_impulse_outcome_state"], "APPROXIMATION_ONLY")

    def test_case_7_legacy_immediate_sidecar_missing_but_t15_valid(self):
        outcome = load("valid_outcome_v1_1.json")
        outcome.update({
            "immediate_impulse_outcome_state": "NOT_AVAILABLE_LEGACY_SCHEMA",
            "first_meaningful_excursion_direction": "UNAVAILABLE",
            "first_meaningful_excursion_timestamp": None,
            "first_meaningful_excursion_pips": None,
            "confirmed_initial_direction": "UNAVAILABLE",
            "initial_direction_confirmation_timestamp": None,
            "initial_peak_pips": None,
            "initial_peak_timestamp": None,
            "maximum_opposite_excursion_pips": None,
            "false_initial_excursion_flag": False,
            "false_initial_excursion_direction": None,
            "initial_peak_retention_at_t5": None,
        })
        outcome["outcome_fingerprint"] = contract._fingerprint(outcome, "outcome_fingerprint", ("acquisition_ts", "status", "error_message"))
        contract.validate_outcome(outcome)
        prediction = load("valid_baseline_prediction_v1_1.json")
        paths = load("valid_prediction_path_v1_1.json")
        evaluation = step6.evaluate(prediction, paths, outcome, generated_ts="2026-01-02T14:32:00Z")
        self.assertTrue(evaluation["direction_15m_ok"])
        self.assertEqual(evaluation["immediate_impulse_direction_result"], "NOT_APPLICABLE")

    def test_case_8_runtime_failure_is_not_counted_as_incorrect_direction(self):
        prediction = load("valid_baseline_prediction_v1_1.json")
        prediction.update({
            "status": "PROVIDER_ERROR",
            "error_message": "runtime failure",
            "immediate_impulse_direction": None,
            "immediate_impulse_peak_pips_min": None,
            "immediate_impulse_peak_pips_max": None,
            "immediate_impulse_confidence": None,
            "immediate_impulse_window_seconds": None,
        })
        prediction["prediction_fingerprint"] = contract._fingerprint(prediction, "prediction_fingerprint", ("run_id", "forecast_created_ts", "prompt_tokens", "completion_tokens", "latency_ms", "status", "error_message"))
        contract.validate_prediction(prediction)
        outcome = load("valid_outcome_v1_1.json")
        evaluation = step6.evaluate(prediction, [], outcome, generated_ts="2026-01-02T14:32:00Z")
        self.assertEqual(evaluation["status"], "UNAVAILABLE")
        self.assertIsNone(evaluation["direction_15m_ok"])


if __name__ == "__main__":
    unittest.main()
