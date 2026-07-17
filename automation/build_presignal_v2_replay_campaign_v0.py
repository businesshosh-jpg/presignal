import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_market_sessions_shadow_v0 import (
    DIAGNOSTICS_SPREADSHEET_ID,
    PROJECT_OVERVIEWS_SPREADSHEET_ID,
    REGISTRY_HEADERS,
    REGISTRY_SHEET,
    _column_letter,
    _ensure_sheet,
    _norm,
    _sheet_to_rows,
    _write_rows,
)
from automation.build_presignal_v2_replay_runner_v0 import build_presignal_v2_replay_runner_v0
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


QUEUE_SHEET = "PreSignal_v2_Replay_Queue"
RUN_STATUS_SHEET = "PreSignal_v2_Run_Status"
RUN_LOG_SHEET = "PreSignal_v2_Replay_Run_Log"
RUN_SUMMARY_SHEET = "PreSignal_v2_Replay_Run_Summary"
FAILURE_DIAGNOSTIC_SHEET = "Replay_Failure_Diagnostics"
FAILURE_SUMMARY_SHEET = "Replay_Failure_Summary"

ATTENTION_AUDIT_SHEET = "Session_Attention_Provider_Response_Audit"
INFO_AUDIT_SHEET = "Session_Information_Provider_Response_Audit"
FORECAST_AUDIT_SHEET = "Session_Forecast_Provider_Response_Audit"

OUTPUT_CAMPAIGN_SHEET = "Replay_Campaign"
OUTPUT_SUMMARY_SHEET = "Replay_Campaign_Summary"
OUTPUT_PROVIDER_SHEET = "Replay_Campaign_Provider_Status"

SCHEMA_VERSION = "presignal_v2_replay_campaign_0.1"
SHADOW_VERSION = "shadow_v0"
REGISTRY_CATEGORY = "PRESIGNAL_V2_MARKET_SESSION"
REGISTRY_OWNER_MODULE = "market_session"
DEFAULT_PROVIDERS = ("Gemini", "OpenAI", "Anthropic")

CAMPAIGN_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "campaign_id",
    "campaign_name",
    "attempt_number",
    "batch_index",
    "session_id",
    "phase_limit",
    "dry_run",
    "retry_failed",
    "queue_status_before",
    "queue_status_after",
    "replay_id",
    "run_build_status",
    "run_final_interpretation",
    "campaign_session_status",
    "campaign_session_classification",
    "retry_recommendation",
    "block_research",
    "started_ts",
    "completed_ts",
    "elapsed_seconds",
    "estimated_provider_call_count",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "campaign_id",
    "campaign_name",
    "sessions_total",
    "sessions_completed",
    "sessions_failed",
    "sessions_remaining",
    "completion_percentage",
    "elapsed_time",
    "provider_call_count",
    "successful_sessions",
    "provider_failure_sessions",
    "transport_failure_sessions",
    "contract_failure_sessions",
    "parse_failure_sessions",
    "cross_session_mismatch_sessions",
    "missing_artifact_sessions",
    "structural_failure_sessions",
    "build_status",
    "final_interpretation",
    "notes",
]

PROVIDER_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "campaign_id",
    "campaign_name",
    "provider",
    "sessions_attempted",
    "sessions_completed",
    "artifact_linkage_failures",
    "provider_errors",
    "transport_errors",
    "parse_errors",
    "contract_errors",
    "successful_replays",
    "retries",
    "retry_success",
    "completion_rate",
    "notes",
]

SESSION_CLASSIFICATIONS = {
    "SUCCESS",
    "PROVIDER_FAILURE",
    "TRANSPORT_FAILURE",
    "CONTRACT_FAILURE",
    "PARSE_FAILURE",
    "CROSS_SESSION_ARTIFACT_MISMATCH",
    "ACTIVE_SESSION_ARTIFACT_MISSING",
    "STRUCTURAL_FAILURE",
    "UNKNOWN_FAILURE",
}


