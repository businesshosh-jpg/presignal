#!/usr/bin/env python3
"""Create Archive 02 and remove only fully verified legacy diagnostics sheets.

This is intentionally a Google Sheets migration, not a values-only export.  It
uses Sheets ``copyTo`` so the copied tab keeps its native layout and objects,
then compares the source and destination before any source tab is deleted.

Option 1 correction (2026-07-17): positions 53 and 81 are named current v2.0
tabs in the live workbook, so they are retained.  The corrected plan moves 728
tabs and retains 92.
"""

import argparse
import copy
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from googleapiclient.errors import HttpError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.google_clients import build_sheets_service, load_credentials
from automation.workbook_overhaul_transition import DIAGNOSTICS_ID


SOURCE_TITLE = "presignal_research_diagnostics"
ARCHIVE_TITLE = "presignal_diagnostics_archive_02"
INDEX_SHEET = "Archive_02_Index"
MOVE_LOG_SHEET = "Archive_02_Move_Log"
EXPECTED_SOURCE_COUNT = 820
EXPECTED_MOVED_COUNT = 728
EXPECTED_RETAINED_COUNT = 92

INDEX_HEADERS = [
    "archive_sequence",
    "original_workbook_position",
    "original_sheet_name",
    "research_family",
    "move_reason",
    "source_workbook",
    "archive_timestamp",
    "verification_status",
]

MOVE_LOG_HEADERS = [
    "stage",
    "source_workbook_path",
    "destination_workbook_path",
    "original_sheet_count",
    "retained_sheet_count",
    "moved_sheet_count",
    "execution_timestamp",
    "implementation_fingerprint",
    "source_workbook_hash_before_modification",
    "active_workbook_hash_after_modification",
    "archive_workbook_hash",
    "overall_result",
    "exceptions_or_warnings",
]

# These fields are computed by Google and can legitimately differ after a copy.
VOLATILE_FIELDS = {
    "sheetId",
    "chartId",
    "bandedRangeId",
    "protectedRangeId",
    "filterViewId",
    "slicerId",
    "developerMetadataId",
    "namedRangeId",
    "effectiveValue",
    "effectiveFormat",
    "formattedValue",
}


@dataclass(frozen=True)
class PlannedSheet:
    position: int
    sheet_id: int
    title: str
    family: str
    reason: str


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _quote_sheet(title: str) -> str:
    return "'" + title.replace("'", "''") + "'"


def _json_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _implementation_fingerprint() -> str:
    return _json_hash(Path(__file__).read_text(encoding="utf-8"))


def _retry(action, label: str):
    last_error = None
    for attempt in range(8):
        try:
            return action()
        except (HttpError, ConnectionResetError, OSError) as exc:
            last_error = exc
            response = getattr(exc, "resp", None)
            status = int(getattr(response, "status", 0) or 0)
            transient_http = not isinstance(exc, HttpError) or status in {429, 500, 502, 503, 504}
            if not transient_http or attempt == 7:
                raise
            time.sleep(min(60, 2 ** attempt))
    raise last_error  # pragma: no cover - defensive only


def _metadata(service, spreadsheet_id: str) -> Dict[str, Any]:
    return _retry(
        lambda: service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields="spreadsheetId,properties(title),sheets.properties(sheetId,title,index,hidden,sheetType,gridProperties),namedRanges(namedRangeId,name,range)",
        ).execute(),
        "workbook metadata",
    )


def _workbook_signature(metadata: Dict[str, Any]) -> str:
    sheets = []
    for item in sorted(metadata.get("sheets", []), key=lambda row: row["properties"]["index"]):
        props = item["properties"]
        sheets.append({
            "sheet_id": props["sheetId"],
            "title": props["title"],
            "index": props["index"],
            "hidden": props.get("hidden", False),
            "sheet_type": props.get("sheetType", "GRID"),
            "grid_properties": props.get("gridProperties", {}),
        })
    return _json_hash({"title": metadata.get("properties", {}).get("title"), "sheets": sheets})


