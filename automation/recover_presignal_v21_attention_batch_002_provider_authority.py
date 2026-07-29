#!/usr/bin/env python3
"""Call-free provider-authority audit and Batch 002 closure for historical Attention."""
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

from automation import execute_presignal_v21_attention_batch_001 as batch_base
from automation import execute_presignal_v21_attention_batch_002 as batch002
from automation import presignal_v21_provider_adapters_v1 as provider_adapters

PLAN_ID = "PPHB-R1-ATTENTION-EXECUTION-PLAN-20260729T010207Z-3fcd59f96f3c"
BATCH_001_CLOSED_ID = "PPHB-R1-ATTENTION-BATCH-001-CLOSED-20260729T035345Z-e3bc0c2909ca"
BATCH_002_EXEC_ID = "PPHB-R1-ATTENTION-EXECUTION-BATCH-002-20260729T040014Z-e270ec415b79"
BATCH_002_REPAIR_ID = "PPHB-R1-ATTENTION-CONTRACT-REPAIR-BATCH-002-20260729T042144Z-22ef2d6080ef"
OUTPUT_AUDIT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_contract_repair"
OUTPUT_EXEC_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_execution"
AUTHORITATIVE_ATTENTION_MAP = ROOT / "outputs" / "presignal_v21_attention_preservation" / "authoritative_attention_map.jsonl"

PLAN_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_execution_plan" / PLAN_ID
BATCH_001_CLOSED_ROOT = OUTPUT_EXEC_ROOT / BATCH_001_CLOSED_ID
BATCH_002_EXEC_ROOT = OUTPUT_EXEC_ROOT / BATCH_002_EXEC_ID
BATCH_002_REPAIR_ROOT = OUTPUT_AUDIT_ROOT / BATCH_002_REPAIR_ID

UNRESOLVED_CALL_IDS = [
    "ATN_b1f301900a92bb0cf6e3",
    "ATN_19e738b1020396398002",
    "ATN_b015d346ca9e87eeda8e",
    "ATN_2a8b084e0810a910e832",
]
CANONICAL_OBJECT = "session_attention_map"


class ProviderAuthorityRecoveryError(RuntimeError):
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
    for root in (PLAN_ROOT, BATCH_001_CLOSED_ROOT, BATCH_002_EXEC_ROOT, BATCH_002_REPAIR_ROOT):
        if not root.exists():
            raise ProviderAuthorityRecoveryError("GOVERNING_ARTIFACT_MISSING:" + root.name)
    calls = {row["call_id"]: row for row in batch002.load_batch_calls()}
    failed_rows = read_jsonl(BATCH_002_REPAIR_ROOT / "remaining_failed_calls.jsonl")
    if sorted(row["call_id"] for row in failed_rows) != sorted(UNRESOLVED_CALL_IDS):
        raise ProviderAuthorityRecoveryError("UNRESOLVED_CALL_SET_DRIFT")
    original_valid_rows = read_jsonl(BATCH_002_EXEC_ROOT / "normalized_attention_results.jsonl")
    prior_recovered_rows = read_jsonl(BATCH_002_REPAIR_ROOT / "recovered_attention_results.jsonl")
    if len(original_valid_rows) != 6:
        raise ProviderAuthorityRecoveryError("BATCH_002_ORIGINAL_VALID_COUNT_MISMATCH")
    if len(prior_recovered_rows) != 2:
        raise ProviderAuthorityRecoveryError("BATCH_002_PRIOR_RECOVERED_COUNT_MISMATCH")
    raw_rows = {row["call_id"]: row for row in read_jsonl(BATCH_002_EXEC_ROOT / "raw_provider_outputs.jsonl")}
    transport_rows = {row["call_id"]: row for row in read_jsonl(BATCH_002_EXEC_ROOT / "raw_transport_results.jsonl")}
    return {
        "runtime_contract": batch_base.load_runtime_contract(),
        "calls": calls,
        "failed_rows": failed_rows,
        "original_valid_rows": original_valid_rows,
        "prior_recovered_rows": prior_recovered_rows,
        "raw_rows": raw_rows,
        "transport_rows": transport_rows,
    }


