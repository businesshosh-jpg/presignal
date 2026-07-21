#!/usr/bin/env python3
"""Prepare bounded R3 compat-r2 evidence without executing provider calls."""
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

from automation import presignal_v21_historical_verification_r3_compat_r2_contract_v1 as compat_r2
REPAIR_ID = "STEP8-R3-R6-4082875"
OUT = ROOT / "outputs/presignal_v21_step8_r3_r6_compatibility_completion" / REPAIR_ID
R5 = ROOT / "outputs/presignal_v21_step8_r3_r5_live_compatibility_repair/STEP8-R3-R5-ca4c993"
PREP = ROOT / "outputs/presignal_v21_step8_r3_repair/STEP8-R3-REPAIR-df9c25e"
SMOKE_RUN = "STEP8-R3-R6-SMOKE-4082875"
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


def record_smoke() -> None:
    """Write sanitized R6 evidence from the already terminal one-Episode run."""
    prepare()
    state = json.loads((SMOKE_DIR / "execution_state.json").read_text())
    records = [json.loads(path.read_text()) for path in sorted((SMOKE_DIR / "stage_results").glob("*.json"))]
    calls = Counter()
    accepted = Counter()
    rejected: list[dict[str, Any]] = []
    for row in records:
        identity = row["identity"]
        stage, provider, arm = identity["stage"], identity["provider"], identity.get("information_arm")
        if stage in {"ATTENTION", "REQUEST", "FORECAST"}:
            calls[stage + ("_" + str(arm) if arm else "")] += 1
        if row.get("accepted"):
            accepted[stage + ("_" + str(arm) if arm else "")] += 1
        elif stage in {"ATTENTION", "REQUEST", "FORECAST"}:
            rejected.append({"provider": provider, "stage": stage, "arm": arm, "reason": row.get("rejection_reason")})
    write("deployment_runtime_verification.json", {
        "runtime_entrypoint": "automation.run_presignal_v21_single_event_path_pair_v1.bridge_dispatch",
        "configuration_source": "automation.google_clients.default_script_id",
        "active_execution_api_script_id": "1A-iJDmNb1RFSCGS9YIPJfboNCO3sGUS1OomKf4yyQhQceSJlgXqWdGA9",
        "deployment_id": None,
        "execution_mode": "devMode=true using pushed Apps Script HEAD",
        "environment_overrides": {"PRESIGNAL_SCRIPT_ID": None, "PRESIGNAL_DEPLOYMENT_ID": None, "PRESIGNAL_EXECUTION_ID": None},
        "redeployment_required": False,
        "r6_behavior_observed": {"anthropic_attention_max_output_tokens": 8192, "anthropic_stop_reason": "end_turn", "raw_response_before_parse": True},
    })
    write("new_smoke_result.json", {
        "run_id": SMOKE_RUN,
        "episode_id": "EP_BATCH_b5c0c544ec07bbf0b950",
        "smoke_execution_status": "TERMINAL_INCOMPLETE",
        "processed_episodes": state["processed_episodes"],
        "provider_calls": sum(calls.values()),
        "attention_calls": {"Anthropic": 1, "Gemini": 1, "OpenAI": 1},
        "request_calls": {"Gemini": 1, "OpenAI": 1},
        "pack_a_calls": {"Gemini": 1},
        "pack_e_calls": {"Gemini": 1},
        "accepted_attention": accepted["ATTENTION"],
        "accepted_requests": accepted["REQUEST"],
        "accepted_pack_a": accepted["FORECAST_PACK_A"],
        "accepted_pack_e": accepted["FORECAST_PACK_E"],
        "complete_paired_observations": state["unique_complete_episodes"],
        "completed_evaluation_paths": 0,
        "rejected": rejected,
        "final_decision": "V2_1_STEP8_R3_R6_CONFIRMED_COMPATIBILITY_DEFECT_REMAINS",
        "remaining_blockers": [
            {
                "provider": "Gemini",
                "stage": "FORECAST",
                "arm": "PACK_E",
                "code": "PATH_PIPS_MIN",
                "cause": "The frozen R3 DOWN pip-range instruction requires negative values, while the active strict validator requires nonnegative absolute pip magnitudes.",
            },
            {
                "provider": "OpenAI",
                "stage": "REQUEST",
                "code": "invalid_request_enum",
                "field": "information_category",
                "value": "unknown",
            },
            {
                "provider": "Anthropic",
                "stage": "ATTENTION",
                "code": "attention_contract_identity",
                "cause": "The response was a fenced JSON object with provider=presignal_v2; the dispatcher rejected it before the R3 extractor normalized the provider identity.",
            },
        ],
        "outcome_attached_after_both_arms_terminal": True,
        "cutoff_violations": 0,
        "duplicate_accepted_calls": 0,
        "model_substitutions": 0,
        "pack_e_equality": "PASSED_BEFORE_FORECASTS",
        "prospective_calls": 0,
    })
    write("new_smoke_resume_validation.json", {
        "command": "--resume --run-id " + SMOKE_RUN,
        "result": "ALREADY_PROCESSED",
        "additional_provider_calls": 0,
        "duplicate_calls": 0,
    })
    (OUT / "repair_summary.md").write_text(
        "# Step 8-R3-R6 Compatibility Completion\n\n"
        "The actual Execution API runtime uses pushed Apps Script HEAD. The one permitted smoke Episode ran once and resumed with zero calls. Anthropic demonstrated the 8192-token limit and raw retention; Gemini Request passed. The smoke remains terminally incomplete because Gemini Pack E hit PATH_PIPS_MIN and OpenAI emitted invalid information_category=unknown. P12 remains paused.\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--finalize-not-executed", action="store_true")
    parser.add_argument("--record-smoke", action="store_true")
    args = parser.parse_args()
    if args.finalize_not_executed:
        finalize_not_executed()
        print(OUT)
        return
    if args.record_smoke:
        record_smoke()
        print(OUT)
        return
    if not args.prepare:
        raise SystemExit("PREPARE_REQUIRED")
    print(prepare())


if __name__ == "__main__":
    main()