def _plan_position(position: int) -> Optional[Tuple[str, str]]:
    if 1 <= position <= 11:
        return ("LEGACY_DIAGNOSTICS", "Legacy outcome/economic/sensitivity diagnostics predating current v2.0 architecture.")
    if 95 <= position <= 176:
        return ("PACK_BEHAVIOR_RESEARCH", "Completed Pack Behavior and generalization research.")
    if 177 <= position <= 235:
        return ("CONTROLLED_ACCURACY_RESEARCH", "Completed controlled accuracy design and review research.")
    if 236 <= position <= 315 and position != 264:
        return ("MARKET_REACTION_REPAIR_HISTORY", "Earlier market-reaction repair and canonical-outcome history.")
    if 324 <= position <= 348:
        return ("CORRECTED_ACCURACY_RESEARCH", "Corrected accuracy re-evaluation branch.")
    if 349 <= position <= 819:
        return ("PHASE_9_MECHANISM_RESEARCH", "Phase 9 mechanism research retained as a secondary shadow track.")
    if position == 820:
        return ("OUTCOME_ARCHITECTURE_AUDIT", "Completed Outcome Architecture audit evidence.")
    return None


def _build_plan(metadata: Dict[str, Any]) -> Tuple[List[PlannedSheet], List[Dict[str, Any]]]:
    sheets = sorted(metadata.get("sheets", []), key=lambda row: row["properties"]["index"])
    if metadata.get("properties", {}).get("title") != SOURCE_TITLE:
        raise RuntimeError(f"Expected source workbook {SOURCE_TITLE!r}, found {metadata.get('properties', {}).get('title')!r}.")
    if len(sheets) != EXPECTED_SOURCE_COUNT:
        raise RuntimeError(f"Expected {EXPECTED_SOURCE_COUNT} source sheets, found {len(sheets)}.")
    if metadata.get("namedRanges"):
        raise RuntimeError("Source contains named ranges. This migration requires an explicit named-range preservation plan before continuing.")

    planned: List[PlannedSheet] = []
    retained: List[Dict[str, Any]] = []
    for position, sheet in enumerate(sheets, start=1):
        props = sheet["properties"]
        classification = _plan_position(position)
        if classification is None:
            retained.append({"position": position, "sheet_id": props["sheetId"], "title": props["title"]})
            continue
        family, reason = classification
        planned.append(PlannedSheet(position, props["sheetId"], props["title"], family, reason))

    if len(planned) != EXPECTED_MOVED_COUNT:
        raise RuntimeError(f"Corrected plan selected {len(planned)} sheets; expected {EXPECTED_MOVED_COUNT}.")
    if len(retained) != EXPECTED_RETAINED_COUNT:
        raise RuntimeError(f"Corrected plan retained {len(retained)} sheets; expected {EXPECTED_RETAINED_COUNT}.")
    if [row["position"] for row in retained if row["position"] in {53, 81}] != [53, 81]:
        raise RuntimeError("Option 1 correction failed: positions 53 and 81 must be retained.")
    return planned, retained


def _sanitize(value: Any, top_level: bool = False) -> Any:
    """Remove copy-specific IDs and calculated display fields before hashing."""
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if not isinstance(value, dict):
        return value
    result: Dict[str, Any] = {}
    for key, item in value.items():
        if key in VOLATILE_FIELDS:
            continue
        if top_level and key == "properties":
            properties = copy.deepcopy(item)
            properties.pop("sheetId", None)
            properties.pop("index", None)
            properties.pop("title", None)
            result[key] = _sanitize(properties)
            continue
        result[key] = _sanitize(item)
    return result


def _full_sheet_snapshot(service, spreadsheet_id: str, title: str) -> Dict[str, Any]:
    response = _retry(
        lambda: service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            ranges=[_quote_sheet(title)],
            includeGridData=True,
        ).execute(),
        f"full snapshot for {title}",
    )
    sheets = response.get("sheets", [])
    if len(sheets) != 1:
        raise RuntimeError(f"Expected one returned sheet for {title!r}, received {len(sheets)}.")
    return _sanitize(sheets[0], top_level=True)


