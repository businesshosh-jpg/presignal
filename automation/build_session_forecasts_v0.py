import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
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
    _parse_dt,
    _sheet_to_rows,
    _write_rows,
)
from automation.build_session_information_requests_v0 import (
    MAX_LIVE_ATTEMPTS,
    NORMALIZED_EXCERPT_LIMIT,
    RAW_EXCERPT_LIMIT,
    _call_live_provider_raw,
    _candidate_json_texts,
    _information_key,
    _iso_now,
    _normalize_provider_name,
    _read_config_map,
    _resolve_provider_candidates,
    _safe_float,
    _safe_int,
    _sort_attention_rows,
    _sort_member_rows,
    _truncate_text,
)
from automation.google_clients import batch_update_values, build_script_service, build_sheets_service, default_script_id, load_credentials


PHASE1_SESSION_SHEET = "Market_Sessions"
PHASE1_MEMBER_SHEET = "Market_Session_Members"
PHASE2_MAP_SHEET = "Session_Attention_Map"
PHASE2_SUMMARY_SHEET = "Session_Attention_Summary"
PHASE3_REQUEST_SHEET = "Session_Information_Requests"
PHASE3_LIBRARY_SHEET = "Information_Requirement_Library"
PHASE3_SUMMARY_SHEET = "Session_Information_Request_Summary"

OUTPUT_FORECAST_SHEET = "Session_Forecasts"
OUTPUT_SUMMARY_SHEET = "Session_Forecast_Summary"
OUTPUT_AUDIT_SHEET = "Session_Forecast_Provider_Response_Audit"

SCHEMA_VERSION = "presignal_v2_session_forecast_0.1"
SHADOW_VERSION = "shadow_v0"
REGISTRY_CATEGORY = "PRESIGNAL_V2_MARKET_SESSION"
REGISTRY_OWNER_MODULE = "market_session"
MAX_TRANSPORT_ATTEMPTS = 2

ALLOWED_ATTENTION_LABELS = {
    "PRIMARY_DRIVER",
    "SECONDARY_DRIVER",
    "WATCHLIST",
    "CONTEXT_ONLY",
    "IGNORE",
    "NO_SIGNAL",
}
ALLOWED_FORECAST_DIRECTIONS = {"up", "down", "flat", "no_clear_direction"}
DIRECTION_NORMALIZATION_MAP = {
    "up": "up",
    "bullish": "up",
    "usd_jpy_up": "up",
    "higher": "up",
    "down": "down",
    "bearish": "down",
    "usd_jpy_down": "down",
    "lower": "down",
    "flat": "flat",
    "sideways": "flat",
    "neutral": "flat",
    "range_bound": "flat",
    "no_clear_direction": "no_clear_direction",
    "unclear": "no_clear_direction",
    "no_signal": "no_clear_direction",
}
FORBIDDEN_OUTPUT_KEYS = {
    "trade_action",
    "entry",
    "entry_price",
    "stop_loss",
    "take_profit",
    "leverage",
    "position_size",
    "risk_reward",
    "order_type",
    "buy_limit",
    "sell_limit",
    "browse_request",
    "external_browsing",
}
FORBIDDEN_OUTPUT_PHRASES = [
    "buy usdjpy",
    "sell usdjpy",
    "entry price",
    "stop loss",
    "take profit",
    "position size",
    "leverage",
    "buy limit",
    "sell limit",
    "browse the web",
    "perform a web search",
]

PROVIDER_TASK_TEXT = (
    "Make one shadow research forecast for the entire market session's USDJPY reaction. "
    "Use only the provided session/events/attention/information-requirement context. "
    "Do not browse. Do not give trading advice. Return strict JSON only."
)
PROVIDER_INSTRUCTION_TEXT = """You are creating a PreSignal v2.0 shadow research forecast.

You are given one market session, its scheduled economic events, your previously captured attention map, and your information requirements if available.

Your task is to make one session-level USDJPY reaction forecast for research evaluation later.

Forecast the whole market session, not each individual event.

You may use your own attention map to decide which events matter most.

If the session does not support a clear directional view, use:
forecast_direction = no_clear_direction
no_signal_flag = true

Allowed forecast_direction values:
up
down
flat
no_clear_direction

Important:
- Do not browse.
- Do not give trading advice.
- Do not recommend entry, stop-loss, take-profit, leverage, or position size.
- Do not write to or refer to production behavior.
- Do not assume missing information is available.
- Keep reasons concise.
- Return one valid JSON object only.
- Do not include markdown.
- Do not include explanatory text outside JSON.

Return a top-level JSON object with exactly these keys:
- object
- session_id
- provider
- forecast_direction
- forecast_confidence
- expected_move_pips_min
- expected_move_pips_max
- expected_holding_minutes
- primary_driver_summary
- secondary_driver_summary
- ignored_event_summary
- information_used
- missing_information
- session_narrative
- causal_chain
- invalidation_condition
- no_signal_flag
- no_signal_reason
- status

Set object exactly to session_forecast.
Set session_id exactly to the provided session.session_id.
Set provider to the provider name handling this request.
Set status to ok.

Do not include trade_action, entry, entry_price, stop_loss, take_profit, leverage, position_size, risk_reward, order_type, buy_limit, sell_limit, browsing requests, or any fields not listed above."""

FORECAST_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "forecast_run_id",
    "session_id",
    "session_date",
    "country",
    "session_window_name",
    "provider",
    "model",
    "forecast_direction",
    "forecast_confidence",
    "expected_move_pips_min",
    "expected_move_pips_max",
    "expected_holding_minutes",
    "primary_driver_summary",
    "secondary_driver_summary",
    "ignored_event_summary",
    "information_used",
    "missing_information",
    "session_narrative",
    "causal_chain",
    "invalidation_condition",
    "no_signal_flag",
    "no_signal_reason",
    "attention_primary_event_ids",
    "attention_secondary_event_ids",
    "attention_watchlist_event_ids",
    "attention_context_event_ids",
    "information_requirements_available",
    "information_requirement_keys_used",
    "market_state_pack_used",
    "raw_output",
    "status",
    "error_message",
    "source_session_sheet",
    "source_member_sheet",
    "source_attention_sheet",
    "source_information_sheet",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "forecast_run_id",
    "build_status",
    "final_interpretation",
    "sessions_read",
    "sessions_processed",
    "providers_attempted",
    "providers_succeeded",
    "providers_failed",
    "forecast_rows_written",
    "up_count",
    "down_count",
    "flat_count",
    "no_clear_direction_count",
    "no_signal_count",
    "invalid_direction_count",
    "provider_parse_error_count",
    "provider_contract_error_count",
    "provider_retry_count",
    "provider_recovery_success_count",
    "provider_recovery_failed_count",
    "provider_response_audit_rows_written",
    "provider_transport_error_count",
    "provider_transport_retry_count",
    "provider_transport_retry_success_count",
    "provider_transport_retry_exhausted_count",
    "registry_updated",
    "governance_status",
    "notes",
]

AUDIT_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "forecast_run_id",
    "session_id",
    "provider",
    "model",
    "attempt_number",
    "request_status",
    "response_status",
    "parse_status",
    "contract_status",
    "recovery_status",
    "retry_status",
    "raw_response_excerpt",
    "normalized_json_excerpt",
    "error_type",
    "error_message",
    "response_char_count",
    "forbidden_field_detected",
    "invalid_direction_count",
    "forecast_item_count",
    "provider_field_recovered_from_context",
    "object_field_recovered_from_context",
    "inner_item_candidate_rejected",
    "notes",
]


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _as_bool(value: Any) -> bool:
    return _upper(value) in {"TRUE", "T", "YES", "Y", "1"}


