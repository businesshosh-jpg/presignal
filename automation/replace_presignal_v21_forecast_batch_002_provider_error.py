"""Correct the Gemini 503 classification and execute one replacement for Batch 002."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from automation import execute_presignal_v21_forecast_batch_001 as batch_exec
from automation import reconcile_presignal_v21_forecast_batch_002_provider_authority as recon
from automation import recover_presignal_v21_forecast_batch_002_governance as prior_recovery
from automation import run_presignal_v21_single_event_path_pair_v1_1 as step6


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
PLAN_ID = "PPHB-R1-FORECAST-EXECUTION-PLAN-20260729T123101Z-14d356fb00c1"
GOVERNANCE_RECOVERY_ID = "PPHB-R1-FORECAST-GOVERNANCE-RECOVERY-BATCH-002-20260729T155711Z-d5eb5c6e23c3"
AUTHORITY_RECON_ID = "PPHB-R1-FORECAST-PROVIDER-AUTHORITY-RECONCILIATION-BATCH-002-20260729T161530Z-d13317b9eca9"
EXPECTED_START_HEAD = "b0c6704e260d202b897f974089018bd69039d69d"
USER_BATCH_LABEL = "FORECAST_BATCH_002"
FROZEN_BATCH_ID = "FCB_PACK_A_002"
CALL_ID = "FCL_ff54346ab7650976cfdf2a77"
EXPECTED_PROVIDER = "Gemini"
EXPECTED_MODEL = "gemini-2.5-flash-lite"
PACK_TYPE = "PACK_A"
FORECAST_CONTRACT = "presignal_event_path_contract_v1_1"
RUN_PREFIX = "PPHB-R1-FORECAST-PROVIDER-ERROR-REPLACEMENT-BATCH-002-"
ORIGINAL_RECONCILED_REASON = "GEMINI_PROVIDER_503_NO_FORECAST_PAYLOAD"
REPLACEMENT_ATTEMPT_CATEGORY = "GOVERNANCE_AUTHORIZED_PROVIDER_ERROR_REPLACEMENT"
REPLACEMENT_AUTH_REASON = "ORIGINAL_ATTEMPT_TERMINATED_WITH_GEMINI_503_AND_RETURNED_NO_FORECAST_PAYLOAD"


class ProviderErrorReplacementError(RuntimeError):
    """Raised when the bounded provider-error replacement move cannot proceed."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_value(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def git(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, cwd=ROOT, text=True).strip()


def git_branch() -> str:
    return git(["git", "rev-parse", "--abbrev-ref", "HEAD"])


def git_head() -> str:
    return git(["git", "rev-parse", "HEAD"])


def is_descendant_of(commit: str) -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=ROOT).returncode == 0


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("".join(canonical_json(dict(row)) + "\n" for row in rows))
    os.replace(tmp, path)


def append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(canonical_json(dict(row)) + "\n")


def update_run_manifest(path: Path, **updates: Any) -> None:
    manifest = read_json(path) if path.exists() else {}
    manifest.update(updates)
    write_json(path, manifest)


