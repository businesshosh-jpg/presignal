#!/usr/bin/env python3
"""Focused release tests for canonical native-v2 typed provider output."""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from automation import run_phase9_authoritative_historical_replay_v0 as executor
from automation.native_v2_typed_schema_v0 import (
    PRIMARY_REACTION_BINDING_FIELD,
    SECONDARY_REACTION_TRANSPORT_FIELD,
    adapter_schema,
    canonical_schema,
    canonical_schema_fingerprint,
    decode_primary_reaction_transport,
    primary_reaction_binding_set,
    transport_adapter_schema,
    validator_approved_primary_reaction_combinations,
    validate_canonical_payload,
)


PACKAGE = Path(__file__).resolve().parents[1] / "outputs" / "phase9_authoritative_historical_replay" / "9-AUTHORITATIVE-HISTORICAL-REPLAY-20260717T094156Z"


class NativeV2TypedSchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # The package is deliberately bound only after the source-level checks
        # in this test suite; none of these tests dispatches a provider.
        cls.state = executor.PackageState(PACKAGE, strict_authoritative=False)
        cls.entry = cls.state.population[0]

    def payload(self, path_len: int = 2):
        return executor._make_valid_payload(self.state, self.entry, path_len=path_len)

    def assert_invalid(self, payload, marker: str) -> None:
        with self.assertRaisesRegex(ValueError, marker):
            validate_canonical_payload(payload)

    def test_canonical_schema_is_single_strict_machine_readable_object(self) -> None:
        schema = canonical_schema()
        self.assertEqual(schema["$id"], "presignal_native_v2_prediction_typed_output_v1")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(len(schema["required"]), len(schema["properties"]))
        self.assertNotIn("anyOf", schema)
        self.assertNotIn("allOf", schema)
        self.assertEqual(len(canonical_schema_fingerprint()), 64)

        def assert_closed_objects(node):
            if isinstance(node, dict):
                if node.get("type") == "object":
                    self.assertIs(node.get("additionalProperties"), False)
                for value in node.values():
                    assert_closed_objects(value)
            elif isinstance(node, list):
                for value in node:
                    assert_closed_objects(value)
        assert_closed_objects(adapter_schema("OpenAI"))

    def test_scalar_enums_and_required_fields_fail_closed(self) -> None:
        valid = self.payload()
        validate_canonical_payload(valid)
        array_enum = copy.deepcopy(valid)
        array_enum["session_forecast_direction"] = ["UP"]
        self.assert_invalid(array_enum, "TYPE")
        blank_enum = copy.deepcopy(valid)
        blank_enum["session_forecast_direction"] = ""
        self.assert_invalid(blank_enum, "ENUM")
        unknown_enum = copy.deepcopy(valid)
        unknown_enum["session_forecast_direction"] = "SIDEWAYS"
        self.assert_invalid(unknown_enum, "ENUM")
        invalid_secondary_target = copy.deepcopy(valid)
        invalid_secondary_target["secondary_reaction_target_type"] = "single"
        self.assert_invalid(invalid_secondary_target, "ANY_OF")
        missing = copy.deepcopy(valid)
        del missing["secondary_reaction_status"]
        self.assert_invalid(missing, "REQUIRED")
        unknown = copy.deepcopy(valid)
        unknown["legacy_prediction"] = "not allowed"
        self.assert_invalid(unknown, "ADDITIONAL_PROPERTY")

    def test_path_cardinality_and_stage_objects_are_typed(self) -> None:
        for path_len in (2, 3, 4):
            validate_canonical_payload(self.payload(path_len))
        for path_len in (0, 1, 5):
            self.assert_invalid(self.payload(path_len), "ITEMS")
        malformed = self.payload()
        del malformed["prediction_path"][0]["stage_explanation"]
        self.assert_invalid(malformed, "REQUIRED")

    def test_envelope_and_cross_field_rules_remain_fail_closed(self) -> None:
        raw = json.dumps(self.payload())
        response = executor._fixture_response(self.payload(), self.entry)
        prediction, paths, errors = executor._parse_response(self.state, self.entry, raw, response)
        self.assertTrue(prediction, errors)
        self.assertTrue(paths)
        for malformed in ({"prediction": self.payload()}, {"forecast": self.payload()}):
            prediction, _, errors = executor._parse_response(
                self.state, self.entry, json.dumps(malformed), response
            )
            self.assertFalse(prediction)
            self.assertTrue(any("LEGACY_OR_NESTED" in error for error in errors))
        prose = executor._fixture_response(self.payload(), self.entry)
        prediction, _, errors = executor._parse_response(self.state, self.entry, "```json\n" + raw + "\n```", prose)
        self.assertFalse(prediction)
        self.assertTrue(errors)

    def test_same_cluster_secondary_conditional_rule(self) -> None:
        members = self.state.members_by_session[self.entry["session_id"]]
        primary_id = self.payload()["primary_driver_event_id"]
        primary = next(row for row in members if row["event_id"] == primary_id)
        secondary = next(
            row for row in members
            if row["event_id"] != primary_id and row.get("release_ts") == primary.get("release_ts")
        )
        valid = self.payload()
        valid.update({
            "secondary_driver_status": "SELECTED",
            "secondary_driver_event_id": secondary["event_id"],
            "secondary_driver_choice_confidence": 0.5,
            "secondary_driver_reason": "Fixture same-cluster secondary driver.",
            "secondary_reaction_status": "SAME_CLUSTER_NOT_SEPARATELY_PREDICTABLE",
            "interaction_status": "NOT_APPLICABLE_SAME_CLUSTER",
            "primary_secondary_interaction": "NOT_APPLICABLE",
        })
        response = executor._fixture_response(valid, self.entry)
        prediction, paths, errors = executor._parse_response(self.state, self.entry, json.dumps(valid), response)
        self.assertTrue(prediction, errors)
        self.assertTrue(paths)
        invalid = copy.deepcopy(valid)
        invalid["secondary_reaction_status"] = "PREDICTED"
        prediction, _, errors = executor._parse_response(self.state, self.entry, json.dumps(invalid), response)
        self.assertFalse(prediction)
        self.assertTrue(any("INTERACTION" in error or "SECONDARY" in error for error in errors))
        self.assertTrue(any("SAME_CLUSTER_SECONDARY" in error for error in errors))

        invalid_no_secondary = self.payload()
        invalid_no_secondary["interaction_status"] = "PREDICTED"
        prediction, _, errors = executor._parse_response(self.state, self.entry, json.dumps(invalid_no_secondary), response)
        self.assertFalse(prediction)
        self.assertTrue(any("INTERACTION_STATUS_INCONSISTENT" in error for error in errors))
        non_session = self.payload()
        non_session["primary_driver_event_id"] = "NOT_A_SESSION_MEMBER"
        prediction, _, errors = executor._parse_response(self.state, self.entry, json.dumps(non_session), response)
        self.assertFalse(prediction)
        self.assertTrue(errors)
        incompatible = self.payload()
        incompatible["primary_reaction_target_type"] = "EVENT"
        prediction, _, errors = executor._parse_response(self.state, self.entry, json.dumps(incompatible), response)
        self.assertFalse(prediction)
        self.assertTrue(errors)

    def test_provider_adapters_are_deterministic_and_cannot_weaken_shape(self) -> None:
        canonical = canonical_schema()
        for provider in ("OpenAI", "Gemini", "Anthropic"):
            adapter = adapter_schema(provider)
            self.assertNotIn("$id", adapter)
            if provider == "Gemini":
                self.assertNotIn("additionalProperties", adapter)
            else:
                self.assertFalse(adapter["additionalProperties"])
            self.assertEqual(adapter["required"], canonical["required"])
            self.assertEqual(adapter["properties"]["prediction_path"]["minItems"], 2)
            self.assertEqual(adapter["properties"]["prediction_path"]["maxItems"], 4)
            self.assertEqual(
                adapter["properties"]["session_forecast_direction"]["enum"],
                canonical["properties"]["session_forecast_direction"]["enum"],
            )
            path_item = adapter["properties"]["prediction_path"]["items"]
            if provider == "Gemini":
                self.assertNotIn("enum", path_item["properties"]["path_stage_index"])
            else:
                self.assertEqual(path_item["properties"]["path_stage_index"]["enum"], [1, 2, 3, 4])
        self.assertEqual(adapter_schema("Gemini")["type"], "OBJECT")
        self.assertEqual(adapter_schema("OpenAI")["type"], "object")

    def test_primary_reaction_binding_equals_frozen_validator_choices_and_decodes_exactly(self) -> None:
        session_id = self.entry["session_id"]
        members = self.state.members_by_session[session_id]
        approved = validator_approved_primary_reaction_combinations(session_id, members)
        bindings = primary_reaction_binding_set(session_id, members)
        self.assertEqual(
            {(row["driver_event_id"], row["reaction_target_type"], row["reaction_target_id"]) for row in bindings},
            {(row["driver_event_id"], row["reaction_target_type"], row["reaction_target_id"]) for row in approved},
        )
        self.assertEqual(bindings, primary_reaction_binding_set(session_id, members))
        self.assertEqual(len({row["binding"] for row in bindings}), len(bindings))
        clustered = next(row for row in bindings if row["reaction_target_type"] == "RELEASE_CLUSTER")
        for row in bindings:
            if row["driver_event_id"] == clustered["driver_event_id"]:
                member = next(item for item in members if item["event_id"] == row["driver_event_id"])
                cluster_size = sum(1 for item in members if item.get("release_ts") == member.get("release_ts"))
                if cluster_size > 1:
                    self.assertNotEqual(row["reaction_target_type"], "EVENT")
        transport = self.payload()
        for field in ("primary_driver_event_id", "primary_reaction_target_type", "primary_reaction_target_id"):
            transport.pop(field)
        for field in (
            "secondary_reaction_status", "secondary_reaction_target_type",
            "secondary_reaction_target_id", "secondary_reaction_direction",
            "secondary_expected_pips_min", "secondary_expected_pips_max",
            "secondary_reaction_horizon_min", "secondary_reaction_confidence",
            "secondary_reaction_thesis",
        ):
            transport.pop(field)
        transport[PRIMARY_REACTION_BINDING_FIELD] = bindings[0]["binding"]
        transport[SECONDARY_REACTION_TRANSPORT_FIELD] = {"status": "NO_MEANINGFUL_SECONDARY_DRIVER"}
        decoded = decode_primary_reaction_transport(transport, session_id, members)
        self.assertEqual(decoded["primary_driver_event_id"], bindings[0]["driver_event_id"])
        self.assertEqual(decoded["primary_reaction_target_type"], bindings[0]["reaction_target_type"])
        self.assertEqual(decoded["primary_reaction_target_id"], bindings[0]["reaction_target_id"])
        bad = copy.deepcopy(transport)
        bad[PRIMARY_REACTION_BINDING_FIELD] = "pb1:not-a-binding"
        with self.assertRaisesRegex(ValueError, "(BINDING|ENUM)"):
            decode_primary_reaction_transport(bad, session_id, members)
        for provider in ("OpenAI", "Gemini", "Anthropic"):
            schema = transport_adapter_schema(provider, session_id, members)
            prop = schema["properties"][PRIMARY_REACTION_BINDING_FIELD]
            self.assertEqual(set(prop["enum"]), {row["binding"] for row in bindings})
            self.assertNotIn("primary_driver_event_id", schema["properties"])

    def test_secondary_reaction_transport_branches_are_exact_and_decode_without_repair(self) -> None:
        session_id = self.entry["session_id"]
        members = self.state.members_by_session[session_id]
        bindings = primary_reaction_binding_set(session_id, members)
        base = self.payload()
        for field in (
            "primary_driver_event_id", "primary_reaction_target_type", "primary_reaction_target_id",
            "secondary_reaction_status", "secondary_reaction_target_type",
            "secondary_reaction_target_id", "secondary_reaction_direction",
            "secondary_expected_pips_min", "secondary_expected_pips_max",
            "secondary_reaction_horizon_min", "secondary_reaction_confidence",
            "secondary_reaction_thesis",
        ):
            base.pop(field)
        base[PRIMARY_REACTION_BINDING_FIELD] = bindings[0]["binding"]
        base[SECONDARY_REACTION_TRANSPORT_FIELD] = {"status": "NOT_PREDICTED"}
        decoded = decode_primary_reaction_transport(base, session_id, members)
        self.assertEqual(decoded["secondary_reaction_status"], "NOT_PREDICTED")
        self.assertEqual(decoded["secondary_reaction_horizon_min"], "")
        self.assertNotIn(SECONDARY_REACTION_TRANSPORT_FIELD, decoded)
        invalid = copy.deepcopy(base)
        invalid[SECONDARY_REACTION_TRANSPORT_FIELD]["horizon_min"] = 0
        with self.assertRaisesRegex(ValueError, "SECONDARY|ADDITIONAL|ANY_OF"):
            decode_primary_reaction_transport(invalid, session_id, members)
        predicted = copy.deepcopy(base)
        predicted[SECONDARY_REACTION_TRANSPORT_FIELD] = {
            "status": "PREDICTED", "target_type": "EVENT", "target_id": members[1]["event_id"],
            "direction": "DOWN", "expected_pips_min": 1, "expected_pips_max": 2,
            "horizon_min": 30, "confidence": 0.5, "thesis": "Secondary reaction fixture.",
        }
        decoded_predicted = decode_primary_reaction_transport(predicted, session_id, members)
        self.assertEqual(decoded_predicted["secondary_reaction_horizon_min"], 30)
        missing = copy.deepcopy(predicted)
        missing[SECONDARY_REACTION_TRANSPORT_FIELD].pop("horizon_min")
        with self.assertRaisesRegex(ValueError, "ANY_OF|REQUIRED"):
            decode_primary_reaction_transport(missing, session_id, members)
        for provider in ("OpenAI", "Gemini", "Anthropic"):
            schema = transport_adapter_schema(provider, session_id, members)
            self.assertIn(SECONDARY_REACTION_TRANSPORT_FIELD, schema["properties"])
            self.assertNotIn("secondary_reaction_horizon_min", schema["properties"])

    def test_archived_responses_remain_negative_regression_evidence(self) -> None:
        archived = executor._rows(self.state.responses_path)[:312]
        accepted = 0
        for row in archived:
            stored = json.loads(Path(row["response_reference"]).read_text())["response"]
            entry = self.state.population_by_id[row["forecast_identity"]]
            prediction, paths, _ = executor._parse_response(
                self.state, entry, str(stored.get("raw_output") or ""), stored
            )
            if prediction and paths:
                accepted += 1
        self.assertEqual(len(archived), 312)
        self.assertEqual(accepted, 0)

    def test_canary_implementation_is_fail_fast(self) -> None:
        source = Path(executor.__file__).read_text()
        start = source.index("def execute_compatibility_canary(")
        body = source[start:source.index("\ndef recover_incomplete_reservations", start)]
        self.assertIn("for entry in typed_entries", body)
        self.assertIn("terminal_status", body)
        self.assertIn("SINGLE_RETRYABLE", body)
        self.assertNotIn("limit=6, entries=typed_entries", body)


if __name__ == "__main__":
    unittest.main()
