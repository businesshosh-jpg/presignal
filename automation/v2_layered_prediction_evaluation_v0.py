#!/usr/bin/env python3
"""PreSignal v2.0 layered prediction, outcome, and evaluation contracts.

This module is shadow-only.  It deliberately does not read or write the legacy
Predictions or evaluation sheets.  Prediction parsing is pre-outcome; outcome
construction and evaluation are separate calls so the forecast boundary is
enforceable in code as well as in the workbook schema.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


SCHEMA_VERSION = "v2.0-layered-shadow-v0"
EVENT_REACTION_HORIZON_MIN = 5
SESSION_REACTION_HORIZON_MIN = 5
PIP_SIZE = 0.01
FLAT_THRESHOLD_PIPS = 1.0
INTERACTION_RULE_VERSION = "v2.0-interaction-outcome-v0"
INTERACTION_RULE_BASE_RUN_ID = "9-V2-LAYERED-PREDICTION-EVALUATION-REPAIR_20260716T083002Z"
REALIZED_INTERACTION_CLASSES = {
    "CONTINUATION", "PARTIAL_RETRACE", "FULL_REVERSAL",
    "NO_MEANINGFUL_SECONDARY_EFFECT", "INDEPENDENT_VOLATILITY", "NOT_EVALUABLE",
}

PREDICTION_SHEET = "v2.0 Prediction"
PATH_SHEET = "v2.0 Prediction Path"
OUTCOME_SHEET = "v2.0 Outcome"
EVALUATION_SHEET = "v2.0 Evaluation"
SCHEMA_SHEET = "v2.0 Schema"

PREDICTION_HEADERS = [
    "prediction_id", "session_id", "session_date", "session_window_name", "fx_pair",
    "provider", "model", "model_version", "pack_arm", "pack_freeze_id",
    "pack_fingerprint", "forecast_run_id", "forecast_created_ts", "forecast_cutoff_ts",
    "prompt_version", "prediction_schema_version", "prediction_status", "prediction_fingerprint",
    "session_member_count", "session_member_event_ids", "session_member_release_cluster_ids",
    "first_release_ts", "last_release_ts", "primary_driver_event_id",
    "primary_driver_indicator_name", "primary_driver_release_cluster_id", "primary_driver_release_ts",
    "primary_driver_choice_confidence", "primary_driver_reason", "secondary_driver_status",
    "secondary_driver_event_id", "secondary_driver_indicator_name", "secondary_driver_release_cluster_id",
    "secondary_driver_release_ts", "secondary_driver_choice_confidence", "secondary_driver_reason",
    "primary_reaction_target_type", "primary_reaction_target_id", "primary_reaction_direction",
    "primary_expected_pips_min", "primary_expected_pips_max", "primary_reaction_horizon_min",
    "primary_reaction_confidence", "primary_reaction_thesis", "secondary_reaction_status",
    "secondary_reaction_target_type", "secondary_reaction_target_id", "secondary_reaction_direction",
    "secondary_expected_pips_min", "secondary_expected_pips_max", "secondary_reaction_horizon_min",
    "secondary_reaction_confidence", "secondary_reaction_thesis", "interaction_status",
    "primary_secondary_interaction", "interaction_confidence", "interaction_explanation",
    "session_forecast_direction", "session_expected_pips_min", "session_expected_pips_max",
    "session_confidence", "session_expected_holding_min", "session_path_summary", "session_thesis",
    "causal_chain", "invalidation_condition", "no_signal_flag", "no_signal_reason",
    "information_used", "missing_information", "raw_output",
]

PATH_HEADERS = [
    "prediction_id", "session_id", "provider", "pack_arm", "path_stage_index",
    "path_stage_type", "path_target_type", "path_target_id", "path_target_name",
    "expected_start_ts", "expected_end_ts", "expected_direction", "expected_pips_min",
    "expected_pips_max", "expected_behavior", "relationship_to_previous_stage",
    "stage_confidence", "stage_explanation", "path_schema_version", "stage_fingerprint",
]

OUTCOME_HEADERS = [
    "outcome_id", "outcome_level", "outcome_target_id", "session_id", "event_id",
    "release_cluster_id", "outcome_window_start_ts", "outcome_window_end_ts", "opening_price_ts",
    "opening_price", "closing_price_ts", "closing_price", "realized_pips", "realized_direction",
    "max_up_pips", "max_down_pips", "volatility_pips", "sustained_displacement_pips",
    "actual_interaction_class", "interaction_evaluation_status", "interaction_price_evidence",
    "outcome_source", "outcome_method", "source_canonical_outcome_ids", "outcome_schema_version",
    "outcome_status", "outcome_rejection_reason", "outcome_fingerprint", "generated_ts",
]

EVALUATION_HEADERS = [
    "evaluation_id", "prediction_id", "session_id", "provider", "model", "pack_arm",
    "evaluation_component", "component_index", "prediction_reference_id", "outcome_reference_id",
    "predicted_value", "actual_value", "predicted_pips_min", "predicted_pips_max", "actual_pips",
    "absolute_pip_error", "direction_result", "magnitude_result", "component_result",
    "evaluation_status", "evaluation_note", "path_components_predicted", "path_components_evaluable",
    "path_components_correct", "path_component_accuracy", "prediction_fingerprint",
    "outcome_fingerprint", "evaluation_schema_version", "evaluation_fingerprint", "generated_ts",
]

SCHEMA_HEADERS = [
    "sheet_name", "field_name", "field_order", "data_type", "required", "allowed_values",
    "description", "scientific_role", "missing_value_rule", "schema_version",
]

DIRECTIONS = {"UP", "DOWN", "FLAT", "NO_CLEAR_DIRECTION", "NOT_PREDICTED"}
FINAL_DIRECTIONS = DIRECTIONS - {"NOT_PREDICTED"}
SECONDARY_STATUSES = {"SELECTED", "NO_MEANINGFUL_SECONDARY_DRIVER", "UNCERTAIN", "NOT_PREDICTED"}
SECONDARY_REACTION_STATUSES = {
    "PREDICTED", "SAME_CLUSTER_NOT_SEPARATELY_PREDICTABLE",
    "NO_MEANINGFUL_SECONDARY_DRIVER", "UNCERTAIN", "NOT_PREDICTED",
}
INTERACTION_STATUSES = {"PREDICTED", "NOT_APPLICABLE_SAME_CLUSTER", "NO_SECONDARY_DRIVER", "UNCERTAIN", "NOT_PREDICTED"}
INTERACTIONS = {
    "CONTINUATION", "PARTIAL_RETRACE", "FULL_REVERSAL", "NO_MEANINGFUL_SECONDARY_EFFECT",
    "INDEPENDENT_VOLATILITY", "UNCERTAIN", "NOT_APPLICABLE",
}
PATH_STAGE_TYPES = {"RELEASE_CLUSTER_REACTION", "BETWEEN_RELEASES", "FINAL_SESSION_STATE"}
PATH_BEHAVIORS = {"HOLD", "CONTINUE", "PARTIAL_RETRACE", "FULL_RETRACE", "RANGE", "VOLATILE_NO_DIRECTION", "UNKNOWN"}
EVALUATION_COMPONENTS = {
    "PRIMARY_DRIVER_CHOICE", "SECONDARY_DRIVER_CHOICE", "PRIMARY_REACTION_DIRECTION",
    "PRIMARY_REACTION_MAGNITUDE", "SECONDARY_REACTION_DIRECTION", "SECONDARY_REACTION_MAGNITUDE",
    "PRIMARY_SECONDARY_INTERACTION", "PATH_STAGE_DIRECTION", "PATH_STAGE_MAGNITUDE",
    "BETWEEN_RELEASE_BEHAVIOR", "SESSION_DIRECTION", "SESSION_MAGNITUDE",
    "PATH_DIRECTIONAL_SEQUENCE", "COMPLETE_PATH_STRICT",
}
COMPONENT_RESULTS = {
    "CORRECT", "PARTIALLY_CORRECT", "INCORRECT", "NOT_PREDICTED", "NOT_APPLICABLE",
    "NOT_SEPARABLY_EVALUABLE", "NOT_YET_EVALUABLE", "OUTCOME_UNAVAILABLE",
}
PACK_ARMS = {"A", "E_STRUCTURED", "E_OFFICIAL", "E_ENVIRONMENT", "E_ENVIRONMENT_EODHD", "E_ENVIRONMENT_INSTITUTIONAL", "E"}

OUTCOME_FIELD_TOKENS = {
    "outcome_id", "realized_direction", "realized_pips", "opening_price", "closing_price",
    "direction_result", "component_result", "canonical_outcome_id", "actual_interaction_class",
}
PREDICTION_FIELD_TOKENS = {
    "primary_driver_event_id", "session_forecast_direction", "primary_reaction_direction",
    "secondary_reaction_direction", "primary_secondary_interaction", "prediction_id",
}


class V2ValidationError(ValueError):
    """A deterministic schema or identity validation failure."""


def _norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def fingerprint(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def interaction_rule_preregistration(frozen_timestamp: str) -> Dict[str, Any]:
    """Return the frozen rule; its fingerprint excludes only freeze metadata."""
    scientific_rule = {
        "rule_version": INTERACTION_RULE_VERSION,
        "base_run_id": INTERACTION_RULE_BASE_RUN_ID,
        "allowed_classes": sorted(REALIZED_INTERACTION_CLASSES),
        "required_price_points": {
            "P0": "last valid price strictly before selected primary release cluster",
            "P1": "first valid price at or after selected primary cluster plus 5 minutes",
            "P2": "last valid price strictly before selected secondary release cluster",
            "P3": "first valid price at or after selected secondary cluster plus 5 minutes",
            "session_open": "last valid price strictly before first frozen session cluster",
            "session_close": "first valid price at or after final frozen session cluster plus 5 minutes",
        },
        "pip_convention": {"pair": "USDJPY", "pip_size": PIP_SIZE, "signed_pips": "(later_price-earlier_price)/0.01"},
        "flat_threshold_pips": FLAT_THRESHOLD_PIPS,
        "meaningful_move_rule": "absolute signed move > 1 pip; equality is non-meaningful",
        "reaction_horizons_minutes": {"primary": EVENT_REACTION_HORIZON_MIN, "secondary": EVENT_REACTION_HORIZON_MIN},
        "authoritative_comparison_target": "secondary_release_interaction",
        "classification_order": [
            "validate selected cluster identity, chronology, session boundary, and P0-P3 price boundaries",
            "same release cluster -> NOT_APPLICABLE outside the realized-class enum",
            "secondary close displacement non-meaningful and meaningful two-sided excursion -> INDEPENDENT_VOLATILITY",
            "secondary close displacement non-meaningful -> NO_MEANINGFUL_SECONDARY_EFFECT",
            "primary close displacement non-meaningful and secondary meaningful -> INDEPENDENT_VOLATILITY",
            "same-sign meaningful moves with meaningful net displacement in primary direction -> CONTINUATION",
            "opposite-sign meaningful moves with meaningful net displacement in primary direction and 0 < retrace_ratio < 1 -> PARTIAL_RETRACE",
            "opposite-sign meaningful moves with meaningful net displacement opposite primary -> FULL_REVERSAL",
            "net displacement at or inside flat band, or other bounded residual -> INDEPENDENT_VOLATILITY",
        ],
        "same_cluster_rule": "NOT_APPLICABLE_SAME_CLUSTER; evaluation result NOT_APPLICABLE",
        "exact_return_rule": "abs(P3-P0) <= 1 pip -> INDEPENDENT_VOLATILITY when secondary movement is meaningful",
        "residual_volatility_rule": "bounded residual only; includes non-meaningful primary with meaningful secondary, meaningful two-sided secondary excursion with flat close, directionally inconsistent net path, or opposite secondary retrace_ratio >= 1 while inter-release drift leaves a primary-direction net",
        "two_sided_excursion_rule": "secondary max_up_pips > 1 and abs(secondary max_down_pips) > 1",
        "missing_data_rule": "missing/invalid identity, timestamp, price, session boundary, or five-minute horizon -> NOT_EVALUABLE",
        "multi_cluster_rule": "use provider-selected primary and secondary release_cluster_ids; require distinct IDs and primary release before secondary release",
        "between_release_behavior_rule": "classify P1->P2 separately; it does not replace secondary_release_interaction",
        "prohibited_use_of_provider_accuracy": True,
        "provider_predictions_are_not_classifier_inputs": True,
    }
    return {
        **scientific_rule,
        "rule_fingerprint": fingerprint(scientific_rule),
        "frozen_timestamp": _ts(frozen_timestamp),
    }


def _parse_ts(value: Any) -> datetime:
    raw = _norm(value)
    if not raw:
        raise V2ValidationError("MISSING_TIMESTAMP")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise V2ValidationError("INVALID_TIMESTAMP:" + raw) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _ts(value: Any) -> str:
    return _parse_ts(value).isoformat().replace("+00:00", "Z")


def _float(value: Any, field: str, *, minimum: float | None = None, maximum: float | None = None) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise V2ValidationError("INVALID_NUMBER:" + field) from exc
    if minimum is not None and number < minimum:
        raise V2ValidationError("NUMBER_BELOW_MINIMUM:" + field)
    if maximum is not None and number > maximum:
        raise V2ValidationError("NUMBER_ABOVE_MAXIMUM:" + field)
    return number


def _bool(value: Any, field: str) -> bool:
    if isinstance(value, bool):
        return value
    normalized = _norm(value).lower()
    if normalized in {"true", "1"}:
        return True
    if normalized in {"false", "0"}:
        return False
    raise V2ValidationError("INVALID_BOOLEAN:" + field)


def _require_enum(value: Any, allowed: set[str], field: str) -> str:
    normalized = _upper(value)
    if normalized not in allowed:
        raise V2ValidationError("INVALID_ENUM:" + field + ":" + normalized)
    return normalized


def release_cluster_id(session_id: str, same_minute_group_key: str) -> str:
    """Create a stable cluster identity from the frozen same-minute identity."""
    key = _norm(same_minute_group_key)
    if not session_id or not key:
        raise V2ValidationError("MISSING_RELEASE_CLUSTER_IDENTITY")
    return "RC_" + fingerprint({"session_id": session_id, "same_minute_group_key": key})[:24]


def normalize_session_members(session_id: str, members: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    seen_events: set[str] = set()
    for raw in members:
        member = dict(raw)
        event_id = _norm(member.get("event_id"))
        release = _ts(member.get("release_ts"))
        if not event_id or event_id in seen_events:
            raise V2ValidationError("MISSING_OR_DUPLICATE_SESSION_MEMBER_EVENT_ID")
        seen_events.add(event_id)
        group_key = _norm(member.get("same_minute_group_key"))
        if not group_key:
            release_minute = _parse_ts(release).replace(second=0, microsecond=0).isoformat().replace("+00:00", "Z")
            group_key = f"{_upper(member.get('country')) or 'UNKNOWN'}|{release_minute}"
        member.update({
            "session_id": session_id,
            "event_id": event_id,
            "release_ts": release,
            "same_minute_group_key": group_key,
            "release_cluster_id": release_cluster_id(session_id, group_key),
        })
        normalized.append(member)
    if not normalized:
        raise V2ValidationError("EMPTY_SESSION_MEMBERSHIP")
    return sorted(normalized, key=lambda row: (row["release_ts"], row["event_id"]))


def release_clusters(session_id: str, members: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    normalized = normalize_session_members(session_id, members)
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for member in normalized:
        grouped.setdefault(member["release_cluster_id"], []).append(member)
    clusters = []
    for cluster_id, rows in grouped.items():
        release_times = {row["release_ts"] for row in rows}
        if len(release_times) != 1:
            raise V2ValidationError("RELEASE_CLUSTER_CONTAINS_DISTINCT_TIMESTAMPS")
        clusters.append({
            "release_cluster_id": cluster_id,
            "same_minute_group_key": rows[0]["same_minute_group_key"],
            "release_ts": rows[0]["release_ts"],
            "member_event_ids": [row["event_id"] for row in rows],
            "member_count": len(rows),
        })
    return sorted(clusters, key=lambda row: (row["release_ts"], row["release_cluster_id"]))


def provider_output_contract() -> Dict[str, Any]:
    """Return the provider-owned portion of the frozen prediction contract."""
    return {
        "primary_driver_event_id": "exact session member event_id",
        "primary_driver_choice_confidence": "0..1",
        "primary_driver_reason": "string",
        "secondary_driver_status": sorted(SECONDARY_STATUSES),
        "secondary_driver_event_id": "required only when SELECTED",
        "secondary_driver_choice_confidence": "0..1 or blank when not selected",
        "secondary_driver_reason": "string",
        "primary_reaction_target_type": ["EVENT", "RELEASE_CLUSTER"],
        "primary_reaction_target_id": "exact event_id or release_cluster_id",
        "primary_reaction_direction": sorted(DIRECTIONS),
        "primary_expected_pips_min": "non-negative number",
        "primary_expected_pips_max": "number >= min",
        "primary_reaction_horizon_min": "positive number",
        "primary_reaction_confidence": "0..1",
        "primary_reaction_thesis": "string",
        "secondary_reaction_status": sorted(SECONDARY_REACTION_STATUSES),
        "secondary_reaction_target_type": "EVENT|RELEASE_CLUSTER or blank",
        "secondary_reaction_target_id": "exact target or blank",
        "secondary_reaction_direction": sorted(DIRECTIONS),
        "secondary_expected_pips_min": "non-negative number or blank",
        "secondary_expected_pips_max": "number >= min or blank",
        "secondary_reaction_horizon_min": "positive number or blank",
        "secondary_reaction_confidence": "0..1 or blank",
        "secondary_reaction_thesis": "string",
        "interaction_status": sorted(INTERACTION_STATUSES),
        "primary_secondary_interaction": sorted(INTERACTIONS),
        "interaction_confidence": "0..1 or blank",
        "interaction_explanation": "string",
        "session_forecast_direction": sorted(FINAL_DIRECTIONS),
        "session_expected_pips_min": "non-negative number",
        "session_expected_pips_max": "number >= min",
        "session_confidence": "0..1",
        "session_expected_holding_min": "positive number",
        "session_path_summary": "string",
        "session_thesis": "string",
        "causal_chain": "string",
        "invalidation_condition": "string",
        "no_signal_flag": "boolean",
        "no_signal_reason": "required for NO_CLEAR_DIRECTION or true flag",
        "information_used": "array or string",
        "missing_information": "array or string",
        "prediction_path": [{
            "path_stage_index": "integer starting at 1",
            "path_stage_type": sorted(PATH_STAGE_TYPES),
            "path_target_type": "EVENT|RELEASE_CLUSTER|MARKET_SESSION",
            "path_target_id": "exact target identity",
            "path_target_name": "string",
            "expected_start_ts": "ISO-8601 UTC",
            "expected_end_ts": "ISO-8601 UTC",
            "expected_direction": sorted(DIRECTIONS),
            "expected_pips_min": "non-negative number",
            "expected_pips_max": "number >= min",
            "expected_behavior": sorted(PATH_BEHAVIORS),
            "relationship_to_previous_stage": "string",
            "stage_confidence": "0..1",
            "stage_explanation": "string",
        }],
    }


def _interval(payload: Mapping[str, Any], minimum_field: str, maximum_field: str, *, optional: bool = False) -> Tuple[Any, Any]:
    if optional and not _norm(payload.get(minimum_field)) and not _norm(payload.get(maximum_field)):
        return "", ""
    minimum = _float(payload.get(minimum_field), minimum_field, minimum=0)
    maximum = _float(payload.get(maximum_field), maximum_field, minimum=0)
    if minimum > maximum:
        raise V2ValidationError("INVALID_PIPS_INTERVAL:" + minimum_field)
    return minimum, maximum


def parse_provider_prediction(
    payload: Mapping[str, Any], *, session: Mapping[str, Any], members: Sequence[Mapping[str, Any]],
    provider: str, model: str, pack_arm: str, pack_freeze_id: str, pack_fingerprint: str,
    forecast_run_id: str, forecast_created_ts: str, forecast_cutoff_ts: str,
    prompt_version: str, raw_output: str,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Validate and freeze one provider prediction without outcome access."""
    if any(field in payload for field in OUTCOME_FIELD_TOKENS):
        raise V2ValidationError("OUTCOME_FIELD_PRESENT_IN_PREDICTION")
    session_id = _norm(session.get("session_id"))
    if not session_id:
        raise V2ValidationError("MISSING_SESSION_ID")
    if pack_arm not in PACK_ARMS:
        raise V2ValidationError("INVALID_PACK_ARM")
    normalized_members = normalize_session_members(session_id, members)
    clusters = release_clusters(session_id, normalized_members)
    events = {row["event_id"]: row for row in normalized_members}
    clusters_by_id = {row["release_cluster_id"]: row for row in clusters}

    primary_event_id = _norm(payload.get("primary_driver_event_id"))
    if primary_event_id not in events:
        raise V2ValidationError("PRIMARY_DRIVER_NOT_IN_SESSION")
    primary_member = events[primary_event_id]
    secondary_status = _require_enum(payload.get("secondary_driver_status"), SECONDARY_STATUSES, "secondary_driver_status")
    secondary_event_id = _norm(payload.get("secondary_driver_event_id"))
    secondary_member: Mapping[str, Any] | None = None
    if secondary_status == "SELECTED":
        if secondary_event_id not in events or secondary_event_id == primary_event_id:
            raise V2ValidationError("SECONDARY_DRIVER_NOT_DISTINCT_SESSION_MEMBER")
        secondary_member = events[secondary_event_id]
    elif secondary_event_id:
        raise V2ValidationError("SECONDARY_EVENT_PRESENT_WITHOUT_SELECTED_STATUS")

    primary_target_type = _require_enum(payload.get("primary_reaction_target_type"), {"EVENT", "RELEASE_CLUSTER"}, "primary_reaction_target_type")
    primary_target_id = _norm(payload.get("primary_reaction_target_id"))
    valid_primary_target = primary_event_id if primary_target_type == "EVENT" else primary_member["release_cluster_id"]
    if primary_target_id != valid_primary_target:
        raise V2ValidationError("PRIMARY_REACTION_TARGET_IDENTITY_MISMATCH")
    if len(clusters_by_id[primary_member["release_cluster_id"]]["member_event_ids"]) > 1 and primary_target_type != "RELEASE_CLUSTER":
        raise V2ValidationError("SAME_TIME_PRIMARY_MUST_TARGET_RELEASE_CLUSTER")

    primary_min, primary_max = _interval(payload, "primary_expected_pips_min", "primary_expected_pips_max")
    secondary_reaction_status = _require_enum(payload.get("secondary_reaction_status"), SECONDARY_REACTION_STATUSES, "secondary_reaction_status")
    interaction_status = _require_enum(payload.get("interaction_status"), INTERACTION_STATUSES, "interaction_status")
    interaction = _require_enum(payload.get("primary_secondary_interaction"), INTERACTIONS, "primary_secondary_interaction")
    same_cluster = bool(secondary_member and secondary_member["release_cluster_id"] == primary_member["release_cluster_id"])
    if same_cluster:
        if secondary_reaction_status != "SAME_CLUSTER_NOT_SEPARATELY_PREDICTABLE":
            raise V2ValidationError("SAME_CLUSTER_SECONDARY_REACTION_MUST_BE_NONSEPARABLE")
        if interaction_status != "NOT_APPLICABLE_SAME_CLUSTER" or interaction != "NOT_APPLICABLE":
            raise V2ValidationError("SAME_CLUSTER_INTERACTION_MUST_BE_NOT_APPLICABLE")
    elif secondary_status == "SELECTED":
        if secondary_reaction_status != "PREDICTED":
            raise V2ValidationError("DISTINCT_SELECTED_SECONDARY_REACTION_REQUIRED")
        if interaction_status != "PREDICTED":
            raise V2ValidationError("DISTINCT_SELECTED_INTERACTION_REQUIRED")
    else:
        if secondary_reaction_status not in {"NO_MEANINGFUL_SECONDARY_DRIVER", "UNCERTAIN", "NOT_PREDICTED"}:
            raise V2ValidationError("SECONDARY_REACTION_STATUS_INCONSISTENT")
        if interaction_status not in {"NO_SECONDARY_DRIVER", "UNCERTAIN", "NOT_PREDICTED"}:
            raise V2ValidationError("INTERACTION_STATUS_INCONSISTENT")

    secondary_target_type = _upper(payload.get("secondary_reaction_target_type"))
    secondary_target_id = _norm(payload.get("secondary_reaction_target_id"))
    secondary_min, secondary_max = _interval(payload, "secondary_expected_pips_min", "secondary_expected_pips_max", optional=secondary_reaction_status != "PREDICTED")
    if secondary_reaction_status == "PREDICTED" and secondary_member:
        if secondary_target_type not in {"EVENT", "RELEASE_CLUSTER"}:
            raise V2ValidationError("INVALID_SECONDARY_REACTION_TARGET_TYPE")
        expected_target = secondary_event_id if secondary_target_type == "EVENT" else secondary_member["release_cluster_id"]
        if secondary_target_id != expected_target:
            raise V2ValidationError("SECONDARY_REACTION_TARGET_IDENTITY_MISMATCH")
        if len(clusters_by_id[secondary_member["release_cluster_id"]]["member_event_ids"]) > 1 and secondary_target_type != "RELEASE_CLUSTER":
            raise V2ValidationError("SAME_TIME_SECONDARY_MUST_TARGET_RELEASE_CLUSTER")

    session_min, session_max = _interval(payload, "session_expected_pips_min", "session_expected_pips_max")
    final_direction = _require_enum(payload.get("session_forecast_direction"), FINAL_DIRECTIONS, "session_forecast_direction")
    no_signal = _bool(payload.get("no_signal_flag"), "no_signal_flag")
    if (no_signal or final_direction == "NO_CLEAR_DIRECTION") and not _norm(payload.get("no_signal_reason")):
        raise V2ValidationError("MISSING_NO_SIGNAL_REASON")
    if no_signal != (final_direction == "NO_CLEAR_DIRECTION"):
        raise V2ValidationError("NO_SIGNAL_DIRECTION_INCONSISTENT")

    path_payload = payload.get("prediction_path")
    if not isinstance(path_payload, list) or len(path_payload) < 2:
        raise V2ValidationError("PREDICTION_PATH_REQUIRES_AT_LEAST_TWO_STAGES")
    path_rows: List[Dict[str, Any]] = []
    for expected_index, raw_stage in enumerate(path_payload, start=1):
        if not isinstance(raw_stage, Mapping):
            raise V2ValidationError("INVALID_PATH_STAGE_OBJECT")
        index = int(_float(raw_stage.get("path_stage_index"), "path_stage_index", minimum=1))
        if index != expected_index:
            raise V2ValidationError("PATH_STAGE_ORDER_INVALID")
        stage_type = _require_enum(raw_stage.get("path_stage_type"), PATH_STAGE_TYPES, "path_stage_type")
        target_type = _require_enum(raw_stage.get("path_target_type"), {"EVENT", "RELEASE_CLUSTER", "MARKET_SESSION"}, "path_target_type")
        target_id = _norm(raw_stage.get("path_target_id"))
        if target_type == "EVENT" and target_id not in events:
            raise V2ValidationError("PATH_EVENT_TARGET_NOT_IN_SESSION")
        if target_type == "RELEASE_CLUSTER" and target_id not in clusters_by_id:
            raise V2ValidationError("PATH_CLUSTER_TARGET_NOT_IN_SESSION")
        if target_type == "MARKET_SESSION" and target_id != session_id:
            raise V2ValidationError("PATH_SESSION_TARGET_MISMATCH")
        if stage_type == "BETWEEN_RELEASES" and len(clusters) < 2:
            raise V2ValidationError("BETWEEN_RELEASE_STAGE_REQUIRES_DISTINCT_CLUSTERS")
        stage_min, stage_max = _interval(raw_stage, "expected_pips_min", "expected_pips_max")
        start_ts, end_ts = _ts(raw_stage.get("expected_start_ts")), _ts(raw_stage.get("expected_end_ts"))
        if _parse_ts(end_ts) < _parse_ts(start_ts):
            raise V2ValidationError("PATH_STAGE_NEGATIVE_TIME_INTERVAL")
        path_rows.append({
            "path_stage_index": index, "path_stage_type": stage_type,
            "path_target_type": target_type, "path_target_id": target_id,
            "path_target_name": _norm(raw_stage.get("path_target_name")),
            "expected_start_ts": start_ts, "expected_end_ts": end_ts,
            "expected_direction": _require_enum(raw_stage.get("expected_direction"), DIRECTIONS, "expected_direction"),
            "expected_pips_min": stage_min, "expected_pips_max": stage_max,
            "expected_behavior": _require_enum(raw_stage.get("expected_behavior"), PATH_BEHAVIORS, "expected_behavior"),
            "relationship_to_previous_stage": _norm(raw_stage.get("relationship_to_previous_stage")),
            "stage_confidence": _float(raw_stage.get("stage_confidence"), "stage_confidence", minimum=0, maximum=1),
            "stage_explanation": _norm(raw_stage.get("stage_explanation")), "path_schema_version": SCHEMA_VERSION,
        })
    if path_rows[0]["path_stage_type"] != "RELEASE_CLUSTER_REACTION" or path_rows[-1]["path_stage_type"] != "FINAL_SESSION_STATE":
        raise V2ValidationError("PATH_MINIMUM_STAGE_TYPES_INVALID")
    if path_rows[-1]["path_target_id"] != session_id:
        raise V2ValidationError("FINAL_PATH_STAGE_MUST_TARGET_SESSION")
    if secondary_member and not same_cluster and not any(row["path_target_id"] == secondary_member["release_cluster_id"] for row in path_rows):
        raise V2ValidationError("DISTINCT_SECONDARY_CLUSTER_MISSING_FROM_PATH")

    identity = {
        "session_id": session_id, "provider": provider, "model": model, "pack_arm": pack_arm,
        "pack_freeze_id": pack_freeze_id, "pack_fingerprint": pack_fingerprint,
        "forecast_run_id": forecast_run_id, "forecast_cutoff_ts": _ts(forecast_cutoff_ts),
        "prompt_version": prompt_version, "prediction_schema_version": SCHEMA_VERSION,
    }
    prediction_id = "V2P_" + fingerprint(identity)[:28]
    for row in path_rows:
        row.update({"prediction_id": prediction_id, "session_id": session_id, "provider": provider, "pack_arm": pack_arm})
        row["stage_fingerprint"] = fingerprint({key: row[key] for key in PATH_HEADERS if key != "stage_fingerprint"})

    prediction: Dict[str, Any] = {
        **identity,
        "prediction_id": prediction_id,
        "session_date": _norm(session.get("session_date")) or _ts(normalized_members[0]["release_ts"])[:10],
        "session_window_name": _norm(session.get("session_window_name")) or _norm(session.get("window_name")),
        "fx_pair": _norm(session.get("fx_pair")) or "USDJPY",
        "model_version": _norm(session.get("model_version")) or model,
        "forecast_created_ts": _ts(forecast_created_ts), "prediction_status": "FROZEN_PREOUTCOME",
        "session_member_count": len(normalized_members),
        "session_member_event_ids": _json([row["event_id"] for row in normalized_members]),
        "session_member_release_cluster_ids": _json([row["release_cluster_id"] for row in clusters]),
        "first_release_ts": clusters[0]["release_ts"], "last_release_ts": clusters[-1]["release_ts"],
        "primary_driver_event_id": primary_event_id,
        "primary_driver_indicator_name": _norm(primary_member.get("indicator_name")),
        "primary_driver_release_cluster_id": primary_member["release_cluster_id"],
        "primary_driver_release_ts": primary_member["release_ts"],
        "primary_driver_choice_confidence": _float(payload.get("primary_driver_choice_confidence"), "primary_driver_choice_confidence", minimum=0, maximum=1),
        "primary_driver_reason": _norm(payload.get("primary_driver_reason")),
        "secondary_driver_status": secondary_status,
        "secondary_driver_event_id": secondary_event_id,
        "secondary_driver_indicator_name": _norm((secondary_member or {}).get("indicator_name")),
        "secondary_driver_release_cluster_id": _norm((secondary_member or {}).get("release_cluster_id")),
        "secondary_driver_release_ts": _norm((secondary_member or {}).get("release_ts")),
        "secondary_driver_choice_confidence": "" if secondary_status != "SELECTED" else _float(payload.get("secondary_driver_choice_confidence"), "secondary_driver_choice_confidence", minimum=0, maximum=1),
        "secondary_driver_reason": _norm(payload.get("secondary_driver_reason")),
        "primary_reaction_target_type": primary_target_type, "primary_reaction_target_id": primary_target_id,
        "primary_reaction_direction": _require_enum(payload.get("primary_reaction_direction"), DIRECTIONS, "primary_reaction_direction"),
        "primary_expected_pips_min": primary_min, "primary_expected_pips_max": primary_max,
        "primary_reaction_horizon_min": _float(payload.get("primary_reaction_horizon_min"), "primary_reaction_horizon_min", minimum=0.01),
        "primary_reaction_confidence": _float(payload.get("primary_reaction_confidence"), "primary_reaction_confidence", minimum=0, maximum=1),
        "primary_reaction_thesis": _norm(payload.get("primary_reaction_thesis")),
        "secondary_reaction_status": secondary_reaction_status,
        "secondary_reaction_target_type": secondary_target_type, "secondary_reaction_target_id": secondary_target_id,
        "secondary_reaction_direction": _require_enum(payload.get("secondary_reaction_direction"), DIRECTIONS, "secondary_reaction_direction"),
        "secondary_expected_pips_min": secondary_min, "secondary_expected_pips_max": secondary_max,
        "secondary_reaction_horizon_min": "" if secondary_reaction_status != "PREDICTED" else _float(payload.get("secondary_reaction_horizon_min"), "secondary_reaction_horizon_min", minimum=0.01),
        "secondary_reaction_confidence": "" if secondary_reaction_status != "PREDICTED" else _float(payload.get("secondary_reaction_confidence"), "secondary_reaction_confidence", minimum=0, maximum=1),
        "secondary_reaction_thesis": _norm(payload.get("secondary_reaction_thesis")),
        "interaction_status": interaction_status, "primary_secondary_interaction": interaction,
        "interaction_confidence": (
            _float(payload.get("interaction_confidence"), "interaction_confidence", minimum=0, maximum=1)
            if _norm(payload.get("interaction_confidence")) else ""
        ),
        "interaction_explanation": _norm(payload.get("interaction_explanation")),
        "session_forecast_direction": final_direction, "session_expected_pips_min": session_min,
        "session_expected_pips_max": session_max,
        "session_confidence": _float(payload.get("session_confidence"), "session_confidence", minimum=0, maximum=1),
        "session_expected_holding_min": _float(payload.get("session_expected_holding_min"), "session_expected_holding_min", minimum=0.01),
        "session_path_summary": _norm(payload.get("session_path_summary")), "session_thesis": _norm(payload.get("session_thesis")),
        "causal_chain": _norm(payload.get("causal_chain")), "invalidation_condition": _norm(payload.get("invalidation_condition")),
        "no_signal_flag": no_signal, "no_signal_reason": _norm(payload.get("no_signal_reason")),
        "information_used": _json(payload.get("information_used")) if not isinstance(payload.get("information_used"), str) else payload.get("information_used"),
        "missing_information": _json(payload.get("missing_information")) if not isinstance(payload.get("missing_information"), str) else payload.get("missing_information"),
        "raw_output": raw_output,
    }
    fingerprint_payload = {key: prediction.get(key, "") for key in PREDICTION_HEADERS if key not in {"prediction_fingerprint", "raw_output"}}
    prediction["prediction_fingerprint"] = fingerprint(fingerprint_payload)
    return prediction, path_rows


