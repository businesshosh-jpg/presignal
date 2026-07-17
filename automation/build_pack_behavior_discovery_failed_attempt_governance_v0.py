import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

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
from automation.build_session_information_requests_v0 import _iso_now, _truncate_text
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


SCHEMA_VERSION = "presignal_v2_behavior_discovery_rerun_governance_0.1"
GOVERNANCE_VERSION = "phase9a4x_failed_attempt_governance_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-4X-G"
REGISTRY_CATEGORY = "PRESIGNAL_V2_BEHAVIOR_DISCOVERY_RERUN_GOVERNANCE"
REGISTRY_OWNER_MODULE = "market_state"

RUNNER_PATH = ROOT / "automation" / "build_pack_behavior_discovery_execution_v0.py"

OUTPUT_FAILED_ATTEMPT_SHEET = "Pack_Behavior_Discovery_Failed_Attempt_Governance"
OUTPUT_RERUN_APPROVAL_SHEET = "Pack_Behavior_Discovery_Rerun_Approval"
OUTPUT_RERUN_GUARDRAILS_SHEET = "Pack_Behavior_Discovery_Rerun_Guardrails"
OUTPUT_SUMMARY_SHEET = "Pack_Behavior_Discovery_Governance_Summary"

PHASE9A4X_OUTPUT_SHEETS = [
    "Pack_Behavior_Discovery_Runs",
    "Pack_Behavior_Discovery_Forecasts",
    "Pack_Behavior_Discovery_Metadata",
    "Pack_Behavior_Discovery_Behavior",
    "Pack_Behavior_Discovery_Raw_Response_Archive",
    "Pack_Behavior_Discovery_Transitions",
    "Pack_Behavior_Discovery_Field_Influence",
    "Pack_Behavior_Discovery_NoSignal",
    "Pack_Behavior_Discovery_Invalid_Output",
    "Pack_Behavior_Discovery_Run_Log",
    "Pack_Behavior_Discovery_Run_Summary",
]

RESEARCH_OUTPUT_SHEETS = [
    sheet for sheet in PHASE9A4X_OUTPUT_SHEETS if sheet != "Pack_Behavior_Discovery_Raw_Response_Archive"
]

FAILED_ATTEMPT_HEADERS = [
    "generated_ts",
    "schema_version",
    "governance_version",
    "governance_id",
    "phase",
    "attempt_label",
    "attempt_classification",
    "failure_mode",
    "failure_location",
    "error_text",
    "approved_call_budget",
    "suspected_provider_calls_attempted",
    "persisted_raw_response_count",
    "persisted_forecast_count",
    "persisted_behavior_count",
    "persisted_transition_count",
    "usable_research_evidence",
    "completed_tier1_batch",
    "counts_toward_pattern_discovery",
    "counts_toward_call_budget_as_completed_batch",
    "recommended_handling",
    "notes",
]

RERUN_APPROVAL_HEADERS = [
    "generated_ts",
    "schema_version",
    "governance_version",
    "governance_id",
    "rerun_approval_id",
    "rerun_decision",
    "approved_phase",
    "approved_execution_tier",
    "approved_session_count",
    "approved_pack_levels",
    "approved_providers",
    "approved_provider_call_cap",
    "approved_retry_count",
    "requires_raw_archive_first",
    "requires_immediate_raw_append",
    "requires_dedupe_key",
    "requires_append_retry",
    "requires_stop_on_raw_archive_failure",
    "requires_new_run_id",
    "requires_original_failed_attempt_preserved",
    "approval_reason",
    "approval_limitations",
    "notes",
]

RERUN_GUARDRAIL_HEADERS = [
    "generated_ts",
    "schema_version",
    "governance_version",
    "guardrail_id",
    "guardrail_name",
    "guardrail_requirement",
    "blocking",
    "verification_method",
    "failure_action",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "governance_version",
    "build_status",
    "final_interpretation",
    "governance_decision",
    "failed_attempt_classification",
    "failed_attempt_usable_research_evidence",
    "failed_attempt_completed_tier1_batch",
    "persisted_raw_response_count",
    "persisted_research_output_count",
    "rerun_approved",
    "approved_provider_call_cap",
    "approved_session_count",
    "approved_retry_count",
    "raw_archive_first_required",
    "immediate_raw_append_required",
    "stop_on_raw_archive_failure_required",
    "new_run_id_required",
    "accuracy_evaluation_count",
    "provider_call_count_this_governance_task",
    "forecast_generation_count_this_governance_task",
    "production_behavior_change_count",
    "recommended_next_step",
    "notes",
]


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _governance_id(generated_ts: str) -> str:
    stamp = generated_ts.replace("-", "").replace(":", "").replace("+00:00", "Z").replace(".", "")
    return f"phase9a4x_failed_attempt_governance_{stamp}"


