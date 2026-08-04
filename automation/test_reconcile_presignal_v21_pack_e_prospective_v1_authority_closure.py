from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation import reconcile_presignal_v21_pack_e_prospective_v1_authority_closure as closure


class PackEProspectiveV1AuthorityClosureTests(unittest.TestCase):
    def test_seven_routes_are_fixed_and_date_only_is_rejected(self):
        rows = closure.availability_matrix()
        self.assertEqual(len(rows), 7)
        self.assertEqual({row["decision"] for row in rows}, {"AVAILABILITY_TIMESTAMP_REQUIRES_DERIVED_CALENDAR_RULE"})
        self.assertTrue(all(row["resolution"] == "daily/date-only" for row in rows))

    def test_raw_schema_excludes_secrets_and_direction_is_numeric_only(self):
        raw = closure.raw_preservation_contract()
        self.assertIn("raw_response_sha256", raw["required_fields"])
        self.assertNotIn("api_key", raw["required_fields"])
        thresholds = closure.threshold_decision()
        self.assertEqual(thresholds["fields_omitted_with_explicit_reason"], ["direction_24h", "direction_5d"])

    def test_blockers_prevent_contract_and_lead_time(self):
        evidence = closure.build_evidence()
        self.assertEqual(evidence["raw_preservation"]["decision"], "PACK_E_PROSPECTIVE_V1_RAW_PRESERVATION_FROZEN")
        self.assertEqual(evidence["stale_authority"]["decision"], "PACK_E_PROSPECTIVE_V1_STALE_AUTHORITY_BLOCKED")
        self.assertEqual(evidence["timeout_authority"]["decision"], "PACK_E_PROSPECTIVE_V1_TIMEOUT_AUTHORITY_BLOCKED")
        self.assertEqual(evidence["field_contract"]["decision"], "PACK_E_PROSPECTIVE_V1_FIELD_CONTRACT_BLOCKED")
        self.assertEqual(evidence["activity"]["source_calls"], 0)

    def test_output_is_deterministic_and_append_only(self):
        first = closure.build_evidence()
        self.assertEqual(first["fingerprint"], closure.build_evidence()["fingerprint"])
        with tempfile.TemporaryDirectory() as directory:
            result = closure.reconcile(Path(directory) / "evidence")
        self.assertEqual(result["fingerprint"], first["fingerprint"])


if __name__ == "__main__":
    unittest.main()