def validated_result_inventory(output_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in output_root.glob("PPHB-R1-FORECAST-*/normalized_forecast_results.jsonl"):
        try:
            rows.extend(read_jsonl(path))
        except Exception:
            continue
    return rows


def find_existing_valid_result(call_id: str, output_root: Path) -> dict[str, Any] | None:
    for row in validated_result_inventory(output_root):
        if row.get("forecast_call_id") == call_id and row.get("terminal_state") == "SUCCEEDED_VALID":
            return row
    return None


def materialize_run(output_root: Path, *, fixed_timestamp: str | None = None) -> Path:
    timestamp = fixed_timestamp or now().replace("-", "").replace(":", "")
    timestamp = timestamp.replace("+00:00", "Z")
    fingerprint = sha256_value(
        {
            "call_id": CALL_ID,
            "governance_recovery_id": GOVERNANCE_RECOVERY_ID,
            "reconciliation_id": AUTHORITY_RECON_ID,
            "move": "FORECAST_PROVIDER_ERROR_REPLACEMENT_BATCH_002",
            "timestamp": timestamp,
        }
    ).split(":")[1][:12]
    run_dir = output_root / f"{RUN_PREFIX}{timestamp}-{fingerprint}"
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def load_target_bundle() -> dict[str, Any]:
    bundle = batch_exec.verified_batch_bundle(user_batch_label=USER_BATCH_LABEL, frozen_batch_id=FROZEN_BATCH_ID)
    matches = [row for row in bundle["bundles"] if row["call"]["forecast_call_id"] == CALL_ID]
    if len(matches) != 1:
        raise ProviderErrorReplacementError("TARGET_CALL_NOT_FOUND_UNIQUELY")
    row = matches[0]
    call = row["call"]
    if call["provider"] != EXPECTED_PROVIDER or call["model"] != EXPECTED_MODEL or call["pack_type"] != PACK_TYPE:
        raise ProviderErrorReplacementError("FROZEN_IDENTITY_MISMATCH")
    return {
        "bundle": bundle,
        "row": row,
        "call": call,
        "prompt_row": row["prompt_row"],
        "prompt_fingerprint": row["prompt_fingerprint"],
        "pack_payload": row["pack_payload"],
    }


def load_original_failed_evidence() -> dict[str, Any]:
    gov_run = OUTPUT_ROOT / GOVERNANCE_RECOVERY_ID
    target = {
        "raw_transport": None,
        "raw_provider": None,
        "provider_authority": None,
        "failed_call": None,
        "operation_journal": [],
        "attempt_category": None,
    }
    for line in read_jsonl(gov_run / "raw_transport_results.jsonl"):
        if line.get("forecast_call_id") == CALL_ID:
            target["raw_transport"] = line
    for line in read_jsonl(gov_run / "raw_provider_outputs.jsonl"):
        if line.get("forecast_call_id") == CALL_ID:
            target["raw_provider"] = line
    for line in read_jsonl(gov_run / "provider_authority_results.jsonl"):
        if line.get("forecast_call_id") == CALL_ID:
            target["provider_authority"] = line
    for line in read_jsonl(gov_run / "failed_call_ledger.jsonl"):
        if line.get("forecast_call_id") == CALL_ID:
            target["failed_call"] = line
    for line in read_jsonl(gov_run / "operation_journal.jsonl"):
        if line.get("forecast_call_id") == CALL_ID:
            target["operation_journal"].append(line)
    for line in read_jsonl(gov_run / "attempt_category_ledger.jsonl"):
        if line.get("forecast_call_id") == CALL_ID:
            target["attempt_category"] = line
    target["reconciliation"] = read_json(OUTPUT_ROOT / AUTHORITY_RECON_ID / "provider_authority_reconciliation.json")
    return target


def provider_error_without_payload(call: Mapping[str, Any], transport_result: Mapping[str, Any] | None) -> bool:
    if not isinstance(transport_result, Mapping):
        return False
    if str(transport_result.get("status") or "") != "error":
        return False
    if str(transport_result.get("request_status") or "") != "attempted":
        return False
    if str(transport_result.get("response_status") or "") != "error":
        return False
    if transport_result.get("provider_response_body") not in (None, ""):
        return False
    if transport_result.get("raw_response_blocks") not in (None, ""):
        return False
    if transport_result.get("request_id") not in (None, ""):
        return False
    error = str(transport_result.get("error") or "")
    requested_provider = str(transport_result.get("requested_provider") or "")
    requested_model = str(transport_result.get("requested_model") or "")
    selected_provider_route = str(transport_result.get("provider") or "")
    selected_model_route = str(transport_result.get("model") or "")
    return (
        call["provider"] == EXPECTED_PROVIDER
        and call["model"] == EXPECTED_MODEL
        and requested_provider == EXPECTED_PROVIDER
        and requested_model == EXPECTED_MODEL
        and selected_provider_route == EXPECTED_PROVIDER
        and selected_model_route == EXPECTED_MODEL
        and "Gemini 503" in error
    )


def successful_forecast_payload(transport_result: Mapping[str, Any] | None) -> bool:
    if not isinstance(transport_result, Mapping):
        return False
    return (
        str(transport_result.get("status") or "") == "ok"
        and str(transport_result.get("response_status") or "") == "ok"
        and bool(str(transport_result.get("provider_response_body") or ""))
        and bool(str(transport_result.get("raw_output") or ""))
    )


def original_attempt_reclassification(call: Mapping[str, Any], original: Mapping[str, Any]) -> dict[str, Any]:
    transport_row = dict(original["raw_transport"] or {})
    raw_transport = dict(transport_row.get("raw_transport_result") or {})
    if provider_error_without_payload(call, raw_transport):
        return {
            "classification_decision": "ORIGINAL_ATTEMPT_RECLASSIFIED_AS_FAILED_PROVIDER",
            "original_recorded_state": "FAILED_PROVIDER_AUTHORITY",
            "reconciled_scientific_state": "FAILED_PROVIDER",
            "reason": ORIGINAL_RECONCILED_REASON,
            "reconciliation_basis": {
                "provider_specific_503_error": raw_transport.get("error"),
                "provider_response_body_present": bool(raw_transport.get("provider_response_body")),
                "raw_response_blocks_present": bool(raw_transport.get("raw_response_blocks")),
                "provider_request_id": raw_transport.get("request_id"),
                "recoverable_forecast_payload_exists": successful_forecast_payload(raw_transport),
            },
        }
    return {
        "classification_decision": "ORIGINAL_ATTEMPT_CLASSIFICATION_NOT_RECONCILED",
        "original_recorded_state": "FAILED_PROVIDER_AUTHORITY",
        "reconciled_scientific_state": None,
        "reason": "FAILED_PROVIDER_RECONCILIATION_NOT_PROVEN",
        "reconciliation_basis": {
            "provider_specific_503_error": raw_transport.get("error"),
            "provider_response_body_present": bool(raw_transport.get("provider_response_body")),
            "raw_response_blocks_present": bool(raw_transport.get("raw_response_blocks")),
            "provider_request_id": raw_transport.get("request_id"),
            "recoverable_forecast_payload_exists": successful_forecast_payload(raw_transport),
        },
    }


def validation_guard_analysis(original: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "decision": "PROVIDER_ERROR_WRAPPER_VALIDATION_GUARD_REPAIRED",
        "earlier_contract_valid_reason": (
            "The earlier governance recovery marked contract validity from parse/validation failure counts only. "
            "Because the Gemini 503 call stopped at provider-authority failure before parse, the move incorrectly emitted "
            "`ALL_RECOVERED_FORECAST_RESULTS_CONTRACT_VALID` even though no forecast payload existed."
        ),
        "mechanical_defect": "contract-valid statement referred only to parse/validation failures rather than requiring a successful provider forecast payload for each claimed valid result",
        "guard_invariant": "response_status must equal ok and provider_response_body must be present before forecast parsing or contract validation can run",
        "prior_recovery_run": GOVERNANCE_RECOVERY_ID,
        "source_reconciliation_run": AUTHORITY_RECON_ID,
    }


def provider_error_path_repair_record(call: Mapping[str, Any], original: Mapping[str, Any]) -> dict[str, Any]:
    transport_row = dict(original["raw_transport"] or {})
    raw_transport = dict(transport_row.get("raw_transport_result") or {})
    return {
        "selected_provider_route": raw_transport.get("provider"),
        "requested_provider": raw_transport.get("requested_provider"),
        "requested_model": raw_transport.get("requested_model"),
        "selected_adapter": raw_transport.get("provider"),
        "provider_error_provider": EXPECTED_PROVIDER if "Gemini" in str(raw_transport.get("error") or "") else None,
        "provider_error_status": raw_transport.get("response_status"),
        "provider_error_message": raw_transport.get("error"),
        "provider_execution_identity_confirmed": False,
        "actual_provider_not_fabricated": True,
        "actual_model_not_fabricated": True,
        "repair_scope": "local execution evidence handling and replacement guard only",
        "call_id": call["forecast_call_id"],
    }


def initialize_run(run_dir: Path, repo_state: Mapping[str, Any], auth_result: Mapping[str, Any], target: Mapping[str, Any], original: Mapping[str, Any], class_recon: Mapping[str, Any], guard: Mapping[str, Any], error_path: Mapping[str, Any]) -> None:
    write_json(
        run_dir / "run_manifest.json",
        {
            "move": "FORECAST_PROVIDER_ERROR_REPLACEMENT_BATCH_002",
            "branch": repo_state["branch"],
            "start_head": repo_state["head"],
            "expected_start_head": EXPECTED_START_HEAD,
            "frozen_batch_id": FROZEN_BATCH_ID,
            "target_call_id": CALL_ID,
            "pack_type": PACK_TYPE,
            "forecast_contract": FORECAST_CONTRACT,
            "google_preflight": auth_result,
            "provider_calls_executed": 0,
            "google_writes_executed": 0,
            "market_data_calls_executed": 0,
            "research_ai_calls_executed": 0,
            "web_calls_executed": 0,
            "outcome_attachment_executed": 0,
            "matrix_updates_executed": 0,
            "forecast_accuracy_calculations_executed": 0,
            "no_batch_003_execution": True,
        },
    )
    write_json(
        run_dir / "governing_artifact_manifest.json",
        {
            "forecast_plan_id": PLAN_ID,
            "governance_recovery_id": GOVERNANCE_RECOVERY_ID,
            "provider_authority_reconciliation_id": AUTHORITY_RECON_ID,
        },
    )
    write_json(
        run_dir / "governance_authorization.json",
        {
            "authorized_call_id": CALL_ID,
            "authorization_type": REPLACEMENT_ATTEMPT_CATEGORY,
            "authorization_reason": REPLACEMENT_AUTH_REASON,
            "maximum_additional_provider_calls": 1,
            "maximum_dispatches_for_call_in_move": 1,
            "explicit_user_authorization": True,
        },
    )
    write_json(
        run_dir / "original_attempt_evidence.json",
        {
            "call_id": CALL_ID,
            "original_raw_transport": original["raw_transport"],
            "original_raw_provider_output": original["raw_provider"],
            "original_provider_authority_row": original["provider_authority"],
            "original_failed_call_row": original["failed_call"],
            "original_operation_journal_rows": original["operation_journal"],
        },
    )
    write_json(run_dir / "classification_reconciliation.json", class_recon)
    write_json(run_dir / "error_wrapper_validation_analysis.json", guard)
    write_json(run_dir / "provider_error_path_repair.json", error_path)
    write_json(
        run_dir / "replacement_execution_contract.json",
        {
            "scope": "single_governance_authorized_replacement",
            "target_call_id": CALL_ID,
            "provider": EXPECTED_PROVIDER,
            "model": EXPECTED_MODEL,
            "pack_type": PACK_TYPE,
            "forecast_contract": FORECAST_CONTRACT,
            "fresh_apps_script_client_per_dispatch": True,
            "apps_script_timeout_seconds": batch_exec.SCRIPT_HTTP_TIMEOUT_SECONDS,
            "bridge_hard_timeout_seconds": 180,
            "maximum_provider_calls": 1,
            "no_automatic_retry": True,
            "no_batch_003_execution": True,
        },
    )
    for name in (
        "operation_journal.jsonl",
        "raw_transport_results.jsonl",
        "raw_provider_outputs.jsonl",
        "provider_authority_results.jsonl",
        "forecast_parse_results.jsonl",
        "forecast_validation_results.jsonl",
        "normalized_forecast_results.jsonl",
        "failed_call_ledger.jsonl",
    ):
        (run_dir / name).write_text("")


def replacement_authoritative_selection(terminal_state: str, run_dir: Path) -> dict[str, Any]:
    if terminal_state == "SUCCEEDED_VALID":
        return {
            "forecast_call_id": CALL_ID,
            "selected_result_run_id": run_dir.name,
            "selected_terminal_state": terminal_state,
            "authoritative_result": "REPLACEMENT_RESULT",
            "authority_reason": "ORIGINAL_ATTEMPT_RETURNED_PROVIDER_503_WITH_NO_FORECAST_PAYLOAD_AND_SINGLE_REPLACEMENT_WAS_EXPLICITLY_AUTHORIZED",
            "original_attempt_reference": {
                "governance_recovery_id": GOVERNANCE_RECOVERY_ID,
                "provider_authority_reconciliation_id": AUTHORITY_RECON_ID,
            },
        }
    return {
        "forecast_call_id": CALL_ID,
        "selected_result_run_id": None,
        "selected_terminal_state": terminal_state,
        "authoritative_result": "NO_AUTHORITATIVE_RESULT_SELECTED",
        "authority_reason": "REPLACEMENT_DID_NOT_PRODUCE_CONTRACT_VALID_FORECAST",
        "original_attempt_reference": {
            "governance_recovery_id": GOVERNANCE_RECOVERY_ID,
            "provider_authority_reconciliation_id": AUTHORITY_RECON_ID,
        },
    }


def default_dispatch(script_service: Any, script_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    return batch_exec.default_dispatch(script_service, script_id, payload)


def execute_replacement(
    *,
    output_root: Path = OUTPUT_ROOT,
    fixed_timestamp: str | None = None,
    auth_preflight: Callable[[], Mapping[str, Any]] = batch_exec.verify_google_preflight,
    dispatch: Callable[[Any, str, Mapping[str, Any]], Mapping[str, Any]] = default_dispatch,
) -> dict[str, Any]:
    branch = git_branch()
    head = git_head()
    if branch != "codex/immediate-impulse-outcome-recovery-r1":
        raise ProviderErrorReplacementError("BRANCH_MISMATCH")
    if head != EXPECTED_START_HEAD or not is_descendant_of(EXPECTED_START_HEAD):
        raise ProviderErrorReplacementError("HEAD_ANCESTRY_NOT_CLEAN")
    repo_state = {"branch": branch, "head": head}

    target = load_target_bundle()
    original = load_original_failed_evidence()
    class_recon = original_attempt_reclassification(target["call"], original)
    guard = validation_guard_analysis(original)
    error_path = provider_error_path_repair_record(target["call"], original)

    if class_recon["classification_decision"] != "ORIGINAL_ATTEMPT_RECLASSIFIED_AS_FAILED_PROVIDER":
        raise ProviderErrorReplacementError("ORIGINAL_CLASSIFICATION_NOT_RECONCILED")
    if find_existing_valid_result(CALL_ID, output_root) is not None:
        raise ProviderErrorReplacementError("AUTHORITATIVE_RESULT_ALREADY_EXISTS")

    leakage = batch_exec.leakage_audit(target["prompt_row"]["prompt_text"], target["prompt_row"]["prompt_payload"], PACK_TYPE)
    if not leakage["passed"]:
        raise ProviderErrorReplacementError("HISTORICAL_LEAKAGE_DETECTED")

    auth_result = dict(auth_preflight())
    run_dir = materialize_run(output_root, fixed_timestamp=fixed_timestamp)
    initialize_run(run_dir, repo_state, auth_result, target, original, class_recon, guard, error_path)

    script_service_factory, script_id = batch_exec.build_default_script_service_factory()
    append_jsonl(
        run_dir / "operation_journal.jsonl",
        {
            "event": "REPLACEMENT_STARTED",
            "forecast_call_id": CALL_ID,
            "attempt_category": REPLACEMENT_ATTEMPT_CATEGORY,
            "provider": EXPECTED_PROVIDER,
            "model": EXPECTED_MODEL,
            "pack_type": PACK_TYPE,
            "started_at": now(),
        },
    )

    payload = step6.bridge_payload(target["pack_payload"], target["prompt_row"]["prompt_text"], run_id=run_dir.name, arm="BASELINE")
    transport_meta = dispatch(script_service_factory(), script_id, payload)
    transport_result = transport_meta.get("result") if isinstance(transport_meta, Mapping) else None
    raw_output = transport_result.get("raw_output") if isinstance(transport_result, Mapping) else None
    raw_transport_row = {
        "forecast_call_id": CALL_ID,
        "attempt_category": REPLACEMENT_ATTEMPT_CATEGORY,
        "dispatch_timestamp": now(),
        "requested_provider": EXPECTED_PROVIDER,
        "requested_model": EXPECTED_MODEL,
        "selected_provider_route": transport_result.get("provider") if isinstance(transport_result, Mapping) else None,
        "selected_adapter": transport_result.get("provider") if isinstance(transport_result, Mapping) else None,
        "provider_error_provider": EXPECTED_PROVIDER if isinstance(transport_result, Mapping) and "Gemini" in str(transport_result.get("error") or "") else None,
        "provider_error_status": transport_result.get("response_status") if isinstance(transport_result, Mapping) else None,
        "provider_error_message": transport_result.get("error") if isinstance(transport_result, Mapping) else None,
        "provider_execution_identity_confirmed": False,
        "actual_provider": transport_result.get("actual_provider") if isinstance(transport_result, Mapping) else None,
        "actual_model": transport_result.get("actual_model") if isinstance(transport_result, Mapping) else None,
        "raw_transport_result": transport_result,
        "transport_ok": bool(transport_meta.get("ok")) if isinstance(transport_meta, Mapping) else False,
        "transport_request": transport_meta.get("request") if isinstance(transport_meta, Mapping) else None,
        "transport_classification": transport_meta.get("classification") if isinstance(transport_meta, Mapping) else None,
        "stop_reason": transport_result.get("stop_reason") if isinstance(transport_result, Mapping) else None,
        "prompt_tokens": transport_result.get("prompt_tokens") if isinstance(transport_result, Mapping) else None,
        "completion_tokens": transport_result.get("completion_tokens") if isinstance(transport_result, Mapping) else None,
        "configured_output_token_limit": None,
        "response_length": len(raw_output) if isinstance(raw_output, str) else 0,
        "completion_timestamp": transport_result.get("completed_timestamp") if isinstance(transport_result, Mapping) else None,
        "pack_row_fingerprint": target["call"]["pack_row_fingerprint"],
        "prompt_fingerprint": target["prompt_fingerprint"]["prompt_text_fingerprint"],
        "google_preflight_result": auth_result["read_only_preflight_result"],
    }
    append_jsonl(run_dir / "raw_transport_results.jsonl", raw_transport_row)
    append_jsonl(
        run_dir / "raw_provider_outputs.jsonl",
        {
            "forecast_call_id": CALL_ID,
            "attempt_category": REPLACEMENT_ATTEMPT_CATEGORY,
            "episode_id": target["call"]["episode_id"],
            "provider": EXPECTED_PROVIDER,
            "model": EXPECTED_MODEL,
            "pack_type": PACK_TYPE,
            "pack_row_fingerprint": target["call"]["pack_row_fingerprint"],
            "prompt_fingerprint": target["prompt_fingerprint"]["prompt_text_fingerprint"],
            "raw_provider_output": raw_output,
        },
    )

    terminal_state = None
    failure_reason = None
    raw_claimed_provider = None
    selection = None
    authority_row = None
    parsed = None

    if not transport_meta.get("ok"):
        terminal_state = batch_exec.classify_transport_failure(transport_result)
        failure_reason = transport_meta.get("classification", {}).get("category", "TRANSPORT_NOT_OK")
    elif provider_error_without_payload(target["call"], transport_result):
        terminal_state = "FAILED_PROVIDER"
        failure_reason = ORIGINAL_RECONCILED_REASON
    elif not successful_forecast_payload(transport_result):
        terminal_state = "FAILED_PROVIDER"
        failure_reason = "PROVIDER_RESPONSE_NOT_USABLE_FOR_FORECAST_PARSING"
    else:
        authority_row = batch_exec.provider_authority_result(target["call"], transport_result) | {"attempt_category": REPLACEMENT_ATTEMPT_CATEGORY}
        append_jsonl(run_dir / "provider_authority_results.jsonl", authority_row)
        if not authority_row["authority_passed"]:
            terminal_state = "FAILED_PROVIDER_AUTHORITY"
            failure_reason = authority_row["reason"]
        else:
            try:
                parsed, parse_audit = step6.normalize_provider_output(raw_output)
                if isinstance(parsed, Mapping):
                    raw_claimed_provider = parsed.get("provider")
                append_jsonl(
                    run_dir / "forecast_parse_results.jsonl",
                    {
                        "forecast_call_id": CALL_ID,
                        "attempt_category": REPLACEMENT_ATTEMPT_CATEGORY,
                        "parse_status": "PARSED",
                        "raw_claimed_provider": raw_claimed_provider,
                        "parse_audit": parse_audit,
                    },
                )
            except Exception as exc:
                terminal_state = "FAILED_PARSE"
                failure_reason = str(exc)
                append_jsonl(
                    run_dir / "forecast_parse_results.jsonl",
                    {
                        "forecast_call_id": CALL_ID,
                        "attempt_category": REPLACEMENT_ATTEMPT_CATEGORY,
                        "parse_status": "FAILED_PARSE",
                        "raw_claimed_provider": raw_claimed_provider,
                        "reason": str(exc),
                    },
                )
            if terminal_state is None:
                try:
                    prediction, paths = step6.response_to_contract(
                        parsed,
                        target["pack_payload"],
                        run_id=run_dir.name,
                        created_ts=str(transport_result.get("completed_timestamp") or now()),
                        raw_output=raw_output,
                        bridge_result=transport_result,
                    )
                    append_jsonl(
                        run_dir / "forecast_validation_results.jsonl",
                        {
                            "forecast_call_id": CALL_ID,
                            "attempt_category": REPLACEMENT_ATTEMPT_CATEGORY,
                            "validation_status": "VALID",
                            "prediction_id": prediction["prediction_id"],
                            "path_count": len(paths),
                        },
                    )
                    append_jsonl(
                        run_dir / "normalized_forecast_results.jsonl",
                        {
                            "forecast_call_id": CALL_ID,
                            "episode_id": target["call"]["episode_id"],
                            "provider": EXPECTED_PROVIDER,
                            "model": EXPECTED_MODEL,
                            "pack_type": PACK_TYPE,
                            "attempt_category": REPLACEMENT_ATTEMPT_CATEGORY,
                            "pack_row_identity": target["call"]["pack_row_identity"],
                            "pack_row_fingerprint": target["call"]["pack_row_fingerprint"],
                            "prompt_text_fingerprint": target["prompt_fingerprint"]["prompt_text_fingerprint"],
                            "prompt_context_fingerprint": target["prompt_fingerprint"]["prompt_context_fingerprint"],
                            "terminal_state": "SUCCEEDED_VALID",
                            "raw_claimed_provider": raw_claimed_provider,
                            "prediction": prediction,
                            "paths": paths,
                        },
                    )
                    terminal_state = "SUCCEEDED_VALID"
                except Exception as exc:
                    terminal_state = "FAILED_VALIDATION"
                    failure_reason = str(exc)
                    append_jsonl(
                        run_dir / "forecast_validation_results.jsonl",
                        {
                            "forecast_call_id": CALL_ID,
                            "attempt_category": REPLACEMENT_ATTEMPT_CATEGORY,
                            "validation_status": "FAILED_VALIDATION",
                            "reason": str(exc),
                        },
                    )

    if authority_row is None:
        authority_row = {
            "forecast_call_id": CALL_ID,
            "manifest_provider": EXPECTED_PROVIDER,
            "manifest_model": EXPECTED_MODEL,
            "actual_provider": transport_result.get("actual_provider") if isinstance(transport_result, Mapping) else None,
            "actual_model": transport_result.get("actual_model") if isinstance(transport_result, Mapping) else None,
            "authority_passed": terminal_state == "SUCCEEDED_VALID" and transport_result.get("actual_provider") == EXPECTED_PROVIDER and transport_result.get("actual_model") == EXPECTED_MODEL if isinstance(transport_result, Mapping) else False,
            "reason": "NOT_REACHED" if terminal_state in {"FAILED_PROVIDER", "FAILED_TRANSPORT"} else batch_exec.provider_authority_result(target["call"], transport_result)["reason"] if isinstance(transport_result, Mapping) else "NOT_REACHED",
            "attempt_category": REPLACEMENT_ATTEMPT_CATEGORY,
        }
        append_jsonl(run_dir / "provider_authority_results.jsonl", authority_row)

    if terminal_state != "SUCCEEDED_VALID":
        failed_row = {
            "forecast_call_id": CALL_ID,
            "episode_id": target["call"]["episode_id"],
            "provider": EXPECTED_PROVIDER,
            "model": EXPECTED_MODEL,
            "pack_type": PACK_TYPE,
            "attempt_category": REPLACEMENT_ATTEMPT_CATEGORY,
            "terminal_state": terminal_state,
            "reason": failure_reason,
            "raw_claimed_provider": raw_claimed_provider,
        }
        append_jsonl(run_dir / "failed_call_ledger.jsonl", failed_row)
        append_jsonl(run_dir / "operation_journal.jsonl", {"event": terminal_state, **failed_row})
    else:
        append_jsonl(
            run_dir / "operation_journal.jsonl",
            {
                "event": "SUCCEEDED_VALID",
                "forecast_call_id": CALL_ID,
                "attempt_category": REPLACEMENT_ATTEMPT_CATEGORY,
                "pack_type": PACK_TYPE,
            },
        )

    selection = replacement_authoritative_selection(terminal_state, run_dir)
    write_json(run_dir / "authoritative_result_selection.json", selection)

    batch002_valid = 12 if terminal_state == "SUCCEEDED_VALID" else 11
    unresolved = 0 if terminal_state == "SUCCEEDED_VALID" else 1
    authority_conflicts = 0 if terminal_state == "SUCCEEDED_VALID" else (1 if terminal_state == "FAILED_PROVIDER_AUTHORITY" else 0)
    cumulative = 12 + batch002_valid
    remaining = 564 - cumulative
    write_json(
        run_dir / "batch_002_final_reconciliation.json",
        {
            "frozen_batch_id": FROZEN_BATCH_ID,
            "authoritative_valid_results": batch002_valid,
            "provider_authority_conflicts": authority_conflicts,
            "missing_authoritative_results": unresolved,
            "duplicate_authoritative_results": 0,
            "cumulative_authoritative_valid_results": cumulative,
            "remaining_planned_forecast_calls": remaining,
            "no_batch_003_execution": True,
        },
    )

    replacement_decision = (
        "SINGLE_REPLACEMENT_SUCCEEDED_VALID"
        if terminal_state == "SUCCEEDED_VALID"
        else "SINGLE_REPLACEMENT_FAILED"
    )
    batch_decision = "FORECAST_BATCH_002_COMPLETE" if terminal_state == "SUCCEEDED_VALID" else "FORECAST_BATCH_002_REMAINS_INCOMPLETE"
    next_phase = "READY_TO_EXECUTE_FORECAST_BATCH_003" if terminal_state == "SUCCEEDED_VALID" else "REPAIR_BEFORE_FORECAST_BATCH_003"
    summary = {
        "classification_decision": class_recon["classification_decision"],
        "validation_guard_decision": guard["decision"],
        "replacement_decision": replacement_decision,
        "batch_002_decision": batch_decision,
        "next_phase_decision": next_phase,
        "replacement_attempt_count": 1,
        "replacement_terminal_state": terminal_state,
        "replacement_failure_reason": failure_reason,
        "leakage_control_result": "NO_HISTORICAL_LEAKAGE_DETECTED",
        "raw_output_preservation_result": "PRESERVED_BEFORE_PARSE_FOR_REPLACEMENT_ATTEMPT",
        "batch_002_authoritative_valid_results": batch002_valid,
        "batch_002_unresolved_results": unresolved,
        "batch_002_provider_authority_conflicts": authority_conflicts,
        "cumulative_validated_forecast_calls": cumulative,
        "remaining_planned_forecast_calls": remaining,
    }
    write_json(run_dir / "replacement_summary.json", summary)
    write_json(
        run_dir / "replacement_decision.json",
        {
            "classification_decision": class_recon["classification_decision"],
            "validation_guard_decision": guard["decision"],
            "replacement_decision": replacement_decision,
            "batch_002_decision": batch_decision,
            "next_phase_decision": next_phase,
        },
    )
    update_run_manifest(
        run_dir / "run_manifest.json",
        provider_calls_executed=1,
        successful_valid_calls=1 if terminal_state == "SUCCEEDED_VALID" else 0,
        failed_provider_calls=1 if terminal_state == "FAILED_PROVIDER" else 0,
        failed_provider_authority_calls=1 if terminal_state == "FAILED_PROVIDER_AUTHORITY" else 0,
        failed_transport_calls=1 if terminal_state == "FAILED_TRANSPORT" else 0,
        failed_parse_calls=1 if terminal_state == "FAILED_PARSE" else 0,
        failed_validation_calls=1 if terminal_state == "FAILED_VALIDATION" else 0,
    )
    return {"run_dir": run_dir, "summary": summary, "selection": selection, "terminal_state": terminal_state}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixed-timestamp", default=None)
    args = parser.parse_args(argv)
    result = execute_replacement(fixed_timestamp=args.fixed_timestamp)
    print(
        json.dumps(
            {
                "run_dir": str(result["run_dir"]),
                "classification_decision": result["summary"]["classification_decision"],
                "validation_guard_decision": result["summary"]["validation_guard_decision"],
                "replacement_decision": result["summary"]["replacement_decision"],
                "batch_002_decision": result["summary"]["batch_002_decision"],
                "next_phase_decision": result["summary"]["next_phase_decision"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
