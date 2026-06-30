import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_sheet_registry_audit import build_sheet_registry_audit
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials
from googleapiclient.errors import HttpError


MAIN_ID = os.environ.get("PRESIGNAL_MAIN_SPREADSHEET_ID", "1_gZGnd6h3VzdiBvGBHRSxn78KW8tsOi2UEc6Y_Sc23Q")
DIAGNOSTICS_ID = os.environ.get("PRESIGNAL_DIAGNOSTICS_SPREADSHEET_ID", "1jxcZotbzJKcAzrK0VhxetYX6hp5DPXCCIA0J6B6RUy0")
ARCHIVE_ID = os.environ.get("PRESIGNAL_ARCHIVE_01_SPREADSHEET_ID", "12hi1rugE_F-MhlupgmL13BIagerzA8CZkm1sk_nHPSg")
OVERVIEW_ID = os.environ.get("PRESIGNAL_PROJECT_OVERVIEWS_SPREADSHEET_ID", "1PtXrQpzNX8600I0aCOb2hLPkWtTvFKtDVIZZIys_Uvo")

WORKBOOKS = {
    "MAIN": {"id": MAIN_ID, "name": "auto_eeresults_predictions"},
    "DIAGNOSTICS": {"id": DIAGNOSTICS_ID, "name": "presignal_research_diagnostics"},
    "ARCHIVE_01": {"id": ARCHIVE_ID, "name": "presignal_diagnostics_archive_01"},
    "PROJECT_OVERVIEWS": {"id": OVERVIEW_ID, "name": "project_overviews"},
}

AUDIT_SHEET = "Workbook_Overhaul_Transition_Audit"
REGISTRY_SHEET = "Sheet_Registry"
MIGRATION_CONTROL_SHEET = "Workbook_Migration_Control"
MIGRATION_LOG_SHEET = "Workbook_Migration_Log"
TRANSITION_BATCH_ID = "OVERHAUL_2026_06_30"

AUDIT_HEADERS = [
    "generated_ts",
    "audit_phase",
    "workbook",
    "sheet_name",
    "current_location",
    "recommended_action",
    "final_action",
    "target_location",
    "lifecycle_label",
    "dependency_status",
    "archive_status",
    "notes",
]

MAIN_KEEP = {
    "Event",
    "Predictions",
    "Config",
    "log",
    "SeriesMap",
    "SeriesMap_Suggestions",
    "FRED_Series_ID",
    "FMP_EventCatalog",
    "MR_ProviderRuns",
    "Evaluation_Rows",
    "Evaluation_Summary",
    "Evaluation_BatchCompare",
    "Evaluation_Scenario",
    "Outcome_Ledger",
}

FOUNDATION_KEEP = {
    "Outcome_Diagnostics",
    "Outcome_Summary_Bucket",
    "Outcome_Summary_Convergence",
    "Outcome_Summary_ProviderFamily",
    "Economic_Value_Accuracy",
    "Provider_Family_Economic_Accuracy",
    "Economic_To_Market_Translation_Errors",
}

RISK_TEMP_KEEP = {
    "Market_Sensitivity_Filter_Candidates",
    "Market_Sensitivity_Filter_Summary",
    "Market_Sensitivity_NoSignal_Counterfactuals",
    "Inflation_NoSignal_Review",
}

PROJECT_KEEP = {
    "Sheet_Registry",
    "Sheet_Registry_Audit",
    "Workbook_Migration_Audit",
    "Workbook_Routing_Dependency_Audit",
    "Workbook_Migration_Phase2C_Report",
    "Experiment_Lifecycle_Audit",
    "Experiment_Lifecycle_Summary",
    "Workbook_Migration_Phase2E_Report",
    "Workbook_Migration_Control",
    "Workbook_Migration_Log",
    "Workbook_Migration_Post2F_Sanity_Audit",
    AUDIT_SHEET,
}

PROJECT_ARCHIVE_CANDIDATES = {
    "Current_Roadmap",
    "Project_Status",
    "Research_Journey",
    "PreSignal_Layer_Map",
    "Experiment_Register",
    "Interpretation_Corrections",
    "Decision_Log_v2",
    "Signal_Synchrony_v1",
}

CHARACTER_EXACT = {
    "Provider_Character_Residuals",
    "Provider_Character_Diagnostics",
    "Provider_Character_Summary",
    "Provider_Character_Family_Summary",
    "Provider_Character_Outcome_Layer_Audit",
    "Provider_Character_Translation_Reinterpretation",
    "Provider_Character_Economic_Rebuild_Plan",
    "Provider_Character_Methodology_Summary",
    "Character_Baseline_E",
    "Character_Disagreement_Report",
    "Character_Drift_Assessment",
    "Character_Recurrence_Validation",
    "Character_Recurrence_Family_Validation",
}
CHARACTER_PREFIXES = [
    "Provider_Character_Direct_Expression_",
    "Provider_Character_Fresh_",
    "Provider_Character_RawOutput_",
    "Provider_Character_MicroExpression_",
    "Character_Economic_",
    "Character_Understanding_Pattern_",
    "Character_Learning_",
]

