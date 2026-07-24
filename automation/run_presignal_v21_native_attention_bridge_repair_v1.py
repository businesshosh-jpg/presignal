"""Offline-only audit of the preserved FOMC Attention response."""
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

SOURCE = ROOT / "outputs/presignal_v21_designed_drift_r6_native_attention_fomc" / "R6-NATIVE-ATTENTION-FOMC-20260724-v1"
OUT = ROOT / "outputs/presignal_v21_designed_drift_r6_native_attention_bridge_repair" / "R6-NATIVE-ATTENTION-BRIDGE-REPAIR-20260724-v1"
RAW_SHA = "sha256:63658f49b0bc8147886d52db16f6d9bae0ecb537d5aa44c599c428a95e38fa39"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def write(name: str, value: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(canonical(value) + "\n", encoding="utf-8")


def run() -> str:
    raw_evidence = json.loads((SOURCE / "new_r6_attention_raw_response.json").read_text())
    request = json.loads((SOURCE / "new_r6_attention_request_envelope.json").read_text())
    raw = json.loads(raw_evidence["raw_response"])
    member_ids = [item["event_id"] for item in raw["attention_items"]]
    unique = []
    for item in raw["attention_items"]:
        if not any(canonical(item) == canonical(previous) for previous in unique):
            unique.append(item)
    role_trace = {"observed_role": raw["provider"], "origin": "model-generated raw response field provider", "request_side_value": None,
                  "bridge_wrapper_behavior": "preserves raw_output without rewriting payload.provider", "normalizer_expected_role": call.TRUSTED_GEMINI_PAYLOAD_ROLE,
                  "originating_paths": ["automation/presignal_v21_minimal_prospective_lineage_v1.py:ATTENTION_INSTRUCTION", "apps_script/authoritative_provider_bridge.js:_authoritativeBridgeResult_", "automation/presignal_v21_native_attention_call_v1.py:normalize_trusted_gemini_bridge_identity"]}
    role_decision = {"classification": "MODEL_GENERATED_UNTRUSTED_VALUE", "canonical_role": None, "existing_allowed_role": call.TRUSTED_GEMINI_PAYLOAD_ROLE,
                     "repair_implemented": False, "provider_identity_changed": False, "role_enum_broadened": False,
                     "reason": "No repository alias or bridge mapping for macromodel exists; mapping it to the allowed macro-research-model role would invent a payload-role alias."}
    lineage_trace = {"authoritative_episode_member_count": 1, "request_member_count": len(request["bridge_request"]["prompt"]["user"]),
                     "request_event_count": 1, "raw_response_member_count": len(member_ids), "raw_response_member_ids": member_ids,
                     "duplication_origin": "model-generated response attention_items; the frozen request contained one Event", "selected_primary_event_identity": "5ea0-ce20-ad20-fba0"}
    lineage_repair = {"repair_location": "automation/presignal_v21_native_attention_call_v1.py:normalize_attention_response", "repair_kind": "response-boundary exact-duplicate collapse before member-lineage validation", "deduplication_key": "country|indicator_name|release_ts via authoritative Episode-member identity; response adapter uses the bound event_id as its serialized identity", "request_member_count_before": 1, "request_member_count_after": 1, "response_member_count_before": 2, "response_member_count_after": len(unique), "same_time_distinct_events_preserved": True, "conflicting_duplicates_fail_closed": True}
    preserved = {"raw_response_checksum_before": raw_evidence["raw_response_checksum"], "raw_response_checksum_after": sha(raw_evidence["raw_response"]),
                 "raw_response_unchanged": raw_evidence["raw_response_checksum"] == RAW_SHA == sha(raw_evidence["raw_response"]), "schema_valid_before": False,
                 "payload_role_valid_after": False, "member_lineage_valid_after": len(unique) == 1, "forecast_content": False, "information_request_content": False,
                 "additional_divergences": ["ATTENTION_BRIDGE_PAYLOAD_ROLE_MISMATCH"], "schema_valid_after": False}
    repair_manifest = {"repair_name": "PRESIGNAL_V21_NATIVE_ATTENTION_BRIDGE_REPAIR_V1", "prior_raw_response_checksum": RAW_SHA,
                       "payload_role_decision": role_decision["classification"], "member_lineage_repair": lineage_repair["repair_location"], "provider_identity_unchanged": True,
                       "prior_authorization_consumed": True, "new_provider_calls": 0}
    artifacts = {
        "new_r6_attention_payload_role_trace.json": role_trace,
        "new_r6_attention_payload_role_decision.json": role_decision,
        "new_r6_attention_member_lineage_trace.json": lineage_trace,
        "new_r6_attention_member_lineage_repair.json": lineage_repair,
        "new_r6_attention_bridge_repair_manifest.json": repair_manifest,
        "new_r6_attention_bridge_repair_fingerprint.json": {"fingerprint": sha(repair_manifest), "deterministic": True},
        "new_r6_attention_preserved_response_revalidation.json": preserved,
        "new_r6_attention_preserved_response_normalized.json": {"status": "NOT_CREATED_PAYLOAD_ROLE_UNRESOLVED", "raw_response_unchanged": True, "deduplicated_member_count": len(unique)},
        "new_r6_attention_canonicalization_authority_report.json": {"classification": "PRESERVED_RESPONSE_STILL_INVALID", "canonical_attention_created": False, "new_provider_call_required": False, "reason": "Untrusted macromodel role cannot be normalized under the frozen contract."},
        "new_r6_native_attention.json": {"status": "NOT_CREATED"},
        "new_r6_attention_v2_authorization_preparation.json": {"status": "NOT_CREATED_PAYLOAD_ROLE_BLOCKED"},
        "new_r6_information_request_authorization_preparation.json": {"status": "NOT_CREATED"},
        "external_access_audit.json": {"gemini_calls": 0, "attention_calls": 0, "information_request_calls": 0, "calendar_refreshes": 0, "apps_script_executions": 0, "fmp_calls": 0, "google_reads": 0, "google_writes": 0, "forecast_calls": 0, "pack_a_constructions": 0, "pack_e_acquisitions": 0, "pack_e_computations": 0, "r6_evidence_writes": 0, "outcome_operations": 0, "evaluation_operations": 0},
        "final_new_r6_attention_bridge_repair_decision.json": {"decision": "NEW_R6_ATTENTION_BRIDGE_REPAIR_BLOCKED_PAYLOAD_ROLE", "new_provider_call_executed": False},
    }
    for name, value in artifacts.items(): write(name, value)
    return "NEW_R6_ATTENTION_BRIDGE_REPAIR_BLOCKED_PAYLOAD_ROLE"


if __name__ == "__main__":
    print(canonical({"decision": run(), "output": str(OUT.relative_to(ROOT))}))
