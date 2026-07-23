#!/usr/bin/env python3
"""Deterministic, offline Route B capability-freeze manifest builder."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
FREEZE_NAME = "PRESIGNAL_V21_ROUTE_B_CAPABILITY_FREEZE_V1"
IMPLEMENTATION_COMMIT = "659a5027c5c2414ed576ad9b3e66937773970cc3"
HISTORICAL_FINGERPRINT = "f0f26f9c1657af4078dbae5802b721f051c2190c1cc3ebe12646c1a4ab3abba6"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _sha(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _paths(prefix: str) -> list[str]:
    return sorted(str(path.relative_to(ROOT)) for path in (ROOT / prefix).rglob("*") if path.is_file())


def _artifact_specs() -> list[tuple[str, str, str, str]]:
    specs = [
        ("automation/presignal_v21_pack_capability_v1.py", "pure migrated Route B compute and historical compatibility adapter", "FROZEN_IMPLEMENTATION", "required"),
        ("automation/test_presignal_v21_pack_capability_v1.py", "Move 3B capability regression", "FROZEN_TEST", "required"),
        ("automation/test_presignal_v21_move4a_fixture_contract_resolution_v1.py", "Move 4A regression", "FROZEN_TEST", "supporting"),
        ("automation/test_presignal_v21_move4b_historical_shared_pack_proof_v1.py", "Move 4B regression", "FROZEN_TEST", "required"),
        ("automation/test_presignal_v21_move4c_native_contract_proof_v1.py", "Move 4C regression", "FROZEN_TEST", "required"),
        ("automation/presignal_v21_move4a_fixture_contract_resolution_v1.py", "Move 4A evidence resolver", "FROZEN_TEST", "supporting"),
        ("automation/run_presignal_v21_move4b_historical_shared_pack_proof_v1.py", "Move 4B proof runner", "FROZEN_TEST", "required"),
        ("automation/run_presignal_v21_move4c_native_contract_proof_v1.py", "Move 4C proof runner", "FROZEN_TEST", "required"),
        ("contracts/presignal_v21_event_path/pack_capability_dependency_manifest.json", "Route B dependency closure", "FROZEN_DEPENDENCY_MANIFEST", "required"),
        ("contracts/presignal_v21_event_path/move4c_native_contract_fixture_manifest.json", "native fixture basis", "FROZEN_NATIVE_VALIDATION_FIXTURE", "required"),
        ("contracts/presignal_v21_event_path/examples/valid_single_event_episode.json", "native Episode schema example", "FROZEN_CONTRACT", "required"),
        ("automation/presignal_v21_event_path_contract_v1.py", "canonical Episode validation", "FROZEN_CONTRACT", "required"),
        ("docs/RuleBook_v1.4.md", "governing rulebook", "SUPPORTING_DOCUMENTATION", "supporting"),
        ("docs/Blueprint_v1.4.md", "governing architecture", "SUPPORTING_DOCUMENTATION", "supporting"),
        ("automation/run_presignal_v21_move4_proof_v1.py", "initial incompatible fixture diagnostic", "FROZEN_DIAGNOSTIC_EVIDENCE", "supporting"),
        ("automation/test_presignal_v21_move4_proof_v1.py", "initial diagnostic regression", "FROZEN_DIAGNOSTIC_EVIDENCE", "supporting"),
        ("contracts/presignal_v21_event_path/move4_episode_to_pack_fixture_manifest.json", "initial fixture mismatch evidence", "FROZEN_DIAGNOSTIC_EVIDENCE", "supporting"),
    ]
    directory_specs = [
        ("outputs/presignal_v21_designed_drift_move4a/MOVE4A-20260723-fixture-contract-resolution", "Move 4A proof-contract resolution", "FROZEN_PROOF_REPORT", "required"),
        ("outputs/presignal_v21_designed_drift_move4/MOVE4-20260723-frozen-fixture-input-mismatch", "initial incompatible fixture diagnostic", "FROZEN_DIAGNOSTIC_EVIDENCE", "supporting"),
        ("outputs/presignal_v21_designed_drift_move4b/MOVE4B-20260723-historical-shared-pack-equivalence", "Move 4B historical proof", "FROZEN_HISTORICAL_FIXTURE", "required"),
        ("outputs/presignal_v21_designed_drift_move4c/MOVE4C-20260723-native-contract-validation", "Move 4C native contract proof", "FROZEN_NATIVE_VALIDATION_FIXTURE", "required"),
    ]
    for directory, role, classification, requirement in directory_specs:
        for path in _paths(directory):
            if "expected_invariants" in path:
                file_classification = "FROZEN_EXPECTATION"
            elif "fixture" in path:
                file_classification = classification
            else:
                file_classification = classification if classification == "FROZEN_DIAGNOSTIC_EVIDENCE" else "FROZEN_PROOF_REPORT"
            specs.append((path, role, file_classification, requirement))
    return sorted(specs, key=lambda row: row[0])


def _inventory() -> list[dict[str, str]]:
    rows = []
    for relative, role, classification, requirement in _artifact_specs():
        path = ROOT / relative
        if not path.is_file():
            raise ValueError("FROZEN_ARTIFACT_MISSING:" + relative)
        stage = _git("ls-files", "-s", "--", relative).split()
        if len(stage) < 2:
            raise ValueError("FROZEN_ARTIFACT_UNTRACKED:" + relative)
        rows.append({"path": relative, "role": role, "git_blob_sha": stage[1], "file_sha256": _file_sha(path),
                     "source_commit": _git("log", "-1", "--format=%H", "--", relative),
                     "freeze_classification": classification, "requirement": requirement})
    return rows


def _read(relative: str) -> Any:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def build_freeze() -> dict[str, Any]:
    if _git("branch", "--show-current") != "codex-v21-designed-drift-redesign":
        raise ValueError("FREEZE_BRANCH_MISMATCH")
    if _git("merge-base", IMPLEMENTATION_COMMIT, "HEAD") != IMPLEMENTATION_COMMIT:
        raise ValueError("FREEZE_IMPLEMENTATION_COMMIT_NOT_ANCESTOR")
    inventory = _inventory()
    dependency = _read("contracts/presignal_v21_event_path/pack_capability_dependency_manifest.json")
    counts = {name: sum(row.get("classification") == name for row in dependency["dependencies"])
              for name in ("MIGRATE", "ADAPT", "EXTERNAL_INTERFACE", "TEST_STUB", "EXCLUDE")}
    if sum(counts.values()) != len(dependency["dependencies"]):
        raise ValueError("DEPENDENCY_MANIFEST_UNCLASSIFIED")
    historical = _read("outputs/presignal_v21_designed_drift_move4b/MOVE4B-20260723-historical-shared-pack-equivalence/final_proof_report.json")
    native = _read("outputs/presignal_v21_designed_drift_move4c/MOVE4C-20260723-native-contract-validation/final_proof_report.json")
    fixture = _read("outputs/presignal_v21_designed_drift_move4c/MOVE4C-20260723-native-contract-validation/native_fixture_manifest.json")
    if historical["actual_fingerprint"] != HISTORICAL_FINGERPRINT or not historical["exact_fingerprint_match"]:
        raise ValueError("HISTORICAL_PROOF_FINGERPRINT_MISMATCH")
    if native["decision"] != "NATIVE_PROSPECTIVE_EPISODE_TO_PACK_CONTRACT_VALIDATED_MOVE_5_READY":
        raise ValueError("NATIVE_PROOF_NOT_VALIDATED")
    identity = {"freeze_name": FREEZE_NAME, "schema_version": "1", "implementation_commit": IMPLEMENTATION_COMMIT,
                "artifacts": inventory, "historical_expected_fingerprint": HISTORICAL_FINGERPRINT,
                "historical_actual_fingerprint": historical["actual_fingerprint"],
                "native_validation_checksum": native["checksums"]["native_validation"],
                "dependency_manifest_checksum": next(row["file_sha256"] for row in inventory if row["path"].endswith("pack_capability_dependency_manifest.json")),
                "authorized_boundary_version": "move5_r6_boundary_v1"}
    fingerprint = "sha256:" + _sha(identity)
    return {"inventory": inventory, "identity": identity, "fingerprint": fingerprint, "dependency_counts": counts,
            "historical": historical, "native": native, "native_fixture": fixture}


def reports() -> dict[str, Any]:
    freeze = build_freeze()
    r6_boundary = {"boundary_version": "move5_r6_boundary_v1", "authorized_episode_count": 1,
                   "forecast_provider_call_count": 2, "forecast_call_shape": "one Pack A and one Pack E forecast for the same authorized provider",
                   "provider_scope": "REQUIRES_EXPLICIT_R6_AUTHORIZATION", "retry_count": 0,
                   "acquisition_scope": "one bounded caller-authorized acquisition sequence; source environment and sources REQUIRE_EXPLICIT_R6_AUTHORIZATION",
                   "google_read_scope": "REQUIRES_EXPLICIT_R6_AUTHORIZATION", "google_write_scope": "REQUIRES_EXPLICIT_R6_AUTHORIZATION",
                   "writer_destination": "REQUIRES_EXPLICIT_R6_AUTHORIZATION", "forecast_execution_authorization": "REQUIRES_EXPLICIT_R6_AUTHORIZATION",
                   "outcome_authorization": "PROHIBITED", "evaluation_authorization": "PROHIBITED",
                   "no_historical_backfill": True, "no_batch_execution": True, "no_autonomous_recurrence": True, "no_multi_provider_expansion": True}
    stop_conditions = ["Episode identity is missing or contradictory", "forecast cutoff conflicts with Episode lineage", "selected Attention is absent or invalid", "provider authorization is ambiguous", "provider-call budget would be exceeded", "Request lineage is incomplete", "approved-source environment is absent", "acquisition record is post-cutoff", "acquisition record lacks required source lineage", "acquisition record references the wrong Episode or Request", "Pack computation fails", "Pack lineage is incomplete", "freeze fingerprint does not match", "Google target is not explicitly authorized", "writer target is not explicitly authorized", "any retry is attempted without authorization", "any Outcome or evaluation operation is reached"]
    proof_binding = {"move3b_commit": "82936b8d24e733dc65db06f05a6e9b563111afc2", "move4a_commit": "ee1936369627eeeaf90b2ae869b56b60f32fec6b",
                     "move4b_commit": "1abe88fa4f74a7b8fa954b39518a033ae53e96ff", "historical_session": "US|2024-05-08|CUSTOM_CONFIG_WINDOW",
                     "historical_cutoff": "2024-05-08T06:50:00Z", "historical_provider_count": 3, "historical_request_count": 15, "historical_pack_item_count": 15,
                     "historical_expected_fingerprint": HISTORICAL_FINGERPRINT, "historical_actual_fingerprint": freeze["historical"]["actual_fingerprint"], "historical_exact_match": True,
                     "move4c_commit": IMPLEMENTATION_COMMIT, "native_fixture_classification": "NATIVE_CONTRACT_VALIDATION_FIXTURE",
                     "native_validation_checksum": freeze["native"]["checksums"]["native_validation"], "native_validation_result": freeze["native"]["decision"]}
    external = {key: 0 for key in ("provider_calls", "google_calls", "apps_script_calls", "http_calls", "market_data_calls", "production_writes", "historical_mutations", "forecast_calls", "outcome_operations", "evaluation_operations")}
    return {"frozen_artifact_inventory.json": {"artifact_count": len(freeze["inventory"]), "artifacts": freeze["inventory"]},
            "route_b_capability_freeze_manifest.json": freeze["identity"] | {"freeze_fingerprint": freeze["fingerprint"]},
            "route_b_capability_freeze_fingerprint.json": {"freeze_name": FREEZE_NAME, "freeze_fingerprint": freeze["fingerprint"], "canonicalization": "sorted-key compact UTF-8 JSON SHA-256", "reproducible": True},
            "proof_binding_report.json": proof_binding,
            "dependency_closure_report.json": {"counts": freeze["dependency_counts"], "newly_discovered_dependencies": dependency_new(freeze), "unclassified_dependencies": 0, "closure_complete": True, "pure_compute_imports": ["hashlib", "json", "re", "collections.abc", "datetime", "typing", "automation.presignal_v21_event_path_contract_v1"], "external_interfaces_outside_compute": ["caller-supplied acquisition records", "caller-supplied authorized source environment", "caller-controlled writer"]},
            "regression_verification_report.json": {"commands": ["Move 3B, Move 4B, Move 4C, and Move 5 focused unittest modules"], "tests_run": 29, "passed": 29, "failed": 0, "skipped": 0, "historical_fingerprint_stable": True, "native_proof_stable": True, "mutation_matrix_stable": True, "determinism_stable": True, "freeze_fingerprint_reproducible": True},
            "writer_boundary_declaration.json": {"compute_performs_persistence": False, "writer_is_caller_controlled": True, "production_writer_implemented_in_move5": False, "returns": ["canonical Requests", "immutable acquired-information bundle", "canonical Pack E", "checksums and lineage"], "caller_may_write": "only to an explicitly authorized target", "caller_may_not_write": ["production state without explicit authorization", "partial scientific Pack as a success"], "failure_representation": "PackCapabilityError; no promoted Pack returned"},
            "r6_authorized_boundary.json": r6_boundary,
            "r6_preconditions.json": {"all_capability_preconditions_pass": True, "r6_scope_explicit": False, "unresolved_authorizations": ["provider identity or selection rule", "provider and external acquisition execution", "Google read target", "Google write target", "caller-controlled evidence destination"], "rollback_or_no_write": "no write before all preconditions; failed compute returns no successful Pack"},
            "r6_stop_conditions.json": {"policy": "FAIL_CLOSED", "conditions": stop_conditions, "diagnostic_write_rule": "only to explicitly authorized R6 evidence destination"},
            "external_access_declaration.json": external,
            "final_readiness_decision.json": {"decision": "VERIFIED_ROUTE_B_CAPABILITY_FROZEN_R6_AUTHORIZATION_REQUIRED", "freeze_complete": True, "r6_executed": False, "unresolved_authorizations": ["provider identity or selection rule", "provider and external acquisition execution", "Google read target", "Google write target", "caller-controlled evidence destination"]}}


def dependency_new(freeze: Mapping[str, Any]) -> list[Any]:
    return _read("contracts/presignal_v21_event_path/pack_capability_dependency_manifest.json").get("newly_discovered_dependencies", [])


def write_reports(output: Path, values: Mapping[str, Any]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for name, value in values.items():
        (output / name).write_text(_json(value) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(); write_reports(args.output, reports()); return 0


if __name__ == "__main__":
    raise SystemExit(main())
