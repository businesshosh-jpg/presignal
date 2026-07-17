#!/usr/bin/env python3
"""Read-only Phase 9 audit of provider information requests versus delivered Pack E."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_market_sessions_shadow_v0 import (  # type: ignore
    DIAGNOSTICS_SPREADSHEET_ID,
    _norm,
    _sheet_to_rows,
)
from automation.build_session_information_requests_v0 import _information_key  # type: ignore
from automation.google_clients import build_sheets_service, load_credentials  # type: ignore


PHASE_ID = "9-PACK-REQUEST-FULFILLMENT"
SCRIPT_PATH = "automation/audit_market_state_pack_request_fulfillment_v0.py"
OUTPUT_ROOT = ROOT / "outputs" / "phase9_pack_request_fulfillment"
PDF_NAME = "Final_Repaired_Phase_9.pdf"
REQUEST_PROVIDERS = ("OpenAI", "Gemini", "Anthropic")
PACK_E = "E"

INPUT_SHEETS = (
    "Session_Information_Requests",
    "Session_Information_Requests_History",
    "Information_Requirement_Library",
    "Market_State_Pack_Candidates",
    "Market_State_Pack_Acquisition_Backlog",
    "Market_State_Pack_Shadow",
    "Market_State_Pack_Item_Audit",
    "Market_State_Pack_Level_Items",
    "Market_State_Pack_Level_Summary",
    "Market_State_Source_Mapping",
    "Market_State_Source_Semantics",
    "Pack_Exposure_Forecast_Metadata",
    "Pack_Behavior_Tier2_Metadata",
    "Pack_Exposure_Prompt_Design",
)
OPTIONAL_ABSENT_SHEETS = (
    "Market_State_Pack_Acquisition_Results",
    "Market_State_Pack_Provisional_Items",
    "Market_State_Pack",
)

SUPPLIED_STATUSES = {
    "SUPPLIED_DETERMINISTIC",
    "SUPPLIED_COMPUTED",
    "SUPPLIED_CALENDAR_DERIVED",
    "SUPPLIED_AI_RETRIEVED_PROVISIONAL",
    "SUPPLIED_AI_RESEARCH_SUMMARY",
}
FINAL_STATUSES = SUPPLIED_STATUSES | {
    "ELIGIBLE_FOR_AI_ACQUISITION",
    "NOT_AVAILABLE",
    "INTERPRETIVE_NOT_SUPPLIED",
    "REJECTED_BY_POLICY",
    "NOT_IMPLEMENTED",
    "UNMAPPED_REQUEST",
    "AMBIGUOUS_FULFILLMENT",
}
INTERPRETIVE_CATEGORIES = {"risk_sentiment", "market_positioning", "jpy_intervention_risk"}
AI_ELIGIBLE_CATEGORIES = {"inflation_narrative"}
PACK_E_FAMILIES = {"usdjpy_trend", "upcoming_larger_events", "treasury_yields", "dxy"}


class AuditBlocked(RuntimeError):
    pass


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _bool(value: Any) -> bool:
    return _upper(value) in {"TRUE", "T", "YES", "Y", "1"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_id() -> str:
    return f"{PHASE_ID}_{_now().replace('-', '').replace(':', '').replace('Z', '')}Z"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical_json(dict(payload)) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(_canonical_json(dict(row)) + "\n")


def _read_inputs() -> Tuple[Dict[str, List[Dict[str, Any]]], Set[str]]:
    service = build_sheets_service(load_credentials())
    metadata = service.spreadsheets().get(
        spreadsheetId=DIAGNOSTICS_SPREADSHEET_ID, fields="sheets.properties.title"
    ).execute()
    titles = {sheet["properties"]["title"] for sheet in metadata.get("sheets", [])}
    missing = [sheet for sheet in INPUT_SHEETS if sheet not in titles]
    if missing:
        raise AuditBlocked("REQUIRED_INPUT_SHEET_MISSING:" + "|".join(sorted(missing)))
    return ({sheet: _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet) for sheet in INPUT_SHEETS}, titles)


def _request_signature(row: Mapping[str, Any]) -> str:
    return _sha256({
        "information_run_id": _norm(row.get("information_run_id")),
        "session_id": _norm(row.get("session_id")),
        "provider": _norm(row.get("provider")),
        "request_rank": _norm(row.get("request_rank")),
        "requested_information": _norm(row.get("requested_information")),
        "information_category": _norm(row.get("information_category")).lower(),
        "reason": _norm(row.get("reason")),
    })


def _request_population(
    history_rows: Sequence[Mapping[str, Any]], current_rows: Sequence[Mapping[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Use immutable history keys, adding current rows only when history lacks them."""
    selected: List[Dict[str, Any]] = []
    seen_signatures: Set[str] = set()
    history_identities: Set[str] = set()
    for raw in history_rows:
        row = dict(raw)
        if _upper(row.get("capture_status")) != "CAPTURED" or _norm(row.get("status")) != "parsed":
            continue
        history_key = _norm(row.get("history_key"))
        source_hash = _norm(row.get("source_row_hash"))
        if not history_key or not source_hash:
            raise AuditBlocked("HISTORY_REQUEST_IDENTITY_MISSING")
        signature = _request_signature(row)
        if signature in seen_signatures:
            raise AuditBlocked("DUPLICATE_REQUEST_IDENTITY:" + signature)
        seen_signatures.add(signature)
        history_identities.add(signature)
        row["request_id"] = source_hash
        row["request_lineage_id"] = history_key
        row["request_source"] = "HISTORY"
        selected.append(row)
    current_only = 0
    for raw in current_rows:
        row = dict(raw)
        if _norm(row.get("status")) != "parsed":
            continue
        signature = _request_signature(row)
        if signature in history_identities:
            continue
        if signature in seen_signatures:
            raise AuditBlocked("DUPLICATE_CURRENT_REQUEST_IDENTITY:" + signature)
        seen_signatures.add(signature)
        current_only += 1
        row["request_id"] = signature
        row["request_lineage_id"] = "CURRENT_ONLY|" + signature
        row["request_source"] = "CURRENT_ONLY"
        selected.append(row)
    selected.sort(key=lambda row: (
        _norm(row.get("session_id")), _norm(row.get("provider")),
        int(_norm(row.get("request_rank")) or "0"), _norm(row.get("request_id")),
    ))
    return selected, {"history_selected": len(selected) - current_only, "current_only_added": current_only}


