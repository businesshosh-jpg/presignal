#!/usr/bin/env python3
"""Call-free audit and recovery for preserved Batch 002 Attention identity failures."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import bind_presignal_v21_step8_r3_runtime_v1 as binding
from automation import execute_presignal_v21_attention_batch_001 as batch_base
from automation import execute_presignal_v21_attention_batch_002 as batch002
from automation import presignal_v21_provider_adapters_v1 as provider_adapters

PLAN_ID = "PPHB-R1-ATTENTION-EXECUTION-PLAN-20260729T010207Z-3fcd59f96f3c"
BATCH_001_CLOSED_ID = "PPHB-R1-ATTENTION-BATCH-001-CLOSED-20260729T035345Z-e3bc0c2909ca"
BATCH_002_EXEC_ID = "PPHB-R1-ATTENTION-EXECUTION-BATCH-002-20260729T040014Z-e270ec415b79"
OUTPUT_AUDIT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_contract_repair"
OUTPUT_EXEC_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_execution"
AUTHORITATIVE_ATTENTION_MAP = ROOT / "outputs" / "presignal_v21_attention_preservation" / "authoritative_attention_map.jsonl"
STEP8_SESSION_ROOT = ROOT / "outputs" / "presignal_v21_step8_r2_historical_replication" / "STEP8-R2-e057ba70c884e0e618cf" / "sessions"

PLAN_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_execution_plan" / PLAN_ID
BATCH_001_CLOSED_ROOT = OUTPUT_EXEC_ROOT / BATCH_001_CLOSED_ID
BATCH_002_EXEC_ROOT = OUTPUT_EXEC_ROOT / BATCH_002_EXEC_ID

FAILED_CALL_IDS = [
    "ATN_13cab543ced6509afc8d",
    "ATN_b1f301900a92bb0cf6e3",
    "ATN_19e738b1020396398002",
    "ATN_b015d346ca9e87eeda8e",
    "ATN_8c1a3f57e88abe10bbcc",
    "ATN_2a8b084e0810a910e832",
]
CANONICAL_OBJECT = "session_attention_map"


class Batch002RecoveryError(RuntimeError):
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


def load_governing_state() -> dict[str, Any]:
    for root in (PLAN_ROOT, BATCH_001_CLOSED_ROOT, BATCH_002_EXEC_ROOT):
        if not root.exists():
            raise Batch002RecoveryError("GOVERNING_ARTIFACT_MISSING:" + root.name)
    calls = {row["call_id"]: row for row in batch002.load_batch_calls()}
    failed_rows = read_jsonl(BATCH_002_EXEC_ROOT / "failed_call_ledger.jsonl")
    if sorted(row["call_id"] for row in failed_rows) != sorted(FAILED_CALL_IDS):
        raise Batch002RecoveryError("FAILED_CALL_SET_DRIFT")
    raw_rows = {row["call_id"]: row for row in read_jsonl(BATCH_002_EXEC_ROOT / "raw_provider_outputs.jsonl")}
    transport_rows = {row["call_id"]: row for row in read_jsonl(BATCH_002_EXEC_ROOT / "raw_transport_results.jsonl")}
    valid_rows = read_jsonl(BATCH_002_EXEC_ROOT / "normalized_attention_results.jsonl")
    if len(valid_rows) != 6:
        raise Batch002RecoveryError("ORIGINAL_VALID_RESULT_COUNT_MISMATCH")
    state = {
        "runtime_contract": batch_base.load_runtime_contract(),
        "failed_rows": failed_rows,
        "raw_rows": raw_rows,
        "transport_rows": transport_rows,
        "calls": calls,
        "valid_rows": valid_rows,
    }
    for call_id in FAILED_CALL_IDS:
        if call_id not in calls or call_id not in raw_rows or call_id not in transport_rows:
            raise Batch002RecoveryError("FAILED_RESPONSE_MISSING:" + call_id)
    return state


def provider_label_occurrences(aliases: Iterable[str]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {alias: {} for alias in aliases}
    provider_name_map = {"gemini": "Gemini", "openai": "OpenAI", "anthropic": "Anthropic"}

    for row in read_jsonl(AUTHORITATIVE_ATTENTION_MAP):
        raw = row.get("raw_output") or ""
        provider = str(row.get("provider"))
        for alias in aliases:
            if alias in raw:
                result[alias][provider] = result[alias].get(provider, 0) + 1

    for path in STEP8_SESSION_ROOT.glob("*/attention/*.json"):
        payload = read_json(path)
        raw = ((payload.get("response") or {}).get("raw_output") or payload.get("raw_output") or "")
        provider = provider_name_map.get(path.stem, path.stem)
        for alias in aliases:
            if alias in raw:
                result[alias][provider] = result[alias].get(provider, 0) + 1

    for path in OUTPUT_EXEC_ROOT.glob("*/raw_provider_outputs.jsonl"):
        for row in read_jsonl(path):
            raw = row.get("raw_output") or ""
            provider = str(row.get("provider"))
            for alias in aliases:
                if alias in raw:
                    result[alias][provider] = result[alias].get(provider, 0) + 1
    return result


def inventory_failed_responses(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for failed in state["failed_rows"]:
        call_id = failed["call_id"]
        raw_row = state["raw_rows"][call_id]
        transport = state["transport_rows"][call_id]
        call = state["calls"][call_id]
        payload = json.loads(stripped_json_text(raw_row["raw_output"]))
        rows.append(
            {
                "call_id": call_id,
                "manifest_bound_provider": call["provider"],
                "manifest_bound_model": call["model"],
                "source_session_id": call["source_session_id"],
                "transport_confirmed_provider": transport.get("actual_provider"),
                "transport_confirmed_model": transport.get("actual_model"),
                "returned_object_identity": payload.get("object"),
                "returned_provider_identity": payload.get("provider"),
                "json_parseability_before_provider_normalization": True,
                "required_scientific_field_presence": {
                    "top_level_required_fields_present": all(
                        key in payload for key in ("object", "session_id", "provider", "attention_items", "session_attention_summary", "status")
                    ),
                    "attention_items_count": len(payload.get("attention_items", [])),
                    "item_required_fields_present": all(
                        all(key in item for key in ("event_id", "attention_label", "attention_rank", "attention_reason", "expected_market_channel", "driver_role", "confidence"))
                        for item in payload.get("attention_items", [])
                    ),
                },
                "current_failure": failed["exact_error"],
                "raw_evidence_reference": path_ref(BATCH_002_EXEC_ROOT / "raw_provider_outputs.jsonl"),
            }
        )
    return rows


def classify_identity_rows(inventory: list[dict[str, Any]], occurrences: Mapping[str, Mapping[str, int]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    audits: list[dict[str, Any]] = []
    accepted: dict[str, str] = {}
    existing_aliases = provider_adapters.ATTENTION_PROVIDER_IDENTITY_ALIASES
    for row in inventory:
        alias = str(row["returned_provider_identity"])
        provider = str(row["manifest_bound_provider"])
        model = str(row["manifest_bound_model"])
        observed_providers = sorted(occurrences.get(alias, {}).keys())
        provider_count = len(observed_providers)
        if alias in existing_aliases.get(provider, {}):
            classification = "ALREADY_VALIDATED_ALIAS_NOT_APPLIED"
        elif any(alias.lower() == key.lower() for key in existing_aliases.get(provider, {})):
            classification = "CASE_OR_SEPARATOR_VARIANT_OF_VALIDATED_ALIAS"
        elif provider_count == 1 and observed_providers == [provider]:
            classification = "NEW_PROVIDER_SPECIFIC_ALIAS"
        elif not alias:
            classification = "IDENTITY_MISSING"
        elif provider_count > 1:
            classification = "IDENTITY_AMBIGUOUS"
        else:
            classification = "SUBSTANTIVE_PROVIDER_CONTRADICTION"

        equivalence_proven = (
            row["transport_confirmed_provider"] == provider
            and row["transport_confirmed_model"] == model
            and row["returned_object_identity"] == CANONICAL_OBJECT
            and provider_count == 1
            and observed_providers == [provider]
        )
        if equivalence_proven:
            accepted[alias] = provider

        audits.append(
            {
                "call_id": row["call_id"],
                "manifest_bound_provider": provider,
                "manifest_bound_model": model,
                "returned_provider_identity": alias,
                "observed_provider_routes": observed_providers,
                "observed_provider_route_count": provider_count,
                "classification": classification,
                "equivalence_proven": equivalence_proven,
                "scientific_payload_unchanged": True,
            }
        )
    return audits, accepted


def build_validated_rows(
    payload: Mapping[str, Any],
    *,
    call_id: str,
    session_id: str,
    provider: str,
    model: str,
    members: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    item_by_event = {str(item["event_id"]): dict(item) for item in payload["attention_items"]}
    rows = []
    for member in members:
        item = item_by_event[str(member["event_id"])]
        rows.append(
            {
                "attention_run_id": "RECOVERED_" + call_id,
                "session_id": session_id,
                "provider": provider,
                "model": model,
                "information_cutoff_ts": "",
                "generated_ts": "",
                "request_fingerprint": None,
                "source": "preserved_batch_002_response_recovery",
                "raw_output": None,
                "event_id": member["event_id"],
                "status": "parsed",
                "attention_label": item["attention_label"],
                "attention_rank": item["attention_rank"],
                "attention_reason": item["attention_reason"],
                "expected_market_channel": item["expected_market_channel"],
                "driver_role": item["driver_role"],
                "confidence": item["confidence"],
            }
        )
    return rows


def reprocess_failed_responses(
    state: Mapping[str, Any],
    accepted_aliases: Mapping[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    source_sessions, source_members = batch_base.read_source_sessions()
    parse_rows = []
    validation_rows = []
    recovered_rows = []
    remaining_rows = []
    normalization_rows = []

    for failed in state["failed_rows"]:
        call_id = failed["call_id"]
        call = state["calls"][call_id]
        raw_row = state["raw_rows"][call_id]
        transport = dict(state["transport_rows"][call_id])
        transport["raw_output"] = raw_row["raw_output"]
        alias = json.loads(stripped_json_text(raw_row["raw_output"])).get("provider")
        audit_scope_ok = accepted_aliases.get(alias) == call["provider"]

        if not audit_scope_ok:
            parse_rows.append(
                {
                    "call_id": call_id,
                    "provider": call["provider"],
                    "model": call["model"],
                    "result": "NOT_RECOVERABLE",
                    "returned_provider_identity": alias,
                    "parse_status": "NOT_ATTEMPTED_ALIAS_UNRESOLVED",
                }
            )
            validation_rows.append(
                {
                    "call_id": call_id,
                    "provider": call["provider"],
                    "model": call["model"],
                    "result": "NOT_RECOVERABLE",
                    "validation_ok": False,
                    "validation_error": "IDENTITY_EQUIVALENCE_NOT_PROVEN",
                }
            )
            remaining_rows.append(
                {
                    "call_id": call_id,
                    "provider": call["provider"],
                    "model": call["model"],
                    "failure_stage": "NOT_RECOVERABLE",
                    "exact_remaining_reason": "IDENTITY_EQUIVALENCE_NOT_PROVEN",
                    "preserved_response_usability": "requires governance or explicit retry authorization",
                    "retry_required": True,
                }
            )
            continue

        normalized = provider_adapters.normalize_provider_response(
            stage="ATTENTION",
            requested_provider=call["provider"],
            requested_model=call["model"],
            transport_result=transport,
            contract_version=state["runtime_contract"]["contract_version"],
        )
        parse_result = "FAILED_PARSE"
        validation_ok = False
        validation_error = "PARSE_FAILED"
        details: dict[str, Any] = {}
        payload = None
        built_rows = None
        if normalized["parse_status"] == provider_adapters.ParseStatus.PARSED:
            payload = dict(normalized["canonical_payload"])
            members = source_members[call["source_session_id"]]
            built_rows = build_validated_rows(
                payload,
                call_id=call_id,
                session_id=call["source_session_id"],
                provider=call["provider"],
                model=call["model"],
                members=members,
            )
            validation_ok, validation_error, details = batch_base.validate_attention_result(
                result={"status": "parsed", "rows": built_rows},
                expected_session_id=call["source_session_id"],
                expected_provider=call["provider"],
                expected_model=call["model"],
                member_ids=[row["event_id"] for row in members],
                contract=state["runtime_contract"],
            )
            parse_result = "PARSED_VALID" if validation_ok else "FAILED_VALIDATION"

        parse_rows.append(
            {
                "call_id": call_id,
                "provider": call["provider"],
                "model": call["model"],
                "result": parse_result,
                "returned_provider_identity": alias,
                "parse_status": str(normalized["parse_status"]),
                "normalization_notes": normalized.get("normalization_notes"),
            }
        )
        validation_rows.append(
            {
                "call_id": call_id,
                "provider": call["provider"],
                "model": call["model"],
                "result": parse_result,
                "validation_ok": validation_ok,
                "validation_error": validation_error,
                "validation_details": details,
            }
        )
        if validation_ok and payload is not None and built_rows is not None:
            normalization_rows.append(
                {
                    "call_id": call_id,
                    "provider": call["provider"],
                    "original_representation": alias,
                    "normalization_rule": "provider-scoped preserved Attention identity alias",
                    "normalized_representation": call["provider"],
                    "scientific_fields_changed": False,
                    "raw_evidence_reference": path_ref(BATCH_002_EXEC_ROOT / "raw_provider_outputs.jsonl"),
                }
            )
            recovered_rows.append(
                {
                    "call_id": call_id,
                    "provider": call["provider"],
                    "model": call["model"],
                    "source_session_id": call["source_session_id"],
                    "session_date": call["session_date"],
                    "episode_ids": list(call["episode_ids"]),
                    "attention_result": payload,
                    "result_source": "PRESERVED_BATCH_002_RESPONSE_RECOVERY",
                    "source_live_run_identity": BATCH_002_EXEC_ID,
                }
            )
        else:
            remaining_rows.append(
                {
                    "call_id": call_id,
                    "provider": call["provider"],
                    "model": call["model"],
                    "failure_stage": parse_result,
                    "exact_remaining_reason": validation_error,
                    "preserved_response_usability": "preserved but not admissibly recoverable",
                    "retry_required": True,
                }
            )
    return parse_rows, validation_rows, recovered_rows, remaining_rows, normalization_rows


def create_closure_run(
    *,
    state: Mapping[str, Any],
    recovered_rows: list[dict[str, Any]],
    normalization_rows: list[dict[str, Any]],
    fixed_timestamp: str | None = None,
    exec_output_root: Path = OUTPUT_EXEC_ROOT,
) -> Path:
    ts = fixed_timestamp or now_stamp()
    seed = {"batch_002_exec": BATCH_002_EXEC_ID, "timestamp": ts}
    run_id = "PPHB-R1-ATTENTION-BATCH-002-CLOSED-" + ts + "-" + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:12]
    run_dir = exec_output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    final_rows = [dict(row) for row in state["valid_rows"]] + [dict(row) for row in recovered_rows]
    episode_map = []
    for row in final_rows:
        for episode_id in row["episode_ids"]:
            episode_map.append(
                {
                    "call_id": row["call_id"],
                    "episode_id": episode_id,
                    "source_session_id": row["source_session_id"],
                    "provider": row["provider"],
                    "model": row["model"],
                    "result_source": row["result_source"],
                }
            )

    write_json(
        run_dir / "run_manifest.json",
        {
            "run_id": run_id,
            "generated_at": now_iso(),
            "git_head": git_head(),
            "governing_plan_identity": PLAN_ID,
            "governing_batch_001_closure_identity": BATCH_001_CLOSED_ID,
            "governing_batch_002_execution_identity": BATCH_002_EXEC_ID,
            "provider_calls_executed": 0,
            "google_writes": 0,
            "forecast_calls_executed": 0,
            "pack_construction_executed": 0,
            "research_ai_calls": 0,
            "market_data_calls": 0,
            "web_calls": 0,
        },
    )
    write_json(
        run_dir / "governing_artifact_manifest.json",
        {
            "plan_root": path_ref(PLAN_ROOT),
            "batch_001_closed_root": path_ref(BATCH_001_CLOSED_ROOT),
            "batch_002_exec_root": path_ref(BATCH_002_EXEC_ROOT),
        },
    )
    write_json(
        run_dir / "batch_closure_contract.json",
        {
            "canonical_attention_contract_identity": CANONICAL_OBJECT,
            "imported_original_valid_result_count": len(state["valid_rows"]),
            "recovered_result_count": len(recovered_rows),
            "provider_calls_executed": 0,
            "failure_behavior": "call-free preserved-response recovery only",
        },
    )
    write_jsonl(run_dir / "imported_original_valid_results.jsonl", state["valid_rows"])
    write_jsonl(
        run_dir / "recovered_result_import_ledger.jsonl",
        [
            {
                "call_id": row["call_id"],
                "provider": row["provider"],
                "model": row["model"],
                "source_session_id": row["source_session_id"],
                "import_status": "RECOVERED_PRESERVED_RESULT",
                "provider_recall_performed": False,
            }
            for row in recovered_rows
        ],
    )
    write_jsonl(run_dir / "normalization_application_ledger.jsonl", normalization_rows)
    write_jsonl(run_dir / "final_normalized_attention_results.jsonl", final_rows)
    write_jsonl(run_dir / "final_episode_attention_result_map.jsonl", episode_map)
    write_jsonl(run_dir / "remaining_failed_calls.jsonl", [])
    reconciliation = {
        "planned_calls": 12,
        "imported_original_valid_results": len(state["valid_rows"]),
        "recovered_valid_results": len(recovered_rows),
        "final_validated_results": len(final_rows),
        "remaining_failed_calls": 0,
        "new_provider_calls": 0,
        "duplicate_calls": 0,
        "unexpected_calls": 0,
        "sessions_represented": len({row["source_session_id"] for row in final_rows}),
        "episodes_mapped": len({row["episode_id"] for row in episode_map}),
        "results_by_provider_model": dict(sorted(Counter(f"{row['provider']}|{row['model']}" for row in final_rows).items())),
    }
    write_json(run_dir / "batch_002_reconciliation.json", reconciliation)
    write_json(run_dir / "batch_002_summary.json", reconciliation)
    write_json(
        run_dir / "batch_002_decision.json",
        {
            "batch_decision": "ATTENTION_BATCH_002_CLOSED",
            "scaling_decision": "READY_FOR_ATTENTION_BATCH_003",
        },
    )
    return run_dir


def run_recovery(
    *,
    audit_output_root: Path = OUTPUT_AUDIT_ROOT,
    exec_output_root: Path = OUTPUT_EXEC_ROOT,
    fixed_timestamp: str | None = None,
) -> dict[str, Any]:
    state = load_governing_state()
    inventory = inventory_failed_responses(state)
    aliases = sorted({row["returned_provider_identity"] for row in inventory})
    occurrences = provider_label_occurrences(aliases)
    audits, accepted_aliases = classify_identity_rows(inventory, occurrences)
    parse_rows, validation_rows, recovered_rows, remaining_rows, normalization_rows = reprocess_failed_responses(state, accepted_aliases)

    ts = fixed_timestamp or now_stamp()
    seed = {"batch_002_exec": BATCH_002_EXEC_ID, "timestamp": ts}
    audit_id = "PPHB-R1-ATTENTION-CONTRACT-REPAIR-BATCH-002-" + ts + "-" + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:12]
    audit_dir = audit_output_root / audit_id
    audit_dir.mkdir(parents=True, exist_ok=False)

    alias_rows = []
    for alias in aliases:
        alias_rows.append(
            {
                "returned_alias": alias,
                "provider_route_frequencies": dict(sorted(occurrences.get(alias, {}).items())),
                "frequency": sum(occurrences.get(alias, {}).values()),
            }
        )

    accepted_contract = []
    rejected_contract = []
    accepted_seen: set[tuple[str, str, str]] = set()
    for audit in audits:
        row = {
            "original_alias": audit["returned_provider_identity"],
            "canonical_provider": audit["manifest_bound_provider"],
            "allowed_provider": audit["manifest_bound_provider"],
            "allowed_model": audit["manifest_bound_model"],
            "allowed_object": CANONICAL_OBJECT,
            "manifest_bound_requirement": True,
            "transport_confirmation_requirement": True,
            "exact_scope": "Attention payload parsing only for manifest-bound provider/model with transport confirmation",
            "scientific_fields_changed": False,
            "failure_behavior": "fail closed if strict validation does not pass",
        }
        if audit["equivalence_proven"]:
            key = (row["original_alias"], row["allowed_provider"], row["allowed_model"])
            if key not in accepted_seen:
                accepted_contract.append(row)
                accepted_seen.add(key)
        else:
            rejected_contract.append({**row, "rejection_reason": audit["classification"]})

    write_json(
        audit_dir / "run_manifest.json",
        {
            "run_id": audit_id,
            "generated_at": now_iso(),
            "git_head": git_head(),
            "provider_calls_executed": 0,
            "google_writes": 0,
            "forecast_calls_executed": 0,
            "pack_construction_executed": 0,
            "research_ai_calls": 0,
            "market_data_calls": 0,
            "web_calls": 0,
        },
    )
    write_json(
        audit_dir / "governing_artifact_manifest.json",
        {
            "plan_root": path_ref(PLAN_ROOT),
            "batch_001_closed_root": path_ref(BATCH_001_CLOSED_ROOT),
            "batch_002_exec_root": path_ref(BATCH_002_EXEC_ROOT),
        },
    )
    write_jsonl(audit_dir / "failed_response_inventory.jsonl", inventory)
    write_jsonl(audit_dir / "returned_identity_inventory.jsonl", alias_rows)
    write_jsonl(audit_dir / "alias_equivalence_audit.jsonl", audits)
    write_json(
        audit_dir / "alias_normalization_contract.json",
        {
            "accepted_aliases": accepted_contract,
            "rejected_aliases": rejected_contract,
            "canonical_attention_contract_identity": CANONICAL_OBJECT,
        },
    )
    write_jsonl(audit_dir / "normalization_application_ledger.jsonl", normalization_rows)
    write_jsonl(audit_dir / "reprocessed_parse_results.jsonl", parse_rows)
    write_jsonl(audit_dir / "reprocessed_validation_results.jsonl", validation_rows)
    write_jsonl(audit_dir / "recovered_attention_results.jsonl", recovered_rows)
    write_jsonl(audit_dir / "remaining_failed_calls.jsonl", remaining_rows)
    repair_reconciliation = {
        "failed_preserved_responses": len(inventory),
        "originally_valid_results": len(state["valid_rows"]),
        "locally_recovered_results": len(recovered_rows),
        "responses_still_failed_parse": sum(1 for row in parse_rows if row["result"] == "FAILED_PARSE"),
        "responses_still_failed_validation": sum(1 for row in parse_rows if row["result"] == "FAILED_VALIDATION"),
        "not_recoverable_responses": sum(1 for row in parse_rows if row["result"] == "NOT_RECOVERABLE"),
        "remaining_failed_calls": len(remaining_rows),
        "new_provider_calls": 0,
        "duplicate_calls": 0,
        "unexpected_calls": 0,
    }
    write_json(audit_dir / "repair_reconciliation.json", repair_reconciliation)
    write_json(audit_dir / "repair_summary.json", repair_reconciliation)

    closure_dir = None
    if len(recovered_rows) == len(inventory):
        closure_dir = create_closure_run(
            state=state,
            recovered_rows=recovered_rows,
            normalization_rows=normalization_rows,
            fixed_timestamp=fixed_timestamp,
            exec_output_root=exec_output_root,
        )
        batch_decision = "ATTENTION_BATCH_002_CLOSED"
        scaling_decision = "READY_FOR_ATTENTION_BATCH_003"
        recovery_decision = "ALL_6_RESPONSES_RECOVERED_WITHOUT_RECALL"
    elif recovered_rows:
        batch_decision = "ATTENTION_BATCH_002_REMAINS_PARTIALLY_COMPLETE"
        scaling_decision = "RETRY_FAILED_BATCH_002_CALLS_REQUIRES_AUTHORIZATION"
        recovery_decision = "SUBSET_RECOVERED_REMAINING_CALLS_REQUIRE_REVIEW"
    else:
        batch_decision = "ATTENTION_BATCH_002_REMAINS_PARTIALLY_COMPLETE"
        scaling_decision = "REPAIR_BEFORE_BATCH_003"
        recovery_decision = "NO_RESPONSES_RECOVERABLE"

    identity_decision = (
        "BATCH_002_IDENTITY_NORMALIZATION_VALIDATED"
        if recovered_rows
        else "BATCH_002_IDENTITY_MISMATCH_SUBSTANTIVE" if remaining_rows else "BATCH_002_IDENTITY_UNRESOLVED"
    )
    repair_status = (
        "LIVE_ATTENTION_BATCH_002_REPAIR_COMPLETE"
        if len(recovered_rows) == len(inventory)
        else "LIVE_ATTENTION_BATCH_002_REPAIR_PARTIALLY_COMPLETE"
    )
    write_json(
        audit_dir / "repair_decision.json",
        {
            "repair_status": repair_status,
            "identity_decision": identity_decision,
            "recovery_decision": recovery_decision,
            "batch_decision": batch_decision,
            "scaling_decision": scaling_decision,
        },
    )
    return {
        "audit_dir": audit_dir,
        "closure_dir": closure_dir,
        "inventory": inventory,
        "alias_rows": alias_rows,
        "audits": audits,
        "parse_rows": parse_rows,
        "validation_rows": validation_rows,
        "recovered_rows": recovered_rows,
        "remaining_rows": remaining_rows,
        "repair_reconciliation": repair_reconciliation,
        "repair_status": repair_status,
        "identity_decision": identity_decision,
        "recovery_decision": recovery_decision,
        "batch_decision": batch_decision,
        "scaling_decision": scaling_decision,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-output-root", type=Path, default=OUTPUT_AUDIT_ROOT)
    parser.add_argument("--fixed-timestamp")
    args = parser.parse_args(argv)
    result = run_recovery(audit_output_root=args.audit_output_root, fixed_timestamp=args.fixed_timestamp)
    print(
        json.dumps(
            {
                "audit_dir": str(result["audit_dir"]),
                "closure_dir": str(result["closure_dir"]) if result["closure_dir"] else None,
                "recovered_results": len(result["recovered_rows"]),
                "remaining_failed": len(result["remaining_rows"]),
                "batch_decision": result["batch_decision"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
