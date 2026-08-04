from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation import freeze_presignal_v21_pack_e_prospective_v1_feasibility as feasibility


class PackEProspectiveV1FeasibilityTests(unittest.TestCase):
    def test_seven_exact_source_families_are_fixed(self):
        result = feasibility.build_evidence()
        sources = result["source_authority"]["source_families"]
        self.assertEqual(len(sources), 7)
        self.assertEqual([(row["provider"], row["symbol"]) for row in sources], [
            ("FRED", "DGS2"), ("FRED", "DGS10"), ("EODHD", "USDJPY.FOREX"),
            ("FMP", "DX-Y.NYB"), ("EODHD", "GSPC.INDX"), ("EODHD", "XAUUSD.FOREX"), ("FMP", "CLUSD"),
        ])
        self.assertTrue(all(row["classification"] == "PROSPECTIVE_SOURCE_REQUIRES_IMPLEMENTATION_AUTHORITY" for row in sources))

    def test_non_equivalence_and_governance_stops_are_preserved(self):
        result = feasibility.build_evidence()
        self.assertIn("ROUND_2_CONFIRMATORY_PROTOCOL_CLOSED_PACK_E_NON_EQUIVALENT", result["amendment"]["decisions"])
        self.assertFalse(result["field_contract"]["historical_equivalence_claim"])
        self.assertEqual(result["field_contract"]["decision"], "PACK_E_PROSPECTIVE_V1_FIELD_CONTRACT_BLOCKED")
        self.assertEqual(result["lead_time"]["decision"], "PACK_E_PROSPECTIVE_V1_LEAD_TIME_BLOCKED")
        self.assertEqual(result["implementation_authorization_inputs"]["status"], "PACK_E_PROSPECTIVE_V1_IMPLEMENTATION_REMAINS_BLOCKED")

    def test_artifact_is_deterministic_and_local_only(self):
        first = feasibility.build_evidence()
        second = feasibility.build_evidence()
        self.assertEqual(first["fingerprint"], second["fingerprint"])
        self.assertEqual(first["activity"]["market_data_calls"], 0)
        with tempfile.TemporaryDirectory() as directory:
            frozen = feasibility.freeze(Path(directory) / "evidence")
        self.assertEqual(frozen["fingerprint"], first["fingerprint"])


if __name__ == "__main__":
    unittest.main()
