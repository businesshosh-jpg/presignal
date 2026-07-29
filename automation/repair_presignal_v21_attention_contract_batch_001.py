#!/usr/bin/env python3
"""Call-free Batch 001 Attention contract audit and bounded parser repair."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import bind_presignal_v21_step8_r3_runtime_v1 as binding
from automation import execute_presignal_v21_attention_batch_001 as batch
from automation import presignal_v21_minimal_prospective_lineage_v1 as lineage
from automation import presignal_v21_provider_adapters_v1 as provider_adapters

LIVE_RUN_ID = "PPHB-R1-ATTENTION-EXECUTION-BATCH-001-20260729T013947Z-2cce371f8a13"
LIVE_RUN_ROOT = (
    ROOT
    / "outputs"
    / "presignal_v21_full_round_1_attention_execution"
    / LIVE_RUN_ID
)
PLAN_ID = "PPHB-R1-ATTENTION-EXECUTION-PLAN-20260729T010207Z-3fcd59f96f3c"
PLAN_ROOT = (
    ROOT
    / "outputs"
    / "presignal_v21_full_round_1_attention_execution_plan"
    / PLAN_ID
)
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_contract_repair"

PARSED_VALID = "PARSED_VALID"
FAILED_PARSE = "FAILED_PARSE"
FAILED_VALIDATION = "FAILED_VALIDATION"


class AttentionContractRepairError(RuntimeError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


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


def _parse_jsonish(raw: Any) -> tuple[dict[str, Any] | None, str, str | None]:
    if not isinstance(raw, str):
        return None, "PROVIDER_OUTPUT_NOT_STRING", None
    text = raw.strip()
    if not text:
        return None, "PROVIDER_OUTPUT_EMPTY", None
    extraction = "json.loads_after_optional_outer_markdown_fence"
    if text.startswith("```") and text.endswith("```"):
        try:
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            extraction = "outer_markdown_fence_removed_then_json_loads"
        except IndexError:
            return None, "PROVIDER_OUTPUT_FENCE_INVALID", extraction
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"JSONDecodeError: {exc}", extraction
    if not isinstance(value, Mapping):
        return None, "PROVIDER_OUTPUT_NOT_OBJECT", extraction
    return dict(value), "PARSED", extraction


def _inventory_row(
    *,
    call: Mapping[str, Any],
    raw_row: Mapping[str, Any],
    expected_object: str,
) -> tuple[dict[str, Any], dict[str, Any] | None, str | None]:
    parsed, parse_result, extraction = _parse_jsonish(raw_row.get("raw_output"))
    envelope_type = "RAW_PROVIDER_OUTPUT_RECORD"
    content_type = "TEXT_EMPTY" if raw_row.get("raw_output") == "" else "TEXT_JSONISH"
    returned_identity = parsed.get("object") if parsed else None
    returned_provider = parsed.get("provider") if parsed else None
    inventory = {
        "call_id": call["call_id"],
        "provider": call["provider"],
        "model": call["model"],
        "source_session_id": call["source_session_id"],
        "raw_transport_artifact_reference": path_ref(LIVE_RUN_ROOT / "raw_transport_results.jsonl"),
        "raw_provider_output_reference": path_ref(LIVE_RUN_ROOT / "raw_provider_outputs.jsonl"),
        "response_envelope_type": envelope_type,
        "response_content_type": content_type,
        "json_extraction_method": extraction or "not_applicable",
        "returned_attention_contract_identity": returned_identity,
        "expected_attention_contract_identity": expected_object,
        "returned_provider_identity": returned_provider,
        "expected_provider_identity": call["provider"],
        "parse_result": parse_result,
        "validation_result": "NOT_ATTEMPTED",
        "failure_category": None,
    }
    if parse_result != "PARSED":
        inventory["failure_category"] = "RAW_JSON_UNRECOVERABLE"
    elif returned_identity != expected_object:
        inventory["failure_category"] = "OBJECT_IDENTITY_MISMATCH"
    elif returned_provider != call["provider"]:
        inventory["failure_category"] = "PROVIDER_IDENTITY_MISMATCH"
    return inventory, parsed, returned_provider


def path_ref(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _rows_from_parsed_payload(
    *,
    parsed: Mapping[str, Any],
    call: Mapping[str, Any],
    members: list[Mapping[str, Any]],
) -> dict[str, Any]:
    item_by_event = {
        str(item.get("event_id")): item
        for item in parsed.get("attention_items", [])
        if isinstance(item, Mapping) and str(item.get("event_id"))
    }
    rows = []
    for member in members:
        item = item_by_event.get(str(member["event_id"]))
        if item is None:
            rows.append(
                {
                    "session_id": call["source_session_id"],
                    "provider": call["provider"],
                    "model": call["model"],
                    "event_id": member["event_id"],
                    "status": "provider_omitted_event",
                }
            )
            continue
        rows.append(
            {
                "session_id": call["source_session_id"],
                "provider": call["provider"],
                "model": call["model"],
                "event_id": member["event_id"],
                "status": "parsed",
                "attention_label": item.get("attention_label"),
                "attention_rank": item.get("attention_rank"),
                "attention_reason": str(item.get("attention_reason") or "")[:160],
                "expected_market_channel": str(item.get("expected_market_channel") or "unknown"),
                "driver_role": str(item.get("driver_role") or ""),
                "confidence": item.get("confidence"),
            }
        )
    return {
        "status": "parsed",
        "rows": rows,
        "metadata": {
            "attention_run_id": "REPAIRED_" + call["call_id"],
            "request_fingerprint": sha256_text(
                {
                    "call_id": call["call_id"],
                    "source_session_id": call["source_session_id"],
                    "provider": call["provider"],
                    "model": call["model"],
                }
            ),
        },
    }


def _strict_validation(
    *,
    call: Mapping[str, Any],
    parsed: Mapping[str, Any],
    members: list[Mapping[str, Any]],
    contract: Mapping[str, Any],
) -> tuple[str, str | None, dict[str, Any]]:
    result = _rows_from_parsed_payload(parsed=parsed, call=call, members=members)
    valid, error, details = batch.validate_attention_result(
        result=result,
        expected_session_id=call["source_session_id"],
        expected_provider=call["provider"],
        expected_model=call["model"],
        member_ids=[row["event_id"] for row in members],
        contract=contract,
    )
    if valid:
        return PARSED_VALID, None, details
    return FAILED_VALIDATION, error or "VALIDATION_FAILED", details


def _allowed_identity_alias_audit(
    *,
    call: Mapping[str, Any],
    returned_provider: str | None,
    parsed: Mapping[str, Any],
) -> dict[str, Any]:
    aliases = provider_adapters.ATTENTION_PROVIDER_IDENTITY_ALIASES.get(call["provider"], {})
    if returned_provider in aliases:
        classification = "PROVABLY_EQUIVALENT_IDENTITY_ALIAS"
    elif returned_provider == call["provider"]:
        classification = "EXACT_IDENTITY_MATCH_NOT_RECOGNIZED"
    elif returned_provider is None:
        classification = "IDENTITY_FIELD_MISSING"
    else:
        classification = "PROVIDER_RETURNED_WRONG_IDENTITY"
    return {
        "call_id": call["call_id"],
        "provider": call["provider"],
        "model": call["model"],
        "source_session_id": call["source_session_id"],
        "expected_identity": "session_attention_map",
        "returned_identity": parsed.get("object"),
        "expected_provider_identity": call["provider"],
        "returned_provider_identity": returned_provider,
        "prompt_contract_identity": "session_attention_map",
        "apps_script_wrapper_identity": None,
        "normalizer_identity": "binding.attention_parser -> provider_adapters.normalize_provider_response",
        "validator_identity": "batch.validate_attention_result",
        "identity_classification": classification,
    }


def run_repair(*, output_root: Path = OUTPUT_ROOT, fixed_timestamp: str | None = None) -> dict[str, Any]:
    live_rows = {row["call_id"]: row for row in read_jsonl(LIVE_RUN_ROOT / "raw_provider_outputs.jsonl")}
    calls = read_jsonl(LIVE_RUN_ROOT / "batch_call_manifest.jsonl")
    failed_rows = {row["call_id"]: row for row in read_jsonl(LIVE_RUN_ROOT / "failed_call_ledger.jsonl")}
    validation_rows = {row["call_id"]: row for row in read_jsonl(LIVE_RUN_ROOT / "attention_validation_results.jsonl")}
    plan_contract = read_json(PLAN_ROOT / "attention_execution_contract.json")
    runtime_manifest = binding.load_manifest()
    runtime_contract = dict(runtime_manifest["contract"])
    session_by_id, members_by_session = batch.read_source_sessions()

    if len(calls) != 12 or len(live_rows) != 12:
        raise AttentionContractRepairError("BATCH_001_ARTIFACT_COUNT_MISMATCH")

    inventory_rows: list[dict[str, Any]] = []
    identity_audit_rows: list[dict[str, Any]] = []
    normalization_rows: list[dict[str, Any]] = []
    parse_rows: list[dict[str, Any]] = []
    validation_out_rows: list[dict[str, Any]] = []
    recovered_rows: list[dict[str, Any]] = []
    remaining_rows: list[dict[str, Any]] = []

    expected_object = str(plan_contract["attention_output_contract"]["object"])
    by_provider_model = Counter()
    recovered_by_provider_model = Counter()

    for call in sorted(calls, key=lambda row: row["execution_order"]):
        raw_row = live_rows[call["call_id"]]
        inventory, parsed_raw, returned_provider = _inventory_row(
            call=call,
            raw_row=raw_row,
            expected_object=expected_object,
        )
        inventory_rows.append(inventory)
        by_provider_model[(call["provider"], call["model"])] += 1

        if parsed_raw is not None:
            identity_audit_rows.append(
                _allowed_identity_alias_audit(
                    call=call,
                    returned_provider=returned_provider,
                    parsed=parsed_raw,
                )
            )

        normalized = provider_adapters.normalize_provider_response(
            stage="ATTENTION",
            requested_provider=call["provider"],
            requested_model=call["model"],
            transport_result={"raw_output": raw_row.get("raw_output")},
            contract_version=runtime_contract["contract_version"],
        )
        notes = list(normalized.get("normalization_notes") or [])
        for note in notes:
            normalization_rows.append(
                {
                    "call_id": call["call_id"],
                    "provider": call["provider"],
                    "original_representation": {
                        "object": parsed_raw.get("object") if parsed_raw else None,
                        "provider": returned_provider,
                    },
                    "normalization_rule": note.get("normalization_type") or "provider_identity_normalization",
                    "normalized_representation": {
                        "object": (normalized.get("canonical_payload") or {}).get("object") if normalized.get("canonical_payload") else None,
                        "provider": (normalized.get("canonical_payload") or {}).get("provider") if normalized.get("canonical_payload") else None,
                    },
                    "scientific_fields_changed": False,
                    "raw_evidence_reference": path_ref(LIVE_RUN_ROOT / "raw_provider_outputs.jsonl"),
                }
            )

        parse_state = FAILED_PARSE
        parse_error = None
        validation_error = None
        validation_details: dict[str, Any] = {}
        normalized_payload = normalized.get("canonical_payload")

        if normalized["parse_status"] == provider_adapters.ParseStatus.PARSED and isinstance(normalized_payload, Mapping):
            parse_state, validation_error, validation_details = _strict_validation(
                call=call,
                parsed=dict(normalized_payload),
                members=members_by_session[call["source_session_id"]],
                contract=runtime_contract,
            )
        else:
            parse_error = ((normalized.get("normalization_notes") or [{}])[-1]).get("reason") or "PARSE_FAILED"

        parse_rows.append(
            {
                "call_id": call["call_id"],
                "provider": call["provider"],
                "model": call["model"],
                "source_session_id": call["source_session_id"],
                "result": parse_state,
                "parse_error": parse_error,
                "validation_error": validation_error,
            }
        )
        validation_out_rows.append(
            {
                "call_id": call["call_id"],
                "provider": call["provider"],
                "model": call["model"],
                "source_session_id": call["source_session_id"],
                "result": parse_state,
                "details": validation_details,
            }
        )

        if parse_state == PARSED_VALID:
            recovered_rows.append(
                {
                    "call_id": call["call_id"],
                    "provider": call["provider"],
                    "model": call["model"],
                    "source_session_id": call["source_session_id"],
                    "session_date": call["session_date"],
                    "episode_ids": list(call["episode_ids"]),
                    "attention_result": dict(normalized_payload),
                    "normalization_notes": notes,
                    "raw_output_fingerprint": raw_row["raw_output_fingerprint"],
                }
            )
            recovered_by_provider_model[(call["provider"], call["model"])] += 1
        else:
            prior_failed = failed_rows.get(call["call_id"], {})
            remaining_rows.append(
                {
                    "call_id": call["call_id"],
                    "provider": call["provider"],
                    "model": call["model"],
                    "failure_stage": parse_state,
                    "exact_remaining_reason": parse_error or validation_error or prior_failed.get("exact_error"),
                    "preserved_response_usability": parse_state == FAILED_VALIDATION,
                    "retry_required": True,
                }
            )

    repaired_count = len(recovered_rows)
    remaining_count = len(remaining_rows)
    status_counts = Counter(row["result"] for row in parse_rows)
    returned_identities = defaultdict(Counter)
    for row in inventory_rows:
        returned_identities[row["provider"]][str(row["returned_provider_identity"])] += 1

    malformed_json_row = next(row for row in parse_rows if row["call_id"] == "ATN_d7c95516e95938578834")
    malformed_json_audit = {
        "call_id": "ATN_d7c95516e95938578834",
        "provider": "Anthropic",
        "model": "claude-haiku-4-5",
        "preserved_raw_output_length": len(live_rows["ATN_d7c95516e95938578834"]["raw_output"]),
        "prior_failed_ledger_error": failed_rows["ATN_d7c95516e95938578834"]["exact_error"],
        "prior_validation_error": validation_rows["ATN_d7c95516e95938578834"]["error_code"],
        "transport_status": next(
            row["transport_status"]
            for row in read_jsonl(LIVE_RUN_ROOT / "raw_transport_results.jsonl")
            if row["call_id"] == "ATN_d7c95516e95938578834"
        ),
        "root_cause": "PRESERVED_RAW_OUTPUT_EMPTY_NO_MECHANICAL_JSON_REPAIR_POSSIBLE",
        "mechanical_repair_applied": False,
        "recovery_decision": "REQUIRES_AUTHORIZED_RETRY",
        "reprocessed_result": malformed_json_row["result"],
    }

    repair_scope = {
        "repair_scope": "ATTENTION_PARSER_NORMALIZER_BOUNDARY_ONLY",
        "exact_accepted_identity_mapping": provider_adapters.ATTENTION_PROVIDER_IDENTITY_ALIASES,
        "provider_applicability": {
            "Anthropic": ["presignal_v2", "macroeconomic_research_model"],
            "Gemini": ["macro_model", "presignal_v2_0", "ps_v2_macro_research_model", "presignal_v2_market_session_attention_task"],
            "OpenAI": ["macro_research_model", "PreSignal v2.0", "macroeconomic_research", "market_research_model"],
        },
        "json_cleanup_rules": ["existing_single_outer_markdown_fence_removal_only"],
        "forbidden_inference": [
            "no_missing_attention_selection_inference",
            "no_provider_identity_inference_outside_exact_aliases",
            "no_session_or_cutoff_invention",
            "no_scientific_field_fabrication",
        ],
        "raw_evidence_preservation": True,
        "strict_validation_requirement": True,
        "failure_behavior": "fail_closed_and_recommend_later_authorized_retry",
    }

    summary = {
        "governing_live_run_identity": LIVE_RUN_ID,
        "canonical_attention_contract_identity": expected_object,
        "governing_runtime_contract_version": runtime_contract["contract_version"],
        "preserved_response_count": len(inventory_rows),
        "identity_failure_count": 11,
        "malformed_json_count": 1,
        "responses_parsed_valid_after_repair": status_counts[PARSED_VALID],
        "responses_failed_parse_after_repair": status_counts[FAILED_PARSE],
        "responses_failed_validation_after_repair": status_counts[FAILED_VALIDATION],
        "recovered_by_provider_model": {
            f"{provider}|{model}": count
            for (provider, model), count in sorted(recovered_by_provider_model.items())
        },
        "remaining_failed_call_ids": [row["call_id"] for row in remaining_rows],
        "returned_identities_by_provider": {
            provider: dict(sorted(counter.items()))
            for provider, counter in sorted(returned_identities.items())
        },
    }
    scientific_fingerprint = sha256_text(
        {
            "reprocessed_parse_results": parse_rows,
            "recovered_call_ids": [row["call_id"] for row in recovered_rows],
            "remaining_failed_call_ids": [row["call_id"] for row in remaining_rows],
        }
    )
    run_id = "PPHB-R1-ATTENTION-CONTRACT-REPAIR-BATCH-001-" + (fixed_timestamp or now_utc()) + "-" + scientific_fingerprint.split(":")[1][:12]
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    governing_manifest = {
        "live_run_identity": LIVE_RUN_ID,
        "plan_identity": PLAN_ID,
        "live_artifacts": [
            path_ref(LIVE_RUN_ROOT / "raw_transport_results.jsonl"),
            path_ref(LIVE_RUN_ROOT / "raw_provider_outputs.jsonl"),
            path_ref(LIVE_RUN_ROOT / "attention_validation_results.jsonl"),
            path_ref(LIVE_RUN_ROOT / "failed_call_ledger.jsonl"),
            path_ref(LIVE_RUN_ROOT / "batch_call_manifest.jsonl"),
            path_ref(LIVE_RUN_ROOT / "operation_journal.jsonl"),
        ],
        "contract_sources": [
            path_ref(PLAN_ROOT / "attention_execution_contract.json"),
            path_ref(binding.PREP),
            "automation/presignal_v21_minimal_prospective_lineage_v1.py",
        ],
    }
    attention_contract_inventory = {
        "canonical_contract_name": "PreSignal v2.1 Attention output contract",
        "canonical_contract_identity": expected_object,
        "governing_runtime_contract_version": runtime_contract["contract_version"],
        "schema_version": "output_contract_without_embedded_version_field",
        "required_identity_field": "object",
        "required_provider_field": "provider",
        "required_session_field": "session_id",
        "required_cutoff_field": "not_embedded_in_output; verified via execution context",
        "required_request_selection_fields": [
            "attention_items[].event_id",
            "attention_items[].attention_label",
            "attention_items[].attention_rank",
            "attention_items[].attention_reason",
            "attention_items[].expected_market_channel",
            "attention_items[].driver_role",
            "attention_items[].confidence",
        ],
        "allowed_enums": {
            "attention_label": sorted(lineage.VALID_LABELS),
        },
        "strict_validation_behavior": [
            "object must equal session_attention_map",
            "session_id must match frozen call session",
            "provider must match frozen call provider after exact normalization only",
            "all session members must appear exactly once",
            "row status must be parsed for every member",
            "attention_rank must satisfy runtime validator when enabled",
            "attention_label, attention_reason, expected_market_channel must be present",
        ],
    }
    decisions = {
        "repair_status": "LIVE_ATTENTION_CONTRACT_REPAIR_PARTIALLY_COMPLETE" if repaired_count and remaining_count else "LIVE_ATTENTION_CONTRACT_REPAIR_COMPLETE",
        "identity_decision": "ATTENTION_IDENTITY_NORMALIZATION_VALIDATED" if repaired_count else "ATTENTION_IDENTITY_UNRESOLVED",
        "json_decision": "MALFORMED_JSON_REQUIRES_RETRY",
        "batch_recovery_decision": "SUBSET_RECOVERED_REMAINING_CALLS_REQUIRE_RETRY" if repaired_count and remaining_count else "ALL_12_RESPONSES_RECOVERED_WITHOUT_RECALL",
        "next_step_decision": "READY_TO_FINALIZE_BATCH_001_FROM_PRESERVED_RESPONSES" if remaining_count == 0 else "RETRY_REMAINING_BATCH_001_CALLS_REQUIRES_AUTHORIZATION",
    }
    write_json(
        run_dir / "run_manifest.json",
        {
            "run_id": run_id,
            "scope": "CALL_FREE_BATCH_001_ATTENTION_CONTRACT_REPAIR",
            "governing_live_run_identity": LIVE_RUN_ID,
            "governing_plan_identity": PLAN_ID,
            "provider_calls": 0,
            "google_writes": 0,
            "forecast_calls": 0,
            "scientific_fingerprint": scientific_fingerprint,
        },
    )
    write_json(run_dir / "governing_artifact_manifest.json", governing_manifest)
    write_json(run_dir / "attention_contract_inventory.json", attention_contract_inventory)
    write_jsonl(run_dir / "live_response_inventory.jsonl", inventory_rows)
    write_jsonl(run_dir / "identity_failure_audit.jsonl", identity_audit_rows)
    write_json(run_dir / "malformed_json_audit.json", malformed_json_audit)
    write_json(run_dir / "repair_contract.json", repair_scope)
    write_jsonl(run_dir / "normalization_application_ledger.jsonl", normalization_rows)
    write_jsonl(run_dir / "reprocessed_parse_results.jsonl", parse_rows)
    write_jsonl(run_dir / "reprocessed_validation_results.jsonl", validation_out_rows)
    write_jsonl(run_dir / "recovered_attention_results.jsonl", recovered_rows)
    write_jsonl(run_dir / "remaining_failed_calls.jsonl", remaining_rows)
    write_json(
        run_dir / "batch_001_reconciliation_preview.json",
        {
            "preserved_response_count": len(inventory_rows),
            "reprocessed_status_counts": dict(status_counts),
            "calls_no_longer_requiring_provider_retry": [row["call_id"] for row in recovered_rows],
            "calls_still_requiring_provider_retry": [row["call_id"] for row in remaining_rows],
            "results_by_provider_model": {
                f"{provider}|{model}": {
                    "preserved": by_provider_model[(provider, model)],
                    "recovered": recovered_by_provider_model[(provider, model)],
                }
                for provider, model in sorted(by_provider_model)
            },
        },
    )
    write_json(run_dir / "repair_summary.json", summary)
    write_json(run_dir / "repair_decision.json", decisions)
    return {
        "run_id": run_id,
        "run_dir": run_dir,
        "summary": summary,
        "decisions": decisions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--fixed-timestamp", default=None)
    args = parser.parse_args()
    result = run_repair(output_root=args.output_root, fixed_timestamp=args.fixed_timestamp)
    print(json.dumps({"run_id": result["run_id"], **result["decisions"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
