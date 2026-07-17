#!/usr/bin/env python3
"""Shadow-only prospective collection contract for mechanism evaluation evidence.

This module does not call providers, write production data, or create outcomes.
It defines and validates the minimum pre-outcome evidence envelope needed to
continue Phase 9A population repair without hindsight selection.
"""

from __future__ import annotations

import hashlib
import json
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

import fcntl


SCHEMA_VERSION = "presignal_phase9a_mechanism_population_shadow_collection_v0"
COLLECTION_MODE = "SHADOW_ONLY_PREOUTCOME"
HISTORICAL_REPLAY_COLLECTION_MODE = "HISTORICAL_ASOF_REPLAY"
SUPPORTED_COLLECTION_MODES = {COLLECTION_MODE, HISTORICAL_REPLAY_COLLECTION_MODE}
ARCHITECTURE_VERSION = "2.0"
COLLECTOR_VERSION = "phase9a_prospective_mechanism_evidence_collector_v1"
COLLECTION_CONTRACT_VERSION = "1.0"
MECHANISM_DEFINITION_VERSION = "1.1"
PRIMARY_CLASSIFICATION_AUTHORITY_VERSION = "1.1"
PRIMARY_CLASSIFICATION_AUTHORITY_RUN_ID = "refined_mechanism_v11_classification_20260710T152725Z"
CANONICAL_OUTCOME_CONTRACT_VERSION = "1.0-clean-r1"
SUCCESS_MAPPING_CONTRACT_VERSION = "1.0-clean-r1"
FROZEN_OUTCOME_WINDOW_MINUTES = 5
ACTIVE_COLLECTION_ROOT = (
    Path(__file__).resolve().parents[1]
    / "outputs"
    / "phase9a_prospective_mechanism_collection"
    / "active_v1"
)

REQUIRED_PREOUTCOME_FIELDS = [
    "collection_run_id",
    "collection_contract_version",
    "collector_version",
    "collection_mode",
    "mechanism_definition_version",
    "primary_classification_authority_version",
    "primary_classification_authority_run_id",
    "classification_authority_status",
    "session_id",
    "session_date",
    "session_start_timestamp",
    "session_window",
    "provider",
    "model",
    "provider_run_id",
    "forecast_identity",
    "forecast_id",
    "forecast_timestamp",
    "capture_timestamp",
    "forecast_source_row_key",
    "pack_level",
    "cluster_id",
    "raw_provider_output_reference",
    "primary_mechanism_classification",
    "mechanism_input_reference",
    "mechanism_input_fields",
    "arm_relevant_pre_outcome_fields",
    "mechanism_classification_pending",
    "preoutcome_representation_inputs",
    "representation_input_fields",
    "exact_linkage_key_provider",
    "exact_linkage_key_session_id",
    "exact_linkage_key_pack_level",
    "exact_linkage_key_source_row_key",
    "canonical_outcome_source_requirement",
    "outcome_window_policy",
    "outcome_window_minutes",
    "canonical_outcome_definition_version",
    "planned_outcome_window_start",
    "planned_outcome_window_end",
    "source_availability_requirement",
    "as_of_timestamp_requirement",
    "success_mapping_input_contract",
    "provider_session_cluster_key",
    "future_exact_linkage_key_fields",
    "source_lineage",
    "stable_observation_key",
    "scientific_observation_key",
    "collection_status",
    "created_timestamp",
    "shadow_only",
    "production_visible",
]

PROHIBITED_COLLECTION_FIELDS = [
    "realized_direction",
    "correctness",
    "overall_ok",
    "provider_performance",
    "accuracy_result",
    "post_session_explanation",
]


class ShadowCollectionError(RuntimeError):
    """Raised when a prospective shadow record is not safe to collect."""


