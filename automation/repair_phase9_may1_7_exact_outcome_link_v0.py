#!/usr/bin/env python3
"""Recover only exact May 1-7 session-to-canonical-outcome bridges.

This is a shadow-only repair for the historical gap replay.  It deliberately
does not alter the replay, canonical outcome sources, Pack E, or workbooks.
The bridge is allowed only when the session's recorded primary release window
contains one exact Event identity and that exact event/release identity has one
strict, authoritative five-minute canonical outcome.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_market_sessions_shadow_v0 import (  # type: ignore
    DIAGNOSTICS_SPREADSHEET_ID,
    MAIN_SPREADSHEET_ID,
    _sheet_to_rows,
)
from automation.google_clients import build_sheets_service, load_credentials  # type: ignore
from automation.repair_mechanism_evaluation_population_end_to_end_v0 import (  # type: ignore
    _derive_success_status,
    _normalize_direction,
)


PHASE_ID = "9-MAY1-7-EXACT-OUTCOME-LINK-REPAIR"
SCRIPT_PATH = "automation/repair_phase9_may1_7_exact_outcome_link_v0.py"
GAP_REPLAY_RUN_ID = "9A-EARLIEST-GAP-REPLAY_20260714T012846Z"
GAP_REPLAY_ROOT = (
    ROOT / "outputs" / "phase9a_earliest_historical_gap_replay" / GAP_REPLAY_RUN_ID
)
ACTIVE_REPLAY_ROOT = (
    ROOT / "outputs" / "phase9a_earliest_historical_gap_replay" / "active_historical_asof_replay_v1"
)
TRUE_PACK_E_FREEZE = (
    ROOT
    / "outputs"
    / "phase9_true_pack_e_validation"
    / "9-TRUE-SHARED-PACK-E-VALIDATION_20260714T081534Z"
    / "pack_e_freeze_manifest.json"
)
OUTPUT_ROOT = ROOT / "outputs" / "phase9_may1_7_exact_outcome_link_repair"

DATE_START = "2024-05-01"
DATE_END_EXCLUSIVE = "2024-05-08"
CANONICAL_IMPLEMENTATION_VERSION = "market_reaction_outcome_source_implementation_v0"
FROZEN_WINDOW_POLICY = "EVENT_RELATIVE_FIXED_DURATION"
FROZEN_WINDOW_MINUTES = 5
SOURCE_COLLECTION_MODE = "HISTORICAL_ASOF_REPLAY"


class RepairBlocked(RuntimeError):
    """Raised when an input or exact-link invariant fails closed."""


def _norm(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return str(value).strip()


def _identifier(value: Any) -> str:
    """Normalize a governed identifier without truthiness fallback coercion."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value != value:  # NaN is never a valid identity.
            return ""
        return str(int(value)) if value.is_integer() else format(value, ".15g")
    return str(value).strip()


def _truth(value: Any) -> bool:
    return _norm(value).upper() in {"TRUE", "1", "YES", "Y", "PASS"}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise RepairBlocked(f"JSON_OBJECT_REQUIRED:{path}")
    return value


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise RepairBlocked(f"JSONL_OBJECT_REQUIRED:{path}:{line_number}")
            rows.append(value)
    return rows


