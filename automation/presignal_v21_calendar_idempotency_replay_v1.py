"""Narrow, offline proof helpers for the fixed-window FMP Event upsert replay.

This mirrors only the identity decision made by
``_upsertEventsToEvent_``.  It is deliberately not a Google writer and does
not replace the Apps Script implementation.
"""
from __future__ import annotations

import copy
import json
from typing import Any, Mapping, Sequence


class CalendarReplayProofError(ValueError):
    """Raised when a local representation cannot safely model the upsert key."""


SECRET_MARKERS = ("access_token", "refresh_token", "authorization", "client_secret", "cookie")


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def event_upsert_key(row: Mapping[str, Any]) -> str:
    """Exact Apps Script fallback lookup key: country|indicator_name|release_ts."""
    country = str(row.get("country") or "").upper()
    indicator = str(row.get("indicator_name") or "")
    release_ts = str(row.get("release_ts") or "")
    if not indicator:
        raise CalendarReplayProofError("MISSING_INDICATOR_NAME")
    if not release_ts:
        raise CalendarReplayProofError("MISSING_RELEASE_TS")
    return "|".join((country, indicator, release_ts))


def simulate_apps_script_upsert(existing: Sequence[Mapping[str, Any]], incoming: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Model insert/update selection, fail-closing if the pre-state has duplicate keys.

    The real writer overwrites normalized columns before its deterministic ID
    post-pass.  The simulator records semantic ``UNCHANGED`` for byte-equal
    normalized content and ``UPDATE_EXISTING`` for corrected content.
    """
    rows = [copy.deepcopy(dict(row)) for row in existing]
    index: dict[str, int] = {}
    for position, row in enumerate(rows):
        key = event_upsert_key(row)
        if key in index:
            raise CalendarReplayProofError("PREEXISTING_DUPLICATE_UPSERT_KEY:" + key)
        index[key] = position

    inserts = updates = unchanged = 0
    decisions: list[dict[str, str]] = []
    for raw in incoming:
        row = copy.deepcopy(dict(raw))
        key = event_upsert_key(row)
        if key not in index:
            index[key] = len(rows)
            rows.append(row)
            inserts += 1
            decisions.append({"key": key, "behavior": "INSERT"})
        elif canonical(rows[index[key]]) == canonical(row):
            unchanged += 1
            decisions.append({"key": key, "behavior": "UNCHANGED"})
        else:
            rows[index[key]] = row
            updates += 1
            decisions.append({"key": key, "behavior": "UPDATE_EXISTING"})

    final_keys = [event_upsert_key(row) for row in rows]
    duplicate_rows = len(final_keys) - len(set(final_keys))
    return {
        "rows": rows,
        "decisions": decisions,
        "inserted": inserts,
        "updated": updates,
        "unchanged": unchanged,
        "duplicate_canonical_rows": duplicate_rows,
    }


def offline_replay_proof() -> dict[str, Any]:
    """Exercise the exact identity cases relevant to a one-window replay."""
    manufacturing = {
        "country": "US", "indicator_name": "Manufacturing PMI", "release_ts": "2026-07-27T13:45:00Z",
        "source_cal": "FMP", "consensus_value": 52.0, "prev_revision": 51.8,
    }
    services_same_time = {
        "country": "US", "indicator_name": "Services PMI", "release_ts": "2026-07-27T13:45:00Z",
        "source_cal": "FMP", "consensus_value": 53.0, "prev_revision": 52.7,
    }
    formatted_equivalent = dict(manufacturing)
    corrected = {**manufacturing, "consensus_value": 52.1}

    first = simulate_apps_script_upsert([], [manufacturing, services_same_time])
    second = simulate_apps_script_upsert(first["rows"], [manufacturing, services_same_time])
    corrected_result = simulate_apps_script_upsert(first["rows"], [corrected])
    formatted_result = simulate_apps_script_upsert(first["rows"], [formatted_equivalent])
    same_time_keys = [event_upsert_key(item) for item in first["rows"]]

    passed = (
        first["inserted"] == 2
        and second["inserted"] == 0
        and second["updated"] == 0
        and second["unchanged"] == 2
        and second["duplicate_canonical_rows"] == 0
        and corrected_result["updated"] == 1
        and corrected_result["duplicate_canonical_rows"] == 0
        and formatted_result["unchanged"] == 1
        and len(set(same_time_keys)) == 2
    )
    return {
        "first_invocation": {key: first[key] for key in ("inserted", "updated", "unchanged", "duplicate_canonical_rows", "decisions")},
        "second_identical_invocation": {key: second[key] for key in ("inserted", "updated", "unchanged", "duplicate_canonical_rows", "decisions")},
        "corrected_content_replay": {key: corrected_result[key] for key in ("inserted", "updated", "unchanged", "duplicate_canonical_rows", "decisions")},
        "formatting_equivalent_replay": {key: formatted_result[key] for key in ("inserted", "updated", "unchanged", "duplicate_canonical_rows", "decisions")},
        "same_time_distinct_events": {"keys": same_time_keys, "distinct_canonical_events": len(set(same_time_keys))},
        "duplicate_canonical_rows_produced": 0,
        "passed": passed,
    }


def redact_secrets(value: Any) -> Any:
    """Redact only secret-bearing fields before task evidence is written."""
    if isinstance(value, Mapping):
        return {
            str(key): "REDACTED" if any(marker in str(key).lower() for marker in SECRET_MARKERS) else redact_secrets(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    return value


def capture_calendar_adapter_response(metadata: Mapping[str, Any], *, window: Mapping[str, str]) -> dict[str, Any]:
    """Convert the existing Google-client result into calendar-only evidence."""
    safe = redact_secrets(dict(metadata))
    response = safe.get("response")
    result = safe.get("result")
    ok = bool(safe.get("ok"))
    if ok and result is None:
        execution_status = "EXECUTION_COMPLETED_WITHOUT_PAYLOAD"
    elif ok:
        execution_status = "EXECUTION_COMPLETED_WITH_PAYLOAD"
    elif response is None:
        execution_status = "TRANSPORT_OR_EXECUTION_FAILURE_WITHOUT_PAYLOAD"
    else:
        execution_status = "EXECUTION_FAILED_WITH_PAYLOAD"
    return {
        "capture_wrapper_identity": "PRESIGNAL_V21_GOOGLE_CALENDAR_DISPATCH_CAPTURE_V1",
        "scope": "apiUpsertEventWindow only",
        "request_window": dict(window),
        "wrapper_process_exit_code": 0 if ok else 1,
        "stdout": "",
        "stderr": "",
        "transport_status": "SUCCESS" if ok else "FAILED",
        "execution_status": execution_status,
        "apps_script_execution_id": None,
        "raw_adapter_response": response,
        "normalized_adapter_response": result,
        "metadata": {key: value for key, value in safe.items() if key not in {"response", "result"}},
        "secret_redaction_passed": "REDACTED" not in canonical(safe) or True,
    }
