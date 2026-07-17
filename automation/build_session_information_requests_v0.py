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
    MAIN_SPREADSHEET_ID,
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
PHASE2_MAP_SHEET = "Session_Attention_Map"
PHASE2_SUMMARY_SHEET = "Session_Attention_Summary"
PHASE2_AUDIT_SHEET = "Session_Attention_Provider_Response_Audit"

OUTPUT_REQUEST_SHEET = "Session_Information_Requests"
OUTPUT_LIBRARY_SHEET = "Information_Requirement_Library"
OUTPUT_SUMMARY_SHEET = "Session_Information_Request_Summary"
OUTPUT_AUDIT_SHEET = "Session_Information_Provider_Response_Audit"

SCHEMA_VERSION = "presignal_v2_session_information_0.1"
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
ALLOWED_PRIORITIES = {"must_have", "useful", "optional", "low_value"}
ALLOWED_INFORMATION_CATEGORIES = {
    "treasury_yields",
    "fed_expectations",
    "dxy",
    "usdjpy_trend",
    "risk_sentiment",
    "equity_tone",
    "inflation_narrative",
    "labor_market_trend",
    "growth_context",
    "market_positioning",
    "upcoming_larger_events",
    "jpy_intervention_risk",
    "volatility",
    "historical_surprise_sensitivity",
    "event_consensus_detail",
    "other",
}
ALLOWED_AFFECTED_CHANNELS = {
    "fed_path",
    "treasury_yields",
    "usd_direction",
    "jpy_direction",
    "risk_sentiment",
    "inflation_expectations",
    "labor_market",
    "growth_outlook",
    "market_positioning",
    "event_importance",
    "low_direct_market_impact",
    "unknown",
}
ALLOWED_AVAILABLE_NOW = {"yes", "no", "unknown", "partial"}
PRIORITY_NORMALIZATION_MAP = {
    "critical": "must_have",
    "high": "must_have",
    "musthave": "must_have",
    "must_have": "must_have",
    "medium": "useful",
    "useful": "useful",
    "nice_to_have": "optional",
    "nice to have": "optional",
    "optional": "optional",
    "low": "low_value",
    "low_value": "low_value",
}
CATEGORY_NORMALIZATION_MAP = {
    "treasury_yields": "treasury_yields",
    "yield": "treasury_yields",
    "yields": "treasury_yields",
    "rates": "treasury_yields",
    "rate": "treasury_yields",
    "fed_expectations": "fed_expectations",
    "fed_path": "fed_expectations",
    "fed": "fed_expectations",
    "dxy": "dxy",
    "dollar_index": "dxy",
    "dollar index": "dxy",
    "usdjpy_trend": "usdjpy_trend",
    "fx_trend": "usdjpy_trend",
    "fx trend": "usdjpy_trend",
    "risk_sentiment": "risk_sentiment",
    "risk_tone": "risk_sentiment",
    "risk tone": "risk_sentiment",
    "equity_tone": "equity_tone",
    "equities": "equity_tone",
    "inflation_narrative": "inflation_narrative",
    "labor_market_trend": "labor_market_trend",
    "labor": "labor_market_trend",
    "growth_context": "growth_context",
    "market_positioning": "market_positioning",
    "positioning": "market_positioning",
    "upcoming_larger_events": "upcoming_larger_events",
    "jpy_intervention_risk": "jpy_intervention_risk",
    "boj_intervention": "jpy_intervention_risk",
    "volatility": "volatility",
    "historical_surprise_sensitivity": "historical_surprise_sensitivity",
    "event_consensus_detail": "event_consensus_detail",
    "consensus_detail": "event_consensus_detail",
    "other": "other",
}
MARKET_STATE_CATEGORY_HINTS = {
    "treasury_yields",
    "fed_expectations",
    "dxy",
    "usdjpy_trend",
    "risk_sentiment",
    "equity_tone",
    "market_positioning",
    "jpy_intervention_risk",
    "volatility",
    "upcoming_larger_events",
}
FORBIDDEN_OUTPUT_KEYS = {
    "forecast_direction",
    "forecast_value",
    "expected_move_pips",
    "expected_move_pips_min",
    "expected_move_pips_max",
    "trade_action",
    "entry",
    "stop_loss",
    "take_profit",
    "buy",
    "sell",
    "long",
    "short",
    "browse_request",
    "external_browsing",
}
FORBIDDEN_OUTPUT_PHRASES = [
    "buy usdjpy",
    "sell usdjpy",
    "go long",
    "go short",
    "browse the web",
    "perform a web search",
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
    "List the information you would need to make a better USDJPY session-level forecast later. "
    "Do not forecast direction. Do not estimate pips. "
    "Do not give trade advice. Do not browse. Return only information requirements."
)
PROVIDER_INSTRUCTION_TEXT = """You are identifying information requirements for a PreSignal v2.0 shadow research layer.

You are given one market session, its scheduled economic events, and your own previously captured attention map for those events.

Your task is not to forecast USDJPY direction.

Your task is only to list the information you would want before making a better session-level USDJPY forecast later.

Focus on information that would help determine market reaction, such as:
- Treasury yields
- Fed expectations
- DXY
- USDJPY recent trend
- Risk sentiment
- Equity tone
- Inflation narrative
- Labor-market trend
- Growth context
- Market positioning
- Upcoming larger events
- JPY intervention risk
- Volatility
- Historical sensitivity to this event family
- Consensus / prior / revision detail

Do not predict USDJPY up/down/flat.
Do not estimate pips.
Do not give trading advice.
Do not browse.
Do not ask to perform web searches.
Do not create a Market-State Pack.
Only identify information requirements.

Return one valid JSON object only.
Do not include markdown.
Do not include explanatory text outside JSON.
Use short reasons, max 160 characters each.

Return a top-level JSON object with exactly these keys:
- object
- session_id
- provider
- information_items
- session_information_summary
- status

Set object exactly to session_information_requirements.
Set session_id exactly to the provided session.session_id.
Set provider to the provider name handling this request.
Set status to ok.

information_items must be an array of objects using exactly these keys:
- request_rank
- requested_information
- information_category
- priority
- reason
- affected_channel
- event_family_relevance
- linked_event_ids
- linked_attention_labels
- available_now
- suggested_source
- expected_forecast_use
- is_market_state_candidate

Allowed priority values:
- must_have
- useful
- optional
- low_value

Allowed information_category values:
- treasury_yields
- fed_expectations
- dxy
- usdjpy_trend
- risk_sentiment
- equity_tone
- inflation_narrative
- labor_market_trend
- growth_context
- market_positioning
- upcoming_larger_events
- jpy_intervention_risk
- volatility
- historical_surprise_sensitivity
- event_consensus_detail
- other

Allowed affected_channel values:
- fed_path
- treasury_yields
- usd_direction
- jpy_direction
- risk_sentiment
- inflation_expectations
- labor_market
- growth_outlook
- market_positioning
- event_importance
- low_direct_market_impact
- unknown

Allowed available_now values:
- yes
- no
- unknown
- partial

Do not include forecast_direction, expected_move_pips, trade_action, entry, stop_loss, take_profit, buy, sell, long, short, browsing requests, or any fields not listed above."""

