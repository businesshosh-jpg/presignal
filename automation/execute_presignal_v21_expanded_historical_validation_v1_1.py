#!/usr/bin/env python3
"""Execute the bounded 12-Episode expanded historical validation batch via Apps Script."""
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
SMALL_VALIDATION_FINAL_HEAD = "e97f6723d3dffc20014bfd2cbd851f3b71e31943"
SOURCE_PREVALIDATION_RUN_ID = "PPHB-R1-PREVALIDATION-20260726T090136Z-254f4ac151673853e5c7"
SOURCE_OUTCOME_PATH = OUTPUT_ROOT / SOURCE_PREVALIDATION_RUN_ID / "outcomes_v1_1" / "outcome_rows.jsonl"
SMALL_VALIDATION_FINAL_EPISODE = "EP_BATCH_6fb320e5e8c5931f2373"
SMALL_VALIDATION_FINAL_RELEASE_TS = "2024-05-09T12:30:00Z"
EPISODE_TARGET = 12
STANDALONE_TARGET = 6
CLUSTER_TARGET = 6


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
    result: dict[tuple[str, str, str], tuple[dict[str, Any], dict[str, Any]]] = {}
    for identity in sorted(set(by_a) & set(by_e)):
        result[identity] = (by_a[identity], by_e[identity])
    return result


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
    after_ts = parse_iso(SMALL_VALIDATION_FINAL_RELEASE_TS)
    eligible_rows = [
        row for row in population_rows
        if row["population_status"] == "ELIGIBLE" and parse_iso(row["release_ts"]) > after_ts
    ]
    pair_map: dict[str, list[tuple[str, str]]] = defaultdict(list)
    episode_meta: dict[str, dict[str, Any]] = {}
    for (episode_id, provider, model), (row_a, row_e) in sorted(pair_index.items()):
        if parse_iso(row_a["release_ts"]) <= after_ts:
            continue
        pair_map[episode_id].append((provider, model))
        episode_meta.setdefault(episode_id, {
            "episode_id": episode_id,
            "release_ts": row_a["release_ts"],
            "episode_type": "cluster" if len(row_a["episode_members"]) > 1 else "standalone",
            "same_time_cluster_flag": len(row_a["episode_members"]) > 1,
            "member_count": len(row_a["episode_members"]),
            "event_family": indicator_label(row_a),
        })
    eligible_episodes: list[dict[str, Any]] = []
    for row in eligible_rows:
        episode_id = row["episode_id"]
        providers = sorted(pair_map.get(episode_id, []))
        eligible_episodes.append({
            "episode_id": episode_id,
            "release_ts": row["release_ts"],
            "same_time_cluster_flag": bool(row["same_time_cluster_flag"]),
            "episode_type": "cluster" if row["same_time_cluster_flag"] else "standalone",
            "member_count": int(row["member_event_count"]),
            "event_family": episode_meta.get(episode_id, {}).get("event_family", "UNKNOWN"),
            "provider_model_pairs": [{"provider": provider, "model": model} for provider, model in providers],
            "provider_pair_count": len(providers),
            "callable": bool(providers),
            "provider_eligibility": [provider for provider, _ in providers],
            "pack_a_ready": bool(providers),
            "pack_e_ready": bool(providers),
            "outcome_ready": row["legacy_outcome_status"] == "VALID",
            "historical_attention_status": row["historical_attention_status"],
            "population_status": row["population_status"],
            "pack_compatibility_status": row["pack_compatibility_status"],
            "request_compatibility_status": row["request_compatibility_status"],
            "parent_session_status": row["parent_session_status"],
        })
    standalone = [row for row in eligible_episodes if row["episode_type"] == "standalone" and row["callable"]]
    clustered = [row for row in eligible_episodes if row["episode_type"] == "cluster" and row["callable"]]
    selected = standalone[:STANDALONE_TARGET] + clustered[:CLUSTER_TARGET]
    selected.sort(key=lambda row: (row["release_ts"], row["episode_id"]))
    if len(selected) != EPISODE_TARGET:
        raise ValidationExecutionError("EXPANDED_SELECTION_COUNT_INVALID")
    if sum(row["episode_type"] == "standalone" for row in selected) != STANDALONE_TARGET:
        raise ValidationExecutionError("EXPANDED_SELECTION_STANDALONE_INVALID")
    if sum(row["episode_type"] == "cluster" for row in selected) != CLUSTER_TARGET:
        raise ValidationExecutionError("EXPANDED_SELECTION_CLUSTER_INVALID")
    frozen = {
        "selection_protocol": "EARLIEST_6_CALLABLE_STANDALONE_PLUS_EARLIEST_6_CALLABLE_CLUSTER_AFTER_SMALL_VALIDATION_THEN_CHRONOLOGICAL_SORT",
        "selection_after_release_ts": SMALL_VALIDATION_FINAL_RELEASE_TS,
        "selection_after_episode_id": SMALL_VALIDATION_FINAL_EPISODE,
        "episode_target": EPISODE_TARGET,
        "standalone_target": STANDALONE_TARGET,
        "cluster_target": CLUSTER_TARGET,
        "callable_cluster_gaps_before_selected": [
            {
                "episode_id": row["episode_id"],
                "release_ts": row["release_ts"],
                "reason": "NO_SHARED_PROVIDER_PACK_AE_INTERSECTION",
            }
            for row in eligible_episodes
            if row["episode_type"] == "cluster"
            and not row["callable"]
            and parse_iso(row["release_ts"]) > after_ts
            and parse_iso(row["release_ts"]) < parse_iso(selected[0]["release_ts"])
        ],
        "selected_episode_ids": [row["episode_id"] for row in selected],
    }
    return selected, frozen


