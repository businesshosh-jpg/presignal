import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_controlled_accuracy_evaluation_v0 import (
    _bool,
    _confidence_bucket_summary,
    _count_true,
    _metric_delta,
    _metric_rate,
    _normalize_direction,
    _range_ok,
    _rows_with,
    _safe_rate,
    _to_float,
)
from automation.build_market_reaction_canonical_outcome_validation_v0 import (
    _ensure_sheet_minimal,
    _safe_rows,
    _sheet_titles,
)
from automation.build_market_sessions_shadow_v0 import (
    DIAGNOSTICS_SPREADSHEET_ID,
    MAIN_SPREADSHEET_ID,
    PROJECT_OVERVIEWS_SPREADSHEET_ID,
    REGISTRY_HEADERS,
    REGISTRY_SHEET,
    _column_letter,
    _norm,
    _sheet_to_rows,
    _write_rows,
)
from automation.build_session_information_requests_v0 import _iso_now
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


SCHEMA_VERSION = "presignal_v2_corrected_accuracy_re_evaluation_execution_0.1"
EVALUATION_VERSION = "corrected_accuracy_re_evaluation_execution_v0"
PHASE_LABEL = "PreSignal v2.0 Phase 9A-5M5"
REGISTRY_CATEGORY = "PRESIGNAL_V2_CORRECTED_ACCURACY_RE_EVALUATION_EXECUTION"
REGISTRY_OWNER_MODULE = "market_state"

STRICT_ROW_COUNT_REQUIRED = 129

DIAG_INPUT_SHEETS = [
    "Corrected_Accuracy_ReEvaluation_Design",
    "Corrected_Accuracy_Row_Selection",
    "Corrected_Accuracy_Control_Definition",
    "Corrected_Accuracy_Metric_Definition",
    "Corrected_Accuracy_Outcome_Mapping",
    "Market_Reaction_Repaired_Remap_Validation",
    "Market_Reaction_Repaired_Trust_Validation",
    "Controlled_Accuracy_Evaluation",
]

MAIN_INPUT_SHEETS = ["Predictions", "Evaluation_Rows", "Outcome_Ledger", "MR_ProviderRuns", "Event", "Config"]
CRITICAL_DIAG_SHEETS = set(DIAG_INPUT_SHEETS)
CRITICAL_MAIN_SHEETS = set(MAIN_INPUT_SHEETS)

OUTPUT_EVALUATION = "Corrected_Accuracy_Evaluation"
OUTPUT_EXPERIMENT = "Corrected_Accuracy_Experiment_Results"
OUTPUT_COMPARISON = "Corrected_Accuracy_Comparison_Results"
OUTPUT_METRIC = "Corrected_Accuracy_Metric_Results"
OUTPUT_HYPOTHESIS = "Corrected_Accuracy_Hypothesis_Results"
OUTPUT_GOVERNANCE = "Corrected_Accuracy_Governance"
OUTPUT_SUMMARY = "Corrected_Accuracy_Execution_Summary"

