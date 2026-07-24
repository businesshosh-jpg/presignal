#!/usr/bin/env python3
"""Minimal explicit-input prospective v2 lineage for the P12 shadow study.

This sidecar reuses the archived v2 Attention and Information Request prompt
contracts and the existing authoritative provider bridge.  It intentionally
does not access worksheets, workbooks, or production state.  Callers supply a
complete session snapshot and cutoff-safe Pack inputs and persist returned
records only in the immutable study run.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Mapping

VALID_LABELS = {"PRIMARY_DRIVER", "SECONDARY_DRIVER", "WATCHLIST", "CONTEXT_ONLY", "IGNORE", "NO_SIGNAL"}
VALID_PRIORITIES = {"must_have", "useful", "optional", "low_value"}
VALID_CATEGORIES = {
    "treasury_yields", "fed_expectations", "dxy", "usdjpy_trend", "risk_sentiment", "equity_tone",
    "inflation_narrative", "labor_market_trend", "growth_context", "market_positioning",
    "upcoming_larger_events", "jpy_intervention_risk", "volatility", "historical_surprise_sensitivity",
    "event_consensus_detail", "other",
}
REQUEST_PROMPT_VERSION_V1 = "presignal_v21_information_request_prompt_v1"
REQUEST_PROMPT_VERSION = "presignal_v21_information_request_prompt_v2"
REQUEST_CATEGORY_ENUM_BLOCK = "\n".join(sorted(VALID_CATEGORIES))
VALID_CHANNELS = {
    "fed_path", "treasury_yields", "usd_direction", "jpy_direction", "risk_sentiment",
    "inflation_expectations", "labor_market", "growth_outlook", "market_positioning",
    "event_importance", "low_direct_market_impact", "unknown",
}
APPROVED_MODELS = {
    "Anthropic": "claude-haiku-4-5", "Gemini": "gemini-2.5-flash-lite", "OpenAI": "gpt-4o-mini-2024-07-18",
}
ATTENTION_INSTRUCTION = """You are classifying event attention for a PreSignal v2.0 shadow research layer.

Your task is not to forecast USDJPY direction, estimate pips, give trading advice, browse, or select an Event Episode. For each supplied event assign exactly one attention label and explain briefly. Return strict JSON only, without markdown, using exactly: object, session_id, provider, attention_items, session_attention_summary, status. Set object to session_attention_map and status to ok. Each attention_items object must use exactly: event_id, attention_label, attention_rank, attention_reason, expected_market_channel, driver_role, confidence. Allowed labels: PRIMARY_DRIVER, SECONDARY_DRIVER, WATCHLIST, CONTEXT_ONLY, IGNORE, NO_SIGNAL. Do not include any forecast, price, released actual, or Outcome field."""
REQUEST_INSTRUCTION_V1 = f"""You are identifying information requirements for a PreSignal v2.0 shadow research layer.

You are given a session, its events, and the same provider's Attention Map. Do not forecast USDJPY direction, estimate pips, give trading advice, browse, or create a Market-State Pack. Return strict JSON only, without markdown, using exactly: object, session_id, provider, information_items, session_information_summary, status. Set object to session_information_requirements and status to ok. The session_id must exactly equal the supplied session identity; the supplied Attention Map binds Attention lineage and the request envelope binds schema version. Each information_items object must use exactly: request_rank, requested_information, information_category, priority, reason, affected_channel, event_family_relevance, linked_event_ids, linked_attention_labels, available_now, suggested_source, expected_forecast_use, is_market_state_candidate. information_items must be a non-empty array and each requested_information must be actionable and non-empty.

For each information item, set information_category to exactly one of these machine values:
{REQUEST_CATEGORY_ENUM_BLOCK}

Do not create category names, use display labels or natural-language alternatives, leave information_category blank, or put multiple categories in one field. Use other only when no specific listed category directly describes the concrete request; do not use it to avoid categorization. Do not include any forecast, price, released actual, Outcome, evaluation, Pack A, or Pack E field."""
REQUEST_INSTRUCTION = f"""You are identifying information requirements for a PreSignal v2.0 shadow research layer.