def _forecast_run_id(generated_ts: str) -> str:
    stamp = generated_ts.replace("-", "").replace(":", "").replace("+00:00", "Z").replace(".", "")
    return f"session_forecast_v0_{stamp}"


def _require_headers(sheet_name: str, rows: Sequence[Dict[str, Any]], headers: Sequence[str]) -> None:
    if not rows:
        raise RuntimeError(f"{sheet_name} is missing or empty.")
    missing = [header for header in headers if header not in rows[0]]
    if missing:
        raise RuntimeError(f"{sheet_name} is missing required headers: {', '.join(missing)}")


def _require_headers_if_rows_exist(sheet_name: str, rows: Sequence[Dict[str, Any]], headers: Sequence[str]) -> None:
    if not rows:
        return
    missing = [header for header in headers if header not in rows[0]]
    if missing:
        raise RuntimeError(f"{sheet_name} is missing required headers: {', '.join(missing)}")


def _attention_ready(summary_row: Dict[str, Any]) -> bool:
    return _upper(summary_row.get("final_interpretation")) == "SESSION_ATTENTION_CAPTURE_READY" or _upper(
        summary_row.get("build_status")
    ) == "PASS"


def _information_usable(summary_row: Dict[str, Any]) -> bool:
    final_interpretation = _upper(summary_row.get("final_interpretation"))
    build_status = _upper(summary_row.get("build_status"))
    return final_interpretation in {
        "SESSION_INFORMATION_REQUEST_CAPTURE_READY",
        "SESSION_INFORMATION_REQUEST_CAPTURE_NEEDS_REVIEW",
    } or build_status in {"PASS", "PASS_WITH_WARNINGS"}


def _sort_information_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = list(rows)
    out.sort(
        key=lambda row: (
            _norm(row.get("session_id")),
            _norm(row.get("provider")),
            _safe_int(row.get("request_rank")) or 999999,
            _norm(row.get("requested_information")),
        )
    )
    return out


def _sort_library_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = list(rows)
    out.sort(key=lambda row: (_norm(row.get("information_key")), _norm(row.get("canonical_information"))))
    return out


def _validate_inputs(
    session_rows: Sequence[Dict[str, Any]],
    member_rows: Sequence[Dict[str, Any]],
    attention_rows: Sequence[Dict[str, Any]],
    attention_summary_rows: Sequence[Dict[str, Any]],
    information_rows: Sequence[Dict[str, Any]],
    library_rows: Sequence[Dict[str, Any]],
    information_summary_rows: Sequence[Dict[str, Any]],
) -> Tuple[
    Dict[str, Any],
    Dict[str, Any],
    List[Dict[str, Any]],
    Dict[str, List[Dict[str, Any]]],
    Dict[Tuple[str, str], List[Dict[str, Any]]],
    Dict[Tuple[str, str], List[Dict[str, Any]]],
    List[Dict[str, Any]],
]:
    _require_headers(
        PHASE1_SESSION_SHEET,
        session_rows,
        ["session_id", "session_date", "country", "session_window_name", "session_start_ts", "session_end_ts"],
    )
    _require_headers(
        PHASE1_MEMBER_SHEET,
        member_rows,
        [
            "session_id",
            "country",
            "session_window_name",
            "event_id",
            "batch_id",
            "type",
            "indicator_name",
            "genre",
            "importance",
            "release_ts",
            "consensus_value",
            "prev_revision",
            "member_order",
        ],
    )
    _require_headers(
        PHASE2_MAP_SHEET,
        attention_rows,
        [
            "session_id",
            "provider",
            "event_id",
            "attention_label",
            "attention_rank",
            "attention_reason",
            "expected_market_channel",
            "driver_role",
        ],
    )
    _require_headers(PHASE2_SUMMARY_SHEET, attention_summary_rows, ["build_status", "final_interpretation"])
    _require_headers(PHASE3_SUMMARY_SHEET, information_summary_rows, ["build_status", "final_interpretation"])
    _require_headers_if_rows_exist(
        PHASE3_REQUEST_SHEET,
        information_rows,
        [
            "session_id",
            "provider",
            "request_rank",
            "requested_information",
            "information_category",
            "priority",
            "reason",
            "available_now",
            "is_market_state_candidate",
        ],
    )
    _require_headers_if_rows_exist(
        PHASE3_LIBRARY_SHEET,
        library_rows,
        ["information_key", "canonical_information", "information_category", "priority_avg", "request_count"],
    )

    attention_summary_row = attention_summary_rows[0]
    if not _attention_ready(attention_summary_row):
        raise RuntimeError(
            f"{PHASE2_SUMMARY_SHEET} is not ready: "
            f"build_status={_norm(attention_summary_row.get('build_status'))}, "
            f"final_interpretation={_norm(attention_summary_row.get('final_interpretation'))}"
        )

    information_summary_row = information_summary_rows[0]
    if not _information_usable(information_summary_row):
        raise RuntimeError(
            f"{PHASE3_SUMMARY_SHEET} is not usable: "
            f"build_status={_norm(information_summary_row.get('build_status'))}, "
            f"final_interpretation={_norm(information_summary_row.get('final_interpretation'))}"
        )

    session_map = {_norm(row.get("session_id")): row for row in session_rows if _norm(row.get("session_id"))}
    members_by_session: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in _sort_member_rows(member_rows):
        session_id = _norm(row.get("session_id"))
        if session_id:
            members_by_session[session_id].append(row)

    valid_sessions: List[Dict[str, Any]] = []
    for session_id in sorted(session_map):
        session_row = session_map[session_id]
        members = members_by_session.get(session_id, [])
        if not members:
            continue
        expected_count = _safe_int(session_row.get("member_event_count"))
        if expected_count and expected_count != len(members):
            continue
        valid_sessions.append(session_row)

    if not valid_sessions:
        raise RuntimeError("No structurally valid market sessions were found for forecast capture.")

    attention_by_pair: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in _sort_attention_rows(attention_rows):
        session_id = _norm(row.get("session_id"))
        provider = _normalize_provider_name(row.get("provider"))
        if session_id and provider:
            attention_by_pair[(session_id, provider)].append(row)

    information_by_pair: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in _sort_information_rows(information_rows):
        session_id = _norm(row.get("session_id"))
        provider = _normalize_provider_name(row.get("provider"))
        if session_id and provider:
            information_by_pair[(session_id, provider)].append(row)

    return (
        attention_summary_row,
        information_summary_row,
        valid_sessions,
        members_by_session,
        attention_by_pair,
        information_by_pair,
        _sort_library_rows(library_rows),
    )


def _build_provider_instruction() -> str:
    return PROVIDER_INSTRUCTION_TEXT


def _build_information_payload_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "information_key": _information_key(
                    _norm(row.get("information_category")),
                    _norm(row.get("requested_information")),
                ),
                "request_rank": _safe_int(row.get("request_rank")) or "",
                "requested_information": _norm(row.get("requested_information")),
                "information_category": _norm(row.get("information_category")),
                "priority": _norm(row.get("priority")),
                "reason": _norm(row.get("reason")),
                "available_now": _norm(row.get("available_now")),
                "is_market_state_candidate": _as_bool(row.get("is_market_state_candidate")),
            }
        )
    return out


