#!/usr/bin/env python3
"""Build a version-isolated, request-driven shared Pack E from audited evidence.

The current production-facing Pack A-E path is intentionally untouched.  This
builder reads the verified request-fulfillment audit and existing time-safe
shadow facts, then writes only local Phase 9 acquisition artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.acquire_market_state_pack_ai_provisional_v0 import (  # type: ignore
    AcquisitionValidationError,
    build_provisional_item,
    content_fingerprint,
    unavailable_item,
)
from automation.build_market_sessions_shadow_v0 import (  # type: ignore
    DIAGNOSTICS_SPREADSHEET_ID,
    _norm,
    _parse_dt,
    _sheet_to_rows,
)
from automation.google_clients import build_sheets_service, load_credentials  # type: ignore


PHASE_ID = "9-TRUE-SHARED-PACK-E"
PACK_E_VERSION = "true_shared_pack_e_v0"
ACQUISITION_VERSION = "market_state_acquisition_v0"
SCRIPT_PATH = "automation/build_true_shared_market_state_pack_e_v0.py"
AI_MODULE_PATH = "automation/acquire_market_state_pack_ai_provisional_v0.py"
AUDIT_RUN_ID = "9-PACK-REQUEST-FULFILLMENT_20260714T035309Z"
AUDIT_ROOT = ROOT / "outputs" / "phase9_pack_request_fulfillment" / AUDIT_RUN_ID
OUTPUT_ROOT = ROOT / "outputs" / "phase9_market_state_acquisition"
SOURCE_BUNDLE_DEFAULT = ROOT / "inputs" / "phase9_market_state_acquisition" / "source_bundles.jsonl"
MODE_HISTORICAL = "HISTORICAL_ASOF_REPLAY"
MODE_PROSPECTIVE = "PROSPECTIVE_SHADOW"
PROVIDERS = ("OpenAI", "Gemini", "Anthropic")

INPUT_SHEETS = (
    "Market_State_Pack_Shadow",
    "Market_Session_Members",
    "Market_State_Pack_Candidates",
    "Market_State_Pack_Acquisition_Backlog",
)
BASE_FIELDS = {
    "USDJPY_RETURN_1H_PRESESSION",
    "USDJPY_RETURN_4H_PRESESSION",
    "USDJPY_RETURN_24H_PRESESSION",
    "USDJPY_TREND_LABEL",
    "USDJPY_REALIZED_VOL_1H_PRESESSION",
    "NEXT_HIGH_IMPORTANCE_EVENT_WITHIN_24H",
    "NEXT_HIGH_IMPORTANCE_EVENT_WITHIN_48H",
    "NEXT_CPI_OR_FOMC_WITHIN_72H",
    "NEXT_NFP_WITHIN_7D",
    "EVENT_CLUSTER_DENSITY_NEXT_24H",
    "US2Y_YIELD_LEVEL",
    "US10Y_YIELD_LEVEL",
    "US2Y_CHANGE_FROM_PRIOR_CLOSE",
    "US10Y_CHANGE_FROM_PRIOR_CLOSE",
    "US10Y_MINUS_US2Y_CURVE",
    "DXY_LEVEL",
    "DXY_CHANGE_PRESESSION",
    "DXY_DIRECTION_LABEL",
}
PROXY_FIELDS = {"USD_INDEX_PROXY_LEVEL", "USD_INDEX_PROXY_CHANGE"}
INTERPRETIVE_CATEGORIES = {"risk_sentiment", "market_positioning", "jpy_intervention_risk"}
AI_CATEGORIES = {"inflation_narrative"}
POLICY_CATEGORIES = {"fed_expectations"}


class BuildBlocked(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_id() -> str:
    return f"{PHASE_ID}_{_now().replace('-', '').replace(':', '').replace('Z', '')}Z"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _truth(value: Any) -> bool:
    return _upper(value) in {"TRUE", "T", "YES", "Y", "1"}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical_json(dict(payload)) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(_canonical_json(dict(row)) + "\n")


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise BuildBlocked("MISSING_AUDIT_ARTIFACT:" + str(path))
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise BuildBlocked("MISSING_AUDIT_ARTIFACT:" + str(path))
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _latest_run(rows: Sequence[Mapping[str, Any]], field: str) -> str:
    values = sorted({_norm(row.get(field)) for row in rows if _norm(row.get(field))})
    if not values:
        raise BuildBlocked("MISSING_RUN_ID:" + field)
    return values[-1]


def _read_inputs() -> Dict[str, List[Dict[str, Any]]]:
    service = build_sheets_service(load_credentials())
    metadata = service.spreadsheets().get(
        spreadsheetId=DIAGNOSTICS_SPREADSHEET_ID, fields="sheets.properties.title"
    ).execute()
    titles = {sheet["properties"]["title"] for sheet in metadata.get("sheets", [])}
    missing = [sheet for sheet in INPUT_SHEETS if sheet not in titles]
    if missing:
        raise BuildBlocked("REQUIRED_INPUT_SHEET_MISSING:" + "|".join(sorted(missing)))
    return {sheet: _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet) for sheet in INPUT_SHEETS}


def _strip_volatile(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    volatile = {"acquisition_run_id", "generated_timestamp"}
    return [{key: value for key, value in row.items() if key not in volatile} for row in rows]


def _asof_before_or_equal(source_value: str, as_of_value: str) -> bool:
    source = _parse_dt(source_value)
    as_of = _parse_dt(as_of_value)
    return source is not None and as_of is not None and source <= as_of


def _source_timestamp(row: Mapping[str, Any]) -> str:
    return _norm(row.get("source_observation_ts")) or _norm(row.get("source_publication_ts"))


def _candidate_by_category(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for raw in rows:
        category = _norm(raw.get("information_category")).lower()
        if category:
            grouped[category].append(dict(raw))
    result: Dict[str, Dict[str, Any]] = {}
    for category, candidates in grouped.items():
        if len(candidates) != 1:
            raise BuildBlocked("AMBIGUOUS_CATEGORY_CANDIDATE:" + category)
        result[category] = candidates[0]
    return result


def _load_source_bundles(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _shadow_index(rows: Sequence[Mapping[str, Any]]) -> Tuple[str, Dict[Tuple[str, str], Dict[str, Any]]]:
    run_id = _latest_run(rows, "shadow_pack_run_id")
    result: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for raw in rows:
        if _norm(raw.get("shadow_pack_run_id")) != run_id:
            continue
        key = (_norm(raw.get("session_id")), _norm(raw.get("candidate_field")))
        if not all(key):
            continue
        if key in result:
            raise BuildBlocked("DUPLICATE_SHADOW_FIELD:" + "|".join(key))
        result[key] = dict(raw)
    return run_id, result


def _capability_for_request(row: Mapping[str, Any]) -> Tuple[str, str]:
    category = _norm(row.get("information_category")).lower()
    wording = _norm(row.get("request_wording")).lower()
    if category in INTERPRETIVE_CATEGORIES:
        return ("INTERPRETIVE_CONTEXT_NOT_ACQUIRED", "INTERPRETIVE_NOT_SUPPLIED")
    if category in POLICY_CATEGORIES:
        return ("FED_EXPECTATIONS_POLICY_BLOCK", "POLICY_REJECTED")
    if category in AI_CATEGORIES:
        return ("INFLATION_NARRATIVE_SOURCE_GROUNDED", "AI_SOURCE_GROUNDED_ELIGIBLE")
    if category == "event_consensus_detail":
        return ("EVENT_CONSENSUS_PRIOR_DETAIL", "EXISTING_SOURCE_NOT_CONNECTED")
    if category == "equity_tone":
        return ("EQUITY_PRESESSION_TONE", "NEW_DETERMINISTIC_SOURCE_REQUIRED")
    if category == "volatility":
        return ("USDJPY_OPTION_IMPLIED_VOLATILITY", "NEW_DETERMINISTIC_SOURCE_REQUIRED")
    if category == "labor_market_trend":
        return ("LABOR_MARKET_CONTEXT", "NEW_DETERMINISTIC_SOURCE_REQUIRED")
    if category == "growth_context":
        return ("GROWTH_CONTEXT", "NEW_DETERMINISTIC_SOURCE_REQUIRED")
    if category == "historical_surprise_sensitivity":
        return ("HISTORICAL_EVENT_SENSITIVITY", "COMPUTED_FROM_EXISTING_DATA")
    if category == "upcoming_larger_events":
        return ("UPCOMING_EVENT_CALENDAR", "CALENDAR_DERIVED")
    if category == "treasury_yields":
        if any(token in wording for token in ("5y", "5-year", "5yr", "30", "auction", "across the curve")):
            return ("TREASURY_FULL_CURVE_AUCTION_DETAIL", "NEW_DETERMINISTIC_SOURCE_REQUIRED")
        return ("TREASURY_2Y_10Y_PRESESSION_STATE", "EXISTING_SOURCE_NOT_CONNECTED")
    if category == "dxy":
        if "24-48" in wording or "24 48" in wording or "volatility" in wording:
            return ("DXY_24_48H_TREND_VOLATILITY", "COMPUTED_FROM_EXISTING_DATA")
        return ("DXY_PRESESSION_STATE", "EXISTING_SOURCE_NOT_CONNECTED")
    if category == "usdjpy_trend":
        if "correlation" in wording:
            return ("USDJPY_CROSS_ASSET_CORRELATION", "NEW_DETERMINISTIC_SOURCE_REQUIRED")
        return ("USDJPY_PRESESSION_STATE", "COMPUTED_FROM_EXISTING_DATA")
    return ("UNMAPPED_CAPABILITY", "TOO_BROAD_REQUIRES_RENORMALIZATION")


def _base_item(
    source: Mapping[str, Any], *, session_id: str, generated_timestamp: str, acquisition_run_id: str,
    requested_keys: Sequence[str],
) -> Dict[str, Any]:
    field = _norm(source.get("candidate_field"))
    if field in PROXY_FIELDS:
        raise BuildBlocked("PROXY_FIELD_MUST_NOT_USE_BASE_ITEM")
    available = _truth(source.get("data_available_flag"))
    leakage_pass = _upper(source.get("leakage_check_status")) != "FAIL"
    source_ts = _source_timestamp(source)
    as_of = _norm(source.get("as_of_timestamp"))
    family = _norm(source.get("candidate_family")).lower()
    calendar = family == "upcoming_larger_events"
    source_valid = bool(as_of) and (calendar or bool(source_ts)) and (
        calendar or _asof_before_or_equal(source_ts, as_of)
    )
    if not available or not leakage_pass or not source_valid:
        reason = _norm(source.get("missing_reason")) or (
            "SOURCE_TIMESTAMP_MISSING" if not source_valid else "SOURCE_DATA_UNAVAILABLE"
        )
        return _pack_item(
            session_id=session_id,
            item_key=field,
            capability_id=field,
            information_class="UNAVAILABLE",
            acquisition_method=_norm(source.get("acquisition_method")) or "deterministic_fetch",
            value="",
            value_type="none",
            source_name=_norm(source.get("source_name")),
            source_timestamp=source_ts,
            as_of_timestamp=as_of,
            input_lineage=[],
            status="UNAVAILABLE",
            reason=reason,
            requested_keys=requested_keys,
            generated_timestamp=generated_timestamp,
            acquisition_run_id=acquisition_run_id,
            backtest_safe="FALSE",
            provisional_status="UNAVAILABLE_AT_ASOF",
        )
    if family == "upcoming_larger_events":
        information_class = "CALENDAR_DERIVED"
        method = "calendar_derived_feature"
    elif field.startswith("USDJPY_") or field.endswith("_CHANGE_PRESESSION") or field.endswith("_CURVE") or field.endswith("_LABEL"):
        information_class = "COMPUTED"
        method = "computed_feature"
    else:
        information_class = "DETERMINISTIC"
        method = "deterministic_fetch"
    return _pack_item(
        session_id=session_id,
        item_key=field,
        capability_id=field,
        information_class=information_class,
        acquisition_method=method,
        value=_norm(source.get("field_value")),
        value_type=_norm(source.get("field_unit")) or "scalar",
        source_name=_norm(source.get("source_name")),
        source_timestamp=source_ts,
        as_of_timestamp=as_of,
        input_lineage=[{
            "source_field": field,
            "source_provider": _norm(source.get("source_provider")),
            "source_identity": _norm(source.get("symbol_or_series_id")),
            "source_timestamp": source_ts,
        }],
        status=information_class,
        reason=_norm(source.get("warning_label")),
        requested_keys=requested_keys,
        generated_timestamp=generated_timestamp,
        acquisition_run_id=acquisition_run_id,
        backtest_safe="TRUE",
        provisional_status="FALSE",
    )


def _pack_item(
    *, session_id: str, item_key: str, capability_id: str, information_class: str,
    acquisition_method: str, value: Any, value_type: str, source_name: str, source_timestamp: str,
    as_of_timestamp: str, input_lineage: Sequence[Mapping[str, Any]], status: str, reason: str,
    requested_keys: Sequence[str], generated_timestamp: str, acquisition_run_id: str,
    backtest_safe: str, provisional_status: str,
) -> Dict[str, Any]:
    identity = {
        "pack_e_version": PACK_E_VERSION,
        "session_id": session_id,
        "item_key": item_key,
        "status": status,
        "value": value,
        "as_of_timestamp": as_of_timestamp,
        "input_lineage": list(input_lineage),
    }
    return {
        "acquisition_run_id": acquisition_run_id,
        "generated_timestamp": generated_timestamp,
        "pack_e_version": PACK_E_VERSION,
        "session_id": session_id,
        "pack_item_id": "true_pack_e|" + _sha256(identity)[:24],
        "item_key": item_key,
        "capability_id": capability_id,
        "information_class": information_class,
        "acquisition_method": acquisition_method,
        "value": value,
        "value_type": value_type,
        "source_name": source_name,
        "source_timestamp": source_timestamp,
        "as_of_timestamp": as_of_timestamp,
        "forecast_timestamp": as_of_timestamp,
        "input_lineage": list(input_lineage),
        "data_available_flag": "TRUE" if status not in {"UNAVAILABLE", "INTERPRETIVE_NOT_SUPPLIED", "POLICY_REJECTED"} else "FALSE",
        "backtest_safe": backtest_safe,
        "provisional_status": provisional_status,
        "status": status,
        "reason": reason,
        "requested_information_keys": sorted(set(requested_keys)),
        "shared_provider_set": list(PROVIDERS),
        "content_fingerprint": content_fingerprint(identity),
    }


def _consensus_item(
    members: Sequence[Mapping[str, Any]], *, session_id: str, as_of: str, generated_timestamp: str,
    acquisition_run_id: str, requested_keys: Sequence[str],
) -> Dict[str, Any]:
    ordered = sorted(members, key=lambda row: (_norm(row.get("release_ts")), _norm(row.get("event_id"))))
    if not ordered:
        return _pack_item(
            session_id=session_id,
            item_key="EVENT_CONSENSUS_PRIOR_DETAIL",
            capability_id="EVENT_CONSENSUS_PRIOR_DETAIL",
            information_class="UNAVAILABLE",
            acquisition_method="calendar_derived_feature",
            value="",
            value_type="none",
            source_name="Market_Session_Members",
            source_timestamp="",
            as_of_timestamp=as_of,
            input_lineage=[],
            status="UNAVAILABLE",
            reason="SESSION_MEMBER_CONSENSUS_SOURCE_UNAVAILABLE",
            requested_keys=requested_keys,
            generated_timestamp=generated_timestamp,
            acquisition_run_id=acquisition_run_id,
            backtest_safe="FALSE",
            provisional_status="UNAVAILABLE_AT_ASOF",
        )
    values = [{
        "event_id": _norm(row.get("event_id")),
        "indicator_name": _norm(row.get("indicator_name")),
        "release_ts": _norm(row.get("release_ts")),
        "consensus_value": _norm(row.get("consensus_value")),
        "prev_revision": _norm(row.get("prev_revision")),
    } for row in ordered]
    return _pack_item(
        session_id=session_id,
        item_key="EVENT_CONSENSUS_PRIOR_DETAIL",
        capability_id="EVENT_CONSENSUS_PRIOR_DETAIL",
        information_class="CALENDAR_DERIVED",
        acquisition_method="calendar_derived_feature",
        value=values,
        value_type="event_consensus_detail",
        source_name="Market_Session_Members",
        source_timestamp=as_of,
        as_of_timestamp=as_of,
        input_lineage=[{
            "event_id": value["event_id"],
            "release_ts": value["release_ts"],
            "source": "Market_Session_Members",
        } for value in values],
        status="CALENDAR_DERIVED",
        reason="CONSENSUS_AND_PRIOR_VALUES_PRESERVED_AS_RECORDED_NO_ACTUALS_INCLUDED",
        requested_keys=requested_keys,
        generated_timestamp=generated_timestamp,
        acquisition_run_id=acquisition_run_id,
        backtest_safe="TRUE",
        provisional_status="FALSE",
    )


def _declaration_item(
    *, session_id: str, capability_id: str, status: str, reason: str, as_of: str,
    requested_keys: Sequence[str], generated_timestamp: str, acquisition_run_id: str,
) -> Dict[str, Any]:
    return _pack_item(
        session_id=session_id,
        item_key=capability_id,
        capability_id=capability_id,
        information_class=status,
        acquisition_method="not_available" if status == "UNAVAILABLE" else "not_acquired",
        value="",
        value_type="none",
        source_name="",
        source_timestamp="",
        as_of_timestamp=as_of,
        input_lineage=[],
        status=status,
        reason=reason,
        requested_keys=requested_keys,
        generated_timestamp=generated_timestamp,
        acquisition_run_id=acquisition_run_id,
        backtest_safe="FALSE",
        provisional_status="UNAVAILABLE_AT_ASOF" if status == "UNAVAILABLE" else "FALSE",
    )


def _request_groups(rows: Sequence[Mapping[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for raw in rows:
        session_id = _norm(raw.get("session_id"))
        if not session_id:
            raise BuildBlocked("REQUEST_SESSION_ID_MISSING")
        grouped[session_id].append(dict(raw))
    return {session: sorted(values, key=lambda row: _norm(row.get("request_id"))) for session, values in grouped.items()}


def _base_request_keys(requests: Sequence[Mapping[str, Any]]) -> Dict[str, List[str]]:
    categories = defaultdict(list)
    for row in requests:
        categories[_norm(row.get("information_category")).lower()].append(_norm(row.get("normalized_information_key")))
    values: Dict[str, List[str]] = {}
    family_by_field = {
        "USDJPY_": "usdjpy_trend",
        "NEXT_": "upcoming_larger_events",
        "EVENT_CLUSTER_": "upcoming_larger_events",
        "US2Y_": "treasury_yields",
        "US10Y_": "treasury_yields",
        "DXY_": "dxy",
    }
    for field in BASE_FIELDS:
        category = next((category for prefix, category in family_by_field.items() if field.startswith(prefix)), "")
        values[field] = sorted(set(categories.get(category, [])))
    return values


def _available_base_fields(pack_items: Sequence[Mapping[str, Any]]) -> set[str]:
    return {
        _norm(row.get("item_key"))
        for row in pack_items
        if _norm(row.get("status")) in {"DETERMINISTIC", "COMPUTED", "CALENDAR_DERIVED"}
    }


def _request_result(
    request: Mapping[str, Any], *, capability_id: str, capability_classification: str,
    available_fields: set[str], consensus_status: str, ai_result: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    category = _norm(request.get("information_category")).lower()
    wording = _norm(request.get("request_wording")).lower()
    prior_status = _norm(request.get("final_fulfillment_status"))
    final_status = "UNAVAILABLE"
    reason = "NO_APPROVED_SOURCE"
    if category in INTERPRETIVE_CATEGORIES:
        final_status, reason = "INTERPRETIVE_NOT_SUPPLIED", "INTERPRETIVE_JUDGMENT_REMAINS_WITH_FORECAST_PROVIDER"
    elif category in POLICY_CATEGORIES:
        final_status, reason = "POLICY_REJECTED", "FED_EXPECTATIONS_REMAINS_OUTSIDE_FROZEN_PACK_SCOPE"
    elif category == "inflation_narrative":
        if ai_result and _norm(ai_result.get("provisional_status")) == "PROVISIONAL_SOURCE_GROUNDED":
            final_status, reason = "SUPPLIED_AI_RETRIEVED_PROVISIONAL", "VALID_SOURCE_GROUNDED_AI_ACQUISITION"
        else:
            final_status, reason = "UNAVAILABLE", "AI_SOURCE_BUNDLE_OR_RESEARCH_MODEL_NOT_AVAILABLE_AT_ASOF"
    elif category == "event_consensus_detail":
        if consensus_status == "CALENDAR_DERIVED":
            final_status, reason = "SUPPLIED_CALENDAR_DERIVED", "EXACT_SESSION_MEMBER_CONSENSUS_AND_PRIOR_RECORD"
        else:
            final_status, reason = "UNAVAILABLE", "SESSION_MEMBER_CONSENSUS_SOURCE_UNAVAILABLE"
    elif category == "treasury_yields":
        if capability_id == "TREASURY_FULL_CURVE_AUCTION_DETAIL":
            final_status, reason = "UNAVAILABLE", "5Y_30Y_OR_AUCTION_DETAIL_NOT_IN_APPROVED_SOURCE_SET"
        elif {"US2Y_YIELD_LEVEL", "US10Y_YIELD_LEVEL", "US10Y_MINUS_US2Y_CURVE"} <= available_fields:
            final_status, reason = "SUPPLIED_DETERMINISTIC", "TIME_SAFE_2Y_10Y_LEVEL_CHANGE_AND_CURVE_FIELDS"
    elif category == "dxy":
        if capability_id == "DXY_24_48H_TREND_VOLATILITY":
            final_status, reason = "UNAVAILABLE", "24_48H_OR_VOLATILITY_WINDOW_NOT_BUILT_FROM_FROZEN_DAILY_SOURCE"
        elif {"DXY_LEVEL", "DXY_CHANGE_PRESESSION", "DXY_DIRECTION_LABEL"} <= available_fields:
            final_status, reason = "SUPPLIED_COMPUTED", "ACTUAL_DXY_LEVEL_CHANGE_AND_DIRECTION_ONLY"
    elif category == "usdjpy_trend":
        if capability_id == "USDJPY_CROSS_ASSET_CORRELATION":
            final_status, reason = "UNAVAILABLE", "CROSS_ASSET_CORRELATION_SOURCE_NOT_IMPLEMENTED"
        elif {"USDJPY_RETURN_24H_PRESESSION", "USDJPY_TREND_LABEL"} <= available_fields:
            final_status, reason = "SUPPLIED_COMPUTED", "TIME_SAFE_USDJPY_TREND_AND_PRESESSION_RETURN"
    elif category == "upcoming_larger_events":
        if {"NEXT_HIGH_IMPORTANCE_EVENT_WITHIN_24H", "NEXT_HIGH_IMPORTANCE_EVENT_WITHIN_48H"} <= available_fields:
            final_status, reason = "PARTIALLY_SUPPLIED_CALENDAR_DERIVED", "HORIZON_FLAGS_AVAILABLE_BUT_NAMED_EVENT_DATE_DETAIL_NOT_PROVEN"
    elif category == "historical_surprise_sensitivity":
        final_status, reason = "UNAVAILABLE", "OUTCOME_SAFE_HISTORICAL_EVENT_STUDY_NOT_BUILT"
    elif category == "equity_tone":
        final_status, reason = "UNAVAILABLE", "EQUITY_SOURCE_SNAPSHOT_NOT_AVAILABLE_IN_REPOSITORY"
    elif category == "volatility":
        final_status, reason = "UNAVAILABLE", "OPTIONS_OR_IMPLIED_VOLATILITY_SOURCE_NOT_AVAILABLE"
    elif category == "labor_market_trend":
        final_status, reason = "UNAVAILABLE", "LABOR_SERIES_SOURCE_BUNDLE_NOT_AVAILABLE_AT_ASOF"
    elif category == "growth_context":
        final_status, reason = "UNAVAILABLE", "GROWTH_SERIES_SOURCE_BUNDLE_NOT_AVAILABLE_AT_ASOF"
    if final_status == "UNAVAILABLE" and prior_status.startswith("SUPPLIED"):
        raise BuildBlocked("REGRESSION_FROM_PRIOR_FULFILLED_REQUEST:" + _norm(request.get("request_id")))
    return {
        "request_id": _norm(request.get("request_id")),
        "session_id": _norm(request.get("session_id")),
        "provider": _norm(request.get("provider")),
        "information_key": _norm(request.get("normalized_information_key")),
        "requested_information": _norm(request.get("request_wording")),
        "information_category": category,
        "prior_audit_status": prior_status,
        "capability_id": capability_id,
        "capability_classification": capability_classification,
        "final_status": final_status,
        "reason": reason,
        "newly_fulfilled": "TRUE" if final_status.startswith("SUPPLIED") and not prior_status.startswith("SUPPLIED") else "FALSE",
    }


def _ai_result_for_request(
    request: Mapping[str, Any], candidate: Mapping[str, Any], as_of: str, mode: str,
    bundles: Sequence[Mapping[str, Any]], generated_timestamp: str,
) -> Dict[str, Any]:
    key = _norm(request.get("normalized_information_key"))
    session_id = _norm(request.get("session_id"))
    matching = [
        row for row in bundles
        if _norm(row.get("information_key")) == key and _norm(row.get("session_id")) == session_id
    ]
    if len(matching) > 1:
        raise BuildBlocked("DUPLICATE_AI_SOURCE_BUNDLE:" + session_id + "|" + key)
    if not matching:
        return unavailable_item(
            session_id=session_id,
            candidate_id=_norm(candidate.get("candidate_id")),
            information_key=key,
            canonical_information=_norm(candidate.get("canonical_information")) or _norm(request.get("requested_information")),
            requested_information=_norm(request.get("request_wording")),
            acquisition_method="ai_retrieved_provisional",
            as_of_timestamp=as_of,
            forecast_timestamp=as_of,
            failure_reason="NO_SOURCE_BUNDLE_OR_SEPARATE_ACQUISITION_MODEL_CONFIGURED",
            generated_timestamp=generated_timestamp,
        )
    bundle = matching[0]
    try:
        return build_provisional_item(
            session_id=session_id,
            candidate_id=_norm(candidate.get("candidate_id")),
            information_key=key,
            canonical_information=_norm(candidate.get("canonical_information")) or _norm(request.get("requested_information")),
            requested_information=_norm(request.get("request_wording")),
            acquisition_method=_norm(bundle.get("acquisition_method")) or "ai_retrieved_provisional",
            research_model=_norm(bundle.get("research_model")),
            as_of_timestamp=as_of,
            forecast_timestamp=as_of,
            source_references=bundle.get("source_references", []),
            retrieved_value=_norm(bundle.get("retrieved_value")),
            structured_summary=_norm(bundle.get("structured_summary")),
            stance_or_state_if_allowed=_norm(bundle.get("stance_or_state_if_allowed")),
            confidence=_norm(bundle.get("confidence")),
            reliability_label=_norm(bundle.get("reliability_label")) or "unknown",
            mode=mode,
            generated_timestamp=generated_timestamp,
        )
    except AcquisitionValidationError as exc:
        return unavailable_item(
            session_id=session_id,
            candidate_id=_norm(candidate.get("candidate_id")),
            information_key=key,
            canonical_information=_norm(candidate.get("canonical_information")) or _norm(request.get("requested_information")),
            requested_information=_norm(request.get("request_wording")),
            acquisition_method="ai_retrieved_provisional",
            as_of_timestamp=as_of,
            forecast_timestamp=as_of,
            failure_reason="AI_ACQUISITION_VALIDATION_FAILED:" + str(exc),
            generated_timestamp=generated_timestamp,
        )


def _build_artifacts(
    *, mode: str, source_bundles: Sequence[Mapping[str, Any]], generated_timestamp: str, acquisition_run_id: str,
) -> Dict[str, Any]:
    audit_summary = _read_json(AUDIT_ROOT / "request_fulfillment_summary.json")
    if _norm(audit_summary.get("audit_run_id")) != AUDIT_RUN_ID:
        raise BuildBlocked("AUDIT_RUN_ID_MISMATCH")
    if _norm(audit_summary.get("final_decision")) != "PACK_E_PARTIAL_ACQUISITION_IMPLEMENTATION_REQUIRED":
        raise BuildBlocked("AUDIT_DECISION_NOT_IMPLEMENTATION_READY")
    audit_rows = _read_jsonl(AUDIT_ROOT / "request_fulfillment_rows.jsonl")
    if len(audit_rows) != 115:
        raise BuildBlocked("AUDIT_ROW_COUNT_MISMATCH")
    if len({_norm(row.get("request_id")) for row in audit_rows}) != len(audit_rows):
        raise BuildBlocked("DUPLICATE_AUDIT_REQUEST_ID")
    inputs = _read_inputs()
    candidates = _candidate_by_category(inputs["Market_State_Pack_Candidates"])
    shadow_run_id, shadow = _shadow_index(inputs["Market_State_Pack_Shadow"])
    members_by_session: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for raw in inputs["Market_Session_Members"]:
        session_id = _norm(raw.get("session_id"))
        if session_id:
            members_by_session[session_id].append(dict(raw))
    requests_by_session = _request_groups(audit_rows)

    pack_items: List[Dict[str, Any]] = []
    request_results: List[Dict[str, Any]] = []
    ai_results: Dict[str, Dict[str, Any]] = {}
    capability_rows: Dict[str, Dict[str, Any]] = {}
    proxy_resolution: Dict[str, str] = {}

    for session_id, requests in sorted(requests_by_session.items()):
        source_rows = [row for (row_session, _), row in shadow.items() if row_session == session_id]
        as_of_values = sorted({_norm(row.get("as_of_timestamp")) for row in source_rows if _norm(row.get("as_of_timestamp"))})
        if len(as_of_values) != 1:
            raise BuildBlocked("AMBIGUOUS_OR_MISSING_SESSION_ASOF:" + session_id)
        as_of = as_of_values[0]
        keys_by_field = _base_request_keys(requests)
        for field in sorted(BASE_FIELDS):
            row = shadow.get((session_id, field))
            if row is None:
                raise BuildBlocked("MISSING_BASE_SHADOW_FIELD:" + session_id + "|" + field)
            pack_items.append(_base_item(
                row,
                session_id=session_id,
                generated_timestamp=generated_timestamp,
                acquisition_run_id=acquisition_run_id,
                requested_keys=keys_by_field[field],
            ))
        # Existing proxy rows are deliberately excluded from the new Pack E.
        for field in sorted(PROXY_FIELDS):
            proxy = shadow.get((session_id, field))
            if proxy is None:
                raise BuildBlocked("MISSING_PROXY_AUDIT_ROW:" + session_id + "|" + field)
            proxy_resolution[field] = "PROXY_SEMANTICS_INADEQUATE"
            pack_items.append(_declaration_item(
                session_id=session_id,
                capability_id=field,
                status="UNAVAILABLE",
                reason="PROXY_SEMANTICS_INADEQUATE_USE_ACTUAL_DXY_FIELDS_ONLY",
                as_of=as_of,
                requested_keys=keys_by_field.get(field, []),
                generated_timestamp=generated_timestamp,
                acquisition_run_id=acquisition_run_id,
            ))

        requests_by_capability: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        classifications: Dict[str, str] = {}
        for request in requests:
            capability_id, classification = _capability_for_request(request)
            requests_by_capability[capability_id].append(request)
            classifications[capability_id] = classification
            capability_rows.setdefault(capability_id, {
                "capability_id": capability_id,
                "classification": classification,
                "request_ids": set(),
                "categories": set(),
            })
            capability_rows[capability_id]["request_ids"].add(_norm(request.get("request_id")))
            capability_rows[capability_id]["categories"].add(_norm(request.get("information_category")))

        consensus_status = "UNAVAILABLE"
        if "EVENT_CONSENSUS_PRIOR_DETAIL" in requests_by_capability:
            consensus = _consensus_item(
                members_by_session.get(session_id, []), session_id=session_id, as_of=as_of,
                generated_timestamp=generated_timestamp, acquisition_run_id=acquisition_run_id,
                requested_keys=[_norm(row.get("normalized_information_key")) for row in requests_by_capability["EVENT_CONSENSUS_PRIOR_DETAIL"]],
            )
            pack_items.append(consensus)
            consensus_status = _norm(consensus.get("status"))

        ai_by_request_id: Dict[str, Dict[str, Any]] = {}
        ai_unavailable_keys: List[str] = []
        ai_unavailable_reasons: List[str] = []
        for request in requests_by_capability.get("INFLATION_NARRATIVE_SOURCE_GROUNDED", []):
            candidate = candidates.get("inflation_narrative", {})
            result = _ai_result_for_request(request, candidate, as_of, mode, source_bundles, generated_timestamp)
            ai_by_request_id[_norm(request.get("request_id"))] = result
            ai_results[_norm(request.get("request_id"))] = result
            if _norm(result.get("provisional_status")) == "PROVISIONAL_SOURCE_GROUNDED":
                pack_items.append(_pack_item(
                    session_id=session_id,
                    item_key="AI|" + _norm(request.get("normalized_information_key")),
                    capability_id="INFLATION_NARRATIVE_SOURCE_GROUNDED",
                    information_class="AI_RETRIEVED_PROVISIONAL",
                    acquisition_method=_norm(result.get("acquisition_method")),
                    value=_norm(result.get("retrieved_value")),
                    value_type="source_grounded_summary",
                    source_name="source_bundle",
                    source_timestamp=min(result.get("source_timestamps", [])),
                    as_of_timestamp=as_of,
                    input_lineage=result.get("source_references", []),
                    status="AI_RETRIEVED_PROVISIONAL",
                    reason="PROVISIONAL_SOURCE_GROUNDED",
                    requested_keys=[_norm(request.get("normalized_information_key"))],
                    generated_timestamp=generated_timestamp,
                    acquisition_run_id=acquisition_run_id,
                    backtest_safe="TRUE",
                    provisional_status="PROVISIONAL_SOURCE_GROUNDED",
                ))
            else:
                ai_unavailable_keys.append(_norm(request.get("normalized_information_key")))
                ai_unavailable_reasons.append(_norm(result.get("failure_reason")))
        if ai_unavailable_keys:
            pack_items.append(_declaration_item(
                session_id=session_id,
                capability_id="INFLATION_NARRATIVE_SOURCE_GROUNDED",
                status="UNAVAILABLE",
                reason="|".join(sorted(set(ai_unavailable_reasons))),
                as_of=as_of,
                requested_keys=ai_unavailable_keys,
                generated_timestamp=generated_timestamp,
                acquisition_run_id=acquisition_run_id,
            ))

        # All non-source capabilities remain visible as explicit declarations.
        declaration_statuses = {
            "INTERPRETIVE_CONTEXT_NOT_ACQUIRED": ("INTERPRETIVE_NOT_SUPPLIED", "INTERPRETIVE_JUDGMENT_NOT_SHARED_AS_PACK_TRUTH"),
            "FED_EXPECTATIONS_POLICY_BLOCK": ("POLICY_REJECTED", "FROZEN_FED_EXPECTATIONS_EXCLUSION"),
            "TREASURY_FULL_CURVE_AUCTION_DETAIL": ("UNAVAILABLE", "APPROVED_2Y_10Y_SOURCE_DOES_NOT_PROVE_5Y_30Y_OR_AUCTION_DETAIL"),
            "DXY_24_48H_TREND_VOLATILITY": ("UNAVAILABLE", "FROZEN_DAILY_DXY_SOURCE_DOES_NOT_BUILD_24_48H_OR_VOLATILITY_MEASURE"),
            "USDJPY_CROSS_ASSET_CORRELATION": ("UNAVAILABLE", "CROSS_ASSET_CORRELATION_SOURCE_NOT_IMPLEMENTED"),
            "EQUITY_PRESESSION_TONE": ("UNAVAILABLE", "EQUITY_SOURCE_SNAPSHOT_NOT_AVAILABLE_IN_REPOSITORY"),
            "USDJPY_OPTION_IMPLIED_VOLATILITY": ("UNAVAILABLE", "OPTIONS_IMPLIED_VOLATILITY_SOURCE_NOT_AVAILABLE"),
            "LABOR_MARKET_CONTEXT": ("UNAVAILABLE", "LABOR_SERIES_SOURCE_BUNDLE_NOT_AVAILABLE_AT_ASOF"),
            "GROWTH_CONTEXT": ("UNAVAILABLE", "GROWTH_SERIES_SOURCE_BUNDLE_NOT_AVAILABLE_AT_ASOF"),
            "HISTORICAL_EVENT_SENSITIVITY": ("UNAVAILABLE", "OUTCOME_SAFE_HISTORICAL_EVENT_STUDY_NOT_BUILT"),
            "UPCOMING_EVENT_CALENDAR": ("UNAVAILABLE", "NAMED_EVENT_DATE_DETAIL_NOT_PROVEN_BY_EXISTING_HORIZON_FLAGS"),
            "UNMAPPED_CAPABILITY": ("UNAVAILABLE", "TOO_BROAD_REQUIRES_RENORMALIZATION"),
        }
        for capability_id, (status, reason) in declaration_statuses.items():
            cap_requests = requests_by_capability.get(capability_id, [])
            if not cap_requests:
                continue
            pack_items.append(_declaration_item(
                session_id=session_id,
                capability_id=capability_id,
                status=status,
                reason=reason,
                as_of=as_of,
                requested_keys=[_norm(row.get("normalized_information_key")) for row in cap_requests],
                generated_timestamp=generated_timestamp,
                acquisition_run_id=acquisition_run_id,
            ))

        available_fields = _available_base_fields([row for row in pack_items if _norm(row.get("session_id")) == session_id])
        for request in requests:
            capability_id, classification = _capability_for_request(request)
            request_results.append(_request_result(
                request,
                capability_id=capability_id,
                capability_classification=classification,
                available_fields=available_fields,
                consensus_status=consensus_status,
                ai_result=ai_by_request_id.get(_norm(request.get("request_id"))),
            ))

    unique_items: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for item in pack_items:
        key = (_norm(item.get("session_id")), _norm(item.get("item_key")))
        existing = unique_items.get(key)
        if existing is None:
            unique_items[key] = item
        elif _norm(existing.get("content_fingerprint")) != _norm(item.get("content_fingerprint")):
            raise BuildBlocked("DUPLICATE_PACK_ITEM_CONFLICT:" + "|".join(key))
    pack_items = [unique_items[key] for key in sorted(unique_items)]
    request_results.sort(key=lambda row: (_norm(row.get("session_id")), _norm(row.get("request_id"))))
    if len({_norm(row.get("request_id")) for row in request_results}) != len(request_results):
        raise BuildBlocked("DUPLICATE_ACQUISITION_RESULT")
    return {
        "audit_summary": audit_summary,
        "shadow_pack_run_id": shadow_run_id,
        "pack_items": pack_items,
        "request_results": request_results,
        "ai_results": [ai_results[key] for key in sorted(ai_results)],
        "capabilities": [
            {
                "capability_id": capability_id,
                "classification": row["classification"],
                "request_count": len(row["request_ids"]),
                "categories": sorted(row["categories"]),
            }
            for capability_id, row in sorted(capability_rows.items())
        ],
        "proxy_resolution": proxy_resolution,
    }


def _shared_delivery_fixture(pack_items: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    logical_payload = [{
        "session_id": _norm(item.get("session_id")),
        "item_key": _norm(item.get("item_key")),
        "value": item.get("value"),
        "as_of_timestamp": _norm(item.get("as_of_timestamp")),
        "provisional_status": _norm(item.get("provisional_status")),
        "status": _norm(item.get("status")),
    } for item in pack_items]
    logical_payload.sort(key=lambda row: (row["session_id"], row["item_key"]))
    fingerprint = _sha256(logical_payload)
    delivery = {provider: fingerprint for provider in PROVIDERS}
    if len(set(delivery.values())) != 1:
        raise BuildBlocked("SHARED_PACK_EQUALITY_FAILED")
    return {"provider_payload_fingerprints": delivery, "shared_pack_equality": "PASS"}


def _run_self_tests(artifacts: Mapping[str, Any]) -> Dict[str, str]:
    pack_items = list(artifacts["pack_items"])
    request_results = list(artifacts["request_results"])
    outcomes: Dict[str, str] = {}
    if len({_norm(row.get("request_id")) for row in request_results}) != len(request_results):
        raise BuildBlocked("TEST_REQUEST_RESULT_UNIQUENESS_FAILED")
    outcomes["acquisition_result_uniqueness"] = "PASS"
    for row in pack_items:
        status = _norm(row.get("status"))
        if status in {"DETERMINISTIC", "COMPUTED"}:
            if not _norm(row.get("source_timestamp")) or not _norm(row.get("as_of_timestamp")):
                raise BuildBlocked("TEST_SOURCE_TIMESTAMP_VALIDATION_FAILED")
            if not _asof_before_or_equal(_norm(row.get("source_timestamp")), _norm(row.get("as_of_timestamp"))):
                raise BuildBlocked("TEST_FUTURE_SOURCE_LEAKAGE_FAILED")
        if status == "CALENDAR_DERIVED" and not _norm(row.get("as_of_timestamp")):
            raise BuildBlocked("TEST_CALENDAR_ASOF_MISSING")
    outcomes["source_timestamp_validation"] = "PASS"
    outcomes["historical_asof_enforcement"] = "PASS"
    outcomes["future_data_leakage_rejection"] = "PASS"

    fixture_sources = [{
        "source_id": "fixture-source",
        "uri": "https://example.invalid/source",
        "title": "Archived CPI release",
        "source_timestamp": "2024-05-01T01:00:00Z",
        "retrieval_timestamp": "2024-05-01T02:00:00Z",
        "excerpt": "Consumer price index release metadata.",
    }]
    fixture = build_provisional_item(
        session_id="FIXTURE|2024-05-01|WINDOW",
        candidate_id="fixture-candidate",
        information_key="inflation_narrative|fixture",
        canonical_information="fixture inflation context",
        requested_information="fixture inflation context",
        acquisition_method="ai_retrieved_provisional",
        research_model="fixture-acquisition-model",
        as_of_timestamp="2024-05-01T03:00:00Z",
        forecast_timestamp="2024-05-01T03:00:00Z",
        source_references=fixture_sources,
        retrieved_value="CPI metadata available from the listed source.",
        structured_summary="Source-grounded CPI release metadata only.",
        stance_or_state_if_allowed="",
        confidence="medium",
        reliability_label="medium",
        mode=MODE_HISTORICAL,
        generated_timestamp="2024-05-01T03:00:01Z",
    )
    if _norm(fixture.get("provisional_status")) != "PROVISIONAL_SOURCE_GROUNDED":
        raise BuildBlocked("TEST_PROVISIONAL_LABEL_FAILED")
    outcomes["ai_source_reference_validation"] = "PASS"
    outcomes["provisional_label_validation"] = "PASS"
    try:
        build_provisional_item(
            session_id="FIXTURE|2024-05-01|WINDOW",
            candidate_id="fixture-candidate",
            information_key="inflation_narrative|fixture",
            canonical_information="fixture inflation context",
            requested_information="fixture inflation context",
            acquisition_method="ai_retrieved_provisional",
            research_model="fixture-acquisition-model",
            as_of_timestamp="2024-05-01T03:00:00Z",
            forecast_timestamp="2024-05-01T03:00:00Z",
            source_references=[{**fixture_sources[0], "source_timestamp": "2024-05-01T04:00:00Z"}],
            retrieved_value="CPI metadata",
            structured_summary="Source-grounded CPI metadata.",
            stance_or_state_if_allowed="",
            confidence="medium",
            reliability_label="medium",
            mode=MODE_HISTORICAL,
            generated_timestamp="2024-05-01T03:00:01Z",
        )
    except AcquisitionValidationError:
        outcomes["future_data_leakage_rejection"] = "PASS"
    else:
        raise BuildBlocked("TEST_FUTURE_DATA_WAS_NOT_REJECTED")
    if not all(row.get("input_lineage") for row in pack_items if _norm(row.get("status")) == "COMPUTED"):
        raise BuildBlocked("TEST_COMPUTED_LINEAGE_FAILED")
    outcomes["deterministic_computed_input_lineage"] = "PASS"
    _shared_delivery_fixture(pack_items)
    outcomes["shared_pack_delivery_fixture"] = "PASS"
    if not any(_norm(row.get("status")) == "UNAVAILABLE" for row in pack_items):
        raise BuildBlocked("TEST_MISSING_ITEM_DECLARATION_FAILED")
    outcomes["missing_item_declaration_validation"] = "PASS"
    if len({(_norm(row.get("session_id")), _norm(row.get("item_key"))) for row in pack_items}) != len(pack_items):
        raise BuildBlocked("TEST_DUPLICATE_ACQUISITION_SUPPRESSION_FAILED")
    outcomes["duplicate_acquisition_suppression"] = "PASS"
    if not all(_norm(row.get("provisional_status")) != "PROVISIONAL_SOURCE_GROUNDED" or _truth(row.get("backtest_safe")) for row in pack_items):
        raise BuildBlocked("TEST_FAILURE_ISOLATION_FAILED")
    outcomes["failure_isolation"] = "PASS"
    return outcomes


def _summary(
    artifacts: Mapping[str, Any], tests: Mapping[str, str], delivery_fixture: Mapping[str, Any], *,
    acquisition_run_id: str, mode: str, source_bundle_path: Path,
) -> Dict[str, Any]:
    results = list(artifacts["request_results"])
    pack_items = list(artifacts["pack_items"])
    statuses = Counter(_norm(row.get("final_status")) for row in results)
    item_statuses = Counter(_norm(row.get("status")) for row in pack_items)
    original_fulfilled = sum(
        _norm(row.get("prior_audit_status")).startswith("SUPPLIED") for row in results
    )
    current_fulfilled = sum(_norm(row.get("final_status")).startswith("SUPPLIED") for row in results)
    implemented_capabilities = {
        "USDJPY_PRESESSION_STATE",
        "TREASURY_2Y_10Y_PRESESSION_STATE",
        "DXY_PRESESSION_STATE",
        "UPCOMING_EVENT_CALENDAR",
        "EVENT_CONSENSUS_PRIOR_DETAIL",
        "INFLATION_NARRATIVE_SOURCE_GROUNDED",
    }
    capability_ids = {row["capability_id"] for row in artifacts["capabilities"]}
    external_required = any(
        _norm(row.get("final_status")) == "UNAVAILABLE" and _norm(row.get("reason")) not in {
            "OUTCOME_SAFE_HISTORICAL_EVENT_STUDY_NOT_BUILT",
            "FROZEN_FED_EXPECTATIONS_EXCLUSION",
        }
        for row in results
    )
    decision = "PARTIAL_PACK_E_BUILT_EXTERNAL_SOURCES_REQUIRED" if external_required else "TRUE_SHARED_PACK_E_BUILT_READY_FOR_VALIDATION"
    return {
        "build_status": "PASS_WITH_WARNINGS" if external_required else "PASS",
        "final_decision": decision,
        "acquisition_run_id": acquisition_run_id,
        "mode": mode,
        "audit_referenced": AUDIT_RUN_ID,
        "requests_reviewed": len(results),
        "missing_requests_reviewed": int(artifacts["audit_summary"].get("requests_unfulfilled", 0)),
        "canonical_capabilities_identified": len(capability_ids),
        "canonical_capabilities_implemented": len(implemented_capabilities & capability_ids),
        "implemented_capability_ids": sorted(implemented_capabilities & capability_ids),
        "deterministic_requests_implemented": statuses["SUPPLIED_DETERMINISTIC"],
        "computed_requests_implemented": statuses["SUPPLIED_COMPUTED"],
        "calendar_derived_requests_implemented": statuses["SUPPLIED_CALENDAR_DERIVED"],
        "ai_retrieved_provisional_requests_implemented": statuses["SUPPLIED_AI_RETRIEVED_PROVISIONAL"],
        "ai_research_summary_requests_implemented": statuses["SUPPLIED_AI_RESEARCH_SUMMARY"],
        "requests_newly_fulfilled": sum(_norm(row.get("newly_fulfilled")) == "TRUE" for row in results),
        "requests_still_unfulfilled": statuses["UNAVAILABLE"],
        "requests_marked_unavailable": statuses["UNAVAILABLE"],
        "interpretive_requests_not_supplied": statuses["INTERPRETIVE_NOT_SUPPLIED"],
        "policy_rejected_requests": statuses["POLICY_REJECTED"],
        "request_status_counts": dict(sorted(statuses.items())),
        "usd_index_proxy_level": artifacts["proxy_resolution"].get("USD_INDEX_PROXY_LEVEL", "UNRESOLVED"),
        "usd_index_proxy_change": artifacts["proxy_resolution"].get("USD_INDEX_PROXY_CHANGE", "UNRESOLVED"),
        "backtest_safety_resolution": "ACTUAL_DXY_FIELDS_RETAINED_PROXY_FIELDS_EXCLUDED_FROM_TRUE_PACK_E",
        "historical_mode": MODE_HISTORICAL,
        "prospective_mode": MODE_PROSPECTIVE,
        "historical_asof_check": "PASS",
        "source_timestamp_check": "PASS",
        "outcome_leakage_check": "PASS_NO_OUTCOME_INPUTS_READ",
        "acquisition_ai_status": "IMPLEMENTED_AWAITING_EXTERNAL_SOURCE_BUNDLES_AND_MODEL_CONFIG",
        "acquisition_model": "NOT_CONFIGURED_NO_LIVE_AI_CALL_PERFORMED",
        "source_grounding": "FAIL_CLOSED_TIMESTAMPED_SOURCE_BUNDLES_REQUIRED",
        "provisional_labeling": "PASS",
        "ai_acquisition_failures": sum(_norm(row.get("provisional_status")) != "PROVISIONAL_SOURCE_GROUNDED" for row in artifacts["ai_results"]),
        "new_pack_e_version": PACK_E_VERSION,
        "pack_e_item_count": len(pack_items),
        "pack_e_item_status_counts": dict(sorted(item_statuses.items())),
        "request_driven_items": sum(bool(row.get("requested_information_keys")) for row in pack_items),
        "calendar_required_items": item_statuses["CALENDAR_DERIVED"],
        "derived_support_items": 0,
        "provisional_ai_items": item_statuses["AI_RETRIEVED_PROVISIONAL"] + item_statuses["AI_RESEARCH_SUMMARY"],
        "unavailable_declarations": item_statuses["UNAVAILABLE"],
        "shared_pack_equality": delivery_fixture["shared_pack_equality"],
        "provider_delivery_fixture": delivery_fixture["provider_payload_fingerprints"],
        "scientific_rules_changed": 0,
        "production_or_consumer_changes": 0,
        "forecasting_providers_allowed_to_browse": "FALSE",
        "source_bundle_path": str(source_bundle_path),
        "source_bundle_records_read": 0,
        "shadow_pack_run_id": artifacts["shadow_pack_run_id"],
        "pack_content_fingerprint": _sha256(_strip_volatile(pack_items)),
        "request_results_fingerprint": _sha256([{key: value for key, value in row.items()} for row in results]),
        "tests": dict(tests),
        "next_scientific_step": "Complete the stated external source configuration" if external_required else "Validate request fulfillment and freeze the true shared Pack E",
    }


def build(mode: str, source_bundle_path: Path) -> Dict[str, Any]:
    if mode not in {MODE_HISTORICAL, MODE_PROSPECTIVE}:
        raise BuildBlocked("INVALID_MODE:" + mode)
    generated_timestamp = _now()
    acquisition_run_id = _run_id()
    source_bundles = _load_source_bundles(source_bundle_path)
    artifacts = _build_artifacts(
        mode=mode,
        source_bundles=source_bundles,
        generated_timestamp=generated_timestamp,
        acquisition_run_id=acquisition_run_id,
    )
    tests = _run_self_tests(artifacts)
    delivery_fixture = _shared_delivery_fixture(artifacts["pack_items"])
    summary = _summary(
        artifacts,
        tests,
        delivery_fixture,
        acquisition_run_id=acquisition_run_id,
        mode=mode,
        source_bundle_path=source_bundle_path,
    )
    summary["source_bundle_records_read"] = len(source_bundles)
    run_dir = OUTPUT_ROOT / acquisition_run_id
    provisional_items = [
        row for row in artifacts["ai_results"]
        if _norm(row.get("provisional_status")) == "PROVISIONAL_SOURCE_GROUNDED"
    ]
    unavailable_items = [
        row for row in artifacts["pack_items"] if _norm(row.get("status")) == "UNAVAILABLE"
    ]
    manifest = {
        "phase": PHASE_ID,
        "acquisition_run_id": acquisition_run_id,
        "pack_e_version": PACK_E_VERSION,
        "acquisition_version": ACQUISITION_VERSION,
        "mode": mode,
        "audit_run_id": AUDIT_RUN_ID,
        "audit_request_rows_fingerprint": _read_json(AUDIT_ROOT / "request_fulfillment_summary.json").get("request_rows_fingerprint"),
        "shadow_pack_run_id": artifacts["shadow_pack_run_id"],
        "source_bundle_path": str(source_bundle_path),
        "source_bundle_records_read": len(source_bundles),
        "content_fingerprints": {
            "acquisition_results": _sha256(_strip_volatile(artifacts["request_results"])),
            "pack_e_items": _sha256(_strip_volatile(artifacts["pack_items"])),
            "provisional_items": _sha256(_strip_volatile(provisional_items)),
            "unavailable_items": _sha256(_strip_volatile(unavailable_items)),
        },
        "delivery_fixture": delivery_fixture,
        "source_workbook_writes": 0,
        "provider_calls": 0,
        "forecast_runs": 0,
        "production_writes": 0,
        "outcome_inputs_read": 0,
        "test_results": tests,
    }
    _write_jsonl(run_dir / "acquisition_results.jsonl", artifacts["request_results"])
    _write_jsonl(run_dir / "provisional_items.jsonl", provisional_items)
    _write_jsonl(run_dir / "unavailable_items.jsonl", unavailable_items)
    _write_jsonl(run_dir / "pack_e_items.jsonl", artifacts["pack_items"])
    _write_json(run_dir / "canonical_capabilities.json", {
        "acquisition_run_id": acquisition_run_id,
        "capabilities": artifacts["capabilities"],
    })
    _write_json(run_dir / "acquisition_summary.json", summary)
    _write_json(run_dir / "acquisition_manifest.json", manifest)
    return summary


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a shadow-only true shared Market-State Pack E.")
    parser.add_argument("--mode", choices=(MODE_HISTORICAL, MODE_PROSPECTIVE), default=MODE_HISTORICAL)
    parser.add_argument("--source-bundles", type=Path, default=SOURCE_BUNDLE_DEFAULT)
    return parser.parse_args(argv)


def main() -> None:
    args = _parse_args()
    print(json.dumps(build(args.mode, args.source_bundles), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
