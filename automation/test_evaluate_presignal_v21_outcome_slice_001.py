import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
RUN = BASE / "PPHB-R1-OUTCOME-EVALUATION-SLICE-001-20260803T103000Z-4f8c2b9a6d10"


class OutcomeSliceEvaluationTest(unittest.TestCase):
    def test_population_and_metrics_are_bounded(self):
        proof = json.loads((RUN / "population_and_denominator_proof.json").read_text())
        self.assertEqual(proof["forecast_count"], 44)
        self.assertEqual(proof["outcome_count"], 12)
        self.assertEqual(proof["complete_episode_pair_groups"], 12)
        self.assertEqual(proof["missing_outcomes"], [])
        self.assertEqual(proof["duplicate_evaluation_rows"], 0)
        self.assertEqual(proof["outside_slice_included"], 0)

    def test_pack_separation_and_approximate_impulse_boundary(self):
        rows = [json.loads(line) for line in (RUN / "per_forecast_evaluation_rows.jsonl").read_text().splitlines()]
        self.assertEqual(len(rows), 44)
        self.assertEqual(sum(row["pack"] == "PACK_A" for row in rows), 22)
        self.assertEqual(sum(row["pack"] == "PACK_E" for row in rows), 22)
        self.assertEqual(sum(row["no_signal"] for row in rows), 0)
        self.assertEqual(sum(row["immediate_supported"] for row in rows), 0)
        metrics = json.loads((RUN / "pack_metrics.json").read_text())
        for pack in ("PACK_A", "PACK_E"):
            impulse = metrics[pack]["metrics"]["Immediate Impulse directional accuracy"]
            self.assertEqual(impulse["evaluated_count"], 0)
            self.assertEqual(impulse["result"], None)

    def test_external_and_composite_guards(self):
        manifest = json.loads((RUN / "run_manifest.json").read_text())
        self.assertEqual(manifest["external_requests"], 0)
        self.assertEqual(manifest["google_reads"], 0)
        self.assertEqual(manifest["google_writes"], 0)
        decision = json.loads((RUN / "evaluation_decision.json").read_text())
        self.assertEqual(decision["composite_score"], "NOT_CALCULATED_NOT_AUTHORIZED")

    def test_deterministic_reproduction(self):
        result = subprocess.run([
            sys.executable, str(ROOT / "automation" / "evaluate_presignal_v21_outcome_slice_001.py"),
            "--run-id", RUN.name,
        ], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("EVALUATION_RUN_ALREADY_EXISTS", result.stderr)


if __name__ == "__main__":
    unittest.main()
