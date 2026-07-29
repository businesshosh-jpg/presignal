#!/usr/bin/env python3
"""Retry the two incomplete Batch 003 Attention calls and close the batch if valid."""
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
from automation import execute_presignal_v21_attention_batch_001 as batch_base
from automation import execute_presignal_v21_attention_batch_003 as batch003
from automation import google_clients
from automation import presignal_v21_provider_adapters_v1 as provider_adapters
from automation import presignal_v21_minimal_prospective_lineage_v1 as lineage
from automation import run_presignal_v21_step8_r2_historical_replication_v1 as replay

PLAN_ID = "PPHB-R1-ATTENTION-EXECUTION-PLAN-20260729T010207Z-3fcd59f96f3c"
BATCH_003_EXEC_ID = "PPHB-R1-ATTENTION-EXECUTION-BATCH-003-20260729T045507Z-64f3c4f5fc50"
ROW_STATUS_AUDIT_ID = "PPHB-R1-ATTENTION-ROW-STATUS-AUDIT-BATCH-003-20260729T051700Z-e377782d7d25"
EXPECTED_START_HEAD = "504838433440346db24afbd390b0d8024a1fb713"
RETRY_CALL_IDS = [
    "ATN_c6e73d4b0bd438cdd970",
    "ATN_592af0718bf939d9ecb6",
]
EXPECTED_IMPORTED_COUNT = 10
EXPECTED_TOTAL_CALLS = 12
EXPECTED_PROVIDER = "OpenAI"
EXPECTED_MODEL = "gpt-4o-mini-2024-07-18"
TOKEN_PATH = Path("/Users/junhoshino/projects/presignal/local/token.json")

OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_execution"
PLAN_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_execution_plan" / PLAN_ID
EXEC_ROOT = OUTPUT_ROOT / BATCH_003_EXEC_ID
AUDIT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_contract_repair" / ROW_STATUS_AUDIT_ID


class Batch003CompletenessRetryError(RuntimeError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def is_descendant_of(commit: str) -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=ROOT).returncode == 0


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


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stripped_json_text(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return text


def preflight_google_auth() -> dict[str, Any]:
    os.environ["PRESIGNAL_GOOGLE_TOKEN_PATH"] = str(TOKEN_PATH)
    if not TOKEN_PATH.exists():
        raise Batch003CompletenessRetryError("GOOGLE_TOKEN_PATH_MISSING")
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
    stamp = fixed_timestamp or now_stamp()
    seed = {
        "plan_id": PLAN_ID,
        "batch_003_exec_id": BATCH_003_EXEC_ID,
        "row_status_audit_id": ROW_STATUS_AUDIT_ID,
        "retry_call_ids": RETRY_CALL_IDS,
        "timestamp": stamp,
    }
    run_id = "PPHB-R1-ATTENTION-BATCH-003-COMPLETENESS-RETRY-" + stamp + "-" + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:12]
    return output_root / run_id


