import argparse
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

from automation.google_clients import batch_update_values, build_sheets_service, get_sheet_values, load_credentials


MAIN_SPREADSHEET_ID = os.environ.get(
    "PRESIGNAL_MAIN_SPREADSHEET_ID",
    "1_gZGnd6h3VzdiBvGBHRSxn78KW8tsOi2UEc6Y_Sc23Q",
)
DIAGNOSTICS_SPREADSHEET_ID = os.environ.get(
    "PRESIGNAL_DIAGNOSTICS_SPREADSHEET_ID",
    "1jxcZotbzJKcAzrK0VhxetYX6hp5DPXCCIA0J6B6RUy0",
)
PROJECT_OVERVIEWS_SPREADSHEET_ID = os.environ.get(
    "PRESIGNAL_PROJECT_OVERVIEWS_SPREADSHEET_ID",
    "1PtXrQpzNX8600I0aCOb2hLPkWtTvFKtDVIZZIys_Uvo",
)

SOURCE_EVENT_SHEET = "Event"
REGISTRY_SHEET = "Sheet_Registry"

REGISTRY_HEADERS = [
    "logical_sheet_id",
    "physical_sheet_name",
    "workbook",
    "workbook_id",
    "category",
    "lifecycle_state",
    "owner_module",
    "participates_in_rebuild",
    "read_only",
    "allow_creation",
    "created_phase",
    "notes",
    "registry_created_ts",
    "registry_last_verified_ts",
    "registry_migration_ts",
    "registry_rename_ts",
]

OUTPUT_SHEETS = {
    "sessions": "Market_Sessions",
    "members": "Market_Session_Members",
    "summary": "Market_Session_Shadow_Summary",
}

SCHEMA_VERSION = "presignal_v2_market_session_0.1"
SHADOW_VERSION = "shadow_v0"
REGISTRY_CATEGORY = "PRESIGNAL_V2_MARKET_SESSION"
REGISTRY_OWNER_MODULE = "market_session"

SESSIONS_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "session_id",
    "session_date",
    "country",
    "session_window_name",
    "session_start_ts",
    "session_end_ts",
    "primary_release_ts",
    "last_release_ts",
    "member_event_count",
    "member_event_ids",
    "member_indicator_names",
    "member_genres",
    "member_importance_levels",
    "high_importance_count",
    "medium_importance_count",
    "low_importance_count",
    "unknown_importance_count",
    "batch_count",
    "single_count",
    "member_count",
    "session_status",
    "source_event_sheet",
    "notes",
]

MEMBERS_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "session_id",
    "session_date",
    "country",
    "session_window_name",
    "event_id",
    "batch_id",
    "type",
    "indicator_name",
    "genre",
    "importance",
    "release_ts",
    "consensus_value",
    "prev_revision",
    "member_order",
    "same_minute_group_key",
    "is_batch_member",
    "source_sheet",
    "source_row_number",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "build_status",
    "source_event_rows_read",
    "eligible_event_rows",
    "sessions_built",
    "session_member_rows_written",
    "events_missing_event_id",
    "events_missing_release_ts",
    "events_missing_country",
    "events_missing_indicator_name",
    "events_missing_type",
    "events_filtered_by_country",
    "events_outside_window",
    "duplicate_member_assignments",
    "events_assigned_multiple_sessions",
    "events_assigned_zero_sessions",
    "market_sessions_sheet_written",
    "market_session_members_sheet_written",
    "sheet_registry_updated",
    "governance_status",
    "final_interpretation",
    "country_filter",
    "session_window_name",
    "window_source",
    "window_timezone",
    "window_from_local",
    "window_to_local",
    "window_from_utc",
    "window_to_utc",
    "notes",
    "sanity_failures",
]


