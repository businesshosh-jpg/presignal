import os
import sys
from collections import defaultdict
from datetime import datetime
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


OUTPUT_AUDIT_SHEET = "Signal_Synchrony_Accuracy_Audit"
OUTPUT_SUMMARY_SHEET = "Signal_Synchrony_Accuracy_Summary"

REGISTRY_ROWS = [
    {
        "logical_sheet_id": "SIGNAL_SYNCHRONY_ACCURACY_AUDIT",
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
        "notes": "Derived-only synchrony accuracy audit",
    },
    {
        "logical_sheet_id": "SIGNAL_SYNCHRONY_ACCURACY_SUMMARY",
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
        "notes": "Derived-only synchrony accuracy summary",
    },
]

AUDIT_HEADERS = [
    "generated_ts",
    "sample_group_id",
    "event_id",
    "provider",
    "cohort_id",
    "event_family",
    "indicator_name",
    "country",
    "release_ts",
    "importance",
    "predictability_bucket",
    "actual_available",
    "actual_comparable",
    "forecast_matches_actual",
    "outcome_result_label",
    "outcome_check_status",
    "forecast_direction_concentration",
    "pattern_concentration_score",
    "expression_similarity_mean",
    "reproducibility_outcome_label",
    "stability_label",
    "recommended_protocol",
    "rerun_success_count",
    "rerun_failure_count",
    "dominant_forecast_direction",
    "dominant_pattern_label",
    "direction_synchrony_bucket",
    "pattern_synchrony_bucket",
    "expression_similarity_bucket",
    "overall_synchrony_bucket",
    "provider_control_key",
    "family_control_key",
    "cohort_control_key",
    "provider_family_key",
    "family_predictability_key",
    "missing_metric_flag",
    "thin_sample_flag",
    "confidence_label",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "section",
    "metric_name",
    "bucket",
    "provider",
    "event_family",
    "cohort_id",
    "sample_groups",
    "comparable_rows",
    "correct_count",
    "wrong_count",
    "correct_rate",
    "baseline_correct_rate",
    "delta_vs_baseline",
    "provider_baseline_rate",
    "delta_vs_provider_baseline",
    "family_baseline_rate",
    "delta_vs_family_baseline",
    "provider_family_baseline_rate",
    "delta_vs_provider_family_baseline",
    "cohort_baseline_rate",
    "delta_vs_cohort_baseline",
    "best_bucket",
    "best_bucket_correct_rate",
    "worst_bucket",
    "worst_bucket_correct_rate",
    "spread",
    "monotonicity_label",
    "provider_control_survival_label",
    "family_control_survival_label",
    "overall_signal_label",
    "final_interpretation",
    "confidence_label",
    "notes",
]

BUCKET_ORDER = ["LOW", "MEDIUM", "HIGH", "VERY_HIGH"]
METRIC_BUCKET_FIELDS = [
    "direction_synchrony_bucket",
    "pattern_synchrony_bucket",
    "expression_similarity_bucket",
    "overall_synchrony_bucket",
    "stability_label",
    "recommended_protocol",
    "reproducibility_outcome_label",
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


def _bucket_continuous(value: Optional[float]) -> str:
    if value is None:
        return "MISSING"
    if value < 0.50:
        return "LOW"
    if value < 0.70:
        return "MEDIUM"
    if value < 0.90:
        return "HIGH"
    return "VERY_HIGH"


def _is_comparable(row: Dict[str, Any]) -> bool:
    if _as_bool(row.get("actual_comparable")):
        return True
    return _upper(row.get("outcome_result_label")) in {
        "FORECAST_CORRECT",
        "FORECAST_INLINE_CORRECT",
        "FORECAST_WRONG",
    }


def _is_correct(row: Dict[str, Any]) -> bool:
    return _upper(row.get("outcome_result_label")) in {
        "FORECAST_CORRECT",
        "FORECAST_INLINE_CORRECT",
    } or _as_bool(row.get("forecast_matches_actual"))


def _read_inputs(service) -> Dict[str, List[Dict[str, Any]]]:
    names = {
        "microcohort": "Provider_Character_Direct_Expression_Microcohort",
        "outcome_check": "Provider_Character_Direct_Expression_Outcome_Check",
        "provider_slice": "Signal_Synchrony_Provider_Slice_Performance",
        "rerun_sufficiency": "Signal_Synchrony_Rerun_Count_Sufficiency",
        "cohort_characterization": "Signal_Synchrony_Cohort_Characterization",
        "provider_dep": "Signal_Synchrony_Provider_Dep_Falsification",
        "provider_dep_summary": "Signal_Synchrony_Provider_Dep_Falsification_Summary",
        "family_slice": "Signal_Synchrony_Family_Slice_Performance",
        "cpv_audit": "Signal_Synchrony_Conditional_Value_Audit",
        "cpv_stability": "Signal_Synchrony_Conditional_Value_Stability",
        "cpv_mechanism": "Signal_Synchrony_Conditional_Value_Mechanism",
    }
    return {key: _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet) for key, sheet in names.items()}