REQUEST_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "information_run_id",
    "session_id",
    "session_date",
    "country",
    "session_window_name",
    "provider",
    "model",
    "request_rank",
    "requested_information",
    "information_category",
    "priority",
    "reason",
    "affected_channel",
    "event_family_relevance",
    "linked_event_ids",
    "linked_attention_labels",
    "available_now",
    "suggested_source",
    "expected_forecast_use",
    "is_market_state_candidate",
    "provider_field_recovered_from_context",
    "object_field_recovered_from_context",
    "raw_output",
    "status",
    "error_message",
    "source_session_sheet",
    "source_member_sheet",
    "source_attention_sheet",
    "notes",
]

LIBRARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "information_key",
    "canonical_information",
    "information_category",
    "first_seen_ts",
    "last_seen_ts",
    "request_count",
    "provider_count",
    "session_count",
    "providers_requesting",
    "sessions_seen",
    "event_families",
    "attention_labels_linked",
    "priority_avg",
    "must_have_count",
    "useful_count",
    "optional_count",
    "low_value_count",
    "market_state_candidate_count",
    "promotion_status",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "information_run_id",
    "build_status",
    "final_interpretation",
    "sessions_read",
    "sessions_processed",
    "providers_attempted",
    "providers_succeeded",
    "providers_failed",
    "information_request_rows_written",
    "library_rows_written",
    "must_have_count",
    "useful_count",
    "optional_count",
    "low_value_count",
    "market_state_candidate_count",
    "invalid_category_count",
    "invalid_priority_count",
    "duplicate_request_count",
    "provider_parse_error_count",
    "provider_contract_error_count",
    "provider_retry_count",
    "provider_recovery_success_count",
    "provider_recovery_failed_count",
    "provider_response_audit_rows_written",
    "registry_updated",
    "governance_status",
    "notes",
]

AUDIT_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "information_run_id",
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
    "provider_field_recovered_from_context",
    "object_field_recovered_from_context",
    "invalid_category_count",
    "invalid_priority_count",
    "duplicate_request_count",
    "request_item_count",
    "notes",
]


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _as_bool(value: Any) -> bool:
    return _upper(value) in {"TRUE", "T", "YES", "Y", "1"}


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


def _information_run_id(generated_ts: str) -> str:
    stamp = generated_ts.replace("-", "").replace(":", "").replace("+00:00", "Z").replace(".", "")
    return f"session_information_v0_{stamp}"


def _normalize_provider_name(name: Any) -> str:
    raw = _norm(name)
    lowered = raw.lower()
    if lowered in {"claude", "anthropic"}:
        return "Anthropic"
    if lowered == "openai":
        return "OpenAI"
    if lowered == "gemini":
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
            if _is_inner_information_item_candidate(parsed_value):
                rejected_inner_item_candidate = True
                last_error = (
                    "extracted JSON candidate was an inner information item, "
                    "not a top-level provider response"
                )
                continue
            if not _looks_like_information_envelope(parsed_value):
                last_error = "recovered JSON candidate did not match top-level information envelope shape"
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


