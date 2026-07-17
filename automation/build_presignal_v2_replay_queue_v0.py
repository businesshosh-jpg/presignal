import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
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
    _column_letter,
    _ensure_sheet,
    _norm,
    _parse_dt,
    _read_config_window,
    _sheet_to_rows,
    _write_rows,
)
from automation.build_session_information_requests_v0 import _iso_now, _truncate_text
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


EVENT_SHEET = "Event"
OUTPUT_QUEUE_SHEET = "PreSignal_v2_Replay_Queue"
OUTPUT_SUMMARY_SHEET = "PreSignal_v2_Replay_Queue_Summary"

SCHEMA_VERSION = "presignal_v2_replay_queue_0.1"
SHADOW_VERSION = "shadow_v0"
REGISTRY_CATEGORY = "PRESIGNAL_V2_MARKET_SESSION"
REGISTRY_OWNER_MODULE = "market_session"

DEFAULT_COUNTRY = "US"
DEFAULT_ENABLED_PROVIDERS = ("Gemini", "OpenAI", "Anthropic")

QUEUE_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "replay_queue_id",
    "replay_order",
    "session_id",
    "session_date",
    "country",
    "session_window_name",
    "session_start_ts",
    "session_end_ts",
    "member_event_count",
    "member_event_ids",
    "member_indicator_names",
    "earliest_release_ts",
    "latest_release_ts",
    "replay_status",
    "recommended_run_mode",
    "phase1_ready",
    "phase2_requires_provider_calls",
    "phase3_requires_provider_calls",
    "phase4_requires_provider_calls",
    "estimated_provider_call_count",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "replay_queue_id",
    "earliest_event_ts",
    "latest_event_ts",
    "events_read",
    "eligible_events",
    "sessions_queued",
    "sessions_skipped",
    "first_session_id",
    "last_session_id",
    "provider_call_estimate_total",
    "build_status",
    "final_interpretation",
    "notes",
]


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _join_unique(values: Iterable[Any]) -> str:
    seen = set()
    out: List[str] = []
    for value in values:
        text = _norm(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return "|".join(out)


def _require_headers(sheet_name: str, rows: Sequence[Dict[str, Any]], headers: Sequence[str]) -> None:
    if not rows:
        raise RuntimeError(f"{sheet_name} is missing or empty.")
    missing = [header for header in headers if header not in rows[0]]
    if missing:
        raise RuntimeError(f"{sheet_name} is missing required headers: {', '.join(missing)}")


def _parse_date_arg(value: str) -> datetime:
    dt = datetime.strptime(value, "%Y-%m-%d")
    return dt.replace(tzinfo=timezone.utc)


def _read_config_value_map(service) -> Dict[str, str]:
    return _read_config_window(service)


def _parse_config_local(value: str, tz_name: str) -> Optional[datetime]:
    raw = _norm(value)
    if not raw:
        return None
    try:
        tzinfo = ZoneInfo(tz_name or "UTC")
    except Exception:
        tzinfo = timezone.utc
    try:
        naive = datetime.strptime(raw, "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    return naive.replace(tzinfo=tzinfo)


def _resolve_replay_window(args: argparse.Namespace, config: Dict[str, str]) -> Dict[str, Any]:
    country = _upper(args.country or DEFAULT_COUNTRY) or DEFAULT_COUNTRY
    tz_name = _norm(config.get("WINDOW_TZ")) or "UTC"
    session_window_name = "FULL_WINDOW"
    recurring_enabled = False
    start_minute = 0
    duration_minutes = 24 * 60
    note = "full-day recurring window"

    if _upper(config.get("WINDOW_ENABLED")) == "TRUE":
        start_local = _parse_config_local(_norm(config.get("WINDOW_FROM_LOCAL")), tz_name)
        end_local = _parse_config_local(_norm(config.get("WINDOW_TO_LOCAL")), tz_name)
        if start_local and end_local:
            delta = end_local - start_local
            minutes = int(delta.total_seconds() // 60)
            if minutes <= 0:
                minutes += 24 * 60
            if 0 < minutes <= 48 * 60:
                recurring_enabled = True
                session_window_name = "CUSTOM_CONFIG_WINDOW"
                start_minute = start_local.hour * 60 + start_local.minute
                duration_minutes = minutes
                note = (
                    "recurring window derived from Config WINDOW_FROM_LOCAL/WINDOW_TO_LOCAL; "
                    "calendar dates ignored for historical replay"
                )

    return {
        "country": country,
        "timezone": tz_name,
        "session_window_name": session_window_name,
        "recurring_enabled": recurring_enabled,
        "start_minute": start_minute,
        "duration_minutes": duration_minutes,
        "note": note,
    }


def _eligible_event(row: Dict[str, Any], country_filter: str) -> Tuple[bool, str]:
    if not _norm(row.get("event_id")):
        return False, "missing_event_id"
    if not _norm(row.get("country")):
        return False, "missing_country"
    if country_filter and country_filter != "ALL" and _upper(row.get("country")) != country_filter:
        return False, "filtered_country"
    if not _norm(row.get("indicator_name")):
        return False, "missing_indicator_name"
    if _parse_dt(row.get("release_ts")) is None:
        return False, "missing_release_ts"
    return True, ""


def _session_assignment(release_dt: datetime, window: Dict[str, Any]) -> Tuple[str, datetime, datetime]:
    tz_name = window["timezone"]
    try:
        tzinfo = ZoneInfo(tz_name or "UTC")
    except Exception:
        tzinfo = timezone.utc
    local_dt = release_dt.astimezone(tzinfo)
    if not window["recurring_enabled"]:
        session_date = local_dt.strftime("%Y-%m-%d")
        start_local = local_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = start_local + timedelta(days=1)
        return session_date, start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)

    start_minute = window["start_minute"]
    duration = window["duration_minutes"]
    current_minute = local_dt.hour * 60 + local_dt.minute
    session_start_local = local_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    if current_minute < start_minute:
        session_start_local -= timedelta(days=1)
    session_start_local += timedelta(minutes=start_minute)
    session_end_local = session_start_local + timedelta(minutes=duration)
    session_date = session_start_local.strftime("%Y-%m-%d")
    return session_date, session_start_local.astimezone(timezone.utc), session_end_local.astimezone(timezone.utc)


def _queue_sort_key(row: Dict[str, Any]) -> Tuple[Any, ...]:
    return (
        _parse_dt(row.get("earliest_release_ts")) or datetime.max.replace(tzinfo=timezone.utc),
        _norm(row.get("country")),
        _norm(row.get("session_id")),
    )


def _upsert_registry_rows(service) -> Dict[str, Any]:
    headers = _ensure_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_upper(row.get("logical_sheet_id")): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_upper(row.get("logical_sheet_id")): row for row in rows}
    updates = []
    appended = 0
    registry_rows = [
        {
            "logical_sheet_id": "PRESIGNAL_V2_REPLAY_QUEUE",
            "physical_sheet_name": OUTPUT_QUEUE_SHEET,
            "sheet_role": "v2_replay_queue",
            "workbook": "DIAGNOSTICS",
            "workbook_location": "DIAGNOSTICS",
            "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
            "category": REGISTRY_CATEGORY,
            "lifecycle": "active_shadow",
            "lifecycle_state": "ACTIVE",
            "owner_module": REGISTRY_OWNER_MODULE,
            "participates_in_rebuild": "TRUE",
            "read_only": "FALSE",
            "allow_creation": "TRUE",
            "created_phase": "PreSignal v2.0 Phase 7.5A",
            "notes": "shadow_v0 historical replay queue builder",
        },
        {
            "logical_sheet_id": "PRESIGNAL_V2_REPLAY_QUEUE_SUMMARY",
            "physical_sheet_name": OUTPUT_SUMMARY_SHEET,
            "sheet_role": "v2_replay_queue_summary",
            "workbook": "DIAGNOSTICS",
            "workbook_location": "DIAGNOSTICS",
            "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
            "category": REGISTRY_CATEGORY,
            "lifecycle": "active_shadow",
            "lifecycle_state": "ACTIVE",
            "owner_module": REGISTRY_OWNER_MODULE,
            "participates_in_rebuild": "TRUE",
            "read_only": "FALSE",
            "allow_creation": "TRUE",
            "created_phase": "PreSignal v2.0 Phase 7.5A",
            "notes": "shadow_v0 historical replay queue summary",
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
            row_number = len(rows) + appended + 1
        updates.append(
            {
                "range": f"'{REGISTRY_SHEET}'!A{row_number}:{_column_letter(len(headers))}{row_number}",
                "values": [values],
            }
        )
    if updates:
        batch_update_values(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, updates)
    return {"updated": len(registry_rows) - appended, "appended": appended}


def _build_queue_rows(
    generated_ts: str,
    event_rows: Sequence[Dict[str, Any]],
    window: Dict[str, Any],
    from_dt: Optional[datetime],
    to_dt: Optional[datetime],
    max_sessions: Optional[int],
    dry_run: bool,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    events_read = len(event_rows)
    eligible_events = 0
    skipped_counts = Counter()
    grouped: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    earliest_event_dt: Optional[datetime] = None
    latest_event_dt: Optional[datetime] = None

    valid_events: List[Dict[str, Any]] = []
    for row in event_rows:
        ok, reason = _eligible_event(row, window["country"])
        if not ok:
            skipped_counts[reason] += 1
            continue
        release_dt = _parse_dt(row.get("release_ts"))
        if release_dt is None:
            skipped_counts["missing_release_ts"] += 1
            continue
        valid_events.append(
            {
                "event_id": _norm(row.get("event_id")),
                "country": _upper(row.get("country")),
                "indicator_name": _norm(row.get("indicator_name")),
                "release_dt": release_dt,
            }
        )

    valid_events.sort(key=lambda row: (row["release_dt"], row["country"], row["indicator_name"], row["event_id"]))
    if valid_events and from_dt is None:
        from_dt = valid_events[0]["release_dt"]

    for row in valid_events:
        release_dt = row["release_dt"]
        if from_dt and release_dt < from_dt:
            skipped_counts["before_from_date"] += 1
            continue
        if to_dt and release_dt >= to_dt:
            skipped_counts["after_to_date"] += 1
            continue
        session_date, session_start_ts, session_end_ts = _session_assignment(release_dt, window)
        session_id = f"{row['country']}|{session_date}|{window['session_window_name']}"
        grouped[(session_id, session_date, row["country"])].append(
            {
                "event_id": row["event_id"],
                "indicator_name": row["indicator_name"],
                "release_dt": release_dt,
                "session_start_ts": session_start_ts,
                "session_end_ts": session_end_ts,
            }
        )
        eligible_events += 1
        earliest_event_dt = release_dt if earliest_event_dt is None else min(earliest_event_dt, release_dt)
        latest_event_dt = release_dt if latest_event_dt is None else max(latest_event_dt, release_dt)

    provider_call_count_per_session = len(DEFAULT_ENABLED_PROVIDERS) * 3
    queue_rows: List[Dict[str, Any]] = []
    seen_session_ids = set()
    ordered_sessions = sorted(
        grouped.items(),
        key=lambda item: (
            min(member["release_dt"] for member in item[1]),
            item[0][2],
            item[0][0],
        ),
    )

    for index, ((session_id, session_date, country), members) in enumerate(ordered_sessions, start=1):
        if max_sessions is not None and len(queue_rows) >= max_sessions:
            skipped_counts["over_max_sessions"] += 1
            continue
        if session_id in seen_session_ids:
            skipped_counts["duplicate_session"] += 1
            queue_rows.append(
                {
                    "generated_ts": generated_ts,
                    "schema_version": SCHEMA_VERSION,
                    "shadow_version": SHADOW_VERSION,
                    "replay_queue_id": "",
                    "replay_order": "",
                    "session_id": session_id,
                    "session_date": session_date,
                    "country": country,
                    "session_window_name": window["session_window_name"],
                    "session_start_ts": "",
                    "session_end_ts": "",
                    "member_event_count": len(members),
                    "member_event_ids": _join_unique(member["event_id"] for member in members),
                    "member_indicator_names": _join_unique(member["indicator_name"] for member in members),
                    "earliest_release_ts": "",
                    "latest_release_ts": "",
                    "replay_status": "SKIP_DUPLICATE_SESSION",
                    "recommended_run_mode": "skip",
                    "phase1_ready": "FALSE",
                    "phase2_requires_provider_calls": "FALSE",
                    "phase3_requires_provider_calls": "FALSE",
                    "phase4_requires_provider_calls": "FALSE",
                    "estimated_provider_call_count": 0,
                    "notes": "duplicate session_id encountered during replay queue build",
                }
            )
            continue

        seen_session_ids.add(session_id)
        members.sort(key=lambda row: (row["release_dt"], row["indicator_name"], row["event_id"]))
        earliest_release = members[0]["release_dt"]
        latest_release = members[-1]["release_dt"]
        replay_queue_id = f"replay_queue|{session_id}"
        queue_rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "shadow_version": SHADOW_VERSION,
                "replay_queue_id": replay_queue_id,
                "replay_order": len([row for row in queue_rows if _norm(row.get('replay_status')) != 'SKIP_DUPLICATE_SESSION']) + 1,
                "session_id": session_id,
                "session_date": session_date,
                "country": country,
                "session_window_name": window["session_window_name"],
                "session_start_ts": members[0]["session_start_ts"].astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "session_end_ts": members[0]["session_end_ts"].astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "member_event_count": len(members),
                "member_event_ids": _join_unique(member["event_id"] for member in members),
                "member_indicator_names": _join_unique(member["indicator_name"] for member in members),
                "earliest_release_ts": earliest_release.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "latest_release_ts": latest_release.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "replay_status": "READY_FOR_REPLAY",
                "recommended_run_mode": "dry_run_only" if dry_run else "phase1_then_phase2_to_phase7",
                "phase1_ready": "TRUE",
                "phase2_requires_provider_calls": "TRUE",
                "phase3_requires_provider_calls": "TRUE",
                "phase4_requires_provider_calls": "TRUE",
                "estimated_provider_call_count": provider_call_count_per_session,
                "notes": _truncate_text(window["note"], 240),
            }
        )

    queue_rows.sort(key=_queue_sort_key)
    for order, row in enumerate([row for row in queue_rows if _norm(row.get("replay_status")) == "READY_FOR_REPLAY"], start=1):
        row["replay_order"] = order

    summary = {
        "earliest_event_ts": earliest_event_dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z") if earliest_event_dt else "",
        "latest_event_ts": latest_event_dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z") if latest_event_dt else "",
        "events_read": events_read,
        "eligible_events": eligible_events,
        "sessions_queued": sum(1 for row in queue_rows if _norm(row.get("replay_status")) == "READY_FOR_REPLAY"),
        "sessions_skipped": sum(1 for row in queue_rows if _upper(row.get("replay_status")).startswith("SKIP_")) + skipped_counts["over_max_sessions"],
        "first_session_id": next((row["session_id"] for row in queue_rows if _norm(row.get("replay_status")) == "READY_FOR_REPLAY"), ""),
        "last_session_id": next((row["session_id"] for row in reversed(queue_rows) if _norm(row.get("replay_status")) == "READY_FOR_REPLAY"), ""),
        "provider_call_estimate_total": sum(int(row.get("estimated_provider_call_count") or 0) for row in queue_rows if _norm(row.get("replay_status")) == "READY_FOR_REPLAY"),
        "skip_reasons": dict(skipped_counts),
    }
    return queue_rows, summary


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PreSignal v2 historical replay queue v0.")
    parser.add_argument("--from-earliest", action="store_true")
    parser.add_argument("--from-date")
    parser.add_argument("--to-date")
    parser.add_argument("--country", default=DEFAULT_COUNTRY)
    parser.add_argument("--max-sessions", type=int)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def build_presignal_v2_replay_queue_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    if args is None:
        args = _parse_args([])

    creds = load_credentials(interactive=False)
    sheets_service = build_sheets_service(creds)
    generated_ts = _iso_now()
    config = _read_config_value_map(sheets_service)
    window = _resolve_replay_window(args, config)

    event_rows = _sheet_to_rows(sheets_service, MAIN_SPREADSHEET_ID, EVENT_SHEET)
    _require_headers(EVENT_SHEET, event_rows, ["event_id", "country", "indicator_name", "release_ts"])

    queue_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_QUEUE_SHEET, QUEUE_HEADERS)
    summary_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)

    from_dt = _parse_date_arg(args.from_date) if _norm(getattr(args, "from_date", "")) else None
    to_dt = _parse_date_arg(args.to_date) if _norm(getattr(args, "to_date", "")) else None
    if args.from_earliest:
        from_dt = None

    queue_rows, summary = _build_queue_rows(
        generated_ts,
        event_rows,
        window,
        from_dt,
        to_dt,
        args.max_sessions,
        args.dry_run,
    )

    replay_queue_id = f"presignal_v2_replay_queue|{window['country']}|{window['session_window_name']}|{generated_ts}"
    for row in queue_rows:
        if not _norm(row.get("replay_queue_id")):
            row["replay_queue_id"] = replay_queue_id

    if summary["sessions_queued"] > 0:
        build_status = "PASS"
        final_interpretation = "PRESIGNAL_V2_REPLAY_QUEUE_READY"
    else:
        build_status = "PASS_WITH_WARNINGS"
        final_interpretation = "PRESIGNAL_V2_REPLAY_QUEUE_NEEDS_REVIEW"

    summary_row = {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "shadow_version": SHADOW_VERSION,
        "replay_queue_id": replay_queue_id,
        "earliest_event_ts": summary["earliest_event_ts"],
        "latest_event_ts": summary["latest_event_ts"],
        "events_read": summary["events_read"],
        "eligible_events": summary["eligible_events"],
        "sessions_queued": summary["sessions_queued"],
        "sessions_skipped": summary["sessions_skipped"],
        "first_session_id": summary["first_session_id"],
        "last_session_id": summary["last_session_id"],
        "provider_call_estimate_total": summary["provider_call_estimate_total"],
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "notes": _truncate_text(
            f"dry_run={args.dry_run}; window_note={window['note']}; skip_reasons={json.dumps(summary['skip_reasons'], ensure_ascii=True, sort_keys=True)}",
            500,
        ),
    }

    _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_QUEUE_SHEET, queue_headers, queue_rows)
    _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, [summary_row])
    registry_result = _upsert_registry_rows(sheets_service)

    return {
        "generated_ts": generated_ts,
        "replay_queue_id": replay_queue_id,
        "earliest_event_ts": summary["earliest_event_ts"],
        "latest_event_ts": summary["latest_event_ts"],
        "events_read": summary["events_read"],
        "eligible_events": summary["eligible_events"],
        "sessions_queued": summary["sessions_queued"],
        "first_session_id": summary["first_session_id"],
        "last_session_id": summary["last_session_id"],
        "estimated_provider_calls": summary["provider_call_estimate_total"],
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "registry_result": registry_result,
        "sample_queue_row": queue_rows[0] if queue_rows else {},
    }


def main() -> None:
    print(json.dumps(build_presignal_v2_replay_queue_v0(_parse_args()), ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
