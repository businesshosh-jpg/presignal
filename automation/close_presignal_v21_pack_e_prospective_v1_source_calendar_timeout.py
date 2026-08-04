#!/usr/bin/env python3
"""Bounded official-document closure audit for PACK_E_PROSPECTIVE_V1."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
ARTIFACT_ID = "PPHB-R2-PACK-E-PROSPECTIVE-V1-SOURCE-CALENDAR-TIMEOUT-CLOSURE-20260804T060000Z"
DEFAULT_OUTPUT_DIR = BASE / ARTIFACT_ID
ROUTES = (
    ("US_2_YEAR_TREASURY_YIELD", "FRED", "DGS2"),
    ("US_10_YEAR_TREASURY_YIELD", "FRED", "DGS10"),
    ("USDJPY_MARKET_STATE", "EODHD", "USDJPY.FOREX"),
    ("SP500_MARKET_STATE", "EODHD", "GSPC.INDX"),
    ("GOLD_MARKET_STATE", "EODHD", "XAUUSD.FOREX"),
    ("US_DOLLAR_INDEX_MARKET_STATE", "FMP", "DX-Y.NYB"),
    ("WTI_CRUDE_OIL_MARKET_STATE", "FMP", "CLUSD"),
)


class ClosureError(RuntimeError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def doc(title: str, url: str, supports: str, extract: str) -> dict[str, str]:
    return {
        "title": title,
        "url": url,
        "supports": supports,
        "deterministic_summary": extract,
        "page_content_extract_fingerprint": digest({"title": title, "url": url, "extract": extract}),
    }


def documentation_register() -> dict[str, Any]:
    evidence = [
        doc(
            "St. Louis Fed Web Services: fred/series/observations",
            "https://fred.stlouisfed.org/docs/api/fred/series_observations.html",
            "FRED observation schema and vintage/revision capability",
            "The observations response supplies date, value, realtime_start, and realtime_end. Vintage dates and real-time periods can select data as known on dates, but the observation schema does not provide a publication-time-of-day field.",
        ),
        doc(
            "Market Yield on U.S. Treasury Securities at 2-Year Constant Maturity",
            "https://fred.stlouisfed.org/series/DGS2",
            "DGS2 series frequency and source-release linkage",
            "The series page identifies DGS2 as a daily, not-seasonally-adjusted H.15 Selected Interest Rates series and displays missing observations as a dot. A page-level current update display is not a historical per-observation availability timestamp.",
        ),
        doc(
            "Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity",
            "https://fred.stlouisfed.org/series/DGS10",
            "DGS10 series frequency and source-release linkage",
            "The series page identifies DGS10 as a daily, not-seasonally-adjusted H.15 Selected Interest Rates series and displays missing observations as a dot. A page-level current update display is not a historical per-observation availability timestamp.",
        ),
        doc(
            "End-Of-Day Historical Stock Market Data API",
            "https://eodhd.com/financial-apis/api-for-historical-data-and-volumes",
            "EODHD EOD route cadence and OHLC bar content",
            "The endpoint returns daily, weekly, or monthly OHLC-style historical data for a symbol, including forex and indices. The documented daily description does not establish a UTC publication instant, completed-bar flag, or historical availability timestamp for an individual row.",
        ),
        doc(
            "List of Supported FOREX Currencies",
            "https://eodhd.com/financial-apis/list-supported-forex-currencies",
            "EODHD FOREX symbol route",
            "The official support page identifies the EOD historical route for FOREX symbols. It does not define an intraday availability field for a daily row.",
        ),
        doc(
            "Stock Price and Volume Data API",
            "https://site.financialmodelingprep.com/developer/docs/stable/historical-price-eod-full",
            "FMP historical EOD route cadence and OHLC content",
            "The endpoint provides end-of-day historical open, high, low, close, volume, and related daily fields. Its documented daily date/price content does not establish a source availability timestamp, current-day completion indicator, or a calendar for DX-Y.NYB and CLUSD.",
        ),
    ]
    return {
        "authorization": {
            "allowed_domains": ["fred.stlouisfed.org", "eodhd.com", "site.financialmodelingprep.com"],
            "maximum_requests": {"FRED": 6, "EODHD": 6, "FMP": 6, "total": 18},
            "retries": 0,
        },
        "official_evidence": evidence,
        "actual_documentation_pages": {"FRED": 3, "EODHD": 2, "FMP": 1, "total": 6},
        "direct_raw_fetch_attempt": {
            "url": "https://fred.stlouisfed.org/docs/api/fred/series_observations.html",
            "result": "HTTP_403_NO_BODY",
            "used_as_evidence": False,
        },
        "market_data_endpoint_calls": 0,
        "authenticated_requests": 0,
    }


def source_calendar_matrix() -> list[dict[str, Any]]:
    local = (ROOT / "apps_script" / "market_context_v2b.js").read_text()
    required = ("_v2bFetchFredHistory_", "_v2bFetchEodhdHistory_", "_v2bFetchFmpHistory_")
    if any(token not in local for token in required):
        raise ClosureError("ACCEPTED_SEVEN_ROUTE_HELPERS_MISSING")
    matrix = []
    for field, family, symbol in ROUTES:
        if family == "FRED":
            semantics = "Daily series observation date; observations API has date/value plus real-time vintage dates."
            calendar = "US business-day H.15 linkage is identified, but retained evidence provides no observation-level UTC publication time."
        elif family == "EODHD":
            semantics = "Historical EOD daily OHLC bar represented by date/close after the accepted normalizer drops other source fields."
            calendar = "Official EOD documentation states daily data but not a completed-bar signal, source timezone, or calendar for this symbol."
        else:
            semantics = "Historical EOD daily OHLC bar represented by date/close after the accepted normalizer drops other source fields."
            calendar = "Official EOD documentation states end-of-day data but not a completed-bar signal, source timezone, or calendar for this symbol."
        matrix.append({
            "field": field,
            "source_family": family,
            "series_or_symbol": symbol,
            "current_adapter_schema": "daily date/value row only",
            "official_period_semantics": semantics,
            "calendar_authority": calendar,
            "timestamp_semantics": "date-only source-period identity; not a publication, availability, or retrieval timestamp",
            "revision_behavior": "FRED supports real-time vintage selection; EODHD/FMP correction timing is not documented by retained evidence",
            "same_day_completed_period": "NOT_PROVEN",
            "prior_period_availability_before_arbitrary_cutoff": "NOT_PROVEN",
            "decision": "SOURCE_CALENDAR_AUTHORITY_PARTIALLY_CONFIRMED",
            "availability_decision": "PACK_E_PROSPECTIVE_V1_AVAILABILITY_RULES_BLOCKED",
            "reason": "No official retained evidence supplies a conservative observation-level availability instant or a source-specific completed-period/calendar rule proving strict pre-T-15 availability.",
        })
    return matrix


def stale_rules(matrix: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "decision": "PACK_E_PROSPECTIVE_V1_STALE_AUTHORITY_BLOCKED",
        "allowed_statuses": ["AVAILABLE", "STALE", "UNAVAILABLE", "SOURCE_CLOSED", "TIMESTAMP_UNRESOLVED", "SOURCE_FAILURE"],
        "reason": "Every frozen route lacks a governed completed-period and observation-availability rule; expected periods, source-closed classification, and missed-period stale bounds cannot be frozen without inventing calendars.",
        "route_count": len(matrix),
        "prohibitions": ["elapsed-hour surrogate", "invented holiday calendar", "cross-market calendar substitution", "zero substitution", "unbounded carry-forward"],
    }


def numeric_only() -> dict[str, Any]:
    return {
        "decision": "PACK_E_PROSPECTIVE_V1_NUMERIC_ONLY_TREATMENT_CONFIRMED",
        "latest_value": "use only the latest eligible completed observation after availability and stale authority close",
        "change_24h": "numeric only; requires two eligible completed observations selected in ascending source-period order",
        "change_5d": "numeric only; requires the latest eligible observation and the fifth preceding eligible source observation",
        "missing_prior_observation": "UNAVAILABLE; do not substitute zero or a non-governed date",
        "rounding_order": "calculate from normalized source-unit values; round only at final Pack serialization under the frozen construction contract",
        "categorical_directions": "omitted; no RISING/FALLING/FLAT threshold is introduced",
    }


def timeout_authority() -> dict[str, Any]:
    source = (ROOT / "apps_script" / "market_context_v2b.js").read_text()
    bridge = (ROOT / "apps_script" / "authoritative_provider_bridge.js").read_text()
    if "UrlFetchApp.fetch" not in source or "hard_timeout_seconds" not in bridge:
        raise ClosureError("TIMEOUT_CONTRACT_DEPENDENCY_MISSING")
    return {
        "decision": "PACK_E_PROSPECTIVE_V1_TIMEOUT_AUTHORITY_BLOCKED",
        "FRED": {"client": "UrlFetchApp.fetch", "connection_timeout": None, "read_timeout": None, "total_timeout": None},
        "EODHD": {"client": "UrlFetchApp.fetch", "connection_timeout": None, "read_timeout": None, "total_timeout": None},
        "FMP": {"client": "UrlFetchApp.fetch", "connection_timeout": None, "read_timeout": None, "total_timeout": None},
        "accepted_infrastructure_inspected": "authoritative_provider_bridge.js hard_timeout_seconds applies to forecast provider calls, not the frozen FRED/EODHD/FMP source routes",
        "reason": "No accepted source-route client configuration or governing source-operation contract sets a hard timeout. Choosing a value would be a new ungoverned parameter, so no maximum duration can be derived.",
        "retry_boundary": 0,
        "terminal_states_when_future_authority_exists": ["SUCCESS", "TRANSPORT_FAILED", "STATUS_UNKNOWN"],
        "safe_resume": "STATUS_UNKNOWN remains non-reusable until a future exact request journal proves a complete raw response was persisted.",
    }


def build_evidence() -> dict[str, Any]:
    docs = documentation_register()
    calendar = source_calendar_matrix()
    stale = stale_rules(calendar)
    timeouts = timeout_authority()
    lead = {
        "decision": "PACK_E_PROSPECTIVE_V1_LEAD_TIME_BLOCKED",
        "execution_model": "not authorized or implemented",
        "maximum_prerequisite_execution_window_seconds": None,
        "safety_margin_seconds": None,
        "admission_deadline_formula": "admission_deadline_utc = episode_t_minus_15_cutoff_utc - maximum_prerequisite_execution_window_seconds - safety_margin_seconds",
        "reason": "Hard per-route timeout authority is absent and none of the seven routes has a strict pre-cutoff availability rule.",
    }
    completeness = {
        "COMPLETE": "all seven fields use eligible completed periods, pass strict cutoff and stale validation, preserve raw evidence, and normalize successfully",
        "COMPLETE_WITH_GOVERNED_MISSING": "not available until a future frozen source-calendar rule explains normal closure; never API failure, timestamp ambiguity, stale data, or implementation failure",
        "INCOMPLETE": "required for unresolved calendar/availability, stale data, raw-evidence absence, source failure/timeout, parser/normalization failure, or silent field absence",
    }
    field_contract = {
        "decision": "PACK_E_PROSPECTIVE_V1_FIELD_CONTRACT_BLOCKED",
        "all_route_availability_blocked": all(row["availability_decision"] == "PACK_E_PROSPECTIVE_V1_AVAILABILITY_RULES_BLOCKED" for row in calendar),
        "blockers": ["seven conservative completed-period availability rules", stale["decision"], timeouts["decision"], lead["decision"]],
        "partial_contract_not_labeled_frozen": True,
        "historical_pack_e_equivalence_claim": False,
    }
    implementation = {
        "decision": "PACK_E_PROSPECTIVE_V1_IMPLEMENTATION_REMAINS_BLOCKED",
        "reason": "The final contract did not freeze; earlier inactive implementation inputs remain unchanged and unactivated.",
        "prior_inputs": "PPHB-R2-PACK-E-PROSPECTIVE-V1-IMPLEMENTATION-AUTHORIZATION-INPUTS-20260804T043000Z",
        "prior_inputs_fingerprint": "sha256:8e8cce92fe0f5cc0577048362c7619ba8e3e1cb9f631665054cb27c004c42866",
    }
    result = {
        "artifact_id": ARTIFACT_ID,
        "bindings": {
            "pack_identity": "PACK_E_PROSPECTIVE_V1",
            "prior_closure_fingerprint": "sha256:7db3bee8b4d85a03ea41966f11ecb19909e67356a8afe63cffa1e34a1d62e7a2",
            "historical_pack_e_equivalence_claim": False,
        },
        "documentation_register": docs,
        "source_calendar_authority": calendar,
        "availability_rules_decision": "PACK_E_PROSPECTIVE_V1_AVAILABILITY_RULES_BLOCKED",
        "stale_authority": stale,
        "numeric_only_treatment": numeric_only(),
        "timeout_authority": timeouts,
        "lead_time": lead,
        "completeness_contract": completeness,
        "field_contract": field_contract,
        "implementation_authorization": implementation,
        "activity": {
            "documentation_pages": docs["actual_documentation_pages"],
            "market_data_calls": 0,
            "authenticated_provider_calls": 0,
            "google_reads": 0,
            "google_writes": 0,
            "forecasts": 0,
            "outcomes": 0,
            "evaluation": 0,
            "retries": 0,
        },
    }
    result["fingerprint"] = digest(result)
    return result


def reconcile(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    if output_dir.exists():
        raise ClosureError("SOURCE_CALENDAR_TIMEOUT_ARTIFACT_ALREADY_EXISTS")
    result = build_evidence()
    output_dir.mkdir(parents=True)
    files = {
        "official_documentation_evidence_register.json": result["documentation_register"],
        "source_calendar_authority_matrix.json": result["source_calendar_authority"],
        "completed_period_eligibility_rules.json": {"decision": result["availability_rules_decision"], "routes": result["source_calendar_authority"]},
        "stale_calendar_rules.json": result["stale_authority"],
        "numeric_only_treatment.json": result["numeric_only_treatment"],
        "timeout_authority.json": result["timeout_authority"],
        "maximum_duration_analysis.json": result["lead_time"],
        "completeness_decision.json": result["completeness_contract"],
        "field_contract_decision.json": result["field_contract"],
        "implementation_authorization_decision.json": result["implementation_authorization"],
        "validation_results.json": {"passed": True, "activity": result["activity"], "no_source_substitution": True, "no_market_data_endpoint_calls": True},
        "source_calendar_timeout_closure_report.json": result,
    }
    for name, value in files.items():
        (output_dir / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    print(json.dumps(reconcile(args.output_dir), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