def _direction_from_pips(pips: float) -> str:
    if pips >= FLAT_THRESHOLD_PIPS:
        return "UP"
    if pips <= -FLAT_THRESHOLD_PIPS:
        return "DOWN"
    return "FLAT"


def interaction_rule_fingerprint() -> str:
    return _norm(interaction_rule_preregistration("2000-01-01T00:00:00Z")["rule_fingerprint"])


def _outcome_number(row: Mapping[str, Any], field: str) -> float:
    try:
        value = float(row.get(field))
    except (TypeError, ValueError) as exc:
        raise V2ValidationError("INTERACTION_PRICE_MISSING:" + field) from exc
    if not math.isfinite(value):
        raise V2ValidationError("INTERACTION_PRICE_NONFINITE:" + field)
    return value


def _pip_delta(later: float, earlier: float) -> float:
    return round((later - earlier) / PIP_SIZE, 6)


def _meaningful(move_pips: float) -> bool:
    return abs(move_pips) > FLAT_THRESHOLD_PIPS


def _move_sign(move_pips: float) -> int:
    if move_pips > FLAT_THRESHOLD_PIPS:
        return 1
    if move_pips < -FLAT_THRESHOLD_PIPS:
        return -1
    return 0


def _validate_cluster_boundary(row: Mapping[str, Any], label: str) -> Dict[str, Any]:
    if _norm(row.get("outcome_level")) != "RELEASE_CLUSTER" or _norm(row.get("outcome_status")) != "VALID":
        raise V2ValidationError("INVALID_" + label + "_CLUSTER_OUTCOME")
    start = _parse_ts(row.get("outcome_window_start_ts"))
    end = _parse_ts(row.get("outcome_window_end_ts"))
    opening_ts = _parse_ts(row.get("opening_price_ts"))
    closing_ts = _parse_ts(row.get("closing_price_ts"))
    if opening_ts >= start:
        raise V2ValidationError(label + "_OPENING_NOT_STRICTLY_PRE_RELEASE")
    if closing_ts < end:
        raise V2ValidationError(label + "_CLOSING_BEFORE_REACTION_HORIZON")
    if (end - start).total_seconds() != EVENT_REACTION_HORIZON_MIN * 60:
        raise V2ValidationError(label + "_REACTION_HORIZON_MISMATCH")
    return {
        "cluster_id": _norm(row.get("outcome_target_id")),
        "release_ts": start, "reaction_end_ts": end,
        "opening_price_ts": opening_ts, "opening_price": _outcome_number(row, "opening_price"),
        "closing_price_ts": closing_ts, "closing_price": _outcome_number(row, "closing_price"),
        "max_up_pips": _outcome_number(row, "max_up_pips") if _norm(row.get("max_up_pips")) else None,
        "max_down_pips": _outcome_number(row, "max_down_pips") if _norm(row.get("max_down_pips")) else None,
        "outcome_id": _norm(row.get("outcome_id")), "outcome_fingerprint": _norm(row.get("outcome_fingerprint")),
    }