def _build_audit_rows(sources: Dict[str, List[Dict[str, Any]]], generated_ts: str) -> List[Dict[str, Any]]:
    micro_lookup = { _norm(r.get("sample_group_id")): r for r in sources["microcohort"] }
    outcome_lookup = { _norm(r.get("sample_group_id")): r for r in sources["outcome_check"] }
    suff_lookup = { _norm(r.get("sample_group_id")): r for r in sources["rerun_sufficiency"] }
    cohort_lookup = { _norm(r.get("sample_group_id")): r for r in sources["cohort_characterization"] }

    rows: List[Dict[str, Any]] = []
    for base in sources["provider_slice"]:
        sample_group_id = _norm(base.get("sample_group_id"))
        if not sample_group_id:
            continue
        micro = micro_lookup.get(sample_group_id, {})
        outcome = outcome_lookup.get(sample_group_id, {})
        suff = suff_lookup.get(sample_group_id, {})
        cohort = cohort_lookup.get(sample_group_id, {})

        direction_value = _as_float(base.get("forecast_direction_concentration"))
        pattern_value = _as_float(base.get("pattern_concentration_score"))
        expression_value = _as_float(base.get("expression_similarity_mean"))
        available_metrics = [v for v in [direction_value, pattern_value, expression_value] if v is not None]
        overall_value = _safe_mean(available_metrics) if len(available_metrics) >= 2 else None

        missing_metrics = []
        if direction_value is None:
            missing_metrics.append("forecast_direction_concentration")
        if pattern_value is None:
            missing_metrics.append("pattern_concentration_score")
        if expression_value is None:
            missing_metrics.append("expression_similarity_mean")

        comparable = _is_comparable(base)
        row = {
            "generated_ts": generated_ts,
            "sample_group_id": sample_group_id,
            "event_id": _norm(base.get("event_id")),
            "provider": _norm(base.get("provider")),
            "cohort_id": _norm(base.get("cohort_id")) or _norm(base.get("cohort_group")) or "",
            "event_family": _norm(base.get("event_family")) or "unknown",
            "indicator_name": _norm(base.get("indicator_name")),
            "country": _norm(base.get("country")),
            "release_ts": _norm(base.get("release_ts")),
            "importance": _norm(base.get("importance")) or "unknown",
            "predictability_bucket": _norm(base.get("predictability_bucket")) or _norm(cohort.get("predictability_bucket")) or "unknown",
            "actual_available": _norm(base.get("actual_available")) or _norm(outcome.get("actual_available")),
            "actual_comparable": "TRUE" if comparable else "FALSE",
            "forecast_matches_actual": _norm(base.get("forecast_matches_actual")) or _norm(outcome.get("forecast_matches_actual")),
            "outcome_result_label": _norm(base.get("outcome_result_label")) or _norm(outcome.get("outcome_result_label")),
            "outcome_check_status": _norm(base.get("outcome_check_status")) or _norm(outcome.get("outcome_check_status")),
            "forecast_direction_concentration": _round4(direction_value),
            "pattern_concentration_score": _round4(pattern_value),
            "expression_similarity_mean": _round4(expression_value),
            "reproducibility_outcome_label": _norm(base.get("reproducibility_outcome_label")) or _norm(outcome.get("reproducibility_outcome_label")),
            "stability_label": _norm(base.get("stability_label")) or _norm(suff.get("interpretation_label")),
            "recommended_protocol": _norm(base.get("recommended_protocol")),
            "rerun_success_count": _norm(base.get("rerun_success_count")) or _norm(suff.get("rerun_success_count")),
            "rerun_failure_count": _norm(base.get("rerun_failure_count")) or _norm(suff.get("rerun_failure_count")),
            "dominant_forecast_direction": _norm(base.get("dominant_forecast_direction")) or _norm(outcome.get("dominant_forecast_direction")) or _norm(micro.get("dominant_forecast_direction")),
            "dominant_pattern_label": _norm(micro.get("dominant_causal_family_if_classifiable")),
            "direction_synchrony_bucket": _bucket_continuous(direction_value),
            "pattern_synchrony_bucket": _bucket_continuous(pattern_value),
            "expression_similarity_bucket": _bucket_continuous(expression_value),
            "overall_synchrony_bucket": _bucket_continuous(overall_value) if overall_value is not None else "MISSING",
            "provider_control_key": _norm(base.get("provider")),
            "family_control_key": _norm(base.get("event_family")) or "unknown",
            "cohort_control_key": _norm(base.get("cohort_group")) or _norm(base.get("cohort_id")) or "unknown",
            "provider_family_key": f"{_norm(base.get('provider'))}|{_norm(base.get('event_family')) or 'unknown'}",
            "family_predictability_key": f"{_norm(base.get('event_family')) or 'unknown'}|{_norm(base.get('predictability_bucket')) or 'unknown'}",
            "missing_metric_flag": "|".join(missing_metrics) if missing_metrics else "",
            "thin_sample_flag": "",
            "confidence_label": "",
            "notes": _norm(cohort.get("notes")) or _norm(micro.get("notes")) or "",
        }
        rows.append(row)
    return rows


