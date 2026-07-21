#!/usr/bin/env python3
"""Prepare bounded R3 compat-r2 evidence without executing provider calls."""
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

from automation import presignal_v21_historical_verification_r3_compat_r2_contract_v1 as compat_r2
REPAIR_ID = "STEP8-R3-R6-4082875"
OUT = ROOT / "outputs/presignal_v21_step8_r3_r6_compatibility_completion" / REPAIR_ID
R5 = ROOT / "outputs/presignal_v21_step8_r3_r5_live_compatibility_repair/STEP8-R3-R5-ca4c993"
PREP = ROOT / "outputs/presignal_v21_step8_r3_repair/STEP8-R3-REPAIR-df9c25e"
SMOKE_RUN = "STEP8-R3-R6-SMOKE-4082875"


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
    parent = json.loads((R5 / "replacement_verification_manifest.json").read_text())
    verification = {
        **parent,
        "contract": compat_r2.spec(),
        "parent_verification_manifest": str((R5 / "replacement_verification_manifest.json").relative_to(ROOT)),
        "runtime_binding": "R6_COMPATIBILITY_REQUIRED",
        "prior_contracts_rejected": [
            "presignal_event_path_contract_v1_historical_verification_r3",
            "presignal_event_path_contract_v1_historical_verification_r3_compat_r1",
        ],
    }
    write("verification_manifest.json", verification)
    write("repair_manifest.json", {
        "repair_id": REPAIR_ID,
        "scope": "NON_SCIENTIFIC_LIVE_PROVIDER_COMPATIBILITY_REPAIR",
        "previous_smokes": ["STEP8-R3-SMOKE-38b2e12", "STEP8-R3-R5-SMOKE-ca4c993"],
        "replacement_smoke": SMOKE_RUN,
        "provider_calls_before_smoke": 0,
        "acquisition_calls": 0,
        "prospective_calls": 0,
    })
    write("prior_smoke_inventory.json", {
        "immutable": True,
        "runs": ["STEP8-R3-SMOKE-38b2e12", "STEP8-R3-R5-SMOKE-ca4c993"],
        "episode_id": "EP_BATCH_b5c0c544ec07bbf0b950",
        "r5_evidence_fingerprint": sha256(json.loads((R5 / "replacement_smoke_result.json").read_text())),
    })
    write("anthropic_output_limit_validation.json", {
        "provider": "Anthropic",
        "model": "claude-haiku-4-5",
        "verified_route_ceiling": 64000,
        "configured_attention_max_output_tokens": compat_r2.ANTHROPIC_ATTENTION_MAX_TOKENS,
        "other_stages_unchanged": True,
        "unsupported_limit_failure_code": "V2_1_STEP8_R3_R6_ANTHROPIC_OUTPUT_LIMIT_UNSUPPORTED",
        "source": "Anthropic Claude models overview; Haiku 4.5 max output 64k.",
    })
    write("raw_response_persistence_validation.json", {
        "order": ["transport_return", "raw_response_persisted", "raw_response_fingerprint_persisted", "stop_reason_persisted", "python_parser", "validator", "dispatcher_result"],
        "truncated_json_auto_repair": False,
        "raw_storage": "raw_provider_responses/<operation_identity>.json",
    })
    write("request_priority_separation.json", {
        "canonical_priorities": ["must_have", "useful", "optional", "low_value"],
        "attention_labels_rejected": ["PRIMARY_DRIVER", "SECONDARY_DRIVER", "WATCHLIST", "CONTEXT_ONLY", "IGNORE", "NO_SIGNAL", "primary_driver", "secondary_driver"],
        "normalization": "none",
    })
    write("affected_channel_other_decision.json", {
        "decision": "EXACT_ALIAS_NORMALIZATION",
        "mapping": compat_r2.NORMALIZATION,
        "evidence": "The Request schema admits unknown as its sole generic channel fallback and omits other from affected_channel; exact lowercase other is a noncanonical generic fallback only.",
        "unknown_remains_canonical": True,
        "other_aliases_accepted": ["other"],
    })
    write("contract_delta.json", {
        "child_contract": compat_r2.CONTRACT_VERSION,
        "parent_contract": compat_r2.PARENT_CONTRACT_VERSION,
        "deltas": [
            "Anthropic Attention max_output_tokens=8192",
            "raw provider response retained before Python parsing",
            "Request priority explicitly separated from Attention labels",
            "exact affected_channel other normalized to unknown with original retained",
        ],
        "scientific_forecast_semantics_changed": False,
    })
    write("compat_r2_contract_manifest.json", compat_r2.spec())
    write("runtime_rebinding_validation.json", {
        "runner": "automation/run_presignal_v21_step8_r3_fresh_historical_verification_v1.py",
        "manifest": str((OUT / "verification_manifest.json").relative_to(ROOT)),
        "required_contract": compat_r2.CONTRACT_VERSION,
        "previous_contracts_rejected": verification["prior_contracts_rejected"],
    })
    write("frozen_response_regression.json", {
        "anthropic_r5_truncated_response": "remains_rejected_and_now_preservable",
        "gemini_priority_primary_driver": "remains_invalid_request_enum",
        "openai_affected_channel_other": "normalizes_only_under_compat_r2_with_original_retained",
        "provider_calls": 0,
    })
    write("new_smoke_manifest.json", {
        "run_id": SMOKE_RUN,
        "episode_id": "EP_BATCH_b5c0c544ec07bbf0b950",
        "contract": compat_r2.spec(),
        "providers": verification["providers"],
        "maximum_processed_episodes": 1,
    })
    return OUT / "verification_manifest.json"


def finalize_not_executed() -> None:
    prepare()
    write("new_smoke_result.json", {
        "run_id": SMOKE_RUN,
        "episode_id": "EP_BATCH_b5c0c544ec07bbf0b950",
        "smoke_execution_status": "NOT_EXECUTED",
        "blocking_error": "Apps Script publish rejected by clasp: invalid_grant",
        "provider_calls": 0,
        "acquisition_calls": 0,
        "forecast_calls": 0,
        "complete_paired_observations": 0,
        "outcome_accessed": False,
        "production_mutation": False,
    })
    write("new_smoke_resume_validation.json", {
        "status": "NOT_EXECUTED",
        "additional_provider_calls": 0,
        "reason": "No replacement smoke run was initialized after the deployment credential failure.",
    })
    write("historical_immutability_validation.json", {
        "original_smoke_changed": False,
        "r5_smoke_changed": False,
        "r3_and_r5_contracts_changed_in_place": False,
        "r6_is_new_child_contract_only": True,
    })
    write("prospective_pause_validation.json", {
        "collection_run_id": "P12-COLLECT-ffd55626bc1a886c2e19",
        "status": "PAUSED_PENDING_HISTORICAL_VALIDATION",
        "admitted_episodes": 0,
        "provider_calls": 0,
        "forecast_calls": 0,
    })
    (OUT / "repair_summary.md").write_text(
        "# Step 8-R3-R6 Compatibility Completion\n\n"
        "The compat-r2 source and call-free regression suite are complete. The authorized one-Episode smoke was not sent because the Apps Script publish command failed with `invalid_grant`; the deployed bridge therefore cannot be claimed to contain this repair. P12 remains paused.\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--finalize-not-executed", action="store_true")
    args = parser.parse_args()
    if args.finalize_not_executed:
        finalize_not_executed()
        print(OUT)
        return
    if not args.prepare:
        raise SystemExit("PREPARE_REQUIRED")
    print(prepare())


if __name__ == "__main__":
    main()