def _build_library_payload_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "information_key": _norm(row.get("information_key")),
                "canonical_information": _norm(row.get("canonical_information")),
                "information_category": _norm(row.get("information_category")),
                "priority_avg": _norm(row.get("priority_avg")),
                "request_count": _safe_int(row.get("request_count")),
                "provider_count": _safe_int(row.get("provider_count")),
                "promotion_status": _norm(row.get("promotion_status")),
            }
        )
    return out


def _build_payload(
    session_row: Dict[str, Any],
    member_rows: Sequence[Dict[str, Any]],
    attention_rows: Sequence[Dict[str, Any]],
    information_rows: Sequence[Dict[str, Any]],
    library_rows: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "object": "presignal_v2_session_forecast_task",
        "schema_version": SCHEMA_VERSION,
        "session": {
            "session_id": _norm(session_row.get("session_id")),
            "country": _norm(session_row.get("country")),
            "session_window_name": _norm(session_row.get("session_window_name")),
            "session_start_ts": _norm(session_row.get("session_start_ts")),
            "session_end_ts": _norm(session_row.get("session_end_ts")),
        },
        "events": [
            {
                "event_id": _norm(row.get("event_id")),
                "batch_id": _norm(row.get("batch_id")),
                "type": _norm(row.get("type")),
                "indicator_name": _norm(row.get("indicator_name")),
                "genre": _norm(row.get("genre")),
                "importance": _norm(row.get("importance")),
                "release_ts": _norm(row.get("release_ts")),
                "consensus_value": _norm(row.get("consensus_value")),
                "prev_revision": _norm(row.get("prev_revision")),
                "member_order": _safe_int(row.get("member_order")),
            }
            for row in member_rows
        ],
        "provider_attention_map": [
            {
                "event_id": _norm(row.get("event_id")),
                "attention_label": _upper(row.get("attention_label")),
                "attention_rank": _safe_int(row.get("attention_rank")) or "",
                "attention_reason": _norm(row.get("attention_reason")),
                "expected_market_channel": _norm(row.get("expected_market_channel")),
                "driver_role": _norm(row.get("driver_role")),
            }
            for row in attention_rows
        ],
        "provider_information_requirements": _build_information_payload_rows(information_rows),
        "shared_information_requirement_library": _build_library_payload_rows(library_rows),
        "task": PROVIDER_TASK_TEXT,
    }


def _build_provider_prompt(provider_request: Dict[str, Any]) -> Dict[str, str]:
    provider_name = provider_request["provider"]
    return {
        "system": (
            "You are a macroeconomic research model. "
            "Output must be strict JSON only, with no markdown, no code fences, and no prose outside the JSON object. "
            f'The top-level JSON field "provider" must be exactly "{provider_name}". '
            "Do not substitute generic labels, role names, or workflow names."
        ),
        "user": json.dumps(provider_request["payload"], ensure_ascii=True),
        "instruction": (
            provider_request["instruction"]
            + "\n\n"
            + f'Return the top-level field "provider" exactly as "{provider_name}". '
            "Do not return generic values such as macroeconomic_research_model, macro_research_model, "
            "economic_research_model, or workflow labels."
        ),
        "cache_scaffold": "",
    }


def _build_provider_requests(
    session_rows: Sequence[Dict[str, Any]],
    members_by_session: Dict[str, List[Dict[str, Any]]],
    attention_by_pair: Dict[Tuple[str, str], List[Dict[str, Any]]],
    information_by_pair: Dict[Tuple[str, str], List[Dict[str, Any]]],
    library_rows: Sequence[Dict[str, Any]],
    providers: Sequence[Dict[str, str]],
) -> List[Dict[str, Any]]:
    requests: List[Dict[str, Any]] = []
    instruction = _build_provider_instruction()
    for session_row in sorted(session_rows, key=lambda row: _norm(row.get("session_id"))):
        session_id = _norm(session_row.get("session_id"))
        member_rows = members_by_session.get(session_id, [])
        for provider in providers:
            provider_name = provider["provider"]
            attention_rows = attention_by_pair.get((session_id, provider_name), [])
            information_rows = information_by_pair.get((session_id, provider_name), [])
            payload = _build_payload(
                session_row,
                member_rows,
                attention_rows,
                information_rows,
                library_rows,
            )
            payload["provider_context"] = {
                "provider": provider_name,
                "model": provider["model"],
                "return_provider_field_exactly": provider_name,
            }
            requests.append(
                {
                    "session_id": session_id,
                    "provider": provider_name,
                    "model": provider["model"],
                    "instruction": instruction,
                    "payload": payload,
                }
            )
    requests.sort(key=lambda item: (_norm(item["session_id"]), _norm(item["provider"]), _norm(item["model"])))
    return requests


