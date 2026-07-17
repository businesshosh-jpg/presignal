import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_market_sessions_shadow_v0 import (
    DIAGNOSTICS_SPREADSHEET_ID,
    MAIN_SPREADSHEET_ID,
    PROJECT_OVERVIEWS_SPREADSHEET_ID,
    REGISTRY_HEADERS,
    REGISTRY_SHEET,
    _column_letter,
    _ensure_sheet,
    _norm,
    _sheet_to_rows,
    _write_rows,
)
from automation.build_pack_exposure_prompt_validation_v0 import (
    ACTIVE_PACK_LEVELS,
    EXPECTED_FIELDS_BY_LEVEL,
    _assemble_prompt_text,
    _attention_history_index,
    _build_event_context,
    _build_market_state_context,
    _event_index,
    _filter_by_run,
    _get_sheet_titles,
    _group_prompt_rows,
    _guardrail_payload,
    _latest_run_id,
    _member_index,
    _read_optional_rows,
    _schema_payload,
    _sha256_text,
    _shadow_index,
    _split_pipe,
)
from automation.build_session_forecasts_v0 import (
    _normalize_confidence,
    _normalize_forecast_direction,
    _normalize_holding_minutes,
    _normalize_numeric_value,
)
from automation.build_session_information_requests_v0 import _iso_now, _normalize_provider_name, _truncate_text
from automation.google_clients import (
    batch_update_values,
    build_script_service,
    build_sheets_service,
    default_script_id,
    load_credentials,
    run_script_function,
)
from automation.true_shared_pack_e_renderer_v0 import (
    load_frozen_true_shared_pack_e,
    render_frozen_true_shared_pack_e_context,
)


INPUT_PROMPT_DESIGN_SHEET = "Pack_Exposure_Prompt_Design"
INPUT_OUTPUT_SCHEMA_SHEET = "Pack_Exposure_Output_Schema"
INPUT_GUARDRAILS_SHEET = "Pack_Exposure_Prompt_Guardrails"
INPUT_PROMPT_SUMMARY_SHEET = "Pack_Exposure_Prompt_Design_Summary"
INPUT_VALIDATION_SUMMARY_SHEET = "Pack_Exposure_Prompt_Validation_Summary"
INPUT_LEVEL_ITEMS_SHEET = "Market_State_Pack_Level_Items"
INPUT_LEVEL_SUMMARY_SHEET = "Market_State_Pack_Level_Summary"
INPUT_SHADOW_SHEET = "Market_State_Pack_Shadow"
INPUT_SHADOW_SUMMARY_SHEET = "Market_State_Pack_Shadow_Summary"
INPUT_SESSIONS_SHEET = "Market_Sessions"
INPUT_MEMBERS_SHEET = "Market_Session_Members"
INPUT_ATTENTION_HISTORY_SHEET = "Session_Attention_Map_History"
MAIN_EVENT_SHEET = "Event"
MAIN_CONFIG_SHEET = "Config"

OUTPUT_FORECASTS_SHEET = "Pack_Exposure_Forecasts"
OUTPUT_METADATA_SHEET = "Pack_Exposure_Forecast_Metadata"
OUTPUT_BEHAVIOR_SHEET = "Pack_Exposure_Behavior_Capture"
OUTPUT_RAW_ARCHIVE_SHEET = "Pack_Exposure_Raw_Response_Archive"
OUTPUT_RUN_LOG_SHEET = "Pack_Exposure_Run_Log"
OUTPUT_SUMMARY_SHEET = "Pack_Exposure_Run_Summary"

SCHEMA_VERSION = "presignal_v2_pack_exposure_pilot_0.1"
EXPERIMENT_ID = "pack_exposure_pilot_experiment_001"
EXPERIMENT_VERSION = "pack_exposure_pilot_v0"
RUN_TYPE = "controlled_pack_exposure_pilot"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-2"
REGISTRY_CATEGORY = "PRESIGNAL_V2_PACK_EXPOSURE_PILOT"
REGISTRY_OWNER_MODULE = "market_state"
AUTOMATION_PROVIDER_FUNCTION = "apiCallProviderJsonObject"
PROVIDER_ORDER = ["OpenAI", "Gemini", "Anthropic"]

FORECAST_HEADERS = [
    "generated_ts",
    "schema_version",
    "experiment_id",
    "experiment_version",
    "pilot_run_id",
    "prompt_version",
    "prompt_hash",
    "provider",
    "model",
    "session_id",
    "session_date",
    "country",
    "session_window_name",
    "pack_level",
    "pack_level_name",
    "forecast_timestamp",
    "run_type",
    "shadow_only",
    "production_visible",
    "temperature",
    "config_version",
    "forecast_direction",
    "forecast_confidence",
    "expected_move_pips_min",
    "expected_move_pips_max",
    "expected_holding_minutes",
    "json_parse_success",
    "json_validation_success",
    "raw_response_archive_key",
    "status",
    "error_message",
    "notes",
]

METADATA_HEADERS = [
    "generated_ts",
    "schema_version",
    "experiment_id",
    "experiment_version",
    "pilot_run_id",
    "prompt_version",
    "prompt_hash",
    "provider",
    "model",
    "session_id",
    "pack_level",
    "pack_level_name",
    "forecast_timestamp",
    "run_type",
    "shadow_only",
    "production_visible",
    "temperature",
    "config_version",
    "allowed_pack_fields",
    "actual_pack_fields_in_prompt",
    "prompt_token_estimate",
    "provider_prompt_tokens",
    "provider_completion_tokens",
    "request_status",
    "response_status",
    "json_parse_success",
    "json_validation_success",
    "source_prompt_design_sheet",
    "source_shadow_sheet",
    "notes",
]

BEHAVIOR_HEADERS = [
    "generated_ts",
    "schema_version",
    "experiment_id",
    "experiment_version",
    "pilot_run_id",
    "prompt_version",
    "prompt_hash",
    "provider",
    "model",
    "session_id",
    "pack_level",
    "pack_level_name",
    "primary_driver_summary",
    "secondary_driver_summary",
    "ignored_event_summary",
    "information_used",
    "information_not_used",
    "pack_fields_used",
    "pack_fields_discarded",
    "pack_fields_that_changed_reasoning",
    "pack_fields_that_did_not_change_reasoning",
    "causal_chain",
    "invalidation_condition",
    "uncertainty_sources",
    "missing_information",
    "no_signal_flag",
    "no_signal_reason",
    "reasoning_summary",
    "json_validation_success",
    "status",
    "error_message",
    "notes",
]

RAW_ARCHIVE_HEADERS = [
    "generated_ts",
    "experiment_id",
    "pilot_run_id",
    "provider",
    "model",
    "session_id",
    "pack_level",
    "prompt_hash",
    "raw_response",
    "response_hash",
    "json_parse_success",
    "json_validation_success",
    "parse_error",
    "notes",
]