def _norm(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return str(value).strip()


def _upper(value: Any) -> str:
    return _norm(value).upper()


def _is_true(value: Any) -> bool:
    return _norm(value).upper() in {"TRUE", "1", "YES", "Y"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _parse_iso(value: Any) -> datetime | None:
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


def _as_iso(value: Any) -> str:
    parsed = _parse_iso(value)
    if parsed is None:
        return ""
    return parsed.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_key(*parts: Any) -> str:
    return "|".join(_norm(part) for part in parts)


def _record_paths(output_root: Path) -> Dict[str, Path]:
    return {
        "activation": output_root / "activation_manifest.json",
        "records": output_root / "preoutcome_records.jsonl",
        "attempts": output_root / "collection_attempts.jsonl",
        "status": output_root / "collection_status.json",
        "lock": output_root / ".collection.lock",
    }


@contextmanager
def _locked_collection_store(output_root: Path):
    output_root.mkdir(parents=True, exist_ok=True)
    lock_path = _record_paths(output_root)["lock"]
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ShadowCollectionError(f"MALFORMED_COLLECTION_STORE:{path.name}:line={index}") from exc
        if not isinstance(parsed, dict):
            raise ShadowCollectionError(f"INVALID_COLLECTION_STORE_RECORD:{path.name}:line={index}")
        rows.append(parsed)
    return rows


def _append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(_canonical_json(dict(payload)) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(_canonical_json(dict(payload)) + "\n", encoding="utf-8")
    os.replace(temp_path, path)


def validate_preoutcome_shadow_record(record: Mapping[str, Any]) -> Dict[str, Any]:
    """Validate a future pre-outcome collection row without using truthiness.

    Missing/null/blank fields fail closed. Outcome-bearing or performance fields
    are prohibited at collection time.
    """

    missing = [field for field in REQUIRED_PREOUTCOME_FIELDS if _norm(record.get(field)) == ""]
    prohibited_present = [
        field
        for field in PROHIBITED_COLLECTION_FIELDS
        if field in record and _norm(record.get(field)) != ""
    ]
    errors: List[str] = []
    if missing:
        errors.append(f"MISSING_REQUIRED_FIELDS:{','.join(missing)}")
    if prohibited_present:
        errors.append(f"PROHIBITED_OUTCOME_OR_PERFORMANCE_FIELDS:{','.join(prohibited_present)}")
    collection_mode = _norm(record.get("collection_mode"))
    if collection_mode not in SUPPORTED_COLLECTION_MODES:
        errors.append("INVALID_COLLECTION_MODE")
    if not _is_true(record.get("shadow_only")):
        errors.append("SHADOW_ONLY_REQUIRED")
    if _is_true(record.get("production_visible")):
        errors.append("PRODUCTION_VISIBLE_FORBIDDEN")
    exact_key = (
        _norm(record.get("exact_linkage_key_provider")),
        _norm(record.get("exact_linkage_key_session_id")),
        _norm(record.get("exact_linkage_key_pack_level")),
        _norm(record.get("exact_linkage_key_source_row_key")),
    )
    forecast_key = (
        _norm(record.get("provider")),
        _norm(record.get("session_id")),
        _norm(record.get("pack_level")),
        _norm(record.get("forecast_source_row_key")),
    )
    if exact_key != forecast_key:
        errors.append("EXACT_LINKAGE_KEY_MISMATCH")
    if _upper(record.get("mechanism_classification_pending")) != "TRUE":
        errors.append("FROZEN_CLASSIFICATION_PENDING_REQUIRED")
    if _upper(record.get("shadow_only")) != "TRUE":
        errors.append("SHADOW_ONLY_REQUIRED")
    if _upper(record.get("production_visible")) != "FALSE":
        errors.append("PRODUCTION_VISIBLE_FORBIDDEN")
    forecast_ts = _parse_iso(record.get("forecast_timestamp"))
    capture_ts = _parse_iso(record.get("capture_timestamp"))
    window_start = _parse_iso(record.get("planned_outcome_window_start"))
    if forecast_ts is None or capture_ts is None or window_start is None:
        errors.append("INVALID_PREOUTCOME_TIMESTAMP")
    else:
        if forecast_ts >= window_start or capture_ts >= window_start:
            errors.append("FORECAST_OR_CAPTURE_NOT_PREOUTCOME")
    if collection_mode == HISTORICAL_REPLAY_COLLECTION_MODE:
        simulated_asof = _parse_iso(record.get("simulated_as_of_timestamp"))
        historical_session = _parse_iso(record.get("historical_session_timestamp"))
        replay_executed = _parse_iso(record.get("replay_executed_timestamp"))
        if not _norm(record.get("historical_replay_run_id")):
            errors.append("HISTORICAL_REPLAY_RUN_ID_REQUIRED")
        if simulated_asof is None or historical_session is None or replay_executed is None:
            errors.append("INVALID_HISTORICAL_REPLAY_TIMESTAMP")
        elif forecast_ts is not None and simulated_asof != forecast_ts:
            errors.append("HISTORICAL_REPLAY_ASOF_MISMATCH")
        if _upper(record.get("outcome_hidden_at_capture")) != "TRUE":
            errors.append("OUTCOME_HIDDEN_AT_CAPTURE_REQUIRED")
    if _upper(record.get("forecast_output_valid")) != "TRUE":
        errors.append("INVALID_FORECAST_OUTPUT")
    if _norm(record.get("_prohibited_source_fields")):
        errors.append(f"PROHIBITED_OUTCOME_OR_PERFORMANCE_SOURCE_FIELDS:{_norm(record.get('_prohibited_source_fields'))}")
    return {
        "record_status": "VALID_PREOUTCOME_SHADOW_RECORD" if not errors else "BLOCKED_PREOUTCOME_SHADOW_RECORD",
        "errors": errors,
        "fail_closed": bool(errors),
    }


def build_tier2_preoutcome_record(
    *,
    collection_run_id: str,
    session_meta: Mapping[str, Any],
    forecast_row: Mapping[str, Any],
    behavior_row: Mapping[str, Any],
    raw_provider_output_reference: str,
    capture_timestamp: str,
    collection_mode: str = COLLECTION_MODE,
    historical_replay_run_id: str = "",
    simulated_as_of_timestamp: str = "",
    replay_executed_timestamp: str = "",
    source_execution: str = "automation/build_pack_behavior_tier2_execution_v0.py",
) -> Dict[str, Any]:
    """Build a frozen-rule, pre-outcome evidence envelope from one Tier 2 call.

    The classification is deliberately pending. This collector preserves only the
    inputs required to apply the frozen v1.1 mechanism rules later; it cannot
    assign an arm or consume an outcome.
    """

    provider = _norm(forecast_row.get("provider"))
    session_id = _norm(forecast_row.get("session_id"))
    pack_level = _norm(forecast_row.get("pack_level"))
    source_row_key = _stable_key(session_id, provider, pack_level)
    forecast_id = _norm(raw_provider_output_reference)
    provider_run_id = _norm(forecast_row.get("execution_run_id")) or _norm(collection_run_id)
    collection_mode = _norm(collection_mode)
    scientific_key_parts = [
        "MECH_INFORMATION_CONSISTENCY",
        MECHANISM_DEFINITION_VERSION,
        PRIMARY_CLASSIFICATION_AUTHORITY_VERSION,
        provider,
        session_id,
        pack_level,
    ]
    # Replay and live records are deliberately separate scientific stores.
    if collection_mode == HISTORICAL_REPLAY_COLLECTION_MODE:
        scientific_key_parts.append(collection_mode)
    scientific_observation_key = _stable_key(*scientific_key_parts)
    stable_observation_key = _stable_key(scientific_observation_key, provider_run_id, forecast_id)
    effective_capture_timestamp = (
        simulated_as_of_timestamp
        if collection_mode == HISTORICAL_REPLAY_COLLECTION_MODE
        else capture_timestamp
    )
    forecast_timestamp = _as_iso(effective_capture_timestamp)
    session_start = _as_iso(session_meta.get("session_start_ts"))
    planned_window_start = _as_iso(session_meta.get("primary_release_ts"))
    planned_window_start_dt = _parse_iso(planned_window_start)
    planned_window_end = (
        planned_window_start_dt + timedelta(minutes=FROZEN_OUTCOME_WINDOW_MINUTES)
        if planned_window_start_dt is not None
        else None
    )
    planned_window_end = _as_iso(planned_window_end)
    mechanism_inputs = {
        "forecast_direction": _norm(forecast_row.get("forecast_direction")),
        "forecast_confidence": _norm(forecast_row.get("forecast_confidence")),
        "no_signal_flag": _norm(behavior_row.get("no_signal_flag")),
        "no_signal_reason": _norm(behavior_row.get("no_signal_reason")),
        "output_valid": _norm(behavior_row.get("output_valid")),
        "primary_driver_summary": _norm(behavior_row.get("primary_driver_summary")),
        "secondary_driver_summary": _norm(behavior_row.get("secondary_driver_summary")),
        "information_used": _norm(behavior_row.get("information_used")),
        "information_not_used": _norm(behavior_row.get("information_not_used")),
        "pack_fields_used": _norm(behavior_row.get("pack_fields_used")),
        "pack_fields_discarded": _norm(behavior_row.get("pack_fields_discarded")),
        "uncertainty_sources": _norm(behavior_row.get("uncertainty_sources")),
        "missing_information": _norm(behavior_row.get("missing_information")),
    }
    representation_inputs = {
        "forecast_direction": _norm(forecast_row.get("forecast_direction")),
        "no_signal_flag": _norm(behavior_row.get("no_signal_flag")),
        "forecast_output_valid": _norm(behavior_row.get("output_valid")),
        "representation_semantics": "FROZEN_SUCCESS_MAPPING_V1_UNCHANGED",
    }
    exact_linkage = {
        "provider": provider,
        "session_id": session_id,
        "pack_level": pack_level,
        "source_row_key": source_row_key,
    }
    source_lineage = {
        "source_execution": _norm(source_execution),
        "execution_run_id": provider_run_id,
        "forecast_sheet": "Pack_Behavior_Tier2_Forecasts",
        "behavior_sheet": "Pack_Behavior_Tier2_Behavior",
        "raw_archive_sheet": "Pack_Behavior_Tier2_Raw_Response_Archive",
        "raw_provider_output_reference": forecast_id,
    }
    prohibited_source_fields = sorted(
        {
            field
            for source in (forecast_row, behavior_row, session_meta)
            for field in PROHIBITED_COLLECTION_FIELDS
            if field in source and _norm(source.get(field)) != ""
        }
    )
    return {
        "collection_run_id": _norm(collection_run_id),
        "collection_contract_version": COLLECTION_CONTRACT_VERSION,
        "collector_version": COLLECTOR_VERSION,
        "collection_mode": collection_mode,
        "mechanism_definition_version": MECHANISM_DEFINITION_VERSION,
        "primary_classification_authority_version": PRIMARY_CLASSIFICATION_AUTHORITY_VERSION,
        "primary_classification_authority_run_id": PRIMARY_CLASSIFICATION_AUTHORITY_RUN_ID,
        "classification_authority_status": "PENDING_FROZEN_RULE_APPLICATION_FOR_FUTURE_OBSERVATION",
        "session_id": session_id,
        "session_date": _norm(forecast_row.get("session_date")) or _norm(session_meta.get("session_date")),
        "session_start_timestamp": session_start,
        "session_window": _norm(forecast_row.get("session_window_name")) or _norm(session_meta.get("session_window_name")),
        "provider": provider,
        "model": _norm(forecast_row.get("model")),
        "provider_run_id": provider_run_id,
        "forecast_identity": forecast_id,
        "forecast_id": forecast_id,
        "forecast_timestamp": forecast_timestamp,
        "capture_timestamp": forecast_timestamp,
        "forecast_source_row_key": source_row_key,
        "pack_level": pack_level,
        "cluster_id": _stable_key(provider, session_id),
        "raw_provider_output_reference": forecast_id,
        "primary_mechanism_classification": "PENDING_FROZEN_V11_CLASSIFICATION",
        "mechanism_input_reference": _sha256(mechanism_inputs),
        "mechanism_input_fields": _canonical_json(mechanism_inputs),
        "arm_relevant_pre_outcome_fields": _canonical_json(mechanism_inputs),
        "mechanism_classification_pending": "TRUE",
        "preoutcome_representation_inputs": _canonical_json(representation_inputs),
        "representation_input_fields": _canonical_json(representation_inputs),
        "exact_linkage_key_provider": provider,
        "exact_linkage_key_session_id": session_id,
        "exact_linkage_key_pack_level": pack_level,
        "exact_linkage_key_source_row_key": source_row_key,
        "canonical_outcome_source_requirement": "FROZEN_CANONICAL_OUTCOME_CONTRACT_REQUIRED",
        "outcome_window_policy": "FROZEN_CANONICAL_MARKET_REACTION_WINDOW",
        "outcome_window_minutes": str(FROZEN_OUTCOME_WINDOW_MINUTES),
        "canonical_outcome_definition_version": CANONICAL_OUTCOME_CONTRACT_VERSION,
        "planned_outcome_window_start": planned_window_start,
        "planned_outcome_window_end": planned_window_end,
        "source_availability_requirement": "FROZEN_CANONICAL_SOURCE_AVAILABILITY_REQUIRED",
        "as_of_timestamp_requirement": "FROZEN_CANONICAL_AS_OF_TIMESTAMP_REQUIRED",
        "success_mapping_input_contract": SUCCESS_MAPPING_CONTRACT_VERSION,
        "provider_session_cluster_key": _stable_key(provider, session_id),
        "future_exact_linkage_key_fields": _canonical_json(exact_linkage),
        "source_lineage": _canonical_json(source_lineage),
        "stable_observation_key": stable_observation_key,
        "scientific_observation_key": scientific_observation_key,
        "collection_status": "VALID_PREOUTCOME_SHADOW_RECORD",
        "failure_code": "",
        "created_timestamp": _now_iso() if collection_mode == HISTORICAL_REPLAY_COLLECTION_MODE else forecast_timestamp,
        "forecast_output_valid": _norm(behavior_row.get("output_valid")),
        "_prohibited_source_fields": "|".join(prohibited_source_fields),
        "shadow_only": "TRUE",
        "production_visible": "FALSE",
        "historical_replay_run_id": _norm(historical_replay_run_id),
        "simulated_as_of_timestamp": forecast_timestamp if collection_mode == HISTORICAL_REPLAY_COLLECTION_MODE else "",
        "historical_session_timestamp": planned_window_start if collection_mode == HISTORICAL_REPLAY_COLLECTION_MODE else "",
        "replay_executed_timestamp": _as_iso(replay_executed_timestamp) if collection_mode == HISTORICAL_REPLAY_COLLECTION_MODE else "",
        "outcome_hidden_at_capture": "TRUE" if collection_mode == HISTORICAL_REPLAY_COLLECTION_MODE else "",
    }


def activate_prospective_shadow_collection(
    *,
    output_root: Path = ACTIVE_COLLECTION_ROOT,
    contract_path: str,
    integration_entry_point: str,
    enabled_providers: Sequence[str],
    eligible_session_rule: str,
    activation_run_id: str,
    collection_mode: str = COLLECTION_MODE,
) -> Dict[str, Any]:
    """Enable the durable local shadow store without creating an observation."""

    if _norm(collection_mode) not in SUPPORTED_COLLECTION_MODES:
        raise ShadowCollectionError("INVALID_COLLECTION_MODE")
    with _locked_collection_store(output_root):
        paths = _record_paths(output_root)
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "collector_version": COLLECTOR_VERSION,
            "collection_mode": _norm(collection_mode),
            "collection_contract_version": COLLECTION_CONTRACT_VERSION,
            "collector_status": "ACTIVE_SHADOW_ONLY",
            "activation_run_id": _norm(activation_run_id),
            "activation_timestamp": _now_iso(),
            "contract_path": _norm(contract_path),
            "integration_entry_point": _norm(integration_entry_point),
            "enabled_providers": sorted({_norm(provider) for provider in enabled_providers if _norm(provider)}),
            "eligible_session_rule": _norm(eligible_session_rule),
            "production_authority": False,
            "consumer_switch": False,
            "outcome_access_at_collection": False,
            "stable_identity_rule": (
                "scientific_observation_key=mechanism/version/provider/session/pack; "
                "stable_observation_key=scientific_observation_key/provider_run_id/forecast_id"
            ),
            "duplicate_policy": "Suppress duplicate scientific_observation_key; provider retries never create a second observation.",
        }
        _atomic_json(paths["activation"], manifest)
        records = _read_jsonl(paths["records"])
        attempts = _read_jsonl(paths["attempts"])
        _atomic_json(
            paths["status"],
            {
                **manifest,
                "successful_preoutcome_records": len(records),
                "failed_collection_attempts": sum(1 for row in attempts if row.get("collection_status") == "BLOCKED"),
                "duplicate_attempts_suppressed": sum(1 for row in attempts if row.get("collection_status") == "DUPLICATE_SUPPRESSED"),
                "last_successful_collection": _norm(records[-1].get("created_timestamp")) if records else "",
                "last_failure": _norm(attempts[-1].get("failure_code")) if attempts else "",
            },
        )
    return manifest


def collect_tier2_preoutcome_record(
    *,
    collection_run_id: str,
    session_meta: Mapping[str, Any],
    forecast_row: Mapping[str, Any],
    behavior_row: Mapping[str, Any],
    raw_provider_output_reference: str,
    capture_timestamp: str,
    output_root: Path = ACTIVE_COLLECTION_ROOT,
    collection_mode: str = COLLECTION_MODE,
    historical_replay_run_id: str = "",
    simulated_as_of_timestamp: str = "",
    replay_executed_timestamp: str = "",
    source_execution: str = "automation/build_pack_behavior_tier2_execution_v0.py",
) -> Dict[str, Any]:
    """Persist one valid Tier 2 prospective observation or a failed attempt.

    Only a valid, time-safe record enters the scientific store. Invalid, late,
    outcome-bearing, or duplicate attempts are auditable but never observational
    evidence.
    """

    record = build_tier2_preoutcome_record(
        collection_run_id=collection_run_id,
        session_meta=session_meta,
        forecast_row=forecast_row,
        behavior_row=behavior_row,
        raw_provider_output_reference=raw_provider_output_reference,
        capture_timestamp=capture_timestamp,
        collection_mode=collection_mode,
        historical_replay_run_id=historical_replay_run_id,
        simulated_as_of_timestamp=simulated_as_of_timestamp,
        replay_executed_timestamp=replay_executed_timestamp,
        source_execution=source_execution,
    )
    validation = validate_preoutcome_shadow_record(record)
    with _locked_collection_store(output_root):
        paths = _record_paths(output_root)
        if not paths["activation"].exists():
            raise ShadowCollectionError("COLLECTOR_NOT_ACTIVATED")
        records = _read_jsonl(paths["records"])
        attempts = _read_jsonl(paths["attempts"])
        existing_scientific_keys = {_norm(item.get("scientific_observation_key")) for item in records}
        attempt = {
            "attempt_timestamp": _now_iso(),
            "collector_version": COLLECTOR_VERSION,
            "collection_run_id": _norm(collection_run_id),
            "stable_observation_key": _norm(record.get("stable_observation_key")),
            "scientific_observation_key": _norm(record.get("scientific_observation_key")),
            "provider": _norm(record.get("provider")),
            "session_id": _norm(record.get("session_id")),
            "pack_level": _norm(record.get("pack_level")),
            "production_visible": "FALSE",
        }
        if validation["fail_closed"]:
            attempt.update(
                {
                    "collection_status": "BLOCKED",
                    "failure_code": "|".join(validation["errors"]),
                    "scientifically_valid": "FALSE",
                }
            )
            _append_jsonl(paths["attempts"], attempt)
            _refresh_status(paths, records, attempts + [attempt])
            return {**attempt, "record_written": False}
        if _norm(record.get("scientific_observation_key")) in existing_scientific_keys:
            attempt.update(
                {
                    "collection_status": "DUPLICATE_SUPPRESSED",
                    "failure_code": "DUPLICATE_SCIENTIFIC_OBSERVATION_KEY",
                    "scientifically_valid": "FALSE",
                }
            )
            _append_jsonl(paths["attempts"], attempt)
            _refresh_status(paths, records, attempts + [attempt])
            return {**attempt, "record_written": False}
        _append_jsonl(paths["records"], record)
        attempt.update(
            {
                "collection_status": "COLLECTED",
                "failure_code": "",
                "scientifically_valid": "TRUE",
            }
        )
        _append_jsonl(paths["attempts"], attempt)
        _refresh_status(paths, records + [record], attempts + [attempt])
        return {**attempt, "record_written": True, "record": record}


def _refresh_status(paths: Mapping[str, Path], records: Sequence[Mapping[str, Any]], attempts: Sequence[Mapping[str, Any]]) -> None:
    if not paths["activation"].exists():
        return
    manifest = json.loads(paths["activation"].read_text(encoding="utf-8"))
    _atomic_json(
        paths["status"],
        {
            **manifest,
            "successful_preoutcome_records": len(records),
            "failed_collection_attempts": sum(1 for row in attempts if _norm(row.get("collection_status")) == "BLOCKED"),
            "duplicate_attempts_suppressed": sum(
                1 for row in attempts if _norm(row.get("collection_status")) == "DUPLICATE_SUPPRESSED"
            ),
            "last_successful_collection": _norm(records[-1].get("created_timestamp")) if records else "",
            "last_failure": _norm(attempts[-1].get("failure_code")) if attempts else "",
        },
    )


def build_collection_contract(
    *,
    output_dir: Path,
    repair_run_id: str,
    final_counts: Mapping[str, Any],
    remaining_evidence_needed: Mapping[str, Any],
    enabled_providers: Sequence[str],
    required_session_policy: str,
) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    contract = {
        "schema_version": SCHEMA_VERSION,
        "generated_ts": _now_iso(),
        "repair_run_id": repair_run_id,
        "architecture_version": ARCHITECTURE_VERSION,
        "collection_mode": COLLECTION_MODE,
        "collector_status": "ACTIVE_SHADOW_CONTRACT_CREATED",
        "production_authority": False,
        "consumer_switch": False,
        "provider_calls_performed": 0,
        "mechanism_tests_performed": 0,
        "required_preoutcome_fields": REQUIRED_PREOUTCOME_FIELDS,
        "prohibited_collection_fields": PROHIBITED_COLLECTION_FIELDS,
        "enabled_providers": sorted(enabled_providers),
        "required_session_policy": required_session_policy,
        "final_counts_at_activation": dict(final_counts),
        "remaining_evidence_needed": dict(remaining_evidence_needed),
        "selection_rule": (
            "Collect every eligible future shadow provider/session/pack observation before outcome availability; "
            "do not select based on realized outcome, provider performance, or post-session evidence."
        ),
        "exact_linkage_contract": "provider + session_id + pack_level + source_row_key",
        "canonical_outcome_requirement": (
            "Frozen market-reaction window, version, timestamp provenance, repaired-overlay lineage, "
            "and source/as-of timestamp requirements must pass before downstream use."
        ),
        "success_mapping_boundary": "Success Mapping v1 remains frozen; collector records inputs only.",
        "fail_closed_conditions": [
            "missing_required_identity",
            "missing_forecast_timestamp",
            "outcome_or_performance_field_present_at_collection",
            "production_visible_record",
            "exact_linkage_key_mismatch",
            "manual_or_fuzzy_join_requested",
        ],
    }
    contract_path = output_dir / "prospective_shadow_collection_contract.json"
    contract_path.write_text(_canonical_json(contract) + "\n", encoding="utf-8")

    queue_template = output_dir / "prospective_shadow_collection_queue_template.csv"
    queue_template.write_text(",".join(REQUIRED_PREOUTCOME_FIELDS) + "\n", encoding="utf-8")

    self_test_record = {field: f"TEST_{field}" for field in REQUIRED_PREOUTCOME_FIELDS}
    self_test_record.update(
        {
            "collection_run_id": repair_run_id,
            "collection_mode": COLLECTION_MODE,
            "provider": "TEST_PROVIDER",
            "session_id": "TEST_SESSION",
            "pack_level": "B",
            "forecast_source_row_key": "TEST_SESSION|TEST_PROVIDER|B",
            "exact_linkage_key_provider": "TEST_PROVIDER",
            "exact_linkage_key_session_id": "TEST_SESSION",
            "exact_linkage_key_pack_level": "B",
            "exact_linkage_key_source_row_key": "TEST_SESSION|TEST_PROVIDER|B",
            "session_start_timestamp": "2030-01-01T00:00:00Z",
            "forecast_timestamp": "2030-01-01T00:05:00Z",
            "capture_timestamp": "2030-01-01T00:05:00Z",
            "planned_outcome_window_start": "2030-01-01T01:00:00Z",
            "planned_outcome_window_end": "2030-01-01T01:05:00Z",
            "mechanism_classification_pending": "TRUE",
            "forecast_output_valid": "TRUE",
            "collection_status": "VALID_PREOUTCOME_SHADOW_RECORD",
            "shadow_only": "TRUE",
            "production_visible": "FALSE",
        }
    )
    valid_test = validate_preoutcome_shadow_record(self_test_record)
    invalid_test = validate_preoutcome_shadow_record({"collection_mode": COLLECTION_MODE})
    tests = {
        "valid_record_test": valid_test,
        "missing_record_test": invalid_test,
        "tests_passed": (
            valid_test["record_status"] == "VALID_PREOUTCOME_SHADOW_RECORD"
            and invalid_test["record_status"] == "BLOCKED_PREOUTCOME_SHADOW_RECORD"
        ),
    }
    (output_dir / "prospective_shadow_collection_self_test.json").write_text(
        _canonical_json(tests) + "\n",
        encoding="utf-8",
    )
    if not tests["tests_passed"]:
        raise ShadowCollectionError("Prospective shadow collector self-test failed.")
    return {
        "contract_path": str(contract_path),
        "queue_template_path": str(queue_template),
        "self_test_path": str(output_dir / "prospective_shadow_collection_self_test.json"),
        "collector_status": contract["collector_status"],
        "self_tests_passed": tests["tests_passed"],
    }


def main() -> None:
    out = Path("outputs") / "phase9a_evaluation_population_repair" / "collector_self_test"
    result = build_collection_contract(
        output_dir=out,
        repair_run_id="COLLECTOR_SELF_TEST",
        final_counts={"positive": 0, "negative": 0, "total": 0},
        remaining_evidence_needed={"positive": 40, "negative": 12, "sessions": 4, "providers": 2, "clusters": 12},
        enabled_providers=["Anthropic", "Gemini", "OpenAI"],
        required_session_policy="future_preoutcome_shadow_sessions_only",
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
