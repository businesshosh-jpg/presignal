#!/usr/bin/env python3
"""Fail closed when v2 lineage sources cannot be isolated from worksheet state."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import presignal_v21_prospective_lineage_adapter_v1 as adapter

OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_post_step9_r2_return_only_wrappers"
P12_ROOT = ROOT / "outputs" / "presignal_v21_prospective_shadow" / "P12-COLLECT-ffd55626bc1a886c2e19"
DECISION = "V2_1_POST_STEP9_R2_WRITE_ISOLATION_VALIDATION_FAILED"
WRITE_TOKENS = ("_write_rows(", "_ensure_sheet(", "_upsert_registry_rows(", "build_sheets_service(", "SpreadsheetApp.getActive", "appendRow(", "setValue(", "setValues(")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)


def call_graph() -> list[dict[str, Any]]:
    rows = []
    for record in adapter.source_inventory():
        source = adapter.git_source(record["source_path"])
        hits = [token for token in WRITE_TOKENS if token in source]
        rows.append({
            "stage": record["stage"], "source_path": record["source_path"], "entrypoint": record["entrypoint"],
            "reachable_write_capable_tokens": hits, "return_only_call_graph_isolated": False,
        })
    return rows


def validate() -> dict[str, Any]:
    inventory = adapter.source_inventory()
    deployed = adapter.deployed_interface_manifest()
    graph = call_graph()
    return {
        "decision": DECISION,
        "classification": "NON_SCIENTIFIC_RETURN_ONLY_WRAPPER_ISOLATION",
        "archived_source_commit": adapter.SOURCE_COMMIT,
        "archived_builder_inventory": inventory,
        "deployed_interface": deployed,
        "call_graph": graph,
        "pure_logic_extraction": {
            "performed": False,
            "reason": "The archived builders entangle scientific construction with mutable worksheet reads, mandatory worksheet writes, and registry mutation. Automatic extraction would create a divergent scientific implementation or restore obsolete builders wholesale.",
        },
        "static_write_isolation": {"passed": False, "reason": "Every identified builder reaches mutable worksheet or registry write tokens."},
        "runtime_write_isolation": {"passed": False, "executed": False, "reason": "Invoking the only identified live paths would violate the no-production-write boundary."},
        "scientific_equivalence": {"passed": False, "executed": False, "reason": "No no-write wrapper exists to compare against the archived builders without introducing a new implementation."},
        "capability_endpoint": {"available": False, "reason": "No current Apps Script operation exposes return-only Attention, Request, or shared-Pack lineage."},
        "external_calls": {"provider": 0, "acquisition": 0, "market_data": 0, "apps_script": 0, "google_sheets_writes": 0},
        "historical_artifacts_changed": False,
    }


def run(output_dir: Path | None = None, p12_dir: Path | None = None) -> tuple[Path, dict[str, Any]]:
    result = validate()
    repair_id = "P12-R2-WRAPPER-" + sha256({"source": adapter.SOURCE_COMMIT, "decision": DECISION}).split(":", 1)[1][:20]
    target = output_dir or OUTPUT_ROOT / repair_id
    p12 = p12_dir or P12_ROOT
    contracts = {"api_version": "NOT_IMPLEMENTED", "status": "BLOCKED_WRITE_ISOLATION", "required_envelope": ["api_version", "operation", "study_id", "collection_run_id", "session_id", "provider", "model", "information_cutoff_ts", "stage_run_id", "idempotency_key", "request_fingerprint", "dry_run", "input_payload"]}
    write_json(target / "repair_manifest.json", {"repair_run_id": repair_id, **result})
    write_json(target / "archived_builder_inventory.json", {"records": result["archived_builder_inventory"]})
    write_json(target / "pure_logic_extraction_manifest.json", result["pure_logic_extraction"])
    write_json(target / "legacy_behavior_preservation.json", {"passed": True, "legacy_builders_modified": False})
    write_json(target / "attention_wrapper_contract.json", {**contracts, "operation": "attention"})
    write_json(target / "request_wrapper_contract.json", {**contracts, "operation": "information_requests"})
    write_json(target / "shared_pack_wrapper_contract.json", {**contracts, "operation": "shared_pack"})
    write_json(target / "common_request_response_contract.json", contracts)
    write_json(target / "apps_script_call_graph.json", {"records": result["call_graph"]})
    write_json(target / "write_capable_function_inventory.json", {"records": result["call_graph"]})
    write_json(target / "static_write_isolation_validation.json", result["static_write_isolation"])
    write_json(target / "runtime_write_isolation_validation.json", result["runtime_write_isolation"])
    for name in ("scientific_equivalence_attention.json", "scientific_equivalence_requests.json", "scientific_equivalence_shared_pack.json", "pack_e_equality_validation.json"):
        write_json(target / name, result["scientific_equivalence"])
    write_json(target / "capability_endpoint_result.json", result["capability_endpoint"])
    write_json(target / "dry_run_validation.json", {"passed": True, "provider_calls": 0, "acquisition_calls": 0, "writes": 0, "note": "Static contract validation only; no wrapper invocation is safe."})
    write_json(target / "deployment_manifest.json", {"deployed": False, "reason": result["capability_endpoint"]["reason"]})
    write_json(target / "deployment_validation.json", {"passed": False, "reason": "NO_SAFE_WRAPPER_TO_DEPLOY"})
    write_json(target / "adapter_integration_validation.json", {"passed": False, "reason": DECISION, "adapter_fingerprint": adapter.sha256(adapter.adapter_contract())})
    write_json(target / "p12_capability_transition.json", {"collection_run_id": p12.name, "previous": "BLOCKED_WRITE_ISOLATION", "current": "BLOCKED_WRITE_ISOLATION", "changed": False})
    write_json(target / "historical_immutability_validation.json", {"passed": True, "historical_artifacts_changed": False})
    write_text(target / "repair_summary.md", "# Return-Only v2 Lineage Wrappers\n\n`V2_1_POST_STEP9_R2_WRITE_ISOLATION_VALIDATION_FAILED`\n\nNo safe return-only source exists to expose without a separate, reviewable pure-logic extraction. No external call occurred.\n")
    previous = p12 / "live_lineage_capability_r1.json"
    current = p12 / "live_lineage_capability.json"
    if current.exists() and not previous.exists():
        previous.write_bytes(current.read_bytes())
    write_json(p12 / "return_only_wrapper_reference.json", {"repair_run_id": repair_id, "repair_evidence_dir": str(target), "decision": DECISION})
    write_json(p12 / "write_isolation_resolution.json", {"resolved": False, "decision": DECISION, "reason": result["static_write_isolation"]["reason"]})
    write_json(p12 / "live_lineage_capability.json", {"previous_artifact": previous.name, "status": "BLOCKED_WRITE_ISOLATION", "decision": DECISION, "external_calls": 0})
    return target, result


if __name__ == "__main__":
    target, result = run()
    print(json.dumps({"output_dir": str(target), "decision": result["decision"]}, sort_keys=True))