def _validate_session_boundary(row: Mapping[str, Any]) -> Dict[str, Any]:
    if _norm(row.get("outcome_level")) != "MARKET_SESSION" or _norm(row.get("outcome_status")) != "VALID":
        raise V2ValidationError("INVALID_MARKET_SESSION_OUTCOME")
    opening_ts = _parse_ts(row.get("opening_price_ts"))
    closing_ts = _parse_ts(row.get("closing_price_ts"))
    if closing_ts <= opening_ts:
        raise V2ValidationError("INVALID_MARKET_SESSION_PRICE_ORDER")
    return {
        "opening_price_ts": opening_ts, "opening_price": _outcome_number(row, "opening_price"),
        "closing_price_ts": closing_ts, "closing_price": _outcome_number(row, "closing_price"),
        "outcome_id": _norm(row.get("outcome_id")), "outcome_fingerprint": _norm(row.get("outcome_fingerprint")),
    }


def classify_between_release_behavior(primary_move: float, p0: float, p1: float, p2: float) -> Dict[str, Any]:
    inter_release_move = _pip_delta(p2, p1)
    net_before_secondary = _pip_delta(p2, p0)
    if not _meaningful(inter_release_move):
        behavior, reason = "HOLD", "INTER_RELEASE_MOVE_AT_OR_INSIDE_FLAT_THRESHOLD"
    elif not _meaningful(primary_move):
        behavior, reason = "VOLATILE_NO_DIRECTION", "PRIMARY_MOVE_NOT_MEANINGFUL"
    elif _move_sign(inter_release_move) == _move_sign(primary_move):
        behavior, reason = "CONTINUE", "INTER_RELEASE_MOVE_SAME_DIRECTION_AS_PRIMARY"
    elif not _meaningful(net_before_secondary) or _move_sign(net_before_secondary) != _move_sign(primary_move):
        behavior, reason = "FULL_RETRACE", "INTER_RELEASE_MOVE_ERASED_OR_CROSSED_PRIMARY_DISPLACEMENT"
    elif _move_sign(net_before_secondary) == _move_sign(primary_move):
        behavior, reason = "PARTIAL_RETRACE", "INTER_RELEASE_MOVE_OPPOSED_BUT_DID_NOT_ERASE_PRIMARY_DISPLACEMENT"
    else:
        behavior, reason = "VOLATILE_NO_DIRECTION", "INTER_RELEASE_PATH_RESIDUAL"
    return {
        "between_release_behavior": behavior,
        "between_release_reason": reason,
        "inter_release_move_pips": inter_release_move,
        "net_before_secondary_pips": net_before_secondary,
    }


