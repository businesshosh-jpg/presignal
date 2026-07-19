#!/usr/bin/env python3
"""Tests for deterministic v2.1 Episode roles and Outcome construction."""
from __future__ import annotations

import copy
import unittest
from datetime import datetime, timedelta, timezone

from automation import build_presignal_v21_episode_outcomes as outcomes
from automation import build_presignal_v21_episodes as episodes
from automation import presignal_v21_event_path_contract_v1 as contract


def member(event_id, indicator, importance="medium"):
    row = {"event_id": event_id, "batch_id": "B", "country": "US", "indicator_name": indicator, "release_ts": "2024-05-01T07:30:00Z", "source_cal": "FMP", "source_provider": "FMP", "source_series_id": "", "type": "member"}
    row["event_row_locator"] = contract.event_record_locator(row)
    row["importance"] = importance
    return row


def episode_for(*members):
    return episodes.episode_for(list(members))


def observation(timestamp, close):
    return {"timestamp": timestamp, "close": close, "provider": "tiingo", "request_id": "test", "provider_returned_timestamp_raw": timestamp, "accepted_raw_price_field": "close"}


class EpisodeOutcomeTests(unittest.TestCase):
    def test_roles_are_pre_release_importance_then_canonical_order(self):
        low, high_a, high_b = member("low", "Low", "low"), member("high-a", "High A", "high"), member("high-b", "High B", "high")
        cluster = episode_for(low, high_b, high_a)
        consumed = [{"event_row_locator": item["event_row_locator"], "episode_id": cluster["episode_id"], "disposition": "CONSUMED"} for item in (low, high_a, high_b)]
        assigned, ledger = outcomes.assign_component_roles([cluster], consumed, {item["event_row_locator"]: item for item in (low, high_a, high_b)})
        primary = min((high_a, high_b), key=lambda item: (item["release_ts"], item["event_row_locator"], item["indicator_name"], item["event_id"]))
        self.assertEqual(assigned[0]["primary_event_id"], primary["event_id"])
        self.assertEqual(len(assigned[0]["secondary_event_ids"]), 1)
        self.assertEqual({item["component_role"] for item in ledger}, {"PRIMARY_COMPONENT", "SECONDARY_COMPONENT", "SUPPORTING_COMPONENT"})

    def test_standalone_member_is_always_primary(self):
        record = member("sole", "Sole", "low")
        single = episode_for(record)
        consumed = [{"event_row_locator": record["event_row_locator"], "episode_id": single["episode_id"], "disposition": "CONSUMED"}]
        assigned, ledger = outcomes.assign_component_roles([single], consumed, {record["event_row_locator"]: record})
        self.assertEqual(assigned[0]["primary_event_id"], "sole")
        self.assertEqual(assigned[0]["secondary_event_ids"], [])
        self.assertEqual(ledger[0]["component_role"], "PRIMARY_COMPONENT")

    def test_midnight_anchor_requires_previous_utc_day(self):
        record = member("midnight", "Midnight")
        record["release_ts"] = "2024-05-02T00:00:00Z"
        record["event_row_locator"] = contract.event_record_locator(record)
        single = episode_for(record)
        windows = outcomes.required_windows([single])
        self.assertIn(datetime(2024, 5, 1, tzinfo=timezone.utc).date(), windows)
        self.assertIn(datetime(2024, 5, 2, tzinfo=timezone.utc).date(), windows)

    def test_pips_directions_reversal_and_excursion_reconstruct(self):
        record = member("event", "Event")
        single = episodes.episode_for([record])
        observations = [
            observation("2024-05-01T07:30:00Z", 150.00),
            observation("2024-05-01T07:35:00Z", 150.02),
            observation("2024-05-01T07:45:00Z", 150.03),
            observation("2024-05-01T08:00:00Z", 149.98),
            observation("2024-05-01T08:30:00Z", 149.97),
        ]
        result, disposition = outcomes.outcome_record(single, observations, {}, False, "2024-05-01T09:00:00Z")
        self.assertEqual(disposition, "AVAILABLE")
        self.assertEqual([result[f"direction_{h}m"] for h in outcomes.HORIZONS], ["UP", "UP", "DOWN", "DOWN"])
        self.assertEqual(result["pips_5m"], 2.0)
        self.assertEqual(result["max_up_pips"], 3.0)
        self.assertEqual(result["max_down_pips"], -3.0)
        self.assertTrue(result["reversal_flag"])
        self.assertEqual(result["reversal_ts"], "2024-05-01T08:00:00Z")
        contract.validate_outcome(result)

    def test_flat_boundaries_and_missing_or_stale_prices_fail_closed(self):
        record = member("event", "Event")
        single = episodes.episode_for([record])
        exact_up = [observation("2024-05-01T07:30:00Z", 150.00), *[observation((datetime(2024, 5, 1, 7, 30, tzinfo=timezone.utc) + timedelta(minutes=h)).isoformat().replace("+00:00", "Z"), 150.01) for h in outcomes.HORIZONS]]
        valid, _ = outcomes.outcome_record(single, exact_up, {}, False, "2024-05-01T09:00:00Z")
        self.assertEqual(valid["direction_5m"], "UP")
        self.assertEqual(contract.direction_for_pips(-1.0), "DOWN")
        self.assertEqual(contract.direction_for_pips(0.99), "FLAT")
        unavailable, status = outcomes.outcome_record(single, [observation("2024-05-01T07:28:59Z", 150.00)], {}, False, "2024-05-01T09:00:00Z")
        self.assertEqual(status, "UNAVAILABLE")
        self.assertEqual(unavailable["status"], "UNAVAILABLE")
        contract.validate_outcome(unavailable)

    def test_intervening_episode_boundaries(self):
        base = member("one", "One")
        first = episodes.episode_for([base])
        second = copy.deepcopy(first); second["episode_id"] = "EP_EVENT_SECOND"; second["release_ts"] = "2024-05-01T08:30:00Z"
        third = copy.deepcopy(first); third["episode_id"] = "EP_EVENT_THIRD"; third["release_ts"] = "2024-05-01T08:31:00Z"
        flags = outcomes.intervening_flags([first, second, third])
        self.assertTrue(flags[first["episode_id"]])
        self.assertTrue(flags[second["episode_id"]])
        self.assertFalse(flags[third["episode_id"]])

    def test_shuffled_episode_order_has_stable_outcomes(self):
        early_record = member("early", "Early")
        late_record = member("late", "Late")
        late_record["release_ts"] = "2024-05-01T09:00:00Z"
        late_record["event_row_locator"] = contract.event_record_locator(late_record)
        early, late = episode_for(early_record), episode_for(late_record)
        observations = [
            observation("2024-05-01T07:30:00Z", 150.00), observation("2024-05-01T07:35:00Z", 150.01),
            observation("2024-05-01T07:45:00Z", 150.01), observation("2024-05-01T08:00:00Z", 150.01),
            observation("2024-05-01T08:30:00Z", 150.01), observation("2024-05-01T09:00:00Z", 151.00),
            observation("2024-05-01T09:05:00Z", 150.99), observation("2024-05-01T09:15:00Z", 150.99),
            observation("2024-05-01T09:30:00Z", 150.99), observation("2024-05-01T10:00:00Z", 150.99),
        ]
        first, _, _ = outcomes.build_outcomes([early, late], observations, {}, "2024-05-01T11:00:00Z")
        second, _, _ = outcomes.build_outcomes([late, early], observations, {}, "2024-05-01T11:00:00Z")
        self.assertEqual(outcomes.fingerprint(first), outcomes.fingerprint(second))

    def test_current_population_has_one_role_per_consumed_event(self):
        population, dispositions = outcomes.load_episode_population(outcomes.SOURCE)
        assigned, ledger = outcomes.assign_component_roles(population, dispositions, outcomes.consumed_event_records(outcomes.SOURCE))
        self.assertEqual(len(assigned), 1682)
        self.assertEqual(len(ledger), 4314)
        self.assertEqual(sum(item["component_role"] == "PRIMARY_COMPONENT" for item in ledger), 1682)
        self.assertEqual(len({item["event_row_locator"] for item in ledger}), 4314)


if __name__ == "__main__":
    unittest.main()
