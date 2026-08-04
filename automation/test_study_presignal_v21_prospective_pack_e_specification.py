from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation import study_presignal_v21_prospective_pack_e_specification as study


class ProspectivePackESpecificationStudyTests(unittest.TestCase):
    def test_historical_universe_and_empty_intersection_are_reproducible(self):
        rows = study.valid_rows(study.read_rows())
        self.assertEqual(len(study.BASE_FIELDS), 18)
        self.assertEqual(len(study.base_field_audit()), 18)
        self.assertTrue(all(
            row["historical_status"] == "STABLE_REQUIRED_SEMANTIC_FIELD"
            for row in study.base_field_audit()
        ))
        self.assertEqual(len(study.field_audit(rows)), 682)
        sample = study.select_sample(rows)
        self.assertEqual(len(sample), 12)
        self.assertGreaterEqual(len({study.episode_family(row) for row in sample}), 2)

    def test_study_is_local_only_and_does_not_promote_pack_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            report = study.study(Path(directory) / "evidence")
        self.assertEqual(report["authority"]["decision"], "HISTORICAL_PACK_E_AUTHORITY_CONFIRMED")
        self.assertEqual(report["candidate"]["closed_field_count"], 0)
        self.assertEqual(report["comparison"]["historical_required_semantic_field_count"], 18)
        self.assertEqual(report["decisions"]["pack_identity"], "PROSPECTIVE_PACK_E_SPECIFICATION_NOT_FEASIBLE")
        self.assertEqual(report["decisions"]["external_activity"]["provider_calls"], 0)
        self.assertEqual(report["comparison"]["historical_field_intersection_count"], 0)


if __name__ == "__main__":
    unittest.main()
