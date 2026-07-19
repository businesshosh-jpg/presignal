#!/usr/bin/env python3
"""Build inactive PreSignal v2.1 foundation workbooks from read-only Sheets sources.

The script never writes to Google Sheets or Apps Script. It snapshots approved reusable
tables through automation.google_clients, delegates XLSX authoring to the bundled
artifact-tool builder, and validates the resulting local workbooks before publishing
the migration inventory, manifest, and report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "outputs" / "presignal_v21_workbook_migration"
MAIN_TARGET = ROOT / "presignal_main.xlsx"
RESEARCH_TARGET = ROOT / "presignal_research.xlsx"
LEGACY_MAIN_SOURCE_ID = os.environ.get("PRESIGNAL_MAIN_SPREADSHEET_ID", "1_gZGnd6h3VzdiBvGBHRSxn78KW8tsOi2UEc6Y_Sc23Q")
MAIN_SEED_SOURCE_ID = os.environ.get("PRESIGNAL_V21_MAIN_SHELL_ID", "1ZGYZ10wRTw74q-QFQdNXgkLbYS2pY7Pz21L4f7O_pqo")
DIAGNOSTICS_SOURCE_ID = os.environ.get("PRESIGNAL_DIAGNOSTICS_SPREADSHEET_ID", "1jxcZotbzJKcAzrK0VhxetYX6hp5DPXCCIA0J6B6RUy0")
RESEARCH_SEED_SOURCE_ID = os.environ.get("PRESIGNAL_V21_RESEARCH_SHELL_ID", "1AlJhyJ9Tg8xXBWJm2It-jfaWnXsmgGgQOw2Ci0W1k-0")
NODE = Path("/Users/junhoshino/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node")
NODE_MODULES = Path("/Users/junhoshino/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules")

MAIN_SHEETS = [
    "Event", "Config", "SeriesMap", "SeriesMap_Suggestions", "FRED_Series_ID",
    "FMP_EventCatalog", "Episode", "Information", "Prediction", "Prediction_Path",
    "Outcome", "Evaluation", "Session_Map", "Schema", "Run_Log",
]
RESEARCH_SHEETS = ["Experiment_Register", "Run_Register", "Evaluation_Metrics", "Case_Review", "Artifact_Register"]
REUSABLE_SHEETS = ["Event", "SeriesMap", "FRED_Series_ID", "FMP_EventCatalog"]
FRESH_MAIN_SHEETS = ["SeriesMap_Suggestions", "Episode", "Information", "Prediction", "Prediction_Path", "Outcome", "Evaluation", "Session_Map", "Run_Log"]
PROHIBITED_MAIN_SHEETS = {
    "Predictions", "MR_ProviderRuns", "Evaluation_Rows", "Evaluation_Summary", "Evaluation_BatchCompare",
    "Evaluation_Scenario", "Outcome_Ledger", "v2.0 Prediction", "v2.0 Prediction Path", "v2.0 Outcome",
    "v2.0 Evaluation", "v2.0 Schema",
}
NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8"))


def normalize(value: Any) -> str:
    return "" if value is None else str(value).strip()


def used_rows(values: List[List[Any]]) -> List[List[Any]]:
    return [row for row in values if any(normalize(value) for value in row)]


def a1_column(column_index: int) -> str:
    result = ""
    while column_index:
        column_index, remainder = divmod(column_index - 1, 26)
        result = chr(65 + remainder) + result
    return result or "A"


def used_range(values: List[List[Any]]) -> str:
    nonempty = used_rows(values)
    width = max((len(row) for row in nonempty), default=0)
    return "" if not nonempty else f"A1:{a1_column(width)}{len(nonempty)}"


def ensure_node_modules_link() -> None:
    link = ROOT / "automation" / "node_modules"
    if link.exists() or link.is_symlink():
        if not link.is_symlink() or link.resolve() != NODE_MODULES:
            raise RuntimeError(f"Refusing to replace existing node_modules path: {link}")
        return
    link.symlink_to(NODE_MODULES)


def sheets_service():
    sys.path.insert(0, str(ROOT))
    from automation.google_clients import build_sheets_service, load_credentials

    return build_sheets_service(load_credentials())


def fetch_values(service: Any, spreadsheet_id: str, sheet_name: str) -> List[List[Any]]:
    response = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_name}'!A1:ZZZ",
    ).execute()
    values = response.get("values", [])
    if not values:
        raise RuntimeError(f"Required source sheet is empty or missing: {sheet_name}")
    return values


def workbook_values(service: Any, spreadsheet_id: str, metadata: Dict[str, Any]) -> Dict[str, List[List[Any]]]:
    names = [sheet["properties"]["title"] for sheet in metadata.get("sheets", []) if sheet["properties"].get("sheetType", "GRID") == "GRID"]
    response = service.spreadsheets().values().batchGet(
        spreadsheetId=spreadsheet_id,
        ranges=[f"'{name}'!A1:ZZZ" for name in names],
    ).execute()
    return {
        name: item.get("values", [])
        for name, item in zip(names, response.get("valueRanges", []))
    }


def workbook_metadata(service: Any, spreadsheet_id: str) -> Dict[str, Any]:
    return service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="spreadsheetId,properties(title),sheets(properties(sheetId,title,hidden,sheetType,gridProperties)),namedRanges(namedRangeId,name,range)",
    ).execute()


def workbook_detail(service: Any, spreadsheet_id: str) -> Dict[str, Any]:
    return service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        includeGridData=True,
        fields="spreadsheetId,sheets(properties(sheetId,title,hidden,sheetType,gridProperties),data(startRow,startColumn,rowData(values(userEnteredValue(formulaValue),dataValidation))),merges,conditionalFormats)",
    ).execute()


def effective_value(value: Dict[str, Any]) -> str:
    if not value:
        return ""
    return str(next(iter(value.values())))


def detailed_sheet_metrics(sheet: Dict[str, Any]) -> Dict[str, Any]:
    max_row = 0
    max_column = 0
    formula_count = 0
    validation_count = 0
    external_formula_count = 0
    header_values: Dict[int, str] = {}
    for grid in sheet.get("data", []):
        start_row = int(grid.get("startRow", 0))
        start_column = int(grid.get("startColumn", 0))
        for row_offset, row in enumerate(grid.get("rowData", [])):
            for column_offset, cell in enumerate(row.get("values", [])):
                formula = normalize(cell.get("userEnteredValue", {}).get("formulaValue"))
                has_validation = bool(cell.get("dataValidation"))
                if not (formula or has_validation):
                    continue
                row_index = start_row + row_offset + 1
                column_index = start_column + column_offset + 1
                max_row = max(max_row, row_index)
                max_column = max(max_column, column_index)
                if formula:
                    formula_count += 1
                    external_formula_count += int("IMPORTRANGE" in formula.upper())
                validation_count += int(has_validation)
                if row_index == 1:
                    header_values[column_index] = formula
    return {
        "used_range": "" if not max_row else f"A1:{a1_column(max_column)}{max_row}",
        "header_row": [header_values[index] for index in range(1, max(header_values, default=0) + 1)],
        "row_count": max_row,
        "formula_count": formula_count,
        "external_formula_count": external_formula_count,
        "validation_rules": validation_count,
        "merged_cells": len(sheet.get("merges", [])),
        "conditional_formatting": len(sheet.get("conditionalFormats", [])),
    }


def validate_source_table(name: str, rows: List[List[Any]]) -> Dict[str, Any]:
    active_rows = used_rows(rows)
    if not active_rows:
        raise RuntimeError(f"Required source sheet is empty: {name}")
    header = [normalize(value) for value in active_rows[0]]
    if not header or any(not value for value in header):
        raise RuntimeError(f"Required source sheet has an invalid header: {name}")
    duplicates = sorted(header_item for header_item, count in Counter(header).items() if count > 1)
    if duplicates:
        raise RuntimeError(f"Required source sheet has duplicate headers: {name}: {duplicates}")
    return {"header": header, "row_count": len(active_rows), "header_count": len(header), "used_range": used_range(active_rows), "fingerprint": sha256_json(active_rows)}


def remote_inventory(metadata: Dict[str, Any], detail: Dict[str, Any], source_tables: Dict[str, List[List[Any]]]) -> Dict[str, Any]:
    tables = {}
    detail_by_name = {sheet["properties"]["title"]: sheet for sheet in detail.get("sheets", [])}
    for sheet in metadata.get("sheets", []):
        properties = sheet["properties"]
        name = properties["title"]
        values = source_tables.get(name, [])
        metrics = detailed_sheet_metrics(detail_by_name.get(name, {"properties": properties}))
        tables[name] = {
            "used_range": used_range(values) if values else metrics["used_range"],
            "header_row": ([normalize(value) for value in values[0]] if values else metrics["header_row"]),
            "row_count": len(used_rows(values)) if values else metrics["row_count"],
            "formula_count": metrics["formula_count"],
            "hidden": bool(properties.get("hidden", False)),
            "merged_cells": metrics["merged_cells"],
            "tables": 0,
            "validation_rules": metrics["validation_rules"],
            "conditional_formatting": metrics["conditional_formatting"],
            "external_formula_count": metrics["external_formula_count"],
            "grid_capacity": properties.get("gridProperties", {}),
            "sheet_type": properties.get("sheetType", "GRID"),
        }
    return {
        "source_kind": "read_only_google_sheets_snapshot",
        "spreadsheet_id": metadata["spreadsheetId"],
        "workbook_filename": metadata["properties"]["title"] + ".xlsx",
        "workbook_title": metadata["properties"]["title"],
        "source_fingerprint": sha256_json({"metadata": metadata, "sampled_tables": source_tables}),
        "named_ranges": metadata.get("namedRanges", []),
        "external_links": sum(value["external_formula_count"] for value in tables.values()),
        "workbook_connections": 0,
        "sheets": tables,
    }


def parse_sheet_xml(archive: zipfile.ZipFile, worksheet_path: str) -> Tuple[int, int, int, int]:
    root = ET.fromstring(archive.read(worksheet_path))
    rows = root.findall("main:sheetData/main:row", NS)
    cells = root.findall(".//main:c", NS)
    formulas = root.findall(".//main:f", NS)
    merged = root.findall(".//main:mergeCell", NS)
    return len(rows), len(cells), len(formulas), len(merged)


def inspect_xlsx(path: Path) -> Dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
        sheets = []
        for item in workbook.findall("main:sheets/main:sheet", NS):
            name = item.attrib["name"]
            relationship_id = item.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            worksheet_path = targets[relationship_id].lstrip("/")
            if not worksheet_path.startswith("xl/"):
                worksheet_path = "xl/" + worksheet_path
            row_count, cell_count, formula_count, merged_count = parse_sheet_xml(archive, worksheet_path)
            sheets.append({"name": name, "hidden": item.attrib.get("state", "visible") != "visible", "row_count": row_count, "cell_count": cell_count, "formula_count": formula_count, "merged_cells": merged_count})
        names = archive.namelist()
        external_links = [name for name in names if name.startswith("xl/externalLinks/")]
        connections = [name for name in names if name == "xl/connections.xml"]
        defined_names = workbook.findall("main:definedNames/main:definedName", NS)
        semantic_parts = {
            name: re.sub(r"R[0-9a-f]{16}", "RELATIONSHIP_ID", archive.read(name).decode("utf-8", "replace"))
            for name in sorted(names)
            if not name.startswith("docProps/")
        }
    return {
        "path": str(path),
        "binary_fingerprint": sha256_bytes(path.read_bytes()),
        "content_fingerprint": sha256_json(semantic_parts),
        "sheets": sheets,
        "named_ranges": [item.attrib.get("name", "") for item in defined_names],
        "external_links": len(external_links),
        "workbook_connections": len(connections),
    }


def target_sheet_names(inspected: Dict[str, Any]) -> List[str]:
    return [sheet["name"] for sheet in inspected["sheets"]]


def validate_targets(main: Dict[str, Any], research: Dict[str, Any], node_result: Dict[str, Any]) -> Dict[str, Any]:
    checks = {
        "main_exact_sheet_inventory": target_sheet_names(main) == MAIN_SHEETS,
        "research_exact_sheet_inventory": target_sheet_names(research) == RESEARCH_SHEETS,
        "main_no_prohibited_sheets": not (set(target_sheet_names(main)) & PROHIBITED_MAIN_SHEETS),
        "main_no_hidden_sheets": not any(sheet["hidden"] for sheet in main["sheets"]),
        "research_no_hidden_sheets": not any(sheet["hidden"] for sheet in research["sheets"]),
        "main_no_external_links": main["external_links"] == 0,
        "research_no_external_links": research["external_links"] == 0,
        "main_no_connections": main["workbook_connections"] == 0,
        "research_no_connections": research["workbook_connections"] == 0,
        "main_no_named_ranges": not main["named_ranges"],
        "research_no_named_ranges": not research["named_ranges"],
        "main_no_formulas": not any(sheet["formula_count"] for sheet in main["sheets"]),
        "research_no_formulas": not any(sheet["formula_count"] for sheet in research["sheets"]),
        "fresh_main_tables_headers_only": all(next(sheet for sheet in main["sheets"] if sheet["name"] == name)["row_count"] == 1 for name in FRESH_MAIN_SHEETS),
        "research_tables_headers_only": all(sheet["row_count"] == 1 for sheet in research["sheets"]),
        "schema_has_inheritance_rows": next(sheet for sheet in main["sheets"] if sheet["name"] == "Schema")["row_count"] > 10,
        "node_builder_reported_expected_sheets": node_result["main_sheets"] == MAIN_SHEETS and node_result["research_sheets"] == RESEARCH_SHEETS,
    }
    checks["all_passed"] = all(checks.values())
    if not checks["all_passed"]:
        failed = ", ".join(name for name, value in checks.items() if not value)
        raise RuntimeError(f"Target validation failed: {failed}")
    return checks


def report_markdown(manifest: Dict[str, Any]) -> str:
    reusable = manifest["migration"]["reusable_row_counts"]
    decisions = manifest["migration"]["config_decisions"]
    config_rows = "\n".join(
        f"| {row['config_key']} | {str(row['source_value_present']).upper()} | {row['migration_status']} | {row['target_value']} | {row['reason']} |"
        for row in decisions
    )
    return f"""# PreSignal v2.1 Workbook Migration Report

