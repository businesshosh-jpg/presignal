"""Focused no-I/O checks for the preserved R6 Request category classification."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from automation import run_presignal_v21_r6_information_request_category_repair_v1 as repair
from automation import run_presignal_v21_r6_information_request_execution_v1 as execution


class RequestCategoryRepairTests(unittest.TestCase):
    def test_frozen_taxonomy_is_reproducible(self):
        first, second = repair.frozen_taxonomy_inventory(), repair.frozen_taxonomy_inventory()
        self.assertEqual(first, second)
        self.assertEqual(len(first), 16)
        self.assertIn("other", [item["canonical_value"] for item in first])
        self.assertNotIn("Economic Indicator", [item["canonical_value"] for item in first])

    def test_economic_indicator_has_no_authorized_exact_mapping(self):
        with self.assertRaisesRegex(repair.RequestCategoryError, "UNSUPPORTED_NO_EXACT"):
            repair.exact_category_normalization(raw_category="Economic Indicator", prompt_version=repair.PROMPT_VERSION, schema_version=repair.RESPONSE_SCHEMA_VERSION)

    def test_existing_canonical_category_needs_no_alias_repair(self):
        self.assertEqual(repair.exact_category_normalization(raw_category="dxy", prompt_version=repair.PROMPT_VERSION, schema_version=repair.RESPONSE_SCHEMA_VERSION), "dxy")

    def test_wrong_version_and_unknown_category_fail_closed(self):
        with self.assertRaisesRegex(repair.RequestCategoryError, "PROMPT_VERSION"):
            repair.exact_category_normalization(raw_category="Economic Indicator", prompt_version="other", schema_version=repair.RESPONSE_SCHEMA_VERSION)
        with self.assertRaisesRegex(repair.RequestCategoryError, "SCHEMA_VERSION"):
            repair.exact_category_normalization(raw_category="Economic Indicator", prompt_version=repair.PROMPT_VERSION, schema_version="other")
        with self.assertRaisesRegex(repair.RequestCategoryError, "NO_GENERIC_FALLBACK"):
            repair.exact_category_normalization(raw_category="unknown value", prompt_version=repair.PROMPT_VERSION, schema_version=repair.RESPONSE_SCHEMA_VERSION)

    def test_full_preserved_inventory_fails_without_other_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            repair.run(output=output)
            inventory = json.loads((output / "preserved_response_category_inventory.json").read_text())
            report = json.loads((output / "offline_request_category_revalidation_report.json").read_text())
            final = json.loads((output / "final_request_category_repair_decision.json").read_text())
            canonical = json.loads((output / "canonical_information_requests.json").read_text())
        self.assertEqual(inventory["raw_item_count"], 3)
        self.assertTrue(inventory["all_items_use_economic_indicator"])
        self.assertFalse(report["category_validation"])
        self.assertTrue(report["next_validation_divergence"].startswith("REQUEST_CATEGORY_UNSUPPORTED"))
        self.assertEqual(canonical["status"], "NOT_CREATED")
        self.assertEqual(final["decision"], "R6_INFORMATION_REQUEST_CATEGORY_REMAINS_INVALID")

    def test_historical_trace_has_no_economic_indicator_alias(self):
        trace = repair.raw_category_occurrences()
        self.assertEqual(trace["occurrences"]["Economic Indicator"], [])

    def test_pre_category_binding_failures_are_independent_and_fail_closed(self):
        episode, _members, attention, _raw_attention = execution.load_inputs()
        evidence = repair.read(repair.EXECUTION / "information_request_raw_response.json")
        pre = repair.read(repair.EXECUTION / "information_request_pre_call_manifest.json")
        raw = json.loads(evidence["raw_response"])
        transport = evidence["transport_metadata"]
        invalid_episode = dict(raw); invalid_episode["session_id"] = "other"
        with self.assertRaisesRegex(repair.RequestCategoryError, "EPISODE_MISMATCH"):
            repair.validate_pre_category_bindings(raw=invalid_episode, pre=pre, transport=transport, episode=episode, attention=attention)
        invalid_pre = dict(pre); invalid_pre["attention_identity"] = "other"
        with self.assertRaisesRegex(repair.RequestCategoryError, "ATTENTION_MISMATCH"):
            repair.validate_pre_category_bindings(raw=raw, pre=invalid_pre, transport=transport, episode=episode, attention=attention)
        invalid_text = dict(raw); invalid_text["information_items"] = [dict(raw["information_items"][0], requested_information="")]
        with self.assertRaisesRegex(repair.RequestCategoryError, "TEXT_REQUIRED"):
            repair.validate_pre_category_bindings(raw=invalid_text, pre=pre, transport=transport, episode=episode, attention=attention)
        invalid_transport = dict(transport); invalid_transport["completed_timestamp"] = "2030-01-01T00:00:00Z"
        with self.assertRaisesRegex(repair.RequestCategoryError, "POST_CUTOFF"):
            repair.validate_pre_category_bindings(raw=raw, pre=pre, transport=invalid_transport, episode=episode, attention=attention)

    def test_no_external_access_is_recorded(self):
        self.assertTrue(all(value == 0 for value in repair.audit().values()))


if __name__ == "__main__":
    unittest.main()
