#!/usr/bin/env python3
"""Freeze a new execution-integrity package from a blocked, unexecuted package.

The blocked package remains immutable apart from its supersession marker.  This
builder copies every scientific snapshot component from it and only regenerates
run-scoped execution metadata and forecast identities.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "outputs" / "phase9_authoritative_historical_replay"
BLOCKED_RUN_ID = "9-AUTHORITATIVE-HISTORICAL-REPLAY-20260717T044112Z"
BLOCKED_PACKAGE = OUTPUT_ROOT / BLOCKED_RUN_ID
CONTRACT_FP = "7ad8b1537f59041a9f9311fbbd547d682a5a15d7fc55a1bc225ca14d24c42e85"
SCHEMA = "v2.0-layered-shadow-v0"
BRIDGE_SCHEMA = "authoritative_historical_replay_bridge_v1"
APPS_SCRIPT_PROJECT_ID = "1A-iJDmNb1RFSCGS9YIPJfboNCO3sGUS1OomKf4yyQhQceSJlgXqWdGA9"
APPS_SCRIPT_VERSION = 74
APPS_SCRIPT_PROJECT_FINGERPRINT = "9449bcc334ff608a947e838151d8b10224bc97d493ea30fb9386397d8c7e5b50"
APPS_SCRIPT_BRIDGE_FILE_NAME = "authoritative_provider_bridge"
SCIENTIFIC_SNAPSHOT_FILES = (
    "authoritative_sessions.jsonl",
    "authoritative_session_members.jsonl",
    "authoritative_requests.jsonl",
    "authoritative_pack_references.jsonl",
    "authoritative_excluded_sessions.jsonl",
)


def canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def sha(value: Any) -> str:
    return hashlib.sha256(canon(value).encode("utf-8")).hexdigest()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())


def rows(path: Path) -> List[Dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def write_jsonl(path: Path, values: Iterable[Mapping[str, Any]]) -> None:
    path.write_text("".join(canon(value) + "\n" for value in values))


def git_value(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()


def git_binding() -> Dict[str, Any]:
    status = git_value("status", "--porcelain=v1").splitlines()
    return {
        "commit": git_value("rev-parse", "HEAD"),
        "branch": git_value("branch", "--show-current"),
        "dirty": bool(status),
        "dirty_status_fingerprint": sha(status),
        "tracked_modified_paths": sorted(line[3:] for line in status if line[:2] != "??"),
        "untracked_count": sum(1 for line in status if line.startswith("??")),
    }


def _validate_blocked_snapshot(blocked: Path) -> Dict[str, Any]:
    snapshot = blocked / "input_snapshot"
    manifest = read_json(snapshot / "authoritative_replay_input_manifest.json")
    expected = manifest.get("component_fingerprints") or {}
    for name, fingerprint in expected.items():
        path = snapshot / name
        if not path.exists() or file_sha(path) != fingerprint:
            raise RuntimeError("BLOCKED_SNAPSHOT_COMPONENT_FINGERPRINT_MISMATCH:" + name)
    counts = manifest.get("record_counts") or {}
    if counts != {"eligible_sessions": 239, "excluded_sessions": 10, "forecast_identities": 1434, "pack_references": 239}:
        raise RuntimeError("BLOCKED_SNAPSHOT_POPULATION_MISMATCH")
    if read_json(blocked / "manifests" / "package_manifest.json").get("authoritative_replay_started"):
        raise RuntimeError("BLOCKED_PACKAGE_WAS_ALREADY_EXECUTED")
    for relative in SCIENTIFIC_SNAPSHOT_FILES:
        if not (snapshot / relative).exists():
            raise RuntimeError("BLOCKED_SCIENTIFIC_COMPONENT_MISSING:" + relative)
    return manifest


def _population(run_id: str, blocked_snapshot: Path, config: Mapping[str, Any]) -> List[Dict[str, Any]]:
    old_population = rows(blocked_snapshot / "authoritative_forecast_population.jsonl")
    identity_fields = ("session_id", "provider", "model", "arm", "pack_fingerprint")
    if len(old_population) != 1434 or len({row["forecast_identity"] for row in old_population}) != 1434:
        raise RuntimeError("BLOCKED_FORECAST_POPULATION_MISMATCH")
    population: List[Dict[str, Any]] = []
    for old in old_population:
        identity_payload = {
            "run_id": run_id,
            **{field: old.get(field, "") for field in identity_fields},
            "contract": config["stage4a_contract"]["fingerprint"],
            "schema": config["schema_version"],
            "prompt": config["prompt_fingerprint"],
            "parser": config["parser_fingerprint"],
            "storage": config["storage_fingerprint"],
        }
        population.append({
            "run_id": run_id,
            "forecast_identity": "AHRF_" + sha(identity_payload)[:28],
            **{field: old.get(field, "") for field in identity_fields},
            "stage4a_contract_fingerprint": config["stage4a_contract"]["fingerprint"],
            "prediction_schema_version": config["schema_version"],
            "prompt_fingerprint": config["prompt_fingerprint"],
            "parser_fingerprint": config["parser_fingerprint"],
            "storage_fingerprint": config["storage_fingerprint"],
        })
    if len({row["forecast_identity"] for row in population}) != 1434:
        raise RuntimeError("REPAIRED_FORECAST_IDENTITIES_NOT_UNIQUE")
    return population


def _assert_population(population: List[Dict[str, Any]], snapshot: Path) -> None:
    excluded = {row["session_id"] for row in rows(snapshot / "authoritative_excluded_sessions.jsonl")}
    sessions = {row["session_id"] for row in rows(snapshot / "authoritative_sessions.jsonl")}
    packs = {row["session_id"] for row in rows(snapshot / "authoritative_pack_references.jsonl")}
    if len(sessions) != 239 or len(packs) != 239 or any(row["session_id"] in excluded for row in population):
        raise RuntimeError("REPAIRED_POPULATION_SESSION_RECONCILIATION_FAILED")
    if any(row["session_id"] not in sessions or row["session_id"] not in packs for row in population):
        raise RuntimeError("REPAIRED_POPULATION_MISSING_SESSION_OR_PACK")
    if sum(row["arm"] == "A" for row in population) != 717 or sum(row["arm"] == "E" for row in population) != 717:
        raise RuntimeError("REPAIRED_ARM_POPULATION_MISMATCH")
    if any(not row["pack_fingerprint"] for row in population if row["arm"] == "E"):
        raise RuntimeError("REPAIRED_PACK_E_REFERENCE_MISSING")
    if any(row["pack_fingerprint"] for row in population if row["arm"] == "A"):
        raise RuntimeError("REPAIRED_PACK_A_CONTAMINATION")


def supersede_package(blocked: Path = BLOCKED_PACKAGE) -> Dict[str, Any]:
    blocked = blocked.resolve()
    blocked_manifest = _validate_blocked_snapshot(blocked)
    blocked_snapshot = blocked / "input_snapshot"
    old_config = read_json(blocked / "execution" / "frozen_execution_configuration.json")
    if old_config.get("stage4a_contract", {}).get("fingerprint") != CONTRACT_FP:
        raise RuntimeError("BLOCKED_STAGE4A_CONTRACT_MISMATCH")
    run_id = "9-AUTHORITATIVE-HISTORICAL-REPLAY-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = OUTPUT_ROOT / run_id
    if run_dir.exists():
        raise RuntimeError("CONFLICTING_RUN_DIRECTORY")
    for name in ("input_snapshot", "active_store", "execution", "logs", "responses", "predictions", "manifests", "failures"):
        (run_dir / name).mkdir(parents=True, exist_ok=False)
    executor = ROOT / "automation" / "run_phase9_authoritative_historical_replay_v0.py"
    builder = ROOT / "automation" / "freeze_authoritative_historical_replay_package_v0.py"
    bridge = ROOT / "apps_script" / "authoritative_provider_bridge.js"
    bindings = {
        "executor": {"relative_path": str(executor.relative_to(ROOT)), "sha256": file_sha(executor)},
        "package_builder": {"relative_path": str(builder.relative_to(ROOT)), "sha256": file_sha(builder)},
        "provider_bridge": {"relative_path": str(bridge.relative_to(ROOT)), "sha256": file_sha(bridge), "request_schema_version": BRIDGE_SCHEMA},
        "git": git_binding(),
    }
    config = dict(old_config)
    config.update({
        "run_id": run_id,
        "rollback_boundary": str(run_dir),
        "runner_fingerprint": bindings["executor"]["sha256"],
        "execution_bindings": bindings,
        "apps_script_project_binding": {
            "project_id": APPS_SCRIPT_PROJECT_ID,
            "version_number": APPS_SCRIPT_VERSION,
            "aggregate_fingerprint": APPS_SCRIPT_PROJECT_FINGERPRINT,
            "bridge_file_name": APPS_SCRIPT_BRIDGE_FILE_NAME,
            "bridge_sha256": bindings["provider_bridge"]["sha256"],
        },
    })
    if config.get("prompt_fingerprint") == config["runner_fingerprint"]:
        raise RuntimeError("RUNNER_FINGERPRINT_COLLIDES_WITH_PROMPT_FINGERPRINT")
    if config.get("schema_version") != SCHEMA:
        raise RuntimeError("PREDICTION_SCHEMA_MISMATCH")
    population = _population(run_id, blocked_snapshot, config)
    snapshot = run_dir / "input_snapshot"
    component_fingerprints: Dict[str, str] = {}
    for relative in SCIENTIFIC_SNAPSHOT_FILES:
        shutil.copyfile(blocked_snapshot / relative, snapshot / relative)
        component_fingerprints[relative] = file_sha(snapshot / relative)
    write_jsonl(snapshot / "authoritative_forecast_population.jsonl", population)
    component_fingerprints["authoritative_forecast_population.jsonl"] = file_sha(snapshot / "authoritative_forecast_population.jsonl")
    write_json(snapshot / "authoritative_provider_model_config.json", config)
    component_fingerprints["authoritative_provider_model_config.json"] = file_sha(snapshot / "authoritative_provider_model_config.json")
    write_json(snapshot / "authoritative_component_fingerprints.json", config["stage4a_contract"])
    component_fingerprints["authoritative_component_fingerprints.json"] = file_sha(snapshot / "authoritative_component_fingerprints.json")
    _assert_population(population, snapshot)
    config_fingerprint = sha(config)
    manifest = {
        "run_id": run_id,
        "record_counts": {"eligible_sessions": 239, "excluded_sessions": 10, "pack_references": 239, "forecast_identities": 1434},
        "source_blocked_package": str(blocked),
        "source_blocked_run_id": str(read_json(blocked / "execution" / "frozen_execution_configuration.json").get("run_id") or ""),
        "source_snapshot_fingerprint": blocked_manifest["snapshot_fingerprint"],
        "source_eligibility_ledger": blocked_manifest["source_eligibility_ledger"],
        "source_eligibility_ledger_fingerprint": blocked_manifest["source_eligibility_ledger_fingerprint"],
        "stage4a_contract": config["stage4a_contract"],
        "component_fingerprints": component_fingerprints,
        "configuration_fingerprint": config_fingerprint,
        "snapshot_fingerprint": sha(component_fingerprints),
        "created_ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "execution_integrity_repair": "EXECUTOR_GIT_BRIDGE_MODEL_TIMEOUT_PROJECT_BINDING_V2",
    }
    write_json(snapshot / "authoritative_replay_input_manifest.json", manifest)
    write_json(run_dir / "execution" / "frozen_execution_configuration.json", config)
    write_json(run_dir / "active_store" / "store_metadata.json", {"run_id": run_id, "snapshot_fingerprint": manifest["snapshot_fingerprint"], "configuration_fingerprint": config_fingerprint, "empty_scientific_records": True})
    dry = {"status": "PENDING_EXECUTOR_FIXTURE_VALIDATION", "provider_calls": 0, "forecasts_generated": 0, "source_blocked_package": str(blocked)}
    write_json(run_dir / "manifests" / "dry_run_validation.json", dry)
    write_json(run_dir / "manifests" / "completion_contract.json", {"terminal_identity_requirement": 1434, "accepted_prediction_requires_complete_path": True, "completion_requires_reconciliation": True, "process_exit_is_insufficient": True})
    write_json(run_dir / "manifests" / "package_manifest.json", {"run_id": run_id, "snapshot_fingerprint": manifest["snapshot_fingerprint"], "configuration_fingerprint": config_fingerprint, "source_blocked_package": str(blocked), "authoritative_replay_started": False})
    old_manifest_path = blocked / "manifests" / "package_manifest.json"
    old_manifest = read_json(old_manifest_path)
    old_manifest.update({"package_status": "SUPERSEDED_BEFORE_EXECUTION_PACKAGE_INTEGRITY_FAILURE", "superseded_by": run_id, "superseded_ts": manifest["created_ts"], "supersession_reason": "IMMUTABLE_VERSION74_PROJECT_FINGERPRINT_BINDING_CORRECTION"})
    write_json(old_manifest_path, old_manifest)
    return {"run_id": run_id, "run_dir": str(run_dir), "snapshot_fingerprint": manifest["snapshot_fingerprint"], "configuration_fingerprint": config_fingerprint, "source_blocked_package": str(blocked)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--supersede-package", default=str(BLOCKED_PACKAGE))
    args = parser.parse_args()
    print(json.dumps(supersede_package(Path(args.supersede_package)), sort_keys=True))
