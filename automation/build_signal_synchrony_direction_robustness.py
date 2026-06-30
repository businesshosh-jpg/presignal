import os
import sys
from collections import Counter, defaultdict
from datetime import datetime
from math import floor, ceil
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_signal_synchrony_conditional_value_audit import (
    DIAGNOSTICS_SPREADSHEET_ID,
    _as_bool,
    _ensure_sheet,
    _round4,
    _sheet_to_rows,
    _write_rows,
)
from automation.build_signal_synchrony_conditional_value_stability import (
    PROJECT_OVERVIEWS_SPREADSHEET_ID,
    REGISTRY_HEADERS,
    REGISTRY_SHEET,
    _column_letter,
)
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


OUTPUT_AUDIT_SHEET = "Signal_Synchrony_Direction_Robustness"
OUTPUT_SUMMARY_SHEET = "Signal_Synchrony_Direction_Robustness_Summary"

REGISTRY_ROWS = [
    {
        "logical_sheet_id": "SIGNAL_SYNCHRONY_DIRECTION_ROBUSTNESS",
        "physical_sheet_name": OUTPUT_AUDIT_SHEET,
        "workbook": "DIAGNOSTICS",
        "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
        "category": "SIGNAL_SYNCHRONY",
        "lifecycle_state": "ACTIVE",
        "owner_module": "signal_synchrony",
        "participates_in_rebuild": "TRUE",
        "read_only": "FALSE",
        "allow_creation": "FALSE",
        "created_phase": "Signal Synchrony v1",
        "notes": "Derived-only direction synchrony robustness audit",
    },
    {
        "logical_sheet_id": "SIGNAL_SYNCHRONY_DIRECTION_ROBUSTNESS_SUMMARY",
        "physical_sheet_name": OUTPUT_SUMMARY_SHEET,
        "workbook": "DIAGNOSTICS",
        "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
        "category": "SIGNAL_SYNCHRONY",
        "lifecycle_state": "ACTIVE",
        "owner_module": "signal_synchrony",
        "participates_in_rebuild": "TRUE",
        "read_only": "FALSE",
        "allow_creation": "FALSE",
        "created_phase": "Signal Synchrony v1",
        "notes": "Derived-only direction synchrony robustness summary",
    },
]

AUDIT_HEADERS = [
    "generated_ts",
    "test_id",
    "test_name",
    "bucket_scheme",
    "control_dimension",
    "control_value",
    "provider",
    "event_family",
    "cohort_bucket",
    "sample_groups",
    "comparable_rows",
    "correct_count",
    "wrong_count",
    "non_comparable_rows",
    "thin_sample_flag",
    "confidence_label",
    "correct_rate",
    "baseline_rate",
    "delta_vs_baseline",
    "high_vs_low_spread",
    "global_baseline_rate",
    "provider_baseline_rate",
    "family_baseline_rate",
    "provider_family_baseline_rate",
    "cohort_baseline_rate",
    "direction_bucket",
    "min_forecast_direction_concentration",
    "max_forecast_direction_concentration",
    "avg_forecast_direction_concentration",
    "dominant_forecast_direction_mix",
    "monotonicity_label",
    "provider_control_result",
    "family_control_result",
    "provider_family_control_result",
    "cohort_control_result",
    "no_anthropic_result",
    "bucket_sensitivity_result",
    "interpretation_note",
    "missing_metric_flag",
    "source_note",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "section",
    "test_id",
    "test_name",
    "bucket_scheme",
    "control_dimension",
    "control_value",
    "provider",
    "event_family",
    "cohort_bucket",
    "sample_groups",
    "comparable_rows",
    "correct_count",
    "wrong_count",
    "correct_rate",
    "baseline_rate",
    "delta_vs_baseline",
    "high_vs_low_spread",
    "control_result_label",
    "confidence_label",
    "best_bucket",
    "best_bucket_rate",
    "weakest_bucket",
    "weakest_bucket_rate",
    "monotonicity_label",
    "sensitivity_label",
    "survival_label",
    "notes",
]

