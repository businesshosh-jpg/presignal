#!/usr/bin/env python3
"""Capture leakage-safe matched Pack A versus frozen true Pack E forecasts.

This is a shadow-only capture runner.  It deliberately does not import an
outcome ledger, canonical outcomes, or evaluation code.  Every provider call
is stateless and produces a frozen forecast record for a single arm only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_market_sessions_shadow_v0 import (
    DIAGNOSTICS_SPREADSHEET_ID,
    MAIN_SPREADSHEET_ID,
    _norm,
    _sheet_to_rows,
)
from automation.build_pack_exposure_pilot_run_v0 import (
    PROVIDER_ORDER,
    _call_live_provider_raw,
    _parse_provider_json,
)
from automation.build_pack_exposure_prompt_validation_v0 import (
    _assemble_prompt_text,
    _event_index,
    _get_sheet_titles,
    _group_prompt_rows,
    _guardrail_payload,
    _latest_run_id,
    _member_index,
    _schema_payload,
)
from automation.build_session_forecasts_v0 import _normalize_confidence, _normalize_forecast_direction
from automation.build_session_information_requests_v0 import _iso_now
from automation.google_clients import build_script_service, build_sheets_service, default_script_id, load_credentials
from automation.true_shared_pack_e_renderer_v0 import (
    FrozenPackEError,
    content_fingerprint,
    load_frozen_true_shared_pack_e,
    render_frozen_true_shared_pack_e_context,
)


FREEZE_MANIFEST = ROOT / "outputs/phase9_true_pack_e_validation/9-TRUE-SHARED-PACK-E-VALIDATION_20260714T081534Z/pack_e_freeze_manifest.json"
FIXTURE_VALIDATION = FREEZE_MANIFEST.parent / "forecast_input_fixture_validation.json"
OUTPUT_ROOT = ROOT / "outputs/phase9_pack_a_vs_frozen_pack_e_forecasts"

VALIDATION_RUN_ID = "9-TRUE-SHARED-PACK-E-VALIDATION_20260714T081534Z"
EXPECTED_PACK_FINGERPRINT = "976271f7cba9689f91098e2a6b7e2038e8c5df004012dc57c733e0addd1dc15e"
EXPECTED_RENDERED_FINGERPRINT = "28b20d670daa7a69dbae08cc064bb516a6996a8374bd80c5d932f60fe34e8248"
PROTOCOL_VERSION = "phase9_pack_a_vs_frozen_true_pack_e_capture_v0"
PROMPT_WRAPPER_VERSION = "phase9_capture_identity_and_json_serialization_r1"
FORECAST_TARGET = "USDJPY_MARKET_SESSION_REACTION"
PACK_A_LEVEL = "A"
PACK_E_LEVEL = "E"
PACK_A_SELECTION = "NO_PACK"
OUTPUT_SCHEMA_VERSION = "Pack_Exposure_Output_Schema"

PROMPT_DESIGN_SHEET = "Pack_Exposure_Prompt_Design"
PROMPT_SUMMARY_SHEET = "Pack_Exposure_Prompt_Design_Summary"
OUTPUT_SCHEMA_SHEET = "Pack_Exposure_Output_Schema"
GUARDRAILS_SHEET = "Pack_Exposure_Prompt_Guardrails"
SESSIONS_SHEET = "Market_Sessions"
MEMBERS_SHEET = "Market_Session_Members"
EVENT_SHEET = "Event"

REQUIRED_RESPONSE_FIELDS = {
    "session_id",
    "provider",
    "model",
    "pack_level",
    "forecast_direction",
    "primary_driver_summary",
    "causal_chain",
    "no_signal_flag",
    "status",
}
FACTUAL_PACK_STATUSES = {
    # These are the artifact's canonical statuses, not the report-only labels
    # (for example, SUPPLIED_DETERMINISTIC) used by the fulfillment audit.
    "DETERMINISTIC",
    "COMPUTED",
    "CALENDAR_DERIVED",
    "AI_RETRIEVED_PROVISIONAL",
    "AI_RESEARCH_SUMMARY",
}
NON_FACT_PACK_STATUSES = {"UNAVAILABLE", "INTERPRETIVE_NOT_SUPPLIED", "POLICY_REJECTED"}
FORBIDDEN_KEY_FRAGMENTS = (
    "canonical_outcome",
    "outcome_id",
    "realized_",
    "start_price",
    "end_price",
    "market_price",
    "realized_pips",
    "evaluation_label",
    "success_mapping",
    "accuracy",
    "forecast_success",
    "released_value",
    "released_ts",
    "outcome_link",
)
RETRYABLE_RESPONSE_STATUSES = {"execution_error", "error", "timeout", "transport_error"}


class CaptureBlocked(RuntimeError):
    """Raised when an invariant blocks capture before a provider call."""


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _utc_parse(value: Any) -> Optional[datetime]:
    text = _norm(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _bool(value: Any) -> bool:
    return _norm(value).upper() in {"TRUE", "1", "YES"}


def _run_id(prefix: str) -> str:
    return prefix + "_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(_canonical(dict(row)) + "\n")


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def _safe_read(service, spreadsheet_id: str, sheet_titles: Set[str], sheet_name: str) -> List[Dict[str, Any]]:
    if sheet_name not in sheet_titles:
        return []
    return _sheet_to_rows(service, spreadsheet_id, sheet_name)


def _filter_run(rows: Sequence[Mapping[str, Any]], key: str, run_id: str) -> List[Dict[str, Any]]:
    return [dict(row) for row in rows if not run_id or _norm(row.get(key)) == run_id]


def _load_prompt_configuration(service) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], str]:
    titles = _get_sheet_titles(service, DIAGNOSTICS_SPREADSHEET_ID)
    summary_rows = _safe_read(service, DIAGNOSTICS_SPREADSHEET_ID, titles, PROMPT_SUMMARY_SHEET)
    prompt_run_id = _latest_run_id(summary_rows, "prompt_design_run_id")
    prompt_rows = _filter_run(_safe_read(service, DIAGNOSTICS_SPREADSHEET_ID, titles, PROMPT_DESIGN_SHEET), "prompt_design_run_id", prompt_run_id)
    schema_rows = _filter_run(_safe_read(service, DIAGNOSTICS_SPREADSHEET_ID, titles, OUTPUT_SCHEMA_SHEET), "prompt_design_run_id", prompt_run_id)
    guardrail_rows = _filter_run(_safe_read(service, DIAGNOSTICS_SPREADSHEET_ID, titles, GUARDRAILS_SHEET), "prompt_design_run_id", prompt_run_id)
    grouped = _group_prompt_rows(prompt_rows, prompt_run_id)
    config: Dict[str, Dict[str, Any]] = {}
    for provider in PROVIDER_ORDER:
        design_a = grouped.get((PACK_A_LEVEL, provider))
        design_e = grouped.get((PACK_E_LEVEL, provider))
        if not design_a or not design_e:
            config[provider] = {"configured": False, "reason": "MISSING_FROZEN_PROMPT_DESIGN"}
            continue
        model_a = _norm(design_a.get("model"))
        model_e = _norm(design_e.get("model"))
        if not model_a or model_a != model_e:
            config[provider] = {"configured": False, "reason": "PACK_ARM_MODEL_CONFIGURATION_MISMATCH"}
            continue
        if _norm(design_a.get("system_prompt_template")) != _norm(design_e.get("system_prompt_template")) or _norm(design_a.get("user_prompt_template")) != _norm(design_e.get("user_prompt_template")):
            config[provider] = {"configured": False, "reason": "PACK_ARM_PROMPT_TEMPLATE_MISMATCH"}
            continue
        config[provider] = {
            "configured": True,
            "provider": provider,
            "model": model_a,
            "prompt_version": prompt_run_id,
            "design_row": dict(design_a),
            "temperature": _norm(design_a.get("temperature")),
            "reasoning": _norm(design_a.get("reasoning_effort")) or _norm(design_a.get("reasoning")),
            "max_tokens": _norm(design_a.get("max_tokens")),
            "output_schema_version": OUTPUT_SCHEMA_VERSION,
            "forecast_runner_version": PROTOCOL_VERSION,
        }
    return config, schema_rows, guardrail_rows, prompt_run_id


def _build_event_context(session_id: str, session_row: Mapping[str, Any], members: Sequence[Mapping[str, Any]], events: Mapping[str, Mapping[str, Any]]) -> Tuple[Dict[str, Any], List[str]]:
    rows = sorted(members, key=lambda row: (_norm(row.get("release_ts")), _norm(row.get("member_order")), _norm(row.get("event_id"))))
    if not rows:
        return {}, ["SESSION_MEMBERS_MISSING"]
    payload_events: List[Dict[str, Any]] = []
    notes: List[str] = []
    for member in rows:
        event_id = _norm(member.get("event_id"))
        event = events.get(event_id, {})
        release_ts = _norm(member.get("release_ts")) or _norm(event.get("release_ts"))
        if not event_id or not release_ts:
            notes.append("MEMBER_EVENT_IDENTITY_OR_RELEASE_MISSING")
            continue
        payload_events.append({
            "event_id": event_id,
            "indicator_name": _norm(member.get("indicator_name")) or _norm(event.get("indicator_name")),
            "release_ts": release_ts,
            "importance": _norm(member.get("importance")) or _norm(event.get("importance")),
            "consensus_value": _norm(member.get("consensus_value")) or _norm(event.get("consensus_value")),
            "previous_value": _norm(member.get("prev_revision")) or _norm(event.get("prev_revision")),
            "revision_info_if_available": _norm(member.get("prev_revision")) or _norm(event.get("prev_revision")),
        })
    if len(payload_events) != len(rows):
        return {}, sorted(set(notes))
    cutoff = _norm(session_row.get("primary_release_ts")) or _norm(session_row.get("session_start_ts"))
    return {
        "session": {
            "session_id": session_id,
            "session_date": _norm(session_row.get("session_date")),
            "country": _norm(session_row.get("country")),
            "session_window_name": _norm(session_row.get("session_window_name")),
            "session_start_ts": cutoff,
            "session_end_ts": cutoff,
            "member_event_count": len(payload_events),
        },
        "events": payload_events,
    }, []


def _validate_pack_session(frozen_pack: Mapping[str, Any], session_id: str, context: Mapping[str, Any]) -> List[str]:
    errors: List[str] = []
    cutoff = None
    for entry in context.get("assigned_market_state_context", []):
        row_cutoff = _utc_parse(entry.get("as_of_timestamp")) or _utc_parse(entry.get("source_timestamp"))
        if row_cutoff:
            cutoff = max(cutoff, row_cutoff) if cutoff else row_cutoff
    # The manifest validates source-bundle lineage; this check proves values are usable at the session cutoff.
    rows = [row for row in frozen_pack.get("pack_rows", []) if _norm(row.get("session_id")) == session_id]
    session_cutoff = None
    for row in rows:
        candidate = _utc_parse(row.get("forecast_timestamp"))
        if candidate:
            session_cutoff = candidate
            break
    if not session_cutoff:
        return ["PACK_E_FORECAST_CUTOFF_MISSING"]
    for row in rows:
        status = _norm(row.get("status"))
        value = _norm(row.get("value"))
        if status in FACTUAL_PACK_STATUSES:
            if not _bool(row.get("backtest_safe")) or not _bool(row.get("data_available_flag")):
                errors.append("PACK_E_FACTUAL_ITEM_NOT_TIME_SAFE:" + _norm(row.get("item_key")))
            source_ts = _utc_parse(row.get("source_timestamp"))
            as_of_ts = _utc_parse(row.get("as_of_timestamp"))
            if source_ts and source_ts > session_cutoff:
                errors.append("PACK_E_SOURCE_POST_CUTOFF:" + _norm(row.get("item_key")))
            if as_of_ts and as_of_ts > session_cutoff:
                errors.append("PACK_E_ASOF_POST_CUTOFF:" + _norm(row.get("item_key")))
            if not value:
                errors.append("PACK_E_FACTUAL_VALUE_MISSING:" + _norm(row.get("item_key")))
        elif status in NON_FACT_PACK_STATUSES:
            if value:
                errors.append("PACK_E_NONFACT_HAS_VALUE:" + _norm(row.get("item_key")))
        else:
            errors.append("PACK_E_UNKNOWN_STATUS:" + _norm(row.get("item_key")))
    return sorted(set(errors))


def _pack_a_context() -> Dict[str, Any]:
    return {
        "pack_arm": PACK_A_LEVEL,
        "pack_selected": PACK_A_SELECTION,
        "pack_e_exposure": False,
        "assigned_market_state_context": [],
        "instruction": "No Market-State Pack is supplied.",
    }


def _pack_e_context(rendered: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "pack_arm": PACK_E_LEVEL,
        "pack_selected": _norm(rendered.get("true_shared_pack_e", {}).get("pack_version")),
        "pack_e_exposure": True,
        **dict(rendered),
    }


def _prompt_for_arm(design_row: Mapping[str, Any], event_context: Mapping[str, Any], exposure: Mapping[str, Any], schema_payload: Sequence[Mapping[str, Any]], guardrails: Sequence[Mapping[str, Any]], execution_identity: Mapping[str, str]) -> Tuple[Dict[str, str], str, str]:
    core_text, full_text = _assemble_prompt_text(dict(design_row), dict(event_context), dict(exposure), list(schema_payload), list(guardrails))
    # The frozen schema requires self-identification, but the original prompt
    # template did not provide those immutable values.  This common wrapper is
    # identical for A/E and contains no Market-State Pack content.
    identity_text = _canonical(dict(execution_identity))
    serialization_text = "\n\n".join([
        "IMMUTABLE EXECUTION IDENTITY",
        identity_text,
        "JSON SERIALIZATION REQUIREMENTS",
        "Echo session_id, provider, and model exactly from the immutable execution identity. "
        "Set pack_level exactly to the pack_arm in the assigned Market-State Context. "
        "Return one complete JSON object only, without markdown or code fences. "
        "Keep every text field concise (300 characters or fewer) so the complete required schema is returned.",
    ])
    prompt = {
        "system": _norm(design_row.get("system_prompt_template")),
        "user": full_text + "\n\n" + serialization_text,
        "instruction": _norm(design_row.get("user_prompt_template")),
        "cache_scaffold": "",
    }
    return prompt, _fingerprint(prompt), core_text


def _walk_forbidden(value: Any, path: str = "") -> List[str]:
    found: List[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = _norm(key).lower()
            child_path = path + "." + key_text if path else key_text
            if any(fragment in key_text for fragment in FORBIDDEN_KEY_FRAGMENTS):
                found.append(child_path)
            found.extend(_walk_forbidden(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_walk_forbidden(child, f"{path}[{index}]"))
    return found


def _validate_prompt(prompt: Mapping[str, Any], exposure: Mapping[str, Any], expected_arm: str) -> List[str]:
    errors = _walk_forbidden(prompt)
    rendered_text = _canonical(prompt).lower()
    for fragment in FORBIDDEN_KEY_FRAGMENTS:
        # Structured input keys are serialized into the provider prompt.  This
        # catches a prohibited field even if it is nested in a JSON string.
        if f'"{fragment}' in rendered_text:
            errors.append("FORBIDDEN_FIELD_IN_RENDERED_PROMPT:" + fragment)
    entries = exposure.get("assigned_market_state_context", [])
    if expected_arm == PACK_A_LEVEL:
        if entries or exposure.get("pack_e_exposure") or exposure.get("pack_selected") != PACK_A_SELECTION:
            errors.append("PACK_A_EXPOSED_TO_MARKET_STATE_PACK")
        # Pack E names/fingerprints may only appear in the absence of Pack A.
        if "true_shared_pack_e" in _canonical(prompt).lower() or EXPECTED_PACK_FINGERPRINT in _canonical(prompt):
            errors.append("PACK_A_CONTAINS_FROZEN_PACK_E_REFERENCE")
    else:
        metadata = exposure.get("true_shared_pack_e", {})
        if _norm(metadata.get("pack_fingerprint")) != EXPECTED_PACK_FINGERPRINT:
            errors.append("PACK_E_FINGERPRINT_MISMATCH_IN_PROMPT")
        if not entries:
            errors.append("PACK_E_CONTEXT_EMPTY")
    return sorted(set(errors))


def _prompt_without_exposure(prompt: Mapping[str, Any]) -> str:
    # The assembled prompt serializes one JSON context.  Normalize by replacing that context with a neutral sentinel.
    text = _norm(prompt.get("user"))
    marker = "ASSIGNED MARKET-STATE CONTEXT\n"
    following = "\n\nREQUIRED JSON OUTPUT SCHEMA"
    if marker not in text or following not in text:
        return "PROMPT_CONTEXT_BOUNDARIES_MISSING"
    before, remainder = text.split(marker, 1)
    _, after = remainder.split(following, 1)
    return before + marker + "<PACK_EXPOSURE_REDACTED>" + following + after


def _experimental_identity(session_id: str, provider: str, model: str, prompt_version: str, cutoff: str, arm: str, pack_version: str, pack_fingerprint: str) -> str:
    return _fingerprint({
        "session_id": session_id,
        "provider": provider,
        "model": model,
        "prompt_version": prompt_version,
        "forecast_target": FORECAST_TARGET,
        "forecast_cutoff": cutoff,
        "experimental_protocol_version": PROTOCOL_VERSION,
        "pack_arm": arm,
        "pack_version": pack_version,
        "pack_fingerprint": pack_fingerprint,
    })


def _existing_successes() -> Dict[str, Dict[str, Any]]:
    existing: Dict[str, Dict[str, Any]] = {}
    for path in OUTPUT_ROOT.glob("*/pack_a_forecasts.jsonl"):
        for row in _read_jsonl(path):
            if _norm(row.get("status")) == "CAPTURED" and _norm(row.get("experimental_identity")):
                existing[_norm(row["experimental_identity"])] = row
    for path in OUTPUT_ROOT.glob("*/frozen_pack_e_forecasts.jsonl"):
        for row in _read_jsonl(path):
            if _norm(row.get("status")) == "CAPTURED" and _norm(row.get("experimental_identity")):
                existing[_norm(row["experimental_identity"])] = row
    return existing


def _response_validation(raw: str, session_id: str, provider: str, model: str, arm: str, schema_rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    parsed_info = _parse_provider_json(raw, session_id, provider, arm, list(schema_rows))
    parsed = parsed_info.get("parsed", {}) if isinstance(parsed_info.get("parsed"), dict) else {}
    errors: List[str] = []
    if not parsed_info.get("parse_success") or not parsed_info.get("validation_success"):
        errors.append(_norm(parsed_info.get("parse_error")) or "OUTPUT_SCHEMA_FAILED")
    missing = sorted(field for field in REQUIRED_RESPONSE_FIELDS if field not in parsed or _norm(parsed.get(field)) == "")
    errors.extend("missing_required_field:" + field for field in missing)
    if _norm(parsed.get("session_id")) != session_id:
        errors.append("SESSION_SELF_IDENTITY_MISMATCH")
    if _norm(parsed.get("provider")) != provider:
        errors.append("PROVIDER_SELF_IDENTITY_MISMATCH")
    if _norm(parsed.get("model")) != model:
        errors.append("MODEL_SELF_IDENTITY_MISMATCH")
    if _norm(parsed.get("pack_level")) != arm:
        errors.append("PACK_ARM_SELF_IDENTITY_MISMATCH")
    direction, invalid_direction = _normalize_forecast_direction(parsed.get("forecast_direction"))
    if invalid_direction:
        errors.append("FORECAST_DIRECTION_INVALID")
    confidence, invalid_confidence = _normalize_confidence(parsed.get("forecast_confidence"))
    if invalid_confidence:
        errors.append("FORECAST_CONFIDENCE_INVALID")
    no_signal = _norm(parsed.get("no_signal_flag")).upper()
    if no_signal not in {"TRUE", "FALSE"}:
        errors.append("NO_SIGNAL_FLAG_INVALID")
    if no_signal == "TRUE" and not _norm(parsed.get("no_signal_reason")):
        errors.append("NO_SIGNAL_REASON_REQUIRED")
    lower_raw = raw.lower()
    if any(term in lower_raw for term in ("canonical outcome", "realized pips", "outcome ledger", "success mapping")):
        errors.append("UNSUPPORTED_OUTCOME_REFERENCE_IN_RESPONSE")
    return {
        "ok": not errors,
        "parsed": parsed,
        "errors": sorted(set(errors)),
        "forecast_direction": direction,
        "forecast_confidence": confidence,
        "no_signal_flag": no_signal,
        "parser_notes": _norm(parsed_info.get("notes")),
    }


def _fixture_dry_run(schema_rows: Sequence[Mapping[str, Any]], provider_config: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    provider = "OpenAI"
    model = _norm(provider_config.get(provider, {}).get("model")) or "fixture-model"
    fixture = {
        "session_id": "FIXTURE|2024-01-01|TEST",
        "provider": provider,
        "model": model,
        "pack_level": "A",
        "forecast_direction": "flat",
        "forecast_confidence": 50,
        "primary_driver_summary": "Fixture only.",
        "causal_chain": "Fixture only.",
        "no_signal_flag": "FALSE",
        "no_signal_reason": "",
        "status": "ok",
    }
    result = _response_validation(json.dumps(fixture), fixture["session_id"], provider, model, "A", schema_rows)
    return {"fixture_output": fixture, "validation_pass": result["ok"], "errors": result["errors"], "scientific_evidence": False}


def _capture_arm(script_service, script_id: str, provider: str, config: Mapping[str, Any], arm: str, prompt: Mapping[str, str], session_id: str, cutoff: str, schema_rows: Sequence[Mapping[str, Any],], exposure: Mapping[str, Any], existing: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    model = _norm(config.get("model"))
    pack_version = PACK_A_SELECTION if arm == PACK_A_LEVEL else _norm(exposure.get("pack_selected"))
    pack_fingerprint = "" if arm == PACK_A_LEVEL else _norm(exposure.get("true_shared_pack_e", {}).get("pack_fingerprint"))
    identity = _experimental_identity(session_id, provider, model, _norm(config.get("prompt_version")), cutoff, arm, pack_version, pack_fingerprint)
    base = {
        "experimental_identity": identity,
        "pair_identity": _fingerprint({"session_id": session_id, "provider": provider, "model": model, "prompt_version": _norm(config.get("prompt_version")), "forecast_cutoff": cutoff, "experimental_protocol_version": PROTOCOL_VERSION}),
        "session_id": session_id,
        "provider": provider,
        "model": model,
        "forecast_timestamp": cutoff,
        "pack_arm": arm,
        "pack_version": pack_version,
        "pack_fingerprint": pack_fingerprint,
        "rendered_context_fingerprint": _fingerprint(exposure),
        "pack_item_count": len(exposure.get("assigned_market_state_context", [])),
        "provisional_item_count": sum(1 for row in exposure.get("assigned_market_state_context", []) if _norm(row.get("availability_status")) == "AI_RETRIEVED_PROVISIONAL"),
        "unavailable_item_count": sum(1 for row in exposure.get("assigned_market_state_context", []) if _norm(row.get("availability_status")) in NON_FACT_PACK_STATUSES),
        "prompt_version": _norm(config.get("prompt_version")),
        "output_schema_version": _norm(config.get("output_schema_version")),
        "experimental_protocol_version": PROTOCOL_VERSION,
        "forecast_target": FORECAST_TARGET,
        "prompt_fingerprint": _fingerprint(prompt),
        "created_ts": _iso_now(),
        "shadow_only": True,
        "production_visible": False,
        "canonical_outcome_accessed": False,
    }
    if identity in existing:
        reused = dict(existing[identity])
        reused.update(base)
        reused["status"] = "CAPTURED"
        reused["capture_provenance"] = "DUPLICATE_EXACT_PAIR_REUSED"
        return reused
    response = _call_live_provider_raw(script_service, script_id, provider, model, dict(prompt))
    retry_count = 0
    if _norm(response.get("status")) in RETRYABLE_RESPONSE_STATUSES and not _norm(response.get("raw_output")):
        retry_count = 1
        response = _call_live_provider_raw(script_service, script_id, provider, model, dict(prompt))
    actual_model = _norm(response.get("model"))
    errors: List[str] = []
    if _norm(response.get("provider")) != provider:
        errors.append("APPS_SCRIPT_PROVIDER_CONFIGURATION_MISMATCH")
    if actual_model != model:
        errors.append("APPS_SCRIPT_MODEL_CONFIGURATION_MISMATCH")
    if _norm(response.get("status")) != "ok":
        errors.append("PROVIDER_CALL_FAILED:" + (_norm(response.get("error")) or _norm(response.get("status"))))
    validation = _response_validation(_norm(response.get("raw_output")), session_id, provider, model, arm, schema_rows)
    errors.extend(validation["errors"])
    row = dict(base)
    row.update({
        "actual_provider": _norm(response.get("provider")),
        "actual_model": actual_model,
        "request_status": _norm(response.get("request_status")),
        "response_status": _norm(response.get("response_status")),
        "provider_prompt_tokens": _norm(response.get("prompt_tokens")),
        "provider_completion_tokens": _norm(response.get("completion_tokens")),
        "retry_calls": retry_count,
        "raw_output": _norm(response.get("raw_output")),
        "raw_output_fingerprint": _fingerprint(_norm(response.get("raw_output"))),
        "error_message": "; ".join(sorted(set(errors))),
        "status": "CAPTURED" if not errors else "OUTPUT_SCHEMA_FAILED" if validation["errors"] else "PROVIDER_MODEL_UNAVAILABLE",
        "capture_provenance": "LIVE_STATELESS_PROVIDER_CALL",
        "forecast_direction": validation.get("forecast_direction", ""),
        "forecast_confidence": validation.get("forecast_confidence", ""),
        "no_signal_flag": validation.get("no_signal_flag", ""),
        "parsed_output": validation.get("parsed", {}),
        "parser_notes": validation.get("parser_notes", ""),
    })
    return row


def _pair_status(a: Mapping[str, Any], e: Mapping[str, Any]) -> str:
    a_ok, e_ok = _norm(a.get("status")) == "CAPTURED", _norm(e.get("status")) == "CAPTURED"
    if a_ok and e_ok:
        return "COMPLETE_A_AND_E_PAIR"
    if a_ok:
        return "PACK_A_ONLY"
    if e_ok:
        return "PACK_E_ONLY"
    if any("MODEL_CONFIGURATION" in _norm(row.get("error_message")) for row in (a, e)):
        return "PROVIDER_MODEL_UNAVAILABLE"
    if any("LEAKAGE" in _norm(row.get("error_message")) for row in (a, e)):
        return "LEAKAGE_CHECK_FAILED"
    if any("OUTPUT_SCHEMA" in _norm(row.get("status")) for row in (a, e)):
        return "OUTPUT_SCHEMA_FAILED"
    return "BOTH_ARMS_FAILED"


def _build_candidates(service, frozen_pack: Mapping[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    diagnostics_titles = _get_sheet_titles(service, DIAGNOSTICS_SPREADSHEET_ID)
    main_titles = _get_sheet_titles(service, MAIN_SPREADSHEET_ID)
    session_rows = _safe_read(service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, SESSIONS_SHEET)
    member_rows = _safe_read(service, DIAGNOSTICS_SPREADSHEET_ID, diagnostics_titles, MEMBERS_SHEET)
    event_rows = _safe_read(service, MAIN_SPREADSHEET_ID, main_titles, EVENT_SHEET)
    session_by_id: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in session_rows:
        if _norm(row.get("session_id")):
            session_by_id[_norm(row.get("session_id"))].append(row)
    members_by_session = _member_index(member_rows)
    events = _event_index(event_rows)
    eligible: List[Dict[str, Any]] = []
    audit: List[Dict[str, Any]] = []
    pack_session_ids = sorted({_norm(row.get("session_id")) for row in frozen_pack.get("pack_rows", []) if _norm(row.get("session_id"))})
    for session_id in pack_session_ids:
        reasons: List[str] = []
        matches = session_by_id.get(session_id, [])
        if len(matches) != 1:
            reasons.append("INELIGIBLE_SESSION_IDENTITY")
            audit.append({"session_id": session_id, "status": reasons[0], "reason": "AUTHORITATIVE_MARKET_SESSION_ROW_NOT_UNIQUE", "member_count": 0})
            continue
        session = matches[0]
        members = members_by_session.get(session_id, [])
        if not members:
            reasons.append("INELIGIBLE_SESSION_IDENTITY")
        event_context, context_errors = _build_event_context(session_id, session, members, events)
        if context_errors:
            reasons.append("INELIGIBLE_SESSION_IDENTITY")
        cutoff = _norm(session.get("primary_release_ts")) or _norm(session.get("session_start_ts"))
        pack_context = render_frozen_true_shared_pack_e_context(frozen_pack, session_id)
        pack_errors = _validate_pack_session(frozen_pack, session_id, pack_context)
        if pack_errors:
            reasons.append("INELIGIBLE_HISTORICAL_CUTOFF")
        if not cutoff or not _utc_parse(cutoff):
            reasons.append("INELIGIBLE_MISSING_FORECAST_INPUT")
        pack_rows = [row for row in frozen_pack.get("pack_rows", []) if _norm(row.get("session_id")) == session_id]
        pack_cutoffs = {_norm(row.get("forecast_timestamp")) for row in pack_rows if _norm(row.get("forecast_timestamp"))}
        if len(pack_cutoffs) != 1 or cutoff not in pack_cutoffs:
            reasons.append("INELIGIBLE_HISTORICAL_CUTOFF")
        if reasons:
            audit.append({"session_id": session_id, "status": reasons[0], "reason": "; ".join(sorted(set(reasons + context_errors + pack_errors))), "member_count": len(members)})
            continue
        row = {"session_id": session_id, "session": session, "members": members, "event_context": event_context, "cutoff": cutoff, "pack_context": pack_context}
        eligible.append(row)
        audit.append({"session_id": session_id, "status": "ELIGIBLE_FOR_A_VS_E_FORECAST", "reason": "", "member_count": len(members), "forecast_cutoff": cutoff, "known_exact_canonical_outcome": "NOT_QUERIED_DURING_CAPTURE"})
    return eligible, audit


def _run(args: argparse.Namespace) -> Dict[str, Any]:
    run_id = args.run_id or _run_id("9-PACK-A-VS-FROZEN-PACK-E-FORECAST-CAPTURE")
    output_dir = OUTPUT_ROOT / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    generated_ts = _iso_now()
    frozen_pack = load_frozen_true_shared_pack_e(FREEZE_MANIFEST)
    if frozen_pack["pack_fingerprint"] != EXPECTED_PACK_FINGERPRINT:
        raise CaptureBlocked("AUTHORITATIVE_PACK_E_FINGERPRINT_MISMATCH")
    contexts = [render_frozen_true_shared_pack_e_context(frozen_pack, session_id) for session_id in sorted({_norm(row.get("session_id")) for row in frozen_pack["pack_rows"]})]
    if content_fingerprint(contexts) != EXPECTED_RENDERED_FINGERPRINT:
        raise CaptureBlocked("FROZEN_PACK_E_RENDERED_CONTEXT_FINGERPRINT_MISMATCH")
    fixture_validation = json.loads(FIXTURE_VALIDATION.read_text(encoding="utf-8"))
    expected_contexts = {row["session_id"]: row for row in fixture_validation.get("sessions", [])}
    for context in contexts:
        session_id = _norm(context.get("true_shared_pack_e", {}).get("session_id"))
        # Renderer context does not carry its session id; obtain it by matching its known fingerprint below.
        del session_id
    creds = load_credentials()
    sheets_service = build_sheets_service(creds)
    provider_config, schema_rows, guardrail_rows, prompt_design_run_id = _load_prompt_configuration(sheets_service)
    schema_payload = _schema_payload(schema_rows)
    guardrails = _guardrail_payload(guardrail_rows)
    candidates, eligibility_audit = _build_candidates(sheets_service, frozen_pack)
    for candidate in candidates:
        fingerprint = content_fingerprint(candidate["pack_context"])
        expected = expected_contexts.get(candidate["session_id"], {})
        if _norm(expected.get("openai_delivery_fingerprint")) != fingerprint:
            raise CaptureBlocked("FROZEN_PACK_E_SESSION_RENDER_FINGERPRINT_MISMATCH:" + candidate["session_id"])
    fixture = _fixture_dry_run(schema_rows, provider_config)
    _write_json(output_dir / "fixture_dry_run.json", fixture)
    if not fixture["validation_pass"]:
        raise CaptureBlocked("FIXTURE_RESPONSE_VALIDATION_FAILED")
    existing = _existing_successes()
    prompt_audit: List[Dict[str, Any]] = []
    leakage_audit: List[Dict[str, Any]] = []
    preflight_failures: Set[Tuple[str, str]] = set()
    work: List[Dict[str, Any]] = []
    for candidate in candidates:
        for provider in PROVIDER_ORDER:
            config = provider_config.get(provider, {})
            if not config.get("configured"):
                preflight_failures.add((candidate["session_id"], provider))
                prompt_audit.append({"session_id": candidate["session_id"], "provider": provider, "status": "INELIGIBLE_PROVIDER_CONFIGURATION", "reason": _norm(config.get("reason"))})
                continue
            exposure_a, exposure_e = _pack_a_context(), _pack_e_context(candidate["pack_context"])
            execution_identity = {
                "session_id": candidate["session_id"],
                "provider": provider,
                "model": _norm(config["model"]),
            }
            prompt_a, hash_a, _ = _prompt_for_arm(config["design_row"], candidate["event_context"], exposure_a, schema_payload, guardrails, execution_identity)
            prompt_e, hash_e, _ = _prompt_for_arm(config["design_row"], candidate["event_context"], exposure_e, schema_payload, guardrails, execution_identity)
            equivalence = _prompt_without_exposure(prompt_a) == _prompt_without_exposure(prompt_e)
            errors_a = _validate_prompt(prompt_a, exposure_a, PACK_A_LEVEL)
            errors_e = _validate_prompt(prompt_e, exposure_e, PACK_E_LEVEL)
            prompt_audit.append({"session_id": candidate["session_id"], "provider": provider, "model": config["model"], "pack_a_prompt_fingerprint": hash_a, "pack_e_prompt_fingerprint": hash_e, "normalized_prompt_equivalence": equivalence, "status": "PASS" if equivalence and not errors_a and not errors_e else "FAIL", "errors": sorted(set(errors_a + errors_e + ([] if equivalence else ["UNINTENDED_PROMPT_DIFFERENCE"])))})
            for arm, prompt, exposure, errors in ((PACK_A_LEVEL, prompt_a, exposure_a, errors_a), (PACK_E_LEVEL, prompt_e, exposure_e, errors_e)):
                leakage_audit.append({"session_id": candidate["session_id"], "provider": provider, "pack_arm": arm, "prompt_fingerprint": _fingerprint(prompt), "leakage_check_status": "PASS" if not errors else "FAIL", "forbidden_fields": errors, "canonical_outcome_accessed_by_forecast_runner": False})
            if not equivalence or errors_a or errors_e:
                preflight_failures.add((candidate["session_id"], provider))
                continue
            work.append({**candidate, "provider": provider, "config": config, "prompt_a": prompt_a, "prompt_e": prompt_e, "exposure_a": exposure_a, "exposure_e": exposure_e})
    _write_jsonl(output_dir / "eligible_sessions.jsonl", eligibility_audit)
    _write_json(output_dir / "provider_configuration_freeze.json", {"prompt_design_run_id": prompt_design_run_id, "providers": provider_config, "protocol_version": PROTOCOL_VERSION, "prompt_wrapper_version": PROMPT_WRAPPER_VERSION})
    _write_jsonl(output_dir / "prompt_equivalence_audit.jsonl", prompt_audit)
    _write_jsonl(output_dir / "leakage_validation.jsonl", leakage_audit)
    if args.dry_run:
        _write_jsonl(output_dir / "pack_a_forecasts.jsonl", [])
        _write_jsonl(output_dir / "frozen_pack_e_forecasts.jsonl", [])
        _write_jsonl(output_dir / "matched_forecast_pairs.jsonl", [])
        _write_jsonl(output_dir / "incomplete_forecast_pairs.jsonl", [])
        summary = {"build_status": "PASS", "final_decision": "DRY_RUN_ONLY", "run_id": run_id, "eligible_sessions": len(candidates), "provider_pairs_preflight_ready": len(work), "provider_calls": 0, "outcome_fields_accessed": 0}
        _write_json(output_dir / "forecast_capture_summary.json", summary)
        _write_json(output_dir / "forecast_capture_manifest.json", {"run_id": run_id, "dry_run": True, "summary": summary, "pack_e_freeze_manifest": str(FREEZE_MANIFEST), "pack_e_fingerprint": EXPECTED_PACK_FINGERPRINT, "rendered_context_fingerprint": EXPECTED_RENDERED_FINGERPRINT, "canonical_outcome_rows_read_by_forecast_runner": 0})
        return summary
    script_service = build_script_service(creds)
    script_id = default_script_id()
    a_rows: List[Dict[str, Any]] = []
    e_rows: List[Dict[str, Any]] = []
    pair_rows: List[Dict[str, Any]] = []
    for item in work:
        # Frozen deterministic order: Pack A first, then Pack E; each Apps Script call is stateless.
        a_row = _capture_arm(script_service, script_id, item["provider"], item["config"], PACK_A_LEVEL, item["prompt_a"], item["session_id"], item["cutoff"], schema_rows, item["exposure_a"], existing)
        e_row = _capture_arm(script_service, script_id, item["provider"], item["config"], PACK_E_LEVEL, item["prompt_e"], item["session_id"], item["cutoff"], schema_rows, item["exposure_e"], existing)
        a_rows.append(a_row)
        e_rows.append(e_row)
        pair_rows.append({"pair_identity": a_row["pair_identity"], "session_id": item["session_id"], "provider": item["provider"], "model": item["config"]["model"], "pack_a_experimental_identity": a_row["experimental_identity"], "pack_e_experimental_identity": e_row["experimental_identity"], "status": _pair_status(a_row, e_row), "forecast_cutoff": item["cutoff"], "shadow_only": True, "outcomes_attached": False, "accuracy_calculated": False})
    incomplete_preflight = [{"session_id": session_id, "provider": provider, "status": "SESSION_INELIGIBLE" if not provider_config.get(provider, {}).get("configured") else "PROMPT_VALIDATION_FAILED", "reason": _norm(provider_config.get(provider, {}).get("reason")) or "PRE_FLIGHT_PROMPT_OR_LEAKAGE_VALIDATION_FAILED"} for session_id, provider in sorted(preflight_failures)]
    completed = [row for row in pair_rows if row["status"] == "COMPLETE_A_AND_E_PAIR"]
    incomplete = [row for row in pair_rows if row["status"] != "COMPLETE_A_AND_E_PAIR"] + incomplete_preflight
    _write_jsonl(output_dir / "pack_a_forecasts.jsonl", a_rows)
    _write_jsonl(output_dir / "frozen_pack_e_forecasts.jsonl", e_rows)
    _write_jsonl(output_dir / "matched_forecast_pairs.jsonl", completed)
    _write_jsonl(output_dir / "incomplete_forecast_pairs.jsonl", incomplete)
    actual_calls = sum(1 for row in a_rows + e_rows if _norm(row.get("capture_provenance")) == "LIVE_STATELESS_PROVIDER_CALL")
    retries = sum(int(row.get("retry_calls") or 0) for row in a_rows + e_rows)
    status_counts = Counter(row["status"] for row in pair_rows)
    if completed and not incomplete:
        decision = "MATCHED_PACK_A_VS_FROZEN_PACK_E_FORECASTS_CAPTURED"
    elif completed:
        decision = "PARTIAL_MATCHED_FORECAST_CAPTURE"
    elif not candidates:
        decision = "NO_ELIGIBLE_SESSIONS_FOR_FROZEN_PACK_E"
    elif all(not provider_config.get(provider, {}).get("configured") for provider in PROVIDER_ORDER):
        decision = "FORECAST_PROVIDER_CONFIGURATION_REQUIRED"
    else:
        decision = "PARTIAL_MATCHED_FORECAST_CAPTURE"
    summary = {
        "build_status": "PASS" if decision == "MATCHED_PACK_A_VS_FROZEN_PACK_E_FORECASTS_CAPTURED" else "PARTIAL",
        "final_decision": decision,
        "run_id": run_id,
        "frozen_pack_e_validation_run": VALIDATION_RUN_ID,
        "frozen_pack_e_version": frozen_pack["manifest"]["pack_version"],
        "pack_e_scientific_fingerprint": EXPECTED_PACK_FINGERPRINT,
        "pack_e_rendered_fingerprint": EXPECTED_RENDERED_FINGERPRINT,
        "candidate_sessions": len(eligibility_audit),
        "eligible_sessions": len(candidates),
        "ineligible_sessions": len(eligibility_audit) - len(candidates),
        "expected_maximum_calls": len(candidates) * len(PROVIDER_ORDER) * 2,
        "actual_provider_calls": actual_calls,
        "retry_calls": retries,
        "calls_by_provider": dict(Counter(row["provider"] for row in a_rows + e_rows if _norm(row.get("capture_provenance")) == "LIVE_STATELESS_PROVIDER_CALL")),
        "pack_a_forecasts_captured": sum(1 for row in a_rows if row["status"] == "CAPTURED"),
        "pack_e_forecasts_captured": sum(1 for row in e_rows if row["status"] == "CAPTURED"),
        "complete_pairs": len(completed),
        "incomplete_pairs": len(incomplete),
        "pair_statuses": dict(status_counts),
        "forecast_directions_by_arm": {"A": dict(Counter(row.get("forecast_direction") for row in a_rows if row["status"] == "CAPTURED")), "E": dict(Counter(row.get("forecast_direction") for row in e_rows if row["status"] == "CAPTURED"))},
        "no_signal_by_arm": {"A": sum(1 for row in a_rows if row.get("no_signal_flag") == "TRUE"), "E": sum(1 for row in e_rows if row.get("no_signal_flag") == "TRUE")},
        "outcome_fields_accessed": 0,
        "accuracy_calculated": False,
        "production_or_consumer_changes": 0,
    }
    manifest = {
        "run_id": run_id,
        "generated_ts": generated_ts,
        "protocol_version": PROTOCOL_VERSION,
        "prompt_wrapper_version": PROMPT_WRAPPER_VERSION,
        "shadow_only": True,
        "outcomes_attached": False,
        "accuracy_calculated": False,
        "canonical_outcome_rows_read_by_forecast_runner": 0,
        "pack_e_freeze_manifest": str(FREEZE_MANIFEST),
        "pack_e_fingerprint": EXPECTED_PACK_FINGERPRINT,
        "rendered_context_fingerprint": EXPECTED_RENDERED_FINGERPRINT,
        "provider_call_function": "apiCallProviderJsonObject",
        "provider_order_policy": "PACK_A_FIRST_THEN_PACK_E_STATELESS",
        "summary_fingerprint": _fingerprint(summary),
    }
    _write_json(output_dir / "forecast_capture_summary.json", summary)
    _write_json(output_dir / "forecast_capture_manifest.json", manifest)
    return summary


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture leakage-safe matched Pack A vs frozen true Pack E forecasts.")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--dry-run", action="store_true", help="Validate local inputs and prompts without provider calls.")
    return parser.parse_args(argv)


def main() -> None:
    args = _parse_args()
    try:
        result = _run(args)
    except (CaptureBlocked, FrozenPackEError, RuntimeError, ValueError) as exc:
        print(json.dumps({"build_status": "BLOCKED", "error": str(exc)}, ensure_ascii=True, indent=2))
        raise SystemExit(2)
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
