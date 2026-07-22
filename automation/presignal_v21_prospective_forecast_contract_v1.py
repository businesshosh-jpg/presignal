"""Prospective-only primary 15-minute forecast contract.

This does not parse provider envelopes and must never be applied to frozen
historical records.  It separates primary directional validity from the
optional multi-horizon sidecar.
"""
from __future__ import annotations

from typing import Any, Mapping

from automation.presignal_v21_canonical_states_v1 import ForecastState, SelectionState

PRIMARY_DIRECTIONS = {"UP", "DOWN", "FLAT"}
SECONDARY_FIELDS = (
    "direction_5m", "direction_30m", "direction_60m", "confidence",
    "reversal", "reversal_horizon", "path_narrative", "invalidation_condition",
)


def _path_direction(payload: Mapping[str, Any], horizon: int) -> Any:
    direct = payload.get(f"direction_{horizon}m")
    if direct is not None:
        return direct
    for item in payload.get("path") or []:
        if isinstance(item, Mapping) and item.get("horizon_min") == horizon:
            return item.get("expected_direction")
    return None


def _status(value: Any, validator) -> str:
    if value is None:
        return "NOT_PROVIDED"
    return "PRESENT_VALID" if validator(value) else "PRESENT_INVALID"


def validate_prospective_forecast(candidate: Mapping[str, Any] | None, *, episode_id: str,
                                  provider: str, model: str, pack_arm: str,
                                  forecast_cutoff: str) -> dict[str, Any]:
    """Validate a neutral provider candidate against the prospective contract."""
    payload = dict(candidate or {})
    context = {"episode_id": episode_id, "provider": provider, "model": model,
               "pack_arm": pack_arm, "forecast_cutoff": forecast_cutoff,
               "forecast_target": payload.get("forecast_target", episode_id)}
    no_signal = payload.get("no_signal_flag") is True
    direction = _path_direction(payload, 15)
    statuses = {
        "direction_5m": _status(_path_direction(payload, 5), lambda value: value in PRIMARY_DIRECTIONS),
        "direction_30m": _status(_path_direction(payload, 30), lambda value: value in PRIMARY_DIRECTIONS),
        "direction_60m": _status(_path_direction(payload, 60), lambda value: value in PRIMARY_DIRECTIONS),
        "confidence": _status(payload.get("confidence"), lambda value: isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1),
        "reversal": _status(payload.get("expected_reversal_flag"), lambda value: isinstance(value, bool)),
        "reversal_horizon": _status(payload.get("expected_reversal_horizon_min"), lambda value: isinstance(value, int) and not isinstance(value, bool) and value > 0),
        "path_narrative": _status(payload.get("expected_path_summary"), lambda value: isinstance(value, str) and bool(value.strip())),
        "invalidation_condition": _status(payload.get("invalidation_condition"), lambda value: isinstance(value, str) and bool(value.strip())),
    }
    errors, warnings = [], []
    if no_signal:
        forecast_state = ForecastState.NO_SIGNAL
        primary_valid = False
    elif direction not in PRIMARY_DIRECTIONS:
        forecast_state = ForecastState.INVALID
        primary_valid = False
        errors.append("PRIMARY_DIRECTION_15M_REQUIRED")
    else:
        forecast_state = ForecastState.DIRECTIONAL
        primary_valid = True
    for field, status in statuses.items():
        if status == "PRESENT_INVALID":
            warnings.append("SECONDARY_" + field.upper() + "_INVALID")
    return {
        **context, "primary_forecast_valid": primary_valid,
        "primary_direction_15m": direction if primary_valid else None,
        "primary_directional_eligibility": primary_valid,
        "abstention_observation_valid": no_signal,
        "secondary_path_complete": all(value == "PRESENT_VALID" for value in statuses.values()),
        "secondary_field_statuses": statuses, "forecast_state": forecast_state,
        "validation_errors": errors, "validation_warnings": warnings,
        "canonical_payload": payload,
    }


def non_entry_result(*, selection_state: str) -> dict[str, Any]:
    if selection_state == SelectionState.SELECTED:
        raise ValueError("SELECTED_REQUIRES_FORECAST_PROCESSING")
    return {"primary_forecast_valid": False, "primary_direction_15m": None,
            "primary_directional_eligibility": False, "abstention_observation_valid": False,
            "secondary_path_complete": False, "secondary_field_statuses": {},
            "forecast_state": ForecastState.NOT_APPLICABLE, "validation_errors": [],
            "validation_warnings": [], "canonical_payload": None}


def primary_pair_eligible(pack_a: Mapping[str, Any], pack_e: Mapping[str, Any], *, outcome_available: bool) -> bool:
    identity = ("episode_id", "provider", "model", "forecast_cutoff", "forecast_target")
    return outcome_available and all(pack_a.get(key) == pack_e.get(key) for key in identity) and bool(pack_a.get("primary_directional_eligibility")) and bool(pack_e.get("primary_directional_eligibility"))
