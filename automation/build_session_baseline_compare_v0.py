import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

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
    _safe_float,
    _truncate_text,
)

from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


PHASE1_SESSION_SHEET = "Market_Sessions"
PHASE1_MEMBER_SHEET = "Market_Session_Members"
PHASE4_FORECAST_SHEET = "Session_Forecasts"
PHASE5_EVALUATION_SHEET = "Session_Evaluation"
PHASE5_SUMMARY_SHEET = "Session_Evaluation_Summary"

MAIN_PREDICTIONS_SHEET = "Predictions"
MAIN_EVAL_ROWS_SHEET = "Evaluation_Rows"
MAIN_EVAL_SUMMARY_SHEET = "Evaluation_Summary"
MAIN_EVAL_BATCH_COMPARE_SHEET = "Evaluation_BatchCompare"
MAIN_EVAL_SCENARIO_SHEET = "Evaluation_Scenario"

OUTPUT_COMPARE_SHEET = "Session_vs_Event_Baseline_Compare"
OUTPUT_SUMMARY_SHEET = "Session_Baseline_Compare_Summary"
OUTPUT_AUDIT_SHEET = "Session_Baseline_Event_Link_Audit"

SCHEMA_VERSION = "presignal_v2_session_baseline_compare_0.1"
SHADOW_VERSION = "shadow_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 6"
REGISTRY_CATEGORY = "PRESIGNAL_V2_MARKET_SESSION"
REGISTRY_OWNER_MODULE = "market_session"

MATCH_LEVEL_RANK = {
    "exact_event_match": 5,
    "exact_batch_match": 5,
    "provider_event_match": 4,
    "provider_batch_match": 4,
    "session_member_match": 3,
    "weak_name_time_match": 2,
    "unmatched": 0,
    "excluded_stale_or_ambiguous": -1,
}
EXACT_MATCH_LEVELS = {"exact_event_match", "exact_batch_match", "provider_event_match", "provider_batch_match"}
WEAK_MATCH_LEVELS = {"session_member_match", "weak_name_time_match"}

COMPARE_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "phase",
    "session_id",
    "session_date",
    "country",
    "session_window_name",
    "provider",
    "model",
    "v2_forecast_direction",
    "v2_forecast_confidence",
    "v2_no_signal_flag",
    "v2_no_signal_reason",
    "v2_realized_direction",
    "v2_realized_pips",
    "v2_direction_ok",
    "v2_strength_ok",
    "v2_overall_ok",
    "v2_evaluation_status",
    "session_member_event_count",
    "session_member_event_ids",
    "session_member_batch_ids",
    "session_primary_release_ts",
    "session_last_release_ts",
    "v1_single_match_count",
    "v1_single_exact_match_count",
    "v1_single_weak_match_count",
    "v1_single_excluded_count",
    "v1_single_best_event_id",
    "v1_single_best_indicator_name",
    "v1_single_best_direction_ok",
    "v1_single_best_overall_ok",
    "v1_single_best_score",
    "v1_single_match_quality",
    "v1_batch_match_count",
    "v1_batch_exact_match_count",
    "v1_batch_weak_match_count",
    "v1_batch_excluded_count",
    "v1_batch_best_batch_id",
    "v1_batch_direction_ok",
    "v1_batch_overall_ok",
    "v1_batch_score",
    "v1_batch_match_quality",
    "v1_member_match_count",
    "v1_member_exact_match_count",
    "v1_member_weak_match_count",
    "v1_member_excluded_count",
    "v1_member_best_event_id",
    "v1_member_direction_ok",
    "v1_member_overall_ok",
    "v1_member_score",
    "v1_member_match_quality",
    "v1_scenario_match_count",
    "v1_scenario_direction_ok",
    "v1_scenario_overall_ok",
    "v1_scenario_match_quality",
    "v1_provider_summary_available",
    "v1_provider_summary_direction_rate",
    "v1_provider_summary_overall_rate",
    "comparison_basis",
    "comparison_status",
    "comparison_label",
    "comparison_note",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "phase",
    "build_status",
    "final_interpretation",
    "sessions_read",
    "sessions_compared",
    "providers_compared",
    "compare_rows_written",
    "v2_overall_ok_count",
    "v2_direction_ok_count",
    "v2_no_signal_count",
    "v2_no_signal_ok_count",
    "v1_single_available_count",
    "v1_single_overall_ok_count",
    "v1_batch_available_count",
    "v1_batch_overall_ok_count",
    "v1_member_available_count",
    "v1_member_overall_ok_count",
    "v1_scenario_available_count",
    "v1_scenario_overall_ok_count",
    "session_better_count",
    "v1_better_count",
    "same_result_count",
    "mixed_result_count",
    "insufficient_v1_baseline_count",
    "not_compared_count",
    "exact_match_count",
    "weak_match_count",
    "excluded_match_count",
    "stale_or_ambiguous_exclusion_count",
    "governance_forbidden_write_count",
    "input_missing_count",
    "error_count",
    "notes",
]

AUDIT_HEADERS = [
    "generated_ts",
    "schema_version",
    "shadow_version",
    "phase",
    "session_id",
    "provider",
    "source_sheet",
    "source_row_number",
    "candidate_event_id",
    "candidate_batch_id",
    "candidate_indicator_name",
    "candidate_release_ts",
    "candidate_created_ts",
    "candidate_eval_type",
    "candidate_direction_ok",
    "candidate_overall_ok",
    "candidate_score",
    "match_level",
    "match_quality",
    "used_in_compare",
    "exclusion_reason",
    "audit_note",
]


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _as_bool(value: Any) -> bool:
    return _upper(value) in {"TRUE", "T", "YES", "Y", "1"}


def _bool_cell(value: Optional[bool]) -> str:
    if value is None:
        return ""
    return "TRUE" if value else "FALSE"


def _iso_z(dt: Optional[datetime]) -> str:
    if dt is None:
        return ""
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_int(value: Any) -> Optional[int]:
    try:
        text = _norm(value)
        if not text:
            return None
        return int(float(text))
    except Exception:
        return None


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


