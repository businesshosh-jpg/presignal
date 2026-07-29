#!/usr/bin/env python3
"""Execute or fail-closed ATTN_BATCH_001 from the frozen Attention execution plan."""
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
from typing import Any, Callable, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import bind_presignal_v21_step8_r3_runtime_v1 as binding
from automation import google_clients
from automation import presignal_v21_minimal_prospective_lineage_v1 as lineage
from automation import run_presignal_v21_single_event_path_pair_v1_1 as single
from automation import run_presignal_v21_step8_r2_historical_replication_v1 as replay

PLAN_ID = "PPHB-R1-ATTENTION-EXECUTION-PLAN-20260729T010207Z-3fcd59f96f3c"
PLAN_ROOT = (
    ROOT
    / "outputs"
    / "presignal_v21_full_round_1_attention_execution_plan"
    / PLAN_ID
)
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_execution"
BATCH_ID = "ATTN_BATCH_001"
PREDECESSOR_RUN_ID = "PPHB-R1-ATTENTION-EXECUTION-BATCH-001-20260729T012813Z-4a361d6c2add"
PREDECESSOR_ATTEMPTED_CALLS = 0
RERUN_REASON = "GOOGLE_AUTHENTICATION_RECOVERED_BEFORE_FIRST_PROVIDER_DISPATCH"
EXPECTED_HEAD_ANCESTOR = "773fba1d4d643d2a64ca3e42a39edb2b30efe39f"
EXPECTED_CALL_COUNT = 12
EXPECTED_FILES = {
    "attention_execution_contract.json": "e04d91b2110b58f3af8a6c3a5e3a36e07d0935a0907e82d4e7738803e59d44dd",
    "attention_call_ledger.jsonl": "13182cd31247f7d7cb45aa168c1e74e862150d0aa705f6a5d6d7904634446697",
    "attention_call_batches.json": "edd135b25faf7dbe842a043a923e8db41e4a0d62299615658e7b2df36ac7ce5c",
    "episode_to_attention_call_map.jsonl": "f6477c6dbde191bd84c7b2df4eccc257def5d4b6d61f8080726b6f6b151e2008",
    "unique_session_inventory.jsonl": "d9db436c706c98bc9fe1c5e42e24bd33175d26aeae2ba2dc959256d23c600ba3",
    "attention_plan_summary.json": "e8d2ff78222d2e7b21f2fd2a586c2da64839df9e64011dd82f7b4ba26fda98ee",
}
PROVIDER_MODELS = {
    "Anthropic": "claude-haiku-4-5",
    "Gemini": "gemini-2.5-flash-lite",
    "OpenAI": "gpt-4o-mini-2024-07-18",
}
PROVIDER_FAILURE_STATUSES = {
    "provider_unavailable",
    "model_not_enforceable",
    "unsupported_provider",
    "configuration_error",
}
TERMINAL_STATUSES = {
    "SUCCEEDED_VALID",
    "FAILED_TRANSPORT",
    "FAILED_PROVIDER",
    "FAILED_PARSE",
    "FAILED_VALIDATION",
}
STEP8_R2_SESSIONS_ROOT = ROOT / "outputs" / "presignal_v21_step8_r2_historical_replication" / "STEP8-R2-e057ba70c884e0e618cf" / "sessions"
POPULATION_AUDIT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_population_audit" / "PPHB-R1-FULL-POPULATION-AUDIT-20260728T125525Z-b25cd178e7d6"


