import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
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
from automation.build_session_information_requests_v0 import (
    _iso_now,
    _normalize_provider_name,
    _read_config_map,
    _safe_float,
    _safe_int,
    _truncate_text,
)
from automation.google_clients import (
    batch_update_values,
    build_script_service,
    build_sheets_service,
    default_script_id,
    load_credentials,
    run_script_function,
)


PHASE1_SESSION_SHEET = "Market_Sessions"
PHASE1_MEMBER_SHEET = "Market_Session_Members"
PHASE2_MAP_SHEET = "Session_Attention_Map"
PHASE2_SUMMARY_SHEET = "Session_Attention_Summary"
PHASE3_REQUEST_SHEET = "Session_Information_Requests"
PHASE3_LIBRARY_SHEET = "Information_Requirement_Library"
PHASE4_FORECAST_SHEET = "Session_Forecasts"
PHASE4_SUMMARY_SHEET = "Session_Forecast_Summary"

MAIN_PREDICTIONS_SHEET = "Predictions"
MAIN_EVAL_ROWS_SHEET = "Evaluation_Rows"
MAIN_EVAL_SUMMARY_SHEET = "Evaluation_Summary"
MAIN_EVAL_BATCH_COMPARE_SHEET = "Evaluation_BatchCompare"
MAIN_EVAL_SCENARIO_SHEET = "Evaluation_Scenario"
MAIN_MR_PROVIDER_RUNS_SHEET = "MR_ProviderRuns"

OUTPUT_EVALUATION_SHEET = "Session_Evaluation"
OUTPUT_SUMMARY_SHEET = "Session_Evaluation_Summary"
OUTPUT_COMPARE_SHEET = "Session_vs_Event_Baseline_Compare"

SCHEMA_VERSION = "presignal_v2_session_evaluation_0.1"
SHADOW_VERSION = "shadow_v0"
REGISTRY_CATEGORY = "PRESIGNAL_V2_MARKET_SESSION"
REGISTRY_OWNER_MODULE = "market_session"

USDJPY_WINDOW_MOVE_FUNCTION = "apiGetUsdJpyWindowMove"
DEFAULT_MR_HORIZON_MIN = 5
DEFAULT_FLAT_THRESHOLD_PIPS = 5.0
SESSION_EVAL_WINDOW_RULE = "first_release_to_last_release_plus_mr_horizon"

ALLOWED_REALIZED_DIRECTIONS = {"up", "down", "flat", "unknown"}
ALLOWED_FORECAST_QUALITY_LABELS = {
    "correct_direction",
    "wrong_direction",
    "correct_no_signal",
    "missed_directional_move",
    "flat_correct",
    "flat_wrong",
    "insufficient_market_data",
    "not_evaluated",
}
ALLOWED_ATTENTION_QUALITY_LABELS = {
    "primary_driver_supported",
    "secondary_driver_supported",
    "attention_unclear",
    "attention_not_evaluated",
}
ALLOWED_INFORMATION_QUALITY_LABELS = {
    "information_used",
    "missing_information_noted",
    "information_not_evaluated",
}

EVALUATION_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "evaluation_run_id",
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
    "no_signal_flag",
    "no_signal_reason",
    "session_eval_window_start_ts",
    "session_eval_window_end_ts",
    "session_eval_window_rule",
    "mr_horizon_min",
    "start_price",
    "end_price",
    "realized_pips",
    "realized_abs_pips",
    "realized_direction",
    "direction_ok",
    "strength_ok",
    "overall_ok",
    "no_signal_ok",
    "forecast_quality_label",
    "attention_quality_label",
    "information_quality_label",
    "primary_driver_event_ids",
    "secondary_driver_event_ids",
    "watchlist_event_ids",
    "context_event_ids",
    "evaluation_status",
    "eval_note",
    "source_forecast_sheet",
    "source_session_sheet",
    "source_member_sheet",
    "source_attention_sheet",
    "market_reaction_source",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "evaluation_run_id",
    "build_status",
    "final_interpretation",
    "sessions_read",
    "sessions_processed",
    "forecast_rows_read",
    "evaluation_rows_written",
    "providers_evaluated",
    "providers_not_evaluated",
    "market_data_success_count",
    "market_data_missing_count",
    "direction_ok_count",
    "direction_wrong_count",
    "overall_ok_count",
    "overall_wrong_count",
    "no_signal_count",
    "no_signal_ok_count",
    "missed_directional_move_count",
    "flat_forecast_count",
    "flat_correct_count",
    "up_forecast_count",
    "down_forecast_count",
    "realized_up_count",
    "realized_down_count",
    "realized_flat_count",
    "avg_realized_abs_pips",
    "median_realized_abs_pips",
    "registry_updated",
    "governance_status",
    "notes",
]

COMPARE_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "evaluation_run_id",
    "session_id",
    "session_date",
    "country",
    "session_window_name",
    "provider",
    "session_forecast_direction",
    "session_realized_direction",
    "session_direction_ok",
    "session_overall_ok",
    "session_realized_pips",
    "session_no_signal_flag",
    "v1_matching_event_count",
    "v1_matching_prediction_count",
    "v1_best_single_overall_ok",
    "v1_best_single_direction_ok",
    "v1_batch_overall_ok",
    "v1_member_overall_ok",
    "v1_available",
    "comparison_label",
    "comparison_note",
    "source_session_evaluation_sheet",
    "source_v1_evaluation_sheet",
    "notes",
]


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _as_bool(value: Any) -> bool:
    return _upper(value) in {"TRUE", "T", "YES", "Y", "1"}


def _iso_z(dt: Optional[datetime]) -> str:
    if dt is None:
        return ""
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _eval_run_id(generated_ts: str) -> str:
    stamp = generated_ts.replace("-", "").replace(":", "").replace("+00:00", "Z").replace(".", "")
    return f"session_evaluation_v0_{stamp}"


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


def _forecast_ready(summary_row: Dict[str, Any]) -> bool:
    return _upper(summary_row.get("final_interpretation")) == "SESSION_FORECAST_CAPTURE_READY"


