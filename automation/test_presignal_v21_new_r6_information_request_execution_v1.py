"""Focused offline tests for the bounded FOMC Information-Request runner."""
from __future__ import annotations

import json
import unittest

from automation import run_presignal_v21_new_r6_information_request_execution_v1 as execution


TRANSPORT = {"actual_provider": "Gemini", "actual_model": "gemini-2.5-flash-lite"}


def item(category: str = "fed_expectations", requested: str = "What are current market-implied probabilities and economist expectations for the upcoming Fed rate decision?", source: str = "CME") -> dict[str, object]:
    return {"request_rank": 1, "information_category": category, "requested_information": requested,
            "priority": "must_have", "reason": "Pre-release policy expectation context is needed.",
            "affected_channel": "fed_path", "event_family_relevance": "FOMC", "linked_event_ids": ["5ea0-ce20-ad20-fba0"],
            "linked_attention_labels": ["PRIMARY_DRIVER"], "available_now": True, "suggested_source": source,
            "expected_forecast_use": "Context", "is_market_state_candidate": True}


def payload(items: list[dict[str, object]]) -> str:
    return json.dumps({"object": "session_information_requirements", "status": "ok", "provider": "CME", "session_id": "not-authoritative", "information_items": items})


class NewR6InformationRequestExecutionTest(unittest.TestCase):
    def test_valid_payload_preserves_gemini_as_provider(self) -> None:
        normalized, rows, report = execution.normalize_response(payload([item()]), TRANSPORT, "sha256:fixture")
        self.assertEqual(normalized["canonical_provider_identity"], "Gemini")
        self.assertEqual(rows[0]["requested_source_identity"], "CME")
        self.assertFalse(report["raw_payload_provider_treated_as_gemini_alias"])

    def test_all_frozen_categories_are_accepted(self) -> None:
        items = [item(category=category, requested=f"What current pre-release context is relevant for {category}?") for category in sorted(execution.lineage.VALID_CATEGORIES)]
        _, rows, _ = execution.normalize_response(payload(items), TRANSPORT, "sha256:fixture")
        self.assertEqual(len(rows), 16)

    def test_unknown_category_fails_closed(self) -> None:
        with self.assertRaisesRegex(execution.RequestValidationError, "REQUEST_CATEGORY_INVALID"):
            execution.normalize_response(payload([item(category="Federal Reserve")]), TRANSPORT, "sha256:fixture")

    def test_upcoming_actual_and_post_release_fail_closed(self) -> None:
        for requested in ("What rate did the Fed announce for the upcoming decision?", "How did USD/JPY react after this release?"):
            with self.assertRaisesRegex(execution.RequestValidationError, "REQUEST_TEMPORAL_SCOPE_INVALID"):
                execution.normalize_response(payload([item(requested=requested)]), TRANSPORT, "sha256:fixture")

    def test_exact_duplicates_collapse_and_conflicts_fail(self) -> None:
        one = item(); duplicate = dict(one); duplicate["request_rank"] = 2
        _, rows, report = execution.normalize_response(payload([one, duplicate]), TRANSPORT, "sha256:fixture")
        self.assertEqual(len(rows), 1); self.assertEqual(report["duplicate_count"], 1)
        conflict = dict(one); conflict["information_category"] = "treasury_yields"
        with self.assertRaisesRegex(execution.RequestValidationError, "REQUEST_RESPONSE_SCHEMA_INVALID"):
            execution.normalize_response(payload([one, conflict]), TRANSPORT, "sha256:fixture")


if __name__ == "__main__":
    unittest.main()
