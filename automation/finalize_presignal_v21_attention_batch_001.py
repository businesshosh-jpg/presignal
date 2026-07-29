#!/usr/bin/env python3
"""Finalize Batch 001 from repaired preserved results plus one authorized retry."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import execute_presignal_v21_attention_batch_001 as batch
from automation import google_clients

PLAN_ID = "PPHB-R1-ATTENTION-EXECUTION-PLAN-20260729T010207Z-3fcd59f96f3c"
LIVE_RUN_ID = "PPHB-R1-ATTENTION-EXECUTION-BATCH-001-20260729T013947Z-2cce371f8a13"
REPAIR_RUN_ID = "PPHB-R1-ATTENTION-CONTRACT-REPAIR-BATCH-001-20260729T020108Z-17657dcc7cd5"
PLAN_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_execution_plan" / PLAN_ID
LIVE_RUN_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_execution" / LIVE_RUN_ID
REPAIR_RUN_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_contract_repair" / REPAIR_RUN_ID
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_execution"
AUTHORIZED_RETRY_CALL_ID = "ATN_d7c95516e95938578834"
TOKEN_PATH = Path("/Users/junhoshino/projects/presignal/local/token.json")
EXPECTED_RECOVERED_COUNT = 11
EXPECTED_TOTAL_CALLS = 12
EXPECTED_PROVIDER_MODELS = {
    "Anthropic": "claude-haiku-4-5",
    "Gemini": "gemini-2.5-flash-lite",
    "OpenAI": "gpt-4o-mini-2024-07-18",
}


class Batch001FinalizationError(RuntimeError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


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


def verify_preconditions() -> dict[str, Any]:
    if batch.git_head() != "e9ddf7cb8d2f2c3cfeba1054174dff746d602642":
        raise Batch001FinalizationError("UNEXPECTED_START_HEAD")
    if not PLAN_ROOT.exists() or not LIVE_RUN_ROOT.exists() or not REPAIR_RUN_ROOT.exists():
        raise Batch001FinalizationError("GOVERNING_ARTIFACT_MISSING")
    recovered = read_jsonl(REPAIR_RUN_ROOT / "recovered_attention_results.jsonl")
    remaining = read_jsonl(REPAIR_RUN_ROOT / "remaining_failed_calls.jsonl")
    if len(recovered) != EXPECTED_RECOVERED_COUNT:
        raise Batch001FinalizationError("RECOVERED_RESULT_COUNT_MISMATCH")
    recovered_ids = [row["call_id"] for row in recovered]
    if len(set(recovered_ids)) != EXPECTED_RECOVERED_COUNT:
        raise Batch001FinalizationError("RECOVERED_RESULT_IDS_NOT_UNIQUE")
    if len(remaining) != 1 or remaining[0]["call_id"] != AUTHORIZED_RETRY_CALL_ID:
        raise Batch001FinalizationError("AUTHORIZED_RETRY_LEDGER_MISMATCH")
    if any(row["call_id"] == AUTHORIZED_RETRY_CALL_ID for row in recovered):
        raise Batch001FinalizationError("AUTHORIZED_RETRY_ALREADY_RECOVERED")
    valid_rows = read_jsonl(LIVE_RUN_ROOT / "attention_validation_results.jsonl")
    if any(row["call_id"] == AUTHORIZED_RETRY_CALL_ID and row["final_state"] == "SUCCEEDED_VALID" for row in valid_rows):
        raise Batch001FinalizationError("AUTHORIZED_RETRY_ALREADY_VALID")
    calls = read_jsonl(LIVE_RUN_ROOT / "batch_call_manifest.jsonl")
    by_call = {row["call_id"]: row for row in calls}
    if AUTHORIZED_RETRY_CALL_ID not in by_call:
        raise Batch001FinalizationError("AUTHORIZED_RETRY_CALL_NOT_IN_FROZEN_MANIFEST")
    retry_call = by_call[AUTHORIZED_RETRY_CALL_ID]
    if retry_call["provider"] != "Anthropic" or retry_call["model"] != EXPECTED_PROVIDER_MODELS["Anthropic"]:
        raise Batch001FinalizationError("AUTHORIZED_RETRY_ASSIGNMENT_DRIFT")
    return {
        "recovered": recovered,
        "remaining": remaining,
        "calls": calls,
        "retry_call": retry_call,
    }


def preflight_google_auth() -> dict[str, Any]:
    os.environ["PRESIGNAL_GOOGLE_TOKEN_PATH"] = str(TOKEN_PATH)
    if not TOKEN_PATH.exists():
        raise Batch001FinalizationError("GOOGLE_TOKEN_PATH_MISSING")
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
    seed = {"plan": PLAN_ID, "live": LIVE_RUN_ID, "repair": REPAIR_RUN_ID, "timestamp": ts}
    run_id = "PPHB-R1-ATTENTION-BATCH-001-FINALIZATION-" + ts + "-" + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:12]
    return output_root / run_id


def import_recovered_rows(
    *,
    run_dir: Path,
    recovered_rows: list[dict[str, Any]],
    normalization_ledger: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    imported = []
    final_rows = []
    episode_map = []
    for row in recovered_rows:
        imported_row = {
            "call_id": row["call_id"],
            "source_live_run_identity": LIVE_RUN_ID,
            "source_repair_run_identity": REPAIR_RUN_ID,
            "provider": row["provider"],
            "model": row["model"],
            "source_session_id": row["source_session_id"],
            "raw_response_reference": path_ref(LIVE_RUN_ROOT / "raw_provider_outputs.jsonl"),
            "normalization_applied": normalization_ledger.get(row["call_id"], []),
            "validation_result": "PARSED_VALID",
            "import_status": "IMPORTED_RECOVERED_RESULT",
            "provider_recall_performed": False,
        }
        imported.append(imported_row)
        final_rows.append(
            {
                "call_id": row["call_id"],
                "provider": row["provider"],
                "model": row["model"],
                "source_session_id": row["source_session_id"],
                "session_date": row["session_date"],
                "episode_ids": list(row["episode_ids"]),
                "attention_result": row["attention_result"],
                "result_source": "RECOVERED_PRESERVED_RESPONSE",
                "source_live_run_identity": LIVE_RUN_ID,
                "source_repair_run_identity": REPAIR_RUN_ID,
            }
        )
        for episode_id in row["episode_ids"]:
            episode_map.append(
                {
                    "call_id": row["call_id"],
                    "episode_id": episode_id,
                    "source_session_id": row["source_session_id"],
                    "provider": row["provider"],
                    "model": row["model"],
                    "result_source": "RECOVERED_PRESERVED_RESPONSE",
                }
            )
    write_jsonl(run_dir / "recovered_result_import_ledger.jsonl", imported)
    return imported, final_rows, episode_map


def execute_retry_call(
    *,
    run_dir: Path,
    retry_call: Mapping[str, Any],
    contract: Mapping[str, Any],
    source_sessions: Mapping[str, Any],
    source_members: Mapping[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    journal_path = run_dir / "operation_journal.jsonl"
    validation_path = run_dir / "attention_validation_results.jsonl"
    normalized_path = run_dir / "normalized_attention_results.jsonl"
    raw_transport_path = run_dir / "raw_transport_results.jsonl"
    raw_output_path = run_dir / "raw_provider_outputs.jsonl"
    episode_map_path = run_dir / "episode_attention_result_map.jsonl"
    failed_path = run_dir / "failed_call_ledger.jsonl"
    for path in (
        validation_path,
        normalized_path,
        raw_transport_path,
        raw_output_path,
        episode_map_path,
        failed_path,
    ):
        if not path.exists():
            path.write_text("")
    session = source_sessions[retry_call["source_session_id"]]
    members = source_members[retry_call["source_session_id"]]
    retry_call = {
        **dict(retry_call),
        "attention_input_artifact": ((retry_call.get("attention_input_identity") or {}).get("attention_input_artifact")),
    }
    identity = batch.attention_input_identity(retry_call, session, members, contract)
    journal_event(
        journal_path,
        "RETRY_STARTED",
        call_id=retry_call["call_id"],
        attempt_number=2,
        predecessor_live_run=LIVE_RUN_ID,
        provider=retry_call["provider"],
        model=retry_call["model"],
        source_session_id=retry_call["source_session_id"],
        attention_input_fingerprint=identity["request_fingerprint"],
        state="RETRY_STARTED",
        retry_authorization="SINGLE_EMPTY_PROVIDER_OUTPUT_RETRY",
    )
    original_read = batch.read_terminal_results
    original_live_dispatch = batch.live_dispatch
    original_journal = batch.journal_event
    try:
        batch.read_terminal_results = lambda _path: {}
        batch.live_dispatch = batch.live_dispatch
        result = batch.execute_call(
            run_dir=run_dir,
            call=retry_call,
            session=session,
            members=members,
            contract=contract,
            dispatcher=batch.live_dispatch,
        )
    finally:
        batch.read_terminal_results = original_read
        batch.live_dispatch = original_live_dispatch
        batch.journal_event = original_journal
    retry_validation_rows = read_jsonl(validation_path)
    retry_normalized_rows = read_jsonl(normalized_path)
    retry_failed_rows = read_jsonl(failed_path)
    if len(retry_validation_rows) > 1 or len(retry_normalized_rows) > 1 or len(retry_failed_rows) > 1:
        raise Batch001FinalizationError("RETRY_OUTPUT_CARDINALITY_VIOLATION")
    transport_rows = read_jsonl(raw_transport_path)
    raw_output_rows = read_jsonl(raw_output_path)
    if len(transport_rows) > 1 or len(raw_output_rows) > 1:
        raise Batch001FinalizationError("RETRY_TRANSPORT_CARDINALITY_VIOLATION")
    write_json(run_dir / "retry_raw_transport_result.json", transport_rows[0] if transport_rows else {})
    write_json(run_dir / "retry_raw_provider_output.json", raw_output_rows[0] if raw_output_rows else {})
    write_json(run_dir / "retry_parse_result.json", retry_validation_rows[0] if retry_validation_rows else {})
    write_json(
        run_dir / "retry_validation_result.json",
        {
            "retry_terminal_state": result["final_state"],
            "normalized_result_count": len(retry_normalized_rows),
            "failed_result_count": len(retry_failed_rows),
        },
    )
    return {
        "final_state": result["final_state"],
        "normalized_rows": retry_normalized_rows,
        "failed_rows": retry_failed_rows,
        "transport_rows": transport_rows,
        "raw_output_rows": raw_output_rows,
    }


def finalize(
    *,
    output_root: Path = OUTPUT_ROOT,
    fixed_timestamp: str | None = None,
    dispatcher: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    preflight_override: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    checked = verify_preconditions()
    plan_contract = read_json(PLAN_ROOT / "attention_execution_contract.json")
    runtime_contract = batch.load_runtime_contract()
    batch.verify_plan_fingerprints()
    preflight = (preflight_override or preflight_google_auth)()
    source_sessions, source_members = batch.read_source_sessions()
    retry_call = checked["retry_call"]
    run_dir = materialize_run(output_root, fixed_timestamp=fixed_timestamp)
    run_dir.mkdir(parents=True, exist_ok=False)

    normalization_rows = read_jsonl(REPAIR_RUN_ROOT / "normalization_application_ledger.jsonl")
    normalization_by_call: dict[str, list[dict[str, Any]]] = {}
    for row in normalization_rows:
        normalization_by_call.setdefault(row["call_id"], []).append(row)

    write_json(
        run_dir / "run_manifest.json",
        {
            "run_id": run_dir.name,
            "generated_at": now_iso(),
            "git_head": batch.git_head(),
            "governing_plan_identity": PLAN_ID,
            "original_live_run_identity": LIVE_RUN_ID,
            "repair_run_identity": REPAIR_RUN_ID,
            "authorized_retry_call_id": AUTHORIZED_RETRY_CALL_ID,
            "authorized_retry_count": 1,
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
            "live_run_identity": LIVE_RUN_ID,
            "repair_run_identity": REPAIR_RUN_ID,
            "plan_root": path_ref(PLAN_ROOT),
            "live_run_root": path_ref(LIVE_RUN_ROOT),
            "repair_run_root": path_ref(REPAIR_RUN_ROOT),
        },
    )
    write_json(
        run_dir / "batch_finalization_contract.json",
        {
            "governing_plan_identity": PLAN_ID,
            "original_live_run_identity": LIVE_RUN_ID,
            "repair_run_identity": REPAIR_RUN_ID,
            "expected_recovered_import_count": 11,
            "authorized_retry_count": 1,
            "authorized_retry_call_id": AUTHORIZED_RETRY_CALL_ID,
            "canonical_attention_contract_identity": plan_contract["attention_output_contract"]["object"],
            "provider_alias_normalization_rule": "exact validated aliases only from automation/presignal_v21_provider_adapters_v1.py",
            "no_repeat_rule": "11 recovered calls are imported only and never re-dispatched",
            "failure_behavior": "single retry only; fail closed if invalid",
            "immutability_requirements": "all governing runs remain append-only and unchanged",
        },
    )
    imported_rows, final_results, episode_map_rows = import_recovered_rows(
        run_dir=run_dir,
        recovered_rows=checked["recovered"],
        normalization_ledger=normalization_by_call,
    )
    write_json(
        run_dir / "authorized_retry_manifest.json",
        {
            "call_id": retry_call["call_id"],
            "provider": retry_call["provider"],
            "model": retry_call["model"],
            "source_session_id": retry_call["source_session_id"],
            "attention_input_identity": retry_call["attention_input_identity"],
            "original_attempt_result": "FAILED_PARSE",
            "retry_reason": "SINGLE_EMPTY_PROVIDER_OUTPUT_RETRY",
            "maximum_retry_attempts_in_this_move": 1,
        },
    )

    journal_event(run_dir / "operation_journal.jsonl", "FINALIZATION_STARTED", recovered_import_count=len(imported_rows), authorized_retry_call_id=AUTHORIZED_RETRY_CALL_ID)
    retry_result = execute_retry_call(
        run_dir=run_dir,
        retry_call=retry_call,
        contract=runtime_contract,
        source_sessions=source_sessions,
        source_members=source_members,
    ) if dispatcher is None else _execute_retry_call_with_dispatcher(
        run_dir=run_dir,
        retry_call=retry_call,
        contract=runtime_contract,
        source_sessions=source_sessions,
        source_members=source_members,
        dispatcher=dispatcher,
    )

    if retry_result["final_state"] == "SUCCEEDED_VALID":
        normalized_row = retry_result["normalized_rows"][0]
        session_date = retry_call["session_date"]
        payload = _reconstruct_attention_payload(normalized_row, retry_call["source_session_id"], retry_call["provider"])
        final_results.append(
            {
                "call_id": retry_call["call_id"],
                "provider": retry_call["provider"],
                "model": retry_call["model"],
                "source_session_id": retry_call["source_session_id"],
                "session_date": session_date,
                "episode_ids": list(retry_call["episode_ids"]),
                "attention_result": payload,
                "result_source": "AUTHORIZED_RETRY_ATTEMPT_2",
                "source_live_run_identity": LIVE_RUN_ID,
                "source_repair_run_identity": REPAIR_RUN_ID,
            }
        )
        for episode_id in retry_call["episode_ids"]:
            episode_map_rows.append(
                {
                    "call_id": retry_call["call_id"],
                    "episode_id": episode_id,
                    "source_session_id": retry_call["source_session_id"],
                    "provider": retry_call["provider"],
                    "model": retry_call["model"],
                    "result_source": "AUTHORIZED_RETRY_ATTEMPT_2",
                }
            )
        remaining_failed = []
        retry_decision = "AUTHORIZED_RETRY_SUCCEEDED_VALID"
    else:
        retry_decision = "AUTHORIZED_RETRY_FAILED"
        remaining_failed = [
            {
                "call_id": retry_call["call_id"],
                "provider": retry_call["provider"],
                "model": retry_call["model"],
                "failure_stage": retry_result["final_state"],
                "exact_remaining_reason": retry_result["failed_rows"][0]["exact_error"] if retry_result["failed_rows"] else retry_result["final_state"],
                "retry_required": True,
            }
        ]
    write_jsonl(run_dir / "final_normalized_attention_results.jsonl", final_results)
    write_jsonl(run_dir / "final_episode_attention_result_map.jsonl", episode_map_rows)
    write_jsonl(run_dir / "remaining_failed_calls.jsonl", remaining_failed)

    final_count = len(final_results)
    by_provider_model = Counter(f"{row['provider']}|{row['model']}" for row in final_results)
    sessions_finalized = len({row["source_session_id"] for row in final_results})
    episodes_mapped = len({row["episode_id"] for row in episode_map_rows})
    reconciliation = {
        "original_authorized_batch_001_calls": EXPECTED_TOTAL_CALLS,
        "original_provider_calls_performed": 12,
        "preserved_responses_recovered": 11,
        "provider_calls_repeated": 0,
        "new_retry_calls": 1,
        "final_validated_results": final_count,
        "remaining_failed_calls": len(remaining_failed),
        "duplicate_calls": 0,
        "unexpected_calls": 0,
        "sessions_finalized": sessions_finalized,
        "episodes_mapped": episodes_mapped,
        "results_by_provider_model": dict(sorted(by_provider_model.items())),
    }
    write_json(run_dir / "batch_001_final_reconciliation.json", reconciliation)
    write_json(
        run_dir / "batch_001_final_summary.json",
        {
            **reconciliation,
            "recovered_call_ids": [row["call_id"] for row in imported_rows],
            "retry_call_id": AUTHORIZED_RETRY_CALL_ID,
            "retry_terminal_state": retry_result["final_state"],
            "google_preflight": preflight,
        },
    )
    if retry_result["final_state"] == "SUCCEEDED_VALID":
        finalization_status = "ATTENTION_BATCH_001_FINALIZED"
        contract_decision = "ALL_BATCH_001_RESULTS_VALID"
        scaling_decision = "READY_FOR_ATTENTION_BATCH_002"
    else:
        finalization_status = "ATTENTION_BATCH_001_REMAINS_PARTIALLY_COMPLETE"
        contract_decision = "VALID_RESULTS_WITH_ONE_REMAINING_FAILURE"
        scaling_decision = "RETRY_REQUIRES_NEW_AUTHORIZATION"
    decision = {
        "finalization_status": finalization_status,
        "retry_decision": retry_decision,
        "contract_decision": contract_decision,
        "resume_decision": "BATCH_001_RESUME_STATE_FROZEN",
        "scaling_decision": scaling_decision,
    }
    write_json(run_dir / "batch_001_final_decision.json", decision)
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
        "imported_rows": imported_rows,
        "final_results": final_results,
        "remaining_failed": remaining_failed,
        "preflight": preflight,
        "retry_call": retry_call,
    }


def _reconstruct_attention_payload(normalized_row: Mapping[str, Any], session_id: str, provider: str) -> dict[str, Any]:
    rows = list(normalized_row["validated_attention_rows"])
    payload = {
        "object": "session_attention_map",
        "session_id": session_id,
        "provider": provider,
        "attention_items": [],
        "session_attention_summary": "Recovered from strict validated retry result.",
        "status": "ok",
    }
    for row in rows:
        payload["attention_items"].append(
            {
                "event_id": row["event_id"],
                "attention_label": row["attention_label"],
                "attention_rank": row["attention_rank"],
                "attention_reason": row["attention_reason"],
                "expected_market_channel": row["expected_market_channel"],
                "driver_role": row["driver_role"],
                "confidence": row["confidence"],
            }
        )
    return payload


def _execute_retry_call_with_dispatcher(
    *,
    run_dir: Path,
    retry_call: Mapping[str, Any],
    contract: Mapping[str, Any],
    source_sessions: Mapping[str, Any],
    source_members: Mapping[str, list[dict[str, Any]]],
    dispatcher: Callable[[Mapping[str, Any]], Mapping[str, Any]],
) -> dict[str, Any]:
    original_dispatch = batch.live_dispatch
    batch.live_dispatch = dispatcher
    try:
        return execute_retry_call(
            run_dir=run_dir,
            retry_call=retry_call,
            contract=contract,
            source_sessions=source_sessions,
            source_members=source_members,
        )
    finally:
        batch.live_dispatch = original_dispatch


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
