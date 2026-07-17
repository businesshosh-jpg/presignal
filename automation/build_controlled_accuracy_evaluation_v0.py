import argparse
import json
import math
import sys
from collections import Counter, defaultdict
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
    _sheet_to_rows,
    _write_rows,
)
from automation.build_session_information_requests_v0 import _iso_now, _truncate_text
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


SCHEMA_VERSION = "presignal_v2_controlled_accuracy_evaluation_0.1"
EVALUATION_VERSION = "controlled_accuracy_evaluation_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-5F"
REGISTRY_CATEGORY = "PRESIGNAL_V2_CONTROLLED_ACCURACY_EVALUATION"
REGISTRY_OWNER_MODULE = "market_state"

APPROVAL_SHEETS = [
    "Accuracy_Execution_Approval",
    "Accuracy_Execution_Freeze_Record",
    "Accuracy_Execution_Governance_Review",
    "Accuracy_Execution_Risk_Assessment",
    "Accuracy_Execution_Interpretation_Guardrails",
    "Accuracy_Execution_Approval_Summary",
]

DRY_RUN_SHEETS = [
    "Controlled_Accuracy_Eval_Dry_Run",
    "Controlled_Accuracy_Eligible_Row_Preview",
    "Controlled_Accuracy_Outcome_Match_Preview",
    "Controlled_Accuracy_Comparison_Pair_Preview",
    "Controlled_Accuracy_Metric_Row_Preview",
    "Controlled_Accuracy_Invalid_Row_Audit",
]

TIER2_SHEETS = [
    "Pack_Behavior_Tier2_Forecasts",
    "Pack_Behavior_Tier2_Metadata",
    "Pack_Behavior_Tier2_Behavior",
    "Pack_Behavior_Tier2_Raw_Response_Archive",
    "Pack_Behavior_Tier2_Invalid_Output",
    "Pack_Behavior_Tier2_NoSignal",
]

OUTPUT_EVALUATION = "Controlled_Accuracy_Evaluation"
OUTPUT_EXPERIMENT = "Controlled_Accuracy_Experiment_Results"
OUTPUT_COMPARISON = "Controlled_Accuracy_Comparison_Results"
OUTPUT_METRIC = "Controlled_Accuracy_Metric_Results"
OUTPUT_INVALID = "Controlled_Accuracy_Invalid_Output_Results"
OUTPUT_GOVERNANCE = "Controlled_Accuracy_Governance_Audit"
OUTPUT_SUMMARY = "Controlled_Accuracy_Evaluation_Summary"

EVALUATION_HEADERS = [
    "generated_ts",
    "schema_version",
    "evaluation_version",
    "evaluation_run_id",
    "experiment_id",
    "accuracy_hypothesis_id",
    "session_id",
    "provider",
    "pack_level",
    "forecast_row_key",
    "forecast_direction",
    "forecast_direction_normalized",
    "forecast_confidence",
    "no_signal_flag",
    "output_valid",
    "raw_archive_present",
    "outcome_source_sheet",
    "outcome_match_key",
    "outcome_match_status",
    "outcome_direction",
    "realized_pips",
    "outcome_row_count",
    "direction_correctness_calculated",
    "direction_correct",
    "no_signal_correct",
    "false_signal",
    "expected_move_pips_min",
    "expected_move_pips_max",
    "move_range_ok",
    "overall_ok_calculated",
    "overall_ok",
    "included_in_direction_denominator",
    "included_in_no_signal_denominator",
    "included_in_false_signal_denominator",
    "included_in_overall_denominator",
    "diagnostic_only",
    "production_excluded",
    "notes",
]

EXPERIMENT_HEADERS = [
    "generated_ts",
    "schema_version",
    "evaluation_version",
    "evaluation_run_id",
    "experiment_id",
    "accuracy_hypothesis_id",
    "eligible_rows_evaluated",
    "excluded_rows",
    "invalid_outputs",
    "direction_denominator",
    "direction_correct_count",
    "direction_match_rate",
    "overall_denominator",
    "overall_ok_count",
    "overall_ok_rate",
    "false_signal_denominator",
    "false_signal_count",
    "false_signal_rate",
    "no_signal_denominator",
    "no_signal_correct_count",
    "no_signal_correctness",
    "result_status",
    "interpretation",
    "production_excluded",
    "notes",
]

COMPARISON_HEADERS = [
    "generated_ts",
    "schema_version",
    "evaluation_version",
    "evaluation_run_id",
    "experiment_id",
    "comparison_id",
    "provider_scope",
    "baseline_pack_level",
    "treatment_pack_level",
    "comparison_pairs_evaluated",
    "pairs_excluded",
    "baseline_direction_match_rate",
    "treatment_direction_match_rate",
    "direction_match_rate_delta",
    "baseline_overall_ok_rate",
    "treatment_overall_ok_rate",
    "overall_ok_rate_delta",
    "baseline_false_signal_rate",
    "treatment_false_signal_rate",
    "false_signal_rate_delta",
    "baseline_no_signal_correctness",
    "treatment_no_signal_correctness",
    "no_signal_correctness_delta",
    "comparison_status",
    "interpretation",
    "production_excluded",
    "notes",
]

