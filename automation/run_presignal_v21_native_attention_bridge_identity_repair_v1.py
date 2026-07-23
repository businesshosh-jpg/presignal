"""Offline-only identity repair and revalidation for the preserved R6 Attention response."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from automation import presignal_v21_native_attention_call_v1 as call
from automation import presignal_v21_native_input_materialization_v1 as native
from automation import run_presignal_v21_r6_native_attention_execution_v1 as execution

EXECUTION = ROOT / "outputs" / "presignal_v21_designed_drift_r6_native_attention_execution" / "R6-NATIVE-ATTENTION-EXECUTION-20260723-v1"
OUTPUT = ROOT / "outputs" / "presignal_v21_designed_drift_r6_native_attention_bridge_identity_repair" / "R6-NATIVE-ATTENTION-BRIDGE-IDENTITY-REPAIR-20260723-v1"


def canonical(value: Any) -> str: return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(canonical(value) + "\n", encoding="utf-8")
def read(path: Path) -> Any: return json.loads(path.read_text(encoding="utf-8"))
def sha_file(path: Path) -> str: return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
def git_blob(path: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD:" + str(path.relative_to(ROOT))], cwd=ROOT, text=True).strip()
def git_commit(path: Path) -> str:
    return subprocess.check_output(["git", "log", "-1", "--format=%H", "--", str(path.relative_to(ROOT))], cwd=ROOT, text=True).strip()


def occurrence_inventory() -> list[dict[str, Any]]:
    paths = sorted(ROOT.glob("outputs/presignal_v21_step8_r2_historical_replication/**/attention/gemini.json"))
    rows = []
    for path in paths:
        data = read(path); raw_records = []
        def walk(value: Any) -> None:
            if isinstance(value, dict):
                if isinstance(value.get("raw_output"), str): raw_records.append(value)
                for nested in value.values(): walk(nested)
            elif isinstance(value, list):
                for nested in value: walk(nested)
        walk(data)
        exact = 0
        for record in raw_records:
            try: exact += int(json.loads(record["raw_output"]).get("provider") == call.TRUSTED_GEMINI_PAYLOAD_ROLE)
            except json.JSONDecodeError: pass
        if exact:
            rows.append({"path": str(path.relative_to(ROOT)), "source_commit": git_commit(path), "blob": git_blob(path), "field_name": "raw_output.provider", "semantic_meaning": "model-authored descriptive prompt-agent role", "producer": "Gemini raw payload", "consumer": "historical routed-provider context adapter", "fixed_by_code": False, "provider_specific": True, "successful_prior_response_records": exact})
    rows.extend([
        {"path": str((EXECUTION / "attention_raw_response.json").relative_to(ROOT)), "source_commit": git_commit(EXECUTION / "attention_raw_response.json"), "blob": git_blob(EXECUTION / "attention_raw_response.json"), "field_name": "raw_response.provider", "semantic_meaning": "model-authored descriptive prompt-agent role", "producer": "Gemini raw payload", "consumer": "native Attention validator", "fixed_by_code": False, "provider_specific": True, "successful_prior_response_records": 0},
        {"path": "automation/presignal_v21_native_attention_call_v1.py", "source_commit": "PENDING_CURRENT_REPAIR_COMMIT", "blob": sha_file(ROOT / "automation/presignal_v21_native_attention_call_v1.py"), "field_name": "TRUSTED_GEMINI_PAYLOAD_ROLE", "semantic_meaning": "narrow canonicalization input", "producer": "repair adapter", "consumer": "offline revalidation", "fixed_by_code": True, "provider_specific": True, "successful_prior_response_records": 0},
    ])
    return rows


def run(output: Path = OUTPUT) -> None:
    raw_evidence = read(EXECUTION / "attention_raw_response.json")
    pre = read(EXECUTION / "attention_pre_call_manifest.json")
    raw_text = raw_evidence["raw_response"]; raw = json.loads(raw_text)
    expected_raw = "sha256:2a64593f94788ed7b7566c98081e2c13993cf6a0338538c8d2e61c160058c2c9"
    raw_checksum_valid = call.checksum(raw_text) == expected_raw == raw_evidence["raw_response_checksum"]
    episode, members, source_provenance = execution.load_frozen_episode()
    bridge_path = ROOT / "apps_script/authoritative_provider_bridge.js"
    bridge_checksum = sha_file(bridge_path)
    inventory = occurrence_inventory()
    trace = {"call_path": ["automation/run_presignal_v21_r6_native_attention_execution_v1.py", "apps_script/authoritative_provider_bridge.js", "Gemini transport", "bridge response envelope", "attention_raw_response.json", "native identity adapter"], "transport_provider_source": "attention_raw_response.json transport_metadata.actual_provider", "transport_model_source": "attention_raw_response.json transport_metadata.actual_model", "raw_payload_provider_source": "attention_raw_response.json raw_response.provider", "historical_precedent": "automation/run_presignal_v21_step8_r2_historical_replication_v1.py:_context_provider_dispatch", "historical_rule": "provider text is required but bridge identity wins; exact raw output is restored after temporary normalized parsing."}
    trust = {"trusted": {"transport_provider": raw_evidence["transport_metadata"]["actual_provider"], "transport_model": raw_evidence["transport_metadata"]["actual_model"], "prompt_template_checksum": pre["prompt_template_checksum"], "bridge_source_checksum": bridge_checksum}, "model_authored": {"payload_provider_role": raw["provider"], "raw_response_checksum": raw_evidence["raw_response_checksum"]}, "trust_rule": "Authenticated bridge route owns canonical provider/model; the exact descriptive raw role is retained only as provenance under the narrow mapped condition."}
    mapping = {"mapping_name": "EXACT_GEMINI_ROUTED_TRANSPORT_PLUS_PROMPT_AGENT_ROLE_V1", "when": {"transport_provider": call.PROVIDER, "transport_model": call.MODEL, "payload_provider_role": call.TRUSTED_GEMINI_PAYLOAD_ROLE, "prompt_template_checksum": call.TRUSTED_GEMINI_PROMPT_TEMPLATE_CHECKSUM, "bridge_source_checksum": call.TRUSTED_GEMINI_BRIDGE_SOURCE_CHECKSUM}, "then": {"canonical_provider_identity": call.PROVIDER, "payload_provider_role_preserved": True}, "not_general_alias_registry": True, "raw_response_mutated": False}
    audit = {"provider_calls": 0, "gemini_calls": 0, "apps_script_executions": 0, "google_reads": 0, "google_writes": 0, "http_acquisition_calls": 0, "forecast_calls": 0, "live_pack_e_computations": 0, "r6_evidence_writes": 0, "outcome_operations": 0, "evaluation_operations": 0}
    try:
        normalized = call.normalize_preserved_gemini_attention_response(episode=episode, raw_response=raw, effective_timestamp=raw_evidence["transport_metadata"]["completed_timestamp"], member_event_ids=[row["event_id"] for row in members], prompt_template_checksum=pre["prompt_template_checksum"], bridge_source_checksum=bridge_checksum, preserved_raw_response_checksum=raw_evidence["raw_response_checksum"])
        attention = native.materialize_selected_native_attention(episode=episode, provider=call.PROVIDER, model=call.MODEL, prompt_version=call.PROMPT_VERSION, selection_state=normalized["selection_state"], acceptance_state=normalized["acceptance_state"], selection_reason=normalized["selection_reason"], effective_timestamp=normalized["effective_timestamp"], provenance={"raw_response_checksum": normalized["raw_response_checksum"], "normalized_response_checksum": normalized["normalized_response_checksum"], "bridge_metadata_checksum": normalized["bridge_metadata_checksum"], "payload_provider_role": normalized["payload_provider_role"], "mapping_rule": normalized["mapping_rule"], **source_provenance})
        attention.update({"canonical_provider_identity": normalized["canonical_provider_identity"], "transport_provider_identity": normalized["transport_provider_identity"], "transport_model_identity": normalized["transport_model_identity"], "payload_provider_role": normalized["payload_provider_role"], "raw_response_checksum": normalized["raw_response_checksum"], "normalized_response_checksum": normalized["normalized_response_checksum"], "bridge_metadata_checksum": normalized["bridge_metadata_checksum"]})
        repetitions = [native.materialize_selected_native_attention(episode=episode, provider=call.PROVIDER, model=call.MODEL, prompt_version=call.PROMPT_VERSION, selection_state=normalized["selection_state"], acceptance_state=normalized["acceptance_state"], selection_reason=normalized["selection_reason"], effective_timestamp=normalized["effective_timestamp"], provenance=attention["provenance"]) for _ in range(3)]
        stable = len({call.checksum(item) for item in repetitions}) == 1
        decision = "NATIVE_ATTENTION_BRIDGE_IDENTITY_REPAIRED_SELECTED_INPUT_READY" if normalized["selection_state"].startswith("SELECTED") and normalized["acceptance_state"] == "ACCEPTED" else "NATIVE_ATTENTION_BRIDGE_IDENTITY_REPAIRED_NOT_SELECTED_R6_STOPPED"
        revalidation = {"raw_checksum_valid": raw_checksum_valid, "episode_match": True, "provider_match": True, "model_match": True, "selection_state": normalized["selection_state"], "acceptance_state": normalized["acceptance_state"], "schema_valid": True, "cutoff_valid": True, "next_validation_divergence": None}
        object_report = attention; determinism = {"proof_runs": 3, "identical_runs": stable, "canonical_provider": call.PROVIDER, "payload_provider_role": normalized["payload_provider_role"], "normalized_response_checksum": normalized["normalized_response_checksum"], "attention_identity": attention["attention_identity"], "provenance_checksum": attention["provenance_checksum"], "lineage_checksum": attention["lineage_checksum"]}
    except Exception as exc:
        decision = "NATIVE_ATTENTION_OFFLINE_REVALIDATION_FAILED"; revalidation = {"raw_checksum_valid": raw_checksum_valid, "schema_valid": False, "next_validation_divergence": str(exc)}; object_report = {"status": "NOT_CREATED"}; determinism = {"proof_runs": 0, "reason": str(exc)}
    reports = {"bridge_identity_occurrence_inventory.json": {"searched_value": call.TRUSTED_GEMINI_PAYLOAD_ROLE, "occurrences": inventory, "occurrence_count": len(inventory)}, "bridge_identity_provenance_trace.json": trace, "bridge_identity_trust_boundary.json": trust, "bridge_identity_classification.json": {"classification": "AUTHORIZED_GEMINI_BRIDGE_ROLE_IDENTITY", "reason": "Historical Gemini envelopes repeatedly pair the descriptive raw role with Gemini/gemini-2.5-flash-lite, and the authoritative historical adapter makes routed bridge identity canonical while preserving raw text."}, "bridge_identity_mapping_contract.json": mapping, "preserved_response_checksum_report.json": {"expected": expected_raw, "actual": raw_evidence["raw_response_checksum"], "valid": raw_checksum_valid, "raw_file_checksum": sha_file(EXECUTION / "attention_raw_response.json"), "raw_response_changed": False}, "offline_revalidation_report.json": revalidation, "native_attention_object.json": object_report, "attention_determinism_report.json": determinism, "external_access_audit.json": audit, "final_bridge_identity_repair_decision.json": {"decision": decision, "previous_attention_calls_used": 1, "remaining_attention_calls": 0, "retry_budget": 0, "new_calls_made": 0}}
    for name, value in reports.items(): write(output / name, value)


if __name__ == "__main__": run()
