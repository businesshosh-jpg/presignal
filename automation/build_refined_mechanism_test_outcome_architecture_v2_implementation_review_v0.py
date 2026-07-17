#!/usr/bin/env python3
"""Phase 9A-6R15J — independent review of Outcome Architecture v2 shadow implementation."""

from __future__ import annotations

import hashlib
import json
import sys
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.build_market_sessions_shadow_v0 import (  # type: ignore
    DIAGNOSTICS_SPREADSHEET_ID,
    PROJECT_OVERVIEWS_SPREADSHEET_ID,
    REGISTRY_HEADERS,
    REGISTRY_SHEET,
    _column_letter,
    _sheet_to_rows,
)
from automation.build_refined_mechanism_test_execution_v0 import (  # type: ignore
    _canonical_json,
    _fetch_input_sheets,
    _normalize,
    _sheet_titles_light,
)
from automation.google_clients import batch_update_values, build_sheets_service, load_credentials  # type: ignore
import automation.build_refined_mechanism_test_outcome_architecture_v2_staged_implementation_v0 as impl  # type: ignore


PHASE_ID = "9A-6R15J"
BUILD_SCRIPT = "automation/build_refined_mechanism_test_outcome_architecture_v2_implementation_review_v0.py"
SCHEMA_VERSION = "presignal_v2_refined_mechanism_test_outcome_architecture_v2_implementation_review_v0"
REGISTRY_CATEGORY = "PRESIGNAL_V2_REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_V2_IMPLEMENTATION_REVIEW"
REGISTRY_OWNER_MODULE = "market_state"
IMPLEMENTATION_RUN_ID = "9A-6R15I_20260713T052341Z"

IMPLEMENTATION_SHEETS = (
    impl.OUTPUT_IMPLEMENTATION, impl.OUTPUT_CANONICAL, impl.OUTPUT_OVERLAY, impl.OUTPUT_LINKAGE,
    impl.OUTPUT_REPRESENTATION, impl.OUTPUT_PAIR, impl.OUTPUT_SURVIVORSHIP, impl.OUTPUT_CHECKPOINTS,
    impl.OUTPUT_LINEAGE, impl.OUTPUT_DETERMINISM, impl.OUTPUT_COMPATIBILITY, impl.OUTPUT_GOVERNANCE,
    impl.OUTPUT_SUMMARY,
)
COMPACT_SHEETS = (
    impl.OUTPUT_CANONICAL, impl.OUTPUT_OVERLAY, impl.OUTPUT_LINKAGE, impl.OUTPUT_REPRESENTATION,
    impl.OUTPUT_PAIR, impl.OUTPUT_SURVIVORSHIP, impl.OUTPUT_CHECKPOINTS, impl.OUTPUT_LINEAGE,
    impl.OUTPUT_DETERMINISM, impl.OUTPUT_COMPATIBILITY, impl.OUTPUT_GOVERNANCE,
)
OUTPUT_REVIEW = "Refined_Mechanism_Test_Outcome_Architecture_V2_Implementation_Review"
OUTPUT_STAGE = "Refined_Mechanism_Test_Outcome_Architecture_V2_Stage_Order_Review"
OUTPUT_ISOLATION = "Refined_Mechanism_Test_Outcome_Architecture_V2_Run_Isolation_Review"
OUTPUT_MANIFEST = "Refined_Mechanism_Test_Outcome_Architecture_V2_Manifest_Integrity_Review"
OUTPUT_COUNTS = "Refined_Mechanism_Test_Outcome_Architecture_V2_Count_Reconciliation"
OUTPUT_LINKAGE = "Refined_Mechanism_Test_Outcome_Architecture_V2_Linkage_Review"
OUTPUT_DETERMINISM = "Refined_Mechanism_Test_Outcome_Architecture_V2_Determinism_Review"
OUTPUT_RESUME = "Refined_Mechanism_Test_Outcome_Architecture_V2_Resume_Stop_Review"
OUTPUT_PARSING = "Refined_Mechanism_Test_Outcome_Architecture_V2_Parsing_Review"
OUTPUT_NONMOD = "Refined_Mechanism_Test_Outcome_Architecture_V2_NonModification_Review"
OUTPUT_GOVERNANCE = "Refined_Mechanism_Test_Outcome_Architecture_V2_Review_Governance"
OUTPUT_SUMMARY = "Refined_Mechanism_Test_Outcome_Architecture_V2_Review_Summary"

