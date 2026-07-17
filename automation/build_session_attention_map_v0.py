import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_market_sessions_shadow_v0 import (
    MAIN_SPREADSHEET_ID,
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
from automation.google_clients import (
    batch_update_values,
    build_script_service,
    build_sheets_service,
    default_script_id,
    get_sheet_values,
    load_credentials,
    run_script_function,
)


PHASE1_SESSION_SHEET = "Market_Sessions"
PHASE1_MEMBER_SHEET = "Market_Session_Members"
PHASE1_SANITY_SUMMARY_SHEET = "Market_Session_Shadow_Sanity_Summary"

OUTPUT_MAP_SHEET = "Session_Attention_Map"
OUTPUT_SUMMARY_SHEET = "Session_Attention_Summary"
OUTPUT_AUDIT_SHEET = "Session_Attention_Provider_Response_Audit"

SCHEMA_VERSION = "presignal_v2_session_attention_0.1"
SHADOW_VERSION = "shadow_v0"
REGISTRY_CATEGORY = "PRESIGNAL_V2_MARKET_SESSION"
REGISTRY_OWNER_MODULE = "market_session"
AUTOMATION_PROVIDER_FUNCTION = "apiCallProviderJsonObject"

DEFAULT_PROVIDERS = ["Gemini", "OpenAI", "Anthropic"]
DEFAULT_MODELS = {
    "Gemini": "gemini-2.5-flash-lite",
    "OpenAI": "gpt-4o-mini",
    "Anthropic": "claude-haiku-4-5",
}

ALLOWED_ATTENTION_LABELS = {
    "PRIMARY_DRIVER",
    "SECONDARY_DRIVER",
    "WATCHLIST",
    "CONTEXT_ONLY",
    "IGNORE",
    "NO_SIGNAL",
}
ALLOWED_MARKET_CHANNELS = {
    "fed_path",
    "treasury_yields",
    "usd_direction",
    "jpy_direction",
    "risk_sentiment",
    "inflation_expectations",
    "labor_market",
    "growth_outlook",
    "market_positioning",
    "low_direct_market_impact",
    "unknown",
}
ALLOWED_DRIVER_ROLES = {"primary", "secondary", "context", "watch", "ignore", "no_signal"}
DEFAULT_DRIVER_ROLE_BY_LABEL = {
    "PRIMARY_DRIVER": "primary",
    "SECONDARY_DRIVER": "secondary",
    "WATCHLIST": "watch",
    "CONTEXT_ONLY": "context",
    "IGNORE": "ignore",
    "NO_SIGNAL": "no_signal",
}
FORBIDDEN_OUTPUT_KEYS = {
    "forecast_direction",
    "forecast_value",
    "expected_move_dir",
    "expected_move_pips",
    "expected_move_pips_min",
    "expected_move_pips_max",
    "trade_advice",
    "trade_recommendation",
    "information_requirements",
    "browse_request",
    "external_browsing",
}
FORBIDDEN_OUTPUT_PHRASES = [
    "buy usdjpy",
    "sell usdjpy",
    "browse the web",
    "external browsing",
    "usdjpy will go up",
    "usdjpy will go down",
]

MAX_LIVE_ATTEMPTS = 2
RAW_EXCERPT_LIMIT = 1200
NORMALIZED_EXCERPT_LIMIT = 1200
SMART_QUOTES_MAP = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
    }
)

PROVIDER_TASK_TEXT = (
    "Classify which events in this market session matter for USDJPY reaction. "
    "Do not forecast USDJPY direction. Do not predict pips. "
    "Only classify attention importance and explain why."
)
PROVIDER_INSTRUCTION_TEXT = """You are classifying event attention for a PreSignal v2.0 shadow research layer.

You are given one market session containing multiple scheduled economic events.

Your task is not to forecast USDJPY direction.

Your task is only to classify which events deserve attention for a later USDJPY session-level forecast.

For each event, assign exactly one attention_label:

PRIMARY_DRIVER:
The event is likely to be one of the main drivers of USDJPY reaction in this session.

SECONDARY_DRIVER:
The event may influence USDJPY but is not the main driver.

WATCHLIST:
The event could become important depending on the released value or interaction with other events.

CONTEXT_ONLY:
The event helps interpret the session but probably should not drive the directional forecast by itself.

IGNORE:
The event is unlikely to matter for USDJPY in this session.

NO_SIGNAL:
The event does not provide enough usable signal for USDJPY reaction.

Do not predict USDJPY up/down/flat.
Do not estimate pips.
Do not give trading advice.
Do not browse.
Only classify event attention and explain briefly.
Return one valid JSON object only.
Return strict JSON only.
Do not include markdown.
Do not include explanatory text outside JSON.
Do not truncate strings.
Use short reasons, max 160 characters each.

Return a top-level JSON object with exactly these keys:
- object
- session_id
- provider
- attention_items
- session_attention_summary
- status

Set object exactly to session_attention_map.
Set session_id exactly to the provided session.session_id.
Set provider to the provider name handling this request.
Set status to ok.

attention_items must be an array of objects using exactly these keys:
- event_id
- attention_label
- attention_rank
- attention_reason
- expected_market_channel
- driver_role
- confidence

Allowed attention_label values:
- PRIMARY_DRIVER
- SECONDARY_DRIVER
- WATCHLIST
- CONTEXT_ONLY
- IGNORE
- NO_SIGNAL

Allowed expected_market_channel values:
- fed_path
- treasury_yields
- usd_direction
- jpy_direction
- risk_sentiment
- inflation_expectations
- labor_market
- growth_outlook
- market_positioning
- low_direct_market_impact
- unknown

Allowed driver_role values:
- primary
- secondary
- context
- watch
- ignore
- no_signal

Do not include forecast_direction, expected_move_dir, expected_move_pips, trade advice, browsing requests, or any fields not listed above."""

MAP_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "attention_run_id",
    "session_id",
    "session_date",
    "country",
    "session_window_name",
    "provider",
    "model",
    "event_id",
    "batch_id",
    "type",
    "indicator_name",
    "genre",
    "importance",
    "release_ts",
    "member_order",
    "attention_label",
    "attention_rank",
    "attention_reason",
    "expected_market_channel",
    "driver_role",
    "confidence",
    "omission_reason",
    "raw_output",
    "status",
    "error_message",
    "source_session_sheet",
    "source_member_sheet",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "attention_run_id",
    "build_status",
    "final_interpretation",
    "sessions_read",
    "sessions_processed",
    "providers_attempted",
    "providers_succeeded",
    "providers_failed",
    "session_member_rows_read",
    "attention_rows_written",
    "primary_driver_count",
    "secondary_driver_count",
    "watchlist_count",
    "context_only_count",
    "ignore_count",
    "no_signal_count",
    "provider_omission_count",
    "invalid_label_count",
    "duplicate_provider_event_count",
    "registry_updated",
    "governance_status",
    "notes",
    "provider_parse_error_count",
    "provider_contract_error_count",
    "provider_retry_count",
    "provider_recovery_success_count",
    "provider_recovery_failed_count",
    "provider_response_audit_rows_written",
]

