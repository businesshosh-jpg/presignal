#!/usr/bin/env python3
"""Call-free audit and recovery for the final preserved Batch 001 Anthropic alias response."""
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
from automation import execute_presignal_v21_attention_batch_001 as batch
from automation import presignal_v21_provider_adapters_v1 as provider_adapters

PLAN_ID = "PPHB-R1-ATTENTION-EXECUTION-PLAN-20260729T010207Z-3fcd59f96f3c"
REPAIR_ID = "PPHB-R1-ATTENTION-CONTRACT-REPAIR-BATCH-001-20260729T020108Z-17657dcc7cd5"
PRIOR_FINALIZATION_ID = "PPHB-R1-ATTENTION-BATCH-001-FINALIZATION-20260729T023607Z-eb4bd2a9277c"
FAILURE_AUDIT_ID = "PPHB-R1-ATTENTION-BATCH-001-ANTHROPIC-FAILURE-AUDIT-20260729T032157Z-a5ae0ae86b0f"
CORRECTED_FINALIZATION_ID = "PPHB-R1-ATTENTION-BATCH-001-CORRECTED-FINALIZATION-20260729T033528Z-66166de58345"
CALL_ID = "ATN_d7c95516e95938578834"
OUTPUT_AUDIT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_contract_repair"
OUTPUT_EXEC_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_execution"
ALIAS = "PreSignal_v2.0_shadow_research"
CANONICAL_PROVIDER = "Anthropic"
MODEL = "claude-haiku-4-5"

PLAN_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_execution_plan" / PLAN_ID
REPAIR_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_contract_repair" / REPAIR_ID
PRIOR_FINALIZATION_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_execution" / PRIOR_FINALIZATION_ID
FAILURE_AUDIT_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_failure_audit" / FAILURE_AUDIT_ID
CORRECTED_FINALIZATION_ROOT = ROOT / "outputs" / "presignal_v21_full_round_1_attention_execution" / CORRECTED_FINALIZATION_ID
AUTHORITATIVE_ATTENTION_MAP = ROOT / "outputs" / "presignal_v21_attention_preservation" / "authoritative_attention_map.jsonl"
R8_REPAIR_ROOT = ROOT / "outputs" / "presignal_v21_step8_r3_r8_provider_coverage_repair" / "STEP8-R3-R8-d84e6a5"


class ShadowAliasRecoveryError(RuntimeError):
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
    for root in (PLAN_ROOT, REPAIR_ROOT, PRIOR_FINALIZATION_ROOT, FAILURE_AUDIT_ROOT, CORRECTED_FINALIZATION_ROOT):
        if not root.exists():
            raise ShadowAliasRecoveryError("GOVERNING_ARTIFACT_MISSING:" + root.name)
    retry_transport = read_json(CORRECTED_FINALIZATION_ROOT / "retry_raw_transport_result.json")
    retry_raw = read_json(CORRECTED_FINALIZATION_ROOT / "retry_raw_provider_output.json")
    if not retry_raw.get("raw_output"):
        raise ShadowAliasRecoveryError("CORRECTED_RAW_RESPONSE_MISSING")
    calls = {row["call_id"]: row for row in batch.load_batch_calls()}
    if CALL_ID not in calls:
        raise ShadowAliasRecoveryError("CALL_ID_NOT_IN_FROZEN_PLAN")
    retry_call = calls[CALL_ID]
    if retry_call["provider"] != CANONICAL_PROVIDER or retry_call["model"] != MODEL:
        raise ShadowAliasRecoveryError("FROZEN_CALL_ASSIGNMENT_DRIFT")
    if retry_transport.get("actual_provider") != CANONICAL_PROVIDER or retry_transport.get("actual_model") != MODEL:
        raise ShadowAliasRecoveryError("TRANSPORT_METADATA_CONFLICT")
    imported = read_jsonl(PRIOR_FINALIZATION_ROOT / "final_normalized_attention_results.jsonl")
    if len(imported) != 11:
        raise ShadowAliasRecoveryError("IMPORTED_RESULT_COUNT_MISMATCH")
    return {
        "retry_call": retry_call,
        "retry_transport": retry_transport,
        "retry_raw": retry_raw,
        "imported": imported,
        "runtime_contract": batch.load_runtime_contract(),
    }