def provider_label_occurrences(aliases: Iterable[str]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {alias: {} for alias in aliases}
    for row in read_jsonl(AUTHORITATIVE_ATTENTION_MAP):
        raw = row.get("raw_output") or ""
        provider = str(row.get("provider"))
        for alias in aliases:
            if alias in raw:
                result[alias][provider] = result[alias].get(provider, 0) + 1
    for path in OUTPUT_EXEC_ROOT.glob("PPHB-R1-ATTENTION-*/raw_provider_outputs.jsonl"):
        for row in read_jsonl(path):
            raw = row.get("raw_output") or ""
            provider = str(row.get("provider"))
            for alias in aliases:
                if alias in raw:
                    result[alias][provider] = result[alias].get(provider, 0) + 1
    return result


def build_validated_rows(
    payload: Mapping[str, Any],
    *,
    call_id: str,
    session_id: str,
    provider: str,
    model: str,
    members: list[Mapping[str, Any]],
    result_source: str,
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
                "source": result_source,
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


def summarize_attention_payload(rows: list[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row["attention_label"]) for row in rows)
    return {
        "PRIMARY_DRIVER": counts.get("PRIMARY_DRIVER", 0),
        "SECONDARY_DRIVER": counts.get("SECONDARY_DRIVER", 0),
        "WATCHLIST": counts.get("WATCHLIST", 0),
        "CONTEXT_ONLY": counts.get("CONTEXT_ONLY", 0),
        "IGNORE": counts.get("IGNORE", 0),
        "NO_SIGNAL": counts.get("NO_SIGNAL", 0),
    }


def execution_row_from_payload(
    *,
    call: Mapping[str, Any],
    payload: Mapping[str, Any],
    members: list[Mapping[str, Any]],
    result_source: str,
    source_identity: str,
) -> dict[str, Any]:
    validated_rows = build_validated_rows(
        payload,
        call_id=str(call["call_id"]),
        session_id=str(call["source_session_id"]),
        provider=str(call["provider"]),
        model=str(call["model"]),
        members=members,
        result_source=result_source,
    )
    return {
        "call_id": call["call_id"],
        "source_session_id": call["source_session_id"],
        "provider": call["provider"],
        "model": call["model"],
        "attention_run_id": "RECOVERED_" + call["call_id"],
        "request_fingerprint": None,
        "validated_attention_rows": validated_rows,
        "result_fingerprint": sha256_text({"call_id": call["call_id"], "payload": payload, "result_source": result_source}),
        "result_source": result_source,
        "source_identity": source_identity,
    }


def inventory_unresolved_calls(state: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    inventory = []
    raw_identities = []
    aliases = []
    for call_id in UNRESOLVED_CALL_IDS:
        call = state["calls"][call_id]
        transport = state["transport_rows"][call_id]
        raw_row = state["raw_rows"][call_id]
        payload = json.loads(stripped_json_text(raw_row["raw_output"]))
        aliases.append(str(payload.get("provider")))
        inventory.append(
            {
                "call_id": call_id,
                "manifest_provider": call["provider"],
                "manifest_model": call["model"],
                "transport_provider": transport.get("actual_provider"),
                "transport_model": transport.get("actual_model"),
                "raw_claimed_provider": payload.get("provider"),
                "manifest_transport_agreement": transport.get("actual_provider") == call["provider"] and transport.get("actual_model") == call["model"],
                "canonical_object": payload.get("object"),
                "json_parse_status": "PARSED",
                "scientific_required_field_status": all(
                    key in payload for key in ("object", "session_id", "provider", "attention_items", "session_attention_summary", "status")
                ) and all(
                    all(
                        key in item
                        for key in (
                            "event_id",
                            "attention_label",
                            "attention_rank",
                            "attention_reason",
                            "expected_market_channel",
                            "driver_role",
                            "confidence",
                        )
                    )
                    for item in payload.get("attention_items", [])
                ),
                "strict_validation_status_before_authoritative_provider_binding": "FAILED_PROVIDER_IDENTITY",
                "strict_validation_status_after_authoritative_provider_binding": "PENDING",
                "raw_evidence_reference": path_ref(BATCH_002_EXEC_ROOT / "raw_provider_outputs.jsonl"),
            }
        )
    for alias, frequencies in sorted(provider_label_occurrences(aliases).items()):
        raw_identities.append(
            {
                "raw_claimed_provider": alias,
                "provider_route_frequencies": dict(sorted(frequencies.items())),
                "frequency": sum(frequencies.values()),
            }
        )
    return inventory, raw_identities


def reprocess_unresolved_calls(
    state: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    source_sessions, source_members = batch_base.read_source_sessions()
    normalization_rows = []
    parse_rows = []
    validation_rows = []
    recovered_rows = []
    for call_id in UNRESOLVED_CALL_IDS:
        call = state["calls"][call_id]
        transport = dict(state["transport_rows"][call_id])
        raw_row = state["raw_rows"][call_id]
        transport["raw_output"] = raw_row["raw_output"]
        parsed_payload = json.loads(stripped_json_text(raw_row["raw_output"]))
        normalized = provider_adapters.normalize_provider_response(
            stage="ATTENTION",
            requested_provider=call["provider"],
            requested_model=call["model"],
            transport_result=transport,
            contract_version=state["runtime_contract"]["contract_version"],
            authoritative_attention_provider_binding=True,
        )
        if normalized["parse_status"] != provider_adapters.ParseStatus.PARSED:
            parse_rows.append(
                {
                    "call_id": call_id,
                    "result": "FAILED_PARSE",
                    "parse_status": str(normalized["parse_status"]),
                    "parse_error": normalized["normalization_notes"][-1]["reason"],
                }
            )
            validation_rows.append(
                {
                    "call_id": call_id,
                    "result": "FAILED_PARSE",
                    "validation_ok": False,
                    "validation_error": normalized["normalization_notes"][-1]["reason"],
                }
            )
            continue
        payload = dict(normalized["canonical_payload"])
        members = source_members[call["source_session_id"]]
        validated_rows = build_validated_rows(
            payload,
            call_id=call_id,
            session_id=call["source_session_id"],
            provider=call["provider"],
            model=call["model"],
            members=members,
            result_source="PRESERVED_BATCH_002_PROVIDER_AUTHORITY_RECOVERY",
        )
        valid, validation_error, validation_details = batch_base.validate_attention_result(
            result={"status": "parsed", "rows": validated_rows},
            expected_session_id=call["source_session_id"],
            expected_provider=call["provider"],
            expected_model=call["model"],
            member_ids=[row["event_id"] for row in members],
            contract=state["runtime_contract"],
        )
        parse_rows.append(
            {
                "call_id": call_id,
                "result": "PARSED_VALID" if valid else "FAILED_VALIDATION",
                "parse_status": str(normalized["parse_status"]),
                "raw_claimed_provider": parsed_payload.get("provider"),
                "canonical_provider": payload.get("provider"),
            }
        )
        validation_rows.append(
            {
                "call_id": call_id,
                "result": "PARSED_VALID" if valid else "FAILED_VALIDATION",
                "validation_ok": valid,
                "validation_error": validation_error,
                "validation_details": validation_details,
            }
        )
        if not valid:
            continue
        normalization_rows.append(
            {
                "call_id": call_id,
                "manifest_provider": call["provider"],
                "manifest_model": call["model"],
                "transport_provider": transport["actual_provider"],
                "transport_model": transport["actual_model"],
                "raw_claimed_provider": parsed_payload.get("provider"),
                "canonical_provider": payload.get("provider"),
                "canonical_object": payload.get("object"),
                "scientific_fields_changed": False,
                "normalization_rule": "historical_attention_manifest_transport_provider_authority",
                "raw_evidence_reference": path_ref(BATCH_002_EXEC_ROOT / "raw_provider_outputs.jsonl"),
            }
        )
        recovered_rows.append(
            execution_row_from_payload(
                call=call,
                payload=payload,
                members=members,
                result_source="PRESERVED_BATCH_002_PROVIDER_AUTHORITY_RECOVERY",
                source_identity=BATCH_002_EXEC_ID,
            )
        )
    return normalization_rows, parse_rows, validation_rows, recovered_rows


def execution_row_from_prior_recovered(
    state: Mapping[str, Any],
    recovered: Mapping[str, Any],
) -> dict[str, Any]:
    source_sessions, source_members = batch_base.read_source_sessions()
    call = state["calls"][str(recovered["call_id"])]
    members = source_members[call["source_session_id"]]
    return execution_row_from_payload(
        call=call,
        payload=dict(recovered["attention_result"]),
        members=members,
        result_source="PRESERVED_BATCH_002_ALIAS_RECOVERY",
        source_identity=BATCH_002_REPAIR_ID,
    )


def create_closure_run(
    *,
    state: Mapping[str, Any],
    recovered_rows: list[dict[str, Any]],
    normalization_rows: list[dict[str, Any]],
    fixed_timestamp: str | None = None,
    exec_output_root: Path = OUTPUT_EXEC_ROOT,
) -> Path:
    ts = fixed_timestamp or now_stamp()
    seed = {"batch_002_exec": BATCH_002_EXEC_ID, "batch_002_repair": BATCH_002_REPAIR_ID, "timestamp": ts}
    run_id = "PPHB-R1-ATTENTION-BATCH-002-CLOSED-" + ts + "-" + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:12]
    run_dir = exec_output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    imported_original = [dict(row) for row in state["original_valid_rows"]]
    imported_prior_recovered = [execution_row_from_prior_recovered(state, row) for row in state["prior_recovered_rows"]]
    final_rows = imported_original + imported_prior_recovered + [dict(row) for row in recovered_rows]
    final_call_ids = [str(row["call_id"]) for row in final_rows]
    if len(final_call_ids) != 12 or len(set(final_call_ids)) != 12:
        raise ProviderAuthorityRecoveryError("BATCH_002_FINAL_CALL_POPULATION_MISMATCH")

    episode_map = []
    imported_ledger = []
    for row in imported_original:
        call = state["calls"][row["call_id"]]
        imported_ledger.append(
            {
                "call_id": row["call_id"],
                "provider": row["provider"],
                "model": row["model"],
                "source_session_id": row["source_session_id"],
                "import_status": "IMPORTED_ORIGINAL_VALID_RESULT",
                "provider_recall_performed": False,
                "source_identity": BATCH_002_EXEC_ID,
            }
        )
        for episode_id in call["episode_ids"]:
            episode_map.append(
                {
                    "call_id": row["call_id"],
                    "episode_id": episode_id,
                    "source_session_id": row["source_session_id"],
                    "provider": row["provider"],
                    "model": row["model"],
                    "normalized_result_fingerprint": row["result_fingerprint"],
                }
            )
    for row in imported_prior_recovered:
        call = state["calls"][row["call_id"]]
        imported_ledger.append(
            {
                "call_id": row["call_id"],
                "provider": row["provider"],
                "model": row["model"],
                "source_session_id": row["source_session_id"],
                "import_status": "IMPORTED_PRIOR_RECOVERED_RESULT",
                "provider_recall_performed": False,
                "source_identity": BATCH_002_REPAIR_ID,
            }
        )
        for episode_id in call["episode_ids"]:
            episode_map.append(
                {
                    "call_id": row["call_id"],
                    "episode_id": episode_id,
                    "source_session_id": row["source_session_id"],
                    "provider": row["provider"],
                    "model": row["model"],
                    "normalized_result_fingerprint": row["result_fingerprint"],
                }
            )
    recovered_import_ledger = []
    for row in recovered_rows:
        call = state["calls"][row["call_id"]]
        recovered_import_ledger.append(
            {
                "call_id": row["call_id"],
                "provider": row["provider"],
                "model": row["model"],
                "source_session_id": row["source_session_id"],
                "import_status": "RECOVERED_PROVIDER_AUTHORITY_RESULT",
                "provider_recall_performed": False,
                "source_identity": BATCH_002_EXEC_ID,
            }
        )
        for episode_id in call["episode_ids"]:
            episode_map.append(
                {
                    "call_id": row["call_id"],
                    "episode_id": episode_id,
                    "source_session_id": row["source_session_id"],
                    "provider": row["provider"],
                    "model": row["model"],
                    "normalized_result_fingerprint": row["result_fingerprint"],
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
            "governing_batch_002_repair_identity": BATCH_002_REPAIR_ID,
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
            "batch_002_repair_root": path_ref(BATCH_002_REPAIR_ROOT),
        },
    )
    write_json(
        run_dir / "batch_closure_contract.json",
        {
            "canonical_attention_contract_identity": CANONICAL_OBJECT,
            "imported_valid_result_count": 8,
            "newly_recovered_result_count": len(recovered_rows),
            "new_provider_calls": 0,
            "duplicate_calls": 0,
            "failure_behavior": "call-free preserved-response recovery only",
        },
    )
    write_jsonl(run_dir / "imported_valid_result_ledger.jsonl", imported_ledger)
    write_jsonl(run_dir / "recovered_result_import_ledger.jsonl", recovered_import_ledger)
    write_jsonl(run_dir / "normalization_application_ledger.jsonl", normalization_rows)
    write_jsonl(run_dir / "final_normalized_attention_results.jsonl", final_rows)
    write_jsonl(run_dir / "final_episode_attention_result_map.jsonl", episode_map)
    write_jsonl(run_dir / "remaining_failed_calls.jsonl", [])
    reconciliation = {
        "planned_calls": 12,
        "imported_valid_results": 8,
        "newly_recovered_results": len(recovered_rows),
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
    create_closure: bool = True,
) -> dict[str, Any]:
    state = load_governing_state()
    inventory_rows, alias_rows = inventory_unresolved_calls(state)
    normalization_rows, parse_rows, validation_rows, recovered_rows = reprocess_unresolved_calls(state)
    ts = fixed_timestamp or now_stamp()
    seed = {"batch_002_exec": BATCH_002_EXEC_ID, "timestamp": ts}
    audit_id = "PPHB-R1-ATTENTION-PROVIDER-AUTHORITY-AUDIT-" + ts + "-" + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:12]
    audit_dir = audit_output_root / audit_id
    audit_dir.mkdir(parents=True, exist_ok=False)

    remaining_rows = []
    parse_by_call = {row["call_id"]: row for row in parse_rows}
    validation_by_call = {row["call_id"]: row for row in validation_rows}
    authority_audit_rows = []
    for row in inventory_rows:
        parse_row = parse_by_call[row["call_id"]]
        validation_row = validation_by_call[row["call_id"]]
        final_status = parse_row["result"]
        if final_status != "PARSED_VALID":
            remaining_rows.append(
                {
                    "call_id": row["call_id"],
                    "provider": row["manifest_provider"],
                    "model": row["manifest_model"],
                    "failure_stage": final_status,
                    "exact_remaining_reason": validation_row["validation_error"],
                    "retry_required": False,
                }
            )
        authority_audit_rows.append(
            {
                **row,
                "strict_validation_status_after_authoritative_provider_binding": final_status,
                "canonical_provider_after_binding": row["manifest_provider"] if final_status == "PARSED_VALID" else None,
                "validation_error_after_authoritative_provider_binding": validation_row["validation_error"],
            }
        )

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
            "batch_002_repair_root": path_ref(BATCH_002_REPAIR_ROOT),
        },
    )
    write_json(
        audit_dir / "provider_identity_authority_contract.json",
        {
            "scope": "historical session_attention_map parsing only",
            "canonical_provider_authority": "frozen call manifest provider confirmed by transport provider/model metadata",
            "transport_confirmation_requirement": True,
            "manifest_transport_conflict_behavior": "fail closed",
            "raw_claimed_provider_preservation": True,
            "allowed_object_identity": CANONICAL_OBJECT,
            "scientific_fields_changed": False,
            "forbidden_inference": "provider may not be derived from model-returned role labels",
            "applicability_limits": [
                "requires manifest-bound call identity",
                "requires transport-confirmed provider and model",
                "does not apply to forecast outputs",
                "does not apply to outcome outputs",
            ],
        },
    )
    write_json(
        audit_dir / "cross_provider_alias_inventory.json",
        {
            "cross_provider_role_labels": alias_rows,
            "canonical_provider_is_not_derived_from_alias": True,
        },
    )
    write_jsonl(audit_dir / "unresolved_call_authority_audit.jsonl", authority_audit_rows)
    write_jsonl(audit_dir / "normalization_application_ledger.jsonl", normalization_rows)
    write_jsonl(audit_dir / "local_parse_results.jsonl", parse_rows)
    write_jsonl(audit_dir / "local_validation_results.jsonl", validation_rows)
    write_jsonl(
        audit_dir / "recovered_attention_results.jsonl",
        [
            {
                "call_id": row["call_id"],
                "provider": row["provider"],
                "model": row["model"],
                "source_session_id": row["source_session_id"],
                "result_source": row["result_source"],
                "validated_attention_rows": row["validated_attention_rows"],
                "result_fingerprint": row["result_fingerprint"],
            }
            for row in recovered_rows
        ],
    )
    write_jsonl(audit_dir / "remaining_failed_calls.jsonl", remaining_rows)
    write_json(
        audit_dir / "audit_reconciliation.json",
        {
            "unresolved_response_count": 4,
            "manifest_transport_agreement_count": sum(1 for row in inventory_rows if row["manifest_transport_agreement"]),
            "manifest_transport_conflict_count": sum(1 for row in inventory_rows if not row["manifest_transport_agreement"]),
            "locally_recovered_count": len(recovered_rows),
            "remaining_parse_failures": sum(1 for row in parse_rows if row["result"] == "FAILED_PARSE"),
            "remaining_validation_failures": sum(1 for row in validation_rows if row["result"] == "FAILED_VALIDATION"),
            "authority_conflicts": sum(1 for row in authority_audit_rows if not row["manifest_transport_agreement"]),
        },
    )
    write_json(
        audit_dir / "audit_summary.json",
        {
            "governance_status": "ATTENTION_PROVIDER_AUTHORITY_AUDIT_COMPLETE",
            "authority_decision": "MANIFEST_AND_TRANSPORT_PROVIDER_AUTHORITY_VALIDATED",
            "recovery_decision": (
                "ALL_4_RESPONSES_RECOVERED_WITHOUT_RECALL"
                if len(recovered_rows) == 4
                else "SUBSET_RECOVERED_REMAINING_CALLS_REQUIRE_REVIEW"
                if recovered_rows
                else "NO_RESPONSES_RECOVERABLE"
            ),
        },
    )

    closure_dir = None
    batch_decision = "ATTENTION_BATCH_002_REMAINS_PARTIALLY_COMPLETE"
    scaling_decision = "GOVERNANCE_DECISION_REQUIRED"
    if not remaining_rows and len(recovered_rows) == 4 and create_closure:
        closure_dir = create_closure_run(
            state=state,
            recovered_rows=recovered_rows,
            normalization_rows=normalization_rows,
            fixed_timestamp=fixed_timestamp,
            exec_output_root=exec_output_root,
        )
        batch_decision = "ATTENTION_BATCH_002_CLOSED"
        scaling_decision = "READY_FOR_ATTENTION_BATCH_003"
    write_json(
        audit_dir / "audit_decision.json",
        {
            "governance_status": "ATTENTION_PROVIDER_AUTHORITY_AUDIT_COMPLETE",
            "authority_decision": "MANIFEST_AND_TRANSPORT_PROVIDER_AUTHORITY_VALIDATED",
            "recovery_decision": (
                "ALL_4_RESPONSES_RECOVERED_WITHOUT_RECALL"
                if len(recovered_rows) == 4
                else "SUBSET_RECOVERED_REMAINING_CALLS_REQUIRE_REVIEW"
                if recovered_rows
                else "NO_RESPONSES_RECOVERABLE"
            ),
            "batch_decision": batch_decision,
            "scaling_decision": scaling_decision,
        },
    )
    return {
        "audit_dir": audit_dir,
        "closure_dir": closure_dir,
        "inventory_rows": inventory_rows,
        "alias_rows": alias_rows,
        "normalization_rows": normalization_rows,
        "parse_rows": parse_rows,
        "validation_rows": validation_rows,
        "recovered_rows": recovered_rows,
        "remaining_rows": remaining_rows,
        "batch_decision": batch_decision,
        "scaling_decision": scaling_decision,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-output-root", type=Path, default=OUTPUT_AUDIT_ROOT)
    parser.add_argument("--no-closure", action="store_true")
    parser.add_argument("--fixed-timestamp")
    args = parser.parse_args(argv)
    result = run_recovery(
        audit_output_root=args.audit_output_root,
        exec_output_root=OUTPUT_EXEC_ROOT,
        fixed_timestamp=args.fixed_timestamp,
        create_closure=not args.no_closure,
    )
    print(
        json.dumps(
            {
                "audit_dir": str(result["audit_dir"]),
                "closure_dir": str(result["closure_dir"]) if result["closure_dir"] else None,
                "recovered_count": len(result["recovered_rows"]),
                "remaining_count": len(result["remaining_rows"]),
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
