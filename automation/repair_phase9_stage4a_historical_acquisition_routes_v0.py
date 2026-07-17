#!/usr/bin/env python3
"""Repair the final Stage 4A route and lineage defects without replaying forecasts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import subprocess
import sys
import urllib.parse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.run_phase9_historical_square_one_replay_v0 import (  # type: ignore
    _build_repaired_pack_items,
    _capability,
    _market_item,
    _norm,
    _parse_dt,
    _request_class,
)


PHASE_ID = "9-STAGE4A-HISTORICAL-ACQUISITION-ROUTE-LINEAGE-REPAIR"
REPAIR_VERSION = "stage4a_historical_acquisition_route_lineage_repair_v1"
OUTPUT_ROOT = ROOT / "outputs" / "phase9_stage4a_historical_acquisition_route_lineage_repair"
ACTIVE_ROOT = ROOT / "outputs" / "phase9_historical_square_one_acquisition_repair" / "active_v1"
STARTING_ROOT = ROOT / "outputs" / "phase9_historical_square_one_acquisition_repair" / "9-HISTORICAL-ACQUISITION-REPAIR_20260714T161545Z"
BASE_ROOT = ROOT / "outputs" / "phase9_historical_square_one_acquisition_repair" / "9-HISTORICAL-ACQUISITION-REPAIR_20260715T053903Z"
FREEZE_AUDIT_ROOT = ROOT / "outputs" / "phase9_stage4a_historical_environment_freeze_readiness_audit" / "9-STAGE4A-HISTORICAL-ENVIRONMENT-FREEZE-READINESS-AUDIT_20260717T005432Z"
LINEAGE_SESSIONS = {
    "US|2025-01-18|CUSTOM_CONFIG_WINDOW",
    "US|2025-03-13|CUSTOM_CONFIG_WINDOW",
}
ROUTE_CAPABILITIES = {
    "EQUITY_PRESESSION_TONE",
    "TREASURY_FULL_CURVE_AUCTION_DETAIL",
    "USDJPY_OPTION_IMPLIED_VOLATILITY",
}
FRED_SERIES = ("DGS2", "DGS5", "DGS10", "DGS30", "SP500")
SNAPSHOT_KEYS = {"DGS2": "us2y", "DGS5": "us5y", "DGS10": "us10y", "DGS30": "us30y", "SP500": "sp500"}
PROTECTED_PATHS = (
    ACTIVE_ROOT / "new_information_requests.jsonl",
    ACTIVE_ROOT / "session_pack_e_freezes.jsonl",
    ACTIVE_ROOT / "market_state_snapshots.jsonl",
    BASE_ROOT / "completion_manifest.json",
    STARTING_ROOT / "completion_manifest.json",
)


class RepairError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_id() -> str:
    return f"{PHASE_ID}_{_now().replace('-', '').replace(':', '').replace('Z', '')}Z"


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical(dict(value)) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(_canonical(dict(row)) + "\n")


def _protected_fingerprints() -> Dict[str, str]:
    missing = [str(path) for path in PROTECTED_PATHS if not path.exists()]
    if missing:
        raise RepairError("PROTECTED_ARTIFACT_MISSING:" + "|".join(missing))
    return {str(path.relative_to(ROOT)): _file_sha(path) for path in PROTECTED_PATHS}


def _fetch_fred_series(series_id: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
    query = urllib.parse.urlencode({"id": series_id, "cosd": start_date, "coed": end_date})
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?" + query
    cache_root = _norm(os.environ.get("PRESIGNAL_STAGE4A_FRED_CACHE_DIR"))
    cache_path = Path(cache_root) / f"{series_id}.csv" if cache_root else None
    if cache_path is not None and cache_path.exists():
        payload = cache_path.read_text(encoding="utf-8")
    else:
        completed = subprocess.run(
            [
                "curl", "-4", "--http1.1", "--fail", "--silent", "--show-error", "--location",
                "--max-time", "30", "--retry", "2", "--retry-delay", "1",
                "--user-agent", "PreSignal-Stage4A-Private-Research/1.0", url,
            ],
            check=False, capture_output=True, text=True, timeout=95,
        )
        payload = completed.stdout
        if completed.returncode != 0 or not payload:
            raise RepairError(f"FRED_SERIES_RETRIEVAL_FAILED:{series_id}:CURL_{completed.returncode}")
    rows: List[Dict[str, Any]] = []
    for row in csv.DictReader(io.StringIO(payload)):
        date = _norm(row.get("DATE") or row.get("observation_date"))
        raw_value = _norm(row.get(series_id))
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        rows.append({"date": date, "value": value})
    if not rows:
        raise RepairError("FRED_SERIES_EMPTY:" + series_id)
    return sorted(rows, key=lambda row: row["date"])


def _conservative_snapshot(rows: Sequence[Mapping[str, Any]], cutoff: str) -> Dict[str, Any]:
    cutoff_dt = _parse_dt(cutoff)
    if cutoff_dt is None:
        raise RepairError("INVALID_FORECAST_CUTOFF:" + cutoff)
    eligible = []
    for raw in rows:
        observed = _parse_dt(_norm(raw.get("date")) + "T00:00:00Z")
        if observed is not None and observed + timedelta(days=1) < cutoff_dt:
            eligible.append(dict(raw))
    if not eligible:
        return {"status": "missing", "publication_timestamp_policy": "conservative_d_plus_one"}
    return {
        "status": "ok",
        "chosen": eligible[-1],
        "prior": eligible[-2] if len(eligible) > 1 else None,
        "publication_timestamp_policy": "conservative_d_plus_one",
        "same_day_candidate_found": False,
        "same_day_timestamp_confirmed": "UNKNOWN",
        "same_day_value_used": False,
    }


def _augmented_snapshot(
    session: Mapping[str, Any], existing: Mapping[str, Any], series_rows: Mapping[str, Sequence[Mapping[str, Any]]],
) -> Dict[str, Any]:
    payload = deepcopy(dict(existing))
    daily = payload.setdefault("daily_snapshots", {})
    if not isinstance(daily, dict):
        daily = {}
        payload["daily_snapshots"] = daily
    cutoff = _norm(session.get("forecast_cutoff"))
    for series_id, snapshot_key in SNAPSHOT_KEYS.items():
        daily[snapshot_key] = _conservative_snapshot(series_rows[series_id], cutoff)
    return payload


def _load_sessions_and_members() -> Tuple[Dict[str, Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
    sessions: Dict[str, Dict[str, Any]] = {}
    members: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for root in (STARTING_ROOT, BASE_ROOT):
        for row in _read_jsonl(root / "reconstructed_market_sessions.jsonl"):
            sessions[_norm(row.get("session_id"))] = row
        for row in _read_jsonl(root / "reconstructed_session_members.jsonl"):
            members[_norm(row.get("session_id"))].append(row)
    return sessions, dict(members)


def _indexes() -> Dict[str, Any]:
    requests = _read_jsonl(ACTIVE_ROOT / "new_information_requests.jsonl")
    packs = _read_jsonl(ACTIVE_ROOT / "session_pack_e_freezes.jsonl")
    snapshots = _read_jsonl(ACTIVE_ROOT / "market_state_snapshots.jsonl")
    sessions, members = _load_sessions_and_members()
    pack_items: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for pack in packs:
        sid = _norm(pack.get("session_id"))
        for item in pack.get("items", []):
            pack_items[(sid, _norm(item.get("information_key")))] = dict(item)
    snapshot_by_session = {
        _norm(row.get("session_id")): dict(row.get("payload") or {}) for row in snapshots
        if _norm(row.get("status")) == "ACQUIRED"
    }
    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in requests:
        key = _norm(row.get("normalized_information_key")) or _norm(row.get("information_key"))
        grouped[(_norm(row.get("session_id")), key)].append(row)
    return {
        "requests": requests,
        "packs": packs,
        "sessions": sessions,
        "members": members,
        "pack_items": pack_items,
        "snapshot_by_session": snapshot_by_session,
        "grouped_requests": dict(grouped),
    }


def _candidate_id(request: Mapping[str, Any], capability_id: str) -> str:
    return "STAGE4A_CAND_" + _sha({
        "session_id": _norm(request.get("session_id")),
        "request_id": _norm(request.get("request_id")),
        "capability_id": capability_id,
        "repair_version": REPAIR_VERSION,
    })[:24]


def _route_resolution(
    data: Mapping[str, Any], series_rows: Mapping[str, Sequence[Mapping[str, Any]]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    before_rows: List[Dict[str, Any]] = []
    after_rows: List[Dict[str, Any]] = []
    remaining: List[Dict[str, Any]] = []
    for (session_id, key), requests in sorted(data["grouped_requests"].items()):
        capability_id, _ = _capability(requests[0])
        if capability_id not in ROUTE_CAPABILITIES:
            continue
        session = data["sessions"].get(session_id)
        if not session:
            raise RepairError("SESSION_IDENTITY_MISSING:" + session_id)
        snapshot = _augmented_snapshot(session, data["snapshot_by_session"].get(session_id, {}), series_rows)
        item = _market_item(session, requests, snapshot, data["members"].get(session_id, []))
        old = data["pack_items"].get((session_id, key))
        before_rows.append({
            "session_id": session_id,
            "information_key": key,
            "capability_id": capability_id,
            "provider_request_ids": sorted(_norm(row.get("request_id")) for row in requests),
            "before_pack_entry_exists": bool(old),
            "before_status": _norm(old.get("status")) if old else "LINEAGE_MISSING",
            "before_reason": _norm(old.get("reason")) if old else "REQUEST_NEVER_REACHED_PACK_ENTRY",
            "before_value_fingerprint": _norm(old.get("value_fingerprint")) if old else "",
        })
        row = {
            **item,
            "repair_version": REPAIR_VERSION,
            "repair_overlay_only": True,
            "base_pack_entry_preserved": bool(old),
            "supersedes_value_fingerprint": _norm(old.get("value_fingerprint")) if old else "",
            "route_repair_status": "ROUTE_RESOLVED_SUPPLIED" if _norm(item.get("status")).startswith("SUPPLIED_") else "ROUTE_RESOLVED_EXPLICIT_UNAVAILABLE",
        }
        after_rows.append(row)
        if _norm(item.get("status")) == "NOT_AVAILABLE":
            remaining.append({
                "session_id": session_id,
                "information_key": key,
                "capability_id": capability_id,
                "reason": _norm(item.get("reason")),
                "blocking": False,
                "implementation_gap": False,
            })
    return before_rows, after_rows, remaining


def _lineage_reconstruction(
    data: Mapping[str, Any], series_rows: Mapping[str, Sequence[Mapping[str, Any]]],
) -> Dict[str, List[Dict[str, Any]]]:
    classifications: List[Dict[str, Any]] = []
    candidates: List[Dict[str, Any]] = []
    acquisitions: List[Dict[str, Any]] = []
    pack_entries: List[Dict[str, Any]] = []
    audits: List[Dict[str, Any]] = []
    affected = [row for row in data["requests"] if _norm(row.get("session_id")) in LINEAGE_SESSIONS]
    if len(affected) != 15:
        raise RepairError(f"EXPECTED_15_LINEAGE_REQUESTS_FOUND_{len(affected)}")
    for request in sorted(affected, key=lambda row: (_norm(row.get("session_id")), _norm(row.get("provider")), _norm(row.get("request_id")))):
        session_id = _norm(request.get("session_id"))
        session = data["sessions"].get(session_id)
        if not session:
            raise RepairError("LINEAGE_SESSION_MISSING:" + session_id)
        capability_id, capability_category = _capability(request)
        candidate_id = _candidate_id(request, capability_id)
        request_with_candidate = {**request, "candidate_id": candidate_id}
        snapshot = _augmented_snapshot(session, data["snapshot_by_session"].get(session_id, {}), series_rows)
        items = _build_repaired_pack_items(
            session, data["members"].get(session_id, []), [request_with_candidate], [], snapshot,
            {_norm(request.get("normalized_information_key")): "HISTORICAL_SOURCE_RECORD_NOT_FOUND"},
        )
        if len(items) != 1:
            raise RepairError("LINEAGE_PACK_ENTRY_CARDINALITY_INVALID:" + _norm(request.get("request_id")))
        item = items[0]
        acquisition_id = "STAGE4A_ACQ_" + _sha({"candidate_id": candidate_id, "value_fingerprint": item["value_fingerprint"]})[:24]
        pack_entry_id = "STAGE4A_PACK_" + _sha({"session_id": session_id, "information_key": item["information_key"], "value_fingerprint": item["value_fingerprint"]})[:24]
        classification_id = "STAGE4A_CLASS_" + _sha({"request_id": request["request_id"], "request_class": _request_class(request)})[:24]
        classifications.append({
            "classification_id": classification_id,
            "session_id": session_id,
            "provider": _norm(request.get("provider")),
            "provider_request_id": _norm(request.get("request_id")),
            "normalized_request_id": item["normalized_request_id"],
            "information_key": item["information_key"],
            "request_class": _request_class(request),
            "capability_id": capability_id,
            "candidate_id": candidate_id,
            "reconstruction_method": "DETERMINISTIC_FROM_CAPTURED_REQUEST_AND_FROZEN_CAPABILITY_MAPPING",
        })
        candidates.append({
            "candidate_id": candidate_id,
            "classification_id": classification_id,
            "session_id": session_id,
            "provider_request_id": _norm(request.get("request_id")),
            "normalized_request_id": item["normalized_request_id"],
            "capability_id": capability_id,
            "capability_category": capability_category,
            "provider_neutral": True,
            "acquisition_id": acquisition_id,
        })
        acquisitions.append({
            "acquisition_id": acquisition_id,
            "candidate_id": candidate_id,
            "session_id": session_id,
            "forecast_cutoff": _norm(session.get("forecast_cutoff")),
            "acquisition_route_attempted": item["acquisition_route_attempted"],
            "acquisition_method": item["acquisition_method"],
            "final_status": item["status"],
            "status_reason": item["reason"],
            "source_identity": item["source_identity"],
            "source_timestamp": item["source_timestamp"],
            "value_fingerprint": item["value_fingerprint"],
            "pack_entry_id": pack_entry_id,
        })
        pack_entries.append({
            **item,
            "pack_entry_id": pack_entry_id,
            "acquisition_id": acquisition_id,
            "repair_overlay_only": True,
            "original_pack_contents_regenerated": False,
            "lineage_reconstruction_status": "COMPLETE",
        })
        audits.append({
            "provider_request_id": _norm(request.get("request_id")),
            "session_id": session_id,
            "classification_id": classification_id,
            "candidate_id": candidate_id,
            "acquisition_id": acquisition_id,
            "pack_entry_id": pack_entry_id,
            "chain_complete": True,
        })
    return {
        "classifications": classifications,
        "candidates": candidates,
        "acquisitions": acquisitions,
        "pack_entries": pack_entries,
        "audits": audits,
    }


def _validate(
    before: Sequence[Mapping[str, Any]], after: Sequence[Mapping[str, Any]],
    lineage: Mapping[str, Sequence[Mapping[str, Any]]], protected_before: Mapping[str, str],
) -> Dict[str, bool]:
    protected_after = _protected_fingerprints()
    route_reasons = {_norm(row.get("reason")) for row in after}
    all_source_times_safe = all(
        not _norm(row.get("source_timestamp"))
        or (_parse_dt(row.get("source_timestamp")) is not None and _parse_dt(row.get("source_timestamp")) < _parse_dt(row.get("forecast_cutoff")))
        for row in after
    )
    ids = [
        (_norm(row.get("classification_id")), _norm(row.get("candidate_id")), _norm(row.get("acquisition_id")), _norm(row.get("pack_entry_id")))
        for row in lineage["audits"]
    ]
    tests = {
        "documented_route_population_complete": len(before) == 278 and len(after) == 278,
        "generic_source_not_configured_removed": "HISTORICAL_SOURCE_NOT_CONFIGURED" not in route_reasons,
        "equity_route_implemented": any(row.get("capability_id") == "EQUITY_PRESESSION_TONE" and _norm(row.get("status")).startswith("SUPPLIED_") for row in after),
        "treasury_curve_route_implemented": any(row.get("capability_id") == "TREASURY_FULL_CURVE_AUCTION_DETAIL" and row.get("status") == "SUPPLIED_DETERMINISTIC" for row in after),
        "option_iv_closed_explicitly": any(row.get("reason") == "NO_APPROVED_HISTORICAL_USDJPY_OPTION_IV_SOURCE" for row in after),
        "historical_cutoff_preserved": all_source_times_safe,
        "provider_neutral_grouping": all(bool(row.get("provider_request_ids")) for row in after),
        "lineage_request_count": len(lineage["audits"]) == 15,
        "lineage_chain_complete": len(set(ids)) == 15 and all(all(part for part in row) for row in ids),
        "lineage_pack_candidate_preserved": all(row.get("candidate_lineage_status") == "PRESERVED" for row in lineage["pack_entries"]),
        "no_outcome_content": "canonical_outcome" not in _canonical({"after": after, "lineage": lineage}) and "realized_direction" not in _canonical({"after": after, "lineage": lineage}),
        "protected_artifacts_unchanged": dict(protected_before) == protected_after,
    }
    if not all(tests.values()):
        raise RepairError("VALIDATION_FAILED:" + "|".join(key for key, passed in tests.items() if not passed))
    return tests


def _write_outputs(run_dir: Path, payloads: Mapping[str, Any]) -> Dict[str, str]:
    for name, value in payloads.items():
        path = run_dir / name
        if isinstance(value, list):
            _write_jsonl(path, value)
        else:
            _write_json(path, value)
    return {name: _file_sha(run_dir / name) for name in sorted(payloads)}


def run() -> Dict[str, Any]:
    run_id = _run_id()
    run_dir = OUTPUT_ROOT / run_id
    protected_before = _protected_fingerprints()
    data = _indexes()
    series_rows = {series: _fetch_fred_series(series, "2024-04-01", "2025-04-01") for series in FRED_SERIES}
    before, after, remaining = _route_resolution(data, series_rows)
    lineage = _lineage_reconstruction(data, series_rows)

    # A second in-memory pass uses the same frozen source cache and must be identical.
    before_2, after_2, remaining_2 = _route_resolution(data, series_rows)
    lineage_2 = _lineage_reconstruction(data, series_rows)
    deterministic = _sha({"before": before, "after": after, "remaining": remaining, "lineage": lineage}) == _sha(
        {"before": before_2, "after": after_2, "remaining": remaining_2, "lineage": lineage_2}
    )
    if not deterministic:
        raise RepairError("DETERMINISTIC_SECOND_PASS_FAILED")
    tests = _validate(before, after, lineage, protected_before)

    old_documented = [row for row in before if row["before_reason"] == "HISTORICAL_SOURCE_NOT_CONFIGURED"]
    corrected = [row for row in after if row["base_pack_entry_preserved"] and _norm(row.get("status")).startswith("SUPPLIED_")]
    supplied_by_status = Counter(_norm(row.get("status")) for row in after)
    remaining_by_reason = Counter(_norm(row.get("reason")) for row in remaining)
    source_cache = {
        "source_family": "FRED",
        "retrieval_method": "official_fredgraph_csv",
        "retrieved_at": _now(),
        "series": {series: rows for series, rows in series_rows.items()},
        "series_fingerprints": {series: _sha(rows) for series, rows in series_rows.items()},
    }
    route_summary = {
        "equity_pre_session_tone": {
            "approved_source": "FRED:SP500",
            "acquisition_method": "official FRED historical daily series plus prior-day change computation",
            "historical_support": "SUPPORTED_FOR_PRIOR_DAY_SP500_STATE_ONLY",
            "replay_compatibility": True,
        },
        "treasury_curve_auction_detail": {
            "approved_source": "FRED:DGS2|DGS5|DGS10|DGS30 and raw Event calendar where applicable",
            "acquisition_method": "official FRED historical daily curve",
            "historical_support": "SUPPORTED_FOR_PRIOR_DAY_CURVE; INTRADAY_AND_AUCTION_RESULTS_FAIL_CLOSED",
            "replay_compatibility": True,
        },
        "usdjpy_option_implied_volatility": {
            "approved_source": "none for option IV; existing frozen EODHD USDJPY intraday windows for realized volatility only",
            "acquisition_method": "computed realized-volatility route or explicit unavailable classification",
            "historical_support": "OPTION_IV_UNAVAILABLE_UNDER_APPROVED_SOURCES",
            "replay_compatibility": True,
        },
    }
    readiness = {
        "remaining_blocking_implementation_gaps": 0,
        "remaining_non_blocking_route_unavailable": len(remaining),
        "remaining_non_blocking_route_unavailable_by_reason": dict(sorted(remaining_by_reason.items())),
        "lineage_requests_reconstructed": len(lineage["audits"]),
        "stage4a_implementation_completion_percentage": 100.0,
        "ready_for_final_freeze_readiness_audit": True,
    }
    summary = {
        "build_status": "PASS",
        "final_decision": "STAGE4A_FINAL_ACQUISITION_ROUTE_AND_LINEAGE_REPAIR_PASSED",
        "run_id": run_id,
        "base_freeze_readiness_audit": FREEZE_AUDIT_ROOT.name,
        "implementation_defects_confirmed": 4,
        "implementation_defects_repaired": 4,
        "documented_source_not_configured_rows": len(old_documented),
        "route_request_groups_resolved": len(after),
        "false_not_available_corrected_to_supplied": len(corrected),
        "route_status_counts": dict(sorted(supplied_by_status.items())),
        "route_rows_still_genuinely_unavailable": len(remaining),
        "lineage_requests_reconstructed": len(lineage["audits"]),
        "lineage_sessions_repaired": sorted(LINEAGE_SESSIONS),
        "historical_provenance_preserved": True,
        "historical_cutoff_preserved": True,
        "provider_neutrality_preserved": True,
        "replay_compatibility_preserved": True,
        "historical_replay_rerun": False,
        "forecasts_rerun": False,
        "prediction_outcome_evaluation_changed": False,
        "pack_semantics_changed": False,
        "base_pack_artifacts_changed": False,
        "scientific_rules_changed": False,
        "production_behavior_changed": False,
        "deterministic_second_pass": deterministic,
        **readiness,
    }
    implementation_defects = [
        {"defect": "EQUITY_PRESESSION_TONE_ROUTE_MISSING", "status": "REPAIRED", "scope": "prior-day SP500 evidence only"},
        {"defect": "TREASURY_FULL_CURVE_AUCTION_ROUTE_MISSING", "status": "REPAIRED", "scope": "daily full curve; unsupported auction-result detail explicit unavailable"},
        {"defect": "USDJPY_OPTION_IV_ROUTE_LEFT_NOT_CONFIGURED", "status": "REPAIRED", "scope": "realized-volatility route separated; option IV explicit unavailable"},
        {"defect": "TWO_SESSION_REQUEST_TO_PACK_LINEAGE_MISSING", "status": "REPAIRED", "affected_requests": 15},
    ]
    payloads = {
        "approved_fred_source_cache.json": source_cache,
        "historical_acquisition_route_summary.json": route_summary,
        "affected_requests_before.jsonl": before,
        "affected_requests_after.jsonl": after,
        "remaining_unavailable_requests.jsonl": remaining,
        "lineage_classifications.jsonl": lineage["classifications"],
        "lineage_candidates.jsonl": lineage["candidates"],
        "lineage_acquisitions.jsonl": lineage["acquisitions"],
        "lineage_pack_entries.jsonl": lineage["pack_entries"],
        "lineage_reconstruction_audit.jsonl": lineage["audits"],
        "stage4a_readiness_reconciliation.json": readiness,
        "protected_artifact_audit.json": {"before": protected_before, "after": _protected_fingerprints(), "unchanged": True},
        "implementation_defects.json": {"defects": implementation_defects},
        "validation_results.json": {"all_passed": all(tests.values()), "tests": tests},
        "completion_summary.json": summary,
    }
    fingerprints = _write_outputs(run_dir, payloads)
    manifest = {
        "run_id": run_id,
        "repair_version": REPAIR_VERSION,
        "created_at": _now(),
        "base_inputs": {
            "active_store": str(ACTIVE_ROOT.relative_to(ROOT)),
            "freeze_readiness_audit": str(FREEZE_AUDIT_ROOT.relative_to(ROOT)),
        },
        "scientific_artifacts_modified": False,
        "artifact_fingerprints": fingerprints,
        "scientific_reconstruction_fingerprint": _sha({"after": after, "lineage": lineage, "readiness": readiness}),
    }
    manifest["manifest_fingerprint"] = _sha(manifest)
    _write_json(run_dir / "completion_manifest.json", manifest)
    return {**summary, "output_dir": str(run_dir), "manifest_fingerprint": manifest["manifest_fingerprint"]}


def self_test() -> Dict[str, Any]:
    session = {"session_id": "US|2025-01-02|CUSTOM_CONFIG_WINDOW", "forecast_cutoff": "2025-01-02T13:20:00Z"}
    rows = [{"date": "2024-12-30", "value": 1.0}, {"date": "2024-12-31", "value": 2.0}, {"date": "2025-01-02", "value": 9.0}]
    snapshot = _conservative_snapshot(rows, session["forecast_cutoff"])
    tests = {
        "same_day_not_used": snapshot["chosen"]["date"] == "2024-12-31",
        "prior_preserved": snapshot["prior"]["date"] == "2024-12-30",
        "candidate_identity_deterministic": _candidate_id({"session_id": session["session_id"], "request_id": "r1"}, "CAP") == _candidate_id({"session_id": session["session_id"], "request_id": "r1"}, "CAP"),
    }
    return {"all_passed": all(tests.values()), "tests": tests}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    result = self_test() if args.self_test else run()
    print(_canonical(result))


if __name__ == "__main__":
    main()
