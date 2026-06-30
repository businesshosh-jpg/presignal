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
from automation.build_signal_synchrony_direction_robustness import _cohort_bucket
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials


OUTPUT_AUDIT_SHEET = "Signal_Synchrony_Interaction_Model_Audit"
OUTPUT_SUMMARY_SHEET = "Signal_Synchrony_Interaction_Model_Summary"

REGISTRY_ROWS = [
    {
        "logical_sheet_id": "SIGNAL_SYNCHRONY_INTERACTION_MODEL_AUDIT",
        "physical_sheet_name": OUTPUT_AUDIT_SHEET,
        "workbook": "DIAGNOSTICS",
        "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
        "category": "SIGNAL_SYNCHRONY",
        "lifecycle_state": "ACTIVE",
        "owner_module": "signal_synchrony",
        "participates_in_rebuild": "TRUE",
        "read_only": "FALSE",
        "allow_creation": "FALSE",
        "created_phase": "Signal Synchrony v2",
        "notes": "Derived-only interaction model audit over existing synchrony and character features",
    },
    {
        "logical_sheet_id": "SIGNAL_SYNCHRONY_INTERACTION_MODEL_SUMMARY",
        "physical_sheet_name": OUTPUT_SUMMARY_SHEET,
        "workbook": "DIAGNOSTICS",
        "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
        "category": "SIGNAL_SYNCHRONY",
        "lifecycle_state": "ACTIVE",
        "owner_module": "signal_synchrony",
        "participates_in_rebuild": "TRUE",
        "read_only": "FALSE",
        "allow_creation": "FALSE",
        "created_phase": "Signal Synchrony v2",
        "notes": "Derived-only interaction model summary",
    },
]

AUDIT_HEADERS = [
    "generated_ts",
    "interaction_id",
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
    "sample_groups",
    "comparable_rows",
    "correct_count",
    "wrong_count",
    "non_comparable_rows",
    "confidence_label",
    "thin_sample_flag",
    "missing_feature_flag",
    "correct_rate",
    "global_baseline_rate",
    "primary_feature_baseline_rate",
    "secondary_feature_baseline_rate",
    "tertiary_feature_baseline_rate",
    "best_component_baseline_rate",
    "provider_family_baseline_rate",
    "delta_vs_global_baseline",
    "delta_vs_best_component_baseline",
    "delta_vs_provider_family_baseline",
    "misleading_stability_count",
    "misleading_stability_rate",
    "dominant_failure_attribution_mix",
    "replay_result_label_mix",
    "risk_note",
    "interaction_label",
    "interaction_strength_label",
    "interaction_direction",
    "interpretation_note",
    "learning_model_approved",
    "routing_approved",
    "weighting_approved",
    "calibration_approved",
    "production_approved",
]

SUMMARY_HEADERS = [
    "generated_ts",
    "section",
    "rank",
    "feature_name",
    "feature_value",
    "interaction_level",
    "interaction_type",
    "interaction_key",
    "provider",
    "event_family",
    "comparable_rows",
    "correct_count",
    "wrong_count",
    "correct_rate",
    "global_baseline_rate",
    "primary_feature_baseline_rate",
    "secondary_feature_baseline_rate",
    "tertiary_feature_baseline_rate",
    "best_component_baseline_rate",
    "provider_family_baseline_rate",
    "delta_vs_global_baseline",
    "delta_vs_best_component_baseline",
    "delta_vs_provider_family_baseline",
    "misleading_stability_rate",
    "confidence_label",
    "interaction_label",
    "interaction_strength_label",
    "interaction_direction",
    "signal_label",
    "values_count",
    "best_value",
    "best_value_correct_rate",
    "worst_value",
    "worst_value_correct_rate",
    "spread",
    "source_rows_read",
    "total_comparable_rows",
    "global_baseline",
    "single_feature_slices",
    "two_way_interaction_slices",
    "three_way_interaction_slices",
    "slices_by_interaction_label",
    "interaction_signal_candidate_count",
    "interaction_risk_candidate_count",
    "interaction_lift_label",
    "best_signal_candidate",
    "best_risk_candidate",
    "total_interaction_slices",
    "signal_candidates",
    "risk_candidates",
    "context_dependent_slices",
    "thin_slices",
    "strongest_signal_interaction",
    "strongest_risk_interaction",
    "misleading_stability_slice_count",
    "misleading_stability_interaction_risk_count",
    "average_misleading_stability_rate",
    "strongest_persistent_risk_interaction",
    "misleading_stability_result_label",
    "final_interpretation_label",
    "final_interpretation_reason",
    "notes",
]

PROVIDER_ORDER = ["Anthropic", "Gemini", "OpenAI"]
FAMILY_ORDER = ["central_bank", "energy", "growth", "housing", "inflation", "labor", "manufacturing", "other"]
PREDICTABILITY_ORDER = ["low", "medium", "high", "unknown"]
DIRECTION_ORDER = ["LOW", "MEDIUM", "HIGH", "VERY_HIGH", "MISSING"]
STABILITY_ORDER = ["STABLE_BY_3", "STABLE_BY_4", "REQUIRES_FULL_5", "UNSTABLE_EVEN_AT_5", "TIE_OR_AMBIGUOUS", "INCOMPLETE_SAMPLE"]
PROTOCOL_ORDER = ["THREE_ONLY", "THREE_PLUS_TWO", "FIVE_ONLY", "INSUFFICIENT_DATA"]
COHORT_ORDER = ["cohort_a", "deterministic", "random", "unknown"]
MISLEAD_ORDER = ["TRUE", "FALSE"]
INTERACTION_LABEL_ORDER = [
    "INTERACTION_SIGNAL_CANDIDATE",
    "INTERACTION_RISK_CANDIDATE",
    "CONTEXT_DEPENDENT",
    "THIN_SAMPLE",
    "NO_SIGNAL",
    "INSUFFICIENT_DATA",
]
FAILURE_ORDER = [
    "MISLEADING_STABILITY_PERSISTS",
    "TIME_WINDOW_SHIFT",
    "COHORT_SHIFT",
    "SAMPLE_FRAGILITY",
    "PROVIDER_DEPENDENCE",
    "EVENT_FAMILY_SHIFT",
    "SYNCHRONY_DRIFT",
    "MULTI_FACTOR_FAILURE",
    "NO_FAILURE_GENERALIZES",
    "INSUFFICIENT_TRACEABILITY",
]
REPLAY_ORDER = [
    "GENERALIZES",
    "PARTIALLY_GENERALIZES",
    "WINDOW_DEPENDENT",
    "COHORT_DEPENDENT",
    "FAILED_REPLAY",
    "INSUFFICIENT_REPLAY_DATA",
]

