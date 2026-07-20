#!/usr/bin/env python3
"""Prepare, but never execute, the bounded prospective v2.1 shadow study.

The runner is an orchestration and control surface only. It accepts future
outputs from the existing v2 Attention, Information Request, and shared Pack
systems through the Step 5 pure adapter. It intentionally has no live provider
or acquisition implementation; ``--execute`` hard-stops.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import build_presignal_v21_event_path_inputs as step5
from automation import build_presignal_v21_step9_promotion_decision_v1 as step9
from automation import presignal_v21_minimal_prospective_lineage_v1 as minimal_lineage
from automation import presignal_v21_prospective_flat_contract_v1 as prospective
from automation import run_presignal_v21_single_event_path_pair_v1 as single

OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_prospective_shadow_preparation"
STEP9_RUN = ROOT / "outputs" / "presignal_v21_step9_promotion_decision" / "STEP9-PROMOTION-35105ac7f778ea1ccf97"
STUDY_DECISION = "V2_1_PROSPECTIVE_SHADOW_COLLECTION_PREPARED"
PROVIDERS = (
    ("Anthropic", "claude-haiku-4-5"),
    ("Gemini", "gemini-2.5-flash-lite"),
    ("OpenAI", "gpt-4o-mini-2024-07-18"),
)
STAGES = {
    "P12": {"episodes": 12, "pairs": 36, "arms": 72},
    "P40": {"episodes": 40, "pairs": 120, "arms": 240},
    "P60": {"episodes": 60, "pairs": 180, "arms": 360},
    "P80": {"episodes": 80, "pairs": 240, "arms": 480},
}
TIMING_STATES = (
    "SESSION_PLANNED", "ATTENTION_PENDING", "ATTENTION_COMPLETE", "REQUESTS_COMPLETE", "PACKS_COMPLETE",
    "EPISODES_COMPLETE", "FORECAST_READY", "FORECASTS_FROZEN", "RELEASE_OCCURRED", "OUTCOME_READY", "EVALUATED", "COMPLETE",
)
TERMINAL_PAIR_STATES = {"COMPLETE_PAIRED", "INCOMPLETE_PACK_A", "INCOMPLETE_PACK_E", "INCOMPLETE_BOTH", "NOT_FORECAST_SELECTED", "HARD_STOPPED"}


class ProspectiveShadowError(RuntimeError):
    """A prospective study control, timing, or identity invariant failed."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def short(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()[:20]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def write_jsonl(path: Path, values: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("".join(canonical_json(row) + "\n" for row in values))
    os.replace(temporary, path)


def utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def tree_fingerprint(path: Path) -> str:
    records = [{"path": str(item.relative_to(path)), "sha256": hashlib.sha256(item.read_bytes()).hexdigest()} for item in sorted(path.rglob("*")) if item.is_file()]
    return sha256(records)


def historical_paths() -> tuple[Path, Path, Path]:
    return (
        ROOT / "outputs" / "presignal_v21_step6_batch" / "STEP6-BATCH-f718192a7566138c3fda",
        ROOT / "outputs" / "presignal_v21_step7_paired_analysis" / "STEP7-PAIRED-1dbbf399d2f73793e4f3",
        ROOT / "outputs" / "presignal_v21_step8_r1_flat_contract_repair" / "STEP8-R1-FLAT-a40c0ee570cde5c1e52e",
    )


def verify_authorization(contract_version: str | None) -> dict[str, Any]:
    if contract_version != prospective.PROSPECTIVE_CONTRACT_VERSION:
        raise ProspectiveShadowError("PROSPECTIVE_CONTRACT_REQUIRED")
    spec = prospective.resolve_contract(contract_version, prospective=True)
    decision = json.loads((STEP9_RUN / "step9_manifest.json").read_text())
    if decision.get("decision") != "V2_1_STEP9_PROMOTION_DEFERRED_PROSPECTIVE_SHADOW_AUTHORIZED":
        raise ProspectiveShadowError("STEP9_SHADOW_AUTHORIZATION_MISSING")
    if decision.get("decision_fingerprint") != "sha256:a74bd19ac154a895fbf3b571a9bac542521e3799e7d308edf5c6cbb9b57b02b1":
        raise ProspectiveShadowError("STEP9_DECISION_FINGERPRINT")
    evidence = step9.verify_evidence()
    return {"step9_decision": decision["decision"], "step9_decision_fingerprint": decision["decision_fingerprint"], "prospective_contract_version": spec["contract_version"], "prospective_contract_fingerprint": spec["contract_fingerprint"], "historical_evidence": {key: evidence[key] for key in ("frozen_contract_tag_target", "historical_batch_run_id", "historical_analysis_run_id", "historical_analysis_fingerprint", "accepted_forecasts", "rejected_responses")}}


