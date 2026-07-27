from __future__ import annotations

import copy
import unittest

from automation import immediate_impulse_outcome_recovery_contract_r1 as recovery


def valid_record(**overrides):
    record = {
        "episode_id": "EP_EVENT_fixture",
        "forecast_id": "PRD_fixture",
        "provider": "Gemini",
        "model": "gemini-2.5-flash-lite",
        "pack_arm": "FULL_CONTEXT",
        "release_timestamp": "2024-05-08T07:00:00Z",
        "market_data_source": "historical_market_data_endpoint.js|tiingo",
        "market_data_resolution": "ONE_MINUTE_OHLC",
        "observation_start_timestamp": "2024-05-08T06:50:00Z",
        "observation_end_timestamp": "2024-05-08T07:02:00Z",
        "observation_count": 13,
        "raw_observation_artifact_reference": "outputs/presignal_v21_immediate_impulse_recovery/fixture/raw_observations.jsonl",
        "anchor_method": "LAST_VALID_MIDPOINT_STRICTLY_BEFORE_T",
        "anchor_fallback_reason": "MEDIAN_WINDOW_EMPTY",
        "anchor_timestamp": "2024-05-08T06:59:00Z",
        "anchor_price": 155.2955,
        "detector_parameters": {
            "minimum_move_pips": 3.0,
            "minimum_persistence_seconds": 15,
            "directional_retention_pips": 1.0,
            "maximum_temporary_violations": 1,
            "maximum_detection_window_seconds": 120,
        },
        "immediate_impulse_status": "APPROXIMATION_ONLY",
        "immediate_impulse_direction": "UP",
        "immediate_impulse_start_timestamp": "2024-05-08T07:00:00Z",
        "immediate_impulse_threshold_cross_timestamp": "2024-05-08T07:01:00Z",
        "immediate_impulse_peak_timestamp": "2024-05-08T07:02:00Z",
        "immediate_impulse_peak_pips": 3.1,
        "immediate_impulse_adverse_pips": -0.8,
        "immediate_impulse_persistence_seconds": 60,
        "immediate_impulse_reversed_by_120s": False,
        "net_move_at_120s_pips": 2.2,
        "net_direction_at_120s": "UP",
        "contract_version": recovery.CONTRACT_ID,
        "schema_version": recovery.SCHEMA_VERSION,
        "evaluator_version": "immediate_impulse_recovery_audit_r1",
        "generated_timestamp": "2026-07-27T09:00:00Z",
    }
    record.update(overrides)
    return record


class ImmediateImpulseOutcomeRecoveryContractTests(unittest.TestCase):
    def test_schema_files_expose_frozen_ids(self):
        outcome_schema = recovery.load_outcome_schema()
        detector_schema = recovery.load_detector_schema()
        self.assertEqual(outcome_schema["$id"], recovery.SCHEMA_ID)
        self.assertEqual(detector_schema["$id"], recovery.DETECTOR_SCHEMA_ID)
        self.assertEqual(
            detector_schema["properties"]["maximum_detection_window_seconds"]["const"],
            recovery.MAXIMUM_DETECTION_WINDOW_SECONDS,
        )

    def test_approximation_only_record_validates(self):
        recovery.validate_outcome_record(valid_record())

    def test_strict_available_requires_subminute_resolution(self):
        record = valid_record(
            immediate_impulse_status="STRICT_AVAILABLE",
            market_data_resolution="SECOND",
            anchor_method="MEDIAN_VALID_MIDPOINT_T_MINUS_10S_TO_T_MINUS_2S",
            anchor_fallback_reason="",
        )
        recovery.validate_outcome_record(record)
        invalid = copy.deepcopy(record)
        invalid["market_data_resolution"] = "ONE_MINUTE_OHLC"
        with self.assertRaisesRegex(recovery.ImmediateImpulseContractError, "OUTCOME_STRICT_RESOLUTION"):
            recovery.validate_outcome_record(invalid)

    def test_outcome_unavailable_fails_closed(self):
        record = valid_record(
            immediate_impulse_status="OUTCOME_UNAVAILABLE",
            immediate_impulse_direction="UNAVAILABLE",
            immediate_impulse_start_timestamp=None,
            immediate_impulse_threshold_cross_timestamp=None,
            immediate_impulse_peak_timestamp=None,
            immediate_impulse_peak_pips=None,
            immediate_impulse_adverse_pips=None,
            immediate_impulse_persistence_seconds=None,
            immediate_impulse_reversed_by_120s=None,
            net_move_at_120s_pips=None,
            net_direction_at_120s="UNAVAILABLE",
        )
        recovery.validate_outcome_record(record)
        invalid = copy.deepcopy(record)
        invalid["immediate_impulse_peak_pips"] = 1.2
        with self.assertRaisesRegex(recovery.ImmediateImpulseContractError, "OUTCOME_UNAVAILABLE_IMMEDIATE_IMPULSE_PEAK_PIPS"):
            recovery.validate_outcome_record(invalid)

    def test_pre_release_impulse_timestamp_is_rejected(self):
        invalid = valid_record(immediate_impulse_start_timestamp="2024-05-08T06:59:59Z")
        with self.assertRaisesRegex(recovery.ImmediateImpulseContractError, "OUTCOME_IMMEDIATE_START_POST_RELEASE"):
            recovery.validate_outcome_record(invalid)

    def test_detector_window_is_system_frozen(self):
        invalid = valid_record()
        invalid["detector_parameters"] = dict(invalid["detector_parameters"])
        invalid["detector_parameters"]["maximum_detection_window_seconds"] = 300
        with self.assertRaisesRegex(recovery.ImmediateImpulseContractError, "DETECTOR_MAXIMUM_DETECTION_WINDOW_SECONDS"):
            recovery.validate_outcome_record(invalid)


if __name__ == "__main__":
    unittest.main()