def _baseline_rate(rows: Sequence[Dict[str, Any]]) -> Optional[float]:
    comparable_rows = [r for r in rows if _as_bool(r.get("actual_comparable"))]
    return _safe_rate(sum(1 for r in comparable_rows if _is_correct(r)), len(comparable_rows))


def _bucket_summary_rows(
    generated_ts: str,
    section: str,
    rows: Sequence[Dict[str, Any]],
    metric_name: str,
    *,
    group_key: Optional[str] = None,
    subgroup_label: str = "",
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    global_baseline = _baseline_rate(rows)
    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        bucket = _norm(row.get(metric_name)) or "MISSING"
        group_value = _norm(row.get(group_key)) if group_key else ""
        grouped[(group_value, bucket)].append(row)

    group_baselines: Dict[str, Optional[float]] = {}
    if group_key:
        groups = sorted({_norm(r.get(group_key)) for r in rows})
        for group in groups:
            group_rows = [r for r in rows if _norm(r.get(group_key)) == group]
            group_baselines[group] = _baseline_rate(group_rows)

    for (group_value, bucket), bucket_rows in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1])):
        comparable_rows = [r for r in bucket_rows if _as_bool(r.get("actual_comparable"))]
        correct_count = sum(1 for r in comparable_rows if _is_correct(r))
        wrong_count = sum(1 for r in comparable_rows if not _is_correct(r))
        correct_rate = _safe_rate(correct_count, len(comparable_rows))
        baseline = group_baselines.get(group_value) if group_key else global_baseline
        row = {
            "generated_ts": generated_ts,
            "section": section,
            "metric_name": metric_name,
            "bucket": bucket,
            "provider": group_value if subgroup_label == "provider" else "",
            "event_family": group_value if subgroup_label == "event_family" else "",
            "cohort_id": group_value if subgroup_label == "cohort_id" else "",
            "sample_groups": len(bucket_rows),
            "comparable_rows": len(comparable_rows),
            "correct_count": correct_count,
            "wrong_count": wrong_count,
            "correct_rate": _round4(correct_rate),
            "baseline_correct_rate": _round4(global_baseline),
            "delta_vs_baseline": _round4(correct_rate - global_baseline) if correct_rate is not None and global_baseline is not None else "",
            "provider_baseline_rate": _round4(baseline) if subgroup_label == "provider" else "",
            "delta_vs_provider_baseline": _round4(correct_rate - baseline) if subgroup_label == "provider" and correct_rate is not None and baseline is not None else "",
            "family_baseline_rate": _round4(baseline) if subgroup_label == "event_family" else "",
            "delta_vs_family_baseline": _round4(correct_rate - baseline) if subgroup_label == "event_family" and correct_rate is not None and baseline is not None else "",
            "provider_family_baseline_rate": "",
            "delta_vs_provider_family_baseline": "",
            "cohort_baseline_rate": _round4(baseline) if subgroup_label == "cohort_id" else "",
            "delta_vs_cohort_baseline": _round4(correct_rate - baseline) if subgroup_label == "cohort_id" and correct_rate is not None and baseline is not None else "",
            "best_bucket": "",
            "best_bucket_correct_rate": "",
            "worst_bucket": "",
            "worst_bucket_correct_rate": "",
            "spread": "",
            "monotonicity_label": "",
            "provider_control_survival_label": "",
            "family_control_survival_label": "",
            "overall_signal_label": "",
            "final_interpretation": "",
            "confidence_label": _confidence_label(len(comparable_rows)),
            "notes": "",
        }
        out.append(row)
    return out


