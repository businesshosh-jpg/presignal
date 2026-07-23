"""Focused offline tests for the exact R6 Request payload field-role repair."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from automation import run_presignal_v21_r6_information_request_payload_identity_repair_v1 as repair


RAW = {
    "object": "session_information_requirements", "session_id": "EP_TEST", "provider": "S&P Global", "status": "ok",
    "information_items": [{"requested_information": "PMI", "information_category": "growth_context"}],
}


class RequestPayloadIdentityRepairTests(unittest.TestCase):
    def mapped(self, **changes):
        args = {
            "raw_response": RAW, "transport_provider": "Gemini", "transport_model": "gemini-2.5-flash-lite",
            "prompt_template_checksum": repair.PROMPT_TEMPLATE_CHECKSUM,
            "response_schema_checksum": repair.RESPONSE_SCHEMA_CHECKSUM,
        }
        args.update(changes)
        return repair.normalize_exact_gemini_request_payload_identity(**args)

    def test_exact_mapping_preserves_untrusted_payload_value(self):
        before = copy.deepcopy(RAW)
        result = self.mapped()
        self.assertEqual(RAW, before)
        self.assertEqual(result["canonical_payload"]["provider"], "Gemini")
        self.assertEqual(result["payload_provider_value"], "S&P Global")
        self.assertIsNone(result["requested_source_identity"])

    def test_wrong_trusted_identity_or_contract_fails_closed(self):
        for field, value, code in (
            ("transport_provider", "OpenAI", "TRANSPORT_PROVIDER"),
            ("transport_model", "other", "TRANSPORT_MODEL"),
            ("prompt_template_checksum", "sha256:wrong", "PROMPT_VERSION"),
            ("response_schema_checksum", "sha256:wrong", "SCHEMA_VERSION"),
        ):
            with self.subTest(field=field):
                with self.assertRaisesRegex(repair.RequestPayloadIdentityError, code):
                    self.mapped(**{field: value})

    def test_unknown_payload_value_cannot_become_provider_alias(self):
        altered = {**RAW, "provider": "anything-else"}
        with self.assertRaisesRegex(repair.RequestPayloadIdentityError, "PAYLOAD_VALUE"):
            self.mapped(raw_response=altered)

    def test_source_registry_lookup_is_deterministic_and_not_an_llm_mismatch(self):
        first, second = repair.source_registry_validation(), repair.source_registry_validation()
        self.assertEqual(first, second)
        self.assertFalse(first["approved_source_match"])
        self.assertEqual(first["source_normalization_result"], "UNRESOLVED_NO_BOUND_AKSR_ENTRY")

    def test_preserved_evidence_revalidates_to_next_category_divergence(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            repair.run(output=output)
            final = json.loads((output / "final_request_payload_identity_repair_decision.json").read_text())
            report = json.loads((output / "offline_request_revalidation_report.json").read_text())
            canonical = json.loads((output / "canonical_information_requests.json").read_text())
        self.assertEqual(final["decision"], "R6_INFORMATION_REQUEST_OFFLINE_REVALIDATION_FAILED")
        self.assertTrue(report["checksum_valid"])
        self.assertTrue(report["payload_identity_normalized"])
        self.assertTrue(report["next_validation_divergence"].startswith("REQUEST_CATEGORY_INVALID"))
        self.assertEqual(canonical["status"], "NOT_CREATED")

    def test_no_external_access_is_recorded(self):
        self.assertTrue(all(value == 0 for value in repair.audit().values()))


if __name__ == "__main__":
    unittest.main()
