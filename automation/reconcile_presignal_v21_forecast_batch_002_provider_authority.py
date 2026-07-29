"""Reconcile the single remaining Batch 002 provider-authority failure.

This move is read-only with respect to providers and Google. It inspects the
preserved Batch 002 governance-recovery evidence for one failed call and
determines whether the existing result can be authoritatively reconciled
without dispatching a replacement call.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
PLAN_ID = "PPHB-R1-FORECAST-EXECUTION-PLAN-20260729T123101Z-14d356fb00c1"
FAILED_BATCH_ID = "PPHB-R1-FORECAST-EXECUTION-BATCH-002-20260729T133420Z-0469b99f5e03"
TRANSPORT_REPAIR_ID = "PPHB-R1-FORECAST-TRANSPORT-REPAIR-BATCH-002-20260729T145855Z-14b086004306"
FINAL_VERIFICATION_ID = "PPHB-R1-FORECAST-FINAL-EXISTENCE-VERIFICATION-BATCH-002-20260729T154300Z-38ed7431cd9f"
GOVERNANCE_RECOVERY_ID = "PPHB-R1-FORECAST-GOVERNANCE-RECOVERY-BATCH-002-20260729T155711Z-d5eb5c6e23c3"
EXPECTED_START_HEAD = "8a7cfcecc9fd2f56e864db48e283b915bf855977"
USER_BATCH_LABEL = "FORECAST_BATCH_002"
FROZEN_BATCH_ID = "FCB_PACK_A_002"
FORECAST_CONTRACT = "presignal_event_path_contract_v1_1"
CALL_ID = "FCL_ff54346ab7650976cfdf2a77"
EXPECTED_PROVIDER = "Gemini"
EXPECTED_MODEL = "gemini-2.5-flash-lite"
BRIDGE_FUNCTION = "apiCallAuthoritativeProviderJsonObject"
RUN_PREFIX = "PPHB-R1-FORECAST-PROVIDER-AUTHORITY-RECONCILIATION-BATCH-002-"

EXACT_PROVIDER_ALIASES = {
    "Gemini": {"Gemini", "Google"},
    "Anthropic": {"Anthropic"},
    "OpenAI": {"OpenAI"},
}


class ProviderAuthorityReconciliationError(RuntimeError):
    """Raised when the bounded reconciliation cannot proceed safely."""


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


def find_row(rows: Iterable[Mapping[str, Any]], key: str, value: str) -> dict[str, Any] | None:
    for row in rows:
        if str(row.get(key)) == value:
            return dict(row)
    return None


def load_call_evidence() -> dict[str, Any]:
    run_dir = OUTPUT_ROOT / GOVERNANCE_RECOVERY_ID
    rows = {
        "batch_call_manifest": read_jsonl(run_dir / "batch_call_manifest.jsonl"),
        "attempt_category": read_jsonl(run_dir / "attempt_category_ledger.jsonl"),
        "operation_journal": read_jsonl(run_dir / "operation_journal.jsonl"),
        "raw_transport": read_jsonl(run_dir / "raw_transport_results.jsonl"),
        "raw_provider": read_jsonl(run_dir / "raw_provider_outputs.jsonl"),
        "provider_authority": read_jsonl(run_dir / "provider_authority_results.jsonl"),
        "forecast_parse": read_jsonl(run_dir / "forecast_parse_results.jsonl"),
        "forecast_validation": read_jsonl(run_dir / "forecast_validation_results.jsonl"),
        "normalized_forecast": read_jsonl(run_dir / "normalized_forecast_results.jsonl"),
        "failed_call": read_jsonl(run_dir / "failed_call_ledger.jsonl"),
    }
    return {
        "run_dir": run_dir,
        "call": find_row(rows["batch_call_manifest"], "forecast_call_id", CALL_ID),
        "attempt_category": find_row(rows["attempt_category"], "forecast_call_id", CALL_ID),
        "operation_journal": [row for row in rows["operation_journal"] if str(row.get("forecast_call_id")) == CALL_ID],
        "raw_transport": find_row(rows["raw_transport"], "forecast_call_id", CALL_ID),
        "raw_provider": find_row(rows["raw_provider"], "forecast_call_id", CALL_ID),
        "provider_authority": find_row(rows["provider_authority"], "forecast_call_id", CALL_ID),
        "forecast_parse": find_row(rows["forecast_parse"], "forecast_call_id", CALL_ID),
        "forecast_validation": find_row(rows["forecast_validation"], "forecast_call_id", CALL_ID),
        "normalized_forecast": find_row(rows["normalized_forecast"], "forecast_call_id", CALL_ID),
        "failed_call": find_row(rows["failed_call"], "forecast_call_id", CALL_ID),
        "batch_reconciliation": read_json(run_dir / "batch_reconciliation.json"),
        "batch_summary": read_json(run_dir / "batch_summary.json"),
    }


def exact_alias(provider: str, candidate: str | None) -> str | None:
    if candidate is None:
        return None
    normalized = str(candidate).strip()
    if not normalized:
        return None
    aliases = EXACT_PROVIDER_ALIASES.get(provider, set())
    if normalized in aliases:
        return provider
    return None


def classify_mismatch(evidence: Mapping[str, Any]) -> dict[str, Any]:
    call = dict(evidence["call"] or {})
    transport_row = dict(evidence["raw_transport"] or {})
    raw_transport = dict(transport_row.get("raw_transport_result") or {})
    transport_request = dict(transport_row.get("transport_request") or {})
    request_payloads = list(transport_request.get("parameters") or [])
    request_payload = dict(request_payloads[0]) if request_payloads else {}
    authority_row = dict(evidence["provider_authority"] or {})

    manifest_provider = str(call.get("provider") or "")
    manifest_model = str(call.get("model") or "")
    actual_provider = str(authority_row.get("actual_provider") or "")
    actual_model = str(authority_row.get("actual_model") or "")
    requested_provider = str(raw_transport.get("requested_provider") or request_payload.get("provider") or "")
    requested_model = str(raw_transport.get("requested_model") or request_payload.get("model") or "")
    route_function = str(transport_request.get("function") or "")
    provider_error = str(raw_transport.get("error") or "")
    provider_field = str(raw_transport.get("provider") or "")
    model_field = str(raw_transport.get("model") or "")

    exact_provider_from_alias = exact_alias(manifest_provider, actual_provider) if actual_provider else None

    if actual_provider and not exact_provider_from_alias:
        return {
            "classification": "TRANSPORT_PROVIDER_LABEL_NORMALIZATION_DEFECT",
            "explanation": "Transport preserved a provider label that is not equal to the manifest label but may require an exact deterministic alias.",
            "independently_proves_provider": False,
            "independently_proves_model": bool(actual_model),
        }
    if actual_provider and exact_provider_from_alias == manifest_provider and actual_model and actual_model != manifest_model:
        return {
            "classification": "TRANSPORT_MODEL_LABEL_NORMALIZATION_DEFECT",
            "explanation": "Transport preserved provider identity but model identity differs from the manifest-bound model.",
            "independently_proves_provider": True,
            "independently_proves_model": False,
        }
    if not actual_provider and not actual_model:
        if route_function == BRIDGE_FUNCTION and requested_provider == manifest_provider and requested_model == manifest_model:
            return {
                "classification": "MISSING_AUTHORITATIVE_TRANSPORT_IDENTITY",
                "explanation": (
                    "The bridge request targeted the frozen Gemini route and frozen model, and the bridge returned a provider-specific "
                    "error string, but the error path preserved empty actual_provider and actual_model."
                ),
                "independently_proves_provider": "Gemini" in provider_error or provider_field == manifest_provider,
                "independently_proves_model": False,
            }
        return {
            "classification": "UNRESOLVED_PROVIDER_AUTHORITY_FAILURE",
            "explanation": "The preserved transport row does not independently preserve authoritative provider/model identity.",
            "independently_proves_provider": False,
            "independently_proves_model": False,
        }
    if actual_provider and actual_provider != manifest_provider:
        return {
            "classification": "MANIFEST_PROVIDER_CONFLICT",
            "explanation": "Transport preserved a concrete provider identity that conflicts with the frozen manifest provider.",
            "independently_proves_provider": True,
            "independently_proves_model": bool(actual_model),
        }
    if actual_model and actual_model != manifest_model:
        return {
            "classification": "MANIFEST_MODEL_CONFLICT",
            "explanation": "Transport preserved a concrete model identity that conflicts with the frozen manifest model.",
            "independently_proves_provider": bool(actual_provider),
            "independently_proves_model": True,
        }
    if actual_provider == manifest_provider and actual_model == manifest_model:
        return {
            "classification": "RAW_MODEL_CLAIM_ONLY_CONFLICT",
            "explanation": "Transport already proves the frozen route, so only non-authoritative model text could still conflict.",
            "independently_proves_provider": True,
            "independently_proves_model": True,
        }
    return {
        "classification": "UNRESOLVED_PROVIDER_AUTHORITY_FAILURE",
        "explanation": "The preserved evidence does not fit a narrower deterministic authority failure class.",
        "independently_proves_provider": False,
        "independently_proves_model": False,
    }


def bridge_route_evidence() -> dict[str, Any]:
    bridge_source = (ROOT / "apps_script" / "authoritative_provider_bridge.js").read_text()
    preserves_actual_identity = "actual_provider: actualProvider" in bridge_source and "actual_model: actualModel" in bridge_source
    preserves_error_identity = "status: 'error'" in bridge_source and "actual_provider: actualProvider" in bridge_source[bridge_source.find("status: 'error'"): bridge_source.find("status: 'error'") + 500]
    return {
        "bridge_function": BRIDGE_FUNCTION,
        "bridge_source_file": str((ROOT / "apps_script" / "authoritative_provider_bridge.js").resolve()),
        "bridge_route_resolution": "_resolveProviders_([providerName]) followed by prov.model = requestedModel",
        "bridge_error_path_preserves_actual_identity": preserves_error_identity,
        "bridge_success_path_preserves_actual_identity": preserves_actual_identity,
        "bridge_error_path_summary": "Provider-error catch path returns status error with request_status attempted and error text, but without actual_provider or actual_model fields.",
    }


def build_decisions(evidence: Mapping[str, Any], mismatch: Mapping[str, Any]) -> dict[str, Any]:
    actual_provider_proven = bool(mismatch["independently_proves_provider"])
    actual_model_proven = bool(mismatch["independently_proves_model"])
    provider_authority_reconciled = actual_provider_proven and actual_model_proven
    current_valid = int(evidence["batch_reconciliation"]["successful_valid_calls"])
    final_valid = current_valid + (1 if provider_authority_reconciled else 0)
    unresolved = 12 - final_valid
    conflicts = 0 if provider_authority_reconciled else 1

    identity_failure_decision = (
        "PROVIDER_AUTHORITY_FAILURE_MECHANICALLY_EXPLAINED"
        if mismatch["classification"] != "UNRESOLVED_PROVIDER_AUTHORITY_FAILURE"
        else "PROVIDER_AUTHORITY_FAILURE_UNRESOLVED"
    )
    if mismatch["classification"] == "UNRESOLVED_PROVIDER_AUTHORITY_FAILURE" and mismatch["explanation"]:
        identity_failure_decision = "PROVIDER_AUTHORITY_FAILURE_PARTIALLY_EXPLAINED"

    if provider_authority_reconciled:
        existing_result_decision = "EXISTING_RESULT_AUTHORITATIVELY_RECONCILED"
        batch_decision = "FORECAST_BATCH_002_COMPLETE"
        next_phase = "READY_TO_EXECUTE_FORECAST_BATCH_003"
        reconciled_result = {
            "forecast_call_id": CALL_ID,
            "authority_passed": True,
            "reason": "EXISTING_CONTRACT_VALID_RESULT_RECONCILED_FROM_PRESERVED_AUTHORITATIVE_TRANSPORT_EVIDENCE",
            "actual_provider": EXPECTED_PROVIDER,
            "actual_model": EXPECTED_MODEL,
        }
    else:
        existing_result_decision = "EXISTING_RESULT_NOT_AUTHORITATIVELY_RECONCILED"
        batch_decision = "FORECAST_BATCH_002_REMAINS_INCOMPLETE"
        next_phase = "GOVERNANCE_REVIEW_REQUIRED"
        reconciled_result = {
            "forecast_call_id": CALL_ID,
            "authority_passed": False,
            "reason": "EXISTING_RESULT_CANNOT_BE_RECONCILED_WITHOUT_INDEPENDENT_TRANSPORT_PROVIDER_AND_MODEL_EVIDENCE",
            "actual_provider_proven": actual_provider_proven,
            "actual_model_proven": actual_model_proven,
        }

    return {
        "identity_failure_decision": identity_failure_decision,
        "existing_result_decision": existing_result_decision,
        "batch_002_decision": batch_decision,
        "next_phase_decision": next_phase,
        "provider_authority_reconciled": provider_authority_reconciled,
        "final_authoritative_valid_count": final_valid,
        "unresolved_result_count": unresolved,
        "provider_authority_conflict_count": conflicts,
        "reconciled_result": reconciled_result,
    }


def materialize_run(*, fixed_timestamp: str | None = None) -> Path:
    timestamp = fixed_timestamp or now().replace("-", "").replace(":", "")
    timestamp = timestamp.replace("+00:00", "Z")
    if "T" not in timestamp:
        raise ProviderAuthorityReconciliationError("INVALID_TIMESTAMP")
    fingerprint = sha256_value(
        {
            "call_id": CALL_ID,
            "governance_recovery_id": GOVERNANCE_RECOVERY_ID,
            "move": "FORECAST_PROVIDER_AUTHORITY_RECONCILIATION_BATCH_002",
            "timestamp": timestamp,
        }
    ).split(":")[1][:12]
    run_dir = OUTPUT_ROOT / f"{RUN_PREFIX}{timestamp}-{fingerprint}"
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def write_artifacts(run_dir: Path, evidence: Mapping[str, Any], mismatch: Mapping[str, Any], decisions: Mapping[str, Any]) -> None:
    call = dict(evidence["call"] or {})
    attempt = dict(evidence["attempt_category"] or {})
    transport = dict(evidence["raw_transport"] or {})
    raw_transport = dict(transport.get("raw_transport_result") or {})
    transport_request = dict(transport.get("transport_request") or {})
    raw_provider = dict(evidence["raw_provider"] or {})
    authority_row = dict(evidence["provider_authority"] or {})
    failed_row = dict(evidence["failed_call"] or {})
    bridge = bridge_route_evidence()

    manifest_identity = {
        "forecast_call_id": CALL_ID,
        "manifest_provider": call.get("provider"),
        "manifest_model": call.get("model"),
        "pack_type": call.get("pack_type"),
        "pack_row_identity": call.get("pack_row_identity"),
        "pack_row_fingerprint": call.get("pack_row_fingerprint"),
        "prompt_contract_identity": call.get("prompt_contract_identity"),
        "source_session_id": call.get("source_session_id"),
        "historical_cutoff": call.get("historical_cutoff"),
    }
    transport_identity = {
        "forecast_call_id": CALL_ID,
        "transport_actual_provider": authority_row.get("actual_provider"),
        "transport_actual_model": authority_row.get("actual_model"),
        "requested_provider": raw_transport.get("requested_provider"),
        "requested_model": raw_transport.get("requested_model"),
        "bridge_provider_field": raw_transport.get("provider"),
        "bridge_model_field": raw_transport.get("model"),
        "transport_status": raw_transport.get("status"),
        "request_status": raw_transport.get("request_status"),
        "response_status": raw_transport.get("response_status"),
        "terminal_status": raw_transport.get("terminal_status"),
        "transport_error": raw_transport.get("error"),
        "transport_classification": transport.get("transport_classification"),
    }
    provider_response_metadata = {
        "forecast_call_id": CALL_ID,
        "provider_request_id": raw_transport.get("request_id"),
        "provider_response_body_present": bool(raw_transport.get("provider_response_body")),
        "raw_response_blocks_present": bool(raw_transport.get("raw_response_blocks")),
        "stop_reason": raw_transport.get("stop_reason"),
        "prompt_tokens": raw_transport.get("prompt_tokens"),
        "completion_tokens": raw_transport.get("completion_tokens"),
        "completion_timestamp": transport.get("completion_timestamp"),
        "raw_provider_output_present": bool(raw_provider.get("raw_provider_output")),
    }
    raw_claimed_identity = {
        "forecast_call_id": CALL_ID,
        "raw_claimed_provider": None,
        "raw_claimed_model": None,
        "source": "No parsed payload or raw provider self-identification was preserved for the failed authority call.",
    }
    conflict_analysis = {
        "forecast_call_id": CALL_ID,
        "exact_conflicting_values": {
            "manifest_provider": call.get("provider"),
            "manifest_model": call.get("model"),
            "transport_actual_provider": authority_row.get("actual_provider"),
            "transport_actual_model": authority_row.get("actual_model"),
            "requested_provider": raw_transport.get("requested_provider"),
            "requested_model": raw_transport.get("requested_model"),
            "bridge_provider_field": raw_transport.get("provider"),
            "bridge_model_field": raw_transport.get("model"),
            "raw_claimed_provider": None,
            "raw_claimed_model": None,
        },
        "mismatch_classification": mismatch["classification"],
        "root_cause": mismatch["explanation"],
    }
    authority_hierarchy = {
        "hierarchy": [
            "frozen manifest assignment",
            "bridge route and selected provider adapter",
            "transport actual_provider and actual_model",
            "provider API response metadata",
            "model-returned self-identification preserved only as non-authoritative",
        ],
        "applied_evidence": {
            "manifest": manifest_identity,
            "bridge_route": {
                "function": transport_request.get("function"),
                "provider_payload": transport_request.get("parameters", [{}])[0].get("provider") if transport_request.get("parameters") else None,
                "model_payload": transport_request.get("parameters", [{}])[0].get("model") if transport_request.get("parameters") else None,
            },
            "transport_actual_identity": {
                "actual_provider": authority_row.get("actual_provider"),
                "actual_model": authority_row.get("actual_model"),
            },
            "provider_response_metadata": provider_response_metadata,
            "raw_model_claim": raw_claimed_identity,
        },
    }
    reconciliation = {
        "forecast_call_id": CALL_ID,
        "identity_failure_decision": decisions["identity_failure_decision"],
        "existing_result_decision": decisions["existing_result_decision"],
        "reconciled_provider_authority_result": decisions["reconciled_result"],
        "no_provider_dispatch": True,
        "raw_response_modified": False,
        "frozen_manifest_modified": False,
        "repair_summary": (
            "No acceptance repair was applied. The reconciliation only documents that the bridge error path failed to preserve "
            "authoritative actual_provider and actual_model for a Gemini 503 provider error."
        ),
        "allowed_repair_assessment": (
            "A mechanical bridge repair is identifiable for future executions, but the preserved existing result cannot be "
            "accepted in this move because independently authoritative transport provider/model identity is absent."
        ),
    }
    authoritative_selection = {
        "forecast_call_id": CALL_ID,
        "selection_result": (
            "EXISTING_CONTRACT_VALID_RESULT_RECONCILED_FROM_PRESERVED_AUTHORITATIVE_TRANSPORT_EVIDENCE"
            if decisions["provider_authority_reconciled"]
            else "NO_AUTHORITATIVE_RESULT_SELECTED"
        ),
        "selection_reason": (
            "EXISTING_CONTRACT_VALID_RESULT_RECONCILED_FROM_PRESERVED_AUTHORITATIVE_TRANSPORT_EVIDENCE"
            if decisions["provider_authority_reconciled"]
            else "INDEPENDENT_TRANSPORT_PROVIDER_AND_MODEL_EVIDENCE_NOT_PRESERVED"
        ),
    }
    final_batch = {
        "frozen_batch_id": FROZEN_BATCH_ID,
        "authoritative_valid_results": decisions["final_authoritative_valid_count"],
        "provider_authority_conflicts": decisions["provider_authority_conflict_count"],
        "contract_valid_results": 12 if decisions["provider_authority_reconciled"] else 11,
        "missing_results": decisions["unresolved_result_count"],
        "duplicate_authoritative_results": 0,
        "batch_002_decision": decisions["batch_002_decision"],
        "no_batch_003_execution": True,
    }
    summary = {
        "forecast_call_id": CALL_ID,
        "mismatch_classification": mismatch["classification"],
        "identity_failure_decision": decisions["identity_failure_decision"],
        "existing_result_decision": decisions["existing_result_decision"],
        "batch_002_decision": decisions["batch_002_decision"],
        "next_phase_decision": decisions["next_phase_decision"],
        "batch_002_authoritative_valid_result_count": decisions["final_authoritative_valid_count"],
        "batch_002_unresolved_result_count": decisions["unresolved_result_count"],
        "batch_002_provider_authority_conflict_count": decisions["provider_authority_conflict_count"],
        "root_cause": mismatch["explanation"],
    }
    decision = {
        "identity_failure_decision": decisions["identity_failure_decision"],
        "existing_result_decision": decisions["existing_result_decision"],
        "batch_002_decision": decisions["batch_002_decision"],
        "next_phase_decision": decisions["next_phase_decision"],
    }

    write_json(
        run_dir / "run_manifest.json",
        {
            "move": "FORECAST_PROVIDER_AUTHORITY_RECONCILIATION_BATCH_002",
            "branch": git_branch(),
            "start_head": git_head(),
            "expected_start_head": EXPECTED_START_HEAD,
            "frozen_batch_id": FROZEN_BATCH_ID,
            "target_call_id": CALL_ID,
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
            "failed_batch_002_id": FAILED_BATCH_ID,
            "transport_repair_id": TRANSPORT_REPAIR_ID,
            "final_existence_verification_id": FINAL_VERIFICATION_ID,
            "governance_recovery_id": GOVERNANCE_RECOVERY_ID,
        },
    )
    write_json(
        run_dir / "reconciliation_contract.json",
        {
            "scope": "single_failed_forecast_call_provider_authority_reconciliation",
            "target_call_id": CALL_ID,
            "provider_calls_authorized": 0,
            "google_writes_authorized": 0,
            "frozen_manifest_must_remain_unchanged": True,
            "raw_response_must_remain_unchanged": True,
            "authority_evidence_hierarchy": authority_hierarchy["hierarchy"],
        },
    )
    write_json(run_dir / "failed_call_identity.json", failed_row)
    write_json(run_dir / "manifest_identity_evidence.json", manifest_identity)
    write_json(run_dir / "transport_identity_evidence.json", transport_identity)
    write_json(run_dir / "bridge_route_evidence.json", bridge)
    write_json(run_dir / "provider_response_metadata.json", provider_response_metadata)
    write_json(run_dir / "raw_claimed_identity.json", raw_claimed_identity)
    write_json(run_dir / "identity_conflict_analysis.json", conflict_analysis)
    write_json(run_dir / "authority_evidence_hierarchy.json", authority_hierarchy)
    write_json(run_dir / "provider_authority_reconciliation.json", reconciliation)
    write_jsonl(run_dir / "reconciled_provider_authority_result.jsonl", [decisions["reconciled_result"]])
    write_json(run_dir / "authoritative_result_selection.json", authoritative_selection)
    write_json(run_dir / "batch_002_final_reconciliation.json", final_batch)
    write_json(run_dir / "reconciliation_summary.json", summary)
    write_json(run_dir / "reconciliation_decision.json", decision)


def main(*, fixed_timestamp: str | None = None) -> dict[str, Any]:
    if git_branch() != "codex/immediate-impulse-outcome-recovery-r1":
        raise ProviderAuthorityReconciliationError("WRONG_BRANCH")
    if git_head() != EXPECTED_START_HEAD:
        raise ProviderAuthorityReconciliationError("UNEXPECTED_HEAD")
    if not is_descendant_of(EXPECTED_START_HEAD):
        raise ProviderAuthorityReconciliationError("ANCESTRY_NOT_CLEAN")

    evidence = load_call_evidence()
    if evidence["call"] is None or evidence["provider_authority"] is None or evidence["failed_call"] is None:
        raise ProviderAuthorityReconciliationError("MISSING_FAILED_CALL_EVIDENCE")
    mismatch = classify_mismatch(evidence)
    decisions = build_decisions(evidence, mismatch)
    run_dir = materialize_run(fixed_timestamp=fixed_timestamp)
    write_artifacts(run_dir, evidence, mismatch, decisions)
    summary = read_json(run_dir / "reconciliation_summary.json")
    return {
        "run_dir": str(run_dir),
        "identity_failure_decision": decisions["identity_failure_decision"],
        "existing_result_decision": decisions["existing_result_decision"],
        "batch_002_decision": decisions["batch_002_decision"],
        "next_phase_decision": decisions["next_phase_decision"],
        "mismatch_classification": summary["mismatch_classification"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixed-timestamp", default=None)
    args = parser.parse_args()
    print(json.dumps(main(fixed_timestamp=args.fixed_timestamp), indent=2, sort_keys=True))
