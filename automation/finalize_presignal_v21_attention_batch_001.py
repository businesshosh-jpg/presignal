#!/usr/bin/env python3
"""Finalize Batch 001 from 11 imported valid results plus one corrected retry."""
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
from typing import Any, Callable, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import bind_presignal_v21_step8_r3_runtime_v1 as binding
from automation import execute_presignal_v21_attention_batch_001 as batch
from automation import google_clients

PLAN_ID = "PPHB-R1-ATTENTION-EXECUTION-PLAN-20260729T010207Z-3fcd59f96f3c"
PRIOR_FINALIZATION_ID = "PPHB-R1-ATTENTION-BATCH-001-FINALIZATION-20260729T023607Z-eb4bd2a9277c"
FAILURE_AUDIT_ID = "PPHB-R1-ATTENTION-BATCH-001-ANTHROPIC-FAILURE-AUDIT-20260729T032157Z-a5ae0ae86b0f"
AUTHORIZED_CALL_ID = "ATN_d7c95516e95938578834"
EXPECTED_START_HEAD = "3a3efd2309693b948e27f03540f127348bc7e518"
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_execution"
PLAN_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_execution_plan" / PLAN_ID
PRIOR_FINALIZATION_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_execution" / PRIOR_FINALIZATION_ID
FAILURE_AUDIT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_failure_audit" / FAILURE_AUDIT_ID
TOKEN_PATH = Path("/Users/junhoshino/projects/presignal/local/token.json")
EXPECTED_IMPORTED_COUNT = 11
EXPECTED_TOTAL_CALLS = 12


class CorrectedFinalizationError(RuntimeError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def is_descendant_of(commit: str) -> bool:
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
        cwd=ROOT,
    ).returncode == 0


def git_status_lines() -> list[str]:
    output = subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True)
    return [line for line in output.splitlines() if line.strip()]


def path_ref(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(canonical_json(dict(row)) + "\n" for row in rows))


def append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(canonical_json(dict(row)) + "\n")


def journal_event(path: Path, event: str, **extra: Any) -> None:
    append_jsonl(path, {"event": event, "timestamp": now_iso(), **extra})


def operation_transcript(path: Path) -> list[dict[str, Any]]:
    return read_jsonl(path) if path.exists() else []


