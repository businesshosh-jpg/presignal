from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation import close_presignal_v21_pack_e_prospective_v1_source_calendar_timeout as closure


class SourceCalendarTimeoutClosureTests(unittest.TestCase):
    def test_evidence_is_official_bounded_and_never_market_data(self):
        register = closure.documentation_register()
        self.assertEqual(register["actual_documentation_pages"]["total"], 6)
        self.assertEqual(register["authorization"]["maximum_requests"]["total"], 18)
        self.assertEqual(register["market_data_endpoint_calls"], 0)
        self.assertEqual(register["authenticated_requests"], 0)

    def test_all_seven_routes_remain_fail_closed_without_availability_instant(self):
        matrix = closure.source_calendar_matrix()
        self.assertEqual(len(matrix), 7)
        self.assertEqual({row["decision"] for row in matrix}, {"SOURCE_CALENDAR_AUTHORITY_PARTIALLY_CONFIRMED"})
        self.assertEqual({row["availability_decision"] for row in matrix}, {"PACK_E_PROSPECTIVE_V1_AVAILABILITY_RULES_BLOCKED"})
        self.assertTrue(all(row["same_day_completed_period"] == "NOT_PROVEN" for row in matrix))
        self.assertTrue(all(row["prior_period_availability_before_arbitrary_cutoff"] == "NOT_PROVEN" for row in matrix))

    def test_numeric_only_and_timeout_blocks_are_preserved(self):
        numeric = closure.numeric_only()
        self.assertIn("omitted", numeric["categorical_directions"])
        timeout = closure.timeout_authority()
        self.assertEqual(timeout["decision"], "PACK_E_PROSPECTIVE_V1_TIMEOUT_AUTHORITY_BLOCKED")
        self.assertIsNone(timeout["FRED"]["total_timeout"])
        self.assertEqual(timeout["retry_boundary"], 0)

    def test_lead_time_contract_and_implementation_remain_blocked(self):
        evidence = closure.build_evidence()
        self.assertIsNone(evidence["lead_time"]["maximum_prerequisite_execution_window_seconds"])
        self.assertEqual(evidence["field_contract"]["decision"], "PACK_E_PROSPECTIVE_V1_FIELD_CONTRACT_BLOCKED")
        self.assertEqual(evidence["implementation_authorization"]["decision"], "PACK_E_PROSPECTIVE_V1_IMPLEMENTATION_REMAINS_BLOCKED")
        self.assertEqual(evidence["activity"]["market_data_calls"], 0)

    def test_output_is_deterministic_and_append_only(self):
        first = closure.build_evidence()
        self.assertEqual(first["fingerprint"], closure.build_evidence()["fingerprint"])
        with tempfile.TemporaryDirectory() as directory:
            result = closure.reconcile(Path(directory) / "evidence")
        self.assertEqual(result["fingerprint"], first["fingerprint"])


if __name__ == "__main__":
    unittest.main()
