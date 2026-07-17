#!/usr/bin/env python3
"""Fixture-only checks for native v2 historical replay compatibility."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from automation import run_phase9_historical_square_one_replay_v0 as replay


class HistoricalReplayNativeLayeredCompatibilityTest(unittest.TestCase):
    def test_runner_fixture_contract_passes_without_provider_calls(self) -> None:
        result = replay.self_test()
        self.assertTrue(result["all_passed"])
        self.assertTrue(result["tests"]["native_v2_prediction_parses"])
        self.assertTrue(result["tests"]["legacy_flat_only_fails_closed"])
        self.assertTrue(result["tests"]["stage4a_contract_identity_attached"])

    def test_missing_frozen_contract_fails_closed(self) -> None:
        with patch.object(replay, "STAGE4A_CONTRACT_PATH", replay.ROOT / "outputs" / "missing-stage4a-contract.json"):
            with self.assertRaisesRegex(replay.SquareOneError, "MISSING_FROZEN_STAGE4A_CONTRACT"):
                replay._frozen_stage4a_contract_identity()

    def test_prompt_requires_native_v2_contract(self) -> None:
        session, members, _ = replay._reconstruct_sessions([{
            "event_id": "fixture-event", "batch_id": "fixture-batch", "type": "SINGLE", "country": "US",
            "indicator_name": "Fixture", "release_ts": "2024-01-02T13:30:00Z", "consensus_value": "1", "prev_revision": "1",
        }])
        prompt = replay._square_one_forecast_prompt(
            session[0], members, {"pack_selected": "NO_PACK", "pack_item_count": 0, "pack_e_exposure": False, "items": []},
            "OpenAI", replay.FORECAST_PROVIDERS["OpenAI"],
        )
        self.assertIn("native v2 layered Prediction", prompt["instruction"])
        self.assertIn("prediction_path", prompt["instruction"])


if __name__ == "__main__":
    unittest.main()