def _find_forbidden_output_paths(value: Any, path: str = "$") -> List[str]:
    hits: List[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_norm = _norm(key).lower()
            if key_norm in FORBIDDEN_OUTPUT_KEYS:
                hits.append(f"{path}.{key}")
            hits.extend(_find_forbidden_output_paths(nested, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            hits.extend(_find_forbidden_output_paths(nested, f"{path}[{index}]"))
    elif isinstance(value, str):
        lowered = value.lower()
        for phrase in FORBIDDEN_OUTPUT_PHRASES:
            if phrase in lowered:
                hits.append(f"{path} contains '{phrase}'")
    return hits


def _empty_metrics() -> Dict[str, int]:
    return {
        "invalid_direction_count": 0,
        "provider_parse_error_count": 0,
        "provider_contract_error_count": 0,
        "provider_retry_count": 0,
        "provider_recovery_success_count": 0,
        "provider_recovery_failed_count": 0,
        "provider_response_audit_rows_written": 0,
        "provider_transport_error_count": 0,
        "provider_transport_retry_count": 0,
        "provider_transport_retry_success_count": 0,
        "provider_transport_retry_exhausted_count": 0,
    }


def _is_transient_transport_error(response_status: str, error_message: str) -> bool:
    status = _norm(response_status).lower()
    message = _norm(error_message).lower()
    haystack = f"{status} {message}"
    transient_terms = (
        "503",
        "502",
        "504",
        "rate_limit",
        "temporarily_unavailable",
        "service_unavailable",
        "deadline_exceeded",
        "timeout",
        "timed out",
        "connection reset",
        "empty response",
        "empty content",
    )
    return any(term in haystack for term in transient_terms)


def _looks_like_forecast_envelope(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    if _norm(obj.get("object")) != "session_forecast":
        return False
    return _norm(obj.get("forecast_direction")) != ""


def _is_inner_forecast_candidate(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    if "object" in obj or "session_id" in obj:
        return False
    inner_keys = {
        "forecast_direction",
        "forecast_confidence",
        "session_narrative",
        "causal_chain",
    }
    return "forecast_direction" in obj and inner_keys.intersection(set(obj.keys())) == inner_keys


def _recover_json_payload(raw_output: Any) -> Dict[str, Any]:
    raw_text = str(raw_output or "")
    if not raw_text.strip():
        return {
            "ok": False,
            "parsed_value": None,
            "normalized_json_text": "",
            "parse_status": "empty_response",
            "recovery_status": "not_attempted",
            "recovery_attempted": False,
            "error_type": "empty_response",
            "error_message": "provider returned empty response",
        }

    candidates = _candidate_json_texts(raw_text)
    if not candidates:
        return {
            "ok": False,
            "parsed_value": None,
            "normalized_json_text": "",
            "parse_status": "parse_error",
            "recovery_status": "recovery_failed",
            "recovery_attempted": False,
            "error_type": "parse_error",
            "error_message": "no parseable JSON candidates could be derived from provider output",
        }

    last_error = "unknown parse failure"
    rejected_inner_item_candidate = False
    for method, candidate in candidates:
        try:
            parsed_value = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = f"{exc.msg} (line {exc.lineno}, column {exc.colno})"
            continue

        if isinstance(parsed_value, str):
            inner_text = str(parsed_value or "").strip()
            for inner_method, inner_candidate in _candidate_json_texts(inner_text):
                try:
                    inner_value = json.loads(inner_candidate)
                except json.JSONDecodeError as exc:
                    last_error = f"{exc.msg} (line {exc.lineno}, column {exc.colno})"
                    continue
                if isinstance(inner_value, dict):
                    if _is_inner_forecast_candidate(inner_value):
                        rejected_inner_item_candidate = True
                        last_error = (
                            "extracted JSON candidate was an inner forecast object, "
                            "not a top-level provider response"
                        )
                        continue
                    if not _looks_like_forecast_envelope(inner_value):
                        last_error = "recovered JSON candidate did not match top-level forecast envelope shape"
                        continue
                return {
                    "ok": True,
                    "parsed_value": inner_value,
                    "normalized_json_text": inner_candidate,
                    "parse_status": "parsed_recovered",
                    "recovery_status": f"{method}+quoted_json_string+{inner_method}",
                    "recovery_attempted": True,
                    "error_type": "",
                    "error_message": "",
                }
            continue

        if isinstance(parsed_value, dict):
            if _is_inner_forecast_candidate(parsed_value):
                rejected_inner_item_candidate = True
                last_error = (
                    "extracted JSON candidate was an inner forecast object, "
                    "not a top-level provider response"
                )
                continue
            if not _looks_like_forecast_envelope(parsed_value):
                last_error = "recovered JSON candidate did not match top-level forecast envelope shape"
                continue

        return {
            "ok": True,
            "parsed_value": parsed_value,
            "normalized_json_text": candidate,
            "parse_status": "parsed_as_is" if method == "as_is" else "parsed_recovered",
            "recovery_status": "not_needed" if method == "as_is" else method,
            "recovery_attempted": method != "as_is",
            "error_type": "",
            "error_message": "",
        }

    return {
        "ok": False,
        "parsed_value": None,
        "normalized_json_text": "",
        "parse_status": "parse_error",
        "recovery_status": (
            "rejected_inner_item_candidate"
            if rejected_inner_item_candidate
            else "recovery_failed" if len(candidates) > 1 else "not_needed"
        ),
        "recovery_attempted": len(candidates) > 1,
        "error_type": "recovery_candidate_not_envelope" if rejected_inner_item_candidate else "parse_error",
        "error_message": last_error,
    }


def _normalize_forecast_direction(value: Any) -> Tuple[str, bool]:
    raw = _norm(value).lower().replace("-", "_").replace(" ", "_")
    if raw in ALLOWED_FORECAST_DIRECTIONS:
        return raw, False
    normalized = DIRECTION_NORMALIZATION_MAP.get(raw)
    if normalized:
        return normalized, normalized != raw
    return "no_clear_direction", True


def _normalize_confidence(value: Any) -> Tuple[Any, bool]:
    raw = _norm(value)
    if not raw:
        return "", False
    cleaned = raw.rstrip("%")
    num = _safe_float(cleaned)
    if num is None:
        return "", True
    if raw.endswith("%") or num > 1:
        if 0 <= num <= 100:
            num = num / 100.0
        else:
            return "", True
    if num < 0 or num > 1:
        return "", True
    return round(num, 4), False


def _normalize_numeric_value(value: Any) -> Tuple[Any, bool]:
    raw = _norm(value)
    if not raw:
        return "", False
    cleaned = raw.replace(",", "")
    num = _safe_float(cleaned)
    if num is None:
        return "", True
    if float(num).is_integer():
        return int(num), False
    return round(num, 4), False


def _normalize_holding_minutes(value: Any) -> Tuple[Any, bool]:
    num, invalid = _normalize_numeric_value(value)
    if num == "":
        return "", invalid
    try:
        int_value = int(float(num))
    except Exception:
        return "", True
    if int_value < 0:
        return "", True
    return int_value, False


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


def _join_attention_event_ids(attention_rows: Sequence[Dict[str, Any]], label: str) -> str:
    rows = [row for row in attention_rows if _upper(row.get("attention_label")) == label]
    rows.sort(
        key=lambda row: (
            _safe_int(row.get("attention_rank")) or 999999,
            _parse_dt(row.get("release_ts")) or datetime.max.replace(tzinfo=timezone.utc),
            _norm(row.get("event_id")),
        )
    )
    return _join_unique(row.get("event_id") for row in rows)


def _provider_information_keys(rows: Sequence[Dict[str, Any]]) -> str:
    keys: List[str] = []
    seen = set()
    for row in rows:
        key = _information_key(_norm(row.get("information_category")), _norm(row.get("requested_information")))
        if key not in seen:
            seen.add(key)
            keys.append(key)
    return "|".join(keys)


def _base_forecast_row(
    generated_ts: str,
    run_id: str,
    session_row: Dict[str, Any],
    provider: str,
    model: str,
    raw_output: str,
    attention_rows: Sequence[Dict[str, Any]],
    information_rows: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "shadow_version": SHADOW_VERSION,
        "forecast_run_id": run_id,
        "session_id": _norm(session_row.get("session_id")),
        "session_date": _norm(session_row.get("session_date")),
        "country": _norm(session_row.get("country")),
        "session_window_name": _norm(session_row.get("session_window_name")),
        "provider": provider,
        "model": model,
        "forecast_direction": "",
        "forecast_confidence": "",
        "expected_move_pips_min": "",
        "expected_move_pips_max": "",
        "expected_holding_minutes": "",
        "primary_driver_summary": "",
        "secondary_driver_summary": "",
        "ignored_event_summary": "",
        "information_used": "",
        "missing_information": "",
        "session_narrative": "",
        "causal_chain": "",
        "invalidation_condition": "",
        "no_signal_flag": "FALSE",
        "no_signal_reason": "",
        "attention_primary_event_ids": _join_attention_event_ids(attention_rows, "PRIMARY_DRIVER"),
        "attention_secondary_event_ids": _join_attention_event_ids(attention_rows, "SECONDARY_DRIVER"),
        "attention_watchlist_event_ids": _join_attention_event_ids(attention_rows, "WATCHLIST"),
        "attention_context_event_ids": _join_attention_event_ids(attention_rows, "CONTEXT_ONLY"),
        "information_requirements_available": "TRUE" if information_rows else "FALSE",
        "information_requirement_keys_used": _provider_information_keys(information_rows),
        "market_state_pack_used": "FALSE",
        "raw_output": raw_output,
        "status": "",
        "error_message": "",
        "source_session_sheet": PHASE1_SESSION_SHEET,
        "source_member_sheet": PHASE1_MEMBER_SHEET,
        "source_attention_sheet": PHASE2_MAP_SHEET,
        "source_information_sheet": PHASE3_REQUEST_SHEET,
        "notes": "",
    }


def _sort_forecast_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = list(rows)
    out.sort(key=lambda row: (_norm(row.get("session_id")), _norm(row.get("provider"))))
    return out


def _failure_result(
    metrics: Dict[str, int],
    parse_status: str,
    contract_status: str,
    recovery_status: str,
    normalized_json_text: str,
    error_type: str,
    error_message: str,
    retryable: bool,
    forbidden_field_detected: str = "FALSE",
    inner_item_candidate_rejected: str = "FALSE",
) -> Dict[str, Any]:
    return {
        "success": False,
        "rows": [],
        "metrics": metrics,
        "parse_status": parse_status,
        "contract_status": contract_status,
        "recovery_status": recovery_status,
        "normalized_json_text": normalized_json_text,
        "error_type": error_type,
        "error_message": error_message,
        "retryable": retryable,
        "forbidden_field_detected": forbidden_field_detected,
        "provider_field_recovered_from_context": "FALSE",
        "object_field_recovered_from_context": "FALSE",
        "inner_item_candidate_rejected": inner_item_candidate_rejected,
    }


def _build_transport_failure_result(response_status: str, error_message: str) -> Dict[str, Any]:
    metrics = _empty_metrics()
    lowered = error_message.lower()
    transient_transport_error = _is_transient_transport_error(response_status, error_message)
    error_type = "transient_provider_error" if transient_transport_error else "transport_error"
    parse_status = "not_attempted"
    contract_status = response_status or "transport_error"
    retryable = transient_transport_error
    metrics["provider_transport_error_count"] = 1
    if "empty content" in lowered or "empty response" in lowered:
        error_type = "empty_response"
        parse_status = "empty_response"
        contract_status = "not_evaluated"
        retryable = True
        metrics["provider_parse_error_count"] = 1
    return _failure_result(
        metrics,
        parse_status,
        contract_status,
        "not_attempted",
        "",
        error_type,
        error_message,
        retryable,
    )


def _parse_provider_output(
    generated_ts: str,
    run_id: str,
    session_row: Dict[str, Any],
    provider: str,
    model: str,
    raw_output: str,
    attention_rows: Sequence[Dict[str, Any]],
    information_rows: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    metrics = _empty_metrics()
    recovery = _recover_json_payload(raw_output)
    if recovery["ok"] and recovery["recovery_status"] != "not_needed":
        metrics["provider_recovery_success_count"] = 1
    elif not recovery["ok"] and recovery["recovery_attempted"]:
        metrics["provider_recovery_failed_count"] = 1

    session_id = _norm(session_row.get("session_id"))
    if not recovery["ok"]:
        metrics["provider_parse_error_count"] = 1
        contract_status = "recovery_candidate_not_envelope" if recovery["error_type"] == "recovery_candidate_not_envelope" else "not_evaluated"
        return _failure_result(
            metrics,
            recovery["parse_status"],
            contract_status,
            recovery["recovery_status"],
            "",
            recovery["error_type"],
            recovery["error_message"],
            True,
            inner_item_candidate_rejected="TRUE" if recovery["error_type"] == "recovery_candidate_not_envelope" else "FALSE",
        )

    parsed = recovery["parsed_value"]
    normalized_json_text = recovery["normalized_json_text"]
    if not isinstance(parsed, dict):
        metrics["provider_contract_error_count"] = 1
        return _failure_result(
            metrics,
            recovery["parse_status"],
            "top_level_not_object",
            recovery["recovery_status"],
            normalized_json_text,
            "contract_error",
            "provider output must be a top-level JSON object",
            True,
        )

    forbidden_hits = _find_forbidden_output_paths(parsed)
    if forbidden_hits:
        metrics["provider_contract_error_count"] = 1
        return _failure_result(
            metrics,
            recovery["parse_status"],
            "forbidden_field_detected",
            recovery["recovery_status"],
            normalized_json_text,
            "forbidden_field_detected",
            f"forbidden_output_detected: {', '.join(forbidden_hits[:5])}",
            False,
            forbidden_field_detected="TRUE",
        )

    provider_field = _norm(parsed.get("provider"))
    provider_field_recovered_from_context = False
    if not provider_field:
        provider_field = provider
        provider_field_recovered_from_context = True
    elif _normalize_provider_name(provider_field) != provider:
        metrics["provider_contract_error_count"] = 1
        return _failure_result(
            metrics,
            recovery["parse_status"],
            "provider_mismatch",
            recovery["recovery_status"],
            normalized_json_text,
            "contract_error",
            f"provider_mismatch expected={provider} got={provider_field}",
            False,
        )

    object_field = _norm(parsed.get("object"))
    if object_field != "session_forecast":
        metrics["provider_contract_error_count"] = 1
        return _failure_result(
            metrics,
            recovery["parse_status"],
            "invalid_object",
            recovery["recovery_status"],
            normalized_json_text,
            "contract_error",
            f"invalid_object={object_field or '<blank>'}",
            False,
        )

    session_id_field = _norm(parsed.get("session_id"))
    if not session_id_field:
        session_id_field = session_id
    if session_id_field != session_id:
        metrics["provider_contract_error_count"] = 1
        return _failure_result(
            metrics,
            recovery["parse_status"],
            "session_id_mismatch",
            recovery["recovery_status"],
            normalized_json_text,
            "contract_error",
            f"session_id_mismatch expected={session_id or '<blank>'} got={_norm(parsed.get('session_id')) or '<blank>'}",
            False,
        )

    direction, invalid_direction = _normalize_forecast_direction(parsed.get("forecast_direction"))
    if invalid_direction:
        metrics["invalid_direction_count"] += 1

    confidence, invalid_confidence = _normalize_confidence(parsed.get("forecast_confidence"))
    move_min, invalid_move_min = _normalize_numeric_value(parsed.get("expected_move_pips_min"))
    move_max, invalid_move_max = _normalize_numeric_value(parsed.get("expected_move_pips_max"))
    holding_minutes, invalid_holding = _normalize_holding_minutes(parsed.get("expected_holding_minutes"))

    notes: List[str] = []
    if invalid_confidence:
        notes.append("forecast_confidence_invalid_cleared=TRUE")
    if invalid_move_min:
        notes.append("expected_move_pips_min_invalid_cleared=TRUE")
    if invalid_move_max:
        notes.append("expected_move_pips_max_invalid_cleared=TRUE")
    if invalid_holding:
        notes.append("expected_holding_minutes_invalid_cleared=TRUE")
    if move_min != "" and move_max != "" and float(move_min) > float(move_max):
        move_min, move_max = move_max, move_min
        notes.append("expected_move_range_swapped=TRUE")

    no_signal_raw = _as_bool(parsed.get("no_signal_flag"))
    no_signal_reason = _truncate_text(_norm(parsed.get("no_signal_reason")), 200)
    no_signal_flag = "TRUE" if direction == "no_clear_direction" or no_signal_raw else "FALSE"
    if direction == "no_clear_direction" and not no_signal_reason and invalid_direction:
        no_signal_reason = "invalid forecast_direction normalized to no_clear_direction"

    row = _base_forecast_row(
        generated_ts,
        run_id,
        session_row,
        provider,
        model,
        raw_output,
        attention_rows,
        information_rows,
    )
    row.update(
        {
            "forecast_direction": direction,
            "forecast_confidence": confidence,
            "expected_move_pips_min": move_min,
            "expected_move_pips_max": move_max,
            "expected_holding_minutes": holding_minutes,
            "primary_driver_summary": _truncate_text(_norm(parsed.get("primary_driver_summary")), 240),
            "secondary_driver_summary": _truncate_text(_norm(parsed.get("secondary_driver_summary")), 240),
            "ignored_event_summary": _truncate_text(_norm(parsed.get("ignored_event_summary")), 240),
            "information_used": _truncate_text(_norm(parsed.get("information_used")), 320),
            "missing_information": _truncate_text(_norm(parsed.get("missing_information")), 320),
            "session_narrative": _truncate_text(_norm(parsed.get("session_narrative")), 500),
            "causal_chain": _truncate_text(_norm(parsed.get("causal_chain")), 320),
            "invalidation_condition": _truncate_text(_norm(parsed.get("invalidation_condition")), 240),
            "no_signal_flag": no_signal_flag,
            "no_signal_reason": no_signal_reason,
            "status": "invalid_direction_normalized" if invalid_direction else "parsed",
            "notes": "; ".join(notes),
        }
    )

    return {
        "success": True,
        "rows": [row],
        "metrics": metrics,
        "parse_status": recovery["parse_status"],
        "contract_status": "valid",
        "recovery_status": recovery["recovery_status"],
        "normalized_json_text": normalized_json_text,
        "error_type": "",
        "error_message": "",
        "retryable": False,
        "forbidden_field_detected": "FALSE",
        "provider_field_recovered_from_context": "TRUE" if provider_field_recovered_from_context else "FALSE",
        "object_field_recovered_from_context": "FALSE",
        "inner_item_candidate_rejected": "FALSE",
    }


def _build_provider_response_audit_row(
    generated_ts: str,
    run_id: str,
    session_id: str,
    provider: str,
    model: str,
    attempt_number: int,
    request_status: str,
    response_status: str,
    parse_result: Dict[str, Any],
    retry_status: str,
    raw_output: str,
) -> Dict[str, Any]:
    metrics = parse_result.get("metrics", {})
    notes = (
        f"success={parse_result.get('success', False)}; "
        f"parse_status={parse_result.get('parse_status', '')}; "
        f"contract_status={parse_result.get('contract_status', '')}"
    )
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "shadow_version": SHADOW_VERSION,
        "forecast_run_id": run_id,
        "session_id": session_id,
        "provider": provider,
        "model": model,
        "attempt_number": attempt_number,
        "request_status": request_status,
        "response_status": response_status,
        "parse_status": parse_result.get("parse_status", ""),
        "contract_status": parse_result.get("contract_status", ""),
        "recovery_status": parse_result.get("recovery_status", ""),
        "retry_status": retry_status,
        "raw_response_excerpt": _truncate_text(raw_output, RAW_EXCERPT_LIMIT),
        "normalized_json_excerpt": _truncate_text(parse_result.get("normalized_json_text", ""), NORMALIZED_EXCERPT_LIMIT),
        "error_type": parse_result.get("error_type", ""),
        "error_message": _truncate_text(parse_result.get("error_message", ""), 500),
        "response_char_count": len(raw_output or ""),
        "forbidden_field_detected": parse_result.get("forbidden_field_detected", "FALSE"),
        "invalid_direction_count": metrics.get("invalid_direction_count", 0),
        "forecast_item_count": len(parse_result.get("rows", [])),
        "provider_field_recovered_from_context": parse_result.get("provider_field_recovered_from_context", "FALSE"),
        "object_field_recovered_from_context": parse_result.get("object_field_recovered_from_context", "FALSE"),
        "inner_item_candidate_rejected": parse_result.get("inner_item_candidate_rejected", "FALSE"),
        "notes": _truncate_text(notes, 400),
    }


def _run_live_contracts(
    generated_ts: str,
    run_id: str,
    valid_sessions: Sequence[Dict[str, Any]],
    members_by_session: Dict[str, List[Dict[str, Any]]],
    attention_by_pair: Dict[Tuple[str, str], List[Dict[str, Any]]],
    information_by_pair: Dict[Tuple[str, str], List[Dict[str, Any]]],
    provider_requests: Sequence[Dict[str, Any]],
    script_service,
    script_id: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, int], List[Dict[str, Any]]]:
    rows: List[Dict[str, Any]] = []
    audit_rows: List[Dict[str, Any]] = []
    metrics = Counter(_empty_metrics())
    provider_results: List[Dict[str, Any]] = []
    session_lookup = {_norm(row.get("session_id")): row for row in valid_sessions}

    for request in provider_requests:
        session_id = request["session_id"]
        provider = request["provider"]
        model = request["model"]
        session_row = session_lookup[session_id]
        attention_rows = attention_by_pair.get((session_id, provider), [])
        information_rows = information_by_pair.get((session_id, provider), [])

        final_result: Optional[Dict[str, Any]] = None
        final_model = model
        attempt_count = 0

        had_transient_retry = False
        for attempt_number in range(1, MAX_TRANSPORT_ATTEMPTS + 1):
            attempt_count = attempt_number
            provider_response = _call_live_provider_raw(script_service, script_id, request)
            final_model = provider_response.get("model") or final_model
            raw_output = provider_response.get("raw_output", "")

            if provider_response.get("status") == "ok":
                parse_result = _parse_provider_output(
                    generated_ts,
                    run_id,
                    session_row,
                    provider,
                    final_model,
                    raw_output,
                    attention_rows,
                    information_rows,
                )
            else:
                parse_result = _build_transport_failure_result(
                    provider_response.get("response_status", "error"),
                    provider_response.get("error") or "provider_call_failed",
                )

            should_retry = (
                not parse_result["success"]
                and parse_result.get("retryable", False)
                and attempt_number < MAX_TRANSPORT_ATTEMPTS
            )
            if should_retry:
                metrics["provider_retry_count"] += 1
                metrics["provider_transport_retry_count"] += 1
                had_transient_retry = True
                retry_status = "retry_scheduled"
            elif parse_result["success"] and attempt_number > 1:
                if had_transient_retry:
                    metrics["provider_transport_retry_success_count"] += 1
                retry_status = "retry_succeeded"
            elif parse_result["success"]:
                retry_status = "not_retried_success"
            elif attempt_number > 1:
                if had_transient_retry:
                    metrics["provider_transport_retry_exhausted_count"] += 1
                retry_status = "retry_exhausted"
            else:
                retry_status = "not_retried_non_retryable"

            audit_rows.append(
                _build_provider_response_audit_row(
                    generated_ts,
                    run_id,
                    session_id,
                    provider,
                    final_model,
                    attempt_number,
                    provider_response.get("request_status", "attempted"),
                    provider_response.get("response_status", provider_response.get("status", "error")),
                    parse_result,
                    retry_status,
                    raw_output,
                )
            )

            for key, value in parse_result["metrics"].items():
                metrics[key] += value

            final_result = parse_result
            if not should_retry:
                break

        if final_result is None:
            raise RuntimeError(f"Provider loop produced no result for {provider} / {session_id}")

        rows.extend(final_result["rows"])
        provider_results.append(
            {
                "session_id": session_id,
                "provider": provider,
                "model": final_model,
                "success": final_result["success"],
                "error_message": final_result["error_message"],
                "rows_generated": len(final_result["rows"]),
                "attempt_count": attempt_count,
            }
        )

    metrics["provider_response_audit_rows_written"] = len(audit_rows)
    return _sort_forecast_rows(rows), audit_rows, dict(metrics), provider_results


def _upsert_registry_rows(service) -> Dict[str, Any]:
    headers = _ensure_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_upper(row.get("logical_sheet_id")): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_upper(row.get("logical_sheet_id")): row for row in rows}
    updates = []
    appended = 0

    registry_rows = [
        {
            "logical_sheet_id": "SESSION_FORECASTS",
            "physical_sheet_name": OUTPUT_FORECAST_SHEET,
            "sheet_role": "provider_session_forecast_capture",
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
            "created_phase": "PreSignal v2.0 Phase 4",
            "notes": "shadow_v0 provider session forecast capture",
        },
        {
            "logical_sheet_id": "SESSION_FORECAST_SUMMARY",
            "physical_sheet_name": OUTPUT_SUMMARY_SHEET,
            "sheet_role": "provider_session_forecast_summary",
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
            "created_phase": "PreSignal v2.0 Phase 4",
            "notes": "shadow_v0 provider session forecast summary",
        },
        {
            "logical_sheet_id": "SESSION_FORECAST_PROVIDER_RESPONSE_AUDIT",
            "physical_sheet_name": OUTPUT_AUDIT_SHEET,
            "sheet_role": "provider_forecast_response_audit",
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
            "created_phase": "PreSignal v2.0 Phase 4",
            "notes": "shadow_v0 provider forecast response audit",
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


def _run_forecast_sanity_checks(
    forecast_rows: Sequence[Dict[str, Any]],
    provider_requests: Sequence[Dict[str, Any]],
    provider_results: Sequence[Dict[str, Any]],
    audit_rows: Sequence[Dict[str, Any]],
    registry_result: Dict[str, Any],
) -> Dict[str, Any]:
    checks: List[Tuple[str, bool, str]] = []
    expected_pairs = {(_norm(req.get("session_id")), _norm(req.get("provider"))) for req in provider_requests}
    audit_pairs = {(_norm(row.get("session_id")), _norm(row.get("provider"))) for row in audit_rows}
    row_pairs = [(_norm(row.get("session_id")), _norm(row.get("provider"))) for row in forecast_rows]
    row_pair_counts = Counter(row_pairs)
    success_pairs = {
        (_norm(result.get("session_id")), _norm(result.get("provider")))
        for result in provider_results
        if result.get("success")
    }

    missing_audit_pairs = sorted(expected_pairs - audit_pairs)
    missing_success_rows = sorted(pair for pair in success_pairs if pair not in set(row_pair_counts))
    duplicate_pairs = sorted(pair for pair, count in row_pair_counts.items() if count > 1)
    checks.append(
        (
            "every_provider_session_has_forecast_row_or_error_diagnostics",
            not missing_audit_pairs and not missing_success_rows,
            f"missing_audit_pairs={len(missing_audit_pairs)} missing_success_rows={len(missing_success_rows)}",
        )
    )
    checks.append(
        (
            "no_duplicate_session_provider_rows",
            not duplicate_pairs,
            f"duplicate_pairs={len(duplicate_pairs)}",
        )
    )

    invalid_direction_rows = [
        row for row in forecast_rows if _norm(row.get("forecast_direction")) not in ALLOWED_FORECAST_DIRECTIONS
    ]
    checks.append(("all_forecast_directions_allowed", not invalid_direction_rows, f"invalid_rows={len(invalid_direction_rows)}"))

    forbidden_rows = [row for row in forecast_rows if _find_forbidden_output_paths(row)]
    checks.append(("no_trading_execution_fields_written", not forbidden_rows, f"forbidden_rows={len(forbidden_rows)}"))

    market_state_rows = [row for row in forecast_rows if _upper(row.get("market_state_pack_used")) != "FALSE"]
    checks.append(("market_state_pack_unused_for_all_rows", not market_state_rows, f"invalid_rows={len(market_state_rows)}"))

    checks.append(
        (
            "sheet_registry_contains_output_entries",
            (registry_result.get("updated", 0) + registry_result.get("appended", 0)) >= 3,
            f"registry_updated={registry_result}",
        )
    )
    checks.append(("event_not_written", True, "python script writes only diagnostics/registry sheets"))
    checks.append(("predictions_not_written", True, "python script writes only diagnostics/registry sheets"))
    checks.append(("evaluation_not_written", True, "python script writes only diagnostics/registry sheets"))
    checks.append(("phase1_phase2_phase3_source_sheets_not_written", True, "python script safe-rewrites only Phase 4 output sheets"))

    return {
        "passed": all(passed for _, passed, _ in checks),
        "checks": checks,
        "missing_audit_pair_count": len(missing_audit_pairs),
        "missing_success_rows_count": len(missing_success_rows),
        "duplicate_pair_count": len(duplicate_pairs),
    }


def _build_summary_row(
    generated_ts: str,
    run_id: str,
    sessions_read: int,
    valid_sessions: Sequence[Dict[str, Any]],
    provider_requests: Sequence[Dict[str, Any]],
    forecast_rows: Sequence[Dict[str, Any]],
    audit_rows: Sequence[Dict[str, Any]],
    registry_result: Dict[str, Any],
    mode: str,
    information_summary_row: Dict[str, Any],
    output_sanity: Optional[Dict[str, Any]] = None,
    metrics: Optional[Dict[str, int]] = None,
    provider_results: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    metrics = metrics or _empty_metrics()
    output_sanity = output_sanity or {"passed": True, "checks": []}
    provider_results = list(provider_results or [])

    direction_counts = Counter(_norm(row.get("forecast_direction")) for row in forecast_rows)
    providers_succeeded = sum(1 for result in provider_results if result.get("success"))
    providers_failed = len(provider_results) - providers_succeeded
    no_signal_count = sum(1 for row in forecast_rows if _as_bool(row.get("no_signal_flag")))

    if mode == "live":
        if providers_succeeded == 0:
            build_status = "FAIL"
            final_interpretation = "SESSION_FORECAST_CAPTURE_FAILED"
        elif providers_failed > 0 or not output_sanity.get("passed", False):
            build_status = "PASS_WITH_WARNINGS"
            final_interpretation = "SESSION_FORECAST_CAPTURE_NEEDS_REVIEW"
        else:
            build_status = "PASS"
            final_interpretation = "SESSION_FORECAST_CAPTURE_READY"
        failed_checks = [name for name, passed, _detail in output_sanity.get("checks", []) if not passed]
        notes = (
            f"mode=live; provider_calls={len(provider_requests)}; "
            f"payloads_prepared={len(provider_requests)}; "
            f"providers={json.dumps([req['provider'] for req in provider_requests], ensure_ascii=True)}; "
            f"information_final_interpretation={_norm(information_summary_row.get('final_interpretation'))}; "
            f"output_sanity_passed={output_sanity.get('passed', False)}; "
            f"failed_checks={json.dumps(failed_checks, ensure_ascii=True)}"
        )
    else:
        build_status = "SCAFFOLD_PASS"
        final_interpretation = "SESSION_FORECAST_SCAFFOLD_READY"
        notes = (
            "dry_run=TRUE; provider_calls=0; "
            f"payloads_prepared={len(provider_requests)}; "
            f"providers={json.dumps([req['provider'] for req in provider_requests], ensure_ascii=True)}; "
            f"information_final_interpretation={_norm(information_summary_row.get('final_interpretation'))}"
        )

    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "shadow_version": SHADOW_VERSION,
        "forecast_run_id": run_id,
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "sessions_read": sessions_read,
        "sessions_processed": len(valid_sessions),
        "providers_attempted": len(provider_requests),
        "providers_succeeded": providers_succeeded,
        "providers_failed": providers_failed,
        "forecast_rows_written": len(forecast_rows),
        "up_count": direction_counts.get("up", 0),
        "down_count": direction_counts.get("down", 0),
        "flat_count": direction_counts.get("flat", 0),
        "no_clear_direction_count": direction_counts.get("no_clear_direction", 0),
        "no_signal_count": no_signal_count,
        "invalid_direction_count": metrics.get("invalid_direction_count", 0),
        "provider_parse_error_count": metrics.get("provider_parse_error_count", 0),
        "provider_contract_error_count": metrics.get("provider_contract_error_count", 0),
        "provider_retry_count": metrics.get("provider_retry_count", 0),
        "provider_recovery_success_count": metrics.get("provider_recovery_success_count", 0),
        "provider_recovery_failed_count": metrics.get("provider_recovery_failed_count", 0),
        "provider_response_audit_rows_written": len(audit_rows),
        "provider_transport_error_count": metrics.get("provider_transport_error_count", 0),
        "provider_transport_retry_count": metrics.get("provider_transport_retry_count", 0),
        "provider_transport_retry_success_count": metrics.get("provider_transport_retry_success_count", 0),
        "provider_transport_retry_exhausted_count": metrics.get("provider_transport_retry_exhausted_count", 0),
        "registry_updated": "TRUE" if registry_result.get("updated", 0) or registry_result.get("appended", 0) else "FALSE",
        "governance_status": "DERIVED_ONLY_SHADOW_SAFE",
        "notes": notes,
    }


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Session Forecast Capture v0 in dry-run or live mode.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs, prepare provider payloads, and create/refresh output sheets without provider calls.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run live provider calls through the Apps Script execution API using existing project key resolution.",
    )
    return parser.parse_args(argv)


def build_session_forecasts_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    if args is None:
        args = _parse_args([])

    mode = "live" if getattr(args, "live", False) else "dry_run"
    creds = load_credentials(interactive=False)
    service = build_sheets_service(creds)
    generated_ts = _iso_now()
    run_id = _forecast_run_id(generated_ts)

    session_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, PHASE1_SESSION_SHEET)
    member_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, PHASE1_MEMBER_SHEET)
    attention_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, PHASE2_MAP_SHEET)
    attention_summary_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, PHASE2_SUMMARY_SHEET)
    information_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, PHASE3_REQUEST_SHEET)
    library_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, PHASE3_LIBRARY_SHEET)
    information_summary_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, PHASE3_SUMMARY_SHEET)

    (
        attention_summary_row,
        information_summary_row,
        valid_sessions,
        members_by_session,
        attention_by_pair,
        information_by_pair,
        sorted_library_rows,
    ) = _validate_inputs(
        session_rows,
        member_rows,
        attention_rows,
        attention_summary_rows,
        information_rows,
        library_rows,
        information_summary_rows,
    )

    config_map = _read_config_map(service)
    providers = _resolve_provider_candidates(config_map)
    if not providers:
        raise RuntimeError("No provider candidates were resolved from Config/defaults for forecast capture.")

    provider_requests = _build_provider_requests(
        valid_sessions,
        members_by_session,
        attention_by_pair,
        information_by_pair,
        sorted_library_rows,
        providers,
    )
    if not provider_requests:
        raise RuntimeError("No provider requests were prepared from the validated forecast inputs.")

    forecast_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_FORECAST_SHEET, FORECAST_HEADERS)
    summary_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)
    audit_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_AUDIT_SHEET, AUDIT_HEADERS)

    if mode == "live":
        script_service = build_script_service(creds)
        script_id = default_script_id()
        forecast_rows, audit_rows, metrics, provider_results = _run_live_contracts(
            generated_ts,
            run_id,
            valid_sessions,
            members_by_session,
            attention_by_pair,
            information_by_pair,
            provider_requests,
            script_service,
            script_id,
        )
        output_sanity = _run_forecast_sanity_checks(
            forecast_rows,
            provider_requests,
            provider_results,
            audit_rows,
            {"updated": 0, "appended": 0},
        )
    else:
        forecast_rows = []
        audit_rows = []
        metrics = _empty_metrics()
        provider_results = [
            {
                "session_id": request["session_id"],
                "provider": request["provider"],
                "model": request["model"],
                "success": True,
                "error_message": "",
                "rows_generated": 0,
                "attempt_count": 0,
            }
            for request in provider_requests
        ]
        output_sanity = {"passed": True, "checks": []}

    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_FORECAST_SHEET, forecast_headers, forecast_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_AUDIT_SHEET, audit_headers, audit_rows)
    registry_result = _upsert_registry_rows(service)
    if mode == "live":
        output_sanity = _run_forecast_sanity_checks(
            forecast_rows,
            provider_requests,
            provider_results,
            audit_rows,
            registry_result,
        )

    summary_row = _build_summary_row(
        generated_ts,
        run_id,
        len(session_rows),
        valid_sessions,
        provider_requests,
        forecast_rows,
        audit_rows,
        registry_result,
        mode,
        information_summary_row,
        output_sanity,
        metrics,
        provider_results,
    )
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, [summary_row])

    return {
        "generated_ts": generated_ts,
        "forecast_run_id": run_id,
        "mode": mode,
        "sessions_read": len(session_rows),
        "sessions_processed": len(valid_sessions),
        "members_read": len(member_rows),
        "providers_attempted": len(provider_requests),
        "providers_succeeded": summary_row["providers_succeeded"],
        "providers_failed": summary_row["providers_failed"],
        "payloads_prepared": len(provider_requests),
        "forecast_rows_written": len(forecast_rows),
        "up_count": summary_row["up_count"],
        "down_count": summary_row["down_count"],
        "flat_count": summary_row["flat_count"],
        "no_clear_direction_count": summary_row["no_clear_direction_count"],
        "no_signal_count": summary_row["no_signal_count"],
        "invalid_direction_count": summary_row["invalid_direction_count"],
        "provider_parse_error_count": summary_row["provider_parse_error_count"],
        "provider_contract_error_count": summary_row["provider_contract_error_count"],
        "provider_retry_count": summary_row["provider_retry_count"],
        "provider_recovery_success_count": summary_row["provider_recovery_success_count"],
        "provider_recovery_failed_count": summary_row["provider_recovery_failed_count"],
        "provider_response_audit_rows_written": summary_row["provider_response_audit_rows_written"],
        "provider_transport_error_count": summary_row["provider_transport_error_count"],
        "provider_transport_retry_count": summary_row["provider_transport_retry_count"],
        "provider_transport_retry_success_count": summary_row["provider_transport_retry_success_count"],
        "provider_transport_retry_exhausted_count": summary_row["provider_transport_retry_exhausted_count"],
        "build_status": summary_row["build_status"],
        "final_interpretation": summary_row["final_interpretation"],
        "output_sheets": [OUTPUT_FORECAST_SHEET, OUTPUT_SUMMARY_SHEET, OUTPUT_AUDIT_SHEET],
        "registry_result": registry_result,
        "output_sanity": {
            "passed": output_sanity.get("passed", True),
            "checks": [
                {"name": name, "passed": passed, "detail": detail}
                for name, passed, detail in output_sanity.get("checks", [])
            ],
        },
        "sample_request": {
            "provider": provider_requests[0]["provider"],
            "model": provider_requests[0]["model"],
            "instruction": provider_requests[0]["instruction"],
            "payload": provider_requests[0]["payload"],
        }
        if provider_requests
        else {},
        "provider_results": provider_results,
        "sample_forecast_row": forecast_rows[0] if forecast_rows else {},
        "sample_audit_row": audit_rows[0] if audit_rows else {},
    }


def main() -> None:
    print(json.dumps(build_session_forecasts_v0(_parse_args()), ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
