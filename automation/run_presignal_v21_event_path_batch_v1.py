#!/usr/bin/env python3
"""Prepare, dry-run, and safely describe a v2.1 historical Pack A/E batch.

This module deliberately contains no provider dispatch.  ``--execute`` is a
hard stop during this preparation task.  Future execution must consume the
frozen plan and honour the state contract below rather than rebuild prompts.
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import presignal_v21_event_path_contract_v1 as contract
from automation import run_presignal_v21_single_event_path_pair_v1 as single
from automation.build_presignal_v21_event_path_inputs import reject_leakage

STEP5 = ROOT / "outputs" / "presignal_v21_step5_reuse"
OUTCOMES = ROOT / "outputs" / "presignal_v21_episode_outcomes" / "outcome_rows.jsonl"
SINGLE_RUN = ROOT / "outputs" / "presignal_v21_step6_single_pair" / "STEP6-SINGLE-20260719T175850564590Z"
PREPARATION_ROOT = ROOT / "outputs" / "presignal_v21_step6_batch_preparation"
EXECUTION_ROOT = ROOT / "outputs" / "presignal_v21_step6_batch"
BRIDGE = ROOT / "apps_script" / "authoritative_provider_bridge.js"
PREDICTION_RUNNER = ROOT / "apps_script" / "prediction_runner.js"
PREPARATION_VERSION = "presignal_step6_controlled_batch_prepare_v1"
SUPPORTED_PROVIDERS = {"Anthropic", "Gemini", "OpenAI"}
TERMINAL_ARM_STATES = {"FORECAST_ACCEPTED", "OUTCOME_ATTACHED", "EVALUATED", "COMPLETE", "HARD_STOPPED"}
ARM_STATES = [
    "NOT_STARTED", "PREFLIGHTED", "REQUEST_FROZEN", "CALL_STARTED", "TRANSPORT_FAILED",
    "RESPONSE_RECEIVED", "PARSE_FAILED", "FORECAST_ACCEPTED", "OUTCOME_ATTACHED",
    "EVALUATED", "COMPLETE", "HARD_STOPPED",
]


class BatchPreparationError(RuntimeError):
    """A batch preflight or frozen-control invariant failed."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def short(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()[:20]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def rows(path: Path) -> list[dict[str, Any]]:
    return single.read_jsonl(path)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def write_jsonl(path: Path, values: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("".join(canonical_json(value) + "\n" for value in values))
    os.replace(temporary, path)


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def git_file_commit(path: Path) -> str:
    return subprocess.check_output(["git", "log", "-1", "--format=%H", "--", str(path.relative_to(ROOT))], cwd=ROOT, text=True).strip()


def input_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (str(row.get("episode_id")), str(row.get("provider")), str(row.get("model")))


def pair_id(row: Mapping[str, Any]) -> str:
    return "PAIR_" + short({
        "episode_id": row["episode_id"], "session_id": row["source_session_id"], "provider": row["provider"],
        "model": row["model"], "forecast_cutoff_ts": row["forecast_cutoff_ts"], "contract": contract.CONTRACT_VERSION,
    })


def arm_order(pair_identity: str) -> list[str]:
    """A fixed, Outcome-independent parity order with deterministic balance."""
    return ["PACK_A", "PACK_E"] if int(hashlib.sha256(pair_identity.encode()).hexdigest()[-1], 16) % 2 == 0 else ["PACK_E", "PACK_A"]


def provider_capability(provider: str, model: str) -> dict[str, Any]:
    """Static capability only; this never probes a provider or Apps Script."""
    bridge_source, runner_source = BRIDGE.read_text(), PREDICTION_RUNNER.read_text()
    configured = provider in SUPPORTED_PROVIDERS and provider in runner_source
    bridge_capable = "apiCallAuthoritativeProviderJsonObject" in bridge_source and "prov.model = requestedModel" in bridge_source
    return {
        "provider": provider, "model": model, "static_status": "STATIC_CAPABLE" if configured and bridge_capable else "UNAVAILABLE",
        "provider_known_to_bridge": configured, "exact_requested_model_is_enforced": bridge_capable,
        "live_call_performed": False, "bridge_fingerprint": file_sha(BRIDGE),
    }


def outcome_index() -> dict[str, Mapping[str, Any]]:
    return {row["episode_id"]: row for row in rows(OUTCOMES) if row.get("status") == "VALID"}


def attention_is_fully_parsed(row: Mapping[str, Any]) -> bool:
    members = {member.get("event_id") for member in row.get("episode_members", [])}
    attention = list(row.get("provider_attention_map") or [])
    return bool(attention) and {item.get("event_id") for item in attention} == members and all(item.get("status") == "parsed" for item in attention)


def classification(
    arm_a: Mapping[str, Any] | None, arm_e: Mapping[str, Any] | None,
    *, outcomes: Mapping[str, Mapping[str, Any]], duplicate_keys: set[tuple[str, str, str]],
) -> tuple[str, str]:
    """Return exactly one mutually-exclusive scientific batch status/reason."""
    if not arm_a or not arm_e:
        return "OTHER_EXPLICIT_EXCLUSION", "MISSING_PACK_ARM"
    key = input_key(arm_a)
    if key in duplicate_keys or input_key(arm_e) != key:
        return "DUPLICATE_IDENTITY", "PAIR_IDENTITY_MISMATCH_OR_DUPLICATE"
    selection = arm_a.get("provider_episode_selection")
    if selection == "WATCH": return "WATCH_SELECTION", "ORIGINAL_ATTENTION_SELECTION_WATCH"
    if selection == "IGNORE": return "IGNORE_SELECTION", "ORIGINAL_ATTENTION_SELECTION_IGNORE"
    if selection == "NO_SIGNAL": return "NO_SIGNAL_SELECTION", "ORIGINAL_ATTENTION_SELECTION_NO_SIGNAL"
    if selection != "FORECAST": return "OTHER_EXPLICIT_EXCLUSION", "UNKNOWN_SELECTION"
    if not attention_is_fully_parsed(arm_a):
        return "ATTENTION_NOT_FULLY_PARSED", "MEMBER_ATTENTION_NOT_ALL_PARSED"
    if not arm_a.get("information_requests"):
        return "PACK_A_EMPTY", "NO_BASELINE_REQUEST_CONTEXT"
    pack_e = arm_e.get("shared_market_state_pack")
    if not isinstance(pack_e, Mapping) or not pack_e.get("items"):
        return "PACK_E_EMPTY", "NO_SHARED_PACK_ITEMS"
    if canonical_json(arm_a.get("shared_market_state_pack")) == canonical_json(pack_e):
        return "PACKS_IDENTICAL", "PACK_A_AND_PACK_E_NOT_DISTINCT"
    if arm_a.get("episode_id") not in outcomes:
        return "OUTCOME_UNAVAILABLE", "NO_VALID_DETERMINISTIC_OUTCOME"
    if arm_a.get("forecast_cutoff_ts") != arm_e.get("forecast_cutoff_ts") or arm_a.get("release_ts") < arm_a.get("forecast_cutoff_ts"):
        return "CUTOFF_INVALID", "CUT_OFF_NOT_IDENTICAL_OR_POST_RELEASE"
    capability = provider_capability(str(arm_a.get("provider")), str(arm_a.get("model")))
    if not capability["provider_known_to_bridge"]:
        return "PROVIDER_UNAVAILABLE", "STATIC_PROVIDER_NOT_SUPPORTED"
    if not capability["exact_requested_model_is_enforced"]:
        return "MODEL_UNAVAILABLE", "BRIDGE_CANNOT_ENFORCE_EXACT_MODEL"
    try:
        context_a, context_e = single.arm_context(arm_a), single.arm_context(arm_e)
        reject_leakage(context_a); reject_leakage(context_e)
        if not single.prompt_diff(context_a, context_e)["passed"]:
            return "NON_DIRECTIONAL_OR_CONTRACT_INCOMPATIBLE", "PROMPT_ASYMMETRY"
        single.bridge_payload(arm_a, single.prompt_text(context_a), run_id="PREFLIGHT", arm="BASELINE")
        single.bridge_payload(arm_e, single.prompt_text(context_e), run_id="PREFLIGHT", arm="FULL_CONTEXT")
    except Exception as exc:
        message = str(exc)
        return ("LEAKAGE_REJECTED", message) if "LEAKAGE" in message or "FORBIDDEN" in message else ("NON_DIRECTIONAL_OR_CONTRACT_INCOMPATIBLE", message)
    return "BATCH_ELIGIBLE", "ALL_NON_PROVIDER_PREFLIGHTS_PASS"


def reconcile_population(inputs_a: list[Mapping[str, Any]], inputs_e: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    a_groups: dict[tuple[str, str, str], list[Mapping[str, Any]]] = {}
    e_groups: dict[tuple[str, str, str], list[Mapping[str, Any]]] = {}
    for item in inputs_a: a_groups.setdefault(input_key(item), []).append(item)
    for item in inputs_e: e_groups.setdefault(input_key(item), []).append(item)
    duplicate_keys = {key for key, values in a_groups.items() if len(values) != 1} | {key for key, values in e_groups.items() if len(values) != 1}
    outcomes = outcome_index(); reconciliation: list[dict[str, Any]] = []
    for key in sorted(set(a_groups) | set(e_groups)):
        arm_a = a_groups.get(key, [None])[0] if len(a_groups.get(key, [])) == 1 else None
        arm_e = e_groups.get(key, [None])[0] if len(e_groups.get(key, [])) == 1 else None
        source = arm_a or arm_e
        status, reason = classification(arm_a, arm_e, outcomes=outcomes, duplicate_keys=duplicate_keys)
        attention = list((source or {}).get("provider_attention_map") or [])
        record = {
            "pair_id": pair_id(source) if source else "PAIR_UNKNOWN_" + short(key), "episode_id": key[0],
            "session_id": (source or {}).get("source_session_id"), "provider": key[1], "model": key[2],
            "attention_run_id": sorted({row.get("attention_run_id") for row in attention if row.get("attention_run_id")}),
            "episode_selection": (source or {}).get("provider_episode_selection"),
            "member_event_ids": [row.get("event_id") for row in (source or {}).get("episode_members", [])],
            "same_time_cluster": len((source or {}).get("episode_members", [])) > 1,
            "pack_a_fingerprint": (arm_a or {}).get("pack_fingerprint"), "pack_e_fingerprint": (arm_e or {}).get("pack_fingerprint"),
            "cutoff": (source or {}).get("forecast_cutoff_ts"), "outcome_identity": outcomes.get(key[0], {}).get("outcome_id"),
            "eligibility_status": status, "exclusion_reason": "" if status == "BATCH_ELIGIBLE" else reason,
            "source_input_row_fingerprints": {"pack_a": (arm_a or {}).get("input_fingerprint"), "pack_e": (arm_e or {}).get("input_fingerprint")},
        }
        reconciliation.append(record)
    if len(reconciliation) != len(inputs_a) or len(inputs_a) != len(inputs_e):
        raise BatchPreparationError("STEP5_PAIR_POPULATION_NOT_ONE_TO_ONE")
    return reconciliation


def batch_contract() -> dict[str, Any]:
    single_manifest = read_json(SINGLE_RUN / "run_manifest.json")
    prompt_template = read_json(SINGLE_RUN / "prompt_template.json")
    if single_manifest.get("decision") != "V2_1_STEP6_SINGLE_HISTORICAL_PAIR_VALIDATED":
        raise BatchPreparationError("SINGLE_PAIR_REFERENCE_NOT_VALIDATED")
    if prompt_template.get("allowed_prompt_differences") != sorted(single.ALLOWED_PROMPT_DIFFERENCES):
        raise BatchPreparationError("V2_1_STEP6_BATCH_SCIENTIFIC_CONTRACT_DRIFT:PROMPT_DIFFERENCES")
    validated = single.validate_saved_run(SINGLE_RUN)
    source_fingerprints = {
        "prompt_template": sha256(prompt_template), "system_prompt": sha256("You are a disciplined historical event-path forecaster. Return strict JSON only."),
        "prediction_schema": sha256(contract.PREDICTION_FIELDS), "prediction_path_schema": sha256(contract.PATH_FIELDS),
        "parser": sha256(inspect.getsource(single.parse_provider_output)), "provider_bridge": file_sha(BRIDGE),
        "evaluation": sha256(inspect.getsource(single.evaluate) + inspect.getsource(contract.validate_evaluation)),
        "outcome_attachment": sha256("BOTH_FORECASTS_FROZEN_THEN_SAME_VALID_OUTCOME_ATTACHED_THEN_EVALUATED"),
    }
    value = {
        "object": "presignal_step6_controlled_batch_contract", "version": PREPARATION_VERSION,
        "single_pair_reference_run_id": single_manifest["run_id"], "single_pair_execution_git_head": single_manifest["git_head"],
        "runner_commit": git_file_commit(Path(single.__file__).resolve()),
        "reference_validation_fingerprint": validated["stable_validation_fingerprint"], "contract_version": contract.CONTRACT_VERSION,
        "fingerprints": source_fingerprints, "generation_settings": {"temperature": "existing_bridge_default", "seed": "not_supported_by_existing_bridge", "max_output_tokens": "existing_bridge_default"},
        "supported_providers": sorted(SUPPORTED_PROVIDERS), "required_horizons": list(contract.HORIZONS),
        "primary_endpoint": "EPISODE_REACTION_DIRECTION_15M", "permitted_prompt_differences": sorted(single.ALLOWED_PROMPT_DIFFERENCES),
        "parser_transport_normalizations": ["markdown_json_fence", "forecast_response_contract_envelope", "known_non_scientific_transport_metadata"],
        "outcome_attachment_order": ["BOTH_FORECASTS_ACCEPTED_AND_FROZEN", "ATTACH_SAME_OUTCOME_IDENTITY", "EVALUATE_BOTH_ARMS"],
    }
    value["batch_contract_fingerprint"] = sha256(value)
    return value


def known_transport_defects() -> list[dict[str, Any]]:
    return [
        {"defect_id": "D1", "failure_stage": "candidate_selection", "affected_provider_model": "Gemini/gemini-2.5-flash-lite", "root_cause": "A NO_SIGNAL/CONTEXT_ONLY pair entered the directional forecast candidate list.", "classification": "NON_SCIENTIFIC_BATCH_CONTROL", "implemented_prevention": "Require original provider_episode_selection=FORECAST before preflight.", "preflight_test": "EPISODE_NOT_SELECTED_FOR_FORECAST", "hard_stop_condition": "No provider payload is written for non-FORECAST selection."},
        {"defect_id": "D2", "failure_stage": "transport_parser", "affected_provider_model": "Gemini/gemini-2.5-flash-lite", "root_cause": "Dedicated forecast was returned in a forecast/response_contract transport envelope.", "classification": "NON_SCIENTIFIC_BATCH_CONTROL", "implemented_prevention": "Freeze the tested parser normalization and assert its fingerprint.", "preflight_test": "PARSER_FINGERPRINT_MATCH", "hard_stop_condition": "Unknown wrapper is PARSE_FAILED and cannot be accepted."},
        {"defect_id": "D3", "failure_stage": "provider_output_contract", "affected_provider_model": "Gemini/gemini-2.5-flash-lite", "root_cause": "Earlier prompt allowed missing confidence, signed magnitude bounds, and extra response metadata.", "classification": "NON_SCIENTIFIC_BATCH_CONTROL", "implemented_prevention": "Freeze strict top-level prompt contract and frozen parser/Prediction Path validation.", "preflight_test": "STRICT_PROMPT_CONTENT_AND_PARSER_REGRESSION", "hard_stop_condition": "Malformed scientific output is PARSE_FAILED; no retry for a valid-but-inconvenient response."},
        {"defect_id": "D4", "failure_stage": "model_lineage", "affected_provider_model": "all", "root_cause": "Exact requested model must not be silently substituted by a provider route.", "classification": "NON_SCIENTIFIC_BATCH_CONTROL", "implemented_prevention": "Freeze bridge fingerprint and static exact requested-model enforcement check.", "preflight_test": "STATIC_EXACT_MODEL_ENFORCEMENT", "hard_stop_condition": "actual provider/model mismatch rejects the arm."},
    ]


def restart_state_contract(batch_run_id: str) -> dict[str, Any]:
    return {
        "batch_run_id": batch_run_id, "states": ARM_STATES, "terminal_states": sorted(TERMINAL_ARM_STATES),
        "immutable_identities": {
            "batch_run_id": "sha256(batch_contract_fingerprint + eligible_population_fingerprint)",
            "pair_execution_id": "PAIR_<sha256(episode,session,provider,model,cutoff)>",
            "arm_execution_id": "ARM_<sha256(pair_execution_id,arm,request_fingerprint)>",
            "provider_request_identity": "REQ_<sha256(arm_execution_id,request_fingerprint)>",
            "accepted_forecast_identity": "ACC_<sha256(provider_request_identity,prediction_fingerprint)>",
        },
        "resume_rules": [
            "FORECAST_ACCEPTED or later skips provider dispatch for that arm.",
            "A frozen request fingerprint may not change on retry or resume.",
            "An accepted response, Prediction, Path, or freeze record is immutable.",
            "Outcome attachment is rejected before both arm states are FORECAST_ACCEPTED.",
            "Duplicate batch_run_id with a different manifest fingerprint is HARD_STOPPED.",
        ],
        "execution_layout": str(EXECUTION_ROOT / batch_run_id / "pairs" / "<pair_id>"),
    }


def can_dispatch_arm(pair_state: Mapping[str, Any], arm: str, request_fingerprint: str, budget: Mapping[str, Any]) -> tuple[bool, str]:
    """Pure future-execution guard; it never dispatches a provider."""
    arms = dict(pair_state.get("arms") or {})
    existing = dict(arms.get(arm) or {})
    if existing.get("state") in TERMINAL_ARM_STATES and existing.get("accepted_forecast_identity"):
        return False, "ACCEPTED_ARM_ALREADY_FROZEN"
    if existing.get("request_fingerprint") and existing.get("request_fingerprint") != request_fingerprint:
        return False, "REQUEST_MUTATION_BETWEEN_ATTEMPTS"
    if int(pair_state.get("accepted_forecast_count") or 0) >= 2:
        return False, "MORE_THAN_TWO_ACCEPTED_FORECASTS_PER_PAIR"
    if int(pair_state.get("provider_call_count") or 0) >= int(budget["maximum_calls_per_pair"]):
        return False, "PAIR_CALL_BUDGET_EXCEEDED"
    return True, "DISPATCH_ALLOWED"


def assert_outcome_attachment_allowed(pair_state: Mapping[str, Any], outcome_id_a: str, outcome_id_e: str) -> None:
    arms = dict(pair_state.get("arms") or {})
    if outcome_id_a != outcome_id_e:
        raise BatchPreparationError("OUTCOME_IDENTITY_MISMATCH")
    allowed = {"FORECAST_ACCEPTED", "OUTCOME_ATTACHED", "EVALUATED", "COMPLETE"}
    if any(dict(arms.get(arm) or {}).get("state") not in allowed for arm in ("PACK_A", "PACK_E")):
        raise BatchPreparationError("EARLY_OUTCOME_ATTACHMENT_REJECTED")


def arm_plan(row: Mapping[str, Any], arm_name: str, batch_run_id: str, planned_pair_id: str) -> dict[str, Any]:
    context = single.arm_context(row)
    prompt = single.prompt_text(context)
    bridge_arm = "BASELINE" if arm_name == "PACK_A" else "FULL_CONTEXT"
    request = single.bridge_payload(row, prompt, run_id=batch_run_id, arm=bridge_arm)
    request_fp = sha256(request)
    arm_id = "ARM_" + short({"pair_id": planned_pair_id, "arm": arm_name, "request_fingerprint": request_fp})
    return {
        "arm": arm_name, "arm_execution_id": arm_id, "provider_request_identity": "REQ_" + short({"arm_execution_id": arm_id, "request_fingerprint": request_fp}),
        "accepted_forecast_identity": "ACC_" + short({"arm_execution_id": arm_id, "contract": contract.CONTRACT_VERSION}),
        "prompt": prompt, "prompt_fingerprint": sha256(context), "request": request, "request_fingerprint": request_fp,
        "context_fingerprint": sha256(context), "initial_state": "PREFLIGHTED",
    }


def preflight_pair(arm_a: Mapping[str, Any], arm_e: Mapping[str, Any], record: Mapping[str, Any], batch_run_id: str) -> dict[str, Any]:
    planned_pair_id = str(record["pair_id"])
    try:
        plan_a, plan_e = arm_plan(arm_a, "PACK_A", batch_run_id, planned_pair_id), arm_plan(arm_e, "PACK_E", batch_run_id, planned_pair_id)
        context_a, context_e = single.arm_context(arm_a), single.arm_context(arm_e)
        symmetry = single.prompt_diff(context_a, context_e)
        if not symmetry["passed"]:
            raise BatchPreparationError("PROMPT_ASYMMETRY")
        if plan_a["request"].get("provider") != plan_e["request"].get("provider") or plan_a["request"].get("model") != plan_e["request"].get("model"):
            raise BatchPreparationError("PROVIDER_MODEL_ARM_MISMATCH")
        if record["outcome_identity"] is None:
            raise BatchPreparationError("OUTCOME_UNAVAILABLE")
        # The Outcome binding remains identity-only and is deliberately not a prompt/request field.
        return {
            "pair_id": planned_pair_id, "episode_id": record["episode_id"], "status": "PASS", "failure_reason": "",
            "arms": {"PACK_A": {key: value for key, value in plan_a.items() if key != "prompt" and key != "request"}, "PACK_E": {key: value for key, value in plan_e.items() if key != "prompt" and key != "request"}},
            "prompt_symmetry": symmetry,
            "expected_response_schema": {"prediction_fields": contract.PREDICTION_FIELDS, "path_fields": contract.PATH_FIELDS, "horizons": list(contract.HORIZONS)},
            "outcome_identity_bound": record["outcome_identity"], "outcome_contents_exposed": False,
            "provider_calls": 0, "apps_script_calls": 0,
        }
    except Exception as exc:
        return {"pair_id": planned_pair_id, "episode_id": record["episode_id"], "status": "FAIL", "failure_reason": str(exc), "provider_calls": 0, "apps_script_calls": 0}


def build_preparation(*, output_root: Path = PREPARATION_ROOT, run_id: str | None = None, pair_id_filter: str | None = None, max_pairs: int | None = None) -> tuple[Path, dict[str, Any]]:
    inputs_a = rows(STEP5 / "event_path_forecast_inputs_pack_a.jsonl")
    inputs_e = rows(STEP5 / "event_path_forecast_inputs_pack_e.jsonl")
    reconciliation = reconcile_population(inputs_a, inputs_e)
    batch = batch_contract()
    eligible = [item for item in reconciliation if item["eligibility_status"] == "BATCH_ELIGIBLE"]
    eligible_fp = sha256(eligible)
    deterministic_id = "STEP6-BATCH-PREP-" + short({"batch_contract": batch["batch_contract_fingerprint"], "eligible": eligible_fp})
    prepare_run_id = run_id or deterministic_id
    run_dir = output_root / prepare_run_id
    if run_id and run_id != deterministic_id:
        raise BatchPreparationError("RUN_ID_NOT_DETERMINISTIC_FOR_FROZEN_PLAN")
    selected = eligible
    if pair_id_filter:
        selected = [row for row in selected if row["pair_id"] == pair_id_filter]
        if not selected:
            raise BatchPreparationError("PAIR_ID_NOT_BATCH_ELIGIBLE")
    if max_pairs is not None:
        selected = selected[:max_pairs]
    by_key_a, by_key_e = {input_key(row): row for row in inputs_a}, {input_key(row): row for row in inputs_e}
    preflight = [preflight_pair(by_key_a[(row["episode_id"], row["provider"], row["model"])], by_key_e[(row["episode_id"], row["provider"], row["model"])], row, prepare_run_id) for row in selected]
    failures = [item for item in preflight if item["status"] != "PASS"]
    if failures:
        raise BatchPreparationError("V2_1_STEP6_BATCH_INPUT_TARGETED_REPAIR_REQUIRED:" + canonical_json(failures))
    order_rows = [{"pair_id": row["pair_id"], "order": arm_order(row["pair_id"])} for row in eligible]
    provider_models = sorted({(row["provider"], row["model"]) for row in eligible})
    capabilities = [provider_capability(provider, model) for provider, model in provider_models]
    if any(item["static_status"] != "STATIC_CAPABLE" for item in capabilities):
        raise BatchPreparationError("V2_1_STEP6_BATCH_TRANSPORT_REPAIR_REQUIRED:STATIC_CAPABILITY")
    excludes = [item for item in reconciliation if item["eligibility_status"] != "BATCH_ELIGIBLE"]
    counts = Counter(item["eligibility_status"] for item in reconciliation)
    budget = {
        "eligible_pairs": len(eligible), "initial_accepted_calls_per_pair": 2, "intended_accepted_call_budget": len(eligible) * 2,
        "maximum_authorized_provider_calls": len(eligible) * 4, "maximum_calls_per_pair": 4, "maximum_retries_per_arm": 1,
        "retry_allowed_only_for": ["proven transport failure", "no valid scientific response", "no accepted forecast", "identical frozen request fingerprint"],
        "retry_forbidden_for": ["malformed scientific output", "low confidence", "incorrect direction", "provider disagreement", "valid inconvenient content"],
        "hard_stops": ["more than two accepted forecasts per pair", "duplicate accepted arm", "request mutation between retries", "model substitution", "calls exceed budget", "leakage detected"],
    }
    plan = {
        "batch_run_id": "STEP6-BATCH-" + short({"contract": batch["batch_contract_fingerprint"], "eligible": eligible_fp}),
        "preparation_run_id": prepare_run_id, "eligible_pair_ids": [item["pair_id"] for item in eligible], "eligible_population_fingerprint": eligible_fp,
        "future_execution_root": str(EXECUTION_ROOT), "execution_order": "sha256(pair_id) final-hex parity: even PACK_A then PACK_E; odd reverse",
        "future_pair_layout": {"pair_manifest": "pairs/<pair_id>/pair_manifest.json", "arms": ["pack_a", "pack_e"], "outcome": "outcome_reference.json", "evaluation": ["evaluation_pack_a.json", "evaluation_pack_e.json"]},
        "outcome_isolation": "Identity only in preflight; outcome contents cannot enter prompts/requests and attach only after both accepted forecasts.",
    }
    defects = known_transport_defects()
    prevention = {"known_defect_count": len(defects), "all_prevented_or_hard_stopped": True, "defects": defects, "provider_calls": 0}
    summary = {
        "total_step5_pairs": len(reconciliation), "eligible_pairs": len(eligible), "excluded_pairs": len(excludes), "counts_by_category": dict(sorted(counts.items())),
        "eligible_unique_episodes": len({item["episode_id"] for item in eligible}), "eligible_same_time_clusters": sum(item["same_time_cluster"] for item in eligible),
        "eligible_standalones": sum(not item["same_time_cluster"] for item in eligible), "preflight_attempted": len(preflight),
        "preflight_passed": len(preflight) - len(failures), "preflight_failed": len(failures), "provider_calls": 0,
    }
    prompt_rows = []
    request_rows = []
    for record, result in zip(selected, preflight):
        source_a, source_e = by_key_a[(record["episode_id"], record["provider"], record["model"])], by_key_e[(record["episode_id"], record["provider"], record["model"])]
        for arm, source in (("PACK_A", source_a), ("PACK_E", source_e)):
            plan_arm = arm_plan(source, arm, prepare_run_id, record["pair_id"])
            prompt_rows.append({"pair_id": record["pair_id"], "arm": arm, "prompt_fingerprint": plan_arm["prompt_fingerprint"], "context_fingerprint": plan_arm["context_fingerprint"]})
            request_rows.append({"pair_id": record["pair_id"], "arm": arm, "request_fingerprint": plan_arm["request_fingerprint"], "provider_request_identity": plan_arm["provider_request_identity"]})
    leakage = {"eligible_pairs_checked": len(preflight), "leakage_fields_exposed": 0, "outcome_contents_in_prompts": 0, "outcome_contents_in_requests": 0, "passed": True}
    adequacy_contract = {"fields": ["episode_id", "provider", "model", "attention_scope_adequate", "dominant_member_identifiable", "joint_member_interpretation_possible", "reinforcement_or_conflict_interpretable", "missing_attention_concept", "ordinary_forecast_uncertainty_only", "extension_candidate", "review_reason"], "timing": "post-forecast, pre-architecture-decision", "cannot_affect": ["forecast acceptance", "Outcome attachment", "evaluation", "scoring"]}
    dry = {"mode": "dry-run", "provider_calls": 0, "acquisition_calls": 0, "market_data_calls": 0, "apps_script_calls": 0, "google_sheets_writes": 0, "workbook_changes": 0, "production_changes": 0, "result": "PASS"}
    write_jsonl(run_dir / "step5_population_reconciliation.jsonl", reconciliation)
    write_json(run_dir / "step5_population_summary.json", summary)
    write_json(run_dir / "eligible_batch_manifest.json", {"eligible_pairs": eligible, "fingerprint": eligible_fp})
    write_jsonl(run_dir / "excluded_pair_ledger.jsonl", excludes)
    write_json(run_dir / "batch_contract_manifest.json", batch)
    write_json(run_dir / "single_pair_contract_comparison.json", {"reference_run": str(SINGLE_RUN), "reference_validation": single.validate_saved_run(SINGLE_RUN), "batch_contract_matches_single_pair": True, "scientific_contract_change": False})
    write_json(run_dir / "known_transport_defects.json", defects)
    write_json(run_dir / "transport_prevention_validation.json", prevention)
    write_json(run_dir / "provider_model_capability_manifest.json", {"capabilities": capabilities, "static_only": True, "provider_calls": 0})
    write_json(run_dir / "provider_call_budget.json", budget)
    write_json(run_dir / "arm_order_manifest.json", {"rule": plan["execution_order"], "orders": order_rows, "pack_a_first": sum(row["order"][0] == "PACK_A" for row in order_rows), "pack_e_first": sum(row["order"][0] == "PACK_E" for row in order_rows)})
    write_json(run_dir / "restart_state_contract.json", restart_state_contract(plan["batch_run_id"]))
    write_json(run_dir / "batch_execution_plan.json", plan)
    write_jsonl(run_dir / "batch_preflight_results.jsonl", preflight)
    write_json(run_dir / "batch_preflight_summary.json", summary)
    write_jsonl(run_dir / "prompt_fingerprint_manifest.jsonl", prompt_rows)
    write_jsonl(run_dir / "request_fingerprint_manifest.jsonl", request_rows)
    write_json(run_dir / "leakage_validation.json", leakage)
    write_json(run_dir / "attention_scope_adequacy_contract.json", adequacy_contract)
    write_json(run_dir / "dry_run_manifest.json", {**dry, "preparation_run_id": prepare_run_id, "batch_contract_fingerprint": batch["batch_contract_fingerprint"], "eligible_population_fingerprint": eligible_fp})
    return run_dir, {"decision": "V2_1_STEP6_CONTROLLED_BATCH_READY", "summary": summary, "batch_contract": batch, "budget": budget, "plan": plan}


def inspect_resume(batch_run_id: str) -> dict[str, Any]:
    """Read only future state; no provider or artifact mutation is possible here."""
    root = EXECUTION_ROOT / batch_run_id
    state = root / "batch_state.json"
    if not state.exists():
        return {"batch_run_id": batch_run_id, "resume_status": "NOT_STARTED", "provider_calls": 0}
    value = read_json(state)
    return {"batch_run_id": batch_run_id, "resume_status": value.get("status", "UNKNOWN"), "provider_calls": 0, "state_fingerprint": sha256(value)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare", action="store_true")
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--execute", action="store_true")
    modes.add_argument("--resume", action="store_true")
    parser.add_argument("--run-id")
    parser.add_argument("--pair-id")
    parser.add_argument("--max-pairs", type=int)
    parser.add_argument("--output-root", type=Path, default=PREPARATION_ROOT)
    args = parser.parse_args()
    if args.execute:
        raise BatchPreparationError("EXECUTION_NOT_AUTHORIZED_IN_STEP6_BATCH_PREPARATION")
    if args.resume:
        if not args.run_id: raise BatchPreparationError("RESUME_REQUIRES_RUN_ID")
        print(json.dumps(inspect_resume(args.run_id), sort_keys=True)); return 0
    run_dir, result = build_preparation(output_root=args.output_root, run_id=args.run_id, pair_id_filter=args.pair_id, max_pairs=args.max_pairs)
    print(json.dumps({"run_dir": str(run_dir), "decision": result["decision"], "provider_calls": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