def _sort_member_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = list(rows)
    out.sort(
        key=lambda row: (
            _parse_dt(row.get("release_ts")) or datetime.max.replace(tzinfo=timezone.utc),
            _norm(row.get("country")),
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
            _normalize_provider_name(row.get("provider")),
            _safe_int(row.get("attention_rank")) or 999999,
            _parse_dt(row.get("release_ts")) or datetime.max.replace(tzinfo=timezone.utc),
            _norm(row.get("event_id")),
        )
    )
    return out


def _sort_forecast_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = list(rows)
    out.sort(key=lambda row: (_norm(row.get("session_id")), _normalize_provider_name(row.get("provider"))))
    return out


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


def _bool_cell(value: Optional[bool]) -> str:
    if value is None:
        return ""
    return "TRUE" if value else "FALSE"


def _quantize_num(value: Optional[float]) -> Any:
    if value is None:
        return ""
    rounded = round(float(value), 4)
    if rounded.is_integer():
        return int(rounded)
    return rounded


def _realized_direction_from_pips(realized_pips: Optional[float], flat_threshold_pips: float) -> str:
    if realized_pips is None:
        return "unknown"
    if realized_pips > flat_threshold_pips:
        return "up"
    if realized_pips < (-flat_threshold_pips):
        return "down"
    return "flat"


def _call_usdjpy_window_move(
    script_service,
    script_id: str,
    start_ts: str,
    end_ts: str,
) -> Dict[str, Any]:
    result = run_script_function(
        script_service,
        script_id,
        USDJPY_WINDOW_MOVE_FUNCTION,
        [{"start_ts": start_ts, "end_ts": end_ts}],
    )
    return result or {}


