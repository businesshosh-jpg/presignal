"""Focused offline checks for the consolidated R6 Request envelope audit."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from automation import run_presignal_v21_r6_information_request_envelope_alignment_v1 as envelope


class EnvelopeAlignmentTests(unittest.TestCase):
    def setUp(self):
        self.evidence, self.raw = envelope.payload(envelope.SECOND / "repaired_information_request_raw_response.json")

    def test_complete_inventory_and_matrix_are_deterministic(self):
        episode, _members, attention, _raw_attention = envelope.legacy.load_inputs()
        first = envelope.field_inventory(raw=self.raw, transport=self.evidence["transport_metadata"], episode=episode, attention=attention)
        self.assertEqual(first, envelope.field_inventory(raw=self.raw, transport=self.evidence["transport_metadata"], episode=episode, attention=attention))
        self.assertGreaterEqual(len(first), 53)
        self.assertEqual(envelope.matrix(), envelope.matrix())

    def test_exact_transport_bound_mapping_preserves_raw_role(self):
        mapped = envelope.normalize_exact_envelope(raw=self.raw, transport=self.evidence["transport_metadata"], prompt_checksum=envelope.PROMPT_CHECKSUM, schema_version=envelope.SCHEMA_VERSION)
        self.assertEqual(self.raw["provider"], "S&P Global")
        self.assertEqual(mapped["canonical_payload"]["provider"], "Gemini")
        self.assertTrue(mapped["not_a_gemini_alias"])
        with self.assertRaisesRegex(envelope.EnvelopeAlignmentError, "PROMPT"):
            envelope.normalize_exact_envelope(raw=self.raw, transport=self.evidence["transport_metadata"], prompt_checksum="sha256:wrong", schema_version=envelope.SCHEMA_VERSION)
        with self.assertRaisesRegex(envelope.EnvelopeAlignmentError, "RAW_PAYLOAD"):
            envelope.normalize_exact_envelope(raw={**self.raw, "provider": "Other"}, transport=self.evidence["transport_metadata"], prompt_checksum=envelope.PROMPT_CHECKSUM, schema_version=envelope.SCHEMA_VERSION)
        with self.assertRaisesRegex(envelope.EnvelopeAlignmentError, "TRANSPORT_PROVIDER"):
            envelope.normalize_exact_envelope(raw=self.raw, transport={**self.evidence["transport_metadata"], "actual_provider": "Other"}, prompt_checksum=envelope.PROMPT_CHECKSUM, schema_version=envelope.SCHEMA_VERSION)

    def test_all_three_categories_are_valid_but_content_divergences_are_reported(self):
        mismatches = envelope.item_mismatches(self.raw)
        codes = [row["code"] for row in mismatches]
        self.assertNotIn("REQUEST_CATEGORY_INVALID", codes)
        self.assertEqual(codes.count("PROMPT_PROHIBITED_RELEASED_ACTUAL_REFERENCE"), 4)

    def test_full_run_preserves_raw_and_stops_before_pack_a(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            envelope.run(output=output)
            final = json.loads((output / "final_information_request_envelope_alignment_decision.json").read_text())
            canonical = json.loads((output / "canonical_information_requests.json").read_text())
            pack_a = json.loads((output / "pack_a_input_contract_readiness.json").read_text())
            audit = json.loads((output / "external_access_audit.json").read_text())
        self.assertEqual(final["decision"], "R6_INFORMATION_REQUEST_ENVELOPE_ALIGNED_RESPONSE_INVALID")
        self.assertEqual(canonical["status"], "NOT_CREATED")
        self.assertFalse(pack_a["pack_a_constructed"])
        self.assertTrue(all(value == 0 for value in audit.values()))


if __name__ == "__main__":
    unittest.main()
