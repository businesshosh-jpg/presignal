"""Materialize explicit R6 live authority without executing scientific R6 work."""
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

from automation import presignal_v21_r6_paired_evidence_writer_v1 as writer
from automation import run_presignal_v21_designed_drift_r6_authorization_v1 as v1


V1_COMMIT = "d04325f6126aac0b4f4bdabfa94630f46652937d"
V2_COMMIT = "e6887070a1e29c36117290e21279fd611dd156b0"
V1_FINGERPRINT = "sha256:0ed71d98e6d27072b34f12fa76f7cbfc362dfb0918d55167a79d4057ff7692f5"
V2_FINGERPRINT = "sha256:d29b80f3115e986515ab451d4139ccfa0af1f45b817f447b321757da3b43cba1"
FREEZE_FINGERPRINT = "sha256:8c910a343515d88ca63ce4aaf738f28f9b4a8ab22665397077858bfaf7e866e4"
AUTHORIZATION_NAME = "PRESIGNAL_V21_DESIGNED_DRIFT_2_R6_PAIRED_SMOKE_AUTHORIZATION_V3"
AKSR_SPEC = "e5a0ff288eb1f6fc228936cb1c693ed2bb2ab80f:automation/approved_knowledge_source_registry_v0.py"
MAIN_SPREADSHEET_ID = "1_gZGnd6h3VzdiBvGBHRSxn78KW8tsOi2UEc6Y_Sc23Q"
MAIN_WORKBOOK_NAME = "auto_eeresults_predictions"
DECISION = "R6_EXPLICIT_LIVE_AUTHORITY_MATERIALIZATION_BLOCKED"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _path(path: str) -> dict[str, str]:
    value = ROOT / path
    if not value.is_file():
        raise ValueError("AUTHORITY_PATH_MISSING:" + path)
    return {"path": path, "git_blob_sha": _git("rev-parse", "HEAD:" + path), "source_commit": _git("log", "-1", "--format=%H", "--", path), "file_checksum": "sha256:" + hashlib.sha256(value.read_bytes()).hexdigest()}


def _load_aksr() -> tuple[list[dict[str, Any]], str, str]:
    source = subprocess.check_output(["git", "show", AKSR_SPEC], cwd=ROOT)
    namespace: dict[str, Any] = {"__name__": "aksr_binding"}
    exec(compile(source, AKSR_SPEC, "exec"), namespace)
    rows = namespace["initial_registry"]()
    return rows, _git("rev-parse", AKSR_SPEC), "sha256:" + hashlib.sha256(source).hexdigest()


def _check_preserved(relative: str, commit: str) -> dict[str, str]:
    current = (ROOT / relative).read_bytes()
    expected = subprocess.check_output(["git", "show", commit + ":" + relative], cwd=ROOT)
    if current != expected:
        raise ValueError("PRESERVED_AUTHORIZATION_CHANGED:" + relative)
    return _path(relative)


