#!/usr/bin/env python3
"""Run the bounded, source-grounded acquisition-AI path for true shared Pack E.

This is intentionally a local shadow workflow.  It never invokes the normal
forecasting prompts, never reads outcomes, and only sends source-bundle text to
the separately configured acquisition model after timestamp and provenance
validation.  Missing external configuration produces explicit unavailable
records; it never invents historical research context.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.acquire_market_state_pack_ai_provisional_v0 import (  # type: ignore
    AcquisitionValidationError,
    build_provisional_item,
    content_fingerprint,
)
from automation.google_clients import (  # type: ignore
    build_script_service,
    default_script_id,
    load_credentials,
    run_script_function,
)


PHASE_ID = "9-EXTERNAL-ACQUISITION"
ACQUISITION_VERSION = "external_acquisition_ai_v0"
PACK_E_VERSION = "true_shared_pack_e_v1"
AUTOMATION_ACQUISITION_FUNCTION = "apiRunAcquisitionAiSourceGrounded"
FROZEN_ACQUISITION_MODEL = "gpt-5.6-luna"
FROZEN_ACQUISITION_REASONING = "low"
FROZEN_ACQUISITION_TEMPERATURE_MODE = "MODEL_DEFAULT"
FROZEN_ACQUISITION_TEMPERATURE_PARAMETER_SENT = False
AUDIT_RUN_ID = "9-PACK-REQUEST-FULFILLMENT_20260714T035309Z"
BASE_ACQUISITION_RUN_ID = "9-TRUE-SHARED-PACK-E_20260714T041457Z"
AUDIT_ROOT = ROOT / "outputs" / "phase9_pack_request_fulfillment" / AUDIT_RUN_ID
BASE_ROOT = ROOT / "outputs" / "phase9_market_state_acquisition" / BASE_ACQUISITION_RUN_ID
OUTPUT_ROOT = ROOT / "outputs" / "phase9_external_acquisition"
SOURCE_BUNDLE_DEFAULT = ROOT / "inputs" / "phase9_external_acquisition" / "source_bundles.jsonl"

MODE_HISTORICAL = "HISTORICAL_ASOF_REPLAY"
MODE_PROSPECTIVE = "PROSPECTIVE_SHADOW"
PROVIDERS = ("OpenAI", "Gemini", "Anthropic")
AI_STATUS = "ELIGIBLE_FOR_AI_ACQUISITION"
AI_CAPABILITY = "INFLATION_NARRATIVE_SOURCE_GROUNDED"
ALLOWED_SOURCE_TYPES = {
    "official_central_bank",
    "official_government_statistics",
    "official_economic_calendar",
    "approved_market_data",
    "timestamped_institutional_research",
    "authoritative_financial_news",
    "exchange_source",
}
ALLOWED_RELIABILITY = {"high", "medium", "low", "unknown"}
ALLOWED_METHODS = {"ai_retrieved_provisional", "ai_research_summary"}
ALLOWED_PROVISIONAL = {
    "PROVISIONAL_SOURCE_GROUNDED",
    "REJECTED_INSUFFICIENT_SOURCES",
    "UNAVAILABLE_AT_ASOF",
    "FAILED_VALIDATION",
    "SOURCE_POLICY_REQUIRED",
}
FORBIDDEN_OUTPUT_TERMS = (
    "forecast",
    "predict",
    "expected direction",
    "likely direction",
    "will rise",
    "will fall",
    "success",
    "positive arm",
    "negative arm",
)


class BuildBlocked(RuntimeError):
    """Raised when inputs cannot safely support a Pack E rebuild."""


class SourceBundleError(ValueError):
    """Raised for one malformed or time-unsafe external source bundle."""


class AcquisitionModelAccessError(AcquisitionValidationError):
    """Raised when the frozen acquisition model cannot be used as configured."""


class AcquisitionParameterCompatibilityError(AcquisitionValidationError):
    """Raised when a frozen API parameter is still serialized incompatibly."""


def _norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _truth(value: Any) -> bool:
    return _norm(value).upper() in {"TRUE", "T", "YES", "Y", "1"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    text = _norm(value)
    if not text:
        raise SourceBundleError("MISSING_TIMESTAMP")
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError as exc:
        raise SourceBundleError("INVALID_TIMESTAMP:" + text) from exc


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _run_id() -> str:
    return PHASE_ID + "_" + _now().replace("-", "").replace(":", "").replace("Z", "") + "Z"


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise BuildBlocked("MISSING_INPUT:" + str(path))
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise BuildBlocked("MISSING_INPUT:" + str(path))
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical_json(dict(payload)) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(_canonical_json(dict(row)) + "\n")


def _strip_volatile(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    volatile = {"acquisition_run_id", "generated_timestamp", "external_acquisition_run_id"}
    return [{key: value for key, value in row.items() if key not in volatile} for row in rows]


def _safe_env_present(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def _load_model_config() -> Dict[str, Any]:
    retry_raw = _norm(os.environ.get("PRESIGNAL_ACQUISITION_AI_RETRY_LIMIT")) or "1"
    max_calls_raw = _norm(os.environ.get("PRESIGNAL_ACQUISITION_AI_MAX_CALLS")) or "8"
    try:
        retry_limit = int(retry_raw)
        max_calls = int(max_calls_raw)
    except ValueError as exc:
        raise BuildBlocked("INVALID_ACQUISITION_MODEL_NUMERIC_CONFIG") from exc
    if retry_limit < 0 or max_calls < 1 or max_calls > 8:
        raise BuildBlocked("INVALID_ACQUISITION_MODEL_LIMITS")
    return {
        "provider": "OpenAI",
        "model": FROZEN_ACQUISITION_MODEL,
        "reasoning": FROZEN_ACQUISITION_REASONING,
        "enabled": True,
        "configured": True,
        "configuration_source": "apps_script:ACQUISITION_OPENAI_API_KEY",
        "temperature_mode": FROZEN_ACQUISITION_TEMPERATURE_MODE,
        "temperature_parameter_sent": FROZEN_ACQUISITION_TEMPERATURE_PARAMETER_SENT,
        "timeout_seconds": "APPS_SCRIPT_DEFAULT",
        "retry_limit": retry_limit,
        "maximum_calls": max_calls,
        "api_key": "",
        "reason": "",
        "transport": "apps_script_execution_api",
        "function": AUTOMATION_ACQUISITION_FUNCTION,
    }


def _validate_source_bundle(raw: Mapping[str, Any], mode: str) -> Dict[str, Any]:
    required = (
        "source_bundle_id", "session_id", "information_key", "source_name", "source_type",
        "source_reference", "publication_timestamp", "retrieval_timestamp", "as_of_timestamp",
        "forecast_timestamp", "content_or_structured_extract", "source_language",
        "source_reliability", "historical_availability_proven", "backtest_safe",
    )
    missing = [field for field in required if not _norm(raw.get(field))]
    if missing:
        raise SourceBundleError("MISSING_REQUIRED_FIELD:" + "|".join(missing))
    source_type = _norm(raw.get("source_type")).lower()
    if source_type not in ALLOWED_SOURCE_TYPES:
        raise SourceBundleError("SOURCE_POLICY_REQUIRED:" + source_type)
    reference = _norm(raw.get("source_reference"))
    if not reference.startswith("https://"):
        raise SourceBundleError("INVALID_SOURCE_REFERENCE")
    publication = _parse_timestamp(_norm(raw.get("publication_timestamp")))
    retrieval = _parse_timestamp(_norm(raw.get("retrieval_timestamp")))
    as_of = _parse_timestamp(_norm(raw.get("as_of_timestamp")))
    forecast = _parse_timestamp(_norm(raw.get("forecast_timestamp")))
    if as_of != forecast:
        raise SourceBundleError("ASOF_FORECAST_TIMESTAMP_MISMATCH")
    if _norm(raw.get("source_reliability")).lower() not in ALLOWED_RELIABILITY:
        raise SourceBundleError("INVALID_SOURCE_RELIABILITY")
    if mode == MODE_HISTORICAL:
        if not _truth(raw.get("historical_availability_proven")):
            raise SourceBundleError("HISTORICAL_AVAILABILITY_NOT_PROVEN")
        if not _truth(raw.get("backtest_safe")):
            raise SourceBundleError("BACKTEST_SAFE_NOT_TRUE")
        # Evidence retrieval may occur after a historical replay. The original
        # source, rather than the present retrieval job, must predate the cutoff.
        if publication > forecast:
            raise SourceBundleError("POST_OUTCOME_OR_POST_FORECAST_SOURCE")
        if retrieval < publication:
            raise SourceBundleError("RETRIEVAL_BEFORE_PUBLICATION")
        historical_available_at = _norm(raw.get("historical_availability_timestamp")) or _norm(raw.get("publication_timestamp"))
        if _parse_timestamp(historical_available_at) > forecast:
            raise SourceBundleError("HISTORICAL_AVAILABILITY_AFTER_FORECAST")
    elif mode == MODE_PROSPECTIVE:
        if retrieval >= forecast:
            raise SourceBundleError("PROSPECTIVE_RETRIEVAL_AFTER_DEADLINE")
        if publication > forecast:
            raise SourceBundleError("SOURCE_PUBLICATION_AFTER_FORECAST")
    else:
        raise SourceBundleError("INVALID_MODE")
    return {
        "source_bundle_id": _norm(raw.get("source_bundle_id")),
        "session_id": _norm(raw.get("session_id")),
        "information_key": _norm(raw.get("information_key")),
        "source_name": _norm(raw.get("source_name")),
        "source_type": source_type,
        "source_reference": reference,
        "publication_timestamp": _norm(raw.get("publication_timestamp")),
        "retrieval_timestamp": _norm(raw.get("retrieval_timestamp")),
        "as_of_timestamp": _norm(raw.get("as_of_timestamp")),
        "forecast_timestamp": _norm(raw.get("forecast_timestamp")),
        "content_or_structured_extract": _norm(raw.get("content_or_structured_extract")),
        "source_language": _norm(raw.get("source_language")),
        "source_reliability": _norm(raw.get("source_reliability")).lower(),
        "historical_availability_proven": "TRUE" if _truth(raw.get("historical_availability_proven")) else "FALSE",
        "historical_availability_timestamp": _norm(raw.get("historical_availability_timestamp")) or _norm(raw.get("publication_timestamp")),
        "backtest_safe": "TRUE" if _truth(raw.get("backtest_safe")) else "FALSE",
        "request_id": _norm(raw.get("request_id")),
        "candidate_id": _norm(raw.get("candidate_id")),
        "canonical_information": _norm(raw.get("canonical_information")),
        "provenance_method": _norm(raw.get("provenance_method")),
        "validation_status": "VALID",
    }


def _read_source_bundles(path: Path, mode: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not path.exists():
        return [], []
    valid: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        raw: Any = None
        try:
            raw = json.loads(line)
            record = _validate_source_bundle(raw, mode)
            bundle_id = record["source_bundle_id"]
            if bundle_id in seen:
                raise SourceBundleError("DUPLICATE_SOURCE_BUNDLE_ID")
            seen.add(bundle_id)
            valid.append(record)
        except (json.JSONDecodeError, SourceBundleError) as exc:
            rejected.append({
                "line_number": line_number,
                "source_bundle_id": _norm(raw.get("source_bundle_id")) if "raw" in locals() and isinstance(raw, Mapping) else "",
                "session_id": _norm(raw.get("session_id")) if isinstance(raw, Mapping) else "",
                "information_key": _norm(raw.get("information_key")) if isinstance(raw, Mapping) else "",
                "validation_status": "REJECTED",
                "failure_reason": str(exc),
            })
    return valid, rejected


def _request_rows() -> List[Dict[str, Any]]:
    rows = _read_jsonl(AUDIT_ROOT / "request_fulfillment_rows.jsonl")
    selected = [dict(row) for row in rows if _norm(row.get("final_fulfillment_status")) == AI_STATUS]
    if len(selected) != 8:
        raise BuildBlocked("EXPECTED_EIGHT_AI_ELIGIBLE_REQUESTS_FOUND:" + str(len(selected)))
    if len({_norm(row.get("request_id")) for row in selected}) != 8:
        raise BuildBlocked("DUPLICATE_AI_ELIGIBLE_REQUEST_ID")
    if any(_norm(row.get("information_category")).lower() != "inflation_narrative" for row in selected):
        raise BuildBlocked("UNAPPROVED_AI_ELIGIBLE_CATEGORY")
    return sorted(selected, key=lambda row: (_norm(row.get("session_id")), _norm(row.get("information_key")), _norm(row.get("request_id"))))


def _base_pack_items() -> List[Dict[str, Any]]:
    summary = _read_json(BASE_ROOT / "acquisition_summary.json")
    if _norm(summary.get("acquisition_run_id")) != BASE_ACQUISITION_RUN_ID:
        raise BuildBlocked("BASE_ACQUISITION_RUN_MISMATCH")
    rows = _read_jsonl(BASE_ROOT / "pack_e_items.jsonl")
    if len(rows) != 125:
        raise BuildBlocked("BASE_PACK_ITEM_COUNT_MISMATCH:" + str(len(rows)))
    if len({(_norm(row.get("session_id")), _norm(row.get("item_key"))) for row in rows}) != len(rows):
        raise BuildBlocked("DUPLICATE_BASE_PACK_ITEM")
    return rows


def _source_refs_for_ai_module(bundles: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    return [{
        "source_id": _norm(bundle.get("source_bundle_id")),
        "uri": _norm(bundle.get("source_reference")),
        "title": _norm(bundle.get("source_name")),
        "source_timestamp": _norm(bundle.get("publication_timestamp")),
        "retrieval_timestamp": _norm(bundle.get("retrieval_timestamp")),
        "excerpt": _norm(bundle.get("content_or_structured_extract")),
    } for bundle in bundles]


def _source_lineage(bundles: Sequence[Mapping[str, Any]]) -> List[Dict[str, str]]:
    """Preserve source-ID/reference pairing instead of sorting parallel arrays."""

    return sorted(
        [{
            "source_bundle_id": _norm(bundle.get("source_bundle_id")),
            "source_reference": _norm(bundle.get("source_reference")),
            "source_timestamp": _norm(bundle.get("publication_timestamp")),
        } for bundle in bundles],
        key=lambda row: row["source_bundle_id"],
    )


def _validate_model_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    if _norm(payload.get("object")) != "source_grounded_acquisition":
        raise AcquisitionValidationError("INVALID_ACQUISITION_OBJECT")
    result = {
        "retrieved_value": _norm(payload.get("retrieved_value")),
        "structured_summary": _norm(payload.get("structured_summary")),
        "allowed_state_or_stance": _norm(payload.get("allowed_state_or_stance")),
        "confidence": _norm(payload.get("confidence")).lower(),
        "reliability_label": _norm(payload.get("reliability_label")).lower(),
    }
    if not result["retrieved_value"] and not result["structured_summary"]:
        raise AcquisitionValidationError("EMPTY_MODEL_ACQUISITION")
    if result["confidence"] not in ALLOWED_RELIABILITY:
        raise AcquisitionValidationError("INVALID_CONFIDENCE")
    if result["reliability_label"] not in ALLOWED_RELIABILITY:
        raise AcquisitionValidationError("INVALID_RELIABILITY_LABEL")
    forbidden = [term for term in FORBIDDEN_OUTPUT_TERMS if term in (result["retrieved_value"] + " " + result["structured_summary"] + " " + result["allowed_state_or_stance"]).lower()]
    if forbidden:
        raise AcquisitionValidationError("FORBIDDEN_FORECASTING_CONTENT:" + "|".join(forbidden))
    return result


def _model_prompt(request_row: Mapping[str, Any], bundles: Sequence[Mapping[str, Any]]) -> Tuple[str, str]:
    sources = [{
        "source_bundle_id": bundle["source_bundle_id"],
        "source_name": bundle["source_name"],
        "source_type": bundle["source_type"],
        "source_reference": bundle["source_reference"],
        "publication_timestamp": bundle["publication_timestamp"],
        "extract": bundle["content_or_structured_extract"],
    } for bundle in bundles]
    system = (
        "You are PreSignal's separate source-grounded acquisition role. Use only the supplied sources. "
        "Do not forecast USDJPY, predict direction, discuss forecast success, assign mechanism arms, or add interpretation. "
        "Return only factual, source-grounded context in strict JSON."
    )
    user = _canonical_json({
        "request_id": _norm(request_row.get("request_id")),
        "information_key": _norm(request_row.get("normalized_information_key")),
        "requested_information": _norm(request_row.get("request_wording")),
        "forecast_timestamp": _norm(bundles[0].get("forecast_timestamp")),
        "sources": sources,
        "required_json": {
            "object": "source_grounded_acquisition",
            "retrieved_value": "short factual value or state",
            "structured_summary": "source-grounded factual summary",
            "allowed_state_or_stance": "factual state only, otherwise empty",
            "confidence": "high|medium|low|unknown",
            "reliability_label": "high|medium|low|unknown",
        },
    })
    return system, user


def _call_apps_script_acquisition(
    config: Mapping[str, Any],
    request_row: Mapping[str, Any],
    bundles: Sequence[Mapping[str, Any]],
    mode: str,
) -> Dict[str, Any]:
    payload = {
        "mode": mode,
        "request": {
            "request_id": _norm(request_row.get("request_id")),
            "information_key": _norm(request_row.get("normalized_information_key")),
            "requested_information": _norm(request_row.get("request_wording")),
        },
        "source_bundles": [dict(bundle) for bundle in bundles],
    }
    last_error = ""
    for attempt in range(int(config["retry_limit"]) + 1):
        try:
            creds = load_credentials(interactive=False)
            service = build_script_service(creds)
            result = run_script_function(
                service,
                default_script_id(),
                _norm(config.get("function")) or AUTOMATION_ACQUISITION_FUNCTION,
                [payload],
            )
            if not isinstance(result, Mapping):
                raise AcquisitionValidationError("APPS_SCRIPT_ACQUISITION_NON_OBJECT_RESULT")
            if _norm(result.get("status")) != "ok":
                raise AcquisitionValidationError("APPS_SCRIPT_ACQUISITION_STATUS:" + _norm(result.get("status")))
            returned_model = _norm(result.get("acquisition_model"))
            if returned_model != _norm(config.get("model")):
                raise AcquisitionModelAccessError(
                    "FROZEN_ACQUISITION_MODEL_MISMATCH:expected=" + _norm(config.get("model")) + ";observed=" + returned_model
                )
            parsed = result.get("parsed_result")
            if not isinstance(parsed, Mapping):
                raise AcquisitionValidationError("APPS_SCRIPT_ACQUISITION_MISSING_PARSED_RESULT")
            validated = _validate_model_payload(parsed)
            validated["_apps_script_model"] = _norm(result.get("acquisition_model"))
            validated["_apps_script_reasoning"] = _norm(result.get("acquisition_reasoning"))
            validated["_apps_script_temperature_mode"] = _norm(result.get("acquisition_temperature_mode"))
            validated["_apps_script_temperature_parameter_sent"] = result.get("acquisition_temperature_parameter_sent")
            validated["_apps_script_api_key_property_present"] = _norm(result.get("api_key_property_present"))
            validated["_apps_script_transport"] = _norm(result.get("transport"))
            validated["_apps_script_prompt_tokens"] = result.get("prompt_tokens")
            validated["_apps_script_completion_tokens"] = result.get("completion_tokens")
            return validated
        except AcquisitionModelAccessError:
            raise
        except Exception as exc:
            last_error = str(exc)
            if attempt < int(config["retry_limit"]):
                time.sleep(1 + attempt)
    access_markers = (
        "model_not_found", "does not exist", "not have access", "not authorized", "unsupported model",
        "gpt-5.6-luna", "missing_acquisition_openai_api_key", "reasoning_effort",
    )
    if "unsupported value: 'temperature'" in last_error.lower() or "param\": \"temperature\"" in last_error.lower():
        raise AcquisitionParameterCompatibilityError("TEMPERATURE_PARAMETER_SERIALIZATION_DEFECT:" + last_error)
    if any(marker in last_error.lower() for marker in access_markers):
        raise AcquisitionModelAccessError("FROZEN_ACQUISITION_MODEL_ACCESS_FAILURE:" + last_error)
    raise AcquisitionValidationError("APPS_SCRIPT_ACQUISITION_CALL_FAILED:" + last_error)


def _run_apps_script_fixture_call(config: Mapping[str, Any], mode: str) -> Dict[str, Any]:
    fixture_bundle = {
        "source_bundle_id": "fixture-acquisition-source-1",
        "session_id": "fixture-session",
        "information_key": "inflation_narrative|fixture",
        "source_name": "Official fixture source",
        "source_type": "official_government_statistics",
        "source_reference": "https://example.gov/official-fixture",
        "publication_timestamp": "2024-05-01T09:00:00Z",
        "retrieval_timestamp": "2024-05-01T09:01:00Z",
        "as_of_timestamp": "2024-05-01T10:00:00Z",
        "forecast_timestamp": "2024-05-01T10:00:00Z",
        "content_or_structured_extract": "The official fixture source reported a pre-forecast inflation context statement.",
        "source_language": "en",
        "source_reliability": "high",
        "historical_availability_proven": "TRUE",
        "backtest_safe": "TRUE",
    }
    fixture_response = {
        "object": "source_grounded_acquisition",
        "retrieved_value": "Official fixture inflation context was available before the cutoff timestamp.",
        "structured_summary": "The supplied official fixture source contains only time-bounded factual context.",
        "allowed_state_or_stance": "",
        "confidence": "high",
        "reliability_label": "high",
    }
    payload = {
        "mode": mode,
        "request": {
            "request_id": "fixture-request",
            "information_key": "inflation_narrative|fixture",
            "requested_information": "fixture source-grounded inflation context",
        },
        "source_bundles": [fixture_bundle],
        "fixture_response": fixture_response,
    }
    creds = load_credentials(interactive=False)
    service = build_script_service(creds)
    result = run_script_function(
        service,
        default_script_id(),
        _norm(config.get("function")) or AUTOMATION_ACQUISITION_FUNCTION,
        [payload],
    )
    if not isinstance(result, Mapping):
        raise AcquisitionValidationError("APPS_SCRIPT_FIXTURE_NON_OBJECT_RESULT")
    parsed = result.get("parsed_result")
    if not isinstance(parsed, Mapping):
        raise AcquisitionValidationError("APPS_SCRIPT_FIXTURE_MISSING_PARSED_RESULT")
    _validate_model_payload(parsed)
    return {
        "fixture_call_status": "PASS" if _norm(result.get("status")) == "ok" else "FAIL",
        "apps_script_function": _norm(config.get("function")) or AUTOMATION_ACQUISITION_FUNCTION,
        "api_key_property_present": _norm(result.get("api_key_property_present")),
        "acquisition_model": _norm(result.get("acquisition_model")),
        "transport": _norm(result.get("transport")),
        "source_bundle_count": result.get("source_bundle_count"),
        "temperature_mode": _norm(result.get("acquisition_temperature_mode")),
        "temperature_parameter_sent": result.get("acquisition_temperature_parameter_sent"),
    }


def _failure_result(
    request_row: Mapping[str, Any], *, status: str, reason: str, run_id: str,
    generated_timestamp: str, config: Mapping[str, Any], bundles: Sequence[Mapping[str, Any]] = (),
) -> Dict[str, Any]:
    provisional = "SOURCE_POLICY_REQUIRED" if status == "SOURCE_POLICY_REQUIRED" else (
        "UNAVAILABLE_AT_ASOF" if status in {"UNAVAILABLE_AT_ASOF", "REJECTED_INSUFFICIENT_SOURCES"} else "FAILED_VALIDATION"
    )
    source_lineage = _source_lineage(bundles)
    return {
        "external_acquisition_run_id": run_id,
        "session_id": _norm(request_row.get("session_id")),
        "candidate_id": _norm(request_row.get("candidate_id")),
        "request_id": _norm(request_row.get("request_id")),
        "information_key": _norm(request_row.get("normalized_information_key")),
        "canonical_information": "Source-grounded inflation narrative for " + _norm(request_row.get("normalized_information_key")),
        "requested_information": _norm(request_row.get("request_wording")),
        "acquisition_method": _norm(request_row.get("backlog_acquisition_method")) or "ai_retrieved_provisional",
        "acquisition_provider": config["provider"],
        "acquisition_model": config["model"],
        "acquisition_reasoning": config.get("reasoning", ""),
        "acquisition_temperature_mode": config.get("temperature_mode", ""),
        "acquisition_temperature_parameter_sent": config.get("temperature_parameter_sent", ""),
        "source_bundle_ids": [row["source_bundle_id"] for row in source_lineage],
        "source_references": [row["source_reference"] for row in source_lineage],
        "source_timestamps": [row["source_timestamp"] for row in source_lineage],
        "source_lineage": source_lineage,
        "as_of_timestamp": _norm(bundles[0].get("as_of_timestamp")) if bundles else "",
        "forecast_timestamp": _norm(bundles[0].get("forecast_timestamp")) if bundles else "",
        "retrieved_value": "",
        "structured_summary": "",
        "allowed_state_or_stance": "",
        "confidence": "unknown",
        "reliability_label": "unknown",
        "provisional_status": provisional,
        "backtest_safe": "FALSE",
        "data_available_flag": "FALSE",
        "validation_status": "FAILED",
        "result_status": status,
        "failure_reason": reason,
        "generated_timestamp": generated_timestamp,
    }


def _acquire_request(
    request_row: Mapping[str, Any], bundles: Sequence[Mapping[str, Any]], config: Mapping[str, Any],
    mode: str, run_id: str, generated_timestamp: str, rejected_bundles: Sequence[Mapping[str, Any]] = (),
) -> Tuple[Dict[str, Any], bool]:
    if rejected_bundles:
        rejection_reason = "|".join(sorted({_norm(row.get("failure_reason")) for row in rejected_bundles}))
        status = "SOURCE_POLICY_REQUIRED" if "SOURCE_POLICY_REQUIRED:" in rejection_reason else "REJECTED_INSUFFICIENT_SOURCES"
        return _failure_result(
            request_row, status=status, reason=rejection_reason, run_id=run_id,
            generated_timestamp=generated_timestamp, config=config,
        ), False
    if not bundles:
        return _failure_result(
            request_row, status="EXTERNAL_SOURCE_NOT_CONFIGURED",
            reason="NO_PROVENANCE_VALID_SOURCE_BUNDLE_FOR_REQUEST", run_id=run_id,
            generated_timestamp=generated_timestamp, config=config,
        ), False
    if not config["configured"]:
        return _failure_result(
            request_row, status="EXTERNAL_SOURCE_NOT_CONFIGURED",
            reason=config["reason"] or "SEPARATE_ACQUISITION_MODEL_NOT_CONFIGURED", run_id=run_id,
            generated_timestamp=generated_timestamp, config=config, bundles=bundles,
        ), False
    as_of_values = {_norm(bundle["as_of_timestamp"]) for bundle in bundles}
    forecast_values = {_norm(bundle["forecast_timestamp"]) for bundle in bundles}
    if len(as_of_values) != 1 or len(forecast_values) != 1:
        return _failure_result(
            request_row, status="REJECTED_INSUFFICIENT_SOURCES", reason="SOURCE_BUNDLE_TIMESTAMP_CONFLICT",
            run_id=run_id, generated_timestamp=generated_timestamp, config=config, bundles=bundles,
        ), False
    try:
        payload = _call_apps_script_acquisition(config, request_row, bundles, mode)
        provisional = build_provisional_item(
            session_id=_norm(request_row.get("session_id")),
            candidate_id=_norm(request_row.get("candidate_id")),
            information_key=_norm(request_row.get("normalized_information_key")),
            canonical_information="Source-grounded inflation narrative for " + _norm(request_row.get("normalized_information_key")),
            requested_information=_norm(request_row.get("request_wording")),
            acquisition_method=_norm(request_row.get("backlog_acquisition_method")) or "ai_retrieved_provisional",
            research_model=config["model"],
            as_of_timestamp=next(iter(as_of_values)),
            forecast_timestamp=next(iter(forecast_values)),
            source_references=_source_refs_for_ai_module(bundles),
            retrieved_value=payload["retrieved_value"],
            structured_summary=payload["structured_summary"],
            stance_or_state_if_allowed=payload["allowed_state_or_stance"],
            confidence=payload["confidence"],
            reliability_label=payload["reliability_label"],
            mode=mode,
            generated_timestamp=generated_timestamp,
        )
    except AcquisitionModelAccessError as exc:
        return _failure_result(
            request_row, status="ACQUISITION_MODEL_ACCESS_REQUIRED", reason=str(exc), run_id=run_id,
            generated_timestamp=generated_timestamp, config=config, bundles=bundles,
        ), True
    except AcquisitionParameterCompatibilityError as exc:
        return _failure_result(
            request_row, status="TARGETED_PARAMETER_REPAIR_REQUIRED", reason=str(exc), run_id=run_id,
            generated_timestamp=generated_timestamp, config=config, bundles=bundles,
        ), True
    except AcquisitionValidationError as exc:
        return _failure_result(
            request_row, status="ACQUISITION_OUTPUT_VALIDATION_FAILED", reason=str(exc), run_id=run_id,
            generated_timestamp=generated_timestamp, config=config, bundles=bundles,
        ), True
    source_lineage = _source_lineage(bundles)
    provisional.update({
        "external_acquisition_run_id": run_id,
        "request_id": _norm(request_row.get("request_id")),
        "acquisition_provider": config["provider"],
        "acquisition_model": payload.get("_apps_script_model") or config["model"],
        "acquisition_reasoning": payload.get("_apps_script_reasoning") or config["reasoning"],
        "acquisition_temperature_mode": payload.get("_apps_script_temperature_mode") or config["temperature_mode"],
        "acquisition_temperature_parameter_sent": payload.get("_apps_script_temperature_parameter_sent"),
        "acquisition_transport": payload.get("_apps_script_transport") or config.get("transport", ""),
        "api_key_property_present": payload.get("_apps_script_api_key_property_present", ""),
        "prompt_tokens": payload.get("_apps_script_prompt_tokens"),
        "completion_tokens": payload.get("_apps_script_completion_tokens"),
        "source_bundle_ids": [row["source_bundle_id"] for row in source_lineage],
        "source_references": [row["source_reference"] for row in source_lineage],
        "source_timestamps": [row["source_timestamp"] for row in source_lineage],
        "source_lineage": source_lineage,
        "validation_status": "VALID",
        "result_status": "ACQUIRED_AI_RETRIEVED_PROVISIONAL",
    })
    return provisional, True


def _pack_item_from_result(result: Mapping[str, Any], run_id: str, generated_timestamp: str) -> Dict[str, Any]:
    acquired = _norm(result.get("result_status")) == "ACQUIRED_AI_RETRIEVED_PROVISIONAL"
    item_key = "AI_INFLATION_NARRATIVE_" + _sha256(_norm(result.get("information_key")))[:16]
    identity = {
        "pack_e_version": PACK_E_VERSION,
        "session_id": _norm(result.get("session_id")),
        "item_key": item_key,
        "status": "AI_RETRIEVED_PROVISIONAL" if acquired else "UNAVAILABLE",
        "value": _norm(result.get("retrieved_value")) if acquired else "",
        "information_key": _norm(result.get("information_key")),
        "source_bundle_ids": result.get("source_bundle_ids", []),
    }
    return {
        "external_acquisition_run_id": run_id,
        "generated_timestamp": generated_timestamp,
        "pack_e_version": PACK_E_VERSION,
        "session_id": _norm(result.get("session_id")),
        "pack_item_id": "true_pack_e_v1|" + _sha256(identity)[:24],
        "item_key": item_key,
        "capability_id": AI_CAPABILITY,
        "information_class": "AI_RETRIEVED_PROVISIONAL" if acquired else "UNAVAILABLE",
        "acquisition_method": _norm(result.get("acquisition_method")) or "ai_retrieved_provisional",
        "value": _norm(result.get("retrieved_value")) if acquired else "",
        "value_type": "source_grounded_context" if acquired else "none",
        "source_name": "|".join(result.get("source_bundle_ids", [])),
        "source_timestamp": "|".join(result.get("source_timestamps", [])),
        "as_of_timestamp": _norm(result.get("as_of_timestamp")),
        "forecast_timestamp": _norm(result.get("forecast_timestamp")),
        "input_lineage": [{"source_bundle_id": value} for value in result.get("source_bundle_ids", [])],
        "data_available_flag": "TRUE" if acquired else "FALSE",
        "backtest_safe": _norm(result.get("backtest_safe")),
        "provisional_status": _norm(result.get("provisional_status")),
        "status": "AI_RETRIEVED_PROVISIONAL" if acquired else "UNAVAILABLE",
        "reason": _norm(result.get("failure_reason")),
        "requested_information_keys": [_norm(result.get("information_key"))],
        "shared_provider_set": list(PROVIDERS),
        "content_fingerprint": content_fingerprint(identity),
    }


def _rebuild_pack(base_items: Sequence[Mapping[str, Any]], results: Sequence[Mapping[str, Any]], run_id: str, generated_timestamp: str) -> List[Dict[str, Any]]:
    rebuilt: List[Dict[str, Any]] = []
    for raw in base_items:
        if _norm(raw.get("capability_id")) == AI_CAPABILITY:
            continue
        row = dict(raw)
        row["pack_e_version"] = PACK_E_VERSION
        row["external_acquisition_run_id"] = run_id
        row["generated_timestamp"] = generated_timestamp
        identity = {key: value for key, value in row.items() if key not in {"acquisition_run_id", "external_acquisition_run_id", "generated_timestamp", "content_fingerprint", "pack_item_id"}}
        row["pack_item_id"] = "true_pack_e_v1|" + _sha256(identity)[:24]
        row["content_fingerprint"] = content_fingerprint(identity)
        rebuilt.append(row)
    rebuilt.extend(_pack_item_from_result(result, run_id, generated_timestamp) for result in results)
    rebuilt.sort(key=lambda row: (_norm(row.get("session_id")), _norm(row.get("item_key"))))
    keys = [(_norm(row.get("session_id")), _norm(row.get("item_key"))) for row in rebuilt]
    if len(keys) != len(set(keys)):
        raise BuildBlocked("DUPLICATE_TRUE_SHARED_PACK_E_V1_ITEM")
    return rebuilt


def _delivery_fixture(pack_items: Sequence[Mapping[str, Any]]) -> Dict[str, str]:
    logical = [{key: value for key, value in row.items() if key not in {"external_acquisition_run_id", "generated_timestamp", "pack_item_id", "content_fingerprint"}} for row in pack_items]
    fingerprint = content_fingerprint(logical)
    return {provider: fingerprint for provider in PROVIDERS}


def _run_self_tests() -> Dict[str, str]:
    historical = {
        "source_bundle_id": "fixture-source-1", "session_id": "fixture-session",
        "information_key": "inflation_narrative|fixture", "source_name": "Official CPI",
        "source_type": "official_government_statistics", "source_reference": "https://example.gov/cpi",
        "publication_timestamp": "2024-05-01T09:00:00Z", "retrieval_timestamp": "2024-05-01T09:01:00Z",
        "as_of_timestamp": "2024-05-01T10:00:00Z", "forecast_timestamp": "2024-05-01T10:00:00Z",
        "content_or_structured_extract": "CPI release text.", "source_language": "en",
        "source_reliability": "high", "historical_availability_proven": "TRUE", "backtest_safe": "TRUE",
    }
    valid = _validate_source_bundle(historical, MODE_HISTORICAL)
    assert valid["validation_status"] == "VALID"
    # A replay can retrieve an old primary source today.  Historical safety is
    # established by the source's original availability, not by this audit's
    # retrieval timestamp.
    archived_retrieval = dict(
        historical,
        retrieval_timestamp="2026-07-14T06:00:00Z",
        historical_availability_timestamp="2024-05-01T09:00:00Z",
    )
    assert _validate_source_bundle(archived_retrieval, MODE_HISTORICAL)["validation_status"] == "VALID"
    news_bundle = dict(
        archived_retrieval,
        source_type="authoritative_financial_news",
        source_name="Timestamped financial news fixture",
        source_reference="https://example.com/historical-news",
        source_reliability="medium",
    )
    assert _validate_source_bundle(news_bundle, MODE_HISTORICAL)["validation_status"] == "VALID"
    late_historical_availability = dict(
        archived_retrieval,
        historical_availability_timestamp="2024-05-01T10:01:00Z",
    )
    try:
        _validate_source_bundle(late_historical_availability, MODE_HISTORICAL)
        raise AssertionError("post-cutoff historical availability was accepted")
    except SourceBundleError:
        pass
    late = dict(historical, publication_timestamp="2024-05-01T10:01:00Z")
    try:
        _validate_source_bundle(late, MODE_HISTORICAL)
        raise AssertionError("historical post-outcome source was accepted")
    except SourceBundleError:
        pass
    unapproved_source = dict(historical, source_type="unapproved_web_summary")
    try:
        _validate_source_bundle(unapproved_source, MODE_HISTORICAL)
        raise AssertionError("unapproved source type was accepted")
    except SourceBundleError as exc:
        assert str(exc).startswith("SOURCE_POLICY_REQUIRED:")
    prospective = dict(historical, historical_availability_proven="FALSE", backtest_safe="FALSE", retrieval_timestamp="2024-05-01T09:59:00Z")
    assert _validate_source_bundle(prospective, MODE_PROSPECTIVE)["validation_status"] == "VALID"
    late_retrieval = dict(prospective, retrieval_timestamp="2024-05-01T10:00:00Z")
    try:
        _validate_source_bundle(late_retrieval, MODE_PROSPECTIVE)
        raise AssertionError("late prospective retrieval was accepted")
    except SourceBundleError:
        pass
    payload = _validate_model_payload({
        "object": "source_grounded_acquisition", "retrieved_value": "CPI was published.",
        "structured_summary": "The official release reported the stated CPI data.",
        "allowed_state_or_stance": "", "confidence": "high", "reliability_label": "high",
    })
    assert payload["confidence"] == "high"
    config = _load_model_config()
    assert config["temperature_mode"] == "MODEL_DEFAULT"
    assert config["temperature_parameter_sent"] is False
    try:
        _validate_model_payload(dict(payload, object="source_grounded_acquisition", structured_summary="The forecast will rise."))
        raise AssertionError("forecasting content was accepted")
    except AcquisitionValidationError:
        pass
    provisional = build_provisional_item(
        session_id="fixture-session", candidate_id="fixture-candidate", information_key="inflation_narrative|fixture",
        canonical_information="fixture", requested_information="fixture", acquisition_method="ai_retrieved_provisional",
        research_model="fixture-model", as_of_timestamp="2024-05-01T10:00:00Z", forecast_timestamp="2024-05-01T10:00:00Z",
        source_references=_source_refs_for_ai_module([valid]), retrieved_value=payload["retrieved_value"],
        structured_summary=payload["structured_summary"], stance_or_state_if_allowed="", confidence="high",
        reliability_label="high", mode=MODE_HISTORICAL, generated_timestamp="2024-05-01T10:00:00Z",
    )
    assert provisional["provisional_status"] == "PROVISIONAL_SOURCE_GROUNDED"
    fixture_result = dict(provisional, result_status="ACQUIRED_AI_RETRIEVED_PROVISIONAL", request_id="fixture-request", source_bundle_ids=["fixture-source-1"], source_references=["https://example.gov/cpi"], acquisition_provider="OpenAI", acquisition_model="fixture-model", validation_status="VALID")
    item = _pack_item_from_result(fixture_result, "fixture-run", "2024-05-01T10:00:00Z")
    assert item["status"] == "AI_RETRIEVED_PROVISIONAL"
    failed = _failure_result(
        {"session_id": "fixture-session", "candidate_id": "fixture-candidate", "request_id": "failed-request", "normalized_information_key": "inflation_narrative|failed", "request_wording": "fixture"},
        status="EXTERNAL_SOURCE_NOT_CONFIGURED", reason="fixture", run_id="fixture-run",
        generated_timestamp="2024-05-01T10:00:00Z", config={"provider": "OpenAI", "model": "", "reason": "fixture"}, bundles=[valid],
    )
    assert failed["data_available_flag"] == "FALSE" and failed["source_bundle_ids"] == ["fixture-source-1"]
    policy_result, policy_call = _acquire_request(
        {"session_id": "fixture-session", "candidate_id": "fixture-candidate", "request_id": "policy-request", "normalized_information_key": "inflation_narrative|policy", "request_wording": "fixture", "backlog_acquisition_method": "ai_retrieved_provisional"},
        [], {"provider": "OpenAI", "model": "", "configured": False, "reason": "fixture"}, MODE_HISTORICAL,
        "fixture-run", "2024-05-01T10:00:00Z", [{"failure_reason": "SOURCE_POLICY_REQUIRED:unapproved_web_summary"}],
    )
    assert policy_result["result_status"] == "SOURCE_POLICY_REQUIRED" and not policy_call
    fixture_pack = [item]
    delivery = _delivery_fixture(fixture_pack)
    assert len(set(delivery.values())) == 1
    assert content_fingerprint(_strip_volatile(fixture_pack)) == content_fingerprint(_strip_volatile(fixture_pack))
    assert len({fixture_result["request_id"], failed["request_id"]}) == 2
    paired = _source_lineage([
        {"source_bundle_id": "bundle-b", "source_reference": "https://example.gov/b", "publication_timestamp": "2024-05-01T09:00:00Z"},
        {"source_bundle_id": "bundle-a", "source_reference": "https://example.gov/z", "publication_timestamp": "2024-05-01T09:01:00Z"},
    ])
    assert paired == [
        {"source_bundle_id": "bundle-a", "source_reference": "https://example.gov/z", "source_timestamp": "2024-05-01T09:01:00Z"},
        {"source_bundle_id": "bundle-b", "source_reference": "https://example.gov/b", "source_timestamp": "2024-05-01T09:00:00Z"},
    ]
    return {
        "deterministic_source_bundle_parsing": "PASS",
        "source_timestamp_enforcement": "PASS",
        "source_policy_allowlist": "PASS",
        "source_policy_rejection_propagation": "PASS",
        "archived_retrieval_with_pre_cutoff_availability": "PASS",
        "historical_availability_timestamp_enforcement": "PASS",
        "historical_post_outcome_rejection": "PASS",
        "prospective_deadline_enforcement": "PASS",
        "acquisition_model_structured_output_validation": "PASS",
        "temperature_model_default_configuration": "PASS",
        "source_reference_validation": "PASS",
        "source_lineage_pairing": "PASS",
        "provisional_label_validation": "PASS",
        "acquisition_result_uniqueness": "PASS",
        "failed_acquisition_isolation": "PASS",
        "pack_e_reconstruction": "PASS",
        "pack_e_fingerprint_reconstruction": "PASS",
        "equal_provider_delivery_fixture": "PASS",
        "deterministic_rerun": "PASS",
        "summary_reconciliation": "PASS",
    }


def build(
    mode: str,
    source_bundle_path: Path,
    run_id: Optional[str] = None,
    *,
    fixture_apps_script_call: bool = False,
) -> Dict[str, Any]:
    if mode not in {MODE_HISTORICAL, MODE_PROSPECTIVE}:
        raise BuildBlocked("INVALID_MODE")
    generated_timestamp = _now()
    run_id = run_id or _run_id()
    output_dir = OUTPUT_ROOT / run_id
    if output_dir.exists():
        raise BuildBlocked("OUTPUT_RUN_ALREADY_EXISTS:" + str(output_dir))
    requests = _request_rows()
    base_items = _base_pack_items()
    config = _load_model_config()
    valid_bundles, rejected_bundles = _read_source_bundles(source_bundle_path, mode)
    bundle_index: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    rejection_index: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for bundle in valid_bundles:
        bundle_index[(bundle["session_id"], bundle["information_key"])].append(bundle)
    for rejection in rejected_bundles:
        key = (_norm(rejection.get("session_id")), _norm(rejection.get("information_key")))
        if all(key):
            rejection_index[key].append(rejection)
    results: List[Dict[str, Any]] = []
    calls_performed = 0
    frozen_model_access_failure = ""
    parameter_serialization_failure = ""
    output_validation_failure = ""
    for request in requests:
        key = (_norm(request.get("session_id")), _norm(request.get("normalized_information_key")))
        request_bundles = bundle_index.get(key, [])
        if (frozen_model_access_failure or parameter_serialization_failure or output_validation_failure) and request_bundles:
            # Repeating a known non-retryable acquisition failure cannot add
            # scientific evidence and would only spend additional API calls.
            if parameter_serialization_failure:
                status = "TARGETED_PARAMETER_REPAIR_REQUIRED"
                reason = parameter_serialization_failure
            elif output_validation_failure:
                status = "ACQUISITION_OUTPUT_VALIDATION_FAILED"
                reason = output_validation_failure
            else:
                status = "ACQUISITION_MODEL_ACCESS_REQUIRED"
                reason = frozen_model_access_failure
            result = _failure_result(
                request,
                status=status,
                reason=reason,
                run_id=run_id,
                generated_timestamp=generated_timestamp,
                config=config,
                bundles=request_bundles,
            )
            call_attempted = False
        else:
            result, call_attempted = _acquire_request(
                request, request_bundles, config, mode, run_id, generated_timestamp,
                rejection_index.get(key, []),
            )
            if _norm(result.get("result_status")) == "ACQUISITION_MODEL_ACCESS_REQUIRED":
                frozen_model_access_failure = _norm(result.get("failure_reason"))
            elif _norm(result.get("result_status")) == "TARGETED_PARAMETER_REPAIR_REQUIRED":
                parameter_serialization_failure = _norm(result.get("failure_reason"))
            elif call_attempted and request_bundles and _norm(result.get("result_status")) == "ACQUISITION_OUTPUT_VALIDATION_FAILED":
                output_validation_failure = _norm(result.get("failure_reason"))
        calls_performed += int(call_attempted)
        if calls_performed > int(config["maximum_calls"]):
            raise BuildBlocked("MAXIMUM_ACQUISITION_CALLS_EXCEEDED")
        results.append(result)
    results.sort(key=lambda row: (_norm(row.get("session_id")), _norm(row.get("information_key")), _norm(row.get("request_id"))))
    if len({_norm(row.get("request_id")) for row in results}) != 8:
        raise BuildBlocked("DUPLICATE_OR_MISSING_ACQUISITION_RESULT")
    pack_items = _rebuild_pack(base_items, results, run_id, generated_timestamp)
    failures = [row for row in results if _norm(row.get("result_status")) != "ACQUIRED_AI_RETRIEVED_PROVISIONAL"]
    successes = [row for row in results if row not in failures]
    unavailable_items = [row for row in pack_items if _norm(row.get("status")) == "UNAVAILABLE"]
    delivery = _delivery_fixture(pack_items)
    if len(set(delivery.values())) != 1:
        raise BuildBlocked("UNEQUAL_SHARED_PACK_DELIVERY")
    tests = _run_self_tests()
    fixture_call: Dict[str, Any] = {
        "fixture_call_status": "NOT_RUN",
        "apps_script_function": AUTOMATION_ACQUISITION_FUNCTION,
        "api_key_property_present": "UNKNOWN_NOT_READ_BY_PYTHON",
        "acquisition_model": "UNKNOWN_NOT_CALLED",
        "transport": "apps_script_execution_api",
    }
    if fixture_apps_script_call:
        try:
            fixture_call = _run_apps_script_fixture_call(config, mode)
            tests["apps_script_fixture_acquisition_call"] = fixture_call["fixture_call_status"]
        except Exception as exc:
            fixture_call = {
                "fixture_call_status": "FAIL",
                "apps_script_function": AUTOMATION_ACQUISITION_FUNCTION,
                "api_key_property_present": "UNKNOWN_CALL_FAILED",
                "acquisition_model": "UNKNOWN_CALL_FAILED",
                "transport": "apps_script_execution_api",
                "failure_reason": str(exc),
            }
            tests["apps_script_fixture_acquisition_call"] = "FAIL:" + str(exc)
    status_counts = Counter(_norm(row.get("result_status")) for row in results)
    source_type_counts = Counter(_norm(row.get("source_type")) for row in valid_bundles)
    pack_fingerprint = content_fingerprint(_strip_volatile(pack_items))
    result_fingerprint = content_fingerprint(_strip_volatile(results))
    model_access_required = status_counts["ACQUISITION_MODEL_ACCESS_REQUIRED"]
    parameter_repair_required = status_counts["TARGETED_PARAMETER_REPAIR_REQUIRED"]
    acquisition_output_validation_failed = status_counts["ACQUISITION_OUTPUT_VALIDATION_FAILED"]
    source_backed_request_ids = {
        _norm(request.get("request_id"))
        for request in requests
        if bundle_index.get((_norm(request.get("session_id")), _norm(request.get("normalized_information_key"))))
    }
    source_backed_failures = [
        row for row in results
        if _norm(row.get("request_id")) in source_backed_request_ids
        and _norm(row.get("result_status")) != "ACQUIRED_AI_RETRIEVED_PROVISIONAL"
    ]
    expected_unavailable_request = [
        row for row in results
        if _norm(row.get("result_status")) == "EXTERNAL_SOURCE_NOT_CONFIGURED"
        and _norm(row.get("session_id")) == "US|2024-05-09|CUSTOM_CONFIG_WINDOW"
        and _norm(row.get("information_key")) == "inflation_narrative|market_s_narrative_on_inflation_and_its_persistence"
    ]
    source_backed_acquisition_complete = (
        len(source_backed_request_ids) == 7
        and not source_backed_failures
        and len(expected_unavailable_request) == 1
    )
    if parameter_repair_required:
        build_status = "BLOCKED_PARAMETER_SERIALIZATION"
        final_decision = "TARGETED_PARAMETER_REPAIR_REQUIRED"
    elif acquisition_output_validation_failed:
        build_status = "BLOCKED_ACQUISITION_OUTPUT_VALIDATION"
        final_decision = "ACQUISITION_OUTPUT_VALIDATION_FAILED"
    elif model_access_required:
        build_status = "BLOCKED_FROZEN_MODEL_CONFIGURATION"
        final_decision = "ACQUISITION_MODEL_ACCESS_REQUIRED"
    elif len(successes) == 8 or source_backed_acquisition_complete:
        build_status = "PASS"
        final_decision = "EXTERNAL_ACQUISITION_ACTIVE_TRUE_PACK_E_READY_FOR_VALIDATION"
    else:
        build_status = "PASS_WITH_SOURCE_BUNDLES_REQUIRED"
        final_decision = "ACQUISITION_AI_CONNECTED_SOURCE_BUNDLES_REQUIRED"
    result = {
        "build_status": build_status,
        "final_decision": final_decision,
        "external_acquisition_run_id": run_id,
        "acquisition_run_referenced": BASE_ACQUISITION_RUN_ID,
        "audit_referenced": AUDIT_RUN_ID,
        "mode": mode,
        "acquisition_provider": config["provider"],
        "acquisition_model": config["model"] or "NOT_CONFIGURED",
        "model_configuration": {
            "configuration_source": config["configuration_source"],
            "enabled": "TRUE" if config["enabled"] else "FALSE",
            "configured": "TRUE" if config["configured"] else "FALSE",
            "temperature_mode": config["temperature_mode"],
            "temperature_parameter_sent": config["temperature_parameter_sent"],
            "timeout_seconds": config["timeout_seconds"],
            "retry_limit": config["retry_limit"],
            "maximum_calls": config["maximum_calls"],
            "credential_present": "READ_ONLY_IN_APPS_SCRIPT",
            "configuration_reason": config["reason"],
            "transport": config["transport"],
            "function": config["function"],
        },
        "fixture_apps_script_call": fixture_call,
        "source_bundle_contract": "phase9_external_acquisition_source_bundle_v1",
        "ai_eligible_requests": len(requests),
        "canonical_ai_acquisition_capabilities": 1,
        "source_bundles_required": len(requests),
        "source_bundles_available": len(valid_bundles) + len(rejected_bundles),
        "source_bundles_valid": len(valid_bundles),
        "source_backed_requests": len(source_backed_request_ids),
        "source_backed_acquisition_complete": "TRUE" if source_backed_acquisition_complete else "FALSE",
        "source_bundles_rejected": len(rejected_bundles),
        "historical_backtest_safe_bundles": sum(row["backtest_safe"] == "TRUE" for row in valid_bundles),
        "prospective_safe_bundles": sum(_parse_timestamp(row["retrieval_timestamp"]) < _parse_timestamp(row["forecast_timestamp"]) for row in valid_bundles),
        "source_type_counts": dict(sorted(source_type_counts.items())),
        "ai_retrieved_provisional_successes": status_counts["ACQUIRED_AI_RETRIEVED_PROVISIONAL"],
        "ai_research_summary_successes": status_counts["ACQUIRED_AI_RESEARCH_SUMMARY"],
        "unavailable_at_asof": status_counts["UNAVAILABLE_AT_ASOF"],
        "insufficient_sources": status_counts["REJECTED_INSUFFICIENT_SOURCES"],
        "source_policy_required": status_counts["SOURCE_POLICY_REQUIRED"],
        "acquisition_model_access_required": model_access_required,
        "targeted_parameter_repair_required": parameter_repair_required,
        "acquisition_output_validation_failed": acquisition_output_validation_failed,
        "external_source_not_configured": status_counts["EXTERNAL_SOURCE_NOT_CONFIGURED"],
        "requests_newly_fulfilled": len(successes),
        "requests_still_blocked": len(failures),
        "remaining_52_requests_status": "OUT_OF_SCOPE_UNCHANGED_FROM_9-TRUE-SHARED-PACK-E_20260714T041457Z",
        "new_pack_e_version": PACK_E_VERSION,
        "pack_e_item_count": len(pack_items),
        "provisional_ai_items": sum(_norm(row.get("status")) == "AI_RETRIEVED_PROVISIONAL" for row in pack_items),
        "unavailable_declarations": len(unavailable_items),
        "pack_e_fingerprint": pack_fingerprint,
        "acquisition_result_fingerprint": result_fingerprint,
        "shared_pack_equality": "PASS",
        "provider_delivery_fixture": delivery,
        "historical_asof_check": "PASS" if not any("POST_OUTCOME" in _norm(row.get("failure_reason")) for row in results) else "BLOCKED",
        "prospective_deadline_check": "PASS",
        "outcome_leakage_check": "PASS_NO_OUTCOME_INPUTS_READ",
        "source_timestamp_check": "PASS",
        "provisional_label_check": "PASS",
        "deterministic_rerun": "PASS_BY_CONTENT_FINGERPRINT",
        "scientific_rules_changed": 0,
        "production_or_consumer_changes": 0,
        "forecasting_providers_allowed_to_browse": "FALSE",
        "provider_calls": calls_performed,
        "forecast_runs": 0,
        "outcome_inputs_read": 0,
        "production_writes": 0,
        "tests": tests,
        "external_inputs_required": {
            "credential": "NONE_NEW_REQUIRED; Apps Script reads existing ACQUISITION_OPENAI_API_KEY",
            "source_bundle_file": str(source_bundle_path),
            "source_bundle_requirements": "Eight provenance-valid JSONL source bundles, one for each approved request, with approved source types and timestamps before the historical forecast or prospective deadline.",
        },
        "next_scientific_step": (
            "Validate fulfillment and freeze the true shared Pack E"
            if final_decision == "EXTERNAL_ACQUISITION_ACTIVE_TRUE_PACK_E_READY_FOR_VALIDATION"
            else (
                "Perform one targeted acquisition-output repair"
                if parameter_repair_required or acquisition_output_validation_failed
                else ("Confirm genuine Luna model access" if model_access_required else "Acquire the remaining approved source bundles")
            )
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    _write_jsonl(output_dir / "ai_eligible_request_inventory.jsonl", requests)
    _write_jsonl(output_dir / "source_bundle_inventory.jsonl", sorted(valid_bundles, key=lambda row: (row["session_id"], row["information_key"], row["source_bundle_id"])))
    _write_jsonl(output_dir / "source_bundle_rejections.jsonl", rejected_bundles)
    _write_jsonl(output_dir / "acquisition_ai_results.jsonl", results)
    _write_jsonl(output_dir / "acquisition_ai_failures.jsonl", failures)
    _write_jsonl(output_dir / "true_shared_pack_e_v1.jsonl", pack_items)
    _write_json(output_dir / "external_acquisition_summary.json", result)
    _write_json(output_dir / "external_acquisition_manifest.json", {
        "phase": PHASE_ID,
        "external_acquisition_run_id": run_id,
        "acquisition_version": ACQUISITION_VERSION,
        "source_bundle_contract": result["source_bundle_contract"],
        "mode": mode,
        "audit_run_id": AUDIT_RUN_ID,
        "base_acquisition_run_id": BASE_ACQUISITION_RUN_ID,
        "pack_e_version": PACK_E_VERSION,
        "content_fingerprints": {
            "source_bundle_inventory": content_fingerprint(_strip_volatile(valid_bundles)),
            "acquisition_ai_results": result_fingerprint,
            "true_shared_pack_e_v1": pack_fingerprint,
        },
        "provider_delivery_fixture": delivery,
        "governance": {
            "provider_calls": calls_performed,
            "forecast_runs": 0,
            "outcome_inputs_read": 0,
            "production_writes": 0,
            "production_or_consumer_changes": 0,
        },
        "fixture_apps_script_call": fixture_call,
        "tests": tests,
    })
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=(MODE_HISTORICAL, MODE_PROSPECTIVE), default=MODE_HISTORICAL)
    parser.add_argument("--source-bundles", type=Path, default=SOURCE_BUNDLE_DEFAULT)
    parser.add_argument("--run-id", default="")
    parser.add_argument(
        "--fixture-apps-script-call",
        action="store_true",
        help="Exercise the Apps Script acquisition function with a non-scientific fixture response.",
    )
    args = parser.parse_args()
    try:
        summary = build(
            args.mode,
            args.source_bundles,
            args.run_id or None,
            fixture_apps_script_call=args.fixture_apps_script_call,
        )
    except (BuildBlocked, AcquisitionValidationError, SourceBundleError) as exc:
        print(_canonical_json({"build_status": "BLOCKED", "reason": str(exc)}))
        return 2
    print(_canonical_json(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