def _family_only_index(rows: Sequence[Mapping[str, Any]], field: str) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for raw in rows:
        key = _norm(raw.get(field)).lower()
        if key:
            out[key].append(dict(raw))
    return out


def _latest_run(rows: Sequence[Mapping[str, Any]], run_field: str) -> str:
    run_ids = sorted({_norm(row.get(run_field)) for row in rows if _norm(row.get(run_field))})
    if not run_ids:
        raise AuditBlocked("MISSING_RUN_ID:" + run_field)
    return run_ids[-1]


def _delivered_metadata(rows: Sequence[Mapping[str, Any]], source: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, str, str, str, str]] = set()
    for raw in rows:
        if _norm(raw.get("pack_level")) != PACK_E:
            continue
        provider = _norm(raw.get("provider"))
        session_id = _norm(raw.get("session_id"))
        run_id = _norm(raw.get("execution_run_id")) or _norm(raw.get("pilot_run_id"))
        fields = _norm(raw.get("actual_pack_fields_in_prompt"))
        if not provider or not session_id or not run_id or not fields:
            raise AuditBlocked(f"PACK_E_DELIVERY_IDENTITY_MISSING:{source}")
        key = (source, run_id, session_id, provider, PACK_E)
        if key in seen:
            raise AuditBlocked("DUPLICATE_PACK_E_PROVIDER_DELIVERY:" + "|".join(key))
        seen.add(key)
        out.append({
            "delivery_source": source,
            "delivery_run_id": run_id,
            "session_id": session_id,
            "provider": provider,
            "pack_level": PACK_E,
            "forecast_timestamp": _norm(raw.get("forecast_timestamp")),
            "field_set": tuple(sorted(field for field in fields.split("|") if field)),
            "metadata_row_key": _sha256({
                "source": source, "run": run_id, "session": session_id, "provider": provider,
                "prompt_hash": _norm(raw.get("prompt_hash")), "fields": fields,
            }),
        })
    return out