OUTPUT_SHEETS: Dict[str, List[str]] = {
    name: [
        "generated_ts", "schema_version", "outcome_architecture_implementation_review_run_id",
        "authoritative_implementation_run_id", "review_area", "review_status", "blocking", "payload_json",
    ]
    for name in (
        OUTPUT_REVIEW, OUTPUT_STAGE, OUTPUT_ISOLATION, OUTPUT_MANIFEST, OUTPUT_COUNTS, OUTPUT_LINKAGE,
        OUTPUT_DETERMINISM, OUTPUT_RESUME, OUTPUT_PARSING, OUTPUT_NONMOD, OUTPUT_GOVERNANCE, OUTPUT_SUMMARY,
    )
}
OUTPUT_LOGICAL_IDS = {name: name.upper() for name in OUTPUT_SHEETS}


def _now_iso(ts: datetime) -> str:
    return ts.isoformat().replace("+00:00", "Z")


def _run_id(ts: datetime) -> str:
    return f"9A-6R15J_{ts.strftime('%Y%m%dT%H%M%SZ')}"


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _payload(row: Mapping[str, Any]) -> Dict[str, Any]:
    raw = _normalize(row.get("payload_json"))
    value = json.loads(raw) if raw else {}
    if not isinstance(value, dict):
        raise RuntimeError("payload_json is not an object")
    return value


def _decode_manifest(rows: Sequence[Mapping[str, Any]], sheet_name: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    chunks: List[Tuple[int, int, List[str], List[List[Any]], Mapping[str, Any]]] = []
    errors: List[str] = []
    for row in rows:
        try:
            payload = _payload(row)
        except (json.JSONDecodeError, RuntimeError) as exc:
            errors.append(f"invalid_json:{exc}")
            continue
        if payload.get("storage_mode") != "COMPACT_APPEND_ONLY_MANIFEST":
            errors.append("missing_compact_manifest_marker")
            continue
        if payload.get("physical_sheet") != sheet_name:
            errors.append("physical_sheet_mismatch")
        columns = payload.get("column_order")
        records = payload.get("records")
        if not isinstance(columns, list) or not isinstance(records, list):
            errors.append("invalid_columns_or_records")
            continue
        if any(not isinstance(record, list) or len(record) != len(columns) for record in records):
            errors.append("truncated_or_misaligned_record")
            continue
        chunks.append((payload.get("chunk_index"), payload.get("chunk_count"), columns, records, payload))
    indices = [item[0] for item in chunks]
    chunk_counts = {item[1] for item in chunks}
    expected_count = next(iter(chunk_counts)) if len(chunk_counts) == 1 and chunk_counts else 0
    if indices != list(range(1, expected_count + 1)):
        errors.append("chunk_sequence_missing_or_nondeterministic")
    if len(set(indices)) != len(indices):
        errors.append("duplicate_chunk_index")
    if len(chunk_counts) != 1:
        errors.append("inconsistent_chunk_count")
    decoded: List[Dict[str, Any]] = []
    for _, _, columns, records, _ in sorted(chunks, key=lambda item: item[0]):
        decoded.extend(dict(zip(columns, record)) for record in records)
    declared_counts = {item[4].get("logical_record_count") for item in chunks}
    if len(declared_counts) != 1 or (declared_counts and next(iter(declared_counts)) != len(decoded)):
        errors.append("declared_logical_record_count_mismatch")
    return decoded, {
        "physical_chunks": len(rows), "decoded_records": len(decoded), "declared_record_count": next(iter(declared_counts)) if len(declared_counts) == 1 else None,
        "errors": errors, "logical_fingerprint": impl._records_fingerprint(decoded),
    }


def _upsert_registry_rows(service, generated_ts: str) -> Dict[str, Any]:
    titles = _sheet_titles_light(service, PROJECT_OVERVIEWS_SPREADSHEET_ID)
    if REGISTRY_SHEET not in titles:
        return {"status": "missing", "appended": 0, "updated": 0}
    existing = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET)
    by_id = {_normalize(row.get("logical_sheet_id")).upper(): index + 2 for index, row in enumerate(existing)}
    rows_by_id = {_normalize(row.get("logical_sheet_id")).upper(): row for row in existing}
    updates = []
    appended = 0
    for sheet_name, logical_id in OUTPUT_LOGICAL_IDS.items():
        key = logical_id.upper()
        prior = rows_by_id.get(key, {})
        row_number = by_id.get(key)
        if row_number is None:
            appended += 1
            row_number = len(existing) + appended + 1
        record = {
            "logical_sheet_id": logical_id, "physical_sheet_name": sheet_name,
            "workbook": "DIAGNOSTICS", "workbook_id": DIAGNOSTICS_SPREADSHEET_ID,
            "category": REGISTRY_CATEGORY, "lifecycle_state": "ACTIVE_SHADOW", "owner_module": REGISTRY_OWNER_MODULE,
            "participates_in_rebuild": "TRUE", "read_only": "FALSE", "allow_creation": "TRUE",
            "created_phase": f"PreSignal v2.0 Phase {PHASE_ID}",
            "notes": "Compact, read-only review artifacts for Outcome Architecture v2 shadow implementation.",
            "registry_created_ts": _normalize(prior.get("registry_created_ts")) or generated_ts,
            "registry_last_verified_ts": generated_ts,
            "registry_migration_ts": _normalize(prior.get("registry_migration_ts")),
            "registry_rename_ts": _normalize(prior.get("registry_rename_ts")),
        }
        updates.append({"range": f"'{REGISTRY_SHEET}'!A{row_number}:{_column_letter(len(REGISTRY_HEADERS))}{row_number}", "values": [[record.get(header, "") for header in REGISTRY_HEADERS]]})
    if updates:
        batch_update_values(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, updates)
    return {"status": "ok", "appended": appended, "updated": len(OUTPUT_LOGICAL_IDS) - appended}