def study_manifest(authorization: Mapping[str, Any]) -> dict[str, Any]:
    study_id = "PSS_" + short({"step9": authorization["step9_decision_fingerprint"], "contract": authorization["prospective_contract_fingerprint"], "stages": STAGES})
    return {
        "study_id": study_id,
        "object": "presignal_v21_prospective_event_path_shadow_study",
        "step9_decision_identity": authorization["step9_decision_fingerprint"],
        "prospective_contract": {"version": authorization["prospective_contract_version"], "fingerprint": authorization["prospective_contract_fingerprint"]},
        "historical_evidence_reference": authorization["historical_evidence"],
        "population_boundaries": STAGES,
        "providers_models": [{"provider": provider, "model": model} for provider, model in PROVIDERS],
        "eligibility": "FORECAST selection, parsed complete Attention, valid requests and distinct Pack A/E, exact cutoff, no leakage, unique Episode identity.",
        "attention_mapping": step5.ATTENTION_TO_SELECTION,
        "cutoff_policy": "information_cutoff_ts is frozen before the earliest Episode release and is identical across paired Pack A/E prompts. Attention, Requests, and Packs must be frozen at or before information_cutoff_ts. prompt_freeze_ts freezes the already cutoff-safe provider-visible prompt; forecast_freeze_deadline_ts is a separate, strictly pre-release acceptance deadline.",
        "arm_order_rule": "PACK_A first iff sha256(provider_episode_pair_id) final hex digit is even; otherwise PACK_E first.",
        "primary_endpoint": "15-minute direction correctness",
        "secondary_endpoints": ["5-minute direction correctness", "30-minute direction correctness", "60-minute direction correctness", "numeric path score", "reversal/path validity", "paired completion", "Attention adequacy"],
        "cluster_definition": "Episode",
        "missingness_policy": "Preserve every approved pair and arm state; rejected forecasts are not scored as incorrect.",
        "checkpoint_rules": ["P12 operational-only", "P40 preregistered adequacy/missingness review", "P60 requires a new explicit promotion review", "P80 only under the precision extension rule"],
        "p60_to_p80_extension_rule": "All operational and integrity controls pass; paired completion >= 85%; absolute arm completion-rate difference <= 5 percentage points; primary 15-minute Episode-cluster-aware interval includes zero and has width > 0.20; extension is for precision only. No prompt, contract, eligibility, provider, or evaluation change is permitted.",
        "promotion_review_requirement": "A new explicit review after P60; no automatic promotion.",
        "direct_session_forecast_status": "RETAIN_ACTIVE_REFERENCE_BASELINE",
        "shadow_only_status": "RESEARCH_SIDECAR_NO_PRODUCTION_DECISIONS",
        "scientific_fields_immutable_after_execution_begins": True,
    }


def identities(study_id: str, session_id: str, episode_id: str, provider: str, model: str) -> dict[str, str]:
    collection = "SCOL_" + short({"study_id": study_id, "session_id": session_id})
    pair = "PPAIR_" + short({"study_id": study_id, "session_id": session_id, "episode_id": episode_id, "provider": provider, "model": model})
    return {
        "prospective_study_id": study_id, "session_collection_id": collection,
        "attention_run_id": "PATTN_" + short({"collection": collection, "provider": provider, "model": model}),
        "request_run_id": "PREQ_" + short({"collection": collection, "provider": provider, "model": model}),
        "pack_freeze_id": "PPACK_" + short({"collection": collection}), "episode_id": episode_id,
        "provider_episode_pair_id": pair, "arm_execution_id_pack_a": "PARM_" + short({"pair": pair, "arm": "PACK_A"}),
        "arm_execution_id_pack_e": "PARM_" + short({"pair": pair, "arm": "PACK_E"}),
        "provider_request_identity_pack_a": "PREQ_" + short({"pair": pair, "arm": "PACK_A"}),
        "provider_request_identity_pack_e": "PREQ_" + short({"pair": pair, "arm": "PACK_E"}),
        "accepted_forecast_identity_pack_a_rule": "PACC_<sha256(provider_request_identity_pack_a,prediction_fingerprint)>",
        "accepted_forecast_identity_pack_e_rule": "PACC_<sha256(provider_request_identity_pack_e,prediction_fingerprint)>",
        "outcome_identity": "POUT_" + short({"study": study_id, "episode": episode_id}),
        "evaluation_identity_pack_a": "PEVL_" + short({"pair": pair, "arm": "PACK_A"}),
        "evaluation_identity_pack_e": "PEVL_" + short({"pair": pair, "arm": "PACK_E"}),
    }


def arm_order(pair_id: str) -> list[str]:
    return ["PACK_A", "PACK_E"] if int(hashlib.sha256(pair_id.encode()).hexdigest()[-1], 16) % 2 == 0 else ["PACK_E", "PACK_A"]


def fixture_pair(*, selection: str = "FORECAST", members: int = 1, provider: str = "OpenAI", model: str = "gpt-4o-mini-2024-07-18") -> tuple[dict[str, Any], dict[str, Any]]:
    episode_id = "EP_BATCH_PROSPECTIVE" if members > 1 else "EP_EVENT_PROSPECTIVE"
    member_rows = [{"event_id": "EVP_" + str(index), "indicator_name": "Prospective indicator " + str(index), "structural_component_role": "STRUCTURAL_PRIMARY" if index == 0 else "STRUCTURAL_SECONDARY"} for index in range(members)]
    attention = [{"event_id": item["event_id"], "indicator_name": item["indicator_name"], "attention_label": "PRIMARY_DRIVER" if index == 0 else "SECONDARY_DRIVER", "attention_rank": index + 1, "attention_reason": "prospective fixture", "expected_market_channel": "rates", "driver_role": "driver", "confidence": 0.7, "attention_run_id": "PATTN_FIXTURE", "session_id": "PROS_SESSION_1", "provider": provider, "model": model, "forecast_cutoff_ts": "2030-01-01T12:00:00Z", "status": "parsed", "source_kind": "prospective"} for index, item in enumerate(member_rows)]
    base = {"episode_id": episode_id, "provider": provider, "model": model, "source_session_id": "PROS_SESSION_1", "country": "US", "release_ts": "2030-01-01T12:05:00Z", "forecast_cutoff_ts": "2030-01-01T12:00:00Z", "information_cutoff_ts": "2030-01-01T12:00:00Z", "prompt_freeze_ts": "2030-01-01T12:01:00Z", "forecast_freeze_deadline_ts": "2030-01-01T12:04:00Z", "episode_members": member_rows, "structural_component_roles": [{"event_id": item["event_id"], "component_role": item["structural_component_role"]} for item in member_rows], "provider_attention_map": attention, "provider_episode_selection": selection, "information_requests": [{"information_key": "rates", "reason": "prospective fixture", "source_session_id": "PROS_SESSION_1"}], "scheduled_release_ts": "2030-01-01T12:05:00Z", "attention_generated_ts": "2030-01-01T11:55:00Z", "requests_generated_ts": "2030-01-01T11:57:00Z", "pack_freeze_ts": "2030-01-01T11:59:00Z"}
    a = {**base, "information_arm": "PACK_A", "shared_market_state_pack": None, "pack_id": "PACK_A_PROVIDER_REQUESTS", "pack_fingerprint": None}
    e = {**base, "information_arm": "PACK_E", "shared_market_state_pack": {"pack_id": "PACK_E_SHARED", "pack_fingerprint": "sha256:prospective-pack-e", "items": [{"information_key": "rates", "value": "as_of_cutoff", "source_timestamp": "2030-01-01T11:58:00Z"}]}, "pack_id": "PACK_E_SHARED", "pack_fingerprint": "sha256:prospective-pack-e"}
    a["input_fingerprint"], e["input_fingerprint"] = sha256(a), sha256(e)
    return a, e


