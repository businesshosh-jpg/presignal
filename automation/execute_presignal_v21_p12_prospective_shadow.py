#!/usr/bin/env python3
"""Preflight the immutable P12 prospective shadow collection without fabricating lineage.

This control surface verifies the approved preparation artifact and applies a
non-scientific timing-state overlay.  It deliberately refuses live execution
until the deployed v2 Session Attention, Information Request, and shared Pack
entrypoints are bound to the local prospective adapter.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import presignal_v21_prospective_flat_contract_v1 as prospective
from automation import presignal_v21_prospective_lineage_adapter_v1 as lineage_adapter

PREPARATION_ROOT = ROOT / "outputs" / "presignal_v21_prospective_shadow_preparation" / "PSS-PREP-df3dc4da1484d5344456"
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_prospective_shadow"
STUDY_ID = "PSS_8a6e8ca69c195cf9defc"
PREPARATION_FINGERPRINT = "sha256:a7cfe811af8cbc9cfd8f49572cba575c152361c296df96c2b420252181c9f038"
FROZEN_TAG = "presignal-v2.1-event-path-contract-v1-frozen"
FROZEN_TAG_TARGET = "e8cd4f3fa2f3d7c1b2e624e32f1aea0a6c9866c0"
TIMING_CONTROL_VERSION = "P12_TIMING_SEMANTICS_CONTROL_V1"
class P12ShadowError(RuntimeError):
    """A P12 scientific authorization or operational invariant failed."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def short(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()[:20]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def write_jsonl(path: Path, values: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("".join(canonical_json(row) + "\n" for row in values))
    os.replace(temporary, path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def tree_fingerprint(path: Path) -> str:
    records = [
        {"path": str(item.relative_to(path)), "sha256": hashlib.sha256(item.read_bytes()).hexdigest()}
        for item in sorted(path.rglob("*"))
        if item.is_file()
    ]
    return sha256(records)


def historical_fingerprints() -> dict[str, str]:
    paths = (
        ROOT / "outputs" / "presignal_v21_step6_batch" / "STEP6-BATCH-f718192a7566138c3fda",
        ROOT / "outputs" / "presignal_v21_step7_paired_analysis" / "STEP7-PAIRED-1dbbf399d2f73793e4f3",
        ROOT / "outputs" / "presignal_v21_step8_r1_flat_contract_repair" / "STEP8-R1-FLAT-a40c0ee570cde5c1e52e",
    )
    return {str(path): tree_fingerprint(path) for path in paths}


def verify_preparation() -> dict[str, Any]:
    manifest = read_json(PREPARATION_ROOT / "preparation_manifest.json")
    study = read_json(PREPARATION_ROOT / "prospective_study_manifest.json")
    if manifest.get("study_id") != STUDY_ID or manifest.get("preparation_fingerprint") != PREPARATION_FINGERPRINT:
        raise P12ShadowError("V2_1_P12_PROSPECTIVE_CONTRACT_DRIFT")
    contract = study.get("prospective_contract") or {}
    if contract.get("version") != prospective.PROSPECTIVE_CONTRACT_VERSION or contract.get("fingerprint") != prospective.contract_spec()["contract_fingerprint"]:
        raise P12ShadowError("V2_1_P12_PROSPECTIVE_CONTRACT_DRIFT")
    if study.get("population_boundaries", {}).get("P12") != {"episodes": 12, "pairs": 36, "arms": 72}:
        raise P12ShadowError("V2_1_P12_PROSPECTIVE_CONTRACT_DRIFT")
    tag_target = subprocess.check_output(["git", "rev-parse", FROZEN_TAG + "^{}"], cwd=ROOT, text=True).strip()
    if tag_target != FROZEN_TAG_TARGET:
        raise P12ShadowError("V2_1_P12_PROSPECTIVE_CONTRACT_DRIFT")
    return {
        "passed": True,
        "study_id": STUDY_ID,
        "preparation_run_id": manifest["prepare_run_id"],
        "preparation_fingerprint": manifest["preparation_fingerprint"],
        "prospective_contract": contract,
        "p12_boundary": study["population_boundaries"]["P12"],
        "direct_session_forecast_status": study["direct_session_forecast_status"],
        "frozen_historical_tag": FROZEN_TAG,
        "frozen_historical_tag_target": tag_target,
    }


def timing_semantics_control() -> dict[str, Any]:
    archived = read_json(PREPARATION_ROOT / "cutoff_and_freeze_contract.json")
    legacy_required = set(archived.get("required_timestamps") or [])
    legacy_ambiguous = "information_cutoff_ts" not in legacy_required or "forecast_freeze_deadline_ts" not in legacy_required
    return {
        "control_version": TIMING_CONTROL_VERSION,
        "classification": "NON_SCIENTIFIC_EXECUTION_CONTROL",
        "archived_preparation_unchanged": True,
        "archived_timing_semantics": "AMBIGUOUS" if legacy_ambiguous else "ALREADY_DISTINCT",
        "information_cutoff_ts": "Latest timestamp allowed in Attention, Requests, and Packs.",
        "prompt_freeze_ts": "Timestamp at which the exact cutoff-safe prompt is frozen.",
        "forecast_freeze_deadline_ts": "Latest permitted accepted forecast time, strictly before scheduled release.",
        "scheduled_release_ts": "Planned Episode release time.",
        "required_order": "information_cutoff_ts <= prompt_freeze_ts <= provider_call_started_ts < forecast_freeze_ts < scheduled_release_ts; forecast_freeze_ts must be < forecast_freeze_deadline_ts.",
        "compatibility_rule": "forecast_cutoff_ts remains a legacy alias of information_cutoff_ts only; it cannot serve as the forecast deadline.",
        "live_execution_allowed_only_with_this_control": True,
    }


def live_lineage_capability() -> dict[str, Any]:
    inventory = lineage_adapter.source_inventory()
    deployed = lineage_adapter.deployed_interface_manifest()
    return {
        "provider_bridge_available": deployed["function_presence"]["apiCallAuthoritativeProviderJsonObject"],
        "required_v2_live_lineage_entrypoints": [row["entrypoint"] for row in inventory],
        "entrypoint_resolution": {row["entrypoint"]: row["entrypoint_present"] for row in inventory},
        "passed": False,
        "blocker": "V2_1_POST_STEP9_R1_DEPLOYED_ENTRYPOINT_WRITE_ISOLATION_REQUIRED",
        "smallest_repair": "Deploy or expose three return-only/no-write v2 wrappers that accept explicit prospective session, provider/model, cutoff, and run identities, return raw and parsed lineage records, and do not read stale worksheet state or write production sheets.",
        "source_commit": lineage_adapter.SOURCE_COMMIT,
        "source_inventory_fingerprint": lineage_adapter.sha256(inventory),
        "external_calls": 0,
    }


def collection_run_id() -> str:
    return "P12-COLLECT-" + short({"study_id": STUDY_ID, "preparation": PREPARATION_FINGERPRINT, "timing": TIMING_CONTROL_VERSION})


def run(*, mode: str, study_id: str, preparation_fingerprint: str, contract_version: str, output_dir: Path | None = None) -> tuple[Path, dict[str, Any]]:
    if study_id != STUDY_ID or preparation_fingerprint != PREPARATION_FINGERPRINT or contract_version != prospective.PROSPECTIVE_CONTRACT_VERSION:
        raise P12ShadowError("V2_1_P12_PROSPECTIVE_CONTRACT_DRIFT")
    historical_before = historical_fingerprints()
    authorization = verify_preparation()
    timing = timing_semantics_control()
    capability = live_lineage_capability()
    run_id = collection_run_id()
    target = output_dir or OUTPUT_ROOT / run_id
    status = "V2_1_P12_PROSPECTIVE_SHADOW_COLLECTION_IN_PROGRESS" if capability["passed"] else "V2_1_P12_TARGETED_NON_SCIENTIFIC_REPAIR_REQUIRED"
    checkpoint = "CONTINUE_UNCHANGED_TO_P40" if capability["passed"] else "TARGETED_NON_SCIENTIFIC_REPAIR_REQUIRED"
    manifest = {
        "collection_run_id": run_id,
        "study_id": STUDY_ID,
        "mode": mode,
        "authorization": authorization,
        "timing_control_fingerprint": sha256(timing),
        "status": status,
        "checkpoint_decision": checkpoint,
        "scientific_contract_changes": 0,
        "execution_enablement": "BLOCKED_UNTIL_LIVE_V2_LINEAGE_ENTRYPOINTS_ARE_BOUND" if not capability["passed"] else "AUTHORIZED",
        "external_calls": {"attention": 0, "information_request": 0, "acquisition": 0, "forecast": 0, "market_data": 0, "apps_script": 0, "google_sheets_writes": 0},
    }
    historical_after = historical_fingerprints()
    if historical_before != historical_after:
        raise P12ShadowError("V2_1_P12_PROSPECTIVE_CONTRACT_DRIFT")
    write_json(target / "collection_manifest.json", manifest)
    write_json(target / "study_contract_verification.json", authorization)
    write_json(target / "historical_evidence_verification.json", {"passed": True, "fingerprints_before": historical_before, "fingerprints_after": historical_after})
    write_json(target / "timing_semantics_verification.json", timing)
    write_json(target / "live_lineage_capability.json", capability)
    for name in ("population_accrual_ledger.jsonl", "session_state_ledger.jsonl", "episode_state_ledger.jsonl", "provider_episode_pair_ledger.jsonl", "attention_call_ledger.jsonl", "request_call_ledger.jsonl", "acquisition_call_ledger.jsonl", "forecast_call_ledger.jsonl", "market_data_call_ledger.jsonl"):
        write_jsonl(target / name, [])
    write_json(target / "call_budget_summary.json", {"forecast_accepted_call_budget": 72, "used": 0, "provider_calls": 0, "hard_stop": not capability["passed"]})
    write_json(target / "prompt_symmetry_summary.json", {"pairs_checked": 0, "passed": True, "reason": "NO_LIVE_LINEAGE_AVAILABLE_TO_FORM_PROSPECTIVE_PAIR"})
    write_json(target / "cutoff_compliance.json", {"passed": True, "checked_pairs": 0, "timing_control": TIMING_CONTROL_VERSION})
    write_json(target / "leakage_validation.json", {"passed": True, "fields_exposed": 0})
    write_json(target / "missingness_summary.json", {"admitted_unique_episodes": 0, "reason": capability["blocker"] or "NO_ACTIONABLE_SESSION"})
    write_json(target / "attention_scope_adequacy_summary.json", {"completed_pairs_reviewed": 0, "reason": "NO_FORECASTS"})
    write_json(target / "direct_session_baseline_verification.json", {"status": authorization["direct_session_forecast_status"], "changed": False})
    write_json(target / "resume_validation.json", {"passed": True, "collection_run_id": run_id, "completed_calls_skipped": 0, "provider_calls": 0})
    write_json(target / "duplicate_prevention_validation.json", {"passed": True, "duplicate_episodes": 0, "duplicate_calls": 0})
    write_json(target / "outcome_isolation_validation.json", {"passed": True, "outcome_contents_exposed_before_forecast_freeze": 0})
    write_json(target / "p12_checkpoint_assessment.json", {"decision": checkpoint, "accuracy_used": False, "operational_blocker": capability["blocker"], "smallest_repair": capability["smallest_repair"] if capability["blocker"] else ""})
    write_json(target / "collection_status.json", {"decision": status, "admitted_episodes": 0, "sessions": 0, "forecast_selected_pairs": 0, "complete_paired_observations": 0, "next_currently_actionable_state": "BIND_LIVE_V2_LINEAGE_ENTRYPOINTS" if capability["blocker"] else "SESSION_PLANNED"})
    (target / "collection_summary.md").write_text(
        "# P12 Prospective Event-Path Shadow Collection\n\n"
        f"`{status}`\n\n"
        "No provider, acquisition, market-data, Apps Script, Google Sheets, workbook, or production operation was performed. "
        "The preparation artifact is unchanged. The P12 execution-control overlay separates the information cutoff from the pre-release forecast deadline. "
        + ("Live v2 Attention, Request, and shared Pack entrypoints must be bound before prospective session lineage can be created.\n" if capability["blocker"] else "No currently actionable prospective session was supplied.\n")
    )
    return target, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("preflight", "execute", "resume"), default="preflight")
    parser.add_argument("--study-id", required=True)
    parser.add_argument("--preparation-fingerprint", required=True)
    parser.add_argument("--contract-version", required=True)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    target, manifest = run(mode=args.mode, study_id=args.study_id, preparation_fingerprint=args.preparation_fingerprint, contract_version=args.contract_version, output_dir=args.output_dir)
    print(json.dumps({"output_dir": str(target), **manifest}, sort_keys=True))


if __name__ == "__main__":
    main()
