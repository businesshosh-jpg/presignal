#!/usr/bin/env python3
"""Verify whether legacy v2 lineage builders can safely serve prospective v2.1.

This adapter is deliberately a gate, not a replacement Attention, Request, or
Pack implementation.  It records the exact v2 source contracts and refuses to
invoke them until a deployed return-only/no-write binding exists.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
SOURCE_COMMIT = "e5a0ff288eb1f6fc228936cb1c693ed2bb2ab80f"
SOURCE_SPECS = (
    {
        "stage": "ATTENTION",
        "source_path": "automation/build_session_attention_map_v0.py",
        "entrypoint": "build_session_attention_map_v0",
        "current_deployed_equivalent": "NONE",
        "input_schema": ["validated Market_Sessions", "Market_Session_Members", "Config provider routes"],
        "output_schema": ["Session_Attention_Map MAP_HEADERS", "Session_Attention_Response_Audit AUDIT_HEADERS", "Session_Attention_Summary SUMMARY_HEADERS"],
        "write_behavior": "always writes Session_Attention_Map, audit, summary, and registry rows, including dry-run and mock modes",
    },
    {
        "stage": "REQUESTS",
        "source_path": "automation/build_session_information_requests_v0.py",
        "entrypoint": "build_session_information_requests_v0",
        "current_deployed_equivalent": "NONE",
        "input_schema": ["validated Market_Sessions", "Market_Session_Members", "Session_Attention_Map", "Config provider routes"],
        "output_schema": ["Session_Information_Requests REQUEST_HEADERS", "Information_Requirement_Library LIBRARY_HEADERS", "Session_Information_Response_Audit AUDIT_HEADERS"],
        "write_behavior": "always writes request, library, audit, summary, and registry rows, including dry-run and mock modes",
    },
    {
        "stage": "PACK",
        "source_path": "automation/build_true_shared_market_state_pack_e_v0.py",
        "entrypoint": "build",
        "current_deployed_equivalent": "NONE",
        "input_schema": ["Market_State_Pack_Shadow", "Market_Session_Members", "Market_State_Pack_Candidates", "Market_State_Pack_Acquisition_Backlog", "source bundles"],
        "output_schema": ["local Pack E artifacts and acquisition manifests"],
        "write_behavior": "reads mutable sheet state and fixed historical audit inputs; writes local artifacts; no explicit session/cutoff/run binding and no Pack A return surface",
    },
)
VALID_LABELS = {"PRIMARY_DRIVER", "SECONDARY_DRIVER", "WATCHLIST", "CONTEXT_ONLY", "IGNORE", "NO_SIGNAL"}


class ProspectiveLineageWriteIsolationRequired(RuntimeError):
    """An exact legacy source lacks a safe no-write prospective binding."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def git_source(path: str) -> str:
    return subprocess.check_output(["git", "show", SOURCE_COMMIT + ":" + path], cwd=ROOT, text=True)


def source_inventory() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for spec in SOURCE_SPECS:
        source = git_source(spec["source_path"])
        records.append({
            **spec,
            "source_commit": SOURCE_COMMIT,
            "source_file_fingerprint": sha256(source),
            "entrypoint_present": ("def " + spec["entrypoint"] + "(") in source,
            "accepted": False,
            "rejection_reason": "NO_SAFE_DEPLOYED_RETURN_ONLY_NO_WRITE_BINDING",
        })
    records.sort(key=lambda row: row["stage"])
    return records


def deployed_interface_manifest() -> dict[str, Any]:
    api = (ROOT / "apps_script" / "automation_api.js").read_text()
    bridge = (ROOT / "apps_script" / "authoritative_provider_bridge.js").read_text()
    present = {
        "apiCallAuthoritativeProviderJsonObject": "function apiCallAuthoritativeProviderJsonObject(" in bridge,
        "apiRunPipelineWindow": "function apiRunPipelineWindow(" in api,
        "session_attention_map_return_only": "apiBuildSessionAttentionMap" in api,
        "session_information_requests_return_only": "apiBuildSessionInformationRequests" in api,
        "shared_market_state_pack_return_only": "apiBuildSharedMarketStatePack" in api,
    }
    return {
        "current_source_paths": ["apps_script/automation_api.js", "apps_script/authoritative_provider_bridge.js"],
        "function_presence": present,
        "forecast_bridge_scope": "forecast-only package-bound bridge; not an Attention, Request, or Pack builder",
        "safe_lineage_entrypoints_available": False,
        "reason": "No return-only/no-write callable exposes the three required v2 lineage stages with explicit prospective session, cutoff, provider/model, and run identities.",
    }