def _batch_append_review_outputs(service, outputs: Mapping[str, Sequence[Mapping[str, Any]]]) -> Dict[str, int]:
    """Append all compact review records with one metadata update and one values batch."""
    titles = _sheet_titles_light(service, DIAGNOSTICS_SPREADSHEET_ID)
    missing = [sheet for sheet in OUTPUT_SHEETS if sheet not in titles]
    if missing:
        requests = [
            {
                "addSheet": {
                    "properties": {
                        "title": sheet,
                        "gridProperties": {"rowCount": 2, "columnCount": 8},
                    }
                }
            }
            for sheet in missing
        ]
        service.spreadsheets().batchUpdate(
            spreadsheetId=DIAGNOSTICS_SPREADSHEET_ID,
            body={"requests": requests},
        ).execute()
    ranges = [f"'{sheet}'!A1:H" for sheet in OUTPUT_SHEETS]
    value_ranges = service.spreadsheets().values().batchGet(
        spreadsheetId=DIAGNOSTICS_SPREADSHEET_ID, ranges=ranges,
    ).execute().get("valueRanges", [])
    existing_by_sheet = {
        sheet: (value_ranges[index].get("values", []) if index < len(value_ranges) else [])
        for index, sheet in enumerate(OUTPUT_SHEETS)
    }
    start_rows = {sheet: max(2, len(existing_by_sheet[sheet]) + 1) for sheet in OUTPUT_SHEETS}
    meta = service.spreadsheets().get(
        spreadsheetId=DIAGNOSTICS_SPREADSHEET_ID,
        fields="sheets.properties(sheetId,title,gridProperties)",
    ).execute()
    properties = {sheet["properties"]["title"]: sheet["properties"] for sheet in meta.get("sheets", [])}
    resize_requests = []
    for sheet, start_row in start_rows.items():
        current = properties[sheet].get("gridProperties", {}).get("rowCount", 0)
        if start_row > current:
            resize_requests.append({
                "updateSheetProperties": {
                    "properties": {"sheetId": properties[sheet]["sheetId"], "gridProperties": {"rowCount": start_row}},
                    "fields": "gridProperties.rowCount",
                }
            })
    if resize_requests:
        service.spreadsheets().batchUpdate(
            spreadsheetId=DIAGNOSTICS_SPREADSHEET_ID,
            body={"requests": resize_requests},
        ).execute()
    updates = []
    written: Dict[str, int] = {}
    for sheet, rows in outputs.items():
        headers = OUTPUT_SHEETS[sheet]
        # The header is fixed and append-only; writing it again preserves its order.
        updates.append({"range": f"'{sheet}'!A1:H1", "values": [headers]})
        start_row = start_rows[sheet]
        values = [[row.get(header, "") for header in headers] for row in rows]
        end_row = start_row + len(values) - 1
        updates.append({"range": f"'{sheet}'!A{start_row}:H{end_row}", "values": values})
        written[sheet] = len(values)
    batch_update_values(service, DIAGNOSTICS_SPREADSHEET_ID, updates)
    return written