def _snapshot_summary(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    props = snapshot.get("properties", {})
    data = snapshot.get("data", [])
    row_count = sum(len(grid.get("rowData", [])) for grid in data)
    col_count = 0
    for grid in data:
        for row in grid.get("rowData", []):
            col_count = max(col_count, len(row.get("values", [])))
    return {
        "fingerprint": _json_hash(snapshot),
        "grid_row_data_count": row_count,
        "grid_column_data_count": col_count,
        "merge_count": len(snapshot.get("merges", [])),
        "chart_count": len(snapshot.get("charts", [])),
        "filter_view_count": len(snapshot.get("filterViews", [])),
        "conditional_format_count": len(snapshot.get("conditionalFormats", [])),
        "hidden": bool(props.get("hidden", False)),
    }


def _create_archive(service) -> str:
    created = _retry(
        lambda: service.spreadsheets().create(
            body={
                "properties": {"title": ARCHIVE_TITLE},
                "sheets": [{"properties": {"title": INDEX_SHEET, "index": 0}}],
            }
        ).execute(),
        "create Archive 02",
    )
    archive_id = created["spreadsheetId"]
    _retry(
        lambda: service.spreadsheets().batchUpdate(
            spreadsheetId=archive_id,
            body={"requests": [{"addSheet": {"properties": {"title": MOVE_LOG_SHEET, "index": 1}}}]},
        ).execute(),
        "create Archive 02 move log",
    )
    _retry(
        lambda: service.spreadsheets().values().batchUpdate(
            spreadsheetId=archive_id,
            body={
                "valueInputOption": "RAW",
                "data": [
                    {"range": f"{_quote_sheet(INDEX_SHEET)}!A1", "values": [INDEX_HEADERS]},
                    {"range": f"{_quote_sheet(MOVE_LOG_SHEET)}!A1", "values": [MOVE_LOG_HEADERS]},
                ],
            },
        ).execute(),
        "initialize Archive 02 headers",
    )
    return archive_id


def _validate_archive_shell(service, archive_id: str) -> None:
    metadata = _metadata(service, archive_id)
    titles = [row["properties"]["title"] for row in sorted(metadata.get("sheets", []), key=lambda row: row["properties"]["index"])]
    if titles[:2] != [INDEX_SHEET, MOVE_LOG_SHEET]:
        raise RuntimeError("Archive 02 does not begin with Archive_02_Index and Archive_02_Move_Log.")


def _copy_sheet(service, plan: PlannedSheet, archive_id: str, target_index: int) -> None:
    response = _retry(
        lambda: service.spreadsheets().sheets().copyTo(
            spreadsheetId=DIAGNOSTICS_ID,
            sheetId=plan.sheet_id,
            body={"destinationSpreadsheetId": archive_id},
        ).execute(),
        f"copy {plan.title}",
    )
    copied_id = response["sheetId"]
    _retry(
        lambda: service.spreadsheets().batchUpdate(
            spreadsheetId=archive_id,
            body={
                "requests": [{
                    "updateSheetProperties": {
                        "properties": {"sheetId": copied_id, "title": plan.title, "index": target_index},
                        "fields": "title,index",
                    }
                }]
            },
        ).execute(),
        f"rename and position {plan.title}",
    )


def _rename_and_position_sheet(service, archive_id: str, sheet_id: int, title: str, target_index: int) -> None:
    _retry(
        lambda: service.spreadsheets().batchUpdate(
            spreadsheetId=archive_id,
            body={
                "requests": [{
                    "updateSheetProperties": {
                        "properties": {"sheetId": sheet_id, "title": title, "index": target_index},
                        "fields": "title,index",
                    }
                }]
            },
        ).execute(),
        f"rename and position {title}",
    )


def _archive_titles(service, archive_id: str) -> Dict[str, Dict[str, Any]]:
    metadata = _metadata(service, archive_id)
    return {item["properties"]["title"]: item["properties"] for item in metadata.get("sheets", [])}


def _write_values(service, archive_id: str, sheet_name: str, start_cell: str, rows: Sequence[Sequence[Any]]) -> None:
    _retry(
        lambda: service.spreadsheets().values().update(
            spreadsheetId=archive_id,
            range=f"{_quote_sheet(sheet_name)}!{start_cell}",
            valueInputOption="RAW",
            body={"values": list(rows)},
        ).execute(),
        f"write {sheet_name}",
    )


def _delete_source_sheets(service, planned: Iterable[PlannedSheet]) -> None:
    requests = [{"deleteSheet": {"sheetId": item.sheet_id}} for item in planned]
    for offset in range(0, len(requests), 100):
        _retry(
            lambda chunk=requests[offset:offset + 100]: service.spreadsheets().batchUpdate(
                spreadsheetId=DIAGNOSTICS_ID,
                body={"requests": chunk},
            ).execute(),
            f"delete validated source batch {offset // 100 + 1}",
        )


def _report_paths(timestamp: str) -> Tuple[Path, Path]:
    safe_ts = timestamp.replace(":", "-")
    output_dir = ROOT / "outputs" / "diagnostics_archive_02_cleanup"
    output_dir.mkdir(parents=True, exist_ok=True)
    return (
        output_dir / f"{safe_ts}_verification.json",
        output_dir / f"{safe_ts}_completion_report.md",
    )


def _checkpoint_path() -> Path:
    return ROOT / "outputs" / "diagnostics_archive_02_cleanup" / "active_migration_checkpoint.json"


def _write_checkpoint(payload: Dict[str, Any]) -> None:
    path = _checkpoint_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp_path, path)