def _provider_family_rows(generated_ts: str, rows: Sequence[Dict[str, Any]], metric_name: str) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    provider_family_baselines: Dict[Tuple[str, str], Optional[float]] = {}
    for row in rows:
        provider = _norm(row.get("provider"))
        family = _norm(row.get("event_family"))
        bucket = _norm(row.get(metric_name)) or "MISSING"
        grouped[(provider, family, bucket)].append(row)
    for provider, family, _bucket in grouped:
        key = (provider, family)
        if key not in provider_family_baselines:
            provider_family_rows = [
                r for r in rows if _norm(r.get("provider")) == provider and _norm(r.get("event_family")) == family
            ]
            provider_family_baselines[key] = _baseline_rate(provider_family_rows)

    out: List[Dict[str, Any]] = []
    for (provider, family, bucket), bucket_rows in sorted(grouped.items()):
        comparable_rows = [r for r in bucket_rows if _as_bool(r.get("actual_comparable"))]
        correct_count = sum(1 for r in comparable_rows if _is_correct(r))
        wrong_count = sum(1 for r in comparable_rows if not _is_correct(r))
        correct_rate = _safe_rate(correct_count, len(comparable_rows))
        baseline = provider_family_baselines.get((provider, family))
        out.append({
            "generated_ts": generated_ts,
            "section": "D_PROVIDER_FAMILY_CONTROLLED_SYNCHRONY",
            "metric_name": metric_name,
            "bucket": bucket,
            "provider": provider,
            "event_family": family,
            "cohort_id": "",
            "sample_groups": len(bucket_rows),
            "comparable_rows": len(comparable_rows),
            "correct_count": correct_count,
            "wrong_count": wrong_count,
            "correct_rate": _round4(correct_rate),
            "baseline_correct_rate": "",
            "delta_vs_baseline": "",
            "provider_baseline_rate": "",
            "delta_vs_provider_baseline": "",
            "family_baseline_rate": "",
            "delta_vs_family_baseline": "",
            "provider_family_baseline_rate": _round4(baseline),
            "delta_vs_provider_family_baseline": _round4(correct_rate - baseline) if correct_rate is not None and baseline is not None else "",
            "cohort_baseline_rate": "",
            "delta_vs_cohort_baseline": "",
            "best_bucket": "",
            "best_bucket_correct_rate": "",
            "worst_bucket": "",
            "worst_bucket_correct_rate": "",
            "spread": "",
            "monotonicity_label": "",
            "provider_control_survival_label": "",
            "family_control_survival_label": "",
            "overall_signal_label": "",
            "final_interpretation": "",
            "confidence_label": _confidence_label(len(comparable_rows)),
            "notes": "",
        })
    return out


def _monotonicity(rows: Sequence[Dict[str, Any]]) -> str:
    bucket_rates = {}
    for bucket in BUCKET_ORDER:
        bucket_rows = [r for r in rows if _norm(r.get("bucket")) == bucket]
        comparable_rows = [r for r in bucket_rows if _norm(r.get("correct_rate")) != ""]
        if comparable_rows:
            bucket_rates[bucket] = _as_float(comparable_rows[0].get("correct_rate"))
    if len(bucket_rates) < 2:
        return "INSUFFICIENT_DATA"
    ordered = [bucket_rates[b] for b in BUCKET_ORDER if b in bucket_rates]
    if all(ordered[i] <= ordered[i + 1] for i in range(len(ordered) - 1)):
        return "MONOTONIC_POSITIVE"
    if ordered[-1] is not None and ordered[0] is not None and ordered[-1] > ordered[0]:
        return "PARTIAL_POSITIVE"
    if all(ordered[i] >= ordered[i + 1] for i in range(len(ordered) - 1)):
        return "NEGATIVE_OR_INVERSE"
    return "NO_MONOTONIC_PATTERN"