def classify_realized_interaction(
    primary_outcome: Mapping[str, Any], secondary_outcome: Mapping[str, Any], session_outcome: Mapping[str, Any],
) -> Dict[str, Any]:
    """Classify the selected cluster pair without provider predictions or accuracy."""
    rule_fp = interaction_rule_fingerprint()
    primary_id = _norm(primary_outcome.get("outcome_target_id"))
    secondary_id = _norm(secondary_outcome.get("outcome_target_id"))
    base = {
        "rule_version": INTERACTION_RULE_VERSION, "rule_fingerprint": rule_fp,
        "authoritative_comparison_target": "secondary_release_interaction",
        "primary_release_cluster_id": primary_id, "secondary_release_cluster_id": secondary_id,
    }
    if not primary_id or not secondary_id:
        return {**base, "interaction_class": "NOT_EVALUABLE", "classification_reason": "MISSING_RELEASE_CLUSTER_IDENTITY", "evaluation_status": "NOT_EVALUABLE"}
    if primary_id == secondary_id:
        return {**base, "interaction_class": "NOT_APPLICABLE", "classification_reason": "NOT_APPLICABLE_SAME_CLUSTER", "evaluation_status": "NOT_APPLICABLE"}
    try:
        primary = _validate_cluster_boundary(primary_outcome, "PRIMARY")
        secondary = _validate_cluster_boundary(secondary_outcome, "SECONDARY")
        session = _validate_session_boundary(session_outcome)
        if primary["release_ts"] >= secondary["release_ts"]:
            reason = "INVALID_DRIVER_ORDER_FOR_INTERACTION" if primary["release_ts"] > secondary["release_ts"] else "DISTINCT_CLUSTER_TIMESTAMP_COLLISION"
            raise V2ValidationError(reason)
        p0, p1 = primary["opening_price"], primary["closing_price"]
        p2, p3 = secondary["opening_price"], secondary["closing_price"]
        primary_move = _pip_delta(p1, p0)
        inter_release_move = _pip_delta(p2, p1)
        secondary_move = _pip_delta(p3, p2)
        net_after_secondary = _pip_delta(p3, p0)
        primary_abs, secondary_abs, net_abs = abs(primary_move), abs(secondary_move), abs(net_after_secondary)
        secondary_to_primary_ratio = round(secondary_abs / primary_abs, 6) if primary_abs else None
        opposite = _move_sign(primary_move) != 0 and _move_sign(secondary_move) != 0 and _move_sign(primary_move) != _move_sign(secondary_move)
        retrace_ratio = round(secondary_abs / primary_abs, 6) if opposite and primary_abs else None
        secondary_two_sided = bool(
            secondary["max_up_pips"] is not None and secondary["max_down_pips"] is not None
            and secondary["max_up_pips"] > FLAT_THRESHOLD_PIPS
            and abs(secondary["max_down_pips"]) > FLAT_THRESHOLD_PIPS
        )
        between = classify_between_release_behavior(primary_move, p0, p1, p2)

        if not _meaningful(secondary_move):
            if secondary_two_sided:
                interaction_class, reason = "INDEPENDENT_VOLATILITY", "SECONDARY_TWO_SIDED_EXCURSION_WITH_NONMEANINGFUL_CLOSE"
            else:
                interaction_class, reason = "NO_MEANINGFUL_SECONDARY_EFFECT", "SECONDARY_MOVE_AT_OR_INSIDE_FLAT_THRESHOLD"
        elif not _meaningful(primary_move):
            interaction_class, reason = "INDEPENDENT_VOLATILITY", "PRIMARY_MOVE_NOT_MEANINGFUL_SECONDARY_MOVE_MEANINGFUL"
        elif _move_sign(secondary_move) == _move_sign(primary_move):
            if _meaningful(net_after_secondary) and _move_sign(net_after_secondary) == _move_sign(primary_move):
                interaction_class, reason = "CONTINUATION", "MEANINGFUL_SAME_DIRECTION_SECONDARY_WITH_PRIMARY_DIRECTION_NET"
            else:
                interaction_class, reason = "INDEPENDENT_VOLATILITY", "SAME_DIRECTION_SECONDARY_BUT_NET_PATH_NOT_PRIMARY_DIRECTION"
        elif not _meaningful(net_after_secondary):
            interaction_class, reason = "INDEPENDENT_VOLATILITY", "SECONDARY_RETURNED_PRICE_TO_ORIGINAL_FLAT_BAND"
        elif (
            _move_sign(net_after_secondary) == _move_sign(primary_move)
            and retrace_ratio is not None and 0 < retrace_ratio < 1
        ):
            interaction_class, reason = "PARTIAL_RETRACE", "OPPOSITE_SECONDARY_MOVE_LEFT_MEANINGFUL_PRIMARY_DIRECTION_NET"
        elif _move_sign(net_after_secondary) == -_move_sign(primary_move):
            interaction_class, reason = "FULL_REVERSAL", "OPPOSITE_SECONDARY_MOVE_ESTABLISHED_MEANINGFUL_OPPOSITE_NET"
        else:
            interaction_class, reason = "INDEPENDENT_VOLATILITY", "BOUNDED_DIRECTIONALLY_INCONSISTENT_OR_RETRACE_RATIO_RESIDUAL"
        combined_path = "|".join([
            "PRIMARY_" + _direction_from_pips(primary_move),
            "BETWEEN_" + between["between_release_behavior"],
            "SECONDARY_" + interaction_class,
            "NET_" + _direction_from_pips(net_after_secondary),
        ])
        result = {
            **base, "interaction_class": interaction_class, "secondary_release_interaction": interaction_class,
            "combined_primary_to_secondary_path": combined_path,
            "classification_reason": reason, "evaluation_status": "EVALUABLE",
            "P0": p0, "P1": p1, "P2": p2, "P3": p3,
            "P0_ts": primary["opening_price_ts"].isoformat().replace("+00:00", "Z"),
            "P1_ts": primary["closing_price_ts"].isoformat().replace("+00:00", "Z"),
            "P2_ts": secondary["opening_price_ts"].isoformat().replace("+00:00", "Z"),
            "P3_ts": secondary["closing_price_ts"].isoformat().replace("+00:00", "Z"),
            "primary_move_pips": primary_move, "inter_release_move_pips": inter_release_move,
            "secondary_move_pips": secondary_move, "net_after_secondary_pips": net_after_secondary,
            "primary_abs_pips": primary_abs, "secondary_abs_pips": secondary_abs, "net_abs_pips": net_abs,
            "secondary_to_primary_ratio": secondary_to_primary_ratio, "retrace_ratio": retrace_ratio,
            "secondary_two_sided_excursion": secondary_two_sided,
            "primary_outcome_id": primary["outcome_id"], "secondary_outcome_id": secondary["outcome_id"],
            "session_outcome_id": session["outcome_id"],
            "session_opening_price": session["opening_price"], "session_closing_price": session["closing_price"],
            **between,
        }
        return result
    except V2ValidationError as exc:
        return {**base, "interaction_class": "NOT_EVALUABLE", "classification_reason": str(exc), "evaluation_status": "NOT_EVALUABLE"}


