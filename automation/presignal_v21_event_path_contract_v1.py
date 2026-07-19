#!/usr/bin/env python3
"""Fail-closed validator for the frozen PreSignal v2.1 Event-Path contract.

This module is intentionally a contract validator. It performs no provider, market-data,
workbook, Apps Script, or Google Sheets operation.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from statistics import mean
from typing import Any, Mapping, Sequence

SYSTEM_VERSION = "presignal_v2.1"
CONTRACT_VERSION = "presignal_event_path_contract_v1"
SCHEMA_VERSION = "2.1.0"
HORIZONS = (5, 15, 30, 60)
FLAT_MAX_ABS_PIPS = 1.0
DIRECTIONS = {"UP", "DOWN", "FLAT", "UNCERTAIN"}
OUTCOME_DIRECTIONS = {"UP", "DOWN", "FLAT", "UNAVAILABLE"}
ARMS = {"BASELINE", "FULL_CONTEXT"}
SELECTIONS = {"PENDING", "FORECAST", "WATCH", "IGNORE", "NO_SIGNAL"}

EPISODE_FIELDS = [
    "object", "schema_version", "system_version", "episode_id", "session_id", "country", "episode_family", "release_ts", "forecast_cutoff_ts", "member_event_count", "member_event_ids", "member_indicator_names", "primary_event_id", "primary_indicator_name", "secondary_event_ids", "secondary_indicator_names", "selection_status", "selection_reason", "same_time_cluster_flag", "created_ts", "updated_ts", "status", "error_message",
]
PREDICTION_FIELDS = [
    "object", "schema_version", "system_version", "run_id", "prediction_id", "episode_id", "session_id", "provider", "model", "information_arm", "pack_id", "pack_fingerprint", "forecast_created_ts", "forecast_cutoff_ts", "prediction_target_type", "prediction_target_id", "primary_event_id", "secondary_event_ids", "no_signal_flag", "no_signal_reason", "confidence", "expected_initial_direction", "expected_reversal_flag", "expected_reversal_horizon_min", "expected_path_summary", "information_used", "missing_information", "invalidation_condition", "raw_output", "prompt_tokens", "completion_tokens", "latency_ms", "prediction_fingerprint", "status", "error_message",
]
PATH_FIELDS = [
    "object", "schema_version", "system_version", "run_id", "prediction_id", "path_id", "episode_id", "provider", "model", "information_arm", "stage_index", "stage_type", "target_type", "target_id", "horizon_min", "expected_direction", "expected_pips_min", "expected_pips_max", "stage_confidence", "continuation_probability", "reversal_probability", "stage_reason", "invalidation_condition", "stage_fingerprint", "created_ts", "status", "error_message",
]
OUTCOME_FIELDS = [
    "object", "schema_version", "system_version", "outcome_id", "episode_id", "session_id", "release_ts", "anchor_price_ts", "anchor_price", "price_5m", "price_15m", "price_30m", "price_60m", "pips_5m", "pips_15m", "pips_30m", "pips_60m", "direction_5m", "direction_15m", "direction_30m", "direction_60m", "max_up_pips", "max_down_pips", "max_up_ts", "max_down_ts", "initial_direction", "reversal_flag", "reversal_ts", "intervening_event_flag", "market_data_provider", "source_lineage", "acquisition_ts", "outcome_fingerprint", "status", "error_message",
]
EVALUATION_FIELDS = [
    "object", "schema_version", "system_version", "evaluation_id", "run_id", "prediction_id", "outcome_id", "episode_id", "provider", "model", "information_arm", "direction_5m_ok", "direction_15m_ok", "direction_30m_ok", "direction_60m_ok", "magnitude_15m_error", "reversal_ok", "no_signal_ok", "primary_endpoint_name", "primary_endpoint_value", "overall_path_score", "evaluation_note", "evaluation_contract_version", "evaluation_fingerprint", "generated_ts", "status", "error_message",
]


class ContractValidationError(ValueError):
    """A frozen-contract invariant was not met."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _short(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()[:20]


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ContractValidationError(code)


def _timestamp(value: Any, code: str) -> datetime:
    _require(isinstance(value, str) and value.endswith("Z"), code)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractValidationError(code) from exc
    _require(parsed.tzinfo is not None and parsed.utcoffset() == timezone.utc.utcoffset(parsed), code)
    return parsed