def _validate_inputs(
    session_rows: Sequence[Dict[str, Any]],
    member_rows: Sequence[Dict[str, Any]],
    attention_rows: Sequence[Dict[str, Any]],
    forecast_rows: Sequence[Dict[str, Any]],
    forecast_summary_rows: Sequence[Dict[str, Any]],
    predictions_rows: Sequence[Dict[str, Any]],
    eval_rows: Sequence[Dict[str, Any]],
    eval_batch_rows: Sequence[Dict[str, Any]],
    eval_scenario_rows: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    _require_headers(
        PHASE1_SESSION_SHEET,
        session_rows,
        ["session_id", "session_date", "country", "session_window_name", "session_start_ts", "session_end_ts"],
    )
    _require_headers(
        PHASE1_MEMBER_SHEET,
        member_rows,
        ["session_id", "event_id", "batch_id", "type", "indicator_name", "release_ts", "member_order"],
    )
    _require_headers(
        PHASE2_MAP_SHEET,
        attention_rows,
        ["session_id", "provider", "event_id", "attention_label", "attention_rank"],
    )
    _require_headers(
        PHASE4_FORECAST_SHEET,
        forecast_rows,
        [
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
            "no_signal_flag",
            "no_signal_reason",
            "information_used",
            "missing_information",
        ],
    )
    _require_headers(PHASE4_SUMMARY_SHEET, forecast_summary_rows, ["build_status", "final_interpretation"])
    _require_headers_if_rows_exist(
        MAIN_PREDICTIONS_SHEET,
        predictions_rows,
        ["event_id", "batch_id", "type", "ai_name", "release_ts", "overall_ok", "mr_dir_ok"],
    )
    _require_headers_if_rows_exist(
        MAIN_EVAL_ROWS_SHEET,
        eval_rows,
        ["event_id", "batch_id", "type", "ai_name", "release_ts", "overall_ok", "mr_dir_ok"],
    )
    _require_headers_if_rows_exist(
        MAIN_EVAL_BATCH_COMPARE_SHEET,
        eval_batch_rows,
        ["batch_id", "ai_name", "release_ts", "batch_overall_ok", "batch_dir_ok"],
    )
    _require_headers_if_rows_exist(
        MAIN_EVAL_SCENARIO_SHEET,
        eval_scenario_rows,
        ["batch_id", "ai_name", "release_ts"],
    )

    session_map = {_norm(row.get("session_id")): row for row in session_rows if _norm(row.get("session_id"))}
    members_by_session: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in _sort_member_rows(member_rows):
        session_id = _norm(row.get("session_id"))
        if session_id:
            members_by_session[session_id].append(row)

    attention_by_pair: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in _sort_attention_rows(attention_rows):
        session_id = _norm(row.get("session_id"))
        provider = _normalize_provider_name(row.get("provider"))
        if session_id and provider:
            attention_by_pair[(session_id, provider)].append(row)

    valid_forecasts = _sort_forecast_rows(forecast_rows)
    valid_sessions = [session_map[sid] for sid in sorted({_norm(row.get("session_id")) for row in valid_forecasts}) if sid in session_map]
    if not valid_sessions:
        raise RuntimeError("No valid session rows matched the current Session_Forecasts sheet.")

    return {
        "session_map": session_map,
        "members_by_session": members_by_session,
        "attention_by_pair": attention_by_pair,
        "forecast_rows": valid_forecasts,
        "valid_sessions": valid_sessions,
    }


def _session_window(
    member_rows: Sequence[Dict[str, Any]],
    mr_horizon_min: int,
) -> Tuple[Optional[datetime], Optional[datetime], Optional[datetime], Optional[datetime], str]:
    timestamps = [_parse_dt(row.get("release_ts")) for row in member_rows]
    timestamps = [ts for ts in timestamps if ts is not None]
    if not timestamps:
        return None, None, None, None, SESSION_EVAL_WINDOW_RULE
    first_release = min(timestamps)
    last_release = max(timestamps)
    eval_end = last_release + timedelta(minutes=mr_horizon_min)
    return first_release, last_release, first_release, eval_end, SESSION_EVAL_WINDOW_RULE


def _session_market_data(
    script_service,
    script_id: str,
    member_rows: Sequence[Dict[str, Any]],
    mr_horizon_min: int,
    flat_threshold_pips: float,
) -> Dict[str, Any]:
    first_release, last_release, eval_start, eval_end, rule = _session_window(member_rows, mr_horizon_min)
    if not first_release or not last_release or not eval_start or not eval_end:
        return {
            "status": "market_data_missing",
            "session_eval_window_start_ts": "",
            "session_eval_window_end_ts": "",
            "session_eval_window_rule": rule,
            "market_reaction_source": "",
            "start_price": "",
            "end_price": "",
            "realized_pips": None,
            "realized_abs_pips": None,
            "realized_direction": "unknown",
            "mr_horizon_min": mr_horizon_min,
            "flat_threshold_pips": flat_threshold_pips,
            "eval_note": "session member rows missing parseable release_ts",
            "notes": "market_data_status=missing_release_ts",
        }

    move = _call_usdjpy_window_move(script_service, script_id, _iso_z(eval_start), _iso_z(eval_end))
    status = _norm(move.get("status"))
    realized_pips = _safe_float(move.get("realized_pips")) if status == "ok" else None
    realized_abs_pips = abs(realized_pips) if realized_pips is not None else None
    realized_direction = _realized_direction_from_pips(realized_pips, flat_threshold_pips)
    if status != "ok":
        realized_direction = "unknown"

    return {
        "status": "ok" if status == "ok" else "market_data_missing",
        "session_eval_window_start_ts": _iso_z(eval_start),
        "session_eval_window_end_ts": _iso_z(eval_end),
        "session_eval_window_rule": rule,
        "market_reaction_source": _norm(move.get("provider")),
        "start_price": _quantize_num(_safe_float(move.get("start_price"))) if status == "ok" else "",
        "end_price": _quantize_num(_safe_float(move.get("end_price"))) if status == "ok" else "",
        "realized_pips": realized_pips,
        "realized_abs_pips": realized_abs_pips,
        "realized_direction": realized_direction,
        "mr_horizon_min": mr_horizon_min,
        "flat_threshold_pips": _safe_float(move.get("flat_threshold_pips")) or flat_threshold_pips,
        "eval_note": _norm(move.get("status")),
        "notes": _truncate_text(
            "market_data_provider={provider}; start_candle_ts={start}; end_candle_ts={end}".format(
                provider=_norm(move.get("provider")) or "<blank>",
                start=_norm(move.get("start_candle_ts")) or "<blank>",
                end=_norm(move.get("end_candle_ts")) or "<blank>",
            ),
            240,
        ),
    }


def _join_attention_ids(attention_rows: Sequence[Dict[str, Any]], label: str) -> str:
    rows = [row for row in attention_rows if _upper(row.get("attention_label")) == label]
    rows.sort(
        key=lambda row: (
            _safe_int(row.get("attention_rank")) or 999999,
            _parse_dt(row.get("release_ts")) or datetime.max.replace(tzinfo=timezone.utc),
            _norm(row.get("event_id")),
        )
    )
    return _join_unique(row.get("event_id") for row in rows)


def _strength_ok(
    realized_abs_pips: Optional[float],
    expected_move_pips_min: Any,
    expected_move_pips_max: Any,
) -> str:
    realized = realized_abs_pips
    minimum = _safe_float(expected_move_pips_min)
    maximum = _safe_float(expected_move_pips_max)
    if realized is None or minimum is None or maximum is None:
        return ""
    low = min(minimum, maximum) - 5
    high = max(minimum, maximum) + 5
    return "TRUE" if low <= realized <= high else "FALSE"


def _forecast_quality_label(
    evaluation_status: str,
    forecast_direction: str,
    direction_ok: str,
    no_signal_ok: str,
    realized_direction: str,
) -> str:
    if evaluation_status != "evaluated":
        return "insufficient_market_data" if evaluation_status == "market_data_missing" else "not_evaluated"
    if forecast_direction == "no_clear_direction":
        return "correct_no_signal" if no_signal_ok == "TRUE" else "missed_directional_move"
    if forecast_direction == "flat":
        return "flat_correct" if realized_direction == "flat" else "flat_wrong"
    return "correct_direction" if direction_ok == "TRUE" else "wrong_direction"


def _attention_quality_label(attention_rows: Sequence[Dict[str, Any]], evaluation_status: str, realized_direction: str) -> str:
    if evaluation_status != "evaluated":
        return "attention_not_evaluated"
    has_primary = any(_upper(row.get("attention_label")) == "PRIMARY_DRIVER" for row in attention_rows)
    has_secondary = any(_upper(row.get("attention_label")) == "SECONDARY_DRIVER" for row in attention_rows)
    if realized_direction in {"up", "down"} and has_primary:
        return "primary_driver_supported"
    if realized_direction in {"up", "down"} and has_secondary:
        return "secondary_driver_supported"
    return "attention_unclear"


def _information_quality_label(forecast_row: Dict[str, Any]) -> str:
    if _norm(forecast_row.get("information_used")):
        return "information_used"
    if _norm(forecast_row.get("missing_information")):
        return "missing_information_noted"
    return "information_not_evaluated"


def _matching_v1_rows(
    rows: Sequence[Dict[str, Any]],
    session_event_ids: Sequence[str],
    session_batch_ids: Sequence[str],
    session_release_ts: Sequence[str],
    provider: str,
) -> List[Dict[str, Any]]:
    event_id_set = set(session_event_ids)
    batch_id_set = {bid for bid in session_batch_ids if bid}
    release_ts_set = {_iso_z(_parse_dt(ts)) for ts in session_release_ts if _parse_dt(ts) is not None}
    provider_norm = _normalize_provider_name(provider)
    out: List[Dict[str, Any]] = []
    for row in rows:
        row_provider = _normalize_provider_name(row.get("ai_name") or row.get("provider"))
        if row_provider and row_provider != provider_norm:
            continue
        row_release_ts = _iso_z(_parse_dt(row.get("release_ts")))
        if _norm(row.get("event_id")) in event_id_set and row_release_ts in release_ts_set:
            out.append(row)
            continue
        if (
            _norm(row.get("type")) == "batch"
            and _norm(row.get("batch_id")) in batch_id_set
            and row_release_ts in release_ts_set
        ):
            out.append(row)
    return out


def _compare_row(
    generated_ts: str,
    run_id: str,
    evaluation_row: Dict[str, Any],
    session_event_ids: Sequence[str],
    session_batch_ids: Sequence[str],
    session_release_ts: Sequence[str],
    predictions_rows: Sequence[Dict[str, Any]],
    eval_rows: Sequence[Dict[str, Any]],
    eval_batch_rows: Sequence[Dict[str, Any]],
    eval_scenario_rows: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    provider = _normalize_provider_name(evaluation_row.get("provider"))
    matching_predictions = _matching_v1_rows(predictions_rows, session_event_ids, session_batch_ids, session_release_ts, provider)
    matching_eval_rows = _matching_v1_rows(eval_rows, session_event_ids, session_batch_ids, session_release_ts, provider)
    matching_batch_rows = _matching_v1_rows(eval_batch_rows, session_event_ids, session_batch_ids, session_release_ts, provider)
    matching_scenario_rows = _matching_v1_rows(eval_scenario_rows, session_event_ids, session_batch_ids, session_release_ts, provider)

    event_count = len(
        {
            _norm(row.get("event_id"))
            for row in matching_predictions + matching_eval_rows
            if _norm(row.get("event_id")) and _norm(row.get("event_id")) in set(session_event_ids)
        }
    )
    prediction_count = len(matching_predictions)
    best_single_overall_ok = any(_as_bool(row.get("overall_ok")) for row in matching_eval_rows if _norm(row.get("type")) != "batch")
    best_single_direction_ok = any(
        _as_bool(row.get("mr_dir_ok")) or _as_bool(row.get("dir_ok"))
        for row in matching_eval_rows
        if _norm(row.get("type")) != "batch"
    )
    batch_overall_ok = any(
        _as_bool(row.get("batch_overall_ok")) or (_norm(row.get("type")) == "batch" and _as_bool(row.get("overall_ok")))
        for row in matching_batch_rows + matching_eval_rows
    )
    member_overall_ok = any(
        _norm(row.get("type")) != "batch" and _as_bool(row.get("overall_ok")) for row in matching_eval_rows
    )
    v1_available = bool(matching_predictions or matching_eval_rows or matching_batch_rows or matching_scenario_rows)
    session_overall_ok = _as_bool(evaluation_row.get("overall_ok"))
    evaluation_status = _norm(evaluation_row.get("evaluation_status"))
    v1_best = best_single_overall_ok or batch_overall_ok or member_overall_ok

    if not v1_available:
        comparison_label = "insufficient_v1_baseline"
        comparison_note = "No reliable v1 rows matched the session event set."
    elif evaluation_status != "evaluated":
        comparison_label = "not_compared"
        comparison_note = f"Session evaluation status={evaluation_status or '<blank>'}; baseline kept read-only."
    elif session_overall_ok and not v1_best:
        comparison_label = "session_better"
        comparison_note = "Session-level forecast evaluated positive while matched v1 baseline rows did not."
    elif not session_overall_ok and v1_best:
        comparison_label = "v1_better"
        comparison_note = "Matched v1 baseline rows had at least one positive overall score while session forecast did not."
    else:
        comparison_label = "same_result"
        comparison_note = "Session-level and matched v1 baseline produced the same coarse overall outcome."

    source_sheets = []
    if matching_predictions:
        source_sheets.append(MAIN_PREDICTIONS_SHEET)
    if matching_eval_rows:
        source_sheets.append(MAIN_EVAL_ROWS_SHEET)
    if matching_batch_rows:
        source_sheets.append(MAIN_EVAL_BATCH_COMPARE_SHEET)
    if matching_scenario_rows:
        source_sheets.append(MAIN_EVAL_SCENARIO_SHEET)

    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "shadow_version": SHADOW_VERSION,
        "evaluation_run_id": run_id,
        "session_id": _norm(evaluation_row.get("session_id")),
        "session_date": _norm(evaluation_row.get("session_date")),
        "country": _norm(evaluation_row.get("country")),
        "session_window_name": _norm(evaluation_row.get("session_window_name")),
        "provider": provider,
        "session_forecast_direction": _norm(evaluation_row.get("forecast_direction")),
        "session_realized_direction": _norm(evaluation_row.get("realized_direction")),
        "session_direction_ok": _norm(evaluation_row.get("direction_ok")),
        "session_overall_ok": _norm(evaluation_row.get("overall_ok")),
        "session_realized_pips": _norm(evaluation_row.get("realized_pips")),
        "session_no_signal_flag": _norm(evaluation_row.get("no_signal_flag")),
        "v1_matching_event_count": event_count,
        "v1_matching_prediction_count": prediction_count,
        "v1_best_single_overall_ok": _bool_cell(best_single_overall_ok),
        "v1_best_single_direction_ok": _bool_cell(best_single_direction_ok),
        "v1_batch_overall_ok": _bool_cell(batch_overall_ok),
        "v1_member_overall_ok": _bool_cell(member_overall_ok),
        "v1_available": _bool_cell(v1_available),
        "comparison_label": comparison_label,
        "comparison_note": _truncate_text(comparison_note, 240),
        "source_session_evaluation_sheet": OUTPUT_EVALUATION_SHEET,
        "source_v1_evaluation_sheet": "|".join(source_sheets) if source_sheets else "",
        "notes": _truncate_text(
            f"matching_eval_rows={len(matching_eval_rows)}; matching_batch_rows={len(matching_batch_rows)}; matching_scenario_rows={len(matching_scenario_rows)}",
            240,
        ),
    }


def _evaluate_forecasts(
    generated_ts: str,
    run_id: str,
    session_map: Dict[str, Dict[str, Any]],
    members_by_session: Dict[str, List[Dict[str, Any]]],
    attention_by_pair: Dict[Tuple[str, str], List[Dict[str, Any]]],
    forecast_rows: Sequence[Dict[str, Any]],
    predictions_rows: Sequence[Dict[str, Any]],
    eval_rows: Sequence[Dict[str, Any]],
    eval_batch_rows: Sequence[Dict[str, Any]],
    eval_scenario_rows: Sequence[Dict[str, Any]],
    script_service,
    script_id: str,
    mr_horizon_min: int,
    flat_threshold_pips: float,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    evaluation_rows: List[Dict[str, Any]] = []
    compare_rows: List[Dict[str, Any]] = []
    metrics = Counter()

    market_data_by_session: Dict[str, Dict[str, Any]] = {}
    for session_id, session_row in session_map.items():
        if not any(_norm(row.get("session_id")) == session_id for row in forecast_rows):
            continue
        market_data_by_session[session_id] = _session_market_data(
            script_service,
            script_id,
            members_by_session.get(session_id, []),
            mr_horizon_min,
            flat_threshold_pips,
        )

    for forecast_row in _sort_forecast_rows(forecast_rows):
        session_id = _norm(forecast_row.get("session_id"))
        provider = _normalize_provider_name(forecast_row.get("provider"))
        session_row = session_map[session_id]
        member_rows = members_by_session.get(session_id, [])
        attention_rows = attention_by_pair.get((session_id, provider), [])
        market_data = market_data_by_session.get(session_id, {})

        realized_pips = market_data.get("realized_pips")
        realized_abs_pips = market_data.get("realized_abs_pips")
        realized_direction = _norm(market_data.get("realized_direction")) or "unknown"
        forecast_direction = _norm(forecast_row.get("forecast_direction"))
        no_signal_flag = _as_bool(forecast_row.get("no_signal_flag")) or forecast_direction == "no_clear_direction"
        evaluation_status = "evaluated" if market_data.get("status") == "ok" else "market_data_missing"

        direction_ok = ""
        no_signal_ok = ""
        overall_ok = ""
        if evaluation_status == "evaluated":
            if forecast_direction in {"up", "down", "flat"}:
                direction_ok = _bool_cell(forecast_direction == realized_direction)
                overall_ok = direction_ok
            if no_signal_flag:
                no_signal_ok = _bool_cell((realized_abs_pips or 0) <= float(market_data.get("flat_threshold_pips") or flat_threshold_pips))
                if forecast_direction == "no_clear_direction":
                    overall_ok = no_signal_ok

        strength_ok = _strength_ok(
            realized_abs_pips,
            forecast_row.get("expected_move_pips_min"),
            forecast_row.get("expected_move_pips_max"),
        )
        forecast_quality_label = _forecast_quality_label(
            evaluation_status,
            forecast_direction,
            direction_ok,
            no_signal_ok,
            realized_direction,
        )
        attention_quality_label = _attention_quality_label(attention_rows, evaluation_status, realized_direction)
        information_quality_label = _information_quality_label(forecast_row)

        row = {
            "generated_ts": generated_ts,
            "schema_version": SCHEMA_VERSION,
            "shadow_version": SHADOW_VERSION,
            "evaluation_run_id": run_id,
            "session_id": session_id,
            "session_date": _norm(session_row.get("session_date")),
            "country": _norm(session_row.get("country")),
            "session_window_name": _norm(session_row.get("session_window_name")),
            "provider": provider,
            "model": _norm(forecast_row.get("model")),
            "forecast_direction": forecast_direction,
            "forecast_confidence": _norm(forecast_row.get("forecast_confidence")),
            "expected_move_pips_min": _norm(forecast_row.get("expected_move_pips_min")),
            "expected_move_pips_max": _norm(forecast_row.get("expected_move_pips_max")),
            "expected_holding_minutes": _norm(forecast_row.get("expected_holding_minutes")),
            "no_signal_flag": "TRUE" if no_signal_flag else "FALSE",
            "no_signal_reason": _truncate_text(_norm(forecast_row.get("no_signal_reason")), 240),
            "session_eval_window_start_ts": _norm(market_data.get("session_eval_window_start_ts")),
            "session_eval_window_end_ts": _norm(market_data.get("session_eval_window_end_ts")),
            "session_eval_window_rule": _norm(market_data.get("session_eval_window_rule")),
            "mr_horizon_min": market_data.get("mr_horizon_min", mr_horizon_min),
            "start_price": _quantize_num(_safe_float(market_data.get("start_price"))),
            "end_price": _quantize_num(_safe_float(market_data.get("end_price"))),
            "realized_pips": _quantize_num(realized_pips),
            "realized_abs_pips": _quantize_num(realized_abs_pips),
            "realized_direction": realized_direction,
            "direction_ok": direction_ok,
            "strength_ok": strength_ok,
            "overall_ok": overall_ok,
            "no_signal_ok": no_signal_ok,
            "forecast_quality_label": forecast_quality_label,
            "attention_quality_label": attention_quality_label,
            "information_quality_label": information_quality_label,
            "primary_driver_event_ids": _join_attention_ids(attention_rows, "PRIMARY_DRIVER"),
            "secondary_driver_event_ids": _join_attention_ids(attention_rows, "SECONDARY_DRIVER"),
            "watchlist_event_ids": _join_attention_ids(attention_rows, "WATCHLIST"),
            "context_event_ids": _join_attention_ids(attention_rows, "CONTEXT_ONLY"),
            "evaluation_status": evaluation_status,
            "eval_note": _truncate_text(_norm(market_data.get("eval_note")), 240),
            "source_forecast_sheet": PHASE4_FORECAST_SHEET,
            "source_session_sheet": PHASE1_SESSION_SHEET,
            "source_member_sheet": PHASE1_MEMBER_SHEET,
            "source_attention_sheet": PHASE2_MAP_SHEET,
            "market_reaction_source": _norm(market_data.get("market_reaction_source")),
            "notes": _truncate_text(
                f"flat_threshold_pips={market_data.get('flat_threshold_pips', flat_threshold_pips)}; {market_data.get('notes', '')}",
                240,
            ),
        }
        evaluation_rows.append(row)

        session_event_ids = [_norm(member.get("event_id")) for member in member_rows]
        session_batch_ids = [_norm(member.get("batch_id")) for member in member_rows]
        session_release_ts = [_norm(member.get("release_ts")) for member in member_rows]
        compare_rows.append(
            _compare_row(
                generated_ts,
                run_id,
                row,
                session_event_ids,
                session_batch_ids,
                session_release_ts,
                predictions_rows,
                eval_rows,
                eval_batch_rows,
                eval_scenario_rows,
            )
        )

        if evaluation_status == "evaluated":
            metrics["providers_evaluated"] += 1
            metrics["market_data_success_count"] += 1
        else:
            metrics["providers_not_evaluated"] += 1
            metrics["market_data_missing_count"] += 1

        if direction_ok == "TRUE":
            metrics["direction_ok_count"] += 1
        elif direction_ok == "FALSE":
            metrics["direction_wrong_count"] += 1

        if overall_ok == "TRUE":
            metrics["overall_ok_count"] += 1
        elif overall_ok == "FALSE":
            metrics["overall_wrong_count"] += 1

        if no_signal_flag:
            metrics["no_signal_count"] += 1
        if no_signal_ok == "TRUE":
            metrics["no_signal_ok_count"] += 1
        if forecast_quality_label == "missed_directional_move":
            metrics["missed_directional_move_count"] += 1
        if forecast_direction == "flat":
            metrics["flat_forecast_count"] += 1
        if forecast_quality_label == "flat_correct":
            metrics["flat_correct_count"] += 1
        if forecast_direction == "up":
            metrics["up_forecast_count"] += 1
        if forecast_direction == "down":
            metrics["down_forecast_count"] += 1
        if realized_direction == "up":
            metrics["realized_up_count"] += 1
        elif realized_direction == "down":
            metrics["realized_down_count"] += 1
        elif realized_direction == "flat":
            metrics["realized_flat_count"] += 1

    return evaluation_rows, compare_rows, dict(metrics)


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
            "logical_sheet_id": "SESSION_EVALUATION",
            "physical_sheet_name": OUTPUT_EVALUATION_SHEET,
            "sheet_role": "session_forecast_scoring",
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
            "created_phase": "PreSignal v2.0 Phase 5",
            "notes": "shadow_v0 session forecast evaluation",
        },
        {
            "logical_sheet_id": "SESSION_EVALUATION_SUMMARY",
            "physical_sheet_name": OUTPUT_SUMMARY_SHEET,
            "sheet_role": "session_forecast_scoring_summary",
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
            "created_phase": "PreSignal v2.0 Phase 5",
            "notes": "shadow_v0 session forecast evaluation summary",
        },
        {
            "logical_sheet_id": "SESSION_VS_EVENT_BASELINE_COMPARE",
            "physical_sheet_name": OUTPUT_COMPARE_SHEET,
            "sheet_role": "v2_vs_v1_shadow_compare",
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
            "created_phase": "PreSignal v2.0 Phase 5",
            "notes": "shadow_v0 session vs event baseline compare",
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


def _run_sanity_checks(
    forecast_rows: Sequence[Dict[str, Any]],
    evaluation_rows: Sequence[Dict[str, Any]],
    members_by_session: Dict[str, List[Dict[str, Any]]],
    registry_result: Dict[str, Any],
    mr_horizon_min: int,
) -> Dict[str, Any]:
    checks: List[Tuple[str, bool, str]] = []
    forecast_pairs = {(_norm(row.get("session_id")), _normalize_provider_name(row.get("provider"))) for row in forecast_rows}
    eval_pairs = [(_norm(row.get("session_id")), _normalize_provider_name(row.get("provider"))) for row in evaluation_rows]
    eval_pair_counts = Counter(eval_pairs)
    missing_pairs = sorted(pair for pair in forecast_pairs if pair not in set(eval_pair_counts))
    duplicate_pairs = sorted(pair for pair, count in eval_pair_counts.items() if count > 1)

    checks.append(
        (
            "every_forecast_row_has_evaluation_row",
            not missing_pairs,
            f"missing_pairs={len(missing_pairs)}",
        )
    )
    checks.append(
        (
            "no_duplicate_session_provider_rows",
            not duplicate_pairs,
            f"duplicate_pairs={len(duplicate_pairs)}",
        )
    )

    session_windows: Dict[str, set] = defaultdict(set)
    for row in evaluation_rows:
        session_windows[_norm(row.get("session_id"))].add(
            (_norm(row.get("session_eval_window_start_ts")), _norm(row.get("session_eval_window_end_ts")))
        )
    inconsistent_windows = [sid for sid, windows in session_windows.items() if len(windows) > 1]
    checks.append(
        (
            "evaluation_window_identical_per_session",
            not inconsistent_windows,
            f"inconsistent_sessions={len(inconsistent_windows)}",
        )
    )

    bad_realized_direction = [row for row in evaluation_rows if _norm(row.get("realized_direction")) not in ALLOWED_REALIZED_DIRECTIONS]
    bad_quality_label = [row for row in evaluation_rows if _norm(row.get("forecast_quality_label")) not in ALLOWED_FORECAST_QUALITY_LABELS]
    missing_market_rows = [row for row in evaluation_rows if _norm(row.get("evaluation_status")) == "market_data_missing"]

    checks.append(("realized_direction_values_allowed", not bad_realized_direction, f"invalid_rows={len(bad_realized_direction)}"))
    checks.append(("forecast_quality_values_allowed", not bad_quality_label, f"invalid_rows={len(bad_quality_label)}"))
    checks.append(("market_data_missing_rows_explicit", True, f"market_data_missing_rows={len(missing_market_rows)}"))
    checks.append(
        (
            "sheet_registry_contains_output_entries",
            (registry_result.get("updated", 0) + registry_result.get("appended", 0)) >= 3,
            f"registry_updated={registry_result}",
        )
    )
    checks.append(("predictions_not_written", True, "python script writes only diagnostics/registry sheets"))
    checks.append(("existing_evaluation_sheets_not_written", True, "python script writes only Phase 5 output sheets"))
    checks.append(("outcome_ledger_not_written", True, "python script writes only diagnostics/registry sheets"))
    checks.append(("phase1_to_phase4_source_sheets_not_written", True, "python script safe-rewrites only Phase 5 output sheets"))

    start_mismatch = []
    end_mismatch = []
    for row in evaluation_rows:
        start_dt = _parse_dt(row.get("session_eval_window_start_ts"))
        end_dt = _parse_dt(row.get("session_eval_window_end_ts"))
        session_id = _norm(row.get("session_id"))
        member_rows = members_by_session.get(session_id, [])
        member_ts = [_parse_dt(member.get("release_ts")) for member in member_rows]
        member_ts = [ts for ts in member_ts if ts is not None]
        expected_start = min(member_ts) if member_ts else None
        expected_end = (max(member_ts) + timedelta(minutes=mr_horizon_min)) if member_ts else None
        if start_dt is None or expected_start is None or start_dt != expected_start:
            start_mismatch.append(row)
        if end_dt is None or expected_end is None or end_dt != expected_end:
            end_mismatch.append(row)
    checks.append(("session_eval_window_start_matches_first_release", not start_mismatch, f"invalid_rows={len(start_mismatch)}"))
    checks.append(("session_eval_window_end_matches_last_release_plus_horizon", not end_mismatch, f"invalid_rows={len(end_mismatch)}"))

    return {"passed": all(passed for _, passed, _ in checks), "checks": checks}


def _build_summary_row(
    generated_ts: str,
    run_id: str,
    sessions_read: int,
    sessions_processed: int,
    forecast_rows: Sequence[Dict[str, Any]],
    evaluation_rows: Sequence[Dict[str, Any]],
    compare_rows: Sequence[Dict[str, Any]],
    registry_result: Dict[str, Any],
    metrics: Dict[str, Any],
    sanity: Dict[str, Any],
    forecast_ready: bool,
    mr_horizon_min: int,
    flat_threshold_pips: float,
) -> Dict[str, Any]:
    realized_abs_values = [
        _safe_float(row.get("realized_abs_pips"))
        for row in evaluation_rows
        if _safe_float(row.get("realized_abs_pips")) is not None
    ]
    providers_evaluated = metrics.get("providers_evaluated", 0)
    providers_not_evaluated = metrics.get("providers_not_evaluated", 0)
    baseline_missing = any(_upper(row.get("v1_available")) != "TRUE" for row in compare_rows) if compare_rows else False
    market_data_missing = metrics.get("market_data_missing_count", 0) > 0

    if not forecast_ready:
        build_status = "BLOCKED"
        final_interpretation = "SESSION_EVALUATION_BLOCKED_FORECASTS_NOT_READY"
    elif providers_evaluated == 0:
        build_status = "FAIL"
        final_interpretation = "SESSION_EVALUATION_FAILED"
    elif market_data_missing or baseline_missing or not sanity.get("passed", False):
        build_status = "PASS_WITH_WARNINGS"
        final_interpretation = "SESSION_EVALUATION_NEEDS_REVIEW"
    else:
        build_status = "PASS"
        final_interpretation = "SESSION_EVALUATION_READY"

    failed_checks = [name for name, passed, _detail in sanity.get("checks", []) if not passed]
    notes = (
        f"forecast_ready={forecast_ready}; "
        f"mr_horizon_min={mr_horizon_min}; "
        f"flat_threshold_pips={flat_threshold_pips}; "
        f"baseline_compare_rows_written={len(compare_rows)}; "
        f"baseline_missing={baseline_missing}; "
        f"sanity_passed={sanity.get('passed', False)}; "
        f"failed_checks={json.dumps(failed_checks, ensure_ascii=True)}"
    )

    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "shadow_version": SHADOW_VERSION,
        "evaluation_run_id": run_id,
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "sessions_read": sessions_read,
        "sessions_processed": sessions_processed,
        "forecast_rows_read": len(forecast_rows),
        "evaluation_rows_written": len(evaluation_rows),
        "providers_evaluated": providers_evaluated,
        "providers_not_evaluated": providers_not_evaluated,
        "market_data_success_count": metrics.get("market_data_success_count", 0),
        "market_data_missing_count": metrics.get("market_data_missing_count", 0),
        "direction_ok_count": metrics.get("direction_ok_count", 0),
        "direction_wrong_count": metrics.get("direction_wrong_count", 0),
        "overall_ok_count": metrics.get("overall_ok_count", 0),
        "overall_wrong_count": metrics.get("overall_wrong_count", 0),
        "no_signal_count": metrics.get("no_signal_count", 0),
        "no_signal_ok_count": metrics.get("no_signal_ok_count", 0),
        "missed_directional_move_count": metrics.get("missed_directional_move_count", 0),
        "flat_forecast_count": metrics.get("flat_forecast_count", 0),
        "flat_correct_count": metrics.get("flat_correct_count", 0),
        "up_forecast_count": metrics.get("up_forecast_count", 0),
        "down_forecast_count": metrics.get("down_forecast_count", 0),
        "realized_up_count": metrics.get("realized_up_count", 0),
        "realized_down_count": metrics.get("realized_down_count", 0),
        "realized_flat_count": metrics.get("realized_flat_count", 0),
        "avg_realized_abs_pips": round(sum(realized_abs_values) / len(realized_abs_values), 4) if realized_abs_values else "",
        "median_realized_abs_pips": round(float(median(realized_abs_values)), 4) if realized_abs_values else "",
        "registry_updated": "TRUE" if registry_result.get("updated", 0) or registry_result.get("appended", 0) else "FALSE",
        "governance_status": "DERIVED_ONLY_SHADOW_SAFE",
        "notes": _truncate_text(notes, 500),
    }


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Session Evaluation v0 in diagnostics workbook.")
    return parser.parse_args(argv)


def build_session_evaluation_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    if args is None:
        args = _parse_args([])

    creds = load_credentials(interactive=False)
    sheets_service = build_sheets_service(creds)
    script_service = build_script_service(creds)
    script_id = default_script_id()
    generated_ts = _iso_now()
    run_id = _eval_run_id(generated_ts)

    session_rows = _sheet_to_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, PHASE1_SESSION_SHEET)
    member_rows = _sheet_to_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, PHASE1_MEMBER_SHEET)
    attention_rows = _sheet_to_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, PHASE2_MAP_SHEET)
    attention_summary_rows = _sheet_to_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, PHASE2_SUMMARY_SHEET)
    forecast_rows = _sheet_to_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, PHASE4_FORECAST_SHEET)
    forecast_summary_rows = _sheet_to_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, PHASE4_SUMMARY_SHEET)

    predictions_rows = _sheet_to_rows(sheets_service, MAIN_SPREADSHEET_ID, MAIN_PREDICTIONS_SHEET)
    eval_rows = _sheet_to_rows(sheets_service, MAIN_SPREADSHEET_ID, MAIN_EVAL_ROWS_SHEET)
    eval_summary_rows = _sheet_to_rows(sheets_service, MAIN_SPREADSHEET_ID, MAIN_EVAL_SUMMARY_SHEET)
    eval_batch_rows = _sheet_to_rows(sheets_service, MAIN_SPREADSHEET_ID, MAIN_EVAL_BATCH_COMPARE_SHEET)
    eval_scenario_rows = _sheet_to_rows(sheets_service, MAIN_SPREADSHEET_ID, MAIN_EVAL_SCENARIO_SHEET)
    mr_provider_rows = _sheet_to_rows(sheets_service, MAIN_SPREADSHEET_ID, MAIN_MR_PROVIDER_RUNS_SHEET)
    _ = attention_summary_rows, eval_summary_rows, mr_provider_rows  # explicit read-only inputs for traceability

    validated = _validate_inputs(
        session_rows,
        member_rows,
        attention_rows,
        forecast_rows,
        forecast_summary_rows,
        predictions_rows,
        eval_rows,
        eval_batch_rows,
        eval_scenario_rows,
    )

    config_map = _read_config_map(sheets_service)
    mr_horizon_min = _safe_int(config_map.get("MR_HORIZON_MIN")) or DEFAULT_MR_HORIZON_MIN
    if mr_horizon_min < 1:
        mr_horizon_min = DEFAULT_MR_HORIZON_MIN
    if mr_horizon_min > 15:
        mr_horizon_min = 15

    flat_threshold_pips = _safe_float(config_map.get("MR_FLAT_MAX_ABS_PIPS"))
    if flat_threshold_pips is None:
        flat_threshold_pips = DEFAULT_FLAT_THRESHOLD_PIPS

    evaluation_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_EVALUATION_SHEET, EVALUATION_HEADERS)
    summary_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)
    compare_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_COMPARE_SHEET, COMPARE_HEADERS)

    forecast_summary_row = forecast_summary_rows[0]
    forecasts_ready = _forecast_ready(forecast_summary_row)

    if forecasts_ready:
        evaluation_rows, compare_rows, metrics = _evaluate_forecasts(
            generated_ts,
            run_id,
            validated["session_map"],
            validated["members_by_session"],
            validated["attention_by_pair"],
            validated["forecast_rows"],
            predictions_rows,
            eval_rows,
            eval_batch_rows,
            eval_scenario_rows,
            script_service,
            script_id,
            mr_horizon_min,
            flat_threshold_pips,
        )
    else:
        evaluation_rows = []
        compare_rows = []
        metrics = Counter()

    _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_EVALUATION_SHEET, evaluation_headers, evaluation_rows)
    _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_COMPARE_SHEET, compare_headers, compare_rows)
    registry_result = _upsert_registry_rows(sheets_service)
    sanity = _run_sanity_checks(
        validated["forecast_rows"],
        evaluation_rows,
        validated["members_by_session"],
        registry_result,
        mr_horizon_min,
    )
    summary_row = _build_summary_row(
        generated_ts,
        run_id,
        len(session_rows),
        len(validated["valid_sessions"]),
        validated["forecast_rows"],
        evaluation_rows,
        compare_rows,
        registry_result,
        dict(metrics),
        sanity,
        forecasts_ready,
        mr_horizon_min,
        flat_threshold_pips,
    )
    _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, [summary_row])

    return {
        "generated_ts": generated_ts,
        "evaluation_run_id": run_id,
        "sessions_read": len(session_rows),
        "sessions_processed": len(validated["valid_sessions"]),
        "forecast_rows_read": len(validated["forecast_rows"]),
        "evaluation_rows_written": len(evaluation_rows),
        "providers_evaluated": summary_row["providers_evaluated"],
        "providers_not_evaluated": summary_row["providers_not_evaluated"],
        "market_data_success_count": summary_row["market_data_success_count"],
        "market_data_missing_count": summary_row["market_data_missing_count"],
        "direction_ok_count": summary_row["direction_ok_count"],
        "overall_ok_count": summary_row["overall_ok_count"],
        "no_signal_count": summary_row["no_signal_count"],
        "no_signal_ok_count": summary_row["no_signal_ok_count"],
        "baseline_compare_rows_written": len(compare_rows),
        "build_status": summary_row["build_status"],
        "final_interpretation": summary_row["final_interpretation"],
        "registry_result": registry_result,
        "mr_horizon_min": mr_horizon_min,
        "flat_threshold_pips": flat_threshold_pips,
        "sample_evaluation_row": evaluation_rows[0] if evaluation_rows else {},
        "sample_compare_row": compare_rows[0] if compare_rows else {},
    }


def main() -> None:
    print(json.dumps(build_session_evaluation_v0(_parse_args()), ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