def _norm(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return str(value).strip()


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _as_bool(value: Any) -> bool:
    return _upper(value) in {"TRUE", "T", "YES", "Y", "1"}


def _parse_dt(value: Any) -> Optional[datetime]:
    raw = _norm(value)
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _iso_z(dt: Optional[datetime]) -> str:
    if dt is None:
        return ""
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _column_letter(index: int) -> str:
    letters: List[str] = []
    n = max(1, int(index))
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters.append(chr(65 + rem))
    return "".join(reversed(letters))


def _sheet_to_rows(service, spreadsheet_id: str, sheet_name: str) -> List[Dict[str, Any]]:
    values = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!A1:ZZZ")
        .execute()
        .get("values", [])
    )
    if not values:
        return []
    headers = values[0]
    rows: List[Dict[str, Any]] = []
    for idx, raw in enumerate(values[1:], start=2):
        padded = list(raw) + [""] * max(0, len(headers) - len(raw))
        row = {headers[i]: padded[i] for i in range(len(headers))}
        row["__source_row_number__"] = idx
        rows.append(row)
    return rows


def _get_sheet_headers(service, spreadsheet_id: str, sheet_name: str) -> List[str]:
    values = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!1:1")
        .execute()
        .get("values", [])
    )
    return values[0] if values else []


def _ensure_sheet(service, spreadsheet_id: str, sheet_name: str, required_headers: Sequence[str]) -> List[str]:
    metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    titles = {s["properties"]["title"] for s in metadata.get("sheets", [])}
    if sheet_name not in titles:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]},
        ).execute()
        headers = list(required_headers)
    else:
        headers = _get_sheet_headers(service, spreadsheet_id, sheet_name) or list(required_headers)
        for header in required_headers:
            if header not in headers:
                headers.append(header)
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_name}'!A1",
        valueInputOption="RAW",
        body={"values": [headers]},
    ).execute()
    return headers


def _write_rows(service, spreadsheet_id: str, sheet_name: str, headers: Sequence[str], rows: Sequence[Dict[str, Any]]) -> None:
    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_name}'!A2:ZZZ",
    ).execute()
    if not rows:
        return
    values = [[row.get(header, "") for header in headers] for row in rows]
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_name}'!A2",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()


def _read_config_window(service) -> Dict[str, str]:
    try:
        values = get_sheet_values(service, MAIN_SPREADSHEET_ID, "Config!A:B")
    except Exception:
        return {}
    if not values:
        return {}
    out: Dict[str, str] = {}
    for raw in values[1:]:
        if not raw:
            continue
        key = _upper(raw[0])
        if not key:
            continue
        out[key] = _norm(raw[1]) if len(raw) > 1 else ""
    return out


def _parse_local_minute(value: str, tz_name: str) -> datetime:
    try:
        tzinfo = ZoneInfo(tz_name or "UTC")
    except Exception as exc:
        raise RuntimeError(f"Invalid timezone '{tz_name}'.") from exc
    try:
        naive = datetime.strptime(value, "%Y-%m-%d %H:%M")
    except ValueError as exc:
        raise RuntimeError(f"Invalid window value '{value}'. Use YYYY-MM-DD HH:MM.") from exc
    return naive.replace(tzinfo=tzinfo).astimezone(timezone.utc)


def _resolve_window(args: argparse.Namespace, config: Dict[str, str]) -> Dict[str, Any]:
    country = _upper(args.country or "US") or "US"
    session_window_name = _norm(args.session_window_name)
    window_source = "full_window"
    tz_name = _norm(args.timezone) or _norm(config.get("WINDOW_TZ")) or "UTC"
    window_from_local = ""
    window_to_local = ""
    window_from_utc = ""
    window_to_utc = ""

    cli_from = _norm(args.window_from)
    cli_to = _norm(args.window_to)
    if cli_from and cli_to:
        window_source = "cli"
        window_from_local = cli_from
        window_to_local = cli_to
        window_from_utc = _iso_z(_parse_local_minute(cli_from, tz_name))
        window_to_utc = _iso_z(_parse_local_minute(cli_to, tz_name))
        if not session_window_name:
            session_window_name = "CUSTOM_WINDOW"
    else:
        enabled = _as_bool(config.get("WINDOW_ENABLED"))
        cfg_from = _norm(config.get("WINDOW_FROM_LOCAL"))
        cfg_to = _norm(config.get("WINDOW_TO_LOCAL"))
        if enabled and cfg_from and cfg_to:
            window_source = "config"
            window_from_local = cfg_from
            window_to_local = cfg_to
            window_from_utc = _iso_z(_parse_local_minute(cfg_from, tz_name))
            window_to_utc = _iso_z(_parse_local_minute(cfg_to, tz_name))
            if not session_window_name:
                session_window_name = "CUSTOM_CONFIG_WINDOW"
        else:
            if not session_window_name:
                session_window_name = "FULL_WINDOW"

    return {
        "country": country,
        "session_window_name": session_window_name or "FULL_WINDOW",
        "window_source": window_source,
        "window_timezone": tz_name,
        "window_from_local": window_from_local,
        "window_to_local": window_to_local,
        "window_from_utc": window_from_utc,
        "window_to_utc": window_to_utc,
        "window_from_dt": _parse_dt(window_from_utc),
        "window_to_dt": _parse_dt(window_to_utc),
    }


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