AUDIT_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "attention_run_id",
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
    "invalid_label_count",
    "omitted_event_count",
    "duplicate_event_count",
    "notes",
]


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _safe_int(value: Any) -> int:
    try:
        return int(float(_norm(value) or "0"))
    except Exception:
        return 0


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(_norm(value))
    except Exception:
        return None


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _attention_run_id(generated_ts: str) -> str:
    stamp = generated_ts.replace("-", "").replace(":", "").replace("+00:00", "Z").replace(".", "")
    return f"session_attention_v0_{stamp}"


def _normalize_provider_name(name: Any) -> str:
    raw = _norm(name)
    if raw.lower() == "claude":
        return "Anthropic"
    if raw.lower() == "anthropic":
        return "Anthropic"
    if raw.lower() == "openai":
        return "OpenAI"
    if raw.lower() == "gemini":
        return "Gemini"
    return raw


def _truncate_text(value: Any, limit: int) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 3)]}..."


def _strip_code_fences(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return text


def _normalize_smart_quotes(value: Any) -> str:
    return str(value or "").translate(SMART_QUOTES_MAP)


def _extract_first_json_object(value: Any) -> Optional[str]:
    text = str(value or "")
    if not text:
        return None
    starts = [i for i, ch in enumerate(text) if ch == "{"]
    for start in starts:
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            ch = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]
    return None


def _candidate_json_texts(raw_output: Any) -> List[Tuple[str, str]]:
    base = str(raw_output or "").strip()
    seen = set()
    candidates: List[Tuple[str, str]] = []

    def add(method: str, candidate: Any) -> None:
        text = str(candidate or "").strip()
        if not text or text in seen:
            return
        seen.add(text)
        candidates.append((method, text))

    add("as_is", base)

    stripped = _strip_code_fences(base)
    if stripped != base:
        add("strip_code_fences", stripped)

    extracted_base = _extract_first_json_object(base)
    if extracted_base:
        add("extract_first_json_object", extracted_base)

    extracted_stripped = _extract_first_json_object(stripped)
    if extracted_stripped:
        add("strip_code_fences+extract_first_json_object", extracted_stripped)

    smart = _normalize_smart_quotes(base)
    if smart != base:
        add("normalize_smart_quotes", smart)
        smart_stripped = _strip_code_fences(smart)
        if smart_stripped != smart:
            add("normalize_smart_quotes+strip_code_fences", smart_stripped)
        extracted_smart = _extract_first_json_object(smart)
        if extracted_smart:
            add("normalize_smart_quotes+extract_first_json_object", extracted_smart)
        extracted_smart_stripped = _extract_first_json_object(smart_stripped)
        if extracted_smart_stripped:
            add(
                "normalize_smart_quotes+strip_code_fences+extract_first_json_object",
                extracted_smart_stripped,
            )

    return candidates


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
        "recovery_status": "recovery_failed" if len(candidates) > 1 else "not_needed",
        "recovery_attempted": len(candidates) > 1,
        "error_type": "parse_error",
        "error_message": last_error,
    }


def _read_config_map(service) -> Dict[str, str]:
    try:
        values = get_sheet_values(service, MAIN_SPREADSHEET_ID, "Config!A:B")
    except Exception:
        return {}
    if not values:
        return {}
    out: Dict[str, str] = {}
    for raw in values[1:]:
        if not raw:
            continue
        key = _upper(raw[0])
        if not key:
            continue
        out[key] = _norm(raw[1]) if len(raw) > 1 else ""
    return out


def _resolve_provider_candidates(config: Dict[str, str]) -> List[Dict[str, str]]:
    providers_raw = _norm(config.get("PROVIDERS"))
    if providers_raw:
        wanted = [_normalize_provider_name(part) for part in providers_raw.split(",") if _norm(part)]
    else:
        wanted = list(DEFAULT_PROVIDERS)

    providers: List[Dict[str, str]] = []
    seen = set()
    for name in wanted:
        if name not in DEFAULT_MODELS or name in seen:
            continue
        seen.add(name)
        model_key = {
            "Gemini": "GEMINI_MODEL",
            "OpenAI": "OPENAI_MODEL",
            "Anthropic": "CLAUDE_MODEL",
        }[name]
        providers.append({"provider": name, "model": _norm(config.get(model_key)) or DEFAULT_MODELS[name]})
    providers.sort(key=lambda item: (_norm(item["provider"]), _norm(item["model"])))
    return providers


def _require_headers(sheet_name: str, rows: Sequence[Dict[str, Any]], headers: Sequence[str]) -> None:
    if not rows:
        raise RuntimeError(f"{sheet_name} is missing or empty.")
    missing = [header for header in headers if header not in rows[0]]
    if missing:
        raise RuntimeError(f"{sheet_name} is missing required headers: {', '.join(missing)}")


def _sanity_ready(summary_row: Dict[str, Any]) -> bool:
    final_interpretation = _upper(summary_row.get("final_interpretation"))
    build_status = _upper(summary_row.get("build_status"))
    return final_interpretation == "MARKET_SESSION_SANITY_READY" or build_status == "PASS"


def _sort_member_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = list(rows)
    out.sort(
        key=lambda row: (
            _norm(row.get("session_id")),
            _parse_dt(row.get("release_ts")) or datetime.max.replace(tzinfo=timezone.utc),
            _safe_int(row.get("member_order")),
            _norm(row.get("indicator_name")),
            _norm(row.get("event_id")),
        )
    )
    return out


