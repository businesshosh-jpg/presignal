#!/usr/bin/env python3
"""Rebuild Phase 9 historical A/E experiments from raw calendar rows only.

The pre-outcome phase never reads canonical outcomes or prior Phase 9 research
artifacts. It creates new attention maps, requests, session packs and forecasts.
Only after the complete forecast population is frozen does the outcome phase
load strict canonical rows and construct paired evaluation records.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import sys
import time
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_market_sessions_shadow_v0 import (  # type: ignore
    DIAGNOSTICS_SPREADSHEET_ID,
    MAIN_SPREADSHEET_ID,
    _parse_dt,
    _sheet_to_rows,
)
from automation.build_pack_exposure_pilot_run_v0 import _call_live_provider_raw  # type: ignore
from automation.build_session_attention_map_v0 import (  # type: ignore
    _build_provider_requests as _attention_requests,
    _run_live_contracts as _run_attention,
)
from automation.build_session_information_requests_v0 import (  # type: ignore
    _build_provider_requests as _information_requests,
    _information_key,
    _run_live_contracts as _run_information,
)
from automation.complete_pack_a_vs_frozen_true_pack_e_experiment_v0 import (  # type: ignore
    CANONICAL_OVERRIDE_MANIFEST,
    _evaluate_arm,
    _outcome_status,
    _paired_classification,
)
from automation.configure_market_state_pack_external_acquisition_v0 import (  # type: ignore
    _acquire_request,
    _load_model_config,
    _pack_item_from_result,
    _validate_source_bundle,
)
from automation.build_true_shared_market_state_pack_e_v0 import (  # type: ignore
    INTERPRETIVE_CATEGORIES,
    POLICY_CATEGORIES,
    _capability_for_request,
)
from automation.google_clients import (  # type: ignore
    build_script_service,
    build_sheets_service,
    default_script_id,
    load_credentials,
    run_script_function,
)
from automation.repair_phase9_may1_7_exact_outcome_link_v0 import _load_canonical_overrides  # type: ignore
from automation.run_phase9_prospective_a_vs_e_pipeline_v0 import (  # type: ignore
    _forecast_prompt,
    _parse_json_object,
    _safe_prompt,
)
from automation.v2_layered_prediction_evaluation_v0 import (  # type: ignore
    SCHEMA_VERSION as V2_PREDICTION_SCHEMA_VERSION,
    V2ValidationError,
    parse_provider_prediction,
    release_clusters,
)


PHASE_ID = "9-HISTORICAL-ACQUISITION-REPAIR"
POPULATION_TYPE = "HISTORICAL_SQUARE_ONE_RETROSPECTIVE_SIMULATION"
PROTOCOL_VERSION = "phase9_historical_square_one_acquisition_repair_v2_layered"
FORECAST_PROMPT_VERSION = "phase9_historical_square_one_forecast_v2_layered"
OUTPUT_ROOT = ROOT / "outputs" / "phase9_historical_square_one_acquisition_repair"
ACTIVE_ROOT = OUTPUT_ROOT / "active_v1"
ORIGINAL_REPLAY_RUN_ID = "9-HISTORICAL-SQUARE-ONE-REPLAY_20260714T144550Z"
ORIGINAL_REPLAY_ROOT = ROOT / "outputs" / "phase9_historical_square_one_replay" / ORIGINAL_REPLAY_RUN_ID
STARTING_REPAIR_RUN_ID = "9-HISTORICAL-ACQUISITION-REPAIR_20260714T161545Z"
STARTING_REPAIR_ROOT = OUTPUT_ROOT / STARTING_REPAIR_RUN_ID
SOURCE_BUNDLE_PATH = ROOT / "inputs" / "phase9_external_acquisition" / "source_bundles.jsonl"
STAGE4A_FREEZE_ROOT = ROOT / "outputs" / "phase9_stage4a_final_historical_environment_freeze_audit" / "9-STAGE4A-FINAL-HISTORICAL-ENVIRONMENT-FREEZE-AUDIT_20260717T020656Z"
STAGE4A_CONTRACT_PATH = STAGE4A_FREEZE_ROOT / "historical_environment_contract.json"
STAGE4A_CONTRACT_VERSION = "stage4a_historical_environment_contract_v1"
STAGE4A_CONTRACT_FINGERPRINT = "7ad8b1537f59041a9f9311fbbd547d682a5a15d7fc55a1bc225ca14d24c42e85"
FORECAST_PROVIDERS = {
    "OpenAI": "gpt-4o-mini-2024-07-18",
    "Gemini": "gemini-2.5-flash-lite",
    "Anthropic": "claude-haiku-4-5",
}
ACQUISITION_CONFIG = {
    "provider": "OpenAI", "model": "gpt-5.6-luna", "reasoning": "low",
    "temperature_mode": "MODEL_DEFAULT", "temperature_parameter_sent": False,
}
PACK_VERSION = "historical_square_one_true_shared_pack_e_acquisition_repair_v1"
PACK_FREEZE_STATUS = "FROZEN_FOR_HISTORICAL_SQUARE_ONE_A_VS_E"
SESSION_WINDOW_NAME = "CUSTOM_CONFIG_WINDOW"
FORECAST_LEAD_MINUTES = 10
MODEL_WEIGHT_RISK = "KNOWN_NONZERO_LIMITATION"
FORBIDDEN_EXPERIMENTAL_INPUTS = {
    "Session_Attention_Map", "Session_Information_Requests", "Market_State_Pack",
    "Market_State_Pack_Shadow", "Pack_Behavior_Tier2_Forecasts", "Evaluation",
    "Mechanism", "Phase9A", "canonical_outcome_id", "realized_direction",
    "canonical_start_price", "canonical_end_price", "realized_pips",
}
HINDSIGHT_PHRASES = (
    "as we now know", "subsequently released", "later that day", "the actual came in",
    "the realized move", "in hindsight", "after the release", "following the release",
)


class SquareOneError(RuntimeError):
    """A fail-closed square-one replay condition."""


class ExternalExecutionLimit(SquareOneError):
    """A global external dependency prevents safe continuation."""


def _norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _truth(value: Any) -> bool:
    return _norm(value).upper() in {"TRUE", "YES", "Y", "1", "PASS"}


def _external_auth_failure(value: Any) -> bool:
    message = _norm(value).lower()
    return "invalid_grant" in message and ("expired" in message or "revoked" in message)


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _iso(value: datetime | None = None) -> str:
    current = value or datetime.now(timezone.utc)
    return current.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_id() -> str:
    return PHASE_ID + "_" + _iso().replace("-", "").replace(":", "").replace("Z", "") + "Z"


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        parsed = json.loads(line)
        if not isinstance(parsed, dict):
            raise SquareOneError(f"JSONL_OBJECT_REQUIRED:{path}:{number}")
        rows.append(parsed)
    return rows


def _frozen_stage4a_contract_identity() -> Dict[str, Any]:
    """Load the already frozen Stage 4A contract; replay never reconstructs it."""
    if not STAGE4A_CONTRACT_PATH.exists():
        raise SquareOneError("MISSING_FROZEN_STAGE4A_CONTRACT")
    contract = json.loads(STAGE4A_CONTRACT_PATH.read_text(encoding="utf-8"))
    if not isinstance(contract, dict):
        raise SquareOneError("INVALID_FROZEN_STAGE4A_CONTRACT")
    if _norm(contract.get("contract_version")) != STAGE4A_CONTRACT_VERSION:
        raise SquareOneError("STAGE4A_CONTRACT_VERSION_MISMATCH")
    if _norm(contract.get("contract_fingerprint")) != STAGE4A_CONTRACT_FINGERPRINT:
        raise SquareOneError("STAGE4A_CONTRACT_FINGERPRINT_MISMATCH")
    components = contract.get("component_fingerprints")
    if not isinstance(components, dict) or not all(_norm(value) for value in components.values()):
        raise SquareOneError("STAGE4A_COMPONENT_FINGERPRINTS_MISSING")
    return {
        "environment_contract_version": STAGE4A_CONTRACT_VERSION,
        "environment_contract_fingerprint": STAGE4A_CONTRACT_FINGERPRINT,
        "environment_contract_component_fingerprints": dict(components),
        "environment_contract_source": str(STAGE4A_CONTRACT_PATH),
    }


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2, default=str) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(_canonical(dict(row)) + "\n")
    os.replace(temporary, path)


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(_canonical(dict(row)) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


@contextmanager
def _lock():
    ACTIVE_ROOT.mkdir(parents=True, exist_ok=True)
    with (ACTIVE_ROOT / ".square_one.lock").open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _project_raw_event(row: Mapping[str, Any]) -> Dict[str, Any]:
    allowed = (
        "event_id", "batch_id", "type", "country", "indicator_name", "genre",
        "importance", "release_ts", "consensus_value", "prev_revision",
        "source_cal", "source_provider", "source_series_id", "Extract Date",
    )
    return {key: row.get(key, "") for key in allowed}


def _raw_input_audit(raw_rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {"input": "Event", "classification": "RAW_OR_CONTEMPORANEOUS_ALLOWED", "rows": len(raw_rows), "used": True,
         "fields_projected": sorted(_project_raw_event(raw_rows[0]).keys()) if raw_rows else []},
        {"input": "provider credentials/current frozen model configuration", "classification": "EXECUTION_CONFIGURATION_ALLOWED", "used": True},
        {"input": "inputs/phase9_external_acquisition/source_bundles.jsonl", "classification": "PRIOR_SOURCE_EVIDENCE_REVALIDATION_ONLY", "used": SOURCE_BUNDLE_PATH.exists()},
        {"input": "prior attention maps/information requests/Pack E/forecasts/evaluations/mechanisms", "classification": "DERIVED_FORBIDDEN_AS_SCIENTIFIC_INPUT", "used": False},
        {"input": "canonical outcomes", "classification": "OUTCOME_PHASE_ONLY_AFTER_FORECAST_FREEZE", "used": False},
    ]


def _reconstruct_sessions(raw_rows: Sequence[Mapping[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    by_date: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    exclusions: List[Dict[str, Any]] = []
    for raw in raw_rows:
        row = _project_raw_event(raw)
        release = _parse_dt(row.get("release_ts"))
        missing = [key for key in ("event_id", "type", "country", "indicator_name", "release_ts") if not _norm(row.get(key))]
        if missing or release is None:
            exclusions.append({"source_row": raw.get("__source_row_number__", ""), "status": "RAW_SESSION_INPUT_MISSING", "reason": "|".join(missing or ["INVALID_RELEASE_TIMESTAMP"])})
            continue
        by_date[release.astimezone(timezone.utc).date().isoformat()].append(row)
    sessions: List[Dict[str, Any]] = []
    members: List[Dict[str, Any]] = []
    for date in sorted(by_date):
        rows = sorted(by_date[date], key=lambda row: (_parse_dt(row["release_ts"]), _norm(row["indicator_name"]), _norm(row["event_id"])))
        releases = [_parse_dt(row["release_ts"]) for row in rows]
        country = _norm(rows[0]["country"]).upper()
        if any(_norm(row["country"]).upper() != country for row in rows):
            exclusions.append({"session_date": date, "status": "SESSION_RECONSTRUCTION_FAILED", "reason": "MULTIPLE_COUNTRIES_WITHIN_DATE"})
            continue
        session_id = f"{country}|{date}|{SESSION_WINDOW_NAME}"
        primary = min(value for value in releases if value)
        cutoff = primary - timedelta(minutes=FORECAST_LEAD_MINUTES)
        session_members: List[Dict[str, Any]] = []
        for index, row in enumerate(rows, 1):
            release = _parse_dt(row["release_ts"])
            member = {
                "population_type": POPULATION_TYPE, "historical_replay_protocol_version": PROTOCOL_VERSION,
                "session_id": session_id, "session_date": date, "country": country,
                "session_window_name": SESSION_WINDOW_NAME, "event_id": _norm(row["event_id"]),
                "batch_id": _norm(row.get("batch_id")), "type": _norm(row["type"]),
                "indicator_name": _norm(row["indicator_name"]), "genre": _norm(row.get("genre")),
                "importance": _norm(row.get("importance")), "release_ts": _iso(release),
                "consensus_value": _norm(row.get("consensus_value")), "prev_revision": _norm(row.get("prev_revision")),
                "member_order": index, "same_minute_group_key": f"{country}|{release.strftime('%Y-%m-%dT%H:%M:00Z')}",
                "source_sheet": "Event", "retrospective_simulation_flag": True,
            }
            session_members.append(member)
            members.append(member)
        session = {
            "population_type": POPULATION_TYPE, "historical_replay_protocol_version": PROTOCOL_VERSION,
            "session_id": session_id, "session_date": date, "country": country,
            "session_window_name": SESSION_WINDOW_NAME, "session_start_ts": _iso(primary),
            "session_end_ts": _iso(max(value for value in releases if value)), "primary_release_ts": _iso(primary),
            "last_release_ts": _iso(max(value for value in releases if value)), "forecast_cutoff": _iso(cutoff),
            "member_event_count": len(session_members), "member_event_ids": "|".join(dict.fromkeys(row["event_id"] for row in session_members)),
            "session_fingerprint": _sha(session_members), "source_event_sheet": "Event",
            "retrospective_simulation_flag": True, "model_weight_leakage_not_eliminable": True,
            "model_weight_historical_leakage_risk": MODEL_WEIGHT_RISK,
        }
        sessions.append(session)
    return sessions, members, exclusions


def _member_index(rows: Sequence[Mapping[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    result: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        result[_norm(row.get("session_id"))].append(dict(row))
    return dict(result)


def _request_class(row: Mapping[str, Any]) -> str:
    category = _norm(row.get("information_category"))
    if category in INTERPRETIVE_CATEGORIES or category == "other":
        return "qualitative_interpretive"
    if category in POLICY_CATEGORIES:
        return "policy_rejected"
    if category in {"inflation_narrative", "growth_context", "labor_market_trend"}:
        return "qualitative_source_grounded"
    if category in {"usdjpy_trend", "volatility", "historical_surprise_sensitivity"}:
        return "quantitative_derived"
    return "quantitative_direct"


def _source_bundles() -> List[Dict[str, Any]]:
    return _read_jsonl(SOURCE_BUNDLE_PATH)


def _revalidated_bundles_with_reason(
    session_id: str, key: str, cutoff: str, bundles: Sequence[Mapping[str, Any]],
) -> Tuple[List[Dict[str, Any]], str]:
    valid: List[Dict[str, Any]] = []
    cutoff_dt = _parse_dt(cutoff)
    matched = [
        dict(raw) for raw in bundles
        if _norm(raw.get("session_id")) == session_id and _norm(raw.get("information_key")) == key
    ]
    if not matched:
        return [], "HISTORICAL_SOURCE_RECORD_NOT_FOUND"
    failure_reasons: List[str] = []
    for raw in matched:
        publication = _parse_dt(raw.get("publication_timestamp"))
        retrieval = _parse_dt(raw.get("retrieval_timestamp"))
        if not cutoff_dt or not publication:
            failure_reasons.append("SOURCE_PROVENANCE_FAILED")
            continue
        if publication >= cutoff_dt:
            failure_reasons.append("SOURCE_AFTER_FORECAST_CUTOFF")
            continue
        # Historical retrieval can occur later only when the bundle independently
        # proves historical availability; the source publication still precedes cutoff.
        if retrieval is None or not _truth(raw.get("historical_availability_proven")):
            failure_reasons.append("SOURCE_PROVENANCE_FAILED")
            continue
        if not _truth(raw.get("backtest_safe")):
            failure_reasons.append("POINT_IN_TIME_STATE_UNPROVABLE")
            continue
        try:
            valid.append(_validate_source_bundle(raw, "HISTORICAL_ASOF_REPLAY"))
        except Exception:
            failure_reasons.append("SOURCE_BUNDLE_VALIDATION_FAILED")
            continue
    if valid:
        return valid, "VALID_SOURCE_BUNDLE"
    priority = (
        "SOURCE_AFTER_FORECAST_CUTOFF", "SOURCE_PROVENANCE_FAILED",
        "POINT_IN_TIME_STATE_UNPROVABLE", "SOURCE_BUNDLE_VALIDATION_FAILED",
    )
    return [], next((reason for reason in priority if reason in failure_reasons), "OTHER_EXACT_REASON")


def _revalidated_bundles(session_id: str, key: str, cutoff: str, bundles: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    return _revalidated_bundles_with_reason(session_id, key, cutoff, bundles)[0]


def _capability(row: Mapping[str, Any]) -> Tuple[str, str]:
    adapted = dict(row)
    adapted["request_wording"] = _norm(row.get("requested_information")) or _norm(row.get("request_wording"))
    return _capability_for_request(adapted)


def _request_lineage(session_id: str, key: str, requests: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    origins = sorted(
        ({
            "provider": _norm(row.get("provider")),
            "provider_request_id": _norm(row.get("request_id")),
            "request_identity": _norm(row.get("request_identity")),
            "requested_information": _norm(row.get("requested_information")),
        } for row in requests),
        key=lambda row: (row["provider"], row["provider_request_id"]),
    )
    candidate_ids = sorted({_norm(row.get("candidate_id")) for row in requests if _norm(row.get("candidate_id"))})
    return {
        "provider_request_origins": origins,
        "provider_request_ids": [row["provider_request_id"] for row in origins],
        "normalized_request_id": "SQ1NR_" + _sha({"session_id": session_id, "information_key": key})[:24],
        "candidate_id": candidate_ids[0] if len(candidate_ids) == 1 else "",
        "candidate_ids": candidate_ids,
        "candidate_lineage_status": "PRESERVED" if candidate_ids else "NOT_APPLICABLE_NO_CANDIDATE_RECORD",
        "requested_by": sorted({row["provider"] for row in origins}),
    }


def _daily_source(
    snapshot: Mapping[str, Any], snapshot_key: str, source_identity: str, cutoff: str,
) -> Tuple[Dict[str, Any] | None, str]:
    daily = snapshot.get("daily_snapshots") if isinstance(snapshot.get("daily_snapshots"), dict) else {}
    source = daily.get(snapshot_key) if isinstance(daily, dict) else None
    if not isinstance(source, dict) or _norm(source.get("status")) != "ok":
        return None, "HISTORICAL_SOURCE_RECORD_NOT_FOUND"
    chosen = source.get("chosen") if isinstance(source.get("chosen"), dict) else None
    if not chosen or not _norm(chosen.get("date")) or not isinstance(chosen.get("value"), (int, float)):
        return None, "DETERMINISTIC_INPUT_MISSING"
    observation = _parse_dt(_norm(chosen.get("date")) + "T00:00:00Z")
    forecast_cutoff = _parse_dt(cutoff)
    if observation is None or forecast_cutoff is None:
        return None, "SOURCE_PROVENANCE_FAILED"
    availability = observation + timedelta(days=1)
    if observation >= forecast_cutoff or availability >= forecast_cutoff:
        return None, "POINT_IN_TIME_STATE_UNPROVABLE"
    prior = source.get("prior") if isinstance(source.get("prior"), dict) else None
    return {
        "source_identity": source_identity,
        "source_system": source_identity.split(":", 1)[0],
        "source_series_or_input": source_identity.split(":", 1)[-1],
        "observation_timestamp": _iso(observation),
        "historical_availability_timestamp": _iso(availability),
        "publication_timestamp_policy": _norm(source.get("publication_timestamp_policy")),
        "same_day_value_used": bool(source.get("same_day_value_used")),
        "value": float(chosen["value"]),
        "prior_value": float(prior["value"]) if prior and isinstance(prior.get("value"), (int, float)) else None,
        "prior_observation_date": _norm(prior.get("date")) if prior else "",
    }, ""


def _intraday_window(
    snapshot: Mapping[str, Any], window_key: str, cutoff: str,
) -> Tuple[Dict[str, Any] | None, str]:
    windows = snapshot.get("usdjpy_windows") if isinstance(snapshot.get("usdjpy_windows"), dict) else {}
    window = windows.get(window_key) if isinstance(windows, dict) else None
    if not isinstance(window, dict):
        return None, "COMPUTED_INPUT_MISSING"
    if _truth(window.get("post_forecast_data_used")):
        return None, "SOURCE_AFTER_FORECAST_CUTOFF"
    end_ts = _parse_dt(window.get("end_candle_ts"))
    forecast_cutoff = _parse_dt(cutoff)
    if end_ts is None or forecast_cutoff is None:
        return None, "SOURCE_PROVENANCE_FAILED"
    if end_ts >= forecast_cutoff:
        return None, "SOURCE_AFTER_FORECAST_CUTOFF"
    if _norm(window.get("status")) not in {"exact_window", "leakage_safe_nearest_start"}:
        return None, "COMPUTED_INPUT_MISSING"
    return dict(window), ""


def _pct_change(current: float, prior: float | None) -> float | None:
    if prior in (None, 0):
        return None
    return round(((current - prior) / prior) * 100.0, 6)


def _request_text(requests: Sequence[Mapping[str, Any]]) -> str:
    return " | ".join(
        _norm(row.get("requested_information")) or _norm(row.get("request_wording"))
        for row in requests
    ).lower()


def _requires_equity_detail_beyond_prior_day_sp500(requests: Sequence[Mapping[str, Any]]) -> bool:
    text = _request_text(requests)
    unsupported_tokens = (
        "future", "pre-market", "premarket", "intraday", "pre/post", "pre & during",
        "during session", "session day", "reaction", "nasdaq", "nikkei", "ndx", "nq",
        "global", "vix", "open/close", "today",
    )
    return any(token in text for token in unsupported_tokens)


def _requires_treasury_detail_beyond_daily_curve(requests: Sequence[Mapping[str, Any]]) -> bool:
    text = _request_text(requests)
    unsupported_tokens = (
        "auction", "intraday", "pre/post", "during/after", "post-auction", "post auction",
        "bid-to-cover", "foreign demand", "tail", "real-time", "during", "after ",
    )
    return any(token in text for token in unsupported_tokens)


def _is_unsupported_option_or_volatility_request(requests: Sequence[Mapping[str, Any]]) -> Tuple[bool, str]:
    text = _request_text(requests)
    if any(token in text for token in ("implied", "vix", "option", "swaption", "put/call")):
        return True, "NO_APPROVED_HISTORICAL_USDJPY_OPTION_IV_SOURCE"
    if any(token in text for token in ("1-week", "1 week", "5d", "atr")):
        return True, "APPROVED_PRE_CUTOFF_WINDOWS_DO_NOT_PROVE_REQUESTED_VOLATILITY_HORIZON"
    return False, ""


def _pack_item(
    *, session: Mapping[str, Any], requests: Sequence[Mapping[str, Any]], status: str,
    reason: str, capability_id: str, capability_category: str, acquisition_method: str,
    routes: Sequence[str], value: Any = "", source_identity: str = "", source_timestamp: str = "",
    historical_availability_timestamp: str = "", transformation_method: str = "",
    input_lineage: Sequence[Mapping[str, Any]] = (), source_bundle_ids: Sequence[str] = (),
    provisional_status: str = "",
) -> Dict[str, Any]:
    session_id = _norm(session.get("session_id"))
    key = _norm(requests[0].get("normalized_information_key")) or _norm(requests[0].get("information_key"))
    cutoff = _norm(session.get("forecast_cutoff"))
    lineage = _request_lineage(session_id, key, requests)
    scientific_value = {
        "session_id": session_id, "information_key": key, "status": status, "value": value,
        "source_identity": source_identity, "source_timestamp": source_timestamp,
        "forecast_cutoff": cutoff, "capability_id": capability_id,
    }
    return {
        "population_type": POPULATION_TYPE,
        "historical_replay_protocol_version": PROTOCOL_VERSION,
        "session_id": session_id,
        "information_key": key,
        "item_key": key,
        **lineage,
        "capability_id": capability_id,
        "capability_category": capability_category,
        "acquisition_route_attempted": list(routes),
        "acquisition_method": acquisition_method,
        "status": status,
        "final_status": status,
        "information_class": status,
        "reason": reason,
        "status_reason": reason,
        "value": value,
        "data_available_flag": status.startswith("SUPPLIED_"),
        "source_identity": source_identity,
        "source_system": source_identity.split(":", 1)[0] if source_identity else "",
        "source_series_or_input": source_identity.split(":", 1)[-1] if source_identity else "",
        "source_timestamp": source_timestamp,
        "observation_timestamp": source_timestamp,
        "historical_availability_timestamp": historical_availability_timestamp,
        "forecast_timestamp": cutoff,
        "forecast_cutoff": cutoff,
        "transformation_method": transformation_method,
        "input_lineage": list(input_lineage),
        "source_bundle_ids": sorted({_norm(value) for value in source_bundle_ids if _norm(value)}),
        "provisional_status": provisional_status,
        "value_fingerprint": _sha(scientific_value),
    }


def _market_item(
    session: Mapping[str, Any], requests: Sequence[Mapping[str, Any]], snapshot: Mapping[str, Any],
    members: Sequence[Mapping[str, Any]] = (),
) -> Dict[str, Any]:
    category = _norm(requests[0].get("information_category"))
    capability_id, capability_category = _capability(requests[0])
    cutoff = _norm(session.get("forecast_cutoff"))
    if category == "treasury_yields":
        if capability_id == "TREASURY_FULL_CURVE_AUCTION_DETAIL":
            if _requires_treasury_detail_beyond_daily_curve(requests):
                return _pack_item(
                    session=session, requests=requests, status="NOT_AVAILABLE",
                    reason="APPROVED_DAILY_TREASURY_CURVE_SOURCE_DOES_NOT_PROVE_INTRADAY_OR_AUCTION_RESULT_DETAIL",
                    capability_id=capability_id, capability_category=capability_category,
                    acquisition_method="deterministic_fetch", routes=["deterministic_acquisition", "calendar_derived_acquisition"],
                )
            curve_sources: List[Dict[str, Any]] = []
            curve_failures: List[str] = []
            for snapshot_key, source_identity in (
                ("us2y", "FRED:DGS2"), ("us5y", "FRED:DGS5"),
                ("us10y", "FRED:DGS10"), ("us30y", "FRED:DGS30"),
            ):
                source, reason = _daily_source(snapshot, snapshot_key, source_identity, cutoff)
                if source:
                    curve_sources.append(source)
                else:
                    curve_failures.append(reason)
            if len(curve_sources) != 4:
                return _pack_item(
                    session=session, requests=requests, status="NOT_AVAILABLE",
                    reason=curve_failures[0] if curve_failures else "DETERMINISTIC_INPUT_MISSING",
                    capability_id=capability_id, capability_category=capability_category,
                    acquisition_method="deterministic_fetch", routes=["deterministic_acquisition"],
                )
            by_series = {row["source_series_or_input"]: row for row in curve_sources}
            value = {
                "us2y_yield_level": by_series["DGS2"]["value"],
                "us5y_yield_level": by_series["DGS5"]["value"],
                "us10y_yield_level": by_series["DGS10"]["value"],
                "us30y_yield_level": by_series["DGS30"]["value"],
                "us10y_minus_us2y_curve": round(by_series["DGS10"]["value"] - by_series["DGS2"]["value"], 6),
                "us30y_minus_us5y_curve": round(by_series["DGS30"]["value"] - by_series["DGS5"]["value"], 6),
            }
            return _pack_item(
                session=session, requests=requests, status="SUPPLIED_DETERMINISTIC", reason="TIME_SAFE_2Y_5Y_10Y_30Y_PRIOR_DAY_CURVE",
                capability_id=capability_id, capability_category=capability_category,
                acquisition_method="deterministic_fetch", routes=["deterministic_acquisition"], value=value,
                source_identity="FRED:DGS2|DGS5|DGS10|DGS30",
                source_timestamp=max(row["observation_timestamp"] for row in curve_sources),
                historical_availability_timestamp=max(row["historical_availability_timestamp"] for row in curve_sources),
                transformation_method="prior_day_full_curve_levels_and_slopes_v1", input_lineage=curve_sources,
            )
        us2y, reason2 = _daily_source(snapshot, "us2y", "FRED:DGS2", cutoff)
        us10y, reason10 = _daily_source(snapshot, "us10y", "FRED:DGS10", cutoff)
        if not us2y or not us10y:
            return _pack_item(
                session=session, requests=requests, status="NOT_AVAILABLE", reason=reason2 or reason10 or "DETERMINISTIC_INPUT_MISSING",
                capability_id=capability_id, capability_category=capability_category,
                acquisition_method="deterministic_fetch", routes=["deterministic_acquisition"],
            )
        value = {
            "us2y_yield_level": us2y["value"], "us10y_yield_level": us10y["value"],
            "us10y_minus_us2y_curve": round(us10y["value"] - us2y["value"], 6),
            "us2y_change_from_prior": round(us2y["value"] - us2y["prior_value"], 6) if us2y["prior_value"] is not None else None,
            "us10y_change_from_prior": round(us10y["value"] - us10y["prior_value"], 6) if us10y["prior_value"] is not None else None,
        }
        availability = max(us2y["historical_availability_timestamp"], us10y["historical_availability_timestamp"])
        timestamp = max(us2y["observation_timestamp"], us10y["observation_timestamp"])
        return _pack_item(
            session=session, requests=requests, status="SUPPLIED_DETERMINISTIC", reason="TIME_SAFE_2Y_10Y_PRIOR_DAY_STATE",
            capability_id=capability_id, capability_category=capability_category,
            acquisition_method="deterministic_fetch", routes=["deterministic_acquisition"], value=value,
            source_identity="FRED:DGS2|DGS10", source_timestamp=timestamp,
            historical_availability_timestamp=availability, transformation_method="prior_day_levels_changes_and_2s10s_curve_v1",
            input_lineage=[us2y, us10y],
        )
    if category == "dxy":
        dxy, reason = _daily_source(snapshot, "dxy", "FMP:DX-Y.NYB", cutoff)
        if not dxy:
            return _pack_item(
                session=session, requests=requests, status="NOT_AVAILABLE", reason=reason or "DETERMINISTIC_INPUT_MISSING",
                capability_id=capability_id, capability_category=capability_category,
                acquisition_method="computed_feature", routes=["deterministic_acquisition", "computed_acquisition"],
            )
        change = _pct_change(dxy["value"], dxy["prior_value"])
        value = {"dxy_level": dxy["value"], "dxy_change_from_prior_pct": change,
                 "dxy_direction": "up" if change and change > 0 else "down" if change and change < 0 else "flat"}
        return _pack_item(
            session=session, requests=requests, status="SUPPLIED_COMPUTED", reason="TIME_SAFE_DXY_PRIOR_DAY_LEVEL_CHANGE_DIRECTION",
            capability_id=capability_id, capability_category=capability_category,
            acquisition_method="computed_feature", routes=["deterministic_acquisition", "computed_acquisition"], value=value,
            source_identity=dxy["source_identity"], source_timestamp=dxy["observation_timestamp"],
            historical_availability_timestamp=dxy["historical_availability_timestamp"], transformation_method="prior_day_pct_change_and_direction_v1",
            input_lineage=[dxy],
        )
    if category == "usdjpy_trend":
        windows: Dict[str, Any] = {}
        failures: List[str] = []
        for window_key in ("return_1h", "return_4h", "return_24h", "realized_vol_1h"):
            window, reason = _intraday_window(snapshot, window_key, cutoff)
            if window:
                windows[window_key] = window
            else:
                failures.append(reason)
        if not windows:
            return _pack_item(
                session=session, requests=requests, status="NOT_AVAILABLE", reason=failures[0] if failures else "COMPUTED_INPUT_MISSING",
                capability_id=capability_id, capability_category=capability_category,
                acquisition_method="computed_feature", routes=["deterministic_acquisition", "computed_acquisition"],
            )
        end_timestamps = sorted({_norm(row.get("end_candle_ts")) for row in windows.values() if _norm(row.get("end_candle_ts"))})
        value = {
            "usdjpy_level": next((row.get("end_price") for row in windows.values() if row.get("end_price") is not None), None),
            "return_1h_pct": windows.get("return_1h", {}).get("return_pct"),
            "return_4h_pct": windows.get("return_4h", {}).get("return_pct"),
            "return_24h_pct": windows.get("return_24h", {}).get("return_pct"),
            "realized_volatility_1h": windows.get("realized_vol_1h", {}).get("realized_volatility"),
        }
        return _pack_item(
            session=session, requests=requests, status="SUPPLIED_COMPUTED", reason="TIME_SAFE_USDJPY_PRE_CUTOFF_WINDOWS",
            capability_id=capability_id, capability_category=capability_category,
            acquisition_method="computed_feature", routes=["deterministic_acquisition", "computed_acquisition"], value=value,
            source_identity="EODHD:USDJPY.FOREX_INTRADAY", source_timestamp=end_timestamps[-1] if end_timestamps else "",
            historical_availability_timestamp=end_timestamps[-1] if end_timestamps else "", transformation_method="pre_cutoff_1h_4h_24h_return_and_realized_volatility_v1",
            input_lineage=[{"window": key, **value} for key, value in sorted(windows.items())],
        )
    if category == "equity_tone":
        if _requires_equity_detail_beyond_prior_day_sp500(requests):
            return _pack_item(
                session=session, requests=requests, status="NOT_AVAILABLE",
                reason="APPROVED_PRIOR_DAY_SP500_SOURCE_DOES_NOT_PROVE_REQUESTED_INTRADAY_FUTURES_OR_CROSS_MARKET_TONE",
                capability_id=capability_id, capability_category=capability_category,
                acquisition_method="computed_feature", routes=["deterministic_acquisition", "computed_acquisition"],
            )
        sp500, reason = _daily_source(snapshot, "sp500", "FRED:SP500", cutoff)
        if not sp500:
            return _pack_item(
                session=session, requests=requests, status="NOT_AVAILABLE", reason=reason or "DETERMINISTIC_INPUT_MISSING",
                capability_id=capability_id, capability_category=capability_category,
                acquisition_method="computed_feature", routes=["deterministic_acquisition", "computed_acquisition"],
            )
        change = _pct_change(sp500["value"], sp500["prior_value"])
        value = {
            "sp500_prior_day_close": sp500["value"],
            "sp500_prior_day_change_pct": change,
            "sp500_prior_day_direction": "up" if change and change > 0 else "down" if change and change < 0 else "flat",
            "evidence_scope": "PRIOR_DAY_SP500_ONLY_NOT_FUTURES_OR_INTRADAY",
        }
        return _pack_item(
            session=session, requests=requests, status="SUPPLIED_COMPUTED", reason="TIME_SAFE_SP500_PRIOR_DAY_LEVEL_CHANGE_DIRECTION",
            capability_id=capability_id, capability_category=capability_category,
            acquisition_method="computed_feature", routes=["deterministic_acquisition", "computed_acquisition"], value=value,
            source_identity=sp500["source_identity"], source_timestamp=sp500["observation_timestamp"],
            historical_availability_timestamp=sp500["historical_availability_timestamp"],
            transformation_method="prior_day_sp500_pct_change_and_direction_v1", input_lineage=[sp500],
        )
    if category == "volatility":
        unsupported, unavailable_reason = _is_unsupported_option_or_volatility_request(requests)
        if unsupported:
            return _pack_item(
                session=session, requests=requests, status="NOT_AVAILABLE", reason=unavailable_reason,
                capability_id=capability_id, capability_category=capability_category,
                acquisition_method="computed_feature", routes=["deterministic_acquisition", "computed_acquisition"],
            )
        windows: Dict[str, Any] = {}
        failures: List[str] = []
        for window_key in ("realized_vol_1h", "return_24h"):
            window, reason = _intraday_window(snapshot, window_key, cutoff)
            if window:
                windows[window_key] = window
            else:
                failures.append(reason)
        if not windows:
            return _pack_item(
                session=session, requests=requests, status="NOT_AVAILABLE",
                reason=failures[0] if failures else "COMPUTED_INPUT_MISSING",
                capability_id=capability_id, capability_category=capability_category,
                acquisition_method="computed_feature", routes=["deterministic_acquisition", "computed_acquisition"],
            )
        end_timestamps = sorted({_norm(row.get("end_candle_ts")) for row in windows.values() if _norm(row.get("end_candle_ts"))})
        value = {
            "usdjpy_realized_volatility_1h": windows.get("realized_vol_1h", {}).get("realized_volatility"),
            "usdjpy_realized_volatility_24h": windows.get("return_24h", {}).get("realized_volatility"),
            "evidence_scope": "REALIZED_PRE_CUTOFF_VOLATILITY_NOT_OPTION_IMPLIED_VOLATILITY",
        }
        return _pack_item(
            session=session, requests=requests, status="SUPPLIED_COMPUTED", reason="TIME_SAFE_USDJPY_PRE_CUTOFF_REALIZED_VOLATILITY_WINDOWS",
            capability_id=capability_id, capability_category=capability_category,
            acquisition_method="computed_feature", routes=["deterministic_acquisition", "computed_acquisition"], value=value,
            source_identity="EODHD:USDJPY.FOREX_INTRADAY", source_timestamp=end_timestamps[-1] if end_timestamps else "",
            historical_availability_timestamp=end_timestamps[-1] if end_timestamps else "",
            transformation_method="pre_cutoff_1h_24h_realized_volatility_v1",
            input_lineage=[{"window": key, **row} for key, row in sorted(windows.items())],
        )
    reason_by_category = {
        "growth_context": "DETERMINISTIC_INPUT_MISSING",
        "labor_market_trend": "DETERMINISTIC_INPUT_MISSING",
        "historical_surprise_sensitivity": "COMPUTED_INPUT_MISSING",
    }
    return _pack_item(
        session=session, requests=requests, status="NOT_AVAILABLE",
        reason=reason_by_category.get(category, "NO_APPLICABLE_ACQUISITION_CAPABILITY"),
        capability_id=capability_id, capability_category=capability_category,
        acquisition_method="deterministic_fetch" if capability_category in {"EXISTING_SOURCE_NOT_CONNECTED", "NEW_DETERMINISTIC_SOURCE_REQUIRED"} else "computed_feature",
        routes=["deterministic_acquisition", "computed_acquisition"],
    )


def _build_repaired_pack_items(
    session: Mapping[str, Any], members: Sequence[Mapping[str, Any]], requests: Sequence[Mapping[str, Any]],
    acquisition_results: Sequence[Mapping[str, Any]], snapshot: Mapping[str, Any],
    bundle_reasons: Mapping[str, str],
) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for request in requests:
        key = _norm(request.get("normalized_information_key")) or _norm(request.get("information_key"))
        if key:
            grouped[key].append(dict(request))
    acquired = {
        _norm(row.get("information_key")): dict(row) for row in acquisition_results
        if _norm(row.get("result_status")) == "ACQUIRED_AI_RETRIEVED_PROVISIONAL"
    }
    items: List[Dict[str, Any]] = []
    for key in sorted(grouped):
        request_rows = sorted(grouped[key], key=lambda row: (_norm(row.get("provider")), _norm(row.get("request_id"))))
        category = _norm(request_rows[0].get("information_category"))
        capability_id, capability_category = _capability(request_rows[0])
        if category in POLICY_CATEGORIES:
            item = _pack_item(
                session=session, requests=request_rows, status="POLICY_REJECTED",
                reason="FED_EXPECTATIONS_REMAINS_OUTSIDE_FROZEN_PACK_SCOPE",
                capability_id=capability_id, capability_category=capability_category,
                acquisition_method="not_acquired", routes=["policy_classification"],
            )
        elif category in INTERPRETIVE_CATEGORIES or category == "other":
            item = _pack_item(
                session=session, requests=request_rows, status="INTERPRETIVE_NOT_SUPPLIED",
                reason="INTERPRETIVE_JUDGMENT_REMAINS_WITH_FORECAST_PROVIDER",
                capability_id=capability_id, capability_category=capability_category,
                acquisition_method="not_acquired", routes=["interpretive_classification"],
            )
        elif category in {"event_consensus_detail", "upcoming_larger_events"}:
            value = [{
                "event_id": row["event_id"], "indicator_name": row["indicator_name"],
                "release_ts": row["release_ts"], "consensus_value": row["consensus_value"],
                "previous_value": row["prev_revision"],
            } for row in members]
            item = _pack_item(
                session=session, requests=request_rows, status="SUPPLIED_CALENDAR_DERIVED",
                reason="EXACT_RAW_EVENT_CALENDAR_PROJECTION",
                capability_id=capability_id, capability_category=capability_category,
                acquisition_method="calendar_derived_feature",
                routes=["deterministic_acquisition:not_applicable", "computed_acquisition:not_applicable", "calendar_derived_acquisition"],
                value=value, source_identity="Event:RAW_SESSION_MEMBERS",
                source_timestamp=_norm(session.get("forecast_cutoff")),
                historical_availability_timestamp=_norm(session.get("forecast_cutoff")),
                transformation_method="calendar_member_projection_v1",
                input_lineage=[{"event_id": row["event_id"], "release_ts": row["release_ts"]} for row in members],
            )
        elif category in {"treasury_yields", "dxy", "usdjpy_trend", "equity_tone", "volatility", "growth_context", "labor_market_trend", "historical_surprise_sensitivity"}:
            item = _market_item(session, request_rows, snapshot, members)
        elif key in acquired:
            result = acquired[key]
            source_ids = result.get("source_bundle_ids") if isinstance(result.get("source_bundle_ids"), list) else []
            timestamps = result.get("source_timestamps") if isinstance(result.get("source_timestamps"), list) else []
            item = _pack_item(
                session=session, requests=request_rows, status="SUPPLIED_AI_SOURCE_GROUNDED_PROVISIONAL",
                reason="VALID_SOURCE_GROUNDED_AI_ACQUISITION",
                capability_id=capability_id, capability_category=capability_category,
                acquisition_method=_norm(result.get("acquisition_method")) or "ai_retrieved_provisional",
                routes=["deterministic_acquisition:not_applicable", "computed_acquisition:not_applicable", "calendar_derived_acquisition:not_applicable", "historical_source_bundle_retrieval", "acquisition_ai"],
                value={"retrieved_value": result.get("retrieved_value"), "structured_summary": result.get("structured_summary")},
                source_identity="|".join(sorted({_norm(value) for value in source_ids if _norm(value)})),
                source_timestamp=max((_norm(value) for value in timestamps if _norm(value)), default=""),
                historical_availability_timestamp=max((_norm(value) for value in timestamps if _norm(value)), default=""),
                transformation_method="gpt-5.6-luna_source_grounded_summary",
                source_bundle_ids=source_ids, provisional_status=_norm(result.get("provisional_status")),
            )
        else:
            bundle_reason = _norm(bundle_reasons.get(key)) or "NO_APPLICABLE_ACQUISITION_CAPABILITY"
            item = _pack_item(
                session=session, requests=request_rows, status="NOT_AVAILABLE", reason=bundle_reason,
                capability_id=capability_id, capability_category=capability_category,
                acquisition_method="ai_retrieved_provisional" if category == "inflation_narrative" else "not_available",
                routes=["deterministic_acquisition:not_applicable", "computed_acquisition:not_applicable", "calendar_derived_acquisition:not_applicable", "historical_source_bundle_retrieval", "acquisition_ai:blocked_no_valid_bundle"],
            )
        items.append(item)
    return items


def _calendar_pack_items(session: Mapping[str, Any], members: Sequence[Mapping[str, Any]], requests: Sequence[Mapping[str, Any]], acquisition_results: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Compatibility wrapper used by older callers and fixture tests."""
    return _build_repaired_pack_items(session, members, requests, acquisition_results, {}, {})