def _number(value: Any, code: str, minimum: float | None = None, maximum: float | None = None) -> float:
    _require(isinstance(value, (int, float)) and not isinstance(value, bool), code)
    result = float(value)
    _require(result == result and result not in (float("inf"), float("-inf")), code)
    if minimum is not None:
        _require(result >= minimum, code)
    if maximum is not None:
        _require(result <= maximum, code)
    return result


def _record(record: Mapping[str, Any], fields: Sequence[str], kind: str) -> None:
    _require(isinstance(record, Mapping), kind + "_NOT_OBJECT")
    missing, extra = set(fields) - set(record), set(record) - set(fields)
    _require(not missing, kind + "_MISSING_FIELD:" + sorted(missing)[0] if missing else "")
    _require(not extra, kind + "_UNKNOWN_FIELD:" + sorted(extra)[0] if extra else "")
    _require(record["schema_version"] == SCHEMA_VERSION, kind + "_SCHEMA_VERSION")
    _require(record["system_version"] == SYSTEM_VERSION, kind + "_SYSTEM_VERSION")


def event_record_locator(source_record: Mapping[str, Any]) -> str:
    """Adapter identity for an Event row; it does not alter its source event_id."""
    keys = ("event_id", "batch_id", "country", "indicator_name", "release_ts", "source_cal", "source_provider", "source_series_id", "type")
    values = {key: source_record.get(key) for key in keys}
    _require(bool(values["event_id"]), "EVENT_RECORD_EVENT_ID_REQUIRED")
    _require(bool(values["country"]), "EVENT_RECORD_COUNTRY_REQUIRED")
    _require(bool(values["indicator_name"]), "EVENT_RECORD_INDICATOR_REQUIRED")
    _require(bool(values["release_ts"]), "EVENT_RECORD_RELEASE_REQUIRED")
    return "ER_" + _short(values)


def episode_id_for(record: Mapping[str, Any]) -> str:
    members = list(record["member_event_ids"])
    seed = {
        "country": record["country"], "release_ts": record["release_ts"], "member_event_ids": members,
        "batch_namespace": record["episode_family"], "session_id": record["session_id"],
    }
    prefix = "EP_BATCH" if record["same_time_cluster_flag"] else "EP_EVENT"
    return f"{prefix}_{_short(seed)}"


def prediction_id_for(record: Mapping[str, Any]) -> str:
    seed = {key: record[key] for key in ("episode_id", "provider", "model", "information_arm", "pack_id", "pack_fingerprint", "forecast_cutoff_ts", "prediction_target_type", "prediction_target_id")}
    seed["contract_version"] = CONTRACT_VERSION
    return "PRD_" + _short(seed)


def path_id_for(record: Mapping[str, Any]) -> str:
    return "PTH_" + _short({key: record[key] for key in ("prediction_id", "stage_index", "horizon_min", "target_id")})


def outcome_id_for(record: Mapping[str, Any]) -> str:
    return "OUT_" + _short({"episode_id": record["episode_id"], "release_ts": record["release_ts"], "contract_version": CONTRACT_VERSION})


def evaluation_id_for(record: Mapping[str, Any]) -> str:
    return "EVL_" + _short({"prediction_id": record["prediction_id"], "outcome_id": record["outcome_id"], "contract_version": CONTRACT_VERSION})


def _fingerprint(record: Mapping[str, Any], field: str, excluded: Sequence[str]) -> str:
    payload = {key: record[key] for key in record if key not in set(excluded) | {field}}
    payload["contract_version"] = CONTRACT_VERSION
    return sha256(payload)


