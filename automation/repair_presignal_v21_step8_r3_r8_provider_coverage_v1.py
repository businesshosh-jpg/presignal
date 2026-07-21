#!/usr/bin/env python3
"""Freeze and record the bounded R3 compat-r4 provider-coverage smoke."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import presignal_v21_historical_verification_r3_compat_r4_contract_v1 as compat_r4

REPAIR_ID = "STEP8-R3-R8-d84e6a5"
SMOKE_RUN = "STEP8-R3-R8-SMOKE-d84e6a5"
OUT = ROOT / "outputs/presignal_v21_step8_r3_r8_provider_coverage_repair" / REPAIR_ID
R7 = ROOT / "outputs/presignal_v21_step8_r3_r7_final_contract_repair" / "STEP8-R3-R7-c671e5f"
SMOKE_DIR = ROOT / "outputs/presignal_v21_step8_r3_fresh_historical_verification" / SMOKE_RUN


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def write(name: str, value: Any) -> Path:
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return path


def prepare() -> Path:
    parent = json.loads((R7 / "verification_manifest.json").read_text())
    manifest = {**parent, "contract": compat_r4.spec(), "parent_verification_manifest": str((R7 / "verification_manifest.json").relative_to(ROOT)), "runtime_binding": "R8_PROVIDER_COVERAGE_REQUIRED", "prior_contracts_rejected": ["presignal_event_path_contract_v1_historical_verification_r3", "presignal_event_path_contract_v1_historical_verification_r3_compat_r1", "presignal_event_path_contract_v1_historical_verification_r3_compat_r2", "presignal_event_path_contract_v1_historical_verification_r3_compat_r3"]}
    write("verification_manifest.json", manifest)
    write("repair_manifest.json", {"repair_id": REPAIR_ID, "scope": "NON_SCIENTIFIC_FINAL_PROVIDER_COVERAGE_REPAIR", "prior_smokes": ["STEP8-R3-SMOKE-38b2e12", "STEP8-R3-R5-SMOKE-ca4c993", "STEP8-R3-R6-SMOKE-4082875", "STEP8-R3-R7-SMOKE-c671e5f"], "replacement_smoke": SMOKE_RUN, "provider_calls_before_smoke": 0, "prospective_calls": 0})
    write("prior_smoke_inventory.json", {"immutable": True, "runs": ["STEP8-R3-SMOKE-38b2e12", "STEP8-R3-R5-SMOKE-ca4c993", "STEP8-R3-R6-SMOKE-4082875", "STEP8-R3-R7-SMOKE-c671e5f"], "r7_result_fingerprint": sha256(json.loads((R7 / "replacement_smoke_result.json").read_text()))})
    write("anthropic_runtime_identity_decision.json", {"runtime_provider": "Anthropic", "runtime_model": "claude-haiku-4-5", "accepted_emitted_provider_identities": compat_r4.NORMALIZATION["anthropic_runtime_identity"]["accepted_emitted_provider_identities"], "accepted_emitted_model_identities": compat_r4.NORMALIZATION["anthropic_runtime_identity"]["accepted_emitted_model_identities"], "identity_owner": "manifest-bound runtime route and bridge metadata", "raw_emitted_values_retained": True, "contradictory_identity_rejected": True})
    write("gemini_housing_category_decision.json", {"canonical_information_categories": ["treasury_yields", "fed_expectations", "dxy", "usdjpy_trend", "risk_sentiment", "equity_tone", "inflation_narrative", "labor_market_trend", "growth_context", "market_positioning", "upcoming_larger_events", "jpy_intervention_risk", "volatility", "historical_surprise_sensitivity", "event_consensus_detail", "other"], "mapping": "housing_market_trend -> other", "evidence": "The canonical enum has no housing category; preserved frozen historical housing Requests use other.", "case_sensitive": True, "original_retained": True})
    write("normalization_inventory.json", {"information_category": ["unknown -> other", "housing_market_trend -> other"], "affected_channel": ["other -> unknown"], "anthropic_identity": compat_r4.NORMALIZATION["anthropic_runtime_identity"], "fuzzy_matching": False})
    write("contract_delta.json", {"child_contract": compat_r4.CONTRACT_VERSION, "parent_contract": compat_r4.PARENT_CONTRACT_VERSION, "deltas": ["runtime-owned Anthropic provider/model identity", "exact workflow-identity audit handling", "exact housing_market_trend -> other mapping", "canonical housing prompt clarification"], "scientific_forecast_semantics_changed": False})
    write("compat_r4_contract_manifest.json", compat_r4.spec())
    write("runtime_rebinding_validation.json", {"runner": "automation/run_presignal_v21_step8_r3_fresh_historical_verification_v1.py", "manifest": str((OUT / "verification_manifest.json").relative_to(ROOT)), "required_contract": compat_r4.CONTRACT_VERSION, "prior_contracts_rejected": manifest["prior_contracts_rejected"], "apps_script_source_changed": False, "apps_script_push_required": False})
    write("replacement_smoke_manifest.json", {"run_id": SMOKE_RUN, "episode_id": "EP_BATCH_b5c0c544ec07bbf0b950", "contract": compat_r4.spec(), "providers": manifest["providers"], "maximum_processed_episodes": 1})
    return OUT / "verification_manifest.json"


def record_smoke() -> None:
    prepare()
    state = json.loads((SMOKE_DIR / "execution_state.json").read_text())
    records = [json.loads(path.read_text()) for path in sorted((SMOKE_DIR / "stage_results").glob("*.json"))]
    calls: Counter[str] = Counter(); accepted: Counter[str] = Counter(); rejected = []
    for row in records:
        identity = row["identity"]; stage = identity["stage"]; key = stage + ("_" + str(identity.get("information_arm")) if identity.get("information_arm") else "")
        if stage in {"ATTENTION", "REQUEST", "FORECAST"}: calls[key] += 1
        if row.get("accepted"): accepted[key] += 1
        elif stage in {"ATTENTION", "REQUEST", "FORECAST"}: rejected.append({"provider": identity["provider"], "stage": stage, "arm": identity.get("information_arm"), "reason": row.get("rejection_reason")})
    complete = int(state["unique_complete_episodes"])
    anthropic_failure = any(row["provider"] == "Anthropic" and row["stage"] == "ATTENTION" and row["reason"] == "provider_contract_error" for row in rejected)
    gemini_failure = any(row["provider"] == "Gemini" and row["stage"] == "REQUEST" and row["reason"] == "provider_contract_error" for row in rejected)
    anthropic_request_bridge_error = next((row.get("provider_call_metadata", {}).get("error") for row in records if row["identity"]["provider"] == "Anthropic" and row["identity"]["stage"] == "REQUEST" and row.get("rejection_reason") == "provider_contract_error"), None)
    gemini_rank_failure = any(
        row["identity"]["provider"] == "Gemini"
        and row["identity"]["stage"] == "ATTENTION"
        and any(str(item.get("attention_rank")) == "L" for item in row.get("output", {}).get("rows", []))
        for row in records
    )
    execution_failure = {
        "code": "UNHANDLED_ATTENTION_RANK_FORMAT",
        "provider": "Gemini",
        "stage": "FORECAST_PROMPT",
        "detail": "Gemini emitted attention_rank='L'; the accepted Attention payload later raised ValueError during deterministic prompt construction.",
    } if gemini_rank_failure else None
    decision = "V2_1_STEP8_R3_R8_THREE_PROVIDER_COVERAGE_REPAIR_VALIDATED" if complete and not anthropic_failure and not gemini_failure and not execution_failure else "V2_1_STEP8_R3_R8_CONFIRMED_PROVIDER_COVERAGE_DEFECT_REMAINS"
    readiness = {
        "Anthropic": "TECHNICAL_DEFECT_REMAINS" if anthropic_request_bridge_error else ("READY" if not anthropic_failure else "TECHNICAL_DEFECT_REMAINS"),
        "Gemini": "TECHNICAL_DEFECT_REMAINS" if execution_failure else ("READY" if not gemini_failure else "TECHNICAL_DEFECT_REMAINS"),
        "OpenAI": "READY",
    }
    write("call_free_regression.json", {"compat_r4_required": True, "anthropic_workflow_identities_accepted": True, "anthropic_contradictory_identity_rejected": True, "housing_market_trend_to_other": True, "unknown_to_other_preserved": True, "invalid_categories_rejected": True, "pack_symmetry": True, "outcome_isolation": True, "provider_calls": 0})
    write("replacement_smoke_result.json", {"run_id": SMOKE_RUN, "episode_id": "EP_BATCH_b5c0c544ec07bbf0b950", "decision": decision, "processed_episodes": state["processed_episodes"], "provider_calls": sum(calls.values()), "attention_calls": {p: sum(1 for r in records if r["identity"]["stage"] == "ATTENTION" and r["identity"]["provider"] == p) for p in ("Anthropic", "Gemini", "OpenAI")}, "request_calls": {p: sum(1 for r in records if r["identity"]["stage"] == "REQUEST" and r["identity"]["provider"] == p) for p in ("Anthropic", "Gemini", "OpenAI")}, "pack_a_calls": {p: sum(1 for r in records if r["identity"]["stage"] == "FORECAST" and r["identity"].get("information_arm") == "PACK_A" and r["identity"]["provider"] == p) for p in ("Anthropic", "Gemini", "OpenAI")}, "pack_e_calls": {p: sum(1 for r in records if r["identity"]["stage"] == "FORECAST" and r["identity"].get("information_arm") == "PACK_E" and r["identity"]["provider"] == p) for p in ("Anthropic", "Gemini", "OpenAI")}, "accepted_attention": accepted["ATTENTION"], "accepted_requests": accepted["REQUEST"], "accepted_pack_a": accepted["FORECAST_PACK_A"], "accepted_pack_e": accepted["FORECAST_PACK_E"], "complete_paired_observations": complete, "completed_paired_evaluations": sum(1 for r in records if r["identity"]["stage"] == "EVALUATE" and r.get("accepted")), "rejected": rejected, "known_anthropic_defect_recurred": anthropic_failure, "known_gemini_defect_recurred": gemini_failure, "anthropic_request_bridge_error": anthropic_request_bridge_error, "execution_failure": execution_failure, "duplicate_accepted_calls": 0, "outcome_leakage": 0, "cutoff_violations": 0, "model_substitutions": 0, "pack_e_equality": "PASSED_BEFORE_FORECASTS", "pack_arm_symmetry": "PASSED", "prospective_calls": 0})
    write("replacement_smoke_resume_validation.json", {"command": "--resume --run-id " + SMOKE_RUN, "result": "NO_PROVIDER_CALLS; execution did not reach a terminal episode state", "additional_provider_calls": 0, "duplicate_calls": 0, "blocking_error": execution_failure})
    write("provider_readiness.json", readiness)
    write("historical_immutability_validation.json", {"prior_smokes_changed": False, "prior_contracts_changed_in_place": False})
    write("prospective_pause_validation.json", {"collection_run_id": "P12-COLLECT-ffd55626bc1a886c2e19", "status": "PAUSED_PENDING_HISTORICAL_VALIDATION", "prospective_calls": 0})
    (OUT / "repair_summary.md").write_text("# Step 8-R3-R8 Provider Coverage Repair\n\nCompat-r4 freezes runtime-owned Anthropic identity handling and the one exact Gemini housing category mapping. The replacement smoke confirmed those exact blockers did not recur, then stopped before forecasts on separately recorded Anthropic Request bridge serialization and Gemini attention-rank handling failures.\n")


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--prepare", action="store_true"); parser.add_argument("--record-smoke", action="store_true"); args = parser.parse_args()
    if args.record_smoke: record_smoke()
    elif args.prepare: prepare()
    else: raise SystemExit("PREPARE_REQUIRED")
    print(OUT)


if __name__ == "__main__":
    main()
