#!/usr/bin/env python3
"""Freeze and execute one bounded Round 2 schedule refresh/export authorization."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import google_clients
from automation.run_presignal_v21_continuous_round_2 import SOURCE_AUTHORITY

BASE = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
OUTPUT_DIR = BASE / "PPHB-R2-SCHEDULE-REFRESH-20260803T141000Z"
AUTH_ID = "PPHB-R2-SCHEDULE-REFRESH-AUTHORIZATION-20260803T141000Z"
PROTOCOL_ID = "PPHB-R2-CONFIRMATORY-PROSPECTIVE-PROTOCOL-20260804T080000Z"
PROTOCOL_FP = "sha256:d417e4c76d3d38d471dbc76cbf361be4a28dac1b615ecccdc8aa18c37262362f"
ENVELOPE_ID = "PPHB-R2-EXECUTION-ENVELOPE-20260803T090000Z"
ENVELOPE_FP = "sha256:3fe721eee816e48a5eca00c50cbcbc397bec6258d60bdfc7857e8169869efdd0"
FROM_UTC = "2026-08-03T00:00:00Z"
TO_UTC = "2026-08-10T23:59:59Z"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def authorization() -> dict[str, Any]:
    return {
        "authorization_id": AUTH_ID,
        "authorization_schema_version": "1.0.0",
        "authorization_status": "FROZEN_SINGLE_USE_ACTIVE_FOR_REFRESH_ONLY",
        "timestamp_semantics": "Deterministic artifact naming metadata only; not a validity boundary.",
        "protocol_binding": {"protocol_id": PROTOCOL_ID, "protocol_fingerprint": PROTOCOL_FP},
        "envelope_binding": {"envelope_id": ENVELOPE_ID, "envelope_fingerprint": ENVELOPE_FP},
        "source_authority": SOURCE_AUTHORITY,
        "fmp_window": {"from_utc_iso": FROM_UTC, "to_utc_iso": TO_UTC, "reason": "Smallest date-bounded window providing current prospective lead time for first Slice admission."},
        "routes": {"apps_script_function": "apiUpsertEventWindow", "apps_script_deployment": "existing configured script ID via automation.google_clients.default_script_id", "fmp_entry_point": "fmpFetchRangeUtc_", "event_sheet": "Event", "export_route": "Google Sheets values read of Event!A:AZ"},
        "ceilings": {"fmp_api_requests": 1, "apps_script_invocations": 1, "event_sheet_upsert_operations": 1, "event_sheet_export_reads": 1, "retries": 0},
        "preservation": ["request identity", "window", "FMP response authority and source timestamps", "Apps Script request/response metadata", "upsert counts", "export rows and headers", "remote-state certainty", "append-only lineage"],
        "duplicate_revision_rules": "Canonical event identity and fallback country|indicator_name|release_ts prevent duplicate insertion; revision/cancellation changes after snapshot validation stop admission rather than silently replacing identity.",
        "stop_conditions": ["ambiguous FMP response", "Apps Script partial or unknown write state", "duplicate identity", "schema mismatch", "timezone ambiguity", "revision conflict", "ceiling exceeded", "credential or transport state not certain"],
        "not_authorized": ["provider dispatch", "Outcome collection", "market-data requests", "evaluation", "retries", "unrelated Google writes"],
        "export_destination": str(OUTPUT_DIR / "event_sheet_snapshot.json"),
    }


def freeze(output_dir: Path = OUTPUT_DIR) -> tuple[dict[str, Any], dict[str, Any]]:
    if output_dir.exists():
        auth_path = output_dir / "schedule_refresh_authorization.json"
        validation_path = output_dir / "authorization_validation.json"
        if not auth_path.exists() or not validation_path.exists():
            raise RuntimeError("SCHEDULE_REFRESH_AUTHORIZATION_ARTIFACT_INCOMPLETE")
        value = json.loads(auth_path.read_text())
        supplied = value.pop("authorization_fingerprint", "")
        if supplied != digest(value) or supplied != "sha256:59f21d0e18ca85fc3bc69e9871093ad9f03c1e422ec757d0307e8338c6b3c275":
            raise RuntimeError("SCHEDULE_REFRESH_AUTHORIZATION_FINGERPRINT_CONFLICT")
        value["authorization_fingerprint"] = supplied
        evidence = json.loads(validation_path.read_text())
        if evidence.get("authorization_fingerprint") != supplied:
            raise RuntimeError("SCHEDULE_REFRESH_AUTHORIZATION_VALIDATION_CONFLICT")
        return value, evidence
    value = authorization()
    value["authorization_fingerprint"] = digest(value)
    evidence = {"decision": "ROUND_2_SCHEDULE_REFRESH_AUTHORIZATION_FROZEN", "external_access": 0, "apps_script_invocations": 0, "fmp_requests": 0, "event_sheet_writes": 0, "export_reads": 0, "remote_state": "NOT_STARTED", "authorization_fingerprint": value["authorization_fingerprint"]}
    output_dir.mkdir(parents=True)
    (output_dir / "schedule_refresh_authorization.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    (output_dir / "authorization_validation.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    return value, evidence


def execute(output_dir: Path, value: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    started = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        credentials = google_clients.load_credentials(interactive=False, persist_refresh=True)
        service = google_clients.build_script_service(credentials, 300)
    except Exception as exc:
        evidence.update({"decision": "ROUND_2_SCHEDULE_REFRESH_BLOCKED", "started_utc": started, "credential_or_client_setup": type(exc).__name__, "error_classification": google_clients.classify_google_exception(exc), "apps_script_invocations": 0, "fmp_requests": 0, "event_sheet_writes": 0, "export_reads": 0, "remote_state": "CONFIRMED_NOT_DISPATCHED", "stop": "SCHEDULE_REFRESH_FAILED_CLOSED"})
        (output_dir / "schedule_refresh_execution.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
        return evidence
    try:
        result = google_clients.run_script_function_with_metadata(service, google_clients.default_script_id(), "apiUpsertEventWindow", [{"from_utc_iso": FROM_UTC, "to_utc_iso": TO_UTC}], dev_mode=True)
    finally:
        google_clients.close_google_service_transport(service)
    evidence.update({"decision": "ROUND_2_SCHEDULE_REFRESH_EXECUTED", "started_utc": started, "apps_script_invocations": 1, "fmp_requests": 1, "apps_script_result": result})
    if not result.get("ok"):
        evidence.update({"remote_state": result.get("classification", {}).get("dispatch_certainty", "UNKNOWN"), "event_sheet_writes": 0, "export_reads": 0, "stop": "SCHEDULE_REFRESH_FAILED_CLOSED"})
        (output_dir / "schedule_refresh_execution.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
        return evidence
    sheets = google_clients.build_sheets_service(credentials, 300)
    try:
        values = google_clients.get_sheet_values(sheets, google_clients.DEFAULT_SPREADSHEET_ID, "Event!A:AZ")
    finally:
        google_clients.close_google_service_transport(sheets)
    headers = [str(item).strip() for item in (values[0] if values else [])]
    rows = [dict(zip(headers, row + [""] * max(0, len(headers) - len(row)))) for row in values[1:]] if values else []
    snapshot = {"snapshot_id": "PPHB-R2-CURRENT-EVENT-SNAPSHOT-20260803T141000Z", "snapshot_status": "AUTHORITATIVE_EVENT_SHEET_EXPORT", "source_authority": SOURCE_AUTHORITY, "exported_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "spreadsheet_id": google_clients.DEFAULT_SPREADSHEET_ID, "sheet_name": "Event", "source_refresh_authorization": AUTH_ID, "source_refresh_authorization_fingerprint": value["authorization_fingerprint"], "request_window": {"from_utc_iso": FROM_UTC, "to_utc_iso": TO_UTC}, "acquisition_lineage": {"canonical_steps": ["apiUpsertEventWindow_", "runFmpRangeToEvent_", "applyBatchingForKeys_", "event_sheet_export"]}, "headers": headers, "event_rows": rows}
    snapshot["snapshot_fingerprint"] = digest(snapshot)
    evidence.update({"event_sheet_writes": 1, "export_reads": 1, "remote_state": "CERTAIN", "event_rows": len(rows), "snapshot_id": snapshot["snapshot_id"], "snapshot_fingerprint": snapshot["snapshot_fingerprint"]})
    (output_dir / "event_sheet_snapshot.json").write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    (output_dir / "schedule_refresh_execution.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--record-blocked", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    value, evidence = freeze(args.output_dir)
    if args.record_blocked:
        evidence.update({"decision": "ROUND_2_SCHEDULE_REFRESH_BLOCKED", "stop": "SCHEDULE_REFRESH_FAILED_CLOSED", "remote_state": "CONFIRMED_NOT_DISPATCHED", "blocking_reason": "Google client setup was interrupted before Apps Script dispatch; no FMP request, Apps Script invocation, Event-sheet write, or export read was confirmed."})
        (args.output_dir / "schedule_refresh_execution.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
        print(json.dumps(evidence, sort_keys=True))
        return 2
    if args.execute:
        evidence = execute(args.output_dir, value, evidence)
    print(json.dumps(evidence, sort_keys=True))
    return 0 if evidence.get("stop") != "SCHEDULE_REFRESH_FAILED_CLOSED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
