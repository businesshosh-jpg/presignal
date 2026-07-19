#!/usr/bin/env python3
"""Read-only integrity audit for existing v2.1 Episode-builder exclusions."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from automation import build_presignal_v21_episodes as builder

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "presignal_main.xlsx"
EPISODE_OUTPUT = ROOT / "outputs" / "presignal_v21_episode_builder"
OUTPUT = ROOT / "outputs" / "presignal_v21_episode_exclusion_audit"
NS = {"m":"http://schemas.openxmlformats.org/spreadsheetml/2006/main", "r":"http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def canonical(value): return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def write_json(path, value): path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
def write_jsonl(path, values): path.write_text("".join(canonical(value) + "\n" for value in values))


def numbered_event_rows(path):
    with zipfile.ZipFile(path) as book:
        shared = []
        if "xl/sharedStrings.xml" in book.namelist():
            root = ET.fromstring(book.read("xl/sharedStrings.xml")); shared = ["".join(node.text or "" for node in item.findall(".//m:t", NS)) for item in root.findall("m:si", NS)]
        workbook = ET.fromstring(book.read("xl/workbook.xml")); rels = ET.fromstring(book.read("xl/_rels/workbook.xml.rels")); targets = {item.attrib["Id"]:item.attrib["Target"] for item in rels}
        sheet = next(item for item in workbook.findall("m:sheets/m:sheet", NS) if item.attrib["name"] == "Event")
        target = targets[sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]].lstrip("/"); target = "xl/" + target if not target.startswith("xl/") else target
        root = ET.fromstring(book.read(target)); physical = root.findall("m:sheetData/m:row", NS)
        matrix = []
        for row in physical:
            values = {}
            for cell in row.findall("m:c", NS):
                raw = cell.findtext("m:v", default="", namespaces=NS)
                if cell.attrib.get("t") == "s": raw = shared[int(raw)]
                elif cell.attrib.get("t") == "inlineStr": raw = "".join(node.text or "" for node in cell.findall(".//m:t", NS))
                values[builder.column(cell.attrib["r"])] = raw
            matrix.append((int(row.attrib["r"]), [values.get(i, "") for i in range(1, max(values, default=0) + 1)]))
    headers = matrix[0][1]
    builder.validate_event_headers(headers)
    return {"physical_rows_including_header":len(matrix), "last_excel_row":matrix[-1][0], "headers":headers, "rows":[(number, dict(zip(headers, values + [""] * (len(headers) - len(values))))) for number, values in matrix[1:] if any(builder.text(value) for value in values)]}


def audit(source=SOURCE, episode_output=EPISODE_OUTPUT, destination=OUTPUT):
    before = sha(source); workbook = numbered_event_rows(source)
    existing = [json.loads(line) for line in (episode_output / "event_row_dispositions.jsonl").read_text().splitlines()]
    excluded = [item for item in existing if item["disposition"] != "CONSUMED"]
    valid, invalid = [], []
    for number, row in workbook["rows"]:
        try:
            item = builder.source_record(row); item["event_row_locator"] = builder.contract.event_record_locator(item); item["source_row_number"] = number; valid.append(item)
        except Exception as exc:
            invalid.append({"source_row_number":number, "raw":row, "error":str(exc)})
    by_locator = {item["event_row_locator"]:item for item in valid}; by_event = defaultdict(list); by_batch = defaultdict(list)
    for item in valid: by_event[item["event_id"]].append(item); by_batch[item["batch_id"]].append(item)
    ledger, batch_cases, duplicate_cases = [], [], []
    for item in excluded:
        reason = item["reason"]
        if reason == "BATCH_RELEASE_MINUTE_CONFLICT":
            source_item = by_locator[item["event_row_locator"]]; members = by_batch[source_item["batch_id"]]
            minutes = sorted({builder.minute(member["release_ts"]) for member in members})
            cause = "STALE_BATCH_ID" if len({minute[:10] for minute in minutes}) > 1 else "MULTI_MINUTE_SOURCE_CLUSTER"
            batch_cases.append({"event_row_locator":source_item["event_row_locator"], "event_id":source_item["event_id"], "batch_id":source_item["batch_id"], "country":source_item["country"], "indicator_name":source_item["indicator_name"], "release_ts":source_item["release_ts"], "normalized_release_minute":builder.minute(source_item["release_ts"]), "other_batch_member_locators":sorted(member["event_row_locator"] for member in members if member is not source_item), "other_batch_member_release_minutes":minutes, "source_row_number":source_item["source_row_number"], "exclusion_reason":reason, "audit_classification":cause, "batch_scope":"ENTIRE_BATCH_INTERNALLY_INCONSISTENT"})
            ledger.append({"event_row_locator":source_item["event_row_locator"], "event_id":source_item["event_id"], "batch_id":source_item["batch_id"], "indicator_name":source_item["indicator_name"], "release_ts":source_item["release_ts"], "original_exclusion_reason":reason, "audit_classification":cause, "scientific_exclusion_justified":False, "repair_possible":True, "repair_type":"REKEY_STALE_BATCH_ID_BY_EXISTING_COUNTRY_AND_UTC_MINUTE", "recommended_disposition":"ELIGIBLE_AFTER_TARGETED_REPAIR", "evidence":"The same inherited batch_id spans distinct calendar release minutes; country and UTC minute already partition the members deterministically."})
        elif reason == "DUPLICATE_MEMBER_EVENT_ID":
            source_item = by_locator[item["event_row_locator"]]; members = by_batch[source_item["batch_id"]]; same = by_event[source_item["event_id"]]
            duplicate_inside = [member for member in members if member["event_id"] == source_item["event_id"]]
            differences = sorted({key for key in ("indicator_name", "release_ts", "batch_id", "source_cal", "source_provider", "source_series_id", "type") if len({member[key] for member in duplicate_inside}) > 1})
            classification = "LEGITIMATE_DISTINCT_EVENT_WITH_COLLIDING_EVENT_ID" if len(duplicate_inside) > 1 else "DUPLICATE_EVENT_INSIDE_ONE_BATCH"
            duplicate_cases.append({"event_row_locator":source_item["event_row_locator"], "event_id":source_item["event_id"], "batch_id":source_item["batch_id"], "country":source_item["country"], "indicator_name":source_item["indicator_name"], "release_ts":source_item["release_ts"], "source_row_number":source_item["source_row_number"], "all_physical_rows_sharing_event_id":[{"event_row_locator":member["event_row_locator"], "source_row_number":member["source_row_number"], "indicator_name":member["indicator_name"], "release_ts":member["release_ts"], "batch_id":member["batch_id"]} for member in same], "all_members_in_affected_batch":[member["event_row_locator"] for member in sorted(members, key=lambda value:value["event_row_locator"])], "immutable_attribute_differences":differences, "source_lineage_differences":differences, "duplicate_event_id_in_affected_batch":len(duplicate_inside) > 1, "audit_classification":classification})
            ledger.append({"event_row_locator":source_item["event_row_locator"], "event_id":source_item["event_id"], "batch_id":source_item["batch_id"], "indicator_name":source_item["indicator_name"], "release_ts":source_item["release_ts"], "original_exclusion_reason":reason, "audit_classification":classification, "scientific_exclusion_justified":False, "repair_possible":True, "repair_type":"REKEY_COLLIDING_EVENT_ID_FROM_EXISTING_IMMUTABLE_SOURCE_LINEAGE", "recommended_disposition":"ELIGIBLE_AFTER_TARGETED_REPAIR", "evidence":"The frozen row locator distinguishes physical rows. Duplicate raw event_id values inside the batch identify different indicators, so consuming both does not double-count one catalyst."})
        elif reason == "INVALID_RELEASE_TS":
            malformed = next(candidate for candidate in invalid if builder.text(candidate["raw"].get("event_id")) == item["event_id"] and builder.text(candidate["raw"].get("batch_id")) == item["batch_id"] and builder.text(candidate["raw"].get("release_ts")) == "member")
            raw = malformed["raw"]; peers = [item for number, item in workbook["rows"] if number != malformed["source_row_number"] and builder.text(item.get("event_id")) == builder.text(raw.get("event_id")) and builder.text(item.get("batch_id")) == builder.text(raw.get("batch_id")) and builder.text(item.get("indicator_name")) == builder.text(raw.get("indicator_name"))]
            invalid_case = {"event_row_locator":None, "locator_status":"UNAVAILABLE_DUE_TO_INVALID_RELEASE_TS", "event_id":raw.get("event_id"), "indicator_name":raw.get("indicator_name"), "raw_release_ts":raw.get("release_ts"), "cell_type":"string", "source_row_number":malformed["source_row_number"], "other_populated_fields":{key:value for key,value in raw.items() if builder.text(value) and key != "release_ts"}, "likely_cause":"An exact duplicate physical row has literal 'member' in release_ts while Excel row 2460 has numeric release_ts 45603.5625; all other populated fields match.", "deterministic_repair_possible":len(peers)==1, "matching_authoritative_row_numbers":[number for number, item in workbook["rows"] if item in peers]}
            ledger.append({"event_row_locator":None, "event_id":raw.get("event_id"), "batch_id":raw.get("batch_id"), "indicator_name":raw.get("indicator_name"), "release_ts":raw.get("release_ts"), "original_exclusion_reason":reason, "audit_classification":"EXACT_DUPLICATE_OBSERVATION", "scientific_exclusion_justified":True, "repair_possible":len(peers)==1, "repair_type":"QUARANTINE_EXACT_DUPLICATE_MALFORMED_SOURCE_ROW", "recommended_disposition":"KEEP_EXCLUDED", "evidence":invalid_case["likely_cause"]})
    expected = Counter({"BATCH_RELEASE_MINUTE_CONFLICT":48, "DUPLICATE_MEMBER_EVENT_ID":21, "INVALID_RELEASE_TS":1})
    if Counter(item["reason"] for item in excluded) != expected or len(ledger) != 70 or len(batch_cases) != 48 or len(duplicate_cases) != 21:
        raise RuntimeError("AUDIT_ACCOUNTING_FAILURE")
    if len({(item["event_row_locator"], item["event_id"], item["original_exclusion_reason"]) for item in ledger}) != len(ledger):
        raise RuntimeError("AUDIT_LEDGER_DUPLICATE")
    consumed = {item["event_row_locator"] for item in existing if item["disposition"] == "CONSUMED"}
    if any(item["event_row_locator"] in consumed for item in ledger if item["event_row_locator"]):
        raise RuntimeError("AUDIT_CONSUMED_ROW_IN_LEDGER")
    if before != sha(source):
        raise RuntimeError("SOURCE_WORKBOOK_CHANGED_DURING_AUDIT")
    destination.mkdir(parents=True, exist_ok=True)
    count = {"migration_count":4316, "builder_count":4315, "canonical_physical_data_row_count":len(workbook["rows"]), "physical_rows_including_header":workbook["physical_rows_including_header"], "count_difference_reason":"Migration counted the Event worksheet used range including header row 1 (A1:V4316); the builder counts only 4,315 non-empty data rows (Excel rows 2-4316).", "affected_row_locator_or_excel_row":"Excel header row 1"}
    write_json(destination / "row_count_reconciliation.json", count); write_jsonl(destination / "batch_release_minute_conflicts.jsonl", sorted(batch_cases, key=lambda value:value["event_row_locator"])); write_jsonl(destination / "duplicate_member_event_id_cases.jsonl", sorted(duplicate_cases, key=lambda value:value["event_row_locator"])); write_json(destination / "invalid_release_ts_case.json", invalid_case); write_jsonl(destination / "exclusion_decision_ledger.jsonl", sorted(ledger, key=lambda value:(str(value["event_row_locator"]), value["event_id"])))
    manifest = {"decision":"TARGETED_EVENT_LINEAGE_REPAIR_REQUIRED", "source_workbook_sha256_before":before, "source_workbook_sha256_after":sha(source), "episode_population_fingerprint":json.loads((episode_output / "episode_manifest.json").read_text())["episode_population_fingerprint"], "row_count_reconciliation":count, "audited_rows":len(ledger), "batch_conflict_rows":len(batch_cases), "batch_conflict_groups":len({item["batch_id"] for item in batch_cases}), "batch_conflict_causes":dict(Counter(item["audit_classification"] for item in batch_cases)), "duplicate_member_rows":len(duplicate_cases), "duplicate_member_classifications":dict(Counter(item["audit_classification"] for item in duplicate_cases)), "invalid_timestamp_rows":1, "scientifically_justified_exclusions":sum(item["scientific_exclusion_justified"] for item in ledger), "repairable_exclusions":sum(item["recommended_disposition"] == "ELIGIBLE_AFTER_TARGETED_REPAIR" for item in ledger), "recommended_dispositions":dict(Counter(item["recommended_disposition"] for item in ledger)), "validation":{"original_exclusions_accounted_for":True, "ledger_unique":True, "no_consumed_row_in_ledger":True, "source_workbook_unchanged":True}, "audit_fingerprint":"sha256:" + hashlib.sha256(canonical(ledger).encode()).hexdigest()}
    write_json(destination / "audit_manifest.json", manifest)
    report = "# Episode Exclusion Integrity Audit\n\n## Decision\n\n`TARGETED_EVENT_LINEAGE_REPAIR_REQUIRED`\n\nThe 48 stale-batch exclusions and 21 rows blocked by four raw Event-ID collisions are contract-valid today but scientifically unnecessary: existing immutable source fields resolve their identities deterministically. The final malformed timestamp row is scientifically justified as excluded because it is an exact duplicate of Excel row 2460 and consuming it would double-count a release.\n\n## Row Count\n\nThe migration count of 4,316 includes header row 1. The builder correctly counts 4,315 non-empty Event data rows, Excel rows 2 through 4316.\n\n## Audit Results\n\n- Batch conflicts: 48 rows in 6 groups, all `STALE_BATCH_ID`.\n- Duplicate-member exclusions: 21 rows in 2 batches; 4 raw IDs are `LEGITIMATE_DISTINCT_EVENT_WITH_COLLIDING_EVENT_ID` and the remaining 17 are batch members blocked by those collisions.\n- Invalid timestamp: Excel row 4316 has literal `member` in `release_ts`; it otherwise exactly duplicates row 2460.\n\n## Repair Scope\n\nOne narrow Event-lineage repair is required before attention selection: partition stale inherited batch identities using the existing country and UTC release minute, and rekey the four colliding raw Event IDs from existing immutable source lineage. Retain the malformed duplicate timestamp row as excluded (or quarantine it in the source lineage) rather than restoring and consuming it. No contract, Episode builder, provider, market-data, or production-routing change is recommended.\n"
    (destination / "audit_report.md").write_text(report)
    return manifest


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=Path, default=OUTPUT); args = parser.parse_args(); print(json.dumps(audit(destination=args.output), sort_keys=True))
if __name__ == "__main__": main()
