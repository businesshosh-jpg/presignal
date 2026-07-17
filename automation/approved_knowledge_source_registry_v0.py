#!/usr/bin/env python3
"""Approved Knowledge Source Registry and provider-neutral knowledge router.

AKSR governs source eligibility before evidence acquisition. Source approval is
deliberately separate from article admission: every item still has to pass the
mode-specific provenance, cutoff, relevance, and revision gates.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


REGISTRY_VERSION = "aksr_v1"
REGISTRY_SHEET = "Knowledge_Source_Registry"

SOURCE_CLASSES = {
    "OFFICIAL_DATA",
    "OFFICIAL_RESEARCH",
    "INSTITUTIONAL_RESEARCH",
    "MARKET_DATA",
    "SURVEY",
    "NEWS",
    "OTHER",
}
LIFECYCLE_STAGES = (
    "CANDIDATE",
    "TECHNICAL_VALIDATION",
    "HISTORICAL_VALIDATION",
    "PROSPECTIVE_VALIDATION",
    "SCIENTIFIC_APPROVAL",
    "APPROVED_SOURCE",
)
ACQUISITION_METHODS = {"API", "HTML", "RSS", "PDF", "SEARCH"}
CONTENT_TYPES = {"STRUCTURED", "SEMI_STRUCTURED", "NARRATIVE"}
MODES = {"HISTORICAL_REPLAY", "PROSPECTIVE_COLLECTION"}

TOPICS = {
    "FED_EXPECTATIONS",
    "INFLATION_NARRATIVE",
    "TREASURY_INTERPRETATION",
    "CONSUMER_OUTLOOK",
    "RISK_SENTIMENT",
    "LABOR_MARKET",
    "GROWTH_CONTEXT",
    "MARKET_DATA",
    "USD_FX_NARRATIVE",
    "BOJ_CONTEXT",
    "MARKET_EXPECTATIONS",
    "OFFICIAL_CALENDAR",
    "FINANCIAL_CONDITIONS",
}

REGISTRY_HEADERS = [
    "registry_version",
    "source_id",
    "source_name",
    "organization",
    "domain",
    "source_aliases",
    "source_class",
    "trust_tier",
    "supported_topics",
    "preferred_topics",
    "excluded_topics",
    "routing_priority",
    "acquisition_method",
    "content_type",
    "historical_status",
    "historical_retrieval_method",
    "historical_provenance_rule",
    "historical_supported",
    "prospective_status",
    "prospective_retrieval_method",
    "prospective_provenance_rule",
    "prospective_supported",
    "provenance_policy_id",
    "publication_date_method",
    "revision_detection_method",
    "citation_required",
    "publisher_verification",
    "ai_summary_allowed",
    "authentication_required",
    "rate_limit",
    "cost",
    "lifecycle_stage",
    "status",
    "last_validation",
    "validation_notes",
]


class RegistryError(RuntimeError):
    """Fail-closed AKSR validation error."""


def _norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)


def fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _csv(values: Sequence[str]) -> str:
    return "|".join(values)


def _priorities(**values: int) -> str:
    return _canonical(values)


def _bool_text(value: bool) -> str:
    return "TRUE" if value else "FALSE"


def _record(
    source_id: str,
    source_name: str,
    organization: str,
    domain: str,
    aliases: Sequence[str],
    source_class: str,
    trust_tier: str,
    supported: Sequence[str],
    preferred: Sequence[str],
    priorities: Mapping[str, int],
    acquisition: Sequence[str],
    content: Sequence[str],
    historical_status: str,
    historical_method: str,
    historical_supported: bool,
    prospective_status: str,
    prospective_method: str,
    prospective_supported: bool,
    publication_method: str,
    revision_method: str,
    authentication_required: bool,
    rate_limit: str,
    cost: str,
    validation_notes: str,
    *,
    excluded: Sequence[str] = (),
    ai_summary_allowed: bool = True,
) -> Dict[str, Any]:
    policy_id = "AKSR_PROV_" + source_class
    return {
        "registry_version": REGISTRY_VERSION,
        "source_id": source_id,
        "source_name": source_name,
        "organization": organization,
        "domain": domain,
        "source_aliases": _csv(tuple(aliases)),
        "source_class": source_class,
        "trust_tier": trust_tier,
        "supported_topics": _csv(tuple(supported)),
        "preferred_topics": _csv(tuple(preferred)),
        "excluded_topics": _csv(tuple(excluded)),
        "routing_priority": _canonical(dict(priorities)),
        "acquisition_method": _csv(tuple(acquisition)),
        "content_type": _csv(tuple(content)),
        "historical_status": historical_status,
        "historical_retrieval_method": historical_method,
        "historical_provenance_rule": policy_id + ":HISTORICAL_REPLAY",
        "historical_supported": _bool_text(historical_supported),
        "prospective_status": prospective_status,
        "prospective_retrieval_method": prospective_method,
        "prospective_provenance_rule": policy_id + ":PROSPECTIVE_COLLECTION",
        "prospective_supported": _bool_text(prospective_supported),
        "provenance_policy_id": policy_id,
        "publication_date_method": publication_method,
        "revision_detection_method": revision_method,
        "citation_required": "TRUE",
        "publisher_verification": "REQUIRED",
        "ai_summary_allowed": _bool_text(ai_summary_allowed),
        "authentication_required": _bool_text(authentication_required),
        "rate_limit": rate_limit,
        "cost": cost,
        "lifecycle_stage": "APPROVED_SOURCE",
        "status": "APPROVED_SOURCE_CAPABILITY_GATED",
        "last_validation": "2026-07-16T00:00:00Z",
        "validation_notes": validation_notes,
    }


PROVENANCE_POLICIES: Dict[str, Dict[str, Any]] = {
    "AKSR_PROV_OFFICIAL_DATA": {
        "source_class": "OFFICIAL_DATA",
        "historical": {
            "publication_rule": "OFFICIAL_PUBLICATION_OR_OBSERVATION_TIMESTAMP_AT_OR_BEFORE_CUTOFF",
            "revision_rule": "OFFICIAL_VINTAGE_OR_REVISION_STATE_REQUIRED_WHEN_SERIES_CAN_REVISE",
            "exact_time_required_same_day": True,
        },
        "prospective": {
            "publication_rule": "CAPTURE_OFFICIAL_TIMESTAMP_AND_CONTENT_FINGERPRINT_BEFORE_CUTOFF",
            "revision_rule": "PRESERVE_CAPTURED_VERSION_AND_LATER_REVISION_IDENTITY",
            "exact_time_required_same_day": True,
        },
    },
    "AKSR_PROV_OFFICIAL_RESEARCH": {
        "source_class": "OFFICIAL_RESEARCH",
        "historical": {
            "publication_rule": "DATED_OFFICIAL_PAGE_OR_ARCHIVED_DOCUMENT_AVAILABLE_BEFORE_CUTOFF",
            "revision_rule": "IMMUTABLE_DOCUMENT_OR_HISTORICAL_PAGE_STATE_REQUIRED",
            "exact_time_required_same_day": True,
        },
        "prospective": {
            "publication_rule": "CAPTURE_OFFICIAL_PAGE_TIMESTAMP_AND_PAGE_STATE_BEFORE_CUTOFF",
            "revision_rule": "CONTENT_FINGERPRINT_AND_REVISION_MONITORING_REQUIRED",
            "exact_time_required_same_day": True,
        },
    },
    "AKSR_PROV_INSTITUTIONAL_RESEARCH": {
        "source_class": "INSTITUTIONAL_RESEARCH",
        "historical": {
            "publication_rule": "PUBLICATION_BEFORE_CUTOFF_WITH_HISTORICAL_PAGE_STATE_EVIDENCE",
            "revision_rule": "NO_SUBSTANTIVE_REVISION_DETECTED_OR_ARCHIVED_VERSION_REQUIRED",
            "exact_time_required_same_day": True,
        },
        "prospective": {
            "publication_rule": "CAPTURE_TIMESTAMP_AND_PAGE_STATE_BEFORE_CUTOFF",
            "revision_rule": "CONTENT_FINGERPRINT_AND_CANONICAL_URL_REQUIRED",
            "exact_time_required_same_day": True,
        },
    },
    "AKSR_PROV_MARKET_DATA": {
        "source_class": "MARKET_DATA",
        "historical": {
            "publication_rule": "OBSERVATION_TIMESTAMP_STRICTLY_BEFORE_CUTOFF_UNLESS_RELEASE_SEMANTICS_APPROVE_EQUALITY",
            "revision_rule": "POINT_IN_TIME_VALUE_OR_NON_REVISED_MARKET_TICK_REQUIRED",
            "exact_time_required_same_day": True,
        },
        "prospective": {
            "publication_rule": "CAPTURED_OBSERVATION_TIMESTAMP_BEFORE_CUTOFF",
            "revision_rule": "RAW_RESPONSE_OR_VALUE_FINGERPRINT_REQUIRED",
            "exact_time_required_same_day": True,
        },
    },
    "AKSR_PROV_SURVEY": {
        "source_class": "SURVEY",
        "historical": {
            "publication_rule": "SURVEY_PUBLICATION_TIMESTAMP_AT_OR_BEFORE_CUTOFF",
            "revision_rule": "SURVEY_VINTAGE_AND_RELEASE_ID_REQUIRED",
            "exact_time_required_same_day": True,
        },
        "prospective": {
            "publication_rule": "CAPTURE_SURVEY_RELEASE_TIMESTAMP_AND_VINTAGE_BEFORE_CUTOFF",
            "revision_rule": "PRESERVE_RELEASE_VINTAGE",
            "exact_time_required_same_day": True,
        },
    },
    "AKSR_PROV_NEWS": {
        "source_class": "NEWS",
        "historical": {
            "publication_rule": "EXACT_PUBLICATION_TIMESTAMP_AND_HISTORICAL_CONTENT_STATE_BEFORE_CUTOFF",
            "revision_rule": "STRICT_REVISION_OR_ARCHIVED_STATE_VERIFICATION_REQUIRED",
            "exact_time_required_same_day": True,
        },
        "prospective": {
            "publication_rule": "CAPTURE_EXACT_TIMESTAMP_AND_CONTENT_BEFORE_CUTOFF",
            "revision_rule": "CONTENT_FINGERPRINT_AND_UPDATE_TIMESTAMP_REQUIRED",
            "exact_time_required_same_day": True,
        },
    },
    "AKSR_PROV_OTHER": {
        "source_class": "OTHER",
        "historical": {
            "publication_rule": "FAIL_CLOSED_UNLESS_EXPLICIT_SOURCE_POLICY_IS_ADDED",
            "revision_rule": "EXPLICIT_VALIDATION_REQUIRED",
            "exact_time_required_same_day": True,
        },
        "prospective": {
            "publication_rule": "FAIL_CLOSED_UNLESS_EXPLICIT_SOURCE_POLICY_IS_ADDED",
            "revision_rule": "EXPLICIT_VALIDATION_REQUIRED",
            "exact_time_required_same_day": True,
        },
    },
}


def initial_registry() -> List[Dict[str, Any]]:
    """Return the frozen initial AKSR population in deterministic source-id order."""
    rows = [
        _record(
            "KSRC_FEDERAL_RESERVE", "Federal Reserve", "Board of Governors of the Federal Reserve System",
            "federalreserve.gov", ("FEDERAL_RESERVE", "FOMC_POLICY_INTERPRETATION", "FOMC"),
            "OFFICIAL_DATA", "TIER_1_OFFICIAL", tuple(sorted(TOPICS - {"BOJ_CONTEXT"})),
            ("FED_EXPECTATIONS", "INFLATION_NARRATIVE"),
            {"INFLATION_NARRATIVE": 40, "FED_EXPECTATIONS": 50, "LABOR_MARKET": 25, "GROWTH_CONTEXT": 25},
            ("HTML", "PDF", "RSS"), ("STRUCTURED", "NARRATIVE"),
            "VALIDATED_OFFICIAL_PAGES", "OFFICIAL_ARCHIVE_AND_DATED_RELEASE_PAGES", True,
            "SUPPORTED_SHADOW", "OFFICIAL_RELEASE_POLL_AND_IMMEDIATE_FINGERPRINT", True,
            "OFFICIAL_RELEASE_TIMESTAMP", "OFFICIAL_UPDATE_MARKER_AND_CONTENT_FINGERPRINT", False,
            "PUBLIC", "FREE", "FOMC and official release pages validated in Stage 4A historical environment runs.",
        ),
        _record(
            "KSRC_FEDERAL_RESERVE_RESEARCH", "Federal Reserve Research", "Federal Reserve System",
            "federalreserve.gov", ("FEDERAL_RESERVE_RESEARCH", "BEIGE_BOOK_MARKET_CONTACT_CONTEXT", "BEIGE_BOOK"),
            "OFFICIAL_RESEARCH", "TIER_1_OFFICIAL", ("INFLATION_NARRATIVE", "LABOR_MARKET", "GROWTH_CONTEXT", "FINANCIAL_CONDITIONS", "FED_EXPECTATIONS"),
            ("INFLATION_NARRATIVE", "LABOR_MARKET", "GROWTH_CONTEXT"),
            {"INFLATION_NARRATIVE": 60, "LABOR_MARKET": 20, "GROWTH_CONTEXT": 20, "FINANCIAL_CONDITIONS": 30},
            ("HTML", "PDF", "SEARCH"), ("NARRATIVE",),
            "VALIDATED_BOUNDED_OFFICIAL_RESEARCH", "DATED_OFFICIAL_REPORT_AND_ARCHIVE_PAGE", True,
            "SUPPORTED_SHADOW", "OFFICIAL_RESEARCH_POLL_AND_PAGE_FINGERPRINT", True,
            "OFFICIAL_PUBLICATION_MARKER", "OFFICIAL_LAST_UPDATE_AND_CONTENT_FINGERPRINT", False,
            "PUBLIC", "FREE", "Beige Book historical page-state and cutoff handling validated.",
        ),
        _record(
            "KSRC_NEW_YORK_FED", "Federal Reserve Bank of New York", "Federal Reserve Bank of New York",
            "newyorkfed.org", ("NEW_YORK_FED", "NY_FED", "FEDERAL_RESERVE_BANK_OF_NEW_YORK"),
            "OFFICIAL_RESEARCH", "TIER_1_OFFICIAL", ("FED_EXPECTATIONS", "MARKET_EXPECTATIONS", "FINANCIAL_CONDITIONS", "INFLATION_NARRATIVE"),
            ("FED_EXPECTATIONS", "MARKET_EXPECTATIONS"),
            {"FED_EXPECTATIONS": 40, "MARKET_EXPECTATIONS": 20, "FINANCIAL_CONDITIONS": 25},
            ("API", "HTML", "PDF"), ("STRUCTURED", "NARRATIVE"),
            "APPROVED_NOT_YET_CONNECTED_TO_STAGE4A_ROUTER", "OFFICIAL_DATED_RELEASE_OR_ARCHIVE", False,
            "APPROVED_NOT_YET_CONNECTED_TO_STAGE4A_ROUTER", "OFFICIAL_PAGE_POLL_AND_CAPTURE", False,
            "OFFICIAL_RELEASE_TIMESTAMP", "OFFICIAL_VERSION_AND_CONTENT_FINGERPRINT", False,
            "PUBLIC", "FREE", "Approved family; Stage 4A adapter capability remains unverified.",
        ),
        _record(
            "KSRC_BLS", "Bureau of Labor Statistics", "U.S. Bureau of Labor Statistics", "bls.gov",
            ("BLS", "BUREAU_OF_LABOR_STATISTICS"), "OFFICIAL_DATA", "TIER_1_OFFICIAL",
            ("INFLATION_NARRATIVE", "LABOR_MARKET", "OFFICIAL_CALENDAR"), ("INFLATION_NARRATIVE", "LABOR_MARKET"),
            {"INFLATION_NARRATIVE": 5, "LABOR_MARKET": 5, "OFFICIAL_CALENDAR": 10},
            ("API", "HTML", "PDF"), ("STRUCTURED", "NARRATIVE"),
            "VALIDATED_OFFICIAL_DATA", "OFFICIAL_RELEASE_AND_VINTAGE", True,
            "SUPPORTED", "OFFICIAL_RELEASE_POLL", True,
            "OFFICIAL_RELEASE_TIMESTAMP", "OFFICIAL_REVISION_TABLE_OR_VINTAGE", False,
            "PUBLIC", "FREE", "Approved official inflation and labor source; cutoff still applies per release.",
        ),
        _record(
            "KSRC_BEA", "Bureau of Economic Analysis", "U.S. Bureau of Economic Analysis", "bea.gov",
            ("BEA", "BUREAU_OF_ECONOMIC_ANALYSIS"), "OFFICIAL_DATA", "TIER_1_OFFICIAL",
            ("CONSUMER_OUTLOOK", "GROWTH_CONTEXT", "INFLATION_NARRATIVE", "OFFICIAL_CALENDAR"), ("CONSUMER_OUTLOOK", "GROWTH_CONTEXT"),
            {"CONSUMER_OUTLOOK": 10, "GROWTH_CONTEXT": 5, "INFLATION_NARRATIVE": 45},
            ("API", "HTML", "PDF"), ("STRUCTURED", "NARRATIVE"),
            "VALIDATED_OFFICIAL_DATA", "OFFICIAL_RELEASE_AND_VINTAGE", True,
            "SUPPORTED", "OFFICIAL_RELEASE_POLL", True,
            "OFFICIAL_RELEASE_TIMESTAMP", "OFFICIAL_REVISION_TABLE_OR_VINTAGE", False,
            "PUBLIC", "FREE", "Approved official growth, consumption, and PCE source.",
        ),
        _record(
            "KSRC_US_TREASURY", "U.S. Treasury", "U.S. Department of the Treasury", "treasury.gov",
            ("TREASURY", "US_TREASURY", "U.S._TREASURY"), "OFFICIAL_DATA", "TIER_1_OFFICIAL",
            ("TREASURY_INTERPRETATION", "MARKET_DATA", "FINANCIAL_CONDITIONS", "OFFICIAL_CALENDAR"), ("TREASURY_INTERPRETATION", "MARKET_DATA"),
            {"TREASURY_INTERPRETATION": 20, "MARKET_DATA": 10, "FINANCIAL_CONDITIONS": 20},
            ("API", "HTML", "CSV"), ("STRUCTURED", "NARRATIVE"),
            "APPROVED_PARTIALLY_VALIDATED", "OFFICIAL_DAILY_DATA_AND_DATED_DOCUMENT", True,
            "SUPPORTED", "OFFICIAL_DATA_POLL", True,
            "OFFICIAL_OBSERVATION_OR_PUBLICATION_TIMESTAMP", "OFFICIAL_VINTAGE_OR_CONTENT_FINGERPRINT", False,
            "PUBLIC", "FREE", "Structured Treasury data supported; narrative admission remains request-specific.",
        ),
        _record(
            "KSRC_CENSUS", "U.S. Census Bureau", "U.S. Census Bureau", "census.gov",
            ("CENSUS", "US_CENSUS", "U.S._CENSUS_BUREAU"), "OFFICIAL_DATA", "TIER_1_OFFICIAL",
            ("CONSUMER_OUTLOOK", "GROWTH_CONTEXT", "LABOR_MARKET", "OFFICIAL_CALENDAR"), ("CONSUMER_OUTLOOK", "GROWTH_CONTEXT"),
            {"CONSUMER_OUTLOOK": 50, "GROWTH_CONTEXT": 15, "OFFICIAL_CALENDAR": 20},
            ("API", "HTML", "PDF"), ("STRUCTURED", "NARRATIVE"),
            "APPROVED_NOT_YET_CONNECTED_TO_STAGE4A_ROUTER", "OFFICIAL_RELEASE_AND_VINTAGE", False,
            "APPROVED_NOT_YET_CONNECTED_TO_STAGE4A_ROUTER", "OFFICIAL_RELEASE_POLL", False,
            "OFFICIAL_RELEASE_TIMESTAMP", "OFFICIAL_REVISION_TABLE_OR_VINTAGE", False,
            "PUBLIC", "FREE", "Approved family; Stage 4A acquisition adapter not yet validated.",
        ),
        _record(
            "KSRC_FRED", "FRED", "Federal Reserve Bank of St. Louis", "fred.stlouisfed.org",
            ("FRED", "FRED_DAILY_SERIES", "ST_LOUIS_FED_FRED"), "OFFICIAL_DATA", "TIER_1_OFFICIAL",
            ("MARKET_DATA", "TREASURY_INTERPRETATION", "FED_EXPECTATIONS", "FINANCIAL_CONDITIONS", "GROWTH_CONTEXT"), ("MARKET_DATA", "FINANCIAL_CONDITIONS"),
            {"MARKET_DATA": 15, "TREASURY_INTERPRETATION": 30, "FINANCIAL_CONDITIONS": 15, "FED_EXPECTATIONS": 60},
            ("API",), ("STRUCTURED",),
            "VALIDATED_POINT_IN_TIME_WITH_WARNINGS", "FRED_API_SERIES_AND_VINTAGE_METADATA", True,
            "SUPPORTED", "FRED_API_PRE_CUTOFF_SNAPSHOT", True,
            "OBSERVATION_AND_AVAILABILITY_TIMESTAMP", "VINTAGE_DATE_OR_PRIOR_KNOWN_OBSERVATION_RULE", True,
            "CONFIGURED_QUOTA", "FREE", "Same-day observation availability must be proven; never label yield proxies as true FedWatch probabilities.",
            ai_summary_allowed=False,
        ),
        _record(
            "KSRC_APOLLO_DAILY_SPARK", "Apollo Daily Spark", "Apollo Global Management", "apollo.com",
            ("APOLLO", "APOLLO_DAILY_SPARK"), "INSTITUTIONAL_RESEARCH", "TIER_2_INSTITUTIONAL",
            ("FED_EXPECTATIONS", "INFLATION_NARRATIVE", "LABOR_MARKET", "GROWTH_CONTEXT", "TREASURY_INTERPRETATION", "FINANCIAL_CONDITIONS", "RISK_SENTIMENT", "USD_FX_NARRATIVE", "MARKET_EXPECTATIONS"),
            ("FED_EXPECTATIONS", "RISK_SENTIMENT", "GROWTH_CONTEXT"),
            {"FED_EXPECTATIONS": 10, "RISK_SENTIMENT": 10, "GROWTH_CONTEXT": 20, "INFLATION_NARRATIVE": 50},
            ("HTML", "SEARCH"), ("NARRATIVE",),
            "VALIDATED_BOUNDED_HISTORICAL", "LEGACY_DATED_ARCHIVE_AND_CANONICAL_ARTICLE", True,
            "SUPPORTED_SHADOW_AEM", "AEM_DAILY_ARCHIVE_POLL_AND_IMMEDIATE_FINGERPRINT", True,
            "ARCHIVE_EXACT_DATETIME_OR_AEM_DATE", "ARCHIVE_ENTRY_AND_CONTENT_FINGERPRINT", False,
            "PUBLIC_BOUNDED", "FREE", "Historical legacy records remain validated; current Apollo AEM discovery and prospective capture validated independently.",
        ),
        _record(
            "KSRC_PIMCO_INSIGHTS", "PIMCO Insights", "PIMCO", "pimco.com",
            ("PIMCO", "PIMCO_INSIGHTS"), "INSTITUTIONAL_RESEARCH", "TIER_2_INSTITUTIONAL",
            ("FED_EXPECTATIONS", "INFLATION_NARRATIVE", "LABOR_MARKET", "GROWTH_CONTEXT", "TREASURY_INTERPRETATION", "CONSUMER_OUTLOOK", "FINANCIAL_CONDITIONS", "MARKET_EXPECTATIONS"),
            ("TREASURY_INTERPRETATION", "INFLATION_NARRATIVE", "FED_EXPECTATIONS"),
            {"FED_EXPECTATIONS": 20, "INFLATION_NARRATIVE": 20, "TREASURY_INTERPRETATION": 10, "CONSUMER_OUTLOOK": 20},
            ("HTML", "PDF", "SEARCH"), ("NARRATIVE",),
            "VALIDATED_CONDITIONAL_ARCHIVED_STATE", "DATED_PAGE_PLUS_PRE_CUTOFF_ARCHIVED_STATE", True,
            "SUPPORTED_SHADOW", "SITEMAP_POLL_AND_IMMEDIATE_PAGE_FINGERPRINT", True,
            "JSONLD_PUBLICATION_DATE_OR_DATED_PDF", "DATE_MODIFIED_AND_ARCHIVED_PAGE_STATE", False,
            "PUBLIC_BOUNDED", "FREE", "Historical admission is allowed only when a retrievable pre-cutoff archive snapshot pins content; current-page dateModified is not historical proof.",
        ),
        _record(
            "KSRC_BLACKROCK_INVESTMENT_INSTITUTE", "BlackRock Investment Institute", "BlackRock", "blackrock.com",
            ("BLACKROCK", "BLACKROCK_INVESTMENT_INSTITUTE"), "INSTITUTIONAL_RESEARCH", "TIER_2_INSTITUTIONAL",
            ("FED_EXPECTATIONS", "INFLATION_NARRATIVE", "GROWTH_CONTEXT", "TREASURY_INTERPRETATION", "FINANCIAL_CONDITIONS", "RISK_SENTIMENT", "USD_FX_NARRATIVE", "MARKET_EXPECTATIONS"),
            ("RISK_SENTIMENT", "FINANCIAL_CONDITIONS", "GROWTH_CONTEXT"),
            {"FED_EXPECTATIONS": 30, "INFLATION_NARRATIVE": 30, "TREASURY_INTERPRETATION": 30, "RISK_SENTIMENT": 20},
            ("HTML", "PDF", "SEARCH"), ("NARRATIVE",),
            "VALIDATED_CONDITIONAL_ARCHIVED_HTML_STATE", "DATED_ROLLING_HTML_PAGE_PLUS_PRE_CUTOFF_ARCHIVE_SNAPSHOT", True,
            "SUPPORTED_SHADOW_HTML", "ROLLING_HTML_PAGE_POLL_AND_IMMEDIATE_FINGERPRINT", True,
            "VISIBLE_PUBLICATION_DATE_OR_STRUCTURED_METADATA", "VERSION_PINNED_HTML_CAPTURE_AND_REVISION_INDICATORS", False,
            "PUBLIC_BOUNDED", "FREE", "PDF URLs remain consent-gated; server-rendered weekly HTML is supported when title, date, body, and page-state gates pass.",
        ),
        _record(
            "KSRC_EODHD", "EODHD", "EOD Historical Data", "eodhd.com",
            ("EODHD", "EOD_HISTORICAL_DATA", "EODHD_NEWS"), "MARKET_DATA", "TIER_2_MARKET_DATA",
            ("MARKET_DATA", "USD_FX_NARRATIVE", "RISK_SENTIMENT", "MARKET_EXPECTATIONS", "TREASURY_INTERPRETATION"),
            ("MARKET_DATA", "USD_FX_NARRATIVE"),
            {"MARKET_DATA": 5, "USD_FX_NARRATIVE": 20, "RISK_SENTIMENT": 30},
            ("API",), ("STRUCTURED", "SEMI_STRUCTURED", "NARRATIVE"),
            "VALIDATED_PRIVATE_RESEARCH_WITH_PROVENANCE_WARNING", "API_TIMESTAMPED_PRICE_OR_NEWS_RESPONSE", True,
            "SUPPORTED_STRUCTURED_MARKET_DATA", "API_PRE_CUTOFF_CAPTURE", True,
            "API_OBSERVATION_OR_ARTICLE_TIMESTAMP", "RAW_RESPONSE_FINGERPRINT_AND_SOURCE_HOST", True,
            "ACCOUNT_QUOTA", "PAID", "Historical news is private-research only with original-publisher and licensing limitations.",
        ),
        _record(
            "KSRC_FMP", "Financial Modeling Prep", "Financial Modeling Prep", "financialmodelingprep.com",
            ("FMP", "FINANCIAL_MODELING_PREP"), "MARKET_DATA", "TIER_2_MARKET_DATA",
            ("MARKET_DATA", "OFFICIAL_CALENDAR", "USD_FX_NARRATIVE", "MARKET_EXPECTATIONS"), ("OFFICIAL_CALENDAR", "MARKET_DATA"),
            {"OFFICIAL_CALENDAR": 5, "MARKET_DATA": 10, "USD_FX_NARRATIVE": 40},
            ("API",), ("STRUCTURED",),
            "VALIDATED_STRUCTURED_INPUT", "API_CALENDAR_AND_PRICE_HISTORY", True,
            "SUPPORTED_PRODUCTION_INPUT", "API_CALENDAR_AND_PRICE_CAPTURE", True,
            "API_EVENT_OR_OBSERVATION_TIMESTAMP", "RAW_RESPONSE_AND_VALUE_FINGERPRINT", True,
            "ACCOUNT_QUOTA", "PAID", "Existing calendar and market-data capability; AKSR does not change production use.",
            ai_summary_allowed=False,
        ),
        _record(
            "KSRC_UNIVERSITY_OF_MICHIGAN", "University of Michigan Surveys of Consumers", "University of Michigan", "sca.isr.umich.edu",
            ("UNIVERSITY_OF_MICHIGAN", "MICHIGAN_CONSUMER_SENTIMENT"), "SURVEY", "TIER_1_SURVEY",
            ("CONSUMER_OUTLOOK", "INFLATION_NARRATIVE", "MARKET_EXPECTATIONS"), ("CONSUMER_OUTLOOK", "INFLATION_NARRATIVE"),
            {"CONSUMER_OUTLOOK": 30, "INFLATION_NARRATIVE": 70, "MARKET_EXPECTATIONS": 30},
            ("HTML", "PDF", "SEARCH"), ("STRUCTURED", "NARRATIVE"),
            "APPROVED_NOT_YET_IMPLEMENTED", "SURVEY_RELEASE_ARCHIVE", False,
            "APPROVED_NOT_YET_IMPLEMENTED", "SURVEY_RELEASE_POLL", False,
            "SURVEY_PUBLICATION_TIMESTAMP", "SURVEY_VINTAGE_AND_REVISION_NOTICE", False,
            "PUBLIC_OR_LICENSED", "UNVERIFIED", "Approved source family; acquisition and usage capability not scientifically verified.",
        ),
        _record(
            "KSRC_CME_FEDWATCH", "CME FedWatch", "CME Group", "cmegroup.com",
            ("CME", "CME_FEDWATCH", "FEDWATCH"), "SURVEY", "TIER_1_MARKET_EXPECTATIONS",
            ("FED_EXPECTATIONS", "MARKET_EXPECTATIONS"), ("FED_EXPECTATIONS",),
            {"FED_EXPECTATIONS": 45, "MARKET_EXPECTATIONS": 10},
            ("API", "HTML"), ("STRUCTURED", "SEMI_STRUCTURED"),
            "APPROVED_TRUE_HISTORICAL_SOURCE_NOT_IMPLEMENTED", "HISTORICAL_FUTURES_PROBABILITY_SNAPSHOT", False,
            "APPROVED_NOT_YET_IMPLEMENTED", "PRE_CUTOFF_SNAPSHOT_CAPTURE", False,
            "SNAPSHOT_TIMESTAMP", "CONTRACT_INPUT_AND_CALCULATION_VERSION", False,
            "UNVERIFIED", "UNVERIFIED", "Must not be replaced by a FRED yield proxy or inferred expectation probability.",
            ai_summary_allowed=False,
        ),
        _record(
            "KSRC_CONFERENCE_BOARD", "Conference Board", "The Conference Board", "conference-board.org",
            ("CONFERENCE_BOARD", "THE_CONFERENCE_BOARD"), "SURVEY", "TIER_1_SURVEY",
            ("CONSUMER_OUTLOOK", "LABOR_MARKET", "GROWTH_CONTEXT", "MARKET_EXPECTATIONS"), ("CONSUMER_OUTLOOK",),
            {"CONSUMER_OUTLOOK": 40, "LABOR_MARKET": 35, "GROWTH_CONTEXT": 30},
            ("HTML", "PDF", "SEARCH"), ("STRUCTURED", "NARRATIVE"),
            "APPROVED_NOT_YET_IMPLEMENTED", "SURVEY_RELEASE_ARCHIVE", False,
            "APPROVED_NOT_YET_IMPLEMENTED", "SURVEY_RELEASE_POLL", False,
            "SURVEY_PUBLICATION_TIMESTAMP", "SURVEY_VINTAGE_AND_REVISION_NOTICE", False,
            "PUBLIC_OR_LICENSED", "UNVERIFIED", "Approved source family; acquisition and usage capability not scientifically verified.",
        ),
    ]
    return sorted(rows, key=lambda row: row["source_id"])


def _split(value: Any) -> Tuple[str, ...]:
    return tuple(part for part in _norm(value).split("|") if part)


def _bool(value: Any) -> bool:
    return _norm(value).upper() == "TRUE"


def _topic_from_request(request: Mapping[str, Any]) -> str:
    explicit = _norm(request.get("request_category") or request.get("requested_topic")).upper()
    aliases = {
        "FED_INTERPRETATION": "FED_EXPECTATIONS",
        "FED_EXPECTATIONS": "FED_EXPECTATIONS",
        "INFLATION_NARRATIVE": "INFLATION_NARRATIVE",
        "TREASURY_NARRATIVE": "TREASURY_INTERPRETATION",
        "TREASURY_INTERPRETATION": "TREASURY_INTERPRETATION",
        "CONSUMER_OUTLOOK": "CONSUMER_OUTLOOK",
        "RISK_SENTIMENT": "RISK_SENTIMENT",
        "LABOR_NARRATIVE": "LABOR_MARKET",
        "LABOR_MARKET": "LABOR_MARKET",
        "GROWTH_CONTEXT": "GROWTH_CONTEXT",
        "USD_FX_NARRATIVE": "USD_FX_NARRATIVE",
        "USD_OR_DXY_NARRATIVE": "USD_FX_NARRATIVE",
        "BOJ_CONTEXT": "BOJ_CONTEXT",
        "MARKET_EXPECTATIONS": "MARKET_EXPECTATIONS",
        "PRE_RELEASE_CONSENSUS": "MARKET_EXPECTATIONS",
        "FINANCIAL_CONDITIONS": "FINANCIAL_CONDITIONS",
        "MARKET_DATA": "MARKET_DATA",
        "OFFICIAL_CALENDAR": "OFFICIAL_CALENDAR",
    }
    if explicit in aliases:
        return aliases[explicit]
    text = " ".join(
        _norm(request.get(field)).lower()
        for field in ("information_key", "requested_concept", "requested_information")
    )
    ordered = (
        ("FED_EXPECTATIONS", ("fed", "fomc", "policy expectation", "rate cut")),
        ("INFLATION_NARRATIVE", ("inflation", "cpi", "pce", "price pressure")),
        ("TREASURY_INTERPRETATION", ("treasury", "yield", "bond", "rates market")),
        ("CONSUMER_OUTLOOK", ("consumer outlook", "consumer confidence", "consumer spending")),
        ("LABOR_MARKET", ("labor", "employment", "payroll", "jobless", "wage")),
        ("GROWTH_CONTEXT", ("growth", "gdp", "recession")),
        ("RISK_SENTIMENT", ("risk sentiment", "risk-on", "risk-off", "equity tone")),
        ("USD_FX_NARRATIVE", ("dxy", "dollar", "usdjpy", "usd", "fx")),
        ("BOJ_CONTEXT", ("boj", "bank of japan", "jpy intervention")),
        ("FINANCIAL_CONDITIONS", ("financial conditions", "credit spread", "liquidity")),
        ("MARKET_EXPECTATIONS", ("market expectation", "consensus", "pre-release")),
    )
    for topic, terms in ordered:
        if any(term in text for term in terms):
            return topic
    raise RegistryError("AKSR_REQUEST_TOPIC_UNRESOLVED")


def validate_registry(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    errors: List[str] = []
    source_ids = [_norm(row.get("source_id")) for row in rows]
    if len(set(source_ids)) != len(source_ids):
        errors.append("DUPLICATE_SOURCE_ID")
    aliases: Dict[str, str] = {}
    for row in rows:
        source_id = _norm(row.get("source_id"))
        missing = [header for header in REGISTRY_HEADERS if header not in row]
        if missing:
            errors.append(source_id + ":MISSING_FIELDS:" + ",".join(missing))
        if _norm(row.get("source_class")) not in SOURCE_CLASSES:
            errors.append(source_id + ":INVALID_SOURCE_CLASS")
        if _norm(row.get("lifecycle_stage")) not in LIFECYCLE_STAGES:
            errors.append(source_id + ":INVALID_LIFECYCLE_STAGE")
        for method in _split(row.get("acquisition_method")):
            if method not in ACQUISITION_METHODS and method != "CSV":
                errors.append(source_id + ":INVALID_ACQUISITION_METHOD:" + method)
        for content_type in _split(row.get("content_type")):
            if content_type not in CONTENT_TYPES:
                errors.append(source_id + ":INVALID_CONTENT_TYPE:" + content_type)
        supported = set(_split(row.get("supported_topics")))
        preferred = set(_split(row.get("preferred_topics")))
        excluded = set(_split(row.get("excluded_topics")))
        if not supported.issubset(TOPICS) or not preferred.issubset(TOPICS) or not excluded.issubset(TOPICS):
            errors.append(source_id + ":INVALID_TOPIC")
        if not preferred.issubset(supported) or supported.intersection(excluded):
            errors.append(source_id + ":CONFLICTING_TOPIC_CAPABILITY")
        try:
            priorities = json.loads(_norm(row.get("routing_priority")) or "{}")
        except json.JSONDecodeError:
            errors.append(source_id + ":INVALID_ROUTING_PRIORITY_JSON")
            priorities = {}
        if not set(priorities).issubset(supported):
            errors.append(source_id + ":ROUTING_TOPIC_NOT_SUPPORTED")
        policy = PROVENANCE_POLICIES.get(_norm(row.get("provenance_policy_id")))
        if not policy or policy["source_class"] != _norm(row.get("source_class")):
            errors.append(source_id + ":PROVENANCE_POLICY_MISMATCH")
        for alias in (source_id, *_split(row.get("source_aliases"))):
            key = alias.upper()
            if key in aliases and aliases[key] != source_id:
                errors.append(source_id + ":DUPLICATE_ALIAS:" + key)
            aliases[key] = source_id
    return {
        "registry_version": REGISTRY_VERSION,
        "source_count": len(rows),
        "source_class_counts": {source_class: sum(_norm(row.get("source_class")) == source_class for row in rows) for source_class in sorted(SOURCE_CLASSES)},
        "errors": sorted(set(errors)),
        "status": "PASS" if not errors else "FAIL",
        "registry_fingerprint": registry_fingerprint(rows),
    }


def registry_fingerprint(rows: Sequence[Mapping[str, Any]]) -> str:
    stable = [{header: row.get(header, "") for header in REGISTRY_HEADERS} for row in sorted(rows, key=lambda item: _norm(item.get("source_id")))]
    return fingerprint(stable)


def alias_index(rows: Optional[Sequence[Mapping[str, Any]]] = None) -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}
    for raw in rows or initial_registry():
        row = dict(raw)
        for alias in (_norm(row.get("source_id")), *_split(row.get("source_aliases"))):
            if alias:
                index[alias.upper()] = row
    return index


def resolve_source(source_identity: Any, rows: Optional[Sequence[Mapping[str, Any]]] = None) -> Dict[str, Any]:
    source = alias_index(rows).get(_norm(source_identity).upper())
    if not source:
        raise RegistryError("AKSR_SOURCE_NOT_REGISTERED:" + _norm(source_identity))
    return dict(source)


def route_request(
    request: Mapping[str, Any], mode: str, rows: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """Route by requested topic only; provider identity never affects ordering."""
    if mode not in MODES:
        raise RegistryError("AKSR_INVALID_MODE:" + _norm(mode))
    topic = _topic_from_request(request)
    configured: List[Tuple[int, str, Dict[str, Any], bool]] = []
    candidates: List[Tuple[int, str, Dict[str, Any]]] = []
    excluded: List[Dict[str, Any]] = []
    for raw in rows or initial_registry():
        row = dict(raw)
        source_id = row["source_id"]
        supported = topic in _split(row.get("supported_topics"))
        explicitly_excluded = topic in _split(row.get("excluded_topics"))
        mode_supported = _bool(row.get("historical_supported" if mode == "HISTORICAL_REPLAY" else "prospective_supported"))
        if row.get("lifecycle_stage") != "APPROVED_SOURCE" or not _norm(row.get("status")).startswith("APPROVED_SOURCE"):
            excluded.append({"source_id": source_id, "reason": "SOURCE_NOT_APPROVED"})
            continue
        if explicitly_excluded:
            excluded.append({"source_id": source_id, "reason": "TOPIC_EXCLUDED"})
            continue
        if not supported:
            excluded.append({"source_id": source_id, "reason": "TOPIC_UNSUPPORTED"})
            continue
        priorities = json.loads(_norm(row.get("routing_priority")) or "{}")
        priority = int(priorities.get(topic, 1000))
        configured.append((priority, source_id, row, mode_supported))
        if not mode_supported:
            excluded.append({"source_id": source_id, "reason": mode + "_NOT_VALIDATED"})
            continue
        candidates.append((priority, source_id, row))
    configured.sort(key=lambda item: (item[0], item[1]))
    candidates.sort(key=lambda item: (item[0], item[1]))
    provider_request_id = _norm(request.get("provider_request_id") or request.get("request_id"))
    normalized_request_id = _norm(request.get("normalized_request_id"))
    route_identity = {
        "registry_version": REGISTRY_VERSION,
        "mode": mode,
        "session_id": _norm(request.get("session_id")),
        "normalized_request_id": normalized_request_id,
        "topic": topic,
        "source_ids": [item[1] for item in candidates],
    }
    return {
        "route_id": "AKSR_ROUTE_" + fingerprint(route_identity)[:24],
        "registry_version": REGISTRY_VERSION,
        "mode": mode,
        "session_id": route_identity["session_id"],
        "provider_request_id": provider_request_id,
        "normalized_request_id": normalized_request_id,
        "requested_topic": topic,
        "configured_routes": [
            {
                "configured_rank": rank,
                "source_id": source_id,
                "source_name": row["source_name"],
                "mode_supported": mode_supported,
                "provenance_policy_id": row["provenance_policy_id"],
            }
            for rank, (_, source_id, row, mode_supported) in enumerate(configured, start=1)
        ],
        "source_routes": [
            {
                "route_rank": rank,
                "source_id": source_id,
                "source_name": row["source_name"],
                "source_class": row["source_class"],
                "acquisition_method": row["acquisition_method"],
                "provenance_policy_id": row["provenance_policy_id"],
                "ai_summary_allowed": _bool(row["ai_summary_allowed"]),
            }
            for rank, (_, source_id, row) in enumerate(candidates, start=1)
        ],
        "excluded_sources": sorted(excluded, key=lambda item: (item["source_id"], item["reason"])),
        "provider_neutral": True,
        "status": "ROUTED" if candidates else "NO_APPROVED_VALIDATED_ROUTE",
    }


def validate_source_use(
    source_identity: Any, mode: str, topic: str, rows: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Tuple[bool, str]:
    source = resolve_source(source_identity, rows)
    if mode not in MODES:
        return False, "INVALID_MODE"
    if source.get("lifecycle_stage") != "APPROVED_SOURCE":
        return False, "SOURCE_NOT_APPROVED"
    if topic not in _split(source.get("supported_topics")):
        return False, "TOPIC_UNSUPPORTED"
    if topic in _split(source.get("excluded_topics")):
        return False, "TOPIC_EXCLUDED"
    supported_field = "historical_supported" if mode == "HISTORICAL_REPLAY" else "prospective_supported"
    if not _bool(source.get(supported_field)):
        return False, mode + "_NOT_VALIDATED"
    return True, "PASS"


def transition_source_lifecycle(
    source: Mapping[str, Any], target_stage: str, validation_evidence: Mapping[str, Any],
) -> Dict[str, Any]:
    """Advance exactly one lifecycle stage; backward or skipped promotion fails."""
    current = _norm(source.get("lifecycle_stage"))
    if current not in LIFECYCLE_STAGES or target_stage not in LIFECYCLE_STAGES:
        raise RegistryError("AKSR_INVALID_LIFECYCLE_STAGE")
    if not validation_evidence or not _norm(validation_evidence.get("validation_id")):
        raise RegistryError("AKSR_LIFECYCLE_EVIDENCE_REQUIRED")
    current_index = LIFECYCLE_STAGES.index(current)
    target_index = LIFECYCLE_STAGES.index(target_stage)
    if target_index != current_index + 1:
        raise RegistryError("AKSR_LIFECYCLE_TRANSITION_NOT_SEQUENTIAL")
    result = dict(source)
    result["lifecycle_stage"] = target_stage
    result["status"] = "APPROVED_SOURCE_CAPABILITY_GATED" if target_stage == "APPROVED_SOURCE" else target_stage
    result["last_validation"] = _norm(validation_evidence.get("validated_at"))
    result["validation_notes"] = _norm(validation_evidence.get("notes"))
    result["lifecycle_validation_id"] = _norm(validation_evidence.get("validation_id"))
    return result


def _parse_timestamp(value: Any) -> datetime:
    text = _norm(value)
    if not text:
        raise RegistryError("PUBLICATION_TIMESTAMP_MISSING")
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise RegistryError("PUBLICATION_TIMEZONE_UNPROVABLE")
    return parsed.astimezone(timezone.utc)


def _parse_publication_timestamp(value: Any, precision: str) -> datetime:
    text = _norm(value)
    if precision == "DATE_ONLY" and len(text) >= 10:
        try:
            return datetime.fromisoformat(text[:10]).replace(tzinfo=timezone.utc)
        except ValueError as exc:
            raise RegistryError("PUBLICATION_DATE_INVALID") from exc
    return _parse_timestamp(value)


def admit_knowledge_item(
    item: Mapping[str, Any], request: Mapping[str, Any], mode: str,
    rows: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """Apply source approval and item-specific admission as separate gates."""
    source = resolve_source(item.get("source_id") or item.get("source_family"), rows)
    topic = _topic_from_request(request)
    allowed, reason = validate_source_use(source["source_id"], mode, topic, rows)
    rejection: List[str] = [] if allowed else [reason]
    if not _norm(item.get("knowledge_item_id") or item.get("source_record_id")):
        rejection.append("KNOWLEDGE_ITEM_ID_MISSING")
    cutoff_text = _norm(request.get("forecast_cutoff"))
    try:
        cutoff = _parse_timestamp(cutoff_text)
        precision = _norm(item.get("timestamp_precision") or "EXACT_DATETIME")
        publication = _parse_publication_timestamp(item.get("publication_timestamp"), precision)
        if publication > cutoff:
            rejection.append("SOURCE_AFTER_FORECAST_CUTOFF")
        policy = PROVENANCE_POLICIES[source["provenance_policy_id"]]["historical" if mode == "HISTORICAL_REPLAY" else "prospective"]
        if precision == "DATE_ONLY" and publication.date() == cutoff.date() and policy["exact_time_required_same_day"]:
            rejection.append("SAME_DAY_TIME_UNPROVABLE")
    except RegistryError as exc:
        rejection.append(str(exc))
    if source["publisher_verification"] == "REQUIRED" and not _norm(item.get("publisher") or item.get("source_host")):
        rejection.append("PUBLISHER_VERIFICATION_MISSING")
    if _bool(source["citation_required"]) and not _norm(item.get("canonical_url") or item.get("source_reference")):
        rejection.append("CITATION_MISSING")
    if not _norm(item.get("content_fingerprint")):
        rejection.append("CONTENT_FINGERPRINT_MISSING")
    if not _norm(item.get("historical_state_evidence") or item.get("provenance_evidence")):
        rejection.append("PROVENANCE_EVIDENCE_MISSING")
    if _norm(item.get("relevance_status")) not in {"PASS", "RELEVANT", "RELEVANT_FULL_TEXT", "RELEVANT_SUFFICIENT_EXCERPT"}:
        rejection.append("SOURCE_NOT_RELEVANT")
    if _norm(item.get("outcome_leakage_status")) not in {"PASS", "NO_OUTCOME_LEAKAGE"}:
        rejection.append("SOURCE_CONTAINS_OUTCOME_LEAKAGE")
    if source["source_class"] in {"INSTITUTIONAL_RESEARCH", "NEWS"}:
        revision = _norm(item.get("revision_status"))
        if revision not in {"NO_SUBSTANTIVE_REVISION_DETECTED", "IMMUTABLE", "VERSION_PINNED"}:
            rejection.append("REVISION_STATE_UNPROVABLE")
    rejection = sorted(set(rejection))
    return {
        "source_id": source["source_id"],
        "knowledge_item_id": _norm(item.get("knowledge_item_id") or item.get("source_record_id")),
        "session_id": _norm(request.get("session_id")),
        "provider_request_id": _norm(request.get("provider_request_id") or request.get("request_id")),
        "normalized_request_id": _norm(request.get("normalized_request_id")),
        "mode": mode,
        "requested_topic": topic,
        "source_approval_status": "PASS" if allowed else "FAIL",
        "article_admission_status": "ADMITTED" if not rejection else "REJECTED",
        "rejection_reasons": rejection,
        "provenance_policy_id": source["provenance_policy_id"],
        "registry_version": REGISTRY_VERSION,
    }


def suppress_duplicate_items(items: Iterable[Mapping[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    accepted: List[Dict[str, Any]] = []
    duplicates: List[Dict[str, Any]] = []
    seen: Dict[str, str] = {}
    for raw in items:
        row = dict(raw)
        identity = _norm(row.get("knowledge_item_id") or row.get("source_record_id"))
        if not identity:
            identity = fingerprint({
                "source_id": row.get("source_id"),
                "canonical_url": row.get("canonical_url") or row.get("source_reference"),
                "publication_timestamp": row.get("publication_timestamp"),
                "content_fingerprint": row.get("content_fingerprint"),
            })
        if identity in seen:
            duplicates.append({**row, "duplicate_of": seen[identity], "duplicate_status": "SOURCE_DUPLICATE"})
            continue
        seen[identity] = identity
        accepted.append(row)
    return accepted, duplicates


def build_traceability_record(
    *, request: Mapping[str, Any], route: Mapping[str, Any], knowledge_item: Mapping[str, Any],
    luna_evidence: Mapping[str, Any], pack_entry: Mapping[str, Any], mode: str,
) -> Dict[str, Any]:
    required = {
        "session_id": request.get("session_id"),
        "provider_request_id": request.get("provider_request_id") or request.get("request_id"),
        "normalized_request_id": request.get("normalized_request_id"),
        "route_id": route.get("route_id"),
        "source_id": knowledge_item.get("source_id"),
        "knowledge_item_id": knowledge_item.get("knowledge_item_id") or knowledge_item.get("source_record_id"),
        "luna_evidence_id": luna_evidence.get("luna_evidence_id") or luna_evidence.get("acquisition_result_id"),
        "pack_entry_id": pack_entry.get("pack_entry_id") or pack_entry.get("item_id"),
    }
    missing = [name for name, value in required.items() if not _norm(value)]
    if missing:
        raise RegistryError("AKSR_TRACE_IDENTITY_MISSING:" + ",".join(sorted(missing)))
    route_ids = {row["source_id"] for row in route.get("source_routes", [])}
    if _norm(required["source_id"]) not in route_ids:
        raise RegistryError("AKSR_TRACE_SOURCE_NOT_IN_ROUTE")
    if _norm(luna_evidence.get("source_id")) != _norm(required["source_id"]):
        raise RegistryError("AKSR_TRACE_LUNA_SOURCE_MISMATCH")
    if _norm(pack_entry.get("luna_evidence_id")) != _norm(required["luna_evidence_id"]):
        raise RegistryError("AKSR_TRACE_PACK_EVIDENCE_MISMATCH")
    trace_identity = {**required, "mode": mode, "registry_version": REGISTRY_VERSION}
    return {
        "trace_id": "AKSR_TRACE_" + fingerprint(trace_identity)[:24],
        **trace_identity,
        "relationship": "SESSION>PROVIDER_REQUEST>KNOWLEDGE_SOURCE>KNOWLEDGE_ITEM>LUNA_EVIDENCE>PACK_ENTRY",
        "traceability_status": "PASS",
    }


def replay_compatibility_aliases() -> Dict[str, str]:
    aliases = alias_index()
    required = (
        "FOMC_POLICY_INTERPRETATION",
        "BEIGE_BOOK_MARKET_CONTACT_CONTEXT",
        "APOLLO_DAILY_SPARK",
        "PIMCO_INSIGHTS",
        "BLACKROCK_INVESTMENT_INSTITUTE",
        "EODHD",
        "FMP",
        "FRED",
        "BLS",
        "BEA",
    )
    return {alias: aliases[alias]["source_id"] for alias in required}
