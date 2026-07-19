#!/usr/bin/env python3
"""Focused tests for the frozen v2.1 Event-Path contract validator."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from automation import presignal_v21_event_path_contract_v1 as contract

EXAMPLES = Path(__file__).resolve().parents[1] / "contracts" / "presignal_v21_event_path" / "examples"


def load(name):
    return json.loads((EXAMPLES / name).read_text())


class EventPathContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.episode = load("valid_single_event_episode.json")
        cls.cluster = load("valid_same_time_cluster_episode.json")
        cls.baseline = load("valid_baseline_prediction.json")
        cls.full = load("valid_full_context_prediction.json")
        cls.paths = load("valid_prediction_path.json")
        cls.no_signal = load("valid_no_signal_prediction.json")
        cls.outcome = load("valid_outcome.json")
        cls.evaluation = load("valid_evaluation.json")

    def assertInvalid(self, function, *args):
        with self.assertRaises(contract.ContractValidationError):
            function(*args)

    def test_valid_examples(self):
        contract.validate_episode(self.episode)
        contract.validate_episode(self.cluster)
        contract.validate_prediction_path_transaction(self.baseline, self.paths)
        contract.validate_prediction_path_transaction(self.no_signal, [])
        contract.validate_outcome(self.outcome)
        contract.validate_evaluation(self.evaluation, self.baseline, self.outcome, self.paths)
        contract.validate_ae_pair(self.baseline, self.full)

    def test_episode_invalid_members_timestamp_and_status(self):
        for mutate in (
            lambda x: x.update(member_event_ids=[], member_event_count=0),
            lambda x: x.update(member_event_ids=[x["primary_event_id"], x["primary_event_id"]], member_indicator_names=["a", "b"], member_event_count=2, same_time_cluster_flag=True, episode_family="SAME_TIME_RELEASE_CLUSTER"),
            lambda x: x.update(release_ts="not-a-utc-timestamp"),
            lambda x: x.update(selection_status="UNKNOWN"),
        ):
            item = copy.deepcopy(self.episode); mutate(item)
            self.assertInvalid(contract.validate_episode, item)

    def test_duplicate_event_id_locator_is_collision_safe(self):
        left = {"event_id":"same", "batch_id":"B1", "country":"US", "indicator_name":"CPI", "release_ts":"2026-01-01T00:00:00Z", "source_cal":"FMP", "source_provider":"FMP", "source_series_id":"", "type":"member"}
        right = {**left, "batch_id":"B2", "indicator_name":"Payrolls"}
        self.assertNotEqual(contract.event_record_locator(left), contract.event_record_locator(right))

    def test_prediction_arm_target_cutoff_no_signal_and_provider_failure(self):
        bad_arm = copy.deepcopy(self.baseline); bad_arm["information_arm"] = "PACK_B"
        self.assertInvalid(contract.validate_prediction, bad_arm)
        bad_target = copy.deepcopy(self.baseline); bad_target["prediction_target_id"] = "SESSION_X"
        self.assertInvalid(contract.validate_prediction, bad_target)
        missing_cutoff = copy.deepcopy(self.baseline); missing_cutoff["forecast_cutoff_ts"] = ""
        self.assertInvalid(contract.validate_prediction, missing_cutoff)
        contract.validate_prediction(self.no_signal)
        provider_error = copy.deepcopy(self.baseline); provider_error.update(status="PROVIDER_ERROR", error_message="timeout")
        contract.validate_prediction(provider_error)

    def test_path_complete_duplicate_order_probability_and_identity(self):
        missing = self.paths[:-1]
        self.assertInvalid(contract.validate_prediction_path_transaction, self.baseline, missing)
        duplicate = copy.deepcopy(self.paths); duplicate[3]["horizon_min"] = 15
        self.assertInvalid(contract.validate_prediction_path_transaction, self.baseline, duplicate)
        unordered = copy.deepcopy(self.paths); unordered[0], unordered[1] = unordered[1], unordered[0]
        self.assertInvalid(contract.validate_prediction_path_transaction, self.baseline, unordered)
        probability = copy.deepcopy(self.paths); probability[0]["stage_confidence"] = 1.1
        self.assertInvalid(contract.validate_prediction_path_transaction, self.baseline, probability)
        mismatch = copy.deepcopy(self.paths); mismatch[0]["episode_id"] = "EP_OTHER"
        self.assertInvalid(contract.validate_prediction_path_transaction, self.baseline, mismatch)
        pip = copy.deepcopy(self.paths); pip[0]["expected_pips_min"] = 9
        self.assertInvalid(contract.validate_prediction_path_transaction, self.baseline, pip)

    def test_path_atomicity(self):
        self.assertInvalid(contract.validate_prediction_path_transaction, self.baseline, self.paths[:3])
        self.assertInvalid(contract.validate_prediction_path_transaction, self.no_signal, self.paths)

    def test_outcome_pips_direction_anchor_unavailable_and_reversal(self):
        contract.validate_outcome(self.outcome)
        bad_pips = copy.deepcopy(self.outcome); bad_pips["pips_15m"] = 6
        self.assertInvalid(contract.validate_outcome, bad_pips)
        bad_direction = copy.deepcopy(self.outcome); bad_direction["direction_15m"] = "DOWN"
        self.assertInvalid(contract.validate_outcome, bad_direction)
        stale = copy.deepcopy(self.outcome); stale["anchor_price_ts"] = "2026-01-02T13:28:00Z"
        self.assertInvalid(contract.validate_outcome, stale)
        bad_reversal = copy.deepcopy(self.outcome); bad_reversal["reversal_flag"] = False
        self.assertInvalid(contract.validate_outcome, bad_reversal)

    def test_evaluation_direction_flat_magnitude_reversal_and_pairing(self):
        contract.validate_evaluation(self.evaluation, self.baseline, self.outcome, self.paths)
        wrong = copy.deepcopy(self.evaluation); wrong["direction_15m_ok"] = False
        self.assertInvalid(contract.validate_evaluation, wrong, self.baseline, self.outcome, self.paths)
        magnitude = copy.deepcopy(self.evaluation); magnitude["magnitude_15m_error"] = 1
        self.assertInvalid(contract.validate_evaluation, magnitude, self.baseline, self.outcome, self.paths)
        reversal = copy.deepcopy(self.evaluation); reversal["reversal_ok"] = False
        self.assertInvalid(contract.validate_evaluation, reversal, self.baseline, self.outcome, self.paths)
        wrong_pair = copy.deepcopy(self.full); wrong_pair["model"] = "other"
        self.assertInvalid(contract.validate_ae_pair, self.baseline, wrong_pair)

    def test_fingerprints_fail_closed(self):
        bad_prediction = copy.deepcopy(self.baseline); bad_prediction["prediction_fingerprint"] = "sha256:wrong"
        self.assertInvalid(contract.validate_prediction, bad_prediction)
        bad_path = copy.deepcopy(self.paths); bad_path[0]["stage_fingerprint"] = "sha256:wrong"
        self.assertInvalid(contract.validate_prediction_path_transaction, self.baseline, bad_path)
        bad_outcome = copy.deepcopy(self.outcome); bad_outcome["outcome_fingerprint"] = "sha256:wrong"
        self.assertInvalid(contract.validate_outcome, bad_outcome)


if __name__ == "__main__":
    unittest.main()