SINGLE_FEATURES = [
    "provider",
    "event_family",
    "predictability_bucket",
    "direction_synchrony_bucket",
    "stability_label",
    "recommended_protocol",
    "cohort_bucket",
    "misleading_stability_flag",
]

TWO_WAY_FEATURES = [
    ("provider_event_family", ("provider", "event_family")),
    ("provider_direction_synchrony_bucket", ("provider", "direction_synchrony_bucket")),
    ("provider_predictability_bucket", ("provider", "predictability_bucket")),
    ("provider_stability_label", ("provider", "stability_label")),
    ("provider_misleading_stability_flag", ("provider", "misleading_stability_flag")),
    ("event_family_direction_synchrony_bucket", ("event_family", "direction_synchrony_bucket")),
    ("event_family_predictability_bucket", ("event_family", "predictability_bucket")),
    ("event_family_stability_label", ("event_family", "stability_label")),
    ("event_family_misleading_stability_flag", ("event_family", "misleading_stability_flag")),
    ("direction_synchrony_bucket_stability_label", ("direction_synchrony_bucket", "stability_label")),
    ("direction_synchrony_bucket_predictability_bucket", ("direction_synchrony_bucket", "predictability_bucket")),
    ("predictability_bucket_stability_label", ("predictability_bucket", "stability_label")),
    ("cohort_bucket_direction_synchrony_bucket", ("cohort_bucket", "direction_synchrony_bucket")),
    ("cohort_bucket_event_family", ("cohort_bucket", "event_family")),
]

THREE_WAY_FEATURES = [
    ("provider_event_family_direction_synchrony_bucket", ("provider", "event_family", "direction_synchrony_bucket")),
    ("provider_event_family_predictability_bucket", ("provider", "event_family", "predictability_bucket")),
    ("provider_event_family_stability_label", ("provider", "event_family", "stability_label")),
    ("provider_direction_synchrony_bucket_stability_label", ("provider", "direction_synchrony_bucket", "stability_label")),
    ("provider_direction_synchrony_bucket_predictability_bucket", ("provider", "direction_synchrony_bucket", "predictability_bucket")),
    ("event_family_direction_synchrony_bucket_stability_label", ("event_family", "direction_synchrony_bucket", "stability_label")),
    ("event_family_direction_synchrony_bucket_predictability_bucket", ("event_family", "direction_synchrony_bucket", "predictability_bucket")),
    ("provider_event_family_misleading_stability_flag", ("provider", "event_family", "misleading_stability_flag")),
    ("provider_event_family_cohort_bucket", ("provider", "event_family", "cohort_bucket")),
    ("provider_event_family_recommended_protocol", ("provider", "event_family", "recommended_protocol")),
]


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


def _confidence_label(comparable_rows: int) -> str:
    if comparable_rows >= 20:
        return "HIGHER_CONFIDENCE"
    if comparable_rows >= 12:
        return "MEDIUM_CONFIDENCE"
    if comparable_rows >= 8:
        return "LOW_CONFIDENCE"
    return "THIN_SAMPLE"


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
        return _cohort_bucket(row.get("cohort_id"))
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


def _unique_or_blank(rows: Sequence[Dict[str, Any]], field: str) -> str:
    values = sorted({ _feature_value(row, field) for row in rows if _feature_value(row, field) != "" })
    if len(values) == 1:
        return values[0]
    return ""


def _read_inputs(service) -> Dict[str, List[Dict[str, Any]]]:
    names = {
        "accuracy": "Signal_Synchrony_Accuracy_Audit",
        "direction_robustness": "Signal_Synchrony_Direction_Robustness",
        "pattern_map": "Character_Understanding_Pattern_Map",
        "candidates": "Character_Learning_Hypothesis_Candidates",
        "validation_queue": "Character_Learning_Validation_Queue",
        "replay_validation": "Character_Learning_Replay_Validation",
        "generalization_failure": "Character_Learning_Generalization_Failure",
        "provider_slice": "Signal_Synchrony_Provider_Slice_Performance",
        "family_slice": "Signal_Synchrony_Family_Slice_Performance",
        "cpv_audit": "Signal_Synchrony_Conditional_Value_Audit",
        "provider_dep": "Signal_Synchrony_Provider_Dep_Falsification",
        "microcohort": "Provider_Character_Direct_Expression_Microcohort",
        "outcome_check": "Provider_Character_Direct_Expression_Outcome_Check",
    }
    return {key: _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet) for key, sheet in names.items()}


def _derive_misleading_stability_flag(row: Dict[str, Any]) -> bool:
    if not _is_comparable(row) or _is_correct(row):
        return False
    bucket = _upper(row.get("direction_synchrony_bucket"))
    if bucket in {"HIGH", "VERY_HIGH"}:
        return True
    concentration = _as_float(row.get("forecast_direction_concentration"))
    return concentration is not None and concentration >= 0.70


def _match_condition_row(row: Dict[str, Any], condition_dimension: str, condition_value: str) -> bool:
    if condition_dimension == "":
        return False
    row_value = _feature_value(row, condition_dimension)
    cond_value = condition_value
    if condition_dimension in {"event_family", "predictability_bucket", "cohort_bucket"}:
        cond_value = _lower(condition_value)
    elif condition_dimension in {"direction_synchrony_bucket", "stability_label", "recommended_protocol", "misleading_stability_flag"}:
        cond_value = _upper(condition_value)
    else:
        cond_value = _norm(condition_value)
    return row_value == cond_value