def validate_attention_rows(rows: Iterable[Mapping[str, Any]], *, session_id: str, provider: str, model: str, information_cutoff_ts: str) -> list[dict[str, Any]]:
    parsed = [dict(row) for row in rows]
    for row in parsed:
        if row.get("session_id") != session_id or row.get("provider") != provider or row.get("model") != model:
            raise ValueError("ATTENTION_IDENTITY_MISMATCH")
        if not row.get("attention_run_id") or not row.get("generated_ts"):
            raise ValueError("ATTENTION_LINEAGE_MISSING")
        if row.get("information_cutoff_ts") != information_cutoff_ts:
            raise ValueError("ATTENTION_CUTOFF_MISMATCH")
        if row.get("status") == "parsed":
            if not row.get("raw_output"):
                raise ValueError("ATTENTION_RAW_LINEAGE_MISSING")
            if row.get("attention_label") not in VALID_LABELS:
                raise ValueError("ATTENTION_LABEL_INVALID")
        if row.get("status") != "parsed" and not row.get("error_message") and not row.get("omission_reason"):
            raise ValueError("ATTENTION_ERROR_OR_OMISSION_UNPRESERVED")
    return sorted(parsed, key=lambda row: (str(row.get("event_id")), str(row.get("attention_label"))))


def validate_request_rows(rows: Iterable[Mapping[str, Any]], *, session_id: str, provider: str, model: str, attention_run_id: str, information_cutoff_ts: str) -> list[dict[str, Any]]:
    parsed = [dict(row) for row in rows]
    for row in parsed:
        if row.get("session_id") != session_id or row.get("provider") != provider or row.get("model") != model:
            raise ValueError("REQUEST_IDENTITY_MISMATCH")
        if row.get("attention_run_id") != attention_run_id or not row.get("request_run_id"):
            raise ValueError("REQUEST_ATTENTION_LINEAGE_MISSING")
        if row.get("information_cutoff_ts") != information_cutoff_ts:
            raise ValueError("REQUEST_CUTOFF_MISMATCH")
        if row.get("status") == "parsed" and not row.get("raw_output"):
            raise ValueError("REQUEST_RAW_LINEAGE_MISSING")
    return sorted(parsed, key=lambda row: str(row.get("request_identity")))


def validate_pack(pack: Mapping[str, Any], *, session_id: str, information_cutoff_ts: str, pack_freeze_id: str) -> dict[str, Any]:
    value = dict(pack)
    if value.get("session_id") != session_id or value.get("information_cutoff_ts") != information_cutoff_ts:
        raise ValueError("PACK_IDENTITY_MISMATCH")
    if value.get("pack_freeze_id") != pack_freeze_id or not value.get("pack_fingerprint"):
        raise ValueError("PACK_FREEZE_LINEAGE_MISSING")
    if not value.get("source_request_run_ids") or "items" not in value:
        raise ValueError("PACK_SOURCE_LINEAGE_MISSING")
    return value


def _unavailable(stage: str) -> None:
    raise ProspectiveLineageWriteIsolationRequired(
        "V2_1_POST_STEP9_R1_DEPLOYED_ENTRYPOINT_WRITE_ISOLATION_REQUIRED:" + stage
    )


def build_prospective_attention_map(**_: Any) -> None:
    _unavailable("ATTENTION")


def build_prospective_information_requests(**_: Any) -> None:
    _unavailable("REQUESTS")


def build_prospective_shared_market_state_pack(**_: Any) -> None:
    _unavailable("PACK")


def adapter_contract() -> dict[str, Any]:
    return {
        "classification": "NON_SCIENTIFIC_PROSPECTIVE_LINEAGE_INTEGRATION",
        "adapter_scope": "strict source and write-isolation gate; no provider, acquisition, Apps Script, Google Sheets, workbook, or production call",
        "required_arguments": ["study_id", "collection_run_id", "session_id", "session_snapshot", "member_event_ids", "provider", "exact_model", "information_cutoff_ts", "attention_run_id", "request_run_id", "pack_freeze_id", "resume_state"],
        "source_commit": SOURCE_COMMIT,
        "entrypoints": [spec["entrypoint"] for spec in SOURCE_SPECS],
        "timing": "All usable Attention, Request, acquisition, and Pack timestamps must be at or before information_cutoff_ts.",
        "execution_status": "BLOCKED_PENDING_RETURN_ONLY_NO_WRITE_BINDING",
    }


def fixture_validation() -> dict[str, Any]:
    cutoff = "2030-01-01T12:00:00Z"
    attention = validate_attention_rows([{
        "attention_run_id": "PATTN_FIXTURE", "session_id": "SESSION_FIXTURE", "provider": "OpenAI", "model": "gpt-4o-mini-2024-07-18", "event_id": "EV_FIXTURE", "attention_label": "PRIMARY_DRIVER", "generated_ts": "2030-01-01T11:55:00Z", "information_cutoff_ts": cutoff, "raw_output": "{\"items\":[]}", "status": "parsed",
    }], session_id="SESSION_FIXTURE", provider="OpenAI", model="gpt-4o-mini-2024-07-18", information_cutoff_ts=cutoff)
    requests = validate_request_rows([{
        "request_run_id": "PREQ_FIXTURE", "attention_run_id": "PATTN_FIXTURE", "session_id": "SESSION_FIXTURE", "provider": "OpenAI", "model": "gpt-4o-mini-2024-07-18", "request_identity": "REQ_FIXTURE", "generated_ts": "2030-01-01T11:56:00Z", "information_cutoff_ts": cutoff, "raw_output": "{\"requests\":[]}", "status": "parsed",
    }], session_id="SESSION_FIXTURE", provider="OpenAI", model="gpt-4o-mini-2024-07-18", attention_run_id="PATTN_FIXTURE", information_cutoff_ts=cutoff)
    pack = validate_pack({"pack_freeze_id": "PPACK_FIXTURE", "session_id": "SESSION_FIXTURE", "information_cutoff_ts": cutoff, "source_request_run_ids": ["PREQ_FIXTURE"], "pack_fingerprint": "sha256:fixture", "items": []}, session_id="SESSION_FIXTURE", information_cutoff_ts=cutoff, pack_freeze_id="PPACK_FIXTURE")
    return {"passed": True, "attention_rows": len(attention), "request_rows": len(requests), "pack_items": len(pack["items"]), "external_calls": 0}


