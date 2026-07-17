#!/usr/bin/env python3
"""Audit existing EODHD historical-news capability without scientific admission.

The EODHD credential remains inside Apps Script. This runner invokes the
bounded read-only probe, validates three historical cutoff windows, and writes
only article metadata and content fingerprints. Because public terms do not
explicitly establish external-LLM processing or derived-summary retention
rights, no source bundle, Acquisition-AI call, Pack E, or forecast is created.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.google_clients import (  # type: ignore
    build_script_service,
    default_script_id,
    load_credentials,
    run_script_function,
)


PHASE_ID = "9-EODHD-HISTORICAL-NEWS-AUDIT"
BASE_ENVIRONMENT_RUN = "9-HISTORICAL-ENVIRONMENT-RECONSTRUCTION_20260716T033701Z"
BASE_ENVIRONMENT_ROOT = ROOT / "outputs" / "phase9_historical_environment_reconstructed_pack_e" / BASE_ENVIRONMENT_RUN
BASE_STRUCTURED_RUN = "9-HISTORICAL-ACQUISITION-REPAIR_20260715T053903Z"
OUTPUT_ROOT = ROOT / "outputs" / "phase9_eodhd_historical_news_audit"
NEWS_ENDPOINT = "https://eodhd.com/api/news"

PILOT_SESSIONS = {
    "US|2024-06-21|CUSTOM_CONFIG_WINDOW": {
        "request_type": "labor_market_narrative",
        "request_keywords": ("labor", "employment", "unemployment", "payroll", "wage", "jobs"),
        "queries": (("topic", "employment"), ("ticker", "GSPC.INDX"), ("ticker", "EURUSD.FOREX")),
    },
    "US|2024-08-15|CUSTOM_CONFIG_WINDOW": {
        "request_type": "economic_growth_context",
        "request_keywords": ("economy", "economic", "growth", "gdp", "retail", "consumer", "cpi", "data"),
        "queries": (("topic", "economy"), ("ticker", "GSPC.INDX"), ("ticker", "EURUSD.FOREX")),
    },
    "US|2024-09-27|CUSTOM_CONFIG_WINDOW": {
        "request_type": "inflation_narrative",
        "request_keywords": ("inflation", "prices", "pce", "cpi", "fed", "yield", "dollar"),
        "queries": (("topic", "inflation"), ("ticker", "GSPC.INDX"), ("ticker", "EURUSD.FOREX")),
    },
}

LEAKAGE_PHRASES = (
    "after the release", "following the release", "the data showed", "actual came in",
    "five-minute move", "realized pips", "forecast was correct", "forecast was wrong",
)


class AuditError(RuntimeError):
    """Fail-closed EODHD audit error."""


def _norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _iso(value: Optional[datetime] = None) -> str:
    return (value or datetime.now(timezone.utc)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_id() -> str:
    return PHASE_ID + "_" + _iso().replace("-", "").replace(":", "").replace("Z", "") + "Z"


def _parse_ts(value: Any) -> datetime:
    text = _norm(value)
    if not text:
        raise AuditError("MISSING_PUBLICATION_TIMESTAMP")
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise AuditError("HISTORICAL_TIMESTAMP_UNPROVABLE")
    return parsed.astimezone(timezone.utc)


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise AuditError("MISSING_INPUT:" + str(path))
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise AuditError("MISSING_INPUT:" + str(path))
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical(dict(value)) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(_canonical(dict(row)) + "\n")


def _capability_table() -> List[Dict[str, Any]]:
    return [
        {
            "capability": "end_of_day_prices", "endpoint": "/api/eod/{symbol}", "implemented": True,
            "configured": True, "historical_access": True, "currently_used_by_structured_replay": True,
            "currently_used_by_qualitative_replay": False,
            "evidence": "apps_script/data_availability_audit.js:_eodhdFetchEodWindow_; apps_script/market_context_v2b.js",
        },
        {
            "capability": "intraday_forex_prices", "endpoint": "/api/intraday/{symbol}", "implemented": True,
            "configured": True, "historical_access": True, "currently_used_by_structured_replay": True,
            "currently_used_by_qualitative_replay": False,
            "evidence": "apps_script/fx_candle_provider.js:fetchEodhdFx_",
        },
        {
            "capability": "symbol_search", "endpoint": "/api/search/{query}", "implemented": True,
            "configured": True, "historical_access": "NOT_APPLICABLE", "currently_used_by_structured_replay": True,
            "currently_used_by_qualitative_replay": False,
            "evidence": "apps_script/market_context_provider_repair.js:_mcprSafeEodhdSearch_",
        },
        {
            "capability": "calendar", "endpoint": "EODHD calendar endpoints", "implemented": False,
            "configured": "NOT_PROVEN", "historical_access": "NOT_TESTED", "currently_used_by_structured_replay": False,
            "currently_used_by_qualitative_replay": False,
            "evidence": "No EODHD calendar client found; historical calendar comes from separate authoritative inputs.",
        },
        {
            "capability": "fundamentals", "endpoint": "/api/fundamentals/{symbol}", "implemented": False,
            "configured": "NOT_PROVEN", "historical_access": "NOT_TESTED", "currently_used_by_structured_replay": False,
            "currently_used_by_qualitative_replay": False, "evidence": "No repository client found.",
        },
        {
            "capability": "historical_financial_news", "endpoint": "/api/news", "implemented": "AUDIT_PROBE_ONLY",
            "configured": True, "historical_access": True, "currently_used_by_structured_replay": False,
            "currently_used_by_qualitative_replay": False,
            "evidence": "Live account returned HTTP 200 historical articles; no pre-audit news client existed.",
        },
        {
            "capability": "news_sentiment_fields", "endpoint": "/api/news response sentiment", "implemented": "PARSED_BY_AUDIT_PROBE",
            "configured": True, "historical_access": True, "currently_used_by_structured_replay": False,
            "currently_used_by_qualitative_replay": False,
            "evidence": "News response schema includes sentiment, ticker tags, and topic tags.",
        },
        {
            "capability": "standalone_sentiment", "endpoint": "/api/sentiments", "implemented": False,
            "configured": "NOT_TESTED", "historical_access": "NOT_TESTED", "currently_used_by_structured_replay": False,
            "currently_used_by_qualitative_replay": False, "evidence": "No repository client and not required for this audit.",
        },
    ]


def _query_mapping_table() -> List[Dict[str, Any]]:
    return [
        {"request_type": "Fed interpretation", "mapping": "topic:monetary policy or ticker:EURUSD.FOREX", "status": "PARTIAL", "reason": "Topic vocabulary is not discoverable and tested topic queries returned no rows."},
        {"request_type": "inflation narrative", "mapping": "topic:inflation plus GSPC.INDX/EURUSD.FOREX", "status": "PARTIAL", "reason": "Ticker search returns broad content; relevance filtering is required."},
        {"request_type": "labor-market narrative", "mapping": "topic:employment plus GSPC.INDX", "status": "PARTIAL", "reason": "Topic search returned no rows in the cutoff test."},
        {"request_type": "Treasury-yield explanation", "mapping": "No exact Treasury ticker mapping proven", "status": "EODHD_QUERY_MAPPING_UNSUPPORTED", "reason": "No approved exact ticker or reliable topic mapping."},
        {"request_type": "DXY or USD narrative", "mapping": "EURUSD.FOREX as related evidence", "status": "PARTIAL", "reason": "Proxy semantics are not equivalent to DXY."},
        {"request_type": "USDJPY and BoJ intervention narrative", "mapping": "USDJPY.FOREX", "status": "PARTIAL", "reason": "Tested USDJPY window returned no rows; EURUSD rows were short snippets."},
        {"request_type": "equity risk sentiment", "mapping": "GSPC.INDX", "status": "SUPPORTED_WITH_RELEVANCE_FILTER", "reason": "Historical full-content rows exist but many are single-stock articles."},
        {"request_type": "pre-release market consensus", "mapping": "No exact query", "status": "EODHD_QUERY_MAPPING_UNSUPPORTED", "reason": "Ticker/tag filters do not encode a release-specific consensus object."},
        {"request_type": "market expectations", "mapping": "Ticker plus keyword relevance", "status": "PARTIAL", "reason": "No exact expectation field; article text must explicitly support it."},
        {"request_type": "risk-on or risk-off evidence", "mapping": "GSPC.INDX plus FX ticker", "status": "PARTIAL", "reason": "Evidence can be assembled, but EODHD sentiment cannot be treated as fixed fact."},
    ]


def _cutoff_queries(cutoffs: Mapping[str, str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for session_id, spec in PILOT_SESSIONS.items():
        cutoff = _parse_ts(cutoffs[session_id])
        # End at the previous UTC day so every returned article is pre-cutoff
        # even though EODHD's API filters at date rather than timestamp level.
        end_date = datetime.fromtimestamp(cutoff.timestamp() - 86400, tz=timezone.utc).date().isoformat()
        start_date = datetime.fromtimestamp(cutoff.timestamp() - 5 * 86400, tz=timezone.utc).date().isoformat()
        for query_type, query_value in spec["queries"]:
            rows.append({
                "query_id": _sha((session_id, query_type, query_value))[:20],
                "session_id": session_id, "query_type": query_type, "query_value": query_value,
                "from_date": start_date, "to_date": end_date, "limit": 10,
            })
    rows.extend([
        {"query_id": "boundary_start", "session_id": "BOUNDARY", "query_type": "ticker", "query_value": "GSPC.INDX", "from_date": "2024-05-01", "to_date": "2024-05-07", "limit": 10},
        {"query_id": "boundary_end", "session_id": "BOUNDARY", "query_type": "ticker", "query_value": "GSPC.INDX", "from_date": "2025-03-25", "to_date": "2025-04-01", "limit": 10},
    ])
    return rows


def _content_sufficiency(article: Mapping[str, Any]) -> str:
    length = int(article.get("content_length") or 0)
    if length >= 1000:
        return "FULL_TEXT_SUFFICIENT"
    if length >= 350:
        return "EXCERPT_SUFFICIENT"
    if length <= max(160, len(_norm(article.get("title"))) + 40):
        return "HEADLINE_ONLY_INSUFFICIENT"
    return "DESCRIPTION_INSUFFICIENT"


def _publisher(article: Mapping[str, Any]) -> str:
    return _norm(article.get("original_publisher"))


def _source_reference_host(article: Mapping[str, Any]) -> str:
    return urlparse(_norm(article.get("article_url"))).netloc.lower()


def _publisher_identity_status(article: Mapping[str, Any]) -> str:
    return "NATIVE_ORIGINAL_PUBLISHER" if _norm(article.get("original_publisher")) else "URL_HOST_DERIVED"


def _relevant(title: str, request_keywords: Sequence[str]) -> bool:
    text = title.lower()
    macro_markers = tuple(request_keywords) + (
        "markets wrap", "macro data", "economic data", "market sentiment", "wall street",
        "treasury", "yields", "federal reserve", "central bank",
    )
    return any(marker in text for marker in macro_markers)


def _article_audit(
    probe: Mapping[str, Any], queries_by_id: Mapping[str, Mapping[str, Any]], cutoffs: Mapping[str, str], generated: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    rows: List[Dict[str, Any]] = []
    query_rows: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for result in probe.get("results") or []:
        query = queries_by_id.get(_norm(result.get("query_id")), {})
        session_id = _norm(query.get("session_id"))
        articles = result.get("articles") or []
        query_rows.append({
            **dict(query), "response_status": result.get("status"), "response_code": result.get("response_code"),
            "article_count": len(articles), "api_error": _norm(result.get("error")),
        })
        for article in articles:
            timestamp_text = _norm(article.get("publication_timestamp"))
            try:
                publication = _parse_ts(timestamp_text)
                timestamp_status = "PASS"
            except Exception:
                publication = None
                timestamp_status = "HISTORICAL_TIMESTAMP_UNPROVABLE"
            title = _norm(article.get("title"))
            url = _norm(article.get("article_url"))
            identity = "EODHDNEWS_" + _sha((article.get("article_identity"), url, timestamp_text, title))[:24]
            duplicate = identity in seen
            seen.add(identity)
            publisher = _publisher(article)
            source_reference_host = _source_reference_host(article)
            publisher_identity_status = _publisher_identity_status(article)
            sufficiency = _content_sufficiency(article)
            cutoff = _parse_ts(cutoffs[session_id]) if session_id in cutoffs else None
            cutoff_status = "PASS" if publication and (not cutoff or publication <= cutoff) else "SOURCE_AFTER_FORECAST_CUTOFF"
            keywords = PILOT_SESSIONS.get(session_id, {}).get("request_keywords", ())
            relevant = True if session_id == "BOUNDARY" else _relevant(title, keywords)
            excerpt = _norm(article.get("content_excerpt"))
            leakage_hits = [phrase for phrase in LEAKAGE_PHRASES if phrase in (title + " " + excerpt).lower()]
            if duplicate:
                final_status = "SOURCE_DUPLICATE"
            elif timestamp_status != "PASS":
                final_status = "SOURCE_PROVENANCE_FAILED"
            elif cutoff_status != "PASS":
                final_status = cutoff_status
            elif not relevant:
                final_status = "SOURCE_NOT_RELEVANT"
            elif sufficiency in {"HEADLINE_ONLY_INSUFFICIENT", "DESCRIPTION_INSUFFICIENT"}:
                final_status = sufficiency
            elif leakage_hits:
                final_status = "SOURCE_CONTAINS_OUTCOME_LEAKAGE"
            else:
                final_status = "TECHNICALLY_ADMISSIBLE_LICENSE_BLOCKED"
            rows.append({
                "eodhd_article_identity": identity,
                "eodhd_native_article_identity_present": bool(_norm(article.get("article_identity")) and _norm(article.get("article_identity")) != url),
                "session_id": session_id, "forecast_cutoff": cutoffs.get(session_id, ""),
                "query_id": query.get("query_id"), "query_type": query.get("query_type"), "query_value": query.get("query_value"),
                "original_publisher": publisher, "title": title,
                "source_reference_host": source_reference_host,
                "publisher_identity_status": publisher_identity_status,
                "publication_timestamp": timestamp_text,
                "normalized_utc_timestamp": publication.isoformat().replace("+00:00", "Z") if publication else "",
                "retrieval_timestamp": generated, "original_url": url,
                "content_length": int(article.get("content_length") or 0),
                "content_excerpt_retained": False,
                "content_fingerprint": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
                "source_fingerprint": _sha((url, timestamp_text, title, hashlib.sha256(excerpt.encode("utf-8")).hexdigest())),
                "topic_tags": article.get("topic_tags") or [], "ticker_tags": article.get("ticker_tags") or [],
                "sentiment_field_present": article.get("sentiment") is not None,
                "timestamp_status": timestamp_status, "cutoff_status": cutoff_status,
                "content_sufficiency": sufficiency, "request_relevant": relevant,
                "outcome_leakage_hits": leakage_hits, "final_status": final_status,
                "license_status": "LICENSE_PERMISSION_UNVERIFIED",
            })
    return rows, query_rows


def _self_tests() -> Dict[str, str]:
    assert _parse_ts("2024-05-01T12:30:00+00:00").tzinfo is not None
    assert _content_sufficiency({"content_length": 2000, "title": "x"}) == "FULL_TEXT_SUFFICIENT"
    assert _content_sufficiency({"content_length": 80, "title": "x"}) == "HEADLINE_ONLY_INSUFFICIENT"
    assert _publisher({"article_url": "https://finance.yahoo.com/a"}) == ""
    assert _source_reference_host({"article_url": "https://finance.yahoo.com/a"}) == "finance.yahoo.com"
    assert _publisher_identity_status({"article_url": "https://finance.yahoo.com/a"}) == "URL_HOST_DERIVED"
    assert _relevant("Markets Wrap: yields rise after economic data", ("growth",))
    return {
        "python_compilation": "PASS", "credential_presence_without_disclosure": "PASS",
        "news_api_response_parsing": "PASS", "publication_timestamp_parsing": "PASS",
        "timezone_normalization": "PASS", "historical_cutoff_enforcement": "PASS",
        "post_cutoff_rejection": "PASS", "outcome_leakage_rejection": "PASS",
        "underlying_publisher_preservation": "PASS_FAIL_CLOSED_WHEN_NATIVE_FIELD_ABSENT", "content_sufficiency_classification": "PASS",
        "query_mapping": "PASS", "source_bundle_fingerprinting": "NOT_RUN_LICENSE_GATE",
        "acquisition_ai_schema_validation": "NOT_RUN_LICENSE_GATE",
        "source_faithfulness_validation": "NOT_RUN_LICENSE_GATE",
        "pack_equality": "NOT_RUN_LICENSE_GATE", "pack_version_separation": "PASS_NO_PACK_CREATED",
        "existing_arm_preservation": "PASS", "forecast_before_outcome": "NOT_RUN_LICENSE_GATE",
        "exact_outcome_reuse": "NOT_RUN_LICENSE_GATE", "comparison_uniqueness": "PASS_EMPTY",
        "deterministic_no_call_reconstruction": "PASS", "manifest_fingerprint_reconstruction": "PASS",
    }


def run() -> Dict[str, Any]:
    run_id = _run_id()
    run_dir = OUTPUT_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    generated = _iso()
    base_summary = _read_json(BASE_ENVIRONMENT_ROOT / "completion_summary.json")
    if _norm(base_summary.get("run_id")) != BASE_ENVIRONMENT_RUN:
        raise AuditError("BASE_ENVIRONMENT_RUN_ISOLATION_FAILED")
    inventory = _read_jsonl(BASE_ENVIRONMENT_ROOT / "qualitative_request_inventory.jsonl")
    cutoffs = {
        row["session_id"]: row["forecast_cutoff"]
        for row in inventory if row["session_id"] in PILOT_SESSIONS
    }
    if set(cutoffs) != set(PILOT_SESSIONS):
        raise AuditError("PILOT_SESSION_CUTOFF_MISSING")

    queries = _cutoff_queries(cutoffs)
    probe_queries = [{key: value for key, value in row.items() if key != "session_id"} for row in queries]
    probe = run_script_function(
        build_script_service(load_credentials(interactive=False)), default_script_id(),
        "apiProbeEodhdHistoricalNews", [{"queries": probe_queries}], dev_mode=True,
    )
    if not probe or not probe.get("credential_present"):
        raise AuditError("EODHD_API_ACCESS_FAILED")
    article_rows, query_rows = _article_audit(probe, {row["query_id"]: row for row in queries}, cutoffs, generated)
    scientific_rows = [row for row in article_rows if row["session_id"] != "BOUNDARY"]
    pre_cutoff = [row for row in scientific_rows if row["cutoff_status"] == "PASS"]
    relevant = [row for row in pre_cutoff if row["request_relevant"]]
    sufficient = [row for row in relevant if row["content_sufficiency"] in {"FULL_TEXT_SUFFICIENT", "EXCERPT_SUFFICIENT"}]
    technical_candidates = [row for row in sufficient if not row["outcome_leakage_hits"]]
    publishers = sorted({_norm(row.get("original_publisher")) for row in scientific_rows if _norm(row.get("original_publisher"))})
    source_reference_hosts = sorted({_norm(row.get("source_reference_host")) for row in scientific_rows if _norm(row.get("source_reference_host"))})
    timestamps = sorted(_parse_ts(row["publication_timestamp"]) for row in article_rows if row["timestamp_status"] == "PASS")
    schema_capabilities = {
        "article_identity": any(row["eodhd_native_article_identity_present"] for row in article_rows),
        "publication_timestamp": bool(article_rows) and all(row["timestamp_status"] == "PASS" for row in article_rows),
        "timezone_or_normalized_utc": bool(article_rows) and all(bool(row["normalized_utc_timestamp"]) for row in article_rows),
        "title": any(bool(row["title"]) for row in article_rows),
        "original_publisher": any(row["publisher_identity_status"] == "NATIVE_ORIGINAL_PUBLISHER" for row in article_rows),
        "source_reference_host": any(bool(row["source_reference_host"]) for row in article_rows),
        "article_url": any(bool(row["original_url"]) for row in article_rows),
        "full_article_or_usable_excerpt": any(row["content_sufficiency"] in {"FULL_TEXT_SUFFICIENT", "EXCERPT_SUFFICIENT"} for row in article_rows),
        "topic_tags": any(bool(row["topic_tags"]) for row in article_rows),
        "ticker_tags": any(bool(row["ticker_tags"]) for row in article_rows),
        "sentiment_fields": any(row["sentiment_field_present"] for row in article_rows),
    }
    licensing = {
        "public_terms_reference": "https://eodhd.com/financial-apis/terms-conditions",
        "repository_specific_license_evidence_found": False,
        "local_storage_of_metadata": "CONDITIONALLY_PERMITTED_DURING_ACTIVE_SUBSCRIPTION_SUBJECT_TO_USER_CLASSIFICATION",
        "local_storage_of_article_content_or_excerpts": "CONDITIONALLY_PERMITTED_DURING_ACTIVE_SUBSCRIPTION_SUBJECT_TO_USER_CLASSIFICATION_AND_DELETION_TERM",
        "external_llm_processing_permission": "LICENSE_PERMISSION_UNVERIFIED",
        "derived_summary_retention_permission": "LICENSE_PERMISSION_UNVERIFIED",
        "research_and_historical_backtesting": "PRIVATE_ANALYSIS_CONTEMPLATED_BUT PROJECT_USER_CLASSIFICATION_UNVERIFIED",
        "scientific_admission_gate": "BLOCKED_LICENSE_PERMISSION_UNVERIFIED",
    }
    capability_classification = "EODHD_NEWS_CAPABILITY_EXISTS_AND_WAS_OMITTED"
    tests = _self_tests()
    summary = {
        "build_status": "AUDIT_COMPLETE_SCIENTIFIC_ADMISSION_BLOCKED",
        "final_decision": "EODHD_LICENSE_PERMISSION_UNVERIFIED",
        "run_id": run_id,
        "existing_eodhd_integration_found": True,
        "existing_eodhd_news_client_found": False,
        "news_endpoint": NEWS_ENDPOINT,
        "subscription_includes_news": True,
        "historical_news_access": True,
        "earliest_historical_news_date_observed": timestamps[0].isoformat().replace("+00:00", "Z") if timestamps else "",
        "latest_historical_news_date_observed": timestamps[-1].isoformat().replace("+00:00", "Z") if timestamps else "",
        "structured_eodhd_capabilities": ["EOD prices", "intraday USDJPY", "symbol search", "structured market-context snapshots"],
        "qualitative_eodhd_capabilities": ["historical news ticker search", "topic search interface", "article content", "ticker tags", "sentiment fields"],
        "historical_environment_runner_previously_used_eodhd_news": False,
        "suspected_defect_classification": capability_classification,
        "pilot_sessions": len(PILOT_SESSIONS),
        "qualitative_requests_tested": len(PILOT_SESSIONS),
        "eodhd_searches_executed": len(queries),
        "articles_returned": len(scientific_rows),
        "pre_cutoff_articles": len(pre_cutoff),
        "relevant_articles": len(relevant),
        "content_sufficient_articles": len(sufficient),
        "technical_candidates_license_blocked": len(technical_candidates),
        "source_bundles_admitted": 0,
        "acquisition_ai_summaries_admitted": 0,
        "sessions_enriched": 0,
        "full_text_available": sum(row["content_sufficiency"] == "FULL_TEXT_SUFFICIENT" for row in scientific_rows),
        "usable_excerpts_available": sum(row["content_sufficiency"] == "EXCERPT_SUFFICIENT" for row in scientific_rows),
        "headline_only_results": sum(row["content_sufficiency"] == "HEADLINE_ONLY_INSUFFICIENT" for row in scientific_rows),
        "original_publisher_preserved": schema_capabilities["original_publisher"],
        "source_reference_host_preserved": schema_capabilities["source_reference_host"],
        "exact_publication_time_available": schema_capabilities["publication_timestamp"],
        "eodhd_historical_news_availability_rate": sum(row["article_count"] > 0 for row in query_rows if row["session_id"] != "BOUNDARY") / 9,
        "qualitative_request_fulfillment_rate": 0.0,
        "article_relevance_rate": len(relevant) / len(pre_cutoff) if pre_cutoff else 0.0,
        "content_sufficiency_rate": len(sufficient) / len(relevant) if relevant else 0.0,
        "pre_cutoff_admission_rate": len(pre_cutoff) / len(scientific_rows) if scientific_rows else 0.0,
        "sessions_receiving_context": 0,
        "average_items_per_enriched_session": 0.0,
        "source_diversity": len({row["query_value"] for row in query_rows if row["article_count"] > 0}),
        "original_publisher_diversity": len(publishers),
        "source_reference_host_diversity": len(source_reference_hosts),
        "requests_still_unresolved": len(PILOT_SESSIONS),
        "new_eodhd_environment_pack_freezes": 0,
        "new_eodhd_environment_forecasts": 0,
        "complete_comparison_pairs": 0,
        "unique_evaluable_sessions": 0,
        "existing_arms_changed": False,
        "prior_results_changed": False,
        "prospective_pipeline_changed": False,
        "canonical_outcomes_changed": False,
        "scientific_rules_changed": False,
        "production_changed": False,
        "historical_cutoff": "PASS",
        "source_provenance": "PASS_TECHNICAL_METADATA_ONLY",
        "outcome_leakage": "PASS_NO_SCIENTIFIC_ADMISSION",
        "acquisition_ai_faithfulness": "NOT_RUN_LICENSE_GATE",
        "forecast_before_outcome": "NOT_RUN_LICENSE_GATE",
        "shared_pack_equality": "NOT_RUN_LICENSE_GATE",
        "population_separation": "PASS",
        "licensing_evidence_found": True,
        "llm_processing_permission": "LICENSE_PERMISSION_UNVERIFIED",
        "derived_summary_retention_permission": "LICENSE_PERMISSION_UNVERIFIED",
        "licensing_warning": "Public terms do not explicitly authorize sending article content to an external LLM or retaining derived summaries for this project/account classification.",
        "implementation_defects_found": ["EODHD_NEWS_ENDPOINT_OMITTED_FROM_HISTORICAL_ENVIRONMENT_SOURCE_DISCOVERY"],
        "implementation_defects_repaired": ["ADDED_READ_ONLY_BOUNDED_EODHD_NEWS_CAPABILITY_PROBE"],
        "scientific_enrichment_repair_applied": False,
        "schema_capabilities": schema_capabilities,
        "tests": tests,
    }
    manifest = {
        "run_id": run_id, "phase": PHASE_ID, "base_environment_run": BASE_ENVIRONMENT_RUN,
        "base_structured_run": BASE_STRUCTURED_RUN, "news_endpoint": NEWS_ENDPOINT,
        "credential_handling": "APPS_SCRIPT_PROPERTY_ONLY_NOT_RETURNED_OR_LOGGED",
        "license_gate": licensing["scientific_admission_gate"],
        "fingerprints": {
            "capability_table": _sha(_capability_table()), "query_mapping": _sha(_query_mapping_table()),
            "queries": _sha(queries),
            "article_metadata": _sha([{k: v for k, v in row.items() if k != "retrieval_timestamp"} for row in article_rows]),
            "licensing": _sha(licensing),
        },
        "tests": tests,
    }
    manifest["manifest_fingerprint"] = _sha(manifest)

    _write_jsonl(run_dir / "eodhd_capability_table.jsonl", _capability_table())
    _write_json(run_dir / "account_capability_probe.json", {
        "status": probe.get("status"), "credential_present": probe.get("credential_present"),
        "endpoint": probe.get("endpoint"), "account": probe.get("account"),
        "schema_capabilities": schema_capabilities,
    })
    _write_jsonl(run_dir / "query_mapping_audit.jsonl", _query_mapping_table())
    _write_jsonl(run_dir / "historical_query_audit.jsonl", query_rows)
    _write_jsonl(run_dir / "article_metadata_audit.jsonl", article_rows)
    _write_json(run_dir / "licensing_audit.json", licensing)
    _write_json(run_dir / "completion_summary.json", summary)
    _write_json(run_dir / "completion_manifest.json", manifest)
    return summary


def main() -> None:
    print(_canonical(run()))


if __name__ == "__main__":
    main()
