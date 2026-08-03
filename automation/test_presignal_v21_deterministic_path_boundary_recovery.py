import json
import re
import unittest
from pathlib import Path

from automation import run_presignal_v21_single_event_path_pair_v1_1 as step6


ROOT = Path(__file__).resolve().parents[1]
RAW_RUN = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution" / "PPHB-R1-FORECAST-EXECUTION-BATCH-010-20260801T190644Z-17f70b192668"
TARGET = "FCL_3d10ae8285471f4e3a980b79"


def raw_target() -> str:
    for line in (RAW_RUN / "raw_provider_outputs.jsonl").read_text().splitlines():
        row = json.loads(line)
        if row.get("forecast_call_id") == TARGET:
            return row["raw_provider_output"]
    raise AssertionError("target raw output not found")


class DeterministicPathBoundaryRecoveryTests(unittest.TestCase):
    def test_exact_scope_and_original_raw_hash(self):
        self.assertEqual(TARGET, "FCL_3d10ae8285471f4e3a980b79")
        self.assertNotIn("FCL_27720b8b23236b173b96fdee", TARGET)
        self.assertNotIn("FCL_7f0463b134c67757968580e8", TARGET)
        self.assertNotIn("FCL_e07264654e9d3da6f63088a1", TARGET)
        import hashlib
        self.assertEqual(
            hashlib.sha256(raw_target().encode()).hexdigest(),
            "1f6c333ccb4489eb1f634d90a2b6ee8de7c42277066ef3568cced8e11e007860",
        )

    def test_one_boundary_repairs_and_strict_validation_passes(self):
        raw = raw_target()
        repaired, audit = step6.repair_missing_path_boundary(raw)
        self.assertEqual(audit["status"], "REPAIRED_ONE_STRUCTURAL_BOUNDARY")
        self.assertEqual(audit["candidate_count"], 1)
        self.assertEqual(raw.count('"horizon_min"'), 4)
        normalized, normalized_audit = step6.normalize_provider_output(raw)
        self.assertEqual([stage["horizon_min"] for stage in normalized["path"]], [5, 15, 30, 60])
        self.assertEqual(normalized_audit["path_boundary_repair"]["status"], "REPAIRED_ONE_STRUCTURAL_BOUNDARY")
        self.assertNotEqual(raw, repaired)
        self.assertEqual(repaired.count('"horizon_min"'), raw.count('"horizon_min"'))
        self.assertEqual(__import__('hashlib').sha256(repaired.encode()).hexdigest(), "142487ec9cad381f7e268c2afb20ad16045f15e7cb92e3e42f835b23821b946d")

    def test_valid_structure_is_unchanged(self):
        valid = '{"path":[{"invalidation_condition":"a","horizon_min":5},{"horizon_min":15},{"horizon_min":30},{"horizon_min":60}]}'
        repaired, audit = step6.repair_missing_path_boundary(valid)
        self.assertEqual(repaired, valid)
        self.assertEqual(audit["status"], "NO_REPAIR_POSITION")

    def test_zero_and_multiple_candidates_fail_closed(self):
        clean = '{"path": [{"horizon_min": 5}]}'
        _, audit = step6.repair_missing_path_boundary(clean)
        self.assertEqual(audit["status"], "NO_REPAIR_POSITION")
        ambiguous = '{"path": [{"invalidation_condition": "a", "horizon_min": 5, "invalidation_condition": "b", "horizon_min": 15}]}'
        with self.assertRaisesRegex(step6.Step6Error, "PATH_BOUNDARY_AMBIGUOUS"):
            step6.repair_missing_path_boundary(ambiguous)

    def test_missing_semantic_fields_remain_rejected(self):
        payload = {
            "no_signal_flag": False,
            "no_signal_reason": None,
            "confidence": 0.5,
            "immediate_impulse_direction": "UP",
            "immediate_impulse_peak_pips_min": 1,
            "immediate_impulse_peak_pips_max": 2,
            "immediate_impulse_confidence": 0.5,
            "early_reaction_5m_direction": "UP",
            "expected_reversal_flag": False,
            "expected_reversal_horizon_min": None,
            "expected_path_summary": "x",
            "information_used": [],
            "missing_information": [],
            "invalidation_condition": "x",
            "path": [
                {"horizon_min": horizon, "expected_direction": "UP", "expected_pips_min": 1, "expected_pips_max": 2,
                 "stage_confidence": 0.5, "continuation_probability": 0.5, "reversal_probability": 0.5, "stage_reason": "x"}
                for horizon in [5, 15, 30, 60]
            ],
        }
        with self.assertRaisesRegex(step6.Step6Error, "PATH_FIELDS"):
            step6.normalize_provider_output(json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
