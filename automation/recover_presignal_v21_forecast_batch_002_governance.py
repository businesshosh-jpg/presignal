#!/usr/bin/env python3
"""Governance-authorized single recovery of frozen forecast Batch 002."""
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

from automation import execute_presignal_v21_forecast_batch_001 as batch_exec
from automation import final_verify_presignal_v21_forecast_batch_002_unknown_states as final_verify
from automation import repair_presignal_v21_forecast_transport_batch_002 as transport_repair
from automation import resolve_presignal_v21_forecast_batch_002_unknown_states as unknown_state
from automation import run_presignal_v21_single_event_path_pair_v1_1 as step6

PLAN_ID = batch_exec.PLAN_ID
OUTPUT_ROOT = batch_exec.OUTPUT_ROOT
EXPECTED_START_HEAD = "6266981b24231bfeb29b4067b6590525671b55a6"
USER_BATCH_LABEL = "FORECAST_BATCH_002"
FROZEN_BATCH_ID = "FCB_PACK_A_002"
FAILED_BATCH_002_ID = "PPHB-R1-FORECAST-EXECUTION-BATCH-002-20260729T133420Z-0469b99f5e03"
TRANSPORT_REPAIR_ID = "PPHB-R1-FORECAST-TRANSPORT-REPAIR-BATCH-002-20260729T145855Z-14b086004306"
UNKNOWN_STATE_RESOLUTION_ID = "PPHB-R1-FORECAST-UNKNOWN-STATE-RESOLUTION-BATCH-002-20260729T151816Z-f0c7e40b79bb"
FINAL_EXISTENCE_ID = "PPHB-R1-FORECAST-FINAL-EXISTENCE-VERIFICATION-BATCH-002-20260729T154300Z-38ed7431cd9f"
RUN_PREFIX = "PPHB-R1-FORECAST-GOVERNANCE-RECOVERY-BATCH-002-"
UNKNOWN_STATE_CALL_IDS = tuple(final_verify.UNKNOWN_CALL_IDS)
CONFIRMED_NOT_SENT_CALL_IDS = (
    "FCL_1e7b6936b48bf931a7ed5e7d",
    "FCL_64c262f5f677009a4ce5c45a",
)
TERMINAL_STATES = {
    "SUCCEEDED_VALID",
    "FAILED_TRANSPORT",
    "FAILED_PROVIDER",
    "FAILED_PROVIDER_AUTHORITY",
    "FAILED_PARSE",
    "FAILED_VALIDATION",
    "SKIPPED_VALID_RESULT_DISCOVERED",
}


class GovernanceRecoveryError(RuntimeError):
    """The governance-authorized recovery failed closed."""


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temp, path)


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text("".join(canonical_json(dict(row)) + "\n" for row in rows))
    os.replace(temp, path)


def append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(canonical_json(dict(row)) + "\n")


def git_head() -> str:
    return batch_exec.git_head()


def git_branch() -> str:
    return batch_exec.git_branch()


def is_descendant_of(commit: str) -> bool:
    return batch_exec.is_descendant_of(commit)


def materialize_run(output_root: Path, fixed_timestamp: str | None = None) -> Path:
    timestamp = fixed_timestamp or now()
    seed = {
        "plan_id": PLAN_ID,
        "frozen_batch_id": FROZEN_BATCH_ID,
        "governance_authorization": FINAL_EXISTENCE_ID,
        "timestamp": timestamp,
    }
    run_id = RUN_PREFIX + timestamp.replace(":", "").replace("-", "") + "-" + hashlib.sha256(
        canonical_json(seed).encode("utf-8")
    ).hexdigest()[:12]
    return output_root / run_id