class AttentionBatchError(RuntimeError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_hex_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_text(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


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
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temp, path)


def update_run_manifest(path: Path, **updates: Any) -> None:
    manifest = read_json(path) if path.exists() else {}
    manifest.update(updates)
    write_json(path, manifest)


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text("".join(canonical_json(row) + "\n" for row in rows))
    os.replace(temp, path)


def append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(canonical_json(dict(row)) + "\n")


def load_plan_contract() -> dict[str, Any]:
    return read_json(PLAN_ROOT / "attention_execution_contract.json")


def load_runtime_contract() -> dict[str, Any]:
    return dict(binding.load_manifest()["contract"])


def verify_plan_fingerprints() -> dict[str, str]:
    observed: dict[str, str] = {}
    for name, expected in EXPECTED_FILES.items():
        path = PLAN_ROOT / name
        if not path.exists():
            raise AttentionBatchError("PLAN_ARTIFACT_MISSING:" + name)
        actual = sha256_hex_bytes(path.read_bytes())
        observed[name] = actual
        if actual != expected:
            raise AttentionBatchError("PLAN_ARTIFACT_FINGERPRINT_MISMATCH:" + name)
    return observed


def load_batch_calls(batch_id: str = BATCH_ID) -> list[dict[str, Any]]:
    ledger = read_jsonl(PLAN_ROOT / "attention_call_ledger.jsonl")
    batches = read_json(PLAN_ROOT / "attention_call_batches.json")
    batch = next((row for row in batches["batches"] if row["batch_id"] == batch_id), None)
    if batch is None:
        raise AttentionBatchError("BATCH_ID_NOT_FOUND")
    call_ids = list(batch["call_ids"])
    if len(call_ids) != EXPECTED_CALL_COUNT or len(set(call_ids)) != EXPECTED_CALL_COUNT:
        raise AttentionBatchError("FROZEN_BATCH_NOT_12_UNIQUE_CALLS")
    calls = [row for row in ledger if row["call_id"] in set(call_ids)]
    calls.sort(key=lambda row: row["execution_order"])
    if [row["call_id"] for row in calls] != call_ids:
        raise AttentionBatchError("BATCH_ORDER_MISMATCH")
    if any(row["call_status"] != "PLANNED" for row in calls):
        raise AttentionBatchError("BATCH_CALL_STATUS_NOT_PLANNED")
    return calls


def load_unique_session_inventory() -> dict[str, dict[str, Any]]:
    rows = read_jsonl(PLAN_ROOT / "unique_session_inventory.jsonl")
    return {row["source_session_id"]: row for row in rows}


def _session_payload_from_step8(session_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
    base = STEP8_R2_SESSIONS_ROOT / session_id / "attention"
    if not base.exists():
        return None
    for provider_file in sorted(base.glob("*.json")):
        payload = read_json(provider_file)
        request = payload.get("request") or {}
        prompt = request.get("prompt") or {}
        user = prompt.get("user")
        if not isinstance(user, str) or not user.strip():
            continue
        try:
            prompt_payload = json.loads(user)
        except json.JSONDecodeError:
            continue
        session = dict(prompt_payload.get("session") or {})
        events = [dict(row) for row in (prompt_payload.get("events") or []) if isinstance(row, Mapping)]
        if session.get("session_id") == session_id and events:
            return session, events
    return None


def _population_calendar_rows() -> list[dict[str, Any]]:
    return read_jsonl(POPULATION_AUDIT_ROOT / "normalized_calendar_event_manifest.jsonl")


def _session_payload_from_population_audit(session_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    parts = session_id.split("|")
    if len(parts) != 3:
        raise AttentionBatchError("INVALID_SESSION_ID:" + session_id)
    country, session_date, session_window_name = parts
    rows = [
        row for row in _population_calendar_rows()
        if row.get("country") == country and str(row.get("canonical_utc_release_timestamp", "")).startswith(session_date)
    ]
    if not rows:
        raise AttentionBatchError("POPULATION_AUDIT_SESSION_MISSING:" + session_id)
    rows.sort(key=lambda row: (
        str(row.get("canonical_utc_release_timestamp") or ""),
        int(((row.get("source_lineage") or {}).get("excel_row_number") or 10**9)),
        str(row.get("event_id") or ""),
    ))
    session = {
        "session_id": session_id,
        "country": country,
        "session_window_name": session_window_name,
        "session_start_ts": rows[0]["canonical_utc_release_timestamp"],
        "session_end_ts": rows[-1]["canonical_utc_release_timestamp"],
    }
    events = []
    for index, row in enumerate(rows, 1):
        events.append(
            {
                "event_id": row.get("event_id", ""),
                "batch_id": row.get("batch_id", ""),
                "type": row.get("type", ""),
                "indicator_name": row.get("normalized_indicator_name") or row.get("raw_indicator_name") or "",
                "genre": row.get("event_family", ""),
                "importance": row.get("importance", ""),
                "release_ts": row.get("canonical_utc_release_timestamp", ""),
                "consensus_value": "",
                "prev_revision": "",
                "member_order": index,
            }
        )
    return session, events


def read_source_sessions() -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    session_inventory = load_unique_session_inventory()
    session_by_id: dict[str, dict[str, Any]] = {}
    members_by_session: dict[str, list[dict[str, Any]]] = {}
    for session_id in sorted(session_inventory):
        exact = _session_payload_from_step8(session_id)
        session_payload, event_rows = exact or _session_payload_from_population_audit(session_id)
        session_by_id[session_id] = {
            "session_id": session_payload.get("session_id", session_id),
            "country": session_payload.get("country", session_id.split("|")[0]),
            "session_window_name": session_payload.get("session_window_name", session_id.split("|")[2]),
            "session_start_ts": session_payload.get("session_start_ts", ""),
            "session_end_ts": session_payload.get("session_end_ts", ""),
            "forecast_cutoff": session_payload.get("session_start_ts", "") or session_payload.get("session_end_ts", ""),
        }
        members_by_session[session_id] = [dict(row) for row in event_rows]
    return session_by_id, members_by_session


def attention_input_identity(call: Mapping[str, Any], session: Mapping[str, Any], members: list[Mapping[str, Any]], contract: Mapping[str, Any]) -> dict[str, Any]:
    generation_settings = binding.generation_settings(contract, call["provider"], "ATTENTION")
    dry_run = lineage.build_prospective_attention(
        study_id="HISTORICAL_R3",
        collection_run_id="FROZEN_ATTENTION_EXECUTION_PLAN",
        session_snapshot=replay._session_snapshot(session),
        member_rows=members,
        provider=call["provider"],
        model=call["model"],
        information_cutoff_ts=session["forecast_cutoff"],
        attention_run_id="PLAN_" + call["call_id"],
        stage_generated_ts=session["forecast_cutoff"],
        dispatcher=None,
        instruction_override=binding.attention_instruction(contract, call["provider"]),
        generation_settings=generation_settings,
    )
    return {
        "request_fingerprint": dry_run["metadata"]["request_fingerprint"],
        "session_snapshot_fingerprint": sha256_text(dry_run["request"]["prompt"]["user"]),
        "input_cutoff": session["forecast_cutoff"],
        "member_count": len(members),
        "attention_input_artifact": call["attention_input_artifact"],
    }


def journal_event(path: Path, event: str, **extra: Any) -> None:
    append_jsonl(path, {"event": event, "timestamp": now(), **extra})


def read_terminal_results(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    rows = read_jsonl(path)
    return {row["call_id"]: row for row in rows if row.get("final_state") in TERMINAL_STATUSES}


def validate_attention_result(
    *,
    result: Mapping[str, Any],
    expected_session_id: str,
    expected_provider: str,
    expected_model: str,
    member_ids: list[str],
    contract: Mapping[str, Any],
) -> tuple[bool, str | None, dict[str, Any]]:
    if result.get("status") != "parsed":
        return False, "RESULT_NOT_PARSED", {}
    rows = list(result.get("rows") or [])
    statuses = [row.get("status") for row in rows]
    if len(rows) != len(member_ids):
        return False, "ATTENTION_MEMBER_COUNT_MISMATCH", {"rows": len(rows), "members": len(member_ids)}
    if any(status != "parsed" for status in statuses):
        return False, "ATTENTION_ROW_STATUS_INVALID", {"statuses": statuses}
    if any(row.get("session_id") != expected_session_id for row in rows):
        return False, "ATTENTION_SESSION_ID_MISMATCH", {}
    if any(row.get("provider") != expected_provider or row.get("model") != expected_model for row in rows):
        return False, "ATTENTION_PROVIDER_MODEL_MISMATCH", {}
    event_ids = [row.get("event_id") for row in rows]
    if sorted(event_ids) != sorted(member_ids):
        return False, "ATTENTION_EVENT_MEMBERSHIP_MISMATCH", {"event_ids": event_ids}
    try:
        binding.validate_attention_rank(rows, contract)
    except Exception as exc:
        return False, str(exc), {}
    for row in rows:
        if not row.get("attention_label") or not row.get("attention_reason") or not row.get("expected_market_channel"):
            return False, "ATTENTION_SCIENTIFIC_FIELDS_MISSING", {}
    return True, None, {"row_count": len(rows), "event_ids": sorted(event_ids)}


def classify_transport_exception(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, google_clients.GoogleCredentialError):
        return "FAILED_TRANSPORT", exc.code
    classified = google_clients.classify_google_exception(exc)
    return "FAILED_TRANSPORT", classified["category"]


def live_dispatch(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return single.bridge_dispatch(payload)


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
    normalized_path = run_dir / "normalized_attention_results.jsonl"
    validation_path = run_dir / "attention_validation_results.jsonl"
    episode_map_path = run_dir / "episode_attention_result_map.jsonl"
    failed_path = run_dir / "failed_call_ledger.jsonl"

    identity = attention_input_identity(call, session, members, contract)
    terminal = read_terminal_results(validation_path).get(call["call_id"])
    if terminal is not None:
        if terminal["final_state"] == "SUCCEEDED_VALID":
            journal_event(journal, "CALL_SKIPPED_ALREADY_SUCCEEDED", call_id=call["call_id"], provider=call["provider"], model=call["model"])
            return {"final_state": "SKIPPED_ALREADY_SUCCEEDED", "attempted": False}
        journal_event(journal, "CALL_SKIPPED_TERMINAL_FAILURE", call_id=call["call_id"], provider=call["provider"], model=call["model"], prior_state=terminal["final_state"])
        return {"final_state": terminal["final_state"], "attempted": False, "skipped_terminal_failure": True}

    journal_event(
        journal,
        "CALL_STARTED",
        call_id=call["call_id"],
        attempt_number=1,
        provider=call["provider"],
        model=call["model"],
        source_session_id=call["source_session_id"],
        attention_input_fingerprint=identity["request_fingerprint"],
        state="STARTED",
    )
    transport_holder: dict[str, Any] = {}

    def wrapped_dispatch(payload: Mapping[str, Any]) -> Mapping[str, Any]:
        response = dict(dispatcher(payload))
        transport_holder["response"] = response
        return response

    final_state = "FAILED_TRANSPORT"
    error_code = ""
    error_summary = ""
    validation_details: dict[str, Any] = {}
    normalized_row: dict[str, Any] | None = None
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
            raw_parser=lambda raw: binding.attention_parser(call["provider"], raw, contract),
            instruction_override=binding.attention_instruction(contract, call["provider"]),
            generation_settings=binding.generation_settings(contract, call["provider"], "ATTENTION"),
        )
    except Exception as exc:
        final_state, error_code = classify_transport_exception(exc)
        error_summary = str(exc)
        result = None

    transport = transport_holder.get("response")
    if transport is not None:
        append_jsonl(
            raw_transport_path,
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
                "response_fingerprint": sha256_text(transport),
            },
        )
        append_jsonl(
            raw_output_path,
            {
                "call_id": call["call_id"],
                "provider": call["provider"],
                "model": call["model"],
                "source_session_id": call["source_session_id"],
                "raw_output": transport.get("raw_output_original", transport.get("raw_output")),
                "raw_output_fingerprint": sha256_text(transport.get("raw_output_original", transport.get("raw_output"))),
            },
        )
        journal_event(journal, "TRANSPORT_COMPLETED", call_id=call["call_id"], transport_status=transport.get("status"))

    if result is not None:
        journal_event(journal, "NORMALIZATION_COMPLETED", call_id=call["call_id"], parse_status=result.get("status"))
        if result.get("status") == "provider_contract_error":
            transport_status = str((transport or {}).get("status") or "")
            if transport_status in PROVIDER_FAILURE_STATUSES:
                final_state = "FAILED_PROVIDER"
                error_code = transport_status or "PROVIDER_CONTRACT_ERROR"
            else:
                final_state = "FAILED_PARSE"
                error_code = str(((result.get("rows") or [{}])[0]).get("error_message") or result.get("status"))
            error_summary = error_code
        else:
            valid, validation_error, validation_details = validate_attention_result(
                result=result,
                expected_session_id=call["source_session_id"],
                expected_provider=call["provider"],
                expected_model=call["model"],
                member_ids=[row["event_id"] for row in members],
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

    validation_row = {
        "call_id": call["call_id"],
        "provider": call["provider"],
        "model": call["model"],
        "source_session_id": call["source_session_id"],
        "attention_input_fingerprint": identity["request_fingerprint"],
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
                "retry_recommendation": "NO_AUTOMATIC_RETRY_IN_BATCH_001",
            },
        )
        journal_event(journal, "CALL_FAILED", call_id=call["call_id"], provider=call["provider"], model=call["model"], final_state=final_state)

    return {"final_state": final_state, "attempted": True}


def preflight_credentials() -> dict[str, Any]:
    script_id = google_clients.default_script_id()
    credentials = google_clients.load_credentials(False)
    google_clients.build_script_service(credentials, 300)
    return {"script_id": script_id, "credential_route_status": "READY"}


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
    run_id = "PPHB-R1-ATTENTION-EXECUTION-BATCH-001-" + ts.replace(":", "").replace("-", "") + "-" + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:12]
    return output_root / run_id


def initialize_run_files(run_dir: Path, batch_calls: list[dict[str, Any]], fingerprint_observations: Mapping[str, str], contract: Mapping[str, Any], source_sessions: Mapping[str, Any], source_members: Mapping[str, list[dict[str, Any]]]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    session_inventory = load_unique_session_inventory()
    batch_manifest = []
    for call in batch_calls:
        if call["source_session_id"] in source_sessions:
            session = source_sessions[call["source_session_id"]]
            members = source_members[call["source_session_id"]]
            input_identity = attention_input_identity(call, session, members, contract)
        else:
            session_meta = session_inventory.get(call["source_session_id"], {})
            input_identity = {
                "request_fingerprint": None,
                "session_snapshot_fingerprint": next(
                    iter(((session_meta.get("attention_input_source") or {}).get("prompt_fingerprints") or [])),
                    None,
                ),
                "input_cutoff": call.get("input_cutoff"),
                "member_count": None,
                "attention_input_artifact": call["attention_input_artifact"],
                "identity_status": "NOT_MATERIALIZED_DUE_TO_PRECALL_BLOCK",
            }
        batch_manifest.append(
            {
                "call_id": call["call_id"],
                "execution_order": call["execution_order"],
                "source_session_id": call["source_session_id"],
                "session_date": call["session_date"],
                "provider": call["provider"],
                "model": call["model"],
                "attention_input_identity": input_identity,
                "episode_ids": call["episode_ids"],
                "pre_execution_state": call["call_status"],
            }
        )
    manifest_path = run_dir / "batch_call_manifest.jsonl"
    if not manifest_path.exists():
        write_jsonl(manifest_path, batch_manifest)
    for name in (
        "operation_journal.jsonl",
        "raw_transport_results.jsonl",
        "raw_provider_outputs.jsonl",
        "normalized_attention_results.jsonl",
        "attention_validation_results.jsonl",
        "episode_attention_result_map.jsonl",
        "failed_call_ledger.jsonl",
    ):
        path = run_dir / name
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("")
    if not (run_dir / "run_manifest.json").exists():
        write_json(
            run_dir / "run_manifest.json",
            {
                "run_id": run_dir.name,
                "generated_at": now(),
                "git_head": git_head(),
                "governing_plan_id": PLAN_ID,
                "authorized_batch_id": BATCH_ID,
                "maximum_authorized_calls": EXPECTED_CALL_COUNT,
                "provider_calls_executed": 0,
                "forecast_calls_executed": 0,
                "pack_construction_executed": 0,
                "research_ai_calls": 0,
                "market_data_calls": 0,
                "web_calls": 0,
                "google_writes": 0,
                "predecessor_run_id": PREDECESSOR_RUN_ID,
                "predecessor_attempted_calls": PREDECESSOR_ATTEMPTED_CALLS,
                "rerun_reason": RERUN_REASON,
            },
        )
    if not (run_dir / "governing_artifact_manifest.json").exists():
        write_json(
            run_dir / "governing_artifact_manifest.json",
            {
                "governing_plan_root": path_ref(PLAN_ROOT),
                "verified_plan_fingerprints": dict(sorted(fingerprint_observations.items())),
            },
        )
    if not (run_dir / "batch_execution_contract.json").exists():
        write_json(
            run_dir / "batch_execution_contract.json",
            {
                "governing_plan_id": PLAN_ID,
                "authorized_batch_id": BATCH_ID,
                "authorized_call_count": EXPECTED_CALL_COUNT,
                "provider_models": PROVIDER_MODELS,
                "pre_call_journaling_required": True,
                "retry_policy": "no automatic retry for success or failure within Batch 001",
                "normalized_result_contract": "session_attention_map via binding.attention_parser plus strict member/rank validation",
                "duplicate_protection": "terminal call states in attention_validation_results.jsonl prevent repeat dispatch",
                "immutability_rule": "append-only run artifacts only; no matrix update in this Move",
            },
        )


def summarize_run(run_dir: Path, batch_calls: list[dict[str, Any]], blocked_reason: str | None = None) -> dict[str, Any]:
    validation_rows = read_jsonl(run_dir / "attention_validation_results.jsonl") if (run_dir / "attention_validation_results.jsonl").exists() else []
    normalized_rows = read_jsonl(run_dir / "normalized_attention_results.jsonl") if (run_dir / "normalized_attention_results.jsonl").exists() else []
    episode_map_rows = read_jsonl(run_dir / "episode_attention_result_map.jsonl") if (run_dir / "episode_attention_result_map.jsonl").exists() else []
    terminal_by_call = {row["call_id"]: row for row in validation_rows}
    attempted = sum(1 for row in validation_rows if row["final_state"] in TERMINAL_STATUSES)
    status_counts = Counter(row["final_state"] for row in validation_rows)
    skipped_success = sum(1 for row in read_jsonl(run_dir / "operation_journal.jsonl") if row.get("event") == "CALL_SKIPPED_ALREADY_SUCCEEDED") if (run_dir / "operation_journal.jsonl").exists() else 0
    by_provider = Counter(f"{row['provider']}|{row['model']}" for row in batch_calls)
    success_by_provider = Counter(f"{row['provider']}|{row['model']}" for row in validation_rows if row["final_state"] == "SUCCEEDED_VALID")
    failed_by_provider = Counter(f"{row['provider']}|{row['model']}" for row in validation_rows if row["final_state"] != "SUCCEEDED_VALID")
    sessions = sorted({row["source_session_id"] for row in batch_calls})
    episodes = sorted({episode_id for row in batch_calls for episode_id in row["episode_ids"]})
    failed_rows = read_jsonl(run_dir / "failed_call_ledger.jsonl") if (run_dir / "failed_call_ledger.jsonl").exists() else []
    reconciliation = {
        "authorized_calls": EXPECTED_CALL_COUNT,
        "attempted_calls": attempted,
        "successful_valid_calls": status_counts.get("SUCCEEDED_VALID", 0),
        "failed_transport_calls": status_counts.get("FAILED_TRANSPORT", 0),
        "failed_provider_calls": status_counts.get("FAILED_PROVIDER", 0),
        "failed_parse_calls": status_counts.get("FAILED_PARSE", 0),
        "failed_validation_calls": status_counts.get("FAILED_VALIDATION", 0),
        "skipped_already_successful_calls": skipped_success,
        "unexpected_calls": max(0, attempted - EXPECTED_CALL_COUNT),
        "duplicate_successful_calls": max(0, status_counts.get("SUCCEEDED_VALID", 0) - len(normalized_rows)),
        "sessions_represented": len(sessions),
        "episodes_served": len(episodes),
        "results_by_provider_model": dict(sorted(by_provider.items())),
        "successful_by_provider_model": dict(sorted(success_by_provider.items())),
        "failed_by_provider_model": dict(sorted(failed_by_provider.items())),
        "blocked_reason": blocked_reason,
    }
    write_json(run_dir / "batch_reconciliation.json", reconciliation)
    write_json(
        run_dir / "batch_summary.json",
        {
            **reconciliation,
            "normalized_result_count": len(normalized_rows),
            "episode_attention_result_map_count": len(episode_map_rows),
            "failed_call_ids": [row["call_id"] for row in failed_rows],
        },
    )
    return reconciliation


def execute_batch(
    *,
    output_root: Path = OUTPUT_ROOT,
    dispatcher: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    fixed_timestamp: str | None = None,
    resume_run_dir: Path | None = None,
    source_session_loader: Callable[[], tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]] | None = None,
) -> dict[str, Any]:
    plan_contract = load_plan_contract()
    contract = load_runtime_contract()
    fingerprint_observations = verify_plan_fingerprints()
    batch_calls = load_batch_calls(BATCH_ID)
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
                "execution_status": "ATTENTION_BATCH_001_BLOCKED",
                "contract_decision": "NO_LIVE_CONTRACT_EVIDENCE",
                "resume_decision": "RESUME_PROTECTION_VALIDATED",
                "scaling_decision": "REPAIR_BEFORE_FURTHER_BATCHES",
                "blocked_reason": blocked_reason,
                "credential_route_status": credential_status,
                "plan_contract_identity": plan_contract["attention_output_contract"]["object"],
                "runtime_contract_version": contract["contract_version"],
            }
            update_run_manifest(run_dir / "run_manifest.json", provider_calls_executed=0)
            write_json(run_dir / "batch_decision.json", decision)
            return {
                "run_dir": run_dir,
                "batch_calls": batch_calls,
                "decision": decision,
                "reconciliation": reconciliation,
            }

    loader = source_session_loader or read_source_sessions
    source_sessions, source_members = loader()
    for call in batch_calls:
        if call["source_session_id"] not in source_sessions:
            raise AttentionBatchError("SOURCE_SESSION_MISSING:" + call["source_session_id"])
    initialize_run_files(run_dir, batch_calls, fingerprint_observations, contract, source_sessions, source_members)
    journal_event(run_dir / "operation_journal.jsonl", "BATCH_STARTED", batch_id=BATCH_ID, authorized_calls=EXPECTED_CALL_COUNT)

    actual_dispatcher = dispatcher or live_dispatch
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
    )
    update_run_manifest(run_dir / "run_manifest.json", provider_calls_executed=reconciliation["attempted_calls"])
    if failures == 0:
        contract_decision = "ALL_BATCH_RESULTS_VALID"
        scaling_decision = "READY_FOR_REMAINING_ATTENTION_BATCHES"
    elif successful == 0:
        contract_decision = "LIVE_ATTENTION_CONTRACT_FAILURE"
        scaling_decision = "REPAIR_BEFORE_FURTHER_BATCHES"
    else:
        contract_decision = "VALID_RESULTS_WITH_FAILED_CALLS"
        scaling_decision = "RETRY_FAILED_BATCH_001_CALLS_REQUIRES_AUTHORIZATION"
    decision = {
        "execution_status": "ATTENTION_BATCH_001_COMPLETE" if successful == EXPECTED_CALL_COUNT else "ATTENTION_BATCH_001_PARTIALLY_COMPLETE",
        "contract_decision": contract_decision,
        "resume_decision": "RESUME_PROTECTION_VALIDATED",
        "scaling_decision": scaling_decision,
    }
    write_json(run_dir / "batch_decision.json", decision)
    return {
        "run_dir": run_dir,
        "batch_calls": batch_calls,
        "decision": decision,
        "reconciliation": reconciliation,
    }


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
