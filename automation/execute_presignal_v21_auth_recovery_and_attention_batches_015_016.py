#!/usr/bin/env python3
"""Verify Google auth recovery, then resume ATTN_BATCH_015 and ATTN_BATCH_016."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import execute_presignal_v21_attention_batches_015_016 as coordinator
from automation import google_clients

OUTPUT_ROOT = coordinator.OUTPUT_ROOT
PLAN_ID = coordinator.PLAN_ID
TOKEN_PATH = Path("/Users/junhoshino/projects/presignal/local/token.json")
BLOCKED_COORDINATION_ID = "PPHB-R1-ATTENTION-EXECUTION-BATCHES-015-016-20260729T090318Z-9e64f5d6f733"
BLOCKED_BATCH_015_ID = "PPHB-R1-ATTENTION-EXECUTION-BATCH-015-20260729T090319Z-a624a4386240"


def canonical_json(value: Any) -> str:
    return coordinator.batch015.batch004.canonical_json(value)


def now() -> str:
    return coordinator.batch015.batch004.now()


def write_json(path: Path, value: Any) -> None:
    coordinator.batch015.batch004.write_json(path, value)


def materialize_run(output_root: Path, fixed_timestamp: str | None = None) -> Path:
    ts = fixed_timestamp or now()
    seed = {"plan_id": PLAN_ID, "move": "ATTENTION_AUTH_RECOVERY_BATCHES_015_016", "timestamp": ts}
    run_id = (
        "PPHB-R1-ATTENTION-AUTH-RECOVERY-AND-BATCHES-015-016-"
        + ts.replace(":", "").replace("-", "")
        + "-"
        + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:12]
    )
    return output_root / run_id


def verify_authentication() -> dict[str, Any]:
    os_env = str(TOKEN_PATH)
    if not TOKEN_PATH.exists():
        return {
            "authentication_decision": "GOOGLE_AUTHENTICATION_STILL_BLOCKED",
            "token_path": os_env,
            "token_path_external": True,
            "scope_names": list(google_clients.SCOPES),
            "scope_verification_result": "TOKEN_PATH_MISSING",
            "read_only_preflight_result": "FAILED",
            "resource_identity_result": "NOT_REACHED",
            "error": "TOKEN_PATH_MISSING",
            "google_writes": 0,
        }

    if str(TOKEN_PATH.resolve()).startswith(str(ROOT)):
        return {
            "authentication_decision": "GOOGLE_AUTHENTICATION_STILL_BLOCKED",
            "token_path": os_env,
            "token_path_external": False,
            "scope_names": list(google_clients.SCOPES),
            "scope_verification_result": "FAILED_TOKEN_INSIDE_REPOSITORY",
            "read_only_preflight_result": "FAILED",
            "resource_identity_result": "NOT_REACHED",
            "error": "TOKEN_PATH_RESOLVED_INSIDE_REPOSITORY",
            "google_writes": 0,
        }

    try:
        credentials = google_clients.load_credentials(False, token_path=TOKEN_PATH)
        existing_scopes = sorted(credentials.scopes or [])
        missing = [scope for scope in google_clients.SCOPES if scope not in set(existing_scopes)]
        if missing:
            return {
                "authentication_decision": "GOOGLE_AUTHENTICATION_STILL_BLOCKED",
                "token_path": os_env,
                "token_path_external": True,
                "authentication_method": "existing_external_token",
                "scope_names": existing_scopes,
                "scope_verification_result": "FAILED_MISSING_SCOPES",
                "missing_scopes": missing,
                "read_only_preflight_result": "FAILED",
                "resource_identity_result": "NOT_REACHED",
                "error": "REQUIRED_SCOPES_MISSING",
                "google_writes": 0,
            }
        script_id = google_clients.default_script_id()
        sheets = google_clients.build_sheets_service(credentials)
        script = google_clients.build_script_service(credentials, 300)
        spreadsheet = (
            sheets.spreadsheets()
            .get(
                spreadsheetId=google_clients.DEFAULT_SPREADSHEET_ID,
                fields="spreadsheetId,properties.title",
            )
            .execute()
        )
        content = script.projects().getContent(scriptId=script_id).execute()
        files = content.get("files", [])
        if spreadsheet.get("spreadsheetId") != google_clients.DEFAULT_SPREADSHEET_ID:
            return {
                "authentication_decision": "GOOGLE_RESOURCE_IDENTITY_MISMATCH",
                "token_path": os_env,
                "token_path_external": True,
                "authentication_method": "existing_external_token",
                "scope_names": existing_scopes,
                "scope_verification_result": "PASSED",
                "read_only_preflight_result": "PASSED",
                "resource_identity_result": "SPREADSHEET_ID_MISMATCH",
                "expected_spreadsheet_id": google_clients.DEFAULT_SPREADSHEET_ID,
                "observed_spreadsheet_id": spreadsheet.get("spreadsheetId"),
                "expected_script_id": script_id,
                "observed_script_id": script_id,
                "google_writes": 0,
            }
        return {
            "authentication_decision": "GOOGLE_AUTHENTICATION_RECOVERED",
            "token_path": os_env,
            "token_path_external": True,
            "authentication_method": "existing_external_token",
            "scope_names": existing_scopes,
            "scope_verification_result": "PASSED",
            "read_only_preflight_result": "PASSED",
            "resource_identity_result": "PASSED",
            "spreadsheet_id": spreadsheet["spreadsheetId"],
            "spreadsheet_title": spreadsheet["properties"]["title"],
            "script_id": script_id,
            "script_file_count": len(files),
            "google_writes": 0,
        }
    except Exception as exc:
        return {
            "authentication_decision": "GOOGLE_AUTHENTICATION_STILL_BLOCKED",
            "token_path": os_env,
            "token_path_external": True,
            "authentication_method": "existing_external_token",
            "scope_names": list(google_clients.SCOPES),
            "scope_verification_result": "FAILED_DURING_LOAD_OR_PRECHECK",
            "read_only_preflight_result": "FAILED",
            "resource_identity_result": "NOT_REACHED",
            "error": str(exc),
            "google_writes": 0,
        }


def initialize_run(run_dir: Path, auth_result: Mapping[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        run_dir / "run_manifest.json",
        {
            "move": "ATTENTION_AUTH_RECOVERY_BATCHES_015_016",
            "plan_id": PLAN_ID,
            "blocked_coordination_run_id": BLOCKED_COORDINATION_ID,
            "blocked_batch_015_run_id": BLOCKED_BATCH_015_ID,
            "authorized_batches": ["ATTN_BATCH_015", "ATTN_BATCH_016"],
            "maximum_authorized_calls": 24,
            "authentication_decision": auth_result["authentication_decision"],
        },
    )
    write_json(
        run_dir / "governing_artifact_manifest.json",
        {
            "plan_id": PLAN_ID,
            "blocked_coordination_run_id": BLOCKED_COORDINATION_ID,
            "blocked_batch_015_run_id": BLOCKED_BATCH_015_ID,
            "batch_015_expected_start_head": coordinator.batch015.EXPECTED_START_HEAD,
            "batch_016_expected_start_head": coordinator.batch016.EXPECTED_START_HEAD,
        },
    )
    write_json(
        run_dir / "authentication_recovery_ledger.json",
        {
            "blocked_run_ids": [BLOCKED_COORDINATION_ID, BLOCKED_BATCH_015_ID],
            "token_path": auth_result["token_path"],
            "token_path_external": auth_result["token_path_external"],
            "authentication_method": auth_result.get("authentication_method", "not_recovered"),
            "scope_names": auth_result["scope_names"],
            "scope_verification_result": auth_result["scope_verification_result"],
            "google_writes": 0,
        },
    )
    write_json(run_dir / "authentication_preflight_result.json", dict(auth_result))
    write_json(
        run_dir / "authorized_batch_manifest.json",
        {
            "authorized_batches": [
                {"batch_id": "ATTN_BATCH_015", "authorized_calls": 12, "call_ids": [row["call_id"] for row in coordinator.batch015.load_batch_calls()]},
                {"batch_id": "ATTN_BATCH_016", "authorized_calls": 12, "call_ids": [row["call_id"] for row in coordinator.batch016.load_batch_calls()]},
            ],
            "maximum_total_calls": 24,
        },
    )


def execute_move(*, output_root: Path = OUTPUT_ROOT, fixed_timestamp: str | None = None, enforce_head: bool = True) -> dict[str, Any]:
    auth_result = verify_authentication()
    run_dir = materialize_run(output_root=output_root, fixed_timestamp=fixed_timestamp)
    initialize_run(run_dir, auth_result)

    if auth_result["authentication_decision"] != "GOOGLE_AUTHENTICATION_RECOVERED":
        write_json(run_dir / "batch_015_result_reference.json", {"executed": False, "reason": auth_result["authentication_decision"]})
        write_json(run_dir / "continuation_gate_decision.json", {"continuation_decision": "STOP_BEFORE_ATTENTION_BATCH_016_SHARED_FAILURE", "evidence": "AUTHENTICATION_NOT_RECOVERED"})
        write_json(run_dir / "batch_016_result_reference.json", {"executed": False, "reason": auth_result["authentication_decision"]})
        move_reconciliation = {
            "authorized_batches": 2,
            "executed_batches": 0,
            "total_authorized_calls": 24,
            "total_attempted_provider_calls": 0,
            "total_successful_valid_calls": 0,
            "total_skipped_already_successful_calls": 0,
            "total_unexpected_calls": 0,
            "total_duplicate_successful_calls": 0,
            "continuation_gate_result": "STOP_BEFORE_ATTENTION_BATCH_016_SHARED_FAILURE",
            "batch_015_decision": "ATTENTION_BATCH_015_BLOCKED",
            "batch_016_decision": "ATTENTION_BATCH_016_NOT_EXECUTED",
            "cumulative_validated_attention_calls": 168,
            "remaining_attention_calls": 36,
            "failed_transport_calls": 0,
            "failed_provider_calls": 0,
            "failed_provider_authority_calls": 0,
            "failed_parse_calls": 0,
            "failed_completeness_calls": 0,
            "failed_validation_calls": 0,
        }
        write_json(run_dir / "move_reconciliation.json", move_reconciliation)
        write_json(run_dir / "move_summary.json", move_reconciliation)
        write_json(
            run_dir / "move_decision.json",
            {
                "authentication_decision": auth_result["authentication_decision"],
                "move_status": "ATTENTION_BATCHES_015_016_AUTHENTICATION_BLOCKED",
                "scaling_decision": "REPAIR_BEFORE_FURTHER_ATTENTION_EXECUTION",
            },
        )
        return {"run_dir": run_dir, "auth_result": auth_result, "coordinator_result": None}

    coordinator_result = coordinator.execute_move(
        output_root=output_root,
        batch_output_root=output_root,
        fixed_timestamp=fixed_timestamp,
        enforce_head=enforce_head,
    )
    write_json(
        run_dir / "batch_015_result_reference.json",
        {"run_dir": str(coordinator_result["batch_015"]["run_dir"]), "decision": coordinator_result["batch_015"]["decision"], "reconciliation": coordinator_result["batch_015"]["reconciliation"]},
    )
    write_json(
        run_dir / "continuation_gate_decision.json",
        {"continuation_decision": coordinator_result["continuation_gate"], "evidence": coordinator_result["continuation_evidence"]},
    )
    batch_016 = coordinator_result["batch_016"]
    if batch_016 is not None:
        write_json(
            run_dir / "batch_016_result_reference.json",
            {"run_dir": str(batch_016["run_dir"]), "decision": batch_016["decision"], "reconciliation": batch_016["reconciliation"]},
        )
    else:
        write_json(run_dir / "batch_016_result_reference.json", {"executed": False, "reason": coordinator_result["continuation_gate"]})
    write_json(run_dir / "move_reconciliation.json", coordinator_result["move_reconciliation"])
    write_json(run_dir / "move_summary.json", coordinator_result["move_reconciliation"])
    write_json(
        run_dir / "move_decision.json",
        {
            "authentication_decision": auth_result["authentication_decision"],
            "move_status": coordinator_result["move_decision"]["move_status"],
            "scaling_decision": coordinator_result["move_decision"]["scaling_decision"],
            "underlying_execution_coordination_run": str(coordinator_result["run_dir"]),
        },
    )
    return {"run_dir": run_dir, "auth_result": auth_result, "coordinator_result": coordinator_result}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--fixed-timestamp")
    args = parser.parse_args(argv)
    result = execute_move(output_root=args.output_root, fixed_timestamp=args.fixed_timestamp)
    move_decision = coordinator.batch015.batch004.read_json(result["run_dir"] / "move_decision.json")
    move_reconciliation = coordinator.batch015.batch004.read_json(result["run_dir"] / "move_reconciliation.json")
    print(
        json.dumps(
            {
                "run_dir": str(result["run_dir"]),
                "authentication_decision": result["auth_result"]["authentication_decision"],
                "move_status": move_decision["move_status"],
                "total_attempted_provider_calls": move_reconciliation["total_attempted_provider_calls"],
                "total_successful_valid_calls": move_reconciliation["total_successful_valid_calls"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
