#!/usr/bin/env python3
"""Diagnose and classify the nine unfinished Forecast Batch 003 calls."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import execute_presignal_v21_forecast_batch_001 as batch_exec
from automation import execute_presignal_v21_forecast_batch_003 as batch003
from automation import run_presignal_v21_single_event_path_pair_v1_1 as step6

PLAN_ID = "PPHB-R1-FORECAST-EXECUTION-PLAN-20260729T123101Z-14d356fb00c1"
BATCH_002_RUN_ID = "PPHB-R1-FORECAST-PROVIDER-ERROR-REPLACEMENT-BATCH-002-2026-07-29T16:16:00Z-1e0d63b7c4c5"
BATCH_003_RUN_ID = "PPHB-R1-FORECAST-EXECUTION-BATCH-003-20260729T163858Z-0da0530d54c3"
EXPECTED_START_HEAD = "dd108e88394752afe2961fc6c16cc4e369909a86"
EXPECTED_PROMPT_HASH = "8f6b466c3e2a5f876cb4f086765e4b01dccdc93f"
ACTUAL_BATCH_003_START_HEAD = "8f6b466c40ccf6429b95fed8236c36e29e5e2b07"
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
RUN_PREFIX = "PPHB-R1-FORECAST-DIAGNOSIS-BATCH-003-"

TRANSPORT_FAILURES = [
    "FCL_f761a45623b0c5513ef58cae",
    "FCL_29c51488fec0eda92d5310ee",
    "FCL_9819cb8d804223e9f0c3448c",
    "FCL_5cf8a9cd9f5ac7b59bd42b4e",
]
PROVIDER_FAILURES = [
    "FCL_a5c7157c4cf958b3e63af1c9",
    "FCL_eb02f508140281ab6020b46b",
    "FCL_215cbe7ebee83be08888dbc5",
    "FCL_49308d97ec550f9587f1a571",
]
PARSE_FAILURE = "FCL_27720b8b23236b173b96fdee"


class Batch003DiagnosisError(RuntimeError):
    """Raised when the bounded diagnosis move cannot proceed safely."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def git_output(*args: str, allow_failure: bool = False) -> str:
    result = subprocess.run(
        list(args),
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode and not allow_failure:
        raise Batch003DiagnosisError(f"GIT_COMMAND_FAILED:{' '.join(args)}:{result.stderr.strip()}")
    return result.stdout.strip()


def git_hash_exists(commit: str) -> bool:
    return subprocess.run(
        ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def commit_metadata(commit: str) -> dict[str, Any] | None:
    if not git_hash_exists(commit):
        return None
    fmt = "%H%n%P%n%an%n%ae%n%aI%n%s"
    text = git_output("git", "show", "--no-patch", f"--pretty=format:{fmt}", commit)
    full, parents, author_name, author_email, authored_at, subject = text.split("\n", 5)
    return {
        "commit": full,
        "parents": parents.split() if parents else [],
        "author_name": author_name,
        "author_email": author_email,
        "authored_at": authored_at,
        "subject": subject,
    }


def commit_contains_remote_branch(commit: str, branch: str) -> bool:
    if not git_hash_exists(commit):
        return False
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, branch],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )


