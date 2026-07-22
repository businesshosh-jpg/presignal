"""Canonical v2.1 state ownership and legacy-compatible mappings.

These states describe an operation without changing its scientific result.
They are authoritative for new records; legacy fields remain compatibility
evidence and are mapped only from structured execution data.
"""
from __future__ import annotations

from typing import Any, Mapping


class SelectionState:
    SELECTED = "SELECTED"
    WATCH = "WATCH"
    IGNORED = "IGNORED"
    NOT_SELECTED = "NOT_SELECTED"
    REJECTED = "REJECTED"


class RuntimeState:
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    SUCCESS = "SUCCESS"
    PROVIDER_REJECTED = "PROVIDER_REJECTED"
    TRANSPORT_FAILED = "TRANSPORT_FAILED"
    STATUS_UNKNOWN = "STATUS_UNKNOWN"


class ForecastState:
    NOT_APPLICABLE = "NOT_APPLICABLE"
    DIRECTIONAL = "DIRECTIONAL"
    NO_SIGNAL = "NO_SIGNAL"
    INVALID = "INVALID"
    INCOMPLETE = "INCOMPLETE"


class EvaluationState:
    NOT_APPLICABLE = "NOT_APPLICABLE"
    PENDING_OUTCOME = "PENDING_OUTCOME"
    CORRECT = "CORRECT"
    INCORRECT = "INCORRECT"
    OUTCOME_UNAVAILABLE = "OUTCOME_UNAVAILABLE"


TRANSPORT_STATUSES = {"exception", "transport_failed", "connection_error", "timeout", "oauth_failed"}
UNKNOWN_TRANSPORT_STATUSES = {"unknown", "status_unknown", "sent_no_confirmed_response"}


def selection_state(attention: Mapping[str, Any] | None) -> str:
    """Map accepted parsed Attention evidence to its sole canonical owner."""
    if not attention or not attention.get("accepted"):
        return SelectionState.REJECTED
    rows = ((attention.get("output") or {}).get("rows") or [])
    parsed = [row for row in rows if row.get("status") == "parsed"]
    if not parsed:
        return SelectionState.REJECTED
    labels = {str(row.get("attention_label") or "") for row in parsed}
    if "PRIMARY_DRIVER" in labels:
        return SelectionState.SELECTED
    if labels & {"SECONDARY_DRIVER", "WATCHLIST", "CONTEXT_ONLY"}:
        return SelectionState.WATCH
    if labels == {"IGNORE"}:
        return SelectionState.IGNORED
    return SelectionState.NOT_SELECTED


def runtime_state(record: Mapping[str, Any] | None, *, selected: bool = True) -> str:
    """Use persisted transport evidence, never free-form rejection text."""
    if not selected:
        return RuntimeState.NOT_ATTEMPTED
    if not record:
        return RuntimeState.NOT_ATTEMPTED
    persisted = record.get("runtime_state")
    if persisted in {
        RuntimeState.NOT_ATTEMPTED, RuntimeState.SUCCESS, RuntimeState.PROVIDER_REJECTED,
        RuntimeState.TRANSPORT_FAILED, RuntimeState.STATUS_UNKNOWN,
    }:
        return str(persisted)
    transport = str(record.get("transport_status") or "").lower()
    if transport in TRANSPORT_STATUSES:
        return RuntimeState.TRANSPORT_FAILED
    if transport in UNKNOWN_TRANSPORT_STATUSES:
        return RuntimeState.STATUS_UNKNOWN
    if transport in {"ok", "deterministic"} or record.get("raw_response") is not None:
        return RuntimeState.SUCCESS if record.get("accepted") else RuntimeState.PROVIDER_REJECTED
    return RuntimeState.STATUS_UNKNOWN


def forecast_state(record: Mapping[str, Any] | None, *, selection: str) -> str:
    if selection != SelectionState.SELECTED:
        return ForecastState.NOT_APPLICABLE
    if record and record.get("forecast_state") in {
        ForecastState.NOT_APPLICABLE, ForecastState.DIRECTIONAL, ForecastState.NO_SIGNAL,
        ForecastState.INVALID, ForecastState.INCOMPLETE,
    }:
        return str(record["forecast_state"])
    runtime = runtime_state(record, selected=True)
    if runtime in {RuntimeState.NOT_ATTEMPTED, RuntimeState.TRANSPORT_FAILED, RuntimeState.STATUS_UNKNOWN}:
        return ForecastState.INCOMPLETE
    prediction = ((record or {}).get("output") or {}).get("prediction")
    if not record or not record.get("accepted") or not isinstance(prediction, Mapping):
        return ForecastState.INVALID
    return ForecastState.NO_SIGNAL if prediction.get("no_signal_flag") else ForecastState.DIRECTIONAL


def evaluation_state(
    forecast: str, evaluation: Mapping[str, Any] | None = None, outcome: Mapping[str, Any] | None = None,
) -> str:
    if forecast != ForecastState.DIRECTIONAL:
        return EvaluationState.NOT_APPLICABLE
    if outcome and outcome.get("status") == "UNAVAILABLE":
        return EvaluationState.OUTCOME_UNAVAILABLE
    if not evaluation:
        return EvaluationState.PENDING_OUTCOME
    value = evaluation.get("direction_15m_ok")
    if value is True:
        return EvaluationState.CORRECT
    if value is False:
        return EvaluationState.INCORRECT
    return EvaluationState.OUTCOME_UNAVAILABLE if outcome else EvaluationState.PENDING_OUTCOME


def canonical_states(
    *, attention: Mapping[str, Any] | None, forecast: Mapping[str, Any] | None = None,
    evaluation: Mapping[str, Any] | None = None, outcome: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    selection = selection_state(attention)
    runtime = runtime_state(forecast, selected=selection == SelectionState.SELECTED)
    forecast_value = forecast_state(forecast, selection=selection)
    return {
        "selection_state": selection,
        "runtime_state": runtime,
        "forecast_state": forecast_value,
        "evaluation_state": evaluation_state(forecast_value, evaluation, outcome),
    }


def validate_transition(states: Mapping[str, str]) -> None:
    """Reject impossible cross-axis state combinations."""
    selection, runtime = states["selection_state"], states["runtime_state"]
    forecast, evaluation = states["forecast_state"], states["evaluation_state"]
    if selection != SelectionState.SELECTED:
        expected = (RuntimeState.NOT_ATTEMPTED, ForecastState.NOT_APPLICABLE, EvaluationState.NOT_APPLICABLE)
        if (runtime, forecast, evaluation) != expected:
            raise ValueError("NON_SELECTED_STATE_TRANSITION_INVALID")
    if runtime in {RuntimeState.TRANSPORT_FAILED, RuntimeState.STATUS_UNKNOWN} and forecast != ForecastState.INCOMPLETE:
        raise ValueError("RUNTIME_INCOMPLETE_TRANSITION_INVALID")
    if forecast != ForecastState.DIRECTIONAL and evaluation != EvaluationState.NOT_APPLICABLE:
        raise ValueError("NON_DIRECTIONAL_EVALUATION_INVALID")
