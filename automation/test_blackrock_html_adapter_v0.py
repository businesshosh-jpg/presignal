#!/usr/bin/env python3
"""Focused BlackRock HTML acquisition and fail-closed regression tests."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from automation.approved_knowledge_source_registry_v0 import (
    admit_knowledge_item,
    build_traceability_record,
    initial_registry,
    route_request,
    validate_registry,
)
from automation.institutional_source_adapters_v0 import (
    InstitutionalSourceError,
    _PDF_TEXT_CACHE,
    _extract_pdf_text,
    blackrock_html_source_record,
    classify_blackrock_html_response,
    match_request,
)


def _response(page: str, *, status: int = 200, url: str = "https://www.blackrock.com/corporate/insights/blackrock-investment-institute/publications/weekly-commentary") -> Mock:
    response = Mock()
    response.text = page
    response.content = page.encode("utf-8")
    response.status_code = status
    response.url = url
    response.headers = {"Content-Type": "text/html;charset=UTF-8"}
    response.history = []
    return response


def _research_page(*, publication: str = "May 13, 2024", modified: bool = False) -> str:
    revision = '<meta property="article:modified_time" content="2024-05-14T10:00:00Z">' if modified else ""
    paragraphs = "".join(
        "<p>BlackRock Investment Institute describes equity risk, policy expectations, yen conditions, and market uncertainty in a source-grounded institutional research paragraph %s.</p>" % index
        for index in range(12)
    )
    return f'''<!DOCTYPE html><html><head><title>Weekly market commentary | BlackRock Investment Institute</title>
    <link rel="canonical" href="https://www.blackrock.com/corporate/insights/blackrock-investment-institute/publications/weekly-commentary">{revision}</head>
    <body><div>Before we proceed, please review the terms and conditions.</div>
    <h1>Weekly market commentary</h1><div>Market insights Weekly market commentary {publication} BlackRock Investment Institute</div>
    <h2>Weak yen unlikely to end Japan's rally</h2><h3>Our bottom line</h3>{paragraphs}
    <h2>On the go?</h2><h3>Research Author</h3></body></html>'''


class BlackRockHtmlAdapterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = initial_registry()
        self.request = {
            "session_id": "AKSR|2024-05-17|BLACKROCK_HTML",
            "forecast_cutoff": "2024-05-17T12:00:00Z",
            "provider": "OpenAI",
            "provider_request_id": "BR_REQ_1",
            "normalized_request_id": "BR_NREQ_1",
            "request_category": "risk_sentiment",
            "requested_concept": "institutional equity risk sentiment and Japan market framing",
        }

    def test_research_html_is_recognized_despite_global_terms_text(self) -> None:
        diagnostic = classify_blackrock_html_response(_response(_research_page()))
        self.assertEqual(diagnostic["classification_result"], "RESEARCH_LANDING_PAGE_WITH_CONTENT")
        self.assertEqual(diagnostic["admission_eligibility"], "ELIGIBLE_FOR_REQUEST_SPECIFIC_VALIDATION")
        self.assertEqual(diagnostic["article_title"], "Weak yen unlikely to end Japan's rally")

    def test_consent_gate_remains_rejected(self) -> None:
        page = '''<html><head><title>BlackRock Corporate Website | BlackRock</title>
        <link rel="canonical" href="https://www.blackrock.com/corporate"></head>
        <body>Before we proceed, review and accept the following terms and conditions. By indicating your consent.</body></html>'''
        diagnostic = classify_blackrock_html_response(_response(page, url="https://www.blackrock.com/test.pdf"))
        self.assertEqual(diagnostic["classification_result"], "CONSENT_OR_COOKIE_GATE")
        self.assertEqual(diagnostic["rejection_reason"], "CONSENT_GATE_HTML_RESPONSE")

    def test_access_gate_and_navigation_shell_remain_rejected(self) -> None:
        access = classify_blackrock_html_response(_response("<html><body>Access denied. Login required.</body></html>"))
        nav = classify_blackrock_html_response(_response("<html><body>Skip to content Navigation Corporate Legal</body></html>"))
        self.assertEqual(access["classification_result"], "DOCUMENT_ACCESS_GATE")
        self.assertEqual(nav["classification_result"], "REDIRECT_OR_NAVIGATION_PAGE")

    def test_html_is_never_passed_to_pdf_parser(self) -> None:
        page = "<html><body>Access denied. Login required.</body></html>"
        with patch("automation.institutional_source_adapters_v0._fetch", return_value=_response(page, url="https://www.blackrock.com/test.pdf")), patch("automation.institutional_source_adapters_v0.subprocess.run") as parser:
            with self.assertRaisesRegex(InstitutionalSourceError, "DOCUMENT_ACCESS_GATE_HTML_RESPONSE"):
                _extract_pdf_text("https://www.blackrock.com/test.pdf")
        parser.assert_not_called()

    def test_genuine_pdf_still_uses_pdf_parser(self) -> None:
        url = "https://www.blackrock.com/genuine-test.pdf"
        _PDF_TEXT_CACHE.pop(url, None)
        response = Mock(content=b"%PDF-1.4 fixture", headers={"Content-Type": "application/pdf"})
        completed = SimpleNamespace(stdout="BlackRock research text", returncode=0)
        with patch("automation.institutional_source_adapters_v0._fetch", return_value=response), patch("automation.institutional_source_adapters_v0.subprocess.run", return_value=completed) as parser:
            self.assertEqual(_extract_pdf_text(url), "BlackRock research text")
        parser.assert_called_once()

    def test_date_only_precision_and_same_day_cutoff_fail_closed(self) -> None:
        diagnostic = classify_blackrock_html_response(_response(_research_page()))
        source = blackrock_html_source_record(diagnostic, archive_snapshot_timestamp="20240516092434")
        self.assertEqual(source["timestamp_precision"], "DATE_ONLY")
        same_day = {**self.request, "forecast_cutoff": "2024-05-13T23:00:00Z"}
        result = match_request([source], same_day, mode="HISTORICAL_REPLAY")
        self.assertEqual(result.rejected[0]["rejection_reason"], "SAME_DAY_TIME_UNPROVABLE")

    def test_post_cutoff_html_is_rejected(self) -> None:
        diagnostic = classify_blackrock_html_response(_response(_research_page()))
        source = blackrock_html_source_record(diagnostic, archive_snapshot_timestamp="20240516092434")
        request = {**self.request, "forecast_cutoff": "2024-05-12T23:59:59Z"}
        result = match_request([source], request, mode="HISTORICAL_REPLAY")
        self.assertEqual(result.rejected[0]["rejection_reason"], "SOURCE_AFTER_FORECAST_CUTOFF")

    def test_revision_indicators_are_preserved_under_version_pin_policy(self) -> None:
        diagnostic = classify_blackrock_html_response(_response(_research_page(modified=True)))
        source = blackrock_html_source_record(diagnostic, archive_snapshot_timestamp="20240516092434")
        self.assertTrue(diagnostic["revision_indicators"])
        self.assertEqual(source["revision_status"], "VERSION_PINNED")
        item = {
            **source, "knowledge_item_id": source["source_record_id"], "relevance_status": "PASS",
            "outcome_leakage_status": "PASS",
        }
        admission = admit_knowledge_item(item, self.request, "HISTORICAL_REPLAY", self.rows)
        self.assertEqual(admission["article_admission_status"], "ADMITTED")

    def test_request_source_evidence_pack_traceability(self) -> None:
        diagnostic = classify_blackrock_html_response(_response(_research_page()))
        source = blackrock_html_source_record(diagnostic, archive_snapshot_timestamp="20240516092434")
        route = route_request(self.request, "HISTORICAL_REPLAY", self.rows)
        trace = build_traceability_record(
            request=self.request, route=route, knowledge_item=source,
            luna_evidence={"source_id": source["source_id"], "luna_evidence_id": "BR_LUNA_1"},
            pack_entry={"pack_entry_id": "BR_PACK_1", "luna_evidence_id": "BR_LUNA_1"},
            mode="HISTORICAL_REPLAY",
        )
        self.assertEqual(trace["traceability_status"], "PASS")

    def test_aksr_integrity_and_blackrock_mode_routing(self) -> None:
        self.assertEqual(validate_registry(self.rows)["status"], "PASS")
        historical = route_request(self.request, "HISTORICAL_REPLAY", self.rows)
        prospective = route_request(self.request, "PROSPECTIVE_COLLECTION", self.rows)
        self.assertIn("KSRC_BLACKROCK_INVESTMENT_INSTITUTE", {row["source_id"] for row in historical["source_routes"]})
        self.assertIn("KSRC_BLACKROCK_INVESTMENT_INSTITUTE", {row["source_id"] for row in prospective["source_routes"]})


if __name__ == "__main__":
    unittest.main()
