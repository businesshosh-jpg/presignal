import argparse
import json
import sys
from itertools import combinations
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
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


CAMPAIGN_SHEET = "Replay_Campaign"
CAMPAIGN_SUMMARY_SHEET = "Replay_Campaign_Summary"
CAMPAIGN_PROVIDER_SHEET = "Replay_Campaign_Provider_Status"
RUN_STATUS_SHEET = "PreSignal_v2_Run_Status"
FAILURE_DIAGNOSTIC_SHEET = "Replay_Failure_Diagnostics"

OUTPUT_EXPERIMENT_SHEET = "Replay_Experiments"
OUTPUT_SUMMARY_SHEET = "Replay_Experiment_Summary"
OUTPUT_COMPARISON_SHEET = "Replay_Experiment_Comparison"

SCHEMA_VERSION = "presignal_v2_experiment_manager_0.1"
SHADOW_VERSION = "shadow_v0"
REGISTRY_CATEGORY = "PRESIGNAL_V2_MARKET_SESSION"
REGISTRY_OWNER_MODULE = "market_session"

EXPERIMENT_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "experiment_id",
    "experiment_name",
    "experiment_description",
    "created_ts",
    "campaign_id",
    "campaign_name",
    "campaign_generated_ts",
    "campaign_build_status",
    "campaign_final_interpretation",
    "campaign_sessions_completed",
    "campaign_sessions_failed",
    "provider_failures",
    "transport_failures",
    "contract_failures",
    "parse_failures",
    "linkage_failures",
    "research_blocking_failures",
    "retryable_failures",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "experiment_id",
    "experiment_name",
    "experiment_description",
    "created_ts",
    "campaigns_linked",
    "sessions_completed",
    "sessions_failed",
    "provider_failures",
    "transport_failures",
    "contract_failures",
    "parse_failures",
    "linkage_failures",
    "research_blocking_failures",
    "retryable_failures",
    "candidate_rows",
    "forecast_rows",
    "evaluation_rows",
    "comparison_rows",
    "build_status",
    "final_interpretation",
    "notes",
]

COMPARISON_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "experiment_a",
    "experiment_b",
    "completed_sessions_delta",
    "provider_failure_delta",
    "transport_delta",
    "candidate_delta",
    "forecast_delta",
    "evaluation_delta",
    "notes",
]


def _iso_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _safe_int(value: Any) -> int:
    try:
        text = _norm(value)
        if not text:
            return 0
        return int(float(text))
    except Exception:
        return 0


def _require_headers(sheet_name: str, rows: Sequence[Dict[str, Any]], headers: Sequence[str]) -> None:
    if not rows:
        raise RuntimeError(f"{sheet_name} is missing or empty.")
    missing = [header for header in headers if header not in rows[0]]
    if missing:
        raise RuntimeError(f"{sheet_name} is missing required headers: {', '.join(missing)}")


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


def _experiment_id(name: str) -> str:
    return f"replay_experiment|{_norm(name)}|{_iso_now()}"