def _delivery_audit(
    deliveries: Sequence[Mapping[str, Any]], expected_fields: Set[str], shadow_rows: Sequence[Mapping[str, Any]],
) -> Tuple[Dict[str, Any], Dict[str, Set[str]], Dict[str, Dict[str, Any]]]:
    groups: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in deliveries:
        groups[(str(row["delivery_source"]), str(row["delivery_run_id"]), str(row["session_id"]))].append(dict(row))
    session_provider_sets: Dict[str, Set[str]] = defaultdict(set)
    equality_failures: List[str] = []
    field_set_failures: List[str] = []
    for group_key, rows in sorted(groups.items()):
        provider_map = {str(row["provider"]): set(row["field_set"]) for row in rows}
        if set(provider_map) != set(REQUEST_PROVIDERS):
            equality_failures.append("MISSING_PROVIDER|" + "|".join(group_key))
        field_sets = {tuple(sorted(value)) for value in provider_map.values()}
        if len(field_sets) != 1:
            equality_failures.append("PROVIDER_FIELD_SET_DIFFERENCE|" + "|".join(group_key))
        elif set(next(iter(field_sets))) != expected_fields:
            field_set_failures.append("EXPECTED_PACK_E_FIELD_SET_MISMATCH|" + "|".join(group_key))
        for provider in provider_map:
            session_provider_sets[group_key[2]].add(provider)

    latest_shadow_run = _latest_run(shadow_rows, "shadow_pack_run_id")
    shadow = [dict(row) for row in shadow_rows if _norm(row.get("shadow_pack_run_id")) == latest_shadow_run]
    shadow_index: Dict[Tuple[str, str], Dict[str, Any]] = {}
    duplicate_shadow_keys: List[str] = []
    for row in shadow:
        key = (_norm(row.get("session_id")), _norm(row.get("candidate_field")))
        if key in shadow_index:
            duplicate_shadow_keys.append("|".join(key))
        shadow_index[key] = row
    if duplicate_shadow_keys:
        raise AuditBlocked("DUPLICATE_SHADOW_SESSION_FIELD:" + "|".join(sorted(duplicate_shadow_keys)))

    session_snapshots: Dict[str, Dict[str, Any]] = {}
    time_safety_failures: List[str] = []
    time_safety_unverified: List[str] = []
    field_time_states: Dict[str, List[str]] = defaultdict(list)
    for session_id in sorted(session_provider_sets):
        field_rows = [shadow_index.get((session_id, field)) for field in sorted(expected_fields)]
        if any(row is None for row in field_rows):
            field_set_failures.append("MISSING_SHADOW_FIELD|" + session_id)
            continue
        values: Dict[str, Any] = {}
        timestamps: Dict[str, Dict[str, str]] = {}
        for field, row in zip(sorted(expected_fields), field_rows):
            assert row is not None
            field_state = "PASS"
            source_observation_ts = _norm(row.get("source_observation_ts"))
            source_publication_ts = _norm(row.get("source_publication_ts"))
            as_of_timestamp = _norm(row.get("as_of_timestamp"))
            is_calendar_derived = field.startswith("NEXT_") or field == "EVENT_CLUSTER_DENSITY_NEXT_24H"
            if not as_of_timestamp:
                time_safety_failures.append("MISSING_AS_OF_TIMESTAMP|" + session_id + "|" + field)
                field_state = "FAIL"
            if not is_calendar_derived and not (source_observation_ts or source_publication_ts):
                time_safety_failures.append("MISSING_SOURCE_TIMESTAMP|" + session_id + "|" + field)
                field_state = "FAIL"
            if not _bool(row.get("data_available_flag")):
                time_safety_failures.append("DATA_UNAVAILABLE|" + session_id + "|" + field)
                field_state = "FAIL"
            if _upper(row.get("leakage_check_status")) == "FAIL" or _upper(row.get("backtest_safe")) == "FALSE":
                time_safety_failures.append("TIME_SAFETY_FAILURE|" + session_id + "|" + field)
                field_state = "FAIL"
            elif not _bool(row.get("backtest_safe")):
                # UNKNOWN is neither a safe claim nor an execution failure. Preserve it as
                # unverified provenance so the audit never upgrades a proxy to time-safe.
                time_safety_unverified.append("BACKTEST_SAFETY_UNVERIFIED|" + session_id + "|" + field)
                field_state = "UNVERIFIABLE"
            field_time_states[field].append(field_state)
            values[field] = _norm(row.get("field_value"))
            timestamps[field] = {
                "source_observation_ts": source_observation_ts,
                "source_publication_ts": source_publication_ts,
                "as_of_timestamp": as_of_timestamp,
            }
        session_snapshots[session_id] = {
            "value_fingerprint": _sha256(values),
            "timestamp_fingerprint": _sha256(timestamps),
            "values": values,
            "timestamps": timestamps,
        }
    time_safety = "FAIL" if time_safety_failures else "PARTIAL_UNVERIFIABLE" if time_safety_unverified else "PASS"
    time_safety_by_field = {
        field: "FAIL" if "FAIL" in states else "UNVERIFIABLE" if "UNVERIFIABLE" in states else "PASS"
        for field, states in sorted(field_time_states.items())
    }
    return ({
        "delivery_groups": len(groups),
        "delivery_records": len(deliveries),
        "shared_pack_equality": "PASS" if not equality_failures and not field_set_failures else "FAIL",
        "equality_failures": equality_failures,
        "field_set_failures": field_set_failures,
        "time_safety": time_safety,
        "time_safety_failures": time_safety_failures,
        "time_safety_unverified": time_safety_unverified,
        "time_safety_by_field": time_safety_by_field,
        "latest_shadow_pack_run_id": latest_shadow_run,
    }, session_provider_sets, session_snapshots)