def _control_survival(control_rows: Sequence[Dict[str, Any]], delta_field: str) -> str:
    rows = [
        r for r in control_rows
        if _norm(r.get("bucket")) not in {"", "MISSING"}
        and _norm(r.get(delta_field)) != ""
        and _norm(r.get("confidence_label")) != "THIN_SAMPLE"
    ]
    if not rows:
        return "INSUFFICIENT_DATA"
    positive = sum(1 for r in rows if (_as_float(r.get(delta_field)) or 0.0) > 0)
    total = len(rows)
    if positive / total >= 0.6:
        return "SURVIVES"
    if positive / total >= 0.3:
        return "WEAKENS"
    return "COLLAPSES"


def _signal_label(monotonicity: str, provider_survival: str, family_survival: str, spread: Optional[float]) -> str:
    if monotonicity == "INSUFFICIENT_DATA":
        return "INSUFFICIENT_DATA"
    if provider_survival == "COLLAPSES":
        return "PROVIDER_CONFOUNDED"
    if family_survival == "COLLAPSES":
        return "FAMILY_CONFOUNDED"
    if provider_survival == "WEAKENS" or family_survival == "WEAKENS":
        if monotonicity in {"MONOTONIC_POSITIVE", "PARTIAL_POSITIVE"} and spread is not None and spread > 0:
            return "WEAK_SYNCHRONY_SIGNAL"
        return "NO_SYNCHRONY_ACCURACY_LINK"
    if monotonicity == "MONOTONIC_POSITIVE" and spread is not None and spread >= 0.10:
        return "STRONG_SYNCHRONY_ACCURACY_LINK"
    if monotonicity in {"MONOTONIC_POSITIVE", "PARTIAL_POSITIVE"} and spread is not None and spread > 0:
        return "WEAK_SYNCHRONY_SIGNAL"
    return "NO_SYNCHRONY_ACCURACY_LINK"