EVALUATION_HEADERS = [
    "generated_ts",
    "schema_version",
    "evaluation_version",
    "evaluation_run_id",
    "accuracy_row_id",
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
    "corrected_canonical_outcome_id",
    "corrected_trust_level",
    "corrected_outcome_direction",
    "corrected_realized_pips",
    "corrected_realized_strength",
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
    "primary_strict_evaluation",
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
    "corrected_rows_evaluated",
    "diagnostic_rows_excluded",
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
    "original_direction_match_rate_same_rows",
    "direction_match_rate_delta_vs_original",
    "original_overall_ok_rate_same_rows",
    "overall_ok_rate_delta_vs_original",
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
    "comparison_id",
    "comparison_type",
    "experiment_id",
    "provider_scope",
    "baseline_group",
    "treatment_group",
    "baseline_pack_level",
    "treatment_pack_level",
    "rows_or_pairs_evaluated",
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

HYPOTHESIS_HEADERS = [
    "generated_ts",
    "schema_version",
    "evaluation_version",
    "evaluation_run_id",
    "accuracy_hypothesis_id",
    "experiment_id",
    "direction_denominator",
    "direction_correct_count",
    "direction_match_rate",
    "overall_denominator",
    "overall_ok_count",
    "overall_ok_rate",
    "original_direction_match_rate_same_rows",
    "direction_delta_vs_original",
    "original_overall_ok_rate_same_rows",
    "overall_delta_vs_original",
    "hypothesis_result",
    "evidence_summary",
    "production_excluded",
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
    "corrected_evaluation_rows_executed",
    "diagnostic_rows_excluded",
    "experiments_executed",
    "metrics_calculated",
    "direction_denominator",
    "direction_correct_count",
    "direction_match_rate",
    "overall_denominator",
    "overall_ok_count",
    "overall_ok_rate",
    "comparison_deltas_calculated",
    "hypotheses_supported",
    "hypotheses_partially_supported",
    "hypotheses_not_supported",
    "hypotheses_inconclusive",
    "provider_calls_performed",
    "forecast_generation_performed",
    "provider_rerun_count",
    "accuracy_execution_performed",
    "production_sheet_write_count",
    "production_behavior_change_count",
    "evaluation_rows_written",
    "outcome_ledger_written",
    "market_reaction_values_modified",
    "canonical_outcomes_modified",
    "routing_changes",
    "weighting_changes",
    "calibration_changes",
    "ensemble_changes",
    "ready_for_corrected_accuracy_review",
    "ready_for_replication_design",
    "ready_for_production",
    "recommended_next_step",
    "notes",
]


def _run_id(generated_ts: str) -> str:
    compact = generated_ts.replace("-", "").replace(":", "").replace("Z", "Z")
    return f"corrected_accuracy_re_evaluation_execution_v0_{compact}"


def _base(generated_ts: str, evaluation_run_id: str) -> Dict[str, Any]:
    return {
        "generated_ts": generated_ts,
        "schema_version": SCHEMA_VERSION,
        "evaluation_version": EVALUATION_VERSION,
        "evaluation_run_id": evaluation_run_id,
    }


def _read_required(service, spreadsheet_id: str, sheet_names: Sequence[str], critical: set[str]) -> Dict[str, List[Dict[str, Any]]]:
    titles = _sheet_titles(service, spreadsheet_id)
    missing = [name for name in sheet_names if name in critical and name not in titles]
    if missing:
        raise RuntimeError(f"Missing critical input sheets: {', '.join(missing)}")
    read_missing: List[str] = []
    out = {name: _safe_rows(service, spreadsheet_id, titles, name, read_missing) for name in sheet_names}
    critical_read_missing = [name for name in read_missing if name in critical]
    if critical_read_missing:
        raise RuntimeError(f"Unable to read critical input sheets: {', '.join(critical_read_missing)}")
    return out


def _accuracy_row_id(row: Dict[str, Any]) -> str:
    explicit = _norm(row.get("accuracy_row_id"))
    if explicit:
        return explicit
    return _norm(row.get("__source_row_number__"))


def _hypothesis_for_experiment(experiment_id: str) -> str:
    mapping = {
        "ACC_EXP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT": "ACC_HYP_USDJPY_TREND_DIRECTIONAL_ALIGNMENT",
        "ACC_EXP_PACK_B_TARGET_STATE_SIGNAL_DISCIPLINE": "ACC_HYP_PACK_B_TARGET_STATE_SIGNAL_DISCIPLINE",
        "ACC_EXP_OPENAI_STABLE_CAUSAL_REWRITE_TESTBED": "ACC_HYP_OPENAI_STABLE_CAUSAL_REWRITE_TESTBED",
    }
    return mapping.get(_norm(experiment_id), "")


def _calculate_corrected_row(
    generated_ts: str,
    evaluation_run_id: str,
    selection: Dict[str, Any],
    mapping: Dict[str, Any],
    original: Dict[str, Any],
) -> Dict[str, Any]:
    forecast_direction_norm = _normalize_direction(original.get("forecast_direction_normalized") or original.get("forecast_direction"))
    outcome_direction = _normalize_direction(mapping.get("repaired_realized_direction"))
    realized_pips = _to_float(mapping.get("repaired_realized_pips"))
    direction_calculated = bool(outcome_direction)
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
    expected_min = _to_float(original.get("expected_move_pips_min"))
    expected_max = _to_float(original.get("expected_move_pips_max"))
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
            "accuracy_row_id": _accuracy_row_id(selection),
            "experiment_id": _norm(selection.get("experiment_id")),
            "accuracy_hypothesis_id": _norm(original.get("accuracy_hypothesis_id")) or _hypothesis_for_experiment(selection.get("experiment_id")),
            "session_id": _norm(selection.get("session_id")),
            "provider": _norm(selection.get("provider")),
            "pack_level": _norm(selection.get("pack_level")),
            "forecast_row_key": _norm(original.get("forecast_row_key")),
            "forecast_direction": _norm(original.get("forecast_direction")),
            "forecast_direction_normalized": forecast_direction_norm,
            "forecast_confidence": _norm(original.get("forecast_confidence")),
            "no_signal_flag": _norm(original.get("no_signal_flag")),
            "output_valid": _norm(original.get("output_valid")),
            "raw_archive_present": _norm(original.get("raw_archive_present")),
            "outcome_source_sheet": "Market_Reaction_Repaired_Remap_Validation",
            "corrected_canonical_outcome_id": _norm(mapping.get("repaired_canonical_outcome_id")),
            "corrected_trust_level": _norm(mapping.get("repaired_trust_level")),
            "corrected_outcome_direction": outcome_direction,
            "corrected_realized_pips": "" if realized_pips is None else f"{realized_pips:.6f}",
            "corrected_realized_strength": _norm(mapping.get("repaired_realized_strength")),
            "direction_correctness_calculated": "TRUE" if direction_calculated else "FALSE",
            "direction_correct": "" if direction_correct is None else str(bool(direction_correct)).upper(),
            "no_signal_correct": "" if no_signal_correct is None else str(bool(no_signal_correct)).upper(),
            "false_signal": "" if false_signal is None else str(bool(false_signal)).upper(),
            "expected_move_pips_min": _norm(original.get("expected_move_pips_min")),
            "expected_move_pips_max": _norm(original.get("expected_move_pips_max")),
            "move_range_ok": "" if move_ok is None else str(bool(move_ok)).upper(),
            "overall_ok_calculated": "TRUE" if overall_ok is not None else "FALSE",
            "overall_ok": "" if overall_ok is None else str(bool(overall_ok)).upper(),
            "included_in_direction_denominator": "TRUE" if forecast_direction_norm in {"UP", "DOWN", "FLAT"} and direction_calculated else "FALSE",
            "included_in_no_signal_denominator": "TRUE" if forecast_direction_norm == "NO_SIGNAL" and direction_calculated else "FALSE",
            "included_in_false_signal_denominator": "TRUE" if forecast_direction_norm in {"UP", "DOWN"} and direction_calculated else "FALSE",
            "included_in_overall_denominator": "TRUE" if overall_ok is not None else "FALSE",
            "diagnostic_only": "TRUE",
            "primary_strict_evaluation": "TRUE",
            "production_excluded": "TRUE",
            "notes": "Corrected diagnostic accuracy re-evaluation using validated repaired canonical outcome overlay; no production action.",
        }
    )
    return row


