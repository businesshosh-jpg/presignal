import sys
from collections import Counter, defaultdict
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


OUTPUT_REPLAY_SHEET = "Signal_Synchrony_Interaction_Replay_Validation"
OUTPUT_SUMMARY_SHEET = "Signal_Synchrony_Interaction_Replay_Summary"

REGISTRY_ROWS = [
    {
        "logical_sheet_id": "SIGNAL_SYNCHRONY_INTERACTION_REPLAY_VALIDATION",
        "physical_sheet_name": OUTPUT_REPLAY_SHEET,
        "workbook": "DIAGNOSTICS",
        "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
        "category": "SIGNAL_SYNCHRONY",
        "lifecycle_state": "ACTIVE",
        "owner_module": "signal_synchrony",
        "participates_in_rebuild": "TRUE",
        "read_only": "FALSE",
        "allow_creation": "FALSE",
        "created_phase": "Signal Synchrony v2B",
        "notes": "Derived-only replay validation for interaction model candidates",
    },
    {
        "logical_sheet_id": "SIGNAL_SYNCHRONY_INTERACTION_REPLAY_SUMMARY",
        "physical_sheet_name": OUTPUT_SUMMARY_SHEET,
        "workbook": "DIAGNOSTICS",
        "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
        "category": "SIGNAL_SYNCHRONY",
        "lifecycle_state": "ACTIVE",
        "owner_module": "signal_synchrony",
        "participates_in_rebuild": "TRUE",
        "read_only": "FALSE",
        "allow_creation": "FALSE",
        "created_phase": "Signal Synchrony v2B",
        "notes": "Derived-only replay summary for interaction model candidates",
    },
]

REPLAY_HEADERS = [
    "generated_ts",
    "replay_validation_id",
    "source_interaction_id",
    "interaction_level",
    "interaction_type",
    "interaction_key",
    "feature_1_name",
    "feature_1_value",
    "feature_2_name",
    "feature_2_value",
    "feature_3_name",
    "feature_3_value",
    "provider",
    "event_family",
    "predictability_bucket",
    "direction_synchrony_bucket",
    "stability_label",
    "recommended_protocol",
    "cohort_bucket",
    "misleading_stability_flag",
    "interaction_label",
    "sample_groups",
    "comparable_rows",
    "correct_count",
    "wrong_count",
    "non_comparable_rows",
    "original_comparable_rows",
    "original_correct_rate",
    "original_wrong_count",
    "original_global_baseline_rate",
    "original_primary_baseline_rate",
    "original_secondary_baseline_rate",
    "original_tertiary_baseline_rate",
    "original_best_component_baseline_rate",
    "original_delta_vs_best_component_baseline",
    "original_delta_vs_global_baseline",
    "time_split_status",
    "discovery_rows",
    "discovery_correct_rate",
    "replay_rows",
    "replay_correct_rate",
    "replay_lift_over_baseline",
    "time_split_label",
    "cohort_split_status",
    "cohort_a_rows",
    "cohort_a_correct_rate",
    "deterministic_rows",
    "deterministic_correct_rate",
    "random_rows",
    "random_correct_rate",
    "cohort_spread",
    "cohort_split_label",
    "provider_family_check_status",
    "provider_family_replay_rows",
    "provider_family_replay_correct_rate",
    "provider_family_replay_lift_over_baseline",
    "provider_family_split_label",
    "sample_depth_label",
    "baseline_lift_persistence_label",
    "risk_rate_persistence_label",
    "misleading_stability_original_rate",
    "misleading_stability_replay_rate",
    "misleading_stability_persistence_label",
    "validation_label",
    "validation_strength_label",
    "validation_direction",
    "replay_reproduces_flag",
    "interpreter_note",
    "learning_model_approved",
    "routing_approved",
    "weighting_approved",
    "calibration_approved",
    "production_approved",
    "notes",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "section",
    "rank",
    "source_sheet_names",
    "source_candidate_counts",
    "validated_signal_candidate_count",
    "validated_risk_candidate_count",
    "reproduced_signal_count",
    "reproduced_risk_count",
    "weak_dependent_count",
    "thin_after_split_count",
    "non_reproduced_count",
    "signal_validation_label_counts",
    "risk_validation_label_counts",
    "strongest_reproduced_signal_slice",
    "strongest_reproduced_risk_slice",
    "final_audit_label",
    "interpretation",
    "governance_statement",
    "notes",
]

INTERACTION_LABELS = {
    "INTERACTION_SIGNAL_CANDIDATE": "signal",
    "INTERACTION_RISK_CANDIDATE": "risk",
}

FEATURE_ORDER = [
    "provider",
    "event_family",
    "predictability_bucket",
    "direction_synchrony_bucket",
    "stability_label",
    "recommended_protocol",
    "cohort_bucket",
    "misleading_stability_flag",
]

SIGNAL_FINAL_LABELS = [
    "REPRODUCES_STRONG",
    "REPRODUCES_WEAK",
    "WINDOW_DEPENDENT",
    "COHORT_DEPENDENT",
    "THIN_AFTER_SPLIT",
    "DOES_NOT_REPRODUCE",
]

RISK_FINAL_LABELS = [
    "RISK_REPRODUCES_STRONG",
    "RISK_REPRODUCES_WEAK",
    "RISK_WINDOW_DEPENDENT",
    "RISK_COHORT_DEPENDENT",
    "RISK_THIN_AFTER_SPLIT",
    "RISK_DOES_NOT_REPRODUCE",
]

COHORT_BUCKETS = ["cohort_a", "deterministic", "random"]
COHORT_ORDER = ["cohort_a", "deterministic", "random", "unknown"]


