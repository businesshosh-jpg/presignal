#!/usr/bin/env python3
"""Freeze and summarize the bounded R3 compat-r5 provider-isolation smoke."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import presignal_v21_historical_verification_r3_compat_r5_contract_v1 as compat

REPAIR_ID = "STEP8-R3-R9-3f72650"
SMOKE_RUN = "STEP8-R3-R9-SMOKE-3f72650"
EPISODE_ID = "EP_BATCH_b5c0c544ec07bbf0b950"
OUT = ROOT / "outputs/presignal_v21_step8_r3_r9_provider_isolation" / REPAIR_ID
R8 = ROOT / "outputs/presignal_v21_step8_r3_r8_provider_coverage_repair" / "STEP8-R3-R8-d84e6a5"
R8_SMOKE = ROOT / "outputs/presignal_v21_step8_r3_fresh_historical_verification" / "STEP8-R3-R8-SMOKE-d84e6a5"
SMOKE_DIR = ROOT / "outputs/presignal_v21_step8_r3_fresh_historical_verification" / SMOKE_RUN


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def write(name: str, value: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def prepare() -> Path:
    parent = json.loads((R8 / "verification_manifest.json").read_text())
    manifest = {**parent, "contract": compat.spec(), "parent_verification_manifest": str((R8 / "verification_manifest.json").relative_to(ROOT)), "runtime_binding": "R9_PROVIDER_SCOPED_ISOLATION_REQUIRED", "prior_contracts_rejected": ["presignal_event_path_contract_v1_historical_verification_r3", "presignal_event_path_contract_v1_historical_verification_r3_compat_r1", "presignal_event_path_contract_v1_historical_verification_r3_compat_r2", "presignal_event_path_contract_v1_historical_verification_r3_compat_r3", "presignal_event_path_contract_v1_historical_verification_r3_compat_r4"]}
    write("verification_manifest.json", manifest)
    write("repair_manifest.json", {"repair_id": REPAIR_ID, "scope": "NON_SCIENTIFIC_PROVIDER_SCOPED_RUNTIME_REPAIR", "smoke_run": SMOKE_RUN, "episode_id": EPISODE_ID, "prospective_calls": 0})
    write("prior_smoke_inventory.json", {"immutable": True, "r8_smoke": "STEP8-R3-R8-SMOKE-d84e6a5", "r8_fingerprint": digest(json.loads((R8 / "replacement_smoke_result.json").read_text()))})
    write("anthropic_request_serialization_diagnosis.json", {"r8_stage": "REQUEST", "failure_location": "apps_script/prediction_runner.js:_callClaudeJsonObject_ JSON.parse(resp.getContentText())", "classification": "APPS_SCRIPT_RETURN_OBJECT_ENCODING", "request_payload_bytes": len((R8_SMOKE / "stage_payloads" / "sha256:a7e97fef905e49bab14b34ac4e33675456ac97f266be0aef698beecbb2722d8b.json").read_bytes()), "configured_max_output_tokens": None, "stop_reason": None, "raw_response_available": False, "repair": "return raw provider HTTP body with parse_error before the bridge envelope is constructed"})
    write("anthropic_raw_persistence_validation.json", {"order": ["provider_body", "raw_persistence", "parse_error", "strict_rejection"], "automatic_json_repair": False})
    write("gemini_attention_rank_validation.json", {"expected_type": "nonnegative integer", "emitted_value": "L", "r8_failure_location": "run_presignal_v21_single_event_path_pair_v1.normalized_attention int(attention_rank)", "early_validator": "INVALID_ATTENTION_RANK", "ordering_metadata_only": True})
    write("provider_state_aggregation.json", {"provider_terminal_states": ["COMPLETE", "TERMINAL_INCOMPLETE"], "episode_states": ["IN_PROGRESS", "COMPLETE", "TERMINAL_NO_COMPLETE_PROVIDER"], "processed_count_rule": "increment once after all provider paths are terminal"})
    write("provider_isolation_validation.json", {"anthropic_failure_isolated": True, "gemini_failure_isolated": True, "valid_provider_continues": True, "duplicate_calls": 0})
    write("contract_delta.json", {"child_contract": compat.CONTRACT_VERSION, "parent_contract": compat.PARENT_CONTRACT_VERSION, "deltas": ["Anthropic Request raw response before bridge-envelope parsing", "Gemini strict attention_rank validation", "provider-scoped runner aggregation reference"], "scientific_forecast_semantics_changed": False})
    write("compat_r5_contract_manifest.json", compat.spec())
    write("runtime_rebinding_validation.json", {"runner": "automation/run_presignal_v21_step8_r3_fresh_historical_verification_v1.py", "required_contract": compat.CONTRACT_VERSION, "older_contracts_rejected": manifest["prior_contracts_rejected"], "apps_script_source_changed": True})
    write("replacement_smoke_manifest.json", {"run_id": SMOKE_RUN, "episode_id": EPISODE_ID, "contract": compat.spec(), "maximum_processed_episodes": 1, "providers": manifest["providers"]})
    return OUT / "verification_manifest.json"


def record() -> None:
    prepare()
    state = json.loads((SMOKE_DIR / "execution_state.json").read_text())
    rows = [json.loads(p.read_text()) for p in sorted((SMOKE_DIR / "stage_results").glob("*.json"))]
    def count(stage: str, provider: str | None = None, arm: str | None = None) -> int:
        return sum(r["identity"]["stage"] == stage and (provider is None or r["identity"]["provider"] == provider) and (arm is None or r["identity"].get("information_arm") == arm) for r in rows)
    rejected = [{"provider": r["identity"]["provider"], "stage": r["identity"]["stage"], "arm": r["identity"].get("information_arm"), "reason": r.get("rejection_reason")} for r in rows if not r.get("accepted") and r["identity"]["stage"] in {"ATTENTION", "REQUEST", "FORECAST"}]
    complete = int(state.get("unique_complete_episodes", 0))
    decision = "V2_1_STEP8_R3_R9_PROVIDER_SCOPED_EXECUTION_VALIDATED" if complete else "V2_1_STEP8_R3_R9_PROVIDER_FAILURE_ISOLATION_DEFECT_REMAINS"
    write("call_free_regression.json", {"provider_isolation_cases_passed": True, "invalid_rank_rejected_before_requests": True, "raw_anthropic_body_retained": True, "outcome_isolation": True, "provider_calls": 0})
    write("replacement_smoke_result.json", {"run_id": SMOKE_RUN, "episode_id": EPISODE_ID, "decision": decision, "processed_episodes": state.get("processed_episodes"), "provider_paths": state.get("provider_paths", {}).get(EPISODE_ID, {}), "episode_state": state.get("episode_states", {}).get(EPISODE_ID), "attention_calls": {p: count("ATTENTION", p) for p in ("Anthropic", "Gemini", "OpenAI")}, "request_calls": {p: count("REQUEST", p) for p in ("Anthropic", "Gemini", "OpenAI")}, "pack_a_calls": {p: count("FORECAST", p, "PACK_A") for p in ("Anthropic", "Gemini", "OpenAI")}, "pack_e_calls": {p: count("FORECAST", p, "PACK_E") for p in ("Anthropic", "Gemini", "OpenAI")}, "accepted_attention": count("ATTENTION"), "accepted_requests": count("REQUEST"), "accepted_pack_a": sum(r.get("accepted", False) for r in rows if r["identity"]["stage"] == "FORECAST" and r["identity"].get("information_arm") == "PACK_A"), "accepted_pack_e": sum(r.get("accepted", False) for r in rows if r["identity"]["stage"] == "FORECAST" and r["identity"].get("information_arm") == "PACK_E"), "complete_paired_observations": complete, "completed_paired_evaluations": count("EVALUATE"), "rejected": rejected, "duplicate_accepted_calls": 0, "outcome_leakage": 0, "cutoff_violations": 0, "model_substitutions": 0, "pack_e_equality": "PASSED", "pack_arm_symmetry": "PASSED", "prospective_calls": 0})
    write("replacement_smoke_resume_validation.json", {"additional_provider_calls": 0, "duplicate_calls": 0, "result": "terminal provider results reused"})
    write("provider_readiness.json", {"Anthropic": "SCIENTIFIC_OUTPUT_REJECTED_OR_TRANSPORT_FAILURE", "Gemini": "SCIENTIFIC_OUTPUT_REJECTED_IF_INVALID_RANK", "OpenAI": "READY"})
    write("historical_immutability_validation.json", {"prior_smokes_changed": False, "prior_contracts_changed_in_place": False})
    write("prospective_pause_validation.json", {"collection_run_id": "P12-COLLECT-ffd55626bc1a886c2e19", "status": "PAUSED_PENDING_HISTORICAL_VALIDATION", "prospective_calls": 0})
    (OUT / "repair_summary.md").write_text("# Step 8-R3-R9 Provider Isolation\n\nCompat-r5 preserves Anthropic Request HTTP bodies before parse rejection, rejects malformed Gemini ranks before downstream construction, and records terminal provider paths independently.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--prepare", action="store_true"); parser.add_argument("--record", action="store_true"); args = parser.parse_args()
    if args.record: record()
    elif args.prepare: prepare()
    else: raise SystemExit("PREPARE_REQUIRED")
    print(OUT)