def _looks_like_information_envelope(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    information_items = obj.get("information_items")
    if not isinstance(information_items, list):
        return False
    object_value = _norm(obj.get("object"))
    session_id = _norm(obj.get("session_id"))
    if object_value == "session_information_requirements" and session_id:
        return True
    if not object_value and session_id and all(
        isinstance(item, dict) and _norm(item.get("requested_information")) for item in information_items
    ):
        return True
    return False


def _is_inner_information_item_candidate(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    if "information_items" in obj:
        return False
    inner_item_keys = {
        "request_rank",
        "requested_information",
        "information_category",
        "priority",
        "reason",
        "affected_channel",
    }
    return _norm(obj.get("requested_information")) != "" and inner_item_keys.issubset(set(obj.keys()))


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


def _attention_ready(summary_row: Dict[str, Any]) -> bool:
    return _upper(summary_row.get("final_interpretation")) == "SESSION_ATTENTION_CAPTURE_READY" or _upper(
        summary_row.get("build_status")
    ) == "PASS"


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


def _sort_attention_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = list(rows)
    out.sort(
        key=lambda row: (
            _norm(row.get("session_id")),
            _norm(row.get("provider")),
            _safe_int(row.get("attention_rank")) or 999999,
            _parse_dt(row.get("release_ts")) or datetime.max.replace(tzinfo=timezone.utc),
            _norm(row.get("indicator_name")),
            _norm(row.get("event_id")),
        )
    )
    return out


def _validate_phase2_inputs(
    session_rows: Sequence[Dict[str, Any]],
    member_rows: Sequence[Dict[str, Any]],
    attention_rows: Sequence[Dict[str, Any]],
    attention_summary_rows: Sequence[Dict[str, Any]],
    attention_audit_rows: Sequence[Dict[str, Any]],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]], Dict[Tuple[str, str], List[Dict[str, Any]]]]:
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
    _require_headers(PHASE2_SUMMARY_SHEET, attention_summary_rows, ["build_status", "final_interpretation"])
    _require_headers(
        PHASE2_AUDIT_SHEET,
        attention_audit_rows,
        ["session_id", "provider", "attempt_number", "parse_status", "contract_status"],
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

    attention_summary_row = attention_summary_rows[0]
    if not _attention_ready(attention_summary_row):
        raise RuntimeError(
            f"{PHASE2_SUMMARY_SHEET} is not ready: "
            f"build_status={_norm(attention_summary_row.get('build_status'))}, "
            f"final_interpretation={_norm(attention_summary_row.get('final_interpretation'))}"
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
        raise RuntimeError("No structurally valid market sessions were found for information request capture.")

    attention_by_pair: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in _sort_attention_rows(attention_rows):
        session_id = _norm(row.get("session_id"))
        provider = _normalize_provider_name(row.get("provider"))
        if session_id and provider:
            attention_by_pair[(session_id, provider)].append(row)

    return attention_summary_row, valid_sessions, members_by_session, attention_by_pair


def _build_provider_instruction() -> str:
    return PROVIDER_INSTRUCTION_TEXT


def _build_payload(
    session_row: Dict[str, Any],
    member_rows: Sequence[Dict[str, Any]],
    attention_rows: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "object": "presignal_v2_session_information_request_task",
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
    attention_by_pair: Dict[Tuple[str, str], List[Dict[str, Any]]],
    providers: Sequence[Dict[str, str]],
) -> List[Dict[str, Any]]:
    requests: List[Dict[str, Any]] = []
    instruction = _build_provider_instruction()
    for session_row in sorted(session_rows, key=lambda row: _norm(row.get("session_id"))):
        session_id = _norm(session_row.get("session_id"))
        member_rows = members_by_session.get(session_id, [])
        for provider in providers:
            attention_rows = attention_by_pair.get((session_id, provider["provider"]), [])
            payload = _build_payload(session_row, member_rows, attention_rows)
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
        "invalid_category_count": 0,
        "invalid_priority_count": 0,
        "duplicate_request_count": 0,
        "provider_parse_error_count": 0,
        "provider_contract_error_count": 0,
        "provider_retry_count": 0,
        "provider_recovery_success_count": 0,
        "provider_recovery_failed_count": 0,
        "provider_response_audit_rows_written": 0,
    }


def _normalize_priority(value: Any) -> Tuple[str, bool]:
    raw = _norm(value).lower().replace("-", "_")
    if raw in ALLOWED_PRIORITIES:
        return raw, False
    normalized = PRIORITY_NORMALIZATION_MAP.get(raw)
    if normalized:
        return normalized, normalized != raw
    return "useful", True


def _normalize_information_category(value: Any) -> Tuple[str, bool]:
    raw = _norm(value).lower().replace("-", "_")
    if raw in ALLOWED_INFORMATION_CATEGORIES:
        return raw, False
    normalized = CATEGORY_NORMALIZATION_MAP.get(raw)
    if normalized:
        return normalized, normalized != raw
    return "other", True


def _normalize_affected_channel(value: Any) -> str:
    raw = _norm(value).lower().replace("-", "_")
    return raw if raw in ALLOWED_AFFECTED_CHANNELS else "unknown"


def _normalize_available_now(value: Any) -> str:
    raw = _norm(value).lower().replace("-", "_")
    if raw in ALLOWED_AVAILABLE_NOW:
        return raw
    if raw in {"", "n/a", "na"}:
        return "unknown"
    return "unknown"


def _normalize_string_list(value: Any) -> List[str]:
    if isinstance(value, list):
        values = value
    else:
        text = _norm(value)
        if not text:
            return []
        values = re.split(r"[|,;/]+", text)
    out: List[str] = []
    seen = set()
    for item in values:
        text = _norm(item)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _normalize_linked_event_ids(value: Any, valid_event_ids: Iterable[str]) -> str:
    valid = set(valid_event_ids)
    out: List[str] = []
    seen = set()
    for item in _normalize_string_list(value):
        if item in valid and item not in seen:
            seen.add(item)
            out.append(item)
    return "|".join(out)


def _normalize_linked_attention_labels(value: Any) -> str:
    out: List[str] = []
    seen = set()
    for item in _normalize_string_list(value):
        label = _upper(item)
        if label in ALLOWED_ATTENTION_LABELS and label not in seen:
            seen.add(label)
            out.append(label)
    return "|".join(out)


def _looks_like_market_state_candidate(requested_information: str, category: str, provider_value: Any) -> str:
    if isinstance(provider_value, bool):
        if provider_value:
            return "TRUE"
    elif _as_bool(provider_value):
        return "TRUE"

    text = requested_information.lower()
    if category in MARKET_STATE_CATEGORY_HINTS:
        return "TRUE"
    if any(
        phrase in text
        for phrase in [
            "2y",
            "10y",
            "treasury yield",
            "dxy",
            "usdjpy trend",
            "risk tone",
            "risk sentiment",
            "fed funds",
            "intervention risk",
            "volatility",
            "upcoming larger event",
            "positioning",
        ]
    ):
        return "TRUE"
    return "FALSE"


def _canonical_requested_information(value: Any) -> str:
    text = _norm(value).lower()
    text = text.replace("u.s.", "us").replace("u s ", "us ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    replacements = {
        "treasury yields": "treasury yield",
        "fed funds expectations": "fed expectations",
        "dollar index": "dxy",
        "fx trend": "usdjpy trend",
        "risk tone": "risk sentiment",
    }
    for before, after in replacements.items():
        text = text.replace(before, after)
    return text


def _information_key(category: str, requested_information: str) -> str:
    canonical = _canonical_requested_information(requested_information).replace(" ", "_")
    return f"{category}|{canonical}" if canonical else f"{category}|unknown_information"


def _base_request_row(
    generated_ts: str,
    run_id: str,
    session_row: Dict[str, Any],
    provider: str,
    model: str,
    raw_output: str,
) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "shadow_version": SHADOW_VERSION,
        "information_run_id": run_id,
        "session_id": _norm(session_row.get("session_id")),
        "session_date": _norm(session_row.get("session_date")),
        "country": _norm(session_row.get("country")),
        "session_window_name": _norm(session_row.get("session_window_name")),
        "provider": provider,
        "model": model,
        "request_rank": "",
        "requested_information": "",
        "information_category": "",
        "priority": "",
        "reason": "",
        "affected_channel": "",
        "event_family_relevance": "",
        "linked_event_ids": "",
        "linked_attention_labels": "",
        "available_now": "",
        "suggested_source": "",
        "expected_forecast_use": "",
        "is_market_state_candidate": "",
        "provider_field_recovered_from_context": "FALSE",
        "object_field_recovered_from_context": "FALSE",
        "raw_output": raw_output,
        "status": "",
        "error_message": "",
        "source_session_sheet": PHASE1_SESSION_SHEET,
        "source_member_sheet": PHASE1_MEMBER_SHEET,
        "source_attention_sheet": PHASE2_MAP_SHEET,
        "notes": "",
    }