def _clear_checkpoint() -> None:
    _checkpoint_path().unlink(missing_ok=True)


def _write_reports(timestamp: str, report: Dict[str, Any]) -> Tuple[Path, Path]:
    json_path, markdown_path = _report_paths(timestamp)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Diagnostics Archive 02 Cleanup",
        "",
        f"- Decision: `{report['final_decision']}`",
        f"- Source sheet count: `{report.get('source_sheet_count', '')}`",
        f"- Sheets copied: `{report.get('sheets_copied', '')}`",
        f"- Sheets verified: `{report.get('sheets_verified', '')}`",
        f"- Sheets removed from active workbook: `{report.get('sheets_removed', '')}`",
        f"- Final active workbook sheet count: `{report.get('final_active_sheet_count', '')}`",
        f"- Archive 02 sheet count: `{report.get('archive_sheet_count', '')}`",
        f"- Archive 02 spreadsheet ID: `{report.get('archive_spreadsheet_id', '')}`",
        "",
        "## Retained Positions",
        "",
        ", ".join(str(item["position"]) for item in report.get("retained_positions", [])),
        "",
        "## Unsupported Features",
        "",
        "- Google Sheets API does not expose threaded Drive comments for per-sheet verification. Cell notes are included in the snapshot comparison.",
        "",
        "## Warnings",
        "",
    ]
    lines.extend([f"- {warning}" for warning in report.get("warnings", [])] or ["- None"])
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, markdown_path


