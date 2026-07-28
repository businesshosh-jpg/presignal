from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from automation import audit_presignal_v21_73_episode_rescue_pilot as rescue


def load_json(path: Path):
    return json.loads(path.read_text())


def load_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


class RescuePilotTests(unittest.TestCase):
    def run_pilot(self):
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        result = rescue.build_run(
            output_root=Path(tempdir.name),
            fixed_timestamp="2026-07-28T15:00:00Z",
        )
        return Path(tempdir.name) / result["run_id"], result

    def test_source_pool_is_exactly_frozen_73_with_unique_ids(self):
        rows = rescue.load_blocked_73()
        self.assertEqual(len(rows), 73)
        self.assertEqual(len({row["episode_id"] for row in rows}), 73)

    def test_sample_size_seed_and_determinism(self):
        rows = rescue.load_blocked_73()
        sample1 = rescue.sample_blocked_population(rows, seed=rescue.SEED)
        sample2 = rescue.sample_blocked_population(rows, seed=rescue.SEED)
        self.assertEqual(rescue.SEED, "20260728")
        self.assertEqual(len(sample1["sample"]), 9)
        self.assertEqual(
            [row["episode_id"] for row in sample1["sample"]],
            [row["episode_id"] for row in sample2["sample"]],
        )

    def test_sample_contains_three_standalone_and_three_batch(self):
        rows = rescue.load_blocked_73()
        sample = rescue.sample_blocked_population(rows)
        self.assertGreaterEqual(sum(row["episode_type"] == "STANDALONE" for row in sample["sample"]), 3)
        self.assertGreaterEqual(sum(row["episode_type"] == "BATCH" for row in sample["sample"]), 3)

    def test_blocker_pattern_coverage_is_recorded(self):
        _, result = self.run_pilot()
        contract = result["sampling_contract"]
        self.assertIn("sampling_strata", contract)
        self.assertEqual(contract["sampling_strata"]["blocker_pattern"], "NO_EXACT_PARENT_SESSION")
        self.assertIn("coverage_pattern", contract["sampling_strata"])

    def test_manual_substitution_is_disallowed(self):
        _, result = self.run_pilot()
        self.assertFalse(result["sampling_contract"]["manual_substitution_allowed"])
        self.assertGreater(len(result["sampling_contract"]["replacement_order"]), 0)

    def test_every_sampled_episode_gets_exactly_one_classification(self):
        run_dir, _ = self.run_pilot()
        rows = load_jsonl(run_dir / "recovery_classification.jsonl")
        self.assertEqual(len(rows), 9)
        self.assertEqual(len({row["episode_id"] for row in rows}), 9)
        for row in rows:
            self.assertIn(row["recovery_classification"], rescue.CLASSIFICATIONS)

    def test_fuzzy_joins_and_current_sources_are_rejected(self):
        self.assertFalse(rescue.exact_only_join("A", "B"))
        self.assertTrue(rescue.fuzzy_join_rejected("A", "B"))
        self.assertFalse(rescue.artifact_allowed_as_historical_evidence(Path("/tmp/current_calendar.csv")))
        self.assertFalse(rescue.artifact_allowed_as_historical_evidence(Path("/Users/junhoshino/projects/presignal-historical-baseline-r1/docs/current_notes.md")))

    def test_repeated_runs_are_deterministic_and_call_free(self):
        first_dir, first = self.run_pilot()
        second_dir, second = self.run_pilot()
        self.assertEqual(load_json(first_dir / "pilot_summary.json"), load_json(second_dir / "pilot_summary.json"))
        self.assertEqual(load_json(first_dir / "sampling_contract.json"), load_json(second_dir / "sampling_contract.json"))
        manifest = load_json(first_dir / "run_manifest.json")
        self.assertEqual(manifest["external_calls"]["provider"], 0)
        self.assertEqual(manifest["external_calls"]["research_ai"], 0)
        self.assertEqual(manifest["external_calls"]["market_data"], 0)
        self.assertEqual(manifest["external_calls"]["web"], 0)
        self.assertEqual(manifest["external_calls"]["google_writes"], 0)


if __name__ == "__main__":
    unittest.main()