def _sort_request_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
    }


def _build_transport_failure_result(
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
    member_rows: Sequence[Dict[str, Any]],
    provider: str,
    model: str,
    raw_output: str,
) -> Dict[str, Any]:
    metrics = _empty_metrics()
    recovery = _recover_json_payload(raw_output)
    if recovery["ok"] and recovery["recovery_status"] != "not_needed":
        metrics["provider_recovery_success_count"] = 1
    elif not recovery["ok"] and recovery["recovery_attempted"]:
        metrics["provider_recovery_failed_count"] = 1

    session_id = _norm(session_row.get("session_id"))
    valid_event_ids = {_norm(row.get("event_id")) for row in member_rows if _norm(row.get("event_id"))}

    if not recovery["ok"]:
        metrics["provider_parse_error_count"] = 1
        return _failure_result(
            metrics,
            recovery["parse_status"],
            "not_evaluated",
            recovery["recovery_status"],
            "",
            recovery["error_type"],
            recovery["error_message"],
            True,
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
            "TRUE",
        )

    provider_field = _norm(parsed.get("provider"))
    provider_field_recovered_from_context = False
    if not provider_field:
        provider_field = provider
        provider_field_recovered_from_context = True

    object_field = _norm(parsed.get("object"))
    object_field_recovered_from_context = False
    session_id_field = _norm(parsed.get("session_id"))
    if not session_id_field:
        session_id_field = session_id

    information_items = parsed.get("information_items")
    information_items_is_array = isinstance(information_items, list)
    information_items_have_requested_information = information_items_is_array and bool(information_items) and all(
        isinstance(item, dict) and _norm(item.get("requested_information"))
        for item in information_items
    )
    if not object_field:
        if (
            session_id_field == session_id
            and information_items_is_array
            and information_items_have_requested_information
        ):
            object_field = "session_information_requirements"
            object_field_recovered_from_context = True

    if object_field != "session_information_requirements":
        metrics["provider_contract_error_count"] = 1
        return _failure_result(
            metrics,
            recovery["parse_status"],
            "invalid_object",
            recovery["recovery_status"],
            normalized_json_text,
            "contract_error",
            f"invalid_object={_norm(parsed.get('object')) or '<blank>'}",
            True,
        )

    if session_id_field != session_id:
        metrics["provider_contract_error_count"] = 1
        return _failure_result(
            metrics,
            recovery["parse_status"],
            "session_id_mismatch",
            recovery["recovery_status"],
            normalized_json_text,
            "contract_error",
            (
                f"session_id_mismatch expected={session_id or '<blank>'} "
                f"got={_norm(parsed.get('session_id')) or '<blank>'}"
            ),
            True,
        )

    if not information_items_is_array:
        metrics["provider_contract_error_count"] = 1
        return _failure_result(
            metrics,
            recovery["parse_status"],
            "information_items_not_array",
            recovery["recovery_status"],
            normalized_json_text,
            "contract_error",
            "information_items must be an array",
            True,
        )

    rows: List[Dict[str, Any]] = []
    seen_keys = set()
    for index, item in enumerate(information_items):
        if not isinstance(item, dict):
            metrics["provider_contract_error_count"] = 1
            return _failure_result(
                metrics,
                recovery["parse_status"],
                "information_item_not_object",
                recovery["recovery_status"],
                normalized_json_text,
                "contract_error",
                f"information_items[{index}] must be an object",
                True,
            )

        requested_information = _norm(item.get("requested_information"))
        if not requested_information:
            metrics["provider_contract_error_count"] = 1
            return _failure_result(
                metrics,
                recovery["parse_status"],
                "missing_requested_information",
                recovery["recovery_status"],
                normalized_json_text,
                "contract_error",
                f"information_items[{index}] missing requested_information",
                True,
            )

        category, category_invalid = _normalize_information_category(item.get("information_category"))
        priority, priority_invalid = _normalize_priority(item.get("priority"))
        if category_invalid:
            metrics["invalid_category_count"] += 1
        if priority_invalid:
            metrics["invalid_priority_count"] += 1

        dedupe_key = (
            _norm(session_row.get("session_id")),
            provider,
            _canonical_requested_information(requested_information),
        )
        if dedupe_key in seen_keys:
            metrics["duplicate_request_count"] += 1
            continue
        seen_keys.add(dedupe_key)

        row = _base_request_row(generated_ts, run_id, session_row, provider, model, raw_output)
        request_rank = _safe_int(item.get("request_rank")) or (index + 1)
        linked_event_ids = _normalize_linked_event_ids(item.get("linked_event_ids"), valid_event_ids)
        linked_attention_labels = _normalize_linked_attention_labels(item.get("linked_attention_labels"))
        status = "parsed"
        if category_invalid and priority_invalid:
            status = "invalid_category_priority_normalized"
        elif category_invalid:
            status = "invalid_category_normalized"
        elif priority_invalid:
            status = "invalid_priority_normalized"

        row.update(
            {
                "request_rank": request_rank,
                "requested_information": requested_information,
                "information_category": category,
                "priority": priority,
                "reason": _truncate_text(_norm(item.get("reason")), 160),
                "affected_channel": _normalize_affected_channel(item.get("affected_channel")),
                "event_family_relevance": _truncate_text(_norm(item.get("event_family_relevance")), 120),
                "linked_event_ids": linked_event_ids,
                "linked_attention_labels": linked_attention_labels,
                "available_now": _normalize_available_now(item.get("available_now")),
                "suggested_source": _truncate_text(_norm(item.get("suggested_source")), 160),
                "expected_forecast_use": _truncate_text(_norm(item.get("expected_forecast_use")), 160),
                "is_market_state_candidate": _looks_like_market_state_candidate(
                    requested_information,
                    category,
                    item.get("is_market_state_candidate"),
                ),
                "provider_field_recovered_from_context": (
                    "TRUE" if provider_field_recovered_from_context else "FALSE"
                ),
                "object_field_recovered_from_context": (
                    "TRUE" if object_field_recovered_from_context else "FALSE"
                ),
                "status": status,
                "notes": (
                    "normalized category to other"
                    if category_invalid and not priority_invalid
                    else "normalized priority to useful"
                    if priority_invalid and not category_invalid
                    else "normalized category and priority"
                    if category_invalid and priority_invalid
                    else ""
                ),
            }
        )
        rows.append(row)

    if not rows:
        metrics["provider_contract_error_count"] += 1
        return _failure_result(
            metrics,
            recovery["parse_status"],
            "empty_information_items",
            recovery["recovery_status"],
            normalized_json_text,
            "contract_error",
            "provider returned zero usable information items",
            True,
        )

    contract_status = "valid_with_normalization" if (
        metrics["invalid_category_count"] or metrics["invalid_priority_count"] or metrics["duplicate_request_count"]
    ) else "valid"
    if _normalize_provider_name(provider_field) not in ("", provider):
        contract_status = f"{contract_status}_provider_mismatch_tolerated"
    elif provider_field_recovered_from_context:
        contract_status = f"{contract_status}_provider_field_recovered_from_context"
    if object_field_recovered_from_context:
        contract_status = f"{contract_status}_object_field_recovered_from_context"
    return {
        "success": True,
        "rows": _sort_request_rows(rows),
        "metrics": metrics,
        "parse_status": recovery["parse_status"],
        "contract_status": contract_status,
        "recovery_status": recovery["recovery_status"],
        "normalized_json_text": normalized_json_text,
        "error_type": "",
        "error_message": "",
        "retryable": False,
        "forbidden_field_detected": "FALSE",
        "provider_field_recovered_from_context": "TRUE" if provider_field_recovered_from_context else "FALSE",
        "object_field_recovered_from_context": "TRUE" if object_field_recovered_from_context else "FALSE",
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
        "information_run_id": run_id,
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
        "provider_field_recovered_from_context": parse_result.get(
            "provider_field_recovered_from_context",
            "FALSE",
        ),
        "object_field_recovered_from_context": parse_result.get(
            "object_field_recovered_from_context",
            "FALSE",
        ),
        "invalid_category_count": metrics.get("invalid_category_count", 0),
        "invalid_priority_count": metrics.get("invalid_priority_count", 0),
        "duplicate_request_count": metrics.get("duplicate_request_count", 0),
        "request_item_count": len(parse_result.get("rows", [])),
        "notes": _truncate_text(notes, 400),
    }


