#!/usr/bin/env python3
"""Focused deterministic regressions for the v2 layered shadow contracts."""

from __future__ import annotations

import copy
import unittest

from automation.implement_phase9_v2_layered_prediction_evaluation_repair_v0 import (
    _base_payload, _candles, _historical_compatibility, _member,
)
from automation.v2_layered_prediction_evaluation_v0 import (
    EVALUATION_HEADERS, OUTCOME_HEADERS, PATH_HEADERS, PREDICTION_HEADERS, SCHEMA_VERSION,
    V2ValidationError, construct_outcomes, evaluate_prediction, fingerprint,
    normalize_session_members, parse_provider_prediction, release_clusters, schema_dictionary,
)


class LayeredV2Test(unittest.TestCase):
    def setUp(self) -> None:
        self.session = {
            "session_id": "US|2031-02-01|CUSTOM_CONFIG_WINDOW",
            "session_date": "2031-02-01", "session_window_name": "CUSTOM_CONFIG_WINDOW", "fx_pair": "USDJPY",
        }
        self.members = [
            _member("evt-a", "CPI", "2031-02-01T13:30:00Z", "US|2031-02-01T13:30:00Z"),
            _member("evt-b", "ISM", "2031-02-01T15:00:00Z", "US|2031-02-01T15:00:00Z"),
        ]
        self.payload = _base_payload(self.session, self.members, "distinct")

    def parse(self, payload=None, *, arm="A"):
        return parse_provider_prediction(
            payload or self.payload, session=self.session, members=self.members,
            provider="FixtureProvider", model="fixture-model", pack_arm=arm,
            pack_freeze_id="NO_PACK" if arm == "A" else "pack-1",
            pack_fingerprint="" if arm == "A" else fingerprint({"pack": 1}),
            forecast_run_id="fixture-run", forecast_created_ts="2031-01-31T00:00:00Z",
            forecast_cutoff_ts="2031-01-31T00:00:00Z", prompt_version="fixture-v2",
            raw_output="fixture",
        )

    def outcomes(self):
        normalized = normalize_session_members(self.session["session_id"], self.members)
        return construct_outcomes(
            session=self.session, members=self.members,
            candles=_candles(normalized[0]["release_ts"], normalized[-1]["release_ts"]),
            generated_ts="2031-02-02T00:00:00Z",
        )

    def test_schema_headers_and_dictionary_are_complete(self):
        dictionary = schema_dictionary()
        for header, sheet in ((PREDICTION_HEADERS, "v2.0 Prediction"), (PATH_HEADERS, "v2.0 Prediction Path"), (OUTCOME_HEADERS, "v2.0 Outcome"), (EVALUATION_HEADERS, "v2.0 Evaluation")):
            self.assertEqual(len(header), len(set(header)))
            self.assertEqual(len(header), sum(row["sheet_name"] == sheet for row in dictionary))
        self.assertTrue(all(row["schema_version"] == SCHEMA_VERSION for row in dictionary))

    def test_session_identity_and_pack_arm_validation(self):
        bad = dict(self.session)
        bad["session_id"] = ""
        with self.assertRaises(V2ValidationError):
            parse_provider_prediction(self.payload, session=bad, members=self.members, provider="P", model="M", pack_arm="A", pack_freeze_id="NO_PACK", pack_fingerprint="", forecast_run_id="R", forecast_created_ts="2031-01-31T00:00:00Z", forecast_cutoff_ts="2031-01-31T00:00:00Z", prompt_version="V", raw_output="")
        with self.assertRaises(V2ValidationError):
            self.parse(arm="INVALID")

    def test_same_time_clusters_and_distinct_times(self):
        same = [
            _member("evt-a", "CPI", "2031-02-01T13:30:00Z", "US|2031-02-01T13:30:00Z"),
            _member("evt-c", "Claims", "2031-02-01T13:30:00Z", "US|2031-02-01T13:30:00Z"),
        ]
        self.assertEqual(1, len(release_clusters(self.session["session_id"], same)))
        self.assertEqual(2, len(release_clusters(self.session["session_id"], self.members)))

    def test_primary_and_secondary_must_be_session_members(self):
        bad = copy.deepcopy(self.payload)
        bad["primary_driver_event_id"] = "outside"
        with self.assertRaisesRegex(V2ValidationError, "PRIMARY_DRIVER_NOT_IN_SESSION"):
            self.parse(bad)
        bad = copy.deepcopy(self.payload)
        bad["secondary_driver_event_id"] = "outside"
        with self.assertRaisesRegex(V2ValidationError, "SECONDARY_DRIVER"):
            self.parse(bad)

    def test_optional_secondary_driver(self):
        payload = _base_payload(self.session, [self.members[0]], "none")
        prediction, _ = parse_provider_prediction(
            payload, session=self.session, members=[self.members[0]], provider="P", model="M", pack_arm="A",
            pack_freeze_id="NO_PACK", pack_fingerprint="", forecast_run_id="R",
            forecast_created_ts="2031-01-31T00:00:00Z", forecast_cutoff_ts="2031-01-31T00:00:00Z",
            prompt_version="V", raw_output="fixture",
        )
        self.assertEqual("NO_MEANINGFUL_SECONDARY_DRIVER", prediction["secondary_driver_status"])

    def test_primary_secondary_reaction_and_interval_validation(self):
        prediction, _ = self.parse()
        self.assertEqual("RELEASE_CLUSTER", prediction["primary_reaction_target_type"])
        self.assertEqual("PREDICTED", prediction["secondary_reaction_status"])
        bad = copy.deepcopy(self.payload)
        bad["primary_expected_pips_min"], bad["primary_expected_pips_max"] = 20, 2
        with self.assertRaisesRegex(V2ValidationError, "INVALID_PIPS_INTERVAL"):
            self.parse(bad)

    def test_interaction_enum_and_same_cluster_safeguard(self):
        bad = copy.deepcopy(self.payload)
        bad["primary_secondary_interaction"] = "AMPLIFICATION"
        with self.assertRaisesRegex(V2ValidationError, "INVALID_ENUM"):
            self.parse(bad)
        same_members = [
            self.members[0], _member("evt-c", "Claims", "2031-02-01T13:30:00Z", "US|2031-02-01T13:30:00Z"),
        ]
        same_payload = _base_payload(self.session, same_members, "same_cluster")
        prediction, _ = parse_provider_prediction(
            same_payload, session=self.session, members=same_members, provider="P", model="M", pack_arm="A",
            pack_freeze_id="NO_PACK", pack_fingerprint="", forecast_run_id="R", forecast_created_ts="2031-01-31T00:00:00Z",
            forecast_cutoff_ts="2031-01-31T00:00:00Z", prompt_version="V", raw_output="fixture",
        )
        self.assertEqual("NOT_APPLICABLE_SAME_CLUSTER", prediction["interaction_status"])

    def test_path_order_and_fingerprints(self):
        prediction, paths = self.parse()
        self.assertEqual(list(range(1, len(paths) + 1)), [row["path_stage_index"] for row in paths])
        self.assertTrue(all(len(row["stage_fingerprint"]) == 64 for row in paths))
        self.assertEqual(64, len(prediction["prediction_fingerprint"]))
        bad = copy.deepcopy(self.payload)
        bad["prediction_path"][1]["path_stage_index"] = 7
        with self.assertRaisesRegex(V2ValidationError, "PATH_STAGE_ORDER_INVALID"):
            self.parse(bad)

    def test_prediction_outcome_separation_and_preoutcome_status(self):
        prediction, _ = self.parse()
        self.assertEqual("FROZEN_PREOUTCOME", prediction["prediction_status"])
        self.assertFalse({"outcome_id", "realized_pips", "component_result"}.intersection(prediction))
        bad = copy.deepcopy(self.payload)
        bad["realized_pips"] = 12
        with self.assertRaisesRegex(V2ValidationError, "OUTCOME_FIELD_PRESENT"):
            self.parse(bad)

    def test_opening_strictly_before_and_closing_after_horizon(self):
        outcomes = self.outcomes()
        for row in outcomes:
            if row["outcome_status"] != "VALID":
                continue
            self.assertLess(row["opening_price_ts"], row["outcome_window_start_ts"])
            self.assertGreaterEqual(row["closing_price_ts"], row["outcome_window_end_ts"])

    def test_event_cluster_and_session_outcome_semantics(self):
        outcomes = self.outcomes()
        self.assertEqual(2, sum(row["outcome_level"] == "EVENT" for row in outcomes))
        self.assertEqual(2, sum(row["outcome_level"] == "RELEASE_CLUSTER" for row in outcomes))
        self.assertEqual(1, sum(row["outcome_level"] == "MARKET_SESSION" for row in outcomes))
        self.assertTrue(all(not {"provider", "prediction_id", "session_forecast_direction"}.intersection(row) for row in outcomes))

    def test_same_cluster_event_is_not_double_scored(self):
        members = [self.members[0], _member("evt-c", "Claims", "2031-02-01T13:30:00Z", "US|2031-02-01T13:30:00Z")]
        outcomes = construct_outcomes(session=self.session, members=members, candles=_candles("2031-02-01T13:30:00Z", "2031-02-01T13:30:00Z"), generated_ts="2031-02-02T00:00:00Z")
        self.assertEqual(1, sum(row["outcome_level"] == "RELEASE_CLUSTER" and row["outcome_status"] == "VALID" for row in outcomes))
        self.assertEqual(2, sum(row["outcome_rejection_reason"] == "EVENT_OUTCOME_NOT_SEPARABLY_EVALUABLE" for row in outcomes))

    def test_session_direction_magnitude_and_path_evaluation(self):
        prediction, paths = self.parse()
        evaluations = evaluate_prediction(prediction, paths, self.outcomes(), "2031-02-02T00:00:00Z")
        components = {row["evaluation_component"]: row for row in evaluations}
        self.assertIn(components["SESSION_DIRECTION"]["component_result"], {"CORRECT", "INCORRECT"})
        self.assertIn(components["SESSION_MAGNITUDE"]["component_result"], {"CORRECT", "INCORRECT"})
        self.assertIn(components["PATH_DIRECTIONAL_SEQUENCE"]["component_result"], {"CORRECT", "INCORRECT", "NOT_SEPARABLY_EVALUABLE"})
        self.assertIn(components["COMPLETE_PATH_STRICT"]["component_result"], {"CORRECT", "INCORRECT", "NOT_SEPARABLY_EVALUABLE"})

    def test_interaction_and_driver_scoring_fail_closed(self):
        prediction, paths = self.parse()
        evaluations = evaluate_prediction(prediction, paths, self.outcomes(), "2031-02-02T00:00:00Z")
        by_component = {row["evaluation_component"]: row for row in evaluations}
        self.assertEqual("NOT_YET_EVALUABLE", by_component["PRIMARY_DRIVER_CHOICE"]["component_result"])
        self.assertIn(by_component["PRIMARY_SECONDARY_INTERACTION"]["component_result"], {"CORRECT", "INCORRECT"})

    def test_historical_compatibility_never_reruns_or_infers_layers(self):
        rows, counts = _historical_compatibility()
        self.assertGreater(counts["forecasts_reviewed"], 0)
        self.assertGreater(counts["not_predicted_fields"], 0)
        self.assertGreater(counts["parse_unresolved_fields"], 0)
        self.assertTrue(all(row["historical_provider_rerun"] is False for row in rows))

    def test_deterministic_reconstruction(self):
        first_prediction, first_paths = self.parse()
        second_prediction, second_paths = self.parse()
        self.assertEqual(first_prediction["prediction_fingerprint"], second_prediction["prediction_fingerprint"])
        self.assertEqual([row["stage_fingerprint"] for row in first_paths], [row["stage_fingerprint"] for row in second_paths])
        first_outcomes = self.outcomes()
        second_outcomes = self.outcomes()
        self.assertEqual([row["outcome_fingerprint"] for row in first_outcomes], [row["outcome_fingerprint"] for row in second_outcomes])


if __name__ == "__main__":
    unittest.main()