def _build_summary_rows(audit_rows: Sequence[Dict[str, Any]], generated_ts: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    summary_rows: List[Dict[str, Any]] = []
    global_baseline = _baseline_rate(audit_rows)
    comparable_rows = [r for r in audit_rows if _as_bool(r.get("actual_comparable"))]

    for metric_name in METRIC_BUCKET_FIELDS:
        summary_rows.extend(_bucket_summary_rows(generated_ts, "A_OVERALL_SYNCHRONY_ACCURACY", audit_rows, metric_name))
        summary_rows.extend(_bucket_summary_rows(generated_ts, "B_PROVIDER_CONTROLLED_SYNCHRONY", audit_rows, metric_name, group_key="provider", subgroup_label="provider"))
        summary_rows.extend(_bucket_summary_rows(generated_ts, "C_FAMILY_CONTROLLED_SYNCHRONY", audit_rows, metric_name, group_key="event_family", subgroup_label="event_family"))
        summary_rows.extend(_provider_family_rows(generated_ts, audit_rows, metric_name))
        summary_rows.extend(_bucket_summary_rows(generated_ts, "E_COHORT_CONTROLLED_SYNCHRONY", audit_rows, metric_name, group_key="cohort_id", subgroup_label="cohort_id"))

    ranking_rows: List[Dict[str, Any]] = []
    for metric_name in METRIC_BUCKET_FIELDS:
        overall_rows = [r for r in summary_rows if r["section"] == "A_OVERALL_SYNCHRONY_ACCURACY" and r["metric_name"] == metric_name]
        provider_rows = [r for r in summary_rows if r["section"] == "B_PROVIDER_CONTROLLED_SYNCHRONY" and r["metric_name"] == metric_name]
        family_rows = [r for r in summary_rows if r["section"] == "C_FAMILY_CONTROLLED_SYNCHRONY" and r["metric_name"] == metric_name]
        ordered_overall = [
            r for r in overall_rows if _norm(r.get("bucket")) in BUCKET_ORDER and _norm(r.get("correct_rate")) != ""
        ]
        nonthin_overall = [r for r in ordered_overall if _norm(r.get("confidence_label")) != "THIN_SAMPLE"]
        ranking_pool = nonthin_overall or ordered_overall
        best_row = max(ranking_pool, key=lambda r: _as_float(r.get("correct_rate")) or -1.0, default=None)
        worst_row = min(ranking_pool, key=lambda r: _as_float(r.get("correct_rate")) or 999.0, default=None)
        best_rate = _as_float(best_row.get("correct_rate")) if best_row else None
        worst_rate = _as_float(worst_row.get("correct_rate")) if worst_row else None
        spread = (best_rate - worst_rate) if best_rate is not None and worst_rate is not None else None
        monotonicity = _monotonicity(overall_rows)
        provider_survival = _control_survival(provider_rows, "delta_vs_provider_baseline")
        family_survival = _control_survival(family_rows, "delta_vs_family_baseline")
        signal_label = _signal_label(monotonicity, provider_survival, family_survival, spread)
        ranking_rows.append({
            "generated_ts": generated_ts,
            "section": "F_SIGNAL_RANKING",
            "metric_name": metric_name,
            "bucket": "",
            "provider": "",
            "event_family": "",
            "cohort_id": "",
            "sample_groups": len([r for r in audit_rows if _norm(r.get(metric_name)) not in {"", "MISSING"}]),
            "comparable_rows": len(comparable_rows),
            "correct_count": "",
            "wrong_count": "",
            "correct_rate": "",
            "baseline_correct_rate": _round4(global_baseline),
            "delta_vs_baseline": "",
            "provider_baseline_rate": "",
            "delta_vs_provider_baseline": "",
            "family_baseline_rate": "",
            "delta_vs_family_baseline": "",
            "provider_family_baseline_rate": "",
            "delta_vs_provider_family_baseline": "",
            "cohort_baseline_rate": "",
            "delta_vs_cohort_baseline": "",
            "best_bucket": _norm(best_row.get("bucket")) if best_row else "",
            "best_bucket_correct_rate": _round4(best_rate),
            "worst_bucket": _norm(worst_row.get("bucket")) if worst_row else "",
            "worst_bucket_correct_rate": _round4(worst_rate),
            "spread": _round4(spread),
            "monotonicity_label": monotonicity,
            "provider_control_survival_label": provider_survival,
            "family_control_survival_label": family_survival,
            "overall_signal_label": signal_label,
            "final_interpretation": "",
            "confidence_label": _confidence_label(len(comparable_rows)),
            "notes": "",
        })
    summary_rows.extend(ranking_rows)

    signal_priority = {
        "STRONG_SYNCHRONY_ACCURACY_LINK": 5,
        "WEAK_SYNCHRONY_SIGNAL": 4,
        "NO_SYNCHRONY_ACCURACY_LINK": 3,
        "PROVIDER_CONFOUNDED": 2,
        "FAMILY_CONFOUNDED": 1,
        "INSUFFICIENT_DATA": 0,
    }
    top_metric = max(
        ranking_rows,
        key=lambda r: (signal_priority.get(_norm(r.get("overall_signal_label")), -1), _as_float(r.get("spread")) or -1.0),
        default=None,
    )
    if not ranking_rows or len(comparable_rows) < 20:
        final_interpretation = "INSUFFICIENT_DATA"
    elif top_metric is None:
        final_interpretation = "INSUFFICIENT_DATA"
    else:
        label = _norm(top_metric.get("overall_signal_label"))
        if label == "STRONG_SYNCHRONY_ACCURACY_LINK":
            final_interpretation = "SYNCHRONY_PREDICTS_ACCURACY"
        elif label == "WEAK_SYNCHRONY_SIGNAL":
            final_interpretation = "WEAK_SYNCHRONY_SIGNAL"
        elif label == "PROVIDER_CONFOUNDED":
            final_interpretation = "PROVIDER_CONFOUNDED"
        elif label == "FAMILY_CONFOUNDED":
            final_interpretation = "FAMILY_CONFOUNDED"
        elif label == "NO_SYNCHRONY_ACCURACY_LINK":
            final_interpretation = "NO_SYNCHRONY_ACCURACY_LINK"
        else:
            final_interpretation = "INSUFFICIENT_DATA"

    summary_rows.append({
        "generated_ts": generated_ts,
        "section": "G_FINAL_INTERPRETATION",
        "metric_name": "",
        "bucket": "",
        "provider": "",
        "event_family": "",
        "cohort_id": "",
        "sample_groups": len(audit_rows),
        "comparable_rows": len(comparable_rows),
        "correct_count": sum(1 for r in comparable_rows if _is_correct(r)),
        "wrong_count": sum(1 for r in comparable_rows if not _is_correct(r)),
        "correct_rate": _round4(_safe_rate(sum(1 for r in comparable_rows if _is_correct(r)), len(comparable_rows))),
        "baseline_correct_rate": _round4(global_baseline),
        "delta_vs_baseline": "",
        "provider_baseline_rate": "",
        "delta_vs_provider_baseline": "",
        "family_baseline_rate": "",
        "delta_vs_family_baseline": "",
        "provider_family_baseline_rate": "",
        "delta_vs_provider_family_baseline": "",
        "cohort_baseline_rate": "",
        "delta_vs_cohort_baseline": "",
        "best_bucket": "",
        "best_bucket_correct_rate": "",
        "worst_bucket": "",
        "worst_bucket_correct_rate": "",
        "spread": "",
        "monotonicity_label": "",
        "provider_control_survival_label": "",
        "family_control_survival_label": "",
        "overall_signal_label": _norm(top_metric.get("overall_signal_label")) if top_metric else "",
        "final_interpretation": final_interpretation,
        "confidence_label": _confidence_label(len(comparable_rows)),
        "notes": (
            f"top_metric={_norm(top_metric.get('metric_name')) if top_metric else ''}; "
            "Historical synchrony/accuracy association only."
        ),
    })

    return summary_rows, {
        "global_baseline": global_baseline,
        "final_interpretation": final_interpretation,
        "top_metric": _norm(top_metric.get("metric_name")) if top_metric else "",
        "top_signal_label": _norm(top_metric.get("overall_signal_label")) if top_metric else "",
    }


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


def build_signal_synchrony_accuracy_audit() -> Dict[str, Any]:
    service = build_sheets_service(load_credentials(interactive=False))
    sources = _read_inputs(service)
    generated_ts = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    audit_rows = _build_audit_rows(sources, generated_ts)
    comparable_rows = [r for r in audit_rows if _as_bool(r.get("actual_comparable"))]

    provider_counts = defaultdict(int)
    family_counts = defaultdict(int)
    cohort_counts = defaultdict(int)
    missing_metrics = 0
    for row in audit_rows:
        provider_counts[_norm(row.get("provider"))] += 1
        family_counts[_norm(row.get("event_family"))] += 1
        cohort_counts[_norm(row.get("cohort_id"))] += 1
        if _norm(row.get("missing_metric_flag")):
            missing_metrics += 1

    summary_rows, summary_meta = _build_summary_rows(audit_rows, generated_ts)

    provider_family_counts: Dict[Tuple[str, str], int] = defaultdict(int)
    for row in comparable_rows:
        provider_family_counts[(_norm(row.get("provider")), _norm(row.get("event_family")))] += 1
    for row in audit_rows:
        count = provider_family_counts[(_norm(row.get("provider")), _norm(row.get("event_family")))] if _as_bool(row.get("actual_comparable")) else 0
        row["thin_sample_flag"] = "TRUE" if count < 8 else "FALSE"
        row["confidence_label"] = _confidence_label(count)

    audit_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_AUDIT_SHEET, AUDIT_HEADERS)
    summary_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_AUDIT_SHEET, audit_headers, audit_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, summary_rows)
    registry_result = _upsert_registry_rows(service)

    return {
        "generated_ts": generated_ts,
        "sample_groups": len(audit_rows),
        "comparable_rows": len(comparable_rows),
        "providers_represented": dict(sorted(provider_counts.items())),
        "families_represented": dict(sorted(family_counts.items())),
        "cohorts_represented": dict(sorted(cohort_counts.items())),
        "missing_metrics": missing_metrics,
        "global_baseline": summary_meta["global_baseline"],
        "top_metric": summary_meta["top_metric"],
        "top_signal_label": summary_meta["top_signal_label"],
        "final_interpretation": summary_meta["final_interpretation"],
        "registry": registry_result,
    }


if __name__ == "__main__":
    print(build_signal_synchrony_accuracy_audit())
