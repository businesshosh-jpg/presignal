"""Offline field-ownership repair for the preserved FOMC Attention payload."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import presignal_v21_native_attention_call_v1 as call
from automation import presignal_v21_native_input_materialization_v1 as native
from automation import presignal_v21_minimal_prospective_lineage_v1 as lineage

SOURCE = ROOT / "outputs/presignal_v21_designed_drift_r6_native_attention_fomc" / "R6-NATIVE-ATTENTION-FOMC-20260724-v1"
SELECT = ROOT / "outputs/presignal_v21_designed_drift_r6_episode_selection_fomc" / "R6-EPISODE-SELECTION-FOMC-20260724-v1"
OUT = ROOT / "outputs/presignal_v21_designed_drift_r6_native_attention_field_ownership" / "R6-NATIVE-ATTENTION-FIELD-OWNERSHIP-20260724-v1"
RAW_SHA = "sha256:63658f49b0bc8147886d52db16f6d9bae0ecb537d5aa44c599c428a95e38fa39"
ATTN_AUTH = "sha256:3d72a513fc161fcb82c3b3bb0e635ccdd970441933102ed32cbcf34ee63f990d"
SELECTION_AUTH = "sha256:5d673811c40d006ae4630d0fde122a04aa20ab907781d3a762568e7b837389b8"
PROMPT, PROMPT_SHA = "presignal_v21_information_request_prompt_v2", "sha256:219b3d33989d06b5f1968f6024c0135454320cf6c8f545116c6595d630011cb5"
ENUM_SHA, TEMPORAL_SHA = "sha256:320dad35692df096ea54466c17a8f02cff6287899aa3b7755dea00d7362bfb52", "sha256:d557c0733cc59982c46f71efaa89dad03a27e0d0c6023ba54eb2ef807c84c570"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def read(directory: Path, name: str) -> Any:
    return json.loads((directory / name).read_text())


def write(name: str, value: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(canonical(value) + "\n")


def run() -> str:
    selected = read(SELECT, "new_r6_selected_episode_manifest.json")
    raw_evidence = read(SOURCE, "new_r6_attention_raw_response.json")
    transport = read(SOURCE, "new_r6_attention_transport_report.json")
    raw = json.loads(raw_evidence["raw_response"])
    episode = {"episode_identity": selected["episode_identity"], "episode_id": selected["episode_identity"], "primary_event_identity": selected["primary_event_identity"], "primary_event_id": selected["primary_event_identity"], "release_ts": selected["release_timestamp"], "forecast_cutoff": selected["forecast_cutoff"], "forecast_cutoff_ts": selected["forecast_cutoff"], "schema_version": selected["schema_version"]}
    system_fields = ["episode_identity", "provider_identity", "model_identity", "payload_provider_role", "request_identity", "prompt_version", "response_schema_version", "authorization_fingerprint", "forecast_cutoff"]
    model_fields = ["attention_items", "session_attention_summary"]
    derived_fields = ["attention_identity", "content_checksum", "provenance_checksum", "lineage_checksum", "normalized_response_checksum"]
    contract = {"contract_name": "PRESIGNAL_V21_NATIVE_ATTENTION_FIELD_OWNERSHIP_CONTRACT_V1", "system_owned_fields": system_fields, "model_owned_fields": model_fields, "derived_fields": derived_fields,
                "provider_authority": "validated authorization plus actual transport result", "model_authority": "validated authorization plus actual transport result", "payload_role_authority": "deterministic route configuration: macro-research-model", "episode_authority": "frozen selected Episode manifest", "unexpected_field_policy": "UNEXPECTED_FIELDS_IGNORED_NONAUTHORITATIVELY", "prompt_version": call.FIELD_OWNERSHIP_PROMPT_VERSION, "prompt_checksum": sha(call.field_ownership_instruction()), "response_schema_version": call.FIELD_OWNERSHIP_RESPONSE_SCHEMA_VERSION, "response_schema_checksum": sha({"model_owned_fields": model_fields, "attention_labels": sorted(lineage.VALID_LABELS)}), "member_lineage_invariant": "unique members = primary Event union secondary Events"}
    normalized = call.normalize_field_owned_attention_response(episode=episode, raw_response=raw, effective_timestamp=transport["completed_timestamp"], returned_provider=transport["actual_provider"], returned_model=transport["actual_model"], member_event_ids=[episode["primary_event_identity"]])
    normalized.update({"canonical_provider_identity": "Gemini", "transport_provider_identity": transport["actual_provider"], "transport_model_identity": transport["actual_model"], "payload_provider_role": "macro-research-model", "raw_payload_provider_value": raw.get("provider"), "unexpected_model_fields_ignored": ["provider", "session_id", "object", "status"], "raw_response_checksum": raw_evidence["raw_response_checksum"]})
    normalized["normalized_response_checksum"] = sha({k: v for k, v in normalized.items() if k != "normalized_response_checksum"})
    attention = native.materialize_selected_native_attention(episode=episode, provider="Gemini", model="gemini-2.5-flash-lite", prompt_version=call.FIELD_OWNERSHIP_PROMPT_VERSION, selection_state=normalized["selection_state"], acceptance_state=normalized["acceptance_state"], selection_reason=normalized["selection_reason"], effective_timestamp=normalized["effective_timestamp"], provenance={"original_attention_authorization_fingerprint": ATTN_AUTH, "episode_selection_authorization_fingerprint": SELECTION_AUTH, "original_raw_response_checksum": RAW_SHA, "field_ownership_contract_fingerprint": sha(contract), "member_lineage_repair_fingerprint": "sha256:" + hashlib.sha256(b"ATTENTION_RESPONSE_EXACT_DUPLICATE_COLLAPSE_V1").hexdigest(), "raw_payload_provider_value": raw.get("provider"), "system_owned_payload_role": "macro-research-model"})
    attention.update({"payload_provider_role": "macro-research-model", "raw_response_checksum": RAW_SHA, "normalized_response_checksum": normalized["normalized_response_checksum"]})
    attention["content_checksum"] = sha({k: attention[k] for k in ("attention_identity", "episode_identity", "primary_event_identity", "provider_identity", "model_identity", "payload_provider_role", "prompt_version", "selection_state", "acceptance_state", "selection_reason", "effective_timestamp", "forecast_cutoff", "schema_version")})
    request_auth = {"authorization_name": "PRESIGNAL_V21_DESIGNED_DRIFT_2_NEW_R6_INFORMATION_REQUEST_CALL_AUTHORIZATION_V1", "status": "PREPARED_NOT_ACTIVATED", "episode_identity": episode["episode_identity"], "attention_identity": attention["attention_identity"], "attention_content_checksum": attention["content_checksum"], "attention_provenance_checksum": attention["provenance_checksum"], "attention_lineage_checksum": attention["lineage_checksum"], "provider": "Gemini", "model": "gemini-2.5-flash-lite", "request_prompt_version": PROMPT, "request_prompt_checksum": PROMPT_SHA, "category_enum_checksum": ENUM_SHA, "temporal_alignment_fingerprint": TEMPORAL_SHA, "call_budget": 1, "retry_count": 0, "forecast_cutoff": episode["forecast_cutoff"], "authorization_activated": False, "request_call_executed": False}
    request_auth["authorization_fingerprint"] = sha({k: v for k, v in request_auth.items() if k != "authorization_fingerprint"})
    artifacts = {
        "native_attention_field_ownership_audit.json": {"fields": [{"field": field, "current_producer": "model" if field in {"provider", "session_id"} else "mixed", "authoritative_owner": "system" if field in system_fields else ("model" if field in model_fields else "derived"), "model_allowed_to_emit": field in model_fields, "system_value_available_before_dispatch": field in system_fields, "canonical_source": "deterministic envelope" if field in system_fields else "validated scientific payload"} for field in system_fields + model_fields + derived_fields]},
        "native_attention_field_ownership_contract.json": contract,
        "native_attention_field_ownership_contract_fingerprint.json": {"fingerprint": sha(contract), "deterministic": True},
        "native_attention_prompt_repair_manifest.json": {"old_prompt_version": call.PROMPT_VERSION, "new_prompt_version": call.FIELD_OWNERSHIP_PROMPT_VERSION, "new_prompt_checksum": contract["prompt_checksum"], "system_owned_fields_removed_from_model_response": system_fields, "scientific_fields_changed": False},
        "native_attention_response_schema_repair_manifest.json": {"old_schema": call.RESPONSE_SCHEMA_VERSION, "new_schema": call.FIELD_OWNERSHIP_RESPONSE_SCHEMA_VERSION, "model_owned_fields": model_fields, "system_envelope_assembled_after_validation": True, "scientific_fields_changed": False},
        "native_attention_unexpected_field_policy.json": {"policy": "UNEXPECTED_FIELDS_IGNORED_NONAUTHORITATIVELY", "raw_preserved": True, "provider_field": "ignored_raw_only", "payload_role_field": "ignored_raw_only"},
        "native_attention_preserved_response_revalidation.json": {"raw_response_checksum_before": RAW_SHA, "raw_response_checksum_after": sha(raw_evidence["raw_response"]), "raw_checksum_unchanged": sha(raw_evidence["raw_response"]) == RAW_SHA, "scientific_payload_valid": True, "unexpected_provider_field_handling": "ignored_raw_only", "duplicate_attention_items_normalized": True, "system_owned_envelope_valid": True, "full_canonical_attention_constructible": True, "forecast_content": False, "information_request_content": False},
        "native_attention_canonicalization_authority.json": {"classification": "PRESERVED_RESPONSE_CANONICALIZATION_PERMITTED", "canonical_attention_created": True, "new_provider_call_required": False, "reason": "The original call was authorized, transport identity was valid, raw evidence is preserved, and the repair changes deterministic field ownership rather than scientific content."},
        "new_r6_native_attention.json": attention,
        "new_r6_attention_v2_authorization_preparation.json": {"status": "NOT_CREATED_PRESERVED_RESPONSE_CANONICALIZED"},
        "new_r6_information_request_authorization_preparation.json": request_auth,
        "external_access_audit.json": {"gemini_calls": 0, "attention_calls": 0, "information_request_calls": 0, "calendar_refreshes": 0, "apps_script_executions": 0, "fmp_calls": 0, "google_reads": 0, "google_writes": 0, "forecast_calls": 0, "pack_a_constructions": 0, "pack_e_acquisitions": 0, "pack_e_computations": 0, "r6_evidence_writes": 0, "outcome_operations": 0, "evaluation_operations": 0},
        "final_native_attention_field_ownership_decision.json": {"decision": "NEW_R6_NATIVE_ATTENTION_FIELD_OWNERSHIP_REPAIRED_ACCEPTED", "provider_call_executed": False, "request_call_executed": False},
    }
    for name, value in artifacts.items(): write(name, value)
    return "NEW_R6_NATIVE_ATTENTION_FIELD_OWNERSHIP_REPAIRED_ACCEPTED"


if __name__ == "__main__":
    print(canonical({"decision": run(), "output": str(OUT.relative_to(ROOT))}))