def _validate_phase1_inputs(
    session_rows: Sequence[Dict[str, Any]],
    member_rows: Sequence[Dict[str, Any]],
    sanity_rows: Sequence[Dict[str, Any]],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
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
            "same_minute_group_key",
            "is_batch_member",
        ],
    )
    _require_headers(PHASE1_SANITY_SUMMARY_SHEET, sanity_rows, ["build_status", "final_interpretation"])

    sanity_row = sanity_rows[0]
    if not _sanity_ready(sanity_row):
        raise RuntimeError(
            f"{PHASE1_SANITY_SUMMARY_SHEET} is not ready: "
            f"build_status={_norm(sanity_row.get('build_status'))}, "
            f"final_interpretation={_norm(sanity_row.get('final_interpretation'))}"
        )

    session_map = {_norm(row.get("session_id")): row for row in session_rows if _norm(row.get("session_id"))}
    members_by_session: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in _sort_member_rows(member_rows):
        session_id = _norm(row.get("session_id"))
        if session_id:
            members_by_session[session_id].append(row)

    valid_sessions: List[Dict[str, Any]] = []
    for session_id in sorted(session_map):
        session = session_map[session_id]
        members = members_by_session.get(session_id, [])
        if not members:
            continue
        expected_count = _safe_int(session.get("member_event_count"))
        if expected_count and expected_count != len(members):
            continue
        valid_sessions.append(session)

    if not valid_sessions:
        raise RuntimeError("No structurally valid market sessions were found for attention preparation.")

    return sanity_row, valid_sessions, members_by_session


def _build_provider_instruction() -> str:
    return PROVIDER_INSTRUCTION_TEXT


def _build_payload(session_row: Dict[str, Any], member_rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "object": "presignal_v2_market_session_attention_task",
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
        "task": PROVIDER_TASK_TEXT,
    }


def _build_provider_prompt(provider_request: Dict[str, Any]) -> Dict[str, str]:
    return {
        "system": (
            "You are a macroeconomic research model. "
            "Output must be strict JSON only, with no markdown, no code fences, and no prose outside the JSON object."
        ),
        "user": json.dumps(provider_request["payload"], ensure_ascii=True),
        "instruction": provider_request["instruction"],
        "cache_scaffold": "",
    }


def _build_provider_requests(
    session_rows: Sequence[Dict[str, Any]],
    members_by_session: Dict[str, List[Dict[str, Any]]],
    providers: Sequence[Dict[str, str]],
) -> List[Dict[str, Any]]:
    requests: List[Dict[str, Any]] = []
    instruction = _build_provider_instruction()
    for session_row in sorted(session_rows, key=lambda row: _norm(row.get("session_id"))):
        session_id = _norm(session_row.get("session_id"))
        member_rows = members_by_session.get(session_id, [])
        payload = _build_payload(session_row, member_rows)
        for provider in providers:
            requests.append(
                {
                    "session_id": session_id,
                    "provider": provider["provider"],
                    "model": provider["model"],
                    "instruction": instruction,
                    "payload": payload,
                }
            )
    requests.sort(key=lambda item: (_norm(item["session_id"]), _norm(item["provider"]), _norm(item["model"])))
    return requests


def _normalize_market_channel(value: Any) -> str:
    raw = _norm(value)
    return raw if raw in ALLOWED_MARKET_CHANNELS else "unknown"


def _normalize_driver_role(value: Any, label: str) -> str:
    raw = _norm(value).lower()
    if raw in ALLOWED_DRIVER_ROLES:
        return raw
    return DEFAULT_DRIVER_ROLE_BY_LABEL[label]


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
        "provider_omission_count": 0,
        "invalid_label_count": 0,
        "duplicate_provider_event_count": 0,
        "provider_parse_error_count": 0,
        "provider_contract_error_count": 0,
        "provider_retry_count": 0,
        "provider_recovery_success_count": 0,
        "provider_recovery_failed_count": 0,
        "provider_response_audit_rows_written": 0,
    }


def _base_attention_row(
    generated_ts: str,
    run_id: str,
    session_row: Dict[str, Any],
    member_row: Dict[str, Any],
    provider: str,
    model: str,
    raw_output: str,
) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "shadow_version": SHADOW_VERSION,
        "attention_run_id": run_id,
        "session_id": _norm(session_row.get("session_id")),
        "session_date": _norm(session_row.get("session_date")),
        "country": _norm(session_row.get("country")),
        "session_window_name": _norm(session_row.get("session_window_name")),
        "provider": provider,
        "model": model,
        "event_id": _norm(member_row.get("event_id")),
        "batch_id": _norm(member_row.get("batch_id")),
        "type": _norm(member_row.get("type")),
        "indicator_name": _norm(member_row.get("indicator_name")),
        "genre": _norm(member_row.get("genre")),
        "importance": _norm(member_row.get("importance")),
        "release_ts": _norm(member_row.get("release_ts")),
        "member_order": _safe_int(member_row.get("member_order")),
        "attention_label": "",
        "attention_rank": "",
        "attention_reason": "",
        "expected_market_channel": "",
        "driver_role": "",
        "confidence": "",
        "omission_reason": "",
        "raw_output": raw_output,
        "status": "",
        "error_message": "",
        "source_session_sheet": PHASE1_SESSION_SHEET,
        "source_member_sheet": PHASE1_MEMBER_SHEET,
        "notes": "",
    }


def _sort_attention_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def sort_key(row: Dict[str, Any]) -> Tuple[Any, ...]:
        rank = _safe_int(row.get("attention_rank"))
        rank_sort = rank if rank > 0 else 999999
        release_dt = _parse_dt(row.get("release_ts")) or datetime.max.replace(tzinfo=timezone.utc)
        return (
            _norm(row.get("session_id")),
            _norm(row.get("provider")),
            rank_sort,
            release_dt,
            _norm(row.get("event_id")),
        )

    out = list(rows)
    out.sort(key=sort_key)
    return out