def validate_episode(record: Mapping[str, Any]) -> str:
    _record(record, EPISODE_FIELDS, "EPISODE")
    _require(record["object"] == "EPISODE", "EPISODE_OBJECT")
    _require(isinstance(record["country"], str) and record["country"], "EPISODE_COUNTRY")
    _require(record["episode_family"] in {"STANDALONE_EVENT", "SAME_TIME_RELEASE_CLUSTER", "TEXTUAL_EVENT"}, "EPISODE_FAMILY")
    release, cutoff = _timestamp(record["release_ts"], "EPISODE_RELEASE_TS"), _timestamp(record["forecast_cutoff_ts"], "EPISODE_CUTOFF_TS")
    _require(cutoff <= release, "EPISODE_CUTOFF_AFTER_RELEASE")
    members, names = record["member_event_ids"], record["member_indicator_names"]
    _require(isinstance(members, list) and members and all(isinstance(value, str) and value for value in members), "EPISODE_MEMBERS")
    _require(len(members) == len(set(members)), "EPISODE_DUPLICATE_MEMBER_IDS")
    _require(isinstance(names, list) and len(names) == len(members) and all(isinstance(value, str) and value for value in names), "EPISODE_MEMBER_NAMES")
    _require(record["member_event_count"] == len(members), "EPISODE_MEMBER_COUNT")
    _require(record["primary_event_id"] in members and isinstance(record["primary_indicator_name"], str) and record["primary_indicator_name"], "EPISODE_PRIMARY")
    secondaries = record["secondary_event_ids"]
    _require(isinstance(secondaries, list) and len(secondaries) == len(set(secondaries)), "EPISODE_SECONDARIES")
    _require(all(value in members and value != record["primary_event_id"] for value in secondaries), "EPISODE_SECONDARY_MEMBER")
    _require(isinstance(record["secondary_indicator_names"], list) and len(record["secondary_indicator_names"]) == len(secondaries), "EPISODE_SECONDARY_NAMES")
    _require(record["selection_status"] in SELECTIONS, "EPISODE_SELECTION_STATUS")
    _require(isinstance(record["selection_reason"], str), "EPISODE_SELECTION_REASON")
    _require(isinstance(record["same_time_cluster_flag"], bool), "EPISODE_CLUSTER_FLAG")
    _require(record["same_time_cluster_flag"] == (len(members) > 1), "EPISODE_CLUSTER_MEMBER_MISMATCH")
    _require(record["episode_family"] == ("SAME_TIME_RELEASE_CLUSTER" if len(members) > 1 else record["episode_family"]), "EPISODE_FAMILY_CLUSTER_MISMATCH")
    _timestamp(record["created_ts"], "EPISODE_CREATED_TS"); _timestamp(record["updated_ts"], "EPISODE_UPDATED_TS")
    _require(record["status"] in {"PENDING", "VALID", "INVALID"}, "EPISODE_STATUS")
    _require((record["status"] != "INVALID") == (record["error_message"] in (None, "")), "EPISODE_ERROR_STATE")
    _require(record["episode_id"] == episode_id_for(record), "EPISODE_ID")
    return sha256({key: record[key] for key in EPISODE_FIELDS if key not in {"created_ts", "updated_ts", "status", "error_message"}})


def validate_prediction(record: Mapping[str, Any]) -> None:
    _record(record, PREDICTION_FIELDS, "PREDICTION")
    _require(record["object"] == "PREDICTION", "PREDICTION_OBJECT")
    _require(all(isinstance(record[key], str) and record[key] for key in ("run_id", "episode_id", "session_id", "provider", "model", "forecast_cutoff_ts")), "PREDICTION_IDENTITY_FIELDS")
    _timestamp(record["forecast_created_ts"], "PREDICTION_CREATED_TS"); _timestamp(record["forecast_cutoff_ts"], "PREDICTION_CUTOFF_TS")
    _require(record["information_arm"] in ARMS, "PREDICTION_ARM")
    _require(record["prediction_target_type"] == "EVENT_EPISODE", "PREDICTION_TARGET_TYPE")
    _require(record["prediction_target_id"] == record["episode_id"], "PREDICTION_TARGET_ID")
    _require(isinstance(record["secondary_event_ids"], list), "PREDICTION_SECONDARIES")
    _require(isinstance(record["no_signal_flag"], bool), "PREDICTION_NO_SIGNAL_FLAG")
    _number(record["confidence"], "PREDICTION_CONFIDENCE", 0, 1)
    _require(record["status"] in {"VALID", "NO_SIGNAL", "PROVIDER_ERROR", "INVALID"}, "PREDICTION_STATUS")
    if record["information_arm"] == "BASELINE":
        _require(record["pack_id"] == "BASELINE_NO_PACK" and record["pack_fingerprint"] in (None, ""), "PREDICTION_BASELINE_PACK")
    else:
        _require(isinstance(record["pack_id"], str) and record["pack_id"] and record["pack_fingerprint"], "PREDICTION_FULL_CONTEXT_PACK")
    if record["no_signal_flag"]:
        _require(record["status"] == "NO_SIGNAL" and isinstance(record["no_signal_reason"], str) and record["no_signal_reason"], "PREDICTION_NO_SIGNAL_STATE")
        _require(record["expected_initial_direction"] == "UNCERTAIN", "PREDICTION_NO_SIGNAL_DIRECTION")
        _require(record["expected_reversal_flag"] is None and record["expected_reversal_horizon_min"] is None, "PREDICTION_NO_SIGNAL_REVERSAL")
    elif record["status"] == "PROVIDER_ERROR":
        _require(record["no_signal_reason"] in (None, "") and isinstance(record["error_message"], str) and record["error_message"], "PREDICTION_PROVIDER_ERROR")
    else:
        _require(record["expected_initial_direction"] in DIRECTIONS - {"UNCERTAIN"}, "PREDICTION_DIRECTION")
        _require(record["no_signal_reason"] in (None, ""), "PREDICTION_UNEXPECTED_NO_SIGNAL_REASON")
        _require(isinstance(record["expected_reversal_flag"], bool), "PREDICTION_REVERSAL_FLAG")
        if record["expected_reversal_flag"]:
            _require(record["expected_reversal_horizon_min"] in HORIZONS[1:], "PREDICTION_REVERSAL_HORIZON")
    _require(record["prediction_id"] == prediction_id_for(record), "PREDICTION_ID")
    _require(record["prediction_fingerprint"] == _fingerprint(record, "prediction_fingerprint", ("run_id", "forecast_created_ts", "prompt_tokens", "completion_tokens", "latency_ms", "status", "error_message")), "PREDICTION_FINGERPRINT")