def _sheet_titles(service, spreadsheet_id: str) -> Set[str]:
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return {sheet["properties"]["title"] for sheet in meta.get("sheets", [])}


def _rows_if_exists(service, spreadsheet_id: str, titles: Set[str], sheet_name: str) -> List[Dict[str, Any]]:
    if sheet_name not in titles:
        return []
    return _sheet_to_rows(service, spreadsheet_id, sheet_name)


def _row_counts_by_sheet(service, spreadsheet_id: str, titles: Set[str], sheet_names: Sequence[str]) -> Dict[str, int]:
    return {sheet: len(_rows_if_exists(service, spreadsheet_id, titles, sheet)) for sheet in sheet_names}


def _verify_runner_repair(source_text: str) -> Dict[str, bool]:
    raw_create_index = source_text.find("raw_headers = _ensure_sheet")
    provider_call_index = source_text.find("response = _call_live_provider_raw")
    append_index = source_text.find("raw_rows_archived += _append_unique_rows")
    return {
        "raw_archive_sheet_created_before_provider_calls": raw_create_index >= 0 and provider_call_index >= 0 and raw_create_index < provider_call_index,
        "raw_response_appended_immediately_after_each_provider_response": provider_call_index >= 0 and append_index >= 0 and provider_call_index < append_index,
        "raw_response_archive_key_required": "raw_response_archive_key" in source_text and "raw_key =" in source_text,
        "dedupe_behavior_present": "existing_keys" in source_text and "raw_response_archive_key" in source_text,
        "append_retry_behavior_present": "for attempt in range(3)" in source_text and "time.sleep" in source_text,
        "stop_on_raw_archive_failure_present": "Failed to append raw archive rows after retries" in source_text and "raise RuntimeError" in source_text,
    }


def _failed_attempt_row(
    generated_ts: str,
    governance_id: str,
    persisted_counts: Dict[str, int],
) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "governance_version": GOVERNANCE_VERSION,
        "governance_id": governance_id,
        "phase": "Phase 9A-4X",
        "attempt_label": "FIRST_TIER1_ATTEMPT",
        "attempt_classification": "VOID_UNARCHIVED_ATTEMPT",
        "failure_mode": "SHEETS_CONNECTION_RESET_DURING_POST_CALL_WRITE",
        "failure_location": "raw_archive_sheet_creation_after_provider_call_loop",
        "error_text": "ConnectionResetError: [Errno 54] Connection reset by peer",
        "approved_call_budget": 45,
        "suspected_provider_calls_attempted": "UNKNOWN_OR_UP_TO_45",
        "persisted_raw_response_count": persisted_counts.get("Pack_Behavior_Discovery_Raw_Response_Archive", 0),
        "persisted_forecast_count": persisted_counts.get("Pack_Behavior_Discovery_Forecasts", 0),
        "persisted_behavior_count": persisted_counts.get("Pack_Behavior_Discovery_Behavior", 0),
        "persisted_transition_count": persisted_counts.get("Pack_Behavior_Discovery_Transitions", 0),
        "usable_research_evidence": "FALSE",
        "completed_tier1_batch": "FALSE",
        "counts_toward_pattern_discovery": "FALSE",
        "counts_toward_call_budget_as_completed_batch": "FALSE",
        "recommended_handling": "APPROVE_FRESH_RERUN_ONLY_IF_RAW_ARCHIVE_FIRST_REPAIR_CONFIRMED",
        "notes": "Attempt may have consumed provider calls externally, but no persisted raw responses or research rows exist, so it is not usable evidence.",
    }