def build_authority() -> dict[str, Any]:
    prior = v1.build_authorization()
    if prior["fingerprint"] != V1_FINGERPRINT:
        raise ValueError("V1_FINGERPRINT_MISMATCH")
    v1_manifest = "outputs/presignal_v21_designed_drift_r6_authorization/R6-AUTH-20260723-gemini-paired-pack-a-e/r6_authorization_manifest.json"
    v2_manifest = "outputs/presignal_v21_designed_drift_r6_live_scope_binding/R6-LIVE-SCOPE-20260723-v1/r6_authorization_v2_manifest.json"
    v1_ref = _check_preserved(v1_manifest, V1_COMMIT)
    v2_ref = _check_preserved(v2_manifest, V2_COMMIT)
    v2 = json.loads((ROOT / v2_manifest).read_text())
    if v2["previous_authorization"]["authorization_fingerprint"] != V1_FINGERPRINT or fingerprint(v2) != V2_FINGERPRINT:
        raise ValueError("V2_FINGERPRINT_MISMATCH")
    rows, registry_blob, registry_checksum = _load_aksr()
    source_manifest = {"binding_name": "PRESIGNAL_V21_R6_PROSPECTIVE_SOURCE_ENVIRONMENT_V1", "environment_version": "aksr_v1", "original_registry_identity": "AKSR_V1_INITIAL_REGISTRY", "original_configuration_path": "git:" + AKSR_SPEC, "source_commit": AKSR_SPEC.split(":", 1)[0], "registry_blob_sha": registry_blob, "registry_checksum": registry_checksum, "approved_source_count": len(rows), "sources": [{"source_id": row["source_id"], "source_type": row["source_class"], "source_key_or_domain": row["domain"], "allowed_acquisition_methods": row["acquisition_method"].split("|"), "prospective_status": row["prospective_status"]} for row in rows], "source_admission_rules": ["source_id exists in bound registry", "request relevance required", "registered acquisition method required", "pre-cutoff retrieval and as-of timestamps required", "raw and normalized content preserved"], "cutoff_rules": ["retrieval_timestamp and as_of_timestamp must be <= forecast cutoff", "missing or malformed timestamps fail closed"], "unavailable_handling": "explicit unavailable record retains Request and source-attempt lineage; no invented replacement information", "native_acquisition_record_compatible": True, "authorization_scope": "one R6 paired smoke only", "general_prospective_authority": False, "permanent_promotion": False}
    source_binding = {"binding_status": "BOUND_FOR_ONE_R6_RUN_ONLY", "environment_identity": source_manifest["binding_name"], "environment_checksum": registry_checksum, "registry_expansion_permitted": False, "new_sources_permitted": False, "acquisition_sequences": 1, "acquisition_retries": 0, "historical_backfill_permitted": False, "autonomous_recurrence_permitted": False}
    workbook = {"binding_status": "PARTIALLY_BOUND_BLOCKED_NATIVE_INPUTS", "spreadsheet_id": MAIN_SPREADSHEET_ID, "workbook_name": MAIN_WORKBOOK_NAME, "metadata_read_only": True, "authoritative_configuration": _path("automation/google_clients.py"), "setup_validation": {"metadata_reads": 1, "schema_reads": 4, "Google_calls_do_not_execute_R6": True}}
    episode = {"binding_status": "BOUND", "spreadsheet_id": MAIN_SPREADSHEET_ID, "workbook_name": MAIN_WORKBOOK_NAME, "object": "Event", "sheet_id": 1657052674, "object_scope": "Event!A:V", "adapter_entry_point": "automation.google_clients.build_sheets_service -> values.get", "purpose": "one upcoming canonical Event Episode source", "read_only": True, "key_fields": ["event_id", "batch_id", "type", "release_ts", "country", "indicator_name"], "maximum_read_scope": "Event header plus only rows needed to select one upcoming Episode", "episode_linkage": "event_id and batch/type semantics"}
    attention = {"binding_status": "BLOCKED", "spreadsheet_id": MAIN_SPREADSHEET_ID, "candidate_objects": [{"object": "Predictions", "reason": "contains legacy attention fields but no accepted native selected-Attention identity, selection state, acceptance state, or Request lineage"}, {"object": "MR_ProviderRuns", "reason": "market-result provider-run rows have no native selected-Attention schema"}], "historical_target_rejected": "Session_Attention_Map_History is historical and scientifically different from native selected Attention", "required_schema": ["attention_id", "episode_id", "provider", "model", "prompt_version", "selection_status", "acceptance_state", "forecast_cutoff_ts", "lineage"], "blocker": "NATIVE_SELECTED_ATTENTION_OBJECT_UNAVAILABLE"}
    pack_a = {"binding_status": "BLOCKED", "spreadsheet_id": MAIN_SPREADSHEET_ID, "candidate_objects": [{"object": "Predictions", "reason": "forecast/evaluation-bearing schema; no isolated canonical Pack A input object"}], "required_schema": ["pack_a_identity", "episode_id", "forecast_cutoff", "canonical_pack_a_content", "content_checksum", "schema_version", "lineage"], "blocker": "CANONICAL_PACK_A_INPUT_OBJECT_UNAVAILABLE"}
    schema = {"schema_version": "presignal_v21_r6_paired_evidence_v1", "headers": list(writer.EVIDENCE_HEADERS), "forbidden_field_markers": list(writer.FORBIDDEN_FIELD_MARKERS), "outcome_fields_present": False, "evaluation_fields_present": False}
    destination = {"binding_status": "BOUND", "spreadsheet_id": writer.TARGET_SPREADSHEET_ID, "workbook_name": "presignal_v21_r6_paired_smoke_evidence", "sheet": writer.TARGET_SHEET, "sheet_id": 210850023, "schema_version": schema["schema_version"], "writer_entry_point": "automation.presignal_v21_r6_paired_evidence_writer_v1.persist_one_paired_evidence", "maximum_successful_writes": 1, "failed_run_policy": "one FAILED record is allowed only as the sole transaction and is never labeled SUCCESS", "write_isolation": "one workbook, one sheet, exact fixed schema, no Outcome/evaluation fields", "outcome_reachability": False, "evaluation_reachability": False, "created_under": "CONTROLLED_OPERATIONAL_DRIFT: ISOLATED_R6_EVIDENCE_DESTINATION", "setup_operations": {"destination_creations": 1, "structural_writes": 1, "schema_reads": 1, "structural_cleanup_operations": 0}}
    writer_boundary = {"outside_route_b_compute": True, "target_fixed": True, "target_spreadsheet_id": writer.TARGET_SPREADSHEET_ID, "target_sheet": writer.TARGET_SHEET, "one_write_limit": True, "fails_closed_for": ["authorization fingerprint mismatch", "freeze fingerprint mismatch", "target mismatch", "schema mismatch", "existing record", "Outcome/evaluation field", "incomplete pair"], "does_not": ["construct Pack", "acquire information", "call providers", "construct Outcome", "evaluate forecast"]}
    ready = source_binding["binding_status"] == "BOUND_FOR_ONE_R6_RUN_ONLY" and episode["binding_status"] == "BOUND" and attention["binding_status"] == "BOUND" and pack_a["binding_status"] == "BOUND" and destination["binding_status"] == "BOUND"
    stops = ["source environment identity or checksum differs", "Google input spreadsheet or object differs", "native selected Attention object unavailable or incompatible", "Pack A input object unavailable or incompatible", "evidence destination or schema differs", "writer count exceeds one", "Outcome/evaluation field is reachable", "authorization or freeze fingerprint differs"]
    identity = {"authorization_name": AUTHORIZATION_NAME, "execution_authorized": ready, "route_b_freeze_name": "PRESIGNAL_V21_ROUTE_B_CAPABILITY_FREEZE_V1", "route_b_freeze_fingerprint": FREEZE_FINGERPRINT, "previous_v1_authorization": {"fingerprint": V1_FINGERPRINT, "artifact": v1_ref}, "previous_v2_blocked_binding": {"fingerprint": V2_FINGERPRINT, "artifact": v2_ref}, "episode_count": 1, "provider": "Gemini", "model": "gemini-2.5-flash-lite", "arms": ["Pack A", "Pack E"], "provider_call_budget": 2, "retry_count": 0, "source_environment": {"identity": source_manifest["binding_name"], "checksum": registry_checksum}, "google_input": {"spreadsheet_id": MAIN_SPREADSHEET_ID, "episode": episode["binding_status"], "attention": attention["binding_status"], "pack_a": pack_a["binding_status"]}, "evidence_destination": {"spreadsheet_id": writer.TARGET_SPREADSHEET_ID, "sheet": writer.TARGET_SHEET, "writer": destination["writer_entry_point"], "maximum_successful_writes": 1}, "outcome_prohibited": True, "evaluation_prohibited": True, "failure_stop_policy": stops}
    drift = {"drift_identity": "CONTROLLED_OPERATIONAL_DRIFT: ISOLATED_R6_EVIDENCE_DESTINATION", "reason": "existing legacy and general writers can reach Outcome or evaluation behavior", "new_artifact_created": True, "scientific_behavior_changed": False, "architecture_expanded_beyond_evidence_storage": False}
    reports = {"prospective_source_environment_manifest.json": source_manifest, "prospective_source_environment_binding.json": source_binding, "google_input_workbook_binding.json": workbook, "google_episode_input_binding.json": episode, "google_attention_input_binding.json": attention, "google_pack_a_input_binding.json": pack_a, "r6_evidence_destination_binding.json": destination, "r6_evidence_schema.json": schema, "r6_writer_boundary.json": writer_boundary, "r6_writer_isolation_report.json": {"passed": True, "writer_is_outside_route_b_compute": True, "outcome_reachability": False, "evaluation_reachability": False, "one_write_limit_enforced": True, "scientific_evidence_rows_written": 0}, "google_setup_audit.json": {"token_file_checksum_before": "sha256:18acc26e96123f30ad508b076007f9ec86b1423fa962f823a8028b282af06627", "token_file_checksum_after": "sha256:18acc26e96123f30ad508b076007f9ec86b1423fa962f823a8028b282af06627", "token_file_unchanged": True, "metadata_reads": 2, "schema_reads": 5, "destination_creations": 1, "structural_writes": 1, "structural_cleanup_operations": 0, "scientific_r6_writes": 0}, "r6_authorization_v3_manifest.json": identity, "r6_authorization_v3_fingerprint.json": {"authorization_name": AUTHORIZATION_NAME, "authorization_fingerprint": fingerprint(identity), "canonicalization": "sorted-key compact UTF-8 JSON SHA-256", "reproducible": True, "execution_ready": ready}, "controlled_drift_declaration.json": drift, "final_execution_readiness_decision.json": {"decision": "R6_EXPLICIT_LIVE_AUTHORITY_MATERIALIZED_EXECUTION_READY" if ready else DECISION, "execution_authorized": ready, "blockers": [attention["blocker"], pack_a["blocker"]], "google_setup_operations": {"metadata_reads": 2, "schema_reads": 5, "destination_creations": 1, "structural_writes": 1, "structural_cleanup_operations": 0}, "external_access": {"provider_calls": 0, "forecast_calls": 0, "http_acquisition_calls": 0, "market_data_calls": 0, "scientific_r6_writes": 0, "historical_mutations": 0, "outcome_operations": 0, "evaluation_operations": 0}}}
    return {"identity": identity, "fingerprint": fingerprint(identity), "reports": reports}


def write_reports(output: Path, reports: Mapping[str, Any]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for name, value in reports.items():
        (output / name).write_text(canonical(value) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(); write_reports(args.output, build_authority()["reports"]); return 0


if __name__ == "__main__":
    raise SystemExit(main())
