import os
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.google_clients import build_sheets_service, load_credentials


MAIN_SPREADSHEET_ID = os.environ.get(
    "PRESIGNAL_MAIN_SPREADSHEET_ID",
    "1_gZGnd6h3VzdiBvGBHRSxn78KW8tsOi2UEc6Y_Sc23Q",
)
DIAGNOSTICS_SPREADSHEET_ID = os.environ.get(
    "PRESIGNAL_DIAGNOSTICS_SPREADSHEET_ID",
    "1jxcZotbzJKcAzrK0VhxetYX6hp5DPXCCIA0J6B6RUy0",
)
ARCHIVE_01_SPREADSHEET_ID = os.environ.get(
    "PRESIGNAL_ARCHIVE_01_SPREADSHEET_ID",
    "12hi1rugE_F-MhlupgmL13BIagerzA8CZkm1sk_nHPSg",
)
PROJECT_OVERVIEWS_SPREADSHEET_ID = os.environ.get(
    "PRESIGNAL_PROJECT_OVERVIEWS_SPREADSHEET_ID",
    "1PtXrQpzNX8600I0aCOb2hLPkWtTvFKtDVIZZIys_Uvo",
)

REGISTRY_SHEET = "Sheet_Registry"
AUDIT_SHEET = "Sheet_Registry_Audit"

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

AUDIT_HEADERS = [
    "audit_ts",
    "issue_type",
    "logical_sheet_id",
    "physical_sheet_name",
    "registry_workbook",
    "observed_workbook",
    "status",
    "details",
]

ALLOWED_LIFECYCLE = {"ACTIVE", "FROZEN", "ARCHIVED", "DEPRECATED"}
ALLOWED_CATEGORY = {
    "CANONICAL",
    "DERIVED",
    "DIAGNOSTIC",
    "SIGNAL_SYNCHRONY",
    "PROVIDER_CHARACTER",
    "OUTCOME_LAYER",
    "FEATURE_PACK",
    "ECONOMIC_VALUE",
    "GOVERNANCE",
    "EVALUATION",
    "MAIN_OPERATIONAL",
    "REFERENCE_DATA",
    "OPERATIONAL_DERIVED",
    "MARKET_SENSITIVITY",
    "ATTENTION_V1",
    "ATTENTION_V3",
    "ATTENTION_C0",
    "FAMILY_STRUCTURE",
    "LEGACY_MR",
    "BATCH_SPLITTING",
    "CHARACTER_ECONOMIC",
    "UNKNOWN_REVIEW_REQUIRED",
}

WORKBOOK_IDS = {
    "MAIN": MAIN_SPREADSHEET_ID,
    "DIAGNOSTICS": DIAGNOSTICS_SPREADSHEET_ID,
    "ARCHIVE_01": ARCHIVE_01_SPREADSHEET_ID,
    "PROJECT_OVERVIEWS": PROJECT_OVERVIEWS_SPREADSHEET_ID,
}

REQUIRED_GOVERNANCE_ROWS = [
    {
        "logical_sheet_id": "SHEET_REGISTRY_AUDIT",
        "physical_sheet_name": "Sheet_Registry_Audit",
        "workbook": "PROJECT_OVERVIEWS",
        "workbook_id": PROJECT_OVERVIEWS_SPREADSHEET_ID,
        "category": "GOVERNANCE",
        "lifecycle_state": "ACTIVE",
        "owner_module": "governance",
        "participates_in_rebuild": "TRUE",
        "read_only": "FALSE",
        "allow_creation": "TRUE",
        "created_phase": "Sheet Registry Governance v2",
        "notes": "Derived registry validation report",
    }
]


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


def _bool_text(value: Any, default: bool = False) -> str:
    raw = _norm(value).lower()
    if raw in {"true", "1", "yes", "y"}:
        return "TRUE"
    if raw in {"false", "0", "no", "n"}:
        return "FALSE"
    return "TRUE" if default else "FALSE"


def _owner_module(sheet_name: str, existing: str) -> str:
    if existing:
        return existing
    name = _norm(sheet_name)
    if name.startswith("Signal_Synchrony_"):
        return "signal_synchrony"
    if name.startswith("Provider_Character_") or name.startswith("Character_"):
        return "provider_character"
    if name.startswith("Outcome_"):
        return "outcome"
    if name.startswith("Evaluation_"):
        return "evaluation"
    if (
        name.startswith("Feature_Pack_")
        or name.startswith("Market_Context_")
        or name.startswith("V2B_")
        or name.startswith("Production_vs_V2B_")
        or name.startswith("Surprise_Pack_")
    ):
        return "feature_pack"
    if name.startswith("Attention_"):
        return "attention"
    if name.startswith("Family_") or name.startswith("Batch_"):
        return "family_structure"
    if (
        name.startswith("Workbook_")
        or name.startswith("Experiment_")
        or name.startswith("Decision_")
        or name.startswith("Current_")
        or name.startswith("Research_")
        or name.startswith("PreSignal_")
        or name in {"Sheet_Registry", "Sheet_Registry_Audit", "Project_Status"}
    ):
        return "governance"
    return "registry_auto_sync"