def alias_occurrence_inventory() -> dict[str, Any]:
    exact_paths: list[str] = []
    preserved_exact_paths: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or "__pycache__" in str(path):
            continue
        try:
            text = path.read_text(errors="ignore")
        except Exception:
            continue
        if ALIAS in text:
            ref = path_ref(path)
            exact_paths.append(ref)
            if path.is_relative_to(CORRECTED_FINALIZATION_ROOT):
                preserved_exact_paths.append(ref)

    lower_count = 0
    lower_providers: Counter[str] = Counter()
    lower_models: Counter[str] = Counter()
    lower_sessions: set[str] = set()
    for row in read_jsonl(AUTHORITATIVE_ATTENTION_MAP):
        raw = row.get("raw_output") or ""
        if "presignal_v2_shadow_research" in raw:
            lower_count += 1
            lower_providers[str(row.get("provider"))] += 1
            lower_models[str(row.get("model"))] += 1
            lower_sessions.add(str(row.get("active_session_id")))

    return {
        "exact_alias_occurrence_count": len(exact_paths),
        "exact_alias_paths": exact_paths,
        "preserved_exact_alias_occurrence_count": len(preserved_exact_paths),
        "preserved_exact_alias_paths": preserved_exact_paths,
        "lower_alias_authoritative_row_count": lower_count,
        "lower_alias_providers": dict(sorted(lower_providers.items())),
        "lower_alias_models": dict(sorted(lower_models.items())),
        "lower_alias_session_count": len(lower_sessions),
        "lower_alias_sessions": sorted(lower_sessions),
    }


def inventory_preserved_response(state: Mapping[str, Any]) -> dict[str, Any]:
    payload = json.loads(stripped_json_text(state["retry_raw"]["raw_output"]))
    return {
        "call_id": CALL_ID,
        "manifest_bound_provider": state["retry_call"]["provider"],
        "manifest_bound_model": state["retry_call"]["model"],
        "source_session_id": state["retry_call"]["source_session_id"],
        "raw_provider_field": payload.get("provider"),
        "canonical_object_field": payload.get("object"),
        "returned_contract_identity": payload.get("object"),
        "expected_contract_identity": "session_attention_map",
        "parseable_json_status": True,
        "required_scientific_field_presence": {
            "top_level_required_fields_present": all(k in payload for k in ("object", "session_id", "provider", "attention_items", "session_attention_summary", "status")),
            "attention_items_count": len(payload.get("attention_items", [])),
            "item_required_fields_present": all(
                all(key in item for key in ("event_id", "attention_label", "attention_rank", "attention_reason", "expected_market_channel", "driver_role", "confidence"))
                for item in payload.get("attention_items", [])
            ),
        },
    }


