"""Pure validation helpers for the one-call R6 native Attention boundary.

This module deliberately contains no Google client, provider client, writer, or
retry policy.  The caller supplies a bounded Event-read inventory and, only
after pre-dispatch admission, the one raw provider response.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

from automation import presignal_v21_minimal_prospective_lineage_v1 as lineage
from automation import presignal_v21_native_input_materialization_v1 as native


AUTHORIZATION_NAME = "PRESIGNAL_V21_DESIGNED_DRIFT_2_R6_NATIVE_ATTENTION_CALL_AUTHORIZATION_V1"
FREEZE_FINGERPRINT = "sha256:8c910a343515d88ca63ce4aaf738f28f9b4a8ab22665397077858bfaf7e866e4"
R6_V3_FINGERPRINT = "sha256:c8cb003af94eef2ef9cad8f323ab31b3c1990f3ffdcdab5ee3e6285fda76efb9"
NATIVE_INPUT_READINESS_FINGERPRINT = "sha256:9c87feb779d862b2a19f85b9a261eabf6c7d1d1d1fb8a1f454ed1c7b0ca23587"
PROVIDER = "Gemini"
MODEL = "gemini-2.5-flash-lite"
PROMPT_VERSION = "existing_v2_attention_prompt_schema"
RESPONSE_SCHEMA_VERSION = "session_attention_map/v0"
TRUSTED_GEMINI_PAYLOAD_ROLE = "macro-research-model"
TRUSTED_GEMINI_PROMPT_TEMPLATE_CHECKSUM = "sha256:cadc09041ed55dee5ecc2b2bf285d9b8da772df0de8381b6f6c8f3f7b0d44d96"
TRUSTED_GEMINI_BRIDGE_SOURCE_CHECKSUM = "sha256:6f20eaacdccdc3eaefb2fc4c86c93fe6e7fa17e7c2184778341401eead6d6c32"


class NativeAttentionCallError(ValueError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def checksum(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def normalize_trusted_gemini_bridge_identity(*, raw_response: Mapping[str, Any], transport_provider: str,
                                              transport_model: str, prompt_template_checksum: str,
                                              bridge_source_checksum: str) -> dict[str, Any]:
    """Canonicalize one historically established Gemini prompt-agent role.

    The raw payload is never edited.  This narrow adapter owns only the exact
    descriptive provider value previously normalized by the routed v2 bridge.
    """
    if transport_provider != PROVIDER:
        raise NativeAttentionCallError("ATTENTION_BRIDGE_TRANSPORT_PROVIDER_MISMATCH")
    if transport_model != MODEL:
        raise NativeAttentionCallError("ATTENTION_BRIDGE_TRANSPORT_MODEL_MISMATCH")
    if prompt_template_checksum != TRUSTED_GEMINI_PROMPT_TEMPLATE_CHECKSUM:
        raise NativeAttentionCallError("ATTENTION_BRIDGE_PROMPT_VERSION_MISMATCH")
    if bridge_source_checksum != TRUSTED_GEMINI_BRIDGE_SOURCE_CHECKSUM:
        raise NativeAttentionCallError("ATTENTION_BRIDGE_SOURCE_VERSION_MISMATCH")
    if raw_response.get("provider") != TRUSTED_GEMINI_PAYLOAD_ROLE:
        raise NativeAttentionCallError("ATTENTION_BRIDGE_PAYLOAD_ROLE_MISMATCH")
    canonical_payload = dict(raw_response)
    canonical_payload["provider"] = PROVIDER
    return {"canonical_payload": canonical_payload, "canonical_provider_identity": PROVIDER,
            "transport_provider_identity": transport_provider, "transport_model_identity": transport_model,
            "payload_provider_role": TRUSTED_GEMINI_PAYLOAD_ROLE,
            "mapping_rule": "EXACT_GEMINI_ROUTED_TRANSPORT_PLUS_PROMPT_AGENT_ROLE_V1",
            "bridge_metadata_checksum": checksum({"transport_provider": transport_provider, "transport_model": transport_model,
                                                     "prompt_template_checksum": prompt_template_checksum,
                                                     "bridge_source_checksum": bridge_source_checksum,
                                                     "payload_provider_role": TRUSTED_GEMINI_PAYLOAD_ROLE})}


def normalize_preserved_gemini_attention_response(*, episode: Mapping[str, Any], raw_response: Mapping[str, Any],
                                                   effective_timestamp: str, member_event_ids: Sequence[str],
                                                   prompt_template_checksum: str, bridge_source_checksum: str,
                                                   preserved_raw_response_checksum: str | None = None) -> dict[str, Any]:
    """Apply the exact bridge-role rule before standard native validation."""
    mapped = normalize_trusted_gemini_bridge_identity(
        raw_response=raw_response, transport_provider=PROVIDER, transport_model=MODEL,
        prompt_template_checksum=prompt_template_checksum, bridge_source_checksum=bridge_source_checksum,
    )
    normalized = normalize_attention_response(
        episode=episode, raw_response=mapped["canonical_payload"], effective_timestamp=effective_timestamp,
        returned_provider=PROVIDER, returned_model=MODEL, member_event_ids=member_event_ids,
    )
    normalized.update({key: mapped[key] for key in ("canonical_provider_identity", "transport_provider_identity", "transport_model_identity", "payload_provider_role", "mapping_rule", "bridge_metadata_checksum")})
    normalized["raw_response_checksum"] = preserved_raw_response_checksum or checksum(raw_response)
    normalized["normalized_response_checksum"] = checksum({key: value for key, value in normalized.items() if key != "normalized_response_checksum"})
    return normalized


def authorization_manifest() -> dict[str, Any]:
    return {
        "authorization_name": AUTHORIZATION_NAME,
        "schema_version": "1",
        "route_b_freeze_fingerprint": FREEZE_FINGERPRINT,
        "r6_authorization_v3_fingerprint": R6_V3_FINGERPRINT,
        "native_input_readiness_fingerprint": NATIVE_INPUT_READINESS_FINGERPRINT,
        "episode_source": {"spreadsheet_id": "1_gZGnd6h3VzdiBvGBHRSxn78KW8tsOi2UEc6Y_Sc23Q", "object": "Event!A:V", "episode_count": 1, "prospective_only": True, "batch_episode_prohibited": True},
        "attention_scope": {"provider": PROVIDER, "model": MODEL, "call_budget": 1, "retry_count": 0, "prompt_version": PROMPT_VERSION, "response_schema_version": RESPONSE_SCHEMA_VERSION},
        "prohibitions": {"forecast_calls": 0, "acquisition_calls": 0, "google_scientific_writes": 0, "outcome_operations": 0, "evaluation_operations": 0},
        "failure_stop_policy": ["episode_read_failed", "no_eligible_episode", "episode_selection_ambiguous", "cutoff_closed", "provider_or_model_mismatch", "prompt_or_schema_mismatch", "attention_response_invalid", "no_retry"],
    }


def select_single_eligible_episode(candidates: Sequence[Mapping[str, Any]], *, as_of_utc: str) -> dict[str, Any]:
    """Select only a sole, pre-cutoff standalone Episode; never rank candidates."""
    now = parse_utc(as_of_utc)
    eligible = []
    normalized = []
    for candidate in candidates:
        row = dict(candidate)
        if row.get("status") != "ELIGIBLE":
            normalized.append(row)
            continue
        required = ("episode_identity", "primary_event_identity", "release_ts", "forecast_cutoff", "schema_version")
        if any(not row.get(field) for field in required):
            row.update({"status": "REJECTED", "reason": "EPISODE_LINEAGE_INCOMPLETE"})
        elif parse_utc(str(row["forecast_cutoff"])) <= now or parse_utc(str(row["release_ts"])) <= now:
            row.update({"status": "REJECTED", "reason": "FORECAST_CUTOFF_CLOSED"})
        elif row.get("market_session_context") != "STANDALONE_EVENT":
            row.update({"status": "REJECTED", "reason": "BATCH_EPISODE_PROHIBITED"})
        else:
            eligible.append(row)
        normalized.append(row)
    if not eligible:
        return {"decision": "R6_NATIVE_ATTENTION_NO_ELIGIBLE_EPISODE", "selected_episode": None, "eligible_candidates": [], "candidates": normalized}
    if len(eligible) != 1:
        return {"decision": "R6_NATIVE_ATTENTION_EPISODE_SELECTION_AMBIGUOUS", "selected_episode": None, "eligible_candidates": eligible, "candidates": normalized, "selection_rule": "No authoritative tie-break exists; no ranking was applied."}
    selected = eligible[0]
    return {"decision": "SELECTED", "selected_episode": selected, "eligible_candidates": eligible, "candidates": normalized, "selection_rule": "Exactly one standalone canonical Episode was eligible."}


def attention_call_input(*, episode: Mapping[str, Any], effective_timestamp: str, collection_run_id: str,
                         member_rows: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """Freeze the established v2 prompt and bridge request for one selected Episode."""
    if parse_utc(effective_timestamp) >= parse_utc(str(episode["forecast_cutoff"])):
        raise NativeAttentionCallError("ATTENTION_AFTER_FORECAST_CUTOFF")
    session = {"session_id": str(episode["episode_identity"]), "country": str(episode.get("country") or "US"), "session_window_name": "R6_SINGLE_EVENT", "session_start_ts": effective_timestamp, "session_end_ts": str(episode["release_ts"])}
    supplied_members = list(member_rows or [])
    if not supplied_members:
        supplied_members = [{"event_id": str(episode["primary_event_identity"]), "batch_id": "", "type": "single", "indicator_name": str(episode.get("event_name") or episode["primary_event_identity"]), "genre": str(episode.get("genre") or ""), "importance": str(episode.get("importance") or ""), "release_ts": str(episode["release_ts"]), "consensus_value": str(episode.get("consensus_value") or ""), "prev_revision": str(episode.get("prev_revision") or ""), "member_order": 1}]
    members = []
    for order, source in enumerate(supplied_members, 1):
        row = dict(source)
        if not row.get("event_id") or not row.get("indicator_name") or str(row.get("release_ts")) != str(episode["release_ts"]):
            raise NativeAttentionCallError("ATTENTION_MEMBER_LINEAGE_MISMATCH")
        members.append({"event_id": str(row["event_id"]), "batch_id": str(row.get("batch_id") or ""), "type": str(row.get("type") or "single"), "indicator_name": str(row["indicator_name"]), "genre": str(row.get("genre") or ""), "importance": str(row.get("importance") or ""), "release_ts": str(row["release_ts"]), "consensus_value": str(row.get("consensus_value") or ""), "prev_revision": str(row.get("prev_revision") or ""), "member_order": int(row.get("member_order") or order)})
    if [row["event_id"] for row in members].count(str(episode["primary_event_identity"])) != 1:
        raise NativeAttentionCallError("ATTENTION_PRIMARY_MEMBER_MISMATCH")
    dry = lineage.build_prospective_attention(study_id="PRESIGNAL_V21_R6", collection_run_id=collection_run_id, session_snapshot=session, member_rows=members, provider=PROVIDER, model=MODEL, information_cutoff_ts=str(episode["forecast_cutoff"]), attention_run_id="PATTN_" + checksum({"episode": episode["episode_identity"], "provider": PROVIDER})[7:27], stage_generated_ts=effective_timestamp)
    return {"episode": dict(episode), "session": session, "members": members, "prompt": dry["prompt"], "bridge_request": dry["request"], "prompt_template_checksum": checksum(lineage.ATTENTION_INSTRUCTION), "resolved_prompt_checksum": checksum(dry["prompt"]), "episode_checksum": checksum(episode), "response_schema_checksum": checksum({"object": "session_attention_map", "schema_version": RESPONSE_SCHEMA_VERSION, "labels": sorted(lineage.VALID_LABELS)}), "provider_call_parameters_checksum": checksum(dry["request"])}


def normalize_attention_response(*, episode: Mapping[str, Any], raw_response: Mapping[str, Any], effective_timestamp: str,
                                 returned_provider: str, returned_model: str,
                                 member_event_ids: Sequence[str] | None = None) -> dict[str, Any]:
    """Adapt only the authoritative PRIMARY_DRIVER selection to native selected Attention."""
    if returned_provider != PROVIDER or returned_model != MODEL:
        raise NativeAttentionCallError("ATTENTION_PROVIDER_MODEL_MISMATCH")
    if parse_utc(effective_timestamp) > parse_utc(str(episode["forecast_cutoff"])):
        raise NativeAttentionCallError("ATTENTION_AFTER_FORECAST_CUTOFF")
    if raw_response.get("object") != "session_attention_map" or raw_response.get("session_id") != episode["episode_identity"] or raw_response.get("status") != "ok":
        raise NativeAttentionCallError("ATTENTION_RESPONSE_SCHEMA_INVALID")
    if raw_response.get("provider") != PROVIDER:
        raise NativeAttentionCallError("ATTENTION_RESPONSE_PROVIDER_FIELD_MISMATCH")
    all_items = list(raw_response.get("attention_items", []))
    if not all(isinstance(item, Mapping) for item in all_items):
        raise NativeAttentionCallError("ATTENTION_RESPONSE_SCHEMA_INVALID")
    # Collapse only byte-for-byte identical duplicate references at the
    # response-boundary construction point.  Conflicting claims for one Event
    # remain invalid rather than being hidden by a final validator.
    deduplicated: dict[str, Mapping[str, Any]] = {}
    for candidate in all_items:
        event_id = str(candidate.get("event_id") or "")
        prior = deduplicated.get(event_id)
        if prior is not None and canonical(candidate) != canonical(prior):
            raise NativeAttentionCallError("ATTENTION_DUPLICATE_MEMBER_CONFLICT")
        deduplicated.setdefault(event_id, candidate)
    all_items = list(deduplicated.values())
    if member_event_ids is not None:
        expected = [str(value) for value in member_event_ids]
        returned = [str(item.get("event_id") or "") for item in all_items]
        if sorted(returned) != sorted(expected) or len(set(returned)) != len(returned):
            raise NativeAttentionCallError("ATTENTION_MEMBER_LINEAGE_MISMATCH")
    items = [item for item in all_items if str(item.get("event_id")) == str(episode["primary_event_identity"])]
    if len(items) != 1:
        raise NativeAttentionCallError("ATTENTION_EPISODE_LINEAGE_MISMATCH")
    item = dict(items[0]); label = str(item.get("attention_label") or "")
    if label not in lineage.VALID_LABELS or label == "WATCH":
        raise NativeAttentionCallError("ATTENTION_STATE_INVALID")
    # The frozen mapping makes PRIMARY_DRIVER the only FORECAST selection.
    selection_state = "SELECTED_FOR_INFORMATION_REQUESTS" if label == "PRIMARY_DRIVER" else "NOT_SELECTED"
    acceptance_state = "ACCEPTED" if selection_state.startswith("SELECTED") else "REJECTED"
    reason = str(item.get("attention_reason") or "")
    if not reason:
        raise NativeAttentionCallError("ATTENTION_REQUIRED_RATIONALE_MISSING")
    normalized = {"episode_identity": episode["episode_identity"], "primary_event_identity": episode["primary_event_identity"], "provider_identity": PROVIDER, "model_identity": MODEL, "prompt_version": PROMPT_VERSION, "selection_state": selection_state, "acceptance_state": acceptance_state, "selection_reason": reason, "effective_timestamp": effective_timestamp, "forecast_cutoff": episode["forecast_cutoff"], "schema_version": native.ATTENTION_SCHEMA_VERSION, "attention_label": label, "raw_response_checksum": checksum(raw_response)}
    normalized["normalized_response_checksum"] = checksum(normalized)
    return normalized


def execute_one_attention(*, episode: Mapping[str, Any], effective_timestamp: str, collection_run_id: str,
                          dispatcher: Callable[[Mapping[str, Any]], Mapping[str, Any]]) -> dict[str, Any]:
    """Dispatch one already-admitted call through an injected existing bridge.

    There is intentionally no retry loop, provider construction, Google access,
    or persistence here.  A caller must use this only after the exact-one
    candidate admission has passed.
    """
    pre_call = attention_call_input(episode=episode, effective_timestamp=effective_timestamp, collection_run_id=collection_run_id)
    response = dict(dispatcher(pre_call["bridge_request"]))  # exactly one dispatch expression
    if response.get("status") != "ok":
        raise NativeAttentionCallError("ATTENTION_TRANSPORT_OR_PROVIDER_FAILURE")
    raw = response.get("raw_output")
    try:
        raw_object = dict(raw) if isinstance(raw, Mapping) else json.loads(str(raw))
    except Exception as exc:
        raise NativeAttentionCallError("ATTENTION_RAW_RESPONSE_INVALID") from exc
    normalized = normalize_attention_response(
        episode=episode,
        raw_response=raw_object,
        effective_timestamp=str(response.get("completed_timestamp") or effective_timestamp),
        returned_provider=str(response.get("actual_provider") or PROVIDER),
        returned_model=str(response.get("actual_model") or MODEL),
    )
    return {"pre_call": pre_call, "response": response, "raw_response": raw_object, "normalized_response": normalized, "provider_calls": 1, "retry_count": 0}
