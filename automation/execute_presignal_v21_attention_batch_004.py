#!/usr/bin/env python3
"""Execute or fail-closed ATTN_BATCH_004 from the frozen Attention execution plan."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import bind_presignal_v21_step8_r3_runtime_v1 as binding
from automation import execute_presignal_v21_attention_batch_001 as base
from automation import execute_presignal_v21_attention_batch_002 as batch002
from automation import execute_presignal_v21_attention_batch_003 as batch003
from automation import google_clients
from automation import presignal_v21_provider_adapters_v1 as provider_adapters
from automation import presignal_v21_minimal_prospective_lineage_v1 as lineage
from automation import run_presignal_v21_step8_r2_historical_replication_v1 as replay

ROOT = base.ROOT
PLAN_ID = base.PLAN_ID
PLAN_ROOT = base.PLAN_ROOT
OUTPUT_ROOT = base.OUTPUT_ROOT
BATCH_ID = "ATTN_BATCH_004"
EXPECTED_CALL_COUNT = 12
EXPECTED_START_HEAD = "2ceda6dd484d1ba6d705fe66acfe39c02798683b"
TOKEN_PATH = Path("/Users/junhoshino/projects/presignal/local/token.json")
GOVERNING_BATCH_001_CLOSURE_ID = "PPHB-R1-ATTENTION-BATCH-001-CLOSED-20260729T035345Z-e3bc0c2909ca"
GOVERNING_BATCH_002_CLOSURE_ID = "PPHB-R1-ATTENTION-BATCH-002-CLOSED-20260729T044448Z-97d9ec4cf579"
GOVERNING_BATCH_003_CLOSURE_ID = "PPHB-R1-ATTENTION-BATCH-003-COMPLETENESS-RETRY-20260729T053347Z-3bbe67af1930"


def canonical_json(value: Any) -> str:
    return base.canonical_json(value)


def now() -> str:
    return base.now()


def write_json(path: Path, value: Any) -> None:
    base.write_json(path, value)


def write_jsonl(path: Path, rows) -> None:
    base.write_jsonl(path, rows)


def append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    base.append_jsonl(path, row)


def journal_event(path: Path, event: str, **extra: Any) -> None:
    base.journal_event(path, event, **extra)


def git_head() -> str:
    return base.git_head()


def is_descendant_of(commit: str) -> bool:
    return base.subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=ROOT).returncode == 0


def path_ref(path: Path) -> str:
    return base.path_ref(path)


def read_json(path: Path) -> dict[str, Any]:
    return base.read_json(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return base.read_jsonl(path)


def stripped_json_text(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return text


def load_batch_calls() -> list[dict[str, Any]]:
    calls = base.load_batch_calls(BATCH_ID)
    if len(calls) != EXPECTED_CALL_COUNT:
        raise base.AttentionBatchError("BATCH_004_CALL_COUNT_MISMATCH")
    prior_ids = {row["call_id"] for row in base.load_batch_calls(base.BATCH_ID)}
    prior_ids.update(row["call_id"] for row in batch002.load_batch_calls())
    prior_ids.update(row["call_id"] for row in batch003.load_batch_calls())
    overlap = [row["call_id"] for row in calls if row["call_id"] in prior_ids]
    if overlap:
        raise base.AttentionBatchError("BATCH_004_OVERLAPS_PRIOR_BATCH:" + ",".join(overlap))
    return calls


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


def preflight_credentials() -> dict[str, Any]:
    os.environ["PRESIGNAL_GOOGLE_TOKEN_PATH"] = str(TOKEN_PATH)
    if not TOKEN_PATH.exists():
        raise base.AttentionBatchError("GOOGLE_TOKEN_PATH_MISSING")
    credentials = google_clients.load_credentials(False, token_path=TOKEN_PATH)
    google_clients.build_script_service(credentials, 300)
    sheets = google_clients.build_sheets_service(credentials)
    spreadsheet = (
        sheets.spreadsheets()
        .get(spreadsheetId=google_clients.DEFAULT_SPREADSHEET_ID, fields="spreadsheetId,properties.title")
        .execute()
    )
    return {
        "credential_route_status": "READY",
        "resolved_token_path": str(TOKEN_PATH),
        "spreadsheet_id": spreadsheet["spreadsheetId"],
        "spreadsheet_title": spreadsheet["properties"]["title"],
        "script_id": google_clients.default_script_id(),
    }


def materialize_run(
    *,
    output_root: Path,
    fixed_timestamp: str | None = None,
    existing_run_dir: Path | None = None,
) -> Path:
    if existing_run_dir is not None:
        return existing_run_dir
    ts = fixed_timestamp or now()
    seed = {"plan_id": PLAN_ID, "batch_id": BATCH_ID, "timestamp": ts}
    run_id = (
        "PPHB-R1-ATTENTION-EXECUTION-BATCH-004-"
        + ts.replace(":", "").replace("-", "")
        + "-"
        + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:12]
    )
    return output_root / run_id


def initialize_run_files(
    run_dir: Path,
    batch_calls: list[dict[str, Any]],
    fingerprint_observations: Mapping[str, str],
    contract: Mapping[str, Any],
    source_sessions: Mapping[str, Any],
    source_members: Mapping[str, list[dict[str, Any]]],
) -> None:
    base.initialize_run_files(
        run_dir,
        batch_calls,
        fingerprint_observations,
        contract,
        source_sessions,
        source_members,
    )
    for name in ("event_completeness_results.jsonl", "attention_parse_results.jsonl"):
        path = run_dir / name
        if not path.exists():
            path.write_text("")
    write_json(
        run_dir / "run_manifest.json",
        {
            **base.read_json(run_dir / "run_manifest.json"),
            "governing_batch_001_closure_id": GOVERNING_BATCH_001_CLOSURE_ID,
            "governing_batch_002_closure_id": GOVERNING_BATCH_002_CLOSURE_ID,
            "governing_batch_003_closure_id": GOVERNING_BATCH_003_CLOSURE_ID,
            "authorized_batch_id": BATCH_ID,
            "maximum_authorized_calls": EXPECTED_CALL_COUNT,
            "predecessor_run_id": None,
            "predecessor_attempted_calls": None,
            "rerun_reason": None,
        },
    )
    write_json(
        run_dir / "batch_execution_contract.json",
        {
            "governing_plan_id": PLAN_ID,
            "governing_batch_001_closure_id": GOVERNING_BATCH_001_CLOSURE_ID,
            "governing_batch_002_closure_id": GOVERNING_BATCH_002_CLOSURE_ID,
            "governing_batch_003_closure_id": GOVERNING_BATCH_003_CLOSURE_ID,
            "batch_id": BATCH_ID,
            "authorized_call_count": EXPECTED_CALL_COUNT,
            "authorized_call_identities": [row["call_id"] for row in batch_calls],
            "provider_model_routes": dict(base.PROVIDER_MODELS),
            "canonical_attention_contract": "session_attention_map",
            "identity_normalization_rules": "historical Attention provider authority binding plus previously validated narrow compatibility rules",
            "event_completeness_rule": "expected and returned event-ID sets must match exactly before strict validation",
            "raw_before_parse_requirement": True,
            "retry_policy": "no automatic retry for success or failure within Batch 004",
            "resume_policy": "validated terminal call states skip repeat dispatch",
            "immutability_rules": "append-only run artifacts only; no matrix update in this Move",
        },
    )


def execute_call(
    *,
    run_dir: Path,
    call: Mapping[str, Any],
    session: Mapping[str, Any],
    members: list[Mapping[str, Any]],
    contract: Mapping[str, Any],
    dispatcher: Callable[[Mapping[str, Any]], Mapping[str, Any]],
) -> dict[str, Any]:
    journal = run_dir / "operation_journal.jsonl"
    raw_transport_path = run_dir / "raw_transport_results.jsonl"
    raw_output_path = run_dir / "raw_provider_outputs.jsonl"
    provider_authority_path = run_dir / "provider_authority_results.jsonl"
    completeness_path = run_dir / "event_completeness_results.jsonl"
    parse_path = run_dir / "attention_parse_results.jsonl"
    normalized_path = run_dir / "normalized_attention_results.jsonl"
    validation_path = run_dir / "attention_validation_results.jsonl"
    episode_map_path = run_dir / "episode_attention_result_map.jsonl"
    failed_path = run_dir / "failed_call_ledger.jsonl"

    identity = base.attention_input_identity(call, session, members, contract)
    terminal = base.read_terminal_results(validation_path).get(call["call_id"])
    if terminal is not None:
        if terminal["final_state"] == "SUCCEEDED_VALID":
            journal_event(journal, "CALL_SKIPPED_ALREADY_SUCCEEDED", call_id=call["call_id"], provider=call["provider"], model=call["model"])
            return {"final_state": "SKIPPED_ALREADY_SUCCEEDED", "attempted": False}
        journal_event(journal, "CALL_SKIPPED_TERMINAL_FAILURE", call_id=call["call_id"], provider=call["provider"], model=call["model"], prior_state=terminal["final_state"])
        return {"final_state": terminal["final_state"], "attempted": False, "skipped_terminal_failure": True}

    expected_event_ids = [row["event_id"] for row in members]
    instruction_override = build_completeness_instruction(binding.attention_instruction(contract, call["provider"]), expected_event_ids)
    request_fingerprint = identity["request_fingerprint"]
    try:
        request_fingerprint = lineage.build_prospective_attention(
            study_id="HISTORICAL_R3",
            collection_run_id=run_dir.name,
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
        )["metadata"]["request_fingerprint"]
    except Exception:
        pass

    journal_event(
        journal,
        "CALL_STARTED",
        call_id=call["call_id"],
        batch_id=BATCH_ID,
        execution_order=call["execution_order"],
        attempt_number=1,
        provider=call["provider"],
        model=call["model"],
        source_session_id=call["source_session_id"],
        attention_input_fingerprint=request_fingerprint,
        expected_event_ids=expected_event_ids,
        state="CALL_STARTED",
    )
    transport_holder: dict[str, Any] = {}

    def wrapped_dispatch(payload: Mapping[str, Any]) -> Mapping[str, Any]:
        transport_holder["request"] = dict(payload)
        response = dict(dispatcher(payload))
        transport_holder["response"] = response
        return response

    final_state = "FAILED_TRANSPORT"
    error_code = ""
    error_summary = ""
    validation_details: dict[str, Any] = {}
    normalized_row: dict[str, Any] | None = None
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
            attention_run_id="LIVE_" + call["call_id"],
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
        final_state, error_code = base.classify_transport_exception(exc)
        error_summary = str(exc)
        result = None

    transport = transport_holder.get("response")
    request_payload = transport_holder.get("request") or {}
    raw_claimed_provider = None
    if transport is not None:
        raw_output_preserved = transport.get("raw_output_original", transport.get("raw_output"))
        raw_claimed_provider = provider_adapters.extract_raw_provider_claim(raw_output_preserved)
        raw_output_length = len(raw_output_preserved) if isinstance(raw_output_preserved, str) else None
        actual_provider = transport.get("actual_provider")
        actual_model = transport.get("actual_model")
        authority_agreement = actual_provider == call["provider"] and actual_model == call["model"]
        if actual_provider is None or actual_model is None:
            authority_decision = "TRANSPORT_METADATA_MISSING"
            canonical_provider = None
        elif authority_agreement:
            authority_decision = "MANIFEST_TRANSPORT_MATCH"
            canonical_provider = call["provider"]
        else:
            authority_decision = "MANIFEST_TRANSPORT_CONFLICT"
            canonical_provider = None
        append_jsonl(
            raw_transport_path,
            {
                "call_id": call["call_id"],
                "provider": call["provider"],
                "model": call["model"],
                "source_session_id": call["source_session_id"],
                "transport_status": transport.get("status"),
                "actual_provider": actual_provider,
                "actual_model": actual_model,
                "completed_timestamp": transport.get("completed_timestamp"),
                "prompt_tokens": transport.get("prompt_tokens"),
                "completion_tokens": transport.get("completion_tokens"),
                "latency_ms": transport.get("latency_ms"),
                "stop_reason": transport.get("stop_reason"),
                "usage_metadata": transport.get("usage_metadata"),
                "configured_max_output_tokens": transport.get("configured_max_output_tokens", request_payload.get("max_output_tokens")),
                "preserve_raw_before_parse": bool(request_payload.get("preserve_raw_before_parse") is True),
                "response_length": raw_output_length,
                "response_fingerprint": base.sha256_text(transport),
            },
        )
        append_jsonl(
            raw_output_path,
            {
                "call_id": call["call_id"],
                "provider": call["provider"],
                "model": call["model"],
                "source_session_id": call["source_session_id"],
                "raw_output": raw_output_preserved,
                "raw_output_fingerprint": base.sha256_text(raw_output_preserved),
                "raw_output_returned": bool(raw_output_preserved not in (None, "")),
            },
        )
        append_jsonl(
            provider_authority_path,
            {
                "call_id": call["call_id"],
                "manifest_provider": call["provider"],
                "manifest_model": call["model"],
                "transport_provider": actual_provider,
                "transport_model": actual_model,
                "raw_claimed_provider": raw_claimed_provider,
                "authority_agreement": authority_agreement,
                "canonical_provider": canonical_provider,
                "authority_decision": authority_decision,
            },
        )
        journal_event(journal, "TRANSPORT_COMPLETED", call_id=call["call_id"], transport_status=transport.get("status"))
        completeness, _ = determine_event_completeness(
            raw_output=raw_output_preserved,
            call=call,
            contract=contract,
            expected_event_ids=expected_event_ids,
            transport=transport,
        )
        append_jsonl(completeness_path, completeness)

    if result is not None:
        journal_event(journal, "NORMALIZATION_COMPLETED", call_id=call["call_id"], parse_status=result.get("status"))
        if result.get("status") == "provider_contract_error":
            transport_status = str((transport or {}).get("status") or "")
            if transport_status in base.PROVIDER_FAILURE_STATUSES:
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
            valid, validation_error, validation_details = base.validate_attention_result(
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
                    "result_fingerprint": base.sha256_text(result),
                }
                append_jsonl(normalized_path, normalized_row)
                for episode_id in call["episode_ids"]:
                    append_jsonl(
                        episode_map_path,
                        {
                            "call_id": call["call_id"],
                            "episode_id": episode_id,
                            "source_session_id": call["source_session_id"],
                            "provider": call["provider"],
                            "model": call["model"],
                            "normalized_result_fingerprint": normalized_row["result_fingerprint"],
                        },
                    )
            else:
                final_state = "FAILED_VALIDATION"
                error_code = validation_error or "VALIDATION_FAILED"
                error_summary = error_code
        journal_event(journal, "VALIDATION_COMPLETED", call_id=call["call_id"], final_state=final_state)

    append_jsonl(
        parse_path,
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
    append_jsonl(validation_path, validation_row)
    if final_state == "SUCCEEDED_VALID":
        journal_event(journal, "CALL_SUCCEEDED", call_id=call["call_id"], provider=call["provider"], model=call["model"])
    else:
        append_jsonl(
            failed_path,
            {
                "call_id": call["call_id"],
                "provider": call["provider"],
                "model": call["model"],
                "source_session_id": call["source_session_id"],
                "failure_stage": final_state,
                "exact_error": error_code or error_summary,
                "raw_evidence_reference": path_ref(raw_output_path),
                "retry_recommendation": "NO_AUTOMATIC_RETRY_IN_BATCH_004",
            },
        )
        journal_event(journal, "CALL_FAILED", call_id=call["call_id"], provider=call["provider"], model=call["model"], final_state=final_state)
    return {"final_state": final_state, "attempted": True}


def summarize_run(run_dir: Path, batch_calls: list[dict[str, Any]], blocked_reason: str | None = None) -> dict[str, Any]:
    reconciliation = base.summarize_run(run_dir, batch_calls, blocked_reason=blocked_reason)
    completeness_rows = read_jsonl(run_dir / "event_completeness_results.jsonl") if (run_dir / "event_completeness_results.jsonl").exists() else []
    completeness_counts = Counter(row.get("completeness_decision") for row in completeness_rows)
    authority_rows = read_jsonl(run_dir / "provider_authority_results.jsonl") if (run_dir / "provider_authority_results.jsonl").exists() else []
    agreement = sum(1 for row in authority_rows if row.get("authority_agreement") is True)
    conflicts = sum(1 for row in authority_rows if row.get("authority_decision") == "MANIFEST_TRANSPORT_CONFLICT")
    reconciliation["authorized_calls"] = EXPECTED_CALL_COUNT
    reconciliation["completeness_passed_calls"] = completeness_counts.get("PASSED", 0)
    reconciliation["completeness_failed_calls"] = completeness_counts.get("FAILED", 0)
    reconciliation["completeness_not_reached_calls"] = completeness_counts.get("NOT_REACHED", 0)
    reconciliation["manifest_transport_agreement_count"] = agreement
    reconciliation["manifest_transport_conflict_count"] = conflicts
    write_json(run_dir / "batch_reconciliation.json", reconciliation)
    summary = base.read_json(run_dir / "batch_summary.json")
    summary["authorized_calls"] = EXPECTED_CALL_COUNT
    summary["completeness_passed_calls"] = reconciliation["completeness_passed_calls"]
    summary["completeness_failed_calls"] = reconciliation["completeness_failed_calls"]
    summary["completeness_not_reached_calls"] = reconciliation["completeness_not_reached_calls"]
    summary["manifest_transport_agreement_count"] = agreement
    summary["manifest_transport_conflict_count"] = conflicts
    write_json(run_dir / "batch_summary.json", summary)
    return reconciliation


def execute_batch(
    *,
    output_root: Path = OUTPUT_ROOT,
    dispatcher: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    fixed_timestamp: str | None = None,
    resume_run_dir: Path | None = None,
    source_session_loader: Callable[[], tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]] | None = None,
    enforce_head: bool = True,
) -> dict[str, Any]:
    if enforce_head and git_head() != EXPECTED_START_HEAD:
        raise base.AttentionBatchError("UNEXPECTED_START_HEAD")
    if enforce_head and not is_descendant_of(EXPECTED_START_HEAD):
        raise base.AttentionBatchError("AUTHORIZED_START_HEAD_NOT_ANCESTOR")
    plan_contract = base.load_plan_contract()
    contract = base.load_runtime_contract()
    fingerprint_observations = base.verify_plan_fingerprints()
    batch_calls = load_batch_calls()
    run_dir = materialize_run(output_root=output_root, fixed_timestamp=fixed_timestamp, existing_run_dir=resume_run_dir)

    credential_status = "SKIPPED_FOR_TEST_DISPATCH" if dispatcher is not None else None
    blocked_reason = None
    if dispatcher is None:
        try:
            preflight = preflight_credentials()
            credential_status = preflight["credential_route_status"]
        except Exception as exc:
            blocked_reason = str(exc)
            credential_status = type(exc).__name__
            initialize_run_files(run_dir, batch_calls, fingerprint_observations, contract, {}, {})
            journal_event(run_dir / "operation_journal.jsonl", "BATCH_STARTED", batch_id=BATCH_ID, authorized_calls=EXPECTED_CALL_COUNT)
            journal_event(run_dir / "operation_journal.jsonl", "BATCH_BLOCKED", batch_id=BATCH_ID, reason=blocked_reason)
            reconciliation = summarize_run(run_dir, batch_calls, blocked_reason=blocked_reason)
            decision = {
                "execution_status": "ATTENTION_BATCH_004_BLOCKED",
                "contract_decision": "EXECUTION_ENVIRONMENT_FAILURE",
                "provider_authority_decision": "PROVIDER_AUTHORITY_NOT_REACHED",
                "completeness_decision": "COMPLETENESS_NOT_REACHED",
                "resume_decision": "RESUME_PROTECTION_VALIDATED",
                "scaling_decision": "REPAIR_BEFORE_BATCH_005",
                "blocked_reason": blocked_reason,
                "credential_route_status": credential_status,
                "plan_contract_identity": plan_contract["attention_output_contract"]["object"],
                "runtime_contract_version": contract["contract_version"],
            }
            base.update_run_manifest(run_dir / "run_manifest.json", provider_calls_executed=0)
            write_json(run_dir / "batch_decision.json", decision)
            return {"run_dir": run_dir, "batch_calls": batch_calls, "decision": decision, "reconciliation": reconciliation}

    loader = source_session_loader or base.read_source_sessions
    source_sessions, source_members = loader()
    for call in batch_calls:
        if call["source_session_id"] not in source_sessions:
            raise base.AttentionBatchError("SOURCE_SESSION_MISSING:" + call["source_session_id"])
    initialize_run_files(run_dir, batch_calls, fingerprint_observations, contract, source_sessions, source_members)
    journal_event(run_dir / "operation_journal.jsonl", "BATCH_STARTED", batch_id=BATCH_ID, authorized_calls=EXPECTED_CALL_COUNT)

    actual_dispatcher = dispatcher or base.live_dispatch
    for call in batch_calls:
        session = source_sessions[call["source_session_id"]]
        members = source_members[call["source_session_id"]]
        execute_call(
            run_dir=run_dir,
            call=call,
            session=session,
            members=members,
            contract=contract,
            dispatcher=actual_dispatcher,
        )
    journal_event(run_dir / "operation_journal.jsonl", "BATCH_COMPLETED", batch_id=BATCH_ID)
    reconciliation = summarize_run(run_dir, batch_calls)
    successful = reconciliation["successful_valid_calls"]
    failures = (
        reconciliation["failed_transport_calls"]
        + reconciliation["failed_provider_calls"]
        + reconciliation["failed_parse_calls"]
        + reconciliation["failed_validation_calls"]
        + reconciliation["failed_provider_authority_calls"]
        + reconciliation["completeness_failed_calls"]
    )
    base.update_run_manifest(run_dir / "run_manifest.json", provider_calls_executed=reconciliation["attempted_calls"])
    if failures == 0:
        contract_decision = "ALL_BATCH_RESULTS_VALID"
        provider_authority_decision = "ALL_PROVIDER_IDENTITIES_AUTHORITATIVELY_BOUND"
        completeness_decision = "ALL_EXPECTED_EVENT_ROWS_RETURNED"
        scaling_decision = "READY_FOR_ATTENTION_BATCH_005"
    elif successful == 0:
        contract_decision = "LIVE_ATTENTION_CONTRACT_FAILURE"
        provider_authority_decision = "PROVIDER_AUTHORITY_FAILURES_PRESENT" if reconciliation["failed_provider_authority_calls"] else "PROVIDER_AUTHORITY_NOT_REACHED"
        completeness_decision = "COMPLETENESS_NOT_REACHED" if reconciliation["completeness_not_reached_calls"] else "EVENT_COMPLETENESS_FAILURES_PRESENT"
        scaling_decision = "REPAIR_BEFORE_BATCH_005"
    else:
        contract_decision = "VALID_RESULTS_WITH_FAILED_CALLS"
        provider_authority_decision = "PROVIDER_AUTHORITY_FAILURES_PRESENT" if reconciliation["failed_provider_authority_calls"] else "ALL_PROVIDER_IDENTITIES_AUTHORITATIVELY_BOUND"
        completeness_decision = (
            "EVENT_COMPLETENESS_FAILURES_PRESENT"
            if reconciliation["completeness_failed_calls"]
            else "COMPLETENESS_NOT_REACHED" if reconciliation["completeness_not_reached_calls"] else "ALL_EXPECTED_EVENT_ROWS_RETURNED"
        )
        scaling_decision = "RETRY_FAILED_BATCH_004_CALLS_REQUIRES_AUTHORIZATION"
    decision = {
        "execution_status": "ATTENTION_BATCH_004_COMPLETE" if successful == EXPECTED_CALL_COUNT else "ATTENTION_BATCH_004_PARTIALLY_COMPLETE",
        "contract_decision": contract_decision,
        "provider_authority_decision": provider_authority_decision,
        "completeness_decision": completeness_decision,
        "resume_decision": "RESUME_PROTECTION_VALIDATED",
        "scaling_decision": scaling_decision,
    }
    write_json(run_dir / "batch_decision.json", decision)
    return {"run_dir": run_dir, "batch_calls": batch_calls, "decision": decision, "reconciliation": reconciliation}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--fixed-timestamp")
    args = parser.parse_args(argv)
    result = execute_batch(output_root=args.output_root, fixed_timestamp=args.fixed_timestamp)
    print(
        json.dumps(
            {
                "run_dir": str(result["run_dir"]),
                "execution_status": result["decision"]["execution_status"],
                "attempted_calls": result["reconciliation"]["attempted_calls"],
                "successful_valid_calls": result["reconciliation"]["successful_valid_calls"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