def _norm(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return str(value).strip()


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _lower(value: Any) -> str:
    return _norm(value).lower()


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
    cleaned = [value for value in values if value is not None]
    if not cleaned:
        return None
    return mean(cleaned)


def _count_string(counter: Counter, order: Sequence[str]) -> str:
    parts: List[str] = []
    for key in order:
        if counter.get(key, 0):
            parts.append(f"{key}:{counter[key]}")
    for key in sorted(counter):
        if key in order or counter.get(key, 0) <= 0:
            continue
        parts.append(f"{key}:{counter[key]}")
    return "|".join(parts)


def _confidence_label(comparable_rows: int) -> str:
    if comparable_rows >= 20:
        return "HIGHER_CONFIDENCE"
    if comparable_rows >= 12:
        return "MEDIUM_CONFIDENCE"
    if comparable_rows >= 8:
        return "LOW_CONFIDENCE"
    return "THIN_SAMPLE"


def _signal_label_rows() -> Dict[str, str]:
    return {"INTERACTION_SIGNAL_CANDIDATE": "signal", "INTERACTION_RISK_CANDIDATE": "risk"}


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


def _feature_value(row: Dict[str, Any], feature_name: str) -> str:
    if feature_name == "cohort_bucket":
        cohort_id = _norm(row.get("cohort_bucket")) or _norm(row.get("cohort_id"))
        if cohort_id.startswith("cohort_a") or "cohort_a" in cohort_id:
            return "cohort_a"
        if "random" in cohort_id:
            return "random"
        if "deterministic" in cohort_id or cohort_id.startswith("cohort_b") or cohort_id.startswith("cohort_c"):
            return "deterministic"
        return "unknown"
    if feature_name == "misleading_stability_flag":
        return "TRUE" if _as_bool(row.get("misleading_stability_flag")) else "FALSE"
    value = row.get(feature_name)
    if feature_name in {"provider"}:
        return _norm(value)
    if feature_name in {"event_family", "predictability_bucket"}:
        return _lower(value)
    if feature_name in {"direction_synchrony_bucket", "stability_label", "recommended_protocol"}:
        return _upper(value)
    return _norm(value)


def _row_matches_candidate(row: Dict[str, Any], candidate: Dict[str, Any]) -> bool:
    for idx in (1, 2, 3):
        feature_name = _norm(candidate.get(f"feature_{idx}_name"))
        feature_value = _norm(candidate.get(f"feature_{idx}_value"))
        if not feature_name or not feature_value:
            continue
        row_value = _feature_value(row, feature_name)
        if feature_name in {"event_family", "predictability_bucket", "cohort_bucket"}:
            feature_value = _lower(feature_value)
        elif feature_name in {"direction_synchrony_bucket", "stability_label", "recommended_protocol", "misleading_stability_flag"}:
            feature_value = _upper(feature_value)
        else:
            feature_value = _norm(feature_value)
        if row_value != feature_value:
            return False
    return True


def _build_release_dt(row: Dict[str, Any]) -> Tuple[str, str]:
    release_ts = _norm(row.get("release_ts"))
    created_ts = _norm(row.get("generated_ts"))
    return release_ts, created_ts


def _read_inputs(service) -> Dict[str, List[Dict[str, Any]]]:
    names = {
        "interaction_audit": "Signal_Synchrony_Interaction_Model_Audit",
        "interaction_summary": "Signal_Synchrony_Interaction_Model_Summary",
        "accuracy": "Signal_Synchrony_Accuracy_Audit",
    }
    return {key: _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet) for key, sheet in names.items()}