def _importance_bucket(value: Any) -> str:
    raw = _upper(value)
    if raw in {"HIGH", "MEDIUM", "LOW"}:
        return raw
    return "UNKNOWN"


def _eligible_event(row: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[str]]:
    event_id = _norm(row.get("event_id"))
    type_name = _norm(row.get("type"))
    country = _norm(row.get("country"))
    indicator_name = _norm(row.get("indicator_name"))
    release_dt = _parse_dt(row.get("release_ts"))
    if not event_id or not type_name or not country or not indicator_name or release_dt is None:
        return False, None, None
    return True, country, _iso_z(release_dt)


def _source_sort_key(row: Dict[str, Any]) -> Tuple[Any, ...]:
    release_dt = _parse_dt(row.get("release_ts")) or datetime.max.replace(tzinfo=timezone.utc)
    return (
        release_dt,
        _upper(row.get("country")),
        _norm(row.get("indicator_name")),
        _norm(row.get("event_id")),
    )


def _session_local_date(dt_utc: datetime, tz_name: str) -> str:
    try:
        tzinfo = ZoneInfo(tz_name or "UTC")
    except Exception:
        tzinfo = timezone.utc
    return dt_utc.astimezone(tzinfo).strftime("%Y-%m-%d")


def _build_market_session_rows(
    generated_ts: str,
    rows: Sequence[Dict[str, Any]],
    window: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    source_country = window["country"]
    window_from_dt = window["window_from_dt"]
    window_to_dt = window["window_to_dt"]
    tz_name = window["window_timezone"]
    session_window_name = window["session_window_name"]

    session_members: List[Dict[str, Any]] = []
    reason_counts = Counter()
    filtered_by_country = 0
    outside_window = 0

    for row in rows:
        event_id = _norm(row.get("event_id"))
        type_name = _norm(row.get("type"))
        country = _norm(row.get("country"))
        indicator_name = _norm(row.get("indicator_name"))
        release_raw = _norm(row.get("release_ts"))
        release_dt = _parse_dt(release_raw)

        if not event_id:
            reason_counts["missing_event_id"] += 1
            continue
        if not release_raw or release_dt is None:
            reason_counts["missing_release_ts"] += 1
            continue
        if not country:
            reason_counts["missing_country"] += 1
            continue
        if not indicator_name:
            reason_counts["missing_indicator_name"] += 1
            continue
        if not type_name:
            reason_counts["missing_type"] += 1
            continue
        if source_country and source_country != "ALL" and _upper(country) != source_country:
            filtered_by_country += 1
            continue
        if window_from_dt and window_to_dt and not (window_from_dt <= release_dt < window_to_dt):
            outside_window += 1
            continue

        is_batch_member = _upper(type_name) == "MEMBER" or _norm(row.get("batch_id")) != ""
        session_members.append(
            {
                "_source_row_number": row.get("__source_row_number__", ""),
                "_release_dt": release_dt,
                "_country": _upper(country),
                "_event_id": event_id,
                "_batch_id": _norm(row.get("batch_id")),
                "_type": type_name,
                "_indicator_name": indicator_name,
                "_genre": _norm(row.get("genre")),
                "_importance": _importance_bucket(row.get("importance")),
                "_importance_raw": _norm(row.get("importance")),
                "_consensus_value": _norm(row.get("consensus_value")),
                "_prev_revision": _norm(row.get("prev_revision")),
                "_is_batch_member": is_batch_member,
                "_source_sheet": SOURCE_EVENT_SHEET,
            }
        )

    session_members.sort(key=lambda row: (
        row["_release_dt"],
        row["_country"],
        row["_indicator_name"],
        row["_event_id"],
    ))

    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in session_members:
        grouped[row["_country"]].append(row)

    session_rows: List[Dict[str, Any]] = []
    for country in sorted(grouped):
        members = grouped[country]
        first_release_dt = members[0]["_release_dt"]
        last_release_dt = members[-1]["_release_dt"]
        session_date = _session_local_date(first_release_dt, tz_name)
        session_id = f"{country}|{session_date}|{session_window_name}"
        member_event_ids = [row["_event_id"] for row in members]
        member_indicator_names = [row["_indicator_name"] for row in members]
        member_genres = [row["_genre"] for row in members]
        member_importance_levels = [row["_importance"] for row in members]
        batch_count = sum(1 for row in members if row["_is_batch_member"])
        single_count = len(members) - batch_count
        counts = Counter(row["_importance"] for row in members)
        session_rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "shadow_version": SHADOW_VERSION,
                "session_id": session_id,
                "session_date": session_date,
                "country": country,
                "session_window_name": session_window_name,
                "session_start_ts": _iso_z(first_release_dt),
                "session_end_ts": _iso_z(last_release_dt),
                "primary_release_ts": _iso_z(first_release_dt),
                "last_release_ts": _iso_z(last_release_dt),
                "member_event_count": len(members),
                "member_event_ids": _join_unique(member_event_ids),
                "member_indicator_names": _join_unique(member_indicator_names),
                "member_genres": _join_unique(member_genres),
                "member_importance_levels": _join_unique(member_importance_levels),
                "high_importance_count": counts.get("HIGH", 0),
                "medium_importance_count": counts.get("MEDIUM", 0),
                "low_importance_count": counts.get("LOW", 0),
                "unknown_importance_count": counts.get("UNKNOWN", 0),
                "batch_count": batch_count,
                "single_count": single_count,
                "member_count": len(members),
                "session_status": "built",
                "source_event_sheet": SOURCE_EVENT_SHEET,
                "notes": "shadow_v0 derived-only; grouped by country within the configured window" + (
                    "; multi_date_session=TRUE" if len({_session_local_date(r["_release_dt"], tz_name) for r in members}) > 1 else ""
                ),
            }
        )

    member_rows: List[Dict[str, Any]] = []
    for country in sorted(grouped):
        members = grouped[country]
        session_date = _session_local_date(members[0]["_release_dt"], tz_name)
        session_id = f"{country}|{session_date}|{session_window_name}"
        for index, row in enumerate(members, start=1):
            member_rows.append(
                {
                    "generated_ts": generated_ts,
                    "schema_version": SCHEMA_VERSION,
                    "shadow_version": SHADOW_VERSION,
                    "session_id": session_id,
                    "session_date": session_date,
                    "country": country,
                    "session_window_name": session_window_name,
                    "event_id": row["_event_id"],
                    "batch_id": row["_batch_id"],
                    "type": row["_type"],
                    "indicator_name": row["_indicator_name"],
                    "genre": row["_genre"],
                    "importance": row["_importance_raw"] or row["_importance"],
                    "release_ts": _iso_z(row["_release_dt"]),
                    "consensus_value": row["_consensus_value"],
                    "prev_revision": row["_prev_revision"],
                    "member_order": index,
                    "same_minute_group_key": f"{country}|{row['_release_dt'].astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:00Z')}",
                    "is_batch_member": "TRUE" if row["_is_batch_member"] else "FALSE",
                    "source_sheet": row["_source_sheet"],
                    "source_row_number": row["_source_row_number"],
                    "notes": "shadow_v0 derived-only",
                }
            )

    summary = {
        "source_event_rows_read": len(rows),
        "eligible_event_rows": len(member_rows),
        "events_missing_event_id": reason_counts["missing_event_id"],
        "events_missing_release_ts": reason_counts["missing_release_ts"],
        "events_missing_country": reason_counts["missing_country"],
        "events_missing_indicator_name": reason_counts["missing_indicator_name"],
        "events_missing_type": reason_counts["missing_type"],
        "events_filtered_by_country": filtered_by_country,
        "events_outside_window": outside_window,
    }
    return session_rows, member_rows, summary


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
            "physical_sheet_name": OUTPUT_SHEETS["sessions"],
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
            "physical_sheet_name": OUTPUT_SHEETS["members"],
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
            "physical_sheet_name": OUTPUT_SHEETS["summary"],
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

    return {
        "updated": len(registry_rows) - appended,
        "appended": appended,
        "logical_ids": [row["logical_sheet_id"] for row in registry_rows],
    }


