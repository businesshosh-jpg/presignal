import unittest

from automation import presignal_v21_prospective_forecast_contract_v1 as contract
from automation.presignal_v21_canonical_states_v1 import ForecastState, SelectionState, canonical_states


CONTEXT = dict(episode_id="EP", provider="OpenAI", model="m", pack_arm="PACK_A", forecast_cutoff="2026-01-01T00:00:00Z")


def payload(direction="UP", **extra):
    value = {"path": [{"horizon_min": 15, "expected_direction": direction}]}
    value.update(extra)
    return value


class ProspectiveForecastContractTests(unittest.TestCase):
    def validate(self, value): return contract.validate_prospective_forecast(value, **CONTEXT)

    def test_primary_direction_is_sufficient_without_secondary_path(self):
        for direction in ("UP", "DOWN", "FLAT"):
            result = self.validate(payload(direction))
            self.assertTrue(result["primary_forecast_valid"])
            self.assertEqual(result["forecast_state"], ForecastState.DIRECTIONAL)
            self.assertFalse(result["secondary_path_complete"])

    def test_missing_or_invalid_15m_is_invalid_even_with_secondary_directions(self):
        missing = self.validate({"path": [{"horizon_min": 5, "expected_direction": "UP"}, {"horizon_min": 30, "expected_direction": "DOWN"}, {"horizon_min": 60, "expected_direction": "FLAT"}]})
        invalid = self.validate(payload("SIDEWAYS"))
        self.assertEqual(missing["forecast_state"], ForecastState.INVALID)
        self.assertEqual(invalid["forecast_state"], ForecastState.INVALID)

    def test_invalid_secondary_is_only_a_warning_and_complete_sidecar_is_detected(self):
        partial = self.validate(payload("UP", path=[{"horizon_min": 15, "expected_direction": "UP"}, {"horizon_min": 30, "expected_direction": "SIDEWAYS"}]))
        self.assertTrue(partial["primary_forecast_valid"])
        self.assertIn("SECONDARY_DIRECTION_30M_INVALID", partial["validation_warnings"])
        complete = self.validate(payload("UP", path=[{"horizon_min": 5, "expected_direction": "UP"}, {"horizon_min": 15, "expected_direction": "UP"}, {"horizon_min": 30, "expected_direction": "DOWN"}, {"horizon_min": 60, "expected_direction": "FLAT"}], confidence=.5, expected_reversal_flag=True, expected_reversal_horizon_min=30, expected_path_summary="path", invalidation_condition="condition"))
        self.assertTrue(complete["secondary_path_complete"])

    def test_no_signal_is_an_abstention_not_primary_evidence(self):
        result = self.validate({"no_signal_flag": True})
        self.assertEqual(result["forecast_state"], ForecastState.NO_SIGNAL)
        self.assertTrue(result["abstention_observation_valid"])
        self.assertFalse(result["primary_directional_eligibility"])

    def test_non_entry_and_runtime_failure_preserve_canonical_distinctions(self):
        for selection in (SelectionState.WATCH, SelectionState.IGNORED, SelectionState.NOT_SELECTED):
            self.assertEqual(contract.non_entry_result(selection_state=selection)["forecast_state"], ForecastState.NOT_APPLICABLE)
            states = canonical_states(attention={"selection_state": selection})
            self.assertEqual(states["runtime_state"], "NOT_ATTEMPTED")
        failed = canonical_states(attention={"selection_state": SelectionState.SELECTED}, forecast={"runtime_state": "TRANSPORT_FAILED"})
        self.assertEqual(failed["forecast_state"], ForecastState.INCOMPLETE)

    def test_pair_eligibility_needs_both_directions_not_secondary_completeness(self):
        a = self.validate(payload("UP")); e = self.validate(payload("DOWN"))
        e["pack_arm"] = "PACK_E"
        self.assertTrue(contract.primary_pair_eligible(a, e, outcome_available=True))
        e["forecast_target"] = "OTHER"
        self.assertFalse(contract.primary_pair_eligible(a, e, outcome_available=True))
        e["forecast_target"] = a["forecast_target"]
        e["primary_directional_eligibility"] = False
        self.assertFalse(contract.primary_pair_eligible(a, e, outcome_available=True))


if __name__ == "__main__":
    unittest.main()