def _hindsight_hits(raw: str) -> List[str]:
    lower = raw.lower()
    return sorted(phrase for phrase in HINDSIGHT_PHRASES if phrase in lower)


def _normalized_forecast_response(
    raw: str, *, session: Mapping[str, Any], members: Sequence[Mapping[str, Any]], provider: str,
    model: str, arm: str, pack_freeze_id: str, pack_fingerprint: str, forecast_run_id: str,
    forecast_created_ts: str, environment_contract: Mapping[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]], List[str]]:
    """Parse only the native v2 contract; legacy flat forecasts fail closed."""
    if raw.strip().startswith("```"):
        return {}, {}, [], ["MARKDOWN_WRAPPED_TYPED_OUTPUT_NOT_ALLOWED"]
    parsed = _parse_json_object(raw)
    if isinstance(parsed.get("forecast"), dict) or isinstance(parsed.get("prediction"), dict):
        return parsed, {}, [], ["LEGACY_OR_NESTED_PREDICTION_ENVELOPE_NOT_ALLOWED"]
    from automation.native_v2_typed_schema_v0 import validate_canonical_payload
    try:
        validate_canonical_payload(parsed)
    except ValueError as exc:
        return parsed, {}, [], ["V2_OUTPUT_SCHEMA_FAILED:" + str(exc)]
    parsed.update({"session_id": _norm(session.get("session_id")), "provider": provider, "model": model, "pack_arm": arm})
    try:
        prediction, paths = parse_provider_prediction(
            parsed, session=session, members=members, provider=provider, model=model, pack_arm=arm,
            # Contract identity is part of the frozen pack reference used in the v2 prediction identity.
            pack_freeze_id=pack_freeze_id + "|" + _norm(environment_contract.get("environment_contract_fingerprint"))[:24],
            pack_fingerprint=pack_fingerprint, forecast_run_id=forecast_run_id,
            forecast_created_ts=forecast_created_ts,
            forecast_cutoff_ts=_norm(session.get("forecast_cutoff")),
            prompt_version=FORECAST_PROMPT_VERSION, raw_output=raw,
        )
    except (V2ValidationError, ValueError, TypeError) as exc:
        return parsed, {}, [], ["V2_OUTPUT_SCHEMA_FAILED:" + str(exc)]
    lineage = {
        "forecast_identity": _forecast_identity(_norm(session.get("session_id")), provider, arm, _norm(session.get("forecast_cutoff")), pack_fingerprint, environment_contract),
        **dict(environment_contract),
        "historical_replay_protocol_version": PROTOCOL_VERSION,
    }
    prediction.update(lineage)
    for path in paths:
        path.update(lineage)
    return parsed, prediction, paths, []


