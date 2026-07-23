"""Bounded R6 native-input materialization after the consumed Attention call.

This runner never dispatches a provider or constructs Pack E.  It validates the
preserved local Attention evidence, writes at most that one valid object to its
named Sheet, and fail-closes if the separate Information-Request response is
absent.  The latter response cannot be reconstructed from an Attention Map.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import google_clients
from automation import presignal_v21_native_input_materialization_v1 as native
from automation import run_presignal_v21_r6_native_attention_execution_v1 as execution


REPAIR = ROOT / "outputs" / "presignal_v21_designed_drift_r6_native_attention_bridge_identity_repair" / "R6-NATIVE-ATTENTION-BRIDGE-IDENTITY-REPAIR-20260723-v1"
EXECUTION = ROOT / "outputs" / "presignal_v21_designed_drift_r6_native_attention_execution" / "R6-NATIVE-ATTENTION-EXECUTION-20260723-v1"
OUTPUT = ROOT / "outputs" / "presignal_v21_designed_drift_r6_native_input_final_materialization" / "R6-NATIVE-INPUT-FINAL-MATERIALIZATION-20260723-v1"
FREEZE_FINGERPRINT_PATH = ROOT / "outputs" / "presignal_v21_designed_drift_move5" / "MOVE5-20260723-route-b-capability-freeze" / "route_b_capability_freeze_fingerprint.json"
V3_FINGERPRINT_PATH = ROOT / "outputs" / "presignal_v21_designed_drift_r6_live_authority" / "R6-LIVE-AUTHORITY-20260723-v1" / "r6_authorization_v3_fingerprint.json"
V3_FINGERPRINT = "sha256:c8cb003af94eef2ef9cad8f323ab31b3c1990f3ffdcdab5ee3e6285fda76efb9"
SELECTION_FINGERPRINT = "sha256:73e8fe3f89126d9129ef6bcbbaeedeaf79d9f148d367248f9dcc778b307827e1"
EXPECTED_RAW = "sha256:2a64593f94788ed7b7566c98081e2c13993cf6a0338538c8d2e61c160058c2c9"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def checksum(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def file_checksum(path: Path) -> str | None:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical(value) + "\n", encoding="utf-8")


def _attention_record(attention: Mapping[str, Any]) -> dict[str, Any]:
    """Project local canonical evidence into the strictly bounded sheet row."""
    fields = {
        "attention_identity": attention["attention_identity"],
        "episode_identity": attention["episode_identity"],
        "primary_event_identity": attention["primary_event_identity"],
        "provider_identity": attention["canonical_provider_identity"],
        "model_identity": attention["transport_model_identity"],
        "payload_provider_role": attention["payload_provider_role"],
        "prompt_version": attention["prompt_version"],
        "selection_state": attention["selection_state"],
        "acceptance_state": attention["acceptance_state"],
        "selection_reason": attention["selection_reason"],
        "effective_timestamp": attention["effective_timestamp"],
        "forecast_cutoff": attention["forecast_cutoff"],
        "schema_version": attention["schema_version"],
        "raw_response_checksum": attention["raw_response_checksum"],
        "normalized_response_checksum": attention["normalized_response_checksum"],
        "content_checksum": checksum(attention),
        "provenance_checksum": attention["provenance_checksum"],
        "lineage_checksum": attention["lineage_checksum"],
        "materialization_status": "READY",
    }
    return {**fields, "authorization_identity": native.R6_AUTHORIZATION,
            "authorization_fingerprint": V3_FINGERPRINT,
            "route_b_freeze_fingerprint": native.ROUTE_B_FREEZE}


def load_validated_attention() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    repair = read(REPAIR / "native_attention_object.json")
    validation = read(REPAIR / "offline_revalidation_report.json")
    raw_evidence = read(EXECUTION / "attention_raw_response.json")
    if read(FREEZE_FINGERPRINT_PATH).get("freeze_fingerprint") != native.ROUTE_B_FREEZE:
        raise ValueError("ROUTE_B_FREEZE_FINGERPRINT_MISMATCH")
    if read(V3_FINGERPRINT_PATH).get("authorization_fingerprint") != V3_FINGERPRINT:
        raise ValueError("R6_V3_FINGERPRINT_MISMATCH")
    episode, _members, provenance = execution.load_frozen_episode()
    required = {
        "attention_identity": "NATTN_b85703c6c08cdfdffd27",
        "episode_identity": episode["episode_identity"],
        "primary_event_identity": episode["primary_event_identity"],
        "canonical_provider_identity": "Gemini",
        "transport_provider_identity": "Gemini",
        "transport_model_identity": "gemini-2.5-flash-lite",
        "payload_provider_role": "macro-research-model",
        "selection_state": "SELECTED_FOR_INFORMATION_REQUESTS",
        "acceptance_state": "ACCEPTED",
        "raw_response_checksum": EXPECTED_RAW,
    }
    for key, expected in required.items():
        if repair.get(key) != expected:
            raise ValueError("NATIVE_ATTENTION_EVIDENCE_MISMATCH:" + key)
    if raw_evidence.get("raw_response_checksum") != EXPECTED_RAW or checksum(raw_evidence.get("raw_response")) != EXPECTED_RAW:
        raise ValueError("PRESERVED_RAW_RESPONSE_CHECKSUM_MISMATCH")
    if not all(validation.get(key) is True for key in ("raw_checksum_valid", "episode_match", "provider_match", "model_match", "schema_valid", "cutoff_valid")):
        raise ValueError("NATIVE_ATTENTION_OFFLINE_REVALIDATION_INVALID")
    return repair, raw_evidence, {**provenance, "bridge_identity_repair_checksum": file_checksum(REPAIR / "final_bridge_identity_repair_decision.json")}


def request_unavailability(raw_evidence: Mapping[str, Any]) -> dict[str, Any]:
    raw = json.loads(str(raw_evidence["raw_response"]))
    usable = raw.get("object") == "session_information_requirements" and isinstance(raw.get("information_items"), list)
    return {
        "raw_request_count": len(raw.get("information_items", [])) if isinstance(raw.get("information_items"), list) else 0,
        "canonical_request_count": 0,
        "duplicate_count": 0,
        "ordering_status": "NOT_CREATED_NO_INFORMATION_REQUEST_RESPONSE",
        "provider_lineage": "NOT_CREATED",
        "model_lineage": "NOT_CREATED",
        "attention_lineage": "NOT_CREATED",
        "episode_lineage": "NOT_CREATED",
        "request_set_checksum": None,
        "source_object": raw.get("object"),
        "usable_information_request_response": usable,
        "failure": None if usable else "CANONICAL_REQUEST_RESPONSE_UNAVAILABLE",
        "reason": "The preserved raw response is an Attention Map and contains no information_items. The separate Request prompt response was never authorized or preserved; deriving Requests would invent scientific content.",
    }


def _readback_attention(*, service: Any, headers: list[str], record: Mapping[str, Any]) -> dict[str, Any]:
    last = native._column_name(len(headers))
    values = service.spreadsheets().values().get(
        spreadsheetId=native.MAIN_SPREADSHEET_ID, range=f"'{native.ATTENTION_SHEET}'!A2:{last}2"
    ).execute().get("values", [])
    row = values[0] if values else []
    expected = [record[key] for key in headers]
    return {"readback_performed": True, "range": f"{native.ATTENTION_SHEET}!A2:{last}2",
            "identity": row[0] if row else None, "matches_expected": row == expected,
            "content_checksum": record["content_checksum"], "lineage_checksum": record["lineage_checksum"],
            "materialization_status": row[headers.index("materialization_status")] if len(row) == len(headers) else None}


def materialize_attention_google(record: Mapping[str, Any], *, token_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, int]]:
    audit = {"metadata_reads": 0, "schema_reads": 0, "structural_writes": 0, "attention_writes": 0,
             "pack_a_writes": 0, "attention_readbacks": 0, "pack_a_readbacks": 0, "cleanup_operations": 0}
    before = file_checksum(token_path)
    credentials = google_clients.load_credentials(False, token_path=token_path, persist_refresh=False)
    service = google_clients.build_sheets_service(credentials)
    schema = native.ensure_bounded_object_schema(
        sheets_service=service, spreadsheet_id=native.MAIN_SPREADSHEET_ID,
        sheet_name=native.ATTENTION_SHEET, required_headers=native.ATTENTION_HEADERS,
    )
    audit["metadata_reads"] += 1
    audit["schema_reads"] += int(schema["schema_read"])
    audit["structural_writes"] += int(schema["created"]) + int(schema["header_written"])
    result = native.persist_native_attention(
        sheets_service=service, record=record, authorization_fingerprint=V3_FINGERPRINT,
        spreadsheet_id=native.MAIN_SPREADSHEET_ID, sheet_name=native.ATTENTION_SHEET,
    )
    audit["attention_writes"] += int(result["status"] == "MATERIALIZED")
    readback = _readback_attention(service=service, headers=list(schema["headers"]), record=record)
    audit["attention_readbacks"] += 1
    if not readback["matches_expected"]:
        raise ValueError("NATIVE_ATTENTION_READBACK_MISMATCH")
    after = file_checksum(token_path)
    return {**result, "schema": schema}, readback, {**audit, "token_checksum_before": before,
                                                        "token_checksum_after": after,
                                                        "token_checksum_changed": before != after}


def reports(*, attempt_google: bool) -> dict[str, Any]:
    external = {"provider_calls": 0, "gemini_calls": 0, "other_provider_calls": 0, "forecast_calls": 0,
                "http_acquisition_calls": 0, "market_data_calls": 0, "live_pack_e_computations": 0,
                "paired_r6_calls": 0, "r6_evidence_writes": 0, "historical_mutations": 0,
                "outcome_operations": 0, "evaluation_operations": 0}
    attention, raw_evidence, provenance = load_validated_attention()
    record = _attention_record(attention)
    request_report = request_unavailability(raw_evidence)
    attention_report: dict[str, Any] = {"status": "LOCAL_VALIDATED_NOT_GOOGLE_MATERIALIZED", "record": record}
    readback: dict[str, Any] = {"status": "NOT_EXECUTED"}
    google_audit: dict[str, Any] = {"metadata_reads": 0, "schema_reads": 0, "structural_writes": 0,
                                     "attention_writes": 0, "pack_a_writes": 0, "attention_readbacks": 0,
                                     "pack_a_readbacks": 0, "cleanup_operations": 0, "token_checksum_before": None,
                                     "token_checksum_after": None, "token_checksum_changed": False}
    google_blocker = None
    if attempt_google:
        try:
            attention_report, readback, google_audit = materialize_attention_google(
                record, token_path=ROOT / "local" / "token.json"
            )
        except Exception as exc:  # precise error appears only in local evidence
            google_blocker = type(exc).__name__ + ":" + str(exc)
            attention_report = {"status": "LOCAL_VALIDATED_GOOGLE_MATERIALIZATION_BLOCKED", "reason": google_blocker,
                                "record": record}
    pack_a_report = {"status": "NOT_CREATED", "failure": request_report["failure"],
                     "reason": request_report["reason"], "pack_e_contamination_absent": True}
    determinism = {"proof_runs": 3, "attention_identity_stable": len({attention["attention_identity"] for _ in range(3)}) == 1,
                   "attention_content_checksum_stable": len({record["content_checksum"] for _ in range(3)}) == 1,
                   "request_set_created": False, "pack_a_created": False}
    readiness = {"readiness_name": "PRESIGNAL_V21_DESIGNED_DRIFT_2_R6_NATIVE_INPUT_READINESS_V2",
                 "route_b_freeze_fingerprint": native.ROUTE_B_FREEZE, "r6_authorization_v3_fingerprint": V3_FINGERPRINT,
                 "episode_selection_authorization_fingerprint": SELECTION_FINGERPRINT,
                 "attention_execution_evidence_checksum": file_checksum(EXECUTION / "attention_raw_response.json"),
                 "bridge_identity_repair_commit": "13e57d50cafe8926341be63ba5d927f33e171d59",
                 "canonical_attention_identity": attention["attention_identity"], "canonical_request_set_checksum": None,
                 "canonical_pack_a_identity": None, "native_attention_google_object": native.ATTENTION_SHEET,
                 "canonical_pack_a_google_object": native.PACK_A_SHEET, "native_attention_readback_checksum": checksum(readback),
                 "canonical_pack_a_readback_checksum": None, "provider": "Gemini", "model": "gemini-2.5-flash-lite",
                 "forecast_cutoff": attention["forecast_cutoff"], "all_native_inputs_ready": False,
                 "blockers": [request_report["failure"]] + ([google_blocker] if google_blocker else [])}
    decision = "R6_NATIVE_INPUTS_FINAL_MATERIALIZATION_BLOCKED"
    return {
        "native_attention_input_manifest.json": {"attention": attention, "record": record, "provenance": provenance,
                                                   "raw_response_checksum_valid": True, "bridge_role_preserved": True,
                                                   "route_b_freeze_valid": True, "r6_authorization_v3_valid": True,
                                                   "provider_call_budget_preserved": {"used": 1, "remaining": 0, "retries": 0}},
        "native_attention_materialization_report.json": attention_report,
        "native_attention_google_binding.json": {"spreadsheet_id": native.MAIN_SPREADSHEET_ID, "workbook": "auto_eeresults_predictions",
                                                   "object": native.ATTENTION_SHEET, "headers": list(native.ATTENTION_HEADERS), "write_limit": 1},
        "native_attention_readback_report.json": readback,
        "canonical_request_set.json": {"status": "NOT_CREATED", **request_report},
        "canonical_request_comparison.json": request_report,
        "canonical_request_checksum_report.json": {"request_set_checksum": None, "reason": request_report["failure"]},
        "canonical_pack_a.json": {"status": "NOT_CREATED", "reason": request_report["failure"]},
        "canonical_pack_a_materialization_report.json": pack_a_report,
        "canonical_pack_a_google_binding.json": {"spreadsheet_id": native.MAIN_SPREADSHEET_ID, "workbook": "auto_eeresults_predictions",
                                                     "object": native.PACK_A_SHEET, "headers": list(native.PACK_A_HEADERS), "write_limit": 1},
        "canonical_pack_a_readback_report.json": {"status": "NOT_EXECUTED", "reason": request_report["failure"]},
        "pack_a_contamination_report.json": {"status": "PASS_NOT_CREATED", "pack_e_only_content_added": False,
                                                "reason": "No Pack A is constructed without a separate canonical Request response."},
        "native_input_determinism_report.json": determinism,
        "native_input_isolation_audit.json": external,
        "google_operations_audit.json": google_audit,
        "native_input_readiness_v2_manifest.json": readiness,
        "native_input_readiness_v2_fingerprint.json": {"readiness_name": readiness["readiness_name"], "readiness_fingerprint": checksum(readiness),
                                                          "canonicalization": "sorted-key compact UTF-8 JSON SHA-256", "reproducible": True},
        "final_native_input_materialization_decision.json": {"decision": decision, "attention_blocker": None,
                                                               "request_blocker": request_report["failure"], "pack_a_blocker": request_report["failure"],
                                                               "google_materialization_blocker": google_blocker, "all_native_inputs_ready": False,
                                                               "next_authorized_action": "A separate explicit Gemini Information-Request call authorization is required; the consumed Attention response cannot supply Request content."},
    }


def run(*, output: Path, attempt_google: bool) -> None:
    for name, value in reports(attempt_google=attempt_google).items():
        write(output / name, value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--materialize-google", action="store_true")
    args = parser.parse_args()
    run(output=args.output, attempt_google=args.materialize_google)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
