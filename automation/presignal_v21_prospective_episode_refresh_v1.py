"""Pure canonical Episode refresh reporting for the bounded R6 Event window.

Event retrieval and Event-sheet persistence remain owned by the existing FMP
Apps Script route.  This module consumes its returned Event-shaped rows and
uses the approved v2.1 Episode builder without altering any scientific rule.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from automation import build_presignal_v21_episodes as episodes


class EpisodeRefreshError(ValueError):
    pass


def _utc(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def canonical_events(rows: Iterable[Mapping[str, Any]], *, window_start_utc: str, window_end_utc: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Apply existing Event conversion only inside the caller-supplied UTC window."""
    start, end = _utc(window_start_utc), _utc(window_end_utc)
    accepted, rejected = [], []
    seen: dict[str, dict[str, Any]] = {}
    for source in rows:
        row = dict(source)
        row["release_ts"] = episodes.utc_timestamp(row.get("release_ts"))
        release = _utc(row["release_ts"])
        if not (start <= release <= end):
            rejected.append({"source_row": row.get("source_row"), "event_id": row.get("event_id", ""), "classification": "OUTSIDE_REFRESH_WINDOW"})
            continue
        try:
            normalized = episodes.source_record(row)
        except episodes.EpisodeBuildError as exc:
            rejected.append({"source_row": row.get("source_row"), "event_id": row.get("event_id", ""), "classification": "SCHEMA_INVALID", "reason": str(exc)})
            continue
        normalized["source_row"] = row.get("source_row")
        locator = episodes.contract.event_record_locator(normalized)
        prior = seen.get(locator)
        if prior and prior != normalized:
            raise EpisodeRefreshError("DUPLICATE_CONFLICT:" + locator)
        if prior:
            rejected.append({"source_row": row.get("source_row"), "event_id": normalized["event_id"], "classification": "ALREADY_MATERIALIZED_IDENTICAL"})
            continue
        seen[locator] = normalized
        accepted.append(normalized)
    return sorted(accepted, key=lambda item: (item["release_ts"], str(item["source_row"]))), rejected


def construct_episodes(events: Iterable[Mapping[str, Any]], *, as_of_utc: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Call the frozen grouping/primary assignment implementation unchanged."""
    source = [dict(row) for row in events]
    built, dispositions = episodes.build_population(source)
    now = _utc(as_of_utc)
    result = []
    for episode in sorted(built, key=lambda item: (item["release_ts"], item["episode_id"])):
        release, cutoff = _utc(episode["release_ts"]), _utc(episode["forecast_cutoff_ts"])
        classification = "ELIGIBLE_UPCOMING" if release > now and cutoff > now else ("FUTURE_BUT_CUTOFF_CLOSED" if release > now else "ALREADY_RELEASED")
        result.append({**episode, "market_session_context": episode["episode_family"], "eligibility": classification,
                       "secondary_event_identities": [event_id for event_id in episode["member_event_ids"] if event_id != episode["primary_event_id"]],
                       "construction_provenance": "automation/build_presignal_v21_episodes.py:build_population",
                       "primary_selection_basis": "frozen canonical member ordering: release_ts, event_row_locator, indicator_name, event_id",
                       "same_time_grouping_key": episode["country"] + "|" + episode["release_ts"] + "|" + ("batch_id" if episode["same_time_cluster_flag"] else "single")})
    return result, dispositions


def candidate_decision(episodes_out: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    eligible = [dict(item) for item in episodes_out if item.get("eligibility") == "ELIGIBLE_UPCOMING"]
    if not eligible:
        return {"decision": "PROSPECTIVE_EPISODE_REFRESH_COMPLETE_NO_OPEN_CUTOFF", "selected_candidate": None, "eligible_candidates": [], "selection_rule": "No open-cutoff canonical Episode."}
    if len(eligible) != 1:
        return {"decision": "PROSPECTIVE_EPISODE_REFRESH_COMPLETE_SELECTION_AMBIGUOUS", "selected_candidate": None, "eligible_candidates": eligible, "selection_rule": "No frozen R6 Episode-selection tie-break exists; no new ranking was applied."}
    return {"decision": "PROSPECTIVE_EPISODES_REFRESHED_NATIVE_ATTENTION_READY", "selected_candidate": eligible[0], "eligible_candidates": eligible, "selection_rule": "Exactly one open-cutoff canonical Episode."}
