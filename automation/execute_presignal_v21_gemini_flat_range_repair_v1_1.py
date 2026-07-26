#!/usr/bin/env python3
"""Repair-run executor for the two remaining Gemini Pack E FLAT-range failures."""
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
    TOKEN_ENV,
    TOKEN_PATH,
    ValidationExecutionError,
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
ORIGINAL_RUN_ID = "PPHB-R1-VALIDATION-20260726T111436Z-5c34d5f7bb10"
WINDOW_REPAIR_RUN_ID = "PPHB-R1-GEMINI-WINDOW-REPAIR-20260726T114718Z-8fc238263380"
AUTHORIZED_ARMS = (
    ("EP_EVENT_ccf7e8031b0d9b2e2443", "Gemini", "gemini-2.5-flash-lite", "PACK_E"),
    ("EP_BATCH_bd5b0d22e01fddb86cf1", "Gemini", "gemini-2.5-flash-lite", "PACK_E"),
)
ORIGINAL_FAILED_CALL_IDS = {
    ("EP_EVENT_ccf7e8031b0d9b2e2443", "Gemini", "gemini-2.5-flash-lite", "PACK_E"): "CALL_02_050edf2fa05df85c",
    ("EP_BATCH_bd5b0d22e01fddb86cf1", "Gemini", "gemini-2.5-flash-lite", "PACK_E"): "CALL_06_bdcd45477e30a800",
}
WINDOW_REPAIR_FAILED_CALL_IDS = {
    ("EP_EVENT_ccf7e8031b0d9b2e2443", "Gemini", "gemini-2.5-flash-lite", "PACK_E"): "REPAIR_CALL_01_23f7316821d1bbf5",
    ("EP_BATCH_bd5b0d22e01fddb86cf1", "Gemini", "gemini-2.5-flash-lite", "PACK_E"): "REPAIR_CALL_02_a5983a6575c5013e",
}


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def logical_arm_key(record: Mapping[str, Any]) -> tuple[str, str, str, str]:
    arm = record.get("pack_arm")
    if arm is None:
        arm = "PACK_A" if record["information_arm"] == "BASELINE" else "PACK_E"
    return (str(record["episode_id"]), str(record["provider"]), str(record["model"]), str(arm))


def load_forecast_index(run_dir: Path) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    path = run_dir / "canonical_forecasts" / "forecast_index.jsonl"
    if not path.exists():
        return {}
    return {logical_arm_key(row): row for row in read_jsonl(path)}


def load_evaluation_index(run_dir: Path) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    path = run_dir / "evaluations" / "evaluation_index.jsonl"
    if not path.exists():
        return {}
    return {logical_arm_key(row): row for row in read_jsonl(path)}


def build_latest_terminal_map(
    original_transport: list[dict[str, Any]],
    window_transport: list[dict[str, Any]],
) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    latest: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in original_transport + window_transport:
        latest[logical_arm_key(row)] = row
    return latest


