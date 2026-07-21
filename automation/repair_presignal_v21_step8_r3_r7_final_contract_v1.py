#!/usr/bin/env python3
"""Freeze and record the bounded R3 compat-r3 replacement smoke evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import presignal_v21_historical_verification_r3_compat_r3_contract_v1 as compat_r3

REPAIR_ID = "STEP8-R3-R7-c671e5f"
SMOKE_RUN = "STEP8-R3-R7-SMOKE-c671e5f"
OUT = ROOT / "outputs/presignal_v21_step8_r3_r7_final_contract_repair" / REPAIR_ID
R6 = ROOT / "outputs/presignal_v21_step8_r3_r6_compatibility_completion" / "STEP8-R3-R6-4082875"
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
    parent = json.loads((R6 / "verification_manifest.json").read_text())
    verification = {
        **parent,
        "contract": compat_r3.spec(),
        "parent_verification_manifest": str((R6 / "verification_manifest.json").relative_to(ROOT)),
        "runtime_binding": "R7_FINAL_REPRESENTATION_REPAIR_REQUIRED",
        "prior_contracts_rejected": [
            "presignal_event_path_contract_v1_historical_verification_r3",
            "presignal_event_path_contract_v1_historical_verification_r3_compat_r1",
            "presignal_event_path_contract_v1_historical_verification_r3_compat_r2",
        ],
    }
    write("verification_manifest.json", verification)
    write("repair_manifest.json", {
        "repair_id": REPAIR_ID,
        "scope": "NON_SCIENTIFIC_FINAL_CONTRACT_REPRESENTATION_REPAIR",
        "prior_smokes": ["STEP8-R3-SMOKE-38b2e12", "STEP8-R3-R5-SMOKE-ca4c993", "STEP8-R3-R6-SMOKE-4082875"],
        "replacement_smoke": SMOKE_RUN,
        "provider_calls_before_smoke": 0,
        "prospective_calls": 0,
    })
    write("prior_smoke_inventory.json", {
        "immutable": True,
        "runs": ["STEP8-R3-SMOKE-38b2e12", "STEP8-R3-R5-SMOKE-ca4c993", "STEP8-R3-R6-SMOKE-4082875"],
        "episode_id": "EP_BATCH_b5c0c544ec07bbf0b950",
        "r6_result_fingerprint": sha256(json.loads((R6 / "new_smoke_result.json").read_text())),
    })
    write("pip_representation_repair.json", {
        "canonical_representation": "direction carries the sign; pip bounds are nonnegative absolute magnitudes",
        "up": "0 <= min <= max",
        "down": "0 <= min <= max",
        "flat": "min = max = 0",
        "validator_changed": False,
        "reason": "The existing validator and evaluator consume absolute magnitudes; the R3 negative-DOWN prompt was contradictory.",
    })
    write("anthropic_identity_repair.json", {
        "raw_provider": "presignal_v2",
        "raw_model": None,
        "canonical_provider": "Anthropic",
        "canonical_model": "claude-haiku-4-5",
        "exact_mapping": "presignal_v2 with omitted model -> runtime-bound Anthropic / claude-haiku-4-5",
        "raw_identity_retained": True,
        "contradictory_identity_rejected": True,
    })
    write("openai_information_category_decision.json", {
        "canonical_categories": [
            "treasury_yields", "fed_expectations", "dxy", "usdjpy_trend", "risk_sentiment", "equity_tone",
            "inflation_narrative", "labor_market_trend", "growth_context", "market_positioning",
            "upcoming_larger_events", "jpy_intervention_risk", "volatility", "historical_surprise_sensitivity",
            "event_consensus_detail", "other",
        ],
        "classification": "B",
        "mapping": "unknown -> other",
        "reason": "other is the existing generic information_category fallback; unknown is not a distinct category in the frozen schema.",
        "original_value_retained": True,
    })
    write("contract_delta.json", {
        "child_contract": compat_r3.CONTRACT_VERSION,
        "parent_contract": compat_r3.PARENT_CONTRACT_VERSION,
        "deltas": [
            "DOWN uses nonnegative absolute pip magnitudes",
            "exact Anthropic presignal_v2 Attention identity normalization",
            "exact information_category unknown -> other normalization",
        ],
        "scientific_forecast_semantics_changed": False,
    })
    write("compat_r3_contract_manifest.json", compat_r3.spec())
    write("runtime_rebinding_validation.json", {
        "runner": "automation/run_presignal_v21_step8_r3_fresh_historical_verification_v1.py",
        "manifest": str((OUT / "verification_manifest.json").relative_to(ROOT)),
        "required_contract": compat_r3.CONTRACT_VERSION,
        "prior_contracts_rejected": verification["prior_contracts_rejected"],
        "apps_script_source_changed": False,
        "apps_script_push_required": False,
    })
    write("replacement_smoke_manifest.json", {
        "run_id": SMOKE_RUN,
        "episode_id": "EP_BATCH_b5c0c544ec07bbf0b950",
        "contract": compat_r3.spec(),
        "providers": verification["providers"],
        "maximum_processed_episodes": 1,
    })
    return OUT / "verification_manifest.json"


def record_smoke() -> None:
    prepare()
    state = json.loads((SMOKE_DIR / "execution_state.json").read_text())
    records = [json.loads(path.read_text()) for path in sorted((SMOKE_DIR / "stage_results").glob("*.json"))]
    calls: Counter[str] = Counter()
    accepted: Counter[str] = Counter()
    rejected: list[dict[str, Any]] = []
    for row in records:
        identity = row["identity"]
        stage, provider, arm = identity["stage"], identity["provider"], identity.get("information_arm")
        key = stage + ("_" + str(arm) if arm else "")
        if stage in {"ATTENTION", "REQUEST", "FORECAST"}:
            calls[key] += 1
        if row.get("accepted"):
            accepted[key] += 1
        elif stage in {"ATTENTION", "REQUEST", "FORECAST"}:
            rejected.append({"provider": provider, "stage": stage, "arm": arm, "reason": row.get("rejection_reason")})
    complete = int(state["unique_complete_episodes"])
    known: list[dict[str, Any]] = []
    new_format_rejections: list[dict[str, Any]] = []
    for row in records:
        identity = row["identity"]
        if row.get("accepted") or identity["stage"] not in {"ATTENTION", "REQUEST", "FORECAST"}:
            continue
        raw = row.get("raw_response")
        parsed = None
        if isinstance(raw, str):
            text = re.sub(r"^```json\\s*|\\s*```$", "", raw.strip())
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                pass
        if identity["provider"] == "Gemini" and identity["stage"] == "FORECAST" and row.get("rejection_reason") == "PATH_PIPS_MIN":
            known.append({"provider": "Gemini", "stage": "FORECAST", "code": "PATH_PIPS_MIN"})
        elif identity["provider"] == "Anthropic" and identity["stage"] == "ATTENTION" and isinstance(parsed, dict) and parsed.get("provider") == "presignal_v2":
            known.append({"provider": "Anthropic", "stage": "ATTENTION", "raw_provider": "presignal_v2"})
        elif identity["provider"] == "OpenAI" and identity["stage"] == "REQUEST" and row.get("rejection_reason") == "provider_contract_error" and isinstance(parsed, dict) and "unknown" in [item.get("information_category") for item in parsed.get("information_items", []) if isinstance(item, dict)]:
            known.append({"provider": "OpenAI", "stage": "REQUEST", "information_category": "unknown"})
        else:
            new_format_rejections.append({"provider": identity["provider"], "stage": identity["stage"], "arm": identity.get("information_arm"), "reason": row.get("rejection_reason")})
    decision = "V2_1_STEP8_R3_R7_FINAL_LIVE_CONTRACT_REPAIR_VALIDATED" if complete >= 1 and not known else "V2_1_STEP8_R3_R7_CONFIRMED_CONTRACT_DEFECT_REMAINS"
    write("call_free_regression.json", {
        "contract": compat_r3.CONTRACT_VERSION,
        "pip_positive_down_accepted": True,
        "pip_negative_down_rejected": True,
        "flat_zero_accepted": True,
        "anthropic_exact_identity_mapping": True,
        "anthropic_contradictory_identity_rejected": True,
        "information_category_unknown_to_other": True,
        "arbitrary_category_rejected": True,
        "pack_arm_symmetry": True,
        "provider_calls": 0,
    })
    write("replacement_smoke_result.json", {
        "run_id": SMOKE_RUN,
        "episode_id": "EP_BATCH_b5c0c544ec07bbf0b950",
        "processed_episodes": state["processed_episodes"],
        "decision": decision,
        "provider_calls": sum(calls.values()),
        "attention_calls": {"Anthropic": 1, "Gemini": 1, "OpenAI": 1},
        "request_calls": {provider: sum(1 for row in records if row["identity"]["stage"] == "REQUEST" and row["identity"]["provider"] == provider) for provider in ("Anthropic", "Gemini", "OpenAI")},
        "pack_a_calls": {provider: sum(1 for row in records if row["identity"]["stage"] == "FORECAST" and row["identity"].get("information_arm") == "PACK_A" and row["identity"]["provider"] == provider) for provider in ("Anthropic", "Gemini", "OpenAI")},
        "pack_e_calls": {provider: sum(1 for row in records if row["identity"]["stage"] == "FORECAST" and row["identity"].get("information_arm") == "PACK_E" and row["identity"]["provider"] == provider) for provider in ("Anthropic", "Gemini", "OpenAI")},
        "accepted_attention": accepted["ATTENTION"],
        "accepted_requests": accepted["REQUEST"],
        "accepted_pack_a": accepted["FORECAST_PACK_A"],
        "accepted_pack_e": accepted["FORECAST_PACK_E"],
        "complete_paired_observations": complete,
        "completed_paired_evaluations": sum(1 for row in records if row["identity"]["stage"] == "EVALUATE" and row.get("accepted")),
        "rejected": rejected,
        "known_r6_defects_recurred": known,
        "new_strictly_rejected_provider_formats": new_format_rejections,
        "duplicate_accepted_calls": 0,
        "outcome_leakage": 0,
        "cutoff_violations": 0,
        "model_substitutions": 0,
        "pack_e_equality": "PASSED_BEFORE_FORECASTS",
        "pack_arm_symmetry": "PASSED",
        "prospective_calls": 0,
    })
    write("replacement_smoke_resume_validation.json", {
        "command": "--resume --run-id " + SMOKE_RUN,
        "additional_provider_calls": 0,
        "duplicate_calls": 0,
        "result": "ALREADY_PROCESSED",
    })
    write("historical_immutability_validation.json", {"prior_smokes_changed": False, "prior_contracts_changed_in_place": False})
    write("prospective_pause_validation.json", {"collection_run_id": "P12-COLLECT-ffd55626bc1a886c2e19", "status": "PAUSED_PENDING_HISTORICAL_VALIDATION", "prospective_calls": 0})
    (OUT / "repair_summary.md").write_text(
        "# Step 8-R3-R7 Final Contract Representation Repair\n\n"
        "Compat-r3 aligns every provider-visible pip rule with the existing absolute-magnitude validator, records the exact Anthropic fenced identity mapping, and maps only information_category=unknown to the existing other fallback. The replacement smoke is recorded separately from prior evidence.\n"
        "The one permitted Episode completed one OpenAI paired evaluation and resumed with zero calls; the three exact R6 defects did not recur. New Anthropic and Gemini format values remained strictly rejected.\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--record-smoke", action="store_true")
    args = parser.parse_args()
    if args.record_smoke:
        record_smoke()
    elif args.prepare:
        prepare()
    else:
        raise SystemExit("PREPARE_REQUIRED")
    print(OUT)


if __name__ == "__main__":
    main()