def _approval_row(generated_ts: str, governance_id: str, decision: str, verification: Dict[str, bool]) -> Dict[str, Any]:
    approved = decision == "APPROVE_ONE_FRESH_TIER1_RERUN"
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "governance_version": GOVERNANCE_VERSION,
        "governance_id": governance_id,
        "rerun_approval_id": f"{governance_id}_rerun_approval",
        "rerun_decision": decision,
        "approved_phase": "Phase 9A-4X" if approved else "",
        "approved_execution_tier": "TIER_1_SMALL_EXPANSION" if approved else "",
        "approved_session_count": 3 if approved else 0,
        "approved_pack_levels": "Pack A|Pack B|Pack C|Pack D|Pack E" if approved else "",
        "approved_providers": "OpenAI|Gemini|Anthropic" if approved else "",
        "approved_provider_call_cap": 45 if approved else 0,
        "approved_retry_count": 0,
        "requires_raw_archive_first": "TRUE",
        "requires_immediate_raw_append": "TRUE",
        "requires_dedupe_key": "TRUE",
        "requires_append_retry": "TRUE",
        "requires_stop_on_raw_archive_failure": "TRUE",
        "requires_new_run_id": "TRUE",
        "requires_original_failed_attempt_preserved": "TRUE",
        "approval_reason": "VOID_UNARCHIVED_ATTEMPT has no persisted research evidence and repaired runner verifies raw-archive-first behavior." if approved else "Rerun not approved because persisted outputs or repair verification failed.",
        "approval_limitations": "One fresh Tier 1 rerun only; 45 provider-call cap; zero retries; no accuracy evaluation; no production writes.",
        "notes": _truncate_text(json.dumps(verification, sort_keys=True), 500),
    }


def _guardrail_rows(generated_ts: str) -> List[Dict[str, Any]]:
    definitions = [
        ("GBD_RG_001", "raw_archive_sheet_created_before_provider_calls", "Create and verify raw archive sheet before any provider call.", "source_code_inspection", "STOP_EXECUTION_IMMEDIATELY"),
        ("GBD_RG_002", "raw_response_appended_immediately_after_each_provider_response", "Append each raw response before any later derived output write.", "source_code_inspection", "STOP_EXECUTION_IMMEDIATELY"),
        ("GBD_RG_003", "raw_response_archive_key_required", "Every raw response row must carry a deterministic raw_response_archive_key.", "source_code_inspection", "STOP_EXECUTION_IMMEDIATELY"),
        ("GBD_RG_004", "raw_archive_dedupe_required", "Raw archive append must skip existing raw_response_archive_key rows.", "source_code_inspection", "STOP_EXECUTION_IMMEDIATELY"),
        ("GBD_RG_005", "raw_archive_append_retry_required", "Transient raw archive append failures must be retried.", "source_code_inspection", "STOP_EXECUTION_IMMEDIATELY"),
        ("GBD_RG_006", "stop_if_raw_archive_append_fails", "If raw archive append fails after retries, stop execution immediately.", "source_code_inspection", "STOP_EXECUTION_IMMEDIATELY"),
        ("GBD_RG_007", "provider_call_cap_45", "Fresh Tier 1 rerun must not exceed 45 provider calls.", "summary_review", "STOP_EXECUTION_IMMEDIATELY"),
        ("GBD_RG_008", "no_automatic_retry_provider_calls", "Provider calls must not be automatically retried inside analysis phases.", "execution_review", "HOLD_FOR_REVIEW"),
        ("GBD_RG_009", "new_run_id_required", "Fresh rerun must use a new discovery_run_id.", "summary_review", "HOLD_FOR_REVIEW"),
        ("GBD_RG_010", "failed_attempt_marked_void", "The failed unarchived attempt must be classified as VOID_UNARCHIVED_ATTEMPT.", "governance_summary", "HOLD_FOR_REVIEW"),
        ("GBD_RG_011", "failed_attempt_excluded_from_pattern_metrics", "Void attempt must be excluded from pattern metrics.", "governance_summary", "HOLD_FOR_REVIEW"),
        ("GBD_RG_012", "no_accuracy_evaluation", "No accuracy evaluation is allowed in governance or rerun execution.", "summary_safety_counter", "STOP_EXECUTION_IMMEDIATELY"),
        ("GBD_RG_013", "no_production_writes", "No production/v1 sheets or production behavior may be modified.", "summary_safety_counter", "STOP_EXECUTION_IMMEDIATELY"),
        ("GBD_RG_014", "no_provider_ranking", "No provider ranking is allowed.", "output_review", "HOLD_FOR_REVIEW"),
        ("GBD_RG_015", "no_pack_ranking", "No pack ranking is allowed.", "output_review", "HOLD_FOR_REVIEW"),
    ]
    rows = []
    for guardrail_id, name, requirement, method, failure_action in definitions:
        rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "governance_version": GOVERNANCE_VERSION,
                "guardrail_id": guardrail_id,
                "guardrail_name": name,
                "guardrail_requirement": requirement,
                "blocking": "TRUE",
                "verification_method": method,
                "failure_action": failure_action,
                "notes": "Mandatory guardrail for one approved fresh Tier 1 rerun.",
            }
        )
    return rows