def execute(archive_id: Optional[str], dry_run: bool) -> Dict[str, Any]:
    timestamp = _now()
    service = build_sheets_service(load_credentials(interactive=False))
    source_metadata = _metadata(service, DIAGNOSTICS_ID)
    planned, retained = _build_plan(source_metadata)
    source_hash_before = _workbook_signature(source_metadata)
    report: Dict[str, Any] = {
        "generated_ts": timestamp,
        "source_workbook": SOURCE_TITLE,
        "source_spreadsheet_id": DIAGNOSTICS_ID,
        "source_sheet_count": EXPECTED_SOURCE_COUNT,
        "planned_move_count": len(planned),
        "planned_retain_count": len(retained),
        "retained_positions": retained,
        "implementation_fingerprint": _implementation_fingerprint(),
        "source_workbook_hash_before_modification": source_hash_before,
        "archive_spreadsheet_id": archive_id or "",
        "sheets_copied": 0,
        "sheets_verified": 0,
        "sheets_removed": 0,
        "verification": [],
        "warnings": [],
        "final_decision": "DIAGNOSTICS_ARCHIVE_02_CLEANUP_BLOCKED",
    }

    if dry_run:
        report["warnings"].append("Dry run only. No Archive 02 workbook was created and no source sheets were changed.")
        _write_reports(timestamp, report)
        return report

    if archive_id:
        _validate_archive_shell(service, archive_id)
    else:
        archive_id = _create_archive(service)
        report["archive_spreadsheet_id"] = archive_id
    _write_checkpoint({
        "created_ts": timestamp,
        "archive_spreadsheet_id": archive_id,
        "source_spreadsheet_id": DIAGNOSTICS_ID,
        "source_workbook_hash_before_modification": source_hash_before,
        "planned_move_count": len(planned),
        "status": "COPYING",
    })
    _validate_archive_shell(service, archive_id)

    # The archive log records the pre-movement audit before the first copy.
    _write_values(service, archive_id, MOVE_LOG_SHEET, "A2", [[
        "PRE_COPY",
        SOURCE_TITLE,
        ARCHIVE_TITLE,
        EXPECTED_SOURCE_COUNT,
        EXPECTED_RETAINED_COUNT,
        EXPECTED_MOVED_COUNT,
        timestamp,
        report["implementation_fingerprint"],
        source_hash_before,
        "",
        "",
        "IN_PROGRESS",
        "Option 1 correction retained named positions 53 and 81. Threaded Drive comments are not API-verifiable; cell notes are verified.",
    ]])

    archive_by_title = _archive_titles(service, archive_id)
    for sequence, item in enumerate(planned, start=1):
        existing = archive_by_title.get(item.title)
        if existing:
            # Full equivalence is checked for every planned sheet in the final
            # verification pass before deletion. Skipping here makes recovery
            # from a connection interruption practical without weakening safety.
            continue
        interrupted_copy = archive_by_title.get(f"Copy of {item.title}")
        if interrupted_copy:
            _rename_and_position_sheet(service, archive_id, interrupted_copy["sheetId"], item.title, sequence + 1)
            archive_by_title = _archive_titles(service, archive_id)
            continue
        _copy_sheet(service, item, archive_id, sequence + 1)
        archive_by_title = _archive_titles(service, archive_id)
        report["sheets_copied"] += 1

    archive_metadata = _metadata(service, archive_id)
    archive_order = [item["properties"]["title"] for item in sorted(archive_metadata.get("sheets", []), key=lambda row: row["properties"]["index"])]
    expected_order = [INDEX_SHEET, MOVE_LOG_SHEET] + [item.title for item in planned]
    if archive_order != expected_order:
        raise RuntimeError("Archive sheet names or relative order did not match the source migration plan.")

    index_rows: List[List[Any]] = []
    for sequence, item in enumerate(planned, start=1):
        source_snapshot = _full_sheet_snapshot(service, DIAGNOSTICS_ID, item.title)
        destination_snapshot = _full_sheet_snapshot(service, archive_id, item.title)
        source_summary = _snapshot_summary(source_snapshot)
        destination_summary = _snapshot_summary(destination_snapshot)
        passed = source_summary["fingerprint"] == destination_summary["fingerprint"]
        report["verification"].append({
            "sequence": sequence,
            "position": item.position,
            "sheet_name": item.title,
            "research_family": item.family,
            "source": source_summary,
            "destination": destination_summary,
            "result": "PASS" if passed else "FAIL",
        })
        if not passed:
            raise RuntimeError(f"Verification failed for {item.title!r}; source tabs were not deleted.")
        report["sheets_verified"] += 1
        index_rows.append([
            sequence,
            item.position,
            item.title,
            item.family,
            item.reason,
            SOURCE_TITLE,
            timestamp,
            "PASS",
        ])

    # Confirm the source tab identity did not change while copies were being validated.
    source_before_delete = _metadata(service, DIAGNOSTICS_ID)
    if _workbook_signature(source_before_delete) != source_hash_before:
        raise RuntimeError("Source workbook sheet structure changed during migration; source tabs were not deleted.")

    _delete_source_sheets(service, planned)
    report["sheets_removed"] = len(planned)
    final_source = _metadata(service, DIAGNOSTICS_ID)
    final_archive = _metadata(service, archive_id)
    final_source_titles = {item["properties"]["title"] for item in final_source.get("sheets", [])}
    final_archive_order = [item["properties"]["title"] for item in sorted(final_archive.get("sheets", []), key=lambda row: row["properties"]["index"])]
    if len(final_source.get("sheets", [])) != EXPECTED_RETAINED_COUNT:
        raise RuntimeError("Source workbook did not finish with exactly 92 retained sheets.")
    if len(final_archive.get("sheets", [])) != EXPECTED_MOVED_COUNT + 2:
        raise RuntimeError("Archive 02 did not finish with 728 moved sheets plus its index/log tabs.")
    if any(item.title in final_source_titles for item in planned):
        raise RuntimeError("At least one moved sheet remains in the active diagnostics workbook.")
    if any(item["title"] not in final_source_titles for item in retained):
        raise RuntimeError("At least one retained sheet is missing from the active diagnostics workbook.")
    if final_archive_order != expected_order:
        raise RuntimeError("Archive 02 final sheet order changed unexpectedly.")

    _write_values(service, archive_id, INDEX_SHEET, "A2", index_rows)
    source_hash_after = _workbook_signature(final_source)
    archive_hash_after = _workbook_signature(final_archive)
    _write_values(service, archive_id, MOVE_LOG_SHEET, "A3", [[
        "POST_VERIFY",
        SOURCE_TITLE,
        ARCHIVE_TITLE,
        EXPECTED_SOURCE_COUNT,
        EXPECTED_RETAINED_COUNT,
        EXPECTED_MOVED_COUNT,
        _now(),
        report["implementation_fingerprint"],
        source_hash_before,
        source_hash_after,
        archive_hash_after,
        "PASS",
        "728 sheets copied and fully verified before source deletion. Positions 53 and 81 were retained by approved Option 1 correction.",
    ]])
    report.update({
        "final_active_sheet_count": len(final_source.get("sheets", [])),
        "archive_sheet_count": len(final_archive.get("sheets", [])),
        "active_workbook_hash_after_modification": source_hash_after,
        "archive_workbook_hash": archive_hash_after,
        "final_decision": "DIAGNOSTICS_ARCHIVE_02_CLEANUP_COMPLETED",
    })
    _clear_checkpoint()
    _write_reports(timestamp, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-id", help="Resume a previously created Archive 02 workbook after a copy-only interruption.")
    parser.add_argument("--execute", action="store_true", help="Perform the migration. Omit for preflight-only dry run.")
    args = parser.parse_args()
    try:
        result = execute(args.archive_id, dry_run=not args.execute)
    except Exception as exc:
        timestamp = _now()
        failure = {
            "generated_ts": timestamp,
            "final_decision": "DIAGNOSTICS_ARCHIVE_02_VERIFICATION_FAILED",
            "error": str(exc),
            "warnings": ["No source sheets are deleted until every copied sheet has passed verification."],
        }
        json_path, markdown_path = _write_reports(timestamp, failure)
        print(json.dumps({**failure, "json_report": str(json_path), "completion_report": str(markdown_path)}, indent=2, sort_keys=True))
        raise SystemExit(1)
    json_path, markdown_path = _write_reports(result["generated_ts"], result)
    print(json.dumps({**result, "json_report": str(json_path), "completion_report": str(markdown_path)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
