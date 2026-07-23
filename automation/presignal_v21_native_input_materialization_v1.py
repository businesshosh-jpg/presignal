"""Return-only native Attention and Pack A materialization adapters for R6.

The adapters preserve the existing v2 split: Attention is established by the
authoritative provider-response boundary, while Pack A is the selected
provider's canonical Information Request set.  They do not call that boundary
or manufacture its output.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence


ATTENTION_SCHEMA_VERSION = "presignal_v21_native_attention_v1"
PACK_A_SCHEMA_VERSION = "presignal_v21_canonical_pack_a_v1"
R6_AUTHORIZATION = "PRESIGNAL_V21_DESIGNED_DRIFT_2_R6_PAIRED_SMOKE_AUTHORIZATION_V3"
ROUTE_B_FREEZE = "sha256:8c910a343515d88ca63ce4aaf738f28f9b4a8ab22665397077858bfaf7e866e4"
MAIN_SPREADSHEET_ID = "1_gZGnd6h3VzdiBvGBHRSxn78KW8tsOi2UEc6Y_Sc23Q"
ATTENTION_SHEET = "Native_Attention"
PACK_A_SHEET = "Canonical_Pack_A"
ATTENTION_HEADERS = ("attention_identity", "episode_identity", "primary_event_identity", "provider_identity", "model_identity", "prompt_version", "selection_state", "acceptance_state", "selection_reason", "effective_timestamp", "forecast_cutoff", "schema_version", "provenance_checksum", "lineage_checksum", "materialization_status")
PACK_A_HEADERS = ("pack_a_identity", "episode_identity", "primary_event_identity", "forecast_cutoff", "schema_version", "pack_a_items_json", "content_checksum", "input_checksum", "provenance_checksum", "lineage_checksum", "materialization_status")
FORBIDDEN = ("outcome", "evaluation", "accuracy", "winner", "pack_e", "acquisition", "source_content", "unavailable")


class NativeInputMaterializationError(ValueError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def checksum(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def _timestamp(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise NativeInputMaterializationError(code)
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError as exc:
        raise NativeInputMaterializationError(code) from exc
    return value


def _episode(episode: Mapping[str, Any]) -> dict[str, str]:
    required = ("episode_id", "primary_event_id", "forecast_cutoff_ts", "release_ts", "schema_version")
    if any(not episode.get(key) for key in required):
        raise NativeInputMaterializationError("CANONICAL_EPISODE_LINEAGE_INCOMPLETE")
    _timestamp(episode["forecast_cutoff_ts"], "EPISODE_CUTOFF_INVALID")
    _timestamp(episode["release_ts"], "EPISODE_RELEASE_INVALID")
    return {"episode_identity": str(episode["episode_id"]), "primary_event_identity": str(episode["primary_event_id"]), "forecast_cutoff": str(episode["forecast_cutoff_ts"]), "episode_schema_version": str(episode["schema_version"])}


def materialize_selected_native_attention(*, episode: Mapping[str, Any], provider: str, model: str, prompt_version: str,
                                          selection_state: str, acceptance_state: str, selection_reason: str,
                                          effective_timestamp: str, provenance: Mapping[str, Any]) -> dict[str, Any]:
    """Canonicalize an already-authoritative selected Attention result.

    The selection decision must be supplied by the existing Attention boundary;
    this function only validates lineage and returns a deterministic object.
    """
    ep = _episode(episode)
    if provider != "Gemini" or model != "gemini-2.5-flash-lite":
        raise NativeInputMaterializationError("ATTENTION_PROVIDER_MODEL_SCOPE_MISMATCH")
    if selection_state not in {"SELECTED", "SELECTED_FOR_INFORMATION_REQUESTS"}:
        raise NativeInputMaterializationError("NATIVE_ATTENTION_NOT_SELECTED")
    if acceptance_state != "ACCEPTED" or not isinstance(selection_reason, str) or not selection_reason:
        raise NativeInputMaterializationError("NATIVE_ATTENTION_NOT_ACCEPTED")
    effective = _timestamp(effective_timestamp, "ATTENTION_EFFECTIVE_TIMESTAMP_INVALID")
    if effective > ep["forecast_cutoff"]:
        raise NativeInputMaterializationError("ATTENTION_AFTER_CUTOFF")
    lineage = {**ep, "provider_identity": provider, "model_identity": model, "prompt_version": prompt_version, "selection_state": selection_state, "acceptance_state": acceptance_state}
    attention_identity = "NATTN_" + hashlib.sha256(canonical(lineage).encode("utf-8")).hexdigest()[:20]
    return {"attention_identity": attention_identity, **lineage, "selection_reason": selection_reason, "effective_timestamp": effective,
            "schema_version": ATTENTION_SCHEMA_VERSION, "provenance": dict(provenance), "provenance_checksum": checksum(provenance),
            "lineage": lineage, "lineage_checksum": checksum(lineage), "materialization_status": "READY"}


def build_canonical_pack_a(*, episode: Mapping[str, Any], attention: Mapping[str, Any], canonical_requests: Sequence[Mapping[str, Any]],
                           provenance: Mapping[str, Any]) -> dict[str, Any]:
    """Build Pack A exclusively from ordered canonical selected-provider Requests."""
    ep = _episode(episode)
    if attention.get("episode_identity") != ep["episode_identity"] or attention.get("forecast_cutoff") != ep["forecast_cutoff"]:
        raise NativeInputMaterializationError("PACK_A_ATTENTION_LINEAGE_MISMATCH")
    if attention.get("selection_state") not in {"SELECTED", "SELECTED_FOR_INFORMATION_REQUESTS"} or attention.get("acceptance_state") != "ACCEPTED":
        raise NativeInputMaterializationError("PACK_A_ATTENTION_NOT_SELECTED")
    rows = []
    for request in canonical_requests:
        if any(marker in str(key).lower() for key in request for marker in FORBIDDEN):
            raise NativeInputMaterializationError("PACK_A_PACK_E_CONTAMINATION")
        required = ("request_identity", "episode_identity", "provider", "model", "prompt_version", "forecast_cutoff", "requested_information", "information_category", "priority")
        if any(not request.get(key) for key in required):
            raise NativeInputMaterializationError("PACK_A_REQUEST_LINEAGE_INCOMPLETE")
        if request["episode_identity"] != ep["episode_identity"] or request["forecast_cutoff"] != ep["forecast_cutoff"]:
            raise NativeInputMaterializationError("PACK_A_REQUEST_LINEAGE_MISMATCH")
        if request["provider"] != attention["provider_identity"] or request["model"] != attention["model_identity"] or request["prompt_version"] != attention["prompt_version"]:
            raise NativeInputMaterializationError("PACK_A_REQUEST_PROVIDER_LINEAGE_MISMATCH")
        rows.append({key: request[key] for key in required})
    if not rows:
        raise NativeInputMaterializationError("PACK_A_EMPTY")
    if [row["request_identity"] for row in rows] != sorted(row["request_identity"] for row in rows):
        raise NativeInputMaterializationError("PACK_A_REQUEST_ORDER_NOT_CANONICAL")
    content_checksum = checksum(rows)
    lineage = {**ep, "attention_identity": attention["attention_identity"], "provider_identity": attention["provider_identity"], "model_identity": attention["model_identity"], "prompt_version": attention["prompt_version"], "request_identities": [row["request_identity"] for row in rows]}
    pack_a_identity = "PACKA_" + hashlib.sha256(canonical({"lineage": lineage, "content_checksum": content_checksum}).encode("utf-8")).hexdigest()[:20]
    return {"pack_a_identity": pack_a_identity, **ep, "schema_version": PACK_A_SCHEMA_VERSION, "pack_a_items": rows,
            "content_checksum": content_checksum, "input_checksum": checksum({"episode": ep, "attention": attention["attention_identity"], "requests": rows}),
            "provenance": dict(provenance), "provenance_checksum": checksum(provenance), "lineage": lineage, "lineage_checksum": checksum(lineage), "materialization_status": "READY"}


def _row(record: Mapping[str, Any], headers: Sequence[str], *, authorization_fingerprint: str) -> list[Any]:
    if record.get("authorization_identity") != R6_AUTHORIZATION or record.get("authorization_fingerprint") != authorization_fingerprint:
        raise NativeInputMaterializationError("NATIVE_INPUT_AUTHORIZATION_MISMATCH")
    if record.get("route_b_freeze_fingerprint") != ROUTE_B_FREEZE:
        raise NativeInputMaterializationError("NATIVE_INPUT_FREEZE_MISMATCH")
    if any(marker in str(key).lower() for key in record for marker in ("outcome", "evaluation")):
        raise NativeInputMaterializationError("NATIVE_INPUT_FORBIDDEN_FIELD")
    if set(record) != set(headers) | {"authorization_identity", "authorization_fingerprint", "route_b_freeze_fingerprint"}:
        raise NativeInputMaterializationError("NATIVE_INPUT_SCHEMA_MISMATCH")
    return [record[key] for key in headers]


def persist_native_attention(*, sheets_service: Any, record: Mapping[str, Any], authorization_fingerprint: str, spreadsheet_id: str, sheet_name: str) -> dict[str, Any]:
    return _persist(sheets_service=sheets_service, record=record, headers=ATTENTION_HEADERS, spreadsheet_id=spreadsheet_id, sheet_name=sheet_name, expected_sheet=ATTENTION_SHEET, authorization_fingerprint=authorization_fingerprint)


def persist_canonical_pack_a(*, sheets_service: Any, record: Mapping[str, Any], authorization_fingerprint: str, spreadsheet_id: str, sheet_name: str) -> dict[str, Any]:
    return _persist(sheets_service=sheets_service, record=record, headers=PACK_A_HEADERS, spreadsheet_id=spreadsheet_id, sheet_name=sheet_name, expected_sheet=PACK_A_SHEET, authorization_fingerprint=authorization_fingerprint)


def _persist(*, sheets_service: Any, record: Mapping[str, Any], headers: Sequence[str], spreadsheet_id: str, sheet_name: str, expected_sheet: str, authorization_fingerprint: str) -> dict[str, Any]:
    if spreadsheet_id != MAIN_SPREADSHEET_ID or sheet_name != expected_sheet:
        raise NativeInputMaterializationError("NATIVE_INPUT_TARGET_MISMATCH")
    values = sheets_service.spreadsheets().values()
    header = values.get(spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!1:1").execute().get("values", [[]])[0]
    if header != list(headers):
        raise NativeInputMaterializationError("NATIVE_INPUT_DESTINATION_SCHEMA_MISMATCH")
    row = _row(record, headers, authorization_fingerprint=authorization_fingerprint)
    existing = values.get(spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!A2:O").execute().get("values", [])
    identity = row[0]
    for prior in existing:
        if prior and prior[0] == identity:
            if prior == row:
                return {"status": "ALREADY_MATERIALIZED_IDENTICAL", "identity": identity}
            raise NativeInputMaterializationError("NATIVE_INPUT_DUPLICATE_CONFLICT")
    if existing:
        raise NativeInputMaterializationError("NATIVE_INPUT_WRITE_LIMIT_EXCEEDED")
    result = values.append(spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!A2", valueInputOption="RAW", insertDataOption="INSERT_ROWS", body={"values": [row]}).execute()
    return {"status": "MATERIALIZED", "identity": identity, "updated_range": result.get("updates", {}).get("updatedRange")}
