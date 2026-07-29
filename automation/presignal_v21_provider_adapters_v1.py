"""Narrow, provider-format normalization boundary for v2.1.

This module deliberately translates response envelopes and established legacy
aliases only.  Transport, scientific contract validation, and canonical state
classification remain with their existing owners.
"""
from __future__ import annotations

import json
from enum import Enum
from typing import Any, Callable, Mapping

from automation import presignal_v21_historical_verification_r3_compat_r2_contract_v1 as compat_r2
from automation import presignal_v21_historical_verification_r3_compat_r3_contract_v1 as compat_r3
from automation import presignal_v21_historical_verification_r3_compat_r4_contract_v1 as compat_r4
from automation import presignal_v21_historical_verification_r3_compat_r5_contract_v1 as compat_r5


class ParseStatus(str, Enum):
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    PARSED = "PARSED"
    PARSE_FAILED = "PARSE_FAILED"


class ValidationStatus(str, Enum):
    NOT_VALIDATED = "NOT_VALIDATED"
    VALID = "VALID"
    INVALID = "INVALID"


ATTENTION_PROVIDER_IDENTITY_ALIASES: dict[str, dict[str, str]] = {
    "Anthropic": {
        "presignal_v2": "Anthropic",
        "presignal_v2_shadow_research": "Anthropic",
        "macroeconomic_research_model": "Anthropic",
        "PreSignal_v2.0_shadow_research": "Anthropic",
    },
    "Gemini": {
        "macro_model": "Gemini",
        "presignal_v2_0": "Gemini",
        "ps_v2_macro_research_model": "Gemini",
        "presignal_v2_market_session_attention_task": "Gemini",
    },
    "OpenAI": {
        "macro_research_model": "OpenAI",
        "PreSignal v2.0": "OpenAI",
        "macroeconomic_research": "OpenAI",
        "market_research_model": "OpenAI",
    },
}


def _json_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, Mapping):
        return dict(raw)
    if not isinstance(raw, str):
        raise ValueError("PROVIDER_OUTPUT_NOT_OBJECT")
    text = raw.strip()
    if not text:
        raise ValueError("PROVIDER_OUTPUT_EMPTY")
    if text.startswith("```") and text.endswith("```"):
        try:
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        except IndexError as exc:
            raise ValueError("PROVIDER_OUTPUT_NOT_JSON") from exc
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("PROVIDER_OUTPUT_NOT_JSON") from exc
    if not isinstance(value, Mapping):
        raise ValueError("PROVIDER_OUTPUT_NOT_OBJECT")
    return dict(value)


def extract_raw_provider_claim(raw: Any) -> str | None:
    """Best-effort access to model-returned provider text without normalizing it."""
    try:
        payload = _json_object(raw)
    except Exception:
        return None
    provider = payload.get("provider")
    return str(provider) if provider is not None else None


