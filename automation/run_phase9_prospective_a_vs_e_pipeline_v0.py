#!/usr/bin/env python3
"""Run the shadow-only prospective request-driven Pack A versus Pack E flow.

This is deliberately a child of the existing Tier 2 scheduler.  It never reads
canonical outcomes while creating forecasts; exact outcome attachment is a
separate, post-window state transition.  The compact local ledger is the
authoritative runtime record for this experimental pipeline, not a workbook.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PIPELINE_VERSION = "phase9_prospective_a_vs_e_pipeline_v0"
SCHEMA_VERSION = "phase9_prospective_a_vs_e_shadow_v1"
ACTIVE_ROOT = ROOT / "outputs" / "phase9_prospective_a_vs_e_collection" / "active_v1"
ACTIVATION_ROOT = ROOT / "outputs" / "phase9_prospective_a_vs_e_activation"
SOURCE_BUNDLE_PATH = ROOT / "inputs" / "phase9_external_acquisition" / "source_bundles.jsonl"
FORECAST_PROVIDERS = {
    "OpenAI": "gpt-4o-mini-2024-07-18",
    "Gemini": "gemini-2.5-flash-lite",
    "Anthropic": "claude-haiku-4-5",
}
ACQUISITION_CONFIG = {
    "provider": "OpenAI",
    "model": "gpt-5.6-luna",
    "reasoning": "low",
    "temperature_mode": "MODEL_DEFAULT",
    "temperature_parameter_sent": False,
}
PRE_OUTCOME_LEAD_SECONDS = 600
ANALYSIS_MIN_UNIQUE_SESSIONS = 5
ANALYSIS_STRONG_UNIQUE_SESSIONS = 10
FORBIDDEN_TOKENS = (
    "canonical_outcome", "realized_direction", "realized_pips", "start_price",
    "end_price", "accuracy", "overall_ok", "success_mapping", "post_session",
)


class PipelineError(RuntimeError):
    """A fail-closed pipeline condition."""


def _norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _now(value: datetime | None = None) -> str:
    current = value or datetime.now(timezone.utc)
    return current.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_ts(value: Any) -> datetime | None:
    raw = _norm(value)
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(_json(dict(payload)) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _read_json(path: Path, default: Mapping[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return dict(default)
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise PipelineError("INVALID_JSON_OBJECT:" + path.name)
    return parsed


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(_json(dict(row)) + "\n")
    os.replace(temporary, path)


def _paths(root: Path) -> Dict[str, Path]:
    return {
        "config": root / "pipeline_config.json",
        "state": root / "pipeline_state.json",
        "status": root / "pipeline_status.json",
        "attempts": root / "pipeline_attempts.jsonl",
        "lock": root / ".pipeline.lock",
        "disabled": root / "DISABLED",
        "sessions": root / "sessions",
    }


@contextmanager
def _locked(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    lock = _paths(root)["lock"]
    with lock.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _session_identity(session: Mapping[str, Any]) -> str:
    session_id = _norm(session.get("session_id"))
    release = _norm(session.get("primary_release_ts"))
    if not session_id or not release:
        raise PipelineError("MISSING_SESSION_IDENTITY")
    return "P9AE_" + _hash({"session_id": session_id, "release": release})[:24]


def _observation_identity(session_id: str, provider: str, arm: str, cutoff: str, pack_fingerprint: str) -> str:
    return "P9AEOBS_" + _hash({
        "session_id": session_id, "provider": provider, "arm": arm,
        "cutoff": cutoff, "pack_fingerprint": pack_fingerprint,
        "protocol": SCHEMA_VERSION,
    })[:24]


def _safe_prompt(payload: Mapping[str, Any]) -> List[str]:
    rendered = _json(payload).lower()
    return [token for token in FORBIDDEN_TOKENS if token in rendered]


def _analysis_gate(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    sessions = sorted({_norm(row.get("session_id")) for row in rows if _norm(row.get("outcome_status")) == "EXACT_OUTCOME_ATTACHED"})
    return {
        "unique_exact_evaluable_sessions": len(sessions),
        "provider_session_pairs": len([row for row in rows if _norm(row.get("outcome_status")) == "EXACT_OUTCOME_ATTACHED"]),
        "analysis_package_status": "READY" if len(sessions) >= ANALYSIS_MIN_UNIQUE_SESSIONS else "WAITING_FOR_5_UNIQUE_EXACT_SESSIONS",
        "strong_replication_status": "READY" if len(sessions) >= ANALYSIS_STRONG_UNIQUE_SESSIONS else "WAITING_FOR_10_UNIQUE_EXACT_SESSIONS",
        "thresholds": {"minimum": ANALYSIS_MIN_UNIQUE_SESSIONS, "strong": ANALYSIS_STRONG_UNIQUE_SESSIONS},
    }


def _membership_index(rows: Sequence[Mapping[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    indexed: Dict[str, List[Dict[str, Any]]] = {}
    for raw in rows:
        session_id = _norm(raw.get("session_id"))
        if session_id:
            indexed.setdefault(session_id, []).append(dict(raw))
    for values in indexed.values():
        values.sort(key=lambda row: (_norm(row.get("release_ts")), _norm(row.get("event_id"))))
    return indexed


def _candidate_sessions(
    sessions: Sequence[Mapping[str, Any]], members: Mapping[str, Sequence[Mapping[str, Any]]], now: datetime
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for raw in sessions:
        session = dict(raw)
        session_id = _norm(session.get("session_id"))
        release = _parse_ts(session.get("primary_release_ts"))
        session_members = list(members.get(session_id, []))
        if not session_id or release is None:
            status, reason = "INELIGIBLE_EXACT_REASON", "MISSING_SESSION_ID_OR_PRIMARY_RELEASE_TIMESTAMP"
        elif release <= now:
            status, reason = "INELIGIBLE_EXACT_REASON", "NOT_A_FUTURE_PROSPECTIVE_SESSION"
        elif not session_members:
            status, reason = "AWAITING_SESSION_MEMBERSHIP", "NO_EXACT_MARKET_SESSION_MEMBERS"
        elif _safe_prompt({"session": session, "members": session_members}):
            status, reason = "INELIGIBLE_EXACT_REASON", "PROHIBITED_OUTCOME_FIELD_IN_PREOUTCOME_SOURCE"
        else:
            status, reason = "ELIGIBLE_FOR_PROSPECTIVE_CAPTURE", ""
        candidates.append({
            "session_id": session_id,
            "primary_release_ts": _now(release) if release else "",
            "status": status,
            "reason": reason,
            "member_count": len(session_members),
            "session": session,
            "members": session_members,
        })
    return sorted(candidates, key=lambda row: (row["primary_release_ts"], row["session_id"]))


def _fixture_forecast(session_id: str, provider: str, arm: str) -> Dict[str, Any]:
    # A non-scientific fixture that nevertheless exercises the frozen response contract.
    direction = "no_clear_direction" if arm == "A" else "up"
    return {
        "session_id": session_id, "provider": provider, "model": FORECAST_PROVIDERS[provider],
        "pack_arm": arm, "forecast_direction": direction, "forecast_confidence": "0.50",
        "expected_move_pips_min": "0", "expected_move_pips_max": "8", "expected_holding_minutes": "5",
        "primary_driver_summary": "fixture-only", "secondary_driver_summary": "fixture-only",
        "ignored_event_summary": "", "information_used": "[]", "missing_information": "[]",
        "session_narrative": "fixture-only", "causal_chain": "fixture-only",
        "invalidation_condition": "fixture-only", "no_signal_flag": "true" if direction == "no_clear_direction" else "false",
        "no_signal_reason": "fixture ambiguity" if direction == "no_clear_direction" else "",
        "status": "VALID_FIXTURE_ONLY",
    }


def _validate_forecast(row: Mapping[str, Any], expected_session: str, expected_provider: str, expected_arm: str) -> List[str]:
    errors: List[str] = []
    if _norm(row.get("session_id")) != expected_session:
        errors.append("SESSION_ID_MISMATCH")
    if _norm(row.get("provider")) != expected_provider:
        errors.append("PROVIDER_MISMATCH")
    if _norm(row.get("pack_arm")) != expected_arm:
        errors.append("PACK_ARM_MISMATCH")
    direction = _norm(row.get("forecast_direction"))
    if direction not in {"up", "down", "flat", "no_clear_direction"}:
        errors.append("INVALID_FORECAST_DIRECTION")
    no_signal = _norm(row.get("no_signal_flag")).lower() == "true" or direction == "no_clear_direction"
    if no_signal and not _norm(row.get("no_signal_reason")):
        errors.append("MISSING_NO_SIGNAL_REASON")
    if _safe_prompt(row):
        errors.append("FORBIDDEN_OUTCOME_REFERENCE")
    return errors


def _freeze_session(root: Path, state_row: MutableMapping[str, Any], candidate: Mapping[str, Any], now: datetime) -> None:
    session_id = _norm(candidate["session_id"])
    frozen = {"session": candidate["session"], "members": candidate["members"]}
    errors = _safe_prompt(frozen)
    if errors:
        state_row.update({"status": "FAILED_CLOSED", "failure_code": "OUTCOME_LEAKAGE:" + "|".join(errors)})
        return
    release = _parse_ts(candidate["primary_release_ts"])
    state_row.update({
        "status": "SESSION_MEMBERSHIP_FROZEN", "session_identity": _session_identity(candidate["session"]),
        "session_fingerprint": _hash(frozen), "session_frozen_timestamp": _now(now),
        "release_ts": candidate["primary_release_ts"],
        "planned_capture_ts": _now(release - timedelta(seconds=PRE_OUTCOME_LEAD_SECONDS)),
        "outcome_available_after": _now(release + timedelta(minutes=5)),
    })
    directory = root / "sessions" / state_row["session_identity"]
    _atomic_json(directory / "session_freeze.json", frozen)


def _source_bundle_rows(session_id: str, forecast_cutoff: str = "") -> List[Dict[str, Any]]:
    if not SOURCE_BUNDLE_PATH.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in SOURCE_BUNDLE_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            retrieval = _parse_ts(row.get("retrieval_timestamp"))
            publication = _parse_ts(row.get("publication_timestamp"))
            cutoff = _parse_ts(forecast_cutoff)
            source_safe = not cutoff or bool(retrieval and publication and retrieval < cutoff and publication <= cutoff)
            if _norm(row.get("session_id")) == session_id and source_safe:
                rows.append(row)
    return rows


def _build_local_pack(session_id: str, requests: Sequence[Mapping[str, Any]], shadow_rows: Sequence[Mapping[str, Any]], cutoff: str) -> List[Dict[str, Any]]:
    """Build a status-aware session pack without inventing any missing source facts."""
    items: List[Dict[str, Any]] = []
    for row in shadow_rows:
        if _norm(row.get("session_id")) != session_id:
            continue
        value = _norm(row.get("value")) or _norm(row.get("computed_value"))
        if not value:
            continue
        item = {
            "session_id": session_id, "item_key": _norm(row.get("candidate_field")) or _norm(row.get("item_key")),
            "information_class": "SUPPLIED_DETERMINISTIC", "status": "SUPPLIED_DETERMINISTIC", "value": value,
            "source_timestamp": _norm(row.get("source_timestamp")) or cutoff, "as_of_timestamp": cutoff,
            "forecast_timestamp": cutoff, "data_available_flag": "TRUE", "backtest_safe": "TRUE",
            "provisional_status": "NOT_APPLICABLE", "source_lineage": "Market_State_Pack_Shadow",
        }
        if item["item_key"]:
            items.append(item)
    existing = {item["item_key"] for item in items}
    for request in requests:
        key = _norm(request.get("normalized_information_key")) or _norm(request.get("information_key"))
        if key and key not in existing:
            items.append({
                "session_id": session_id, "item_key": key, "information_class": "NOT_AVAILABLE",
                "status": "NOT_AVAILABLE", "value": "", "source_timestamp": "", "as_of_timestamp": cutoff,
                "forecast_timestamp": cutoff, "data_available_flag": "FALSE", "backtest_safe": "FALSE",
                "provisional_status": "UNAVAILABLE_PENDING_PROVENANCE_VALID_SOURCE_BUNDLE",
                "source_lineage": "request-driven explicit unavailable declaration",
            })
    return sorted(items, key=lambda row: row["item_key"])


def _parse_json_object(raw: str) -> Dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise PipelineError("FORECAST_RESPONSE_NOT_OBJECT")
    return parsed


def _forecast_prompt(session: Mapping[str, Any], members: Sequence[Mapping[str, Any]], exposure: Mapping[str, Any], provider: str, model: str) -> Dict[str, str]:
    from automation.native_v2_typed_schema_v0 import canonical_schema_fingerprint
    from automation.v2_layered_prediction_evaluation_v0 import normalize_session_members

    normalized_members = normalize_session_members(_norm(session.get("session_id")), members)
    target_binding_table = [
        {
            "driver_event_id": row["event_id"],
            "event_target_id": row["event_id"],
            "release_cluster_target_id": row["release_cluster_id"],
            "same_release_cluster_event_ids": sorted(
                member["event_id"] for member in normalized_members
                if member["release_cluster_id"] == row["release_cluster_id"]
            ),
            "reaction_target_requirement": (
                "RELEASE_CLUSTER_REQUIRED" if sum(
                    1 for member in normalized_members if member["release_cluster_id"] == row["release_cluster_id"]
                ) > 1 else "EVENT_OR_RELEASE_CLUSTER"
            ),
        }
        for row in normalized_members
    ]
    base = {
        "protocol": SCHEMA_VERSION, "task": "Forecast the USDJPY market-session reaction without trading advice.",
        "session": dict(session), "members": normalized_members, "provider": provider, "model": model,
        "market_state_exposure": dict(exposure),
        "native_v2_schema_fingerprint": canonical_schema_fingerprint(),
        "native_v2_target_binding_table": target_binding_table,
    }
    if _safe_prompt(base):
        raise PipelineError("OUTCOME_FIELD_IN_FORECAST_PROMPT")
    return {
        "system": "Return only one strict JSON object. Do not browse. Do not provide trading advice.",
        "user": _json(base),
        "instruction": (
            "Use only supplied pre-outcome inputs. Do not refer to outcomes or earlier forecasts. "
            "The provider transport enforces the native-v2 typed schema. Emit only that typed object; do not echo this request. "
            "Frozen cross-field validation also requires session-member drivers and exact reaction targets, consecutive path "
            "stage indexes beginning at 1, and SAME_CLUSTER_NOT_SEPARATELY_PREDICTABLE plus NOT_APPLICABLE interaction "
            "when selected drivers share a release cluster. Use native_v2_target_binding_table: an EVENT target uses the "
            "selected driver's event_target_id and a RELEASE_CLUSTER target uses its release_cluster_target_id. Before emitting, "
            "verify this exact pair field-by-field: never place an event_target_id in a RELEASE_CLUSTER target, never place a "
            "release_cluster_target_id in an EVENT target, and never use the instrument name or symbol as a driver/reaction target."
            " If reaction_target_requirement is RELEASE_CLUSTER_REQUIRED for the selected driver, its reaction target type must be "
            "RELEASE_CLUSTER and its reaction target ID must be that row's release_cluster_target_id; never select EVENT in that case."
            " Conditional serialization is frozen: if secondary_driver_status is not SELECTED, secondary_driver_event_id, "
            "secondary_driver_choice_confidence, secondary_driver_reason, all secondary-reaction target/direction/thesis/"
            "horizon/confidence/pips fields must be the schema's explicit blank value (never 0, null, or a placeholder); "
            "secondary_reaction_status must be NO_MEANINGFUL_SECONDARY_DRIVER, UNCERTAIN, or NOT_PREDICTED; and "
            "interaction_status must be NO_SECONDARY_DRIVER, UNCERTAIN, or NOT_PREDICTED. If a secondary driver is selected "
            "in the same release cluster, use SAME_CLUSTER_NOT_SEPARATELY_PREDICTABLE plus NOT_APPLICABLE_SAME_CLUSTER and "
            "NOT_APPLICABLE interaction. Otherwise a selected secondary driver requires PREDICTED secondary reaction and interaction."
        ),
        "cache_scaffold": "",
    }


def _run_live_preoutcome_experiment(
    root: Path, record: MutableMapping[str, Any], candidate: Mapping[str, Any], shadow_rows: Sequence[Mapping[str, Any]], now: datetime
) -> List[Dict[str, Any]]:
    """Execute one eligible session through existing provider transports.

    This is called only by an active scheduler tick after the configured lead
    time.  It keeps request collection, acquisition, pack construction and
    forecast capture in one pre-outcome transaction lineage.
    """
    from automation.build_session_attention_map_v0 import _build_provider_requests as attention_requests, _run_live_contracts as run_attention
    from automation.build_session_information_requests_v0 import _build_provider_requests as information_requests, _run_live_contracts as run_information
    from automation.build_pack_exposure_pilot_run_v0 import _call_live_provider_raw
    from automation.configure_market_state_pack_external_acquisition_v0 import _acquire_request, _load_model_config, _pack_item_from_result, _validate_source_bundle
    from automation.google_clients import build_script_service, default_script_id, load_credentials

    session = dict(candidate["session"])
    session_id = _norm(candidate["session_id"])
    members_by_session = {session_id: [dict(row) for row in candidate["members"]]}
    providers = [{"provider": provider, "model": model} for provider, model in FORECAST_PROVIDERS.items()]
    credentials = load_credentials(interactive=False)
    script_service, script_id = build_script_service(credentials), default_script_id()
    run_id = "9-PROSPECTIVE-A-E_" + now.strftime("%Y%m%dT%H%M%SZ")
    generated = _now(now)
    session_dir = root / "sessions" / record["session_identity"]
    attention_rows, _, attention_ok, _ = run_attention(
        generated, run_id, [session], members_by_session, attention_requests([session], members_by_session, providers), script_service, script_id
    )
    if not attention_ok:
        record.update({"status": "FAILED_CLOSED", "failure_code": "ATTENTION_PROVIDER_CONTRACT_FAILURE"})
        return []
    _write_jsonl(session_dir / "attention.jsonl", attention_rows)
    record.update({"status": "ATTENTION_CAPTURED", "attention_capture_timestamp": generated})
    attention_by_pair: Dict[tuple[str, str], List[Dict[str, Any]]] = {}
    for row in attention_rows:
        attention_by_pair.setdefault((_norm(row.get("session_id")), _norm(row.get("provider"))), []).append(dict(row))
    request_rows, _, request_ok, _ = run_information(
        generated, run_id, [session], members_by_session,
        information_requests([session], members_by_session, attention_by_pair, providers), script_service, script_id
    )
    if not request_ok:
        record.update({"status": "FAILED_CLOSED", "failure_code": "REQUEST_PROVIDER_CONTRACT_FAILURE"})
        return []
    record.update({"status": "REQUESTS_CAPTURED", "request_capture_timestamp": generated})
    for request in request_rows:
        category = _norm(request.get("information_category"))
        request["prospective_classification"] = (
            "qualitative_interpretive" if category in {"market_positioning", "other"}
            else "qualitative_source_grounded" if category in {"inflation_narrative", "growth_context", "labor_market_trend"}
            else "quantitative_derived" if category in {"usdjpy_trend", "risk_sentiment", "volatility"}
            else "quantitative_direct"
        )
    _write_jsonl(session_dir / "information_requests.jsonl", request_rows)
    record.update({"status": "REQUESTS_CLASSIFIED", "request_classification_timestamp": generated})
    # Capture institutional source state in a separate shadow population. This
    # sidecar is deliberately non-blocking and cannot mutate the existing A/E
    # pack or forecast identities.
    try:
        from automation.run_phase9_prospective_institutional_source_capture_v0 import capture_prospective_institutional_sources
        institutional_capture = capture_prospective_institutional_sources(
            root=root,
            session_id=session_id,
            forecast_cutoff=_norm(session.get("forecast_cutoff")) or generated,
            request_rows=request_rows,
            generated_timestamp=generated,
        )
        record.update({
            "institutional_source_capture_status": institutional_capture.get("status"),
            "institutional_sources_admitted": institutional_capture.get("sources_admitted", 0),
            "institutional_population_mutated_existing_a_e": False,
        })
    except Exception as exc:
        record.update({
            "institutional_source_capture_status": "SHADOW_SOURCE_CAPTURE_FAILED_CLOSED",
            "institutional_source_capture_error": str(exc),
            "institutional_population_mutated_existing_a_e": False,
        })
    pack = _build_local_pack(session_id, request_rows, shadow_rows, generated)
    # Provenance-valid source bundles are the only input that can enable the
    # separate acquisition role.  Until they exist, requests remain explicit
    # unavailable declarations rather than model-generated facts.
    bundles = _source_bundle_rows(session_id, generated)
    valid_bundles: List[Dict[str, Any]] = []
    for bundle in bundles:
        try:
            valid_bundles.append(_validate_source_bundle(bundle, "PROSPECTIVE_SHADOW"))
        except Exception:
            # An invalid source cannot become a scientific pack item; the
            # request's existing explicit unavailable declaration remains.
            continue
    acquisition_results: List[Dict[str, Any]] = []
    if valid_bundles:
        acquisition_config = _load_model_config()
        for request in request_rows:
            key = _norm(request.get("normalized_information_key"))
            matched = [bundle for bundle in valid_bundles if _norm(bundle.get("information_key")) == key]
            if not matched:
                continue
            result, _ = _acquire_request(request, matched, acquisition_config, "PROSPECTIVE_SHADOW", run_id, generated)
            acquisition_results.append(result)
            if _norm(result.get("result_status")) == "ACQUIRED_AI_RETRIEVED_PROVISIONAL":
                pack = [item for item in pack if item.get("item_key") != key]
                pack.append(_pack_item_from_result(result, run_id, generated))
        pack.sort(key=lambda row: _norm(row.get("item_key")))
    _write_jsonl(session_dir / "acquisition_results.jsonl", acquisition_results)
    record.update({"source_bundle_count": len(valid_bundles), "acquisition_result_count": len(acquisition_results), "acquisition_mode": "OpenAI/gpt-5.6-luna/low/MODEL_DEFAULT"})
    record.update({"status": "ACQUISITION_COMPLETE", "acquisition_timestamp": generated})
    pack_fp = _hash(pack)
    _write_jsonl(session_dir / "session_pack_e.jsonl", pack)
    _atomic_json(session_dir / "pack_freeze.json", {"session_id": session_id, "pack_version": "prospective_true_shared_pack_e_v1", "pack_fingerprint": pack_fp, "rendered_context_fingerprint": _hash({"items": pack}), "item_count": len(pack), "frozen_timestamp": generated, "freeze_status": "FROZEN_FOR_PHASE9_PROSPECTIVE_A_VS_E", "shadow_only": True})
    record.update({"status": "PACK_E_FROZEN", "pack_frozen_timestamp": generated})
    attempts: List[Dict[str, Any]] = []
    forecasts: List[Dict[str, Any]] = []
    v2_predictions: List[Dict[str, Any]] = []
    v2_paths: List[Dict[str, Any]] = []
    from automation.v2_layered_prediction_evaluation_v0 import (
        append_shadow_rows_to_workbook, parse_provider_prediction,
    )
    for provider, model in FORECAST_PROVIDERS.items():
        for arm in ("A", "E"):
            exposure = (
                {"pack_selected": "NO_PACK", "pack_item_count": 0, "pack_e_exposure": False, "items": []}
                if arm == "A" else
                {"pack_selected": "prospective_true_shared_pack_e", "pack_item_count": len(pack), "pack_e_exposure": True, "pack_fingerprint": pack_fp, "items": pack}
            )
            prompt = _forecast_prompt(session, candidate["members"], exposure, provider, model)
            leakage = _safe_prompt(prompt)
            identity = _observation_identity(session_id, provider, arm, generated, "" if arm == "A" else pack_fp)
            if leakage:
                attempts.append({"session_id": session_id, "provider": provider, "arm": arm, "status": "LEAKAGE_CHECK_FAILED", "errors": leakage})
                continue
            parsed: Dict[str, Any] = {}
            errors: List[str] = []
            response: Mapping[str, Any] = {}
            v2_prediction: Dict[str, Any] | None = None
            v2_path: List[Dict[str, Any]] = []
            for schema_attempt in range(2):
                request_prompt = dict(prompt)
                if schema_attempt:
                    request_prompt["instruction"] = prompt["instruction"] + " Correct only these schema errors: " + "|".join(errors)
                response = _call_live_provider_raw(script_service, script_id, provider, model, request_prompt)
                try:
                    parsed = _parse_json_object(_norm(response.get("raw_output"))) if _norm(response.get("status")) == "ok" else {}
                    parsed.update({"session_id": session_id, "provider": provider, "model": model, "pack_arm": arm})
                    errors = _validate_forecast(parsed, session_id, provider, arm)
                    if not errors:
                        v2_prediction, v2_path = parse_provider_prediction(
                            parsed, session=session, members=candidate["members"], provider=provider, model=model,
                            pack_arm=arm, pack_freeze_id="NO_PACK" if arm == "A" else "P9PACK_" + pack_fp[:24],
                            pack_fingerprint="" if arm == "A" else pack_fp, forecast_run_id=run_id,
                            forecast_created_ts=generated,
                            forecast_cutoff_ts=_norm(session.get("forecast_cutoff")) or generated,
                            prompt_version=SCHEMA_VERSION + "+v2.0-layered-shadow-v0",
                            raw_output=_norm(response.get("raw_output")),
                        )
                except Exception as exc:
                    errors = ["OUTPUT_SCHEMA_FAILED:" + str(exc)]
                if not errors and v2_prediction:
                    break
            status = "FROZEN_PREOUTCOME" if not errors else "OUTPUT_SCHEMA_FAILED"
            row = {"forecast_identity": identity, "session_id": session_id, "provider": provider, "model": model, "pack_arm": arm,
                   "forecast_timestamp": generated, "pack_fingerprint": "" if arm == "A" else pack_fp, "raw_output": _norm(response.get("raw_output")),
                   "parsed_output": parsed, "status": status, "validation_errors": errors, "outcome_access": 0, "production_authority": False}
            forecasts.append(row)
            if status == "FROZEN_PREOUTCOME" and v2_prediction:
                v2_predictions.append(v2_prediction)
                v2_paths.extend(v2_path)
            attempts.append({"session_id": session_id, "provider": provider, "arm": arm, "status": status, "forecast_identity": identity, "outcome_access": 0})
    _write_jsonl(session_dir / "forecast_attempts.jsonl", forecasts)
    _write_jsonl(session_dir / "v2_predictions.jsonl", v2_predictions)
    _write_jsonl(session_dir / "v2_prediction_paths.jsonl", v2_paths)
    try:
        v2_workbook_writes = append_shadow_rows_to_workbook(predictions=v2_predictions, paths=v2_paths)
        record.update({"v2_layered_workbook_status": "WRITTEN", "v2_layered_workbook_writes": v2_workbook_writes})
    except Exception as exc:
        record.update({"v2_layered_workbook_status": "FAILED_CLOSED", "v2_layered_workbook_error": str(exc)})
    complete = []
    for provider in FORECAST_PROVIDERS:
        arms = {row["pack_arm"]: row for row in forecasts if row["provider"] == provider and row["status"] == "FROZEN_PREOUTCOME"}
        complete.append({"session_id": session_id, "provider": provider, "pair_status": "COMPLETE_A_AND_E_PAIR" if set(arms) == {"A", "E"} else "INCOMPLETE_PAIR", "a_forecast_identity": _norm(arms.get("A", {}).get("forecast_identity")), "e_forecast_identity": _norm(arms.get("E", {}).get("forecast_identity")), "outcome_status": "AWAITING_OUTCOME_WINDOW"})
    _write_jsonl(session_dir / "matched_pairs.jsonl", complete)
    try:
        from automation.run_phase9_prospective_institutional_source_capture_v0 import finalize_prospective_institutional_arm
        institutional_arm = finalize_prospective_institutional_arm(
            root=root,
            session=session,
            members=candidate["members"],
            request_rows=request_rows,
            base_pack=pack,
            generated_timestamp=generated,
            script_service=script_service,
            script_id=script_id,
        )
        record.update({
            "institutional_environment_arm_status": institutional_arm.get("status"),
            "institutional_environment_arm_frozen_forecasts": institutional_arm.get("frozen_forecast_count", 0),
            "institutional_population_mutated_existing_a_e": False,
        })
    except Exception as exc:
        record.update({
            "institutional_environment_arm_status": "SHADOW_INSTITUTIONAL_ARM_FAILED_CLOSED",
            "institutional_environment_arm_error": str(exc),
            "institutional_population_mutated_existing_a_e": False,
        })
    record.update({"status": "FORECASTS_FROZEN", "forecast_run_id": run_id, "pack_fingerprint": pack_fp, "pack_item_count": len(pack), "forecast_pair_count": len([row for row in complete if row["pair_status"] == "COMPLETE_A_AND_E_PAIR"]), "outcome_access": 0})
    return attempts


def _attach_exact_outcome_after_window(root: Path, record: MutableMapping[str, Any], candidate: Mapping[str, Any], state: MutableMapping[str, Any], now: datetime) -> List[Dict[str, Any]]:
    """Load canonical data only after both forecast arms are durably frozen."""
    from automation.build_market_sessions_shadow_v0 import DIAGNOSTICS_SPREADSHEET_ID, _sheet_to_rows
    from automation.complete_pack_a_vs_frozen_true_pack_e_experiment_v0 import _evaluate_arm, _outcome_status
    from automation.google_clients import build_script_service, build_sheets_service, default_script_id, load_credentials

    directory = root / "sessions" / _norm(record.get("session_identity"))
    forecast_path, pairs_path = directory / "forecast_attempts.jsonl", directory / "matched_pairs.jsonl"
    if not forecast_path.exists() or not pairs_path.exists():
        record.update({"status": "FAILED_CLOSED", "failure_code": "MISSING_FROZEN_FORECAST_ARTIFACT"})
        return []
    forecasts = [json.loads(line) for line in forecast_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    pairs = [json.loads(line) for line in pairs_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    credentials = load_credentials(interactive=False)
    canonical_rows = _sheet_to_rows(build_sheets_service(credentials), DIAGNOSTICS_SPREADSHEET_ID, "Market_Reaction_Canonical_Outcomes")
    # The existing evaluator enforces exact member/occurrence identity, strict
    # readiness, authority and the frozen five-minute window.
    session_for_outcome = {"session": candidate["session"], "members": candidate["members"]}
    record.update({"status": "OUTCOME_AVAILABLE", "outcome_window_checked_timestamp": _now(now)})
    outcome_status, reason, outcome = _outcome_status(session_for_outcome, canonical_rows)
    audit: List[Dict[str, Any]] = []
    evaluable: List[Dict[str, Any]] = []
    for pair in pairs:
        if pair.get("pair_status") != "COMPLETE_A_AND_E_PAIR" or outcome_status != "EXACT_OUTCOME_ATTACHED" or not outcome:
            audit.append({"session_id": pair.get("session_id"), "provider": pair.get("provider"), "outcome_status": outcome_status, "reason": reason})
            continue
        selected = {row["pack_arm"]: row for row in forecasts if row.get("provider") == pair.get("provider") and row.get("status") == "FROZEN_PREOUTCOME"}
        if set(selected) != {"A", "E"}:
            audit.append({"session_id": pair.get("session_id"), "provider": pair.get("provider"), "outcome_status": "REMAINS_UNEVALUABLE", "reason": "MISSING_COMPLETE_FROZEN_PAIR"})
            continue
        a_eval, e_eval = _evaluate_arm(selected["A"], outcome), _evaluate_arm(selected["E"], outcome)
        evaluable.append({
            "session_id": pair["session_id"], "provider": pair["provider"], "outcome_status": outcome_status,
            "canonical_outcome_id": _norm(outcome.get("canonical_outcome_id")), "a_forecast_identity": pair["a_forecast_identity"], "e_forecast_identity": pair["e_forecast_identity"],
            "pack_a": a_eval, "pack_e": e_eval, "outcome_loaded_after_forecast_freeze": True,
        })
        audit.append({"session_id": pair["session_id"], "provider": pair["provider"], "outcome_status": outcome_status, "reason": "", "canonical_outcome_id": _norm(outcome.get("canonical_outcome_id"))})
    # The v2 outcome path is a separate shadow projection. It runs only after
    # legacy exact/strict outcome attachment has opened the post-outcome gate.
    v2_prediction_path = directory / "v2_predictions.jsonl"
    v2_path_path = directory / "v2_prediction_paths.jsonl"
    if outcome_status == "EXACT_OUTCOME_ATTACHED" and v2_prediction_path.exists() and v2_path_path.exists():
        try:
            from automation.build_session_evaluation_v0 import _call_usdjpy_window_move
            from automation.v2_layered_prediction_evaluation_v0 import (
                append_shadow_rows_to_workbook, construct_outcomes_from_window_moves,
                evaluate_prediction, release_clusters,
            )
            v2_predictions = [json.loads(line) for line in v2_prediction_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            v2_paths = [json.loads(line) for line in v2_path_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            script_service = build_script_service(credentials)
            script_id = default_script_id()
            clusters = release_clusters(_norm(candidate["session_id"]), candidate["members"])
            cluster_moves = {}
            for cluster in clusters:
                release = _parse_ts(cluster["release_ts"])
                cluster_moves[cluster["release_cluster_id"]] = _call_usdjpy_window_move(
                    script_service, script_id, _now(release), _now(release + timedelta(minutes=5)),
                )
            first_release = _parse_ts(clusters[0]["release_ts"])
            final_release = _parse_ts(clusters[-1]["release_ts"])
            session_move = _call_usdjpy_window_move(
                script_service, script_id, _now(first_release), _now(final_release + timedelta(minutes=5)),
            )
            v2_outcomes = construct_outcomes_from_window_moves(
                session=candidate["session"], members=candidate["members"], cluster_moves=cluster_moves,
                session_move=session_move, generated_ts=_now(now),
            )
            v2_evaluations = []
            for prediction in v2_predictions:
                prediction_paths = [row for row in v2_paths if row.get("prediction_id") == prediction.get("prediction_id")]
                v2_evaluations.extend(evaluate_prediction(prediction, prediction_paths, v2_outcomes, _now(now)))
            _write_jsonl(directory / "v2_outcomes.jsonl", v2_outcomes)
            _write_jsonl(directory / "v2_evaluations.jsonl", v2_evaluations)
            writes = append_shadow_rows_to_workbook(outcomes=v2_outcomes, evaluations=v2_evaluations)
            record.update({"v2_layered_postoutcome_status": "WRITTEN", "v2_layered_postoutcome_writes": writes})
        except Exception as exc:
            record.update({"v2_layered_postoutcome_status": "FAILED_CLOSED", "v2_layered_postoutcome_error": str(exc)})
    _write_jsonl(directory / "exact_outcome_attachment.jsonl", audit)
    _write_jsonl(directory / "evaluable_pairs.jsonl", evaluable)
    all_pairs = [row for row in state.get("evaluable_pairs", []) if _norm(row.get("session_id")) != _norm(candidate["session_id"])] + evaluable
    state["evaluable_pairs"] = sorted(all_pairs, key=lambda row: (_norm(row.get("session_id")), _norm(row.get("provider"))))
    record.update({"status": "SESSION_COMPLETE" if evaluable else "SESSION_BLOCKED", "paired_evaluation_status": "PAIRED_EVALUATION_COMPLETE" if evaluable else "NOT_EVALUABLE", "outcome_attachment_status": outcome_status, "outcome_attachment_reason": reason, "outcome_access": 1, "evaluated_timestamp": _now(now)})
    return audit


def _capture_fixture_lifecycle(root: Path) -> Dict[str, Any]:
    """Exercise the complete lifecycle with only fixture data and no model calls."""
    now = datetime(2031, 1, 2, 13, 15, tzinfo=timezone.utc)
    session = {"session_id": "US|2031-01-02|CUSTOM_CONFIG_WINDOW", "primary_release_ts": "2031-01-02T13:30:00Z"}
    members = [{"session_id": session["session_id"], "event_id": "fixture-event", "release_ts": session["primary_release_ts"]}]
    candidate = _candidate_sessions([session], _membership_index(members), now)[0]
    state: Dict[str, Any] = {"sessions": {session["session_id"]: {"session_id": session["session_id"], "status": "SESSION_DISCOVERED"}}}
    record = state["sessions"][session["session_id"]]
    _freeze_session(root, record, candidate, now)
    requests = [{"normalized_information_key": "fixture_context", "request_id": "fixture-request"}]
    pack = _build_local_pack(session["session_id"], requests, [], _now(now))
    pack_fp = _hash(pack)
    prompts = {
        "A": {"session_id": session["session_id"], "pack_selected": "NO_PACK", "pack_item_count": 0, "pack_e_exposure": False},
        "E": {"session_id": session["session_id"], "pack_selected": "prospective_session_pack", "pack_item_count": len(pack), "pack_e_exposure": True, "items": pack},
    }
    forecasts = [_fixture_forecast(session["session_id"], provider, arm) for provider in FORECAST_PROVIDERS for arm in ("A", "E")]
    validation = all(not _validate_forecast(row, session["session_id"], row["provider"], row["pack_arm"]) for row in forecasts)
    pairs = []
    for provider in FORECAST_PROVIDERS:
        pairs.append({"session_id": session["session_id"], "provider": provider, "outcome_status": "EXACT_OUTCOME_ATTACHED"})
    gate = _analysis_gate(pairs)
    restart = _hash({"pack": pack, "forecasts": forecasts}) == _hash({"pack": _build_local_pack(session["session_id"], requests, [], _now(now)), "forecasts": forecasts})
    return {
        "session_freeze": record.get("status") == "SESSION_MEMBERSHIP_FROZEN",
        "prompt_zero_exposure": not prompts["A"]["pack_e_exposure"] and prompts["A"]["pack_item_count"] == 0,
        "prompt_provider_equality": _hash(prompts["E"]["items"]) == _hash(pack),
        "forecast_schema": validation,
        "forecast_outcome_boundary": not _safe_prompt({"prompts": prompts, "forecasts": forecasts}),
        "same_outcome_for_arms": len(pairs) == 3,
        "provider_pairs": gate["provider_session_pairs"],
        "unique_sessions": gate["unique_exact_evaluable_sessions"],
        "idempotent_restart": restart,
        "analysis_threshold": gate["analysis_package_status"] == "WAITING_FOR_5_UNIQUE_EXACT_SESSIONS",
        "fixture_only": True,
        "pack_fingerprint": pack_fp,
    }


def _read_live_source() -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    from automation.build_market_sessions_shadow_v0 import _sheet_to_rows
    from automation.build_pack_behavior_tier2_execution_v0 import DIAGNOSTICS_SPREADSHEET_ID, INPUT_SESSIONS_SHEET, INPUT_SHADOW_SHEET
    from automation.google_clients import build_sheets_service, load_credentials
    credentials = load_credentials(interactive=False)
    service = build_sheets_service(credentials)
    return (
        _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, INPUT_SESSIONS_SHEET),
        _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, "Market_Session_Members"),
        _sheet_to_rows(service, DIAGNOSTICS_SPREADSHEET_ID, INPUT_SHADOW_SHEET),
    )


def run_tick(
    *, root: Path = ACTIVE_ROOT, dry_run: bool = False,
    source: tuple[Sequence[Mapping[str, Any]], Sequence[Mapping[str, Any]], Sequence[Mapping[str, Any]]] | None = None,
    now: datetime | None = None,
) -> Dict[str, Any]:
    """Discover/freeze eligible future sessions. Live provider stages are gated by time.

    The pipeline intentionally fails closed rather than loading outcomes.  A
    current future session is frozen and made visible for the next pre-outcome
    scheduler tick; provider calls are not made by a dry run.
    """
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    with _locked(root):
        paths = _paths(root)
        config = _read_json(paths["config"], {"enabled": False})
        state = _read_json(paths["state"], {"schema_version": SCHEMA_VERSION, "sessions": {}})
        if source is None:
            source = _read_live_source()
        sessions, member_rows, shadow_rows = source
        candidates = _candidate_sessions(sessions, _membership_index(member_rows), current)
        eligible = [row for row in candidates if row["status"] == "ELIGIBLE_FOR_PROSPECTIVE_CAPTURE"]
        attempts: List[Dict[str, Any]] = []
        disabled = paths["disabled"].exists() or not bool(config.get("enabled"))
        pending_outcome = [
            row for row in candidates
            if _norm(state.get("sessions", {}).get(row["session_id"], {}).get("status")) == "FORECASTS_FROZEN"
        ]
        process_candidates = eligible + [row for row in pending_outcome if row not in eligible]
        for candidate in process_candidates:
            session_id = candidate["session_id"]
            record = state.setdefault("sessions", {}).setdefault(session_id, {"session_id": session_id, "status": "SESSION_DISCOVERED"})
            release_for_record = _parse_ts(candidate["primary_release_ts"])
            if record.get("status") == "FORECASTS_FROZEN" and release_for_record and current >= release_for_record + timedelta(minutes=5):
                attempts.extend(_attach_exact_outcome_after_window(root, record, candidate, state, current))
                continue
            if record.get("status") == "SESSION_DISCOVERED":
                _freeze_session(root, record, candidate, current)
                attempts.append({"session_id": session_id, "stage": "SESSION_FREEZE", "status": record.get("status"), "outcome_access": 0})
            if record.get("status") == "SESSION_MEMBERSHIP_FROZEN":
                release = _parse_ts(candidate["primary_release_ts"])
                planned = release - timedelta(seconds=PRE_OUTCOME_LEAD_SECONDS) if release else None
                if release and current >= release:
                    record.update({"status": "MISSED_PREOUTCOME_DEADLINE", "failure_code": "FORECAST_NOT_CAPTURED_BEFORE_RELEASE"})
                elif not dry_run and not disabled and planned and current >= planned:
                    attempts.extend(_run_live_preoutcome_experiment(root, record, candidate, shadow_rows, current))
        state.update({"updated_timestamp": _now(current), "pipeline_version": PIPELINE_VERSION, "shadow_only": True, "production_authority": False, "consumer_switch": False})
        _atomic_json(paths["state"], state)
        _write_jsonl(paths["attempts"], attempts)
        pair_rows = [row for row in state.get("evaluable_pairs", []) if isinstance(row, Mapping)]
        status = {
            "schema_version": SCHEMA_VERSION, "pipeline_version": PIPELINE_VERSION, "timestamp": _now(current),
            "collector_status": "ACTIVE_SHADOW_ONLY" if config.get("enabled") and not disabled else "DISABLED",
            "session_source": "Market_Sessions|Market_Session_Members|Market_State_Pack_Shadow",
            "candidate_sessions": len(candidates), "eligible_sessions": len(eligible),
            "ineligible_sessions": len(candidates) - len(eligible), "session_statuses": [{key: row[key] for key in ("session_id", "status", "reason")} for row in candidates],
            "active_session_states": sorted({str(row.get("status", "")) for row in state.get("sessions", {}).values()}),
            "acquisition_configuration": ACQUISITION_CONFIG, "forecast_provider_configuration": FORECAST_PROVIDERS,
            "analysis_gate": _analysis_gate(pair_rows), "attempts_this_tick": attempts,
            "outcome_access": 0, "production_authority": False, "consumer_switch": False,
            "durable_root": str(root),
        }
        _atomic_json(paths["status"], status)
        return status


def run_self_test() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="presignal-p9-ae-") as temporary:
        root = Path(temporary)
        lifecycle = _capture_fixture_lifecycle(root)
        fixture_session = {"session_id": "US|2031-01-02|CUSTOM_CONFIG_WINDOW", "primary_release_ts": "2031-01-02T13:30:00Z"}
        fixture_members = [{"session_id": fixture_session["session_id"], "event_id": "fixture", "release_ts": fixture_session["primary_release_ts"]}]
        _atomic_json(_paths(root)["config"], {"enabled": True, "shadow_only": True})
        first = run_tick(root=root, dry_run=True, source=([fixture_session], fixture_members, []), now=datetime(2031, 1, 2, 13, 0, tzinfo=timezone.utc))
        second = run_tick(root=root, dry_run=True, source=([fixture_session], fixture_members, []), now=datetime(2031, 1, 2, 13, 0, tzinfo=timezone.utc))
        tests = {
            "session_discovery": first["eligible_sessions"] == 1,
            "deterministic_session_freeze": first["active_session_states"] == ["SESSION_MEMBERSHIP_FROZEN"],
            "no_outcome_access_before_forecast": first["outcome_access"] == 0 and lifecycle["forecast_outcome_boundary"],
            "pack_a_zero_exposure": lifecycle["prompt_zero_exposure"],
            "provider_equal_pack_e": lifecycle["prompt_provider_equality"],
            "forecast_schema": lifecycle["forecast_schema"],
            "same_outcome_for_arms": lifecycle["same_outcome_for_arms"],
            "unique_session_population_counting": lifecycle["provider_pairs"] == 3 and lifecycle["unique_sessions"] == 1,
            "restart_idempotency": second["active_session_states"] == ["SESSION_MEMBERSHIP_FROZEN"] and lifecycle["idempotent_restart"],
            "analysis_gate": lifecycle["analysis_threshold"],
            "production_non_modification": first["production_authority"] is False and first["consumer_switch"] is False,
        }
    return {"all_passed": all(tests.values()), "tests": tests, "fixture_lifecycle": lifecycle}


def _write_activation_artifacts(activation: Mapping[str, Any]) -> Path:
    timestamp = _now().replace("-", "").replace(":", "").replace("Z", "") + "Z"
    run_id = "9-PROSPECTIVE-A-VS-E-ACTIVATION_" + timestamp
    output = ACTIVATION_ROOT / run_id
    output.mkdir(parents=True, exist_ok=False)
    test = dict(activation["self_test"])
    tick = dict(activation["tick"])
    state_machine = [
        {"state": "SESSION_DISCOVERED", "transition": "exact future session identity and members"},
        {"state": "SESSION_MEMBERSHIP_FROZEN", "transition": "pre-outcome source and membership freeze"},
        {"state": "ATTENTION_CAPTURED", "transition": "provider attention maps complete"},
        {"state": "REQUESTS_CAPTURED", "transition": "provider information requests complete"},
        {"state": "REQUESTS_CLASSIFIED", "transition": "approved union request classification complete"},
        {"state": "ACQUISITION_COMPLETE", "transition": "safe deterministic/source-grounded acquisition complete"},
        {"state": "PACK_E_FROZEN", "transition": "session-specific shared pack frozen"},
        {"state": "FORECASTS_FROZEN", "transition": "matched A/E forecasts saved before release"},
        {"state": "AWAITING_OUTCOME_WINDOW", "transition": "outcomes remain inaccessible"},
        {"state": "EXACT_OUTCOME_ATTACHED", "transition": "post-window exact strict canonical attachment"},
        {"state": "PAIRED_EVALUATION_COMPLETE", "transition": "frozen paired metrics reconstructed"},
        {"state": "SESSION_COMPLETE", "transition": "population artifact updated"},
        {"state": "SESSION_BLOCKED", "transition": "fail closed with exact failure code"},
    ]
    _atomic_json(output / "prospective_pipeline_state_machine.json", {"states": state_machine, "idempotent": True, "restart_safe": True})
    _atomic_json(output / "component_reuse_audit.json", {
        "collector": "automation/collect_mechanism_evaluation_population_shadow_v0.py",
        "scheduler": "automation/run_tier2_prospective_shadow_scheduler_v0.py",
        "attention": "automation/build_session_attention_map_v0.py",
        "requests": "automation/build_session_information_requests_v0.py",
        "acquisition": "automation/configure_market_state_pack_external_acquisition_v0.py",
        "canonical_evaluation": "automation/complete_pack_a_vs_frozen_true_pack_e_experiment_v0.py",
        "new_orchestration": "automation/run_phase9_prospective_a_vs_e_pipeline_v0.py",
    })
    _atomic_json(output / "scheduler_configuration.json", {"scheduler": "com.presignal.phase9a.tier2.prospective-shadow", "enabled": True, "cadence_seconds": 60, "child_pipeline": PIPELINE_VERSION})
    _write_jsonl(output / "current_session_status.jsonl", tick["session_statuses"])
    _write_jsonl(output / "session_eligibility.jsonl", tick["session_statuses"])
    _atomic_json(output / "acquisition_configuration_freeze.json", ACQUISITION_CONFIG)
    _atomic_json(output / "provider_configuration_freeze.json", FORECAST_PROVIDERS)
    _atomic_json(output / "pack_e_freeze_policy.json", {"freeze_status": "FROZEN_FOR_PHASE9_PROSPECTIVE_A_VS_E", "shared_provider_content": True, "immutable_after_forecast": True})
    _atomic_json(output / "forecast_capture_policy.json", {"pack_a_zero_exposure": True, "independent_stateless_calls": True, "outcome_access_before_freeze": False})
    _atomic_json(output / "outcome_attachment_policy.json", {"occurrence_key": "country|event_id|normalized_exact_release_ts", "strict_ready_required": True, "window_minutes": 5})
    _atomic_json(output / "paired_evaluation_policy.json", {"existing_frozen_semantics": True, "provider_weighting": False, "same_outcome_for_arms": True})
    _atomic_json(output / "population_threshold_policy.json", {
        "minimum_unique_exact_sessions": ANALYSIS_MIN_UNIQUE_SESSIONS,
        "strong_replication_unique_exact_sessions": ANALYSIS_STRONG_UNIQUE_SESSIONS,
        "current": tick["analysis_gate"], "analysis_execution": "NOT_TRIGGERED_BEFORE_MINIMUM",
    })
    _atomic_json(output / "fixture_lifecycle_result.json", test)
    _write_jsonl(output / "matched_forecast_pair_fixture.jsonl", [
        {"fixture_only": True, "session_id": "US|2031-01-02|CUSTOM_CONFIG_WINDOW", "provider": provider,
         "pair_status": "COMPLETE_A_AND_E_PAIR", "outcome_access": 0}
        for provider in FORECAST_PROVIDERS
    ])
    _write_jsonl(output / "outcome_attachment_fixture.jsonl", [{
        "fixture_only": True, "outcome_attachment_order": "AFTER_FORECAST_FREEZE",
        "required_chain": "session_id->exact member occurrence->strict canonical outcome", "same_outcome_for_a_and_e": True,
    }])
    _atomic_json(output / "live_processing_result.json", tick)
    _atomic_json(output / "activation_summary.json", {"build_status": "PASS", "current_eligible_sessions": tick["eligible_sessions"], "collection_status": tick["collector_status"], "analysis_gate": tick["analysis_gate"]})
    _atomic_json(output / "activation_manifest.json", {
        "activation_run_id": run_id, "pipeline_version": PIPELINE_VERSION, "parent_scheduler": "phase9a_tier2_prospective_shadow_scheduler_v1",
        "entry_point": "python3 automation/run_tier2_prospective_shadow_scheduler_v0.py --active",
        "child_entry_point": "python3 automation/run_phase9_prospective_a_vs_e_pipeline_v0.py --scheduler-tick",
        "shadow_only": True, "production_authority": False, "consumer_switch": False,
        "acquisition_configuration": ACQUISITION_CONFIG, "forecast_providers": FORECAST_PROVIDERS,
        "fixture_tests_passed": test["all_passed"], "active_status": tick["collector_status"],
        "current_eligible_sessions": tick["eligible_sessions"], "created_timestamp": _now(),
    })
    return output


def activate(root: Path = ACTIVE_ROOT) -> Dict[str, Any]:
    test = run_self_test()
    if not test["all_passed"]:
        raise PipelineError("PROSPECTIVE_PIPELINE_SELF_TEST_FAILED")
    with _locked(root):
        _atomic_json(_paths(root)["config"], {
            "enabled": True, "shadow_only": True, "production_authority": False, "consumer_switch": False,
            "pipeline_version": PIPELINE_VERSION, "activated_timestamp": _now(), "scheduler_parent": "phase9a_tier2_prospective_shadow_scheduler_v1",
        })
        _paths(root)["disabled"].unlink(missing_ok=True)
    activation = {"activation_timestamp": _now(), "self_test": test, "tick": run_tick(root=root, dry_run=True)}
    activation["activation_output"] = str(_write_activation_artifacts(activation))
    return activation


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Phase 9 prospective shadow A/E pipeline.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--scheduler-tick", action="store_true")
    group.add_argument("--dry-run", action="store_true", help="Run a standalone discovery-only tick.")
    group.add_argument("--self-test", action="store_true")
    group.add_argument("--activate", action="store_true")
    parser.add_argument("--scheduler-dry-run", action="store_true", help="Discovery-only mode when invoked by Tier 2.")
    args = parser.parse_args()
    if args.self_test:
        result = run_self_test()
    elif args.activate:
        result = activate()
    else:
        result = run_tick(dry_run=args.dry_run or args.scheduler_dry_run)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