def build_repair_ledger(
    run_dir: Path,
    pack_a: Mapping[tuple[str, str, str], dict[str, Any]],
    pack_e: Mapping[tuple[str, str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, identity in enumerate(AUTHORIZED_ARMS, start=1):
        episode_id, provider, model, pack_arm = identity
        row = pack_e[(episode_id, provider, model)]
        context = step6.arm_context(row)
        prompt = step6.prompt_text(context)
        payload = step6.bridge_payload(row, prompt, run_id=run_dir.name, arm="FULL_CONTEXT")
        rows.append({
            "call_index": index,
            "call_id": f"FLAT_REPAIR_CALL_{index:02d}_{hashlib.sha256('|'.join(identity).encode()).hexdigest()[:16]}",
            "episode_id": episode_id,
            "provider": provider,
            "model": model,
            "pack_arm": pack_arm,
            "release_ts": row["release_ts"],
            "historical_cutoff_ts": row["forecast_cutoff_ts"],
            "input_snapshot_id": row["input_fingerprint"],
            "pack_fingerprint": row["pack_fingerprint"],
            "prompt_fingerprint": sha256(context),
            "request_fingerprint": sha256(payload),
            "planned_output_path": str((run_dir / "raw_provider_responses" / f"{index:02d}_{episode_id}_{provider}_{pack_arm}.json").relative_to(ROOT)),
            "prompt_text_path": str((run_dir / "prompts" / f"{index:02d}_{episode_id}_{provider}_{pack_arm}.txt").relative_to(ROOT)),
            "normalization_audit_path": str((run_dir / "normalization_audits" / f"{index:02d}_{episode_id}_{provider}_{pack_arm}.json").relative_to(ROOT)),
            "attempt_limit": 1,
            "contract": contract.CONTRACT_VERSION,
            "schema": contract.SCHEMA_VERSION,
            "original_failed_call_id": ORIGINAL_FAILED_CALL_IDS[identity],
            "window_repair_failed_call_id": WINDOW_REPAIR_FAILED_CALL_IDS[identity],
        })
    return rows


def persist_precall(run_dir: Path, source_prevalidation_manifest: dict[str, Any], ledger: list[dict[str, Any]], pack_e: Mapping[tuple[str, str, str], dict[str, Any]]) -> None:
    for folder in ("input_snapshots", "prompts", "raw_provider_responses", "canonical_forecasts", "evaluations", "pair_comparisons", "normalization_audits", "outcomes"):
        (run_dir / folder).mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "source_prevalidation_manifest.json", source_prevalidation_manifest)
    write_json(run_dir / "source_original_validation_run.json", read_json(OUTPUT_ROOT / ORIGINAL_RUN_ID / "run_manifest.json"))
    write_json(run_dir / "source_window_repair_run.json", read_json(OUTPUT_ROOT / WINDOW_REPAIR_RUN_ID / "run_manifest.json"))
    write_jsonl(run_dir / "call_ledger.jsonl", ledger)
    for item in ledger:
        row = pack_e[(item["episode_id"], item["provider"], item["model"])]
        context = step6.arm_context(row)
        prompt = step6.prompt_text(context)
        payload = step6.bridge_payload(row, prompt, run_id=run_dir.name, arm="FULL_CONTEXT")
        prefix = f"{item['call_index']:02d}_{item['episode_id']}_{item['provider']}_{item['pack_arm']}"
        write_json(run_dir / "input_snapshots" / f"{prefix}.json", {"input_row": row, "context": context, "payload": payload})
        (run_dir / "prompts" / f"{prefix}.txt").write_text(prompt + "\n")


def execute_repair(output_root: Path = OUTPUT_ROOT) -> tuple[Path, dict[str, Any]]:
    original_run_dir = output_root / ORIGINAL_RUN_ID
    window_repair_run_dir = output_root / WINDOW_REPAIR_RUN_ID
    source_prevalidation_manifest = read_json(original_run_dir / "source_prevalidation_manifest.json")
    outcomes, outcome_check = outcome_preflight(source_prevalidation_manifest)
    outcome_by_episode = {row["episode_id"]: row for row in outcomes}
    original_transport = read_jsonl(original_run_dir / "transport_results.jsonl")
    window_transport = read_jsonl(window_repair_run_dir / "transport_results.jsonl")
    latest_terminal = build_latest_terminal_map(original_transport, window_transport)
    original_forecasts = load_forecast_index(original_run_dir)
    window_forecasts = load_forecast_index(window_repair_run_dir)
    original_evaluations = load_evaluation_index(original_run_dir)
    window_evaluations = load_evaluation_index(window_repair_run_dir)
    pack_a, pack_e = load_inputs()

    token_before = token_sha256()
    bridge_info = verify_bridge_transport()
    run_id = "PPHB-R1-GEMINI-FLAT-RANGE-REPAIR-" + now().replace(":", "").replace("-", "") + "-" + hashlib.sha256((WINDOW_REPAIR_RUN_ID + "|" + git_head()).encode()).hexdigest()[:12]
    run_dir = output_root / run_id
    ledger = build_repair_ledger(run_dir, pack_a, pack_e)
    persist_precall(run_dir, source_prevalidation_manifest, ledger, pack_e)
    write_json(run_dir / "outcomes" / "outcome_preflight_check.json", outcome_check)
    write_json(run_dir / "transport_verification.json", bridge_info)

    os.environ[TOKEN_ENV] = str(TOKEN_PATH)
    script_service = build_script_service(load_credentials(False, token_path=TOKEN_PATH, persist_refresh=False), 240)
    script_id = default_script_id()

    call_results: list[dict[str, Any]] = []
    new_forecasts: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    new_evaluations: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    new_paths: list[dict[str, Any]] = []

    for item in ledger:
        episode_id, provider, model, pack_arm = item["episode_id"], item["provider"], item["model"], item["pack_arm"]
        row = pack_e[(episode_id, provider, model)]
        context = step6.arm_context(row)
        prompt = step6.prompt_text(context)
        payload = step6.bridge_payload(row, prompt, run_id=run_id, arm="FULL_CONTEXT")
        prefix = f"{item['call_index']:02d}_{episode_id}_{provider}_{pack_arm}"
        result = run_script_function_with_metadata(script_service, script_id, BRIDGE_FUNCTION, [dict(payload)], dev_mode=True)
        raw_path = run_dir / "raw_provider_responses" / f"{prefix}.json"
        write_json(raw_path, {"request": payload, "transport_result": result})
        terminal = {
            "call_id": item["call_id"],
            "episode_id": episode_id,
            "provider": provider,
            "model": model,
            "pack_arm": pack_arm,
            "original_failed_call_id": item["original_failed_call_id"],
            "window_repair_failed_call_id": item["window_repair_failed_call_id"],
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
            raise ValidationExecutionError("FLAT_RANGE_REPAIR_MODEL_SUBSTITUTION")
        if transport_terminal != "RESPONSE_RECEIVED":
            terminal["terminal_state"] = transport_terminal
            terminal["error"] = bridge_result.get("error")
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
            evaluation = step6.evaluate(prediction, paths, outcome_by_episode[episode_id], generated_ts=now())
            write_json(run_dir / "canonical_forecasts" / f"{prefix}.json", prediction)
            write_jsonl(run_dir / "canonical_forecasts" / f"{prefix}_paths.jsonl", paths)
            write_json(run_dir / "evaluations" / f"{prefix}.json", evaluation)
            key = (episode_id, provider, model, pack_arm)
            new_forecasts[key] = prediction
            new_evaluations[key] = evaluation
            new_paths.extend(paths)
            terminal["terminal_state"] = "VALID_NO_SIGNAL" if prediction["no_signal_flag"] else "COMPLETED_DIRECTIONAL_FORECAST"
            terminal["prediction_id"] = prediction["prediction_id"]
            terminal["provider_immediate_window_status"] = audit["provider_immediate_window_status"]
            terminal["provider_returned_immediate_window_seconds"] = audit["provider_returned_immediate_window_seconds"]
            terminal["canonical_immediate_window_seconds"] = audit["canonical_immediate_window_seconds"]
        except Exception as exc:
            terminal["terminal_state"] = "SCHEMA_FAILURE"
            terminal["error"] = str(exc)
        call_results.append(terminal)

    latest_combined = dict(latest_terminal)
    for row in call_results:
        latest_combined[logical_arm_key(row)] = row

    merged_forecasts = dict(original_forecasts)
    merged_forecasts.update(window_forecasts)
    merged_forecasts.update(new_forecasts)
    merged_evaluations = dict(original_evaluations)
    merged_evaluations.update(window_evaluations)
    merged_evaluations.update(new_evaluations)

    pair_comparisons: list[dict[str, Any]] = []
    for episode_id, provider, model, _pack_arm in AUTHORIZED_ARMS:
        base_key = (episode_id, provider, model, "PACK_A")
        full_key = (episode_id, provider, model, "PACK_E")
        left_prediction = merged_forecasts.get(base_key)
        right_prediction = merged_forecasts.get(full_key)
        left_eval = merged_evaluations.get(base_key)
        right_eval = merged_evaluations.get(full_key)
        compare = {
            "episode_id": episode_id,
            "provider": provider,
            "model": model,
            "baseline_prediction_id": left_prediction["prediction_id"] if left_prediction else None,
            "full_context_prediction_id": right_prediction["prediction_id"] if right_prediction else None,
            "shared_outcome_id": outcome_by_episode[episode_id]["outcome_id"],
            "t5_pair_classification": pair_classification(left_eval["direction_5m_ok"] if left_eval else None, right_eval["direction_5m_ok"] if right_eval else None),
            "t15_pair_classification": pair_classification(left_eval["direction_15m_ok"] if left_eval else None, right_eval["direction_15m_ok"] if right_eval else None),
        }
        pair_comparisons.append(compare)
        write_json(run_dir / "pair_comparisons" / f"{episode_id}_{provider}_{model}.json", compare)
        write_json(run_dir / "outcomes" / f"{episode_id}.json", outcome_by_episode[episode_id])

    token_after = token_sha256()
    write_json(run_dir / "token_checksum_audit.json", {"before_sha256": token_before, "after_sha256": token_after, "unchanged": token_before == token_after})

    latest_counts = Counter(row["terminal_state"] for row in latest_combined.values())
    historical_attempt_counts = Counter(row["terminal_state"] for row in original_transport + window_transport + call_results)
    directional_count = sum(row["terminal_state"] == "COMPLETED_DIRECTIONAL_FORECAST" for row in latest_combined.values())
    no_signal_count = sum(row["terminal_state"] == "VALID_NO_SIGNAL" for row in latest_combined.values())
    schema_failure_count = sum(row["terminal_state"] == "SCHEMA_FAILURE" for row in latest_combined.values())

    write_json(run_dir / "transport_reconciliation.json", {
        "authorized_calls": 2,
        "attempted_calls": len(call_results),
        "precall_blocks": 2 - len(call_results),
        "terminal_counts": dict(sorted(Counter(row["terminal_state"] for row in call_results).items())),
    })
    write_json(run_dir / "final_logical_14_arm_reconciliation.json", {
        "logical_forecast_arms": 14,
        "latest_terminal_counts": dict(sorted(latest_counts.items())),
        "completed_directional_forecasts": directional_count,
        "valid_no_signals": no_signal_count,
        "schema_failures": schema_failure_count,
    })
    write_json(run_dir / "historical_attempt_reconciliation.json", {
        "original_run_id": ORIGINAL_RUN_ID,
        "window_repair_run_id": WINDOW_REPAIR_RUN_ID,
        "flat_range_repair_run_id": run_id,
        "total_historical_attempts": len(original_transport) + len(window_transport) + len(call_results),
        "attempt_terminal_counts": dict(sorted(historical_attempt_counts.items())),
    })
    write_json(run_dir / "evaluation_reconciliation.json", {
        "new_valid_canonical_forecasts": len(new_forecasts),
        "new_evaluated_forecasts": len(new_evaluations),
        "new_evaluation_exclusions": len(new_forecasts) - len(new_evaluations),
    })
    write_jsonl(run_dir / "transport_results.jsonl", call_results)
    write_jsonl(run_dir / "canonical_forecasts" / "forecast_index.jsonl", list(new_forecasts.values()))
    write_jsonl(run_dir / "canonical_forecasts" / "path_index.jsonl", new_paths)
    write_jsonl(run_dir / "evaluations" / "evaluation_index.jsonl", list(new_evaluations.values()))
    write_jsonl(run_dir / "pair_comparisons" / "pair_index.jsonl", pair_comparisons)

    report = {
        "run_id": run_id,
        "git_head": git_head(),
        "contract_version": contract.CONTRACT_VERSION,
        "schema_version": contract.SCHEMA_VERSION,
        "source_prevalidation_run_id": PREVALIDATION_RUN_ID,
        "original_run_id": ORIGINAL_RUN_ID,
        "window_repair_run_id": WINDOW_REPAIR_RUN_ID,
        "attempted_calls": len(call_results),
        "new_directional_forecasts": sum(row["terminal_state"] == "COMPLETED_DIRECTIONAL_FORECAST" for row in call_results),
        "new_valid_no_signals": sum(row["terminal_state"] == "VALID_NO_SIGNAL" for row in call_results),
        "token_checksum_unchanged": token_before == token_after,
    }
    write_json(run_dir / "run_manifest.json", report)
    (run_dir / "validation_report.md").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return run_dir, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    run_dir, report = execute_repair(args.output_root)
    print(json.dumps({"run_dir": str(run_dir), "report": report}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