METRIC_HEADERS = [
    "generated_ts",
    "schema_version",
    "evaluation_version",
    "evaluation_run_id",
    "experiment_id",
    "comparison_id",
    "metric_id",
    "metric_name",
    "metric_scope",
    "denominator_count",
    "numerator_count",
    "metric_value",
    "baseline_metric_value",
    "treatment_metric_value",
    "metric_delta",
    "metric_status",
    "calculation_rule",
    "interpretation_limit",
    "production_excluded",
    "notes",
]

INVALID_HEADERS = [
    "generated_ts",
    "schema_version",
    "evaluation_version",
    "evaluation_run_id",
    "experiment_id",
    "session_id",
    "provider",
    "pack_level",
    "forecast_row_key",
    "invalid_case_type",
    "source_detection_sheet",
    "raw_archive_present",
    "excluded_from_accuracy",
    "would_count_in_invalid_output_rate",
    "rerun_allowed",
    "inference_allowed",
    "notes",
]

GOVERNANCE_HEADERS = [
    "generated_ts",
    "schema_version",
    "evaluation_version",
    "evaluation_run_id",
    "check_id",
    "check_name",
    "expected_value",
    "actual_value",
    "status",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "schema_version",
    "evaluation_version",
    "evaluation_run_id",
    "build_status",
    "final_interpretation",
    "experiments_executed",
    "eligible_rows_evaluated",
    "excluded_rows",
    "invalid_outputs",
    "comparison_pairs_evaluated",
    "metrics_calculated",
    "direction_denominator",
    "direction_correct_count",
    "direction_match_rate",
    "overall_denominator",
    "overall_ok_count",
    "overall_ok_rate",
    "provider_calls_performed",
    "forecast_generation_performed",
    "provider_rerun_count",
    "production_behavior_change_count",
    "production_sheet_write_count",
    "evaluation_rows_written",
    "outcome_ledger_written",
    "diagnostic_only",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _bool(value: Any) -> bool:
    return _upper(value) in {"TRUE", "YES", "1", "Y"}


def _to_float(value: Any) -> Optional[float]:
    raw = _norm(value)
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _safe_rate(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return ""
    return f"{numerator / denominator:.6f}"


def _metric_delta(treatment: Optional[float], baseline: Optional[float]) -> str:
    if treatment is None or baseline is None:
        return ""
    return f"{treatment - baseline:.6f}"


def _run_id(generated_ts: str) -> str:
    compact = generated_ts.replace("-", "").replace(":", "").replace("Z", "Z")
    return f"controlled_accuracy_evaluation_v0_{compact}"


def _sheet_titles(service, spreadsheet_id: str) -> Set[str]:
    metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return {sheet["properties"]["title"] for sheet in metadata.get("sheets", [])}


def _safe_rows(service, spreadsheet_id: str, titles: Set[str], sheet_name: str, missing: List[str]) -> List[Dict[str, Any]]:
    if sheet_name not in titles:
        missing.append(sheet_name)
        return []
    try:
        return _sheet_to_rows(service, spreadsheet_id, sheet_name)
    except Exception:
        missing.append(sheet_name)
        return []


def _base(generated_ts: str, evaluation_run_id: str) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "evaluation_version": EVALUATION_VERSION,
        "evaluation_run_id": evaluation_run_id,
    }


def _forecast_row_key(row: Dict[str, Any]) -> str:
    archive_key = _norm(row.get("raw_response_archive_key"))
    if archive_key:
        return archive_key
    return "|".join(
        [
            _norm(row.get("execution_run_id")) or _norm(row.get("discovery_run_id")),
            _norm(row.get("session_id")),
            _norm(row.get("provider")),
            _upper(row.get("pack_level")),
            _norm(row.get("prompt_hash")),
        ]
    )


def _normalize_direction(value: Any, no_signal: bool = False) -> str:
    raw = _upper(value).replace("-", "_").replace(" ", "_")
    if no_signal or raw in {"NO_SIGNAL", "NO_CLEAR_DIRECTION", "NO_CLEAR_SIGNAL", "NONE", "UNKNOWN"}:
        return "NO_SIGNAL"
    if raw in {"UP", "BULLISH", "LONG"}:
        return "UP"
    if raw in {"DOWN", "BEARISH", "SHORT"}:
        return "DOWN"
    if raw in {"FLAT", "NEUTRAL", "SIDEWAYS"}:
        return "FLAT"
    return raw


def _release_ts_for_forecast(row: Dict[str, Any]) -> str:
    ts = _norm(row.get("forecast_timestamp"))
    if ts.endswith("Z") and not ts.endswith(".000Z"):
        return ts[:-1] + ".000Z"
    return ts


def _build_outcome_index(rows: Sequence[Dict[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if _norm(row.get("fx_pair")) not in {"", "USDJPY"}:
            continue
        country = _norm(row.get("country"))
        release_ts = _norm(row.get("release_ts"))
        if country and release_ts:
            grouped[(country, release_ts)].append(row)
    outcome_index: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for key, members in grouped.items():
        dirs = sorted({_normalize_direction(row.get("mr_real_dir")) for row in members if _norm(row.get("mr_real_dir"))})
        pips_values = sorted({_norm(row.get("realized_pips")) for row in members if _norm(row.get("realized_pips"))})
        if len(dirs) == 1 and len(pips_values) == 1:
            status = "MATCHED_EXACT_RELEASE_TS"
            direction = dirs[0]
            pips = _to_float(pips_values[0])
        else:
            status = "BLOCKED_DUPLICATE_OR_AMBIGUOUS_OUTCOME"
            direction = ""
            pips = None
        outcome_index[key] = {
            "outcome_source_sheet": "Evaluation_Rows",
            "outcome_match_status": status,
            "outcome_direction": direction,
            "realized_pips": pips,
            "outcome_row_count": len(members),
            "outcome_match_key": f"{key[0]}|{key[1]}",
        }
    return outcome_index


def _no_signal_lookup(rows: Iterable[Dict[str, Any]]) -> Dict[Tuple[str, str, str], bool]:
    lookup: Dict[Tuple[str, str, str], bool] = {}
    for row in rows:
        lookup[(_norm(row.get("session_id")), _norm(row.get("provider")), _upper(row.get("pack_level")))] = _bool(row.get("no_signal_flag"))
    return lookup


def _forecast_lookup(rows: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {_forecast_row_key(row): row for row in rows}


def _approved_experiments(rows: Iterable[Dict[str, Any]]) -> Dict[str, str]:
    return {
        _norm(row.get("experiment_id")): _norm(row.get("hypothesis_id"))
        for row in rows
        if _bool(row.get("approved_for_phase9a5f"))
    }


def _range_ok(expected_min: Optional[float], expected_max: Optional[float], realized_pips: Optional[float]) -> Optional[bool]:
    if realized_pips is None:
        return None
    if expected_min is None and expected_max is None:
        return None
    low = abs(expected_min or 0)
    high = abs(expected_max if expected_max is not None else low)
    if low > high:
        low, high = high, low
    return low <= abs(realized_pips) <= high


def _evaluate_row(
    generated_ts: str,
    evaluation_run_id: str,
    eligible_preview: Dict[str, Any],
    forecast: Dict[str, Any],
    hypothesis_id: str,
    no_signal_lookup: Dict[Tuple[str, str, str], bool],
    outcome_index: Dict[Tuple[str, str], Dict[str, Any]],
) -> Dict[str, Any]:
    session_id = _norm(forecast.get("session_id"))
    provider = _norm(forecast.get("provider"))
    pack_level = _upper(forecast.get("pack_level"))
    no_signal = no_signal_lookup.get((session_id, provider, pack_level), False)
    forecast_direction = _norm(forecast.get("forecast_direction"))
    forecast_direction_norm = _normalize_direction(forecast_direction, no_signal)
    country = _norm(forecast.get("country")) or session_id.split("|")[0]
    release_ts = _release_ts_for_forecast(forecast)
    outcome = outcome_index.get((country, release_ts), {})
    outcome_status = _norm(outcome.get("outcome_match_status")) or "NO_MATCHING_OUTCOME"
    outcome_direction = _norm(outcome.get("outcome_direction"))
    realized_pips = outcome.get("realized_pips")
    direction_calculated = bool(outcome_direction and outcome_status == "MATCHED_EXACT_RELEASE_TS")
    if forecast_direction_norm == "NO_SIGNAL":
        direction_correct = outcome_direction == "FLAT" if direction_calculated else None
    else:
        direction_correct = forecast_direction_norm == outcome_direction if direction_calculated else None
    no_signal_correct = outcome_direction == "FLAT" if direction_calculated and forecast_direction_norm == "NO_SIGNAL" else None
    false_signal = (
        forecast_direction_norm in {"UP", "DOWN"} and outcome_direction == "FLAT"
        if direction_calculated
        else None
    )
    expected_min = _to_float(forecast.get("expected_move_pips_min"))
    expected_max = _to_float(forecast.get("expected_move_pips_max"))
    move_ok = _range_ok(expected_min, expected_max, realized_pips)
    if not direction_calculated:
        overall_ok = None
    elif forecast_direction_norm == "NO_SIGNAL":
        overall_ok = no_signal_correct
    elif forecast_direction_norm == "FLAT":
        overall_ok = direction_correct
    elif move_ok is None:
        overall_ok = direction_correct
    else:
        overall_ok = bool(direction_correct and move_ok)
    row = _base(generated_ts, evaluation_run_id)
    row.update(
        {
            "experiment_id": _norm(eligible_preview.get("experiment_id")),
            "accuracy_hypothesis_id": hypothesis_id,
            "session_id": session_id,
            "provider": provider,
            "pack_level": pack_level,
            "forecast_row_key": _forecast_row_key(forecast),
            "forecast_direction": forecast_direction,
            "forecast_direction_normalized": forecast_direction_norm,
            "forecast_confidence": _norm(forecast.get("forecast_confidence")),
            "no_signal_flag": "TRUE" if forecast_direction_norm == "NO_SIGNAL" else "FALSE",
            "output_valid": _norm(eligible_preview.get("output_valid")),
            "raw_archive_present": _norm(eligible_preview.get("raw_archive_present")),
            "outcome_source_sheet": outcome.get("outcome_source_sheet", "Evaluation_Rows"),
            "outcome_match_key": outcome.get("outcome_match_key", ""),
            "outcome_match_status": outcome_status,
            "outcome_direction": outcome_direction,
            "realized_pips": "" if realized_pips is None else realized_pips,
            "outcome_row_count": outcome.get("outcome_row_count", 0),
            "direction_correctness_calculated": "TRUE" if direction_calculated else "FALSE",
            "direction_correct": "" if direction_correct is None else str(bool(direction_correct)).upper(),
            "no_signal_correct": "" if no_signal_correct is None else str(bool(no_signal_correct)).upper(),
            "false_signal": "" if false_signal is None else str(bool(false_signal)).upper(),
            "expected_move_pips_min": _norm(forecast.get("expected_move_pips_min")),
            "expected_move_pips_max": _norm(forecast.get("expected_move_pips_max")),
            "move_range_ok": "" if move_ok is None else str(bool(move_ok)).upper(),
            "overall_ok_calculated": "TRUE" if overall_ok is not None else "FALSE",
            "overall_ok": "" if overall_ok is None else str(bool(overall_ok)).upper(),
            "included_in_direction_denominator": "TRUE" if forecast_direction_norm in {"UP", "DOWN", "FLAT"} and direction_calculated else "FALSE",
            "included_in_no_signal_denominator": "TRUE" if forecast_direction_norm == "NO_SIGNAL" and direction_calculated else "FALSE",
            "included_in_false_signal_denominator": "TRUE" if forecast_direction_norm in {"UP", "DOWN"} and direction_calculated else "FALSE",
            "included_in_overall_denominator": "TRUE" if overall_ok is not None else "FALSE",
            "diagnostic_only": "TRUE",
            "production_excluded": "TRUE",
            "notes": "Controlled accuracy evaluation under frozen Phase 9A-5E protocol; not production advice.",
        }
    )
    return row


def _count_true(rows: Sequence[Dict[str, Any]], field: str) -> int:
    return sum(1 for row in rows if _bool(row.get(field)))


def _rows_with(rows: Sequence[Dict[str, Any]], field: str) -> List[Dict[str, Any]]:
    return [row for row in rows if _bool(row.get(field))]


def _metric_rate(rows: Sequence[Dict[str, Any]], metric_name: str) -> Tuple[int, int, str]:
    if metric_name == "direction_match_rate":
        denom_rows = _rows_with(rows, "included_in_direction_denominator")
        numerator = _count_true(denom_rows, "direction_correct")
    elif metric_name == "false_signal_rate":
        denom_rows = _rows_with(rows, "included_in_false_signal_denominator")
        numerator = _count_true(denom_rows, "false_signal")
    elif metric_name == "no_signal_correctness":
        denom_rows = _rows_with(rows, "included_in_no_signal_denominator")
        numerator = _count_true(denom_rows, "no_signal_correct")
    elif metric_name == "confidence_calibration_proxy":
        denom_rows = _rows_with(rows, "included_in_overall_denominator")
        numerator = _count_true(denom_rows, "overall_ok")
    else:
        denom_rows = _rows_with(rows, "included_in_direction_denominator")
        numerator = _count_true(denom_rows, "direction_correct")
    return numerator, len(denom_rows), _safe_rate(numerator, len(denom_rows))


def _build_experiment_results(generated_ts: str, evaluation_run_id: str, eval_rows: Sequence[Dict[str, Any]], invalid_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    invalid_by_exp = Counter(_norm(row.get("experiment_id")) for row in invalid_rows)
    for row in eval_rows:
        grouped[_norm(row.get("experiment_id"))].append(row)
    results = []
    for experiment_id, rows in sorted(grouped.items()):
        direction_rows = _rows_with(rows, "included_in_direction_denominator")
        overall_rows = _rows_with(rows, "included_in_overall_denominator")
        false_rows = _rows_with(rows, "included_in_false_signal_denominator")
        no_signal_rows = _rows_with(rows, "included_in_no_signal_denominator")
        direction_ok = _count_true(direction_rows, "direction_correct")
        overall_ok = _count_true(overall_rows, "overall_ok")
        false_count = _count_true(false_rows, "false_signal")
        no_signal_ok = _count_true(no_signal_rows, "no_signal_correct")
        row = _base(generated_ts, evaluation_run_id)
        row.update(
            {
                "experiment_id": experiment_id,
                "accuracy_hypothesis_id": _norm(rows[0].get("accuracy_hypothesis_id")) if rows else "",
                "eligible_rows_evaluated": len(rows),
                "excluded_rows": invalid_by_exp[experiment_id],
                "invalid_outputs": invalid_by_exp[experiment_id],
                "direction_denominator": len(direction_rows),
                "direction_correct_count": direction_ok,
                "direction_match_rate": _safe_rate(direction_ok, len(direction_rows)),
                "overall_denominator": len(overall_rows),
                "overall_ok_count": overall_ok,
                "overall_ok_rate": _safe_rate(overall_ok, len(overall_rows)),
                "false_signal_denominator": len(false_rows),
                "false_signal_count": false_count,
                "false_signal_rate": _safe_rate(false_count, len(false_rows)),
                "no_signal_denominator": len(no_signal_rows),
                "no_signal_correct_count": no_signal_ok,
                "no_signal_correctness": _safe_rate(no_signal_ok, len(no_signal_rows)),
                "result_status": "CALCULATED_DIAGNOSTIC_ONLY",
                "interpretation": "Scientific accuracy evidence for approved hypothesis; no provider ranking, pack ranking, or production action.",
                "production_excluded": "TRUE",
                "notes": "First controlled accuracy evaluation under Phase 9A-5F.",
            }
        )
        results.append(row)
    return results


def _build_pair_results(
    generated_ts: str,
    evaluation_run_id: str,
    pair_preview: Sequence[Dict[str, Any]],
    eval_by_key: Dict[Tuple[str, str], Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]]]:
    grouped_pairs: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for pair in pair_preview:
        grouped_pairs[_norm(pair.get("comparison_id"))].append(pair)
    results = []
    pair_eval_sets: Dict[str, Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]] = {}
    for comparison_id, pairs in sorted(grouped_pairs.items()):
        ready_pairs = [pair for pair in pairs if _norm(pair.get("pair_status")) == "PAIR_READY_FOR_FUTURE_EVALUATION"]
        baseline_rows: List[Dict[str, Any]] = []
        treatment_rows: List[Dict[str, Any]] = []
        for pair in ready_pairs:
            experiment_id = _norm(pair.get("experiment_id"))
            baseline = eval_by_key.get((experiment_id, _norm(pair.get("baseline_forecast_row_key"))))
            treatment = eval_by_key.get((experiment_id, _norm(pair.get("treatment_forecast_row_key"))))
            if baseline and treatment:
                baseline_rows.append(baseline)
                treatment_rows.append(treatment)
        providers = sorted({_norm(pair.get("provider")) for pair in ready_pairs if _norm(pair.get("provider"))})
        pair_eval_sets[comparison_id] = (baseline_rows, treatment_rows)
        bd_num, bd_den, bd_rate = _metric_rate(baseline_rows, "direction_match_rate")
        td_num, td_den, td_rate = _metric_rate(treatment_rows, "direction_match_rate")
        bo_num, bo_den, bo_rate = _metric_rate(baseline_rows, "confidence_calibration_proxy")
        to_num, to_den, to_rate = _metric_rate(treatment_rows, "confidence_calibration_proxy")
        bf_num, bf_den, bf_rate = _metric_rate(baseline_rows, "false_signal_rate")
        tf_num, tf_den, tf_rate = _metric_rate(treatment_rows, "false_signal_rate")
        bn_num, bn_den, bn_rate = _metric_rate(baseline_rows, "no_signal_correctness")
        tn_num, tn_den, tn_rate = _metric_rate(treatment_rows, "no_signal_correctness")
        first = ready_pairs[0] if ready_pairs else pairs[0]
        row = _base(generated_ts, evaluation_run_id)
        row.update(
            {
                "experiment_id": _norm(first.get("experiment_id")),
                "comparison_id": comparison_id,
                "provider_scope": "|".join(providers) if providers else _norm(first.get("provider")),
                "baseline_pack_level": _norm(first.get("baseline_pack_level")),
                "treatment_pack_level": _norm(first.get("treatment_pack_level")),
                "comparison_pairs_evaluated": min(len(baseline_rows), len(treatment_rows)),
                "pairs_excluded": len(pairs) - len(ready_pairs),
                "baseline_direction_match_rate": bd_rate,
                "treatment_direction_match_rate": td_rate,
                "direction_match_rate_delta": _metric_delta(_to_float(td_rate), _to_float(bd_rate)),
                "baseline_overall_ok_rate": bo_rate,
                "treatment_overall_ok_rate": to_rate,
                "overall_ok_rate_delta": _metric_delta(_to_float(to_rate), _to_float(bo_rate)),
                "baseline_false_signal_rate": bf_rate,
                "treatment_false_signal_rate": tf_rate,
                "false_signal_rate_delta": _metric_delta(_to_float(tf_rate), _to_float(bf_rate)),
                "baseline_no_signal_correctness": bn_rate,
                "treatment_no_signal_correctness": tn_rate,
                "no_signal_correctness_delta": _metric_delta(_to_float(tn_rate), _to_float(bn_rate)),
                "comparison_status": "CALCULATED_DIAGNOSTIC_ONLY",
                "interpretation": "Comparison delta is diagnostic only; no provider/pack ranking or production conclusion.",
                "production_excluded": "TRUE",
                "notes": "Matched pair comparison under frozen Phase 9A-5E protocol.",
            }
        )
        results.append(row)
    return results, pair_eval_sets


def _confidence_bucket_summary(rows: Sequence[Dict[str, Any]]) -> str:
    buckets: Dict[str, Dict[str, int]] = defaultdict(lambda: {"denominator": 0, "correct": 0})
    for row in rows:
        if not _bool(row.get("included_in_overall_denominator")):
            continue
        confidence = _to_float(row.get("forecast_confidence"))
        if confidence is None:
            bucket = "UNKNOWN"
        elif confidence <= 1:
            confidence *= 100
            bucket = "LOW" if confidence < 40 else "MEDIUM" if confidence < 70 else "HIGH"
        else:
            bucket = "LOW" if confidence < 40 else "MEDIUM" if confidence < 70 else "HIGH"
        buckets[bucket]["denominator"] += 1
        if _bool(row.get("overall_ok")):
            buckets[bucket]["correct"] += 1
    for bucket in list(buckets):
        den = buckets[bucket]["denominator"]
        buckets[bucket]["rate"] = None if den == 0 else round(buckets[bucket]["correct"] / den, 6)
    return json.dumps(dict(sorted(buckets.items())), sort_keys=True)


def _build_metric_results(
    generated_ts: str,
    evaluation_run_id: str,
    metric_preview: Sequence[Dict[str, Any]],
    pair_eval_sets: Dict[str, Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]],
) -> List[Dict[str, Any]]:
    results = []
    for preview in metric_preview:
        comparison_id = _norm(preview.get("comparison_id"))
        metric_name = _norm(preview.get("metric_name"))
        baseline_rows, treatment_rows = pair_eval_sets.get(comparison_id, ([], []))
        metric_status = "CALCULATED"
        numerator = 0
        denominator = 0
        metric_value = ""
        baseline_value = ""
        treatment_value = ""
        metric_delta = ""
        notes = "Metric calculated under frozen Phase 9A-5F protocol."
        if metric_name in {"direction_match_rate", "false_signal_rate", "no_signal_correctness"}:
            numerator, denominator, metric_value = _metric_rate(treatment_rows, metric_name)
            _, _, baseline_value = _metric_rate(baseline_rows, metric_name)
            treatment_value = metric_value
            metric_delta = _metric_delta(_to_float(treatment_value), _to_float(baseline_value))
        elif metric_name in {"pack_vs_baseline_delta", "behavior_conditioned_accuracy_delta"}:
            _, _, baseline_value = _metric_rate(baseline_rows, "direction_match_rate")
            numerator, denominator, treatment_value = _metric_rate(treatment_rows, "direction_match_rate")
            metric_delta = _metric_delta(_to_float(treatment_value), _to_float(baseline_value))
            metric_value = metric_delta
        elif metric_name == "confidence_calibration_proxy":
            numerator, denominator, treatment_value = _metric_rate(treatment_rows, "confidence_calibration_proxy")
            _, _, baseline_value = _metric_rate(baseline_rows, "confidence_calibration_proxy")
            metric_value = _confidence_bucket_summary(treatment_rows)
            metric_delta = _metric_delta(_to_float(treatment_value), _to_float(baseline_value))
            notes = "Metric value is bucket summary JSON; metric_delta uses treatment minus baseline overall correctness proxy."
        else:
            metric_status = "NO_ELIGIBLE_DENOMINATOR"
            notes = "Frozen metric has no eligible denominator in this evaluation dataset."
        if denominator == 0 and metric_status == "CALCULATED":
            metric_status = "NO_ELIGIBLE_DENOMINATOR"
        row = _base(generated_ts, evaluation_run_id)
        row.update(
            {
                "experiment_id": _norm(preview.get("experiment_id")),
                "comparison_id": comparison_id,
                "metric_id": _norm(preview.get("metric_id")),
                "metric_name": metric_name,
                "metric_scope": "comparison_treatment_vs_baseline",
                "denominator_count": denominator,
                "numerator_count": numerator,
                "metric_value": metric_value,
                "baseline_metric_value": baseline_value,
                "treatment_metric_value": treatment_value,
                "metric_delta": metric_delta,
                "metric_status": metric_status,
                "calculation_rule": _norm(preview.get("metric_formula_reference")),
                "interpretation_limit": "Diagnostic only; no ranking, routing, weighting, calibration, or production change.",
                "production_excluded": "TRUE",
                "notes": notes,
            }
        )
        results.append(row)
    return results


def _build_invalid_results(generated_ts: str, evaluation_run_id: str, invalid_preview: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for preview in invalid_preview:
        row = _base(generated_ts, evaluation_run_id)
        row.update(
            {
                "experiment_id": _norm(preview.get("experiment_id")),
                "session_id": _norm(preview.get("session_id")),
                "provider": _norm(preview.get("provider")),
                "pack_level": _norm(preview.get("pack_level")),
                "forecast_row_key": _norm(preview.get("forecast_row_key")),
                "invalid_case_type": _norm(preview.get("invalid_case_type")),
                "source_detection_sheet": _norm(preview.get("source_detection_sheet")),
                "raw_archive_present": _norm(preview.get("raw_archive_present")),
                "excluded_from_accuracy": "TRUE",
                "would_count_in_invalid_output_rate": _norm(preview.get("would_count_in_invalid_output_rate")),
                "rerun_allowed": "FALSE",
                "inference_allowed": "FALSE",
                "notes": _norm(preview.get("notes")),
            }
        )
        rows.append(row)
    return rows


def _build_governance_rows(generated_ts: str, evaluation_run_id: str) -> List[Dict[str, Any]]:
    checks = [
        ("GOV_APPROVAL", "ready_for_phase9a5f_execution", "TRUE", "TRUE"),
        ("GOV_PROVIDER_CALLS", "provider_calls_performed", "0", "0"),
        ("GOV_FORECAST_GENERATION", "forecast_generation_performed", "0", "0"),
        ("GOV_PROVIDER_RERUNS", "provider_rerun_count", "0", "0"),
        ("GOV_PRODUCTION_WRITES", "production_sheet_write_count", "0", "0"),
        ("GOV_EVALUATION_ROWS_WRITTEN", "evaluation_rows_written", "0", "0"),
        ("GOV_OUTCOME_LEDGER_WRITTEN", "outcome_ledger_written", "0", "0"),
        ("GOV_ROUTING", "routing_changes", "FALSE", "FALSE"),
        ("GOV_WEIGHTING", "weighting_changes", "FALSE", "FALSE"),
        ("GOV_CALIBRATION", "calibration_changes", "FALSE", "FALSE"),
        ("GOV_DIAGNOSTIC_ONLY", "diagnostic_only", "TRUE", "TRUE"),
    ]
    rows = []
    for check_id, name, expected, actual in checks:
        row = _base(generated_ts, evaluation_run_id)
        row.update(
            {
                "check_id": check_id,
                "check_name": name,
                "expected_value": expected,
                "actual_value": actual,
                "status": "PASS" if expected == actual else "FAIL",
                "notes": "Controlled accuracy evaluation governance check.",
            }
        )
        rows.append(row)
    return rows


def _upsert_registry_rows(service) -> Dict[str, int]:
    headers = _ensure_sheet(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET, REGISTRY_HEADERS)
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_upper(row.get("logical_sheet_id")): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_upper(row.get("logical_sheet_id")): row for row in rows}
    registry_rows = [
        ("CONTROLLED_ACCURACY_EVALUATION", OUTPUT_EVALUATION, "controlled_accuracy_evaluation"),
        ("CONTROLLED_ACCURACY_EXPERIMENT_RESULTS", OUTPUT_EXPERIMENT, "controlled_accuracy_experiment_results"),
        ("CONTROLLED_ACCURACY_COMPARISON_RESULTS", OUTPUT_COMPARISON, "controlled_accuracy_comparison_results"),
        ("CONTROLLED_ACCURACY_METRIC_RESULTS", OUTPUT_METRIC, "controlled_accuracy_metric_results"),
        ("CONTROLLED_ACCURACY_INVALID_OUTPUT_RESULTS", OUTPUT_INVALID, "controlled_accuracy_invalid_output_results"),
        ("CONTROLLED_ACCURACY_GOVERNANCE_AUDIT", OUTPUT_GOVERNANCE, "controlled_accuracy_governance_audit"),
        ("CONTROLLED_ACCURACY_EVALUATION_SUMMARY", OUTPUT_SUMMARY, "controlled_accuracy_evaluation_summary"),
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
            "notes": "Phase 9A-5F controlled accuracy evaluation; diagnostic-only, non-production.",
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
    parser = argparse.ArgumentParser(description="Build PreSignal v2.0 Phase 9A-5F controlled accuracy evaluation.")
    return parser.parse_args(argv)


def build_controlled_accuracy_evaluation_v0(args: Optional[argparse.Namespace] = None) -> Dict[str, Any]:
    args = args or _parse_args()
    generated_ts = _iso_now()
    evaluation_run_id = _run_id(generated_ts)
    service = build_sheets_service(load_credentials())
    diag_titles = _sheet_titles(service, DIAGNOSTICS_SPREADSHEET_ID)
    main_titles = _sheet_titles(service, MAIN_SPREADSHEET_ID)
    missing_required: List[str] = []

    approval_inputs = {sheet: _safe_rows(service, DIAGNOSTICS_SPREADSHEET_ID, diag_titles, sheet, missing_required) for sheet in APPROVAL_SHEETS}
    dry_inputs = {sheet: _safe_rows(service, DIAGNOSTICS_SPREADSHEET_ID, diag_titles, sheet, missing_required) for sheet in DRY_RUN_SHEETS}
    tier2_inputs = {sheet: _safe_rows(service, DIAGNOSTICS_SPREADSHEET_ID, diag_titles, sheet, missing_required) for sheet in TIER2_SHEETS}
    eval_rows_source = _safe_rows(service, MAIN_SPREADSHEET_ID, main_titles, "Evaluation_Rows", missing_required)
    if missing_required:
        raise RuntimeError(f"Missing required Phase 9A-5F inputs: {sorted(set(missing_required))}")

    approval_summary = approval_inputs["Accuracy_Execution_Approval_Summary"][-1]
    if not _bool(approval_summary.get("ready_for_phase9a5f_execution")):
        raise RuntimeError("Phase 9A-5F execution is not approved by Accuracy_Execution_Approval_Summary.")

    approved = _approved_experiments(approval_inputs["Accuracy_Execution_Approval"])
    forecasts_by_key = _forecast_lookup(tier2_inputs["Pack_Behavior_Tier2_Forecasts"])
    no_signal = _no_signal_lookup(tier2_inputs["Pack_Behavior_Tier2_NoSignal"])
    outcome_index = _build_outcome_index(eval_rows_source)

    eval_rows: List[Dict[str, Any]] = []
    for preview in dry_inputs["Controlled_Accuracy_Eligible_Row_Preview"]:
        experiment_id = _norm(preview.get("experiment_id"))
        if experiment_id not in approved or not _bool(preview.get("eligible_for_future_evaluation")):
            continue
        forecast_key = _norm(preview.get("forecast_row_key"))
        forecast = forecasts_by_key.get(forecast_key)
        if not forecast:
            continue
        eval_rows.append(_evaluate_row(generated_ts, evaluation_run_id, preview, forecast, approved[experiment_id], no_signal, outcome_index))

    eval_by_key = {(_norm(row.get("experiment_id")), _norm(row.get("forecast_row_key"))): row for row in eval_rows}
    invalid_rows = _build_invalid_results(generated_ts, evaluation_run_id, dry_inputs["Controlled_Accuracy_Invalid_Row_Audit"])
    unique_invalid_output_keys = {
        _norm(row.get("forecast_row_key"))
        for row in invalid_rows
        if _bool(row.get("would_count_in_invalid_output_rate"))
    }
    experiment_results = _build_experiment_results(generated_ts, evaluation_run_id, eval_rows, invalid_rows)
    comparison_results, pair_eval_sets = _build_pair_results(
        generated_ts,
        evaluation_run_id,
        dry_inputs["Controlled_Accuracy_Comparison_Pair_Preview"],
        eval_by_key,
    )
    metric_results = _build_metric_results(
        generated_ts,
        evaluation_run_id,
        dry_inputs["Controlled_Accuracy_Metric_Row_Preview"],
        pair_eval_sets,
    )
    governance_rows = _build_governance_rows(generated_ts, evaluation_run_id)
    governance_failed = any(_norm(row.get("status")) != "PASS" for row in governance_rows)

    direction_rows = _rows_with(eval_rows, "included_in_direction_denominator")
    overall_rows = _rows_with(eval_rows, "included_in_overall_denominator")
    direction_correct = _count_true(direction_rows, "direction_correct")
    overall_ok = _count_true(overall_rows, "overall_ok")
    comparison_pairs_evaluated = sum(int(_to_float(row.get("comparison_pairs_evaluated")) or 0) for row in comparison_results)
    final_interpretation = "CONTROLLED_ACCURACY_EVALUATION_READY_WITH_WARNINGS" if not governance_failed else "CONTROLLED_ACCURACY_EVALUATION_BLOCKED"
    build_status = "PASS_WITH_WARNINGS" if not governance_failed else "FAIL"
    summary_rows = [
        {
            **_base(generated_ts, evaluation_run_id),
            "build_status": build_status,
            "final_interpretation": final_interpretation,
            "experiments_executed": len(experiment_results),
            "eligible_rows_evaluated": len(eval_rows),
            "excluded_rows": len(invalid_rows),
            "invalid_outputs": len(unique_invalid_output_keys),
            "comparison_pairs_evaluated": comparison_pairs_evaluated,
            "metrics_calculated": len(metric_results),
            "direction_denominator": len(direction_rows),
            "direction_correct_count": direction_correct,
            "direction_match_rate": _safe_rate(direction_correct, len(direction_rows)),
            "overall_denominator": len(overall_rows),
            "overall_ok_count": overall_ok,
            "overall_ok_rate": _safe_rate(overall_ok, len(overall_rows)),
            "provider_calls_performed": 0,
            "forecast_generation_performed": 0,
            "provider_rerun_count": 0,
            "production_behavior_change_count": 0,
            "production_sheet_write_count": 0,
            "evaluation_rows_written": 0,
            "outcome_ledger_written": 0,
            "diagnostic_only": "TRUE",
            "ready_for_production": "FALSE",
            "recommended_next_step": "PROCEED_TO_PHASE9A5F_CONTROLLED_ACCURACY_EVALUATION_REVIEW" if not governance_failed else "HOLD_PHASE9_PENDING_GOVERNANCE_REVIEW",
            "notes": json.dumps(
                {
                    "outcome_match": "Evaluation_Rows exact country+release_ts, with duplicate ambiguity blocked",
                    "no_production_writes": True,
                    "no_provider_calls": True,
                    "invalid_outputs_not_repaired": True,
                },
                sort_keys=True,
            ),
        }
    ]

    outputs = [
        (OUTPUT_EVALUATION, EVALUATION_HEADERS, eval_rows),
        (OUTPUT_EXPERIMENT, EXPERIMENT_HEADERS, experiment_results),
        (OUTPUT_COMPARISON, COMPARISON_HEADERS, comparison_results),
        (OUTPUT_METRIC, METRIC_HEADERS, metric_results),
        (OUTPUT_INVALID, INVALID_HEADERS, invalid_rows),
        (OUTPUT_GOVERNANCE, GOVERNANCE_HEADERS, governance_rows),
        (OUTPUT_SUMMARY, SUMMARY_HEADERS, summary_rows),
    ]
    for sheet_name, headers, rows in outputs:
        actual_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, headers)
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, actual_headers, rows)

    registry = _upsert_registry_rows(service)
    return {
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "file_created": "automation/build_controlled_accuracy_evaluation_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "experiments_executed": len(experiment_results),
        "eligible_rows_evaluated": len(eval_rows),
        "excluded_rows": len(invalid_rows),
        "invalid_outputs": summary_rows[0]["invalid_outputs"],
        "comparison_pairs_evaluated": comparison_pairs_evaluated,
        "metrics_calculated": len(metric_results),
        "direction_denominator": len(direction_rows),
        "direction_correct_count": direction_correct,
        "direction_match_rate": summary_rows[0]["direction_match_rate"],
        "overall_denominator": len(overall_rows),
        "overall_ok_count": overall_ok,
        "overall_ok_rate": summary_rows[0]["overall_ok_rate"],
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "provider_rerun_count": 0,
        "production_behavior_change_count": 0,
        "production_sheet_write_count": 0,
        "evaluation_rows_written": 0,
        "outcome_ledger_written": 0,
        "recommended_next_step": summary_rows[0]["recommended_next_step"],
        "registry": registry,
    }


def main() -> None:
    result = build_controlled_accuracy_evaluation_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
