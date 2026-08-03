#!/usr/bin/env python3
"""Freeze the governed T-15 Round 2 admission and dispatch inputs locally."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation import build_presignal_v21_episodes as episode_builder
from automation import presignal_v21_event_path_contract_v1_1 as contract

BASE = ROOT / "outputs" / "presignal_v21_full_round_1_forecast_execution"
SNAPSHOT_PATH = BASE / "PPHB-R2-SCHEDULE-REFRESH-20260803T151000Z" / "event_sheet_snapshot.json"
OUTPUT_DIR = BASE / "PPHB-R2-T-MINUS-15-FIRST-SLICE-20260804T013000Z"
AMENDMENT_ID = "PPHB-R2-T-MINUS-15-CUTOFF-PROTOCOL-AMENDMENT-20260804T013000Z"
SLICE_ID = "PPHB-R2-FIRST-ROLLING-SLICE-001-20260804T013000Z"
MANIFEST_ID = "PPHB-R2-FIRST-ROLLING-SLICE-MANIFEST-20260804T013000Z"
AUTHORIZATION_ID = "PPHB-R2-FIRST-ROLLING-SLICE-DISPATCH-AUTHORIZATION-20260804T013000Z"
SNAPSHOT_ID = "PPHB-R2-CURRENT-EVENT-SNAPSHOT-20260803T151000Z"
SNAPSHOT_FINGERPRINT = "sha256:afab082d51abdd725b7c1a802c3391673de91e65c2b964b5cd31a29f3475b6d9"
PROMPT_ID = "presignal_event_path_contract_v1_1_single_pair_validation_no_signal_confidence_explicit_v1"
PROMPT_FINGERPRINT = "sha256:2515e6c09742e58507efe8d9196ba58473c01f2d5bb9e8b5405405088d323a77"
PROTOCOL_ID = "PPHB-R2-CONFIRMATORY-PROSPECTIVE-PROTOCOL-20260804T080000Z"
PROTOCOL_FINGERPRINT = "sha256:d417e4c76d3d38d471dbc76cbf361be4a28dac1b615ecccdc8aa18c37262362f"
ENVELOPE_ID = "PPHB-R2-EXECUTION-ENVELOPE-20260803T090000Z"
ENVELOPE_FINGERPRINT = "sha256:3fe721eee816e48a5eca00c50cbcbc397bec6258d60bdfc7857e8169869efdd0"
DEPLOYMENT_ID = "AKfycbw-SXeE8pE85mISnpH_xygFLjgysQqGpzAmcj9h8P9kRg4LCq3iI7BnoB5hYL-x72xN"
DEPLOYMENT_VERSION = "83"
ROUTES = (
    ("Anthropic", "claude-haiku-4-5"),
    ("Gemini", "gemini-2.5-flash-lite"),
    ("OpenAI", "gpt-4o-mini-2024-07-18"),
)
HORIZONS = [5, 15, 30, 60]


class TMinus15Error(ValueError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise TMinus15Error("AMBIGUOUS_OR_INVALID_UTC_TIMESTAMP") from exc
    if parsed.tzinfo is None:
        raise TMinus15Error("AMBIGUOUS_TIMEZONE")
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def cutoff_for(release_timestamp: str) -> str:
    release = parse_utc(release_timestamp)
    return (release - timedelta(minutes=15)).isoformat().replace("+00:00", "Z")


def dispatch_allowed(now_utc: datetime, cutoff_timestamp: str) -> bool:
    return now_utc.astimezone(timezone.utc).replace(microsecond=0) < parse_utc(cutoff_timestamp)


def classify_event(row: dict[str, Any], *, now_utc: datetime, snapshot_export_utc: datetime) -> str:
    raw = canonical(row).lower()
    if any(marker in raw for marker in ("synthetic", "dry_run", "fixture", "ep_event_prospective")):
        return "SYNTHETIC_OR_DRY_RUN"
    if row.get("release_status") in {"cancelled", "superseded"}:
        return "CANCELLED_OR_SUPERSEDED"
    if row.get("release_status") in {"unresolved", "revised"}:
        return "AUTHORITY_UNRESOLVED"
    try:
        release = parse_utc(str(row.get("release_ts", "")))
    except TMinus15Error:
        return "IDENTITY_OR_INSTRUMENT_INVALID"
    required = ("event_id", "country", "indicator_name", "type", "source_cal")
    if not all(str(row.get(key, "")).strip() for key in required) or row.get("country") != "US":
        return "IDENTITY_OR_INSTRUMENT_INVALID"
    if release <= snapshot_export_utc:
        return "HISTORICAL"
    if release <= now_utc:
        return "ALREADY_RELEASED"
    if not dispatch_allowed(now_utc, cutoff_for(release.isoformat().replace("+00:00", "Z"))):
        return "PAST_CUTOFF"
    return "ELIGIBLE_PROSPECTIVE"


def load_snapshot() -> dict[str, Any]:
    snapshot = json.loads(SNAPSHOT_PATH.read_text())
    if snapshot.get("snapshot_id") != SNAPSHOT_ID or snapshot.get("snapshot_fingerprint") != SNAPSHOT_FINGERPRINT:
        raise TMinus15Error("SNAPSHOT_BINDING_CONFLICT")
    if snapshot.get("snapshot_status") != "AUTHORITATIVE_EVENT_SHEET_EXPORT":
        raise TMinus15Error("AUTHORITATIVE_SNAPSHOT_REQUIRED")
    return snapshot


def amendment() -> dict[str, Any]:
    value = {
        "amendment_id": AMENDMENT_ID,
        "schema_version": "1.0.0",
        "decision": "ROUND_2_T_MINUS_15_CUTOFF_AUTHORITY_FROZEN",
        "supplements": {"protocol_id": PROTOCOL_ID, "protocol_fingerprint": PROTOCOL_FINGERPRINT},
        "rule": "forecast_cutoff_utc = authoritative release_timestamp_utc - 15 minutes",
        "rules": {
            "comparison_timezone": "UTC",
            "comparison_precision": "one second after canonical timestamp normalization",
            "manifest_freeze": "before forecast_cutoff_utc",
            "dispatch_boundary": "transport creation and dispatch must begin strictly before cutoff; no call at or after cutoff",
            "cutoff_passed_state": "CUTOFF_PASSED_NOT_AUTHORIZED",
            "retries": 0,
            "revised_release": "recalculate cutoff before dispatch",
            "cancelled_or_superseded": "ineligible",
            "already_released": "ineligible",
            "ambiguous_release_or_timezone": "fail closed",
            "dispatch_clock": "recorded execution-environment UTC clock",
            "waiver": "cutoff cannot be moved or waived",
        },
    }
    value["fingerprint"] = digest(value)
    return value


def classify_snapshot(snapshot: dict[str, Any], now_utc: datetime) -> tuple[dict[str, Any], dict[str, list[str]]]:
    export_utc = parse_utc(str(snapshot["exported_at_utc"]))
    identities: dict[str, list[str]] = {}
    counts = Counter()
    for row in snapshot["event_rows"]:
        category = classify_event(row, now_utc=now_utc, snapshot_export_utc=export_utc)
        event_id = str(row.get("event_id", ""))
        counts[category] += 1
        identities.setdefault(category, []).append(event_id)
    expected = {
        "ELIGIBLE_PROSPECTIVE", "FUTURE_NOT_YET_ADMITTED", "PAST_CUTOFF", "ALREADY_RELEASED",
        "CANCELLED_OR_SUPERSEDED", "HISTORICAL", "SYNTHETIC_OR_DRY_RUN",
        "IDENTITY_OR_INSTRUMENT_INVALID", "AUTHORITY_UNRESOLVED",
    }
    if set(counts) - expected or sum(counts.values()) != len(snapshot["event_rows"]):
        raise TMinus15Error("SNAPSHOT_PARTITION_CONFLICT")
    for category in sorted(expected):
        counts.setdefault(category, 0)
        identities.setdefault(category, [])
    return {
        "snapshot_id": SNAPSHOT_ID,
        "snapshot_fingerprint": SNAPSHOT_FINGERPRINT,
        "classification_clock_utc": now_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "snapshot_export_timestamp_utc": export_utc.isoformat().replace("+00:00", "Z"),
        "counts": dict(sorted(counts.items())),
        "total_events": len(snapshot["event_rows"]),
    }, identities


def build_slice(snapshot: dict[str, Any], now_utc: datetime, amendment_record: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, list[str]]]:
    classification, identities = classify_snapshot(snapshot, now_utc)
    eligible_rows = [
        row for row in snapshot["event_rows"]
        if classify_event(
            row,
            now_utc=now_utc,
            snapshot_export_utc=parse_utc(str(snapshot["exported_at_utc"])),
        ) == "ELIGIBLE_PROSPECTIVE"
    ]
    episodes, dispositions = episode_builder.build_population(eligible_rows)
    if any(item["disposition"] != "CONSUMED" for item in dispositions):
        raise TMinus15Error("ELIGIBLE_EVENT_TO_EPISODE_CONFLICT")
    episodes = sorted(episodes, key=lambda item: (item["release_ts"], item["episode_id"]))
    selected = episodes[:48]
    if len(selected) != len(episodes):
        for episode in episodes[48:]:
            for event_id in episode["member_event_ids"]:
                identities.setdefault("FUTURE_NOT_YET_ADMITTED", []).append(event_id)
        classification["counts"]["FUTURE_NOT_YET_ADMITTED"] = len(identities["FUTURE_NOT_YET_ADMITTED"])
        classification["counts"]["ELIGIBLE_PROSPECTIVE"] -= sum(e["member_event_count"] for e in episodes[48:])
    freeze_ts = now_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    admitted = []
    for episode in selected:
        cutoff = cutoff_for(episode["release_ts"])
        if not parse_utc(freeze_ts) < parse_utc(cutoff):
            raise TMinus15Error("MANIFEST_FREEZE_NOT_BEFORE_CUTOFF")
        admitted.append({
            "episode_id": episode["episode_id"],
            "event_ids": episode["member_event_ids"],
            "event_source": "FMP_ECONOMIC_CALENDAR_VIA_APPS_SCRIPT_EVENT_SHEET",
            "event_sheet_identity": {"snapshot_id": SNAPSHOT_ID, "event_ids": episode["member_event_ids"]},
            "event_name_category": episode["member_indicator_names"],
            "country": episode["country"],
            "instrument": "USD/JPY",
            "release_timestamp_utc": episode["release_ts"],
            "forecast_cutoff_utc": cutoff,
            "admission_timestamp_utc": freeze_ts,
            "manifest_freeze_timestamp_utc": freeze_ts,
            "snapshot_lineage": {"snapshot_id": SNAPSHOT_ID, "snapshot_fingerprint": SNAPSHOT_FINGERPRINT},
            "duplicate_prevention_identity": digest({"slice_id": SLICE_ID, "episode_id": episode["episode_id"], "instrument": "USD/JPY", "release": episode["release_ts"]}),
        })
    inventory = []
    for item in admitted:
        for pack, arm in (("A", "BASELINE"), ("E", "FULL_CONTEXT")):
            input_fingerprint = digest({"episode_id": item["episode_id"], "pack": pack, "information_arm": arm, "source_snapshot": SNAPSHOT_FINGERPRINT})
            for provider, model in ROUTES:
                key = {"slice_id": SLICE_ID, "episode_id": item["episode_id"], "pack": pack, "provider": provider, "model": model, "prompt_id": PROMPT_ID, "prompt_fingerprint": PROMPT_FINGERPRINT, "pack_input_fingerprint": input_fingerprint, "release_timestamp_utc": item["release_timestamp_utc"], "forecast_cutoff_utc": item["forecast_cutoff_utc"], "instrument": "USD/JPY"}
                call_id = "R2FCL_" + hashlib.sha256(canonical(key).encode()).hexdigest()[:24]
                inventory.append({**key, "call_id": call_id, "forecast_horizons_minutes": HORIZONS, "output_contract": {"contract_version": contract.CONTRACT_VERSION, "schema_version": contract.SCHEMA_VERSION}, "exclusive_lease_identity": "R2_EXCLUSIVE_SLICE_LEASE_" + SLICE_ID, "durable_reservation_identity": "R2_RESERVATION_" + call_id, "duplicate_prevention_identity": call_id, "append_only_lineage": {"manifest_id": MANIFEST_ID, "amendment_id": AMENDMENT_ID}, "timing_classification": "DISPATCH_DUE_NOW" if dispatch_allowed(now_utc, item["forecast_cutoff_utc"]) else "CUTOFF_PASSED_NOT_AUTHORIZED"})
    if len({x["call_id"] for x in inventory}) != len(inventory):
        raise TMinus15Error("DUPLICATE_CALL_IDENTITY")
    provider_counts = Counter(f"{x['provider']}/{x['model']}" for x in inventory)
    manifest = {
        "manifest_id": MANIFEST_ID, "slice_id": SLICE_ID, "schema_version": "presignal_r2_first_slice_manifest_v1", "status": "FROZEN_PREPARATION_ONLY", "amendment_id": AMENDMENT_ID, "amendment_fingerprint": amendment_record["fingerprint"], "protocol_id": PROTOCOL_ID, "protocol_fingerprint": PROTOCOL_FINGERPRINT, "envelope_id": ENVELOPE_ID, "envelope_fingerprint": ENVELOPE_FINGERPRINT, "snapshot_id": SNAPSHOT_ID, "snapshot_fingerprint": SNAPSHOT_FINGERPRINT, "deployment_id": DEPLOYMENT_ID, "deployment_version": DEPLOYMENT_VERSION, "episode_count": len(admitted), "episodes": admitted, "forecast_call_count": len(inventory), "pack_a_count": sum(x["pack"] == "A" for x in inventory), "pack_e_count": sum(x["pack"] == "E" for x in inventory), "complete_pack_pairs": len(admitted) * len(ROUTES), "provider_model_counts": dict(sorted(provider_counts.items())), "deterministic_order": "release_timestamp_utc ascending, then episode_id", "pairing_proof": "Every admitted Episode has exactly one Pack A and one Pack E call for each of the three fixed provider/model routes.", "exclusions": {"historical_and_released": "snapshot classification", "authority_unresolved": "snapshot classification", "terminal_or_synthetic": "snapshot classification"}, "forecast_contract": contract.CONTRACT_VERSION, "schema_version_output": contract.SCHEMA_VERSION, "attachment_and_evaluation": "not authorized in this Move"}
    manifest["manifest_fingerprint"] = digest(manifest)
    authorization = {"authorization_id": AUTHORIZATION_ID, "status": "FROZEN_NOT_ACTIVE", "manifest_id": MANIFEST_ID, "manifest_fingerprint": manifest["manifest_fingerprint"], "amendment_id": AMENDMENT_ID, "exact_call_ids": [x["call_id"] for x in inventory], "maximum_provider_calls": len(inventory), "maximum_calls_per_provider": {provider: sum(x["provider"] == provider for x in inventory) for provider, _ in ROUTES}, "retry_boundary": 0, "transport_route": "existing canonical v2.1 provider forecast path", "raw_output_preservation": True, "output_validator": contract.CONTRACT_VERSION, "exclusive_slice_lease": True, "durable_reservation_before_transport": True, "cutoff_recheck": "immediately before every dispatch; strictly before forecast_cutoff_utc", "remote_state": "ambiguous post-dispatch state is governance stop", "google_writes": 0, "market_data_access": 0, "outcome_access": 0, "evaluation": 0, "single_use": True}
    authorization["fingerprint"] = digest(authorization)
    return classification, {"classification": classification, "identities": identities}, {"manifest": manifest, "inventory": inventory, "authorization": authorization}, identities


def freeze(output_dir: Path = OUTPUT_DIR, *, now_utc: datetime | None = None) -> dict[str, Any]:
    if output_dir.exists():
        raise TMinus15Error("ARTIFACT_ALREADY_EXISTS")
    now_utc = now_utc or datetime.now(timezone.utc)
    amendment_record = amendment()
    snapshot = load_snapshot()
    classification, proof, downstream, identities = build_slice(snapshot, now_utc, amendment_record)
    timing = Counter(x["timing_classification"] for x in downstream["inventory"])
    for state in ("DISPATCH_DUE_NOW", "FROZEN_NOT_YET_DISPATCHABLE", "CUTOFF_PASSED_NOT_AUTHORIZED"):
        timing.setdefault(state, 0)
    evidence = {"amendment": amendment_record, "snapshot_eligibility": proof, "snapshot_event_identities_by_class": identities, "first_slice": downstream["manifest"], "forecast_call_inventory": downstream["inventory"], "dispatch_authorization": downstream["authorization"], "timing_counts": dict(sorted(timing.items())), "activity": {"provider_calls": 0, "google_access": 0, "market_data_access": 0, "outcome_activity": 0, "evaluation_activity": 0, "retries": 0}}
    output_dir.mkdir(parents=True)
    for name, value in (("cutoff_amendment.json", amendment_record), ("snapshot_eligibility_proof.json", proof), ("first_slice_manifest.json", downstream["manifest"]), ("forecast_call_inventory.json", {"calls": downstream["inventory"]}), ("provider_dispatch_authorization.json", downstream["authorization"]), ("validation_evidence.json", {"classification": classification, "timing_counts": dict(sorted(timing.items())), "activity": evidence["activity"]})):
        (output_dir / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR); args = parser.parse_args()
    print(json.dumps(freeze(args.output_dir), sort_keys=True)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
