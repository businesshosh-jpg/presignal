#!/usr/bin/env python3
"""Call-free audit for Batch 003 historical Attention row-status failures."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import bind_presignal_v21_step8_r3_runtime_v1 as binding
from automation import execute_presignal_v21_attention_batch_001 as batch_base
from automation import execute_presignal_v21_attention_batch_003 as batch003
from automation import export_authoritative_v2_attention_map_v1 as historical_attention

PLAN_ID = "PPHB-R1-ATTENTION-EXECUTION-PLAN-20260729T010207Z-3fcd59f96f3c"
BATCH_001_CLOSED_ID = "PPHB-R1-ATTENTION-BATCH-001-CLOSED-20260729T035345Z-e3bc0c2909ca"
BATCH_002_CLOSED_ID = "PPHB-R1-ATTENTION-BATCH-002-CLOSED-20260729T044448Z-97d9ec4cf579"
BATCH_003_EXEC_ID = "PPHB-R1-ATTENTION-EXECUTION-BATCH-003-20260729T045507Z-64f3c4f5fc50"

OUTPUT_AUDIT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_contract_repair"
OUTPUT_EXEC_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_execution"

PLAN_ROOT = OUTPUT_EXEC_ROOT.parent / "presignal_v21_full_round_1_attention_execution_plan" / PLAN_ID
BATCH_001_CLOSED_ROOT = OUTPUT_EXEC_ROOT / BATCH_001_CLOSED_ID
BATCH_002_CLOSED_ROOT = OUTPUT_EXEC_ROOT / BATCH_002_CLOSED_ID
BATCH_003_EXEC_ROOT = OUTPUT_EXEC_ROOT / BATCH_003_EXEC_ID

FAILED_CALL_IDS = [
    "ATN_c6e73d4b0bd438cdd970",
    "ATN_592af0718bf939d9ecb6",
]
CANONICAL_OBJECT = "session_attention_map"
SELECTABLE_STATUS = "parsed"


class Batch003RowStatusAuditError(RuntimeError):
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


def stripped_json_text(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return text


def materialize_run(root: Path, prefix: str, fixed_timestamp: str | None = None) -> Path:
    stamp = fixed_timestamp or now_stamp()
    seed = {
        "plan_id": PLAN_ID,
        "batch_003_exec_id": BATCH_003_EXEC_ID,
        "failed_calls": FAILED_CALL_IDS,
        "timestamp": stamp,
        "prefix": prefix,
    }
    run_id = prefix + stamp + "-" + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:12]
    return root / run_id


def load_governing_state() -> dict[str, Any]:
    for path in (PLAN_ROOT, BATCH_001_CLOSED_ROOT, BATCH_002_CLOSED_ROOT, BATCH_003_EXEC_ROOT):
        if not path.exists():
            raise Batch003RowStatusAuditError("GOVERNING_ARTIFACT_MISSING:" + path.name)
    failed_rows = read_jsonl(BATCH_003_EXEC_ROOT / "failed_call_ledger.jsonl")
    if sorted(row["call_id"] for row in failed_rows) != sorted(FAILED_CALL_IDS):
        raise Batch003RowStatusAuditError("FAILED_CALL_SET_DRIFT")
    valid_rows = read_jsonl(BATCH_003_EXEC_ROOT / "normalized_attention_results.jsonl")
    if len(valid_rows) != 10:
        raise Batch003RowStatusAuditError("ORIGINAL_VALID_RESULT_COUNT_MISMATCH")

    state = {
        "runtime_contract": batch_base.load_runtime_contract(),
        "calls": {row["call_id"]: row for row in batch003.load_batch_calls()},
        "failed_rows": failed_rows,
        "valid_rows": valid_rows,
        "raw_rows": {row["call_id"]: row for row in read_jsonl(BATCH_003_EXEC_ROOT / "raw_provider_outputs.jsonl")},
        "transport_rows": {row["call_id"]: row for row in read_jsonl(BATCH_003_EXEC_ROOT / "raw_transport_results.jsonl")},
        "authority_rows": {row["call_id"]: row for row in read_jsonl(BATCH_003_EXEC_ROOT / "provider_authority_results.jsonl")},
        "validation_rows": {row["call_id"]: row for row in read_jsonl(BATCH_003_EXEC_ROOT / "attention_validation_results.jsonl")},
    }
    _, state["members_by_session"] = batch_base.read_source_sessions()
    for call_id in FAILED_CALL_IDS:
        for key in ("calls", "raw_rows", "transport_rows", "authority_rows", "validation_rows"):
            if call_id not in state[key]:
                raise Batch003RowStatusAuditError("FAILED_CALL_ARTIFACT_MISSING:" + call_id + ":" + key)
    return state


def canonical_status_vocabulary() -> dict[str, Any]:
    return {
        "canonical_status_values": sorted(historical_attention.GOOGLE_ALLOWED_STATUSES),
        "status_meanings": {
            "parsed": "Provider returned an exact Attention item for the event and the event remains selectable.",
            "provider_contract_error": "Provider output violated the Attention response contract and is preserved only as failure evidence.",
            "provider_omitted_event": "Provider returned a dedicated Attention map but omitted an expected event row; preserved evidence only and not selectable.",
        },
        "case_sensitivity": "STRICT",
        "separator_rules": "NO_VARIANT_SEPARATORS_DEFINED",
        "legacy_status_forms_exist": False,
        "status_controls_scientific_selection": True,
        "strict_validator_behavior": {
            "batch_execution_requires": SELECTABLE_STATUS,
            "execution_validator_error": "ATTENTION_ROW_STATUS_INVALID",
        },
    }


def classify_status_value(status: str) -> str:
    if status == SELECTABLE_STATUS:
        return "EXACT_CANONICAL_VALUE_NOT_RECOGNIZED"
    if status == "provider_omitted_event":
        return "SCIENTIFICALLY_DIFFERENT_STATUS"
    if status == "provider_contract_error":
        return "SCIENTIFICALLY_DIFFERENT_STATUS"
    if status in historical_attention.GOOGLE_ALLOWED_STATUSES:
        return "LEGACY_EQUIVALENT_STATUS"
    if not status:
        return "MISSING_STATUS"
    return "AMBIGUOUS_STATUS"


def inventory_failed_rows(state: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    inventory: list[dict[str, Any]] = []
    equivalence_audit: list[dict[str, Any]] = []
    local_validation: list[dict[str, Any]] = []
    for call_id in FAILED_CALL_IDS:
        call = state["calls"][call_id]
        raw_row = state["raw_rows"][call_id]
        transport = state["transport_rows"][call_id]
        authority = state["authority_rows"][call_id]
        validation = state["validation_rows"][call_id]
        payload = json.loads(stripped_json_text(raw_row["raw_output"]))
        expected_members = list(state["members_by_session"][call["source_session_id"]])
        returned_items = [item for item in payload.get("attention_items", []) if isinstance(item, Mapping)]
        returned_event_ids = {str(item.get("event_id")) for item in returned_items if str(item.get("event_id"))}
        missing_members = [member for member in expected_members if member["event_id"] not in returned_event_ids]
        invalid_statuses = sorted({status for status in validation["validation_details"]["statuses"] if status != SELECTABLE_STATUS})
        inventory.append(
            {
                "call_id": call_id,
                "source_session_id": call["source_session_id"],
                "raw_evidence_reference": path_ref(BATCH_003_EXEC_ROOT / "raw_provider_outputs.jsonl"),
                "manifest_provider": call["provider"],
                "manifest_model": call["model"],
                "transport_provider": transport.get("actual_provider"),
                "transport_model": transport.get("actual_model"),
                "raw_claimed_provider": payload.get("provider"),
                "json_parse_result": "PARSED",
                "invalid_row_count": len(missing_members),
                "exact_invalid_status_values": invalid_statuses,
                "row_identities_containing_them": [
                    {
                        "event_id": member["event_id"],
                        "indicator_name": member.get("indicator_name"),
                        "release_ts": member.get("release_ts"),
                        "raw_claimed_status": "provider_omitted_event",
                    }
                    for member in missing_members
                ],
                "canonical_statuses_expected": [SELECTABLE_STATUS],
                "all_other_validation_fields": {
                    "provider_authority_decision": authority.get("authority_decision"),
                    "provider_authority_agreement": authority.get("authority_agreement"),
                    "event_membership_expected_count": len(expected_members),
                    "attention_item_count_returned": len(returned_items),
                    "validation_error_code": validation.get("error_code"),
                },
            }
        )
        for status in invalid_statuses:
            classification = classify_status_value(status)
            equivalence_audit.append(
                {
                    "call_id": call_id,
                    "source_session_id": call["source_session_id"],
                    "original_status": status,
                    "classification": classification,
                    "canonical_status": None,
                    "evidence_of_equivalence": [],
                    "equivalence_proven": False,
                    "scientific_selection_changed_if_normalized": status != SELECTABLE_STATUS,
                }
            )
        local_validation.append(
            {
                "call_id": call_id,
                "source_session_id": call["source_session_id"],
                "provider": call["provider"],
                "model": call["model"],
                "parse_result": "PARSED_VALID",
                "validation_result": "FAILED_VALIDATION",
                "error_code": "ATTENTION_ROW_STATUS_INVALID",
                "missing_event_ids": [member["event_id"] for member in missing_members],
                "missing_event_count": len(missing_members),
                "scientific_fields_changed": False,
            }
        )
    return inventory, equivalence_audit, local_validation


def build_remaining_failed_rows(
    state: Mapping[str, Any],
    local_validation: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_call = {row["call_id"]: row for row in local_validation}
    rows = []
    for call_id in FAILED_CALL_IDS:
        call = state["calls"][call_id]
        validation = by_call[call_id]
        rows.append(
            {
                "call_id": call_id,
                "provider": call["provider"],
                "model": call["model"],
                "source_session_id": call["source_session_id"],
                "failure_stage": validation["validation_result"],
                "exact_remaining_reason": validation["error_code"],
                "preserved_response_usability": "PARSED_BUT_SCIENTIFICALLY_INCOMPLETE",
                "retry_required": True,
                "retry_recommendation": "RETRY_FAILED_BATCH_003_CALLS_REQUIRES_AUTHORIZATION",
            }
        )
    return rows


def create_closure_run(*args: Any, **kwargs: Any) -> None:
    raise Batch003RowStatusAuditError("BATCH_003_CLOSURE_NOT_SUPPORTED_FOR_UNRECOVERED_RESPONSES")


def run_audit(
    *,
    audit_output_root: Path = OUTPUT_AUDIT_ROOT,
    exec_output_root: Path = OUTPUT_EXEC_ROOT,
    fixed_timestamp: str | None = None,
    create_closure: bool = True,
) -> dict[str, Any]:
    state = load_governing_state()
    audit_dir = materialize_run(
        audit_output_root,
        "PPHB-R1-ATTENTION-ROW-STATUS-AUDIT-BATCH-003-",
        fixed_timestamp=fixed_timestamp,
    )
    audit_dir.mkdir(parents=True, exist_ok=False)

    status_contract = canonical_status_vocabulary()
    inventory, equivalence_audit, local_validation = inventory_failed_rows(state)
    local_parse = [
        {
            "call_id": row["call_id"],
            "parse_result": "PARSED_VALID",
            "raw_statuses_preserved": True,
            "raw_claimed_statuses": ["provider_omitted_event"] * row["invalid_row_count"],
        }
        for row in inventory
    ]
    remaining_rows = build_remaining_failed_rows(state, local_validation)
    recovered_rows: list[dict[str, Any]] = []
    accepted_normalizations: list[dict[str, Any]] = []
    rejected_statuses = sorted({row["original_status"] for row in equivalence_audit})

    write_json(
        audit_dir / "run_manifest.json",
        {
            "run_id": audit_dir.name,
            "generated_at": now_iso(),
            "start_head": git_head(),
            "provider_calls_executed": 0,
            "pack_construction_executed": 0,
            "forecast_calls_executed": 0,
            "google_writes": 0,
            "governing_batch_003_execution_identity": BATCH_003_EXEC_ID,
        },
    )
    write_json(
        audit_dir / "governing_artifact_manifest.json",
        {
            "governing_plan_identity": PLAN_ID,
            "governing_batch_001_closure_identity": BATCH_001_CLOSED_ID,
            "governing_batch_002_closure_identity": BATCH_002_CLOSED_ID,
            "governing_batch_003_execution_identity": BATCH_003_EXEC_ID,
            "paths": {
                "plan_root": path_ref(PLAN_ROOT),
                "batch_001_closed_root": path_ref(BATCH_001_CLOSED_ROOT),
                "batch_002_closed_root": path_ref(BATCH_002_CLOSED_ROOT),
                "batch_003_execution_root": path_ref(BATCH_003_EXEC_ROOT),
            },
        },
    )
    write_jsonl(audit_dir / "failed_row_status_inventory.jsonl", inventory)
    write_json(audit_dir / "canonical_status_contract.json", status_contract)
    write_jsonl(audit_dir / "status_equivalence_audit.jsonl", equivalence_audit)
    write_json(
        audit_dir / "status_normalization_contract.json",
        {
            "accepted_normalizations": accepted_normalizations,
            "rejected_statuses": rejected_statuses,
            "allowed_object": CANONICAL_OBJECT,
            "allowed_route": "historical session_attention_map row-status parsing only",
            "raw_status_preservation_requirement": True,
            "scientific_fields_changed": False,
            "failure_behavior": "FAIL_CLOSED_ON_PROVIDER_OMITTED_EVENT_OR_ANY_UNPROVEN_STATUS",
        },
    )
    write_jsonl(audit_dir / "normalization_application_ledger.jsonl", [])
    write_jsonl(audit_dir / "local_parse_results.jsonl", local_parse)
    write_jsonl(audit_dir / "local_validation_results.jsonl", local_validation)
    write_jsonl(audit_dir / "recovered_attention_results.jsonl", recovered_rows)
    write_jsonl(audit_dir / "remaining_failed_calls.jsonl", remaining_rows)
    write_json(
        audit_dir / "audit_reconciliation.json",
        {
            "failed_response_count": len(inventory),
            "originally_valid_result_count": len(state["valid_rows"]),
            "locally_recovered_result_count": len(recovered_rows),
            "remaining_failed_count": len(remaining_rows),
            "new_provider_call_count": 0,
            "duplicate_call_count": 0,
            "unexpected_call_count": 0,
            "full_recovery_supported": False,
        },
    )
    write_json(
        audit_dir / "audit_summary.json",
        {
            "canonical_attention_contract_identity": CANONICAL_OBJECT,
            "runtime_contract_version": state["runtime_contract"]["contract_version"],
            "failed_calls": FAILED_CALL_IDS,
            "invalid_statuses": rejected_statuses,
            "row_status_decision": "provider_omitted_event is a preserved omission state, not a canonical parsed-row synonym",
        },
    )
    write_json(
        audit_dir / "audit_decision.json",
        {
            "audit_status": "ATTENTION_ROW_STATUS_AUDIT_COMPLETE",
            "status_decision": "ROW_STATUS_MISMATCH_SUBSTANTIVE",
            "recovery_decision": "NO_RESPONSES_RECOVERABLE",
            "batch_decision": "ATTENTION_BATCH_003_REMAINS_PARTIALLY_COMPLETE",
            "scaling_decision": "RETRY_FAILED_BATCH_003_CALLS_REQUIRES_AUTHORIZATION",
        },
    )

    closure_dir = None
    if create_closure and recovered_rows:
        closure_dir = materialize_run(
            exec_output_root,
            "PPHB-R1-ATTENTION-BATCH-003-CLOSED-",
            fixed_timestamp=fixed_timestamp,
        )
        create_closure_run()

    return {
        "audit_dir": audit_dir,
        "closure_dir": closure_dir,
        "inventory": inventory,
        "recovered_rows": recovered_rows,
        "remaining_rows": remaining_rows,
        "audit_status": "ATTENTION_ROW_STATUS_AUDIT_COMPLETE",
        "status_decision": "ROW_STATUS_MISMATCH_SUBSTANTIVE",
        "recovery_decision": "NO_RESPONSES_RECOVERABLE",
        "batch_decision": "ATTENTION_BATCH_003_REMAINS_PARTIALLY_COMPLETE",
        "scaling_decision": "RETRY_FAILED_BATCH_003_CALLS_REQUIRES_AUTHORIZATION",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-output-root", type=Path, default=OUTPUT_AUDIT_ROOT)
    parser.add_argument("--execution-output-root", type=Path, default=OUTPUT_EXEC_ROOT)
    parser.add_argument("--fixed-timestamp")
    parser.add_argument("--skip-closure", action="store_true")
    args = parser.parse_args(argv)
    result = run_audit(
        audit_output_root=args.audit_output_root,
        exec_output_root=args.execution_output_root,
        fixed_timestamp=args.fixed_timestamp,
        create_closure=not args.skip_closure,
    )
    print(
        json.dumps(
            {
                "audit_dir": path_ref(result["audit_dir"]),
                "closure_dir": path_ref(result["closure_dir"]) if result["closure_dir"] else None,
                "audit_status": result["audit_status"],
                "status_decision": result["status_decision"],
                "recovery_decision": result["recovery_decision"],
                "batch_decision": result["batch_decision"],
                "scaling_decision": result["scaling_decision"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