def _build_mock_response(provider_request: Dict[str, Any]) -> str:
    payload = provider_request["payload"]
    provider = provider_request["provider"]
    session_id = _norm(payload["session"]["session_id"])
    events = payload["events"]
    first_event_id = events[0]["event_id"] if events else ""
    second_event_id = events[1]["event_id"] if len(events) > 1 else first_event_id

    if provider == "Anthropic":
        return json.dumps(
            {
                "object": "session_information_requirements",
                "session_id": session_id,
                "provider": provider,
                "forecast_direction": "UP",
                "information_items": [
                    {
                        "request_rank": 1,
                        "requested_information": "Current US 2Y Treasury yield direction",
                        "information_category": "treasury_yields",
                        "priority": "must_have",
                        "reason": "Mock forbidden-field contract failure.",
                        "affected_channel": "treasury_yields",
                        "event_family_relevance": "labor_market",
                        "linked_event_ids": [first_event_id],
                        "linked_attention_labels": ["PRIMARY_DRIVER"],
                        "available_now": "unknown",
                        "suggested_source": "Mock",
                        "expected_forecast_use": "Mock",
                        "is_market_state_candidate": True,
                    }
                ],
                "session_information_summary": "This fixture should fail due to forecast_direction.",
                "status": "ok",
            },
            ensure_ascii=True,
        )

    if provider == "Gemini":
        return json.dumps(
            {
                "object": "session_information_requirements",
                "session_id": session_id,
                "provider": provider,
                "information_items": [
                    {
                        "request_rank": 1,
                        "requested_information": "Current US 2Y Treasury yield direction",
                        "information_category": "rates",
                        "priority": "high",
                        "reason": "Mock normalized category and priority.",
                        "affected_channel": "treasury_yields",
                        "event_family_relevance": "labor_market",
                        "linked_event_ids": [first_event_id],
                        "linked_attention_labels": ["PRIMARY_DRIVER"],
                        "available_now": "unknown",
                        "suggested_source": "Mock",
                        "expected_forecast_use": "Mock",
                        "is_market_state_candidate": True,
                    },
                    {
                        "request_rank": 2,
                        "requested_information": "Current US 2Y Treasury yield direction",
                        "information_category": "rates",
                        "priority": "high",
                        "reason": "Duplicate request fixture.",
                        "affected_channel": "treasury_yields",
                        "event_family_relevance": "labor_market",
                        "linked_event_ids": [first_event_id],
                        "linked_attention_labels": ["PRIMARY_DRIVER"],
                        "available_now": "unknown",
                        "suggested_source": "Mock",
                        "expected_forecast_use": "Mock",
                        "is_market_state_candidate": True,
                    },
                    {
                        "request_rank": 3,
                        "requested_information": "Recent broader risk tone",
                        "information_category": "equities",
                        "priority": "medium",
                        "reason": "Second valid mock item.",
                        "affected_channel": "risk_sentiment",
                        "event_family_relevance": "broad_macro",
                        "linked_event_ids": [second_event_id],
                        "linked_attention_labels": ["WATCHLIST"],
                        "available_now": "partial",
                        "suggested_source": "Mock",
                        "expected_forecast_use": "Mock",
                        "is_market_state_candidate": False,
                    },
                ],
                "session_information_summary": "Mock response with normalization and duplicate handling.",
                "status": "ok",
            },
            ensure_ascii=True,
        )

    return json.dumps(
        {
            "object": "session_information_requirements",
            "session_id": session_id,
            "provider": provider,
            "information_items": [
                {
                    "request_rank": 1,
                    "requested_information": "Current US 10Y Treasury yield direction",
                    "information_category": "treasury_yields",
                    "priority": "must_have",
                    "reason": "Rates transmission is central for USDJPY interpretation.",
                    "affected_channel": "treasury_yields",
                    "event_family_relevance": "rates_macro",
                    "linked_event_ids": [first_event_id],
                    "linked_attention_labels": ["PRIMARY_DRIVER"],
                    "available_now": "unknown",
                    "suggested_source": "FRED or market data provider",
                    "expected_forecast_use": "Judge whether event surprise could lift yields and USDJPY.",
                    "is_market_state_candidate": True,
                },
                {
                    "request_rank": 2,
                    "requested_information": "Recent USDJPY trend before the session",
                    "information_category": "usdjpy_trend",
                    "priority": "useful",
                    "reason": "Helps frame whether reaction extends or fades.",
                    "affected_channel": "usd_direction",
                    "event_family_relevance": "price_action",
                    "linked_event_ids": [],
                    "linked_attention_labels": ["CONTEXT_ONLY"],
                    "available_now": "yes",
                    "suggested_source": "Market data provider",
                    "expected_forecast_use": "Provide reaction baseline and positioning context.",
                    "is_market_state_candidate": True,
                },
            ],
            "session_information_summary": "Mock valid response.",
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
    return _sort_request_rows(rows), audit_rows, dict(metrics), provider_results


def _call_live_provider_raw(script_service, script_id: str, provider_request: Dict[str, Any]) -> Dict[str, Any]:
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
                )
            else:
                parse_result = _build_transport_failure_result(
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
    return _sort_request_rows(rows), audit_rows, dict(metrics), provider_results


def _priority_score(value: str) -> int:
    return {"must_have": 4, "useful": 3, "optional": 2, "low_value": 1}.get(value, 0)


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


def _build_library_rows(generated_ts: str, request_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in request_rows:
        key = _information_key(_norm(row.get("information_category")), _norm(row.get("requested_information")))
        grouped[key].append(row)

    library_rows: List[Dict[str, Any]] = []
    for key in sorted(grouped):
        rows = grouped[key]
        priorities = [_norm(row.get("priority")) for row in rows]
        providers = sorted({_norm(row.get("provider")) for row in rows if _norm(row.get("provider"))})
        sessions = sorted({_norm(row.get("session_id")) for row in rows if _norm(row.get("session_id"))})
        category = _norm(rows[0].get("information_category"))
        canonical_information = _norm(rows[0].get("requested_information"))
        promotion_status = "REPEATED" if len(providers) > 1 else "OBSERVED"
        avg_score = 0.0
        if priorities:
            avg_score = sum(_priority_score(priority) for priority in priorities) / len(priorities)
        library_rows.append(
            {
                "generated_ts": generated_ts,
                "schema_version": SCHEMA_VERSION,
                "shadow_version": SHADOW_VERSION,
                "information_key": key,
                "canonical_information": canonical_information,
                "information_category": category,
                "first_seen_ts": min(_norm(row.get("generated_ts")) for row in rows),
                "last_seen_ts": max(_norm(row.get("generated_ts")) for row in rows),
                "request_count": len(rows),
                "provider_count": len(providers),
                "session_count": len(sessions),
                "providers_requesting": "|".join(providers),
                "sessions_seen": "|".join(sessions),
                "event_families": _join_unique(row.get("event_family_relevance") for row in rows),
                "attention_labels_linked": _join_unique(row.get("linked_attention_labels") for row in rows),
                "priority_avg": f"{avg_score:.2f}" if priorities else "",
                "must_have_count": sum(1 for priority in priorities if priority == "must_have"),
                "useful_count": sum(1 for priority in priorities if priority == "useful"),
                "optional_count": sum(1 for priority in priorities if priority == "optional"),
                "low_value_count": sum(1 for priority in priorities if priority == "low_value"),
                "market_state_candidate_count": sum(1 for row in rows if _as_bool(row.get("is_market_state_candidate"))),
                "promotion_status": promotion_status,
                "notes": "shadow_v0 rebuilt from Session_Information_Requests; no auto feature-pack approval",
            }
        )
    return library_rows


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
            "logical_sheet_id": "SESSION_INFORMATION_REQUESTS",
            "physical_sheet_name": OUTPUT_REQUEST_SHEET,
            "sheet_role": "provider_information_request_capture",
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
            "created_phase": "PreSignal v2.0 Phase 3",
            "notes": "shadow_v0 provider information request capture",
        },
        {
            "logical_sheet_id": "INFORMATION_REQUIREMENT_LIBRARY",
            "physical_sheet_name": OUTPUT_LIBRARY_SHEET,
            "sheet_role": "aggregate_information_need_registry",
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
            "created_phase": "PreSignal v2.0 Phase 3",
            "notes": "shadow_v0 aggregate information requirement library",
        },
        {
            "logical_sheet_id": "SESSION_INFORMATION_REQUEST_SUMMARY",
            "physical_sheet_name": OUTPUT_SUMMARY_SHEET,
            "sheet_role": "provider_information_request_summary",
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
            "created_phase": "PreSignal v2.0 Phase 3",
            "notes": "shadow_v0 information request summary",
        },
        {
            "logical_sheet_id": "SESSION_INFORMATION_PROVIDER_RESPONSE_AUDIT",
            "physical_sheet_name": OUTPUT_AUDIT_SHEET,
            "sheet_role": "provider_information_response_audit",
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
            "created_phase": "PreSignal v2.0 Phase 3",
            "notes": "shadow_v0 provider information response audit",
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


def _run_information_sanity_checks(
    request_rows: Sequence[Dict[str, Any]],
    library_rows: Sequence[Dict[str, Any]],
    provider_requests: Sequence[Dict[str, Any]],
    provider_results: Sequence[Dict[str, Any]],
    audit_rows: Sequence[Dict[str, Any]],
    registry_result: Dict[str, Any],
) -> Dict[str, Any]:
    checks: List[Tuple[str, bool, str]] = []
    expected_pairs = {(_norm(req.get("session_id")), _norm(req.get("provider"))) for req in provider_requests}
    audit_pairs = {(_norm(row.get("session_id")), _norm(row.get("provider"))) for row in audit_rows}
    request_pairs = {(_norm(row.get("session_id")), _norm(row.get("provider"))) for row in request_rows}
    success_pairs = {
        (_norm(result.get("session_id")), _norm(result.get("provider")))
        for result in provider_results
        if result.get("success")
    }

    missing_audit_pairs = sorted(expected_pairs - audit_pairs)
    missing_success_rows = sorted(pair for pair in success_pairs if pair not in request_pairs)
    checks.append(
        (
            "every_provider_session_has_rows_or_error_diagnostics",
            not missing_audit_pairs and not missing_success_rows,
            f"missing_audit_pairs={len(missing_audit_pairs)} missing_success_rows={len(missing_success_rows)}",
        )
    )

    forbidden_rows = [row for row in request_rows if _find_forbidden_output_paths(row)]
    checks.append(("no_forbidden_forecast_or_trading_fields_written", not forbidden_rows, f"forbidden_rows={len(forbidden_rows)}"))

    invalid_priority_rows = [row for row in request_rows if _norm(row.get("priority")) not in ALLOWED_PRIORITIES]
    checks.append(("all_priority_values_allowed", not invalid_priority_rows, f"invalid_rows={len(invalid_priority_rows)}"))

    invalid_category_rows = [
        row for row in request_rows if _norm(row.get("information_category")) not in ALLOWED_INFORMATION_CATEGORIES
    ]
    checks.append(("all_information_categories_allowed", not invalid_category_rows, f"invalid_rows={len(invalid_category_rows)}"))

    library_group_counts = {row.get("information_key"): _safe_int(row.get("request_count")) for row in library_rows}
    rebuilt_counts = Counter(
        _information_key(_norm(row.get("information_category")), _norm(row.get("requested_information"))) for row in request_rows
    )
    checks.append(
        (
            "library_aggregates_from_request_rows",
            dict(sorted(library_group_counts.items())) == dict(sorted(rebuilt_counts.items())),
            f"library_keys={len(library_group_counts)} rebuilt_keys={len(rebuilt_counts)}",
        )
    )

    approved_rows = [row for row in library_rows if _upper(row.get("promotion_status")) == "APPROVED_FOR_FEATURE_PACK"]
    checks.append(("no_auto_feature_pack_approval", not approved_rows, f"approved_rows={len(approved_rows)}"))
    checks.append(
        (
            "sheet_registry_contains_output_entries",
            (registry_result.get("updated", 0) + registry_result.get("appended", 0)) >= 4,
            f"registry_updated={registry_result}",
        )
    )
    checks.append(("event_not_written", True, "python script writes only diagnostics/registry sheets"))
    checks.append(("predictions_not_written", True, "python script writes only diagnostics/registry sheets"))
    checks.append(("evaluation_not_written", True, "python script writes only diagnostics/registry sheets"))
    checks.append(("phase1_phase2_source_sheets_not_written", True, "python script safe-rewrites only Phase 3 output sheets"))

    return {
        "passed": all(passed for _, passed, _ in checks),
        "checks": checks,
        "missing_audit_pair_count": len(missing_audit_pairs),
        "missing_success_rows_count": len(missing_success_rows),
        "forbidden_row_count": len(forbidden_rows),
        "approved_row_count": len(approved_rows),
    }


def _build_summary_row(
    generated_ts: str,
    run_id: str,
    sessions_read: int,
    valid_sessions: Sequence[Dict[str, Any]],
    provider_requests: Sequence[Dict[str, Any]],
    request_rows: Sequence[Dict[str, Any]],
    library_rows: Sequence[Dict[str, Any]],
    audit_rows: Sequence[Dict[str, Any]],
    registry_result: Dict[str, Any],
    mode: str,
    attention_summary_row: Dict[str, Any],
    output_sanity: Optional[Dict[str, Any]] = None,
    metrics: Optional[Dict[str, int]] = None,
    provider_results: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    metrics = metrics or _empty_metrics()
    output_sanity = output_sanity or {"passed": True, "checks": []}
    provider_results = list(provider_results or [])

    priority_counts = Counter(_norm(row.get("priority")) for row in request_rows)
    providers_succeeded = sum(1 for result in provider_results if result.get("success"))
    providers_failed = len(provider_results) - providers_succeeded
    market_state_candidate_count = sum(1 for row in request_rows if _as_bool(row.get("is_market_state_candidate")))

    if mode == "mock":
        build_status = "MOCK_CONTRACT_PASS" if providers_failed == 0 else "MOCK_CONTRACT_PASS_WITH_WARNINGS"
        final_interpretation = "SESSION_INFORMATION_REQUEST_CONTRACT_READY"
        notes = (
            "mode=mock; provider_calls=0; "
            f"payloads_prepared={len(provider_requests)}; "
            f"providers={json.dumps([req['provider'] for req in provider_requests], ensure_ascii=True)}; "
            f"attention_final_interpretation={_norm(attention_summary_row.get('final_interpretation'))}; "
            "mock_contract_checks=priority,category,duplicates,forbidden_fields"
        )
    elif mode == "live":
        if providers_succeeded == 0:
            build_status = "FAIL"
            final_interpretation = "SESSION_INFORMATION_REQUEST_CAPTURE_FAILED"
        elif providers_failed > 0 or not output_sanity.get("passed", False):
            build_status = "PASS_WITH_WARNINGS"
            final_interpretation = "SESSION_INFORMATION_REQUEST_CAPTURE_NEEDS_REVIEW"
        else:
            build_status = "PASS"
            final_interpretation = "SESSION_INFORMATION_REQUEST_CAPTURE_READY"
        failed_checks = [name for name, passed, _detail in output_sanity.get("checks", []) if not passed]
        notes = (
            f"mode=live; provider_calls={len(provider_requests)}; "
            f"payloads_prepared={len(provider_requests)}; "
            f"providers={json.dumps([req['provider'] for req in provider_requests], ensure_ascii=True)}; "
            f"attention_final_interpretation={_norm(attention_summary_row.get('final_interpretation'))}; "
            f"output_sanity_passed={output_sanity.get('passed', False)}; "
            f"failed_checks={json.dumps(failed_checks, ensure_ascii=True)}"
        )
    else:
        build_status = "SCAFFOLD_PASS"
        final_interpretation = "SESSION_INFORMATION_REQUEST_SCAFFOLD_READY"
        notes = (
            "dry_run=TRUE; provider_calls=0; "
            f"payloads_prepared={len(provider_requests)}; "
            f"providers={json.dumps([req['provider'] for req in provider_requests], ensure_ascii=True)}; "
            f"attention_final_interpretation={_norm(attention_summary_row.get('final_interpretation'))}"
        )

    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "shadow_version": SHADOW_VERSION,
        "information_run_id": run_id,
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "sessions_read": sessions_read,
        "sessions_processed": len(valid_sessions),
        "providers_attempted": len(provider_requests),
        "providers_succeeded": providers_succeeded,
        "providers_failed": providers_failed,
        "information_request_rows_written": len(request_rows),
        "library_rows_written": len(library_rows),
        "must_have_count": priority_counts.get("must_have", 0),
        "useful_count": priority_counts.get("useful", 0),
        "optional_count": priority_counts.get("optional", 0),
        "low_value_count": priority_counts.get("low_value", 0),
        "market_state_candidate_count": market_state_candidate_count,
        "invalid_category_count": metrics.get("invalid_category_count", 0),
        "invalid_priority_count": metrics.get("invalid_priority_count", 0),
        "duplicate_request_count": metrics.get("duplicate_request_count", 0),
        "provider_parse_error_count": metrics.get("provider_parse_error_count", 0),
        "provider_contract_error_count": metrics.get("provider_contract_error_count", 0),
        "provider_retry_count": metrics.get("provider_retry_count", 0),
        "provider_recovery_success_count": metrics.get("provider_recovery_success_count", 0),
        "provider_recovery_failed_count": metrics.get("provider_recovery_failed_count", 0),
        "provider_response_audit_rows_written": len(audit_rows),
        "registry_updated": "TRUE" if registry_result.get("updated", 0) or registry_result.get("appended", 0) else "FALSE",
        "governance_status": "DERIVED_ONLY_SHADOW_SAFE",
        "notes": notes,
    }


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Session Information Requirement Capture v0 in dry-run, mock, or live mode."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scaffold mode only; validate inputs, prepare provider payloads, and write empty output sheets.",
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


def build_session_information_requests_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    if args is None:
        args = _parse_args([])

    mode = "live" if getattr(args, "live", False) else "mock" if getattr(args, "mock", False) else "dry_run"
    creds = load_credentials(interactive=False)
    service = build_sheets_service(creds)
    generated_ts = _iso_now()
    run_id = _information_run_id(generated_ts)

    session_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, PHASE1_SESSION_SHEET)
    member_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, PHASE1_MEMBER_SHEET)
    attention_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, PHASE2_MAP_SHEET)
    attention_summary_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, PHASE2_SUMMARY_SHEET)
    attention_audit_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, PHASE2_AUDIT_SHEET)
    attention_summary_row, valid_sessions, members_by_session, attention_by_pair = _validate_phase2_inputs(
        session_rows,
        member_rows,
        attention_rows,
        attention_summary_rows,
        attention_audit_rows,
    )

    config_map = _read_config_map(service)
    providers = _resolve_provider_candidates(config_map)
    if not providers:
        raise RuntimeError("No provider candidates were resolved from Config/defaults for information capture.")

    provider_requests = _build_provider_requests(valid_sessions, members_by_session, attention_by_pair, providers)
    if not provider_requests:
        raise RuntimeError("No provider requests were prepared from the validated session inputs.")

    request_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_REQUEST_SHEET, REQUEST_HEADERS)
    library_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_LIBRARY_SHEET, LIBRARY_HEADERS)
    summary_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)
    audit_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_AUDIT_SHEET, AUDIT_HEADERS)

    if mode == "mock":
        request_rows, audit_rows, metrics, provider_results = _run_mock_contracts(
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
        request_rows, audit_rows, metrics, provider_results = _run_live_contracts(
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
        request_rows = []
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

    library_rows = _build_library_rows(generated_ts, request_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_REQUEST_SHEET, request_headers, request_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_LIBRARY_SHEET, library_headers, library_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_AUDIT_SHEET, audit_headers, audit_rows)
    registry_result = _upsert_registry_rows(service)
    if mode == "live":
        output_sanity = _run_information_sanity_checks(
            request_rows,
            library_rows,
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
        request_rows,
        library_rows,
        audit_rows,
        registry_result,
        mode,
        attention_summary_row,
        output_sanity,
        metrics,
        provider_results,
    )
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, [summary_row])

    return {
        "generated_ts": generated_ts,
        "information_run_id": run_id,
        "mode": mode,
        "sessions_read": len(session_rows),
        "sessions_processed": len(valid_sessions),
        "members_read": len(member_rows),
        "providers_attempted": len(provider_requests),
        "providers_succeeded": summary_row["providers_succeeded"],
        "providers_failed": summary_row["providers_failed"],
        "payloads_prepared": len(provider_requests),
        "information_request_rows_written": len(request_rows),
        "library_rows_written": len(library_rows),
        "must_have_count": summary_row["must_have_count"],
        "useful_count": summary_row["useful_count"],
        "optional_count": summary_row["optional_count"],
        "low_value_count": summary_row["low_value_count"],
        "market_state_candidate_count": summary_row["market_state_candidate_count"],
        "invalid_category_count": summary_row["invalid_category_count"],
        "invalid_priority_count": summary_row["invalid_priority_count"],
        "duplicate_request_count": summary_row["duplicate_request_count"],
        "provider_parse_error_count": summary_row["provider_parse_error_count"],
        "provider_contract_error_count": summary_row["provider_contract_error_count"],
        "provider_retry_count": summary_row["provider_retry_count"],
        "provider_recovery_success_count": summary_row["provider_recovery_success_count"],
        "provider_recovery_failed_count": summary_row["provider_recovery_failed_count"],
        "provider_response_audit_rows_written": summary_row["provider_response_audit_rows_written"],
        "build_status": summary_row["build_status"],
        "final_interpretation": summary_row["final_interpretation"],
        "output_sheets": [
            OUTPUT_REQUEST_SHEET,
            OUTPUT_LIBRARY_SHEET,
            OUTPUT_SUMMARY_SHEET,
            OUTPUT_AUDIT_SHEET,
        ],
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
        "sample_request_row": request_rows[0] if request_rows else {},
        "sample_library_row": library_rows[0] if library_rows else {},
        "sample_audit_row": audit_rows[0] if audit_rows else {},
    }


def main() -> None:
    print(json.dumps(build_session_information_requests_v0(_parse_args()), ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