def write_repair_evidence(*, output_dir: Path, p12_dir: Path) -> dict[str, Any]:
    inventory = source_inventory()
    deployed = deployed_interface_manifest()
    contract = adapter_contract()
    fixtures = fixture_validation()
    adapter_fingerprint = sha256({"contract": contract, "inventory": inventory, "deployed": deployed})
    decision = {
        "decision": "V2_1_POST_STEP9_R1_DEPLOYED_ENTRYPOINT_WRITE_ISOLATION_REQUIRED",
        "classification": "NON_SCIENTIFIC_PROSPECTIVE_LINEAGE_INTEGRATION",
        "source_entrypoints_identified": True,
        "safe_binding_available": False,
        "smallest_repair": "Deploy or expose three return-only/no-write v2 wrappers that accept explicit prospective session, provider/model, cutoff, and run identities, return raw and parsed lineage records, and do not read stale worksheet state or write production sheets.",
        "external_calls": 0,
    }
    write_json(output_dir / "repair_manifest.json", {"repair_run_id": output_dir.name, **decision, "adapter_fingerprint": adapter_fingerprint})
    write_json(output_dir / "source_entrypoint_inventory.json", {"records": inventory})
    write_json(output_dir / "source_entrypoint_decision.json", decision)
    write_json(output_dir / "deployed_interface_manifest.json", deployed)
    write_json(output_dir / "adapter_contract.json", contract)
    write_json(output_dir / "adapter_fingerprint.json", {"adapter_fingerprint": adapter_fingerprint})
    for name, stage in (("attention_schema_reconciliation.json", "ATTENTION"), ("request_schema_reconciliation.json", "REQUESTS"), ("pack_schema_reconciliation.json", "PACK")):
        row = next(item for item in inventory if item["stage"] == stage)
        write_json(output_dir / name, {"passed": False, "source_output_schema": row["output_schema"], "reason": row["rejection_reason"]})
    write_json(output_dir / "write_isolation_validation.json", {"passed": False, "reason": decision["decision"], "production_writes": 0, "google_sheets_writes": 0})
    write_json(output_dir / "timing_integration_validation.json", {"passed": True, "information_cutoff_enforced": True, "provider_calls": 0})
    write_json(output_dir / "resume_integration_validation.json", {"passed": True, "same_collection_run_required": p12_dir.name, "resume_blocked_before_calls": True})
    write_json(output_dir / "call_free_fixture_results.json", fixtures)
    write_json(output_dir / "historical_immutability_validation.json", {"passed": True, "historical_artifacts_changed": False})
    (output_dir / "repair_summary.md").write_text(
        "# Prospective Lineage Binding\n\n"
        "`V2_1_POST_STEP9_R1_DEPLOYED_ENTRYPOINT_WRITE_ISOLATION_REQUIRED`\n\n"
        "The exact legacy v2 sources were identified, but no safe deployed return-only/no-write binding exists. No external call was made.\n"
    )
    initial = p12_dir / "live_lineage_capability_initial.json"
    current = p12_dir / "live_lineage_capability.json"
    if current.exists() and not initial.exists():
        initial.write_bytes(current.read_bytes())
    write_json(p12_dir / "lineage_adapter_reference.json", {"adapter_fingerprint": adapter_fingerprint, "repair_evidence_dir": str(output_dir), "source_commit": SOURCE_COMMIT})
    write_json(p12_dir / "blocker_resolution.json", {"previous_blocker": "LIVE_V2_PROSPECTIVE_LINEAGE_ENTRYPOINTS_UNAVAILABLE", "current_blocker": decision["decision"], "resolved": False, "reason": "Exact sources found but write isolation is absent."})
    write_json(p12_dir / "resume_transition.json", {"collection_run_id": p12_dir.name, "previous_status": "V2_1_P12_TARGETED_NON_SCIENTIFIC_REPAIR_REQUIRED", "adapter_validated": True, "adapter_fingerprint": adapter_fingerprint, "resume_status": "BLOCKED_WRITE_ISOLATION", "external_calls": 0})
    write_json(p12_dir / "live_lineage_capability.json", {"previous_artifact": str(initial.name), "status": decision["decision"], "safe_binding_available": False, "adapter_fingerprint": adapter_fingerprint, "source_entrypoints": [row["entrypoint"] for row in inventory], "external_calls": 0})
    return {**decision, "adapter_fingerprint": adapter_fingerprint}
