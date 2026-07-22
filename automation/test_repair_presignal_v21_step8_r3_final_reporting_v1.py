#!/usr/bin/env python3
"""Focused tests for final NO_SIGNAL reporting taxonomy."""
from __future__ import annotations

import unittest

from automation import repair_presignal_v21_step8_r3_final_reporting_v1 as reporting


def forecast(accepted: bool, no_signal: bool = False) -> dict:
    return {"accepted": accepted, "output": {"prediction": {"no_signal_flag": no_signal}}} if accepted else {"accepted": False, "rejection_reason": "REJECTED"}


class ReportingTaxonomyTests(unittest.TestCase):
    def stages(self, a: dict, e: dict, request: bool = True) -> dict:
        return {"REQUEST:": {"accepted": request, "rejection_reason": "timeout" if not request else None}, "FORECAST:PACK_A": a, "FORECAST:PACK_E": e, "EVALUATE:": {"output": {"PACK_A": {"direction_15m_ok": True}, "PACK_E": {"direction_15m_ok": False}}}}

    def test_directional_pair(self) -> None:
        self.assertEqual(reporting.classify(self.stages(forecast(True), forecast(True)))[:2], ("DIRECTIONAL_PAIR_EVALUABLE", "BOTH_ARMS_DIRECTIONAL"))

    def test_no_signal_subclasses(self) -> None:
        self.assertEqual(reporting.classify(self.stages(forecast(True, True), forecast(True, True)))[:2], ("VALID_NO_SIGNAL_PAIR", "BOTH_ARMS_NO_SIGNAL"))
        self.assertEqual(reporting.classify(self.stages(forecast(True, True), forecast(True)))[:2], ("VALID_NO_SIGNAL_PAIR", "PACK_A_NO_SIGNAL_PACK_E_DIRECTIONAL"))
        self.assertEqual(reporting.classify(self.stages(forecast(True), forecast(True, True)))[:2], ("VALID_NO_SIGNAL_PAIR", "PACK_A_DIRECTIONAL_PACK_E_NO_SIGNAL"))

    def test_missing_and_request_failure_are_incomplete(self) -> None:
        self.assertEqual(reporting.classify(self.stages(forecast(False), forecast(True)))[:2], ("TRUE_INCOMPLETE_PAIR", "PACK_A_MISSING"))
        self.assertEqual(reporting.classify(self.stages(forecast(False), forecast(False)))[:2], ("TRUE_INCOMPLETE_PAIR", "BOTH_ARMS_MISSING"))
        self.assertEqual(reporting.classify(self.stages(forecast(False), forecast(False), request=False))[:2], ("TRUE_INCOMPLETE_PAIR", "REQUEST_TRANSPORT_FAILURE"))

    def test_authoritative_reconciliation(self) -> None:
        rows = reporting.pair_rows()
        counts = {name: sum(row["top_level_status"] == name for row in rows) for name in ("DIRECTIONAL_PAIR_EVALUABLE", "VALID_NO_SIGNAL_PAIR", "TRUE_INCOMPLETE_PAIR")}
        self.assertEqual(counts, {"DIRECTIONAL_PAIR_EVALUABLE": 52, "VALID_NO_SIGNAL_PAIR": 83, "TRUE_INCOMPLETE_PAIR": 57})
        self.assertEqual(sum(counts.values()), 192)
        self.assertEqual(52 / 192, 0.2708333333333333)
        self.assertEqual(135 / 192, 0.703125)


if __name__ == "__main__":
    unittest.main()
