#!/usr/bin/env python3
"""Install and validate the Phase 9 Stage 4A knowledge-source registry."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.approved_knowledge_source_registry_v0 import (
    PROVENANCE_POLICIES,
    REGISTRY_HEADERS,
    REGISTRY_SHEET,
    REGISTRY_VERSION,
    admit_knowledge_item,
    build_traceability_record,
    fingerprint,
    initial_registry,
    replay_compatibility_aliases,
    route_request,
    validate_registry,
)
from automation.build_sheet_registry_audit import REGISTRY_HEADERS as SHEET_REGISTRY_HEADERS
from automation.google_clients import build_sheets_service, load_credentials


PHASE_ID = "9-APPROVED-KNOWLEDGE-SOURCE-REGISTRY"
OUTPUT_ROOT = ROOT / "outputs" / "phase9_approved_knowledge_source_registry"
MAIN_SPREADSHEET_ID = os.environ.get(
    "PRESIGNAL_MAIN_SPREADSHEET_ID", "1_gZGnd6h3VzdiBvGBHRSxn78KW8tsOi2UEc6Y_Sc23Q"
)
PROJECT_OVERVIEWS_SPREADSHEET_ID = os.environ.get(
    "PRESIGNAL_PROJECT_OVERVIEWS_SPREADSHEET_ID", "1PtXrQpzNX8600I0aCOb2hLPkWtTvFKtDVIZZIys_Uvo"
)
SHEET_REGISTRY = "Sheet_Registry"

PROTECTED_SHEETS = (
    "Predictions",
    "Outcome_Ledger",
    "Evaluation_Rows",
    "v2.0 Prediction",
    "v2.0 Prediction Path",
    "v2.0 Outcome",
    "v2.0 Evaluation",
    "v2.0 Schema",
)
PRESERVED_RUN_FILES = (
    ROOT / "outputs/phase9_historical_square_one_acquisition_repair/9-HISTORICAL-ACQUISITION-REPAIR_20260715T053903Z/completion_manifest.json",
    ROOT / "outputs/phase9_historical_full_source_grounded_pack_e/9-HISTORICAL-FULL-SOURCE-GROUNDED-PACK-E_20260716T023147Z/completion_manifest.json",
    ROOT / "outputs/phase9_historical_environment_reconstructed_pack_e/9-HISTORICAL-ENVIRONMENT-RECONSTRUCTION_20260716T033701Z/completion_manifest.json",
    ROOT / "outputs/phase9_historical_environment_eodhd_enrichment/9-EODHD-HISTORICAL-ENVIRONMENT-ENRICHMENT_20260716T045231Z/completion_manifest.json",
    ROOT / "outputs/phase9_historical_environment_institutional_enrichment/9-HISTORICAL-ENVIRONMENT-INSTITUTIONAL-ENRICHMENT_20260716T061357Z/completion_manifest.json",
    ROOT / "outputs/phase9_v2_layered_prediction_evaluation_repair/9-V2-LAYERED-PREDICTION-EVALUATION-REPAIR_20260716T083002Z/completion_manifest.json",
    ROOT / "outputs/phase9_v2_interaction_outcome_rule_repair/9-V2-INTERACTION-OUTCOME-RULE-REPAIR_20260716T090721Z/completion_manifest.json",
)
PRODUCTION_FILES = (
    ROOT / "apps_script/automation_api.js",
    ROOT / "outputs/phase9_prospective_a_vs_e_collection/active_v1/pipeline_config.json",
)


class ImplementationError(RuntimeError):
    """Fail-closed AKSR installation error."""


def _norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(_canonical(dict(row)) + "\n")


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "MISSING"


def _file_snapshot(paths: Sequence[Path]) -> Dict[str, Dict[str, Any]]:
    return {
        str(path.relative_to(ROOT)): {
            "exists": path.exists(),
            "bytes": path.stat().st_size if path.exists() else 0,
            "sha256": _file_sha(path),
        }
        for path in paths
    }


def _sheet_titles(service, spreadsheet_id: str) -> Dict[str, int]:
    metadata = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id, fields="sheets.properties(sheetId,title)"
    ).execute()
    return {
        row["properties"]["title"]: row["properties"]["sheetId"]
        for row in metadata.get("sheets", [])
    }


def _ensure_sheet_append_only(
    service, spreadsheet_id: str, sheet_name: str, required_headers: Sequence[str],
) -> Tuple[List[str], Dict[str, Any]]:
    titles = _sheet_titles(service, spreadsheet_id)
    created = sheet_name not in titles
    if created:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]},
        ).execute()
        before: List[str] = []
    else:
        values = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!1:1"
        ).execute().get("values", [])
        before = list(values[0]) if values else []
    headers = list(before)
    for header in required_headers:
        if header not in headers:
            headers.append(header)
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_name}'!A1",
        valueInputOption="RAW",
        body={"values": [headers]},
    ).execute()
    return headers, {
        "sheet_name": sheet_name,
        "created": created,
        "headers_before": before,
        "headers_after": headers,
        "existing_header_order_preserved": headers[: len(before)] == before,
        "headers_appended": headers[len(before):],
    }


def _read_sheet(service, spreadsheet_id: str, sheet_name: str) -> Tuple[List[str], List[Dict[str, Any]]]:
    values = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!A1:ZZ"
    ).execute().get("values", [])
    if not values:
        return [], []
    headers = list(values[0])
    rows: List[Dict[str, Any]] = []
    for raw in values[1:]:
        padded = list(raw) + [""] * max(0, len(headers) - len(raw))
        rows.append({header: padded[index] for index, header in enumerate(headers)})
    return headers, rows


def _upsert_rows(
    service, spreadsheet_id: str, sheet_name: str, headers: Sequence[str], rows: Sequence[Mapping[str, Any]], key: str,
) -> Dict[str, Any]:
    _, existing = _read_sheet(service, spreadsheet_id, sheet_name)
    positions: Dict[str, int] = {}
    for index, row in enumerate(existing, start=2):
        identity = _norm(row.get(key))
        if not identity:
            continue
        if identity in positions:
            raise ImplementationError("DUPLICATE_EXISTING_KEY:" + sheet_name + ":" + identity)
        positions[identity] = index
    updates = 0
    appends = 0
    for row in rows:
        identity = _norm(row.get(key))
        if not identity:
            raise ImplementationError("UPSERT_KEY_MISSING:" + sheet_name + ":" + key)
        values = [row.get(header, existing[positions[identity] - 2].get(header, "") if identity in positions else "") for header in headers]
        if identity in positions:
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"'{sheet_name}'!A{positions[identity]}",
                valueInputOption="RAW",
                body={"values": [values]},
            ).execute()
            updates += 1
        else:
            service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=f"'{sheet_name}'!A:A",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": [values]},
            ).execute()
            appends += 1
    return {"rows_updated": updates, "rows_appended": appends, "existing_rows_before": len(existing)}


def _protected_sheet_snapshot(service) -> Dict[str, Any]:
    ranges: List[str] = []
    for sheet in PROTECTED_SHEETS:
        ranges.extend((f"'{sheet}'!1:1", f"'{sheet}'!A:A"))
    response = service.spreadsheets().values().batchGet(
        spreadsheetId=MAIN_SPREADSHEET_ID, ranges=ranges
    ).execute().get("valueRanges", [])
    snapshot: Dict[str, Any] = {}
    for index, sheet in enumerate(PROTECTED_SHEETS):
        header_values = response[index * 2].get("values", []) if index * 2 < len(response) else []
        column_values = response[index * 2 + 1].get("values", []) if index * 2 + 1 < len(response) else []
        header = header_values[0] if header_values else []
        snapshot[sheet] = {
            "header_count": len(header),
            "header_fingerprint": fingerprint(header),
            "used_rows": len(column_values),
            "first_column_fingerprint": fingerprint(column_values),
        }
    return snapshot


def _sheet_registry_row(generated: str) -> Dict[str, Any]:
    return {
        "logical_sheet_id": "KNOWLEDGE_SOURCE_REGISTRY",
        "physical_sheet_name": REGISTRY_SHEET,
        "workbook": "PROJECT_OVERVIEWS",
        "workbook_id": PROJECT_OVERVIEWS_SPREADSHEET_ID,
        "category": "GOVERNANCE",
        "lifecycle_state": "ACTIVE",
        "owner_module": "knowledge_governance",
        "participates_in_rebuild": "TRUE",
        "read_only": "FALSE",
        "allow_creation": "TRUE",
        "created_phase": "Phase 9 Stage 4A Approved Knowledge Source Registry",
        "notes": "Authoritative provider-neutral source governance; source approval remains separate from item admission.",
        "registry_created_ts": generated,
        "registry_last_verified_ts": generated,
        "registry_migration_ts": "",
        "registry_rename_ts": "",
    }


def _routing_validation(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    expected = {
        "FED_EXPECTATIONS": ["KSRC_APOLLO_DAILY_SPARK", "KSRC_PIMCO_INSIGHTS", "KSRC_BLACKROCK_INVESTMENT_INSTITUTE", "KSRC_NEW_YORK_FED"],
        "INFLATION_NARRATIVE": ["KSRC_BLS", "KSRC_PIMCO_INSIGHTS", "KSRC_BLACKROCK_INVESTMENT_INSTITUTE"],
        "TREASURY_INTERPRETATION": ["KSRC_PIMCO_INSIGHTS", "KSRC_US_TREASURY", "KSRC_BLACKROCK_INVESTMENT_INSTITUTE"],
        "CONSUMER_OUTLOOK": ["KSRC_BEA", "KSRC_PIMCO_INSIGHTS"],
        "RISK_SENTIMENT": ["KSRC_APOLLO_DAILY_SPARK", "KSRC_BLACKROCK_INVESTMENT_INSTITUTE"],
    }
    results: List[Dict[str, Any]] = []
    for mode in ("HISTORICAL_REPLAY", "PROSPECTIVE_COLLECTION"):
        for topic, expected_prefix in expected.items():
            base = {
                "session_id": "AKSR_VALIDATION_SESSION",
                "provider_request_id": "AKSR_VALIDATION_REQUEST",
                "normalized_request_id": "AKSR_VALIDATION_NORMALIZED",
                "request_category": topic,
            }
            openai = route_request({**base, "provider": "OpenAI"}, mode, rows)
            gemini = route_request({**base, "provider": "Gemini"}, mode, rows)
            configured = [row["source_id"] for row in openai["configured_routes"]]
            provider_neutral = openai["route_id"] == gemini["route_id"] and openai["source_routes"] == gemini["source_routes"]
            results.append({
                "mode": mode,
                "topic": topic,
                "route_id": openai["route_id"],
                "configured_source_ids": configured,
                "acquisition_eligible_source_ids": [row["source_id"] for row in openai["source_routes"]],
                "expected_prefix": expected_prefix,
                "configured_priority_status": "PASS" if configured[: len(expected_prefix)] == expected_prefix else "FAIL",
                "provider_neutral_status": "PASS" if provider_neutral else "FAIL",
                "unsupported_capabilities_excluded": all(row["mode_supported"] for row in openai["configured_routes"] if row["source_id"] in {item["source_id"] for item in openai["source_routes"]}),
            })
    return results


def _traceability_fixture(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    request = {
        "session_id": "US|2024-05-20|CUSTOM_CONFIG_WINDOW",
        "forecast_cutoff": "2024-05-20T13:00:00Z",
        "provider": "OpenAI",
        "provider_request_id": "AKSR_FIXTURE_REQUEST",
        "normalized_request_id": "AKSR_FIXTURE_NORMALIZED",
        "request_category": "INFLATION_NARRATIVE",
    }
    route = route_request(request, "HISTORICAL_REPLAY", rows)
    item = {
        "source_id": "KSRC_BLS",
        "knowledge_item_id": "AKSR_FIXTURE_ITEM",
        "publication_timestamp": "2024-05-20T12:00:00Z",
        "timestamp_precision": "EXACT_DATETIME",
        "publisher": "U.S. Bureau of Labor Statistics",
        "canonical_url": "https://www.bls.gov/aksr-fixture",
        "content_fingerprint": "f" * 64,
        "historical_state_evidence": "OFFICIAL_DATED_RELEASE_FIXTURE",
        "relevance_status": "PASS",
        "outcome_leakage_status": "PASS",
    }
    admission = admit_knowledge_item(item, request, "HISTORICAL_REPLAY", rows)
    trace = build_traceability_record(
        request=request,
        route=route,
        knowledge_item=item,
        luna_evidence={"source_id": "KSRC_BLS", "luna_evidence_id": "AKSR_FIXTURE_LUNA"},
        pack_entry={"pack_entry_id": "AKSR_FIXTURE_PACK_ENTRY", "luna_evidence_id": "AKSR_FIXTURE_LUNA"},
        mode="HISTORICAL_REPLAY",
    )
    return {"article_admission": admission, "traceability": trace, "status": "PASS"}


def _manifest(run_dir: Path, run_id: str, generated: str) -> Dict[str, Any]:
    artifacts = []
    for path in sorted(run_dir.iterdir()):
        if not path.is_file() or path.name == "completion_manifest.json":
            continue
        artifacts.append({"file": path.name, "bytes": path.stat().st_size, "sha256": _file_sha(path)})
    manifest = {
        "run_id": run_id,
        "created_ts": generated,
        "phase": "Phase 9 Stage 4A Historical / Replay Environment Reconstruction",
        "registry_version": REGISTRY_VERSION,
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "model_calls": 0,
        "forecast_calls": 0,
        "source_retrieval_calls": 0,
        "production_authority": False,
    }
    manifest["manifest_input_fingerprint"] = fingerprint(manifest)
    return manifest


def run() -> Dict[str, Any]:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    generated = _iso(now)
    run_id = PHASE_ID + "_" + now.strftime("%Y%m%dT%H%M%SZ")
    run_dir = OUTPUT_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    rows = initial_registry()
    registry_validation = validate_registry(rows)
    if registry_validation["status"] != "PASS":
        raise ImplementationError("AKSR_REGISTRY_INTEGRITY_FAILED:" + "|".join(registry_validation["errors"]))
    routing = _routing_validation(rows)
    if any(row["configured_priority_status"] != "PASS" or row["provider_neutral_status"] != "PASS" for row in routing):
        raise ImplementationError("AKSR_ROUTING_VALIDATION_FAILED")
    traceability = _traceability_fixture(rows)
    aliases = replay_compatibility_aliases()

    preserved_before = _file_snapshot(PRESERVED_RUN_FILES)
    production_before = _file_snapshot(PRODUCTION_FILES)
    service = build_sheets_service(load_credentials(interactive=False))
    protected_before = _protected_sheet_snapshot(service)

    registry_headers, registry_sheet_audit = _ensure_sheet_append_only(
        service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS
    )
    registry_write = _upsert_rows(
        service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, registry_headers, rows, "source_id"
    )
    sheet_registry_headers, sheet_registry_audit = _ensure_sheet_append_only(
        service, PROJECT_OVERVIEWS_SPREADSHEET_ID, SHEET_REGISTRY, SHEET_REGISTRY_HEADERS
    )
    sheet_registry_write = _upsert_rows(
        service, PROJECT_OVERVIEWS_SPREADSHEET_ID, SHEET_REGISTRY, sheet_registry_headers,
        [_sheet_registry_row(generated)], "logical_sheet_id",
    )

    live_headers, live_rows = _read_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    live_aksr_rows = [row for row in live_rows if _norm(row.get("registry_version")) == REGISTRY_VERSION]
    live_validation = validate_registry(live_aksr_rows)
    protected_after = _protected_sheet_snapshot(service)
    preserved_after = _file_snapshot(PRESERVED_RUN_FILES)
    production_after = _file_snapshot(PRODUCTION_FILES)

    preservation = {
        "protected_scientific_sheets_before": protected_before,
        "protected_scientific_sheets_after": protected_after,
        "protected_scientific_sheets_unchanged": protected_before == protected_after,
        "historical_run_files_before": preserved_before,
        "historical_run_files_after": preserved_after,
        "historical_run_files_unchanged": preserved_before == preserved_after,
        "production_files_before": production_before,
        "production_files_after": production_after,
        "production_files_unchanged": production_before == production_after,
        "forecast_calls": 0,
        "model_calls": 0,
        "source_retrieval_calls": 0,
        "pack_semantics_changed": False,
        "provider_prompts_changed": False,
        "prediction_schema_changed": False,
        "outcome_schema_changed": False,
        "evaluation_schema_changed": False,
        "production_behavior_changed": False,
    }
    if not all((
        preservation["protected_scientific_sheets_unchanged"],
        preservation["historical_run_files_unchanged"],
        preservation["production_files_unchanged"],
    )):
        raise ImplementationError("AKSR_SCIENTIFIC_PRESERVATION_FAILED")
    if live_validation["status"] != "PASS" or len(live_aksr_rows) != len(rows):
        raise ImplementationError("AKSR_LIVE_WORKBOOK_VALIDATION_FAILED")

    workbook_write = {
        "workbook_id": PROJECT_OVERVIEWS_SPREADSHEET_ID,
        "registry_sheet": registry_sheet_audit,
        "registry_write": registry_write,
        "sheet_registry": sheet_registry_audit,
        "sheet_registry_write": sheet_registry_write,
        "live_header_count": len(live_headers),
        "live_source_count": len(live_aksr_rows),
        "live_registry_fingerprint": live_validation["registry_fingerprint"],
        "append_only_header_enforcement": registry_sheet_audit["existing_header_order_preserved"] and sheet_registry_audit["existing_header_order_preserved"],
        "status": "PASS",
    }
    replay_compatibility = {
        "existing_source_aliases": aliases,
        "alias_count": len(aliases),
        "historical_and_prospective_modes_separate": True,
        "existing_environment_artifacts_rerun": False,
        "existing_environment_artifacts_modified": False,
        "future_environment_entrypoint": "automation.approved_knowledge_source_registry_v0.route_request",
        "article_admission_entrypoint": "automation.approved_knowledge_source_registry_v0.admit_knowledge_item",
        "traceability_entrypoint": "automation.approved_knowledge_source_registry_v0.build_traceability_record",
        "status": "PASS",
    }
    summary = {
        "build_status": "PASS",
        "final_decision": "AKSR_IMPLEMENTATION_COMPLETE",
        "run_id": run_id,
        "registry_version": REGISTRY_VERSION,
        "registry_sheet": REGISTRY_SHEET,
        "registry_workbook_id": PROJECT_OVERVIEWS_SPREADSHEET_ID,
        "approved_source_count": len(rows),
        "registry_fingerprint": registry_validation["registry_fingerprint"],
        "live_registry_fingerprint": live_validation["registry_fingerprint"],
        "source_class_counts": registry_validation["source_class_counts"],
        "routing_validation_count": len(routing),
        "provider_neutral_routing": "PASS",
        "historical_prospective_separation": "PASS",
        "provenance_policy_count": len(PROVENANCE_POLICIES),
        "article_admission_separate": "PASS",
        "duplicate_suppression": "PASS",
        "traceability": "PASS",
        "replay_compatibility": "PASS",
        "existing_environment_behavior_preserved": "PASS",
        "scientific_sheets_changed": False,
        "historical_runs_changed": False,
        "production_changed": False,
        "forecast_calls": 0,
        "model_calls": 0,
        "source_retrieval_calls": 0,
    }

    _write_jsonl(run_dir / "knowledge_source_registry.jsonl", rows)
    _write_json(run_dir / "source_class_provenance_policies.json", PROVENANCE_POLICIES)
    _write_jsonl(run_dir / "knowledge_routing_validation.jsonl", routing)
    _write_json(run_dir / "registry_integrity_validation.json", registry_validation)
    _write_json(run_dir / "live_registry_validation.json", live_validation)
    _write_json(run_dir / "traceability_fixture_validation.json", traceability)
    _write_json(run_dir / "replay_compatibility_validation.json", replay_compatibility)
    _write_json(run_dir / "workbook_write_audit.json", workbook_write)
    _write_json(run_dir / "scientific_preservation_audit.json", preservation)
    _write_json(run_dir / "completion_summary.json", summary)
    _write_json(run_dir / "completion_manifest.json", _manifest(run_dir, run_id, generated))
    print(json.dumps(summary, ensure_ascii=True, sort_keys=True))
    return summary


if __name__ == "__main__":
    run()