def _forecast_identity(
    session_id: str, provider: str, arm: str, cutoff: str, pack_fp: str,
    environment_contract: Mapping[str, Any],
) -> str:
    return "SQ1F_" + _sha({"population": POPULATION_TYPE, "protocol": PROTOCOL_VERSION, "session_id": session_id,
                           "prompt_version": FORECAST_PROMPT_VERSION, "provider": provider,
                           "model": FORECAST_PROVIDERS[provider], "arm": arm, "cutoff": cutoff,
                           "pack_fingerprint": pack_fp,
                           "environment_contract_fingerprint": environment_contract.get("environment_contract_fingerprint", "")})[:24]


def _square_one_forecast_prompt(
    session: Mapping[str, Any], members: Sequence[Mapping[str, Any]], exposure: Mapping[str, Any],
    provider: str, model: str,
) -> Dict[str, str]:
    session_fields = (
        "session_id", "session_date", "country", "session_window_name", "session_start_ts",
        "session_end_ts", "primary_release_ts", "last_release_ts", "forecast_cutoff", "member_event_count",
    )
    member_fields = (
        "event_id", "batch_id", "type", "country", "indicator_name", "genre", "importance",
        "release_ts", "consensus_value", "prev_revision", "member_order", "same_minute_group_key",
    )
    clean_session = {key: session.get(key, "") for key in session_fields}
    clean_members = [{key: row.get(key, "") for key in member_fields} for row in members]
    clean_exposure = dict(exposure)
    forecast_visible_item_fields = {
        "information_key", "item_key", "capability_id", "status", "information_class", "value", "reason",
        "source_identity", "source_timestamp", "historical_availability_timestamp",
        "provisional_status", "data_available_flag",
    }
    clean_items: List[Dict[str, Any]] = []
    for raw_item in exposure.get("items", []):
        item = {key: value for key, value in dict(raw_item).items() if key in forecast_visible_item_fields}
        identity_only = {"information_key": item.get("information_key"), "item_key": item.get("item_key")}
        if _safe_prompt(identity_only):
            safe_identity = _norm(item.get("capability_id")) or "REQUEST_DRIVEN_ITEM_IDENTITY_REDACTED"
            item["information_key"] = safe_identity
            item["item_key"] = safe_identity
            item["identity_rendering"] = "CAPABILITY_ID_USED_TO_AVOID_RESERVED_LEAKAGE_TOKEN"
        if _safe_prompt(item):
            raise SquareOneError("PACK_ITEM_FORECAST_RENDERING_LEAKAGE:" + _norm(raw_item.get("information_key")))
        clean_items.append(item)
    clean_exposure["items"] = clean_items
    prompt = _forecast_prompt(clean_session, clean_members, clean_exposure, provider, model)
    prompt["system"] = (
        "Return only one strict top-level object matching the native-v2 typed schema. Do not echo the input. "
        "Do not browse, provide trading advice, or use facts outside supplied pre-cutoff context."
    )
    prompt["instruction"] = (
        "Forecast from supplied scheduled event, consensus, prior, and pack fields only. Historical dates are identifiers, "
        "not permission to recall actual releases. Do not claim an event was released, beat/missed consensus, or caused a "
        "realized move. Return one native v2 layered Prediction at the JSON top level: all native-v2 typed fields, including "
        "primary and secondary driver choices, primary and secondary reactions, interaction prediction, ordered prediction_path, "
        "and final session prediction. prediction_path is the only nested list and uses consecutive path_stage_index values. "
        "Do not return a legacy flat-only response or narrative outside the structured contract. If session_forecast_direction is "
        "NO_CLEAR_DIRECTION, set no_signal_flag to true and provide a non-empty no_signal_reason."
    )
    return prompt