def _semantic_scope_gap(category: str, wording: str) -> str:
    text = wording.lower()
    if category == "treasury_yields" and re.search(r"(?:\b5\s*(?:yr|year)\b|\b30\s*(?:yr|year)\b|auction)", text):
        return "REQUESTED_TENOR_OR_AUCTION_DETAIL_NOT_IN_PACK_E"
    if category == "treasury_yields" and "curve" in text:
        return "REQUESTED_FULL_CURVE_NOT_EXACTLY_DEFINED_BY_2Y_10Y_PACK_E_FIELDS"
    if category == "dxy" and ("volatility" in text or re.search(r"24\s*[- ]?48", text)):
        return "REQUESTED_DXY_WINDOW_OR_VOLATILITY_NOT_EXACTLY_DEFINED_BY_PACK_E"
    if category == "usdjpy_trend" and "correlation" in text:
        return "REQUESTED_CORRELATION_NOT_IN_PACK_E"
    return ""


def _not_delivered_status(category: str, backlog: Mapping[str, Any]) -> Tuple[str, str]:
    if category == "fed_expectations":
        return "REJECTED_BY_POLICY", "FED_EXPECTATIONS_BLOCKED_FROM_EARLY_PACK_LEVELS"
    if category in INTERPRETIVE_CATEGORIES:
        return "INTERPRETIVE_NOT_SUPPLIED", "FROZEN_DESIGN_RETURNS_INTERPRETIVE_JUDGMENT_TO_FORECASTING_PROVIDER"
    if category in AI_ELIGIBLE_CATEGORIES:
        return "ELIGIBLE_FOR_AI_ACQUISITION", "SOURCE_GROUNDED_AI_PROVISIONAL_METHOD_PLANNED_BUT_NOT_IMPLEMENTED"
    if not backlog:
        return "UNMAPPED_REQUEST", "NO_CANDIDATE_OR_BACKLOG_EVIDENCE"
    return "NOT_IMPLEMENTED", "NO_RELEVANT_SESSION_PACK_E_DELIVERY_OR_IMPLEMENTED_ACQUISITION"


def _fulfilled_status(category: str, wording: str) -> Tuple[str, str]:
    gap = _semantic_scope_gap(category, wording)
    if gap:
        return "AMBIGUOUS_FULFILLMENT", gap
    if category == "treasury_yields":
        return "SUPPLIED_DETERMINISTIC", "US2Y_AND_US10Y_LEVEL_CHANGE_AND_CURVE_FIELDS_DELIVERED"
    if category == "dxy":
        return "SUPPLIED_COMPUTED", "DXY_LEVEL_CHANGE_AND_DIRECTION_FIELDS_DELIVERED"
    if category == "usdjpy_trend":
        return "SUPPLIED_COMPUTED", "USDJPY_1H_4H_24H_TREND_AND_REALIZED_VOLATILITY_FIELDS_DELIVERED"
    if category == "upcoming_larger_events":
        return "SUPPLIED_CALENDAR_DERIVED", "SCHEDULED_EVENT_HORIZON_AND_CLUSTER_FIELDS_DELIVERED"
    raise AuditBlocked("UNEXPECTED_PACK_E_FAMILY:" + category)


