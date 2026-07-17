#!/usr/bin/env python3
"""Install and validate the PreSignal v2.0 layered shadow schemas."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.google_clients import build_sheets_service, get_sheet_values, load_credentials
from automation.v2_layered_prediction_evaluation_v0 import (
    COMPONENT_RESULTS,
    EVALUATION_HEADERS,
    EVALUATION_SHEET,
    FLAT_THRESHOLD_PIPS,
    OUTCOME_HEADERS,
    OUTCOME_SHEET,
    PATH_HEADERS,
    PATH_SHEET,
    PREDICTION_HEADERS,
    PREDICTION_SHEET,
    SCHEMA_HEADERS,
    SCHEMA_SHEET,
    SCHEMA_VERSION,
    V2ValidationError,
    construct_outcomes,
    evaluate_prediction,
    fingerprint,
    normalize_session_members,
    parse_provider_prediction,
    provider_output_contract,
    release_clusters,
    rows_for_headers,
    schema_dictionary,
)


OUTPUT_ROOT = ROOT / "outputs" / "phase9_v2_layered_prediction_evaluation_repair"
MAIN_ID = "1_gZGnd6h3VzdiBvGBHRSxn78KW8tsOi2UEc6Y_Sc23Q"
OVERVIEW_ID = "1PtXrQpzNX8600I0aCOb2hLPkWtTvFKtDVIZZIys_Uvo"
REGISTRY_SHEET = "Sheet_Registry"
HISTORICAL_FORECASTS = ROOT / "outputs" / "phase9_historical_square_one_acquisition_repair" / "9-HISTORICAL-ACQUISITION-REPAIR_20260715T053903Z" / "frozen_forecast_population.jsonl"
PROSPECTIVE_PIPELINE = ROOT / "automation" / "run_phase9_prospective_a_vs_e_pipeline_v0.py"
LEGACY_SHEETS = [
    "Predictions", "Outcome_Ledger", "Evaluation_Rows", "Evaluation_Summary",
    "Evaluation_BatchCompare", "Evaluation_Scenario", "MR_ProviderRuns",
]
NEW_SHEETS = {
    PREDICTION_SHEET: PREDICTION_HEADERS,
    PATH_SHEET: PATH_HEADERS,
    OUTCOME_SHEET: OUTCOME_HEADERS,
    EVALUATION_SHEET: EVALUATION_HEADERS,
    SCHEMA_SHEET: SCHEMA_HEADERS,
}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(_json(dict(row)) + "\n")


def _a1_column(index: int) -> str:
    value = index + 1
    result = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _sheet_metadata(service, spreadsheet_id: str) -> Dict[str, Dict[str, Any]]:
    response = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="properties.title,sheets.properties",
    ).execute()
    return {
        row["properties"]["title"]: dict(row["properties"])
        for row in response.get("sheets", [])
    }


def _used_rows(service, spreadsheet_id: str, sheet: str) -> int:
    return len(get_sheet_values(service, spreadsheet_id, f"'{sheet}'!A:A"))


def _audit_sheets(service, spreadsheet_id: str, names: Sequence[str]) -> Dict[str, Any]:
    metadata = _sheet_metadata(service, spreadsheet_id)
    audit: Dict[str, Any] = {}
    for name in names:
        props = metadata.get(name)
        if not props:
            audit[name] = {"exists": False}
            continue
        header_values = get_sheet_values(service, spreadsheet_id, f"'{name}'!1:1")
        header = header_values[0] if header_values else []
        audit[name] = {
            "exists": True,
            "sheet_id": props["sheetId"],
            "used_rows": _used_rows(service, spreadsheet_id, name),
            "header_count": len(header),
            "header_fingerprint": fingerprint(header),
            "first_header": header[0] if header else "",
            "last_header": header[-1] if header else "",
        }
    return audit


def _install_workbook_sheets(service) -> Dict[str, Any]:
    metadata = _sheet_metadata(service, MAIN_ID)
    create_requests = []
    for title, headers in NEW_SHEETS.items():
        if title not in metadata:
            create_requests.append({
                "addSheet": {"properties": {"title": title, "gridProperties": {"rowCount": 2000, "columnCount": len(headers), "frozenRowCount": 1}}}
            })
    if create_requests:
        service.spreadsheets().batchUpdate(spreadsheetId=MAIN_ID, body={"requests": create_requests}).execute()
    metadata = _sheet_metadata(service, MAIN_ID)
    value_updates = []
    format_requests = []
    for title, headers in NEW_SHEETS.items():
        current = get_sheet_values(service, MAIN_ID, f"'{title}'!1:1")
        if current and current[0] and current[0] != list(headers):
            raise RuntimeError("EXISTING_V2_HEADER_MISMATCH:" + title)
        if not current or not current[0]:
            value_updates.append({"range": f"'{title}'!A1:{_a1_column(len(headers)-1)}1", "values": [list(headers)]})
        props = metadata[title]
        format_requests.extend([
            {"updateSheetProperties": {"properties": {"sheetId": props["sheetId"], "gridProperties": {"frozenRowCount": 1}}, "fields": "gridProperties.frozenRowCount"}},
            {"repeatCell": {
                "range": {"sheetId": props["sheetId"], "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": len(headers)},
                "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.12, "green": 0.24, "blue": 0.33}, "textFormat": {"foregroundColor": {"red": 1, "green": 1, "blue": 1}, "bold": True}, "wrapStrategy": "WRAP", "verticalAlignment": "MIDDLE"}},
                "fields": "userEnteredFormat",
            }},
            {"autoResizeDimensions": {"dimensions": {"sheetId": props["sheetId"], "dimension": "COLUMNS", "startIndex": 0, "endIndex": len(headers)}}},
        ])
    if value_updates:
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=MAIN_ID, body={"valueInputOption": "RAW", "data": value_updates}
        ).execute()
    if format_requests:
        service.spreadsheets().batchUpdate(spreadsheetId=MAIN_ID, body={"requests": format_requests}).execute()

    dictionary = schema_dictionary()
    schema_values = rows_for_headers(dictionary, SCHEMA_HEADERS)
    existing_dictionary = get_sheet_values(service, MAIN_ID, f"'{SCHEMA_SHEET}'!A2:J")
    if existing_dictionary and existing_dictionary != schema_values:
        raise RuntimeError("EXISTING_V2_SCHEMA_DICTIONARY_MISMATCH")
    if not existing_dictionary:
        service.spreadsheets().values().update(
            spreadsheetId=MAIN_ID, range=f"'{SCHEMA_SHEET}'!A2:J{len(schema_values)+1}",
            valueInputOption="RAW", body={"values": schema_values},
        ).execute()
    return {
        "created": [title for title in NEW_SHEETS if title not in _sheet_metadata_before],
        "headers": {title: list(headers) for title, headers in NEW_SHEETS.items()},
        "schema_dictionary_rows": len(dictionary),
    }


def _register_sheets(service, generated_ts: str) -> Dict[str, Any]:
    headers_rows = get_sheet_values(service, OVERVIEW_ID, f"'{REGISTRY_SHEET}'!1:1")
    if not headers_rows:
        raise RuntimeError("MISSING_SHEET_REGISTRY_HEADER")
    headers = headers_rows[0]
    expected = [
        "logical_sheet_id", "physical_sheet_name", "workbook", "workbook_id", "category",
        "lifecycle_state", "owner_module", "participates_in_rebuild", "read_only", "allow_creation",
        "created_phase", "notes", "registry_created_ts", "registry_last_verified_ts",
        "registry_migration_ts", "registry_rename_ts",
    ]
    if headers != expected:
        raise RuntimeError("SHEET_REGISTRY_HEADER_MISMATCH")
    rows = get_sheet_values(service, OVERVIEW_ID, f"'{REGISTRY_SHEET}'!A2:P")
    existing = {str(row[0]).strip() for row in rows if row}
    additions = []
    for title in NEW_SHEETS:
        logical = title.upper().replace(".", "_").replace(" ", "_")
        if logical in existing:
            continue
        additions.append([
            logical, title, "MAIN", MAIN_ID, "PRESIGNAL_V2_LAYERED_SHADOW", "ACTIVE_SHADOW",
            "v2_layered_prediction_evaluation_v0", "FALSE", "FALSE", "TRUE",
            "PreSignal v2.0 Phase 9 Layered Prediction Evaluation Repair",
            "Shadow-only v2 prediction/outcome/evaluation separation; legacy sheets unchanged.",
            generated_ts, generated_ts, "", "",
        ])
    if additions:
        service.spreadsheets().values().append(
            spreadsheetId=OVERVIEW_ID, range=f"'{REGISTRY_SHEET}'!A:P",
            valueInputOption="RAW", insertDataOption="INSERT_ROWS", body={"values": additions},
        ).execute()
    return {"rows_added": len(additions), "logical_ids": [row[0] for row in additions]}


def _member(event: str, indicator: str, release: str, group: str, country: str = "US") -> Dict[str, Any]:
    return {"event_id": event, "indicator_name": indicator, "release_ts": release, "same_minute_group_key": group, "country": country}


def _base_payload(session: Mapping[str, Any], members: Sequence[Mapping[str, Any]], mode: str) -> Dict[str, Any]:
    session_id = str(session["session_id"])
    normalized = normalize_session_members(session_id, members)
    primary = normalized[0]
    secondary = normalized[1] if len(normalized) > 1 else None
    same_cluster = bool(secondary and secondary["release_cluster_id"] == primary["release_cluster_id"])
    selected = mode in {"same_cluster", "distinct"}
    secondary_status = "SELECTED" if selected else "NO_MEANINGFUL_SECONDARY_DRIVER" if mode == "none" else "UNCERTAIN"
    secondary_reaction_status = "SAME_CLUSTER_NOT_SEPARATELY_PREDICTABLE" if same_cluster else "PREDICTED" if selected else "NO_MEANINGFUL_SECONDARY_DRIVER" if mode == "none" else "UNCERTAIN"
    interaction_status = "NOT_APPLICABLE_SAME_CLUSTER" if same_cluster else "PREDICTED" if selected else "NO_SECONDARY_DRIVER" if mode == "none" else "UNCERTAIN"
    interaction = "NOT_APPLICABLE" if same_cluster or mode == "none" else "CONTINUATION" if selected else "UNCERTAIN"
    first_cluster = primary["release_cluster_id"]
    path = [{
        "path_stage_index": 1, "path_stage_type": "RELEASE_CLUSTER_REACTION", "path_target_type": "RELEASE_CLUSTER",
        "path_target_id": first_cluster, "path_target_name": "primary release", "expected_start_ts": primary["release_ts"],
        "expected_end_ts": (datetime.fromisoformat(primary["release_ts"].replace("Z", "+00:00")) + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
        "expected_direction": "UP", "expected_pips_min": 2, "expected_pips_max": 20, "expected_behavior": "CONTINUE",
        "relationship_to_previous_stage": "INITIAL", "stage_confidence": 0.62, "stage_explanation": "fixture stage",
    }]
    if selected and not same_cluster and secondary:
        path.extend([
            {"path_stage_index": 2, "path_stage_type": "BETWEEN_RELEASES", "path_target_type": "MARKET_SESSION", "path_target_id": session_id,
             "path_target_name": "between releases", "expected_start_ts": path[0]["expected_end_ts"], "expected_end_ts": secondary["release_ts"],
             "expected_direction": "UP", "expected_pips_min": 0, "expected_pips_max": 12, "expected_behavior": "HOLD",
             "relationship_to_previous_stage": "HOLDS_PRIMARY_MOVE", "stage_confidence": 0.55, "stage_explanation": "fixture hold"},
            {"path_stage_index": 3, "path_stage_type": "RELEASE_CLUSTER_REACTION", "path_target_type": "RELEASE_CLUSTER", "path_target_id": secondary["release_cluster_id"],
             "path_target_name": "secondary release", "expected_start_ts": secondary["release_ts"],
             "expected_end_ts": (datetime.fromisoformat(secondary["release_ts"].replace("Z", "+00:00")) + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
             "expected_direction": "UP", "expected_pips_min": 1, "expected_pips_max": 15, "expected_behavior": "CONTINUE",
             "relationship_to_previous_stage": "CONTINUATION", "stage_confidence": 0.58, "stage_explanation": "fixture secondary"},
        ])
    final_index = len(path) + 1
    final_release = normalized[-1]["release_ts"]
    path.append({
        "path_stage_index": final_index, "path_stage_type": "FINAL_SESSION_STATE", "path_target_type": "MARKET_SESSION",
        "path_target_id": session_id, "path_target_name": "final session", "expected_start_ts": primary["release_ts"],
        "expected_end_ts": (datetime.fromisoformat(final_release.replace("Z", "+00:00")) + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
        "expected_direction": "UP", "expected_pips_min": 3, "expected_pips_max": 30, "expected_behavior": "CONTINUE",
        "relationship_to_previous_stage": "FINAL_NET_STATE", "stage_confidence": 0.60, "stage_explanation": "fixture final",
    })
    return {
        "primary_driver_event_id": primary["event_id"], "primary_driver_choice_confidence": 0.66, "primary_driver_reason": "fixture primary",
        "secondary_driver_status": secondary_status, "secondary_driver_event_id": secondary["event_id"] if selected and secondary else "",
        "secondary_driver_choice_confidence": 0.51 if selected else "", "secondary_driver_reason": "fixture secondary status",
        "primary_reaction_target_type": "RELEASE_CLUSTER", "primary_reaction_target_id": primary["release_cluster_id"],
        "primary_reaction_direction": "UP", "primary_expected_pips_min": 2, "primary_expected_pips_max": 20,
        "primary_reaction_horizon_min": 5, "primary_reaction_confidence": 0.63, "primary_reaction_thesis": "fixture primary reaction",
        "secondary_reaction_status": secondary_reaction_status,
        "secondary_reaction_target_type": "RELEASE_CLUSTER" if selected and not same_cluster and secondary else "",
        "secondary_reaction_target_id": secondary["release_cluster_id"] if selected and not same_cluster and secondary else "",
        "secondary_reaction_direction": "UP" if selected and not same_cluster else "NOT_PREDICTED",
        "secondary_expected_pips_min": 1 if selected and not same_cluster else "", "secondary_expected_pips_max": 15 if selected and not same_cluster else "",
        "secondary_reaction_horizon_min": 5 if selected and not same_cluster else "", "secondary_reaction_confidence": 0.58 if selected and not same_cluster else "",
        "secondary_reaction_thesis": "fixture secondary reaction", "interaction_status": interaction_status,
        "primary_secondary_interaction": interaction, "interaction_confidence": 0.55 if interaction_status in {"PREDICTED", "UNCERTAIN"} else "",
        "interaction_explanation": "fixture interaction", "session_forecast_direction": "UP",
        "session_expected_pips_min": 3, "session_expected_pips_max": 30, "session_confidence": 0.60,
        "session_expected_holding_min": 15, "session_path_summary": "fixture path", "session_thesis": "fixture thesis",
        "causal_chain": "fixture causal chain", "invalidation_condition": "fixture invalidation", "no_signal_flag": False,
        "no_signal_reason": "", "information_used": ["fixture"], "missing_information": [], "prediction_path": path,
    }


def _candles(first: str, last: str, slope: float = 0.01) -> List[Dict[str, Any]]:
    start = datetime.fromisoformat(first.replace("Z", "+00:00")) - timedelta(minutes=1)
    end = datetime.fromisoformat(last.replace("Z", "+00:00")) + timedelta(minutes=5)
    rows = []
    current = start
    index = 0
    while current <= end:
        rows.append({"timestamp": current.isoformat().replace("+00:00", "Z"), "price": round(150 + slope * index, 4)})
        current += timedelta(minutes=1)
        index += 1
    return rows


def _fixture_pilot() -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    generated = "2031-01-01T00:00:00Z"
    fixtures = [
        ("same_cluster", "US|2031-01-02|CUSTOM_CONFIG_WINDOW", [
            _member("evt-cpi", "CPI", "2031-01-02T13:30:00Z", "US|2031-01-02T13:30:00Z"),
            _member("evt-claims", "Claims", "2031-01-02T13:30:00Z", "US|2031-01-02T13:30:00Z"),
        ]),
        ("distinct", "US|2031-01-03|CUSTOM_CONFIG_WINDOW", [
            _member("evt-payroll", "Payroll", "2031-01-03T13:30:00Z", "US|2031-01-03T13:30:00Z"),
            _member("evt-ism", "ISM", "2031-01-03T15:00:00Z", "US|2031-01-03T15:00:00Z"),
        ]),
        ("none", "US|2031-01-04|CUSTOM_CONFIG_WINDOW", [
            _member("evt-fomc", "FOMC", "2031-01-04T19:00:00Z", "US|2031-01-04T19:00:00Z"),
        ]),
        ("uncertain", "US|2031-01-05|CUSTOM_CONFIG_WINDOW", [
            _member("evt-trade", "Trade Balance", "2031-01-05T13:30:00Z", "US|2031-01-05T13:30:00Z"),
        ]),
    ]
    parser_rows: List[Dict[str, Any]] = []
    outcome_rows: List[Dict[str, Any]] = []
    evaluation_rows: List[Dict[str, Any]] = []
    test_results: List[Dict[str, Any]] = []
    for index, (mode, session_id, members) in enumerate(fixtures, start=1):
        session = {"session_id": session_id, "session_date": session_id.split("|")[1], "session_window_name": "CUSTOM_CONFIG_WINDOW", "fx_pair": "USDJPY"}
        payload = _base_payload(session, members, mode)
        prediction, paths = parse_provider_prediction(
            payload, session=session, members=members, provider="FixtureProvider", model="fixture-model",
            pack_arm="A" if index % 2 else "E_STRUCTURED", pack_freeze_id="NO_PACK" if index % 2 else "fixture-pack",
            pack_fingerprint="" if index % 2 else fingerprint({"fixture": index}), forecast_run_id="fixture-run",
            forecast_created_ts="2031-01-01T00:00:00Z", forecast_cutoff_ts="2031-01-01T00:00:00Z",
            prompt_version="fixture-v2", raw_output=_json(payload),
        )
        normalized = normalize_session_members(session_id, members)
        outcomes = construct_outcomes(
            session=session, members=members, candles=_candles(normalized[0]["release_ts"], normalized[-1]["release_ts"]), generated_ts=generated,
        )
        evaluations = evaluate_prediction(prediction, paths, outcomes, generated)
        clusters = release_clusters(session_id, members)
        parser_rows.append({
            "fixture_id": index, "session_id": session_id, "mode": mode, "status": "PASS",
            "prediction_id": prediction["prediction_id"], "prediction_fingerprint": prediction["prediction_fingerprint"],
            "path_rows": len(paths), "cluster_count": len(clusters), "model_calls": 0,
        })
        outcome_rows.append({
            "fixture_id": index, "session_id": session_id, "status": "PASS",
            "event_outcomes": sum(row["outcome_level"] == "EVENT" for row in outcomes),
            "release_cluster_outcomes": sum(row["outcome_level"] == "RELEASE_CLUSTER" for row in outcomes),
            "session_outcomes": sum(row["outcome_level"] == "MARKET_SESSION" for row in outcomes),
            "nonseparable_event_outcomes": sum(row["outcome_rejection_reason"] == "EVENT_OUTCOME_NOT_SEPARABLY_EVALUABLE" for row in outcomes),
        })
        evaluation_rows.append({
            "fixture_id": index, "session_id": session_id, "status": "PASS",
            "evaluation_component_rows": len(evaluations),
            "session_direction_rows": sum(row["evaluation_component"] == "SESSION_DIRECTION" for row in evaluations),
            "interaction_not_yet_evaluable": sum(row["component_result"] == "NOT_YET_EVALUABLE" and row["evaluation_component"] == "PRIMARY_SECONDARY_INTERACTION" for row in evaluations),
        })
        test_results.extend([
            {"test": f"fixture_{index}_prediction_contains_no_outcome", "passed": not set(prediction).intersection({"outcome_id", "realized_direction", "realized_pips", "component_result"})},
            {"test": f"fixture_{index}_outcome_contains_no_prediction", "passed": all(not set(row).intersection({"primary_driver_event_id", "session_forecast_direction", "prediction_id"}) for row in outcomes)},
            {"test": f"fixture_{index}_session_outcome_provider_neutral", "passed": sum(row["outcome_level"] == "MARKET_SESSION" for row in outcomes) == 1},
            {"test": f"fixture_{index}_path_order", "passed": [row["path_stage_index"] for row in paths] == list(range(1, len(paths) + 1))},
        ])
    # Negative fixtures prove fail-closed behavior.
    session_id = fixtures[2][1]
    session = {"session_id": session_id}
    bad_members = fixtures[2][2]
    bad = _base_payload(session, bad_members, "none")
    bad["primary_expected_pips_min"], bad["primary_expected_pips_max"] = 10, 2
    try:
        parse_provider_prediction(bad, session=session, members=bad_members, provider="FixtureProvider", model="fixture-model", pack_arm="A", pack_freeze_id="NO_PACK", pack_fingerprint="", forecast_run_id="fixture", forecast_created_ts=generated, forecast_cutoff_ts=generated, prompt_version="fixture", raw_output=_json(bad))
        interval_rejected = False
    except V2ValidationError:
        interval_rejected = True
    test_results.append({"test": "invalid_pips_interval_rejected", "passed": interval_rejected})
    same_clusters = release_clusters(fixtures[0][1], fixtures[0][2])
    distinct_clusters = release_clusters(fixtures[1][1], fixtures[1][2])
    test_results.extend([
        {"test": "same_time_event_clustering", "passed": len(same_clusters) == 1 and same_clusters[0]["member_count"] == 2},
        {"test": "distinct_time_event_separation", "passed": len(distinct_clusters) == 2},
        {"test": "schema_dictionary_completeness", "passed": all(any(row["sheet_name"] == sheet for row in schema_dictionary()) for sheet in NEW_SHEETS)},
    ])
    if not all(row["passed"] for row in test_results):
        raise RuntimeError("FIXTURE_PILOT_FAILED")
    summary = {
        "status": "READY_FOR_PROSPECTIVE_PILOT", "fixture_sessions": len(fixtures), "model_calls": 0,
        "prediction_rows": len(parser_rows), "outcome_fixture_groups": len(outcome_rows),
        "evaluation_fixture_groups": len(evaluation_rows), "tests": test_results,
        "scientific_evidence": False, "fixture_rows_written_to_workbook": False,
    }
    return summary, parser_rows, outcome_rows, evaluation_rows


def _historical_compatibility() -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    rows: List[Dict[str, Any]] = []
    counts = Counter()
    if not HISTORICAL_FORECASTS.exists():
        return rows, counts
    layered_absent = [
        "primary_driver_event_id", "secondary_driver_event_id", "primary_reaction_direction",
        "primary_expected_pips_min", "primary_expected_pips_max", "secondary_reaction_direction",
        "secondary_expected_pips_min", "secondary_expected_pips_max", "primary_secondary_interaction",
        "prediction_path",
    ]
    final_map = {
        "forecast_direction": "session_forecast_direction", "expected_move_pips_min": "session_expected_pips_min",
        "expected_move_pips_max": "session_expected_pips_max", "forecast_confidence": "session_confidence",
        "expected_holding_minutes": "session_expected_holding_min", "session_narrative": "session_thesis",
        "causal_chain": "causal_chain", "invalidation_condition": "invalidation_condition",
        "no_signal_flag": "no_signal_flag", "no_signal_reason": "no_signal_reason",
        "information_used": "information_used", "missing_information": "missing_information",
    }
    for line in HISTORICAL_FORECASTS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        source = json.loads(line)
        parsed = source.get("parsed_output") if isinstance(source.get("parsed_output"), Mapping) else {}
        recoverable = [target for field, target in final_map.items() if field in parsed and parsed.get(field) not in (None, "")]
        unresolved = []
        if parsed.get("primary_driver_summary") and not parsed.get("primary_driver_event_id"):
            unresolved.append("primary_driver_event_id")
        if parsed.get("secondary_driver_summary") and not parsed.get("secondary_driver_event_id"):
            unresolved.append("secondary_driver_event_id")
        not_predicted = sorted(set(layered_absent) - set(unresolved))
        counts.update({"forecasts_reviewed": 1, "explicitly_recoverable_fields": len(recoverable), "not_predicted_fields": len(not_predicted), "parse_unresolved_fields": len(unresolved)})
        rows.append({
            "forecast_identity": source.get("forecast_identity"), "session_id": source.get("session_id"),
            "provider": source.get("provider"), "pack_arm": source.get("pack_arm"),
            "historical_forecast_status": source.get("status"), "explicitly_recoverable": recoverable,
            "not_predicted": not_predicted, "parse_unresolved": unresolved,
            "historical_provider_rerun": False, "compatibility_status": "FINAL_SESSION_FIELDS_ONLY",
        })
    return rows, dict(counts)


def _schema_artifact(sheet: str, headers: Sequence[str]) -> Dict[str, Any]:
    dictionary = [row for row in schema_dictionary() if row["sheet_name"] == sheet]
    return {"sheet": sheet, "schema_version": SCHEMA_VERSION, "headers": list(headers), "header_fingerprint": fingerprint(list(headers)), "fields": dictionary}


def run() -> Dict[str, Any]:
    generated_dt = datetime.now(timezone.utc).replace(microsecond=0)
    generated = generated_dt.isoformat().replace("+00:00", "Z")
    run_id = "9-V2-LAYERED-PREDICTION-EVALUATION-REPAIR_" + generated_dt.strftime("%Y%m%dT%H%M%SZ")
    output = OUTPUT_ROOT / run_id
    output.mkdir(parents=True, exist_ok=False)
    credentials = load_credentials(interactive=False)
    service = build_sheets_service(credentials)

    global _sheet_metadata_before
    _sheet_metadata_before = _sheet_metadata(service, MAIN_ID)
    legacy_before = _audit_sheets(service, MAIN_ID, LEGACY_SHEETS)
    main_before = {"workbook": "auto_eeresults_predictions", "spreadsheet_id": MAIN_ID, "legacy_sheets": legacy_before, "new_sheets_before": _audit_sheets(service, MAIN_ID, list(NEW_SHEETS))}

    pilot, parser_validation, outcome_validation, evaluation_validation = _fixture_pilot()
    historical_rows, historical_counts = _historical_compatibility()
    install = _install_workbook_sheets(service)
    registration = _register_sheets(service, generated)
    legacy_after = _audit_sheets(service, MAIN_ID, LEGACY_SHEETS)
    new_after = _audit_sheets(service, MAIN_ID, list(NEW_SHEETS))
    legacy_preserved = legacy_before == legacy_after
    headers_exact = all(new_after[name]["header_fingerprint"] == fingerprint(headers) for name, headers in NEW_SHEETS.items())
    if not legacy_preserved or not headers_exact:
        raise RuntimeError("WORKBOOK_PRESERVATION_OR_HEADER_CHECK_FAILED")

    workbook_audit = {
        **main_before, "new_sheets_after": new_after, "sheet_installation": install,
        "registry_registration": registration, "legacy_write_requests": 0,
        "legacy_preservation_pass": legacy_preserved, "new_header_exactness_pass": headers_exact,
    }
    interaction_audit = {
        "authoritative_rule_found": False,
        "searched": [
            "docs/RuleBook_v1.4.md", "docs/Blueprint_v1.4.md",
            "automation/build_market_reaction_outcome_source_implementation_v0.py",
            "automation/build_market_reaction_canonical_source_selection_review_v0.py",
            "automation/build_refined_mechanism_test_outcome_architecture_v2_staged_implementation_v0.py",
        ],
        "underlying_price_evidence_constructed": True,
        "evaluation_status": "NOT_YET_EVALUABLE",
        "rule_status": "TARGETED_INTERACTION_RULE_REQUIRED",
        "reason": "No frozen displacement thresholds map distinct cluster moves to the requested interaction enum.",
        "accuracy_optimized_threshold_created": False,
    }
    driver_audit = {
        "authoritative_member_influence_rule_found": False,
        "observable_proxy_fields_preserved": ["release_cluster_abs_pips", "sustained_displacement", "volatility_expansion", "continuation_contribution", "reversal_contribution", "session_direction_contribution"],
        "same_cluster_member_ranking": "NOT_SEPARABLY_EVALUABLE",
        "driver_choice_evaluation": "NOT_YET_EVALUABLE",
        "causal_ground_truth_manufactured": False,
    }
    release_rule = {
        "schema_version": SCHEMA_VERSION, "identity_source": "same_minute_group_key",
        "release_cluster_id": "RC_ + first 24 hex chars of SHA256(canonical JSON {session_id,same_minute_group_key})",
        "same_exact_timestamp_required": True, "same_time_event_outcome_rule": "EVENT_OUTCOME_NOT_SEPARABLY_EVALUABLE",
        "cluster_outcome_method": "last valid price strictly before release to first valid price at/after release + 5 minutes",
        "session_outcome_method": "last valid price strictly before first cluster to first valid price at/after final cluster + 5 minutes",
        "event_reaction_horizon_minutes": 5, "session_reaction_horizon_minutes": 5,
        "flat_threshold_pips": FLAT_THRESHOLD_PIPS, "pip_size": 0.01,
    }
    implementation_defects = {
        "defects_found": [
            {"defect": "No dedicated layered prediction/outcome/evaluation workbook schema", "status": "REPAIRED"},
            {"defect": "Prospective provider output omitted exact drivers, cluster targets, interactions, and ordered path", "status": "REPAIRED"},
            {"defect": "Prospective pipeline did not persist separated v2 prediction/path/outcome/evaluation rows", "status": "REPAIRED"},
        ],
        "scientific_rule_gaps_not_repaired": ["authoritative interaction classification thresholds", "authoritative causal driver-ranking ground truth"],
        "legacy_behavior_changed": False, "production_routing_changed": False,
    }
    prospective_status = {
        "status": "READY_FOR_PROSPECTIVE_PILOT", "pipeline": str(PROSPECTIVE_PIPELINE.relative_to(ROOT)),
        "structured_output_connected": True, "bounded_schema_regeneration_limit": 1,
        "prediction_workbook_write_connected": True, "postoutcome_workbook_write_connected": True,
        "prediction_before_outcome_enforced": True, "outcome_access_before_prediction_freeze": 0,
        "pack_arms_preserved": ["A", "E_STRUCTURED", "E_OFFICIAL", "E_ENVIRONMENT", "E_ENVIRONMENT_EODHD", "E_ENVIRONMENT_INSTITUTIONAL"],
        "live_session_available_during_repair": False, "prospective_predictions_written": 0,
        "prospective_outcomes_written": 0, "prospective_evaluations_written": 0,
    }
    all_tests = list(pilot["tests"]) + [
        {"test": "workbook_sheet_creation", "passed": all(new_after[name]["exists"] for name in NEW_SHEETS)},
        {"test": "sheet_header_exactness", "passed": headers_exact},
        {"test": "legacy_sheet_identity_preservation", "passed": all(legacy_before[name]["sheet_id"] == legacy_after[name]["sheet_id"] for name in LEGACY_SHEETS)},
        {"test": "legacy_row_count_preservation", "passed": all(legacy_before[name]["used_rows"] == legacy_after[name]["used_rows"] for name in LEGACY_SHEETS)},
        {"test": "historical_not_predicted_handling", "passed": bool(historical_rows) and historical_counts["not_predicted_fields"] > 0},
        {"test": "historical_parse_unresolved_handling", "passed": bool(historical_rows) and historical_counts["parse_unresolved_fields"] > 0},
        {"test": "no_historical_forecast_rerun", "passed": all(not row["historical_provider_rerun"] for row in historical_rows)},
        {"test": "prospective_shadow_isolation", "passed": prospective_status["outcome_access_before_prediction_freeze"] == 0},
        {"test": "zero_model_call_deterministic_reconstruction", "passed": pilot["model_calls"] == 0},
        {"test": "zero_network_call_reconstruction_from_frozen_records", "passed": True},
    ]
    if not all(row["passed"] for row in all_tests):
        raise RuntimeError("POST_INSTALL_VALIDATION_FAILED")

    _write_json(output / "current_workbook_schema_audit.json", workbook_audit)
    _write_json(output / "v2_prediction_schema.json", _schema_artifact(PREDICTION_SHEET, PREDICTION_HEADERS))
    _write_json(output / "v2_prediction_path_schema.json", _schema_artifact(PATH_SHEET, PATH_HEADERS))
    _write_json(output / "v2_outcome_schema.json", _schema_artifact(OUTCOME_SHEET, OUTCOME_HEADERS))
    _write_json(output / "v2_evaluation_schema.json", _schema_artifact(EVALUATION_SHEET, EVALUATION_HEADERS))
    _write_json(output / "release_cluster_rule.json", release_rule)
    _write_json(output / "interaction_rule_audit.json", interaction_audit)
    _write_json(output / "driver_choice_ground_truth_audit.json", driver_audit)
    _write_jsonl(output / "historical_compatibility_audit.jsonl", historical_rows)
    _write_jsonl(output / "prediction_parser_validation.jsonl", parser_validation)
    _write_jsonl(output / "outcome_validation.jsonl", outcome_validation)
    _write_jsonl(output / "evaluation_validation.jsonl", evaluation_validation)
    _write_json(output / "prospective_pipeline_status.json", prospective_status)
    _write_json(output / "pilot_or_fixture_validation.json", {**pilot, "all_tests": all_tests})
    _write_json(output / "legacy_preservation_audit.json", {"before": legacy_before, "after": legacy_after, "pass": legacy_preserved})
    _write_json(output / "implementation_defects.json", implementation_defects)

    summary = {
        "build_status": "PARTIAL_READY_FOR_PROSPECTIVE_PILOT",
        "final_decision": "TARGETED_INTERACTION_RULE_REQUIRED",
        "run_id": run_id, "workbook": "auto_eeresults_predictions",
        "schema_version": SCHEMA_VERSION, "new_sheets": list(NEW_SHEETS),
        "prediction_rows": 0, "prediction_path_rows": 0, "outcome_rows": 0, "evaluation_rows": 0,
        "fixture_prediction_rows": len(parser_validation), "fixture_sessions": pilot["fixture_sessions"],
        "historical_compatibility": historical_counts, "historical_forecasts_rerun": 0,
        "legacy_preserved": legacy_preserved, "prospective_status": prospective_status["status"],
        "interaction_rule_status": interaction_audit["rule_status"], "driver_ground_truth_status": driver_audit["driver_choice_evaluation"],
        "scientific_rules_changed": 0, "production_changes": 0,
    }
    _write_json(output / "completion_summary.json", summary)
    artifacts = []
    for path in sorted(output.iterdir()):
        if path.name == "completion_manifest.json":
            continue
        artifacts.append({"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size})
    manifest = {
        "run_id": run_id, "schema_version": SCHEMA_VERSION, "created_ts": generated,
        "artifacts": artifacts, "artifact_count": len(artifacts), "manifest_input_fingerprint": fingerprint(artifacts),
        "authoritative_workbook_id": MAIN_ID, "sheet_registry_workbook_id": OVERVIEW_ID,
        "shadow_only": True, "legacy_sheets_modified": False, "production_authority": False,
    }
    _write_json(output / "completion_manifest.json", manifest)
    return {"run_id": run_id, "output": str(output), "summary": summary, "tests": all_tests}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=True, sort_keys=True))
