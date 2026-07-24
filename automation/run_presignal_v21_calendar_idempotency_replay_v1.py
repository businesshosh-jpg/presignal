"""One bounded, captured replay of the fixed R6 FMP/Event refresh window.

The live branch is deliberately reachable only after the local identity proof
passes.  It performs no provider, forecast, Pack, or outcome work.
"""
from __future__ import annotations

import argparse
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
from automation import presignal_v21_calendar_idempotency_replay_v1 as replay
from automation import presignal_v21_prospective_episode_refresh_v1 as episode_refresh


OUT = ROOT / "outputs" / "presignal_v21_designed_drift_r6_calendar_idempotency_replay" / "R6-CALENDAR-IDEMPOTENCY-REPLAY-20260724-v1"
WINDOW = {"start_utc": "2026-07-24T00:00:00Z", "end_utc": "2026-07-31T00:00:00Z"}
SPREADSHEET_ID = "1_gZGnd6h3VzdiBvGBHRSxn78KW8tsOi2UEc6Y_Sc23Q"
TOKEN_PATH = Path("/Users/junhoshino/projects/presignal/local/token.json")
READBACK_RANGE = "Event!A4345:U4445"
EVENT_HEADERS = [
    "object", "country", "indicator_name", "genre", "importance", "type", "event_id", "batch_id", "release_ts",
    "source_cal", "consensus_value", "prev_revision", "released_value", "released_ts", "source_provider",
    "source_series_id", "transform", "release_status", "notes", "resolution_method", "confidence_level",
]
FREEZE = "sha256:8c910a343515d88ca63ce4aaf738f28f9b4a8ab22665397077858bfaf7e866e4"
REQUEST_BINDING = {
    "prompt_version": "presignal_v21_information_request_prompt_v2",
    "prompt_checksum": "sha256:219b3d33989d06b5f1968f6024c0135454320cf6c8f545116c6595d630011cb5",
    "category_enum_checksum": "sha256:320dad35692df096ea54466c17a8f02cff6287899aa3b7755dea00d7362bfb52",
    "temporal_alignment_fingerprint": "sha256:d557c0733cc59982c46f71efaa89dad03a27e0d0c6023ba54eb2ef807c84c570",
    "old_pmi_attention_reused": False,
    "old_pmi_request_responses_reused": False,
}
CLOSED_PMI = "EP_BATCH_0b3bf1cac3c02da74063"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical(value) + "\n", encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def upsert_identity_trace() -> dict[str, Any]:
    return {
        "route": "runFmpRangeToEvent_ -> _upsertEventsToEvent_ -> applyBatchingForKeys_",
        "source_path": "apps_script/fmp_calendar.js:_upsertEventsToEvent_",
        "canonical_event_identity_key": "country|indicator_name|release_ts",
        "source_event_identity_key": "FMP normalized country|indicator_name|release_ts; FMP source id is not used by this writer lookup",
        "release_time_participation": "release_ts is required and participates in the upsert key",
        "existing_row_lookup": "existingByKey[key] = row index; same key updates that row",
        "same_event_replay_behavior": "UPDATE_EXISTING at writer level; semantic content is UNCHANGED when normalized values are identical",
        "changed_content_replay_behavior": "UPDATE_EXISTING using the same country|indicator_name|release_ts lookup key",
        "duplicate_prevention_rule": "append only when the lookup key is absent; offline proof fail-closes if the pre-state already has duplicate keys",
        "postpass_identity": "apps_script/runner_rules_patch.js:applyBatchingForKeys_ deterministically assigns event_id/type/batch_id from country, UTC minute, and indicator_name",
        "row_selection_rule": "unique existing key required; a duplicate pre-state is an ambiguity and is not replay-safe",
    }


def safe_token_metadata() -> dict[str, Any]:
    if not TOKEN_PATH.exists():
        return {"exists": False, "path_reference": "local/token.json", "checksum": None, "size": None}
    return {
        "exists": True,
        "path_reference": "local/token.json (existing authorized parent worktree binding)",
        "checksum": "sha256:" + hashlib.sha256(TOKEN_PATH.read_bytes()).hexdigest(),
        "size": TOKEN_PATH.stat().st_size,
    }


def probe(service: Any) -> dict[str, Any]:
    try:
        response = service.spreadsheets().get(
            spreadsheetId=SPREADSHEET_ID,
            fields="spreadsheetId,properties.title",
        ).execute()
    except Exception as exc:
        return {"attempted": True, "probe_type": "bounded_workbook_metadata", "status": "FAILED", "classification": google_clients.classify_google_exception(exc), "scientific_writes": 0}
    return {
        "attempted": True,
        "probe_type": "bounded_workbook_metadata",
        "status": "OK",
        "spreadsheet_id_match": response.get("spreadsheetId") == SPREADSHEET_ID,
        "workbook_title": response.get("properties", {}).get("title"),
        "scientific_writes": 0,
    }