def _provider_contract_error_rows(
    generated_ts: str,
    run_id: str,
    session_row: Dict[str, Any],
    member_rows: Sequence[Dict[str, Any]],
    provider: str,
    model: str,
    raw_output: str,
    error_message: str,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for member_row in member_rows:
        row = _base_attention_row(generated_ts, run_id, session_row, member_row, provider, model, raw_output)
        row.update(
            {
                "attention_label": "NO_SIGNAL",
                "expected_market_channel": "unknown",
                "driver_role": "no_signal",
                "omission_reason": "provider_contract_error",
                "status": "provider_contract_error",
                "error_message": error_message,
            }
        )
        rows.append(row)
    return rows


def _build_transport_failure_result(
    generated_ts: str,
    run_id: str,
    session_row: Dict[str, Any],
    member_rows: Sequence[Dict[str, Any]],
    provider: str,
    model: str,
    raw_output: str,
    response_status: str,
    error_message: str,
) -> Dict[str, Any]:
    metrics = _empty_metrics()
    lowered = error_message.lower()
    error_type = "transport_error"
    parse_status = "not_attempted"
    contract_status = response_status or "transport_error"
    retryable = False
    if "empty content" in lowered or "empty response" in lowered:
        error_type = "empty_response"
        parse_status = "empty_response"
        contract_status = "not_evaluated"
        retryable = True
        metrics["provider_parse_error_count"] = 1
    rows = _provider_contract_error_rows(
        generated_ts,
        run_id,
        session_row,
        member_rows,
        provider,
        model,
        raw_output,
        error_message,
    )
    return {
        "success": False,
        "rows": rows,
        "metrics": metrics,
        "parse_status": parse_status,
        "contract_status": contract_status,
        "recovery_status": "not_attempted",
        "normalized_json_text": "",
        "error_type": error_type,
        "error_message": error_message,
        "retryable": retryable,
        "forbidden_field_detected": "FALSE",
    }


def _parse_provider_output(
    generated_ts: str,
    run_id: str,
    session_row: Dict[str, Any],
    member_rows: Sequence[Dict[str, Any]],
    provider: str,
    model: str,
    raw_output: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    del payload  # payload retained for future audit/context without changing parser behavior.

    metrics = _empty_metrics()
    recovery = _recover_json_payload(raw_output)
    if recovery["ok"] and recovery["recovery_status"] != "not_needed":
        metrics["provider_recovery_success_count"] = 1
    elif not recovery["ok"] and recovery["recovery_attempted"]:
        metrics["provider_recovery_failed_count"] = 1

    session_id = _norm(session_row.get("session_id"))
    event_rows = {_norm(row.get("event_id")): row for row in member_rows}

    if not recovery["ok"]:
        metrics["provider_parse_error_count"] = 1
        rows = _provider_contract_error_rows(
            generated_ts,
            run_id,
            session_row,
            member_rows,
            provider,
            model,
            raw_output,
            recovery["error_message"],
        )
        return {
            "success": False,
            "rows": rows,
            "metrics": metrics,
            "parse_status": recovery["parse_status"],
            "contract_status": "not_evaluated",
            "recovery_status": recovery["recovery_status"],
            "normalized_json_text": "",
            "error_type": recovery["error_type"],
            "error_message": recovery["error_message"],
            "retryable": True,
            "forbidden_field_detected": "FALSE",
        }

    parsed = recovery["parsed_value"]
    normalized_json_text = recovery["normalized_json_text"]

    if not isinstance(parsed, dict):
        metrics["provider_contract_error_count"] = 1
        error_message = "provider output must be a top-level JSON object"
        rows = _provider_contract_error_rows(
            generated_ts,
            run_id,
            session_row,
            member_rows,
            provider,
            model,
            raw_output,
            error_message,
        )
        return {
            "success": False,
            "rows": rows,
            "metrics": metrics,
            "parse_status": recovery["parse_status"],
            "contract_status": "top_level_not_object",
            "recovery_status": recovery["recovery_status"],
            "normalized_json_text": normalized_json_text,
            "error_type": "contract_error",
            "error_message": error_message,
            "retryable": True,
            "forbidden_field_detected": "FALSE",
        }

    forbidden_hits = _find_forbidden_output_paths(parsed)
    if forbidden_hits:
        metrics["provider_contract_error_count"] = 1
        error_message = f"forbidden_output_detected: {', '.join(forbidden_hits[:5])}"
        rows = _provider_contract_error_rows(
            generated_ts,
            run_id,
            session_row,
            member_rows,
            provider,
            model,
            raw_output,
            error_message,
        )
        return {
            "success": False,
            "rows": rows,
            "metrics": metrics,
            "parse_status": recovery["parse_status"],
            "contract_status": "forbidden_field_detected",
            "recovery_status": recovery["recovery_status"],
            "normalized_json_text": normalized_json_text,
            "error_type": "forbidden_field_detected",
            "error_message": error_message,
            "retryable": False,
            "forbidden_field_detected": "TRUE",
        }

    provider_field = _norm(parsed.get("provider"))
    if not provider_field:
        metrics["provider_contract_error_count"] = 1
        error_message = "provider field is missing from provider output"
        rows = _provider_contract_error_rows(
            generated_ts,
            run_id,
            session_row,
            member_rows,
            provider,
            model,
            raw_output,
            error_message,
        )
        return {
            "success": False,
            "rows": rows,
            "metrics": metrics,
            "parse_status": recovery["parse_status"],
            "contract_status": "missing_provider",
            "recovery_status": recovery["recovery_status"],
            "normalized_json_text": normalized_json_text,
            "error_type": "contract_error",
            "error_message": error_message,
            "retryable": True,
            "forbidden_field_detected": "FALSE",
        }

    if _norm(parsed.get("object")) != "session_attention_map":
        metrics["provider_contract_error_count"] = 1
        error_message = f"invalid_object={_norm(parsed.get('object')) or '<blank>'}"
        rows = _provider_contract_error_rows(
            generated_ts,
            run_id,
            session_row,
            member_rows,
            provider,
            model,
            raw_output,
            error_message,
        )
        return {
            "success": False,
            "rows": rows,
            "metrics": metrics,
            "parse_status": recovery["parse_status"],
            "contract_status": "invalid_object",
            "recovery_status": recovery["recovery_status"],
            "normalized_json_text": normalized_json_text,
            "error_type": "contract_error",
            "error_message": error_message,
            "retryable": True,
            "forbidden_field_detected": "FALSE",
        }

    if _norm(parsed.get("session_id")) != session_id:
        metrics["provider_contract_error_count"] = 1
        error_message = (
            f"session_id_mismatch expected={session_id or '<blank>'} "
            f"got={_norm(parsed.get('session_id')) or '<blank>'}"
        )
        rows = _provider_contract_error_rows(
            generated_ts,
            run_id,
            session_row,
            member_rows,
            provider,
            model,
            raw_output,
            error_message,
        )
        return {
            "success": False,
            "rows": rows,
            "metrics": metrics,
            "parse_status": recovery["parse_status"],
            "contract_status": "session_id_mismatch",
            "recovery_status": recovery["recovery_status"],
            "normalized_json_text": normalized_json_text,
            "error_type": "contract_error",
            "error_message": error_message,
            "retryable": True,
            "forbidden_field_detected": "FALSE",
        }

    attention_items = parsed.get("attention_items")
    if not isinstance(attention_items, list):
        metrics["provider_contract_error_count"] = 1
        error_message = "attention_items must be an array"
        rows = _provider_contract_error_rows(
            generated_ts,
            run_id,
            session_row,
            member_rows,
            provider,
            model,
            raw_output,
            error_message,
        )
        return {
            "success": False,
            "rows": rows,
            "metrics": metrics,
            "parse_status": recovery["parse_status"],
            "contract_status": "attention_items_not_array",
            "recovery_status": recovery["recovery_status"],
            "normalized_json_text": normalized_json_text,
            "error_type": "contract_error",
            "error_message": error_message,
            "retryable": True,
            "forbidden_field_detected": "FALSE",
        }

    rows: List[Dict[str, Any]] = []
    seen_event_ids = set()
    for index, item in enumerate(attention_items):
        if not isinstance(item, dict):
            continue
        event_id = _norm(item.get("event_id"))
        if not event_id or event_id not in event_rows:
            continue
        if event_id in seen_event_ids:
            metrics["duplicate_provider_event_count"] += 1
            continue

        seen_event_ids.add(event_id)
        member_row = event_rows[event_id]
        row = _base_attention_row(generated_ts, run_id, session_row, member_row, provider, model, raw_output)

        label = _upper(item.get("attention_label"))
        if label not in ALLOWED_ATTENTION_LABELS:
            metrics["invalid_label_count"] += 1
            row.update(
                {
                    "attention_label": "NO_SIGNAL",
                    "expected_market_channel": "unknown",
                    "driver_role": "no_signal",
                    "omission_reason": f"invalid_attention_label:{_norm(item.get('attention_label')) or '<blank>'}",
                    "status": "invalid_attention_label",
                    "error_message": (
                        f"attention_items[{index}] invalid label: "
                        f"{_norm(item.get('attention_label')) or '<blank>'}"
                    ),
                    "notes": "provider item parsed but downgraded to NO_SIGNAL due to invalid label",
                }
            )
            rows.append(row)
            continue

        confidence = _safe_float(item.get("confidence"))
        attention_rank = _safe_int(item.get("attention_rank"))
        row.update(
            {
                "attention_label": label,
                "attention_rank": attention_rank if attention_rank > 0 else "",
                "attention_reason": _truncate_text(_norm(item.get("attention_reason")), 160),
                "expected_market_channel": _normalize_market_channel(item.get("expected_market_channel")),
                "driver_role": _normalize_driver_role(item.get("driver_role"), label),
                "confidence": confidence if confidence is not None else "",
                "status": "parsed",
            }
        )
        rows.append(row)

    for event_id, member_row in event_rows.items():
        if event_id in seen_event_ids:
            continue
        metrics["provider_omission_count"] += 1
        row = _base_attention_row(generated_ts, run_id, session_row, member_row, provider, model, raw_output)
        row.update(
            {
                "attention_label": "NO_SIGNAL",
                "expected_market_channel": "unknown",
                "driver_role": "no_signal",
                "omission_reason": "event_not_returned_by_provider",
                "status": "provider_omitted_event",
            }
        )
        rows.append(row)

    contract_status = "valid_with_invalid_labels" if metrics["invalid_label_count"] else "valid"
    if _normalize_provider_name(provider_field) not in ("", provider):
        contract_status = f"{contract_status}_provider_mismatch_tolerated"
    return {
        "success": True,
        "rows": _sort_attention_rows(rows),
        "metrics": metrics,
        "parse_status": recovery["parse_status"],
        "contract_status": contract_status,
        "recovery_status": recovery["recovery_status"],
        "normalized_json_text": normalized_json_text,
        "error_type": "",
        "error_message": "",
        "retryable": False,
        "forbidden_field_detected": "FALSE",
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
        "attention_run_id": run_id,
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
        "normalized_json_excerpt": _truncate_text(
            parse_result.get("normalized_json_text", ""),
            NORMALIZED_EXCERPT_LIMIT,
        ),
        "error_type": parse_result.get("error_type", ""),
        "error_message": _truncate_text(parse_result.get("error_message", ""), 500),
        "response_char_count": len(raw_output or ""),
        "forbidden_field_detected": parse_result.get("forbidden_field_detected", "FALSE"),
        "invalid_label_count": metrics.get("invalid_label_count", 0),
        "omitted_event_count": metrics.get("provider_omission_count", 0),
        "duplicate_event_count": metrics.get("duplicate_provider_event_count", 0),
        "notes": _truncate_text(notes, 400),
    }


def _build_mock_response(provider_request: Dict[str, Any]) -> str:
    payload = provider_request["payload"]
    provider = provider_request["provider"]
    session_id = _norm(payload["session"]["session_id"])
    events = payload["events"]
    first_event_id = events[0]["event_id"]
    second_event_id = events[1]["event_id"] if len(events) > 1 else first_event_id
    third_event_id = events[2]["event_id"] if len(events) > 2 else first_event_id
    fourth_event_id = events[3]["event_id"] if len(events) > 3 else first_event_id

    if provider == "Anthropic":
        return json.dumps(
            {
                "object": "session_attention_map",
                "session_id": session_id,
                "provider": provider,
                "forecast_direction": "UP",
                "attention_items": [
                    {
                        "event_id": first_event_id,
                        "attention_label": "PRIMARY_DRIVER",
                        "attention_rank": 1,
                        "attention_reason": "Mock contract failure fixture.",
                        "expected_market_channel": "treasury_yields",
                        "driver_role": "primary",
                        "confidence": 0.81,
                    }
                ],
                "session_attention_summary": "This fixture should fail because it exposes a forbidden forecast field.",
                "status": "ok",
            },
            ensure_ascii=True,
        )

    if provider == "Gemini":
        return json.dumps(
            {
                "object": "session_attention_map",
                "session_id": session_id,
                "provider": provider,
                "attention_items": [
                    {
                        "event_id": first_event_id,
                        "attention_label": "SECONDARY_DRIVER",
                        "attention_rank": 2,
                        "attention_reason": "Mock valid item.",
                        "expected_market_channel": "usd_direction",
                        "driver_role": "secondary",
                        "confidence": 0.63,
                    },
                    {
                        "event_id": first_event_id,
                        "attention_label": "CONTEXT_ONLY",
                        "attention_rank": 4,
                        "attention_reason": "Duplicate event fixture that should be ignored after counting.",
                        "expected_market_channel": "unknown",
                        "driver_role": "context",
                        "confidence": 0.4,
                    },
                    {
                        "event_id": second_event_id,
                        "attention_label": "TERTIARY_DRIVER",
                        "attention_rank": 3,
                        "attention_reason": "Invalid label fixture.",
                        "expected_market_channel": "labor_market",
                        "driver_role": "secondary",
                        "confidence": 0.51,
                    },
                    {
                        "event_id": third_event_id,
                        "attention_label": "IGNORE",
                        "attention_reason": "Mock low-impact item.",
                        "expected_market_channel": "low_direct_market_impact",
                        "driver_role": "ignore",
                        "confidence": 0.74,
                    },
                ],
                "session_attention_summary": "Mock response with one duplicate and one invalid label.",
                "status": "ok",
            },
            ensure_ascii=True,
        )

    return json.dumps(
        {
            "object": "session_attention_map",
            "session_id": session_id,
            "provider": provider,
            "attention_items": [
                {
                    "event_id": first_event_id,
                    "attention_label": "PRIMARY_DRIVER",
                    "attention_rank": 1,
                    "attention_reason": "Front-loaded Fed communication can anchor session interpretation.",
                    "expected_market_channel": "fed_path",
                    "driver_role": "primary",
                    "confidence": 0.86,
                },
                {
                    "event_id": fourth_event_id,
                    "attention_label": "WATCHLIST",
                    "attention_rank": 2,
                    "attention_reason": "Labor print could matter if it changes rate-path expectations.",
                    "expected_market_channel": "labor_market",
                    "driver_role": "watch",
                    "confidence": 0.71,
                },
            ],
            "session_attention_summary": "Mock valid response with intentional omissions for fill testing.",
            "status": "ok",
        },
        ensure_ascii=True,
    )


def _run_mock_contracts(
    generated_ts: str,
    run_id: str,
    valid_sessions: Sequence[Dict[str, Any]],
    members_by_session: Dict[str, List[Dict[str, Any]]],
    provider_requests: Sequence[Dict[str, Any]],
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
        member_rows = members_by_session.get(session_id, [])
        raw_output = _build_mock_response(request)
        parse_result = _parse_provider_output(
            generated_ts,
            run_id,
            session_row,
            member_rows,
            provider,
            model,
            raw_output,
            request["payload"],
        )
        retry_status = "not_retried_success" if parse_result["success"] else "not_retried_non_retryable"
        audit_rows.append(
            _build_provider_response_audit_row(
                generated_ts,
                run_id,
                session_id,
                provider,
                model,
                1,
                "attempted",
                "ok",
                parse_result,
                retry_status,
                raw_output,
            )
        )
        rows.extend(parse_result["rows"])
        for key, value in parse_result["metrics"].items():
            metrics[key] += value
        provider_results.append(
            {
                "session_id": session_id,
                "provider": provider,
                "model": model,
                "success": parse_result["success"],
                "error_message": parse_result["error_message"],
                "rows_generated": len(parse_result["rows"]),
                "attempt_count": 1,
            }
        )

    metrics["provider_response_audit_rows_written"] = len(audit_rows)
    return _sort_attention_rows(rows), audit_rows, dict(metrics), provider_results


def _call_live_provider_raw(
    script_service,
    script_id: str,
    provider_request: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        result = run_script_function(
            script_service,
            script_id,
            AUTOMATION_PROVIDER_FUNCTION,
            [
                {
                    "provider": provider_request["provider"],
                    "prompt": _build_provider_prompt(provider_request),
                }
            ],
        )
    except Exception as exc:
        return {
            "status": "execution_error",
            "provider": provider_request["provider"],
            "model": provider_request["model"],
            "request_status": "attempted",
            "response_status": "execution_error",
            "raw_output": "",
            "error": str(exc),
        }

    if not isinstance(result, dict):
        return {
            "status": "execution_error",
            "provider": provider_request["provider"],
            "model": provider_request["model"],
            "request_status": "attempted",
            "response_status": "execution_error",
            "raw_output": "",
            "error": "provider execution returned non-object result",
        }

    return {
        "status": _norm(result.get("status")) or "error",
        "provider": _normalize_provider_name(result.get("provider")) or provider_request["provider"],
        "model": _norm(result.get("model")) or provider_request["model"],
        "request_status": _norm(result.get("request_status")) or "attempted",
        "response_status": _norm(result.get("response_status")) or _norm(result.get("status")) or "unknown",
        "raw_output": str(result.get("raw_output") or ""),
        "error": _norm(result.get("error")),
    }


def _run_live_contracts(
    generated_ts: str,
    run_id: str,
    valid_sessions: Sequence[Dict[str, Any]],
    members_by_session: Dict[str, List[Dict[str, Any]]],
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
        member_rows = members_by_session.get(session_id, [])

        final_result: Optional[Dict[str, Any]] = None
        final_model = model
        attempt_count = 0

        for attempt_number in range(1, MAX_LIVE_ATTEMPTS + 1):
            attempt_count = attempt_number
            provider_response = _call_live_provider_raw(script_service, script_id, request)
            final_model = provider_response.get("model") or final_model
            raw_output = provider_response.get("raw_output", "")

            if provider_response.get("status") == "ok":
                parse_result = _parse_provider_output(
                    generated_ts,
                    run_id,
                    session_row,
                    member_rows,
                    provider,
                    final_model,
                    raw_output,
                    request["payload"],
                )
            else:
                parse_result = _build_transport_failure_result(
                    generated_ts,
                    run_id,
                    session_row,
                    member_rows,
                    provider,
                    final_model,
                    raw_output,
                    provider_response.get("response_status", "error"),
                    provider_response.get("error") or "provider_call_failed",
                )

            should_retry = (
                not parse_result["success"]
                and parse_result.get("retryable", False)
                and attempt_number < MAX_LIVE_ATTEMPTS
            )
            if should_retry:
                metrics["provider_retry_count"] += 1
                retry_status = "retry_scheduled"
            elif parse_result["success"] and attempt_number > 1:
                retry_status = "retry_succeeded"
            elif parse_result["success"]:
                retry_status = "not_retried_success"
            elif attempt_number > 1:
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
    return _sort_attention_rows(rows), audit_rows, dict(metrics), provider_results


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
            "logical_sheet_id": "SESSION_ATTENTION_MAP",
            "physical_sheet_name": OUTPUT_MAP_SHEET,
            "sheet_role": "provider_attention_capture",
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
            "created_phase": "PreSignal v2.0 Phase 2A",
            "notes": "shadow_v0 provider attention capture live-hardened",
        },
        {
            "logical_sheet_id": "SESSION_ATTENTION_SUMMARY",
            "physical_sheet_name": OUTPUT_SUMMARY_SHEET,
            "sheet_role": "provider_attention_summary",
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
            "created_phase": "PreSignal v2.0 Phase 2A",
            "notes": "shadow_v0 provider attention summary live-hardened",
        },
        {
            "logical_sheet_id": "SESSION_ATTENTION_PROVIDER_RESPONSE_AUDIT",
            "physical_sheet_name": OUTPUT_AUDIT_SHEET,
            "sheet_role": "provider_response_audit",
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
            "created_phase": "PreSignal v2.0 Phase 2D",
            "notes": "shadow_v0 provider response audit",
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


def _run_attention_sanity_checks(
    map_rows: Sequence[Dict[str, Any]],
    valid_sessions: Sequence[Dict[str, Any]],
    members_by_session: Dict[str, List[Dict[str, Any]]],
    provider_requests: Sequence[Dict[str, Any]],
    registry_result: Dict[str, Any],
) -> Dict[str, Any]:
    del valid_sessions

    checks: List[Tuple[str, bool, str]] = []
    expected_keys = set()
    for request in provider_requests:
        session_id = request["session_id"]
        provider = request["provider"]
        for member_row in members_by_session.get(session_id, []):
            expected_keys.add((session_id, provider, _norm(member_row.get("event_id"))))

    row_keys = [(_norm(r.get("session_id")), _norm(r.get("provider")), _norm(r.get("event_id"))) for r in map_rows]
    row_key_counts = Counter(row_keys)
    duplicate_keys = sorted([key for key, count in row_key_counts.items() if count > 1])
    missing_keys = sorted(expected_keys - set(row_key_counts))
    extra_keys = sorted(set(row_key_counts) - expected_keys)

    checks.append(
        (
            "every_processed_session_provider_event_has_one_row",
            not missing_keys and not extra_keys and all(count == 1 for count in row_key_counts.values()),
            f"missing={len(missing_keys)} extra={len(extra_keys)} duplicates={len(duplicate_keys)}",
        )
    )
    checks.append(
        (
            "no_duplicate_session_provider_event_rows",
            not duplicate_keys,
            f"duplicate_keys={len(duplicate_keys)}",
        )
    )

    invalid_label_rows = [row for row in map_rows if _upper(row.get("attention_label")) not in ALLOWED_ATTENTION_LABELS]
    checks.append(("all_attention_labels_allowed", not invalid_label_rows, f"invalid_rows={len(invalid_label_rows)}"))

    primary_without_rank = [
        row for row in map_rows if _upper(row.get("attention_label")) == "PRIMARY_DRIVER" and _safe_int(row.get("attention_rank")) <= 0
    ]
    checks.append(
        ("every_primary_driver_has_rank", not primary_without_rank, f"primary_without_rank={len(primary_without_rank)}")
    )

    low_signal_provider_pairs = []
    provider_group_counts: Dict[Tuple[str, str], Counter] = defaultdict(Counter)
    for row in map_rows:
        provider_group_counts[(_norm(row.get("session_id")), _norm(row.get("provider")))].update([_upper(row.get("attention_label"))])
    for key, counts in provider_group_counts.items():
        substantive = sum(
            counts.get(label, 0)
            for label in ["PRIMARY_DRIVER", "SECONDARY_DRIVER", "WATCHLIST", "CONTEXT_ONLY"]
        )
        if substantive == 0:
            low_signal_provider_pairs.append(key)
    checks.append(
        (
            "provider_has_at_least_one_substantive_item",
            not low_signal_provider_pairs,
            f"low_signal_provider_pairs={len(low_signal_provider_pairs)}",
        )
    )

    forbidden_rows = [row for row in map_rows if _find_forbidden_output_paths(row)]
    checks.append(("no_forecast_direction_fields_in_output_rows", not forbidden_rows, f"forbidden_rows={len(forbidden_rows)}"))
    checks.append(("predictions_not_written", True, "python script writes only diagnostics/registry sheets"))
    checks.append(("event_not_written", True, "python script reads Event-derived diagnostics only"))
    checks.append(
        (
            "sheet_registry_contains_output_entries",
            (registry_result.get("updated", 0) + registry_result.get("appended", 0)) >= 3,
            f"registry_updated={registry_result}",
        )
    )

    return {
        "passed": all(passed for _, passed, _ in checks),
        "checks": checks,
        "missing_key_count": len(missing_keys),
        "extra_key_count": len(extra_keys),
        "duplicate_key_count": len(duplicate_keys),
        "primary_without_rank_count": len(primary_without_rank),
        "low_signal_provider_pair_count": len(low_signal_provider_pairs),
    }


def _build_summary_row(
    generated_ts: str,
    run_id: str,
    sessions_read: int,
    member_rows_read: int,
    valid_sessions: Sequence[Dict[str, Any]],
    provider_requests: Sequence[Dict[str, Any]],
    map_rows: Sequence[Dict[str, Any]],
    audit_rows: Sequence[Dict[str, Any]],
    registry_result: Dict[str, Any],
    mode: str,
    sanity_row: Dict[str, Any],
    output_sanity: Optional[Dict[str, Any]] = None,
    metrics: Optional[Dict[str, int]] = None,
    provider_results: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    metrics = metrics or _empty_metrics()
    output_sanity = output_sanity or {"passed": True, "checks": []}
    provider_results = list(provider_results or [])

    label_counts = Counter(_upper(row.get("attention_label")) for row in map_rows)
    providers_succeeded = sum(1 for result in provider_results if result.get("success"))
    providers_failed = len(provider_results) - providers_succeeded

    if mode == "mock":
        build_status = "MOCK_CONTRACT_PASS" if providers_failed == 0 else "MOCK_CONTRACT_PASS_WITH_WARNINGS"
        final_interpretation = "SESSION_ATTENTION_CONTRACT_READY"
        notes = (
            "mode=mock; provider_calls=0; "
            f"payloads_prepared={len(provider_requests)}; "
            f"providers={json.dumps([req['provider'] for req in provider_requests], ensure_ascii=True)}; "
            f"sanity_final_interpretation={_norm(sanity_row.get('final_interpretation'))}; "
            "mock_contract_checks=labels,omissions,duplicates,forbidden_fields"
        )
    elif mode == "live":
        if providers_succeeded == 0:
            build_status = "FAIL"
            final_interpretation = "SESSION_ATTENTION_CAPTURE_FAILED"
        elif providers_failed > 0 or not output_sanity.get("passed", False):
            build_status = "PASS_WITH_WARNINGS"
            final_interpretation = "SESSION_ATTENTION_CAPTURE_NEEDS_REVIEW"
        else:
            build_status = "PASS"
            final_interpretation = "SESSION_ATTENTION_CAPTURE_READY"
        failed_checks = [name for name, passed, _detail in output_sanity.get("checks", []) if not passed]
        notes = (
            f"mode=live; provider_calls={len(provider_requests)}; "
            f"payloads_prepared={len(provider_requests)}; "
            f"providers={json.dumps([req['provider'] for req in provider_requests], ensure_ascii=True)}; "
            f"sanity_final_interpretation={_norm(sanity_row.get('final_interpretation'))}; "
            f"output_sanity_passed={output_sanity.get('passed', False)}; "
            f"failed_checks={json.dumps(failed_checks, ensure_ascii=True)}"
        )
    else:
        build_status = "SCAFFOLD_PASS"
        final_interpretation = "SESSION_ATTENTION_SCAFFOLD_READY"
        notes = (
            "dry_run=TRUE; provider_calls=0; "
            f"payloads_prepared={len(provider_requests)}; "
            f"providers={json.dumps([req['provider'] for req in provider_requests], ensure_ascii=True)}; "
            f"sanity_final_interpretation={_norm(sanity_row.get('final_interpretation'))}"
        )

    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "shadow_version": SHADOW_VERSION,
        "attention_run_id": run_id,
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "sessions_read": sessions_read,
        "sessions_processed": len(valid_sessions),
        "providers_attempted": len(provider_requests),
        "providers_succeeded": providers_succeeded,
        "providers_failed": providers_failed,
        "session_member_rows_read": member_rows_read,
        "attention_rows_written": len(map_rows),
        "primary_driver_count": label_counts.get("PRIMARY_DRIVER", 0),
        "secondary_driver_count": label_counts.get("SECONDARY_DRIVER", 0),
        "watchlist_count": label_counts.get("WATCHLIST", 0),
        "context_only_count": label_counts.get("CONTEXT_ONLY", 0),
        "ignore_count": label_counts.get("IGNORE", 0),
        "no_signal_count": label_counts.get("NO_SIGNAL", 0),
        "provider_omission_count": metrics.get("provider_omission_count", 0),
        "invalid_label_count": metrics.get("invalid_label_count", 0),
        "duplicate_provider_event_count": metrics.get("duplicate_provider_event_count", 0),
        "registry_updated": "TRUE" if registry_result.get("updated", 0) or registry_result.get("appended", 0) else "FALSE",
        "governance_status": "DERIVED_ONLY_SHADOW_SAFE",
        "notes": notes,
        "provider_parse_error_count": metrics.get("provider_parse_error_count", 0),
        "provider_contract_error_count": metrics.get("provider_contract_error_count", 0),
        "provider_retry_count": metrics.get("provider_retry_count", 0),
        "provider_recovery_success_count": metrics.get("provider_recovery_success_count", 0),
        "provider_recovery_failed_count": metrics.get("provider_recovery_failed_count", 0),
        "provider_response_audit_rows_written": len(audit_rows),
    }


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the Session Attention Map v0 in scaffold, mock, or live mode."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scaffold mode only; build provider payloads and write empty output sheets.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run contract validation in mock mode with fake provider outputs and no live AI calls.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run live provider calls through the Apps Script execution API using existing project key resolution.",
    )
    return parser.parse_args(argv)


def build_session_attention_map_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    if args is None:
        args = _parse_args([])

    mode = "live" if getattr(args, "live", False) else "mock" if args.mock else "dry_run"
    creds = load_credentials(interactive=False)
    service = build_sheets_service(creds)
    generated_ts = _iso_now()
    run_id = _attention_run_id(generated_ts)

    session_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, PHASE1_SESSION_SHEET)
    member_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, PHASE1_MEMBER_SHEET)
    sanity_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, PHASE1_SANITY_SUMMARY_SHEET)
    sanity_row, valid_sessions, members_by_session = _validate_phase1_inputs(session_rows, member_rows, sanity_rows)

    config_map = _read_config_map(service)
    providers = _resolve_provider_candidates(config_map)
    if not providers:
        raise RuntimeError("No provider candidates were resolved from Config/defaults for attention preparation.")

    provider_requests = _build_provider_requests(valid_sessions, members_by_session, providers)
    if not provider_requests:
        raise RuntimeError("No provider requests were prepared from the validated market session inputs.")

    map_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_MAP_SHEET, MAP_HEADERS)
    summary_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)
    audit_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_AUDIT_SHEET, AUDIT_HEADERS)

    if mode == "mock":
        map_rows, audit_rows, metrics, provider_results = _run_mock_contracts(
            generated_ts,
            run_id,
            valid_sessions,
            members_by_session,
            provider_requests,
        )
        output_sanity = {"passed": True, "checks": []}
    elif mode == "live":
        script_service = build_script_service(creds)
        script_id = default_script_id()
        map_rows, audit_rows, metrics, provider_results = _run_live_contracts(
            generated_ts,
            run_id,
            valid_sessions,
            members_by_session,
            provider_requests,
            script_service,
            script_id,
        )
        output_sanity = {"passed": True, "checks": []}
    else:
        map_rows = []
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

    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_MAP_SHEET, map_headers, map_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_AUDIT_SHEET, audit_headers, audit_rows)
    registry_result = _upsert_registry_rows(service)
    if mode == "live":
        output_sanity = _run_attention_sanity_checks(
            map_rows,
            valid_sessions,
            members_by_session,
            provider_requests,
            registry_result,
        )
    summary_row = _build_summary_row(
        generated_ts,
        run_id,
        len(session_rows),
        len(member_rows),
        valid_sessions,
        provider_requests,
        map_rows,
        audit_rows,
        registry_result,
        mode,
        sanity_row,
        output_sanity,
        metrics,
        provider_results,
    )
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, [summary_row])

    return {
        "generated_ts": generated_ts,
        "attention_run_id": run_id,
        "mode": mode,
        "sessions_read": len(session_rows),
        "sessions_processed": len(valid_sessions),
        "members_read": len(member_rows),
        "providers_attempted": len(provider_requests),
        "providers_succeeded": summary_row["providers_succeeded"],
        "providers_failed": summary_row["providers_failed"],
        "payloads_prepared": len(provider_requests),
        "attention_rows_written": len(map_rows),
        "provider_omission_count": summary_row["provider_omission_count"],
        "invalid_label_count": summary_row["invalid_label_count"],
        "duplicate_provider_event_count": summary_row["duplicate_provider_event_count"],
        "provider_parse_error_count": summary_row["provider_parse_error_count"],
        "provider_contract_error_count": summary_row["provider_contract_error_count"],
        "provider_retry_count": summary_row["provider_retry_count"],
        "provider_recovery_success_count": summary_row["provider_recovery_success_count"],
        "provider_recovery_failed_count": summary_row["provider_recovery_failed_count"],
        "provider_response_audit_rows_written": summary_row["provider_response_audit_rows_written"],
        "build_status": summary_row["build_status"],
        "final_interpretation": summary_row["final_interpretation"],
        "output_sheets": [OUTPUT_MAP_SHEET, OUTPUT_SUMMARY_SHEET, OUTPUT_AUDIT_SHEET],
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
        "sample_map_row": map_rows[0] if map_rows else {},
        "sample_audit_row": audit_rows[0] if audit_rows else {},
    }


def main() -> None:
    print(json.dumps(build_session_attention_map_v0(_parse_args()), ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
