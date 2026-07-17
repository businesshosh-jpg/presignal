import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_market_sessions_shadow_v0 import (
    DIAGNOSTICS_SPREADSHEET_ID,
    MAIN_SPREADSHEET_ID,
    PROJECT_OVERVIEWS_SPREADSHEET_ID,
    REGISTRY_HEADERS,
    REGISTRY_SHEET,
    _as_bool,
    _column_letter,
    _ensure_sheet,
    _join_unique,
    _norm,
    _parse_dt,
    _session_local_date,
    _sheet_to_rows,
    _write_rows,
)
from automation.google_clients import batch_update_values, build_sheets_service, get_sheet_values, load_credentials


SOURCE_EVENT_SHEET = "Event"
PHASE1_SESSION_SHEET = "Market_Sessions"
PHASE1_MEMBER_SHEET = "Market_Session_Members"
PHASE1_SUMMARY_SHEET = "Market_Session_Shadow_Summary"

OUTPUT_AUDIT_SHEET = "Market_Session_Shadow_Sanity_Audit"
OUTPUT_SUMMARY_SHEET = "Market_Session_Shadow_Sanity_Summary"

SCHEMA_VERSION = "presignal_v2_market_session_0.1"
SHADOW_VERSION = "shadow_v0"
REGISTRY_CATEGORY = "PRESIGNAL_V2_MARKET_SESSION"
REGISTRY_OWNER_MODULE = "market_session"

AUDIT_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "check_group",
    "check_name",
    "check_status",
    "severity",
    "scope_type",
    "scope_id",
    "session_id",
    "session_date",
    "country",
    "session_window_name",
    "expected_value",
    "actual_value",
    "evidence",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "build_status",
    "source_event_rows_read",
    "eligible_source_rows_recomputed",
    "eligible_event_rows_reported",
    "sessions_expected",
    "sessions_actual",
    "member_rows_expected",
    "member_rows_actual",
    "session_id_determinism",
    "member_assignment_uniqueness",
    "window_behavior",
    "registry_correctness",
    "source_sheet_safety",
    "summary_consistency",
    "registry_entries_verified",
    "registry_entries_missing",
    "duplicate_member_assignments",
    "events_assigned_multiple_sessions",
    "events_assigned_zero_sessions",
    "events_outside_window",
    "source_event_sheet",
    "country_filter",
    "session_window_name",
    "window_source",
    "window_timezone",
    "window_from_local",
    "window_to_local",
    "window_from_utc",
    "window_to_utc",
    "phase1_summary_status",
    "phase1_summary_interpretation",
    "governance_status",
    "final_interpretation",
    "notes",
    "sanity_failures",
]


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _safe_int(value: Any) -> int:
    try:
        return int(float(_norm(value) or "0"))
    except Exception:
        return 0


def _parse_local_minute(value: str, tz_name: str) -> Optional[datetime]:
    raw = _norm(value)
    if not raw:
        return None
    try:
        tzinfo = ZoneInfo(tz_name or "UTC")
        return datetime.fromisoformat(raw.replace(" ", "T")).replace(tzinfo=tzinfo).astimezone(timezone.utc)
    except Exception:
        try:
            tzinfo = ZoneInfo(tz_name or "UTC")
            return datetime.strptime(raw, "%Y-%m-%d %H:%M").replace(tzinfo=tzinfo).astimezone(timezone.utc)
        except Exception:
            return None


def _parse_window_from_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
    tz_name = _norm(summary.get("window_timezone")) or "UTC"
    return {
        "country": _upper(summary.get("country_filter")) or "US",
        "session_window_name": _norm(summary.get("session_window_name")) or "FULL_WINDOW",
        "window_source": _norm(summary.get("window_source")) or "unknown",
        "window_timezone": tz_name,
        "window_from_local": _norm(summary.get("window_from_local")),
        "window_to_local": _norm(summary.get("window_to_local")),
        "window_from_utc": _norm(summary.get("window_from_utc")),
        "window_to_utc": _norm(summary.get("window_to_utc")),
        "window_from_dt": _parse_dt(summary.get("window_from_utc")),
        "window_to_dt": _parse_dt(summary.get("window_to_utc")),
    }