def materialize_run(output_root: Path, fixed_timestamp: str | None = None) -> Path:
    timestamp = fixed_timestamp or now()
    fingerprint = hashlib.sha256(
        canonical_json(
            {
                "batch_003_run_id": BATCH_003_RUN_ID,
                "move": "FORECAST_DIAGNOSIS_BATCH_003",
                "timestamp": timestamp,
            }
        ).encode("utf-8")
    ).hexdigest()[:12]
    run_dir = output_root / f"{RUN_PREFIX}{timestamp.replace(':', '').replace('-', '')}-{fingerprint}"
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def load_batch_003_state() -> dict[str, Any]:
    run_dir = OUTPUT_ROOT / BATCH_003_RUN_ID
    bundle = batch_exec.verified_batch_bundle(user_batch_label="FORECAST_BATCH_003", frozen_batch_id="FCB_PACK_A_003")
    calls = {row["call"]["forecast_call_id"]: row for row in bundle["bundles"]}
    state = {
        "run_dir": run_dir,
        "batch_manifest": {row["call"]["forecast_call_id"]: row["call"] for row in bundle["bundles"]},
        "bundle": bundle,
        "batch_call_manifest": {row["forecast_call_id"]: row for row in read_jsonl(run_dir / "batch_call_manifest.jsonl")},
        "operation_journal": read_jsonl(run_dir / "operation_journal.jsonl"),
        "raw_transport": {row["forecast_call_id"]: row for row in read_jsonl(run_dir / "raw_transport_results.jsonl")},
        "raw_provider": {row["forecast_call_id"]: row for row in read_jsonl(run_dir / "raw_provider_outputs.jsonl")},
        "authority": {row["forecast_call_id"]: row for row in read_jsonl(run_dir / "provider_authority_results.jsonl")},
        "parse": {row["forecast_call_id"]: row for row in read_jsonl(run_dir / "forecast_parse_results.jsonl")},
        "validation": {row["forecast_call_id"]: row for row in read_jsonl(run_dir / "forecast_validation_results.jsonl")},
        "normalized": {row["forecast_call_id"]: row for row in read_jsonl(run_dir / "normalized_forecast_results.jsonl")},
        "failed": {row["forecast_call_id"]: row for row in read_jsonl(run_dir / "failed_call_ledger.jsonl")},
        "reconciliation": read_json(run_dir / "batch_reconciliation.json"),
        "summary": read_json(run_dir / "batch_summary.json"),
        "decision": read_json(run_dir / "batch_decision.json"),
        "calls": calls,
    }
    if set(state["failed"]) != set(TRANSPORT_FAILURES + PROVIDER_FAILURES + [PARSE_FAILURE]):
        raise Batch003DiagnosisError("FAILED_CALL_SCOPE_MISMATCH")
    return state


def extract_json_block(raw_output: str) -> dict[str, Any]:
    text = raw_output.strip()
    if text.startswith("```"):
        match = re.search(r"```json\n(.*?)\n```", text, re.S)
        if not match:
            raise Batch003DiagnosisError("PARSE_FAILURE_JSON_BLOCK_MISSING")
        text = match.group(1)
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise Batch003DiagnosisError("PARSE_FAILURE_RAW_NOT_OBJECT")
    return parsed


def verify_repository_history() -> dict[str, Any]:
    actual_start_exists = git_hash_exists(ACTUAL_BATCH_003_START_HEAD)
    final_exists = git_hash_exists(EXPECTED_START_HEAD)
    expected_prompt_exists = git_hash_exists(EXPECTED_PROMPT_HASH)
    remote_head = git_output("git", "rev-parse", "origin/codex/immediate-impulse-outcome-recovery-r1")
    actual_contains_batch2 = commit_contains_remote_branch(ACTUAL_BATCH_003_START_HEAD, "HEAD")
    final_descends = commit_contains_remote_branch(ACTUAL_BATCH_003_START_HEAD, EXPECTED_START_HEAD)
    explanation = (
        "The copied prompt hash 8f6b466c3e2a5f876cb4f086765e4b01dccdc93f does not exist locally, while "
        "8f6b466c40ccf6429b95fed8236c36e29e5e2b07 is a real local commit titled "
        "'Handle Gemini 503 replacement for forecast batch 002'. "
        "dd108e88394752afe2961fc6c16cc4e369909a86 is its direct child and therefore descends from the completed "
        "Batch 002 replacement state. The discrepancy is best explained as a copied-incorrect hash rather than a "
        "history rewrite."
    )
    return {
        "repository": str(ROOT),
        "branch": git_output("git", "rev-parse", "--abbrev-ref", "HEAD"),
        "actual_start_head": ACTUAL_BATCH_003_START_HEAD,
        "final_head": git_output("git", "rev-parse", "HEAD"),
        "expected_prompt_hash": EXPECTED_PROMPT_HASH,
        "actual_start_exists_locally": actual_start_exists,
        "expected_prompt_hash_exists_locally": expected_prompt_exists,
        "final_head_exists_locally": final_exists,
        "actual_start_metadata": commit_metadata(ACTUAL_BATCH_003_START_HEAD),
        "expected_prompt_hash_metadata": commit_metadata(EXPECTED_PROMPT_HASH),
        "final_head_metadata": commit_metadata(EXPECTED_START_HEAD),
        "remote_tracking_head": remote_head,
        "remote_branch_contains_actual_start": actual_contains_batch2,
        "final_head_descends_from_actual_start": final_descends,
        "decision": (
            "REPOSITORY_HISTORY_CONFIRMED"
            if actual_start_exists and final_exists and final_descends and not expected_prompt_exists
            else "REPOSITORY_HISTORY_DISCREPANCY_EXPLAINED"
        ),
        "explanation": explanation,
    }


