#!/usr/bin/env python3
"""Run one frozen, lineage-valid v2.1 Event-Path Pack A/E pair.

This is intentionally a single-pair validation runner.  It reads the Step 5
compatibility artifacts, uses the existing Apps Script provider bridge for at
most two independent calls, and attaches an Outcome only after both forecasts
have been frozen.  It does not write a workbook or Google Sheet.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Callable, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import presignal_v21_event_path_contract_v1_1 as contract
from automation.build_presignal_v21_event_path_inputs import reject_leakage
from automation.google_clients import build_script_service, default_script_id, load_credentials, run_script_function

STEP5 = ROOT / "outputs" / "presignal_v21_step5_reuse"
PREVALIDATION_POINTER = ROOT / "outputs" / "presignal_v21_pure_prediction_historical_baseline" / "latest_prevalidation_manifest.json"
OUTPUT_ROOT = ROOT / "outputs" / "presignal_v21_step6_single_pair_v1_1"
BRIDGE_FUNCTION = "apiCallAuthoritativeProviderJsonObject"
BRIDGE_SCHEMA_VERSION = "authoritative_historical_replay_bridge_v1"
PROMPT_VERSION = "presignal_event_path_contract_v1_1_single_pair_validation"
FUTURE_NO_SIGNAL_PROMPT_VERSION = "presignal_event_path_contract_v1_1_single_pair_validation_no_signal_confidence_explicit_v1"
FUTURE_NO_SIGNAL_CONFIDENCE_SENTENCE = (
    "Even when no_signal_flag is true, confidence must be a numeric value from 0 to 1 and must not be null. "
)
ALLOWED_PROMPT_DIFFERENCES = {
    "information_arm",
    "information_pack",
    "information_pack_fingerprint",
}


class Step6Error(RuntimeError):
    """A narrow Step 6 invariant could not be satisfied."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise Step6Error("MISSING_ARTIFACT:" + str(path))
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise Step6Error("MISSING_ARTIFACT:" + str(path))
    return json.loads(path.read_text())


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def write_jsonl(path: Path, values: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("".join(canonical_json(row) + "\n" for row in values))
    os.replace(temporary, path)


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def pair_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (str(row["episode_id"]), str(row["provider"]), str(row["model"]))


def resolve_v1_1_outcomes_path(prevalidation_manifest: Path | None = None, outcomes_path: Path | None = None) -> Path:
    if outcomes_path is not None:
        return outcomes_path
    manifest_path = prevalidation_manifest or PREVALIDATION_POINTER
    manifest = read_json(manifest_path)
    if manifest.get("contract_version") != contract.CONTRACT_VERSION or manifest.get("schema_version") != contract.SCHEMA_VERSION:
        raise Step6Error("PREVALIDATION_MANIFEST_VERSION_MISMATCH")
    relative = manifest.get("outcomes_v1_1_path")
    if not isinstance(relative, str) or not relative:
        raise Step6Error("PREVALIDATION_MANIFEST_OUTCOMES_PATH_MISSING")
    path = ROOT / relative
    if path == ROOT / "outputs" / "presignal_v21_episode_outcomes" / "outcome_rows.jsonl":
        raise Step6Error("LEGACY_OUTCOME_FALLBACK_FORBIDDEN")
    return path


def load_v1_1_outcomes(path: Path) -> list[dict[str, Any]]:
    rows = read_jsonl(path)
    if not rows:
        raise Step6Error("OUTCOME_SET_EMPTY")
    versions = {(row.get("schema_version"), row.get("system_version")) for row in rows}
    if versions != {(contract.SCHEMA_VERSION, contract.SYSTEM_VERSION)}:
        raise Step6Error("OUTCOME_SET_VERSION_MISMATCH:" + canonical_json(sorted(list(versions))))
    for row in rows:
        if row.get("object") != "OUTCOME":
            raise Step6Error("OUTCOME_SET_OBJECT_MISMATCH")
        if "immediate_impulse_outcome_state" not in row:
            raise Step6Error("OUTCOME_SET_IMMEDIATE_IMPULSE_FIELD_MISSING")
        contract.validate_outcome(row)
    return rows


def normalized_attention(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Keep original member-level evidence, without sending raw response blobs."""
    fields = (
        "event_id", "indicator_name", "attention_label", "attention_rank",
        "attention_reason", "expected_market_channel", "driver_role", "confidence",
        "attention_run_id", "session_id", "provider", "model", "forecast_cutoff_ts",
    )
    return [
        {field: row.get(field) for field in fields}
        for row in sorted(rows, key=lambda item: (str(item.get("event_id")), int(item.get("attention_rank") or 999999)))
    ]


def eligible_candidates(
    inputs_a: list[Mapping[str, Any]], inputs_e: list[Mapping[str, Any]], outcomes: list[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return all assessed pairs and the eligible ordered population.

    Availability is the only Outcome property used here.  No prices, directions,
    magnitudes, or scores participate in selection.
    """
    a_by_key = {pair_key(row): row for row in inputs_a}
    e_by_key = {pair_key(row): row for row in inputs_e}
    outcomes_by_episode = {row["episode_id"]: row for row in outcomes if row.get("status") == "VALID"}
    assessed: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []
    for key in sorted(set(a_by_key) | set(e_by_key)):
        arm_a, arm_e = a_by_key.get(key), e_by_key.get(key)
        reasons: list[str] = []
        if not arm_a or not arm_e:
            reasons.append("MISSING_PACK_A_OR_PACK_E")
        if arm_a and not arm_a.get("information_requests"):
            reasons.append("PACK_A_EMPTY")
        pack_e = arm_e.get("shared_market_state_pack") if arm_e else None
        if not isinstance(pack_e, Mapping) or not pack_e.get("items"):
            reasons.append("PACK_E_EMPTY")
        if arm_a and arm_e and canonical_json(arm_a.get("shared_market_state_pack")) == canonical_json(pack_e):
            reasons.append("PACK_ARMS_NOT_DISTINCT")
        if key[0] not in outcomes_by_episode:
            reasons.append("OUTCOME_NOT_AVAILABLE")
        attention = list((arm_a or {}).get("provider_attention_map") or [])
        members = list((arm_a or {}).get("episode_members") or [])
        member_ids = {row.get("event_id") for row in members}
        attention_ids = {row.get("event_id") for row in attention}
        if not attention or attention_ids != member_ids:
            reasons.append("ATTENTION_MEMBER_LINEAGE_INCOMPLETE")
        if any(row.get("status") != "parsed" for row in attention):
            reasons.append("ATTENTION_ERROR_OR_OMISSION")
        if arm_a and arm_a.get("provider_episode_selection") != "FORECAST":
            # Step 6 validates an actual directional Event-Path forecast pair.
            # WATCH, IGNORE, and NO_SIGNAL are valid Step 5 outputs, but are not
            # a scientifically meaningful target for this forecast-pair check.
            reasons.append("EPISODE_NOT_SELECTED_FOR_FORECAST")
        variation = {
            "labels": len({row.get("attention_label") for row in attention}),
            "ranks": len({row.get("attention_rank") for row in attention}),
            "reasons": len({row.get("attention_reason") for row in attention}),
            "channels": len({row.get("expected_market_channel") for row in attention}),
        }
        candidate = {
            "episode_id": key[0], "provider": key[1], "model": key[2],
            "member_count": len(members), "same_time_cluster_flag": len(members) > 1,
            "attention_variation": variation, "eligible": not reasons,
            "ineligibility_reasons": sorted(reasons),
            "pack_a_input_fingerprint": (arm_a or {}).get("input_fingerprint"),
            "pack_e_input_fingerprint": (arm_e or {}).get("input_fingerprint"),
            "pack_a_fingerprint": (arm_a or {}).get("pack_fingerprint"),
            "pack_e_fingerprint": (arm_e or {}).get("pack_fingerprint"),
        }
        assessed.append(candidate)
        if not reasons:
            candidate["preference"] = {
                "multi_member": len(members) > 1,
                "attention_variation": any(value > 1 for value in variation.values()),
            }
            eligible.append(candidate)
    # The documented preference deliberately stops before outcome characteristics.
    eligible.sort(key=lambda row: (
        not row["preference"]["multi_member"],
        not row["preference"]["attention_variation"],
        row["episode_id"], row["provider"], row["model"],
    ))
    return assessed, eligible


def arm_context(row: Mapping[str, Any]) -> dict[str, Any]:
    arm = str(row["information_arm"])
    if arm not in {"PACK_A", "PACK_E"}:
        raise Step6Error("UNEXPECTED_STEP5_ARM:" + arm)
    prompt_arm = "BASELINE" if arm == "PACK_A" else "FULL_CONTEXT"
    context = {
        "object": "presignal_event_path_contract_v1_1_forecast_request",
        "system_version": contract.SYSTEM_VERSION,
        "contract_version": contract.CONTRACT_VERSION,
        "schema_version": contract.SCHEMA_VERSION,
        "information_arm": prompt_arm,
        "information_pack_fingerprint": None if prompt_arm == "BASELINE" else row["pack_fingerprint"],
        "information_pack": None if prompt_arm == "BASELINE" else row["shared_market_state_pack"],
        "episode": {
            "episode_id": row["episode_id"], "source_session_id": row["source_session_id"],
            "country": row["country"], "release_ts": row["release_ts"],
            "forecast_cutoff_ts": row["forecast_cutoff_ts"],
            "members": [{"event_id": item["event_id"], "indicator_name": item["indicator_name"]} for item in row["episode_members"]],
            "structural_component_roles": row["structural_component_roles"],
        },
        "attention_evidence": normalized_attention(list(row["provider_attention_map"])),
        "information_requests": row["information_requests"],
        "required_horizons_min": list(contract.HORIZONS),
        "response_contract_version": contract.CONTRACT_VERSION,
    }
    reject_leakage(context)
    return context


def prompt_instruction_text(
    *,
    include_future_no_signal_confidence_clarification: bool = False,
) -> str:
    no_signal_confidence_sentence = (
        FUTURE_NO_SIGNAL_CONFIDENCE_SENTENCE
        if include_future_no_signal_confidence_clarification
        else ""
    )
    return (
        "You are producing a PreSignal v2.1 Event-Path forecast. Reason only from the supplied "
        "frozen pre-release information. Do not use released actual values, subsequent prices, Outcomes, "
        "Evaluation, prior forecasts, or external/current information. Structural component roles are neutral "
        "organization metadata, not causal truth. Interpret all same-time members jointly using the preserved "
        "member-level Attention evidence. Immediate Impulse is defined by PreSignal as the first meaningful persistent "
        "USD/JPY movement during the fixed T through T+120-second window. Do not select or alter this duration; the "
        "local system owns that protocol metadata. Return one strict JSON object with exactly these top-level keys, and no "
        "wrapper or metadata keys: no_signal_flag, no_signal_reason, confidence, immediate_impulse_direction, "
        "immediate_impulse_peak_pips_min, immediate_impulse_peak_pips_max, immediate_impulse_confidence, "
        "early_reaction_5m_direction, expected_reversal_flag, "
        "expected_reversal_horizon_min, expected_path_summary, information_used, missing_information, "
        "invalidation_condition, path. early_reaction_5m_direction is the EARLY_REACTION_5M forecast and must equal "
        "the 5-minute path direction. immediate_impulse_* is a separate first-persistent-move sidecar for the fixed 120-second target. "
        "If you include immediate_impulse_window_seconds, the only valid value is 120; omission is allowed because the system inserts the fixed protocol value. "
        "NO_SIGNAL is appropriate only when no defensible directional hypothesis can be formed from the supplied frozen "
        "historical information. Uncertainty alone does not require NO_SIGNAL; if one direction is more defensible than "
        "the alternatives, return a directional forecast with the appropriately lower confidence. Missing optional context "
        "does not by itself require NO_SIGNAL. "
        "Confidence is always a number from 0 to 1. "
        + no_signal_confidence_sentence +
        "For a "
        "normal forecast, path contains exactly ordered 5, 15, 30, 60 minute rows, each with horizon_min, "
        "expected_direction, expected_pips_min, expected_pips_max, stage_confidence, continuation_probability, "
        "reversal_probability, stage_reason, invalidation_condition. Directions are UP, DOWN, or FLAT. Pip bounds "
        "are nonnegative absolute magnitudes with minimum less than or equal to maximum. If expected_direction is FLAT, "
        "expected_pips_min must be 0 and expected_pips_max must be 0. If a nonzero net move is expected, choose UP or DOWN "
        "rather than FLAT and provide a nonnegative absolute pip range consistent with that direction. Valid examples: "
        "UP with 2 to 8 pips, DOWN with 3 to 9 pips, FLAT with 0 to 0 pips. "
        "For reversal fields: if expected_reversal_flag is true, expected_reversal_horizon_min must be exactly 15, 30, or 60. "
        "If expected_reversal_flag is false, expected_reversal_horizon_min must be null. "
        "For no signal, immediate_impulse_* fields are null, early_reaction_5m_direction is UNCERTAIN, reversal fields are null, and path is empty."
    )


def prompt_text(
    context: Mapping[str, Any],
    *,
    include_future_no_signal_confidence_clarification: bool = False,
) -> str:
    return (
        prompt_instruction_text(
            include_future_no_signal_confidence_clarification=include_future_no_signal_confidence_clarification,
        )
        + "\n\n"
        + canonical_json(context)
    )


def future_prompt_text(context: Mapping[str, Any]) -> str:
    return prompt_text(
        context,
        include_future_no_signal_confidence_clarification=True,
    )


def prompt_text_fingerprint(prompt: str) -> str:
    return sha256(prompt)


def prompt_instruction_fingerprint(
    *,
    include_future_no_signal_confidence_clarification: bool = False,
) -> str:
    return prompt_text_fingerprint(
        prompt_instruction_text(
            include_future_no_signal_confidence_clarification=include_future_no_signal_confidence_clarification,
        )
    )


def prompt_diff(context_a: Mapping[str, Any], context_e: Mapping[str, Any]) -> dict[str, Any]:
    paths: list[str] = []

    def compare(left: Any, right: Any, path: str = "") -> None:
        if isinstance(left, Mapping) and isinstance(right, Mapping):
            for key in sorted(set(left) | set(right)):
                compare(left.get(key), right.get(key), key if not path else path + "." + key)
        elif left != right:
            paths.append(path)

    compare(context_a, context_e)
    passed = set(paths) <= ALLOWED_PROMPT_DIFFERENCES
    return {"differences": paths, "allowed_differences": sorted(ALLOWED_PROMPT_DIFFERENCES), "passed": passed}


def parse_provider_output(raw_output: Any) -> dict[str, Any]:
    return normalize_provider_output(raw_output)[0]


def repair_missing_path_boundary(text: str) -> tuple[str, dict[str, Any]]:
    """Restore one provable path-object delimiter without changing values."""
    path_marker = re.search(r'"path"\s*:\s*\[', text)
    if not path_marker:
        return text, {"status": "NOT_APPLICABLE", "candidate_count": 0}

    path_text = text[path_marker.end():]
    boundary = re.compile(
        r'("invalidation_condition"\s*:\s*"(?:\\.|[^"\\])*")\s*,\s*("horizon_min"\s*:)'
    )
    candidates = list(boundary.finditer(path_text))
    if len(candidates) == 0:
        return text, {"status": "NO_REPAIR_POSITION", "candidate_count": 0}
    if len(candidates) != 1:
        raise Step6Error("PROVIDER_OUTPUT_PATH_BOUNDARY_AMBIGUOUS")

    match = candidates[0]
    replacement = (
        match.group(1)
        + "\n    },\n    {\n      \"horizon_min\":"
    )
    repaired_path = path_text[:match.start()] + replacement + path_text[match.end():]
    return text[:path_marker.end()] + repaired_path, {
        "status": "REPAIRED_ONE_STRUCTURAL_BOUNDARY",
        "candidate_count": 1,
        "match_start": path_marker.end() + match.start(),
        "match_end": path_marker.end() + match.end(),
        "transformation": "INSERT_MISSING_PATH_OBJECT_BOUNDARY_BEFORE_SECOND_HORIZON_MIN",
    }


def normalize_provider_output(raw_output: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    parsed_source: Mapping[str, Any] | None
    if isinstance(raw_output, Mapping):
        parsed_source = raw_output
        result = dict(raw_output)
    elif isinstance(raw_output, str):
        text = raw_output.strip()
        if text.startswith("```") and text.endswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        text, repair_audit = repair_missing_path_boundary(text)
        try:
            result = json.loads(text)
        except json.JSONDecodeError as exc:
            raise Step6Error("PROVIDER_OUTPUT_NOT_JSON") from exc
        parsed_source = result if isinstance(result, Mapping) else None
    else:
        raise Step6Error("PROVIDER_OUTPUT_NOT_OBJECT")
    # Gemini returned the requested forecast in its explicit response-contract
    # envelope. This is transport formatting, not a second scientific schema.
    if set(result) == {"forecast", "response_contract"}:
        if not isinstance(result["forecast"], Mapping) or not isinstance(result["response_contract"], Mapping):
            raise Step6Error("PROVIDER_OUTPUT_ENVELOPE")
        parsed_source = result["forecast"]
        result = dict(result["forecast"])
    elif not isinstance(result, Mapping):
        raise Step6Error("PROVIDER_OUTPUT_NOT_OBJECT")
    transport_fields = {
        "object", "system_version", "schema_version", "response_contract", "forecast_cutoff_ts",
        "information_pack_fingerprint", "market_state_snapshot_fingerprint", "population_type",
        "rendered_context_fingerprint", "retrospective_simulation_flag", "session_id",
        "model_weight_leakage_not_eliminable",
    }
    required = {
        "no_signal_flag", "no_signal_reason", "confidence", "immediate_impulse_direction",
        "immediate_impulse_peak_pips_min", "immediate_impulse_peak_pips_max", "immediate_impulse_confidence",
        "early_reaction_5m_direction",
        "expected_reversal_flag", "expected_reversal_horizon_min", "expected_path_summary",
        "information_used", "missing_information", "invalidation_condition", "path",
    }
    window_field = "immediate_impulse_window_seconds"
    unexpected = set(result) - required - transport_fields - {window_field}
    missing = required - set(result)
    if unexpected or missing:
        raise Step6Error("PROVIDER_OUTPUT_FIELDS:" + canonical_json(sorted(unexpected | missing)))
    result = {key: result[key] for key in required}
    provider_window_present = isinstance(parsed_source, Mapping) and window_field in parsed_source
    provider_window_raw = parsed_source.get(window_field) if provider_window_present else None
    if not provider_window_present:
        provider_window_status = "OMITTED"
    elif isinstance(provider_window_raw, (int, float)) and not isinstance(provider_window_raw, bool):
        provider_window_status = "MATCHED_PROTOCOL" if float(provider_window_raw) == float(contract.IMMEDIATE_IMPULSE_WINDOW_SECONDS_DEFAULT) else "OVERRIDDEN_BY_PROTOCOL"
    else:
        provider_window_status = "INVALID_TYPE"
    audit = {
        "immediate_window_source": "SYSTEM_PROTOCOL",
        "provider_immediate_window_status": provider_window_status,
        "provider_returned_immediate_window_seconds": provider_window_raw if provider_window_present else None,
        "canonical_immediate_window_seconds": contract.IMMEDIATE_IMPULSE_WINDOW_SECONDS_DEFAULT,
        "path_boundary_repair": repair_audit if isinstance(raw_output, str) else {"status": "NOT_APPLICABLE"},
    }
    result[window_field] = contract.IMMEDIATE_IMPULSE_WINDOW_SECONDS_DEFAULT
    if not isinstance(result["no_signal_flag"], bool) or not isinstance(result["confidence"], (int, float)):
        raise Step6Error("PROVIDER_OUTPUT_TYPES")
    if not 0 <= float(result["confidence"]) <= 1:
        raise Step6Error("PROVIDER_OUTPUT_CONFIDENCE")
    if result["no_signal_flag"]:
        if any(result[key] is not None for key in ("immediate_impulse_direction", "immediate_impulse_peak_pips_min", "immediate_impulse_peak_pips_max", "immediate_impulse_confidence")):
            raise Step6Error("PROVIDER_OUTPUT_NO_SIGNAL_IMMEDIATE_IMPULSE")
        if result["early_reaction_5m_direction"] != "UNCERTAIN" or result["path"]:
            raise Step6Error("PROVIDER_OUTPUT_NO_SIGNAL_PATH")
        return result, audit
    if result["immediate_impulse_direction"] not in {"UP", "DOWN", "FLAT"}:
        raise Step6Error("PROVIDER_OUTPUT_IMMEDIATE_DIRECTION")
    for key in ("immediate_impulse_peak_pips_min", "immediate_impulse_peak_pips_max", "immediate_impulse_confidence"):
        if not isinstance(result[key], (int, float)):
            raise Step6Error("PROVIDER_OUTPUT_IMMEDIATE_TYPES")
    if not 0 <= float(result["immediate_impulse_confidence"]) <= 1:
        raise Step6Error("PROVIDER_OUTPUT_IMMEDIATE_CONFIDENCE")
    if float(result["immediate_impulse_peak_pips_min"]) > float(result["immediate_impulse_peak_pips_max"]):
        raise Step6Error("PROVIDER_OUTPUT_IMMEDIATE_RANGE")
    if result["early_reaction_5m_direction"] not in {"UP", "DOWN", "FLAT"}:
        raise Step6Error("PROVIDER_OUTPUT_INITIAL_DIRECTION")
    paths = result["path"]
    if not isinstance(paths, list) or len(paths) != len(contract.HORIZONS):
        raise Step6Error("PROVIDER_OUTPUT_PATH_COUNT")
    required_stage = {
        "horizon_min", "expected_direction", "expected_pips_min", "expected_pips_max", "stage_confidence",
        "continuation_probability", "reversal_probability", "stage_reason", "invalidation_condition",
    }
    if any(not isinstance(stage, Mapping) or set(stage) != required_stage for stage in paths):
        raise Step6Error("PROVIDER_OUTPUT_PATH_FIELDS")
    if [stage["horizon_min"] for stage in paths] != list(contract.HORIZONS):
        raise Step6Error("PROVIDER_OUTPUT_HORIZONS")
    if paths[0]["expected_direction"] != result["early_reaction_5m_direction"]:
        raise Step6Error("PROVIDER_OUTPUT_EARLY_REACTION_BINDING")
    return result, audit


def response_to_contract(
    response: Mapping[str, Any], input_row: Mapping[str, Any], *, run_id: str, created_ts: str,
    raw_output: Any, bridge_result: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    arm = "BASELINE" if input_row["information_arm"] == "PACK_A" else "FULL_CONTEXT"
    pack_id = "BASELINE_NO_PACK" if arm == "BASELINE" else str(input_row["pack_id"])
    pack_fingerprint = None if arm == "BASELINE" else input_row["pack_fingerprint"]
    primary = next((member["event_id"] for member in input_row["episode_members"] if member.get("structural_component_role") == "STRUCTURAL_PRIMARY"), input_row["episode_members"][0]["event_id"])
    secondary = [member["event_id"] for member in input_row["episode_members"] if member.get("structural_component_role") == "STRUCTURAL_SECONDARY"]
    prediction = {
        "object": "PREDICTION", "schema_version": contract.SCHEMA_VERSION, "system_version": contract.SYSTEM_VERSION,
        "run_id": run_id, "prediction_id": "", "episode_id": input_row["episode_id"], "session_id": input_row["source_session_id"],
        "provider": input_row["provider"], "model": input_row["model"], "information_arm": arm,
        "pack_id": pack_id, "pack_fingerprint": pack_fingerprint, "forecast_created_ts": created_ts,
        "forecast_cutoff_ts": input_row["forecast_cutoff_ts"], "prediction_target_type": "EVENT_EPISODE",
        "prediction_target_id": input_row["episode_id"], "primary_event_id": primary, "secondary_event_ids": secondary,
        "no_signal_flag": response["no_signal_flag"], "no_signal_reason": response["no_signal_reason"],
        "confidence": float(response["confidence"]), "immediate_impulse_direction": response["immediate_impulse_direction"],
        "immediate_impulse_peak_pips_min": response["immediate_impulse_peak_pips_min"],
        "immediate_impulse_peak_pips_max": response["immediate_impulse_peak_pips_max"],
        "immediate_impulse_confidence": response["immediate_impulse_confidence"],
        "immediate_impulse_window_seconds": response["immediate_impulse_window_seconds"],
        "early_reaction_5m_direction": response["early_reaction_5m_direction"],
        "expected_reversal_flag": response["expected_reversal_flag"], "expected_reversal_horizon_min": response["expected_reversal_horizon_min"],
        "expected_path_summary": response["expected_path_summary"], "information_used": response["information_used"],
        "missing_information": response["missing_information"], "invalidation_condition": response["invalidation_condition"],
        "raw_output": raw_output, "prompt_tokens": bridge_result.get("prompt_tokens"),
        "completion_tokens": bridge_result.get("completion_tokens"), "latency_ms": bridge_result.get("latency_ms"),
        "prediction_fingerprint": "", "status": "NO_SIGNAL" if response["no_signal_flag"] else "VALID", "error_message": None,
    }
    prediction["prediction_id"] = contract.prediction_id_for(prediction)
    prediction["prediction_fingerprint"] = contract._fingerprint(prediction, "prediction_fingerprint", ("run_id", "forecast_created_ts", "prompt_tokens", "completion_tokens", "latency_ms", "status", "error_message"))
    paths: list[dict[str, Any]] = []
    for index, stage in enumerate(response["path"], start=1):
        path = {
            "object": "PREDICTION_PATH", "schema_version": contract.SCHEMA_VERSION, "system_version": contract.SYSTEM_VERSION,
            "run_id": run_id, "prediction_id": prediction["prediction_id"], "path_id": "", "episode_id": prediction["episode_id"],
            "provider": prediction["provider"], "model": prediction["model"], "information_arm": arm,
            "stage_index": index, "stage_type": "HORIZON", "target_type": "EVENT_EPISODE", "target_id": prediction["episode_id"],
            "horizon_min": stage["horizon_min"], "expected_direction": stage["expected_direction"],
            "expected_pips_min": stage["expected_pips_min"], "expected_pips_max": stage["expected_pips_max"],
            "stage_confidence": stage["stage_confidence"], "continuation_probability": stage["continuation_probability"],
            "reversal_probability": stage["reversal_probability"], "stage_reason": stage["stage_reason"],
            "invalidation_condition": stage["invalidation_condition"], "stage_fingerprint": "", "created_ts": created_ts,
            "status": "VALID", "error_message": None,
        }
        path["path_id"] = contract.path_id_for(path)
        path["stage_fingerprint"] = contract._fingerprint(path, "stage_fingerprint", ("run_id", "created_ts", "status", "error_message"))
        paths.append(path)
    contract.validate_prediction_path_transaction(prediction, paths)
    return prediction, paths


def evaluate(prediction: Mapping[str, Any], paths: list[Mapping[str, Any]], outcome: Mapping[str, Any], *, generated_ts: str) -> dict[str, Any]:
    by_horizon = {path["horizon_min"]: path for path in paths}
    unavailable = outcome["status"] == "UNAVAILABLE" or prediction["status"] == "PROVIDER_ERROR"
    if unavailable:
        directions = {horizon: None for horizon in contract.HORIZONS}
        immediate_result = "OUTCOME_UNAVAILABLE"
        immediate_range = None; immediate_distance = None; immediate_midpoint = None; false_initial = None
        t5_range = None; t5_distance = None; t5_midpoint = None; retention = None
        sustained = None; faded = None; reversed_t5 = None
        primary = None; magnitude = None; reversal = None; no_signal = None; score = None; status = "UNAVAILABLE"
    elif prediction["no_signal_flag"]:
        directions = {horizon: None for horizon in contract.HORIZONS}
        quiet = all(outcome[f"direction_{horizon}m"] == "FLAT" for horizon in contract.HORIZONS) and max(abs(outcome["max_up_pips"]), abs(outcome["max_down_pips"])) < contract.FLAT_MAX_ABS_PIPS
        immediate_result = "NOT_APPLICABLE"
        immediate_range = None; immediate_distance = None; immediate_midpoint = None; false_initial = None
        t5_range = None; t5_distance = None; t5_midpoint = None; retention = None
        sustained = None; faded = None; reversed_t5 = None
        primary = None; magnitude = None; reversal = None; no_signal = quiet; score = None; status = "VALID"
    else:
        directions = {horizon: by_horizon[horizon]["expected_direction"] == outcome[f"direction_{horizon}m"] for horizon in contract.HORIZONS}
        false_initial = outcome["false_initial_excursion_flag"]
        if outcome["immediate_impulse_outcome_state"] == "SUPPORTED":
            realized_impulse_abs = abs(outcome["initial_peak_pips"])
            immediate_result = "CORRECT" if prediction["immediate_impulse_direction"] == outcome["confirmed_initial_direction"] else "INCORRECT"
            immediate_range = prediction["immediate_impulse_peak_pips_min"] <= realized_impulse_abs <= prediction["immediate_impulse_peak_pips_max"]
            immediate_distance = contract._interval_error(realized_impulse_abs, prediction["immediate_impulse_peak_pips_min"], prediction["immediate_impulse_peak_pips_max"])
            immediate_midpoint = contract._midpoint_absolute_error(realized_impulse_abs, prediction["immediate_impulse_peak_pips_min"], prediction["immediate_impulse_peak_pips_max"])
        else:
            immediate_result = "NOT_APPLICABLE"
            immediate_range = None; immediate_distance = None; immediate_midpoint = None
        realized_5m_abs = abs(outcome["pips_5m"]); path5 = by_horizon[5]
        t5_range = path5["expected_pips_min"] <= realized_5m_abs <= path5["expected_pips_max"]
        t5_distance = contract._interval_error(realized_5m_abs, path5["expected_pips_min"], path5["expected_pips_max"])
        t5_midpoint = contract._midpoint_absolute_error(realized_5m_abs, path5["expected_pips_min"], path5["expected_pips_max"])
        retention = outcome["initial_peak_retention_at_t5"]
        confirmed = outcome["confirmed_initial_direction"]
        if confirmed in {"UP", "DOWN"} and retention is not None:
            opposite = {"UP": "DOWN", "DOWN": "UP"}[confirmed]
            sustained = outcome["direction_5m"] == confirmed
            reversed_t5 = outcome["direction_5m"] == opposite
            faded = not sustained and not reversed_t5
        else:
            sustained = None; faded = None; reversed_t5 = None
        primary = directions[15]
        realized_abs = abs(outcome["pips_15m"]); path15 = by_horizon[15]
        magnitude = 0.0 if path15["expected_pips_min"] <= realized_abs <= path15["expected_pips_max"] else min(abs(realized_abs - path15["expected_pips_min"]), abs(realized_abs - path15["expected_pips_max"]))
        reversal = prediction["expected_reversal_flag"] == outcome["reversal_flag"]
        no_signal = None; score = mean(directions.values()); status = "VALID"
    record = {
        "object": "EVALUATION", "schema_version": contract.SCHEMA_VERSION, "system_version": contract.SYSTEM_VERSION,
        "evaluation_id": "", "run_id": prediction["run_id"], "prediction_id": prediction["prediction_id"], "outcome_id": outcome["outcome_id"],
        "episode_id": prediction["episode_id"], "provider": prediction["provider"], "model": prediction["model"], "information_arm": prediction["information_arm"],
        "immediate_impulse_direction_result": immediate_result,
        "immediate_impulse_peak_range_covered": immediate_range,
        "immediate_impulse_peak_range_distance_error_pips": immediate_distance,
        "immediate_impulse_peak_midpoint_absolute_error_pips": immediate_midpoint,
        "false_initial_excursion_observed": false_initial,
        **{f"direction_{horizon}m_ok": directions[horizon] for horizon in contract.HORIZONS},
        "t5_range_covered": t5_range,
        "t5_range_distance_error_pips": t5_distance,
        "t5_midpoint_absolute_error_pips": t5_midpoint,
        "initial_peak_retention_at_t5": retention,
        "initial_impulse_sustained_to_t5": sustained,
        "initial_impulse_faded_by_t5": faded,
        "initial_impulse_reversed_by_t5": reversed_t5,
        "magnitude_15m_error": magnitude, "reversal_ok": reversal, "no_signal_ok": no_signal,
        "primary_endpoint_name": "EPISODE_REACTION_DIRECTION_15M", "primary_endpoint_value": primary,
        "overall_path_score": score, "evaluation_note": "Single-pair pipeline validation only; not an A/E effect estimate.",
        "evaluation_contract_version": contract.CONTRACT_VERSION, "evaluation_fingerprint": "", "generated_ts": generated_ts,
        "status": status, "error_message": None,
    }
    record["evaluation_id"] = contract.evaluation_id_for(record)
    record["evaluation_fingerprint"] = contract._fingerprint(record, "evaluation_fingerprint", ("run_id", "generated_ts", "status", "error_message", "evaluation_note"))
    contract.validate_evaluation(record, prediction, outcome, paths)
    return record


def attention_adequacy(input_row: Mapping[str, Any]) -> dict[str, Any]:
    evidence = normalized_attention(list(input_row["provider_attention_map"]))
    members = {member["event_id"] for member in input_row["episode_members"]}
    labels = {row["event_id"]: row["attention_label"] for row in evidence}
    dominant = [row for row in evidence if row["attention_label"] == "PRIMARY_DRIVER"]
    if not dominant:
        dominant = sorted(evidence, key=lambda row: (int(row["attention_rank"] or 999999), row["event_id"]))[:1]
    sufficient = set(labels) == members and all(row.get("attention_reason") and row.get("expected_market_channel") for row in evidence)
    return {
        "episode_id": input_row["episode_id"], "provider": input_row["provider"], "model": input_row["model"],
        "member_attention_evidence": evidence, "episode_selected_as": input_row["provider_episode_selection"],
        "member_labels_and_ranks_available": len(evidence) == len(members), "dominant_member_identifiable": bool(dominant),
        "dominant_member_event_ids": [row["event_id"] for row in dominant],
        "joint_same_time_interpretation_supported": len(members) <= 1 or len(evidence) == len(members),
        "reinforcement_or_conflict_interpretable": len(members) <= 1 or bool({row.get("expected_market_channel") for row in evidence}),
        "reasons_and_channels_useful": all(row.get("attention_reason") and row.get("expected_market_channel") for row in evidence),
        "essential_episode_attention_concept_missing": [] if sufficient else ["complete_member_level_attention_evidence"],
        "would_episode_attention_field_materially_change_task": not sufficient,
        "decision": "ADEQUATE" if sufficient else "INADEQUATE",
        "rationale": "Preserved member labels, ranks, reasons, channels, and exact membership provide sufficient causal orientation without treating structural roles as causal truth." if sufficient else "A member lacks preserved original Attention orientation; a forecast would require unsupported inference.",
    }


def bridge_dispatch(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    credentials = load_credentials(False)
    service = build_script_service(credentials, 240)
    result = run_script_function(service, default_script_id(), BRIDGE_FUNCTION, [dict(payload)])
    if not isinstance(result, Mapping):
        raise Step6Error("BRIDGE_RESPONSE_NOT_OBJECT")
    return result


def bridge_payload(row: Mapping[str, Any], prompt: str, *, run_id: str, arm: str) -> dict[str, Any]:
    return {
        "provider": row["provider"], "model": row["model"], "prompt": {
            "system": "You are a disciplined historical event-path forecaster. Return strict JSON only.",
            "user": prompt, "instruction": "Follow the supplied frozen contract and information boundary.", "cache_scaffold": "",
        },
        "authoritative_run_id": run_id,
        "forecast_identity": "STEP6_" + hashlib.sha256((row["episode_id"] + "|" + row["provider"] + "|" + row["model"]).encode()).hexdigest()[:20],
        "arm": arm, "session_id": row["source_session_id"], "hard_timeout_seconds": 180,
        "request_schema_version": BRIDGE_SCHEMA_VERSION,
    }


def is_availability_failure(result: Mapping[str, Any]) -> bool:
    return str(result.get("status")) in {"provider_unavailable", "model_not_enforceable", "unsupported_provider", "configuration_error"}


def run(
    *,
    output_root: Path = OUTPUT_ROOT,
    dispatcher: Callable[[Mapping[str, Any]], Mapping[str, Any]] = bridge_dispatch,
    prevalidation_manifest: Path | None = None,
    outcomes_path: Path | None = None,
) -> tuple[Path, dict[str, Any]]:
    inputs_a = read_jsonl(STEP5 / "event_path_forecast_inputs_pack_a.jsonl")
    inputs_e = read_jsonl(STEP5 / "event_path_forecast_inputs_pack_e.jsonl")
    outcomes = load_v1_1_outcomes(resolve_v1_1_outcomes_path(prevalidation_manifest, outcomes_path))
    assessed, eligible = eligible_candidates(inputs_a, inputs_e, outcomes)
    if not eligible:
        raise Step6Error("NO_ELIGIBLE_STEP6_PAIR")
    run_id = "STEP6-SINGLE-" + now().replace(":", "").replace("-", "").replace(".", "")
    run_dir = output_root / run_id
    a_by_key, e_by_key = {pair_key(row): row for row in inputs_a}, {pair_key(row): row for row in inputs_e}
    outcome_by_episode = {row["episode_id"]: row for row in outcomes if row.get("status") == "VALID"}
    write_json(run_dir / "candidate_selection.json", {"criteria": ["exact lineage", "exact configured provider/model callable", "nonempty distinct Pack A/E", "available deterministic Outcome", "complete parsed member Attention", "multi-member preference", "attention-variation preference", "episode/provider/model tie-break"], "assessed_candidates": assessed, "eligible_count": len(eligible)})
    availability_attempts: list[dict[str, Any]] = []
    selected: tuple[dict[str, Any], Mapping[str, Any], Mapping[str, Any]] | None = None
    for candidate in eligible:
        key = (candidate["episode_id"], candidate["provider"], candidate["model"])
        arm_a, arm_e = a_by_key[key], e_by_key[key]
        # Deterministic arm order uses pair identity.  The first call doubles as exact-model availability test.
        identity_hash = hashlib.sha256("|".join(key).encode()).digest()[0]
        order = ["PACK_A", "PACK_E"] if identity_hash % 2 == 0 else ["PACK_E", "PACK_A"]
        contexts = {"PACK_A": arm_context(arm_a), "PACK_E": arm_context(arm_e)}
        diff = prompt_diff(contexts["PACK_A"], contexts["PACK_E"])
        if not diff["passed"]:
            raise Step6Error("PROMPT_SYMMETRY_FAILURE:" + canonical_json(diff["differences"]))
        first_arm = order[0]; first_row = arm_a if first_arm == "PACK_A" else arm_e
        first_payload = bridge_payload(first_row, prompt_text(contexts[first_arm]), run_id=run_id, arm="BASELINE" if first_arm == "PACK_A" else "FULL_CONTEXT")
        first_result = dispatcher(first_payload)
        availability_attempts.append({"candidate": candidate, "first_arm": first_arm, "bridge_status": first_result.get("status"), "actual_model": first_result.get("model")})
        if is_availability_failure(first_result):
            continue
        if first_result.get("status") != "ok" or first_result.get("actual_provider") != candidate["provider"] or first_result.get("actual_model") != candidate["model"]:
            raise Step6Error("EXACT_PROVIDER_MODEL_CALL_FAILED:" + canonical_json(first_result))
        selected = candidate, arm_a, arm_e
        first = (first_arm, first_result, first_payload, contexts, diff, order)
        break
    if selected is None:
        write_json(run_dir / "selected_pair.json", {"decision": "V2_1_STEP6_EXACT_PROVIDER_MODEL_UNAVAILABLE", "availability_attempts": availability_attempts})
        raise Step6Error("V2_1_STEP6_EXACT_PROVIDER_MODEL_UNAVAILABLE")
    candidate, arm_a, arm_e = selected
    first_arm, first_result, first_payload, contexts, diff, order = first
    by_arm = {"PACK_A": arm_a, "PACK_E": arm_e}
    responses: dict[str, Mapping[str, Any]] = {first_arm: first_result}
    payloads: dict[str, Mapping[str, Any]] = {first_arm: first_payload}
    for arm in order[1:]:
        payload = bridge_payload(by_arm[arm], prompt_text(contexts[arm]), run_id=run_id, arm="BASELINE" if arm == "PACK_A" else "FULL_CONTEXT")
        result = dispatcher(payload)
        if result.get("status") != "ok" or result.get("actual_provider") != candidate["provider"] or result.get("actual_model") != candidate["model"]:
            raise Step6Error("SECOND_ARM_EXACT_PROVIDER_MODEL_CALL_FAILED:" + canonical_json(result))
        payloads[arm], responses[arm] = payload, result
    # Preserve raw provider evidence before transport parsing or contract work.
    for arm, filename in (("PACK_A", "pack_a"), ("PACK_E", "pack_e")):
        write_json(run_dir / f"provider_request_{filename}.json", payloads[arm])
        write_json(run_dir / f"provider_response_{filename}_raw.json", responses[arm])
    predictions: dict[str, dict[str, Any]] = {}; paths: dict[str, list[dict[str, Any]]] = {}
    freeze_timestamps: dict[str, str] = {}
    for arm in ("PACK_A", "PACK_E"):
        raw = responses[arm].get("raw_output")
        parsed = parse_provider_output(raw)
        freeze_ts = str(responses[arm].get("completed_timestamp") or now())
        prediction, arm_paths = response_to_contract(parsed, by_arm[arm], run_id=run_id, created_ts=freeze_ts, raw_output=raw, bridge_result=responses[arm])
        predictions[arm], paths[arm], freeze_timestamps[arm] = prediction, arm_paths, freeze_ts
    contract.validate_ae_pair(predictions["PACK_A"], predictions["PACK_E"])
    outcome = outcome_by_episode[candidate["episode_id"]]
    contract.validate_outcome(outcome)
    attachment_ts = now()
    evaluations = {arm: evaluate(predictions[arm], paths[arm], outcome, generated_ts=attachment_ts) for arm in ("PACK_A", "PACK_E")}
    adequacy = attention_adequacy(arm_a)
    if adequacy["decision"] != "ADEQUATE":
        raise Step6Error("V2_1_STEP6_ATTENTION_SCOPE_TARGETED_EXTENSION_REQUIRED")
    write_json(run_dir / "selected_pair.json", {"selected_candidate": candidate, "availability_attempts": availability_attempts, "execution_order": order, "generation_settings": {"temperature": "existing_bridge_default", "seed": "not_supported_by_existing_bridge", "max_output_tokens": "existing_bridge_default"}})
    write_json(run_dir / "prompt_template.json", {"version": PROMPT_VERSION, "allowed_prompt_differences": sorted(ALLOWED_PROMPT_DIFFERENCES), "instruction": "Canonical prompt text is identical except the explicitly permitted context fields."})
    for arm, filename in (("PACK_A", "pack_a"), ("PACK_E", "pack_e")):
        prompt = prompt_text(contexts[arm])
        (run_dir / f"prompt_{filename}.txt").write_text(prompt + "\n")
        write_json(run_dir / f"prompt_{filename}_fingerprint.json", {"fingerprint": sha256(contexts[arm]), "context": contexts[arm]})
        write_json(run_dir / f"prediction_{filename}.json", predictions[arm])
        write_jsonl(run_dir / f"prediction_path_{filename}.jsonl", paths[arm])
        write_json(run_dir / f"evaluation_{filename}.json", evaluations[arm])
    write_json(run_dir / "prompt_diff.json", diff)
    write_json(run_dir / "outcome_reference.json", {"outcome_attached_ts": attachment_ts, "outcome": outcome, "same_outcome_for_pack_a_and_pack_e": True})
    write_json(run_dir / "attention_scope_adequacy.json", adequacy)
    validation = {
        "contract_ae_pair_valid": True, "outcome_valid": True, "outcome_attached_after_forecast_freeze": all(parse_iso(freeze_timestamps[arm]) <= parse_iso(attachment_ts) for arm in freeze_timestamps),
        "same_outcome_identity": evaluations["PACK_A"]["outcome_id"] == evaluations["PACK_E"]["outcome_id"], "prompt_symmetry": diff,
        "leakage_fields_exposed": 0, "attention_scope_decision": adequacy["decision"],
    }
    write_json(run_dir / "pair_validation.json", validation)
    manifest = {
        "run_id": run_id, "created_ts": now(), "git_head": git_head(), "contract_version": contract.CONTRACT_VERSION,
        "candidate_selection_fingerprint": sha256(assessed), "selected_pair": candidate, "execution_order": order,
        "provider_calls": 2, "apps_script_calls": 2, "google_sheets_writes": 0, "workbook_writes": 0,
        "prediction_fingerprints": {arm: predictions[arm]["prediction_fingerprint"] for arm in predictions},
        "prediction_path_fingerprints": {arm: sha256(paths[arm]) for arm in paths},
        "evaluation_fingerprints": {arm: evaluations[arm]["evaluation_fingerprint"] for arm in evaluations},
        "outcome_id": outcome["outcome_id"], "outcome_attachment_ts": attachment_ts, "forecast_freeze_timestamps": freeze_timestamps,
        "decision": "V2_1_STEP6_SINGLE_HISTORICAL_PAIR_VALIDATED",
    }
    write_json(run_dir / "run_manifest.json", manifest)
    return run_dir, manifest


def validate_saved_run(run_dir: Path) -> dict[str, Any]:
    """Reconstruct the completed pair without dispatching any provider call."""
    manifest = json.loads((run_dir / "run_manifest.json").read_text())
    predictions = {arm: json.loads((run_dir / f"prediction_pack_{arm.lower()}.json").read_text()) for arm in ("A", "E")}
    paths = {arm: read_jsonl(run_dir / f"prediction_path_pack_{arm.lower()}.jsonl") for arm in ("A", "E")}
    evaluations = {arm: json.loads((run_dir / f"evaluation_pack_{arm.lower()}.json").read_text()) for arm in ("A", "E")}
    outcome = json.loads((run_dir / "outcome_reference.json").read_text())["outcome"]
    contract.validate_ae_pair(predictions["A"], predictions["E"])
    contract.validate_outcome(outcome)
    contract.validate_evaluation(evaluations["A"], predictions["A"], outcome, paths["A"])
    contract.validate_evaluation(evaluations["E"], predictions["E"], outcome, paths["E"])
    validation = json.loads((run_dir / "pair_validation.json").read_text())
    if not validation.get("prompt_symmetry", {}).get("passed") or validation.get("leakage_fields_exposed") != 0:
        raise Step6Error("SAVED_RUN_VALIDATION_FAILURE")
    stable = {
        "prediction_fingerprints": manifest["prediction_fingerprints"],
        "prediction_path_fingerprints": manifest["prediction_path_fingerprints"],
        "evaluation_fingerprints": manifest["evaluation_fingerprints"],
        "outcome_id": manifest["outcome_id"],
        "prompt_a": json.loads((run_dir / "prompt_pack_a_fingerprint.json").read_text())["fingerprint"],
        "prompt_e": json.loads((run_dir / "prompt_pack_e_fingerprint.json").read_text())["fingerprint"],
    }
    return {"run_id": manifest["run_id"], "provider_calls": 0, "valid": True, "stable_validation_fingerprint": sha256(stable)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--validate-run", type=Path)
    parser.add_argument("--prevalidation-manifest", type=Path)
    parser.add_argument("--outcomes-path", type=Path)
    args = parser.parse_args()
    if args.validate_run:
        print(json.dumps(validate_saved_run(args.validate_run), sort_keys=True))
        return 0
    run_dir, manifest = run(output_root=args.output_root, prevalidation_manifest=args.prevalidation_manifest, outcomes_path=args.outcomes_path)
    print(json.dumps({"run_dir": str(run_dir), "decision": manifest["decision"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