def build_outcomes_for_selected(selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    legacy_rows = {row["episode_id"]: row for row in read_jsonl(prevalidation.LEGACY_OUTCOMES)}
    acquisition_ts = now()
    outcomes = [prevalidation.convert_legacy_outcome(legacy_rows[row["episode_id"]], acquisition_ts=acquisition_ts) for row in selected]
    if len({row["outcome_id"] for row in outcomes}) != len(outcomes):
        raise ValidationExecutionError("EXPANDED_OUTCOME_DUPLICATE_IDENTITY")
    if sorted({row["immediate_impulse_outcome_state"] for row in outcomes}) != ["APPROXIMATION_ONLY"]:
        raise ValidationExecutionError("EXPANDED_IMMEDIATE_IMPULSE_STATE_INVALID")
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
        episode_id = episode["episode_id"]
        for provider_model in episode["provider_model_pairs"]:
            provider = provider_model["provider"]
            model = provider_model["model"]
            row_a, row_e = pair_index[(episode_id, provider, model)]
            context_a = step6.arm_context(row_a)
            context_e = step6.arm_context(row_e)
            diff = step6.prompt_diff(context_a, context_e)
            pair_symmetry.append({
                "episode_id": episode_id,
                "provider": provider,
                "model": model,
                "prompt_symmetry_passed": diff["passed"],
                "differences": diff["differences"],
                "allowed_differences": diff["allowed_differences"],
            })
            if not diff["passed"]:
                raise ValidationExecutionError("EXPANDED_PROMPT_SYMMETRY_FAILURE:" + canonical_json(diff["differences"]))
            for pack_arm, row, context in (("PACK_A", row_a, context_a), ("PACK_E", row_e, context_e)):
                call_index += 1
                prompt = step6.prompt_text(context)
                payload = step6.bridge_payload(row, prompt, run_id=run_dir.name, arm="BASELINE" if pack_arm == "PACK_A" else "FULL_CONTEXT")
                ledger.append({
                    "call_index": call_index,
                    "call_id": f"EXP_CALL_{call_index:02d}_{hashlib.sha256((episode_id + provider + model + pack_arm).encode()).hexdigest()[:16]}",
                    "episode_id": episode_id,
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
                    "planned_output_path": path_ref(run_dir / "raw_provider_responses" / f"{call_index:02d}_{episode_id}_{provider}_{pack_arm}.json"),
                    "prompt_text_path": path_ref(run_dir / "prompts" / f"{call_index:02d}_{episode_id}_{provider}_{pack_arm}.txt"),
                })
    if len(ledger) != 60:
        raise ValidationExecutionError("EXPANDED_LEDGER_COUNT_UNEXPECTED")
    return ledger, pair_symmetry


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
) -> None:
    for folder in (
        "input_snapshots",
        "pack_symmetry",
        "prompts",
        "raw_provider_responses",
        "normalization_audits",
        "canonical_forecasts",
        "outcomes",
        "evaluations",
        "pair_comparisons",
    ):
        (run_dir / folder).mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "source_prevalidation_manifest.json", source_prevalidation_manifest)
    write_json(run_dir / "selection_protocol.json", selected_frozen)
    write_jsonl(run_dir / "selected_episode_manifest.jsonl", selected)
    write_jsonl(run_dir / "call_ledger.jsonl", ledger)
    write_json(run_dir / "pack_symmetry" / "pair_symmetry.json", {"pairs": pair_symmetry})
    write_jsonl(run_dir / "outcomes" / "outcome_rows.jsonl", outcomes)
    for item in ledger:
        row_a, row_e = pair_index[(item["episode_id"], item["provider"], item["model"])]
        row = row_a if item["pack_arm"] == "PACK_A" else row_e
        context = step6.arm_context(row)
        prompt = step6.prompt_text(context)
        payload = step6.bridge_payload(row, prompt, run_id=run_dir.name, arm="BASELINE" if item["pack_arm"] == "PACK_A" else "FULL_CONTEXT")
        prefix = f"{item['call_index']:02d}_{item['episode_id']}_{item['provider']}_{item['pack_arm']}"
        write_json(run_dir / "input_snapshots" / f"{prefix}.json", {"input_row": row, "context": context, "payload": payload})
        (run_dir / "prompts" / f"{prefix}.txt").write_text(prompt + "\n")


