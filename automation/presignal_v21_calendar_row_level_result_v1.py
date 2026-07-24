"""Validation for the compact row-level calendar refresh result contract."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping


REQUIRED_EVENT_FIELDS = ("event_identity", "country", "indicator_name", "release_ts", "source_identity", "content_checksum", "write_disposition")
DISPOSITIONS = {"INSERTED", "UPDATED", "UNCHANGED", "FAILED"}


def canonical(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True)


def sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def identity(row: Mapping[str, Any]) -> str:
    return "|".join((str(row.get("country") or "").upper(), str(row.get("indicator_name") or ""), str(row.get("release_ts") or "")))


def ordering_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (str(row["release_ts"]), str(row["country"]), str(row["indicator_name"]), str(row["event_identity"]))


def ordered_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Restore the declared result-field order after JSON transport reorders keys."""
    return {key: row[key] for key in REQUIRED_EVENT_FIELDS}


def validate_result(value: Mapping[str, Any]) -> list[dict[str, Any]]:
    transport_rows = list(value.get("canonical_events") or [])
    rows = []
    for row in transport_rows:
        missing = [key for key in REQUIRED_EVENT_FIELDS if key not in row]
        if missing:
            raise ValueError("CANONICAL_EVENT_FIELD_MISSING:" + missing[0])
        rows.append(ordered_row(row))
    if int(value.get("canonical_event_count", -1)) != len(rows):
        raise ValueError("CANONICAL_EVENT_COUNT_MISMATCH")
    if rows != sorted(rows, key=ordering_key):
        raise ValueError("CANONICAL_EVENT_ORDER_INVALID")
    identities = []
    disposition_counts = {key: 0 for key in DISPOSITIONS}
    for row in rows:
        if row["write_disposition"] not in DISPOSITIONS:
            raise ValueError("CANONICAL_EVENT_DISPOSITION_INVALID")
        if row["write_disposition"] != "FAILED" and row["event_identity"] != identity(row):
            raise ValueError("CANONICAL_EVENT_IDENTITY_INVALID")
        identities.append(row["event_identity"])
        disposition_counts[row["write_disposition"]] += 1
    if len(identities) != len(set(identities)):
        raise ValueError("CANONICAL_EVENT_DUPLICATE_IDENTITY")
    if value.get("canonical_event_set_checksum") != sha(rows):
        raise ValueError("CANONICAL_EVENT_SET_CHECKSUM_MISMATCH")
    if int(value.get("inserted_count", -1)) != disposition_counts["INSERTED"]:
        raise ValueError("INSERTED_COUNT_MISMATCH")
    if int(value.get("updated_count", -1)) != disposition_counts["UPDATED"]:
        raise ValueError("UPDATED_COUNT_MISMATCH")
    if int(value.get("unchanged_count", -1)) != disposition_counts["UNCHANGED"]:
        raise ValueError("UNCHANGED_COUNT_MISMATCH")
    if int(value.get("failed_count", -1)) != disposition_counts["FAILED"]:
        raise ValueError("FAILED_COUNT_MISMATCH")
    return rows


def reconcile(adapter_rows: Iterable[Mapping[str, Any]], readback_rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    adapter = {row["event_identity"]: dict(row) for row in adapter_rows}
    readback = {row["event_identity"]: dict(row) for row in readback_rows}
    common = sorted(set(adapter) & set(readback))
    content = [key for key in common if adapter[key]["content_checksum"] != readback[key]["content_checksum"]]
    return {
        "adapter_only": sorted(set(adapter) - set(readback)),
        "readback_only": sorted(set(readback) - set(adapter)),
        "matching": common,
        "content_mismatches": content,
        "identity_sets_equal": set(adapter) == set(readback),
        "passed": set(adapter) == set(readback) and not content,
    }