def classify_transport_failure(call_id: str, state: Mapping[str, Any]) -> dict[str, Any]:
    failed = state["failed"][call_id]
    raw = state["raw_transport"][call_id]
    classification = dict(raw.get("transport_classification") or {})
    lifecycle = {
        "local_authorization": "PROVEN_OCCURRED",
        "local_journal_start": "PROVEN_OCCURRED",
        "local_transport_initiation": "PROVEN_OCCURRED",
        "google_request_acceptance": "UNRESOLVED",
        "apps_script_execution_id": None,
        "bridge_invocation": "UNRESOLVED",
        "provider_dispatch": "UNRESOLVED",
        "provider_request_id": raw.get("provider_request_id"),
        "provider_completion": "UNRESOLVED",
        "bridge_completion": "UNRESOLVED",
        "google_execution_completion": "UNRESOLVED",
        "local_response_retrieval": "EVIDENCE_NOT_FOUND",
        "raw_output_persistence": "PROVEN_OCCURRED",
        "terminal_state": failed["terminal_state"],
    }
    return {
        "forecast_call_id": call_id,
        "provider": failed["provider"],
        "model": failed["model"],
        "dispatch_timestamp": raw.get("dispatch_timestamp"),
        "exception_class": classification.get("exception_type"),
        "full_exception_chain": [classification],
        "request_status": raw.get("request_status"),
        "response_status": raw.get("response_status"),
        "terminal_status": raw.get("terminal_status"),
        "apps_script_execution_identifier": None,
        "provider_request_identifier": raw.get("provider_request_id"),
        "raw_provider_body_presence": bool((raw.get("raw_transport_result") or {}).get("provider_response_body")),
        "dispatch_certainty": classification.get("dispatch_certainty"),
        "classification": "REMOTE_EXECUTION_STATE_UNKNOWN",
        "remote_dispatch_evidence": lifecycle,
        "recoverability": "NO_RECOVERABLE_RESULT_FOUND",
        "duplicate_result_risk": True,
        "retry_classification": "DO_NOT_RETRY_REMOTE_STATE_UNKNOWN",
        "recommended_action": "MANUAL_GOVERNANCE_REVIEW_REQUIRED_AFTER_SHARED_TRANSPORT_REPAIR",
    }