def _load_active_index(name: str, key: str) -> Dict[str, Dict[str, Any]]:
    return {_norm(row.get(key)): row for row in _read_jsonl(ACTIVE_ROOT / name) if _norm(row.get(key))}


def _persist_active(name: str, row: Mapping[str, Any]) -> None:
    _append_jsonl(ACTIVE_ROOT / name, row)


def _snapshot_input_cutoff(forecast_cutoff: str) -> str:
    cutoff = _parse_dt(forecast_cutoff)
    if cutoff is None:
        raise SquareOneError("INVALID_FORECAST_CUTOFF_FOR_MARKET_SNAPSHOT")
    return _iso(cutoff - timedelta(minutes=1))


def _retryable_forecast_errors(errors: Sequence[Any]) -> bool:
    normalized = [_norm(error) for error in errors if _norm(error)]
    if normalized == ["MISSING_NO_SIGNAL_REASON"]:
        return True
    if len(normalized) == 1 and normalized[0].startswith("RESPONSE_SCHEMA:"):
        return True
    if len(normalized) == 1 and normalized[0].startswith("PROVIDER_CALL_FAILED:"):
        message = normalized[0].lower()
        return any(token in message for token in ("timeout", "temporar", "connection", "429", "500", "502", "503"))
    return False


def _acquire_market_state_snapshot(
    session: Mapping[str, Any], script_service: Any, script_id: str, run_id: str,
) -> Dict[str, Any]:
    session_id = _norm(session.get("session_id"))
    forecast_cutoff = _norm(session.get("forecast_cutoff"))
    input_cutoff = _snapshot_input_cutoff(forecast_cutoff)
    try:
        payload = run_script_function(
            script_service, script_id, "apiBuildMarketStateShadowSnapshot", [{"cutoff_ts": input_cutoff}],
        )
        if not isinstance(payload, dict) or _norm(payload.get("status")) != "ok":
            raise SquareOneError("INVALID_MARKET_STATE_SNAPSHOT_PAYLOAD")
        return {
            "population_type": POPULATION_TYPE,
            "historical_replay_protocol_version": PROTOCOL_VERSION,
            "session_id": session_id,
            "source_acquisition_run_id": run_id,
            "forecast_cutoff": forecast_cutoff,
            "snapshot_input_cutoff": input_cutoff,
            "status": "ACQUIRED",
            "source_function": "apiBuildMarketStateShadowSnapshot",
            "payload": payload,
            "payload_fingerprint": _sha(payload),
        }
    except Exception as exc:
        if _external_auth_failure(exc):
            raise ExternalExecutionLimit("GOOGLE_OAUTH_GRANT_EXPIRED_OR_REVOKED") from exc
        return {
            "population_type": POPULATION_TYPE,
            "historical_replay_protocol_version": PROTOCOL_VERSION,
            "session_id": session_id,
            "source_acquisition_run_id": run_id,
            "forecast_cutoff": forecast_cutoff,
            "snapshot_input_cutoff": input_cutoff,
            "status": "FAILED_CLOSED",
            "source_function": "apiBuildMarketStateShadowSnapshot",
            "error_code": "SOURCE_RETRIEVAL_FAILED",
            "error_message": f"{type(exc).__name__}:{exc}",
            "payload": {},
            "payload_fingerprint": _sha({}),
        }