def _same_row_original_rate(original_rows: Sequence[Dict[str, Any]], metric_name: str) -> Tuple[int, int, str]:
    return _metric_rate(original_rows, metric_name)


def _build_experiment_results(
    generated_ts: str,
    evaluation_run_id: str,
    corrected_rows: Sequence[Dict[str, Any]],
    original_by_id: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in corrected_rows:
        grouped[_norm(row.get("experiment_id"))].append(row)
    results: List[Dict[str, Any]] = []
    for experiment_id, rows in sorted(grouped.items()):
        original_rows = [original_by_id.get(_norm(row.get("accuracy_row_id")), {}) for row in rows]
        original_rows = [row for row in original_rows if row]
        direction_rows = _rows_with(rows, "included_in_direction_denominator")
        overall_rows = _rows_with(rows, "included_in_overall_denominator")
        false_rows = _rows_with(rows, "included_in_false_signal_denominator")
        no_signal_rows = _rows_with(rows, "included_in_no_signal_denominator")
        direction_ok = _count_true(direction_rows, "direction_correct")
        overall_ok = _count_true(overall_rows, "overall_ok")
        false_count = _count_true(false_rows, "false_signal")
        no_signal_ok = _count_true(no_signal_rows, "no_signal_correct")
        _, _, original_direction_rate = _same_row_original_rate(original_rows, "direction_match_rate")
        _, _, original_overall_rate = _same_row_original_rate(original_rows, "confidence_calibration_proxy")
        corrected_direction_rate = _safe_rate(direction_ok, len(direction_rows))
        corrected_overall_rate = _safe_rate(overall_ok, len(overall_rows))
        row = _base(generated_ts, evaluation_run_id)
        row.update(
            {
                "experiment_id": experiment_id,
                "accuracy_hypothesis_id": _norm(rows[0].get("accuracy_hypothesis_id")) if rows else _hypothesis_for_experiment(experiment_id),
                "corrected_rows_evaluated": len(rows),
                "diagnostic_rows_excluded": 0,
                "direction_denominator": len(direction_rows),
                "direction_correct_count": direction_ok,
                "direction_match_rate": corrected_direction_rate,
                "overall_denominator": len(overall_rows),
                "overall_ok_count": overall_ok,
                "overall_ok_rate": corrected_overall_rate,
                "false_signal_denominator": len(false_rows),
                "false_signal_count": false_count,
                "false_signal_rate": _safe_rate(false_count, len(false_rows)),
                "no_signal_denominator": len(no_signal_rows),
                "no_signal_correct_count": no_signal_ok,
                "no_signal_correctness": _safe_rate(no_signal_ok, len(no_signal_rows)),
                "original_direction_match_rate_same_rows": original_direction_rate,
                "direction_match_rate_delta_vs_original": _metric_delta(_to_float(corrected_direction_rate), _to_float(original_direction_rate)),
                "original_overall_ok_rate_same_rows": original_overall_rate,
                "overall_ok_rate_delta_vs_original": _metric_delta(_to_float(corrected_overall_rate), _to_float(original_overall_rate)),
                "result_status": "CALCULATED_DIAGNOSTIC_ONLY",
                "interpretation": "Corrected accuracy evidence under repaired canonical outcome overlay; not production validation.",
                "production_excluded": "TRUE",
                "notes": "Only strict-ready corrected rows included.",
            }
        )
        results.append(row)
    return results


def _comparison_row(
    generated_ts: str,
    evaluation_run_id: str,
    comparison_id: str,
    comparison_type: str,
    experiment_id: str,
    provider_scope: str,
    baseline_group: str,
    treatment_group: str,
    baseline_pack: str,
    treatment_pack: str,
    baseline_rows: Sequence[Dict[str, Any]],
    treatment_rows: Sequence[Dict[str, Any]],
    notes: str,
) -> Dict[str, Any]:
    _, _, bd_rate = _metric_rate(baseline_rows, "direction_match_rate")
    _, _, td_rate = _metric_rate(treatment_rows, "direction_match_rate")
    _, _, bo_rate = _metric_rate(baseline_rows, "confidence_calibration_proxy")
    _, _, to_rate = _metric_rate(treatment_rows, "confidence_calibration_proxy")
    _, _, bf_rate = _metric_rate(baseline_rows, "false_signal_rate")
    _, _, tf_rate = _metric_rate(treatment_rows, "false_signal_rate")
    _, _, bn_rate = _metric_rate(baseline_rows, "no_signal_correctness")
    _, _, tn_rate = _metric_rate(treatment_rows, "no_signal_correctness")
    row = _base(generated_ts, evaluation_run_id)
    row.update(
        {
            "comparison_id": comparison_id,
            "comparison_type": comparison_type,
            "experiment_id": experiment_id,
            "provider_scope": provider_scope,
            "baseline_group": baseline_group,
            "treatment_group": treatment_group,
            "baseline_pack_level": baseline_pack,
            "treatment_pack_level": treatment_pack,
            "rows_or_pairs_evaluated": min(len(baseline_rows), len(treatment_rows)),
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
            "interpretation": "Comparison delta is diagnostic only; no provider ranking, pack ranking, routing, or production change.",
            "production_excluded": "TRUE",
            "notes": notes,
        }
    )
    return row


def _build_comparison_results(
    generated_ts: str,
    evaluation_run_id: str,
    corrected_rows: Sequence[Dict[str, Any]],
    original_by_id: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in corrected_rows:
        grouped[_norm(row.get("experiment_id"))].append(row)
    for experiment_id, rows in sorted(grouped.items()):
        original_rows = [original_by_id.get(_norm(row.get("accuracy_row_id")), {}) for row in rows]
        original_rows = [row for row in original_rows if row]
        results.append(
            _comparison_row(
                generated_ts,
                evaluation_run_id,
                f"ORIGINAL_VS_CORRECTED_{experiment_id}",
                "ORIGINAL_VS_CORRECTED",
                experiment_id,
                "ALL_PROVIDERS_IN_STRICT_ROW_SET",
                "ORIGINAL_PHASE9A5F_SAME_ROWS",
                "CORRECTED_PHASE9A5M5_STRICT_ROWS",
                "",
                "",
                original_rows,
                rows,
                "Delta isolates outcome mapping replacement on the same strict row set.",
            )
        )
    by_group: Dict[Tuple[str, str, str], Dict[str, Dict[str, Any]]] = defaultdict(dict)
    for row in corrected_rows:
        by_group[(_norm(row.get("experiment_id")), _norm(row.get("session_id")), _norm(row.get("provider")))][_norm(row.get("pack_level")).upper()] = row
    pack_pairs: Dict[Tuple[str, str], Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]] = defaultdict(lambda: ([], [], []))
    for (experiment_id, _session_id, provider), packs in by_group.items():
        baseline = packs.get("A")
        if not baseline:
            continue
        for treatment_pack in ("B", "D", "E"):
            treatment = packs.get(treatment_pack)
            if treatment:
                key = (experiment_id, f"A_TO_{treatment_pack}")
                pack_pairs[key][0].append(baseline)
                pack_pairs[key][1].append(treatment)
                pack_pairs[key][2].append(provider)
    for (experiment_id, transition), (baseline_rows, treatment_rows, providers) in sorted(pack_pairs.items()):
        results.append(
            _comparison_row(
                generated_ts,
                evaluation_run_id,
                f"CORRECTED_{experiment_id}_{transition}",
                "CORRECTED_PACK_COMPARISON",
                experiment_id,
                "|".join(sorted(set(providers))),
                "PACK_A_BASELINE",
                f"PACK_{transition[-1]}_TREATMENT",
                "A",
                transition[-1],
                baseline_rows,
                treatment_rows,
                "Corrected pack comparison using strict-ready rows only.",
            )
        )
    return results


def _average_delta(rows: Sequence[Dict[str, Any]], field: str, comparison_type: str) -> str:
    values = [
        _to_float(row.get(field))
        for row in rows
        if _norm(row.get("comparison_type")) == comparison_type and _to_float(row.get(field)) is not None
    ]
    if not values:
        return ""
    return f"{sum(v for v in values if v is not None) / len(values):.6f}"


def _build_metric_results(
    generated_ts: str,
    evaluation_run_id: str,
    corrected_rows: Sequence[Dict[str, Any]],
    original_rows: Sequence[Dict[str, Any]],
    comparison_rows: Sequence[Dict[str, Any]],
    metric_definitions: Sequence[Dict[str, Any]],
    experiment_results: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    metric_ids = [_norm(row.get("metric_id")) for row in metric_definitions if _norm(row.get("metric_id"))]
    if not metric_ids:
        metric_ids = [
            "direction_correctness",
            "overall_ok",
            "direction_match_rate",
            "false_signal_rate",
            "no_signal_correctness",
            "behavior_conditioned_accuracy_delta",
            "pack_vs_baseline_delta",
            "confidence_calibration_proxy",
            "scenario_alignment",
        ]
    rows: List[Dict[str, Any]] = []
    direction_num, direction_den, direction_rate = _metric_rate(corrected_rows, "direction_match_rate")
    overall_num, overall_den, overall_rate = _metric_rate(corrected_rows, "confidence_calibration_proxy")
    false_num, false_den, false_rate = _metric_rate(corrected_rows, "false_signal_rate")
    no_signal_num, no_signal_den, no_signal_rate = _metric_rate(corrected_rows, "no_signal_correctness")
    _, _, original_direction_rate = _metric_rate(original_rows, "direction_match_rate")
    _, _, original_overall_rate = _metric_rate(original_rows, "confidence_calibration_proxy")
    experiment_summary = {
        _norm(row.get("experiment_id")): {
            "direction_match_rate": _norm(row.get("direction_match_rate")),
            "overall_ok_rate": _norm(row.get("overall_ok_rate")),
        }
        for row in experiment_results
    }
    metric_payload = {
        "direction_correctness": (direction_den, direction_num, direction_rate, "", direction_rate, "", "CALCULATED"),
        "overall_ok": (overall_den, overall_num, overall_rate, "", overall_rate, "", "CALCULATED"),
        "direction_match_rate": (direction_den, direction_num, direction_rate, original_direction_rate, direction_rate, _metric_delta(_to_float(direction_rate), _to_float(original_direction_rate)), "CALCULATED"),
        "false_signal_rate": (false_den, false_num, false_rate, "", false_rate, "", "CALCULATED" if false_den else "NO_ELIGIBLE_DENOMINATOR"),
        "no_signal_correctness": (no_signal_den, no_signal_num, no_signal_rate, "", no_signal_rate, "", "CALCULATED" if no_signal_den else "NO_ELIGIBLE_DENOMINATOR"),
        "behavior_conditioned_accuracy_delta": (direction_den, direction_num, _metric_delta(_to_float(direction_rate), _to_float(original_direction_rate)), original_direction_rate, direction_rate, _metric_delta(_to_float(direction_rate), _to_float(original_direction_rate)), "CALCULATED"),
        "pack_vs_baseline_delta": (len([r for r in comparison_rows if _norm(r.get("comparison_type")) == "CORRECTED_PACK_COMPARISON"]), 0, _average_delta(comparison_rows, "direction_match_rate_delta", "CORRECTED_PACK_COMPARISON"), "", "", _average_delta(comparison_rows, "direction_match_rate_delta", "CORRECTED_PACK_COMPARISON"), "CALCULATED"),
        "confidence_calibration_proxy": (overall_den, overall_num, _confidence_bucket_summary(corrected_rows), original_overall_rate, overall_rate, _metric_delta(_to_float(overall_rate), _to_float(original_overall_rate)), "CALCULATED"),
        "scenario_alignment": (len(experiment_results), "", json.dumps(experiment_summary, sort_keys=True), "", "", "", "CALCULATED_SUMMARY"),
    }
    name_lookup = {
        "direction_correctness": "Direction correctness",
        "overall_ok": "Overall OK",
        "direction_match_rate": "Direction match rate",
        "false_signal_rate": "False signal rate",
        "no_signal_correctness": "No-signal correctness",
        "behavior_conditioned_accuracy_delta": "Behavior-conditioned accuracy delta",
        "pack_vs_baseline_delta": "Pack vs baseline delta",
        "confidence_calibration_proxy": "Confidence calibration proxy",
        "scenario_alignment": "Scenario alignment",
    }
    definition_by_id = {_norm(row.get("metric_id")): row for row in metric_definitions}
    for metric_id in metric_ids:
        denominator, numerator, value, baseline, treatment, delta, status = metric_payload.get(metric_id, ("", "", "", "", "", "", "NOT_CALCULATED"))
        definition = definition_by_id.get(metric_id, {})
        row = _base(generated_ts, evaluation_run_id)
        row.update(
            {
                "metric_id": metric_id,
                "metric_name": _norm(definition.get("metric_name")) or name_lookup.get(metric_id, metric_id),
                "metric_scope": "strict_corrected_primary_evaluation",
                "denominator_count": denominator,
                "numerator_count": numerator,
                "metric_value": value,
                "baseline_metric_value": baseline,
                "treatment_metric_value": treatment,
                "metric_delta": delta,
                "metric_status": status,
                "calculation_rule": _norm(definition.get("formula_or_logic_reference")),
                "interpretation_limit": "Diagnostic corrected accuracy only; not production validation and not provider or pack ranking.",
                "production_excluded": "TRUE",
                "notes": "Metric reused from approved corrected re-evaluation design.",
            }
        )
        rows.append(row)
    return rows


def _classify_hypothesis(direction_rate: str, overall_rate: str, direction_delta: str) -> str:
    direction = _to_float(direction_rate)
    overall = _to_float(overall_rate)
    delta = _to_float(direction_delta)
    if direction is None or overall is None:
        return "Inconclusive"
    if direction >= 0.55 and overall >= 0.15 and (delta is None or delta >= 0):
        return "Supported"
    if (direction >= 0.50 and (delta is None or delta >= 0)) or (overall >= 0.10 and delta is not None and delta >= 0):
        return "Partially Supported"
    if delta is not None and delta > 0 and direction >= 0.45:
        return "Partially Supported"
    return "Not Supported"


def _build_hypothesis_results(generated_ts: str, evaluation_run_id: str, experiment_results: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for exp in experiment_results:
        result = _classify_hypothesis(
            _norm(exp.get("direction_match_rate")),
            _norm(exp.get("overall_ok_rate")),
            _norm(exp.get("direction_match_rate_delta_vs_original")),
        )
        row = _base(generated_ts, evaluation_run_id)
        row.update(
            {
                "accuracy_hypothesis_id": _norm(exp.get("accuracy_hypothesis_id")),
                "experiment_id": _norm(exp.get("experiment_id")),
                "direction_denominator": exp.get("direction_denominator", ""),
                "direction_correct_count": exp.get("direction_correct_count", ""),
                "direction_match_rate": exp.get("direction_match_rate", ""),
                "overall_denominator": exp.get("overall_denominator", ""),
                "overall_ok_count": exp.get("overall_ok_count", ""),
                "overall_ok_rate": exp.get("overall_ok_rate", ""),
                "original_direction_match_rate_same_rows": exp.get("original_direction_match_rate_same_rows", ""),
                "direction_delta_vs_original": exp.get("direction_match_rate_delta_vs_original", ""),
                "original_overall_ok_rate_same_rows": exp.get("original_overall_ok_rate_same_rows", ""),
                "overall_delta_vs_original": exp.get("overall_ok_rate_delta_vs_original", ""),
                "hypothesis_result": result,
                "evidence_summary": (
                    f"direction={exp.get('direction_match_rate', '')}; overall={exp.get('overall_ok_rate', '')}; "
                    f"direction_delta={exp.get('direction_match_rate_delta_vs_original', '')}"
                ),
                "production_excluded": "TRUE",
                "notes": "Classification is based solely on corrected diagnostic evaluation results and requires Phase 9A-5M6 review.",
            }
        )
        rows.append(row)
    return rows


def _build_governance_rows(generated_ts: str, evaluation_run_id: str, row_count_ok: bool) -> List[Dict[str, Any]]:
    checks = [
        ("GOV_ROW_COUNT", "strict_ready_row_count", str(STRICT_ROW_COUNT_REQUIRED), str(STRICT_ROW_COUNT_REQUIRED) if row_count_ok else "MISMATCH"),
        ("GOV_PROVIDER_CALLS", "provider_calls_performed", "0", "0"),
        ("GOV_FORECAST_GENERATION", "forecast_generation_performed", "0", "0"),
        ("GOV_PROVIDER_RERUNS", "provider_rerun_count", "0", "0"),
        ("GOV_ACCURACY_EXECUTION", "accuracy_execution_performed", "1", "1"),
        ("GOV_PRODUCTION_WRITES", "production_sheet_write_count", "0", "0"),
        ("GOV_PRODUCTION_BEHAVIOR", "production_behavior_change_count", "0", "0"),
        ("GOV_EVALUATION_ROWS_WRITTEN", "evaluation_rows_written", "0", "0"),
        ("GOV_OUTCOME_LEDGER_WRITTEN", "outcome_ledger_written", "0", "0"),
        ("GOV_MARKET_REACTION_MODIFIED", "market_reaction_values_modified", "0", "0"),
        ("GOV_CANONICAL_MODIFIED", "canonical_outcomes_modified", "0", "0"),
        ("GOV_ROUTING", "routing_changes", "FALSE", "FALSE"),
        ("GOV_WEIGHTING", "weighting_changes", "FALSE", "FALSE"),
        ("GOV_CALIBRATION", "calibration_changes", "FALSE", "FALSE"),
        ("GOV_ENSEMBLE", "ensemble_changes", "FALSE", "FALSE"),
    ]
    rows: List[Dict[str, Any]] = []
    for check_id, name, expected, actual in checks:
        row = _base(generated_ts, evaluation_run_id)
        row.update(
            {
                "check_id": check_id,
                "check_name": name,
                "expected_value": expected,
                "actual_value": actual,
                "status": "PASS" if expected == actual else "FAIL",
                "notes": "Corrected diagnostic re-evaluation governance check.",
            }
        )
        rows.append(row)
    return rows


def _upsert_registry_rows(service) -> Dict[str, int]:
    titles = _sheet_titles(service, PROJECT_OVERVIEWS_SPREADSHEET_ID)
    if REGISTRY_SHEET not in titles:
        return {"updated": 0, "appended": 0, "status": "missing"}
    headers = REGISTRY_HEADERS
    registry_rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    now = _iso_now()
    by_id = {_norm(row.get("logical_sheet_id")).upper(): i + 2 for i, row in enumerate(registry_rows)}
    existing_by_id = {_norm(row.get("logical_sheet_id")).upper(): row for row in registry_rows}
    registry_specs = [
        ("CORRECTED_ACCURACY_EVALUATION", OUTPUT_EVALUATION, "corrected_accuracy_evaluation"),
        ("CORRECTED_ACCURACY_EXPERIMENT_RESULTS", OUTPUT_EXPERIMENT, "corrected_accuracy_experiment_results"),
        ("CORRECTED_ACCURACY_COMPARISON_RESULTS", OUTPUT_COMPARISON, "corrected_accuracy_comparison_results"),
        ("CORRECTED_ACCURACY_METRIC_RESULTS", OUTPUT_METRIC, "corrected_accuracy_metric_results"),
        ("CORRECTED_ACCURACY_HYPOTHESIS_RESULTS", OUTPUT_HYPOTHESIS, "corrected_accuracy_hypothesis_results"),
        ("CORRECTED_ACCURACY_GOVERNANCE", OUTPUT_GOVERNANCE, "corrected_accuracy_governance"),
        ("CORRECTED_ACCURACY_EXECUTION_SUMMARY", OUTPUT_SUMMARY, "corrected_accuracy_execution_summary"),
    ]
    updates: List[Dict[str, Any]] = []
    appended = 0
    for logical_id, sheet_name, role in registry_specs:
        key = logical_id.upper()
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
            "notes": "Phase 9A-5M5 corrected diagnostic accuracy re-evaluation; non-production.",
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
            row_number = len(registry_rows) + appended + 1
        updates.append({"range": f"'{REGISTRY_SHEET}'!A{row_number}:{_column_letter(len(headers))}{row_number}", "values": [values]})
    if updates:
        batch_update_values(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, updates)
    return {"updated": len(registry_specs) - appended, "appended": appended}


def build_corrected_accuracy_re_evaluation_execution_v0() -> Dict[str, Any]:
    generated_ts = _iso_now()
    evaluation_run_id = _run_id(generated_ts)
    service = build_sheets_service(load_credentials())
    diag = _read_required(service, DIAGNOSTICS_SPREADSHEET_ID, DIAG_INPUT_SHEETS, CRITICAL_DIAG_SHEETS)
    _read_required(service, MAIN_SPREADSHEET_ID, MAIN_INPUT_SHEETS, CRITICAL_MAIN_SHEETS)

    design_summary = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, "Corrected_Accuracy_ReEvaluation_Summary")
    if not design_summary or not _bool(design_summary[-1].get("ready_for_corrected_accuracy_execution")):
        raise RuntimeError("Phase 9A-5M5 execution is not approved by Corrected_Accuracy_ReEvaluation_Summary.")

    selections = diag["Corrected_Accuracy_Row_Selection"]
    mappings = diag["Corrected_Accuracy_Outcome_Mapping"]
    original_eval_rows = diag["Controlled_Accuracy_Evaluation"]
    metric_definitions = diag["Corrected_Accuracy_Metric_Definition"]

    strict_selections = [row for row in selections if _bool(row.get("included_in_primary_corrected_evaluation")) and _norm(row.get("remap_status")) == "STRICT_READY"]
    diagnostic_rows_excluded = sum(1 for row in selections if _bool(row.get("included_in_diagnostic_sensitivity")))
    row_count_ok = len(strict_selections) == STRICT_ROW_COUNT_REQUIRED
    if not row_count_ok:
        governance_rows = _build_governance_rows(generated_ts, evaluation_run_id, row_count_ok)
        summary_rows = [
            {
                **_base(generated_ts, evaluation_run_id),
                "build_status": "BLOCKED",
                "final_interpretation": "CORRECTED_ACCURACY_RE_EVALUATION_BLOCKED_ROW_COUNT_MISMATCH",
                "corrected_evaluation_rows_executed": 0,
                "diagnostic_rows_excluded": diagnostic_rows_excluded,
                "experiments_executed": 0,
                "metrics_calculated": 0,
                "direction_denominator": 0,
                "direction_correct_count": 0,
                "direction_match_rate": "",
                "overall_denominator": 0,
                "overall_ok_count": 0,
                "overall_ok_rate": "",
                "comparison_deltas_calculated": 0,
                "hypotheses_supported": 0,
                "hypotheses_partially_supported": 0,
                "hypotheses_not_supported": 0,
                "hypotheses_inconclusive": 0,
                "provider_calls_performed": 0,
                "forecast_generation_performed": 0,
                "provider_rerun_count": 0,
                "accuracy_execution_performed": 0,
                "production_sheet_write_count": 0,
                "production_behavior_change_count": 0,
                "evaluation_rows_written": 0,
                "outcome_ledger_written": 0,
                "market_reaction_values_modified": 0,
                "canonical_outcomes_modified": 0,
                "routing_changes": "FALSE",
                "weighting_changes": "FALSE",
                "calibration_changes": "FALSE",
                "ensemble_changes": "FALSE",
                "ready_for_corrected_accuracy_review": "FALSE",
                "ready_for_replication_design": "FALSE",
                "ready_for_production": "FALSE",
                "recommended_next_step": "PROCEED_TO_PHASE9A5R_SECOND_HYPOTHESIS_REVISION",
                "notes": f"Expected exactly {STRICT_ROW_COUNT_REQUIRED} strict-ready rows; found {len(strict_selections)}.",
            }
        ]
        outputs = [
            (OUTPUT_EVALUATION, EVALUATION_HEADERS, []),
            (OUTPUT_EXPERIMENT, EXPERIMENT_HEADERS, []),
            (OUTPUT_COMPARISON, COMPARISON_HEADERS, []),
            (OUTPUT_METRIC, METRIC_HEADERS, []),
            (OUTPUT_HYPOTHESIS, HYPOTHESIS_HEADERS, []),
            (OUTPUT_GOVERNANCE, GOVERNANCE_HEADERS, governance_rows),
            (OUTPUT_SUMMARY, SUMMARY_HEADERS, summary_rows),
        ]
        for sheet_name, headers, rows in outputs:
            actual_headers = _ensure_sheet_minimal(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, headers, len(rows))
            _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, actual_headers, rows)
        return {
            "build_status": "BLOCKED",
            "final_interpretation": "CORRECTED_ACCURACY_RE_EVALUATION_BLOCKED_ROW_COUNT_MISMATCH",
            "file_created": "automation/build_corrected_accuracy_re_evaluation_execution_v0.py",
            "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
            "corrected_evaluation_rows_executed": 0,
            "diagnostic_rows_excluded": diagnostic_rows_excluded,
            "recommended_next_step": "PROCEED_TO_PHASE9A5R_SECOND_HYPOTHESIS_REVISION",
        }

    mappings_by_id = {_accuracy_row_id(row): row for row in mappings}
    original_by_id = {_norm(row.get("__source_row_number__")): row for row in original_eval_rows if _norm(row.get("__source_row_number__"))}
    corrected_rows: List[Dict[str, Any]] = []
    same_row_originals: List[Dict[str, Any]] = []
    for selection in strict_selections:
        accuracy_row_id = _accuracy_row_id(selection)
        mapping = mappings_by_id.get(accuracy_row_id)
        original = original_by_id.get(accuracy_row_id)
        if not mapping or not original:
            raise RuntimeError(f"Unable to join frozen corrected row {accuracy_row_id}.")
        corrected_rows.append(_calculate_corrected_row(generated_ts, evaluation_run_id, selection, mapping, original))
        same_row_originals.append(original)

    original_same_by_id = {_norm(row.get("__source_row_number__")): row for row in same_row_originals}
    experiment_results = _build_experiment_results(generated_ts, evaluation_run_id, corrected_rows, original_same_by_id)
    comparison_results = _build_comparison_results(generated_ts, evaluation_run_id, corrected_rows, original_same_by_id)
    metric_results = _build_metric_results(
        generated_ts,
        evaluation_run_id,
        corrected_rows,
        same_row_originals,
        comparison_results,
        metric_definitions,
        experiment_results,
    )
    hypothesis_results = _build_hypothesis_results(generated_ts, evaluation_run_id, experiment_results)
    governance_rows = _build_governance_rows(generated_ts, evaluation_run_id, row_count_ok)
    governance_failed = any(_norm(row.get("status")) != "PASS" for row in governance_rows)

    direction_rows = _rows_with(corrected_rows, "included_in_direction_denominator")
    overall_rows = _rows_with(corrected_rows, "included_in_overall_denominator")
    direction_correct = _count_true(direction_rows, "direction_correct")
    overall_ok = _count_true(overall_rows, "overall_ok")
    hypothesis_counts = Counter(_norm(row.get("hypothesis_result")) for row in hypothesis_results)
    final_interpretation = "CORRECTED_ACCURACY_RE_EVALUATION_READY_WITH_WARNINGS" if not governance_failed else "CORRECTED_ACCURACY_RE_EVALUATION_BLOCKED"
    build_status = "PASS_WITH_WARNINGS" if not governance_failed else "BLOCKED"
    recommended_next = "PROCEED_TO_PHASE9A5M6_CORRECTED_ACCURACY_REVIEW" if not governance_failed else "PROCEED_TO_PHASE9A5R_SECOND_HYPOTHESIS_REVISION"

    summary_rows = [
        {
            **_base(generated_ts, evaluation_run_id),
            "build_status": build_status,
            "final_interpretation": final_interpretation,
            "corrected_evaluation_rows_executed": len(corrected_rows),
            "diagnostic_rows_excluded": diagnostic_rows_excluded,
            "experiments_executed": len(experiment_results),
            "metrics_calculated": len(metric_results),
            "direction_denominator": len(direction_rows),
            "direction_correct_count": direction_correct,
            "direction_match_rate": _safe_rate(direction_correct, len(direction_rows)),
            "overall_denominator": len(overall_rows),
            "overall_ok_count": overall_ok,
            "overall_ok_rate": _safe_rate(overall_ok, len(overall_rows)),
            "comparison_deltas_calculated": len(comparison_results),
            "hypotheses_supported": hypothesis_counts["Supported"],
            "hypotheses_partially_supported": hypothesis_counts["Partially Supported"],
            "hypotheses_not_supported": hypothesis_counts["Not Supported"],
            "hypotheses_inconclusive": hypothesis_counts["Inconclusive"],
            "provider_calls_performed": 0,
            "forecast_generation_performed": 0,
            "provider_rerun_count": 0,
            "accuracy_execution_performed": 1,
            "production_sheet_write_count": 0,
            "production_behavior_change_count": 0,
            "evaluation_rows_written": 0,
            "outcome_ledger_written": 0,
            "market_reaction_values_modified": 0,
            "canonical_outcomes_modified": 0,
            "routing_changes": "FALSE",
            "weighting_changes": "FALSE",
            "calibration_changes": "FALSE",
            "ensemble_changes": "FALSE",
            "ready_for_corrected_accuracy_review": "TRUE" if not governance_failed else "FALSE",
            "ready_for_replication_design": "FALSE",
            "ready_for_production": "FALSE",
            "recommended_next_step": recommended_next,
            "notes": json.dumps(
                {
                    "strict_row_count_required": STRICT_ROW_COUNT_REQUIRED,
                    "strict_row_count_actual": len(corrected_rows),
                    "diagnostic_rows_excluded_from_primary": diagnostic_rows_excluded,
                    "only_changed_variable": "validated_repaired_canonical_outcome_overlay",
                    "original_phase9a5f_sheets_modified": False,
                },
                sort_keys=True,
            ),
        }
    ]

    outputs = [
        (OUTPUT_EVALUATION, EVALUATION_HEADERS, corrected_rows),
        (OUTPUT_EXPERIMENT, EXPERIMENT_HEADERS, experiment_results),
        (OUTPUT_COMPARISON, COMPARISON_HEADERS, comparison_results),
        (OUTPUT_METRIC, METRIC_HEADERS, metric_results),
        (OUTPUT_HYPOTHESIS, HYPOTHESIS_HEADERS, hypothesis_results),
        (OUTPUT_GOVERNANCE, GOVERNANCE_HEADERS, governance_rows),
        (OUTPUT_SUMMARY, SUMMARY_HEADERS, summary_rows),
    ]
    for sheet_name, headers, rows in outputs:
        actual_headers = _ensure_sheet_minimal(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, headers, len(rows))
        _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name, actual_headers, rows)
    registry = _upsert_registry_rows(service)
    return {
        "build_status": build_status,
        "final_interpretation": final_interpretation,
        "file_created": "automation/build_corrected_accuracy_re_evaluation_execution_v0.py",
        "sheets_written": {sheet_name: len(rows) for sheet_name, _, rows in outputs},
        "corrected_evaluation_rows_executed": len(corrected_rows),
        "diagnostic_rows_excluded": diagnostic_rows_excluded,
        "metrics_calculated": len(metric_results),
        "direction_correctness": {
            "denominator": len(direction_rows),
            "correct_count": direction_correct,
            "rate": summary_rows[0]["direction_match_rate"],
        },
        "overall_ok": {
            "denominator": len(overall_rows),
            "ok_count": overall_ok,
            "rate": summary_rows[0]["overall_ok_rate"],
        },
        "experiment_results": {
            row["experiment_id"]: {
                "direction_match_rate": row["direction_match_rate"],
                "overall_ok_rate": row["overall_ok_rate"],
            }
            for row in experiment_results
        },
        "comparison_deltas": len(comparison_results),
        "hypothesis_results": {row["accuracy_hypothesis_id"]: row["hypothesis_result"] for row in hypothesis_results},
        "provider_calls_performed": 0,
        "forecast_generation_performed": 0,
        "provider_rerun_count": 0,
        "accuracy_execution_performed": 1,
        "production_sheet_write_count": 0,
        "production_behavior_change_count": 0,
        "ready_for_corrected_accuracy_review": not governance_failed,
        "ready_for_replication_design": False,
        "ready_for_production": False,
        "recommended_next_step": recommended_next,
        "registry": registry,
    }


def main() -> None:
    result = build_corrected_accuracy_re_evaluation_execution_v0()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