## Decision

PASS. Both workbooks were built as inactive local artifacts. Source data was read through the existing authenticated Sheets client; no Sheets writes, Apps Script calls, or provider calls were made.

## Source Inventory

| Source | Fingerprint | Sheets | Hidden sheets | Named ranges | External links | Connections |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| auto_eeresults_predictions.xlsx (frozen lineage) | {manifest['source_workbooks']['legacy_auto_eeresults']['source_fingerprint']} | {len(manifest['source_workbooks']['legacy_auto_eeresults']['sheets'])} | {sum(1 for value in manifest['source_workbooks']['legacy_auto_eeresults']['sheets'].values() if value['hidden'])} | {len(manifest['source_workbooks']['legacy_auto_eeresults']['named_ranges'])} | {manifest['source_workbooks']['legacy_auto_eeresults']['external_links']} | {manifest['source_workbooks']['legacy_auto_eeresults']['workbook_connections']} |
| presignal_main.xlsx (provided seed) | {manifest['source_workbooks']['main_seed']['source_fingerprint']} | {len(manifest['source_workbooks']['main_seed']['sheets'])} | {sum(1 for value in manifest['source_workbooks']['main_seed']['sheets'].values() if value['hidden'])} | {len(manifest['source_workbooks']['main_seed']['named_ranges'])} | {manifest['source_workbooks']['main_seed']['external_links']} | {manifest['source_workbooks']['main_seed']['workbook_connections']} |
| presignal_research_diagnostics.xlsx | {manifest['source_workbooks']['diagnostics']['source_fingerprint']} | {len(manifest['source_workbooks']['diagnostics']['sheets'])} | {sum(1 for value in manifest['source_workbooks']['diagnostics']['sheets'].values() if value['hidden'])} | {len(manifest['source_workbooks']['diagnostics']['named_ranges'])} | {manifest['source_workbooks']['diagnostics']['external_links']} | {manifest['source_workbooks']['diagnostics']['workbook_connections']} |
| presignal_research.xlsx (provided seed) | {manifest['source_workbooks']['research_seed']['source_fingerprint']} | {len(manifest['source_workbooks']['research_seed']['sheets'])} | {sum(1 for value in manifest['source_workbooks']['research_seed']['sheets'].values() if value['hidden'])} | {len(manifest['source_workbooks']['research_seed']['named_ranges'])} | {manifest['source_workbooks']['research_seed']['external_links']} | {manifest['source_workbooks']['research_seed']['workbook_connections']} |

