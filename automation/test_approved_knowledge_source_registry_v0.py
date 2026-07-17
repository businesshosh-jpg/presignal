#!/usr/bin/env python3

from __future__ import annotations

import copy
import unittest

from automation.approved_knowledge_source_registry_v0 import (
    LIFECYCLE_STAGES,
    PROVENANCE_POLICIES,
    REGISTRY_VERSION,
    RegistryError,
    admit_knowledge_item,
    build_traceability_record,
    initial_registry,
    registry_fingerprint,
    replay_compatibility_aliases,
    resolve_source,
    route_request,
    suppress_duplicate_items,
    transition_source_lifecycle,
    validate_registry,
    validate_source_use,
)


class ApprovedKnowledgeSourceRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = initial_registry()
        self.request = {
            "session_id": "US|2024-05-20|CUSTOM_CONFIG_WINDOW",
            "forecast_cutoff": "2024-05-20T13:00:00Z",
            "provider": "OpenAI",
            "provider_request_id": "REQ_1",
            "normalized_request_id": "NREQ_1",
            "request_category": "INFLATION_NARRATIVE",
            "requested_concept": "Current inflation narrative",
        }

    def test_initial_registry_integrity_and_population(self) -> None:
        validation = validate_registry(self.rows)
        self.assertEqual(validation["status"], "PASS")
        self.assertEqual(validation["source_count"], 16)
        self.assertEqual(len({row["source_id"] for row in self.rows}), 16)
        expected = {
            "KSRC_FEDERAL_RESERVE", "KSRC_FEDERAL_RESERVE_RESEARCH", "KSRC_NEW_YORK_FED",
            "KSRC_BLS", "KSRC_BEA", "KSRC_US_TREASURY", "KSRC_CENSUS", "KSRC_FRED",
            "KSRC_APOLLO_DAILY_SPARK", "KSRC_PIMCO_INSIGHTS", "KSRC_BLACKROCK_INVESTMENT_INSTITUTE",
            "KSRC_EODHD", "KSRC_FMP", "KSRC_UNIVERSITY_OF_MICHIGAN", "KSRC_CME_FEDWATCH",
            "KSRC_CONFERENCE_BOARD",
        }
        self.assertEqual({row["source_id"] for row in self.rows}, expected)

    def test_registry_fingerprint_is_order_independent(self) -> None:
        self.assertEqual(registry_fingerprint(self.rows), registry_fingerprint(list(reversed(self.rows))))

    def test_configured_routing_matches_stage4a_priorities(self) -> None:
        examples = {
            "FED_EXPECTATIONS": ["KSRC_APOLLO_DAILY_SPARK", "KSRC_PIMCO_INSIGHTS", "KSRC_BLACKROCK_INVESTMENT_INSTITUTE", "KSRC_NEW_YORK_FED"],
            "INFLATION_NARRATIVE": ["KSRC_BLS", "KSRC_PIMCO_INSIGHTS", "KSRC_BLACKROCK_INVESTMENT_INSTITUTE"],
            "TREASURY_INTERPRETATION": ["KSRC_PIMCO_INSIGHTS", "KSRC_US_TREASURY", "KSRC_BLACKROCK_INVESTMENT_INSTITUTE"],
            "CONSUMER_OUTLOOK": ["KSRC_BEA", "KSRC_PIMCO_INSIGHTS"],
            "RISK_SENTIMENT": ["KSRC_APOLLO_DAILY_SPARK", "KSRC_BLACKROCK_INVESTMENT_INSTITUTE"],
        }
        for topic, expected_prefix in examples.items():
            request = {**self.request, "request_category": topic}
            routed = route_request(request, "HISTORICAL_REPLAY", self.rows)
            actual = [row["source_id"] for row in routed["configured_routes"]]
            self.assertEqual(actual[: len(expected_prefix)], expected_prefix)

    def test_routing_is_provider_neutral(self) -> None:
        openai = route_request(self.request, "HISTORICAL_REPLAY", self.rows)
        anthropic = route_request({**self.request, "provider": "Anthropic"}, "HISTORICAL_REPLAY", self.rows)
        self.assertEqual(openai["route_id"], anthropic["route_id"])
        self.assertEqual(openai["source_routes"], anthropic["source_routes"])

    def test_historical_and_prospective_capabilities_are_independent(self) -> None:
        request = {**self.request, "request_category": "TREASURY_INTERPRETATION"}
        historical = route_request(request, "HISTORICAL_REPLAY", self.rows)
        prospective = route_request(request, "PROSPECTIVE_COLLECTION", self.rows)
        historical_ids = {row["source_id"] for row in historical["source_routes"]}
        prospective_ids = {row["source_id"] for row in prospective["source_routes"]}
        self.assertIn("KSRC_PIMCO_INSIGHTS", historical_ids)
        self.assertIn("KSRC_PIMCO_INSIGHTS", prospective_ids)
        self.assertIn("KSRC_BLACKROCK_INVESTMENT_INSTITUTE", historical_ids)
        self.assertIn("KSRC_BLACKROCK_INVESTMENT_INSTITUTE", prospective_ids)

    def test_unvalidated_capability_fails_closed(self) -> None:
        allowed, reason = validate_source_use("NEW_YORK_FED", "HISTORICAL_REPLAY", "FED_EXPECTATIONS", self.rows)
        self.assertFalse(allowed)
        self.assertEqual(reason, "HISTORICAL_REPLAY_NOT_VALIDATED")

    def test_source_class_provenance_is_configurable(self) -> None:
        classes = {row["source_class"] for row in self.rows}
        for source_class in classes:
            policy = PROVENANCE_POLICIES["AKSR_PROV_" + source_class]
            self.assertEqual(policy["source_class"], source_class)
            self.assertIn("historical", policy)
            self.assertIn("prospective", policy)

    def test_lifecycle_requires_sequential_evidenced_transitions(self) -> None:
        row = copy.deepcopy(self.rows[0])
        row["lifecycle_stage"] = LIFECYCLE_STAGES[0]
        next_row = transition_source_lifecycle(row, "TECHNICAL_VALIDATION", {
            "validation_id": "VAL_1", "validated_at": "2026-07-16T00:00:00Z", "notes": "fixture",
        })
        self.assertEqual(next_row["lifecycle_stage"], "TECHNICAL_VALIDATION")
        with self.assertRaisesRegex(RegistryError, "NOT_SEQUENTIAL"):
            transition_source_lifecycle(row, "HISTORICAL_VALIDATION", {"validation_id": "VAL_2"})
        with self.assertRaisesRegex(RegistryError, "EVIDENCE_REQUIRED"):
            transition_source_lifecycle(row, "TECHNICAL_VALIDATION", {})

    def _knowledge_item(self, **overrides):
        row = {
            "knowledge_item_id": "ITEM_1",
            "source_id": "KSRC_BLS",
            "publication_timestamp": "2024-05-20T12:00:00Z",
            "timestamp_precision": "EXACT_DATETIME",
            "publisher": "U.S. Bureau of Labor Statistics",
            "canonical_url": "https://www.bls.gov/example",
            "content_fingerprint": "a" * 64,
            "historical_state_evidence": "OFFICIAL_DATED_RELEASE",
            "relevance_status": "PASS",
            "outcome_leakage_status": "PASS",
        }
        row.update(overrides)
        return row

    def test_article_admission_is_separate_and_passes_valid_pre_cutoff_item(self) -> None:
        admitted = admit_knowledge_item(self._knowledge_item(), self.request, "HISTORICAL_REPLAY", self.rows)
        self.assertEqual(admitted["source_approval_status"], "PASS")
        self.assertEqual(admitted["article_admission_status"], "ADMITTED")
        self.assertEqual(admitted["rejection_reasons"], [])

    def test_post_cutoff_item_is_rejected(self) -> None:
        rejected = admit_knowledge_item(
            self._knowledge_item(publication_timestamp="2024-05-20T13:00:01Z"),
            self.request, "HISTORICAL_REPLAY", self.rows,
        )
        self.assertIn("SOURCE_AFTER_FORECAST_CUTOFF", rejected["rejection_reasons"])

    def test_same_day_date_only_item_is_rejected(self) -> None:
        rejected = admit_knowledge_item(
            self._knowledge_item(publication_timestamp="2024-05-20", timestamp_precision="DATE_ONLY"),
            self.request, "HISTORICAL_REPLAY", self.rows,
        )
        self.assertIn("SAME_DAY_TIME_UNPROVABLE", rejected["rejection_reasons"])

    def test_institutional_revision_state_is_required(self) -> None:
        item = self._knowledge_item(
            source_id="KSRC_APOLLO_DAILY_SPARK",
            publisher="Apollo Global Management",
            canonical_url="https://www.apolloacademy.com/example",
        )
        rejected = admit_knowledge_item(item, self.request, "HISTORICAL_REPLAY", self.rows)
        self.assertIn("REVISION_STATE_UNPROVABLE", rejected["rejection_reasons"])
        item["revision_status"] = "NO_SUBSTANTIVE_REVISION_DETECTED"
        admitted = admit_knowledge_item(item, self.request, "HISTORICAL_REPLAY", self.rows)
        self.assertEqual(admitted["article_admission_status"], "ADMITTED")

    def test_duplicate_suppression_is_deterministic(self) -> None:
        item = self._knowledge_item()
        accepted, duplicates = suppress_duplicate_items([item, dict(item)])
        self.assertEqual(len(accepted), 1)
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0]["duplicate_status"], "SOURCE_DUPLICATE")

    def test_traceability_links_request_through_pack_entry(self) -> None:
        route = route_request(self.request, "HISTORICAL_REPLAY", self.rows)
        trace = build_traceability_record(
            request=self.request,
            route=route,
            knowledge_item={"source_id": "KSRC_BLS", "knowledge_item_id": "ITEM_1"},
            luna_evidence={"source_id": "KSRC_BLS", "luna_evidence_id": "LUNA_1"},
            pack_entry={"pack_entry_id": "PACK_1", "luna_evidence_id": "LUNA_1"},
            mode="HISTORICAL_REPLAY",
        )
        self.assertEqual(trace["traceability_status"], "PASS")
        self.assertEqual(trace["registry_version"], REGISTRY_VERSION)
        with self.assertRaisesRegex(RegistryError, "PACK_EVIDENCE_MISMATCH"):
            build_traceability_record(
                request=self.request,
                route=route,
                knowledge_item={"source_id": "KSRC_BLS", "knowledge_item_id": "ITEM_1"},
                luna_evidence={"source_id": "KSRC_BLS", "luna_evidence_id": "LUNA_1"},
                pack_entry={"pack_entry_id": "PACK_1", "luna_evidence_id": "OTHER"},
                mode="HISTORICAL_REPLAY",
            )

    def test_replay_aliases_cover_existing_environment_source_families(self) -> None:
        aliases = replay_compatibility_aliases()
        self.assertEqual(aliases["FOMC_POLICY_INTERPRETATION"], "KSRC_FEDERAL_RESERVE")
        self.assertEqual(aliases["APOLLO_DAILY_SPARK"], "KSRC_APOLLO_DAILY_SPARK")
        self.assertEqual(aliases["EODHD"], "KSRC_EODHD")
        self.assertEqual(resolve_source("FINANCIAL_MODELING_PREP", self.rows)["source_id"], "KSRC_FMP")

    def test_unregistered_source_fails_closed(self) -> None:
        with self.assertRaisesRegex(RegistryError, "SOURCE_NOT_REGISTERED"):
            resolve_source("UNAPPROVED_BLOG", self.rows)


if __name__ == "__main__":
    unittest.main()
