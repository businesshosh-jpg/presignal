"""Pure, one-run user-selection binding for a frozen R6 Episode inventory."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence


SELECTION_METHOD = "USER_AUTHORIZED_ONE_RUN_EPISODE_SELECTION"
AUTHORIZATION_NAME = "PRESIGNAL_V21_DESIGNED_DRIFT_2_R6_EPISODE_SELECTION_AUTHORIZATION_V1"
ROUTE_B_FREEZE = "sha256:8c910a343515d88ca63ce4aaf738f28f9b4a8ab22665397077858bfaf7e866e4"
R6_V3 = "sha256:c8cb003af94eef2ef9cad8f323ab31b3c1990f3ffdcdab5ee3e6285fda76efb9"
NATIVE_ATTENTION_AUTH = "sha256:a5e1dfda5a637dbaf626c43c2bcdf512d36e2b24daff6f6ab3ce4adbd923db50"


class EpisodeSelectionError(ValueError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def checksum(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def utc(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def validate_inventory(*, candidates: Sequence[Mapping[str, Any]], episode_checksum: str, expected_episode_checksum: str, readback_valid: bool) -> None:
    if len(candidates) != 5:
        raise EpisodeSelectionError("CANDIDATE_COUNT_NOT_FIVE")
    if len({row.get("episode_id") for row in candidates}) != 5:
        raise EpisodeSelectionError("DUPLICATE_EPISODE_IDENTITY")
    if episode_checksum != expected_episode_checksum:
        raise EpisodeSelectionError("EPISODE_INVENTORY_CHECKSUM_MISMATCH")
    if checksum(candidates) != expected_episode_checksum:
        raise EpisodeSelectionError("CANDIDATE_INVENTORY_CHECKSUM_MISMATCH")
    if not readback_valid:
        raise EpisodeSelectionError("EVENT_READBACK_INVALID")
    for item in candidates:
        required = ("episode_id", "primary_event_id", "release_ts", "forecast_cutoff_ts", "schema_version", "member_event_ids", "eligibility")
        if any(not item.get(key) for key in required) or item["eligibility"] != "ELIGIBLE_UPCOMING":
            raise EpisodeSelectionError("FROZEN_CANDIDATE_INVALID")


def cutoff_revalidation(candidates: Sequence[Mapping[str, Any]], *, authorization_time_utc: str) -> list[dict[str, Any]]:
    now = utc(authorization_time_utc)
    rows = []
    for number, item in enumerate(candidates, 1):
        cutoff, release = utc(item["forecast_cutoff_ts"]), utc(item["release_ts"])
        rows.append({"candidate_number": number, "episode_id": item["episode_id"], "forecast_cutoff_ts": item["forecast_cutoff_ts"], "release_ts": item["release_ts"], "cutoff_currently_open": now < cutoff, "attention_eligibility": "ATTENTION_ELIGIBLE" if now < cutoff else "NO_LONGER_ATTENTION_ELIGIBLE", "seconds_until_forecast_cutoff": int((cutoff - now).total_seconds()), "seconds_until_release": int((release - now).total_seconds())})
    return rows


def bind_explicit_selection(*, candidates: Sequence[Mapping[str, Any]], candidate_number: int, selected_episode_id: str | None, authorization_time_utc: str, refresh_commit: str, refresh_evidence_checksum: str, candidate_inventory_checksum: str) -> dict[str, Any]:
    """Bind only the exact candidate the user supplied; no fallback or ranking."""
    if not selected_episode_id:
        raise EpisodeSelectionError("EXPLICIT_USER_SELECTION_REQUIRED")
    if candidate_number < 1 or candidate_number > len(candidates):
        raise EpisodeSelectionError("SELECTED_CANDIDATE_NUMBER_UNKNOWN")
    selected = dict(candidates[candidate_number - 1])
    if selected["episode_id"] != selected_episode_id:
        raise EpisodeSelectionError("SELECTED_EPISODE_IDENTITY_MISMATCH")
    if utc(authorization_time_utc) >= utc(selected["forecast_cutoff_ts"]):
        raise EpisodeSelectionError("SELECTED_EPISODE_CUTOFF_PASSED")
    content_checksum = checksum(selected)
    identity = {"authorization_name": AUTHORIZATION_NAME, "schema_version": "1", "route_b_freeze_fingerprint": ROUTE_B_FREEZE, "r6_authorization_v3_fingerprint": R6_V3, "native_attention_authorization_fingerprint": NATIVE_ATTENTION_AUTH, "episode_refresh_commit": refresh_commit, "episode_refresh_evidence_checksum": refresh_evidence_checksum, "candidate_inventory_checksum": candidate_inventory_checksum, "selection_method": SELECTION_METHOD, "selected_candidate_number": candidate_number, "selected_episode_identity": selected["episode_id"], "primary_event_identity": selected["primary_event_id"], "secondary_event_identities": [event_id for event_id in selected["member_event_ids"] if event_id != selected["primary_event_id"]], "release_time": selected["release_ts"], "forecast_cutoff": selected["forecast_cutoff_ts"], "market_session_context": selected["market_session_context"], "episode_schema_version": selected["schema_version"], "episode_content_checksum": content_checksum, "gemini": {"provider": "Gemini", "model": "gemini-2.5-flash-lite", "attention_call_budget": 1, "retry_count": 0}, "one_run_only": True, "fallback_episode_prohibited": True, "forecast_calls_prohibited": True, "acquisition_prohibited": True, "google_scientific_writes_prohibited": True, "outcome_prohibited": True, "evaluation_prohibited": True}
    return {"manifest": identity, "fingerprint": checksum(identity), "selected_episode": selected}
