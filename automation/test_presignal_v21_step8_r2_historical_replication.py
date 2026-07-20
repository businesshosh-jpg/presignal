import unittest
from pathlib import Path

from automation import run_presignal_v21_step8_r2_historical_replication_v1 as runner


class Step8R2Tests(unittest.TestCase):
    def test_population_is_exact_and_outcome_blind(self):
        summary, eligible, _excluded, _source = runner.recover_population()
        self.assertEqual(summary["reconstructed_sessions"], 249)
        self.assertEqual(summary["eligible_sessions"], 239)
        self.assertGreaterEqual(len(eligible), 80)
        selected = eligible[:80]
        self.assertEqual(len({row["episode_id"] for row in selected}), 80)
        self.assertEqual(selected, sorted(selected, key=lambda x: (x["release_ts"], x["session_id"], x["episode_id"])))
        self.assertTrue(all("direction_15m" not in row for row in selected))

    def test_selection_mapping_fails_closed(self):
        self.assertEqual(runner.selection_action([{ "status":"parsed", "attention_label":"PRIMARY_DRIVER"}]), "FORECAST")
        self.assertEqual(runner.selection_action([{ "status":"parsed", "attention_label":"SECONDARY_DRIVER"}]), "WATCH")
        self.assertEqual(runner.selection_action([{ "status":"provider_contract_error"}]), "UNAVAILABLE")

    def test_repaired_contract_is_explicit(self):
        spec = runner.prospective.contract_spec()
        self.assertEqual(spec["contract_version"], runner.prospective.PROSPECTIVE_CONTRACT_VERSION)
        self.assertEqual(runner.REPLAY_CONTRACT_ROLE, "HISTORICAL_REPLICATION_OUTPUT_CONTRACT")


if __name__ == "__main__":
    unittest.main()