def _window_allows_row(row: Dict[str, Any], window: Dict[str, Any]) -> bool:
    country = _upper(row.get("country"))
    release_dt = _parse_dt(row.get("release_ts"))
    if not country or release_dt is None:
        return False
    if window["country"] and window["country"] != "ALL" and country != window["country"]:
        return False
    lo = window["window_from_dt"]
    hi = window["window_to_dt"]
    if lo and hi and not (lo <= release_dt < hi):
        return False
    return True


def _eligible_source_rows(rows: Sequence[Dict[str, Any]], window: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    counts = Counter()
    eligible: List[Dict[str, Any]] = []
    for row in rows:
        event_id = _norm(row.get("event_id"))
        type_name = _norm(row.get("type"))
        country = _norm(row.get("country"))
        indicator_name = _norm(row.get("indicator_name"))
        release_dt = _parse_dt(row.get("release_ts"))

        if not event_id:
            counts["missing_event_id"] += 1
            continue
        if not release_dt:
            counts["missing_release_ts"] += 1
            continue
        if not country:
            counts["missing_country"] += 1
            continue
        if not indicator_name:
            counts["missing_indicator_name"] += 1
            continue
        if not type_name:
            counts["missing_type"] += 1
            continue
        if not _window_allows_row(row, window):
            counts["outside_window"] += 1
            continue
        eligible.append(row)
    eligible.sort(
        key=lambda row: (
            _parse_dt(row.get("release_ts")) or datetime.max.replace(tzinfo=timezone.utc),
            _upper(row.get("country")),
            _norm(row.get("indicator_name")),
            _norm(row.get("event_id")),
        )
    )
    return eligible, dict(counts)


def _recompute_expected_sessions(eligible_rows: Sequence[Dict[str, Any]], window: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in eligible_rows:
        grouped[_upper(row.get("country"))].append(row)

    expected: Dict[str, Dict[str, Any]] = {}
    for country in sorted(grouped):
        members = grouped[country]
        first_release_dt = _parse_dt(members[0].get("release_ts"))
        session_date = _session_local_date(first_release_dt, window["window_timezone"]) if first_release_dt else ""
        session_id = f"{country}|{session_date}|{window['session_window_name']}"
        expected[session_id] = {
            "session_id": session_id,
            "country": country,
            "session_date": session_date,
            "session_window_name": window["session_window_name"],
            "session_start_ts": _norm(members[0].get("release_ts")),
            "session_end_ts": _norm(members[-1].get("release_ts")),
            "primary_release_ts": _norm(members[0].get("release_ts")),
            "last_release_ts": _norm(members[-1].get("release_ts")),
            "member_event_ids": [ _norm(r.get("event_id")) for r in members ],
            "member_indicator_names": [ _norm(r.get("indicator_name")) for r in members ],
            "member_release_ts": [ _norm(r.get("release_ts")) for r in members ],
            "member_count": len(members),
        }
    return expected


def _read_phase1_summary(service) -> Dict[str, Any]:
    rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, PHASE1_SUMMARY_SHEET)
    return rows[0] if rows else {}


def _read_phase1_outputs(service) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    session_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, PHASE1_SESSION_SHEET)
    member_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, PHASE1_MEMBER_SHEET)
    return session_rows, member_rows


def _read_registry_rows(service) -> List[Dict[str, Any]]:
    return _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)