def readback_rows(service: Any) -> dict[str, Any]:
    try:
        response = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=READBACK_RANGE,
            valueRenderOption="UNFORMATTED_VALUE",
            dateTimeRenderOption="SERIAL_NUMBER",
        ).execute()
    except Exception as exc:
        return {"status": "FAILED", "range": READBACK_RANGE, "classification": google_clients.classify_google_exception(exc), "rows": []}
    all_rows = response.get("values", [])
    mapped = []
    for offset, values in enumerate(all_rows):
        if not any(str(value) for value in values):
            continue
        # The accepted Event sheet has a legacy leading cell before the
        # append-only canonical headers.  Read it but do not treat it as a
        # scientific Event field.
        aligned = list(values)[1:]
        row = dict(zip(EVENT_HEADERS, aligned + [""] * (len(EVENT_HEADERS) - len(aligned))))
        row["source_row"] = 4345 + offset
        mapped.append(row)
    return {"status": "OK", "range": READBACK_RANGE, "rows": mapped, "raw_rows_read": len(all_rows), "header_alignment": "legacy_leading_column_ignored", "checksum": sha(mapped)}


def realign_captured_rows(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Repair only the local interpretation of an already-read legacy row."""
    repaired = []
    for raw in rows:
        values = [raw.get(header, "") for header in EVENT_HEADERS]
        if values[1] == "econ_event":
            values = values[1:] + [""]
        row = dict(zip(EVENT_HEADERS, values))
        row["source_row"] = raw.get("source_row")
        repaired.append(row)
    return repaired


def window_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected, rejected = [], []
    start, end = parse_utc(WINDOW["start_utc"]), parse_utc(WINDOW["end_utc"])
    for row in rows:
        try:
            timestamp = episode_refresh.episodes.utc_timestamp(row.get("release_ts"))
            in_window = start <= parse_utc(timestamp) <= end
        except Exception:
            rejected.append({"source_row": row["source_row"], "classification": "INVALID_RELEASE_TIMESTAMP"})
            continue
        if in_window:
            selected.append(row)
    return selected, rejected


def candidate_artifacts(rows: list[dict[str, Any]], *, reference_utc: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], str]:
    events, event_rejected = episode_refresh.canonical_events(rows, window_start_utc=WINDOW["start_utc"], window_end_utc=WINDOW["end_utc"])
    runs = [episode_refresh.construct_episodes(events, as_of_utc=reference_utc) for _ in range(3)]
    episodes, dispositions = runs[0]
    if any(canonical(run) != canonical(runs[0]) for run in runs[1:]):
        raise RuntimeError("EPISODE_CONSTRUCTION_NONDETERMINISTIC")
    excluded, eligible = [], []
    for item in episodes:
        if item["episode_id"] == CLOSED_PMI:
            excluded.append({"episode_identity": item["episode_id"], "reason": "CLOSED_PMI_EPISODE"})
        elif item["eligibility"] != "ELIGIBLE_UPCOMING":
            excluded.append({"episode_identity": item["episode_id"], "reason": item["eligibility"]})
        else:
            eligible.append(item)
    decision = episode_refresh.candidate_decision(eligible)
    rule = {
        "existing_authoritative_rule_found": True,
        "rule_path": "automation/presignal_v21_prospective_episode_refresh_v1.py:candidate_decision",
        "rule_result": decision["selection_rule"],
        "unique_candidate_selected": decision["selected_candidate"] is not None,
        "invented_tie_breaker": False,
    }
    event_artifact = {"status": "CREATED", "events": events, "rejected": event_rejected, "checksum": sha(events)}
    episode_artifact = {"status": "CREATED", "episodes": episodes, "dispositions": dispositions, "checksum": sha(episodes)}
    eligibility = {
        "eligible_episode_count": len(eligible), "excluded_episode_count": len(excluded), "closed_pmi_episode_excluded": CLOSED_PMI,
        "eligible_episodes": eligible, "excluded_episodes": excluded,
        "lineage_failures": sum(1 for item in dispositions if item["disposition"] != "CONSUMED"),
    }
    package = {
        "package_name": "PRESIGNAL_V21_DESIGNED_DRIFT_2_NEW_R6_EPISODE_CANDIDATE_PACKAGE_V1",
        "route_b_freeze_fingerprint": FREEZE,
        "calendar_source_identity": "FMP_ECONOMIC_CALENDAR",
        "refresh_window": WINDOW,
        "frozen_reference_timestamp": reference_utc,
        "canonical_event_set_checksum": event_artifact["checksum"],
        "canonical_episode_set_checksum": episode_artifact["checksum"],
        "eligible_candidate_identities": [item["episode_id"] for item in eligible],
        "excluded_candidate_identities_and_reasons": excluded,
        "selection_rule_status": decision["decision"],
        "recommended_candidate": None,
        **REQUEST_BINDING,
    }
    return event_artifact, episode_artifact, eligibility, {"decision": decision, "rule": rule, "package": package}, sha(package)


def not_executed(reason: str) -> dict[str, Any]:
    return {"status": "NOT_EXECUTED", "reason": reason}


def run(*, output: Path, execute: bool) -> str:
    reference_utc = utc_now()
    proof = replay.offline_replay_proof()
    trace = upsert_identity_trace()
    contract = {
        "classification": "CALENDAR_REFRESH_IDEMPOTENT_REPLAY_SAFE" if proof["passed"] else "CALENDAR_REFRESH_IDEMPOTENCY_UNRESOLVED",
        "identity_trace_checksum": sha(trace),
        "offline_proof_checksum": sha(proof),
        "identical_replay_can_duplicate": False if proof["passed"] else None,
        "preexisting_duplicate_key_behavior": "FAIL_CLOSED",
        "changed_content_behavior": "UPDATE_EXISTING",
    }
    files: dict[str, Any] = {
        "calendar_upsert_identity_trace.json": trace,
        "calendar_idempotency_contract.json": contract,
        "calendar_offline_replay_proof.json": proof,
        "calendar_replay_safety_decision.json": {"classification": contract["classification"], "new_dispatch_authorized": proof["passed"], "reason": "identical replay has zero duplicate canonical rows in the exact lookup-key simulation" if proof["passed"] else "offline proof failed"},
        "calendar_authentication_probe.json": not_executed("LIVE_REPLAY_NOT_STARTED"),
        "calendar_replay_request.json": {"window": WINDOW, "function": "apiUpsertEventWindow", "parameters": [{"from_utc_iso": WINDOW["start_utc"], "to_utc_iso": WINDOW["end_utc"]}], "status": "NOT_EXECUTED"},
        "calendar_replay_raw_response.json": not_executed("LIVE_REPLAY_NOT_STARTED"),
        "calendar_replay_normalized_response.json": not_executed("LIVE_REPLAY_NOT_STARTED"),
        "calendar_replay_execution_report.json": not_executed("LIVE_REPLAY_NOT_STARTED"),
        "calendar_event_readback.json": not_executed("LIVE_REPLAY_NOT_STARTED"),
        "calendar_event_reconciliation.json": not_executed("LIVE_REPLAY_NOT_STARTED"),
        "canonical_future_events.json": {"status": "NOT_CREATED"},
        "canonical_future_episodes.json": {"status": "NOT_CREATED"},
        "episode_eligibility_report.json": {"status": "NOT_EVALUATED"},
        "episode_selection_rule_trace.json": {"status": "NOT_EVALUATED"},
        "new_r6_episode_candidate_package.json": {"status": "NOT_CREATED"},
        "new_r6_episode_candidate_package_fingerprint.json": {"status": "NOT_CREATED"},
    }
    audit = {"authentication_probes": 0, "calendar_refresh_dispatches": 0, "apps_script_executions": 0, "fmp_calls": 0, "google_event_readbacks": 0, "google_event_writes": 0, "gemini_calls": 0, "attention_calls": 0, "information_request_calls": 0, "forecast_calls": 0, "pack_a_constructions": 0, "pack_e_acquisitions": 0, "pack_e_computations": 0, "r6_paired_evidence_writes": 0, "outcome_operations": 0, "evaluation_operations": 0}

    if not proof["passed"]:
        decision = "CALENDAR_REFRESH_REPLAY_BLOCKED_IDEMPOTENCY_UNRESOLVED"
    elif parse_utc(WINDOW["end_utc"]) <= parse_utc(reference_utc):
        decision = "CALENDAR_ACCESS_READY_NEW_WINDOW_AUTHORIZATION_REQUIRED"
    elif not execute:
        decision = "CALENDAR_REFRESH_REPLAY_BLOCKED_IDEMPOTENCY_UNRESOLVED"
        files["calendar_replay_safety_decision.json"]["reason"] = "live replay was not requested"
    else:
        token = safe_token_metadata()
        if not token["exists"]:
            decision = "CALENDAR_REFRESH_CAPTURED_FAILED"
            files["calendar_authentication_probe.json"] = {"attempted": False, "status": "FAILED", "reason": "EXPECTED_TOKEN_FILE_NOT_FOUND", "credential": token}
        else:
            try:
                credentials = google_clients.load_credentials(interactive=False, token_path=TOKEN_PATH, persist_refresh=False)
                sheets = google_clients.build_sheets_service(credentials)
                script = google_clients.build_script_service(credentials)
            except Exception as exc:
                decision = "CALENDAR_REFRESH_CAPTURED_FAILED"
                files["calendar_authentication_probe.json"] = {"attempted": False, "status": "FAILED", "credential": token, "classification": google_clients.classify_google_exception(exc)}
            else:
                audit["authentication_probes"] = 1
                files["calendar_authentication_probe.json"] = {**probe(sheets), "credential": token}
                if files["calendar_authentication_probe.json"]["status"] != "OK":
                    decision = "CALENDAR_REFRESH_CAPTURED_FAILED"
                else:
                    audit["calendar_refresh_dispatches"] = 1
                    audit["apps_script_executions"] = 1
                    raw_stdout, raw_stderr = io.StringIO(), io.StringIO()
                    with contextlib.redirect_stdout(raw_stdout), contextlib.redirect_stderr(raw_stderr):
                        metadata = google_clients.run_script_function_with_metadata(
                            script, google_clients.default_script_id(), "apiUpsertEventWindow",
                            [{"from_utc_iso": WINDOW["start_utc"], "to_utc_iso": WINDOW["end_utc"]}],
                        )
                    captured = replay.capture_calendar_adapter_response(metadata, window=WINDOW)
                    captured["stdout"] = raw_stdout.getvalue()
                    captured["stderr"] = raw_stderr.getvalue()
                    files["calendar_replay_request.json"] = captured["metadata"].get("request", files["calendar_replay_request.json"])
                    files["calendar_replay_raw_response.json"] = {"response": captured["raw_adapter_response"], "checksum": sha(captured["raw_adapter_response"]), "transport_status": captured["transport_status"]}
                    files["calendar_replay_normalized_response.json"] = {"response": captured["normalized_adapter_response"], "checksum": sha(captured["normalized_adapter_response"]), "execution_status": captured["execution_status"]}
                    files["calendar_replay_execution_report.json"] = captured
                    if captured["transport_status"] != "SUCCESS" or not isinstance(captured["normalized_adapter_response"], Mapping):
                        decision = "CALENDAR_REFRESH_CAPTURED_FAILED"
                    else:
                        result = dict(captured["normalized_adapter_response"])
                        upsert = dict(result.get("upsert") or {})
                        audit["fmp_calls"] = 1
                        audit["google_event_writes"] = int(upsert.get("appended") or 0) + int(upsert.get("upserts") or 0)
                        audit["google_event_readbacks"] = 1
                        readback = readback_rows(sheets)
                        files["calendar_event_readback.json"] = readback
                        if readback["status"] != "OK":
                            decision = "CALENDAR_REFRESH_CAPTURED_FAILED"
                        else:
                            in_window, invalid_rows = window_rows(readback["rows"])
                            adapter_count = upsert.get("fetched")
                            reconciliation = {
                                "status": "PASS" if adapter_count == len(in_window) and not invalid_rows else "FAIL",
                                "adapter_reported_canonical_event_count": adapter_count,
                                "bounded_readback_window_event_count": len(in_window),
                                "invalid_readback_rows": invalid_rows,
                                "duplicate_upsert_keys": len(in_window) - len({replay.event_upsert_key(row) for row in in_window}),
                                "readback_checksum": sha(in_window),
                            }
                            files["calendar_event_reconciliation.json"] = reconciliation
                            if reconciliation["status"] != "PASS" or reconciliation["duplicate_upsert_keys"]:
                                decision = "CALENDAR_REFRESH_CAPTURED_FAILED"
                            else:
                                event_out, episode_out, eligibility, candidate_out, package_fp = candidate_artifacts(in_window, reference_utc=reference_utc)
                                files["canonical_future_events.json"] = event_out
                                files["canonical_future_episodes.json"] = episode_out
                                files["episode_eligibility_report.json"] = eligibility
                                files["episode_selection_rule_trace.json"] = candidate_out["rule"]
                                files["new_r6_episode_candidate_package.json"] = candidate_out["package"]
                                files["new_r6_episode_candidate_package_fingerprint.json"] = {"package_name": candidate_out["package"]["package_name"], "package_fingerprint": package_fp, "reproducible": True}
                                if not eligibility["eligible_episode_count"]:
                                    decision = "NEW_R6_NO_ELIGIBLE_EPISODE_IN_AUTHORIZED_WINDOW"
                                elif candidate_out["decision"]["selected_candidate"] is None:
                                    decision = "NEW_R6_EPISODE_CANDIDATES_READY_USER_SELECTION_REQUIRED"
                                else:
                                    decision = "NEW_R6_EPISODE_DETERMINISTICALLY_SELECTED_ATTENTION_AUTHORIZATION_READY"

    files["external_access_audit.json"] = audit
    files["final_calendar_idempotency_and_replay_decision.json"] = {"decision": decision, "reference_utc": reference_utc, "fixed_window": WINDOW, "idempotency_classification": contract["classification"], "attention_authorization_created": False}
    for name, value in files.items():
        write_json(output / name, value)
    return decision


def reconcile_captured(output: Path) -> str:
    """Offline-only completion of the captured replay after reader alignment repair."""
    readback_path = output / "calendar_event_readback.json"
    normalized_path = output / "calendar_replay_normalized_response.json"
    readback = json.loads(readback_path.read_text(encoding="utf-8"))
    normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
    rows = realign_captured_rows(list(readback.get("rows") or []))
    in_window, invalid_rows = window_rows(rows)
    result = dict(normalized.get("response") or {})
    upsert = dict(result.get("upsert") or {})
    reconciliation = {
        "status": "PASS" if upsert.get("fetched") == len(in_window) and not invalid_rows else "FAIL",
        "adapter_reported_canonical_event_count": upsert.get("fetched"),
        "bounded_readback_window_event_count": len(in_window),
        "invalid_readback_rows": invalid_rows,
        "duplicate_upsert_keys": len(in_window) - len({replay.event_upsert_key(row) for row in in_window}),
        "readback_checksum": sha(in_window),
        "header_alignment_repair": "legacy_leading_column_ignored; no external read or write was repeated",
    }
    repaired_readback = {**readback, "rows": rows, "header_alignment": "legacy_leading_column_ignored", "checksum": sha(rows)}
    write_json(readback_path, repaired_readback)
    write_json(output / "calendar_event_reconciliation.json", reconciliation)
    if reconciliation["status"] != "PASS" or reconciliation["duplicate_upsert_keys"]:
        decision = "CALENDAR_REFRESH_CAPTURED_FAILED"
    else:
        reference = json.loads((output / "final_calendar_idempotency_and_replay_decision.json").read_text(encoding="utf-8"))["reference_utc"]
        event_out, episode_out, eligibility, candidate_out, package_fp = candidate_artifacts(in_window, reference_utc=reference)
        write_json(output / "canonical_future_events.json", event_out)
        write_json(output / "canonical_future_episodes.json", episode_out)
        write_json(output / "episode_eligibility_report.json", eligibility)
        write_json(output / "episode_selection_rule_trace.json", candidate_out["rule"])
        write_json(output / "new_r6_episode_candidate_package.json", candidate_out["package"])
        write_json(output / "new_r6_episode_candidate_package_fingerprint.json", {"package_name": candidate_out["package"]["package_name"], "package_fingerprint": package_fp, "reproducible": True})
        if not eligibility["eligible_episode_count"]:
            decision = "NEW_R6_NO_ELIGIBLE_EPISODE_IN_AUTHORIZED_WINDOW"
        elif candidate_out["decision"]["selected_candidate"] is None:
            decision = "NEW_R6_EPISODE_CANDIDATES_READY_USER_SELECTION_REQUIRED"
        else:
            decision = "NEW_R6_EPISODE_DETERMINISTICALLY_SELECTED_ATTENTION_AUTHORIZATION_READY"
    final = json.loads((output / "final_calendar_idempotency_and_replay_decision.json").read_text(encoding="utf-8"))
    final.update({"decision": decision, "offline_reconciliation_repaired": True})
    write_json(output / "final_calendar_idempotency_and_replay_decision.json", final)
    return decision


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--reconcile-captured", action="store_true")
    args = parser.parse_args()
    try:
        output_reference = str(args.output.relative_to(ROOT))
    except ValueError:
        output_reference = str(args.output)
    decision = reconcile_captured(args.output) if args.reconcile_captured else run(output=args.output, execute=args.execute)
    print(canonical({"decision": decision, "output": output_reference}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