BUCKET_ORDER = ["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]
BUCKET_SCHEMES = {
    "existing_direction_synchrony_bucket": {
        "kind": "categorical",
        "field": "direction_synchrony_bucket",
        "order": BUCKET_ORDER + ["MISSING"],
    },
    "quantile_forecast_direction_concentration": {
        "kind": "quantile4",
        "field": "forecast_direction_concentration",
        "order": BUCKET_ORDER + ["MISSING"],
    },
    "binary_top_half": {
        "kind": "binary_half",
        "field": "forecast_direction_concentration",
        "order": ["BOTTOM_HALF", "TOP_HALF", "MISSING"],
    },
    "binary_top_quartile": {
        "kind": "top_quartile",
        "field": "forecast_direction_concentration",
        "order": ["REST", "TOP_QUARTILE", "MISSING"],
    },
}

TESTS = [
    ("raw_direction_synchrony_effect", "Raw Direction Synchrony Effect"),
    ("provider_controlled_direction_synchrony", "Provider-Controlled Direction Synchrony"),
    ("no_anthropic_direction_synchrony", "No-Anthropic Direction Synchrony"),
    ("family_controlled_direction_synchrony", "Family-Controlled Direction Synchrony"),
    ("provider_family_direction_synchrony", "Provider x Family Direction Synchrony"),
    ("cohort_controlled_direction_synchrony", "Cohort-Controlled Direction Synchrony"),
    ("thin_family_exclusion", "Thin-Family Exclusion"),
    ("bucket_sensitivity", "Bucket Sensitivity"),
]


def _norm(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return str(value).strip()


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _as_float(value: Any) -> Optional[float]:
    raw = _norm(value)
    if raw == "":
        return None
    try:
        return float(raw)
    except Exception:
        return None


def _safe_rate(numerator: int, denominator: int) -> Optional[float]:
    if denominator <= 0:
        return None
    return numerator / denominator


def _safe_mean(values: Iterable[Optional[float]]) -> Optional[float]:
    cleaned = [v for v in values if v is not None]
    if not cleaned:
        return None
    return mean(cleaned)


def _confidence_label(comparable_rows: int) -> str:
    if comparable_rows >= 20:
        return "HIGHER_CONFIDENCE"
    if comparable_rows >= 12:
        return "MEDIUM_CONFIDENCE"
    if comparable_rows >= 8:
        return "LOW_CONFIDENCE"
    return "THIN_SAMPLE"


def _compare_confidence_label(comparable_rows: int) -> str:
    return _confidence_label(comparable_rows)


def _is_comparable(row: Dict[str, Any]) -> bool:
    if _as_bool(row.get("actual_comparable")):
        return True
    return _upper(row.get("outcome_result_label")) in {"FORECAST_CORRECT", "FORECAST_INLINE_CORRECT", "FORECAST_WRONG"}


def _is_correct(row: Dict[str, Any]) -> bool:
    return _upper(row.get("outcome_result_label")) in {"FORECAST_CORRECT", "FORECAST_INLINE_CORRECT"} or _as_bool(row.get("forecast_matches_actual"))


def _quantile(sorted_values: Sequence[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = (len(sorted_values) - 1) * q
    lower = floor(pos)
    upper = ceil(pos)
    if lower == upper:
        return sorted_values[int(pos)]
    frac = pos - lower
    return sorted_values[lower] * (1 - frac) + sorted_values[upper] * frac


def _cohort_bucket(cohort_id: str) -> str:
    raw = _upper(cohort_id)
    if raw.startswith("COHORT_A") or "COHORT_A" in raw:
        return "cohort_a"
    if "RANDOM" in raw:
        return "random"
    if "DETERMINISTIC" in raw or raw.startswith("COHORT_B") or raw.startswith("COHORT_C"):
        return "deterministic"
    return "unknown"


def _bucketize(value: Optional[float], scheme: str, thresholds: Dict[str, Any]) -> str:
    if value is None:
        return "MISSING"
    if scheme == "existing_direction_synchrony_bucket":
        if value < 0.50:
            return "LOW"
        if value < 0.70:
            return "MEDIUM"
        if value < 0.90:
            return "HIGH"
        return "VERY_HIGH"
    if scheme == "quantile_forecast_direction_concentration":
        q1, q2, q3 = thresholds["q1"], thresholds["q2"], thresholds["q3"]
        if value < q1:
            return "LOW"
        if value < q2:
            return "MEDIUM"
        if value < q3:
            return "HIGH"
        return "VERY_HIGH"
    if scheme == "binary_top_half":
        return "TOP_HALF" if value >= thresholds["median"] else "BOTTOM_HALF"
    if scheme == "binary_top_quartile":
        return "TOP_QUARTILE" if value >= thresholds["q3"] else "REST"
    return "MISSING"


def _read_inputs(service) -> Dict[str, List[Dict[str, Any]]]:
    names = {
        "accuracy_audit": "Signal_Synchrony_Accuracy_Audit",
        "accuracy_summary": "Signal_Synchrony_Accuracy_Summary",
        "microcohort": "Provider_Character_Direct_Expression_Microcohort",
        "outcome_check": "Provider_Character_Direct_Expression_Outcome_Check",
        "cohort_characterization": "Signal_Synchrony_Cohort_Characterization",
        "provider_slice": "Signal_Synchrony_Provider_Slice_Performance",
        "family_slice": "Signal_Synchrony_Family_Slice_Performance",
        "provider_dep": "Signal_Synchrony_Provider_Dep_Falsification",
        "provider_dep_summary": "Signal_Synchrony_Provider_Dep_Falsification_Summary",
    }
    return {key: _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet) for key, sheet in names.items()}


def _build_records(sources: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    micro_lookup = {_norm(r.get("sample_group_id")): r for r in sources["microcohort"]}
    outcome_lookup = {_norm(r.get("sample_group_id")): r for r in sources["outcome_check"]}
    cohort_lookup = {_norm(r.get("sample_group_id")): r for r in sources["cohort_characterization"]}

    records: List[Dict[str, Any]] = []
    for row in sources["accuracy_audit"]:
        sample_group_id = _norm(row.get("sample_group_id"))
        if not sample_group_id:
            continue
        micro = micro_lookup.get(sample_group_id, {})
        outcome = outcome_lookup.get(sample_group_id, {})
        cohort = cohort_lookup.get(sample_group_id, {})
        direction = _as_float(row.get("forecast_direction_concentration"))
        pattern = _as_float(row.get("pattern_concentration_score"))
        expr = _as_float(row.get("expression_similarity_mean"))
        overall_vals = [v for v in [direction, pattern, expr] if v is not None]
        overall = _safe_mean(overall_vals) if len(overall_vals) >= 2 else None
        records.append({
            "sample_group_id": sample_group_id,
            "event_id": _norm(row.get("event_id")),
            "provider": _norm(row.get("provider")),
            "cohort_id": _norm(row.get("cohort_id")) or _norm(cohort.get("cohort_id")),
            "cohort_bucket": _cohort_bucket(_norm(row.get("cohort_id")) or _norm(cohort.get("cohort_id"))),
            "event_family": _norm(row.get("event_family")) or "unknown",
            "indicator_name": _norm(row.get("indicator_name")),
            "country": _norm(row.get("country")),
            "release_ts": _norm(row.get("release_ts")),
            "importance": _norm(row.get("importance")) or "unknown",
            "predictability_bucket": _norm(row.get("predictability_bucket")) or _norm(cohort.get("predictability_bucket")) or "unknown",
            "actual_available": _norm(row.get("actual_available")) or _norm(outcome.get("actual_available")),
            "actual_comparable": "TRUE" if _is_comparable(row) else "FALSE",
            "forecast_matches_actual": _norm(row.get("forecast_matches_actual")) or _norm(outcome.get("forecast_matches_actual")),
            "outcome_result_label": _norm(row.get("outcome_result_label")) or _norm(outcome.get("outcome_result_label")),
            "outcome_check_status": _norm(row.get("outcome_check_status")) or _norm(outcome.get("outcome_check_status")),
            "forecast_direction_concentration": direction,
            "pattern_concentration_score": pattern,
            "expression_similarity_mean": expr,
            "overall_synchrony": overall,
            "reproducibility_outcome_label": _norm(row.get("reproducibility_outcome_label")) or _norm(outcome.get("reproducibility_outcome_label")),
            "stability_label": _norm(row.get("stability_label")) or _norm(cohort.get("stability_label")),
            "recommended_protocol": _norm(row.get("recommended_protocol")) or _norm(cohort.get("recommended_protocol")),
            "rerun_success_count": _norm(row.get("rerun_success_count")) or _norm(cohort.get("rerun_success_count")),
            "rerun_failure_count": _norm(row.get("rerun_failure_count")) or _norm(cohort.get("rerun_failure_count")),
            "dominant_forecast_direction": _norm(row.get("dominant_forecast_direction")) or _norm(micro.get("dominant_forecast_direction")),
            "dominant_pattern_label": _norm(row.get("dominant_pattern_label")) or _norm(micro.get("dominant_causal_family_if_classifiable")),
            "missing_metric_flag": "" if direction is not None else "forecast_direction_concentration",
            "thin_sample_flag": "FALSE",
            "confidence_label": _confidence_label(1 if _is_comparable(row) else 0),
            "notes": _norm(row.get("notes")) or _norm(cohort.get("notes")) or _norm(micro.get("notes")),
        })

    by_provider_family: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for rec in records:
        if rec["actual_comparable"] == "TRUE":
            by_provider_family[(rec["provider"], rec["event_family"])].append(rec)
    for rec in records:
        if rec["actual_comparable"] != "TRUE":
            continue
        count = len(by_provider_family[(rec["provider"], rec["event_family"])])
        rec["thin_sample_flag"] = "TRUE" if count < 8 else "FALSE"
        rec["confidence_label"] = _confidence_label(count)
    return records


def _build_slice_rows(
    generated_ts: str,
    test_id: str,
    test_name: str,
    bucket_scheme: str,
    control_dimension: str,
    control_value: str,
    rows: Sequence[Dict[str, Any]],
    *,
    allow_bucket_rows: Optional[Sequence[str]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    comparable_rows = [r for r in rows if r["actual_comparable"] == "TRUE"]
    if allow_bucket_rows is not None:
        comparable_rows = [r for r in comparable_rows if _bucketize(r["forecast_direction_concentration"], bucket_scheme, _bucket_thresholds(rows, bucket_scheme)) in allow_bucket_rows]
    thresholds = _bucket_thresholds(rows, bucket_scheme)
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for rec in rows:
        bucket = _bucketize(rec["forecast_direction_concentration"], bucket_scheme, thresholds)
        grouped[bucket].append(rec)

    global_baseline = _safe_rate(sum(1 for r in comparable_rows if _is_correct(r)), len(comparable_rows))
    bucket_rates: Dict[str, Dict[str, Any]] = {}
    for bucket in sorted(grouped.keys(), key=lambda b: BUCKET_ORDER.index(b) if b in BUCKET_ORDER else 99):
        bucket_rows = grouped[bucket]
        comp = [r for r in bucket_rows if r["actual_comparable"] == "TRUE"]
        correct_count = sum(1 for r in comp if _is_correct(r))
        wrong_count = sum(1 for r in comp if not _is_correct(r))
        rate = _safe_rate(correct_count, len(comp))
        bucket_rates[bucket] = {
            "sample_groups": len(bucket_rows),
            "comparable_rows": len(comp),
            "correct_count": correct_count,
            "wrong_count": wrong_count,
            "non_comparable_rows": len(bucket_rows) - len(comp),
            "correct_rate": rate,
            "baseline_rate": global_baseline,
            "delta_vs_baseline": (rate - global_baseline) if rate is not None and global_baseline is not None else None,
            "min": min((r["forecast_direction_concentration"] for r in bucket_rows if r["forecast_direction_concentration"] is not None), default=None),
            "max": max((r["forecast_direction_concentration"] for r in bucket_rows if r["forecast_direction_concentration"] is not None), default=None),
            "avg": _safe_mean([r["forecast_direction_concentration"] for r in bucket_rows if r["forecast_direction_concentration"] is not None]),
            "mix": _mix_string(bucket_rows),
            "confidence": _confidence_label(len(comp)),
        }

    ordered_buckets = [b for b in BUCKET_ORDER if b in bucket_rates] if bucket_scheme in {"existing_direction_synchrony_bucket", "quantile_forecast_direction_concentration"} else [b for b in bucket_rates if b != "MISSING"]
    if bucket_scheme in {"binary_top_half", "binary_top_quartile"}:
        ordered_buckets = ["BOTTOM_HALF", "TOP_HALF"] if bucket_scheme == "binary_top_half" else ["REST", "TOP_QUARTILE"]
    if "MISSING" in bucket_rates and "MISSING" not in ordered_buckets:
        ordered_buckets.append("MISSING")
    valid_for_spread = [bucket_rates[b] for b in ordered_buckets if bucket_rates.get(b) and bucket_rates[b]["correct_rate"] is not None and b != "MISSING"]
    best_rate = max((r["correct_rate"] for r in valid_for_spread), default=None)
    worst_rate = min((r["correct_rate"] for r in valid_for_spread), default=None)
    spread = (best_rate - worst_rate) if best_rate is not None and worst_rate is not None else None
    monotonicity = _monotonicity_from_order([bucket_rates.get(b, {}).get("correct_rate") for b in ordered_buckets if b != "MISSING"])
    control_result = _control_result_from_spread(spread, global_baseline, valid_for_spread)
    rows_out: List[Dict[str, Any]] = []
    for bucket, stats in bucket_rates.items():
        rows_out.append({
            "generated_ts": generated_ts,
            "test_id": test_id,
            "test_name": test_name,
            "bucket_scheme": bucket_scheme,
            "control_dimension": control_dimension,
            "control_value": control_value,
            "provider": _norm(control_value) if control_dimension in {"provider", "no_anthropic"} else "",
            "event_family": _norm(control_value) if control_dimension == "family" else "",
            "cohort_bucket": _norm(control_value) if control_dimension == "cohort" else "",
            "sample_groups": stats["sample_groups"],
            "comparable_rows": stats["comparable_rows"],
            "correct_count": stats["correct_count"],
            "wrong_count": stats["wrong_count"],
            "non_comparable_rows": stats["non_comparable_rows"],
            "thin_sample_flag": "TRUE" if stats["comparable_rows"] < 8 else "FALSE",
            "confidence_label": stats["confidence"],
            "correct_rate": _round4(stats["correct_rate"]),
            "baseline_rate": _round4(stats["baseline_rate"]),
            "delta_vs_baseline": _round4(stats["delta_vs_baseline"]),
            "high_vs_low_spread": _round4(spread),
            "global_baseline_rate": _round4(global_baseline),
            "provider_baseline_rate": "",
            "family_baseline_rate": "",
            "provider_family_baseline_rate": "",
            "cohort_baseline_rate": "",
            "direction_bucket": bucket,
            "min_forecast_direction_concentration": _round4(stats["min"]),
            "max_forecast_direction_concentration": _round4(stats["max"]),
            "avg_forecast_direction_concentration": _round4(stats["avg"]),
            "dominant_forecast_direction_mix": stats["mix"],
            "monotonicity_label": monotonicity,
            "provider_control_result": control_result if control_dimension == "provider" else "",
            "family_control_result": control_result if control_dimension == "family" else "",
            "provider_family_control_result": control_result if control_dimension == "provider_family" else "",
            "cohort_control_result": control_result if control_dimension == "cohort" else "",
            "no_anthropic_result": control_result if control_dimension == "no_anthropic" else "",
            "bucket_sensitivity_result": control_result if control_dimension == "bucket_sensitivity" else "",
            "interpretation_note": "",
            "missing_metric_flag": "",
            "source_note": f"{bucket_scheme}; control={control_dimension}:{control_value}",
        })

    meta = {
        "bucket_rates": bucket_rates,
        "baseline_rate": global_baseline,
        "best_bucket": max(valid_for_spread, key=lambda r: r["correct_rate"], default={}).get("bucket") if valid_for_spread else "",
        "best_bucket_rate": best_rate,
        "worst_bucket": min(valid_for_spread, key=lambda r: r["correct_rate"], default={}).get("bucket") if valid_for_spread else "",
        "worst_bucket_rate": worst_rate,
        "spread": spread,
        "monotonicity_label": monotonicity,
        "control_result_label": control_result,
        "confidence_label": _confidence_label(len(comparable_rows)),
    }
    return rows_out, meta


def _bucket_thresholds(rows: Sequence[Dict[str, Any]], bucket_scheme: str) -> Dict[str, Any]:
    if bucket_scheme == "existing_direction_synchrony_bucket":
        return {}
    values = sorted([r["forecast_direction_concentration"] for r in rows if r["forecast_direction_concentration"] is not None])
    if not values:
        return {"q1": 0.0, "q2": 0.0, "q3": 0.0, "median": 0.0}
    return {
        "q1": _quantile(values, 0.25),
        "q2": _quantile(values, 0.50),
        "q3": _quantile(values, 0.75),
        "median": _quantile(values, 0.50),
    }


def _mix_string(rows: Sequence[Dict[str, Any]]) -> str:
    counter = Counter(_norm(r.get("dominant_forecast_direction")) or "unknown" for r in rows)
    return "|".join(f"{k}:{v}" for k, v in counter.most_common())


def _monotonicity_from_order(rates: Sequence[Optional[float]]) -> str:
    cleaned = [r for r in rates if r is not None]
    if len(cleaned) < 2:
        return "INSUFFICIENT_DATA"
    if all(cleaned[i] <= cleaned[i + 1] for i in range(len(cleaned) - 1)):
        return "MONOTONIC_POSITIVE"
    if cleaned[-1] > cleaned[0]:
        return "PARTIAL_POSITIVE"
    if all(cleaned[i] >= cleaned[i + 1] for i in range(len(cleaned) - 1)):
        return "NEGATIVE_OR_INVERSE"
    return "NO_MONOTONIC_PATTERN"


def _control_result_from_spread(spread: Optional[float], baseline: Optional[float], bucket_stats: Sequence[Dict[str, Any]]) -> str:
    if not bucket_stats or spread is None or baseline is None:
        return "INSUFFICIENT_DATA"
    if all(stats["comparable_rows"] < 5 for stats in bucket_stats):
        return "INSUFFICIENT_DATA"
    if spread <= 0:
        return "COLLAPSES"
    if spread >= 0.10:
        return "SURVIVES"
    return "WEAKENS"


def _sensitivity_label(scheme_results: Dict[str, Dict[str, Any]]) -> str:
    if not scheme_results:
        return "INSUFFICIENT_DATA"
    non_missing = [r for r in scheme_results.values() if r["spread"] is not None]
    if not non_missing:
        return "INSUFFICIENT_DATA"
    positive = [r for r in non_missing if r["spread"] > 0]
    if len(positive) == len(non_missing) and all(r["monotonicity_label"] in {"MONOTONIC_POSITIVE", "PARTIAL_POSITIVE"} for r in non_missing):
        return "STABLE_ACROSS_BUCKETS"
    if positive and len(positive) >= max(1, len(non_missing) - 1):
        return "PARTIAL_BUCKET_DEPENDENCE"
    if len(positive) <= 1:
        return "BUCKET_ARTIFACT_RISK"
    return "PARTIAL_BUCKET_DEPENDENCE"


def _bucket_sensitivity_meta(audit_rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    scheme_rows = [r for r in audit_rows if r["test_id"] == "bucket_sensitivity"]
    scheme_results: Dict[str, Dict[str, Any]] = {}
    for scheme_name in BUCKET_SCHEMES:
        rows = [r for r in scheme_rows if r["bucket_scheme"] == scheme_name]
        if not rows:
            continue
        buckets = [r for r in rows if r["direction_bucket"] != "MISSING"]
        best = max(buckets, key=lambda r: _as_float(r.get("correct_rate")) or -1.0, default=None)
        worst = min(buckets, key=lambda r: _as_float(r.get("correct_rate")) or 999.0, default=None)
        spread = (_as_float(best.get("correct_rate")) - _as_float(worst.get("correct_rate"))) if best and worst and _as_float(best.get("correct_rate")) is not None and _as_float(worst.get("correct_rate")) is not None else None
        scheme_results[scheme_name] = {
            "comparable_rows": sum(r["comparable_rows"] for r in rows),
            "spread": spread,
            "monotonicity_label": _monotonicity_from_order([r["correct_rate"] for r in buckets]),
            "control_result_label": rows[0].get("bucket_sensitivity_result", ""),
            "best_bucket": _norm(best.get("direction_bucket")) if best else "",
            "best_bucket_rate": _as_float(best.get("correct_rate")) if best else None,
            "worst_bucket": _norm(worst.get("direction_bucket")) if worst else "",
            "worst_bucket_rate": _as_float(worst.get("correct_rate")) if worst else None,
        }
    return {
        "scheme_results": scheme_results,
        "sensitivity_label": _sensitivity_label(scheme_results),
    }


def _build_audit_rows(records: Sequence[Dict[str, Any]], generated_ts: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    audit_rows: List[Dict[str, Any]] = []
    control_summaries: Dict[str, Dict[str, Any]] = {}

    global_rows = [r for r in records if r["actual_comparable"] == "TRUE"]
    global_baseline = _safe_rate(sum(1 for r in global_rows if _is_correct(r)), len(global_rows))

    def add_rows(test_id: str, test_name: str, bucket_scheme: str, control_dimension: str, control_value: str, rows: Sequence[Dict[str, Any]], extra_note: str = ""):
        rows_out, meta = _build_slice_rows(generated_ts, test_id, test_name, bucket_scheme, control_dimension, control_value, rows)
        for row in rows_out:
            row["interpretation_note"] = extra_note
        audit_rows.extend(rows_out)
        control_summaries.setdefault(test_id, meta)
        control_summaries[test_id].update({"control_dimension": control_dimension, "control_value": control_value, "test_name": test_name, "bucket_scheme": bucket_scheme})

    # Test 1
    add_rows("raw_direction_synchrony_effect", "Raw Direction Synchrony Effect", "existing_direction_synchrony_bucket", "global", "all", records)

    # Test 2
    for provider in ["Anthropic", "Gemini", "OpenAI"]:
        add_rows("provider_controlled_direction_synchrony", "Provider-Controlled Direction Synchrony", "existing_direction_synchrony_bucket", "provider", provider, [r for r in records if r["provider"] == provider])

    # Test 3
    no_anthropic = [r for r in records if r["provider"] != "Anthropic"]
    add_rows("no_anthropic_direction_synchrony", "No-Anthropic Direction Synchrony", "existing_direction_synchrony_bucket", "no_anthropic", "Gemini|OpenAI", no_anthropic)

    # Test 4
    families = ["growth", "inflation", "housing", "labor", "energy", "central_bank", "manufacturing", "other"]
    for family in families:
        add_rows("family_controlled_direction_synchrony", "Family-Controlled Direction Synchrony", "existing_direction_synchrony_bucket", "family", family, [r for r in records if r["event_family"] == family])

    # Test 5
    for provider in ["Anthropic", "Gemini", "OpenAI"]:
        for family in families:
            slice_rows = [r for r in records if r["provider"] == provider and r["event_family"] == family]
            if not slice_rows:
                continue
            add_rows("provider_family_direction_synchrony", "Provider x Family Direction Synchrony", "existing_direction_synchrony_bucket", "provider_family", f"{provider}|{family}", slice_rows)

    # Test 6
    for cohort_bucket in ["cohort_a", "deterministic", "random"]:
        add_rows("cohort_controlled_direction_synchrony", "Cohort-Controlled Direction Synchrony", "existing_direction_synchrony_bucket", "cohort", cohort_bucket, [r for r in records if r["cohort_bucket"] == cohort_bucket])

    # Test 7
    family_counts = Counter(r["event_family"] for r in global_rows)
    retained_families = {fam for fam, cnt in family_counts.items() if cnt >= 8}
    thin_excluded = [r for r in records if r["event_family"] in retained_families]
    add_rows("thin_family_exclusion", "Thin-Family Exclusion", "existing_direction_synchrony_bucket", "family_filter", "families_ge_8", thin_excluded, "Excluded families with comparable_rows < 8.")

    # Test 8
    for scheme_name in BUCKET_SCHEMES:
        add_rows("bucket_sensitivity", "Bucket Sensitivity", scheme_name, "scheme", scheme_name, records)

    # compute extra meta for control summaries
    control_summaries["raw_direction_synchrony_effect"]["raw_result_label"] = "WEAK_SYNCHRONY_SIGNAL"
    control_summaries["raw_direction_synchrony_effect"]["global_baseline_rate"] = global_baseline
    bucket_meta = _bucket_sensitivity_meta(audit_rows)
    control_summaries["bucket_sensitivity"] = bucket_meta

    return audit_rows, {
        "global_baseline": global_baseline,
        "global_baseline_rate": global_baseline,
        "control_summaries": control_summaries,
        "retained_families": sorted(retained_families),
        "excluded_families": sorted(set(family_counts) - retained_families),
        "bucket_sensitivity": bucket_meta,
    }


def _overall_result_label(control_summaries: Dict[str, Dict[str, Any]]) -> str:
    raw = control_summaries.get("raw_direction_synchrony_effect", {})
    bucket_label = control_summaries.get("bucket_sensitivity", {}).get("sensitivity_label", "INSUFFICIENT_DATA")
    no_anthropic = control_summaries.get("no_anthropic_direction_synchrony", {}).get("control_result_label", "INSUFFICIENT_DATA")
    provider_any = control_summaries.get("provider_controlled_direction_synchrony", {}).get("control_result_label", "") == "SURVIVES"
    family_any = control_summaries.get("family_controlled_direction_synchrony", {}).get("control_result_label", "") == "SURVIVES"
    cohort_any = control_summaries.get("cohort_controlled_direction_synchrony", {}).get("control_result_label", "") == "SURVIVES"
    if bucket_label == "BUCKET_ARTIFACT_RISK":
        return "DIRECTION_SYNCHRONY_BUCKET_ARTIFACT"
    if no_anthropic == "COLLAPSES":
        return "DIRECTION_SYNCHRONY_PROVIDER_CONFOUNDED"
    if family_any is False and raw.get("control_result_label") == "COLLAPSES":
        return "DIRECTION_SYNCHRONY_FAMILY_CONFOUNDED"
    if not cohort_any and raw.get("control_result_label") == "COLLAPSES":
        return "DIRECTION_SYNCHRONY_COHORT_DEPENDENT"
    if raw.get("control_result_label") == "SURVIVES" and bucket_label in {"STABLE_ACROSS_BUCKETS", "PARTIAL_BUCKET_DEPENDENCE"}:
        return "DIRECTION_SYNCHRONY_ROBUST"
    if raw.get("control_result_label") in {"SURVIVES", "WEAKENS"} and bucket_label != "BUCKET_ARTIFACT_RISK":
        return "DIRECTION_SYNCHRONY_WEAK_BUT_REAL"
    return "NO_ROBUST_DIRECTION_SYNCHRONY_SIGNAL"


def _summary_rows(
    generated_ts: str,
    audit_rows: Sequence[Dict[str, Any]],
    meta: Dict[str, Any],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    global_baseline = meta["global_baseline_rate"]
    raw_rows = [r for r in audit_rows if r["test_id"] == "raw_direction_synchrony_effect"]
    raw_buckets = [r for r in raw_rows if r["direction_bucket"] in {"LOW", "MEDIUM", "HIGH", "VERY_HIGH"}]
    raw_best = max(raw_buckets, key=lambda r: _as_float(r.get("correct_rate")) or -1.0, default=None)
    raw_worst = min(raw_buckets, key=lambda r: _as_float(r.get("correct_rate")) or 999.0, default=None)
    raw_spread = (_as_float(raw_best.get("correct_rate")) - _as_float(raw_worst.get("correct_rate"))) if raw_best and raw_worst and _as_float(raw_best.get("correct_rate")) is not None and _as_float(raw_worst.get("correct_rate")) is not None else None

    rows.append({
        "generated_ts": generated_ts,
        "section": "A_OVERALL_RESULT",
        "test_id": "raw_direction_synchrony_effect",
        "test_name": "Raw Direction Synchrony Effect",
        "bucket_scheme": "existing_direction_synchrony_bucket",
        "control_dimension": "global",
        "control_value": "all",
        "provider": "",
        "event_family": "",
        "cohort_bucket": "",
        "sample_groups": len(raw_rows),
        "comparable_rows": sum(1 for r in raw_rows if r["comparable_rows"] > 0),
        "correct_count": sum(r["correct_count"] for r in raw_rows if r["direction_bucket"] in {"LOW", "MEDIUM", "HIGH", "VERY_HIGH"}),
        "wrong_count": sum(r["wrong_count"] for r in raw_rows if r["direction_bucket"] in {"LOW", "MEDIUM", "HIGH", "VERY_HIGH"}),
        "correct_rate": _round4(global_baseline),
        "baseline_rate": _round4(global_baseline),
        "delta_vs_baseline": "",
        "high_vs_low_spread": _round4(raw_spread),
        "control_result_label": meta["control_summaries"]["raw_direction_synchrony_effect"]["control_result_label"],
        "confidence_label": meta["control_summaries"]["raw_direction_synchrony_effect"]["confidence_label"],
        "best_bucket": _norm(raw_best.get("direction_bucket")) if raw_best else "",
        "best_bucket_rate": _round4(_as_float(raw_best.get("correct_rate")) if raw_best else None),
        "weakest_bucket": _norm(raw_worst.get("direction_bucket")) if raw_worst else "",
        "weakest_bucket_rate": _round4(_as_float(raw_worst.get("correct_rate")) if raw_worst else None),
        "monotonicity_label": meta["control_summaries"]["raw_direction_synchrony_effect"]["monotonicity_label"],
        "sensitivity_label": meta.get("bucket_sensitivity", {}).get("sensitivity_label", "INSUFFICIENT_DATA"),
        "survival_label": meta["control_summaries"]["raw_direction_synchrony_effect"]["control_result_label"],
        "notes": "Historical synchrony/accuracy association only.",
    })

    for test_id, test_name in TESTS:
        test_rows = [r for r in audit_rows if r["test_id"] == test_id]
        if not test_rows:
            continue
        if test_id == "bucket_sensitivity":
            for scheme_name in BUCKET_SCHEMES:
                scheme_rows = [r for r in test_rows if r["bucket_scheme"] == scheme_name]
                if not scheme_rows:
                    continue
                buckets = [r for r in scheme_rows if r["direction_bucket"] != "MISSING"]
                best = max(buckets, key=lambda r: _as_float(r.get("correct_rate")) or -1.0, default=None)
                worst = min(buckets, key=lambda r: _as_float(r.get("correct_rate")) or 999.0, default=None)
                spread = (_as_float(best.get("correct_rate")) - _as_float(worst.get("correct_rate"))) if best and worst and _as_float(best.get("correct_rate")) is not None and _as_float(worst.get("correct_rate")) is not None else None
                rows.append({
                    "generated_ts": generated_ts,
                    "section": "B_STRESS_TEST_SUMMARY",
                    "test_id": test_id,
                    "test_name": test_name,
                    "bucket_scheme": scheme_name,
                    "control_dimension": "scheme",
                    "control_value": scheme_name,
                    "provider": "",
                    "event_family": "",
                    "cohort_bucket": "",
                    "sample_groups": sum(r["sample_groups"] for r in scheme_rows),
                    "comparable_rows": sum(r["comparable_rows"] for r in scheme_rows),
                    "correct_count": sum(r["correct_count"] for r in scheme_rows),
                    "wrong_count": sum(r["wrong_count"] for r in scheme_rows),
                    "correct_rate": _round4(_safe_rate(sum(r["correct_count"] for r in scheme_rows), sum(r["comparable_rows"] for r in scheme_rows))),
                    "baseline_rate": _round4(_baseline_rate([r for r in meta["control_summaries"]["raw_direction_synchrony_effect"].get("bucket_rates", {}).values()])),
                    "delta_vs_baseline": "",
                    "high_vs_low_spread": _round4(spread),
                    "control_result_label": meta.get("bucket_sensitivity", {}).get("sensitivity_label", "INSUFFICIENT_DATA"),
                    "confidence_label": _compare_confidence_label(sum(r["comparable_rows"] for r in scheme_rows)),
                    "best_bucket": _norm(best.get("direction_bucket")) if best else "",
                    "best_bucket_rate": _round4(_as_float(best.get("correct_rate")) if best else None),
                    "weakest_bucket": _norm(worst.get("direction_bucket")) if worst else "",
                    "weakest_bucket_rate": _round4(_as_float(worst.get("correct_rate")) if worst else None),
                    "monotonicity_label": meta.get("bucket_sensitivity", {}).get("monotonicity_label", "INSUFFICIENT_DATA"),
                    "sensitivity_label": meta.get("bucket_sensitivity", {}).get("sensitivity_label", "INSUFFICIENT_DATA"),
                    "survival_label": meta.get("bucket_sensitivity", {}).get("sensitivity_label", "INSUFFICIENT_DATA"),
                    "notes": "",
                })
            continue

        # generic summary rows per control slice
        control_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for r in test_rows:
            key = r["control_value"] or r["provider"] or r["event_family"] or r["cohort_bucket"] or "all"
            control_groups[key].append(r)
        for control_value, group_rows in sorted(control_groups.items()):
            buckets = [r for r in group_rows if r["direction_bucket"] != "MISSING"]
            best = max(buckets, key=lambda r: _as_float(r.get("correct_rate")) or -1.0, default=None)
            worst = min(buckets, key=lambda r: _as_float(r.get("correct_rate")) or 999.0, default=None)
            spread = (_as_float(best.get("correct_rate")) - _as_float(worst.get("correct_rate"))) if best and worst and _as_float(best.get("correct_rate")) is not None and _as_float(worst.get("correct_rate")) is not None else None
            baseline = _safe_rate(sum(r["correct_count"] for r in group_rows if r["comparable_rows"] > 0), sum(r["comparable_rows"] for r in group_rows))
            rows.append({
                "generated_ts": generated_ts,
                "section": "B_STRESS_TEST_SUMMARY",
                "test_id": test_id,
                "test_name": test_name,
                "bucket_scheme": group_rows[0]["bucket_scheme"],
                "control_dimension": group_rows[0]["control_dimension"],
                "control_value": control_value,
                "provider": group_rows[0]["provider"],
                "event_family": group_rows[0]["event_family"],
                "cohort_bucket": group_rows[0]["cohort_bucket"],
                "sample_groups": sum(r["sample_groups"] for r in group_rows),
                "comparable_rows": sum(r["comparable_rows"] for r in group_rows),
                "correct_count": sum(r["correct_count"] for r in group_rows),
                "wrong_count": sum(r["wrong_count"] for r in group_rows),
                "correct_rate": _round4(_safe_rate(sum(r["correct_count"] for r in group_rows), sum(r["comparable_rows"] for r in group_rows))),
                "baseline_rate": _round4(baseline),
                "delta_vs_baseline": _round4((_safe_rate(sum(r["correct_count"] for r in group_rows), sum(r["comparable_rows"] for r in group_rows)) or 0) - (baseline or 0)) if baseline is not None else "",
                "high_vs_low_spread": _round4(spread),
                "control_result_label": group_rows[0].get("provider_control_result") or group_rows[0].get("family_control_result") or group_rows[0].get("provider_family_control_result") or group_rows[0].get("cohort_control_result") or group_rows[0].get("no_anthropic_result") or group_rows[0].get("bucket_sensitivity_result") or "",
                "confidence_label": _compare_confidence_label(sum(r["comparable_rows"] for r in group_rows)),
                "best_bucket": _norm(best.get("direction_bucket")) if best else "",
                "best_bucket_rate": _round4(_as_float(best.get("correct_rate")) if best else None),
                "weakest_bucket": _norm(worst.get("direction_bucket")) if worst else "",
                "weakest_bucket_rate": _round4(_as_float(worst.get("correct_rate")) if worst else None),
                "monotonicity_label": group_rows[0]["monotonicity_label"],
                "sensitivity_label": meta.get("bucket_sensitivity", {}).get("sensitivity_label", "INSUFFICIENT_DATA") if test_id == "bucket_sensitivity" else "",
                "survival_label": group_rows[0].get("provider_control_result") or group_rows[0].get("family_control_result") or group_rows[0].get("provider_family_control_result") or group_rows[0].get("cohort_control_result") or group_rows[0].get("no_anthropic_result") or group_rows[0].get("bucket_sensitivity_result") or "",
                "notes": "",
            })

    provider_family_rows = [r for r in audit_rows if r["test_id"] == "provider_family_direction_synchrony"]
    if provider_family_rows:
        slices = defaultdict(list)
        for r in provider_family_rows:
            slices[r["control_value"]].append(r)
        positive = 0
        negative = 0
        insufficient = 0
        strongest = None
        weakest = None
        for key, group_rows in slices.items():
            buckets = [r for r in group_rows if r["direction_bucket"] != "MISSING"]
            if len([r for r in group_rows if r["comparable_rows"] >= 8]) == 0:
                insufficient += 1
                continue
            best = max(buckets, key=lambda r: _as_float(r.get("correct_rate")) or -1.0, default=None)
            worst = min(buckets, key=lambda r: _as_float(r.get("correct_rate")) or 999.0, default=None)
            if best and worst and _as_float(best.get("correct_rate")) is not None and _as_float(worst.get("correct_rate")) is not None:
                if _as_float(best.get("correct_rate")) > _as_float(worst.get("correct_rate")):
                    positive += 1
                else:
                    negative += 1
            if strongest is None or (_as_float(best.get("correct_rate")) or -1) > (_as_float(strongest.get("best_bucket_rate")) or -1):
                strongest = {"control_value": key, "best_bucket_rate": _as_float(best.get("correct_rate")) if best else None, "spread": (_as_float(best.get("correct_rate")) - _as_float(worst.get("correct_rate"))) if best and worst and _as_float(best.get("correct_rate")) is not None and _as_float(worst.get("correct_rate")) is not None else None}
            if weakest is None or (_as_float(worst.get("correct_rate")) or 999) < (_as_float(weakest.get("worst_bucket_rate")) or 999):
                weakest = {"control_value": key, "worst_bucket_rate": _as_float(worst.get("correct_rate")) if worst else None, "spread": (_as_float(best.get("correct_rate")) - _as_float(worst.get("correct_rate"))) if best and worst and _as_float(best.get("correct_rate")) is not None and _as_float(worst.get("correct_rate")) is not None else None}
        rows.append({
            "generated_ts": generated_ts,
            "section": "F_PROVIDER_FAMILY_RESULT",
            "test_id": "provider_family_direction_synchrony",
            "test_name": "Provider x Family Direction Synchrony",
            "bucket_scheme": "existing_direction_synchrony_bucket",
            "control_dimension": "provider_family",
            "control_value": "",
            "provider": "",
            "event_family": "",
            "cohort_bucket": "",
            "sample_groups": len(provider_family_rows),
            "comparable_rows": sum(1 for r in provider_family_rows if r["comparable_rows"] > 0),
            "correct_count": "",
            "wrong_count": "",
            "correct_rate": "",
            "baseline_rate": _round4(_safe_rate(sum(r["correct_count"] for r in provider_family_rows), sum(r["comparable_rows"] for r in provider_family_rows))),
            "delta_vs_baseline": "",
            "high_vs_low_spread": "",
            "control_result_label": "",
            "confidence_label": _compare_confidence_label(sum(r["comparable_rows"] for r in provider_family_rows)),
            "best_bucket": strongest["control_value"] if strongest else "",
            "best_bucket_rate": _round4(strongest["best_bucket_rate"]) if strongest else "",
            "weakest_bucket": weakest["control_value"] if weakest else "",
            "weakest_bucket_rate": _round4(weakest["worst_bucket_rate"]) if weakest else "",
            "monotonicity_label": "",
            "sensitivity_label": "",
            "survival_label": "",
            "notes": f"tested_slices={len(slices)}; positive={positive}; negative={negative}; insufficient={insufficient}",
        })

    summary_meta = {
        "global_baseline_rate": global_baseline,
        "raw_result_label": "WEAK_SYNCHRONY_SIGNAL",
        "raw_spread": raw_spread,
        "raw_best_bucket": _norm(raw_best.get("direction_bucket")) if raw_best else "",
        "raw_best_rate": _as_float(raw_best.get("correct_rate")) if raw_best else None,
        "raw_worst_bucket": _norm(raw_worst.get("direction_bucket")) if raw_worst else "",
        "raw_worst_rate": _as_float(raw_worst.get("correct_rate")) if raw_worst else None,
        "control_summaries": control_summaries,
        "retained_families": sorted(retained_families),
        "excluded_families": sorted(set(family_counts) - retained_families),
        "bucket_sensitivity": bucket_meta,
    }
    summary_meta["overall_interpretation"] = _overall_interpretation(control_summaries, summary_meta)
    return rows, summary_meta


def _overall_interpretation(control_summaries: Dict[str, Dict[str, Any]], meta: Dict[str, Any]) -> str:
    bucket_label = meta.get("bucket_sensitivity", {}).get("sensitivity_label", "INSUFFICIENT_DATA")
    raw_result = meta["control_summaries"].get("raw_direction_synchrony_effect", {}).get("control_result_label", "INSUFFICIENT_DATA")
    provider_result = meta["control_summaries"].get("provider_controlled_direction_synchrony", {}).get("control_result_label", "INSUFFICIENT_DATA")
    no_anthropic_result = meta["control_summaries"].get("no_anthropic_direction_synchrony", {}).get("control_result_label", "INSUFFICIENT_DATA")
    family_result = meta["control_summaries"].get("family_controlled_direction_synchrony", {}).get("control_result_label", "INSUFFICIENT_DATA")
    cohort_result = meta["control_summaries"].get("cohort_controlled_direction_synchrony", {}).get("control_result_label", "INSUFFICIENT_DATA")
    if bucket_label == "BUCKET_ARTIFACT_RISK":
        return "DIRECTION_SYNCHRONY_BUCKET_ARTIFACT"
    if raw_result == "COLLAPSES":
        return "NO_ROBUST_DIRECTION_SYNCHRONY_SIGNAL"
    if no_anthropic_result == "COLLAPSES" and provider_result in {"COLLAPSES", "WEAKENS"}:
        return "DIRECTION_SYNCHRONY_PROVIDER_CONFOUNDED"
    if family_result == "COLLAPSES":
        return "DIRECTION_SYNCHRONY_FAMILY_CONFOUNDED"
    if cohort_result == "COLLAPSES":
        return "DIRECTION_SYNCHRONY_COHORT_DEPENDENT"
    if raw_result in {"SURVIVES", "WEAKENS"} and bucket_label in {"STABLE_ACROSS_BUCKETS", "PARTIAL_BUCKET_DEPENDENCE"}:
        return "DIRECTION_SYNCHRONY_WEAK_BUT_REAL"
    return "NO_ROBUST_DIRECTION_SYNCHRONY_SIGNAL"


def _summary_output_rows(generated_ts: str, audit_rows: Sequence[Dict[str, Any]], meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    overall = meta["control_summaries"]["raw_direction_synchrony_effect"]
    overall_label = meta.get("overall_interpretation") or _overall_interpretation(meta["control_summaries"], meta)
    global_baseline = meta.get("global_baseline_rate")
    raw_rows = [r for r in audit_rows if r["test_id"] == "raw_direction_synchrony_effect"]
    raw_buckets = [r for r in raw_rows if r["direction_bucket"] != "MISSING"]
    raw_best = max(raw_buckets, key=lambda r: _as_float(r.get("correct_rate")) or -1.0, default=None)
    raw_worst = min(raw_buckets, key=lambda r: _as_float(r.get("correct_rate")) or 999.0, default=None)
    raw_spread = (_as_float(raw_best.get("correct_rate")) - _as_float(raw_worst.get("correct_rate"))) if raw_best and raw_worst and _as_float(raw_best.get("correct_rate")) is not None and _as_float(raw_worst.get("correct_rate")) is not None else None
    rows.append({
        "generated_ts": generated_ts,
        "section": "A_OVERALL_RESULT",
        "test_id": "raw_direction_synchrony_effect",
        "test_name": "Raw Direction Synchrony Effect",
        "bucket_scheme": "existing_direction_synchrony_bucket",
        "control_dimension": "global",
        "control_value": "all",
        "provider": "",
        "event_family": "",
        "cohort_bucket": "",
        "sample_groups": sum(r["sample_groups"] for r in raw_rows),
        "comparable_rows": sum(r["comparable_rows"] for r in raw_rows),
        "correct_count": sum(r["correct_count"] for r in raw_rows),
        "wrong_count": sum(r["wrong_count"] for r in raw_rows),
        "correct_rate": _round4(global_baseline),
        "baseline_rate": _round4(global_baseline),
        "delta_vs_baseline": "",
        "high_vs_low_spread": _round4(raw_spread),
        "control_result_label": overall["control_result_label"],
        "confidence_label": overall["confidence_label"],
        "best_bucket": _norm(raw_best.get("direction_bucket")) if raw_best else "",
        "best_bucket_rate": _round4(_as_float(raw_best.get("correct_rate")) if raw_best else None),
        "weakest_bucket": _norm(raw_worst.get("direction_bucket")) if raw_worst else "",
        "weakest_bucket_rate": _round4(_as_float(raw_worst.get("correct_rate")) if raw_worst else None),
        "monotonicity_label": overall["monotonicity_label"],
        "sensitivity_label": meta.get("bucket_sensitivity", {}).get("sensitivity_label", "INSUFFICIENT_DATA"),
        "survival_label": overall["control_result_label"],
        "notes": "Historical synchrony/accuracy association only.",
    })

    for test_id, test_name in TESTS[1:7]:
        test_rows = [r for r in audit_rows if r["test_id"] == test_id]
        if not test_rows:
            continue
        groups = defaultdict(list)
        for r in test_rows:
            groups[r["control_value"]].append(r)
        # per-control summary rows
        for control_value, group_rows in sorted(groups.items()):
            buckets = [r for r in group_rows if r["direction_bucket"] != "MISSING"]
            best = max(buckets, key=lambda r: _as_float(r.get("correct_rate")) or -1.0, default=None)
            worst = min(buckets, key=lambda r: _as_float(r.get("correct_rate")) or 999.0, default=None)
            spread = (_as_float(best.get("correct_rate")) - _as_float(worst.get("correct_rate"))) if best and worst and _as_float(best.get("correct_rate")) is not None and _as_float(worst.get("correct_rate")) is not None else None
            if test_id == "provider_controlled_direction_synchrony":
                baseline = _safe_rate(sum(r["correct_count"] for r in group_rows), sum(r["comparable_rows"] for r in group_rows))
                control_label = group_rows[0].get("provider_control_result", "")
            elif test_id == "no_anthropic_direction_synchrony":
                baseline = _safe_rate(sum(r["correct_count"] for r in group_rows), sum(r["comparable_rows"] for r in group_rows))
                control_label = group_rows[0].get("no_anthropic_result", "")
            elif test_id == "family_controlled_direction_synchrony":
                baseline = _safe_rate(sum(r["correct_count"] for r in group_rows), sum(r["comparable_rows"] for r in group_rows))
                control_label = group_rows[0].get("family_control_result", "")
            elif test_id == "provider_family_direction_synchrony":
                baseline = _safe_rate(sum(r["correct_count"] for r in group_rows), sum(r["comparable_rows"] for r in group_rows))
                control_label = group_rows[0].get("provider_family_control_result", "")
            elif test_id == "cohort_controlled_direction_synchrony":
                baseline = _safe_rate(sum(r["correct_count"] for r in group_rows), sum(r["comparable_rows"] for r in group_rows))
                control_label = group_rows[0].get("cohort_control_result", "")
            else:
                baseline = _safe_rate(sum(r["correct_count"] for r in group_rows), sum(r["comparable_rows"] for r in group_rows))
                control_label = group_rows[0].get("control_result_label", "")
            rows.append({
                "generated_ts": generated_ts,
                "section": "B_STRESS_TEST_SUMMARY",
                "test_id": test_id,
                "test_name": test_name,
                "bucket_scheme": group_rows[0]["bucket_scheme"],
                "control_dimension": group_rows[0]["control_dimension"],
                "control_value": control_value,
                "provider": group_rows[0]["provider"],
                "event_family": group_rows[0]["event_family"],
                "cohort_bucket": group_rows[0]["cohort_bucket"],
                "sample_groups": sum(r["sample_groups"] for r in group_rows),
                "comparable_rows": sum(r["comparable_rows"] for r in group_rows),
                "correct_count": sum(r["correct_count"] for r in group_rows),
                "wrong_count": sum(r["wrong_count"] for r in group_rows),
                "correct_rate": _round4(_safe_rate(sum(r["correct_count"] for r in group_rows), sum(r["comparable_rows"] for r in group_rows))),
                "baseline_rate": _round4(baseline),
                "delta_vs_baseline": _round4((_safe_rate(sum(r["correct_count"] for r in group_rows), sum(r["comparable_rows"] for r in group_rows)) or 0) - (baseline or 0)) if baseline is not None else "",
                "high_vs_low_spread": _round4(spread),
                "control_result_label": control_label,
                "confidence_label": _compare_confidence_label(sum(r["comparable_rows"] for r in group_rows)),
                "best_bucket": _norm(best.get("direction_bucket")) if best else "",
                "best_bucket_rate": _round4(_as_float(best.get("correct_rate")) if best else None),
                "weakest_bucket": _norm(worst.get("direction_bucket")) if worst else "",
                "weakest_bucket_rate": _round4(_as_float(worst.get("correct_rate")) if worst else None),
                "monotonicity_label": group_rows[0]["monotonicity_label"],
                "sensitivity_label": meta.get("bucket_sensitivity", {}).get("sensitivity_label", "INSUFFICIENT_DATA") if test_id == "bucket_sensitivity" else "",
                "survival_label": control_label,
                "notes": "",
            })

    # provider summary
    provider_rows = [r for r in audit_rows if r["test_id"] == "provider_controlled_direction_synchrony"]
    provider_groups = defaultdict(list)
    for r in provider_rows:
        provider_groups[r["provider"]].append(r)
    for provider, group_rows in sorted(provider_groups.items()):
        buckets = [r for r in group_rows if r["direction_bucket"] != "MISSING"]
        best = max(buckets, key=lambda r: _as_float(r.get("correct_rate")) or -1.0, default=None)
        worst = min(buckets, key=lambda r: _as_float(r.get("correct_rate")) or 999.0, default=None)
        spread = (_as_float(best.get("correct_rate")) - _as_float(worst.get("correct_rate"))) if best and worst and _as_float(best.get("correct_rate")) is not None and _as_float(worst.get("correct_rate")) is not None else None
        provider_baseline = _safe_rate(sum(r["correct_count"] for r in group_rows), sum(r["comparable_rows"] for r in group_rows))
        rows.append({
            "generated_ts": generated_ts,
            "section": "C_PROVIDER_CONTROLLED_RESULT",
            "test_id": "provider_controlled_direction_synchrony",
            "test_name": "Provider-Controlled Direction Synchrony",
            "bucket_scheme": "existing_direction_synchrony_bucket",
            "control_dimension": "provider",
            "control_value": provider,
            "provider": provider,
            "event_family": "",
            "cohort_bucket": "",
            "sample_groups": sum(r["sample_groups"] for r in group_rows),
            "comparable_rows": sum(r["comparable_rows"] for r in group_rows),
            "correct_count": sum(r["correct_count"] for r in group_rows),
            "wrong_count": sum(r["wrong_count"] for r in group_rows),
            "correct_rate": _round4(provider_baseline),
            "baseline_rate": _round4(provider_baseline),
            "delta_vs_baseline": "",
            "high_vs_low_spread": _round4(spread),
            "control_result_label": group_rows[0].get("provider_control_result", ""),
            "confidence_label": _compare_confidence_label(sum(r["comparable_rows"] for r in group_rows)),
            "best_bucket": _norm(best.get("direction_bucket")) if best else "",
            "best_bucket_rate": _round4(_as_float(best.get("correct_rate")) if best else None),
            "weakest_bucket": _norm(worst.get("direction_bucket")) if worst else "",
            "weakest_bucket_rate": _round4(_as_float(worst.get("correct_rate")) if worst else None),
            "monotonicity_label": group_rows[0]["monotonicity_label"],
            "sensitivity_label": "",
            "survival_label": group_rows[0].get("provider_control_result", ""),
            "notes": "",
        })

    # no-Anthropic
    na_rows = [r for r in audit_rows if r["test_id"] == "no_anthropic_direction_synchrony"]
    na_buckets = [r for r in na_rows if r["direction_bucket"] != "MISSING"]
    na_best = max(na_buckets, key=lambda r: _as_float(r.get("correct_rate")) or -1.0, default=None)
    na_worst = min(na_buckets, key=lambda r: _as_float(r.get("correct_rate")) or 999.0, default=None)
    na_spread = (_as_float(na_best.get("correct_rate")) - _as_float(na_worst.get("correct_rate"))) if na_best and na_worst and _as_float(na_best.get("correct_rate")) is not None and _as_float(na_worst.get("correct_rate")) is not None else None
    na_baseline = _safe_rate(sum(r["correct_count"] for r in na_rows), sum(r["comparable_rows"] for r in na_rows))
    rows.append({
        "generated_ts": generated_ts,
        "section": "D_NO_ANTHROPIC_RESULT",
        "test_id": "no_anthropic_direction_synchrony",
        "test_name": "No-Anthropic Direction Synchrony",
        "bucket_scheme": "existing_direction_synchrony_bucket",
        "control_dimension": "no_anthropic",
        "control_value": "Gemini|OpenAI",
        "provider": "",
        "event_family": "",
        "cohort_bucket": "",
        "sample_groups": sum(r["sample_groups"] for r in na_rows),
        "comparable_rows": sum(r["comparable_rows"] for r in na_rows),
        "correct_count": sum(r["correct_count"] for r in na_rows),
        "wrong_count": sum(r["wrong_count"] for r in na_rows),
        "correct_rate": _round4(na_baseline),
        "baseline_rate": _round4(na_baseline),
        "delta_vs_baseline": "",
        "high_vs_low_spread": _round4(na_spread),
        "control_result_label": na_rows[0].get("no_anthropic_result", ""),
        "confidence_label": _compare_confidence_label(sum(r["comparable_rows"] for r in na_rows)),
        "best_bucket": _norm(na_best.get("direction_bucket")) if na_best else "",
        "best_bucket_rate": _round4(_as_float(na_best.get("correct_rate")) if na_best else None),
        "weakest_bucket": _norm(na_worst.get("direction_bucket")) if na_worst else "",
        "weakest_bucket_rate": _round4(_as_float(na_worst.get("correct_rate")) if na_worst else None),
        "monotonicity_label": na_rows[0]["monotonicity_label"],
        "sensitivity_label": "",
        "survival_label": na_rows[0].get("no_anthropic_result", ""),
        "notes": "",
    })

    # family result
    family_rows = [r for r in audit_rows if r["test_id"] == "family_controlled_direction_synchrony"]
    family_groups = defaultdict(list)
    for r in family_rows:
        family_groups[r["event_family"]].append(r)
    for family, group_rows in sorted(family_groups.items()):
        buckets = [r for r in group_rows if r["direction_bucket"] != "MISSING"]
        best = max(buckets, key=lambda r: _as_float(r.get("correct_rate")) or -1.0, default=None)
        worst = min(buckets, key=lambda r: _as_float(r.get("correct_rate")) or 999.0, default=None)
        spread = (_as_float(best.get("correct_rate")) - _as_float(worst.get("correct_rate"))) if best and worst and _as_float(best.get("correct_rate")) is not None and _as_float(worst.get("correct_rate")) is not None else None
        family_baseline = _safe_rate(sum(r["correct_count"] for r in group_rows), sum(r["comparable_rows"] for r in group_rows))
        rows.append({
            "generated_ts": generated_ts,
            "section": "E_FAMILY_CONTROLLED_RESULT",
            "test_id": "family_controlled_direction_synchrony",
            "test_name": "Family-Controlled Direction Synchrony",
            "bucket_scheme": "existing_direction_synchrony_bucket",
            "control_dimension": "family",
            "control_value": family,
            "provider": "",
            "event_family": family,
            "cohort_bucket": "",
            "sample_groups": sum(r["sample_groups"] for r in group_rows),
            "comparable_rows": sum(r["comparable_rows"] for r in group_rows),
            "correct_count": sum(r["correct_count"] for r in group_rows),
            "wrong_count": sum(r["wrong_count"] for r in group_rows),
            "correct_rate": _round4(family_baseline),
            "baseline_rate": _round4(family_baseline),
            "delta_vs_baseline": "",
            "high_vs_low_spread": _round4(spread),
            "control_result_label": group_rows[0].get("family_control_result", ""),
            "confidence_label": _compare_confidence_label(sum(r["comparable_rows"] for r in group_rows)),
            "best_bucket": _norm(best.get("direction_bucket")) if best else "",
            "best_bucket_rate": _round4(_as_float(best.get("correct_rate")) if best else None),
            "weakest_bucket": _norm(worst.get("direction_bucket")) if worst else "",
            "weakest_bucket_rate": _round4(_as_float(worst.get("correct_rate")) if worst else None),
            "monotonicity_label": group_rows[0]["monotonicity_label"],
            "sensitivity_label": "",
            "survival_label": group_rows[0].get("family_control_result", ""),
            "notes": "",
        })

    # cohort result
    cohort_rows = [r for r in audit_rows if r["test_id"] == "cohort_controlled_direction_synchrony"]
    cohort_groups = defaultdict(list)
    for r in cohort_rows:
        cohort_groups[r["cohort_bucket"]].append(r)
    for cohort_bucket, group_rows in sorted(cohort_groups.items()):
        buckets = [r for r in group_rows if r["direction_bucket"] != "MISSING"]
        best = max(buckets, key=lambda r: _as_float(r.get("correct_rate")) or -1.0, default=None)
        worst = min(buckets, key=lambda r: _as_float(r.get("correct_rate")) or 999.0, default=None)
        spread = (_as_float(best.get("correct_rate")) - _as_float(worst.get("correct_rate"))) if best and worst and _as_float(best.get("correct_rate")) is not None and _as_float(worst.get("correct_rate")) is not None else None
        cohort_baseline = _safe_rate(sum(r["correct_count"] for r in group_rows), sum(r["comparable_rows"] for r in group_rows))
        rows.append({
            "generated_ts": generated_ts,
            "section": "G_COHORT_RESULT",
            "test_id": "cohort_controlled_direction_synchrony",
            "test_name": "Cohort-Controlled Direction Synchrony",
            "bucket_scheme": "existing_direction_synchrony_bucket",
            "control_dimension": "cohort",
            "control_value": cohort_bucket,
            "provider": "",
            "event_family": "",
            "cohort_bucket": cohort_bucket,
            "sample_groups": sum(r["sample_groups"] for r in group_rows),
            "comparable_rows": sum(r["comparable_rows"] for r in group_rows),
            "correct_count": sum(r["correct_count"] for r in group_rows),
            "wrong_count": sum(r["wrong_count"] for r in group_rows),
            "correct_rate": _round4(cohort_baseline),
            "baseline_rate": _round4(cohort_baseline),
            "delta_vs_baseline": "",
            "high_vs_low_spread": _round4(spread),
            "control_result_label": group_rows[0].get("cohort_control_result", ""),
            "confidence_label": _compare_confidence_label(sum(r["comparable_rows"] for r in group_rows)),
            "best_bucket": _norm(best.get("direction_bucket")) if best else "",
            "best_bucket_rate": _round4(_as_float(best.get("correct_rate")) if best else None),
            "weakest_bucket": _norm(worst.get("direction_bucket")) if worst else "",
            "weakest_bucket_rate": _round4(_as_float(worst.get("correct_rate")) if worst else None),
            "monotonicity_label": group_rows[0]["monotonicity_label"],
            "sensitivity_label": "",
            "survival_label": group_rows[0].get("cohort_control_result", ""),
            "notes": "",
        })

    # thin family exclusion
    thin_rows = [r for r in audit_rows if r["test_id"] == "thin_family_exclusion"]
    thin_buckets = [r for r in thin_rows if r["direction_bucket"] != "MISSING"]
    thin_best = max(thin_buckets, key=lambda r: _as_float(r.get("correct_rate")) or -1.0, default=None)
    thin_worst = min(thin_buckets, key=lambda r: _as_float(r.get("correct_rate")) or 999.0, default=None)
    thin_spread = (_as_float(thin_best.get("correct_rate")) - _as_float(thin_worst.get("correct_rate"))) if thin_best and thin_worst and _as_float(thin_best.get("correct_rate")) is not None and _as_float(thin_worst.get("correct_rate")) is not None else None
    rows.append({
        "generated_ts": generated_ts,
        "section": "H_THIN_FAMILY_EXCLUSION",
        "test_id": "thin_family_exclusion",
        "test_name": "Thin-Family Exclusion",
        "bucket_scheme": "existing_direction_synchrony_bucket",
        "control_dimension": "family_filter",
        "control_value": "families_ge_8",
        "provider": "",
        "event_family": "",
        "cohort_bucket": "",
        "sample_groups": sum(r["sample_groups"] for r in thin_rows),
        "comparable_rows": sum(r["comparable_rows"] for r in thin_rows),
        "correct_count": sum(r["correct_count"] for r in thin_rows),
        "wrong_count": sum(r["wrong_count"] for r in thin_rows),
        "correct_rate": _round4(_safe_rate(sum(r["correct_count"] for r in thin_rows), sum(r["comparable_rows"] for r in thin_rows))),
        "baseline_rate": _round4(_safe_rate(sum(r["correct_count"] for r in thin_rows), sum(r["comparable_rows"] for r in thin_rows))),
        "delta_vs_baseline": "",
        "high_vs_low_spread": _round4(thin_spread),
        "control_result_label": "SURVIVES" if thin_spread and thin_spread > 0 else "INSUFFICIENT_DATA",
        "confidence_label": _compare_confidence_label(sum(r["comparable_rows"] for r in thin_rows)),
        "best_bucket": _norm(thin_best.get("direction_bucket")) if thin_best else "",
        "best_bucket_rate": _round4(_as_float(thin_best.get("correct_rate")) if thin_best else None),
        "weakest_bucket": _norm(thin_worst.get("direction_bucket")) if thin_worst else "",
        "weakest_bucket_rate": _round4(_as_float(thin_worst.get("correct_rate")) if thin_worst else None),
        "monotonicity_label": _monotonicity_from_order([r["correct_rate"] for r in thin_buckets if r["direction_bucket"] != "MISSING"]),
        "sensitivity_label": "",
        "survival_label": "SURVIVES" if thin_spread and thin_spread > 0 else "INSUFFICIENT_DATA",
        "notes": f"retained_families={','.join(meta['retained_families'])}; excluded_families={','.join(meta['excluded_families'])}",
    })

    # bucket sensitivity
    sens_rows = [r for r in audit_rows if r["test_id"] == "bucket_sensitivity"]
    by_scheme = defaultdict(list)
    for r in sens_rows:
        by_scheme[r["bucket_scheme"]].append(r)
    for scheme_name, scheme_rows in sorted(by_scheme.items()):
        buckets = [r for r in scheme_rows if r["direction_bucket"] != "MISSING"]
        best = max(buckets, key=lambda r: _as_float(r.get("correct_rate")) or -1.0, default=None)
        worst = min(buckets, key=lambda r: _as_float(r.get("correct_rate")) or 999.0, default=None)
        spread = (_as_float(best.get("correct_rate")) - _as_float(worst.get("correct_rate"))) if best and worst and _as_float(best.get("correct_rate")) is not None and _as_float(worst.get("correct_rate")) is not None else None
        rows.append({
            "generated_ts": generated_ts,
            "section": "I_BUCKET_SENSITIVITY",
            "test_id": "bucket_sensitivity",
            "test_name": "Bucket Sensitivity",
            "bucket_scheme": scheme_name,
            "control_dimension": "scheme",
            "control_value": scheme_name,
            "provider": "",
            "event_family": "",
            "cohort_bucket": "",
            "sample_groups": sum(r["sample_groups"] for r in scheme_rows),
            "comparable_rows": sum(r["comparable_rows"] for r in scheme_rows),
            "correct_count": sum(r["correct_count"] for r in scheme_rows),
            "wrong_count": sum(r["wrong_count"] for r in scheme_rows),
            "correct_rate": _round4(_safe_rate(sum(r["correct_count"] for r in scheme_rows), sum(r["comparable_rows"] for r in scheme_rows))),
            "baseline_rate": _round4(_safe_rate(sum(r["correct_count"] for r in scheme_rows), sum(r["comparable_rows"] for r in scheme_rows))),
            "delta_vs_baseline": "",
            "high_vs_low_spread": _round4(spread),
            "control_result_label": scheme_rows[0].get("bucket_sensitivity_result", ""),
            "confidence_label": _compare_confidence_label(sum(r["comparable_rows"] for r in scheme_rows)),
            "best_bucket": _norm(best.get("direction_bucket")) if best else "",
            "best_bucket_rate": _round4(_as_float(best.get("correct_rate")) if best else None),
            "weakest_bucket": _norm(worst.get("direction_bucket")) if worst else "",
            "weakest_bucket_rate": _round4(_as_float(worst.get("correct_rate")) if worst else None),
            "monotonicity_label": _monotonicity_from_order([r["correct_rate"] for r in buckets]),
            "sensitivity_label": meta.get("bucket_sensitivity", {}).get("sensitivity_label", "INSUFFICIENT_DATA"),
            "survival_label": scheme_rows[0].get("bucket_sensitivity_result", ""),
            "notes": "",
        })

    rows.append({
        "generated_ts": generated_ts,
        "section": "J_FINAL_INTERPRETATION",
        "test_id": "overall",
        "test_name": "Overall Direction Synchrony Robustness",
        "bucket_scheme": "existing_direction_synchrony_bucket",
        "control_dimension": "global",
        "control_value": "all",
        "provider": "",
        "event_family": "",
        "cohort_bucket": "",
        "sample_groups": len(audit_rows),
        "comparable_rows": sum(r["comparable_rows"] for r in raw_rows),
        "correct_count": sum(r["correct_count"] for r in raw_rows),
        "wrong_count": sum(r["wrong_count"] for r in raw_rows),
        "correct_rate": _round4(global_baseline),
        "baseline_rate": _round4(global_baseline),
        "delta_vs_baseline": "",
        "high_vs_low_spread": _round4(meta.get("raw_spread")),
        "control_result_label": overall_label,
        "confidence_label": _compare_confidence_label(sum(r["comparable_rows"] for r in raw_rows)),
        "best_bucket": meta.get("raw_best_bucket", ""),
        "best_bucket_rate": _round4(meta.get("raw_best_rate")),
        "weakest_bucket": meta.get("raw_worst_bucket", ""),
        "weakest_bucket_rate": _round4(meta.get("raw_worst_rate")),
        "monotonicity_label": meta["control_summaries"]["raw_direction_synchrony_effect"]["monotonicity_label"],
        "sensitivity_label": meta.get("bucket_sensitivity", {}).get("sensitivity_label", "INSUFFICIENT_DATA"),
        "survival_label": overall_label,
        "notes": f"excluded_families={','.join(meta['excluded_families'])}; retained_families={','.join(meta['retained_families'])}",
    })

    return rows


def _upsert_registry_rows(service) -> Dict[str, Any]:
    rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    if not rows:
        raise RuntimeError("Sheet_Registry is missing or empty.")
    existing_headers = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=PROJECT_OVERVIEWS_SPREADSHEET_ID, range=f"'{REGISTRY_SHEET}'!1:1")
        .execute()
        .get("values", [[]])[0]
    ) or list(REGISTRY_HEADERS)
    now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    by_id = {(_norm(row.get("logical_sheet_id")).upper()): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {(_norm(row.get("logical_sheet_id")).upper()): row for row in rows}
    updates = []
    appended = 0
    for row in REGISTRY_ROWS:
        key = _norm(row["logical_sheet_id"]).upper()
        existing = existing_by_id.get(key, {})
        merged = dict(row)
        if "registry_created_ts" in existing_headers:
            merged["registry_created_ts"] = _norm(existing.get("registry_created_ts")) or now
        if "registry_last_verified_ts" in existing_headers:
            merged["registry_last_verified_ts"] = now
        if "registry_migration_ts" in existing_headers:
            merged["registry_migration_ts"] = _norm(existing.get("registry_migration_ts"))
        if "registry_rename_ts" in existing_headers:
            merged["registry_rename_ts"] = _norm(existing.get("registry_rename_ts"))
        values = [merged.get(header, "") for header in existing_headers]
        if key in by_id:
            row_number = by_id[key]
            updates.append({
                "range": f"'{REGISTRY_SHEET}'!A{row_number}:{_column_letter(len(existing_headers))}{row_number}",
                "values": [values],
            })
        else:
            appended += 1
            target_row = len(rows) + appended
            updates.append({
                "range": f"'{REGISTRY_SHEET}'!A{target_row}:{_column_letter(len(existing_headers))}{target_row}",
                "values": [values],
            })
    if updates:
        batch_update_values(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, updates)
    return {"updated": len(REGISTRY_ROWS) - appended, "appended": appended}


def build_direction_robustness_audit() -> Dict[str, Any]:
    service = build_sheets_service(load_credentials(interactive=False))
    sources = _read_inputs(service)
    generated_ts = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    records = _build_records(sources)
    audit_rows, meta = _build_audit_rows(records, generated_ts)
    summary_rows = _summary_output_rows(generated_ts, audit_rows, meta)
    overall_interpretation = meta.get("overall_interpretation") or _overall_interpretation(meta["control_summaries"], meta)

    audit_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_AUDIT_SHEET, AUDIT_HEADERS)
    summary_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_AUDIT_SHEET, audit_headers, audit_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, summary_rows)
    registry_result = _upsert_registry_rows(service)
    overall_row = next((r for r in summary_rows if r.get("section") == "A_OVERALL_RESULT"), {})

    return {
        "generated_ts": generated_ts,
        "sample_groups": len(records),
        "comparable_rows": sum(1 for r in records if r["actual_comparable"] == "TRUE"),
        "providers_represented": sorted({r["provider"] for r in records}),
        "families_represented": sorted({r["event_family"] for r in records}),
        "cohorts_represented": sorted({r["cohort_bucket"] for r in records}),
        "excluded_thin_families": meta["excluded_families"],
        "overall_interpretation": overall_row.get("control_result_label", overall_interpretation),
        "raw_spread": overall_row.get("high_vs_low_spread", ""),
        "raw_best_bucket": overall_row.get("best_bucket", ""),
        "raw_worst_bucket": overall_row.get("weakest_bucket", ""),
        "global_baseline_rate": _round4(meta["global_baseline_rate"]),
        "global_baseline": _round4(meta["global_baseline_rate"]),
        "registry": registry_result,
    }


if __name__ == "__main__":
    print(build_direction_robustness_audit())