You are given a pre-release session, its events, and the same provider's Attention Map. Generate only information requests that can be answered using information available or knowable before the forecast cutoff. The Event has not occurred for purposes of this task: treat its scheduled actual value and any market reaction as unavailable future information. Do not forecast USDJPY direction, estimate pips, give trading advice, browse, or create a Market-State Pack. Return strict JSON only, without markdown, using exactly: object, session_id, provider, information_items, session_information_summary, status. Set object to session_information_requirements and status to ok. The session_id must exactly equal the supplied session identity; the supplied Attention Map binds Attention lineage and the request envelope binds schema version. Each information_items object must use exactly: request_rank, requested_information, information_category, priority, reason, affected_channel, event_family_relevance, linked_event_ids, linked_attention_labels, available_now, suggested_source, expected_forecast_use, is_market_state_candidate. information_items must be a non-empty array and each requested_information must be actionable and non-empty.

For each information item, set information_category to exactly one of these machine values:
{REQUEST_CATEGORY_ENUM_BLOCK}

Do not create category names, use display labels or natural-language alternatives, leave information_category blank, or put multiple categories in one field. Use other only when no specific listed category directly describes the concrete request; do not use it to avoid categorization. Do not request the actual value of the upcoming Event; whether it beat, matched, or missed consensus; a surprise magnitude for the upcoming Event; any post-release market reaction; a realized price path; Outcome data; or evaluation results. Do not use released actual values, post-release evidence, Pack A, or Pack E fields.

Valid examples: event_consensus_detail — What are the current consensus estimate, forecast range, and most recent economist revisions for the upcoming Manufacturing PMI release? growth_context — How have recent regional manufacturing surveys and industrial indicators changed expectations for the upcoming PMI release? historical_surprise_sensitivity — How has USD/JPY historically reacted when comparable PMI releases differed materially from consensus? treasury_yields — What is the current pre-release Treasury-yield environment relevant to the expected USD reaction?

Invalid examples (all prohibited because they require Event Outcome or post-release evidence): What was the released Manufacturing PMI value? Did the Manufacturing PMI beat expectations? How did USD/JPY react after the PMI release? What was the realized 15-minute price path? Was the forecast direction correct?"""
FORBIDDEN_KEYS = {"outcome", "evaluation", "released_value", "actual", "realized", "reversal", "forecast_direction", "expected_move_pips"}


class MinimalProspectiveLineageError(RuntimeError):
    """An explicit-input prospective lineage invariant failed."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def utc(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def _short(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()[:20]


def _require(value: Any, code: str) -> Any:
    if value is None or value == "" or value == []:
        raise MinimalProspectiveLineageError(code)
    return value


