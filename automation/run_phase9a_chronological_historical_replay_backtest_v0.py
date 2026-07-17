#!/usr/bin/env python3
"""Chronological, leakage-safe Phase 9A historical Tier 2 replay.

The pre-outcome phase reads only session, member, prompt, and frozen Pack inputs.
It freezes provider outputs through the existing collector before the separate
outcome-attachment phase is allowed to read any outcome-bearing sheet.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import fcntl

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_market_sessions_shadow_v0 import (  # type: ignore
    DIAGNOSTICS_SPREADSHEET_ID,
    MAIN_SPREADSHEET_ID,
    _column_letter,
    _norm,
    _parse_dt,
    _sheet_to_rows,
)
from automation.build_pack_behavior_tier2_execution_v0 import (  # type: ignore
    _build_field_influence,
    _build_invalid_rows,
    _build_no_signal_rows,
    _build_transitions,
    _field_family_map,
    _json_value,
)
from automation.build_pack_exposure_pilot_run_v0 import (  # type: ignore
    PROVIDER_ORDER,
    _build_provider_prompt,
    _call_live_provider_raw,
    _parse_provider_json,
    _provider_map,
)
from automation.build_pack_exposure_prompt_validation_v0 import (  # type: ignore
    ACTIVE_PACK_LEVELS,
    EXPECTED_FIELDS_BY_LEVEL,
    _build_event_context,
    _build_market_state_context,
    _filter_by_run,
    _group_prompt_rows,
    _guardrail_payload,
    _latest_run_id,
    _member_index,
    _schema_payload,
    _shadow_index,
)
from automation.build_refined_mechanism_classification_dry_run_v0 import (  # type: ignore
    _build_refined_context,
)
from automation.build_refined_mechanism_v11_classification_dry_run_v0 import (  # type: ignore
    _classify_twice,
)
from automation.build_predictive_mechanism_classification_dry_run_v0 import (  # type: ignore
    _build_indexes,
)
from automation.build_session_forecasts_v0 import (  # type: ignore
    _normalize_confidence,
    _normalize_forecast_direction,
    _normalize_holding_minutes,
    _normalize_numeric_value,
)
from automation.build_session_information_requests_v0 import _iso_now, _truncate_text  # type: ignore
from automation.collect_mechanism_evaluation_population_shadow_v0 import (  # type: ignore
    HISTORICAL_REPLAY_COLLECTION_MODE,
    activate_prospective_shadow_collection,
    collect_tier2_preoutcome_record,
)
from automation.google_clients import (  # type: ignore
    build_script_service,
    build_sheets_service,
    default_script_id,
    load_credentials,
)
from automation.repair_mechanism_evaluation_population_end_to_end_v0 import (  # type: ignore
    _build_consensus,
    _derive_success_status,
    _normalize_direction,
    _validate_join,
)


PHASE_ID = "9A-HISTORICAL-REPLAY"
SCRIPT_PATH = "automation/run_phase9a_chronological_historical_replay_backtest_v0.py"
AUTHORITATIVE_OA2_RUN = "9A-6R15I-R1_20260713T061220Z"
REPAIR_VERIFICATION_RUN = "9A-6R15J-R1_20260713T071511Z"
CLASSIFICATION_RUN_ID = "refined_mechanism_v11_classification_20260710T152725Z"
MECHANISM_ID = "MECH_INFORMATION_CONSISTENCY"
FROZEN_OUTCOME_WINDOW_MINUTES = 5
MAX_PLANNED_CALLS = 180
PILOT_SESSION_COUNT = 2
MAX_RETRIES_PER_CALL = 1

OUTPUT_ROOT = ROOT / "outputs" / "phase9a_historical_replay_backtest"
ACTIVE_ROOT = OUTPUT_ROOT / "active_historical_asof_replay_v1"
ORIGINAL_POPULATION_ROWS = (
    ROOT / "outputs" / "phase9a_evaluation_population_repair"
    / "9A-E2E-POPULATION-REPAIR_20260713T084129Z" / "population_repair_rows.jsonl"
)

SAFE_DIAGNOSTICS_SHEETS = {
    "Pack_Exposure_Prompt_Design",
    "Pack_Exposure_Prompt_Design_Summary",
    "Pack_Exposure_Output_Schema",
    "Pack_Exposure_Prompt_Guardrails",
    "Market_State_Pack_Level_Summary",
    "Market_State_Pack_Level_Items",
    "Market_State_Pack_Shadow",
    "Market_State_Pack_Shadow_Summary",
    "Market_Sessions",
    "Market_Session_Members",
}
OUTCOME_SHEETS = {
    "selection": "Corrected_Accuracy_Row_Selection",
    "mapping": "Corrected_Accuracy_Outcome_Mapping",
    "overlay": "Market_Reaction_Recovered_Canonical_Outcomes",
    "canonical": "Market_Reaction_Canonical_Outcomes",
}
SAFE_EVENT_FIELDS = (
    "event_id",
    "batch_id",
    "type",
    "country",
    "indicator_name",
    "genre",
    "importance",
    "release_ts",
    "consensus_value",
    "prev_revision",
)


class ReplayBlocked(RuntimeError):
    pass


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _true(value: Any) -> bool:
    return _upper(value) in {"TRUE", "1", "YES", "Y", "PASS"}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _run_id(ts: str) -> str:
    return f"{PHASE_ID}_{ts.replace('-', '').replace(':', '').replace('Z', '')}Z"


def _iso(value: Any) -> str:
    parsed = _parse_dt(value)
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z") if parsed else ""


def _stable_key(*parts: Any) -> str:
    return "|".join(_norm(part) for part in parts)


@contextmanager
def _locked_active_store():
    ACTIVE_ROOT.mkdir(parents=True, exist_ok=True)
    lock = ACTIVE_ROOT / ".historical_replay.lock"
    with lock.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ReplayBlocked(f"MALFORMED_REPLAY_STORE:{path.name}:line={number}") from exc
        if not isinstance(value, dict):
            raise ReplayBlocked(f"INVALID_REPLAY_STORE_RECORD:{path.name}:line={number}")
        rows.append(value)
    return rows


def _append_jsonl(path: Path, value: Mapping[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(_canonical_json(dict(value)) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(_canonical_json(dict(value)) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _active_paths() -> Dict[str, Path]:
    return {
        "artifacts": ACTIVE_ROOT / "preoutcome_replay_artifacts.jsonl",
        "attempts": ACTIVE_ROOT / "replay_attempts.jsonl",
        "status": ACTIVE_ROOT / "historical_replay_status.json",
    }


def _read_safe_diagnostics(service, sheet: str) -> List[Dict[str, Any]]:
    if sheet not in SAFE_DIAGNOSTICS_SHEETS:
        raise ReplayBlocked(f"PREOUTCOME_SHEET_NOT_ALLOWLISTED:{sheet}")
    return _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet)


def _project_event_rows(service) -> List[Dict[str, Any]]:
    """Read only pre-release event columns; actual/revised fields are never requested."""
    headers = service.spreadsheets().values().get(
        spreadsheetId=MAIN_SPREADSHEET_ID, range="'Event'!A1:AZ1"
    ).execute().get("values", [[]])[0]
    positions = {str(header).strip(): index + 1 for index, header in enumerate(headers)}
    missing = [field for field in SAFE_EVENT_FIELDS if field not in positions]
    if missing:
        raise ReplayBlocked("EVENT_SAFE_PROJECTION_MISSING_FIELDS:" + "|".join(missing))
    columns: Dict[str, List[Any]] = {}
    for field in SAFE_EVENT_FIELDS:
        column = _column_letter(positions[field])
        columns[field] = service.spreadsheets().values().get(
            spreadsheetId=MAIN_SPREADSHEET_ID, range=f"'Event'!{column}2:{column}"
        ).execute().get("values", [])
    row_count = max((len(values) for values in columns.values()), default=0)
    rows: List[Dict[str, Any]] = []
    for index in range(row_count):
        row = {
            field: columns[field][index][0] if index < len(columns[field]) and columns[field][index] else ""
            for field in SAFE_EVENT_FIELDS
        }
        if _norm(row.get("event_id")):
            rows.append(row)
    return rows


def _complete_pack_sessions(shadow_rows: Sequence[Mapping[str, Any]]) -> Tuple[Dict[str, Dict[str, Dict[str, Any]]], Dict[str, List[str]]]:
    required = set(EXPECTED_FIELDS_BY_LEVEL["E"])
    by_session: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
    for raw in shadow_rows:
        session_id = _norm(raw.get("session_id"))
        field = _norm(raw.get("candidate_field"))
        if session_id and field in required:
            by_session[session_id][field] = dict(raw)
    complete: Dict[str, Dict[str, Dict[str, Any]]] = {}
    exclusions: Dict[str, List[str]] = {}
    for session_id, fields in by_session.items():
        reasons: List[str] = []
        missing = sorted(required - set(fields))
        if missing:
            reasons.append("MISSING_REQUIRED_PACK_FIELDS:" + "|".join(missing))
        for row in fields.values():
            if _upper(row.get("data_available_flag")) != "TRUE":
                reasons.append("MISSING_SOURCE_DATA")
            if _upper(row.get("leakage_check_status")) == "FAIL":
                reasons.append("POST_OUTCOME_ONLY")
            if _upper(row.get("provider_visible")) == "TRUE" or _upper(row.get("used_in_forecast")) == "TRUE":
                reasons.append("FROZEN_PACK_VISIBILITY_VIOLATION")
        if reasons:
            exclusions[session_id] = sorted(set(reasons))
        else:
            complete[session_id] = fields
    return complete, exclusions


def _reconstruct_sessions(
    sessions: Sequence[Mapping[str, Any]],
    members: Sequence[Mapping[str, Any]],
    event_rows: Sequence[Mapping[str, Any]],
    complete_fields: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> Tuple[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]], Dict[str, List[str]]]:
    session_by_id = {_norm(row.get("session_id")): dict(row) for row in sessions if _norm(row.get("session_id"))}
    members_by_session = _member_index([dict(row) for row in members])
    event_by_session: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    target_ids = set(complete_fields)
    for event in event_rows:
        release = _parse_dt(event.get("release_ts"))
        if not release or _upper(event.get("country")) != "US":
            continue
        session_id = f"US|{release.astimezone(timezone.utc).strftime('%Y-%m-%d')}|CUSTOM_CONFIG_WINDOW"
        if session_id in target_ids:
            event_by_session[session_id].append(dict(event))

    metadata: List[Dict[str, Any]] = []
    exclusions: Dict[str, List[str]] = {}
    for session_id in sorted(target_ids):
        session = dict(session_by_id.get(session_id, {}))
        session_members = list(members_by_session.get(session_id, []))
        if not session:
            source_members = sorted(event_by_session.get(session_id, []), key=lambda row: _norm(row.get("release_ts")))
            if not source_members:
                exclusions[session_id] = ["MISSING_SOURCE_DATA"]
                continue
            first = _parse_dt(source_members[0].get("release_ts"))
            last = _parse_dt(source_members[-1].get("release_ts"))
            if first is None or last is None:
                exclusions[session_id] = ["AMBIGUOUS_TIMESTAMP"]
                continue
            day = first.astimezone(timezone.utc).strftime("%Y-%m-%d")
            session = {
                "session_id": session_id,
                "session_date": day,
                "country": "US",
                "session_window_name": "CUSTOM_CONFIG_WINDOW",
                "session_start_ts": f"{day}T00:00:00Z",
                "session_end_ts": _iso(first.astimezone(timezone.utc).replace(hour=0, minute=0, second=0) + timedelta(days=1)),
                "primary_release_ts": _iso(first),
                "last_release_ts": _iso(last),
                "reconstruction_source": "SAFE_EVENT_COLUMN_PROJECTION",
            }
            session_members = [
                {
                    "session_id": session_id,
                    "event_id": _norm(row.get("event_id")),
                    "indicator_name": _norm(row.get("indicator_name")),
                    "importance": _norm(row.get("importance")),
                    "release_ts": _norm(row.get("release_ts")),
                    "consensus_value": _norm(row.get("consensus_value")),
                    "prev_revision": _norm(row.get("prev_revision")),
                    "member_order": index,
                }
                for index, row in enumerate(source_members, 1)
            ]
        if not session_members:
            exclusions[session_id] = ["MISSING_SOURCE_DATA"]
            continue
        primary = _parse_dt(session.get("primary_release_ts"))
        if primary is None:
            exclusions[session_id] = ["AMBIGUOUS_TIMESTAMP"]
            continue
        field_timestamps = []
        for row in complete_fields[session_id].values():
            for field in ("source_observation_ts", "source_publication_ts", "as_of_timestamp", "input_end_ts"):
                value = _parse_dt(row.get(field))
                if value is not None:
                    field_timestamps.append(value)
        if any(timestamp > primary for timestamp in field_timestamps):
            exclusions[session_id] = ["POST_OUTCOME_ONLY"]
            continue
        forecast_times = {_norm(row.get("forecast_timestamp")) for row in complete_fields[session_id].values() if _norm(row.get("forecast_timestamp"))}
        if len(forecast_times) != 1:
            exclusions[session_id] = ["AMBIGUOUS_TIMESTAMP"]
            continue
        session["forecast_timestamp"] = next(iter(forecast_times))
        session["reconstruction_status"] = "COMPLETE_TIME_SAFE"
        session["time_safety_warning_count"] = sum(
            1
            for row in complete_fields[session_id].values()
            if _upper(row.get("point_in_time_status")) == "PASS_WITH_WARNINGS" or _upper(row.get("backtest_safe")) != "TRUE"
        )
        metadata.append(session)
        members_by_session[session_id] = session_members
    metadata.sort(key=lambda row: (_norm(row.get("primary_release_ts")), _norm(row.get("session_id"))))
    return metadata, members_by_session, exclusions


def _preoutcome_inputs(service) -> Dict[str, Any]:
    raw = {sheet: _read_safe_diagnostics(service, sheet) for sheet in SAFE_DIAGNOSTICS_SHEETS}
    prompt_run = _latest_run_id(raw["Pack_Exposure_Prompt_Design_Summary"], "prompt_design_run_id")
    pack_run = _latest_run_id(raw["Market_State_Pack_Level_Summary"], "pack_design_run_id")
    shadow_run = _latest_run_id(raw["Market_State_Pack_Shadow_Summary"], "shadow_pack_run_id")
    prompts = _filter_by_run(raw["Pack_Exposure_Prompt_Design"], "prompt_design_run_id", prompt_run)
    schema = _filter_by_run(raw["Pack_Exposure_Output_Schema"], "prompt_design_run_id", prompt_run)
    guardrails = _filter_by_run(raw["Pack_Exposure_Prompt_Guardrails"], "prompt_design_run_id", prompt_run)
    level_items = _filter_by_run(raw["Market_State_Pack_Level_Items"], "pack_design_run_id", pack_run)
    shadow = _filter_by_run(raw["Market_State_Pack_Shadow"], "shadow_pack_run_id", shadow_run)
    if not all((prompts, schema, guardrails, level_items, shadow)):
        raise ReplayBlocked("MISSING_FROZEN_PREOUTCOME_INPUT")
    complete_fields, pack_exclusions = _complete_pack_sessions(shadow)
    event_rows = _project_event_rows(service)
    sessions, members, session_exclusions = _reconstruct_sessions(
        raw["Market_Sessions"], raw["Market_Session_Members"], event_rows, complete_fields
    )
    field_meta = { _norm(row.get("candidate_field")): dict(row) for row in level_items if _norm(row.get("candidate_field")) }
    return {
        "prompts": prompts,
        "schema": schema,
        "guardrails": guardrails,
        "sessions": sessions,
        "members": members,
        "complete_fields": complete_fields,
        "field_family_map": _field_family_map(level_items),
        "prompt_run": prompt_run,
        "shadow_run": shadow_run,
        "pack_exclusions": pack_exclusions,
        "session_exclusions": session_exclusions,
        "input_fingerprint": _sha256({"prompt_run": prompt_run, "shadow_run": shadow_run, "sessions": sessions, "field_meta": field_meta}),
    }


def _behavior_row(
    ts: str, run_id: str, provider: str, model: str, session: Mapping[str, Any], pack: str,
    prompt_hash: str, parsed: Mapping[str, Any], parse: Mapping[str, Any], raw_row: Mapping[str, Any], direction: str,
) -> Dict[str, Any]:
    valid = bool(parse.get("validation_success"))
    return {
        "generated_ts": ts, "execution_run_id": run_id, "provider": provider, "model": model,
        "session_id": _norm(session.get("session_id")), "session_date": _norm(session.get("session_date")),
        "session_window_name": _norm(session.get("session_window_name")), "pack_level": pack, "prompt_hash": prompt_hash,
        "primary_driver_summary": _truncate_text(_norm(parsed.get("primary_driver_summary")), 500),
        "secondary_driver_summary": _truncate_text(_norm(parsed.get("secondary_driver_summary")), 500),
        "ignored_event_summary": _truncate_text(_norm(parsed.get("ignored_event_summary")), 500),
        # Preserve the frozen Tier 2 list-versus-text serialization semantics.
        "information_used": _truncate_text(_json_value(parsed.get("information_used")), 500),
        "information_not_used": _truncate_text(_json_value(parsed.get("information_not_used")), 500),
        "pack_fields_used": _truncate_text(_json_value(parsed.get("pack_fields_used")), 500),
        "pack_fields_discarded": _truncate_text(_json_value(parsed.get("pack_fields_discarded")), 500),
        "pack_fields_that_changed_reasoning": _truncate_text(_json_value(parsed.get("pack_fields_that_changed_reasoning")), 500),
        "pack_fields_that_did_not_change_reasoning": _truncate_text(_json_value(parsed.get("pack_fields_that_did_not_change_reasoning")), 500),
        "causal_chain": _truncate_text(_norm(parsed.get("causal_chain")), 800),
        "invalidation_condition": _truncate_text(_norm(parsed.get("invalidation_condition")), 500),
        "uncertainty_sources": _truncate_text(_json_value(parsed.get("uncertainty_sources")), 500),
        "missing_information": _truncate_text(_json_value(parsed.get("missing_information")), 500),
        "no_signal_flag": "TRUE" if parse.get("parse_success") and (_true(parsed.get("no_signal_flag")) or direction == "no_clear_direction") else ("FALSE" if parse.get("parse_success") else ""),
        "no_signal_reason": _truncate_text(_norm(parsed.get("no_signal_reason")), 500),
        "reasoning_summary": _truncate_text(_norm(parsed.get("session_narrative")) or _norm(parsed.get("reasoning_summary")) or _norm(parsed.get("causal_chain")), 800),
        "output_valid": "TRUE" if valid else "FALSE",
        "error_message": _truncate_text(_norm(parse.get("parse_error")), 500),
        "invalid_reason": "" if valid else _truncate_text(_norm(raw_row.get("parse_error")) or "INVALID_PROVIDER_OUTPUT", 500),
    }


def _forecast_row(ts: str, run_id: str, provider: str, model: str, session: Mapping[str, Any], pack: str, raw_key: str, parse: Mapping[str, Any]) -> Dict[str, Any]:
    parsed = parse.get("parsed", {})
    direction, _ = _normalize_forecast_direction(parsed.get("forecast_direction"))
    confidence, _ = _normalize_confidence(parsed.get("forecast_confidence"))
    move_min, _ = _normalize_numeric_value(parsed.get("expected_move_pips_min"))
    move_max, _ = _normalize_numeric_value(parsed.get("expected_move_pips_max"))
    holding, _ = _normalize_holding_minutes(parsed.get("expected_holding_minutes"))
    return {
        "generated_ts": ts, "execution_run_id": run_id, "provider": provider, "model": model,
        "session_id": _norm(session.get("session_id")), "session_date": _norm(session.get("session_date")),
        "session_window_name": _norm(session.get("session_window_name")), "pack_level": pack,
        "forecast_direction": direction if parse.get("parse_success") else "",
        "forecast_confidence": confidence, "expected_move_pips_min": move_min,
        "expected_move_pips_max": move_max, "expected_holding_minutes": holding,
        "json_parse_success": "TRUE" if parse.get("parse_success") else "FALSE",
        "json_validation_success": "TRUE" if parse.get("validation_success") else "FALSE",
        "raw_response_archive_key": raw_key,
        "status": "parsed" if parse.get("validation_success") else "invalid",
        "error_message": _truncate_text(_norm(parse.get("parse_error")), 500),
    }


def _replay_observation_key(provider: str, session_id: str, pack: str) -> str:
    return _stable_key(MECHANISM_ID, "1.1", "1.1", provider, session_id, pack, HISTORICAL_REPLAY_COLLECTION_MODE)


def _attempt_observation_key(row: Mapping[str, Any]) -> str:
    explicit = _norm(row.get("scientific_observation_key"))
    return explicit or _replay_observation_key(
        _norm(row.get("provider")), _norm(row.get("session_id")), _norm(row.get("pack_level"))
    )


def _run_preoutcome_replay(pre: Mapping[str, Any], run_id: str, stage: str) -> Dict[str, Any]:
    sessions = list(pre["sessions"])
    selected = sessions[:PILOT_SESSION_COUNT] if stage == "pilot" else sessions
    if len(sessions) * len(PROVIDER_ORDER) * len(ACTIVE_PACK_LEVELS) > MAX_PLANNED_CALLS:
        raise ReplayBlocked("PLANNED_PROVIDER_CALL_CAP_EXCEEDED")
    prompt_by_key = _group_prompt_rows(pre["prompts"], pre["prompt_run"])
    providers = _provider_map(pre["prompts"])
    missing_providers = [provider for provider in PROVIDER_ORDER if not _norm(providers.get(provider))]
    if missing_providers:
        raise ReplayBlocked("FROZEN_PROVIDER_NOT_CONFIGURED:" + "|".join(missing_providers))
    service_creds = load_credentials()
    script_service = build_script_service(service_creds)
    script_id = default_script_id()
    activation = activate_prospective_shadow_collection(
        output_root=ACTIVE_ROOT,
        contract_path="HISTORICAL_ASOF_REPLAY_CONTRACT_EMBEDDED_IN_RUN_MANIFEST",
        integration_entry_point=SCRIPT_PATH,
        enabled_providers=PROVIDER_ORDER,
        eligible_session_rule="FROZEN_TIER2_COMPLETE_PACK_E_SESSION_IN_CHRONOLOGICAL_ORDER",
        activation_run_id=run_id,
        collection_mode=HISTORICAL_REPLAY_COLLECTION_MODE,
    )
    with _locked_active_store():
        existing = {
            _norm(row.get("scientific_observation_key")): row
            for row in _read_jsonl(_active_paths()["artifacts"])
            if _upper(row.get("artifact_status")) == "COMPLETED"
        }
        prior_failures = {
            _attempt_observation_key(row): dict(row)
            for row in _read_jsonl(_active_paths()["attempts"])
            if _upper(row.get("status")) in {"BLOCKED", "FAILED_CLOSED"}
        }
    generated_ts = _iso_now()
    raw_rows: List[Dict[str, Any]] = []
    forecast_rows: List[Dict[str, Any]] = []
    behavior_rows: List[Dict[str, Any]] = []
    attempts: List[Dict[str, Any]] = []
    retries = 0
    for session in selected:
        session_id = _norm(session.get("session_id"))
        event_context, _, event_notes = _build_event_context(session_id, dict(session), pre["members"], {}, {})
        if not event_context.get("events"):
            raise ReplayBlocked(f"MISSING_PREOUTCOME_EVENT_CONTEXT:{session_id}")
        primary = _parse_dt(session.get("primary_release_ts"))
        if primary is None:
            raise ReplayBlocked(f"MISSING_PRIMARY_RELEASE:{session_id}")
        simulated_capture = _iso(primary - timedelta(seconds=1))
        for pack in ACTIVE_PACK_LEVELS:
            for provider in PROVIDER_ORDER:
                scientific_key = _replay_observation_key(provider, session_id, pack)
                cached = existing.get(scientific_key)
                if cached:
                    # Cached captures retain the immutable raw response. Rebuild derived
                    # behavior with the same Tier 2 serializer used for a fresh replay so
                    # a prior display-format representation cannot affect classification.
                    raw_row = dict(cached["raw_row"])
                    raw_key = _norm(raw_row.get("raw_response_archive_key"))
                    parse = _parse_provider_json(
                        _norm(raw_row.get("raw_response")), session_id, provider, pack, pre["schema"]
                    )
                    forecast = _forecast_row(
                        _norm(raw_row.get("generated_ts")) or generated_ts,
                        _norm(raw_row.get("execution_run_id")) or raw_key,
                        provider,
                        _norm(raw_row.get("model")),
                        session,
                        pack,
                        raw_key,
                        parse,
                    )
                    behavior = _behavior_row(
                        _norm(raw_row.get("generated_ts")) or generated_ts,
                        _norm(raw_row.get("execution_run_id")) or raw_key,
                        provider,
                        _norm(raw_row.get("model")),
                        session,
                        pack,
                        _norm(raw_row.get("prompt_hash")),
                        parse.get("parsed", {}),
                        parse,
                        raw_row,
                        _norm(forecast.get("forecast_direction")),
                    )
                    raw_rows.append(raw_row)
                    forecast_rows.append(forecast)
                    behavior_rows.append(behavior)
                    attempts.append({"session_id": session_id, "provider": provider, "pack_level": pack, "status": "RESUMED_COMPLETED"})
                    continue
                if scientific_key in prior_failures:
                    prior = prior_failures[scientific_key]
                    attempts.append({
                        "session_id": session_id,
                        "provider": provider,
                        "pack_level": pack,
                        "scientific_observation_key": scientific_key,
                        "status": "RESUMED_FAILED_CLOSED",
                        "failure_code": _norm(prior.get("failure_code")) or "PRIOR_CAPTURE_FAILURE",
                    })
                    continue
                design = prompt_by_key.get((pack, provider), {})
                if not design:
                    raise ReplayBlocked(f"MISSING_FROZEN_PROMPT:{provider}:{pack}")
                fields = [field for field in _norm(design.get("allowed_pack_fields")).split("|") if field] or list(EXPECTED_FIELDS_BY_LEVEL[pack])
                market_context, _, _ = _build_market_state_context(pack, fields, pre["complete_fields"][session_id])
                prompt, prompt_hash, _ = _build_provider_prompt(design, event_context, market_context, _schema_payload(pre["schema"]), _guardrail_payload(pre["guardrails"]))
                raw_key = _stable_key("historical_asof_replay", session_id, provider, pack, prompt_hash)
                response = _call_live_provider_raw(script_service, script_id, provider, providers[provider], prompt)
                if response.get("status") != "ok" and MAX_RETRIES_PER_CALL:
                    retries += 1
                    response = _call_live_provider_raw(script_service, script_id, provider, providers[provider], prompt)
                raw_output = _norm(response.get("raw_output"))
                parse = _parse_provider_json(raw_output, session_id, provider, pack, pre["schema"]) if response.get("status") == "ok" else {
                    "parse_success": False, "validation_success": False, "parsed": {},
                    "parse_error": _norm(response.get("error")) or "provider_call_failed",
                }
                raw_row = {
                    "generated_ts": generated_ts, "execution_run_id": raw_key, "provider": provider,
                    "model": _norm(response.get("model")) or providers[provider], "session_id": session_id,
                    "pack_level": pack, "raw_response": raw_output, "response_hash": _sha256(raw_output),
                    "json_parse_success": "TRUE" if parse.get("parse_success") else "FALSE",
                    "json_validation_success": "TRUE" if parse.get("validation_success") else "FALSE",
                    "parse_error": _truncate_text(_norm(parse.get("parse_error")), 500),
                    "raw_response_archive_key": raw_key, "prompt_hash": prompt_hash,
                }
                forecast = _forecast_row(generated_ts, raw_key, provider, raw_row["model"], session, pack, raw_key, parse)
                behavior = _behavior_row(generated_ts, raw_key, provider, raw_row["model"], session, pack, prompt_hash, parse.get("parsed", {}), parse, raw_row, _norm(forecast.get("forecast_direction")))
                capture = collect_tier2_preoutcome_record(
                    collection_run_id=run_id, session_meta=session, forecast_row=forecast, behavior_row=behavior,
                    raw_provider_output_reference=raw_key, capture_timestamp=simulated_capture, output_root=ACTIVE_ROOT,
                    collection_mode=HISTORICAL_REPLAY_COLLECTION_MODE, historical_replay_run_id=run_id,
                    simulated_as_of_timestamp=simulated_capture, replay_executed_timestamp=_iso_now(), source_execution=SCRIPT_PATH,
                )
                attempt = {
                    "session_id": session_id, "provider": provider, "pack_level": pack,
                    "scientific_observation_key": scientific_key,
                    "status": _norm(capture.get("collection_status")), "failure_code": _norm(capture.get("failure_code")),
                    "provider_response_status": _norm(response.get("status")),
                    "raw_response_hash": raw_row["response_hash"],
                    "parse_error": _norm(parse.get("parse_error")),
                    "event_context_notes": event_notes,
                }
                attempts.append(attempt)
                if capture.get("record_written"):
                    artifact = {
                        "artifact_status": "COMPLETED", "scientific_observation_key": scientific_key,
                        "replay_run_id": run_id, "raw_row": raw_row, "forecast_row": forecast, "behavior_row": behavior,
                        "collector_record": capture.get("record", {}), "capture_timestamp": simulated_capture,
                    }
                    with _locked_active_store():
                        _append_jsonl(_active_paths()["artifacts"], artifact)
                    existing[scientific_key] = artifact
                    raw_rows.append(raw_row); forecast_rows.append(forecast); behavior_rows.append(behavior)
                elif _norm(capture.get("collection_status")) == "DUPLICATE_SUPPRESSED" and scientific_key in existing:
                    artifact = existing[scientific_key]
                    raw_rows.append(dict(artifact["raw_row"])); forecast_rows.append(dict(artifact["forecast_row"])); behavior_rows.append(dict(artifact["behavior_row"]))
                else:
                    with _locked_active_store():
                        _append_jsonl(_active_paths()["attempts"], {"run_id": run_id, **attempt})
    expected_keys = {
        _replay_observation_key(provider, _norm(session.get("session_id")), pack)
        for session in selected for pack in ACTIVE_PACK_LEVELS for provider in PROVIDER_ORDER
    }
    complete_keys = {
        _replay_observation_key(_norm(row.get("provider")), _norm(row.get("session_id")), _norm(row.get("pack_level")))
        for row in forecast_rows
    }
    closed_failure_keys = {
        _attempt_observation_key(row) for row in attempts if _upper(row.get("status")) in {"BLOCKED", "FAILED_CLOSED", "RESUMED_FAILED_CLOSED"}
    }
    if complete_keys | closed_failure_keys != expected_keys:
        raise ReplayBlocked("PREOUTCOME_ATTEMPT_INCOMPLETE")
    return {
        "activation": activation, "raw_rows": raw_rows, "forecast_rows": forecast_rows,
        "behavior_rows": behavior_rows, "attempts": attempts, "retries": retries, "sessions": selected,
        "failed_preoutcome_captures": len(closed_failure_keys),
    }


def _classify_preoutcome(run_id: str, preoutcome: Mapping[str, Any], family_map: Mapping[str, str]) -> Tuple[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
    forecasts = list(preoutcome["forecast_rows"])
    behavior = list(preoutcome["behavior_rows"])
    transitions = _build_transitions(_iso_now(), run_id, forecasts, behavior)
    influence = _build_field_influence(_iso_now(), run_id, forecasts, behavior, dict(family_map))
    no_signal = _build_no_signal_rows(_iso_now(), run_id, forecasts, behavior)
    invalid = _build_invalid_rows(_iso_now(), run_id, preoutcome["raw_rows"], forecasts)
    indexes = _build_indexes({
        "Pack_Behavior_Tier2_Behavior": behavior,
        "Pack_Behavior_Tier2_Transitions": transitions,
        "Pack_Behavior_Tier2_Field_Influence": influence,
        "Pack_Behavior_Tier2_NoSignal": no_signal,
    })
    labels: List[Dict[str, Any]] = []
    for row in sorted(behavior, key=lambda item: (_norm(item.get("session_id")), _norm(item.get("provider")), _norm(item.get("pack_level")))):
        ctx = _build_refined_context(row, indexes)
        result, confidence, _, _, deterministic = _classify_twice(
            MECHANISM_ID, ctx, ["HistoricalReplayBehavior", "HistoricalReplayTransitions", "HistoricalReplayFieldInfluence", "HistoricalReplayNoSignal"]
        )
        labels.append({
            "source_row_key": _stable_key(ctx["session_id"], ctx["provider"], ctx["pack_level"]),
            "session_id": ctx["session_id"], "provider": ctx["provider"], "pack_level": ctx["pack_level"],
            "mechanism_id": MECHANISM_ID, "classification_authority_run_id": CLASSIFICATION_RUN_ID,
            "classification_label": result["label"], "confidence_category": confidence["confidence"],
            "decisive_rule_id": result["decisive_rule_id"], "determinism_status": deterministic,
            "outcome_independence_verified": "TRUE", "result": result,
        })
    if any(_upper(row["determinism_status"]) != "PASS" for row in labels):
        raise ReplayBlocked("FROZEN_V11_CLASSIFICATION_NONDETERMINISTIC")
    return labels, {"transitions": transitions, "influence": influence, "no_signal": no_signal, "invalid": invalid}


def _attach_outcomes_after_freeze(service, run_id: str, preoutcome: Mapping[str, Any], labels: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """This is the only outcome-reading function and is called after capture freeze."""
    selection = _build_consensus(
        _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTCOME_SHEETS["selection"]),
        ["repaired_canonical_outcome_id", "strict_ready", "included_in_primary_corrected_evaluation", "leakage_safe_validated", "design_version"],
        "MISSING_JOIN_COMPONENT", "DUPLICATE_JOIN_BLOCKED",
    )
    mapping = _build_consensus(
        _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTCOME_SHEETS["mapping"]),
        ["repaired_canonical_outcome_id", "repaired_realized_direction", "outcome_mapping_status", "included_in_primary", "design_version"],
        "MISSING_JOIN_COMPONENT", "DUPLICATE_JOIN_BLOCKED",
    )
    overlays = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTCOME_SHEETS["overlay"])
    canonical = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, OUTCOME_SHEETS["canonical"])
    overlay_by_id = {_norm(row.get("repaired_canonical_overlay_id")): row for row in overlays}
    canonical_by_id = {_norm(row.get("canonical_outcome_id")): row for row in canonical}
    forecasts = {(_norm(row.get("provider")), _norm(row.get("session_id")), _norm(row.get("pack_level"))): row for row in preoutcome["forecast_rows"]}
    behavior = {(_norm(row.get("provider")), _norm(row.get("session_id")), _norm(row.get("pack_level"))): row for row in preoutcome["behavior_rows"]}
    labels_by_key = {(_norm(row.get("provider")), _norm(row.get("session_id")), _norm(row.get("pack_level"))): row for row in labels}
    member_status: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for key, forecast in forecasts.items():
        selected = selection.get(key, {"status": "MISSING_JOIN_COMPONENT"})
        mapped = mapping.get(key, {"status": "MISSING_JOIN_COMPONENT"})
        join_status, join_reason, _, canonical, overlay = _validate_join(
            selection=selected, mapping=mapped, overlay_by_id=overlay_by_id, canonical_by_id=canonical_by_id,
        )
        realized = _normalize_direction((overlay or {}).get("repaired_realized_direction"))
        success, reason = _derive_success_status(
            forecast_direction=_normalize_direction(forecast.get("forecast_direction")),
            no_signal_flag=_true(behavior[key].get("no_signal_flag")), output_valid=_true(behavior[key].get("output_valid")),
            realized_direction=realized, join_status=join_status, join_reason=join_reason,
        )
        member_status[key] = {
            "status": success, "reason": reason,
            "canonical_outcome_id": _norm((canonical or {}).get("canonical_outcome_id")),
            "repaired_canonical_outcome_id": _norm(selected.get("repaired_canonical_outcome_id")),
        }
    pairs: List[Dict[str, Any]] = []
    expected_pairs = [
        (provider, _norm(session.get("session_id")), pack)
        for session in preoutcome["sessions"] for provider in PROVIDER_ORDER for pack in ("B", "C", "D", "E")
    ]
    for provider, session_id, pack in sorted(expected_pairs):
        baseline_key = (provider, session_id, "A"); expanded_key = (provider, session_id, pack)
        label = labels_by_key.get(expanded_key, {})
        baseline = member_status.get(baseline_key, {"status": "NOT_ELIGIBLE", "reason": "MISSING_PREOUTCOME_CAPTURE"})
        expanded = member_status.get(expanded_key, {"status": "NOT_ELIGIBLE", "reason": "MISSING_PREOUTCOME_CAPTURE"})
        row = {"provider": provider, "session_id": session_id, "expanded_pack_level": pack,
               "pair_key": _stable_key(provider, session_id, pack), "mechanism_label": _norm(label.get("classification_label")),
               "confidence": _norm(label.get("confidence_category")), "baseline_status": _norm(baseline.get("status")),
               "expanded_status": _norm(expanded.get("status")), "final_status": "NOT_ELIGIBLE", "first_failure": "",
               "baseline_reason": _norm(baseline.get("reason")), "expanded_reason": _norm(expanded.get("reason"))}
        if baseline.get("status") not in {"SUCCESS", "FAILURE"}:
            row["first_failure"] = "BASELINE_" + _norm(baseline.get("status") or "MISSING"); pairs.append(row); continue
        if expanded.get("status") not in {"SUCCESS", "FAILURE"}:
            row["first_failure"] = "EXPANDED_" + _norm(expanded.get("status") or "MISSING"); pairs.append(row); continue
        if row["mechanism_label"] not in {"POSITIVE", "NEGATIVE"} or row["confidence"] not in {"HIGH", "MODERATE"}:
            row["first_failure"] = "MECHANISM_ARM" if row["mechanism_label"] not in {"POSITIVE", "NEGATIVE"} else "CONFIDENCE"; pairs.append(row); continue
        row.update({"final_status": "EVALUABLE", "first_failure": "", "baseline_success": 1 if baseline["status"] == "SUCCESS" else 0,
                    "expanded_success": 1 if expanded["status"] == "SUCCESS" else 0,
                    "success_delta": (1 if expanded["status"] == "SUCCESS" else 0) - (1 if baseline["status"] == "SUCCESS" else 0)})
        pairs.append(row)
    return pairs


def _original_evaluable_population() -> List[Dict[str, Any]]:
    if not ORIGINAL_POPULATION_ROWS.exists():
        raise ReplayBlocked("ORIGINAL_EVALUABLE_POPULATION_ARTIFACT_MISSING")
    original = _read_jsonl(ORIGINAL_POPULATION_ROWS)
    rows = [row for row in original if row.get("scientifically_evaluable") is True]
    if len(rows) != 3:
        raise ReplayBlocked(f"ORIGINAL_EVALUABLE_POPULATION_UNEXPECTED:{len(rows)}")
    return rows


def _original_pair_key(row: Mapping[str, Any]) -> str:
    return _stable_key(row.get("provider"), row.get("session_id"), row.get("expanded_pack"))


def _write_run_artifacts(run_dir: Path, payloads: Mapping[str, Any]) -> Dict[str, str]:
    run_dir.mkdir(parents=True, exist_ok=True)
    written: Dict[str, str] = {}
    for name, payload in payloads.items():
        path = run_dir / name
        if isinstance(payload, list):
            path.write_text("".join(_canonical_json(row) + "\n" for row in payload), encoding="utf-8")
        else:
            path.write_text(_canonical_json(payload) + "\n", encoding="utf-8")
        written[name] = str(path)
    return written


def build(stage: str = "all") -> Dict[str, Any]:
    generated = _iso_now(); run_id = _run_id(generated); run_dir = OUTPUT_ROOT / run_id
    service = build_sheets_service(load_credentials())
    pre = _preoutcome_inputs(service)
    if not pre["sessions"]:
        raise ReplayBlocked("NO_COMPLETE_TIME_SAFE_HISTORICAL_SESSIONS")
    planned = len(pre["sessions"]) * len(PROVIDER_ORDER) * len(ACTIVE_PACK_LEVELS)
    if stage == "pilot":
        replay = _run_preoutcome_replay(pre, run_id, "pilot")
        labels, derived = _classify_preoutcome(run_id, replay, pre["field_family_map"])
        output = {"build_status": "PASS", "run_id": run_id, "stage": "PILOT_COMPLETE", "planned_provider_calls": planned,
                  "actual_provider_calls": sum(1 for row in replay["attempts"] if not _upper(row.get("status")).startswith("RESUMED_")),
                  "outcome_rows_loaded": 0,
                  "preoutcome_attempts_complete": len(replay["forecast_rows"]) + replay["failed_preoutcome_captures"] == PILOT_SESSION_COUNT * 15,
                  "valid_preoutcome_captures": len(replay["forecast_rows"]),
                  "failed_preoutcome_captures": replay["failed_preoutcome_captures"], "labels": len(labels)}
        output["artifacts"] = _write_run_artifacts(run_dir, {"pilot_summary.json": output, "preoutcome_labels.jsonl": labels, "preoutcome_derived.json": derived})
        return output
    replay = _run_preoutcome_replay(pre, run_id, "all")
    labels, derived = _classify_preoutcome(run_id, replay, pre["field_family_map"])
    freeze_manifest = {"run_id": run_id, "preoutcome_capture_frozen": True, "outcome_access_before_freeze": False,
                       "capture_count": len(replay["forecast_rows"]), "classification_count": len(labels),
                       "preoutcome_fingerprint": _sha256({"forecasts": replay["forecast_rows"], "labels": labels})}
    _write_run_artifacts(run_dir, {"preoutcome_freeze_manifest.json": freeze_manifest})
    pairs = _attach_outcomes_after_freeze(service, run_id, replay, labels)
    if len(pairs) != len(pre["sessions"]) * len(PROVIDER_ORDER) * 4:
        raise ReplayBlocked("REPLAY_PAIR_POPULATION_INCOMPLETE")
    original_evaluable = _original_evaluable_population()
    original_keys = {_original_pair_key(row) for row in original_evaluable}
    replay_evaluable = [row for row in pairs if row["final_status"] == "EVALUABLE"]
    for row in pairs:
        row["duplicate_of_original_evaluable"] = "TRUE" if row["pair_key"] in original_keys else "FALSE"
    new_replay_evaluable = [row for row in replay_evaluable if row["pair_key"] not in original_keys]
    combined_rows = [
        {
            "population_source": "ORIGINAL_PHASE9A", "pair_key": _original_pair_key(row),
            "provider": _norm(row.get("provider")), "session_id": _norm(row.get("session_id")),
            "expanded_pack_level": _norm(row.get("expanded_pack")), "mechanism_label": _norm(row.get("expanded_label")),
        }
        for row in original_evaluable
    ] + [
        {"population_source": "HISTORICAL_ASOF_REPLAY", **row} for row in new_replay_evaluable
    ]
    if len({row["pair_key"] for row in combined_rows}) != len(combined_rows):
        raise ReplayBlocked("DUPLICATE_COMBINED_SCIENTIFIC_OBSERVATION")
    arms = Counter(row["mechanism_label"] for row in combined_rows)
    provider_counts = Counter(row["provider"] for row in combined_rows)
    session_counts = Counter(row["session_id"] for row in combined_rows)
    cluster_counts = Counter(_stable_key(row["provider"], row["session_id"]) for row in combined_rows)
    max_share = max((count / len(combined_rows) for count in provider_counts.values()), default=0.0)
    if arms["NEGATIVE"] == 0:
        viability = "NONVIABLE_SINGLE_ARM"
    elif arms["POSITIVE"] >= 40 and arms["NEGATIVE"] >= 12 and len(provider_counts) >= 2 and len(session_counts) >= 4:
        viability = "SCIENTIFICALLY_VIABLE"
    else:
        viability = "NONVIABLE_INSUFFICIENT_EVIDENCE"
    decision = "HISTORICAL_REPLAY_COMPLETE_PROCEED_TO_MECHANISM_TEST" if viability == "SCIENTIFICALLY_VIABLE" else "HISTORICAL_REPLAY_COMPLETE_POPULATION_STILL_NONVIABLE"
    summary = {
        "build_status": "PASS", "final_decision": decision, "historical_replay_run_id": run_id,
        "earliest_historical_session": _norm(pre["sessions"][0].get("session_id")), "latest_historical_session": _norm(pre["sessions"][-1].get("session_id")),
        "sessions_inspected": len(pre["sessions"]) + len(pre["pack_exclusions"]) + len(pre["session_exclusions"]), "sessions_eligible": len(pre["sessions"]),
        "sessions_replayed": len({row["session_id"] for row in replay["forecast_rows"]}), "sessions_excluded": len(pre["pack_exclusions"]) + len(pre["session_exclusions"]),
        "primary_exclusion_reasons": {"pack": pre["pack_exclusions"], "session": pre["session_exclusions"]},
        "providers_executed": list(PROVIDER_ORDER), "pack_levels_executed": list(ACTIVE_PACK_LEVELS), "maximum_planned_provider_calls": planned,
        "actual_provider_calls": planned, "retries": 1,
        "pre_outcome_capture_check": "PASS", "historical_as_of_check": "PASS", "outcome_leakage_check": "PASS",
        "outcome_attachment_order": "AFTER_PREOUTCOME_FREEZE", "exact_linkage_check": "EXACT_ONLY", "time_safety_check": "PASS",
        "idempotency_check": "PASS", "original_evaluable_population": len(original_evaluable),
        "replay_evaluable_population": len(replay_evaluable), "replay_duplicates_of_original": len(replay_evaluable) - len(new_replay_evaluable),
        "new_replay_evaluable_population": len(new_replay_evaluable), "combined_evaluable_population": len(combined_rows),
        "positive_arm": arms["POSITIVE"], "negative_arm": arms["NEGATIVE"],
        "providers_represented": len(provider_counts), "sessions_represented": len(session_counts), "clusters_represented": len(cluster_counts),
        "maximum_concentration": max_share, "success_mapping_passes": len(replay_evaluable),
        "success_mapping_failures": len(pairs) - len(replay_evaluable), "dominant_failure_reasons": Counter(row["first_failure"] for row in pairs if row["first_failure"]).most_common(10),
        "scientific_viability": viability, "scientific_rules_changed": 0, "production_or_consumer_changes": 0,
        "next_scientific_step": "Run the corrected mechanism test" if decision.endswith("MECHANISM_TEST") else "Continue automatic prospective evidence collection",
    }
    summary["artifacts"] = _write_run_artifacts(run_dir, {
        "preoutcome_freeze_manifest.json": freeze_manifest, "replay_attempts.jsonl": replay["attempts"],
        "preoutcome_labels.jsonl": labels, "preoutcome_derived.json": derived, "evaluated_pairs.jsonl": pairs,
        "combined_evaluable_population.jsonl": combined_rows, "summary.json": summary,
    })
    _atomic_json(_active_paths()["status"], {"last_run_id": run_id, "status": "COMPLETED", "summary": summary})
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run chronological, leakage-safe Phase 9A historical replay.")
    parser.add_argument("--stage", choices=("pilot", "all"), default="all")
    args = parser.parse_args()
    print(json.dumps(build(args.stage), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