def _iso_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _require_headers(sheet_name: str, rows: Sequence[Dict[str, Any]], headers: Sequence[str]) -> None:
    if not rows:
        raise RuntimeError(f"{sheet_name} is missing or empty.")
    missing = [header for header in headers if header not in rows[0]]
    if missing:
        raise RuntimeError(f"{sheet_name} is missing required headers: {', '.join(missing)}")


def _safe_float(value: Any) -> float:
    try:
        text = _norm(value)
        if not text:
            return 0.0
        return float(text)
    except Exception:
        return 0.0


def _campaign_id(name: str) -> str:
    return f"replay_campaign|{_norm(name)}|{_iso_now()}"


def _ensure_registry(service) -> Dict[str, Any]:
    headers = _ensure_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_upper(row.get("logical_sheet_id")): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_upper(row.get("logical_sheet_id")): row for row in rows}
    updates = []
    appended = 0
    registry_rows = [
        {
            "logical_sheet_id": "REPLAY_CAMPAIGN",
            "physical_sheet_name": OUTPUT_CAMPAIGN_SHEET,
            "sheet_role": "v2_replay_campaign",
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
            "created_phase": "PreSignal v2.0 Phase 7.5C",
            "notes": "shadow_v0 replay campaign detail",
        },
        {
            "logical_sheet_id": "REPLAY_CAMPAIGN_SUMMARY",
            "physical_sheet_name": OUTPUT_SUMMARY_SHEET,
            "sheet_role": "v2_replay_campaign_summary",
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
            "created_phase": "PreSignal v2.0 Phase 7.5C",
            "notes": "shadow_v0 replay campaign summary",
        },
        {
            "logical_sheet_id": "REPLAY_CAMPAIGN_PROVIDER_STATUS",
            "physical_sheet_name": OUTPUT_PROVIDER_SHEET,
            "sheet_role": "v2_replay_campaign_provider_status",
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
            "created_phase": "PreSignal v2.0 Phase 7.5C",
            "notes": "shadow_v0 replay campaign provider aggregation",
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


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PreSignal v2 replay campaign manager v0.")
    parser.add_argument("--campaign-name", required=True)
    parser.add_argument("--max-sessions", type=int)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--phase-limit", type=int, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--capture-history", action="store_true")
    parser.add_argument("--history-dry-run", action="store_true")
    return parser.parse_args(argv)


def _latest_campaign_id(campaign_rows: Sequence[Dict[str, Any]], campaign_name: str) -> Optional[str]:
    matches = [row for row in campaign_rows if _norm(row.get("campaign_name")) == _norm(campaign_name)]
    if not matches:
        return None
    matches.sort(key=lambda row: (_norm(row.get("generated_ts")), _norm(row.get("campaign_id"))), reverse=True)
    return _norm(matches[0].get("campaign_id")) or None


def _campaign_attempt_rows(campaign_rows: Sequence[Dict[str, Any]], campaign_id: str) -> List[Dict[str, Any]]:
    return [row for row in campaign_rows if _norm(row.get("campaign_id")) == campaign_id]


def _latest_attempt_by_session(rows: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    sorted_rows = sorted(
        rows,
        key=lambda row: (
            _norm(row.get("session_id")),
            int(float(_norm(row.get("attempt_number")) or "0")),
            _norm(row.get("generated_ts")),
        ),
    )
    for row in sorted_rows:
        session_id = _norm(row.get("session_id"))
        if session_id:
            latest[session_id] = row
    return latest


def _latest_row_by_key(rows: Sequence[Dict[str, Any]], key: str) -> Dict[str, Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    sorted_rows = sorted(
        rows,
        key=lambda row: (
            _norm(row.get(key)),
            _norm(row.get("generated_ts")),
            int(float(_norm(row.get("__source_row_number__")) or "0")),
        ),
    )
    for row in sorted_rows:
        row_key = _norm(row.get(key))
        if row_key:
            latest[row_key] = row
    return latest


def _select_campaign_sessions(
    queue_rows: Sequence[Dict[str, Any]],
    existing_rows: Sequence[Dict[str, Any]],
    args: argparse.Namespace,
) -> Tuple[List[Dict[str, Any]], int]:
    latest = _latest_attempt_by_session(existing_rows)
    candidate_rows = []
    for row in queue_rows:
        queue_status = _norm(row.get("replay_status"))
        if queue_status not in {"READY_FOR_REPLAY", "FAILED", "RUNNING", "COMPLETED"}:
            continue
        session_id = _norm(row.get("session_id"))
        previous = latest.get(session_id)
        previous_status = _norm(previous.get("campaign_session_status")) if previous else ""
        if args.resume:
            if queue_status == "COMPLETED":
                continue
            if queue_status == "FAILED" and not args.retry_failed:
                continue
            if previous_status == "COMPLETED":
                continue
            if previous_status == "FAILED" and not args.retry_failed:
                continue
        else:
            if queue_status == "COMPLETED":
                continue
            if queue_status == "FAILED" and not args.retry_failed:
                continue
        candidate_rows.append(row)
    candidate_rows.sort(
        key=lambda row: (
            int(_safe_float(row.get("replay_order"))),
            _norm(row.get("session_id")),
        )
    )
    sessions_total = len(candidate_rows)
    limit = sessions_total
    if args.max_sessions is not None:
        limit = min(limit, args.max_sessions)
    if args.batch_size is not None:
        limit = min(limit, args.batch_size)
    return candidate_rows[:limit], sessions_total


def _read_optional_rows(service, sheet_name: str) -> List[Dict[str, Any]]:
    try:
        return _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name)
    except Exception:
        return []


def _parse_provider_stats_from_audits(service, phase_limit: int, dry_run: bool) -> Dict[str, Counter]:
    stats: Dict[str, Counter] = {provider: Counter() for provider in DEFAULT_PROVIDERS}
    if dry_run or phase_limit < 2:
        return stats
    sheet_names = []
    if phase_limit >= 2:
        sheet_names.append(ATTENTION_AUDIT_SHEET)
    if phase_limit >= 3:
        sheet_names.append(INFO_AUDIT_SHEET)
    if phase_limit >= 4:
        sheet_names.append(FORECAST_AUDIT_SHEET)

    provider_seen = {provider: False for provider in DEFAULT_PROVIDERS}
    for sheet_name in sheet_names:
        rows = _read_optional_rows(service, sheet_name)
        for row in rows:
            provider = _norm(row.get("provider"))
            if provider not in stats:
                continue
            provider_seen[provider] = True
            response_status = _norm(row.get("response_status")).lower()
            request_status = _norm(row.get("request_status")).lower()
            parse_status = _norm(row.get("parse_status")).lower()
            contract_status = _norm(row.get("contract_status")).lower()
            retry_status = _norm(row.get("retry_status")).lower()
            error_type = _norm(row.get("error_type")).lower()
            error_message = _norm(row.get("error_message")).lower()

            if response_status == "provider_error" or request_status == "provider_error":
                stats[provider]["provider_errors"] += 1
            if any(token in error_type or token in error_message for token in ["503", "502", "504", "rate_limit", "service_unavailable", "timeout", "deadline_exceeded", "connection reset", "transient_provider_error"]):
                stats[provider]["transport_errors"] += 1
            if "parse" in parse_status and parse_status not in {"parsed", "parsed_recovered"}:
                stats[provider]["parse_errors"] += 1
            if contract_status and contract_status not in {"ok", "valid", "validated"}:
                stats[provider]["contract_errors"] += 1
            if retry_status in {"retry_scheduled", "retry_succeeded", "retry_exhausted"}:
                stats[provider]["retries"] += 1
            if retry_status == "retry_succeeded":
                stats[provider]["retry_success"] += 1

    for provider in DEFAULT_PROVIDERS:
        if provider_seen[provider]:
            stats[provider]["sessions_attempted"] += 1
    return stats


def _classification_from_diagnostic(diag_row: Dict[str, Any]) -> str:
    category = _norm(diag_row.get("failure_category"))
    mapping = {
        "provider_failure": "PROVIDER_FAILURE",
        "provider_warning": "PROVIDER_FAILURE",
        "transport_failure": "TRANSPORT_FAILURE",
        "contract_failure": "CONTRACT_FAILURE",
        "parse_failure": "PARSE_FAILURE",
        "structural_sheet_problem": "STRUCTURAL_FAILURE",
        "schema_failure": "STRUCTURAL_FAILURE",
        "missing_rows": "STRUCTURAL_FAILURE",
        "summary_gating": "STRUCTURAL_FAILURE",
        "other": "UNKNOWN_FAILURE",
    }
    return mapping.get(category, "UNKNOWN_FAILURE")


def _retry_recommendation(classification: str, diagnostic_row: Dict[str, Any]) -> str:
    if classification == "SUCCESS":
        return "NO_ACTION"
    if classification == "TRANSPORT_FAILURE":
        return "RETRY_PROVIDER"
    if classification in {"PROVIDER_FAILURE", "CONTRACT_FAILURE", "PARSE_FAILURE"}:
        return "REVIEW_THEN_RETRY"
    if classification in {"CROSS_SESSION_ARTIFACT_MISMATCH", "ACTIVE_SESSION_ARTIFACT_MISSING", "STRUCTURAL_FAILURE"}:
        return _norm(diagnostic_row.get("recommended_runner_action")) or "BLOCK_RESEARCH"
    return "MANUAL_REVIEW"


def _classify_campaign_session(
    session_id: str,
    dry_run: bool,
    runner_result: Dict[str, Any],
    run_log_row: Dict[str, Any],
    diagnostic_row: Dict[str, Any],
) -> Tuple[str, str, str, str]:
    linkage_status = _norm(run_log_row.get("linkage_status"))
    log_status = _norm(run_log_row.get("status"))
    if linkage_status == "CROSS_SESSION_ARTIFACT_MISMATCH":
        return (
            "CROSS_SESSION_ARTIFACT_MISMATCH",
            _retry_recommendation("CROSS_SESSION_ARTIFACT_MISMATCH", diagnostic_row),
            "TRUE",
            _norm(run_log_row.get("linkage_error")) or _norm((runner_result.get("sample_log_row") or {}).get("errors")),
        )
    if linkage_status == "ACTIVE_SESSION_ARTIFACT_MISSING":
        return (
            "ACTIVE_SESSION_ARTIFACT_MISSING",
            _retry_recommendation("ACTIVE_SESSION_ARTIFACT_MISSING", diagnostic_row),
            "TRUE",
            _norm(run_log_row.get("linkage_error")) or _norm((runner_result.get("sample_log_row") or {}).get("errors")),
        )
    if log_status in {"COMPLETED", "DRY_RUN"} and (dry_run or linkage_status in {"LINKED", "NOT_CHECKED"}):
        return (
            "SUCCESS",
            "NO_ACTION",
            "FALSE",
            _norm((runner_result.get("sample_log_row") or {}).get("warnings")),
        )
    if diagnostic_row:
        classification = _classification_from_diagnostic(diagnostic_row)
        block_research = "TRUE" if classification in {
            "CROSS_SESSION_ARTIFACT_MISMATCH",
            "ACTIVE_SESSION_ARTIFACT_MISSING",
            "STRUCTURAL_FAILURE",
        } else "FALSE"
        return (
            classification,
            _retry_recommendation(classification, diagnostic_row),
            block_research,
            _norm(diagnostic_row.get("failure_reason")) or _norm((runner_result.get("sample_log_row") or {}).get("errors")),
        )
    return (
        "UNKNOWN_FAILURE",
        "MANUAL_REVIEW",
        "TRUE" if _norm(run_log_row.get("status")) == "FAILED" else "FALSE",
        _norm((runner_result.get("sample_log_row") or {}).get("errors")) or _norm(run_log_row.get("errors")),
    )


def _merge_provider_stats(base: Dict[str, Counter], delta: Dict[str, Counter], session_completed: bool) -> None:
    for provider in DEFAULT_PROVIDERS:
        base[provider].update(delta.get(provider, Counter()))
        if session_completed and delta.get(provider, Counter()).get("sessions_attempted", 0) > 0:
            has_errors = sum(
                delta.get(provider, Counter()).get(key, 0)
                for key in ["provider_errors", "transport_errors", "parse_errors", "contract_errors"]
            ) > 0
            if not has_errors:
                base[provider]["sessions_completed"] += 1


def _provider_rows_for_campaign(
    generated_ts: str,
    campaign_id: str,
    campaign_name: str,
    provider_stats: Dict[str, Counter],
) -> List[Dict[str, Any]]:
    rows = []
    for provider in DEFAULT_PROVIDERS:
        stats = provider_stats.get(provider, Counter())
        attempted = stats.get("sessions_attempted", 0)
        completed = stats.get("sessions_completed", 0)
        completion_rate = round((completed / attempted) * 100, 2) if attempted else 0
        rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "shadow_version": SHADOW_VERSION,
                "campaign_id": campaign_id,
                "campaign_name": campaign_name,
                "provider": provider,
                "sessions_attempted": attempted,
                "sessions_completed": completed,
                "artifact_linkage_failures": stats.get("artifact_linkage_failures", 0),
                "provider_errors": stats.get("provider_errors", 0),
                "transport_errors": stats.get("transport_errors", 0),
                "parse_errors": stats.get("parse_errors", 0),
                "contract_errors": stats.get("contract_errors", 0),
                "successful_replays": stats.get("successful_replays", completed),
                "retries": stats.get("retries", 0),
                "retry_success": stats.get("retry_success", 0),
                "completion_rate": completion_rate,
                "notes": _norm(stats.get("notes")),
            }
        )
    return rows