def verify_governing_artifacts(*, enforce_head: bool = True) -> dict[str, Any]:
    if enforce_head and git_head() != EXPECTED_START_HEAD:
        raise Batch003CompletenessRetryError("UNEXPECTED_START_HEAD")
    if enforce_head and not is_descendant_of(EXPECTED_START_HEAD):
        raise Batch003CompletenessRetryError("AUTHORIZED_START_HEAD_NOT_ANCESTOR")
    for root in (PLAN_ROOT, EXEC_ROOT, AUDIT_ROOT):
        if not root.exists():
            raise Batch003CompletenessRetryError("GOVERNING_ARTIFACT_MISSING:" + root.name)
    batch_base.verify_plan_fingerprints()

    valid_rows = read_jsonl(EXEC_ROOT / "normalized_attention_results.jsonl")
    if len(valid_rows) != EXPECTED_IMPORTED_COUNT:
        raise Batch003CompletenessRetryError("IMPORTED_VALID_RESULT_COUNT_MISMATCH")
    valid_call_ids = {row["call_id"] for row in valid_rows}
    if len(valid_call_ids) != EXPECTED_IMPORTED_COUNT:
        raise Batch003CompletenessRetryError("IMPORTED_CALL_IDS_NOT_UNIQUE")
    if any(call_id in valid_call_ids for call_id in RETRY_CALL_IDS):
        raise Batch003CompletenessRetryError("RETRY_CALL_ALREADY_VALID")

    audit_remaining = read_jsonl(AUDIT_ROOT / "remaining_failed_calls.jsonl")
    if sorted(row["call_id"] for row in audit_remaining) != sorted(RETRY_CALL_IDS):
        raise Batch003CompletenessRetryError("REMAINING_FAILURE_LEDGER_MISMATCH")

    failed_inventory = {row["call_id"]: row for row in read_jsonl(AUDIT_ROOT / "failed_row_status_inventory.jsonl")}
    if sorted(failed_inventory) != sorted(RETRY_CALL_IDS):
        raise Batch003CompletenessRetryError("FAILED_ROW_STATUS_INVENTORY_MISMATCH")

    calls = {row["call_id"]: row for row in batch003.load_batch_calls()}
    source_sessions, source_members = batch_base.read_source_sessions()
    retries: list[dict[str, Any]] = []
    for call_id in RETRY_CALL_IDS:
        call = calls.get(call_id)
        if call is None:
            raise Batch003CompletenessRetryError("RETRY_CALL_NOT_IN_FROZEN_BATCH:" + call_id)
        if call["provider"] != EXPECTED_PROVIDER or call["model"] != EXPECTED_MODEL:
            raise Batch003CompletenessRetryError("RETRY_PROVIDER_MODEL_DRIFT:" + call_id)
        session = source_sessions.get(call["source_session_id"])
        members = source_members.get(call["source_session_id"])
        if session is None or not members:
            raise Batch003CompletenessRetryError("RETRY_SOURCE_SESSION_MISSING:" + call["source_session_id"])
        expected_event_ids = [row["event_id"] for row in members]
        prior_omitted = [row["event_id"] for row in failed_inventory[call_id]["row_identities_containing_them"]]
        if not all(event_id in expected_event_ids for event_id in prior_omitted):
            raise Batch003CompletenessRetryError("OMITTED_EVENT_NOT_IN_EXPECTED_SET:" + call_id)
        retries.append(
            {
                "call": call,
                "session": session,
                "members": members,
                "expected_event_ids": expected_event_ids,
                "prior_omitted_event_ids": prior_omitted,
            }
        )

    return {
        "runtime_contract": batch_base.load_runtime_contract(),
        "valid_rows": valid_rows,
        "valid_call_ids": valid_call_ids,
        "retries": retries,
        "working_tree": git_status_lines(),
        "fingerprints": {
            "plan_contract_sha256": file_sha256(PLAN_ROOT / "attention_execution_contract.json"),
            "batch_003_valid_results_sha256": file_sha256(EXEC_ROOT / "normalized_attention_results.jsonl"),
            "row_status_audit_sha256": file_sha256(AUDIT_ROOT / "audit_decision.json"),
            "row_status_inventory_sha256": file_sha256(AUDIT_ROOT / "failed_row_status_inventory.jsonl"),
        },
    }


def build_completeness_instruction(base_instruction: str, expected_event_ids: list[str]) -> str:
    return (
        base_instruction
        + "\n\n"
        + "Return exactly one Attention row for every expected event ID supplied in this call.\n"
        + "Do not omit an event.\n"
        + "If the provider does not select or prioritize an event, still return its row using the canonical non-selected representation required by session_attention_map.\n"
        + "Before finishing, verify:\n"
        + "returned event-ID set = expected event-ID set\n"
        + "missing event IDs = none\n"
        + "unexpected event IDs = none\n"
        + "duplicate event IDs = none\n"
        + "Expected event IDs (exact): " + ", ".join(expected_event_ids)
    )


