"""Offline priority-contract regression tests."""
from __future__ import annotations

import unittest

from automation import presignal_v21_minimal_prospective_lineage_v1 as lineage
from automation import run_presignal_v21_new_r6_information_request_execution_v1 as request
from automation import run_presignal_v21_information_request_priority_contract_repair_v1 as repair


class PriorityContractRepairTest(unittest.TestCase):
    def test_existing_display_mapping_is_explicit(self) -> None:
        self.assertEqual(request.normalize_known_priority("High"), ("must_have", True))
        self.assertEqual(request.normalize_known_priority("Medium"), ("useful", True))
        self.assertEqual(request.normalize_known_priority("Low"), ("low_value", True))
        self.assertEqual(request.normalize_known_priority("optional"), ("optional", False))

    def test_unknown_priority_fails_closed(self) -> None:
        self.assertEqual(request.normalize_known_priority("urgent"), (None, False))

    def test_canonical_enum_is_not_broadened(self) -> None:
        contract = repair.priority_contract()
        self.assertEqual(contract["canonical_enum"], sorted(lineage.VALID_PRIORITIES))
        self.assertNotIn("High", contract["canonical_enum"])

    def test_v3_prompt_requires_machine_priorities(self) -> None:
        prompt = lineage.REQUEST_INSTRUCTION_V3
        for value in ("must_have", "useful", "optional", "low_value"):
            self.assertIn(value, prompt)
        self.assertIn("Do not return High, Medium, Low", prompt)

    def test_preserved_raw_checksum_is_unchanged(self) -> None:
        raw = repair.read("new_r6_information_request_raw_response.json")["raw_response"]
        self.assertEqual(request.sha(raw), repair.RAW_SHA)


if __name__ == "__main__":
    unittest.main()