def validate_prediction_path(record: Mapping[str, Any], prediction: Mapping[str, Any]) -> None:
    _record(record, PATH_FIELDS, "PATH")
    _require(record["object"] == "PREDICTION_PATH" and record["prediction_id"] == prediction["prediction_id"], "PATH_PREDICTION_ID")
    for key in ("episode_id", "provider", "model", "information_arm"):
        _require(record[key] == prediction[key], "PATH_IDENTITY_MISMATCH:" + key)
    _require(record["target_type"] == "EVENT_EPISODE" and record["target_id"] == prediction["episode_id"], "PATH_TARGET")
    _require(record["stage_index"] in (1, 2, 3, 4) and record["horizon_min"] in HORIZONS, "PATH_STAGE")
    _require(record["stage_type"] == "HORIZON", "PATH_STAGE_TYPE")
    _require(record["expected_direction"] in DIRECTIONS, "PATH_DIRECTION")
    low, high = _number(record["expected_pips_min"], "PATH_PIPS_MIN", 0), _number(record["expected_pips_max"], "PATH_PIPS_MAX", 0)
    _require(low <= high, "PATH_PIP_RANGE")
    if record["expected_direction"] in {"FLAT", "UNCERTAIN"}:
        _require(low == 0 and high == 0, "PATH_NEUTRAL_PIP_RANGE")
    for key in ("stage_confidence", "continuation_probability", "reversal_probability"):
        _number(record[key], "PATH_" + key.upper(), 0, 1)
    _require(isinstance(record["stage_reason"], str) and record["stage_reason"], "PATH_REASON")
    _require(record["path_id"] == path_id_for(record), "PATH_ID")
    _require(record["stage_fingerprint"] == _fingerprint(record, "stage_fingerprint", ("run_id", "created_ts", "status", "error_message")), "PATH_FINGERPRINT")


def validate_prediction_path_transaction(prediction: Mapping[str, Any], paths: Sequence[Mapping[str, Any]]) -> None:
    validate_prediction(prediction)
    if prediction["no_signal_flag"] or prediction["status"] == "PROVIDER_ERROR":
        _require(not paths, "PATH_NOT_ALLOWED_FOR_NON_FORECAST")
        return
    _require(len(paths) == 4, "PATH_INCOMPLETE")
    for path in paths:
        validate_prediction_path(path, prediction)
    stages, horizons = [row["stage_index"] for row in paths], [row["horizon_min"] for row in paths]
    _require(stages == [1, 2, 3, 4] and horizons == list(HORIZONS), "PATH_ORDER_OR_HORIZONS")
    _require(len(set(horizons)) == 4, "PATH_DUPLICATE_HORIZON")


def direction_for_pips(pips: float) -> str:
    return "FLAT" if abs(pips) < FLAT_MAX_ABS_PIPS else ("UP" if pips > 0 else "DOWN")


def _horizon_timestamp(lineage: Mapping[str, Any], horizon: int) -> datetime:
    values = lineage.get("horizon_observation_ts") if isinstance(lineage, Mapping) else None
    _require(isinstance(values, Mapping) and str(horizon) in values, "OUTCOME_HORIZON_LINEAGE")
    return _timestamp(values[str(horizon)], "OUTCOME_HORIZON_TS")