def _upsert_registry_rows(service) -> Dict[str, int]:
    headers = _ensure_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_upper(row.get("logical_sheet_id")): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_upper(row.get("logical_sheet_id")): row for row in rows}
    registry_rows = [
        ("PACK_BEHAVIOR_DISCOVERY_FAILED_ATTEMPT_GOVERNANCE", OUTPUT_FAILED_ATTEMPT_SHEET, "behavior_discovery_failed_attempt_governance"),
        ("PACK_BEHAVIOR_DISCOVERY_RERUN_APPROVAL", OUTPUT_RERUN_APPROVAL_SHEET, "behavior_discovery_rerun_approval"),
        ("PACK_BEHAVIOR_DISCOVERY_RERUN_GUARDRAILS", OUTPUT_RERUN_GUARDRAILS_SHEET, "behavior_discovery_rerun_guardrails"),
        ("PACK_BEHAVIOR_DISCOVERY_GOVERNANCE_SUMMARY", OUTPUT_SUMMARY_SHEET, "behavior_discovery_governance_summary"),
    ]
    updates: List[Dict[str, Any]] = []
    appended = 0
    for logical_id, sheet_name, role in registry_rows:
        key = _upper(logical_id)
        existing = existing_by_id.get(key, {})
        merged = {
            "logical_sheet_id": logical_id,
            "physical_sheet_name": sheet_name,
            "sheet_role": role,
            "workbook": "DIAGNOSTICS",
            "workbook_location": "DIAGNOSTICS",
            "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
            "category": REGISTRY_CATEGORY,
            "lifecycle": "active_shadow_governance",
            "lifecycle_state": "ACTIVE",
            "owner_module": REGISTRY_OWNER_MODULE,
            "participates_in_rebuild": "TRUE",
            "read_only": "FALSE",
            "allow_creation": "TRUE",
            "created_phase": PHASE_LABEL,
            "notes": "Phase 9A-4X-G failed-attempt governance and one-rerun approval; no provider calls.",
            "registry_created_ts": _norm(existing.get("registry_created_ts")) or now,
            "registry_last_verified_ts": now,
            "registry_migration_ts": _norm(existing.get("registry_migration_ts")),
            "registry_rename_ts": _norm(existing.get("registry_rename_ts")),
        }
        values = [merged.get(header, "") for header in headers]
        row_number = by_id.get(key)
        if not row_number:
            appended += 1
            row_number = len(rows) + appended + 1
        updates.append({"range": f"'{REGISTRY_SHEET}'!A{row_number}:{_column_letter(len(headers))}{row_number}", "values": [values]})
    if updates:
        batch_update_values(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, updates)
    return {"updated": len(registry_rows) - appended, "appended": appended}


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Phase 9A-4X-G failed-attempt rerun governance sheets.")
    return parser.parse_args(argv)


