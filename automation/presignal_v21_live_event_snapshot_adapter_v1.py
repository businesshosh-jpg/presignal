"""Bind authoritative Event-sheet rows to the immutable v2.1 Episode input.

This is deliberately only a serialization boundary.  Episode construction,
event identity, batching and type semantics remain owned by their existing
authoritative modules.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from automation import build_presignal_v21_episodes as episodes
from automation.run_presignal_v21_designed_drift_r6_admission_v1 import AdmissionError, validate_event_batch_semantics

SCHEMA_VERSION = "presignal_v21_live_event_source_snapshot_v1"
CONSTRUCTOR_FIELDS = (
    "event_id", "batch_id", "country", "indicator_name", "release_ts",
    "source_cal", "source_provider", "source_series_id", "type",
)


class LiveEventSnapshotError(RuntimeError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    if path.exists():
        raise LiveEventSnapshotError("DUPLICATE_EVENT_SOURCE_SNAPSHOT")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def build_event_source_snapshot(*, event_rows: Iterable[Mapping[str, Any]], source_identity: Mapping[str, Any],
                                read_timestamp: str, output_path: Path) -> dict[str, Any]:
    """Freeze valid live Event rows in the exact existing constructor schema."""
    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for ordinal, row in enumerate(event_rows, 2):
        mapped = {field: _text(row.get(field)) for field in CONSTRUCTOR_FIELDS}
        try:
            validate_event_batch_semantics(mapped)
            mapped["release_ts"] = episodes.utc_timestamp(mapped["release_ts"])
            # Validate the existing constructor's immutable source requirements
            # without reproducing any grouping or identity logic.
            episodes.source_record(mapped)
        except (AdmissionError, episodes.EpisodeBuildError) as exc:
            excluded.append({"source_row_identity": _text(row.get("_row_number")) or str(ordinal),
                             "event_id": mapped["event_id"], "reason": str(exc)})
            continue
        mapped["source_row_identity"] = _text(row.get("_row_number")) or str(ordinal)
        included.append(mapped)
    included.sort(key=lambda row: (row["release_ts"], row["source_row_identity"], row["event_id"]))
    identity = {"schema_version": SCHEMA_VERSION, "source_identity": dict(source_identity),
                "read_timestamp": read_timestamp, "rows": included, "excluded": excluded}
    snapshot = {"snapshot_id": "EVSRC_" + sha256(identity)[7:27], **identity,
                "included_row_count": len(included), "excluded_row_count": len(excluded)}
    snapshot["snapshot_checksum"] = sha256(snapshot)
    _atomic_json(output_path, snapshot)
    return snapshot


def constructor_rows(snapshot: Mapping[str, Any]) -> list[dict[str, str]]:
    """Return only the original constructor input fields, unchanged."""
    if snapshot.get("schema_version") != SCHEMA_VERSION:
        raise LiveEventSnapshotError("EVENT_SOURCE_SNAPSHOT_SCHEMA_INVALID")
    return [{field: _text(row.get(field)) for field in CONSTRUCTOR_FIELDS} for row in snapshot.get("rows", [])]


def build_population_from_snapshot(snapshot: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return episodes.build_population(constructor_rows(snapshot))