def _registry_entries_present(service) -> bool:
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    registered = {_upper(row.get("logical_sheet_id")) for row in rows}
    return all(logical in registered for logical in ("MARKET_SESSIONS", "MARKET_SESSION_MEMBERS", "MARKET_SESSION_SHADOW_SUMMARY"))


def _sanity_check(
    session_rows: Sequence[Dict[str, Any]],
    member_rows: Sequence[Dict[str, Any]],
    eligible_event_rows: int,
) -> Tuple[bool, List[str]]:
    failures: List[str] = []
    if eligible_event_rows <= 0:
        failures.append("no_eligible_events")
    if not session_rows and eligible_event_rows > 0:
        failures.append("no_sessions_built")

    for row in member_rows:
        if not _norm(row.get("session_id")):
            failures.append("missing_session_id_in_member_rows")
            break

    duplicate_pairs = Counter((row.get("session_id"), row.get("event_id")) for row in member_rows)
    if any(count > 1 for count in duplicate_pairs.values()):
        failures.append("duplicate_session_event_pairs")

    assigned_event_ids = Counter(_norm(row.get("event_id")) for row in member_rows if _norm(row.get("event_id")))
    if assigned_event_ids:
        multi_session_ids = 0
        for event_id in assigned_event_ids:
            sessions = {_norm(row.get("session_id")) for row in member_rows if _norm(row.get("event_id")) == event_id}
            if len(sessions) > 1:
                multi_session_ids += 1
        if multi_session_ids:
            failures.append("events_assigned_multiple_sessions")
    else:
        failures.append("no_assigned_events")

    session_lookup = {row.get("session_id"): row for row in session_rows}
    for session_id, session in session_lookup.items():
        members = [row for row in member_rows if row.get("session_id") == session_id]
        if int(session.get("member_event_count") or 0) != len(members):
            failures.append(f"member_count_mismatch:{session_id}")
            break
        releases = sorted(_parse_dt(row.get("release_ts")) for row in members if _parse_dt(row.get("release_ts")) is not None)
        if releases:
            if _iso_z(releases[0]) != _norm(session.get("primary_release_ts")):
                failures.append(f"primary_release_ts_mismatch:{session_id}")
                break
            if _iso_z(releases[-1]) != _norm(session.get("last_release_ts")):
                failures.append(f"last_release_ts_mismatch:{session_id}")
                break

    if len(member_rows) != eligible_event_rows:
        failures.append("eligible_event_rows_not_fully_assigned")

    return (len(failures) == 0, failures)