def _ensure_sheet(service, spreadsheet_id: str, sheet_name: str, required_headers: List[str]) -> List[str]:
    metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    titles = {s["properties"]["title"] for s in metadata.get("sheets", [])}
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


def _read_rows(service, spreadsheet_id: str, sheet_name: str) -> Tuple[List[str], List[Dict[str, Any]]]:
    values = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!A1:ZZZ")
        .execute()
        .get("values", [])
    )
    if not values:
        return [], []
    headers = values[0]
    rows = []
    for raw in values[1:]:
        padded = list(raw) + [""] * (len(headers) - len(raw))
        rows.append({headers[i]: padded[i] for i in range(len(headers))})
    return headers, rows


def _write_body(service, spreadsheet_id: str, sheet_name: str, headers: List[str], rows: List[Dict[str, Any]]) -> None:
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


def _sheet_titles(service, spreadsheet_id: str) -> List[str]:
    metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return [s["properties"]["title"] for s in metadata.get("sheets", [])]


def build_sheet_registry_audit() -> Dict[str, Any]:
    creds = load_credentials(interactive=False)
    service = build_sheets_service(creds)
    now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    registry_headers = _ensure_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS)
    _, registry_rows = _read_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)

    repaired_rows: List[Dict[str, Any]] = []
    repaired_count = 0
    for row in registry_rows:
        logical = _norm(row.get("logical_sheet_id")) or _key(row.get("physical_sheet_name"))
        physical = _norm(row.get("physical_sheet_name")) or logical
        workbook = _norm(row.get("workbook")).upper() or "PROJECT_OVERVIEWS"
        if workbook == "OVERVIEW":
            workbook = "PROJECT_OVERVIEWS"
        elif workbook == "ARCHIVE":
            workbook = "ARCHIVE_01"
        category = _norm(row.get("category")).upper() or "GOVERNANCE"
        lifecycle = _norm(row.get("lifecycle_state")).upper() or "ACTIVE"
        repaired = dict(row)
        repaired["logical_sheet_id"] = logical
        repaired["physical_sheet_name"] = physical
        repaired["workbook"] = workbook
        repaired["workbook_id"] = _norm(row.get("workbook_id")) or WORKBOOK_IDS.get(workbook, "")
        repaired["category"] = category if category in ALLOWED_CATEGORY else "GOVERNANCE"
        repaired["lifecycle_state"] = lifecycle if lifecycle in ALLOWED_LIFECYCLE else "ACTIVE"
        repaired["owner_module"] = _owner_module(physical, _norm(row.get("owner_module")))
        repaired["participates_in_rebuild"] = _bool_text(row.get("participates_in_rebuild"))
        repaired["read_only"] = _bool_text(row.get("read_only"))
        repaired["allow_creation"] = _bool_text(row.get("allow_creation"))
        repaired["created_phase"] = _norm(row.get("created_phase"))
        repaired["notes"] = _norm(row.get("notes"))
        repaired["registry_created_ts"] = _norm(row.get("registry_created_ts")) or now
        repaired["registry_last_verified_ts"] = now
        repaired["registry_migration_ts"] = _norm(row.get("registry_migration_ts"))
        repaired["registry_rename_ts"] = _norm(row.get("registry_rename_ts"))
        if any(_norm(repaired.get(h)) != _norm(row.get(h)) for h in registry_headers):
            repaired_count += 1
        repaired_rows.append(repaired)

    existing_logical = {_key(row["logical_sheet_id"]) for row in repaired_rows}
    for required in REQUIRED_GOVERNANCE_ROWS:
        if _key(required["logical_sheet_id"]) in existing_logical:
            continue
        row = dict(required)
        row["registry_created_ts"] = now
        row["registry_last_verified_ts"] = now
        row["registry_migration_ts"] = ""
        row["registry_rename_ts"] = ""
        repaired_rows.append(row)
        repaired_count += 1

    _write_body(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, registry_headers, repaired_rows)

    by_logical = Counter(_key(row["logical_sheet_id"]) for row in repaired_rows)
    by_physical = Counter((_key(row["physical_sheet_name"]), _norm(row["workbook"]).upper()) for row in repaired_rows)

    workbook_sheets = {
        "MAIN": set(_sheet_titles(service, MAIN_SPREADSHEET_ID)),
        "DIAGNOSTICS": set(_sheet_titles(service, DIAGNOSTICS_SPREADSHEET_ID)),
        "ARCHIVE_01": set(_sheet_titles(service, ARCHIVE_01_SPREADSHEET_ID)),
        "PROJECT_OVERVIEWS": set(_sheet_titles(service, PROJECT_OVERVIEWS_SPREADSHEET_ID)),
    }

    audit_rows: List[Dict[str, Any]] = []

    def add(issue_type: str, logical_id: str, physical_name: str, registry_workbook: str, observed_workbook: str, status: str, details: str) -> None:
        audit_rows.append(
            {
                "audit_ts": now,
                "issue_type": issue_type,
                "logical_sheet_id": logical_id,
                "physical_sheet_name": physical_name,
                "registry_workbook": registry_workbook,
                "observed_workbook": observed_workbook,
                "status": status,
                "details": details,
            }
        )

    add("SUMMARY", "", "", "", "", "PASS", f"registered_sheets={len(repaired_rows)}")
    add(
        "SUMMARY",
        "",
        "",
        "",
        "",
        "PASS",
        f"active_sheets={sum(1 for row in repaired_rows if row['lifecycle_state'] == 'ACTIVE')}",
    )

    for logical_key, count in sorted(by_logical.items()):
        if count > 1:
            add("DUPLICATE_LOGICAL_ID", logical_key, "", "", "", "FAIL", "Duplicate logical id present in Sheet_Registry")

    for (physical_key, workbook), count in sorted(by_physical.items()):
        if count > 1:
            add("DUPLICATE_PHYSICAL_NAME", "", physical_key, workbook, workbook, "FAIL", "Duplicate physical sheet mapping present in Sheet_Registry")

    observed_registered = set()
    for row in repaired_rows:
        logical = _norm(row["logical_sheet_id"])
        physical = _norm(row["physical_sheet_name"])
        workbook = _norm(row["workbook"]).upper()
        found_in = []
        for workbook_name, titles in workbook_sheets.items():
            if physical in titles or logical in titles:
                found_in.append(workbook_name)
        if not found_in:
            add("MISSING_SHEET", logical, physical, workbook, "", "WARN", "Registry entry exists but no workbook sheet was found.")
            continue
        observed_registered.add((_key(physical), workbook))
        if len(found_in) > 1:
            add("ORPHAN_GOVERNED_SHEET", logical, physical, workbook, "|".join(found_in), "WARN", "Multiple workbook matches found for governed sheet.")
        observed_workbook = found_in[0]
        if physical not in workbook_sheets.get(workbook, set()) and logical in workbook_sheets.get(workbook, set()):
            add("RENAMED_SHEET", logical, physical, workbook, observed_workbook, "WARN", f"Observed sheet name matches logical id {logical}.")
        elif workbook not in found_in:
            add("MIGRATED_SHEET", logical, physical, workbook, observed_workbook, "WARN", "Workbook mismatch between registry and observed sheet.")
        if _norm(row["lifecycle_state"]).upper() not in ALLOWED_LIFECYCLE:
            add("INVALID_LIFECYCLE", logical, physical, workbook, observed_workbook, "FAIL", f"Unsupported lifecycle_state={row['lifecycle_state']}")
        if _norm(row["category"]).upper() not in ALLOWED_CATEGORY:
            add("INVALID_CATEGORY", logical, physical, workbook, observed_workbook, "FAIL", f"Unsupported category={row['category']}")

    fallback_known = {
        "Sheet_Registry",
        "Sheet_Registry_Audit",
        "Current_Roadmap",
        "Research_Journey",
        "PreSignal_Layer_Map",
        "Experiment_Register",
        "Interpretation_Corrections",
        "Decision_Log_v2",
        "Project_Status",
    }
    registered_logical = {_key(row["logical_sheet_id"]) for row in repaired_rows}
    for known in sorted(fallback_known):
        if _key(known) not in registered_logical:
            add("ORPHAN_GOVERNED_SHEET", _key(known), known, "PROJECT_OVERVIEWS", "", "WARN", "Governed fallback sheet is not yet registered.")

    audit_headers = _ensure_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, AUDIT_SHEET, AUDIT_HEADERS)
    _write_body(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, AUDIT_SHEET, audit_headers, audit_rows)

    return {
        "audit_ts": now,
        "registered_sheets": len(repaired_rows),
        "registry_entries_repaired": repaired_count,
        "audit_rows_written": len(audit_rows),
        "duplicate_logical_ids": sum(1 for c in by_logical.values() if c > 1),
        "duplicate_physical_names": sum(1 for c in by_physical.values() if c > 1),
    }


if __name__ == "__main__":
    print(build_sheet_registry_audit())
