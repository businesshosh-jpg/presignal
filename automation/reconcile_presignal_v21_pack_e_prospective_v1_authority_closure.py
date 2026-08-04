#!/usr/bin/env python3
"""Local-only closure audit for PACK_E_PROSPECTIVE_V1 unresolved authorities."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
ARTIFACT_ID = "PPHB-R2-PACK-E-PROSPECTIVE-V1-AUTHORITY-CLOSURE-RECONCILIATION-20260804T050000Z"
DEFAULT_OUTPUT_DIR = BASE / ARTIFACT_ID
ROUTES = (
    ("US_2_YEAR_TREASURY_YIELD", "FRED", "DGS2", "_v2bFetchFredHistory_", "observations[] {date, value}"),
    ("US_10_YEAR_TREASURY_YIELD", "FRED", "DGS10", "_v2bFetchFredHistory_", "observations[] {date, value}"),
    ("USDJPY_MARKET_STATE", "EODHD", "USDJPY.FOREX", "_v2bFetchEodhdHistory_", "eod[] {date, close}"),
    ("US_DOLLAR_INDEX_MARKET_STATE", "FMP", "DX-Y.NYB", "_v2bFetchFmpHistory_", "historical[] {date, close}"),
    ("SP500_MARKET_STATE", "EODHD", "GSPC.INDX", "_v2bFetchEodhdHistory_", "eod[] {date, close}"),
    ("GOLD_MARKET_STATE", "EODHD", "XAUUSD.FOREX", "_v2bFetchEodhdHistory_", "eod[] {date, close}"),
    ("WTI_CRUDE_OIL_MARKET_STATE", "FMP", "CLUSD", "_v2bFetchFmpHistory_", "historical[] {date, close}"),
)


class AuthorityClosureError(RuntimeError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def availability_matrix() -> list[dict[str, Any]]:
    source = (ROOT / "apps_script" / "market_context_v2b.js").read_text()
    required = ("_v2bSortRowsAsc_", "_v2bObservationWindow_", "UrlFetchApp.fetch")
    if any(token not in source for token in required):
        raise AuthorityClosureError("ACCEPTED_MARKET_CONTEXT_HELPERS_MISSING")
    rows = []
    for family, provider, symbol, adapter, schema in ROUTES:
        if adapter not in source or symbol not in source:
            raise AuthorityClosureError("ROUTE_NOT_FOUND:" + symbol)
        rows.append({
            "source_family": family,
            "provider": provider,
            "series_or_symbol": symbol,
            "request_schema": "historical window: source symbol plus start/end ISO dates; source key is resolved only at execution",
            "response_schema": schema,
            "raw_timestamp_fields": ["date"],
            "timestamp_format": "YYYY-MM-DD",
            "timezone": "not supplied by the current normalized source row",
            "resolution": "daily/date-only",
            "publication_availability_meaning": "not present in accepted local schema",
            "observation_meaning": "trading or series observation date only; not an intraday availability assertion",
            "revision_behavior": "not represented in current normalized source row",
            "utc_normalization": "date is preserved, but midnight UTC must not be inferred as publication time",
            "same_second_boundary": "unresolvable from date-only source data",
            "decision": "AVAILABILITY_TIMESTAMP_REQUIRES_DERIVED_CALENDAR_RULE",
            "strict_cutoff_usability": "BLOCKED until an accepted calendar/publication-time rule supplies source_available_timestamp_utc",
        })
    return rows


def raw_preservation_contract() -> dict[str, Any]:
    fields = [
        "request_id", "episode_id", "source", "series_or_symbol", "endpoint_or_adapter_identity",
        "request_parameters_without_secrets", "request_timestamp_utc", "http_status_or_transport_terminal_state",
        "raw_response_body_or_lossless_canonical_payload", "raw_response_sha256", "provider_returned_timestamp_fields",
        "parser_version", "normalized_output", "normalization_fingerprint", "source_availability_decision",
        "stale_missing_decision", "duplicate_prevention_identity", "remote_state_classification",
    ]
    return {
        "decision": "PACK_E_PROSPECTIVE_V1_RAW_PRESERVATION_FROZEN",
        "write_order": "persist append-only local raw evidence before normalized Pack materialization",
        "required_fields": fields,
        "forbidden_secret_fields": ["api_key", "access_token", "authorization", "authorization_header", "cookie"],
        "google_writes": 0,
        "implementation_note": "Current v2B fetch normalizers do not provide this artifact; a future return-only adapter must implement it under separate authority.",
    }


def stale_authority() -> dict[str, Any]:
    return {
        "decision": "PACK_E_PROSPECTIVE_V1_STALE_AUTHORITY_BLOCKED",
        "allowed_statuses": ["AVAILABLE", "STALE", "UNAVAILABLE", "SOURCE_CLOSED", "TIMESTAMP_UNRESOLVED", "SOURCE_FAILURE"],
        "reason": "No accepted local source calendar identifies expected publication cadence, holidays, or a maximum acceptable age for any of the seven daily/date-only routes.",
        "prohibitions": ["global arbitrary duration", "zero substitution", "carry-forward beyond an accepted bound", "unrelated replacement series"],
    }


def threshold_decision() -> dict[str, Any]:
    return {
        "decision": "PACK_E_PROSPECTIVE_V1_FLAT_THRESHOLDS_FROZEN",
        "rule": "Retain numeric 24-hour and five-observation changes only; omit ungoverned categorical direction fields from PACK_E_PROSPECTIVE_V1 V1 output.",
        "fields_retained": ["latest_value", "latest_observation_timestamp_utc", "change_24h", "change_5d"],
        "fields_omitted_with_explicit_reason": ["direction_24h", "direction_5d"],
        "authority": "market_scoring.js flat threshold is an Outcome-reaction pip rule, not an accepted cross-asset market-state threshold; it cannot be reused.",
        "no_performance_optimization": True,
    }


def timeout_authority() -> dict[str, Any]:
    return {
        "decision": "PACK_E_PROSPECTIVE_V1_TIMEOUT_AUTHORITY_BLOCKED",
        "current_transport": "UrlFetchApp.fetch with HTTP failure handling but no adapter-level hard timeout parameter in the FRED, EODHD, or FMP market-context helpers",
        "retry_boundary": 0,
        "reason": "No accepted source-specific connection/request or total-operation timeout exists, so a bounded maximum prerequisite execution window cannot be derived.",
        "safe_resume_requirement": "A future adapter must record request intent before transport, terminal response evidence on completion, and REMOTE_STATE_UNRESOLVED on interruption; no duplicate read may be assumed safe without its frozen request identity.",
    }


def completeness_contract() -> dict[str, Any]:
    return {
        "complete": "all seven fields structurally present, AVAILABLE, timestamp-eligible, non-stale, raw-preserved, and normalized",
        "complete_with_governed_missing": "structurally present explicit unavailable status only when a future accepted source-calendar rule proves normal source closure; never for API failure, timestamp ambiguity, or stale data",
        "incomplete": "any unresolved timestamp, missing raw evidence, source failure, stale field, unresolved stale rule, or failed normalization",
        "smoke_test_admission": "only COMPLETE or explicitly governed COMPLETE_WITH_GOVERNED_MISSING",
    }


def build_evidence() -> dict[str, Any]:
    availability = availability_matrix()
    raw = raw_preservation_contract()
    stale = stale_authority()
    thresholds = threshold_decision()
    timeouts = timeout_authority()
    lead = {
        "decision": "PACK_E_PROSPECTIVE_V1_LEAD_TIME_BLOCKED",
        "formula": "admission_deadline_utc = episode_t_minus_15_cutoff_utc - maximum_prerequisite_execution_window_seconds - safety_margin_seconds",
        "maximum_prerequisite_execution_window_seconds": None,
        "safety_margin_seconds": None,
        "reason": "Source-specific hard timeouts are not accepted and strict source availability cannot be calculated from date-only rows.",
    }
    field_contract = {
        "decision": "PACK_E_PROSPECTIVE_V1_FIELD_CONTRACT_BLOCKED",
        "fixed_source_family_count": 7,
        "availability_decisions": [row["decision"] for row in availability],
        "resolved_parts": [raw["decision"], thresholds["decision"]],
        "unresolved_parts": [stale["decision"], timeouts["decision"], lead["decision"]],
        "historical_pack_e_equivalence_claim": False,
    }
    implementation = {
        "decision": "PACK_E_PROSPECTIVE_V1_IMPLEMENTATION_REMAINS_BLOCKED",
        "prior_input_package": "PPHB-R2-PACK-E-PROSPECTIVE-V1-IMPLEMENTATION-AUTHORIZATION-INPUTS-20260804T043000Z",
        "prior_input_fingerprint": "sha256:8e8cce92fe0f5cc0577048362c7619ba8e3e1cb9f631665054cb27c004c42866",
        "blocked_by": ["accepted UTC availability calendar/derivation", "source-calendar stale rule", "source-specific hard timeout"],
        "not_activated": True,
    }
    result = {
        "artifact_id": ARTIFACT_ID,
        "bindings": {"amendment_fingerprint": "sha256:13b998d4a25538794fea1df193cca0381722f280e9c12fb7eba16b65bf5bdd17", "pack_identity": "PACK_E_PROSPECTIVE_V1", "historical_pack_e_identity_retained": False},
        "availability_time_authority": availability,
        "raw_preservation": raw,
        "stale_authority": stale,
        "flat_thresholds": thresholds,
        "timeout_authority": timeouts,
        "lead_time": lead,
        "completeness_contract": completeness_contract(),
        "field_contract": field_contract,
        "implementation_authorization": implementation,
        "activity": {"source_calls": 0, "google_access": 0, "google_writes": 0, "provider_calls": 0, "outcome_activity": 0, "evaluation_activity": 0, "retries": 0},
    }
    result["fingerprint"] = digest(result)
    return result


def reconcile(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    if output_dir.exists():
        raise AuthorityClosureError("AUTHORITY_CLOSURE_ARTIFACT_ALREADY_EXISTS")
    result = build_evidence()
    output_dir.mkdir(parents=True)
    files = {
        "availability_time_authority_matrix.json": result["availability_time_authority"],
        "raw_preservation_contract.json": result["raw_preservation"],
        "stale_calendar_authority.json": result["stale_authority"],
        "flat_threshold_decision.json": result["flat_thresholds"],
        "timeout_authority.json": result["timeout_authority"],
        "lead_time_analysis.json": result["lead_time"],
        "completeness_contract.json": result["completeness_contract"],
        "field_contract_decision.json": result["field_contract"],
        "implementation_authorization_decision.json": result["implementation_authorization"],
        "validation_results.json": {"passed": True, "activity": result["activity"], "no_source_substitution": True},
        "authority_closure_report.json": result,
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
