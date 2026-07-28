#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automation import freeze_presignal_v21_full_round1_eligibility_contract as contract


class FreezeFullRound1EligibilityContractTest(unittest.TestCase):
    def test_missing_attention_does_not_change_episode_eligibility(self) -> None:
        row = {
            "episode_id": "EP_X",
            "release_ts": "2024-05-01T00:00:00Z",
            "forecast_cutoff_ts": "2024-05-01T00:00:00Z",
            "member_event_count": 1,
            "member_event_ids": ["EV1"],
            "historical_attention_status": "ATTENTION_LINEAGE_MISSING",
            "episode_type": "STANDALONE",
            "event_family": "Test",
        }
        pre = {
            "request_compatibility_status": "COMPATIBLE",
            "request_compatibility_reason": "",
            "pack_compatibility_status": "COMPATIBLE",
            "pack_compatibility_reason": "",
            "legacy_outcome_status": "VALID",
            "population_status": "ELIGIBLE",
            "population_exclusion_detail": None,
        }
        result = contract.build_application_row(row, pre, set(), set())
        self.assertEqual(result["episode_eligibility_status"], "ELIGIBLE")
        self.assertEqual(result["attention_status"], "ATTENTION_RECONSTRUCTABLE")

    def test_outcome_unavailable_does_not_change_episode_eligibility(self) -> None:
        row = {
            "episode_id": "EP_Y",
            "release_ts": "2024-05-19T19:30:00Z",
            "forecast_cutoff_ts": "2024-05-19T19:30:00Z",
            "member_event_count": 1,
            "member_event_ids": ["EV1"],
            "historical_attention_status": "ATTENTION_LINEAGE_AVAILABLE",
            "episode_type": "STANDALONE",
            "event_family": "Powell",
        }
        pre = {
            "request_compatibility_status": "COMPATIBLE",
            "request_compatibility_reason": "",
            "pack_compatibility_status": "COMPATIBLE",
            "pack_compatibility_reason": "",
            "legacy_outcome_status": "UNAVAILABLE",
            "population_status": "EXCLUDED_OUTCOME_UNAVAILABLE",
            "population_exclusion_detail": "MISSING_OR_STALE_ANCHOR_PRICE_5M_PRICE_15M_PRICE_30M_PRICE_60M",
        }
        result = contract.build_application_row(row, pre, {"EP_Y"}, {"EP_Y"})
        self.assertEqual(result["episode_eligibility_status"], "ELIGIBLE")
        self.assertEqual(result["outcome_status_t15"], "OUTCOME_UNAVAILABLE")
        self.assertEqual(result["evaluation_status_t15"], "OUTCOME_UNAVAILABLE")

    def test_input_admissibility_is_pack_local(self) -> None:
        self.assertEqual(contract.classify_input_admissibility("PACK_EXISTING_EXACT")[0], "PRE_CUTOFF_CONFIRMED")
        self.assertEqual(contract.classify_input_admissibility("PACK_RECONSTRUCTABLE")[0], "HISTORICAL_VERSION_UNVERIFIED")
        self.assertEqual(contract.classify_input_admissibility("PACK_UNAVAILABLE")[0], "SOURCE_UNAVAILABLE")

    def test_runtime_and_forecast_state_contracts_remain_separate(self) -> None:
        runtime = contract.runtime_status_contract()["statuses"]
        forecast = contract.forecast_status_contract()["statuses"]
        self.assertIn("TRANSPORT_FAILED", runtime)
        self.assertIn("NO_SIGNAL", forecast)
        self.assertNotIn("NO_SIGNAL", runtime)

    def test_freeze_contract_reconciles_all_462_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = contract.freeze_contract(output_root=Path(tmp), fixed_timestamp="2026-07-28T00:00:00Z")
            self.assertEqual(result["candidate_episode_count"], 462)
            self.assertEqual(result["eligible_episode_count"], 462)
            self.assertEqual(result["ineligible_episode_count"], 0)
            self.assertEqual(result["attention_exact_count"], 48)
            self.assertEqual(result["attention_reconstructable_count"], 341)
            self.assertEqual(result["attention_unavailable_count"], 73)
            self.assertEqual(result["pack_a_exact_count"], 48)
            self.assertEqual(result["pack_a_reconstructable_count"], 341)
            self.assertEqual(result["pack_a_unavailable_count"], 73)
            self.assertEqual(result["pack_e_exact_count"], 48)
            self.assertEqual(result["pack_e_reconstructable_count"], 341)
            self.assertEqual(result["pack_e_unavailable_count"], 73)
            run_dir = Path(tmp) / result["run_id"]
            previous = [json.loads(line) for line in (run_dir / "previous_47_contract_application.jsonl").read_text().splitlines() if line.strip()]
            self.assertEqual(len(previous), 47)

    def test_deterministic_contract_fingerprint_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = contract.freeze_contract(output_root=Path(tmp), fixed_timestamp="2026-07-28T00:00:00Z")
            second = contract.freeze_contract(output_root=Path(tmp), fixed_timestamp="2026-07-28T00:00:00Z")
            self.assertEqual(first["run_id"], second["run_id"])


if __name__ == "__main__":
    unittest.main()