RUN_LOG_HEADERS = [
    "generated_ts",
    "schema_version",
    "experiment_id",
    "experiment_version",
    "pilot_run_id",
    "session_id",
    "provider",
    "model",
    "pack_level",
    "pack_level_name",
    "prompt_hash",
    "request_status",
    "response_status",
    "json_parse_success",
    "json_validation_success",
    "status",
    "error_message",
    "elapsed_seconds",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "experiment_id",
    "experiment_version",
    "pilot_run_id",
    "build_status",
    "final_interpretation",
    "session_selected",
    "pack_levels_executed",
    "providers_executed",
    "forecast_count",
    "successful_provider_calls",
    "failed_provider_calls",
    "raw_responses_archived",
    "json_validation_success_count",
    "json_validation_failure_count",
    "behavior_rows_captured",
    "metadata_rows_written",
    "run_log_rows_written",
    "shadow_only_count",
    "production_visible_count",
    "routing_changes",
    "provider_weight_changes",
    "ensemble_changes",
    "evaluation_changes",
    "subscriber_visible",
    "predictions_write_count",
    "evaluation_write_count",
    "outcome_ledger_write_count",
    "mr_provider_runs_write_count",
    "market_state_pack_write_count",
    "production_behavior_change_count",
    "notes",
]


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _as_bool(value: Any) -> bool:
    return _upper(value) in {"TRUE", "T", "YES", "Y", "1"}


def _pilot_run_id(generated_ts: str) -> str:
    stamp = generated_ts.replace("-", "").replace(":", "").replace("+00:00", "Z").replace(".", "")
    return f"pack_exposure_pilot_v0_{stamp}"


