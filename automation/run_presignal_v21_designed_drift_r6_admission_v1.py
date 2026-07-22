"""Fail-closed, write-isolated admission utility for one R6 smoke identity.

It performs no provider dispatch and intentionally accepts an already-ingested
authoritative episode snapshot; live calendar acquisition remains owned by the
existing ingestion route.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from automation.presignal_v21_canonical_states_v1 import SelectionState

ROOT = Path(__file__).resolve().parents[1]
ISOLATED_ROOT = ROOT / "outputs" / "presignal_v21_designed_drift_prospective"
FROZEN_MARKERS = ("final_historical", "step8_r3_final", "frozen")
FORBIDDEN_MARKERS = ("Predictions", "prediction")


class AdmissionError(RuntimeError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def safe_run_path(run_id: str, root: Path = ISOLATED_ROOT) -> Path:
    candidate = (root / run_id).resolve()
    root_resolved = root.resolve()
    if candidate.parent != root_resolved or any(marker in str(candidate) for marker in FROZEN_MARKERS + FORBIDDEN_MARKERS):
        raise AdmissionError("WRITE_ISOLATION_PATH_REJECTED")
    return candidate


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def admission_snapshot(*, episode: Mapping[str, Any], selection_state: str, provider: str, model: str,
                       attention: Mapping[str, Any] | None, requests: Mapping[str, Any] | None,
                       pack_a: Mapping[str, Any] | None, pack_e: Mapping[str, Any] | None,
                       admitted_at: datetime | None = None) -> dict[str, Any]:
    now = admitted_at or datetime.now(timezone.utc)
    required = ("episode_id", "member_event_ids", "release_ts", "forecast_cutoff_ts")
    if any(not episode.get(field) for field in required):
        raise AdmissionError("EPISODE_LINEAGE_INCOMPLETE")
    cutoff = _parse_time(str(episode["forecast_cutoff_ts"]))
    if now >= cutoff:
        raise AdmissionError("NO_PRE_CUTOFF_EPISODE_AVAILABLE")
    target = str(episode.get("forecast_target") or episode["episode_id"])
    common = {"episode_id": episode["episode_id"], "provider": provider, "model": model,
              "forecast_cutoff": episode["forecast_cutoff_ts"], "forecast_target": target}
    for value in (pack_a, pack_e):
        if not value or any(value.get(key) != expected for key, expected in common.items()):
            raise AdmissionError("PACK_LINEAGE_MISMATCH")
        forbidden = {"outcome", "evaluation", "released_actual", "post_release_price"} & set(value)
        if forbidden:
            raise AdmissionError("PACK_LEAKAGE_DETECTED")
    if selection_state != SelectionState.SELECTED:
        return {**common, "selection_state": selection_state, "smoke_ready": False,
                "reason": "NON_SELECTED_EPISODE", "remaining_seconds": int((cutoff - now).total_seconds())}
    if not attention or not requests:
        raise AdmissionError("LINEAGE_INCOMPLETE")
    return {**common, "selection_state": selection_state, "attention_identity": attention.get("identity"),
            "request_identity": requests.get("identity"), "pack_a_identity": pack_a.get("identity"),
            "pack_e_identity": pack_e.get("identity"), "smoke_ready": True,
            "remaining_seconds": int((cutoff - now).total_seconds())}


def persist_admission(*, run_id: str, identity: Mapping[str, Any], snapshots: Mapping[str, Mapping[str, Any]], root: Path = ISOLATED_ROOT) -> Path:
    run = safe_run_path(run_id, root)
    if (run / "smoke_identity.json").exists():
        raise AdmissionError("DUPLICATE_SMOKE_IDENTITY")
    for name, value in snapshots.items():
        if name.startswith("pack_") and "forecast" in name:
            raise AdmissionError("FORECAST_ARTIFACT_FORBIDDEN")
        atomic_json(run / name, value)
    immutable = dict(identity)
    immutable["identity_fingerprint"] = fingerprint(identity)
    atomic_json(run / "smoke_identity.json", immutable)
    return run