SYNCHRONY_EXACT = {
    "Signal_Synchrony_Cohort_Characterization",
    "Signal_Synchrony_Cohort_Characterization_Summary",
    "Signal_Synchrony_Rerun_Count_Sufficiency",
    "Signal_Synchrony_Rerun_Count_Summary",
    "Signal_Synchrony_Provider_Slice_Performance",
    "Signal_Synchrony_Provider_Slice_Summary",
    "Signal_Synchrony_Family_Slice_Performance",
    "Signal_Synchrony_Family_Slice_Summary",
    "Signal_Synchrony_Conditional_Value_Audit",
    "Signal_Synchrony_Conditional_Value_Summary",
    "Signal_Synchrony_Conditional_Value_Stability",
    "Signal_Synchrony_Conditional_Value_Stability_Summary",
    "Signal_Synchrony_Conditional_Value_Mechanism",
    "Signal_Synchrony_Conditional_Value_Mechanism_Summary",
    "Signal_Synchrony_Provider_Dep_Falsification",
    "Signal_Synchrony_Provider_Dep_Falsification_Summary",
    "Signal_Synchrony_Accuracy_Audit",
    "Signal_Synchrony_Accuracy_Summary",
    "Signal_Synchrony_Direction_Robustness",
    "Signal_Synchrony_Direction_Robustness_Summary",
    "Signal_Synchrony_Interaction_Model_Audit",
    "Signal_Synchrony_Interaction_Model_Summary",
    "Signal_Synchrony_Interaction_Replay_Validation",
    "Signal_Synchrony_Interaction_Replay_Summary",
}

FEATURE_ARCHIVE = {
    "Feature_Pack_Audit",
    "Surprise_Pack_Coverage_Report",
    "Feature_Pack_v2B_Core_Audit",
    "Market_Context_Source_Validation_Report",
    "Market_Context_Data_Sanity_Report",
    "Market_Context_Provider_Repair_Report",
    "V2B_Context_Consumption_Audit",
    "V2B_Context_Utilization_Report",
    "Production_vs_V2B_Replay",
    "Production_vs_V2B_Summary",
    "Production_vs_V2B_Provider_Summary",
    "Production_vs_V2B_Family_Summary",
    "V2B_Prediction_Stability",
}


@dataclass
class SheetSnapshot:
    workbook: str
    spreadsheet_id: str
    title: str
    sheet_id: int
    values: List[List[Any]]

    @property
    def row_count(self) -> int:
        return len(self.values)

    @property
    def col_count(self) -> int:
        return max((len(r) for r in self.values), default=0)

    @property
    def header(self) -> List[Any]:
        return self.values[0] if self.values else []

    @property
    def is_empty(self) -> bool:
        for row in self.values:
            for cell in row:
                if _norm(cell) != "":
                    return False
        return True

    @property
    def data_hash(self) -> str:
        payload = json.dumps(self.values, ensure_ascii=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @property
    def header_hash(self) -> str:
        payload = json.dumps(self.header, ensure_ascii=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _norm(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return str(value).strip()


def _key(value: Any) -> str:
    return (
        _norm(value)
        .upper()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("/", "_")
        .replace("__", "_")
    )


def _now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _column_letter(index: int) -> str:
    letters = []
    n = index
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters.append(chr(65 + rem))
    return "".join(reversed(letters or ["A"]))


def _read_values(service, spreadsheet_id: str, sheet_name: str) -> List[List[Any]]:
    last_error = None
    for attempt in range(5):
        try:
            return (
                service.spreadsheets()
                .values()
                .get(spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!A1:ZZZ")
                .execute()
                .get("values", [])
            )
        except HttpError as exc:
            last_error = exc
            if getattr(exc, "resp", None) is not None and int(exc.resp.status) == 429 and attempt < 4:
                time.sleep(20 * (attempt + 1))
                continue
            raise
    if last_error:
        raise last_error
    return []


def _get_workbook_meta(service, spreadsheet_id: str) -> Dict[str, Any]:
    return service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()


def _inventory_workbook(service, workbook: str) -> Dict[str, SheetSnapshot]:
    spreadsheet_id = WORKBOOKS[workbook]["id"]
    meta = _get_workbook_meta(service, spreadsheet_id)
    out: Dict[str, SheetSnapshot] = {}
    for sheet in meta.get("sheets", []):
        title = sheet["properties"]["title"]
        sheet_id = sheet["properties"]["sheetId"]
        out[title] = SheetSnapshot(workbook, spreadsheet_id, title, sheet_id, [])
    return out


def _materialize_snapshot(service, snapshot: Optional[SheetSnapshot]) -> Optional[SheetSnapshot]:
    if snapshot is None:
        return None
    if snapshot.values:
        return snapshot
    return SheetSnapshot(
        workbook=snapshot.workbook,
        spreadsheet_id=snapshot.spreadsheet_id,
        title=snapshot.title,
        sheet_id=snapshot.sheet_id,
        values=_read_values(service, snapshot.spreadsheet_id, snapshot.title),
    )


def _ensure_sheet(service, spreadsheet_id: str, sheet_name: str, required_headers: Sequence[str]) -> List[str]:
    meta = _get_workbook_meta(service, spreadsheet_id)
    titles = {s["properties"]["title"] for s in meta.get("sheets", [])}
    if sheet_name not in titles:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]},
        ).execute()
        headers = list(required_headers)
    else:
        values = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!1:1")
            .execute()
            .get("values", [])
        )
        headers = values[0] if values else []
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