def import_valid_results(run_dir: Path, rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    imported_rows: list[dict[str, Any]] = []
    final_results: list[dict[str, Any]] = []
    episode_map: list[dict[str, Any]] = []
    manifest_rows = {row["call_id"]: row for row in read_jsonl(EXEC_ROOT / "batch_call_manifest.jsonl")}
    for row in rows:
        manifest = manifest_rows[row["call_id"]]
        imported_rows.append(
            {
                "call_id": row["call_id"],
                "source_live_run_identity": BATCH_003_EXEC_ID,
                "provider": row["provider"],
                "model": row["model"],
                "source_session_id": row["source_session_id"],
                "raw_response_reference": path_ref(EXEC_ROOT / "raw_provider_outputs.jsonl"),
                "validation_result": "SUCCEEDED_VALID",
                "import_status": "IMPORTED_VALIDATED_RESULT",
                "provider_recall_performed": False,
            }
        )
        final_results.append(
            {
                "call_id": row["call_id"],
                "provider": row["provider"],
                "model": row["model"],
                "source_session_id": row["source_session_id"],
                "session_date": manifest["session_date"],
                "episode_ids": list(manifest["episode_ids"]),
                "attention_result": reconstruct_attention_payload(row),
                "result_source": "IMPORTED_BATCH_003_VALIDATED_RESULT",
                "source_live_run_identity": BATCH_003_EXEC_ID,
            }
        )
        for episode_id in manifest["episode_ids"]:
            episode_map.append(
                {
                    "call_id": row["call_id"],
                    "episode_id": episode_id,
                    "source_session_id": row["source_session_id"],
                    "provider": row["provider"],
                    "model": row["model"],
                    "result_source": "IMPORTED_BATCH_003_VALIDATED_RESULT",
                }
            )
    write_jsonl(run_dir / "imported_valid_result_ledger.jsonl", imported_rows)
    return imported_rows, final_results, episode_map


def reconstruct_attention_payload(normalized_row: Mapping[str, Any]) -> dict[str, Any]:
    rows = list(normalized_row["validated_attention_rows"])
    return {
        "object": "session_attention_map",
        "session_id": normalized_row["source_session_id"],
        "provider": normalized_row["provider"],
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
        "session_attention_summary": "Recovered from strict validated Batch 003 result.",
        "status": "ok",
    }


def build_request_fingerprint(
    *,
    call: Mapping[str, Any],
    session: Mapping[str, Any],
    members: list[Mapping[str, Any]],
    contract: Mapping[str, Any],
    instruction_override: str,
) -> str:
    dry_run = lineage.build_prospective_attention(
        study_id="HISTORICAL_R3",
        collection_run_id="BATCH_003_COMPLETENESS_RETRY",
        session_snapshot=replay._session_snapshot(session),
        member_rows=members,
        provider=call["provider"],
        model=call["model"],
        information_cutoff_ts=session["forecast_cutoff"],
        attention_run_id="PLAN_" + call["call_id"],
        stage_generated_ts=session["forecast_cutoff"],
        dispatcher=None,
        instruction_override=instruction_override,
        generation_settings=binding.generation_settings(contract, call["provider"], "ATTENTION"),
    )
    return dry_run["metadata"]["request_fingerprint"]


def determine_event_completeness(
    *,
    raw_output: Any,
    call: Mapping[str, Any],
    contract: Mapping[str, Any],
    expected_event_ids: list[str],
    transport: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    adapted = provider_adapters.normalize_provider_response(
        stage="ATTENTION",
        requested_provider=call["provider"],
        requested_model=call["model"],
        transport_result={
            "raw_output": raw_output,
            "actual_provider": transport.get("actual_provider"),
            "actual_model": transport.get("actual_model"),
        },
        contract_version=contract["contract_version"],
        authoritative_attention_provider_binding=True,
    )
    if adapted["parse_status"] != provider_adapters.ParseStatus.PARSED:
        return (
            {
                "call_id": call["call_id"],
                "expected_event_ids": list(expected_event_ids),
                "returned_event_ids": [],
                "missing_event_ids": list(expected_event_ids),
                "unexpected_event_ids": [],
                "duplicate_event_ids": [],
                "completeness_decision": "NOT_REACHED",
                "parse_failure_reason": adapted["normalization_notes"][-1]["reason"] if adapted["normalization_notes"] else "PARSE_FAILED",
            },
            None,
        )
    payload = adapted["canonical_payload"]
    returned_event_ids = [str(item.get("event_id")) for item in payload.get("attention_items", []) if isinstance(item, Mapping)]
    counts = Counter(returned_event_ids)
    duplicate_event_ids = sorted([event_id for event_id, count in counts.items() if count > 1])
    expected_set = set(expected_event_ids)
    returned_set = set(returned_event_ids)
    missing_event_ids = [event_id for event_id in expected_event_ids if event_id not in returned_set]
    unexpected_event_ids = sorted([event_id for event_id in returned_set if event_id not in expected_set])
    decision = "PASSED" if not missing_event_ids and not unexpected_event_ids and not duplicate_event_ids else "FAILED"
    return (
        {
            "call_id": call["call_id"],
            "expected_event_ids": list(expected_event_ids),
            "returned_event_ids": returned_event_ids,
            "missing_event_ids": missing_event_ids,
            "unexpected_event_ids": unexpected_event_ids,
            "duplicate_event_ids": duplicate_event_ids,
            "completeness_decision": decision,
        },
        payload,
    )


def execute_retry(
    *,
    run_dir: Path,
    retry: Mapping[str, Any],
    contract: Mapping[str, Any],
    dispatcher: Callable[[Mapping[str, Any]], Mapping[str, Any]],
) -> dict[str, Any]:
    call = retry["call"]
    session = retry["session"]
    members = retry["members"]
    expected_event_ids = list(retry["expected_event_ids"])
    prior_omitted_event_ids = list(retry["prior_omitted_event_ids"])
    base_instruction = binding.attention_instruction(contract, call["provider"])
    instruction_override = build_completeness_instruction(base_instruction, expected_event_ids)
    request_fingerprint = build_request_fingerprint(
        call=call,
        session=session,
        members=members,
        contract=contract,
        instruction_override=instruction_override,
    )
    journal_event(
        run_dir / "operation_journal.jsonl",
        "COMPLETENESS_RETRY_STARTED",
        call_id=call["call_id"],
        attempt_number=2,
        retry_reason="REQUIRED_EVENT_ROWS_OMITTED",
        expected_event_ids=expected_event_ids,
        prior_omitted_event_ids=prior_omitted_event_ids,
        provider=call["provider"],
        model=call["model"],
        source_session_id=call["source_session_id"],
        attention_input_fingerprint=request_fingerprint,
        state="COMPLETENESS_RETRY_STARTED",
    )
    transport_holder: dict[str, Any] = {}

    def wrapped_dispatch(payload: Mapping[str, Any]) -> Mapping[str, Any]:
        transport_holder["request"] = dict(payload)
        response = dict(dispatcher(payload))
        transport_holder["response"] = response
        return response

    result = None
    final_state = "FAILED_TRANSPORT"
    error_code = ""
    error_summary = ""
    validation_details: dict[str, Any] = {}
    completeness = {
        "call_id": call["call_id"],
        "expected_event_ids": expected_event_ids,
        "returned_event_ids": [],
        "missing_event_ids": expected_event_ids,
        "unexpected_event_ids": [],
        "duplicate_event_ids": [],
        "completeness_decision": "NOT_REACHED",
    }
    try:
        result = lineage.build_prospective_attention(
            study_id="HISTORICAL_R3",
            collection_run_id=run_dir.name,
            session_snapshot=replay._session_snapshot(session),
            member_rows=members,
            provider=call["provider"],
            model=call["model"],
            information_cutoff_ts=session["forecast_cutoff"],
            attention_run_id="RETRY_" + call["call_id"],
            stage_generated_ts=session["forecast_cutoff"],
            dispatcher=wrapped_dispatch,
            raw_parser=lambda raw: binding.attention_parser(
                call["provider"],
                raw,
                contract,
                actual_provider=(transport_holder.get("response") or {}).get("actual_provider"),
                actual_model=(transport_holder.get("response") or {}).get("actual_model"),
                requested_model=call["model"],
                authoritative_provider_binding=True,
            ),
            instruction_override=instruction_override,
            generation_settings=binding.generation_settings(contract, call["provider"], "ATTENTION"),
        )
    except Exception as exc:
        final_state, error_code = batch_base.classify_transport_exception(exc)
        error_summary = str(exc)

    transport = transport_holder.get("response")
    request_payload = transport_holder.get("request") or {}
    raw_preserved = None
    raw_claimed_provider = None
    authority_row = None
    if transport is not None:
        raw_preserved = transport.get("raw_output_original", transport.get("raw_output"))
        raw_claimed_provider = provider_adapters.extract_raw_provider_claim(raw_preserved)
        raw_length = len(raw_preserved) if isinstance(raw_preserved, str) else None
        append_jsonl(
            run_dir / "raw_transport_results.jsonl",
            {
                "call_id": call["call_id"],
                "provider": call["provider"],
                "model": call["model"],
                "source_session_id": call["source_session_id"],
                "transport_status": transport.get("status"),
                "actual_provider": transport.get("actual_provider"),
                "actual_model": transport.get("actual_model"),
                "completed_timestamp": transport.get("completed_timestamp"),
                "prompt_tokens": transport.get("prompt_tokens"),
                "completion_tokens": transport.get("completion_tokens"),
                "latency_ms": transport.get("latency_ms"),
                "stop_reason": transport.get("stop_reason"),
                "usage_metadata": transport.get("usage_metadata"),
                "configured_max_output_tokens": transport.get("configured_max_output_tokens", request_payload.get("max_output_tokens")),
                "preserve_raw_before_parse": bool(request_payload.get("preserve_raw_before_parse") is True),
                "response_length": raw_length,
                "response_fingerprint": sha256_text(transport),
            },
        )
        append_jsonl(
            run_dir / "raw_provider_outputs.jsonl",
            {
                "call_id": call["call_id"],
                "provider": call["provider"],
                "model": call["model"],
                "source_session_id": call["source_session_id"],
                "raw_output": raw_preserved,
                "raw_output_fingerprint": sha256_text(raw_preserved),
                "raw_output_returned": bool(raw_preserved not in (None, "")),
            },
        )
        authority_row = {
            "call_id": call["call_id"],
            "manifest_provider": call["provider"],
            "manifest_model": call["model"],
            "transport_provider": transport.get("actual_provider"),
            "transport_model": transport.get("actual_model"),
            "raw_claimed_provider": raw_claimed_provider,
            "authority_agreement": (
                transport.get("actual_provider") == call["provider"]
                and transport.get("actual_model") == call["model"]
            ),
            "canonical_provider": call["provider"] if (
                transport.get("actual_provider") == call["provider"]
                and transport.get("actual_model") == call["model"]
            ) else None,
            "authority_decision": (
                "MANIFEST_TRANSPORT_MATCH"
                if transport.get("actual_provider") == call["provider"] and transport.get("actual_model") == call["model"]
                else "MANIFEST_TRANSPORT_CONFLICT"
            ),
        }
        append_jsonl(run_dir / "provider_authority_results.jsonl", authority_row)
        journal_event(run_dir / "operation_journal.jsonl", "TRANSPORT_COMPLETED", call_id=call["call_id"], transport_status=transport.get("status"))
        completeness, _ = determine_event_completeness(
            raw_output=raw_preserved,
            call=call,
            contract=contract,
            expected_event_ids=expected_event_ids,
            transport=transport,
        )
        append_jsonl(run_dir / "event_completeness_results.jsonl", completeness)

    normalized_row = None
    if result is not None:
        journal_event(run_dir / "operation_journal.jsonl", "NORMALIZATION_COMPLETED", call_id=call["call_id"], parse_status=result.get("status"))
        if result.get("status") == "provider_contract_error":
            transport_status = str((transport or {}).get("status") or "")
            if transport_status in batch_base.PROVIDER_FAILURE_STATUSES:
                final_state = "FAILED_PROVIDER"
                error_code = transport_status or "PROVIDER_CONTRACT_ERROR"
            elif str(((result.get("rows") or [{}])[0]).get("error_message") or "").startswith("ATTENTION_PROVIDER_AUTHORITY_"):
                final_state = "FAILED_PROVIDER_AUTHORITY"
                error_code = str(((result.get("rows") or [{}])[0]).get("error_message") or result.get("status"))
            else:
                final_state = "FAILED_PARSE"
                error_code = str(((result.get("rows") or [{}])[0]).get("error_message") or result.get("status"))
            error_summary = error_code
        elif completeness["completeness_decision"] != "PASSED":
            final_state = "FAILED_COMPLETENESS"
            error_code = "ATTENTION_EVENT_COMPLETENESS_FAILED"
            error_summary = error_code
            validation_details = {
                "missing_event_ids": completeness["missing_event_ids"],
                "unexpected_event_ids": completeness["unexpected_event_ids"],
                "duplicate_event_ids": completeness["duplicate_event_ids"],
            }
        else:
            valid, validation_error, validation_details = batch_base.validate_attention_result(
                result=result,
                expected_session_id=call["source_session_id"],
                expected_provider=call["provider"],
                expected_model=call["model"],
                member_ids=expected_event_ids,
                contract=contract,
            )
            if valid:
                final_state = "SUCCEEDED_VALID"
                normalized_row = {
                    "call_id": call["call_id"],
                    "source_session_id": call["source_session_id"],
                    "provider": call["provider"],
                    "model": call["model"],
                    "attention_run_id": (result.get("metadata") or {}).get("attention_run_id"),
                    "request_fingerprint": (result.get("metadata") or {}).get("request_fingerprint"),
                    "validated_attention_rows": list(result.get("rows") or []),
                    "result_fingerprint": sha256_text(result),
                }
                append_jsonl(run_dir / "retry_normalized_attention_results.jsonl", normalized_row)
            else:
                final_state = "FAILED_VALIDATION"
                error_code = validation_error or "VALIDATION_FAILED"
                error_summary = error_code
        journal_event(run_dir / "operation_journal.jsonl", "VALIDATION_COMPLETED", call_id=call["call_id"], final_state=final_state)

    validation_row = {
        "call_id": call["call_id"],
        "provider": call["provider"],
        "model": call["model"],
        "source_session_id": call["source_session_id"],
        "attention_input_fingerprint": request_fingerprint,
        "final_state": final_state,
        "error_code": error_code or None,
        "error_summary": error_summary or None,
        "validation_details": validation_details,
    }
    append_jsonl(run_dir / "attention_validation_results.jsonl", validation_row)
    append_jsonl(
        run_dir / "attention_parse_results.jsonl",
        {
            "call_id": call["call_id"],
            "provider": call["provider"],
            "model": call["model"],
            "source_session_id": call["source_session_id"],
            "parse_result": "PARSED_VALID" if result is not None and result.get("status") != "provider_contract_error" else "FAILED_PARSE",
            "final_state": final_state,
            "raw_claimed_provider": raw_claimed_provider,
        },
    )
    if final_state != "SUCCEEDED_VALID":
        append_jsonl(
            run_dir / "remaining_failed_calls.jsonl",
            {
                "call_id": call["call_id"],
                "provider": call["provider"],
                "model": call["model"],
                "source_session_id": call["source_session_id"],
                "failure_stage": final_state,
                "exact_remaining_reason": error_code or error_summary,
                "retry_recommendation": "NO_AUTOMATIC_ADDITIONAL_RETRY",
            },
        )
        journal_event(run_dir / "operation_journal.jsonl", "CALL_FAILED", call_id=call["call_id"], provider=call["provider"], model=call["model"], final_state=final_state)
    else:
        journal_event(run_dir / "operation_journal.jsonl", "CALL_SUCCEEDED", call_id=call["call_id"], provider=call["provider"], model=call["model"])
    return {
        "call": call,
        "terminal_state": final_state,
        "completeness": completeness,
        "normalized_row": normalized_row,
        "authority_row": authority_row,
        "validation_row": validation_row,
    }


def finalize(
    *,
    output_root: Path = OUTPUT_ROOT,
    fixed_timestamp: str | None = None,
    dispatcher: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    preflight_override: Callable[[], dict[str, Any]] | None = None,
    enforce_head: bool = True,
) -> dict[str, Any]:
    checked = verify_governing_artifacts(enforce_head=enforce_head)
    preflight = (preflight_override or preflight_google_auth)()
    run_dir = materialize_run(output_root, fixed_timestamp=fixed_timestamp)
    run_dir.mkdir(parents=True, exist_ok=False)
    contract = checked["runtime_contract"]
    imported_rows, final_results, episode_map = import_valid_results(run_dir, checked["valid_rows"])

    write_json(
        run_dir / "run_manifest.json",
        {
            "run_id": run_dir.name,
            "generated_at": now_iso(),
            "git_head": git_head(),
            "governing_plan_identity": PLAN_ID,
            "governing_batch_003_execution_identity": BATCH_003_EXEC_ID,
            "governing_row_status_audit_identity": ROW_STATUS_AUDIT_ID,
            "authorized_provider_calls": 2,
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
            "batch_003_execution_identity": BATCH_003_EXEC_ID,
            "batch_003_execution_root": path_ref(EXEC_ROOT),
            "row_status_audit_identity": ROW_STATUS_AUDIT_ID,
            "row_status_audit_root": path_ref(AUDIT_ROOT),
            "fingerprints": checked["fingerprints"],
            "google_preflight": preflight,
        },
    )
    write_json(
        run_dir / "completeness_retry_contract.json",
        {
            "governing_plan_identity": PLAN_ID,
            "governing_batch_003_execution_identity": BATCH_003_EXEC_ID,
            "governing_row_status_audit_identity": ROW_STATUS_AUDIT_ID,
            "expected_imported_valid_result_count": EXPECTED_IMPORTED_COUNT,
            "authorized_retry_call_count": 2,
            "authorized_retry_call_ids": RETRY_CALL_IDS,
            "allowed_provider": EXPECTED_PROVIDER,
            "allowed_model": EXPECTED_MODEL,
            "canonical_attention_contract_identity": "session_attention_map",
            "bounded_correction": "explicit required full expected event-ID set plus exact completeness check before canonical validation",
            "no_repeat_rule": "ten validated calls are imported only and never redispatched",
            "failure_behavior": "one retry attempt per failed call only; fail closed on completeness, parse, validation, or provider-authority error",
            "immutability_requirements": "all governing runs remain append-only and unchanged",
        },
    )
    write_jsonl(
        run_dir / "authorized_retry_manifest.jsonl",
        [
            {
                "call_id": retry["call"]["call_id"],
                "provider": retry["call"]["provider"],
                "model": retry["call"]["model"],
                "source_session_id": retry["call"]["source_session_id"],
                "attention_input_identity": {
                    "input_cutoff": retry["session"]["forecast_cutoff"],
                    "expected_event_ids": retry["expected_event_ids"],
                    "member_count": len(retry["members"]),
                },
                "prior_omitted_event_ids": retry["prior_omitted_event_ids"],
                "original_attempt_result": "FAILED_VALIDATION",
                "retry_reason": "REQUIRED_EVENT_ROWS_OMITTED",
                "maximum_retry_attempts_in_this_move": 1,
            }
            for retry in checked["retries"]
        ],
    )
    for name in (
        "operation_journal.jsonl",
        "raw_transport_results.jsonl",
        "raw_provider_outputs.jsonl",
        "provider_authority_results.jsonl",
        "event_completeness_results.jsonl",
        "attention_parse_results.jsonl",
        "attention_validation_results.jsonl",
        "retry_normalized_attention_results.jsonl",
        "remaining_failed_calls.jsonl",
    ):
        (run_dir / name).write_text("")
    journal_event(
        run_dir / "operation_journal.jsonl",
        "FINALIZATION_STARTED",
        imported_valid_result_count=len(imported_rows),
        authorized_retry_call_ids=RETRY_CALL_IDS,
    )

    retry_results = []
    actual_dispatcher = dispatcher or batch_base.live_dispatch
    for retry in checked["retries"]:
        retry_results.append(execute_retry(run_dir=run_dir, retry=retry, contract=contract, dispatcher=actual_dispatcher))

    successful_retries = [row for row in retry_results if row["terminal_state"] == "SUCCEEDED_VALID"]
    for retry_result in successful_retries:
        call = retry_result["call"]
        normalized = retry_result["normalized_row"]
        assert normalized is not None
        final_results.append(
            {
                "call_id": call["call_id"],
                "provider": call["provider"],
                "model": call["model"],
                "source_session_id": call["source_session_id"],
                "session_date": call["session_date"],
                "episode_ids": list(call["episode_ids"]),
                "attention_result": reconstruct_attention_payload(normalized),
                "result_source": "BATCH_003_COMPLETENESS_RETRY",
                "source_live_run_identity": BATCH_003_EXEC_ID,
            }
        )
        for episode_id in call["episode_ids"]:
            episode_map.append(
                {
                    "call_id": call["call_id"],
                    "episode_id": episode_id,
                    "source_session_id": call["source_session_id"],
                    "provider": call["provider"],
                    "model": call["model"],
                    "result_source": "BATCH_003_COMPLETENESS_RETRY",
                }
            )

    write_jsonl(run_dir / "final_normalized_attention_results.jsonl", final_results)
    write_jsonl(run_dir / "final_episode_attention_result_map.jsonl", episode_map)
    remaining_failed = read_jsonl(run_dir / "remaining_failed_calls.jsonl")

    final_validated = len(final_results)
    successful_retry_count = len(successful_retries)
    failed_retry_count = len(retry_results) - successful_retry_count
    if successful_retry_count == 2:
        execution_status = "ATTENTION_BATCH_003_CLOSED"
        retry_decision = "BOTH_COMPLETENESS_RETRIES_SUCCEEDED_VALID"
        completeness_decision = "ALL_EXPECTED_EVENT_ROWS_RETURNED"
        contract_decision = "ALL_BATCH_003_RESULTS_VALID"
        scaling_decision = "READY_FOR_ATTENTION_BATCH_004"
    elif successful_retry_count == 1:
        execution_status = "ATTENTION_BATCH_003_REMAINS_PARTIALLY_COMPLETE"
        retry_decision = "ONE_COMPLETENESS_RETRY_FAILED"
        completeness_decision = "EVENT_OMISSIONS_REMAIN"
        contract_decision = "VALID_RESULTS_WITH_REMAINING_FAILURE"
        scaling_decision = "BATCH_003_EXCEPTION_REQUIRES_GOVERNANCE_DECISION"
    elif failed_retry_count == 2:
        execution_status = "ATTENTION_BATCH_003_REMAINS_PARTIALLY_COMPLETE"
        retry_decision = "BOTH_COMPLETENESS_RETRIES_FAILED"
        completeness_decision = "EVENT_OMISSIONS_REMAIN"
        contract_decision = "VALID_RESULTS_WITH_REMAINING_FAILURE"
        scaling_decision = "BATCH_003_EXCEPTION_REQUIRES_GOVERNANCE_DECISION"
    else:
        execution_status = "ATTENTION_BATCH_003_RETRY_BLOCKED"
        retry_decision = "COMPLETENESS_RETRIES_NOT_ATTEMPTED"
        completeness_decision = "COMPLETENESS_NOT_REACHED"
        contract_decision = "LIVE_ATTENTION_CONTRACT_FAILURE"
        scaling_decision = "REPAIR_BEFORE_BATCH_004"

    write_json(
        run_dir / "batch_003_reconciliation.json",
        {
            "planned_calls": EXPECTED_TOTAL_CALLS,
            "imported_valid_results": len(imported_rows),
            "authorized_retry_call_count": len(RETRY_CALL_IDS),
            "attempted_retry_call_count": len(retry_results),
            "successful_valid_retry_count": successful_retry_count,
            "failed_retry_count": failed_retry_count,
            "final_validated_result_count": final_validated,
            "remaining_failed_count": len(remaining_failed),
            "duplicate_call_count": 0,
            "unexpected_call_count": 0,
            "new_provider_call_count": len(retry_results),
            "results_by_provider_model": {f"{EXPECTED_PROVIDER}|{EXPECTED_MODEL}": len(retry_results)},
        },
    )
    write_json(
        run_dir / "batch_003_summary.json",
        {
            "execution_status": execution_status,
            "retry_decision": retry_decision,
            "completeness_decision": completeness_decision,
            "contract_decision": contract_decision,
            "scaling_decision": scaling_decision,
            "sessions_represented": len({row["source_session_id"] for row in final_results}),
            "episodes_mapped": len({row["episode_id"] for row in episode_map}),
            "results_by_provider_model": dict(sorted(Counter(f"{row['provider']}|{row['model']}" for row in final_results).items())),
        },
    )
    decision = {
        "execution_status": execution_status,
        "retry_decision": retry_decision,
        "completeness_decision": completeness_decision,
        "contract_decision": contract_decision,
        "scaling_decision": scaling_decision,
    }
    write_json(run_dir / "batch_003_decision.json", decision)
    write_json(
        run_dir / "run_manifest.json",
        {
            **read_json(run_dir / "run_manifest.json"),
            "provider_calls_executed": len(retry_results),
        },
    )
    return {
        "run_dir": run_dir,
        "decision": decision,
        "imported_rows": imported_rows,
        "retry_results": retry_results,
        "final_results": final_results,
        "remaining_failed": remaining_failed,
        "episode_map": episode_map,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--fixed-timestamp")
    args = parser.parse_args(argv)
    result = finalize(output_root=args.output_root, fixed_timestamp=args.fixed_timestamp)
    print(
        json.dumps(
            {
                "run_dir": path_ref(result["run_dir"]),
                "execution_status": result["decision"]["execution_status"],
                "successful_valid_retry_count": sum(1 for row in result["retry_results"] if row["terminal_state"] == "SUCCEEDED_VALID"),
                "remaining_failed_count": len(result["remaining_failed"]),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