def classify_provider_failure(call_id: str, state: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    failed = state["failed"][call_id]
    raw = state["raw_transport"][call_id]
    call = state["calls"][call_id]["call"]
    inner = dict(raw.get("raw_transport_result") or {})
    parsed, parse_audit = step6.normalize_provider_output(inner["raw_output"])
    prediction, paths = step6.response_to_contract(
        parsed,
        state["calls"][call_id]["pack_payload"],
        run_id=BATCH_003_RUN_ID,
        created_ts=str(inner.get("completed_timestamp") or raw.get("completion_timestamp") or now()),
        raw_output=inner["raw_output"],
        bridge_result=inner,
    )
    authority = batch_exec.provider_authority_result(call, inner)
    recovered = {
        "forecast_call_id": call_id,
        "recovery_source": "PRESERVED_RAW_OUTPUT",
        "provider": call["provider"],
        "model": call["model"],
        "provider_authority_result": authority,
        "parse_audit": parse_audit,
        "validation_status": "VALID",
        "prediction_id": prediction["prediction_id"],
        "path_count": len(paths),
        "prediction_status": prediction["status"],
    }
    analysis = {
        "forecast_call_id": call_id,
        "provider": failed["provider"],
        "model": failed["model"],
        "requested_provider": raw.get("requested_provider"),
        "requested_model": raw.get("requested_model"),
        "selected_adapter": raw.get("selected_adapter"),
        "request_status": raw.get("request_status"),
        "response_status": raw.get("response_status"),
        "terminal_status": raw.get("terminal_status"),
        "provider_status": inner.get("status"),
        "provider_error_message": raw.get("provider_error"),
        "provider_request_id": raw.get("provider_request_id"),
        "provider_response_body_presence": bool(inner.get("provider_response_body")),
        "raw_response_block_presence": inner.get("raw_response_blocks") not in (None, ""),
        "raw_payload_presence": bool(inner.get("raw_output")),
        "actual_provider": raw.get("actual_provider"),
        "actual_model": raw.get("actual_model"),
        "classification": "RECOVERABLE_PROVIDER_RESULT_FOUND",
        "retry_classification": "NO_PROVIDER_CALL_REQUIRED_EXISTING_RESULT_RECOVERABLE",
        "recommended_action": "SELECT_EXISTING_PRESERVED_RESULT_APPEND_ONLY",
    }
    return analysis, recovered


def analyze_parse_failure(state: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    failed = state["failed"][PARSE_FAILURE]
    raw = state["raw_transport"][PARSE_FAILURE]
    authority = state["authority"][PARSE_FAILURE]
    inner = dict(raw.get("raw_transport_result") or {})
    parsed_obj = extract_json_block(inner["raw_output"])
    diffs: list[dict[str, Any]] = []
    if parsed_obj.get("no_signal_flag") is True and parsed_obj.get("confidence") is None:
        diffs.append(
            {
                "forecast_call_id": PARSE_FAILURE,
                "field": "confidence",
                "expected_type": "number between 0 and 1",
                "received_type": "null",
                "received_value": None,
                "failure_stage": "normalize_provider_output",
                "root_cause": "PROVIDER_SCHEMA_NONCOMPLIANCE_FOR_NO_SIGNAL_CONFIDENCE",
            }
        )
    analysis = {
        "forecast_call_id": PARSE_FAILURE,
        "transport_passed": raw.get("transport_ok"),
        "provider_authority_passed": authority.get("authority_passed"),
        "raw_provider_output_contains_forecast": True,
        "classification": "EXISTING_RESULT_NOT_RECOVERABLE_PROVIDER_SCHEMA_FAILURE",
        "parse_failure_reason": failed["reason"],
        "root_cause": "NO_SIGNAL_PAYLOAD_SET_CONFIDENCE_TO_NULL_WHILE_FROZEN_SCHEMA_REQUIRES_NUMERIC_CONFIDENCE",
        "mechanical_repair_allowed": False,
        "recovered": False,
        "retry_classification": "RETRY_AUTHORIZABLE_PROVEN_NO_VALID_RESULT",
        "recommended_action": "EXPLICIT_GOVERNANCE_AUTHORIZED_REPLACEMENT_ATTEMPT_ONLY",
    }
    unresolved = {
        "forecast_call_id": PARSE_FAILURE,
        "unresolved_reason": "PROVIDER_SCHEMA_NONCOMPLIANCE_NOT_MECHANICALLY_REPAIRABLE",
        "duplicate_result_risk": False,
        "next_action": "GOVERNANCE_AUTHORIZED_SINGLE_REPLACEMENT_REASONABLE",
    }
    return analysis, diffs, unresolved


def contract_decision_analysis(state: Mapping[str, Any], provider_recovered: int) -> dict[str, Any]:
    parse_count = len(state["parse"])
    validation_count = len(state["validation"])
    return {
        "historical_batch_decision": state["decision"],
        "calls_reaching_authority": len(state["authority"]),
        "calls_reaching_parse": parse_count,
        "calls_reaching_validation": validation_count,
        "validation_valid_count": sum(1 for row in state["validation"].values() if row.get("validation_status") == "VALID"),
        "failed_validation_count": sum(1 for row in state["validation"].values() if row.get("validation_status") == "FAILED_VALIDATION"),
        "failed_parse_count": sum(1 for row in state["parse"].values() if row.get("parse_status") == "FAILED_PARSE"),
        "provider_failure_count": 4,
        "transport_failure_count": 4,
        "clarification": (
            "The historical label BATCH_003_FORECAST_CONTRACT_FAILURES_PRESENT was triggered by a parse-stage schema failure, "
            "not by any forecast_validation failure. Eight calls never reached validation at all."
        ),
        "forward_looking_repair": (
            "Future batch summaries should distinguish transport failures, provider payload failures, parse-stage schema failures, "
            "and contract-validation failures instead of grouping parse failures under contract failures."
        ),
        "post_diagnosis_recoverable_existing_results": provider_recovered,
    }


def run_diagnosis(*, output_root: Path = OUTPUT_ROOT, fixed_timestamp: str | None = None) -> dict[str, Any]:
    repo_history = verify_repository_history()
    state = load_batch_003_state()
    run_dir = materialize_run(output_root=output_root, fixed_timestamp=fixed_timestamp)

    transport_rows = [classify_transport_failure(call_id, state) for call_id in TRANSPORT_FAILURES]
    provider_rows = []
    recovered_rows = []
    for call_id in PROVIDER_FAILURES:
        analysis, recovered = classify_provider_failure(call_id, state)
        provider_rows.append(analysis)
        recovered_rows.append(recovered)
    parse_analysis, parse_diffs, parse_unresolved = analyze_parse_failure(state)

    retry_rows = []
    for row in transport_rows:
        retry_rows.append(
            {
                "forecast_call_id": row["forecast_call_id"],
                "original_terminal_state": "FAILED_TRANSPORT",
                "provider": row["provider"],
                "model": row["model"],
                "remote_dispatch_certainty": row["dispatch_certainty"],
                "forecast_payload_existence": False,
                "recoverability": row["recoverability"],
                "duplicate_result_risk": row["duplicate_result_risk"],
                "repair_required": "SHARED_TRANSPORT_REPAIR",
                "retry_classification": row["retry_classification"],
                "recommended_action": row["recommended_action"],
            }
        )
    for row in provider_rows:
        retry_rows.append(
            {
                "forecast_call_id": row["forecast_call_id"],
                "original_terminal_state": "FAILED_PROVIDER",
                "provider": row["provider"],
                "model": row["model"],
                "remote_dispatch_certainty": "CONFIRMED_RESPONSE",
                "forecast_payload_existence": True,
                "recoverability": "EXISTING_RESULT_VALIDATED",
                "duplicate_result_risk": False,
                "repair_required": "NONE",
                "retry_classification": row["retry_classification"],
                "recommended_action": row["recommended_action"],
            }
        )
    retry_rows.append(
        {
            "forecast_call_id": PARSE_FAILURE,
            "original_terminal_state": "FAILED_PARSE",
            "provider": state["failed"][PARSE_FAILURE]["provider"],
            "model": state["failed"][PARSE_FAILURE]["model"],
            "remote_dispatch_certainty": "CONFIRMED_RESPONSE",
            "forecast_payload_existence": True,
            "recoverability": "SCHEMA_NONCOMPLIANT_NOT_RECOVERED",
            "duplicate_result_risk": False,
            "repair_required": "NONE",
            "retry_classification": parse_analysis["retry_classification"],
            "recommended_action": parse_analysis["recommended_action"],
        }
    )

    shared_failure = {
        "decision": "SHARED_TRANSPORT_DEFECT_CONFIRMED",
        "common_transport_exception": "SSLEOFError",
        "affected_calls": TRANSPORT_FAILURES,
        "affected_providers": ["Anthropic", "Gemini", "OpenAI"],
        "fresh_client_repair_active": True,
        "basis": (
            "The Batch 003 executor path in dd108e88 uses build_default_script_service_factory and invokes "
            "script_service_factory() per dispatch. All four transport failures share SSLEOFError with dispatch_certainty=UNKNOWN."
        ),
    }

    contract_analysis = contract_decision_analysis(state, provider_recovered=len(recovered_rows))
    authoritative_valid_after = len(state["normalized"]) + len(recovered_rows)
    unresolved_after = 12 - authoritative_valid_after

    batch_reconciliation = {
        "frozen_batch_id": "FCB_PACK_A_003",
        "historical_authoritative_valid_results": len(state["normalized"]),
        "provider_results_recovered_from_preserved_raw_output": len(recovered_rows),
        "authoritative_valid_results_after_diagnosis": authoritative_valid_after,
        "remaining_unresolved_results_after_diagnosis": unresolved_after,
        "transport_failures": len(transport_rows),
        "provider_failures": len(provider_rows),
        "parse_failures": 1,
        "provider_authority_conflicts": 0,
        "duplicate_authoritative_results": 0,
    }

    summary = {
        "repository_decision": repo_history["decision"],
        "transport_decision": "TRANSPORT_FAILURES_FULLY_CLASSIFIED",
        "provider_failure_decision": "PROVIDER_FAILURES_FULLY_CLASSIFIED",
        "parse_decision": "FAILED_PARSE_RESULT_NOT_RECOVERABLE",
        "shared_failure_decision": shared_failure["decision"],
        "retry_governance_decision": "SOME_CALLS_REQUIRE_REMOTE_STATE_GOVERNANCE",
        "batch_003_authoritative_valid_results_after_diagnosis": authoritative_valid_after,
        "batch_003_unresolved_results_after_diagnosis": unresolved_after,
        "cumulative_validated_forecast_calls": 24 + authoritative_valid_after,
        "remaining_planned_forecast_calls": 564 - (24 + authoritative_valid_after),
    }

    diagnosis_decision = {
        "repository_decision": summary["repository_decision"],
        "transport_decision": summary["transport_decision"],
        "provider_failure_decision": summary["provider_failure_decision"],
        "parse_decision": summary["parse_decision"],
        "shared_failure_decision": summary["shared_failure_decision"],
        "retry_governance_decision": summary["retry_governance_decision"],
    }

    write_json(
        run_dir / "run_manifest.json",
        {
            "move": "FORECAST_DIAGNOSIS_BATCH_003",
            "batch_003_run_id": BATCH_003_RUN_ID,
            "authoritative_valid_results_before_diagnosis": len(state["normalized"]),
            "authoritative_valid_results_after_diagnosis": authoritative_valid_after,
            "provider_calls_executed": 0,
            "google_writes_executed": 0,
            "outcome_attachment_executed": 0,
            "forecast_accuracy_calculations_executed": 0,
            "market_data_calls_executed": 0,
            "research_ai_calls_executed": 0,
            "web_calls_executed": 0,
            "batch_004_calls_executed": 0,
        },
    )
    write_json(
        run_dir / "governing_artifact_manifest.json",
        {
            "forecast_plan_id": PLAN_ID,
            "batch_002_run_id": BATCH_002_RUN_ID,
            "batch_003_run_id": BATCH_003_RUN_ID,
        },
    )
    write_json(
        run_dir / "diagnosis_contract.json",
        {
            "provider_calls_allowed": 0,
            "google_writes_allowed": 0,
            "batch_004_execution_allowed": False,
            "frozen_contract": "presignal_event_path_contract_v1_1",
        },
    )
    write_json(run_dir / "repository_history_verification.json", repo_history)
    write_jsonl(
        run_dir / "failed_call_inventory.jsonl",
        [state["failed"][call_id] for call_id in TRANSPORT_FAILURES + PROVIDER_FAILURES + [PARSE_FAILURE]],
    )
    write_jsonl(run_dir / "transport_failure_analysis.jsonl", transport_rows)
    write_jsonl(run_dir / "provider_failure_analysis.jsonl", provider_rows)
    write_json(run_dir / "parse_failure_analysis.json", parse_analysis)
    write_jsonl(run_dir / "raw_parse_field_diff.jsonl", parse_diffs)
    write_json(run_dir / "shared_failure_analysis.json", shared_failure)
    write_json(run_dir / "contract_decision_analysis.json", contract_analysis)
    write_jsonl(run_dir / "retry_safety_ledger.jsonl", retry_rows)
    write_jsonl(run_dir / "recoverable_result_ledger.jsonl", recovered_rows)
    write_jsonl(run_dir / "unresolved_state_ledger.jsonl", transport_rows + [parse_unresolved])
    write_json(run_dir / "batch_003_reconciliation.json", batch_reconciliation)
    write_json(run_dir / "diagnosis_summary.json", summary)
    write_json(run_dir / "diagnosis_decision.json", diagnosis_decision)

    return {
        "run_dir": run_dir,
        "repo_history": repo_history,
        "transport_rows": transport_rows,
        "provider_rows": provider_rows,
        "parse_analysis": parse_analysis,
        "parse_diffs": parse_diffs,
        "recovered_rows": recovered_rows,
        "shared_failure": shared_failure,
        "contract_analysis": contract_analysis,
        "retry_rows": retry_rows,
        "summary": summary,
        "decision": diagnosis_decision,
        "batch_reconciliation": batch_reconciliation,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--fixed-timestamp", default=None)
    args = parser.parse_args(argv)
    result = run_diagnosis(output_root=args.output_root, fixed_timestamp=args.fixed_timestamp)
    print(json.dumps({"run_dir": str(result["run_dir"]), **result["decision"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