def prove_equivalence(state: Mapping[str, Any], inventory: Mapping[str, Any], occurrence: Mapping[str, Any]) -> dict[str, Any]:
    instruction = (ROOT / "automation" / "presignal_v21_minimal_prospective_lineage_v1.py").read_text()
    r8_decision = read_json(R8_REPAIR_ROOT / "anthropic_runtime_identity_decision.json")
    normalization_inventory = read_json(R8_REPAIR_ROOT / "normalization_inventory.json")
    exact_paths = set(occurrence["preserved_exact_alias_paths"])
    expected_paths = {
        path_ref(CORRECTED_FINALIZATION_ROOT / "retry_raw_provider_output.json"),
        path_ref(CORRECTED_FINALIZATION_ROOT / "raw_provider_outputs.jsonl"),
    }
    if exact_paths != expected_paths:
        raise ShadowAliasRecoveryError("EXACT_ALIAS_OCCURRENCE_SCOPE_UNEXPECTED")
    if occurrence["lower_alias_providers"] != {"Anthropic": occurrence["lower_alias_authoritative_row_count"]}:
        raise ShadowAliasRecoveryError("LOWER_ALIAS_USED_BY_NON_ANTHROPIC_PROVIDER")
    if occurrence["lower_alias_models"] != {MODEL: occurrence["lower_alias_authoritative_row_count"]}:
        raise ShadowAliasRecoveryError("LOWER_ALIAS_USED_BY_NON_ANTHROPIC_MODEL")
    if "PreSignal v2.0 shadow research layer" not in instruction:
        raise ShadowAliasRecoveryError("PROMPT_PERSONA_EVIDENCE_MISSING")
    if "presignal_v2_shadow_research" not in (r8_decision.get("accepted_emitted_provider_identities") or []):
        raise ShadowAliasRecoveryError("LOWER_ALIAS_NOT_IN_FROZEN_RUNTIME_IDENTITY_RULE")
    return {
        "manifest_bound_provider": state["retry_call"]["provider"],
        "manifest_bound_model": state["retry_call"]["model"],
        "transport_actual_provider": state["retry_transport"]["actual_provider"],
        "transport_actual_model": state["retry_transport"]["actual_model"],
        "returned_provider_identity": inventory["raw_provider_field"],
        "lower_alias_frozen_equivalent": "presignal_v2_shadow_research",
        "evidence": [
            "The corrected retry manifest binds the call to Anthropic / claude-haiku-4-5.",
            "The preserved transport metadata confirms actual_provider Anthropic and actual_model claude-haiku-4-5.",
            "Among preserved evidence artifacts, the exact capitalized alias appears only in the corrected-finalization raw provider evidence for the unresolved Anthropic call.",
            "The lowercase shadow-research alias appears in preserved authoritative Anthropic Attention outputs and only under provider Anthropic / model claude-haiku-4-5.",
            "The frozen compat-r4 runtime identity decision already accepted presignal_v2_shadow_research as an exact emitted Anthropic workflow label.",
            "The Attention prompt itself identifies the workflow as a PreSignal v2.0 shadow research layer, supporting the capitalized variant as a persona/workflow label rather than a distinct provider.",
        ],
        "normalization_scope": {
            "stage": "ATTENTION",
            "requested_provider": "Anthropic",
            "required_actual_provider": "Anthropic",
            "required_actual_model": "claude-haiku-4-5",
            "allowed_alias": ALIAS,
            "canonical_provider": CANONICAL_PROVIDER,
        },
        "any_other_provider_used_alias": False,
        "scientific_meaning_changed": False,
        "r8_identity_owner": r8_decision["identity_owner"],
        "normalization_inventory": normalization_inventory["anthropic_identity"],
    }


