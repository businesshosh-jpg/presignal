#!/usr/bin/env python3
"""Authorized four-row frozen event-identity correction for one paused replay."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "outputs" / "phase9_authoritative_historical_replay" / "9-AUTHORITATIVE-HISTORICAL-REPLAY-20260717T094156Z"
RUN_ID = "9-AUTHORITATIVE-HISTORICAL-REPLAY-20260717T094156Z"
TARGETS = {
    ("US|2024-08-16|CUSTOM_CONFIG_WINDOW", "CFTC Gold Speculative net positions", 5),
    ("US|2024-08-16|CUSTOM_CONFIG_WINDOW", "CFTC Natural Gas speculative net positions", 7),
    ("US|2025-03-18|CUSTOM_CONFIG_WINDOW", "Building Permits MoM (Feb)", 2),
    ("US|2025-03-18|CUSTOM_CONFIG_WINDOW", "Export Prices MoM (Feb)", 3),
}


def canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def sha(value: Any) -> str:
    return hashlib.sha256(canon(value).encode()).hexdigest()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[Dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_rows(path: Path, values: Iterable[Mapping[str, Any]]) -> None:
    path.write_text("".join(canon(value) + "\n" for value in values))


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def immutable_member_content(row: Mapping[str, Any]) -> Dict[str, Any]:
    return {key: row.get(key) for key in (
        "session_id", "batch_id", "country", "indicator_name", "genre", "importance", "consensus_value",
        "prev_revision", "release_ts", "same_minute_group_key", "member_order", "source_sheet", "type",
    )}


def replacement_id(row: Mapping[str, Any]) -> str:
    return "EIDR_" + sha(immutable_member_content(row))[:24]


def build_mapping(members: list[Dict[str, Any]]) -> tuple[Dict[tuple[str, str, int], Dict[str, Any]], Dict[str, list[Dict[str, Any]]]]:
    by_key: Dict[tuple[str, str, int], Dict[str, Any]] = {}
    by_old: Dict[str, list[Dict[str, Any]]] = {}
    for row in members:
        key = (str(row.get("session_id")), str(row.get("indicator_name")), int(row.get("member_order") or 0))
        if key not in TARGETS:
            continue
        old, new = str(row["event_id"]), replacement_id(row)
        by_key[key] = {"old_event_id": old, "new_event_id": new, "source_row": dict(row), "source_row_sha256": sha(row)}
        by_old.setdefault(old, []).append(by_key[key])
    if len(by_key) != 4 or set(by_old) != {"070b-5b8f-0497-0223", "bfaa-bba2-b392-a77a"}:
        raise RuntimeError("TARGET_FOUR_SOURCE_ROWS_NOT_FOUND")
    if len({record["new_event_id"] for record in by_key.values()}) != 4:
        raise RuntimeError("REPLACEMENT_EVENT_ID_COLLISION")
    return by_key, by_old


def _session_replacements(session_id: str, old_id: str, by_old: Mapping[str, list[Dict[str, Any]]]) -> list[str]:
    records = [record for record in by_old.get(old_id, []) if record["source_row"]["session_id"] == session_id]
    return [record["new_event_id"] for record in sorted(records, key=lambda record: int(record["source_row"]["member_order"]))]


def _rewrite(value: Any, *, session_id: str, by_key: Mapping[tuple[str, str, int], Dict[str, Any]], by_old: Mapping[str, list[Dict[str, Any]]]) -> Any:
    if isinstance(value, list):
        # Calendar-derived lineage lists preserve source-member ordering but
        # omit indicator names.  Where a list contains each duplicate exactly
        # once, map its ordered occurrences to the immutable member-order map.
        occurrence_counts: Dict[str, int] = {}
        for item in value:
            if isinstance(item, dict) and isinstance(item.get("event_id"), str) and item["event_id"] in by_old and not item.get("indicator_name"):
                occurrence_counts[item["event_id"]] = occurrence_counts.get(item["event_id"], 0) + 1
        sequence_index = {old: 0 for old in occurrence_counts}
        rewritten = []
        for item in value:
            if isinstance(item, str) and item in by_old:
                # Request-attention lists carried only the ambiguous legacy
                # identifier.  Expanding it to both repaired immutable members
                # preserves the original relation without selecting one.
                rewritten.extend(_session_replacements(session_id, item, by_old))
                continue
            if isinstance(item, dict) and isinstance(item.get("event_id"), str) and item["event_id"] in occurrence_counts and not item.get("indicator_name"):
                old = item["event_id"]
                replacements = _session_replacements(session_id, old, by_old)
                if occurrence_counts[old] != len(replacements):
                    raise RuntimeError("AMBIGUOUS_DUPLICATE_EVENT_ID_LIST_REFERENCE:" + session_id + ":" + old)
                item = {**item, "event_id": replacements[sequence_index[old]]}
                sequence_index[old] += 1
            rewritten.append(_rewrite(item, session_id=session_id, by_key=by_key, by_old=by_old))
        return rewritten
    if isinstance(value, dict):
        local_session = str(value.get("session_id") or session_id)
        key = (local_session, str(value.get("indicator_name") or ""), int(value.get("member_order") or 0))
        record = by_key.get(key)
        if record is None and value.get("indicator_name"):
            candidates = [candidate for candidate in by_key.values() if candidate["source_row"]["session_id"] == local_session and candidate["source_row"]["indicator_name"] == value.get("indicator_name")]
            record = candidates[0] if len(candidates) == 1 else None
        out = {}
        for name, item in value.items():
            if name == "event_id" and record is not None:
                out[name] = record["new_event_id"]
            else:
                out[name] = _rewrite(item, session_id=local_session, by_key=by_key, by_old=by_old)
        return out
    if not isinstance(value, str):
        return value
    if value in by_old:
        replacements = _session_replacements(session_id, value, by_old)
        if len(replacements) != 1:
            raise RuntimeError("AMBIGUOUS_BARE_DUPLICATE_EVENT_ID_REFERENCE:" + session_id + ":" + value)
        return replacements[0]
    if value.lstrip().startswith(("{", "[")):
        try:
            return json.dumps(_rewrite(json.loads(value), session_id=session_id, by_key=by_key, by_old=by_old), sort_keys=True)
        except json.JSONDecodeError:
            return value
    if "|" in value:
        parts = value.split("|")
        rewritten = []
        for part in parts:
            replacements = _session_replacements(session_id, part, by_old)
            rewritten.extend(replacements or [part])
        return "|".join(rewritten)
    return value


def apply(package: Path, *, dry_run: bool) -> Dict[str, Any]:
    package = package.resolve()
    snapshot = package / "input_snapshot"
    members_path = snapshot / "authoritative_session_members.jsonl"
    original_members = rows(members_path)
    by_key, by_old = build_mapping(original_members)
    existing_ids = {str(row["event_id"]) for row in original_members}
    if any(record["new_event_id"] in existing_ids for record in by_key.values()):
        raise RuntimeError("REPLACEMENT_ID_ALREADY_EXISTS")
    corrected_members = []
    for row in original_members:
        key = (str(row.get("session_id")), str(row.get("indicator_name")), int(row.get("member_order") or 0))
        corrected_members.append({**row, "event_id": by_key[key]["new_event_id"]} if key in by_key else dict(row))
    grouped: Dict[str, list[Dict[str, Any]]] = {}
    for row in corrected_members:
        grouped.setdefault(str(row["session_id"]), []).append(row)
    if any(len({row["event_id"] for row in values}) != len(values) for values in grouped.values()):
        raise RuntimeError("POST_REPAIR_SESSION_EVENT_ID_NOT_UNIQUE")
    corrected_files: Dict[str, list[Dict[str, Any]]] = {"authoritative_session_members.jsonl": corrected_members}
    for name in ("authoritative_sessions.jsonl", "authoritative_pack_references.jsonl", "authoritative_requests.jsonl"):
        values = []
        for row in rows(snapshot / name):
            sid = str(row.get("session_id") or "")
            rewritten = _rewrite(row, session_id=sid, by_key=by_key, by_old=by_old)
            if name == "authoritative_sessions.jsonl" and sid in grouped:
                rewritten["member_event_ids"] = "|".join(row["event_id"] for row in sorted(grouped[sid], key=lambda item: int(item.get("member_order") or 0)))
                rewritten["session_fingerprint"] = sha(grouped[sid])
            values.append(rewritten)
        corrected_files[name] = values
    remaining_old = []
    for name, values in corrected_files.items():
        text = "\n".join(canon(value) for value in values)
        for old in by_old:
            if old in text:
                remaining_old.append(name + ":" + old)
    if remaining_old:
        raise RuntimeError("DEPENDENT_REFERENCE_NOT_REPAIRED:" + ",".join(remaining_old))
    config_path = package / "execution" / "frozen_execution_configuration.json"
    provider_config_path = snapshot / "authoritative_provider_model_config.json"
    config = json.loads(config_path.read_text())
    correction = {
        "repair_type": "TARGETED_FROZEN_DUPLICATE_EVENT_IDENTITY_REPAIR_V1",
        "run_id": RUN_ID,
        "replacement_derivation": "EIDR_SHA256_OF_IMMUTABLE_SOURCE_MEMBER_CONTENT_PREFIX_24",
        "mapping": [{
            "session_id": record["source_row"]["session_id"], "indicator_name": record["source_row"]["indicator_name"],
            "member_order": record["source_row"]["member_order"], "old_event_id": record["old_event_id"],
            "new_event_id": record["new_event_id"], "source_row_sha256": record["source_row_sha256"],
            "original_source_row": record["source_row"],
        } for record in sorted(by_key.values(), key=lambda record: (record["source_row"]["session_id"], int(record["source_row"]["member_order"])))],
        "scientific_content_equality": "PASS_WITH_AUTHORIZED_FOUR_EVENT_ID_CORRECTION_ONLY",
    }
    new_config = {**config, "targeted_event_identity_correction": correction}
    component_paths = {
        name: snapshot / name for name in json.loads((snapshot / "authoritative_replay_input_manifest.json").read_text())["component_fingerprints"]
    }
    component_fingerprints = {}
    for name, path in component_paths.items():
        if name in corrected_files:
            component_fingerprints[name] = hashlib.sha256("".join(canon(row) + "\n" for row in corrected_files[name]).encode()).hexdigest()
        elif name == "authoritative_provider_model_config.json":
            component_fingerprints[name] = hashlib.sha256((json.dumps(new_config, indent=2, sort_keys=True) + "\n").encode()).hexdigest()
        else:
            component_fingerprints[name] = file_sha(path)
    manifest_path = snapshot / "authoritative_replay_input_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    new_manifest = {**manifest, "component_fingerprints": component_fingerprints, "configuration_fingerprint": sha(new_config), "snapshot_fingerprint": sha(component_fingerprints)}
    report = {
        "status": "PASS", "run_id": RUN_ID, "affected_rows": correction["mapping"],
        "old_to_new_mapping": [{"old_event_id": row["old_event_id"], "new_event_id": row["new_event_id"]} for row in correction["mapping"]],
        "dependent_files_updated": sorted(corrected_files), "eligible_sessions": len(grouped),
        "members_before": len(original_members), "members_after": len(corrected_members),
        "unique_event_ids_after": sum(len({row["event_id"] for row in values}) for values in grouped.values()),
        "snapshot_fingerprint": new_manifest["snapshot_fingerprint"], "configuration_fingerprint": new_manifest["configuration_fingerprint"],
    }
    if not dry_run:
        for name, values in corrected_files.items(): write_rows(snapshot / name, values)
        write_json(config_path, new_config); write_json(provider_config_path, new_config); write_json(manifest_path, new_manifest)
        package_manifest_path = package / "manifests" / "package_manifest.json"
        package_manifest = json.loads(package_manifest_path.read_text())
        write_json(package_manifest_path, {**package_manifest, "configuration_fingerprint": sha(new_config), "snapshot_fingerprint": new_manifest["snapshot_fingerprint"]})
        metadata_path = package / "active_store" / "store_metadata.json"
        metadata = json.loads(metadata_path.read_text())
        write_json(metadata_path, {**metadata, "configuration_fingerprint": sha(new_config), "snapshot_fingerprint": new_manifest["snapshot_fingerprint"]})
        write_json(package / "execution" / "targeted_event_identity_correction.json", {**correction, "report": report})
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", default=str(PACKAGE))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(apply(Path(args.package), dry_run=not args.apply), sort_keys=True))