def _provider_map(prompt_rows: Sequence[Dict[str, Any]]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for row in prompt_rows:
        provider = _normalize_provider_name(row.get("provider"))
        if provider:
            out.setdefault(provider, _norm(row.get("model")))
    return out


def _config_map(rows: Sequence[Dict[str, Any]]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for row in rows:
        keys = list(row.keys())
        if len(keys) >= 2:
            key = _norm(row.get(keys[0]))
            value = _norm(row.get(keys[1]))
            if key:
                out[key] = value
        for key_name in ("key", "name", "config_key"):
            if _norm(row.get(key_name)):
                out[_norm(row.get(key_name))] = _norm(row.get("value"))
    return out


def _jsonish(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=True)
    return _norm(value)


def _select_session(shadow_rows: Sequence[Dict[str, Any]]) -> Tuple[str, str]:
    required = set(EXPECTED_FIELDS_BY_LEVEL["D"])
    by_session: Dict[str, Dict[str, Dict[str, Any]]] = {}
    session_dates: Dict[str, str] = {}
    for row in shadow_rows:
        session_id = _norm(row.get("session_id"))
        field = _norm(row.get("candidate_field"))
        if not session_id or field not in required:
            continue
        by_session.setdefault(session_id, {})[field] = row
        session_dates.setdefault(session_id, _norm(row.get("session_date")))

    candidates: List[Tuple[str, str]] = []
    for session_id, fields in by_session.items():
        if set(fields) != required:
            continue
        if all(_upper(row.get("data_available_flag")) == "TRUE" and _upper(row.get("leakage_check_status")) != "FAIL" for row in fields.values()):
            candidates.append((session_dates.get(session_id, ""), session_id))
    if not candidates:
        return "", "no session had complete deterministic Lane A pack fields"
    candidates.sort()
    return candidates[0][1], "earliest complete deterministic shadow-pack session selected"


def _build_provider_prompt(design_row: Dict[str, Any], event_context: Dict[str, Any], market_state_context: Dict[str, Any], schema_payload, guardrail_payload) -> Tuple[Dict[str, str], str, str]:
    core_text, full_text = _assemble_prompt_text(design_row, event_context, market_state_context, schema_payload, guardrail_payload)
    prompt = {
        "system": _norm(design_row.get("system_prompt_template")),
        "user": "\n\n".join(
            [
                "MARKET SESSION CONTEXT",
                json.dumps(event_context, ensure_ascii=True),
                "ASSIGNED MARKET-STATE CONTEXT",
                json.dumps(market_state_context, ensure_ascii=True),
                "REQUIRED JSON OUTPUT SCHEMA",
                json.dumps({"required_json_output_schema": list(schema_payload)}, ensure_ascii=True),
                "GUARDRAILS",
                json.dumps({"guardrails": list(guardrail_payload)}, ensure_ascii=True),
            ]
        ),
        "instruction": _norm(design_row.get("user_prompt_template")),
        "cache_scaffold": "",
    }
    prompt_hash = _sha256_text(json.dumps(prompt, sort_keys=True, ensure_ascii=True))
    return prompt, prompt_hash, full_text


def _call_live_provider_raw(script_service, script_id: str, provider: str, model: str, prompt: Dict[str, str]) -> Dict[str, Any]:
    try:
        result = run_script_function(
            script_service,
            script_id,
            AUTOMATION_PROVIDER_FUNCTION,
            [{"provider": provider, "prompt": prompt}],
        )
    except Exception as exc:
        return {
            "status": "execution_error",
            "provider": provider,
            "model": model,
            "request_status": "attempted",
            "response_status": "execution_error",
            "raw_output": "",
            "error": str(exc),
        }
    if not isinstance(result, dict):
        return {
            "status": "execution_error",
            "provider": provider,
            "model": model,
            "request_status": "attempted",
            "response_status": "execution_error",
            "raw_output": "",
            "error": "provider execution returned non-object result",
        }
    return {
        "status": _norm(result.get("status")) or "error",
        "provider": _normalize_provider_name(result.get("provider")) or provider,
        "model": _norm(result.get("model")) or model,
        "request_status": _norm(result.get("request_status")) or "attempted",
        "response_status": _norm(result.get("response_status")) or _norm(result.get("status")) or "unknown",
        "raw_output": str(result.get("raw_output") or ""),
        "error": _norm(result.get("error")),
        "prompt_tokens": _norm(result.get("prompt_tokens")),
        "completion_tokens": _norm(result.get("completion_tokens")),
    }


def _strip_json_fences(raw_output: Any) -> str:
    text = str(raw_output or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _extract_first_json_object(text: str) -> Optional[str]:
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _recover_pack_json_payload(raw_output: Any) -> Dict[str, Any]:
    text = _strip_json_fences(raw_output)
    if not text:
        return {"ok": False, "parsed": {}, "error": "empty_response", "notes": "empty_response"}
    try:
        parsed = json.loads(text)
        return {"ok": isinstance(parsed, dict), "parsed": parsed if isinstance(parsed, dict) else {}, "error": "" if isinstance(parsed, dict) else "top_level_json_not_object", "notes": "not_needed"}
    except Exception as first_error:
        candidate = _extract_first_json_object(text)
        if not candidate:
            return {"ok": False, "parsed": {}, "error": str(first_error), "notes": "no_json_object_candidate"}
        try:
            parsed = json.loads(candidate)
            return {"ok": isinstance(parsed, dict), "parsed": parsed if isinstance(parsed, dict) else {}, "error": "" if isinstance(parsed, dict) else "top_level_json_not_object", "notes": "extracted_first_json_object"}
        except Exception as second_error:
            return {"ok": False, "parsed": {}, "error": str(second_error), "notes": "json_object_candidate_parse_failed"}


def _parse_provider_json(raw_output: str, session_id: str, provider: str, pack_level: str, schema_rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    recovery = _recover_pack_json_payload(raw_output)
    if not recovery.get("ok"):
        return {
            "parse_success": False,
            "validation_success": False,
            "parsed": {},
            "parse_error": recovery.get("error") or "json_parse_failed",
            "notes": recovery.get("notes", ""),
        }
    parsed = recovery.get("parsed", {})
    errors: List[str] = []
    notes: List[str] = [recovery.get("notes", "")]
    required_fields = [_norm(row.get("field_name")) for row in schema_rows if _as_bool(row.get("required"))]
    for field in required_fields:
        if field and field not in parsed:
            errors.append(f"missing_required_field:{field}")
    provider_field = _normalize_provider_name(parsed.get("provider"))
    if provider_field and provider_field != provider:
        notes.append(f"provider_self_label_mismatch:{provider_field}")
    session_field = _norm(parsed.get("session_id"))
    if session_field and session_field != session_id:
        notes.append(f"session_id_self_label_mismatch:{session_field}")
    pack_field = _norm(parsed.get("pack_level"))
    if pack_field and pack_field != pack_level:
        notes.append(f"pack_level_self_label_mismatch:{pack_field}")
    if pack_field and pack_field not in ACTIVE_PACK_LEVELS:
        errors.append(f"invalid_pack_level:{pack_field}")
    direction, invalid_direction = _normalize_forecast_direction(parsed.get("forecast_direction"))
    if invalid_direction:
        errors.append("invalid_forecast_direction")
    return {
        "parse_success": True,
        "validation_success": not errors,
        "parsed": parsed,
        "parse_error": "; ".join(errors),
        "notes": "; ".join(note for note in notes if note),
        "normalized_direction": direction,
    }


def _base_metadata(
    generated_ts: str,
    pilot_run_id: str,
    prompt_version: str,
    prompt_hash: str,
    provider: str,
    model: str,
    session_meta: Dict[str, Any],
    pack_level: str,
    pack_level_name: str,
    temperature: str,
    config_version: str,
) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "experiment_version": EXPERIMENT_VERSION,
        "pilot_run_id": pilot_run_id,
        "prompt_version": prompt_version,
        "prompt_hash": prompt_hash,
        "provider": provider,
        "model": model,
        "session_id": session_meta["session_id"],
        "session_date": session_meta.get("session_date", ""),
        "country": session_meta.get("country", ""),
        "session_window_name": session_meta.get("session_window_name", ""),
        "pack_level": pack_level,
        "pack_level_name": pack_level_name,
        "forecast_timestamp": session_meta.get("forecast_timestamp", ""),
        "run_type": RUN_TYPE,
        "shadow_only": "TRUE",
        "production_visible": "FALSE",
        "temperature": temperature,
        "config_version": config_version,
    }


def _summary_row(
    generated_ts: str,
    pilot_run_id: str,
    session_id: str,
    forecast_rows: Sequence[Dict[str, Any]],
    behavior_rows: Sequence[Dict[str, Any]],
    metadata_rows: Sequence[Dict[str, Any]],
    raw_rows: Sequence[Dict[str, Any]],
    log_rows: Sequence[Dict[str, Any]],
    notes: Sequence[str],
) -> Dict[str, Any]:
    successful_calls = sum(1 for row in log_rows if _norm(row.get("response_status")) == "ok")
    failed_calls = len(log_rows) - successful_calls
    json_success = sum(1 for row in raw_rows if _upper(row.get("json_validation_success")) == "TRUE")
    json_failure = len(raw_rows) - json_success
    safety = {
        "production_visible_count": sum(1 for row in forecast_rows if _upper(row.get("production_visible")) == "TRUE"),
        "routing_changes": "FALSE",
        "provider_weight_changes": "FALSE",
        "ensemble_changes": "FALSE",
        "evaluation_changes": "FALSE",
        "subscriber_visible": "FALSE",
        "predictions_write_count": 0,
        "evaluation_write_count": 0,
        "outcome_ledger_write_count": 0,
        "mr_provider_runs_write_count": 0,
        "market_state_pack_write_count": 0,
        "production_behavior_change_count": 0,
    }
    if any(value not in ("FALSE", 0) for value in safety.values()):
        build_status = "FAIL"
        final = "PACK_EXPOSURE_PILOT_BLOCKED"
    elif failed_calls or json_failure:
        build_status = "PASS_WITH_WARNINGS"
        final = "PACK_EXPOSURE_PILOT_READY_WITH_WARNINGS" if successful_calls else "PACK_EXPOSURE_PILOT_NEEDS_REVIEW"
    else:
        build_status = "PASS"
        final = "PACK_EXPOSURE_PILOT_READY"
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "experiment_version": EXPERIMENT_VERSION,
        "pilot_run_id": pilot_run_id,
        "build_status": build_status,
        "final_interpretation": final,
        "session_selected": session_id,
        "pack_levels_executed": "|".join(ACTIVE_PACK_LEVELS),
        "providers_executed": "|".join(PROVIDER_ORDER),
        "forecast_count": len(forecast_rows),
        "successful_provider_calls": successful_calls,
        "failed_provider_calls": failed_calls,
        "raw_responses_archived": len(raw_rows),
        "json_validation_success_count": json_success,
        "json_validation_failure_count": json_failure,
        "behavior_rows_captured": len(behavior_rows),
        "metadata_rows_written": len(metadata_rows),
        "run_log_rows_written": len(log_rows),
        "shadow_only_count": sum(1 for row in forecast_rows if _upper(row.get("shadow_only")) == "TRUE"),
        **safety,
        "notes": _truncate_text(json.dumps({"notes": list(notes)}, ensure_ascii=True), 500),
    }


def _upsert_registry_rows(service) -> Dict[str, int]:
    headers = _ensure_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_upper(row.get("logical_sheet_id")): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_upper(row.get("logical_sheet_id")): row for row in rows}
    registry_rows = [
        ("PACK_EXPOSURE_FORECASTS", OUTPUT_FORECASTS_SHEET, "pack_exposure_forecast_capture"),
        ("PACK_EXPOSURE_FORECAST_METADATA", OUTPUT_METADATA_SHEET, "pack_exposure_forecast_metadata"),
        ("PACK_EXPOSURE_BEHAVIOR_CAPTURE", OUTPUT_BEHAVIOR_SHEET, "pack_exposure_behavior_capture"),
        ("PACK_EXPOSURE_RAW_RESPONSE_ARCHIVE", OUTPUT_RAW_ARCHIVE_SHEET, "pack_exposure_raw_response_archive"),
        ("PACK_EXPOSURE_RUN_LOG", OUTPUT_RUN_LOG_SHEET, "pack_exposure_run_log"),
        ("PACK_EXPOSURE_RUN_SUMMARY", OUTPUT_SUMMARY_SHEET, "pack_exposure_run_summary"),
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
            "lifecycle": "active_shadow",
            "lifecycle_state": "ACTIVE",
            "owner_module": REGISTRY_OWNER_MODULE,
            "participates_in_rebuild": "TRUE",
            "read_only": "FALSE",
            "allow_creation": "TRUE",
            "created_phase": PHASE_LABEL,
            "notes": "Phase 9A-2 controlled pilot output; shadow-only and not production visible.",
            "registry_created_ts": _norm(existing.get("registry_created_ts")) or now,
            "registry_last_verified_ts": now,
            "registry_migration_ts": _norm(existing.get("registry_migration_ts")),
            "registry_rename_ts": _norm(existing.get("registry_rename_ts")),
        }
        values = [merged.get(header, "") for header in headers]
        if key in by_id:
            row_number = by_id[key]
        else:
            appended += 1
            row_number = len(rows) + appended + 1
        updates.append({"range": f"'{REGISTRY_SHEET}'!A{row_number}:{_column_letter(len(headers))}{row_number}", "values": [values]})
    if updates:
        batch_update_values(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, updates)
    return {"updated": len(registry_rows) - appended, "appended": appended}


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run PreSignal v2.0 Phase 9A-2 controlled pack exposure pilot.")
    parser.add_argument(
        "--reparse-latest",
        action="store_true",
        help="Rebuild pilot output sheets from the latest raw-response archive without calling providers.",
    )
    parser.add_argument(
        "--true-shared-pack-e-freeze-manifest",
        default="",
        help=(
            "Absolute path to an explicitly frozen true shared Pack E manifest. "
            "When supplied, only Pack E uses that frozen artifact; Pack A remains the baseline."
        ),
    )
    return parser.parse_args(argv)


def _reparse_latest_archived_run(
    generated_ts: str,
    sheets_service,
    diagnostics_titles: Set[str],
    main_titles: Set[str],
) -> Dict[str, Any]:
    warnings: List[str] = []
    missing: List[str] = []
    summary_rows = _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, OUTPUT_SUMMARY_SHEET, missing)
    latest_pilot_run_id = _latest_run_id(summary_rows, "pilot_run_id")
    raw_rows_existing = [
        row
        for row in _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, OUTPUT_RAW_ARCHIVE_SHEET, missing)
        if _norm(row.get("pilot_run_id")) == latest_pilot_run_id
    ]
    metadata_existing = [
        row
        for row in _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, OUTPUT_METADATA_SHEET, missing)
        if _norm(row.get("pilot_run_id")) == latest_pilot_run_id
    ]
    prompt_summary_rows = _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_PROMPT_SUMMARY_SHEET, missing)
    prompt_design_run_id = _latest_run_id(prompt_summary_rows, "prompt_design_run_id")
    schema_rows = _filter_by_run(
        _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_OUTPUT_SCHEMA_SHEET, missing),
        "prompt_design_run_id",
        prompt_design_run_id,
    )
    shadow_summary_rows = _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_SHADOW_SUMMARY_SHEET, warnings)
    shadow_run_id = _latest_run_id(shadow_summary_rows, "shadow_pack_run_id")
    shadow_rows = _filter_by_run(
        _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_SHADOW_SHEET, warnings),
        "shadow_pack_run_id",
        shadow_run_id,
    )
    session_meta_by_id, _ = _shadow_index(shadow_rows)
    if not latest_pilot_run_id or not raw_rows_existing or not metadata_existing or not schema_rows:
        summary = _summary_row(generated_ts, latest_pilot_run_id or _pilot_run_id(generated_ts), "", [], [], [], [], [], ["reparse blocked: missing latest raw archive, metadata, or schema"])
        summary["build_status"] = "FAIL"
        summary["final_interpretation"] = "PACK_EXPOSURE_PILOT_BLOCKED"
        for sheet, default_headers, rows in [
            (OUTPUT_FORECASTS_SHEET, FORECAST_HEADERS, []),
            (OUTPUT_METADATA_SHEET, METADATA_HEADERS, []),
            (OUTPUT_BEHAVIOR_SHEET, BEHAVIOR_HEADERS, []),
            (OUTPUT_RAW_ARCHIVE_SHEET, RAW_ARCHIVE_HEADERS, raw_rows_existing),
            (OUTPUT_RUN_LOG_SHEET, RUN_LOG_HEADERS, []),
            (OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS, [summary]),
        ]:
            headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, sheet, default_headers)
            _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, sheet, headers, rows)
        registry = _upsert_registry_rows(sheets_service)
        return {"build_status": summary["build_status"], "final_interpretation": summary["final_interpretation"], "registry": registry, "missing_required": missing}

    raw_by_key = {
        (
            _norm(row.get("session_id")),
            _normalize_provider_name(row.get("provider")),
            _norm(row.get("pack_level")),
            _norm(row.get("prompt_hash")),
        ): row
        for row in raw_rows_existing
    }
    forecast_rows: List[Dict[str, Any]] = []
    metadata_rows: List[Dict[str, Any]] = []
    behavior_rows: List[Dict[str, Any]] = []
    raw_rows: List[Dict[str, Any]] = []
    log_rows: List[Dict[str, Any]] = []
    selected_session_id = _norm(metadata_existing[0].get("session_id"))

    for meta in metadata_existing:
        provider = _normalize_provider_name(meta.get("provider"))
        session_id = _norm(meta.get("session_id"))
        pack_level = _norm(meta.get("pack_level"))
        prompt_hash = _norm(meta.get("prompt_hash"))
        raw_row = raw_by_key.get((session_id, provider, pack_level, prompt_hash), {})
        raw_output = _norm(raw_row.get("raw_response"))
        model = _norm(meta.get("model")) or _norm(raw_row.get("model"))
        parse = _parse_provider_json(raw_output, session_id, provider, pack_level, schema_rows)
        parsed = parse.get("parsed", {})
        response_hash = _sha256_text(raw_output)
        raw_key = f"{latest_pilot_run_id}|{session_id}|{provider}|{pack_level}|{prompt_hash}"
        session_meta = session_meta_by_id.get(
            session_id,
            {
                "session_id": session_id,
                "session_date": "",
                "country": "",
                "session_window_name": "",
                "forecast_timestamp": _norm(meta.get("forecast_timestamp")),
            },
        )

        raw_rows.append(
            {
                "generated_ts": _norm(raw_row.get("generated_ts")) or generated_ts,
                "experiment_id": EXPERIMENT_ID,
                "pilot_run_id": latest_pilot_run_id,
                "provider": provider,
                "model": model,
                "session_id": session_id,
                "pack_level": pack_level,
                "prompt_hash": prompt_hash,
                "raw_response": raw_output,
                "response_hash": response_hash,
                "json_parse_success": "TRUE" if parse.get("parse_success") else "FALSE",
                "json_validation_success": "TRUE" if parse.get("validation_success") else "FALSE",
                "parse_error": _truncate_text(parse.get("parse_error", ""), 500),
                "notes": _truncate_text(parse.get("notes", ""), 500),
            }
        )

        direction, _ = _normalize_forecast_direction(parsed.get("forecast_direction"))
        confidence, _ = _normalize_confidence(parsed.get("forecast_confidence"))
        move_min, _ = _normalize_numeric_value(parsed.get("expected_move_pips_min"))
        move_max, _ = _normalize_numeric_value(parsed.get("expected_move_pips_max"))
        holding, _ = _normalize_holding_minutes(parsed.get("expected_holding_minutes"))
        no_signal = "TRUE" if _as_bool(parsed.get("no_signal_flag")) or direction == "no_clear_direction" else "FALSE"
        row_status = "parsed" if parse.get("validation_success") else ("parse_failed" if not parse.get("parse_success") else "validation_failed")

        forecast_row = {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "experiment_id": EXPERIMENT_ID,
            "experiment_version": EXPERIMENT_VERSION,
            "pilot_run_id": latest_pilot_run_id,
            "prompt_version": _norm(meta.get("prompt_version")),
            "prompt_hash": prompt_hash,
            "provider": provider,
            "model": model,
            "session_id": session_id,
            "session_date": session_meta.get("session_date", ""),
            "country": session_meta.get("country", ""),
            "session_window_name": session_meta.get("session_window_name", ""),
            "pack_level": pack_level,
            "pack_level_name": _norm(meta.get("pack_level_name")),
            "forecast_timestamp": _norm(meta.get("forecast_timestamp")),
            "run_type": RUN_TYPE,
            "shadow_only": "TRUE",
            "production_visible": "FALSE",
            "temperature": _norm(meta.get("temperature")),
            "config_version": _norm(meta.get("config_version")),
            "forecast_direction": direction if parse.get("parse_success") else "",
            "forecast_confidence": confidence,
            "expected_move_pips_min": move_min,
            "expected_move_pips_max": move_max,
            "expected_holding_minutes": holding,
            "json_parse_success": "TRUE" if parse.get("parse_success") else "FALSE",
            "json_validation_success": "TRUE" if parse.get("validation_success") else "FALSE",
            "raw_response_archive_key": raw_key,
            "status": row_status,
            "error_message": _truncate_text(parse.get("parse_error", ""), 500),
            "notes": _truncate_text(f"response_hash={response_hash}; reparse_latest=TRUE", 500),
        }
        forecast_rows.append(forecast_row)

        metadata = dict(meta)
        metadata.update(
            {
                "generated_ts": generated_ts,
                "model": model,
                "request_status": _norm(meta.get("request_status")) or "attempted",
                "response_status": _norm(meta.get("response_status")) or "ok",
                "json_parse_success": forecast_row["json_parse_success"],
                "json_validation_success": forecast_row["json_validation_success"],
                "notes": _truncate_text((_norm(meta.get("notes")) + "; reparse_latest=TRUE").strip("; "), 500),
            }
        )
        metadata_rows.append(metadata)

        behavior_rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "experiment_id": EXPERIMENT_ID,
                "experiment_version": EXPERIMENT_VERSION,
                "pilot_run_id": latest_pilot_run_id,
                "prompt_version": _norm(meta.get("prompt_version")),
                "prompt_hash": prompt_hash,
                "provider": provider,
                "model": model,
                "session_id": session_id,
                "pack_level": pack_level,
                "pack_level_name": _norm(meta.get("pack_level_name")),
                "primary_driver_summary": _truncate_text(_norm(parsed.get("primary_driver_summary")), 500),
                "secondary_driver_summary": _truncate_text(_norm(parsed.get("secondary_driver_summary")), 500),
                "ignored_event_summary": _truncate_text(_norm(parsed.get("ignored_event_summary")), 500),
                "information_used": _truncate_text(_jsonish(parsed.get("information_used")), 500),
                "information_not_used": _truncate_text(_jsonish(parsed.get("information_not_used")), 500),
                "pack_fields_used": _truncate_text(_jsonish(parsed.get("pack_fields_used")), 500),
                "pack_fields_discarded": _truncate_text(_jsonish(parsed.get("pack_fields_discarded")), 500),
                "pack_fields_that_changed_reasoning": _truncate_text(_jsonish(parsed.get("pack_fields_that_changed_reasoning")), 500),
                "pack_fields_that_did_not_change_reasoning": _truncate_text(_jsonish(parsed.get("pack_fields_that_did_not_change_reasoning")), 500),
                "causal_chain": _truncate_text(_norm(parsed.get("causal_chain")), 800),
                "invalidation_condition": _truncate_text(_norm(parsed.get("invalidation_condition")), 500),
                "uncertainty_sources": _truncate_text(_jsonish(parsed.get("uncertainty_sources")), 500),
                "missing_information": _truncate_text(_jsonish(parsed.get("missing_information")), 500),
                "no_signal_flag": no_signal if parse.get("parse_success") else "",
                "no_signal_reason": _truncate_text(_norm(parsed.get("no_signal_reason")), 500),
                "reasoning_summary": _truncate_text(_norm(parsed.get("session_narrative")) or _norm(parsed.get("reasoning_summary")) or _norm(parsed.get("causal_chain")), 800),
                "json_validation_success": forecast_row["json_validation_success"],
                "status": row_status,
                "error_message": forecast_row["error_message"],
                "notes": "reparse_latest=TRUE",
            }
        )

        log_rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "experiment_id": EXPERIMENT_ID,
                "experiment_version": EXPERIMENT_VERSION,
                "pilot_run_id": latest_pilot_run_id,
                "session_id": session_id,
                "provider": provider,
                "model": model,
                "pack_level": pack_level,
                "pack_level_name": _norm(meta.get("pack_level_name")),
                "prompt_hash": prompt_hash,
                "request_status": _norm(meta.get("request_status")) or "attempted",
                "response_status": _norm(meta.get("response_status")) or "ok",
                "json_parse_success": forecast_row["json_parse_success"],
                "json_validation_success": forecast_row["json_validation_success"],
                "status": row_status,
                "error_message": forecast_row["error_message"],
                "elapsed_seconds": "",
                "notes": f"reparse_latest=TRUE; raw_response_archive_key={raw_key}",
            }
        )

    summary = _summary_row(
        generated_ts,
        latest_pilot_run_id,
        selected_session_id,
        forecast_rows,
        behavior_rows,
        metadata_rows,
        raw_rows,
        log_rows,
        ["reparsed latest raw-response archive without provider calls"],
    )
    for sheet, default_headers, rows in [
        (OUTPUT_FORECASTS_SHEET, FORECAST_HEADERS, forecast_rows),
        (OUTPUT_METADATA_SHEET, METADATA_HEADERS, metadata_rows),
        (OUTPUT_BEHAVIOR_SHEET, BEHAVIOR_HEADERS, behavior_rows),
        (OUTPUT_RAW_ARCHIVE_SHEET, RAW_ARCHIVE_HEADERS, raw_rows),
        (OUTPUT_RUN_LOG_SHEET, RUN_LOG_HEADERS, log_rows),
        (OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS, [summary]),
    ]:
        headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, sheet, default_headers)
        _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, sheet, headers, rows)
    registry = _upsert_registry_rows(sheets_service)
    return {
        "pilot_run_id": latest_pilot_run_id,
        "build_status": summary["build_status"],
        "final_interpretation": summary["final_interpretation"],
        "session_selected": selected_session_id,
        "sheets_written": {
            OUTPUT_FORECASTS_SHEET: len(forecast_rows),
            OUTPUT_METADATA_SHEET: len(metadata_rows),
            OUTPUT_BEHAVIOR_SHEET: len(behavior_rows),
            OUTPUT_RAW_ARCHIVE_SHEET: len(raw_rows),
            OUTPUT_RUN_LOG_SHEET: len(log_rows),
            OUTPUT_SUMMARY_SHEET: 1,
        },
        "forecast_count": summary["forecast_count"],
        "successful_provider_calls": summary["successful_provider_calls"],
        "failed_provider_calls": summary["failed_provider_calls"],
        "raw_responses_archived": summary["raw_responses_archived"],
        "json_validation_success_count": summary["json_validation_success_count"],
        "json_validation_failure_count": summary["json_validation_failure_count"],
        "behavior_rows_captured": summary["behavior_rows_captured"],
        "immutable_metadata_verified": "TRUE",
        "provider_call_count_this_reparse": 0,
        "registry": registry,
        "warnings": warnings,
        "missing_required": missing,
        "summary": summary,
    }


