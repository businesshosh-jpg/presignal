#!/usr/bin/env python3
"""Apply only the audited v2.1 Event-lineage repairs and rebuild Episodes."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from automation import build_presignal_v21_episodes as builder

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "presignal_main.xlsx"
AUDIT = ROOT / "outputs" / "presignal_v21_episode_exclusion_audit"
OUTPUT = ROOT / "outputs" / "presignal_v21_event_lineage_repair"
EPISODE_OUTPUT = ROOT / "outputs" / "presignal_v21_episode_builder"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
MAIN_NS = "{" + NS["m"] + "}"


class RepairError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint(value):
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def load_json(path):
    return json.loads(path.read_text())


def load_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def js_int32(value):
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value & 0x80000000 else value


def legacy_uuid_from_string(seed):
    """Exact deterministic v2.0 post-pass UUID-ish generator from runner_rules_patch.js."""
    value = 0
    for char in seed:
        value = js_int32((value << 5) - value + ord(char))

    def segment(multiplier):
        return f"{js_int32(value * multiplier) & 0xFFFFFFFF:04x}"[-4:]

    return "-".join(segment(multiplier) for multiplier in (1, 13, 37, 73))


def minute_key(country, release_ts):
    return f"{country}|{builder.minute(release_ts)[:16]}Z"


def legacy_batch_id(country, release_ts):
    return legacy_uuid_from_string("batch|" + minute_key(country, release_ts))


def repaired_batch_id(country, release_ts):
    """Collision-safe extension for audited legacy batch-ID FNV collisions only."""
    seed = {
        "namespace": "presignal_v21_batch_lineage_repair_v1",
        "country": country,
        "release_minute": builder.minute(release_ts),
    }
    digest = hashlib.sha256(canonical(seed).encode()).hexdigest()[:16]
    return "-".join(digest[offset:offset + 4] for offset in range(0, 16, 4))


def repaired_event_id(record):
    """Narrow SHA-256 extension only for the four audited legacy FNV collisions."""
    seed = {
        "namespace": "presignal_v21_event_lineage_repair_v1",
        "country": record["country"],
        "indicator_name": record["indicator_name"],
        "release_minute": builder.minute(record["release_ts"]),
        "source_cal": record["source_cal"],
        "source_provider": record["source_provider"],
        "source_series_id": record["source_series_id"],
    }
    digest = hashlib.sha256(canonical(seed).encode()).hexdigest()[:16]
    return "-".join(digest[offset:offset + 4] for offset in range(0, 16, 4))


def column_letters(index):
    value, letters = index, ""
    while value:
        value, remainder = divmod(value - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def workbook_parts(path):
    with zipfile.ZipFile(path) as book:
        shared = []
        if "xl/sharedStrings.xml" in book.namelist():
            root = ET.fromstring(book.read("xl/sharedStrings.xml"))
            shared = ["".join(node.text or "" for node in item.findall(".//m:t", NS)) for item in root.findall("m:si", NS)]
        workbook = ET.fromstring(book.read("xl/workbook.xml"))
        rels = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        targets = {item.attrib["Id"]: item.attrib["Target"] for item in rels}
        sheets = {}
        for sheet in workbook.findall("m:sheets/m:sheet", NS):
            target = targets[sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]].lstrip("/")
            sheets[sheet.attrib["name"]] = target if target.startswith("xl/") else "xl/" + target
    return shared, sheets


def cell_value(cell, shared):
    if cell is None:
        return ""
    if cell.find("m:f", NS) is not None:
        return "=" + (cell.findtext("m:f", default="", namespaces=NS))
    kind = cell.attrib.get("t")
    if kind == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//m:t", NS))
    value = cell.findtext("m:v", default="", namespaces=NS)
    return shared[int(value)] if kind == "s" and value else value


def logical_workbook_cells(path):
    shared, sheets = workbook_parts(path)
    result = {}
    with zipfile.ZipFile(path) as book:
        for name, target in sheets.items():
            root = ET.fromstring(book.read(target))
            result[name] = {
                cell.attrib["r"]: cell_value(cell, shared)
                for cell in root.findall("m:sheetData/m:row/m:c", NS)
            }
    return result


def workbook_event_rows(path):
    numbered = []
    headers, rows = builder.xlsx_event_rows(path)
    with zipfile.ZipFile(path) as book:
        _, sheets = workbook_parts(path)
        root = ET.fromstring(book.read(sheets["Event"]))
        excel_rows = [int(row.attrib["r"]) for row in root.findall("m:sheetData/m:row", NS)][1:]
    for number, row in zip(excel_rows, rows):
        numbered.append((number, row))
    return headers, numbered


def audited_scope():
    manifest = load_json(AUDIT / "audit_manifest.json")
    ledger = load_jsonl(AUDIT / "exclusion_decision_ledger.jsonl")
    batch_cases = load_jsonl(AUDIT / "batch_release_minute_conflicts.jsonl")
    duplicate_cases = load_jsonl(AUDIT / "duplicate_member_event_id_cases.jsonl")
    invalid = load_json(AUDIT / "invalid_release_ts_case.json")
    if manifest["source_workbook_sha256_before"] != manifest["source_workbook_sha256_after"]:
        raise RepairError("AUDIT_SOURCE_FINGERPRINT_INCONSISTENT")
    if len(ledger) != 70 or len(batch_cases) != 48 or len(duplicate_cases) != 21:
        raise RepairError("AUDIT_SCOPE_COUNT_INVALID")
    return manifest, ledger, batch_cases, duplicate_cases, invalid


def planned_repairs(source):
    manifest, ledger, batch_cases, duplicate_cases, invalid = audited_scope()
    headers, rows = workbook_event_rows(source)
    by_number = dict(rows)
    valid = {}
    for number, row in rows:
        try:
            record = builder.source_record(row)
            record["event_row_locator"] = builder.contract.event_record_locator(record)
            valid[record["event_row_locator"]] = (number, row, record)
        except builder.EpisodeBuildError:
            continue

    batch_locators = {item["event_row_locator"] for item in batch_cases}
    collision_locators = {
        item["event_row_locator"] for item in duplicate_cases
        if item["audit_classification"] == "LEGITIMATE_DISTINCT_EVENT_WITH_COLLIDING_EVENT_ID"
    }
    collateral_locators = {
        item["event_row_locator"] for item in duplicate_cases
        if item["audit_classification"] == "DUPLICATE_EVENT_INSIDE_ONE_BATCH"
    }
    if len(batch_locators) != 48 or len(collision_locators) != 4 or len(collateral_locators) != 17:
        raise RepairError("AUDIT_SCOPE_CLASSIFICATION_INVALID")
    if not all(locator in valid for locator in batch_locators | collision_locators | collateral_locators):
        raise RepairError("AUDITED_LOCATOR_NOT_FOUND")

    repair_rows = {}
    batches = defaultdict(list)
    for locator in batch_locators:
        number, row, record = valid[locator]
        batches[(record["batch_id"], minute_key(record["country"], record["release_ts"]))].append((locator, number, row, record))
    occupied_batch_ids = defaultdict(set)
    for locator, (number, row, record) in valid.items():
        if locator not in batch_locators and record["type"] == "member" and record["batch_id"]:
            occupied_batch_ids[record["batch_id"]].add(minute_key(record["country"], record["release_ts"]))
    proposed = {}
    used_batch_ids = set(occupied_batch_ids)
    for group_key, members in sorted(batches.items(), key=lambda item: item[0][1]):
        country = members[0][3]["country"]
        candidate = legacy_uuid_from_string("batch|" + group_key[1])
        if candidate not in used_batch_ids:
            proposed[group_key] = (candidate, "LEGACY_V2_BATCH_ID")
            used_batch_ids.add(candidate)
            continue
        extended = repaired_batch_id(country, members[0][3]["release_ts"])
        if extended in used_batch_ids:
            raise RepairError("REPAIRED_BATCH_ID_COLLISION")
        proposed[group_key] = (extended, "SHA256_LINEAGE_EXTENSION")
        used_batch_ids.add(extended)
    batch_map = []
    for (original_batch_id, key), members in sorted(batches.items()):
        country = members[0][3]["country"]
        batch_id, batch_id_method = proposed[(original_batch_id, key)]
        repaired_type = "member" if len(members) >= 2 else "single"
        for locator, number, row, record in members:
            repair_rows[locator] = {"excel_row": number, "record": record, "values": {"batch_id": batch_id if repaired_type == "member" else "", "type": repaired_type}, "repair_class": "STALE_BATCH_ID_REPARTITION", "repair_reason": "The inherited batch_id was reused across release minutes. The v2.0 country-plus-UTC-minute ID is retained when unique and extended with SHA-256 only when the legacy FNV ID collides."}
        batch_map.append({"original_batch_id": original_batch_id, "country": country, "normalized_utc_minute": builder.minute(members[0][3]["release_ts"]), "legacy_batch_id_candidate": legacy_uuid_from_string("batch|" + key), "repaired_batch_id": batch_id if repaired_type == "member" else "", "batch_id_method": batch_id_method, "repaired_type": repaired_type, "member_count": len(members), "event_row_locators": sorted(member[0] for member in members)})

    existing_ids = {record["event_id"] for _, _, record in valid.values()}
    rekey_map = []
    new_ids = set()
    for locator in sorted(collision_locators):
        number, row, record = valid[locator]
        repaired = repaired_event_id(record)
        if repaired in (existing_ids - {record["event_id"]}) or repaired in new_ids:
            raise RepairError("REPAIRED_EVENT_ID_COLLISION")
        new_ids.add(repaired)
        repair_rows[locator] = {"excel_row": number, "record": record, "values": {"event_id": repaired}, "repair_class": "EVENT_ID_COLLISION_REKEY", "repair_reason": "The legacy v2.0 FNV-derived event ID collides for distinct immutable source lineages; the narrow SHA-256 lineage extension is deterministic and local to these audited rows."}
        rekey_map.append({"event_row_locator": locator, "excel_row": number, "old_event_id": record["event_id"], "new_event_id": repaired, "indicator_name": record["indicator_name"], "lineage_seed": {"country": record["country"], "release_minute": builder.minute(record["release_ts"]), "source_cal": record["source_cal"], "source_provider": record["source_provider"], "source_series_id": record["source_series_id"]}})

    duplicate_map = []
    for locator in sorted(collateral_locators):
        number, row, record = valid[locator]
        repair_rows[locator] = {"excel_row": number, "record": record, "values": {}, "repair_class": "DUPLICATE_LOGICAL_EVENT_CANONICALIZED", "repair_reason": "This row is a unique active member of a batch blocked by another pair's raw event_id collision. It is canonical to itself; no physical row is deactivated because doing so would remove a distinct catalyst."}
        duplicate_map.append({"event_row_locator": locator, "excel_row": number, "canonical_event_row_locator": locator, "duplicate_of_event_row_locator": "", "action": "REMAIN_ACTIVE_UNCHANGED", "reason": repair_rows[locator]["repair_reason"]})

    invalid_row = invalid["source_row_number"]
    if invalid_row not in by_number or by_number[invalid_row].get("release_ts") != "member":
        raise RepairError("INVALID_DUPLICATE_SCOPE_CHANGED")
    invalid_key = f"INVALID_ROW_{invalid_row}"
    repair_rows[invalid_key] = {"excel_row": invalid_row, "record": None, "values": {}, "repair_class": "INVALID_CORRUPT_DUPLICATE_UNCHANGED", "repair_reason": "The source row remains INVALID_RELEASE_TS because it exactly duplicates Excel row 2460 except for its corrupt release_ts literal; consuming it would double-count the catalyst."}
    if len(repair_rows) != 70:
        raise RepairError("REPAIR_LEDGER_SCOPE_INVALID")
    return manifest, headers, rows, repair_rows, batch_map, rekey_map, duplicate_map


def set_inline_string(cell, value):
    cell.attrib["t"] = "inlineStr"
    for child in list(cell):
        cell.remove(child)
    inline = ET.SubElement(cell, MAIN_NS + "is")
    text = ET.SubElement(inline, MAIN_NS + "t")
    text.text = value


def preview_workbook(source, destination, headers, repair_rows):
    destination.parent.mkdir(parents=True, exist_ok=True)
    _, sheets = workbook_parts(source)
    target = sheets["Event"]
    indexes = {header: index + 1 for index, header in enumerate(headers)}
    updates = defaultdict(dict)
    for plan in repair_rows.values():
        for field, value in plan["values"].items():
            updates[plan["excel_row"]][field] = value
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(destination, "w") as output:
        for info in original.infolist():
            data = original.read(info.filename)
            if info.filename == target:
                root = ET.fromstring(data)
                for row in root.findall("m:sheetData/m:row", NS):
                    row_number = int(row.attrib["r"])
                    for field, value in updates.get(row_number, {}).items():
                        reference = column_letters(indexes[field]) + str(row_number)
                        cell = next((candidate for candidate in row.findall("m:c", NS) if candidate.attrib["r"] == reference), None)
                        if cell is None:
                            raise RepairError("TARGET_EVENT_CELL_MISSING:" + reference)
                        set_inline_string(cell, value)
                data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            output.writestr(info, data)


def change_audit(source, preview, audited_excel_rows):
    before, after = logical_workbook_cells(source), logical_workbook_cells(preview)
    sheets = sorted(set(before) | set(after))
    changes = []
    for sheet in sheets:
        for reference in sorted(set(before.get(sheet, {})) | set(after.get(sheet, {}))):
            if before.get(sheet, {}).get(reference, "") != after.get(sheet, {}).get(reference, ""):
                changes.append({"sheet": sheet, "cell": reference, "before": before.get(sheet, {}).get(reference, ""), "after": after.get(sheet, {}).get(reference, "")})
    event_headers = {value: reference for reference, value in before["Event"].items() if int("".join(char for char in reference if char.isdigit())) == 1}
    event_changes = [item for item in changes if item["sheet"] == "Event"]
    unaudited = [item for item in event_changes if int("".join(char for char in item["cell"] if char.isdigit())) not in audited_excel_rows]
    non_event = [item for item in changes if item["sheet"] != "Event"]
    reverse_headers = {reference.rstrip("0123456789"): value for value, reference in event_headers.items()}
    changed_columns = sorted({reverse_headers.get(item["cell"].rstrip("0123456789"), item["cell"].rstrip("0123456789")) for item in event_changes})
    result = {"total_logical_cells_changed": len(changes), "event_rows_changed": len({int("".join(char for char in item["cell"] if char.isdigit())) for item in event_changes}), "event_columns_changed": changed_columns, "non_event_sheets_changed": len(non_event), "unaudited_event_rows_changed": len(unaudited), "unaudited_event_ids_changed": sum(item["cell"].rstrip("0123456789") == event_headers["event_id"].rstrip("0123456789") for item in unaudited), "unaudited_batch_ids_changed": sum(item["cell"].rstrip("0123456789") == event_headers["batch_id"].rstrip("0123456789") for item in unaudited), "changes": changes}
    if non_event or unaudited:
        raise RepairError("REPAIR_SCOPE_VIOLATION")
    return result


def build_ledger(repair_rows, rows):
    row_by_number = dict(rows)
    ledger = []
    for key, plan in sorted(repair_rows.items(), key=lambda item: item[1]["excel_row"]):
        number, original = plan["excel_row"], row_by_number[plan["excel_row"]]
        repaired = dict(original)
        repaired.update(plan["values"])
        if plan["record"] is None:
            original_locator = None
            canonical_locator = None
        else:
            original_locator = plan["record"]["event_row_locator"]
            repaired_record = builder.source_record(repaired)
            canonical_locator = builder.contract.event_record_locator(repaired_record)
        ledger.append({"event_row_locator": original_locator, "excel_row": number, "original_event_id": original.get("event_id", ""), "repaired_event_id": repaired.get("event_id", ""), "original_batch_id": original.get("batch_id", ""), "repaired_batch_id": repaired.get("batch_id", ""), "original_type": original.get("type", ""), "repaired_type": repaired.get("type", ""), "repair_class": plan["repair_class"], "canonical_event_row_locator": canonical_locator, "duplicate_of_event_row_locator": "", "original_values_fingerprint": fingerprint(original), "repaired_values_fingerprint": fingerprint(repaired), "repair_reason": plan["repair_reason"], "episode_eligibility_before": "EXCLUDED", "episode_eligibility_after": "EXCLUDED" if plan["repair_class"] == "INVALID_CORRUPT_DUPLICATE_UNCHANGED" else "ELIGIBLE"})
    if len(ledger) != 70 or len({item["excel_row"] for item in ledger}) != 70:
        raise RepairError("REPAIR_LEDGER_INVALID")
    return ledger


def episode_comparison(source, preview):
    old_manifest = load_json(EPISODE_OUTPUT / "episode_manifest.json")
    _, old_rows = builder.xlsx_event_rows(source)
    _, new_rows = builder.xlsx_event_rows(preview)
    old_episodes, old_dispositions = builder.build_population(old_rows)
    new_episodes, new_dispositions = builder.build_population(new_rows)
    shuffled_episodes, shuffled_dispositions = builder.build_population(list(reversed(new_rows)))
    if builder.fingerprint(builder.stable_population(new_episodes, new_dispositions)) != builder.fingerprint(builder.stable_population(shuffled_episodes, shuffled_dispositions)):
        raise RepairError("INPUT_ORDER_NONDETERMINISTIC")
    old_members = {tuple(item["member_event_ids"]) for item in old_episodes}
    recovered = [item for item in new_episodes if tuple(item["member_event_ids"]) not in old_members]
    counts = Counter(item["disposition"] for item in new_dispositions)
    reasons = Counter(item["reason"] for item in new_dispositions if item["disposition"] != "CONSUMED")
    if counts != Counter({"CONSUMED": 4314, "EXCLUDED": 1}) or reasons != Counter({"INVALID_RELEASE_TS": 1}):
        raise RepairError("EPISODE_REBUILD_TARGET_NOT_MET")
    return {"old": {"episodes": len(old_episodes), "standalone_episodes": sum(not item["same_time_cluster_flag"] for item in old_episodes), "batch_episodes": sum(item["same_time_cluster_flag"] for item in old_episodes), "consumed_rows": sum(item["disposition"] == "CONSUMED" for item in old_dispositions), "excluded_rows": sum(item["disposition"] == "EXCLUDED" for item in old_dispositions), "episode_population_fingerprint": old_manifest["episode_population_fingerprint"]}, "new": {"episodes": len(new_episodes), "standalone_episodes": sum(not item["same_time_cluster_flag"] for item in new_episodes), "batch_episodes": sum(item["same_time_cluster_flag"] for item in new_episodes), "consumed_rows": counts["CONSUMED"], "excluded_rows": counts["EXCLUDED"], "error_rows": counts["ERROR"], "excluded_by_reason": dict(reasons), "episode_population_fingerprint": builder.fingerprint(builder.stable_population(new_episodes, new_dispositions))}, "new_episode_memberships": [{"episode_id": item["episode_id"], "member_event_ids": item["member_event_ids"], "member_event_count": item["member_event_count"]} for item in sorted(recovered, key=lambda value: value["episode_id"])]}, new_episodes, new_dispositions


def verify_repair_determinism(source, preview, headers, plans):
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        repeat = directory / "repeat.xlsx"
        rerun = directory / "rerun.xlsx"
        preview_workbook(source, repeat, headers, plans)
        if sha(preview) != sha(repeat):
            raise RepairError("PREVIEW_BYTES_NONDETERMINISTIC")
        preview_workbook(preview, rerun, headers, plans)
        rerun_audit = change_audit(preview, rerun, {plan["excel_row"] for plan in plans.values()})
        if rerun_audit["total_logical_cells_changed"] != 0 or sha(preview) != sha(rerun):
            raise RepairError("REPAIR_NOT_IDEMPOTENT")


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_jsonl(path, values):
    path.write_text("".join(canonical(value) + "\n" for value in values))


def existing_repair_manifest():
    path = OUTPUT / "repair_manifest.json"
    return load_json(path) if path.exists() else None


def reuse_validated_repair(source, destination, manifest):
    """A repaired source is an idempotent no-op; retain the validated evidence."""
    _, rows = builder.xlsx_event_rows(source)
    episodes, dispositions = builder.build_population(rows)
    counts = Counter(item["disposition"] for item in dispositions)
    if counts != Counter({"CONSUMED": 4314, "EXCLUDED": 1}):
        raise RepairError("REPAIRED_SOURCE_EPISODE_RECONCILIATION_FAILED")
    destination.mkdir(parents=True, exist_ok=True)
    preview = destination / "presignal_main_repaired_preview.xlsx"
    shutil.copyfile(source, preview)
    if destination != OUTPUT:
        for name in ("event_lineage_repair_ledger.jsonl", "batch_repartition_map.json", "event_id_rekey_map.json", "duplicate_canonicalization_map.json", "workbook_change_audit.json", "episode_population_comparison.json", "repair_manifest.json", "repair_report.md"):
            shutil.copyfile(OUTPUT / name, destination / name)
    return manifest


def repair(source=SOURCE, destination=OUTPUT, promote=False):
    source = Path(source)
    destination = Path(destination)
    audit_manifest, _, _, _, _ = audited_scope()
    source_sha = sha(source)
    if source_sha != audit_manifest["source_workbook_sha256_before"]:
        previous = existing_repair_manifest()
        if previous and source_sha == previous.get("repaired_workbook_sha256"):
            return reuse_validated_repair(source, destination, previous)
        raise RepairError("SOURCE_WORKBOOK_FINGERPRINT_MISMATCH")
    audit_manifest, headers, rows, plans, batch_map, rekey_map, duplicate_map = planned_repairs(source)
    destination.mkdir(parents=True, exist_ok=True)
    preview = destination / "presignal_main_repaired_preview.xlsx"
    preview_workbook(source, preview, headers, plans)
    changes = change_audit(source, preview, {plan["excel_row"] for plan in plans.values()})
    ledger = build_ledger(plans, rows)
    comparison, episodes, dispositions = episode_comparison(source, preview)
    verify_repair_determinism(source, preview, headers, plans)
    repaired_sha = sha(preview)
    write_jsonl(destination / "event_lineage_repair_ledger.jsonl", ledger)
    write_json(destination / "batch_repartition_map.json", batch_map)
    write_json(destination / "event_id_rekey_map.json", rekey_map)
    write_json(destination / "duplicate_canonicalization_map.json", duplicate_map)
    write_json(destination / "workbook_change_audit.json", changes)
    write_json(destination / "episode_population_comparison.json", comparison)
    manifest = {"decision": "V2_1_EVENT_LINEAGE_REPAIR_AND_EPISODE_REBUILD_VALIDATED", "source_workbook_sha256_before": source_sha, "repaired_workbook_sha256": repaired_sha, "audited_rows": len(ledger), "stale_batch_groups_partitioned": len(batch_map), "new_batch_ids_created": sum(item["original_batch_id"] != item["repaired_batch_id"] for item in batch_map), "repair_classes": dict(Counter(item["repair_class"] for item in ledger)), "changed_event_rows": changes["event_rows_changed"], "workbook_change_audit": {key: changes[key] for key in changes if key != "changes"}, "episode_population_comparison": comparison, "determinism": {"repeated_preview_bytes": "PASS", "input_order_shuffle": "PASS", "repair_idempotency": "PASS"}, "validation": {"no_non_event_changes": changes["non_event_sheets_changed"] == 0, "no_unaudited_event_changes": changes["unaudited_event_rows_changed"] == 0, "one_invalid_timestamp_exclusion": comparison["new"]["excluded_by_reason"] == {"INVALID_RELEASE_TS": 1}}}
    write_json(destination / "repair_manifest.json", manifest)
    report = "# Event Lineage Repair and Episode Rebuild\n\n## Decision\n\n`V2_1_EVENT_LINEAGE_REPAIR_AND_EPISODE_REBUILD_VALIDATED`\n\nThe repair changes only audited Event cells: 48 stale inherited batch identities are repartitioned with the legacy country-plus-UTC-minute rule, and four raw Event-ID collisions receive deterministic SHA-256 lineage extensions. The 17 collateral batch members remain active because audit evidence shows they are unique catalysts, not duplicate physical observations. Excel row 4316 remains excluded as the corrupt duplicate of row 2460.\n\n## Rebuild\n\n- Old Episode population: {} Episodes, {} consumed rows, {} exclusions.\n- New Episode population: {} Episodes, {} consumed rows, {} exclusion.\n- Recovered memberships: {} newly valid cluster Episodes.\n\nNo frozen contract, provider, market-data, Apps Script, Google Sheets, or production routing behavior changed.\n".format(comparison["old"]["episodes"], comparison["old"]["consumed_rows"], comparison["old"]["excluded_rows"], comparison["new"]["episodes"], comparison["new"]["consumed_rows"], comparison["new"]["excluded_rows"], len(comparison["new_episode_memberships"]))
    (destination / "repair_report.md").write_text(report)
    if promote:
        shutil.copyfile(preview, source)
        builder.write_outputs(episodes, dispositions, repaired_sha, EPISODE_OUTPUT)
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--promote", action="store_true")
    args = parser.parse_args()
    print(json.dumps(repair(args.source, args.output, args.promote), sort_keys=True))


if __name__ == "__main__":
    main()
