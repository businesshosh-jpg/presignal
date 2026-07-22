import unittest

from automation import presignal_v21_canonical_states_v1 as states


def attention(label, accepted=True):
    return {"accepted": accepted, "output": {"rows": [{"status": "parsed", "attention_label": label}]}}


def directional(accepted=True):
    return {"accepted": accepted, "transport_status": "ok", "output": {"prediction": {"no_signal_flag": False}}}


class CanonicalStateTests(unittest.TestCase):
    def test_watch_and_ignore_are_not_runtime_incompletion(self):
        for label, expected in (("WATCHLIST", states.SelectionState.WATCH), ("IGNORE", states.SelectionState.IGNORED)):
            result = states.canonical_states(attention=attention(label))
            self.assertEqual(result, {"selection_state": expected, "runtime_state": states.RuntimeState.NOT_ATTEMPTED, "forecast_state": states.ForecastState.NOT_APPLICABLE, "evaluation_state": states.EvaluationState.NOT_APPLICABLE})
            states.validate_transition(result)

    def test_valid_non_entry_is_not_attempted(self):
        result = states.canonical_states(attention=attention("NO_SIGNAL"))
        self.assertEqual(result["selection_state"], states.SelectionState.NOT_SELECTED)
        self.assertEqual(result["runtime_state"], states.RuntimeState.NOT_ATTEMPTED)
        states.validate_transition(result)

    def test_transport_failure_is_incomplete(self):
        result = states.canonical_states(attention=attention("PRIMARY_DRIVER"), forecast={"accepted": False, "transport_status": "exception"})
        self.assertEqual(result["runtime_state"], states.RuntimeState.TRANSPORT_FAILED)
        self.assertEqual(result["forecast_state"], states.ForecastState.INCOMPLETE)
        self.assertEqual(result["evaluation_state"], states.EvaluationState.NOT_APPLICABLE)
        states.validate_transition(result)

    def test_no_signal_is_valid_and_non_directional(self):
        result = states.canonical_states(attention=attention("PRIMARY_DRIVER"), forecast={"accepted": True, "transport_status": "ok", "output": {"prediction": {"no_signal_flag": True}}})
        self.assertEqual(result["runtime_state"], states.RuntimeState.SUCCESS)
        self.assertEqual(result["forecast_state"], states.ForecastState.NO_SIGNAL)
        self.assertEqual(result["evaluation_state"], states.EvaluationState.NOT_APPLICABLE)

    def test_directional_evaluation_uses_outcome_only(self):
        correct = states.canonical_states(attention=attention("PRIMARY_DRIVER"), forecast=directional(), evaluation={"direction_15m_ok": True}, outcome={"status": "VALID"})
        pending = states.canonical_states(attention=attention("PRIMARY_DRIVER"), forecast=directional())
        unavailable = states.canonical_states(attention=attention("PRIMARY_DRIVER"), forecast=directional(), outcome={"status": "UNAVAILABLE"})
        self.assertEqual(correct["evaluation_state"], states.EvaluationState.CORRECT)
        self.assertEqual(pending["evaluation_state"], states.EvaluationState.PENDING_OUTCOME)
        self.assertEqual(unavailable["evaluation_state"], states.EvaluationState.OUTCOME_UNAVAILABLE)

    def test_invalid_provider_content_is_not_no_signal_or_incorrect(self):
        result = states.canonical_states(attention=attention("PRIMARY_DRIVER"), forecast={"accepted": False, "transport_status": "ok", "output": None})
        self.assertEqual(result["runtime_state"], states.RuntimeState.PROVIDER_REJECTED)
        self.assertEqual(result["forecast_state"], states.ForecastState.INVALID)
        self.assertEqual(result["evaluation_state"], states.EvaluationState.NOT_APPLICABLE)

    def test_structured_legacy_mapping_never_uses_reason_text(self):
        self.assertEqual(states.runtime_state({"accepted": False, "transport_status": "exception", "rejection_reason": "schema invalid"}), states.RuntimeState.TRANSPORT_FAILED)
        self.assertEqual(states.runtime_state({"accepted": False, "transport_status": "ok", "rejection_reason": "timeout"}), states.RuntimeState.PROVIDER_REJECTED)


if __name__ == "__main__":
    unittest.main()
