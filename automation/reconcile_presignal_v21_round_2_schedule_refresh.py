#!/usr/bin/env python3
"""One-read, no-refresh reconciliation for an ambiguous Round 2 schedule upsert."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import google_clients

BASE = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
PRIOR_DIR = BASE / "PPHB-R2-SCHEDULE-REFRESH-20260803T142000Z"
OUTPUT_DIR = BASE / "PPHB-R2-SCHEDULE-REFRESH-RECONCILIATION-20260803T143000Z"
AUTH_ID = "PPHB-R2-SCHEDULE-REFRESH-RECONCILIATION-AUTHORIZATION-20260803T143000Z"
PRIOR_AUTH_ID = "PPHB-R2-SCHEDULE-REFRESH-AUTHORIZATION-20260803T142000Z"
PRIOR_FP = "sha256:2e4bd7300b5098515e25edefe75da10402d633c2ea53bc9e2206d35970a0962c"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def load_prior() -> dict[str, Any]:
    prior = json.loads((PRIOR_DIR / "schedule_refresh_execution.json").read_text())
    if prior.get("authorization_fingerprint") != PRIOR_FP or prior.get("remote_state") != "UNKNOWN_POST_DISPATCH":
        raise RuntimeError("PRIOR_REFRESH_BINDING_CONFLICT")
    return prior


def authorization(prior: dict[str, Any]) -> dict[str, Any]:
    return {
        "authorization_id": AUTH_ID,
        "authorization_schema_version": "1.0.0",
        "authorization_status": "FROZEN_SINGLE_USE_READ_ONLY_RECONCILIATION",
        "prior_refresh_binding": {"authorization_id": PRIOR_AUTH_ID, "authorization_fingerprint": PRIOR_FP, "window": {"from_utc_iso": "2026-08-03T00:00:00Z", "to_utc_iso": "2026-08-10T23:59:59Z"}, "prior_remote_state": prior["remote_state"]},
        "workbook_authority": {"spreadsheet_id": google_clients.DEFAULT_SPREADSHEET_ID, "sheet": "Event", "read_range": "Event!A:AZ"},
        "ceilings": {"fmp_requests": 0, "apps_script_refresh_invocations": 0, "event_sheet_writes": 0, "event_sheet_diagnostic_reads": 1, "retries": 0, "provider_calls": 0, "outcome_activity": 0},
        "classification_rule": "An Event-sheet read can confirm neither creation/update by the prior invocation nor non-application without invocation-specific operation lineage or pre-dispatch baseline. Existing matching rows alone are insufficient.",
        "stop_conditions": ["duplicate event identity", "schema mismatch", "timezone ambiguity", "revision conflict", "read failure", "missing invocation-specific lineage"],
    }


def freeze(output_dir: Path = OUTPUT_DIR) -> tuple[dict[str, Any], dict[str, Any]]:
    if output_dir.exists():
        auth = json.loads((output_dir / "reconciliation_authorization.json").read_text())
        original = dict(auth); supplied = original.pop("authorization_fingerprint", "")
        if supplied != digest(original):
            raise RuntimeError("RECONCILIATION_AUTHORIZATION_FINGERPRINT_CONFLICT")
        return auth, load_prior()
    prior = load_prior()
    auth = authorization(prior); auth["authorization_fingerprint"] = digest(auth)
    output_dir.mkdir(parents=True)
    (output_dir / "reconciliation_authorization.json").write_text(json.dumps(auth, indent=2, sort_keys=True) + "\n")
    return auth, prior


def execute(output_dir: Path, auth: dict[str, Any], prior: dict[str, Any]) -> dict[str, Any]:
    # The caller supplies the accepted explicit credential path; it is never
    # written to evidence and the one read is performed without the retrying helper.
    creds = google_clients.load_credentials(False, persist_refresh=False)
    service = google_clients.build_sheets_service(creds)
    try:
        values = service.spreadsheets().values().get(spreadsheetId=google_clients.DEFAULT_SPREADSHEET_ID, range="Event!A:AZ").execute().get("values", [])
    finally:
        google_clients.close_google_service(service)
    headers = [str(value).strip() for value in (values[0] if values else [])]
    rows = [dict(zip(headers, row + [""] * max(0, len(headers) - len(row)))) for row in values[1:]]
    required = {"country", "indicator_name", "release_ts", "source_cal", "event_id", "batch_id", "type"}
    schema_ok = required <= set(headers)
    in_window = [row for row in rows if str(row.get("source_cal", "")).upper() == "FMP" and "2026-08-03" <= str(row.get("release_ts", ""))[:10] <= "2026-08-10"]
    keys = [(str(row.get("country", "")).upper(), str(row.get("indicator_name", "")), str(row.get("release_ts", ""))) for row in in_window]
    duplicates = len(keys) - len(set(keys))
    result = {
        "decision": "SCHEDULE_REFRESH_REMOTE_STATE_UNRESOLVED",
        "prior_refresh_binding": {"authorization_id": PRIOR_AUTH_ID, "authorization_fingerprint": PRIOR_FP, "remote_state": prior["remote_state"]},
        "reconciliation_authorization_binding": {"authorization_id": auth["authorization_id"], "authorization_fingerprint": auth["authorization_fingerprint"]},
        "event_sheet_read": {"count": 1, "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "header_count": len(headers), "row_count": len(rows), "schema_ok": schema_ok, "window_fmp_row_count": len(in_window), "duplicate_window_event_keys": duplicates},
        "classification_proof": "The Event schema has no invocation ID, upsert timestamp, raw-FMP response fingerprint, or pre-dispatch baseline binding. The permitted one read cannot distinguish rows created/updated by the submitted invocation from pre-existing matching rows; success and non-application are therefore both unproven.",
        "new_fmp_requests": 0,
        "new_apps_script_refresh_invocations": 0,
        "new_event_sheet_writes": 0,
        "new_export_or_diagnostic_reads": 1,
        "retries": 0,
        "provider_calls": 0,
        "outcome_activity": 0,
        "snapshot_permitted": False,
        "admission_permitted": False,
    }
    (output_dir / "event_sheet_diagnostic_read.json").write_text(json.dumps({"headers": headers, "rows": rows, "fingerprint": digest({"headers": headers, "rows": rows})}, indent=2, sort_keys=True) + "\n")
    (output_dir / "remote_state_reconciliation.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--execute", action="store_true"); parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR); args = parser.parse_args()
    auth, prior = freeze(args.output_dir)
    if not args.execute:
        print(json.dumps({"authorization_id": auth["authorization_id"], "authorization_fingerprint": auth["authorization_fingerprint"]}, sort_keys=True)); return 0
    result = execute(args.output_dir, auth, prior)
    print(json.dumps(result, sort_keys=True)); return 2


if __name__ == "__main__":
    raise SystemExit(main())
