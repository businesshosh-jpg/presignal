"""Call-free checks for the accepted Round 1 Outcome authorization package."""

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "outputs/presignal_v21_full_round_1_forecast_execution/PPHB-R1-OUTCOME-AUTHORIZATION-PREPARATION-20260803T090000Z-18cddcdc5477"


class OutcomeAuthorizationPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.partition = json.loads((PACKAGE / "forecast_population_partition.json").read_text())
        cls.next_move = json.loads((PACKAGE / "next_authorization_draft.json").read_text())
        cls.run_manifest = json.loads((PACKAGE / "run_manifest.json").read_text())

    def test_full_identity_partition_and_pairing(self):
        self.assertEqual(self.partition["frozen_calls"], 564)
        self.assertEqual(self.partition["authoritative_valid_forecasts"], 561)
        self.assertEqual(self.partition["terminal_invalid_calls"], 3)
        self.assertEqual(self.partition["unexecuted_calls"], 0)
        self.assertEqual(self.partition["complete_pack_a_e_pairs"], 279)
        self.assertEqual(self.partition["pack_a_only_valid"], 1)
        self.assertEqual(self.partition["pack_e_only_valid"], 2)
        self.assertEqual(self.partition["pair_identity_mismatches"], 0)

    def test_recovered_forecast_is_in_a_complete_pair(self):
        self.assertTrue(self.partition["recovered_call"]["participates_in_complete_pair"])

    def test_next_move_is_bounded_and_does_not_execute(self):
        episodes = self.next_move["episode_manifest"]
        self.assertEqual(len(episodes), 12)
        self.assertEqual(len({row["episode_id"] for row in episodes}), 12)
        self.assertEqual(len({row["release_ts"][:10] for row in episodes}), 3)
        self.assertEqual(self.next_move["max_apps_script_google_reads"], 3)
        self.assertEqual(self.next_move["max_google_writes"], 0)
        self.assertEqual(self.next_move["max_market_data_provider_attempts"], 12)

    def test_preparation_has_no_external_side_effects(self):
        for key in ("provider_calls", "google_reads", "google_writes", "market_data_calls", "outcome_attachment", "evaluation_calculations"):
            self.assertEqual(self.run_manifest[key], 0)


if __name__ == "__main__":
    unittest.main()
