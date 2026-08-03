import copy
import json
import tempfile
import unittest
from pathlib import Path

from automation.attach_presignal_v21_outcome_slice_001 import (
    resolve_collection_inputs,
    validate_bridge_candidates,
)


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution" / "PPHB-R1-OUTCOME-COLLECTION-SLICE-002-20260803T035402Z-5b2104c5270c"
MANIFEST = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution" / "PPHB-R1-OUTCOME-COLLECTION-MANIFEST-SLICE-002-20260803T121500Z-9c7adf4c2f2e" / "slice_002_manifest.json"
EXPECTED = "sha256:16e231a854572c72e1869ff04d3c6dcb038021af7bfe9bb059a05b2104c5270c"


class CollectionAttachmentBridgeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest_rows = json.loads(MANIFEST.read_text())["episode_manifest"]
        cls.episodes = {row["episode_id"] for row in cls.manifest_rows}

    def copy_run(self, rows):
        tmp = tempfile.TemporaryDirectory()
        path = Path(tmp.name) / "collection"
        path.mkdir()
        for name in ("run_manifest.json", "collection_reconciliation.json", "collection_decision.json"):
            (path / name).write_bytes((RUN / name).read_bytes())
        (path / "candidate_outcomes.jsonl").write_text(json.dumps(rows, indent=2) + "\n")
        return tmp, path

    def rows(self):
        return json.loads((RUN / "candidate_outcomes.jsonl").read_text())

    def test_native_collector_artifacts_bind_without_transformation(self):
        resolved = resolve_collection_inputs(RUN, EXPECTED)
        self.assertEqual(resolved["source_mode"], "COLLECTOR_NATIVE_ARTIFACTS")
        self.assertEqual(len(resolved["candidates"]), 12)
        validate_bridge_candidates(resolved["candidates"], self.episodes)
        self.assertEqual(resolved["source_hashes"]["candidate_records"], "sha256:451e3d47f503c8f3f19cd0b82d2659e2ebbdc4f0332967b0323fc2414e7cf62b")

    def test_missing_extra_duplicate_and_altered_records_fail_closed(self):
        cases = []
        rows = self.rows()
        cases.append(rows[:-1])
        cases.append(rows + [copy.deepcopy(rows[0])])
        duplicate = rows[:-1] + [copy.deepcopy(rows[0])]
        cases.append(duplicate)
        altered = copy.deepcopy(rows)
        altered[0]["candidate_outcome"]["direction"] = "FLAT"
        cases.append(altered)
        for candidate_rows in cases:
            with self.subTest():
                with self.assertRaises(SystemExit):
                    validate_bridge_candidates(candidate_rows, self.episodes)

    def test_manifest_binding_and_resume_are_fail_closed(self):
        with self.assertRaises(SystemExit):
            resolve_collection_inputs(RUN, "sha256:" + "0" * 64)
        resolved = resolve_collection_inputs(RUN, EXPECTED)
        self.assertEqual(resolved["source_mode"], "COLLECTOR_NATIVE_ARTIFACTS")
        self.assertEqual(resolved["source_hashes"]["run_manifest"], "sha256:1ff008c57815f67eb0f2708640b25c2eebe880e6329db3b2f7bca328ae6226f1")


if __name__ == "__main__":
    unittest.main()