def _upsert_registry_rows(service) -> Dict[str, Any]:
    headers = _ensure_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    by_id = {(_upper(row.get("logical_sheet_id"))): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {(_upper(row.get("logical_sheet_id"))): row for row in rows}
    updates = []
    appended = 0
    registry_rows = [
        {
            "logical_sheet_id": "MARKET_SESSIONS",
            "physical_sheet_name": PHASE1_SESSION_SHEET,
            "workbook": "DIAGNOSTICS",
            "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
            "category": REGISTRY_CATEGORY,
            "lifecycle_state": "ACTIVE",
            "owner_module": REGISTRY_OWNER_MODULE,
            "participates_in_rebuild": "TRUE",
            "read_only": "FALSE",
            "allow_creation": "TRUE",
            "created_phase": "PreSignal v2.0 Phase 1",
            "notes": "shadow_v0 derived-only market-session grouping layer",
        },
        {
            "logical_sheet_id": "MARKET_SESSION_MEMBERS",
            "physical_sheet_name": PHASE1_MEMBER_SHEET,
            "workbook": "DIAGNOSTICS",
            "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
            "category": REGISTRY_CATEGORY,
            "lifecycle_state": "ACTIVE",
            "owner_module": REGISTRY_OWNER_MODULE,
            "participates_in_rebuild": "TRUE",
            "read_only": "FALSE",
            "allow_creation": "TRUE",
            "created_phase": "PreSignal v2.0 Phase 1",
            "notes": "shadow_v0 derived-only market-session member mapping",
        },
        {
            "logical_sheet_id": "MARKET_SESSION_SHADOW_SUMMARY",
            "physical_sheet_name": PHASE1_SUMMARY_SHEET,
            "workbook": "DIAGNOSTICS",
            "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
            "category": REGISTRY_CATEGORY,
            "lifecycle_state": "ACTIVE",
            "owner_module": REGISTRY_OWNER_MODULE,
            "participates_in_rebuild": "TRUE",
            "read_only": "FALSE",
            "allow_creation": "TRUE",
            "created_phase": "PreSignal v2.0 Phase 1",
            "notes": "shadow_v0 derived-only market-session build summary",
        },
        {
            "logical_sheet_id": "MARKET_SESSION_SHADOW_SANITY_AUDIT",
            "physical_sheet_name": OUTPUT_AUDIT_SHEET,
            "workbook": "DIAGNOSTICS",
            "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
            "category": REGISTRY_CATEGORY,
            "lifecycle_state": "ACTIVE",
            "owner_module": REGISTRY_OWNER_MODULE,
            "participates_in_rebuild": "TRUE",
            "read_only": "FALSE",
            "allow_creation": "TRUE",
            "created_phase": "PreSignal v2.0 Phase 1 Sanity Audit",
            "notes": "Derived-only market-session sanity audit",
        },
        {
            "logical_sheet_id": "MARKET_SESSION_SHADOW_SANITY_SUMMARY",
            "physical_sheet_name": OUTPUT_SUMMARY_SHEET,
            "workbook": "DIAGNOSTICS",
            "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
            "category": REGISTRY_CATEGORY,
            "lifecycle_state": "ACTIVE",
            "owner_module": REGISTRY_OWNER_MODULE,
            "participates_in_rebuild": "TRUE",
            "read_only": "FALSE",
            "allow_creation": "TRUE",
            "created_phase": "PreSignal v2.0 Phase 1 Sanity Audit",
            "notes": "Derived-only market-session sanity summary",
        },
    ]

    for row in registry_rows:
        key = _upper(row["logical_sheet_id"])
        existing = existing_by_id.get(key, {})
        merged = dict(row)
        merged["registry_created_ts"] = _norm(existing.get("registry_created_ts")) or now
        merged["registry_last_verified_ts"] = now
        merged["registry_migration_ts"] = _norm(existing.get("registry_migration_ts"))
        merged["registry_rename_ts"] = _norm(existing.get("registry_rename_ts"))
        values = [merged.get(header, "") for header in headers]
        if key in by_id:
            row_number = by_id[key]
        else:
            appended += 1
            row_number = len(rows) + appended
        updates.append(
            {
                "range": f"'{REGISTRY_SHEET}'!A{row_number}:{_column_letter(len(headers))}{row_number}",
                "values": [values],
            }
        )

    if updates:
        batch_update_values(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, updates)

    return {"updated": len(registry_rows) - appended, "appended": appended}


def _registry_lookup(rows: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return { _upper(row.get("logical_sheet_id")): row for row in rows }


def _build_audit_rows(
    generated_ts: str,
    window: Dict[str, Any],
    source_rows: Sequence[Dict[str, Any]],
    eligible_rows: Sequence[Dict[str, Any]],
    expected_sessions: Dict[str, Dict[str, Any]],
    actual_sessions: Sequence[Dict[str, Any]],
    actual_members: Sequence[Dict[str, Any]],
    summary: Dict[str, Any],
    registry_rows: Sequence[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    audit_rows: List[Dict[str, Any]] = []
    check_status = {
        "session_id_determinism": "PASS",
        "member_assignment_uniqueness": "PASS",
        "window_behavior": "PASS",
        "registry_correctness": "PASS",
        "source_sheet_safety": "PASS",
        "summary_consistency": "PASS",
    }
    failures: List[str] = []

    actual_session_map = { _norm(row.get("session_id")): row for row in actual_sessions }
    actual_member_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in actual_members:
        actual_member_map[_norm(row.get("session_id"))].append(row)
    for rows in actual_member_map.values():
        rows.sort(key=lambda row: _safe_int(row.get("member_order")))

    # Session determinism and per-session membership
    for session_id in sorted(expected_sessions):
        expected = expected_sessions[session_id]
        actual = actual_session_map.get(session_id, {})
        members = actual_member_map.get(session_id, [])
        expected_event_ids = expected["member_event_ids"]
        actual_event_ids = [ _norm(row.get("event_id")) for row in members ]
        expected_release_ts = expected["member_release_ts"]
        actual_release_ts = [ _norm(row.get("release_ts")) for row in members ]

        status = "PASS"
        notes = []
        if _norm(actual.get("session_id")) != session_id:
            status = "FAIL"
            notes.append("session_id_mismatch")
        if _norm(actual.get("session_date")) != expected["session_date"]:
            status = "FAIL"
            notes.append("session_date_mismatch")
        if _norm(actual.get("country")) != expected["country"]:
            status = "FAIL"
            notes.append("country_mismatch")
        if _norm(actual.get("session_window_name")) != expected["session_window_name"]:
            status = "FAIL"
            notes.append("window_name_mismatch")
        if _norm(actual.get("member_event_count")) != str(expected["member_count"]):
            status = "FAIL"
            notes.append("member_count_mismatch")
        if _norm(actual.get("primary_release_ts")) != expected["primary_release_ts"]:
            status = "FAIL"
            notes.append("primary_release_ts_mismatch")
        if _norm(actual.get("last_release_ts")) != expected["last_release_ts"]:
            status = "FAIL"
            notes.append("last_release_ts_mismatch")
        if actual_event_ids != expected_event_ids:
            status = "FAIL"
            notes.append("member_event_ids_mismatch")
        if actual_release_ts != expected_release_ts:
            status = "FAIL"
            notes.append("member_release_ts_mismatch")

        audit_rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "shadow_version": SHADOW_VERSION,
                "check_group": "SESSION_ID_DETERMINISM",
                "check_name": "EXPECTED_SESSION_ID_MATCH",
                "check_status": status,
                "severity": "FAIL" if status == "FAIL" else "PASS",
                "scope_type": "session",
                "scope_id": session_id,
                "session_id": session_id,
                "session_date": expected["session_date"],
                "country": expected["country"],
                "session_window_name": expected["session_window_name"],
                "expected_value": expected["session_id"],
                "actual_value": _norm(actual.get("session_id")),
                "evidence": f"member_count={expected['member_count']}|actual_member_count={_norm(actual.get('member_event_count'))}|member_order={_join_unique([row.get('member_order') for row in members])}",
                "notes": ";".join(notes),
            }
        )
        if status == "FAIL":
            check_status["session_id_determinism"] = "FAIL"
            failures.append("session_id_determinism")

        # Member assignment uniqueness per session.
        session_duplicate_pairs = Counter((row.get("session_id"), row.get("event_id")) for row in members)
        duplicate_pairs = sum(count - 1 for count in session_duplicate_pairs.values() if count > 1)
        session_multi_session_events = 0
        for event_id in expected_event_ids:
            sessions = {_norm(row.get("session_id")) for row in actual_members if _norm(row.get("event_id")) == event_id}
            if len(sessions) > 1:
                session_multi_session_events += 1
        missing_events = [event_id for event_id in expected_event_ids if event_id not in actual_event_ids]
        extra_events = [event_id for event_id in actual_event_ids if event_id not in expected_event_ids]
        status = "PASS" if duplicate_pairs == 0 and session_multi_session_events == 0 and not missing_events and not extra_events else "FAIL"
        if status == "FAIL":
            check_status["member_assignment_uniqueness"] = "FAIL"
            failures.append("member_assignment_uniqueness")
        audit_rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "shadow_version": SHADOW_VERSION,
                "check_group": "MEMBER_ASSIGNMENT_UNIQUENESS",
                "check_name": "SESSION_MEMBER_MAPPING",
                "check_status": status,
                "severity": "FAIL" if status == "FAIL" else "PASS",
                "scope_type": "session",
                "scope_id": session_id,
                "session_id": session_id,
                "session_date": expected["session_date"],
                "country": expected["country"],
                "session_window_name": expected["session_window_name"],
                "expected_value": str(expected["member_count"]),
                "actual_value": str(len(members)),
                "evidence": f"duplicate_pairs={duplicate_pairs}|multi_session_events={session_multi_session_events}|missing={_join_unique(missing_events)}|extra={_join_unique(extra_events)}",
                "notes": "",
            }
        )

        # Window behavior per session.
        window_violations = []
        for row in members:
            if not _window_allows_row(row, window):
                window_violations.append(_norm(row.get("event_id")))
        status = "PASS" if not window_violations else "FAIL"
        if status == "FAIL":
            check_status["window_behavior"] = "FAIL"
            failures.append("window_behavior")
        audit_rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "shadow_version": SHADOW_VERSION,
                "check_group": "WINDOW_BEHAVIOR",
                "check_name": "SESSION_WINDOW_FILTER",
                "check_status": status,
                "severity": "FAIL" if status == "FAIL" else "PASS",
                "scope_type": "session",
                "scope_id": session_id,
                "session_id": session_id,
                "session_date": expected["session_date"],
                "country": expected["country"],
                "session_window_name": expected["session_window_name"],
                "expected_value": f"{window['window_from_utc']}..{window['window_to_utc']}" if window["window_from_utc"] or window["window_to_utc"] else "FULL_WINDOW",
                "actual_value": str(len(members)),
                "evidence": f"violations={_join_unique(window_violations)}|session_start={_norm(actual.get('session_start_ts'))}|session_end={_norm(actual.get('session_end_ts'))}",
                "notes": "",
            }
        )

    # Registry correctness.
    registry_map = _registry_lookup(registry_rows)
    required_registry = {
        "MARKET_SESSIONS": PHASE1_SESSION_SHEET,
        "MARKET_SESSION_MEMBERS": PHASE1_MEMBER_SHEET,
        "MARKET_SESSION_SHADOW_SUMMARY": PHASE1_SUMMARY_SHEET,
        "MARKET_SESSION_SHADOW_SANITY_AUDIT": OUTPUT_AUDIT_SHEET,
        "MARKET_SESSION_SHADOW_SANITY_SUMMARY": OUTPUT_SUMMARY_SHEET,
    }
    registry_missing = []
    for logical_id, physical_name in required_registry.items():
        row = registry_map.get(logical_id)
        status = "PASS"
        actual_value = ""
        evidence = ""
        if not row:
            status = "FAIL"
            actual_value = "MISSING"
            registry_missing.append(logical_id)
        else:
            actual_value = _norm(row.get("physical_sheet_name"))
            mismatches = []
            if _upper(row.get("workbook")) != "DIAGNOSTICS":
                mismatches.append("workbook")
            if _norm(row.get("physical_sheet_name")) != physical_name:
                mismatches.append("physical_sheet_name")
            if _upper(row.get("category")) != REGISTRY_CATEGORY:
                mismatches.append("category")
            if _upper(row.get("lifecycle_state")) != "ACTIVE":
                mismatches.append("lifecycle_state")
            if _norm(row.get("owner_module")) != REGISTRY_OWNER_MODULE:
                mismatches.append("owner_module")
            if _upper(row.get("participates_in_rebuild")) != "TRUE":
                mismatches.append("participates_in_rebuild")
            if _upper(row.get("read_only")) != "FALSE":
                mismatches.append("read_only")
            if not mismatches:
                evidence = f"workbook={_norm(row.get('workbook'))}|category={_norm(row.get('category'))}|owner={_norm(row.get('owner_module'))}"
            else:
                status = "FAIL"
                evidence = f"mismatch={_join_unique(mismatches)}"
                registry_missing.append(logical_id)
        audit_rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "shadow_version": SHADOW_VERSION,
                "check_group": "REGISTRY_CORRECTNESS",
                "check_name": "REGISTRY_ENTRY_MATCH",
                "check_status": status,
                "severity": "FAIL" if status == "FAIL" else "PASS",
                "scope_type": "registry",
                "scope_id": logical_id,
                "session_id": "",
                "session_date": "",
                "country": "",
                "session_window_name": "",
                "expected_value": physical_name,
                "actual_value": actual_value,
                "evidence": evidence,
                "notes": "",
            }
        )
        if status == "FAIL":
            check_status["registry_correctness"] = "FAIL"
            failures.append("registry_correctness")

    # Source-sheet safety.
    source_sheet_values = {_norm(row.get("source_sheet")) for row in actual_members if _norm(row.get("source_sheet"))}
    source_sheet_values.update({_norm(row.get("source_event_sheet")) for row in actual_sessions if _norm(row.get("source_event_sheet"))})
    source_row_numbers_ok = all(_safe_int(row.get("source_row_number")) > 0 for row in actual_members)
    status = "PASS" if source_sheet_values == {SOURCE_EVENT_SHEET} and source_row_numbers_ok else "FAIL"
    if status == "FAIL":
        check_status["source_sheet_safety"] = "FAIL"
        failures.append("source_sheet_safety")
    audit_rows.append(
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "shadow_version": SHADOW_VERSION,
            "check_group": "SOURCE_SHEET_SAFETY",
            "check_name": "SOURCE_SHEET_MARKERS",
            "check_status": status,
            "severity": "FAIL" if status == "FAIL" else "PASS",
            "scope_type": "build",
            "scope_id": "phase1_outputs",
            "session_id": "",
            "session_date": "",
            "country": "",
            "session_window_name": "",
            "expected_value": SOURCE_EVENT_SHEET,
            "actual_value": _join_unique(source_sheet_values),
            "evidence": f"source_row_numbers_ok={'TRUE' if source_row_numbers_ok else 'FALSE'}|member_rows={len(actual_members)}|session_rows={len(actual_sessions)}",
            "notes": "",
        }
    )

    # Summary consistency against the phase1 summary row and recomputed counts.
    recomputed_outside_window = _safe_int(summary.get("outside_window"))
    recomputed_missing_event_id = _safe_int(summary.get("missing_event_id"))
    recomputed_missing_release_ts = _safe_int(summary.get("missing_release_ts"))
    recomputed_missing_country = _safe_int(summary.get("missing_country"))
    recomputed_missing_indicator_name = _safe_int(summary.get("missing_indicator_name"))
    recomputed_missing_type = _safe_int(summary.get("missing_type"))
    eligible_expected = len(eligible_rows)
    session_expected = len(expected_sessions)
    member_expected = len(eligible_rows)

    summary_mismatches = []
    summary_checks = [
        ("source_event_rows_read", _safe_int(summary.get("source_event_rows_read")), len(source_rows)),
        ("eligible_event_rows", _safe_int(summary.get("eligible_event_rows")), eligible_expected),
        ("sessions_built", _safe_int(summary.get("sessions_built")), session_expected),
        ("session_member_rows_written", _safe_int(summary.get("session_member_rows_written")), member_expected),
        ("events_missing_event_id", _safe_int(summary.get("events_missing_event_id")), recomputed_missing_event_id),
        ("events_missing_release_ts", _safe_int(summary.get("events_missing_release_ts")), recomputed_missing_release_ts),
        ("events_missing_country", _safe_int(summary.get("events_missing_country")), recomputed_missing_country),
        ("events_missing_indicator_name", _safe_int(summary.get("events_missing_indicator_name")), recomputed_missing_indicator_name),
        ("events_missing_type", _safe_int(summary.get("events_missing_type")), recomputed_missing_type),
        ("events_outside_window", _safe_int(summary.get("events_outside_window")), recomputed_outside_window),
    ]
    for field, actual, expected in summary_checks:
        if actual != expected:
            summary_mismatches.append(f"{field}:{actual}!={expected}")
    status = "PASS" if not summary_mismatches else "FAIL"
    if status == "FAIL":
        check_status["summary_consistency"] = "FAIL"
        failures.append("summary_consistency")
    audit_rows.append(
        {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "shadow_version": SHADOW_VERSION,
            "check_group": "SUMMARY_CONSISTENCY",
            "check_name": "PHASE1_SUMMARY_MATCH",
            "check_status": status,
            "severity": "FAIL" if status == "FAIL" else "PASS",
            "scope_type": "build",
            "scope_id": "phase1_summary",
            "session_id": "",
            "session_date": "",
            "country": window["country"],
            "session_window_name": window["session_window_name"],
            "expected_value": f"eligible={eligible_expected}|sessions={session_expected}|members={member_expected}",
            "actual_value": f"eligible={_safe_int(summary.get('eligible_event_rows'))}|sessions={_safe_int(summary.get('sessions_built'))}|members={_safe_int(summary.get('session_member_rows_written'))}",
            "evidence": "|".join(summary_mismatches) if summary_mismatches else "summary_counts_match",
            "notes": f"phase1_status={_norm(summary.get('build_status'))}|phase1_interpretation={_norm(summary.get('final_interpretation'))}",
        }
    )

    build_status = "PASS" if not failures else "REVIEW_NEEDED"
    final_interpretation = "MARKET_SESSION_SANITY_READY" if build_status == "PASS" else "MARKET_SESSION_SANITY_NEEDS_REVIEW"
    return audit_rows, {
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "check_status": check_status,
        "failures": failures,
        "registry_missing": registry_missing,
        "recomputed_outside_window": recomputed_outside_window,
        "recomputed_missing_event_id": recomputed_missing_event_id,
        "recomputed_missing_release_ts": recomputed_missing_release_ts,
        "recomputed_missing_country": recomputed_missing_country,
        "recomputed_missing_indicator_name": recomputed_missing_indicator_name,
        "recomputed_missing_type": recomputed_missing_type,
        "eligible_expected": eligible_expected,
        "session_expected": session_expected,
        "member_expected": member_expected,
    }