def no_signal_reason_fields(prediction: Mapping[str, Any], transport_row: Mapping[str, Any], prompt_row: Mapping[str, Any]) -> dict[str, Any]:
    reason = prediction.get("no_signal_reason")
    if isinstance(reason, Mapping):
        reason_code = reason.get("code")
        reason_text = reason.get("reason") or reason.get("text") or reason.get("message")
        insufficient = reason.get("insufficient_evidence") or reason.get("missing_evidence") or reason.get("gaps")
    else:
        reason_code = "UNSPECIFIED"
        reason_text = reason
        insufficient = None
    return {
        "provider": prediction["provider"],
        "model": prediction["model"],
        "episode_id": prediction["episode_id"],
        "pack": prediction["information_arm"],
        "confidence": prediction["confidence"],
        "reason_code": reason_code or "UNSPECIFIED",
        "reason_text": reason_text,
        "insufficient_evidence": insufficient,
        "event_family": str(prompt_row.get("event_family") or "UNKNOWN") if isinstance(prompt_row, Mapping) else "UNKNOWN",
        "transport_terminal_state": transport_row["terminal_state"],
    }


def pair_transition(pack_a_prediction: Mapping[str, Any] | None, pack_e_prediction: Mapping[str, Any] | None) -> str:
    if not pack_a_prediction or not pack_e_prediction:
        return "PAIR_NOT_EVALUABLE"
    a_signal = not pack_a_prediction["no_signal_flag"]
    e_signal = not pack_e_prediction["no_signal_flag"]
    if not a_signal and e_signal:
        return "A_NO_SIGNAL_TO_E_DIRECTIONAL"
    if a_signal and not e_signal:
        return "A_DIRECTIONAL_TO_E_NO_SIGNAL"
    if not a_signal and not e_signal:
        return "BOTH_NO_SIGNAL"
    return "BOTH_DIRECTIONAL"