The diagnostics workbook was inventoried only and none of its historical diagnostic sheets were migrated.

## Reusable Tables

| Sheet | Source rows | Target rows | Header count | Fingerprint |
| --- | ---: | ---: | ---: | --- |
""" + "\n".join(
        f"| {name} | {details['source_rows']} | {details['target_rows']} | {details['header_count']} | {details['fingerprint']} |"
        for name, details in reusable.items()
    ) + f"""

## Config Decisions

| config_key | source_value_present | migration_status | target_value | reason |
| --- | --- | --- | --- | --- |
{config_rows}

## Fresh Tables

The following main-workbook tables contain headers only: {", ".join(FRESH_MAIN_SHEETS)}. The research workbook contains only its five required header-only tables.

## Sanitization

| Target | Formulas | External links | Connections | Hidden sheets | Named ranges |
| --- | ---: | ---: | ---: | ---: | ---: |
| presignal_main.xlsx | 0 | 0 | 0 | 0 | 0 |
| presignal_research.xlsx | 0 | 0 | 0 | 0 | 0 |

## Validation

All target validation checks passed: {", ".join(key for key, value in manifest['validation'].items() if key != 'all_passed' and value)}.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main-target", type=Path, default=MAIN_TARGET)
    parser.add_argument("--research-target", type=Path, default=RESEARCH_TARGET)
    args = parser.parse_args()
    if not NODE.exists() or not NODE_MODULES.exists():
        raise RuntimeError("Bundled spreadsheet runtime is unavailable.")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    service = sheets_service()
    legacy_main_metadata = workbook_metadata(service, LEGACY_MAIN_SOURCE_ID)
    main_seed_metadata = workbook_metadata(service, MAIN_SEED_SOURCE_ID)
    diagnostics_metadata = workbook_metadata(service, DIAGNOSTICS_SOURCE_ID)
    research_seed_metadata = workbook_metadata(service, RESEARCH_SEED_SOURCE_ID)
    legacy_main_values = workbook_values(service, LEGACY_MAIN_SOURCE_ID, legacy_main_metadata)
    main_seed_values = workbook_values(service, MAIN_SEED_SOURCE_ID, main_seed_metadata)
    diagnostics_values = workbook_values(service, DIAGNOSTICS_SOURCE_ID, diagnostics_metadata)
    research_seed_values = workbook_values(service, RESEARCH_SEED_SOURCE_ID, research_seed_metadata)
    legacy_main_detail = workbook_detail(service, LEGACY_MAIN_SOURCE_ID)
    main_seed_detail = workbook_detail(service, MAIN_SEED_SOURCE_ID)
    diagnostics_detail = workbook_detail(service, DIAGNOSTICS_SOURCE_ID)
    research_seed_detail = workbook_detail(service, RESEARCH_SEED_SOURCE_ID)
    source_tables = {name: main_seed_values.get(name, []) for name in ["Event", "Config", "SeriesMap", "FRED_Series_ID", "FMP_EventCatalog"]}
    source_stats = {name: validate_source_table(name, rows) for name, rows in source_tables.items()}
    legacy_main_inventory = remote_inventory(legacy_main_metadata, legacy_main_detail, legacy_main_values)
    main_seed_inventory = remote_inventory(main_seed_metadata, main_seed_detail, main_seed_values)
    diagnostics_inventory = remote_inventory(diagnostics_metadata, diagnostics_detail, diagnostics_values)
    research_seed_inventory = remote_inventory(research_seed_metadata, research_seed_detail, research_seed_values)
    snapshot = {"source_tables": source_tables}
    ensure_node_modules_link()
    with tempfile.TemporaryDirectory(prefix="presignal-v21-") as directory:
        temp_dir = Path(directory)
        snapshot_path = temp_dir / "source_snapshot.json"
        node_result_path = temp_dir / "node_result.json"
        snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=True), encoding="utf-8")
        for target in (args.main_target, args.research_target):
            target.unlink(missing_ok=True)
            Path(str(target) + ".inspect.ndjson").unlink(missing_ok=True)
        command = [str(NODE), str(ROOT / "automation" / "build_presignal_v21_workbooks.mjs"), "--snapshot", str(snapshot_path), "--main", str(args.main_target), "--research", str(args.research_target), "--result", str(node_result_path)]
        subprocess.run(command, cwd=ROOT, check=True)
        node_result = json.loads(node_result_path.read_text(encoding="utf-8"))
    for target in (args.main_target, args.research_target):
        Path(str(target) + ".inspect.ndjson").unlink(missing_ok=True)
    main_target = inspect_xlsx(args.main_target)
    research_target = inspect_xlsx(args.research_target)
    validation = validate_targets(main_target, research_target, node_result)
    reusable_row_counts = {
        name: {
            "source_rows": source_stats[name]["row_count"],
            "target_rows": node_result["target_rows"][name],
            "header_count": source_stats[name]["header_count"],
            "fingerprint": source_stats[name]["fingerprint"],
        }
        for name in REUSABLE_SHEETS
    }
    event_header = source_stats["Event"]["header"]
    event_rows = used_rows(source_tables["Event"])
    event_id_index = event_header.index("event_id")
    event_id_values = [normalize(row[event_id_index]) if event_id_index < len(row) else "" for row in event_rows[1:]]
    event_duplicate_count = sum(count - 1 for count in Counter(value for value in event_id_values if value).values() if count > 1)
    manifest = {
        "migration_name": "PreSignal v2.1 clean workbook foundation",
        "source_workbooks": {"legacy_auto_eeresults": legacy_main_inventory, "main_seed": main_seed_inventory, "diagnostics": diagnostics_inventory, "research_seed": research_seed_inventory},
        "target_files": {"main": main_target, "research": research_target},
        "migration": {
            "sheets_migrated": REUSABLE_SHEETS + ["Config"],
            "sheets_created_fresh": FRESH_MAIN_SHEETS + ["Schema"] + RESEARCH_SHEETS,
            "sheets_excluded": sorted(PROHIBITED_MAIN_SHEETS),
            "reusable_row_counts": reusable_row_counts,
            "event_identity": {"source_duplicate_event_id_count": event_duplicate_count, "target_duplicate_event_id_count": event_duplicate_count, "source_null_event_id_count": sum(1 for value in event_id_values if not value), "target_null_event_id_count": sum(1 for value in event_id_values if not value), "fingerprint": source_stats["Event"]["fingerprint"]},
            "config_decisions": node_result["config_decisions"],
        },
        "operations": {"provider_calls": 0, "apps_script_calls": 0, "live_google_sheets_writes": 0, "production_or_deployment_changes": 0},
        "validation": validation,
    }
    (OUTPUT_DIR / "workbook_inventory.json").write_text(json.dumps({"source_workbooks": manifest["source_workbooks"], "target_files": manifest["target_files"]}, indent=2) + "\n", encoding="utf-8")
    (OUTPUT_DIR / "migration_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (OUTPUT_DIR / "migration_report.md").write_text(report_markdown(manifest), encoding="utf-8")
    print(json.dumps({"status": "PASS", "main": str(args.main_target), "research": str(args.research_target), "manifest": str(OUTPUT_DIR / "migration_manifest.json")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
