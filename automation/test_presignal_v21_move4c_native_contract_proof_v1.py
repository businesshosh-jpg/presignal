"""Focused offline tests for Move 4C native contract validation."""
from __future__ import annotations

import copy
from pathlib import Path
import socket
import unittest
from unittest import mock
import urllib.request

from automation import presignal_v21_pack_capability_v1 as capability
from automation import run_presignal_v21_move4c_native_contract_proof_v1 as proof


ROOT = Path(__file__).resolve().parents[1]


class NativeContractProofTests(unittest.TestCase):
    def setUp(self):
        self.fixture = proof.build_native_fixture(ROOT)

    def test_fixture_and_manifest_are_rule_derived_and_check_summed(self):
        self.assertEqual(self.fixture["classification"], "NATIVE_CONTRACT_VALIDATION_FIXTURE")
        self.assertTrue((ROOT / "contracts/presignal_v21_event_path/move4c_native_contract_fixture_manifest.json").is_file())
        self.assertEqual(self.fixture["fixture_checksum"], "sha256:" + proof._sha({key: value for key, value in self.fixture.items() if key != "fixture_checksum"}))

    def test_selected_provider_aggregation_is_shared_and_excludes_openai(self):
        result = proof.run_native_proof(ROOT, self.fixture)
        self.assertEqual(len(result["requests"]), 5)
        self.assertEqual({row["lineage"]["provider"] for row in result["requests"]}, {"Anthropic", "Gemini"})
        self.assertEqual(sum(row["information_key"] == "dxy|dxy_pre_session_state" for row in result["requests"]), 2)
        self.assertEqual([row["lineage"]["provider"] for row in result["requests"]], sorted(row["lineage"]["provider"] for row in result["requests"]))

    def test_native_records_validate_and_preserve_raw_normalized_and_unavailable(self):
        result = proof.run_native_proof(ROOT, self.fixture)
        self.assertEqual(len(result["bundle"]["items"]), 5)
        supplied = [row for row in result["bundle"]["items"] if row["status"] == "SUPPLIED"]
        unavailable = [row for row in result["bundle"]["items"] if row["status"] == "UNAVAILABLE"]
        self.assertTrue(all(row["raw_acquired_content"] and row["normalized_acquired_content"] for row in supplied))
        self.assertEqual(len(unavailable), 1)
        self.assertEqual((unavailable[0]["raw_acquired_content"], unavailable[0]["normalized_acquired_content"]), ("", ""))

    def test_fail_closed_mutation_matrix_has_no_silent_or_partial_results(self):
        matrix = proof.proof_reports(ROOT)["mutation_matrix_report.json"]
        self.assertGreaterEqual(len(matrix), 12)
        self.assertTrue(all(row["actual"] == "FAIL_CLOSED" for row in matrix))
        self.assertTrue(all(row["computation_stopped"] and not row["partial_pack_returned"] for row in matrix))

    def test_record_reordering_does_not_change_bundle_or_pack_identities(self):
        requests = proof._aggregate_requests(self.fixture)
        records = proof._records(requests, self.fixture["episode"])
        first = proof.run_native_proof(ROOT, self.fixture, records=records)
        second = proof.run_native_proof(ROOT, self.fixture, records=list(reversed(records)))
        self.assertEqual(first["checksums"], second["checksums"])
        self.assertEqual(first["native_validation_checksum"], second["native_validation_checksum"])

    def test_source_environment_and_selected_attention_fail_closed(self):
        changed = copy.deepcopy(self.fixture)
        changed["authorized_source_environment"]["approved_source_ids"].remove("FIXTURE_DXY")
        with self.assertRaisesRegex(capability.PackCapabilityError, "UNAUTHORIZED_SOURCE"):
            proof.run_native_proof(ROOT, changed)
        changed = copy.deepcopy(self.fixture)
        changed["selected_attention"]["Anthropic"]["acceptance_state"] = "REJECTED"
        with self.assertRaisesRegex(capability.PackCapabilityError, "SELECTED_PROVIDER_AGGREGATION_MISMATCH"):
            proof.run_native_proof(ROOT, changed)

    def test_determinism_and_external_write_sentinels(self):
        calls: list[str] = []
        def blocked(name):
            def _blocked(*args, **kwargs):
                calls.append(name); raise AssertionError(name)
            return _blocked
        with mock.patch.object(socket, "create_connection", blocked("socket")), mock.patch.object(urllib.request, "urlopen", blocked("http")):
            reports = proof.proof_reports(ROOT)
        self.assertEqual(calls, [])
        self.assertTrue(reports["determinism_report.json"]["identical_runs"])
        self.assertEqual(sum(reports["isolation_audit.json"].values()), 0)


if __name__ == "__main__":
    unittest.main()