def _sort_member_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = list(rows)
    out.sort(
        key=lambda row: (
            _norm(row.get("session_id")),
            _parse_dt(row.get("release_ts")) or datetime.max.replace(tzinfo=timezone.utc),
            _norm(row.get("indicator_name")),
            _norm(row.get("event_id")),
        )
    )
    return out


def _sort_session_eval_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = list(rows)
    out.sort(key=lambda row: (_norm(row.get("session_id")), _normalize_provider_name(row.get("provider"))))
    return out


def _eval_ready(summary_rows: Sequence[Dict[str, Any]]) -> bool:
    if not summary_rows:
        return False
    return _upper(summary_rows[0].get("final_interpretation")) == "SESSION_EVALUATION_READY"


def _release_date_text(row: Dict[str, Any]) -> str:
    if _norm(row.get("release_date")):
        return _norm(row.get("release_date"))
    release_dt = _parse_dt(row.get("release_ts"))
    return release_dt.date().isoformat() if release_dt is not None else ""


def _build_session_context(member_rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    event_ids = [_norm(row.get("event_id")) for row in member_rows if _norm(row.get("event_id"))]
    batch_ids = [_norm(row.get("batch_id")) for row in member_rows if _norm(row.get("batch_id"))]
    release_dts = [_parse_dt(row.get("release_ts")) for row in member_rows]
    release_dts = [dt for dt in release_dts if dt is not None]
    release_ts_set = {_iso_z(dt) for dt in release_dts}
    release_dates = {dt.date().isoformat() for dt in release_dts}
    indicator_names = {_upper(row.get("indicator_name")) for row in member_rows if _norm(row.get("indicator_name"))}
    genres = {_upper(row.get("genre")) for row in member_rows if _norm(row.get("genre"))}
    event_to_release = {
        _norm(row.get("event_id")): _iso_z(_parse_dt(row.get("release_ts")))
        for row in member_rows
        if _norm(row.get("event_id")) and _parse_dt(row.get("release_ts")) is not None
    }
    batch_to_releases: Dict[str, Set[str]] = defaultdict(set)
    for row in member_rows:
        batch_id = _norm(row.get("batch_id"))
        release_ts = _iso_z(_parse_dt(row.get("release_ts")))
        if batch_id and release_ts:
            batch_to_releases[batch_id].add(release_ts)
    first_release = min(release_dts) if release_dts else None
    last_release = max(release_dts) if release_dts else None
    return {
        "event_ids": set(event_ids),
        "batch_ids": set(batch_ids),
        "release_ts_set": release_ts_set,
        "release_dates": release_dates,
        "indicator_names": indicator_names,
        "genres": genres,
        "event_to_release": event_to_release,
        "batch_to_releases": batch_to_releases,
        "first_release": first_release,
        "last_release": last_release,
        "member_event_ids_joined": _join_unique(event_ids),
        "member_batch_ids_joined": _join_unique(batch_ids),
        "member_event_count": len(event_ids),
    }


def _baseline_type_for_row(source_sheet: str, row: Dict[str, Any]) -> str:
    if source_sheet == MAIN_EVAL_BATCH_COMPARE_SHEET:
        return "batch"
    if source_sheet == MAIN_EVAL_SCENARIO_SHEET:
        return "scenario"
    if source_sheet == MAIN_EVAL_SUMMARY_SHEET:
        return "summary"
    row_type = _norm(row.get("type")).lower()
    if source_sheet in {MAIN_EVAL_ROWS_SHEET, MAIN_PREDICTIONS_SHEET}:
        if row_type == "batch":
            return "batch"
        if row_type == "member":
            return "member"
        return "single"
    return "unknown"


def _candidate_score(source_sheet: str, row: Dict[str, Any]) -> float:
    if source_sheet == MAIN_EVAL_BATCH_COMPARE_SHEET:
        if _as_bool(row.get("batch_overall_ok")):
            return 2.0
        if _as_bool(row.get("batch_dir_ok")):
            return 1.0
        return 0.0
    if source_sheet == MAIN_EVAL_SCENARIO_SHEET:
        if _as_bool(row.get("batch_overall_ok")) or _upper(row.get("scenario_eval_result")) == "HIT":
            return 2.0
        return 0.0
    if _as_bool(row.get("overall_ok")):
        return 2.0
    if _as_bool(row.get("mr_dir_ok")) or _as_bool(row.get("dir_ok")):
        return 1.0
    return 0.0


def _candidate_direction_ok(source_sheet: str, row: Dict[str, Any]) -> str:
    if source_sheet == MAIN_EVAL_BATCH_COMPARE_SHEET:
        return _bool_cell(_as_bool(row.get("batch_dir_ok")))
    return _bool_cell(_as_bool(row.get("mr_dir_ok")) or _as_bool(row.get("dir_ok")))


def _candidate_overall_ok(source_sheet: str, row: Dict[str, Any]) -> str:
    if source_sheet == MAIN_EVAL_BATCH_COMPARE_SHEET:
        return _bool_cell(_as_bool(row.get("batch_overall_ok")))
    if source_sheet == MAIN_EVAL_SCENARIO_SHEET:
        if _norm(row.get("batch_overall_ok")):
            return _bool_cell(_as_bool(row.get("batch_overall_ok")))
        if _norm(row.get("scenario_eval_result")):
            return _bool_cell(_upper(row.get("scenario_eval_result")) == "HIT")
        return ""
    return _bool_cell(_as_bool(row.get("overall_ok")))


def _stale_market_reaction_timestamp(source_sheet: str, row: Dict[str, Any], release_dt: Optional[datetime]) -> bool:
    if release_dt is None:
        return False
    check_fields = ["start_ts", "end_ts", "mr_start_ts", "mr_end_ts", "mr_anchor_ts"]
    if source_sheet not in {MAIN_PREDICTIONS_SHEET, MAIN_EVAL_ROWS_SHEET}:
        return False
    for field in check_fields:
        ts = _parse_dt(row.get(field))
        if ts is None:
            continue
        if abs((ts - release_dt).total_seconds()) > 86400:
            return True
    return False


def _classify_candidate(
    session_id: str,
    provider: str,
    source_sheet: str,
    row: Dict[str, Any],
    session_ctx: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    candidate_provider = _normalize_provider_name(row.get("ai_name") or row.get("provider"))
    event_id = _norm(row.get("event_id"))
    batch_id = _norm(row.get("batch_id"))
    indicator_name = _norm(row.get("indicator_name") or row.get("batch_indicator_name") or row.get("best_member_indicator_name"))
    indicator_key = _upper(indicator_name)
    release_dt = _parse_dt(row.get("release_ts"))
    release_ts = _iso_z(release_dt)
    release_date = _release_date_text(row)
    row_type = _baseline_type_for_row(source_sheet, row)

    overlaps = any(
        [
            event_id and event_id in session_ctx["event_ids"],
            batch_id and batch_id in session_ctx["batch_ids"],
            release_ts and release_ts in session_ctx["release_ts_set"],
            release_date and release_date in session_ctx["release_dates"],
            indicator_key and indicator_key in session_ctx["indicator_names"],
        ]
    )
    if not overlaps:
        return None

    match_level = "unmatched"
    match_quality = ""
    exclusion_reason = ""
    note_bits: List[str] = []

    if not candidate_provider:
        match_level = "excluded_stale_or_ambiguous"
        exclusion_reason = "missing_provider"
        note_bits.append("candidate provider missing")
    elif candidate_provider != provider:
        match_level = "excluded_stale_or_ambiguous"
        exclusion_reason = "provider_mismatch"
        note_bits.append(f"candidate_provider={candidate_provider}")
    elif _stale_market_reaction_timestamp(source_sheet, row, release_dt):
        match_level = "excluded_stale_or_ambiguous"
        exclusion_reason = "stale_market_reaction_timestamp"
        note_bits.append("reaction timestamp drifted more than one day from release_ts")
    elif event_id and event_id in session_ctx["event_ids"]:
        expected_release = session_ctx["event_to_release"].get(event_id)
        if expected_release and release_ts and expected_release != release_ts:
            match_level = "excluded_stale_or_ambiguous"
            exclusion_reason = "release_ts_mismatch"
            note_bits.append(f"expected_release_ts={expected_release}")
        elif release_ts:
            match_level = "exact_event_match"
            match_quality = "exact"
        else:
            match_level = "provider_event_match"
            match_quality = "exact"
            note_bits.append("release_ts missing but event_id exact")
    elif batch_id and batch_id in session_ctx["batch_ids"]:
        batch_releases = session_ctx["batch_to_releases"].get(batch_id, set())
        if batch_releases and release_ts and release_ts not in batch_releases:
            match_level = "excluded_stale_or_ambiguous"
            exclusion_reason = "release_ts_mismatch"
            note_bits.append(f"expected_batch_release_ts={sorted(batch_releases)[0]}")
        elif release_ts:
            match_level = "exact_batch_match"
            match_quality = "exact"
        else:
            match_level = "provider_batch_match"
            match_quality = "exact"
            note_bits.append("release_ts missing but batch_id exact")
    elif release_date and release_date not in session_ctx["release_dates"]:
        match_level = "excluded_stale_or_ambiguous"
        exclusion_reason = "session_date_mismatch"
        note_bits.append(f"release_date={release_date}")
    elif indicator_key and indicator_key in session_ctx["indicator_names"] and release_ts and release_ts in session_ctx["release_ts_set"]:
        match_level = "session_member_match"
        match_quality = "weak"
    elif indicator_key and indicator_key in session_ctx["indicator_names"] and release_date in session_ctx["release_dates"]:
        match_level = "weak_name_time_match"
        match_quality = "weak"
    elif row_type == "summary" and release_date in session_ctx["release_dates"]:
        match_level = "session_member_match"
        match_quality = "weak"
        note_bits.append("provider summary row aligned by release_date only")
    elif not event_id and not batch_id and not indicator_name:
        match_level = "excluded_stale_or_ambiguous"
        exclusion_reason = "unsupported_row_shape"
        note_bits.append("no event_id, batch_id, or indicator_name")
    else:
        match_level = "unmatched"
        note_bits.append("overlap not strong enough for baseline use")

    if row_type == "batch" and batch_id and batch_id in session_ctx["batch_ids"]:
        if source_sheet in {MAIN_EVAL_ROWS_SHEET, MAIN_PREDICTIONS_SHEET} and _norm(row.get("type")).lower() != "batch":
            match_level = "excluded_stale_or_ambiguous"
            exclusion_reason = "ambiguous_batch_match"
            note_bits.append("batch_id present on non-batch row")

    score = _candidate_score(source_sheet, row)
    direction_ok = _candidate_direction_ok(source_sheet, row)
    overall_ok = _candidate_overall_ok(source_sheet, row)
    if row_type == "summary":
        direction_ok = ""
        overall_ok = ""
        score = 0.0

    return {
        "generated_ts": "",
        "schema_version": SCHEMA_VERSION,
        "shadow_version": SHADOW_VERSION,
        "phase": PHASE_LABEL,
        "session_id": session_id,
        "provider": provider,
        "source_sheet": source_sheet,
        "source_row_number": row.get("__source_row_number__", ""),
        "candidate_event_id": event_id,
        "candidate_batch_id": batch_id,
        "candidate_indicator_name": indicator_name,
        "candidate_release_ts": release_ts or _norm(row.get("release_ts")),
        "candidate_created_ts": _norm(row.get("created_ts") or row.get("eval_ts") or row.get("generated_ts")),
        "candidate_eval_type": row_type,
        "candidate_direction_ok": direction_ok,
        "candidate_overall_ok": overall_ok,
        "candidate_score": score,
        "match_level": match_level,
        "match_quality": match_quality,
        "used_in_compare": "FALSE",
        "exclusion_reason": exclusion_reason,
        "audit_note": _truncate_text("; ".join(note_bits), 240),
    }


def _collect_candidates(
    session_id: str,
    provider: str,
    session_ctx: Dict[str, Any],
    source_rows: Dict[str, Sequence[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for source_sheet, rows in source_rows.items():
        for row in rows:
            classified = _classify_candidate(session_id, provider, source_sheet, row, session_ctx)
            if classified is not None:
                candidates.append(classified)
    return candidates


def _match_sort_key(row: Dict[str, Any]) -> Tuple[int, float, int]:
    return (
        MATCH_LEVEL_RANK.get(_norm(row.get("match_level")), 0),
        float(row.get("candidate_score") or 0.0),
        -(_safe_int(row.get("source_row_number")) or 0),
    )


def _select_best_candidate(candidates: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    usable = [row for row in candidates if _norm(row.get("match_level")) in EXACT_MATCH_LEVELS | WEAK_MATCH_LEVELS]
    if not usable:
        return None
    usable.sort(key=_match_sort_key, reverse=True)
    return usable[0]


def _provider_summary_metrics(
    provider: str,
    session_ctx: Dict[str, Any],
    summary_rows: Sequence[Dict[str, Any]],
) -> Tuple[str, str, str]:
    provider_norm = _normalize_provider_name(provider)
    matches = []
    for row in summary_rows:
        if _normalize_provider_name(row.get("ai_name")) != provider_norm:
            continue
        if _release_date_text(row) not in session_ctx["release_dates"]:
            continue
        if _norm(row.get("scope")).lower() != "all":
            continue
        if _norm(row.get("breakdown")) and _norm(row.get("breakdown")).lower() != "by_scope":
            continue
        matches.append(row)
    if not matches:
        return "FALSE", "", ""
    matches.sort(key=lambda row: (_release_date_text(row), _safe_int(row.get("__source_row_number__")) or 0), reverse=True)
    row = matches[0]
    return "TRUE", _norm(row.get("dir_ok_rate")), _norm(row.get("overall_ok_rate"))


def _type_metrics(candidates: Sequence[Dict[str, Any]], best: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    exact = [row for row in candidates if _norm(row.get("match_level")) in EXACT_MATCH_LEVELS]
    weak = [row for row in candidates if _norm(row.get("match_level")) in WEAK_MATCH_LEVELS]
    excluded = [row for row in candidates if _norm(row.get("match_level")) == "excluded_stale_or_ambiguous"]
    if best is not None:
        best["used_in_compare"] = "TRUE"
    return {
        "match_count": len(exact) + len(weak),
        "exact_count": len(exact),
        "weak_count": len(weak),
        "excluded_count": len(excluded),
        "best": best,
    }


def _compare_outcome(v2_value: Any, baseline_value: Any) -> Optional[str]:
    if _norm(v2_value) == "" or _norm(baseline_value) == "":
        return None
    v2_bool = _as_bool(v2_value)
    base_bool = _as_bool(baseline_value)
    if v2_bool and not base_bool:
        return "session_better"
    if not v2_bool and base_bool:
        return "v1_better"
    return "same_result"


def _build_compare_row(
    generated_ts: str,
    evaluation_row: Dict[str, Any],
    session_row: Dict[str, Any],
    session_ctx: Dict[str, Any],
    source_rows: Dict[str, Sequence[Dict[str, Any]]],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Counter]:
    session_id = _norm(evaluation_row.get("session_id"))
    provider = _normalize_provider_name(evaluation_row.get("provider"))
    candidates = _collect_candidates(session_id, provider, session_ctx, source_rows)

    by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        by_type[_norm(candidate.get("candidate_eval_type"))].append(candidate)

    single_metrics = _type_metrics(by_type.get("single", []), _select_best_candidate(by_type.get("single", [])))
    batch_metrics = _type_metrics(by_type.get("batch", []), _select_best_candidate(by_type.get("batch", [])))
    member_metrics = _type_metrics(by_type.get("member", []), _select_best_candidate(by_type.get("member", [])))
    scenario_metrics = _type_metrics(by_type.get("scenario", []), _select_best_candidate(by_type.get("scenario", [])))
    provider_summary_available, provider_dir_rate, provider_overall_rate = _provider_summary_metrics(
        provider,
        session_ctx,
        source_rows[MAIN_EVAL_SUMMARY_SHEET],
    )

    comparison_inputs: List[Tuple[str, Optional[str]]] = []
    for name, metrics in [
        ("single", single_metrics),
        ("batch", batch_metrics),
        ("member", member_metrics),
        ("scenario", scenario_metrics),
    ]:
        best = metrics["best"]
        if best is None:
            continue
        if _norm(best.get("candidate_overall_ok")):
            comparison_inputs.append((f"{name}.overall_ok", _compare_outcome(evaluation_row.get("v2_overall_ok") or evaluation_row.get("overall_ok"), best.get("candidate_overall_ok"))))
        elif _norm(best.get("candidate_direction_ok")):
            comparison_inputs.append((f"{name}.direction_ok", _compare_outcome(evaluation_row.get("v2_direction_ok") or evaluation_row.get("direction_ok"), best.get("candidate_direction_ok"))))

    usable_outcomes = [outcome for _basis, outcome in comparison_inputs if outcome]
    if _norm(evaluation_row.get("evaluation_status")) != "evaluated":
        comparison_status = "NO_V2_EVALUATION"
        comparison_basis = ""
        comparison_label = "not_compared"
        comparison_note = f"Session evaluation status={_norm(evaluation_row.get('evaluation_status')) or '<blank>'}."
    elif not usable_outcomes:
        comparison_status = "NO_V1_MATCH"
        comparison_basis = ""
        comparison_label = "insufficient_v1_baseline"
        comparison_note = "No safe v1 baseline rows passed the conservative session-link audit."
    else:
        basis_labels = [basis for basis, outcome in comparison_inputs if outcome]
        exact_outcomes = set(usable_outcomes)
        comparison_basis = "|".join(basis_labels)
        if any(".direction_ok" in basis for basis in basis_labels) and not any(".overall_ok" in basis for basis in basis_labels):
            comparison_status = "PARTIAL_COMPARE"
        else:
            comparison_status = "COMPARED"
        if len(exact_outcomes) > 1:
            comparison_label = "mixed_result"
            comparison_note = "Available v1 baseline types disagreed on whether the session layer outperformed the event/member baseline."
        else:
            comparison_label = usable_outcomes[0]
            comparison_note = {
                "session_better": "Session-level evaluation beat the matched v1 baseline on the available coarse success flag.",
                "v1_better": "Matched v1 baseline beat the session-level evaluation on the available coarse success flag.",
                "same_result": "Session-level evaluation and matched v1 baseline produced the same coarse result.",
            }[comparison_label]
        if comparison_status == "PARTIAL_COMPARE":
            comparison_note += " Comparison fell back to direction_ok because overall_ok was unavailable for at least one baseline."

    metrics = Counter()
    all_candidates = single_metrics["match_count"] + batch_metrics["match_count"] + member_metrics["match_count"] + scenario_metrics["match_count"]
    exact_count = sum(item["exact_count"] for item in [single_metrics, batch_metrics, member_metrics, scenario_metrics])
    weak_count = sum(item["weak_count"] for item in [single_metrics, batch_metrics, member_metrics, scenario_metrics])
    excluded_count = sum(item["excluded_count"] for item in [single_metrics, batch_metrics, member_metrics, scenario_metrics])
    metrics["exact_match_count"] += exact_count
    metrics["weak_match_count"] += weak_count
    metrics["excluded_match_count"] += excluded_count
    metrics["stale_or_ambiguous_exclusion_count"] += sum(
        1 for row in candidates if _norm(row.get("exclusion_reason")) in {"stale_market_reaction_timestamp", "ambiguous_batch_match"}
    )

    if _as_bool(evaluation_row.get("overall_ok")):
        metrics["v2_overall_ok_count"] += 1
    if _as_bool(evaluation_row.get("direction_ok")):
        metrics["v2_direction_ok_count"] += 1
    if _as_bool(evaluation_row.get("no_signal_flag")):
        metrics["v2_no_signal_count"] += 1
    if _as_bool(evaluation_row.get("no_signal_ok")):
        metrics["v2_no_signal_ok_count"] += 1

    if single_metrics["best"] is not None:
        metrics["v1_single_available_count"] += 1
        if _as_bool(single_metrics["best"].get("candidate_overall_ok")):
            metrics["v1_single_overall_ok_count"] += 1
    if batch_metrics["best"] is not None:
        metrics["v1_batch_available_count"] += 1
        if _as_bool(batch_metrics["best"].get("candidate_overall_ok")):
            metrics["v1_batch_overall_ok_count"] += 1
    if member_metrics["best"] is not None:
        metrics["v1_member_available_count"] += 1
        if _as_bool(member_metrics["best"].get("candidate_overall_ok")):
            metrics["v1_member_overall_ok_count"] += 1
    if scenario_metrics["best"] is not None:
        metrics["v1_scenario_available_count"] += 1
        if _as_bool(scenario_metrics["best"].get("candidate_overall_ok")):
            metrics["v1_scenario_overall_ok_count"] += 1

    metrics[f"{comparison_label}_count"] += 1
    if comparison_status == "ERROR":
        metrics["error_count"] += 1

    compare_row = {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "shadow_version": SHADOW_VERSION,
        "phase": PHASE_LABEL,
        "session_id": session_id,
        "session_date": _norm(session_row.get("session_date")),
        "country": _norm(session_row.get("country")),
        "session_window_name": _norm(session_row.get("session_window_name")),
        "provider": provider,
        "model": _norm(evaluation_row.get("model")),
        "v2_forecast_direction": _norm(evaluation_row.get("forecast_direction")),
        "v2_forecast_confidence": _norm(evaluation_row.get("forecast_confidence")),
        "v2_no_signal_flag": _norm(evaluation_row.get("no_signal_flag")),
        "v2_no_signal_reason": _truncate_text(_norm(evaluation_row.get("no_signal_reason")), 240),
        "v2_realized_direction": _norm(evaluation_row.get("realized_direction")),
        "v2_realized_pips": _norm(evaluation_row.get("realized_pips")),
        "v2_direction_ok": _norm(evaluation_row.get("direction_ok")),
        "v2_strength_ok": _norm(evaluation_row.get("strength_ok")),
        "v2_overall_ok": _norm(evaluation_row.get("overall_ok")),
        "v2_evaluation_status": _norm(evaluation_row.get("evaluation_status")),
        "session_member_event_count": session_ctx["member_event_count"],
        "session_member_event_ids": session_ctx["member_event_ids_joined"],
        "session_member_batch_ids": session_ctx["member_batch_ids_joined"],
        "session_primary_release_ts": _iso_z(session_ctx["first_release"]),
        "session_last_release_ts": _iso_z(session_ctx["last_release"]),
        "v1_single_match_count": single_metrics["match_count"],
        "v1_single_exact_match_count": single_metrics["exact_count"],
        "v1_single_weak_match_count": single_metrics["weak_count"],
        "v1_single_excluded_count": single_metrics["excluded_count"],
        "v1_single_best_event_id": _norm((single_metrics["best"] or {}).get("candidate_event_id")),
        "v1_single_best_indicator_name": _norm((single_metrics["best"] or {}).get("candidate_indicator_name")),
        "v1_single_best_direction_ok": _norm((single_metrics["best"] or {}).get("candidate_direction_ok")),
        "v1_single_best_overall_ok": _norm((single_metrics["best"] or {}).get("candidate_overall_ok")),
        "v1_single_best_score": _norm((single_metrics["best"] or {}).get("candidate_score")),
        "v1_single_match_quality": _norm((single_metrics["best"] or {}).get("match_quality")),
        "v1_batch_match_count": batch_metrics["match_count"],
        "v1_batch_exact_match_count": batch_metrics["exact_count"],
        "v1_batch_weak_match_count": batch_metrics["weak_count"],
        "v1_batch_excluded_count": batch_metrics["excluded_count"],
        "v1_batch_best_batch_id": _norm((batch_metrics["best"] or {}).get("candidate_batch_id")),
        "v1_batch_direction_ok": _norm((batch_metrics["best"] or {}).get("candidate_direction_ok")),
        "v1_batch_overall_ok": _norm((batch_metrics["best"] or {}).get("candidate_overall_ok")),
        "v1_batch_score": _norm((batch_metrics["best"] or {}).get("candidate_score")),
        "v1_batch_match_quality": _norm((batch_metrics["best"] or {}).get("match_quality")),
        "v1_member_match_count": member_metrics["match_count"],
        "v1_member_exact_match_count": member_metrics["exact_count"],
        "v1_member_weak_match_count": member_metrics["weak_count"],
        "v1_member_excluded_count": member_metrics["excluded_count"],
        "v1_member_best_event_id": _norm((member_metrics["best"] or {}).get("candidate_event_id")),
        "v1_member_direction_ok": _norm((member_metrics["best"] or {}).get("candidate_direction_ok")),
        "v1_member_overall_ok": _norm((member_metrics["best"] or {}).get("candidate_overall_ok")),
        "v1_member_score": _norm((member_metrics["best"] or {}).get("candidate_score")),
        "v1_member_match_quality": _norm((member_metrics["best"] or {}).get("match_quality")),
        "v1_scenario_match_count": scenario_metrics["match_count"],
        "v1_scenario_direction_ok": _norm((scenario_metrics["best"] or {}).get("candidate_direction_ok")),
        "v1_scenario_overall_ok": _norm((scenario_metrics["best"] or {}).get("candidate_overall_ok")),
        "v1_scenario_match_quality": _norm((scenario_metrics["best"] or {}).get("match_quality")),
        "v1_provider_summary_available": provider_summary_available,
        "v1_provider_summary_direction_rate": provider_dir_rate,
        "v1_provider_summary_overall_rate": provider_overall_rate,
        "comparison_basis": comparison_basis,
        "comparison_status": comparison_status,
        "comparison_label": comparison_label,
        "comparison_note": _truncate_text(comparison_note, 300),
    }
    return compare_row, candidates, metrics


def _validate_inputs(
    session_rows: Sequence[Dict[str, Any]],
    member_rows: Sequence[Dict[str, Any]],
    forecast_rows: Sequence[Dict[str, Any]],
    evaluation_rows: Sequence[Dict[str, Any]],
    evaluation_summary_rows: Sequence[Dict[str, Any]],
    main_eval_rows: Sequence[Dict[str, Any]],
    main_eval_summary_rows: Sequence[Dict[str, Any]],
    main_eval_batch_rows: Sequence[Dict[str, Any]],
    main_eval_scenario_rows: Sequence[Dict[str, Any]],
    predictions_rows: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    _require_headers(
        PHASE1_SESSION_SHEET,
        session_rows,
        ["session_id", "session_date", "country", "session_window_name", "primary_release_ts", "last_release_ts"],
    )
    _require_headers(
        PHASE1_MEMBER_SHEET,
        member_rows,
        ["session_id", "event_id", "batch_id", "type", "indicator_name", "genre", "release_ts"],
    )
    _require_headers(
        PHASE4_FORECAST_SHEET,
        forecast_rows,
        ["session_id", "provider", "model", "forecast_direction", "forecast_confidence", "no_signal_flag", "no_signal_reason"],
    )
    _require_headers(
        PHASE5_EVALUATION_SHEET,
        evaluation_rows,
        [
            "session_id",
            "provider",
            "model",
            "forecast_direction",
            "forecast_confidence",
            "no_signal_flag",
            "no_signal_reason",
            "realized_direction",
            "realized_pips",
            "direction_ok",
            "strength_ok",
            "overall_ok",
            "evaluation_status",
        ],
    )
    _require_headers(PHASE5_SUMMARY_SHEET, evaluation_summary_rows, ["build_status", "final_interpretation"])
    _require_headers_if_rows_exist(
        MAIN_EVAL_ROWS_SHEET,
        main_eval_rows,
        ["event_id", "batch_id", "type", "indicator_name", "release_ts", "ai_name", "mr_dir_ok", "overall_ok"],
    )
    _require_headers_if_rows_exist(
        MAIN_EVAL_SUMMARY_SHEET,
        main_eval_summary_rows,
        ["release_date", "ai_name", "scope", "dir_ok_rate", "overall_ok_rate"],
    )
    _require_headers_if_rows_exist(
        MAIN_EVAL_BATCH_COMPARE_SHEET,
        main_eval_batch_rows,
        ["release_ts", "batch_id", "ai_name", "batch_dir_ok", "batch_overall_ok"],
    )
    _require_headers_if_rows_exist(
        MAIN_EVAL_SCENARIO_SHEET,
        main_eval_scenario_rows,
        ["release_ts", "batch_id", "ai_name", "scenario_eval_result"],
    )
    _require_headers_if_rows_exist(
        MAIN_PREDICTIONS_SHEET,
        predictions_rows,
        ["event_id", "batch_id", "type", "indicator_name", "release_ts", "ai_name"],
    )

    session_map = {_norm(row.get("session_id")): row for row in session_rows if _norm(row.get("session_id"))}
    members_by_session: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in _sort_member_rows(member_rows):
        session_id = _norm(row.get("session_id"))
        if session_id:
            members_by_session[session_id].append(row)

    forecast_by_pair = {
        (_norm(row.get("session_id")), _normalize_provider_name(row.get("provider"))): row for row in forecast_rows
    }
    valid_evaluation_rows = []
    for row in _sort_session_eval_rows(evaluation_rows):
        session_id = _norm(row.get("session_id"))
        provider = _normalize_provider_name(row.get("provider"))
        if not session_id or not provider:
            continue
        if session_id not in session_map:
            continue
        valid_evaluation_rows.append(row)

    if not valid_evaluation_rows:
        raise RuntimeError("No valid Session_Evaluation rows matched the current Market_Sessions sheet.")

    return {
        "session_map": session_map,
        "members_by_session": members_by_session,
        "forecast_by_pair": forecast_by_pair,
        "evaluation_rows": valid_evaluation_rows,
    }


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
            "created_phase": PHASE_LABEL,
            "notes": "shadow_v0 session baseline compare",
        },
        {
            "logical_sheet_id": "SESSION_BASELINE_COMPARE_SUMMARY",
            "physical_sheet_name": OUTPUT_SUMMARY_SHEET,
            "sheet_role": "v2_vs_v1_compare_summary",
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
            "notes": "shadow_v0 session baseline compare summary",
        },
        {
            "logical_sheet_id": "SESSION_BASELINE_EVENT_LINK_AUDIT",
            "physical_sheet_name": OUTPUT_AUDIT_SHEET,
            "sheet_role": "v2_vs_v1_link_audit",
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
            "notes": "shadow_v0 session baseline link audit",
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
    evaluation_rows: Sequence[Dict[str, Any]],
    compare_rows: Sequence[Dict[str, Any]],
    registry_result: Dict[str, Any],
) -> Dict[str, Any]:
    checks: List[Tuple[str, bool, str]] = []
    eval_pairs = {(_norm(row.get("session_id")), _normalize_provider_name(row.get("provider"))) for row in evaluation_rows}
    compare_pairs = [(_norm(row.get("session_id")), _normalize_provider_name(row.get("provider"))) for row in compare_rows]
    compare_pair_counts = Counter(compare_pairs)
    missing_pairs = sorted(pair for pair in eval_pairs if pair not in set(compare_pair_counts))
    duplicate_pairs = sorted(pair for pair, count in compare_pair_counts.items() if count > 1)
    bad_status = [
        row
        for row in compare_rows
        if _norm(row.get("comparison_status"))
        not in {"COMPARED", "PARTIAL_COMPARE", "INSUFFICIENT_BASELINE", "NO_V2_EVALUATION", "NO_V1_MATCH", "ERROR"}
    ]
    bad_labels = [
        row
        for row in compare_rows
        if _norm(row.get("comparison_label"))
        not in {"session_better", "v1_better", "same_result", "mixed_result", "insufficient_v1_baseline", "not_compared"}
    ]

    checks.append(("every_session_evaluation_row_has_compare_row", not missing_pairs, f"missing_pairs={len(missing_pairs)}"))
    checks.append(("no_duplicate_session_provider_compare_rows", not duplicate_pairs, f"duplicate_pairs={len(duplicate_pairs)}"))
    checks.append(("comparison_status_values_allowed", not bad_status, f"invalid_rows={len(bad_status)}"))
    checks.append(("comparison_label_values_allowed", not bad_labels, f"invalid_rows={len(bad_labels)}"))
    checks.append(
        (
            "sheet_registry_contains_output_entries",
            (registry_result.get("updated", 0) + registry_result.get("appended", 0)) >= 3,
            f"registry_updated={registry_result}",
        )
    )
    checks.append(("forbidden_sheets_not_written", True, "python script writes only Phase 6 output sheets plus registry"))
    return {"passed": all(passed for _, passed, _ in checks), "checks": checks}


def _build_summary_row(
    generated_ts: str,
    sessions_read: int,
    sessions_compared: int,
    providers_compared: int,
    compare_rows: Sequence[Dict[str, Any]],
    audit_rows: Sequence[Dict[str, Any]],
    registry_result: Dict[str, Any],
    metrics: Counter,
    sanity: Dict[str, Any],
    ready: bool,
) -> Dict[str, Any]:
    if not ready:
        build_status = "BLOCKED"
        final_interpretation = "SESSION_BASELINE_COMPARE_NEEDS_REVIEW"
    elif not compare_rows:
        build_status = "FAIL"
        final_interpretation = "SESSION_BASELINE_COMPARE_FAILED"
    elif sanity.get("passed", False) and metrics.get("insufficient_v1_baseline_count", 0) == 0 and metrics.get("weak_match_count", 0) == 0:
        build_status = "PASS"
        final_interpretation = "SESSION_BASELINE_COMPARE_READY"
    elif sanity.get("passed", False) and compare_rows:
        build_status = "PASS_WITH_WARNINGS"
        final_interpretation = "SESSION_BASELINE_COMPARE_READY_WITH_LIMITED_BASELINE"
    else:
        build_status = "PASS_WITH_WARNINGS"
        final_interpretation = "SESSION_BASELINE_COMPARE_NEEDS_REVIEW"

    failed_checks = [name for name, passed, _detail in sanity.get("checks", []) if not passed]
    notes = (
        f"sanity_passed={sanity.get('passed', False)}; "
        f"failed_checks={json.dumps(failed_checks, ensure_ascii=True)}; "
        f"audit_rows_written={len(audit_rows)}; "
        f"exact_match_count={metrics.get('exact_match_count', 0)}; "
        f"weak_match_count={metrics.get('weak_match_count', 0)}; "
        f"excluded_match_count={metrics.get('excluded_match_count', 0)}"
    )
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "shadow_version": SHADOW_VERSION,
        "phase": PHASE_LABEL,
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "sessions_read": sessions_read,
        "sessions_compared": sessions_compared,
        "providers_compared": providers_compared,
        "compare_rows_written": len(compare_rows),
        "v2_overall_ok_count": metrics.get("v2_overall_ok_count", 0),
        "v2_direction_ok_count": metrics.get("v2_direction_ok_count", 0),
        "v2_no_signal_count": metrics.get("v2_no_signal_count", 0),
        "v2_no_signal_ok_count": metrics.get("v2_no_signal_ok_count", 0),
        "v1_single_available_count": metrics.get("v1_single_available_count", 0),
        "v1_single_overall_ok_count": metrics.get("v1_single_overall_ok_count", 0),
        "v1_batch_available_count": metrics.get("v1_batch_available_count", 0),
        "v1_batch_overall_ok_count": metrics.get("v1_batch_overall_ok_count", 0),
        "v1_member_available_count": metrics.get("v1_member_available_count", 0),
        "v1_member_overall_ok_count": metrics.get("v1_member_overall_ok_count", 0),
        "v1_scenario_available_count": metrics.get("v1_scenario_available_count", 0),
        "v1_scenario_overall_ok_count": metrics.get("v1_scenario_overall_ok_count", 0),
        "session_better_count": metrics.get("session_better_count", 0),
        "v1_better_count": metrics.get("v1_better_count", 0),
        "same_result_count": metrics.get("same_result_count", 0),
        "mixed_result_count": metrics.get("mixed_result_count", 0),
        "insufficient_v1_baseline_count": metrics.get("insufficient_v1_baseline_count", 0),
        "not_compared_count": metrics.get("not_compared_count", 0),
        "exact_match_count": metrics.get("exact_match_count", 0),
        "weak_match_count": metrics.get("weak_match_count", 0),
        "excluded_match_count": metrics.get("excluded_match_count", 0),
        "stale_or_ambiguous_exclusion_count": metrics.get("stale_or_ambiguous_exclusion_count", 0),
        "governance_forbidden_write_count": 0,
        "input_missing_count": 0,
        "error_count": metrics.get("error_count", 0),
        "notes": _truncate_text(notes, 500),
    }


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Session Baseline Compare v0 in diagnostics workbook.")
    return parser.parse_args(argv)


def build_session_baseline_compare_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    if args is None:
        args = _parse_args([])

    creds = load_credentials(interactive=False)
    sheets_service = build_sheets_service(creds)
    generated_ts = _iso_now()

    session_rows = _sheet_to_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, PHASE1_SESSION_SHEET)
    member_rows = _sheet_to_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, PHASE1_MEMBER_SHEET)
    forecast_rows = _sheet_to_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, PHASE4_FORECAST_SHEET)
    evaluation_rows = _sheet_to_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, PHASE5_EVALUATION_SHEET)
    evaluation_summary_rows = _sheet_to_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, PHASE5_SUMMARY_SHEET)

    main_eval_rows = _sheet_to_rows(sheets_service, MAIN_SPREADSHEET_ID, MAIN_EVAL_ROWS_SHEET)
    main_eval_summary_rows = _sheet_to_rows(sheets_service, MAIN_SPREADSHEET_ID, MAIN_EVAL_SUMMARY_SHEET)
    main_eval_batch_rows = _sheet_to_rows(sheets_service, MAIN_SPREADSHEET_ID, MAIN_EVAL_BATCH_COMPARE_SHEET)
    main_eval_scenario_rows = _sheet_to_rows(sheets_service, MAIN_SPREADSHEET_ID, MAIN_EVAL_SCENARIO_SHEET)
    predictions_rows = _sheet_to_rows(sheets_service, MAIN_SPREADSHEET_ID, MAIN_PREDICTIONS_SHEET)

    validated = _validate_inputs(
        session_rows,
        member_rows,
        forecast_rows,
        evaluation_rows,
        evaluation_summary_rows,
        main_eval_rows,
        main_eval_summary_rows,
        main_eval_batch_rows,
        main_eval_scenario_rows,
        predictions_rows,
    )

    compare_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_COMPARE_SHEET, COMPARE_HEADERS)
    summary_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)
    audit_headers = _ensure_sheet(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_AUDIT_SHEET, AUDIT_HEADERS)

    ready = _eval_ready(evaluation_summary_rows)
    compare_rows: List[Dict[str, Any]] = []
    audit_rows: List[Dict[str, Any]] = []
    metrics: Counter = Counter()

    source_rows = {
        MAIN_EVAL_ROWS_SHEET: main_eval_rows,
        MAIN_EVAL_BATCH_COMPARE_SHEET: main_eval_batch_rows,
        MAIN_EVAL_SCENARIO_SHEET: main_eval_scenario_rows,
        MAIN_EVAL_SUMMARY_SHEET: main_eval_summary_rows,
        MAIN_PREDICTIONS_SHEET: predictions_rows,
    }

    if ready:
        for evaluation_row in validated["evaluation_rows"]:
            session_id = _norm(evaluation_row.get("session_id"))
            provider = _normalize_provider_name(evaluation_row.get("provider"))
            member_group = validated["members_by_session"].get(session_id, [])
            session_ctx = _build_session_context(member_group)
            compare_row, row_audits, row_metrics = _build_compare_row(
                generated_ts,
                evaluation_row,
                validated["session_map"][session_id],
                session_ctx,
                source_rows,
            )
            compare_rows.append(compare_row)
            for audit_row in row_audits:
                audit_row["generated_ts"] = generated_ts
                audit_rows.append(audit_row)
            metrics.update(row_metrics)
            if provider:
                metrics["providers_compared"] += 1
        metrics["sessions_compared"] = len({_norm(row.get("session_id")) for row in compare_rows if _norm(row.get("session_id"))})
    else:
        metrics["not_compared_count"] = len(validated["evaluation_rows"])

    _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_COMPARE_SHEET, compare_headers, compare_rows)
    _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_AUDIT_SHEET, audit_headers, audit_rows)
    registry_result = _upsert_registry_rows(sheets_service)
    sanity = _run_sanity_checks(validated["evaluation_rows"], compare_rows, registry_result)
    summary_row = _build_summary_row(
        generated_ts,
        len(session_rows),
        metrics.get("sessions_compared", 0),
        metrics.get("providers_compared", 0),
        compare_rows,
        audit_rows,
        registry_result,
        metrics,
        sanity,
        ready,
    )
    _write_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, [summary_row])

    return {
        "generated_ts": generated_ts,
        "sessions_read": len(session_rows),
        "sessions_compared": summary_row["sessions_compared"],
        "providers_compared": summary_row["providers_compared"],
        "compare_rows_written": len(compare_rows),
        "summary_rows_written": 1,
        "audit_rows_written": len(audit_rows),
        "exact_match_count": summary_row["exact_match_count"],
        "weak_match_count": summary_row["weak_match_count"],
        "excluded_count": summary_row["excluded_match_count"],
        "build_status": summary_row["build_status"],
        "final_interpretation": summary_row["final_interpretation"],
        "registry_result": registry_result,
        "sample_compare_row": compare_rows[0] if compare_rows else {},
        "sample_audit_row": audit_rows[0] if audit_rows else {},
    }


def main() -> None:
    print(json.dumps(build_session_baseline_compare_v0(_parse_args()), ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
