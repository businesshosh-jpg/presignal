import copy
import unittest

from automation import prepare_presignal_v21_round_2_execution_envelope as preparation


class Round2ExecutionEnvelopeTest(unittest.TestCase):
    def setUp(self):
        self.protocol = preparation.load_protocol(preparation.PROTOCOL_PATH)
        self.envelope = preparation.build_envelope(self.protocol)
        self.blocker = preparation.build_blocked_slice_evidence(self.protocol, self.envelope)
        self.dispatch = preparation.build_dispatch_inputs(self.protocol, self.envelope, self.blocker)

    def test_protocol_binding_and_inactive_status(self):
        self.assertEqual(self.envelope["protocol_binding"]["protocol_fingerprint"], "sha256:d417e4c76d3d38d471dbc76cbf361be4a28dac1b615ecccdc8aa18c37262362f")
        self.assertEqual(self.envelope["envelope_status"], "FROZEN_INACTIVE_NO_PROVIDER_AUTHORITY")
        self.assertEqual(self.envelope["population_limits"]["maximum_episodes_per_slice"], 48)

    def test_no_current_prospective_population_fails_closed(self):
        self.assertEqual(self.blocker["eligible_episode_count"], 0)
        self.assertEqual(self.blocker["selected_episode_count"], 0)
        self.assertEqual(self.blocker["unresolved_conflict"], "PROSPECTIVE_EPISODE_SOURCE_AUTHORITY_MISSING")
        self.assertTrue(self.blocker["exclusions"]["synthetic_prospective_fixtures"])

    def test_routes_and_pairing_rule_are_preserved(self):
        routes = self.envelope["provider_model_allocation"]["routes"]
        self.assertEqual(len(routes), 3)
        self.assertIn("one Pack A and one Pack E call", self.envelope["provider_model_allocation"]["rule"])
        self.assertIn("shared cutoff", self.envelope["provider_model_allocation"]["pack_pairing"])

    def test_dispatch_inputs_are_not_authorization(self):
        self.assertEqual(self.dispatch["maximum_provider_calls"], 0)
        self.assertEqual(self.dispatch["exact_forecast_call_identities"], [])
        self.assertEqual(self.dispatch["retry_boundary"], 0)
        self.assertIsNone(self.dispatch["manifest_binding"])

    def test_envelope_tampering_changes_fingerprint(self):
        tampered = copy.deepcopy(self.envelope)
        original = preparation.digest(tampered)
        tampered["population_limits"]["maximum_admitted_episodes"] = 48
        self.assertNotEqual(original, preparation.digest(tampered))


if __name__ == "__main__":
    unittest.main()