def _group_matching_accuracy_rows(
    candidate: Dict[str, Any],
    accuracy_rows: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    matched: List[Dict[str, Any]] = []
    for row in accuracy_rows:
        if _row_matches_candidate(row, candidate):
            matched.append(dict(row))
    return matched


def _split_time(rows: Sequence[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    sortable: List[Tuple[datetime, Dict[str, Any]]] = []
    from datetime import datetime as _dt
    for row in rows:
        ts = _norm(row.get("release_ts")) or _norm(row.get("generated_ts"))
        if not ts:
            continue
        try:
            sortable.append((_dt.fromisoformat(ts.replace("Z", "+00:00")), row))
        except Exception:
            continue
    if len(sortable) < 2:
        return "CHECK_NOT_AVAILABLE", [], []
    sortable.sort(key=lambda item: item[0])
    mid = max(1, len(sortable) // 2)
    discovery = [row for _, row in sortable[:mid]]
    replay = [row for _, row in sortable[mid:]]
    if not replay:
        return "CHECK_NOT_AVAILABLE", discovery, replay
    return "AVAILABLE", discovery, replay


def _split_cohort(rows: Sequence[Dict[str, Any]]) -> Tuple[str, Dict[str, List[Dict[str, Any]]]]:
    by_cohort: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_cohort[_feature_value(row, "cohort_bucket")].append(row)
    active = {key: value for key, value in by_cohort.items() if value}
    if not active:
        return "CHECK_NOT_AVAILABLE", {}
    return "AVAILABLE", active


def _rate_for_rows(rows: Sequence[Dict[str, Any]]) -> Tuple[int, int, Optional[float]]:
    comparable = [row for row in rows if _is_comparable(row)]
    correct = sum(1 for row in comparable if _is_correct(row))
    return len(comparable), correct, _safe_rate(correct, len(comparable))


def _subset_rate(
    rows: Sequence[Dict[str, Any]],
    extra_filter: Optional[Any] = None,
) -> Tuple[int, int, Optional[float]]:
    if extra_filter is not None:
        rows = [row for row in rows if extra_filter(row)]
    return _rate_for_rows(rows)


def _best_component_baseline(candidate: Dict[str, Any]) -> Optional[float]:
    values = []
    for key in [
        "primary_feature_baseline_rate",
        "secondary_feature_baseline_rate",
        "tertiary_feature_baseline_rate",
    ]:
        val = _as_float(candidate.get(key))
        if val is not None:
            values.append(val)
    if not values:
        return None
    return max(values)


def _provider_family_baseline(
    candidate: Dict[str, Any],
    accuracy_rows: Sequence[Dict[str, Any]],
) -> Tuple[int, int, Optional[float]]:
    provider = _norm(candidate.get("provider"))
    family = _lower(candidate.get("event_family"))
    if not provider or not family:
        return 0, 0, None
    matched = [
        row for row in accuracy_rows
        if _norm(row.get("provider")) == provider and _lower(row.get("event_family")) == family
    ]
    return _rate_for_rows(matched)


def _split_metrics(rows: Sequence[Dict[str, Any]]) -> Dict[str, Tuple[int, int, Optional[float]]]:
    metrics: Dict[str, Tuple[int, int, Optional[float]]] = {}
    for bucket in COHORT_BUCKETS:
        bucket_rows = [row for row in rows if _feature_value(row, "cohort_bucket") == bucket]
        metrics[bucket] = _rate_for_rows(bucket_rows)
    return metrics


def _persistence_label(
    original_rate: Optional[float],
    replay_rate: Optional[float],
    compare_rate: Optional[float],
    minimum_replay_rows: int,
    preferred_replay_rows: int,
    threshold: float,
) -> str:
    if original_rate is None or replay_rate is None:
        return "CHECK_NOT_AVAILABLE"
    if minimum_replay_rows < 5 or compare_rate is None:
        return "THIN_AFTER_SPLIT"
    if original_rate < threshold and compare_rate < threshold:
        return "DOES_NOT_REPRODUCE"
    if replay_rate >= max(threshold, original_rate - 0.03):
        return "REPRODUCES_STRONG" if minimum_replay_rows >= preferred_replay_rows and replay_rate >= original_rate - 0.02 else "REPRODUCES_WEAK"
    if compare_rate >= threshold:
        return "REPRODUCES_WEAK"
    return "DOES_NOT_REPRODUCE"


def _risk_persistence_label(
    original_rate: Optional[float],
    replay_rate: Optional[float],
    compare_rate: Optional[float],
    minimum_replay_rows: int,
    preferred_replay_rows: int,
    threshold: float,
) -> str:
    if original_rate is None or replay_rate is None:
        return "CHECK_NOT_AVAILABLE"
    if minimum_replay_rows < 5 or compare_rate is None:
        return "RISK_THIN_AFTER_SPLIT"
    if original_rate >= threshold and replay_rate >= max(threshold, original_rate - 0.05):
        return "RISK_REPRODUCES_STRONG" if minimum_replay_rows >= preferred_replay_rows and replay_rate >= original_rate - 0.02 else "RISK_REPRODUCES_WEAK"
    if compare_rate >= threshold:
        return "RISK_REPRODUCES_WEAK"
    if replay_rate < threshold and original_rate >= threshold:
        return "RISK_DOES_NOT_REPRODUCE"
    return "RISK_DOES_NOT_REPRODUCE"


def _validation_label_from_row(
    candidate: Dict[str, Any],
    original_rows: Sequence[Dict[str, Any]],
    discovery_rows: Sequence[Dict[str, Any]],
    replay_rows: Sequence[Dict[str, Any]],
    cohort_metrics: Dict[str, Tuple[int, int, Optional[float]]],
) -> Tuple[str, str, str, str, str, str, str, str, str, str, str, str, str, str]:
    original_comparable = len([row for row in original_rows if _is_comparable(row)])
    original_correct = sum(1 for row in original_rows if _is_comparable(row) and _is_correct(row))
    original_correct_rate = _safe_rate(original_correct, original_comparable)
    original_wrong = original_comparable - original_correct
    global_baseline = _as_float(candidate.get("global_baseline_rate"))
    primary_baseline = _as_float(candidate.get("primary_feature_baseline_rate"))
    secondary_baseline = _as_float(candidate.get("secondary_feature_baseline_rate"))
    tertiary_baseline = _as_float(candidate.get("tertiary_feature_baseline_rate"))
    best_component = _best_component_baseline(candidate)
    original_delta_best = (
        original_correct_rate - best_component
        if original_correct_rate is not None and best_component is not None
        else None
    )
    original_delta_global = (
        original_correct_rate - global_baseline
        if original_correct_rate is not None and global_baseline is not None
        else None
    )
    original_misleading = _as_float(candidate.get("misleading_stability_rate"))

    discovery_comparable, discovery_correct, discovery_rate = _rate_for_rows(discovery_rows)
    replay_comparable, replay_correct, replay_rate = _rate_for_rows(replay_rows)

    min_replay_rows = min(
        [count for count, _, _ in cohort_metrics.values() if count > 0] + [replay_comparable] if replay_comparable > 0 else [0]
    ) if cohort_metrics else 0
    replay_counts = [count for count, _, _ in cohort_metrics.values() if count > 0]
    min_replay_rows = min(replay_counts) if replay_counts else replay_comparable
    preferred_replay_rows = 10
    minimum_replay_rows = 5

    cohort_rates = {bucket: rate for bucket, (_, _, rate) in cohort_metrics.items() if rate is not None}
    if cohort_rates:
        best_cohort = max(cohort_rates, key=lambda key: (cohort_rates[key], key))
        worst_cohort = min(cohort_rates, key=lambda key: (cohort_rates[key], key))
        cohort_spread = max(cohort_rates.values()) - min(cohort_rates.values()) if len(cohort_rates) >= 2 else None
    else:
        best_cohort = ""
        worst_cohort = ""
        cohort_spread = None

    time_available = "AVAILABLE" if discovery_rows and replay_rows else "CHECK_NOT_AVAILABLE"
    cohort_available = "AVAILABLE" if cohort_rates else "CHECK_NOT_AVAILABLE"
    provider_family_rows, provider_family_correct, provider_family_rate = _provider_family_baseline(candidate, original_rows)
    provider_family_check_status = "AVAILABLE" if provider_family_rate is not None else "CHECK_NOT_AVAILABLE"

    if candidate.get("interaction_label") == "INTERACTION_SIGNAL_CANDIDATE":
        replay_lift = replay_rate - provider_family_rate if replay_rate is not None and provider_family_rate is not None else None
        baseline_lift_persistence = (
            "REPRODUCES_STRONG"
            if replay_lift is not None and original_delta_best is not None and replay_lift >= max(0.06, original_delta_best - 0.03)
            else "REPRODUCES_WEAK"
            if replay_lift is not None and replay_lift > 0
            else "DOES_NOT_REPRODUCE"
        )
        risk_rate_persistence = "CHECK_NOT_AVAILABLE"
        misleading_original_rate = original_misleading
        misleading_replay_rate = _safe_mean([
            _as_float(row.get("misleading_stability_rate")) for row in replay_rows
            if _as_float(row.get("misleading_stability_rate")) is not None
        ])
        misleading_label = (
            "RISK_REPRODUCES_STRONG"
            if misleading_replay_rate is not None and original_misleading is not None and misleading_replay_rate >= max(0.40, original_misleading - 0.05)
            else "RISK_REPRODUCES_WEAK"
            if misleading_replay_rate is not None and original_misleading is not None and misleading_replay_rate >= original_misleading - 0.15
            else "RISK_DOES_NOT_REPRODUCE"
        )
        if len(original_rows) < 10:
            validation_label = "THIN_AFTER_SPLIT"
        elif time_available == "CHECK_NOT_AVAILABLE" and cohort_available == "CHECK_NOT_AVAILABLE":
            validation_label = "THIN_AFTER_SPLIT"
        elif replay_lift is not None and replay_lift >= 0.10 and original_delta_best is not None and original_delta_best >= 0.10 and misleading_label != "RISK_REPRODUCES_STRONG":
            validation_label = "REPRODUCES_STRONG"
        elif replay_lift is not None and replay_lift > 0:
            if replay_rate is not None and provider_family_rate is not None and replay_rate < provider_family_rate + 0.03:
                validation_label = "WINDOW_DEPENDENT"
            elif cohort_spread is not None and cohort_spread >= 0.25:
                validation_label = "COHORT_DEPENDENT"
            else:
                validation_label = "REPRODUCES_WEAK"
        elif replay_rate is not None and provider_family_rate is not None and replay_rate < provider_family_rate:
            validation_label = "WINDOW_DEPENDENT"
        else:
            validation_label = "DOES_NOT_REPRODUCE"
        validation_strength = "STRONG" if validation_label == "REPRODUCES_STRONG" else "MODERATE" if validation_label == "REPRODUCES_WEAK" else "WEAK"
        validation_direction = "POSITIVE" if validation_label in {"REPRODUCES_STRONG", "REPRODUCES_WEAK"} else "NEGATIVE"
        replay_reproduces_flag = "TRUE" if validation_label in {"REPRODUCES_STRONG", "REPRODUCES_WEAK"} else "FALSE"
        return (
            _round4(original_correct_rate),
            int(original_wrong),
            _round4(global_baseline),
            _round4(primary_baseline),
            _round4(secondary_baseline),
            _round4(tertiary_baseline),
            _round4(best_component),
            _round4(original_delta_best),
            _round4(original_delta_global),
            time_available,
            int(discovery_comparable),
            _round4(discovery_rate),
            int(replay_comparable),
            _round4(replay_rate),
            _round4(replay_rate - provider_family_rate if replay_rate is not None and provider_family_rate is not None else None),
        )

    return (
        _round4(original_correct_rate),
        int(original_wrong),
        _round4(global_baseline),
        _round4(primary_baseline),
        _round4(secondary_baseline),
        _round4(tertiary_baseline),
        _round4(best_component),
        _round4(original_delta_best),
        _round4(original_delta_global),
        time_available,
        int(discovery_comparable),
        _round4(discovery_rate),
        int(replay_comparable),
        _round4(replay_rate),
        _round4(replay_rate - provider_family_rate if replay_rate is not None and provider_family_rate is not None else None),
    )


def _build_replay_row(
    generated_ts: str,
    candidate: Dict[str, Any],
    accuracy_rows: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    matched_rows = _group_matching_accuracy_rows(candidate, accuracy_rows)
    comparable_rows = [row for row in matched_rows if _is_comparable(row)]
    signal_or_risk = candidate.get("interaction_label")
    original_comparable_rows = int(_as_float(candidate.get("comparable_rows")) or 0)
    original_correct_rate = _as_float(candidate.get("correct_rate"))
    original_wrong_count = int(_as_float(candidate.get("wrong_count")) or 0)
    global_baseline_rate = _as_float(candidate.get("global_baseline_rate"))
    primary_baseline = _as_float(candidate.get("primary_feature_baseline_rate"))
    secondary_baseline = _as_float(candidate.get("secondary_feature_baseline_rate"))
    tertiary_baseline = _as_float(candidate.get("tertiary_feature_baseline_rate"))
    best_component = _best_component_baseline(candidate)
    original_delta_best = _as_float(candidate.get("delta_vs_best_component_baseline"))
    original_delta_global = _as_float(candidate.get("delta_vs_global_baseline"))
    sample_groups = len({ _norm(row.get("sample_group_id")) for row in matched_rows if _norm(row.get("sample_group_id")) })
    correct_count = sum(1 for row in comparable_rows if _is_correct(row))
    wrong_count = len(comparable_rows) - correct_count
    comparable_count = len(comparable_rows)
    non_comparable_rows = len(matched_rows) - comparable_count
    confidence_label = _confidence_label(comparable_count)

    time_status, discovery_rows, replay_rows = _split_time(comparable_rows)
    discovery_comparable, discovery_correct, discovery_rate = _rate_for_rows(discovery_rows)
    replay_comparable, replay_correct, replay_rate = _rate_for_rows(replay_rows)
    if time_status == "CHECK_NOT_AVAILABLE":
        time_split_label = "CHECK_NOT_AVAILABLE"
    elif replay_comparable < 5 or discovery_comparable < 5:
        time_split_label = "THIN_AFTER_SPLIT"
    else:
        replay_lift = replay_rate - best_component if replay_rate is not None and best_component is not None else None
        if signal_or_risk == "INTERACTION_SIGNAL_CANDIDATE":
            if replay_lift is not None and replay_lift >= 0.10:
                time_split_label = "REPRODUCES_STRONG"
            elif replay_lift is not None and replay_lift > 0:
                time_split_label = "REPRODUCES_WEAK"
            elif original_delta_best is not None and original_delta_best > 0 and replay_lift is not None and replay_lift <= 0:
                time_split_label = "WINDOW_DEPENDENT"
            else:
                time_split_label = "DOES_NOT_REPRODUCE"
        else:
            if candidate.get("misleading_stability_flag") == "TRUE":
                orig_mis = _as_float(candidate.get("misleading_stability_rate"))
                replay_mis = _safe_mean([_as_float(row.get("misleading_stability_rate")) for row in replay_rows])
                if replay_mis is not None and orig_mis is not None and replay_mis >= max(0.40, orig_mis - 0.05):
                    time_split_label = "RISK_REPRODUCES_STRONG"
                elif replay_mis is not None and orig_mis is not None and replay_mis >= orig_mis - 0.15:
                    time_split_label = "RISK_REPRODUCES_WEAK"
                elif orig_mis is not None and replay_mis is not None and orig_mis >= 0.40 and replay_mis < orig_mis - 0.15:
                    time_split_label = "RISK_WINDOW_DEPENDENT"
                else:
                    time_split_label = "RISK_DOES_NOT_REPRODUCE"
            else:
                time_split_label = "RISK_DOES_NOT_REPRODUCE"

    cohort_status, cohort_groups = _split_cohort(comparable_rows)
    cohort_metrics = {bucket: _rate_for_rows(bucket_rows) for bucket, bucket_rows in cohort_groups.items()}
    cohort_a_rows, cohort_a_correct, cohort_a_rate = cohort_metrics.get("cohort_a", (0, 0, None))
    deterministic_rows, deterministic_correct, deterministic_rate = cohort_metrics.get("deterministic", (0, 0, None))
    random_rows, random_correct, random_rate = cohort_metrics.get("random", (0, 0, None))
    valid_cohort_rates = {k: v for k, (_, _, v) in cohort_metrics.items() if v is not None}
    if len(valid_cohort_rates) >= 2:
        cohort_spread = max(valid_cohort_rates.values()) - min(valid_cohort_rates.values())
    else:
        cohort_spread = None
    if cohort_status == "CHECK_NOT_AVAILABLE":
        cohort_split_label = "CHECK_NOT_AVAILABLE"
    elif min([count for count, _, _ in cohort_metrics.values()] + [0]) < 5:
        cohort_split_label = "THIN_AFTER_SPLIT"
    else:
        if signal_or_risk == "INTERACTION_SIGNAL_CANDIDATE":
            if cohort_spread is not None and cohort_spread >= 0.25:
                cohort_split_label = "COHORT_DEPENDENT"
            elif any(rate is not None and rate >= (best_component or 0) + 0.06 for rate in valid_cohort_rates.values()):
                cohort_split_label = "REPRODUCES_STRONG" if len(valid_cohort_rates) >= 2 else "REPRODUCES_WEAK"
            elif any(rate is not None and rate > (best_component or 0) for rate in valid_cohort_rates.values()):
                cohort_split_label = "REPRODUCES_WEAK"
            else:
                cohort_split_label = "DOES_NOT_REPRODUCE"
        else:
            orig_mis = _as_float(candidate.get("misleading_stability_rate"))
            if orig_mis is not None and any(rate is not None and rate >= max(0.40, orig_mis - 0.05) for rate in valid_cohort_rates.values()):
                cohort_split_label = "RISK_REPRODUCES_STRONG"
            elif orig_mis is not None and any(rate is not None and rate >= orig_mis - 0.15 for rate in valid_cohort_rates.values()):
                cohort_split_label = "RISK_REPRODUCES_WEAK"
            elif cohort_spread is not None and cohort_spread >= 0.25:
                cohort_split_label = "RISK_COHORT_DEPENDENT"
            else:
                cohort_split_label = "RISK_DOES_NOT_REPRODUCE"

    provider_family_status = "AVAILABLE" if _norm(candidate.get("provider")) and _norm(candidate.get("event_family")) else "CHECK_NOT_AVAILABLE"
    provider_family_rows = [
        row for row in candidate.get("_accuracy_rows", [])
        if _norm(row.get("provider")) == _norm(candidate.get("provider")) and _lower(row.get("event_family")) == _lower(candidate.get("event_family"))
    ]
    provider_family_replay_rows, provider_family_replay_correct, provider_family_replay_rate = _rate_for_rows(provider_family_rows)
    provider_family_replay_lift = (
        provider_family_replay_rate - best_component
        if provider_family_replay_rate is not None and best_component is not None
        else None
    )
    provider_family_split_label = "CHECK_NOT_AVAILABLE"
    if provider_family_status == "AVAILABLE":
        if provider_family_replay_rows < 5:
            provider_family_split_label = "THIN_AFTER_SPLIT"
        elif signal_or_risk == "INTERACTION_SIGNAL_CANDIDATE":
            if provider_family_replay_lift is not None and provider_family_replay_lift >= 0.10:
                provider_family_split_label = "REPRODUCES_STRONG"
            elif provider_family_replay_lift is not None and provider_family_replay_lift > 0:
                provider_family_split_label = "REPRODUCES_WEAK"
            else:
                provider_family_split_label = "DOES_NOT_REPRODUCE"
        else:
            orig_mis = _as_float(candidate.get("misleading_stability_rate"))
            if orig_mis is not None and _as_float(candidate.get("misleading_stability_rate")) is not None:
                provider_family_split_label = (
                    "RISK_REPRODUCES_STRONG"
                    if provider_family_replay_rate is not None and provider_family_replay_rate >= max(0.40, orig_mis - 0.05)
                    else "RISK_REPRODUCES_WEAK"
                    if provider_family_replay_rate is not None and provider_family_replay_rate >= orig_mis - 0.15
                    else "RISK_DOES_NOT_REPRODUCE"
                )
            else:
                provider_family_split_label = "RISK_DOES_NOT_REPRODUCE"

    if comparable_count < 10:
        sample_depth_label = "THIN_AFTER_SPLIT"
    elif comparable_count >= 20:
        sample_depth_label = "STRONG"
    else:
        sample_depth_label = "OK"

    original_misleading = _as_float(candidate.get("misleading_stability_rate"))
    replay_misleading = _safe_mean([_as_float(row.get("misleading_stability_rate")) for row in comparable_rows])
    if signal_or_risk == "INTERACTION_SIGNAL_CANDIDATE":
        baseline_lift_persistence = (
            "REPRODUCES_STRONG"
            if provider_family_replay_lift is not None and original_delta_best is not None and provider_family_replay_lift >= max(0.10, original_delta_best - 0.03)
            else "REPRODUCES_WEAK"
            if provider_family_replay_lift is not None and provider_family_replay_lift > 0
            else "DOES_NOT_REPRODUCE"
        )
        risk_rate_persistence = "CHECK_NOT_AVAILABLE"
        misleading_persistence = (
            "RISK_REPRODUCES_STRONG"
            if replay_misleading is not None and original_misleading is not None and replay_misleading >= max(0.40, original_misleading - 0.05)
            else "RISK_REPRODUCES_WEAK"
            if replay_misleading is not None and original_misleading is not None and replay_misleading >= original_misleading - 0.15
            else "RISK_DOES_NOT_REPRODUCE"
        )
    else:
        baseline_lift_persistence = "CHECK_NOT_AVAILABLE"
        if replay_misleading is not None and original_misleading is not None and replay_misleading >= max(0.40, original_misleading - 0.05):
            risk_rate_persistence = "RISK_REPRODUCES_STRONG"
        elif replay_misleading is not None and original_misleading is not None and replay_misleading >= original_misleading - 0.15:
            risk_rate_persistence = "RISK_REPRODUCES_WEAK"
        else:
            risk_rate_persistence = "RISK_DOES_NOT_REPRODUCE"
        misleading_persistence = risk_rate_persistence

    if signal_or_risk == "INTERACTION_SIGNAL_CANDIDATE":
        if sample_depth_label == "THIN_AFTER_SPLIT" or time_split_label == "THIN_AFTER_SPLIT" or cohort_split_label == "THIN_AFTER_SPLIT" or provider_family_split_label == "THIN_AFTER_SPLIT":
            validation_label = "THIN_AFTER_SPLIT"
        elif time_split_label == "WINDOW_DEPENDENT":
            validation_label = "WINDOW_DEPENDENT"
        elif cohort_split_label == "COHORT_DEPENDENT":
            validation_label = "COHORT_DEPENDENT"
        elif any(label == "REPRODUCES_STRONG" for label in [time_split_label, cohort_split_label, provider_family_split_label, baseline_lift_persistence]):
            validation_label = "REPRODUCES_STRONG" if any(label == "REPRODUCES_STRONG" for label in [time_split_label, cohort_split_label, provider_family_split_label, baseline_lift_persistence]) and original_delta_best is not None and original_delta_best >= 0.10 else "REPRODUCES_WEAK"
        elif all(label == "DOES_NOT_REPRODUCE" for label in [time_split_label, cohort_split_label, provider_family_split_label, baseline_lift_persistence]):
            validation_label = "DOES_NOT_REPRODUCE"
        else:
            validation_label = "REPRODUCES_WEAK"
        if validation_label == "REPRODUCES_STRONG":
            validation_strength = "STRONG"
        elif validation_label == "REPRODUCES_WEAK":
            validation_strength = "MODERATE"
        elif validation_label == "THIN_AFTER_SPLIT":
            validation_strength = "THIN"
        else:
            validation_strength = "WEAK"
        validation_direction = "POSITIVE" if validation_label in {"REPRODUCES_STRONG", "REPRODUCES_WEAK"} else "NEGATIVE"
        replay_reproduces_flag = "TRUE" if validation_label in {"REPRODUCES_STRONG", "REPRODUCES_WEAK"} else "FALSE"
    else:
        if sample_depth_label == "THIN_AFTER_SPLIT" or time_split_label == "RISK_THIN_AFTER_SPLIT" or cohort_split_label == "RISK_THIN_AFTER_SPLIT" or provider_family_split_label == "THIN_AFTER_SPLIT":
            validation_label = "RISK_THIN_AFTER_SPLIT"
        elif time_split_label == "RISK_WINDOW_DEPENDENT":
            validation_label = "RISK_WINDOW_DEPENDENT"
        elif cohort_split_label == "RISK_COHORT_DEPENDENT":
            validation_label = "RISK_COHORT_DEPENDENT"
        elif any(label == "RISK_REPRODUCES_STRONG" for label in [time_split_label, cohort_split_label, provider_family_split_label, risk_rate_persistence, misleading_persistence]):
            validation_label = "RISK_REPRODUCES_STRONG"
        elif any(label == "RISK_REPRODUCES_WEAK" for label in [time_split_label, cohort_split_label, provider_family_split_label, risk_rate_persistence, misleading_persistence]):
            validation_label = "RISK_REPRODUCES_WEAK"
        else:
            validation_label = "RISK_DOES_NOT_REPRODUCE"
        if validation_label == "RISK_REPRODUCES_STRONG":
            validation_strength = "STRONG"
        elif validation_label == "RISK_REPRODUCES_WEAK":
            validation_strength = "MODERATE"
        elif validation_label == "RISK_THIN_AFTER_SPLIT":
            validation_strength = "THIN"
        else:
            validation_strength = "WEAK"
        validation_direction = "NEGATIVE"
        replay_reproduces_flag = "TRUE" if validation_label in {"RISK_REPRODUCES_STRONG", "RISK_REPRODUCES_WEAK"} else "FALSE"

    interpretation = (
        f"time={time_split_label}; cohort={cohort_split_label}; provider_family={provider_family_split_label}; "
        f"baseline={baseline_lift_persistence}; risk={risk_rate_persistence}; mislead={misleading_persistence}"
    )

    return {
        "generated_ts": generated_ts,
        "replay_validation_id": "interaction_replay_v2b",
        "source_interaction_id": _norm(candidate.get("interaction_id")),
        "interaction_level": _norm(candidate.get("interaction_level")),
        "interaction_type": _norm(candidate.get("interaction_type")),
        "interaction_key": _norm(candidate.get("interaction_key")),
        "feature_1_name": _norm(candidate.get("feature_1_name")),
        "feature_1_value": _norm(candidate.get("feature_1_value")),
        "feature_2_name": _norm(candidate.get("feature_2_name")),
        "feature_2_value": _norm(candidate.get("feature_2_value")),
        "feature_3_name": _norm(candidate.get("feature_3_name")),
        "feature_3_value": _norm(candidate.get("feature_3_value")),
        "provider": _norm(candidate.get("provider")),
        "event_family": _norm(candidate.get("event_family")),
        "predictability_bucket": _norm(candidate.get("predictability_bucket")),
        "direction_synchrony_bucket": _norm(candidate.get("direction_synchrony_bucket")),
        "stability_label": _norm(candidate.get("stability_label")),
        "recommended_protocol": _norm(candidate.get("recommended_protocol")),
        "cohort_bucket": _norm(candidate.get("cohort_bucket")),
        "misleading_stability_flag": _norm(candidate.get("misleading_stability_flag")),
        "interaction_label": _norm(candidate.get("interaction_label")),
        "sample_groups": sample_groups,
        "comparable_rows": comparable_count,
        "correct_count": correct_count,
        "wrong_count": wrong_count,
        "non_comparable_rows": non_comparable_rows,
        "original_comparable_rows": original_comparable_rows,
        "original_correct_rate": original_correct_rate,
        "original_wrong_count": original_wrong_count,
        "original_global_baseline_rate": global_baseline_rate,
        "original_primary_baseline_rate": primary_baseline,
        "original_secondary_baseline_rate": secondary_baseline,
        "original_tertiary_baseline_rate": tertiary_baseline,
        "original_best_component_baseline_rate": best_component,
        "original_delta_vs_best_component_baseline": original_delta_best,
        "original_delta_vs_global_baseline": original_delta_global,
        "time_split_status": time_status,
        "discovery_rows": discovery_comparable,
        "discovery_correct_rate": discovery_rate,
        "replay_rows": replay_comparable,
        "replay_correct_rate": replay_rate,
        "replay_lift_over_baseline": _round4(replay_rate - best_component if replay_rate is not None and best_component is not None else None),
        "time_split_label": time_split_label,
        "cohort_split_status": cohort_status,
        "cohort_a_rows": cohort_a_rows,
        "cohort_a_correct_rate": cohort_a_rate,
        "deterministic_rows": deterministic_rows,
        "deterministic_correct_rate": deterministic_rate,
        "random_rows": random_rows,
        "random_correct_rate": random_rate,
        "cohort_spread": _round4(cohort_spread),
        "cohort_split_label": cohort_split_label,
        "provider_family_check_status": provider_family_status,
        "provider_family_replay_rows": provider_family_replay_rows,
        "provider_family_replay_correct_rate": provider_family_replay_rate,
        "provider_family_replay_lift_over_baseline": _round4(provider_family_replay_lift),
        "provider_family_split_label": provider_family_split_label,
        "sample_depth_label": sample_depth_label,
        "baseline_lift_persistence_label": baseline_lift_persistence,
        "risk_rate_persistence_label": risk_rate_persistence,
        "misleading_stability_original_rate": original_misleading,
        "misleading_stability_replay_rate": replay_misleading,
        "misleading_stability_persistence_label": misleading_persistence,
        "validation_label": validation_label,
        "validation_strength_label": validation_strength,
        "validation_direction": validation_direction,
        "replay_reproduces_flag": replay_reproduces_flag,
        "interpreter_note": interpretation,
        "learning_model_approved": "FALSE",
        "routing_approved": "FALSE",
        "weighting_approved": "FALSE",
        "calibration_approved": "FALSE",
        "production_approved": "FALSE",
        "notes": "Derived-only replay validation of interaction model candidate reproducibility.",
    }


def _build_replay_rows(
    sources: Dict[str, List[Dict[str, Any]]],
    generated_ts: str,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    interaction_rows = sources["interaction_audit"]
    accuracy_rows = sources["accuracy"]
    candidate_rows = [
        row for row in interaction_rows
        if _norm(row.get("interaction_label")) in INTERACTION_LABELS
    ]

    replay_rows: List[Dict[str, Any]] = []
    for candidate in candidate_rows:
        enriched = dict(candidate)
        enriched["_accuracy_rows"] = accuracy_rows
        replay_rows.append(_build_replay_row(generated_ts, enriched, accuracy_rows))

    summary_context = {
        "interaction_rows_read": len(interaction_rows),
        "candidate_rows": len(candidate_rows),
        "signal_candidates": sum(1 for row in candidate_rows if _norm(row.get("interaction_label")) == "INTERACTION_SIGNAL_CANDIDATE"),
        "risk_candidates": sum(1 for row in candidate_rows if _norm(row.get("interaction_label")) == "INTERACTION_RISK_CANDIDATE"),
    }
    return replay_rows, summary_context


def _build_summary_rows(
    replay_rows: Sequence[Dict[str, Any]],
    context: Dict[str, Any],
    generated_ts: str,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    signal_rows = [row for row in replay_rows if row["interaction_label"] == "INTERACTION_SIGNAL_CANDIDATE"]
    risk_rows = [row for row in replay_rows if row["interaction_label"] == "INTERACTION_RISK_CANDIDATE"]
    signal_counts = Counter(row["validation_label"] for row in signal_rows)
    risk_counts = Counter(row["validation_label"] for row in risk_rows)
    reproduced_signal_count = sum(1 for row in signal_rows if row["validation_label"] in {"REPRODUCES_STRONG", "REPRODUCES_WEAK"})
    reproduced_risk_count = sum(1 for row in risk_rows if row["validation_label"] in {"RISK_REPRODUCES_STRONG", "RISK_REPRODUCES_WEAK"})
    thin_count = sum(1 for row in replay_rows if "THIN_AFTER_SPLIT" in _norm(row.get("validation_label")))
    dependent_count = sum(1 for row in replay_rows if _norm(row.get("validation_label")) in {"WINDOW_DEPENDENT", "COHORT_DEPENDENT", "RISK_WINDOW_DEPENDENT", "RISK_COHORT_DEPENDENT"})
    non_reproduced_count = sum(
        1
        for row in replay_rows
        if _norm(row.get("validation_label")) in {"DOES_NOT_REPRODUCE", "RISK_DOES_NOT_REPRODUCE"}
    )
    strong_signal = next((row for row in sorted(signal_rows, key=lambda r: (_as_float(r.get("original_delta_vs_best_component_baseline")) or 0.0, _as_float(r.get("replay_lift_over_baseline")) or 0.0), reverse=True) if row["validation_label"] == "REPRODUCES_STRONG"), {})
    strong_risk = next((row for row in sorted(risk_rows, key=lambda r: (_as_float(r.get("misleading_stability_replay_rate")) or 0.0, _as_float(r.get("replay_correct_rate")) or 0.0), reverse=True) if row["validation_label"] == "RISK_REPRODUCES_STRONG"), {})

    if reproduced_signal_count > 0 and reproduced_risk_count > 0:
        final_label = "REPLAY_SUPPORTS_SIGNAL_AND_RISK_MODELING"
        interpretation = "At least one positive interaction signal and one interaction risk pattern reproduced under replay checks."
    elif reproduced_risk_count > 0 and reproduced_signal_count == 0:
        final_label = "REPLAY_SUPPORTS_RISK_MODELING_ONLY"
        interpretation = "Risk interactions reproduced more clearly than positive signal interactions."
    elif reproduced_signal_count == 0 and reproduced_risk_count == 0 and dependent_count > 0:
        final_label = "REPLAY_SUPPORTS_MONITORING_ONLY"
        interpretation = "Interaction slices are more useful as monitoring or dependency flags than as durable predictive signals."
    elif reproduced_signal_count == 0 and reproduced_risk_count == 0 and thin_count > 0:
        final_label = "REPLAY_INSUFFICIENT_DATA"
        interpretation = "Too many interaction slices thin out after replay splits to support a stable conclusion."
    else:
        final_label = "REPLAY_REJECTS_INTERACTION_VALUE"
        interpretation = "The interaction model does not show durable replay support for either signal or risk detection."

    rows.append(
        {
            "generated_ts": generated_ts,
            "section": "A_OVERALL_SUMMARY",
            "rank": 0,
            "source_sheet_names": "Signal_Synchrony_Interaction_Model_Audit|Signal_Synchrony_Interaction_Model_Summary|Signal_Synchrony_Accuracy_Audit",
            "source_candidate_counts": f"signal:{context['signal_candidates']}|risk:{context['risk_candidates']}",
            "validated_signal_candidate_count": context["signal_candidates"],
            "validated_risk_candidate_count": context["risk_candidates"],
            "reproduced_signal_count": reproduced_signal_count,
            "reproduced_risk_count": reproduced_risk_count,
            "weak_dependent_count": dependent_count,
            "thin_after_split_count": thin_count,
            "non_reproduced_count": non_reproduced_count,
            "signal_validation_label_counts": _count_string(signal_counts, SIGNAL_FINAL_LABELS),
            "risk_validation_label_counts": _count_string(risk_counts, RISK_FINAL_LABELS),
            "strongest_reproduced_signal_slice": strong_signal.get("source_interaction_id", ""),
            "strongest_reproduced_risk_slice": strong_risk.get("source_interaction_id", ""),
            "final_audit_label": final_label,
            "interpretation": interpretation,
            "governance_statement": "Derived-only replay validation. No routing, weighting, calibration, or production behavior is approved.",
            "notes": "Reproduction is only counted when the interaction survives split checks without becoming thin-after-split.",
        }
    )
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
    by_id = {_norm(row.get("logical_sheet_id")).upper(): i + 2 for i, row in enumerate(rows)}
    existing_by_id = {_norm(row.get("logical_sheet_id")).upper(): row for row in rows}
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
            updates.append(
                {
                    "range": f"'{REGISTRY_SHEET}'!A{row_number}:{_column_letter(len(existing_headers))}{row_number}",
                    "values": [values],
                }
            )
        else:
            appended += 1
            target_row = len(rows) + appended
            updates.append(
                {
                    "range": f"'{REGISTRY_SHEET}'!A{target_row}:{_column_letter(len(existing_headers))}{target_row}",
                    "values": [values],
                }
            )
    if updates:
        batch_update_values(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, updates)
    return {"updated": len(REGISTRY_ROWS) - appended, "appended": appended}


def build_signal_synchrony_interaction_replay_validation() -> Dict[str, Any]:
    service = build_sheets_service(load_credentials(interactive=False))
    sources = _read_inputs(service)
    generated_ts = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    replay_rows, context = _build_replay_rows(sources, generated_ts)
    summary_rows = _build_summary_rows(replay_rows, context, generated_ts)

    replay_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_REPLAY_SHEET, REPLAY_HEADERS)
    summary_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_REPLAY_SHEET, replay_headers, replay_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, summary_rows)

    registry_result = _upsert_registry_rows(service)
    final_row = next((row for row in summary_rows if row.get("section") == "A_OVERALL_SUMMARY"), {})
    return {
        "generated_ts": generated_ts,
        "source_rows_read": context["interaction_rows_read"],
        "validated_signal_candidate_count": context["signal_candidates"],
        "validated_risk_candidate_count": context["risk_candidates"],
        "reproduced_signal_count": final_row.get("reproduced_signal_count", 0),
        "reproduced_risk_count": final_row.get("reproduced_risk_count", 0),
        "final_audit_label": final_row.get("final_audit_label", ""),
        "registry_result": registry_result,
    }


def main() -> None:
    print(build_signal_synchrony_interaction_replay_validation())


if __name__ == "__main__":
    main()
