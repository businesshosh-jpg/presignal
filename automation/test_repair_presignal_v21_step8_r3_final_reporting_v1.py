#!/usr/bin/env python3
"""Focused tests for final NO_SIGNAL reporting taxonomy."""
from __future__ import annotations

import unittest
import os
from pathlib import Path

from automation import repair_presignal_v21_step8_r3_final_reporting_v1 as reporting


def forecast(accepted: bool, no_signal: bool = False) -> dict:
    return {"accepted": accepted, "transport_status": "ok", "output": {"prediction": {"no_signal_flag": no_signal}}} if accepted else {"accepted": False, "transport_status": "ok", "rejection_reason": "REJECTED"}


class ReportingTaxonomyTests(unittest.TestCase):
    def stages(self, a: dict, e: dict, request: bool = True) -> dict:
        return {"REQUEST:": {"accepted": request, "transport_status": "exception" if not request else "ok", "rejection_reason": "timeout" if not request else None}, "FORECAST:PACK_A": a, "FORECAST:PACK_E": e, "EVALUATE:": {"output": {"PACK_A": {"direction_15m_ok": True}, "PACK_E": {"direction_15m_ok": False}}}}

    def test_directional_pair(self) -> None:
        self.assertEqual(reporting.classify(self.stages(forecast(True), forecast(True)))[:2], ("DIRECTIONAL_PAIR_EVALUABLE", "BOTH_ARMS_DIRECTIONAL"))

    def test_no_signal_subclasses(self) -> None:
        self.assertEqual(reporting.classify(self.stages(forecast(True, True), forecast(True, True)))[:2], ("VALID_NO_SIGNAL_PAIR", "BOTH_ARMS_NO_SIGNAL"))
        self.assertEqual(reporting.classify(self.stages(forecast(True, True), forecast(True)))[:2], ("VALID_NO_SIGNAL_PAIR", "PACK_A_NO_SIGNAL_PACK_E_DIRECTIONAL"))
        self.assertEqual(reporting.classify(self.stages(forecast(True), forecast(True, True)))[:2], ("VALID_NO_SIGNAL_PAIR", "PACK_A_DIRECTIONAL_PACK_E_NO_SIGNAL"))

    def test_invalid_and_incomplete_are_not_directional_or_abstention(self) -> None:
        self.assertEqual(reporting.classify(self.stages(forecast(False), forecast(True)))[:2], ("TRUE_INCOMPLETE_PAIR", "INVALID_OR_INCOMPLETE_FORECAST"))
        self.assertEqual(reporting.classify(self.stages(forecast(False), forecast(False)))[:2], ("TRUE_INCOMPLETE_PAIR", "INVALID_OR_INCOMPLETE_FORECAST"))

    def test_report_uses_canonical_states_without_text_inference(self) -> None:
        attention = {"accepted": False, "selection_state": "REJECTED", "raw_response": "PRIMARY_DRIVER"}
        self.assertEqual(reporting.states.selection_state(attention), "REJECTED")
        timeout_word = {"accepted": False, "transport_status": "ok", "rejection_reason": "timeout OAuth network transport"}
        self.assertEqual(reporting.states.runtime_state(timeout_word), "PROVIDER_REJECTED")

    def test_non_entry_and_operational_states_are_separate(self) -> None:
        records = [
            {"episode_id": "watch", "provider": "OpenAI", "model": "m", "selection_state": "WATCH", "arms": {arm: {"forecast_state": "NOT_APPLICABLE", "evaluation_state": "NOT_APPLICABLE"} for arm in ("PACK_A", "PACK_E")}, "operations": [{"runtime_state": "NOT_ATTEMPTED"}], "top_level_status": "NOT_FORECAST_SELECTED"},
            {"episode_id": "ignored", "provider": "OpenAI", "model": "m", "selection_state": "IGNORED", "arms": {arm: {"forecast_state": "NOT_APPLICABLE", "evaluation_state": "NOT_APPLICABLE"} for arm in ("PACK_A", "PACK_E")}, "operations": [{"runtime_state": "NOT_ATTEMPTED"}], "top_level_status": "NOT_FORECAST_SELECTED"},
            {"episode_id": "not-selected", "provider": "OpenAI", "model": "m", "selection_state": "NOT_SELECTED", "arms": {arm: {"forecast_state": "NOT_APPLICABLE", "evaluation_state": "NOT_APPLICABLE"} for arm in ("PACK_A", "PACK_E")}, "operations": [{"runtime_state": "NOT_ATTEMPTED"}], "top_level_status": "NOT_FORECAST_SELECTED"},
            {"episode_id": "transport", "provider": "OpenAI", "model": "m", "selection_state": "SELECTED", "arms": {arm: {"forecast_state": "INCOMPLETE", "evaluation_state": "NOT_APPLICABLE"} for arm in ("PACK_A", "PACK_E")}, "operations": [{"runtime_state": "TRANSPORT_FAILED"}], "top_level_status": "TRUE_INCOMPLETE_PAIR"},
            {"episode_id": "no-signal", "provider": "Gemini", "model": "m", "selection_state": "SELECTED", "arms": {"PACK_A": {"forecast_state": "NO_SIGNAL", "evaluation_state": "NOT_APPLICABLE"}, "PACK_E": {"forecast_state": "DIRECTIONAL", "evaluation_state": "CORRECT"}}, "operations": [{"runtime_state": "SUCCESS"}], "top_level_status": "VALID_NO_SIGNAL_PAIR"},
        ]
        report = reporting.canonical_report(records)
        self.assertEqual(report["selection_summary"]["counts"]["WATCH"], 1)
        self.assertEqual(report["selection_summary"]["counts"]["IGNORED"], 1)
        self.assertEqual(report["selection_summary"]["counts"]["NOT_SELECTED"], 1)
        self.assertEqual(report["operational_summary"]["counts"]["NOT_ATTEMPTED"], 3)
        self.assertEqual(report["operational_summary"]["counts"]["TRANSPORT_FAILED"], 1)
        self.assertEqual(report["abstention_summary"]["counts"]["pack_a_no_signal"], 1)
        self.assertEqual(report["directional_summary"]["denominator"], 0)
        self.assertEqual(reporting.canonical_report(list(reversed(records))), report)

    def test_authoritative_reconciliation(self) -> None:
        source_run = Path(os.environ.get("PRESIGNAL_V21_FROZEN_STAGE_RESULTS_DIR", reporting.SOURCE_RUN))
        if source_run.name == "stage_results":
            source_run = source_run.parent
        if not source_run.exists() or not any((source_run / "stage_results").glob("*.json")):
            self.skipTest("frozen historical stage-results are not present; set PRESIGNAL_V21_FROZEN_STAGE_RESULTS_DIR")
        previous = reporting.SOURCE_RUN
        previous_root = reporting.recon.ROOT
        reporting.SOURCE_RUN = source_run
        reporting.recon.ROOT = source_run.parents[2]
        try:
            rows = reporting.pair_rows()
        finally:
            reporting.SOURCE_RUN = previous
            reporting.recon.ROOT = previous_root
        counts = {name: sum(row["top_level_status"] == name for row in rows) for name in ("DIRECTIONAL_PAIR_EVALUABLE", "VALID_NO_SIGNAL_PAIR", "TRUE_INCOMPLETE_PAIR")}
        self.assertEqual(counts, {"DIRECTIONAL_PAIR_EVALUABLE": 52, "VALID_NO_SIGNAL_PAIR": 83, "TRUE_INCOMPLETE_PAIR": 57})
        self.assertEqual(sum(counts.values()), 192)
        self.assertEqual(52 / 192, 0.2708333333333333)
        self.assertEqual(135 / 192, 0.703125)


if __name__ == "__main__":
    unittest.main()
