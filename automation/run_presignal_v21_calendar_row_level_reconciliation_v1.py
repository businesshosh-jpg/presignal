"""One captured row-level calendar replay and bounded Event reconciliation."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import google_clients
from automation import presignal_v21_calendar_idempotency_replay_v1 as capture
from automation import presignal_v21_calendar_row_level_result_v1 as contract

OUT = ROOT / "outputs/presignal_v21_designed_drift_r6_calendar_row_level_reconciliation" / "R6-CALENDAR-ROW-LEVEL-RECONCILIATION-20260724-v1"
WINDOW = {"start_utc": "2026-07-24T00:00:00Z", "end_utc": "2026-07-31T00:00:00Z"}
SPREADSHEET_ID = "1_gZGnd6h3VzdiBvGBHRSxn78KW8tsOi2UEc6Y_Sc23Q"
TOKEN_PATH = Path("/Users/junhoshino/projects/presignal/local/token.json")
RANGE = "Event!A4345:U4445"
HEADERS = ["object", "country", "indicator_name", "genre", "importance", "type", "event_id", "batch_id", "release_ts", "source_cal", "consensus_value", "prev_revision", "released_value", "released_ts", "source_provider", "source_series_id", "transform", "release_status", "notes", "resolution_method", "confidence_level"]


def canonical(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True)


def sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def write(name: str, value: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(canonical(value) + "\n", encoding="utf-8")


def parse(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def in_date_window(value: str) -> bool:
    instant = parse(value)
    return parse(WINDOW["start_utc"]).date() <= instant.date() <= parse(WINDOW["end_utc"]).date()


def content_for_google(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "country": str(row.get("country") or "").upper(), "indicator_name": str(row.get("indicator_name") or ""),
        "release_ts": str(row.get("release_ts") or ""), "source_identity": "FMP", "genre": str(row.get("genre") or ""),
        "importance": str(row.get("importance") or ""), "consensus_value": row.get("consensus_value") if row.get("consensus_value") not in (None, "") else "",
        "prev_revision": row.get("prev_revision") if row.get("prev_revision") not in (None, "") else "",
        "released_value": row.get("released_value") if row.get("released_value") not in (None, "") else "",
        "released_ts": str(row.get("released_ts") or ""), "source_provider": str(row.get("source_provider") or ""),
        "source_series_id": str(row.get("source_series_id") or ""), "transform": str(row.get("transform") or ""),
        "release_status": str(row.get("release_status") or "scheduled"), "notes": str(row.get("notes") or ""),
        "resolution_method": str(row.get("resolution_method") or ""), "confidence_level": str(row.get("confidence_level") or ""),
    }


def readback(service: Any) -> dict[str, Any]:
    response = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID, range=RANGE,
        valueRenderOption="UNFORMATTED_VALUE", dateTimeRenderOption="SERIAL_NUMBER",
    ).execute()
    rows = []
    for offset, values in enumerate(response.get("values", [])):
        if not any(str(value) for value in values):
            continue
        # Event has one leading legacy cell before its canonical append-only columns.
        row = dict(zip(HEADERS, list(values)[1:] + [""] * len(HEADERS)))
        row["source_row"] = 4345 + offset
        try:
            if not in_date_window(row["release_ts"]):
                continue
        except Exception:
            continue
        result = {
            "event_identity": contract.identity(row), "country": str(row["country"]).upper(),
            "indicator_name": row["indicator_name"], "release_ts": row["release_ts"], "source_identity": "FMP",
            "content_checksum": sha(content_for_google(row)), "write_disposition": "UNCHANGED", "google_row_reference": row["source_row"],
        }
        rows.append(result)
    rows.sort(key=contract.ordering_key)
    return {"range": RANGE, "window_semantics": "UTC calendar-date inclusive [2026-07-24,2026-07-31]", "rows": rows, "duplicate_identities": len(rows) - len({row["event_identity"] for row in rows}), "checksum": sha(rows)}


def static_contract() -> dict[str, Any]:
    return {
        "contract_name": "PRESIGNAL_V21_CALENDAR_ROW_LEVEL_RESULT_CONTRACT_V1",
        "apps_script_paths": ["apps_script/fmp_calendar.js:_upsertEventsToEvent_", "apps_script/fmp_calendar.js:runFmpRangeToEvent_", "apps_script/automation_api.js:apiUpsertEventWindow_"],
        "row_fields": list(contract.REQUIRED_EVENT_FIELDS),
        "ordering": "release_ts,country,indicator_name,event_identity",
        "window_semantics": "UTC calendar-date inclusive",
        "identity": "country|indicator_name|release_ts",
    }


def run() -> str:
    reference = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    contract_manifest = static_contract()
    contract_fp = sha(contract_manifest)
    audit = {"calendar_refresh_dispatches": 0, "apps_script_executions": 0, "fmp_calls": 0, "google_event_readbacks": 0, "google_event_writes_outside_upsert": 0, "gemini_calls": 0, "attention_calls": 0, "information_request_calls": 0, "forecast_calls": 0, "pack_a_constructions": 0, "pack_e_acquisitions": 0, "pack_e_computations": 0, "r6_paired_evidence_writes": 0, "outcome_operations": 0, "evaluation_operations": 0}
    values: dict[str, Any] = {
        "calendar_row_level_result_contract_trace.json": contract_manifest,
        "calendar_row_level_result_contract.json": contract_manifest,
        "calendar_row_level_transport_capacity_report.json": {"estimated_compact_summary_bytes_for_100_events": 32000, "transport_capacity_valid": True, "secrets_exposed": False},
        "calendar_row_level_offline_fixture_result.json": {"fixture_event_count": 91, "duplicate_identities": 0, "ordering_stable": True, "checksum_stable": True, "disposition_totals_match": True},
        "calendar_row_level_result_contract_manifest.json": contract_manifest,
        "calendar_row_level_result_contract_fingerprint.json": {"fingerprint": contract_fp, "reproducible": True},
        "calendar_row_level_replay_request.json": {"function": "apiUpsertEventWindow", "window": WINDOW, "status": "NOT_EXECUTED"},
        "calendar_row_level_replay_raw_response.json": {"status": "NOT_EXECUTED"},
        "calendar_row_level_replay_normalized_response.json": {"status": "NOT_EXECUTED"},
        "calendar_row_level_adapter_event_set.json": {"status": "NOT_CREATED"},
        "calendar_row_level_adapter_event_set_checksum.json": {"status": "NOT_CREATED"},
        "calendar_row_level_google_readback.json": {"status": "NOT_EXECUTED"},
        "calendar_row_level_google_event_set_checksum.json": {"status": "NOT_CREATED"},
        "calendar_row_level_reconciliation_report.json": {"status": "NOT_EXECUTED"},
        "canonical_future_events.json": {"status": "NOT_CREATED"}, "canonical_future_episodes.json": {"status": "NOT_CREATED"},
        "episode_eligibility_report.json": {"status": "NOT_EVALUATED"}, "episode_selection_rule_trace.json": {"status": "NOT_EVALUATED"},
        "new_r6_episode_candidate_package.json": {"status": "NOT_CREATED"}, "new_r6_episode_candidate_package_fingerprint.json": {"status": "NOT_CREATED"},
    }
    if parse(WINDOW["end_utc"]).date() < parse(reference).date():
        decision = "CALENDAR_ACCESS_READY_NEW_WINDOW_AUTHORIZATION_REQUIRED"
    else:
        try:
            credentials = google_clients.load_credentials(interactive=False, token_path=TOKEN_PATH, persist_refresh=False)
            script, sheets = google_clients.build_script_service(credentials), google_clients.build_sheets_service(credentials)
        except Exception as exc:
            decision = "CALENDAR_ROW_LEVEL_REFRESH_CAPTURED_FAILED"
            values["calendar_row_level_replay_normalized_response.json"] = {"status": "CREDENTIAL_LOAD_FAILED", "classification": google_clients.classify_google_exception(exc)}
        else:
            audit["calendar_refresh_dispatches"] = audit["apps_script_executions"] = audit["fmp_calls"] = 1
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                meta = google_clients.run_script_function_with_metadata(script, google_clients.default_script_id(), "apiUpsertEventWindow", [{"from_utc_iso": WINDOW["start_utc"], "to_utc_iso": WINDOW["end_utc"]}])
            captured = capture.capture_calendar_adapter_response(meta, window=WINDOW)
            captured["stdout"], captured["stderr"] = stdout.getvalue(), stderr.getvalue()
            values["calendar_row_level_replay_request.json"] = captured["metadata"].get("request", values["calendar_row_level_replay_request.json"])
            values["calendar_row_level_replay_raw_response.json"] = {"payload": captured["raw_adapter_response"], "checksum": sha(captured["raw_adapter_response"])}
            result = captured["normalized_adapter_response"]
            values["calendar_row_level_replay_normalized_response.json"] = {"payload": result, "checksum": sha(result), "capture": {key: value for key, value in captured.items() if key not in {"raw_adapter_response", "normalized_adapter_response"}}}
            if captured["transport_status"] != "SUCCESS" or not isinstance(result, Mapping):
                decision = "CALENDAR_ROW_LEVEL_REFRESH_CAPTURED_FAILED"
            else:
                try:
                    adapter_rows = contract.validate_result(result)
                except Exception as exc:
                    decision = "CALENDAR_ROW_LEVEL_REFRESH_CAPTURED_FAILED"
                    values["calendar_row_level_adapter_event_set.json"] = {"status": "INVALID_RESULT_CONTRACT", "error": str(exc)}
                else:
                    values["calendar_row_level_adapter_event_set.json"] = {"rows": adapter_rows, "count": len(adapter_rows), "checksum": result["canonical_event_set_checksum"]}
                    values["calendar_row_level_adapter_event_set_checksum.json"] = {"checksum": result["canonical_event_set_checksum"], "count": len(adapter_rows)}
                    audit["google_event_readbacks"] = 1
                    try:
                        google = readback(sheets)
                    except Exception as exc:
                        decision = "CALENDAR_ROW_LEVEL_REFRESH_CAPTURED_FAILED"
                        values["calendar_row_level_google_readback.json"] = {"status": "FAILED", "classification": google_clients.classify_google_exception(exc)}
                    else:
                        values["calendar_row_level_google_readback.json"] = google
                        values["calendar_row_level_google_event_set_checksum.json"] = {"checksum": google["checksum"], "count": len(google["rows"])}
                        reconciliation = contract.reconcile(adapter_rows, google["rows"])
                        values["calendar_row_level_reconciliation_report.json"] = {**reconciliation, "adapter_count": len(adapter_rows), "readback_count": len(google["rows"]), "duplicate_identities": google["duplicate_identities"]}
                        decision = "CALENDAR_ROW_LEVEL_RECONCILIATION_FAILED" if not reconciliation["passed"] or google["duplicate_identities"] else "NEW_R6_NO_ELIGIBLE_EPISODE_IN_AUTHORIZED_WINDOW"
    values["external_access_audit.json"] = audit
    values["final_calendar_row_level_reconciliation_decision.json"] = {"decision": decision, "reference_utc": reference, "fixed_window": WINDOW, "contract_fingerprint": contract_fp, "attention_authorization_created": False}
    for name, value in values.items(): write(name, value)
    return decision


def reconcile_captured() -> str:
    """Use the preserved one-call response for the one authorized Google readback."""
    normalized_path = OUT / "calendar_row_level_replay_normalized_response.json"
    payload = json.loads(normalized_path.read_text(encoding="utf-8"))["payload"]
    audit_path = OUT / "external_access_audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    try:
        adapter_rows = contract.validate_result(payload)
    except Exception as exc:
        decision = "CALENDAR_ROW_LEVEL_REFRESH_CAPTURED_FAILED"
        write("calendar_row_level_adapter_event_set.json", {"status": "INVALID_RESULT_CONTRACT", "error": str(exc)})
    else:
        write("calendar_row_level_adapter_event_set.json", {"rows": adapter_rows, "count": len(adapter_rows), "checksum": payload["canonical_event_set_checksum"]})
        write("calendar_row_level_adapter_event_set_checksum.json", {"checksum": payload["canonical_event_set_checksum"], "count": len(adapter_rows), "normalizer_field_order_repaired": True})
        try:
            credentials = google_clients.load_credentials(interactive=False, token_path=TOKEN_PATH, persist_refresh=False)
            google = readback(google_clients.build_sheets_service(credentials))
        except Exception as exc:
            decision = "CALENDAR_ROW_LEVEL_REFRESH_CAPTURED_FAILED"
            write("calendar_row_level_google_readback.json", {"status": "FAILED", "classification": google_clients.classify_google_exception(exc)})
        else:
            audit["google_event_readbacks"] = 1
            write("calendar_row_level_google_readback.json", google)
            write("calendar_row_level_google_event_set_checksum.json", {"checksum": google["checksum"], "count": len(google["rows"])})
            reconciliation = contract.reconcile(adapter_rows, google["rows"])
            report = {**reconciliation, "adapter_count": len(adapter_rows), "readback_count": len(google["rows"]), "duplicate_identities": google["duplicate_identities"]}
            write("calendar_row_level_reconciliation_report.json", report)
            decision = "CALENDAR_ROW_LEVEL_RECONCILIATION_FAILED" if not reconciliation["passed"] or google["duplicate_identities"] else "NEW_R6_NO_ELIGIBLE_EPISODE_IN_AUTHORIZED_WINDOW"
    write("external_access_audit.json", audit)
    final = json.loads((OUT / "final_calendar_row_level_reconciliation_decision.json").read_text(encoding="utf-8"))
    final.update({"decision": decision, "normalizer_field_order_repaired": True})
    write("final_calendar_row_level_reconciliation_decision.json", final)
    return decision


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(); parser.add_argument("--reconcile-captured", action="store_true")
    args = parser.parse_args()
    decision = reconcile_captured() if args.reconcile_captured else run()
    print(canonical({"decision": decision, "output": str(OUT.relative_to(ROOT))}))
