#!/usr/bin/env python3
"""Execute targeted OpenAI/Anthropic provider-yield validation for Round 1."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import prepare_presignal_v21_historical_baseline_prevalidation_v1_1 as prevalidation
from automation import presignal_v21_event_path_contract_v1_1 as contract
from automation import run_presignal_v21_single_event_path_pair_v1_1 as step6
from automation.execute_presignal_v21_historical_validation_batch_v1_1 import (
    BRIDGE_FUNCTION,
    PREVALIDATION_RUN_ID,
    REQUEST_SCHEMA_VERSION,
    TOKEN_ENV,
    TOKEN_PATH,
    ValidationExecutionError,
    outcome_preflight,
    pair_classification,
    sha256,
    terminal_from_transport,
    token_sha256,
    verify_bridge_transport,
    write_json,
    write_jsonl,
)
from automation.google_clients import build_script_service, default_script_id, load_credentials, run_script_function_with_metadata

STEP5 = ROOT / "outputs" / "presignal_v21_step5_reuse"
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_pure_prediction_historical_baseline"
EXPANDED_RUN_ID = "PPHB-R1-EXPANDED-VALIDATION-20260726T123833Z-c6afc7952cca"
POST_EXPANDED_RELEASE_TS = "2024-05-14T15:30:00Z"
TARGET_EPISODE_COUNT = 8
TARGET_STANDALONE = 4
TARGET_CLUSTER = 4
PROVIDERS = ("Anthropic", "OpenAI")
MODEL_BY_PROVIDER = {
    "Anthropic": "claude-haiku-4-5",
    "OpenAI": "gpt-4o-mini-2024-07-18",
}
EXPANDED_AND_SMALL_EPISODES = {
    "EP_EVENT_ccf7e8031b0d9b2e2443",
    "EP_BATCH_bd5b0d22e01fddb86cf1",
    "EP_BATCH_6fb320e5e8c5931f2373",
    "EP_EVENT_2d777c70a07c631e5f03",
    "EP_BATCH_80bbf91b9afbc592880f",
    "EP_BATCH_48e817a6f98121eb04dd",
    "EP_EVENT_fbb37fea272c4e76546e",
    "EP_EVENT_697fa043068a1f61838f",
    "EP_EVENT_1b999628b864d9bebb06",
    "EP_EVENT_870dc1a1acc371a30f04",
    "EP_BATCH_a170305f20ad150c2335",
    "EP_BATCH_4bf004a6c160d4763e06",
    "EP_EVENT_92769da428b1a43350e5",
    "EP_BATCH_4c1237b4fdba265e575f",
    "EP_BATCH_6bf769aa6603093027fc",
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def path_ref(path: Path) -> str:
    return str(path.relative_to(ROOT))


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_inputs() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return (
        read_jsonl(STEP5 / "event_path_forecast_inputs_pack_a.jsonl"),
        read_jsonl(STEP5 / "event_path_forecast_inputs_pack_e.jsonl"),
    )


def key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (str(row["episode_id"]), str(row["provider"]), str(row["model"]))


def pair_rows(
    pack_a_rows: list[dict[str, Any]],
    pack_e_rows: list[dict[str, Any]],
) -> dict[tuple[str, str, str], tuple[dict[str, Any], dict[str, Any]]]:
    by_a = {key(row): row for row in pack_a_rows}
    by_e = {key(row): row for row in pack_e_rows}
    return {identity: (by_a[identity], by_e[identity]) for identity in sorted(set(by_a) & set(by_e))}


def indicator_label(row: Mapping[str, Any]) -> str:
    members = list(row.get("episode_members") or [])
    if not members:
        return "UNKNOWN"
    primary = next((member for member in members if member.get("structural_component_role") == "STRUCTURAL_PRIMARY"), members[0])
    return str(primary.get("indicator_name") or "UNKNOWN")


def build_selected_episode_manifest(
    *,
    population_rows: list[dict[str, Any]],
    pair_index: Mapping[tuple[str, str, str], tuple[dict[str, Any], dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    after_ts = parse_iso(POST_EXPANDED_RELEASE_TS)
    population_by_episode = {row["episode_id"]: row for row in population_rows}
    provider_pairs_by_episode: dict[str, dict[str, tuple[str, str]]] = defaultdict(dict)
    episode_meta: dict[str, dict[str, Any]] = {}
    for (episode_id, provider, model), (row_a, row_e) in sorted(pair_index.items()):
        if provider not in PROVIDERS:
            continue
        if episode_id in EXPANDED_AND_SMALL_EPISODES:
            continue
        if parse_iso(row_a["release_ts"]) <= after_ts:
            continue
        provider_pairs_by_episode[episode_id][provider] = (provider, model)
        episode_meta.setdefault(episode_id, {
            "episode_id": episode_id,
            "release_ts": row_a["release_ts"],
            "episode_type": "cluster" if len(row_a["episode_members"]) > 1 else "standalone",
            "member_count": len(row_a["episode_members"]),
            "event_family": indicator_label(row_a),
        })
    candidates: list[dict[str, Any]] = []
    for episode_id, providers in provider_pairs_by_episode.items():
        row = population_by_episode[episode_id]
        if row["population_status"] != "ELIGIBLE":
            continue
        if set(providers) != set(PROVIDERS):
            continue
        candidates.append({
            "episode_id": episode_id,
            "release_ts": episode_meta[episode_id]["release_ts"],
            "episode_type": episode_meta[episode_id]["episode_type"],
            "member_count": episode_meta[episode_id]["member_count"],
            "same_time_cluster_flag": episode_meta[episode_id]["episode_type"] == "cluster",
            "event_family": episode_meta[episode_id]["event_family"],
            "provider_model_pairs": [{"provider": provider, "model": providers[provider][1]} for provider in PROVIDERS],
            "provider_eligibility": list(PROVIDERS),
            "pack_a_ready": True,
            "pack_e_ready": True,
            "outcome_ready": row["legacy_outcome_status"] == "VALID",
            "historical_attention_status": row["historical_attention_status"],
            "population_status": row["population_status"],
            "pack_compatibility_status": row["pack_compatibility_status"],
            "request_compatibility_status": row["request_compatibility_status"],
            "parent_session_status": row["parent_session_status"],
        })
    candidates.sort(key=lambda row: (row["release_ts"], row["episode_id"]))
    standalone = [row for row in candidates if row["episode_type"] == "standalone"]
    cluster = [row for row in candidates if row["episode_type"] == "cluster"]
    if len(candidates) < TARGET_EPISODE_COUNT:
        selected = list(candidates)
    else:
        selected = standalone[:TARGET_STANDALONE] + cluster[:TARGET_CLUSTER]
        selected.sort(key=lambda row: (row["release_ts"], row["episode_id"]))
    frozen = {
        "selection_protocol": "EARLIEST_COMMON_OPENAI_ANTHROPIC_EPISODES_AFTER_EXPANDED_WINDOW_WITH_PACK_AE_AND_V1_1_OUTCOME",
        "selection_after_release_ts": POST_EXPANDED_RELEASE_TS,
        "target_episode_count": TARGET_EPISODE_COUNT,
        "target_standalone_count": TARGET_STANDALONE,
        "target_cluster_count": TARGET_CLUSTER,
        "available_common_episode_count": len(candidates),
        "available_common_standalone_count": len(standalone),
        "available_common_cluster_count": len(cluster),
        "selected_episode_ids": [row["episode_id"] for row in selected],
        "shortfall_reason": None if len(selected) == TARGET_EPISODE_COUNT else "INSUFFICIENT_COMMON_OPENAI_ANTHROPIC_EPISODES_AFTER_EXPANDED_WINDOW",
    }
    return selected, frozen


def build_outcomes_for_selected(selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    legacy_rows = {row["episode_id"]: row for row in read_jsonl(prevalidation.LEGACY_OUTCOMES)}
    acquisition_ts = now()
    outcomes = [prevalidation.convert_legacy_outcome(legacy_rows[row["episode_id"]], acquisition_ts=acquisition_ts) for row in selected]
    return outcomes


def build_ledger(
    *,
    selected: list[dict[str, Any]],
    pair_index: Mapping[tuple[str, str, str], tuple[dict[str, Any], dict[str, Any]]],
    run_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ledger: list[dict[str, Any]] = []
    pair_symmetry: list[dict[str, Any]] = []
    call_index = 0
    for episode in selected:
        for provider_model in episode["provider_model_pairs"]:
            provider = provider_model["provider"]
            model = provider_model["model"]
            row_a, row_e = pair_index[(episode["episode_id"], provider, model)]
            context_a = step6.arm_context(row_a)
            context_e = step6.arm_context(row_e)
            diff = step6.prompt_diff(context_a, context_e)
            pair_symmetry.append({
                "episode_id": episode["episode_id"],
                "provider": provider,
                "model": model,
                "prompt_symmetry_passed": diff["passed"],
                "differences": diff["differences"],
                "allowed_differences": diff["allowed_differences"],
            })
            if not diff["passed"]:
                raise ValidationExecutionError("TARGETED_PROMPT_SYMMETRY_FAILURE:" + canonical_json(diff["differences"]))
            for pack_arm, row, context in (("PACK_A", row_a, context_a), ("PACK_E", row_e, context_e)):
                call_index += 1
                prompt = step6.prompt_text(context)
                payload = step6.bridge_payload(row, prompt, run_id=run_dir.name, arm="BASELINE" if pack_arm == "PACK_A" else "FULL_CONTEXT")
                ledger.append({
                    "call_index": call_index,
                    "call_id": f"TPV_CALL_{call_index:02d}_{hashlib.sha256((episode['episode_id'] + provider + model + pack_arm).encode()).hexdigest()[:16]}",
                    "episode_id": episode["episode_id"],
                    "release_ts": row["release_ts"],
                    "episode_type": episode["episode_type"],
                    "event_family": episode["event_family"],
                    "provider": provider,
                    "model": model,
                    "pack_arm": pack_arm,
                    "historical_cutoff_ts": row["forecast_cutoff_ts"],
                    "input_snapshot_id": row["input_fingerprint"],
                    "pack_fingerprint": None if pack_arm == "PACK_A" else row["pack_fingerprint"],
                    "prompt_fingerprint": sha256(context),
                    "request_fingerprint": sha256(payload),
                    "contract": contract.CONTRACT_VERSION,
                    "schema": contract.SCHEMA_VERSION,
                    "request_schema_version": REQUEST_SCHEMA_VERSION,
                    "attempt_limit": 1,
                })
    return ledger, pair_symmetry


def anthropic_prompt_audit() -> dict[str, Any]:
    run = OUTPUT_ROOT / EXPANDED_RUN_ID
    forecasts = read_jsonl(run / "canonical_forecasts" / "forecast_index.jsonl")
    reasons = [
        str(row["no_signal_reason"])
        for row in forecasts
        if row["provider"] == "Anthropic" and row["no_signal_flag"]
    ]
    lower = "\n".join(reasons).lower()
    return {
        "source_run_id": EXPANDED_RUN_ID,
        "anthropic_no_signal_count": len(reasons),
        "dominant_patterns": {
            "missing_primary_driver": sum("primary_driver" in reason.lower() or "primary driver" in reason.lower() for reason in reasons),
            "missing_required_context": sum(any(token in reason.lower() for token in ("not available", "unavailable", "not supplied", "policy_rejected")) for reason in reasons),
            "insufficient_signal_strength": sum(any(token in reason.lower() for token in ("insufficient", "cannot", "no directional", "cannot be established")) for reason in reasons),
            "context_only_event": sum(any(token in reason.lower() for token in ("context_only", "low direct market impact", "minimal direct market impact", "negligible direct")) for reason in reasons),
        },
        "interpretation": "Expanded-run Anthropic NO_SIGNAL responses consistently cite unavailable primary drivers, missing must-have context, and low direct USDJPY relevance. This pattern looks like a strict interpretation of abstention under incomplete causal context rather than random transport or parser failure.",
        "clarification_rationale": "Prompt should clarify that uncertainty alone does not require NO_SIGNAL and that a lower-confidence directional forecast is valid when one direction remains more defensible than alternatives.",
    }


def openai_reversal_audit() -> dict[str, Any]:
    run = OUTPUT_ROOT / EXPANDED_RUN_ID
    transport = read_jsonl(run / "transport_results.jsonl")
    failures = [row for row in transport if row["provider"] == "OpenAI" and row["terminal_state"] == "SCHEMA_FAILURE"]
    details = []
    for row in failures:
        raw = read_json(ROOT / row["raw_response_path"])
        payload = raw["transport_result"]["result"]["raw_output"]
        if isinstance(payload, str):
            parsed = json.loads(payload)
        else:
            parsed = payload
        details.append({
            "call_id": row["call_id"],
            "episode_id": row["episode_id"],
            "pack_arm": row["pack_arm"],
            "terminal_error": row["error"],
            "provider_expected_reversal_flag": parsed.get("expected_reversal_flag"),
            "provider_expected_reversal_horizon_min": parsed.get("expected_reversal_horizon_min"),
            "accepted_rule": {
                "directional_forecast_requires_boolean_reversal_flag": True,
                "if_expected_reversal_flag_true_horizon_must_be": [15, 30, 60],
                "if_expected_reversal_flag_false_horizon_must_be": None,
            },
        })
    return {
        "source_run_id": EXPANDED_RUN_ID,
        "openai_schema_failures": details,
        "interpretation": "Observed failures are prompt-adherence issues on frozen reversal-field semantics, not transport or parser ambiguity.",
    }


def classify_no_signal_reason(text: str | None) -> str:
    if not text:
        return "UNCLASSIFIED"
    value = text.lower()
    if any(token in value for token in ("not available", "unavailable", "not supplied", "policy_rejected", "missing", "blocked by policy", "critical information gap", "must-have information unavailable")):
        return "MISSING_REQUIRED_CONTEXT"
    if any(token in value for token in ("context_only", "low direct market impact", "minimal direct market impact", "negligible direct", "irrelevant", "insufficient standalone signal")):
        return "EVENT_IRRELEVANT_TO_USDJPY"
    if any(token in value for token in ("competing forces", "conflicting", "mixed signal", "reassess", "compete", "cross-currents")):
        return "CONFLICTING_INPUTS"
    if any(token in value for token in ("low magnitude", "too small", "negligible move", "minimal move")):
        return "LOW_EXPECTED_MAGNITUDE"
    if any(token in value for token in ("uncertainty", "uncertain", "confidence falls below", "confidence cannot exceed", "below threshold")):
        return "HIGH_UNCERTAINTY"
    if any(token in value for token in ("insufficient directional", "no directional", "cannot establish directional", "no defensible directional hypothesis", "insufficient signal strength")):
        return "INSUFFICIENT_DIRECTIONAL_EDGE"
    return "OTHER"


def persist_precall(
    *,
    run_dir: Path,
    source_prevalidation_manifest: dict[str, Any],
    selected: list[dict[str, Any]],
    selected_frozen: dict[str, Any],
    ledger: list[dict[str, Any]],
    pair_symmetry: list[dict[str, Any]],
    pair_index: Mapping[tuple[str, str, str], tuple[dict[str, Any], dict[str, Any]]],
    outcomes: list[dict[str, Any]],
    prompt_audit: dict[str, Any],
    reversal_audit: dict[str, Any],
) -> None:
    for folder in (
        "raw_provider_responses",
        "canonical_forecasts",
        "normalization_audits",
        "evaluations",
        "pair_comparisons",
    ):
        (run_dir / folder).mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "source_prevalidation_manifest.json", source_prevalidation_manifest)
    write_json(run_dir / "selection_protocol.json", selected_frozen)
    write_jsonl(run_dir / "selected_episode_manifest.jsonl", selected)
    write_jsonl(run_dir / "call_ledger.jsonl", ledger)
    write_json(run_dir / "provider_prompt_audit.json", {"anthropic_audit": prompt_audit, "openai_reversal_audit": reversal_audit})
    write_json(run_dir / "prompt_changes.json", {
        "contract_changed": False,
        "schema_changed": False,
        "changes": [
            "Clarified that uncertainty alone does not require NO_SIGNAL.",
            "Clarified that lower-confidence directional forecasts are valid when one direction is more defensible.",
            "Clarified reversal-field rule: true => horizon 15/30/60, false => null.",
        ],
    })
    write_jsonl(run_dir / "outcomes.jsonl", outcomes)
    write_json(run_dir / "pack_symmetry.json", {"pairs": pair_symmetry})
    for item in ledger:
        row_a, row_e = pair_index[(item["episode_id"], item["provider"], item["model"])]
        row = row_a if item["pack_arm"] == "PACK_A" else row_e
        write_json(
            run_dir / f"prompt_{item['call_index']:02d}_{item['episode_id']}_{item['provider']}_{item['pack_arm']}.json",
            {"context": step6.arm_context(row), "prompt": step6.prompt_text(step6.arm_context(row))},
        )


def execute_run(output_root: Path = OUTPUT_ROOT) -> tuple[Path, dict[str, Any]]:
    source_prevalidation_manifest = read_json(OUTPUT_ROOT / "latest_prevalidation_manifest.json")
    if source_prevalidation_manifest.get("prevalidation_run_id") != PREVALIDATION_RUN_ID:
        raise ValidationExecutionError("TARGETED_PREVALIDATION_RUN_ID_MISMATCH")
    token_before = token_sha256()
    bridge_info = verify_bridge_transport()
    _, outcome_preflight_check = outcome_preflight(source_prevalidation_manifest)
    pack_a_rows, pack_e_rows = load_inputs()
    pairs = pair_rows(pack_a_rows, pack_e_rows)
    population_rows = read_jsonl(OUTPUT_ROOT / PREVALIDATION_RUN_ID / "population_admission.jsonl")
    selected, selected_frozen = build_selected_episode_manifest(population_rows=population_rows, pair_index=pairs)
    outcomes = build_outcomes_for_selected(selected)
    outcomes_by_episode = {row["episode_id"]: row for row in outcomes}
    prompt_audit = anthropic_prompt_audit()
    reversal_audit = openai_reversal_audit()
    run_id = "PPHB-R1-TARGETED-PROVIDER-VALIDATION-" + now().replace(":", "").replace("-", "") + "-" + hashlib.sha256((EXPANDED_RUN_ID + "|" + git_head()).encode()).hexdigest()[:12]
    run_dir = output_root / run_id
    ledger, pair_symmetry = build_ledger(selected=selected, pair_index=pairs, run_dir=run_dir)
    persist_precall(
        run_dir=run_dir,
        source_prevalidation_manifest=source_prevalidation_manifest,
        selected=selected,
        selected_frozen=selected_frozen,
        ledger=ledger,
        pair_symmetry=pair_symmetry,
        pair_index=pairs,
        outcomes=outcomes,
        prompt_audit=prompt_audit,
        reversal_audit=reversal_audit,
    )
    write_json(run_dir / "outcome_preflight_check.json", outcome_preflight_check)
    write_json(run_dir / "transport_verification.json", bridge_info)

    os.environ[TOKEN_ENV] = str(TOKEN_PATH)
    script_service = build_script_service(load_credentials(False, token_path=TOKEN_PATH, persist_refresh=False), 240)
    script_id = default_script_id()

    call_results: list[dict[str, Any]] = []
    forecasts: list[dict[str, Any]] = []
    forecast_paths: list[dict[str, Any]] = []
    evaluations: list[dict[str, Any]] = []
    pair_comparisons: list[dict[str, Any]] = []
    no_signal_rows: list[dict[str, Any]] = []
    stop_reason: str | None = None
    ledger_lookup = {(item["episode_id"], item["provider"], item["model"], item["pack_arm"]): item for item in ledger}

    for episode in selected:
        episode_id = episode["episode_id"]
        outcome = outcomes_by_episode[episode_id]
        episode_forecasts: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
        episode_paths: dict[tuple[str, str], dict[str, list[dict[str, Any]]]] = {}
        episode_evaluations: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
        for provider_model in episode["provider_model_pairs"]:
            provider = provider_model["provider"]
            model = provider_model["model"]
            row_a, row_e = pairs[(episode_id, provider, model)]
            for pack_arm, row in (("PACK_A", row_a), ("PACK_E", row_e)):
                item = ledger_lookup[(episode_id, provider, model, pack_arm)]
                context = step6.arm_context(row)
                prompt = step6.prompt_text(context)
                payload = step6.bridge_payload(row, prompt, run_id=run_id, arm="BASELINE" if pack_arm == "PACK_A" else "FULL_CONTEXT")
                result = run_script_function_with_metadata(script_service, script_id, BRIDGE_FUNCTION, [dict(payload)], dev_mode=True)
                raw_path = run_dir / "raw_provider_responses" / f"{item['call_index']:02d}_{episode_id}_{provider}_{pack_arm}.json"
                write_json(raw_path, {"request": payload, "transport_result": result})
                terminal = {
                    "call_id": item["call_id"],
                    "episode_id": episode_id,
                    "release_ts": item["release_ts"],
                    "episode_type": item["episode_type"],
                    "event_family": item["event_family"],
                    "provider": provider,
                    "model": model,
                    "pack_arm": pack_arm,
                    "transport_ok": result["ok"],
                    "transport_elapsed_ms": result["elapsed_ms"],
                    "transport_classification": result["classification"],
                    "transport_request": result["request"],
                    "raw_response_path": path_ref(raw_path),
                    "attempted": True,
                }
                if not result["ok"]:
                    terminal["terminal_state"] = "PROVIDER_RUNTIME_FAILURE"
                    terminal["error"] = result["classification"]["message"]
                    call_results.append(terminal)
                    continue
                bridge_result = result["result"]
                terminal["bridge_result_status"] = bridge_result.get("status")
                terminal["actual_provider"] = bridge_result.get("actual_provider")
                terminal["actual_model"] = bridge_result.get("actual_model")
                transport_terminal = terminal_from_transport(bridge_result)
                if transport_terminal == "MODEL_MISMATCH":
                    terminal["terminal_state"] = "MODEL_MISMATCH"
                    terminal["error"] = bridge_result.get("error")
                    call_results.append(terminal)
                    stop_reason = "MODEL_SUBSTITUTION"
                    break
                if transport_terminal != "RESPONSE_RECEIVED":
                    terminal["terminal_state"] = transport_terminal
                    terminal["error"] = bridge_result.get("error")
                    call_results.append(terminal)
                    continue
                try:
                    normalized, audit = step6.normalize_provider_output(bridge_result.get("raw_output"))
                    write_json(run_dir / "normalization_audits" / f"{item['call_index']:02d}_{episode_id}_{provider}_{pack_arm}.json", audit)
                    prediction, paths = step6.response_to_contract(
                        normalized,
                        row,
                        run_id=run_id,
                        created_ts=str(bridge_result.get("completed_timestamp") or now()),
                        raw_output=bridge_result.get("raw_output"),
                        bridge_result=bridge_result,
                    )
                    evaluation = step6.evaluate(prediction, paths, outcome, generated_ts=now())
                    write_json(run_dir / "canonical_forecasts" / f"{item['call_index']:02d}_{episode_id}_{provider}_{pack_arm}.json", prediction)
                    write_json(run_dir / "evaluations" / f"{item['call_index']:02d}_{episode_id}_{provider}_{pack_arm}.json", evaluation)
                    terminal["terminal_state"] = "VALID_NO_SIGNAL" if prediction["no_signal_flag"] else "COMPLETED_DIRECTIONAL_FORECAST"
                    terminal["prediction_id"] = prediction["prediction_id"]
                    episode_forecasts.setdefault((provider, model), {})[pack_arm] = prediction
                    episode_paths.setdefault((provider, model), {})[pack_arm] = paths
                    episode_evaluations.setdefault((provider, model), {})[pack_arm] = evaluation
                    forecasts.append(prediction)
                    forecast_paths.extend(paths)
                    evaluations.append(evaluation)
                    if prediction["no_signal_flag"]:
                        other_pack = "FULL_CONTEXT" if prediction["information_arm"] == "BASELINE" else "BASELINE"
                        no_signal_rows.append({
                            "provider": provider,
                            "model": model,
                            "episode_id": episode_id,
                            "pack": prediction["information_arm"],
                            "confidence": prediction["confidence"],
                            "reason_code": "UNSPECIFIED",
                            "reason_text": prediction["no_signal_reason"],
                            "derived_reason": classify_no_signal_reason(prediction["no_signal_reason"]),
                            "other_pack_also_no_signal": None,
                            "event_family": episode["event_family"],
                            "episode_type": episode["episode_type"],
                            "other_pack": other_pack,
                        })
                except Exception as exc:
                    terminal["terminal_state"] = "SCHEMA_FAILURE"
                    terminal["error"] = str(exc)
                call_results.append(terminal)
            if stop_reason:
                break
        if stop_reason:
            break
        for (provider, model), by_arm in episode_forecasts.items():
            prediction_a = by_arm.get("PACK_A")
            prediction_e = by_arm.get("PACK_E")
            eval_a = episode_evaluations.get((provider, model), {}).get("PACK_A")
            eval_e = episode_evaluations.get((provider, model), {}).get("PACK_E")
            compare = {
                "episode_id": episode_id,
                "provider": provider,
                "model": model,
                "t5_pair_classification": pair_classification(
                    None if not eval_a or prediction_a["no_signal_flag"] else eval_a["direction_5m_ok"],
                    None if not eval_e or prediction_e["no_signal_flag"] else eval_e["direction_5m_ok"],
                ),
                "t15_pair_classification": pair_classification(
                    None if not eval_a or prediction_a["no_signal_flag"] else eval_a["direction_15m_ok"],
                    None if not eval_e or prediction_e["no_signal_flag"] else eval_e["direction_15m_ok"],
                ),
                "pair_transition": (
                    "BOTH_NO_SIGNAL" if prediction_a and prediction_e and prediction_a["no_signal_flag"] and prediction_e["no_signal_flag"]
                    else "A_NO_SIGNAL_TO_E_DIRECTIONAL" if prediction_a and prediction_e and prediction_a["no_signal_flag"] and not prediction_e["no_signal_flag"]
                    else "A_DIRECTIONAL_TO_E_NO_SIGNAL" if prediction_a and prediction_e and not prediction_a["no_signal_flag"] and prediction_e["no_signal_flag"]
                    else "BOTH_DIRECTIONAL" if prediction_a and prediction_e and not prediction_a["no_signal_flag"] and not prediction_e["no_signal_flag"]
                    else "PAIR_NOT_EVALUABLE"
                ),
                "shared_outcome_id": outcome["outcome_id"],
            }
            pair_comparisons.append(compare)
            write_json(run_dir / "pair_comparisons" / f"{episode_id}_{provider}_{model}.json", compare)

    token_after = token_sha256()
    write_json(run_dir / "token_checksum_audit.json", {"before_sha256": token_before, "after_sha256": token_after, "unchanged": token_before == token_after})

    # Fill cross-pack no_signal awareness after all predictions exist.
    by_key = {(f["episode_id"], f["provider"], f["model"], f["information_arm"]): f for f in forecasts}
    for row in no_signal_rows:
        other = by_key.get((row["episode_id"], row["provider"], row["model"], row["other_pack"]))
        row["other_pack_also_no_signal"] = bool(other and other["no_signal_flag"])
        row.pop("other_pack", None)
    write_jsonl(run_dir / "no_signal_reason_classification.jsonl", no_signal_rows)

    authoritative_valid_forecasts = [row for row in forecasts if row["status"] in {"VALID", "NO_SIGNAL"}]
    directional = [row for row in forecasts if not row["no_signal_flag"]]

    provider_yield: dict[str, Any] = {"by_provider": {}, "by_provider_pack": {}, "overall": {}}
    for provider in PROVIDERS:
        subset = [row for row in authoritative_valid_forecasts if row["provider"] == provider]
        directional_count = sum(not row["no_signal_flag"] for row in subset)
        provider_yield["by_provider"][provider] = {
            "authoritative_valid_forecasts": len(subset),
            "completed_directional_forecasts": directional_count,
            "valid_no_signal_forecasts": len(subset) - directional_count,
            "directional_yield": directional_count / len(subset) if subset else None,
        }
        for arm in ("BASELINE", "FULL_CONTEXT"):
            arm_subset = [row for row in subset if row["information_arm"] == arm]
            arm_directional = sum(not row["no_signal_flag"] for row in arm_subset)
            provider_yield["by_provider_pack"][f"{provider}|{arm}"] = {
                "authoritative_valid_forecasts": len(arm_subset),
                "completed_directional_forecasts": arm_directional,
                "valid_no_signal_forecasts": len(arm_subset) - arm_directional,
                "directional_yield": arm_directional / len(arm_subset) if arm_subset else None,
            }
    provider_yield["overall"] = {
        "authoritative_valid_forecasts": len(authoritative_valid_forecasts),
        "completed_directional_forecasts": len(directional),
        "valid_no_signal_forecasts": len(authoritative_valid_forecasts) - len(directional),
        "directional_yield": len(directional) / len(authoritative_valid_forecasts) if authoritative_valid_forecasts else None,
    }
    write_json(run_dir / "provider_yield_analysis.json", provider_yield)

    call_reconciliation = {
        "authorized_calls": len(ledger),
        "attempted_calls": len(call_results),
        "precall_blocks": len(ledger) - len(call_results),
        "terminal_counts": dict(sorted(Counter(row["terminal_state"] for row in call_results).items())),
    }
    forecast_reconciliation = {
        "expected_forecast_arms": len(ledger),
        "completed_directional_forecasts": sum(row["terminal_state"] == "COMPLETED_DIRECTIONAL_FORECAST" for row in call_results),
        "valid_no_signals": sum(row["terminal_state"] == "VALID_NO_SIGNAL" for row in call_results),
        "schema_failures": sum(row["terminal_state"] == "SCHEMA_FAILURE" for row in call_results),
        "runtime_failures": sum(row["terminal_state"] == "PROVIDER_RUNTIME_FAILURE" for row in call_results),
        "provider_rejections": sum(row["terminal_state"] == "PROVIDER_REJECTION" for row in call_results),
        "model_mismatches": sum(row["terminal_state"] == "MODEL_MISMATCH" for row in call_results),
    }
    evaluation_reconciliation = {
        "authoritative_valid_forecasts": len(authoritative_valid_forecasts),
        "evaluated_directional_forecasts": len(directional),
        "evaluated_no_signal_forecasts": len(authoritative_valid_forecasts) - len(directional),
        "explicit_evaluation_exclusions": len(call_results) - len(authoritative_valid_forecasts),
    }
    write_json(run_dir / "call_reconciliation.json", call_reconciliation)
    write_json(run_dir / "forecast_arm_reconciliation.json", forecast_reconciliation)
    write_json(run_dir / "evaluation_reconciliation.json", evaluation_reconciliation)
    write_jsonl(run_dir / "transport_results.jsonl", call_results)

    inclusion = {
        "OpenAI": None,
        "Anthropic": None,
    }
    write_json(run_dir / "provider_inclusion_decision.json", inclusion)

    report = {
        "run_id": run_id,
        "git_head": git_head(),
        "contract_version": contract.CONTRACT_VERSION,
        "schema_version": contract.SCHEMA_VERSION,
        "selected_episode_count": len(selected),
        "target_episode_count": TARGET_EPISODE_COUNT,
        "shortfall_reason": selected_frozen["shortfall_reason"],
        "attempted_calls": len(call_results),
        "terminal_counts": call_reconciliation["terminal_counts"],
        "directional_forecasts": len(directional),
        "valid_no_signal_forecasts": len(authoritative_valid_forecasts) - len(directional),
        "schema_failures": forecast_reconciliation["schema_failures"],
        "stop_reason": stop_reason,
    }
    write_json(run_dir / "run_manifest.json", report)
    (run_dir / "targeted_validation_report.md").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return run_dir, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    run_dir, report = execute_run(args.output_root)
    print(json.dumps({"run_dir": str(run_dir), "report": report}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
