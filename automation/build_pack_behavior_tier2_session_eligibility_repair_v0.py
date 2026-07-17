import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_market_sessions_shadow_v0 import (
    DIAGNOSTICS_SPREADSHEET_ID,
    MAIN_SPREADSHEET_ID,
    MEMBERS_HEADERS,
    OUTPUT_SHEETS as MARKET_SESSION_OUTPUT_SHEETS,
    SESSIONS_HEADERS,
    SHADOW_VERSION as MARKET_SESSION_SHADOW_VERSION,
    SUMMARY_HEADERS as MARKET_SESSION_SUMMARY_HEADERS,
    SCHEMA_VERSION as MARKET_SESSION_SCHEMA_VERSION,
    _ensure_sheet,
    _norm,
    _parse_dt,
    _sheet_to_rows,
    _write_rows,
)
from automation.build_market_state_pack_shadow_v0 import build_market_state_pack_shadow_v0
from automation.build_pack_behavior_tier2_execution_plan_v0 import build_pack_behavior_tier2_execution_plan_v0
from automation.build_pack_exposure_prompt_validation_v0 import EXPECTED_FIELDS_BY_LEVEL
from automation.build_presignal_v2_replay_queue_v0 import _read_config_value_map, _resolve_replay_window, _session_assignment
from automation.build_session_information_requests_v0 import _iso_now, _truncate_text
from automation.google_clients import build_sheets_service, load_credentials


SCHEMA_VERSION = "presignal_v2_behavior_tier2_session_eligibility_repair_0.1"
REPAIR_VERSION = "behavior_tier2_session_eligibility_repair_v0"
OUTPUT_AUDIT_SHEET = "Pack_Behavior_Tier2_Session_Eligibility_Audit"

INPUT_SHADOW = "Market_State_Pack_Shadow"
INPUT_SHADOW_SUMMARY = "Market_State_Pack_Shadow_Summary"
INPUT_PILOT_SUMMARY = "Pack_Exposure_Run_Summary"
INPUT_TIER1_RUNS = "Pack_Behavior_Discovery_Runs"
INPUT_TIER1_SUMMARY = "Pack_Behavior_Discovery_Run_Summary"
INPUT_PLAN_SUMMARY = "Pack_Behavior_Tier2_Execution_Plan_Summary"
INPUT_EVENT = "Event"

REQUIRED_FIELDS = tuple(EXPECTED_FIELDS_BY_LEVEL["E"])
MIN_ELIGIBLE_UNUSED_SESSIONS = 5

USED_SESSION_FLOOR = "2024-05-15"
AFTER_SEARCH_FROM = "2024-05-21"
AFTER_SEARCH_TO = "2024-05-28"
BEFORE_SEARCH_FROM = "2024-05-01"
BEFORE_SEARCH_TO = "2024-05-08"

AUDIT_HEADERS = [
    "generated_ts",
    "schema_version",
    "repair_version",
    "repair_run_id",
    "session_id",
    "session_date",
    "search_bucket",
    "event_candidate_present",
    "event_candidate_count",
    "used_by_pilot_or_tier1",
    "status_before",
    "reason_before",
    "missing_fields_before",
    "missing_reasons_before",
    "repaired_this_run",
    "status_after",
    "reason_after",
    "missing_fields_after",
    "missing_reasons_after",
    "became_additional_eligible_unused",
    "notes",
]


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _parse_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _repair_run_id(generated_ts: str) -> str:
    stamp = generated_ts.replace("-", "").replace(":", "").replace("+00:00", "Z").replace(".", "")
    return f"pack_behavior_tier2_session_eligibility_repair_v0_{stamp}"


