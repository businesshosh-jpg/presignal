#!/usr/bin/env python3
"""Compact contract for Immediate Impulse Outcome recovery, Moves 1-2 only.

This module freezes a small additive supplement contract. It does not modify the
accepted Event-Path v1.1 contract or any completed Round 1 evidence.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIR = ROOT / "contracts" / "presignal_v21_immediate_impulse_outcome_recovery_r1"

CONTRACT_ID = "presignal_immediate_impulse_outcome_recovery_r1"
SCHEMA_VERSION = "1.0.0"
SCHEMA_ID = "presignal.immediate_impulse_outcome_recovery.r1"
DETECTOR_SCHEMA_ID = "presignal.immediate_impulse_detector_parameters.r1"
MAXIMUM_DETECTION_WINDOW_SECONDS = 120

STATUSES = {
    "STRICT_AVAILABLE",
    "RESOLUTION_LIMITED",
    "APPROXIMATION_ONLY",
    "OUTCOME_UNAVAILABLE",
}
DIRECTIONS = {"UP", "DOWN", "FLAT", "UNAVAILABLE"}
PACK_ARMS = {"BASELINE", "FULL_CONTEXT"}
ANCHOR_METHODS = {
    "MEDIAN_VALID_MIDPOINT_T_MINUS_10S_TO_T_MINUS_2S",
    "LAST_VALID_MIDPOINT_STRICTLY_BEFORE_T",
}
MARKET_DATA_RESOLUTIONS = {
    "TICK",
    "SECOND",
    "FIVE_SECOND",
    "ONE_MINUTE_OHLC",
    "OTHER_LIMITED",
}
DETECTOR_PARAMETER_NAMES = (
    "minimum_move_pips",
    "minimum_persistence_seconds",
    "directional_retention_pips",
    "maximum_temporary_violations",
    "maximum_detection_window_seconds",
)
REQUIRED_FIELDS = (
    "episode_id",
    "forecast_id",
    "provider",
    "model",
    "pack_arm",
    "release_timestamp",
    "market_data_source",
    "market_data_resolution",
    "observation_start_timestamp",
    "observation_end_timestamp",
    "observation_count",
    "raw_observation_artifact_reference",
    "anchor_method",
    "anchor_fallback_reason",
    "anchor_timestamp",
    "anchor_price",
    "detector_parameters",
    "immediate_impulse_status",
    "immediate_impulse_direction",
    "immediate_impulse_start_timestamp",
    "immediate_impulse_threshold_cross_timestamp",
    "immediate_impulse_peak_timestamp",
    "immediate_impulse_peak_pips",
    "immediate_impulse_adverse_pips",
    "immediate_impulse_persistence_seconds",
    "immediate_impulse_reversed_by_120s",
    "net_move_at_120s_pips",
    "net_direction_at_120s",
    "contract_version",
    "schema_version",
    "evaluator_version",
    "generated_timestamp",
)


class ImmediateImpulseContractError(ValueError):
    """Raised when a compact Immediate Impulse record violates the frozen shape."""


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def load_outcome_schema() -> dict[str, Any]:
    return read_json(CONTRACT_DIR / "immediate_impulse_outcome_contract_r1.json")


def load_detector_schema() -> dict[str, Any]:
    return read_json(CONTRACT_DIR / "immediate_impulse_detector_parameters_r1.json")


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ImmediateImpulseContractError(code)


def _timestamp(value: Any, code: str) -> datetime:
    _require(isinstance(value, str) and value.endswith("Z"), code)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ImmediateImpulseContractError(code) from exc


def _string(value: Any, code: str) -> str:
    _require(isinstance(value, str) and value.strip() != "", code)
    return value


def _number(value: Any, code: str) -> float:
    _require(isinstance(value, (int, float)) and not isinstance(value, bool), code)
    result = float(value)
    _require(result == result and result not in (float("inf"), float("-inf")), code)
    return result


def _integer(value: Any, code: str, minimum: int | None = None) -> int:
    _require(isinstance(value, int) and not isinstance(value, bool), code)
    if minimum is not None:
        _require(value >= minimum, code)
    return value


def validate_detector_parameters(record: Mapping[str, Any]) -> None:
    _require(isinstance(record, Mapping), "DETECTOR_PARAMETERS_NOT_OBJECT")
    _require(set(record) == set(DETECTOR_PARAMETER_NAMES), "DETECTOR_PARAMETERS_FIELD_SET")
    _number(record["minimum_move_pips"], "DETECTOR_MINIMUM_MOVE_PIPS")
    _integer(record["minimum_persistence_seconds"], "DETECTOR_MINIMUM_PERSISTENCE_SECONDS", 0)
    _number(record["directional_retention_pips"], "DETECTOR_DIRECTIONAL_RETENTION_PIPS")
    _integer(record["maximum_temporary_violations"], "DETECTOR_MAXIMUM_TEMPORARY_VIOLATIONS", 0)
    _require(
        record["maximum_detection_window_seconds"] == MAXIMUM_DETECTION_WINDOW_SECONDS,
        "DETECTOR_MAXIMUM_DETECTION_WINDOW_SECONDS",
    )


def validate_outcome_record(record: Mapping[str, Any]) -> None:
    _require(isinstance(record, Mapping), "OUTCOME_NOT_OBJECT")
    _require(set(record) == set(REQUIRED_FIELDS), "OUTCOME_FIELD_SET")
    for key in (
        "episode_id",
        "forecast_id",
        "provider",
        "model",
        "release_timestamp",
        "market_data_source",
        "raw_observation_artifact_reference",
        "evaluator_version",
    ):
        _string(record[key], "OUTCOME_" + key.upper())
    _require(record["pack_arm"] in PACK_ARMS, "OUTCOME_PACK_ARM")
    _require(record["market_data_resolution"] in MARKET_DATA_RESOLUTIONS, "OUTCOME_MARKET_DATA_RESOLUTION")
    start = _timestamp(record["observation_start_timestamp"], "OUTCOME_OBSERVATION_START_TIMESTAMP")
    end = _timestamp(record["observation_end_timestamp"], "OUTCOME_OBSERVATION_END_TIMESTAMP")
    release = _timestamp(record["release_timestamp"], "OUTCOME_RELEASE_TIMESTAMP")
    anchor_ts = _timestamp(record["anchor_timestamp"], "OUTCOME_ANCHOR_TIMESTAMP")
    _require(start <= end, "OUTCOME_OBSERVATION_WINDOW_ORDER")
    _require(start <= release <= end, "OUTCOME_RELEASE_INSIDE_WINDOW")
    _require(anchor_ts < release, "OUTCOME_ANCHOR_STRICTLY_PRE_RELEASE")
    _integer(record["observation_count"], "OUTCOME_OBSERVATION_COUNT", 0)
    _require(record["anchor_method"] in ANCHOR_METHODS, "OUTCOME_ANCHOR_METHOD")
    if record["anchor_method"] == "MEDIAN_VALID_MIDPOINT_T_MINUS_10S_TO_T_MINUS_2S":
        _require(record["anchor_fallback_reason"] in ("", None), "OUTCOME_ANCHOR_FALLBACK_REASON")
    else:
        _string(record["anchor_fallback_reason"], "OUTCOME_ANCHOR_FALLBACK_REASON")
    _number(record["anchor_price"], "OUTCOME_ANCHOR_PRICE")
    validate_detector_parameters(record["detector_parameters"])
    _require(record["immediate_impulse_status"] in STATUSES, "OUTCOME_IMMEDIATE_STATUS")
    _require(record["immediate_impulse_direction"] in DIRECTIONS, "OUTCOME_IMMEDIATE_DIRECTION")
    _require(record["net_direction_at_120s"] in DIRECTIONS, "OUTCOME_NET_DIRECTION_AT_120S")
    _require(record["contract_version"] == CONTRACT_ID, "OUTCOME_CONTRACT_VERSION")
    _require(record["schema_version"] == SCHEMA_VERSION, "OUTCOME_SCHEMA_VERSION")
    _timestamp(record["generated_timestamp"], "OUTCOME_GENERATED_TIMESTAMP")

    if record["immediate_impulse_status"] == "OUTCOME_UNAVAILABLE":
        for key in (
            "immediate_impulse_start_timestamp",
            "immediate_impulse_threshold_cross_timestamp",
            "immediate_impulse_peak_timestamp",
            "immediate_impulse_peak_pips",
            "immediate_impulse_adverse_pips",
            "immediate_impulse_persistence_seconds",
            "immediate_impulse_reversed_by_120s",
            "net_move_at_120s_pips",
        ):
            _require(record[key] is None, "OUTCOME_UNAVAILABLE_" + key.upper())
        _require(record["immediate_impulse_direction"] == "UNAVAILABLE", "OUTCOME_UNAVAILABLE_DIRECTION")
        _require(record["net_direction_at_120s"] == "UNAVAILABLE", "OUTCOME_UNAVAILABLE_NET_DIRECTION")
        return

    if record["immediate_impulse_start_timestamp"] is not None:
        start_ts = _timestamp(record["immediate_impulse_start_timestamp"], "OUTCOME_IMMEDIATE_START_TIMESTAMP")
        _require(start_ts >= release, "OUTCOME_IMMEDIATE_START_POST_RELEASE")
    if record["immediate_impulse_threshold_cross_timestamp"] is not None:
        cross_ts = _timestamp(
            record["immediate_impulse_threshold_cross_timestamp"],
            "OUTCOME_IMMEDIATE_THRESHOLD_CROSS_TIMESTAMP",
        )
        _require(cross_ts >= release, "OUTCOME_THRESHOLD_CROSS_POST_RELEASE")
    if record["immediate_impulse_peak_timestamp"] is not None:
        peak_ts = _timestamp(record["immediate_impulse_peak_timestamp"], "OUTCOME_IMMEDIATE_PEAK_TIMESTAMP")
        _require(peak_ts >= release, "OUTCOME_PEAK_POST_RELEASE")

    for key in ("immediate_impulse_peak_pips", "immediate_impulse_adverse_pips", "net_move_at_120s_pips"):
        if record[key] is not None:
            _number(record[key], "OUTCOME_" + key.upper())
    if record["immediate_impulse_persistence_seconds"] is not None:
        _integer(record["immediate_impulse_persistence_seconds"], "OUTCOME_IMMEDIATE_PERSISTENCE_SECONDS", 0)
    if record["immediate_impulse_reversed_by_120s"] is not None:
        _require(isinstance(record["immediate_impulse_reversed_by_120s"], bool), "OUTCOME_IMMEDIATE_REVERSED_BY_120S")

    if record["immediate_impulse_status"] == "STRICT_AVAILABLE":
        _require(record["market_data_resolution"] in {"TICK", "SECOND", "FIVE_SECOND"}, "OUTCOME_STRICT_RESOLUTION")
        _require(record["immediate_impulse_direction"] in {"UP", "DOWN", "FLAT"}, "OUTCOME_STRICT_DIRECTION")
    elif record["immediate_impulse_status"] == "APPROXIMATION_ONLY":
        _require(record["market_data_resolution"] == "ONE_MINUTE_OHLC", "OUTCOME_APPROXIMATION_RESOLUTION")
    elif record["immediate_impulse_status"] == "RESOLUTION_LIMITED":
        _require(record["market_data_resolution"] in {"ONE_MINUTE_OHLC", "OTHER_LIMITED"}, "OUTCOME_LIMITED_RESOLUTION")


__all__ = [
    "ANCHOR_METHODS",
    "CONTRACT_DIR",
    "CONTRACT_ID",
    "DETECTOR_PARAMETER_NAMES",
    "DETECTOR_SCHEMA_ID",
    "DIRECTIONS",
    "ImmediateImpulseContractError",
    "MARKET_DATA_RESOLUTIONS",
    "MAXIMUM_DETECTION_WINDOW_SECONDS",
    "PACK_ARMS",
    "REQUIRED_FIELDS",
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "STATUSES",
    "load_detector_schema",
    "load_outcome_schema",
    "validate_detector_parameters",
    "validate_outcome_record",
]