def build_market_sessions_shadow_sanity_audit() -> Dict[str, Any]:
    service = build_sheets_service(load_credentials(interactive=False))
    generated_ts = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    summary = _read_phase1_summary(service)
    session_rows, member_rows = _read_phase1_outputs(service)
    source_rows = _sheet_to_rows(service, MAIN_SPREADSHEET_ID, SOURCE_EVENT_SHEET)

    if not summary:
        raise RuntimeError(f"Missing required sheet or data: {PHASE1_SUMMARY_SHEET}")
    window = _parse_window_from_summary(summary)
    eligible_rows, counts = _eligible_source_rows(source_rows, window)
    expected_sessions = _recompute_expected_sessions(eligible_rows, window)
    registry_result = _upsert_registry_rows(service)
    registry_rows = _read_registry_rows(service)

    audit_rows, meta = _build_audit_rows(
        generated_ts,
        window,
        source_rows,
        eligible_rows,
        expected_sessions,
        session_rows,
        member_rows,
        {**summary, **counts},
        registry_rows,
    )

    audit_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_AUDIT_SHEET, AUDIT_HEADERS)
    summary_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_AUDIT_SHEET, audit_headers, audit_rows)

    registry_entries_missing = len(meta["registry_missing"])
    summary_row = {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "shadow_version": SHADOW_VERSION,
        "build_status": meta["build_status"],
        "source_event_rows_read": len(source_rows),
        "eligible_source_rows_recomputed": len(eligible_rows),
        "eligible_event_rows_reported": _safe_int(summary.get("eligible_event_rows")),
        "sessions_expected": len(expected_sessions),
        "sessions_actual": len(session_rows),
        "member_rows_expected": len(eligible_rows),
        "member_rows_actual": len(member_rows),
        "session_id_determinism": meta["check_status"]["session_id_determinism"],
        "member_assignment_uniqueness": meta["check_status"]["member_assignment_uniqueness"],
        "window_behavior": meta["check_status"]["window_behavior"],
        "registry_correctness": meta["check_status"]["registry_correctness"],
        "source_sheet_safety": meta["check_status"]["source_sheet_safety"],
        "summary_consistency": meta["check_status"]["summary_consistency"],
        "registry_entries_verified": 5 - registry_entries_missing,
        "registry_entries_missing": registry_entries_missing,
        "duplicate_member_assignments": sum(
            count - 1 for count in Counter((row.get("session_id"), row.get("event_id")) for row in member_rows).values() if count > 1
        ),
        "events_assigned_multiple_sessions": sum(
            1
            for event_id in {_norm(row.get("event_id")) for row in member_rows if _norm(row.get("event_id"))}
            if len({_norm(row.get("session_id")) for row in member_rows if _norm(row.get("event_id")) == event_id}) > 1
        ),
        "events_assigned_zero_sessions": max(0, len(eligible_rows) - len(member_rows)),
        "events_outside_window": meta["recomputed_outside_window"],
        "source_event_sheet": SOURCE_EVENT_SHEET,
        "country_filter": window["country"],
        "session_window_name": window["session_window_name"],
        "window_source": window["window_source"],
        "window_timezone": window["window_timezone"],
        "window_from_local": window["window_from_local"],
        "window_to_local": window["window_to_local"],
        "window_from_utc": window["window_from_utc"],
        "window_to_utc": window["window_to_utc"],
        "phase1_summary_status": _norm(summary.get("build_status")),
        "phase1_summary_interpretation": _norm(summary.get("final_interpretation")),
        "governance_status": "DERIVED_ONLY_SHADOW_SAFE",
        "final_interpretation": meta["final_interpretation"],
        "notes": "post-phase1 sanity audit; derived-only; no AI calls; no operational sheets modified",
        "sanity_failures": "|".join(meta["failures"]),
    }
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, [summary_row])

    return {
        "generated_ts": generated_ts,
        "build_status": meta["build_status"],
        "final_interpretation": meta["final_interpretation"],
        "checks": meta["check_status"],
        "source_event_rows_read": len(source_rows),
        "eligible_source_rows_recomputed": len(eligible_rows),
        "sessions_expected": len(expected_sessions),
        "sessions_actual": len(session_rows),
        "member_rows_expected": len(eligible_rows),
        "member_rows_actual": len(member_rows),
        "registry_result": registry_result,
        "registry_entries_missing": meta["registry_missing"],
        "window": window,
    }


def main() -> None:
    print(build_market_sessions_shadow_sanity_audit())


if __name__ == "__main__":
    main()