def _price_before(candles: Sequence[Mapping[str, Any]], boundary: datetime) -> Mapping[str, Any] | None:
    eligible = [row for row in candles if _parse_ts(row.get("timestamp")) < boundary]
    return max(eligible, key=lambda row: _parse_ts(row.get("timestamp"))) if eligible else None


def _price_at_or_after(candles: Sequence[Mapping[str, Any]], boundary: datetime) -> Mapping[str, Any] | None:
    eligible = [row for row in candles if _parse_ts(row.get("timestamp")) >= boundary]
    return min(eligible, key=lambda row: _parse_ts(row.get("timestamp"))) if eligible else None


def _outcome_row(
    *, level: str, target_id: str, session_id: str, event_id: str, cluster_id: str,
    start: datetime, end: datetime, candles: Sequence[Mapping[str, Any]], source: str,
    method: str, generated_ts: str, canonical_ids: Sequence[str] = (), rejection_reason: str = "",
) -> Dict[str, Any]:
    opening = _price_before(candles, start)
    closing = _price_at_or_after(candles, end)
    status = "VALID" if opening and closing and not rejection_reason else "REJECTED"
    row: Dict[str, Any] = {
        "outcome_level": level, "outcome_target_id": target_id, "session_id": session_id,
        "event_id": event_id, "release_cluster_id": cluster_id,
        "outcome_window_start_ts": start.isoformat().replace("+00:00", "Z"),
        "outcome_window_end_ts": end.isoformat().replace("+00:00", "Z"),
        "opening_price_ts": _ts(opening.get("timestamp")) if opening else "", "opening_price": opening.get("price", "") if opening else "",
        "closing_price_ts": _ts(closing.get("timestamp")) if closing else "", "closing_price": closing.get("price", "") if closing else "",
        "realized_pips": "", "realized_direction": "", "max_up_pips": "", "max_down_pips": "",
        "volatility_pips": "", "sustained_displacement_pips": "", "actual_interaction_class": "",
        "interaction_evaluation_status": "NOT_YET_EVALUABLE", "interaction_price_evidence": "",
        "outcome_source": source, "outcome_method": method,
        "source_canonical_outcome_ids": _json(list(canonical_ids)), "outcome_schema_version": SCHEMA_VERSION,
        "outcome_status": status, "outcome_rejection_reason": rejection_reason or ("" if status == "VALID" else "PRICE_BOUNDARY_UNAVAILABLE"),
        "generated_ts": _ts(generated_ts),
    }
    if status == "VALID":
        opening_price, closing_price = float(opening["price"]), float(closing["price"])
        pips = round((closing_price - opening_price) / PIP_SIZE, 4)
        window_rows = [row for row in candles if start <= _parse_ts(row.get("timestamp")) <= end]
        prices = [float(item["price"]) for item in window_rows] or [opening_price, closing_price]
        row.update({
            "realized_pips": pips, "realized_direction": _direction_from_pips(pips),
            "max_up_pips": round((max(prices) - opening_price) / PIP_SIZE, 4),
            "max_down_pips": round((min(prices) - opening_price) / PIP_SIZE, 4),
            "volatility_pips": round((max(prices) - min(prices)) / PIP_SIZE, 4),
            "sustained_displacement_pips": pips,
        })
    identity = {"level": level, "target": target_id, "session_id": session_id, "start": row["outcome_window_start_ts"], "end": row["outcome_window_end_ts"], "schema": SCHEMA_VERSION}
    row["outcome_id"] = "V2O_" + fingerprint(identity)[:28]
    row["outcome_fingerprint"] = fingerprint({key: row.get(key, "") for key in OUTCOME_HEADERS if key not in {"outcome_fingerprint", "generated_ts"}})
    return row


def _interaction_evidence(outcomes: Sequence[Mapping[str, Any]]) -> str:
    clusters = []
    for row in outcomes:
        if _norm(row.get("outcome_level")) != "RELEASE_CLUSTER":
            continue
        clusters.append({
            "release_cluster_id": row.get("outcome_target_id"), "outcome_id": row.get("outcome_id"),
            "outcome_status": row.get("outcome_status"), "outcome_window_start_ts": row.get("outcome_window_start_ts"),
            "outcome_window_end_ts": row.get("outcome_window_end_ts"), "opening_price_ts": row.get("opening_price_ts"),
            "opening_price": row.get("opening_price"), "closing_price_ts": row.get("closing_price_ts"),
            "closing_price": row.get("closing_price"), "realized_pips": row.get("realized_pips"),
            "realized_direction": row.get("realized_direction"), "max_up_pips": row.get("max_up_pips"),
            "max_down_pips": row.get("max_down_pips"), "volatility_pips": row.get("volatility_pips"),
            "outcome_fingerprint": row.get("outcome_fingerprint"),
        })
    return _json({
        "rule_version": INTERACTION_RULE_VERSION, "rule_fingerprint": interaction_rule_fingerprint(),
        "classification_scope": "provider-selected distinct release-cluster pair",
        "authoritative_comparison_target": "secondary_release_interaction",
        "clusters": sorted(clusters, key=lambda row: (_norm(row.get("outcome_window_start_ts")), _norm(row.get("release_cluster_id")))),
    })