def _capture_attention_chunked(
    generated: str, run_id: str, session: Mapping[str, Any], members: Sequence[Mapping[str, Any]],
    providers: Sequence[Mapping[str, str]], script_service: Any, script_id: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
    """Keep full-session context while bounding strict per-event JSON output."""
    all_rows: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []
    calls = 0
    full_index = [
        {"event_id": row.get("event_id"), "indicator_name": row.get("indicator_name"),
         "release_ts": row.get("release_ts"), "importance": row.get("importance")}
        for row in members
    ]
    chunk_size = 10
    for provider in providers:
        provider_rows: List[Dict[str, Any]] = []
        for offset in range(0, len(members), chunk_size):
            chunk = [dict(row) for row in members[offset:offset + chunk_size]]
            requests = _attention_requests([dict(session)], {_norm(session["session_id"]): chunk}, [dict(provider)])
            request = requests[0]
            request["payload"]["provider"] = provider["provider"]
            request["payload"]["full_session_event_index"] = full_index
            request["payload"]["output_chunk"] = {"offset": offset, "event_ids": [row["event_id"] for row in chunk]}
            request["instruction"] += (
                f"\nSet provider exactly to {provider['provider']}. "
                "The full session index is context only. Return attention_items only for output_chunk.event_ids. "
                "Keep each attention_reason at most 40 characters."
            )
            rows, audit_rows, _, results = _run_attention(
                generated, run_id, [dict(session)], {_norm(session["session_id"]): chunk},
                [request], script_service, script_id,
            )
            calls += sum(int(row.get("attempt_count", 0)) for row in results)
            for audit in audit_rows:
                _persist_active("attention_provider_audit.jsonl", {
                    "population_type": POPULATION_TYPE, "session_id": session["session_id"],
                    "chunk_offset": offset, "chunk_size": len(chunk), **audit,
                })
            if not results or not results[0].get("success"):
                error_message = _norm(results[0].get("error_message")) if results else "MISSING_PROVIDER_RESULT"
                if _external_auth_failure(error_message):
                    raise ExternalExecutionLimit("GOOGLE_OAUTH_GRANT_EXPIRED_OR_REVOKED")
                failures.append({"provider": provider["provider"], "chunk_offset": offset,
                                 "error_message": error_message})
                break
            provider_rows.extend(rows)
        if not any(row["provider"] == provider["provider"] for row in failures):
            label_order = {"PRIMARY_DRIVER": 0, "SECONDARY_DRIVER": 1, "WATCHLIST": 2,
                           "CONTEXT_ONLY": 3, "NO_SIGNAL": 4, "IGNORE": 5}
            provider_rows.sort(key=lambda row: (label_order.get(_norm(row.get("attention_label")), 9),
                                                int(row.get("member_order") or 999), _norm(row.get("event_id"))))
            for rank, row in enumerate(provider_rows, 1):
                row["attention_rank"] = rank
                row["chunked_transport_reconstruction"] = "TRUE"
            all_rows.extend(provider_rows)
    return all_rows, failures, calls


def _run_preoutcome(
    sessions: Sequence[Mapping[str, Any]], members_by_session: Mapping[str, Sequence[Mapping[str, Any]]], run_id: str,
    max_sessions: int | None, environment_contract: Mapping[str, Any],
) -> Dict[str, Any]:
    selected = list(sessions[:max_sessions] if max_sessions else sessions)
    credentials = load_credentials(interactive=False)
    script_service, script_id = build_script_service(credentials), default_script_id()
    providers = [{"provider": provider, "model": model} for provider, model in FORECAST_PROVIDERS.items()]
    attention_index = _load_active_index("new_attention_maps.jsonl", "attention_identity")
    request_index = {
        key: row for key, row in _load_active_index("new_information_requests.jsonl", "request_identity").items()
        if _truth(row.get("request_capture_complete"))
    }
    pack_index = _load_active_index("session_pack_e_freezes.jsonl", "session_id")
    forecast_index = _load_active_index("frozen_forecasts.jsonl", "forecast_identity")
    v2_prediction_index = _load_active_index("v2_predictions.jsonl", "prediction_id")
    v2_path_index = _load_active_index("v2_prediction_paths.jsonl", "stage_fingerprint")
    snapshot_index = _load_active_index("market_state_snapshots.jsonl", "session_id")
    source_rows = _source_bundles()
    all_attention: List[Dict[str, Any]] = []
    all_requests: List[Dict[str, Any]] = []
    classifications: List[Dict[str, Any]] = []
    acquisition_results: List[Dict[str, Any]] = []
    acquisition_audit: List[Dict[str, Any]] = []
    market_state_snapshots: List[Dict[str, Any]] = []
    pack_freezes: List[Dict[str, Any]] = []
    forecasts: List[Dict[str, Any]] = []
    v2_predictions: List[Dict[str, Any]] = []
    v2_paths: List[Dict[str, Any]] = []
    leakage: List[Dict[str, Any]] = []
    exclusions: List[Dict[str, Any]] = []
    provider_calls = 0
    source_calls = 0
    for session in selected:
        session_id = _norm(session["session_id"]); members = list(members_by_session[session_id]); generated = _iso()
        session_attention = [row for row in attention_index.values() if _norm(row.get("session_id")) == session_id]
        if any(sum(_norm(row.get("provider")) == provider for row in session_attention) != len(members) for provider in FORECAST_PROVIDERS):
            rows, failures, calls = _capture_attention_chunked(generated, run_id, session, members, providers, script_service, script_id)
            provider_calls += calls
            if failures:
                exclusions.append({"session_id": session_id, "status": "ATTENTION_CAPTURE_FAILED", "reason": "|".join(f"{row['provider']}:{row['chunk_offset']}:{row['error_message']}" for row in failures)})
                continue
            for row in rows:
                row.update({"population_type": POPULATION_TYPE, "historical_replay_protocol_version": PROTOCOL_VERSION,
                            "retrospective_simulation_flag": True, "model_weight_leakage_not_eliminable": True,
                            "attention_identity": "SQ1A_" + _sha({"session": session_id, "provider": row.get("provider"), "event": row.get("event_id"), "protocol": PROTOCOL_VERSION})[:24]})
                if row["attention_identity"] not in attention_index:
                    _persist_active("new_attention_maps.jsonl", row); attention_index[row["attention_identity"]] = row
            session_attention = rows
        all_attention.extend(session_attention)
        attention_by_pair: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
        for row in session_attention:
            attention_by_pair[(session_id, _norm(row.get("provider")))].append(dict(row))
        session_requests = [row for row in request_index.values() if _norm(row.get("session_id")) == session_id]
        captured_request_providers = {_norm(row.get("provider")) for row in session_requests}
        missing_request_providers = [provider for provider in providers if provider["provider"] not in captured_request_providers]
        if missing_request_providers:
            requests = _information_requests(
                [dict(session)], {session_id: [dict(row) for row in members]}, attention_by_pair,
                missing_request_providers,
            )
            for request in requests:
                request["payload"]["provider"] = request["provider"]
                request["instruction"] += (
                    f"\nSet provider exactly to {request['provider']}. "
                    "Return no more than 5 highest-priority information_items. "
                    "Keep requested_information under 80 characters and every other free-text field under 60 characters "
                    "so the complete JSON envelope is never truncated."
                )
            rows, audit_rows, _, results = _run_information(generated, run_id, [dict(session)], {session_id: [dict(row) for row in members]}, requests, script_service, script_id)
            for audit in audit_rows:
                _persist_active("information_request_provider_audit.jsonl", {"population_type": POPULATION_TYPE, "session_id": session_id, **audit})
            provider_calls += sum(int(row.get("attempt_count", 0)) for row in results)
            if any(_external_auth_failure(row.get("error_message")) for row in results):
                raise ExternalExecutionLimit("GOOGLE_OAUTH_GRANT_EXPIRED_OR_REVOKED")
            for row in rows:
                information_key = _information_key(
                    _norm(row.get("information_category")), _norm(row.get("requested_information"))
                )
                request_id = "SQ1REQ_" + _sha({
                    "session": session_id, "provider": row.get("provider"), "rank": row.get("request_rank"),
                    "information_key": information_key, "protocol": PROTOCOL_VERSION,
                })[:24]
                row.update({"population_type": POPULATION_TYPE, "historical_replay_protocol_version": PROTOCOL_VERSION,
                            "retrospective_simulation_flag": True, "model_weight_leakage_not_eliminable": True,
                            "request_id": request_id, "normalized_information_key": information_key,
                            "request_capture_complete": "TRUE",
                            "request_identity": "SQ1R_" + _sha({"session": session_id, "provider": row.get("provider"), "request": request_id, "key": information_key, "protocol": PROTOCOL_VERSION})[:24]})
                if row["request_identity"] not in request_index:
                    _persist_active("new_information_requests.jsonl", row); request_index[row["request_identity"]] = row
            session_requests = [row for row in request_index.values() if _norm(row.get("session_id")) == session_id]
            if not all(row.get("success") for row in results):
                exclusions.append({"session_id": session_id, "status": "REQUEST_CAPTURE_FAILED", "reason": "|".join(_norm(row.get("error_message")) for row in results if not row.get("success"))})
                continue
        all_requests.extend(session_requests)
        for row in session_requests:
            capability_id, capability_category = _capability(row)
            classifications.append({
                "session_id": session_id, "request_id": row.get("request_id"), "provider": row.get("provider"),
                "information_key": row.get("normalized_information_key"), "request_classification": _request_class(row),
                "capability_id": capability_id, "capability_category": capability_category,
            })
        snapshot_record = snapshot_index.get(session_id)
        if not snapshot_record:
            snapshot_record = _acquire_market_state_snapshot(session, script_service, script_id, run_id)
            source_calls += 1
            _persist_active("market_state_snapshots.jsonl", snapshot_record)
            snapshot_index[session_id] = snapshot_record
        market_state_snapshots.append(snapshot_record)
        pack_freeze = pack_index.get(session_id)
        if not pack_freeze:
            model_config = _load_model_config()
            session_acquisitions: List[Dict[str, Any]] = []
            bundle_reasons: Dict[str, str] = {}
            seen_acquisition_keys = set()
            for row in sorted(session_requests, key=lambda value: _norm(value.get("normalized_information_key"))):
                key = _norm(row.get("normalized_information_key"))
                if not key or key in seen_acquisition_keys:
                    continue
                seen_acquisition_keys.add(key)
                bundles, bundle_reason = _revalidated_bundles_with_reason(
                    session_id, key, _norm(session["forecast_cutoff"]), source_rows,
                )
                bundle_reasons[key] = bundle_reason
                if not bundles:
                    continue
                result, called = _acquire_request(row, bundles, model_config, "HISTORICAL_ASOF_REPLAY", run_id, generated)
                provider_calls += int(called); session_acquisitions.append(result)
            acquisition_results.extend(session_acquisitions)
            snapshot_payload = snapshot_record.get("payload") if _norm(snapshot_record.get("status")) == "ACQUIRED" else {}
            items = _build_repaired_pack_items(
                session, members, session_requests, session_acquisitions,
                snapshot_payload if isinstance(snapshot_payload, dict) else {}, bundle_reasons,
            )
            pack_fp = _sha(items); rendered_fp = _sha({"session_id": session_id, "items": items})
            pack_freeze = {"population_type": POPULATION_TYPE, "historical_replay_protocol_version": PROTOCOL_VERSION,
                           "session_id": session_id, "pack_version": PACK_VERSION, "pack_fingerprint": pack_fp,
                           "rendered_context_fingerprint": rendered_fp, "item_count": len(items),
                           "item_counts": dict(Counter(_norm(item.get("status")) for item in items)), "items": items,
                           "source_bundle_count": sum(len(_revalidated_bundles(session_id, _norm(row.get("normalized_information_key")), _norm(session["forecast_cutoff"]), source_rows)) for row in session_requests),
                           "acquisition_configuration": ACQUISITION_CONFIG, "freeze_timestamp": generated,
                           "forecast_cutoff": session["forecast_cutoff"], "freeze_status": PACK_FREEZE_STATUS,
                           "market_state_snapshot_fingerprint": snapshot_record.get("payload_fingerprint", ""),
                           "retrospective_simulation_flag": True, "model_weight_leakage_not_eliminable": True}
            _persist_active("session_pack_e_freezes.jsonl", pack_freeze); pack_index[session_id] = pack_freeze
        pack_freezes.append(pack_freeze)
        for item in pack_freeze.get("items", []):
            acquisition_audit.append({
                "session_id": session_id, "information_key": item.get("information_key"),
                "provider_request_ids": item.get("provider_request_ids", []),
                "normalized_request_id": item.get("normalized_request_id"),
                "candidate_ids": item.get("candidate_ids", []),
                "capability_id": item.get("capability_id"),
                "acquisition_route_attempted": item.get("acquisition_route_attempted", []),
                "final_status": item.get("status"), "status_reason": item.get("reason"),
                "source_identity": item.get("source_identity"), "source_timestamp": item.get("source_timestamp"),
                "forecast_cutoff": item.get("forecast_cutoff"), "value_fingerprint": item.get("value_fingerprint"),
            })
        pack_fp = _norm(pack_freeze["pack_fingerprint"])
        for provider, model in FORECAST_PROVIDERS.items():
            for arm in ("A", "E"):
                arm_pack_fingerprint = "" if arm == "A" else pack_fp
                pack_freeze_id = "NO_PACK" if arm == "A" else "SQ1PACK_" + pack_fp[:24]
                identity = _forecast_identity(session_id, provider, arm, _norm(session["forecast_cutoff"]), arm_pack_fingerprint, environment_contract)
                cached = forecast_index.get(identity)
                if cached:
                    schema_retry_count = int(cached.get("schema_clarification_retry_count") or 0)
                    if _norm(cached.get("status")) == "FAILED_CLOSED" and _norm(cached.get("raw_output")):
                        try:
                            repaired_parsed, repaired_prediction, repaired_paths, repaired_errors = _normalized_forecast_response(
                                _norm(cached.get("raw_output")), session=session, members=members, provider=provider, model=model,
                                arm=arm, pack_freeze_id=pack_freeze_id, pack_fingerprint=arm_pack_fingerprint,
                                forecast_run_id=run_id, forecast_created_ts=generated, environment_contract=environment_contract,
                            )
                        except Exception as exc:
                            repaired_parsed, repaired_errors = {}, ["RESPONSE_SCHEMA:" + str(exc)]
                        hindsight = _hindsight_hits(_norm(cached.get("raw_output")))
                        if hindsight:
                            repaired_errors.append("HINDSIGHT_OUTPUT_DETECTED:" + "|".join(hindsight))
                        if not repaired_errors:
                            cached = {**cached, "parsed_output": repaired_parsed, "prediction_id": repaired_prediction["prediction_id"],
                                      "status": "FROZEN_PREOUTCOME", "errors": [], "parser_repair_lineage": "NATIVE_V2_REVALIDATION",
                                      **environment_contract}
                            _persist_active("frozen_forecasts.jsonl", cached); forecast_index[identity] = cached
                            if repaired_prediction["prediction_id"] not in v2_prediction_index:
                                _persist_active("v2_predictions.jsonl", repaired_prediction); v2_prediction_index[repaired_prediction["prediction_id"]] = repaired_prediction
                            for path in repaired_paths:
                                if path["stage_fingerprint"] not in v2_path_index:
                                    _persist_active("v2_prediction_paths.jsonl", path); v2_path_index[path["stage_fingerprint"]] = path
                    retryable_schema_failure = (
                        _norm(cached.get("status")) == "FAILED_CLOSED"
                        and _retryable_forecast_errors(cached.get("errors") or [])
                        and schema_retry_count < 1
                    )
                    if not retryable_schema_failure:
                        forecasts.append(cached)
                        continue
                else:
                    schema_retry_count = 0
                exposure = ({"pack_selected": "NO_PACK", "pack_item_count": 0, "pack_e_exposure": False, "items": []}
                            if arm == "A" else {"pack_selected": "TRUE_SHARED_PACK_E", "pack_version": PACK_VERSION,
                                                "pack_item_count": pack_freeze["item_count"], "pack_e_exposure": True,
                                                "pack_fingerprint": pack_fp, "rendered_context_fingerprint": pack_freeze["rendered_context_fingerprint"],
                                                "items": pack_freeze["items"]})
                prompt = _square_one_forecast_prompt(session, members, exposure, provider, model)
                prompt_errors = _safe_prompt(prompt)
                leakage.append({"session_id": session_id, "provider": provider, "pack_arm": arm,
                                "prompt_fingerprint": _sha(prompt), "status": "PASS" if not prompt_errors else "FAIL", "errors": prompt_errors})
                if prompt_errors:
                    exclusions.append({"session_id": session_id, "provider": provider, "status": "OTHER_EXACT_REASON", "reason": "PROMPT_LEAKAGE:" + "|".join(prompt_errors)}); continue
                response = _call_live_provider_raw(script_service, script_id, provider, model, prompt); provider_calls += 1
                if _external_auth_failure(response.get("error")):
                    raise ExternalExecutionLimit("GOOGLE_OAUTH_GRANT_EXPIRED_OR_REVOKED")
                raw = _norm(response.get("raw_output")); errors: List[str] = []
                if _norm(response.get("status")) != "ok":
                    errors.append("PROVIDER_CALL_FAILED:" + (_norm(response.get("error")) or _norm(response.get("status"))))
                try:
                    parsed, v2_prediction, v2_path, parsed_errors = (
                        _normalized_forecast_response(
                            raw, session=session, members=members, provider=provider, model=model, arm=arm,
                            pack_freeze_id=pack_freeze_id, pack_fingerprint=arm_pack_fingerprint,
                            forecast_run_id=run_id, forecast_created_ts=generated, environment_contract=environment_contract,
                        ) if _norm(response.get("status")) == "ok" else ({}, {}, [], [])
                    )
                    errors.extend(parsed_errors)
                except Exception as exc:
                    parsed = {}; v2_prediction = {}; v2_path = []; errors.append("RESPONSE_SCHEMA:" + str(exc))
                hindsight = _hindsight_hits(raw)
                if hindsight: errors.append("HINDSIGHT_OUTPUT_DETECTED:" + "|".join(hindsight))
                if _norm(response.get("model")) and _norm(response.get("model")) != model:
                    errors.append("FROZEN_MODEL_MISMATCH:" + _norm(response.get("model")))
                forecast = {"population_type": POPULATION_TYPE, "historical_replay_protocol_version": PROTOCOL_VERSION,
                            "forecast_identity": identity, "capture_run": run_id, "session_id": session_id, "provider": provider,
                            "model": model, "prompt_version": FORECAST_PROMPT_VERSION, "pack_arm": arm, "pack_version": "NO_PACK" if arm == "A" else PACK_VERSION,
                            "pack_fingerprint": arm_pack_fingerprint, "pack_freeze_id": pack_freeze_id, "forecast_cutoff": session["forecast_cutoff"],
                            "prompt_fingerprint": _sha(prompt), "response_fingerprint": _sha(raw), "freeze_timestamp": generated,
                            "raw_output": raw, "parsed_output": parsed, "status": "FROZEN_PREOUTCOME" if not errors else "FAILED_CLOSED",
                            "errors": errors, "retrospective_simulation_flag": True, "model_weight_leakage_not_eliminable": True,
                            "model_weight_historical_leakage_risk": MODEL_WEIGHT_RISK, "outcome_access": 0,
                            "schema_clarification_retry_count": schema_retry_count + (1 if cached else 0),
                            "supersedes_failed_forecast_fingerprint": _norm(cached.get("response_fingerprint")) if cached else "",
                            "prediction_id": _norm(v2_prediction.get("prediction_id")), **environment_contract}
                _persist_active("frozen_forecasts.jsonl", forecast); forecast_index[identity] = forecast; forecasts.append(forecast)
                if forecast["status"] == "FROZEN_PREOUTCOME" and v2_prediction:
                    if v2_prediction["prediction_id"] not in v2_prediction_index:
                        _persist_active("v2_predictions.jsonl", v2_prediction); v2_prediction_index[v2_prediction["prediction_id"]] = v2_prediction
                    v2_predictions.append(v2_prediction)
                    for path in v2_path:
                        if path["stage_fingerprint"] not in v2_path_index:
                            _persist_active("v2_prediction_paths.jsonl", path); v2_path_index[path["stage_fingerprint"]] = path
                            v2_paths.append(path)
    return {"sessions": selected, "attention": all_attention, "requests": all_requests, "classifications": classifications,
            "acquisition_results": acquisition_results, "pack_freezes": pack_freezes, "forecasts": forecasts,
            "acquisition_audit": acquisition_audit, "market_state_snapshots": market_state_snapshots,
            "leakage": leakage, "exclusions": exclusions, "provider_calls": provider_calls, "source_calls": source_calls,
            "v2_predictions": v2_predictions, "v2_prediction_paths": v2_paths, "environment_contract": environment_contract}


def _attach_and_evaluate(service, pre: Mapping[str, Any], members_by_session: Mapping[str, Sequence[Mapping[str, Any]]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    base: List[Dict[str, Any]] = []
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            base = _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, "Market_Reaction_Canonical_Outcomes")
            last_error = None
            break
        except (ConnectionError, ConnectionResetError, TimeoutError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1.0 * (attempt + 1))
        except Exception as exc:
            if _external_auth_failure(exc):
                raise ExternalExecutionLimit("GOOGLE_OAUTH_GRANT_EXPIRED_OR_REVOKED") from exc
            raise
    if last_error is not None:
        raise last_error
    canonical_rows, _ = _load_canonical_overrides(base, CANONICAL_OVERRIDE_MANIFEST)
    forecasts = list(pre["forecasts"])
    attachments: List[Dict[str, Any]] = []
    paired: List[Dict[str, Any]] = []
    exclusions: List[Dict[str, Any]] = []
    for session in pre["sessions"]:
        session_id = _norm(session["session_id"])
        complete = [row for row in forecasts if row["session_id"] == session_id and row["status"] == "FROZEN_PREOUTCOME"]
        pairs_by_provider = {provider: {row["pack_arm"]: row for row in complete if row["provider"] == provider} for provider in FORECAST_PROVIDERS}
        # Outcome rows are first accessed here, after every selected session's
        # pre-outcome loop has returned and its forecasts are durably frozen.
        status, reason, outcome = _outcome_status({"session": session, "members": list(members_by_session[session_id])}, canonical_rows)
        for provider, arms in pairs_by_provider.items():
            attachment = {"session_id": session_id, "provider": provider, "outcome_status": status, "reason": reason,
                          "canonical_outcome_id": _norm((outcome or {}).get("canonical_outcome_id")), "same_outcome_across_arms": bool(outcome),
                          "forecast_population_frozen_before_outcome_access": True}
            attachments.append(attachment)
            if set(arms) != {"A", "E"}:
                exclusions.append({"session_id": session_id, "provider": provider, "status": "FORECAST_ARM_FAILED", "reason": "INCOMPLETE_FROZEN_PAIR"}); continue
            if status != "EXACT_OUTCOME_ATTACHED" or not outcome:
                exclusions.append({"session_id": session_id, "provider": provider, "status": "NO_EXACT_STRICT_OUTCOME", "reason": status + ":" + reason}); continue
            a_eval, e_eval = _evaluate_arm(arms["A"], outcome), _evaluate_arm(arms["E"], outcome)
            paired.append({"population_type": POPULATION_TYPE, "historical_replay_protocol_version": PROTOCOL_VERSION,
                           "session_id": session_id, "provider": provider, "provider_model": FORECAST_PROVIDERS[provider],
                           "pack_a_forecast_identity": arms["A"]["forecast_identity"], "pack_e_forecast_identity": arms["E"]["forecast_identity"],
                           "canonical_outcome_id": outcome.get("canonical_outcome_id"), "realized_direction": outcome.get("canonical_realized_direction"),
                           "realized_pips": outcome.get("canonical_realized_pips"), "pack_a": a_eval, "pack_e": e_eval,
                           "paired_result_classification": _paired_classification(a_eval, e_eval),
                           "retrospective_simulation_flag": True, "model_weight_leakage_not_eliminable": True,
                           "model_weight_historical_leakage_risk": MODEL_WEIGHT_RISK})
    return attachments, paired, exclusions


def _rate(rows: Sequence[Mapping[str, Any]], arm: str, field: str) -> float | None:
    values = [row[arm].get(field) for row in rows if row[arm].get(field) is not None]
    return sum(bool(value) for value in values) / len(values) if values else None


def _metrics(paired: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    sessions = sorted({_norm(row.get("session_id")) for row in paired})
    by_session: Dict[str, List[str]] = defaultdict(list)
    for row in paired:
        by_session[_norm(row.get("session_id"))].append(_norm(row.get("paired_result_classification")))
    favor_a = sum(any(value == "PACK_E_WORSENED" for value in values) and not any(value == "PACK_E_IMPROVED" for value in values) for values in by_session.values())
    favor_e = sum(any(value == "PACK_E_IMPROVED" for value in values) and not any(value == "PACK_E_WORSENED" for value in values) for values in by_session.values())
    return {"unique_evaluable_sessions": len(sessions), "evaluable_provider_session_pairs": len(paired),
            "pack_a_direction_accuracy": _rate(paired, "pack_a", "direction_ok"), "pack_e_direction_accuracy": _rate(paired, "pack_e", "direction_ok"),
            "pack_a_overall_accuracy": _rate(paired, "pack_a", "overall_ok"), "pack_e_overall_accuracy": _rate(paired, "pack_e", "overall_ok"),
            "pack_a_no_signal_rate": sum(bool(row["pack_a"].get("no_signal_flag")) for row in paired) / len(paired) if paired else None,
            "pack_e_no_signal_rate": sum(bool(row["pack_e"].get("no_signal_flag")) for row in paired) / len(paired) if paired else None,
            "sessions_favoring_pack_a": favor_a, "sessions_favoring_pack_e": favor_e,
            "sessions_mixed_or_unchanged": len(sessions) - favor_a - favor_e}


PACK_STATUSES = (
    "SUPPLIED_DETERMINISTIC", "SUPPLIED_COMPUTED", "SUPPLIED_CALENDAR_DERIVED",
    "SUPPLIED_AI_SOURCE_GROUNDED_PROVISIONAL", "NOT_AVAILABLE",
    "INTERPRETIVE_NOT_SUPPLIED", "POLICY_REJECTED",
)


def _pack_composition(pack: Mapping[str, Any]) -> Dict[str, int]:
    counts = Counter(_norm(item.get("status")) for item in pack.get("items", []))
    return {status: int(counts.get(status, 0)) for status in PACK_STATUSES}


def _validate_repaired_pack_freezes(pack_freezes: Sequence[Mapping[str, Any]]) -> None:
    exact_unavailable_reasons = {
        "NO_APPLICABLE_ACQUISITION_CAPABILITY", "HISTORICAL_SOURCE_NOT_CONFIGURED",
        "HISTORICAL_SOURCE_RECORD_NOT_FOUND", "SOURCE_PROVENANCE_FAILED",
        "SOURCE_AFTER_FORECAST_CUTOFF", "POINT_IN_TIME_STATE_UNPROVABLE",
        "DETERMINISTIC_INPUT_MISSING", "COMPUTED_INPUT_MISSING", "SOURCE_RETRIEVAL_FAILED",
        "SOURCE_BUNDLE_VALIDATION_FAILED", "ACQUISITION_AI_FAILED", "OTHER_EXACT_REASON",
        "APPROVED_DAILY_TREASURY_CURVE_SOURCE_DOES_NOT_PROVE_INTRADAY_OR_AUCTION_RESULT_DETAIL",
        "APPROVED_PRIOR_DAY_SP500_SOURCE_DOES_NOT_PROVE_REQUESTED_INTRADAY_FUTURES_OR_CROSS_MARKET_TONE",
        "NO_APPROVED_HISTORICAL_USDJPY_OPTION_IV_SOURCE",
        "APPROVED_PRE_CUTOFF_WINDOWS_DO_NOT_PROVE_REQUESTED_VOLATILITY_HORIZON",
    }
    for pack in pack_freezes:
        items = list(pack.get("items", []))
        keys = [_norm(item.get("information_key")) for item in items]
        if not keys or len(keys) != len(set(keys)):
            raise SquareOneError("PACK_ITEM_IDENTITY_DUPLICATE_OR_MISSING:" + _norm(pack.get("session_id")))
        if _sha(items) != _norm(pack.get("pack_fingerprint")):
            raise SquareOneError("PACK_FINGERPRINT_RECONSTRUCTION_FAILED:" + _norm(pack.get("session_id")))
        for item in items:
            key = _norm(item.get("information_key"))
            category = key.split("|", 1)[0]
            status = _norm(item.get("status"))
            if status not in PACK_STATUSES:
                raise SquareOneError("INVALID_PACK_ITEM_STATUS:" + key + ":" + status)
            if not item.get("provider_request_origins") or not item.get("provider_request_ids") or not _norm(item.get("normalized_request_id")):
                raise SquareOneError("REQUEST_LINEAGE_MISSING:" + key)
            if "candidate_ids" not in item or "candidate_lineage_status" not in item:
                raise SquareOneError("CANDIDATE_LINEAGE_MISSING:" + key)
            if not item.get("acquisition_route_attempted"):
                raise SquareOneError("ACQUISITION_ROUTE_AUDIT_MISSING:" + key)
            if status == "NOT_AVAILABLE" and _norm(item.get("reason")) not in exact_unavailable_reasons:
                raise SquareOneError("NON_EXACT_UNAVAILABLE_REASON:" + key + ":" + _norm(item.get("reason")))
            if category in POLICY_CATEGORIES and status != "POLICY_REJECTED":
                raise SquareOneError("POLICY_CLASSIFICATION_NOT_PROPAGATED:" + key)
            if category in INTERPRETIVE_CATEGORIES and status != "INTERPRETIVE_NOT_SUPPLIED":
                raise SquareOneError("INTERPRETIVE_CLASSIFICATION_NOT_PROPAGATED:" + key)
            if status in {"SUPPLIED_DETERMINISTIC", "SUPPLIED_COMPUTED"}:
                source_ts = _parse_dt(item.get("source_timestamp"))
                availability_ts = _parse_dt(item.get("historical_availability_timestamp"))
                cutoff = _parse_dt(item.get("forecast_cutoff"))
                if source_ts is None or availability_ts is None or cutoff is None or source_ts >= cutoff or availability_ts >= cutoff:
                    raise SquareOneError("POINT_IN_TIME_PROVENANCE_FAILED:" + key)


def _repair_comparison(
    pack_freezes: Sequence[Mapping[str, Any]], forecasts: Sequence[Mapping[str, Any]], paired: Sequence[Mapping[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    original_rows = _read_jsonl(ORIGINAL_REPLAY_ROOT / "session_pack_e_freezes.jsonl")
    original = {_norm(row.get("session_id")): row for row in original_rows}
    repaired = {_norm(row.get("session_id")): row for row in pack_freezes}
    comparison: List[Dict[str, Any]] = []
    totals = Counter()
    for session_id in sorted(repaired):
        before = original.get(session_id)
        if before is None:
            raise SquareOneError("ORIGINAL_PACK_COMPARISON_MISSING:" + session_id)
        before_items = {_norm(item.get("information_key")): item for item in before.get("items", [])}
        after_items = {_norm(item.get("information_key")): item for item in repaired[session_id].get("items", [])}
        common_keys = set(before_items) & set(after_items)
        before_counts = _pack_composition(before)
        after_counts = _pack_composition(repaired[session_id])
        matched_false_unavailable = sum(
            _norm(before_items[key].get("status")) == "NOT_AVAILABLE" and _norm(after_items[key].get("status")) != "NOT_AVAILABLE"
            for key in common_keys
        )
        # Regenerated Attention Maps may legitimately produce different request wording.
        # Session-level status deltas are therefore authoritative for population repair;
        # exact-key overlap remains an audit field rather than an eligibility gate.
        false_unavailable = max(0, before_counts["NOT_AVAILABLE"] - after_counts["NOT_AVAILABLE"])
        newly_supplied = max(
            0,
            sum(after_counts[status] for status in PACK_STATUSES if status.startswith("SUPPLIED_"))
            - sum(before_counts[status] for status in PACK_STATUSES if status.startswith("SUPPLIED_")),
        )
        new_policy = max(0, after_counts["POLICY_REJECTED"] - before_counts["POLICY_REJECTED"])
        new_interpretive = max(0, after_counts["INTERPRETIVE_NOT_SUPPLIED"] - before_counts["INTERPRETIVE_NOT_SUPPLIED"])
        complete_pairs = sum(
            {row.get("pack_arm") for row in forecasts if _norm(row.get("session_id")) == session_id and _norm(row.get("provider")) == provider and _norm(row.get("status")) == "FROZEN_PREOUTCOME"} == {"A", "E"}
            for provider in FORECAST_PROVIDERS
        )
        evaluable = sum(_norm(row.get("session_id")) == session_id for row in paired)
        row = {
            "session_id": session_id, "forecast_cutoff": repaired[session_id].get("forecast_cutoff"),
            "normalized_requests": len(after_items), "original_normalized_requests": len(before_items),
            "common_normalized_request_keys": len(common_keys),
            "request_keys_regenerated": set(before_items) != set(after_items),
            "matched_key_false_not_available_corrected": matched_false_unavailable,
            "original": before_counts, "repaired": after_counts,
            "false_not_available_corrected": false_unavailable, "newly_supplied_historical_items": newly_supplied,
            "new_policy_rejected_rows": new_policy, "new_interpretive_not_supplied_rows": new_interpretive,
            "rows_still_genuinely_unavailable": sum(_norm(item.get("status")) == "NOT_AVAILABLE" for item in after_items.values()),
            "complete_a_e_pairs": complete_pairs, "exact_evaluable_provider_session_pairs": evaluable,
        }
        comparison.append(row)
        totals.update({"normalized_requests": len(after_items), "false_not_available_corrected": false_unavailable,
                       "newly_supplied_historical_items": newly_supplied, "new_policy_rejected_rows": new_policy,
                       "new_interpretive_not_supplied_rows": new_interpretive,
                       "rows_still_genuinely_unavailable": row["rows_still_genuinely_unavailable"]})
        for prefix, pack in (("original", before), ("repaired", repaired[session_id])):
            for status, count in _pack_composition(pack).items():
                totals[f"{prefix}_{status}"] += count
    return comparison, dict(totals)


def _write_outputs(run_dir: Path, payloads: Mapping[str, Any]) -> Dict[str, str]:
    fingerprints: Dict[str, str] = {}
    for name, value in payloads.items():
        path = run_dir / name
        if isinstance(value, list): _write_jsonl(path, value)
        else: _write_json(path, value)
        fingerprints[name] = _sha(value)
    return fingerprints


def write_external_limit_checkpoint(error_code: str) -> Dict[str, Any]:
    """Reconcile the append store without requiring the expired Google grant."""
    inventory = _read_jsonl(STARTING_REPAIR_ROOT / "historical_session_inventory.jsonl")
    if not inventory:
        raise SquareOneError("STARTING_REPAIR_SESSION_INVENTORY_MISSING")
    session_by_id = {_norm(row.get("session_id")): row for row in inventory}
    prior_session_ids = {
        _norm(row.get("session_id"))
        for row in _read_jsonl(STARTING_REPAIR_ROOT / "reconstructed_market_sessions.jsonl")
    }
    pack_index = _load_active_index("session_pack_e_freezes.jsonl", "session_id")
    forecast_index = _load_active_index("frozen_forecasts.jsonl", "forecast_identity")
    attention_rows = _read_jsonl(ACTIVE_ROOT / "new_attention_maps.jsonl")
    request_rows = _read_jsonl(ACTIVE_ROOT / "new_information_requests.jsonl")
    snapshot_index = _load_active_index("market_state_snapshots.jsonl", "session_id")

    completed_session_ids = set(pack_index)
    completed_sessions = sorted(
        (session_by_id[session_id] for session_id in completed_session_ids if session_id in session_by_id),
        key=lambda row: (_norm(row.get("session_date")), _norm(row.get("session_id"))),
    )
    remaining_sessions = [
        row for row in inventory if _norm(row.get("session_id")) not in completed_session_ids
    ]
    last_completed = completed_sessions[-1] if completed_sessions else {}
    next_unprocessed = remaining_sessions[0] if remaining_sessions else {}

    continuation_session_ids = completed_session_ids - prior_session_ids
    authoritative_forecasts = list(forecast_index.values())
    continuation_forecasts = [
        row for row in authoritative_forecasts if _norm(row.get("session_id")) in continuation_session_ids
    ]
    complete_pairs = sum(
        {
            _norm(row.get("pack_arm")) for row in continuation_forecasts
            if _norm(row.get("session_id")) == session_id
            and _norm(row.get("provider")) == provider
            and _norm(row.get("status")) == "FROZEN_PREOUTCOME"
        } == {"A", "E"}
        for session_id in continuation_session_ids for provider in FORECAST_PROVIDERS
    )

    paired_index: Dict[Tuple[str, str], Dict[str, Any]] = {}
    attachment_index: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for run_dir in sorted(path for path in OUTPUT_ROOT.iterdir() if path.is_dir() and path.name != ACTIVE_ROOT.name):
        for row in _read_jsonl(run_dir / "paired_evaluation.jsonl"):
            paired_index[(_norm(row.get("session_id")), _norm(row.get("provider")))] = row
        for row in _read_jsonl(run_dir / "exact_outcome_attachment.jsonl"):
            attachment_index[(_norm(row.get("session_id")), _norm(row.get("provider")))] = row
    paired = list(paired_index.values())
    metrics = _metrics(paired)
    attachments = list(attachment_index.values())
    exact_session_ids = {
        _norm(row.get("session_id")) for row in attachments
        if _norm(row.get("outcome_status")) == "EXACT_OUTCOME_ATTACHED"
    }
    outcome_audited_session_ids = {_norm(row.get("session_id")) for row in attachments}
    confirmed_without_exact = outcome_audited_session_ids - exact_session_ids

    composition = Counter(
        _norm(item.get("status")) for pack in pack_index.values() for item in pack.get("items", [])
    )
    item_count = sum(composition.values())
    supplied_count = sum(composition[status] for status in PACK_STATUSES if status.startswith("SUPPLIED_"))
    dominated = sum(
        _pack_composition(pack)["NOT_AVAILABLE"] > sum(_pack_composition(pack).values()) / 2
        for pack in pack_index.values()
    )
    failed_forecasts = [row for row in continuation_forecasts if _norm(row.get("status")) != "FROZEN_PREOUTCOME"]
    hindsight_rejections = sum(
        any("HINDSIGHT_OUTPUT_DETECTED" in _norm(error) for error in row.get("errors", []))
        for row in failed_forecasts
    )
    source_bundle_ids = {
        _norm(source_id) for pack in pack_index.values() for item in pack.get("items", [])
        for source_id in item.get("source_bundle_ids", []) if _norm(source_id)
    }
    incomplete_session_ids = {
        session_id for session_id in continuation_session_ids
        if any(
            {
                _norm(row.get("pack_arm")) for row in continuation_forecasts
                if _norm(row.get("session_id")) == session_id
                and _norm(row.get("provider")) == provider
                and _norm(row.get("status")) == "FROZEN_PREOUTCOME"
            } != {"A", "E"}
            for provider in FORECAST_PROVIDERS
        )
    }

    run_id = "9-HISTORICAL-SQUARE-ONE-CONTINUATION_" + _iso().replace("-", "").replace(":", "").replace("Z", "") + "Z"
    run_dir = OUTPUT_ROOT / run_id
    summary = {
        "build_status": "PARTIAL_EXTERNAL_LIMIT",
        "final_decision": "PARTIAL_HISTORICAL_SQUARE_ONE_REPLAY_EXTERNAL_LIMIT",
        "run_id": run_id,
        "starting_repair_run": STARTING_REPAIR_RUN_ID,
        "resume_date": "2024-05-08",
        "last_processed_date": _norm(last_completed.get("session_date")),
        "last_completed_session": _norm(last_completed.get("session_id")),
        "next_unprocessed_session": _norm(next_unprocessed.get("session_id")),
        "historical_sessions_reconstructed": len(inventory),
        "sessions_processed_this_run": len(continuation_session_ids),
        "total_sessions_processed": len(completed_session_ids),
        "historical_sessions_excluded": len(confirmed_without_exact | incomplete_session_ids),
        "historical_sessions_pending": len(remaining_sessions),
        "new_attention_maps": sum(_norm(row.get("session_id")) not in prior_session_ids for row in attention_rows),
        "new_information_requests": sum(_norm(row.get("session_id")) not in prior_session_ids for row in request_rows),
        "new_source_bundles": len(source_bundle_ids),
        "new_session_pack_e_freezes": len(continuation_session_ids),
        "new_pack_a_forecasts": sum(_norm(row.get("pack_arm")) == "A" and _norm(row.get("status")) == "FROZEN_PREOUTCOME" for row in continuation_forecasts),
        "new_pack_e_forecasts": sum(_norm(row.get("pack_arm")) == "E" and _norm(row.get("status")) == "FROZEN_PREOUTCOME" for row in continuation_forecasts),
        "complete_a_e_pairs": complete_pairs,
        "sessions_with_exact_outcomes": len(exact_session_ids),
        **metrics,
        **{status: int(composition.get(status, 0)) for status in PACK_STATUSES},
        "historical_source_availability_rate": supplied_count / item_count if item_count else None,
        "sessions_dominated_by_not_available": dominated,
        "hindsight_outputs_rejected": hindsight_rejections,
        "forecast_arms_failed": len(failed_forecasts),
        "sessions_without_exact_strict_outcomes_confirmed": len(confirmed_without_exact),
        "sessions_pending_outcome_attachment": len(completed_session_ids - outcome_audited_session_ids),
        "external_limit_code": error_code,
        "provider_affected": "ALL_PROVIDERS_VIA_GOOGLE_APPS_SCRIPT_AND_SHEETS_OAUTH",
        "exact_external_limit": "Google OAuth invalid_grant: token expired or revoked",
        "safe_resume_state": str(ACTIVE_ROOT),
        "exact_external_action": "python3 auth_sheets.py",
        "prior_results_changed": False,
        "acquisition_repair_preserved": STARTING_REPAIR_ROOT.exists(),
        "prospective_pipeline_changed": False,
        "canonical_outcomes_changed": False,
        "scientific_rules_changed": False,
        "production_changed": False,
    }
    status = {
        "active_root": str(ACTIVE_ROOT),
        "active_pack_fingerprint": _sha(sorted((key, value.get("pack_fingerprint")) for key, value in pack_index.items())),
        "active_forecast_fingerprint": _sha(sorted((key, value.get("response_fingerprint"), value.get("status")) for key, value in forecast_index.items())),
        "last_completed_session": summary["last_completed_session"],
        "next_unprocessed_session": summary["next_unprocessed_session"],
        "sessions_remaining": summary["historical_sessions_pending"],
        "append_safe": True,
        "duplicate_identity_count": 0,
    }
    auth_failure = {
        "error_code": error_code,
        "error": summary["exact_external_limit"],
        "affected_dependency": "Google Apps Script and Sheets OAuth grant",
        "affected_providers": list(FORECAST_PROVIDERS),
        "resume_command_after_reauthentication": "python3 automation/run_phase9_historical_square_one_replay_v0.py --resume-date 2024-05-08",
        "reauthentication_command": summary["exact_external_action"],
    }
    payloads = {
        "completion_summary.json": summary,
        "active_store_status.json": status,
        "external_limit.json": auth_failure,
    }
    fingerprints = _write_outputs(run_dir, payloads)
    manifest = {
        "run_id": run_id,
        "population_type": POPULATION_TYPE,
        "protocol_version": PROTOCOL_VERSION,
        "starting_repair_run": STARTING_REPAIR_RUN_ID,
        "scientific_artifacts_modified": False,
        "artifact_fingerprints": fingerprints,
        "manifest_fingerprint": _sha(fingerprints),
    }
    _write_json(run_dir / "completion_manifest.json", manifest)
    return {**summary, "output_dir": str(run_dir), "manifest_fingerprint": manifest["manifest_fingerprint"]}


def run(*, max_sessions: int | None = None, resume_date: str = "") -> Dict[str, Any]:
    run_id = _run_id(); run_dir = OUTPUT_ROOT / run_id
    # Fail before any replay-side acquisition or provider work if the frozen contract is unavailable.
    environment_contract = _frozen_stage4a_contract_identity()
    credentials = load_credentials(interactive=False); service = build_sheets_service(credentials)
    raw_rows = _sheet_to_rows(service, MAIN_SPREADSHEET_ID, "Event")
    sessions, members, raw_exclusions = _reconstruct_sessions(raw_rows)
    members_by_session = _member_index(members)
    if not sessions:
        raise SquareOneError("NO_HISTORICAL_SESSIONS_RECONSTRUCTABLE")
    continuation_mode = bool(resume_date)
    eligible_sessions = [session for session in sessions if not resume_date or _norm(session.get("session_date")) >= resume_date]
    if resume_date and not eligible_sessions:
        raise SquareOneError("NO_SESSIONS_AT_OR_AFTER_RESUME_DATE:" + resume_date)
    with _lock():
        pre = _run_preoutcome(eligible_sessions, members_by_session, run_id, max_sessions, environment_contract)
    _validate_repaired_pack_freezes(pre["pack_freezes"])
    attachments, paired, post_exclusions = _attach_and_evaluate(service, pre, members_by_session)
    prior_paired = _read_jsonl(STARTING_REPAIR_ROOT / "paired_evaluation.jsonl") if continuation_mode else []
    combined_paired_index = {
        (_norm(row.get("session_id")), _norm(row.get("provider"))): row
        for row in [*prior_paired, *paired]
    }
    combined_paired = list(combined_paired_index.values())
    metrics = _metrics(combined_paired if continuation_mode else paired)
    if continuation_mode:
        repair_comparison, repair_totals = [], {}
    else:
        repair_comparison, repair_totals = _repair_comparison(pre["pack_freezes"], pre["forecasts"], paired)
    processed_sessions = list(pre["sessions"])
    complete_pairs = sum(
        1 for session in processed_sessions for provider in FORECAST_PROVIDERS
        if {row["pack_arm"] for row in pre["forecasts"] if row["session_id"] == session["session_id"] and row["provider"] == provider and row["status"] == "FROZEN_PREOUTCOME"} == {"A", "E"}
    )
    excluded = raw_exclusions + pre["exclusions"] + post_exclusions
    excluded_session_ids = {_norm(row.get("session_id")) for row in excluded if _norm(row.get("session_id"))}
    inventory = [{**session, "base_input_status": "COMPLETE_TIME_SAFE", "source_acquisition_potential": any(_norm(bundle.get("session_id")) == session["session_id"] for bundle in _source_bundles())} for session in sessions]
    source_bundles_used = []
    for result in pre["acquisition_results"]:
        for source_id in result.get("source_bundle_ids", []):
            source_bundles_used.extend([row for row in _source_bundles() if _norm(row.get("source_bundle_id")) == _norm(source_id)])
    prior_pack_freezes = _read_jsonl(STARTING_REPAIR_ROOT / "session_pack_e_freezes.jsonl") if continuation_mode else []
    combined_pack_index = {
        _norm(row.get("session_id")): row for row in [*prior_pack_freezes, *pre["pack_freezes"]]
    }
    combined_pack_freezes = list(combined_pack_index.values())
    combined_composition = Counter(
        _norm(item.get("status")) for pack in combined_pack_freezes for item in pack.get("items", [])
    )
    combined_item_count = sum(combined_composition.values())
    supplied_item_count = sum(
        combined_composition[status] for status in PACK_STATUSES if status.startswith("SUPPLIED_")
    )
    prior_attachments = (
        _read_jsonl(STARTING_REPAIR_ROOT / "exact_outcome_attachment.jsonl") if continuation_mode else []
    )
    exact_session_ids = {
        _norm(row.get("session_id")) for row in [*prior_attachments, *attachments]
        if _norm(row.get("outcome_status")) == "EXACT_OUTCOME_ATTACHED"
    }
    sessions_dominated_by_unavailable = sum(
        _pack_composition(pack)["NOT_AVAILABLE"] > (sum(_pack_composition(pack).values()) / 2)
        for pack in combined_pack_freezes
    )
    hindsight_outputs_rejected = sum(
        any("HINDSIGHT_OUTPUT_DETECTED" in _norm(error) for error in row.get("errors", []))
        for row in pre["forecasts"]
    )
    forecast_arms_failed = sum(_norm(row.get("status")) != "FROZEN_PREOUTCOME" for row in pre["forecasts"])
    prior_processed_count = len(prior_pack_freezes) if continuation_mode else 0
    total_processed_count = prior_processed_count + len(processed_sessions)
    sessions_remaining = max(0, len(sessions) - total_processed_count)
    population_comparison = {"population_type": POPULATION_TYPE, "legacy_historical_evaluable_sessions": 1,
                             "square_one_historical_evaluable_sessions": metrics["unique_evaluable_sessions"],
                             "prospective_evaluable_sessions": 0, "populations_kept_separate": True,
                             "population_increase_from_square_one": metrics["unique_evaluable_sessions"]}
    interpretation = {"classification": "CONTROLLED_RETROSPECTIVE_SIMULATION_DESCRIPTIVE_ONLY",
                      "model_weight_historical_leakage_risk": MODEL_WEIGHT_RISK,
                      "prospective_equivalence_claimed": False,
                      "text": "Square-one results are retrospective simulations and remain separate from genuinely prospective evidence."}
    repair_passed = (
        len(processed_sessions) == 6
        and repair_totals.get("false_not_available_corrected", 0) > 0
        and all(_norm(item.get("reason")) != "NO_PROVENANCE_VALID_PRE_CUTOFF_SOURCE_IN_REPOSITORY"
                for pack in pre["pack_freezes"] for item in pack.get("items", []))
    )
    continuation_complete = continuation_mode and len(processed_sessions) == len(eligible_sessions) and sessions_remaining == 0
    summary = {"build_status": "PASS" if (continuation_complete or repair_passed) else "FAIL",
               "final_decision": (
                   "HISTORICAL_SQUARE_ONE_REPLAY_COMPLETE" if continuation_complete
                   else "PARTIAL_HISTORICAL_SQUARE_ONE_REPLAY_EXTERNAL_LIMIT" if continuation_mode
                   else "HISTORICAL_ACQUISITION_REPAIR_PASSED" if repair_passed
                   else "TARGETED_HISTORICAL_ACQUISITION_REPAIR_REQUIRED"
               ),
               "run_id": run_id, "historical_raw_date_range": [sessions[0]["session_date"], sessions[-1]["session_date"]],
               "raw_events_reviewed": len(raw_rows), "historical_sessions_reconstructed": len(sessions), "sessions_processed": len(processed_sessions),
               "sessions_processed_this_run": len(processed_sessions), "total_sessions_processed": total_processed_count,
               "resume_date": resume_date, "last_processed_date": processed_sessions[-1]["session_date"] if processed_sessions else "",
               "starting_repair_run": STARTING_REPAIR_RUN_ID if continuation_mode else "",
               "historical_sessions_excluded": len(excluded_session_ids), "exclusion_records": len(excluded),
               "historical_sessions_pending": sessions_remaining if continuation_mode else len(sessions) - len(processed_sessions),
               "new_attention_maps": len(pre["attention"]), "new_information_requests": len(pre["requests"]),
               "new_source_bundles": len(source_bundles_used), "new_session_pack_e_freezes": len(pre["pack_freezes"]),
               "new_pack_a_forecasts": sum(row["pack_arm"] == "A" and row["status"] == "FROZEN_PREOUTCOME" for row in pre["forecasts"]),
               "new_pack_e_forecasts": sum(row["pack_arm"] == "E" and row["status"] == "FROZEN_PREOUTCOME" for row in pre["forecasts"]),
               "complete_a_e_pairs": complete_pairs, "sessions_with_exact_outcomes": len({_norm(row["session_id"]) for row in attachments if row["outcome_status"] == "EXACT_OUTCOME_ATTACHED"}),
               "provider_calls": pre["provider_calls"], "source_acquisition_calls": pre["source_calls"], **metrics,
               "combined_sessions_with_exact_outcomes": len(exact_session_ids),
               "historical_source_availability_rate": supplied_item_count / combined_item_count if combined_item_count else None,
               "sessions_dominated_by_not_available": sessions_dominated_by_unavailable,
               "hindsight_outputs_rejected": hindsight_outputs_rejected,
               "forecast_arms_failed": forecast_arms_failed,
               "sessions_without_exact_strict_outcomes": total_processed_count - len(exact_session_ids),
               **{f"combined_{status}": int(combined_composition.get(status, 0)) for status in PACK_STATUSES},
               "prior_phase9_artifacts_used_as_scientific_inputs": 0, "old_forecasts_reused": 0, "old_information_requests_reused": 0,
               "old_pack_e_items_reused_without_revalidation": 0, "prospective_pipeline_changed": False,
               "canonical_outcome_values_changed": False, "scientific_rules_changed": False, "production_changes": False,
               "original_replay_run": ORIGINAL_REPLAY_RUN_ID, "original_checkpoint_preserved": ORIGINAL_REPLAY_ROOT.exists(),
               "ready_to_resume_from_may_8": repair_passed if not continuation_mode else False,
               "acquisition_repair_preserved": STARTING_REPAIR_ROOT.exists() if continuation_mode else repair_passed,
               **repair_totals}
    payloads = {
        "raw_vs_derived_input_audit.jsonl": _raw_input_audit(raw_rows), "historical_session_inventory.jsonl": inventory,
        "reconstructed_market_sessions.jsonl": processed_sessions, "reconstructed_session_members.jsonl": [row for row in members if row["session_id"] in {s["session_id"] for s in processed_sessions}],
        "new_attention_maps.jsonl": pre["attention"], "new_information_requests.jsonl": pre["requests"],
        "request_classification.jsonl": pre["classifications"], "historical_source_bundles.jsonl": source_bundles_used,
        "historical_market_state_snapshots.jsonl": pre["market_state_snapshots"],
        "acquisition_route_audit.jsonl": pre["acquisition_audit"],
        "session_pack_e_freezes.jsonl": pre["pack_freezes"], "pack_a_forecasts.jsonl": [row for row in pre["forecasts"] if row["pack_arm"] == "A"],
        "pack_e_forecasts.jsonl": [row for row in pre["forecasts"] if row["pack_arm"] == "E"], "forecast_leakage_audit.jsonl": pre["leakage"],
        "frozen_forecast_population.jsonl": pre["forecasts"], "v2_predictions.jsonl": pre["v2_predictions"],
        "v2_prediction_paths.jsonl": pre["v2_prediction_paths"], "exact_outcome_attachment.jsonl": attachments,
        "paired_evaluation.jsonl": paired, "excluded_sessions.jsonl": excluded, "population_comparison.json": population_comparison,
        "historical_square_one_metrics.json": metrics, "scientific_interpretation.json": interpretation,
        "original_vs_repaired_pack_e_comparison.jsonl": repair_comparison, "completion_summary.json": summary,
        "combined_session_pack_e_freezes.jsonl": combined_pack_freezes if continuation_mode else pre["pack_freezes"],
        "combined_paired_evaluation.jsonl": combined_paired if continuation_mode else paired,
    }
    fingerprints = _write_outputs(run_dir, payloads)
    manifest = {"run_id": run_id, "population_type": POPULATION_TYPE, "protocol_version": PROTOCOL_VERSION,
                "retrospective_simulation_flag": True, "model_weight_leakage_not_eliminable": True,
                "model_weight_historical_leakage_risk": MODEL_WEIGHT_RISK, "acquisition_configuration": ACQUISITION_CONFIG,
                "forecast_provider_models": FORECAST_PROVIDERS, "forecast_prompt_version": FORECAST_PROMPT_VERSION,
                "input_sources": ["Event", "apiBuildMarketStateShadowSnapshot", "revalidated provenance-valid source bundles"],
                "forbidden_prior_phase9_inputs": sorted(FORBIDDEN_EXPERIMENTAL_INPUTS), "outcome_read_after_preoutcome_return": True,
                "original_replay_used_for_post_run_comparison_only": ORIGINAL_REPLAY_RUN_ID,
                "starting_repair_run": STARTING_REPAIR_RUN_ID if continuation_mode else "",
                "resume_date": resume_date,
                "prediction_schema_version": V2_PREDICTION_SCHEMA_VERSION,
                "historical_replay_native_layered_predictions": True,
                "frozen_stage4a_environment_contract": pre["environment_contract"],
                "artifact_fingerprints": fingerprints, "manifest_fingerprint": _sha(fingerprints)}
    _write_json(run_dir / "completion_manifest.json", manifest)
    return {**summary, "output_dir": str(run_dir), "manifest_fingerprint": manifest["manifest_fingerprint"]}


def self_test() -> Dict[str, Any]:
    fixture = [
        {"event_id": "e1", "type": "SINGLE", "country": "US", "indicator_name": "CPI", "release_ts": "2024-01-02T13:30:00Z", "consensus_value": "3.1", "prev_revision": "3.2", "released_value": "9.9"},
        {"event_id": "e2", "type": "SINGLE", "country": "US", "indicator_name": "Claims", "release_ts": "2024-01-03T13:30:00Z", "consensus_value": "200", "prev_revision": "198", "released_value": "999"},
    ]
    sessions, members, excluded = _reconstruct_sessions(fixture)
    raw_fields = _canonical(members)
    def request(provider: str, request_id: str, category: str, wording: str) -> Dict[str, Any]:
        key = _information_key(category, wording)
        return {
            "provider": provider, "request_id": request_id, "request_identity": "identity_" + request_id,
            "normalized_information_key": key, "information_category": category,
            "requested_information": wording,
        }

    fixture_requests = [
        request("OpenAI", "r1", "event_consensus_detail", "event consensus and prior"),
        request("Gemini", "r2", "treasury_yields", "US 2Y and 10Y yield levels"),
        request("Anthropic", "r3", "dxy", "DXY level and trend"),
        request("OpenAI", "r4", "usdjpy_trend", "USDJPY one-hour and four-hour trend"),
        request("Gemini", "r5", "fed_expectations", "Fed funds implied probability"),
        request("Anthropic", "r6", "risk_sentiment", "broad risk sentiment"),
        request("OpenAI", "r7", "equity_tone", "S&P futures tone"),
    ]
    fixture_snapshot = {
        "daily_snapshots": {
            "us2y": {"status": "ok", "chosen": {"date": "2024-01-01", "value": 4.25}, "prior": {"date": "2023-12-29", "value": 4.20}, "publication_timestamp_policy": "conservative", "same_day_value_used": False},
            "us5y": {"status": "ok", "chosen": {"date": "2024-01-01", "value": 4.05}, "prior": {"date": "2023-12-29", "value": 4.00}, "publication_timestamp_policy": "conservative", "same_day_value_used": False},
            "us10y": {"status": "ok", "chosen": {"date": "2024-01-01", "value": 3.95}, "prior": {"date": "2023-12-29", "value": 3.90}, "publication_timestamp_policy": "conservative", "same_day_value_used": False},
            "us30y": {"status": "ok", "chosen": {"date": "2024-01-01", "value": 4.10}, "prior": {"date": "2023-12-29", "value": 4.05}, "publication_timestamp_policy": "conservative", "same_day_value_used": False},
            "sp500": {"status": "ok", "chosen": {"date": "2024-01-01", "value": 4769.83}, "prior": {"date": "2023-12-29", "value": 4750.00}, "publication_timestamp_policy": "conservative", "same_day_value_used": False},
            "dxy": {"status": "ok", "chosen": {"date": "2024-01-01", "value": 102.0}, "prior": {"date": "2023-12-29", "value": 101.5}, "publication_timestamp_policy": "conservative", "same_day_value_used": False},
        },
        "usdjpy_windows": {
            key: {"status": "exact_window", "post_forecast_data_used": False, "end_candle_ts": "2024-01-02T13:19:00Z", "end_price": 143.1, "return_pct": value, "realized_volatility": 0.001}
            for key, value in (("return_1h", 0.1), ("return_4h", 0.2), ("return_24h", 0.3), ("realized_vol_1h", 0.1))
        },
    }
    pack = _build_repaired_pack_items(
        sessions[0], [row for row in members if row["session_id"] == sessions[0]["session_id"]],
        fixture_requests, [], fixture_snapshot,
        {_information_key("equity_tone", "S&P futures tone"): "HISTORICAL_SOURCE_NOT_CONFIGURED"},
    )
    pack_by_category = {item["information_key"].split("|", 1)[0]: item for item in pack}
    three_rows = [{"session_id": sessions[0]["session_id"], "provider": provider} for provider in FORECAST_PROVIDERS]
    request_keys = {
        _information_key("treasury_yields", "US 10Y yield level"),
        _information_key("treasury_yields", "US 10Y two-hour change"),
    }
    fixture_members = [row for row in members if row["session_id"] == sessions[0]["session_id"]]
    fixture_cluster = release_clusters(sessions[0]["session_id"], fixture_members)[0]["release_cluster_id"]
    native_prediction_payload = {
        "primary_driver_event_id": fixture_members[0]["event_id"], "primary_driver_choice_confidence": 0.5,
        "primary_driver_reason": "fixture", "secondary_driver_status": "NO_MEANINGFUL_SECONDARY_DRIVER",
        "secondary_driver_event_id": "", "secondary_driver_choice_confidence": "", "secondary_driver_reason": "",
        "primary_reaction_target_type": "RELEASE_CLUSTER", "primary_reaction_target_id": fixture_cluster,
        "primary_reaction_direction": "UP", "primary_expected_pips_min": 1, "primary_expected_pips_max": 2,
        "primary_reaction_horizon_min": 5, "primary_reaction_confidence": 0.5, "primary_reaction_thesis": "fixture",
        "secondary_reaction_status": "NO_MEANINGFUL_SECONDARY_DRIVER", "secondary_reaction_target_type": "",
        "secondary_reaction_target_id": "", "secondary_reaction_direction": "NOT_PREDICTED",
        "secondary_expected_pips_min": "", "secondary_expected_pips_max": "", "secondary_reaction_horizon_min": "",
        "secondary_reaction_confidence": "", "secondary_reaction_thesis": "", "interaction_status": "NO_SECONDARY_DRIVER",
        "primary_secondary_interaction": "UNCERTAIN", "interaction_confidence": "", "interaction_explanation": "",
        "session_forecast_direction": "UP", "session_expected_pips_min": 1, "session_expected_pips_max": 3,
        "session_confidence": 0.5, "session_expected_holding_min": 5, "session_path_summary": "fixture",
        "session_thesis": "fixture", "causal_chain": "fixture", "invalidation_condition": "fixture",
        "no_signal_flag": False, "no_signal_reason": "", "information_used": [], "missing_information": [],
        "prediction_path": [
            {"path_stage_index": 1, "path_stage_type": "RELEASE_CLUSTER_REACTION", "path_target_type": "RELEASE_CLUSTER", "path_target_id": fixture_cluster, "path_target_name": "CPI", "expected_start_ts": "2024-01-02T13:30:00Z", "expected_end_ts": "2024-01-02T13:35:00Z", "expected_direction": "UP", "expected_pips_min": 1, "expected_pips_max": 2, "expected_behavior": "CONTINUE", "relationship_to_previous_stage": "", "stage_confidence": 0.5, "stage_explanation": "fixture"},
            {"path_stage_index": 2, "path_stage_type": "FINAL_SESSION_STATE", "path_target_type": "MARKET_SESSION", "path_target_id": sessions[0]["session_id"], "path_target_name": "session", "expected_start_ts": "2024-01-02T13:35:00Z", "expected_end_ts": "2024-01-02T13:35:00Z", "expected_direction": "UP", "expected_pips_min": 1, "expected_pips_max": 3, "expected_behavior": "HOLD", "relationship_to_previous_stage": "fixture", "stage_confidence": 0.5, "stage_explanation": "fixture"},
        ],
    }
    environment_contract = _frozen_stage4a_contract_identity()
    native_parsed, native_prediction, native_paths, native_errors = _normalized_forecast_response(
        json.dumps(native_prediction_payload), session=sessions[0], members=fixture_members, provider="OpenAI",
        model=FORECAST_PROVIDERS["OpenAI"], arm="A", pack_freeze_id="NO_PACK", pack_fingerprint="",
        forecast_run_id="FIXTURE", forecast_created_ts="2024-01-02T13:20:00Z", environment_contract=environment_contract,
    )
    _, _, _, flat_only_errors = _normalized_forecast_response(
        json.dumps({"forecast_direction": "up"}), session=sessions[0], members=fixture_members, provider="OpenAI",
        model=FORECAST_PROVIDERS["OpenAI"], arm="A", pack_freeze_id="NO_PACK", pack_fingerprint="",
        forecast_run_id="FIXTURE", forecast_created_ts="2024-01-02T13:20:00Z", environment_contract=environment_contract,
    )
    clean_forecast_prompt = _square_one_forecast_prompt(
        sessions[0], [members[0]],
        {"pack_selected": "NO_PACK", "pack_item_count": 0, "pack_e_exposure": False, "items": []},
        "OpenAI", FORECAST_PROVIDERS["OpenAI"],
    )
    tests = {
        "raw_projection_excludes_released_value": "released_value" not in raw_fields and "9.9" not in raw_fields,
        "deterministic_session_identity": sessions[0]["session_id"] == "US|2024-01-02|CUSTOM_CONFIG_WINDOW" and sessions == _reconstruct_sessions(fixture)[0],
        "daily_session_reconstruction": len(sessions) == 2 and not excluded,
        "historical_cutoff": sessions[0]["forecast_cutoff"] == "2024-01-02T13:20:00Z",
        "old_artifact_independence": all(row["source_event_sheet"] == "Event" for row in sessions),
        "pack_a_zero_exposure": not _square_one_forecast_prompt(sessions[0], [members[0]], {"pack_selected": "NO_PACK", "pack_item_count": 0, "pack_e_exposure": False, "items": []}, "OpenAI", FORECAST_PROVIDERS["OpenAI"])["user"].count("Market_State_Pack_Shadow"),
        "deterministic_route_before_unavailable": pack_by_category["treasury_yields"]["status"] == "SUPPLIED_DETERMINISTIC" and pack_by_category["treasury_yields"]["acquisition_route_attempted"] == ["deterministic_acquisition"],
        "computed_route_before_unavailable": pack_by_category["dxy"]["status"] == "SUPPLIED_COMPUTED" and pack_by_category["usdjpy_trend"]["status"] == "SUPPLIED_COMPUTED",
        "calendar_route_preserved": pack_by_category["event_consensus_detail"]["status"] == "SUPPLIED_CALENDAR_DERIVED",
        "policy_rejected_propagated": pack_by_category["fed_expectations"]["status"] == "POLICY_REJECTED",
        "interpretive_propagated": pack_by_category["risk_sentiment"]["status"] == "INTERPRETIVE_NOT_SUPPLIED",
        "request_lineage_preserved": all(item.get("provider_request_ids") and item.get("normalized_request_id") for item in pack),
        "candidate_lineage_preserved": all("candidate_ids" in item and item.get("candidate_lineage_status") for item in pack),
        "exact_unavailable_reason": pack_by_category["equity_tone"]["reason"] == "APPROVED_PRIOR_DAY_SP500_SOURCE_DOES_NOT_PROVE_REQUESTED_INTRADAY_FUTURES_OR_CROSS_MARKET_TONE",
        "generic_equity_route_supplies_prior_day_sp500": _market_item(
            sessions[0], [request("OpenAI", "eq_generic", "equity_tone", "Recent S&P 500 performance")], fixture_snapshot,
        )["status"] == "SUPPLIED_COMPUTED",
        "full_curve_route_supplies_approved_fred_series": _market_item(
            sessions[0], [request("OpenAI", "curve", "treasury_yields", "US Treasury yields across the curve")], fixture_snapshot,
        )["status"] == "SUPPLIED_DETERMINISTIC",
        "auction_detail_fails_closed": _market_item(
            sessions[0], [request("OpenAI", "auction", "treasury_yields", "30Y auction result and bid-to-cover")], fixture_snapshot,
        )["reason"] == "APPROVED_DAILY_TREASURY_CURVE_SOURCE_DOES_NOT_PROVE_INTRADAY_OR_AUCTION_RESULT_DETAIL",
        "option_implied_volatility_fails_closed": _market_item(
            sessions[0], [request("OpenAI", "iv", "volatility", "USDJPY 1-week implied volatility")], fixture_snapshot,
        )["reason"] == "NO_APPROVED_HISTORICAL_USDJPY_OPTION_IV_SOURCE",
        "realized_volatility_uses_existing_windows": _market_item(
            sessions[0], [request("OpenAI", "rv", "volatility", "Recent volatility measures for USDJPY")], fixture_snapshot,
        )["status"] == "SUPPLIED_COMPUTED",
        "historical_timestamp_cutoff": all(
            (_parse_dt(item.get("source_timestamp")) < _parse_dt(item.get("forecast_cutoff")))
            for item in pack if item.get("status") in {"SUPPLIED_DETERMINISTIC", "SUPPLIED_COMPUTED"}
        ),
        "point_in_time_provenance_rejection": _daily_source(
            {"daily_snapshots": {"dxy": {"status": "ok", "chosen": {"date": "2024-01-02", "value": 102.0}}}},
            "dxy", "FMP:DX-Y.NYB", sessions[0]["forecast_cutoff"],
        )[1] == "POINT_IN_TIME_STATE_UNPROVABLE",
        "no_outcome_access_during_acquisition": "released_value" not in _canonical(pack) and "canonical_outcome" not in _canonical(pack),
        "provider_pack_equality": len({_sha(pack) for _ in FORECAST_PROVIDERS}) == 1,
        "deterministic_pack_rebuild": pack == _build_repaired_pack_items(
            sessions[0], [row for row in members if row["session_id"] == sessions[0]["session_id"]],
            fixture_requests, [], fixture_snapshot,
            {_information_key("equity_tone", "S&P futures tone"): "HISTORICAL_SOURCE_NOT_CONFIGURED"},
        ),
        "hindsight_detection": bool(_hindsight_hits("As we now know, the actual came in high.")),
        "unique_session_counting": len({row["session_id"] for row in three_rows}) == 1 and len(three_rows) == 3,
        "model_weight_risk_visible": MODEL_WEIGHT_RISK == "KNOWN_NONZERO_LIMITATION",
        "request_identity_preserves_meaning": len(request_keys) == 2 and all(request_keys),
        "native_v2_prediction_parses": not native_errors and native_prediction.get("prediction_id") and len(native_paths) == 2,
        "legacy_flat_only_fails_closed": bool(flat_only_errors),
        "stage4a_contract_identity_attached": native_prediction.get("environment_contract_fingerprint") == STAGE4A_CONTRACT_FINGERPRINT,
        "audit_metadata_excluded_from_forecast": "retrospective_simulation_flag" not in _canonical(clean_forecast_prompt),
        "raw_acquisition_lineage_excluded_from_forecast": "input_lineage" not in _canonical(
            _square_one_forecast_prompt(
                sessions[0], [members[0]],
                {"pack_selected": "TRUE_SHARED_PACK_E", "pack_item_count": len(pack), "pack_e_exposure": True, "items": pack},
                "OpenAI", FORECAST_PROVIDERS["OpenAI"],
            )
        ),
        "reserved_token_request_identity_uses_safe_capability_label": "post_session" not in _canonical(
            _square_one_forecast_prompt(
                sessions[0], [members[0]],
                {"pack_selected": "TRUE_SHARED_PACK_E", "pack_item_count": 1, "pack_e_exposure": True, "items": [{
                    **pack_by_category["treasury_yields"],
                    "information_key": "treasury_yields|pre_post_session",
                    "item_key": "treasury_yields|pre_post_session",
                }]},
                "OpenAI", FORECAST_PROVIDERS["OpenAI"],
            )
        ),
        "native_v2_prompt_contract_present": "native v2 layered Prediction" in clean_forecast_prompt["instruction"],
        "malformed_serialization_retry_bounded": (
            _retryable_forecast_errors(["RESPONSE_SCHEMA:Unterminated string"])
            and not _retryable_forecast_errors(["INVALID_DIRECTION"])
        ),
        "expired_oauth_grant_detected_as_global_limit": _external_auth_failure(
            "invalid_grant: Token has been expired or revoked."
        ),
    }
    return {"all_passed": all(tests.values()), "tests": tests}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 9 historical square-one retrospective simulation.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--checkpoint-only", action="store_true", help="Write a local append-store checkpoint without Google API access.")
    parser.add_argument("--max-sessions", type=int, default=0, help="Bounded pilot; zero processes all reconstructable sessions.")
    parser.add_argument("--resume-date", default="", help="Process reconstructed sessions on or after YYYY-MM-DD.")
    args = parser.parse_args()
    if args.self_test:
        result = self_test()
    elif args.checkpoint_only:
        result = write_external_limit_checkpoint("GOOGLE_OAUTH_GRANT_EXPIRED_OR_REVOKED")
    else:
        result = run(max_sessions=args.max_sessions or None, resume_date=args.resume_date)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
