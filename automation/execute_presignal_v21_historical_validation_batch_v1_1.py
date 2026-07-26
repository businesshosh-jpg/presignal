#!/usr/bin/env python3
"""Execute the frozen three-Episode historical validation batch via Apps Script."""
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

from automation import prepare_presignal_v21_historical_baseline_prevalidation_v1_1 as prevalidation
from automation import presignal_v21_event_path_contract_v1_1 as contract
from automation import run_presignal_v21_single_event_path_pair_v1_1 as step6
from automation.google_clients import (
    build_script_service,
    default_script_id,
    load_credentials,
    run_script_function_with_metadata,
)

STEP5 = ROOT / "outputs" / "presignal_v21_step5_reuse"
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_pure_prediction_historical_baseline"
BRIDGE_FUNCTION = "apiCallAuthoritativeProviderJsonObject"
REQUEST_SCHEMA_VERSION = "authoritative_historical_replay_bridge_v1"
PREVALIDATION_RUN_ID = "PPHB-R1-PREVALIDATION-20260726T090136Z-254f4ac151673853e5c7"
TOKEN_PATH = Path("/Users/junhoshino/projects/presignal/local/token.json")
TOKEN_ENV = "PRESIGNAL_GOOGLE_TOKEN_PATH"


class ValidationExecutionError(RuntimeError):
    """A frozen validation batch invariant was not met."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def token_sha256() -> str:
    return hashlib.sha256(TOKEN_PATH.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("".join(canonical_json(row) + "\n" for row in rows))
    os.replace(temporary, path)


def terminal_from_transport(result: Mapping[str, Any]) -> str:
    status = str(result.get("status") or "")
    if status == "ok":
        return "RESPONSE_RECEIVED"
    if status in {"provider_unavailable", "model_not_enforceable"}:
        return "PROVIDER_REJECTION"
    if status == "provider_contract_error":
        return "SCHEMA_FAILURE"
    if status == "execution_integrity_error":
        return "MODEL_MISMATCH"
    if status in {"timeout", "error"}:
        return "PROVIDER_RUNTIME_FAILURE"
    return "PROVIDER_RUNTIME_FAILURE"


def pair_classification(left: bool | None, right: bool | None) -> str:
    if left is None or right is None:
        return "PAIR_NOT_EVALUABLE"
    if left and right:
        return "BOTH_CORRECT"
    if (not left) and right:
        return "CORRECTION"
    if left and (not right):
        return "DEGRADATION"
    return "BOTH_INCORRECT"


def outcome_preflight(prevalidation_manifest: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if prevalidation_manifest.get("prevalidation_run_id") != PREVALIDATION_RUN_ID:
        raise ValidationExecutionError("PREVALIDATION_RUN_ID_MISMATCH")
    if prevalidation_manifest.get("contract_version") != contract.CONTRACT_VERSION or prevalidation_manifest.get("schema_version") != contract.SCHEMA_VERSION:
        raise ValidationExecutionError("PREVALIDATION_MANIFEST_VERSION_MISMATCH")
    outcomes_path = ROOT / prevalidation_manifest["outcomes_v1_1_path"]
    if "presignal_v21_episode_outcomes/outcome_rows.jsonl" in prevalidation_manifest["outcomes_v1_1_path"]:
        raise ValidationExecutionError("LEGACY_OUTCOME_FALLBACK_FORBIDDEN")
    outcomes = step6.load_v1_1_outcomes(outcomes_path)
    episode_ids = sorted({row["episode_id"] for row in outcomes})
    outcome_ids = sorted({row["outcome_id"] for row in outcomes})
    if len(outcomes) != 3 or len(episode_ids) != 3 or len(outcome_ids) != 3:
        raise ValidationExecutionError("PREVALIDATION_OUTCOME_CARDINALITY_INVALID")
    if sorted({row["immediate_impulse_outcome_state"] for row in outcomes}) != ["APPROXIMATION_ONLY"]:
        raise ValidationExecutionError("PREVALIDATION_IMMEDIATE_IMPULSE_STATE_INVALID")
    return outcomes, {
        "prevalidation_run_id": prevalidation_manifest["prevalidation_run_id"],
        "outcomes_count": len(outcomes),
        "unique_episode_ids": episode_ids,
        "unique_outcome_ids": outcome_ids,
        "schema_versions": sorted({row["schema_version"] for row in outcomes}),
        "contract_version": prevalidation_manifest["contract_version"],
        "immediate_impulse_states": sorted({row["immediate_impulse_outcome_state"] for row in outcomes}),
        "legacy_path_reference_present": False,
        "mixed_versions": False,
        "outcome_file_fingerprint": sha256(outcomes),
    }


def verify_bridge_transport() -> dict[str, Any]:
    os.environ[TOKEN_ENV] = str(TOKEN_PATH)
    creds = load_credentials(False, token_path=TOKEN_PATH, persist_refresh=False)
    service = build_script_service(creds, 240)
    script_id = default_script_id()
    content = service.projects().getContent(scriptId=script_id).execute()
    files = content.get("files", [])
    bridge_files = [item for item in files if BRIDGE_FUNCTION in item.get("source", "")]
    if not bridge_files:
        raise ValidationExecutionError("APPS_SCRIPT_BRIDGE_FUNCTION_MISSING")
    source = next(item["source"] for item in bridge_files if item.get("name") == "authoritative_provider_bridge")
    if "prov.model = requestedModel" not in source:
        raise ValidationExecutionError("APPS_SCRIPT_MODEL_ENFORCEMENT_MISSING")
    if "requestSchemaVersion !== 'authoritative_historical_replay_bridge_v1'" not in source:
        raise ValidationExecutionError("APPS_SCRIPT_REQUEST_SCHEMA_GATE_MISSING")
    if "elapsedMs > hardTimeoutSeconds * 1000" not in source:
        raise ValidationExecutionError("APPS_SCRIPT_TIMEOUT_GATE_MISSING")
    if "provider_unavailable" not in source or "model_not_enforceable" not in source or "execution_integrity_error" not in source:
        raise ValidationExecutionError("APPS_SCRIPT_TERMINAL_STATE_MAPPING_MISSING")
    return {
        "script_id": script_id,
        "invocation_route": "script.v1 projects.run devMode=true by scriptId",
        "bridge_function": BRIDGE_FUNCTION,
        "files_with_bridge": [{"name": item.get("name"), "type": item.get("type")} for item in bridge_files],
        "token_route": str(TOKEN_PATH),
        "token_valid": bool(creds.valid),
        "token_has_refresh_token": bool(getattr(creds, "refresh_token", None)),
        "scopes_count": len(creds.scopes or []),
        "request_schema_version": REQUEST_SCHEMA_VERSION,
        "exact_model_enforcement": True,
        "bridge_timeout_gate": True,
        "bridge_retry_behavior": "NO_LOCAL_RETRY_IN_BRIDGE_CALLER",
    }


def load_inputs() -> tuple[dict[tuple[str, str, str], dict[str, Any]], dict[tuple[str, str, str], dict[str, Any]]]:
    pack_a = {(row["episode_id"], row["provider"], row["model"]): row for row in read_jsonl(STEP5 / "event_path_forecast_inputs_pack_a.jsonl")}
    pack_e = {(row["episode_id"], row["provider"], row["model"]): row for row in read_jsonl(STEP5 / "event_path_forecast_inputs_pack_e.jsonl")}
    return pack_a, pack_e


def build_ledger(validation_batch: dict[str, Any], pack_a: Mapping[tuple[str, str, str], dict[str, Any]], pack_e: Mapping[tuple[str, str, str], dict[str, Any]], run_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ledger: list[dict[str, Any]] = []
    pair_symmetry: list[dict[str, Any]] = []
    index = 0
    for episode in validation_batch["episodes"]:
        episode_id = episode["episode_id"]
        for pair in episode["provider_model_pairs"]:
            provider, model = pair["provider"], pair["model"]
            row_a = pack_a[(episode_id, provider, model)]
            row_e = pack_e[(episode_id, provider, model)]
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
                raise ValidationExecutionError("PROMPT_SYMMETRY_FAILURE:" + canonical_json(diff["differences"]))
            for arm, row, context in (("PACK_A", row_a, context_a), ("PACK_E", row_e, context_e)):
                index += 1
                pack_arm = "BASELINE" if arm == "PACK_A" else "FULL_CONTEXT"
                pack_fp = None if arm == "PACK_A" else row["pack_fingerprint"]
                prompt = step6.prompt_text(context)
                payload = step6.bridge_payload(row, prompt, run_id=run_dir.name, arm=pack_arm)
                prediction_seed = {
                    "episode_id": episode_id,
                    "provider": provider,
                    "model": model,
                    "arm": arm,
                    "forecast_cutoff_ts": row["forecast_cutoff_ts"],
                    "pack_id": "BASELINE_NO_PACK" if arm == "PACK_A" else row["pack_id"],
                    "pack_fingerprint": pack_fp,
                }
                ledger.append({
                    "call_index": index,
                    "call_id": f"CALL_{index:02d}_{hashlib.sha256((episode_id + provider + model + arm).encode()).hexdigest()[:16]}",
                    "episode_id": episode_id,
                    "release_ts": row["release_ts"],
                    "provider": provider,
                    "model": model,
                    "pack_arm": arm,
                    "historical_cutoff_ts": row["forecast_cutoff_ts"],
                    "input_snapshot_id": row["input_fingerprint"],
                    "pack_fingerprint": pack_fp,
                    "prompt_fingerprint": sha256(context),
                    "request_fingerprint": sha256(payload),
                    "contract": contract.CONTRACT_VERSION,
                    "schema": contract.SCHEMA_VERSION,
                    "attempt_limit": 1,
                    "planned_output_path": str((run_dir / "raw_provider_responses" / f"{index:02d}_{episode_id}_{provider}_{arm}.json").relative_to(ROOT)),
                    "prompt_text_path": str((run_dir / "prompts" / f"{index:02d}_{episode_id}_{provider}_{arm}.txt").relative_to(ROOT)),
                    "canonical_forecast_seed": prediction_seed,
                })
    if len(ledger) != 14:
        raise ValidationExecutionError("VALIDATION_LEDGER_COUNT_UNEXPECTED")
    return ledger, pair_symmetry


def persist_precall_artifacts(run_dir: Path, prevalidation_manifest: dict[str, Any], validation_batch: dict[str, Any], ledger: list[dict[str, Any]], pair_symmetry: list[dict[str, Any]], pack_a: Mapping[tuple[str, str, str], dict[str, Any]], pack_e: Mapping[tuple[str, str, str], dict[str, Any]]) -> None:
    (run_dir / "input_snapshots").mkdir(parents=True, exist_ok=True)
    (run_dir / "prompts").mkdir(parents=True, exist_ok=True)
    (run_dir / "pack_symmetry").mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "source_prevalidation_manifest.json", prevalidation_manifest)
    write_json(run_dir / "validation_batch.json", validation_batch)
    write_jsonl(run_dir / "call_ledger.jsonl", ledger)
    write_json(run_dir / "pack_symmetry" / "pair_symmetry.json", {"pairs": pair_symmetry})
    for item in ledger:
        key = (item["episode_id"], item["provider"], item["model"])
        row = pack_a[key] if item["pack_arm"] == "PACK_A" else pack_e[key]
        context = step6.arm_context(row)
        prompt = step6.prompt_text(context)
        payload = step6.bridge_payload(row, prompt, run_id=run_dir.name, arm="BASELINE" if item["pack_arm"] == "PACK_A" else "FULL_CONTEXT")
        prefix = f"{item['call_index']:02d}_{item['episode_id']}_{item['provider']}_{item['pack_arm']}"
        write_json(run_dir / "input_snapshots" / f"{prefix}.json", {"input_row": row, "context": context, "payload": payload})
        (run_dir / "prompts" / f"{prefix}.txt").write_text(prompt + "\n")


def execute_run(prevalidation_manifest: dict[str, Any], output_root: Path = OUTPUT_ROOT) -> tuple[Path, dict[str, Any]]:
    token_before = token_sha256()
    bridge_info = verify_bridge_transport()
    outcomes, outcome_check = outcome_preflight(prevalidation_manifest)
    outcome_by_episode = {row["episode_id"]: row for row in outcomes}
    validation_batch = read_json(ROOT / prevalidation_manifest["validation_batch_path"])
    pack_a, pack_e = load_inputs()
    run_id = "PPHB-R1-VALIDATION-" + now().replace(":", "").replace("-", "") + "-" + hashlib.sha256((PREVALIDATION_RUN_ID + "|" + git_head()).encode()).hexdigest()[:12]
    run_dir = output_root / run_id
    ledger, pair_symmetry = build_ledger(validation_batch, pack_a, pack_e, run_dir)
    persist_precall_artifacts(run_dir, prevalidation_manifest, validation_batch, ledger, pair_symmetry, pack_a, pack_e)
    write_json(run_dir / "outcomes" / "outcome_preflight_check.json", outcome_check)
    write_json(run_dir / "transport_verification.json", bridge_info)

    os.environ[TOKEN_ENV] = str(TOKEN_PATH)
    script_service = build_script_service(load_credentials(False, token_path=TOKEN_PATH, persist_refresh=False), 240)
    script_id = default_script_id()

    call_results: list[dict[str, Any]] = []
    forecasts: list[dict[str, Any]] = []
    forecast_paths: list[dict[str, Any]] = []
    evaluations: list[dict[str, Any]] = []
    pair_comparisons: list[dict[str, Any]] = []
    stop_reason: str | None = None
    outcome_references: list[dict[str, Any]] = []
    index_lookup = {(item["episode_id"], item["provider"], item["model"], item["pack_arm"]): item for item in ledger}

    for episode in validation_batch["episodes"]:
        episode_id = episode["episode_id"]
        episode_calls = [row for row in ledger if row["episode_id"] == episode_id]
        episode_forecasts: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
        episode_paths: dict[tuple[str, str], dict[str, list[dict[str, Any]]]] = {}
        episode_terminal: list[dict[str, Any]] = []
        for provider_model in episode["provider_model_pairs"]:
            provider, model = provider_model["provider"], provider_model["model"]
            for pack_arm in ("PACK_A", "PACK_E"):
                item = index_lookup[(episode_id, provider, model, pack_arm)]
                prefix = f"{item['call_index']:02d}_{episode_id}_{provider}_{pack_arm}"
                row = pack_a[(episode_id, provider, model)] if pack_arm == "PACK_A" else pack_e[(episode_id, provider, model)]
                context = step6.arm_context(row)
                prompt = step6.prompt_text(context)
                payload = step6.bridge_payload(row, prompt, run_id=run_id, arm="BASELINE" if pack_arm == "PACK_A" else "FULL_CONTEXT")
                result = run_script_function_with_metadata(script_service, script_id, BRIDGE_FUNCTION, [dict(payload)], dev_mode=True)
                raw_path = run_dir / "raw_provider_responses" / f"{prefix}.json"
                write_json(raw_path, {"request": payload, "transport_result": result})
                terminal = {
                    "call_id": item["call_id"],
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
                    parsed = step6.parse_provider_output(bridge_result.get("raw_output"))
                    prediction, paths = step6.response_to_contract(
                        parsed,
                        row,
                        run_id=run_id,
                        created_ts=str(bridge_result.get("completed_timestamp") or now()),
                        raw_output=bridge_result.get("raw_output"),
                        bridge_result=bridge_result,
                    )
                    write_json(run_dir / "canonical_forecasts" / f"{prefix}.json", prediction)
                    write_jsonl(run_dir / "canonical_forecasts" / f"{prefix}_paths.jsonl", paths)
                    terminal["terminal_state"] = "VALID_NO_SIGNAL" if prediction["no_signal_flag"] else "COMPLETED_DIRECTIONAL_FORECAST"
                    terminal["prediction_id"] = prediction["prediction_id"]
                    episode_forecasts.setdefault((provider, model), {})[pack_arm] = prediction
                    episode_paths.setdefault((provider, model), {})[pack_arm] = paths
                    forecasts.append(prediction)
                    forecast_paths.extend(paths)
                except Exception as exc:
                    terminal["terminal_state"] = "SCHEMA_FAILURE"
                    terminal["error"] = str(exc)
                episode_terminal.append(terminal)
                call_results.append(terminal)
            if stop_reason:
                break
        if stop_reason:
            break
        outcome = outcome_by_episode[episode_id]
        outcome_references.append({"episode_id": episode_id, "outcome_id": outcome["outcome_id"], "outcome": outcome})
        write_json(run_dir / "outcomes" / f"{episode_id}.json", outcome)
        for (provider, model), pair in episode_forecasts.items():
            if "PACK_A" in pair:
                evaluation_a = step6.evaluate(pair["PACK_A"], episode_paths[(provider, model)]["PACK_A"], outcome, generated_ts=now())
                evaluations.append(evaluation_a)
                write_json(run_dir / "evaluations" / f"{episode_id}_{provider}_{model}_PACK_A.json", evaluation_a)
            if "PACK_E" in pair:
                evaluation_e = step6.evaluate(pair["PACK_E"], episode_paths[(provider, model)]["PACK_E"], outcome, generated_ts=now())
                evaluations.append(evaluation_e)
                write_json(run_dir / "evaluations" / f"{episode_id}_{provider}_{model}_PACK_E.json", evaluation_e)
            if "PACK_A" in pair and "PACK_E" in pair:
                by_arm = {record["information_arm"]: record for record in evaluations if record["episode_id"] == episode_id and record["provider"] == provider and record["model"] == model}
                compare = {
                    "episode_id": episode_id,
                    "provider": provider,
                    "model": model,
                    "t5_pair_classification": pair_classification(by_arm["BASELINE"]["direction_5m_ok"], by_arm["FULL_CONTEXT"]["direction_5m_ok"]),
                    "t15_pair_classification": pair_classification(by_arm["BASELINE"]["direction_15m_ok"], by_arm["FULL_CONTEXT"]["direction_15m_ok"]),
                    "baseline_prediction_id": pair["PACK_A"]["prediction_id"],
                    "full_context_prediction_id": pair["PACK_E"]["prediction_id"],
                    "shared_outcome_id": outcome["outcome_id"],
                }
                pair_comparisons.append(compare)
                write_json(run_dir / "pair_comparisons" / f"{episode_id}_{provider}_{model}.json", compare)

    token_after = token_sha256()
    write_json(run_dir / "token_checksum_audit.json", {"before_sha256": token_before, "after_sha256": token_after, "unchanged": token_before == token_after})

    call_counts = Counter(record["terminal_state"] for record in call_results)
    transport_reconciliation = {
        "authorized_calls": 14,
        "attempted_calls": len(call_results),
        "precall_blocks": 14 - len(call_results),
        "provider_returned_responses": sum(record["transport_ok"] for record in call_results),
        "transport_failures": sum(not record["transport_ok"] for record in call_results),
        "terminal_counts": dict(sorted(call_counts.items())),
    }
    forecast_reconciliation = {
        "expected_forecast_arms": 14,
        "completed_directional_forecasts": sum(record["terminal_state"] == "COMPLETED_DIRECTIONAL_FORECAST" for record in call_results),
        "valid_no_signals": sum(record["terminal_state"] == "VALID_NO_SIGNAL" for record in call_results),
        "provider_rejections": sum(record["terminal_state"] == "PROVIDER_REJECTION" for record in call_results),
        "runtime_failures": sum(record["terminal_state"] == "PROVIDER_RUNTIME_FAILURE" for record in call_results),
        "schema_failures": sum(record["terminal_state"] == "SCHEMA_FAILURE" for record in call_results),
        "validation_failures": sum(record["terminal_state"] == "VALIDATION_FAILURE" for record in call_results),
        "lineage_failures": 0,
        "persistence_failures": 0,
        "model_mismatches": sum(record["terminal_state"] == "MODEL_MISMATCH" for record in call_results),
    }
    evaluation_reconciliation = {
        "authoritative_completed_forecasts": len(forecasts),
        "evaluated_forecasts": len(evaluations),
        "evaluation_exclusions": len(forecasts) - len(evaluations),
    }
    write_json(run_dir / "call_reconciliation.json", transport_reconciliation)
    write_json(run_dir / "forecast_arm_reconciliation.json", forecast_reconciliation)
    write_json(run_dir / "evaluation_reconciliation.json", evaluation_reconciliation)
    write_json(run_dir / "episode_reconciliation.json", {
        "authorized_episodes": 3,
        "completed_episodes": len({row["episode_id"] for row in outcome_references}),
        "blocked_episodes": 3 - len({row["episode_id"] for row in outcome_references}),
    })
    write_jsonl(run_dir / "canonical_forecasts" / "forecast_index.jsonl", forecasts)
    write_jsonl(run_dir / "canonical_forecasts" / "path_index.jsonl", forecast_paths)
    write_jsonl(run_dir / "evaluations" / "evaluation_index.jsonl", evaluations)
    write_jsonl(run_dir / "pair_comparisons" / "pair_index.jsonl", pair_comparisons)
    write_jsonl(run_dir / "transport_results.jsonl", call_results)
    report = {
        "run_id": run_id,
        "contract_version": contract.CONTRACT_VERSION,
        "schema_version": contract.SCHEMA_VERSION,
        "source_prevalidation_run_id": PREVALIDATION_RUN_ID,
        "transport_verification": bridge_info,
        "token_checksum_unchanged": token_before == token_after,
        "attempted_calls": len(call_results),
        "completed_forecasts": len(forecasts),
        "evaluations": len(evaluations),
        "stop_reason": stop_reason,
    }
    write_json(run_dir / "run_manifest.json", report)
    (run_dir / "validation_report.md").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return run_dir, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prevalidation-manifest", type=Path, default=OUTPUT_ROOT / "latest_prevalidation_manifest.json")
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    manifest = read_json(args.prevalidation_manifest)
    run_dir, report = execute_run(manifest, args.output_root)
    print(json.dumps({"run_dir": str(run_dir), "report": report}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