def _clear_sheet_body(service, spreadsheet_id: str, sheet_name: str) -> None:
    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_name}'!A2:ZZZ",
    ).execute()


def _write_rows(service, spreadsheet_id: str, sheet_name: str, headers: Sequence[str], rows: Sequence[Dict[str, Any]], start_row: int = 2) -> None:
    if not rows:
        return
    values = [[row.get(header, "") for header in headers] for row in rows]
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_name}'!A{start_row}",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()


def _find_sheet_meta(meta: Dict[str, Any], title: str) -> Optional[Dict[str, Any]]:
    for sheet in meta.get("sheets", []):
        if sheet["properties"]["title"] == title:
            return sheet
    return None


def _copy_sheet(service, source: SheetSnapshot, dest_workbook: str, dest_title: str) -> Tuple[int, str]:
    result = (
        service.spreadsheets()
        .sheets()
        .copyTo(
            spreadsheetId=source.spreadsheet_id,
            sheetId=source.sheet_id,
            body={"destinationSpreadsheetId": WORKBOOKS[dest_workbook]["id"]},
        )
        .execute()
    )
    new_sheet_id = result["sheetId"]
    service.spreadsheets().batchUpdate(
        spreadsheetId=WORKBOOKS[dest_workbook]["id"],
        body={
            "requests": [
                {
                    "updateSheetProperties": {
                        "properties": {"sheetId": new_sheet_id, "title": dest_title},
                        "fields": "title",
                    }
                }
            ]
        },
    ).execute()
    return new_sheet_id, dest_title


def _delete_sheet(service, workbook: str, sheet_id: int) -> None:
    service.spreadsheets().batchUpdate(
        spreadsheetId=WORKBOOKS[workbook]["id"],
        body={"requests": [{"deleteSheet": {"sheetId": sheet_id}}]},
    ).execute()


def _compare_snapshots(left: SheetSnapshot, right: SheetSnapshot) -> bool:
    return (
        left.row_count == right.row_count
        and left.col_count == right.col_count
        and left.header == right.header
        and left.data_hash == right.data_hash
    )


def _deterministic_archive_name(sheet_name: str, source_workbook: str) -> str:
    if sheet_name == "Sheet22":
        return "Archived_Sheet22_from_MAIN"
    suffix = source_workbook.replace("PROJECT_OVERVIEWS", "PROJECT").replace("ARCHIVE_01", "ARCHIVE")
    candidate = f"{sheet_name}__from_{suffix}"
    return candidate[:99]


def _read_registry(service) -> Tuple[List[str], List[Dict[str, Any]]]:
    headers = _ensure_sheet(service, OVERVIEW_ID, REGISTRY_SHEET, [
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
    ])
    values = _read_values(service, OVERVIEW_ID, REGISTRY_SHEET)
    rows = []
    for raw in values[1:]:
        padded = list(raw) + [""] * (len(headers) - len(raw))
        rows.append({headers[i]: padded[i] for i in range(len(headers))})
    return headers, rows


def _upsert_registry_rows(
    service,
    moved_rows: Sequence[Dict[str, Any]],
    extra_rows: Sequence[Dict[str, Any]],
) -> Dict[str, int]:
    headers, rows = _read_registry(service)
    by_logical: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        by_logical[_key(row.get("logical_sheet_id") or row.get("physical_sheet_name"))] = row

    updated = 0
    created = 0
    now = _now()
    desired = list(moved_rows) + list(extra_rows)
    for move in desired:
        logical = move["logical_sheet_id"]
        record = by_logical.get(_key(logical))
        if record is None:
            record = {header: "" for header in headers}
            record["logical_sheet_id"] = logical
            record["registry_created_ts"] = now
            rows.append(record)
            by_logical[_key(logical)] = record
            created += 1
        else:
            updated += 1
        for key, value in move.items():
            record[key] = value
        record["registry_last_verified_ts"] = now

    _clear_sheet_body(service, OVERVIEW_ID, REGISTRY_SHEET)
    _write_rows(service, OVERVIEW_ID, REGISTRY_SHEET, headers, rows)
    return {"updated": updated, "created": created}


def _append_to_model_sheet(
    service,
    sheet_name: str,
    required_headers: Sequence[str],
    rows: Sequence[Dict[str, Any]],
) -> int:
    values = _read_values(service, OVERVIEW_ID, sheet_name)
    if not values:
        model_header = [sheet_name + "_Model"]
        service.spreadsheets().values().update(
            spreadsheetId=OVERVIEW_ID,
            range=f"'{sheet_name}'!A1",
            valueInputOption="RAW",
            body={"values": [model_header, list(required_headers)]},
        ).execute()
        start_row = 3
        headers = list(required_headers)
    else:
        if len(values) == 1:
            headers = list(required_headers)
            service.spreadsheets().values().update(
                spreadsheetId=OVERVIEW_ID,
                range=f"'{sheet_name}'!A2",
                valueInputOption="RAW",
                body={"values": [headers]},
            ).execute()
            start_row = 3
        else:
            headers = values[1]
            for header in required_headers:
                if header not in headers:
                    headers.append(header)
            service.spreadsheets().values().update(
                spreadsheetId=OVERVIEW_ID,
                range=f"'{sheet_name}'!A2",
                valueInputOption="RAW",
                body={"values": [headers]},
            ).execute()
            start_row = len(values) + 1
    if rows:
        _write_rows(service, OVERVIEW_ID, sheet_name, headers, rows, start_row=start_row)
    return len(rows)