def _latest_row(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    return rows[-1] if rows else {}


def _latest_run_id(rows: Sequence[Dict[str, Any]], field: str) -> str:
    for row in reversed(rows):
        value = _norm(row.get(field))
        if value:
            return value
    return ""


def _used_sessions(
    pilot_rows: Sequence[Dict[str, Any]],
    tier1_runs: Sequence[Dict[str, Any]],
    tier1_summary: Sequence[Dict[str, Any]],
) -> Set[str]:
    used: Set[str] = set()
    for row in pilot_rows:
        session_id = _norm(row.get("session_selected"))
        if session_id:
            used.add(session_id)
    for row in tier1_runs:
        session_id = _norm(row.get("session_id"))
        if session_id:
            used.add(session_id)
    for row in tier1_summary:
        session_id = _norm(row.get("session_id"))
        if session_id:
            used.add(session_id)
    return used


def _build_replay_window(service) -> Dict[str, Any]:
    config = _read_config_value_map(service)
    return _resolve_replay_window(SimpleNamespace(country="US"), config)


def _importance_bucket(value: Any) -> str:
    raw = _upper(value)
    if raw in {"HIGH", "MEDIUM", "LOW"}:
        return raw
    return "UNKNOWN"


def _join_unique(values: Iterable[Any]) -> str:
    seen: Set[str] = set()
    out: List[str] = []
    for value in values:
        text = _norm(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return "|".join(out)


def _eligible_event(row: Dict[str, Any], country_filter: str) -> bool:
    if not _norm(row.get("event_id")):
        return False
    if not _norm(row.get("type")):
        return False
    if not _norm(row.get("country")):
        return False
    if country_filter and country_filter != "ALL" and _upper(row.get("country")) != _upper(country_filter):
        return False
    if not _norm(row.get("indicator_name")):
        return False
    return _parse_dt(row.get("release_ts")) is not None


def _daily_market_session_rows(
    generated_ts: str,
    event_rows: Sequence[Dict[str, Any]],
    window: Dict[str, Any],
    from_dt: datetime,
    to_dt: datetime,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    grouped: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    counts = Counter()
    country_filter = _upper(window.get("country") or "US")
    session_window_name = _norm(window.get("session_window_name")) or "CUSTOM_CONFIG_WINDOW"

    for row in event_rows:
        if not _eligible_event(row, country_filter):
            if not _norm(row.get("event_id")):
                counts["missing_event_id"] += 1
            elif not _norm(row.get("type")):
                counts["missing_type"] += 1
            elif not _norm(row.get("country")):
                counts["missing_country"] += 1
            elif country_filter and country_filter != "ALL" and _upper(row.get("country")) != country_filter:
                counts["filtered_country"] += 1
            elif not _norm(row.get("indicator_name")):
                counts["missing_indicator_name"] += 1
            else:
                counts["missing_release_ts"] += 1
            continue

        release_dt = _parse_dt(row.get("release_ts"))
        if release_dt is None:
            counts["missing_release_ts"] += 1
            continue
        if release_dt < from_dt or release_dt >= to_dt:
            counts["outside_window"] += 1
            continue

        session_date, session_start_dt, session_end_dt = _session_assignment(release_dt, window)
        session_id = f"{country_filter}|{session_date}|{session_window_name}"
        grouped[(session_id, session_date, country_filter)].append(
            {
                "event_id": _norm(row.get("event_id")),
                "batch_id": _norm(row.get("batch_id")),
                "type": _norm(row.get("type")),
                "indicator_name": _norm(row.get("indicator_name")),
                "genre": _norm(row.get("genre")),
                "importance": _norm(row.get("importance")),
                "release_dt": release_dt,
                "consensus_value": _norm(row.get("consensus_value")),
                "prev_revision": _norm(row.get("prev_revision")),
                "source_row_number": row.get("__source_row_number__", ""),
                "session_start_dt": session_start_dt,
                "session_end_dt": session_end_dt,
                "is_batch_member": "TRUE" if _upper(row.get("type")) == "MEMBER" or _norm(row.get("batch_id")) else "FALSE",
            }
        )

    session_rows: List[Dict[str, Any]] = []
    member_rows: List[Dict[str, Any]] = []
    ordered_sessions = sorted(grouped.items(), key=lambda item: (item[0][1], item[0][0]))
    for session_id_tuple, members in ordered_sessions:
        session_id, session_date, country = session_id_tuple
        members.sort(key=lambda row: (row["release_dt"], row["indicator_name"], row["event_id"]))
        first_release_dt = members[0]["release_dt"]
        last_release_dt = members[-1]["release_dt"]
        importance_counts = Counter(_importance_bucket(row.get("importance")) for row in members)
        batch_count = sum(1 for row in members if row["is_batch_member"] == "TRUE")
        session_rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": MARKET_SESSION_SCHEMA_VERSION,
                "shadow_version": MARKET_SESSION_SHADOW_VERSION,
                "session_id": session_id,
                "session_date": session_date,
                "country": country,
                "session_window_name": session_window_name,
                "session_start_ts": members[0]["session_start_dt"].astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "session_end_ts": members[0]["session_end_dt"].astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "primary_release_ts": first_release_dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "last_release_ts": last_release_dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "member_event_count": len(members),
                "member_event_ids": _join_unique(member["event_id"] for member in members),
                "member_indicator_names": _join_unique(member["indicator_name"] for member in members),
                "member_genres": _join_unique(member["genre"] for member in members),
                "member_importance_levels": _join_unique(member["importance"] for member in members),
                "high_importance_count": importance_counts.get("HIGH", 0),
                "medium_importance_count": importance_counts.get("MEDIUM", 0),
                "low_importance_count": importance_counts.get("LOW", 0),
                "unknown_importance_count": importance_counts.get("UNKNOWN", 0),
                "batch_count": batch_count,
                "single_count": len(members) - batch_count,
                "member_count": len(members),
                "session_status": "built",
                "source_event_sheet": INPUT_EVENT,
                "notes": "tier2 eligibility repair daily session materialization",
            }
        )
        for index, member in enumerate(members, start=1):
            member_rows.append(
                {
                    "generated_ts": generated_ts,
                    "schema_version": MARKET_SESSION_SCHEMA_VERSION,
                    "shadow_version": MARKET_SESSION_SHADOW_VERSION,
                    "session_id": session_id,
                    "session_date": session_date,
                    "country": country,
                    "session_window_name": session_window_name,
                    "event_id": member["event_id"],
                    "batch_id": member["batch_id"],
                    "type": member["type"],
                    "indicator_name": member["indicator_name"],
                    "genre": member["genre"],
                    "importance": member["importance"],
                    "release_ts": member["release_dt"].astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    "consensus_value": member["consensus_value"],
                    "prev_revision": member["prev_revision"],
                    "member_order": index,
                    "same_minute_group_key": f"{country}|{member['release_dt'].astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:00Z')}",
                    "is_batch_member": member["is_batch_member"],
                    "source_sheet": INPUT_EVENT,
                    "source_row_number": member["source_row_number"],
                    "notes": "tier2 eligibility repair daily member mapping",
                }
            )

    summary = {
        "source_event_rows_read": len(event_rows),
        "eligible_event_rows": len(member_rows),
        "events_missing_event_id": counts["missing_event_id"],
        "events_missing_release_ts": counts["missing_release_ts"],
        "events_missing_country": counts["missing_country"],
        "events_missing_indicator_name": counts["missing_indicator_name"],
        "events_missing_type": counts["missing_type"],
        "events_filtered_by_country": counts["filtered_country"],
        "events_outside_window": counts["outside_window"],
    }
    return session_rows, member_rows, summary


def _write_market_session_shadow(
    service,
    generated_ts: str,
    window: Dict[str, Any],
    session_rows: Sequence[Dict[str, Any]],
    member_rows: Sequence[Dict[str, Any]],
    source_summary: Dict[str, Any],
    from_date: str,
    to_date: str,
) -> None:
    session_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, MARKET_SESSION_OUTPUT_SHEETS["sessions"], SESSIONS_HEADERS)
    member_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, MARKET_SESSION_OUTPUT_SHEETS["members"], MEMBERS_HEADERS)
    summary_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, MARKET_SESSION_OUTPUT_SHEETS["summary"], MARKET_SESSION_SUMMARY_HEADERS)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, MARKET_SESSION_OUTPUT_SHEETS["sessions"], session_headers, session_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, MARKET_SESSION_OUTPUT_SHEETS["members"], member_headers, member_rows)
    summary_row = {
        "generated_ts": generated_ts,
        "schema_version": MARKET_SESSION_SCHEMA_VERSION,
        "shadow_version": MARKET_SESSION_SHADOW_VERSION,
        "build_status": "PASS" if session_rows else "PASS_WITH_WARNINGS",
        "source_event_rows_read": source_summary["source_event_rows_read"],
        "eligible_event_rows": source_summary["eligible_event_rows"],
        "sessions_built": len(session_rows),
        "session_member_rows_written": len(member_rows),
        "events_missing_event_id": source_summary["events_missing_event_id"],
        "events_missing_release_ts": source_summary["events_missing_release_ts"],
        "events_missing_country": source_summary["events_missing_country"],
        "events_missing_indicator_name": source_summary["events_missing_indicator_name"],
        "events_missing_type": source_summary["events_missing_type"],
        "events_filtered_by_country": source_summary["events_filtered_by_country"],
        "events_outside_window": source_summary["events_outside_window"],
        "duplicate_member_assignments": 0,
        "events_assigned_multiple_sessions": 0,
        "events_assigned_zero_sessions": 0,
        "market_sessions_sheet_written": "TRUE",
        "market_session_members_sheet_written": "TRUE",
        "sheet_registry_updated": "FALSE",
        "governance_status": "DERIVED_ONLY_SHADOW_SAFE",
        "final_interpretation": "MARKET_SESSION_GROUPING_READY" if session_rows else "MARKET_SESSION_GROUPING_NEEDS_REVIEW",
        "country_filter": _norm(window.get("country")) or "US",
        "session_window_name": _norm(window.get("session_window_name")) or "CUSTOM_CONFIG_WINDOW",
        "window_source": "tier2_session_eligibility_repair",
        "window_timezone": _norm(window.get("timezone")) or "UTC",
        "window_from_local": f"{from_date} 00:00",
        "window_to_local": f"{to_date} 00:00",
        "window_from_utc": f"{from_date}T00:00:00Z",
        "window_to_utc": f"{to_date}T00:00:00Z",
        "notes": "Tier 2 eligibility repair daily session materialization; shadow-only; no provider calls; no forecasts.",
        "sanity_failures": "",
    }
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, MARKET_SESSION_OUTPUT_SHEETS["summary"], summary_headers, [summary_row])


