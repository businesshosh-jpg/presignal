#!/usr/bin/env python3
"""Fail-closed Round 2 schedule admission and continuous execution coordinator.

This controller deliberately does not fetch a schedule or dispatch a provider.  It
accepts only a captured canonical Event-sheet export, so a separately authorized
schedule refresh remains the sole way to introduce prospective identities.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import build_presignal_v21_episodes as episode_builder
from automation import freeze_presignal_v21_round_2_protocol as protocol_builder
from automation import prepare_presignal_v21_round_2_execution_envelope as envelope_builder

BASE = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
PROTOCOL_PATH = BASE / "PPHB-R2-CONFIRMATORY-PROSPECTIVE-PROTOCOL-20260804T080000Z" / "round_2_protocol.json"
ENVELOPE_PATH = BASE / "PPHB-R2-EXECUTION-ENVELOPE-PREPARATION-20260803T090000Z" / "execution_envelope.json"
OUTPUT_DIR = BASE / "PPHB-R2-CONTINUOUS-EXECUTION-CONTROLLER-20260803T100000Z"
CONTROLLER_ID = "PPHB-R2-CONTINUOUS-EXECUTION-CONTROLLER-20260803T100000Z"
SOURCE_AUTHORITY = "FMP_ECONOMIC_CALENDAR_VIA_APPS_SCRIPT_EVENT_SHEET"
ROUTES = (
    ("Anthropic", "claude-haiku-4-5"),
    ("Gemini", "gemini-2.5-flash-lite"),
    ("OpenAI", "gpt-4o-mini-2024-07-18"),
)
PREREQUISITE_PROVIDER_STAGE_TIMEOUT_SECONDS = 180


class AdmissionError(ValueError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def parse_utc(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (AttributeError, ValueError) as exc:
        raise AdmissionError("INVALID_UTC_TIMESTAMP") from exc


def load_authorities() -> tuple[dict[str, Any], dict[str, Any]]:
    protocol = json.loads(PROTOCOL_PATH.read_text())
    protocol_builder.validate_protocol(protocol)
    if protocol.get("protocol_fingerprint") != "sha256:d417e4c76d3d38d471dbc76cbf361be4a28dac1b615ecccdc8aa18c37262362f":
        raise AdmissionError("ROUND_2_PROTOCOL_FINGERPRINT_CONFLICT")
    envelope = json.loads(ENVELOPE_PATH.read_text())
    frozen = dict(envelope)
    supplied = frozen.pop("envelope_fingerprint", "")
    if supplied != digest(frozen) or supplied != "sha256:3fe721eee816e48a5eca00c50cbcbc397bec6258d60bdfc7857e8169869efdd0":
        raise AdmissionError("ROUND_2_ENVELOPE_FINGERPRINT_CONFLICT")
    return protocol, envelope


def source_contract() -> dict[str, Any]:
    return {
        "source_authority": SOURCE_AUTHORITY,
        "authoritative_owner": "Apps Script Event sheet populated only through the canonical FMP calendar integration",
        "refresh_entry_point": "apps_script/automation_api.js::apiUpsertEventWindow_",
        "fmp_collection_entry_point": "apps_script/fmp_calendar.js::fmpFetchRangeUtc_",
        "normalization_entry_point": "apps_script/fmp_calendar.js::normalizeFmpRow_",
        "persistence_and_batching": ["apps_script/fmp_calendar.js::_upsertEventsToEvent_", "apps_script/automation_api.js::applyBatchingForKeys_"],
        "local_read_adapter": "automation/google_clients.py::get_sheet_values, captured as an append-only Event-sheet export",
        "required_event_schema": sorted(episode_builder.REQUIRED_HEADERS),
        "identity_rule": "Event-row locator and deterministic Episode construction from automation/build_presignal_v21_episodes.py; FMP upsert fallback key is country|indicator_name|release_ts.",
        "revision_and_cancellation": "A changed event, release timestamp, type, batch, or cancellation after a manifest is frozen invalidates that pending admission and is a governance stop; no silent replacement is permitted.",
        "refresh_cadence": "A separately authorized refresh before each new Slice admission and on any authoritative revision/cancellation notice.",
        "snapshot_requirement": "Only an append-only authoritative Event-sheet export with canonical Apps Script/FMP lineage may admit Episodes.",
        "live_access_boundary": "Refreshing calls FMP and upserts the Event sheet; it requires a separate exact schedule-refresh authorization with external and Google-write ceilings.",
        "fixture_rejection": ["synthetic", "fixture", "dry_run", "EP_EVENT_PROSPECTIVE"],
    }


def validate_snapshot(snapshot: dict[str, Any], now: datetime) -> list[dict[str, Any]]:
    if snapshot.get("snapshot_status") != "AUTHORITATIVE_EVENT_SHEET_EXPORT" or snapshot.get("source_authority") != SOURCE_AUTHORITY:
        raise AdmissionError("AUTHORITATIVE_SNAPSHOT_REQUIRED")
    lineage = snapshot.get("acquisition_lineage", {})
    required = {"apiUpsertEventWindow_", "runFmpRangeToEvent_", "applyBatchingForKeys_", "event_sheet_export"}
    if not isinstance(lineage, dict) or not required <= set(lineage.get("canonical_steps", [])):
        raise AdmissionError("SOURCE_LINEAGE_INCOMPLETE")
    rows = snapshot.get("event_rows")
    if not isinstance(rows, list) or not rows:
        raise AdmissionError("EMPTY_AUTHORITATIVE_SNAPSHOT")
    for row in rows:
        serialized = canonical(row).lower()
        if any(marker in serialized for marker in ("synthetic", "fixture", "dry_run", "ep_event_prospective")):
            raise AdmissionError("SYNTHETIC_OR_DRY_RUN_EPISODE_REJECTED")
        if row.get("release_status", "scheduled") not in {"scheduled", ""}:
            raise AdmissionError("NON_SCHEDULED_EVENT_REJECTED")
        if parse_utc(str(row.get("release_ts", ""))) <= now:
            raise AdmissionError("HISTORICAL_OR_RELEASED_EVENT_REJECTED")
    episodes, dispositions = episode_builder.build_population(rows)
    if any(item["disposition"] != "CONSUMED" for item in dispositions):
        raise AdmissionError("EVENT_TO_EPISODE_RECONCILIATION_CONFLICT")
    return sorted(episodes, key=lambda item: (item["release_ts"], item["episode_id"]))


def select_rolling_slice(episodes: list[dict[str, Any]], prepared: dict[str, dict[str, Any]], now: datetime, maximum: int = 48) -> list[dict[str, Any]]:
    if maximum < 1 or maximum > 48:
        raise AdmissionError("ROUND_2_SLICE_LIMIT_CONFLICT")
    selected = []
    for episode in episodes:
        item = prepared.get(episode["episode_id"])
        if not item:
            continue
        cutoff = parse_utc(str(item.get("forecast_cutoff_ts", "")))
        release = parse_utc(episode["release_ts"])
        if not now < cutoff < release:
            raise AdmissionError("PROSPECTIVE_CUTOFF_CONFLICT")
        if set(item.get("prompt_fingerprints", {})) != {"A", "E"}:
            raise AdmissionError("PROMPT_FINGERPRINT_AUTHORITY_CONFLICT")
        inputs = item.get("pack_inputs", {})
        if set(inputs) != {"A", "E"} or any(not inputs[pack].get("artifact_id") or not inputs[pack].get("fingerprint") for pack in ("A", "E")):
            raise AdmissionError("PACK_INPUTS_COMPLETE_REQUIRED_BEFORE_CALL_FREEZE")
        selected.append({"episode": episode, "prepared": item})
        if len(selected) == maximum:
            break
    return selected


def forecast_inventory(slice_id: str, selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    inventory = []
    for item in selected:
        episode, prepared = item["episode"], item["prepared"]
        pack_inputs = prepared["pack_inputs"]
        for pack in ("A", "E"):
            for provider, model in ROUTES:
                key = {"slice_id": slice_id, "episode_id": episode["episode_id"], "pack": pack, "provider": provider, "model": model, "cutoff": prepared["forecast_cutoff_ts"], "prompt_fingerprint": prepared["prompt_fingerprints"][pack], "release_ts": episode["release_ts"]}
                record = dict(key)
                record["call_id"] = "R2FCL_" + hashlib.sha256(canonical(key).encode()).hexdigest()[:24]
                record["target_instrument"] = "USD/JPY"
                record["pack_input_artifact_id"] = pack_inputs[pack]["artifact_id"]
                record["pack_input_fingerprint"] = pack_inputs[pack]["fingerprint"]
                record["forecast_horizons_minutes"] = [5, 15, 30, 60]
                record["duplicate_prevention_identity"] = record["call_id"]
                inventory.append(record)
    if len({record["call_id"] for record in inventory}) != len(inventory):
        raise AdmissionError("DUPLICATE_FORECAST_CALL_IDENTITY")
    return inventory


def continuous_contract(protocol: dict[str, Any], envelope: dict[str, Any]) -> dict[str, Any]:
    return {
        "controller_id": CONTROLLER_ID,
        "controller_schema_version": "1.0.0",
        "protocol_binding": {"protocol_id": protocol["protocol_id"], "protocol_fingerprint": protocol["protocol_fingerprint"]},
        "envelope_binding": {"envelope_id": envelope["envelope_id"], "envelope_fingerprint": envelope["envelope_fingerprint"]},
        "execution_sequence": ["authorized_schedule_refresh", "snapshot_validation", "episode_admission", "authorized_attention", "authorized_information_requests", "authorized_shared_market_state_acquisition", "canonical_pack_materialization", "pack_input_validation", "manifest_freeze", "exact_dispatch_authorization", "canonical_forecast_dispatch", "outcome_eligibility_wait", "canonical_outcome_collection_attachment_evaluation", "cumulative_progress_reconciliation", "next_slice_or_protocol_stop"],
        "canonical_stage_entry_points": ["automation/build_presignal_v21_episodes.py", "automation/presignal_v21_minimal_prospective_lineage_v1.py::build_prospective_attention", "automation/presignal_v21_minimal_prospective_lineage_v1.py::build_prospective_requests", "automation/presignal_v21_minimal_prospective_lineage_v1.py::build_prospective_packs", "automation/build_presignal_v21_event_path_inputs.py::build_episode_inputs", "automation/run_presignal_v21_single_event_path_pair_v1_1.py", "automation/run_presignal_v21_authorized_slice.py"],
        "pre_cutoff_states": ["EVENT_AVAILABLE_BEFORE_ADMISSION_DEADLINE", "PRE_CUTOFF_ACQUISITION_AUTHORIZATION_REQUIRED", "PRE_CUTOFF_ACQUISITION_IN_PROGRESS", "SHARED_MARKET_STATE_COMPLETE", "PACK_INPUTS_COMPLETE", "FORECAST_DISPATCH_AUTHORIZATION_REQUIRED", "PRE_CUTOFF_ACQUISITION_PENDING", "PACK_INPUTS_COMPLETE_DISPATCH_AUTHORIZATION_REQUIRED", "ADMISSION_WINDOW_PASSED", "PREREQUISITE_GOVERNANCE_BLOCKED"],
        "call_freeze_guard": "Forecast-call identities may be constructed only after both immutable Pack-input artifact IDs and fingerprints are present for every Episode. The controller never materializes or substitutes missing semantic inputs.",
        "known_stage_limit_seconds": {"attention_provider_call": PREREQUISITE_PROVIDER_STAGE_TIMEOUT_SECONDS, "information_request_provider_call": PREREQUISITE_PROVIDER_STAGE_TIMEOUT_SECONDS},
        "resume_and_idempotency": "Durable exact call reservations, schedule snapshot lineage, accepted stage proofs, and per-request checkpoints are required. Resume dispatches only missing exact identities and stops on any ambiguous remote state.",
        "global_limits": {"maximum_admitted_episodes": 144, "maximum_episodes_per_slice": 48, "zero_retry_default": 0, "zero_google_write_default": 0},
        "mechanical_repairs": ["paths", "filenames", "serialization", "schedule parsing", "argument mapping", "manifest discovery", "authorization binding", "completion proofs", "resume", "idempotency", "duplicate prevention", "checkpointing", "dynamic population", "ceiling derivation"],
        "governance_stops": protocol["mandatory_governance_stops"],
        "no_implicit_dispatch": "Provider calls require an active immutable authorization enumerating every exact call identity; policy ceilings alone never authorize dispatch.",
    }


def freeze(output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    if output_dir.exists():
        raise AdmissionError("CONTINUOUS_CONTROLLER_ARTIFACT_ALREADY_EXISTS")
    protocol, envelope = load_authorities()
    source = source_contract()
    controller = continuous_contract(protocol, envelope)
    roster = {
        "decision": "ROUND_2_FULL_ROSTER_NOT_FEASIBLE_WITHOUT_AUTHORIZED_CURRENT_SNAPSHOT",
        "eligible_current_episode_count": 0,
        "full_roster_authorization_inputs_ready": False,
        "first_rolling_slice_authorization_inputs_ready": False,
        "reason": "No append-only authoritative current Event-sheet export is present. The previous 2030 records are synthetic fixtures and cannot be admitted.",
        "required_next_authority": "Freeze a bounded schedule-refresh and Event-sheet-export authorization, then validate the captured snapshot before freezing exact provider-call identities.",
    }
    dispatch = {
        "decision": "ROUND_2_DISPATCH_AUTHORIZATION_INPUTS_NOT_READY",
        "exact_forecast_call_identities": [],
        "maximum_provider_calls": 0,
        "maximum_calls_per_provider": {provider: 0 for provider, _ in ROUTES},
        "retry_boundary": 0,
        "prohibitions": ["provider dispatch", "Google writes", "Outcome collection", "evaluation", "retry"],
        "blocking_reference": roster["reason"],
    }
    decision = {
        "source_decision": "ROUND_2_AUTHORITATIVE_EPISODE_SOURCE_ESTABLISHED",
        "controller_decision": "CONTINUOUS_ROUND_2_CONTROLLER_READY",
        "roster_decision": "ROUND_2_DISPATCH_AUTHORIZATION_INPUTS_NOT_READY",
        "external_access": 0,
        "provider_calls": 0,
        "google_writes": 0,
        "outcome_activity": 0,
        "evaluation_activity": 0,
    }
    output_dir.mkdir(parents=True)
    files = {"authoritative_episode_source.json": source, "continuous_controller_contract.json": controller, "admission_rules.json": {"snapshot_validation": "validate_snapshot", "selection": "select_rolling_slice", "full_roster_rule": "A live dynamic release schedule cannot be frozen beyond the captured authoritative snapshot; revisions invalidate affected pending admissions."}, "roster_feasibility.json": roster, "first_rolling_slice_population_proof.json": roster, "forecast_call_inventory.json": {"calls": []}, "forecast_dispatch_authorization_inputs.json": dispatch, "controller_validation.json": decision, "controller_decision.json": decision}
    for name, value in files.items():
        (output_dir / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return decision


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    print(json.dumps(freeze(args.output_dir), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
