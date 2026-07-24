"""Focused Pack A and approved-source-environment gate tests."""
from __future__ import annotations

import unittest

from automation import run_presignal_v21_new_r6_pack_construction_v1 as packs


class NewR6PackConstructionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.authorization, self.requests, self.episode, self.attention, self.old = packs.load_inputs()

    def test_pack_authorization_and_request_set_validate(self) -> None:
        result = packs.validate_authorization(self.authorization, self.requests, self.episode, self.attention)
        self.assertTrue(result["authorization_valid"])

    def test_pack_a_is_exactly_the_ten_ordered_requests(self) -> None:
        pack = packs.construct_pack_a(self.requests["requests"])
        self.assertEqual(len(pack["ordered_canonical_requests"]), 10)
        self.assertEqual(pack["ordered_request_identities"], [row["request_identity"] for row in self.requests["requests"]])
        self.assertFalse(pack["provenance"]["acquired_source_content_included"])

    def test_pack_a_is_deterministic(self) -> None:
        first = packs.construct_pack_a(self.requests["requests"])
        second = packs.construct_pack_a(self.requests["requests"])
        self.assertEqual(first, second)

    def test_no_bound_environment_blocks_acquisition_without_substitution(self) -> None:
        gate = packs.source_environment_gate(self.old)
        self.assertEqual(gate["result"], "BLOCKED_NO_PROSPECTIVE_R6_APPROVED_SOURCE_ENVIRONMENT")
        self.assertEqual(gate["acquisition_dispatches_authorized"], 0)
        self.assertIn("does not itself bind", gate["why_registry_not_substituted"])

    def test_cutoff_closed_stops_before_pack_a(self) -> None:
        self.assertGreaterEqual((packs.parse_utc("2026-07-30T00:00:00Z") - packs.parse_utc(packs.CUTOFF)).total_seconds(), 0)


if __name__ == "__main__":
    unittest.main()
