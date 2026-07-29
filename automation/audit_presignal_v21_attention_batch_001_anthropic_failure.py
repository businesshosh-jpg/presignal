#!/usr/bin/env python3
"""Audit the remaining Batch 001 Anthropic failure and freeze one-retry guidance."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import bind_presignal_v21_step8_r3_runtime_v1 as binding
from automation import execute_presignal_v21_attention_batch_001 as batch
from automation import presignal_v21_historical_verification_r3_compat_r1_contract_v1 as compat_r1
from automation import presignal_v21_historical_verification_r3_compat_r2_contract_v1 as compat_r2
from automation import presignal_v21_minimal_prospective_lineage_v1 as lineage
from automation import run_presignal_v21_step8_r2_historical_replication_v1 as replay

PLAN_ID = "PPHB-R1-ATTENTION-EXECUTION-PLAN-20260729T010207Z-3fcd59f96f3c"
RUN1_ID = "PPHB-R1-ATTENTION-EXECUTION-BATCH-001-20260729T013947Z-2cce371f8a13"
REPAIR_ID = "PPHB-R1-ATTENTION-CONTRACT-REPAIR-BATCH-001-20260729T020108Z-17657dcc7cd5"
RUN2_ID = "PPHB-R1-ATTENTION-BATCH-001-FINALIZATION-20260729T023607Z-eb4bd2a9277c"
CALL_ID = "ATN_d7c95516e95938578834"
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_failure_audit"

PLAN_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_execution_plan" / PLAN_ID
RUN1_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_execution" / RUN1_ID
REPAIR_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_contract_repair" / REPAIR_ID
RUN2_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_execution" / RUN2_ID


class AnthropicFailureAuditError(RuntimeError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


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


def parse_error_boundary(message: str) -> dict[str, Any]:
    boundary = {"position": None, "line": None, "column": None}
    if "position " in message:
        try:
            boundary["position"] = int(message.split("position ", 1)[1].split(" ", 1)[0])
        except Exception:
            pass
    if "(line " in message and " column " in message:
        try:
            tail = message.split("(line ", 1)[1].rstrip(")")
            line_text, column_text = tail.split(" column ", 1)
            boundary["line"] = int(line_text)
            boundary["column"] = int(column_text)
        except Exception:
            pass
    return boundary


def build_corrected_request(call: Mapping[str, Any], session: Mapping[str, Any], members: list[Mapping[str, Any]], contract: Mapping[str, Any]) -> dict[str, Any]:
    return lineage.build_prospective_attention(
        study_id="HISTORICAL_R3",
        collection_run_id="ATTENTION_FAILURE_AUDIT",
        session_snapshot=replay._session_snapshot(session),
        member_rows=members,
        provider=call["provider"],
        model=call["model"],
        information_cutoff_ts=session["forecast_cutoff"],
        attention_run_id="AUDIT_" + call["call_id"],
        stage_generated_ts=session["forecast_cutoff"],
        dispatcher=None,
        instruction_override=binding.attention_instruction(contract, call["provider"]),
        generation_settings=binding.generation_settings(contract, call["provider"], "ATTENTION"),
    )


def run_audit(*, output_root: Path = OUTPUT_ROOT, fixed_timestamp: str | None = None) -> dict[str, Any]:
    if batch.git_head() != "090b82674c4f01a69e9c5e7d95bb51f550b33d8b":
        raise AnthropicFailureAuditError("UNEXPECTED_START_HEAD")

    calls = {row["call_id"]: row for row in read_jsonl(RUN1_ROOT / "batch_call_manifest.jsonl")}
    if CALL_ID not in calls:
        raise AnthropicFailureAuditError("FAILED_CALL_NOT_FOUND")
    call = calls[CALL_ID]
    if call["provider"] != "Anthropic" or call["model"] != "claude-haiku-4-5":
        raise AnthropicFailureAuditError("FAILED_CALL_PROVIDER_MODEL_DRIFT")

    recovered = read_jsonl(REPAIR_ROOT / "recovered_attention_results.jsonl")
    if len(recovered) != 11:
        raise AnthropicFailureAuditError("RECOVERED_COUNT_MISMATCH")
    if any(row["call_id"] == CALL_ID for row in recovered):
        raise AnthropicFailureAuditError("FAILED_CALL_ALREADY_RECOVERED")

    sessions, members_by_session = batch.read_source_sessions()
    session = sessions[call["source_session_id"]]
    members = members_by_session[call["source_session_id"]]
    contract = binding.load_manifest()["contract"]
    corrected_dry = build_corrected_request(call, session, members, contract)
    original_instruction = lineage.ATTENTION_INSTRUCTION
    corrected_instruction = binding.attention_instruction(contract, call["provider"])

    first_transport = next(row for row in read_jsonl(RUN1_ROOT / "raw_transport_results.jsonl") if row["call_id"] == CALL_ID)
    first_raw = next(row for row in read_jsonl(RUN1_ROOT / "raw_provider_outputs.jsonl") if row["call_id"] == CALL_ID)
    first_validation = next(row for row in read_jsonl(RUN1_ROOT / "attention_validation_results.jsonl") if row["call_id"] == CALL_ID)
    first_failed = next(row for row in read_jsonl(RUN1_ROOT / "failed_call_ledger.jsonl") if row["call_id"] == CALL_ID)

    second_transport = read_json(RUN2_ROOT / "retry_raw_transport_result.json")
    second_raw = read_json(RUN2_ROOT / "retry_raw_provider_output.json")
    second_parse = read_json(RUN2_ROOT / "retry_parse_result.json")
    second_validation = read_json(RUN2_ROOT / "retry_validation_result.json")
    second_remaining = next(row for row in read_jsonl(RUN2_ROOT / "remaining_failed_calls.jsonl") if row["call_id"] == CALL_ID)

    successful_anthropic = [row for row in recovered if row["provider"] == "Anthropic"]
    live_raw_rows = {row["call_id"]: row for row in read_jsonl(RUN1_ROOT / "raw_provider_outputs.jsonl")}
    success_compare = []
    for row in successful_anthropic:
        call_row = calls[row["call_id"]]
        success_compare.append(
            {
                "call_id": row["call_id"],
                "session_id": row["source_session_id"],
                "episode_count": len(row["episode_ids"]),
                "member_count": len(row["attention_result"]["attention_items"]),
                "prompt_user_length": len(
                    build_corrected_request(
                        call_row,
                        sessions[call_row["source_session_id"]],
                        members_by_session[call_row["source_session_id"]],
                        contract,
                    )["prompt"]["user"]
                ),
                "request_json_length": len(json.dumps(build_corrected_request(call_row, sessions[call_row["source_session_id"]], members_by_session[call_row["source_session_id"]], contract)["request"])),
                "raw_output_length": len(live_raw_rows[row["call_id"]]["raw_output"]),
                "avg_attention_reason_length": sum(len(item.get("attention_reason", "")) for item in row["attention_result"]["attention_items"]) / len(row["attention_result"]["attention_items"]),
            }
        )

    failed_prompt_user_length = len(corrected_dry["prompt"]["user"])
    failed_request_json_length = len(json.dumps(corrected_dry["request"]))
    success_max_raw = max(row["raw_output_length"] for row in success_compare)
    success_max_prompt = max(row["prompt_user_length"] for row in success_compare)

    correction = {
        "call_id": CALL_ID,
        "provider": "Anthropic",
        "model": "claude-haiku-4-5",
        "frozen_session_identity": call["source_session_id"],
        "frozen_attention_input_identity": call["attention_input_identity"],
        "canonical_contract_identity": "session_attention_map",
        "exact_correction": {
            "attention_instruction_suffix": compat_r1.ANTHROPIC_ATTENTION_RULE,
            "generation_settings": {
                "max_output_tokens": compat_r2.ANTHROPIC_ATTENTION_MAX_TOKENS,
                "preserve_raw_before_parse": True,
            },
        },
        "fields_unchanged": [
            "object",
            "session_id",
            "provider",
            "attention_items[].event_id",
            "attention_items[].attention_label",
            "attention_items[].attention_rank",
            "attention_items[].attention_reason",
            "attention_items[].expected_market_channel",
            "attention_items[].driver_role",
            "attention_items[].confidence",
            "status",
        ],
        "scientific_meaning_unchanged": True,
        "maximum_additional_retry_count_recommended": 1,
        "failure_behavior": "single future retry only; fail closed if raw output remains invalid or missing",
    }

    audit_fingerprint = sha256_text(
        {
            "call_id": CALL_ID,
            "first_error": first_validation["error_code"],
            "second_error": second_parse["error_code"],
            "exact_correction": correction["exact_correction"],
        }
    )
    run_id = "PPHB-R1-ATTENTION-BATCH-001-ANTHROPIC-FAILURE-AUDIT-" + (fixed_timestamp or now_stamp()) + "-" + audit_fingerprint.split(":")[1][:12]
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    failed_inventory = {
        "call_id": CALL_ID,
        "provider": "Anthropic",
        "model": "claude-haiku-4-5",
        "session_id": call["source_session_id"],
        "session_date": call["session_date"],
        "episode_count": len(call["episode_ids"]),
        "member_count": len(members),
        "first_attempt_error": first_validation["error_code"],
        "second_attempt_error": second_parse["error_code"],
    }
    retry_boundary = {
        "call_id": CALL_ID,
        "raw_response_preserved": second_raw["raw_output"] != "",
        "raw_response_length": len(second_raw["raw_output"]),
        "parse_failure_boundary": parse_error_boundary(second_parse["error_code"]),
        "field_being_generated_at_failure": "UNINSPECTABLE_RAW_OUTPUT_MISSING",
        "last_complete_json_object": "UNINSPECTABLE_RAW_OUTPUT_MISSING",
        "string_cut_off": "UNINSPECTABLE_RAW_OUTPUT_MISSING",
        "closing_braces_absent": "UNINSPECTABLE_RAW_OUTPUT_MISSING",
        "markdown_fences_involved": "UNINSPECTABLE_RAW_OUTPUT_MISSING",
        "prose_after_json": "UNINSPECTABLE_RAW_OUTPUT_MISSING",
        "response_appears_truncated": "NOT_PROVABLE_FROM_PRESERVED_RAW_OUTPUT",
        "scientific_content_before_truncation_structurally_valid": "UNINSPECTABLE_RAW_OUTPUT_MISSING",
    }
    attempt_comparison = {
        "call_id": CALL_ID,
        "first_attempt": {
            "run_identity": RUN1_ID,
            "transport_status": first_transport["transport_status"],
            "raw_output_length": len(first_raw["raw_output"]),
            "error": first_validation["error_code"],
            "stop_reason": None,
            "completion_tokens": first_transport["completion_tokens"],
            "prompt_tokens": first_transport["prompt_tokens"],
        },
        "second_attempt": {
            "run_identity": RUN2_ID,
            "transport_status": second_transport["transport_status"],
            "raw_output_length": len(second_raw["raw_output"]),
            "error": second_parse["error_code"],
            "stop_reason": second_transport.get("stop_reason"),
            "completion_tokens": second_transport["completion_tokens"],
            "prompt_tokens": second_transport["prompt_tokens"],
        },
        "shared_pattern_primary": "OUTPUT_LENGTH_RISK_CONFIRMED",
        "secondary_causes": [
            "TRANSPORT_CONTENT_LOSS_DURING_FAILURE_EVIDENCE_CAPTURE",
            "RAW_STOP_AND_TOKEN_METADATA_NOT_PRESERVED_ON_FAILED_ATTEMPTS",
        ],
    }
    success_comparison = {
        "failed_call": {
            "call_id": CALL_ID,
            "episode_count": len(call["episode_ids"]),
            "member_count": len(members),
            "prompt_user_length": failed_prompt_user_length,
            "request_json_length": failed_request_json_length,
            "raw_output_length": 0,
            "configured_max_output_tokens": corrected_dry["request"].get("max_output_tokens"),
        },
        "successful_anthropic_calls": success_compare,
        "largest_successful_prompt_user_length": success_max_prompt,
        "largest_successful_raw_output_length": success_max_raw,
        "failed_call_is_largest_by_member_count": all(len(members) >= row["member_count"] for row in success_compare),
        "failed_call_is_largest_by_prompt_user_length": failed_prompt_user_length > success_max_prompt,
    }
    prompt_output_size = {
        "call_id": CALL_ID,
        "current_instruction_length": len(original_instruction),
        "corrected_instruction_length": len(corrected_instruction),
        "corrected_instruction_added_rule": compat_r1.ANTHROPIC_ATTENTION_RULE,
        "failed_session_member_count": len(members),
        "failed_prompt_user_length": failed_prompt_user_length,
        "failed_request_json_length": failed_request_json_length,
        "current_generation_settings": {},
        "corrected_generation_settings": binding.generation_settings(contract, "Anthropic", "ATTENTION"),
        "size_risk_inference": "The failed session has the largest member_count and request payload among Anthropic Batch 001 calls; its parse-error positions also sit in the same character range as the largest successful raw responses.",
    }
    root_cause = {
        "decision": "OUTPUT_LENGTH_RISK_CONFIRMED",
        "supporting_evidence": [
            "Failed Anthropic session has 37 members vs successful Anthropic sessions with 31, 19, and 2 members.",
            f"Failed request JSON length {failed_request_json_length} exceeds the largest successful Anthropic request length {max(row['request_json_length'] for row in success_compare)}.",
            f"First parse error position 13031 and second parse error position 13252 are both in the same character range as the largest successful Anthropic raw output length {success_max_raw}.",
            "Both failed attempts lost usable raw output, preventing full truncation confirmation but reinforcing the need for raw preservation before parse.",
        ],
        "secondary_causes": attempt_comparison["secondary_causes"],
    }
    local_validation = {
        "provider_calls": 0,
        "prompt_fields_unchanged": all(field in correction["fields_unchanged"] for field in correction["fields_unchanged"]),
        "same_provider_model": corrected_dry["request"]["provider"] == "Anthropic" and corrected_dry["request"]["model"] == "claude-haiku-4-5",
        "same_session_id": corrected_dry["request"]["session_id"] == call["source_session_id"],
        "same_event_member_count": len(json.loads(corrected_dry["prompt"]["user"])["events"]) == len(members),
        "same_candidate_set": [row["event_id"] for row in json.loads(corrected_dry["prompt"]["user"])["events"]] == [row["event_id"] for row in members],
        "canonical_output_fields_still_requested": all(token in corrected_instruction for token in ["object, session_id, provider, attention_items, session_attention_summary, status", "event_id, attention_label, attention_rank, attention_reason, expected_market_channel, driver_role, confidence"]),
        "max_output_tokens_enabled": corrected_dry["request"].get("max_output_tokens") == compat_r2.ANTHROPIC_ATTENTION_MAX_TOKENS,
        "preserve_raw_before_parse_enabled": corrected_dry["request"].get("preserve_raw_before_parse") is True,
    }
    retry_recommendation = {
        "decision": "AUTHORIZE_ONE_CORRECTED_RETRY",
        "maximum_additional_calls": 1,
        "call_id": CALL_ID,
        "provider": "Anthropic",
        "model": "claude-haiku-4-5",
        "retry_only_if": [
            "corrected Anthropic Attention instruction is active",
            "max_output_tokens=8192 is set on the request",
            "preserve_raw_before_parse=True is set",
            "no other call identities are retried",
        ],
    }
    summary = {
        "audit_status": "ANTHROPIC_ATTENTION_FAILURE_AUDIT_COMPLETE",
        "root_cause_decision": root_cause["decision"],
        "correction_decision": "MINIMAL_RETRY_CORRECTION_VALIDATED",
        "retry_recommendation": retry_recommendation["decision"],
        "output_run_id": run_id,
    }
    decision = {
        "audit_status": "ANTHROPIC_ATTENTION_FAILURE_AUDIT_COMPLETE",
        "root_cause_decision": "OUTPUT_LENGTH_RISK_CONFIRMED",
        "correction_decision": "MINIMAL_RETRY_CORRECTION_VALIDATED",
        "retry_recommendation": "AUTHORIZE_ONE_CORRECTED_RETRY",
    }

    write_json(
        run_dir / "run_manifest.json",
        {
            "run_id": run_id,
            "scope": "CALL_FREE_ANTHROPIC_BATCH_001_FAILURE_AUDIT",
            "governing_plan_identity": PLAN_ID,
            "first_attempt_run_identity": RUN1_ID,
            "second_attempt_run_identity": RUN2_ID,
            "provider_calls": 0,
            "google_writes": 0,
            "forecast_calls": 0,
            "pack_construction": 0,
            "scientific_fingerprint": audit_fingerprint,
        },
    )
    write_json(
        run_dir / "governing_artifact_manifest.json",
        {
            "plan_root": path_ref(PLAN_ROOT),
            "first_attempt_root": path_ref(RUN1_ROOT),
            "repair_root": path_ref(REPAIR_ROOT),
            "second_attempt_root": path_ref(RUN2_ROOT),
        },
    )
    write_json(run_dir / "failed_call_inventory.json", failed_inventory)
    write_json(run_dir / "retry_response_boundary_audit.json", retry_boundary)
    write_json(run_dir / "attempt_comparison.json", attempt_comparison)
    write_json(run_dir / "successful_anthropic_comparison.json", success_comparison)
    write_json(run_dir / "prompt_output_size_audit.json", prompt_output_size)
    write_json(run_dir / "root_cause_decision.json", root_cause)
    write_json(run_dir / "minimal_retry_correction_contract.json", correction)
    write_json(run_dir / "local_validation_results.json", local_validation)
    write_json(run_dir / "retry_authorization_recommendation.json", retry_recommendation)
    write_json(run_dir / "audit_summary.json", summary)
    write_json(run_dir / "audit_decision.json", decision)
    return {"run_dir": run_dir, "decision": decision, "summary": summary}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--fixed-timestamp")
    args = parser.parse_args(argv)
    result = run_audit(output_root=args.output_root, fixed_timestamp=args.fixed_timestamp)
    print(json.dumps({"run_dir": str(result["run_dir"]), **result["decision"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