def build_validated_rows(payload: Mapping[str, Any], *, session_id: str, provider: str, model: str, members: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    item_by_event = {str(item["event_id"]): dict(item) for item in payload["attention_items"]}
    rows: list[dict[str, Any]] = []
    for member in members:
        item = item_by_event[str(member["event_id"])]
        rows.append(
            {
                "attention_run_id": "RECOVERED_" + CALL_ID,
                "session_id": session_id,
                "provider": provider,
                "model": model,
                "information_cutoff_ts": "",
                "generated_ts": "",
                "request_fingerprint": None,
                "source": "preserved_corrected_retry_response",
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


def reprocess_preserved_response(state: Mapping[str, Any]) -> dict[str, Any]:
    transport = dict(state["retry_transport"])
    transport["raw_output"] = state["retry_raw"]["raw_output"]
    normalized = provider_adapters.normalize_provider_response(
        stage="ATTENTION",
        requested_provider=CANONICAL_PROVIDER,
        requested_model=MODEL,
        transport_result=transport,
        contract_version=state["runtime_contract"]["contract_version"],
    )
    if normalized["parse_status"] != provider_adapters.ParseStatus.PARSED:
        return {
            "result": "FAILED_PARSE",
            "normalized": normalized,
            "validation_ok": False,
            "validation_error": "PARSE_FAILED",
        }
    payload = dict(normalized["canonical_payload"])
    source_sessions, source_members = batch.read_source_sessions()
    retry_call = state["retry_call"]
    members = source_members[retry_call["source_session_id"]]
    rows = build_validated_rows(payload, session_id=retry_call["source_session_id"], provider=CANONICAL_PROVIDER, model=MODEL, members=members)
    valid, error, details = batch.validate_attention_result(
        result={"status": "parsed", "rows": rows},
        expected_session_id=retry_call["source_session_id"],
        expected_provider=CANONICAL_PROVIDER,
        expected_model=MODEL,
        member_ids=[row["event_id"] for row in members],
        contract=state["runtime_contract"],
    )
    return {
        "result": "PARSED_VALID" if valid else "FAILED_VALIDATION",
        "normalized": normalized,
        "validation_ok": valid,
        "validation_error": error,
        "validation_details": details,
        "payload": payload,
        "rows": rows,
    }


def build_recovered_result(state: Mapping[str, Any], reparsed: Mapping[str, Any]) -> dict[str, Any]:
    retry_call = state["retry_call"]
    payload = dict(reparsed["payload"])
    return {
        "call_id": CALL_ID,
        "provider": CANONICAL_PROVIDER,
        "model": MODEL,
        "source_session_id": retry_call["source_session_id"],
        "session_date": retry_call["session_date"],
        "episode_ids": list(retry_call["episode_ids"]),
        "attention_result": payload,
        "result_source": "PRESERVED_CORRECTED_RETRY_RESPONSE_RECOVERY",
        "source_live_run_identity": CORRECTED_FINALIZATION_ID,
        "source_repair_run_identity": FAILURE_AUDIT_ID,
    }


def create_closure_run(
    *,
    state: Mapping[str, Any],
    reparsed: Mapping[str, Any],
    fixed_timestamp: str | None = None,
    exec_output_root: Path = OUTPUT_EXEC_ROOT,
) -> Path:
    ts = fixed_timestamp or now_stamp()
    seed = {"call_id": CALL_ID, "audit": FAILURE_AUDIT_ID, "corrected_finalization": CORRECTED_FINALIZATION_ID, "timestamp": ts}
    run_id = "PPHB-R1-ATTENTION-BATCH-001-CLOSED-" + ts + "-" + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:12]
    run_dir = exec_output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    imported_rows = state["imported"]
    recovered = build_recovered_result(state, reparsed)
    final_results = [dict(row) for row in imported_rows] + [recovered]
    episode_map: list[dict[str, Any]] = []
    for row in final_results:
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
            "governing_corrected_finalization_identity": CORRECTED_FINALIZATION_ID,
            "governing_alias_audit_identity": FAILURE_AUDIT_ID,
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
            "repair_root": path_ref(REPAIR_ROOT),
            "prior_finalization_root": path_ref(PRIOR_FINALIZATION_ROOT),
            "failure_audit_root": path_ref(FAILURE_AUDIT_ROOT),
            "corrected_finalization_root": path_ref(CORRECTED_FINALIZATION_ROOT),
        },
    )
    write_json(
        run_dir / "batch_closure_contract.json",
        {
            "canonical_attention_contract_identity": "session_attention_map",
            "imported_valid_result_count": 11,
            "recovered_call_id": CALL_ID,
            "provider_calls_executed": 0,
            "failure_behavior": "call-free preserved-response recovery only",
        },
    )
    imported_ledger = []
    for row in imported_rows:
        imported_ledger.append(
            {
                "call_id": row["call_id"],
                "provider": row["provider"],
                "model": row["model"],
                "source_session_id": row["source_session_id"],
                "import_status": "IMPORTED_PRIOR_VALID_RESULT",
                "provider_recall_performed": False,
            }
        )
    write_jsonl(run_dir / "imported_valid_result_ledger.jsonl", imported_ledger)
    write_json(run_dir / "recovered_final_call_result.json", recovered)
    write_jsonl(
        run_dir / "normalization_application_ledger.jsonl",
        [
            {
                "call_id": CALL_ID,
                "provider": CANONICAL_PROVIDER,
                "original_representation": ALIAS,
                "normalization_rule": "Anthropic Attention preserved shadow alias exact equivalence",
                "normalized_representation": CANONICAL_PROVIDER,
                "scientific_fields_changed": False,
                "raw_evidence_reference": path_ref(CORRECTED_FINALIZATION_ROOT / "retry_raw_provider_output.json"),
            }
        ],
    )
    write_jsonl(run_dir / "final_normalized_attention_results.jsonl", final_results)
    write_jsonl(run_dir / "final_episode_attention_result_map.jsonl", episode_map)
    write_jsonl(run_dir / "remaining_failed_calls.jsonl", [])
    reconciliation = {
        "planned_calls": 12,
        "imported_valid_results": 11,
        "recovered_valid_results": 1,
        "final_validated_results": len(final_results),
        "remaining_failed_calls": 0,
        "new_provider_calls": 0,
        "duplicate_calls": 0,
        "unexpected_calls": 0,
        "sessions_represented": len({row["source_session_id"] for row in final_results}),
        "episodes_mapped": len({row["episode_id"] for row in episode_map}),
        "results_by_provider_model": dict(sorted(Counter(f"{row['provider']}|{row['model']}" for row in final_results).items())),
    }
    write_json(run_dir / "batch_001_reconciliation.json", reconciliation)
    write_json(run_dir / "batch_001_summary.json", reconciliation)
    write_json(
        run_dir / "batch_001_decision.json",
        {
            "batch_decision": "ATTENTION_BATCH_001_CLOSED",
            "contract_decision": "ALL_BATCH_001_RESULTS_VALID",
            "scaling_decision": "READY_FOR_ATTENTION_BATCH_002",
        },
    )
    return run_dir


