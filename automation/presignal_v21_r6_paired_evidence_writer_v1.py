"""Fixed-target, caller-controlled writer for one R6 paired-evidence record.

This operational writer is intentionally outside Route B scientific compute.
It does not construct Packs, call a provider, acquire sources, construct an
Outcome, or evaluate a forecast.
"""
from __future__ import annotations

from typing import Any, Mapping


TARGET_SPREADSHEET_ID = "1hQpdjKAICAbk8oIIFp0xS_oeV3pN9Q2yxmBhqYewG54"
TARGET_SHEET = "R6_Paired_Evidence"
AUTHORIZATION_NAME = "PRESIGNAL_V21_DESIGNED_DRIFT_2_R6_PAIRED_SMOKE_AUTHORIZATION_V3"
ROUTE_B_FREEZE_NAME = "PRESIGNAL_V21_ROUTE_B_CAPABILITY_FREEZE_V1"
ROUTE_B_FREEZE_FINGERPRINT = "sha256:8c910a343515d88ca63ce4aaf738f28f9b4a8ab22665397077858bfaf7e866e4"
EVIDENCE_HEADERS = (
    "run_identity", "authorization_identity", "authorization_fingerprint", "route_b_freeze_name", "route_b_freeze_fingerprint",
    "episode_identity", "primary_event_identity", "forecast_cutoff", "provider", "model", "prompt_version", "call_order",
    "pack_a_identity", "pack_a_checksum", "pack_e_identity", "pack_e_checksum", "paired_comparability_status",
    "pack_a_raw_response", "pack_e_raw_response", "pack_a_normalized_forecast", "pack_e_normalized_forecast",
    "pack_a_schema_status", "pack_e_schema_status", "run_status", "failure_stage", "failure_reason",
    "episode_lineage", "attention_lineage", "request_lineage", "acquisition_lineage", "pack_lineage", "created_at",
)
FORBIDDEN_FIELD_MARKERS = ("outcome", "evaluation", "accuracy", "winner", "market_path", "promotion")


class R6EvidenceWriterError(ValueError):
    pass


def validate_evidence(evidence: Mapping[str, Any], *, authorization_fingerprint: str) -> dict[str, Any]:
    keys = set(evidence)
    required = set(EVIDENCE_HEADERS)
    if keys != required:
        raise R6EvidenceWriterError("R6_EVIDENCE_SCHEMA_INCOMPLETE")
    if any(marker in key.lower() for key in keys for marker in FORBIDDEN_FIELD_MARKERS):
        raise R6EvidenceWriterError("R6_EVIDENCE_FORBIDDEN_FIELD")
    if evidence["authorization_identity"] != AUTHORIZATION_NAME or evidence["authorization_fingerprint"] != authorization_fingerprint:
        raise R6EvidenceWriterError("R6_EVIDENCE_AUTHORIZATION_MISMATCH")
    if evidence["route_b_freeze_name"] != ROUTE_B_FREEZE_NAME or evidence["route_b_freeze_fingerprint"] != ROUTE_B_FREEZE_FINGERPRINT:
        raise R6EvidenceWriterError("R6_EVIDENCE_FREEZE_MISMATCH")
    if evidence["provider"] != "Gemini" or evidence["model"] != "gemini-2.5-flash-lite":
        raise R6EvidenceWriterError("R6_EVIDENCE_PROVIDER_SCOPE_MISMATCH")
    if evidence["call_order"] != "PACK_A_THEN_PACK_E":
        raise R6EvidenceWriterError("R6_EVIDENCE_CALL_ORDER_MISMATCH")
    if evidence["run_status"] not in {"SUCCESS", "FAILED"}:
        raise R6EvidenceWriterError("R6_EVIDENCE_RUN_STATUS_INVALID")
    if evidence["run_status"] == "SUCCESS" and (not evidence["pack_a_schema_status"] or not evidence["pack_e_schema_status"]):
        raise R6EvidenceWriterError("R6_EVIDENCE_PARTIAL_PAIR")
    return {name: evidence[name] for name in EVIDENCE_HEADERS}


def persist_one_paired_evidence(*, sheets_service: Any, evidence: Mapping[str, Any], authorization_fingerprint: str,
                                spreadsheet_id: str, sheet_name: str) -> dict[str, Any]:
    """Append exactly one validated record to the fixed isolated destination."""
    if spreadsheet_id != TARGET_SPREADSHEET_ID or sheet_name != TARGET_SHEET:
        raise R6EvidenceWriterError("R6_EVIDENCE_TARGET_MISMATCH")
    row = validate_evidence(evidence, authorization_fingerprint=authorization_fingerprint)
    header = sheets_service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range="'R6_Paired_Evidence'!1:1").execute().get("values", [[]])[0]
    if header != list(EVIDENCE_HEADERS):
        raise R6EvidenceWriterError("R6_EVIDENCE_DESTINATION_SCHEMA_MISMATCH")
    existing = sheets_service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range="'R6_Paired_Evidence'!A2:A").execute().get("values", [])
    if existing:
        raise R6EvidenceWriterError("R6_EVIDENCE_WRITE_LIMIT_EXCEEDED")
    result = sheets_service.spreadsheets().values().append(spreadsheetId=spreadsheet_id, range="'R6_Paired_Evidence'!A2", valueInputOption="RAW", insertDataOption="INSERT_ROWS", body={"values": [[row[name] for name in EVIDENCE_HEADERS]]}).execute()
    return {"target_spreadsheet_id": spreadsheet_id, "target_sheet": sheet_name, "successful_write_count": 1, "updated_range": result.get("updates", {}).get("updatedRange")}