def _classify_request(
    request: Mapping[str, Any], library: Mapping[str, Any], candidate: Mapping[str, Any], backlog: Mapping[str, Any],
    e_families: Set[str], delivered_provider_sessions: Mapping[str, Set[str]],
) -> Dict[str, Any]:
    category = _norm(request.get("information_category")).lower()
    wording = _norm(request.get("requested_information"))
    normalized_key = _information_key(category, wording)
    session_id = _norm(request.get("session_id"))
    provider = _norm(request.get("provider"))
    candidate_mapping = "EXACT" if candidate.get("exact") else "FAMILY_ONLY" if candidate else "NONE"
    received = provider in delivered_provider_sessions.get(session_id, set())
    if category in PACK_E_FAMILIES and received:
        final_status, reason = _fulfilled_status(category, wording)
    else:
        final_status, reason = _not_delivered_status(category, backlog)
    if final_status not in FINAL_STATUSES:
        raise AuditBlocked("INVALID_FINAL_STATUS:" + final_status)
    return {
        "request_id": _norm(request.get("request_id")),
        "request_lineage_id": _norm(request.get("request_lineage_id")),
        "request_source": _norm(request.get("request_source")),
        "provider": provider,
        "session_id": session_id,
        "request_timestamp": _norm(request.get("generated_ts")),
        "request_run_id": _norm(request.get("information_run_id")),
        "request_rank": _norm(request.get("request_rank")),
        "request_wording": wording,
        "normalized_information_key": normalized_key,
        "information_category": category,
        "priority": _norm(request.get("priority")),
        "reason": _norm(request.get("reason")),
        "suggested_source": _norm(request.get("suggested_source")),
        "library_status": "EXACT_LIBRARY_RECORD" if library else "NO_EXACT_LIBRARY_RECORD",
        "library_information_key": _norm(library.get("information_key")),
        "candidate_mapping_status": candidate_mapping,
        "candidate_id": _norm(candidate.get("candidate_id")),
        "candidate_status": _norm(candidate.get("candidate_status")),
        "candidate_recommended_acquisition_method": _norm(candidate.get("recommended_acquisition_method")),
        "backlog_status": _norm(backlog.get("implementation_status")),
        "backlog_acquisition_method": _norm(backlog.get("recommended_acquisition_method")),
        "relevant_session_received_pack_e": "TRUE" if received else "FALSE",
        "pack_e_family_present": "TRUE" if category in e_families else "FALSE",
        "final_fulfillment_status": final_status,
        "omission_or_fulfillment_reason": reason,
    }


def _pack_e_inventory(
    level_items: Sequence[Mapping[str, Any]], semantics: Sequence[Mapping[str, Any]], mappings: Sequence[Mapping[str, Any]],
    requests: Sequence[Mapping[str, Any]], session_snapshots: Mapping[str, Mapping[str, Any]],
    delivery_sessions: Mapping[str, Set[str]], time_safety_by_field: Mapping[str, str],
) -> List[Dict[str, Any]]:
    semantics_by_field = {_norm(row.get("candidate_field")): dict(row) for row in semantics}
    mappings_by_field = {_norm(row.get("candidate_field")): dict(row) for row in mappings}
    request_by_category: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for row in requests:
        request_by_category[_norm(row.get("information_category")).lower()].append(row)
    included = [row for row in level_items if _norm(row.get("pack_level")) == PACK_E and _bool(row.get("include_in_level"))]
    inventory: List[Dict[str, Any]] = []
    for raw in sorted(included, key=lambda row: (_norm(row.get("candidate_family")), _norm(row.get("candidate_field")))):
        row = dict(raw)
        family = _norm(row.get("candidate_family")).lower()
        field = _norm(row.get("candidate_field"))
        request_rows = request_by_category.get(family, [])
        if field in {"USD_INDEX_PROXY_LEVEL", "USD_INDEX_PROXY_CHANGE"}:
            lineage = "DERIVED_SUPPORT_FIELD"
        elif family == "upcoming_larger_events":
            lineage = "CALENDAR_REQUIRED"
        elif request_rows:
            lineage = "REQUEST_DRIVEN"
        else:
            lineage = "UNTRACEABLE"
        values = {session: _norm(snapshot["values"].get(field)) for session, snapshot in sorted(session_snapshots.items())}
        timestamps = {
            session: dict(snapshot["timestamps"].get(field, {}))
            for session, snapshot in sorted(session_snapshots.items())
        }
        semantic = semantics_by_field.get(field, {})
        mapping = mappings_by_field.get(field, {})
        inventory.append({
            "pack_item_key": family + "|" + field,
            "candidate_family": family,
            "canonical_information": _norm(semantic.get("canonical_definition")) or field,
            "information_class": "calendar_derived" if family == "upcoming_larger_events" else "deterministic_market_state",
            "acquisition_method": _norm(row.get("acquisition_method")),
            "source": _norm(row.get("source_name")) or _norm(mapping.get("primary_source_name")),
            "source_timestamp": timestamps,
            "as_of_timestamp": {session: value.get("as_of_timestamp", "") for session, value in timestamps.items()},
            "value": values,
            "value_fingerprint": _sha256(values),
            "reliability": time_safety_by_field.get(field, "NO_DELIVERY_SESSION_VALUE") if values else "NO_DELIVERY_SESSION_VALUE",
            "provisional_status": "FALSE",
            "request_lineage": lineage,
            "requesting_providers": "|".join(sorted({_norm(request.get("provider")) for request in request_rows})),
            "request_count": len(request_rows),
            "session_count": len({_norm(request.get("session_id")) for request in request_rows}),
            "actually_sent_to_forecasters": "TRUE" if delivery_sessions else "FALSE",
            "delivery_session_count": len(session_snapshots),
        })
    return inventory