def _classification_for_sheet(workbook: str, sheet_name: str) -> Tuple[str, str, str]:
    if workbook == "MAIN":
        if sheet_name in MAIN_KEEP:
            return ("KEEP_MAIN", "MAIN_OPERATIONAL", "NONE")
        if sheet_name in {"Signal_Synchrony_Provider_Slice_Performance", "Signal_Synchrony_Provider_Slice_Summary"}:
            return ("REMOVE_MAIN_STRAY_DIAGNOSTIC", "ARCHIVE_COMPLETED_SYNCHRONY_BRANCH", "NONE")
        if sheet_name == "Sheet22":
            return ("INSPECT_ANONYMOUS", "ANONYMOUS", "NONE")
    if workbook == "DIAGNOSTICS":
        if sheet_name in FOUNDATION_KEEP:
            return ("KEEP_DIAGNOSTICS_FOUNDATION", "FOUNDATION_EVALUATION", "FOUNDATION_ACTIVE")
        if sheet_name in RISK_TEMP_KEEP:
            return ("KEEP_TEMP_REFERENCE", "ARCHIVE_OR_REFERENCE_OLD_RISK_FILTER_STACK", "ACTIVE_EVAL_DEPENDENCY")
        if sheet_name in CHARACTER_EXACT or any(sheet_name.startswith(prefix) for prefix in CHARACTER_PREFIXES):
            return ("MOVE_TO_ARCHIVE", "ARCHIVE_COMPLETED_CHARACTER_BRANCH", "NONE")
        if sheet_name in SYNCHRONY_EXACT:
            return ("MOVE_TO_ARCHIVE", "ARCHIVE_COMPLETED_SYNCHRONY_BRANCH", "NONE")
        if sheet_name in FEATURE_ARCHIVE:
            return ("MOVE_TO_ARCHIVE", "ARCHIVE_SUPERSEDED_FEATURE_PACK_V2B", "NONE")
    if workbook == "PROJECT_OVERVIEWS":
        if sheet_name in PROJECT_KEEP:
            return ("KEEP_PROJECT_OVERVIEWS", "MIGRATION_GOVERNANCE", "NONE")
        if sheet_name in PROJECT_ARCHIVE_CANDIDATES:
            return ("MOVE_TO_ARCHIVE", "ARCHIVE_PROJECT_MEMORY", "NONE")
    return ("NO_ACTION", "UNCLASSIFIED", "NONE")


def _control_family(label: str) -> str:
    mapping = {
        "ARCHIVE_COMPLETED_CHARACTER_BRANCH": "PROVIDER_CHARACTER",
        "ARCHIVE_COMPLETED_SYNCHRONY_BRANCH": "SIGNAL_SYNCHRONY",
        "ARCHIVE_SUPERSEDED_FEATURE_PACK_V2B": "FEATURE_PACK_V2B",
        "ARCHIVE_OR_REFERENCE_OLD_RISK_FILTER_STACK": "MARKET_SENSITIVITY",
        "FOUNDATION_EVALUATION": "FOUNDATION_EVALUATION",
        "ARCHIVE_PROJECT_MEMORY": "GOVERNANCE",
        "MIGRATION_GOVERNANCE": "GOVERNANCE",
        "MAIN_OPERATIONAL": "MAIN_OPERATIONAL",
    }
    return mapping.get(label, "WORKBOOK_TRANSITION")


