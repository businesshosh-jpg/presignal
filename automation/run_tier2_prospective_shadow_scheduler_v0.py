#!/usr/bin/env python3
"""Run the shadow-only prospective Tier 2 scheduler.

The scheduler reads only pre-outcome Market_Sessions and Market_State_Pack_Shadow
inputs. It queues one provider task per future, complete Pack A-E session and
invokes the existing Tier 2 runner with exact session/provider/pack identities.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, MutableMapping, Sequence, Tuple

import fcntl

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_pack_behavior_tier2_execution_v0 import (
    ACTIVE_PACK_LEVELS,
    DIAGNOSTICS_SPREADSHEET_ID,
    INPUT_SESSIONS_SHEET,
    INPUT_SHADOW_SHEET,
    INPUT_SHADOW_SUMMARY_SHEET,
    MAIN_CONFIG_SHEET,
    MAIN_SPREADSHEET_ID,
    PROVIDER_ORDER,
    _capture_prospective_mechanism_evidence,
    _complete_shadow_sessions,
    _filter_by_run,
    _latest_run_id,
)
from automation.build_market_sessions_shadow_v0 import _sheet_to_rows
from automation.build_session_information_requests_v0 import _read_config_map, _resolve_provider_candidates
from automation.collect_mechanism_evaluation_population_shadow_v0 import (
    COLLECTION_CONTRACT_VERSION,
    MECHANISM_DEFINITION_VERSION,
    PRIMARY_CLASSIFICATION_AUTHORITY_VERSION,
    _read_jsonl,
    activate_prospective_shadow_collection,
)
from automation.google_clients import build_sheets_service, load_credentials


SCHEDULER_VERSION = "phase9a_tier2_prospective_shadow_scheduler_v1"
SCHEDULER_SCHEMA_VERSION = "presignal_phase9a_tier2_prospective_scheduler_v0"
SCHEDULER_LABEL = "com.presignal.phase9a.tier2.prospective-shadow"
TIMEZONE = "UTC"
PRE_OUTCOME_LEAD_SECONDS = 600
SCHEDULER_INTERVAL_SECONDS = 60
MAX_CONCURRENT_SESSIONS = 1
MAX_INITIAL_PROVIDER_CALLS_PER_SESSION = len(ACTIVE_PACK_LEVELS) * len(PROVIDER_ORDER)
MAX_RETRY_PROVIDER_CALLS_PER_SESSION = len(ACTIVE_PACK_LEVELS)
MAX_PROVIDER_RETRIES = 1
RUNNER_TIMEOUT_SECONDS = 300
DISCOVERY_LOOKBACK_SECONDS = 3600
PROHIBITED_SOURCE_FIELDS = {
    "realized_direction",
    "correctness",
    "overall_ok",
    "provider_performance",
    "accuracy_result",
    "post_session_explanation",
}
ACTIVE_ROOT = ROOT / "outputs" / "phase9a_prospective_tier2_scheduler" / "active_v1"
CONTRACT_PATH = (
    ROOT
    / "outputs"
    / "phase9a_evaluation_population_repair"
    / "9A-E2E-POPULATION-REPAIR_20260713T084129Z"
    / "prospective_shadow_collection_contract.json"
)
RUNNER_PATH = ROOT / "automation" / "build_pack_behavior_tier2_execution_v0.py"
PHASE9_A_VS_E_PIPELINE_PATH = ROOT / "automation" / "run_phase9_prospective_a_vs_e_pipeline_v0.py"


class SchedulerError(RuntimeError):
    """Raised for a deterministic scheduler safety failure."""


def _norm(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return str(value).strip()


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _now_iso(now: datetime | None = None) -> str:
    value = now or datetime.now(timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_utc(value: Any) -> datetime | None:
    raw = _norm(value)
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _paths(root: Path) -> Dict[str, Path]:
    return {
        "config": root / "scheduler_config.json",
        "manifest": root / "activation_manifest.json",
        "queue": root / "queue_state.json",
        "attempts": root / "execution_attempts.jsonl",
        "status": root / "scheduler_status.json",
        "lock": root / ".scheduler.lock",
        "disabled": root / "DISABLED",
        "logs": root / "logs",
    }


@contextmanager
def _locked(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    paths = _paths(root)
    with paths["lock"].open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(_canonical_json(dict(payload)) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _read_json(path: Path, default: Mapping[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SchedulerError(f"MALFORMED_SCHEDULER_STATE:{path.name}") from exc
    if not isinstance(value, dict):
        raise SchedulerError(f"INVALID_SCHEDULER_STATE:{path.name}")
    return value


def _append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(_canonical_json(dict(payload)) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _state(root: Path) -> Dict[str, Any]:
    return _read_json(root / "queue_state.json", {"schema_version": SCHEDULER_SCHEMA_VERSION, "jobs": {}})


def _queue_identity(session_id: str, provider: str) -> str:
    return "|".join(
        [
            "TIER2_PROSPECTIVE",
            MECHANISM_DEFINITION_VERSION,
            PRIMARY_CLASSIFICATION_AUTHORITY_VERSION,
            _norm(session_id),
            _norm(provider),
            "A-E",
        ]
    )


def _scheduled_execution_identity(session_id: str, provider: str) -> str:
    return "T2S_" + _sha256(_queue_identity(session_id, provider))[:20]


def _source_outcome_fields(rows: Iterable[Mapping[str, Any]]) -> List[str]:
    found = set()
    for row in rows:
        for field in PROHIBITED_SOURCE_FIELDS:
            if field in row and _norm(row.get(field)):
                found.add(field)
    return sorted(found)


def _timing_from_session(row: Mapping[str, Any]) -> Tuple[datetime, datetime, datetime] | None:
    release = _parse_utc(row.get("primary_release_ts"))
    if release is None:
        return None
    outcome_end = release + timedelta(minutes=5)
    planned = release - timedelta(seconds=PRE_OUTCOME_LEAD_SECONDS)
    return release, outcome_end, planned


def _session_index(session_rows: Sequence[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}
    timing_fields = ("session_start_ts", "session_end_ts", "primary_release_ts", "last_release_ts")
    for raw in session_rows:
        session_id = _norm(raw.get("session_id"))
        if not session_id:
            continue
        row = dict(raw)
        existing = index.get(session_id)
        if existing is not None:
            before = tuple(_norm(existing.get(field)) for field in timing_fields)
            after = tuple(_norm(row.get(field)) for field in timing_fields)
            if before != after:
                raise SchedulerError(f"SESSION_TIMESTAMP_AMBIGUITY:{session_id}")
            continue
        index[session_id] = row
    return index


def _enabled_provider_rows(config_rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    config = {_upper(row.get("key")): _norm(row.get("value")) for row in config_rows if _norm(row.get("key"))}
    candidates = {row["provider"]: row for row in _resolve_provider_candidates(config)}
    return [
        {
            "provider": provider,
            "configured": provider in candidates,
            "enabled": provider in candidates,
            "model": _norm(candidates.get(provider, {}).get("model")),
            "credential_status": "UNVERIFIED_NO_PROVIDER_CALL",
        }
        for provider in PROVIDER_ORDER
    ]


def _live_inputs() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    credentials = load_credentials(interactive=False)
    service = build_sheets_service(credentials)
    session_rows = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, INPUT_SESSIONS_SHEET)
    shadow_summary = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, INPUT_SHADOW_SUMMARY_SHEET)
    shadow_run_id = _latest_run_id(shadow_summary, "shadow_pack_run_id")
    shadow_rows = _filter_by_run(
        _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, INPUT_SHADOW_SHEET),
        "shadow_pack_run_id",
        shadow_run_id,
    )
    config_rows = _sheet_to_rows(service, MAIN_SPREADSHEET_ID, MAIN_CONFIG_SHEET)
    return session_rows, shadow_rows, config_rows


def _new_job(
    session: Mapping[str, Any], provider: str, now: datetime
) -> Dict[str, Any]:
    timing = _timing_from_session(session)
    if timing is None:
        raise SchedulerError("MISSING_PRIMARY_RELEASE_TIMESTAMP")
    release, outcome_end, planned = timing
    identity = _queue_identity(_norm(session.get("session_id")), provider)
    return {
        "queue_identity": identity,
        "scheduled_execution_identity": _scheduled_execution_identity(_norm(session.get("session_id")), provider),
        "session_id": _norm(session.get("session_id")),
        "provider": provider,
        "model": "",
        "mechanism_version": MECHANISM_DEFINITION_VERSION,
        "classification_authority_version": PRIMARY_CLASSIFICATION_AUTHORITY_VERSION,
        "expected_pack_levels": list(ACTIVE_PACK_LEVELS),
        "completed_pack_levels": [],
        "failed_pack_levels": [],
        "attempt_count": 0,
        "provider_run_identity": "",
        "primary_release_ts": _now_iso(release),
        "frozen_outcome_window_start": _now_iso(release),
        "frozen_outcome_window_end": _now_iso(outcome_end),
        "required_pre_outcome_capture_deadline": _now_iso(release),
        "planned_tier2_execution_ts": _now_iso(planned),
        "timezone": TIMEZONE,
        "status": "QUEUED",
        "failure_code": "",
        "created_timestamp": _now_iso(now),
        "updated_timestamp": _now_iso(now),
        "source_lineage": "Market_Sessions|Market_State_Pack_Shadow",
    }


def _reconcile_queue(
    state: MutableMapping[str, Any],
    session_rows: Sequence[Mapping[str, Any]],
    shadow_rows: Sequence[Mapping[str, Any]],
    provider_rows: Sequence[Mapping[str, Any]],
    now: datetime,
) -> Dict[str, Any]:
    jobs = state.setdefault("jobs", {})
    sessions = _session_index(session_rows)
    forbidden = _source_outcome_fields(list(session_rows) + list(shadow_rows))
    if forbidden:
        return {"created": 0, "ineligible": 0, "blocked": "OUTCOME_LEAKAGE_SOURCE_FIELD:" + "|".join(forbidden)}
    complete = {session_id for _, session_id in _complete_shadow_sessions(shadow_rows)}
    enabled = [row["provider"] for row in provider_rows if row.get("enabled")]
    created = 0
    ineligible = 0
    for session_id in sorted(complete):
        session = sessions.get(session_id)
        if session is None:
            ineligible += 1
            continue
        timing = _timing_from_session(session)
        if timing is None:
            ineligible += 1
            continue
        release, _, _ = timing
        # Do not manufacture missed records for unrelated old history. Existing
        # queued jobs still receive an explicit missed-deadline disposition.
        if release < now - timedelta(seconds=DISCOVERY_LOOKBACK_SECONDS):
            continue
        for provider in enabled:
            key = _queue_identity(session_id, provider)
            if key not in jobs:
                jobs[key] = _new_job(session, provider, now)
                jobs[key]["model"] = next((_norm(row.get("model")) for row in provider_rows if row.get("provider") == provider), "")
                created += 1
    for job in jobs.values():
        deadline = _parse_utc(job.get("required_pre_outcome_capture_deadline"))
        if deadline and now >= deadline and job.get("status") not in {"COMPLETED", "FAILED_CLOSED", "INELIGIBLE", "DISABLED"}:
            job["status"] = "MISSED_PREOUTCOME_DEADLINE"
            job["failure_code"] = "MISSED_PREOUTCOME_DEADLINE"
            job["updated_timestamp"] = _now_iso(now)
    return {"created": created, "ineligible": ineligible, "blocked": ""}


def _due_jobs(state: Mapping[str, Any], now: datetime) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for job in state.get("jobs", {}).values():
        if job.get("status") not in {"QUEUED", "RETRY_PENDING"}:
            continue
        planned = _parse_utc(job.get("planned_tier2_execution_ts"))
        deadline = _parse_utc(job.get("required_pre_outcome_capture_deadline"))
        if planned is None or deadline is None or now >= deadline or now < planned:
            continue
        candidates.append(job)
    candidates.sort(key=lambda row: (row["planned_tier2_execution_ts"], row["session_id"], row["provider"]))
    allowed_sessions: List[str] = []
    selected: List[Dict[str, Any]] = []
    for job in candidates:
        session_id = job["session_id"]
        if session_id not in allowed_sessions:
            if len(allowed_sessions) >= MAX_CONCURRENT_SESSIONS:
                continue
            allowed_sessions.append(session_id)
        selected.append(job)
    return selected


def _pending_packs(job: Mapping[str, Any]) -> List[str]:
    completed = set(job.get("completed_pack_levels", []))
    return [pack for pack in job.get("expected_pack_levels", []) if pack not in completed]


def _retry_budget_available(state: Mapping[str, Any], session_id: str, requested_calls: int) -> bool:
    used = sum(
        int(job.get("retry_provider_call_count", 0))
        for job in state.get("jobs", {}).values()
        if _norm(job.get("session_id")) == _norm(session_id)
    )
    return used + requested_calls <= MAX_RETRY_PROVIDER_CALLS_PER_SESSION


def _runner_command(job: Mapping[str, Any], packs: Sequence[str]) -> List[str]:
    command = [
        sys.executable,
        str(RUNNER_PATH),
        "--prospective-session-id",
        job["session_id"],
        "--prospective-provider",
        job["provider"],
        "--prospective-scheduled-execution-id",
        job["scheduled_execution_identity"],
    ]
    for pack in packs:
        command.extend(["--prospective-pack-level", pack])
    return command


def _real_executor(job: Mapping[str, Any], packs: Sequence[str]) -> Dict[str, Any]:
    command = _runner_command(job, packs)
    result = subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=RUNNER_TIMEOUT_SECONDS,
        check=False,
    )
    if result.returncode != 0:
        return {
            "ok": False,
            "failure_code": f"TIER2_RUNNER_EXIT_{result.returncode}",
            "detail": result.stderr[-1000:] or result.stdout[-1000:],
            "command": command,
            "provider_pack_status": [],
        }
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {
            "ok": False,
            "failure_code": "TIER2_RUNNER_NON_JSON_RESULT",
            "detail": result.stdout[-1000:],
            "command": command,
            "provider_pack_status": [],
        }
    return {"ok": True, "command": command, **payload}


def _apply_result(job: MutableMapping[str, Any], result: Mapping[str, Any], now: datetime) -> Dict[str, Any]:
    expected = set(_pending_packs(job))
    successful: List[str] = []
    failed: List[str] = []
    for row in result.get("provider_pack_status", []):
        pack = _upper(row.get("pack_level"))
        if pack not in expected:
            continue
        good = (
            _upper(row.get("response_status")) == "OK"
            and _upper(row.get("json_validation_success")) == "TRUE"
            and _upper(row.get("collector_status")) in {"COLLECTED", "DUPLICATE_SUPPRESSED"}
        )
        (successful if good else failed).append(pack)
    missing = expected - set(successful) - set(failed)
    failed.extend(sorted(missing))
    completed = sorted(set(job.get("completed_pack_levels", [])) | set(successful))
    job["completed_pack_levels"] = completed
    job["failed_pack_levels"] = sorted(set(failed))
    job["attempt_count"] = int(job.get("attempt_count", 0)) + 1
    job["provider_run_identity"] = _norm(result.get("discovery_run_id"))
    job["updated_timestamp"] = _now_iso(now)
    deadline = _parse_utc(job.get("required_pre_outcome_capture_deadline"))
    if set(completed) == set(job.get("expected_pack_levels", [])):
        job["status"] = "COMPLETED"
        job["failure_code"] = ""
    elif deadline is not None and now >= deadline:
        job["status"] = "MISSED_PREOUTCOME_DEADLINE"
        job["failure_code"] = "MISSED_PREOUTCOME_DEADLINE"
    elif job["attempt_count"] <= MAX_PROVIDER_RETRIES:
        job["status"] = "RETRY_PENDING"
        job["failure_code"] = _norm(result.get("failure_code")) or "PARTIAL_PROVIDER_FAILURE"
    else:
        job["status"] = "FAILED_CLOSED"
        job["failure_code"] = _norm(result.get("failure_code")) or "RETRY_LIMIT_EXHAUSTED"
    return {"successful": sorted(set(successful)), "failed": sorted(set(failed)), "status": job["status"]}


def _status_payload(state: Mapping[str, Any], provider_rows: Sequence[Mapping[str, Any]], now: datetime, **extra: Any) -> Dict[str, Any]:
    jobs = list(state.get("jobs", {}).values())
    counts = {status: sum(1 for job in jobs if job.get("status") == status) for status in (
        "QUEUED", "RUNNING", "COMPLETED", "PARTIAL_PROVIDER_FAILURE", "RETRY_PENDING",
        "MISSED_PREOUTCOME_DEADLINE", "INELIGIBLE", "DISABLED", "FAILED_CLOSED",
    )}
    next_jobs = sorted(
        [job for job in jobs if job.get("status") in {"QUEUED", "RETRY_PENDING"}],
        key=lambda job: (job.get("planned_tier2_execution_ts", ""), job.get("session_id", "")),
    )[:10]
    return {
        "schema_version": SCHEDULER_SCHEMA_VERSION,
        "scheduler_version": SCHEDULER_VERSION,
        "generated_timestamp": _now_iso(now),
        "scheduler_entry_point": "python3 automation/run_tier2_prospective_shadow_scheduler_v0.py --active",
        "tier2_entry_point": str(RUNNER_PATH),
        "session_source": "Market_Sessions + latest Market_State_Pack_Shadow",
        "eligibility_rule": "future exact Market_Sessions row + complete deterministic Pack A-E shadow + pre-outcome primary_release_ts",
        "timezone": TIMEZONE,
        "pre_outcome_lead_time_seconds": PRE_OUTCOME_LEAD_SECONDS,
        "enabled_providers": [row["provider"] for row in provider_rows if row.get("enabled")],
        "provider_status": list(provider_rows),
        "retry_policy": f"max_provider_retries={MAX_PROVIDER_RETRIES}; retry only incomplete Pack levels before deadline",
        "maximum_initial_provider_calls_per_session": MAX_INITIAL_PROVIDER_CALLS_PER_SESSION,
        "maximum_retry_provider_calls_per_session": MAX_RETRY_PROVIDER_CALLS_PER_SESSION,
        "maximum_concurrently_processed_sessions": MAX_CONCURRENT_SESSIONS,
        "dry_run_available": True,
        "kill_switch": str(_paths(ACTIVE_ROOT)["disabled"]),
        "collector_bridge_status": "TIER2_RUNNER_INVOKES_ACTIVE_PROSPECTIVE_COLLECTOR",
        "queue_identity_rule": "session_id|provider|mechanism_version|classification_authority_version|A-E",
        "observation_identity_rule": "collector scientific_observation_key remains authoritative",
        "queued_sessions": counts["QUEUED"],
        "completed_sessions": counts["COMPLETED"],
        "partial_sessions": counts["PARTIAL_PROVIDER_FAILURE"] + counts["RETRY_PENDING"],
        "missed_deadline_sessions": counts["MISSED_PREOUTCOME_DEADLINE"],
        "failed_closed_sessions": counts["FAILED_CLOSED"],
        "next_known_eligible_sessions": next_jobs,
        "durable_log_location": str(_paths(ACTIVE_ROOT)["attempts"]),
        "shadow_only": True,
        "production_authority": False,
        "consumer_switch": False,
        **extra,
    }


def _run_phase9_a_vs_e_pipeline_tick(dry_run: bool) -> Dict[str, Any]:
    """Invoke the request-driven A/E child through the existing scheduler only.

    A child failure is visible in scheduler status but cannot block the legacy
    Tier 2 shadow run or change operational forecast behavior.
    """
    if not PHASE9_A_VS_E_PIPELINE_PATH.exists():
        return {"status": "FAILED_CLOSED", "failure_code": "MISSING_A_VS_E_PIPELINE_ENTRY_POINT"}
    command = [sys.executable, str(PHASE9_A_VS_E_PIPELINE_PATH), "--scheduler-tick"]
    if dry_run:
        command.append("--scheduler-dry-run")
    try:
        completed = subprocess.run(command, cwd=str(ROOT), check=False, capture_output=True, text=True, timeout=300)
    except Exception as exc:
        return {"status": "FAILED_CLOSED", "failure_code": "A_VS_E_PIPELINE_EXECUTION_ERROR", "error": str(exc)}
    if completed.returncode != 0:
        return {"status": "FAILED_CLOSED", "failure_code": "A_VS_E_PIPELINE_NONZERO_EXIT", "error": completed.stderr[-1000:]}
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"status": "FAILED_CLOSED", "failure_code": "A_VS_E_PIPELINE_INVALID_JSON", "error": completed.stdout[-1000:]}
    if not isinstance(payload, dict):
        return {"status": "FAILED_CLOSED", "failure_code": "A_VS_E_PIPELINE_NONOBJECT_RESPONSE"}
    return {"status": _norm(payload.get("collector_status")) or "ACTIVE_SHADOW_ONLY", "result": payload}


def run_once(
    *,
    root: Path = ACTIVE_ROOT,
    dry_run: bool,
    now: datetime | None = None,
    source_rows: Tuple[Sequence[Mapping[str, Any]], Sequence[Mapping[str, Any]], Sequence[Mapping[str, Any]]] | None = None,
    executor: Callable[[Mapping[str, Any], Sequence[str]], Dict[str, Any]] = _real_executor,
) -> Dict[str, Any]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    with _locked(root):
        paths = _paths(root)
        config = _read_json(paths["config"], {"enabled": False})
        state = _state(root)
        if source_rows is None:
            source_rows = _live_inputs()
        session_rows, shadow_rows, config_rows = source_rows
        provider_rows = _enabled_provider_rows(config_rows)
        reconciliation = _reconcile_queue(state, session_rows, shadow_rows, provider_rows, current)
        if reconciliation["blocked"]:
            state["status"] = "FAILED_CLOSED"
            state["failure_code"] = reconciliation["blocked"]
        disabled = paths["disabled"].exists() or not bool(config.get("enabled"))
        due = [] if disabled or reconciliation["blocked"] else _due_jobs(state, current)
        attempt_results: List[Dict[str, Any]] = []
        if not dry_run:
            for job in due:
                prior_status = _norm(job.get("status"))
                job["status"] = "RUNNING"
                packs = _pending_packs(job)
                if prior_status == "RETRY_PENDING" and not _retry_budget_available(state, job["session_id"], len(packs)):
                    job["status"] = "FAILED_CLOSED"
                    job["failure_code"] = "RETRY_CALL_BUDGET_EXHAUSTED"
                    job["updated_timestamp"] = _now_iso(current)
                    attempt = {
                        "timestamp": _now_iso(current),
                        "queue_identity": job["queue_identity"],
                        "scheduled_execution_identity": job["scheduled_execution_identity"],
                        "session_id": job["session_id"],
                        "provider": job["provider"],
                        "packs_requested": packs,
                        "result_status": job["status"],
                        "successful_packs": [],
                        "failed_packs": packs,
                        "provider_run_identity": job.get("provider_run_identity", ""),
                        "failure_code": job["failure_code"],
                        "shadow_only": True,
                        "outcome_access": 0,
                        "production_writes": 0,
                    }
                    _append_jsonl(paths["attempts"], attempt)
                    attempt_results.append(attempt)
                    continue
                result = executor(job, packs)
                applied = _apply_result(job, result, current)
                job["provider_call_count"] = int(job.get("provider_call_count", 0)) + len(packs)
                if prior_status == "RETRY_PENDING":
                    job["retry_provider_call_count"] = int(job.get("retry_provider_call_count", 0)) + len(packs)
                attempt = {
                    "timestamp": _now_iso(current),
                    "queue_identity": job["queue_identity"],
                    "scheduled_execution_identity": job["scheduled_execution_identity"],
                    "session_id": job["session_id"],
                    "provider": job["provider"],
                    "packs_requested": packs,
                    "result_status": applied["status"],
                    "successful_packs": applied["successful"],
                    "failed_packs": applied["failed"],
                    "provider_run_identity": job.get("provider_run_identity", ""),
                    "failure_code": job.get("failure_code", ""),
                    "shadow_only": True,
                    "outcome_access": 0,
                    "production_writes": 0,
                }
                _append_jsonl(paths["attempts"], attempt)
                attempt_results.append(attempt)
        for job in state.get("jobs", {}).values():
            if disabled and job.get("status") in {"QUEUED", "RETRY_PENDING"}:
                job["status"] = "DISABLED"
                job["failure_code"] = "SCHEDULER_KILL_SWITCH_OR_DISABLED"
                job["updated_timestamp"] = _now_iso(current)
        state["updated_timestamp"] = _now_iso(current)
        _atomic_json(paths["queue"], state)
        # Do not create a second scheduler.  The request-driven Pack A/E flow is
        # a non-blocking child of this existing pre-outcome scheduler and is not
        # invoked from fixture roots used by the Tier 2 scheduler self-test.
        pipeline_bridge = (
            _run_phase9_a_vs_e_pipeline_tick(dry_run)
            if root == ACTIVE_ROOT and not disabled
            else {"status": "NOT_INVOKED_FOR_FIXTURE_OR_DISABLED"}
        )
        status = _status_payload(
            state,
            provider_rows,
            current,
            activation_run_id=_read_json(paths["manifest"], {}).get("activation_run_id", ""),
            initial_execution_state=_read_json(paths["manifest"], {}).get("initial_execution_state", "MANUAL_ONLY"),
            final_execution_state=_read_json(paths["manifest"], {}).get("final_execution_state", "AUTOMATICALLY_SCHEDULED"),
            activation_self_test=_read_json(paths["manifest"], {}).get("self_test", {}),
            scheduler_status="DRY_RUN" if dry_run else ("DISABLED" if disabled else "ACTIVE_SHADOW_ONLY"),
            reconciliation=reconciliation,
            due_job_count=len(due),
            attempts_this_run=attempt_results,
            last_success=next((row for row in reversed(attempt_results) if row["result_status"] == "COMPLETED"), {}),
            last_failure=next((row for row in reversed(attempt_results) if row["result_status"] != "COMPLETED"), {}),
            phase9_a_vs_e_pipeline_bridge=pipeline_bridge,
        )
        _atomic_json(paths["status"], status)
        return status


def _fixture_sources(release: str = "2031-01-02T13:30:00Z") -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    session_id = "US|2031-01-02|CUSTOM_CONFIG_WINDOW"
    session = {
        "session_id": session_id,
        "session_date": "2031-01-02",
        "session_start_ts": "2031-01-02T13:00:00Z",
        "session_end_ts": "2031-01-02T13:30:00Z",
        "primary_release_ts": release,
        "last_release_ts": release,
    }
    fields = []
    for field in sorted(set(__import__("automation.build_pack_behavior_tier2_execution_v0", fromlist=["EXPECTED_FIELDS_BY_LEVEL"]).EXPECTED_FIELDS_BY_LEVEL["E"])):
        fields.append({
            "session_id": session_id,
            "session_date": "2031-01-02",
            "candidate_field": field,
            "data_available_flag": "TRUE",
            "leakage_check_status": "PASS",
            "provider_visible": "FALSE",
            "used_in_forecast": "FALSE",
        })
    config = [
        {"key": "OPENAI_ENABLED", "value": "TRUE"}, {"key": "OPENAI_MODEL", "value": "gpt-4o-mini"},
        {"key": "GEMINI_ENABLED", "value": "TRUE"}, {"key": "GEMINI_MODEL", "value": "gemini-2.5-flash-lite"},
        {"key": "ANTHROPIC_ENABLED", "value": "TRUE"}, {"key": "ANTHROPIC_MODEL", "value": "claude-haiku-4-5"},
    ]
    return [session], fields, config


def _fake_executor(successful_packs: Sequence[str]) -> Callable[[Mapping[str, Any], Sequence[str]], Dict[str, Any]]:
    def execute(job: Mapping[str, Any], packs: Sequence[str]) -> Dict[str, Any]:
        rows = []
        for pack in packs:
            success = pack in successful_packs
            rows.append({
                "pack_level": pack,
                "response_status": "ok" if success else "provider_error",
                "json_validation_success": "TRUE" if success else "FALSE",
                "collector_status": "COLLECTED" if success else "COLLECTOR_FAILED_ISOLATED",
            })
        return {"ok": True, "discovery_run_id": "fixture_provider_run", "provider_pack_status": rows}
    return execute


def run_self_test() -> Dict[str, Any]:
    now = datetime(2031, 1, 2, 13, 21, tzinfo=timezone.utc)
    source = _fixture_sources()
    with tempfile.TemporaryDirectory(prefix="presignal-tier2-scheduler-") as temp:
        root = Path(temp)
        _atomic_json(_paths(root)["config"], {"enabled": True})
        initial = run_once(root=root, dry_run=True, now=now, source_rows=source)
        state = _state(root)
        jobs = list(state["jobs"].values())
        due = _due_jobs(state, now)
        selected = due[0]
        completed_key = selected["queue_identity"]
        state["jobs"][completed_key]["status"] = "COMPLETED"
        before = len(state["jobs"])
        _reconcile_queue(state, *source, now)
        after = len(state["jobs"])
        partial_job = next(job for job in state["jobs"].values() if job["queue_identity"] != completed_key)
        partial = _apply_result(partial_job, _fake_executor(["A"])(partial_job, list(ACTIVE_PACK_LEVELS)), now)
        partial_job["retry_provider_call_count"] = MAX_RETRY_PROVIDER_CALLS_PER_SESSION
        missed_source = _fixture_sources("2031-01-02T13:20:00Z")
        missed_state = {"schema_version": SCHEDULER_SCHEMA_VERSION, "jobs": {}}
        _reconcile_queue(missed_state, *missed_source, now)
        timezone_release = _parse_utc("2031-01-02T00:05:00+09:00")
        source_code = RUNNER_PATH.read_text(encoding="utf-8")
        leakage_source = _fixture_sources()
        leakage_source[1][0]["realized_direction"] = "UP"
        leakage_state = {"schema_version": SCHEDULER_SCHEMA_VERSION, "jobs": {}}
        leakage = _reconcile_queue(leakage_state, *leakage_source, now)
        tests = {
            "eligible_future_session": len(jobs) == 3 and initial["due_job_count"] == 3,
            "ineligible_session": _reconcile_queue({"jobs": {}}, source[0], source[1][:-1], _enabled_provider_rows(source[2]), now)["created"] == 0,
            "completed_observation": before == after and completed_key not in {job["queue_identity"] for job in _due_jobs(state, now)},
            "partial_provider_failure": partial["status"] == "RETRY_PENDING" and partial_job["completed_pack_levels"] == ["A"] and "A" not in _pending_packs(partial_job),
            "rate_limit_protection": not _retry_budget_available(state, partial_job["session_id"], 1),
            "missed_deadline": all(job["status"] == "MISSED_PREOUTCOME_DEADLINE" for job in missed_state["jobs"].values()),
            "timezone_boundary": timezone_release is not None and _now_iso(timezone_release) == "2031-01-01T15:05:00Z",
            "restart_rerun": before == after,
            "collector_bridge": "_capture_prospective_mechanism_evidence(" in source_code and "collector_result" in source_code,
            "outcome_leakage": leakage["blocked"].startswith("OUTCOME_LEAKAGE_SOURCE_FIELD"),
            "operational_non_modification": initial["production_authority"] is False and initial["consumer_switch"] is False,
        }
        bridge_root = root / "collector_bridge_fixture"
        activate_prospective_shadow_collection(
            output_root=bridge_root,
            contract_path=str(CONTRACT_PATH),
            integration_entry_point="scheduler fixture -> exact Tier 2 collector bridge",
            enabled_providers=PROVIDER_ORDER,
            eligible_session_rule="fixture pre-outcome session only",
            activation_run_id="TIER2_SCHEDULER_SELF_TEST",
        )
        active_root = root / "active_path_fixture"
        _atomic_json(_paths(active_root)["config"], {"enabled": True})
        executed_commands: List[List[str]] = []

        def bridge_executor(job: Mapping[str, Any], packs: Sequence[str]) -> Dict[str, Any]:
            executed_commands.append(_runner_command(job, packs))
            pack_results = []
            session_meta = dict(source[0][0])
            for pack in packs:
                result = _capture_prospective_mechanism_evidence(
                    discovery_run_id="tier2_scheduler_fixture_run",
                    session_meta=session_meta,
                    forecast_row={
                        "execution_run_id": "tier2_scheduler_fixture_run",
                        "session_id": job["session_id"],
                        "session_date": "2031-01-02",
                        "session_window_name": "CUSTOM_CONFIG_WINDOW",
                        "provider": job["provider"],
                        "model": "fixture-model",
                        "pack_level": pack,
                        "forecast_direction": "UP",
                        "forecast_confidence": "MODERATE",
                    },
                    behavior_row={
                        "output_valid": "TRUE",
                        "no_signal_flag": "FALSE",
                        "no_signal_reason": "",
                        "primary_driver_summary": "fixture",
                        "secondary_driver_summary": "fixture",
                        "information_used": "[]",
                        "information_not_used": "[]",
                        "pack_fields_used": "[]",
                        "pack_fields_discarded": "[]",
                        "uncertainty_sources": "[]",
                        "missing_information": "[]",
                    },
                    raw_response_archive_key=f"scheduler-fixture|{job['provider']}|{pack}",
                    capture_timestamp="2031-01-02T13:21:00Z",
                    collection_root=bridge_root,
                )
                pack_results.append(
                    {
                        "pack_level": pack,
                        "response_status": "ok" if result.get("collection_status") == "COLLECTED" else "collector_error",
                        "json_validation_success": "TRUE",
                        "collector_status": result.get("collection_status", ""),
                    }
                )
            return {
                "ok": True,
                "discovery_run_id": "tier2_scheduler_fixture_run",
                "provider_pack_status": pack_results,
            }

        active_result = run_once(
            root=active_root,
            dry_run=False,
            now=now,
            source_rows=source,
            executor=bridge_executor,
        )
        collected_records = _read_jsonl(bridge_root / "preoutcome_records.jsonl")
        tests["collector_bridge"] = (
            active_result["completed_sessions"] == 3
            and len(collected_records) == 15
            and len(executed_commands) == 3
            and all("--prospective-session-id" in command and "--prospective-provider" in command for command in executed_commands)
            and "_capture_prospective_mechanism_evidence(" in source_code
        )
    return {"all_passed": all(tests.values()), "tests": tests}


def _launch_agent_payload() -> Dict[str, Any]:
    paths = _paths(ACTIVE_ROOT)
    return {
        "Label": SCHEDULER_LABEL,
        "ProgramArguments": [sys.executable, str(Path(__file__).resolve()), "--active"],
        "WorkingDirectory": str(ROOT),
        "StartInterval": SCHEDULER_INTERVAL_SECONDS,
        "RunAtLoad": False,
        "ProcessType": "Background",
        "StandardOutPath": str(paths["logs"] / "scheduler.stdout.log"),
        "StandardErrorPath": str(paths["logs"] / "scheduler.stderr.log"),
    }


def activate_launch_agent() -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    test = run_self_test()
    if not test["all_passed"]:
        raise SchedulerError("SCHEDULER_SELF_TEST_FAILED")
    if not CONTRACT_PATH.exists():
        raise SchedulerError("MISSING_PROSPECTIVE_COLLECTION_CONTRACT")
    with _locked(ACTIVE_ROOT):
        paths = _paths(ACTIVE_ROOT)
        paths["logs"].mkdir(parents=True, exist_ok=True)
        _atomic_json(paths["config"], {
            "enabled": True,
            "shadow_only": True,
            "production_authority": False,
            "consumer_switch": False,
            "activation_timestamp": _now_iso(now),
            "scheduler_version": SCHEDULER_VERSION,
        })
        paths["disabled"].unlink(missing_ok=True)
        _atomic_json(paths["manifest"], {
            "schema_version": SCHEDULER_SCHEMA_VERSION,
            "activation_run_id": "9A-TIER2-AUTO-ACTIVATION_" + now.strftime("%Y%m%dT%H%M%SZ"),
            "scheduler_version": SCHEDULER_VERSION,
            "initial_execution_state": "MANUAL_ONLY",
            "final_execution_state": "AUTOMATICALLY_SCHEDULED",
            "shadow_only": True,
            "production_authority": False,
            "consumer_switch": False,
            "collector_contract_version": COLLECTION_CONTRACT_VERSION,
            "collection_contract_path": str(CONTRACT_PATH),
            "launch_agent_label": SCHEDULER_LABEL,
            "self_test": test,
            "created_timestamp": _now_iso(now),
        })
    dry_run_status = run_once(root=ACTIVE_ROOT, dry_run=True)
    plist_path = Path.home() / "Library" / "LaunchAgents" / f"{SCHEDULER_LABEL}.plist"
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    with plist_path.open("wb") as handle:
        plistlib.dump(_launch_agent_payload(), handle, sort_keys=True)
    domain = f"gui/{os.getuid()}"
    subprocess.run(["launchctl", "bootout", domain, str(plist_path)], check=False, capture_output=True, text=True)
    launched = subprocess.run(["launchctl", "bootstrap", domain, str(plist_path)], check=False, capture_output=True, text=True)
    launch_status = "LOADED" if launched.returncode == 0 else "EXTERNAL_ENABLEMENT_REQUIRED"
    status = {
        **dry_run_status,
        "activation_run_id": _read_json(_paths(ACTIVE_ROOT)["manifest"], {}).get("activation_run_id", ""),
        "initial_execution_state": "MANUAL_ONLY",
        "final_execution_state": "AUTOMATICALLY_SCHEDULED" if launch_status == "LOADED" else "REPOSITORY_AUTOMATION_READY",
        "launch_agent_path": str(plist_path),
        "launch_agent_status": launch_status,
        "launch_agent_error": launched.stderr.strip(),
        "self_test": test,
    }
    _atomic_json(_paths(ACTIVE_ROOT)["status"], status)
    return status


def main() -> None:
    parser = argparse.ArgumentParser(description="Run or activate the Phase 9A prospective Tier 2 shadow scheduler.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--active", action="store_true", help="Run one active scheduler tick.")
    group.add_argument("--dry-run", action="store_true", help="Discover and queue without provider calls.")
    group.add_argument("--self-test", action="store_true", help="Run deterministic fixture coverage only.")
    group.add_argument("--activate", action="store_true", help="Run fixture tests, write state, and load the user launch agent.")
    args = parser.parse_args()
    if args.self_test:
        result = run_self_test()
    elif args.activate:
        result = activate_launch_agent()
    else:
        result = run_once(root=ACTIVE_ROOT, dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