def validate_outcome(record: Mapping[str, Any]) -> None:
    _record(record, OUTCOME_FIELDS, "OUTCOME")
    _require(record["object"] == "OUTCOME", "OUTCOME_OBJECT")
    _timestamp(record["release_ts"], "OUTCOME_RELEASE_TS")
    _require(record["status"] in {"VALID", "UNAVAILABLE", "INVALID"}, "OUTCOME_STATUS")
    _require(isinstance(record["intervening_event_flag"], bool), "OUTCOME_INTERVENING_FLAG")
    _require(record["outcome_id"] == outcome_id_for(record), "OUTCOME_ID")
    if record["status"] == "UNAVAILABLE":
        for key in ("anchor_price_ts", "anchor_price", "price_5m", "price_15m", "price_30m", "price_60m", "pips_5m", "pips_15m", "pips_30m", "pips_60m", "max_up_pips", "max_down_pips", "max_up_ts", "max_down_ts", "initial_direction", "reversal_ts"):
            _require(record[key] is None, "OUTCOME_UNAVAILABLE_VALUE:" + key)
        _require(all(record[f"direction_{h}m"] == "UNAVAILABLE" for h in HORIZONS), "OUTCOME_UNAVAILABLE_DIRECTIONS")
        _require(record["reversal_flag"] is None and isinstance(record["error_message"], str) and record["error_message"], "OUTCOME_UNAVAILABLE_STATE")
    else:
        release, anchor = _timestamp(record["release_ts"], "OUTCOME_RELEASE_TS"), _timestamp(record["anchor_price_ts"], "OUTCOME_ANCHOR_TS")
        _require(anchor <= release and (release - anchor).total_seconds() <= 60, "OUTCOME_ANCHOR_STALENESS")
        anchor_price = _number(record["anchor_price"], "OUTCOME_ANCHOR_PRICE", 0)
        _require(isinstance(record["source_lineage"], Mapping) and record["market_data_provider"], "OUTCOME_LINEAGE")
        for horizon in HORIZONS:
            price = _number(record[f"price_{horizon}m"], "OUTCOME_PRICE", 0)
            pips = _number(record[f"pips_{horizon}m"], "OUTCOME_PIPS")
            _require(round((price - anchor_price) / 0.01, 2) == round(pips, 2), "OUTCOME_PIP_RECONSTRUCTION")
            _require(record[f"direction_{horizon}m"] == direction_for_pips(pips), "OUTCOME_DIRECTION")
            observed = _horizon_timestamp(record["source_lineage"], horizon)
            target = release.timestamp() + horizon * 60
            _require(observed.timestamp() <= target and target - observed.timestamp() <= 60, "OUTCOME_HORIZON_TOLERANCE")
        _require(_number(record["max_up_pips"], "OUTCOME_MAX_UP") >= 0 and _number(record["max_down_pips"], "OUTCOME_MAX_DOWN") <= 0, "OUTCOME_EXCURSION_SIGN")
        _timestamp(record["max_up_ts"], "OUTCOME_MAX_UP_TS"); _timestamp(record["max_down_ts"], "OUTCOME_MAX_DOWN_TS")
        initial = next((record[f"direction_{h}m"] for h in HORIZONS if record[f"direction_{h}m"] in {"UP", "DOWN"}), "FLAT")
        _require(record["initial_direction"] == initial, "OUTCOME_INITIAL_DIRECTION")
        opposite = {"UP": "DOWN", "DOWN": "UP"}.get(initial)
        reversed_horizon = next((h for h in HORIZONS[1:] if opposite and record[f"direction_{h}m"] == opposite), None)
        _require(record["reversal_flag"] == bool(reversed_horizon), "OUTCOME_REVERSAL")
        if reversed_horizon:
            _require(_timestamp(record["reversal_ts"], "OUTCOME_REVERSAL_TS").timestamp() == release.timestamp() + reversed_horizon * 60, "OUTCOME_REVERSAL_TS")
        else:
            _require(record["reversal_ts"] is None, "OUTCOME_UNEXPECTED_REVERSAL_TS")
    _require(record["outcome_fingerprint"] == _fingerprint(record, "outcome_fingerprint", ("acquisition_ts", "status", "error_message")), "OUTCOME_FINGERPRINT")