def _index_annotations(
    candidate_rows: Sequence[Dict[str, Any]],
    queue_rows: Sequence[Dict[str, Any]],
    replay_rows: Sequence[Dict[str, Any]],
    failure_rows: Sequence[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    return {
        "candidates": list(candidate_rows),
        "queue": list(queue_rows),
        "replay": list(replay_rows),
        "failure": list(failure_rows),
    }


def _annotate_base_rows(sources: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    annotation_rows = _index_annotations(
        sources["candidates"],
        sources["validation_queue"],
        sources["replay_validation"],
        sources["generalization_failure"],
    )
    rows: List[Dict[str, Any]] = []
    for row in sources["accuracy"]:
        sample_group_id = _norm(row.get("sample_group_id"))
        if not sample_group_id:
            continue
        enriched = dict(row)
        enriched["provider"] = _norm(row.get("provider"))
        enriched["event_family"] = _lower(row.get("event_family"))
        enriched["predictability_bucket"] = _lower(row.get("predictability_bucket")) or "unknown"
        enriched["direction_synchrony_bucket"] = _upper(row.get("direction_synchrony_bucket")) or "MISSING"
        enriched["stability_label"] = _upper(row.get("stability_label"))
        enriched["recommended_protocol"] = _upper(row.get("recommended_protocol"))
        enriched["cohort_bucket"] = _cohort_bucket(row.get("cohort_id"))
        enriched["misleading_stability_flag"] = "TRUE" if _derive_misleading_stability_flag(row) else "FALSE"

        candidate_ids: List[str] = []
        candidate_labels: Counter = Counter()
        queue_labels: Counter = Counter()
        replay_labels: Counter = Counter()
        failure_labels: Counter = Counter()
        persistence_labels: Counter = Counter()

        for cand in annotation_rows["queue"]:
            if _norm(cand.get("provider")) != enriched["provider"]:
                continue
            if _lower(cand.get("event_family")) != enriched["event_family"]:
                continue
            if not _match_condition_row(enriched, _norm(cand.get("condition_dimension")), _norm(cand.get("condition_value"))):
                continue
            candidate_id = _norm(cand.get("candidate_id"))
            if candidate_id:
                candidate_ids.append(candidate_id)
            if _norm(cand.get("candidate_label")):
                candidate_labels[_norm(cand.get("candidate_label"))] += 1
            if _norm(cand.get("validation_queue_label")):
                queue_labels[_norm(cand.get("validation_queue_label"))] += 1

        for replay in annotation_rows["replay"]:
            if _norm(replay.get("provider")) != enriched["provider"]:
                continue
            if _lower(replay.get("event_family")) != enriched["event_family"]:
                continue
            if not _match_condition_row(enriched, _norm(replay.get("condition_dimension")), _norm(replay.get("condition_value"))):
                continue
            if _norm(replay.get("replay_result_label")):
                replay_labels[_norm(replay.get("replay_result_label"))] += 1

        for failure in annotation_rows["failure"]:
            if _norm(failure.get("provider")) != enriched["provider"]:
                continue
            if _lower(failure.get("event_family")) != enriched["event_family"]:
                continue
            if not _match_condition_row(enriched, _norm(failure.get("condition_dimension")), _norm(failure.get("condition_value"))):
                continue
            if _norm(failure.get("dominant_failure_attribution")):
                failure_labels[_norm(failure.get("dominant_failure_attribution"))] += 1
            if _norm(failure.get("misleading_stability_persistence_label")):
                persistence_labels[_norm(failure.get("misleading_stability_persistence_label"))] += 1

        enriched["candidate_label_mix"] = _count_string(candidate_labels, [])
        enriched["validation_queue_label_mix"] = _count_string(queue_labels, ["VALIDATE_FIRST", "VALIDATE_LATER", "OBSERVE_ONLY", "REJECT_AFTER_FILTER"])
        enriched["replay_result_label_mix"] = _count_string(replay_labels, REPLAY_ORDER)
        enriched["dominant_failure_attribution_mix"] = _count_string(failure_labels, FAILURE_ORDER)
        enriched["misleading_stability_persistence_label_mix"] = _count_string(
            persistence_labels,
            [
                "MISLEADING_STABILITY_PERSISTS",
                "MISLEADING_STABILITY_WEAKENS",
                "MISLEADING_STABILITY_FAILS",
                "NOT_MISLEADING_STABILITY_CANDIDATE",
                "INSUFFICIENT_MISLEADING_STABILITY_DATA",
            ],
        )
        rows.append(enriched)
    return rows


def _baseline_map(rows: Sequence[Dict[str, Any]], feature_name: str) -> Dict[str, float]:
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        value = _feature_value(row, feature_name)
        if value == "":
            continue
        groups[value].append(row)
    result: Dict[str, float] = {}
    for value, group in groups.items():
        comparable = [row for row in group if _is_comparable(row)]
        rate = _safe_rate(sum(1 for row in comparable if _is_correct(row)), len(comparable))
        if rate is not None:
            result[value] = rate
    return result


def _provider_family_baselines(rows: Sequence[Dict[str, Any]]) -> Dict[str, float]:
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        provider = _feature_value(row, "provider")
        family = _feature_value(row, "event_family")
        if provider == "" or family == "":
            continue
        groups[f"{provider}|{family}"].append(row)
    result: Dict[str, float] = {}
    for key, group in groups.items():
        comparable = [row for row in group if _is_comparable(row)]
        rate = _safe_rate(sum(1 for row in comparable if _is_correct(row)), len(comparable))
        if rate is not None:
            result[key] = rate
    return result


def _slice_rows(rows: Sequence[Dict[str, Any]], features: Sequence[str]) -> Dict[Tuple[str, ...], List[Dict[str, Any]]]:
    groups: Dict[Tuple[str, ...], List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        values = tuple(_feature_value(row, feature) for feature in features)
        if any(value == "" for value in values):
            continue
        groups[values].append(row)
    return groups


def _best_component_baseline(values: Sequence[Optional[float]]) -> Optional[float]:
    usable = [value for value in values if value is not None]
    if not usable:
        return None
    return max(usable)


def _interaction_label(
    comparable_rows: int,
    missing_feature_flag: bool,
    delta_vs_global: Optional[float],
    delta_vs_best: Optional[float],
    misleading_rate: Optional[float],
) -> str:
    if missing_feature_flag or comparable_rows <= 0:
        return "INSUFFICIENT_DATA"
    if comparable_rows < 8:
        return "THIN_SAMPLE"
    if misleading_rate is not None and misleading_rate >= 0.50:
        return "INTERACTION_RISK_CANDIDATE"
    if delta_vs_best is not None and delta_vs_best <= -0.10:
        return "INTERACTION_RISK_CANDIDATE"
    if misleading_rate is not None and misleading_rate >= 0.40:
        return "INTERACTION_RISK_CANDIDATE"
    if delta_vs_best is not None and delta_vs_best <= -0.06:
        return "INTERACTION_RISK_CANDIDATE"
    if delta_vs_best is not None and delta_vs_best >= 0.10 and (delta_vs_global or 0.0) >= 0.06:
        return "INTERACTION_SIGNAL_CANDIDATE"
    if delta_vs_best is not None and delta_vs_best >= 0.06 and (delta_vs_global or 0.0) >= 0.03:
        return "CONTEXT_DEPENDENT"
    return "NO_SIGNAL"


def _interaction_strength_label(label: str, delta_vs_best: Optional[float], misleading_rate: Optional[float]) -> str:
    if label == "INSUFFICIENT_DATA":
        return "INSUFFICIENT"
    if label == "THIN_SAMPLE":
        return "THIN"
    if label == "INTERACTION_SIGNAL_CANDIDATE":
        return "STRONG" if (delta_vs_best or 0.0) >= 0.10 else "MODERATE"
    if label == "INTERACTION_RISK_CANDIDATE":
        if (misleading_rate or 0.0) >= 0.50 or (delta_vs_best or 0.0) <= -0.10:
            return "STRONG"
        return "MODERATE"
    if label == "CONTEXT_DEPENDENT":
        return "WEAK"
    return "WEAK"


def _interaction_direction(label: str, delta_vs_best: Optional[float], misleading_rate: Optional[float]) -> str:
    if label == "INTERACTION_SIGNAL_CANDIDATE":
        return "POSITIVE"
    if label == "INTERACTION_RISK_CANDIDATE":
        return "NEGATIVE"
    if label == "CONTEXT_DEPENDENT":
        if delta_vs_best is not None and delta_vs_best > 0:
            return "MIXED_POSITIVE"
        if misleading_rate is not None and misleading_rate >= 0.40:
            return "MIXED_NEGATIVE"
        return "MIXED"
    if label == "NO_SIGNAL":
        return "NEUTRAL"
    return "UNKNOWN"


def _mix_from_rows(rows: Sequence[Dict[str, Any]], field: str, order: Sequence[str]) -> str:
    counter: Counter = Counter()
    for row in rows:
        raw = _norm(row.get(field))
        if raw == "":
            continue
        if "|" in raw and ":" in raw:
            for part in raw.split("|"):
                if ":" not in part:
                    continue
                key, value = part.split(":", 1)
                try:
                    counter[key] += int(value)
                except Exception:
                    counter[key] += 1
        else:
            counter[raw] += 1
    return _count_string(counter, order)


def _build_interaction_row(
    generated_ts: str,
    interaction_level: str,
    interaction_type: str,
    features: Sequence[str],
    values: Sequence[str],
    matched_rows: Sequence[Dict[str, Any]],
    global_baseline_rate: Optional[float],
    feature_baselines: Dict[str, Dict[str, float]],
    provider_family_baselines: Dict[str, float],
) -> Dict[str, Any]:
    comparable = [row for row in matched_rows if _is_comparable(row)]
    correct_count = sum(1 for row in comparable if _is_correct(row))
    wrong_count = len(comparable) - correct_count
    correct_rate = _safe_rate(correct_count, len(comparable))
    misleading_count = sum(1 for row in comparable if _feature_value(row, "misleading_stability_flag") == "TRUE")
    misleading_rate = _safe_rate(misleading_count, len(comparable))
    sample_groups = len({ _norm(row.get("sample_group_id")) for row in matched_rows if _norm(row.get("sample_group_id")) })
    non_comparable_rows = len(matched_rows) - len(comparable)
    confidence_label = _confidence_label(len(comparable))
    thin_sample_flag = "TRUE" if len(comparable) < 8 else "FALSE"
    missing_feature_flag = "TRUE" if any(value == "" for value in values) else "FALSE"

    primary_baseline = feature_baselines.get(features[0], {}).get(values[0]) if len(features) >= 1 else None
    secondary_baseline = feature_baselines.get(features[1], {}).get(values[1]) if len(features) >= 2 else None
    tertiary_baseline = feature_baselines.get(features[2], {}).get(values[2]) if len(features) >= 3 else None
    best_component = _best_component_baseline([primary_baseline, secondary_baseline, tertiary_baseline])

    unique_provider = _unique_or_blank(matched_rows, "provider")
    unique_family = _unique_or_blank(matched_rows, "event_family")
    provider_family_baseline = None
    if unique_provider and unique_family:
        provider_family_baseline = provider_family_baselines.get(f"{unique_provider}|{unique_family}")

    delta_vs_global = (correct_rate - global_baseline_rate) if correct_rate is not None and global_baseline_rate is not None else None
    delta_vs_best = (correct_rate - best_component) if correct_rate is not None and best_component is not None else None
    delta_vs_provider_family = (
        correct_rate - provider_family_baseline
        if correct_rate is not None and provider_family_baseline is not None
        else None
    )

    label = _interaction_label(len(comparable), missing_feature_flag == "TRUE", delta_vs_global, delta_vs_best, misleading_rate)
    strength = _interaction_strength_label(label, delta_vs_best, misleading_rate)
    direction = _interaction_direction(label, delta_vs_best, misleading_rate)

    interpretation_note = (
        f"rate={_round4(correct_rate)}; best_component={_round4(best_component)}; "
        f"delta_best={_round4(delta_vs_best)}; mislead={_round4(misleading_rate)}"
    )
    if label == "INTERACTION_SIGNAL_CANDIDATE":
        risk_note = "Interaction slice is above both global and component baselines without elevated misleading-stability risk."
    elif label == "INTERACTION_RISK_CANDIDATE":
        risk_note = "Interaction slice marks a concentrated failure/risk zone or repeated misleading-stability behavior."
    elif label == "CONTEXT_DEPENDENT":
        risk_note = "Interaction slice shows a partial effect but remains narrow or baseline-dependent."
    else:
        risk_note = ""

    row = {
        "generated_ts": generated_ts,
        "interaction_id": f"{interaction_level}_{interaction_type}_{'|'.join(values)}",
        "interaction_level": interaction_level,
        "interaction_type": interaction_type,
        "interaction_key": "|".join(values),
        "feature_1_name": features[0] if len(features) >= 1 else "",
        "feature_1_value": values[0] if len(values) >= 1 else "",
        "feature_2_name": features[1] if len(features) >= 2 else "",
        "feature_2_value": values[1] if len(values) >= 2 else "",
        "feature_3_name": features[2] if len(features) >= 3 else "",
        "feature_3_value": values[2] if len(values) >= 3 else "",
        "provider": unique_provider,
        "event_family": unique_family,
        "predictability_bucket": _unique_or_blank(matched_rows, "predictability_bucket"),
        "direction_synchrony_bucket": _unique_or_blank(matched_rows, "direction_synchrony_bucket"),
        "stability_label": _unique_or_blank(matched_rows, "stability_label"),
        "recommended_protocol": _unique_or_blank(matched_rows, "recommended_protocol"),
        "cohort_bucket": _unique_or_blank(matched_rows, "cohort_bucket"),
        "misleading_stability_flag": _unique_or_blank(matched_rows, "misleading_stability_flag"),
        "sample_groups": sample_groups,
        "comparable_rows": len(comparable),
        "correct_count": correct_count,
        "wrong_count": wrong_count,
        "non_comparable_rows": non_comparable_rows,
        "confidence_label": confidence_label,
        "thin_sample_flag": thin_sample_flag,
        "missing_feature_flag": missing_feature_flag,
        "correct_rate": correct_rate,
        "global_baseline_rate": global_baseline_rate,
        "primary_feature_baseline_rate": primary_baseline,
        "secondary_feature_baseline_rate": secondary_baseline,
        "tertiary_feature_baseline_rate": tertiary_baseline,
        "best_component_baseline_rate": best_component,
        "provider_family_baseline_rate": provider_family_baseline,
        "delta_vs_global_baseline": delta_vs_global,
        "delta_vs_best_component_baseline": delta_vs_best,
        "delta_vs_provider_family_baseline": delta_vs_provider_family,
        "misleading_stability_count": misleading_count,
        "misleading_stability_rate": misleading_rate,
        "dominant_failure_attribution_mix": _mix_from_rows(matched_rows, "dominant_failure_attribution_mix", FAILURE_ORDER),
        "replay_result_label_mix": _mix_from_rows(matched_rows, "replay_result_label_mix", REPLAY_ORDER),
        "risk_note": risk_note,
        "interaction_label": label,
        "interaction_strength_label": strength,
        "interaction_direction": direction,
        "interpretation_note": interpretation_note,
        "learning_model_approved": "FALSE",
        "routing_approved": "FALSE",
        "weighting_approved": "FALSE",
        "calibration_approved": "FALSE",
        "production_approved": "FALSE",
    }
    return row


def _build_audit_rows(rows: Sequence[Dict[str, Any]], generated_ts: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    comparable_rows = [row for row in rows if _is_comparable(row)]
    global_baseline_rate = _safe_rate(sum(1 for row in comparable_rows if _is_correct(row)), len(comparable_rows))
    feature_baselines = {feature: _baseline_map(rows, feature) for feature in SINGLE_FEATURES}
    provider_family_baselines = _provider_family_baselines(rows)

    audit_rows: List[Dict[str, Any]] = []

    for feature in SINGLE_FEATURES:
        for values, matched_rows in sorted(_slice_rows(rows, (feature,)).items()):
            audit_rows.append(
                _build_interaction_row(
                    generated_ts,
                    "single_feature",
                    feature,
                    (feature,),
                    values,
                    matched_rows,
                    global_baseline_rate,
                    feature_baselines,
                    provider_family_baselines,
                )
            )

    for interaction_type, features in TWO_WAY_FEATURES:
        for values, matched_rows in sorted(_slice_rows(rows, features).items()):
            audit_rows.append(
                _build_interaction_row(
                    generated_ts,
                    "two_way",
                    interaction_type,
                    features,
                    values,
                    matched_rows,
                    global_baseline_rate,
                    feature_baselines,
                    provider_family_baselines,
                )
            )

    for interaction_type, features in THREE_WAY_FEATURES:
        for values, matched_rows in sorted(_slice_rows(rows, features).items()):
            audit_rows.append(
                _build_interaction_row(
                    generated_ts,
                    "three_way",
                    interaction_type,
                    features,
                    values,
                    matched_rows,
                    global_baseline_rate,
                    feature_baselines,
                    provider_family_baselines,
                )
            )

    summary_context = {
        "source_rows_read": len(rows),
        "comparable_rows": len(comparable_rows),
        "global_baseline_rate": global_baseline_rate,
        "feature_baselines": feature_baselines,
    }
    return audit_rows, summary_context


def _spread_for_rows(rows: Sequence[Dict[str, Any]]) -> Optional[float]:
    rates: List[float] = []
    for row in rows:
        rate = _as_float(row.get("correct_rate"))
        if rate is not None:
            rates.append(rate)
    if len(rates) < 2:
        return None
    return max(rates) - min(rates)


def _single_feature_signal_label(best_delta: Optional[float], worst_delta: Optional[float], best_misleading: Optional[float], values_count: int) -> str:
    if values_count <= 0 or best_delta is None:
        return "INSUFFICIENT_DATA"
    if best_delta >= 0.10:
        return "SINGLE_FEATURE_SIGNAL"
    if best_misleading is not None and best_misleading >= 0.40 and (worst_delta is None or worst_delta <= 0):
        return "RISK_ONLY_SINGLE_FEATURE"
    if best_delta >= 0.06:
        return "WEAK_SINGLE_FEATURE_SIGNAL"
    return "NO_SINGLE_FEATURE_SIGNAL"


def _build_summary_rows(audit_rows: Sequence[Dict[str, Any]], context: Dict[str, Any], generated_ts: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    global_baseline_rate = context["global_baseline_rate"]
    label_counts = Counter(_norm(row.get("interaction_label")) for row in audit_rows)
    single_rows = [row for row in audit_rows if row["interaction_level"] == "single_feature"]
    two_way_rows = [row for row in audit_rows if row["interaction_level"] == "two_way"]
    three_way_rows = [row for row in audit_rows if row["interaction_level"] == "three_way"]

    rows.append(
        {
            "generated_ts": generated_ts,
            "section": "A_OVERALL_POPULATION_SUMMARY",
            "rank": 0,
            "source_rows_read": context["source_rows_read"],
            "total_comparable_rows": context["comparable_rows"],
            "global_baseline": _round4(global_baseline_rate),
            "single_feature_slices": len(single_rows),
            "two_way_interaction_slices": len(two_way_rows),
            "three_way_interaction_slices": len(three_way_rows),
            "slices_by_interaction_label": _count_string(label_counts, INTERACTION_LABEL_ORDER),
            "notes": "All slices are derived from Signal_Synchrony_Accuracy_Audit sample-group rows only.",
        }
    )

    single_by_feature: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in single_rows:
        single_by_feature[row["interaction_type"]].append(row)
    for rank, feature_name in enumerate(SINGLE_FEATURES, start=1):
        feature_rows = [row for row in single_by_feature.get(feature_name, []) if row["comparable_rows"] > 0]
        if not feature_rows:
            continue
        best_row = max(feature_rows, key=lambda row: (_as_float(row.get("correct_rate")) or -1.0, row["interaction_key"]))
        worst_row = min(feature_rows, key=lambda row: (_as_float(row.get("correct_rate")) or 2.0, row["interaction_key"]))
        spread = _spread_for_rows(feature_rows)
        signal_label = _single_feature_signal_label(
            _as_float(best_row.get("delta_vs_global_baseline")),
            _as_float(worst_row.get("delta_vs_global_baseline")),
            _as_float(best_row.get("misleading_stability_rate")),
            len(feature_rows),
        )
        rows.append(
            {
                "generated_ts": generated_ts,
                "section": "B_SINGLE_FEATURE_BASELINE_SUMMARY",
                "rank": rank,
                "feature_name": feature_name,
                "values_count": len(feature_rows),
                "best_value": best_row["interaction_key"],
                "best_value_correct_rate": best_row["correct_rate"],
                "worst_value": worst_row["interaction_key"],
                "worst_value_correct_rate": worst_row["correct_rate"],
                "spread": _round4(spread),
                "signal_label": signal_label,
                "notes": f"Best and worst values are measured against the global baseline {_round4(global_baseline_rate)}.",
            }
        )

    comparable_two = [row for row in two_way_rows if row["comparable_rows"] >= 8]
    comparable_three = [row for row in three_way_rows if row["comparable_rows"] >= 8]
    single_spread_mean = _safe_mean([_spread_for_rows(rows_) for rows_ in single_by_feature.values()])
    two_by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    three_by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in comparable_two:
        two_by_type[row["interaction_type"]].append(row)
    for row in comparable_three:
        three_by_type[row["interaction_type"]].append(row)
    two_spread_mean = _safe_mean([_spread_for_rows(rows_) for rows_ in two_by_type.values()])
    three_spread_mean = _safe_mean([_spread_for_rows(rows_) for rows_ in three_by_type.values()])
    signal_candidate_count = sum(1 for row in audit_rows if row["interaction_label"] == "INTERACTION_SIGNAL_CANDIDATE")
    risk_candidate_count = sum(1 for row in audit_rows if row["interaction_label"] == "INTERACTION_RISK_CANDIDATE")
    if (signal_candidate_count >= 3) and ((two_spread_mean or 0.0) > (single_spread_mean or 0.0) or (three_spread_mean or 0.0) > (single_spread_mean or 0.0)):
        lift_label = "INTERACTIONS_IMPROVE_SIGNAL"
    elif risk_candidate_count >= 3:
        lift_label = "INTERACTIONS_IMPROVE_RISK_DETECTION"
    elif len(comparable_two) + len(comparable_three) < 10:
        lift_label = "INTERACTIONS_TOO_THIN"
    else:
        lift_label = "INTERACTIONS_NO_BETTER_THAN_SINGLE_FEATURES"
    rows.append(
        {
            "generated_ts": generated_ts,
            "section": "C_INTERACTION_LIFT_SUMMARY",
            "rank": 0,
            "spread": _round4(single_spread_mean),
            "source_rows_read": context["source_rows_read"],
            "total_comparable_rows": context["comparable_rows"],
            "global_baseline": _round4(global_baseline_rate),
            "single_feature_slices": len(single_rows),
            "two_way_interaction_slices": len(two_way_rows),
            "three_way_interaction_slices": len(three_way_rows),
            "interaction_signal_candidate_count": signal_candidate_count,
            "interaction_risk_candidate_count": risk_candidate_count,
            "interaction_lift_label": lift_label,
            "notes": f"single_feature_average_spread={_round4(single_spread_mean)}; two_way_average_spread={_round4(two_spread_mean)}; three_way_average_spread={_round4(three_spread_mean)}",
        }
    )

    signal_rows = [row for row in audit_rows if row["interaction_label"] == "INTERACTION_SIGNAL_CANDIDATE"]
    signal_rows.sort(
        key=lambda row: (
            _as_float(row.get("delta_vs_best_component_baseline")) or -999.0,
            _as_float(row.get("correct_rate")) or -999.0,
            row["comparable_rows"],
            row["interaction_id"],
        ),
        reverse=True,
    )
    for rank, row in enumerate(signal_rows[:15], start=1):
        rows.append(
            {
                "generated_ts": generated_ts,
                "section": "D_BEST_INTERACTION_SIGNAL_CANDIDATES",
                "rank": rank,
                "interaction_level": row["interaction_level"],
                "interaction_type": row["interaction_type"],
                "interaction_key": row["interaction_key"],
                "provider": row["provider"],
                "event_family": row["event_family"],
                "comparable_rows": row["comparable_rows"],
                "correct_rate": row["correct_rate"],
                "delta_vs_best_component_baseline": row["delta_vs_best_component_baseline"],
                "delta_vs_global_baseline": row["delta_vs_global_baseline"],
                "confidence_label": row["confidence_label"],
                "interaction_label": row["interaction_label"],
                "notes": row["interpretation_note"],
            }
        )

    risk_rows = [row for row in audit_rows if row["interaction_label"] == "INTERACTION_RISK_CANDIDATE"]
    risk_rows.sort(
        key=lambda row: (
            _as_float(row.get("misleading_stability_rate")) or -1.0,
            -(_as_float(row.get("delta_vs_best_component_baseline")) or 999.0),
            row["comparable_rows"],
            row["interaction_id"],
        ),
        reverse=True,
    )
    for rank, row in enumerate(risk_rows[:15], start=1):
        rows.append(
            {
                "generated_ts": generated_ts,
                "section": "E_BEST_INTERACTION_RISK_CANDIDATES",
                "rank": rank,
                "interaction_level": row["interaction_level"],
                "interaction_type": row["interaction_type"],
                "interaction_key": row["interaction_key"],
                "provider": row["provider"],
                "event_family": row["event_family"],
                "comparable_rows": row["comparable_rows"],
                "correct_rate": row["correct_rate"],
                "delta_vs_best_component_baseline": row["delta_vs_best_component_baseline"],
                "misleading_stability_rate": row["misleading_stability_rate"],
                "confidence_label": row["confidence_label"],
                "interaction_label": row["interaction_label"],
                "notes": row["risk_note"] or row["interpretation_note"],
            }
        )

    for rank, provider in enumerate(PROVIDER_ORDER, start=1):
        provider_rows = [row for row in audit_rows if row["provider"] == provider]
        if not provider_rows:
            continue
        best_signal = signal_rows and next((row for row in signal_rows if row["provider"] == provider), None)
        best_risk = risk_rows and next((row for row in risk_rows if row["provider"] == provider), None)
        rows.append(
            {
                "generated_ts": generated_ts,
                "section": "F_PROVIDER_INTERACTION_SUMMARY",
                "rank": rank,
                "provider": provider,
                "total_interaction_slices": len(provider_rows),
                "signal_candidates": sum(1 for row in provider_rows if row["interaction_label"] == "INTERACTION_SIGNAL_CANDIDATE"),
                "risk_candidates": sum(1 for row in provider_rows if row["interaction_label"] == "INTERACTION_RISK_CANDIDATE"),
                "context_dependent_slices": sum(1 for row in provider_rows if row["interaction_label"] == "CONTEXT_DEPENDENT"),
                "thin_slices": sum(1 for row in provider_rows if row["interaction_label"] == "THIN_SAMPLE"),
                "strongest_signal_interaction": best_signal["interaction_id"] if best_signal else "",
                "strongest_risk_interaction": best_risk["interaction_id"] if best_risk else "",
                "notes": "Provider summary counts slices where the provider value is fixed within the interaction.",
            }
        )

    for rank, family in enumerate(FAMILY_ORDER, start=1):
        family_rows = [row for row in audit_rows if row["event_family"] == family]
        if not family_rows:
            continue
        best_signal = next((row for row in signal_rows if row["event_family"] == family), None)
        best_risk = next((row for row in risk_rows if row["event_family"] == family), None)
        rows.append(
            {
                "generated_ts": generated_ts,
                "section": "G_FAMILY_INTERACTION_SUMMARY",
                "rank": rank,
                "event_family": family,
                "total_interaction_slices": len(family_rows),
                "signal_candidates": sum(1 for row in family_rows if row["interaction_label"] == "INTERACTION_SIGNAL_CANDIDATE"),
                "risk_candidates": sum(1 for row in family_rows if row["interaction_label"] == "INTERACTION_RISK_CANDIDATE"),
                "context_dependent_slices": sum(1 for row in family_rows if row["interaction_label"] == "CONTEXT_DEPENDENT"),
                "thin_slices": sum(1 for row in family_rows if row["interaction_label"] == "THIN_SAMPLE"),
                "strongest_signal_interaction": best_signal["interaction_id"] if best_signal else "",
                "strongest_risk_interaction": best_risk["interaction_id"] if best_risk else "",
                "notes": "Family summary counts slices where the event family is fixed within the interaction.",
            }
        )

    misleading_rows = [
        row for row in audit_rows
        if "misleading_stability_flag" in {row["feature_1_name"], row["feature_2_name"], row["feature_3_name"]}
        or row["misleading_stability_flag"] == "TRUE"
    ]
    avg_misleading = _safe_mean([_as_float(row.get("misleading_stability_rate")) for row in misleading_rows])
    strongest_misleading = risk_rows[0] if risk_rows else {}
    if misleading_rows and sum(1 for row in misleading_rows if row["interaction_label"] == "INTERACTION_RISK_CANDIDATE") >= max(1, len(misleading_rows) // 6):
        misleading_label = "MISLEADING_STABILITY_RISK_SIGNAL"
    elif misleading_rows and any((_as_float(row.get("delta_vs_best_component_baseline")) or 0.0) > 0.06 for row in misleading_rows):
        misleading_label = "MISLEADING_STABILITY_ACCURACY_SIGNAL"
    elif misleading_rows:
        misleading_label = "MISLEADING_STABILITY_NOISY"
    else:
        misleading_label = "INSUFFICIENT_DATA"
    rows.append(
        {
            "generated_ts": generated_ts,
            "section": "H_MISLEADING_STABILITY_INTERACTION_SUMMARY",
            "rank": 0,
            "misleading_stability_slice_count": len(misleading_rows),
            "misleading_stability_interaction_risk_count": sum(1 for row in misleading_rows if row["interaction_label"] == "INTERACTION_RISK_CANDIDATE"),
            "average_misleading_stability_rate": _round4(avg_misleading),
            "strongest_persistent_risk_interaction": strongest_misleading.get("interaction_id", ""),
            "misleading_stability_result_label": misleading_label,
            "notes": "Misleading stability is assessed as a descriptive risk flag only and does not alter the source audits.",
        }
    )

    best_signal = signal_rows[0] if signal_rows else {}
    best_risk = risk_rows[0] if risk_rows else {}
    if signal_rows and ((two_spread_mean or 0.0) > (single_spread_mean or 0.0) or (three_spread_mean or 0.0) > (single_spread_mean or 0.0)):
        final_label = "INTERACTION_SIGNAL_FOUND"
        final_reason = "Several interaction slices beat both global and component baselines and are stronger than the average single-feature spread."
    elif risk_rows:
        final_label = "INTERACTION_RISK_ONLY"
        final_reason = "Interactions are more useful as failure/risk detectors than as clean accuracy-improvement signals, with misleading stability acting mainly as risk."
    elif signal_candidate_count == 0 and risk_candidate_count == 0:
        final_label = "NO_INTERACTION_VALUE"
        final_reason = "The current interaction slices do not improve on single-feature baselines or reveal stable risk zones."
    elif len(comparable_two) + len(comparable_three) < 10:
        final_label = "INSUFFICIENT_DATA"
        final_reason = "Too few non-thin interaction slices survive to evaluate the interaction hypothesis cleanly."
    else:
        final_label = "INTERACTIONS_NOISY"
        final_reason = "Some interaction effects appear, but they remain thin, unstable, or inconsistent against the component baselines."
    rows.append(
        {
            "generated_ts": generated_ts,
            "section": "I_FINAL_INTERPRETATION",
            "rank": 0,
            "source_rows_read": context["source_rows_read"],
            "total_comparable_rows": context["comparable_rows"],
            "global_baseline": _round4(global_baseline_rate),
            "single_feature_slices": len(single_rows),
            "two_way_interaction_slices": len(two_way_rows),
            "three_way_interaction_slices": len(three_way_rows),
            "slices_by_interaction_label": _count_string(label_counts, INTERACTION_LABEL_ORDER),
            "interaction_signal_candidate_count": signal_candidate_count,
            "interaction_risk_candidate_count": risk_candidate_count,
            "best_signal_candidate": best_signal.get("interaction_id", ""),
            "best_risk_candidate": best_risk.get("interaction_id", ""),
            "misleading_stability_result_label": misleading_label,
            "final_interpretation_label": final_label,
            "final_interpretation_reason": final_reason,
            "notes": "This audit is historical and derived-only. It does not approve learning, routing, weighting, calibration, or production behavior.",
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


def build_signal_synchrony_interaction_model_audit() -> Dict[str, Any]:
    service = build_sheets_service(load_credentials(interactive=False))
    sources = _read_inputs(service)
    generated_ts = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    base_rows = _annotate_base_rows(sources)
    audit_rows, context = _build_audit_rows(base_rows, generated_ts)
    summary_rows = _build_summary_rows(audit_rows, context, generated_ts)

    audit_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_AUDIT_SHEET, AUDIT_HEADERS)
    summary_headers = _ensure_sheet(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, SUMMARY_HEADERS)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_AUDIT_SHEET, audit_headers, audit_rows)
    _write_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTPUT_SUMMARY_SHEET, summary_headers, summary_rows)

    registry_result = _upsert_registry_rows(service)
    final_row = next((row for row in summary_rows if row.get("section") == "I_FINAL_INTERPRETATION"), {})
    return {
        "generated_ts": generated_ts,
        "source_rows_read": context["source_rows_read"],
        "comparable_rows": context["comparable_rows"],
        "global_baseline": _round4(context["global_baseline_rate"]),
        "single_feature_slices": len([row for row in audit_rows if row["interaction_level"] == "single_feature"]),
        "two_way_slices": len([row for row in audit_rows if row["interaction_level"] == "two_way"]),
        "three_way_slices": len([row for row in audit_rows if row["interaction_level"] == "three_way"]),
        "providers_represented": _count_string(Counter(row["provider"] for row in base_rows if row["provider"]), PROVIDER_ORDER),
        "families_represented": _count_string(Counter(row["event_family"] for row in base_rows if row["event_family"]), FAMILY_ORDER),
        "final_interpretation_label": final_row.get("final_interpretation_label", ""),
        "misleading_stability_result_label": final_row.get("misleading_stability_result_label", ""),
        "best_signal_candidate": final_row.get("best_signal_candidate", ""),
        "best_risk_candidate": final_row.get("best_risk_candidate", ""),
        "registry_result": registry_result,
    }


def main() -> None:
    print(build_signal_synchrony_interaction_model_audit())


if __name__ == "__main__":
    main()