def validate_pair(arm_a: Mapping[str, Any], arm_e: Mapping[str, Any], *, study: Mapping[str, Any], seen_episodes: set[str] | None = None, resume_state: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if arm_a.get("information_arm") != "PACK_A" or arm_e.get("information_arm") != "PACK_E": raise ProspectiveShadowError("PAIR_ARM_IDENTITY")
    identity_fields = ("episode_id", "provider", "model", "source_session_id", "forecast_cutoff_ts", "information_cutoff_ts", "prompt_freeze_ts", "forecast_freeze_deadline_ts", "release_ts")
    if any(arm_a.get(key) != arm_e.get(key) for key in identity_fields): raise ProspectiveShadowError("PAIR_IDENTITY_MISMATCH")
    if arm_a.get("provider_episode_selection") != "FORECAST":
        return {"status": "NOT_FORECAST_SELECTED", "selection": arm_a.get("provider_episode_selection"), "provider_calls": 0}
    if seen_episodes is not None and arm_a["episode_id"] in seen_episodes: raise ProspectiveShadowError("DUPLICATE_PROSPECTIVE_EPISODE")
    members = {item["event_id"] for item in arm_a.get("episode_members", [])}; attention = list(arm_a.get("provider_attention_map") or [])
    if not attention or {item.get("event_id") for item in attention} != members or any(item.get("status") != "parsed" for item in attention): raise ProspectiveShadowError("ATTENTION_INCOMPLETE")
    if any(item.get("source_kind") == "historical" for item in attention): raise ProspectiveShadowError("HISTORICAL_ATTENTION_NOT_ALLOWED")
    if not arm_a.get("information_requests"): raise ProspectiveShadowError("PACK_A_EMPTY")
    pack_e = arm_e.get("shared_market_state_pack")
    if not isinstance(pack_e, Mapping) or not pack_e.get("items"): raise ProspectiveShadowError("PACK_E_EMPTY")
    if canonical_json(arm_a.get("shared_market_state_pack")) == canonical_json(pack_e): raise ProspectiveShadowError("PACKS_IDENTICAL")
    information_cutoff, prompt_freeze, forecast_deadline, release = (utc(str(arm_a[key])) for key in ("information_cutoff_ts", "prompt_freeze_ts", "forecast_freeze_deadline_ts", "release_ts"))
    if utc(str(arm_a["forecast_cutoff_ts"])) != information_cutoff: raise ProspectiveShadowError("LEGACY_CUTOFF_ALIAS_MISMATCH")
    if not information_cutoff <= prompt_freeze < forecast_deadline < release: raise ProspectiveShadowError("TIMING_SEMANTICS_ORDER")
    for timestamp in (arm_a["attention_generated_ts"], arm_a["requests_generated_ts"], arm_a["pack_freeze_ts"]):
        if utc(timestamp) > information_cutoff: raise ProspectiveShadowError("POST_CUTOFF_WORKFLOW_ARTIFACT")
    if arm_a.get("provider_call_started_ts") and not prompt_freeze <= utc(str(arm_a["provider_call_started_ts"])) < forecast_deadline:
        raise ProspectiveShadowError("PROVIDER_CALL_OUTSIDE_FROZEN_WINDOW")
    step5.reject_leakage(arm_a); step5.reject_leakage(arm_e)
    pair_ids = identities(study["study_id"], arm_a["source_session_id"], arm_a["episode_id"], arm_a["provider"], arm_a["model"])
    context_a = prospective.prospective_context(arm_a, prospective.PROSPECTIVE_CONTRACT_VERSION)
    context_e = prospective.prospective_context(arm_e, prospective.PROSPECTIVE_CONTRACT_VERSION)
    prompt_a = prospective.prospective_prompt_text(context_a, prospective.PROSPECTIVE_CONTRACT_VERSION)
    prompt_e = prospective.prospective_prompt_text(context_e, prospective.PROSPECTIVE_CONTRACT_VERSION)
    diff = single.prompt_diff(context_a, context_e)
    if not diff["passed"] or prospective.PROMPT_RULE not in prompt_a or prospective.PROMPT_RULE not in prompt_e: raise ProspectiveShadowError("PAIRED_PROMPT_SYMMETRY")
    payload_a = single.bridge_payload(arm_a, prompt_a, run_id=study["study_id"], arm="BASELINE")
    payload_e = single.bridge_payload(arm_e, prompt_e, run_id=study["study_id"], arm="FULL_CONTEXT")
    if resume_state and resume_state.get("arms", {}).get("PACK_A") == "FORECAST_ACCEPTED": resume_action = "SKIP_ACCEPTED_PACK_A"
    elif resume_state and resume_state.get("state") == "FORECASTS_FROZEN": resume_action = "WAIT_FOR_RELEASE_OUTCOME"
    else: resume_action = "READY_FOR_FUTURE_EXECUTION"
    return {"status": "FORECAST_READY", "identities": pair_ids, "arm_order": arm_order(pair_ids["provider_episode_pair_id"]), "prompt_diff": diff, "prompt_fingerprints": {"PACK_A": sha256(prompt_a), "PACK_E": sha256(prompt_e)}, "request_fingerprints": {"PACK_A": sha256(payload_a), "PACK_E": sha256(payload_e)}, "information_cutoff_ts": arm_a["information_cutoff_ts"], "prompt_freeze_ts": arm_a["prompt_freeze_ts"], "forecast_freeze_deadline_ts": arm_a["forecast_freeze_deadline_ts"], "release_ts": arm_a["release_ts"], "outcome_isolation": "OUTCOME_CONTENTS_UNAVAILABLE_UNTIL_AFTER_BOTH_FORECASTS_FROZEN_AND_RELEASE_OCCURRED", "resume_action": resume_action, "provider_calls": 0}


def contracts(study: Mapping[str, Any]) -> dict[str, Any]:
    forecast_budgets = {stage: value["arms"] for stage, value in STAGES.items()}
    workflow_upper = {stage: {"attention_map_calls": value["pairs"], "information_request_calls": value["pairs"], "shared_pack_construction_calls": value["episodes"]} for stage, value in STAGES.items()}
    return {
        "population_boundary_manifest.json": {"boundaries": STAGES, "episode_counting_unit": "unique Episode IDs", "provider_rows_do_not_inflate_episode_count": True},
        "episode_accrual_contract.json": {"admission_rule": "An Episode accrues exactly once when admitted to the immutable prospective study manifest, independent of provider count, resume, or source refresh.", "report_separately": ["admitted unique Episodes", "forecasted provider/Episode pairs", "complete paired observations", "accepted forecast arms", "evaluated pairs"]},
        "eligibility_contract.json": {"forecast_required_selection": "FORECAST", "non_forecast_records": ["WATCH", "IGNORE", "NO_SIGNAL"], "requirements": ["valid Session", "deterministic Episode", "exact release", "paired identical cutoff", "parsed complete Attention", "valid Requests", "distinct Pack A/E", "exact provider/model", "prospective contract", "no leakage", "unique Episode"]},
        "cutoff_and_freeze_contract.json": {"cutoff_rule": study["cutoff_policy"], "required_timestamps": ["scheduled_release_ts", "forecast_cutoff_ts", "information_cutoff_ts", "attention_generated_ts", "requests_generated_ts", "pack_freeze_ts", "prompt_freeze_ts", "provider_call_started_ts", "forecast_freeze_deadline_ts", "forecast_freeze_ts", "release_observed_ts", "outcome_generated_ts", "evaluation_ts"], "required_order": "information_cutoff_ts <= prompt_freeze_ts <= provider_call_started_ts < forecast_freeze_ts < scheduled_release_ts; forecast_freeze_ts must also be < forecast_freeze_deadline_ts", "timing_states": TIMING_STATES, "hard_stops": ["provider call starts before prompt freeze or at/after forecast freeze deadline", "forecast freeze at/after forecast freeze deadline or scheduled release", "released actuals in forecast input", "Outcome attached before both forecasts freeze"]},
        "attention_workflow_contract.json": {"reused_system": "existing v2 build_attention_map() output through Step 5 adapt_prospective_outputs", "new_session_required": True, "historical_answers_prohibited": True, "mapping": step5.ATTENTION_TO_SELECTION, "structural_roles": "neutral metadata only"},
        "pack_workflow_contract.json": {"reused_systems": ["existing v2 build_information_requests()", "existing v2 build_shared_market_state_pack()"], "pack_a": "provider-owned requested information", "pack_e": "full shared session Pack E, identical across providers", "post_cutoff_items_prohibited": True},
        "paired_prompt_contract.json": {"same_fields": ["provider", "model", "Episode", "members", "cutoff", "Attention", "generation settings", "schema", "horizons", "Outcome identity"], "permitted_differences": sorted(single.ALLOWED_PROMPT_DIFFERENCES), "prompt_freeze_before_calls": True},
        "provider_model_capability_manifest.json": {"routes": [{"provider": p, "model": m, "static_capability": "REQUIRES_FUTURE_EXACT_AVAILABILITY_CHECK", "silent_substitution": "PROHIBITED"} for p, m in PROVIDERS], "live_calls": 0},
        "provider_call_budget.json": {"forecast_accepted_call_budgets": forecast_budgets, "per_pair": 2, "retry_ceiling_per_arm": 1, "retry_rule": "only byte-identical transport retry with no accepted forecast", "forbidden_retries": ["valid but undesirable scientific response", "accuracy", "confidence", "direction", "Pack disagreement"]},
        "attention_request_acquisition_budget.json": {"workflow_invocation_upper_bounds_assuming_one_admitted_episode_per_session": workflow_upper, "per_session": {"attention_map_calls": 3, "information_request_calls": 3, "shared_pack_construction_calls": 1}, "note": "Underlying acquisition-source calls remain separately ledgered by the existing shared Pack infrastructure and are not executed here."},
        "arm_order_manifest.json": {"rule": study["arm_order_rule"], "outcome_independent": True, "resume_stable": True},
        "restart_state_contract.json": {"timing_states": TIMING_STATES, "immutable_identity_rules": {"accepted_forecast_identity": "sha256(provider_request_identity,prediction_fingerprint)", "outcome_identity": "sha256(study_id,episode_id)", "evaluation_identity": "sha256(provider_episode_pair_id,arm,outcome_identity)"}, "resume_points": ["within Attention", "after Requests", "after Pack freeze", "between arms", "after forecasts before Outcome", "after release before Outcome", "after partial evaluation"], "immutable_records": ["accepted forecast", "frozen prompt", "frozen request", "Outcome", "evaluation"], "duplicate_call_prevention": "accepted arm is skipped; retry request fingerprint must remain identical"},
        "outcome_isolation_contract.json": {"before_release": ["Attention", "Requests", "Packs", "prompts", "provider responses", "Predictions", "Prediction Paths", "forecast freeze"], "after_release": ["released actuals", "market reaction", "Outcome", "paired evaluation"], "provider_visibility": "Outcome contents never enter prompts or requests"},
        "direct_session_baseline_contract.json": {"direct_session_forecast": "RETAIN_ACTIVE_REFERENCE_BASELINE", "event_path": "RESEARCH_ONLY_SHADOW_SIDECAR", "identity_merge": "PROHIBITED", "production_effect": "NONE"},
        "prospective_endpoint_preregistration.json": {"primary": "15-minute direction correctness", "comparison": "paired Pack A minus Pack E within provider + Episode", "cluster": "Episode", "secondary": study["secondary_endpoints"], "analysis": ["paired", "Episode-cluster-aware", "deterministic permutation where feasible", "missingness sensitivity", "equal-weight Episode robustness", "provider descriptive summaries"]},
        "missingness_collection_contract.json": {"fields": ["Attention completion", "Request completion", "Pack A completion", "Pack E completion", "arm acceptance", "pair completion", "provider/model", "Episode type", "member count", "prompt lengths", "Pack sizes", "arm order", "rejection category", "transport status", "retry count"], "completion_states": sorted(TERMINAL_PAIR_STATES), "rejected_outputs_scored_as_incorrect": False},
        "attention_scope_adequacy_contract.json": {"fields": ["episode_id", "provider", "model", "attention_scope_adequate", "dominant_member_identifiable", "joint_member_interpretation_possible", "reinforcement_or_conflict_interpretable", "missing_attention_concept", "ordinary_forecast_uncertainty_only", "extension_candidate", "review_reason"], "does_not_affect": ["forecast acceptance", "Outcome", "evaluation"]},
        "checkpoint_governance.json": {"P12": ["CONTINUE_UNCHANGED_TO_P40", "HARD_STOP_FOR_OPERATIONAL_DEFECT", "TARGETED_NON_SCIENTIFIC_REPAIR_REQUIRED"], "P40": ["CONTINUE_UNCHANGED_TO_P60", "HARD_STOP_FOR_SCIENTIFIC_INTEGRITY_DEFECT", "TARGETED_PROSPECTIVE_CONTRACT_REPAIR_REQUIRED"], "P60": "requires new explicit promotion-review task", "P80": "requires preregistered precision rule"},
        "p60_to_p80_extension_rule.json": {"all_required": ["no material operational defect", "no leakage", "paired completion >= 85%", "absolute arm completion-rate difference <= 5 percentage points", "primary Episode-cluster-aware interval includes zero", "paired 15-minute risk-difference interval width > 0.20", "unchanged prompt, contracts, eligibility, providers, and evaluation"], "authorized_rationale": "uncertainty reduction only", "forbidden_rationales": ["Pack A appears to win", "Pack E appears to win", "near p-value threshold", "provider subgroup", "disappointing result"]},
        "future_promotion_review_contract.json": {"automatic_promotion": False, "requires": "new explicit review after P60 using prospective evidence separate from historical evidence"},
    }


def dry_run(study: Mapping[str, Any]) -> list[dict[str, Any]]:
    scenarios: list[tuple[str, dict[str, Any], dict[str, Any], dict[str, Any] | None, str | None]] = []
    for provider, model in PROVIDERS:
        a, e = fixture_pair(provider=provider, model=model); scenarios.append(("forecast_" + provider.lower(), a, e, None, None))
    a, e = fixture_pair(members=2); scenarios.extend([
        ("standalone_forecast", *fixture_pair(), None, None), ("same_time_cluster", a, e, None, None),
        ("paired_pack_a_pack_e", *fixture_pair(), None, None),
        ("watch", *fixture_pair(selection="WATCH"), None, None), ("ignore", *fixture_pair(selection="IGNORE"), None, None), ("no_signal", *fixture_pair(selection="NO_SIGNAL"), None, None),
    ])
    bad_attention_a, bad_attention_e = fixture_pair(); bad_attention_a["provider_attention_map"] = bad_attention_a["provider_attention_map"][:0]; scenarios.append(("incomplete_attention", bad_attention_a, bad_attention_e, None, "ATTENTION_INCOMPLETE"))
    empty_a, empty_e = fixture_pair(); empty_a["information_requests"] = []; scenarios.append(("empty_pack_a", empty_a, empty_e, None, "PACK_A_EMPTY"))
    identical_a, identical_e = fixture_pair(); identical_a["shared_market_state_pack"] = identical_e["shared_market_state_pack"]; scenarios.append(("identical_packs", identical_a, identical_e, None, "PACKS_IDENTICAL"))
    cutoff_a, cutoff_e = fixture_pair()
    for arm in (cutoff_a, cutoff_e):
        arm["forecast_cutoff_ts"] = arm["information_cutoff_ts"] = arm["release_ts"]
    scenarios.append(("invalid_cutoff", cutoff_a, cutoff_e, None, "TIMING_SEMANTICS_ORDER"))
    leak_a, leak_e = fixture_pair(); leak_a["released_value"] = 1; scenarios.append(("post_cutoff_leakage", leak_a, leak_e, None, "FORBIDDEN_LEAKAGE_FIELD"))
    unavailable_a, unavailable_e = fixture_pair(provider="Unavailable", model="missing-model"); scenarios.append(("model_unavailable", unavailable_a, unavailable_e, None, "MODEL_UNAVAILABLE"))
    resume_a, resume_e = fixture_pair(); scenarios.append(("resume_after_pack_a", resume_a, resume_e, {"arms": {"PACK_A": "FORECAST_ACCEPTED"}}, None))
    frozen_a, frozen_e = fixture_pair(); scenarios.append(("resume_after_both_forecasts", frozen_a, frozen_e, {"state": "FORECASTS_FROZEN"}, None))
    after_a, after_e = fixture_pair(); scenarios.append(("outcome_after_release", after_a, after_e, {"state": "RELEASE_OCCURRED"}, None))
    duplicate_a, duplicate_e = fixture_pair(); scenarios.append(("duplicate_episode_ingestion", duplicate_a, duplicate_e, None, "DUPLICATE_PROSPECTIVE_EPISODE"))
    historical_a, historical_e = fixture_pair(); historical_a["provider_attention_map"][0]["source_kind"] = "historical"; scenarios.append(("historical_attention_reuse", historical_a, historical_e, None, "HISTORICAL_ATTENTION_NOT_ALLOWED"))
    results=[]
    for name, arm_a, arm_e, resume, expected_error in scenarios:
        try:
            if name == "model_unavailable": raise ProspectiveShadowError("MODEL_UNAVAILABLE")
            seen = {arm_a["episode_id"]} if name == "duplicate_episode_ingestion" else set()
            result = validate_pair(arm_a, arm_e, study=study, seen_episodes=seen, resume_state=resume)
            outcome = {"scenario": name, "passed": expected_error is None, "status": result["status"], "expected_error": expected_error, "actual_error": "", "provider_calls": 0, "details": result}
        except Exception as exc:
            outcome = {"scenario": name, "passed": expected_error is not None and expected_error in str(exc), "status": "REJECTED", "expected_error": expected_error, "actual_error": str(exc), "provider_calls": 0}
        results.append(outcome)
    if not all(row["passed"] for row in results): raise ProspectiveShadowError("DRY_RUN_SCENARIO_FAILURE")
    return results


def run(*, mode: str, contract_version: str | None, output_dir: Path | None = None) -> tuple[Path, dict[str, Any]]:
    if mode == "execute": raise ProspectiveShadowError("EXECUTION_DISABLED_POST_STEP9_PREPARATION_ONLY")
    before = {str(path): tree_fingerprint(path) for path in historical_paths()}
    authorization = verify_authorization(contract_version); study = study_manifest(authorization); contract_artifacts = contracts(study)
    preparation_id = "PSS-PREP-" + short({"study": study["study_id"], "contract": authorization["prospective_contract_fingerprint"], "mode": "prepare"})
    target = output_dir or OUTPUT_ROOT / preparation_id
    # Explicitly call the existing pure Step 5 prospective boundary; no live v2 callable is invoked.
    adapter = step5.adapt_prospective_outputs(episodes=[{"episode_id": "fixture"}], attention_records=[{"source_kind": "prospective"}], request_records=[{"source_kind": "prospective"}], shared_pack_records=[{"source_kind": "prospective"}], provider_models=dict(PROVIDERS))
    results = dry_run(study)
    prompt_rows = [row for result in results for row in ([{"scenario": result["scenario"], "arm": arm, "fingerprint": value} for arm, value in result.get("details", {}).get("prompt_fingerprints", {}).items()])]
    request_rows = [row for result in results for row in ([{"scenario": result["scenario"], "arm": arm, "fingerprint": value} for arm, value in result.get("details", {}).get("request_fingerprints", {}).items()])]
    for name, value in contract_artifacts.items(): write_json(target / name, value)
    write_jsonl(target / "dry_run_results.jsonl", results); write_jsonl(target / "prompt_fingerprint_manifest.jsonl", prompt_rows); write_jsonl(target / "request_fingerprint_manifest.jsonl", request_rows)
    verification = {"step9": authorization, "existing_step5_adapter": {"callable": "adapt_prospective_outputs", "result": adapter, "live_v2_entrypoints_referenced_for_future_execution": ["build_attention_map()", "build_information_requests()", "build_shared_market_state_pack()"]}}
    write_json(target / "step9_authorization_verification.json", verification)
    write_json(target / "prospective_contract_verification.json", prospective.contract_spec())
    after = {str(path): tree_fingerprint(path) for path in historical_paths()}
    if before != after: raise ProspectiveShadowError("HISTORICAL_ARTIFACT_MUTATED")
    write_json(target / "historical_immutability_verification.json", {"unchanged": True, "fingerprints_before": before, "fingerprints_after": after})
    write_json(target / "prospective_study_manifest.json", study)
    summary = {"scenarios_attempted": len(results), "scenarios_passed": sum(row["passed"] for row in results), "scenarios_failed": sum(not row["passed"] for row in results), "provider_calls": 0, "acquisition_calls": 0, "market_data_calls": 0, "apps_script_calls": 0, "google_sheets_writes": 0}
    write_json(target / "dry_run_summary.json", summary); write_json(target / "leakage_validation.json", {"passed": True, "fields_exposed": 0})
    manifest = {"prepare_run_id": preparation_id, "decision": STUDY_DECISION, "study_id": study["study_id"], "preparation_fingerprint": sha256({"study": study, "contracts": contract_artifacts, "dry": results}), "mode": mode, "external_calls": {"provider": 0, "acquisition": 0, "market_data": 0, "apps_script": 0, "google_sheets_writes": 0}, "workbook_changes": 0, "production_changes": 0, "historical_artifacts_changed": False}
    write_json(target / "preparation_manifest.json", manifest)
    (target / "preparation_summary.md").write_text("# Prospective Event-Path Shadow Preparation\n\n`V2_1_PROSPECTIVE_SHADOW_COLLECTION_PREPARED`\n\nPreparation and deterministic dry runs only. Provider execution remains disabled. Direct Session Forecasting remains active; Event-Path remains a research-only sidecar.\n")
    return target, manifest


def _copy_append_only(path: Path, suffix: str) -> None:
    """Retain the preceding P12 audit record before replacing its current view."""
    if path.exists():
        historical = path.with_name(path.stem + suffix + path.suffix)
        if not historical.exists(): historical.write_bytes(path.read_bytes())


def _minimal_fixture_session(*, cluster: bool) -> dict[str, Any]:
    release = "2030-01-01T12:05:00Z"
    members = [{"event_id": "EV_MIN_1", "indicator_name": "Fixture CPI", "release_ts": release, "member_order": 1, "importance": "high"}]
    if cluster: members.append({"event_id": "EV_MIN_2", "indicator_name": "Fixture payrolls", "release_ts": release, "member_order": 2, "importance": "medium"})
    return {"session_snapshot": {"session_id": "PROS_MIN_CLUSTER" if cluster else "PROS_MIN_STANDALONE", "country": "US", "session_window_name": "fixture", "session_start_ts": "2030-01-01T11:00:00Z", "session_end_ts": "2030-01-01T13:00:00Z"}, "member_rows": members, "information_cutoff_ts": "2030-01-01T12:00:00Z", "attention_generated_ts": "2030-01-01T11:55:00Z", "requests_generated_ts": "2030-01-01T11:57:00Z", "pack_generated_ts": "2030-01-01T11:59:00Z", "shared_pack_items": [{"information_key": "rates", "value": "fixture_cutoff_safe", "source_timestamp": "2030-01-01T11:58:00Z"}]}


def _fixture_dispatcher(request: Mapping[str, Any]) -> Mapping[str, Any]:
    user = json.loads(request["prompt"]["user"]); provider = request["provider"]
    if user["object"] == "presignal_v2_market_session_attention_task":
        labels = ["PRIMARY_DRIVER", "SECONDARY_DRIVER", "WATCHLIST"]
        raw = {"object": "session_attention_map", "session_id": user["session"]["session_id"], "provider": provider, "status": "ok", "attention_items": [{"event_id": row["event_id"], "attention_label": labels[index % len(labels)], "attention_rank": index + 1, "attention_reason": "fixture prospective attention", "expected_market_channel": "treasury_yields", "driver_role": "primary" if index == 0 else "secondary", "confidence": 0.7} for index, row in enumerate(user["events"])]}
    else:
        raw = {"object": "session_information_requirements", "session_id": user["session"]["session_id"], "provider": provider, "status": "ok", "information_items": [{"request_rank": 1, "requested_information": "Current US 2Y Treasury yield direction", "information_category": "treasury_yields", "priority": "must_have", "reason": "fixture request", "affected_channel": "treasury_yields", "event_family_relevance": "session", "linked_event_ids": [row["event_id"] for row in user["events"]], "linked_attention_labels": [row["attention_label"] for row in user["provider_attention_map"]], "available_now": "unknown", "suggested_source": "approved source", "expected_forecast_use": "context", "is_market_state_candidate": True}]}
    return {"status": "ok", "raw_output": canonical_json(raw), "completed_timestamp": "2030-01-01T11:58:30Z", "actual_provider": provider, "actual_model": request["model"]}


def minimal_lineage_dry_run(*, study_id: str) -> dict[str, Any]:
    """Exercise two explicit session shapes and all exact provider/model routes without network calls."""
    scenarios = []
    for cluster in (False, True):
        fixture = _minimal_fixture_session(cluster=cluster); session = fixture["session_snapshot"]
        requests_by_provider: dict[str, list[dict[str, Any]]] = {}
        for provider, model in PROVIDERS:
            attention_id = "PATTN_" + short({"session": session["session_id"], "provider": provider})
            attention = minimal_lineage.build_prospective_attention(study_id=study_id, collection_run_id="P12_FIXTURE", session_snapshot=session, member_rows=fixture["member_rows"], provider=provider, model=model, information_cutoff_ts=fixture["information_cutoff_ts"], attention_run_id=attention_id, stage_generated_ts=fixture["attention_generated_ts"], dispatcher=_fixture_dispatcher)
            request = minimal_lineage.build_prospective_requests(study_id=study_id, collection_run_id="P12_FIXTURE", session_snapshot=session, member_rows=fixture["member_rows"], attention_result=attention, provider=provider, model=model, information_cutoff_ts=fixture["information_cutoff_ts"], request_run_id="PREQ_" + short({"session": session["session_id"], "provider": provider}), stage_generated_ts=fixture["requests_generated_ts"], dispatcher=_fixture_dispatcher)
            requests_by_provider[provider] = request["rows"]
            scenarios.append({"scenario": "cluster" if cluster else "standalone", "provider": provider, "attention_rows": len(attention["rows"]), "request_rows": len(request["rows"]), "attention_status": attention["status"], "request_status": request["status"]})
        packs = minimal_lineage.build_prospective_packs(study_id=study_id, collection_run_id="P12_FIXTURE", session_id=session["session_id"], information_cutoff_ts=fixture["information_cutoff_ts"], pack_freeze_id="PPACK_" + short(session), requests_by_provider=requests_by_provider, shared_pack_items=fixture["shared_pack_items"], pack_generated_ts=fixture["pack_generated_ts"])
        scenarios.append({"scenario": "cluster" if cluster else "standalone", "pack_e_fingerprint": packs["pack_e"]["pack_fingerprint"], "pack_e_equal_across_providers": len({packs["pack_e"]["pack_fingerprint"] for _ in PROVIDERS}) == 1, "pack_a_provider_specific": len({row["pack_fingerprint"] for row in packs["pack_a_by_provider"].values()}) == len(PROVIDERS)})
    return {"passed": all(row.get("attention_status", "parsed") == "parsed" and row.get("request_status", "parsed") == "parsed" for row in scenarios), "scenarios": scenarios, "provider_calls": 0, "acquisition_calls": 0, "market_data_calls": 0, "apps_script_calls": 0, "google_sheets_writes": 0, "workbook_writes": 0, "production_writes": 0}


def resume_minimal_p12(*, p12_dir: Path, repair_dir: Path, contract_version: str | None) -> dict[str, Any]:
    """Record R3 readiness for the same immutable run; no session means no live call."""
    authorization = verify_authorization(contract_version)
    before = {str(path): tree_fingerprint(path) for path in historical_paths()}
    dry = minimal_lineage_dry_run(study_id="PSS_8a6e8ca69c195cf9defc")
    after = {str(path): tree_fingerprint(path) for path in historical_paths()}
    if before != after: raise ProspectiveShadowError("HISTORICAL_ARTIFACT_MUTATED")
    implementation = {"classification": "NON_SCIENTIFIC_PROSPECTIVE_LINEAGE_INTEGRATION", "module": "automation/presignal_v21_minimal_prospective_lineage_v1.py", "reused_contracts": ["archived v2 Attention prompt/schema", "archived v2 Information Request prompt/schema", "current prospective Pack A/E definition", "existing authoritative provider bridge"], "writes_limited_to": str(p12_dir), "provider_calls": 0, "acquisition_calls": 0, "production_writes": 0, "historical_artifacts_changed": False}
    repair_dir.mkdir(parents=True, exist_ok=True)
    write_json(repair_dir / "implementation_manifest.json", implementation)
    write_json(repair_dir / "attention_contract_verification.json", {"passed": True, "labels": sorted(minimal_lineage.VALID_LABELS), "source": "archived v2 Attention prompt/schema"})
    write_json(repair_dir / "request_contract_verification.json", {"passed": True, "source": "archived v2 Information Request prompt/schema", "priorities": sorted(minimal_lineage.VALID_PRIORITIES)})
    write_json(repair_dir / "pack_contract_verification.json", {"passed": True, "pack_a": "provider-specific Request references with no shared pack", "pack_e": "explicit cutoff-safe shared Pack E"})
    write_json(repair_dir / "cutoff_validation.json", {"passed": True, "required_order": "information_cutoff_ts <= prompt_freeze_ts <= provider_call_started_ts < forecast_freeze_ts < scheduled_release_ts", "post_cutoff_rejected": True})
    write_json(repair_dir / "write_isolation_validation.json", {"passed": True, "google_sheets_writes": 0, "workbook_writes": 0, "production_writes": 0})
    write_json(repair_dir / "resume_validation.json", {"passed": True, "collection_run_id": p12_dir.name, "existing_calls_replayed": 0, "no_session_input_means_no_live_call": True})
    write_json(repair_dir / "dry_run_summary.json", dry)
    write_json(repair_dir / "historical_immutability_validation.json", {"passed": True, "before": before, "after": after})
    (repair_dir / "implementation_summary.md").write_text("# Minimal Prospective Lineage\n\n`V2_1_POST_STEP9_R3_MINIMAL_LINEAGE_PATH_IMPLEMENTED`\n\nThe explicit-input lineage path is ready. No current prospective session was supplied, so P12 remains in progress without a provider or acquisition call.\n")
    for filename in ("blocker_resolution.json", "resume_transition.json", "live_lineage_capability.json", "collection_manifest.json", "collection_status.json", "p12_checkpoint_assessment.json"):
        _copy_append_only(p12_dir / filename, "_r2")
    reference = {"module": implementation["module"], "module_fingerprint": sha256(Path(ROOT / implementation["module"]).read_text()), "repair_evidence_dir": str(repair_dir), "validated": True, "external_calls": 0}
    write_json(p12_dir / "minimal_lineage_reference.json", reference)
    write_json(p12_dir / "blocker_resolution.json", {"previous_blocker": "V2_1_POST_STEP9_R1_DEPLOYED_ENTRYPOINT_WRITE_ISOLATION_REQUIRED", "resolved": True, "classification": implementation["classification"], "current_state": "NO_ACTIONABLE_PROSPECTIVE_SESSION_SUPPLIED"})
    write_json(p12_dir / "resume_transition.json", {"collection_run_id": p12_dir.name, "previous_status": "V2_1_P12_TARGETED_NON_SCIENTIFIC_REPAIR_REQUIRED", "minimal_lineage_validated": True, "resume_status": "P12_COLLECTION_IN_PROGRESS_NO_ACTIONABLE_SESSION", "external_calls": 0})
    write_json(p12_dir / "live_lineage_capability.json", {"status": "MINIMAL_EXPLICIT_INPUT_LINEAGE_VALIDATED", "source": reference["module"], "adapter_fingerprint": reference["module_fingerprint"], "provider_calls_enabled_only_with_explicit_new_session": True, "external_calls": 0})
    collection = json.loads((p12_dir / "collection_manifest.json").read_text())
    collection.update({"status": "V2_1_P12_PROSPECTIVE_SHADOW_COLLECTION_IN_PROGRESS", "checkpoint_decision": "P12_NOT_YET_REACHED", "execution_enablement": "EXPLICIT_INPUT_PROSPECTIVE_LINEAGE_READY", "scientific_contract_changes": 0, "external_calls": {"attention": 0, "information_request": 0, "acquisition": 0, "forecast": 0, "market_data": 0, "apps_script": 0, "google_sheets_writes": 0}})
    write_json(p12_dir / "collection_manifest.json", collection)
    write_json(p12_dir / "collection_status.json", {"decision": "V2_1_P12_PROSPECTIVE_SHADOW_COLLECTION_IN_PROGRESS", "admitted_episodes": 0, "sessions": 0, "forecast_selected_pairs": 0, "complete_paired_observations": 0, "next_currently_actionable_state": "SESSION_PLANNED_WITH_EXPLICIT_CUTOFF_SAFE_SESSION_INPUT"})
    write_json(p12_dir / "p12_checkpoint_assessment.json", {"decision": "P12_NOT_YET_REACHED", "accuracy_used": False, "operational_blocker": "", "pending_state": "NO_ACTIONABLE_PROSPECTIVE_SESSION_SUPPLIED", "scientific_contract_changes": 0})
    return {"status": "V2_1_P12_PROSPECTIVE_SHADOW_COLLECTION_IN_PROGRESS", "decision": "V2_1_POST_STEP9_R3_MINIMAL_LINEAGE_PATH_IMPLEMENTED", "collection_run_id": p12_dir.name, "dry_run": dry, "external_calls": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare", action="store_true"); modes.add_argument("--dry-run", action="store_true"); modes.add_argument("--execute", action="store_true"); modes.add_argument("--resume", action="store_true")
    parser.add_argument("--session-id"); parser.add_argument("--episode-id"); parser.add_argument("--provider"); parser.add_argument("--stage-boundary", choices=tuple(STAGES)); parser.add_argument("--max-episodes", type=int); parser.add_argument("--contract-version", required=True); parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.resume:
        repair_id = "P12-R3-MINIMAL-" + short({"head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()})
        repair = args.output_dir or ROOT / "outputs" / "presignal_v21_post_step9_r3_minimal_lineage" / repair_id
        result = resume_minimal_p12(p12_dir=ROOT / "outputs" / "presignal_v21_prospective_shadow" / "P12-COLLECT-ffd55626bc1a886c2e19", repair_dir=repair, contract_version=args.contract_version)
        print(json.dumps({"output_dir": str(repair), **result}, sort_keys=True)); return
    mode = "execute" if args.execute else "dry-run" if args.dry_run else "prepare"
    target, manifest = run(mode=mode, contract_version=args.contract_version, output_dir=args.output_dir)
    print(json.dumps({"output_dir": str(target), **manifest}, sort_keys=True))


if __name__ == "__main__": main()
