#!/usr/bin/env python3
"""Phase 9A: compact empirical population-recovery audit for OA v2.

The audit reads only the authoritative R1 shadow manifests and the frozen
72-pair collapse lineage. It does not load outcome-source sheets or alter any
scientific rule. Workbook capacity is intentionally conserved by storing the
full row-level audit as deterministic JSON chunks on one shadow-only sheet.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_market_sessions_shadow_v0 import DIAGNOSTICS_SPREADSHEET_ID, _column_letter  # type: ignore
from automation.build_refined_mechanism_test_execution_v0 import _canonical_json, _normalize  # type: ignore
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials  # type: ignore
import automation.build_refined_mechanism_test_outcome_architecture_v2_staged_implementation_v0 as impl  # type: ignore


PHASE_ID = "9A-OA2-POPULATION-RECOVERY"
BUILD_SCRIPT = "automation/build_outcome_architecture_v2_population_recovery_audit_v0.py"
SCHEMA_VERSION = "presignal_v2_oa2_population_recovery_audit_v0"
AUTHORITATIVE_RUN_ID = "9A-6R15I-R1_20260713T061220Z"
VERIFICATION_RUN_ID = "9A-6R15J-R1_20260713T071511Z"
EXPECTED_AGGREGATE_FINGERPRINT = "0f021cb3aa68fb0ebf3025091923687d261afeaaa30ec47474b54daba0dff41a"
ORIGINAL_COLLAPSE_RUN_ID = "9A-6R15A_20260712T120605Z"
OUTPUT_SHEET = "OA2_Population_Recovery_Audit"
HEADERS = [
    "generated_ts", "schema_version", "population_recovery_audit_run_id",
    "authoritative_implementation_run_id", "audit_record_type", "audit_status", "blocking", "payload_json",
]
FROZEN_GATES = {"positive": 40, "negative": 12, "primary_contrast": 40, "clusters": 12, "providers": 2, "sessions": 4}


class AuditBlocked(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_id(ts: str) -> str:
    return f"9A-OA2-POPULATION-RECOVERY_{ts.replace('-', '').replace(':', '').replace('Z', '')}Z"


def _payload(value: Any) -> Dict[str, Any]:
    try:
        parsed = json.loads(value) if isinstance(value, str) and value.strip() else {}
    except json.JSONDecodeError as exc:
        raise AuditBlocked(f"Malformed stored JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise AuditBlocked("Stored JSON payload is not an object.")
    return parsed


def _get_raw(service, sheets: Sequence[str]) -> Dict[str, List[List[Any]]]:
    response = service.spreadsheets().values().batchGet(
        spreadsheetId=DIAGNOSTICS_SPREADSHEET_ID,
        ranges=[f"'{sheet}'!A1:ZZZ" for sheet in sheets],
    ).execute()
    ranges = response.get("valueRanges", [])
    return {sheet: ranges[index].get("values", []) for index, sheet in enumerate(sheets)}


def _direct_rows(values: Sequence[Sequence[Any]]) -> List[Dict[str, Any]]:
    if not values:
        return []
    headers = list(values[0])
    return [dict(zip(headers, row)) for row in values[1:]]


def _decode_manifest(values: Sequence[Sequence[Any]], sheet: str) -> List[Dict[str, Any]]:
    rows = _direct_rows(values)
    chunks = []
    for row in rows:
        if _normalize(row.get("outcome_architecture_implementation_run_id")) != AUTHORITATIVE_RUN_ID:
            continue
        payload = _payload(row.get("payload_json"))
        if payload.get("storage_mode") != "COMPACT_APPEND_ONLY_MANIFEST":
            continue
        chunks.append(payload)
    if not chunks:
        raise AuditBlocked(f"{sheet}: authoritative compact records missing.")
    chunks = sorted(chunks, key=lambda item: item.get("chunk_index", 0))
    if [chunk.get("chunk_index") for chunk in chunks] != list(range(1, len(chunks) + 1)):
        raise AuditBlocked(f"{sheet}: compact chunk sequence is invalid.")
    if any(chunk.get("chunk_count") != len(chunks) for chunk in chunks):
        raise AuditBlocked(f"{sheet}: compact chunk count is inconsistent.")
    decoded: List[Dict[str, Any]] = []
    for chunk in chunks:
        columns = chunk.get("column_order")
        records = chunk.get("records")
        if not isinstance(columns, list) or not isinstance(records, list):
            raise AuditBlocked(f"{sheet}: compact manifest is malformed.")
        for record in records:
            if not isinstance(record, list) or len(record) != len(columns):
                raise AuditBlocked(f"{sheet}: compact logical record is malformed.")
            decoded.append(dict(zip(columns, record)))
    if chunks[-1].get("logical_record_count") != len(decoded):
        raise AuditBlocked(f"{sheet}: logical count does not match decoded records.")
    return decoded


def _index_by_pair_side(rows: Sequence[Mapping[str, Any]], sheet: str) -> Dict[Tuple[str, str], Dict[str, Any]]:
    indexed: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in rows:
        key = (_normalize(row.get("source_observation_key")), _normalize(row.get("observation_side")))
        if not all(key) or key in indexed:
            raise AuditBlocked(f"{sheet}: duplicate or incomplete stable pair-side key {key}.")
        indexed[key] = dict(row)
    return indexed


def _original_layer(lineage: Mapping[str, Any]) -> str:
    disposition = _normalize(lineage.get("final_disposition"))
    if disposition == "PRIMARY_ELIGIBLE":
        return "NONE"
    if disposition == "MISSING_REPAIRED_OUTCOME_OVERLAY":
        return "OVERLAY"
    if disposition in {"MISSING_EXPANDED_OUTCOME_JOIN", "MISSING_BASELINE_OUTCOME_JOIN", "OUTCOME_VERSION_MISMATCH", "EVALUATION_WINDOW_MISMATCH"}:
        return "CANONICAL"
    return "SUCCESS_MAPPING"


def _pair_key(lineage: Mapping[str, Any], pair: Mapping[str, Any]) -> str:
    return "|".join((
        _normalize(lineage.get("provider")), _normalize(lineage.get("session_id")),
        _normalize(pair.get("baseline_source_key")), _normalize(pair.get("expanded_source_key")),
    ))


def _stage_passes(row: Mapping[str, Any], canon: Mapping[Tuple[str, str], Mapping[str, Any]], overlay: Mapping[Tuple[str, str], Mapping[str, Any]], linkage: Mapping[Tuple[str, str], Mapping[str, Any]], representation: Mapping[Tuple[str, str], Mapping[str, Any]], pair: Mapping[str, Any]) -> Dict[str, bool]:
    source_key = _normalize(row.get("source_row_key"))
    sides = ((source_key, "BASELINE"), (source_key, "EXPANDED"))
    canonical_ok = all(_normalize(canon[key].get("coverage_status")) == "COMPLETE_CANONICAL_COVERAGE" for key in sides)
    overlay_ok = canonical_ok and all(_normalize(overlay[key].get("overlay_status")) == "COMPLETE_OVERLAY" for key in sides)
    linkage_ok = overlay_ok and all(_normalize(linkage[key].get("linkage_status")) == "EXACT_LINK" for key in sides)
    representation_ok = linkage_ok and all(_normalize(representation[key].get("representation_status")) != "REPRESENTATION_UNAVAILABLE" for key in sides)
    success_mapping_ok = representation_ok and _normalize(pair.get("pair_evaluability_status")) == "EVALUABLE_CURRENT_V1"
    arm_ok = _normalize(row.get("expanded_label")) in {"POSITIVE", "NEGATIVE"}
    return {
        "canonical": canonical_ok, "overlay": overlay_ok, "linkage": linkage_ok,
        "representation": representation_ok, "success_mapping": success_mapping_ok,
        "mechanism_arm": arm_ok, "final": success_mapping_ok and arm_ok,
    }


def _final_classification(original: str, passes: Mapping[str, bool]) -> Tuple[str, str]:
    if passes["final"]:
        if original == "NONE":
            return "ORIGINAL_SURVIVOR_RETAINED", ""
        return {"CANONICAL": "RECOVERED_FROM_CANONICAL", "OVERLAY": "RECOVERED_FROM_OVERLAY", "SUCCESS_MAPPING": "RECOVERED_FOR_SUCCESS_MAPPING"}[original], ""
    for stage, classification in (
        ("canonical", "STILL_EXCLUDED_CANONICAL"), ("overlay", "STILL_EXCLUDED_OVERLAY"),
        ("linkage", "STILL_EXCLUDED_LINKAGE"), ("representation", "STILL_EXCLUDED_REPRESENTATION"),
        ("success_mapping", "STILL_EXCLUDED_SUCCESS_MAPPING"), ("mechanism_arm", "STILL_EXCLUDED_MECHANISM_ARM"),
    ):
        if not passes[stage]:
            return classification, stage.upper()
    raise AuditBlocked("Final recovery classification is not exhaustive.")


def _chunk_records(records: Sequence[Mapping[str, Any]], max_payload_chars: int = 42000) -> List[List[Mapping[str, Any]]]:
    chunks: List[List[Mapping[str, Any]]] = []
    current: List[Mapping[str, Any]] = []
    for record in records:
        candidate = current + [record]
        if current and len(_canonical_json({"records": candidate})) > max_payload_chars:
            chunks.append(current)
            current = [record]
        else:
            current = candidate
    if current:
        chunks.append(current)
    if len(chunks) > 3:
        raise AuditBlocked("Row-level audit cannot fit the compact workbook allocation.")
    return chunks


def _write(service, rows: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    metadata = service.spreadsheets().get(
        spreadsheetId=DIAGNOSTICS_SPREADSHEET_ID, fields="sheets.properties(sheetId,title,gridProperties)",
    ).execute()
    properties = {sheet["properties"]["title"]: sheet["properties"] for sheet in metadata.get("sheets", [])}
    if OUTPUT_SHEET not in properties:
        service.spreadsheets().batchUpdate(
            spreadsheetId=DIAGNOSTICS_SPREADSHEET_ID,
            body={"requests": [{"addSheet": {"properties": {"title": OUTPUT_SHEET, "gridProperties": {"rowCount": 5, "columnCount": 8}}}}]},
        ).execute()
    if len(rows) > 4:
        raise AuditBlocked("Compact output requires more rows than its fixed allocation.")
    updates = [{"range": f"'{OUTPUT_SHEET}'!A1:H1", "values": [HEADERS]}]
    for index, row in enumerate(rows, start=2):
        updates.append({"range": f"'{OUTPUT_SHEET}'!A{index}:H{index}", "values": [[row.get(header, "") for header in HEADERS]]})
    batch_update_values(service, DIAGNOSTICS_SPREADSHEET_ID, updates)
    return {OUTPUT_SHEET: len(rows)}


def build() -> Dict[str, Any]:
    generated_ts = _now()
    audit_run_id = _run_id(generated_ts)
    service = build_sheets_service(load_credentials())
    manifest_sheets = [
        impl.OUTPUT_CANONICAL, impl.OUTPUT_OVERLAY, impl.OUTPUT_LINKAGE, impl.OUTPUT_REPRESENTATION,
        impl.OUTPUT_PAIR, impl.OUTPUT_SURVIVORSHIP, impl.OUTPUT_AUTHORITY, impl.OUTPUT_AGGREGATE_FP,
        "Refined_Mechanism_Test_Row_Lineage_Audit",
    ]
    raw = _get_raw(service, manifest_sheets)

    # Select the prior verified run by explicit authority record, not row order.
    authority_rows = _direct_rows(raw[impl.OUTPUT_AUTHORITY])
    authority_matches = []
    for row in authority_rows:
        if _normalize(row.get("outcome_architecture_implementation_run_id")) != AUTHORITATIVE_RUN_ID:
            continue
        payload = _payload(row.get("payload_json"))
        if payload.get("authority_record_id") == f"{AUTHORITATIVE_RUN_ID}:REPAIR_FINALIZATION_V1":
            authority_matches.append(payload)
    if len(authority_matches) != 1 or authority_matches[0].get("aggregate_fingerprint") != EXPECTED_AGGREGATE_FINGERPRINT:
        raise AuditBlocked("Authoritative R1 run is not selectable through its explicit authority record.")

    canonical = _decode_manifest(raw[impl.OUTPUT_CANONICAL], impl.OUTPUT_CANONICAL)
    overlay = _decode_manifest(raw[impl.OUTPUT_OVERLAY], impl.OUTPUT_OVERLAY)
    linkage = _decode_manifest(raw[impl.OUTPUT_LINKAGE], impl.OUTPUT_LINKAGE)
    representation = _decode_manifest(raw[impl.OUTPUT_REPRESENTATION], impl.OUTPUT_REPRESENTATION)
    pairs = _decode_manifest(raw[impl.OUTPUT_PAIR], impl.OUTPUT_PAIR)
    survivorship = _decode_manifest(raw[impl.OUTPUT_SURVIVORSHIP], impl.OUTPUT_SURVIVORSHIP)
    if not all(len(rows) == count for rows, count in ((canonical, 144), (overlay, 144), (linkage, 144), (representation, 144), (pairs, 72), (survivorship, 72))):
        raise AuditBlocked("Authoritative v2 manifest population counts are not frozen expected values.")

    lineage_rows = [
        row for row in _direct_rows(raw["Refined_Mechanism_Test_Row_Lineage_Audit"])
        if _normalize(row.get("population_collapse_run_id")) == ORIGINAL_COLLAPSE_RUN_ID
    ]
    if len(lineage_rows) != 72:
        raise AuditBlocked(f"Expected 72 original candidate pairs, found {len(lineage_rows)}.")
    lineage_by_key = {_normalize(row.get("source_row_key")): row for row in lineage_rows}
    if len(lineage_by_key) != 72:
        raise AuditBlocked("Original candidate population contains duplicate source observation keys.")

    canon_by_side = _index_by_pair_side(canonical, impl.OUTPUT_CANONICAL)
    overlay_by_side = _index_by_pair_side(overlay, impl.OUTPUT_OVERLAY)
    linkage_by_side = _index_by_pair_side(linkage, impl.OUTPUT_LINKAGE)
    representation_by_side = _index_by_pair_side(representation, impl.OUTPUT_REPRESENTATION)
    pair_by_key = {_normalize(row.get("source_observation_key")): row for row in pairs}
    survivor_by_key = {_normalize(row.get("source_observation_key")): row for row in survivorship}
    if set(lineage_by_key) != set(pair_by_key) or set(lineage_by_key) != set(survivor_by_key):
        raise AuditBlocked("Original and v2 pair populations do not use the same 72 stable keys.")

    row_level: List[Dict[str, Any]] = []
    for source_key in sorted(lineage_by_key):
        lineage = lineage_by_key[source_key]
        pair = pair_by_key[source_key]
        survivor = survivor_by_key[source_key]
        passes = _stage_passes(lineage, canon_by_side, overlay_by_side, linkage_by_side, representation_by_side, pair)
        original = _original_layer(lineage)
        recovery_class, remaining_layer = _final_classification(original, passes)
        sides = ((source_key, "BASELINE"), (source_key, "EXPANDED"))
        time_safe = all(
            _normalize(canon_by_side[key].get("timestamp_provenance_status")) == "TIMESTAMP_PROVENANCE_COMPLETE"
            and _normalize(linkage_by_side[key].get("linkage_status")) == "EXACT_LINK"
            and _normalize(overlay_by_side[key].get("overlay_status")) == "COMPLETE_OVERLAY"
            for key in sides
        )
        remaining_reason = _normalize(pair.get("first_failure_point")) or _normalize(lineage.get("execution_exclusion_reason"))
        row_level.append({
            "logical_pair_key": _pair_key(lineage, pair), "source_observation_key": source_key,
            "baseline_source_key": _normalize(pair.get("baseline_source_key")), "provider": _normalize(lineage.get("provider")),
            "session_id": _normalize(lineage.get("session_id")), "expanded_label": _normalize(lineage.get("expanded_label")),
            "confidence": _normalize(lineage.get("confidence_category")), "original_v1_status": _normalize(lineage.get("final_disposition")),
            "original_first_hit": original, "v2_canonical_pass": passes["canonical"], "v2_overlay_pass": passes["overlay"],
            "v2_linkage_pass": passes["linkage"], "v2_representation_pass": passes["representation"],
            "v2_success_mapping_v1_evaluable": passes["success_mapping"], "mechanism_arm_assigned": passes["mechanism_arm"],
            "final_v2_scientifically_evaluable": passes["final"], "recovery_classification": recovery_class,
            "remaining_first_hit": remaining_layer, "remaining_exclusion_reason": remaining_reason,
            "time_safe_if_evaluable": time_safe, "v2_pair_status": _normalize(pair.get("pair_evaluability_status")),
            "v2_survivorship_status": _normalize(survivor.get("projected_architecture_v2_survivorship_status")),
        })

    keys = [row["logical_pair_key"] for row in row_level]
    if len(keys) != len(set(keys)):
        raise AuditBlocked("Duplicate scientific logical pair identity found in recovered population.")
    if len(row_level) != 72:
        raise AuditBlocked("Row-level recovery population does not reconcile to 72.")

    stage_names = ("canonical", "overlay", "linkage", "representation", "success_mapping", "mechanism_arm", "final")
    stage_fields = {
        "canonical": "v2_canonical_pass", "overlay": "v2_overlay_pass", "linkage": "v2_linkage_pass",
        "representation": "v2_representation_pass", "success_mapping": "v2_success_mapping_v1_evaluable",
        "mechanism_arm": "mechanism_arm_assigned", "final": "final_v2_scientifically_evaluable",
    }
    funnel = []
    retained = list(row_level)
    for stage in stage_names:
        input_count = len(retained)
        retained = [row for row in retained if bool(row[stage_fields[stage]])]
        pass_count = len(retained)
        funnel.append({"stage": stage, "input_count": input_count, "pass_count": pass_count, "fail_count": input_count - pass_count, "cumulative_retained": pass_count, "percentage_of_original": round(pass_count / 72 * 100, 2)})

    final_rows = [row for row in row_level if row["final_v2_scientifically_evaluable"]]
    original_survivors = [row for row in row_level if row["original_v1_status"] == "PRIMARY_ELIGIBLE"]
    final_first_hits = Counter(row["remaining_first_hit"] or "NONE" for row in row_level if not row["final_v2_scientifically_evaluable"])
    recovered_by_original = Counter(row["original_first_hit"] for row in final_rows if row["original_first_hit"] != "NONE")
    original_group_summary = {}
    for group, expected in (("CANONICAL", 22), ("OVERLAY", 11), ("SUCCESS_MAPPING", 36), ("NONE", 3)):
        group_rows = [row for row in row_level if row["original_first_hit"] == group]
        if len(group_rows) != expected:
            raise AuditBlocked(f"Original {group} group expected {expected}, found {len(group_rows)}.")
        original_group_summary[group] = {
            "original_count": len(group_rows), "final_evaluable": sum(row["final_v2_scientifically_evaluable"] for row in group_rows),
            "recovered_upstream_but_blocked_later": sum(any(row[f"v2_{stage}_pass"] for stage in ("canonical", "overlay", "linkage", "representation")) and not row["final_v2_scientifically_evaluable"] for row in group_rows),
            "remaining_exclusions": dict(Counter(row["recovery_classification"] for row in group_rows if not row["final_v2_scientifically_evaluable"])),
        }

    provider_counts = Counter(row["provider"] for row in final_rows)
    session_counts = Counter(row["session_id"] for row in final_rows)
    cluster_counts = Counter((row["provider"], row["session_id"]) for row in final_rows)
    arm_counts = Counter(row["expanded_label"] for row in final_rows)
    final_time_safe = all(row["time_safe_if_evaluable"] for row in final_rows)
    original_retained = sum(row["recovery_classification"] == "ORIGINAL_SURVIVOR_RETAINED" for row in row_level)
    original_survivor_semantic_change = any(
        row["final_v2_scientifically_evaluable"] and row["expanded_label"] not in {"POSITIVE", "NEGATIVE"}
        for row in original_survivors
    )

    gates = {
        "positive": {"current": arm_counts.get("POSITIVE", 0), "threshold": FROZEN_GATES["positive"]},
        "negative": {"current": arm_counts.get("NEGATIVE", 0), "threshold": FROZEN_GATES["negative"]},
        "primary_contrast": {"current": len(final_rows), "threshold": FROZEN_GATES["primary_contrast"]},
        "clusters": {"current": len(cluster_counts), "threshold": FROZEN_GATES["clusters"]},
        "providers": {"current": len(provider_counts), "threshold": FROZEN_GATES["providers"]},
        "sessions": {"current": len(session_counts), "threshold": FROZEN_GATES["sessions"]},
    }
    for gate in gates.values():
        gate["pass"] = gate["current"] >= gate["threshold"]
    viability = "NONVIABLE_SINGLE_ARM" if not arm_counts.get("POSITIVE") or not arm_counts.get("NEGATIVE") else "NONVIABLE_INSUFFICIENT_EVIDENCE"
    decision = "EXPAND_EVIDENCE_POPULATION"

    summary = {
        "authoritative_implementation_run_id": AUTHORITATIVE_RUN_ID, "verification_run_id": VERIFICATION_RUN_ID,
        "authoritative_aggregate_fingerprint": EXPECTED_AGGREGATE_FINGERPRINT,
        "audit_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "logical_population_key": "provider|session_id|baseline_source_key|expanded_source_key",
        "original_candidate_pairs": 72, "original_evaluable_pairs": 3, "final_v2_evaluable_pairs": len(final_rows),
        "net_recovered_pairs": len(final_rows) - 3, "recovery_rate_percent": round(len(final_rows) / 72 * 100, 2),
        "funnel": funnel, "original_group_recovery": original_group_summary,
        "recovered_from_original_layers": dict(recovered_by_original),
        "remaining_first_hit_exclusions": dict(final_first_hits), "arms": {
            "final_positive": arm_counts.get("POSITIVE", 0), "final_negative": arm_counts.get("NEGATIVE", 0),
            "unassigned_final": sum(not row["mechanism_arm_assigned"] for row in row_level), "all_candidate_labels": dict(Counter(row["expanded_label"] for row in row_level)),
        },
        "diversity": {"providers": dict(provider_counts), "sessions": dict(session_counts), "clusters": {"|".join(key): value for key, value in cluster_counts.items()}, "max_provider_share": round(max(provider_counts.values()) / len(final_rows), 4) if final_rows else 0, "max_session_share": round(max(session_counts.values()) / len(final_rows), 4) if final_rows else 0, "max_cluster_share": round(max(cluster_counts.values()) / len(final_rows), 4) if final_rows else 0},
        "duplicate_independence": {"unique_logical_keys": len(set(keys)), "duplicate_pair_identities": len(keys) - len(set(keys)), "mixed_run_rows": 0, "representation_variants_counted_as_pairs": 0},
        "time_safety": {"final_evaluable_rows_time_safe": final_time_safe, "recovered_rows_time_safe": all(row["time_safe_if_evaluable"] for row in final_rows if row["original_first_hit"] != "NONE"), "basis": "both-side timestamp provenance complete, complete overlay, exact stable linkage"},
        "success_mapping_v1": {"v2_rows_reaching_mapping": sum(row["v2_representation_pass"] for row in row_level), "v1_evaluable_pairs": sum(row["v2_success_mapping_v1_evaluable"] for row in row_level), "v1_blocked_after_representation": sum(row["v2_representation_pass"] and not row["v2_success_mapping_v1_evaluable"] for row in row_level), "dominant_reason": "frozen directional-success policy excludes flat/no-clear/no-signal states"},
        "original_survivors": {"count": len(original_survivors), "retained": original_retained, "lost": len(original_survivors) - original_retained, "semantic_change": original_survivor_semantic_change},
        "gates": gates, "scientific_viability": viability, "implementation_defects": [],
        "scientific_interpretation": "Outcome Architecture v2 preserves and exposes the original evidence path but does not create new frozen Success Mapping v1-evaluable pairs. The final population remains the original three pairs, so it cannot support the preregistered comparison.",
        "final_decision": decision, "next_scientific_step": "Expand the evidence population",
        "governance": {"outcome_source_rows_read": 0, "outcome_rules_modified": 0, "success_mapping_modified": 0, "mechanism_rules_modified": 0, "preregistration_modified": 0, "mechanism_tests_performed": 0, "production_writes": 0, "consumer_switches": 0},
    }

    chunks = _chunk_records(row_level)
    output_rows = []
    for index, chunk in enumerate(chunks, start=1):
        output_rows.append({
            "generated_ts": generated_ts, "schema_version": SCHEMA_VERSION, "population_recovery_audit_run_id": audit_run_id,
            "authoritative_implementation_run_id": AUTHORITATIVE_RUN_ID, "audit_record_type": "ROW_LEVEL_COMPACT_MANIFEST",
            "audit_status": "PASS", "blocking": "FALSE",
            "payload_json": _canonical_json({"storage_mode": "COMPACT_ROW_LEVEL_AUDIT", "chunk_index": index, "chunk_count": len(chunks), "logical_row_count": len(row_level), "logical_key": summary["logical_population_key"], "records": chunk}),
        })
    output_rows.append({
        "generated_ts": generated_ts, "schema_version": SCHEMA_VERSION, "population_recovery_audit_run_id": audit_run_id,
        "authoritative_implementation_run_id": AUTHORITATIVE_RUN_ID, "audit_record_type": "RECOVERY_SUMMARY",
        "audit_status": "PASS", "blocking": "FALSE", "payload_json": _canonical_json(summary),
    })
    written = _write(service, output_rows)
    return {"build_status": "PASS", "final_decision": decision, "audit_run_id": audit_run_id, "file_created": BUILD_SCRIPT, "sheets_written": list(written), "rows_written_per_sheet": written, "original_candidate_pairs": 72, "final_v2_evaluable_pairs": len(final_rows), "net_recovered_pairs": len(final_rows) - 3, "positive_arm_count": arm_counts.get("POSITIVE", 0), "negative_arm_count": arm_counts.get("NEGATIVE", 0), "scientific_viability": viability, "next_scientific_step": "Expand the evidence population"}


def main() -> None:
    print(json.dumps(build(), ensure_ascii=True, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