def build_market_sessions_shadow_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    if args is None:
        args = _parse_args([])

    creds = load_credentials(interactive=False)
    service = build_sheets_service(creds)
    generated_ts = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    config = _read_config_window(service)
    window = _resolve_window(args, config)

    values = get_sheet_values(service, MAIN_SPREADSHEET_ID, f"{SOURCE_EVENT_SHEET}!A:ZZZ")
    if not values:
        raise RuntimeError("Event sheet is missing or empty.")
    event_headers = values[0]
    required_headers = ["country", "indicator_name", "release_ts", "event_id", "type"]
    missing_headers = [header for header in required_headers if header not in event_headers]
    if missing_headers:
        raise RuntimeError(f"Event sheet is missing required headers: {', '.join(missing_headers)}")

    source_rows = _sheet_to_rows(service, MAIN_SPREADSHEET_ID, SOURCE_EVENT_SHEET)
    session_rows, member_rows, source_summary = _build_market_session_rows(generated_ts, source_rows, window)

    session_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SHEETS["sessions"], SESSIONS_HEADERS)
    member_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SHEETS["members"], MEMBERS_HEADERS)
    summary_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SHEETS["summary"], SUMMARY_HEADERS)

    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SHEETS["sessions"], session_headers, session_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SHEETS["members"], member_headers, member_rows)

    registry_result = _upsert_registry_rows(service)
    registry_ok = _registry_entries_present(service)

    sanity_ok, sanity_failures = _sanity_check(session_rows, member_rows, source_summary["eligible_event_rows"])
    if not registry_ok:
        sanity_failures.append("registry_entries_missing")
    build_status = "PASS" if sanity_ok and registry_ok else "REVIEW_NEEDED"

    summary_row = {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "shadow_version": SHADOW_VERSION,
        "build_status": build_status,
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
        "duplicate_member_assignments": sum(
            count - 1 for count in Counter((row.get("session_id"), row.get("event_id")) for row in member_rows).values() if count > 1
        ),
        "events_assigned_multiple_sessions": sum(
            1
            for event_id in {_norm(row.get("event_id")) for row in member_rows if _norm(row.get("event_id"))}
            if len({_norm(row.get("session_id")) for row in member_rows if _norm(row.get("event_id")) == event_id}) > 1
        ),
        "events_assigned_zero_sessions": max(0, source_summary["eligible_event_rows"] - len(member_rows)),
        "market_sessions_sheet_written": "TRUE",
        "market_session_members_sheet_written": "TRUE",
        "sheet_registry_updated": "TRUE" if registry_result else "FALSE",
        "governance_status": "DERIVED_ONLY_SHADOW_SAFE",
        "final_interpretation": "MARKET_SESSION_GROUPING_READY" if build_status == "PASS" else "MARKET_SESSION_GROUPING_NEEDS_REVIEW",
        "country_filter": window["country"],
        "session_window_name": window["session_window_name"],
        "window_source": window["window_source"],
        "window_timezone": window["window_timezone"],
        "window_from_local": window["window_from_local"],
        "window_to_local": window["window_to_local"],
        "window_from_utc": window["window_from_utc"],
        "window_to_utc": window["window_to_utc"],
        "notes": (
            "shadow_v0 derived-only; no AI calls; no forecasts; no operational sheets modified; "
            f"country_filter={window['country']}; window_source={window['window_source']}"
        ),
        "sanity_failures": "|".join(sanity_failures),
    }
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SHEETS["summary"], summary_headers, [summary_row])

    return {
        "generated_ts": generated_ts,
        "rows_read": source_summary["source_event_rows_read"],
        "eligible_events": source_summary["eligible_event_rows"],
        "sessions_built": len(session_rows),
        "member_rows_written": len(member_rows),
        "summary_status": build_status,
        "registry": registry_result,
        "sanity_failures": sanity_failures,
        "window": {
            "country": window["country"],
            "session_window_name": window["session_window_name"],
            "window_source": window["window_source"],
            "window_timezone": window["window_timezone"],
            "window_from_local": window["window_from_local"],
            "window_to_local": window["window_to_local"],
            "window_from_utc": window["window_from_utc"],
            "window_to_utc": window["window_to_utc"],
        },
    }


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Market Session Shadow v0 derived sheets.")
    parser.add_argument("--window-from", "--window-from-local", dest="window_from", default="", help="Local window start, YYYY-MM-DD HH:MM")
    parser.add_argument("--window-to", "--window-to-local", dest="window_to", default="", help="Local window end, YYYY-MM-DD HH:MM")
    parser.add_argument("--timezone", "--tz", dest="timezone", default="", help="IANA timezone for window parsing")
    parser.add_argument("--country", default="US", help="Country filter for session grouping")
    parser.add_argument("--session-window-name", default="", help="Session window label")
    return parser.parse_args(argv)


def main() -> None:
    args = _parse_args()
    print(build_market_sessions_shadow_v0(args))


if __name__ == "__main__":
    main()
