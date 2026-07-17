#!/usr/bin/env python3
"""Focused regression tests for AKSR Tier 2 institutional capabilities."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from automation.approved_knowledge_source_registry_v0 import initial_registry, route_request
from automation.institutional_source_adapters_v0 import (
    InstitutionalSourceError,
    _apollo_aem_article_links,
    _extract_pdf_text,
    _fetch_archive_bounded,
    _hydrate_pimco_archive_with_diagnostic,
    _json_ld_objects,
    _parse_apollo_aem_article,
    _parse_apollo_legacy_archive,
    match_request,
    parse_pimco_article,
)
from automation.run_phase9_historical_environment_institutional_enrichment_v0 import _bundle


class InstitutionalCapabilityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.request = {
            "session_id": "AKSR|2024-07-16|VALIDATION",
            "forecast_cutoff": "2024-07-16T12:00:00Z",
            "provider_request_id": "REQ_1",
            "normalized_request_id": "NREQ_1",
            "request_category": "inflation_narrative",
            "requested_concept": "current inflation narrative and Federal Reserve interpretation",
        }

    def test_apollo_legacy_parser_remains_compatible(self) -> None:
        page = '''<li class="wp-block-post"><time datetime="2024-07-15T10:00:00+00:00"></time>
        <a href="https://www.apolloacademy.com/inflation-test/">Inflation Test</a>
        <div class="entry-content">Inflation and Federal Reserve market expectations ''' + ("evidence " * 40) + "</div></div></li>"
        rows = _parse_apollo_legacy_archive(page, "https://www.apolloacademy.com/the-daily-spark/")
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["historical_page_state_proven"])
        self.assertEqual(rows[0]["source_id"], "KSRC_APOLLO_DAILY_SPARK")

    def test_apollo_aem_discovery_and_article_parsing(self) -> None:
        listing = '<a href="/wealth/insights-news/insights/daily-spark/inflation-test">Article</a>'
        links = _apollo_aem_article_links(listing)
        self.assertEqual(links, ["https://www.apollo.com/wealth/insights-news/insights/daily-spark/inflation-test"])
        article = '''<meta property="og:title" content="Inflation Test | The Daily Spark">
        <script>{"dateIsoFormat":"2026-07-16","date":"July 16, 2026"}</script>
        <main>Inflation and Federal Reserve market expectations ''' + ("evidence " * 80) + "</main>"
        row = _parse_apollo_aem_article(article, links[0])
        self.assertEqual(row["publication_timestamp"], "2026-07-16")
        self.assertEqual(row["timestamp_precision"], "DATE_ONLY")
        self.assertFalse(row["historical_page_state_proven"])

    def test_jsonld_graph_and_pimco_parser(self) -> None:
        page = '''<script type="application/ld+json">{"@graph":[{"@type":"NewsArticle",
        "headline":"Inflation Outlook","datePublished":"2024-07-11T00:00:00+00:00",
        "dateModified":"2024-07-12T00:00:00+00:00","keywords":"inflation fed"}]}</script>
        <main>Inflation Federal Reserve policy market outlook ''' + ("evidence " * 80) + "</main>"
        self.assertEqual(len(list(_json_ld_objects(page))), 2)
        row = parse_pimco_article(page, "https://www.pimco.com/us/en/insights/inflation-outlook")
        self.assertEqual(row["source_id"], "KSRC_PIMCO_INSIGHTS")
        self.assertEqual(row["timestamp_precision"], "DATE_ONLY")

    def test_pimco_historical_snapshot_failure_is_explicit(self) -> None:
        response = Mock()
        response.json.return_value = [["timestamp", "original", "statuscode", "digest"]]
        with patch("automation.institutional_source_adapters_v0._fetch", return_value=response):
            row, detail = _hydrate_pimco_archive_with_diagnostic({
                "canonical_url": "https://www.pimco.com/us/en/insights/test",
                "publication_timestamp": "2024-07-11",
                "timestamp_precision": "DATE_ONLY",
            }, datetime(2024, 7, 16, 12, tzinfo=timezone.utc))
        self.assertIsNone(row)
        self.assertEqual(detail, "ARCHIVE_SNAPSHOT_NOT_FOUND_BEFORE_CUTOFF")

    def test_archive_transport_has_one_bounded_retry(self) -> None:
        response = Mock()
        with patch("automation.institutional_source_adapters_v0._fetch", side_effect=[
            __import__("requests").Timeout("transient"), response,
        ]) as fetch:
            self.assertIs(_fetch_archive_bounded("https://web.archive.org/test"), response)
        self.assertEqual(fetch.call_count, 2)

    def test_pimco_historical_match_uses_pinned_snapshot(self) -> None:
        row = {
            "source_record_id": "P1", "source_id": "KSRC_PIMCO_INSIGHTS", "source_family": "PIMCO_INSIGHTS",
            "publisher": "PIMCO", "title": "Inflation and Fed outlook", "canonical_url": "https://www.pimco.com/test",
            "publication_timestamp": "2024-07-11", "timestamp_precision": "DATE_ONLY", "retrieval_timestamp": "2026-07-17T00:00:00Z",
            "article_type": "EVENT_SPECIFIC", "narrative_scope": "EVENT_SPECIFIC",
            "relevant_text": "Inflation Federal Reserve market policy outlook " + ("evidence " * 80),
            "content_fingerprint": "a" * 64, "historical_page_state_proven": False,
            "historical_state_evidence": "CURRENT_PAGE", "revision_status": "VERSION_PINNED",
        }
        pinned = {**row, "historical_page_state_proven": True, "historical_state_evidence": "WAYBACK_PRE_CUTOFF_SNAPSHOT:20240715111958"}
        with patch("automation.institutional_source_adapters_v0._hydrate_pimco_archive_with_diagnostic", return_value=(pinned, "PASS")):
            result = match_request([row], self.request, mode="HISTORICAL_REPLAY")
        self.assertEqual(len(result.admitted), 1)
        self.assertTrue(result.admitted[0]["historical_page_state_proven"])

    def test_prospective_pimco_does_not_claim_historical_archive(self) -> None:
        row = {
            "source_record_id": "P1", "source_id": "KSRC_PIMCO_INSIGHTS", "source_family": "PIMCO_INSIGHTS",
            "publisher": "PIMCO", "title": "Inflation and Fed outlook", "canonical_url": "https://www.pimco.com/test",
            "publication_timestamp": "2024-07-11", "timestamp_precision": "DATE_ONLY", "retrieval_timestamp": "2024-07-15T00:00:00Z",
            "article_type": "EVENT_SPECIFIC", "narrative_scope": "EVENT_SPECIFIC",
            "relevant_text": "Inflation Federal Reserve market policy outlook " + ("evidence " * 80),
            "content_fingerprint": "a" * 64, "historical_page_state_proven": False,
            "historical_state_evidence": "CURRENT_PAGE", "revision_status": "VERSION_PINNED",
        }
        with patch("automation.institutional_source_adapters_v0._hydrate_pimco_archive_with_diagnostic") as hydrate:
            result = match_request([row], self.request, mode="PROSPECTIVE_COLLECTION")
        hydrate.assert_not_called()
        self.assertEqual(len(result.admitted), 1)
        self.assertIn("PROSPECTIVE_PRE_CUTOFF_PAGE_CAPTURE", result.admitted[0]["historical_state_evidence"])

    def test_blackrock_html_access_gate_is_not_parsed_as_pdf(self) -> None:
        response = Mock()
        response.content = b"<!DOCTYPE html><html><title>BlackRock Corporate Website | BlackRock</title><link rel='canonical' href='https://www.blackrock.com/corporate'><body>Before we proceed, review and accept the following terms and conditions. By indicating your consent.</body></html>"
        response.text = response.content.decode("utf-8")
        response.status_code = 200
        response.url = "https://www.blackrock.com/test.pdf"
        response.history = []
        response.headers = {"Content-Type": "text/html;charset=UTF-8"}
        with patch("automation.institutional_source_adapters_v0._fetch", return_value=response):
            with self.assertRaisesRegex(InstitutionalSourceError, "CONSENT_GATE_HTML_RESPONSE"):
                _extract_pdf_text("https://www.blackrock.com/test.pdf")

    def test_aksr_capabilities_are_mode_specific(self) -> None:
        rows = initial_registry()
        request = {**self.request, "request_category": "TREASURY_INTERPRETATION"}
        historical = {row["source_id"] for row in route_request(request, "HISTORICAL_REPLAY", rows)["source_routes"]}
        prospective = {row["source_id"] for row in route_request(request, "PROSPECTIVE_COLLECTION", rows)["source_routes"]}
        self.assertIn("KSRC_PIMCO_INSIGHTS", historical)
        self.assertIn("KSRC_PIMCO_INSIGHTS", prospective)
        self.assertIn("KSRC_BLACKROCK_INVESTMENT_INSTITUTE", historical)
        self.assertIn("KSRC_BLACKROCK_INVESTMENT_INSTITUTE", prospective)

    def test_archived_snapshot_controls_historical_availability(self) -> None:
        source = {
            "source_record_id": "P1", "source_family": "PIMCO_INSIGHTS", "publisher": "PIMCO",
            "title": "Inflation outlook", "canonical_url": "https://www.pimco.com/test",
            "publication_timestamp": "2024-07-11T00:00:00Z", "timestamp_precision": "DATE_ONLY",
            "narrative_scope": "EVENT_SPECIFIC", "publication_age_hours": 120.0,
            "relevant_text": "Inflation and Federal Reserve policy " + ("evidence " * 80),
            "content_fingerprint": "a" * 64, "archive_snapshot_timestamp": "20240715111958",
            "cited_underlying_sources": [],
        }
        request = {
            **self.request, "information_key": "inflation_narrative|current",
            "requested_concept": "current inflation narrative",
        }
        bundle = _bundle(request, [source], "2026-07-17T00:00:00Z")
        self.assertEqual(bundle["historical_availability_timestamp"], "2024-07-15T11:19:58Z")
        self.assertEqual(bundle["source_tier"], "TIER_2_INSTITUTIONAL_RESEARCH")


if __name__ == "__main__":
    unittest.main()