def _shadow_status_by_session(rows: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    required = set(REQUIRED_FIELDS)
    by_session: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        session_id = _norm(row.get("session_id"))
        field = _norm(row.get("candidate_field"))
        if session_id and field in required:
            by_session[session_id][field] = row

    statuses: Dict[str, Dict[str, Any]] = {}
    for session_id, fields in by_session.items():
        missing_fields = sorted(required - set(fields))
        missing_reasons = sorted({_norm(row.get("missing_reason")) for row in fields.values() if _norm(row.get("missing_reason"))})
        unavailable_reasons = sorted({_norm(row.get("missing_reason")) for row in fields.values() if _upper(row.get("data_available_flag")) != "TRUE"})
        leakage_fail = any(_upper(row.get("leakage_check_status")) == "FAIL" for row in fields.values())
        provider_visible = any(_upper(row.get("provider_visible")) == "TRUE" for row in fields.values())
        used_in_forecast = any(_upper(row.get("used_in_forecast")) == "TRUE" for row in fields.values())
        complete = (
            not missing_fields
            and all(_upper(row.get("data_available_flag")) == "TRUE" for row in fields.values())
            and not leakage_fail
            and not provider_visible
            and not used_in_forecast
        )
        statuses[session_id] = {
            "session_id": session_id,
            "session_date": _norm(next(iter(fields.values())).get("session_date")) if fields else "",
            "field_count": len(fields),
            "missing_fields": missing_fields,
            "missing_reasons": missing_reasons,
            "unavailable_reasons": unavailable_reasons,
            "complete": complete,
            "weekend_or_market_closed": bool(unavailable_reasons) and all(
                reason in {"market_closed", "weekend_gap_outside_tolerance"} for reason in unavailable_reasons
            ),
            "leakage_fail": leakage_fail,
            "provider_visible": provider_visible,
            "used_in_forecast": used_in_forecast,
        }
    return statuses


def _status_label(session_id: str, shadow_status: Dict[str, Dict[str, Any]], used_sessions: Set[str]) -> str:
    info = shadow_status.get(session_id)
    if not info:
        return "ABSENT_FROM_SHADOW"
    if info["complete"] and session_id in used_sessions:
        return "USED_COMPLETE"
    if info["complete"]:
        return "ELIGIBLE_UNUSED"
    if session_id in used_sessions:
        return "USED_INCOMPLETE"
    return "INELIGIBLE"


def _reason_label(session_id: str, shadow_status: Dict[str, Dict[str, Any]]) -> str:
    info = shadow_status.get(session_id)
    if not info:
        return "Incomplete shadow acquisition"
    if info["weekend_or_market_closed"]:
        return "Weekend / market closed"
    if info["missing_fields"]:
        return "Missing deterministic fields"
    if any(reason in {"source_unavailable", "insufficient_history"} for reason in info["unavailable_reasons"]):
        return "Missing market-state data"
    if info["leakage_fail"] or info["provider_visible"] or info["used_in_forecast"]:
        return "Data quality issue"
    if info["unavailable_reasons"]:
        return "Incomplete shadow acquisition"
    return "Other"


def _candidate_sessions(
    event_rows: Sequence[Dict[str, Any]],
    window: Dict[str, Any],
    from_date: str,
    to_date: str,
) -> Dict[str, int]:
    from_dt = _parse_date(from_date)
    to_dt = _parse_date(to_date)
    counts: Dict[str, int] = Counter()
    for row in event_rows:
        if not _eligible_event(row, _norm(window.get("country")) or "US"):
            continue
        release_dt = _parse_dt(row.get("release_ts"))
        if release_dt is None or release_dt < from_dt or release_dt >= to_dt:
            continue
        session_date, _, _ = _session_assignment(release_dt, window)
        session_id = f"{_upper(row.get('country'))}|{session_date}|{_norm(window.get('session_window_name')) or 'CUSTOM_CONFIG_WINDOW'}"
        counts[session_id] += 1
    return dict(sorted(counts.items(), key=lambda item: item[0]))


def _eligible_unused_sessions(shadow_status: Dict[str, Dict[str, Any]], used_sessions: Set[str]) -> List[str]:
    return sorted(session_id for session_id, info in shadow_status.items() if info["complete"] and session_id not in used_sessions)


def _audit_rows(
    generated_ts: str,
    repair_run_id: str,
    session_ids: Sequence[str],
    after_candidates: Dict[str, int],
    before_candidates: Dict[str, int],
    used_sessions: Set[str],
    before_status: Dict[str, Dict[str, Any]],
    after_status: Dict[str, Dict[str, Any]],
    newly_eligible: Set[str],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for session_id in session_ids:
        parsed_date = session_id.split("|")[1] if "|" in session_id else ""
        if session_id in after_candidates:
            bucket = "AFTER_2024-05-20"
            event_count = after_candidates[session_id]
        elif session_id in before_candidates:
            bucket = "BEFORE_2024-05-08"
            event_count = before_candidates[session_id]
        else:
            bucket = "BASELINE_REFERENCE"
            event_count = 0
        info_before = before_status.get(session_id, {})
        info_after = after_status.get(session_id, {})
        rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "repair_version": REPAIR_VERSION,
                "repair_run_id": repair_run_id,
                "session_id": session_id,
                "session_date": parsed_date or _norm(info_after.get("session_date")) or _norm(info_before.get("session_date")),
                "search_bucket": bucket,
                "event_candidate_present": "TRUE" if event_count else "FALSE",
                "event_candidate_count": event_count,
                "used_by_pilot_or_tier1": "TRUE" if session_id in used_sessions else "FALSE",
                "status_before": _status_label(session_id, before_status, used_sessions),
                "reason_before": _reason_label(session_id, before_status),
                "missing_fields_before": "|".join(info_before.get("missing_fields", [])),
                "missing_reasons_before": "|".join(info_before.get("missing_reasons", [])),
                "repaired_this_run": "TRUE" if session_id in after_candidates or session_id in before_candidates else "FALSE",
                "status_after": _status_label(session_id, after_status, used_sessions),
                "reason_after": _reason_label(session_id, after_status),
                "missing_fields_after": "|".join(info_after.get("missing_fields", [])),
                "missing_reasons_after": "|".join(info_after.get("missing_reasons", [])),
                "became_additional_eligible_unused": "TRUE" if session_id in newly_eligible else "FALSE",
                "notes": "",
            }
        )
    return rows