def _acquisition_ai_status(titles: Set[str]) -> Dict[str, Any]:
    occurrence_files: List[str] = []
    invocation_files: List[str] = []
    for path in sorted((ROOT / "automation").glob("*.py")):
        # The audit knows the vocabulary it is testing. It cannot constitute
        # implementation evidence for the acquisition layer it is auditing.
        if path.resolve() == Path(__file__).resolve():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "ai_retrieved_provisional" in text or "ai_research_summary" in text:
            occurrence_files.append(str(path.relative_to(ROOT)))
        if "ai_retrieved_provisional" in text and ("run_script_function" in text or "apiCallProvider" in text):
            invocation_files.append(str(path.relative_to(ROOT)))
    result_sheets = {
        name: name in titles for name in ("Market_State_Pack_Acquisition_Results", "Market_State_Pack_Provisional_Items")
    }
    status = "BACKLOG_ONLY" if not invocation_files and not any(result_sheets.values()) else "PARTIALLY_IMPLEMENTED"
    return {
        "acquisition_ai_status": status,
        "method_catalog_files": occurrence_files,
        "acquisition_invocation_files": invocation_files,
        "result_or_provisional_sheets_present": result_sheets,
        "evidence": "No executable acquisition invocation, result sheet, provisional-item sheet, or Pack E AI field was found."
        if status == "BACKLOG_ONLY" else "Review the listed invocation or result evidence.",
    }


def _find_pdf() -> str:
    matches = list(ROOT.rglob(PDF_NAME))
    return str(matches[0]) if matches else ""


