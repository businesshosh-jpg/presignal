#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automation import prepare_presignal_v21_historical_baseline_prevalidation_v1_1 as prevalidation
from automation import presignal_v21_event_path_contract_v1_1 as contract
from automation import run_presignal_v21_single_event_path_pair_v1_1 as step6
from automation.test_run_presignal_v21_single_event_path_pair_v1_1 import input_row, response


class PopulationAdmissionTests(unittest.TestCase):
    def test_option_c_population_reconciliation_is_complete(self) -> None:
        rows, summary = prevalidation.build_population_admission_rows()
        self.assertEqual(len(rows), 462)
        self.assertEqual(summary["eligible_episodes"], 374)
        self.assertEqual(summary["excluded_episodes"], 88)
        self.assertEqual(summary["by_population_status"]["ELIGIBLE"], 374)
        self.assertEqual(summary["by_population_status"]["EXCLUDED_LINEAGE_UNSAFE"], 73)
        self.assertEqual(summary["by_population_status"]["EXCLUDED_OUTCOME_UNAVAILABLE"], 15)
        self.assertEqual(summary["attention_metadata"]["ATTENTION_LINEAGE_MISSING"], 341)
        self.assertEqual(summary["attention_metadata"]["ATTENTION_LINEAGE_AVAILABLE"], 48)
        for episode_id in prevalidation.VALIDATION_EPISODES:
            self.assertEqual(summary["validation_candidates"][episode_id]["population_status"], "ELIGIBLE")

    def test_missing_attention_is_metadata_not_exclusion_under_option_c(self) -> None:
        rows, _ = prevalidation.build_population_admission_rows()
        target = next(row for row in rows if row["historical_attention_status"] == "ATTENTION_LINEAGE_MISSING" and row["population_status"] == "ELIGIBLE")
        self.assertEqual(target["population_status"], "ELIGIBLE")


class OutcomeConversionTests(unittest.TestCase):
    @staticmethod
    def legacy_outcome(episode_id: str) -> dict:
        path = prevalidation.LEGACY_OUTCOMES
        return next(json.loads(line) for line in path.read_text().splitlines() if line.strip() and json.loads(line)["episode_id"] == episode_id)

    def test_validation_episode_converts_to_v1_1_approximation_only(self) -> None:
        converted = prevalidation.convert_legacy_outcome(
            self.legacy_outcome("EP_BATCH_6fb320e5e8c5931f2373"),
            acquisition_ts="2026-07-26T00:00:00Z",
        )
        self.assertEqual(converted["schema_version"], "2.1.1")
        self.assertEqual(converted["immediate_impulse_outcome_state"], "APPROXIMATION_ONLY")
        self.assertEqual(converted["direction_5m"], "FLAT")
        self.assertEqual(converted["direction_15m"], "DOWN")
        contract.validate_outcome(converted)

    def test_same_v1_1_outcome_can_be_reused_across_pack_a_and_pack_e(self) -> None:
        outcome = prevalidation.convert_legacy_outcome(
            self.legacy_outcome("EP_BATCH_bd5b0d22e01fddb86cf1"),
            acquisition_ts="2026-07-26T00:00:00Z",
        )
        payload = response()
        payload["immediate_impulse_direction"] = "UP"
        payload["early_reaction_5m_direction"] = "UP"
        payload["path"][0]["expected_direction"] = "UP"
        baseline_prediction, baseline_paths = step6.response_to_contract(
            payload,
            input_row(arm="PACK_A", episode_id=outcome["episode_id"]),
            run_id="RUN",
            created_ts="2026-07-26T00:00:01Z",
            raw_output=payload,
            bridge_result={"prompt_tokens": 1, "completion_tokens": 1, "latency_ms": 1},
        )
        full_context_prediction, full_context_paths = step6.response_to_contract(
            payload,
            input_row(arm="PACK_E", episode_id=outcome["episode_id"]),
            run_id="RUN",
            created_ts="2026-07-26T00:00:02Z",
            raw_output=payload,
            bridge_result={"prompt_tokens": 1, "completion_tokens": 1, "latency_ms": 1},
        )
        baseline_eval = step6.evaluate(baseline_prediction, baseline_paths, outcome, generated_ts="2026-07-26T00:01:00Z")
        full_context_eval = step6.evaluate(full_context_prediction, full_context_paths, outcome, generated_ts="2026-07-26T00:01:00Z")
        self.assertEqual(baseline_eval["outcome_id"], full_context_eval["outcome_id"])
        self.assertEqual(baseline_eval["immediate_impulse_direction_result"], "NOT_APPLICABLE")
        self.assertEqual(full_context_eval["immediate_impulse_direction_result"], "NOT_APPLICABLE")
        self.assertIsNotNone(baseline_eval["direction_15m_ok"])
        self.assertEqual(baseline_eval["primary_endpoint_name"], "EPISODE_REACTION_DIRECTION_15M")


class RunnerOutcomeBoundaryTests(unittest.TestCase):
    def test_legacy_outcomes_are_rejected(self) -> None:
        with self.assertRaisesRegex(step6.Step6Error, "OUTCOME_SET_VERSION_MISMATCH"):
            step6.load_v1_1_outcomes(prevalidation.LEGACY_OUTCOMES)

    def test_mixed_versions_fail_closed(self) -> None:
        legacy = OutcomeConversionTests.legacy_outcome("EP_EVENT_ccf7e8031b0d9b2e2443")
        converted = prevalidation.convert_legacy_outcome(legacy, acquisition_ts="2026-07-26T00:00:00Z")
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "outcomes.jsonl"
            path.write_text(json.dumps(converted) + "\n" + json.dumps(legacy) + "\n")
            with self.assertRaisesRegex(step6.Step6Error, "OUTCOME_SET_VERSION_MISMATCH"):
                step6.load_v1_1_outcomes(path)

    def test_manifest_cannot_fallback_to_legacy_outcome_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / "manifest.json"
            manifest.write_text(json.dumps({
                "contract_version": contract.CONTRACT_VERSION,
                "schema_version": contract.SCHEMA_VERSION,
                "outcomes_v1_1_path": "outputs/presignal_v21_episode_outcomes/outcome_rows.jsonl",
            }))
            with self.assertRaisesRegex(step6.Step6Error, "LEGACY_OUTCOME_FALLBACK_FORBIDDEN"):
                step6.resolve_v1_1_outcomes_path(prevalidation_manifest=manifest)

    def test_build_prevalidation_writes_isolated_artifacts_and_pointer(self) -> None:
        original_pointer = prevalidation.LATEST_POINTER
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir) / "outputs"
            temp_pointer = temp_root / "latest_prevalidation_manifest.json"
            prevalidation.LATEST_POINTER = temp_root / "latest_prevalidation_manifest.json"
            try:
                run_dir, pointer = prevalidation.build_prevalidation(output_root=temp_root)
            finally:
                prevalidation.LATEST_POINTER = original_pointer
            self.assertTrue((run_dir / "population_admission.jsonl").exists())
            self.assertTrue((run_dir / "outcomes_v1_1" / "outcome_rows.jsonl").exists())
            self.assertEqual(pointer["contract_version"], contract.CONTRACT_VERSION)
            outcomes = step6.load_v1_1_outcomes(run_dir / "outcomes_v1_1" / "outcome_rows.jsonl")
            self.assertEqual(len(outcomes), 3)
            manifest = json.loads((run_dir / "validation_batch.json").read_text())
            self.assertEqual(manifest["expected_provider_calls"], 14)
            self.assertTrue(temp_pointer.exists())


if __name__ == "__main__":
    unittest.main()
