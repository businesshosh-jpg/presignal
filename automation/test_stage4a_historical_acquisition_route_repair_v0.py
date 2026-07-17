#!/usr/bin/env python3
"""Focused regression tests for the final Stage 4A route repair."""

from __future__ import annotations

import unittest

from automation.repair_phase9_stage4a_historical_acquisition_routes_v0 import (
    _candidate_id,
    _conservative_snapshot,
)
from automation.run_phase9_historical_square_one_replay_v0 import _market_item


def _request(category: str, wording: str, request_id: str = "r1"):
    return {
        "session_id": "US|2025-01-02|CUSTOM_CONFIG_WINDOW",
        "provider": "OpenAI",
        "request_id": request_id,
        "request_identity": "identity_" + request_id,
        "normalized_information_key": category + "|" + request_id,
        "information_category": category,
        "requested_information": wording,
    }


class Stage4AHistoricalAcquisitionRouteRepairTest(unittest.TestCase):
    def setUp(self):
        self.session = {
            "session_id": "US|2025-01-02|CUSTOM_CONFIG_WINDOW",
            "forecast_cutoff": "2025-01-02T13:20:00Z",
        }
        daily = lambda current, prior: {
            "status": "ok",
            "chosen": {"date": "2024-12-31", "value": current},
            "prior": {"date": "2024-12-30", "value": prior},
            "publication_timestamp_policy": "conservative_d_plus_one",
            "same_day_value_used": False,
        }
        window = lambda value: {
            "status": "exact_window",
            "post_forecast_data_used": False,
            "end_candle_ts": "2025-01-02T13:19:00Z",
            "end_price": 157.0,
            "return_pct": 0.1,
            "realized_volatility": value,
        }
        self.snapshot = {
            "daily_snapshots": {
                "us2y": daily(4.2, 4.1), "us5y": daily(4.1, 4.0),
                "us10y": daily(4.3, 4.2), "us30y": daily(4.5, 4.4),
                "sp500": daily(5900.0, 5850.0),
            },
            "usdjpy_windows": {"realized_vol_1h": window(0.001), "return_24h": window(0.004)},
        }

    def test_equity_prior_day_route(self):
        item = _market_item(self.session, [_request("equity_tone", "Recent S&P 500 performance")], self.snapshot)
        self.assertEqual(item["status"], "SUPPLIED_COMPUTED")
        self.assertEqual(item["source_identity"], "FRED:SP500")

    def test_equity_futures_request_fails_closed(self):
        item = _market_item(self.session, [_request("equity_tone", "S&P 500 futures tone")], self.snapshot)
        self.assertEqual(item["status"], "NOT_AVAILABLE")
        self.assertIn("DOES_NOT_PROVE", item["reason"])

    def test_full_curve_route(self):
        item = _market_item(self.session, [_request("treasury_yields", "US Treasury yields across the curve")], self.snapshot)
        self.assertEqual(item["status"], "SUPPLIED_DETERMINISTIC")
        self.assertEqual(set(item["value"]), {
            "us2y_yield_level", "us5y_yield_level", "us10y_yield_level",
            "us30y_yield_level", "us10y_minus_us2y_curve", "us30y_minus_us5y_curve",
        })

    def test_auction_results_request_fails_closed(self):
        item = _market_item(self.session, [_request("treasury_yields", "30Y auction result and bid-to-cover")], self.snapshot)
        self.assertEqual(item["status"], "NOT_AVAILABLE")
        self.assertIn("AUCTION_RESULT_DETAIL", item["reason"])

    def test_option_iv_request_is_explicitly_unavailable(self):
        item = _market_item(self.session, [_request("volatility", "USDJPY 1-week implied volatility")], self.snapshot)
        self.assertEqual(item["reason"], "NO_APPROVED_HISTORICAL_USDJPY_OPTION_IV_SOURCE")

    def test_realized_volatility_uses_existing_windows(self):
        item = _market_item(self.session, [_request("volatility", "Recent volatility measures for USDJPY")], self.snapshot)
        self.assertEqual(item["status"], "SUPPLIED_COMPUTED")
        self.assertEqual(item["value"]["usdjpy_realized_volatility_24h"], 0.004)

    def test_conservative_cutoff_rejects_same_day_daily_value(self):
        snapshot = _conservative_snapshot(
            [{"date": "2024-12-31", "value": 1.0}, {"date": "2025-01-02", "value": 2.0}],
            self.session["forecast_cutoff"],
        )
        self.assertEqual(snapshot["chosen"]["date"], "2024-12-31")

    def test_candidate_identity_is_deterministic(self):
        request = _request("equity_tone", "Recent S&P 500 performance")
        self.assertEqual(_candidate_id(request, "EQUITY_PRESESSION_TONE"), _candidate_id(request, "EQUITY_PRESESSION_TONE"))


if __name__ == "__main__":
    unittest.main()