def run_recovery(
    *,
    audit_output_root: Path = OUTPUT_AUDIT_ROOT,
    exec_output_root: Path = OUTPUT_EXEC_ROOT,
    create_closure: bool = True,
    fixed_timestamp: str | None = None,
) -> dict[str, Any]:
    state = load_governing_state()
    inventory = inventory_preserved_response(state)
    occurrence = alias_occurrence_inventory()
    equivalence = prove_equivalence(state, inventory, occurrence)
    reparsed = reprocess_preserved_response(state)
    ts = fixed_timestamp or now_stamp()
    seed = {"call_id": CALL_ID, "timestamp": ts, "alias": ALIAS}
    audit_run_id = "PPHB-R1-ATTENTION-ANTHROPIC-SHADOW-ALIAS-AUDIT-" + ts + "-" + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:12]
    audit_dir = audit_output_root / audit_run_id
    audit_dir.mkdir(parents=True, exist_ok=False)

    write_json(
        audit_dir / "run_manifest.json",
        {
            "run_id": audit_run_id,
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
            "repair_root": path_ref(REPAIR_ROOT),
            "prior_finalization_root": path_ref(PRIOR_FINALIZATION_ROOT),
            "failure_audit_root": path_ref(FAILURE_AUDIT_ROOT),
            "corrected_finalization_root": path_ref(CORRECTED_FINALIZATION_ROOT),
        },
    )
    write_json(audit_dir / "preserved_response_inventory.json", inventory)
    write_json(
        audit_dir / "alias_source_inventory.json",
        {
            **occurrence,
            "prompt_persona_source": "automation/presignal_v21_minimal_prospective_lineage_v1.py:ATTENTION_INSTRUCTION",
            "frozen_runtime_identity_source": path_ref(R8_REPAIR_ROOT / "anthropic_runtime_identity_decision.json"),
        },
    )
    write_json(audit_dir / "alias_equivalence_audit.json", equivalence)
    write_json(
        audit_dir / "alias_normalization_contract.json",
        {
            "original_alias": ALIAS,
            "canonical_provider": CANONICAL_PROVIDER,
            "allowed_call_provider": CANONICAL_PROVIDER,
            "allowed_object": "session_attention_map",
            "manifest_bound_requirement": True,
            "transport_metadata_requirement": {"actual_provider": CANONICAL_PROVIDER, "actual_model": MODEL},
            "scope": "Attention payload parsing for manifest-bound Anthropic calls only",
            "forbidden_aliases": ["unknown shadow aliases", "shadow aliases on Gemini", "shadow aliases on OpenAI", "missing provider values"],
            "scientific_fields_changed": False,
            "failure_behavior": "fail closed if strict validation does not pass",
        },
    )
    write_json(
        audit_dir / "local_reprocessing_result.json",
        {
            "call_id": CALL_ID,
            "result": reparsed["result"],
            "parse_status": str(reparsed["normalized"]["parse_status"]),
            "validation_ok": reparsed["validation_ok"],
            "validation_error": reparsed.get("validation_error"),
            "normalization_notes": reparsed["normalized"].get("normalization_notes"),
        },
    )
    write_json(
        audit_dir / "audit_summary.json",
        {
            "alias_audit_status": "ANTHROPIC_SHADOW_ALIAS_AUDIT_COMPLETE",
            "alias_decision": "SHADOW_RESEARCH_ALIAS_EQUIVALENCE_PROVEN",
            "recovery_decision": (
                "PRESERVED_RESPONSE_RECOVERED_VALID"
                if reparsed["result"] == "PARSED_VALID"
                else "PRESERVED_RESPONSE_FAILED_VALIDATION" if reparsed["result"] == "FAILED_VALIDATION"
                else "PRESERVED_RESPONSE_FAILED_PARSE"
            ),
        },
    )
    batch_decision = "ATTENTION_BATCH_001_REMAINS_TERMINAL_PARTIAL"
    scaling_decision = "REPAIR_BEFORE_BATCH_002"
    closure_dir = None
    if reparsed["result"] == "PARSED_VALID" and create_closure:
        closure_dir = create_closure_run(
            state=state,
            reparsed=reparsed,
            fixed_timestamp=fixed_timestamp,
            exec_output_root=exec_output_root,
        )
        batch_decision = "ATTENTION_BATCH_001_CLOSED"
        scaling_decision = "READY_FOR_ATTENTION_BATCH_002"
    write_json(
        audit_dir / "audit_decision.json",
        {
            "alias_audit_status": "ANTHROPIC_SHADOW_ALIAS_AUDIT_COMPLETE",
            "alias_decision": "SHADOW_RESEARCH_ALIAS_EQUIVALENCE_PROVEN",
            "recovery_decision": (
                "PRESERVED_RESPONSE_RECOVERED_VALID"
                if reparsed["result"] == "PARSED_VALID"
                else "PRESERVED_RESPONSE_FAILED_VALIDATION" if reparsed["result"] == "FAILED_VALIDATION"
                else "PRESERVED_RESPONSE_FAILED_PARSE"
            ),
            "batch_decision": batch_decision,
            "scaling_decision": scaling_decision,
        },
    )
    return {
        "audit_dir": audit_dir,
        "closure_dir": closure_dir,
        "inventory": inventory,
        "occurrence": occurrence,
        "equivalence": equivalence,
        "reparsed": reparsed,
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
        create_closure=not args.no_closure,
        fixed_timestamp=args.fixed_timestamp,
    )
    print(
        json.dumps(
            {
                "audit_dir": str(result["audit_dir"]),
                "closure_dir": str(result["closure_dir"]) if result["closure_dir"] else None,
                "result": result["reparsed"]["result"],
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
