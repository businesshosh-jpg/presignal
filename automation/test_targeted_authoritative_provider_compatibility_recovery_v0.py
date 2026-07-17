#!/usr/bin/env python3
"""Focused offline release checks for the paused authoritative replay recovery."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from automation import run_phase9_authoritative_historical_replay_v0 as executor
from automation import run_phase9_historical_square_one_replay_v0 as square_one
from automation import run_phase9_prospective_a_vs_e_pipeline_v0 as prospective
from automation.apply_authoritative_replay_provider_compatibility_recovery_v0 import ledger_lineage_312_to_333, recovery_prompt_fingerprint
from automation.native_v2_typed_schema_v0 import (
    PRIMARY_REACTION_BINDING_FIELD, SECONDARY_REACTION_TRANSPORT_FIELD,
    canonical_schema_fingerprint,
)


PACKAGE = Path(__file__).resolve().parents[1] / "outputs" / "phase9_authoritative_historical_replay" / "9-AUTHORITATIVE-HISTORICAL-REPLAY-20260717T094156Z"


class TargetedAuthoritativeProviderCompatibilityRecoveryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.state = executor.PackageState(PACKAGE, strict_authoritative=False)

    def test_prompt_binds_the_single_native_v2_typed_contract(self) -> None:
        entry = self.state.population[0]
        session = self.state.sessions[entry["session_id"]]
        members = self.state.members_by_session[entry["session_id"]]
        prompt = prospective._forecast_prompt(
            session, members,
            {"pack_selected": "NO_PACK", "pack_item_count": 0, "pack_e_exposure": False, "items": []},
            entry["provider"], entry["model"],
        )
        contract = json.loads(prompt["user"])
        self.assertEqual(contract["native_v2_schema_fingerprint"], canonical_schema_fingerprint())
        self.assertNotIn("output_contract", contract)
        self.assertEqual(len(contract["native_v2_target_binding_table"]), len(members))
        self.assertTrue(all(row["driver_event_id"] == row["event_target_id"] for row in contract["native_v2_target_binding_table"]))
        self.assertIn("typed schema", prompt["instruction"])
        self.assertIn("SAME_CLUSTER_NOT_SEPARATELY_PREDICTABLE", prompt["instruction"])
        self.assertIn("REACTION_TARGET_REQUIREMENT", prompt["user"].upper())
        self.assertIn("RELEASE_CLUSTER_REQUIRED", prompt["instruction"])

    def test_recovery_prompt_binding_includes_renderer_source_bytes(self) -> None:
        recovery_source = (Path(__file__).resolve().parents[1] / "automation" / "apply_authoritative_replay_provider_compatibility_recovery_v0.py").read_text()
        renderer = Path(__file__).resolve().parents[1] / "automation" / "run_phase9_authoritative_historical_replay_v0.py"
        self.assertIn('"sha256": file_sha(prompt_renderer)', recovery_source)
        self.assertEqual(len(recovery_prompt_fingerprint()), 64)
        self.assertIn("primary_reaction_binding_transport", renderer.read_text())

    def test_executor_prompt_and_bridge_bind_the_session_specific_scalar_enum(self) -> None:
        entry = self.state.population[0]
        prompt = executor._prompt_for_entry(self.state, entry)
        transport = json.loads(prompt["user"])["native_v2_primary_reaction_binding_transport"]
        self.assertEqual(transport["field"], PRIMARY_REACTION_BINDING_FIELD)
        self.assertTrue(transport["choices"])
        bridge = executor._bridge_payload(self.state, entry, prompt, 300)
        schema = bridge["structured_output"]["canonical_schema"]
        self.assertEqual(schema["properties"][PRIMARY_REACTION_BINDING_FIELD]["enum"], transport["choices"])
        self.assertNotIn("primary_driver_event_id", schema["properties"])
        self.assertIn(SECONDARY_REACTION_TRANSPORT_FIELD, schema["properties"])
        self.assertNotIn("secondary_reaction_horizon_min", schema["properties"])
        self.assertIn("secondary_reaction", bridge["structured_output"])

    def test_post_312_ledger_lineage_is_complete(self) -> None:
        lineage = json.loads((PACKAGE / "execution" / "ledger_lineage_312_to_333.json").read_text())
        self.assertEqual(lineage["increase"], 21)
        self.assertTrue(lineage["all_records_reconciled"])
        self.assertEqual([row["invocation_number"] for row in lineage["records"]], list(range(313, 334)))
        self.assertTrue(all(row["provider_endpoint_attempted"] for row in lineage["records"]))

    def test_duplicate_event_repair_is_four_row_deterministic_and_referentially_closed(self) -> None:
        correction = json.loads((PACKAGE / "execution" / "targeted_event_identity_correction.json").read_text())
        report = correction["report"]
        self.assertEqual(report["eligible_sessions"], 239)
        self.assertEqual(report["members_before"], report["members_after"])
        self.assertEqual(len(report["affected_rows"]), 4)
        self.assertEqual(len({row["new_event_id"] for row in report["affected_rows"]}), 4)
        self.assertEqual(report["unique_event_ids_after"], report["members_after"])

    def test_complete_native_v2_payload_passes_and_invalid_path_lengths_fail(self) -> None:
        entry = self.state.population[0]
        for path_len, expected_error in ((2, None), (1, "PREDICTION_PATH"), (5, "PREDICTION_PATH")):
            response = executor._fixture_response(executor._make_valid_payload(self.state, entry, path_len=path_len), entry)
            prediction, paths, errors = executor._parse_response(self.state, entry, response["raw_output"], response)
            if expected_error is None:
                self.assertTrue(prediction)
                self.assertEqual(len(paths), 2)
            else:
                self.assertFalse(prediction)
                self.assertTrue(errors)

    def test_archived_gemini_legacy_and_anthropic_truncation_remain_invalid(self) -> None:
        response_rows = executor._rows(self.state.responses_path)
        by_provider = {}
        for row in response_rows:
            by_provider.setdefault(row["provider"], row)
        gemini = json.loads(Path(by_provider["Gemini"]["response_reference"]).read_text())["response"]
        anth = json.loads(Path(by_provider["Anthropic"]["response_reference"]).read_text())["response"]
        self.assertIn("prediction", str(gemini.get("raw_output") or ""))
        with self.assertRaises(json.JSONDecodeError):
            json.loads(str(anth.get("raw_output") or ""))
        self.assertEqual(anth.get("completion_tokens"), 2048)

    def test_route_repair_keeps_exact_frozen_model_and_mismatch_fails_closed(self) -> None:
        bridge = (Path(__file__).resolve().parents[1] / "apps_script" / "authoritative_provider_bridge.js").read_text()
        self.assertIn("prov.model = requestedModel", bridge)
        self.assertNotIn("configured_model_does_not_match_frozen_model", bridge)
        entry = next(row for row in self.state.population if row["provider"] == "OpenAI")
        payload = executor._bridge_payload(self.state, entry, {}, 300)
        self.assertEqual(payload["model"], "gpt-4o-mini-2024-07-18")
        mismatched = executor._fixture_response(executor._make_valid_payload(self.state, entry), entry, model="gpt-4o-mini")
        _, _, errors = executor._parse_response(self.state, entry, mismatched["raw_output"], mismatched)
        self.assertTrue(any("PROVIDER_EXECUTION_METADATA_MISMATCH:actual_model" in error for error in errors))

    def test_anthropic_cap_and_telemetry_contract(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "apps_script" / "automation_api.js").read_text()
        self.assertIn("max_tokens: 4096", source)
        self.assertIn("stop_reason: j.stop_reason || null", source)
        bridge = (Path(__file__).resolve().parents[1] / "apps_script" / "authoritative_provider_bridge.js").read_text()
        self.assertIn("stop_reason: response.stop_reason || null", bridge)

    def test_pre_dispatch_openai_records_are_preserved_but_recovery_eligible_once(self) -> None:
        eligible = executor._recovery_eligible_identities(self.state)
        self.assertEqual(len(eligible), 102)
        entry = self.state.population_by_id[next(iter(eligible))]
        self.assertNotIn(entry["forecast_identity"], executor._terminal_by_identity(self.state))
        self.assertEqual(executor._next_attempt_plan(self.state, entry), (2, "recovery_retry"))


if __name__ == "__main__":
    unittest.main()