def _write_audit_rows(service, rows: Sequence[Dict[str, Any]]) -> None:
    headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_AUDIT_SHEET, AUDIT_HEADERS)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_AUDIT_SHEET, headers, rows)


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repair Tier 2 execution plan session eligibility by widening deterministic shadow-pack session coverage.")
    return parser.parse_args(argv)


def build_pack_behavior_tier2_session_eligibility_repair_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    args = args or _parse_args()
    generated_ts = _iso_now()
    repair_run_id = _repair_run_id(generated_ts)

    service = build_sheets_service(load_credentials())
    event_rows = _sheet_to_rows(service, MAIN_SPREADSHEET_ID, INPUT_EVENT)
    if not event_rows:
        raise RuntimeError("Event sheet is missing or empty.")

    pilot_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, INPUT_PILOT_SUMMARY)
    tier1_runs = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, INPUT_TIER1_RUNS)
    tier1_summary = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, INPUT_TIER1_SUMMARY)
    used_sessions = _used_sessions(pilot_rows, tier1_runs, tier1_summary)

    shadow_summary_rows_before = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, INPUT_SHADOW_SUMMARY)
    shadow_run_id_before = _latest_run_id(shadow_summary_rows_before, "shadow_pack_run_id")
    shadow_rows_before_all = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, INPUT_SHADOW)
    shadow_rows_before = [
        row for row in shadow_rows_before_all if not shadow_run_id_before or _norm(row.get("shadow_pack_run_id")) == shadow_run_id_before
    ]
    shadow_status_before = _shadow_status_by_session(shadow_rows_before)
    eligible_unused_before = _eligible_unused_sessions(shadow_status_before, used_sessions)

    window = _build_replay_window(service)
    after_candidates = _candidate_sessions(event_rows, window, AFTER_SEARCH_FROM, AFTER_SEARCH_TO)
    before_candidates = _candidate_sessions(event_rows, window, BEFORE_SEARCH_FROM, BEFORE_SEARCH_TO)

    repair_from = USED_SESSION_FLOOR
    repair_to = AFTER_SEARCH_TO
    session_rows, member_rows, session_summary = _daily_market_session_rows(
        generated_ts,
        event_rows,
        window,
        _parse_date(repair_from),
        _parse_date(repair_to),
    )
    _write_market_session_shadow(service, generated_ts, window, session_rows, member_rows, session_summary, repair_from, repair_to)

    shadow_result = build_market_state_pack_shadow_v0()
    shadow_summary_rows_after = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, INPUT_SHADOW_SUMMARY)
    shadow_run_id_after = _latest_run_id(shadow_summary_rows_after, "shadow_pack_run_id")
    shadow_rows_after_all = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, INPUT_SHADOW)
    shadow_rows_after = [
        row for row in shadow_rows_after_all if not shadow_run_id_after or _norm(row.get("shadow_pack_run_id")) == shadow_run_id_after
    ]
    shadow_status_after = _shadow_status_by_session(shadow_rows_after)
    eligible_unused_after = _eligible_unused_sessions(shadow_status_after, used_sessions)

    used_or_reference = sorted(
        used_sessions
        | set(eligible_unused_before)
        | set(after_candidates)
        | {
            "US|2024-05-18|CUSTOM_CONFIG_WINDOW",
            "US|2024-05-19|CUSTOM_CONFIG_WINDOW",
        }
    )
    before_search_used = False
    if len(eligible_unused_after) < MIN_ELIGIBLE_UNUSED_SESSIONS:
        before_search_used = True
        repair_from = BEFORE_SEARCH_FROM
        session_rows, member_rows, session_summary = _daily_market_session_rows(
            generated_ts,
            event_rows,
            window,
            _parse_date(repair_from),
            _parse_date(repair_to),
        )
        _write_market_session_shadow(service, generated_ts, window, session_rows, member_rows, session_summary, repair_from, repair_to)
        shadow_result = build_market_state_pack_shadow_v0()
        shadow_summary_rows_after = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, INPUT_SHADOW_SUMMARY)
        shadow_run_id_after = _latest_run_id(shadow_summary_rows_after, "shadow_pack_run_id")
        shadow_rows_after_all = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, INPUT_SHADOW)
        shadow_rows_after = [
            row for row in shadow_rows_after_all if not shadow_run_id_after or _norm(row.get("shadow_pack_run_id")) == shadow_run_id_after
        ]
        shadow_status_after = _shadow_status_by_session(shadow_rows_after)
        eligible_unused_after = _eligible_unused_sessions(shadow_status_after, used_sessions)
        used_or_reference = sorted(used_or_reference | set(before_candidates))

    plan_result = build_pack_behavior_tier2_execution_plan_v0()

    newly_eligible = set(eligible_unused_after) - set(eligible_unused_before)
    audit_rows = _audit_rows(
        generated_ts,
        repair_run_id,
        used_or_reference,
        after_candidates,
        before_candidates if before_search_used else {},
        used_sessions,
        shadow_status_before,
        shadow_status_after,
        newly_eligible,
    )
    _write_audit_rows(service, audit_rows)

    return {
        "repair_run_id": repair_run_id,
        "build_status": _norm(plan_result.get("build_status")),
        "final_interpretation": _norm(plan_result.get("final_interpretation")),
        "eligible_unused_before": eligible_unused_before,
        "eligible_unused_after": eligible_unused_after,
        "newly_eligible_unused": sorted(newly_eligible),
        "after_candidates": sorted(after_candidates),
        "before_candidates": sorted(before_candidates),
        "before_search_used": before_search_used,
        "shadow_result": shadow_result,
        "plan_result": plan_result,
        "audit_rows_written": len(audit_rows),
    }


def main() -> None:
    result = build_pack_behavior_tier2_session_eligibility_repair_v0()
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
