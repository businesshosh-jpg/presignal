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
import tarfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
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
    args = parser.parse_args()
    print(json.dumps(run_inventory(args.output), sort_keys=True))


if __name__ == "__main__":
    main()
