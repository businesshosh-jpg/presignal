#!/usr/bin/env python3
"""Close the final Batch 003 schema failure and stage a future NO_SIGNAL prompt clarification."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
FORECAST_PLANNING_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_planning"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FORECAST_PLAN_RUN_ID = "PPHB-R1-FORECAST-EXECUTION-PLAN-20260729T123101Z-14d356fb00c1"
BATCH_003_EXECUTION_RUN_ID = "PPHB-R1-FORECAST-EXECUTION-BATCH-003-20260729T163858Z-0da0530d54c3"
BATCH_003_DIAGNOSIS_RUN_ID = "PPHB-R1-FORECAST-DIAGNOSIS-BATCH-003-20260729T172538Z-a7eb93dfa2ce"
BATCH_003_GOVERNANCE_RECOVERY_RUN_ID = "PPHB-R1-FORECAST-GOVERNANCE-RECOVERY-BATCH-003-20260729T175456Z-786b31e16d49"
BATCH_003_FINAL_DIAGNOSIS_RUN_ID = "PPHB-R1-FORECAST-FINAL-RESULT-DIAGNOSIS-BATCH-003-20260729T234944Z-a65de810bf75"
TARGET_CALL_ID = "FCL_27720b8b23236b173b96fdee"
TARGET_BATCH_ID = "FCB_PACK_A_003"
TARGET_PACK_TYPE = "PACK_A"
TERMINAL_CLASSIFICATION = "TERMINAL_PROVIDER_SCHEMA_NONCOMPLIANCE"
TERMINAL_REASON = "REPEATED_NO_SIGNAL_CONFIDENCE_NULL_UNDER_AMBIGUOUS_FROZEN_PROMPT"
ADDED_PROMPT_SENTENCE = (
    "Even when no_signal_flag is true, confidence must be a numeric value from 0 to 1 and must not be null."
)
RUN_PREFIX = "PPHB-R1-FORECAST-BATCH-003-CLOSURE-AND-FUTURE-NO-SIGNAL-CLARIFICATION"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_text(canonical_json(value))


def now_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def git_branch() -> str:
    return subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, text=True).strip()


def commit_exists(commit: str) -> bool:
    return subprocess.run(
        ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0


def path_for_run(run_id: str) -> Path:
    return OUTPUT_ROOT / run_id


def line_by_call(rows: Iterable[Mapping[str, Any]], call_id: str) -> dict[str, Any]:
    for row in rows:
        if row.get("forecast_call_id") == call_id:
            return dict(row)
    raise KeyError(call_id)


def extract_json_payload(raw_provider_output: str) -> dict[str, Any]:
    text = raw_provider_output.strip()
    if text.startswith("```json"):
        text = text[len("```json"):].strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    return json.loads(text)


def load_target_attempts() -> dict[str, Any]:
    original_run = path_for_run(BATCH_003_EXECUTION_RUN_ID)
    replacement_run = path_for_run(BATCH_003_GOVERNANCE_RECOVERY_RUN_ID)

    original_output = line_by_call(read_jsonl(original_run / "raw_provider_outputs.jsonl"), TARGET_CALL_ID)
    replacement_output = line_by_call(read_jsonl(replacement_run / "raw_provider_outputs.jsonl"), TARGET_CALL_ID)
    original_authority = line_by_call(read_jsonl(original_run / "provider_authority_results.jsonl"), TARGET_CALL_ID)
    replacement_authority = line_by_call(read_jsonl(replacement_run / "provider_authority_results.jsonl"), TARGET_CALL_ID)
    original_parse = line_by_call(read_jsonl(original_run / "forecast_parse_results.jsonl"), TARGET_CALL_ID)
    replacement_parse = line_by_call(read_jsonl(replacement_run / "forecast_parse_results.jsonl"), TARGET_CALL_ID)
    return {
        "original_output": original_output,
        "replacement_output": replacement_output,
        "original_authority": original_authority,
        "replacement_authority": replacement_authority,
        "original_parse": original_parse,
        "replacement_parse": replacement_parse,
        "original_payload": extract_json_payload(original_output["raw_provider_output"]),
        "replacement_payload": extract_json_payload(replacement_output["raw_provider_output"]),
    }


def build_terminal_schema_failure_record(attempts: Mapping[str, Any]) -> dict[str, Any]:
    original_payload = attempts["original_payload"]
    replacement_payload = attempts["replacement_payload"]
    return {
        "forecast_call_id": TARGET_CALL_ID,
        "provider": attempts["original_output"]["provider"],
        "model": attempts["original_output"]["model"],
        "pack_type": TARGET_PACK_TYPE,
        "terminal_classification": TERMINAL_CLASSIFICATION,
        "reason": TERMINAL_REASON,
        "supporting_facts": {
            "provider_executions_completed": 2,
            "provider_authority_passed": (
                attempts["original_authority"]["authority_passed"]
                and attempts["replacement_authority"]["authority_passed"]
            ),
            "raw_outputs_preserved": True,
            "same_decisive_type_failure_repeated": (
                original_payload["no_signal_flag"] is True
                and replacement_payload["no_signal_flag"] is True
                and original_payload["confidence"] is None
                and replacement_payload["confidence"] is None
                and original_payload["early_reaction_5m_direction"] == "UNCERTAIN"
                and replacement_payload["early_reaction_5m_direction"] == "UNCERTAIN"
                and original_payload["path"] == []
                and replacement_payload["path"] == []
            ),
            "contract_valid_result_exists": False,
            "additional_unchanged_retry_recommended": False,
        },
    }


def build_attempt_comparison(attempts: Mapping[str, Any]) -> dict[str, Any]:
    original_payload = attempts["original_payload"]
    replacement_payload = attempts["replacement_payload"]
    return {
        "forecast_call_id": TARGET_CALL_ID,
        "original_attempt": {
            "authority_passed": attempts["original_authority"]["authority_passed"],
            "parse_status": attempts["original_parse"]["parse_status"],
            "provider": attempts["original_output"]["provider"],
            "model": attempts["original_output"]["model"],
            "no_signal_flag": original_payload["no_signal_flag"],
            "confidence": original_payload["confidence"],
            "early_reaction_5m_direction": original_payload["early_reaction_5m_direction"],
            "path": original_payload["path"],
        },
        "replacement_attempt": {
            "attempt_category": attempts["replacement_output"]["attempt_category"],
            "authority_passed": attempts["replacement_authority"]["authority_passed"],
            "parse_status": attempts["replacement_parse"]["parse_status"],
            "provider": attempts["replacement_output"]["provider"],
            "model": attempts["replacement_output"]["model"],
            "no_signal_flag": replacement_payload["no_signal_flag"],
            "confidence": replacement_payload["confidence"],
            "early_reaction_5m_direction": replacement_payload["early_reaction_5m_direction"],
            "path": replacement_payload["path"],
        },
        "repeated_type_failure": {
            "field": "confidence",
            "expected_type": "numeric int or float in [0,1]",
            "original_value": original_payload["confidence"],
            "replacement_value": replacement_payload["confidence"],
        },
    }


def build_stop_retry_rationale() -> dict[str, Any]:
    return {
        "forecast_call_id": TARGET_CALL_ID,
        "decision": "NO_FURTHER_RETRY_FOR_TERMINAL_SCHEMA_FAILURE",
        "scientific_rationale": [
            "Two independently dispatched attempts produced the same decisive schema violation.",
            "The frozen prompt did not explicitly state that numeric confidence remained mandatory for NO_SIGNAL.",
            "The parser and schema implementation did require numeric confidence in [0,1].",
            "Another unchanged call would repeat sampling in pursuit of a compliant format.",
            "Selection after repeated attempts could introduce response-selection bias.",
        ],
        "boundary": "This closure is a provider-format failure, not a forecast-accuracy result.",
        "downstream_rule": "The invalid response must not enter downstream forecast evaluation.",
    }


def build_batch_003_final_accounting() -> dict[str, Any]:
    return {
        "batch_id": TARGET_BATCH_ID,
        "frozen_calls": 12,
        "executed_call_identities": 12,
        "authoritative_valid_results": 11,
        "terminal_provider_schema_failures": 1,
        "unattempted_calls": 0,
        "remote_state_unknown_calls": 0,
        "provider_authority_conflicts": 0,
        "duplicate_authoritative_results": 0,
        "cumulative_authoritative_valid_results": 35,
        "remaining_planned_valid_result_slots": 529,
    }


def build_prompt_contract_test_results(step6_module: Any) -> dict[str, Any]:
    def no_signal_payload(confidence_value: Any, *, include_confidence: bool = True) -> dict[str, Any]:
        payload = {
            "no_signal_flag": True,
            "no_signal_reason": "insufficient conviction",
            "immediate_impulse_direction": None,
            "immediate_impulse_peak_pips_min": None,
            "immediate_impulse_peak_pips_max": None,
            "immediate_impulse_confidence": None,
            "early_reaction_5m_direction": "UNCERTAIN",
            "expected_reversal_flag": None,
            "expected_reversal_horizon_min": None,
            "expected_path_summary": "no directional edge",
            "information_used": ["rates"],
            "missing_information": [],
            "invalidation_condition": "surprise",
            "path": [],
        }
        if include_confidence:
            payload["confidence"] = confidence_value
        return payload

    test_results: list[dict[str, Any]] = []
    accepted = [
        ("NO_SIGNAL confidence=0.0", no_signal_payload(0.0)),
        ("NO_SIGNAL confidence=0.5", no_signal_payload(0.5)),
        ("NO_SIGNAL confidence=1.0", no_signal_payload(1.0)),
    ]
    for name, payload in accepted:
        step6_module.normalize_provider_output(payload)
        test_results.append({"name": name, "result": "PERMITTED"})
    rejected = [
        ("NO_SIGNAL confidence=null", no_signal_payload(None), "PROVIDER_OUTPUT_TYPES"),
        ("NO_SIGNAL confidence omitted", no_signal_payload(0.0, include_confidence=False), "PROVIDER_OUTPUT_FIELDS"),
    ]
    for name, payload, expected_error in rejected:
        try:
            step6_module.normalize_provider_output(payload)
        except Exception as exc:  # pragma: no cover - asserted below
            test_results.append({"name": name, "result": "REJECTED", "error": str(exc), "expected_error": expected_error})
        else:  # pragma: no cover
            raise AssertionError(f"{name} unexpectedly passed")
    return {
        "prompt_explicit_requirement": ADDED_PROMPT_SENTENCE,
        "results": test_results,
    }


def build_prompt_lineage_and_impact(step6_module: Any) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    planning_run = FORECAST_PLANNING_ROOT / FORECAST_PLAN_RUN_ID
    batch_manifest = read_jsonl(planning_run / "forecast_batch_manifest.jsonl")
    authorized_calls = read_jsonl(planning_run / "authorized_forecast_call_ledger.jsonl")
    prompt_manifest = read_jsonl(planning_run / "prompt_fingerprint_ledger.jsonl")
    prompt_manifest_by_call = {row["forecast_call_id"]: row for row in prompt_manifest}
    future_batches = [
        row for row in batch_manifest
        if (
            row["pack_type"] == "PACK_A" and row["first_execution_order"] >= 37
        ) or row["pack_type"] == "PACK_E"
    ]
    future_batch_ids = [row["batch_id"] for row in future_batches]
    future_calls = [row for row in authorized_calls if row["batch_id"] in future_batch_ids]
    prompt_rows = [prompt_manifest_by_call[row["forecast_call_id"]] for row in future_calls]
    affected_call_ids = [row["forecast_call_id"] for row in future_calls]
    providers = sorted({f"{row['provider']}/{row['model']}" for row in future_calls})
    first_eligible_future_batch = future_batches[0]["batch_id"] if future_batches else None
    lineage = {
        "prior_prompt_version": step6_module.PROMPT_VERSION,
        "new_prompt_version": step6_module.FUTURE_NO_SIGNAL_PROMPT_VERSION,
        "exact_added_sentence": ADDED_PROMPT_SENTENCE,
        "prior_prompt_instruction_fingerprint": step6_module.prompt_instruction_fingerprint(),
        "new_prompt_instruction_fingerprint": step6_module.prompt_instruction_fingerprint(
            include_future_no_signal_confidence_clarification=True,
        ),
        "first_eligible_future_batch": first_eligible_future_batch,
        "affected_providers": providers,
        "affected_unexecuted_call_count": len(future_calls),
        "affected_unexecuted_prompt_payload_fingerprint_count": len({row["prompt_text_fingerprint"] for row in prompt_rows}),
    }
    impact = {
        "manifests_changed": False,
        "frozen_completed_batches_unchanged": ["FCB_PACK_A_001", "FCB_PACK_A_002", "FCB_PACK_A_003"],
        "affected_future_batch_count": len(future_batches),
        "affected_future_batches": future_batch_ids,
        "affected_future_call_count": len(future_calls),
        "affected_pack_counts": {
            "PACK_A": sum(1 for row in future_calls if row["pack_type"] == "PACK_A"),
            "PACK_E": sum(1 for row in future_calls if row["pack_type"] == "PACK_E"),
        },
        "existing_frozen_manifests_include_prompt_fingerprints": True,
        "frozen_manifest_prompt_fingerprint_regeneration_required_if_applied": True,
        "example_affected_call_ids": affected_call_ids[:12],
    }
    migration_plan = {
        "authorization_required": True,
        "manifests_changed_in_this_move": False,
        "smallest_plan_aligned_migration": [
            "Prepare a new prompt version and fingerprint without changing any completed Batch 001–003 evidence.",
            "Inventory all unexecuted PACK_A and PACK_E forecast calls whose frozen prompt payload fingerprints would change.",
            "Regenerate future prompt payload fingerprints and prompt manifests only after explicit authorization.",
            "Preserve Pack rows, providers, models, and historical cutoffs unchanged.",
            "Preserve forecast_call_id only where governance explicitly deems the forward-looking prompt-version amendment scientifically compatible; otherwise mint new future-only call identities.",
            "Record old and new prompt lineage append-only for every affected future call.",
        ],
    }
    return lineage, impact, migration_plan


def build_drifting_warning() -> dict[str, Any]:
    return {
        "warning": "DRIFTING WARNING",
        "deviation": "Add explicit numeric-confidence language for NO_SIGNAL to future prompts.",
        "expected_benefit": "Reduce repeated null-confidence responses and avoid preventable schema failures.",
        "risk_and_cost": "Future prompt fingerprints differ from Batches 001–003 and may introduce a small prompt-version comparability boundary.",
        "smallest_plan_aligned_alternative": "Add exactly one response-format sentence while preserving every scientific instruction and the existing schema.",
        "authorization": "Explicit authorization is required before applying the new prompt to unexecuted frozen manifests.",
    }


def build_future_prompt_clarification(step6_module: Any) -> dict[str, Any]:
    return {
        "prior_prompt_version": step6_module.PROMPT_VERSION,
        "new_prompt_version": step6_module.FUTURE_NO_SIGNAL_PROMPT_VERSION,
        "exact_added_sentence": ADDED_PROMPT_SENTENCE,
        "insertion_section": "existing response-format / NO_SIGNAL instruction section",
        "prior_prompt_instruction": step6_module.prompt_instruction_text(),
        "new_prompt_instruction": step6_module.prompt_instruction_text(
            include_future_no_signal_confidence_clarification=True,
        ),
    }


def build_governing_manifest() -> dict[str, Any]:
    return {
        "forecast_plan_run_id": FORECAST_PLAN_RUN_ID,
        "batch_003_execution_run_id": BATCH_003_EXECUTION_RUN_ID,
        "batch_003_diagnosis_run_id": BATCH_003_DIAGNOSIS_RUN_ID,
        "batch_003_governance_recovery_run_id": BATCH_003_GOVERNANCE_RECOVERY_RUN_ID,
        "batch_003_final_diagnosis_run_id": BATCH_003_FINAL_DIAGNOSIS_RUN_ID,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()

    from automation import run_presignal_v21_single_event_path_pair_v1_1 as step6

    timestamp = now_timestamp()
    fingerprint = sha256_json(
        {
            "target_call_id": TARGET_CALL_ID,
            "timestamp": timestamp,
            "action": "batch_003_closure_and_future_no_signal_prompt_clarification",
        }
    )[7:19]
    run_id = f"{RUN_PREFIX}-{timestamp}-{fingerprint}"
    run_dir = OUTPUT_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    attempts = load_target_attempts()
    terminal_schema_failure_record = build_terminal_schema_failure_record(attempts)
    attempt_comparison = build_attempt_comparison(attempts)
    stop_retry_rationale = build_stop_retry_rationale()
    batch_003_final_accounting = build_batch_003_final_accounting()
    future_prompt_clarification = build_future_prompt_clarification(step6)
    prompt_version_lineage, impact_analysis, migration_plan = build_prompt_lineage_and_impact(step6)
    prompt_contract_test_results = build_prompt_contract_test_results(step6)
    drifting_warning = build_drifting_warning()

    closure_decision = {
        "batch_003_closure_decision": "FORECAST_BATCH_003_EXECUTION_COMPLETE_WITH_ONE_TERMINAL_SCHEMA_FAILURE",
        "retry_decision": "NO_FURTHER_RETRY_FOR_TERMINAL_SCHEMA_FAILURE",
        "prompt_clarification_decision": "FUTURE_NO_SIGNAL_PROMPT_CLARIFICATION_PREPARED",
        "next_phase_decision": "FUTURE_MANIFEST_MIGRATION_AUTHORIZATION_REQUIRED",
    }

    summary = {
        "batch_003_terminal_call_id": TARGET_CALL_ID,
        "batch_003_authoritative_valid_results": batch_003_final_accounting["authoritative_valid_results"],
        "batch_003_terminal_schema_failures": batch_003_final_accounting["terminal_provider_schema_failures"],
        "cumulative_authoritative_valid_results": batch_003_final_accounting["cumulative_authoritative_valid_results"],
        "remaining_planned_valid_result_slots": batch_003_final_accounting["remaining_planned_valid_result_slots"],
        "affected_future_batch_count": impact_analysis["affected_future_batch_count"],
        "affected_future_call_count": impact_analysis["affected_future_call_count"],
    }

    run_manifest = {
        "run_id": run_id,
        "object": "presignal_batch_003_closure_and_future_no_signal_prompt_clarification_run",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "repository": str(ROOT),
        "branch": git_branch(),
        "start_head": git_head(),
        "expected_start_head": "18c20ee3f7147e18cad7d85f0b64dc7bbfb73672",
        "expected_start_head_exists_locally": commit_exists("18c20ee3f7147e18cad7d85f0b64dc7bbfb73672"),
    }

    write_json(run_dir / "run_manifest.json", run_manifest)
    write_json(run_dir / "governing_artifact_manifest.json", build_governing_manifest())
    write_json(
        run_dir / "batch_003_closure_contract.json",
        {
            "target_call_id": TARGET_CALL_ID,
            "terminal_classification": TERMINAL_CLASSIFICATION,
            "terminal_reason": TERMINAL_REASON,
            "no_provider_calls": True,
            "no_retries": True,
            "no_batch_004_execution": True,
        },
    )
    write_json(run_dir / "terminal_schema_failure_record.json", terminal_schema_failure_record)
    write_json(run_dir / "attempt_comparison.json", attempt_comparison)
    write_json(run_dir / "stop_retry_rationale.json", stop_retry_rationale)
    write_json(run_dir / "batch_003_final_accounting.json", batch_003_final_accounting)
    write_json(run_dir / "batch_003_closure_decision.json", {"decision": closure_decision["batch_003_closure_decision"]})
    write_json(run_dir / "drifting_warning.json", drifting_warning)
    write_json(run_dir / "future_prompt_clarification.json", future_prompt_clarification)
    write_json(run_dir / "prompt_version_lineage.json", prompt_version_lineage)
    write_json(run_dir / "unexecuted_manifest_impact_analysis.json", impact_analysis)
    write_json(run_dir / "future_manifest_migration_plan.json", migration_plan)
    write_json(run_dir / "prompt_contract_test_results.json", prompt_contract_test_results)
    write_json(run_dir / "closure_summary.json", summary)
    write_json(run_dir / "closure_decision.json", closure_decision)

    print(run_id)


if __name__ == "__main__":
    main()
