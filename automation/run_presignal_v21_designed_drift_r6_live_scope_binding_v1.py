"""Bind or fail-close the repository-evidenced live scopes for the R6 smoke.

The module only inventories committed local evidence.  In particular, it never
loads Google credentials, opens a workbook, dispatches a provider, or acquires
information.  A blocked binding is deliberately a first-class result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import run_presignal_v21_designed_drift_r6_authorization_v1 as v1


V1_NAME = "PRESIGNAL_V21_DESIGNED_DRIFT_2_R6_PAIRED_SMOKE_AUTHORIZATION_V1"
V1_FINGERPRINT = "sha256:0ed71d98e6d27072b34f12fa76f7cbfc362dfb0918d55167a79d4057ff7692f5"
V1_COMMIT = "d04325f6126aac0b4f4bdabfa94630f46652937d"
V2_BLOCKED_NAME = "PRESIGNAL_V21_DESIGNED_DRIFT_2_R6_PAIRED_SMOKE_AUTHORIZATION_V2_BLOCKED_SCOPE_BINDING"
FREEZE_FINGERPRINT = "sha256:8c910a343515d88ca63ce4aaf738f28f9b4a8ab22665397077858bfaf7e866e4"
DECISION = "R6_LIVE_SCOPE_BINDING_REQUIRES_EXPLICIT_USER_AUTHORIZATION"
V1_MANIFEST = "outputs/presignal_v21_designed_drift_r6_authorization/R6-AUTH-20260723-gemini-paired-pack-a-e/r6_authorization_manifest.json"
V1_FINGERPRINT_PATH = "outputs/presignal_v21_designed_drift_r6_authorization/R6-AUTH-20260723-gemini-paired-pack-a-e/r6_authorization_fingerprint.json"
HISTORICAL_REGISTRY = "e5a0ff288eb1f6fc228936cb1c693ed2bb2ab80f:automation/approved_knowledge_source_registry_v0.py"
EXTERNAL_ACCESS = {key: 0 for key in ("provider_calls", "google_calls", "apps_script_calls", "http_calls", "market_data_calls", "production_writes", "historical_mutations", "forecast_calls", "outcome_operations", "evaluation_operations")}


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _file_checksum(relative: str) -> str:
    return "sha256:" + hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


def _git_object_checksum(spec: str) -> tuple[str, str]:
    raw = subprocess.check_output(["git", "show", spec], cwd=ROOT)
    return _git("rev-parse", spec), "sha256:" + hashlib.sha256(raw).hexdigest()


def _path_reference(relative: str, *, role: str, classification: str) -> dict[str, str]:
    path = ROOT / relative
    if not path.is_file():
        raise ValueError("BINDING_EVIDENCE_PATH_MISSING:" + relative)
    return {"path": relative, "git_blob_sha": _git("rev-parse", "HEAD:" + relative), "file_checksum": _file_checksum(relative), "source_commit": _git("log", "-1", "--format=%H", "--", relative), "role": role, "classification": classification}


def _v1_binding() -> dict[str, Any]:
    prior = v1.build_authorization()
    stored_manifest = json.loads((ROOT / V1_MANIFEST).read_text(encoding="utf-8"))
    stored_fingerprint = json.loads((ROOT / V1_FINGERPRINT_PATH).read_text(encoding="utf-8"))
    if prior["fingerprint"] != V1_FINGERPRINT or stored_fingerprint["authorization_fingerprint"] != V1_FINGERPRINT:
        raise ValueError("V1_AUTHORIZATION_FINGERPRINT_MISMATCH")
    if stored_manifest != prior["identity"]:
        raise ValueError("V1_AUTHORIZATION_EVIDENCE_CHANGED")
    for relative in (V1_MANIFEST, V1_FINGERPRINT_PATH):
        if subprocess.check_output(["git", "show", V1_COMMIT + ":" + relative], cwd=ROOT) != (ROOT / relative).read_bytes():
            raise ValueError("V1_AUTHORIZATION_EVIDENCE_CHANGED:" + relative)
    return {"authorization_name": V1_NAME, "authorization_fingerprint": V1_FINGERPRINT, "source_commit": V1_COMMIT, "manifest": _path_reference(V1_MANIFEST, role="prior blocked authorization", classification="CURRENT_R6_AUTHORIZATION"), "fingerprint_artifact": _path_reference(V1_FINGERPRINT_PATH, role="prior authorization identity", classification="CURRENT_R6_AUTHORIZATION")}


def candidate_inventory() -> list[dict[str, Any]]:
    registry_blob, registry_checksum = _git_object_checksum(HISTORICAL_REGISTRY)
    candidates = [
        {"candidate_type": "PROSPECTIVE_SOURCE_ENVIRONMENT", "identity": "MOVE4C_APPROVED_SOURCES_V1", "artifact": _path_reference("outputs/presignal_v21_designed_drift_move4c/MOVE4C-20260723-native-contract-validation/native_fixture_inputs.json", role="native validation fixture", classification="TEST_ONLY_FIXTURE"), "authority_status": "TEST_ONLY", "approved_source_count": 4, "native_acquisition_schema_compatible": True, "cutoff_compatible": True, "source_admission_compatible": True, "scope_compatible": False, "current_or_legacy": "TEST_ONLY", "selected": False, "rejection_reason": "Move 4C explicitly classifies this as NATIVE_CONTRACT_VALIDATION_FIXTURE, not live R6 authority."},
        {"candidate_type": "PROSPECTIVE_SOURCE_ENVIRONMENT", "identity": "AKSR_V1_INITIAL_REGISTRY", "artifact": {"path": "git:" + HISTORICAL_REGISTRY, "git_blob_sha": registry_blob, "file_checksum": registry_checksum, "source_commit": HISTORICAL_REGISTRY.split(":", 1)[0], "role": "historical approved-source registry capability", "classification": "HISTORICAL_AUTHORITY_ONLY"}, "authority_status": "HISTORICAL_CAPABILITY_ONLY", "approved_source_count": 16, "native_acquisition_schema_compatible": False, "cutoff_compatible": "UNPROVEN_FOR_NATIVE_R6", "source_admission_compatible": "CALLER_SUPPLIED_ONLY", "scope_compatible": False, "current_or_legacy": "HISTORICAL", "selected": False, "rejection_reason": "The frozen dependency manifest preserves registry provenance but requires a caller-supplied prospective environment; no governing artifact binds this historical registry to R6."},
        {"candidate_type": "PROSPECTIVE_SOURCE_ENVIRONMENT", "identity": "ROUTE_B_CALLER_SUPPLIED_ENVIRONMENT", "artifact": _path_reference("contracts/presignal_v21_event_path/pack_capability_dependency_manifest.json", role="Route B dependency closure", classification="CURRENT_CONTRACT"), "authority_status": "UNRESOLVED", "approved_source_count": 0, "native_acquisition_schema_compatible": True, "cutoff_compatible": True, "source_admission_compatible": True, "scope_compatible": False, "current_or_legacy": "CURRENT", "selected": False, "rejection_reason": "It defines the required interface but intentionally supplies neither an environment identity nor approved sources."},
        {"candidate_type": "GOOGLE_READ_TARGET", "identity": "SESSION_ATTENTION_MAP_HISTORY:1jxcZotbzJKcAzrK0VhxetYX6hp5DPXCCIA0J6B6RUy0", "artifact": _path_reference("automation/export_authoritative_v2_attention_map_v1.py", role="historical Attention exporter", classification="HISTORICAL_AUTHORITY_ONLY"), "authority_status": "HISTORICAL_ONLY", "schema_compatible": False, "scope_compatible": False, "isolation_status": "READ_ONLY_HISTORICAL_EXPORT", "current_or_legacy": "HISTORICAL", "selected": False, "rejection_reason": "Exports Session_Attention_Map_History with historical attention labels, not a native accepted selected-Attention object for the R6 Episode."},
        {"candidate_type": "GOOGLE_READ_TARGET", "identity": "MAIN_SPREADSHEET_FALLBACK:1_gZGnd6h3VzdiBvGBHRSxn78KW8tsOi2UEc6Y_Sc23Q", "artifact": _path_reference("apps_script/config.js", role="Apps Script fallback configuration", classification="UNRESOLVED_RUNTIME_CONFIGURATION"), "authority_status": "UNRESOLVED", "schema_compatible": "UNPROVEN", "scope_compatible": False, "isolation_status": "SCRIPT_PROPERTIES_CAN_OVERRIDE", "current_or_legacy": "RUNTIME_FALLBACK", "selected": False, "rejection_reason": "A general Config fallback is not an explicit bounded R6 Episode/Attention/Pack-A read binding and is mutable through prohibited Script Properties."},
        {"candidate_type": "GOOGLE_READ_TARGET", "identity": "LEGACY_BENCHMARK:1W6ZL4kK3Qs_76sgQPw83KS9TQVk2LHHXJ_O2GSahe9s", "artifact": _path_reference("automation/presignal_v21_autonomous_ai_benchmark_v1.py", role="historical autonomous-AI benchmark", classification="LEGACY_BENCHMARK_CONFIGURATION"), "authority_status": "LEGACY_BENCHMARK_ONLY", "schema_compatible": False, "scope_compatible": False, "isolation_status": "OUTCOME_COMPARISON_REACHABLE", "current_or_legacy": "LEGACY", "selected": False, "rejection_reason": "Historical benchmark inputs and outcome comparison are not the current prospective R6 canonical input scope."},
        {"candidate_type": "GOOGLE_WRITE_TARGET", "identity": "LEGACY_BENCHMARK:1W6ZL4kK3Qs_76sgQPw83KS9TQVk2LHHXJ_O2GSahe9s", "artifact": _path_reference("automation/presignal_v21_autonomous_ai_benchmark_v1.py", role="legacy benchmark writer", classification="LEGACY_BENCHMARK_CONFIGURATION"), "authority_status": "LEGACY_BENCHMARK_ONLY", "schema_compatible": False, "scope_compatible": False, "isolation_status": "NOT_R6_WRITE_SAFE", "current_or_legacy": "LEGACY", "selected": False, "rejection_reason": "LEGACY_BENCHMARK_TARGET_NOT_R6_WRITE_SAFE: its writer reaches Outcome_Comparison and evaluation-bearing comparison rows; one isolated paired-R6 transaction cannot be enforced."},
        {"candidate_type": "GOOGLE_WRITE_TARGET", "identity": "MAIN_SPREADSHEET_FALLBACK:1_gZGnd6h3VzdiBvGBHRSxn78KW8tsOi2UEc6Y_Sc23Q", "artifact": _path_reference("automation/build_presignal_v21_workbooks.py", role="general v2.1 workbook builder", classification="GENERAL_WORKBOOK_CONFIGURATION"), "authority_status": "UNRESOLVED", "schema_compatible": False, "scope_compatible": False, "isolation_status": "OUTCOME_AND_EVALUATION_SHEETS_DECLARED", "current_or_legacy": "GENERAL_RUNTIME", "selected": False, "rejection_reason": "General workbook configuration declares Outcome and Evaluation sheets and no isolated R6 paired-evidence writer or transaction boundary."},
        {"candidate_type": "R6_EVIDENCE_DESTINATION", "identity": "LOCAL_R6_ADMISSION_ROOT", "artifact": _path_reference("automation/run_presignal_v21_designed_drift_r6_admission_v1.py", role="local R6 admission snapshot utility", classification="LOCAL_DIAGNOSTIC_ONLY"), "authority_status": "LOCAL_ONLY", "schema_compatible": False, "scope_compatible": False, "isolation_status": "NO_GOOGLE_WRITER", "current_or_legacy": "CURRENT_LOCAL_DIAGNOSTIC", "selected": False, "rejection_reason": "The utility protects a local admission snapshot; it is neither a Google target nor an implemented paired forecast evidence writer."},
    ]
    return candidates


def _binding(category: str, decision: str, candidates: list[dict[str, Any]], *, required_shape: str) -> dict[str, Any]:
    rows = [row for row in candidates if row["candidate_type"] == category]
    return {"binding_status": "REQUIRES_EXPLICIT_USER_AUTHORIZATION", "decision": decision, "selected_identity": None, "candidate_identities": [row["identity"] for row in rows], "selected_artifact": None, "required_shape": required_shape, "no_fallback_target_permitted": True, "candidates": rows}


def build_binding() -> dict[str, Any]:
    prior = _v1_binding()
    candidates = candidate_inventory()
    source = _binding("PROSPECTIVE_SOURCE_ENVIRONMENT", "PROSPECTIVE_SOURCE_ENVIRONMENT_REQUIRES_EXPLICIT_USER_AUTHORIZATION", candidates, required_shape="one immutable prospective environment with approved source identities, types, keys/domains, allowed methods, cutoff and unavailable rules, commit, and checksum")
    read = _binding("GOOGLE_READ_TARGET", "R6_GOOGLE_READ_TARGET_REQUIRES_EXPLICIT_USER_AUTHORIZATION", candidates, required_shape="one existing bounded R6 input workbook/object for Episode, accepted Attention, Pack A components, or execution configuration")
    write = _binding("GOOGLE_WRITE_TARGET", "R6_GOOGLE_WRITE_TARGET_REQUIRES_EXPLICIT_USER_AUTHORIZATION", candidates, required_shape="one existing isolated paired-R6 evidence object with a caller-controlled writer, no Outcome/evaluation reachability, and a one-transaction limit")
    evidence = _binding("R6_EVIDENCE_DESTINATION", "R6_EVIDENCE_DESTINATION_REQUIRES_EXPLICIT_USER_AUTHORIZATION", candidates, required_shape="an existing isolated workbook or table containing paired evidence only, failed-run status support, no Outcome/evaluation automation, and one caller-controlled transaction")
    stops = ["approved-source environment identity differs", "Google read target differs", "Google write target differs", "evidence destination differs", "target checksum or configuration differs", "writer scope exceeds one transaction", "legacy Outcome behavior is reachable", "legacy evaluation behavior is reachable", "no fallback target is permitted", "no automatic workbook creation is permitted"]
    identity = {"authorization_name": V2_BLOCKED_NAME, "schema_version": "1", "execution_authorized": False, "previous_authorization": prior, "route_b_freeze_fingerprint": FREEZE_FINGERPRINT, "episode_scope": {"count": 1, "prospective_only": True}, "forecast_scope": {"provider": "Gemini", "model": "gemini-2.5-flash-lite", "arms": ["Pack A", "Pack E"], "call_budget": 2, "retry_count": 0}, "source_environment_binding": source, "google_read_binding": read, "google_write_binding": write, "evidence_destination_binding": evidence, "outcome_prohibited": True, "evaluation_prohibited": True, "failure_stop_conditions": stops}
    reports = {
        "live_scope_candidate_inventory.json": {"inventory_version": "1", "candidate_count": len(candidates), "candidates": candidates},
        "live_scope_compatibility_matrix.json": [{key: row.get(key) for key in ("candidate_type", "identity", "authority_status", "schema_compatible", "scope_compatible", "isolation_status", "current_or_legacy", "selected", "rejection_reason")} for row in candidates],
        "prospective_source_environment_binding.json": source,
        "google_read_target_binding.json": read,
        "google_write_target_binding.json": write,
        "r6_evidence_destination_binding.json": evidence,
        "r6_authorization_v2_manifest.json": identity,
        "r6_authorization_v2_fingerprint.json": {"authorization_name": V2_BLOCKED_NAME, "authorization_fingerprint": fingerprint(identity), "canonicalization": "sorted-key compact UTF-8 JSON SHA-256", "execution_ready": False, "reproducible": True},
        "live_scope_failure_stop_policy.json": {"policy": "FAIL_CLOSED", "conditions": stops, "external_execution_permitted": False},
        "final_live_scope_binding_decision.json": {"decision": DECISION, "source_environment_decision": source["decision"], "google_read_decision": read["decision"], "google_write_decision": write["decision"], "evidence_destination_decision": evidence["decision"], "execution_authorized": False, "external_access": EXTERNAL_ACCESS},
    }
    return {"identity": identity, "fingerprint": fingerprint(identity), "reports": reports}


def write_reports(output: Path, reports: Mapping[str, Any]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for name, value in reports.items():
        (output / name).write_text(canonical(value) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = build_binding()
    write_reports(args.output, value["reports"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