def execute_run(output_root: Path = OUTPUT_ROOT) -> tuple[Path, dict[str, Any]]:
    current_head = git_head()
    source_prevalidation_manifest = read_json(OUTPUT_ROOT / "latest_prevalidation_manifest.json")
    if source_prevalidation_manifest.get("prevalidation_run_id") != PREVALIDATION_RUN_ID:
        raise ValidationExecutionError("EXPANDED_PREVALIDATION_RUN_ID_MISMATCH")
    if path_ref(SOURCE_OUTCOME_PATH) != source_prevalidation_manifest.get("outcomes_v1_1_path"):
        raise ValidationExecutionError("EXPANDED_PREVALIDATION_OUTCOME_PATH_MISMATCH")

    token_before = token_sha256()
    bridge_info = verify_bridge_transport()
    outcome_preflight_rows, outcome_preflight_check = outcome_preflight(source_prevalidation_manifest)
    pack_a_rows, pack_e_rows = load_inputs()
    pairs = pair_rows(pack_a_rows, pack_e_rows)
    population_rows = read_jsonl(OUTPUT_ROOT / SOURCE_PREVALIDATION_RUN_ID / "population_admission.jsonl")
    selected, selected_frozen = build_selected_episode_manifest(population_rows=population_rows, pair_index=pairs)
    outcomes = build_outcomes_for_selected(selected)
    outcomes_by_episode = {row["episode_id"]: row for row in outcomes}
    run_id = "PPHB-R1-EXPANDED-VALIDATION-" + now().replace(":", "").replace("-", "") + "-" + hashlib.sha256((SOURCE_PREVALIDATION_RUN_ID + "|" + git_head()).encode()).hexdigest()[:12]
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
    )
    write_json(run_dir / "outcomes" / "source_outcome_preflight_check.json", outcome_preflight_check)
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
    episode_summary: list[dict[str, Any]] = []

    for episode in selected:
        episode_id = episode["episode_id"]
        outcome = outcomes_by_episode[episode_id]
        write_json(run_dir / "outcomes" / f"{episode_id}.json", outcome)
        episode_terminal: list[dict[str, Any]] = []
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
                prefix = f"{item['call_index']:02d}_{episode_id}_{provider}_{pack_arm}"
                result = run_script_function_with_metadata(script_service, script_id, BRIDGE_FUNCTION, [dict(payload)], dev_mode=True)
                raw_path = run_dir / "raw_provider_responses" / f"{prefix}.json"
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
                    "request_fingerprint": item["request_fingerprint"],
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
                    episode_terminal.append(terminal)
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
                    episode_terminal.append(terminal)
                    call_results.append(terminal)
                    stop_reason = "MODEL_SUBSTITUTION"
                    break
                if transport_terminal != "RESPONSE_RECEIVED":
                    terminal["terminal_state"] = transport_terminal
                    terminal["error"] = bridge_result.get("error")
                    episode_terminal.append(terminal)
                    call_results.append(terminal)
                    continue
                try:
                    normalized, audit = step6.normalize_provider_output(bridge_result.get("raw_output"))
                    write_json(run_dir / "normalization_audits" / f"{prefix}.json", audit)
                    prediction, paths = step6.response_to_contract(
                        normalized,
                        row,
                        run_id=run_id,
                        created_ts=str(bridge_result.get("completed_timestamp") or now()),
                        raw_output=bridge_result.get("raw_output"),
                        bridge_result=bridge_result,
                    )
                    write_json(run_dir / "canonical_forecasts" / f"{prefix}.json", prediction)
                    write_jsonl(run_dir / "canonical_forecasts" / f"{prefix}_paths.jsonl", paths)
                    evaluation = step6.evaluate(prediction, paths, outcome, generated_ts=now())
                    write_json(run_dir / "evaluations" / f"{prefix}.json", evaluation)
                    episode_forecasts.setdefault((provider, model), {})[pack_arm] = prediction
                    episode_paths.setdefault((provider, model), {})[pack_arm] = paths
                    episode_evaluations.setdefault((provider, model), {})[pack_arm] = evaluation
                    forecasts.append(prediction)
                    forecast_paths.extend(paths)
                    evaluations.append(evaluation)
                    terminal["terminal_state"] = "VALID_NO_SIGNAL" if prediction["no_signal_flag"] else "COMPLETED_DIRECTIONAL_FORECAST"
                    terminal["prediction_id"] = prediction["prediction_id"]
                    terminal["provider_immediate_window_status"] = audit["provider_immediate_window_status"]
                    terminal["provider_returned_immediate_window_seconds"] = audit["provider_returned_immediate_window_seconds"]
                    terminal["canonical_immediate_window_seconds"] = audit["canonical_immediate_window_seconds"]
                    if prediction["no_signal_flag"]:
                        no_signal_row = no_signal_reason_fields(prediction, terminal, item)
                        no_signal_row["episode_type"] = episode["episode_type"]
                        no_signal_row["event_family"] = episode["event_family"]
                        no_signal_rows.append(no_signal_row)
                except Exception as exc:
                    terminal["terminal_state"] = "SCHEMA_FAILURE"
                    terminal["error"] = str(exc)
                episode_terminal.append(terminal)
                call_results.append(terminal)
            if stop_reason:
                break
        if stop_reason:
            break

        for (provider, model), by_arm in episode_forecasts.items():
            prediction_a = by_arm.get("PACK_A")
            prediction_e = by_arm.get("PACK_E")
            evaluation_a = episode_evaluations.get((provider, model), {}).get("PACK_A")
            evaluation_e = episode_evaluations.get((provider, model), {}).get("PACK_E")
            compare = {
                "episode_id": episode_id,
                "provider": provider,
                "model": model,
                "baseline_prediction_id": prediction_a["prediction_id"] if prediction_a else None,
                "full_context_prediction_id": prediction_e["prediction_id"] if prediction_e else None,
                "shared_outcome_id": outcome["outcome_id"],
                "pair_transition": pair_transition(prediction_a, prediction_e),
                "t5_pair_classification": pair_classification(
                    None if not evaluation_a or prediction_a["no_signal_flag"] else evaluation_a["direction_5m_ok"],
                    None if not evaluation_e or prediction_e["no_signal_flag"] else evaluation_e["direction_5m_ok"],
                ),
                "t15_pair_classification": pair_classification(
                    None if not evaluation_a or prediction_a["no_signal_flag"] else evaluation_a["direction_15m_ok"],
                    None if not evaluation_e or prediction_e["no_signal_flag"] else evaluation_e["direction_15m_ok"],
                ),
                "pack_a_no_signal_flag": None if not prediction_a else prediction_a["no_signal_flag"],
                "pack_e_no_signal_flag": None if not prediction_e else prediction_e["no_signal_flag"],
            }
            pair_comparisons.append(compare)
            write_json(run_dir / "pair_comparisons" / f"{episode_id}_{provider}_{model}.json", compare)

        episode_summary.append({
            "episode_id": episode_id,
            "completed": True,
            "terminal_counts": dict(sorted(Counter(row["terminal_state"] for row in episode_terminal).items())),
            "shared_outcome_id": outcome["outcome_id"],
        })

    token_after = token_sha256()
    write_json(run_dir / "token_checksum_audit.json", {"before_sha256": token_before, "after_sha256": token_after, "unchanged": token_before == token_after})

    attempted_calls = len(call_results)
    terminal_counts = dict(sorted(Counter(row["terminal_state"] for row in call_results).items()))
    provider_counts = dict(sorted(Counter(row["provider"] for row in call_results).items()))
    pack_counts = dict(sorted(Counter(row["pack_arm"] for row in call_results).items()))
    exact_model_enforcement = {
        "attempted_calls": attempted_calls,
        "all_exact_models_matched": all(
            row.get("actual_model") in {None, row["model"]} and row.get("actual_provider") in {None, row["provider"]}
            for row in call_results
        ),
        "providers_attempted": provider_counts,
        "pack_attempts": pack_counts,
    }

    authoritative_valid_forecasts = [
        forecast for forecast in forecasts
        if forecast["status"] in {"VALID", "NO_SIGNAL"}
    ]
    directional_forecasts = [forecast for forecast in forecasts if not forecast["no_signal_flag"]]
    evaluation_by_prediction = {row["prediction_id"]: row for row in evaluations}

    directional_yield_by_provider_pack: dict[str, dict[str, int | float]] = {}
    for provider in sorted({row["provider"] for row in forecasts}):
        for arm in ("BASELINE", "FULL_CONTEXT"):
            subset = [row for row in authoritative_valid_forecasts if row["provider"] == provider and row["information_arm"] == arm]
            directional = sum(not row["no_signal_flag"] for row in subset)
            if subset:
                directional_yield_by_provider_pack[f"{provider}|{arm}"] = {
                    "authoritative_valid_forecasts": len(subset),
                    "completed_directional_forecasts": directional,
                    "valid_no_signal_forecasts": len(subset) - directional,
                    "directional_yield": directional / len(subset),
                }

    directional_yield_by_provider: dict[str, dict[str, int | float]] = {}
    for provider in sorted({row["provider"] for row in forecasts}):
        subset = [row for row in authoritative_valid_forecasts if row["provider"] == provider]
        directional = sum(not row["no_signal_flag"] for row in subset)
        directional_yield_by_provider[provider] = {
            "authoritative_valid_forecasts": len(subset),
            "completed_directional_forecasts": directional,
            "valid_no_signal_forecasts": len(subset) - directional,
            "directional_yield": directional / len(subset) if subset else None,
        }

    directional_yield_by_pack: dict[str, dict[str, int | float]] = {}
    for arm in ("BASELINE", "FULL_CONTEXT"):
        subset = [row for row in authoritative_valid_forecasts if row["information_arm"] == arm]
        directional = sum(not row["no_signal_flag"] for row in subset)
        directional_yield_by_pack[arm] = {
            "authoritative_valid_forecasts": len(subset),
            "completed_directional_forecasts": directional,
            "valid_no_signal_forecasts": len(subset) - directional,
            "directional_yield": directional / len(subset) if subset else None,
        }

    episode_type_by_id = {row["episode_id"]: row["episode_type"] for row in selected}
    family_by_id = {row["episode_id"]: row["event_family"] for row in selected}
    directional_yield_by_episode_type: dict[str, dict[str, int | float]] = {}
    for episode_type in ("standalone", "cluster"):
        subset = [row for row in authoritative_valid_forecasts if episode_type_by_id[row["episode_id"]] == episode_type]
        directional = sum(not row["no_signal_flag"] for row in subset)
        directional_yield_by_episode_type[episode_type] = {
            "authoritative_valid_forecasts": len(subset),
            "completed_directional_forecasts": directional,
            "valid_no_signal_forecasts": len(subset) - directional,
            "directional_yield": directional / len(subset) if subset else None,
        }

    no_signal_analysis = {
        "total_no_signal_forecasts": len(no_signal_rows),
        "by_provider": dict(sorted(Counter(row["provider"] for row in no_signal_rows).items())),
        "by_pack": dict(sorted(Counter(row["pack"] for row in no_signal_rows).items())),
        "by_provider_pack": dict(sorted(Counter(f"{row['provider']}|{row['pack']}" for row in no_signal_rows).items())),
        "by_episode_type": dict(sorted(Counter(row["episode_type"] for row in no_signal_rows).items())),
        "by_event_family": dict(sorted(Counter(row["event_family"] for row in no_signal_rows).items())),
        "by_reason_code": dict(sorted(Counter(row["reason_code"] for row in no_signal_rows).items())),
        "rows": no_signal_rows,
    }
    directional_yield_analysis = {
        "overall": {
            "authoritative_valid_forecasts": len(authoritative_valid_forecasts),
            "completed_directional_forecasts": len(directional_forecasts),
            "valid_no_signal_forecasts": len(authoritative_valid_forecasts) - len(directional_forecasts),
            "directional_yield": (len(directional_forecasts) / len(authoritative_valid_forecasts)) if authoritative_valid_forecasts else None,
        },
        "by_provider": directional_yield_by_provider,
        "by_pack": directional_yield_by_pack,
        "by_provider_pack": directional_yield_by_provider_pack,
        "by_episode_type": directional_yield_by_episode_type,
    }
    write_json(run_dir / "no_signal_analysis.json", no_signal_analysis)
    write_json(run_dir / "directional_yield_analysis.json", directional_yield_analysis)

    t5_rows = []
    t15_rows = []
    t30_rows = []
    t60_rows = []
    for forecast in directional_forecasts:
        evaluation = evaluation_by_prediction[forecast["prediction_id"]]
        base = {
            "episode_id": forecast["episode_id"],
            "provider": forecast["provider"],
            "model": forecast["model"],
            "pack": forecast["information_arm"],
            "episode_type": episode_type_by_id[forecast["episode_id"]],
            "event_family": family_by_id[forecast["episode_id"]],
        }
        t5_rows.append({
            **base,
            "direction_ok": evaluation["direction_5m_ok"],
            "signed_realized_pips": outcomes_by_episode[forecast["episode_id"]]["pips_5m"],
            "range_covered": evaluation["t5_range_covered"],
            "range_distance_error_pips": evaluation["t5_range_distance_error_pips"],
            "midpoint_absolute_pip_error": evaluation["t5_midpoint_absolute_error_pips"],
        })
        t15_rows.append({
            **base,
            "direction_ok": evaluation["direction_15m_ok"],
            "signed_realized_pips": outcomes_by_episode[forecast["episode_id"]]["pips_15m"],
            "range_covered": evaluation["magnitude_15m_error"] == 0.0,
            "range_distance_error_pips": evaluation["magnitude_15m_error"],
            "midpoint_absolute_pip_error": evaluation["magnitude_15m_error"],
        })
        t30_rows.append({
            **base,
            "direction_ok": evaluation["direction_30m_ok"],
            "signed_realized_pips": outcomes_by_episode[forecast["episode_id"]]["pips_30m"],
        })
        t60_rows.append({
            **base,
            "direction_ok": evaluation["direction_60m_ok"],
            "signed_realized_pips": outcomes_by_episode[forecast["episode_id"]]["pips_60m"],
        })

    transport_reconciliation = {
        "authorized_calls": len(ledger),
        "attempted_calls": attempted_calls,
        "precall_blocks": len(ledger) - attempted_calls,
        "provider_returned_responses": sum(bool(row["transport_ok"]) for row in call_results),
        "transport_failures": sum(not row["transport_ok"] for row in call_results),
        "terminal_counts": terminal_counts,
    }
    forecast_reconciliation = {
        "expected_forecast_arms": len(ledger),
        "completed_directional_forecasts": sum(row["terminal_state"] == "COMPLETED_DIRECTIONAL_FORECAST" for row in call_results),
        "valid_no_signals": sum(row["terminal_state"] == "VALID_NO_SIGNAL" for row in call_results),
        "provider_rejections": sum(row["terminal_state"] == "PROVIDER_REJECTION" for row in call_results),
        "runtime_failures": sum(row["terminal_state"] == "PROVIDER_RUNTIME_FAILURE" for row in call_results),
        "schema_failures": sum(row["terminal_state"] == "SCHEMA_FAILURE" for row in call_results),
        "lineage_failures": 0,
        "persistence_failures": 0,
        "model_mismatches": sum(row["terminal_state"] == "MODEL_MISMATCH" for row in call_results),
    }
    evaluation_reconciliation = {
        "authoritative_valid_forecasts": len(authoritative_valid_forecasts),
        "evaluated_directional_forecasts": len(directional_forecasts),
        "evaluated_no_signal_forecasts": len(authoritative_valid_forecasts) - len(directional_forecasts),
        "explicit_evaluation_exclusions": len(call_results) - len(authoritative_valid_forecasts),
    }
    episode_reconciliation = {
        "selected_episodes": len(selected),
        "completed_episodes": len(episode_summary),
        "blocked_episodes": len(selected) - len(episode_summary),
    }
    write_json(run_dir / "episode_reconciliation.json", episode_reconciliation)
    write_json(run_dir / "call_reconciliation.json", transport_reconciliation)
    write_json(run_dir / "forecast_arm_reconciliation.json", forecast_reconciliation)
    write_json(run_dir / "evaluation_reconciliation.json", evaluation_reconciliation)
    write_jsonl(run_dir / "transport_results.jsonl", call_results)
    write_jsonl(run_dir / "canonical_forecasts" / "forecast_index.jsonl", forecasts)
    write_jsonl(run_dir / "canonical_forecasts" / "path_index.jsonl", forecast_paths)
    write_jsonl(run_dir / "evaluations" / "evaluation_index.jsonl", evaluations)
    write_jsonl(run_dir / "pair_comparisons" / "pair_index.jsonl", pair_comparisons)

    correction_count = sum(row["t15_pair_classification"] == "CORRECTION" for row in pair_comparisons)
    degradation_count = sum(row["t15_pair_classification"] == "DEGRADATION" for row in pair_comparisons)
    no_signal_transitions = dict(sorted(Counter(row["pair_transition"] for row in pair_comparisons).items()))

    full_run_provider_pairs = sorted(pairs)
    full_run_call_estimate = len(full_run_provider_pairs) * 2
    report = {
        "run_id": run_id,
        "git_head": current_head,
        "accepted_small_validation_head": SMALL_VALIDATION_FINAL_HEAD,
        "contract_version": contract.CONTRACT_VERSION,
        "schema_version": contract.SCHEMA_VERSION,
        "source_prevalidation_run_id": PREVALIDATION_RUN_ID,
        "transport_verification": bridge_info,
        "token_checksum_unchanged": token_before == token_after,
        "attempted_calls": attempted_calls,
        "terminal_counts": terminal_counts,
        "directional_forecasts": len(directional_forecasts),
        "valid_no_signal_forecasts": len(authoritative_valid_forecasts) - len(directional_forecasts),
        "schema_failures": forecast_reconciliation["schema_failures"],
        "runtime_failures": forecast_reconciliation["runtime_failures"],
        "provider_rejections": forecast_reconciliation["provider_rejections"],
        "t15_correction_count": correction_count,
        "t15_degradation_count": degradation_count,
        "pair_no_signal_transitions": no_signal_transitions,
        "estimated_full_run_call_volume": {
            "eligible_episode_count": 374,
            "provider_episode_identities_with_pack_ae_intersection": len(full_run_provider_pairs),
            "estimated_total_calls": full_run_call_estimate,
        },
        "stop_reason": stop_reason,
    }
    write_json(run_dir / "run_manifest.json", report)
    (run_dir / "expanded_validation_report.md").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
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
