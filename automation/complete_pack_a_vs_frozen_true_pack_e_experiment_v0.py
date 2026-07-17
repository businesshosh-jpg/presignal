#!/usr/bin/env python3
"""Complete the shadow Pack A versus frozen true Pack E experiment.

The script has an explicit separation point: it repairs and freezes forecasts
before loading any canonical outcome rows. It writes local shadow artifacts
only and does not modify workbooks, production consumers, or Pack E.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_market_sessions_shadow_v0 import DIAGNOSTICS_SPREADSHEET_ID, _norm, _sheet_to_rows
from automation.build_session_evaluation_v0 import DEFAULT_FLAT_THRESHOLD_PIPS, _strength_ok
from automation.build_session_information_requests_v0 import _iso_now, _safe_float
from automation.capture_pack_a_vs_frozen_true_pack_e_forecasts_v0 import (
    EXPECTED_PACK_FINGERPRINT,
    EXPECTED_RENDERED_FINGERPRINT,
    FIXTURE_VALIDATION,
    FORECAST_TARGET,
    FREEZE_MANIFEST,
    PACK_A_LEVEL,
    PACK_A_SELECTION,
    PACK_E_LEVEL,
    PROTOCOL_VERSION,
    PROVIDER_ORDER,
    _build_candidates,
    _capture_arm,
    _fingerprint,
    _load_prompt_configuration,
    _pack_a_context,
    _prompt_for_arm,
    _prompt_without_exposure,
    _response_validation,
    _validate_prompt,
)
from automation.google_clients import build_script_service, build_sheets_service, default_script_id, load_credentials
from automation.repair_phase9_may1_7_exact_outcome_link_v0 import _load_canonical_overrides
from automation.true_shared_pack_e_renderer_v0 import content_fingerprint, load_frozen_true_shared_pack_e, render_frozen_true_shared_pack_e_context


PHASE_ID = "9-PACK-A-VS-FROZEN-PACK-E-COMPLETION"
OUTPUT_ROOT = ROOT / "outputs/phase9_pack_a_vs_frozen_pack_e_completion"
CAPTURE_RUN_ID = "9-PACK-A-VS-FROZEN-PACK-E-FORECAST-CAPTURE-R1_20260714T094000Z"
CAPTURE_ROOT = ROOT / "outputs/phase9_pack_a_vs_frozen_pack_e_forecasts" / CAPTURE_RUN_ID
PACK_E_RUN_ID = "9-TRUE-SHARED-PACK-E-VALIDATION_20260714T081534Z"
CANONICAL_REPAIR_RUN_ID = "9-CANONICAL-BATCH-IDENTITY-REPAIR_20260714T085417Z"
CANONICAL_REPAIR_ROOT = ROOT / "outputs/phase9_canonical_batch_identity_repair" / CANONICAL_REPAIR_RUN_ID
CANONICAL_OVERRIDE_MANIFEST = CANONICAL_REPAIR_ROOT / "repaired_canonical_outcome_manifest.json"
CANONICAL_IMPLEMENTATION_VERSION = "market_reaction_outcome_source_implementation_v0"
CANONICAL_IMPLEMENTATION_RUN_ID = "market_reaction_outcome_source_implementation_v0_20260709T065247Z"
FROZEN_WINDOW_POLICY = "EVENT_RELATIVE_FIXED_DURATION"
FROZEN_WINDOW_MINUTES = 5
OPENAI_MODEL = "gpt-4o-mini-2024-07-18"
TARGET_SESSIONS = (
    "US|2024-05-19|CUSTOM_CONFIG_WINDOW",
    "US|2024-05-20|CUSTOM_CONFIG_WINDOW",
)
SCHEMA_CLARIFICATION_VERSION = "openai_pack_a_conditional_no_signal_r1"
SCHEMA_CLARIFICATION = (
    "CONDITIONAL NO-SIGNAL SCHEMA CLARIFICATION\n"
    "If forecast_direction is no_clear_direction or no_signal_flag is true, "
    "no_signal_flag must be true and no_signal_reason must be a non-empty explanation. "
    "Otherwise no_signal_flag must be false and no_signal_reason may be empty. "
    "This is a schema requirement only; choose the forecast direction independently from the supplied evidence."
)
REQUIRED_COMPLETENESS_FIELDS = {
    "session_id", "provider", "model", "pack_level", "forecast_direction",
    "primary_driver_summary", "causal_chain", "no_signal_flag", "status",
}


class CompletionBlocked(RuntimeError):
    """Raised only for a hard experiment invariant."""


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _read_json(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CompletionBlocked("JSON_OBJECT_REQUIRED:" + str(path))
    return value


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise CompletionBlocked(f"JSONL_OBJECT_REQUIRED:{path}:{line_number}")
        rows.append(value)
    return rows


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.write_text("".join(_canonical(dict(row)) + "\n" for row in rows), encoding="utf-8")


def _parse_dt(value: Any) -> Optional[datetime]:
    text = _norm(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _same_instant(left: Any, right: Any) -> bool:
    a, b = _parse_dt(left), _parse_dt(right)
    return a is not None and b is not None and a == b


def _truth(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _norm(value).upper() in {"TRUE", "1", "YES", "Y"}


def _percent(numerator: int, denominator: int) -> Optional[float]:
    return round(100.0 * numerator / denominator, 6) if denominator else None


def _run_id() -> str:
    return PHASE_ID + "_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _load_authoritative_capture() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    summary = _read_json(CAPTURE_ROOT / "forecast_capture_summary.json")
    if _norm(summary.get("run_id")) != CAPTURE_RUN_ID:
        raise CompletionBlocked("FORECAST_CAPTURE_RUN_ID_MISMATCH")
    a_rows = _read_jsonl(CAPTURE_ROOT / "pack_a_forecasts.jsonl")
    e_rows = _read_jsonl(CAPTURE_ROOT / "frozen_pack_e_forecasts.jsonl")
    if len(a_rows) != 6 or len(e_rows) != 6:
        raise CompletionBlocked("FORECAST_CAPTURE_ARM_COUNT_MISMATCH")
    return a_rows, e_rows, summary


def _clarified_prompt(base_prompt: Mapping[str, str]) -> Dict[str, str]:
    prompt = dict(base_prompt)
    prompt["user"] = _norm(prompt.get("user")) + "\n\n" + SCHEMA_CLARIFICATION
    return prompt


def _prompt_without_clarification(prompt: Mapping[str, str]) -> Dict[str, str]:
    normalized = dict(prompt)
    normalized["user"] = _norm(normalized.get("user")).replace("\n\n" + SCHEMA_CLARIFICATION, "")
    return normalized


def _repair_openai_pack_a(
    sheets_service,
    script_service,
    script_id: str,
    frozen_pack: Mapping[str, Any],
    run_id: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any], List[Dict[str, Any]]]:
    provider_config, schema_rows, guardrail_rows, prompt_run_id = _load_prompt_configuration(sheets_service)
    config = provider_config.get("OpenAI", {})
    if not config.get("configured") or _norm(config.get("model")) != OPENAI_MODEL:
        raise CompletionBlocked("FROZEN_OPENAI_CONFIGURATION_UNAVAILABLE")
    candidates, eligibility = _build_candidates(sheets_service, frozen_pack)
    candidate_by_id = {row["session_id"]: row for row in candidates}
    if set(candidate_by_id) != set(TARGET_SESSIONS):
        raise CompletionBlocked("OPENAI_REPAIR_ELIGIBLE_SESSION_SET_MISMATCH")
    from automation.build_pack_exposure_prompt_validation_v0 import _guardrail_payload, _schema_payload

    schema_payload = _schema_payload(schema_rows)
    guardrails = _guardrail_payload(guardrail_rows)
    repair_rows: List[Dict[str, Any]] = []
    prompt_audit: List[Dict[str, Any]] = []
    empty_existing: Dict[str, Dict[str, Any]] = {}
    for session_id in TARGET_SESSIONS:
        candidate = candidate_by_id[session_id]
        exposure = _pack_a_context()
        execution_identity = {"session_id": session_id, "provider": "OpenAI", "model": OPENAI_MODEL}
        base_prompt, base_hash, _ = _prompt_for_arm(
            config["design_row"], candidate["event_context"], exposure,
            schema_payload, guardrails, execution_identity,
        )
        repaired_prompt = _clarified_prompt(base_prompt)
        leakage_errors = _validate_prompt(repaired_prompt, exposure, PACK_A_LEVEL)
        equivalent = _prompt_without_clarification(repaired_prompt) == base_prompt
        if not equivalent or leakage_errors:
            raise CompletionBlocked("OPENAI_REPAIR_PROMPT_PREFLIGHT_FAILED:" + session_id)
        prompt_audit.append({
            "session_id": session_id,
            "provider": "OpenAI",
            "model": OPENAI_MODEL,
            "base_prompt_fingerprint": base_hash,
            "repair_prompt_fingerprint": _fingerprint(repaired_prompt),
            "schema_clarification_version": SCHEMA_CLARIFICATION_VERSION,
            "equivalent_excluding_clarification": equivalent,
            "pack_selected": PACK_A_SELECTION,
            "pack_item_count": 0,
            "pack_e_exposure": False,
            "pack_fingerprint": "",
            "leakage_check": "PASS",
        })
        row = _capture_arm(
            script_service, script_id, "OpenAI", config, PACK_A_LEVEL,
            repaired_prompt, session_id, candidate["cutoff"], schema_rows,
            exposure, empty_existing,
        )
        row.update({
            "completion_run_id": run_id,
            "repair_run_id": run_id + "-OPENAI-PACK-A-REPAIR",
            "repair_lineage": CAPTURE_RUN_ID,
            "superseded_invalid_arm_identity": row.get("experimental_identity", ""),
            "schema_clarification_version": SCHEMA_CLARIFICATION_VERSION,
            "prompt_equivalent_excluding_clarification": True,
            "scientific_content_edited_after_generation": False,
        })
        repair_rows.append(row)
    return repair_rows, prompt_audit, config, eligibility


def _arm_key(row: Mapping[str, Any]) -> Tuple[str, str, str]:
    return (_norm(row.get("session_id")), _norm(row.get("provider")), _norm(row.get("pack_arm")))


def _valid_arm(row: Mapping[str, Any], expected_arm: str, config: Mapping[str, Mapping[str, Any]]) -> List[str]:
    errors: List[str] = []
    provider = _norm(row.get("provider"))
    expected_model = _norm(config.get(provider, {}).get("model"))
    if _norm(row.get("status")) != "CAPTURED":
        errors.append("ARM_NOT_CAPTURED")
    if not provider or _norm(row.get("actual_model")) != expected_model or _norm(row.get("model")) != expected_model:
        errors.append("PROVIDER_MODEL_IDENTITY_MISMATCH")
    if _norm(row.get("pack_arm")) != expected_arm:
        errors.append("PACK_ARM_MISMATCH")
    if expected_arm == PACK_A_LEVEL:
        if _norm(row.get("pack_version")) != PACK_A_SELECTION or row.get("pack_item_count") != 0 or _norm(row.get("pack_fingerprint")):
            errors.append("PACK_A_ZERO_EXPOSURE_FAILED")
    else:
        if _norm(row.get("pack_version")) != "true_shared_pack_e_v1" or _norm(row.get("pack_fingerprint")) != EXPECTED_PACK_FINGERPRINT:
            errors.append("FROZEN_PACK_E_IDENTITY_FAILED")
    return errors


def _consolidate_pairs(
    original_a: Sequence[Mapping[str, Any]],
    original_e: Sequence[Mapping[str, Any]],
    repaired_a: Sequence[Mapping[str, Any]],
    config: Mapping[str, Mapping[str, Any]],
    run_id: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[Tuple[str, str], Dict[str, Any]]]:
    a_by_key = {_arm_key(row): dict(row) for row in original_a if _norm(row.get("status")) == "CAPTURED"}
    for row in repaired_a:
        if _norm(row.get("status")) == "CAPTURED":
            a_by_key[_arm_key(row)] = dict(row)
    e_by_key = {_arm_key(row): dict(row) for row in original_e if _norm(row.get("status")) == "CAPTURED"}
    complete: List[Dict[str, Any]] = []
    incomplete: List[Dict[str, Any]] = []
    selected: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for session_id in TARGET_SESSIONS:
        for provider in PROVIDER_ORDER:
            a = a_by_key.get((session_id, provider, PACK_A_LEVEL), {})
            e = e_by_key.get((session_id, provider, PACK_E_LEVEL), {})
            a_errors = _valid_arm(a, PACK_A_LEVEL, config) if a else ["PACK_A_MISSING"]
            e_errors = _valid_arm(e, PACK_E_LEVEL, config) if e else ["PACK_E_MISSING"]
            status = "COMPLETE_A_AND_E_PAIR"
            if a_errors:
                status = "INCOMPLETE_PACK_A"
            elif e_errors:
                status = "INCOMPLETE_PACK_E"
            elif _norm(a.get("session_id")) != _norm(e.get("session_id")) or _norm(a.get("provider")) != _norm(e.get("provider")) or _norm(a.get("model")) != _norm(e.get("model")):
                status = "EXCLUDED_IDENTITY_MISMATCH"
            pair = {
                "completion_run_id": run_id,
                "session_id": session_id,
                "provider": provider,
                "provider_model": _norm(config.get(provider, {}).get("model")),
                "forecast_target": FORECAST_TARGET,
                "forecast_cutoff": _norm(a.get("forecast_timestamp")) or _norm(e.get("forecast_timestamp")),
                "prompt_version": _norm(config.get(provider, {}).get("prompt_version")),
                "output_schema_version": _norm(config.get(provider, {}).get("output_schema_version")),
                "experimental_protocol_version": PROTOCOL_VERSION,
                "pack_a_forecast_identity": _norm(a.get("experimental_identity")),
                "pack_e_forecast_identity": _norm(e.get("experimental_identity")),
                "pack_a_source_run": _norm(a.get("repair_run_id")) or CAPTURE_RUN_ID,
                "pack_e_source_run": CAPTURE_RUN_ID,
                "pack_a_repair_lineage": _norm(a.get("repair_lineage")),
                "pack_a_status": _norm(a.get("status")) or "MISSING",
                "pack_e_status": _norm(e.get("status")) or "MISSING",
                "pair_status": status,
                "exclusion_reasons": sorted(set(a_errors + e_errors)),
                "pack_a": a,
                "pack_e": e,
            }
            target = complete if status == "COMPLETE_A_AND_E_PAIR" else incomplete
            target.append(pair)
            if status == "COMPLETE_A_AND_E_PAIR":
                selected[(session_id, provider)] = pair
    identities = [arm for pair in complete for arm in (pair["pack_a_forecast_identity"], pair["pack_e_forecast_identity"])]
    if not all(identities) or len(identities) != len(set(identities)):
        raise CompletionBlocked("AUTHORITATIVE_FORECAST_ARM_IDENTITY_DUPLICATE")
    return complete, incomplete, selected


def _canonical_candidates_for_session(
    session: Mapping[str, Any], canonical_rows: Sequence[Mapping[str, Any]]
) -> Tuple[List[Dict[str, Any]], str]:
    session_row = session["session"]
    primary_ts = _norm(session_row.get("primary_release_ts"))
    primary_members = [row for row in session["members"] if _same_instant(row.get("release_ts"), primary_ts)]
    if len(primary_members) != 1:
        return [], "SESSION_TO_OUTCOME_IDENTITY_FAILED"
    event_id = _norm(primary_members[0].get("event_id"))
    country = _norm(session_row.get("country"))
    candidates = [
        dict(row) for row in canonical_rows
        if _norm(row.get("country")) == country
        and _norm(row.get("event_id")) == event_id
        and _same_instant(row.get("release_ts"), primary_ts)
        and _norm(row.get("implementation_version")) == CANONICAL_IMPLEMENTATION_VERSION
        and _norm(row.get("implementation_run_id")) == CANONICAL_IMPLEMENTATION_RUN_ID
        and _norm(row.get("window_policy")) == FROZEN_WINDOW_POLICY
        and _safe_float(row.get("window_minutes")) == float(FROZEN_WINDOW_MINUTES)
    ]
    return candidates, ""


def _outcome_status(session: Mapping[str, Any], canonical_rows: Sequence[Mapping[str, Any]]) -> Tuple[str, str, Optional[Dict[str, Any]]]:
    candidates, identity_failure = _canonical_candidates_for_session(session, canonical_rows)
    if identity_failure:
        return identity_failure, "primary release did not resolve to one exact session member", None
    if not candidates:
        return "NO_EXACT_CANONICAL_OUTCOME", "no exact occurrence-level canonical candidate", None
    if len(candidates) > 1:
        return "MULTIPLE_CANONICAL_CANDIDATES", "multiple exact canonical candidates", None
    candidate = candidates[0]
    if not _truth(candidate.get("usable_for_strict_accuracy")):
        return "CANONICAL_OUTCOME_NOT_STRICT_READY", "exact canonical candidate is not strict-ready", None
    start = _safe_float(candidate.get("canonical_start_price"))
    end = _safe_float(candidate.get("canonical_end_price"))
    pips = _safe_float(candidate.get("canonical_realized_pips"))
    direction = _norm(candidate.get("canonical_realized_direction")).upper()
    start_ts, end_ts = _parse_dt(candidate.get("canonical_start_ts")), _parse_dt(candidate.get("canonical_end_ts"))
    if start is None or end is None or pips is None or direction not in {"UP", "DOWN", "FLAT"}:
        return "REMAINS_UNEVALUABLE", "strict candidate lacks required scientific values", None
    if not start_ts or not end_ts or (end_ts - start_ts).total_seconds() != FROZEN_WINDOW_MINUTES * 60:
        return "OUTCOME_WINDOW_MISMATCH", "canonical window is not exactly five minutes", None
    return "EXACT_OUTCOME_ATTACHED", "", candidate


def _attach_outcomes(
    complete_pairs: Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
    canonical_rows: Sequence[Mapping[str, Any]],
    run_id: str,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    session_by_id = {row["session_id"]: row for row in candidates}
    session_decisions: Dict[str, Dict[str, Any]] = {}
    for session_id in TARGET_SESSIONS:
        status, reason, outcome = _outcome_status(session_by_id[session_id], canonical_rows)
        session_decisions[session_id] = {"status": status, "reason": reason, "outcome": outcome}
    audit: List[Dict[str, Any]] = []
    for pair in complete_pairs:
        session_id = pair["session_id"]
        decision = session_decisions[session_id]
        outcome = decision["outcome"]
        cutoff = _parse_dt(pair.get("forecast_cutoff"))
        outcome_start = _parse_dt(outcome.get("canonical_start_ts")) if outcome else None
        forecast_before = bool(cutoff and outcome_start and cutoff <= outcome_start)
        status = decision["status"]
        reason = decision["reason"]
        if outcome and not forecast_before:
            status, reason, outcome = "FORECAST_BEFORE_OUTCOME_FAILED", "forecast cutoff is after canonical outcome-window start", None
        audit.append({
            "completion_run_id": run_id,
            "session_id": session_id,
            "provider": pair["provider"],
            "pair_status": pair["pair_status"],
            "outcome_attachment_status": status,
            "exclusion_reason": reason,
            "canonical_outcome_id": _norm(outcome.get("canonical_outcome_id")) if outcome else "",
            "canonical_outcome_run": CANONICAL_IMPLEMENTATION_RUN_ID if outcome else "",
            "exact_occurrence_identity": bool(outcome),
            "strict_ready": bool(outcome),
            "five_minute_window": bool(outcome),
            "forecast_before_outcome": forecast_before if outcome else False,
            "same_outcome_for_both_arms": bool(outcome),
            "outcome_loaded_after_forecast_population_frozen": True,
        })
    return audit, session_decisions


def _forecast_completeness(forecast: Mapping[str, Any]) -> bool:
    parsed = forecast.get("parsed_output", {})
    if not isinstance(parsed, Mapping):
        return False
    if any(field not in parsed or _norm(parsed.get(field)) == "" for field in REQUIRED_COMPLETENESS_FIELDS):
        return False
    direction = _norm(parsed.get("forecast_direction"))
    no_signal = _truth(parsed.get("no_signal_flag")) or direction == "no_clear_direction"
    return not no_signal or bool(_norm(parsed.get("no_signal_reason")))


def _evaluate_arm(forecast: Mapping[str, Any], outcome: Mapping[str, Any]) -> Dict[str, Any]:
    parsed = forecast.get("parsed_output", {})
    direction = _norm(parsed.get("forecast_direction")).lower()
    realized_direction = _norm(outcome.get("canonical_realized_direction")).lower()
    realized_pips = _safe_float(outcome.get("canonical_realized_pips"))
    realized_abs = abs(realized_pips) if realized_pips is not None else None
    no_signal = _truth(parsed.get("no_signal_flag")) or direction == "no_clear_direction"
    direction_ok: Optional[bool] = None
    no_signal_quality: Optional[bool] = None
    overall_ok: Optional[bool] = None
    if direction in {"up", "down", "flat"}:
        direction_ok = direction == realized_direction
        overall_ok = direction_ok
    if no_signal:
        no_signal_quality = realized_abs is not None and realized_abs <= DEFAULT_FLAT_THRESHOLD_PIPS
        if direction == "no_clear_direction":
            overall_ok = no_signal_quality
    strength_token = _strength_ok(
        realized_abs,
        parsed.get("expected_move_pips_min"),
        parsed.get("expected_move_pips_max"),
    )
    strength_ok = True if strength_token == "TRUE" else False if strength_token == "FALSE" else None
    confidence = _safe_float(parsed.get("forecast_confidence"))
    return {
        "forecast_direction": direction,
        "forecast_confidence": confidence,
        "no_signal_flag": no_signal,
        "direction_ok": direction_ok,
        "strength_ok": strength_ok,
        "overall_ok": overall_ok,
        "no_signal_quality": no_signal_quality,
        "forecast_completeness": _forecast_completeness(forecast),
        "confidence_calibration": None,
        "confidence_calibration_status": "UNAVAILABLE_NO_FROZEN_ROW_LEVEL_CALIBRATION_RULE",
    }


def _delta(left: Optional[bool], right: Optional[bool]) -> Optional[int]:
    if left is None or right is None:
        return None
    return int(right) - int(left)


def _paired_classification(a: Mapping[str, Any], e: Mapping[str, Any]) -> str:
    overall_delta = _delta(a.get("overall_ok"), e.get("overall_ok"))
    if overall_delta == 1:
        return "PACK_E_IMPROVED"
    if overall_delta == -1:
        return "PACK_E_WORSENED"
    deltas = [
        _delta(a.get("direction_ok"), e.get("direction_ok")),
        _delta(a.get("strength_ok"), e.get("strength_ok")),
        _delta(a.get("no_signal_quality"), e.get("no_signal_quality")),
        _delta(a.get("forecast_completeness"), e.get("forecast_completeness")),
    ]
    observed = [value for value in deltas if value is not None]
    if overall_delta == 0 and all(value == 0 for value in observed):
        return "NO_CHANGE"
    if not observed and overall_delta is None:
        return "NOT_FULLY_EVALUABLE"
    return "MIXED_RESULT"


def _build_evaluation_rows(
    complete_pairs: Sequence[Mapping[str, Any]],
    attachment_audit: Sequence[Mapping[str, Any]],
    session_decisions: Mapping[str, Mapping[str, Any]],
    run_id: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    attachment_by_pair = {(row["session_id"], row["provider"]): row for row in attachment_audit}
    evaluable: List[Dict[str, Any]] = []
    unevaluable: List[Dict[str, Any]] = []
    for pair in complete_pairs:
        key = (pair["session_id"], pair["provider"])
        attachment = attachment_by_pair[key]
        outcome = session_decisions[pair["session_id"]]["outcome"]
        if attachment["outcome_attachment_status"] != "EXACT_OUTCOME_ATTACHED" or not outcome:
            unevaluable.append({
                "completion_run_id": run_id,
                "session_id": pair["session_id"],
                "provider": pair["provider"],
                "pair_status": pair["pair_status"],
                "evaluation_status": attachment["outcome_attachment_status"],
                "exclusion_reason": attachment["exclusion_reason"],
            })
            continue
        a_eval, e_eval = _evaluate_arm(pair["pack_a"], outcome), _evaluate_arm(pair["pack_e"], outcome)
        row = {
            "completion_run_id": run_id,
            "session_id": pair["session_id"],
            "provider": pair["provider"],
            "provider_model": pair["provider_model"],
            "pack_a_forecast_identity": pair["pack_a_forecast_identity"],
            "pack_e_forecast_identity": pair["pack_e_forecast_identity"],
            "canonical_outcome_id": _norm(outcome.get("canonical_outcome_id")),
            "realized_direction": _norm(outcome.get("canonical_realized_direction")).lower(),
            "realized_pips": _safe_float(outcome.get("canonical_realized_pips")),
            "pack_a_direction": a_eval["forecast_direction"],
            "pack_e_direction": e_eval["forecast_direction"],
            "pack_a_confidence": a_eval["forecast_confidence"],
            "pack_e_confidence": e_eval["forecast_confidence"],
            "pack_a_no_signal_flag": a_eval["no_signal_flag"],
            "pack_e_no_signal_flag": e_eval["no_signal_flag"],
            "pack_a_direction_ok": a_eval["direction_ok"],
            "pack_e_direction_ok": e_eval["direction_ok"],
            "pack_a_strength_ok": a_eval["strength_ok"],
            "pack_e_strength_ok": e_eval["strength_ok"],
            "pack_a_overall_ok": a_eval["overall_ok"],
            "pack_e_overall_ok": e_eval["overall_ok"],
            "pack_a_no_signal_quality": a_eval["no_signal_quality"],
            "pack_e_no_signal_quality": e_eval["no_signal_quality"],
            "pack_a_completeness": a_eval["forecast_completeness"],
            "pack_e_completeness": e_eval["forecast_completeness"],
            "pack_a_confidence_calibration": a_eval["confidence_calibration"],
            "pack_e_confidence_calibration": e_eval["confidence_calibration"],
            "confidence_calibration_status": a_eval["confidence_calibration_status"],
            "direction_result_difference": _delta(a_eval["direction_ok"], e_eval["direction_ok"]),
            "strength_result_difference": _delta(a_eval["strength_ok"], e_eval["strength_ok"]),
            "overall_result_difference": _delta(a_eval["overall_ok"], e_eval["overall_ok"]),
            "confidence_difference": None if a_eval["forecast_confidence"] is None or e_eval["forecast_confidence"] is None else round(e_eval["forecast_confidence"] - a_eval["forecast_confidence"], 6),
            "no_signal_difference": int(e_eval["no_signal_flag"]) - int(a_eval["no_signal_flag"]),
            "completeness_difference": int(e_eval["forecast_completeness"]) - int(a_eval["forecast_completeness"]),
            "paired_result_classification": _paired_classification(a_eval, e_eval),
            "evaluation_semantics": "build_session_evaluation_v0 direction/no-signal/strength semantics",
            "flat_threshold_pips": DEFAULT_FLAT_THRESHOLD_PIPS,
        }
        evaluable.append(row)
    return evaluable, unevaluable


def _accuracy(rows: Sequence[Mapping[str, Any]], field: str) -> Dict[str, Any]:
    observed = [row.get(field) for row in rows if row.get(field) is not None]
    correct = sum(1 for value in observed if value is True)
    return {"correct": correct, "denominator": len(observed), "accuracy_percent": _percent(correct, len(observed))}


def _metrics(
    complete: Sequence[Mapping[str, Any]],
    incomplete: Sequence[Mapping[str, Any]],
    evaluable: Sequence[Mapping[str, Any]],
    unevaluable: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    classes = Counter(_norm(row.get("paired_result_classification")) for row in evaluable)
    return {
        "complete_forecast_pairs": len(complete),
        "incomplete_forecast_pairs": len(incomplete),
        "outcome_attached_pairs": len(evaluable),
        "excluded_complete_pairs": len(unevaluable),
        "unique_evaluable_sessions": len({row["session_id"] for row in evaluable}),
        "providers_represented": len({row["provider"] for row in evaluable}),
        "pack_a_direction_accuracy": _accuracy(evaluable, "pack_a_direction_ok"),
        "pack_e_direction_accuracy": _accuracy(evaluable, "pack_e_direction_ok"),
        "pack_a_strength_accuracy": _accuracy(evaluable, "pack_a_strength_ok"),
        "pack_e_strength_accuracy": _accuracy(evaluable, "pack_e_strength_ok"),
        "pack_a_overall_accuracy": _accuracy(evaluable, "pack_a_overall_ok"),
        "pack_e_overall_accuracy": _accuracy(evaluable, "pack_e_overall_ok"),
        "pack_a_no_signal_count": sum(1 for row in evaluable if row.get("pack_a_no_signal_flag") is True),
        "pack_e_no_signal_count": sum(1 for row in evaluable if row.get("pack_e_no_signal_flag") is True),
        "pack_a_valid_directional_count": sum(1 for row in evaluable if row.get("pack_a_direction") in {"up", "down", "flat"}),
        "pack_e_valid_directional_count": sum(1 for row in evaluable if row.get("pack_e_direction") in {"up", "down", "flat"}),
        "pack_a_forecast_completeness": _accuracy(evaluable, "pack_a_completeness"),
        "pack_e_forecast_completeness": _accuracy(evaluable, "pack_e_completeness"),
        "paired_classifications": {
            "PACK_E_IMPROVED": classes["PACK_E_IMPROVED"],
            "PACK_E_WORSENED": classes["PACK_E_WORSENED"],
            "NO_CHANGE": classes["NO_CHANGE"],
            "MIXED_RESULT": classes["MIXED_RESULT"],
            "NOT_FULLY_EVALUABLE": classes["NOT_FULLY_EVALUABLE"],
        },
    }


def _provider_comparison(complete: Sequence[Mapping[str, Any]], evaluable: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for provider in PROVIDER_ORDER:
        provider_eval = [row for row in evaluable if row["provider"] == provider]
        classes = Counter(row["paired_result_classification"] for row in provider_eval)
        conclusion = "PACK_E_WORSENED" if classes["PACK_E_WORSENED"] > classes["PACK_E_IMPROVED"] else "PACK_E_IMPROVED" if classes["PACK_E_IMPROVED"] > classes["PACK_E_WORSENED"] else "NO_EVALUABLE_DIFFERENCE"
        rows.append({
            "provider": provider,
            "complete_forecast_pairs": sum(1 for row in complete if row["provider"] == provider),
            "evaluable_pairs": len(provider_eval),
            "pack_a_overall_accuracy": _accuracy(provider_eval, "pack_a_overall_ok"),
            "pack_e_overall_accuracy": _accuracy(provider_eval, "pack_e_overall_ok"),
            "pack_a_directions": [row["pack_a_direction"] for row in provider_eval],
            "pack_e_directions": [row["pack_e_direction"] for row in provider_eval],
            "pack_a_no_signal_count": sum(1 for row in provider_eval if row["pack_a_no_signal_flag"]),
            "pack_e_no_signal_count": sum(1 for row in provider_eval if row["pack_e_no_signal_flag"]),
            "descriptive_conclusion": conclusion,
            "stable_provider_characteristic_claimed": False,
        })
    return rows


def _session_comparison(complete: Sequence[Mapping[str, Any]], evaluable: Sequence[Mapping[str, Any]], session_decisions: Mapping[str, Mapping[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for session_id in TARGET_SESSIONS:
        session_eval = [row for row in evaluable if row["session_id"] == session_id]
        rows.append({
            "session_id": session_id,
            "complete_forecast_pairs": sum(1 for row in complete if row["session_id"] == session_id),
            "outcome_status": session_decisions[session_id]["status"],
            "evaluable_pairs": len(session_eval),
            "provider_results": {row["provider"]: row["paired_result_classification"] for row in session_eval},
            "exclusion_reason": session_decisions[session_id]["reason"],
        })
    return rows


def _self_tests() -> List[Dict[str, str]]:
    tests: List[Dict[str, str]] = []
    def record(name: str, condition: bool) -> None:
        tests.append({"test": name, "status": "PASS" if condition else "FAIL"})
        if not condition:
            raise CompletionBlocked("SELF_TEST_FAILED:" + name)
    exposure = _pack_a_context()
    record("pack_a_zero_exposure", exposure["pack_selected"] == "NO_PACK" and not exposure["assigned_market_state_context"] and not exposure["pack_e_exposure"])
    sample = {"user": "BASE", "system": "S", "instruction": "I", "cache_scaffold": ""}
    record("schema_clarification_equivalence", _prompt_without_clarification(_clarified_prompt(sample)) == sample)
    record("strength_tolerance_reused", _strength_ok(12.0, 10, 20) == "TRUE" and _strength_ok(2.5, 10, 20) == "FALSE")
    record("paired_degradation", _paired_classification({"overall_ok": True}, {"overall_ok": False}) == "PACK_E_WORSENED")
    record("paired_improvement", _paired_classification({"overall_ok": False}, {"overall_ok": True}) == "PACK_E_IMPROVED")
    return tests


def run(args: argparse.Namespace) -> Dict[str, Any]:
    run_id = args.run_id or _run_id()
    output_dir = OUTPUT_ROOT / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    generated_ts = _iso_now()
    tests = _self_tests()

    frozen_pack = load_frozen_true_shared_pack_e(FREEZE_MANIFEST)
    if frozen_pack["pack_fingerprint"] != EXPECTED_PACK_FINGERPRINT:
        raise CompletionBlocked("FROZEN_PACK_E_FINGERPRINT_MISMATCH")
    contexts = [render_frozen_true_shared_pack_e_context(frozen_pack, session_id) for session_id in sorted({row["session_id"] for row in frozen_pack["pack_rows"]})]
    if content_fingerprint(contexts) != EXPECTED_RENDERED_FINGERPRINT:
        raise CompletionBlocked("FROZEN_PACK_E_RENDERED_FINGERPRINT_MISMATCH")
    original_a, original_e, capture_summary = _load_authoritative_capture()

    creds = load_credentials()
    sheets_service = build_sheets_service(creds)
    script_service = build_script_service(creds)
    repaired_a, repair_prompt_audit, openai_config, eligibility = _repair_openai_pack_a(
        sheets_service, script_service, default_script_id(), frozen_pack, run_id
    )
    provider_config, schema_rows, _, _ = _load_prompt_configuration(sheets_service)
    for row in repaired_a:
        if row["status"] == "CAPTURED":
            validation = _response_validation(row["raw_output"], row["session_id"], "OpenAI", OPENAI_MODEL, "A", schema_rows)
            if not validation["ok"]:
                raise CompletionBlocked("REPAIRED_OPENAI_RESPONSE_REVALIDATION_FAILED")

    complete, incomplete, selected = _consolidate_pairs(original_a, original_e, repaired_a, provider_config, run_id)
    # Forecast population is frozen on disk before canonical outcomes are loaded.
    _write_jsonl(output_dir / "openai_pack_a_repair_results.jsonl", repaired_a)
    _write_jsonl(output_dir / "openai_pack_a_repair_prompt_audit.jsonl", repair_prompt_audit)
    _write_jsonl(output_dir / "authoritative_matched_forecast_pairs.jsonl", complete)
    _write_jsonl(output_dir / "incomplete_forecast_pairs.jsonl", incomplete)
    forecast_freeze = {
        "completion_run_id": run_id,
        "freeze_timestamp": _iso_now(),
        "complete_pair_count": len(complete),
        "incomplete_pair_count": len(incomplete),
        "logical_fingerprint": _sha(complete),
        "canonical_outcomes_loaded_before_freeze": False,
    }
    _write_json(output_dir / "authoritative_forecast_population_freeze.json", forecast_freeze)

    # Separation point: canonical outcome data is loaded only after forecast freeze.
    base_canonical = _sheet_to_rows(sheets_service, DIAGNOSTICS_SPREADSHEET_ID, "Market_Reaction_Canonical_Outcomes")
    canonical_rows, override_manifest = _load_canonical_overrides(base_canonical, CANONICAL_OVERRIDE_MANIFEST)
    candidates, _ = _build_candidates(sheets_service, frozen_pack)
    attachment_audit, session_decisions = _attach_outcomes(complete, candidates, canonical_rows, run_id)
    evaluable, unevaluable = _build_evaluation_rows(complete, attachment_audit, session_decisions, run_id)
    for row in incomplete:
        unevaluable.append({
            "completion_run_id": run_id,
            "session_id": row["session_id"],
            "provider": row["provider"],
            "pair_status": row["pair_status"],
            "evaluation_status": "REMAINS_UNEVALUABLE",
            "exclusion_reason": ";".join(row["exclusion_reasons"]),
        })
    metrics = _metrics(complete, incomplete, evaluable, [row for row in unevaluable if row.get("pair_status") == "COMPLETE_A_AND_E_PAIR"])
    provider_rows = _provider_comparison(complete, evaluable)
    session_rows = _session_comparison(complete, evaluable, session_decisions)
    classes = metrics["paired_classifications"]
    if not evaluable:
        scientific = "INSUFFICIENT_EXACT_EVALUATION_POPULATION"
        roadmap = "CONTINUE_PROSPECTIVE_COLLECTION"
    elif classes["PACK_E_WORSENED"] > classes["PACK_E_IMPROVED"]:
        scientific = "PRELIMINARY_PACK_E_DEGRADATION"
        roadmap = "INVESTIGATE_PACK_CONTENT_EFFECTS"
    elif classes["PACK_E_IMPROVED"] > classes["PACK_E_WORSENED"]:
        scientific = "PRELIMINARY_PACK_E_IMPROVEMENT"
        roadmap = "PROCEED_TO_REPLICATION"
    else:
        scientific = "PRELIMINARY_MIXED_OR_NO_EFFECT"
        roadmap = "INVESTIGATE_PACK_CONTENT_EFFECTS"

    _write_jsonl(output_dir / "exact_outcome_attachment_audit.jsonl", attachment_audit)
    _write_jsonl(output_dir / "evaluable_paired_rows.jsonl", evaluable)
    _write_jsonl(output_dir / "unevaluable_paired_rows.jsonl", unevaluable)
    _write_jsonl(output_dir / "provider_comparison.jsonl", provider_rows)
    _write_jsonl(output_dir / "session_comparison.jsonl", session_rows)
    _write_json(output_dir / "pack_a_vs_e_metrics.json", metrics)
    interpretation = {
        "scientific_interpretation": scientific,
        "roadmap_decision": roadmap,
        "statistical_significance_claimed": False,
        "unique_evaluable_sessions": metrics["unique_evaluable_sessions"],
        "provider_session_pairs": len(evaluable),
        "independence_limitation": "Provider rows from one session are not independent market observations.",
    }
    _write_json(output_dir / "scientific_interpretation.json", interpretation)

    summary = {
        "build_status": "PASS",
        "final_execution_decision": "PHASE9_PRIMARY_PAIRED_EVALUATION_COMPLETE",
        "completion_run_id": run_id,
        "scientific_interpretation": scientific,
        "roadmap_decision": roadmap,
        "authoritative_forecast_capture_run": CAPTURE_RUN_ID,
        "openai_repair_run": run_id + "-OPENAI-PACK-A-REPAIR",
        "frozen_pack_e_run": PACK_E_RUN_ID,
        "canonical_outcome_run": CANONICAL_REPAIR_RUN_ID,
        "openai_pack_a_arms_attempted": 2,
        "openai_pack_a_arms_repaired": sum(1 for row in repaired_a if row["status"] == "CAPTURED"),
        "openai_pack_a_arms_remaining_invalid": sum(1 for row in repaired_a if row["status"] != "CAPTURED"),
        "metrics": metrics,
        "may_19_status": session_decisions[TARGET_SESSIONS[0]]["status"],
        "may_20_status": session_decisions[TARGET_SESSIONS[1]]["status"],
        "tests": tests,
        "forecast_population_fingerprint": forecast_freeze["logical_fingerprint"],
        "evaluable_population_fingerprint": _sha(evaluable),
        "scientific_content_changed": False,
        "pack_content_changed": False,
        "canonical_outcome_values_changed": False,
        "scientific_rules_changed": False,
        "production_or_consumer_changes": False,
    }
    _write_json(output_dir / "completion_summary.json", summary)
    output_fingerprints = {
        name: hashlib.sha256((output_dir / name).read_bytes()).hexdigest()
        for name in (
            "openai_pack_a_repair_results.jsonl",
            "authoritative_matched_forecast_pairs.jsonl",
            "incomplete_forecast_pairs.jsonl",
            "exact_outcome_attachment_audit.jsonl",
            "evaluable_paired_rows.jsonl",
            "unevaluable_paired_rows.jsonl",
            "provider_comparison.jsonl",
            "session_comparison.jsonl",
            "pack_a_vs_e_metrics.json",
            "scientific_interpretation.json",
            "completion_summary.json",
        )
    }
    manifest = {
        "completion_run_id": run_id,
        "generated_ts": generated_ts,
        "schema_version": "phase9_pack_a_vs_frozen_pack_e_completion_v0.1",
        "shadow_only": True,
        "source_forecast_run": CAPTURE_RUN_ID,
        "source_pack_e_manifest": str(FREEZE_MANIFEST),
        "source_pack_e_fingerprint": EXPECTED_PACK_FINGERPRINT,
        "source_canonical_repair_manifest": str(CANONICAL_OVERRIDE_MANIFEST),
        "source_canonical_run": CANONICAL_IMPLEMENTATION_RUN_ID,
        "canonical_override_manifest_fingerprint": _sha(override_manifest),
        "forecast_population_frozen_before_outcome_load": True,
        "output_fingerprints": output_fingerprints,
        "aggregate_logical_fingerprint": _sha(output_fingerprints),
        "deterministic_reconstruction_fingerprint": _sha(output_fingerprints),
        "provider_calls": {"OpenAI_Pack_A": 2, "all_successful_arms_rerun": 0},
    }
    _write_json(output_dir / "completion_manifest.json", manifest)
    return summary


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Complete the Phase 9 Pack A versus frozen true Pack E experiment.")
    parser.add_argument("--run-id", default="")
    return parser.parse_args(argv)


def main() -> None:
    args = _parse_args()
    try:
        result = run(args)
    except Exception as exc:
        print(json.dumps({"build_status": "BLOCKED", "error": str(exc)}, ensure_ascii=True, indent=2))
        raise
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