def verify_governing_artifacts() -> dict[str, Any]:
    if not is_descendant_of(EXPECTED_START_HEAD):
        raise CorrectedFinalizationError("AUTHORIZED_START_HEAD_NOT_ANCESTOR")
    for root in (PLAN_ROOT, PRIOR_FINALIZATION_ROOT, FAILURE_AUDIT_ROOT):
        if not root.exists():
            raise CorrectedFinalizationError("GOVERNING_ARTIFACT_MISSING:" + root.name)
    batch.verify_plan_fingerprints()

    prior_results = read_jsonl(PRIOR_FINALIZATION_ROOT / "final_normalized_attention_results.jsonl")
    if len(prior_results) != EXPECTED_IMPORTED_COUNT:
        raise CorrectedFinalizationError("IMPORTED_RESULT_COUNT_MISMATCH")
    imported_ids = [row["call_id"] for row in prior_results]
    if len(set(imported_ids)) != EXPECTED_IMPORTED_COUNT:
        raise CorrectedFinalizationError("IMPORTED_RESULT_IDS_NOT_UNIQUE")
    if AUTHORIZED_CALL_ID in set(imported_ids):
        raise CorrectedFinalizationError("AUTHORIZED_CALL_ALREADY_VALID")

    remaining = read_jsonl(PRIOR_FINALIZATION_ROOT / "remaining_failed_calls.jsonl")
    if len(remaining) != 1 or remaining[0]["call_id"] != AUTHORIZED_CALL_ID:
        raise CorrectedFinalizationError("PRIOR_REMAINING_FAILURE_LEDGER_MISMATCH")

    retry_auth = read_json(FAILURE_AUDIT_ROOT / "retry_authorization_recommendation.json")
    if (
        retry_auth.get("decision") != "AUTHORIZE_ONE_CORRECTED_RETRY"
        or retry_auth.get("maximum_additional_calls") != 1
        or retry_auth.get("call_id") != AUTHORIZED_CALL_ID
    ):
        raise CorrectedFinalizationError("FAILURE_AUDIT_AUTHORIZATION_MISMATCH")

    correction = read_json(FAILURE_AUDIT_ROOT / "minimal_retry_correction_contract.json")
    if correction.get("call_id") != AUTHORIZED_CALL_ID:
        raise CorrectedFinalizationError("CORRECTION_CONTRACT_CALL_ID_MISMATCH")
    exact = correction.get("exact_correction") or {}
    if (exact.get("generation_settings") or {}).get("max_output_tokens") != 8192:
        raise CorrectedFinalizationError("CORRECTION_MAX_OUTPUT_TOKENS_MISMATCH")
    if (exact.get("generation_settings") or {}).get("preserve_raw_before_parse") is not True:
        raise CorrectedFinalizationError("CORRECTION_RAW_PRESERVATION_MISMATCH")

    contract = batch.load_runtime_contract()
    instruction = binding.attention_instruction(contract, "Anthropic")
    if exact.get("attention_instruction_suffix") not in instruction:
        raise CorrectedFinalizationError("RUNTIME_CORRECTION_RULE_NOT_ACTIVE")
    generation_settings = binding.generation_settings(contract, "Anthropic", "ATTENTION")
    if generation_settings != {"max_output_tokens": 8192, "preserve_raw_before_parse": True}:
        raise CorrectedFinalizationError("RUNTIME_GENERATION_SETTINGS_MISMATCH")

    plan_calls = batch.load_batch_calls()
    by_call = {row["call_id"]: row for row in plan_calls}
    retry_call = by_call.get(AUTHORIZED_CALL_ID)
    if retry_call is None:
        raise CorrectedFinalizationError("AUTHORIZED_CALL_NOT_IN_FROZEN_BATCH")
    if retry_call["provider"] != "Anthropic" or retry_call["model"] != "claude-haiku-4-5":
        raise CorrectedFinalizationError("AUTHORIZED_CALL_ASSIGNMENT_DRIFT")

    return {
        "prior_results": prior_results,
        "remaining": remaining,
        "retry_auth": retry_auth,
        "correction": correction,
        "runtime_contract": contract,
        "retry_call": retry_call,
        "working_tree": git_status_lines(),
        "fingerprints": {
            "plan_contract_sha256": file_sha256(PLAN_ROOT / "attention_execution_contract.json"),
            "prior_final_results_sha256": file_sha256(PRIOR_FINALIZATION_ROOT / "final_normalized_attention_results.jsonl"),
            "failure_audit_correction_sha256": file_sha256(FAILURE_AUDIT_ROOT / "minimal_retry_correction_contract.json"),
            "failure_audit_retry_auth_sha256": file_sha256(FAILURE_AUDIT_ROOT / "retry_authorization_recommendation.json"),
            "failure_audit_root_cause_sha256": file_sha256(FAILURE_AUDIT_ROOT / "root_cause_decision.json"),
        },
    }


def preflight_google_auth() -> dict[str, Any]:
    os.environ["PRESIGNAL_GOOGLE_TOKEN_PATH"] = str(TOKEN_PATH)
    if not TOKEN_PATH.exists():
        raise CorrectedFinalizationError("GOOGLE_TOKEN_PATH_MISSING")
    credentials = google_clients.load_credentials(False, token_path=TOKEN_PATH)
    sheets = google_clients.build_sheets_service(credentials)
    spreadsheet = (
        sheets.spreadsheets()
        .get(spreadsheetId=google_clients.DEFAULT_SPREADSHEET_ID, fields="spreadsheetId,properties.title")
        .execute()
    )
    script_service = google_clients.build_script_service(credentials, 300)
    script = script_service.projects().getContent(scriptId=google_clients.default_script_id()).execute()
    return {
        "token_path_resolution_method": "explicit_env_then_google_clients.load_credentials(token_path=TOKEN_PATH)",
        "resolved_token_path": str(TOKEN_PATH),
        "token_reused": True,
        "spreadsheet_id": spreadsheet["spreadsheetId"],
        "spreadsheet_title": spreadsheet["properties"]["title"],
        "script_id": google_clients.default_script_id(),
        "script_file_count": len(script.get("files", [])),
        "google_writes": 0,
    }