def build_pack_behavior_discovery_failed_attempt_governance_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    args = args or _parse_args()
    generated_ts = _iso_now()
    governance_id = _governance_id(generated_ts)
    service = build_sheets_service(load_credentials())
    titles = _sheet_titles(service, DIAGNOSTICS_SPREADSHEET_ID)

    persisted_counts = _row_counts_by_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, titles, PHASE9A4X_OUTPUT_SHEETS)
    raw_count = persisted_counts.get("Pack_Behavior_Discovery_Raw_Response_Archive", 0)
    research_count = sum(persisted_counts.get(sheet, 0) for sheet in RESEARCH_OUTPUT_SHEETS)

    source_text = RUNNER_PATH.read_text(encoding="utf-8") if RUNNER_PATH.exists() else ""
    repair_verification = _verify_runner_repair(source_text)
    repair_confirmed = all(repair_verification.values())

    if raw_count > 0 or research_count > 0:
        decision = "HOLD_PENDING_MANUAL_REVIEW"
        build_status = "PASS_WITH_WARNINGS"
        final_interpretation = "BEHAVIOR_DISCOVERY_RERUN_GOVERNANCE_NEEDS_REVIEW"
        recommended_next_step = "HOLD_PENDING_MANUAL_REVIEW"
    elif not repair_confirmed:
        decision = "DENY_RERUN_HOLD_FOR_REPAIR"
        build_status = "PASS_WITH_WARNINGS"
        final_interpretation = "BEHAVIOR_DISCOVERY_RERUN_GOVERNANCE_NEEDS_REVIEW"
        recommended_next_step = "RUN_PHASE9A4X_REPAIR_FIRST"
    else:
        decision = "APPROVE_ONE_FRESH_TIER1_RERUN"
        build_status = "PASS_WITH_WARNINGS"
        final_interpretation = "BEHAVIOR_DISCOVERY_RERUN_GOVERNANCE_APPROVED_WITH_WARNINGS"
        recommended_next_step = "PROCEED_TO_PHASE9A4X_TIER1_RERUN"

    failed_rows = [_failed_attempt_row(generated_ts, governance_id, persisted_counts)]
    approval_rows = [_approval_row(generated_ts, governance_id, decision, repair_verification)]
    guardrail_rows = _guardrail_rows(generated_ts)
    summary = {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "governance_version": GOVERNANCE_VERSION,
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "governance_decision": decision,
        "failed_attempt_classification": "VOID_UNARCHIVED_ATTEMPT",
        "failed_attempt_usable_research_evidence": "FALSE",
        "failed_attempt_completed_tier1_batch": "FALSE",
        "persisted_raw_response_count": raw_count,
        "persisted_research_output_count": research_count,
        "rerun_approved": "TRUE" if decision == "APPROVE_ONE_FRESH_TIER1_RERUN" else "FALSE",
        "approved_provider_call_cap": 45 if decision == "APPROVE_ONE_FRESH_TIER1_RERUN" else 0,
        "approved_session_count": 3 if decision == "APPROVE_ONE_FRESH_TIER1_RERUN" else 0,
        "approved_retry_count": 0,
        "raw_archive_first_required": "TRUE",
        "immediate_raw_append_required": "TRUE",
        "stop_on_raw_archive_failure_required": "TRUE",
        "new_run_id_required": "TRUE",
        "accuracy_evaluation_count": 0,
        "provider_call_count_this_governance_task": 0,
        "forecast_generation_count_this_governance_task": 0,
        "production_behavior_change_count": 0,
        "recommended_next_step": recommended_next_step,
        "notes": _truncate_text(
            json.dumps(
                {
                    "phase9a4x_output_row_counts": persisted_counts,
                    "repair_verification": repair_verification,
                    "warning": "failed attempt may have consumed provider calls externally but no research artifacts persisted",
                },
                sort_keys=True,
            ),
            500,
        ),
    }

    for sheet, headers, rows in [
        (OUTPUT_FAILED_ATTEMPT_SHEET, FAILED_ATTEMPT_HEADERS, failed_rows),
        (OUTPUT_RERUN_APPROVAL_SHEET, RERUN_APPROVAL_HEADERS, approval_rows),
        (OUTPUT_RERUN_GUARDRAILS_SHEET, RERUN_GUARDRAIL_HEADERS, guardrail_rows),
        (OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS, [summary]),
    ]:
        sheet_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, sheet, headers)
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet, sheet_headers, rows)
    registry = _upsert_registry_rows(service)
    return {
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "governance_decision": decision,
        "governance_id": governance_id,
        "failed_attempt_classification": "VOID_UNARCHIVED_ATTEMPT",
        "failed_attempt_usable_research_evidence": False,
        "failed_attempt_completed_tier1_batch": False,
        "persisted_raw_response_count": raw_count,
        "persisted_research_output_count": research_count,
        "rerun_approved": decision == "APPROVE_ONE_FRESH_TIER1_RERUN",
        "approved_provider_call_cap": 45 if decision == "APPROVE_ONE_FRESH_TIER1_RERUN" else 0,
        "approved_session_count": 3 if decision == "APPROVE_ONE_FRESH_TIER1_RERUN" else 0,
        "approved_retry_count": 0,
        "repair_verification": repair_verification,
        "accuracy_evaluation_count": 0,
        "provider_call_count_this_governance_task": 0,
        "forecast_generation_count_this_governance_task": 0,
        "production_behavior_change_count": 0,
        "sheets_written": {
            OUTPUT_FAILED_ATTEMPT_SHEET: len(failed_rows),
            OUTPUT_RERUN_APPROVAL_SHEET: len(approval_rows),
            OUTPUT_RERUN_GUARDRAILS_SHEET: len(guardrail_rows),
            OUTPUT_SUMMARY_SHEET: 1,
        },
        "registry": registry,
        "recommended_next_step": recommended_next_step,
    }


def main() -> None:
    result = build_pack_behavior_discovery_failed_attempt_governance_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