def _latest_campaign_summary(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        raise RuntimeError("Replay_Campaign_Summary is empty.")
    return sorted(
        rows,
        key=lambda row: (
            _norm(row.get("generated_ts")),
            _norm(row.get("campaign_id")),
            _safe_int(row.get("__source_row_number__")),
        ),
    )[-1]


def _latest_by_key(rows: Sequence[Dict[str, Any]], key: str) -> Dict[str, Dict[str, Any]]:
    ordered = sorted(
        rows,
        key=lambda row: (
            _norm(row.get(key)),
            _norm(row.get("generated_ts")),
            _safe_int(row.get("__source_row_number__")),
        ),
    )
    latest: Dict[str, Dict[str, Any]] = {}
    for row in ordered:
        row_key = _norm(row.get(key))
        if row_key:
            latest[row_key] = row
    return latest


def _select_campaign_ids(args: argparse.Namespace, summary_rows: Sequence[Dict[str, Any]]) -> List[str]:
    selected = [_norm(campaign_id) for campaign_id in args.campaign_id if _norm(campaign_id)]
    if selected:
        return selected
    return [_norm(_latest_campaign_summary(summary_rows).get("campaign_id"))]


def _classifications_for_campaign(campaign_rows: Sequence[Dict[str, Any]], campaign_id: str) -> List[str]:
    latest_by_session: Dict[str, Dict[str, Any]] = {}
    ordered = sorted(
        [row for row in campaign_rows if _norm(row.get("campaign_id")) == campaign_id],
        key=lambda row: (
            _norm(row.get("session_id")),
            _safe_int(row.get("attempt_number")),
            _norm(row.get("generated_ts")),
            _safe_int(row.get("__source_row_number__")),
        ),
    )
    for row in ordered:
        session_id = _norm(row.get("session_id"))
        if session_id:
            latest_by_session[session_id] = row
    return [_norm(row.get("campaign_session_classification")) or "UNKNOWN_FAILURE" for row in latest_by_session.values()]


def _failure_rollup(classifications: Sequence[str]) -> Dict[str, int]:
    provider_failures = sum(1 for value in classifications if value == "PROVIDER_FAILURE")
    transport_failures = sum(1 for value in classifications if value == "TRANSPORT_FAILURE")
    contract_failures = sum(1 for value in classifications if value == "CONTRACT_FAILURE")
    parse_failures = sum(1 for value in classifications if value == "PARSE_FAILURE")
    linkage_failures = sum(
        1
        for value in classifications
        if value in {"CROSS_SESSION_ARTIFACT_MISMATCH", "ACTIVE_SESSION_ARTIFACT_MISSING"}
    )
    research_blocking_failures = sum(
        1
        for value in classifications
        if value in {"CROSS_SESSION_ARTIFACT_MISMATCH", "ACTIVE_SESSION_ARTIFACT_MISSING", "STRUCTURAL_FAILURE"}
    )
    retryable_failures = sum(
        1
        for value in classifications
        if value in {"PROVIDER_FAILURE", "TRANSPORT_FAILURE", "CONTRACT_FAILURE", "PARSE_FAILURE"}
    )
    return {
        "provider_failures": provider_failures,
        "transport_failures": transport_failures,
        "contract_failures": contract_failures,
        "parse_failures": parse_failures,
        "linkage_failures": linkage_failures,
        "research_blocking_failures": research_blocking_failures,
        "retryable_failures": retryable_failures,
    }


def _campaign_notes(
    provider_rows: Sequence[Dict[str, Any]],
    failure_rows: Sequence[Dict[str, Any]],
    campaign_id: str,
    session_ids: Sequence[str],
) -> str:
    provider_notes = []
    for row in provider_rows:
        if _norm(row.get("campaign_id")) != campaign_id:
            continue
        provider = _norm(row.get("provider"))
        total_errors = sum(
            _safe_int(row.get(field))
            for field in [
                "artifact_linkage_failures",
                "provider_errors",
                "transport_errors",
                "parse_errors",
                "contract_errors",
            ]
        )
        if total_errors > 0:
            provider_notes.append(f"{provider}:{total_errors}")
    session_id_set = {session_id for session_id in session_ids if session_id}
    failure_notes = [
        _norm(row.get("failure_category"))
        for row in failure_rows
        if _norm(row.get("session_id")) in session_id_set and _norm(row.get("failure_category"))
    ]
    notes = []
    if provider_notes:
        notes.append(f"provider_error_sources={json.dumps(provider_notes)}")
    if failure_notes:
        notes.append(f"failure_categories_seen={json.dumps(sorted(set(failure_notes)))}")
    return " | ".join(notes)


def _run_status_rollup(
    session_ids: Sequence[str],
    run_status_rows: Sequence[Dict[str, Any]],
) -> Dict[str, int]:
    latest = _latest_by_key(run_status_rows, "session_id")
    candidate_rows = 0
    forecast_rows = 0
    evaluation_rows = 0
    for session_id in session_ids:
        row = latest.get(session_id, {})
        candidate_rows += _safe_int(row.get("phase7_candidate_rows"))
        forecast_rows += _safe_int(row.get("phase4_forecast_rows"))
        evaluation_rows += _safe_int(row.get("phase5_evaluation_rows"))
    return {
        "candidate_rows": candidate_rows,
        "forecast_rows": forecast_rows,
        "evaluation_rows": evaluation_rows,
    }


def _experiment_interpretation(summary_row: Dict[str, Any]) -> Tuple[str, str]:
    sessions_completed = _safe_int(summary_row.get("sessions_completed"))
    research_blocking_failures = _safe_int(summary_row.get("research_blocking_failures"))
    retryable_failures = _safe_int(summary_row.get("retryable_failures"))
    sessions_failed = _safe_int(summary_row.get("sessions_failed"))

    if sessions_completed == 0 and sessions_failed > 0:
        return ("FAIL", "PRESIGNAL_V2_EXPERIMENT_MANAGER_NEEDS_REVIEW")
    if research_blocking_failures > 0:
        return ("PASS_WITH_WARNINGS", "PRESIGNAL_V2_EXPERIMENT_MANAGER_READY")
    if retryable_failures > 0:
        return ("PASS_WITH_WARNINGS", "PRESIGNAL_V2_EXPERIMENT_MANAGER_READY")
    return ("PASS", "PRESIGNAL_V2_EXPERIMENT_MANAGER_READY")


def _comparison_rows(
    generated_ts: str,
    summary_rows: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    ordered = sorted(
        summary_rows,
        key=lambda row: (
            _norm(row.get("created_ts")),
            _norm(row.get("experiment_id")),
        ),
    )
    for row_a, row_b in combinations(ordered, 2):
        experiment_a = _norm(row_a.get("experiment_id"))
        experiment_b = _norm(row_b.get("experiment_id"))
        if not experiment_a or not experiment_b:
            continue
        rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "shadow_version": SHADOW_VERSION,
                "experiment_a": experiment_a,
                "experiment_b": experiment_b,
                "completed_sessions_delta": _safe_int(row_b.get("sessions_completed")) - _safe_int(row_a.get("sessions_completed")),
                "provider_failure_delta": _safe_int(row_b.get("provider_failures")) - _safe_int(row_a.get("provider_failures")),
                "transport_delta": _safe_int(row_b.get("transport_failures")) - _safe_int(row_a.get("transport_failures")),
                "candidate_delta": _safe_int(row_b.get("candidate_rows")) - _safe_int(row_a.get("candidate_rows")),
                "forecast_delta": _safe_int(row_b.get("forecast_rows")) - _safe_int(row_a.get("forecast_rows")),
                "evaluation_delta": _safe_int(row_b.get("evaluation_rows")) - _safe_int(row_a.get("evaluation_rows")),
                "notes": _norm(
                    f"{_norm(row_a.get('experiment_name'))} -> {_norm(row_b.get('experiment_name'))}"
                ),
            }
        )
    return rows


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
            "logical_sheet_id": "REPLAY_EXPERIMENTS",
            "physical_sheet_name": OUTPUT_EXPERIMENT_SHEET,
            "sheet_role": "v2_replay_experiments",
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
            "created_phase": "PreSignal v2.0 Phase 7.6",
            "notes": "shadow_v0 replay experiment links",
        },
        {
            "logical_sheet_id": "REPLAY_EXPERIMENT_SUMMARY",
            "physical_sheet_name": OUTPUT_SUMMARY_SHEET,
            "sheet_role": "v2_replay_experiment_summary",
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
            "created_phase": "PreSignal v2.0 Phase 7.6",
            "notes": "shadow_v0 replay experiment summary",
        },
        {
            "logical_sheet_id": "REPLAY_EXPERIMENT_COMPARISON",
            "physical_sheet_name": OUTPUT_COMPARISON_SHEET,
            "sheet_role": "v2_replay_experiment_comparison",
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
            "created_phase": "PreSignal v2.0 Phase 7.6",
            "notes": "shadow_v0 replay experiment comparison",
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
    parser = argparse.ArgumentParser(description="Build PreSignal v2 replay experiment manager v0.")
    parser.add_argument("--experiment-name", required=True)
    parser.add_argument("--experiment-description", default="")
    parser.add_argument("--campaign-id", action="append", default=[])
    return parser.parse_args(argv)


def build_presignal_v2_experiment_manager_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    if args is None:
        args = _parse_args([])

    creds = load_credentials(interactive=False)
    service = build_sheets_service(creds)
    generated_ts = _iso_now()
    created_ts = generated_ts

    campaign_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, CAMPAIGN_SHEET)
    campaign_summary_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, CAMPAIGN_SUMMARY_SHEET)
    campaign_provider_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, CAMPAIGN_PROVIDER_SHEET)
    run_status_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, RUN_STATUS_SHEET)
    failure_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, FAILURE_DIAGNOSTIC_SHEET)

    _require_headers(CAMPAIGN_SHEET, campaign_rows, ["campaign_id", "session_id", "campaign_session_classification"])
    _require_headers(
        CAMPAIGN_SUMMARY_SHEET,
        campaign_summary_rows,
        [
            "campaign_id",
            "campaign_name",
            "sessions_completed",
            "sessions_failed",
            "provider_failure_sessions",
            "transport_failure_sessions",
            "contract_failure_sessions",
            "parse_failure_sessions",
            "cross_session_mismatch_sessions",
            "missing_artifact_sessions",
            "structural_failure_sessions",
        ],
    )
    _require_headers(CAMPAIGN_PROVIDER_SHEET, campaign_provider_rows, ["campaign_id", "provider"])
    _require_headers(RUN_STATUS_SHEET, run_status_rows, ["session_id", "phase4_forecast_rows", "phase5_evaluation_rows", "phase7_candidate_rows"])
    _require_headers(FAILURE_DIAGNOSTIC_SHEET, failure_rows, ["session_id", "failure_category"])

    experiment_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_EXPERIMENT_SHEET, EXPERIMENT_HEADERS)
    summary_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)
    comparison_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_COMPARISON_SHEET, COMPARISON_HEADERS)

    existing_experiment_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_EXPERIMENT_SHEET)
    existing_summary_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET)

    selected_campaign_ids = _select_campaign_ids(args, campaign_summary_rows)
    campaign_summaries_by_id = _latest_by_key(campaign_summary_rows, "campaign_id")
    experiment_id = _experiment_id(args.experiment_name)

    experiment_rows: List[Dict[str, Any]] = []
    linked_session_ids: List[str] = []
    aggregate_failures = {
        "provider_failures": 0,
        "transport_failures": 0,
        "contract_failures": 0,
        "parse_failures": 0,
        "linkage_failures": 0,
        "research_blocking_failures": 0,
        "retryable_failures": 0,
    }
    sessions_completed = 0
    sessions_failed = 0

    for campaign_id in selected_campaign_ids:
        summary_row = campaign_summaries_by_id.get(campaign_id)
        if not summary_row:
            raise RuntimeError(f"Replay_Campaign_Summary missing campaign_id={campaign_id}")
        campaign_name = _norm(summary_row.get("campaign_name"))
        campaign_detail_rows = [row for row in campaign_rows if _norm(row.get("campaign_id")) == campaign_id]
        campaign_session_ids = [_norm(row.get("session_id")) for row in campaign_detail_rows if _norm(row.get("session_id"))]
        linked_session_ids.extend(campaign_session_ids)
        classifications = _classifications_for_campaign(campaign_rows, campaign_id)
        if not classifications:
            classifications = ["UNKNOWN_FAILURE"] * max(1, _safe_int(summary_row.get("sessions_failed")))
        failure_rollup = _failure_rollup(classifications)
        provider_notes = _campaign_notes(campaign_provider_rows, failure_rows, campaign_id, campaign_session_ids)

        sessions_completed += _safe_int(summary_row.get("sessions_completed"))
        sessions_failed += _safe_int(summary_row.get("sessions_failed"))
        for key in aggregate_failures:
            aggregate_failures[key] += failure_rollup[key]

        experiment_rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "shadow_version": SHADOW_VERSION,
                "experiment_id": experiment_id,
                "experiment_name": args.experiment_name,
                "experiment_description": args.experiment_description,
                "created_ts": created_ts,
                "campaign_id": campaign_id,
                "campaign_name": campaign_name,
                "campaign_generated_ts": _norm(summary_row.get("generated_ts")),
                "campaign_build_status": _norm(summary_row.get("build_status")),
                "campaign_final_interpretation": _norm(summary_row.get("final_interpretation")),
                "campaign_sessions_completed": _safe_int(summary_row.get("sessions_completed")),
                "campaign_sessions_failed": _safe_int(summary_row.get("sessions_failed")),
                "provider_failures": failure_rollup["provider_failures"],
                "transport_failures": failure_rollup["transport_failures"],
                "contract_failures": failure_rollup["contract_failures"],
                "parse_failures": failure_rollup["parse_failures"],
                "linkage_failures": failure_rollup["linkage_failures"],
                "research_blocking_failures": failure_rollup["research_blocking_failures"],
                "retryable_failures": failure_rollup["retryable_failures"],
                "notes": provider_notes,
            }
        )

    unique_session_ids = sorted({session_id for session_id in linked_session_ids if session_id})
    run_status_rollup = _run_status_rollup(unique_session_ids, run_status_rows)
    comparison_seed_rows = [row for row in existing_summary_rows if _norm(row.get("experiment_id")) != experiment_id]

    summary_row = {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "shadow_version": SHADOW_VERSION,
        "experiment_id": experiment_id,
        "experiment_name": args.experiment_name,
        "experiment_description": args.experiment_description,
        "created_ts": created_ts,
        "campaigns_linked": len(selected_campaign_ids),
        "sessions_completed": sessions_completed,
        "sessions_failed": sessions_failed,
        "provider_failures": aggregate_failures["provider_failures"],
        "transport_failures": aggregate_failures["transport_failures"],
        "contract_failures": aggregate_failures["contract_failures"],
        "parse_failures": aggregate_failures["parse_failures"],
        "linkage_failures": aggregate_failures["linkage_failures"],
        "research_blocking_failures": aggregate_failures["research_blocking_failures"],
        "retryable_failures": aggregate_failures["retryable_failures"],
        "candidate_rows": run_status_rollup["candidate_rows"],
        "forecast_rows": run_status_rollup["forecast_rows"],
        "evaluation_rows": run_status_rollup["evaluation_rows"],
        "comparison_rows": 0,
        "build_status": "",
        "final_interpretation": "",
        "notes": _norm(
            f"campaign_ids={json.dumps(selected_campaign_ids)}; linked_sessions={len(unique_session_ids)}"
        ),
    }
    build_status, final_interpretation = _experiment_interpretation(summary_row)
    summary_row["build_status"] = build_status
    summary_row["final_interpretation"] = final_interpretation

    all_summary_rows = comparison_seed_rows + [summary_row]
    comparison_rows = _comparison_rows(generated_ts, all_summary_rows)
    summary_row["comparison_rows"] = len(
        [row for row in comparison_rows if experiment_id in {_norm(row.get("experiment_a")), _norm(row.get("experiment_b"))}]
    )
    all_summary_rows = comparison_seed_rows + [summary_row]
    comparison_rows = _comparison_rows(generated_ts, all_summary_rows)

    _write_rows(
        service,
        DIAGNOSTICS_SPREADSHEET_ID,
        OUTPUT_EXPERIMENT_SHEET,
        experiment_headers,
        existing_experiment_rows + experiment_rows,
    )
    _write_rows(
        service,
        DIAGNOSTICS_SPREADSHEET_ID,
        OUTPUT_SUMMARY_SHEET,
        summary_headers,
        all_summary_rows,
    )
    _write_rows(
        service,
        DIAGNOSTICS_SPREADSHEET_ID,
        OUTPUT_COMPARISON_SHEET,
        comparison_headers,
        comparison_rows,
    )
    registry_result = _ensure_registry(service)

    return {
        "experiment_id": experiment_id,
        "campaigns_linked": len(selected_campaign_ids),
        "campaign_ids": selected_campaign_ids,
        "sessions_summarized": sessions_completed + sessions_failed,
        "comparison_rows": len(
            [row for row in comparison_rows if experiment_id in {_norm(row.get("experiment_a")), _norm(row.get("experiment_b"))}]
        ),
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "registry_result": registry_result,
    }


def main() -> None:
    print(json.dumps(build_presignal_v2_experiment_manager_v0(_parse_args()), ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