def _reject_forbidden(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                raise MinimalProspectiveLineageError("FORBIDDEN_PROSPECTIVE_FIELD:" + path + "." + str(key))
            _reject_forbidden(nested, path + "." + str(key))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_forbidden(nested, path + "[" + str(index) + "]")


def validate_request_temporal_scope(requested_information: Any) -> str | None:
    """Return a narrow fail-closed code for outcome-dependent Request wording.

    Historical context remains permitted when the request explicitly marks the
    release or reaction as prior, previous, historical, past, or last-N.
    """
    text = " ".join(str(requested_information or "").lower().split())
    historical = any(marker in text for marker in ("historical", "previous", "prior ", "past ", "last "))
    if "realized" in text and ("path" in text or "minute" in text):
        return "REJECTED_PROMPT_PROHIBITED_REALIZED_PATH_REFERENCE"
    if any(marker in text for marker in ("forecast direction correct", "evaluation result", "was the forecast", "forecast accuracy")):
        return "REJECTED_PROMPT_PROHIBITED_EVALUATION_REFERENCE"
    if not historical and any(marker in text for marker in ("beat expectations", "beat consensus", "missed expectations", "missed consensus", "matched consensus", "surprise magnitude")):
        return "REJECTED_PROMPT_PROHIBITED_OUTCOME_REFERENCE"
    if not historical and any(marker in text for marker in ("post-release", "post release", "react after", "reaction after", "after this release", "after the pmi release")):
        return "REJECTED_PROMPT_PROHIBITED_POST_RELEASE_REFERENCE"
    if not historical and any(marker in text for marker in ("released actual", "released value", "actual value of the upcoming", "actual value for the upcoming", "what was the actual value", "upcoming actual")):
        return "REJECTED_PROMPT_PROHIBITED_RELEASED_ACTUAL_REFERENCE"
    return None


def _validate_identity(*, study_id: str, collection_run_id: str, session_snapshot: Mapping[str, Any], provider: str, model: str, information_cutoff_ts: str, stage_run_id: str) -> None:
    _require(study_id, "STUDY_ID_REQUIRED"); _require(collection_run_id, "COLLECTION_RUN_ID_REQUIRED")
    _require(session_snapshot.get("session_id"), "SESSION_ID_REQUIRED"); _require(stage_run_id, "STAGE_RUN_ID_REQUIRED")
    if APPROVED_MODELS.get(provider) != model:
        raise MinimalProspectiveLineageError("EXACT_PROVIDER_MODEL_REQUIRED")
    _require(information_cutoff_ts, "INFORMATION_CUTOFF_REQUIRED"); utc(information_cutoff_ts)
    _reject_forbidden(session_snapshot)


def _event_payload(member_rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in sorted((dict(row) for row in member_rows), key=lambda value: (int(value.get("member_order") or 999999), str(value.get("event_id") or ""))):
        _require(row.get("event_id"), "EVENT_ID_REQUIRED")
        _require(row.get("release_ts"), "EVENT_RELEASE_TS_REQUIRED")
        _reject_forbidden(row)
        rows.append({key: row.get(key, "") for key in ("event_id", "batch_id", "type", "indicator_name", "genre", "importance", "release_ts", "consensus_value", "prev_revision", "member_order")})
    _require(rows, "SESSION_MEMBERS_REQUIRED")
    return rows


def _prompt(instruction: str, payload: Mapping[str, Any]) -> dict[str, str]:
    return {"system": "You are a macroeconomic research model. Output strict JSON only, with no markdown or prose outside the JSON object.", "user": canonical_json(payload), "instruction": instruction, "cache_scaffold": ""}


def bridge_request(*, provider: str, model: str, prompt: Mapping[str, str], collection_run_id: str, session_id: str, stage: str, generation_settings: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Build the existing bridge payload without dispatching it."""
    request = {
        "provider": provider, "model": model, "prompt": dict(prompt), "authoritative_run_id": collection_run_id,
        "forecast_identity": "P12_LINEAGE_" + _short({"run": collection_run_id, "session": session_id, "stage": stage, "provider": provider, "model": model}),
        "arm": "LINEAGE_" + stage, "session_id": session_id, "hard_timeout_seconds": 180,
        "request_schema_version": "authoritative_historical_replay_bridge_v1",
    }
    if generation_settings:
        if "max_output_tokens" in generation_settings:
            request["max_output_tokens"] = generation_settings["max_output_tokens"]
        if generation_settings.get("preserve_raw_before_parse") is True:
            request["preserve_raw_before_parse"] = True
    return request


def _raw_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, Mapping):
        return dict(raw)
    if isinstance(raw, str):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise MinimalProspectiveLineageError("PROVIDER_RAW_JSON_INVALID") from exc
        if isinstance(value, Mapping):
            return dict(value)
    raise MinimalProspectiveLineageError("PROVIDER_RAW_OBJECT_REQUIRED")


def _stage_timestamp(response: Mapping[str, Any], fallback: str) -> str:
    value = str(response.get("completed_timestamp") or response.get("completed_ts") or fallback)
    utc(value)
    return value


def build_prospective_attention(*, study_id: str, collection_run_id: str, session_snapshot: Mapping[str, Any], member_rows: Iterable[Mapping[str, Any]], provider: str, model: str, information_cutoff_ts: str, attention_run_id: str, stage_generated_ts: str, dispatcher: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None, raw_parser: Callable[[Any], Mapping[str, Any]] | None = None, instruction_override: str | None = None, generation_settings: Mapping[str, Any] | None = None, raw_response_persistor: Callable[[Mapping[str, Any]], None] | None = None) -> dict[str, Any]:
    """Build one explicit prospective Attention call or parse its returned output."""
    _validate_identity(study_id=study_id, collection_run_id=collection_run_id, session_snapshot=session_snapshot, provider=provider, model=model, information_cutoff_ts=information_cutoff_ts, stage_run_id=attention_run_id)
    if utc(stage_generated_ts) > utc(information_cutoff_ts): raise MinimalProspectiveLineageError("ATTENTION_AFTER_INFORMATION_CUTOFF")
    members = _event_payload(member_rows); session_id = str(session_snapshot["session_id"])
    payload = {"object": "presignal_v2_market_session_attention_task", "schema_version": "v0", "session": {key: session_snapshot.get(key, "") for key in ("session_id", "country", "session_window_name", "session_start_ts", "session_end_ts")}, "events": members, "task": "Classify which events in this market session matter for USDJPY reaction. Do not forecast USDJPY direction or pips."}
    prompt = _prompt(instruction_override or ATTENTION_INSTRUCTION, payload); request = bridge_request(provider=provider, model=model, prompt=prompt, collection_run_id=collection_run_id, session_id=session_id, stage="ATTENTION", generation_settings=generation_settings)
    base = {"attention_run_id": attention_run_id, "session_id": session_id, "provider": provider, "model": model, "information_cutoff_ts": information_cutoff_ts, "generated_ts": stage_generated_ts, "request_fingerprint": sha256(request), "source": "existing_v2_attention_prompt_schema", "raw_output": None}
    if dispatcher is None:
        return {"status": "DRY_RUN", "request": request, "prompt": prompt, "rows": [], "metadata": base, "provider_calls": 0}
    response = dict(dispatcher(request)); raw = response.get("raw_output"); raw_preserved = response.get("raw_output_original", raw)
    if raw_response_persistor is not None: raw_response_persistor(response)
    if response.get("status") != "ok":
        return {"status": "provider_contract_error", "request": request, "response": response, "rows": [{**base, "status": "provider_contract_error", "error_message": response.get("error") or response.get("status"), "raw_output": raw_preserved}], "provider_calls": 1}
    try:
        parsed = dict((raw_parser or _raw_object)(raw))
    except Exception as exc:
        return {"status": "provider_contract_error", "request": request, "response": response, "rows": [{**base, "status": "provider_contract_error", "error_message": str(exc), "raw_output": raw_preserved}], "provider_calls": 1}
    identity_normalization = parsed.pop("_provider_identity_normalization", None)
    if parsed.get("object") != "session_attention_map" or parsed.get("session_id") != session_id or parsed.get("provider") != provider or parsed.get("status") != "ok":
        return {"status": "provider_contract_error", "request": request, "response": response, "rows": [{**base, "status": "provider_contract_error", "error_message": "attention_contract_identity", "raw_output": raw_preserved}], "provider_calls": 1}
    item_by_event = {str(item.get("event_id")): item for item in parsed.get("attention_items", []) if isinstance(item, Mapping) and str(item.get("event_id"))}
    rows = []
    for member in members:
        item = item_by_event.get(str(member["event_id"]))
        if item is None:
            rows.append({**base, **member, "status": "provider_omitted_event", "omission_reason": "event_not_returned_by_provider", "raw_output": raw_preserved})
            continue
        label = str(item.get("attention_label") or "")
        if label not in VALID_LABELS:
            rows.append({**base, **member, "status": "provider_contract_error", "error_message": "invalid_attention_label", "raw_output": raw_preserved})
            continue
        rows.append({**base, **member, "status": "parsed", "attention_label": label, "attention_rank": item.get("attention_rank"), "attention_reason": str(item.get("attention_reason") or "")[:160], "expected_market_channel": str(item.get("expected_market_channel") or "unknown"), "driver_role": str(item.get("driver_role") or ""), "confidence": item.get("confidence"), "raw_output": raw_preserved, "response_fingerprint": sha256(response), "provider_identity_normalization": identity_normalization})
    return {"status": "parsed", "request": request, "response": response, "rows": rows, "provider_identity_normalization": identity_normalization, "provider_calls": 1}


def build_prospective_requests(*, study_id: str, collection_run_id: str, session_snapshot: Mapping[str, Any], member_rows: Iterable[Mapping[str, Any]], attention_result: Mapping[str, Any], provider: str, model: str, information_cutoff_ts: str, request_run_id: str, stage_generated_ts: str, dispatcher: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None, raw_parser: Callable[[Any], Mapping[str, Any]] | None = None, instruction_override: str | None = None, request_normalizer: Callable[[Mapping[str, Any]], tuple[dict[str, Any], Mapping[str, Any] | None]] | None = None, raw_response_persistor: Callable[[Mapping[str, Any]], None] | None = None, include_attention_identity: bool = True) -> dict[str, Any]:
    """Build one Request call from the same provider's prospective Attention."""
    _validate_identity(study_id=study_id, collection_run_id=collection_run_id, session_snapshot=session_snapshot, provider=provider, model=model, information_cutoff_ts=information_cutoff_ts, stage_run_id=request_run_id)
    if utc(stage_generated_ts) > utc(information_cutoff_ts): raise MinimalProspectiveLineageError("REQUEST_AFTER_INFORMATION_CUTOFF")
    rows = list(attention_result.get("rows") or []); attention_run_id = _require((attention_result.get("metadata") or {}).get("attention_run_id") or (rows[0].get("attention_run_id") if rows else None), "ATTENTION_RUN_ID_REQUIRED")
    if any(row.get("session_id") != session_snapshot.get("session_id") or row.get("provider") != provider or row.get("model") != model for row in rows): raise MinimalProspectiveLineageError("REQUEST_ATTENTION_IDENTITY_MISMATCH")
    members = _event_payload(member_rows); session_id = str(session_snapshot["session_id"])
    payload = {"object": "presignal_v2_session_information_request_task", "schema_version": "v0", "session": {key: session_snapshot.get(key, "") for key in ("session_id", "country", "session_window_name", "session_start_ts", "session_end_ts")}, "events": members, "provider_attention_map": [{key: row.get(key, "") for key in ("event_id", "attention_label", "attention_rank", "attention_reason", "expected_market_channel", "driver_role")} for row in rows], "task": "List information needed for a later USDJPY forecast. Do not forecast direction or pips."}
    if include_attention_identity:
        payload["attention_identity"] = attention_run_id
    prompt = _prompt(instruction_override or REQUEST_INSTRUCTION, payload); request = bridge_request(provider=provider, model=model, prompt=prompt, collection_run_id=collection_run_id, session_id=session_id, stage="REQUESTS")
    base = {"request_run_id": request_run_id, "attention_run_id": attention_run_id, "session_id": session_id, "provider": provider, "model": model, "information_cutoff_ts": information_cutoff_ts, "generated_ts": stage_generated_ts, "request_fingerprint": sha256(request), "source": "existing_v2_information_request_prompt_schema", "raw_output": None}
    if dispatcher is None: return {"status": "DRY_RUN", "request": request, "prompt": prompt, "rows": [], "metadata": base, "provider_calls": 0}
    response = dict(dispatcher(request)); raw = response.get("raw_output"); raw_preserved = response.get("raw_output_original", raw)
    if raw_response_persistor is not None: raw_response_persistor(response)
    if response.get("status") != "ok": return {"status": "provider_contract_error", "request": request, "response": response, "rows": [{**base, "status": "provider_contract_error", "error_message": response.get("error") or response.get("status"), "raw_output": raw_preserved}], "provider_calls": 1}
    try:
        parsed = dict((raw_parser or _raw_object)(raw))
    except Exception as exc:
        return {"status": "provider_contract_error", "request": request, "response": response, "rows": [{**base, "status": "provider_contract_error", "error_message": str(exc), "raw_output": raw_preserved}], "provider_calls": 1}
    if parsed.get("object") != "session_information_requirements" or parsed.get("session_id") != session_id or parsed.get("provider") != provider or parsed.get("status") != "ok": return {"status": "provider_contract_error", "request": request, "response": response, "rows": [{**base, "status": "provider_contract_error", "error_message": "request_contract_identity", "raw_output": raw_preserved}], "provider_calls": 1}
    output = []
    for index, item in enumerate(parsed.get("information_items", []), 1):
        if not isinstance(item, Mapping) or not item.get("requested_information"): return {"status": "provider_contract_error", "request": request, "response": response, "rows": [{**base, "status": "provider_contract_error", "error_message": "invalid_information_item", "raw_output": raw_preserved}], "provider_calls": 1}
        normalized_item, normalization = request_normalizer(item) if request_normalizer else (dict(item), None)
        category = str(normalized_item.get("information_category") or "other"); priority = str(normalized_item.get("priority") or "useful"); channel = str(normalized_item.get("affected_channel") or "unknown")
        if category not in VALID_CATEGORIES or priority not in VALID_PRIORITIES or channel not in VALID_CHANNELS: return {"status": "provider_contract_error", "request": request, "response": response, "rows": [{**base, "status": "provider_contract_error", "error_message": "invalid_request_enum", "raw_output": raw_preserved}], "provider_calls": 1}
        requested = str(normalized_item["requested_information"])
        temporal_error = validate_request_temporal_scope(requested)
        if temporal_error:
            return {"status": "provider_contract_error", "request": request, "response": response, "rows": [{**base, "status": "provider_contract_error", "error_message": temporal_error, "raw_output": raw_preserved}], "provider_calls": 1}
        output.append({**base, "status": "parsed", "request_identity": "PINFO_" + _short({"run": request_run_id, "rank": index, "requested": requested}), "request_rank": normalized_item.get("request_rank") or index, "requested_information": requested, "information_category": category, "original_information_category": item.get("information_category"), "priority": priority, "reason": str(normalized_item.get("reason") or "")[:160], "affected_channel": channel, "original_affected_channel": item.get("affected_channel"), "normalization": normalization, "event_family_relevance": normalized_item.get("event_family_relevance"), "linked_event_ids": normalized_item.get("linked_event_ids"), "linked_attention_labels": normalized_item.get("linked_attention_labels"), "available_now": normalized_item.get("available_now"), "suggested_source": normalized_item.get("suggested_source"), "expected_forecast_use": normalized_item.get("expected_forecast_use"), "is_market_state_candidate": normalized_item.get("is_market_state_candidate"), "raw_output": raw_preserved, "response_fingerprint": sha256(response)})
    return {"status": "parsed", "request": request, "response": response, "rows": output, "provider_calls": 1}


def build_prospective_packs(*, study_id: str, collection_run_id: str, session_id: str, information_cutoff_ts: str, pack_freeze_id: str, requests_by_provider: Mapping[str, Iterable[Mapping[str, Any]]], shared_pack_items: Iterable[Mapping[str, Any]], pack_generated_ts: str) -> dict[str, Any]:
    """Freeze provider Request references for Pack A and one explicit shared Pack E."""
    _require(study_id, "STUDY_ID_REQUIRED"); _require(collection_run_id, "COLLECTION_RUN_ID_REQUIRED"); _require(session_id, "SESSION_ID_REQUIRED"); _require(pack_freeze_id, "PACK_FREEZE_ID_REQUIRED")
    if utc(pack_generated_ts) > utc(information_cutoff_ts): raise MinimalProspectiveLineageError("PACK_AFTER_INFORMATION_CUTOFF")
    shared = [dict(item) for item in shared_pack_items]
    _require(shared, "PACK_E_EMPTY")
    for item in shared:
        _reject_forbidden(item)
        timestamp = _require(item.get("source_timestamp"), "PACK_ITEM_TIMESTAMP_REQUIRED")
        if utc(str(timestamp)) > utc(information_cutoff_ts): raise MinimalProspectiveLineageError("POST_CUTOFF_PACK_ITEM")
    pack_e = {"pack_id": "PACK_E_SHARED_" + _short({"freeze": pack_freeze_id, "items": shared}), "pack_freeze_id": pack_freeze_id, "session_id": session_id, "information_cutoff_ts": information_cutoff_ts, "pack_generated_ts": pack_generated_ts, "items": sorted(shared, key=canonical_json), "source_request_run_ids": sorted({str(row.get("request_run_id")) for rows in requests_by_provider.values() for row in rows if row.get("request_run_id")}), "source_kind": "prospective_explicit_shared_pack"}
    pack_e["pack_fingerprint"] = sha256(pack_e)
    pack_a_by_provider = {}
    for provider, requests in sorted(requests_by_provider.items()):
        rows = [dict(row) for row in requests if row.get("status") == "parsed"]
        _require(rows, "PACK_A_EMPTY:" + provider)
        if any(row.get("session_id") != session_id or row.get("information_cutoff_ts") != information_cutoff_ts for row in rows): raise MinimalProspectiveLineageError("PACK_A_LINEAGE_MISMATCH")
        pack_a_by_provider[provider] = {"pack_id": "PACK_A_REQUESTS_" + _short({"freeze": pack_freeze_id, "provider": provider, "requests": rows}), "pack_freeze_id": pack_freeze_id, "session_id": session_id, "information_cutoff_ts": information_cutoff_ts, "information_requests": rows, "shared_market_state_pack": None, "pack_fingerprint": sha256({"provider": provider, "request_identities": [row["request_identity"] for row in rows]}), "source_kind": "prospective_provider_requests"}
    return {"status": "FROZEN", "pack_e": pack_e, "pack_a_by_provider": pack_a_by_provider, "acquisition_calls": 0, "market_data_calls": 0, "production_writes": 0}
