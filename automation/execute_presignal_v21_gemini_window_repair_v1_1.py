#!/usr/bin/env python3
"""Repair-run executor for the four Gemini arms blocked by window ownership."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import presignal_v21_event_path_contract_v1_1 as contract
from automation import run_presignal_v21_single_event_path_pair_v1_1 as step6
from automation.execute_presignal_v21_historical_validation_batch_v1_1 import (
    BRIDGE_FUNCTION,
    PREVALIDATION_RUN_ID,
    REQUEST_SCHEMA_VERSION,
    TOKEN_ENV,
    TOKEN_PATH,
    ValidationExecutionError,
    canonical_json,
    load_inputs,
    now,
    outcome_preflight,
    pair_classification,
    read_json,
    read_jsonl,
    sha256,
    terminal_from_transport,
    token_sha256,
    verify_bridge_transport,
    write_json,
    write_jsonl,
)
from automation.google_clients import build_script_service, default_script_id, load_credentials, run_script_function_with_metadata

OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_pure_prediction_historical_baseline"
PRIOR_RUN_ID = "PPHB-R1-VALIDATION-20260726T111436Z-5c34d5f7bb10"
PRIOR_RUN_DIR = OUTPUT_ROOT / PRIOR_RUN_ID
PRIOR_HEAD = "25c57f10bb97a5865870b2ebbe93136960c069b8"
FAILED_CALL_IDS = (
    "CALL_02_050edf2fa05df85c",
    "CALL_06_bdcd45477e30a800",
    "CALL_11_c56d995c6d332f7a",
    "CALL_12_dddecb9e9e0397c7",
)
AUTHORIZED_ARMS = (
    ("EP_EVENT_ccf7e8031b0d9b2e2443", "Gemini", "gemini-2.5-flash-lite", "PACK_E"),
    ("EP_BATCH_bd5b0d22e01fddb86cf1", "Gemini", "gemini-2.5-flash-lite", "PACK_E"),
    ("EP_BATCH_6fb320e5e8c5931f2373", "Gemini", "gemini-2.5-flash-lite", "PACK_A"),
    ("EP_BATCH_6fb320e5e8c5931f2373", "Gemini", "gemini-2.5-flash-lite", "PACK_E"),
)


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def pair_key(record: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (str(record["episode_id"]), str(record["provider"]), str(record["model"]), str(record["pack_arm"]))


def prediction_pair_key(record: Mapping[str, Any]) -> tuple[str, str, str, str]:
    arm = "PACK_A" if record["information_arm"] == "BASELINE" else "PACK_E"
    return (str(record["episode_id"]), str(record["provider"]), str(record["model"]), arm)


def load_prior_context() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    manifest = read_json(PRIOR_RUN_DIR / "run_manifest.json")
    if manifest.get("source_prevalidation_run_id") != PREVALIDATION_RUN_ID:
        raise ValidationExecutionError("PRIOR_RUN_PREVALIDATION_ID_MISMATCH")
    ledger = read_jsonl(PRIOR_RUN_DIR / "call_ledger.jsonl")
    transport = read_jsonl(PRIOR_RUN_DIR / "transport_results.jsonl")
    if {row["call_id"] for row in transport if row.get("terminal_state") == "SCHEMA_FAILURE"} != set(FAILED_CALL_IDS):
        raise ValidationExecutionError("FAILED_CALL_SET_MISMATCH")
    if git_head() == PRIOR_HEAD:
        raise ValidationExecutionError("REPAIR_HEAD_NOT_ADVANCED")
    return manifest, {pair_key(row): row for row in ledger}, transport, ledger


def load_prior_authoritative_forecasts() -> tuple[dict[tuple[str, str, str, str], dict[str, Any]], dict[tuple[str, str, str, str], dict[str, Any]]]:
    forecasts = {
        prediction_pair_key(record): record
        for record in read_jsonl(PRIOR_RUN_DIR / "canonical_forecasts" / "forecast_index.jsonl")
    }
    evaluations = {
        prediction_pair_key(record): record
        for record in read_jsonl(PRIOR_RUN_DIR / "evaluations" / "evaluation_index.jsonl")
    }
    return forecasts, evaluations


def build_repair_ledger(
    prior_ledger: Mapping[tuple[str, str, str, str], dict[str, Any]],
    pack_a: Mapping[tuple[str, str, str], dict[str, Any]],
    pack_e: Mapping[tuple[str, str, str], dict[str, Any]],
    run_dir: Path,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, identity in enumerate(AUTHORIZED_ARMS, start=1):
        episode_id, provider, model, pack_arm = identity
        prior = prior_ledger.get(identity)
        if prior is None:
            raise ValidationExecutionError("REPAIR_PRIOR_LEDGER_ROW_MISSING")
        row = pack_a[(episode_id, provider, model)] if pack_arm == "PACK_A" else pack_e[(episode_id, provider, model)]
        context = step6.arm_context(row)
        prompt = step6.prompt_text(context)
        payload = step6.bridge_payload(row, prompt, run_id=run_dir.name, arm="BASELINE" if pack_arm == "PACK_A" else "FULL_CONTEXT")
        rows.append({
            "call_index": index,
            "call_id": f"REPAIR_CALL_{index:02d}_{hashlib.sha256('|'.join(identity).encode()).hexdigest()[:16]}",
            "repaired_prior_call_id": prior["call_id"],
            "episode_id": episode_id,
            "release_ts": row["release_ts"],
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
            "attempt_limit": 1,
            "planned_output_path": str((run_dir / "raw_provider_responses" / f"{index:02d}_{episode_id}_{provider}_{pack_arm}.json").relative_to(ROOT)),
            "prompt_text_path": str((run_dir / "prompts" / f"{index:02d}_{episode_id}_{provider}_{pack_arm}.txt").relative_to(ROOT)),
            "normalization_audit_path": str((run_dir / "normalization_audits" / f"{index:02d}_{episode_id}_{provider}_{pack_arm}.json").relative_to(ROOT)),
            "prior_prompt_fingerprint": prior["prompt_fingerprint"],
            "prior_request_fingerprint": prior["request_fingerprint"],
        })
    return rows


def persist_precall_artifacts(
    run_dir: Path,
    source_prevalidation_manifest: dict[str, Any],
    prior_manifest: dict[str, Any],
    ledger: list[dict[str, Any]],
    pack_a: Mapping[tuple[str, str, str], dict[str, Any]],
    pack_e: Mapping[tuple[str, str, str], dict[str, Any]],
) -> None:
    for folder in ("input_snapshots", "prompts", "raw_provider_responses", "canonical_forecasts", "evaluations", "pair_comparisons", "normalization_audits", "outcomes"):
        (run_dir / folder).mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "source_prevalidation_manifest.json", source_prevalidation_manifest)
    write_json(run_dir / "source_prior_validation_run.json", prior_manifest)
    write_jsonl(run_dir / "call_ledger.jsonl", ledger)
    for item in ledger:
        key = (item["episode_id"], item["provider"], item["model"])
        row = pack_a[key] if item["pack_arm"] == "PACK_A" else pack_e[key]
        context = step6.arm_context(row)
        prompt = step6.prompt_text(context)
        payload = step6.bridge_payload(row, prompt, run_id=run_dir.name, arm="BASELINE" if item["pack_arm"] == "PACK_A" else "FULL_CONTEXT")
        prefix = f"{item['call_index']:02d}_{item['episode_id']}_{item['provider']}_{item['pack_arm']}"
        write_json(run_dir / "input_snapshots" / f"{prefix}.json", {"input_row": row, "context": context, "payload": payload})
        (run_dir / "prompts" / f"{prefix}.txt").write_text(prompt + "\n")


def repair_run(output_root: Path = OUTPUT_ROOT) -> tuple[Path, dict[str, Any]]:
    prior_manifest, prior_ledger, prior_transport, _ = load_prior_context()
    source_prevalidation_manifest = read_json(PRIOR_RUN_DIR / "source_prevalidation_manifest.json")
    outcomes, outcome_check = outcome_preflight(source_prevalidation_manifest)
    outcome_by_episode = {row["episode_id"]: row for row in outcomes}
    prior_forecasts, prior_evaluations = load_prior_authoritative_forecasts()
    pack_a, pack_e = load_inputs()
    token_before = token_sha256()
    bridge_info = verify_bridge_transport()
    run_id = "PPHB-R1-GEMINI-WINDOW-REPAIR-" + now().replace(":", "").replace("-", "") + "-" + hashlib.sha256((PRIOR_RUN_ID + "|" + git_head()).encode()).hexdigest()[:12]
    run_dir = output_root / run_id
    ledger = build_repair_ledger(prior_ledger, pack_a, pack_e, run_dir)
    persist_precall_artifacts(run_dir, source_prevalidation_manifest, prior_manifest, ledger, pack_a, pack_e)
    write_json(run_dir / "outcomes" / "outcome_preflight_check.json", outcome_check)
    write_json(run_dir / "transport_verification.json", bridge_info)

    os.environ[TOKEN_ENV] = str(TOKEN_PATH)
    script_service = build_script_service(load_credentials(False, token_path=TOKEN_PATH, persist_refresh=False), 240)
    script_id = default_script_id()

    call_results: list[dict[str, Any]] = []
    forecasts: list[dict[str, Any]] = []
    paths: list[dict[str, Any]] = []
    evaluations: list[dict[str, Any]] = []
    pair_comparisons: list[dict[str, Any]] = []
    stop_reason: str | None = None

    for item in ledger:
        episode_id, provider, model, pack_arm = item["episode_id"], item["provider"], item["model"], item["pack_arm"]
        key = (episode_id, provider, model)
        row = pack_a[key] if pack_arm == "PACK_A" else pack_e[key]
        context = step6.arm_context(row)
        prompt = step6.prompt_text(context)
        payload = step6.bridge_payload(row, prompt, run_id=run_id, arm="BASELINE" if pack_arm == "PACK_A" else "FULL_CONTEXT")
        prefix = f"{item['call_index']:02d}_{episode_id}_{provider}_{pack_arm}"
        result = run_script_function_with_metadata(script_service, script_id, BRIDGE_FUNCTION, [dict(payload)], dev_mode=True)
        raw_path = run_dir / "raw_provider_responses" / f"{prefix}.json"
        write_json(raw_path, {"request": payload, "transport_result": result})
        terminal = {
            "call_id": item["call_id"],
            "repaired_prior_call_id": item["repaired_prior_call_id"],
            "episode_id": episode_id,
            "provider": provider,
            "model": model,
            "pack_arm": pack_arm,
            "request_fingerprint": item["request_fingerprint"],
            "transport_ok": result["ok"],
            "transport_elapsed_ms": result["elapsed_ms"],
            "transport_classification": result["classification"],
            "transport_request": result["request"],
            "raw_response_path": str(raw_path.relative_to(ROOT)),
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
            write_json(run_dir / "normalization_audits" / f"{prefix}.json", audit)
            prediction, prediction_paths = step6.response_to_contract(
                normalized,
                row,
                run_id=run_id,
                created_ts=str(bridge_result.get("completed_timestamp") or now()),
                raw_output=bridge_result.get("raw_output"),
                bridge_result=bridge_result,
            )
            write_json(run_dir / "canonical_forecasts" / f"{prefix}.json", prediction)
            write_jsonl(run_dir / "canonical_forecasts" / f"{prefix}_paths.jsonl", prediction_paths)
            evaluation = step6.evaluate(prediction, prediction_paths, outcome_by_episode[episode_id], generated_ts=now())
            write_json(run_dir / "evaluations" / f"{prefix}.json", evaluation)
            forecasts.append(prediction)
            paths.extend(prediction_paths)
            evaluations.append(evaluation)
            terminal["terminal_state"] = "VALID_NO_SIGNAL" if prediction["no_signal_flag"] else "COMPLETED_DIRECTIONAL_FORECAST"
            terminal["prediction_id"] = prediction["prediction_id"]
            terminal["provider_immediate_window_status"] = audit["provider_immediate_window_status"]
            terminal["provider_returned_immediate_window_seconds"] = audit["provider_returned_immediate_window_seconds"]
            terminal["canonical_immediate_window_seconds"] = audit["canonical_immediate_window_seconds"]
        except Exception as exc:
            terminal["terminal_state"] = "SCHEMA_FAILURE"
            terminal["error"] = str(exc)
        call_results.append(terminal)

    if stop_reason:
        raise ValidationExecutionError("REPAIR_SAFETY_STOP:" + stop_reason)

    for episode_id in sorted({row["episode_id"] for row in outcomes if row["episode_id"] in {arm[0] for arm in AUTHORIZED_ARMS}}):
        write_json(run_dir / "outcomes" / f"{episode_id}.json", outcome_by_episode[episode_id])

    combined_forecasts = dict(prior_forecasts)
    combined_evaluations = dict(prior_evaluations)
    for prediction in forecasts:
        combined_forecasts[prediction_pair_key(prediction)] = prediction
    for evaluation in evaluations:
        combined_evaluations[prediction_pair_key(evaluation)] = evaluation

    for episode_id, provider, model, _ in AUTHORIZED_ARMS:
        pair_id = (episode_id, provider, model)
        if any(row.get("episode_id") == episode_id and row.get("provider") == provider and row.get("model") == model for row in pair_comparisons):
            continue
        left_prediction = combined_forecasts.get((episode_id, provider, model, "PACK_A"))
        right_prediction = combined_forecasts.get((episode_id, provider, model, "PACK_E"))
        left_eval = combined_evaluations.get((episode_id, provider, model, "PACK_A"))
        right_eval = combined_evaluations.get((episode_id, provider, model, "PACK_E"))
        comparison = {
            "episode_id": episode_id,
            "provider": provider,
            "model": model,
            "baseline_prediction_id": left_prediction["prediction_id"] if left_prediction else None,
            "full_context_prediction_id": right_prediction["prediction_id"] if right_prediction else None,
            "shared_outcome_id": outcome_by_episode[episode_id]["outcome_id"],
            "t5_pair_classification": pair_classification(left_eval["direction_5m_ok"] if left_eval else None, right_eval["direction_5m_ok"] if right_eval else None),
            "t15_pair_classification": pair_classification(left_eval["direction_15m_ok"] if left_eval else None, right_eval["direction_15m_ok"] if right_eval else None),
        }
        pair_comparisons.append(comparison)
        write_json(run_dir / "pair_comparisons" / f"{episode_id}_{provider}_{model}.json", comparison)

    token_after = token_sha256()
    write_json(run_dir / "token_checksum_audit.json", {"before_sha256": token_before, "after_sha256": token_after, "unchanged": token_before == token_after})

    repair_counts = Counter(row["terminal_state"] for row in call_results)
    combined_counts = Counter(row["terminal_state"] for row in prior_transport if row["terminal_state"] == "VALID_NO_SIGNAL")
    combined_counts.update(repair_counts)

    directional = sum(row["terminal_state"] == "COMPLETED_DIRECTIONAL_FORECAST" for row in call_results)
    valid_no_signal = sum(row["terminal_state"] == "VALID_NO_SIGNAL" for row in call_results)
    write_json(run_dir / "transport_reconciliation.json", {
        "authorized_new_calls": 4,
        "attempted_calls": len(call_results),
        "precall_blocks": 4 - len(call_results),
        "terminal_counts": dict(sorted(repair_counts.items())),
    })
    write_json(run_dir / "forecast_arm_reconciliation.json", {
        "expected_repaired_arms": 4,
        "completed_directional_forecasts": directional,
        "valid_no_signals": valid_no_signal,
        "schema_failures": sum(row["terminal_state"] == "SCHEMA_FAILURE" for row in call_results),
        "runtime_failures": sum(row["terminal_state"] == "PROVIDER_RUNTIME_FAILURE" for row in call_results),
        "provider_rejections": sum(row["terminal_state"] == "PROVIDER_REJECTION" for row in call_results),
        "model_mismatches": sum(row["terminal_state"] == "MODEL_MISMATCH" for row in call_results),
    })
    write_json(run_dir / "evaluation_reconciliation.json", {
        "valid_canonical_forecasts": len(forecasts),
        "evaluated_forecasts": len(evaluations),
        "evaluation_exclusions": len(forecasts) - len(evaluations),
    })
    write_json(run_dir / "combined_validation_reconciliation.json", {
        "prior_validation_run_id": PRIOR_RUN_ID,
        "repair_run_id": run_id,
        "authoritative_original_arms": 10,
        "newly_executed_repaired_arms": 4,
        "combined_terminal_counts": dict(sorted(combined_counts.items())),
        "combined_directional_forecasts": directional,
        "combined_valid_no_signals": 10 + valid_no_signal,
    })
    write_jsonl(run_dir / "transport_results.jsonl", call_results)
    write_jsonl(run_dir / "canonical_forecasts" / "forecast_index.jsonl", forecasts)
    write_jsonl(run_dir / "canonical_forecasts" / "path_index.jsonl", paths)
    write_jsonl(run_dir / "evaluations" / "evaluation_index.jsonl", evaluations)
    write_jsonl(run_dir / "pair_comparisons" / "pair_index.jsonl", pair_comparisons)

    report = {
        "run_id": run_id,
        "prior_run_id": PRIOR_RUN_ID,
        "source_prevalidation_run_id": PREVALIDATION_RUN_ID,
        "contract_version": contract.CONTRACT_VERSION,
        "schema_version": contract.SCHEMA_VERSION,
        "git_head": git_head(),
        "attempted_calls": len(call_results),
        "directional_forecasts": directional,
        "valid_no_signal_forecasts": valid_no_signal,
        "token_checksum_unchanged": token_before == token_after,
        "stop_reason": stop_reason,
    }
    write_json(run_dir / "run_manifest.json", report)
    (run_dir / "validation_report.md").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return run_dir, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    run_dir, report = repair_run(args.output_root)
    print(json.dumps({"run_dir": str(run_dir), "report": report}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