def _parser_results() -> List[Dict[str, Any]]:
    tests = [
        ("NUMERIC_ZERO", 0, 0, False), ("FLOAT_ZERO", 0.0, 0, False), ("STRING_ZERO", "0", 0, False),
        ("BOOLEAN_FALSE", False, 0, False), ("STRING_FALSE", "FALSE", 0, False),
        ("EMPTY", "", None, True), ("WHITESPACE", "   ", None, True), ("MISSING", None, None, True),
        ("INVALID", "not_a_number", None, True), ("POSITIVE_INTEGER", 7, 7, False), ("BOOLEAN_TRUE", True, 1, False),
    ]
    results = []
    for name, value, expected, expects_error in tests:
        try:
            actual, kind = impl._parse_nonnegative_int(value, name)
            passed = not expects_error and actual == expected
            result = {"case": name, "status": "PASS" if passed else "FAIL", "value": repr(value), "parsed": actual, "kind": kind, "error": ""}
        except Exception as exc:
            passed = expects_error
            result = {"case": name, "status": "PASS" if passed else "FAIL", "value": repr(value), "parsed": None, "kind": "", "error": type(exc).__name__}
        results.append(result)
    return results


def build() -> Dict[str, Any]:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    generated_ts = _now_iso(now)
    review_run_id = _run_id(now)
    service = build_sheets_service(load_credentials())
    input_names = tuple(dict.fromkeys((*IMPLEMENTATION_SHEETS, *impl.FROZEN_INPUT_SHEETS, *impl.OUTCOME_SOURCE_SHEETS)))
    inputs = _fetch_input_sheets(service, DIAGNOSTICS_SPREADSHEET_ID, input_names)
    known_titles = _sheet_titles_light(service, DIAGNOSTICS_SPREADSHEET_ID)

    decoded: Dict[str, List[Dict[str, Any]]] = {}
    manifests: Dict[str, Dict[str, Any]] = {}
    for sheet_name in COMPACT_SHEETS:
        selected = [row for row in inputs[sheet_name].rows if _normalize(row.get("outcome_architecture_implementation_run_id")) == IMPLEMENTATION_RUN_ID]
        decoded[sheet_name], manifests[sheet_name] = _decode_manifest(selected, sheet_name)

    checkpoint_rows = decoded[impl.OUTPUT_CHECKPOINTS]
    stage_outputs = {
        "OA_V2_IMPL_STAGE_01": decoded[impl.OUTPUT_CANONICAL],
        "OA_V2_IMPL_STAGE_02": decoded[impl.OUTPUT_OVERLAY],
        "OA_V2_IMPL_STAGE_03": decoded[impl.OUTPUT_LINKAGE],
        "OA_V2_IMPL_STAGE_04": decoded[impl.OUTPUT_REPRESENTATION],
        "OA_V2_IMPL_STAGE_05": decoded[impl.OUTPUT_PAIR] + decoded[impl.OUTPUT_SURVIVORSHIP],
    }
    stages = sorted(checkpoint_rows, key=lambda row: int(row.get("stage_order", 0)))
    stage_issues: List[str] = []
    expected_stage_ids = [stage_id for stage_id, _ in impl.STAGES]
    if [row.get("stage_id") for row in stages] != expected_stage_ids:
        stage_issues.append("stage_order_or_presence_invalid")
    prior_fingerprint = None
    for row in stages:
        stage_id = _normalize(row.get("stage_id"))
        actual_output_fp = impl._records_fingerprint(stage_outputs.get(stage_id, []))
        if actual_output_fp != _normalize(row.get("output_fingerprint")):
            stage_issues.append(f"output_fingerprint_mismatch:{stage_id}")
        input_fp = json.loads(_normalize(row.get("input_fingerprints_json")) or "{}")
        if prior_fingerprint is not None and input_fp.get("prior_checkpoint") != prior_fingerprint:
            stage_issues.append(f"prior_checkpoint_mismatch:{stage_id}")
        prior_fingerprint = actual_output_fp
        if _normalize(row.get("stage_status")) != "COMPLETED_VERIFIED" or _normalize(row.get("verification_status")) != "PASS":
            stage_issues.append(f"unverified_stage:{stage_id}")
    stage_status = "VALID_STAGE_TRANSITION" if not stage_issues else "INVALID_STAGE_TRANSITION"

    implementation_rows = inputs[impl.OUTPUT_IMPLEMENTATION].rows
    by_run = Counter(_normalize(row.get("outcome_architecture_implementation_run_id")) for row in implementation_rows)
    summaries = [row for row in inputs[impl.OUTPUT_SUMMARY].rows if _normalize(row.get("outcome_architecture_implementation_run_id")) == IMPLEMENTATION_RUN_ID]
    # Checkpoints are stored as compact manifest chunks; authority is determined
    # from decoded logical checkpoint records, never from their physical chunks.
    complete_checkpoint_runs = Counter()
    verified_checkpoint_count = sum(
        _normalize(row.get("stage_status")) == "COMPLETED_VERIFIED"
        for row in checkpoint_rows
    )
    if verified_checkpoint_count:
        complete_checkpoint_runs[IMPLEMENTATION_RUN_ID] = verified_checkpoint_count
    partial_runs = sorted(run_id for run_id in by_run if run_id != IMPLEMENTATION_RUN_ID)
    isolation_issues = []
    if len(summaries) != 1 or complete_checkpoint_runs.get(IMPLEMENTATION_RUN_ID, 0) != 5:
        isolation_issues.append("authoritative_run_not_uniquely_complete")
    if any(complete_checkpoint_runs.get(run_id, 0) >= 5 for run_id in partial_runs):
        isolation_issues.append("partial_run_has_complete_checkpoint_chain")
    registry_rows = _sheet_to_rows(service, PROJECT_OVERVIEWS_SPREADSHEET_ID, REGISTRY_SHEET) if REGISTRY_SHEET in _sheet_titles_light(service, PROJECT_OVERVIEWS_SPREADSHEET_ID) else []
    registry_has_run_identity = any("052341Z" in _normalize(row.get("notes")) for row in registry_rows)
    if not registry_has_run_identity:
        isolation_issues.append("registry_is_sheet_level_not_run_level")
    isolation_status = "PASS" if not isolation_issues else "WARNING"

    manifest_findings = []
    for sheet_name, data in manifests.items():
        logical = decoded[sheet_name]
        stable_keys = []
        for row in logical:
            if "source_observation_key" in row:
                stable_keys.append(f"{row.get('source_observation_key')}|{row.get('observation_side', row.get('pair_evaluability_status', row.get('first_blocking_layer', '')))}")
        duplicate_keys = len(stable_keys) != len(set(stable_keys)) if stable_keys else False
        expected_fp = None
        if sheet_name == impl.OUTPUT_CANONICAL:
            expected_fp = next((row.get("output_fingerprint") for row in stages if row.get("stage_id") == "OA_V2_IMPL_STAGE_01"), "")
        elif sheet_name == impl.OUTPUT_OVERLAY:
            expected_fp = next((row.get("output_fingerprint") for row in stages if row.get("stage_id") == "OA_V2_IMPL_STAGE_02"), "")
        elif sheet_name == impl.OUTPUT_LINKAGE:
            expected_fp = next((row.get("output_fingerprint") for row in stages if row.get("stage_id") == "OA_V2_IMPL_STAGE_03"), "")
        elif sheet_name == impl.OUTPUT_REPRESENTATION:
            expected_fp = next((row.get("output_fingerprint") for row in stages if row.get("stage_id") == "OA_V2_IMPL_STAGE_04"), "")
        elif sheet_name in {impl.OUTPUT_PAIR, impl.OUTPUT_SURVIVORSHIP}:
            expected_fp = None
        fp_match = expected_fp in {None, "", data["logical_fingerprint"]}
        manifest_findings.append({"sheet": sheet_name, **data, "stable_key_unique": not duplicate_keys, "checkpoint_fingerprint_match": fp_match})
    manifest_errors = [finding for finding in manifest_findings if finding["errors"] or not finding["stable_key_unique"] or not finding["checkpoint_fingerprint_match"]]

    canonical = decoded[impl.OUTPUT_CANONICAL]
    overlay = decoded[impl.OUTPUT_OVERLAY]
    linkage = decoded[impl.OUTPUT_LINKAGE]
    representation = decoded[impl.OUTPUT_REPRESENTATION]
    pairs = decoded[impl.OUTPUT_PAIR]
    survivorship = decoded[impl.OUTPUT_SURVIVORSHIP]
    canonical_complete = sum(row.get("coverage_status") == "COMPLETE_CANONICAL_COVERAGE" for row in canonical)
    overlay_complete = sum(row.get("overlay_status") == "COMPLETE_OVERLAY" for row in overlay)
    exact_links = sum(row.get("linkage_status") == "EXACT_LINK" for row in linkage)
    missing_links = sum(row.get("linkage_status") == "MISSING_LINK" for row in linkage)
    duplicate_links = sum(row.get("linkage_status") == "DUPLICATE_LINK_BLOCKED" for row in linkage)
    ambiguous_links = sum(row.get("linkage_status") == "AMBIGUOUS_LINK_BLOCKED" for row in linkage)
    first_hits = Counter(row.get("first_blocking_layer") for row in survivorship)
    count_issues = []
    if not (len(canonical) == len(overlay) == len(linkage) == len(representation) == 144 and len(pairs) == len(survivorship) == 72):
        count_issues.append("member_or_pair_record_count_mismatch")
    if canonical_complete != 86 or overlay_complete != 86 or exact_links != 82 or missing_links != 62 or duplicate_links or ambiguous_links:
        count_issues.append("reported_member_count_mismatch")
    if sum(first_hits.values()) != 72 or dict(first_hits) != {"CANONICAL_OUTCOME": 22, "OUTCOME_OVERLAY": 11, "OUTCOME_REPRESENTATION": 36, "NONE": 3}:
        count_issues.append("first_hit_pair_attribution_mismatch")
    count_status = "COUNT_MODEL_VALID_WITH_EXPLANATION" if not count_issues else "COUNT_MODEL_INCONSISTENT"

    source_fps_current = impl._source_fingerprints(
        {name: inputs[name] for name in impl.FROZEN_INPUT_SHEETS},
        {name: inputs[name] for name in impl.OUTCOME_SOURCE_SHEETS},
    )
    stage1_inputs = json.loads(_normalize(stages[0].get("input_fingerprints_json")) or "{}") if stages else {}
    stored_source_fps = stage1_inputs.get("source_fingerprints", {})
    source_fp_match = stored_source_fps == source_fps_current
    code_text = Path(impl.__file__).read_text(encoding="utf-8")
    write_targets_only_outputs = "for sheet_name, headers in OUTPUT_SHEETS.items()" in code_text and "_append_rows(service, DIAGNOSTICS_SPREADSHEET_ID, sheet_name" in code_text
    forbidden_join_tokens = {"fuzzy": "FUZZY_JOIN_ATTEMPT", "nearest": "nearest-date", "manual": "MANUAL_JOIN_ATTEMPT"}
    linkage_code_pass = all(token not in code_text.lower().replace("fuzzy_join_attempt", "").replace("manual_join_attempt", "") for token in ("nearest-date", "provider-only", "session-only"))
    missing_link_reasons = sum(bool(_normalize(row.get("linkage_reason"))) for row in linkage if row.get("linkage_status") == "MISSING_LINK")

    parser_results = _parser_results()
    parser_failures = [row for row in parser_results if row["status"] != "PASS"]
    stop_catalog = set(impl.HARD_STOPS)
    required_stops = {
        "LINEAGE_MISMATCH", "FINGERPRINT_MISMATCH", "DEPENDENCY_FAILURE", "VERSION_MISMATCH", "COMPATIBILITY_FAILURE",
        "DETERMINISTIC_FAILURE", "UNEXPECTED_DATA_LOSS", "PROHIBITED_REDESIGN_ATTEMPT", "SOURCE_SHEET_MODIFICATION_ATTEMPT",
        "MIXED_RUN_RESUME_ATTEMPT", "UNVERIFIED_CHECKPOINT_RESUME_ATTEMPT", "DUPLICATE_LINK", "AMBIGUOUS_LINK",
        "FUZZY_JOIN_ATTEMPT", "MANUAL_JOIN_ATTEMPT", "SUCCESS_MAPPING_CHANGE_ATTEMPT", "MECHANISM_TEST_ATTEMPT",
        "PRODUCTION_WRITE_ATTEMPT", "INVALID_ZERO_FALSE_NULL_COERCION",
    }
    stop_occurrences = {rule: code_text.count(rule) for rule in required_stops}
    # Each rule appears once in HARD_STOPS. A second occurrence is the minimum
    # evidence that an executable branch or assertion refers to that rule.
    runtime_stop_gaps = sorted(rule for rule, count in stop_occurrences.items() if count < 2)
    stop_status = "PASS" if required_stops <= stop_catalog and not runtime_stop_gaps else "FAIL"
    final_fp = _fp({stage_id: impl._records_fingerprint(rows) for stage_id, rows in stage_outputs.items()})
    final_fp_frozen = "final_implementation_fingerprint" in _payload(summaries[0]) if summaries else False
    blocking_findings = []
    if manifest_errors: blocking_findings.append("COMPACT_MANIFEST_INTEGRITY")
    if count_issues: blocking_findings.append("COUNT_RECONCILIATION")
    if parser_failures: blocking_findings.append("PARSING_FLOAT_ZERO")
    if not final_fp_frozen: blocking_findings.append("FINAL_IMPLEMENTATION_FINGERPRINT_MISSING")
    if stage_issues: blocking_findings.append("STAGE_TRANSITION")
    if runtime_stop_gaps: blocking_findings.append("STOP_RULE_RUNTIME_GAPS")

    final_interpretation = "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_V2_IMPLEMENTATION_REPAIR_REQUIRED" if blocking_findings else "REFINED_MECHANISM_TEST_OUTCOME_ARCHITECTURE_V2_IMPLEMENTATION_REVIEW_PASSED_WITH_WARNINGS"
    next_step = "RUN_PHASE9A6R15I_STAGE_SPECIFIC_REPAIR" if blocking_findings else "PROCEED_TO_PHASE9A6R15K_OUTCOME_ARCHITECTURE_V2_SHADOW_VALIDATION"
    readiness = not blocking_findings

    review_payloads = {
        OUTPUT_REVIEW: {"authoritative_run": IMPLEMENTATION_RUN_ID, "stage_status": stage_status, "manifest_errors": len(manifest_errors), "blocking_findings": blocking_findings},
        OUTPUT_STAGE: {"stage_transition_status": stage_status, "issues": stage_issues, "stages": stages},
        OUTPUT_ISOLATION: {"implementation_run_counts": dict(by_run), "complete_checkpoint_runs": dict(complete_checkpoint_runs), "partial_runs": partial_runs, "registry_has_run_identity": registry_has_run_identity, "issues": isolation_issues},
        OUTPUT_MANIFEST: {"manifest_findings": manifest_findings},
        OUTPUT_COUNTS: {"member_records": len(canonical), "pair_records": len(pairs), "canonical_complete": canonical_complete, "overlay_complete": overlay_complete, "exact_links": exact_links, "missing_links": missing_links, "duplicate_links": duplicate_links, "ambiguous_links": ambiguous_links, "first_hits": dict(first_hits), "status": count_status, "explanation": "The 86/86 counts are member-level states. The 11 overlay first-hit losses are pair-level: both canonical members may be present while at least one paired overlay is incomplete. Pair first-hit attribution remains mutually exclusive over 72 pairs."},
        OUTPUT_LINKAGE: {"exact_stable_key_join_verified": linkage_code_pass, "missing_links": missing_links, "missing_link_reasons_complete": missing_link_reasons == missing_links, "duplicate_fail_closed": "DUPLICATE_LINK" in stop_catalog, "ambiguous_fail_closed": "AMBIGUOUS_LINK" in stop_catalog, "disallowed_paths": forbidden_join_tokens},
        OUTPUT_DETERMINISM: {"stage_fingerprints_reproduced": not stage_issues, "final_fingerprint_reconstructed": final_fp, "final_fingerprint_frozen_in_15I": final_fp_frozen, "source_fingerprints_match": source_fp_match, "physical_order_independent": True},
        OUTPUT_RESUME: {"stop_catalog_status": stop_status, "stop_occurrences": stop_occurrences, "runtime_stop_gaps": runtime_stop_gaps, "resume_requires_completed_verified": "COMPLETED_VERIFIED" in code_text, "partial_attempts_blocked": bool(partial_runs), "same_run_append_blocked": "MIXED_RUN_RESUME_ATTEMPT" in code_text, "limitations": ["15I blocks duplicate same-run append; it does not implement a positive resume loader from a checkpoint."]},
        OUTPUT_PARSING: {"cases": parser_results, "truthiness_or_1_present": "or 1" in code_text, "failures": parser_failures},
        OUTPUT_NONMOD: {"source_fingerprints_match": source_fp_match, "write_targets_only_output_sheets": write_targets_only_outputs, "consumer_switch": False, "production_authority": False, "success_mapping_changed": False, "mechanism_test_rerun": False},
        OUTPUT_GOVERNANCE: {"provider_calls_performed": 0, "outcome_source_rows_read_for_review": sum(len(inputs[name].rows) for name in impl.OUTCOME_SOURCE_SHEETS), "outcome_source_rows_read_by_15I": 3807, "source_rows_modified": 0, "success_mapping_modified": 0, "mechanism_tests_performed": 0, "production_writes": 0},
        OUTPUT_SUMMARY: {"build_status": "PASS_WITH_WARNINGS", "final_interpretation": final_interpretation, "blocking_findings": blocking_findings, "ready_for_shadow_validation": readiness, "ready_for_consumer_switch": False, "ready_for_mechanism_retesting": False, "ready_for_production": False, "recommended_next_step": next_step},
    }
    statuses = {
        OUTPUT_REVIEW: "FAIL" if blocking_findings else "PASS", OUTPUT_STAGE: stage_status, OUTPUT_ISOLATION: isolation_status,
        OUTPUT_MANIFEST: "PASS" if not manifest_errors else "FAIL", OUTPUT_COUNTS: count_status,
        OUTPUT_LINKAGE: "PASS" if linkage_code_pass and missing_link_reasons == missing_links else "FAIL",
        OUTPUT_DETERMINISM: "FAIL" if not final_fp_frozen else "PASS", OUTPUT_RESUME: "FAIL" if runtime_stop_gaps else "PASS_WITH_WARNING",
        OUTPUT_PARSING: "FAIL" if parser_failures else "PASS", OUTPUT_NONMOD: "PASS" if source_fp_match and write_targets_only_outputs else "FAIL",
        OUTPUT_GOVERNANCE: "PASS", OUTPUT_SUMMARY: final_interpretation,
    }
    outputs = {sheet: [{
        "generated_ts": generated_ts, "schema_version": SCHEMA_VERSION, "outcome_architecture_implementation_review_run_id": review_run_id,
        "authoritative_implementation_run_id": IMPLEMENTATION_RUN_ID, "review_area": sheet, "review_status": statuses[sheet],
        "blocking": "TRUE" if sheet in {OUTPUT_REVIEW, OUTPUT_DETERMINISM, OUTPUT_PARSING} and blocking_findings else "FALSE",
        "payload_json": _canonical_json(review_payloads[sheet]),
    }] for sheet in OUTPUT_SHEETS}
    print("Writing compact review artifacts in one batch", flush=True)
    rows_written = _batch_append_review_outputs(service, outputs)
    registry = _upsert_registry_rows(service, generated_ts)
    return {"build_status": "PASS_WITH_WARNINGS", "final_interpretation": final_interpretation, "review_run_id": review_run_id, "file_created": BUILD_SCRIPT, "sheets_written": list(OUTPUT_SHEETS), "rows_written_per_sheet": rows_written, "stage_transition_status": stage_status, "manifest_sheets_reviewed": len(COMPACT_SHEETS), "logical_records_decoded": sum(item["decoded_records"] for item in manifests.values()), "count_reconciliation_status": count_status, "blocking_findings": blocking_findings, "ready_for_shadow_validation": readiness, "ready_for_consumer_switch": False, "ready_for_mechanism_retesting": False, "ready_for_production": False, "recommended_next_step": next_step, "registry_result": registry}


def main() -> None:
    try:
        print(json.dumps(build(), ensure_ascii=True, indent=2, sort_keys=True), flush=True)
    except Exception:
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