def _content_projection(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    volatile = {"audit_run_id", "audit_generated_ts"}
    return [{key: value for key, value in row.items() if key not in volatile} for row in rows]


def build() -> Dict[str, Any]:
    audit_run_id = _run_id()
    run_dir = OUTPUT_ROOT / audit_run_id
    inputs, titles = _read_inputs()
    pdf_path = _find_pdf()
    requests, request_population_stats = _request_population(
        inputs["Session_Information_Requests_History"], inputs["Session_Information_Requests"]
    )
    libraries = {_norm(row.get("information_key")): dict(row) for row in inputs["Information_Requirement_Library"]}
    candidates_exact = {_norm(row.get("information_key")): dict(row) for row in inputs["Market_State_Pack_Candidates"]}
    candidates_by_category = _family_only_index(inputs["Market_State_Pack_Candidates"], "information_category")
    backlog_by_candidate = {_norm(row.get("candidate_id")): dict(row) for row in inputs["Market_State_Pack_Acquisition_Backlog"]}

    latest_level_run = _latest_run(inputs["Market_State_Pack_Level_Items"], "pack_design_run_id")
    level_items = [
        dict(row) for row in inputs["Market_State_Pack_Level_Items"]
        if _norm(row.get("pack_design_run_id")) == latest_level_run
    ]
    e_fields = {
        _norm(row.get("candidate_field")) for row in level_items
        if _norm(row.get("pack_level")) == PACK_E and _bool(row.get("include_in_level"))
    }
    if not e_fields:
        raise AuditBlocked("PACK_E_HAS_NO_INCLUDED_FIELDS")
    deliveries = _delivered_metadata(inputs["Pack_Behavior_Tier2_Metadata"], "TIER2") + _delivered_metadata(
        inputs["Pack_Exposure_Forecast_Metadata"], "PILOT"
    )
    delivery, delivered_provider_sessions, snapshots = _delivery_audit(
        deliveries, e_fields, inputs["Market_State_Pack_Shadow"]
    )
    if delivery["shared_pack_equality"] != "PASS":
        raise AuditBlocked("PACK_E_DELIVERY_EQUALITY_FAILED")
    if delivery["time_safety"] == "FAIL":
        raise AuditBlocked("PACK_E_TIME_SAFETY_FAILED")

    audit_rows: List[Dict[str, Any]] = []
    exact_library_count = 0
    exact_candidate_count = 0
    family_candidate_count = 0
    for request in requests:
        category = _norm(request.get("information_category")).lower()
        key = _information_key(category, _norm(request.get("requested_information")))
        library = libraries.get(key, {})
        candidate = candidates_exact.get(key, {})
        if candidate:
            exact_candidate_count += 1
            candidate_record = {**candidate, "exact": True}
        else:
            by_family = candidates_by_category.get(category, [])
            if len(by_family) == 1:
                family_candidate_count += 1
                candidate_record = {**by_family[0], "exact": False}
            elif len(by_family) > 1:
                raise AuditBlocked("AMBIGUOUS_CATEGORY_CANDIDATE_MAPPING:" + category)
            else:
                candidate_record = {}
        if library:
            exact_library_count += 1
        backlog = backlog_by_candidate.get(_norm(candidate_record.get("candidate_id")), {})
        row = _classify_request(request, library, candidate_record, backlog, PACK_E_FAMILIES, delivered_provider_sessions)
        row["audit_run_id"] = audit_run_id
        row["audit_generated_ts"] = _now()
        audit_rows.append(row)

    request_ids = {_norm(row.get("request_id")) for row in audit_rows}
    if len(request_ids) != len(audit_rows) or "" in request_ids:
        raise AuditBlocked("REQUEST_ROW_UNIQUENESS_FAILED")
    inventory = _pack_e_inventory(
        level_items, inputs["Market_State_Source_Semantics"], inputs["Market_State_Source_Mapping"],
        audit_rows, snapshots, delivered_provider_sessions, delivery["time_safety_by_field"],
    )
    if {row["pack_item_key"].split("|", 1)[1] for row in inventory} != e_fields:
        raise AuditBlocked("PACK_E_INVENTORY_RECONCILIATION_FAILED")
    ai_status = _acquisition_ai_status(titles)
    statuses = Counter(_norm(row.get("final_fulfillment_status")) for row in audit_rows)
    providers = {provider: [row for row in audit_rows if row["provider"] == provider] for provider in REQUEST_PROVIDERS}
    provider_summary = {
        provider: {
            "request_count": len(rows),
            "fulfilled_count": sum(row["final_fulfillment_status"] in SUPPLIED_STATUSES for row in rows),
            "status_counts": dict(sorted(Counter(row["final_fulfillment_status"] for row in rows).items())),
        }
        for provider, rows in providers.items()
    }
    category_summary = {
        category: dict(sorted(Counter(row["final_fulfillment_status"] for row in rows).items()))
        for category, rows in sorted(_family_only_index(audit_rows, "information_category").items())
    }
    delivered_request_rows = sum(_bool(row["relevant_session_received_pack_e"]) for row in audit_rows)
    requested_sessions = {_norm(row["session_id"]) for row in audit_rows}
    delivered_requested_sessions = requested_sessions & set(delivered_provider_sessions)
    output_projection = _content_projection(audit_rows)
    inventory_projection = _content_projection(inventory)
    summary = {
        "build_status": "PASS",
        "audit_run_id": audit_run_id,
        "design_reference": str(pdf_path) if pdf_path else "PDF_NOT_FOUND_PROMPT_PIPELINE_USED",
        "provider_requests_reviewed": len(audit_rows),
        "distinct_normalized_requests": len({_norm(row["normalized_information_key"]) for row in audit_rows}),
        "pack_e_items_reviewed": len(inventory),
        "request_population": request_population_stats,
        "exact_library_matches": exact_library_count,
        "exact_candidate_matches": exact_candidate_count,
        "family_only_candidate_matches": family_candidate_count,
        "requests_fulfilled": sum(statuses[status] for status in SUPPLIED_STATUSES),
        "requests_partially_fulfilled": statuses["AMBIGUOUS_FULFILLMENT"],
        "requests_unfulfilled": sum(statuses[status] for status in ("NOT_IMPLEMENTED", "NOT_AVAILABLE", "ELIGIBLE_FOR_AI_ACQUISITION")),
        "requests_unmapped": statuses["UNMAPPED_REQUEST"],
        "interpretive_requests_not_supplied": statuses["INTERPRETIVE_NOT_SUPPLIED"],
        "policy_rejected_requests": statuses["REJECTED_BY_POLICY"],
        "fulfillment_by_status": dict(sorted(statuses.items())),
        "fulfillment_by_provider": provider_summary,
        "fulfillment_by_category": category_summary,
        "pack_e_request_driven_items": sum(row["request_lineage"] == "REQUEST_DRIVEN" for row in inventory),
        "pack_e_system_assumed_items": sum(row["request_lineage"] == "SYSTEM_ASSUMED" for row in inventory),
        "pack_e_derived_support_items": sum(row["request_lineage"] == "DERIVED_SUPPORT_FIELD" for row in inventory),
        "pack_e_calendar_required_items": sum(row["request_lineage"] == "CALENDAR_REQUIRED" for row in inventory),
        "pack_e_untraceable_items": sum(row["request_lineage"] == "UNTRACEABLE" for row in inventory),
        "request_fulfillment_rate": round(sum(statuses[status] for status in SUPPLIED_STATUSES) / len(audit_rows), 6),
        "provider_coverage_rate": round(delivered_request_rows / len(audit_rows), 6),
        "session_coverage_rate": round(len(delivered_requested_sessions) / len(requested_sessions), 6),
        "deterministic_coverage_rate": round(
            sum(statuses[status] for status in ("SUPPLIED_DETERMINISTIC", "SUPPLIED_COMPUTED", "SUPPLIED_CALENDAR_DERIVED")) / len(audit_rows), 6
        ),
        "provisional_acquisition_coverage_rate": 0.0,
        "shared_pack_equality": delivery["shared_pack_equality"],
        "time_safety": delivery["time_safety"],
        "provider_delivery": "PASS",
        "acquisition_ai": ai_status,
        "request_rows_fingerprint": _sha256(output_projection),
        "pack_e_inventory_fingerprint": _sha256(inventory_projection),
        "code_fingerprint": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "production_or_consumer_changes": 0,
        "scientific_rules_changed": 0,
    }
    if exact_candidate_count == 0 and len(audit_rows) > 0:
        decision = "REQUEST_NORMALIZATION_REPAIR_REQUIRED"
        next_step = "Repair request normalization"
    elif delivery["shared_pack_equality"] != "PASS":
        decision = "PACK_E_DELIVERY_DEFECT_REQUIRED"
        next_step = "Repair Pack E provider delivery"
    elif summary["requests_fulfilled"] < len(audit_rows):
        decision = "PACK_E_PARTIAL_ACQUISITION_IMPLEMENTATION_REQUIRED"
        next_step = "Implement the justified missing acquisition methods"
    else:
        decision = "PACK_E_REQUEST_FULFILLMENT_CONFIRMED"
        next_step = "Proceed to build and freeze the true shared Pack E"
    summary["final_decision"] = decision
    summary["next_scientific_step"] = next_step

    manifest = {
        "audit_run_id": audit_run_id,
        "phase": PHASE_ID,
        "script_path": SCRIPT_PATH,
        "input_sheets": {sheet: len(inputs[sheet]) for sheet in INPUT_SHEETS},
        "optional_absent_sheets": [sheet for sheet in OPTIONAL_ABSENT_SHEETS if sheet not in titles],
        "pack_level_run_id": latest_level_run,
        "delivery": delivery,
        "row_count": len(audit_rows),
        "inventory_count": len(inventory),
        "request_rows_fingerprint": summary["request_rows_fingerprint"],
        "pack_e_inventory_fingerprint": summary["pack_e_inventory_fingerprint"],
        "outcome_or_forecast_execution": "NOT_PERFORMED",
        "source_workbook_writes": 0,
    }
    _write_jsonl(run_dir / "request_fulfillment_rows.jsonl", audit_rows)
    _write_jsonl(run_dir / "pack_e_inventory.jsonl", inventory)
    _write_json(run_dir / "acquisition_gap_summary.json", {
        "audit_run_id": audit_run_id,
        "acquisition_ai": ai_status,
        "missing_status_counts": {
            status: statuses[status] for status in sorted(statuses) if status not in SUPPLIED_STATUSES
        },
        "dominant_categories": sorted(
            ((category, sum(counts.values())) for category, counts in category_summary.items()),
            key=lambda item: (-item[1], item[0]),
        ),
    })
    _write_json(run_dir / "request_fulfillment_summary.json", summary)
    _write_json(run_dir / "audit_manifest.json", manifest)
    return summary


def main() -> None:
    print(json.dumps(build(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