def materialize_run(output_root: Path, fixed_timestamp: str | None = None) -> Path:
    ts = fixed_timestamp or now_stamp()
    seed = {
        "plan": PLAN_ID,
        "prior_finalization": PRIOR_FINALIZATION_ID,
        "failure_audit": FAILURE_AUDIT_ID,
        "authorized_call": AUTHORIZED_CALL_ID,
        "timestamp": ts,
    }
    run_id = "PPHB-R1-ATTENTION-BATCH-001-CORRECTED-FINALIZATION-" + ts + "-" + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:12]
    return output_root / run_id


def import_prior_valid_results(run_dir: Path, rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    imported_rows: list[dict[str, Any]] = []
    final_results: list[dict[str, Any]] = []
    episode_map: list[dict[str, Any]] = []
    for row in rows:
        imported_rows.append(
            {
                "call_id": row["call_id"],
                "source_finalization_run_identity": PRIOR_FINALIZATION_ID,
                "source_live_run_identity": "PPHB-R1-ATTENTION-EXECUTION-BATCH-001-20260729T013947Z-2cce371f8a13",
                "provider": row["provider"],
                "model": row["model"],
                "source_session_id": row["source_session_id"],
                "raw_response_reference": path_ref(PRIOR_FINALIZATION_ROOT / "final_normalized_attention_results.jsonl"),
                "normalization_applied": row["attention_result"].get("_provider_identity_normalization"),
                "validation_result": "SUCCEEDED_VALID",
                "import_status": "IMPORTED_VALIDATED_RESULT",
                "provider_recall_performed": False,
            }
        )
        final_results.append(dict(row))
        for episode_id in row["episode_ids"]:
            episode_map.append(
                {
                    "call_id": row["call_id"],
                    "episode_id": episode_id,
                    "source_session_id": row["source_session_id"],
                    "provider": row["provider"],
                    "model": row["model"],
                    "result_source": "IMPORTED_VALIDATED_RESULT",
                }
            )
    write_jsonl(run_dir / "imported_valid_result_ledger.jsonl", imported_rows)
    return imported_rows, final_results, episode_map


def execute_retry(
    *,
    run_dir: Path,
    retry_call: Mapping[str, Any],
    contract: Mapping[str, Any],
    dispatcher: Callable[[Mapping[str, Any]], Mapping[str, Any]],
) -> dict[str, Any]:
    source_sessions, source_members = batch.read_source_sessions()
    session = source_sessions[retry_call["source_session_id"]]
    members = source_members[retry_call["source_session_id"]]
    correction_identity = FAILURE_AUDIT_ID
    settings = binding.generation_settings(contract, retry_call["provider"], "ATTENTION")
    for name in (
        "raw_transport_results.jsonl",
        "raw_provider_outputs.jsonl",
        "normalized_attention_results.jsonl",
        "attention_validation_results.jsonl",
        "episode_attention_result_map.jsonl",
        "failed_call_ledger.jsonl",
    ):
        path = run_dir / name
        if not path.exists():
            path.write_text("")
    identity = batch.attention_input_identity(retry_call, session, members, contract)
    journal_event(
        run_dir / "operation_journal.jsonl",
        "FINAL_CORRECTED_RETRY_STARTED",
        call_id=retry_call["call_id"],
        attempt_number=3,
        provider=retry_call["provider"],
        model=retry_call["model"],
        source_session_id=retry_call["source_session_id"],
        attention_input_fingerprint=identity["request_fingerprint"],
        correction_contract_identity=correction_identity,
        max_output_tokens=settings.get("max_output_tokens"),
        preserve_raw_before_parse=settings.get("preserve_raw_before_parse") is True,
        state="FINAL_CORRECTED_RETRY_STARTED",
    )
    result = batch.execute_call(
        run_dir=run_dir,
        call=retry_call,
        session=session,
        members=members,
        contract=contract,
        dispatcher=dispatcher,
    )
    transport_rows = read_jsonl(run_dir / "raw_transport_results.jsonl")
    raw_rows = read_jsonl(run_dir / "raw_provider_outputs.jsonl")
    validation_rows = read_jsonl(run_dir / "attention_validation_results.jsonl")
    normalized_rows = read_jsonl(run_dir / "normalized_attention_results.jsonl")
    failed_rows = read_jsonl(run_dir / "failed_call_ledger.jsonl")
    if len(transport_rows) > 1 or len(raw_rows) > 1 or len(validation_rows) > 1:
        raise CorrectedFinalizationError("RETRY_OUTPUT_CARDINALITY_VIOLATION")
    transport = transport_rows[0] if transport_rows else {}
    raw_row = raw_rows[0] if raw_rows else {}
    validation = validation_rows[0] if validation_rows else {}
    normalized = normalized_rows[0] if normalized_rows else None
    failed = failed_rows[0] if failed_rows else None
    write_json(run_dir / "retry_raw_transport_result.json", transport)
    raw_preserved = {
        **raw_row,
        "raw_output_returned": bool(raw_row.get("raw_output") not in (None, "")),
        "raw_output_absence_reason": None if raw_row.get("raw_output") not in (None, "") else "TRANSPORT_RETURNED_NO_PROVIDER_TEXT",
    }
    write_json(run_dir / "retry_raw_provider_output.json", raw_preserved)
    write_json(
        run_dir / "retry_metadata.json",
        {
            "call_id": retry_call["call_id"],
            "provider": retry_call["provider"],
            "model": retry_call["model"],
            "source_session_id": retry_call["source_session_id"],
            "stop_reason": transport.get("stop_reason"),
            "prompt_tokens": transport.get("prompt_tokens"),
            "completion_tokens": transport.get("completion_tokens"),
            "configured_max_output_tokens": transport.get("configured_max_output_tokens"),
            "preserve_raw_before_parse": transport.get("preserve_raw_before_parse"),
            "response_length": transport.get("response_length"),
            "completed_timestamp": transport.get("completed_timestamp"),
            "usage_metadata": transport.get("usage_metadata"),
        },
    )
    parse_result = {
        "call_id": retry_call["call_id"],
        "final_state": result["final_state"],
        "parse_result": "PARSED" if result["final_state"] in {"SUCCEEDED_VALID", "FAILED_VALIDATION"} else "FAILED_PARSE",
        "error_code": validation.get("error_code"),
        "error_summary": validation.get("error_summary"),
    }
    validation_result = {
        "call_id": retry_call["call_id"],
        "final_state": result["final_state"],
        "validation_result": "VALID" if result["final_state"] == "SUCCEEDED_VALID" else ("FAILED_VALIDATION" if result["final_state"] == "FAILED_VALIDATION" else "NOT_REACHED"),
        "normalized_result_count": len(normalized_rows),
        "failed_result_count": len(failed_rows),
    }
    write_json(run_dir / "retry_parse_result.json", parse_result)
    write_json(run_dir / "retry_validation_result.json", validation_result)
    return {
        "terminal_state": result["final_state"],
        "transport": transport,
        "raw": raw_preserved,
        "validation": validation,
        "normalized": normalized,
        "failed": failed,
    }


def reconstruct_attention_payload(normalized_row: Mapping[str, Any], session_id: str, provider: str) -> dict[str, Any]:
    rows = list(normalized_row["validated_attention_rows"])
    return {
        "object": "session_attention_map",
        "session_id": session_id,
        "provider": provider,
        "attention_items": [
            {
                "event_id": row["event_id"],
                "attention_label": row["attention_label"],
                "attention_rank": row["attention_rank"],
                "attention_reason": row["attention_reason"],
                "expected_market_channel": row["expected_market_channel"],
                "driver_role": row["driver_role"],
                "confidence": row["confidence"],
            }
            for row in rows
        ],
        "session_attention_summary": "Recovered from corrected final retry strict validated result.",
        "status": "ok",
    }


def finalize(
    *,
    output_root: Path = OUTPUT_ROOT,
    fixed_timestamp: str | None = None,
    dispatcher: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    preflight_override: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    checked = verify_governing_artifacts()
    preflight = (preflight_override or preflight_google_auth)()
    run_dir = materialize_run(output_root, fixed_timestamp=fixed_timestamp)
    run_dir.mkdir(parents=True, exist_ok=False)

    write_json(
        run_dir / "run_manifest.json",
        {
            "run_id": run_dir.name,
            "generated_at": now_iso(),
            "git_head": git_head(),
            "governing_plan_identity": PLAN_ID,
            "governing_failure_audit_identity": FAILURE_AUDIT_ID,
            "prior_finalization_identity": PRIOR_FINALIZATION_ID,
            "authorized_call_id": AUTHORIZED_CALL_ID,
            "authorized_provider_calls": 1,
            "provider_calls_executed": 0,
            "google_writes": 0,
            "forecast_calls_executed": 0,
            "pack_construction_executed": 0,
            "research_ai_calls": 0,
            "market_data_calls": 0,
            "web_calls": 0,
        },
    )
    write_json(
        run_dir / "governing_artifact_manifest.json",
        {
            "plan_identity": PLAN_ID,
            "plan_root": path_ref(PLAN_ROOT),
            "prior_finalization_identity": PRIOR_FINALIZATION_ID,
            "prior_finalization_root": path_ref(PRIOR_FINALIZATION_ROOT),
            "failure_audit_identity": FAILURE_AUDIT_ID,
            "failure_audit_root": path_ref(FAILURE_AUDIT_ROOT),
            "fingerprints": checked["fingerprints"],
        },
    )
    write_json(
        run_dir / "corrected_retry_contract.json",
        {
            "governing_plan_identity": PLAN_ID,
            "prior_finalization_identity": PRIOR_FINALIZATION_ID,
            "failure_audit_identity": FAILURE_AUDIT_ID,
            "expected_imported_valid_result_count": 11,
            "authorized_retry_call_id": AUTHORIZED_CALL_ID,
            "authorized_retry_count": 1,
            "canonical_attention_contract_identity": checked["correction"]["canonical_contract_identity"],
            "provider_alias_normalization_rule": "validated exact alias only from automation/presignal_v21_provider_adapters_v1.py",
            "exact_correction": checked["correction"]["exact_correction"],
            "failure_behavior": "single corrected retry only; fail closed if invalid",
            "immutability_requirements": "all governing runs remain append-only and unchanged",
        },
    )

    imported_rows, final_results, episode_map = import_prior_valid_results(run_dir, checked["prior_results"])
    retry_call = checked["retry_call"]
    write_json(
        run_dir / "corrected_retry_manifest.json",
        {
            "call_id": retry_call["call_id"],
            "provider": retry_call["provider"],
            "model": retry_call["model"],
            "source_session_id": retry_call["source_session_id"],
            "session_date": retry_call["session_date"],
            "attention_input_identity": checked["correction"]["frozen_attention_input_identity"],
            "original_attempt_result": "FAILED_PARSE",
            "retry_reason": "FINAL_CORRECTED_SINGLE_RETRY_AFTER_FAILURE_AUDIT",
            "maximum_retry_attempts_in_this_move": 1,
        },
    )
    journal_event(
        run_dir / "operation_journal.jsonl",
        "FINALIZATION_STARTED",
        imported_valid_result_count=len(imported_rows),
        authorized_call_id=AUTHORIZED_CALL_ID,
    )

    retry = execute_retry(
        run_dir=run_dir,
        retry_call=retry_call,
        contract=checked["runtime_contract"],
        dispatcher=dispatcher or batch.live_dispatch,
    )

    if retry["terminal_state"] == "SUCCEEDED_VALID":
        normalized_row = retry["normalized"]
        final_results.append(
            {
                "call_id": retry_call["call_id"],
                "provider": retry_call["provider"],
                "model": retry_call["model"],
                "source_session_id": retry_call["source_session_id"],
                "session_date": retry_call["session_date"],
                "episode_ids": list(retry_call["episode_ids"]),
                "attention_result": reconstruct_attention_payload(normalized_row, retry_call["source_session_id"], retry_call["provider"]),
                "result_source": "FINAL_CORRECTED_RETRY",
                "source_live_run_identity": "PPHB-R1-ATTENTION-EXECUTION-BATCH-001-20260729T013947Z-2cce371f8a13",
                "source_repair_run_identity": FAILURE_AUDIT_ID,
            }
        )
        for episode_id in retry_call["episode_ids"]:
            episode_map.append(
                {
                    "call_id": retry_call["call_id"],
                    "episode_id": episode_id,
                    "source_session_id": retry_call["source_session_id"],
                    "provider": retry_call["provider"],
                    "model": retry_call["model"],
                    "result_source": "FINAL_CORRECTED_RETRY",
                }
            )
        remaining_failed: list[dict[str, Any]] = []
        finalization_status = "ATTENTION_BATCH_001_FINALIZED"
        retry_decision = "FINAL_CORRECTED_RETRY_SUCCEEDED_VALID"
        contract_decision = "ALL_BATCH_001_RESULTS_VALID"
        scaling_decision = "READY_FOR_ATTENTION_BATCH_002"
    else:
        remaining_failed = [
            {
                "call_id": retry_call["call_id"],
                "provider": retry_call["provider"],
                "model": retry_call["model"],
                "failure_stage": retry["terminal_state"],
                "exact_remaining_reason": (retry["failed"] or {}).get("exact_error") or retry["validation"].get("error_code") or retry["terminal_state"],
                "retry_required": False,
            }
        ]
        finalization_status = "ATTENTION_BATCH_001_TERMINAL_PARTIAL"
        retry_decision = "FINAL_CORRECTED_RETRY_FAILED"
        contract_decision = "VALID_RESULTS_WITH_TERMINAL_FAILURE"
        scaling_decision = "BATCH_001_EXCEPTION_REQUIRES_GOVERNANCE_DECISION"

    write_jsonl(run_dir / "final_normalized_attention_results.jsonl", final_results)
    write_jsonl(run_dir / "final_episode_attention_result_map.jsonl", episode_map)
    write_jsonl(run_dir / "remaining_failed_calls.jsonl", remaining_failed)

    by_provider_model = Counter(f"{row['provider']}|{row['model']}" for row in final_results)
    sessions = sorted({row["source_session_id"] for row in final_results})
    episodes = sorted({row["episode_id"] for row in episode_map})
    reconciliation = {
        "planned_calls": EXPECTED_TOTAL_CALLS,
        "imported_valid_results": len(imported_rows),
        "new_provider_calls": 1,
        "successful_corrected_retries": 1 if retry["terminal_state"] == "SUCCEEDED_VALID" else 0,
        "remaining_failed_calls": len(remaining_failed),
        "final_validated_result_count": len(final_results),
        "duplicate_calls": 0,
        "unexpected_calls": 0,
        "sessions_represented": len(sessions),
        "episodes_mapped": len(episodes),
        "results_by_provider_model": dict(sorted(by_provider_model.items())),
    }
    write_json(run_dir / "batch_001_reconciliation.json", reconciliation)
    write_json(
        run_dir / "batch_001_summary.json",
        {
            **reconciliation,
            "authorized_call_id": AUTHORIZED_CALL_ID,
            "provider_stop_reason": retry["transport"].get("stop_reason"),
            "prompt_tokens": retry["transport"].get("prompt_tokens"),
            "completion_tokens": retry["transport"].get("completion_tokens"),
            "raw_provider_output_length": retry["transport"].get("response_length"),
            "retry_terminal_state": retry["terminal_state"],
            "working_tree_preflight": checked["working_tree"],
            "google_preflight": preflight,
        },
    )
    decision = {
        "finalization_status": finalization_status,
        "retry_decision": retry_decision,
        "contract_decision": contract_decision,
        "raw_preservation_decision": (
            "RAW_PROVIDER_OUTPUT_PRESERVED"
            if retry["raw"].get("raw_output_returned")
            else "RAW_PROVIDER_OUTPUT_NOT_RETURNED"
        ),
        "scaling_decision": scaling_decision,
    }
    write_json(run_dir / "batch_001_decision.json", decision)
    write_json(
        run_dir / "run_manifest.json",
        {
            **read_json(run_dir / "run_manifest.json"),
            "provider_calls_executed": 1,
        },
    )
    return {
        "run_dir": run_dir,
        "decision": decision,
        "reconciliation": reconciliation,
        "retry": retry,
        "imported_rows": imported_rows,
        "final_results": final_results,
        "remaining_failed": remaining_failed,
        "preflight": preflight,
        "retry_call": retry_call,
        "working_tree": checked["working_tree"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--fixed-timestamp")
    args = parser.parse_args(argv)
    result = finalize(output_root=args.output_root, fixed_timestamp=args.fixed_timestamp)
    print(json.dumps({"run_dir": str(result["run_dir"]), **result["decision"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