def category_map(bundle: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    all_ids = [row["call"]["forecast_call_id"] for row in bundle["bundles"]]
    first_attempt_ids = [call_id for call_id in all_ids if call_id not in set(UNKNOWN_STATE_CALL_IDS) | set(CONFIRMED_NOT_SENT_CALL_IDS)]
    if len(first_attempt_ids) != 7:
        raise GovernanceRecoveryError("FIRST_ATTEMPT_COUNT_MISMATCH")
    mapping: dict[str, dict[str, Any]] = {}
    for call_id in UNKNOWN_STATE_CALL_IDS:
        mapping[call_id] = {
            "attempt_category": "GOVERNANCE_AUTHORIZED_UNKNOWN_STATE_RECOVERY",
            "original_attempt_state": "REMOTE_EXECUTION_STATE_UNRESOLVED",
            "recovery_authorization": "USER_AUTHORIZED_SINGLE_RECOVERY",
            "duplicate_execution_risk": "ACKNOWLEDGED",
            "maximum_allowed_attempts": 1,
            "original_attempt_reference": {
                "failed_batch_002_id": FAILED_BATCH_002_ID,
                "transport_repair_id": TRANSPORT_REPAIR_ID,
                "unknown_state_resolution_id": UNKNOWN_STATE_RESOLUTION_ID,
                "final_existence_verification_id": FINAL_EXISTENCE_ID,
            },
        }
    for call_id in CONFIRMED_NOT_SENT_CALL_IDS:
        mapping[call_id] = {
            "attempt_category": "CONFIRMED_NOT_SENT_RETRY",
            "original_dispatch_state": "CONFIRMED_NOT_SENT",
            "retry_authorization": "RETRY_AUTHORIZABLE_PROVEN_NO_VALID_RESULT",
            "duplicate_execution_risk": "NONE_CONFIRMED_NOT_SENT",
            "maximum_allowed_attempts": 1,
            "original_attempt_reference": {
                "failed_batch_002_id": FAILED_BATCH_002_ID,
                "transport_repair_id": TRANSPORT_REPAIR_ID,
            },
        }
    for call_id in first_attempt_ids:
        mapping[call_id] = {
            "attempt_category": "FIRST_ATTEMPT",
            "maximum_allowed_attempts": 1,
            "original_attempt_reference": None,
            "duplicate_execution_risk": "NONE_NOT_PREVIOUSLY_DISPATCHED",
        }
    if set(mapping) != set(all_ids):
        raise GovernanceRecoveryError("ATTEMPT_CATEGORY_MAP_INCOMPLETE")
    return mapping


def initialize_run(run_dir: Path, bundle: Mapping[str, Any], repo_state: Mapping[str, Any], auth_result: Mapping[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        run_dir / "run_manifest.json",
        {
            "move": "FORECAST_GOVERNANCE_RECOVERY_BATCH_002",
            "plan_id": PLAN_ID,
            "user_batch_label": USER_BATCH_LABEL,
            "frozen_batch_id": FROZEN_BATCH_ID,
            "pack_type": bundle["pack_type"],
            "authorized_call_count": 12,
            "maximum_provider_calls": 12,
            "branch": repo_state["branch"],
            "start_head": repo_state["head"],
            "expected_start_head": EXPECTED_START_HEAD,
            "google_preflight": auth_result,
            "provider_calls_executed": 0,
            "google_writes_executed": 0,
            "market_data_calls_executed": 0,
            "research_ai_calls_executed": 0,
            "web_calls_executed": 0,
            "outcome_attachment_executed": 0,
            "matrix_updates_executed": 0,
            "forecast_accuracy_calculations_executed": 0,
            "consensus_or_ranking_executed": 0,
        },
    )
    write_json(
        run_dir / "governing_artifact_manifest.json",
        {
            "forecast_plan_id": PLAN_ID,
            "failed_batch_002_id": FAILED_BATCH_002_ID,
            "transport_repair_id": TRANSPORT_REPAIR_ID,
            "unknown_state_resolution_id": UNKNOWN_STATE_RESOLUTION_ID,
            "final_existence_verification_id": FINAL_EXISTENCE_ID,
            "forecast_execution_contract": str((batch_exec.PLAN_ROOT / "forecast_execution_contract.json").relative_to(ROOT)),
            "provider_model_contract": str((batch_exec.PLAN_ROOT / "provider_model_contract.json").relative_to(ROOT)),
            "historical_leakage_control_contract": str((batch_exec.PLAN_ROOT / "historical_leakage_control_contract.json").relative_to(ROOT)),
        },
    )
    write_json(
        run_dir / "governance_authorization.json",
        {
            "authorization_source": FINAL_EXISTENCE_ID,
            "authorized_unknown_state_calls": list(UNKNOWN_STATE_CALL_IDS),
            "authorized_confirmed_not_sent_retries": list(CONFIRMED_NOT_SENT_CALL_IDS),
            "authorized_first_attempt_calls": [
                row["call"]["forecast_call_id"]
                for row in bundle["bundles"]
                if row["call"]["forecast_call_id"] not in set(UNKNOWN_STATE_CALL_IDS) | set(CONFIRMED_NOT_SENT_CALL_IDS)
            ],
            "duplicate_execution_risk_acknowledged": True,
            "maximum_recovery_attempts_per_call": 1,
            "maximum_retry_attempts_per_call": 1,
        },
    )
    write_json(
        run_dir / "recovery_execution_contract.json",
        {
            "allowed_terminal_states": sorted(TERMINAL_STATES),
            "provider_authority_rule": read_json(batch_exec.PLAN_ROOT / "provider_model_contract.json")["provider_authority_rule"],
            "forecast_contract": read_json(batch_exec.PLAN_ROOT / "forecast_execution_contract.json"),
            "historical_leakage_control_contract": read_json(batch_exec.PLAN_ROOT / "historical_leakage_control_contract.json"),
            "fresh_apps_script_client_per_dispatch": True,
            "apps_script_timeout_seconds": batch_exec.SCRIPT_HTTP_TIMEOUT_SECONDS,
            "bridge_hard_timeout_seconds": 180,
            "no_automatic_retry": True,
            "no_batch_003_execution": True,
        },
    )
    write_jsonl(run_dir / "batch_call_manifest.jsonl", [row["call"] for row in bundle["bundles"]])
    for name in (
        "attempt_category_ledger.jsonl",
        "operation_journal.jsonl",
        "raw_transport_results.jsonl",
        "raw_provider_outputs.jsonl",
        "provider_authority_results.jsonl",
        "forecast_parse_results.jsonl",
        "forecast_validation_results.jsonl",
        "normalized_forecast_results.jsonl",
        "duplicate_risk_lineage.jsonl",
        "authoritative_result_selection.jsonl",
        "failed_call_ledger.jsonl",
    ):
        (run_dir / name).write_text("")


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


def leakage_audit_result(bundle: Mapping[str, Any]) -> dict[str, Any]:
    rows = []
    for row in bundle["bundles"]:
        audit = batch_exec.leakage_audit(row["prompt_row"]["prompt_text"], row["prompt_row"]["prompt_payload"], row["call"]["pack_type"])
        rows.append({"forecast_call_id": row["call"]["forecast_call_id"], "passed": audit["passed"], "violations": audit["violations"]})
        if not audit["passed"]:
            raise GovernanceRecoveryError("HISTORICAL_LEAKAGE_DETECTED:" + row["call"]["forecast_call_id"])
    return {"decision": "NO_HISTORICAL_LEAKAGE_DETECTED", "rows": rows}


def default_dispatch(script_service: Any, script_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    return batch_exec.default_dispatch(script_service, script_id, payload)


def load_transport_retry_safety() -> dict[str, dict[str, Any]]:
    rows = read_jsonl(OUTPUT_ROOT / TRANSPORT_REPAIR_ID / "retry_safety_ledger.jsonl")
    return {row["forecast_call_id"]: row for row in rows}


def authoritative_selection_row(
    *,
    call: Mapping[str, Any],
    attempt_meta: Mapping[str, Any],
    terminal_state: str,
    run_dir: Path,
) -> dict[str, Any]:
    if terminal_state == "SUCCEEDED_VALID":
        if attempt_meta["attempt_category"] == "GOVERNANCE_AUTHORIZED_UNKNOWN_STATE_RECOVERY":
            reason = "NO_RECOVERABLE_ORIGINAL_RESULT_FOUND_AND_SINGLE_RECOVERY_WAS_EXPLICITLY_AUTHORIZED"
        elif attempt_meta["attempt_category"] == "CONFIRMED_NOT_SENT_RETRY":
            reason = "ORIGINAL_DISPATCH_CONFIRMED_NOT_SENT_AND_SINGLE_RETRY_AUTHORIZED"
        else:
            reason = "FIRST_SUCCESSFUL_FROZEN_ATTEMPT"
        return {
            "forecast_call_id": call["forecast_call_id"],
            "selected_result_run_id": run_dir.name,
            "selected_terminal_state": terminal_state,
            "authoritative_result": "RECOVERY_RESULT",
            "authority_reason": reason,
            "original_attempt_reference": attempt_meta.get("original_attempt_reference"),
        }
    return {
        "forecast_call_id": call["forecast_call_id"],
        "selected_result_run_id": None,
        "selected_terminal_state": terminal_state,
        "authoritative_result": "NO_VALID_RESULT_SELECTED",
        "authority_reason": "NO_CONTRACT_VALID_RESULT_AVAILABLE",
        "original_attempt_reference": attempt_meta.get("original_attempt_reference"),
    }


def execute_recovery(
    *,
    output_root: Path = OUTPUT_ROOT,
    fixed_timestamp: str | None = None,
    enforce_head: bool = True,
    auth_preflight: Callable[[], Mapping[str, Any]] = batch_exec.verify_google_preflight,
    dispatch: Callable[[Any, str, Mapping[str, Any]], Mapping[str, Any]] = default_dispatch,
) -> dict[str, Any]:
    branch = git_branch()
    head = git_head()
    if branch != "codex/immediate-impulse-outcome-recovery-r1":
        raise GovernanceRecoveryError("BRANCH_MISMATCH")
    if enforce_head and head != EXPECTED_START_HEAD and not is_descendant_of(EXPECTED_START_HEAD):
        raise GovernanceRecoveryError("HEAD_ANCESTRY_NOT_CLEAN")
    repo_state = {
        "branch": branch,
        "head": head,
        "expected_head_matched": head == EXPECTED_START_HEAD,
        "clean_descendant_of_expected_head": is_descendant_of(EXPECTED_START_HEAD),
    }

    bundle = batch_exec.verified_batch_bundle(user_batch_label=USER_BATCH_LABEL, frozen_batch_id=FROZEN_BATCH_ID)
    if bundle["pack_type"] != "PACK_A":
        raise GovernanceRecoveryError("PACK_TYPE_MISMATCH")
    leakage = leakage_audit_result(bundle)
    auth_result = dict(auth_preflight())
    run_dir = materialize_run(output_root, fixed_timestamp=fixed_timestamp)
    initialize_run(run_dir, bundle, repo_state, auth_result)
    attempt_categories = category_map(bundle)
    transport_retry_safety = load_transport_retry_safety()
    script_service_factory, script_id = batch_exec.build_default_script_service_factory()

    dispatched_this_move: set[str] = set()
    call_results: list[dict[str, Any]] = []
    duplicate_lineage_rows: list[dict[str, Any]] = []
    authoritative_rows: list[dict[str, Any]] = []

    for row in bundle["bundles"]:
        call = row["call"]
        prompt_row = row["prompt_row"]
        prompt_fingerprint = row["prompt_fingerprint"]
        pack_payload = row["pack_payload"]
        call_id = call["forecast_call_id"]
        attempt_meta = dict(attempt_categories[call_id])
        attempt_meta.update(
            {
                "forecast_call_id": call_id,
                "episode_id": call["episode_id"],
                "provider": call["provider"],
                "model": call["model"],
                "pack_type": call["pack_type"],
                "remaining_allowed_attempts_before_dispatch": 1,
                "governance_authorization_reference": FINAL_EXISTENCE_ID if call_id in UNKNOWN_STATE_CALL_IDS else None,
            }
        )
        append_jsonl(run_dir / "attempt_category_ledger.jsonl", attempt_meta)

        if call_id in dispatched_this_move:
            raise GovernanceRecoveryError("CALL_ALREADY_DISPATCHED_IN_MOVE:" + call_id)
        if attempt_meta["maximum_allowed_attempts"] != 1 or attempt_meta["remaining_allowed_attempts_before_dispatch"] != 1:
            raise GovernanceRecoveryError("ATTEMPT_LIMIT_VIOLATION:" + call_id)

        current_auth = dict(auth_preflight())
        existing_valid = find_existing_valid_result(call_id, output_root)
        if existing_valid is not None:
            skipped = {
                "forecast_call_id": call_id,
                "episode_id": call["episode_id"],
                "provider": call["provider"],
                "model": call["model"],
                "pack_type": call["pack_type"],
                "terminal_state": "SKIPPED_VALID_RESULT_DISCOVERED",
                "reason": "VALID_RESULT_DISCOVERED_BEFORE_RECOVERY_DISPATCH",
            }
            append_jsonl(run_dir / "operation_journal.jsonl", {"event": "SKIPPED_VALID_RESULT_DISCOVERED", **skipped})
            append_jsonl(
                run_dir / "authoritative_result_selection.jsonl",
                {
                    "forecast_call_id": call_id,
                    "selected_result_run_id": existing_valid.get("prediction", {}).get("run_id"),
                    "selected_terminal_state": "SUCCEEDED_VALID",
                    "authoritative_result": "PREEXISTING_VALID_RESULT",
                    "authority_reason": "VALID_RESULT_DISCOVERED_BEFORE_RECOVERY_DISPATCH",
                    "original_attempt_reference": attempt_meta.get("original_attempt_reference"),
                },
            )
            call_results.append(skipped)
            raise GovernanceRecoveryError("VALID_RESULT_DISCOVERED_BEFORE_DISPATCH:" + call_id)

        append_jsonl(
            run_dir / "operation_journal.jsonl",
            {
                "event": "CALL_STARTED",
                "forecast_call_id": call_id,
                "batch_id": FROZEN_BATCH_ID,
                "user_batch_label": USER_BATCH_LABEL,
                "execution_order": call["execution_order"],
                "attempt_number": 1,
                "attempt_category": attempt_meta["attempt_category"],
                "provider": call["provider"],
                "model": call["model"],
                "source_session_id": call["source_session_id"],
                "episode_id": call["episode_id"],
                "pack_type": call["pack_type"],
                "pack_row_fingerprint": call["pack_row_fingerprint"],
                "prompt_text_fingerprint": prompt_fingerprint["prompt_text_fingerprint"],
                "started_at": now(),
                "state": "CALL_STARTED",
            },
        )

        arm = "BASELINE"
        payload = step6.bridge_payload(pack_payload, prompt_row["prompt_text"], run_id=run_dir.name, arm=arm)
        transport_meta = dispatch(script_service_factory(), script_id, payload)
        dispatched_this_move.add(call_id)
        transport_result = transport_meta.get("result") if isinstance(transport_meta, Mapping) else None
        raw_output = transport_result.get("raw_output") if isinstance(transport_result, Mapping) else None
        raw_claimed_provider = None

        raw_transport_row = {
            "forecast_call_id": call_id,
            "attempt_category": attempt_meta["attempt_category"],
            "original_attempt_reference": attempt_meta.get("original_attempt_reference"),
            "governance_authorization_reference": attempt_meta.get("governance_authorization_reference"),
            "dispatch_timestamp": now(),
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
            "response_length": len(raw_output) if isinstance(raw_output, str) else None,
            "completion_timestamp": transport_result.get("completed_timestamp") if isinstance(transport_result, Mapping) else None,
            "pack_row_fingerprint": call["pack_row_fingerprint"],
            "prompt_fingerprint": prompt_fingerprint["prompt_text_fingerprint"],
            "google_preflight_result": current_auth["read_only_preflight_result"],
        }
        append_jsonl(run_dir / "raw_transport_results.jsonl", raw_transport_row)
        append_jsonl(
            run_dir / "raw_provider_outputs.jsonl",
            {
                "forecast_call_id": call_id,
                "attempt_category": attempt_meta["attempt_category"],
                "original_attempt_reference": attempt_meta.get("original_attempt_reference"),
                "governance_authorization_reference": attempt_meta.get("governance_authorization_reference"),
                "episode_id": call["episode_id"],
                "provider": call["provider"],
                "model": call["model"],
                "pack_type": call["pack_type"],
                "pack_row_fingerprint": call["pack_row_fingerprint"],
                "prompt_fingerprint": prompt_fingerprint["prompt_text_fingerprint"],
                "raw_provider_output": raw_output,
            },
        )
        duplicate_lineage_rows.append(
            {
                "forecast_call_id": call_id,
                "attempt_category": attempt_meta["attempt_category"],
                "original_attempt_reference": attempt_meta.get("original_attempt_reference"),
                "recovery_attempt_run_id": run_dir.name,
                "recovery_attempt_dispatched": True,
                "duplicate_execution_risk": attempt_meta["duplicate_execution_risk"],
                "governance_authorization_reference": attempt_meta.get("governance_authorization_reference"),
            }
        )

        if not transport_meta.get("ok") or not isinstance(transport_result, Mapping):
            terminal_state = batch_exec.classify_transport_failure(transport_result if isinstance(transport_result, Mapping) else None)
            failed_row = {
                "forecast_call_id": call_id,
                "episode_id": call["episode_id"],
                "provider": call["provider"],
                "model": call["model"],
                "pack_type": call["pack_type"],
                "attempt_category": attempt_meta["attempt_category"],
                "terminal_state": terminal_state,
                "reason": transport_meta.get("classification", {}).get("category", "TRANSPORT_NOT_OK"),
            }
            append_jsonl(run_dir / "failed_call_ledger.jsonl", failed_row)
            append_jsonl(run_dir / "operation_journal.jsonl", {"event": terminal_state, **failed_row})
            selection = authoritative_selection_row(call=call, attempt_meta=attempt_meta, terminal_state=terminal_state, run_dir=run_dir)
            authoritative_rows.append(selection)
            append_jsonl(run_dir / "authoritative_result_selection.jsonl", selection)
            call_results.append(failed_row)
            continue

        status = str(transport_result.get("status") or "")
        if status in batch_exec.PROVIDER_FAILURE_STATUSES:
            authority_row = batch_exec.provider_authority_result(call, transport_result) | {"attempt_category": attempt_meta["attempt_category"]}
            append_jsonl(run_dir / "provider_authority_results.jsonl", authority_row)
            failed_row = {
                "forecast_call_id": call_id,
                "episode_id": call["episode_id"],
                "provider": call["provider"],
                "model": call["model"],
                "pack_type": call["pack_type"],
                "attempt_category": attempt_meta["attempt_category"],
                "terminal_state": "FAILED_PROVIDER",
                "reason": status,
            }
            append_jsonl(run_dir / "failed_call_ledger.jsonl", failed_row)
            append_jsonl(run_dir / "operation_journal.jsonl", {"event": "FAILED_PROVIDER", **failed_row})
            selection = authoritative_selection_row(call=call, attempt_meta=attempt_meta, terminal_state="FAILED_PROVIDER", run_dir=run_dir)
            authoritative_rows.append(selection)
            append_jsonl(run_dir / "authoritative_result_selection.jsonl", selection)
            call_results.append(failed_row)
            continue

        authority = batch_exec.provider_authority_result(call, transport_result) | {"attempt_category": attempt_meta["attempt_category"]}
        append_jsonl(run_dir / "provider_authority_results.jsonl", authority)
        if not authority["authority_passed"]:
            failed_row = {
                "forecast_call_id": call_id,
                "episode_id": call["episode_id"],
                "provider": call["provider"],
                "model": call["model"],
                "pack_type": call["pack_type"],
                "attempt_category": attempt_meta["attempt_category"],
                "terminal_state": "FAILED_PROVIDER_AUTHORITY",
                "reason": authority["reason"],
            }
            append_jsonl(run_dir / "failed_call_ledger.jsonl", failed_row)
            append_jsonl(run_dir / "operation_journal.jsonl", {"event": "FAILED_PROVIDER_AUTHORITY", **failed_row})
            selection = authoritative_selection_row(call=call, attempt_meta=attempt_meta, terminal_state="FAILED_PROVIDER_AUTHORITY", run_dir=run_dir)
            authoritative_rows.append(selection)
            append_jsonl(run_dir / "authoritative_result_selection.jsonl", selection)
            call_results.append(failed_row)
            continue

        try:
            parsed, parse_audit = step6.normalize_provider_output(raw_output)
            if isinstance(parsed, Mapping):
                raw_claimed_provider = parsed.get("provider")
            append_jsonl(
                run_dir / "forecast_parse_results.jsonl",
                {
                    "forecast_call_id": call_id,
                    "attempt_category": attempt_meta["attempt_category"],
                    "parse_status": "PARSED",
                    "raw_claimed_provider": raw_claimed_provider,
                    "parse_audit": parse_audit,
                },
            )
        except Exception as exc:
            failed_row = {
                "forecast_call_id": call_id,
                "episode_id": call["episode_id"],
                "provider": call["provider"],
                "model": call["model"],
                "pack_type": call["pack_type"],
                "attempt_category": attempt_meta["attempt_category"],
                "terminal_state": "FAILED_PARSE",
                "reason": str(exc),
            }
            append_jsonl(
                run_dir / "forecast_parse_results.jsonl",
                {
                    "forecast_call_id": call_id,
                    "attempt_category": attempt_meta["attempt_category"],
                    "parse_status": "FAILED_PARSE",
                    "raw_claimed_provider": raw_claimed_provider,
                    "reason": str(exc),
                },
            )
            append_jsonl(run_dir / "failed_call_ledger.jsonl", failed_row)
            append_jsonl(run_dir / "operation_journal.jsonl", {"event": "FAILED_PARSE", **failed_row})
            selection = authoritative_selection_row(call=call, attempt_meta=attempt_meta, terminal_state="FAILED_PARSE", run_dir=run_dir)
            authoritative_rows.append(selection)
            append_jsonl(run_dir / "authoritative_result_selection.jsonl", selection)
            call_results.append(failed_row)
            continue

        try:
            prediction, paths = step6.response_to_contract(
                parsed,
                pack_payload,
                run_id=run_dir.name,
                created_ts=str(transport_result.get("completed_timestamp") or now()),
                raw_output=raw_output,
                bridge_result=transport_result,
            )
            normalized_row = {
                "forecast_call_id": call_id,
                "episode_id": call["episode_id"],
                "provider": call["provider"],
                "model": call["model"],
                "pack_type": call["pack_type"],
                "attempt_category": attempt_meta["attempt_category"],
                "pack_row_identity": call["pack_row_identity"],
                "pack_row_fingerprint": call["pack_row_fingerprint"],
                "prompt_text_fingerprint": prompt_fingerprint["prompt_text_fingerprint"],
                "prompt_context_fingerprint": prompt_fingerprint["prompt_context_fingerprint"],
                "terminal_state": "SUCCEEDED_VALID",
                "raw_claimed_provider": raw_claimed_provider,
                "governance_authorization_reference": attempt_meta.get("governance_authorization_reference"),
                "original_attempt_reference": attempt_meta.get("original_attempt_reference"),
                "prediction": prediction,
                "paths": paths,
            }
            append_jsonl(
                run_dir / "forecast_validation_results.jsonl",
                {
                    "forecast_call_id": call_id,
                    "attempt_category": attempt_meta["attempt_category"],
                    "validation_status": "VALID",
                    "prediction_id": prediction["prediction_id"],
                    "path_count": len(paths),
                },
            )
            append_jsonl(run_dir / "normalized_forecast_results.jsonl", normalized_row)
            append_jsonl(
                run_dir / "operation_journal.jsonl",
                {
                    "event": "SUCCEEDED_VALID",
                    "forecast_call_id": call_id,
                    "attempt_category": attempt_meta["attempt_category"],
                    "prediction_id": prediction["prediction_id"],
                    "pack_type": call["pack_type"],
                },
            )
            selection = authoritative_selection_row(call=call, attempt_meta=attempt_meta, terminal_state="SUCCEEDED_VALID", run_dir=run_dir)
            authoritative_rows.append(selection)
            append_jsonl(run_dir / "authoritative_result_selection.jsonl", selection)
            call_results.append(
                {
                    "forecast_call_id": call_id,
                    "episode_id": call["episode_id"],
                    "provider": call["provider"],
                    "model": call["model"],
                    "pack_type": call["pack_type"],
                    "attempt_category": attempt_meta["attempt_category"],
                    "terminal_state": "SUCCEEDED_VALID",
                    "raw_claimed_provider": raw_claimed_provider,
                }
            )
        except Exception as exc:
            failed_row = {
                "forecast_call_id": call_id,
                "episode_id": call["episode_id"],
                "provider": call["provider"],
                "model": call["model"],
                "pack_type": call["pack_type"],
                "attempt_category": attempt_meta["attempt_category"],
                "terminal_state": "FAILED_VALIDATION",
                "reason": str(exc),
                "raw_claimed_provider": raw_claimed_provider,
            }
            append_jsonl(
                run_dir / "forecast_validation_results.jsonl",
                {
                    "forecast_call_id": call_id,
                    "attempt_category": attempt_meta["attempt_category"],
                    "validation_status": "FAILED_VALIDATION",
                    "reason": str(exc),
                },
            )
            append_jsonl(run_dir / "failed_call_ledger.jsonl", failed_row)
            append_jsonl(run_dir / "operation_journal.jsonl", {"event": "FAILED_VALIDATION", **failed_row})
            selection = authoritative_selection_row(call=call, attempt_meta=attempt_meta, terminal_state="FAILED_VALIDATION", run_dir=run_dir)
            authoritative_rows.append(selection)
            append_jsonl(run_dir / "authoritative_result_selection.jsonl", selection)
            call_results.append(failed_row)

    write_jsonl(run_dir / "duplicate_risk_lineage.jsonl", duplicate_lineage_rows)
    terminal_counts = Counter(row["terminal_state"] for row in call_results)
    authority_rows = read_jsonl(run_dir / "provider_authority_results.jsonl")
    agreements = sum(1 for row in authority_rows if row.get("authority_passed"))
    conflicts = sum(1 for row in authority_rows if not row.get("authority_passed"))
    normalized_rows = read_jsonl(run_dir / "normalized_forecast_results.jsonl")
    failed_rows = read_jsonl(run_dir / "failed_call_ledger.jsonl")
    provider_model_results = dict(Counter(f"{row['provider']}|{row['model']}|{row['terminal_state']}" for row in call_results))
    unknown_rows = [row for row in call_results if row["attempt_category"] == "GOVERNANCE_AUTHORIZED_UNKNOWN_STATE_RECOVERY"]
    retry_rows = [row for row in call_results if row["attempt_category"] == "CONFIRMED_NOT_SENT_RETRY"]
    first_attempt_rows = [row for row in call_results if row["attempt_category"] == "FIRST_ATTEMPT"]
    cumulative_validated = len(batch_exec.load_validated_call_ids(output_root))
    reconciliation = {
        "authorized_calls": 12,
        "attempted_provider_calls": sum(1 for row in call_results if row["terminal_state"] != "SKIPPED_VALID_RESULT_DISCOVERED"),
        "successful_valid_calls": terminal_counts["SUCCEEDED_VALID"],
        "failed_transport_calls": terminal_counts["FAILED_TRANSPORT"],
        "failed_provider_calls": terminal_counts["FAILED_PROVIDER"],
        "failed_provider_authority_calls": terminal_counts["FAILED_PROVIDER_AUTHORITY"],
        "failed_parse_calls": terminal_counts["FAILED_PARSE"],
        "failed_validation_calls": terminal_counts["FAILED_VALIDATION"],
        "skipped_valid_result_discovered_calls": terminal_counts["SKIPPED_VALID_RESULT_DISCOVERED"],
        "results_by_provider_model": provider_model_results,
        "manifest_transport_agreements": agreements,
        "manifest_transport_conflicts": conflicts,
        "leakage_control_result": leakage["decision"],
        "raw_output_preservation_result": "PRESERVED_BEFORE_PARSE_FOR_ALL_DISPATCHED_CALLS",
        "duplicate_risk_lineage_result": "PRESERVED",
        "three_unknown_state_recovery_results": unknown_rows,
        "two_confirmed_not_sent_retry_results": retry_rows,
        "seven_first_attempt_results": first_attempt_rows,
        "exact_failed_calls": failed_rows,
        "cumulative_validated_forecast_calls": cumulative_validated,
        "remaining_planned_forecast_calls": 564 - cumulative_validated,
    }
    write_json(run_dir / "batch_reconciliation.json", reconciliation)
    write_json(run_dir / "batch_summary.json", reconciliation)

    if terminal_counts["SKIPPED_VALID_RESULT_DISCOVERED"]:
        recovery_status = "BATCH_002_GOVERNANCE_RECOVERY_BLOCKED"
        duplicate_decision = "DUPLICATE_RESULT_DISCOVERED_RECONCILIATION_REQUIRED"
        contract_decision = "RECOVERED_FORECAST_CONTRACT_NOT_REACHED"
        provider_decision = "RECOVERED_PROVIDER_AUTHORITY_NOT_REACHED"
        resume_decision = "BATCH_002_GOVERNANCE_RECONCILIATION_REQUIRED"
        next_phase = "GOVERNANCE_REVIEW_REQUIRED"
    elif any(terminal_counts[state] for state in ("FAILED_TRANSPORT", "FAILED_PROVIDER", "FAILED_PROVIDER_AUTHORITY", "FAILED_PARSE", "FAILED_VALIDATION")):
        recovery_status = "BATCH_002_GOVERNANCE_RECOVERY_PARTIALLY_COMPLETE"
        duplicate_decision = "DUPLICATE_RISK_ACCEPTED_AND_LINEAGE_PRESERVED"
        contract_decision = (
            "RECOVERED_FORECAST_CONTRACT_FAILURES_PRESENT"
            if terminal_counts["FAILED_PARSE"] or terminal_counts["FAILED_VALIDATION"]
            else "ALL_RECOVERED_FORECAST_RESULTS_CONTRACT_VALID"
        )
        provider_decision = (
            "RECOVERED_PROVIDER_AUTHORITY_FAILURES_PRESENT"
            if terminal_counts["FAILED_PROVIDER_AUTHORITY"]
            else "ALL_RECOVERED_PROVIDER_IDENTITIES_AUTHORITATIVELY_BOUND"
        )
        resume_decision = "BATCH_002_REMAINS_INCOMPLETE"
        next_phase = "REPAIR_BEFORE_FORECAST_BATCH_003"
    else:
        recovery_status = "BATCH_002_GOVERNANCE_RECOVERY_COMPLETE"
        duplicate_decision = "DUPLICATE_RISK_ACCEPTED_AND_LINEAGE_PRESERVED"
        contract_decision = "ALL_RECOVERED_FORECAST_RESULTS_CONTRACT_VALID"
        provider_decision = "ALL_RECOVERED_PROVIDER_IDENTITIES_AUTHORITATIVELY_BOUND"
        resume_decision = "BATCH_002_COMPLETE_READY_FOR_BATCH_003"
        next_phase = "READY_TO_EXECUTE_FORECAST_BATCH_003"
    decision = {
        "recovery_status": recovery_status,
        "duplicate_risk_decision": duplicate_decision,
        "contract_decision": contract_decision,
        "provider_authority_decision": provider_decision,
        "resume_decision": resume_decision,
        "next_phase_decision": next_phase,
    }
    write_json(run_dir / "batch_decision.json", decision)
    batch_exec.update_run_manifest(
        run_dir / "run_manifest.json",
        provider_calls_executed=reconciliation["attempted_provider_calls"],
        successful_valid_calls=reconciliation["successful_valid_calls"],
        failed_transport_calls=reconciliation["failed_transport_calls"],
        failed_provider_calls=reconciliation["failed_provider_calls"],
        failed_provider_authority_calls=reconciliation["failed_provider_authority_calls"],
        failed_parse_calls=reconciliation["failed_parse_calls"],
        failed_validation_calls=reconciliation["failed_validation_calls"],
        skipped_valid_result_discovered_calls=reconciliation["skipped_valid_result_discovered_calls"],
        normalized_result_count=len(normalized_rows),
    )
    return {
        "run_dir": run_dir,
        "repo_state": repo_state,
        "auth_result": auth_result,
        "reconciliation": reconciliation,
        "decision": decision,
        "attempt_categories": attempt_categories,
        "duplicate_lineage_rows": duplicate_lineage_rows,
        "authoritative_rows": authoritative_rows,
        "leakage": leakage,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--fixed-timestamp", default=None)
    parser.add_argument("--skip-head-check", action="store_true")
    args = parser.parse_args(argv)
    result = execute_recovery(
        output_root=args.output_root,
        fixed_timestamp=args.fixed_timestamp,
        enforce_head=not args.skip_head_check,
    )
    print(json.dumps({"run_dir": str(result["run_dir"]), **result["decision"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