def _extract_envelope(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract the established Gemini forecast response-contract envelope."""
    if set(payload) != {"forecast", "response_contract"}:
        return payload
    if not isinstance(payload["forecast"], Mapping) or not isinstance(payload["response_contract"], Mapping):
        raise ValueError("PROVIDER_OUTPUT_ENVELOPE")
    return dict(payload["forecast"])


def _unwrap_bridge_transport_result(transport_result: Mapping[str, Any]) -> dict[str, Any]:
    """Flatten the preserved Apps Script execution wrapper to its result payload."""
    direct = dict(transport_result)
    nested_result = transport_result.get("result")
    if isinstance(nested_result, Mapping) and (
        "raw_output" in nested_result or "raw_response" in nested_result
    ):
        return dict(nested_result)
    response = transport_result.get("response")
    if isinstance(response, Mapping):
        execution_response = response.get("response")
        if isinstance(execution_response, Mapping):
            execution_result = execution_response.get("result")
            if isinstance(execution_result, Mapping) and (
                "raw_output" in execution_result or "raw_response" in execution_result
            ):
                return dict(execution_result)
    return direct


def normalize_provider_response(*, stage: str, requested_provider: str, requested_model: str,
                                transport_result: Mapping[str, Any], contract_version: str | None = None,
                                validator: Callable[[Mapping[str, Any]], bool] | None = None,
                                authoritative_attention_provider_binding: bool = False) -> dict[str, Any]:
    """Return neutral response facts without deciding runtime or scientific state."""
    transport_payload = _unwrap_bridge_transport_result(transport_result)
    raw = transport_payload.get("raw_output", transport_payload.get("raw_response"))
    result: dict[str, Any] = {
        "requested_provider": requested_provider, "requested_model": requested_model,
        "actual_provider": transport_payload.get("actual_provider", transport_result.get("actual_provider")),
        "actual_model": transport_payload.get("actual_model", transport_result.get("actual_model")),
        "raw_response": raw, "raw_response_reference": transport_result.get("raw_response_reference"),
        "canonical_payload": None, "parse_status": ParseStatus.NOT_ATTEMPTED,
        "validation_status": ValidationStatus.NOT_VALIDATED, "normalization_notes": [],
        "provider_metadata": {
            key: transport_payload.get(key, transport_result.get(key))
            for key in ("status", "transport_status", "completed_timestamp", "prompt_tokens", "completion_tokens", "latency_ms")
            if key in transport_payload or key in transport_result
        },
    }
    if raw is None:
        return result
    try:
        payload = _json_object(raw)
        if stage == "FORECAST":
            payload = _extract_envelope(payload)
        if stage == "ATTENTION":
            payload, notes = normalize_attention_identity(
                payload,
                requested_provider,
                contract_version,
                actual_provider=result["actual_provider"],
                actual_model=result["actual_model"],
                requested_model=requested_model,
                authoritative_provider_binding=authoritative_attention_provider_binding,
            )
            result["normalization_notes"].extend(notes)
        result["canonical_payload"] = payload
        result["parse_status"] = ParseStatus.PARSED
        if validator is not None:
            result["validation_status"] = ValidationStatus.VALID if validator(payload) else ValidationStatus.INVALID
    except (ValueError, TypeError) as exc:
        result["parse_status"] = ParseStatus.PARSE_FAILED
        result["normalization_notes"].append({"reason": str(exc)})
    return result


def normalize_prospective_forecast_response(*, requested_provider: str, requested_model: str,
                                            transport_result: Mapping[str, Any],
                                            scientific_validator: Callable[[Mapping[str, Any]], Any] | None = None) -> dict[str, Any]:
    """Prospective forecast entrypoint; validation remains caller-owned.

    The validator may return ``False`` or raise to report a scientific-contract
    failure.  Neither outcome is a transport or evaluation classification.
    """
    result = normalize_provider_response(
        stage="FORECAST", requested_provider=requested_provider,
        requested_model=requested_model, transport_result=transport_result,
    )
    if result["parse_status"] != ParseStatus.PARSED or scientific_validator is None:
        return result
    try:
        accepted = scientific_validator(result["canonical_payload"])
        result["validation_status"] = ValidationStatus.INVALID if accepted is False else ValidationStatus.VALID
    except Exception as exc:
        result["validation_status"] = ValidationStatus.INVALID
        result["normalization_notes"].append({"scientific_validation_error": str(exc)})
    return result


def normalize_attention_identity(
    payload: Mapping[str, Any],
    provider: str,
    contract_version: str | None,
    *,
    actual_provider: str | None = None,
    actual_model: str | None = None,
    requested_model: str | None = None,
    authoritative_provider_binding: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    value, notes = dict(payload), []
    if value.get("object") == "session_attention_map":
        emitted_provider = value.get("provider")
        if authoritative_provider_binding:
            if not provider or not requested_model:
                raise ValueError("ATTENTION_PROVIDER_AUTHORITY_REQUEST_MISSING")
            if not actual_provider or not actual_model:
                raise ValueError("ATTENTION_PROVIDER_AUTHORITY_METADATA_MISSING")
            if actual_provider != provider or actual_model != requested_model:
                raise ValueError("ATTENTION_PROVIDER_AUTHORITY_CONFLICT")
            note = {
                "normalization_type": "attention_provider_authority_binding",
                "raw_claimed_provider": emitted_provider,
                "canonical_provider": provider,
                "requested_provider": provider,
                "requested_model": requested_model,
                "actual_provider": actual_provider,
                "actual_model": actual_model,
                "reason": "Historical session_attention_map canonical provider is bound from the frozen call manifest when transport-confirmed provider/model match exactly; model-returned provider text is preserved only as a raw claim.",
            }
            value["provider"] = provider
            value["_raw_claimed_provider"] = emitted_provider
            value["_provider_identity_normalization"] = note
            notes.append(note)
            return value, notes
    if value.get("object") == "session_attention_map" and not (
        provider == "Anthropic" and contract_version in (compat_r4.CONTRACT_VERSION, compat_r5.CONTRACT_VERSION)
    ):
        alias_map = ATTENTION_PROVIDER_IDENTITY_ALIASES.get(provider, {})
        if emitted_provider in alias_map:
            if (
                emitted_provider in {"PreSignal_v2.0_shadow_research", "presignal_v2_shadow_research"}
                and (
                    provider != "Anthropic"
                    or (actual_provider is not None and actual_provider != "Anthropic")
                    or (actual_model is not None and actual_model not in {"", "claude-haiku-4-5"})
                    or (requested_model is not None and requested_model not in {"", "claude-haiku-4-5"})
                )
            ):
                raise ValueError("ANTHROPIC_SHADOW_ALIAS_RUNTIME_MISMATCH")
            note = {
                "normalization_type": "attention_provider_identity_alias",
                "original_provider": emitted_provider,
                "normalized_provider": alias_map[emitted_provider],
                "requested_provider": provider,
                "reason": "Preserved historical Attention outputs proved this provider label as an exact legacy alias for the manifest-bound provider route.",
            }
            value["provider"] = alias_map[emitted_provider]
            value["_provider_identity_normalization"] = note
            notes.append(note)
    if provider != "Anthropic":
        return value, notes
    if contract_version in (compat_r4.CONTRACT_VERSION, compat_r5.CONTRACT_VERSION):
        rule = compat_r4.NORMALIZATION["anthropic_runtime_identity"]
        emitted_provider, emitted_model = value.get("provider"), value.get("model")
        if emitted_provider not in rule["accepted_emitted_provider_identities"] or emitted_model not in rule["accepted_emitted_model_identities"]:
            raise ValueError("ANTHROPIC_EMITTED_RUNTIME_IDENTITY_CONTRADICTION")
        value["provider"] = rule["runtime_provider"]
        note = {"runtime_provider": rule["runtime_provider"], "runtime_model": rule["runtime_model"], "model_emitted_provider_identity": emitted_provider, "model_emitted_model_identity": emitted_model, "acceptance_reason": rule["reason"]}
        value["_provider_identity_normalization"] = note
        notes.append(note)
    elif contract_version == compat_r3.CONTRACT_VERSION:
        rule = compat_r3.NORMALIZATION["anthropic_attention_identity"]
        if value.get("provider") == rule["raw_provider"] and value.get("model") == rule["raw_model"]:
            note = {"original_provider": rule["raw_provider"], "original_model": rule["raw_model"], "normalized_provider": rule["canonical_provider"], "normalized_model": rule["canonical_model"], "reason": rule["reason"]}
            value["provider"] = rule["canonical_provider"]
            value["_provider_identity_normalization"] = note
            notes.append(note)
    return value, notes


def normalize_information_request_item(item: Mapping[str, Any], contract_version: str) -> tuple[dict[str, Any], dict[str, Any] | None]:
    value, changes = dict(item), []
    if contract_version in (compat_r2.CONTRACT_VERSION, compat_r3.CONTRACT_VERSION, compat_r4.CONTRACT_VERSION, compat_r5.CONTRACT_VERSION) and value.get("affected_channel") == compat_r2.NORMALIZATION["input"]:
        value["affected_channel"] = compat_r2.NORMALIZATION["output"]
        changes.append({"field": "affected_channel", "original_value": "other", "normalized_value": "unknown", "reason": compat_r2.NORMALIZATION["reason"]})
    if contract_version in (compat_r3.CONTRACT_VERSION, compat_r4.CONTRACT_VERSION, compat_r5.CONTRACT_VERSION) and value.get("information_category") == compat_r3.NORMALIZATION["information_category"]["input"]:
        rule = compat_r3.NORMALIZATION["information_category"]
        value["information_category"] = rule["output"]; changes.append({"field": rule["field"], "original_value": rule["input"], "normalized_value": rule["output"], "reason": rule["reason"]})
    if contract_version in (compat_r4.CONTRACT_VERSION, compat_r5.CONTRACT_VERSION) and value.get("information_category") == compat_r4.NORMALIZATION["information_category_housing"]["input"]:
        rule = compat_r4.NORMALIZATION["information_category_housing"]
        value["information_category"] = rule["output"]; changes.append({"field": rule["field"], "original_value": rule["input"], "normalized_value": rule["output"], "reason": rule["reason"]})
    return value, {"normalizations": changes} if changes else None