def _interval_error(realized_abs_pips: float, low: float, high: float) -> float:
    return 0.0 if low <= realized_abs_pips <= high else min(abs(realized_abs_pips - low), abs(realized_abs_pips - high))


def validate_evaluation(record: Mapping[str, Any], prediction: Mapping[str, Any], outcome: Mapping[str, Any], paths: Sequence[Mapping[str, Any]] | None = None) -> None:
    _record(record, EVALUATION_FIELDS, "EVALUATION")
    _require(record["object"] == "EVALUATION" and record["evaluation_contract_version"] == CONTRACT_VERSION, "EVALUATION_VERSION")
    for key in ("prediction_id", "episode_id", "provider", "model", "information_arm"):
        _require(record[key] == prediction[key], "EVALUATION_PREDICTION_MISMATCH:" + key)
    _require(record["outcome_id"] == outcome["outcome_id"] and outcome["episode_id"] == prediction["episode_id"], "EVALUATION_OUTCOME_MISMATCH")
    _require(record["evaluation_id"] == evaluation_id_for(record), "EVALUATION_ID")
    _require(record["primary_endpoint_name"] == "EPISODE_REACTION_DIRECTION_15M", "EVALUATION_PRIMARY_NAME")
    unavailable = outcome["status"] == "UNAVAILABLE" or prediction["status"] == "PROVIDER_ERROR"
    if unavailable:
        _require(record["status"] == "UNAVAILABLE" and record["primary_endpoint_value"] is None, "EVALUATION_UNAVAILABLE_STATE")
        _require(all(record[f"direction_{h}m_ok"] is None for h in HORIZONS), "EVALUATION_UNAVAILABLE_DIRECTIONS")
    elif prediction["no_signal_flag"]:
        if paths is not None:
            validate_prediction_path_transaction(prediction, paths)
        quiet = all(outcome[f"direction_{h}m"] == "FLAT" for h in HORIZONS) and max(abs(outcome["max_up_pips"]), abs(outcome["max_down_pips"])) < FLAT_MAX_ABS_PIPS
        _require(record["status"] == "VALID" and record["no_signal_ok"] == quiet, "EVALUATION_NO_SIGNAL")
        _require(record["primary_endpoint_value"] is None and all(record[f"direction_{h}m_ok"] is None for h in HORIZONS), "EVALUATION_NO_SIGNAL_DIRECTIONS")
    else:
        if paths is None:
            raise ContractValidationError("EVALUATION_PATH_REQUIRED")
        validate_prediction_path_transaction(prediction, paths)
        by_horizon = {path["horizon_min"]: path for path in paths}
        correctness = []
        for horizon in HORIZONS:
            expected = by_horizon[horizon]["expected_direction"] == outcome[f"direction_{horizon}m"]
            _require(record[f"direction_{horizon}m_ok"] is expected, "EVALUATION_DIRECTION_VALUE")
            correctness.append(expected)
        _require(record["status"] == "VALID" and record["primary_endpoint_value"] == record["direction_15m_ok"], "EVALUATION_PRIMARY_VALUE")
        _number(record["overall_path_score"], "EVALUATION_PATH_SCORE", 0, 1)
        _require(round(record["overall_path_score"], 8) == round(mean(correctness), 8), "EVALUATION_PATH_SCORE_VALUE")
        magnitude = _interval_error(abs(outcome["pips_15m"]), by_horizon[15]["expected_pips_min"], by_horizon[15]["expected_pips_max"])
        _require(round(record["magnitude_15m_error"], 8) == round(magnitude, 8), "EVALUATION_MAGNITUDE")
        _require(record["reversal_ok"] is (prediction["expected_reversal_flag"] == outcome["reversal_flag"]), "EVALUATION_REVERSAL")
    _require(record["evaluation_fingerprint"] == _fingerprint(record, "evaluation_fingerprint", ("run_id", "generated_ts", "status", "error_message", "evaluation_note")), "EVALUATION_FINGERPRINT")


def validate_ae_pair(baseline: Mapping[str, Any], full_context: Mapping[str, Any]) -> None:
    validate_prediction(baseline); validate_prediction(full_context)
    _require({baseline["information_arm"], full_context["information_arm"]} == ARMS, "AE_ARMS")
    for key in ("episode_id", "provider", "model", "forecast_cutoff_ts", "prediction_target_type", "prediction_target_id"):
        _require(baseline[key] == full_context[key], "AE_IDENTITY_MISMATCH:" + key)
