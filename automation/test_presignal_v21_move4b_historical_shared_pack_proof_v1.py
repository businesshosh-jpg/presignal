"""Focused offline regression tests for the Move 4B historical Pack proof."""
from __future__ import annotations

import copy
from pathlib import Path
import socket
import unittest
from unittest import mock
import urllib.request

from automation import presignal_v21_pack_capability_v1 as capability
from automation import run_presignal_v21_move4b_historical_shared_pack_proof_v1 as proof


ROOT = Path(__file__).resolve().parents[1]


class HistoricalSharedPackProofTests(unittest.TestCase):
    def setUp(self):
        self.fixture = proof.build_historical_fixture(ROOT)

    def test_fixture_loads_and_checksums_validate(self):
        self.assertEqual(self.fixture["expected_fingerprint"], proof.EXPECTED_FINGERPRINT)
        self.assertEqual(self.fixture["sources"][0]["checksum"], "sha256:" + proof._file_sha(ROOT / proof.SOURCE_PATH))
        self.assertEqual(self.fixture["fixture_checksum"], "sha256:" + proof._sha({key: value for key, value in self.fixture.items() if key != "fixture_checksum"}))

    def test_three_provider_union_request_dedup_and_models_are_preserved(self):
        result = proof.run_historical_shared_pack_proof(ROOT, self.fixture)
        self.assertEqual(result["expected_provider_count"], 3)
        self.assertEqual(result["actual_provider_count"], 3)
        self.assertEqual(result["expected_request_count"], 15)
        self.assertTrue(result["provider_lineage_match"])
        self.assertEqual(sorted({row["provider"] for row in self.fixture["historical_requests"]}), ["Anthropic", "Gemini", "OpenAI"])
        self.assertEqual(len({row["information_key"] for row in self.fixture["historical_requests"]}), 15)

    def test_derived_information_and_historical_cutoff_reproduce_exact_pack(self):
        result = proof.run_historical_shared_pack_proof(ROOT, self.fixture)
        self.assertEqual(result["expected_item_count"], 15)
        self.assertEqual(result["actual_item_count"], 15)
        self.assertTrue(result["content_match"])
        self.assertTrue(result["ordering_match"])
        self.assertTrue(result["exact_fingerprint_match"])
        self.assertTrue(all(row["classification"] == "historical derived information input" for row in self.fixture["historical_derived_information_inputs"]))
        self.assertTrue(all(row["payload"]["forecast_cutoff"] == proof.CUTOFF for row in self.fixture["historical_derived_information_inputs"]))

    def test_three_runs_are_deterministic(self):
        reports = proof.proof_reports(ROOT)
        deterministic = reports["determinism_report.json"]
        self.assertEqual(deterministic["proof_runs"], 3)
        self.assertTrue(deterministic["identical_runs"])
        self.assertTrue(deterministic["final_fingerprint_stability"])

    def test_fixture_mutation_changes_the_resulting_fingerprint(self):
        mutated = copy.deepcopy(self.fixture)
        mutated["historical_derived_information_inputs"][0]["payload"]["value"] = {"changed": True}
        result = proof.run_historical_shared_pack_proof(ROOT, mutated)
        self.assertFalse(result["content_match"])
        self.assertNotEqual(result["actual_fingerprint"], proof.EXPECTED_FINGERPRINT)

    def test_provider_removal_and_item_reorder_fail_closed(self):
        missing_provider = copy.deepcopy(self.fixture)
        missing_provider["historical_requests"] = [row for row in missing_provider["historical_requests"] if row["provider"] != "OpenAI"]
        with self.assertRaisesRegex(capability.PackCapabilityError, "HISTORICAL_PROVIDER_UNION_MISMATCH"):
            proof.run_historical_shared_pack_proof(ROOT, missing_provider)
        reordered = copy.deepcopy(self.fixture)
        reordered["historical_derived_information_inputs"][0], reordered["historical_derived_information_inputs"][1] = reordered["historical_derived_information_inputs"][1], reordered["historical_derived_information_inputs"][0]
        with self.assertRaisesRegex(capability.PackCapabilityError, "HISTORICAL_STORED_ORDER_INVALID"):
            proof.run_historical_shared_pack_proof(ROOT, reordered)

    def test_external_and_write_sentinels_remain_untouched(self):
        calls: list[str] = []
        def blocked(name):
            def _blocked(*args, **kwargs):
                calls.append(name)
                raise AssertionError(name)
            return _blocked
        with mock.patch.object(socket, "create_connection", blocked("socket")), mock.patch.object(urllib.request, "urlopen", blocked("http")):
            result = proof.run_historical_shared_pack_proof(ROOT, self.fixture)
        self.assertTrue(result["exact_fingerprint_match"])
        self.assertEqual(calls, [])
        self.assertEqual(proof.proof_reports(ROOT)["isolation_audit.json"], {
            "provider_calls": 0, "google_calls": 0, "apps_script_calls": 0, "http_calls": 0,
            "market_data_calls": 0, "production_writes": 0, "historical_mutations": 0,
            "forecast_calls": 0, "outcome_operations": 0, "evaluation_operations": 0,
        })


if __name__ == "__main__":
    unittest.main()
