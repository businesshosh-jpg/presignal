#!/usr/bin/env python3
"""Build deterministic v2.1 Episode roles and canonical USD/JPY Outcomes."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import shutil
import sys
import tempfile
import zipfile
from bisect import bisect_right
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from automation import build_presignal_v21_episodes as episode_builder
from automation import presignal_v21_event_path_contract_v1 as contract
from automation import repair_presignal_v21_event_lineage as workbook_io

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "presignal_main.xlsx"
EPISODE_OUTPUT = ROOT / "outputs" / "presignal_v21_episode_builder"
OUTPUT = ROOT / "outputs" / "presignal_v21_episode_outcomes"
ENDPOINT_DEPLOYMENT = "AKfycbw-SXeE8pE85mISnpH_xygFLjgysQqGpzAmcj9h8P9kRg4LCq3iI7BnoB5hYL-x72xN"
ENDPOINT_FUNCTION = "apiFetchGovernedHistoricalUsdJpyObservation"
HORIZONS = (5, 15, 30, 60)
NS = workbook_io.NS
MAIN_NS = workbook_io.MAIN_NS
IMPORTANCE = {"high": 4, "medium": 3, "low": 2, "unknown": 1, "": 1}


class EpisodeOutcomeError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fingerprint(value):
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def iso(value):
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path):
    return json.loads(path.read_text())


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_jsonl(path, rows):
    path.write_text("".join(canonical(row) + "\n" for row in rows))


def importance_rank(record):
    return IMPORTANCE.get(str(record.get("importance", "")).strip().lower(), 1)


def consumed_event_records(source):
    _, rows = episode_builder.xlsx_event_rows(source)
    records = {}
    for row in rows:
        try:
            record = episode_builder.source_record(row)
            record["event_row_locator"] = contract.event_record_locator(record)
            record["importance"] = str(row.get("importance", "")).strip().lower()
            records[record["event_row_locator"]] = record
        except episode_builder.EpisodeBuildError:
            continue
    return records


def load_episode_population(source):
    manifest = read_json(EPISODE_OUTPUT / "episode_manifest.json")
    source_sha = sha(source)
    if manifest["source_workbook_sha256"] != source_sha:
        completed_manifest = OUTPUT / "episode_outcome_manifest.json"
        accepted_outcome_update = completed_manifest.exists() and read_json(completed_manifest).get("source_workbook_sha256_before") == manifest["source_workbook_sha256"] and read_json(completed_manifest).get("preview_workbook_sha256") == source_sha
        if not accepted_outcome_update:
            raise EpisodeOutcomeError("EPISODE_BUILDER_SOURCE_FINGERPRINT_MISMATCH")
    episodes = read_jsonl(EPISODE_OUTPUT / "episode_rows.jsonl")
    dispositions = read_jsonl(EPISODE_OUTPUT / "event_row_dispositions.jsonl")
    if len(episodes) != 1682 or Counter(item["disposition"] for item in dispositions) != Counter({"CONSUMED": 4314, "EXCLUDED": 1}):
        raise EpisodeOutcomeError("EPISODE_POPULATION_UNEXPECTED")
    return episodes, dispositions


def assign_component_roles(episodes, dispositions, records):
    consumed = {item["event_row_locator"]: item["episode_id"] for item in dispositions if item["disposition"] == "CONSUMED"}
    by_episode_member = defaultdict(list)
    for locator, episode_id in consumed.items():
        record = records.get(locator)
        if record:
            by_episode_member[(episode_id, record["event_id"], record["indicator_name"])].append(record)
    assigned, ledger = [], []
    for episode in sorted(episodes, key=lambda item: item["episode_id"]):
        members = []
        for event_id, indicator in zip(episode["member_event_ids"], episode["member_indicator_names"]):
            candidates = by_episode_member[(episode["episode_id"], event_id, indicator)]
            if len(candidates) != 1:
                raise EpisodeOutcomeError("EPISODE_MEMBER_LINEAGE_AMBIGUOUS:" + episode["episode_id"])
            members.append(candidates[0])
        members = episode_builder.ordered(members)
        highest = max(importance_rank(member) for member in members)
        primary = next(member for member in members if importance_rank(member) == highest)
        secondary = [member for member in members if member is not primary and importance_rank(member) == highest]
        updated = dict(episode)
        updated["primary_event_id"] = primary["event_id"]
        updated["primary_indicator_name"] = primary["indicator_name"]
        updated["secondary_event_ids"] = [member["event_id"] for member in secondary]
        updated["secondary_indicator_names"] = [member["indicator_name"] for member in secondary]
        updated["updated_ts"] = episode["release_ts"]
        contract.validate_episode(updated)
        assigned.append(updated)
        for member in members:
            role = "PRIMARY_COMPONENT" if member is primary else "SECONDARY_COMPONENT" if member in secondary else "SUPPORTING_COMPONENT"
            ledger.append({"episode_id": updated["episode_id"], "event_row_locator": member["event_row_locator"], "event_id": member["event_id"], "indicator_name": member["indicator_name"], "component_role": role, "role_rank": importance_rank(member), "role_basis": "PRE_RELEASE_IMPORTANCE_RANK_THEN_CANONICAL_MEMBER_ORDER"})
    if len(ledger) != len(consumed) or len({item["event_row_locator"] for item in ledger}) != len(ledger):
        raise EpisodeOutcomeError("COMPONENT_ROLE_RECONCILIATION")
    return assigned, sorted(ledger, key=lambda item: (item["episode_id"], item["event_row_locator"]))


def required_windows(episodes):
    """Return merged UTC windows needed for anchors, horizons, and excursions."""
    windows = defaultdict(list)
    for episode in episodes:
        release = utc(episode["release_ts"])
        start, end = release - timedelta(seconds=60), release + timedelta(minutes=60)
        cursor = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
        while cursor <= end:
            next_day = cursor + timedelta(days=1)
            windows[cursor.date()].append((max(start, cursor), min(end, next_day - timedelta(microseconds=1))))
            cursor = next_day
    merged = {}
    for day, day_windows in windows.items():
        ordered = sorted(day_windows)
        compact = []
        for start, end in ordered:
            if compact and start <= compact[-1][1] + timedelta(seconds=1):
                compact[-1] = (compact[-1][0], max(compact[-1][1], end))
            else:
                compact.append((start, end))
        merged[day] = compact
    return merged


def required_days(episodes):
    return sorted(required_windows(episodes))


def endpoint_request(day, service_factory, request_id):
    from automation.google_clients import run_script_function
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1) - timedelta(minutes=1)
    result = run_script_function(service_factory(), ENDPOINT_DEPLOYMENT, ENDPOINT_FUNCTION, [{
        "request_identity": request_id,
        "instrument": "USD/JPY",
        "requested_window_start": iso(start),
        "requested_window_end": iso(end),
        "timezone": "UTC",
    }])
    return {"request_id": request_id, "day": str(day), "window_start": iso(start), "window_end": iso(end), "response": result}


def compact_request_lineage(lineage):
    """Keep endpoint provenance without duplicating raw daily observations per Outcome."""
    compact = {key: lineage.get(key, "") for key in ("request_id", "day", "window_start", "window_end", "status", "selected_provider", "returned_observation_count", "transport_error")}
    compact["provider_attempts"] = [
        {key: value for key, value in attempt.items() if key != "observations"}
        for attempt in lineage.get("provider_attempts", [])
    ]
    return compact


def cache_rows(path):
    if not path.exists():
        return {}
    return {row["day"]: row for row in read_jsonl(path) if row.get("day")}


def write_cache_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(path, [rows[day] for day in sorted(rows)])


def acquire_daily_observations(episodes, cache_path, max_workers=2, day_offset=0, day_limit=None, require_complete=True):
    """Acquire a deterministic slice and retain only contract-relevant observations."""
    from automation.google_clients import build_script_service, load_credentials
    windows = required_windows(episodes)
    days = sorted(windows)
    cached = cache_rows(cache_path)
    selected_days = days[day_offset:day_offset + day_limit if day_limit is not None else None]
    pending_days = [day for day in selected_days if str(day) not in cached]

    def service_factory():
        return build_script_service(load_credentials())

    requests = [(day, "MD_DAY_" + hashlib.sha256(str(day).encode()).hexdigest()[:20]) for day in pending_days]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(endpoint_request, day, service_factory, request_id): (day, request_id) for day, request_id in requests}
        for future in concurrent.futures.as_completed(futures):
            day, request_id = futures[future]
            try:
                response = future.result()
            except Exception as exc:
                response = {"request_id": request_id, "day": str(day), "window_start": "", "window_end": "", "response": None, "error": str(exc)}
            payload = response.get("response") or {}
            request_lineage = {key: response.get(key, "") for key in ("request_id", "day", "window_start", "window_end")}
            request_lineage.update({"status": payload.get("status", "TRANSPORT_FAILURE"), "selected_provider": payload.get("selected_provider", ""), "returned_observation_count": payload.get("returned_observation_count", 0), "provider_attempts": payload.get("provider_attempts", []), "transport_error": response.get("error", "")})
            accepted = []
            for observation in payload.get("observations", []):
                observed_at = utc(observation["returned_observation_timestamp"])
                if not any(start <= observed_at <= end for start, end in windows[day]):
                    continue
                timestamp = iso(observed_at)
                accepted.append({"timestamp": timestamp, "close": float(observation["accepted_raw_price"]), "provider": payload.get("selected_provider", ""), "request_id": response["request_id"], "provider_returned_timestamp_raw": observation.get("provider_returned_timestamp_raw"), "accepted_raw_price_field": observation.get("accepted_raw_price_field", "close")})
            cached[str(day)] = {"day": str(day), "request_lineage": compact_request_lineage(request_lineage), "observations": accepted}
    if requests:
        write_cache_rows(cache_path, cached)
    if set(cached) != {str(day) for day in days} and require_complete:
        missing = sorted({str(day) for day in days} - set(cached))
        raise EpisodeOutcomeError("MARKET_DATA_CACHE_INCOMPLETE:" + ",".join(missing))
    if not require_complete:
        return [], {}, len(requests), len(cached)
    by_timestamp = defaultdict(list)
    request_lineage = {}
    for day in days:
        if str(day) not in cached:
            continue
        row = cached[str(day)]
        request_lineage[str(day)] = compact_request_lineage(row["request_lineage"])
        for observation in row["observations"]:
            by_timestamp[observation["timestamp"]].append(observation)
    observations = []
    for timestamp, candidates in by_timestamp.items():
        observations.append(sorted(candidates, key=lambda item: (item["provider"], item["request_id"]))[0])
    return sorted(observations, key=lambda item: item["timestamp"]), request_lineage, len(requests), len(cached)


class ObservationIndex:
    def __init__(self, observations):
        self.observations = sorted(observations, key=lambda item: item["timestamp"])
        self.timestamps = [utc(item["timestamp"]) for item in self.observations]

    def latest_at_or_before(self, target):
        position = bisect_right(self.timestamps, target) - 1
        if position < 0 or (target - self.timestamps[position]).total_seconds() > 60:
            return None
        return self.observations[position]

    def between(self, start, end):
        left = bisect_right(self.timestamps, start - timedelta(microseconds=1))
        right = bisect_right(self.timestamps, end)
        return self.observations[left:right]


def latest_accepted(observations, target):
    index = observations if isinstance(observations, ObservationIndex) else ObservationIndex(observations)
    return index.latest_at_or_before(target)


def intervening_flags(episodes):
    releases = sorted(utc(item["release_ts"]) for item in episodes)
    flags = {}
    for episode in episodes:
        release = utc(episode["release_ts"])
        position = bisect_right(releases, release)
        flags[episode["episode_id"]] = position < len(releases) and releases[position] <= release + timedelta(minutes=60)
    return flags


def outcome_record(episode, observations, request_lineage, intervening, acquisition_ts):
    observations = observations if isinstance(observations, ObservationIndex) else ObservationIndex(observations)
    release = utc(episode["release_ts"])
    anchor = latest_accepted(observations, release)
    horizon_observations = {horizon: latest_accepted(observations, release + timedelta(minutes=horizon)) for horizon in HORIZONS}
    provider_set = sorted({item["provider"] for item in [anchor, *horizon_observations.values()] if item})
    provider = ",".join(provider_set)
    missing = []
    if not anchor:
        missing.append("ANCHOR")
    missing.extend(f"PRICE_{horizon}M" for horizon, item in horizon_observations.items() if not item)
    episode_days = sorted({str(release.date()), str((release + timedelta(minutes=60)).date())})
    lineage = {"instrument": "USD/JPY", "endpoint_deployment": ENDPOINT_DEPLOYMENT, "request_windows": [request_lineage[day] for day in episode_days if day in request_lineage], "anchor_observation_ts": anchor["timestamp"] if anchor else None, "horizon_observation_ts": {str(horizon): horizon_observations[horizon]["timestamp"] for horizon in HORIZONS if horizon_observations[horizon]}, "selected_observations": {"anchor": anchor, **{str(horizon): horizon_observations[horizon] for horizon in HORIZONS if horizon_observations[horizon]}}}
    base = {"object": "OUTCOME", "schema_version": contract.SCHEMA_VERSION, "system_version": contract.SYSTEM_VERSION, "outcome_id": "", "episode_id": episode["episode_id"], "session_id": episode["session_id"], "release_ts": episode["release_ts"], "anchor_price_ts": None, "anchor_price": None, "price_5m": None, "price_15m": None, "price_30m": None, "price_60m": None, "pips_5m": None, "pips_15m": None, "pips_30m": None, "pips_60m": None, "direction_5m": "UNAVAILABLE", "direction_15m": "UNAVAILABLE", "direction_30m": "UNAVAILABLE", "direction_60m": "UNAVAILABLE", "max_up_pips": None, "max_down_pips": None, "max_up_ts": None, "max_down_ts": None, "initial_direction": None, "reversal_flag": None, "reversal_ts": None, "intervening_event_flag": intervening, "market_data_provider": provider, "source_lineage": lineage, "acquisition_ts": acquisition_ts, "outcome_fingerprint": "", "status": "UNAVAILABLE", "error_message": "MISSING_OR_STALE_" + "_".join(missing) if missing else ""}
    base["outcome_id"] = contract.outcome_id_for(base)
    if missing:
        base["outcome_fingerprint"] = contract._fingerprint(base, "outcome_fingerprint", ("acquisition_ts", "status", "error_message"))
        contract.validate_outcome(base)
        availability = "UNAVAILABLE" if not anchor else "PARTIAL"
        return base, availability
    base["status"] = "VALID"
    base["error_message"] = None
    base["anchor_price_ts"] = anchor["timestamp"]
    base["anchor_price"] = anchor["close"]
    for horizon, observation in horizon_observations.items():
        pips = round((observation["close"] - anchor["close"]) / 0.01, 2)
        base[f"price_{horizon}m"] = observation["close"]
        base[f"pips_{horizon}m"] = pips
        base[f"direction_{horizon}m"] = contract.direction_for_pips(pips)
    window = observations.between(release, release + timedelta(minutes=60))
    if not window:
        raise EpisodeOutcomeError("MAX_EXCURSION_OBSERVATIONS_MISSING")
    pips_window = [(round((item["close"] - anchor["close"]) / 0.01, 2), item) for item in window]
    max_up, max_up_observation = max(pips_window, key=lambda item: (item[0], -utc(item[1]["timestamp"]).timestamp()))
    max_down, max_down_observation = min(pips_window, key=lambda item: (item[0], utc(item[1]["timestamp"]).timestamp()))
    base.update({"max_up_pips": max_up, "max_down_pips": max_down, "max_up_ts": max_up_observation["timestamp"], "max_down_ts": max_down_observation["timestamp"]})
    directions = [base[f"direction_{horizon}m"] for horizon in HORIZONS]
    initial = next((direction for direction in directions if direction in {"UP", "DOWN"}), "FLAT")
    base["initial_direction"] = initial
    opposite = {"UP": "DOWN", "DOWN": "UP"}.get(initial)
    reversal_horizon = next((horizon for horizon in HORIZONS[1:] if opposite and base[f"direction_{horizon}m"] == opposite), None)
    base["reversal_flag"] = bool(reversal_horizon)
    base["reversal_ts"] = iso(release + timedelta(minutes=reversal_horizon)) if reversal_horizon else None
    base["outcome_fingerprint"] = contract._fingerprint(base, "outcome_fingerprint", ("acquisition_ts", "status", "error_message"))
    contract.validate_outcome(base)
    return base, "AVAILABLE"


def build_outcomes(episodes, observations, request_lineage, acquisition_ts):
    flags = intervening_flags(episodes)
    observations = ObservationIndex(observations)
    outcomes, availability, lineage = [], [], []
    for episode in sorted(episodes, key=lambda item: item["episode_id"]):
        try:
            outcome, disposition = outcome_record(episode, observations, request_lineage, flags[episode["episode_id"]], acquisition_ts)
        except Exception as exc:
            outcome = {"object": "OUTCOME", "schema_version": contract.SCHEMA_VERSION, "system_version": contract.SYSTEM_VERSION, "outcome_id": "", "episode_id": episode["episode_id"], "session_id": episode["session_id"], "release_ts": episode["release_ts"], "anchor_price_ts": None, "anchor_price": None, "price_5m": None, "price_15m": None, "price_30m": None, "price_60m": None, "pips_5m": None, "pips_15m": None, "pips_30m": None, "pips_60m": None, "direction_5m": "UNAVAILABLE", "direction_15m": "UNAVAILABLE", "direction_30m": "UNAVAILABLE", "direction_60m": "UNAVAILABLE", "max_up_pips": None, "max_down_pips": None, "max_up_ts": None, "max_down_ts": None, "initial_direction": None, "reversal_flag": None, "reversal_ts": None, "intervening_event_flag": flags[episode["episode_id"]], "market_data_provider": "", "source_lineage": {"instrument": "USD/JPY"}, "acquisition_ts": acquisition_ts, "outcome_fingerprint": "", "status": "UNAVAILABLE", "error_message": "OUTCOME_BUILD_ERROR:" + str(exc)}
            outcome["outcome_id"] = contract.outcome_id_for(outcome)
            outcome["outcome_fingerprint"] = contract._fingerprint(outcome, "outcome_fingerprint", ("acquisition_ts", "status", "error_message"))
            disposition = "ERROR"
        outcomes.append(outcome)
        availability.append({"episode_id": episode["episode_id"], "release_ts": episode["release_ts"], "anchor_available": outcome["anchor_price"] is not None, "price_5m_available": outcome["price_5m"] is not None, "price_15m_available": outcome["price_15m"] is not None, "price_30m_available": outcome["price_30m"] is not None, "price_60m_available": outcome["price_60m"] is not None, "max_excursion_available": outcome["max_up_pips"] is not None, "outcome_status": disposition, "unavailable_reason": outcome["error_message"] or "", "market_data_provider": outcome["market_data_provider"]})
        lineage.append({"episode_id": outcome["episode_id"], "outcome_id": outcome["outcome_id"], "market_data_provider": outcome["market_data_provider"], "source_lineage": outcome["source_lineage"]})
    if len(outcomes) != len(episodes) or len({item["outcome_id"] for item in outcomes}) != len(outcomes):
        raise EpisodeOutcomeError("OUTCOME_ID_RECONCILIATION")
    return outcomes, availability, lineage


def sheet_headers(path, sheet_name):
    shared, sheets = workbook_io.workbook_parts(path)
    with zipfile.ZipFile(path) as book:
        root = ET.fromstring(book.read(sheets[sheet_name]))
    header = root.find("m:sheetData/m:row", NS)
    return [workbook_io.cell_value(cell, shared) for cell in header.findall("m:c", NS)]


def encode_cell(cell, value):
    if value is None:
        return
    if isinstance(value, bool):
        cell.attrib["t"] = "b"
        value_node = ET.SubElement(cell, MAIN_NS + "v")
        value_node.text = "1" if value else "0"
        return
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        value_node = ET.SubElement(cell, MAIN_NS + "v")
        value_node.text = str(value)
        return
    cell.attrib["t"] = "inlineStr"
    inline = ET.SubElement(cell, MAIN_NS + "is")
    text = ET.SubElement(inline, MAIN_NS + "t")
    text.text = value if isinstance(value, str) else canonical(value)


def write_sheet_rows(root, headers, rows):
    sheet_data = root.find("m:sheetData", NS)
    for row in list(sheet_data)[1:]:
        sheet_data.remove(row)
    for row_index, record in enumerate(rows, start=2):
        row = ET.SubElement(sheet_data, MAIN_NS + "row", {"r": str(row_index)})
        for column_index, header in enumerate(headers, start=1):
            value = record.get(header)
            if value is None:
                continue
            cell = ET.SubElement(row, MAIN_NS + "c", {"r": workbook_io.column_letters(column_index) + str(row_index)})
            encode_cell(cell, value)
    dimension = root.find("m:dimension", NS)
    if dimension is not None:
        dimension.attrib["ref"] = f"A1:{workbook_io.column_letters(len(headers))}{len(rows) + 1}"


def write_preview(source, destination, episodes, outcomes):
    destination.parent.mkdir(parents=True, exist_ok=True)
    _, sheets = workbook_io.workbook_parts(source)
    episode_headers, outcome_headers = sheet_headers(source, "Episode"), sheet_headers(source, "Outcome")
    if episode_headers != contract.EPISODE_FIELDS or outcome_headers != contract.OUTCOME_FIELDS:
        raise EpisodeOutcomeError("WORKBOOK_HEADERS_CONTRACT_MISMATCH")
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(destination, "w") as output:
        for info in original.infolist():
            data = original.read(info.filename)
            if info.filename in {sheets["Episode"], sheets["Outcome"]}:
                root = ET.fromstring(data)
                write_sheet_rows(root, episode_headers if info.filename == sheets["Episode"] else outcome_headers, episodes if info.filename == sheets["Episode"] else outcomes)
                data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            output.writestr(info, data)


def workbook_change_audit(source, preview):
    before, after = workbook_io.logical_workbook_cells(source), workbook_io.logical_workbook_cells(preview)
    changed = {}
    for sheet in sorted(set(before) | set(after)):
        count = sum(before.get(sheet, {}).get(ref, "") != after.get(sheet, {}).get(ref, "") for ref in set(before.get(sheet, {})) | set(after.get(sheet, {})))
        if count:
            changed[sheet] = count
    invalid = {sheet: count for sheet, count in changed.items() if sheet not in {"Episode", "Outcome"}}
    if invalid:
        raise EpisodeOutcomeError("NON_TARGET_WORKBOOK_SHEET_CHANGED")
    return {"logical_cells_changed_by_sheet": changed, "non_episode_outcome_sheets_changed": len(invalid), "event_sheet_changed": "Event" in changed}


def stable_outcome_population(episodes, roles, outcomes):
    return {"episodes": [{key: item[key] for key in item if key not in {"created_ts", "updated_ts"}} for item in episodes], "roles": roles, "outcomes": [{key: item[key] for key in item if key != "acquisition_ts"} for item in outcomes]}


def write_artifacts(destination, roles, outcomes, availability, lineage, manifest, report):
    write_jsonl(destination / "episode_component_roles.jsonl", roles)
    write_jsonl(destination / "outcome_rows.jsonl", outcomes)
    write_jsonl(destination / "outcome_availability_ledger.jsonl", availability)
    write_jsonl(destination / "market_data_lineage.jsonl", lineage)
    write_json(destination / "episode_outcome_manifest.json", manifest)
    (destination / "episode_outcome_report.md").write_text(report)


def build(source=SOURCE, destination=OUTPUT, promote=False, max_workers=2):
    source, destination = Path(source), Path(destination)
    source_sha = sha(source)
    episodes, dispositions = load_episode_population(source)
    records = consumed_event_records(source)
    role_episodes, roles = assign_component_roles(episodes, dispositions, records)
    observations, requests, calls, cached_days = acquire_daily_observations(role_episodes, destination / "market_data_observation_cache.jsonl", max_workers=max_workers)
    acquired_at = iso(datetime.now(timezone.utc))
    outcomes, availability, lineage = build_outcomes(role_episodes, observations, requests, acquired_at)
    counts = Counter(item["outcome_status"] for item in availability)
    if sum(counts.values()) != len(role_episodes):
        raise EpisodeOutcomeError("OUTCOME_TERMINAL_RECONCILIATION")
    for outcome in outcomes:
        contract.validate_outcome(outcome)
    destination.mkdir(parents=True, exist_ok=True)
    preview = destination / "presignal_main_episode_outcome_preview.xlsx"
    write_preview(source, preview, role_episodes, outcomes)
    changes = workbook_change_audit(source, preview)
    population_fp = fingerprint(stable_outcome_population(role_episodes, roles, outcomes))
    manifest = {"decision": "V2_1_DETERMINISTIC_EPISODE_AND_OUTCOME_LAYER_VALIDATED", "source_workbook_sha256_before": source_sha, "preview_workbook_sha256": sha(preview), "episodes": len(role_episodes), "component_roles": dict(Counter(item["component_role"] for item in roles)), "outcome_terminal_dispositions": dict(counts), "market_data_provider_counts": dict(Counter(item["market_data_provider"] or "UNAVAILABLE" for item in outcomes)), "market_data_calls_this_build": calls, "market_data_cached_days": cached_days, "market_data_endpoint": {"deployment": ENDPOINT_DEPLOYMENT, "function": ENDPOINT_FUNCTION, "path": "apps_script/historical_market_data_endpoint.js"}, "coverage": {"anchor": sum(item["anchor_available"] for item in availability), **{str(horizon): sum(item[f"price_{horizon}m_available"] for item in availability) for horizon in HORIZONS}, "max_excursion": sum(item["max_excursion_available"] for item in availability)}, "reversals_detected": sum(item["reversal_flag"] is True for item in outcomes), "intervening_event_outcomes": sum(item["intervening_event_flag"] for item in outcomes), "outcome_population_fingerprint": population_fp, "workbook_change_audit": changes, "validation": {"one_role_per_consumed_event": len(roles) == 4314, "one_outcome_per_episode": len(outcomes) == len(role_episodes), "outcome_ids_unique": len({item["outcome_id"] for item in outcomes}) == len(outcomes), "contract_valid_outcomes": sum(item["status"] == "VALID" for item in outcomes), "errors": counts.get("ERROR", 0)}}
    report = "# Deterministic Episode and Outcome Layer\n\n## Decision\n\n`V2_1_DETERMINISTIC_EPISODE_AND_OUTCOME_LAYER_VALIDATED`\n\nRoles use pre-release importance rank (`high > medium > low > unknown`) and canonical member order. USD/JPY observations come only from the approved read-only historical endpoint in UTC daily windows. Missing or stale required prices produce contract-valid `UNAVAILABLE` Outcomes; the availability ledger distinguishes `PARTIAL` coverage.\n\n- Episodes: {}\n- Component roles: {}\n- Outcome terminal dispositions: {}\n- Market-data daily calls in this build: {}\n- Cached UTC days: {}\n- Outcome population fingerprint: `{}`\n".format(len(role_episodes), dict(Counter(item["component_role"] for item in roles)), dict(counts), calls, cached_days, population_fp)
    write_artifacts(destination, roles, outcomes, availability, lineage, manifest, report)
    if promote:
        shutil.copyfile(preview, source)
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--promote", action="store_true")
    parser.add_argument("--max-workers", type=int, default=2)
    parser.add_argument("--acquire-only", action="store_true")
    parser.add_argument("--day-offset", type=int, default=0)
    parser.add_argument("--day-limit", type=int)
    args = parser.parse_args()
    if args.acquire_only:
        episodes, dispositions = load_episode_population(args.source)
        role_episodes, _ = assign_component_roles(episodes, dispositions, consumed_event_records(args.source))
        _, _, calls, cached_days = acquire_daily_observations(role_episodes, args.output / "market_data_observation_cache.jsonl", args.max_workers, args.day_offset, args.day_limit, False)
        print(json.dumps({"acquired_days": calls, "cached_days": cached_days, "required_days": len(required_days(role_episodes))}, sort_keys=True))
    else:
        print(json.dumps(build(args.source, args.output, args.promote, args.max_workers), sort_keys=True))


if __name__ == "__main__":
    main()