def construct_outcomes(
    *, session: Mapping[str, Any], members: Sequence[Mapping[str, Any]], candles: Sequence[Mapping[str, Any]],
    generated_ts: str, source: str = "APPROVED_MARKET_PRICE_FIXTURE",
) -> List[Dict[str, Any]]:
    """Construct event, cluster, and provider-neutral session outcomes."""
    session_id = _norm(session.get("session_id"))
    normalized_members = normalize_session_members(session_id, members)
    clusters = release_clusters(session_id, normalized_members)
    outcomes: List[Dict[str, Any]] = []
    for cluster in clusters:
        release = _parse_ts(cluster["release_ts"])
        end = release + timedelta(minutes=EVENT_REACTION_HORIZON_MIN)
        outcomes.append(_outcome_row(
            level="RELEASE_CLUSTER", target_id=cluster["release_cluster_id"], session_id=session_id,
            event_id="", cluster_id=cluster["release_cluster_id"], start=release, end=end, candles=candles,
            source=source, method="EVENT_RELATIVE_FIXED_DURATION|5", generated_ts=generated_ts,
        ))
        for event_id in cluster["member_event_ids"]:
            if cluster["member_count"] > 1:
                outcomes.append(_outcome_row(
                    level="EVENT", target_id=event_id, session_id=session_id, event_id=event_id,
                    cluster_id=cluster["release_cluster_id"], start=release, end=end, candles=candles,
                    source=source, method="EVENT_RELATIVE_FIXED_DURATION|5", generated_ts=generated_ts,
                    rejection_reason="EVENT_OUTCOME_NOT_SEPARABLY_EVALUABLE",
                ))
            else:
                outcomes.append(_outcome_row(
                    level="EVENT", target_id=event_id, session_id=session_id, event_id=event_id,
                    cluster_id=cluster["release_cluster_id"], start=release, end=end, candles=candles,
                    source=source, method="EVENT_RELATIVE_FIXED_DURATION|5", generated_ts=generated_ts,
                ))
    first_release = _parse_ts(clusters[0]["release_ts"])
    final_release = _parse_ts(clusters[-1]["release_ts"])
    session_outcome = _outcome_row(
        level="MARKET_SESSION", target_id=session_id, session_id=session_id, event_id="", cluster_id="",
        start=first_release, end=final_release + timedelta(minutes=SESSION_REACTION_HORIZON_MIN), candles=candles,
        source=source, method="FIRST_CLUSTER_PREPRICE_TO_FINAL_CLUSTER_PLUS_5_MIN", generated_ts=generated_ts,
    )
    session_outcome["interaction_evaluation_status"] = "RULE_AVAILABLE_SELECTION_DEPENDENT"
    session_outcome["interaction_price_evidence"] = _interaction_evidence(outcomes)
    session_outcome["outcome_fingerprint"] = fingerprint({key: session_outcome.get(key, "") for key in OUTCOME_HEADERS if key not in {"outcome_fingerprint", "generated_ts"}})
    outcomes.append(session_outcome)
    return outcomes


def construct_outcomes_from_window_moves(
    *, session: Mapping[str, Any], members: Sequence[Mapping[str, Any]],
    cluster_moves: Mapping[str, Mapping[str, Any]], session_move: Mapping[str, Any], generated_ts: str,
) -> List[Dict[str, Any]]:
    """Normalize approved post-window API moves into the v2 outcome contract."""
    session_id = _norm(session.get("session_id"))
    normalized_members = normalize_session_members(session_id, members)
    clusters = release_clusters(session_id, normalized_members)
    outcomes: List[Dict[str, Any]] = []

    def from_move(level: str, target_id: str, event_id: str, cluster_id: str, start: datetime, end: datetime, move: Mapping[str, Any]) -> Dict[str, Any]:
        if _norm(move.get("status")) != "ok":
            return _outcome_row(
                level=level, target_id=target_id, session_id=session_id, event_id=event_id,
                cluster_id=cluster_id, start=start, end=end, candles=[], source=_norm(move.get("provider")),
                method="EVENT_RELATIVE_FIXED_DURATION|5" if level != "MARKET_SESSION" else "FIRST_CLUSTER_PREPRICE_TO_FINAL_CLUSTER_PLUS_5_MIN",
                generated_ts=generated_ts, rejection_reason="APPROVED_MARKET_PRICE_WINDOW_UNAVAILABLE",
            )
        candles = [
            {"timestamp": move.get("start_candle_ts"), "price": move.get("start_price")},
            {"timestamp": move.get("end_candle_ts"), "price": move.get("end_price")},
        ]
        return _outcome_row(
            level=level, target_id=target_id, session_id=session_id, event_id=event_id,
            cluster_id=cluster_id, start=start, end=end, candles=candles,
            source=_norm(move.get("provider")) or "APPROVED_USDJPY_WINDOW_MOVE",
            method="EVENT_RELATIVE_FIXED_DURATION|5" if level != "MARKET_SESSION" else "FIRST_CLUSTER_PREPRICE_TO_FINAL_CLUSTER_PLUS_5_MIN",
            generated_ts=generated_ts,
        )

    for cluster in clusters:
        release = _parse_ts(cluster["release_ts"])
        end = release + timedelta(minutes=EVENT_REACTION_HORIZON_MIN)
        cluster_outcome = from_move(
            "RELEASE_CLUSTER", cluster["release_cluster_id"], "", cluster["release_cluster_id"],
            release, end, cluster_moves.get(cluster["release_cluster_id"], {}),
        )
        outcomes.append(cluster_outcome)
        for event_id in cluster["member_event_ids"]:
            if cluster["member_count"] > 1:
                outcomes.append(_outcome_row(
                    level="EVENT", target_id=event_id, session_id=session_id, event_id=event_id,
                    cluster_id=cluster["release_cluster_id"], start=release, end=end, candles=[],
                    source=cluster_outcome["outcome_source"], method="EVENT_RELATIVE_FIXED_DURATION|5",
                    generated_ts=generated_ts, rejection_reason="EVENT_OUTCOME_NOT_SEPARABLY_EVALUABLE",
                ))
            else:
                event_row = dict(cluster_outcome)
                event_row.update({"outcome_level": "EVENT", "outcome_target_id": event_id, "event_id": event_id})
                event_row["outcome_id"] = "V2O_" + fingerprint({"level": "EVENT", "target": event_id, "session_id": session_id, "start": event_row["outcome_window_start_ts"], "end": event_row["outcome_window_end_ts"], "schema": SCHEMA_VERSION})[:28]
                event_row["outcome_fingerprint"] = fingerprint({key: event_row.get(key, "") for key in OUTCOME_HEADERS if key not in {"outcome_fingerprint", "generated_ts"}})
                outcomes.append(event_row)
    first = _parse_ts(clusters[0]["release_ts"])
    final = _parse_ts(clusters[-1]["release_ts"]) + timedelta(minutes=SESSION_REACTION_HORIZON_MIN)
    session_outcome = from_move("MARKET_SESSION", session_id, "", "", first, final, session_move)
    session_outcome["interaction_evaluation_status"] = "RULE_AVAILABLE_SELECTION_DEPENDENT"
    session_outcome["interaction_price_evidence"] = _interaction_evidence(outcomes)
    session_outcome["outcome_fingerprint"] = fingerprint({key: session_outcome.get(key, "") for key in OUTCOME_HEADERS if key not in {"outcome_fingerprint", "generated_ts"}})
    outcomes.append(session_outcome)
    return outcomes


def _magnitude_result(minimum: Any, maximum: Any, actual_pips: Any) -> Tuple[str, Any]:
    if minimum == "" or maximum == "":
        return "NOT_PREDICTED", ""
    if actual_pips == "":
        return "OUTCOME_UNAVAILABLE", ""
    magnitude = abs(float(actual_pips))
    if float(minimum) <= magnitude <= float(maximum):
        return "CORRECT", 0
    error = min(abs(magnitude - float(minimum)), abs(magnitude - float(maximum)))
    return "INCORRECT", round(error, 4)


