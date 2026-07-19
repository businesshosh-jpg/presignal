#!/usr/bin/env python3
"""Preserve only provable v2 Session Attention Map evidence.

This utility is intentionally fail-closed.  It inventories the frozen replay
package and the archived v2 capture implementation, but exports rows only from
a dedicated Session_Attention_Map artifact whose full identity lineage is
present.  It never calls providers, Google APIs, or the historical builder.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tarfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.google_clients import build_sheets_service, get_sheet_values, load_credentials

OUTPUT = ROOT / "outputs" / "presignal_v21_attention_preservation"
PACKAGE = (
    ROOT
    / "outputs"
    / "simplified_authoritative_replay"
    / "production_packages"
    / "SIMPLIFIED-REPLAY-PROD-20260718T010455Z"
)
RUN = (
    ROOT
    / "outputs"
    / "simplified_authoritative_replay"
    / "runs"
    / "SIMPLIFIED-REPLAY-AUTHORITATIVE-20260718T010455Z"
)
HISTORICAL_CAPTURE_COMMIT = "e5a0ff288eb1f6fc228936cb1c693ed2bb2ab80f"
HISTORICAL_CAPTURE_PATH = "automation/build_session_attention_map_v0.py"
ALLOWED_LABELS = {
    "PRIMARY_DRIVER",
    "SECONDARY_DRIVER",
    "WATCHLIST",
    "CONTEXT_ONLY",
    "IGNORE",
    "NO_SIGNAL",
}
REQUIRED_LINEAGE = {
    "session_id",
    "provider",
    "model",
    "event_id",
    "attention_label",
    "attention_run_id",
    "forecast_cutoff_ts",
    "raw_output",
}
GOOGLE_SPREADSHEET_ID = "1jxcZotbzJKcAzrK0VhxetYX6hp5DPXCCIA0J6B6RUy0"
GOOGLE_WORKSHEET_NAME = "Session_Attention_Map_History"
REQUESTED_GOOGLE_WORKSHEET_GID = 1865169058
# The supplied URL GID resolves to Market_Sessions.  This is the verified GID
# of the explicitly named historical Attention worksheet in that spreadsheet.
GOOGLE_WORKSHEET_GID = 1528972154
GOOGLE_SPREADSHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    + GOOGLE_SPREADSHEET_ID
    + "/edit?gid=1528972154#gid=1528972154"
)
GOOGLE_REQUIRED_HEADERS = {
    "history_capture_ts", "replay_id", "source_sheet", "source_row_hash", "capture_phase",
    "capture_status", "generated_ts", "attention_run_id", "session_id", "provider", "model",
    "event_id", "attention_label", "raw_output", "status", "error_message",
    "source_session_sheet", "source_member_sheet",
}
GOOGLE_ALLOWED_STATUSES = {"parsed", "provider_contract_error", "provider_omitted_event"}


class PreservationError(ValueError):
    """Raised when an alleged Attention artifact cannot be proven exact."""


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_show(commit: str, path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT)


def candidate(
    *,
    source_path: str,
    source_type: str,
    source_commit: str,
    source_run_id: str,
    source_file_hash: str,
    candidate_object_type: str,
    dedicated: bool,
    session: bool,
    provider: bool,
    model: bool,
    cutoff: bool,
    raw: bool,
    parser: bool,
    accepted: bool,
    reason: str,
    decision: str,
) -> dict[str, Any]:
    return {
        "source_path": source_path,
        "source_type": source_type,
        "source_commit": source_commit,
        "source_run_id": source_run_id,
        "source_file_hash": source_file_hash,
        "candidate_object_type": candidate_object_type,
        "dedicated_attention_capture_proven": dedicated,
        "session_binding_proven": session,
        "provider_binding_proven": provider,
        "model_binding_proven": model,
        "cutoff_binding_proven": cutoff,
        "raw_lineage_available": raw,
        "parser_or_schema_available": parser,
        "accepted_or_rejected": "ACCEPTED" if accepted else "REJECTED",
        "rejection_reason": reason,
        "source_decision": decision,
    }


def inspect_sources(package: Path = PACKAGE, run: Path = RUN) -> list[dict[str, Any]]:
    """Return a deterministic inventory without consulting any external system."""
    manifest = json.loads((package / "package_manifest.json").read_text())
    package_commit = manifest["local_git_repository_binding"]["git_commit"]
    package_run = manifest["package_id"]
    files = manifest["files"]
    inventory = []
    for package_manifest in sorted(package.parent.glob("*/package_manifest.json")):
        historical_manifest = json.loads(package_manifest.read_text())
        historical_files = historical_manifest.get("files", {})
        inventory.append(candidate(
            source_path=str(package_manifest),
            source_type="frozen_authoritative_package_manifest",
            source_commit=historical_manifest.get("local_git_repository_binding", {}).get("git_commit", ""),
            source_run_id=historical_manifest.get("package_id", package_manifest.parent.name),
            source_file_hash=sha256_path(package_manifest),
            candidate_object_type="FROZEN_REPLAY_PACKAGE_MANIFEST",
            dedicated=False, session=False, provider=False, model=False, cutoff=False,
            raw=False, parser=False, accepted=False,
            reason=("No authoritative_attention_map artifact is listed in the immutable package manifest."
                    if not any("attention" in name.lower() for name in historical_files)
                    else "Attention-named package artifact requires targeted source validation."),
            decision="INSUFFICIENT_LINEAGE",
        ))
    inventory.extend([
        candidate(
            source_path=str(package / "snapshot" / "authoritative_requests.jsonl"),
            source_type="frozen_information_request_snapshot",
            source_commit=package_commit,
            source_run_id=package_run,
            source_file_hash=files["snapshot/authoritative_requests.jsonl"],
            candidate_object_type="INFORMATION_REQUEST_WITH_LINKED_ATTENTION_LABELS",
            dedicated=False, session=True, provider=True, model=True, cutoff=True,
            raw=True, parser=False, accepted=False,
            reason="Request-linked attention labels are request metadata, not records from the dedicated Session Attention Map capture path.",
            decision="NON_AUTHORITATIVE_ATTENTION_LIKE_METADATA",
        ),
        candidate(
            source_path=str(run / "ledgers" / "accepted_predictions"),
            source_type="frozen_accepted_prediction_ledgers",
            source_commit=package_commit,
            source_run_id=run.name,
            source_file_hash=fingerprint(sorted(path.name for path in (run / "ledgers" / "accepted_predictions").glob("*.json"))),
            candidate_object_type="PREDICTION_PRIMARY_SECONDARY_DRIVER_SUMMARIES",
            dedicated=False, session=True, provider=True, model=True, cutoff=True,
            raw=True, parser=False, accepted=False,
            reason="Prediction driver summaries and rationales are forecast outputs, not Session Attention Map records.",
            decision="NON_AUTHORITATIVE_ATTENTION_LIKE_METADATA",
        ),
        candidate(
            source_path=f"git:{HISTORICAL_CAPTURE_COMMIT}:{HISTORICAL_CAPTURE_PATH}",
            source_type="historical_dedicated_attention_capture_implementation",
            source_commit=HISTORICAL_CAPTURE_COMMIT,
            source_run_id="",
            source_file_hash=hashlib.sha256(git_show(HISTORICAL_CAPTURE_COMMIT, HISTORICAL_CAPTURE_PATH)).hexdigest(),
            candidate_object_type="SESSION_ATTENTION_MAP_CAPTURE_IMPLEMENTATION",
            dedicated=True, session=False, provider=False, model=False, cutoff=False,
            raw=False, parser=True, accepted=False,
            reason="The dedicated builder and parser survive, but no immutable exported rows, raw responses, or run manifest survive in Git.",
            decision="INSUFFICIENT_LINEAGE",
        ),
    ])
    archive_dir = package.parents[1] / "checkpoints"
    for archive in sorted(archive_dir.glob("*.tar.gz")):
        with tarfile.open(archive, "r:gz") as archive_file:
            contains_attention = any("attention" in name.lower() for name in archive_file.getnames())
        inventory.append(candidate(
            source_path=str(archive), source_type="frozen_checkpoint_archive", source_commit=package_commit,
            source_run_id=package_run, source_file_hash=sha256_path(archive),
            candidate_object_type="FROZEN_REPLAY_ARCHIVE", dedicated=False, session=False, provider=False,
            model=False, cutoff=False, raw=False, parser=False, accepted=False,
            reason=("The checkpoint archive contains no Session Attention Map artifact."
                    if not contains_attention else "Attention-named checkpoint member requires targeted source validation."),
            decision="INSUFFICIENT_LINEAGE",
        ))
    return sorted(inventory, key=lambda row: (row["source_path"], row["source_type"]))


def validate_attention_record(record: Mapping[str, Any]) -> None:
    """Enforce the original capture identity before a preservation export."""
    if record.get("source_object") != "session_attention_map":
        raise PreservationError("SOURCE_NOT_DEDICATED_SESSION_ATTENTION_MAP")
    missing = sorted(key for key in REQUIRED_LINEAGE if not record.get(key))
    if missing:
        raise PreservationError("MISSING_REQUIRED_LINEAGE:" + ",".join(missing))
    if record["attention_label"] not in ALLOWED_LABELS:
        raise PreservationError("UNKNOWN_ATTENTION_LABEL")
    try:
        datetime.fromisoformat(str(record["forecast_cutoff_ts"]).replace("Z", "+00:00"))
    except ValueError as exc:
        raise PreservationError("INVALID_FORECAST_CUTOFF") from exc
    rank = record.get("attention_rank")
    if rank not in (None, "") and (not isinstance(rank, int) or rank <= 0):
        raise PreservationError("INVALID_ATTENTION_RANK")
    confidence = record.get("confidence")
    if confidence not in (None, "") and (not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1):
        raise PreservationError("INVALID_ATTENTION_CONFIDENCE")


def export_records(records: Iterable[Mapping[str, Any]], output: Path) -> dict[str, Any]:
    """Write a canonical export when, and only when, every row is exact."""
    accepted = [dict(row) for row in records]
    for row in accepted:
        validate_attention_record(row)
    identities = [tuple(row[key] for key in ("session_id", "provider", "model", "event_id", "attention_run_id")) for row in accepted]
    if len(identities) != len(set(identities)):
        raise PreservationError("DUPLICATE_ATTENTION_IDENTITY")
    accepted.sort(key=lambda row: tuple(str(row[key]) for key in ("session_id", "provider", "model", "event_id", "attention_run_id")))
    output.mkdir(parents=True, exist_ok=True)
    payload = "".join(canonical(row) + "\n" for row in accepted)
    (output / "authoritative_attention_map.jsonl").write_text(payload)
    export_fingerprint = fingerprint(accepted)
    manifest = {"export_status": "AUTHORITATIVE_ATTENTION_SOURCE", "record_count": len(accepted), "export_fingerprint": export_fingerprint}
    (output / "authoritative_attention_map_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    (output / "authoritative_attention_map_reconciliation.json").write_text(json.dumps({"accepted_exported_records": len(accepted), "provider_error_records": 0, "explicit_source_omissions": 0, "governed_unavailable_records": 0, "planned_population_manifest_available": False}, indent=2, sort_keys=True) + "\n")
    (output / "authoritative_attention_map_unavailable_ledger.jsonl").write_text("")
    return manifest


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def normalize_google_values(values: list[list[Any]]) -> tuple[list[str], list[dict[str, str]]]:
    if not values:
        raise PreservationError("EMPTY_GOOGLE_WORKSHEET")
    headers = [str(value).strip() for value in values[0]]
    if len(headers) != len(set(headers)):
        raise PreservationError("DUPLICATE_GOOGLE_HEADERS")
    missing = sorted(GOOGLE_REQUIRED_HEADERS - set(headers))
    if missing:
        raise PreservationError("MISSING_GOOGLE_HEADERS:" + ",".join(missing))
    rows = []
    for source_row in values[1:]:
        padded = list(source_row) + [""] * (len(headers) - len(source_row))
        row = {header: "" if value is None else str(value) for header, value in zip(headers, padded)}
        if any(value.strip() for value in row.values()):
            rows.append(row)
    return headers, rows


def google_content_fingerprint(headers: list[str], rows: Iterable[Mapping[str, str]]) -> str:
    normalized = sorted(({header: str(row.get(header, "")) for header in headers} for row in rows), key=canonical)
    return fingerprint({"headers": headers, "rows": normalized})


def strip_json_fence(raw_output: str) -> str:
    value = raw_output.strip()
    if value.startswith("```json"):
        value = value[len("```json"):].strip()
    if value.startswith("```"):
        value = value[3:].strip()
    if value.endswith("```"):
        value = value[:-3].strip()
    return value


def parse_raw_attention(raw_output: str) -> dict[str, Any] | None:
    try:
        value = json.loads(strip_json_fence(raw_output))
    except (TypeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def historical_state(package: Path = PACKAGE) -> dict[str, Any]:
    """Read the verified frozen snapshot used to prove historical cutoff lineage."""
    from automation.build_simplified_replay_package_v1 import verify_package_manifest, verify_whole_package_fingerprint

    if not verify_package_manifest(package) or not verify_whole_package_fingerprint(package):
        raise PreservationError("FROZEN_PACKAGE_FINGERPRINT_MISMATCH")
    sessions = {row["session_id"]: row for row in read_jsonl(package / "snapshot" / "authoritative_sessions.jsonl")}
    members: dict[str, set[str]] = {}
    for row in read_jsonl(package / "snapshot" / "authoritative_session_members.jsonl"):
        members.setdefault(row["session_id"], set()).add(row["event_id"])
    provider_models = {(row["provider"], row["model"]) for row in read_jsonl(package / "snapshot" / "authoritative_forecast_population.jsonl")}
    return {"sessions": sessions, "members": members, "provider_models": provider_models, "package": package.name}


def is_iso_before_or_equal(left: str, right: str) -> bool:
    try:
        return datetime.fromisoformat(left.replace("Z", "+00:00")) <= datetime.fromisoformat(right.replace("Z", "+00:00"))
    except ValueError:
        return False


def is_sha256_hex(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value.lower())


def validate_google_history_row(row: Mapping[str, str], state: Mapping[str, Any]) -> dict[str, Any]:
    """Preserve the original row while deriving only immutable validation metadata."""
    exported = dict(row)
    status = exported.get("status", "")
    problems = []
    if exported.get("source_sheet") != "Session_Attention_Map":
        problems.append("SOURCE_SHEET_NOT_DEDICATED_ATTENTION_MAP")
    if exported.get("capture_status") != "CAPTURED":
        problems.append("CAPTURE_NOT_CONFIRMED")
    if status not in GOOGLE_ALLOWED_STATUSES:
        problems.append("UNKNOWN_STATUS")
    if not exported.get("source_row_hash"):
        problems.append("MISSING_SOURCE_ROW_HASH")
    elif not is_sha256_hex(exported["source_row_hash"]):
        problems.append("INVALID_SOURCE_ROW_HASH")
    session = state["sessions"].get(exported.get("session_id", ""))
    if not session:
        problems.append("SESSION_NOT_IN_FROZEN_SNAPSHOT")
    else:
        exported["forecast_cutoff_ts"] = session["forecast_cutoff"]
        exported["forecast_cutoff_source"] = "frozen_authoritative_session_snapshot"
        if exported.get("event_id") not in state["members"].get(exported["session_id"], set()):
            problems.append("EVENT_NOT_IN_EXACT_FROZEN_SESSION")
        if (exported.get("provider"), exported.get("model")) not in state["provider_models"]:
            problems.append("PROVIDER_MODEL_NOT_IN_FROZEN_POPULATION")
        if not is_iso_before_or_equal(session["forecast_cutoff"], exported.get("release_ts", "")):
            problems.append("CUTOFF_NOT_BEFORE_SOURCE_RELEASE")
    raw = parse_raw_attention(exported.get("raw_output", ""))
    raw_valid = False
    if status == "parsed":
        if exported.get("attention_label") not in ALLOWED_LABELS:
            problems.append("UNKNOWN_ATTENTION_LABEL")
        if not raw or raw.get("object") != "session_attention_map" or raw.get("session_id") != exported.get("session_id"):
            problems.append("PARSED_RAW_OUTPUT_NOT_DEDICATED_ATTENTION_MAP")
        else:
            item = next((item for item in raw.get("attention_items", []) if item.get("event_id") == exported.get("event_id")), None)
            if not item or item.get("attention_label") != exported.get("attention_label"):
                problems.append("PARSED_RAW_OUTPUT_FIELD_MISMATCH")
            else:
                raw_valid = True
    elif status == "provider_omitted_event":
        if not raw or raw.get("object") != "session_attention_map" or raw.get("session_id") != exported.get("session_id"):
            problems.append("OMISSION_RAW_OUTPUT_NOT_DEDICATED_ATTENTION_MAP")
        elif any(item.get("event_id") == exported.get("event_id") for item in raw.get("attention_items", [])):
            problems.append("OMITTED_EVENT_PRESENT_IN_RAW_OUTPUT")
        else:
            raw_valid = True
    else:
        # Contract-error raw output is evidence of failure, not a candidate classification.
        raw_valid = bool(exported.get("raw_output"))
    exported["raw_output_validation"] = "VALID" if raw_valid else "UNAVAILABLE"
    exported["historical_pre_release_lineage"] = (
        "PROVEN_BY_FROZEN_CUTOFF_AND_PRE_RELEASE_PAYLOAD" if session and "CUTOFF_NOT_BEFORE_SOURCE_RELEASE" not in problems else "UNAVAILABLE"
    )
    exported["step5_lineage_status"] = (
        "VALID_FOR_STEP5" if status == "parsed" and raw_valid and not problems else "PRESERVED_NOT_SELECTABLE"
    )
    exported["validation_errors"] = sorted(problems)
    exported["source_object"] = "session_attention_map"
    exported["source_spreadsheet_id"] = GOOGLE_SPREADSHEET_ID
    exported["source_worksheet_gid"] = str(GOOGLE_WORKSHEET_GID)
    exported["source_worksheet_name"] = GOOGLE_WORKSHEET_NAME
    return exported


def deduplicate_google_records(records: Iterable[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    by_identity: dict[tuple[str, ...], dict[str, Any]] = {}
    exact_duplicates = 0
    for record in records:
        identity = tuple(str(record.get(key, "")) for key in ("attention_run_id", "session_id", "provider", "model", "event_id"))
        if not all(identity):
            raise PreservationError("MISSING_ATTENTION_IDENTITY")
        previous = by_identity.get(identity)
        if previous is None:
            by_identity[identity] = dict(record)
        elif canonical(previous) == canonical(record):
            exact_duplicates += 1
        else:
            raise PreservationError("CONFLICTING_ATTENTION_IDENTITY")
    return [by_identity[key] for key in sorted(by_identity)], exact_duplicates


def retrieve_google_history(service=None) -> tuple[list[str], list[dict[str, str]], dict[str, Any]]:
    """Perform the sole permitted external operation: a Sheets values read."""
    if service is None:
        service = build_sheets_service(load_credentials(interactive=False))
    metadata = service.spreadsheets().get(
        spreadsheetId=GOOGLE_SPREADSHEET_ID,
        fields="spreadsheetId,sheets.properties",
    ).execute()
    properties = [sheet["properties"] for sheet in metadata.get("sheets", [])]
    if not any(prop.get("title") == GOOGLE_WORKSHEET_NAME and prop.get("sheetId") == GOOGLE_WORKSHEET_GID for prop in properties):
        raise PreservationError("GOOGLE_WORKSHEET_IDENTITY_MISMATCH")
    headers, rows = normalize_google_values(get_sheet_values(service, GOOGLE_SPREADSHEET_ID, "'Session_Attention_Map_History'"))
    return headers, rows, {"spreadsheet_id": metadata.get("spreadsheetId"), "worksheet_count": len(properties)}


def export_google_history(output: Path = OUTPUT, service=None) -> dict[str, Any]:
    headers, source_rows, metadata = retrieve_google_history(service)
    state = historical_state()
    validated = [validate_google_history_row(row, state) for row in source_rows]
    exported, exact_duplicates = deduplicate_google_records(validated)
    source_fingerprint = google_content_fingerprint(headers, source_rows)
    for row in exported:
        row["source_content_fingerprint"] = source_fingerprint
        row["export_version"] = "presignal_v2_attention_history_export_v1"
        row["export_row_fingerprint"] = fingerprint({key: value for key, value in row.items() if key != "export_row_fingerprint"})
    output.mkdir(parents=True, exist_ok=True)
    (output / "authoritative_attention_map.jsonl").write_text("".join(canonical(row) + "\n" for row in exported))
    statuses = Counter(row["status"] for row in exported)
    unavailable = [row for row in exported if row["step5_lineage_status"] != "VALID_FOR_STEP5"]
    (output / "authoritative_attention_map_unavailable_ledger.jsonl").write_text("".join(canonical(row) + "\n" for row in unavailable))
    export_fingerprint = fingerprint(exported)
    source_manifest = {
        "spreadsheet_id": GOOGLE_SPREADSHEET_ID,
        "spreadsheet_url": GOOGLE_SPREADSHEET_URL,
        "worksheet_name": GOOGLE_WORKSHEET_NAME,
        "worksheet_gid": GOOGLE_WORKSHEET_GID,
        "requested_worksheet_gid": REQUESTED_GOOGLE_WORKSHEET_GID,
        "requested_gid_resolution": "Market_Sessions",
        "retrieval_timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "header_fields": headers,
        "source_row_count": len(source_rows),
        "non_empty_source_row_count": len(source_rows),
        "source_content_fingerprint": source_fingerprint,
        "export_schema_version": "presignal_v2_attention_history_export_v1",
        "exporter_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "google_metadata": metadata,
    }
    manifest = {
        "export_status": "AUTHORITATIVE_ATTENTION_SOURCE",
        "record_count": len(exported),
        "export_fingerprint": export_fingerprint,
        "source_content_fingerprint": source_fingerprint,
        "exact_duplicates_deduplicated": exact_duplicates,
        "status_counts": dict(sorted(statuses.items())),
        "step5_selectable_records": sum(row["step5_lineage_status"] == "VALID_FOR_STEP5" for row in exported),
    }
    parsed_labels: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in exported:
        if row["status"] == "parsed" and row["step5_lineage_status"] == "VALID_FOR_STEP5":
            parsed_labels[(row["session_id"], row["event_id"])].add(row["attention_label"])
    reconciliation = {
        "total_authoritative_captured_rows": len(source_rows),
        "successful_parsed_rows": statuses["parsed"],
        "provider_contract_error_rows": statuses["provider_contract_error"],
        "provider_omitted_event_rows": statuses["provider_omitted_event"],
        "invalid_or_unavailable_rows": len(source_rows) - sum(statuses.values()),
        "equation_holds": len(source_rows) == sum(statuses.values()),
        "sessions": len({row["session_id"] for row in exported}),
        "attention_runs": len({row["attention_run_id"] for row in exported}),
        "events": len({row["event_id"] for row in exported}),
        "providers": sorted({row["provider"] for row in exported}),
        "models": sorted({row["model"] for row in exported}),
        "label_counts": dict(sorted(Counter(row["attention_label"] for row in exported).items())),
        "status_counts": dict(sorted(statuses.items())),
        "duplicate_source_row_hashes": len(exported) - len({row["source_row_hash"] for row in exported}),
        "invalid_source_row_hashes": sum(not is_sha256_hex(row["source_row_hash"]) for row in exported),
        "raw_output_validation_counts": dict(sorted(Counter(row["raw_output_validation"] for row in exported).items())),
        "historical_pre_release_lineage_counts": dict(sorted(Counter(row["historical_pre_release_lineage"] for row in exported).items())),
        "provider_disagreement_event_count": sum(len(labels) > 1 for labels in parsed_labels.values()),
        "step5_lineage_status_counts": dict(sorted(Counter(row["step5_lineage_status"] for row in exported).items())),
    }
    (output / "attention_google_sheet_source_manifest.json").write_text(json.dumps(source_manifest, indent=2, sort_keys=True) + "\n")
    (output / "authoritative_attention_map_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    (output / "authoritative_attention_map_reconciliation.json").write_text(json.dumps(reconciliation, indent=2, sort_keys=True) + "\n")
    inventory = inspect_sources() + [candidate(
        source_path=GOOGLE_SPREADSHEET_URL, source_type="google_sheet_history_export", source_commit="",
        source_run_id="multiple_attention_runs", source_file_hash=source_fingerprint,
        candidate_object_type="SESSION_ATTENTION_MAP_HISTORY", dedicated=True, session=True, provider=True,
        model=True, cutoff=True, raw=True, parser=True, accepted=True, reason="", decision="AUTHORITATIVE_ATTENTION_SOURCE",
    )]
    (output / "attention_source_inventory.json").write_text(json.dumps(sorted(inventory, key=lambda row: row["source_path"]), indent=2, sort_keys=True) + "\n")
    (output / "attention_source_decision.json").write_text(json.dumps({
        "decision": "V2_1_FROZEN_ATTENTION_EXPORT_VALIDATED",
        "accepted_authoritative_sources": 1,
        "source_content_fingerprint": source_fingerprint,
        "external_calls": {"provider": 0, "acquisition": 0, "market_data": 0, "apps_script": 0, "google_sheets_writes": 0},
    }, indent=2, sort_keys=True) + "\n")
    return {**manifest, "source_manifest": source_manifest, "reconciliation": reconciliation}


def run_inventory(output: Path = OUTPUT) -> dict[str, Any]:
    inventory = inspect_sources()
    decision = {
        "decision": "V2_1_FROZEN_ATTENTION_LINEAGE_NOT_RECOVERABLE",
        "accepted_authoritative_sources": 0,
        "candidate_count": len(inventory),
        "candidate_decisions": dict(sorted(Counter(row["source_decision"] for row in inventory).items())),
        "reason": "No exact Session_Attention_Map rows or exact immutable raw responses are present in the authorized local frozen artifacts or Git history.",
        "external_calls": {"provider": 0, "acquisition": 0, "market_data": 0, "apps_script": 0, "google_sheets_writes": 0},
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "attention_source_inventory.json").write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n")
    (output / "attention_source_decision.json").write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n")
    return decision


def main() -> None:
    parser = argparse.ArgumentParser(description="Fail-closed v2 Session Attention Map preservation export.")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--source", choices=("inventory", "google"), default="inventory")
    args = parser.parse_args()
    result = export_google_history(args.output) if args.source == "google" else run_inventory(args.output)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