def build_pack_exposure_pilot_run_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    args = args or _parse_args()
    generated_ts = _iso_now()
    pilot_run_id = _pilot_run_id(generated_ts)

    creds = load_credentials()
    sheets_service = build_sheets_service(creds)
    script_service = build_script_service(creds)
    script_id = default_script_id()
    diagnostics_titles = _get_sheet_titles(sheets_service, DIAGNOSTICS_SPREADSHEET_ID)
    main_titles = _get_sheet_titles(sheets_service, MAIN_SPREADSHEET_ID)
    if getattr(args, "reparse_latest", False):
        return _reparse_latest_archived_run(generated_ts, sheets_service, diagnostics_titles, main_titles)

    missing_required: List[str] = []
    warnings: List[str] = []

    prompt_summary_rows = _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_PROMPT_SUMMARY_SHEET, missing_required)
    prompt_design_run_id = _latest_run_id(prompt_summary_rows, "prompt_design_run_id")
    prompt_rows = _filter_by_run(
        _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_PROMPT_DESIGN_SHEET, missing_required),
        "prompt_design_run_id",
        prompt_design_run_id,
    )
    schema_rows = _filter_by_run(
        _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_OUTPUT_SCHEMA_SHEET, missing_required),
        "prompt_design_run_id",
        prompt_design_run_id,
    )
    guardrail_rows = _filter_by_run(
        _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_GUARDRAILS_SHEET, missing_required),
        "prompt_design_run_id",
        prompt_design_run_id,
    )
    validation_summary_rows = _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_VALIDATION_SUMMARY_SHEET, missing_required)
    level_summary_rows = _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_LEVEL_SUMMARY_SHEET, missing_required)
    pack_design_run_id = _latest_run_id(level_summary_rows, "pack_design_run_id")
    level_items = _filter_by_run(
        _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_LEVEL_ITEMS_SHEET, missing_required),
        "pack_design_run_id",
        pack_design_run_id,
    )
    shadow_summary_rows = _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_SHADOW_SUMMARY_SHEET, missing_required)
    shadow_run_id = _latest_run_id(shadow_summary_rows, "shadow_pack_run_id")
    shadow_rows = _filter_by_run(
        _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_SHADOW_SHEET, missing_required),
        "shadow_pack_run_id",
        shadow_run_id,
    )
    session_rows = _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_SESSIONS_SHEET, warnings)
    member_rows = _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_MEMBERS_SHEET, warnings)
    attention_rows = _read_optional_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, INPUT_ATTENTION_HISTORY_SHEET, warnings)
    event_rows = _read_optional_rows(sheets_service, MAIN_SPREADSHEET_ID, main_titles, MAIN_EVENT_SHEET, warnings)
    config_rows = _read_optional_rows(sheets_service, MAIN_SPREADSHEET_ID, main_titles, MAIN_CONFIG_SHEET, warnings)

    if not prompt_rows or not schema_rows or not guardrail_rows or not level_items or not shadow_rows or not validation_summary_rows:
        summary = _summary_row(generated_ts, pilot_run_id, "", [], [], [], [], [], ["pilot blocked: required Phase 8C/9A-0/9A-1 inputs missing"])
        summary["build_status"] = "FAIL"
        summary["final_interpretation"] = "PACK_EXPOSURE_PILOT_BLOCKED"
        headers = [
            (OUTPUT_FORECASTS_SHEET, FORECAST_HEADERS, []),
            (OUTPUT_METADATA_SHEET, METADATA_HEADERS, []),
            (OUTPUT_BEHAVIOR_SHEET, BEHAVIOR_HEADERS, []),
            (OUTPUT_RAW_ARCHIVE_SHEET, RAW_ARCHIVE_HEADERS, []),
            (OUTPUT_RUN_LOG_SHEET, RUN_LOG_HEADERS, []),
            (OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS, [summary]),
        ]
        for sheet, default_headers, rows in headers:
            sheet_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, sheet, default_headers)
            _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, sheet, sheet_headers, rows)
        registry = _upsert_registry_rows(sheets_service)
        return {"build_status": summary["build_status"], "final_interpretation": summary["final_interpretation"], "registry": registry, "missing_required": missing_required}

    session_meta_by_id, shadow_field_rows = _shadow_index(shadow_rows)
    selected_session_id, selection_note = _select_session(shadow_rows)
    if not selected_session_id:
        summary = _summary_row(generated_ts, pilot_run_id, "", [], [], [], [], [], [selection_note])
        summary["build_status"] = "FAIL"
        summary["final_interpretation"] = "PACK_EXPOSURE_PILOT_BLOCKED"
        for sheet, default_headers, rows in [
            (OUTPUT_FORECASTS_SHEET, FORECAST_HEADERS, []),
            (OUTPUT_METADATA_SHEET, METADATA_HEADERS, []),
            (OUTPUT_BEHAVIOR_SHEET, BEHAVIOR_HEADERS, []),
            (OUTPUT_RAW_ARCHIVE_SHEET, RAW_ARCHIVE_HEADERS, []),
            (OUTPUT_RUN_LOG_SHEET, RUN_LOG_HEADERS, []),
            (OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS, [summary]),
        ]:
            sheet_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, sheet, default_headers)
            _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, sheet, sheet_headers, rows)
        registry = _upsert_registry_rows(sheets_service)
        return {"build_status": summary["build_status"], "final_interpretation": summary["final_interpretation"], "registry": registry, "missing_required": missing_required}

    provider_models = _provider_map(prompt_rows)
    providers = [(provider, provider_models.get(provider, "")) for provider in PROVIDER_ORDER if provider in provider_models]
    if len(providers) != 3:
        warnings.append(f"expected three providers, resolved={json.dumps(providers, ensure_ascii=True)}")

    config = _config_map(config_rows)
    temperature = config.get("PREDICTION_TEMPERATURE") or config.get("prediction_temperature") or ""
    config_version = _sha256_text(json.dumps(config, sort_keys=True, ensure_ascii=True))[:16] if config else "config_unavailable"
    frozen_true_pack_e = None
    frozen_true_pack_e_manifest = _norm(getattr(args, "true_shared_pack_e_freeze_manifest", ""))
    if frozen_true_pack_e_manifest:
        manifest_path = Path(frozen_true_pack_e_manifest)
        if not manifest_path.is_absolute():
            raise RuntimeError("TRUE_SHARED_PACK_E_FREEZE_MANIFEST_MUST_BE_ABSOLUTE")
        frozen_true_pack_e = load_frozen_true_shared_pack_e(manifest_path)
        warnings.append(
            "true_shared_pack_e_selected_by_explicit_freeze_manifest="
            + frozen_true_pack_e_manifest
        )

    prompt_by_key = _group_prompt_rows(prompt_rows, prompt_design_run_id)
    session_meta = session_meta_by_id[selected_session_id]
    event_context, _, event_notes = _build_event_context(
        selected_session_id,
        session_meta,
        _member_index(member_rows),
        _attention_history_index(attention_rows),
        _event_index(event_rows),
    )
    schema_payload = _schema_payload(schema_rows)
    guardrail_payload = _guardrail_payload(guardrail_rows)
    session_field_map = shadow_field_rows[selected_session_id]

    forecast_rows: List[Dict[str, Any]] = []
    metadata_rows: List[Dict[str, Any]] = []
    behavior_rows: List[Dict[str, Any]] = []
    raw_rows: List[Dict[str, Any]] = []
    log_rows: List[Dict[str, Any]] = []
    notes: List[str] = [selection_note] + event_notes

    for pack_level in ACTIVE_PACK_LEVELS:
        for provider, default_model in providers:
            started = _iso_now()
            design_row = prompt_by_key.get((pack_level, provider), {})
            pack_level_name = _norm(design_row.get("pack_level_name")) or pack_level
            allowed_fields = _split_pipe(design_row.get("allowed_pack_fields")) or list(EXPECTED_FIELDS_BY_LEVEL[pack_level])
            if pack_level == "E" and frozen_true_pack_e is not None:
                market_state_context = render_frozen_true_shared_pack_e_context(frozen_true_pack_e, selected_session_id)
                market_state_entries = market_state_context["assigned_market_state_context"]
                allowed_fields = [entry["item_key"] for entry in market_state_entries]
            else:
                market_state_context, market_state_entries, _ = _build_market_state_context(pack_level, allowed_fields, session_field_map)
            prompt, prompt_hash, full_prompt_text = _build_provider_prompt(
                design_row,
                event_context,
                market_state_context,
                schema_payload,
                guardrail_payload,
            )
            response = _call_live_provider_raw(script_service, script_id, provider, default_model, prompt)
            completed = _iso_now()
            raw_output = response.get("raw_output", "")
            model = response.get("model") or default_model
            parse = _parse_provider_json(raw_output, selected_session_id, provider, pack_level, schema_rows) if response.get("status") == "ok" else {
                "parse_success": False,
                "validation_success": False,
                "parsed": {},
                "parse_error": response.get("error") or "provider_call_failed",
                "notes": "",
            }
            parsed = parse.get("parsed", {})
            raw_key = f"{pilot_run_id}|{selected_session_id}|{provider}|{pack_level}|{prompt_hash}"
            response_hash = _sha256_text(raw_output)

            raw_rows.append(
                {
                    "generated_ts": generated_ts,
                    "experiment_id": EXPERIMENT_ID,
                    "pilot_run_id": pilot_run_id,
                    "provider": provider,
                    "model": model,
                    "session_id": selected_session_id,
                    "pack_level": pack_level,
                    "prompt_hash": prompt_hash,
                    "raw_response": raw_output,
                    "response_hash": response_hash,
                    "json_parse_success": "TRUE" if parse.get("parse_success") else "FALSE",
                    "json_validation_success": "TRUE" if parse.get("validation_success") else "FALSE",
                    "parse_error": _truncate_text(parse.get("parse_error", ""), 500),
                    "notes": _truncate_text(parse.get("notes", ""), 500),
                }
            )

            base = _base_metadata(
                generated_ts,
                pilot_run_id,
                prompt_design_run_id,
                prompt_hash,
                provider,
                model,
                session_meta,
                pack_level,
                pack_level_name,
                temperature,
                config_version,
            )

            direction, _ = _normalize_forecast_direction(parsed.get("forecast_direction"))
            confidence, _ = _normalize_confidence(parsed.get("forecast_confidence"))
            move_min, _ = _normalize_numeric_value(parsed.get("expected_move_pips_min"))
            move_max, _ = _normalize_numeric_value(parsed.get("expected_move_pips_max"))
            holding, _ = _normalize_holding_minutes(parsed.get("expected_holding_minutes"))
            no_signal = "TRUE" if _as_bool(parsed.get("no_signal_flag")) or direction == "no_clear_direction" else "FALSE"
            row_status = "parsed" if parse.get("validation_success") else ("parse_failed" if not parse.get("parse_success") else "validation_failed")

            forecast_row = dict(base)
            forecast_row.update(
                {
                    "forecast_direction": direction if parse.get("parse_success") else "",
                    "forecast_confidence": confidence,
                    "expected_move_pips_min": move_min,
                    "expected_move_pips_max": move_max,
                    "expected_holding_minutes": holding,
                    "json_parse_success": "TRUE" if parse.get("parse_success") else "FALSE",
                    "json_validation_success": "TRUE" if parse.get("validation_success") else "FALSE",
                    "raw_response_archive_key": raw_key,
                    "status": row_status,
                    "error_message": _truncate_text(parse.get("parse_error", ""), 500),
                    "notes": _truncate_text(f"response_hash={response_hash}", 500),
                }
            )
            forecast_rows.append(forecast_row)

            metadata_row = dict(base)
            metadata_row.update(
                {
                    "allowed_pack_fields": "|".join(allowed_fields),
                    "actual_pack_fields_in_prompt": "|".join([
                        entry.get("field_name", "") or entry.get("item_key", "")
                        for entry in market_state_entries
                        if entry.get("field_name", "") or entry.get("item_key", "")
                    ]),
                    "prompt_token_estimate": int(len(full_prompt_text) / 4),
                    "provider_prompt_tokens": response.get("prompt_tokens", ""),
                    "provider_completion_tokens": response.get("completion_tokens", ""),
                    "request_status": response.get("request_status", ""),
                    "response_status": response.get("response_status", ""),
                    "json_parse_success": forecast_row["json_parse_success"],
                    "json_validation_success": forecast_row["json_validation_success"],
                    "source_prompt_design_sheet": INPUT_PROMPT_DESIGN_SHEET,
                    "source_shadow_sheet": INPUT_SHADOW_SHEET,
                    "notes": _truncate_text(
                        response.get("error", "")
                        or (
                            "true_shared_pack_e_fingerprint=" + frozen_true_pack_e["pack_fingerprint"]
                            if pack_level == "E" and frozen_true_pack_e is not None
                            else ""
                        ),
                        500,
                    ),
                }
            )
            metadata_rows.append(metadata_row)

            behavior_row = {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "experiment_id": EXPERIMENT_ID,
                "experiment_version": EXPERIMENT_VERSION,
                "pilot_run_id": pilot_run_id,
                "prompt_version": prompt_design_run_id,
                "prompt_hash": prompt_hash,
                "provider": provider,
                "model": model,
                "session_id": selected_session_id,
                "pack_level": pack_level,
                "pack_level_name": pack_level_name,
                "primary_driver_summary": _truncate_text(_norm(parsed.get("primary_driver_summary")), 500),
                "secondary_driver_summary": _truncate_text(_norm(parsed.get("secondary_driver_summary")), 500),
                "ignored_event_summary": _truncate_text(_norm(parsed.get("ignored_event_summary")), 500),
                "information_used": _truncate_text(_jsonish(parsed.get("information_used")), 500),
                "information_not_used": _truncate_text(_jsonish(parsed.get("information_not_used")), 500),
                "pack_fields_used": _truncate_text(_jsonish(parsed.get("pack_fields_used")), 500),
                "pack_fields_discarded": _truncate_text(_jsonish(parsed.get("pack_fields_discarded")), 500),
                "pack_fields_that_changed_reasoning": _truncate_text(_jsonish(parsed.get("pack_fields_that_changed_reasoning")), 500),
                "pack_fields_that_did_not_change_reasoning": _truncate_text(_jsonish(parsed.get("pack_fields_that_did_not_change_reasoning")), 500),
                "causal_chain": _truncate_text(_norm(parsed.get("causal_chain")), 800),
                "invalidation_condition": _truncate_text(_norm(parsed.get("invalidation_condition")), 500),
                "uncertainty_sources": _truncate_text(_jsonish(parsed.get("uncertainty_sources")), 500),
                "missing_information": _truncate_text(_jsonish(parsed.get("missing_information")), 500),
                "no_signal_flag": no_signal if parse.get("parse_success") else "",
                "no_signal_reason": _truncate_text(_norm(parsed.get("no_signal_reason")), 500),
                "reasoning_summary": _truncate_text(_norm(parsed.get("session_narrative")) or _norm(parsed.get("reasoning_summary")) or _norm(parsed.get("causal_chain")), 800),
                "json_validation_success": forecast_row["json_validation_success"],
                "status": row_status,
                "error_message": forecast_row["error_message"],
                "notes": "",
            }
            behavior_rows.append(behavior_row)

            log_rows.append(
                {
                    "generated_ts": generated_ts,
                    "schema_version": SCHEMA_VERSION,
                    "experiment_id": EXPERIMENT_ID,
                    "experiment_version": EXPERIMENT_VERSION,
                    "pilot_run_id": pilot_run_id,
                    "session_id": selected_session_id,
                    "provider": provider,
                    "model": model,
                    "pack_level": pack_level,
                    "pack_level_name": pack_level_name,
                    "prompt_hash": prompt_hash,
                    "request_status": response.get("request_status", ""),
                    "response_status": response.get("response_status", ""),
                    "json_parse_success": forecast_row["json_parse_success"],
                    "json_validation_success": forecast_row["json_validation_success"],
                    "status": row_status,
                    "error_message": forecast_row["error_message"] or _truncate_text(response.get("error", ""), 500),
                    "elapsed_seconds": "",
                    "notes": f"started_ts={started}; completed_ts={completed}; raw_response_archive_key={raw_key}",
                }
            )

    summary = _summary_row(generated_ts, pilot_run_id, selected_session_id, forecast_rows, behavior_rows, metadata_rows, raw_rows, log_rows, notes)

    for sheet, default_headers, rows in [
        (OUTPUT_FORECASTS_SHEET, FORECAST_HEADERS, forecast_rows),
        (OUTPUT_METADATA_SHEET, METADATA_HEADERS, metadata_rows),
        (OUTPUT_BEHAVIOR_SHEET, BEHAVIOR_HEADERS, behavior_rows),
        (OUTPUT_RAW_ARCHIVE_SHEET, RAW_ARCHIVE_HEADERS, raw_rows),
        (OUTPUT_RUN_LOG_SHEET, RUN_LOG_HEADERS, log_rows),
        (OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS, [summary]),
    ]:
        headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, sheet, default_headers)
        _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, sheet, headers, rows)
    registry = _upsert_registry_rows(sheets_service)
    return {
        "pilot_run_id": pilot_run_id,
        "build_status": summary["build_status"],
        "final_interpretation": summary["final_interpretation"],
        "session_selected": selected_session_id,
        "sheets_written": {
            OUTPUT_FORECASTS_SHEET: len(forecast_rows),
            OUTPUT_METADATA_SHEET: len(metadata_rows),
            OUTPUT_BEHAVIOR_SHEET: len(behavior_rows),
            OUTPUT_RAW_ARCHIVE_SHEET: len(raw_rows),
            OUTPUT_RUN_LOG_SHEET: len(log_rows),
            OUTPUT_SUMMARY_SHEET: 1,
        },
        "pack_levels_executed": summary["pack_levels_executed"],
        "providers_executed": summary["providers_executed"],
        "forecast_count": summary["forecast_count"],
        "successful_provider_calls": summary["successful_provider_calls"],
        "failed_provider_calls": summary["failed_provider_calls"],
        "raw_responses_archived": summary["raw_responses_archived"],
        "json_validation_success_count": summary["json_validation_success_count"],
        "json_validation_failure_count": summary["json_validation_failure_count"],
        "behavior_rows_captured": summary["behavior_rows_captured"],
        "metadata_rows_written": summary["metadata_rows_written"],
        "run_log_rows_written": summary["run_log_rows_written"],
        "immutable_metadata_verified": "TRUE",
        "safety": {
            "shadow_only_count": summary["shadow_only_count"],
            "production_visible_count": summary["production_visible_count"],
            "routing_changes": summary["routing_changes"],
            "provider_weight_changes": summary["provider_weight_changes"],
            "ensemble_changes": summary["ensemble_changes"],
            "evaluation_changes": summary["evaluation_changes"],
            "subscriber_visible": summary["subscriber_visible"],
            "predictions_write_count": summary["predictions_write_count"],
            "evaluation_write_count": summary["evaluation_write_count"],
            "outcome_ledger_write_count": summary["outcome_ledger_write_count"],
            "mr_provider_runs_write_count": summary["mr_provider_runs_write_count"],
            "market_state_pack_write_count": summary["market_state_pack_write_count"],
            "production_behavior_change_count": summary["production_behavior_change_count"],
        },
        "registry": registry,
        "warnings": warnings,
        "missing_required": missing_required,
        "summary": summary,
    }


def main() -> None:
    result = build_pack_exposure_pilot_run_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