def evaluate_prediction(
    prediction: Mapping[str, Any], path_rows: Sequence[Mapping[str, Any]], outcomes: Sequence[Mapping[str, Any]], generated_ts: str,
) -> List[Dict[str, Any]]:
    """Create one row per component without inventing interaction/driver truth."""
    if _norm(prediction.get("prediction_status")) != "FROZEN_PREOUTCOME":
        raise V2ValidationError("PREDICTION_NOT_FROZEN_PREOUTCOME")
    valid_outcomes = {(_norm(row.get("outcome_level")), _norm(row.get("outcome_target_id"))): row for row in outcomes if _norm(row.get("outcome_status")) == "VALID"}
    session_id = _norm(prediction.get("session_id"))
    session_outcome = valid_outcomes.get(("MARKET_SESSION", session_id))
    rows: List[Dict[str, Any]] = []

    def add(component: str, predicted: Any, actual: Any, result: str, *, outcome: Mapping[str, Any] | None = None,
            pmin: Any = "", pmax: Any = "", actual_pips: Any = "", abs_error: Any = "", note: str = "",
            direction_result: str = "", magnitude_result: str = "", reference: str = "") -> None:
        if component not in EVALUATION_COMPONENTS or result not in COMPONENT_RESULTS:
            raise V2ValidationError("INVALID_EVALUATION_COMPONENT_OR_RESULT")
        row = {
            "prediction_id": prediction["prediction_id"], "session_id": session_id,
            "provider": prediction["provider"], "model": prediction["model"], "pack_arm": prediction["pack_arm"],
            "evaluation_component": component, "component_index": len(rows) + 1,
            "prediction_reference_id": reference or prediction["prediction_id"],
            "outcome_reference_id": _norm((outcome or {}).get("outcome_id")), "predicted_value": predicted,
            "actual_value": actual, "predicted_pips_min": pmin, "predicted_pips_max": pmax,
            "actual_pips": actual_pips, "absolute_pip_error": abs_error, "direction_result": direction_result,
            "magnitude_result": magnitude_result, "component_result": result,
            "evaluation_status": "EVALUATED" if result in {"CORRECT", "PARTIALLY_CORRECT", "INCORRECT"} else result,
            "evaluation_note": note, "path_components_predicted": "", "path_components_evaluable": "",
            "path_components_correct": "", "path_component_accuracy": "",
            "prediction_fingerprint": prediction["prediction_fingerprint"],
            "outcome_fingerprint": _norm((outcome or {}).get("outcome_fingerprint")),
            "evaluation_schema_version": SCHEMA_VERSION, "generated_ts": _ts(generated_ts),
        }
        row["evaluation_id"] = "V2E_" + fingerprint({"prediction_id": row["prediction_id"], "component": component, "index": row["component_index"]})[:28]
        row["evaluation_fingerprint"] = fingerprint({key: row.get(key, "") for key in EVALUATION_HEADERS if key not in {"evaluation_fingerprint", "generated_ts"}})
        rows.append(row)

    add("PRIMARY_DRIVER_CHOICE", prediction.get("primary_driver_event_id"), "", "NOT_YET_EVALUABLE",
        note="No authoritative causal member-ranking rule exists; observable cluster evidence is retained separately.")
    secondary_status = _norm(prediction.get("secondary_driver_status"))
    secondary_result = "NOT_APPLICABLE" if secondary_status == "NO_MEANINGFUL_SECONDARY_DRIVER" else "NOT_YET_EVALUABLE"
    if prediction.get("secondary_driver_release_cluster_id") == prediction.get("primary_driver_release_cluster_id") and secondary_status == "SELECTED":
        secondary_result = "NOT_SEPARABLY_EVALUABLE"
    add("SECONDARY_DRIVER_CHOICE", prediction.get("secondary_driver_event_id"), "", secondary_result,
        note="Same-cluster members are not causally separable; no authoritative driver ground truth was found.")

    def reaction(prefix: str) -> Tuple[str, str]:
        target_type = _norm(prediction.get(prefix + "_reaction_target_type"))
        target_id = _norm(prediction.get(prefix + "_reaction_target_id"))
        outcome = valid_outcomes.get((target_type, target_id))
        component_prefix = prefix.upper()
        direction_component = component_prefix + "_REACTION_DIRECTION"
        magnitude_component = component_prefix + "_REACTION_MAGNITUDE"
        if prefix == "secondary" and _norm(prediction.get("secondary_reaction_status")) == "SAME_CLUSTER_NOT_SEPARATELY_PREDICTABLE":
            add(direction_component, prediction.get(prefix + "_reaction_direction"), "", "NOT_SEPARABLY_EVALUABLE")
            add(magnitude_component, "", "", "NOT_SEPARABLY_EVALUABLE")
            return "NOT_SEPARABLY_EVALUABLE", "NOT_SEPARABLY_EVALUABLE"
        if prefix == "secondary" and _norm(prediction.get("secondary_reaction_status")) != "PREDICTED":
            result = "NOT_PREDICTED" if _norm(prediction.get("secondary_reaction_status")) in {"NOT_PREDICTED", "UNCERTAIN"} else "NOT_APPLICABLE"
            add(direction_component, prediction.get(prefix + "_reaction_direction"), "", result)
            add(magnitude_component, "", "", result)
            return result, result
        if not outcome:
            add(direction_component, prediction.get(prefix + "_reaction_direction"), "", "OUTCOME_UNAVAILABLE")
            add(magnitude_component, "", "", "OUTCOME_UNAVAILABLE")
            return "OUTCOME_UNAVAILABLE", "OUTCOME_UNAVAILABLE"
        predicted_direction = _norm(prediction.get(prefix + "_reaction_direction"))
        actual_direction = _norm(outcome.get("realized_direction"))
        direction_result = "NOT_PREDICTED" if predicted_direction == "NOT_PREDICTED" else "CORRECT" if predicted_direction == actual_direction else "INCORRECT"
        add(direction_component, predicted_direction, actual_direction, direction_result, outcome=outcome, direction_result=direction_result)
        magnitude, error = _magnitude_result(prediction.get(prefix + "_expected_pips_min"), prediction.get(prefix + "_expected_pips_max"), outcome.get("realized_pips"))
        add(magnitude_component, f"{prediction.get(prefix + '_expected_pips_min')}..{prediction.get(prefix + '_expected_pips_max')}", outcome.get("realized_pips"), magnitude,
            outcome=outcome, pmin=prediction.get(prefix + "_expected_pips_min"), pmax=prediction.get(prefix + "_expected_pips_max"), actual_pips=outcome.get("realized_pips"), abs_error=error, magnitude_result=magnitude)
        return direction_result, magnitude

    primary_direction_result, primary_magnitude_result = reaction("primary")
    secondary_direction_result, secondary_magnitude_result = reaction("secondary")
    interaction_status = _norm(prediction.get("interaction_status"))
    primary_cluster_id = _norm(prediction.get("primary_driver_release_cluster_id"))
    secondary_cluster_id = _norm(prediction.get("secondary_driver_release_cluster_id"))
    primary_cluster_outcome = valid_outcomes.get(("RELEASE_CLUSTER", primary_cluster_id))
    secondary_cluster_outcome = valid_outcomes.get(("RELEASE_CLUSTER", secondary_cluster_id))
    interaction_evidence: Dict[str, Any] = {}
    if interaction_status in {"NOT_APPLICABLE_SAME_CLUSTER", "NO_SECONDARY_DRIVER"}:
        interaction_result = "NOT_APPLICABLE"
        actual_interaction = "NOT_APPLICABLE"
        interaction_note = _json({"reason": interaction_status, "rule_version": INTERACTION_RULE_VERSION, "rule_fingerprint": interaction_rule_fingerprint()})
    elif interaction_status in {"UNCERTAIN", "NOT_PREDICTED"}:
        interaction_result = "NOT_PREDICTED"
        actual_interaction = ""
        interaction_note = _json({"reason": "INTERACTION_NOT_PREDICTED", "rule_version": INTERACTION_RULE_VERSION, "rule_fingerprint": interaction_rule_fingerprint()})
    elif not primary_cluster_outcome or not secondary_cluster_outcome or not session_outcome:
        interaction_result = "OUTCOME_UNAVAILABLE"
        actual_interaction = "NOT_EVALUABLE"
        interaction_note = _json({"reason": "REQUIRED_INTERACTION_OUTCOME_UNAVAILABLE", "rule_version": INTERACTION_RULE_VERSION, "rule_fingerprint": interaction_rule_fingerprint()})
    else:
        interaction_evidence = classify_realized_interaction(primary_cluster_outcome, secondary_cluster_outcome, session_outcome)
        actual_interaction = interaction_evidence["interaction_class"]
        if interaction_evidence["evaluation_status"] != "EVALUABLE":
            interaction_result = "OUTCOME_UNAVAILABLE" if actual_interaction == "NOT_EVALUABLE" else "NOT_APPLICABLE"
        else:
            interaction_result = "CORRECT" if _norm(prediction.get("primary_secondary_interaction")) == actual_interaction else "INCORRECT"
        interaction_note = _json(interaction_evidence)
    add("PRIMARY_SECONDARY_INTERACTION", prediction.get("primary_secondary_interaction"), actual_interaction, interaction_result,
        outcome=session_outcome, note=interaction_note)

    if session_outcome:
        predicted_direction = _norm(prediction.get("session_forecast_direction"))
        actual_direction = _norm(session_outcome.get("realized_direction"))
        direction_result = "NOT_PREDICTED" if predicted_direction == "NO_CLEAR_DIRECTION" else "CORRECT" if predicted_direction == actual_direction else "INCORRECT"
        add("SESSION_DIRECTION", predicted_direction, actual_direction, direction_result, outcome=session_outcome, direction_result=direction_result)
        magnitude, error = _magnitude_result(prediction.get("session_expected_pips_min"), prediction.get("session_expected_pips_max"), session_outcome.get("realized_pips"))
        add("SESSION_MAGNITUDE", f"{prediction.get('session_expected_pips_min')}..{prediction.get('session_expected_pips_max')}", session_outcome.get("realized_pips"), magnitude,
            outcome=session_outcome, pmin=prediction.get("session_expected_pips_min"), pmax=prediction.get("session_expected_pips_max"), actual_pips=session_outcome.get("realized_pips"), abs_error=error, magnitude_result=magnitude)
        session_direction_result, session_magnitude_result = direction_result, magnitude
    else:
        add("SESSION_DIRECTION", prediction.get("session_forecast_direction"), "", "OUTCOME_UNAVAILABLE")
        add("SESSION_MAGNITUDE", "", "", "OUTCOME_UNAVAILABLE")
        session_direction_result = session_magnitude_result = "OUTCOME_UNAVAILABLE"

    directional_results: List[str] = [primary_direction_result, session_direction_result]
    strict_results: List[str] = [primary_direction_result, primary_magnitude_result, session_direction_result, session_magnitude_result]
    if secondary_direction_result != "NOT_APPLICABLE":
        directional_results.append(secondary_direction_result)
    if secondary_magnitude_result != "NOT_APPLICABLE":
        strict_results.extend([secondary_direction_result, secondary_magnitude_result])
    if interaction_result != "NOT_APPLICABLE":
        directional_results.append(interaction_result)
        strict_results.append(interaction_result)
    for stage in sorted(path_rows, key=lambda row: int(row["path_stage_index"])):
        if stage["path_stage_type"] == "BETWEEN_RELEASES":
            if interaction_evidence.get("evaluation_status") == "EVALUABLE":
                actual_behavior = interaction_evidence["between_release_behavior"]
                predicted_behavior = _norm(stage.get("expected_behavior"))
                behavior_result = "NOT_PREDICTED" if predicted_behavior == "UNKNOWN" else "CORRECT" if predicted_behavior == actual_behavior else "INCORRECT"
                behavior_note = _json({
                    "reason": interaction_evidence["between_release_reason"],
                    "inter_release_move_pips": interaction_evidence["inter_release_move_pips"],
                    "rule_version": INTERACTION_RULE_VERSION, "rule_fingerprint": interaction_rule_fingerprint(),
                })
            elif interaction_result == "NOT_APPLICABLE":
                actual_behavior, behavior_result, behavior_note = "", "NOT_APPLICABLE", "No distinct selected release-cluster pair."
            else:
                actual_behavior, behavior_result, behavior_note = "", "OUTCOME_UNAVAILABLE", "Selected-cluster price boundaries unavailable."
            add("BETWEEN_RELEASE_BEHAVIOR", stage.get("expected_behavior"), actual_behavior, behavior_result,
                reference=stage["stage_fingerprint"], note=behavior_note)
            if behavior_result != "NOT_APPLICABLE":
                strict_results.append(behavior_result)
            continue
        level = "MARKET_SESSION" if stage["path_target_type"] == "MARKET_SESSION" else stage["path_target_type"]
        outcome = valid_outcomes.get((level, _norm(stage.get("path_target_id"))))
        if not outcome:
            add("PATH_STAGE_DIRECTION", stage.get("expected_direction"), "", "OUTCOME_UNAVAILABLE", reference=stage["stage_fingerprint"])
            add("PATH_STAGE_MAGNITUDE", "", "", "OUTCOME_UNAVAILABLE", reference=stage["stage_fingerprint"])
            directional_results.append("OUTCOME_UNAVAILABLE")
            strict_results.extend(["OUTCOME_UNAVAILABLE", "OUTCOME_UNAVAILABLE"])
            continue
        predicted_direction = _norm(stage.get("expected_direction"))
        actual_direction = _norm(outcome.get("realized_direction"))
        result = "NOT_PREDICTED" if predicted_direction == "NOT_PREDICTED" else "CORRECT" if predicted_direction == actual_direction else "INCORRECT"
        add("PATH_STAGE_DIRECTION", predicted_direction, actual_direction, result, outcome=outcome, reference=stage["stage_fingerprint"], direction_result=result)
        magnitude, error = _magnitude_result(stage.get("expected_pips_min"), stage.get("expected_pips_max"), outcome.get("realized_pips"))
        add("PATH_STAGE_MAGNITUDE", f"{stage.get('expected_pips_min')}..{stage.get('expected_pips_max')}", outcome.get("realized_pips"), magnitude,
            outcome=outcome, reference=stage["stage_fingerprint"], pmin=stage.get("expected_pips_min"), pmax=stage.get("expected_pips_max"), actual_pips=outcome.get("realized_pips"), abs_error=error, magnitude_result=magnitude)
        directional_results.append(result)
        strict_results.extend([result, magnitude])

    def aggregate(results: Sequence[str]) -> str:
        applicable = [result for result in results if result != "NOT_APPLICABLE"]
        if not applicable:
            return "NOT_PREDICTED"
        for status in ("NOT_SEPARABLY_EVALUABLE", "NOT_YET_EVALUABLE", "OUTCOME_UNAVAILABLE", "NOT_PREDICTED"):
            if status in applicable:
                return status
        if "INCORRECT" in applicable:
            return "INCORRECT"
        if "PARTIALLY_CORRECT" in applicable:
            return "PARTIALLY_CORRECT"
        return "CORRECT"

    predicted_count = len(strict_results)
    evaluable = [result for result in strict_results if result in {"CORRECT", "PARTIALLY_CORRECT", "INCORRECT"}]
    correct = [result for result in evaluable if result == "CORRECT"]
    directional_sequence = aggregate(directional_results)
    strict_result = aggregate(strict_results)
    for component, result in (("PATH_DIRECTIONAL_SEQUENCE", directional_sequence), ("COMPLETE_PATH_STRICT", strict_result)):
        add(component, "ordered predicted path", "ordered realized path", result, outcome=session_outcome)
        rows[-1].update({
            "path_components_predicted": predicted_count, "path_components_evaluable": len(evaluable),
            "path_components_correct": len(correct),
            "path_component_accuracy": round(len(correct) / len(evaluable), 6) if evaluable else "",
        })
        rows[-1]["evaluation_fingerprint"] = fingerprint({key: rows[-1].get(key, "") for key in EVALUATION_HEADERS if key not in {"evaluation_fingerprint", "generated_ts"}})
    return rows