def build_presignal_v2_replay_campaign_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    if args is None:
        args = _parse_args([])
    if args.phase_limit < 1 or args.phase_limit > 7:
        raise RuntimeError("--phase-limit must be between 1 and 7.")

    creds = load_credentials(interactive=False)
    service = build_sheets_service(creds)
    generated_ts = _iso_now()

    queue_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, QUEUE_SHEET)
    run_status_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, RUN_STATUS_SHEET)
    run_log_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, RUN_LOG_SHEET)
    run_summary_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, RUN_SUMMARY_SHEET)
    failure_diagnostic_rows = _read_optional_rows(service, FAILURE_DIAGNOSTIC_SHEET)
    failure_summary_rows = _read_optional_rows(service, FAILURE_SUMMARY_SHEET)
    _ = failure_summary_rows
    _require_headers(QUEUE_SHEET, queue_rows, ["session_id", "replay_status", "estimated_provider_call_count"])
    _require_headers(RUN_STATUS_SHEET, run_status_rows, ["session_id", "overall_v2_pipeline_status"])
    if run_log_rows:
        _require_headers(RUN_LOG_SHEET, run_log_rows, ["replay_id", "session_id", "status"])
    if run_summary_rows:
        _require_headers(RUN_SUMMARY_SHEET, run_summary_rows, ["replay_id", "build_status", "final_interpretation"])

    campaign_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_CAMPAIGN_SHEET, CAMPAIGN_HEADERS)
    summary_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)
    provider_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_PROVIDER_SHEET, PROVIDER_HEADERS)

    existing_campaign_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_CAMPAIGN_SHEET)
    existing_summary_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET)
    existing_provider_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_PROVIDER_SHEET)

    if args.resume:
        campaign_id = _latest_campaign_id(existing_campaign_rows, args.campaign_name)
        if not campaign_id:
            raise RuntimeError(f"No existing campaign found for campaign-name={args.campaign_name}")
    else:
        campaign_id = _campaign_id(args.campaign_name)

    campaign_history_rows = _campaign_attempt_rows(existing_campaign_rows, campaign_id)
    scheduled_rows, sessions_total = _select_campaign_sessions(queue_rows, campaign_history_rows, args)

    latest_by_session = _latest_attempt_by_session(campaign_history_rows)
    provider_stats: Dict[str, Counter] = {provider: Counter() for provider in DEFAULT_PROVIDERS}
    # Seed provider stats from existing campaign provider rows if resuming.
    for row in existing_provider_rows:
        if _norm(row.get("campaign_id")) != campaign_id:
            continue
        provider = _norm(row.get("provider"))
        if provider not in provider_stats:
            continue
        provider_stats[provider]["sessions_attempted"] = int(_safe_float(row.get("sessions_attempted")))
        provider_stats[provider]["sessions_completed"] = int(_safe_float(row.get("sessions_completed")))
        provider_stats[provider]["provider_errors"] = int(_safe_float(row.get("provider_errors")))
        provider_stats[provider]["transport_errors"] = int(_safe_float(row.get("transport_errors")))
        provider_stats[provider]["parse_errors"] = int(_safe_float(row.get("parse_errors")))
        provider_stats[provider]["contract_errors"] = int(_safe_float(row.get("contract_errors")))
        provider_stats[provider]["artifact_linkage_failures"] = int(_safe_float(row.get("artifact_linkage_failures")))
        provider_stats[provider]["successful_replays"] = int(_safe_float(row.get("successful_replays")))
        provider_stats[provider]["retries"] = int(_safe_float(row.get("retries")))
        provider_stats[provider]["retry_success"] = int(_safe_float(row.get("retry_success")))

    new_campaign_rows: List[Dict[str, Any]] = []
    outcome_counts = Counter()
    batch_started = time.time()
    for batch_index, queue_row in enumerate(scheduled_rows, start=1):
        session_id = _norm(queue_row.get("session_id"))
        previous_attempt = latest_by_session.get(session_id)
        attempt_number = int(_safe_float((previous_attempt or {}).get("attempt_number"))) + 1
        queue_status_before = _norm(queue_row.get("replay_status"))
        started_ts = _iso_now()
        started = time.time()

        runner_args = argparse.Namespace(
            phase_limit=args.phase_limit,
            max_sessions=1,
            replay_queue_id="",
            session_id=session_id,
            dry_run=args.dry_run,
            resume=bool(args.retry_failed or queue_status_before in {"FAILED", "RUNNING"}),
            retry_failed=bool(args.retry_failed),
            capture_history=bool(args.capture_history),
            history_dry_run=bool(args.history_dry_run),
            campaign_id=campaign_id,
            experiment_id="",
        )
        runner_result = build_presignal_v2_replay_runner_v0(runner_args)
        elapsed = round(time.time() - started, 3)

        queue_rows_after = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, QUEUE_SHEET)
        queue_after_map = {_norm(row.get("session_id")): row for row in queue_rows_after}
        queue_status_after = _norm(queue_after_map.get(session_id, {}).get("replay_status")) or queue_status_before
        run_log_rows_after = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, RUN_LOG_SHEET)
        run_log_map = {
            (_norm(row.get("replay_id")), _norm(row.get("session_id"))): row
            for row in run_log_rows_after
        }
        run_log_row = run_log_map.get((_norm(runner_result.get("replay_id")), session_id), {})
        failure_diagnostic_rows = _read_optional_rows(service, FAILURE_DIAGNOSTIC_SHEET)
        latest_failure_by_session = _latest_row_by_key(failure_diagnostic_rows, "session_id")
        diagnostic_row = latest_failure_by_session.get(session_id, {})

        session_completed = runner_result.get("sessions_completed", 0) > 0 and runner_result.get("sessions_failed", 0) == 0
        session_status = "COMPLETED" if session_completed else "FAILED"
        if args.dry_run and session_completed:
            session_status = "DRY_RUN_COMPLETED"
        classification, retry_recommendation, block_research, classification_note = _classify_campaign_session(
            session_id,
            args.dry_run,
            runner_result,
            run_log_row,
            diagnostic_row,
        )
        outcome_counts[classification] += 1

        provider_delta = _parse_provider_stats_from_audits(service, args.phase_limit, args.dry_run)
        _merge_provider_stats(provider_stats, provider_delta, session_completed and not args.dry_run)
        if classification == "SUCCESS":
            for provider in DEFAULT_PROVIDERS:
                provider_stats[provider]["successful_replays"] += 1
        if classification in {"CROSS_SESSION_ARTIFACT_MISMATCH", "ACTIVE_SESSION_ARTIFACT_MISSING", "STRUCTURAL_FAILURE"}:
            for provider in DEFAULT_PROVIDERS:
                provider_stats[provider]["artifact_linkage_failures"] += 1
                provider_stats[provider]["notes"] = "campaign-level linkage/infrastructure failures counted across providers"

        new_campaign_rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "shadow_version": SHADOW_VERSION,
                "campaign_id": campaign_id,
                "campaign_name": args.campaign_name,
                "attempt_number": attempt_number,
                "batch_index": batch_index,
                "session_id": session_id,
                "phase_limit": args.phase_limit,
                "dry_run": "TRUE" if args.dry_run else "FALSE",
                "retry_failed": "TRUE" if args.retry_failed else "FALSE",
                "queue_status_before": queue_status_before,
                "queue_status_after": queue_status_after,
                "replay_id": _norm(runner_result.get("replay_id")),
                "run_build_status": _norm(runner_result.get("build_status")),
                "run_final_interpretation": _norm(runner_result.get("final_interpretation")),
                "campaign_session_status": session_status,
                "campaign_session_classification": classification,
                "retry_recommendation": retry_recommendation,
                "block_research": block_research,
                "started_ts": started_ts,
                "completed_ts": _iso_now(),
                "elapsed_seconds": elapsed,
                "estimated_provider_call_count": _safe_float(queue_row.get("estimated_provider_call_count")),
                "notes": _norm(classification_note or (runner_result.get("sample_log_row") or {}).get("errors") or (runner_result.get("sample_log_row") or {}).get("warnings")),
            }
        )

    all_campaign_rows = existing_campaign_rows + new_campaign_rows
    campaign_rows_for_id = _campaign_attempt_rows(all_campaign_rows, campaign_id)
    latest_by_session = _latest_attempt_by_session(campaign_rows_for_id)

    sessions_completed = sum(1 for row in latest_by_session.values() if _norm(row.get("campaign_session_status")) in {"COMPLETED", "DRY_RUN_COMPLETED"})
    sessions_failed = sum(1 for row in latest_by_session.values() if _norm(row.get("campaign_session_status")) == "FAILED")
    sessions_remaining = max(0, sessions_total - sessions_completed - sessions_failed)
    completion_percentage = round((sessions_completed / sessions_total) * 100, 2) if sessions_total else 0
    elapsed_time = round(sum(_safe_float(row.get("elapsed_seconds")) for row in campaign_rows_for_id), 3)
    provider_call_count = int(sum(_safe_float(row.get("estimated_provider_call_count")) for row in campaign_rows_for_id))
    latest_outcome_counts = Counter(
        _norm(row.get("campaign_session_classification")) or "UNKNOWN_FAILURE"
        for row in latest_by_session.values()
    )

    cross_session_mismatch_sessions = latest_outcome_counts.get("CROSS_SESSION_ARTIFACT_MISMATCH", 0)
    missing_artifact_sessions = latest_outcome_counts.get("ACTIVE_SESSION_ARTIFACT_MISSING", 0)
    structural_failure_sessions = latest_outcome_counts.get("STRUCTURAL_FAILURE", 0)
    provider_failure_sessions = latest_outcome_counts.get("PROVIDER_FAILURE", 0)
    transport_failure_sessions = latest_outcome_counts.get("TRANSPORT_FAILURE", 0)
    contract_failure_sessions = latest_outcome_counts.get("CONTRACT_FAILURE", 0)
    parse_failure_sessions = latest_outcome_counts.get("PARSE_FAILURE", 0)
    successful_sessions = latest_outcome_counts.get("SUCCESS", 0)

    if cross_session_mismatch_sessions > 0 or missing_artifact_sessions > 0 or structural_failure_sessions > 0:
        build_status = "BLOCKED"
        final_interpretation = "REPLAY_CAMPAIGN_BLOCKED"
    elif sessions_failed == 0:
        build_status = "PASS"
        final_interpretation = "REPLAY_CAMPAIGN_READY"
    elif provider_failure_sessions > 0 or transport_failure_sessions > 0 or contract_failure_sessions > 0 or parse_failure_sessions > 0:
        build_status = "PASS_WITH_WARNINGS"
        final_interpretation = "REPLAY_CAMPAIGN_READY_WITH_WARNINGS"
    else:
        build_status = "FAIL"
        final_interpretation = "REPLAY_CAMPAIGN_NEEDS_REVIEW"

    summary_row = {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "shadow_version": SHADOW_VERSION,
        "campaign_id": campaign_id,
        "campaign_name": args.campaign_name,
        "sessions_total": sessions_total,
        "sessions_completed": sessions_completed,
        "sessions_failed": sessions_failed,
        "sessions_remaining": sessions_remaining,
        "completion_percentage": completion_percentage,
        "elapsed_time": elapsed_time,
        "provider_call_count": provider_call_count,
        "successful_sessions": successful_sessions,
        "provider_failure_sessions": provider_failure_sessions,
        "transport_failure_sessions": transport_failure_sessions,
        "contract_failure_sessions": contract_failure_sessions,
        "parse_failure_sessions": parse_failure_sessions,
        "cross_session_mismatch_sessions": cross_session_mismatch_sessions,
        "missing_artifact_sessions": missing_artifact_sessions,
        "structural_failure_sessions": structural_failure_sessions,
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "notes": _norm(
            f"phase_limit={args.phase_limit}; batch_size={args.batch_size or ''}; dry_run={args.dry_run}; "
            f"retry_failed={args.retry_failed}; failure_summary_available={bool(failure_diagnostic_rows)}"
        ),
    }

    provider_rows = _provider_rows_for_campaign(generated_ts, campaign_id, args.campaign_name, provider_stats)

    summary_without_campaign = [row for row in existing_summary_rows if _norm(row.get("campaign_id")) != campaign_id]
    provider_without_campaign = [row for row in existing_provider_rows if _norm(row.get("campaign_id")) != campaign_id]

    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_CAMPAIGN_SHEET, campaign_headers, all_campaign_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, summary_without_campaign + [summary_row])
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_PROVIDER_SHEET, provider_headers, provider_without_campaign + provider_rows)
    registry_result = _ensure_registry(service)

    return {
        "campaign_id": campaign_id,
        "campaign_name": args.campaign_name,
        "sessions_scheduled": len(scheduled_rows),
        "sessions_total": sessions_total,
        "sessions_completed": sessions_completed,
        "sessions_failed": sessions_failed,
        "sessions_remaining": sessions_remaining,
        "completion_percentage": completion_percentage,
        "provider_stats": {
            provider: {
                "sessions_attempted": provider_stats[provider].get("sessions_attempted", 0),
                "sessions_completed": provider_stats[provider].get("sessions_completed", 0),
                "provider_errors": provider_stats[provider].get("provider_errors", 0),
                "transport_errors": provider_stats[provider].get("transport_errors", 0),
                "parse_errors": provider_stats[provider].get("parse_errors", 0),
                "contract_errors": provider_stats[provider].get("contract_errors", 0),
                "artifact_linkage_failures": provider_stats[provider].get("artifact_linkage_failures", 0),
                "successful_replays": provider_stats[provider].get("successful_replays", 0),
                "retries": provider_stats[provider].get("retries", 0),
                "retry_success": provider_stats[provider].get("retry_success", 0),
            }
            for provider in DEFAULT_PROVIDERS
        },
        "campaign_summary": summary_row,
        "final_interpretation": final_interpretation,
        "build_status": build_status,
        "registry_result": registry_result,
    }


def main() -> None:
    print(json.dumps(build_presignal_v2_replay_campaign_v0(_parse_args()), ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
