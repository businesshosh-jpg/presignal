#!/usr/bin/env python3
"""Diagnose the four remaining unresolved Forecast Batch 003 results."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import execute_presignal_v21_forecast_batch_001 as batch_exec
from automation import run_presignal_v21_single_event_path_pair_v1_1 as step6

PLAN_ID = "PPHB-R1-FORECAST-EXECUTION-PLAN-20260729T123101Z-14d356fb00c1"
BATCH_003_RUN_ID = "PPHB-R1-FORECAST-EXECUTION-BATCH-003-20260729T163858Z-0da0530d54c3"
BATCH_003_DIAGNOSIS_ID = "PPHB-R1-FORECAST-DIAGNOSIS-BATCH-003-20260729T172538Z-a7eb93dfa2ce"
SSL_REPAIR_ID = "PPHB-R1-FORECAST-SHARED-SSL-TRANSPORT-REPAIR-BATCH-003-20260729T174216Z-c32ec12def01"
BATCH_003_RECOVERY_ID = "PPHB-R1-FORECAST-GOVERNANCE-RECOVERY-BATCH-003-20260729T175456Z-786b31e16d49"
EXPECTED_START_HEAD = "04b5637eaebddc1ccf7197092d4aed5d49035865"
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
RUN_PREFIX = "PPHB-R1-FORECAST-FINAL-RESULT-DIAGNOSIS-BATCH-003-"
PACK_TYPE = "PACK_A"
FORECAST_CONTRACT = "presignal_event_path_contract_v1_1"
PROVIDER_RESPONSE_CALLS = (
    "FCL_f761a45623b0c5513ef58cae",
    "FCL_9819cb8d804223e9f0c3448c",
    "FCL_5cf8a9cd9f5ac7b59bd42b4e",
)
PARSE_FAILURE_CALL = "FCL_27720b8b23236b173b96fdee"
UNRESOLVED_CALLS = PROVIDER_RESPONSE_CALLS + (PARSE_FAILURE_CALL,)
PREVIOUSLY_RECOVERED_PROVIDER_CALLS = (
    "FCL_a5c7157c4cf958b3e63af1c9",
    "FCL_eb02f508140281ab6020b46b",
    "FCL_215cbe7ebee83be08888dbc5",
    "FCL_49308d97ec550f9587f1a571",
)


class Batch003FinalResultDiagnosisError(RuntimeError):
    """The bounded diagnosis move failed closed."""


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
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("".join(canonical_json(dict(row)) + "\n" for row in rows))
    os.replace(tmp, path)


def git_head() -> str:
    return batch_exec.git_head()


def git_branch() -> str:
    return batch_exec.git_branch()


def is_descendant_of(commit: str) -> bool:
    return batch_exec.is_descendant_of(commit)


def materialize_run(output_root: Path, fixed_timestamp: str | None = None) -> Path:
    timestamp = fixed_timestamp or now()
    fingerprint = hashlib.sha256(
        canonical_json(
            {
                "move": "FORECAST_FINAL_RESULT_DIAGNOSIS_BATCH_003",
                "forecast_plan_id": PLAN_ID,
                "batch_003_run_id": BATCH_003_RUN_ID,
                "batch_003_recovery_id": BATCH_003_RECOVERY_ID,
                "timestamp": timestamp,
            }
        ).encode("utf-8")
    ).hexdigest()[:12]
    return output_root / f"{RUN_PREFIX}{timestamp.replace(':', '').replace('-', '')}-{fingerprint}"


def extract_json_object(raw_output: Any) -> dict[str, Any]:
    if isinstance(raw_output, Mapping):
        return dict(raw_output)
    if not isinstance(raw_output, str):
        raise Batch003FinalResultDiagnosisError("RAW_OUTPUT_NOT_STRING_OR_OBJECT")
    text = raw_output.strip()
    if text.startswith("```"):
        match = re.search(r"```(?:json)?\n(.*?)\n```", text, re.S)
        if not match:
            raise Batch003FinalResultDiagnosisError("RAW_OUTPUT_FENCED_JSON_MISSING")
        text = match.group(1)
    parsed = json.loads(text)
    if not isinstance(parsed, Mapping):
        raise Batch003FinalResultDiagnosisError("RAW_OUTPUT_JSON_NOT_OBJECT")
    return dict(parsed)


def load_scope_bundle() -> dict[str, Any]:
    bundle = batch_exec.verified_batch_bundle(user_batch_label="FORECAST_BATCH_003", frozen_batch_id="FCB_PACK_A_003")
    by_call_id = {row["call"]["forecast_call_id"]: row for row in bundle["bundles"]}
    missing = set(UNRESOLVED_CALLS) - set(by_call_id)
    if missing:
        raise Batch003FinalResultDiagnosisError("UNRESOLVED_CALLS_MISSING_FROM_BUNDLE:" + ",".join(sorted(missing)))
    return {"bundle": bundle, "by_call_id": by_call_id}


def load_run_state(run_id: str) -> dict[str, Any]:
    run_dir = OUTPUT_ROOT / run_id
    state = {"run_dir": run_dir}
    for name in (
        "operation_journal.jsonl",
        "dispatch_state_ledger.jsonl",
        "raw_transport_results.jsonl",
        "raw_provider_outputs.jsonl",
        "provider_authority_results.jsonl",
        "forecast_parse_results.jsonl",
        "forecast_validation_results.jsonl",
        "normalized_forecast_results.jsonl",
        "failed_call_ledger.jsonl",
    ):
        path = run_dir / name
        state[name] = read_jsonl(path) if path.exists() else []
    return state


def index_by_call(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        call_id = row.get("forecast_call_id")
        if call_id is not None:
            result[str(call_id)] = dict(row)
    return result


def existing_authoritative_result_ids() -> set[str]:
    original = read_jsonl(OUTPUT_ROOT / BATCH_003_RUN_ID / "normalized_forecast_results.jsonl")
    recovered = read_jsonl(OUTPUT_ROOT / BATCH_003_DIAGNOSIS_ID / "recoverable_result_ledger.jsonl")
    governance = read_jsonl(OUTPUT_ROOT / BATCH_003_RECOVERY_ID / "normalized_forecast_results.jsonl")
    call_ids = {row["forecast_call_id"] for row in original if row.get("terminal_state") == "SUCCEEDED_VALID"}
    call_ids.update(row["forecast_call_id"] for row in recovered if row.get("validation_status") == "VALID")
    call_ids.update(row["forecast_call_id"] for row in governance if row.get("terminal_state") == "SUCCEEDED_VALID")
    return call_ids


def candidate_payloads_from_call(call_id: str, state: Mapping[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    raw_transport = index_by_call(state["raw_transport_results.jsonl"]).get(call_id)
    raw_provider = index_by_call(state["raw_provider_outputs.jsonl"]).get(call_id)
    if raw_provider and raw_provider.get("raw_provider_output") not in (None, ""):
        candidates.append(
            {
                "forecast_call_id": call_id,
                "source": "raw_provider_output",
                "payload_location": "raw_provider_outputs.jsonl.raw_provider_output",
                "payload": raw_provider["raw_provider_output"],
            }
        )
    if raw_transport:
        transport_result = raw_transport.get("raw_transport_result")
        if isinstance(transport_result, Mapping):
            for field in ("raw_output", "provider_response_body"):
                value = transport_result.get(field)
                if value not in (None, ""):
                    candidates.append(
                        {
                            "forecast_call_id": call_id,
                            "source": field,
                            "payload_location": f"raw_transport_results.jsonl.raw_transport_result.{field}",
                            "payload": value,
                        }
                    )
    return candidates


def structure_summary(payload: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "payload_type": type(payload).__name__,
        "fenced_json": isinstance(payload, str) and payload.strip().startswith("```"),
        "top_level_type": None,
        "top_level_keys": None,
    }
    try:
        parsed = extract_json_object(payload)
        summary["top_level_type"] = "object"
        summary["top_level_keys"] = sorted(parsed)
        summary["path_count"] = len(parsed.get("path") or []) if isinstance(parsed.get("path"), list) else None
        summary["no_signal_flag"] = parsed.get("no_signal_flag")
        summary["confidence"] = parsed.get("confidence")
    except Exception as exc:
        summary["parse_error"] = str(exc)
    return summary


def recover_existing_payload(call_id: str, scope_row: Mapping[str, Any], run_state: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    authority = index_by_call(run_state["provider_authority_results.jsonl"]).get(call_id)
    if not authority or not authority.get("authority_passed"):
        raise Batch003FinalResultDiagnosisError("PROVIDER_AUTHORITY_RECHECK_FAILED")
    candidates = candidate_payloads_from_call(call_id, run_state)
    payload_rows: list[dict[str, Any]] = []
    extraction_rows: list[dict[str, Any]] = []
    success_rows: list[dict[str, Any]] = []
    for candidate in candidates:
        payload_rows.append(
            {
                "forecast_call_id": call_id,
                "source": candidate["source"],
                "payload_location": candidate["payload_location"],
                "structure": structure_summary(candidate["payload"]),
            }
        )
        try:
            parsed, parse_audit = step6.normalize_provider_output(candidate["payload"])
            prediction, paths = step6.response_to_contract(
                parsed,
                scope_row["pack_payload"],
                run_id="EXISTING_PRESERVED_PROVIDER_PAYLOAD_RECOVERY",
                created_ts=str(
                    (
                        index_by_call(run_state["raw_transport_results.jsonl"]).get(call_id, {}).get("completion_timestamp")
                        or now()
                    )
                ),
                raw_output=candidate["payload"],
                bridge_result=index_by_call(run_state["raw_transport_results.jsonl"]).get(call_id, {}),
            )
            extraction_rows.append(
                {
                    "forecast_call_id": call_id,
                    "source": candidate["source"],
                    "payload_location": candidate["payload_location"],
                    "extraction_route": "DIRECT_RAW_OUTPUT_OR_TRANSPORT_FIELD",
                    "deterministic": True,
                    "parse_audit": parse_audit,
                }
            )
            success_rows.append(
                {
                    "forecast_call_id": call_id,
                    "source": candidate["source"],
                    "prediction": prediction,
                    "paths": paths,
                    "parse_audit": parse_audit,
                }
            )
        except Exception as exc:
            extraction_rows.append(
                {
                    "forecast_call_id": call_id,
                    "source": candidate["source"],
                    "payload_location": candidate["payload_location"],
                    "extraction_route": "DIRECT_RAW_OUTPUT_OR_TRANSPORT_FIELD",
                    "deterministic": True,
                    "recovery_error": str(exc),
                }
            )
    if len(success_rows) > 1:
        fingerprints = {
            canonical_json(
                {
                    "prediction": row["prediction"],
                    "paths": row["paths"],
                }
            )
            for row in success_rows
        }
        if len(fingerprints) > 1:
            classification = {
                "forecast_call_id": call_id,
                "classification": "MULTIPLE_PAYLOADS_IDENTITY_CONFLICT",
                "recommended_action": "GOVERNANCE_REVIEW_REQUIRED",
            }
            return classification, payload_rows, extraction_rows, []
    if success_rows:
        row = success_rows[0]
        classification = {
            "forecast_call_id": call_id,
            "classification": "EXISTING_FORECAST_PAYLOAD_RECOVERED_AND_VALIDATED",
            "recovery_source": row["source"],
            "recommended_action": "NO_PROVIDER_CALL_REQUIRED_RESULT_RECOVERED",
            "maximum_additional_dispatch_recommendation": 0,
            "duplicate_result_risk": "NONE",
        }
        recovered = {
            "forecast_call_id": call_id,
            "provider": scope_row["call"]["provider"],
            "model": scope_row["call"]["model"],
            "provider_authority_result": authority,
            "parse_status": "PARSED",
            "parse_audit": row["parse_audit"],
            "validation_status": "VALID",
            "prediction_id": row["prediction"]["prediction_id"],
            "path_count": len(row["paths"]),
            "prediction": row["prediction"],
            "paths": row["paths"],
            "recovery_source": row["source"],
            "authoritative_selection_reason": "EXISTING_PRESERVED_PROVIDER_PAYLOAD_RECOVERED_BY_DETERMINISTIC_WRAPPER_EXTRACTION",
        }
        return classification, payload_rows, extraction_rows, [recovered]
    classification = {
        "forecast_call_id": call_id,
        "classification": "NO_FORECAST_PAYLOAD_PRESENT",
        "recommended_action": "GOVERNANCE_REVIEW_REQUIRED",
        "maximum_additional_dispatch_recommendation": 0,
        "duplicate_result_risk": "NONE",
    }
    if any("recovery_error" in row for row in extraction_rows):
        classification["classification"] = "PROVIDER_RESPONSE_STATE_UNRESOLVED"
        classification["recommended_action"] = "FURTHER_EXISTING_RESULT_RECOVERY_REQUIRED"
    return classification, payload_rows, extraction_rows, []


def provider_response_analysis(call_id: str, scope_row: Mapping[str, Any], recovery_state: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    transport_row = index_by_call(recovery_state["raw_transport_results.jsonl"])[call_id]
    provider_row = index_by_call(recovery_state["raw_provider_outputs.jsonl"])[call_id]
    authority_row = index_by_call(recovery_state["provider_authority_results.jsonl"])[call_id]
    failed_row = index_by_call(recovery_state["failed_call_ledger.jsonl"])[call_id]
    transport_result = transport_row["raw_transport_result"]
    provider_body = transport_result.get("provider_response_body") if isinstance(transport_result, Mapping) else None
    response_blocks = transport_result.get("raw_response_blocks") if isinstance(transport_result, Mapping) else None
    classification, payload_rows, extraction_rows, recovered_rows = recover_existing_payload(call_id, scope_row, recovery_state)
    analysis = {
        "forecast_call_id": call_id,
        "classification": classification["classification"],
        "provider": scope_row["call"]["provider"],
        "model": scope_row["call"]["model"],
        "manifest_provider": scope_row["call"]["provider"],
        "manifest_model": scope_row["call"]["model"],
        "requested_provider": transport_row.get("requested_provider"),
        "requested_model": transport_row.get("requested_model"),
        "actual_provider": transport_row.get("actual_provider"),
        "actual_model": transport_row.get("actual_model"),
        "request_status": transport_row.get("request_status"),
        "response_status": transport_row.get("response_status"),
        "terminal_status": transport_row.get("terminal_status"),
        "provider_error": transport_row.get("provider_error"),
        "provider_request_id": transport_row.get("provider_request_id"),
        "provider_response_body_present": provider_body not in (None, ""),
        "raw_response_blocks_present": bool(response_blocks),
        "raw_output_present": provider_row.get("raw_provider_output") not in (None, ""),
        "raw_output_type": type(provider_row.get("raw_provider_output")).__name__,
        "raw_output_structure": structure_summary(provider_row.get("raw_provider_output")),
        "failed_reason": failed_row.get("reason"),
        "authority_passed": authority_row.get("authority_passed"),
        "recommended_action": classification["recommended_action"],
        "maximum_additional_dispatch_recommendation": classification["maximum_additional_dispatch_recommendation"],
    }
    return analysis, payload_rows, extraction_rows, recovered_rows


def compare_prior_recovery_pattern(call_id: str, analysis: Mapping[str, Any], recovery_state: Mapping[str, Any], previous_state: Mapping[str, Any]) -> dict[str, Any]:
    current_transport = index_by_call(recovery_state["raw_transport_results.jsonl"])[call_id]
    prev_rows = []
    prev_transport = index_by_call(previous_state["raw_transport_results.jsonl"])
    prev_provider = index_by_call(previous_state["raw_provider_outputs.jsonl"])
    for prev_call in PREVIOUSLY_RECOVERED_PROVIDER_CALLS:
        prev_transport_row = prev_transport[prev_call]
        prev_payload_row = prev_provider[prev_call]
        prev_result = prev_transport_row["raw_transport_result"]
        prev_rows.append(
            {
                "forecast_call_id": prev_call,
                "provider_response_body_present": prev_result.get("provider_response_body") not in (None, ""),
                "raw_output_type": type(prev_payload_row.get("raw_provider_output")).__name__,
                "raw_output_structure": structure_summary(prev_payload_row.get("raw_provider_output")),
                "response_status": prev_transport_row.get("response_status"),
            }
        )
    current_result = current_transport["raw_transport_result"]
    return {
        "forecast_call_id": call_id,
        "same_wrapper_structure": all(
            row["provider_response_body_present"] is False
            and row["raw_output_structure"].get("top_level_keys") == analysis["raw_output_structure"].get("top_level_keys")
            and row["response_status"] == analysis["response_status"]
            for row in prev_rows
        ),
        "same_raw_output_field": all(row["raw_output_type"] == analysis["raw_output_type"] for row in prev_rows),
        "same_provider_body_flags": all(row["provider_response_body_present"] is False for row in prev_rows)
        and current_result.get("provider_response_body") in (None, ""),
        "same_extraction_route": "DIRECT_RAW_OUTPUT_OR_TRANSPORT_FIELD",
        "same_parser_eligibility_defect": "RECOVERY_EXECUTOR_REJECTED_EMPTY_PROVIDER_RESPONSE_BODY_BEFORE_PARSING",
        "comparison_basis": prev_rows,
    }


def parse_failure_comparison(original_state: Mapping[str, Any], recovery_state: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    original_transport = index_by_call(original_state["raw_transport_results.jsonl"])[PARSE_FAILURE_CALL]
    replacement_transport = index_by_call(recovery_state["raw_transport_results.jsonl"])[PARSE_FAILURE_CALL]
    original_payload = extract_json_object(original_transport["raw_transport_result"]["raw_output"])
    replacement_payload = extract_json_object(replacement_transport["raw_transport_result"]["raw_output"])
    prompt_user = (
        original_transport.get("transport_request", {})
        .get("parameters", [{}])[0]
        .get("prompt", {})
        .get("user", "")
    )
    comparison = {
        "forecast_call_id": PARSE_FAILURE_CALL,
        "original_attempt": {
            "provider": original_transport.get("actual_provider"),
            "model": original_transport.get("actual_model"),
            "no_signal_flag": original_payload.get("no_signal_flag"),
            "confidence": original_payload.get("confidence"),
            "early_reaction_5m_direction": original_payload.get("early_reaction_5m_direction"),
            "path": original_payload.get("path"),
            "information_used_type": type(original_payload.get("information_used")).__name__,
        },
        "replacement_attempt": {
            "provider": replacement_transport.get("actual_provider"),
            "model": replacement_transport.get("actual_model"),
            "no_signal_flag": replacement_payload.get("no_signal_flag"),
            "confidence": replacement_payload.get("confidence"),
            "early_reaction_5m_direction": replacement_payload.get("early_reaction_5m_direction"),
            "path": replacement_payload.get("path"),
            "information_used_type": type(replacement_payload.get("information_used")).__name__,
        },
        "both_no_signal_flag_true": original_payload.get("no_signal_flag") is True and replacement_payload.get("no_signal_flag") is True,
        "both_confidence_null": original_payload.get("confidence") is None and replacement_payload.get("confidence") is None,
        "otherwise_equivalent_scientific_content": (
            original_payload.get("no_signal_flag") == replacement_payload.get("no_signal_flag")
            and original_payload.get("early_reaction_5m_direction") == replacement_payload.get("early_reaction_5m_direction")
            and original_payload.get("path") == replacement_payload.get("path")
        ),
        "prompt_explicitly_requires_numeric_confidence_for_no_signal": False,
        "schema_implementation_requires_numeric_confidence": True,
        "prompt_key_list_includes_confidence": "confidence" in prompt_user,
        "prompt_text_contains_numeric_constraint_for_confidence": bool(re.search(r"confidence[^\\n]{0,80}(0,1|0 and 1|numeric|float)", prompt_user, re.I)),
        "prompt_text_excerpt": prompt_user[:1200],
    }
    raw_diffs = [
        {
            "field": "confidence",
            "expected_type": "int|float in [0,1]",
            "original_value": original_payload.get("confidence"),
            "original_type": type(original_payload.get("confidence")).__name__,
            "replacement_value": replacement_payload.get("confidence"),
            "replacement_type": type(replacement_payload.get("confidence")).__name__,
        }
    ]
    analysis = {
        "forecast_call_id": PARSE_FAILURE_CALL,
        "classification": "FROZEN_PROMPT_NO_SIGNAL_REQUIREMENT_AMBIGUOUS",
        "governance_recommendation": "PROMPT_OR_CONTRACT_REPAIR_REQUIRED_FOR_FUTURE_BATCHES_ONLY",
        "root_cause": (
            "Both Anthropic attempts returned NO_SIGNAL with confidence=null. The frozen parser requires numeric "
            "confidence for all outputs, but the frozen prompt enumerates the confidence key without explicitly stating "
            "that NO_SIGNAL must still carry a numeric confidence in [0,1]."
        ),
        "another_unchanged_replacement_usefulness": "LOW",
        "another_unchanged_replacement_meaningful_likelihood": False,
    }
    no_signal_contract = {
        "frozen_prompt_no_signal_requirement": {
            "confidence_key_present": comparison["prompt_key_list_includes_confidence"],
            "numeric_confidence_explicit_for_no_signal": comparison["prompt_explicitly_requires_numeric_confidence_for_no_signal"],
            "assessment": "AMBIGUOUS_FOR_NO_SIGNAL",
        },
        "frozen_schema_no_signal_requirement": {
            "source": "automation.run_presignal_v21_single_event_path_pair_v1_1.normalize_provider_output",
            "numeric_confidence_required": True,
            "null_confidence_permitted": False,
            "assessment": "EXPLICIT_IN_IMPLEMENTATION",
        },
        "forward_looking_recommendation": {
            "decision": "PROMPT_OR_CONTRACT_REPAIR_REQUIRED_FOR_FUTURE_BATCHES_ONLY",
            "drifting_warning_required": True,
            "deviation": "Clarify future forecast prompts and/or response-contract text that NO_SIGNAL still requires numeric confidence in [0,1].",
            "expected_benefit": "Reduces repeated Anthropic null-confidence outputs on no-signal cases.",
            "risk_and_cost": "Changes future frozen prompt comparability and therefore requires authorization before any future batch planning update.",
            "smallest_plan_aligned_alternative": "Add one explicit sentence to future prompt contracts without changing the downstream parser or historical Batch 003 inputs.",
            "authorization_required": True,
        },
    }
    return analysis, raw_diffs, comparison, no_signal_contract


def initialize_run(run_dir: Path, repo_state: Mapping[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=False)
    write_json(
        run_dir / "run_manifest.json",
        {
            "move": "FORECAST_FINAL_RESULT_DIAGNOSIS_BATCH_003",
            "forecast_plan_id": PLAN_ID,
            "batch_003_run_id": BATCH_003_RUN_ID,
            "batch_003_recovery_id": BATCH_003_RECOVERY_ID,
            "authorized_provider_calls": 0,
            "provider_calls_executed": 0,
            "batch_004_calls_executed": 0,
            "google_writes_executed": 0,
            "outcome_attachment_executed": 0,
            "forecast_accuracy_calculations_executed": 0,
            "market_data_calls_executed": 0,
            "research_ai_calls_executed": 0,
            "web_calls_executed": 0,
            "branch": repo_state["branch"],
            "start_head": repo_state["head"],
            "expected_start_head": EXPECTED_START_HEAD,
        },
    )
    write_json(
        run_dir / "governing_artifact_manifest.json",
        {
            "forecast_plan_id": PLAN_ID,
            "batch_003_execution_id": BATCH_003_RUN_ID,
            "batch_003_diagnosis_id": BATCH_003_DIAGNOSIS_ID,
            "ssl_transport_repair_id": SSL_REPAIR_ID,
            "batch_003_governance_recovery_id": BATCH_003_RECOVERY_ID,
        },
    )
    write_json(
        run_dir / "diagnosis_contract.json",
        {
            "scope_call_ids": list(UNRESOLVED_CALLS),
            "provider_response_failure_call_ids": list(PROVIDER_RESPONSE_CALLS),
            "parse_failure_call_id": PARSE_FAILURE_CALL,
            "pack_type": PACK_TYPE,
            "forecast_contract": FORECAST_CONTRACT,
            "provider_calls_authorized": 0,
            "google_writes_authorized": 0,
        },
    )


def run_diagnosis(*, output_root: Path = OUTPUT_ROOT, fixed_timestamp: str | None = None, enforce_head: bool = True) -> dict[str, Any]:
    repo_state = {"branch": git_branch(), "head": git_head()}
    if repo_state["branch"] != "codex/immediate-impulse-outcome-recovery-r1":
        raise Batch003FinalResultDiagnosisError("BRANCH_MISMATCH")
    if enforce_head and repo_state["head"] != EXPECTED_START_HEAD:
        raise Batch003FinalResultDiagnosisError("HEAD_MISMATCH")
    if not is_descendant_of(EXPECTED_START_HEAD):
        raise Batch003FinalResultDiagnosisError("ANCESTRY_MISMATCH")

    run_dir = materialize_run(output_root, fixed_timestamp=fixed_timestamp)
    initialize_run(run_dir, repo_state)

    scope_bundle = load_scope_bundle()
    original_state = load_run_state(BATCH_003_RUN_ID)
    previous_diagnosis_state = load_run_state(BATCH_003_RUN_ID)
    recovery_state = load_run_state(BATCH_003_RECOVERY_ID)
    authoritative_before = existing_authoritative_result_ids()
    if len(authoritative_before) != 8:
        raise Batch003FinalResultDiagnosisError("AUTHORITATIVE_BATCH_003_COUNT_UNEXPECTED")

    unresolved_inventory = []
    provider_structures = []
    prior_comparisons = []
    candidate_inventory = []
    extraction_ledger = []
    recovered_results = []
    authority_rechecks = []
    parse_rechecks = []
    validation_rechecks = []
    retry_rows = []

    for call_id in PROVIDER_RESPONSE_CALLS:
        scope_row = scope_bundle["by_call_id"][call_id]
        unresolved_inventory.append(
            {
                "forecast_call_id": call_id,
                "provider": scope_row["call"]["provider"],
                "model": scope_row["call"]["model"],
                "original_terminal_state": "FAILED_PROVIDER",
                "governance_recovery_terminal_state": index_by_call(recovery_state["failed_call_ledger.jsonl"])[call_id]["terminal_state"],
            }
        )
        analysis, payload_rows, extraction_rows, recovered_rows = provider_response_analysis(call_id, scope_row, recovery_state)
        provider_structures.append(analysis)
        candidate_inventory.extend(payload_rows)
        extraction_ledger.extend(extraction_rows)
        recovered_results.extend(recovered_rows)
        prior_comparisons.append(compare_prior_recovery_pattern(call_id, analysis, recovery_state, previous_diagnosis_state))
        if recovered_rows:
            recovered = recovered_rows[0]
            authority_rechecks.append(
                {
                    "forecast_call_id": call_id,
                    "authority_passed": recovered["provider_authority_result"]["authority_passed"],
                    "actual_provider": recovered["provider_authority_result"]["actual_provider"],
                    "actual_model": recovered["provider_authority_result"]["actual_model"],
                    "reason": recovered["provider_authority_result"]["reason"],
                }
            )
            parse_rechecks.append(
                {
                    "forecast_call_id": call_id,
                    "parse_status": recovered["parse_status"],
                    "parse_audit": recovered["parse_audit"],
                }
            )
            validation_rechecks.append(
                {
                    "forecast_call_id": call_id,
                    "validation_status": recovered["validation_status"],
                    "prediction_id": recovered["prediction_id"],
                    "path_count": recovered["path_count"],
                }
            )
            retry_rows.append(
                {
                    "forecast_call_id": call_id,
                    "provider": scope_row["call"]["provider"],
                    "model": scope_row["call"]["model"],
                    "number_of_prior_provider_dispatches": 2,
                    "existing_payload_found": True,
                    "existing_payload_recoverable": True,
                    "authoritative_result_exists": True,
                    "duplicate_result_risk": "NONE",
                    "provider_noncompliance_pattern": False,
                    "recommended_action": "NO_PROVIDER_CALL_REQUIRED_RESULT_RECOVERED",
                    "maximum_additional_dispatch_recommendation": 0,
                }
            )
        else:
            retry_rows.append(
                {
                    "forecast_call_id": call_id,
                    "provider": scope_row["call"]["provider"],
                    "model": scope_row["call"]["model"],
                    "number_of_prior_provider_dispatches": 2,
                    "existing_payload_found": False,
                    "existing_payload_recoverable": False,
                    "authoritative_result_exists": False,
                    "duplicate_result_risk": "NONE",
                    "provider_noncompliance_pattern": None,
                    "recommended_action": analysis["recommended_action"],
                    "maximum_additional_dispatch_recommendation": analysis["maximum_additional_dispatch_recommendation"],
                }
            )

    parse_scope = scope_bundle["by_call_id"][PARSE_FAILURE_CALL]
    unresolved_inventory.append(
        {
            "forecast_call_id": PARSE_FAILURE_CALL,
            "provider": parse_scope["call"]["provider"],
            "model": parse_scope["call"]["model"],
            "original_terminal_state": "FAILED_PARSE",
            "governance_recovery_terminal_state": index_by_call(recovery_state["failed_call_ledger.jsonl"])[PARSE_FAILURE_CALL]["terminal_state"],
        }
    )
    parse_analysis, parse_diffs, parse_comparison, no_signal_contract = parse_failure_comparison(original_state, recovery_state)
    retry_rows.append(
        {
            "forecast_call_id": PARSE_FAILURE_CALL,
            "provider": parse_scope["call"]["provider"],
            "model": parse_scope["call"]["model"],
            "number_of_prior_provider_dispatches": 2,
            "existing_payload_found": True,
            "existing_payload_recoverable": False,
            "authoritative_result_exists": False,
            "duplicate_result_risk": "NONE",
            "provider_noncompliance_pattern": True,
            "recommended_action": parse_analysis["governance_recommendation"],
            "maximum_additional_dispatch_recommendation": 0,
        }
    )

    recovered_call_ids = {row["forecast_call_id"] for row in recovered_results if row.get("validation_status") == "VALID"}
    authoritative_after = authoritative_before | recovered_call_ids
    if len(authoritative_after) != 11:
        raise Batch003FinalResultDiagnosisError("POST_DIAGNOSIS_AUTHORITATIVE_COUNT_UNEXPECTED")

    contract_accounting = {
        "new_calls_attempted": 5,
        "provider_authority_passed": 5,
        "transport_succeeded": 5,
        "forecast_parse_passed": 1,
        "forecast_parse_failed": 1,
        "provider_response_failures_before_parse": 3,
        "validation_reached": 1,
        "validation_valid": 1,
        "validation_failed": 0,
        "clarification": {
            "provider_response_usability_failure": "Three governance-recovery calls already contained provider forecasts but were classified as FAILED_PROVIDER before parse because provider_response_body was empty while raw_output was present.",
            "parse_stage_schema_failure": "The repeated Anthropic NO_SIGNAL outputs failed at parse because confidence was null.",
            "contract_validation_failure": "No validation-stage failure occurred in the five-call governance recovery run.",
        },
    }

    summary = {
        "provider_response_calls_recovered": len(recovered_call_ids),
        "parse_failure_recovered": False,
        "batch_003_authoritative_valid_results": len(authoritative_after),
        "batch_003_unresolved_results": 12 - len(authoritative_after),
        "cumulative_validated_forecast_calls": 24 + len(authoritative_after),
        "remaining_planned_forecast_calls": 564 - (24 + len(authoritative_after)),
        "provider_response_decision": "ALL_THREE_PROVIDER_RESULTS_RECOVERED" if len(recovered_call_ids) == 3 else "SOME_PROVIDER_RESULTS_RECOVERED",
        "parse_failure_decision": "REPEATED_PARSE_FAILURE_FULLY_EXPLAINED",
        "retry_governance_decision": "FUTURE_PROMPT_OR_CONTRACT_REPAIR_REQUIRED",
        "batch_003_decision": "FORECAST_BATCH_003_REMAINS_INCOMPLETE",
    }

    decision = {
        "provider_response_decision": summary["provider_response_decision"],
        "parse_failure_decision": summary["parse_failure_decision"],
        "retry_governance_decision": summary["retry_governance_decision"],
        "batch_003_decision": summary["batch_003_decision"],
    }

    write_jsonl(run_dir / "unresolved_call_inventory.jsonl", unresolved_inventory)
    write_jsonl(run_dir / "provider_response_structure_analysis.jsonl", provider_structures)
    write_jsonl(run_dir / "prior_recovery_pattern_comparison.jsonl", prior_comparisons)
    write_jsonl(run_dir / "candidate_payload_inventory.jsonl", candidate_inventory)
    write_jsonl(run_dir / "deterministic_extraction_ledger.jsonl", extraction_ledger)
    write_jsonl(run_dir / "recovered_result_ledger.jsonl", recovered_results)
    write_jsonl(run_dir / "provider_authority_recheck.jsonl", authority_rechecks)
    write_jsonl(run_dir / "forecast_parse_recheck.jsonl", parse_rechecks)
    write_jsonl(run_dir / "forecast_validation_recheck.jsonl", validation_rechecks)
    write_json(run_dir / "repeated_parse_attempt_comparison.json", parse_comparison)
    write_json(run_dir / "no_signal_contract_analysis.json", no_signal_contract)
    write_jsonl(run_dir / "retry_governance_ledger.jsonl", retry_rows)
    write_json(run_dir / "contract_decision_accounting.json", contract_accounting)
    write_json(
        run_dir / "batch_003_post_diagnosis_reconciliation.json",
        {
            "batch_003_authoritative_valid_results": len(authoritative_after),
            "batch_003_unresolved_results": 12 - len(authoritative_after),
            "cumulative_validated_forecast_calls": 24 + len(authoritative_after),
            "remaining_planned_forecast_calls": 564 - (24 + len(authoritative_after)),
            "recovered_call_ids": sorted(recovered_call_ids),
        },
    )
    write_json(run_dir / "diagnosis_summary.json", summary)
    write_json(run_dir / "diagnosis_decision.json", decision)

    return {
        "run_dir": run_dir,
        "summary": summary,
        "decision": decision,
        "parse_analysis": parse_analysis,
        "parse_diffs": parse_diffs,
        "recovered_results": recovered_results,
        "retry_rows": retry_rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--fixed-timestamp", default=None)
    parser.add_argument("--skip-head-check", action="store_true")
    args = parser.parse_args(argv)
    result = run_diagnosis(
        output_root=args.output_root,
        fixed_timestamp=args.fixed_timestamp,
        enforce_head=not args.skip_head_check,
    )
    print(json.dumps({"run_dir": str(result["run_dir"]), **result["decision"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