def rows_for_headers(rows: Iterable[Mapping[str, Any]], headers: Sequence[str]) -> List[List[Any]]:
    return [[row.get(header, "") for header in headers] for row in rows]


def _a1_column(index: int) -> str:
    value = index + 1
    result = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(65 + remainder) + result
    return result


def append_shadow_rows_to_workbook(
    *, predictions: Sequence[Mapping[str, Any]] = (), paths: Sequence[Mapping[str, Any]] = (),
    outcomes: Sequence[Mapping[str, Any]] = (), evaluations: Sequence[Mapping[str, Any]] = (),
    spreadsheet_id: str = "1_gZGnd6h3VzdiBvGBHRSxn78KW8tsOi2UEc6Y_Sc23Q",
) -> Dict[str, int]:
    """Append validated v2 rows idempotently; legacy sheets are never addressed."""
    from automation.google_clients import build_sheets_service, get_sheet_values, load_credentials

    service = build_sheets_service(load_credentials(interactive=False))
    plans = [
        (PREDICTION_SHEET, PREDICTION_HEADERS, predictions, "prediction_id"),
        (PATH_SHEET, PATH_HEADERS, paths, "stage_fingerprint"),
        (OUTCOME_SHEET, OUTCOME_HEADERS, outcomes, "outcome_id"),
        (EVALUATION_SHEET, EVALUATION_HEADERS, evaluations, "evaluation_id"),
    ]
    counts: Dict[str, int] = {}
    for sheet, headers, incoming, identity_field in plans:
        if not incoming:
            counts[sheet] = 0
            continue
        current_header = get_sheet_values(service, spreadsheet_id, f"'{sheet}'!1:1")
        if not current_header or current_header[0] != list(headers):
            raise V2ValidationError("V2_WORKBOOK_HEADER_MISMATCH:" + sheet)
        existing = {
            _norm(row[0]) for row in get_sheet_values(service, spreadsheet_id, f"'{sheet}'!A2:A") if row and _norm(row[0])
        }
        # Path identity is not the first column, so read the exact fingerprint column.
        if sheet == PATH_SHEET:
            column_index = headers.index(identity_field)
            column_name = _a1_column(column_index)
            existing = {
                _norm(row[0]) for row in get_sheet_values(service, spreadsheet_id, f"'{sheet}'!{column_name}2:{column_name}") if row and _norm(row[0])
            }
        selected = [dict(row) for row in incoming if _norm(row.get(identity_field)) and _norm(row.get(identity_field)) not in existing]
        if selected:
            service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=f"'{sheet}'!A:{_a1_column(len(headers) - 1)}",
                valueInputOption="RAW", insertDataOption="INSERT_ROWS",
                body={"values": rows_for_headers(selected, headers)},
            ).execute()
        counts[sheet] = len(selected)
    return counts


def schema_dictionary() -> List[Dict[str, Any]]:
    allowed: Dict[str, str] = {
        "secondary_driver_status": "|".join(sorted(SECONDARY_STATUSES)),
        "primary_reaction_target_type": "EVENT|RELEASE_CLUSTER",
        "primary_reaction_direction": "|".join(sorted(DIRECTIONS)),
        "secondary_reaction_status": "|".join(sorted(SECONDARY_REACTION_STATUSES)),
        "secondary_reaction_direction": "|".join(sorted(DIRECTIONS)),
        "interaction_status": "|".join(sorted(INTERACTION_STATUSES)),
        "primary_secondary_interaction": "|".join(sorted(INTERACTIONS)),
        "session_forecast_direction": "|".join(sorted(FINAL_DIRECTIONS)),
        "path_stage_type": "|".join(sorted(PATH_STAGE_TYPES)),
        "expected_behavior": "|".join(sorted(PATH_BEHAVIORS)),
        "outcome_level": "EVENT|RELEASE_CLUSTER|MARKET_SESSION",
        "evaluation_component": "|".join(sorted(EVALUATION_COMPONENTS)),
        "component_result": "|".join(sorted(COMPONENT_RESULTS)),
    }
    sheets = {
        PREDICTION_SHEET: PREDICTION_HEADERS, PATH_SHEET: PATH_HEADERS,
        OUTCOME_SHEET: OUTCOME_HEADERS, EVALUATION_SHEET: EVALUATION_HEADERS,
    }
    rows: List[Dict[str, Any]] = []
    for sheet, headers in sheets.items():
        for order, field in enumerate(headers, start=1):
            is_fingerprint = field.endswith("fingerprint")
            is_ts = field.endswith("_ts") or field == "generated_ts"
            data_type = "TIMESTAMP_UTC" if is_ts else "SHA256" if is_fingerprint else "JSON_OR_TEXT" if field in {"session_member_event_ids", "session_member_release_cluster_ids", "information_used", "missing_information", "source_canonical_outcome_ids", "interaction_price_evidence"} else "NUMBER" if any(token in field for token in ("pips", "confidence", "count", "index", "price", "holding_min", "horizon_min", "accuracy")) else "BOOLEAN" if field == "no_signal_flag" else "STRING"
            rows.append({
                "sheet_name": sheet, "field_name": field, "field_order": order, "data_type": data_type,
                "required": "TRUE", "allowed_values": allowed.get(field, ""),
                "description": field.replace("_", " "),
                "scientific_role": "PREDICTION" if sheet == PREDICTION_SHEET else "PREDICTED_PATH" if sheet == PATH_SHEET else "OUTCOME" if sheet == OUTCOME_SHEET else "EVALUATION",
                "missing_value_rule": "Explicit status/enumerated unavailable state; never infer from final direction." if field in {"secondary_driver_event_id", "actual_interaction_class", "actual_value"} else "Required unless the corresponding explicit status makes it not applicable.",
                "schema_version": SCHEMA_VERSION,
            })
    rule_rows = [
        ("release_cluster_definition", "Exact same release timestamp/same_minute_group_key within one frozen session."),
        ("event_reaction_horizon", "5 minutes; EVENT_RELATIVE_FIXED_DURATION."),
        ("session_reaction_horizon", "First valid price strictly before first cluster to first valid price at/after final cluster plus 5 minutes."),
        ("pip_convention", "USDJPY price delta divided by 0.01."),
        ("direction_thresholds", "Config MR_FLAT_MAX_ABS_PIPS=1; UP >= +1, DOWN <= -1, otherwise FLAT."),
        ("interaction_definitions", f"{INTERACTION_RULE_VERSION}; selected distinct cluster P0-P3 classifier; rule_fingerprint={interaction_rule_fingerprint()}; provider accuracy prohibited."),
        ("same_time_release_rule", "One release-cluster outcome; member events are NOT_SEPARABLY_EVALUABLE."),
        ("path_evaluation_rule", "SESSION_DIRECTION remains headline; directional and strict path rows are separate diagnostics."),
        ("fingerprint_inputs", "Canonical scientific fields in header order; generated_ts and raw_output excluded where documented."),
    ]
    for index, (field, description) in enumerate(rule_rows, start=1):
        rows.append({
            "sheet_name": SCHEMA_SHEET, "field_name": field, "field_order": index,
            "data_type": "RULE", "required": "TRUE", "allowed_values": "", "description": description,
            "scientific_role": "SCHEMA_RULE", "missing_value_rule": "NOT_APPLICABLE", "schema_version": SCHEMA_VERSION,
        })
    return rows
