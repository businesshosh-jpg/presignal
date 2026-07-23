#!/usr/bin/env python3
"""Focused no-I/O tests for the v2.1 return-only Episode-to-Pack capability."""
from __future__ import annotations

import builtins
import copy
import inspect
import json
import socket
import unittest
from pathlib import Path

from automation import presignal_v21_pack_capability_v1 as capability


EXAMPLES = Path(__file__).resolve().parents[1] / "contracts" / "presignal_v21_event_path" / "examples"


def load_episode():
    return json.loads((EXAMPLES / "valid_single_event_episode.json").read_text())


class PackCapabilityTests(unittest.TestCase):
    def setUp(self):
        self.episode = load_episode()
        self.cutoff = self.episode["forecast_cutoff_ts"]
        self.attention = {
            "attention_id": "ATTN_FIXTURE_1", "episode_id": self.episode["episode_id"],
            "selection_status": "SELECTED", "provider": "Gemini", "model": "gemini-2.5-flash-lite",
            "forecast_cutoff_ts": self.cutoff, "attention_labels": ["PRIMARY_DRIVER"],
        }
        self.raw = {
            "object": "session_information_requirements", "session_id": self.episode["session_id"],
            "provider": "Gemini", "status": "ok", "information_items": [
                {"request_rank": 2, "requested_information": "DXY pre-session state", "information_category": "dollar index", "priority": "high", "reason": "context", "affected_channel": "usd_direction", "linked_event_ids": [self.episode["primary_event_id"]], "linked_attention_labels": ["PRIMARY_DRIVER"], "available_now": "unknown", "suggested_source": "FROZEN_DXY", "expected_forecast_use": "context", "is_market_state_candidate": True},
                {"request_rank": 1, "requested_information": "US 2Y and 10Y Treasury yields", "information_category": "rates", "priority": "must_have", "reason": "rates", "affected_channel": "treasury_yields", "linked_event_ids": [self.episode["primary_event_id"]], "linked_attention_labels": ["PRIMARY_DRIVER"], "available_now": "unknown", "suggested_source": "FROZEN_YIELDS", "expected_forecast_use": "context", "is_market_state_candidate": True},
                {"request_rank": 3, "requested_information": "US 2Y and 10Y Treasury yields", "information_category": "rates", "priority": "must_have", "reason": "duplicate", "affected_channel": "treasury_yields", "linked_event_ids": [], "linked_attention_labels": [], "available_now": "unknown", "suggested_source": "FROZEN_YIELDS", "expected_forecast_use": "context", "is_market_state_candidate": True},
                {"request_rank": 4, "requested_information": "Unmapped thing", "information_category": "novel_future_category", "priority": "novel", "reason": "must be normalized", "affected_channel": "unknown", "linked_event_ids": [], "linked_attention_labels": [], "available_now": "unknown", "suggested_source": "", "expected_forecast_use": "", "is_market_state_candidate": False},
                {"request_rank": 5, "requested_information": "Fed expectations", "information_category": "fed_expectations", "priority": "useful", "reason": "frozen exclusion", "affected_channel": "fed_path", "linked_event_ids": [], "linked_attention_labels": [], "available_now": "unknown", "suggested_source": "", "expected_forecast_use": "", "is_market_state_candidate": False},
            ],
        }
        self.environment = {"environment_id": "FIXTURE_SOURCE_ENV", "approved_source_ids": ["FROZEN_DXY", "FROZEN_YIELDS"]}

    def requests(self):
        return capability.compute_canonical_information_requests(self.episode, self.attention, "Gemini", "gemini-2.5-flash-lite", "REQUEST_PROMPT_V0", self.raw, self.cutoff)

    def records(self, requests=None):
        requests = requests or self.requests()
        by_category = {row["information_category"]: row["request_identity"] for row in requests}
        return [
            {"request_identity": by_category["dxy"], "status": "SUPPLIED", "source_id": "FROZEN_DXY", "source_name": "Frozen DXY", "source_timestamp": "2026-01-02T13:20:00Z", "as_of_timestamp": "2026-01-02T13:25:00Z", "acquisition_timestamp": "2026-01-02T13:28:00Z", "acquisition_method": "computed_feature", "source_items": [{"canonical_field": "DXY_LEVEL", "value": "109.1", "value_type": "index", "source_identity": "DXY", "source_timestamp": "2026-01-02T13:20:00Z", "as_of_timestamp": "2026-01-02T13:25:00Z"}]},
            {"request_identity": by_category["treasury_yields"], "status": "SUPPLIED", "source_id": "FROZEN_YIELDS", "source_name": "Frozen yields", "source_timestamp": "2026-01-02T13:20:00Z", "as_of_timestamp": "2026-01-02T13:25:00Z", "acquisition_timestamp": "2026-01-02T13:28:00Z", "acquisition_method": "deterministic_fetch", "source_items": [{"canonical_field": "US2Y_YIELD_LEVEL", "value": "4.20", "value_type": "percent", "source_identity": "US2Y", "source_timestamp": "2026-01-02T13:20:00Z", "as_of_timestamp": "2026-01-02T13:25:00Z"}, {"canonical_field": "US10Y_YIELD_LEVEL", "value": "4.50", "value_type": "percent", "source_identity": "US10Y", "source_timestamp": "2026-01-02T13:20:00Z", "as_of_timestamp": "2026-01-02T13:25:00Z"}]},
        ]

    def bundle(self, requests=None, records=None):
        return capability.build_immutable_acquired_information_bundle(requests or self.requests(), records if records is not None else self.records(requests), self.environment, self.cutoff, "2026-01-02T13:28:00Z")

    def pack(self, requests=None, bundle=None):
        requests = requests or self.requests()
        bundle = bundle or self.bundle(requests)
        manifest = {"manifest_id": "MANIFEST_FIXTURE_1", "bundle_id": bundle["bundle_id"], "authorized_source_environment_id": self.environment["environment_id"]}
        return capability.assemble_canonical_pack_e(self.episode, requests, bundle, manifest, capability.FROZEN_PACK_E_RULES_V1, self.cutoff)

    def test_request_normalization_order_identity_lineage_duplicates_and_unknown_category(self):
        first, second = self.requests(), self.requests()
        self.assertEqual(first, second)
        self.assertEqual([row["information_category"] for row in first], ["treasury_yields", "dxy", "other", "fed_expectations"])
        self.assertEqual([row["canonical_request_order"] for row in first], [1, 2, 3, 4])
        self.assertEqual(len({row["request_identity"] for row in first}), 4)
        self.assertEqual(first[0]["lineage"]["episode_id"], self.episode["episode_id"])
        self.assertEqual(first[0]["lineage"]["attention_id"], "ATTN_FIXTURE_1")
        self.assertEqual(first[0]["lineage"]["provider"], "Gemini")
        self.assertTrue(first[2]["normalization"]["category_normalized"])
        self.assertTrue(first[2]["normalization"]["priority_normalized"])

    def test_request_invalid_schema_and_attention_lineage_fail_closed(self):
        invalid = copy.deepcopy(self.raw); invalid["object"] = "wrong"
        with self.assertRaisesRegex(capability.PackCapabilityError, "REQUEST_RESPONSE_SCHEMA_INVALID"):
            capability.compute_canonical_information_requests(self.episode, self.attention, "Gemini", "gemini-2.5-flash-lite", "REQUEST_PROMPT_V0", invalid, self.cutoff)
        attention = dict(self.attention); attention["episode_id"] = "EP_OTHER"
        with self.assertRaisesRegex(capability.PackCapabilityError, "SELECTED_ATTENTION_EPISODE_MISMATCH"):
            capability.compute_canonical_information_requests(self.episode, attention, "Gemini", "gemini-2.5-flash-lite", "REQUEST_PROMPT_V0", self.raw, self.cutoff)

    def test_bundle_valid_pre_cutoff_is_stable_and_immutable(self):
        requests = self.requests()
        bundle = self.bundle(requests)
        self.assertEqual(bundle["bundle_fingerprint"], self.bundle(requests)["bundle_fingerprint"])
        self.assertEqual(len(bundle["items"]), len(requests))
        self.assertEqual(sum(row["status"] == "UNAVAILABLE" for row in bundle["items"]), 2)
        with self.assertRaises(TypeError):
            bundle["new"] = "not mutable"  # type: ignore[index]
        with self.assertRaises(TypeError):
            bundle["items"][0]["status"] = "changed"  # type: ignore[index]

    def test_bundle_rejects_post_cutoff_missing_provenance_unauthorized_source_and_lineage_mismatch(self):
        records = self.records()
        post_cutoff = copy.deepcopy(records); post_cutoff[0]["source_items"][0]["source_timestamp"] = "2026-01-02T13:30:00Z"
        with self.assertRaisesRegex(capability.PackCapabilityError, "POST_CUTOFF_INFORMATION"):
            self.bundle(records=post_cutoff)
        no_provenance = copy.deepcopy(records); no_provenance[0]["source_items"][0].pop("source_timestamp")
        no_provenance[0].pop("source_timestamp")
        with self.assertRaisesRegex(capability.PackCapabilityError, "SOURCE_TIMESTAMP_REQUIRED"):
            self.bundle(records=no_provenance)
        unauthorized = copy.deepcopy(records); unauthorized[0]["source_id"] = "NOT_APPROVED"
        with self.assertRaisesRegex(capability.PackCapabilityError, "UNAUTHORIZED_SOURCE"):
            self.bundle(records=unauthorized)
        wrong_request = copy.deepcopy(records); wrong_request[0]["request_identity"] = "PS21REQ_OTHER"
        with self.assertRaisesRegex(capability.PackCapabilityError, "ACQUISITION_REQUEST_LINEAGE_MISMATCH"):
            self.bundle(records=wrong_request)

    def test_pack_applies_inclusion_exclusion_dedup_ordering_cutoff_and_lineage(self):
        requests = self.requests(); bundle = self.bundle(requests); pack = self.pack(requests, bundle)
        self.assertEqual([row["item_key"] for row in pack["items"]], sorted(row["item_key"] for row in pack["items"]))
        self.assertEqual({row["item_key"] for row in pack["items"]}, {"DXY_LEVEL", "US2Y_YIELD_LEVEL", "US10Y_YIELD_LEVEL", "FED_EXPECTATIONS_POLICY_BLOCK", "UNMAPPED_CAPABILITY"})
        policy = next(row for row in pack["items"] if row["item_key"] == "FED_EXPECTATIONS_POLICY_BLOCK")
        self.assertEqual((policy["status"], policy["reason"]), ("POLICY_REJECTED", "FROZEN_FED_EXPECTATIONS_EXCLUSION"))
        self.assertEqual(pack["lineage"]["acquired_information_bundle_id"], bundle["bundle_id"])
        self.assertEqual(pack["pack_fingerprint"], self.pack(requests, bundle)["pack_fingerprint"])

    def test_pack_rejects_conflicting_duplicate_field_and_rules_change(self):
        requests = self.requests(); records = self.records(requests)
        duplicated = copy.deepcopy(records)
        duplicated[1]["source_items"].append({"canonical_field": "US2Y_YIELD_LEVEL", "value": "4.99", "value_type": "percent", "source_identity": "US2Y", "source_timestamp": "2026-01-02T13:20:00Z", "as_of_timestamp": "2026-01-02T13:25:00Z"})
        with self.assertRaisesRegex(capability.PackCapabilityError, "DUPLICATE_SOURCE_FIELD_FOR_REQUEST"):
            self.bundle(requests, duplicated)
        bundle = self.bundle(requests)
        changed_rules = capability.to_plain_data(capability.FROZEN_PACK_E_RULES_V1); changed_rules["ordering"] = "changed"
        manifest = {"manifest_id": "MANIFEST_FIXTURE_1", "bundle_id": bundle["bundle_id"], "authorized_source_environment_id": self.environment["environment_id"]}
        with self.assertRaisesRegex(capability.PackCapabilityError, "FROZEN_PACK_E_RULES_MISMATCH"):
            capability.assemble_canonical_pack_e(self.episode, requests, bundle, manifest, changed_rules, self.cutoff)

    def test_pack_deduplicates_identical_canonical_source_field_across_requests(self):
        raw = copy.deepcopy(self.raw)
        raw["information_items"].insert(1, {"request_rank": 2, "requested_information": "Dollar-index level", "information_category": "dxy", "priority": "useful", "reason": "same frozen field", "affected_channel": "usd_direction", "linked_event_ids": [], "linked_attention_labels": [], "available_now": "unknown", "suggested_source": "FROZEN_DXY", "expected_forecast_use": "context", "is_market_state_candidate": True})
        requests = capability.compute_canonical_information_requests(self.episode, self.attention, "Gemini", "gemini-2.5-flash-lite", "REQUEST_PROMPT_V0", raw, self.cutoff)
        records = self.records(requests)
        dxy_requests = [row for row in requests if row["information_category"] == "dxy"]
        records[0]["request_identity"] = dxy_requests[0]["request_identity"]
        records.append({**copy.deepcopy(records[0]), "request_identity": dxy_requests[1]["request_identity"]})
        bundle = self.bundle(requests, records)
        pack = self.pack(requests, bundle)
        dxy = [row for row in pack["items"] if row["item_key"] == "DXY_LEVEL"]
        self.assertEqual(len(dxy), 1)
        self.assertEqual(len(dxy[0]["request_identities"]), 2)

    def test_pack_preserves_unavailable_eligible_request_without_inventing_information(self):
        requests = self.requests()
        records = [row for row in self.records(requests) if row["request_identity"] != next(item["request_identity"] for item in requests if item["information_category"] == "dxy")]
        bundle = self.bundle(requests, records)
        pack = self.pack(requests, bundle)
        unavailable = next(row for row in pack["items"] if row["item_key"] == "DXY_PRESESSION_STATE")
        self.assertEqual(unavailable["status"], "UNAVAILABLE")
        self.assertEqual(unavailable["value"], "")

    def test_harness_and_boundary_isolation_have_no_destination_or_external_capability(self):
        original_open, original_connect = builtins.open, socket.create_connection
        def forbidden(*args, **kwargs):
            raise AssertionError("external or filesystem operation attempted")
        builtins.open = forbidden
        socket.create_connection = forbidden
        try:
            result = capability.run_offline_episode_to_pack_harness(
                episode=self.episode, selected_attention=self.attention, provider="Gemini", model="gemini-2.5-flash-lite",
                prompt_version="REQUEST_PROMPT_V0", raw_information_request_response=self.raw,
                supplied_acquisition_records=self.records(), authorized_source_environment=self.environment,
                acquisition_manifest={"manifest_id": "MANIFEST_FIXTURE_1"}, cutoff=self.cutoff,
                acquisition_timestamp="2026-01-02T13:28:00Z",
            )
        finally:
            builtins.open, socket.create_connection = original_open, original_connect
        self.assertIn("pack_e", result["checksums"])
        source = inspect.getsource(capability)
        for forbidden_token in ("build_sheets_service", "load_credentials", "requests.", "urllib", "socket.", "Path(", "open(", "output_root", "spreadsheet_id"):
            self.assertNotIn(forbidden_token, source)


if __name__ == "__main__":
    unittest.main()
