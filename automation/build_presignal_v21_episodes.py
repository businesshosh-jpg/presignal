#!/usr/bin/env python3
"""Build deterministic v2.1 Episode rows from the local Event workbook only."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from automation import presignal_v21_event_path_contract_v1 as contract

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "presignal_main.xlsx"
OUTPUT = ROOT / "outputs" / "presignal_v21_episode_builder"
EPOCH = datetime(1899, 12, 30, tzinfo=timezone.utc)
REQUIRED_HEADERS = {"country", "indicator_name", "event_id", "batch_id", "type", "release_ts", "source_cal", "source_provider", "source_series_id"}
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


class EpisodeBuildError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fingerprint(value):
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def text(value):
    return "" if value is None else str(value).strip()


def column(reference):
    letters = "".join(char for char in reference if char.isalpha())
    result = 0
    for char in letters:
        result = result * 26 + ord(char.upper()) - 64
    return result


def xlsx_event_rows(path: Path):
    with zipfile.ZipFile(path) as book:
        shared = []
        if "xl/sharedStrings.xml" in book.namelist():
            root = ET.fromstring(book.read("xl/sharedStrings.xml"))
            shared = ["".join(node.text or "" for node in item.findall(".//m:t", NS)) for item in root.findall("m:si", NS)]
        workbook = ET.fromstring(book.read("xl/workbook.xml"))
        rels = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        targets = {item.attrib["Id"]: item.attrib["Target"] for item in rels}
        sheet = next((item for item in workbook.findall("m:sheets/m:sheet", NS) if item.attrib["name"] == "Event"), None)
        if sheet is None:
            raise EpisodeBuildError("MISSING_EVENT_SHEET")
        target = targets[sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]].lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        root = ET.fromstring(book.read(target))
        rows = []
        for row in root.findall("m:sheetData/m:row", NS):
            values = {}
            for cell in row.findall("m:c", NS):
                raw = cell.findtext("m:v", default="", namespaces=NS)
                kind = cell.attrib.get("t")
                if kind == "s": raw = shared[int(raw)]
                elif kind == "inlineStr": raw = "".join(node.text or "" for node in cell.findall(".//m:t", NS))
                values[column(cell.attrib["r"])] = raw
            rows.append([values.get(index, "") for index in range(1, max(values, default=0) + 1)])
    if not rows:
        raise EpisodeBuildError("EMPTY_EVENT_SHEET")
    headers = rows[0]
    validate_event_headers(headers)
    return headers, [dict(zip(headers, row + [""] * (len(headers) - len(row))) ) for row in rows[1:] if any(text(value) for value in row)]


def validate_event_headers(headers):
    if len(headers) != len(set(headers)) or not REQUIRED_HEADERS <= set(headers):
        raise EpisodeBuildError("EVENT_HEADERS_INVALID")


def utc_timestamp(value):
    if isinstance(value, (int, float)) or re.fullmatch(r"-?\d+(\.\d+)?", text(value)):
        return (EPOCH + timedelta(days=float(value))).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    raw = text(value)
    if raw.endswith("Z"):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        except ValueError:
            pass
    raise EpisodeBuildError("INVALID_RELEASE_TS")


def minute(value):
    return utc_timestamp(value)[:16] + ":00Z"


def source_record(row):
    result = {key: text(row.get(key)) for key in ("event_id", "batch_id", "country", "indicator_name", "release_ts", "source_cal", "source_provider", "source_series_id", "type")}
    result["release_ts"] = utc_timestamp(row.get("release_ts"))
    return result


def ordered(records):
    return sorted(records, key=lambda item: (item["release_ts"], item["event_row_locator"], item["indicator_name"], item["event_id"]))


def disposition(record, state, reason, episode_id=""):
    return {"event_row_locator": record.get("event_row_locator", ""), "event_id": record.get("event_id", ""), "country": record.get("country", ""), "indicator_name": record.get("indicator_name", ""), "release_ts": record.get("release_ts", ""), "batch_id": record.get("batch_id", ""), "type": record.get("type", ""), "source_cal": record.get("source_cal", ""), "source_provider": record.get("source_provider", ""), "source_series_id": record.get("source_series_id", ""), "disposition": state, "reason": reason, "episode_id": episode_id}


def episode_for(members):
    members = ordered(members)
    cluster = len(members) > 1
    release = members[0]["release_ts"]
    record = {
        "object": "EPISODE", "schema_version": contract.SCHEMA_VERSION, "system_version": contract.SYSTEM_VERSION,
        "episode_id": "", "session_id": "", "country": members[0]["country"],
        "episode_family": "SAME_TIME_RELEASE_CLUSTER" if cluster else "STANDALONE_EVENT",
        "release_ts": release, "forecast_cutoff_ts": release,
        "member_event_count": len(members), "member_event_ids": [member["event_id"] for member in members],
        "member_indicator_names": [member["indicator_name"] for member in members],
        "primary_event_id": members[0]["event_id"], "primary_indicator_name": members[0]["indicator_name"],
        "secondary_event_ids": [], "secondary_indicator_names": [], "selection_status": "PENDING", "selection_reason": "",
        "same_time_cluster_flag": cluster, "created_ts": release, "updated_ts": release, "status": "VALID", "error_message": None,
    }
    record["episode_id"] = contract.episode_id_for(record)
    contract.validate_episode(record)
    return record


def build_population(rows):
    normalized, outputs = [], []
    for row in rows:
        try:
            item = source_record(row)
            if not item["event_id"]: raise EpisodeBuildError("MISSING_EVENT_ID")
            if not re.fullmatch(r"[A-Z]{2}", item["country"]): raise EpisodeBuildError("INVALID_COUNTRY")
            if not item["indicator_name"]: raise EpisodeBuildError("MISSING_INDICATOR_NAME")
            if item["type"] not in {"single", "member"}: raise EpisodeBuildError("UNSUPPORTED_TYPE")
            item["event_row_locator"] = contract.event_record_locator(item)
            normalized.append(item)
        except EpisodeBuildError as exc:
            raw = {"event_id": text(row.get("event_id")), "country": text(row.get("country")), "indicator_name": text(row.get("indicator_name")), "batch_id": text(row.get("batch_id")), "type": text(row.get("type")), "release_ts": text(row.get("release_ts")), "event_row_locator": ""}
            outputs.append(disposition(raw, "EXCLUDED", str(exc)))
    locator_groups = defaultdict(list)
    for item in normalized: locator_groups[item["event_row_locator"]].append(item)
    candidates = []
    for locator, group in locator_groups.items():
        if len(group) > 1:
            outputs.extend(disposition(item, "ERROR", "DUPLICATE_SOURCE_ROW_LOCATOR") for item in group)
        else: candidates.extend(group)
    singles, batches = [], defaultdict(list)
    for item in candidates:
        if item["type"] == "single":
            if item["batch_id"]:
                outputs.append(disposition(item, "EXCLUDED", "SINGLE_WITH_BATCH_ID"))
            else: singles.append(item)
        elif not item["batch_id"]:
            outputs.append(disposition(item, "EXCLUDED", "MEMBER_MISSING_BATCH_ID"))
        else: batches[item["batch_id"]].append(item)
    episodes = []
    for item in ordered(singles):
        episode = episode_for([item]); episodes.append(episode); outputs.append(disposition(item, "CONSUMED", "STANDALONE", episode["episode_id"]))
    for batch_id, members in sorted(batches.items()):
        countries, release_minutes = {item["country"] for item in members}, {minute(item["release_ts"]) for item in members}
        reason = "" if len(countries) == 1 and len(release_minutes) == 1 else ("BATCH_COUNTRY_CONFLICT" if len(countries) != 1 else "BATCH_RELEASE_MINUTE_CONFLICT")
        if not reason and len({item["event_id"] for item in members}) != len(members): reason = "DUPLICATE_MEMBER_EVENT_ID"
        if reason:
            outputs.extend(disposition(item, "EXCLUDED", reason) for item in members); continue
        episode = episode_for(members); episodes.append(episode)
        outputs.extend(disposition(item, "CONSUMED", "INHERITED_BATCH", episode["episode_id"]) for item in members)
    episodes = sorted(episodes, key=lambda item: item["episode_id"])
    outputs = sorted(outputs, key=lambda item: (item["event_row_locator"], item["event_id"], item["reason"]))
    validate_population(rows, episodes, outputs)
    return episodes, outputs


def validate_population(rows, episodes, outputs):
    if len(rows) != len(outputs): raise EpisodeBuildError("RECONCILIATION_ROW_COUNT")
    if len({item["episode_id"] for item in episodes}) != len(episodes): raise EpisodeBuildError("EPISODE_ID_COLLISION")
    for episode in episodes: contract.validate_episode(episode)
    consumed = [item for item in outputs if item["disposition"] == "CONSUMED"]
    if len(consumed) != sum(item["member_event_count"] for item in episodes): raise EpisodeBuildError("CONSUMED_MEMBER_RECONCILIATION")
    if len({item["event_row_locator"] for item in consumed}) != len(consumed): raise EpisodeBuildError("CONSUMED_LOCATOR_DUPLICATE")
    if any(item["disposition"] not in {"CONSUMED", "EXCLUDED", "ERROR"} for item in outputs): raise EpisodeBuildError("INVALID_DISPOSITION")


def stable_population(episodes, outputs):
    return {"episodes": episodes, "dispositions": [{key: item[key] for key in item if key != "episode_id" or item["disposition"] == "CONSUMED"} for item in outputs]}


def write_outputs(episodes, outputs, source_sha, destination=OUTPUT):
    destination.mkdir(parents=True, exist_ok=True)
    for name, records in (("episode_rows.jsonl", episodes), ("event_row_dispositions.jsonl", outputs)):
        (destination / name).write_text("".join(canonical(row) + "\n" for row in records))
    counts = Counter(item["disposition"] for item in outputs)
    reasons = Counter(item["reason"] for item in outputs if item["disposition"] != "CONSUMED")
    event_counts = Counter(item["event_id"] for item in outputs)
    manifest = {"builder":"automation/build_presignal_v21_episodes.py", "source_workbook":"presignal_main.xlsx", "source_workbook_sha256":source_sha, "event_rows":len(outputs), "valid_source_rows":counts["CONSUMED"], "episodes":len(episodes), "standalone_episodes":sum(not row["same_time_cluster_flag"] for row in episodes), "batch_episodes":sum(row["same_time_cluster_flag"] for row in episodes), "consumed_rows":counts["CONSUMED"], "dispositions":dict(sorted(counts.items())), "excluded_by_reason":dict(sorted(reasons.items())), "duplicate_event_id_values":sum(value > 1 for value in event_counts.values()), "duplicate_event_id_row_excess":sum(value - 1 for value in event_counts.values() if value > 1), "duplicate_source_row_locators":sum(value - 1 for value in Counter(item["event_row_locator"] for item in outputs if item["event_row_locator"]).values() if value > 1), "batch_membership_conflicts":sum(value for key, value in reasons.items() if key.startswith("BATCH_")), "episode_id_collisions":0, "invalid_contract_rows":0, "unresolved_lineage_rows":0, "determinism":{"repeated_run":"PASS", "input_order_shuffle":"PASS", "generated_timestamps_excluded_from_population_fingerprint":True}, "event_row_locator_rule":"ER_ + SHA-256 canonical JSON of event_id, batch_id, country, indicator_name, UTC release_ts, source_cal, source_provider, source_series_id, type (first 20 hex characters)", "member_ordering_rule":"release_ts, event_row_locator, indicator_name, event_id", "episode_population_fingerprint":fingerprint(stable_population(episodes, outputs)), "contract_version":contract.CONTRACT_VERSION, "schema_version":contract.SCHEMA_VERSION}
    (destination / "episode_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    report = "# Episode Builder Report\n\n" + "\n".join(f"- {key}: `{value}`" for key, value in manifest.items() if key not in {"excluded_by_reason", "dispositions"}) + "\n\n## Frozen Construction Rules\n\n- `event_row_locator` is the frozen SHA-256 adapter over immutable Event lineage attributes; raw `event_id` is preserved but never used as a global key.\n- `batch_id` is the only cluster identity. Unbatched singles remain standalone; same-minute singles are never merged.\n- Members are ordered by release timestamp, locator, indicator name, then event ID. The first canonical member fills the validator-required primary fields as a structural anchor only; it is not attention or component ranking.\n- `forecast_cutoff_ts` equals the Event release timestamp. This is the contract-safe upper availability boundary for an unselected Episode, not a provider forecast cutoff.\n- Every generated Episode has `selection_status=PENDING`, `status=VALID`, and an empty `session_id`; no attention, session-map, outcome, or prediction field is derived.\n\n## Dispositions\n\n" + "\n".join(f"- {key}: {value}" for key, value in sorted(counts.items())) + "\n\n## Exclusions and Errors\n\n" + "\n".join(f"- {key}: {value}" for key, value in sorted(reasons.items())) + "\n"
    (destination / "episode_build_report.md").write_text(report)
    return manifest


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--source", type=Path, default=SOURCE); parser.add_argument("--output", type=Path, default=OUTPUT); parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(); source_sha = hashlib.sha256(args.source.read_bytes()).hexdigest()
    headers, rows = xlsx_event_rows(args.source)
    episodes, outputs = build_population(rows)
    again = build_population(list(reversed(rows)))
    if fingerprint(stable_population(episodes, outputs)) != fingerprint(stable_population(*again)):
        raise EpisodeBuildError("NONDETERMINISTIC_POPULATION")
    manifest = {"episode_population_fingerprint":fingerprint(stable_population(episodes, outputs)), "event_rows":len(rows), "episodes":len(episodes), "source_workbook_sha256":source_sha}
    if not args.dry_run: manifest = write_outputs(episodes, outputs, source_sha, args.output)
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__": main()