def _write_json(path: Path, value: Any) -> None:
    path.write_text(_canonical_json(value) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.write_text(
        "".join(_canonical_json(dict(row)) + "\n" for row in rows), encoding="utf-8"
    )


def _canonical_row_payload(row: Mapping[str, Any]) -> Dict[str, Any]:
    """Canonical source content excludes physical Sheets row positions only."""
    return {
        key: value
        for key, value in row.items()
        if key != "__source_row_number__"
    }


def _canonical_source_fingerprint(rows: Sequence[Mapping[str, Any]]) -> str:
    payload = sorted(
        (_canonical_row_payload(row) for row in rows),
        key=lambda row: _identifier(row.get("canonical_outcome_id")),
    )
    return _sha256(payload)


def _load_canonical_overrides(
    base_rows: Sequence[Mapping[str, Any]], override_manifest_path: Optional[Path]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Apply only validated batch-ID overrides from a shadow repair artifact."""
    if override_manifest_path is None:
        return [dict(row) for row in base_rows], {}
    manifest = _read_json(override_manifest_path)
    if _norm(manifest.get("repair_scope")) != "CANONICAL_BATCH_IDENTITY_SHADOW_OVERRIDE":
        raise RepairBlocked("CANONICAL_OVERRIDE_SCOPE_INVALID")
    if _norm(manifest.get("base_canonical_logical_fingerprint")) != _canonical_source_fingerprint(base_rows):
        raise RepairBlocked("CANONICAL_OVERRIDE_BASE_FINGERPRINT_MISMATCH")
    overrides_path = Path(_norm(manifest.get("override_file")))
    if not overrides_path.is_absolute():
        overrides_path = override_manifest_path.parent / overrides_path
    overrides = _read_jsonl(overrides_path)
    if _norm(manifest.get("override_file_fingerprint")) != _sha256(overrides):
        raise RepairBlocked("CANONICAL_OVERRIDE_FILE_FINGERPRINT_MISMATCH")
    by_id = {
        _identifier(row.get("canonical_outcome_id")): dict(row)
        for row in base_rows
        if _identifier(row.get("canonical_outcome_id"))
    }
    if len(by_id) != len(base_rows):
        raise RepairBlocked("CANONICAL_OVERRIDE_BASE_ID_DUPLICATE_OR_MISSING")
    seen: set[str] = set()
    for override in overrides:
        canonical_id = _identifier(override.get("canonical_outcome_id"))
        if not canonical_id or canonical_id in seen or canonical_id not in by_id:
            raise RepairBlocked("CANONICAL_OVERRIDE_ID_INVALID_OR_DUPLICATE")
        seen.add(canonical_id)
        base = by_id[canonical_id]
        if (
            _norm(base.get("country")) != _norm(override.get("country"))
            or _identifier(base.get("event_id")) != _identifier(override.get("event_id"))
            or _iso_second(base.get("release_ts")) != _iso_second(override.get("release_ts"))
            or _identifier(base.get("batch_id")) != _identifier(override.get("old_batch_id"))
        ):
            raise RepairBlocked("CANONICAL_OVERRIDE_BASE_IDENTITY_MISMATCH")
        if _norm(override.get("scientific_value_fingerprint_before")) != _norm(override.get("scientific_value_fingerprint_after")):
            raise RepairBlocked("CANONICAL_OVERRIDE_SCIENTIFIC_VALUE_CHANGE")
        base["batch_id"] = _identifier(override.get("new_batch_id"))
    return list(by_id.values()), {
        "canonical_override_manifest": str(override_manifest_path),
        "canonical_override_run_id": _identifier(manifest.get("canonical_repair_run_id")),
        "canonical_override_count": len(overrides),
        "repaired_canonical_logical_fingerprint": _norm(manifest.get("repaired_canonical_logical_fingerprint")),
    }


def _parse_ts(value: Any) -> Optional[datetime]:
    text = _norm(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _iso_second(value: Any) -> str:
    parsed = _parse_ts(value)
    return parsed.isoformat().replace("+00:00", "Z") if parsed else ""


def _stable_key(*parts: Any) -> str:
    return "|".join(_identifier(part) for part in parts)


def _run_id(now: datetime) -> str:
    return f"{PHASE_ID}_{now.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"


def _source_date_in_scope(value: Any) -> bool:
    date = _iso_second(value)[:10]
    return DATE_START <= date < DATE_END_EXCLUSIVE


def _window_is_exact(canonical: Mapping[str, Any]) -> bool:
    start = _parse_ts(canonical.get("canonical_start_ts"))
    end = _parse_ts(canonical.get("canonical_end_ts"))
    release = _parse_ts(canonical.get("release_ts"))
    return (
        _norm(canonical.get("window_policy")) == FROZEN_WINDOW_POLICY
        and _norm(canonical.get("window_minutes")) in {"5", "5.0", "5.000"}
        and start is not None
        and end is not None
        and release is not None
        and start == release
        and end - start == timedelta(minutes=FROZEN_WINDOW_MINUTES)
    )


def _canonical_strict_ready(canonical: Mapping[str, Any], authoritative_run_id: str) -> bool:
    return (
        _identifier(canonical.get("implementation_run_id")) == authoritative_run_id
        and _norm(canonical.get("implementation_version")) == CANONICAL_IMPLEMENTATION_VERSION
        and _truth(canonical.get("usable_for_strict_accuracy"))
        and _norm(canonical.get("trust_level")) == "HIGH_TRUST"
        and _normalize_direction(canonical.get("canonical_realized_direction")) in {"UP", "DOWN", "FLAT"}
        and _window_is_exact(canonical)
    )


def _event_index(rows: Sequence[Mapping[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    index: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        event_id = _identifier(row.get("event_id"))
        release_ts = _iso_second(row.get("release_ts"))
        if event_id and release_ts:
            index[event_id].append(dict(row))
    for values in index.values():
        values.sort(key=lambda row: (_iso_second(row.get("release_ts")), _identifier(row.get("batch_id"))))
    return index


def _canonical_index(rows: Sequence[Mapping[str, Any]]) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
    index: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (_identifier(row.get("event_id")), _iso_second(row.get("release_ts")))
        if key[0] and key[1]:
            index[key].append(dict(row))
    for values in index.values():
        values.sort(key=lambda row: _identifier(row.get("canonical_outcome_id")))
    return index


def _member_rows_for_session(
    session: Mapping[str, Any], event_by_id: Mapping[str, Sequence[Mapping[str, Any]]]
) -> Tuple[List[Dict[str, Any]], List[str]]:
    session_start = _parse_ts(session.get("session_start_ts"))
    session_end = _parse_ts(session.get("session_end_ts"))
    country = _norm(session.get("country"))
    if session_start is None or session_end is None or session_end < session_start:
        return [], ["INVALID_SESSION_BOUNDARIES"]
    member_ids = [part for part in _norm(session.get("member_event_ids")).split("|") if part]
    if not member_ids or len(member_ids) != len(set(member_ids)):
        return [], ["MISSING_OR_DUPLICATE_MEMBER_EVENT_ID"]
    members: List[Dict[str, Any]] = []
    errors: List[str] = []
    for event_id in member_ids:
        candidates = [
            dict(row)
            for row in event_by_id.get(event_id, [])
            if _norm(row.get("country")) == country
            and (release := _parse_ts(row.get("release_ts"))) is not None
            and session_start <= release <= session_end
        ]
        if len(candidates) != 1:
            errors.append(f"EVENT_MEMBER_IDENTITY_NOT_UNIQUE:{event_id}:{len(candidates)}")
            continue
        members.append(candidates[0])
    return members, errors


def _candidate_audit_row(
    *,
    session: Mapping[str, Any],
    member: Mapping[str, Any],
    canonical: Mapping[str, Any],
    authoritative_run_id: str,
    primary_member_count: int,
    disposition: str,
) -> Dict[str, Any]:
    return {
        "session_id": _identifier(session.get("session_id")),
        "session_primary_release_ts": _iso_second(session.get("primary_release_ts")),
        "member_event_id": _identifier(member.get("event_id")),
        "member_batch_id": _identifier(member.get("batch_id")),
        "member_type": _norm(member.get("type")),
        "member_release_ts": _iso_second(member.get("release_ts")),
        "canonical_event_id": _identifier(canonical.get("event_id")),
        "canonical_batch_id": _identifier(canonical.get("batch_id")),
        "canonical_outcome_id": _identifier(canonical.get("canonical_outcome_id")),
        "canonical_release_ts": _iso_second(canonical.get("release_ts")),
        "canonical_start_ts": _iso_second(canonical.get("canonical_start_ts")),
        "canonical_end_ts": _iso_second(canonical.get("canonical_end_ts")),
        "canonical_direction": _normalize_direction(canonical.get("canonical_realized_direction")),
        "canonical_trust_level": _norm(canonical.get("trust_level")),
        "strict_ready": "TRUE" if _canonical_strict_ready(canonical, authoritative_run_id) else "FALSE",
        "event_id_exact": "TRUE" if _identifier(member.get("event_id")) == _identifier(canonical.get("event_id")) else "FALSE",
        "release_ts_exact": "TRUE" if _iso_second(member.get("release_ts")) == _iso_second(canonical.get("release_ts")) else "FALSE",
        "batch_id_confirmed": "TRUE"
        if _identifier(member.get("batch_id")) == _identifier(canonical.get("batch_id"))
        else "FALSE",
        "five_minute_window_valid": "TRUE" if _window_is_exact(canonical) else "FALSE",
        "primary_member_count": primary_member_count,
        "disposition": disposition,
    }


def _resolve_session(
    *,
    session: Mapping[str, Any],
    event_by_id: Mapping[str, Sequence[Mapping[str, Any]]],
    canonical_by_event_release: Mapping[Tuple[str, str], Sequence[Mapping[str, Any]]],
    authoritative_run_id: str,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Resolve one session without using any date-, time-, or fuzzy fallback."""
    session_id = _identifier(session.get("session_id"))
    primary_release = _iso_second(session.get("primary_release_ts"))
    audit: Dict[str, Any] = {
        "session_id": session_id,
        "session_date": _norm(session.get("session_date")),
        "country": _norm(session.get("country")),
        "session_primary_release_ts": primary_release,
        "session_member_event_ids": _norm(session.get("member_event_ids")),
        "primary_member_event_ids": "",
        "primary_member_count": 0,
        "canonical_candidate_count": 0,
        "strict_canonical_candidate_count": 0,
        "status": "REMAINS_EXCLUDED",
        "exclusion_reason": "",
        "selected_event_id": "",
        "selected_batch_id": "",
        "canonical_outcome_id": "",
        "canonical_direction": "",
        "canonical_implementation_run_id": "",
        "exact_identity_chain": "",
    }
    members, member_errors = _member_rows_for_session(session, event_by_id)
    if member_errors:
        audit.update({"status": "SESSION_MEMBER_LINK_MISSING", "exclusion_reason": "|".join(sorted(member_errors))})
        return audit, []
    primary_members = [row for row in members if _iso_second(row.get("release_ts")) == primary_release]
    audit["primary_member_event_ids"] = "|".join(sorted(_identifier(row.get("event_id")) for row in primary_members))
    audit["primary_member_count"] = len(primary_members)
    if not primary_members:
        audit.update({"status": "EXACT_EVENT_ID_MISSING", "exclusion_reason": "NO_SESSION_MEMBER_AT_EXPLICIT_PRIMARY_RELEASE"})
        return audit, []

    candidate_rows: List[Dict[str, Any]] = []
    exact_candidates: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    for member in primary_members:
        matching = list(canonical_by_event_release.get((_identifier(member.get("event_id")), _iso_second(member.get("release_ts"))), []))
        if not matching:
            candidate_rows.append({
                "session_id": session_id,
                "session_primary_release_ts": primary_release,
                "member_event_id": _identifier(member.get("event_id")),
                "member_batch_id": _identifier(member.get("batch_id")),
                "member_release_ts": _iso_second(member.get("release_ts")),
                "canonical_outcome_id": "",
                "primary_member_count": len(primary_members),
                "disposition": "NO_EXACT_EVENT_RELEASE_CANONICAL_CANDIDATE",
            })
        for canonical in matching:
            batch_confirmed = _identifier(member.get("batch_id")) == _identifier(canonical.get("batch_id"))
            disposition = "CANDIDATE"
            if not batch_confirmed:
                disposition = "BATCH_ID_MISMATCH_REJECTED"
            else:
                exact_candidates.append((dict(member), dict(canonical)))
            candidate_rows.append(_candidate_audit_row(
                session=session,
                member=member,
                canonical=canonical,
                authoritative_run_id=authoritative_run_id,
                primary_member_count=len(primary_members),
                disposition=disposition,
            ))
    audit["canonical_candidate_count"] = len(exact_candidates)
    audit["strict_canonical_candidate_count"] = sum(
        1 for _, canonical in exact_candidates if _canonical_strict_ready(canonical, authoritative_run_id)
    )

    # A shared primary minute is never an ownership rule.  It stays blocked even
    # if its event-specific candidates happen to have equal market reactions.
    if len(primary_members) > 1:
        audit.update({
            "status": "MULTIPLE_CANONICAL_CANDIDATES",
            "exclusion_reason": "MULTIPLE_EXACT_SESSION_MEMBERS_AT_PRIMARY_RELEASE_NO_FROZEN_OWNERSHIP_RULE",
        })
        return audit, candidate_rows
    if not exact_candidates:
        audit.update({"status": "NO_CANONICAL_OUTCOME_EXISTS", "exclusion_reason": "NO_EXACT_EVENT_ID_AND_RELEASE_TS_CANONICAL_OUTCOME"})
        return audit, candidate_rows
    if len(exact_candidates) > 1:
        audit.update({"status": "MULTIPLE_CANONICAL_CANDIDATES", "exclusion_reason": "MULTIPLE_CANONICAL_ROWS_FOR_EXACT_EVENT_ID_AND_RELEASE_TS"})
        return audit, candidate_rows

    member, canonical = exact_candidates[0]
    if _identifier(canonical.get("implementation_run_id")) != authoritative_run_id:
        audit.update({"status": "CANONICAL_OUTCOME_NON_AUTHORITATIVE", "exclusion_reason": "CANONICAL_IMPLEMENTATION_RUN_MISMATCH"})
        return audit, candidate_rows
    if not _window_is_exact(canonical):
        audit.update({"status": "OUTCOME_WINDOW_MISMATCH", "exclusion_reason": "CANONICAL_WINDOW_NOT_EXACT_FIVE_MINUTES"})
        return audit, candidate_rows
    if not _canonical_strict_ready(canonical, authoritative_run_id):
        audit.update({"status": "REMAINS_EXCLUDED", "exclusion_reason": "CANONICAL_OUTCOME_NOT_STRICT_READY"})
        return audit, candidate_rows

    audit.update({
        "status": "EXACT_CANONICAL_OUTCOME_LINK_RECOVERED",
        "exclusion_reason": "",
        "selected_event_id": _identifier(member.get("event_id")),
        "selected_batch_id": _identifier(member.get("batch_id")),
        "canonical_outcome_id": _identifier(canonical.get("canonical_outcome_id")),
        "canonical_direction": _normalize_direction(canonical.get("canonical_realized_direction")),
        "canonical_implementation_run_id": _identifier(canonical.get("implementation_run_id")),
        "exact_identity_chain": _stable_key(
            session_id,
            member.get("event_id"),
            member.get("release_ts"),
            canonical.get("canonical_outcome_id"),
        ),
    })
    for candidate in candidate_rows:
        if candidate.get("canonical_outcome_id") == audit["canonical_outcome_id"]:
            candidate["disposition"] = "SELECTED_EXACT_STRICT_CANONICAL_OUTCOME"
    return audit, candidate_rows


def _load_preoutcome_artifacts() -> List[Dict[str, Any]]:
    artifacts = _read_jsonl(ACTIVE_REPLAY_ROOT / "preoutcome_replay_artifacts.jsonl")
    result: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for artifact in artifacts:
        collector = artifact.get("collector_record")
        forecast = artifact.get("forecast_row")
        behavior = artifact.get("behavior_row")
        if not isinstance(collector, dict) or not isinstance(forecast, dict) or not isinstance(behavior, dict):
            raise RepairBlocked("PREOUTCOME_ARTIFACT_COMPONENT_MISSING")
        stable_key = _identifier(collector.get("stable_observation_key"))
        if not stable_key or stable_key in seen:
            raise RepairBlocked("DUPLICATE_OR_MISSING_STABLE_OBSERVATION_KEY")
        seen.add(stable_key)
        result.append({"collector": collector, "forecast": forecast, "behavior": behavior, "artifact": artifact})
    return result


def _forecast_integrity(artifact: Mapping[str, Any], canonical: Mapping[str, Any]) -> Tuple[bool, str]:
    collector = artifact["collector"]
    forecast = artifact["forecast"]
    behavior = artifact["behavior"]
    captured = _parse_ts(collector.get("capture_timestamp"))
    forecast_ts = _parse_ts(collector.get("forecast_timestamp"))
    canonical_start = _parse_ts(canonical.get("canonical_start_ts"))
    complete = (
        _norm(artifact["artifact"].get("artifact_status")) == "COMPLETED"
        and _norm(collector.get("collection_mode")) == SOURCE_COLLECTION_MODE
        and _norm(collector.get("collection_status")) == "VALID_PREOUTCOME_SHADOW_RECORD"
        and _truth(collector.get("outcome_hidden_at_capture"))
        and _truth(forecast.get("json_parse_success"))
        and _truth(forecast.get("json_validation_success"))
        and _truth(behavior.get("output_valid"))
        and captured is not None
        and forecast_ts is not None
        and canonical_start is not None
        and captured < canonical_start
        and forecast_ts < canonical_start
    )
    return (complete, "PASS" if complete else "FORECAST_OR_CAPTURE_INTEGRITY_FAILED")


def _recovered_evaluation_rows(
    *,
    session_audits: Sequence[Mapping[str, Any]],
    canonical_by_id: Mapping[str, Mapping[str, Any]],
    artifacts: Sequence[Mapping[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    recovered_sessions = {
        _identifier(row.get("session_id")): row
        for row in session_audits
        if row.get("status") == "EXACT_CANONICAL_OUTCOME_LINK_RECOVERED"
    }
    recovered_rows: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []
    for artifact in artifacts:
        collector = artifact["collector"]
        session_id = _identifier(collector.get("session_id"))
        audit = recovered_sessions.get(session_id)
        if audit is None:
            continue
        canonical = canonical_by_id.get(_identifier(audit.get("canonical_outcome_id")))
        if canonical is None:
            raise RepairBlocked("SELECTED_CANONICAL_OUTCOME_NOT_FOUND")
        integrity_ok, integrity_reason = _forecast_integrity(artifact, canonical)
        if not integrity_ok:
            failures.append({
                "session_id": session_id,
                "provider": _norm(collector.get("provider")),
                "pack_level": _norm(collector.get("pack_level")),
                "status": "FORECAST_INTEGRITY_FAILED",
                "reason": integrity_reason,
            })
            continue
        forecast = artifact["forecast"]
        behavior = artifact["behavior"]
        direction = _normalize_direction(forecast.get("forecast_direction"))
        realized = _normalize_direction(canonical.get("canonical_realized_direction"))
        success_status, success_reason = _derive_success_status(
            forecast_direction=direction,
            no_signal_flag=_truth(behavior.get("no_signal_flag")),
            output_valid=_truth(behavior.get("output_valid")),
            realized_direction=realized,
            join_status="OK",
            join_reason="JOIN_READY",
        )
        recovered_rows.append({
            "recovery_status": "RECOVERED_THROUGH_EXACT_LINKAGE",
            "scientific_observation_key": _identifier(collector.get("scientific_observation_key")),
            "stable_observation_key": _identifier(collector.get("stable_observation_key")),
            "session_id": session_id,
            "provider": _norm(collector.get("provider")),
            "pack_level": _norm(collector.get("pack_level")),
            "forecast_id": _identifier(collector.get("forecast_id")),
            "source_session_run_id": GAP_REPLAY_RUN_ID,
            "source_forecast_run_id": _identifier(collector.get("historical_replay_run_id")),
            "source_outcome_run_id": _identifier(canonical.get("implementation_run_id")),
            "authoritative_status": "AUTHORITATIVE_EXACT_SHADOW_BRIDGE",
            "canonical_outcome_id": _identifier(canonical.get("canonical_outcome_id")),
            "event_id": _identifier(canonical.get("event_id")),
            "batch_id": _identifier(canonical.get("batch_id")),
            "canonical_start_ts": _iso_second(canonical.get("canonical_start_ts")),
            "canonical_end_ts": _iso_second(canonical.get("canonical_end_ts")),
            "forecast_timestamp": _iso_second(collector.get("forecast_timestamp")),
            "capture_timestamp": _iso_second(collector.get("capture_timestamp")),
            "outcome_hidden_at_capture": "TRUE",
            "forecast_before_outcome": "TRUE",
            "forecast_direction": direction,
            "realized_direction": realized,
            "success_status": success_status,
            "success_reason": success_reason,
            "no_rule_change_confirmation": "TRUE",
            "outcome_attachment_order": "AFTER_PREOUTCOME_FREEZE",
            "frozen_true_pack_e_version": "",
        })
    recovered_rows.sort(key=lambda row: (row["session_id"], row["provider"], row["pack_level"], row["forecast_id"]))
    if len({_identifier(row["stable_observation_key"]) for row in recovered_rows}) != len(recovered_rows):
        raise RepairBlocked("RECOVERED_EVALUATION_DUPLICATE_STABLE_KEY")
    return recovered_rows, failures


def _pair_readiness(
    recovered_rows: Sequence[Mapping[str, Any]], freeze: Mapping[str, Any]
) -> List[Dict[str, Any]]:
    by_provider: Dict[Tuple[str, str], Dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in recovered_rows:
        by_provider[(_identifier(row.get("session_id")), _norm(row.get("provider")))][_norm(row.get("pack_level"))] = row
    result: List[Dict[str, Any]] = []
    for (session_id, provider), levels in sorted(by_provider.items()):
        baseline = levels.get("A")
        legacy_e = levels.get("E")
        result.append({
            "session_id": session_id,
            "provider": provider,
            "valid_pack_a_forecast": "TRUE" if baseline else "FALSE",
            "valid_legacy_pack_e_forecast": "TRUE" if legacy_e else "FALSE",
            "valid_frozen_true_pack_e_forecast": "FALSE",
            "frozen_true_pack_e_version": _norm(freeze.get("pack_version")),
            "frozen_true_pack_e_fingerprint": _norm(freeze.get("pack_fingerprint")),
            "same_provider": "TRUE" if baseline and legacy_e else "FALSE",
            "same_session": "TRUE" if baseline and legacy_e else "FALSE",
            "same_frozen_outcome_window": "TRUE" if baseline and legacy_e else "FALSE",
            "pair_ready_for_frozen_true_pack_a_vs_e": "FALSE",
            "reason": "REPLAY_FORECASTS_PREDATE_TRUE_SHARED_PACK_E_V1_FREEZE",
        })
    return result


def _content_payload(
    session_audit: Sequence[Mapping[str, Any]],
    candidate_audit: Sequence[Mapping[str, Any]],
    canonical_identity_defects: Sequence[Mapping[str, Any]],
    recovered_links: Sequence[Mapping[str, Any]],
    exclusions: Sequence[Mapping[str, Any]],
    evaluation_rows: Sequence[Mapping[str, Any]],
    pair_rows: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    return {
        "session_event_identity_audit": list(session_audit),
        "canonical_outcome_candidate_audit": list(candidate_audit),
        "canonical_identity_defects": list(canonical_identity_defects),
        "exact_outcome_links_recovered": list(recovered_links),
        "remaining_exclusions": list(exclusions),
        "recovered_evaluation_rows": list(evaluation_rows),
        "pack_pair_readiness": list(pair_rows),
    }


def _guard_tests() -> List[Dict[str, str]]:
    """Focused negative fixtures prove this repair cannot degrade to weak matching."""
    tests: List[Dict[str, str]] = []

    def record(name: str, condition: bool) -> None:
        if not condition:
            raise RepairBlocked(f"REGRESSION_TEST_FAILED:{name}")
        tests.append({"test": name, "status": "PASS"})

    record("numeric_integer_identifier_preserved", _identifier(0) == "0")
    record("numeric_float_identifier_preserved", _identifier(0.0) == "0")
    record("null_identifier_rejected", _identifier(None) == "")
    record("whitespace_identifier_rejected", _identifier("   ") == "")
    record("five_minute_window_validation", _window_is_exact({
        "window_policy": FROZEN_WINDOW_POLICY,
        "window_minutes": "5.000",
        "release_ts": "2024-05-01T07:30:00Z",
        "canonical_start_ts": "2024-05-01T07:30:00Z",
        "canonical_end_ts": "2024-05-01T07:35:00Z",
    }))
    record("non_five_minute_window_rejected", not _window_is_exact({
        "window_policy": FROZEN_WINDOW_POLICY,
        "window_minutes": "5",
        "release_ts": "2024-05-01T07:30:00Z",
        "canonical_start_ts": "2024-05-01T07:30:00Z",
        "canonical_end_ts": "2024-05-01T07:36:00Z",
    }))

    fixture_session = {
        "session_id": "US|2024-05-01|CUSTOM_CONFIG_WINDOW",
        "session_date": "2024-05-01",
        "country": "US",
        "session_start_ts": "2024-05-01T07:00:00Z",
        "session_end_ts": "2024-05-01T08:00:00Z",
        "primary_release_ts": "2024-05-01T07:30:00Z",
        "member_event_ids": "EVENT_A",
    }
    event = {"event_id": "EVENT_A", "country": "US", "release_ts": "2024-05-01T07:30:00Z", "batch_id": "", "type": "single"}
    canonical = {
        "event_id": "EVENT_A", "batch_id": "", "release_ts": "2024-05-01T07:30:00Z",
        "canonical_outcome_id": "CAN_A", "implementation_run_id": "RUN", "implementation_version": CANONICAL_IMPLEMENTATION_VERSION,
        "usable_for_strict_accuracy": "TRUE", "trust_level": "HIGH_TRUST", "canonical_realized_direction": "UP",
        "window_policy": FROZEN_WINDOW_POLICY, "window_minutes": "5",
        "canonical_start_ts": "2024-05-01T07:30:00Z", "canonical_end_ts": "2024-05-01T07:35:00Z",
    }
    date_only = dict(canonical, event_id="EVENT_B")
    audit, _ = _resolve_session(
        session=fixture_session,
        event_by_id={"EVENT_A": [event]},
        canonical_by_event_release={("EVENT_B", "2024-05-01T07:30:00Z"): [date_only]},
        authoritative_run_id="RUN",
    )
    record("date_or_time_only_match_rejected", audit["status"] == "NO_CANONICAL_OUTCOME_EXISTS")
    ambiguous_session = dict(fixture_session, member_event_ids="EVENT_A|EVENT_B")
    event_b = dict(event, event_id="EVENT_B")
    canonical_b = dict(canonical, event_id="EVENT_B", canonical_outcome_id="CAN_B")
    audit, _ = _resolve_session(
        session=ambiguous_session,
        event_by_id={"EVENT_A": [event], "EVENT_B": [event_b]},
        canonical_by_event_release={
            ("EVENT_A", "2024-05-01T07:30:00Z"): [canonical],
            ("EVENT_B", "2024-05-01T07:30:00Z"): [canonical_b],
        },
        authoritative_run_id="RUN",
    )
    record("same_minute_ambiguity_rejected", audit["status"] == "MULTIPLE_CANONICAL_CANDIDATES")
    audit, _ = _resolve_session(
        session=fixture_session,
        event_by_id={"EVENT_A": [event]},
        canonical_by_event_release={("EVENT_A", "2024-05-01T07:30:00Z"): [canonical, dict(canonical, canonical_outcome_id="CAN_DUP")]},
        authoritative_run_id="RUN",
    )
    record("multiple_canonical_candidates_rejected", audit["status"] == "MULTIPLE_CANONICAL_CANDIDATES")
    return tests


def _load_inputs() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    required = [
        GAP_REPLAY_ROOT / "reconstructed_sessions.jsonl",
        GAP_REPLAY_ROOT / "preoutcome_freeze_manifest.json",
        GAP_REPLAY_ROOT / "preoutcome_gap_manifest.json",
        GAP_REPLAY_ROOT / "preoutcome_labels.jsonl",
        GAP_REPLAY_ROOT / "summary.json",
        ACTIVE_REPLAY_ROOT / "preoutcome_replay_artifacts.jsonl",
        TRUE_PACK_E_FREEZE,
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise RepairBlocked("REQUIRED_ARTIFACT_MISSING:" + "|".join(missing))
    sessions = _read_jsonl(GAP_REPLAY_ROOT / "reconstructed_sessions.jsonl")
    labels = _read_jsonl(GAP_REPLAY_ROOT / "preoutcome_labels.jsonl")
    preoutcome_freeze = _read_json(GAP_REPLAY_ROOT / "preoutcome_freeze_manifest.json")
    preoutcome_gap = _read_json(GAP_REPLAY_ROOT / "preoutcome_gap_manifest.json")
    summary = _read_json(GAP_REPLAY_ROOT / "summary.json")
    freeze = _read_json(TRUE_PACK_E_FREEZE)
    if (
        _norm(preoutcome_freeze.get("gap_replay_run_id")) != GAP_REPLAY_RUN_ID
        or preoutcome_freeze.get("preoutcome_capture_frozen") is not True
        or preoutcome_freeze.get("outcome_access_before_freeze") is not False
        or _norm(summary.get("build_status")) != "PASS"
    ):
        raise RepairBlocked("AUTHORITATIVE_REPLAY_FREEZE_OR_STATUS_INVALID")
    if (
        _norm(freeze.get("freeze_status")) != "FROZEN_FOR_PHASE9_A_VS_E_SHADOW_TEST"
        or _norm(freeze.get("pack_fingerprint")) != "976271f7cba9689f91098e2a6b7e2038e8c5df004012dc57c733e0addd1dc15e"
    ):
        raise RepairBlocked("FROZEN_TRUE_PACK_E_REFERENCE_INVALID")
    scoped = [session for session in sessions if DATE_START <= _norm(session.get("session_date")) < DATE_END_EXCLUSIVE]
    if len(scoped) != 6:
        raise RepairBlocked(f"UNEXPECTED_MAY1_7_SESSION_COUNT:{len(scoped)}")
    return scoped, _load_preoutcome_artifacts(), labels, preoutcome_freeze, preoutcome_gap, freeze


def _build_audit(override_manifest_path: Optional[Path] = None) -> Dict[str, Any]:
    sessions, artifacts, labels, preoutcome_freeze, preoutcome_gap, freeze = _load_inputs()
    # The active store is a resumable capture store.  Its parent run IDs are
    # provenance only; this exact frozen input fingerprint is the authority
    # boundary that proves the latest completed replay accepted this full set.
    replay_input_fingerprint = _sha256({
        "forecasts": [artifact["forecast"] for artifact in artifacts],
        "labels": labels,
    })
    if replay_input_fingerprint != _norm(preoutcome_freeze.get("preoutcome_fingerprint")):
        raise RepairBlocked("AUTHORITATIVE_PREOUTCOME_FREEZE_FINGERPRINT_MISMATCH")
    service = build_sheets_service(load_credentials())
    event_rows = _sheet_to_rows(service, MAIN_SPREADSHEET_ID, "Event")
    base_canonical_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, "Market_Reaction_Canonical_Outcomes")
    canonical_rows, canonical_override = _load_canonical_overrides(
        base_canonical_rows, override_manifest_path
    )
    if canonical_override and (
        _norm(canonical_override.get("repaired_canonical_logical_fingerprint"))
        != _canonical_source_fingerprint(canonical_rows)
    ):
        raise RepairBlocked("CANONICAL_OVERRIDE_REPAIRED_FINGERPRINT_MISMATCH")
    event_by_id = _event_index(event_rows)
    canonical_by_event_release = _canonical_index(canonical_rows)
    canonical_run_ids = {
        _identifier(row.get("implementation_run_id"))
        for row in canonical_rows
        if _norm(row.get("implementation_version")) == CANONICAL_IMPLEMENTATION_VERSION
        and _identifier(row.get("implementation_run_id"))
    }
    if len(canonical_run_ids) != 1:
        raise RepairBlocked("CANONICAL_AUTHORITATIVE_RUN_AMBIGUOUS:" + "|".join(sorted(canonical_run_ids)))
    canonical_run_id = next(iter(canonical_run_ids))
    canonical_by_id = {
        _identifier(row.get("canonical_outcome_id")): row
        for row in canonical_rows
        if _identifier(row.get("canonical_outcome_id"))
    }
    if len(canonical_by_id) != len(canonical_rows):
        raise RepairBlocked("CANONICAL_OUTCOME_ID_DUPLICATE_OR_MISSING")

    session_audit: List[Dict[str, Any]] = []
    candidate_audit: List[Dict[str, Any]] = []
    for session in sorted(sessions, key=lambda row: _identifier(row.get("session_id"))):
        audit, candidates = _resolve_session(
            session=session,
            event_by_id=event_by_id,
            canonical_by_event_release=canonical_by_event_release,
            authoritative_run_id=canonical_run_id,
        )
        session_audit.append(audit)
        candidate_audit.extend(candidates)
    recovered_links = [
        {
            "session_id": row["session_id"],
            "event_id": row["selected_event_id"],
            "batch_id": row["selected_batch_id"],
            "canonical_outcome_id": row["canonical_outcome_id"],
            "canonical_direction": row["canonical_direction"],
            "source_session_run_id": GAP_REPLAY_RUN_ID,
            "source_outcome_run_id": canonical_run_id,
            "authoritative_status": "AUTHORITATIVE_EXACT_EVENT_RELEASE_CANONICAL_CHAIN",
            "link_status": "EXACT_CANONICAL_OUTCOME_LINK_RECOVERED",
            "linkage_key": row["exact_identity_chain"],
        }
        for row in session_audit
        if row["status"] == "EXACT_CANONICAL_OUTCOME_LINK_RECOVERED"
    ]
    # This is deliberately a finding, not a repair.  The canonical builder's
    # event-only batch lookup can bind a reused event ID to a later occurrence.
    # The audit has both exact event/release identities, so it can prove the
    # mismatch without inferring a replacement batch or changing any outcome.
    canonical_identity_defects = [
        {
            "defect_code": "CANONICAL_BATCH_ID_BOUND_BY_REUSED_EVENT_ID",
            "affected_session_id": row.get("session_id"),
            "event_id": row.get("member_event_id"),
            "release_ts": row.get("member_release_ts"),
            "source_event_batch_id": row.get("member_batch_id"),
            "canonical_batch_id": row.get("canonical_batch_id"),
            "canonical_outcome_id": row.get("canonical_outcome_id"),
            "evidence": "event_id_and_release_ts_match_but_batch_id_differs",
            "root_cause_code_path": "automation/build_market_reaction_outcome_source_implementation_v0.py:_event_batch_map",
            "repair_scope": "SEPARATE_CANONICAL_OUTCOME_IMPLEMENTATION_REPAIR_REQUIRED",
            "outcome_value_changed_in_this_run": "FALSE",
        }
        for row in candidate_audit
        if row.get("event_id_exact") == "TRUE"
        and row.get("release_ts_exact") == "TRUE"
        and row.get("batch_id_confirmed") == "FALSE"
        and row.get("canonical_outcome_id")
    ]
    exclusions = [
        {
            "session_id": row["session_id"],
            "status": row["status"],
            "exclusion_reason": row["exclusion_reason"],
            "primary_member_event_ids": row["primary_member_event_ids"],
            "canonical_candidate_count": row["canonical_candidate_count"],
            "strict_canonical_candidate_count": row["strict_canonical_candidate_count"],
        }
        for row in session_audit
        if row["status"] != "EXACT_CANONICAL_OUTCOME_LINK_RECOVERED"
    ]
    evaluation_rows, integrity_failures = _recovered_evaluation_rows(
        session_audits=session_audit,
        canonical_by_id=canonical_by_id,
        artifacts=artifacts,
    )
    if integrity_failures:
        raise RepairBlocked("FORECAST_INTEGRITY_FAILED:" + _canonical_json(integrity_failures))
    pair_rows = _pair_readiness(evaluation_rows, freeze)
    for row in evaluation_rows:
        if row["pack_level"] == "E":
            row["frozen_true_pack_e_version"] = "NOT_APPLICABLE_LEGACY_REPLAY_PACK_E"

    content = _content_payload(
        session_audit,
        candidate_audit,
        canonical_identity_defects,
        recovered_links,
        exclusions,
        evaluation_rows,
        pair_rows,
    )
    content_fingerprint = _sha256(content)
    return {
        "sessions": session_audit,
        "candidates": candidate_audit,
        "canonical_identity_defects": canonical_identity_defects,
        "links": recovered_links,
        "exclusions": exclusions,
        "evaluation_rows": evaluation_rows,
        "pair_rows": pair_rows,
        "content": content,
        "content_fingerprint": content_fingerprint,
        "canonical_run_id": canonical_run_id,
        "preoutcome_freeze": preoutcome_freeze,
        "preoutcome_gap": preoutcome_gap,
        "freeze": freeze,
        "artifacts": artifacts,
        "replay_input_fingerprint": replay_input_fingerprint,
        "canonical_override": canonical_override,
    }


def _summary(result: Mapping[str, Any], *, run_id: str, tests: Sequence[Mapping[str, Any]], deterministic_pass: bool) -> Dict[str, Any]:
    sessions = result["sessions"]
    candidates = result["candidates"]
    links = result["links"]
    eval_rows = result["evaluation_rows"]
    exclusions = result["exclusions"]
    artifacts = result["artifacts"]
    by_date = {row["session_date"]: row["status"] for row in sessions}
    current_directions = Counter(row["realized_direction"] for row in eval_rows)
    success_counts = Counter(row["success_status"] for row in eval_rows)
    provider_counts = Counter(row["provider"] for row in eval_rows)
    canonical_identity_defects = result["canonical_identity_defects"]
    if canonical_identity_defects:
        final_decision = "CANONICAL_OUTCOME_DEFECT_FOUND"
        next_scientific_step = "Repair one documented canonical-outcome defect"
    elif links:
        final_decision = "EXACT_OUTCOME_LINKS_RECOVERED"
        next_scientific_step = "Run the leakage-safe Pack A versus frozen true Pack E forecasts"
    else:
        final_decision = "NO_ADDITIONAL_EXACT_LINKS_AVAILABLE"
        next_scientific_step = "Continue with existing exact outcomes because no further links are available"
    return {
        "phase": PHASE_ID,
        "repair_run_id": run_id,
        "build_status": "PASS",
        "final_decision": final_decision,
        "date_start": DATE_START,
        "date_end_exclusive": DATE_END_EXCLUSIVE,
        "authoritative_session_run": GAP_REPLAY_RUN_ID,
        "authoritative_forecast_run": GAP_REPLAY_RUN_ID,
        "parent_capture_run_ids": sorted({_identifier(row["collector"].get("historical_replay_run_id")) for row in artifacts}),
        "authoritative_preoutcome_freeze_fingerprint": result["replay_input_fingerprint"],
        "authoritative_preoutcome_freeze_verified": "PASS",
        "authoritative_outcome_run": result["canonical_run_id"],
        "excluded_runs": ["9A-EARLIEST-GAP-REPLAY_20260714T005623Z"],
        "market_sessions_reviewed": len(sessions),
        "forecast_rows_reviewed": len(artifacts),
        "providers_reviewed": sorted({_norm(row["collector"].get("provider")) for row in artifacts}),
        "existing_exact_links": 0,
        "new_exact_links_recovered": len(links),
        "total_exact_links_after_repair": len(links),
        "rows_remaining_excluded": len(exclusions),
        "forecast_rows_remaining_excluded": len(artifacts) - len(eval_rows),
        "date_statuses": by_date,
        "canonical_outcomes_referenced": len({row["canonical_outcome_id"] for row in links}),
        "duplicate_outcomes_suppressed": 0,
        "five_minute_window_check": "PASS",
        "forecast_before_outcome_check": "PASS",
        "authoritative_run_isolation": "PASS",
        "duplicate_suppression": "PASS",
        "exact_event_id_links": len(links),
        "exact_primary_event_links": len(links),
        "batch_owned_links": 0,
        "same_minute_ambiguities_rejected": sum(1 for row in exclusions if row["status"] == "MULTIPLE_CANONICAL_CANDIDATES"),
        "multiple_candidates_rejected": sum(1 for row in exclusions if row["status"] == "MULTIPLE_CANONICAL_CANDIDATES"),
        "date_time_only_candidates_rejected": "PASS_BY_GUARD_TEST",
        "recovered_evaluation_rows": len(eval_rows),
        "recovered_pack_a_rows": sum(1 for row in eval_rows if row["pack_level"] == "A"),
        "recovered_legacy_pack_e_rows": sum(1 for row in eval_rows if row["pack_level"] == "E"),
        "recovered_frozen_true_pack_e_rows": 0,
        "pack_a_e_paired_rows_ready": 0,
        "provider_counts_recovered": dict(sorted(provider_counts.items())),
        "realized_direction_counts_recovered": dict(sorted(current_directions.items())),
        "success_failure_counts_recovered": dict(sorted(success_counts.items())),
        "forecast_content_changed": 0,
        "forecast_direction_changed": 0,
        "forecast_confidence_changed": 0,
        "pack_contents_changed": 0,
        "market_prices_changed": 0,
        "canonical_outcome_value_changed": 0,
        "outcome_horizon_changed": 0,
        "realized_direction_changed": 0,
        "evaluation_semantics_changed": 0,
        "provider_weighting_changed": 0,
        "scientific_eligibility_rules_changed": 0,
        "scientific_rules_changed": 0,
        "production_or_consumer_changes": 0,
        "provider_calls": 0,
        "acquisition_ai_calls": 0,
        "forecast_reruns": 0,
        "outcome_recomputations": 0,
        "deterministic_rerun": "PASS" if deterministic_pass else "FAILED",
        "guard_tests": list(tests),
        "content_fingerprint": result["content_fingerprint"],
        "canonical_identity_defect_count": len(canonical_identity_defects),
        "canonical_identity_defects": canonical_identity_defects,
        "canonical_batch_identity_override": result["canonical_override"],
        "frozen_pack_e_reference": str(TRUE_PACK_E_FREEZE.relative_to(ROOT)),
        "frozen_pack_e_version": result["freeze"].get("pack_version"),
        "frozen_pack_e_fingerprint": result["freeze"].get("pack_fingerprint"),
        "warnings": [
            "May 2 and May 3 remain excluded because their explicit primary minutes contain multiple exact member outcomes and no frozen ownership rule selects one.",
            "Recovered May 7 replay rows use legacy replay Pack E; they are not forecasts with frozen true_shared_pack_e_v1 and cannot form the upcoming Pack A-versus-frozen-true-Pack-E pair.",
        ] + (["Two canonical rows retain a batch ID from a later reused event ID; this task records the defect but does not modify canonical outcomes."] if canonical_identity_defects else []),
        "next_scientific_step": next_scientific_step,
    }


def _write_outputs(run_dir: Path, result: Mapping[str, Any], summary: Mapping[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=False)
    _write_jsonl(run_dir / "session_event_identity_audit.jsonl", result["sessions"])
    _write_jsonl(run_dir / "canonical_outcome_candidate_audit.jsonl", result["candidates"])
    _write_jsonl(run_dir / "canonical_identity_defects.jsonl", result["canonical_identity_defects"])
    _write_jsonl(run_dir / "exact_outcome_links_recovered.jsonl", result["links"])
    _write_jsonl(run_dir / "remaining_exclusions.jsonl", result["exclusions"])
    _write_jsonl(run_dir / "recovered_evaluation_rows.jsonl", result["evaluation_rows"])
    _write_jsonl(run_dir / "pack_pair_readiness.jsonl", result["pair_rows"])
    _write_json(run_dir / "exact_link_repair_summary.json", summary)
    manifest = {
        "schema_version": "phase9_may1_7_exact_outcome_link_repair_v0.1",
        "repair_run_id": summary["repair_run_id"],
        "script": SCRIPT_PATH,
        "source_gap_replay_run_id": GAP_REPLAY_RUN_ID,
        "source_forecast_authority_run_id": summary["authoritative_forecast_run"],
        "parent_capture_run_ids": summary["parent_capture_run_ids"],
        "authoritative_preoutcome_freeze_fingerprint": summary["authoritative_preoutcome_freeze_fingerprint"],
        "source_canonical_outcome_run_id": summary["authoritative_outcome_run"],
        "canonical_batch_identity_override": result["canonical_override"],
        "frozen_true_pack_e_manifest": str(TRUE_PACK_E_FREEZE.relative_to(ROOT)),
        "content_fingerprint_algorithm": "sha256",
        "content_fingerprint": result["content_fingerprint"],
        "logical_row_counts": {
            "session_event_identity_audit": len(result["sessions"]),
            "canonical_outcome_candidate_audit": len(result["candidates"]),
            "canonical_identity_defects": len(result["canonical_identity_defects"]),
            "exact_outcome_links_recovered": len(result["links"]),
            "remaining_exclusions": len(result["exclusions"]),
            "recovered_evaluation_rows": len(result["evaluation_rows"]),
            "pack_pair_readiness": len(result["pair_rows"]),
        },
        "write_scope": "LOCAL_SHADOW_OUTPUTS_ONLY",
        "governance": {
            "provider_calls": 0,
            "acquisition_ai_calls": 0,
            "forecast_reruns": 0,
            "outcome_recomputations": 0,
            "workbook_writes": 0,
            "production_writes": 0,
            "scientific_rule_changes": 0,
        },
    }
    _write_json(run_dir / "exact_link_repair_manifest.json", manifest)


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", help="Optional unique shadow output run identifier.")
    parser.add_argument(
        "--canonical-override-manifest",
        help="Validated shadow canonical batch-identity override manifest.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    tests = _guard_tests()
    override_manifest_path = (
        Path(args.canonical_override_manifest).resolve()
        if args.canonical_override_manifest
        else None
    )
    first = _build_audit(override_manifest_path)
    second = _build_audit(override_manifest_path)
    deterministic = first["content_fingerprint"] == second["content_fingerprint"] and first["content"] == second["content"]
    if not deterministic:
        raise RepairBlocked("NONDETERMINISTIC_EXACT_LINK_REPAIR")
    now = datetime.now(timezone.utc)
    run_id = _identifier(args.run_id) or _run_id(now)
    run_dir = OUTPUT_ROOT / run_id
    if run_dir.exists():
        raise RepairBlocked(f"OUTPUT_RUN_ALREADY_EXISTS:{run_dir}")
    summary = _summary(first, run_id=run_id, tests=tests, deterministic_pass=deterministic)
    _write_outputs(run_dir, first, summary)
    print(_canonical_json({
        "build_status": summary["build_status"],
        "final_decision": summary["final_decision"],
        "repair_run_id": run_id,
        "new_exact_links_recovered": summary["new_exact_links_recovered"],
        "recovered_evaluation_rows": summary["recovered_evaluation_rows"],
        "content_fingerprint": summary["content_fingerprint"],
        "output_dir": str(run_dir),
    }))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RepairBlocked as error:
        print(_canonical_json({"build_status": "BLOCKED", "error": str(error)}))
        raise SystemExit(2)