def execute_transition() -> Dict[str, Any]:
    creds = load_credentials(interactive=False)
    service = build_sheets_service(creds)
    generated_ts = _now()

    inventories = {workbook: _inventory_workbook(service, workbook) for workbook in WORKBOOKS}

    pre_rows: List[Dict[str, Any]] = []
    for workbook, sheets in inventories.items():
        for sheet_name in sorted(sheets):
            action, lifecycle, dep = _classification_for_sheet(workbook, sheet_name)
            pre_rows.append({
                "generated_ts": generated_ts,
                "audit_phase": "PRE",
                "workbook": workbook,
                "sheet_name": sheet_name,
                "current_location": workbook,
                "recommended_action": action,
                "final_action": "",
                "target_location": "",
                "lifecycle_label": lifecycle,
                "dependency_status": dep,
                "archive_status": "",
                "notes": "",
            })

    # Explicit missing targets requested by the brief.
    explicit_missing = []
    for workbook, sheet_name, lifecycle in [
        ("MAIN", "Signal_Synchrony_Provider_Slice", "ARCHIVE_COMPLETED_SYNCHRONY_BRANCH"),
        ("MAIN", "Sheet22", "ANONYMOUS"),
    ]:
        if sheet_name not in inventories[workbook]:
            explicit_missing.append({
                "generated_ts": generated_ts,
                "audit_phase": "PRE",
                "workbook": workbook,
                "sheet_name": sheet_name,
                "current_location": workbook,
                "recommended_action": "MISSING_SOURCE",
                "final_action": "MISSING_SOURCE",
                "target_location": "ARCHIVE_01" if sheet_name != "Sheet22" else "",
                "lifecycle_label": lifecycle,
                "dependency_status": "NONE",
                "archive_status": "MISSING_SOURCE",
                "notes": "Requested exact source sheet was not present in the workbook inventory.",
            })
    pre_rows.extend(explicit_missing)

    actions_log: List[Dict[str, Any]] = []
    control_rows: List[Dict[str, Any]] = []
    registry_updates: List[Dict[str, Any]] = []
    extra_registry_rows: List[Dict[str, Any]] = [
        {
            "logical_sheet_id": "WORKBOOK_OVERHAUL_TRANSITION_AUDIT",
            "physical_sheet_name": AUDIT_SHEET,
            "workbook": "PROJECT_OVERVIEWS",
            "workbook_id": OVERVIEW_ID,
            "category": "GOVERNANCE",
            "lifecycle_state": "ACTIVE",
            "owner_module": "governance",
            "participates_in_rebuild": "TRUE",
            "read_only": "FALSE",
            "allow_creation": "TRUE",
            "created_phase": "Workbook Overhaul Transition",
            "notes": "Aggressive workbook structure transition audit",
            "registry_migration_ts": "",
            "registry_rename_ts": "",
        }
    ]

    sequence = 1

    def log_action(
        workbook: str,
        sheet_name: str,
        recommended_action: str,
        final_action: str,
        target_location: str,
        lifecycle_label: str,
        dependency_status: str,
        archive_status: str,
        notes: str,
        snapshot: Optional[SheetSnapshot],
        rows_after: Any = "",
        cols_after: Any = "",
        header_validation: str = "",
        dest_name: str = "",
    ) -> None:
        nonlocal sequence
        row_count = snapshot.row_count if snapshot else ""
        col_count = snapshot.col_count if snapshot else ""
        header_hash = snapshot.header_hash if snapshot else ""
        control_rows.append({
            "migration_batch_id": TRANSITION_BATCH_ID,
            "control_row_id": f"OVERHAUL-{sequence:03d}",
            "sheet_name": sheet_name,
            "source_workbook": WORKBOOKS.get(workbook, {}).get("name", workbook),
            "target_workbook": WORKBOOKS.get(target_location, {}).get("name", target_location) if target_location else "",
            "current_workbook_confirmed": "TRUE" if snapshot else "FALSE",
            "target_workbook_confirmed": "TRUE" if target_location else "FALSE",
            "experiment_family": _control_family(lifecycle_label),
            "lifecycle_status": "ARCHIVED" if final_action.startswith("MOVED") or final_action.startswith("DELETED_DUPLICATE") else ("ACTIVE" if "KEEP" in final_action else lifecycle_label),
            "archive_candidate": "TRUE" if "ARCHIVE" in recommended_action or "REMOVE" in recommended_action else "FALSE",
            "migration_reason": lifecycle_label,
            "approval_status": "APPROVED",
            "approved_for_migration": "TRUE",
            "approval_source": "User approved workbook overhaul transition",
            "migration_status": final_action,
            "blocking_reason": "" if "KEEP_TEMP_REFERENCE" not in final_action else notes,
            "rows_before": row_count,
            "cols_before": col_count,
            "expected_header_hash": header_hash,
            "rows_after": rows_after,
            "cols_after": cols_after,
            "actual_header_hash": header_validation,
            "validation_result": archive_status,
            "migrated_ts": generated_ts,
            "migrated_by_phase": "Workbook Overhaul Transition",
            "migration_notes": notes,
        })
        actions_log.append({
            "log_id": f"OVERHAUL-LOG-{sequence:03d}",
            "migration_batch_id": TRANSITION_BATCH_ID,
            "executed_ts": generated_ts,
            "sheet_name": sheet_name,
            "from_workbook": WORKBOOKS.get(workbook, {}).get("name", workbook),
            "to_workbook": WORKBOOKS.get(target_location, {}).get("name", target_location) if target_location else "",
            "action_taken": final_action,
            "result": archive_status,
            "rows_before": row_count,
            "rows_after": rows_after,
            "cols_before": col_count,
            "cols_after": cols_after,
            "header_validation": header_validation,
            "source_deleted": "TRUE" if final_action.startswith("MOVED") or final_action.startswith("DELETED") else "FALSE",
            "destination_sheet_name": dest_name,
            "error_message": "",
            "notes": notes,
        })
        sequence += 1

    # Phase A: move diagnostics branch sheets to archive.
    diagnostics_targets = []
    for name, snap in inventories["DIAGNOSTICS"].items():
        action, lifecycle, dep = _classification_for_sheet("DIAGNOSTICS", name)
        if action == "MOVE_TO_ARCHIVE":
            diagnostics_targets.append((name, snap, lifecycle))
        elif action == "KEEP_TEMP_REFERENCE":
            log_action("DIAGNOSTICS", name, action, "KEEP_TEMP_REFERENCE", "DIAGNOSTICS", lifecycle, dep, "TEMPORARY_KEEP", "Kept in DIAGNOSTICS because evaluation_report.js still exposes active builder dependencies for this risk-history stack.", snap)

    archive_inventory = inventories["ARCHIVE_01"]
    for name, snap, lifecycle in sorted(diagnostics_targets, key=lambda item: item[0]):
        snap = _materialize_snapshot(service, snap)
        archive_snap = archive_inventory.get(name)
        archive_snap = _materialize_snapshot(service, archive_snap)
        final_action = ""
        archive_status = ""
        target_name = name
        if archive_snap and _compare_snapshots(snap, archive_snap):
            _delete_sheet(service, "DIAGNOSTICS", snap.sheet_id)
            final_action = "DELETED_SOURCE_ALREADY_IN_ARCHIVE"
            archive_status = "ALREADY_IN_ARCHIVE"
        else:
            if archive_snap and not _compare_snapshots(snap, archive_snap):
                target_name = _deterministic_archive_name(name, "DIAGNOSTICS")
            new_sheet_id, target_name = _copy_sheet(service, snap, "ARCHIVE_01", target_name)
            copied = _materialize_snapshot(service, _inventory_workbook(service, "ARCHIVE_01")[target_name])
            if copied.row_count != snap.row_count or copied.col_count != snap.col_count or copied.header != snap.header:
                raise RuntimeError(f"Validation failed for copied sheet {name} -> {target_name}")
            _delete_sheet(service, "DIAGNOSTICS", snap.sheet_id)
            final_action = "MOVED_TO_ARCHIVE_01"
            archive_status = "MIGRATED"
            archive_inventory = _inventory_workbook(service, "ARCHIVE_01")
        log_action("DIAGNOSTICS", name, "MOVE_TO_ARCHIVE", final_action, "ARCHIVE_01", lifecycle, "NONE", archive_status, f"{lifecycle} transition from DIAGNOSTICS to ARCHIVE_01.", snap, rows_after=snap.row_count, cols_after=snap.col_count, header_validation=snap.header_hash, dest_name=target_name)
        registry_updates.append({
            "logical_sheet_id": _key(name),
            "physical_sheet_name": target_name,
            "workbook": "ARCHIVE_01",
            "workbook_id": ARCHIVE_ID,
            "category": "SIGNAL_SYNCHRONY" if name.startswith("Signal_Synchrony_") else ("GOVERNANCE" if name in PROJECT_ARCHIVE_CANDIDATES else "DIAGNOSTIC"),
            "lifecycle_state": "ARCHIVED",
            "owner_module": "signal_synchrony" if name.startswith("Signal_Synchrony_") else ("governance" if name in PROJECT_ARCHIVE_CANDIDATES else "provider_character"),
            "participates_in_rebuild": "FALSE",
            "read_only": "FALSE",
            "allow_creation": "FALSE",
            "created_phase": "Workbook Overhaul Transition",
            "notes": lifecycle,
            "registry_migration_ts": generated_ts,
            "registry_rename_ts": generated_ts if target_name != name else "",
        })

    inventories["DIAGNOSTICS"] = _inventory_workbook(service, "DIAGNOSTICS")
    archive_inventory = _inventory_workbook(service, "ARCHIVE_01")

    # Phase B: move project overview memory sheets to archive.
    for name in sorted(PROJECT_ARCHIVE_CANDIDATES):
        snap = inventories["PROJECT_OVERVIEWS"].get(name)
        if not snap:
            log_action("PROJECT_OVERVIEWS", name, "MOVE_TO_ARCHIVE", "MISSING_SOURCE", "ARCHIVE_01", "ARCHIVE_PROJECT_MEMORY", "NONE", "MISSING_SOURCE", "Requested project-memory sheet was not present in PROJECT_OVERVIEWS.", None)
            continue
        snap = _materialize_snapshot(service, snap)
        if snap.is_empty:
            _delete_sheet(service, "PROJECT_OVERVIEWS", snap.sheet_id)
            log_action("PROJECT_OVERVIEWS", name, "MOVE_TO_ARCHIVE", "DELETE_EMPTY_GOVERNANCE_SHEET", "", "ARCHIVE_PROJECT_MEMORY", "NONE", "DELETED_EMPTY", "Sheet was empty and removed after audit.", snap)
            continue
        archive_snap = archive_inventory.get(name)
        archive_snap = _materialize_snapshot(service, archive_snap)
        target_name = name
        if archive_snap and _compare_snapshots(snap, archive_snap):
            _delete_sheet(service, "PROJECT_OVERVIEWS", snap.sheet_id)
            final_action = "DELETED_SOURCE_ALREADY_IN_ARCHIVE"
            archive_status = "ALREADY_IN_ARCHIVE"
        else:
            if archive_snap and not _compare_snapshots(snap, archive_snap):
                target_name = _deterministic_archive_name(name, "PROJECT_OVERVIEWS")
            _copy_sheet(service, snap, "ARCHIVE_01", target_name)
            copied = _materialize_snapshot(service, _inventory_workbook(service, "ARCHIVE_01")[target_name])
            if copied.row_count != snap.row_count or copied.col_count != snap.col_count or copied.header != snap.header:
                raise RuntimeError(f"Validation failed for copied project sheet {name} -> {target_name}")
            _delete_sheet(service, "PROJECT_OVERVIEWS", snap.sheet_id)
            final_action = "MOVED_TO_ARCHIVE_01"
            archive_status = "MIGRATED"
            archive_inventory = _inventory_workbook(service, "ARCHIVE_01")
        log_action("PROJECT_OVERVIEWS", name, "MOVE_TO_ARCHIVE", final_action, "ARCHIVE_01", "ARCHIVE_PROJECT_MEMORY", "NONE", archive_status, "Historical project-memory sheet moved out of active PROJECT_OVERVIEWS.", snap, rows_after=snap.row_count, cols_after=snap.col_count, header_validation=snap.header_hash, dest_name=target_name)
        registry_updates.append({
            "logical_sheet_id": _key(name),
            "physical_sheet_name": target_name,
            "workbook": "ARCHIVE_01",
            "workbook_id": ARCHIVE_ID,
            "category": "SIGNAL_SYNCHRONY" if name == "Signal_Synchrony_v1" else "GOVERNANCE",
            "lifecycle_state": "ARCHIVED",
            "owner_module": "signal_synchrony" if name == "Signal_Synchrony_v1" else "governance",
            "participates_in_rebuild": "FALSE",
            "read_only": "FALSE",
            "allow_creation": "FALSE",
            "created_phase": "Workbook Overhaul Transition",
            "notes": "Archived project-memory sheet",
            "registry_migration_ts": generated_ts,
            "registry_rename_ts": generated_ts if target_name != name else "",
        })

    inventories["PROJECT_OVERVIEWS"] = _inventory_workbook(service, "PROJECT_OVERVIEWS")
    archive_inventory = _inventory_workbook(service, "ARCHIVE_01")

    # Phase C: clean MAIN stray synchrony sheets.
    for name in ["Signal_Synchrony_Provider_Slice_Performance", "Signal_Synchrony_Provider_Slice_Summary"]:
        snap = inventories["MAIN"].get(name)
        if not snap:
            continue
        snap = _materialize_snapshot(service, snap)
        archive_snap = archive_inventory.get(name)
        archive_snap = _materialize_snapshot(service, archive_snap)
        lifecycle = "ARCHIVE_COMPLETED_SYNCHRONY_BRANCH"
        if archive_snap and _compare_snapshots(snap, archive_snap):
            _delete_sheet(service, "MAIN", snap.sheet_id)
            final_action = "DELETED_DUPLICATE_AFTER_ARCHIVE_CONFIRM"
            archive_status = "ALREADY_IN_ARCHIVE"
            target_name = name
        else:
            target_name = name if not archive_snap else _deterministic_archive_name(name, "MAIN")
            _copy_sheet(service, snap, "ARCHIVE_01", target_name)
            copied = _materialize_snapshot(service, _inventory_workbook(service, "ARCHIVE_01")[target_name])
            if copied.row_count != snap.row_count or copied.col_count != snap.col_count or copied.header != snap.header:
                raise RuntimeError(f"Validation failed for MAIN stray sheet {name} -> {target_name}")
            _delete_sheet(service, "MAIN", snap.sheet_id)
            final_action = "MOVED_TO_ARCHIVE_01"
            archive_status = "MIGRATED"
            archive_inventory = _inventory_workbook(service, "ARCHIVE_01")
        log_action("MAIN", name, "REMOVE_MAIN_STRAY_DIAGNOSTIC", final_action, "ARCHIVE_01", lifecycle, "NONE", archive_status, "Removed stray Signal Synchrony diagnostic duplicate from MAIN after preserving it in ARCHIVE_01.", snap, rows_after=snap.row_count, cols_after=snap.col_count, header_validation=snap.header_hash, dest_name=target_name)

    # Explicit missing rows for Sheet22 and exact slice name.
    for item in explicit_missing:
        log_action(item["workbook"], item["sheet_name"], item["recommended_action"], item["final_action"], item["target_location"], item["lifecycle_label"], item["dependency_status"], item["archive_status"], item["notes"], None)

    inventories["MAIN"] = _inventory_workbook(service, "MAIN")
    inventories["ARCHIVE_01"] = _inventory_workbook(service, "ARCHIVE_01")

    # Append keep rows for foundation/governance counts that were not logged.
    for workbook, sheets in [("DIAGNOSTICS", inventories["DIAGNOSTICS"]), ("PROJECT_OVERVIEWS", inventories["PROJECT_OVERVIEWS"]), ("MAIN", inventories["MAIN"])]:
        for name, snap in sorted(sheets.items()):
            action, lifecycle, dep = _classification_for_sheet(workbook, name)
            if workbook == "DIAGNOSTICS" and name in FOUNDATION_KEEP:
                log_action(workbook, name, action, "KEEP_FOUNDATION_EVALUATION", workbook, lifecycle, dep, "ACTIVE", "Kept as foundation evaluation layer for future comparisons.", _materialize_snapshot(service, snap))
            elif workbook == "PROJECT_OVERVIEWS" and name in PROJECT_KEEP:
                log_action(workbook, name, action, "KEEP_GOVERNANCE", workbook, lifecycle, dep, "ACTIVE", "Kept as migration/registry governance sheet.", _materialize_snapshot(service, snap))
            elif workbook == "MAIN" and name in MAIN_KEEP:
                log_action(workbook, name, action, "KEEP_MAIN_OPERATIONAL", workbook, lifecycle, dep, "ACTIVE", "Kept as operational/reference/evaluation support sheet.", _materialize_snapshot(service, snap))

    # Write transition audit pre/post.
    post_rows: List[Dict[str, Any]] = []
    for workbook, sheets in inventories.items():
        for name in sorted(sheets):
            action, lifecycle, dep = _classification_for_sheet(workbook, name)
            post_rows.append({
                "generated_ts": generated_ts,
                "audit_phase": "POST",
                "workbook": workbook,
                "sheet_name": name,
                "current_location": workbook,
                "recommended_action": action,
                "final_action": action if action.startswith("KEEP") else "",
                "target_location": workbook,
                "lifecycle_label": lifecycle,
                "dependency_status": dep,
                "archive_status": "",
                "notes": "",
            })

    audit_headers = _ensure_sheet(service, OVERVIEW_ID, AUDIT_SHEET, AUDIT_HEADERS)
    _clear_sheet_body(service, OVERVIEW_ID, AUDIT_SHEET)
    _write_rows(service, OVERVIEW_ID, AUDIT_SHEET, audit_headers, pre_rows + post_rows)

    control_headers = [
        "migration_batch_id", "control_row_id", "sheet_name", "source_workbook", "target_workbook",
        "current_workbook_confirmed", "target_workbook_confirmed", "experiment_family", "lifecycle_status",
        "archive_candidate", "migration_reason", "approval_status", "approved_for_migration", "approval_source",
        "migration_status", "blocking_reason", "rows_before", "cols_before", "expected_header_hash", "rows_after",
        "cols_after", "actual_header_hash", "validation_result", "migrated_ts", "migrated_by_phase", "migration_notes",
    ]
    log_headers = [
        "log_id", "migration_batch_id", "executed_ts", "sheet_name", "from_workbook", "to_workbook",
        "action_taken", "result", "rows_before", "rows_after", "cols_before", "cols_after", "header_validation",
        "source_deleted", "destination_sheet_name", "error_message", "notes",
    ]
    _append_to_model_sheet(service, MIGRATION_CONTROL_SHEET, control_headers, control_rows)
    _append_to_model_sheet(service, MIGRATION_LOG_SHEET, log_headers, actions_log)

    registry_result = _upsert_registry_rows(service, registry_updates, extra_registry_rows)
    registry_audit_result = build_sheet_registry_audit()

    final_main = inventories["MAIN"]
    final_diag = inventories["DIAGNOSTICS"]
    final_overview = inventories["PROJECT_OVERVIEWS"]
    final_archive = inventories["ARCHIVE_01"]
    missing_count = sum(1 for row in actions_log if row["result"] == "MISSING_SOURCE")
    already_count = sum(1 for row in actions_log if row["result"] == "ALREADY_IN_ARCHIVE")
    blocked = [row["sheet_name"] for row in actions_log if row["action_taken"] == "KEEP_TEMP_REFERENCE"]

    return {
        "generated_ts": generated_ts,
        "main_sheets_kept_count": len([n for n in final_main if n in MAIN_KEEP]),
        "main_sheets_moved_deleted_count": sum(1 for row in actions_log if row["from_workbook"] == WORKBOOKS["MAIN"]["name"] and row["action_taken"] not in {"KEEP_MAIN_OPERATIONAL"}),
        "diagnostics_foundation_kept_count": len([n for n in final_diag if n in FOUNDATION_KEEP]),
        "diagnostics_moved_to_archive_count": sum(1 for row in actions_log if row["from_workbook"] == WORKBOOKS["DIAGNOSTICS"]["name"] and row["action_taken"] in {"MOVED_TO_ARCHIVE_01", "DELETED_SOURCE_ALREADY_IN_ARCHIVE"}),
        "project_overviews_kept_count": len([n for n in final_overview if n in PROJECT_KEEP]),
        "project_overviews_archived_deleted_count": sum(1 for row in actions_log if row["from_workbook"] == WORKBOOKS["PROJECT_OVERVIEWS"]["name"] and row["action_taken"] in {"MOVED_TO_ARCHIVE_01", "DELETED_SOURCE_ALREADY_IN_ARCHIVE", "DELETE_EMPTY_GOVERNANCE_SHEET"}),
        "missing_requested_sheets_count": missing_count,
        "already_in_archive_count": already_count,
        "blocked_sheets": blocked,
        "temporary_dependency_keeps": sorted([name for name in final_diag if name in RISK_TEMP_KEEP]),
        "registry_updates": registry_result,
        "registry_audit": registry_audit_result,
        "final_counts": {
            "MAIN": len(final_main),
            "DIAGNOSTICS": len(final_diag),
            "ARCHIVE_01": len(final_archive),
            "PROJECT_OVERVIEWS": len(final_overview),
        },
    }


if __name__ == "__main__":
    result = execute_transition()
    print(json.dumps(result, indent=2, sort_keys=True))
