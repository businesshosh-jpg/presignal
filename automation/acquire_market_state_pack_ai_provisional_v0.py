#!/usr/bin/env python3
"""Fail-closed validation for source-grounded, provisional Pack E acquisition.

This module deliberately does not call a model or a search provider.  It is the
shared boundary around any separately configured acquisition model: callers must
provide a timestamped source bundle and a structured model result.  Forecasting
providers never receive access to this acquisition path.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Sequence


ALLOWED_METHODS = {"ai_retrieved_provisional", "ai_research_summary"}
ALLOWED_RELIABILITY = {"high", "medium", "low", "unknown"}
ALLOWED_PROVISIONAL = {
    "PROVISIONAL_SOURCE_GROUNDED",
    "REJECTED_INSUFFICIENT_SOURCES",
    "UNAVAILABLE_AT_ASOF",
    "FAILED_VALIDATION",
}
FORBIDDEN_INTERPRETIVE_TERMS = {
    "forecast direction",
    "likely market",
    "likely fade",
    "bad news is good news",
    "expected direction",
    "will succeed",
}


class AcquisitionValidationError(ValueError):
    """Raised when an acquisition item cannot be admitted to Pack E."""


def _norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _parse_timestamp(value: Any) -> datetime:
    text = _norm(value)
    if not text:
        raise AcquisitionValidationError("MISSING_TIMESTAMP")
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError as exc:
        raise AcquisitionValidationError("INVALID_TIMESTAMP:" + text) from exc


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)


def content_fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def validate_source_bundle(
    source_references: Sequence[Mapping[str, Any]],
    *,
    as_of_timestamp: str,
    forecast_timestamp: str,
    mode: str,
) -> list[Dict[str, str]]:
    """Return normalized sources only when every source is valid at the as-of time."""

    as_of = _parse_timestamp(as_of_timestamp)
    forecast = _parse_timestamp(forecast_timestamp)
    if as_of > forecast:
        raise AcquisitionValidationError("ASOF_AFTER_FORECAST")
    if not source_references:
        raise AcquisitionValidationError("MISSING_SOURCE_REFERENCES")

    normalized: list[Dict[str, str]] = []
    seen: set[str] = set()
    for raw in source_references:
        source_id = _norm(raw.get("source_id"))
        uri = _norm(raw.get("uri"))
        title = _norm(raw.get("title"))
        source_timestamp = _norm(raw.get("source_timestamp"))
        retrieval_timestamp = _norm(raw.get("retrieval_timestamp"))
        excerpt = _norm(raw.get("excerpt"))
        if not source_id or not uri or not title or not source_timestamp or not excerpt:
            raise AcquisitionValidationError("INCOMPLETE_SOURCE_REFERENCE")
        if source_id in seen:
            raise AcquisitionValidationError("DUPLICATE_SOURCE_REFERENCE:" + source_id)
        seen.add(source_id)
        source_time = _parse_timestamp(source_timestamp)
        if source_time > as_of:
            raise AcquisitionValidationError("SOURCE_AFTER_ASOF:" + source_id)
        if mode == "HISTORICAL_ASOF_REPLAY" and not retrieval_timestamp:
            # Historical proof needs an explicit original source time and a
            # recorded retrieval/provenance time, not a present-day summary.
            raise AcquisitionValidationError("HISTORICAL_RETRIEVAL_PROVENANCE_MISSING:" + source_id)
        if retrieval_timestamp and _parse_timestamp(retrieval_timestamp) < source_time:
            raise AcquisitionValidationError("RETRIEVAL_BEFORE_SOURCE:" + source_id)
        normalized.append({
            "source_id": source_id,
            "uri": uri,
            "title": title,
            "source_timestamp": source_timestamp,
            "retrieval_timestamp": retrieval_timestamp,
            "excerpt": excerpt,
        })
    return sorted(normalized, key=lambda row: row["source_id"])


def _validate_summary_semantics(structured_summary: str, retrieved_value: str) -> None:
    text = (structured_summary + " " + retrieved_value).lower()
    forbidden = [term for term in FORBIDDEN_INTERPRETIVE_TERMS if term in text]
    if forbidden:
        raise AcquisitionValidationError("INTERPRETIVE_OR_FORECAST_CONTENT:" + "|".join(sorted(forbidden)))


def build_provisional_item(
    *,
    session_id: str,
    candidate_id: str,
    information_key: str,
    canonical_information: str,
    requested_information: str,
    acquisition_method: str,
    research_model: str,
    as_of_timestamp: str,
    forecast_timestamp: str,
    source_references: Sequence[Mapping[str, Any]],
    retrieved_value: str,
    structured_summary: str,
    stance_or_state_if_allowed: str,
    confidence: str,
    reliability_label: str,
    mode: str,
    generated_timestamp: str,
) -> Dict[str, Any]:
    """Validate one external-research result and return a provisional record."""

    if acquisition_method not in ALLOWED_METHODS:
        raise AcquisitionValidationError("UNAPPROVED_ACQUISITION_METHOD")
    if not _norm(research_model):
        raise AcquisitionValidationError("MISSING_RESEARCH_MODEL")
    if _norm(reliability_label).lower() not in ALLOWED_RELIABILITY:
        raise AcquisitionValidationError("INVALID_RELIABILITY_LABEL")
    if not _norm(retrieved_value) and not _norm(structured_summary):
        raise AcquisitionValidationError("EMPTY_ACQUISITION_RESULT")
    _validate_summary_semantics(_norm(structured_summary), _norm(retrieved_value))
    sources = validate_source_bundle(
        source_references,
        as_of_timestamp=as_of_timestamp,
        forecast_timestamp=forecast_timestamp,
        mode=mode,
    )
    if _norm(stance_or_state_if_allowed):
        _validate_summary_semantics(_norm(stance_or_state_if_allowed), "")
    return {
        "session_id": _norm(session_id),
        "candidate_id": _norm(candidate_id),
        "information_key": _norm(information_key),
        "canonical_information": _norm(canonical_information),
        "requested_information": _norm(requested_information),
        "acquisition_method": acquisition_method,
        "research_model": _norm(research_model),
        "as_of_timestamp": _norm(as_of_timestamp),
        "forecast_timestamp": _norm(forecast_timestamp),
        "source_references": sources,
        "source_timestamps": [row["source_timestamp"] for row in sources],
        "retrieved_value": _norm(retrieved_value),
        "structured_summary": _norm(structured_summary),
        "stance_or_state_if_allowed": _norm(stance_or_state_if_allowed),
        "confidence": _norm(confidence),
        "reliability_label": _norm(reliability_label).lower(),
        "provisional_status": "PROVISIONAL_SOURCE_GROUNDED",
        "backtest_safe": "TRUE",
        "data_available_flag": "TRUE",
        "failure_reason": "",
        "generated_timestamp": _norm(generated_timestamp),
        "source_fingerprint": content_fingerprint(sources),
        "acquisition_content_fingerprint": content_fingerprint({
            "session_id": _norm(session_id),
            "candidate_id": _norm(candidate_id),
            "information_key": _norm(information_key),
            "method": acquisition_method,
            "sources": sources,
            "retrieved_value": _norm(retrieved_value),
            "structured_summary": _norm(structured_summary),
        }),
    }


def unavailable_item(
    *,
    session_id: str,
    candidate_id: str,
    information_key: str,
    canonical_information: str,
    requested_information: str,
    acquisition_method: str,
    as_of_timestamp: str,
    forecast_timestamp: str,
    failure_reason: str,
    generated_timestamp: str,
) -> Dict[str, Any]:
    """Produce an explicit, non-admissible result without inventing a value."""

    if acquisition_method not in ALLOWED_METHODS:
        raise AcquisitionValidationError("UNAPPROVED_ACQUISITION_METHOD")
    _parse_timestamp(as_of_timestamp)
    _parse_timestamp(forecast_timestamp)
    return {
        "session_id": _norm(session_id),
        "candidate_id": _norm(candidate_id),
        "information_key": _norm(information_key),
        "canonical_information": _norm(canonical_information),
        "requested_information": _norm(requested_information),
        "acquisition_method": acquisition_method,
        "research_model": "",
        "as_of_timestamp": _norm(as_of_timestamp),
        "forecast_timestamp": _norm(forecast_timestamp),
        "source_references": [],
        "source_timestamps": [],
        "retrieved_value": "",
        "structured_summary": "",
        "stance_or_state_if_allowed": "",
        "confidence": "unknown",
        "reliability_label": "unknown",
        "provisional_status": "UNAVAILABLE_AT_ASOF",
        "backtest_safe": "FALSE",
        "data_available_flag": "FALSE",
        "failure_reason": _norm(failure_reason),
        "generated_timestamp": _norm(generated_timestamp),
        "source_fingerprint": content_fingerprint([]),
        "acquisition_content_fingerprint": content_fingerprint({
            "session_id": _norm(session_id),
            "candidate_id": _norm(candidate_id),
            "information_key": _norm(information_key),
            "failure_reason": _norm(failure_reason),
        }),
    }
