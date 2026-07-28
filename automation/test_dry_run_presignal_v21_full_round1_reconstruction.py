from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automation import dry_run_presignal_v21_full_round1_reconstruction as dry_run


def load_json(path: Path):
    return json.loads(path.read_text())


def load_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


class ReconstructionDryRunTests(unittest.TestCase):
    def run_dry(self):
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        result = dry_run.build_run(
            output_root=Path(tempdir.name),
            fixed_timestamp="2026-07-28T13:40:00Z",
        )
        return Path(tempdir.name) / result["run_id"], result

    def test_all_462_episodes_are_accounted_for(self):
        run_dir, result = self.run_dry()
        rows = load_jsonl(run_dir / "episode_reconstruction_plan.jsonl")
        self.assertEqual(len(rows), 462)
        self.assertEqual(result["summary"]["admitted_episode_count"], 462)
        self.assertEqual(sum(row["stage1_episode_inputs_status"] == "READY_FROM_FROZEN_INPUTS" for row in rows), 462)

    def test_341_reconstructable_and_73_unavailable_remain_admitted(self):
        run_dir, result = self.run_dry()
        plan = load_jsonl(run_dir / "episode_reconstruction_plan.jsonl")
        self.assertEqual(sum(row["stage2_attention_status"] == "REBUILT_FROM_FROZEN_INPUTS_WITH_PROVIDER_CALL" for row in plan), 341)
        self.assertEqual(sum(row["stage2_attention_status"] == "UNAVAILABLE" for row in plan), 73)
        self.assertEqual(result["summary"]["reconstructable_episode_count"], 341)
        self.assertEqual(result["summary"]["unavailable_episode_count"], 73)

    def test_exact_48_artifacts_are_preserved_not_rebuilt(self):
        run_dir, result = self.run_dry()
        preservation = load_json(run_dir / "existing_48_preservation_check.json")
        self.assertEqual(preservation["exact_lineage_episode_count"], 48)
        self.assertEqual(preservation["immutable_gemini_openai_arms_preserved"], 170)
        self.assertEqual(preservation["ready_for_execution_not_only_special_case"]["special_episode_openai_gemini_ready_arms"], 4)
        self.assertEqual(preservation["ready_for_execution_not_only_special_case"]["gemini_only_exact_cohort_missing_openai_ready_arms"], 18)

    def test_no_post_cutoff_or_unverifiable_input_is_marked_usable_for_unavailable_episodes(self):
        run_dir, _ = self.run_dry()
        rows = load_jsonl(run_dir / "input_admissibility_inventory.jsonl")
        unavailable_attention = [
            row for row in rows
            if row["input_kind"] == "ATTENTION_INPUT_SNAPSHOT" and row["admissibility_status"] == "SOURCE_UNAVAILABLE"
        ]
        self.assertEqual(len(unavailable_attention), 73)
        pack_bindings = [row for row in rows if row["input_kind"] in {"PACK_A_BINDING", "PACK_E_BINDING"}]
        self.assertGreater(sum(row["admissibility_status"] == "HISTORICAL_VERSION_UNVERIFIED" for row in pack_bindings), 0)

    def test_pack_e_remains_shared_and_provider_specific_attention_is_not_deduplicated(self):
        run_dir, result = self.run_dry()
        pack_e_rows = load_jsonl(run_dir / "pack_e_reconstruction_plan.jsonl")
        self.assertEqual(sum(row["shared_pack_rule_preserved"] for row in pack_e_rows), 462)
        projection = result["provider_call_projection"]
        self.assertEqual(projection["attention_calls"]["required"], 186)
        self.assertEqual(projection["information_request_calls"]["required"], 0)
        self.assertEqual(projection["information_request_calls"]["conditionally_required"], 186)

    def test_no_calls_or_google_writes_occur(self):
        run_dir, _ = self.run_dry()
        manifest = load_json(run_dir / "run_manifest.json")
        self.assertEqual(manifest["external_calls"]["provider"], 0)
        self.assertEqual(manifest["external_calls"]["research_ai"], 0)
        self.assertEqual(manifest["external_calls"]["market_data"], 0)
        self.assertEqual(manifest["external_calls"]["google_writes"], 0)

    def test_exact_special_case_remains_admitted_with_outcome_unavailable(self):
        run_dir, _ = self.run_dry()
        plan = {row["episode_id"]: row for row in load_jsonl(run_dir / "episode_reconstruction_plan.jsonl")}
        special = plan["EP_EVENT_757e72165d3ec05306a6"]
        self.assertEqual(special["stage2_attention_status"], "REUSED_EXACT")
        self.assertEqual(special["stage4_pack_a_status"], "READY_FROM_EXISTING_INPUTS")
        self.assertEqual(special["stage5_pack_e_status"], "READY_FROM_EXISTING_INPUTS")

    def test_deterministic_fingerprint_on_rerun(self):
        first_dir, first = self.run_dry()
        second_dir, second = self.run_dry()
        self.assertEqual(first["summary"]["provider_call_projection_fingerprint"], second["summary"]["provider_call_projection_fingerprint"])
        self.assertEqual(load_json(first_dir / "reconstruction_summary.json"), load_json(second_dir / "reconstruction_summary.json"))


if __name__ == "__main__":
    unittest.main()
